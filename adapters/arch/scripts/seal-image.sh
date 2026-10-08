#!/usr/bin/env bash
set -euo pipefail
cd /repo
python scripts/inputs.py --check
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
root="$workspace/root"
if mountpoint -q "$root"; then
    echo 'The extracted root must be unmounted before sealing.' >&2
    exit 1
fi
rm -f "$workspace/airootfs.sfs"
mksquashfs "$root" "$workspace/airootfs.sfs" -noappend -comp zstd -Xcompression-level 6 -mem 512M -processors "${BUILD_JOBS:-2}"
# Both are in the same staging filesystem. Avoid holding two full copies of
# the sealed root while assembling the ISO; later builds replace the tree.
ln -f "$workspace/airootfs.sfs" "$workspace/iso/arch/x86_64/airootfs.sfs"
# The successfully sealed filesystem is now authoritative. Drop the disposable
# extracted tree before writing another full image on space-constrained hosts.
rm -rf -- "$root"
rm -f "$workspace/iso/arch/x86_64/airootfs.sfs.cms.sig"
(cd "$workspace/iso/arch/x86_64"; sha512sum airootfs.sfs > airootfs.sha512)
output="/repo/dist/arch-agent-${values[0]#archlinux-}"
output="${output%.iso}-codex-$codex_version.iso"
rm -f "$output"
# Recreate the stock BIOS + UEFI hybrid layout with our replacement EFI partition.
xorriso -as mkisofs -V "AGENT_${snapshot//\//}" --modification-date="$(cat "$workspace/iso-modification-date")" -iso-level 3 -full-iso9660-filenames -r \
    -isohybrid-mbr "$workspace/boot-images/mbr_code_isohybrid.img" -partition_cyl_align off \
    -partition_offset 16 --mbr-force-bootable -append_partition 2 0xef "$workspace/efi.img" \
    -iso_mbr_part_type 0x00 -c /boot/syslinux/boot.cat -b /boot/syslinux/isolinux.bin \
    -no-emul-boot -boot-load-size 4 -boot-info-table -isohybrid-gpt-basdat \
    -eltorito-alt-boot -e '--interval:appended_partition_2:all::' -no-emul-boot \
    -o "$output" "$workspace/iso"
# Ventoy exposes a mapped ISO device, which filename fallback scans can miss.
# Require the kernel's UUID lookup to identify this exact ISO directly.
uuid=$(basename "$(find "$workspace/iso/boot" -maxdepth 1 -name '*.uuid' -print -quit)" .uuid)
test "$(blkid -p -s UUID -o value "$output")" = "$uuid"
# Previous release directories may hard-link these artifacts. Replace metadata
# paths before writing so a rebuild never changes an archived receipt.
rm -f dist/inputs.lock.json dist/iso-signature.txt dist/packages.txt dist/SHA256SUMS
cp inputs.lock.json dist/inputs.lock.json
cp "$workspace/iso-signature.txt" dist/iso-signature.txt
cp "$workspace/iso/arch/pkglist.x86_64.txt" dist/packages.txt
(cd dist; sha256sum "$(basename "$output")" > SHA256SUMS)
chown -R "${OUTPUT_UID:-0}:${OUTPUT_GID:-0}" /repo/dist
echo "Built $output"
