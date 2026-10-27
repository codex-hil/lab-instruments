"""SIMULATED SDWire HOST/DUT ownership; no physical USB or block writes."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from labinstruments.storage import MockRemovableStorage, StorageError
from labinstruments.storage_sdwire import SDWireSession
from labinstruments.sdwire_ftdi import ftx_checksum, cbus0_iomode_image


class GuardedMock(MockRemovableStorage):
    supports_off = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._save('target')
        self.stopped = False
        self.stop_fails = False

    def require_stopped(self):
        if not self.stopped:
            raise StorageError('DUT_NOT_QUIESCED', 'simulated stop readback failure')

    def quiesce_target(self):
        self.events.append('stop_verify')
        if not self.stop_fails:
            self.stopped = True
        self.require_stopped()

    def switch(self, state):
        self.require_stopped()
        if state not in ('host','target'):
            raise AssertionError('No OFF on SDWire')
        self.events.append(state)
        self._save(state)


class DirectSessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.backend = GuardedMock('SDWIRE_TEST',self.root/'mock',capacity=4096)
        self.storage = SDWireSession('test',self.backend,self.root/'runtime',settle=0,timeout=0)
        self.image = self.root/'input.img'
        self.image.write_bytes(b'qualified image'*32)
        sync=patch('labinstruments.storage_sdwire.os.sync');sync.start();self.addCleanup(sync.stop)

    def test_success_stays_stopped_until_caller_releases(self):
        with self.storage as s:
            result=s.flash(self.image)
        self.assertTrue(result['verified'])
        self.assertTrue(self.backend.stopped)
        self.assertEqual(self.backend.state(),'target')
        self.assertNotIn('off',self.backend.events)
        self.assertEqual(self.backend.card.read_bytes()[:self.image.stat().st_size],self.image.read_bytes())

    def test_stop_readback_failure_never_switches(self):
        self.backend.stop_fails=True
        with self.assertRaises(StorageError),self.storage as s:
            s.acquire_host()
        self.assertEqual(self.backend.state(),'target')
        self.assertNotIn('host',self.backend.events)

    def test_write_failure_retains_host_and_dirty_marker(self):
        self.backend.faults.add('write')
        with self.assertRaises(StorageError),self.storage as s:
            s.flash(self.image)
        self.assertEqual(self.backend.state(),'host')
        self.assertTrue(self.backend.stopped)
        self.assertTrue(self.storage.dirty.exists())

    def test_explicit_recovery_after_failed_previous_session(self):
        self.backend.faults.add('write')
        with self.assertRaises(StorageError),self.storage as s:s.flash(self.image)
        self.backend.faults.clear()
        next_session=SDWireSession('test',self.backend,self.root/'runtime',settle=0,timeout=0)
        with next_session as s:
            with self.assertRaisesRegex(StorageError,'Previous|Inspect'):s.acquire_target()
            s.recover()
            s.flash(self.image)
        self.assertEqual(self.backend.state(),'target')

    def test_dry_run_keeps_host_without_writer(self):
        with self.storage as s,patch.object(self.backend,'open_writer',side_effect=AssertionError):
            result=s.flash(self.image,dry_run=True)
        self.assertEqual(result['state'],'host')
        self.assertFalse(self.backend.card.exists())
        events=[json.loads(line) for line in (self.root/'runtime/operations.jsonl').read_text().splitlines()]
        self.assertFalse(any(row['new_state']=='off' for row in events))

    def test_unknown_controller_state_does_not_select_dut(self):
        self.backend._save('unknown')
        with self.assertRaises(StorageError),self.storage as s:s.acquire_target()
        self.assertNotIn('target',self.backend.events)


class ControllerImageTests(unittest.TestCase):
    def image(self):
        raw=bytearray((i*31+7)&255 for i in range(256))
        raw[0x1a]=15  # Factory I2C function, not a mux GPIO.
        raw[-2:]=ftx_checksum(raw)
        return bytes(raw)

    def test_preserves_every_byte_except_cbus0_and_checksum(self):
        original=self.image();updated=cbus0_iomode_image(original)
        self.assertEqual(updated[0x1a],8)
        self.assertEqual(updated[-2:],ftx_checksum(updated))
        self.assertTrue(all(original[i]==updated[i] for i in range(256) if i not in (0x1a,254,255)))

    def test_bad_original_checksum_never_produces_write_image(self):
        raw=bytearray(self.image());raw[0]^=1
        with self.assertRaisesRegex(StorageError,'checksum'):cbus0_iomode_image(raw)

    def test_user_region_is_excluded_but_factory_region_is_included(self):
        raw=bytearray(self.image());old=ftx_checksum(raw)
        raw[0x30]^=1
        self.assertEqual(old,ftx_checksum(raw))
        raw[0x80]^=1
        self.assertNotEqual(old,ftx_checksum(raw))


if __name__=='__main__':unittest.main()
