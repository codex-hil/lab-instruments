import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('plugctl', Path(__file__).parents[1]/'plugctl.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class LeaseTests(unittest.TestCase):
    def test_reservation_and_control_boundary(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(m, 'ROOT', Path(tmp)), patch.object(m, 'publish') as pub:
            def args(action, token=None):
                return SimpleNamespace(action=action, owner='test-thread', token=token, timeout=1)
            token = m.execute(args('reserve'))['token']
            with self.assertRaisesRegex(ValueError, 'LEASE_BUSY'):
                m.execute(args('reserve'))
            with self.assertRaisesRegex(ValueError, 'LEASE_REQUIRED'):
                m.execute(args('off', 'wrong'))
            pub.assert_not_called()
            identity = json.dumps([{'ieee_address':m.DEVICE, 'manufacturer':'_TZ3000_xzhnra8x', 'friendly_name':m.DEVICE}])
            with patch.object(m, 'run', side_effect=['active', identity]):
                result = m.execute(args('off', token))
            pub.assert_called_once_with('/set', {'state':'OFF'})
            self.assertFalse(result['physical_state_confirmed'])
            with patch.object(m, 'run', side_effect=['active', '[]']):
                with self.assertRaisesRegex(ValueError, 'IDENTITY_MISMATCH'):
                    m.execute(args('on', token))
            self.assertEqual(pub.call_count, 1)
            m.execute(args('release', token))
            self.assertIsNone(m.execute(args('reservation'))['lease'])
            with self.assertRaisesRegex(ValueError, 'LEASE_REQUIRED'):
                m.execute(args('on', token))

if __name__ == '__main__':
    unittest.main()
