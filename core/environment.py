"""Read-only facts; image metadata never substitutes for runtime detection."""
import os
import platform
import shlex
import subprocess
from pathlib import Path


def os_release(path):
    values = {}
    for line in path.read_text().splitlines() if path.exists() else []:
        if '=' in line and not line.startswith('#'):
            key, value = line.split('=', 1)
            try:
                words = shlex.split(value)
                values[key] = words[0] if words else ''
            except ValueError:
                continue
    return values


def phase(*, in_chroot, live_marker, root_type):
    if in_chroot:
        return 'chroot'
    if live_marker and root_type in ('overlay', 'tmpfs', 'ramfs', 'aufs'):
        return 'live'
    return 'unconfirmed'  # Agent must verify disk boot before calling it installed.


def discover(root=Path('/'), run=subprocess.run):
    distro = os_release(root / 'etc/os-release')
    result = run(['systemd-detect-virt', '--chroot'], capture_output=True, text=True)
    mount = run(['findmnt', '-n', '-o', 'FSTYPE', '/'], capture_output=True, text=True)
    live_marker = (root / 'run/archiso').exists() or (root / 'etc/agent-installer/live-image').exists()
    return {'distro_id': distro.get('ID', 'unknown'), 'distro_name': distro.get('PRETTY_NAME', 'Unknown Linux'),
            'distro_version': distro.get('VERSION_ID', 'rolling'), 'kernel': platform.release(),
            'uid': os.geteuid(), 'root_type': mount.stdout.strip(),
            'phase': phase(in_chroot=result.returncode == 0, live_marker=live_marker,
                           root_type=mount.stdout.strip())}
