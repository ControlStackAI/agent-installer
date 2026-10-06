#!/usr/bin/env python3
"""Shared live onboarding. No partitioning or disk executor is shipped here."""
import argparse
import getpass
import json
import os
import re
import subprocess
import shutil
from pathlib import Path
from core.checks import Readiness
from core.environment import discover
from core.runtime import load_runtime

SHARE = Path('/usr/share/agent-installer')
SESSION = Path('/run/agent-installer')


def read_profile(share, name):
    if not re.fullmatch(r'[a-z][a-z0-9-]*', name) or not (share / 'profiles' / (name + '.json')).is_file():
        raise ValueError('This image does not include an adapter for that distribution.')
    profile = json.loads((share / 'profiles' / (name + '.json')).read_text())
    if profile.get('schema') != 1 or profile.get('id') != name:
        raise ValueError('Unsupported distro profile schema or identity.')
    return profile


def identity(share, profile, facts):
    return ((share / 'identity/AGENTS.md').read_text() + '\n\n' +
            (share / 'profiles' / (profile['id'] + '.md')).read_text() +
            '\n\n## Current session facts\n\n```json\n' +
            json.dumps({'observed': facts, 'default_target': profile['id'],
                        'adapter_capabilities': profile['capabilities']}, indent=2) +
            '\n```\nRecheck these facts after changing roots, devices, or rebooting.\n')


class Wizard:
    def __init__(self, checks, runtime, choose=input, key=getpass.getpass, shell=None):
        self.checks, self.runtime, self.choose, self.key = checks, runtime, choose, key
        self.shell = shell or (lambda: subprocess.run([shutil.which('bash') or '/bin/sh', '-l']))

    def next_input(self, prompt):
        try:
            return self.choose(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            return '0'

    def connection(self):
        while True:
            print('\nStep 1: Connect to the internet. Checking Ethernet or an existing Wi-Fi connection…', flush=True)
            if self.checks.ready():
                return True
            print('1) Set up Wi-Fi or another connection\n2) Retry checks\n9) Troubleshooting shell\n0) Leave setup')
            choice = self.next_input('Choose: ')
            if choice == '1':
                self.checks.connect()
            elif choice == '9':
                self.shell()
            elif choice == '0':
                return False

    def run(self):
        print('\nWelcome to the ControlStackAI Installer.\n'
              'Your local assistant can help you install Linux or recover this computer.\n'
              'You do not need to know Linux commands. It will ask before erasing data.\n'
              'This development image has no qualified disk installation executor yet.\n'
              'Sign-in and session notes stay in memory and disappear when you reboot.', flush=True)
        while self.connection():
            if self.runtime.authenticated():
                # Recheck immediately before a new agent session, including after a disconnect.
                if self.checks.ready():
                    self.runtime.start()
            else:
                print('\nStep 2: Sign in.\n1) ChatGPT subscription: sign in on your phone or another computer (recommended)\n'
                      '2) ChatGPT subscription: browser sign-in\n3) OpenAI API key (API billing is separate)\n'
                      '9) Troubleshooting shell\n0) Leave setup')
                choice = self.next_input('Choose: ')
                if choice == '0':
                    return
                if choice == '9':
                    self.shell()
                    continue
                method = {'1': 'device', '2': 'browser', '3': 'key'}.get(choice)
                if method is None:
                    continue
                # The connection can disappear while the person is choosing.
                if not self.checks.ready():
                    continue
                secret = None
                if method == 'key':
                    try:
                        secret = self.key('API key (input hidden): ')
                    except (EOFError, KeyboardInterrupt):
                        continue
                    if not secret:
                        continue
                try:
                    signed_in = self.runtime.login(method, secret)
                finally:
                    secret = None
                if not signed_in:
                    print('Sign-in did not finish. You can retry or choose another method.')
                    continue
                if not self.checks.ready():
                    continue
                print('\nStep 3: Starting your local assistant.', flush=True)
                self.runtime.start()
            print('\n1) Return to the assistant\n2) Forget sign-in and choose an account\n'
                  '9) Troubleshooting shell\n0) Leave setup')
            choice = self.next_input('Choose: ')
            if choice == '0':
                return
            if choice == '2':
                self.runtime.forget()
                continue
            if choice == '9':
                self.shell()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--facts', action='store_true', help='Print non-secret runtime facts')
    parser.add_argument('--preflight', action='store_true', help='Check readiness without signing in')
    parser.add_argument('--network', action='store_true', help='Open connection setup')
    args = parser.parse_args()
    facts = discover()
    if args.facts:
        print(json.dumps(facts, indent=2))
        return 0
    if facts['uid'] != 0 or facts['phase'] != 'live':
        print('Open this assistant from a supported live USB image. This session is not a confirmed live boot.')
        return 1
    image = json.loads(Path('/etc/agent-installer/image.json').read_text())
    profile = read_profile(SHARE, image['distro'])
    if facts['distro_id'] not in profile['os_ids']:
        raise ValueError('The running distribution does not match this image profile.')
    manifest = json.loads((SHARE / "runtimes" / (image["runtime"] + ".json")).read_text())
    if manifest.get("id") != image["runtime"] or manifest.get("schema") != 1:
        raise ValueError("Unsupported runtime manifest")
    checks = Readiness(profile, auth_endpoints=manifest["authentication_endpoints"])
    if args.network:
        return checks.connect()
    if args.preflight:
        return 0 if checks.ready() else 1
    # Never allow authentication state to silently land on a persistent /run.
    mount = subprocess.run(['findmnt', '-n', '-o', 'FSTYPE', '/run'], capture_output=True, text=True)
    if mount.returncode or mount.stdout.strip() != 'tmpfs':
        raise ValueError('The live session requires /run to be memory-backed.')
    os.umask(0o077)
    runtime = load_runtime(image['runtime'], session=SESSION, identity=identity(SHARE, profile, facts))
    Wizard(checks, runtime).run()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
