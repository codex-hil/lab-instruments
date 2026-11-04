import threading
import unittest
from labinstruments.drivers import Driver
from labinstruments.fra_math import acquisition_plan


class IO:
    def __init__(self):self.commands=[];self.channel=1;self.running=False;self.clip=False
    def write(self,c):
        self.commands.append(c)
        if c.startswith('DATA:SOURCE CH'):self.channel=int(c[-1])
    def query(self,c):
        self.commands.append(c)
        answers={'ACQ:MODE?':'SAMPLE','ACQ:STATE?':'1' if self.running else '0','ACQ:STOPAFTER?':'SEQUENCE',
            'HOR:SAMPLERATE?':'62500','HOR:RECORDLENGTH?':'1000','HOR:SCALE?':'.0016','WFMOUTPRE:XINCR?':'.000016',
            'WFMOUTPRE:XZERO?':'-.008','WFMOUTPRE:PT_OFF?':'2','WFMOUTPRE:YMULT?':'.01','WFMOUTPRE:YOFF?':'3','WFMOUTPRE:YZERO?':'.1',
            'WFMOUTPRE:XUNIT?':'"s"','WFMOUTPRE:YUNIT?':'"V"'}
        if c in answers:return answers[c]
        if c.endswith(':COUP?'):return 'DC'
        if c.endswith(':TER?'):return '1000000'
        if c.endswith(':SCALE?'):return '.05'
        if c.endswith(':PROBE:GAIN?'):return '1'
        raise AssertionError(c)
    def transaction(self,c):
        self.commands.append(c)
        payload=bytes([127 if self.clip else self.channel*10])*1000
        return b'#41000'+payload+b'\n'


class ScopeTests(unittest.TestCase):
    def ready(self):
        io=IO();d=Driver(io,'mso4104');d.configure_acquisition([1,2],acquisition_plan(1000),.05);return d,io
    def test_scaling_and_same_stopped_record(self):
        d,io=self.ready();waves=d.acquire_waveforms()
        self.assertAlmostEqual(waves[1]['values'][0],.17)
        self.assertAlmostEqual(waves[2]['values'][0],.27)
        self.assertAlmostEqual(waves[1]['t0_s'],-.008032)
        self.assertEqual(waves[1]['dt_s'],.000016)
        self.assertEqual(io.commands.count('ACQ:STATE RUN'),1)
        self.assertEqual(io.commands[-1],'ACQ:STATE STOP')
    def test_clipping(self):
        d,io=self.ready();io.clip=True;self.assertTrue(d.acquire_waveforms()[1]['clipped'])
    def test_timeout_and_cancel_stop(self):
        d,io=self.ready();io.running=True
        with self.assertRaises(TimeoutError):d.acquire_waveforms(timeout=0)
        self.assertEqual(io.commands[-1],'ACQ:STATE STOP')
        e=threading.Event();e.set()
        with self.assertRaises(InterruptedError):d.acquire_waveforms(cancel=e)
        self.assertEqual(io.commands[-1],'ACQ:STATE STOP')
    def test_missing_samples_rejected(self):
        d,io=self.ready();io.transaction=lambda c:b'#41000\x00\n'
        with self.assertRaises(ValueError):d.acquire_waveforms()
    def test_other_scope_not_silently_supported(self):
        with self.assertRaises(ValueError):Driver(IO(),'mso2002b').configure_acquisition([1,2],acquisition_plan(1000),.05)
