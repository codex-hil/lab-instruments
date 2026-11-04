import cmath
import math
import random
import unittest
from labinstruments.fra_math import *


def wave(amplitude=1,phase=0,noise=0,dt=1/50123,n=813,t0=.00123,frequency=1234.567):
    rng=random.Random(4)
    return dict(values=[2.3+amplitude*math.cos(2*math.pi*frequency*(t0+i*dt)+phase)+rng.gauss(0,noise) for i in range(n)],dt_s=dt,t0_s=t0,clipped=False)


class MathTests(unittest.TestCase):
    def test_non_bin_amplitudes_and_phases(self):
        for gain,deg in [(1,0),(.2,0),(.5,47),(2,-103),(.8,179),(.8,-179)]:
            with self.subTest(gain=gain,deg=deg):
                e=summarize([estimate_pair(wave(),wave(gain,math.radians(deg)),1234.567)])
                self.assertAlmostEqual(e['gain_db'],20*math.log10(gain),places=9)
                self.assertAlmostEqual(e['phase_deg'],deg,places=9)
                self.assertAlmostEqual(e['vin_rms'],1/math.sqrt(2),places=9)
    def test_noise(self):
        e=summarize([estimate_pair(wave(noise=.02),wave(.5,-.7,.02),1234.567)])
        self.assertAlmostEqual(e['gain_db'],-6.0206,delta=.1)
        self.assertAlmostEqual(e['phase_deg'],math.degrees(-.7),delta=.3)
    def test_complex_averages_wrap(self):
        e=summarize([estimate_pair(wave(),wave(.5,math.radians(p)),1234.567) for p in [179,-179]])
        self.assertAlmostEqual(e['phase_deg'],-180)
        self.assertAlmostEqual(e['phase_std_deg'],math.sqrt(2))
        self.assertAlmostEqual(e['gain_db'],20*math.log10(.5*math.cos(math.pi/180)))
    def test_different_time_origins(self):
        e=estimate_pair(wave(),wave(.5,.3,t0=.004),1234.567)
        self.assertAlmostEqual(cmath.phase(complex(e['h_real'],e['h_imag'])),.3)
    def test_quality(self):
        with self.assertRaises(QualityError): estimate_pair(wave(0),wave(),1234.567)
        w=wave();w['clipped']=True
        with self.assertRaises(QualityError): estimate_pair(w,wave(),1234.567)
        for w in [wave(n=10),wave(dt=.001),dict(values=[float('nan')]*100,dt_s=.00001,t0_s=0)]:
            with self.assertRaises(ValueError): phasor(w,1234.567)
    def test_planning(self):
        self.assertEqual(frequencies(10,1000,points_per_decade=2),[10,10*100**.25,100,10*100**.75,1000])
        self.assertEqual(frequencies(1,3,points=3,spacing='linear'),[1,2,3])
        self.assertEqual(frequencies(1,1),[1])
        self.assertEqual(acquisition_plan(1000)['record_length'],800)
        for start,stop in [(0,1),(2,1),(float('nan'),1)]:
            with self.assertRaises(ValueError): frequencies(start,stop)
        with self.assertRaises(ValueError): acquisition_plan(1000,sample_rate=1000)
    def test_wrapping(self):
        self.assertEqual(wrap_phase(180),-180)
        self.assertEqual(unwrap_phase([170,-170,-150,None,-170,170]),[170,190,210,None,-170,-190])

class ComparisonTests(unittest.TestCase):
    def test_rc_and_loopback_errors(self):
        from labinstruments.fra_validation import compare
        for kind in ['loopback','rc']:
            points=[]
            for f in frequencies(10,100000,points=81):
                h=1 if kind=='loopback' else 1/(1+1j*f/1000)
                points.append(dict(frequency_hz=f,status='ok',gain_db=20*math.log10(abs(h)),phase_deg=math.degrees(cmath.phase(h))))
            r=compare(dict(points=points,status='completed',simulation=True),kind,1000,1/(2*math.pi*1e6))
            self.assertEqual(r['comparison_status'],'PASS');self.assertEqual(r['max_abs_gain_error_db'],0)
            if kind=='rc':self.assertAlmostEqual(r['measured_cutoff_hz'],1000)
            points[0]['status']='clipping'
            self.assertEqual(compare(dict(points=points,status='completed',simulation=True),kind,1000,1/(2*math.pi*1e6))['comparison_status'],'FAIL')
