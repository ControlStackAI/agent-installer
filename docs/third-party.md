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
- NixOS/Nixpkgs: https://github.com/NixOS/nixpkgs ; public pinned revision and
  NAR hash in flake.lock. The NixOS module system builds the ISO and tracks the
  package closure; package licenses remain their upstream licenses.

Published source licensing does not replace redistribution requirements for a
release's third-party packages. Preserve upstream license files and provenance.
No packages are implicitly updated at build time.
