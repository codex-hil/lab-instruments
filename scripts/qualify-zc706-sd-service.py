#!/usr/bin/env python3
"""Observe autonomous ZC706 SD startup and test SFP under shared board/storage leases."""
import argparse,fcntl,json,subprocess,time,ipaddress
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--host',required=True,type=ipaddress.ip_address)
parser.add_argument('--output',required=True,type=Path)
parser.add_argument('--image-sha256',required=True)
parser.add_argument('--project',type=Path,default=Path.home()/'kasli-soc-linux')
args=parser.parse_args()
out=args.output;out.mkdir(parents=True,exist_ok=False)
leases=[];record={'result':'FAIL','sd_image_sha256':args.image_sha256,'host':str(args.host),'status_snapshots':[],'cold_power_cycle_tested':False}
ssh=['ssh','-i',str(args.project/'build/ssh/id_ed25519'),'-o','BatchMode=yes','-o','ConnectTimeout=5','-o','StrictHostKeyChecking=accept-new','-o','UserKnownHostsFile='+str(out.resolve()/'known_hosts'),'-o','HostKeyAlias=zc706-sdwire-mode-fix-20261027','root@'+str(args.host)]
def command(text,timeout=15):
 r=subprocess.run(ssh+[text],capture_output=True,text=True,timeout=timeout)
 if r.returncode:raise RuntimeError(r.stderr+r.stdout)
 return r.stdout
try:
 for p in [Path.home()/'.cache/zc706-210251842914.lock',Path.home()/'.local/state/hil-storage/hil-storage-DP04I33Y.lock']:
  f=p.open('a');leases.append(f);fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
 assert command('hostname').strip()=='zc706-linux'
 (out/'uname.log').write_text(command('uname -a; ip -4 addr show eth0; cat /proc/mounts'))
 deadline=time.monotonic()+160;locked_start=None
 while time.monotonic()<deadline:
  r=subprocess.run(ssh+['cat /run/zc706-integrated/pll.status.json'],capture_output=True,text=True,timeout=15)
  if r.returncode:time.sleep(2);continue
  state=json.loads(r.stdout)
  if state['state']!='running':raise RuntimeError('PLL service reports '+json.dumps(state))
  record['status_snapshots'].append(state)
  if all(card['last']['locked'] for card in state['cards'].values()):
   if locked_start is None:locked_start=time.monotonic()
   if time.monotonic()-locked_start>=40:break
  else:locked_start=None
  time.sleep(2)
 else:raise RuntimeError('Automatic dual lock not held for 40 seconds')
 log=command('cat /run/zc706-integrated/service.log');(out/'service.log').write_text(log)
 assert 'PASS: PL SODIMM init/leveling, GP1 smoke/address test, 3 whole-1-GiB BIST passes' in log
 record['ddr_bist']='PASS';record['autonomous_pll_lock_observed_seconds']=time.monotonic()-locked_start
 base='cd /opt/zc706-integrated && python3 sfp_probe.py --csr-json /etc/litex/csr.json --output /run/zc706-integrated/sfp-health.json >/run/zc706-integrated/sfp-health.log && cat /run/zc706-integrated/sfp-health.json'
 before=json.loads(command(base,30));(out/'sfp-before.json').write_text(json.dumps(before,indent=2)+'\n')
 subprocess.run(['python3',str(args.project/'tools/test_sfp_network.py'),'--repeat','50','--output',str(out/'network.json')],check=True,timeout=120)
 after=json.loads(command(base,30));(out/'sfp-after.json').write_text(json.dumps(after,indent=2)+'\n')
 fields=['mac_status_crc_errors','mac_status_preamble_errors','sfp_status_clock_faults']
 record['network_error_deltas']={n:(after['status'][n]-before['status'][n])&0xffffffff for n in fields}
 assert not any(record['network_error_deltas'].values())
 record['final_status']=json.loads(command('cat /run/zc706-integrated/pll.status.json'))
 assert record['final_status']['state']=='running' and all(card['last']['locked'] for card in record['final_status']['cards'].values())
 record.update(result='PASS',sdwire_retained='DUT',runtime_retained='continuous dual PLL service',jtag_pl_loaded=False)
except Exception as exc:record['error']=str(exc)
finally:
 (out/'result.json').write_text(json.dumps(record,indent=2)+'\n')
 for f in reversed(leases):f.close()
print(json.dumps({k:v for k,v in record.items() if k not in ['status_snapshots','final_status']},indent=2))
