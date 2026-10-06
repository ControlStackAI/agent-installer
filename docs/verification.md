# Verification boundaries

Shared tests cover offline gating, disconnects before/after login, all three
Codex sign-in routes, private profile permissions, stdin key transport, unknown
runtime/distro rejection and live/chroot/installed distinctions. Arch input tests
preserve signature pins, digests and exact released kernel/ZFS compatibility.

`python3 scripts/vm.py IMAGE.iso --distro arch` (or `nixos`) boots an actual image
in QEMU with an explicit smoke flag. No host or target disks are attached. The
flag enables guest checks for actual Codex login flags, NetworkManager, RAM
storage, HTTPS/NTP readiness, shared fixture tests and real ZFS snapshot rollback,
full/incremental send/receive and export/import on guest-only file-backed vdevs.

An ordinary console boot must separately verify that onboarding opens without
requesting a smoke flag. Firmware and USB boot modes require distinct receipts;
no receipt can be transferred to changed image bytes. Owner account login and a
real model response require a separate actual-user test. A fixture never proves
a working subscription, API account or model access.

No image here yet qualifies physical-disk installation, root-on-ZFS boot,
migration or recovery. Those require a guarded executor, disposable target-disk
VM installation tests, removed-media reboots, rollback/recovery tests and then
explicitly approved hardware qualification. See capability declarations in
profiles/*.json. Tests and build success do not change these declarations.

## Recorded development checks, 2026-10-06

- Shared core plus Arch input policy: 30 unit tests passed. [Hosted source/package
  checks](https://github.com/ControlStackAI/agent-installer/actions/runs/37498249410)
  also evaluated the NixOS ISO and built the actual Codex/core packages.
- Refreshed Arch live image: kernel 7.2.8-arch1-2, ZFS 2.4.4, Codex 0.160.1;
  SHA256 `5d8fb366ed35b21b2dfd4d41965f924707c0d5ea7479cc05c510eac5bda0c55a`.
  Local BIOS/UEFI functional checks passed, as did the ordinary console boot
  with networking disabled: onboarding opened automatically and did not offer
  sign-in. Keyboard access to troubleshooting and actual Codex startup worked.
- NixOS live image: Linux 7.2.9, ZFS 2.4.4, Codex 0.160.1. [Hosted build and both
  BIOS/UEFI functional boots](https://github.com/ControlStackAI/agent-installer/actions/runs/37497970407)
  passed at source 51b7dc1. The first run exposed an Arch-specific diagnostic
  Python path; that path was fixed before this passing run. The ISO and its
  exact-hash receipts are in that run's `agent-nixos-2` artifact. A separate
  ordinary local NixOS console check has not been recorded; fetching the large
  artifact to the development host was too slow.

These checks did not use an owner account or install a target disk. Earlier
hardware subscription-login success belongs to the original Arch prototype,
not these changed image bytes. The development host had no attached USB during
this iteration, so the existing Ventoy disk was not updated.
