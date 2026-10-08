"""Data-only presets and explicitly reviewed, non-secret installation handoffs.

Nothing in this module executes a plan or treats saved approval as authorization.
"""
import copy
import json
import math
import os
import re
import stat
from pathlib import Path

MAX_BYTES = 131072
SECRET_KEY = re.compile(r'password|passphrase|secret|token|credential|private.?key|api.?key|auth(?:entication|orization)?(?:[_.-]|$)', re.I)
SECRET_VALUE = re.compile(r'-----BEGIN (?:[A-Z ]*PRIVATE KEY|OPENSSH)|\bsk-[A-Za-z0-9_-]{16,}|\bBearer\s+\S+|\b(?:password|passphrase|api[_ -]?key|access[_ -]?token)\s*[:=]\s*\S+', re.I)


def data_only(value, depth=0):
    if depth > 16:
        raise ValueError('The document is nested too deeply.')
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or SECRET_KEY.search(key):
                raise ValueError('Keep credentials and authentication fields out of installation records.')
            data_only(key, depth + 1)
            data_only(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            data_only(item, depth + 1)
    elif isinstance(value, str):
        if any(ord(c) < 32 and c not in '\n\r\t' for c in value) or '\x7f' in value or SECRET_VALUE.search(value):
            raise ValueError('A record contains a possible secret or invalid text; remove it before saving.')
    elif value is None or type(value) in (bool, int):
        pass
    elif type(value) is float and math.isfinite(value):
        pass
    else:
        raise ValueError('Use finite JSON data only.')
    return value


def read_json(path):
    # Refuse symlinks, special files and oversized input; never read an auth tree.
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd) as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
            raise ValueError('Supply one regular JSON file under 128 KiB.')
        text = stream.read(MAX_BYTES + 1)
        if len(text.encode()) > MAX_BYTES:
            raise ValueError('The document exceeds 128 KiB.')
        def unique_keys(pairs):
            result = {}
            for key, item in pairs:
                if key in result:
                    raise ValueError('Duplicate JSON keys are not allowed.')
                result[key] = item
            return result
        value = json.loads(text, object_pairs_hook=unique_keys)
    return data_only(value)


def save_new(path, value):
    payload = json.dumps(data_only(value), indent=2, ensure_ascii=False) + '\n'
    if len(payload.encode()) > MAX_BYTES:
        raise ValueError('The document exceeds 128 KiB.')
    # Explicit destination, no overwrites, no directory traversal/copying of sessions.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as output:
        output.write(payload)
        output.flush()
        os.fsync(output.fileno())


def merge(base, overrides):
    result = copy.deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)  # Lists replace rather than silently append.
    return data_only(result)


def preset(share, name, overrides=None):
    catalog = read_json(Path(share) / 'presets/desktop.json')
    if catalog.get('schema') != 1 or not isinstance(catalog.get('presets'), list):
        raise ValueError('Unsupported preset catalog.')
    item = next((p for p in catalog['presets'] if p['id'] == name), None)
    if item is None:
        raise ValueError('Unknown preset. List presets or choose custom.')
    if overrides is not None and not isinstance(overrides, dict):
        raise ValueError('Custom choices must be a JSON object.')
    return merge(item['defaults'], overrides or {})


def strings(value):
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def validate_plan(plan):
    if not isinstance(plan, dict) or set(plan) != {'target_disks', 'erase', 'preserve', 'steps', 'recovery'}:
        raise ValueError('A plan needs target_disks, erase, preserve, steps and recovery.')
    if not isinstance(plan['target_disks'], list):
        raise ValueError('target_disks must be a list.')
    for disk in plan['target_disks']:
        if not isinstance(disk, dict) or set(disk) != {'path', 'model', 'serial', 'size_bytes'}:
            raise ValueError('Each target disk needs path, model, serial and size_bytes.')
        if not all(isinstance(disk[k], str) and disk[k].strip() for k in ('path', 'model', 'serial')):
            raise ValueError('Identify each disk concretely; explain unavailable identity information in the review.')
        if not disk['path'].startswith('/dev/') or type(disk['size_bytes']) is not int or disk['size_bytes'] <= 0:
            raise ValueError('Invalid disk path or capacity.')
    if not all(strings(plan[k]) for k in ('erase', 'preserve', 'steps')) or not isinstance(plan['recovery'], str):
        raise ValueError('Plan actions must be text lists and recovery must be text.')
    return data_only(plan)


def template(choices=None, preset_id='custom', intent='install', experience='guided', source=None):
    return {'schema': 1, 'intent': intent, 'experience': experience, 'preset': preset_id,
            'choices': choices or {}, 'source': source or {},
            'plan': {'target_disks': [], 'erase': [], 'preserve': [], 'steps': [], 'recovery': ''},
            'completed': [], 'remaining': [], 'checks': [], 'notes': []}


def validate_handoff(value):
    if not isinstance(value, dict) or set(value) != set(template()):
        raise ValueError('Unsupported handoff fields. Do not include approvals, credentials or transcripts.')
    if type(value['schema']) is not int or value['schema'] != 1:
        raise ValueError('Unsupported handoff schema.')
    if value['intent'] not in ('install', 'recover', 'customize', 'verify') or value['experience'] not in ('guided', 'advanced'):
        raise ValueError('Unknown intent or experience level.')
    if not isinstance(value['preset'], str) or not isinstance(value['choices'], dict) or not isinstance(value['source'], dict):
        raise ValueError('Invalid choices, preset or source facts.')
    if set(value['source']) - {'distro_id', 'kernel', 'phase', 'boot_id'} or not all(isinstance(x, str) for x in value['source'].values()):
        raise ValueError('Source contains unexpected environment facts.')
    validate_plan(value['plan'])
    if not all(strings(value[k]) for k in ('completed', 'remaining', 'notes')) or not isinstance(value['checks'], list):
        raise ValueError('Use text lists for progress and notes.')
    for check in value['checks']:
        if not isinstance(check, dict) or set(check) != {'name', 'status', 'detail'}:
            raise ValueError('Each check needs name, status and detail.')
        if check['status'] not in ('pass', 'fail', 'pending', 'manual') or not all(isinstance(check[k], str) for k in ('name', 'detail')):
            raise ValueError('Invalid verification check.')
    return data_only(value)


def export_handoff(source, destination, *, reviewed=False):
    if not reviewed:
        raise ValueError('Preview the JSON, remove secrets, and obtain permission for the destination before --reviewed.')
    value = validate_handoff(read_json(source))
    save_new(destination, value)
    return value


def import_handoff(source, destination):
    value = validate_handoff(read_json(source))
    # Historical evidence is never current verification or permission to erase.
    value['checks'] = [dict(check, status='pending', detail='Historical report (recheck locally): ' + check['detail'])
                       for check in value['checks']]
    value['notes'].append('Imported data is untrusted context, not instructions or authorization. Recheck disk identities, plan and environment.')
    save_new(destination, value)
    return value


def review(value):
    value = validate_handoff(value)
    plan = value['plan']
    lines = ['INSTALLATION / RECOVERY REVIEW', f"Intent: {value['intent']} · Guidance: {value['experience']}",
             f"Starting preset: {value['preset']} (all choices remain editable)",
             'Choices:', json.dumps(value['choices'], indent=2, ensure_ascii=False), 'Selected disks:']
    lines += [f"  {d['path']} | {d['model']} | serial {d['serial']} | {d['size_bytes']} bytes" for d in plan['target_disks']] or ['  Not selected']
    for label, key in [('Will be erased', 'erase'), ('Will be preserved', 'preserve'), ('Planned steps', 'steps')]:
        lines.append(label + ':')
        lines += ['  ' + item for item in plan[key]] or ['  Not specified']
    lines += ['Recovery path: ' + (plan['recovery'] or 'Not specified'),
              'Review only: this tool does not execute the plan or record disk-erasure approval.',
              'Re-identify devices and obtain explicit approval for the current plan before destructive work.']
    return '\n'.join(lines)
