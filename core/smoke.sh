#!/usr/bin/env bash
set -euo pipefail
exec > /dev/ttyS0 2>&1
trap 'echo AGENT_SMOKE_FAIL; systemctl poweroff' ERR
# This service runs only with an explicit test flag in a disposable VM.
echo AGENT_SMOKE_START
case "$(systemd-detect-virt)" in kvm|qemu) ;; *) false ;; esac
uname -r
codex --version
agent-installer-tui --version
agent-installer-tui --render 80 25 | grep -F 'Guided setup'
agent-installer-tui --render 80 25 | grep -F 'Direct agent conversation'
agent-support presets --preset custom
echo AGENT_TUI_PACKAGE_PASS
help=$(codex login --help)
grep -F -- '--device-auth' <<< "$help"
grep -F -- '--with-api-key' <<< "$help"
systemctl is-active NetworkManager
test "$(findmnt -n -o FSTYPE /run)" = tmpfs
test ! -e /root/.codex/auth.json
modprobe zfs zfs_arc_max=134217728
zfs version
for attempt in {1..45}; do
    if agent-preflight; then break; fi
    if [[ "$attempt" == 45 ]]; then false; fi
    sleep 2
done
echo AGENT_PREFLIGHT_PASS

# Shared tests exercise offline gating, all authentication methods, private RAM
# identity and secret transport using fixtures; never an actual owner account.
PYTHONPATH="${PYTHONPATH:-/usr/lib/agent-installer}" python -m unittest discover -s /usr/share/agent-installer/tests -v
echo AGENT_LAUNCHER_FIXTURES_PASS

# File-backed vdevs exist only in guest RAM. Exercise snapshot portability,
# rollback, incremental send/receive and export/import without attaching disks.
test -z "$(zpool list -H -o name 2>/dev/null)"
area=/run/agent-zfs-test
mkdir -m 700 "$area"
truncate -s 256M "$area/source.vdev" "$area/replica.vdev"
zpool create -o cachefile=none -O mountpoint=none agenttest "$area/source.vdev"
zpool create -o cachefile=none -O mountpoint=none agentreplica "$area/replica.vdev"
zfs create -o mountpoint="$area/source" agenttest/data
printf 'snapshot portability sentinel\n' > "$area/source/sentinel"
original=$(sha256sum "$area/source/sentinel" | cut -d ' ' -f 1)
zfs snapshot agenttest/data@baseline
printf 'temporary change\n' > "$area/source/sentinel"
zfs rollback agenttest/data@baseline
test "$(sha256sum "$area/source/sentinel" | cut -d ' ' -f 1)" = "$original"
zfs send agenttest/data@baseline | zfs receive -u agentreplica/data
zfs set mountpoint="$area/replica" agentreplica/data
test "$(zfs get -H -o value mounted agentreplica/data)" = yes
test "$(sha256sum "$area/replica/sentinel" | cut -d ' ' -f 1)" = "$original"
printf 'incremental snapshot sentinel\n' > "$area/source/sentinel"
zfs snapshot agenttest/data@next
zfs send -i agenttest/data@baseline agenttest/data@next | zfs receive agentreplica/data
latest=$(sha256sum "$area/source/sentinel" | cut -d ' ' -f 1)
test "$(sha256sum "$area/replica/sentinel" | cut -d ' ' -f 1)" = "$latest"
zpool export agentreplica
zpool import -d "$area" agentreplica
test "$(sha256sum "$area/replica/sentinel" | cut -d ' ' -f 1)" = "$latest"
zpool status -x agenttest
zpool status -x agentreplica
zpool destroy agenttest
zpool destroy agentreplica
rm -rf "$area"
echo AGENT_ZFS_SNAPSHOT_PASS
echo AGENT_SMOKE_PASS
systemctl poweroff
