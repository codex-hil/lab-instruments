#!/usr/bin/env python3
"""Real FCA3003 smoke test; configures acquisition, never enables other sources."""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import platform
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from labinstruments.fca3003 import FCA3003
from labinstruments.transport import Transport, usb_devices


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--usb-serial')
    source.add_argument('--transport-json', help='path to Transport configuration (may reference credentials)')
    parser.add_argument('--serial', help='expected SCPI serial, if different from USB serial')
    parser.add_argument('--channel', type=int, default=6, choices=(1, 2, 3, 4, 6))
    parser.add_argument('--expected-hz', type=float, default=10e6)
    parser.add_argument('--relative-tolerance', type=float, default=1e-4)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if not math.isfinite(args.expected_hz) or args.expected_hz <= 0:
        parser.error('--expected-hz must be finite and positive')
    if not math.isfinite(args.relative_tolerance) or args.relative_tolerance <= 0:
        parser.error('--relative-tolerance must be finite and positive')
    config = (json.loads(Path(args.transport_json).read_text()) if args.transport_json else
              {'kind': 'usb', 'serial': args.usb_serial, 'timeout': 4})
    report = {'timestamp_utc': datetime.now(timezone.utc).isoformat(),
              'simulated': False, 'platform': platform.platform(),
              'python': platform.python_version(), 'transport_kind': config['kind'],
              'channel': args.channel, 'expected_hz': args.expected_hz,
              'relative_tolerance': args.relative_tolerance, 'passed': False,
              'scope': 'Scalar frequency smoke; not calibration or full input validation.'}
    if config['kind'] == 'usb': report['usb_inventory'] = usb_devices()
    try:
        with Transport(config) as io:
            driver = FCA3003(io, args.serial)
            report['identity'] = driver.identify()
            report['measurements_hz'] = [driver.measure('frequency', args.channel) for _ in range(3)]
            report['passed'] = all(math.isclose(value, args.expected_hz,
                                      rel_tol=args.relative_tolerance)
                                   for value in report['measurements_hz'])
    except Exception as error:
        report['error'] = {'type': type(error).__name__, 'message': str(error)}
    Path(args.output).write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
