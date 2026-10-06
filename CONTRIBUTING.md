# Contributing

Read AGENTS.md and docs/architecture.md. Keep beginner-facing text understandable
and ask for choices, not copied terminal reports. Make adapters explicit and
state exactly which boot and installation paths were tested.

Run `python3 scripts/check.py`. Evaluate NixOS changes and boot changed images in
isolated VMs. VM target devices must be regular-file images. Never use host disks.
Describe actual input digests and tested image hashes in verification receipts.
Do not submit credentials, owner-specific host configuration or private agent
state. Keep caches and artifacts ignored.

For an Arch input update, run `adapters/arch/scripts/inputs.py` explicitly using
its documented options, review the dated snapshot/kernel/ZFS/signatures, and
update `runtimes/codex/inputs.lock.json` consistently if Codex changes. Validation
rejects mismatched Codex pins. Update the Nixpkgs flake lock explicitly and review
ZFS/kernel compatibility before rebuilding. Input updates require fresh boots;
old receipts never qualify different bytes.
