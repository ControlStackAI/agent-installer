# Contributor instructions

Keep distro-independent behavior in core/, agent authentication and launch in
runtimes/, distro facts/instructions in profiles/, and image-specific building
in adapters/. This repository provides live installer environments; the resident
OpenClaw OS agent belongs in a separate repository. Do not quietly add it here.

Run python3 scripts/check.py and evaluate affected NixOS configurations. Builds
are pinned; never update inputs as a side effect. Keep Arch signing fingerprints
and released kernel/ZFS support checks enabled. New adapters must document their
actual tested capabilities. Never equate a build or live boot with disk install
qualification.

Never copy operator credentials, home directories, SSH private keys, Wi-Fi
passwords, personal machine details or host block devices into source, builds,
containers or VMs. Only mount the listed public sources and disposable caches.
Use .build/ for disposable staging and dist/ for generated artifacts. VMs may
attach only regular-file virtual disks. No destructive target disk operation is
authorized by a general request to develop this project.
