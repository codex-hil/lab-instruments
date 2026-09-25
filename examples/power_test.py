"""Run only on a commissioned test fixture. Server policy remains authoritative."""
import argparse
import time
from labinstruments.client import Client
p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--token-file',required=True);p.add_argument('--ca-file',required=True);p.add_argument('--device',default='supply');a=p.parse_args()
c=Client(a.url,a.token_file,a.ca_file)
print(c.identify(a.device))
try:
    # Each apply turns the previous output off before changing setpoints.
    for voltage in [1,2,3]:
        print(c.apply(a.device,channel=1,voltage=voltage,current=.01,enable=True))
        for _ in range(3):
            time.sleep(1);c.renew(a.device)
            print(c.read(a.device,'voltage'))
finally:
    print(c.off(a.device))
