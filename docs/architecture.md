# Architecture and adapter contract

The shared core owns a continuous local-console flow: network readiness, clock
readiness, authentication, agent session and retry/troubleshooting. It knows no
Arch pacman or NixOS installation commands. The runtime owns login, private
session state, instruction loading, start and logout. A manifest supplies that
runtime's connectivity endpoints. Codex is integrated; other live runtimes need
an explicit implementation of `AgentRuntime`, manifest and tests.

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

Codex receives the common role, selected profile and observed facts as a global
AGENTS.md inside its private live CODEX_HOME. It is instructions, not an enforced
disk policy. The work directory holds non-secret plans, not a credential handoff.
See [Codex instruction discovery](https://learn.chatgpt.com/docs/agent-configuration/agents-md).

Future storage execution should use explicit plans bound to actual disk
identities and guarded executors, with payload validation before erasure and a
real installed-system reboot test. Persistent OpenClaw services, authentication,
memory, backups and system permissions are developed in a separate repository.
Only sanitized installation records should cross that boundary.
