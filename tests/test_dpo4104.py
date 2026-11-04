import unittest
from labinstruments.drivers import Driver, PROFILES
from test_profiles import ProfileFake

class DPOTests(unittest.TestCase):
    def test_profile_and_four_channels(self):
        self.assertEqual(PROFILES['dpo4104'], ('DPO4104','scope',4,4000))
        for ch in range(1,5):
            for op, mode in [('frequency','FREQ'),('vpp','PK2PK')]:
                io=ProfileFake('dpo4104');io.values['MEASU:IMMED:VALUE']='0.04'
                self.assertEqual(Driver(io,'dpo4104','TEST').read(op,ch),'0.04')
                self.assertEqual(io.writes,['HEADER OFF',f'MEASU:IMMED:SOURCE1 CH{ch}',f'MEASU:IMMED:TYPE {mode}'])
    def test_wrong_identity_and_channel_no_mutation(self):
        for model, serial, channel in [('mso4104','TEST',1),('dpo4104','WRONG',1),('dpo4104','TEST',5)]:
            io=ProfileFake(model)
            with self.assertRaises(ValueError):Driver(io,'dpo4104',serial).read('vpp',channel)
            self.assertEqual(io.writes,[])
    def test_tcp_padding(self):
        io=ProfileFake('dpo4104');io.config={'kind':'tcp'}
        Driver(io,'dpo4104')
        self.assertEqual(io.config['read_padding'],'\r')
