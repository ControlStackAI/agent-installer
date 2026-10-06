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
