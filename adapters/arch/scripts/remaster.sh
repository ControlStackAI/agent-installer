#!/usr/bin/env bash
set -euo pipefail
cd /repo
python scripts/inputs.py --check
# Build only from public Rust sources and the reviewed crate checksum lock.
# Cargo's cache stays in disposable staging; no operator Cargo profile is mounted.
CARGO_HOME=/repo/.build/cargo-home cargo build --locked --release --jobs "${BUILD_JOBS:-2}" \
    --manifest-path /shared/frontends/ratatui/Cargo.toml --target-dir /repo/.build/tui-target
mapfile -t values < <(python - <<'PY'
import json
l=json.load(open('inputs.lock.json'))
for v in [l['arch']['iso']['name'], l['arch']['signer'], l['arch']['snapshot'], l['arch']['kernel_release'], l['arch']['kernel_package_version'], l['codex']['version'], l['codex']['package']['name'], l['zfs']['signer']]: print(v)
PY
)
downloads="/repo/.build/downloads/$(sha256sum inputs.lock.json | cut -d ' ' -f 1)"
iso="$downloads/${values[0]}"
snapshot="${values[2]}"
kernel="${values[3]}"
codex_version="${values[5]}"
workspace="/repo/.build/remaster"
# A subsequent build replaces only the previous disposable build tree.
if mountpoint -q "$workspace/root/proc"; then
    echo 'Previous chroot is still mounted; clean it up before rebuilding.' >&2
    exit 1
fi
rm -rf "$workspace"
mkdir -p "$workspace/gnupg" /repo/dist
chmod 700 "$workspace/gnupg"
gpg --homedir "$workspace/gnupg" --import config/arch-iso-signing-key.asc config/archzfs-signing-key.asc
gpg --homedir "$workspace/gnupg" --status-fd 1 --verify "$iso.sig" "$iso" > "$workspace/iso-signature.txt"
grep -Eq "^\[GNUPG:\] VALIDSIG [0-9A-F]+ .*${values[1]}$|^\[GNUPG:\] VALIDSIG ${values[1]} " "$workspace/iso-signature.txt"

xorriso -osirrox on -indev "$iso" -extract / "$workspace/iso" -extract_boot_images "$workspace/boot-images"
# The appended-partition copies duplicate the El Torito EFI image used below.
rm -f "$workspace/boot-images/mbr_part2_efi.img" "$workspace/boot-images/gpt_part3_efi.img"
chmod -R u+w "$workspace/iso"
unsquashfs -processors "${BUILD_JOBS:-2}" -d "$workspace/root" "$workspace/iso/arch/x86_64/airootfs.sfs"
# A new sealed filesystem replaces this stock copy after customization.
rm -f "$workspace/iso/arch/x86_64/airootfs.sfs"
root="$workspace/root"
# pacman's space checks require the chroot itself to be a mount point.
mount --bind "$root" "$root"
trap 'umount -R "$root" || true' EXIT
rm -f "$root/etc/resolv.conf"
cp /etc/resolv.conf "$root/etc/resolv.conf"
cp /repo/inputs.lock.json "$root/root/agent-inputs.json"
mkdir -p "$root/root/agent-downloads"
cp "$downloads/"zfs-*.pkg.tar.zst* "$downloads/${values[6]}" "$root/root/agent-downloads/"
# Persist only public package archives; pacman checks their signatures on use.
package_cache="/repo/.build/pacman-cache/${snapshot//\//-}"
mkdir -p "$package_cache" "$root/var/cache/pacman/pkg"
cp "$downloads/"linux-*.pkg.tar.zst "$package_cache/"
mount --bind "$package_cache" "$root/var/cache/pacman/pkg"
cp /repo/config/archzfs-signing-key.asc "$root/root/archzfs-signing-key.asc"
cp /repo/scripts/configure-root.sh "$root/root/agent-build.sh"
arch-chroot "$root" /bin/bash /root/agent-build.sh

cp -a /repo/live/. "$root/"
chmod 755 "$root/usr/local/bin/agent-installer" "$root/usr/local/bin/agent-network" "$root/usr/local/bin/agent-preflight" "$root/usr/local/bin/agent-smoke-test"
mkdir -p "$root/usr/share/arch-agent-installer"
cp /repo/inputs.lock.json "$root/usr/share/arch-agent-installer/inputs.lock.json"
python /shared/core/install-overlay.py "$root" /shared --distro arch
install -D -m 755 /repo/.build/tui-target/release/agent-installer-tui "$root/usr/local/libexec/agent-installer-tui"
cp /shared/frontends/ratatui/Cargo.lock "$root/usr/share/agent-installer/tui-Cargo.lock"
python /shared/tui-notices.py --lock /shared/frontends/ratatui/Cargo.lock \
    --sources /repo/.build/cargo-home/registry/src --output "$root/usr/share/agent-installer/tui-notices"
cp /repo/inputs.lock.json "$root/usr/share/agent-installer/arch-inputs.lock.json"
arch-chroot "$root" systemctl disable systemd-networkd.service systemd-networkd.socket systemd-networkd-wait-online.service iwd.service systemd-resolved.service
arch-chroot "$root" systemctl enable NetworkManager.service systemd-timesyncd.service agent-smoke-test.service
# NetworkManager owns DNS and credentials remain on the live RAM overlay.
rm -f "$root/etc/resolv.conf"
ln -s /run/NetworkManager/resolv.conf "$root/etc/resolv.conf"
arch-chroot "$root" pacman -Q > "$workspace/iso/arch/pkglist.x86_64.txt"
arch-chroot "$root" /opt/codex/bin/codex --version | grep -Fx "codex-cli $codex_version"
arch-chroot "$root" modinfo -k "$kernel" -F vermagic zfs | grep -F "$kernel "
test -f "$root/usr/lib/modules/$kernel/vmlinuz"
# Regenerate the live initramfs against the matching new kernel, never the host kernel.
arch-chroot "$root" depmod "$kernel"
# Do not pass -c: it disables the ArchISO live-boot configuration drop-in.
arch-chroot "$root" mkinitcpio -k "$kernel" -g /root/agent-initramfs.img
arch-chroot "$root" lsinitcpio /root/agent-initramfs.img | grep -Fx 'hooks/archiso'
cp "$root/usr/lib/modules/$kernel/vmlinuz" "$workspace/iso/arch/boot/x86_64/vmlinuz-linux"
cp "$root/root/agent-initramfs.img" "$workspace/iso/arch/boot/x86_64/initramfs-linux.img"

# Separate our live-medium identity from the stock ISO on the same Ventoy disk.
mapfile -t identity < <(python - <<'PY'
from datetime import datetime, timezone
now=datetime.now(timezone.utc)
hundredths=f'{now.microsecond // 10000:02d}'
print(now.strftime('%Y%m%d%H%M%S')+hundredths)
print(now.strftime('%Y-%m-%d-%H-%M-%S-')+hundredths)
PY
)
uuid="${identity[1]}"
printf '%s\n' "${identity[0]}" > "$workspace/iso-modification-date"
old_uuid=$(basename "$(find "$workspace/iso/boot" -maxdepth 1 -name '*.uuid' -print -quit)" .uuid)
test -n "$old_uuid"
find "$workspace/iso/boot" -maxdepth 1 -name '*.uuid' -delete
touch "$workspace/iso/boot/$uuid.uuid"
python - "$workspace/iso" "$old_uuid" "$uuid" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1])
for pattern in ('*.conf','*.cfg'):
    for path in root.rglob(pattern):
        text=path.read_text().replace(sys.argv[2],sys.argv[3]).replace('Arch Linux install medium','ControlStackAI Arch agent installer')
        # The stock CMS signature cannot authenticate our changed squashfs.
        text=text.replace('cms_verify=y','cms_verify=n')
        path.write_text(text)
PY

# Rebuild the appended FAT image as well: UEFI boots its copy of these files.
mkdir -p "$workspace/efi-tree"
mcopy -s -i "$workspace/boot-images/eltorito_img2_uefi.img" '::*' "$workspace/efi-tree/"
cp "$workspace/iso/arch/boot/x86_64/"* "$workspace/efi-tree/arch/boot/x86_64/"
cp -a "$workspace/iso/loader/." "$workspace/efi-tree/loader/"
truncate -s 512M "$workspace/efi.img"
mkfs.fat -F 32 -n AGENT_EFI "$workspace/efi.img"
mcopy -s -i "$workspace/efi.img" "$workspace/efi-tree/"* ::/

# Detach the shared public cache before scrubbing the sealed live filesystem.
umount "$root/var/cache/pacman/pkg"
# Scrub disposable build inputs, caches and generated IDs before sealing the root.
rm -rf "$root/root/agent-downloads" "$root/root/agent-inputs.json" "$root/root/agent-build.sh" "$root/root/archzfs-signing-key.asc" "$root/root/agent-initramfs.img" "$root/var/cache/pacman/pkg/"* "$root/var/log/"*
: > "$root/etc/machine-id"
rm -f "$root/var/lib/dbus/machine-id"
test ! -e "$root/root/.codex/auth.json"
umount "$root"
trap - EXIT
bash /repo/scripts/seal-image.sh
