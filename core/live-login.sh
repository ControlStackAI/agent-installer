# Shared login hook: only the primary local live console starts onboarding.
if [ "$(id -u)" = 0 ] && [ -t 0 ] && [ -t 1 ] && [ "$(tty)" = /dev/tty1 ] &&
   [ -e /etc/agent-installer/live-image ] &&
   ! [ -e /sys/firmware/qemu_fw_cfg/by_name/opt/org.controlstackai/smoke/raw ] &&
   ! grep -qw 'agent.smoke=1' /proc/cmdline && [ "${AGENT_SETUP_OPENED:-}" != 1 ]; then
    export AGENT_SETUP_OPENED=1
    agent-installer
fi
