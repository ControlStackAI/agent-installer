"""Support the local agent with editable choices, reviews and read-only evidence.

These commands do not install a system, change disks or authorize a saved plan.
"""
import argparse
import json
import os
from pathlib import Path
from core.diagnostics import inventory, verification, command
from core.support import (preset, read_json, save_new, template, validate_handoff,
                          export_handoff, import_handoff, review)

SHARE = Path('/usr/share/agent-installer')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--share', type=Path, default=SHARE, help='Public support data directory')
    commands = parser.add_subparsers(dest='command', required=True)
    choices = commands.add_parser('presets', help='List presets, or print editable starting choices')
    choices.add_argument('--preset')
    choices.add_argument('--overrides', type=Path, help='Custom JSON; objects merge, lists replace')
    hardware = commands.add_parser('inventory', help='Collect bounded, read-only hardware evidence')
    hardware.add_argument('--output', type=Path)
    verify = commands.add_parser('verify', help='Collect current boot evidence and remaining manual checks')
    verify.add_argument('--handoff', type=Path)
    verify.add_argument('--online', action='store_true', help='Also request a public HTTPS page; no account authentication')
    verify.add_argument('--output', type=Path)
    handoff = commands.add_parser('handoff', help='Create, review, export or import one non-secret JSON record')
    actions = handoff.add_subparsers(dest='action', required=True)
    new = actions.add_parser('new')
    new.add_argument('--preset', default='custom')
    new.add_argument('--overrides', type=Path)
    new.add_argument('--intent', choices=['install', 'recover', 'customize', 'verify'], default='install')
    new.add_argument('--experience', choices=['guided', 'advanced'], default='guided')
    new.add_argument('--output', type=Path)
    for name in ('check', 'review'):
        action = actions.add_parser(name)
        action.add_argument('source', type=Path)
    for name in ('export', 'import'):
        action = actions.add_parser(name)
        action.add_argument('source', type=Path)
        action.add_argument('destination', type=Path)
        if name == 'export':
            action.add_argument('--reviewed', action='store_true', help='Owner reviewed the exact record and approved this destination; not erasure approval')
    args = parser.parse_args(argv)
    os.umask(0o077)
    try:
        if args.command == 'presets':
            if args.overrides and not args.preset:
                raise ValueError('Choose a starting preset, including custom, before applying overrides.')
            value = (preset(args.share, args.preset, read_json(args.overrides) if args.overrides else None)
                     if args.preset else read_json(args.share / 'presets/desktop.json'))
        elif args.command == 'inventory':
            value = inventory()
        elif args.command == 'verify':
            prior = validate_handoff(read_json(args.handoff)) if args.handoff else None
            online = command(['curl', '--silent', '--fail', '--output', '/dev/null', '--connect-timeout', '5',
                              '--max-time', '12', 'https://example.com/']) if args.online else None
            value = verification(inventory(), prior, online)
        elif args.action == 'new':
            choices = preset(args.share, args.preset, read_json(args.overrides) if args.overrides else None)
            # Environment facts only; handoff creation does not require a full hardware report.
            from core.environment import discover
            facts = discover()
            boot = Path('/proc/sys/kernel/random/boot_id')
            source = {k: str(facts[k]) for k in ('distro_id', 'kernel', 'phase')}
            source['boot_id'] = boot.read_text().strip() if boot.is_file() else ''
            value = validate_handoff(template(choices, args.preset, args.intent, args.experience, source))
        elif args.action in ('check', 'review'):
            value = validate_handoff(read_json(args.source))
            if args.action == 'review':
                print(review(value))
                return 0
        elif args.action == 'export':
            export_handoff(args.source, args.destination, reviewed=args.reviewed)
            print('Saved the reviewed record. Credentials and disk approval are not handed off.')
            return 0
        elif args.action == 'import':
            import_handoff(args.source, args.destination)
            print('Imported as untrusted context. Recheck all verification, environment facts and disk choices locally.')
            return 0
        if getattr(args, 'output', None):
            save_new(args.output, value)
            print('Saved a new private report; existing files are never overwritten.')
        else:
            print(json.dumps(value, indent=2, ensure_ascii=False))
        return 0
    except json.JSONDecodeError:
        print('That file is not valid JSON. Ask the assistant to repair its syntax without printing secrets.')
        return 1
    except ValueError as error:
        # These validation messages are static; never echo input documents.
        print(str(error))
        return 1
    except (OSError, KeyError, TypeError):
        print('Cannot access this record or support data. Use regular JSON files, check permissions and choose a new destination; existing files are never overwritten.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
