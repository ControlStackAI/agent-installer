# Architecture and adapter contract

Canonical repository: https://github.com/ControlStackAI/agent-installer .
The earlier private arch-agent-installer repository is a historical prototype.

The shared core owns a continuous local-console flow: network readiness, clock
readiness, authentication, agent session and retry/troubleshooting. It knows no
Arch pacman or NixOS installation commands. The runtime owns login, private
session state, instruction loading, start and logout. A manifest supplies that
runtime's connectivity endpoints. Codex is integrated; other live runtimes need
an explicit implementation of `AgentRuntime`, manifest and tests.

`frontends/ratatui/` supplies the optional terminal welcome and guided dashboard.
It calls the fixed JSON interface in `core.frontend` for shared presets, local
records, read-only reports and readiness checks. It suspends terminal rendering
for native networking, editing, authentication and conversation, then resumes
the same dashboard. Direct conversation and the basic text fallback use the
same core flow. No frontend duplicates a runtime or distro installer. See
[terminal interface](terminal-interface.md) for controls and preview mode.

A distribution adapter contains its native image builder and package policy.
It installs the core, runtime, profiles and common identity, then writes
`/etc/agent-installer/image.json` with schema, distro and runtime. Live images
also include `/etc/agent-installer/live-image`; the reusable NixOS tools module
alone does not mark a system as a live image.

Profiles use schema 1 and contain `id`, `name`, `os_ids`, default filesystem,
package endpoints and capability declarations. Pair each JSON profile with a
Markdown installation guide. To add a distro, add its profile, native builder,
package policy and verification matrix; shared authentication stays unchanged.
Unknown distro/runtime/context fails explicitly. Profiles currently report
`physical_disk_executor: false`; do not change it because an ISO boots.

Runtime facts come from os-release, current root filesystem, privilege and
chroot detection. The image's default target is recorded separately. The agent
can discuss another target but must inspect required native tools and research
the official installation process. A chroot never proves an installed disk boot.

Codex receives the common role, agent-directed workflow, selected profile and observed facts as a global
AGENTS.md inside its private live CODEX_HOME. It is instructions, not an enforced
disk policy. The work directory holds non-secret plans, not a credential handoff.
See [Codex instruction discovery](https://learn.chatgpt.com/docs/agent-configuration/agents-md).

Future storage execution should use explicit plans bound to actual disk
identities and guarded executors, with payload validation before erasure and a
real installed-system reboot test. Persistent OpenClaw services, authentication,
memory, backups and system permissions are developed in a separate repository.
Only sanitized installation records should cross that boundary.

`presets/desktop.json` supplies editable starting choices. Custom values are
JSON data; objects merge recursively and lists replace. No desktop allowlist
restricts advanced choices. Presets do not pick disks or account credentials and
do not claim an implemented/qualified desktop session.

`core.assistant` provides the `agent-support` CLI: inventory, presets, structured
review, explicit handoff export/import and read-only verification evidence.
Handoffs contain one bounded schema-1 JSON record, not runtime state. Import
resets old verification results and never evaluates code or writes agent
instructions. Its source is untrusted; approval is never transferable. Secret
pattern rejection supplements, but cannot replace, review of free text before
an owner-approved persistent save. Verification always returns needs-review;
media removal, functional hardware and recovery need separate testing. See
[the workflow](agent-directed-workflow.md).
