import unittest
from labinstruments.drivers import Driver
from test_profiles import ProfileFake

class XDMTests(unittest.TestCase):
    def test_read_only_main_display(self):
        io=ProfileFake('xdm2041');io.values.update({'MEAS1':'-9.06E-05','FUNC1':'"VOLT"'})
        d=Driver(io,'xdm2041','TEST')
        self.assertEqual(d.read('reading'),'-9.06E-05')
        self.assertEqual(d.read('function'),'"VOLT"')
        self.assertEqual(io.writes,[])
    def test_wrong_serial_channel_and_unsupported(self):
        io=ProfileFake('xdm2041')
        with self.assertRaises(ValueError):Driver(io,'xdm2041','WRONG').read('reading')
        with self.assertRaises(ValueError):Driver(io,'xdm2041','TEST').read('reading',2)
        with self.assertRaises(ValueError):Driver(io,'xdm2041','TEST').read('voltage')
        self.assertEqual(io.writes,[])
