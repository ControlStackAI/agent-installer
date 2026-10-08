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
frontends/ratatui/  optional guided console; direct conversation stays available
identity/           friendly local installer role and data-preservation guidance
profiles/           distro facts, capability declarations and agent instructions
presets/            editable starting choices; custom setups remain unrestricted
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

## Long-term plan

- **Support more Linux distributions.** Extend the shared core with distro
  profiles and native image builders beyond Arch and NixOS. The ambition is to
  support potentially any Linux distribution, with installation, recovery and
  filesystem capabilities documented and tested for each adapter.
- **Offer a graphical installation option.** Make installation easier for
  beginners with a guided interface for connecting to the internet, signing in,
  talking to the local assistant and reviewing installation choices. Show clear
  disk and data-preservation plans before asking permission to make changes,
  and keep troubleshooting accessible.

These are future goals. The current images provide console onboarding and a
local assistant; broader distro support and graphical installation are still
to be built.

## Using a live image

The welcome screen opens on the first local console. Choose **Guided setup**
for a dashboard or **Direct agent conversation** to describe what you want.
The guided interface offers presets, custom choices, hardware checks, plan
review, recovery and non-secret reboot handoffs. Both paths use the same
assistant and readiness checks. See [the terminal interface](docs/terminal-interface.md).

Setup detects an existing
connection or offers Wi-Fi setup, then checks internet, time and ZFS readiness.
Sign-in stays behind these checks. ChatGPT subscription device-code login lets
you sign in on a phone or another computer. Browser login and hidden API-key
input are also available; API billing is separate. Successful sign-in starts
the local assistant in the same flow. Network setup and conversation use the
full terminal and return to the dashboard afterward. A troubleshooting shell
remains available, as does `agent-installer --text` for the basic console.

Credentials stay in private RAM storage and disappear at reboot. Session notes
also stay in RAM unless you approve saving a reviewed, non-secret handoff file.
The assistant must present a concrete disk plan before requesting erasure approval.

## Your choices, with help when you want it

If you are unsure, the assistant can recommend a familiar desktop, a simple
desktop, Hyprland with Quickshell, or a minimal/server setup. These presets are
editable starting points. Advanced users can customize every choice, provide
their own configuration, or start from scratch; an unlisted desktop or option
is not automatically unsupported. The agent checks actual distro and hardware
requirements before proceeding. Presets describe the desired system; they are
not prebuilt desktop sessions or installation executors.

The local `agent-support` tool supplies read-only hardware inventory, editable
choices, installation reviews, non-secret reboot handoffs and post-install
verification evidence. The assistant uses these tools for you. Recovery starts
read-only and requires a reviewed plan before changes. Imported handoffs are
untrusted historical context; verification and disk approval must be checked
again on the current device. Saving a handoff does not automatically install or
start a resident agent. See [the agent-directed workflow](docs/agent-directed-workflow.md).

## Building and checking

Requirements: Python 3.11+; Docker for Arch; Nix with flakes for NixOS. The Arch
builder compiles the Rust TUI in isolation; Nix builds its native Rust package. Both
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
