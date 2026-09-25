#!/usr/bin/env python3
"""Offline deterministic Python zipapp, identical archive bytes on all architectures."""
import compileall
import hashlib
from pathlib import Path
import subprocess
import sys
import zipfile
root=Path(__file__).resolve().parents[1]
subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=root,check=True)
if not compileall.compile_dir(root/'labinstruments',quiet=1):raise SystemExit(1)
out=root/'dist';out.mkdir(exist_ok=True)
artifact=out/'labinst.pyz'
with artifact.open('wb') as f:f.write(b'#!/usr/bin/env python3\n')
with zipfile.ZipFile(artifact,'a',compression=zipfile.ZIP_STORED) as z:
    files={str(p.relative_to(root)):p.read_bytes() for p in (root/'labinstruments').glob('*.py')}
    files['__main__.py']=b'from labinstruments.__main__ import main\nmain()\n'
    for name,data in sorted(files.items()):
        item=zipfile.ZipInfo(name,(2020,1,1,0,0,0));item.external_attr=0o644<<16;z.writestr(item,data)
artifact.chmod(0o755)
digest=hashlib.sha256(artifact.read_bytes()).hexdigest()
(out/'SHA256SUMS').write_text(digest+'  labinst.pyz\n');print(digest,artifact)
