"""Bounded read-only hardware and boot evidence. No repairs or pool imports."""
import json
import subprocess
from pathlib import Path
from core.environment import discover

COMMANDS = {
    'disks': ['lsblk', '--json', '--bytes', '--output', 'NAME,PATH,TYPE,SIZE,MODEL,SERIAL,TRAN,FSTYPE,MOUNTPOINTS,RO,RM'],
    'pci_drivers': ['lspci', '-nnk'],
    'network_links': ['ip', '-j', 'link'],
    'radios': ['rfkill', '--json'],
    'root_mount': ['findmnt', '--json', '--output', 'SOURCE,TARGET,FSTYPE', '/'],
    'memory': ['free', '--bytes'],
    'space': ['df', '-B1', '--output=avail,target', '/'],
    'zfs_module': ['modinfo', '-F', 'vermagic', 'zfs'],
    'zfs_version': ['modinfo', '-F', 'version', 'zfs'],
    'pool_health': ['zpool', 'status', '-x'],
    'network_manager': ['systemctl', 'is-active', 'NetworkManager.service'],
}


def command(args, run=subprocess.run):
    try:
        result = run(args, capture_output=True, text=True, timeout=15)
        output = result.stdout[:24000].strip()
        try:
            output = json.loads(output)
        except ValueError:
            pass
        return {'returncode': result.returncode, 'output': output}
    except (OSError, subprocess.TimeoutExpired):
        return {'returncode': None, 'output': 'Unavailable or timed out; inspect with distro-native tools.'}


def inventory(run=subprocess.run, root=Path('/'), facts=None):
    # libzfs utilities can load the module themselves. Never invoke them as a
    # diagnostic on a machine where ZFS is not already loaded.
    zfs_loaded = (root / 'sys/module/zfs').is_dir()
    observations = {name: (command(args, run) if name != 'pool_health' or zfs_loaded else
                           {'returncode': None, 'output': 'ZFS is not loaded; pool inspection skipped without loading it.'})
                    for name, args in COMMANDS.items()}
    observed = facts if facts is not None else discover(root=root, run=run)
    boot_id = root / 'proc/sys/kernel/random/boot_id'
    observed = dict(observed, boot_id=boot_id.read_text().strip() if boot_id.is_file() else '', zfs_loaded=zfs_loaded)
    return {'schema': 1, 'observed': observed, 'evidence': observations,
            'limits': ['Read-only inventory; no driver, firmware, graphics, audio or installation qualification.',
                       'No credentials, Wi-Fi profiles, logs, serial-port contents or authentication directories are collected.']}


def verification(report, handoff=None, online=None):
    facts, evidence = report['observed'], report['evidence']
    checks = []
    def add(name, status, detail):
        checks.append({'name': name, 'status': status, 'detail': detail})
    disk_root = facts['phase'] == 'unconfirmed' and facts['root_type'] not in ('', 'overlay', 'tmpfs', 'ramfs', 'aufs', 'squashfs')
    add('Disk-root candidate', 'pass' if disk_root else 'fail',
        'Inspect the root mount evidence and boot entries; this alone does not prove USB removal.' if disk_root else
        'This is a live session, a chroot, or an unconfirmed root filesystem. Boot the target system before verifying installation.')
    previous = (handoff or {}).get('source', {}).get('boot_id')
    add('New boot since handoff', 'pass' if previous and facts.get('boot_id') and previous != facts['boot_id'] else 'pending',
        'Boot IDs differ.' if previous and facts.get('boot_id') and previous != facts['boot_id'] else
        'No previous boot ID, or the system has not rebooted since this handoff.')
    for name in ('disks', 'pci_drivers', 'network_links', 'radios', 'memory', 'space', 'root_mount'):
        entry = evidence[name]
        add(name.replace('_', ' ').capitalize(), 'pass' if entry['returncode'] == 0 else 'pending',
            'Evidence collected; inspect it for readiness. Collection success is not a hardware test.' if entry['returncode'] == 0 else
            'Evidence unavailable; inspect with distro-native tools.')
    if (handoff or {}).get('choices', {}).get('filesystem', 'zfs') == 'zfs':
        vermagic = evidence['zfs_module']
        output = vermagic['output']
        matched = vermagic['returncode'] == 0 and isinstance(output, str) and output.split() and output.split()[0] == facts['kernel']
        add('ZFS module matches running kernel', 'pass' if matched else 'fail',
            'Module metadata matches; also verify it is loaded and the target pool is healthy.' if matched else 'ZFS module is missing or mismatched.')
        pool = evidence['pool_health']
        add('Imported ZFS pool health', 'pass' if pool['returncode'] == 0 and pool['output'] == 'all pools are healthy' else 'pending',
            str(pool['output']) or 'No healthy imported-pool result; inspect before making changes.')
    if online is not None:
        add('Secure internet reachability', 'pass' if online['returncode'] == 0 else 'fail',
            'HTTPS request completed. This is not a model-response or Wi-Fi reconnect test.')
    for name, detail in (
        ('Boot without installation media', 'Shut down, remove the installation media and boot the target; inspect root and boot entries again.'),
        ('Graphics and desktop', 'Log in and test the chosen desktop, displays, launcher and accessibility settings.'),
        ('Audio and microphone', 'Test playback and recording with the intended devices.'),
        ('Networking after reboot', 'Test the intended Ethernet/Wi-Fi path and reconnect; inventory cannot prove firmware works.'),
        ('Snapshots and recovery', 'Review the recovery plan and test an owner-approved disposable dataset or VM; do not roll back the live root as a probe.'),
    ):
        add(name, 'manual', detail)
    return {'schema': 1, 'status': 'needs-review', 'checks': checks, 'report': report,
            'note': 'No automatic overall installation-success claim. Imported notes and passed evidence checks are not current authorization.'}
