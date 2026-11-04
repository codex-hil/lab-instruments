"""labinst fra: same inventory, semantic drivers and JSON preset for every frontend."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import re
import signal
import sys
import threading
from .fra_engine import FRAConfig,FRAEngine,InstrumentSession
from .fra_export import save
from .fra_simulation import Simulation
from .fra_web import make_server
from .service import load_config


def quantity(text):
    m=re.fullmatch(r'([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)([kMGmunµ]?)(Hz|V|Vpp|Sa/s)?',str(text))
    if not m:raise argparse.ArgumentTypeError('use a number with optional k/M/G/m/u/n prefix and Hz/V/Vpp/Sa/s')
    return float(m[1])*{'':1,'k':1e3,'M':1e6,'G':1e9,'m':1e-3,'u':1e-6,'µ':1e-6,'n':1e-9}[m[2]]


def main(argv=None):
    parser=argparse.ArgumentParser(prog='labinst fra');subs=parser.add_subparsers(dest='verb',required=True)
    for name in ('sweep','measure','gui'):
        p=subs.add_parser(name);p.add_argument('--config',help='existing labinst instrument inventory JSON')
        p.add_argument('--preset',help='shared FRAConfig JSON');p.add_argument('--simulate',action='store_true',help='explicit deterministic RC fixture; no hardware')
        p.add_argument('--source');p.add_argument('--input');p.add_argument('--response',dest='response',help='scope output endpoint, e.g. scope:ch2')
        p.add_argument('--start',type=quantity);p.add_argument('--stop',type=quantity)
        if name=='measure':p.add_argument('--frequency',type=quantity,required=True)
        group=p.add_mutually_exclusive_group();group.add_argument('--points',type=int);group.add_argument('--points-per-decade',type=float)
        p.add_argument('--spacing',choices=['log','linear']);p.add_argument('--amplitude',type=quantity,help='programmed AWG Vpp (e.g. 100mV)')
        p.add_argument('--averages',type=int);p.add_argument('--cycles',type=float);p.add_argument('--settling-cycles',type=float)
        p.add_argument('--sample-rate',type=lambda x:'auto' if x=='auto' else quantity(x));p.add_argument('--samples-per-cycle',type=float)
        p.add_argument('--volts-per-div',type=quantity);p.add_argument('--minimum-input-rms',type=quantity)
        p.add_argument('--save-preset')
        if name=='gui':
            p.add_argument('--port',type=int,default=8850);p.add_argument('--results-dir',default='local/fra')
        else:
            p.add_argument('--output',help='JSON result filename');p.add_argument('--csv');p.add_argument('--png');p.add_argument('--svg')
    p=subs.add_parser('export');p.add_argument('result');p.add_argument('--output',required=True,help='.csv/.png/.svg/.json')
    p=subs.add_parser('compare');p.add_argument('result');p.add_argument('--kind',choices=['loopback','rc'],required=True)
    p.add_argument('--resistance',type=float);p.add_argument('--capacitance',type=float);p.add_argument('--output')
    p.add_argument('--gain-tolerance-db',type=float,default=.5);p.add_argument('--phase-tolerance-deg',type=float,default=5);p.add_argument('--cutoff-tolerance-percent',type=float,default=5)
    a=parser.parse_args(argv)
    if a.verb=='compare':
        from .fra_validation import compare
        result=compare(json.loads(Path(a.result).read_text()),a.kind,a.resistance,a.capacitance,a.gain_tolerance_db,a.phase_tolerance_deg,a.cutoff_tolerance_percent)
        data=json.dumps(result,indent=2,allow_nan=False)+'\n'
        if a.output:Path(a.output).write_text(data)
        else:print(data,end='')
        return 0 if result['comparison_status']=='PASS' else 2
    if a.verb in ('sweep','measure'):
        for arg,extension in [('output','json'),('csv','csv'),('png','png'),('svg','svg')]:
            if getattr(a,arg) and Path(getattr(a,arg)).suffix.lower()!='.'+extension:parser.error('--'+arg+' requires .'+extension)

    if a.verb=='export':save(json.loads(Path(a.result).read_text()),a.output);return 0
    cfg=json.loads(Path(a.preset).read_text()) if a.preset else {}
    for arg,key in [('source','source'),('input','input'),('response','output'),('start','start_frequency'),('stop','stop_frequency'),
                    ('points','points'),('points_per_decade','points_per_decade'),('spacing','spacing'),('amplitude','amplitude'),('averages','averages'),
                    ('cycles','cycles_per_record'),('settling_cycles','settling_cycles'),('sample_rate','sample_rate'),('samples_per_cycle','samples_per_cycle'),
                    ('volts_per_div','volts_per_div'),('minimum_input_rms','minimum_input_rms')]:
        if getattr(a,arg,None) is not None:cfg[key]=getattr(a,arg)
    if a.points_per_decade is not None:cfg['points']=None
    if a.verb=='measure':cfg.update(start_frequency=a.frequency,stop_frequency=a.frequency,points=1)
    c=FRAConfig.from_dict(cfg)
    if a.save_preset:Path(a.save_preset).write_text(json.dumps(asdict(c),indent=2)+'\n')
    if a.simulate:factory=Simulation
    else:
        if not a.config:parser.error('--config required for hardware; --simulate for software fixture')
        inventory=load_config(a.config);factory=lambda config:InstrumentSession(inventory,config)
    engine=FRAEngine(factory)
    if a.verb=='gui':
        server=make_server(engine,c,port=a.port,results_dir=a.results_dir)
        print(f'FRA GUI: http://127.0.0.1:{server.server_port} ({"SIMULATION" if a.simulate else "hardware"}, UNTRUSTED)',flush=True)
        def stop(*args):raise KeyboardInterrupt
        signal.signal(signal.SIGTERM,stop)
        try:server.serve_forever(poll_interval=.2)
        except KeyboardInterrupt:pass
        finally:server.jobs.close();server.server_close()
        return 0
    cancel=threading.Event()
    previous={s:signal.signal(s,lambda *args:cancel.set()) for s in (signal.SIGINT,signal.SIGTERM)}
    def event(e):
        if e['type']=='point':print(f"{e['index']}/{e['total']} {e['point']['frequency_hz']:.7g} Hz: {e['point']['status']}",file=sys.stderr)
    try:result=engine.run(c,cancel,event)
    finally:
        for s,h in previous.items():signal.signal(s,h)
    if a.output:
        if Path(a.output).suffix.lower()!='.json':parser.error('--output must be .json; use --csv/--png/--svg for plots')
        save(result,a.output)
    else:print(json.dumps(result,indent=2,allow_nan=False))
    for kind in ('csv','png','svg'):
        if getattr(a,kind):
            if Path(getattr(a,kind)).suffix.lower()!='.'+kind:parser.error('--'+kind+' needs .'+kind+' filename')
            save(result,getattr(a,kind))
    return 0 if result['status']=='completed' else 2
