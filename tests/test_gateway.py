"""Gateway hotplug regressions using simulated USB enumeration and kernel I/O."""
import base64
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import urllib.request
import urllib.error
import unittest
from unittest.mock import patch

from labinstruments.service import Gateway, make_server
from labinstruments.transport import select_usb


def device(index, path=None):
    return dict(path=path or f'/dev/usbtmc{index}', topology=f'1-1.{index+1}',
                serial=f'SN{index}', vendor='0699', product_id='0353', model='Scope')


def body(slot='usb1'):
    return dict(slot=slot, data=base64.b64encode(b'*IDN?\n').decode(), reply=True)


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.devices = [device(i) for i in range(4)]
        self.cfg = {'slots': {f'usb{i+1}': {'serial': f'SN{i}', 'delay': 0}
                              for i in range(4)}}
        self.gateway = Gateway(self.cfg)

    def test_four_slots_and_ambiguous_status(self):
        with patch('labinstruments.service.usb_devices', return_value=self.devices):
            self.assertTrue(all(s['connected'] for s in self.gateway.snapshot()['slots'].values()))
            self.devices.append(device(0, '/dev/usbtmc9'))
            slot = self.gateway.snapshot()['slots']['usb1']
            self.assertEqual(slot['state'], 'ambiguous')
            self.assertFalse(slot['connected'])
        with patch('labinstruments.transport.usb_devices', return_value=self.devices):
            with self.assertRaises(OSError):
                select_usb({'serial': 'SN0'})
            self.assertEqual(select_usb({'topology': '1-1.2'}), '/dev/usbtmc1')

    def test_hotplug_renumbering_and_no_retry(self):
        def ioctl(fd, request, value, *args):
            if args:
                value[0] = 1  # USBTMC EOM
        with patch('labinstruments.transport.usb_devices', side_effect=lambda: self.devices), \
             patch('labinstruments.service.usb_devices', side_effect=lambda: self.devices), \
             patch('os.open', return_value=42) as opened, patch('os.close') as closed, \
             patch('fcntl.flock'), patch('fcntl.ioctl', side_effect=ioctl), \
             patch('os.write', return_value=6) as write, patch('os.read', return_value=b'ID\n') as read:
            for name in self.cfg['slots']:
                self.assertEqual(self.gateway.transaction(body(name))['data'], 'SUQK')
            read.side_effect = OSError('disconnected during read')
            with self.assertRaises(OSError):
                self.gateway.transaction(body())
            self.assertEqual(write.call_count, 5)  # No retry of uncertain command.
            self.assertEqual(closed.call_count, 5)
            self.devices.pop(0)
            self.assertEqual(self.gateway.snapshot()['slots']['usb1']['state'], 'disconnected')
            with self.assertRaises(OSError):
                self.gateway.transaction(body())
            self.assertEqual(write.call_count, 5)
            self.devices.append(device(0, '/dev/usbtmc8'))
            read.side_effect = None
            self.gateway.transaction(body())
            opened.assert_called_with('/dev/usbtmc8', 2)
            self.assertIsNone(self.gateway.snapshot()['slots']['usb1']['status']['error'])
            self.assertEqual(closed.call_count, 6)

    def test_invalid_selectors_rejected_at_startup(self):
        for spec in ({}, {'vendor': '0699'}, {'serial': ''}, {'topology': None}):
            with self.subTest(spec=spec), self.assertRaises(ValueError):
                Gateway({'slots': {'bad': spec}})

    def test_identify_metrics_and_bounded_history(self):
        from unittest.mock import MagicMock
        io = MagicMock()
        io.__enter__.return_value = io
        io.transaction.return_value = b'TEKTRONIX,TBS1022,C012657,1.0\n'
        gateway = Gateway(self.cfg, lambda _: io)
        result = gateway.identify({'slot': 'usb1'})
        self.assertEqual(result['identity'], 'TEKTRONIX,TBS1022,C012657,1.0')
        io.transaction.assert_called_once_with(b'*IDN?\n', True)
        io.transaction.side_effect = OSError('USB unplugged')
        with self.assertRaises(OSError):
            gateway.identify({'slot': 'usb1'})
        with patch('labinstruments.service.usb_devices', return_value=self.devices):
            snapshot = gateway.snapshot()
        state = snapshot['slots']['usb1']['status']
        self.assertEqual(state['transactions'], 2)
        self.assertEqual(state['failures'], 1)
        self.assertIn('last_ok', state)
        self.assertEqual(state['identity'], result['identity'])
        self.assertEqual(snapshot['events'][0]['error'], 'USB unplugged')
        self.assertIsNone(snapshot['gateway']['active_slot'])
        io.transaction.side_effect = None
        for _ in range(45):
            gateway.transaction(body())
        self.assertEqual(len(gateway.events), 40)
        self.assertIsNone(gateway.status['usb1']['error'])
        self.assertNotIn('data', gateway.events[0])

    def test_busy_gateway_status_remains_responsive(self):
        from unittest.mock import MagicMock
        entered, release = threading.Event(), threading.Event()
        io = MagicMock()
        io.__enter__.return_value = io
        def transaction(*args):
            entered.set()
            if not release.wait(3):
                raise TimeoutError('test did not release transport')
            return b'ID\n'
        io.transaction.side_effect = transaction
        gateway = Gateway(self.cfg, lambda _: io)
        failures = []
        def run():
            try: gateway.identify({'slot': 'usb1'})
            except Exception as error: failures.append(error)
        thread = threading.Thread(target=run)
        thread.start()
        try:
            self.assertTrue(entered.wait(2))
            with patch('labinstruments.service.usb_devices', return_value=self.devices):
                self.assertEqual(gateway.snapshot()['gateway']['active_slot'], 'usb1')
            with self.assertRaisesRegex(OSError, 'busy; no command sent'):
                gateway.transaction(body('usb2'))
            io.transaction.assert_called_once()
        finally:
            release.set()
            thread.join(4)
        self.assertEqual(failures, [])
        self.assertFalse(thread.is_alive())

    def test_invalid_payload_never_opens_usb(self):
        with patch('os.open') as opened:
            for changes in ({'data': ''}, {'data': '?!'}, {'data': 3}, {'slot': []}, {'reply': 1}):
                with self.subTest(changes=changes), self.assertRaises(ValueError):
                    self.gateway.transaction(dict(body(), **changes))
            opened.assert_not_called()


class GatewayHTTPTests(unittest.TestCase):
    def test_status_auth_and_transaction(self):
        class FakeUSB:
            def __init__(self, config): pass
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def transaction(self, data, reply): return b'ID\n'
        with tempfile.TemporaryDirectory() as tmp:
            token = Path(tmp) / 'token'
            token.write_text('x' * 40)
            cfg = dict(mode='usb-gateway', listen=['127.0.0.1', 0],
                       token_file=str(token), slots={'usb1': {'serial': 'SN0'}})
            server = make_server(cfg, Gateway(cfg, FakeUSB), development=True)
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            url = f'http://127.0.0.1:{server.server_port}'
            try:
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(url + '/v1/status')
                self.assertEqual(error.exception.code, 401)
                with patch('labinstruments.service.usb_devices', return_value=[device(0)]):
                    request = urllib.request.Request(url + '/v1/status',
                              headers={'Authorization': 'Bearer ' + 'x' * 40})
                    with urllib.request.urlopen(request) as response:
                        self.assertEqual(json.load(response)['slots']['usb1']['state'], 'connected')
                request = urllib.request.Request(url + '/v1/transaction', json.dumps(body()).encode(),
                          {'Authorization': 'Bearer ' + 'x' * 40})
                with urllib.request.urlopen(request) as response:
                    self.assertEqual(json.load(response), {'data': 'SUQK'})
                request = urllib.request.Request(url + '/v1/identify', json.dumps({'slot': 'usb1'}).encode(),
                          {'Authorization': 'Bearer ' + 'x' * 40})
                with urllib.request.urlopen(request) as response:
                    self.assertEqual(json.load(response), {'identity': 'ID'})
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

    def test_udev_topology_rule_and_invalid_selector(self):
        script = str(Path(__file__).resolve().parents[1] / 'scripts' / 'udev-rule.py')
        command = [sys.executable, script, '--vendor', '0699', '--product', '0353', '--topology']
        result = subprocess.run(command + ['1-1.2'], capture_output=True, text=True, check=True)
        self.assertIn('KERNELS=="1-1.2"', result.stdout)
        self.assertIn('GROUP="labinst", MODE="0660"', result.stdout)
        result = subprocess.run(command + ['*'], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')


if __name__ == '__main__':
    unittest.main()
