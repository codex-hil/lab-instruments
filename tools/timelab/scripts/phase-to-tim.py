#!/usr/bin/env python3
"""Wrap one phase-error sample in seconds per line in a known TimeLab header, at 1 Hz."""
import sys,math
from pathlib import Path
base=Path('/home/timelab/wr-timing')
values=[float(s) for s in Path(sys.argv[1]).read_text().split()]
assert len(values)>=16 and all(math.isfinite(x) for x in values)
template=(base/'app/userdocs/TimeLab/Examples/HP_5370B_ADEV_floor.tim').read_text()
h=template[:template.index('TIC 30000')]
replacements={'CAP':'Imported phase seconds, 1 Hz','NOT':'Offline ASCII import; template instrument metadata is not evidence of acquisition','IFN':str(Path(sys.argv[1]).resolve()),'PER':'1','NOM':'1','DAQ':'0','UNW':'1','WIN':str(len(values))}
lines=[]
for l in h.splitlines():
    k=l.split(' ',1)[0]
    if k in replacements: l=k+' '+replacements[k]
    lines.append(l)
Path(sys.argv[2]).write_text('\n'.join(lines)+'\nTIC '+str(len(values))+'\n'+'\n'.join(format(v,'.17e') for v in values)+'\n')
