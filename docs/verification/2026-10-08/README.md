# Image receipts, 2026-10-08

Source: [`9d8bcd3ef090bae17018d747fa57f8bf9f14d0b8`](https://github.com/ControlStackAI/agent-installer/commit/9d8bcd3ef090bae17018d747fa57f8bf9f14d0b8).
These files are unmodified receipts extracted from the successful hosted builds.
Every receipt's `iso_sha256` matches its adjacent `SHA256SUMS`.

| Distribution | BIOS | UEFI | Ordinary offline console | Image artifact |
| --- | --- | --- | --- | --- |
| Arch | [Receipt](arch/bios-result.json) | [Receipt](arch/uefi-result.json) | [Receipt](arch/offline-console-result.json) | [Download](https://github.com/ControlStackAI/agent-installer/actions/runs/37827953315/artifacts/11572028879) |
| NixOS | [Receipt](nixos/bios-result.json) | [Receipt](nixos/uefi-result.json) | [Receipt](nixos/offline-console-result.json) | [Download](https://github.com/ControlStackAI/agent-installer/actions/runs/37827958787/artifacts/11573385102) |

The ZIP downloads also contain the ISO, console screenshots, and logs. GitHub
requires sign-in; artifacts expire after 14 days. Keeping these receipts does
not extend that retention or qualify different image bytes.

The ordinary console test boots with networking disabled and no smoke flag. It
exercises both interface paths and prevents offline sign-in. The BIOS and UEFI
smoke tests separately exercise real HTTPS/clock checks and file-backed ZFS
operations. Authentication lifecycle fixtures do not prove an owner account
login or model response. None of these tests attaches a host/target disk or
installs the operating system. See [verification boundaries](../../verification.md).
