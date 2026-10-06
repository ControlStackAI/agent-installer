#!/usr/bin/env python3
"""Boot the actual ISO directly or from a file-backed Ventoy USB, with an opt-in test flag."""
import argparse
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('iso', type=Path)
    parser.add_argument('--distro', choices=['arch', 'nixos'], required=True)
    parser.add_argument('--uefi-code', type=Path, help='OVMF CODE firmware; omit for BIOS')
    parser.add_argument('--uefi-vars', type=Path, help='OVMF VARS template (copied into scratch)')
    parser.add_argument('--timeout', type=int, default=600)
    parser.add_argument('--ventoy-disk', type=Path, help='Regular file containing the ISO on a virtual Ventoy USB; never a host disk')
    args = parser.parse_args()
    if not args.iso.is_file(): parser.error('ISO must be a regular file')
    directory = ROOT / '.build/smoke' / args.distro
    directory.mkdir(parents=True, exist_ok=True)
    mode = ('ventoy-' if args.ventoy_disk else '') + ('uefi' if args.uefi_code else 'bios')
    log = directory / (mode + '.log')
    (directory / (mode + '-result.json')).unlink(missing_ok=True)
    command = ['qemu-system-x86_64', '-machine', 'q35', '-m', '1536', '-smp', '2',
               '-display', 'none', '-monitor', 'none', '-serial', 'file:' + str(log),
               '-nic', 'user,model=virtio-net-pci',
               '-fw_cfg', 'name=opt/org.controlstackai/smoke,string=1', '-no-reboot']
    if args.ventoy_disk:
        if not args.ventoy_disk.is_file():
            parser.error('Ventoy disk must be a regular image file; host block devices are forbidden')
        command.extend(['-drive', f'if=none,id=ventoy,format=raw,readonly=on,file={args.ventoy_disk.resolve()}',
                        '-device', 'qemu-xhci,id=xhci', '-device', 'usb-storage,drive=ventoy,bootindex=1'])
    else:
        command.extend(['-boot', 'd', '-cdrom', str(args.iso.resolve())])
    if os.access('/dev/kvm', os.R_OK | os.W_OK):
        command.extend(['-enable-kvm', '-cpu', 'host'])
    else:
        command.extend(['-accel', 'tcg', '-cpu', 'max'])
    if args.uefi_code:
        if not args.uefi_vars:
            parser.error('--uefi-vars required with --uefi-code')
        vars_copy = directory / 'OVMF_VARS.fd'
        vars_copy.write_bytes(args.uefi_vars.read_bytes())
        command.extend(['-drive', f'if=pflash,format=raw,readonly=on,file={args.uefi_code.resolve()}',
                        '-drive', f'if=pflash,format=raw,file={vars_copy}'])
    log.write_text('')
    started = time.monotonic()
    with (directory / (mode + '-qemu.log')).open('w') as stderr:
        process = subprocess.Popen(command, stderr=stderr)
        try:
            process.wait(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            raise RuntimeError(f'{mode} boot timed out; inspect {log}')
    output = log.read_text(errors='replace')
    lock = json.loads((ROOT / 'adapters/arch/inputs.lock.json').read_text())
    if args.distro == 'nixos':
        def evaluate(attr):
            return subprocess.check_output(['nix','eval','--extra-experimental-features','nix-command flakes',
                                            '--raw',str(ROOT)+'#nixosConfigurations.live.config.'+attr], text=True).strip()
        lock['arch']['kernel_release'] = evaluate('boot.kernelPackages.kernel.modDirVersion')
        lock['zfs']['version'] = evaluate('boot.zfs.package.version')
    passed = (process.returncode == 0 and 'AGENT_SMOKE_PASS' in output and 'AGENT_SMOKE_FAIL' not in output
              and all(marker in output for marker in ('AGENT_PREFLIGHT_PASS', 'AGENT_LAUNCHER_FIXTURES_PASS', 'AGENT_ZFS_SNAPSHOT_PASS'))
              and lock['arch']['kernel_release'] in output and 'codex-cli ' + lock['codex']['version'] in output
              and 'zfs-' + lock['zfs']['version'] in output)
    with args.iso.open('rb') as stream:
        iso_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
    receipt = {'iso_sha256': iso_hash, 'mode': mode, 'passed': passed, 'elapsed_seconds': round(time.monotonic() - started, 2),
               'disk_devices': ('File-backed read-only Ventoy USB only' if args.ventoy_disk else 'ISO CD-ROM only') + '; no host disks or target disks attached',
               'checks': ['ISO boot', 'kernel version', 'Codex version/login flags', 'NetworkManager active',
                          'RAM credential storage and cleanup (fixture authentication)', 'matching ZFS module loaded',
                          'real clock and HTTPS preflight', 'snapshot rollback', 'full and incremental ZFS send/receive',
                          'pool export/import and data hashes'],
               'not_tested': ['account login', 'model inference', 'physical installation', 'ZFS root reboot/recovery']}
    (directory / (mode + '-result.json')).write_text(json.dumps(receipt, indent=2) + '\n')
    print(output)
    if not passed:
        raise RuntimeError(f'{mode} smoke test failed; inspect {log}')


if __name__ == '__main__':
    main()
