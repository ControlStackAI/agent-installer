#!/usr/bin/env python3
import argparse,hashlib,json,os,socket,subprocess,time,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description='Verify the ordinary live console without opting into smoke tests.')
parser.add_argument('iso',type=Path)
parser.add_argument('--boot-wait',type=int,default=90)
parser.add_argument('--distro',choices=['arch','nixos'],required=True)
parser.add_argument('--offline',action='store_true')
args=parser.parse_args()
if not args.iso.is_file():parser.error('ISO must be a regular file')
root=ROOT
area=root/'.build/smoke'/args.distro;area.mkdir(parents=True,exist_ok=True)
iso=args.iso.resolve()
socket_dir=tempfile.TemporaryDirectory(prefix='arch-agent-qmp-')
qmp=Path(socket_dir.name)/'control.sock'
mode='offline-console' if args.offline else 'normal-console'
log=area/(mode+'.log');log.write_text('')
(area/(mode+'-result.json')).unlink(missing_ok=True)
cmd=['qemu-system-x86_64','-machine','q35','-m','1536','-smp','2','-display','none','-monitor','none','-serial','file:'+str(log),'-qmp','unix:'+str(qmp)+',server=on,wait=off','-cdrom',str(iso),'-boot','d','-nic','none' if args.offline else 'user,model=virtio-net-pci','-no-reboot']
if os.access('/dev/kvm',os.R_OK|os.W_OK):cmd+=['-enable-kvm','-cpu','host']
else:cmd+=['-accel','tcg','-cpu','max']
started=time.monotonic()
with (area/'normal-qemu.log').open('w') as err:
    p=subprocess.Popen(cmd,stderr=err)
    try:
        for _ in range(50):
            if qmp.exists():break
            time.sleep(.1)
        sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);sock.connect(str(qmp));sock.settimeout(15)
        stream=sock.makefile('rwb',buffering=0)
        json.loads(stream.readline())
        counter=0
        def call(execute,arguments=None):
            global counter
            counter+=1
            msg={'execute':execute,'id':counter}
            if arguments is not None:msg['arguments']=arguments
            stream.write(json.dumps(msg).encode()+b'\n')
            while True:
                response=json.loads(stream.readline())
                if response.get('id')==counter:
                    if 'error' in response:raise RuntimeError(response)
                    return response.get('return')
        call('qmp_capabilities')
        def type_text(text):
            keys={' ':'spc','\n':'ret','/':'slash','.':'dot','-':'minus','_':'shift-minus','>':'shift-dot'}
            for char in text:
                call('human-monitor-command',{'command-line':'sendkey '+keys.get(char,('shift-'+char.lower()) if char.isupper() else char)+' 10'})
                time.sleep(.025)
        time.sleep(args.boot_wait)
        call('screendump',{'filename':str(area/(mode+'-onboarding.png')),'format':'png'})
        type_text('9\n')
        time.sleep(2)
        type_text('systemctl is-active agent-smoke-test.service >/dev/ttyS0\n')
        time.sleep(1)
        type_text('codex --version >/dev/ttyS0\n')
        time.sleep(1)
        type_text('agent-installer --facts >/dev/ttyS0\n')
        time.sleep(2)
        type_text('exit\n')
        time.sleep(3)
        type_text('0\n')
        time.sleep(2)
        type_text('echo normal_boot_pass >/dev/ttyS0\n')
        time.sleep(1)
        call('screendump',{'filename':str(area/'normal-console.png'),'format':'png'})
        type_text('poweroff\n')
        p.wait(timeout=30)
    finally:
        if p.poll() is None:p.terminate();p.wait(timeout=10)
socket_dir.cleanup()
output=log.read_text(errors='replace')
version=json.loads((root/'runtimes/codex/inputs.lock.json').read_text())['version']
passed=all(x in output for x in ('inactive','"phase": "live"', '"distro_id": "'+args.distro+'"','codex-cli '+version,'normal_boot_pass')) and 'AGENT_SMOKE_START' not in output and p.returncode==0
with iso.open('rb') as iso_file:
    iso_hash=hashlib.file_digest(iso_file,'sha256').hexdigest()
receipt={'iso_sha256':iso_hash,'mode':mode,'passed':passed,'elapsed_seconds':round(time.monotonic()-started,2),'checks':['normal ISO boot without smoke flag','smoke service remains inactive','real root console keyboard input','actual Codex binary starts','automatic guided launcher and troubleshooting shell', 'offline connectivity gate' if args.offline else 'online onboarding'],'disk_devices':'ISO only; no host or target disks','not_tested':['owner account login','model response','disk installation']}
(area/(mode+'-result.json')).write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt));print(output)
assert passed
