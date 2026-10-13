#!/usr/bin/env python3
"""Bounded real SDWire inventory/read test. Never switch, reset, mount or write.

Holds both the SDWire transaction lock and shared Genesys lease conservatively;
DUT attachment is not assumed. OS access errors are evidence, not bypassed.
"""
import argparse
import ctypes
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
import stat

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from labinstruments.storage import (SDWireStorage, RemovableStorage, discover_sdwire,
                                    commissioned_reader_candidate, StorageError)

parser = argparse.ArgumentParser()
parser.add_argument('--serial', required=True)
parser.add_argument('--output', required=True, help='New report directory')
parser.add_argument('--runtime', default=str(Path.home()/'.local/state/hil-storage'))
args = parser.parse_args()
out = Path(args.output)
out.mkdir(parents=True, exist_ok=False)
report = {'timestamp': datetime.now(timezone.utc).isoformat(), 'validation': 'HARDWARE_READ_ONLY',
          'serial': args.serial, 'write_test': 'NOT_RUN', 'switch_test': 'BLOCKED_OFF_UNSUPPORTED',
          'eeprom_write': 'NOT_RUN', 'tests': {}, 'board_actions': 'NONE'}
lease = None
try:
    lease = os.open(Path.home()/'.cache/genesys-210383B7F02DA.lock', os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW, 0o600)
    fcntl.flock(lease, fcntl.LOCK_EX|fcntl.LOCK_NB)
    matches = [d for d in discover_sdwire() if d['serial'] == args.serial]
    if len(matches) != 1:
        raise StorageError('IDENTITY', 'Expected exactly one SDWire with requested serial')
    device = matches[0]
    report['controller'] = device
    backend = SDWireStorage(args.serial, device['vid'], device['pid'])
    with RemovableStorage('sdwire-01', backend, args.runtime) as storage:
        backend.reader = commissioned_reader_candidate(backend)
        identity = storage.block_device()
        report['identity'] = identity
        report['partitions'] = storage.partitions()
        report['status'] = storage.info()
        report['tests']['topology_identity'] = 'PASS'
        control = backend.control_device()
        usbnode = Path('/dev/bus/usb')/f"{int(backend.read(control/'busnum')):03d}"/f"{int(backend.read(control/'devnum')):03d}"
        try:
            fd = os.open(usbnode, os.O_RDWR|os.O_NOFOLLOW)
            try:
                class Transfer(ctypes.Structure):
                    _fields_ = [('type',ctypes.c_uint8),('request',ctypes.c_uint8),
                                ('value',ctypes.c_uint16),('index',ctypes.c_uint16),
                                ('length',ctypes.c_uint16),('timeout',ctypes.c_uint32),('data',ctypes.c_void_p)]
                value = ctypes.c_uint8()
                transfer = Transfer(0xc0, 0x0c, 0, 1, 1, 2000, ctypes.addressof(value))
                request = (3<<30)|(ctypes.sizeof(Transfer)<<16)|(ord('U')<<8)
                result = fcntl.ioctl(fd, request, bytearray(transfer), True)
                if result != 1:
                    raise StorageError('PROTOCOL', 'Read-pins transfer returned unexpected length')
                report['tests']['usb_read_pins'] = {'result':'PASS', 'raw':value.value,
                    'ownership':'unknown: factory CBUS configuration not qualified'}
            finally:
                os.close(fd)
        except (OSError,StorageError) as e:
            report['tests']['usb_read_pins'] = {'result':'NOT_RUN' if isinstance(e,PermissionError) else 'FAIL',
                'code':'ACCESS' if isinstance(e,PermissionError) else getattr(e,'code','IO'), 'diagnostic':str(e)}
        try:
            fd = os.open(identity['device'], os.O_RDONLY|os.O_NOFOLLOW)
            try:
                node = os.fstat(fd)
                expected = backend.read(backend.sysfs/'class/block'/Path(identity['device']).name/'dev')
                if not stat.S_ISBLK(node.st_mode):
                    raise StorageError('IDENTITY', 'Opened object is not a block device')
                if f'{os.major(node.st_rdev)}:{os.minor(node.st_rdev)}' != expected or identity != storage.block_device():
                    raise StorageError('IDENTITY','Opened disk identity mismatch')
                first = os.pread(fd, 1024*1024, 0)
                second = os.pread(fd, 1024*1024, 0)
                if len(first) != 1024*1024 or first != second or identity != storage.block_device():
                    raise StorageError('VERIFY','Two bounded reads differ or device changed')
                report['tests']['card_read_repeat'] = {'result':'PASS','bytes':len(first),
                    'sha256':hashlib.sha256(first).hexdigest()}
            finally:
                os.close(fd)
        except (OSError,StorageError) as e:
            report['tests']['card_read_repeat'] = {'result':'NOT_RUN' if isinstance(e,PermissionError) else 'FAIL',
                'code':'ACCESS' if isinstance(e,PermissionError) else getattr(e,'code','IO'), 'diagnostic':str(e)}
        config = {'storage':{'sdwire-01': {'backend':'sdwire','serial':args.serial,
                  'vid':device['vid'],'pid':device['pid'],'reader':backend.reader}}}
        (out/'storage.json').write_text(json.dumps(config,indent=2)+'\n')
    report['result'] = 'PARTIAL' if any(isinstance(t,dict) and t['result'] != 'PASS'
                                     for t in report['tests'].values()) else 'PASS_READ_ONLY'
except BaseException as e:
    report['result'] = 'BLOCKED'
    report['error'] = {'code':'LOCKED' if isinstance(e,BlockingIOError) else getattr(e,'code','IO'),'message':str(e)}
finally:
    if lease is not None:
        os.close(lease)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,sort_keys=True))
sys.exit(0 if report['result'] == 'PASS_READ_ONLY' else 5)
