"""No credentials or installation writes are needed for readiness checks."""
import subprocess
import time


class Readiness:
    def __init__(self, profile, run=subprocess.run, sleep=time.sleep, auth_endpoints=()):
        self.profile, self.run, self.sleep = profile, run, sleep
        self.auth_endpoints = list(auth_endpoints)

    def command(self, args):
        return self.run(args, capture_output=True, text=True)

    def internet(self):
        endpoints = [*self.auth_endpoints, *self.profile['package_endpoints']]
        for url in endpoints:
            result = self.command(['curl', '--silent', '--location', '--output', '/dev/null',
                                   '--write-out', '%{http_code}', '--connect-timeout', '5',
                                   '--max-time', '12', url])
            status = result.stdout.strip()
            # 401/403 proves reachability only, never successful model access.
            if result.returncode or not status.isdigit() or not 100 <= int(status) < 500:
                if result.returncode == 60:
                    return False, 'Secure connection failed. Check the clock, or whether this network needs a web sign-in.'
                return False, 'Internet check failed. Connect Ethernet or choose Wi-Fi setup; this network may need a web sign-in.'
        return True, 'Internet connection is working.'

    def clock(self, attempts=20):
        self.command(['timedatectl', 'set-ntp', 'true'])
        for attempt in range(attempts):
            result = self.command(['timedatectl', 'show', '-p', 'NTPSynchronized', '--value'])
            if result.returncode == 0 and result.stdout.strip() == 'yes':
                return True, 'Clock is synchronized.'
            if attempt + 1 < attempts:
                self.sleep(2)
        return False, 'Internet works, but the clock has not synchronized. Retry, or use another network that allows time synchronization.'

    def storage(self):
        if self.profile['default_filesystem'] != 'zfs':
            return True, 'Storage tools are ready.'
        kernel = self.command(['uname', '-r']).stdout.strip()
        module = self.command(['modinfo', '-F', 'vermagic', 'zfs'])
        if not kernel or module.returncode or not module.stdout.split() or module.stdout.split()[0] != kernel:
            return False, 'This image has a ZFS module mismatch. Use a verified image before installing.'
        result = self.command(['modprobe', 'zfs'])
        version = self.command(['zfs', 'version'])
        if result.returncode or version.returncode:
            return False, 'ZFS tools could not start. Open troubleshooting or use a verified image.'
        return True, 'ZFS is ready for this kernel.'

    def ready(self):
        for check in (self.internet, self.clock, self.storage):
            ok, message = check()
            print(message, flush=True)
            if not ok:
                return False
        return True

    def connect(self):
        self.command(['systemctl', 'start', 'NetworkManager.service', 'systemd-timesyncd.service'])
        return self.run(['nmtui']).returncode
