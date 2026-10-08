#!/usr/bin/env python3
"""Preserve notices from checked public Cargo sources, never an operator profile."""
import argparse
import shutil
import tomllib
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--lock', type=Path, required=True)
parser.add_argument('--sources', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
locked = {(p['name'], p['version']) for p in tomllib.loads(args.lock.read_text())['package'] if 'source' in p}
# Nix vendor trees and isolated Cargo registry trees use one or two directory levels.
roots = [args.sources, *args.sources.glob('*'), *args.sources.glob('*/*')]
args.output.mkdir(parents=True, exist_ok=True)
lines = ['Third-party Rust crates used by the TUI build', 'Source versions and registry checksums: Cargo.lock', '']
seen = set()
for root in roots:
    manifest = root / 'Cargo.toml'
    if not manifest.is_file():
        continue
    package = tomllib.loads(manifest.read_text()).get('package', {})
    identity = (package.get('name'), package.get('version'))
    if identity not in locked or identity in seen:
        continue
    seen.add(identity)
    label = '-'.join(identity)
    lines.append(f"{label}: {package.get('license', 'See upstream license files')}")
    for path in root.rglob('*'):
        if path.is_file() and path.name.upper().startswith(('LICENSE', 'LICENCE', 'COPYING', 'NOTICE')):
            destination = args.output / label / path.relative_to(root)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
if not seen:
    raise SystemExit('No verified Cargo crate sources found for license preservation')
(args.output / 'INDEX.txt').write_text('\n'.join(lines) + '\n')
shutil.copyfile(args.lock, args.output / 'Cargo.lock')
print(f'Preserved upstream notices for {len(seen)} public Rust crate versions.')
