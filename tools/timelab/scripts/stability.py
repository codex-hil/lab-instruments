#!/usr/bin/env python3
import subprocess,time,json,hashlib
from pathlib import Path
b=Path('/home/timelab/wr-timing'); results=[]
for i in range(10):
    out=b/'results'/f'repeat-{i+1:02d}';t=time.monotonic()
    r=subprocess.run([str(b/'scripts/timelab-run'),'export',str(b/'evidence/imported-pps.tim'),str(out)],capture_output=True,text=True,timeout=110)
    row={'run':i+1,'returncode':r.returncode,'seconds':time.monotonic()-t}
    if r.returncode==0:
        c=subprocess.run([str(b/'venv/bin/python'),str(b/'scripts/compare.py'),str(b/'evidence/synthetic-pps-seconds.txt'),str(out)],capture_output=True,text=True)
        row['comparison_pass']=c.returncode==0
        row['csv_sha256']={n:hashlib.sha256((out/(n+'.csv')).read_bytes()).hexdigest() for n in ['adev','tdev']}
    results.append(row);print(json.dumps(row),flush=True)
    (b/'results/stability.json').write_text(json.dumps(results,indent=2))
assert all(r['returncode']==0 and r.get('comparison_pass') for r in results)
