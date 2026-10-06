# Agent Installer

[Public source: ControlStackAI/agent-installer](https://github.com/ControlStackAI/agent-installer)

A local assistant to help people install or recover Linux without needing to
learn terminal commands first. Boot a supported live image, connect to the
internet, sign in, and talk to the assistant running on that computer.

**Development status:** these are agent-assisted live environments. A qualified
physical-disk installation executor is not included. Build and boot evidence
must identify the exact image; live-agent success does not qualify disk erasure,
a finished installation or migration. Arch and NixOS adapters share the same
onboarding and identity. Hardware support still needs broader testing.

## What belongs where

```
core/               shared onboarding, readiness and environment detection
identity/           friendly local installer role and data-preservation guidance
profiles/           distro facts, capability declarations and agent instructions
runtimes/codex/      Codex login, launch and independently pinned upstream bundle
adapters/arch/      signed Arch ISO remaster, dated packages and matching ZFS
adapters/nixos/     reusable NixOS module and reproducible live-image configuration
scripts/           common validation and explicit build dispatch
tests/             readiness, authentication and identity contract tests
docs/              extension contract, qualification and contributor guidance
```

The distribution describes system installation, packages and boot; the agent
runtime describes sign-in and conversation. Keep these independent. A resident
OpenClaw operating-system agent is a separate project, with its own persistent
state and lifecycle. This project prepares the live installation environment.

## Using a live image

The guided setup opens on the first local console. It detects an existing
connection or offers Wi-Fi setup, then checks internet, time and ZFS readiness.
Sign-in stays behind these checks. ChatGPT subscription device-code login lets
you sign in on a phone or another computer. Browser login and hidden API-key
input are also available; API billing is separate. Successful sign-in starts
the local assistant in the same flow. A troubleshooting shell remains available.

Credentials and session notes stay in private RAM storage. They disappear at
reboot. The assistant asks before saving non-secret continuation notes elsewhere
and must present a concrete disk plan before requesting erasure approval.

## Building and checking

Requirements: Python 3.11+; Docker for Arch; Nix with flakes for NixOS. Both
current image builders target x86_64 Linux. Reviewed inputs are pinned: building
never silently resolves a new runtime, image or package snapshot.

```sh
git clone https://github.com/ControlStackAI/agent-installer.git
cd agent-installer
python3 scripts/check.py
python3 scripts/build.py --distro arch --jobs 2
python3 scripts/build.py --distro nixos --jobs 2
```

Both adapters write artifacts under `dist/<distro>/`. Adapter staging remains
under `adapters/arch/.build/` or `.build/nixos/`. Only listed public sources and disposable artifact caches
are mounted into the Arch build container. No operator home, credentials or
host block devices are exposed. Upstream signatures and checksums are required.

The NixOS module can be imported into another custom live-image flake. A NixOS
image uses NixOS's native module and ISO builder; Arch remaster commands are not
run on NixOS. See [architecture](docs/architecture.md) and [verification](docs/verification.md).

## Contributing and licensing

See [CONTRIBUTING.md](CONTRIBUTING.md). The project's source is Apache-2.0;
third-party packages and image contents retain their own licenses. This project
is independent of OpenAI, Arch Linux, NixOS and OpenClaw and does not imply their
endorsement. See [third-party provenance](docs/third-party.md).
