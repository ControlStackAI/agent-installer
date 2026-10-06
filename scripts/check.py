#!/usr/bin/env python3
"""Validate shared contracts, Arch signed input policy, tests and shell syntax."""
import json
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
shared = json.loads((ROOT/'runtimes/codex/inputs.lock.json').read_text())
arch = json.loads((ROOT/'adapters/arch/inputs.lock.json').read_text())
if {k:v for k,v in shared.items() if k != 'schema'} != arch['codex']:
    raise ValueError('Arch and shared Codex pins differ; review and update both locks')
for path in ROOT.rglob('*.sh'):
    if '.build' not in path.parts:
        subprocess.run(['bash','-n',str(path)],check=True)
for path in (ROOT/'adapters/arch/live/usr/local/bin').iterdir():
    subprocess.run(['bash','-n',str(path)],check=True)
subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=ROOT,check=True)
subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=ROOT/'adapters/arch',check=True)
subprocess.run([sys.executable,'scripts/inputs.py','--check'],cwd=ROOT/'adapters/arch',check=True)
