"""6487 source protocol regression; no hardware or HV output required."""
import unittest
from labinstruments.drivers import Driver
from labinstruments.service import Controller
from test_profiles import ProfileFake

LIMITS = dict(allow_output=True, voltage_min=-500, voltage_max=500,
              current_min=25e-6, current_max=.025, power_max=1.25)
STATE = dict(channel=1, enable=False, voltage=500, current=25e-6)

class PicoFake(ProfileFake):
    def __init__(self):
        super().__init__('6487')
        self.values.update({'SOUR:VOLT:INT:FAIL':'0', 'SOUR:VOLT:SWE:STAT':'0'})
    def write(self, command):
        super().write(command)
        if command == 'SOUR:VOLT:SWE:ABOR': self.values['SOUR:VOLT:SWE:STAT'] = '0'

class PicoTests(unittest.TestCase):
    def test_range_selection_and_off_by_request(self):
        for voltage, expected in [(0,10),(-10,10),(10.01,50),(-50,50),(50.01,500),(-500,500),(500,500)]:
            with self.subTest(voltage=voltage):
                io=PicoFake()
                result=Driver(io,'6487','TEST').apply(dict(STATE,voltage=voltage),LIMITS)
                self.assertEqual(result['readback']['SOUR:VOLT:RANG?'],expected)
                self.assertEqual(result['state']['voltage'],voltage)
                self.assertEqual(io.writes[:2],['SOUR:VOLT:SWE:ABOR','SOUR:VOLT:STAT OFF'])
                self.assertNotIn('SOUR:VOLT:STAT ON',io.writes)
                self.assertFalse(any(c.startswith('SOUR:VOLT:INT ') for c in io.writes))

    def test_invalid_requests_do_not_touch_instrument(self):
        for change in [dict(voltage=500.1),dict(voltage=-501),dict(current=.001),dict(current=.025),
                       dict(current=0),dict(voltage=float('nan')),dict(voltage=True),dict(channel=2)]:
            io=PicoFake()
            with self.subTest(change=change),self.assertRaises(ValueError):
                Driver(io,'6487','TEST').apply(dict(STATE,**change),dict(LIMITS,voltage_min=-1000,voltage_max=1000,power_max=100))
            self.assertEqual(io.writes,[])

    def test_supported_limits_and_enable(self):
        for voltage, current in [(500,25e-6),(500,250e-6),(500,.0025),(10,.025)]:
            io=PicoFake()
            result=Driver(io,'6487','TEST').apply(dict(STATE,enable=True,voltage=voltage,current=current),LIMITS)
            self.assertEqual(result['state']['current'],current)
            self.assertEqual(io.writes[-1],'SOUR:VOLT:STAT ON')

    def test_policy_blocks_enable_voltage_and_power(self):
        for limits in [dict(LIMITS,allow_output=False),dict(LIMITS,voltage_max=10),dict(LIMITS,power_max=.001)]:
            io=PicoFake()
            with self.assertRaises(ValueError):Driver(io,'6487','TEST').apply(dict(STATE,enable=True),limits)
            self.assertEqual(io.writes,[])

    def test_interlock_failure_prevents_enable(self):
        for status in ['1','ON','unknown']:
            io=PicoFake();io.values['SOUR:VOLT:INT:FAIL']=status
            with self.assertRaises(OSError):Driver(io,'6487','TEST').apply(dict(STATE,enable=True),LIMITS)
            self.assertNotIn('SOUR:VOLT:STAT ON',io.writes)
            self.assertEqual(io.writes[-1],'SOUR:VOLT:STAT OFF')

    def test_readback_mismatch_and_timeout_prevent_enable(self):
        for bad_command in ['SOUR:VOLT?', 'SOUR:VOLT:ILIM?', 'SOUR:VOLT:RANG?', 'SOUR:VOLT:SWE:STAT?', 'SOUR:VOLT:INT:FAIL?']:
            class Bad(PicoFake):
                def query(self, command):
                    if command == bad_command: raise TimeoutError('lost readback')
                    return super().query(command)
            io=Bad()
            with self.assertRaises(TimeoutError):Driver(io,'6487','TEST').apply(dict(STATE,enable=True),LIMITS)
            self.assertNotIn('SOUR:VOLT:STAT ON',io.writes)
            self.assertEqual(io.values['SOUR:VOLT:STAT'],'0')
        io=PicoFake();io.bad_readback=True
        with self.assertRaises(OSError):Driver(io,'6487','TEST').apply(dict(STATE,enable=True),LIMITS)
        self.assertNotIn('SOUR:VOLT:STAT ON',io.writes)

    def test_state_read_is_non_mutating(self):
        io=PicoFake();io.values.update({'SOUR:VOLT':'500','SOUR:VOLT:ILIM':'0.000025','SOUR:VOLT:RANG':'500'})
        result=Driver(io,'6487','TEST').read('source_state')
        self.assertEqual(result['voltage_setpoint_v'],'500');self.assertEqual(io.writes,[])

    def test_controller_requires_identity_and_commissioning(self):
        spec=dict(model='6487',transport=dict(kind='tcp'),limits=LIMITS)
        with self.assertRaises(ValueError):Controller({'devices':{'pico':spec}})
        spec['serial']='TEST'
        controller=Controller({'devices':{'pico':spec}},lambda _: self.fail('uncommissioned I/O'))
        with self.assertRaises(ValueError):controller.call('pico','apply',STATE)
