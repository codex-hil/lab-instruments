"""MSO4104 semantic extension, not yet physically commissioned.
Source: Tektronix 077024801, acquisition/horizontal/waveform commands.
"""
import math
import time


def configure(driver,channels,plan,volts_per_div):
    if driver.model!='mso4104': raise ValueError('waveform acquisition only on mso4104; other profiles OPEN ITEM')
    if len(channels)!=2 or len(set(channels))!=2 or any(type(c)!=int or not 1<=c<=4 for c in channels): raise ValueError('two distinct scope channels 1..4 required')
    if not math.isfinite(volts_per_div) or volts_per_div<=0: raise ValueError('invalid volts/div')
    count=next((n for n in (1000,10000,100000) if n>=plan['record_length']),None)
    if count is None: raise ValueError('record too large')
    w,q=driver.io.write,driver.io.query
    w('HEADER OFF'); w('ACQ:STATE STOP'); w('ACQ:MODE SAMPLE')
    for ch in channels:
        for suffix,val in [('COUP','DC'),('TER','MEG'),('SCALE',volts_per_div),('POSITION',0),('OFFSET',0)]: w(f'CH{ch}:{suffix} {val}')
        w(f'SEL:CH{ch} ON')
    w(f'HOR:RECORDLENGTH {count}'); w(f'HOR:SCALE {plan["duration_s"]/10:.12g}')
    if plan['manual_sample_rate']: w(f'HOR:SAMPLERATE {plan["sample_rate_hz"]:.12g}')
    w('TRIG:A:TYPE EDGE'); w(f'TRIG:A:EDGE:SOURCE CH{channels[0]}'); w('TRIG:A:EDGE:SLOPE RISE')
    w('TRIG:A:MOD AUTO'); w(f'TRIG:A:LEVEL:CH{channels[0]} 0')
    if q('ACQ:MODE?').upper() not in ('SAMPLE','SAM'): raise ValueError('scope refused sample acquisition mode')
    actual=dict(sample_rate_hz=float(q('HOR:SAMPLERATE?')),record_length=int(q('HOR:RECORDLENGTH?')),
                seconds_per_div=float(q('HOR:SCALE?')),channels={})
    for ch in channels:
        actual['channels'][str(ch)]={k:q(f'CH{ch}:{cmd}?') for k,cmd in [('volts_per_div','SCALE'),('coupling','COUP'),('termination','TER'),('probe_gain','PROBE:GAIN')]}
    if not 64<=actual['record_length']<=100000: raise ValueError('scope record outside bounded transfer')
    if not math.isfinite(actual['sample_rate_hz']) or actual['sample_rate_hz']<=0: raise ValueError('invalid actual sample rate')
    for channel in actual['channels'].values():
        if channel['coupling'].upper()!='DC' or not math.isclose(float(channel['termination']),1e6):
            raise ValueError('scope refused DC / 1 megohm input configuration')
    driver._fra_channels=tuple(channels)
    return actual


def acquire(driver,timeout=10,cancel=None):
    if driver.model!='mso4104' or not hasattr(driver,'_fra_channels'): raise ValueError('configure acquisition first')
    io=driver.io
    deadline=time.monotonic()+timeout
    try:
        io.write('ACQ:STATE STOP'); io.write('ACQ:STOPAFTER SEQUENCE'); io.write('ACQ:STATE RUN')
        if io.query('ACQ:STOPAFTER?').upper() not in ('SEQUENCE','SEQ'): raise ValueError('scope refused single-sequence acquisition')
        while io.query('ACQ:STATE?').strip().upper() not in ('0','OFF','STOP'):
            if cancel and cancel.is_set(): raise InterruptedError('cancelled')
            if time.monotonic()>=deadline: raise TimeoutError('scope acquisition timeout')
            time.sleep(.02)
        waves={}
        for channel in driver._fra_channels:
            if cancel and cancel.is_set(): raise InterruptedError('cancelled')
            io.write(f'DATA:SOURCE CH{channel}'); io.write('DATA:ENCDG RIBINARY'); io.write('DATA:WIDTH 1'); io.write('DATA:START 1')
            n=int(io.query('HOR:RECORDLENGTH?'))
            if not 64<=n<=100000: raise ValueError('invalid record length')
            io.write(f'DATA:STOP {n}')
            meta={key:float(io.query('WFMOUTPRE:'+cmd+'?')) for key,cmd in [('dt_s','XINCR'),('xzero','XZERO'),('pt_off','PT_OFF'),('ymult','YMULT'),('yoff','YOFF'),('yzero','YZERO')]}
            if not all(math.isfinite(x) for x in meta.values()) or meta['dt_s']<=0 or meta['ymult']==0: raise ValueError('invalid waveform preamble')
            if io.query('WFMOUTPRE:XUNIT?').strip('"').lower()!='s' or io.query('WFMOUTPRE:YUNIT?').strip('"').upper()!='V': raise ValueError('waveform units are not seconds/volts')
            block=io.transaction(b'CURVE?\n')
            if block[:1]!=b'#' or block[1:2] not in b'123456789': raise ValueError('invalid binary waveform block')
            digits=int(block[1:2]); size=int(block[2:2+digits]); payload=block[2+digits:2+digits+size]
            if size!=n or len(payload)!=n: raise ValueError('missing waveform samples')
            raw=[b if b<128 else b-256 for b in payload]
            waves[channel]=dict(values=[(v-meta['yoff'])*meta['ymult']+meta['yzero'] for v in raw],dt_s=meta['dt_s'],
                t0_s=meta['xzero']-meta['pt_off']*meta['dt_s'],clipped=any(v<=-127 or v>=126 for v in raw),preamble=meta,record_length=n)
        return waves
    finally: io.write('ACQ:STATE STOP')
