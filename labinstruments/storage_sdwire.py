"""SDWire v1 HOST/DUT sessions with a verified, continuously held DUT guard.

Unlike the isolated-storage API, this backend has no OFF. Recovery retains
HOST and the DUT must remain stopped; releasing reset/power is a caller action.
"""
import os
import stat
import time
from .storage import SDWireStorage, RemovableStorage, fail


class GuardedSDWire(SDWireStorage):
    """Controller must provide commissioned state()/select() operations.

    Guard callbacks must stop the actual DUT and verify that it stays stopped.
    A boolean configuration flag is deliberately insufficient.
    """
    def __init__(self, *args, transport, stop_target, target_stopped, **kwargs):
        super().__init__(*args, **kwargs)
        self.transport = transport
        self.stop_target = stop_target
        self.target_stopped = target_stopped

    def quiesce_target(self):
        self.stop_target()
        self.require_stopped()

    def require_stopped(self):
        if self.target_stopped() is not True:
            fail('DUT_NOT_QUIESCED', 'DUT stop/reset readback failed')

    def state(self):
        self.control_device()
        return self.transport.state()

    def switch(self, state):
        if state not in {'host', 'target'}:
            fail('OFF_UNSUPPORTED', 'SDWire v1 supports HOST/DUT only')
        self.require_stopped()
        self.control_device()
        self.transport.select(state)
        if self.state() != state:
            fail('UNSAFE_SWITCH', 'SDWire selection readback mismatch')

    def unmount(self):
        # Do not silently unmount another user's filesystem. Caller can unmount
        # explicitly before this operation and repeat identification.
        device = self.device()['device']
        devices = [device] + [p['device'] for p in self.partitions()]
        numbers = {f'{os.major(os.stat(p).st_rdev)}:{os.minor(os.stat(p).st_rdev)}' for p in devices}
        for row in open('/proc/self/mountinfo'):
            if row.split()[2] in numbers:
                fail('MOUNTED', 'Unmount SDWire filesystems before switching/writing')

    def before_write(self):
        self.require_stopped()
        if self.state() != 'host':
            fail('UNSAFE_SWITCH', 'SDWire lost HOST selection')

    def device(self):
        self.require_stopped()
        return super().device()

    def mount(self, partition):
        fail('UNSUPPORTED', 'Guarded SDWire currently supports whole-image flashing, not mounted file transactions')

    def open_writer(self, identity):
        self.before_write()
        self.unmount()
        if identity != self.device():
            fail('IDENTITY', 'SDWire identity changed before opening writer')
        fd = os.open(identity['device'], os.O_RDWR | os.O_NOFOLLOW | os.O_EXCL)
        try:
            info = os.fstat(fd)
            if not stat.S_ISBLK(info.st_mode):
                fail('IDENTITY', 'Writer is not a block device')
            expected = self.read(self.sysfs/'class/block'/os.path.basename(identity['device'])/'dev')
            if expected != f'{os.major(info.st_rdev)}:{os.minor(info.st_rdev)}' or identity != self.device():
                fail('IDENTITY', 'Opened writer does not match verified reader')
            return os.fdopen(fd, 'r+b', buffering=0)
        except BaseException:
            os.close(fd)
            raise


class SDWireSession(RemovableStorage):
    """Reuse identity, lock, streaming and verification; never claim OFF."""
    @staticmethod
    def bmap_for(image, size):
        # The streaming path rechecks the DUT guard between blocks. Do not
        # delegate an uninterrupted write to an external bmap process.
        return None

    def _transition(self, desired):
        self._require_lock()
        if desired == 'off':
            fail('OFF_UNSUPPORTED', 'Use retain_host(); SDWire has no OFF')
        if self._needs_recovery:
            fail('RECOVERY_REQUIRED', 'Inspect failed transaction before explicit recovery')
        start = time.monotonic()
        old = 'unknown'
        try:
            self.backend.quiesce_target()
            old = self.backend.state()
            if old not in {'host', 'target'}:
                fail('UNSAFE_SWITCH', 'Controller is not commissioned')
            self._mark_dirty(desired)
            if old == 'host':
                self.backend.unmount()
                os.sync()
            self.backend.switch(desired)
            if desired == 'host':
                self.wait_for_host()
            if not self._transaction:
                self._clear_dirty()
            self._log('transition', old, desired, start, 'ok', isolation='none', dut_stopped=True)
        except BaseException as exc:
            self._needs_recovery = True
            self._recover()
            self._log('transition', old, 'unknown', start, 'failed', diagnostic=str(exc))
            raise

    def _recover(self):
        try:
            self.backend.quiesce_target()
            if self.backend.state() != 'host':
                self.backend.switch('host')
            self.backend.require_stopped()
            self._log('recovery', 'unknown', 'host', time.monotonic(), 'ok', isolation='none', dut_stopped=True)
        except BaseException as exc:
            self._log('recovery', 'unknown', 'unknown', time.monotonic(), 'failed', diagnostic=str(exc))

    def retain_host(self):
        self._transition('host')

    def disconnect(self):
        # Parent dry-run cleanup retains HOST rather than pretending to isolate.
        if self._needs_recovery:
            self.backend.quiesce_target()
            self.backend.switch('host')
            self.wait_for_host()
        else:
            self.retain_host()

    def _log(self, operation, old, new, start, result, **fields):
        # Parent isolated-storage cleanup labels must reflect actual capability.
        if new == 'off':
            new = 'host'
        fields['isolation'] = 'none'
        super()._log(operation, old, new, start, result, **fields)

    def recover(self):
        self._require_lock()
        self.backend.quiesce_target()
        self.backend.switch('host')
        self.wait_for_host()
        self._clear_dirty()
        self._needs_recovery = False

    def flash(self, image, dry_run=False, verify=True):
        # Full readback is mandatory for real SDWire writes.
        result = super().flash(image, dry_run=dry_run, verify=True)
        result['planned_operation'] = ['stop and verify DUT', 'HOST', 'verify identity',
            'reject mounted card', 'stream write', 'fsync', 'full readback', 'DUT while stopped']
        result['isolation'] = 'none'
        if dry_run:
            result['state'] = 'host'
        return result
