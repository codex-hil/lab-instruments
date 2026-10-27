#!/usr/bin/env python3
"""Bounded ZC706/SDWire commissioning, with UART shutdown and JTAG stop guard.

No SD data writes, FPGA programming, boot-environment or QSPI writes.
On success leaves SDIO/CPUs stopped and selection unchanged. Board owner must
finish the storage operation and reset/boot the board under the same lease.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from labinstruments.sdwire_ftdi import FT200XControl
from labinstruments.storage import SDWireStorage, RemovableStorage


class ZC706Guard:
    def __init__(self, output):
        self.output=output
        self.config=output/'guard.cfg'
        self.config.write_text('''adapter driver ftdi
ftdi vid_pid 0x0403 0x6014
adapter serial 210251842914
ftdi channel 0
ftdi layout_init 0x00e8 0x60eb
adapter speed 1000
transport select jtag
jtag newtap zynq_pl bs -irlen 6 -ircapture 1 -irmask 3 -expected-id 0x23731093
jtag newtap zynq cpu -irlen 4 -ircapture 1 -irmask 15 -expected-id 0x4ba00477
dap create zynq.dap -chain-position zynq.cpu
target create zynq.cpu0 cortex_a -dap zynq.dap -coreid 0 -dbgbase 0x80090000
target create zynq.cpu1 cortex_a -dap zynq.dap -coreid 1 -dbgbase 0x80092000
''')
        self.sequence=0

    def dap(self, commands):
        prefix='gdb_port disabled; telnet_port disabled; tcl_port disabled; init; '
        result=subprocess.run(['openocd','-f',str(self.config),'-c',prefix+commands+'; shutdown'],
                              capture_output=True,text=True,timeout=20)
        self.sequence+=1
        text=result.stdout+result.stderr
        (self.output/f'jtag-{self.sequence:03}.log').write_text(text)
        if result.returncode:raise RuntimeError(text)
        return text

    @staticmethod
    def read_sdio():
        return 'zynq.dap apreg 0 0 0x23000052; zynq.dap apreg 0 4 0xf8000218; set sdio [zynq.dap apreg 0 0xc]'

    def stopped(self):
        text=self.dap(self.read_sdio()+''';
if {(([expr $sdio] & 0x11) == 0x11) && ([zynq.cpu0 curstate] eq "halted") && ([zynq.cpu1 curstate] eq "halted")} { echo HIL_STOPPED_VERIFIED } else { error "DUT stop guard lost" }''')
        return 'HIL_STOPPED_VERIFIED' in text

    def stop(self):
        self.dap('''targets zynq.cpu0; halt; targets zynq.cpu1; halt; '''+self.read_sdio()+''';
zynq.dap apreg 0 4 0xf8000008; zynq.dap apreg 0 0xc 0xdf0d;
zynq.dap apreg 0 4 0xf8000218; zynq.dap apreg 0 0xc [expr $sdio | 0x11]''')
        if not self.stopped():raise RuntimeError('DUT guard not established')


def uart_quiesce(output):
    port='/dev/serial/by-id/usb-Silicon_Labs_CP2103_USB_to_UART_Bridge_Controller_0001-if00-port0'
    if subprocess.run(['fuser',port],capture_output=True).returncode==0:
        raise RuntimeError('UART has another owner')
    fd=os.open(port,os.O_RDWR|os.O_NOCTTY|os.O_NONBLOCK)
    transcript=b''
    def receive(seconds):
        nonlocal transcript
        end=time.monotonic()+seconds;data=b''
        while time.monotonic()<end:
            if select.select([fd],[],[],max(0,end-time.monotonic()))[0]:
                data+=os.read(fd,4096)
        transcript+=data
        (output/'uart-quiesce.log').write_bytes(transcript)
        return data
    try:
        os.write(fd,b'\x03\r');receive(.5)
        os.write(fd,b'IFS= read -r h < /proc/sys/kernel/hostname; echo HIL_HOST="$h"\r')
        if b'HIL_HOST=zc706-linux' not in receive(2):
            raise RuntimeError('Expected ZC706 Linux shell')
        # This kernel has no CONFIG_MAGIC_SYSRQ. BusyBox init handles SIGUSR1
        # as orderly halt, calling sync even when SD shutdown prevents rcK exec.
        os.write(fd,b'IFS= read -r p < /proc/1/comm; echo HIL_INIT="$p"\r')
        if b'HIL_INIT=init' not in receive(2):
            raise RuntimeError('Expected BusyBox init before halt signal')
        os.write(fd,b'kill -USR1 1\r')
        result=receive(15)
        if b'System halted' not in result:
            raise RuntimeError('Kernel halt not confirmed; no controller write')
    finally:os.close(fd)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--libftdi',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    report={'sd_written':False,'eeprom_written':False,'result':'FAIL'}
    leases=[]
    try:
        for name in ('pm12-210249A73E43.lock','zc706-210251842914.lock'):
            lease=(Path.home()/'.cache'/name).open('a');leases.append(lease)
            fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
        backend=SDWireStorage('DP04I33Y','0403','6015')
        with RemovableStorage('zc706-sdwire',backend,Path.home()/'.local/state/hil-storage'):
            backend.control_device()
            uart_quiesce(args.output)
            guard=ZC706Guard(args.output)
            guard.stop()
            with FT200XControl(args.libftdi,'DP04I33Y') as control:
                backup=Path.home()/'.local/share/sdwire-backups/DP04I33Y/pre-commission-20261027.bin'
                report['commission']=control.commission_cbus0(backup,guard.stopped)
                report['eeprom_written']=report['commission']['written']
            report.update(result='PASS_MTP_READBACK',dut_stopped=guard.stopped(),
                          selection_test='NOT_RUN',reconnect_may_be_required=True)
    except BaseException as exc:
        report['error']=str(exc)
        raise
    finally:
        (args.output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
        for lease in reversed(leases):lease.close()
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
