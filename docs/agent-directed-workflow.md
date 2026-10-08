# Presets, custom choices and continuation

The assistant installs and repairs the system through conversation using native
distro tools. These additions support that work; they do not add a disk executor
or a graphical installer. A successful live-agent boot is not disk-installation
qualification.

## Beginner and advanced paths

Tell the assistant what you want to do and which files to keep. If you are unsure,
it can suggest a familiar desktop (Plasma), a simple desktop (GNOME), Hyprland
with Quickshell, or a minimal/server system. It explains the choices, asks one
question at a time and does the technical work locally. Presets do not pick a
disk, password, encryption decision, language or timezone for you.

Every preset is editable. You can change distribution, desktop, applications,
services, storage, kernel policy, key bindings, appearance and accessibility.
Advanced owners can describe a complete setup or provide custom JSON. Unlisted
choices are allowed, subject to real distro/package/hardware support. Custom
starts empty. Presets are suggestions and design specifications; this repository
does not ship prebuilt desktop sessions. In particular, the Hyprland preset tells
the agent to build three floating islands and a searchable Quickshell launcher
with icons rather than claiming that installing two packages provides that shell.

The agent normally runs these helpers for you:

```sh
agent-support presets
agent-support presets --preset hyprland
agent-support presets --preset familiar --overrides choices.json
agent-support inventory --output hardware.json
agent-support handoff new --preset custom --experience advanced --overrides choices.json --output plan.json
agent-support handoff review plan.json
```

Custom choices are JSON objects. Nested objects merge; lists and scalar values
replace the preset's values. Empty lists remove suggested applications. Additional
keys are accepted. For example:

```json
{
  "desktop": "sway",
  "filesystem": "btrfs",
  "applications": [],
  "appearance": {"scale": 1.5},
  "services": {"ssh": false}
}
```

Values are data for the agent to validate, not shell code. Credentials must stay
outside these files. ZFS and the newest released compatible kernel remain the
usual starting recommendation; explicit alternatives remain possible. The live
image's own readiness checks still validate its bundled ZFS module before login.

## Plan and hardware review

The read-only inventory collects disks/mounts, PCI driver information, network
links/radio blocks, memory, available space and ZFS metadata. Missing commands
are reported. It does not prove working firmware, graphics, Wi-Fi or audio. The
agent investigates and tests those paths before installation as appropriate.

The structured review identifies target disks, erasure, preservation, planned
steps, chosen options and a recovery path. Edits require a new review. A validated
file is not permission to erase; current explicit owner approval and current
device verification are required. There is no helper command that executes a plan.

## Reboot handoff

The assistant records choices, completed and remaining steps, checks and sanitized
notes in a schema-1 JSON record. After you review the exact contents and approve
a destination, it can save that one file:

```sh
agent-support handoff check plan.json
agent-support handoff export plan.json /approved/location/install-handoff.json --reviewed
```

The destination must be new. The tool refuses overwrites, symlinks, oversized or
special files, unexpected top-level fields and common secret patterns. It uses
0600 permissions where supported. This is not encryption; FAT/exFAT permissions
may not protect the file. Free text can hide secrets the checks cannot recognize,
so review matters. No runtime profile, credential directory or transcript is copied.
The review flag covers saving this record, not disk erasure.

On a subsequent live boot or an installed system where the support tools and an
agent have been arranged explicitly:

```sh
agent-support handoff import /approved/location/install-handoff.json /private/work/handoff.json
agent-support verify --handoff /private/work/handoff.json --online
```

Create the private work directory first; use the live session's existing
`/run/agent-installer/work/` when appropriate. Import validates one JSON document,
keeps it as untrusted data and resets old check results to pending. Device paths,
claimed completed steps and historical approvals cannot authorize new actions.
The assistant confirms your intended continuation and inspects the current machine.

Saving the file does **not** install a resident agent, restore credentials, launch
a service or resume a conversation automatically. Include any desired installed
support tools/agent in the reviewed installation plan and sign in afresh. On
NixOS the public core package can be installed without enabling the live-onboarding
module. On Arch the agent can package the public core and support data using
native packaging. Persistent OpenClaw lifecycle remains a separate project.

## Verification and recovery

Verification collects fresh read-only boot evidence and optional public HTTPS
reachability. It distinguishes live/chroot sessions from a disk-root candidate,
compares boot IDs when available, checks ZFS module metadata and imported-pool
health, and lists pending hardware, media-removal and recovery checks. It always
reports `needs-review`; a changed boot ID or healthy unrelated pool is insufficient.
Internet reachability is not successful model access.

Recovery uses the same assistant with `--intent recover` in its record. It starts
read-only and proposes explicit steps for boot repair, file recovery or snapshot
restoration. Pool imports, write mounts, rollback and boot-file changes require
a reviewed plan and current permission. No recovery operations run automatically.

See [verification](verification.md) for exact tested boundaries, and
[the automatically loaded agent workflow](../identity/WORKFLOW.md) for the full
instructions. To use helpers directly from a source checkout, replace
`agent-support` with `python3 -m core.assistant --share .`.
