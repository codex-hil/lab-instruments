#!/usr/bin/env python3
"""Offline differential regression. All numerical mismatches are failures, never auto-baselined."""
import argparse,base64,csv,datetime,hashlib,html,inspect,io,json,math,os,platform,random,signal,subprocess,sys,time
from pathlib import Path
import numpy as np
import allantools as at
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from reference import statistics
BASE=Path('/home/timelab/wr-timing'); CODE=Path(__file__).resolve().parent
STATS={'adev':at.adev,'oadev':at.oadev,'mdev':at.mdev,'hdev':at.hdev,'ohdev':at.ohdev,'tdev':at.tdev,'mtie':at.mtie}
TL={'oadev':'a','mdev':'m','ohdev':'h','tdev':'t','mtie':'M'}
# Frozen before first differential run. Dimensionless for xDEV, seconds for TDEV/MTIE.
RTOL=5e-8; ATOL=1e-20
GRID=[1,2,4,8,10,20,40,80,100]
MTIE_GRID=[1,2,4,10,20,40,100]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,o):Path(p).write_text(json.dumps(o,indent=2,allow_nan=False)+'\n')
def win(p):return 'Z:'+str(Path(p).resolve()).replace('/','\\')
def capture(cmd):return subprocess.run(cmd,capture_output=True,text=True).stdout

def validate_input(values, dt, timestamps=None):
    x=np.asarray(values)
    if x.ndim!=1 or len(x)<16 or not np.isfinite(x).all():
        raise ValueError('Require >=16 finite phase samples in seconds; missing samples must be rejected or explicitly segmented/imputed')
    if not math.isfinite(dt) or dt<=0:raise ValueError('Invalid sample period')
    if timestamps is not None:
        t=np.asarray(timestamps)
        if t.shape!=x.shape or not np.isfinite(t).all() or not np.allclose(np.diff(t),dt,rtol=1e-12,atol=1e-12*dt):
            raise ValueError('Nonuniform/missing/duplicate timestamps; do not compress time')
    return x

def tim(values,dt,path,name):
    template=(BASE/'app/userdocs/TimeLab/Examples/HP_5370B_ADEV_floor.tim').read_text()
    header=template[:template.index('TIC 30000')]
    repl={'CAP':'SYNTHETIC regression '+name,'NOT':'Offline synthetic fixture; instrument field is template metadata only',
          'IFN':name+'.csv','PER':format(dt,'.17g'),'NOM':'1','DAQ':'0','DEN':'29','MIN':'4','UNW':'1','WIN':str(len(values)),'HIS':'1'}
    header='\n'.join(k.split(' ',1)[0]+' '+repl[k.split(' ',1)[0]] if k.split(' ',1)[0] in repl else k for k in header.splitlines())
    path.write_text(header+'\nTIC '+str(len(values))+'\n'+''.join(format(float(v),'.17e')+'\n' for v in values))

def fixtures(root):
    out=[]; n=1024; seed=20261101
    rng=random.Random(seed); white=np.array([rng.gauss(0,1e-10) for _ in range(n)])
    rng=random.Random(seed+1); wf=np.cumsum([rng.gauss(0,2e-11) for _ in range(n)])
    t=np.arange(n,dtype=float); drift=2e-15*t*t; mixture=white+drift+3e-10*t
    coeff=np.polynomial.polynomial.polyfit(t,mixture,2)
    cases=[('zero',np.zeros(n),1.,{'type':'constant','offset_s':0}),
      ('linear_phase',2e-9+4e-10*t,1.,{'type':'linear phase','offset_s':2e-9,'fractional_frequency':4e-10}),
      ('quadratic_drift',drift,1.,{'type':'quadratic phase','frequency_drift_per_s':4e-15}),
      ('white_phase',white,1.,{'type':'Gaussian phase','seed':seed,'sigma_s':1e-10}),
      ('white_frequency',wf,1.,{'type':'cumulative Gaussian phase increments','seed':seed+1,'increment_sigma_s':2e-11}),
      ('sinusoid_noise',2e-9*np.sin(2*np.pi*t/127)+white*.2,1.,{'type':'sinusoid+Gaussian phase','period_s':127,'amplitude_s':2e-9,'seed':seed,'noise_sigma_s':2e-11}),
      ('step',np.where(t>=512,3e-9,0.),1.,{'type':'phase step','index':512,'height_s':3e-9}),
      ('alternating',np.where(t%2,1e-9,-1e-9),1.,{'type':'alternating phase','amplitude_s':1e-9}),
      ('quarter_second',white,.25,{'type':'same binary phase values as white_phase','sample_period_s':.25}),
      ('two_seconds',white,2.,{'type':'same binary phase values as white_phase','sample_period_s':2.}),
      ('drift_plus_noise',mixture,1.,{'type':'white_phase + 2e-15*t^2 + 3e-10*t','seed':seed}),
      ('explicit_detrend',mixture-np.polynomial.polynomial.polyval(t,coeff),1.,{'type':'explicit polynomial removal before BOTH applications','parent':'drift_plus_noise','degree':2,'coefficients_ascending':coeff.tolist(),'fit':'numpy.polynomial.polynomial.polyfit, unweighted; t in seconds'}),
      ('short_record',white[:64],1.,{'type':'white_phase prefix','seed':seed,'length':64})]
    mask=np.ones(n,dtype=bool);mask[128:136]=False;mask[600]=False
    raw=white.copy();raw[~mask]=np.nan
    np.savetxt(root/'missing-raw.csv',np.column_stack([t,raw]),delimiter=',',header='time_s,phase_s',comments='')
    # Explicit segmentation, never collapse timestamps or bridge missing intervals.
    edges=np.flatnonzero(np.diff(np.r_[False,mask,False])); spans=list(zip(edges[::2],edges[1::2]))
    for i,(a,b) in enumerate(spans):cases.append((f'gap_segment_{i}',white[a:b],1.,{'type':'contiguous finite segment','source_start_index':int(a),'source_stop_exclusive':int(b),'policy':'no window crosses a gap'}))
    interp=np.interp(t,t[mask],white[mask]);cases.append(('explicit_gap_interpolation',interp,1.,{'type':'explicit linear interpolation','policy':'OPTIONAL imputation, not equivalent to original measurement','missing_indices':np.flatnonzero(~mask).tolist()}))
    gap={'missing_indices':np.flatnonzero(~mask).tolist(),'segments':[[int(a),int(b)] for a,b in spans],'default_policy':'reject nonfinite or nonuniform samples before either tool','raw_sha256':sha(root/'missing-raw.csv')}
    for name,x,dt,params in cases:
        validate_input(x,dt)
        f=root/(name+'.csv');np.savetxt(f,x,fmt='%.17e')
        tt=root/(name+'.tim');tim(x,dt,tt,name)
        entry={'name':name,'n':len(x),'dt_s':dt,'rate_hz':1/dt,'phase_unit':'seconds','data_type':'phase','detrending':'none except explicit_detrend fixture','generator':params,'csv_sha256':sha(f),'tim_sha256':sha(tt)}
        out.append(entry)
    dump(root/'manifest.json',{'generator':'CPython random.Random.gauss + NumPy deterministic arithmetic; exact CSV retained','fixtures':out,'missing_samples':gap})
    return out,raw,mask

def run_tl(inp,out,prefix=None,png=False,timeout=40):
    out.mkdir(parents=True);env=os.environ.copy();env.update(WINEPREFIX=str(prefix or BASE.parent/'.wine-timelab'),WINEDEBUG='-all',WINEDLLOVERRIDES='gdiplus=n,b')
    cmd=['xvfb-run','-a','-s','-screen 0 1440x1000x24 -nolisten tcp','wine',str(BASE/'app/app/timelab64.exe'),win(CODE/'export_all.js'),win(inp.parent),inp.name,win(out),'png' if png else 'no-png']
    start=time.monotonic()
    with (out/'wine.log').open('w') as log:
        p=subprocess.Popen(cmd,cwd=BASE/'app/app',env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        try:rc=p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid,signal.SIGTERM)
            subprocess.run(['/usr/lib/x86_64-linux-gnu/wine/wineserver','-k'],env=env,capture_output=True)
            p.wait();rc=124
    return {'returncode':rc,'elapsed_s':time.monotonic()-start,'completed':(out/'completed.json').exists()}

def load_csv(p):
    try:
        a=np.loadtxt(p,delimiter=',',ndmin=2)
        return a if a.size else np.empty((0,2))
    except (ValueError,OSError):return np.empty((0,2))

def close(a,b):return bool(math.isfinite(a) and math.isfinite(b) and abs(a-b)<=ATOL+RTOL*abs(b))
def figure_uri(fig):
    f=io.BytesIO();fig.savefig(f,format='png',dpi=115,bbox_inches='tight');plt.close(fig)
    return 'data:image/png;base64,'+base64.b64encode(f.getvalue()).decode()

def report(run,summary,rows,cases,events):
    chunks=['<!doctype html><html lang="pl"><meta charset="utf-8"><title>TimeLab differential regression</title><style>body{font:16px system-ui;margin:32px;max-width:1250px}table{border-collapse:collapse;font-size:13px}td,th{border:1px solid #ccc;padding:6px}th{background:#eef3f8}.PASS{color:#12682d}.FAIL{color:#b11}img{max-width:100%}code{background:#eee}details{margin:20px 0}</style>',
      '<h1>TimeLab / AllanTools / niezależna kontrola</h1>',f'<h2 class="{summary["status"]}">{summary["status"]}</h2>',
      '<p>Offline, dane syntetyczne; żaden program nie jest wzorcem. Kontrola: bezpośrednie wzory różnicowe i arytmetyka Decimal (60 cyfr), osobny moduł bez AllanTools i NumPy.</p>',
      '<p>TimeLab ADEV → OADEV; TimeLab HDEV → OHDEV. Klasyczne ADEV/HDEV: AllanTools kontra kontrola, TimeLab N/A — brak osobnego trybu w udokumentowanym interfejsie. MDEV i TDEV to estymatory nakładające się. MTIE używa okna m+1 próbek (m odstępów).</p>',
      '<p>Faza/TIE w sekundach, tau w sekundach, ADEV/OADEV/MDEV/HDEV/OHDEV bezwymiarowe, TDEV/MTIE w sekundach. Brak automatycznego detrendingu. Dane po jawnym detrendingu są identyczne w obu programach; weryfikowany jest eksport fazy.</p>',
      f'<p>Tolerancja ustalona przed testem: |a−b| ≤ {ATOL:g} + {RTOL:g}|b|. Niepewność statystyczna nie jest tolerancją numeryczną. W pobliżu zera raportujemy błąd absolutny. Brak oczekiwanego tau, niefinitywny wynik i brak eksportu to FAIL, nie pominięcie.</p>',
      '<p>Jawna wspólna siatka m: '+html.escape(str(GRID))+'. MTIE ma oddzielną, potwierdzoną eksportem siatkę m=1,2,4,10,20,40,100 (brak m=8,80); nie interpolujemy jej. Dla krótkich rekordów m ≤ N/8. TimeLab wybiera własne koszyki; zapisano wszystkie i wymagamy obecności każdego oczekiwanego tau, bez interpolacji wykresów. Funkcje AllanTools mają data_type=phase, rate=1/dt. Binning DEN=29, MIN=4; clipping, error bars i spline wyłączone.</p>',
      '<p>Formuły: d2=x[i+2m]−2x[i+m]+x[i]; OADEV²=mean(d2²)/(2τ²); ADEV stosuje i=0,m,2m…; d3=x[i+3m]−3x[i+2m]+3x[i+m]−x[i]; OHDEV²=mean(d3²)/(6τ²), HDEV stosuje krok m. MDEV: mean((mean_m(d2))²)/(2τ²), N−3m+1 okien. TDEV=τ·MDEV/√3. MTIE=max_i(max(x[i:i+m+1])−min(...)).</p>',
      '<h2>Podsumowanie</h2><pre>'+html.escape(json.dumps(summary,indent=2))+'</pre>',
      '<h2>Diagnostyka i brakujące próbki</h2><p>Surowy NaN: wynik TimeLab to bounded smoke test, nie matematyczna walidacja. Timeout jest FAIL obsługi surowego wejścia; PASS całego regresyjnego testu dotyczy wejścia skończonego i poprawnego działania blokady luk. Zwykłe funkcje AllanTools również nie są estymatorami odpornymi na luki. Segmentów nie łączymy ani nie uśredniamy ich xDEV bez odrębnej definicji.</p><pre>'+html.escape(json.dumps(events,indent=2))+'</pre>',
      '<h2>Macierz testów</h2><table><tr><th>Dane</th><th>Statystyka</th><th>Porównanie</th><th>Liczba tau</th><th>Max abs</th><th>Max rel*</th><th>Wynik</th></tr>']
    groups={}
    for row in rows:groups.setdefault((row['fixture'],row['statistic'],row['comparison']),[]).append(row)
    for (f,s,c),g in groups.items():
        status='PASS' if all(r['pass'] for r in g) else 'FAIL'
        chunks.append('<tr>'+''.join('<td>'+html.escape(str(x))+'</td>' for x in [f,s,c,len(g),f"{max(r['absolute_error'] for r in g):.3g}",f"{max(r['relative_error'] for r in g):.3g}",status])+'</tr>')
    chunks.append('</table><p>* Względny błąd z mianownikiem max(|kontrola|,atol); nie służy samodzielnie do oceny blisko zera.</p>')
    for stat in STATS:
        fig,axes=plt.subplots(1,2,figsize=(12,4))
        for (f,s,c),g in groups.items():
            if s!=stat:continue
            if c=='TimeLab vs Decimal':axes[0].plot([r['tau_s'] for r in g],[r['observed'] for r in g],'.-',label=f)
            axes[1].plot([r['tau_s'] for r in g],[max(r['absolute_error']/(ATOL+RTOL*abs(r['reference'])),1e-12) for r in g],'.-',label=f+' '+c)
        axes[0].set_yscale('symlog',linthresh=ATOL)
        axes[0].set(xscale='log',xlabel='tau [s]',ylabel=stat+' [s]' if stat in ['tdev','mtie'] else stat+' [1]',title='TimeLab wartości')
        axes[1].set(xscale='log',yscale='log',xlabel='tau [s]',ylabel='|błąd| / tolerancja',title='Trzy implementacje: różnice');axes[1].axhline(1,color='red',ls='--')
        for ax in axes:ax.grid(True,alpha=.3)
        if stat in TL:axes[0].legend(fontsize=5,ncol=2,loc='best')
        axes[1].legend(fontsize=4,ncol=2,loc='upper left',bbox_to_anchor=(1.01,1))
        if stat in ['adev','hdev']:axes[0].text(.1,.5,'TimeLab: N/A (brak trybu non-overlap)',transform=axes[0].transAxes)
        chunks.append(f'<h2>{stat.upper()}</h2><img alt="Różnice {stat}" src="{figure_uri(fig)}">')
    chunks.append('<details><summary>Pełne wyniki punkt po punkcie (także results.csv)</summary><table><tr>'+''.join('<th>'+html.escape(k)+'</th>' for k in rows[0])+'</tr>')
    for r in rows:chunks.append('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in r.values())+'</tr>')
    chunks.append('</table></details><h2>Odtwarzanie i ślady</h2><p>manifest.json: wersje, konfiguracja, źródła i SHA256. inputs/manifest.json: generatory, parametry, odstępy, brakujące indeksy i hashe danych. timelab/: pełne eksporty i logi. results.csv i results.json: wszystkie porównania. controls.json: niezależne kontrole analityczne.</p><p>Źródła: <a href="https://allantools.readthedocs.io/en/stable/functions.html">AllanTools</a>, <a href="https://www.miles.io/PhaseStation_53100A_user_manual.pdf">TimeLab manual</a>, <a href="https://doi.org/10.6028/NIST.SP.1065">NIST SP1065</a>.</p></html>')
    (run/'report.html').write_text('\n'.join(chunks))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run-dir',type=Path);ap.add_argument('--skip-nan-probe',action='store_true');ap.add_argument('--inputs-from',type=Path);ap.add_argument('--label',default='');args=ap.parse_args()
    run=(args.run_dir or CODE/'runs'/(datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+str(os.getpid()))).resolve();run.mkdir(parents=True,exist_ok=False)
    inputs=run/'inputs';inputs.mkdir()
    if args.inputs_from:
        import shutil
        src=args.inputs_from.resolve(); fixture_manifest=json.loads((src/'manifest.json').read_text())
        cases=fixture_manifest['fixtures']
        for c in cases:
            if Path(c['name']).name!=c['name']:raise ValueError('Invalid fixture name')
            for ext in ['csv','tim']:
                f=src/(c['name']+'.'+ext)
                if sha(f)!=c[ext+'_sha256']:raise ValueError('Input SHA256 mismatch: '+str(f))
                shutil.copyfile(f,inputs/f.name)
        for name in ['manifest.json','missing-raw.csv']:shutil.copyfile(src/name,inputs/name)
        if sha(inputs/'missing-raw.csv')!=fixture_manifest['missing_samples']['raw_sha256']:raise ValueError('Gap fixture SHA256 mismatch')
        raw=np.loadtxt(inputs/'missing-raw.csv',delimiter=',',skiprows=1)[:,1];mask=np.isfinite(raw)
    else:cases,raw,mask=fixtures(inputs)
    versions={'python':sys.version,'platform':platform.platform(),'allantools':at.__version__,'numpy':np.__version__,'matplotlib':matplotlib.__version__,'wine':capture(['wine','--version']).strip(),'timelab':'runtime banner in timelab/*/wine.log; binary SHA256 below'}
    manifest={'versions':versions,'label':args.label,'replayed_inputs_from':str(args.inputs_from) if args.inputs_from else None,'input_manifest_sha256':sha(inputs/'manifest.json'),'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'config':{'rtol':RTOL,'atol':ATOL,'m_grid':GRID,'mtie_m_grid':MTIE_GRID,'tau_unit':'seconds','phase_unit':'seconds','native_detrend':False,'native_visual_residual':False,'clip_bw':False,'clip_confidence':False,'error_bars':False,'spline':False,'nominal_frequency_hz':1,'data_type':'phase','NOM_is_not_a_phase_scale':True},'sha256':{str(p):sha(p) for p in [BASE/'app/app/timelab64.exe',BASE/'app/app/gdiplus.dll',CODE/'regression.py',CODE/'reference.py',CODE/'export_all.js',CODE/'run-regression',Path(inspect.getfile(at.oadev))]},'requirements':capture([sys.executable,'-m','pip','freeze'])}
    dump(run/'manifest.json',manifest)
    # Independent controls against analytically known functions, including MTIE endpoints.
    controls={}
    lin=statistics([float(i) for i in range(64)],4,1)
    controls['linear']={'pass':all(lin[k]==0 for k in STATS if k!='mtie') and lin['mtie']==4.,'values':lin}
    quad=statistics([float(i*i) for i in range(64)],4,1)
    controls['quadratic']={'pass':abs(quad['oadev']-math.sqrt(2)*4)<1e-14 and quad['ohdev']==0 and quad['hdev']==0 and abs(quad['mdev']-math.sqrt(2)*4)<1e-14 and abs(quad['tdev']-math.sqrt(2/3)*16)<1e-14 and quad['mtie']==63**2-59**2,'values':quad}
    manual=statistics([0,1,0,-1,0,1,0,-1],2,1)
    expected={'adev':0.,'oadev':1.,'hdev':0.,'ohdev':math.sqrt(4/3),'mdev':math.sqrt(.5),'tdev':math.sqrt(2/3),'mtie':2.}
    controls['handworked_periodic_vector']={'pass':all(abs(manual[k]-v)<1e-14 for k,v in expected.items()),'values':manual,'analytic_expected':expected}
    controls['tolerance_detects_injected_error']={'pass':not close(1e-10+100*(ATOL+RTOL*1e-10),1e-10)}
    dump(run/'controls.json',controls)
    rows=[];events={'runs':[],'phase_roundtrip':[],'missing_samples':{'default_rejection':bool(not np.isfinite(raw).all()),'policy':'reject by default; explicit contiguous segments or recorded interpolation only','time_compression_forbidden':True},'capability':{'TimeLab ADEV':'OADEV','TimeLab HDEV':'OHDEV','nonoverlap TimeLab':'N/A documented interface lacks a separate mode'}}
    errors=[]
    for case in cases:
        name=case['name'];dt=case['dt_s'];x=validate_input(np.loadtxt(inputs/(name+'.csv')),dt); out=run/'timelab'/name
        print('RUN',name,flush=True);result=run_tl(inputs/(name+'.tim'),out,png=name in ['white_phase','quadratic_drift']);events['runs'].append({'fixture':name,**result})
        if not result['completed'] or result['returncode']!=0:errors.append(name+': TimeLab failed');continue
        if isinstance(manifest['versions']['timelab'],str) and manifest['versions']['timelab'].startswith('runtime banner'):
            import re
            found=re.search(r';Written by ([^\r\n]+)',(out/'roundtrip.tim').read_text(errors='replace'))
            manifest['versions']['timelab']=found.group(1) if found else 'UNKNOWN: banner absent'
            dump(run/'manifest.json',manifest)
        ph=load_csv(out/'phase.csv');phase_ok=len(ph)==len(x) and np.all(np.isfinite(ph[:,0])) and np.allclose(ph[:,0],x,rtol=2e-14,atol=1e-24)
        events['phase_roundtrip'].append({'fixture':name,'pass':bool(phase_ok),'samples':len(ph),'max_abs_error_s':float(np.max(np.abs(ph[:,0]-x))) if len(ph)==len(x) else None})
        if not phase_ok:errors.append(name+': phase import differs')
        ms=[m for m in GRID if m<=len(x)//8];taus=np.array(ms)*dt
        ctrl={m:statistics(x,m,dt) for m in ms}
        tl={s:load_csv(out/(s+'.csv')) for s in TL}
        events.setdefault('native_tau_grids',{})[name]={s:tl[s][:,0].tolist() for s in TL}
        for stat,fn in STATS.items():
            stat_ms=[m for m in ms if stat!='mtie' or m in MTIE_GRID];stat_taus=np.array(stat_ms)*dt
            try:t,a,e,nn=fn(x,rate=1/dt,data_type='phase',taus=stat_taus)
            except Exception as ex:errors.append(name+' '+stat+' AllanTools '+str(ex));continue
            if not np.array_equal(t,stat_taus):errors.append(name+' '+stat+': AllanTools tau mismatch')
            for i,m in enumerate(stat_ms):
                expected=ctrl[m][stat];tau=m*dt
                if i>=len(a):errors.append(name+' '+stat+': missing AllanTools tau');continue
                pairs=[('AllanTools vs Decimal',float(a[i]),expected)]
                if stat in TL:
                    native=tl[stat];found=np.where(np.isclose(native[:,0],tau,rtol=1e-12,atol=1e-12))[0] if len(native) else []
                    if len(found)!=1:errors.append(f'{name} {stat}: expected tau {tau} absent/duplicate');continue
                    v=float(native[found[0],1]);pairs.extend([('TimeLab vs Decimal',v,expected),('TimeLab vs AllanTools',v,float(a[i]))])
                for comparison,v,ref in pairs:
                    finite=math.isfinite(v) and math.isfinite(ref)
                    rows.append({'fixture':name,'statistic':stat,'comparison':comparison,'tau_s':tau,'m':m,'observed':v if finite else None,'reference':ref if finite else None,'absolute_error':abs(v-ref) if finite else 1e99,'relative_error':abs(v-ref)/max(abs(ref),ATOL) if finite else 1e99,'pass':close(v,ref)})
    unit_checks=[]
    lookup={(r['fixture'],r['statistic'],r['m']):r['observed'] for r in rows if r['comparison']=='TimeLab vs Decimal'}
    for case_name,dt in [('quarter_second',.25),('two_seconds',2.)]:
        for stat in TL:
            for m in GRID:
                key=(case_name,stat,m);base_key=('white_phase',stat,m)
                if key not in lookup or base_key not in lookup:continue
                expected_value=lookup[base_key] if stat in ['mtie','tdev'] else lookup[base_key]/dt
                passed=close(lookup[key],expected_value)
                unit_checks.append({'fixture':case_name,'statistic':stat,'m':m,'pass':passed})
    events['unit_scaling_checks']=unit_checks
    if not all(c['pass'] for c in unit_checks):errors.append('Unit/sample-rate scaling invariant failed')
    # Characterize naive NaNs in AllanTools; no dropping samples, no asserted equivalence.
    nan_at={}
    for stat,fn in STATS.items():
        try:
            with np.errstate(all='ignore'):v=fn(raw,rate=1,data_type='phase',taus=[1,8])[1]
            nan_at[stat]={'finite':np.isfinite(v).tolist(),'values':[float(z) if math.isfinite(z) else None for z in v]}
        except Exception as ex:nan_at[stat]={'exception':str(ex)}
    events['missing_samples']['allantools_raw_nan']=nan_at
    guard_tests={}
    for label,values,ts in [('nan',raw,np.arange(len(raw))),('missing_timestamps',raw[mask],np.arange(len(raw))[mask]),('duplicate_timestamp',np.zeros(32),np.r_[np.arange(31),30])]:
        try:validate_input(values,1.,ts);guard_tests[label]={'pass':False,'error':'ACCEPTED invalid input'}
        except ValueError as ex:guard_tests[label]={'pass':True,'rejection':str(ex)}
    events['missing_samples']['input_guard_tests']=guard_tests
    if not all(g['pass'] for g in guard_tests.values()):errors.append('input guard accepted missing data')
    if not args.skip_nan_probe:
        probe=run/'probe-prefix';subprocess.run(['cp','-a','--reflink=auto',str(BASE.parent/'.wine-timelab'),str(probe)],check=True)
        control=run_tl(inputs/'white_phase.tim',run/'nan-probe-finite-control',prefix=probe,timeout=60)
        events['missing_samples']['timelab_probe_finite_control']=control
        if not control['completed']:errors.append('fresh-prefix finite probe control did not complete; NaN probe inconclusive')
        tim(raw,1,inputs/'raw_nan_probe.tim','RAW NAN PROBE - UNSUPPORTED')
        pr=run_tl(inputs/'raw_nan_probe.tim',run/'nan-probe',prefix=probe,timeout=60)
        env=os.environ.copy();env['WINEPREFIX']=str(probe);subprocess.run(['/usr/lib/x86_64-linux-gnu/wine/wineserver','-k'],env=env,capture_output=True)
        phase=load_csv(run/'nan-probe/phase.csv')
        events['missing_samples']['timelab_raw_nan_probe']={**pr,'exported_phase_count':len(phase),'exported_nonfinite':int(np.sum(~np.isfinite(phase))) if len(phase) else None,'values_at_missing_indices':[float(z) if math.isfinite(z) else None for z in phase[np.where(~mask)[0],0]] if len(phase)==len(raw) else None,'interpretation':'diagnostic only; not an endorsed missing-data estimator; production guard rejects raw NaNs'}
            # Only this unique, task-owned clone is removed; the production prefix is preserved.
        import shutil
        shutil.rmtree(probe)
        events['missing_samples']['probe_prefix_cleanup']='removed temporary clone after targeted wineserver shutdown'
    else:events['missing_samples']['timelab_raw_nan_probe']='NOT_RUN explicitly skipped'
    failed=[r for r in rows if not r['pass']]
    summary={'status':'PASS' if not failed and not errors and all(c['pass'] for c in controls.values()) else 'FAIL','fixtures':len(cases),'comparisons':len(rows),'failed_points':len(failed),'execution_errors':errors,'analytic_controls_pass':all(c['pass'] for c in controls.values()),'max_absolute_error':max((r['absolute_error'] for r in rows),default=None),'max_relative_error_with_atol_floor':max((r['relative_error'] for r in rows),default=None),'max_relative_error_where_relative_term_dominates':max((r['relative_error'] for r in rows if r['reference'] is not None and abs(r['reference'])>=ATOL/RTOL),default=None),'rtol':RTOL,'atol':ATOL,'unavailable':['TimeLab non-overlapping ADEV','TimeLab non-overlapping HDEV'],'scope':'offline finite regularly sampled input; no apparatus/driver validation','gap_input_policy':'raw NaN/nonuniform input rejected; explicit segments/interpolation tested; native raw-NaN probe is characterization only'}
    events['discrepancy_diagnosis']={'policy':'No authority assumed. Inspect each TimeLab/AllanTools/Decimal triple. All numerical failures remain FAIL; tolerances are never relaxed automatically.','numeric_failed_points':len(failed),'analytic_controls':controls}
    dump(run/'summary.json',summary);dump(run/'events.json',events);dump(run/'results.json',rows)
    if rows:
        with (run/'results.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
        report(run,summary,rows,cases,events)
    print(json.dumps(summary,indent=2));print('REPORT',run/'report.html',flush=True)
    return 0 if summary['status']=='PASS' else 1
if __name__=='__main__':sys.exit(main())
