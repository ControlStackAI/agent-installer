#!/usr/bin/env python3
"""Dispatch an explicit distribution; building never silently updates pins."""
import argparse
import subprocess
import sys
import hashlib
import json
import os
import shutil
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--distro', choices=['arch', 'nixos'], required=True)
parser.add_argument('--jobs', type=int, default=2)
args, rest = parser.parse_known_args()
if args.jobs < 1: parser.error('--jobs must be positive')
if args.distro == 'arch':
    command = [sys.executable, str(ROOT/'adapters/arch/scripts/build.py'), '--jobs', str(args.jobs), *rest]
else:
    if rest: parser.error('Extra options apply only to the Arch adapter')
    command = ['nix', 'build', '--extra-experimental-features', 'nix-command flakes',
               '--max-jobs', str(args.jobs), '--cores', str(args.jobs),
               '--no-write-lock-file', '--out-link', str(ROOT/'.build/nixos'), str(ROOT)+'#nixos-iso']
    (ROOT/'.build').mkdir(exist_ok=True)
subprocess.run(command, check=True, cwd=ROOT)

# Give both adapters the same artifact layout for release tooling.
output = ROOT/'dist'/args.distro
output.mkdir(parents=True, exist_ok=True)
source = ROOT/'adapters/arch/dist' if args.distro == 'arch' else ROOT/'.build/nixos/iso'
for path in source.iterdir():
    if path.is_file():
        destination = output/path.name
        if destination.exists(): destination.unlink()
        try: os.link(path, destination)
        except OSError: shutil.copy2(path, destination)
if args.distro == 'nixos':
    shutil.copy2(ROOT/'flake.lock', output/'flake.lock')
    shutil.copy2(ROOT/'runtimes/codex/inputs.lock.json', output/'codex-inputs.lock.json')
    with (output/'SHA256SUMS').open('w') as sums:
        for path in output.glob('*.iso'):
            with path.open('rb') as stream: digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            sums.write(digest+'  '+path.name+'\n')
