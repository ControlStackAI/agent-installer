# Guided terminal interface

The live ISO opens a Ratatui welcome screen on its first console. Choose
**Guided setup** for a dashboard, or **Direct agent conversation** to describe
what you want immediately. Both use the same local assistant, native sign-in
and shared readiness checks. An internet connection, synchronized clock and
matching live ZFS module are required before authentication or agent launch.

Guided setup provides desktop presets, unrestricted custom choices, a read-only
hardware report, installation review, non-secret reboot handoffs, recovery
intent and verification evidence. Presets are starting points rather than a
fixed menu of supported configurations. Ask the assistant to customize anything.
Advanced users can edit the complete JSON record in a terminal editor.

The interface never executes a disk plan. The local agent still explains,
performs authorized installation work and verifies it using native distro tools.
Selecting a preset or reading the plan records no permission to erase disks.
Recovery begins with inspection; selecting it runs no repair or pool import.

## Controls

- **Enter** continues or performs the current page's stated action.
- **Tab / Left / Right**, or **1–8**, changes dashboard pages.
- **Up / Down** selects a preset or scrolls; **Page Up / Page Down** scrolls further.
- **A** opens the local assistant; **N** opens network setup; **R** checks readiness.
- **E** opens the complete non-secret record in your editor (advanced).
- On **Reboot handoff**, **I** imports and **S** saves the reviewed JSON record.
- **F1 / ?** opens help; **Esc** returns to the welcome screen; **Q** leaves setup.

Network setup, editing and agent sign-in/conversation temporarily use the full
terminal. On exit, the dashboard returns. Secrets use native hidden-input/login
flows and are never entered into a TUI path or configuration field. Device-code
login remains convenient for a phone or another computer.

Export shows the destination and requires an explicit save confirmation, with
cancellation as the default. The current record must match the preview's content
fingerprint. Export copies only that validated snapshot. Existing files are never
overwritten. Imported historical verification is marked pending; notes never
become instructions or permission to erase. A saved handoff does not install a
resident agent or restore credentials after reboot.

## Text fallback and preview

Use `agent-installer --direct` to skip the dashboard, or `agent-installer --text`
for the original basic console. Non-interactive/dumb terminals use the text path.
A TUI startup failure also falls back to that path. Other live consoles remain
available for troubleshooting.

`agent-installer-tui --preview` explores the interface without running system
actions. `agent-installer-tui --render 100 32` renders a deterministic example;
`--screen presets` previews the preset page. These examples are explicitly
marked design previews and do not inspect or modify the host.

## Building

Rust sources are under `frontends/ratatui/`. Ratatui and Crossterm versions plus
all transitive crate checksums are recorded in Cargo.lock. Nix builds and tests
the frontend as `.#installer-tui`; the core package wraps it with its Python
bridge. Arch builds it with the dated builder's Rust compiler using `--locked`
and isolated Cargo staging. Both images carry upstream dependency notices.

```sh
CARGO_TARGET_DIR="$PWD/.build/tui-target" cargo test --locked --manifest-path frontends/ratatui/Cargo.toml
nix build .#installer-tui .#installer-core
```

The Rust UI invokes the fixed shared JSON bridge rather than shell-interpolating
paths or reimplementing storage/readiness/authentication logic. Native tools are
only available in a confirmed live, root, RAM-backed session; preview mode never
invokes them. UI/render and fixture tests complement actual ISO boots and console
interaction checks; they do not qualify physical disk installation or a real
account/model response. See [verification](verification.md).
