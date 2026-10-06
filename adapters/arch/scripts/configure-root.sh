#!/usr/bin/env bash
# Executed only inside the disposable extracted Arch root.
set -euo pipefail
mapfile -t values < <(python - <<'PY'
import json
l=json.load(open('/root/agent-inputs.json'))
for v in [l['arch']['snapshot'],l['arch']['kernel_package_version'],l['zfs']['signer'],l['codex']['package']['name']]: print(v)
for p in l['zfs']['packages']: print(p['name'])
PY
)
snapshot="${values[0]}"
# Generate exactly one live initramfs after all packages and overlays are ready.
mkdir -p /etc/pacman.d/hooks
ln -s /dev/null /etc/pacman.d/hooks/90-mkinitcpio-install.hook
printf '\nCOMPRESSION="zstd"\nCOMPRESSION_OPTIONS=(-T2 -3)\n' >> /etc/mkinitcpio.conf.d/archiso.conf
printf '[options]\nArchitecture = auto\nCheckSpace\nParallelDownloads = 3\nSigLevel = Required DatabaseOptional\nLocalFileSigLevel = Required\n[core]\nServer = https://archive.archlinux.org/repos/%s/$repo/os/$arch\n[extra]\nServer = https://archive.archlinux.org/repos/%s/$repo/os/$arch\n' "$snapshot" "$snapshot" > /etc/pacman.conf
pacman-key --init
pacman-key --populate archlinux
pacman-key --add /root/archzfs-signing-key.asc
pacman-key --finger "${values[2]}"
# Trust only the separately pinned and reviewed ArchZFS release fingerprint.
pacman-key --lsign-key "${values[2]}"
# An older supported snapshot may be selected when a newer ISO kernel outruns
# released OpenZFS support; align the whole root, including downgrades.
pacman -Syy --noconfirm
for attempt in 1 2 3; do
    if pacman -Suu --noconfirm --needed networkmanager wpa_supplicant curl ca-certificates git ripgrep tmux python openssh; then
        break
    fi
    if [[ "$attempt" == 3 ]]; then exit 1; fi
    echo "Package transaction failed; retry $attempt of 3 using the verified archive cache." >&2
    sleep 5
done
test "$(pacman -Q linux | cut -d ' ' -f 2)" = "${values[1]}"
for package in "${values[@]:4}"; do
    pacman-key --verify "/root/agent-downloads/$package.sig"
done
pacman -U --noconfirm "/root/agent-downloads/${values[4]}" "/root/agent-downloads/${values[5]}"
rm /etc/pacman.d/hooks/90-mkinitcpio-install.hook
mkdir -p /opt/codex
tar -xzf "/root/agent-downloads/${values[3]}" -C /opt/codex --no-same-owner
ln -s /opt/codex/bin/codex /usr/local/bin/codex
ln -s /opt/codex/bin/codex-code-mode-host /usr/local/bin/codex-code-mode-host
