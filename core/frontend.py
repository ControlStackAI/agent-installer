"""JSON bridge for the optional live TUI; never a disk executor."""
import argparse
import copy
import contextlib
import hashlib
import io
import json
import os
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path

from core.checks import Readiness
from core.environment import discover
from core.diagnostics import inventory, verification
from core.support import (read_json, save_new, preset, template, validate_handoff,
                          import_handoff, export_handoff, review, data_only)

SESSION = Path('/run/agent-installer')
SHARE = Path('/usr/share/agent-installer')


def atomic_json(path, value):
    payload = json.dumps(data_only(value), indent=2, ensure_ascii=False) + '\n'
    if len(payload.encode()) > 131072:
        raise ValueError('This record is too large. Keep the handoff under 128 KiB.')
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, prefix='.ui-', delete=False) as output:
            temporary = Path(output.name)
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(path)  # Replace a symlink itself, never follow it.
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class Bridge:
    def __init__(self, share, work, facts):
        self.share, self.work, self.facts = Path(share), Path(work), facts
        self.record = self.work / 'handoff.json'
        self.work.mkdir(parents=True, exist_ok=True, mode=0o700)

    def handoff(self):
        return validate_handoff(read_json(self.record)) if self.record.exists() else None

    def source(self):
        source = {k: str(self.facts[k]) for k in ('distro_id', 'kernel', 'phase')}
        boot = Path('/proc/sys/kernel/random/boot_id')
        source['boot_id'] = boot.read_text().strip() if boot.is_file() else ''
        return source

    def snapshot(self):
        record = self.handoff()
        ready = self.work / 'readiness.json'
        return {'schema': 1, 'distro': self.facts['distro_name'], 'kernel': self.facts['kernel'],
                'phase': self.facts['phase'], 'presets': read_json(self.share / 'presets/desktop.json')['presets'],
                'handoff': record, 'fingerprint': fingerprint(record) if record else '',
                'review': review(record) if record else 'Choose a preset or talk directly to the assistant. No disk has been selected.',
                'readiness': read_json(ready) if ready.exists() else {'checks': [], 'ready': False},
                'note': 'Readiness is checked again before sign-in and agent launch.'}

    def select(self, name, intent='install'):
        old = self.handoff()
        value = template(preset(self.share, name), name, intent,
                         'advanced' if name == 'custom' else 'guided', self.source())
        if old:
            # Keep historical work, but make the changed choices and checks explicit.
            value.update({k: copy.deepcopy(old[k]) for k in ('plan', 'completed', 'remaining', 'notes')})
            value['checks'] = [dict(c, status='pending') for c in old['checks']]
            value['notes'].append('Starting choices changed in setup; review the plan and recheck it before acting.')
            atomic_json(self.work / 'handoff.previous.json', old)
        atomic_json(self.record, validate_handoff(value))
        return self.snapshot()

    def intent(self, name):
        value = self.handoff() or template(source=self.source())
        value['intent'] = name
        atomic_json(self.record, validate_handoff(value))
        return self.snapshot()

    def readiness(self):
        from core.launcher import read_profile
        image = read_json(Path('/etc/agent-installer/image.json'))
        profile = read_profile(self.share, image['distro'])
        manifest = read_json(self.share / 'runtimes' / (image['runtime'] + '.json'))
        checker = Readiness(profile, auth_endpoints=manifest['authentication_endpoints'])
        result = {'ready': False, 'checks': []}
        for name, action in [('Internet', checker.internet), ('Clock', checker.clock), ('Live ZFS', checker.storage)]:
            ok, message = action()
            result['checks'].append({'name': name, 'status': 'pass' if ok else 'fail', 'detail': message})
            atomic_json(self.work / 'readiness.json', result)
            if not ok:
                break
        result['ready'] = len(result['checks']) == 3 and all(c['status'] == 'pass' for c in result['checks'])
        atomic_json(self.work / 'readiness.json', result)
        return self.snapshot()

    def import_record(self, source):
        # Existing local work is backed up before replacing it, using the same schema.
        old = self.handoff()
        with tempfile.TemporaryDirectory(dir=self.work) as area:
            target = Path(area) / 'handoff.json'
            value = import_handoff(source, target)
            if old:
                atomic_json(self.work / 'handoff.previous.json', old)
            atomic_json(self.record, value)
        return self.snapshot()

    def export_record(self, destination, expected):
        value = self.handoff()
        if not value or expected != fingerprint(value):
            raise ValueError('The record changed since the preview. Review it again before saving.')
        # Snapshot the exact validated preview so an agent editing the active file
        # cannot change what the owner just approved for this save.
        with tempfile.TemporaryDirectory(dir=self.work) as area:
            source = Path(area) / 'record.json'
            save_new(source, value)
            export_handoff(source, destination, reviewed=True)
        return {'message': 'Saved the reviewed non-secret handoff. This is not disk-erasure approval.'}

    def edit(self):
        value = self.handoff() or template(source=self.source(), experience='advanced')
        editor = shlex.split(os.environ.get('EDITOR', ''))
        if not editor:
            editor = [next((p for name in ('nano', 'vi') if (p := shutil.which(name))), 'vi')]
        # Edit a private draft. Invalid input or a cancelled editor never replaces
        # the valid active record. Values remain data, never shell commands.
        with tempfile.TemporaryDirectory(dir=self.work) as area:
            draft = Path(area) / 'handoff.json'
            save_new(draft, value)
            if subprocess.run([*editor, str(draft)]).returncode:
                return {'message': 'Editing cancelled. Your previous choices are preserved.'}
            updated = validate_handoff(read_json(draft))
            updated['experience'] = 'advanced'
            updated['checks'] = [dict(c, status='pending') for c in updated['checks']]
            if self.record.exists():
                atomic_json(self.work / 'handoff.previous.json', value)
            atomic_json(self.record, updated)
        return {'message': 'Saved custom choices. Review the updated plan with the assistant.'}


def live_facts():
    facts = discover()
    if facts['uid'] != 0 or facts['phase'] != 'live':
        raise ValueError('Use this interface on a supported live USB. Use --preview to explore its design elsewhere.')
    mount = subprocess.run(['findmnt', '-n', '-o', 'FSTYPE', '/run'], capture_output=True, text=True)
    if mount.returncode or mount.stdout.strip() != 'tmpfs':
        raise ValueError('Live setup requires private memory-backed session storage.')
    if SESSION.is_symlink() or (SESSION / 'work').is_symlink():
        raise ValueError('The private session directory must not be a symlink.')
    for path in (SESSION, SESSION / 'work'):
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.chmod(0o700)
    return facts


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--share', type=Path, default=SHARE)
    parser.add_argument('action', choices=['state', 'preset', 'intent', 'preflight', 'inventory', 'verify', 'import', 'export', 'edit'])
    parser.add_argument('value', nargs='?')
    parser.add_argument('--fingerprint', default='')
    args = parser.parse_args(argv)
    os.umask(0o077)
    try:
        bridge = Bridge(args.share, SESSION / 'work', live_facts())
        if args.action == 'state': result = bridge.snapshot()
        elif args.action == 'preset': result = bridge.select(args.value)
        elif args.action == 'intent': result = bridge.intent(args.value)
        elif args.action == 'preflight': result = bridge.readiness()
        elif args.action == 'inventory': result = inventory()
        elif args.action == 'verify': result = verification(inventory(), bridge.handoff())
        elif args.action == 'import': result = bridge.import_record(Path(args.value))
        elif args.action == 'export': result = bridge.export_record(Path(args.value), args.fingerprint)
        elif args.action == 'edit': result = bridge.edit()
        print(json.dumps({'ok': True, 'data': result}, ensure_ascii=False))
        return 0
    except json.JSONDecodeError:
        message = 'That record is not valid JSON. The current choices were preserved.'
    except (OSError, TypeError, KeyError):
        message = 'Could not access the record or tools. Check the path, permissions and available commands; existing exports are never overwritten.'
    except ValueError as error:
        message = str(error)
    print(json.dumps({'ok': False, 'error': message}))
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
