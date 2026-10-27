"""Transport-independent removable storage transactions. Linux, Python >=3.11.

SDWire v1 has no OFF: its production backend intentionally refuses mutations.
Mock resources never open block devices and are visibly SIMULATED.
"""
from __future__ import annotations
import contextlib
import fcntl
import gzip
import hashlib
import json
import lzma
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Protocol


class StorageError(RuntimeError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def fail(code, message):
    raise StorageError(code, message)


def token(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,96}', value):
        fail('CONFIG', 'Invalid storage alias/serial')
    return value


def run(argv):
    try:
        return subprocess.run(argv, check=True, capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError) as e:
        fail('IO', f'{argv[0]} failed: {e}')


class Backend(Protocol):
    serial: str
    kind: str
    simulated: bool
    supports_off: bool
    def state(self) -> str: ...
    def switch(self, state: str) -> None: ...
    def device(self) -> dict: ...
    def quiesce_target(self) -> None: ...
    def unmount(self) -> None: ...
    def mount(self, partition: str) -> Path: ...
    def partitions(self) -> list[dict]: ...
    def open_writer(self, identity: dict): ...
    def before_write(self) -> None: ...
    def before_copy(self) -> None: ...


class MockRemovableStorage:
    """Persistent simulated backend. Only private regular files, never /dev/*."""
    kind = 'mock'
    simulated = True
    supports_off = True

    def __init__(self, serial, root, capacity=64 * 1024 * 1024, faults=()):
        self.serial = token(serial)
        self.root = Path(root) / self.serial
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.root.is_symlink() or self.root.stat().st_uid != os.getuid():
            fail('IDENTITY', 'Mock directory must be owned by this user and not a symlink')
        self.capacity = int(capacity)
        if self.capacity <= 0:
            fail('CONFIG', 'Mock capacity must be positive')
        self.faults = set(faults)
        self.events = []
        self.card = self.root / 'card.bin'
        self.statefile = self.root / 'state.json'
        if not self.statefile.exists():
            self._save('off')

    def _save(self, state):
        tmp = self.root / 'state.tmp'
        tmp.write_text(json.dumps({'state': state}))
        tmp.replace(self.statefile)

    def state(self):
        return json.loads(self.statefile.read_text())['state']

    def _fault(self, operation):
        if operation in self.faults:
            if operation == 'interrupt':
                raise KeyboardInterrupt()
            fail('SIMULATED_FAILURE', operation)

    def switch(self, state):
        self._fault('switch')
        if state != 'off' and self.state() != 'off':
            fail('UNSAFE_SWITCH', 'Break-before-make required')
        self.events.append(state)
        self._save(state)

    def quiesce_target(self):
        self._fault('quiesce')
        self.events.append('stop_target')

    def unmount(self):
        self._fault('unmount')
        self.events.append('unmount')

    def device(self):
        self._fault('disappears')
        if self.state() != 'host':
            fail('NO_CARD', 'Mock card is not owned by HOST')
        self._fault('no_card')
        return {'device': str(self.card), 'serial': self.serial,
                'usb_path': f'SIMULATED/{self.serial}', 'capacity': self.capacity,
                'removable': True, 'card_present': True, 'simulated': True,
                'vid': 'SIMULATED', 'pid': 'SIMULATED'}

    def before_write(self):
        self._fault('write')
        self._fault('interrupt')

    def before_copy(self):
        self._fault('copy')

    def open_writer(self, identity):
        self._fault('wrong_device')
        if identity != self.device() or Path(identity['device']) != self.card:
            fail('IDENTITY', 'Wrong mock device')
        fd = os.open(self.card, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        s = os.fstat(fd)
        if not stat.S_ISREG(s.st_mode) or s.st_nlink != 1 or s.st_uid != os.getuid():
            os.close(fd)
            fail('IDENTITY', 'Mock writer requires a private regular file')
        os.ftruncate(fd, self.capacity)
        return os.fdopen(fd, 'r+b', buffering=0)

    def partitions(self):
        self.device()
        return [{'name': 'boot', 'label': 'BOOT', 'simulated': True}]

    def mount(self, partition):
        self._fault('mount')
        if partition != 'boot':
            fail('NO_PARTITION', 'Mock supports boot only')
        self.device()
        path = self.root / 'boot'
        path.mkdir(exist_ok=True)
        return path


class SDWireStorage:
    """3mdeb SDWire legacy read-only backend; no unsafe fallback for missing OFF."""
    kind = 'sdwire'
    simulated = False
    supports_off = False

    def __init__(self, serial, vid='04e8', pid='6001', reader=None,
                 sysfs='/sys', by_id='/dev/disk/by-id', controller='sd-mux-ctrl'):
        self.serial = token(serial)
        self.vid, self.pid = vid.lower(), pid.lower()
        if (self.vid, self.pid) not in {('04e8', '6001'), ('0403', '6001'), ('0403', '6015')}:
            fail('CONFIG', 'Unsupported SDWire controller VID/PID')
        self.reader = reader
        self.sysfs, self.by_id = Path(sysfs), Path(by_id)
        self.controller = controller

    @staticmethod
    def read(path):
        try:
            return path.read_text().strip()
        except OSError:
            return None

    def control_device(self):
        matches = [p.resolve() for p in (self.sysfs / 'bus/usb/devices').glob('*')
                   if self.read(p / 'idVendor') == self.vid
                   and self.read(p / 'idProduct') == self.pid
                   and self.read(p / 'serial') == self.serial]
        if len(matches) != 1:
            fail('IDENTITY', f'Expected exactly one SDWire {self.serial}, found {len(matches)}')
        p = matches[0]
        if (self.vid, self.pid) == ('0403', '6015'):
            if self.read(p / 'product') != 'FT200X USB I2C' or not factory_sdwire_topology(p):
                fail('IDENTITY', 'Factory FT200X lacks unique SDWire reader/hub association')
        elif self.read(p / 'product') != 'sd-wire':
            fail('IDENTITY', 'USB product is not sd-wire; refusing generic FTDI')
        return p

    def state(self):
        self.control_device()
        if (self.vid, self.pid) == ('0403', '6015'):
            fail('UNCOMMISSIONED_FACTORY', 'Factory EEPROM/CBUS role not qualified; ownership unknown. No EEPROM writes performed.')
        out = run([self.controller, f'--device-serial={self.serial}',
                   f'--vendor=0x{self.vid}', f'--product=0x{self.pid}', '--status'])
        states = re.findall(r'^SD connected to: (TS|DUT)$', out, re.M)
        if len(states) != 1:
            fail('PROTOCOL', 'Unrecognized sd-mux-ctrl status')
        return {'TS': 'host', 'DUT': 'target'}[states[0]]

    def switch(self, state):
        fail('OFF_UNSUPPORTED', '3mdeb SDWire has no independent OFF. '
             'No switching or writing until a verified hardware isolation backend exists.')

    def quiesce_target(self):
        fail('DUT_NOT_QUIESCED', 'DUT power/reset interlock is required')

    def unmount(self):
        fail('OFF_UNSUPPORTED', 'Production transactions disabled without OFF')

    def mount(self, partition):
        self.switch('host')

    def before_write(self):
        self.switch('host')

    def before_copy(self):
        self.switch('host')

    def open_writer(self, identity):
        self.switch('host')

    def device(self):
        control = self.control_device()
        if not self.reader:
            fail('IDENTITY', 'Configure reader VID/PID, serial, USB path, by-id and capacity bounds')
        r = self.reader
        required = {'vid', 'pid', 'serial', 'usb_path', 'by_id', 'min_capacity', 'max_capacity'}
        if not required <= r.keys() or not r['serial']:
            fail('CONFIG', 'Incomplete reader identity')
        reader = (self.sysfs / 'bus/usb/devices' / r['usb_path']).resolve()
        # Controller and card reader must be distinct sibling ports of the SDWire hub.
        if reader == control or reader.parent != control.parent:
            fail('IDENTITY', 'Reader is not an SDWire hub sibling')
        if (self.read(control.parent / 'idVendor'), self.read(control.parent / 'idProduct')) != ('0424', '2640'):
            fail('IDENTITY', 'Parent is not the expected USB2640 SDWire hub')
        for key, filename in [('vid', 'idVendor'), ('pid', 'idProduct'), ('serial', 'serial')]:
            if self.read(reader / filename) != r[key]:
                fail('IDENTITY', f'Reader {key} mismatch')
        matches = []
        for p in (self.sysfs / 'class/block').glob('*'):
            if (p / 'partition').exists():
                continue
            resolved = (p / 'device').resolve()
            if reader in resolved.parents:
                matches.append(p)
        if not matches:
            fail('NO_CARD', 'Reader has not enumerated a card yet')
        if len(matches) != 1:
            fail('IDENTITY', f'Expected one whole disk below reader, found {len(matches)}')
        p = matches[0]
        dev = Path('/dev') / p.name
        link = self.by_id / r['by_id']
        if '/' in r['by_id'] or not link.is_symlink() or link.resolve() != dev:
            fail('IDENTITY', 'by-id does not identify this disk')
        if self.read(p / 'removable') != '1':
            fail('IDENTITY', 'Disk is not removable')
        capacity = int(self.read(p / 'size') or 0) * 512
        if capacity == 0:
            fail('NO_CARD', 'Reader has not reported card capacity yet')
        if not int(r['min_capacity']) <= capacity <= int(r['max_capacity']):
            fail('IDENTITY', 'Card capacity outside configured limits')
        ds = dev.stat()
        if not stat.S_ISBLK(ds.st_mode):
            fail('IDENTITY', 'Expected a block device')
        major_minor = f'{os.major(ds.st_rdev)}:{os.minor(ds.st_rdev)}'
        if self.read(p / 'dev') != major_minor:
            fail('IDENTITY', 'Device node major/minor does not match sysfs')
        return {'device': str(dev), 'by_id': str(link), 'serial': self.serial,
                'reader_serial': r['serial'], 'usb_path': r['usb_path'],
                'vid': r['vid'], 'pid': r['pid'], 'capacity': capacity,
                'removable': True, 'card_present': capacity > 0, 'simulated': False}

    def partitions(self):
        identity = self.device()
        name = Path(identity['device']).name
        parent = (self.sysfs / 'class/block' / name).resolve()
        return sorted([{'device': f'/dev/{p.name}', 'partition': self.read(p / 'partition')}
                for p in (self.sysfs / 'class/block').glob('*')
                if (p / 'partition').exists() and p.resolve().parent == parent], key=lambda p: int(p['partition']))


def factory_sdwire_topology(control):
    read = SDWireStorage.read
    parent = control.resolve().parent
    if (read(parent / 'idVendor'), read(parent / 'idProduct')) != ('0424', '2640'):
        return False
    readers = [p for p in parent.iterdir()
               if read(p / 'idVendor') == '0424' and read(p / 'idProduct') == '4050']
    controllers = [p for p in parent.iterdir() if read(p / 'idVendor') == '0403']
    return len(readers) == 1 and len(controllers) == 1 and controllers[0].resolve() == control.resolve()


def discover_sdwire(sysfs='/sys'):
    result = []
    read = SDWireStorage.read
    for p in (Path(sysfs) / 'bus/usb/devices').glob('*'):
        ids = read(p / 'idVendor'), read(p / 'idProduct')
        configured = ids in {('04e8', '6001'), ('0403', '6001')} and read(p / 'product') == 'sd-wire'
        factory = ids == ('0403', '6015') and read(p / 'product') == 'FT200X USB I2C' and factory_sdwire_topology(p)
        if configured or factory:
            result.append({'serial': read(p / 'serial'), 'usb_path': p.name,
                           'vid': ids[0], 'pid': ids[1], 'backend': 'sdwire',
                           'product': read(p / 'product'), 'factory_identity': factory,
                           'state': 'unknown', 'supports_off': False})
    return sorted(result, key=lambda x: x['usb_path'])


def commissioned_reader_candidate(backend):
    """Propose exact topology-bound inventory, never permission to write."""
    control = backend.control_device()
    read = backend.read
    siblings = [p for p in (backend.sysfs / 'bus/usb/devices').glob('*')
                if p.resolve().parent == control.parent and read(p / 'idVendor') == '0424'
                and read(p / 'idProduct') == '4050']
    if len(siblings) != 1:
        fail('IDENTITY', 'Expected exactly one USB2640 reader sibling')
    reader = siblings[0]
    disks = [p for p in (backend.sysfs / 'class/block').glob('*')
             if not (p / 'partition').exists() and reader.resolve() in (p / 'device').resolve().parents]
    if len(disks) != 1:
        fail('IDENTITY', 'Expected exactly one whole disk for reader')
    dev = Path('/dev') / disks[0].name
    links = [p for p in backend.by_id.glob('usb-*') if p.is_symlink() and p.resolve() == dev]
    if len(links) != 1:
        fail('IDENTITY', 'Expected exactly one USB by-id for whole disk')
    capacity = int(read(disks[0] / 'size') or 0) * 512
    if capacity <= 0 or not read(reader / 'serial'):
        fail('NO_CARD', 'Reader has no card capacity or serial')
    return dict(vid=read(reader / 'idVendor'), pid=read(reader / 'idProduct'),
                serial=read(reader / 'serial'), usb_path=reader.name, by_id=links[0].name,
                min_capacity=capacity, max_capacity=capacity)


class RemovableStorage:
    """Own the lock for an entire workflow. Transitions always go through OFF.

    On errors we attempt OFF and preserve diagnostics if OFF cannot be established.
    Transactions prevent TARGET after failed cleanup. SIGKILL needs hardware failsafe.
    """
    def __init__(self, name, backend: Backend, runtime, settle=0.05, timeout=10):
        self.name, self.backend = token(name), backend
        self.runtime = Path(runtime)
        self.runtime.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.settle, self.timeout = settle, timeout
        self._lock = None
        self._needs_recovery = False
        self._identity = None
        self._transaction = False
        self._active_host = False
        self.dirty = self.runtime / f'{token(backend.serial)}.dirty'

    def __enter__(self):
        path = self.runtime / f'hil-storage-{token(self.backend.serial)}.lock'
        fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode) or os.fstat(fd).st_nlink != 1:
                fail('LOCK', 'Invalid lock file')
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException as e:
            os.close(fd)
            if isinstance(e, BlockingIOError):
                fail('LOCKED', f'{self.backend.serial} is already in use')
            raise
        self._lock = fd
        if self.dirty.exists():
            self._needs_recovery = True
            try:
                self.disconnect()
                # Explicit recover is required before a new ownership transaction.
                self._needs_recovery = True
            except BaseException:
                self.__exit__(None, None, None)
                raise
        return self

    def __exit__(self, typ, value, tb):
        try:
            if typ is not None:
                self._recover()
        finally:
            if self._lock is not None:
                os.close(self._lock)
                self._lock = None

    def _require_lock(self):
        if self._lock is None:
            fail('LOCK_REQUIRED', 'Use with storage: to own the resource')

    def _mark_dirty(self, operation):
        fd = os.open(self.dirty, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        try:
            os.write(fd, operation.encode())
            os.fsync(fd)
        finally:
            os.close(fd)
        directory = os.open(self.runtime, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)

    def _clear_dirty(self):
        self.dirty.unlink(missing_ok=True)
        directory = os.open(self.runtime, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)

    def _log(self, operation, old, new, start, result, **fields):
        record = dict(timestamp=datetime.now(timezone.utc).isoformat(),
                      storage=self.name, serial=self.backend.serial, old_state=old,
                      new_state=new, operation=operation, duration=time.monotonic()-start,
                      result=result, block_device=(self._identity or {}).get('device'),
                      image_hash=fields.pop('image_sha256', None), simulated=self.backend.simulated, **fields)
        with (self.runtime / 'operations.jsonl').open('a') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            f.write(json.dumps(record, sort_keys=True) + '\n')
            f.flush()
            os.fsync(f.fileno())

    def _recover(self):
        try:
            self.backend.switch('off')
            if self.backend.state() != 'off':
                fail('RECOVERY', 'OFF readback failed')
            self._log('recovery', 'unknown', 'off', time.monotonic(), 'ok')
        except BaseException as e:
            self._log('recovery', 'unknown', 'unknown', time.monotonic(),
                      'failed', diagnostic=str(e))
            # Do not claim safe OFF and do not erase the dirty marker.

    def _transition(self, desired):
        self._require_lock()
        start = time.monotonic()
        old = 'unknown'
        try:
            if self._needs_recovery and desired != 'off':
                fail('RECOVERY_REQUIRED', 'Previous transaction failed; inspect card then run recover')
            if not self.backend.supports_off:
                fail('OFF_UNSUPPORTED', 'This backend cannot guarantee disconnected state')
            old = self.backend.state()
            if old not in {'host', 'target', 'off'}:
                fail('UNSAFE_SWITCH', 'Unknown electrical ownership; refusing transition')
            self._mark_dirty(desired)
            if old == 'target':
                self.backend.quiesce_target()
            if old == 'host':
                self.backend.unmount()
                os.sync()
            self.backend.switch('off')
            if self.backend.state() != 'off':
                fail('UNSAFE_SWITCH', 'OFF could not be confirmed')
            time.sleep(self.settle)
            if desired != 'off':
                self.backend.switch(desired)
            if self.backend.state() != desired:
                fail('UNSAFE_SWITCH', 'Ownership readback mismatch')
            if desired == 'host':
                self.wait_for_host()
            if not self._transaction and not self._needs_recovery:
                self._clear_dirty()
            self._log('transition', old, desired, start, 'ok')
        except BaseException as e:
            self._needs_recovery = True
            self._recover()
            self._log('transition', old, 'unknown', start, 'failed', diagnostic=str(e))
            raise

    def recover(self):
        self._require_lock()
        self.disconnect()
        self._clear_dirty()
        self._needs_recovery = False

    def acquire_host(self):
        self._transition('host')

    def acquire_target(self):
        if self._active_host:
            fail('TRANSACTION', 'Cannot transfer to DUT inside host transaction')
        self._transition('target')

    def disconnect(self):
        self._transition('off')

    def wait_for_host(self):
        self._require_lock()
        end = time.monotonic() + self.timeout
        while True:
            if self.backend.state() != 'host':
                fail('UNSAFE_SWITCH', 'HOST ownership was lost')
            try:
                self._identity = self.backend.device()
                return self._identity
            except StorageError as e:
                if e.code != 'NO_CARD' or time.monotonic() >= end:
                    raise
                time.sleep(0.05)

    def wait_for_target(self):
        self._require_lock()
        if self.backend.state() != 'target':
            fail('UNSAFE_SWITCH', 'TARGET ownership not confirmed')

    def block_device(self):
        self._require_lock()
        return self.backend.device()

    def info(self):
        self._require_lock()
        state_error = None
        try:
            state = self.backend.state()
        except StorageError as e:
            state = 'unknown'
            state_error = {'code': e.code, 'message': str(e)}
        out = dict(storage=self.name, backend=self.backend.kind, serial=self.backend.serial,
                   state=state, locked=True, simulated=self.backend.simulated,
                   supports_off=self.backend.supports_off, device=None, card_present=None)
        if state_error:
            out['state_error'] = state_error
        if state in {'host', 'unknown'}:
            try:
                out.update(self.backend.device())
            except StorageError as e:
                out['device_error'] = dict(code=e.code, message=str(e))
        return out

    def partitions(self):
        self._require_lock()
        return self.backend.partitions()

    @contextlib.contextmanager
    def host(self, partition='boot'):
        self._require_lock()
        if self._transaction:
            fail('TRANSACTION', 'Nested storage transactions are unsupported')
        self._transaction = True
        start = time.monotonic()
        try:
            self.acquire_host()
            self._active_host = True
            mount = self.backend.mount(partition)
            files = HostFiles(self.backend, mount)
            try:
                yield files
            finally:
                files.active = False
            os.sync()
            self.backend.unmount()
            self._active_host = False
            self.disconnect()
            self._clear_dirty()
            self._log('host_files', 'unknown', 'off', start, 'ok')
        except BaseException as e:
            self._needs_recovery = True
            self._recover()
            self._log('host_files', 'unknown', 'unknown', start, 'failed', diagnostic=str(e))
            raise
        finally:
            self._active_host = self._transaction = False

    @staticmethod
    def image_stream(path):
        suffix = Path(path).suffix
        if suffix == '.gz' and str(path).endswith('.img.gz'):
            return gzip.open(path, 'rb')
        if suffix == '.xz' and str(path).endswith('.img.xz'):
            return lzma.open(path, 'rb')
        if suffix == '.img':
            return open(path, 'rb')
        fail('IMAGE', 'Supported images: .img, .img.gz, .img.xz')

    @classmethod
    def image_details(cls, image):
        digest, size = hashlib.sha256(), 0
        with cls.image_stream(image) as f:
            while chunk := f.read(1024 * 1024):
                digest.update(chunk)
                size += len(chunk)
        if not size:
            fail('IMAGE', 'Empty image')
        return size, digest.hexdigest()

    @staticmethod
    def bmap_for(image, size):
        candidates = [Path(str(image) + '.bmap')]
        raw = image.with_suffix('') if image.suffix in {'.gz', '.xz'} else image
        candidates += [Path(str(raw) + '.bmap'), raw.with_suffix('.bmap')]
        bmap = next((p for p in candidates if p.is_file()), None)
        tool = shutil.which('bmaptool')
        if bmap is None or tool is None:
            return None
        try:
            tree = ET.parse(bmap)
            image_size = int(tree.findtext('ImageSize'))
            block_size = int(tree.findtext('BlockSize'))
            blocks = (size + block_size - 1) // block_size
            if image_size != size or block_size <= 0:
                fail('IMAGE', 'bmap ImageSize/BlockSize mismatch')
            ranges = []
            previous = -1
            for element in tree.findall('./BlockMap/Range'):
                bounds = (element.text or '').strip().split('-')
                first, last = int(bounds[0]), int(bounds[-1])
                if len(bounds) > 2 or not 0 <= first <= last < blocks or first <= previous:
                    fail('IMAGE', 'Invalid, overlapping or out-of-order bmap range')
                ranges.append((first * block_size, min(size, (last + 1) * block_size)))
                previous = last
        except (OSError, ValueError, TypeError, ET.ParseError, ZeroDivisionError) as e:
            fail('IMAGE', f'Invalid bmap: {e}')
        return tool, bmap, ranges

    def flash(self, image, dry_run=False, verify=False):
        self._require_lock()
        image = Path(image).resolve(strict=True)
        start = time.monotonic()
        size, digest = self.image_details(image)
        bmap = self.bmap_for(image, size)
        self._transaction = True
        try:
            # A dry run may switch to HOST, but never opens a writer.
            self.acquire_host()
            identity = self.block_device()
            if size > identity['capacity']:
                fail('CAPACITY', 'Expanded image exceeds card capacity')
            plan = dict(storage=self.name, sdwire_serial=self.backend.serial,
                        usb_path=identity['usb_path'], block_device=identity['device'],
                        card_capacity=identity['capacity'], image=str(image),
                        image_size=size, image_hash=digest, dry_run=dry_run,
                        writer='bmaptool' if bmap else 'stream',
                        simulated=self.backend.simulated,
                        planned_operation=['stop DUT', 'OFF', 'HOST', 'verify identity',
                                           'unmount', 'stream write', 'flush',
                                           'verify' if verify or bmap else 'no readback', 'OFF', 'TARGET'])
            if dry_run:
                self.disconnect()
                self._clear_dirty()
                self._log('flash_dry_run', 'unknown', 'off', start, 'ok', image=str(image), image_sha256=digest)
                return plan
            self.backend.unmount()
            os.sync()
            if identity != self.block_device():
                fail('IDENTITY', 'Card identity changed before write')
            with self.backend.open_writer(identity) as out:
                if bmap:
                    self.backend.before_write()
                    tool, mapping, ranges = bmap
                    # bmaptool skips unmapped ranges. Zero them so stale card data
                    # cannot survive in image holes; readback covers every byte.
                    cursor = 0
                    for begin, end in ranges + [(size, size)]:
                        out.seek(cursor)
                        while cursor < begin:
                            if identity != self.block_device():
                                fail('IDENTITY', 'Card changed while clearing sparse gaps')
                            count = min(1024 * 1024, begin - cursor)
                            if out.write(b'\0' * count) != count:
                                fail('IO', 'Short write while clearing sparse gaps')
                            cursor += count
                        cursor = end
                    out.flush()
                    try:
                        subprocess.run([tool, 'copy', '--bmap', str(mapping), str(image),
                                        f'/proc/self/fd/{out.fileno()}'],
                                       pass_fds=(out.fileno(),), check=True,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       timeout=3600)
                    except (OSError, subprocess.SubprocessError) as e:
                        fail('IO', f'bmaptool failed; no write retry: {e}')
                    written, actual_digest = self.image_details(image)
                else:
                    actual, written = hashlib.sha256(), 0
                    with self.image_stream(image) as src:
                        while chunk := src.read(1024 * 1024):
                            if identity != self.block_device():
                                fail('IDENTITY', 'Card identity changed during write')
                            if written + len(chunk) > size:
                                fail('IMAGE', 'Image changed during operation')
                            self.backend.before_write()
                            view = memoryview(chunk)
                            while view:
                                count = out.write(view)
                                if not count:
                                    fail('IO', 'Short write')
                                view = view[count:]
                            actual.update(chunk)
                            written += len(chunk)
                    actual_digest = actual.hexdigest()
                if identity != self.block_device():
                    fail('IDENTITY', 'Card identity changed during write')
                if written != size or actual_digest != digest:
                    fail('IMAGE', 'Image changed during operation')
                out.flush()
                os.fsync(out.fileno())
                if verify or bmap:
                    out.seek(0)
                    read_hash, remaining = hashlib.sha256(), size
                    while remaining:
                        if identity != self.block_device():
                            fail('IDENTITY', 'Card identity changed during readback')
                        chunk = out.read(min(1024 * 1024, remaining))
                        if not chunk:
                            fail('VERIFY', 'Short read')
                        read_hash.update(chunk)
                        remaining -= len(chunk)
                    if read_hash.hexdigest() != digest:
                        fail('VERIFY', 'Readback SHA256 differs')
            self.acquire_target()
            self._clear_dirty()
            self._log('flash', 'unknown', 'target', start, 'ok', image=str(image), image_sha256=digest)
            return plan | {'written': size, 'verified': bool(verify or bmap), 'state': 'target'}
        except BaseException as e:
            self._needs_recovery = True
            self._recover()
            self._log('flash', 'unknown', 'unknown', start, 'failed', image=str(image),
                      image_sha256=digest, diagnostic=str(e))
            raise
        finally:
            self._transaction = False


class HostFiles:
    def __init__(self, backend, root):
        self.backend, self.root = backend, Path(root).resolve()
        self.active = True

    def copy(self, source, destination):
        if not self.active or self.backend.state() != 'host':
            fail('UNSAFE_SWITCH', 'HOST file transaction is no longer active')
        self.backend.before_copy()
        # /boot is a logical selected partition, never the host OS /boot.
        relative = str(destination).removeprefix('/boot/')
        if relative.startswith('/') or '..' in Path(relative).parts:
            fail('PATH', 'Destination must be inside selected partition')
        dst = (self.root / relative).resolve()
        if self.root not in dst.parents:
            fail('PATH', 'Destination escapes selected partition')
        dst.parent.mkdir(parents=True, exist_ok=True)
        temporary = dst.with_name(dst.name + '.hil-tmp')
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o644)
        try:
            with os.fdopen(fd, 'wb') as out, open(source, 'rb') as src:
                shutil.copyfileobj(src, out)
                out.flush()
                os.fsync(out.fileno())
            temporary.replace(dst)
        finally:
            temporary.unlink(missing_ok=True)
