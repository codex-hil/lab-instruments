"""SIMULATED: no physical SDWire, USB or real block device is modified."""
import gzip
import json
import lzma
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from labinstruments.storage import (MockRemovableStorage, RemovableStorage,
                                    SDWireStorage, StorageError, HostFiles)


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.backend = MockRemovableStorage('TEST01', self.root / 'mock', capacity=4096)
        self.storage = RemovableStorage('zynq', self.backend, self.root / 'runtime', settle=0, timeout=0)
        self.image = self.root / 'test.img'
        self.image.write_bytes(b'AI-HIL' * 100)
        self.sync = patch('labinstruments.storage.os.sync')
        self.sync.start()
        self.addCleanup(self.sync.stop)

    def test_transitions_break_before_make(self):
        with self.storage as s:
            s.acquire_host()
            s.acquire_target()
            s.acquire_host()
        self.assertEqual(self.backend.events, ['off', 'host', 'unmount', 'off', 'target',
                                             'stop_target', 'off', 'host'])

    def test_success_all_image_formats_and_readback(self):
        for suffix, opener in [('.img', open), ('.img.gz', gzip.open), ('.img.xz', lzma.open)]:
            path = self.root / ('input' + suffix)
            with opener(path, 'wb') as f:
                f.write(self.image.read_bytes())
            with self.storage as s:
                result = s.flash(path, verify=True)
                self.assertTrue(result['verified'])
                self.assertEqual(s.info()['state'], 'target')
            self.assertEqual(self.backend.card.read_bytes()[:600], self.image.read_bytes())

    def test_dry_run_never_opens_writer(self):
        with self.storage as s, patch.object(self.backend, 'open_writer', side_effect=AssertionError):
            plan = s.flash(self.image, dry_run=True)
            self.assertEqual(plan['card_capacity'], 4096)
            self.assertEqual(self.backend.state(), 'off')
        self.assertFalse(self.backend.card.exists())

    def test_flash_failure_and_interrupt_leave_off(self):
        for fault, exception in [('write', StorageError), ('interrupt', KeyboardInterrupt),
                                 ('wrong_device', StorageError), ('disappears', StorageError),
                                 ('no_card', StorageError), ('unmount', StorageError)]:
            with self.subTest(fault=fault):
                self.backend.faults = {fault}
                with self.storage as s:
                    with self.assertRaises(exception):
                        s.flash(self.image)
                    self.assertEqual(self.backend.state(), 'off')
                    with self.assertRaises(StorageError):
                        s.acquire_target()
                self.backend.faults = set()
                with self.storage as s:
                    s.recover()

    def test_mount_copy_unmount_failure(self):
        for fault in ['mount', 'copy', 'unmount']:
            with self.subTest(fault=fault):
                with self.storage as s:
                    self.backend.faults = {fault}
                    with self.assertRaises(StorageError):
                        with s.host() as sd:
                            sd.copy(self.image, '/boot/BOOT.BIN')
                    self.assertEqual(self.backend.state(), 'off')
                self.backend.faults.clear()
                with self.storage as s:
                    s.recover()

    def test_copy_success_and_path_escape(self):
        with self.storage as s:
            with s.host() as sd:
                sd.copy(self.image, '/boot/BOOT.BIN')
                self.assertEqual((sd.root / 'BOOT.BIN').read_bytes(), self.image.read_bytes())
                with self.assertRaises(StorageError):
                    sd.copy(self.image, '../host-file')
                with self.assertRaises(StorageError):
                    s.acquire_target()
            self.assertEqual(self.backend.state(), 'off')

    def test_wrong_disk_never_opened(self):
        sentinel = self.root / 'important-disk'
        sentinel.write_bytes(b'NEVER OVERWRITE')
        original = self.backend.device
        calls = 0
        def changed():
            nonlocal calls
            calls += 1
            value = original()
            if calls >= 3:
                value['device'] = str(sentinel)
            return value
        with self.storage as s, patch.object(self.backend, 'device', side_effect=changed), \
                patch.object(self.backend, 'open_writer', side_effect=AssertionError('writer called')):
            with self.assertRaises(StorageError):
                s.flash(self.image)
        self.assertEqual(sentinel.read_bytes(), b'NEVER OVERWRITE')

    def test_mock_symlink_cannot_write_host_disk(self):
        sentinel = self.root / 'important-disk'
        sentinel.write_bytes(b'NEVER OVERWRITE')
        self.backend.card.symlink_to(sentinel)
        with self.storage as s:
            with self.assertRaises(OSError):
                s.flash(self.image)
        self.assertEqual(sentinel.read_bytes(), b'NEVER OVERWRITE')

    def test_lock_collision(self):
        other = RemovableStorage('another_alias', self.backend, self.root / 'runtime')
        with self.storage:
            with self.assertRaises(StorageError) as err:
                with other:
                    pass
            self.assertEqual(err.exception.code, 'LOCKED')

    def test_killed_transaction_is_not_sent_to_target(self):
        self.storage.dirty.write_text('host-files')
        self.backend._save('host')
        with self.storage as s:
            self.assertEqual(self.backend.state(), 'off')
            self.assertTrue(self.storage.dirty.exists())
            with self.assertRaises(StorageError) as err:
                s.acquire_target()
            self.assertEqual(err.exception.code, 'RECOVERY_REQUIRED')
            s.recover()
            s.acquire_target()

    def test_capacity_rejected_before_open(self):
        self.image.write_bytes(b'x' * 4097)
        with self.storage as s, patch.object(self.backend, 'open_writer', side_effect=AssertionError):
            with self.assertRaises(StorageError) as err:
                s.flash(self.image)
            self.assertEqual(err.exception.code, 'CAPACITY')

    def test_sdwire_without_off_never_calls_usb_or_writer(self):
        backend = SDWireStorage('TEST01')
        s = RemovableStorage('real', backend, self.root / 'runtime')
        with s, patch.object(backend, 'state', side_effect=AssertionError('USB accessed')):
            for operation in [s.acquire_host, s.acquire_target, s.disconnect,
                              lambda: s.flash(self.image, dry_run=True)]:
                with self.assertRaises(StorageError) as err:
                    operation()
                self.assertIn(err.exception.code, {'OFF_UNSUPPORTED', 'RECOVERY_REQUIRED'})

    def test_backend_rejects_wrong_reader(self):
        backend = SDWireStorage('TEST01', reader={})
        with patch.object(backend, 'control_device', return_value=self.root / 'controller'):
            with self.assertRaises(StorageError) as err:
                backend.device()
            self.assertEqual(err.exception.code, 'IDENTITY')

    def test_log_has_required_fields(self):
        with self.storage as s:
            s.flash(self.image, verify=True)
        records = [json.loads(line) for line in (self.root / 'runtime/operations.jsonl').read_text().splitlines()]
        last = records[-1]
        self.assertEqual(last['operation'], 'flash')
        self.assertEqual(len(last['image_hash']), 64)
        for key in ['timestamp', 'storage', 'serial', 'old_state', 'new_state',
                    'block_device', 'duration', 'result']:
            self.assertIn(key, last)

    def test_cli_definition_of_done(self):
        cfg = self.root / 'mock.json'
        cfg.write_text(json.dumps({'storage': {'zynq': {'backend': 'mock', 'serial': 'CLI01'}}}))
        for argv in [['list'], ['zynq', 'status'], ['zynq', 'host'], ['zynq', 'target'],
                     ['zynq', 'off'], ['zynq', 'flash', str(self.image), '--dry-run']]:
            p = subprocess.run([sys.executable, '-m', 'labinstruments.storage_cli', '--json',
                                '--config', str(cfg), '--runtime', str(self.root / 'cli'), *argv],
                               capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            self.assertTrue(json.loads(p.stdout)['ok'])

class WorkflowTests(unittest.TestCase):
    setUp = StorageTests.setUp
    def test_boot_workflow_artifacts(self):
        import queue
        from labinstruments.storage_workflow import storage_boot_test
        chunks = queue.Queue()
        def receive(timeout):
            try:
                return chunks.get(timeout=timeout)
            except queue.Empty:
                return b''
        def power():
            chunks.put(b'raw preamble\r\nU-Boot 2025\r\nLinux version 6.6\r\nlogin:')
        result = storage_boot_test(self.storage, lambda: None,
                                   {str(self.image): '/boot/BOOT.BIN'}, power, receive,
                                   self.root / 'artifacts', timeout=1)
        self.assertEqual(result['result'], 'PASS')
        self.assertTrue(result['simulated'])
        self.assertIn(b'raw preamble', (self.root / 'artifacts/uart.bin').read_bytes())
        self.assertTrue((self.root / 'artifacts/result.json').exists())

    def test_boot_failure_keeps_uart_and_off(self):
        from labinstruments.storage_workflow import storage_boot_test
        import queue
        chunks = queue.Queue()
        def receive(timeout):
            try:
                return chunks.get(timeout=timeout)
            except queue.Empty:
                return b''
        result = storage_boot_test(self.storage, lambda: None, {},
                                   lambda: chunks.put(b'boot failure\r\n'), receive,
                                   self.root / 'failure', timeout=0.1)
        self.assertEqual(result['result'], 'FAIL')
        self.assertEqual(self.backend.state(), 'off')
        self.assertEqual((self.root / 'failure/uart.bin').read_bytes(), b'boot failure\r\n')

class ProcessTests(unittest.TestCase):
    setUp = StorageTests.setUp

    def worker(self):
        program = """
import sys, time
from labinstruments.storage import MockRemovableStorage, RemovableStorage
b=MockRemovableStorage('TEST01', sys.argv[1]+'/mock', capacity=4096)
s=RemovableStorage('zynq', b, sys.argv[1]+'/runtime', settle=0)
with s:
    with s.host():
        print('READY', flush=True)
        time.sleep(60)
"""
        p = subprocess.Popen([sys.executable, '-c', program, str(self.root)],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: p.kill() if p.poll() is None else None)
        self.assertEqual(p.stdout.readline().strip(), 'READY')
        return p

    def test_real_sigint_recovery(self):
        import signal
        p = self.worker()
        p.send_signal(signal.SIGINT)
        p.communicate(timeout=5)
        self.assertNotEqual(p.returncode, 0)
        self.assertEqual(self.backend.state(), 'off')
        self.assertTrue(self.storage.dirty.exists())

    def test_real_sigkill_requires_next_owner_recovery(self):
        import signal
        p = self.worker()
        p.send_signal(signal.SIGKILL)
        p.communicate(timeout=5)
        # Software cannot run cleanup after SIGKILL: explicitly do not claim OFF.
        self.assertEqual(self.backend.state(), 'host')
        with self.storage as s:
            self.assertEqual(self.backend.state(), 'off')
            with self.assertRaises(StorageError):
                s.acquire_target()
            s.recover()

    def test_cross_process_lock(self):
        p = self.worker()
        with self.assertRaises(StorageError) as err:
            with self.storage:
                pass
        self.assertEqual(err.exception.code, 'LOCKED')
        p.send_signal(__import__('signal').SIGINT)
        p.communicate(timeout=5)



class BmapTests(unittest.TestCase):
    setUp = StorageTests.setUp

    @unittest.skipUnless(__import__('shutil').which('bmaptool'), 'bmaptool not in this environment')
    def test_real_bmaptool_on_private_mock_file(self):
        # Sparse source and dirty destination exercise clearing unmapped ranges.
        self.backend.capacity = 16384
        with self.image.open('wb') as f:
            f.write(b'BOOT' * 256)
            f.seek(12000)
            f.write(b'END')
        self.backend.card.write_bytes(b'X' * 16384)
        subprocess.run(['bmaptool', 'create', '-o', str(self.image)+'.bmap', str(self.image)], check=True,
                       capture_output=True)
        with self.storage as s:
            result = s.flash(self.image)
        self.assertEqual(result['writer'], 'bmaptool')
        self.assertTrue(result['verified'])
        self.assertEqual(self.backend.card.read_bytes()[:12003], self.image.read_bytes())

    def test_bmap_outside_capacity_rejected(self):
        Path(str(self.image)+'.bmap').write_text('<bmap><ImageSize>600</ImageSize>'
            '<BlockSize>512</BlockSize><BlockMap><Range>0-99</Range></BlockMap></bmap>')
        with patch('labinstruments.storage.shutil.which', return_value='/not/executed'):
            with self.storage as s:
                with self.assertRaises(StorageError):
                    s.flash(self.image)
        self.assertFalse(self.backend.card.exists())

class IdentityTests(unittest.TestCase):
    """Synthetic sysfs with mocked stat for /dev/sdz; no physical disk access."""
    def setUp(self):
        from types import SimpleNamespace
        import stat
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.sysfs = self.root / 'sys'
        usb = self.sysfs / 'bus/usb/devices'
        block = self.sysfs / 'class/block'
        usb.mkdir(parents=True)
        block.mkdir(parents=True)
        physical = self.sysfs / 'devices/usb1/1-4'
        self.control = physical / '1-4.2'
        self.reader = physical / '1-4.1'
        physical.mkdir(parents=True)
        (physical / 'idVendor').write_text('0424')
        (physical / 'idProduct').write_text('2640')
        for path, vid, pid, serial, product in [
                (self.control, '04e8', '6001', 'CONTROL01', 'sd-wire'),
                (self.reader, '0424', '2640', 'READER01', 'SD Reader')]:
            path.mkdir(parents=True)
            for name, value in [('idVendor', vid), ('idProduct', pid), ('serial', serial), ('product', product)]:
                (path / name).write_text(value)
            (usb / path.name).symlink_to(path)
        self.disk = self.reader / '1-4.1:1.0/host0/target0/block/sdz'
        self.disk.mkdir(parents=True)
        (self.disk / 'device').symlink_to(self.disk.parent.parent)
        for name, value in [('removable', '1'), ('size', '8192'), ('dev', '8:240')]:
            (self.disk / name).write_text(value)
        (block / 'sdz').symlink_to(self.disk)
        self.by_id = self.root / 'by-id'
        self.by_id.mkdir()
        (self.by_id / 'usb-READER01').symlink_to('/dev/sdz')
        self.reader_config = dict(vid='0424', pid='2640', serial='READER01', usb_path='1-4.1',
                                  by_id='usb-READER01', min_capacity=4000000, max_capacity=5000000)
        self.backend = SDWireStorage('CONTROL01', reader=self.reader_config,
                                     sysfs=self.sysfs, by_id=self.by_id)
        original = Path.stat
        def fake_stat(path, *args, **kwargs):
            if str(path) == '/dev/sdz' and kwargs.get('follow_symlinks', True):
                return SimpleNamespace(st_mode=stat.S_IFBLK, st_rdev=os.makedev(8, 240))
            return original(path, *args, **kwargs)
        patcher = patch.object(Path, 'stat', fake_stat)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_full_stable_identity(self):
        info = self.backend.device()
        self.assertEqual(info['device'], '/dev/sdz')
        self.assertEqual(info['reader_serial'], 'READER01')
        self.assertEqual(info['capacity'], 4194304)

    def test_wrong_reader_serial(self):
        (self.reader / 'serial').write_text('ANOTHER_DISK')
        with self.assertRaises(StorageError):
            self.backend.device()

    def test_generic_upstream_hub_rejected(self):
        (self.control.parent / 'idProduct').write_text('1234')
        with self.assertRaises(StorageError):
            self.backend.device()

    def test_nonremovable_disk(self):
        (self.disk / 'removable').write_text('0')
        with self.assertRaises(StorageError):
            self.backend.device()

    def test_wrong_major_minor(self):
        (self.disk / 'dev').write_text('8:0')
        with self.assertRaises(StorageError):
            self.backend.device()

    def test_by_id_points_to_other_disk(self):
        link = self.by_id / 'usb-READER01'
        link.unlink()
        link.symlink_to('/dev/sda')
        with self.assertRaises(StorageError):
            self.backend.device()

    def test_reader_outside_sdwire_hub(self):
        self.reader_config['usb_path'] = '9-9.1'
        with self.assertRaises(StorageError):
            self.backend.device()

    def test_capacity_outside_limits(self):
        (self.disk / 'size').write_text('999999')
        with self.assertRaises(StorageError):
            self.backend.device()

    def test_multiple_controller_serials(self):
        extra = self.control.parent / '1-4.3'
        extra.mkdir()
        for field in ['idVendor', 'idProduct', 'serial', 'product']:
            (extra / field).write_text((self.control / field).read_text())
        (self.sysfs / 'bus/usb/devices/1-4.3').symlink_to(extra)
        with self.assertRaises(StorageError):
            self.backend.device()

    def test_multiple_disks(self):
        (self.sysfs / 'class/block/sdy').symlink_to(self.disk)
        with self.assertRaises(StorageError):
            self.backend.device()

    def test_generic_ftdi_rejected(self):
        (self.control / 'product').write_text('USB UART')
        with self.assertRaises(StorageError):
            self.backend.device()

    def test_sdwire_status_protocol(self):
        with patch('labinstruments.storage.run', return_value='SD connected to: TS\n'):
            self.assertEqual(self.backend.state(), 'host')
        with patch('labinstruments.storage.run', return_value='unrecognized output\n'):
            with self.assertRaises(StorageError):
                self.backend.state()


class TransactionSafetyTests(unittest.TestCase):
    setUp = StorageTests.setUp

    def test_sync_failure_keeps_off_and_blocks_target(self):
        with self.storage as storage:
            with patch('labinstruments.storage.os.sync', side_effect=OSError('sync failure')):
                with self.assertRaises(OSError):
                    with storage.host() as sd:
                        sd.copy(self.image, '/boot/BOOT.BIN')
            self.assertEqual(self.backend.state(), 'off')
            with self.assertRaises(StorageError):
                storage.acquire_target()

    def test_stale_file_transaction_cannot_be_reused(self):
        with self.storage as storage:
            with storage.host() as sd:
                sd.copy(self.image, '/boot/BOOT.BIN')
            storage.acquire_host()
            with self.assertRaises(StorageError):
                sd.copy(self.image, '/boot/another.bin')
            self.assertFalse((sd.root / 'another.bin').exists())

    def test_unconfirmed_off_never_opens_writer_or_makes_target(self):
        with self.storage as storage:
            def bad_switch(state):
                self.backend.events.append(state)
                self.backend._save('host')
            with patch.object(self.backend, 'switch', side_effect=bad_switch), \
                    patch.object(self.backend, 'open_writer', side_effect=AssertionError('writer called')):
                with self.assertRaises(StorageError):
                    storage.flash(self.image)
            self.assertNotIn('target', self.backend.events)
            records = [json.loads(line) for line in
                       (self.root / 'runtime/operations.jsonl').read_text().splitlines()]
            self.assertTrue(any(r['operation'] == 'recovery' and r['result'] == 'failed'
                                and r['new_state'] == 'unknown' for r in records))


class FactorySDWireTests(unittest.TestCase):
    setUp = IdentityTests.setUp

    def factory(self):
        (self.control / 'idVendor').write_text('0403')
        (self.control / 'idProduct').write_text('6015')
        (self.control / 'product').write_text('FT200X USB I2C')
        (self.reader / 'idProduct').write_text('4050')
        self.reader_config['pid'] = '4050'
        self.backend = SDWireStorage('CONTROL01','0403','6015',reader=self.reader_config,
                                     sysfs=self.sysfs,by_id=self.by_id)

    def test_factory_discovery_requires_paired_reader(self):
        from labinstruments.storage import discover_sdwire
        self.factory()
        result = discover_sdwire(self.sysfs)
        self.assertEqual(len(result),1)
        self.assertTrue(result[0]['factory_identity'])
        (self.reader/'idProduct').write_text('9999')
        self.assertEqual(discover_sdwire(self.sysfs),[])

    def test_factory_identity_and_unknown_state(self):
        self.factory()
        with patch('labinstruments.storage.run',side_effect=AssertionError('No sd-mux/EEPROM operation')):
            with self.assertRaises(StorageError) as error:
                self.backend.state()
        self.assertEqual(error.exception.code,'UNCOMMISSIONED_FACTORY')
        resource = RemovableStorage('factory',self.backend,self.root/'runtime')
        with resource:
            self.assertEqual(resource.info()['state'],'unknown')
            self.assertEqual(resource.info()['device'],'/dev/sdz')
            with self.assertRaises(StorageError):
                resource.acquire_host()

    def test_factory_generic_hub_is_rejected(self):
        self.factory()
        (self.control.parent/'idProduct').write_text('9999')
        with self.assertRaises(StorageError):
            self.backend.control_device()

    def test_factory_reader_config_proposal(self):
        from labinstruments.storage import commissioned_reader_candidate
        self.factory()
        proposed = commissioned_reader_candidate(self.backend)
        self.assertEqual(proposed['serial'],'READER01')
        self.assertEqual(proposed['by_id'],'usb-READER01')
        self.assertEqual(proposed['min_capacity'],4194304)
        self.backend.reader=proposed
        self.assertEqual(self.backend.device()['capacity'],4194304)


if __name__ == '__main__':
    unittest.main()
