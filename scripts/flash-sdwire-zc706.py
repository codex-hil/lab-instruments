#!/usr/bin/env python3
"""Back up overwritten SD ranges, flash/read back, and boot ZC706 from SD Wire.

Requires the previously established, hardware-readable ZC706 stop guard. Never
loads PL through JTAG. Preserves backup privately outside the public repository.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import select
import struct
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from labinstruments.storage import SDWireStorage,commissioned_reader_candidate,RemovableStorage
from labinstruments.storage_sdwire import GuardedSDWire,SDWireSession
from labinstruments.sdwire_ftdi import FT200XControl

spec=importlib.util.spec_from_file_location('commission',ROOT/'scripts/commission-sdwire-zc706.py')
commission=importlib.util.module_from_spec(spec)
spec.loader.exec_module(commission)


def backup_card(storage, image_size, backup):
    storage.backend.unmount()
    identity=storage.block_device()
    fd=os.open(identity['device'],os.O_RDONLY|os.O_NOFOLLOW)
    try:
        mbr=os.pread(fd,512,0)
        if mbr[-2:]!=b'\x55\xaa':raise RuntimeError('Existing card has no valid MBR')
        used=512
        for index in range(4):
            entry=mbr[446+16*index:462+16*index]
            start,count=struct.unpack_from('<II',entry,8)
            if count:used=max(used,(start+count)*512)
        size=max(image_size,used)
        if size>identity['capacity']:raise RuntimeError('Invalid backup extent')
        digest=hashlib.sha256();position=0
        backup.parent.mkdir(parents=True,exist_ok=True)
        with backup.open('xb') as out:
            backup.chmod(0o600)
            while position<size:
                data=os.pread(fd,min(1024*1024,size-position),position)
                if not data:raise RuntimeError('Short card backup read')
                out.write(data);digest.update(data);position+=len(data)
            out.flush();os.fsync(out.fileno())
        if identity!=storage.block_device():raise RuntimeError('Card changed during backup')
        repeated=hashlib.sha256();position=0
        while position<size:
            data=os.pread(fd,min(1024*1024,size-position),position)
            if not data:raise RuntimeError('Short repeated backup read')
            repeated.update(data);position+=len(data)
        if repeated.digest()!=digest.digest():raise RuntimeError('Backup reads differ')
        return dict(path=str(backup),bytes=size,sha256=digest.hexdigest(),
                    scope='All original MBR partition extents and the complete overwritten image range; remaining card tail is not written',
                    repeat_read='PASS',filesystem_consistency='NOT_ASSERTED')
    finally:os.close(fd)


def sd_boot(guard, output):
    port='/dev/serial/by-id/usb-Silicon_Labs_CP2103_USB_to_UART_Bridge_Controller_0001-if00-port0'
    if subprocess.run(['fuser',port],capture_output=True).returncode==0:raise RuntimeError('UART busy')
    fd=os.open(port,os.O_RDWR|os.O_NOCTTY|os.O_NONBLOCK)
    transcript=b'';logged_in=False;query=False;last_query=0
    try:
        # BootROM/SPL/U-Boot must load PL from the card. No FPGA/JTAG load.
        guard.dap('''zynq.dap apreg 0 0 0x23000052;
zynq.dap apreg 0 4 0xf8000008; zynq.dap apreg 0 0xc 0xdf0d;
zynq.dap apreg 0 4 0xf8000200; zynq.dap apreg 0 0xc 1''')
        deadline=time.monotonic()+180
        with (output/'sd-boot-uart.log').open('wb') as log:
            while time.monotonic()<deadline:
                if select.select([fd],[],[],.3)[0]:
                    block=os.read(fd,8192);transcript+=block;log.write(block);log.flush()
                if not logged_in and b'zc706-linux login:' in transcript:
                    os.write(fd,b'root\r');logged_in=True
                if logged_in and b'# ' in transcript[-300:] and time.monotonic()-last_query>10:
                    os.write(fd,b'echo HIL_SD_BOOT; hostname; ip -4 addr show eth0; cat /run/zc706-integrated/pll.status.json\r');query=True;last_query=time.monotonic()
                if query and b'HIL_SD_BOOT\r\n' in transcript:
                    addresses=re.findall(rb'inet (192\.168\.2\.\d+)/',transcript)
                    if addresses:
                        return dict(host=addresses[-1].decode(),uart_login=True,
                            spl_seen=b'U-Boot SPL' in transcript,uboot_seen=b'U-Boot ' in transcript,
                            kernel_seen=b'Linux version' in transcript,
                            pl_loaded_by='U-Boot SD boot script',jtag_pl_loaded=False)
            raise RuntimeError('SD boot/login/DHCP not confirmed; inspect UART')
    finally:os.close(fd)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',required=True,type=Path)
    parser.add_argument('--image-sha256',required=True)
    parser.add_argument('--libftdi',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--backup',required=True,type=Path)
    parser.add_argument('--reader-config',type=Path,help='Previously qualified reader identity, needed when card is initially on DUT')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    report=dict(result='FAIL',sd_written=False,dut_booted=False);leases=[]
    try:
        size,digest=RemovableStorage.image_details(args.image)
        if digest!=args.image_sha256:raise RuntimeError('Image SHA256 mismatch')
        for name in ('pm12-210249A73E43.lock','zc706-210251842914.lock'):
            lease=(Path.home()/'.cache'/name).open('a');leases.append(lease)
            fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
        guard=commission.ZC706Guard(args.output)
        if not guard.stopped():raise RuntimeError('Existing hardware stop guard required')
        b=SDWireStorage('DP04I33Y','0403','6015')
        reader=json.loads(args.reader_config.read_text())['reader'] if args.reader_config else commissioned_reader_candidate(b)
        with FT200XControl(args.libftdi,'DP04I33Y') as control:
            backend=GuardedSDWire('DP04I33Y','0403','6015',reader=reader,transport=control,
                                 stop_target=guard.stopped,target_stopped=guard.stopped)
            with SDWireSession('zc706-sdwire',backend,Path.home()/'.local/state/hil-storage',timeout=15) as storage:
                storage.recover()
                host_device=storage.block_device()['device']
                storage.acquire_target();time.sleep(2)
                node=Path('/sys/class/block')/Path(host_device).name/'size'
                if node.exists() and int(node.read_text())>0:raise RuntimeError('HOST still sees card in DUT mode')
                storage.acquire_host()
                report['switch_test']='PASS'
                print('HOST/DUT/HOST PASS; backing up original card extents',flush=True)
                report['backup']=backup_card(storage,size,args.backup)
                (args.output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
                print('Backup and repeated read PASS; writing and verifying image',flush=True)
                report['sd_write_attempted']=True
                (args.output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
                report['flash']=storage.flash(args.image,verify=True)
                report['sd_written']=True
                (args.output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
                print('Image readback PASS; booting from SD without JTAG PL load',flush=True)
                report['boot']=sd_boot(guard,args.output)
                report['dut_booted']=True
                report['result']='PASS_SD_BOOT'
    except BaseException as exc:
        report['error']=str(exc)
        raise
    finally:
        (args.output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
        for lease in reversed(leases):lease.close()
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
