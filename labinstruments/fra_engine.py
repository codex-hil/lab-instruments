"""GUI-independent FRA orchestration using semantic Driver methods only."""
from contextlib import ExitStack
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import math
import fcntl
import hashlib
import os
import threading
import time
import uuid
import platform
from importlib.resources import files
from . import __version__
from .drivers import Driver, PROFILES, validate
from .transport import Transport
from .fra_math import acquisition_plan, frequencies, estimate_pair, summarize, QualityError


def now(): return datetime.now(timezone.utc).isoformat()


def implementation_identity():
    digest=hashlib.sha256()
    for item in sorted(files('labinstruments').iterdir(),key=lambda p:p.name):
        if item.name.endswith('.py'):
            digest.update(item.name.encode()+b'\0'+item.read_bytes())
    return dict(package='labinstruments',version=__version__,python=platform.python_version(),source_sha256=digest.hexdigest())


@dataclass
class FRAConfig:
    source: str = 'tek_awg:ch1'
    input: str = 'scope:ch1'
    output: str = 'scope:ch2'
    start_frequency: float = 10.
    stop_frequency: float = 100000.
    points: int | None = None
    points_per_decade: float = 20.
    spacing: str = 'log'
    amplitude: float = .1  # programmed Vpp; transfer always uses measured Vin
    averages: int = 4
    cycles_per_record: float = 16.
    settling_cycles: float = 5.
    minimum_settling_s: float = .05
    sample_rate: str | float = 'auto'
    samples_per_cycle: float = 50.
    minimum_input_rms: float = 1e-5
    volts_per_div: float = .05
    acquisition_timeout_s: float = 10.

    @classmethod
    def from_dict(cls,value):
        if not isinstance(value,dict): raise ValueError('preset must be an object')
        try: obj=cls(**value)
        except TypeError as e: raise ValueError(str(e)) from e
        obj.validate(); return obj

    def validate(self):
        for key in ('start_frequency','stop_frequency','points_per_decade','amplitude','cycles_per_record',
                    'minimum_input_rms','volts_per_div','acquisition_timeout_s','samples_per_cycle'):
            v=getattr(self,key)
            if type(v) not in (int,float) or not math.isfinite(v) or v<=0: raise ValueError(key+' must be finite and positive')
        for key in ('settling_cycles','minimum_settling_s'):
            v=getattr(self,key)
            if type(v) not in (int,float) or not math.isfinite(v) or v<0: raise ValueError(key+' must be finite and nonnegative')
        if type(self.averages)!=int or not 1<=self.averages<=128: raise ValueError('averages must be 1..128')
        if self.cycles_per_record<2 or self.samples_per_cycle<8: raise ValueError('need >=2 cycles and >=8 samples/cycle')
        if self.acquisition_timeout_s>120: raise ValueError('acquisition timeout max 120 s')
        if self.sample_rate!='auto' and (type(self.sample_rate) not in (int,float) or not math.isfinite(self.sample_rate) or self.sample_rate<=0): raise ValueError('sample_rate must be auto or positive number')
        a,b,c=[endpoint(v) for v in (self.source,self.input,self.output)]
        if b[0]!=c[0] or b[1]==c[1] or a[0]==b[0]: raise ValueError('input/output must be distinct channels of one scope, source a separate AWG')
        fs=frequencies(self.start_frequency,self.stop_frequency,self.points,self.points_per_decade,self.spacing)
        if len(fs)*self.averages>20000: raise ValueError('sweep exceeds 20000 acquisitions')
        for f in (fs[0],fs[-1]): acquisition_plan(f,self.cycles_per_record,self.samples_per_cycle,self.sample_rate)
        return fs


def endpoint(text):
    if not isinstance(text,str): raise ValueError('endpoint must be device:chN')
    name,sep,ch=text.rpartition(':ch')
    if not sep or not name or not ch.isdigit() or not 1<=int(ch)<=4: raise ValueError('endpoint must be device:chN')
    return name,int(ch)


def settling_seconds(config,frequency): return max(config.minimum_settling_s,config.settling_cycles/frequency)


class InstrumentSession:
    """Reuse existing inventory and Driver/Transport. No new instrument registry."""
    def __init__(self,inventory,config): self.inventory=inventory; self.config=config; self.stack=ExitStack()
    def __enter__(self):
        c=self.config; c.validate(); source,ch=endpoint(c.source); scope,_=endpoint(c.input)
        specs=self.inventory['devices']; awg_spec=specs[source]; scope_spec=specs[scope]
        if PROFILES[awg_spec['model']][1]!='awg' or scope_spec['model']!='mso4104': raise ValueError('requires AWG profile and MSO4104 waveform capability')
        if awg_spec['transport']['kind']=='gateway': raise ValueError('AWG multi-command operation over raw shared gateway is not supported yet')
        if not awg_spec.get('serial') or not scope_spec.get('serial'): raise ValueError('expected SCPI serials required')
        if not awg_spec.get('commissioned') or not awg_spec.get('limits',{}).get('allow_output'): raise ValueError('AWG must be commissioned with limits.allow_output=true in existing inventory')
        self.limits=awg_spec['limits']
        for f in c.validate(): validate(awg_spec['model'],dict(channel=ch,frequency=f,vpp=c.amplitude,offset=0,enable=True),self.limits)
        try:
            # Process-local FRA jobs must not overlap on either physical identity.
            # This does not reserve devices against unrelated external SCPI clients.
            for spec in sorted([awg_spec,scope_spec],key=lambda x:(x['model'],x['serial'])):
                key=hashlib.sha256((spec['model']+'/'+spec['serial']).encode()).hexdigest()
                fd=os.open(f'/tmp/labinst-fra-{os.getuid()}-{key}.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
                handle=self.stack.enter_context(os.fdopen(fd,'w'))
                fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
            self.awg=Driver(self.stack.enter_context(Transport(awg_spec['transport'])),awg_spec['model'],awg_spec['serial'])
            self.scope=Driver(self.stack.enter_context(Transport(scope_spec['transport'])),scope_spec['model'],scope_spec['serial'])
            return self
        except BaseException: self.stack.close(); raise
    def __exit__(self,*args): self.stack.close()


class FRAEngine:
    def __init__(self,session_factory): self.session_factory=session_factory

    def run(self,config,cancel=None,notify=None):
        fs=config.validate(); cancel=cancel or threading.Event(); notify=notify or (lambda event:None)
        result=dict(software=implementation_identity(),schema='labinst.fra.v1',id=str(uuid.uuid4()),timestamp=now(),trust_state='UNTRUSTED',
                    config=asdict(config),identities={},points=[],warnings=[],errors=[],status='running',cleanup={})
        def emit(kind,**data): notify(dict(type=kind,**data))
        emit('started',result=result,total=len(fs))
        try:
            with self.session_factory(config) as session:
                awg,scope=session.awg,session.scope
                verified={}
                try:
                    verified['source']=awg.identify()
                    verified['scope']=scope.identify()
                    result['identities']=dict(verified)
                    result['simulation']=bool(getattr(session,'simulation',False))
                    emit('identified',identities=result['identities'],simulation=result['simulation'])
                    for index,f in enumerate(fs):
                        if cancel.is_set(): raise InterruptedError('cancelled')
                        emit('progress',frequency_hz=f,index=index,total=len(fs))
                        point=dict(frequency_hz=f,timestamp=now(),gain_db=None,phase_deg=None,vin_rms=None,vout_rms=None,
                                   sample_rate_hz=None,record_length=None,averages=0,requested_averages=config.averages,
                                   status='acquisition_error',warnings=[],estimates=[],acquisitions=[])
                        try:
                            plan=acquisition_plan(f,config.cycles_per_record,config.samples_per_cycle,config.sample_rate)
                            point['requested_acquisition']=plan
                            if cancel.is_set(): raise InterruptedError('cancelled')
                            point['source_settings']=awg.apply(dict(channel=endpoint(config.source)[1],frequency=f,vpp=config.amplitude,offset=0,enable=True),session.limits)
                            excitation=point['source_settings']['state']['frequency']
                            if not math.isfinite(excitation) or excitation<=0: raise ValueError('invalid source frequency readback')
                            point['excitation_frequency_hz']=excitation
                            channels=[endpoint(config.input)[1],endpoint(config.output)[1]]
                            point['actual_acquisition']=scope.configure_acquisition(channels,plan,config.volts_per_div)
                            actual=point['actual_acquisition']
                            if actual['sample_rate_hz']/f<max(8,config.samples_per_cycle*.95) and config.sample_rate=='auto': raise ValueError('actual sample rate below requested samples/cycle')
                            if actual['sample_rate_hz']/f<8: raise ValueError('aliasing/insufficient samples per cycle')
                            if cancel.wait(settling_seconds(config,f)): raise InterruptedError('cancelled')
                            for avg in range(config.averages):
                                if cancel.is_set(): raise InterruptedError('cancelled')
                                waves=scope.acquire_waveforms(config.acquisition_timeout_s,cancel)
                                inp,out=[waves[ch] for ch in channels]
                                for wave in (inp,out):
                                    if len(wave['values'])*wave['dt_s']*f<config.cycles_per_record*.95: raise ValueError('actual record too short for requested cycles')
                                    if config.sample_rate=='auto' and 1/wave['dt_s']/f<config.samples_per_cycle*.95: raise ValueError('waveform sampling below target')
                                point['sample_rate_hz']=1/inp['dt_s']; point['record_length']=len(inp['values'])
                                point['acquisitions'].append({str(ch):{k:v for k,v in waves[ch].items() if k!='values'} for ch in channels})
                                point['estimates'].append(estimate_pair(inp,out,excitation,config.minimum_input_rms))
                                point['averages']=len(point['estimates'])
                            point.update(summarize(point['estimates'])); point['status']='ok'
                        except InterruptedError: raise
                        except QualityError as e: point['status']=e.status; point['warnings'].append(str(e))
                        except Exception as e: point['warnings'].append(type(e).__name__+': '+str(e))
                        result['points'].append(point); emit('point',point=point,index=index+1,total=len(fs))
                        if point['status']=='acquisition_error':
                            result['errors'].append('acquisition failed; sweep stopped to avoid continuing with uncertain instrument state')
                            break
                    result['status']='completed' if all(p['status']=='ok' for p in result['points']) else 'completed_with_errors'
                finally:
                    # Separate cleanup attempts: a scope failure must never suppress AWG OFF.
                    for name,operation in [('source_off',awg.off),('scope_stopped',scope.stop_acquisition)]:
                        if ('source' if name=='source_off' else 'scope') not in verified: continue
                        try: result['cleanup'][name]=operation() or True
                        except Exception as e:
                            result['cleanup'][name]=False; result['errors'].append(name+': '+str(e))
        except InterruptedError: result['status']='cancelled'
        except Exception as e: result['status']='error'; result['errors'].append(type(e).__name__+': '+str(e))
        finally:
            if any(v is False for v in result['cleanup'].values()): result['status']='cleanup_error'
            result['finished_at']=now(); emit('finished',result=result)
        return result
