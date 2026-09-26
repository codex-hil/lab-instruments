"""Explicit deterministic demo fixture; never evidence of physical commissioning."""
import math
import random


class Simulation:
    simulation=True
    def __init__(self,config,cutoff=1000): self.config=config; self.cutoff=cutoff; self.awg=self; self.scope=self; self.limits={}; self.count=0; self.enabled=False
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def identify(self): return 'SIMULATED RC fixture; no physical instrument'
    def apply(self,params,limits): self.frequency=params['frequency']; self.enabled=params['enable']; return {'state':dict(params),'readback':{}}
    def off(self): self.enabled=False; return {'off_confirmed':True}
    def stop_acquisition(self): return True
    def configure_acquisition(self,channels,plan,volts_per_div):
        self.channels=channels; self.plan=plan
        return dict(sample_rate_hz=plan['sample_rate_hz']*1.03,record_length=math.ceil(plan['record_length']*1.03))
    def acquire_waveforms(self,timeout=10,cancel=None):
        f=self.frequency; fs=self.plan['sample_rate_hz']*1.03; n=math.ceil(self.plan['record_length']*1.03)
        self.count+=1; rng=random.Random(self.count); t0=.000137*self.count; h=1/(1+1j*f/self.cutoff)
        result={}
        for ch,transfer in zip(self.channels,[1+0j,h]):
            amp=self.config.amplitude/2*abs(transfer); phase=math.atan2(transfer.imag,transfer.real)
            result[ch]=dict(values=[amp*math.cos(2*math.pi*f*(t0+i/fs)+phase)+rng.gauss(0,amp*.001) for i in range(n)],
                            dt_s=1/fs,t0_s=t0,clipped=False,record_length=n)
        return result
