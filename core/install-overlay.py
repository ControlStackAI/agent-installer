#!/usr/bin/env python3
"""Install shared public files into a disposable extracted image, never host /."""
import argparse
import json
import shutil
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('root', type=Path)
parser.add_argument('source', type=Path)
parser.add_argument('--distro', choices=['arch'], required=True)
args = parser.parse_args()
root, source = args.root.resolve(), args.source.resolve()
if root == Path('/') or not (root / 'etc/os-release').is_file():
    parser.error('Supply a disposable extracted image root, never the running host root')
lib = root / 'usr/lib/agent-installer'
share = root / 'usr/share/agent-installer'
for folder in ['core', 'runtimes']:
    shutil.copytree(source / folder, lib / folder, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__', '*.nix', '*.json'))
for folder in ['identity', 'profiles', 'tests']:
    shutil.copytree(source / folder, share / folder, dirs_exist_ok=True)
(share / 'runtimes').mkdir(parents=True, exist_ok=True)
shutil.copy2(source / 'runtimes/codex/manifest.json', share / 'runtimes/codex.json')
conf = root / 'etc/agent-installer'
conf.mkdir(parents=True, exist_ok=True)
(conf / 'image.json').write_text(json.dumps({'schema':1, 'distro':args.distro, 'runtime':'codex'})+'\n')
(conf / 'live-image').write_text(args.distro+'\n')
for name, flags in [('agent-installer',''),('agent-preflight','--preflight'),('agent-network','--network')]:
    script = root / 'usr/local/bin' / name
    script.write_text('#!/bin/sh\nPYTHONPATH=/usr/lib/agent-installer exec python3 -m core.launcher '+flags+' "$@"\n')
    script.chmod(0o755)
# Stock Arch's root login shell is zsh. Other login shells are also supported.
hook = (source / 'core/live-login.sh').read_text()
for name in ['.zlogin', '.bash_profile']:
    path = root / 'root' / name
    with path.open('a') as output:
        output.write('\n'+hook)
(root / 'etc/motd').write_text('ControlStackAI Installer\nThe guided assistant opens automatically on the first console.\nRun agent-installer to reopen it; other consoles remain available for troubleshooting.\n')
