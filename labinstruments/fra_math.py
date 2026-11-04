"""Instrument-independent synchronous fitting and acquisition planning."""
import cmath
import math
import statistics


def wrap_phase(x): return (x+180)%360-180


def unwrap_phase(values):
    result=[]; previous=None
    for value in values:
        if value is None: result.append(None); previous=None
        else:
            value=value if previous is None else previous+wrap_phase(value-previous)
            result.append(value); previous=value
    return result


def frequencies(start,stop,points=None,points_per_decade=20,spacing='log'):
    if not all(math.isfinite(v) and v>0 for v in (start,stop)) or stop<start: raise ValueError('require 0 < start <= stop')
    if spacing not in ('log','linear'): raise ValueError('invalid spacing')
    if points is None:
        if not math.isfinite(points_per_decade) or points_per_decade<=0: raise ValueError('points_per_decade must be positive')
        points=max(2,math.ceil(math.log10(stop/start)*points_per_decade)+1)
    if type(points)!=int or not 1<=points<=10000: raise ValueError('points must be 1..10000')
    if start==stop: return [start]
    if points<2: raise ValueError('different endpoints require >=2 points')
    out=[start*(stop/start)**(i/(points-1)) if spacing=='log' else start+(stop-start)*i/(points-1) for i in range(points)]
    out[0],out[-1]=start,stop
    return out


def acquisition_plan(frequency,cycles=16,samples_per_cycle=50,sample_rate='auto'):
    fs=frequency*samples_per_cycle if sample_rate=='auto' else float(sample_rate)
    if not math.isfinite(fs) or fs/frequency<8: raise ValueError('need >=8 samples/cycle')
    duration=cycles/frequency; count=math.ceil(duration*fs)
    if count>100000: raise ValueError('record exceeds 100000 samples')
    return dict(duration_s=duration,sample_rate_hz=fs,record_length=max(64,count),manual_sample_rate=sample_rate!='auto')


def _solve(matrix,rhs):
    a=[list(row)+[v] for row,v in zip(matrix,rhs)]
    for i in range(len(a)):
        p=max(range(i,len(a)),key=lambda j:abs(a[j][i])); a[i],a[p]=a[p],a[i]
        pivot=a[i][i]
        if abs(pivot)<1e-12: raise ValueError('singular sine fit')
        a[i]=[v/pivot for v in a[i]]
        for j in range(len(a)):
            if j!=i:
                scale=a[j][i]; a[j]=[x-scale*y for x,y in zip(a[j],a[i])]
    return [row[-1] for row in a]


def phasor(wave,frequency):
    """Generalized single-frequency DFT: fit cos, sin and DC jointly.
    Correct finite-record nonorthogonality, no integer-cycle/FFT-bin requirement.
    Peak cosine convention: real*cos - imag*sin. Timing comes only from waveform.
    """
    y=wave['values']; dt=wave['dt_s']; t0=wave['t0_s']
    if len(y)<32 or not math.isfinite(dt) or dt<=0 or not math.isfinite(t0): raise ValueError('invalid waveform/timing')
    if 1/dt/frequency<8: raise ValueError('insufficient samples per cycle')
    if len(y)*dt*frequency<2: raise ValueError('insufficient cycles')
    if not all(math.isfinite(v) for v in y): raise ValueError('nonfinite waveform')
    c=[]; s=[]
    for i in range(len(y)):
        angle=2*math.pi*math.remainder(frequency*(t0+i*dt),1)
        c.append(math.cos(angle)); s.append(math.sin(angle))
    cc=sum(v*v for v in c); ss=sum(v*v for v in s); cs=sum(x*z for x,z in zip(c,s))
    a,b,dc=_solve([[cc,cs,sum(c)],[cs,ss,sum(s)],[sum(c),sum(s),len(y)]],
                 [sum(v*x for v,x in zip(y,c)),sum(v*x for v,x in zip(y,s)),sum(y)])
    if not all(math.isfinite(v) for v in (a,b,dc)): raise ValueError("nonfinite sine fit")
    return complex(a,-b)


class QualityError(ValueError):
    def __init__(self,status,message): super().__init__(message); self.status=status


def estimate_pair(inp,out,frequency,minimum_input_rms=1e-5):
    if inp.get('clipped') or out.get('clipped'): raise QualityError('clipping','input' if inp.get('clipped') else 'output')
    if len(inp['values'])!=len(out['values']): raise ValueError('channel length mismatch')
    if not math.isclose(inp['dt_s'],out['dt_s'],rel_tol=1e-9): raise ValueError('channel timing mismatch')
    x=phasor(inp,frequency); y=phasor(out,frequency)
    if abs(x)/math.sqrt(2)<minimum_input_rms: raise QualityError('low_input','Vin below minimum RMS')
    if abs(y)==0: raise QualityError('low_output','zero output fundamental')
    h=y/x
    if not math.isfinite(h.real) or not math.isfinite(h.imag): raise ValueError('nonfinite transfer function')
    return dict(h_real=h.real,h_imag=h.imag,vin_rms=abs(x)/math.sqrt(2),vout_rms=abs(y)/math.sqrt(2),
                xin_real=x.real,xin_imag=x.imag,xout_real=y.real,xout_imag=y.imag)


def summarize(estimates):
    hs=[complex(e['h_real'],e['h_imag']) for e in estimates]; h=sum(hs)/len(hs)
    if not math.isfinite(h.real) or not math.isfinite(h.imag): raise ValueError('nonfinite complex mean')
    if abs(h)<1e-15: raise QualityError('unstable','complex averages cancel')
    phase=wrap_phase(math.degrees(cmath.phase(h))); gains=[20*math.log10(abs(v)) for v in hs]
    deviations=[wrap_phase(math.degrees(cmath.phase(v))-phase) for v in hs]
    return dict(gain_db=20*math.log10(abs(h)),phase_deg=phase,
        vin_rms=statistics.mean(e['vin_rms'] for e in estimates),vout_rms=statistics.mean(e['vout_rms'] for e in estimates),
        gain_std_db=statistics.stdev(gains) if len(hs)>1 else 0.,phase_std_deg=statistics.stdev(deviations) if len(hs)>1 else 0.,
        h_real=h.real,h_imag=h.imag)
