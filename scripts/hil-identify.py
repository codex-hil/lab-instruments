#!/usr/bin/env python3
"""Read-only commissioning check; no resets, output writes or measurements."""
import concurrent.futures
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from labinstruments.transport import Transport
from labinstruments.drivers import Driver
cfg=json.loads(Path(sys.argv[1]).read_text())
def probe(item):
    name,spec=item;t=time.monotonic()
    try:
        with Transport(spec['transport']) as io:
            r={'name':name,'identity':Driver(io,spec['model'],spec.get('serial')).identify()}
    except Exception as e:r={'name':name,'error':str(e)}
    r['seconds']=round(time.monotonic()-t,3);return r
# Serial by default: configurations may alias a single physical port.
results=[probe(item) for item in cfg['devices'].items()]
print(json.dumps({'test':'identity only; outputs unchanged','results':results},indent=2))
raise SystemExit(any('error' in r for r in results))
