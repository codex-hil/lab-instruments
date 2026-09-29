import base64
import copy
import unittest
from unittest.mock import patch
from labinstruments.drivers import Driver, PROFILES
from labinstruments.service import Gateway
from labinstruments.transport import select_usb
from test_core import Fake, STATE, LIMITS

class ProfileFake(Fake):
    def __init__(self,model):
        super().__init__();self.model=model
        self.values.update({'OUTP:GEN':'0','OUTP1':'0','OUTP2':'0','INP:STAT':'0','SOUR:VOLT:STAT':'0'})
    def write(self,c):
        if ' ' not in c:self.writes.append(c);return
        super().write(c)
        if c.startswith('INP '):self.values['INP:STAT']=self.values['INP']
    def query(self,c):
        if c=='*IDN?':return f'TEST,{PROFILES[self.model][0]},TEST,1.0'
        return super().query(c)

class ProfileTests(unittest.TestCase):
    def test_tbs1022_uses_shared_scope_measurements(self):
        io = ProfileFake('tbs1022')
        io.values['MEASU:IMMED:VALUE'] = '1.234E3'
        driver = Driver(io, 'tbs1022', 'TEST')
        self.assertEqual(driver.read('frequency', 2), '1.234E3')
        self.assertEqual(io.writes, ['HEADER OFF', 'MEASU:IMMED:SOURCE1 CH2',
                                     'MEASU:IMMED:TYPE FREQ'])
        with self.assertRaises(ValueError):
            driver.read('frequency', 3)
        with self.assertRaises(ValueError):
            Driver(io, 'tbs1022', 'WRONG').identify()

    def test_active_profiles_complete_apply(self):
        awg={'channel':2,'enable':True,'frequency':1000,'vpp':.1,'offset':0}
        awgl={'allow_output':True,'frequency_min':1,'frequency_max':1e6,'vpp_min':.01,'vpp_max':1,'voltage_peak_max':2,'current_max':.04,'power_max':.1}
        rf={'channel':1,'enable':True,'frequency':1e8,'dbm':-20}
        rfl={'allow_output':True,'frequency_min':1e6,'frequency_max':1e9,'dbm_min':-120,'dbm_max':-10,'power_max':.001}
        load={'channel':1,'enable':True,'current':.1}
        loadl={'allow_output':True,'current_min':.001,'current_max':.5,'power_max':5,'external_voltage_max':10}
        for model,params,limits in [('ngp814',STATE,LIMITS),('b2910bl',STATE,LIMITS),('smb100a',rf,rfl),('afg1062',awg,awgl),('mp750288',awg,awgl),('8550',load,loadl)]:
            with self.subTest(model=model):
                io=ProfileFake(model);result=Driver(io,model,'TEST').apply(params,limits)
                self.assertTrue(result['state']['enable'])
                self.assertGreater(len(io.writes), 3)
    def test_multicomp_textual_modulation_state(self):
        class TextMode(ProfileFake):
            def query(self, command):
                if command.endswith(':MOD:STAT?'):return 'OFF'
                return super().query(command)
        io=TextMode('mp750288')
        params={'channel':1,'enable':True,'frequency':1000,'vpp':.1,'offset':0}
        limits={'allow_output':True,'frequency_min':1,'frequency_max':1e6,'vpp_min':.01,'vpp_max':1,'voltage_peak_max':2,'current_max':.04,'power_max':.1}
        result=Driver(io,'mp750288','TEST').apply(params,limits)
        self.assertTrue(result['state']['enable'])

    def test_smu_fetch_no_trigger(self):
        io=ProfileFake('b2910bl');io.values['FETC:VOLT']='1'
        self.assertEqual(Driver(io,'b2910bl','TEST').read('voltage'),'1')
        self.assertEqual(io.writes,[])
    def test_reconnect_resolves_new_node(self):
        config={'serial':'ABC','vendor':'0699'}
        with patch('labinstruments.transport.usb_devices',return_value=[{'serial':'ABC','vendor':'0699','path':'/dev/usbtmc3'}]):
            self.assertEqual(select_usb(config),'/dev/usbtmc3')
        with patch('labinstruments.transport.usb_devices',return_value=[{'serial':'ABC','vendor':'0699','path':'/dev/usbtmc0'}]):
            self.assertEqual(select_usb(config),'/dev/usbtmc0')
    def test_missing_and_duplicate_usb_fail_closed(self):
        for devices in [[],[{'serial':'A','path':'a'},{'serial':'A','path':'b'}]]:
            with patch('labinstruments.transport.usb_devices',return_value=devices),self.assertRaises(OSError):select_usb({'serial':'A'})
    def test_unstable_usb_path_not_supported(self):
        with self.assertRaises(ValueError):select_usb({'path':'/dev/usbtmc0'})
    def test_gateway_binary_and_explicit_reply(self):
        class USB:
            def __init__(self,config):pass
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def transaction(self,data,reply):return b'\x00\xff\n' if reply else b''
        gateway=Gateway({'slots':{'usb1':{'serial':'A'}}},USB)
        result=gateway.transaction({'slot':'usb1','data':base64.b64encode(b'CURVE?\n').decode(),'reply':True})
        self.assertEqual(base64.b64decode(result['data']),b'\x00\xff\n')
        with self.assertRaises(ValueError):gateway.transaction({'slot':'../../etc/passwd','data':'AA==','reply':True})
