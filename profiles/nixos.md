## NixOS adapter

This image defaults to NixOS, the Linux distribution built using Nix. Nix itself
can also be installed on other distributions; it does not make them NixOS.
Explain declarative configuration in plain language: the system configuration
records the desired setup so it can be rebuilt and earlier generations selected.

Use nixos-generate-config, reviewed configuration.nix or a flake, nixos-install
and nixos-enter for approved manual work. Build and validate the target system
before erasing disks. Keep hardware discovery separate from shared configuration.
Generate a unique hostId for the installed ZFS host. Select the newest explicitly reviewed supported kernel from the pinned Nixpkgs
snapshot. The deprecated latestCompatibleLinuxPackages alias can return an LTS
kernel, so do not assume it selects the newest supported release. Never override
a failed ZFS compatibility check.
NixOS generation rollback and ZFS dataset rollback serve different purposes;
verify both separately, including the bootloader and installed root imports.
The included module builds this live image; it is not a target disk installer.
Physical disk installation remains unqualified.
