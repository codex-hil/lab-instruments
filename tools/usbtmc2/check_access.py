#!/usr/bin/env python3
"""Read identity and output state through the existing driver, under shared locks."""
import argparse
from contextlib import ExitStack
import fcntl
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from labinstruments.drivers import Driver
from labinstruments.transport import Transport


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT / 'examples/usb-tsmc2-client.json')
    args = parser.parse_args()
    spec = json.loads(args.config.read_text())['devices']['awg_usbtsmc2']
    with ExitStack() as stack:
        for name in sorted(('rpi-7379fa4619d5d5f0.lock', 'instrument-mp750288-1944201.lock')):
            path = Path.home() / '.cache' / name
            path.parent.mkdir(exist_ok=True)
            handle = stack.enter_context(path.open('a'))
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                print('Busy: ' + str(path), file=sys.stderr)
                return 75
        with Transport(spec['transport']) as io:
            driver = Driver(io, spec['model'], spec['serial'])
            result = {'identity': driver.identify(), 'outputs': {
                'ch1': io.query('OUTP1?'), 'ch2': io.query('OUTP2?')},
                'url': spec['transport']['url'], 'slot': spec['transport']['slot'],
                'commands': ['*IDN?', 'OUTP1?', 'OUTP2?'], 'settings_changed': False}
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
