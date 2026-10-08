# Third-party provenance

The repository contains original integration source, public package metadata
and public signing keys. It does not vendor credentials or a private host flake.

- Codex official musl bundle: https://github.com/openai/codex ; independently
  pinned URL/SHA256 in runtimes/codex/inputs.lock.json; upstream Apache-2.0.
  Keep bundled dependency notices when distributing the full bundle.
- Arch ISO/packages: https://archlinux.org ; dated snapshot, digests, detached
  signatures and reviewed signer fingerprints in adapters/arch/inputs.lock.json.
  Package inventory is included with built images; each package has its own license.
- ArchZFS: https://github.com/archzfs/archzfs ; pinned released package bytes and
  signatures. OpenZFS is https://github.com/openzfs/zfs under its upstream terms,
  including CDDL. Do not describe all ISO contents as Apache-2.0.
  The rolling upstream release pruned the Linux 7.2.8 module. Explicit mirrors
  in the input lock point to our [preserved signed build inputs](https://github.com/ControlStackAI/agent-installer/releases/tag/build-inputs-2026-10-05).
  These keep the original package/signature digests and signer, with provenance
  and upstream source links. A mirror never selects another version or weakens
  verification. Declared preserved archives take precedence because upstream
  also replaces same-name assets. The archive is separate from live-image releases.
- NixOS/Nixpkgs: https://github.com/NixOS/nixpkgs ; public pinned revision and
  NAR hash in flake.lock. The NixOS module system builds the ISO and tracks the
  package closure; package licenses remain their upstream licenses.
- Ratatui: https://ratatui.rs and https://github.com/ratatui/ratatui ; upstream
  MIT. Crossterm and transitive Rust crates retain their own licenses. Exact
  versions/checksums are in frontends/ratatui/Cargo.lock. Image builds preserve
  upstream license/notice files under share/agent-installer/tui-notices.

Published source licensing does not replace redistribution requirements for a
release's third-party packages. Preserve upstream license files and provenance.
No packages are implicitly updated at build time.
