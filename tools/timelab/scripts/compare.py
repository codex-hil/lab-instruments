#!/usr/bin/env python3
import sys,json
from pathlib import Path
import numpy as np,allantools
x=np.loadtxt(sys.argv[1]); out=Path(sys.argv[2]); report={}
for name,fn in [('adev',allantools.oadev),('tdev',allantools.tdev)]:
    a=np.loadtxt(out/(name+'.csv'),delimiter=',')
    t,d,e,n=fn(x,rate=1,data_type='phase',taus=a[:,0])
    assert np.array_equal(t,a[:,0])
    err=np.abs(a[:,1]-d)/d
    report[name]={'bins':len(t),'max_relative_error':float(max(err)),'pass':bool(max(err)<1e-5)}
    np.savetxt(out/(name+'-allantools.csv'),np.column_stack([t,d,a[:,1],err]),delimiter=',',header='tau,allantools,timelab,relative_error')
report['allantools_version']=allantools.__version__
(out/'comparison.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
assert report['adev']['pass'] and report['tdev']['pass']
