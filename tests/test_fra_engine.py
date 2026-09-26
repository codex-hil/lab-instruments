import copy
from dataclasses import asdict
import json
import math
import threading
import unittest
from labinstruments.fra_engine import FRAConfig,FRAEngine,InstrumentSession
from labinstruments.fra_simulation import Simulation
from labinstruments.fra_export import export_bytes


class EngineTests(unittest.TestCase):
    def config(self,**extra):
        return FRAConfig.from_dict(dict(start_frequency=100,stop_frequency=10000,points=3,averages=3,minimum_settling_s=0,settling_cycles=0,**extra))
    def run_fixture(self,cls=Simulation,config=None,cancel=None,notify=None):
        sessions=[]
        def factory(c):s=cls(c);sessions.append(s);return s
        result=FRAEngine(factory).run(config or self.config(),cancel,notify)
        if sessions:self.assertFalse(sessions[0].enabled)
        return result
    def test_quantized_timing_rc(self):
        r=self.run_fixture();self.assertEqual(r['status'],'completed');self.assertTrue(r['simulation'])
        for p in r['points']:
            h=1/(1+1j*p['frequency_hz']/1000)
            self.assertAlmostEqual(p['gain_db'],20*math.log10(abs(h)),delta=.01)
            self.assertAlmostEqual(p['phase_deg'],math.degrees(math.atan2(h.imag,h.real)),delta=.03)
            self.assertAlmostEqual(p['sample_rate_hz'],p['frequency_hz']*50*1.03)
            self.assertEqual(len(p['estimates']),3)
        json.dumps(r,allow_nan=False)
    def test_clipped_invalid_point(self):
        class Clipped(Simulation):
            def acquire_waveforms(self,*a):
                w=super().acquire_waveforms(*a);w[self.channels[1]]['clipped']=True;return w
        r=self.run_fixture(Clipped)
        self.assertEqual(r['status'],'completed_with_errors')
        self.assertTrue(all(p['status']=='clipping' and p['gain_db'] is None for p in r['points']))
    def test_low_input(self):
        class Low(Simulation):
            def acquire_waveforms(self,*a):
                w=super().acquire_waveforms(*a);w[self.channels[0]]['values']=[0]*len(w[self.channels[0]]['values']);return w
        r=self.run_fixture(Low);self.assertEqual(r['points'][0]['status'],'low_input')
    def test_timeout_stops_sweep_and_cleans(self):
        class Timeout(Simulation):
            def acquire_waveforms(self,*a):raise TimeoutError('fixture timeout')
        r=self.run_fixture(Timeout);self.assertEqual(len(r['points']),1)
        self.assertEqual(r['points'][0]['status'],'acquisition_error');self.assertTrue(r['cleanup']['source_off'])
    def test_invalid_acquisition(self):
        for mode in ['short','rate','missing','nan']:
            class Invalid(Simulation):
                def acquire_waveforms(self,*a):
                    w=super().acquire_waveforms(*a);one=w[self.channels[0]]
                    if mode=='short':one['values']=one['values'][:5]
                    if mode=='rate':one['dt_s']=1/self.frequency
                    if mode=='missing':return {}
                    if mode=='nan':one['values'][3]=float('nan')
                    return w
            with self.subTest(mode=mode):
                r=self.run_fixture(Invalid);self.assertEqual(r['points'][0]['status'],'acquisition_error')
    def test_stop_after_point(self):
        cancel=threading.Event()
        def notify(e):
            if e['type']=='point':cancel.set()
        r=self.run_fixture(cancel=cancel,notify=notify)
        self.assertEqual(r['status'],'cancelled');self.assertEqual(len(r['points']),1);self.assertTrue(r['cleanup']['source_off'])
    def test_stop_during_wait(self):
        cancel=threading.Event()
        def notify(e):
            if e['type']=='progress':cancel.set()
        r=self.run_fixture(cancel=cancel,notify=notify);self.assertEqual(r['status'],'cancelled')
    def test_cleanup_failure_is_explicit(self):
        class BadOff(Simulation):
            def off(self):self.enabled=False;raise OSError('OFF not confirmed')
        r=self.run_fixture(BadOff);self.assertEqual(r['status'],'cleanup_error');self.assertFalse(r['cleanup']['source_off']);self.assertTrue(r['cleanup']['scope_stopped'])
    def test_bad_settings_no_session(self):
        for extra in [{'averages':False},{'amplitude':float('nan')},{'output':'other:ch2'},{'input':'scope:ch2'},{'sample_rate':False},{'points':True}]:
            with self.subTest(extra=extra),self.assertRaises(ValueError):FRAConfig.from_dict(extra)
    def test_exports(self):
        r=self.run_fixture()
        self.assertEqual(json.loads(export_bytes(r,'json'))['schema'],'labinst.fra.v1')
        self.assertIn(b'phase_unwrapped_deg',export_bytes(r,'csv'))
        self.assertTrue(export_bytes(r,'png').startswith(b'\x89PNG'))
        self.assertIn(b'SIMULATION',export_bytes(r,'svg'))
    def test_existing_inventory_gate(self):
        from pathlib import Path
        inventory=json.loads((Path(__file__).parents[1]/'examples/lab.json').read_text())
        with self.assertRaisesRegex(ValueError,'commissioned'):
            with InstrumentSession(inventory,self.config()):pass
    def test_fra_contains_no_command_io(self):
        import ast
        from pathlib import Path
        for name in ['fra_engine.py','fra_math.py','fra_web.py','fra_cli.py']:
            tree=ast.parse((Path(__file__).parents[1]/'labinstruments'/name).read_text())
            for node in ast.walk(tree):
                if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):
                    self.assertNotIn(node.func.attr,['query','transaction'],name)
    def test_manual_rate_uses_actual_timing(self):
        c=FRAConfig(start_frequency=1000,stop_frequency=1000,points=1,averages=1,sample_rate=51000,settling_cycles=0,minimum_settling_s=0)
        r=self.run_fixture(config=c)
        self.assertEqual(r['status'],'completed');self.assertAlmostEqual(r['points'][0]['sample_rate_hz'],52530)
