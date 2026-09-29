#!/usr/bin/env python3
"""Loopback-only dashboard fixture using recorded identities; never opens USB."""
import argparse
import json
from pathlib import Path
import sys
from unittest.mock import patch

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from labinstruments.service import Gateway, make_server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--token-file', required=True, help='Existing test token, at least 32 characters')
    parser.add_argument('--port', type=int, default=8841)
    args = parser.parse_args()
    report = root / 'reports/rpi-gateway-2026-09-29'
    recorded = json.loads((report / 'status.json').read_text())
    identities = json.loads((report / 'identification.json').read_text())
    cfg = dict(mode='usb-gateway', listen=['127.0.0.1', args.port],
               token_file=str(Path(args.token_file).absolute()),
               slots={name: dict(slot['selectors'], label=slot['label'])
                      for name, slot in recorded['slots'].items()})

    class RecordedUSB:
        def __init__(self, config):
            self.slot = next(name for name, spec in cfg['slots'].items()
                             if spec['serial'] == config['serial'])

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def transaction(self, data, reply):
            if data != b'*IDN?\n' or not reply:
                raise ValueError('fixture permits only IDN queries')
            return identities[self.slot]['identity'].encode('ascii') + b'\n'

    class RecordedGateway(Gateway):
        def snapshot(self):
            result = super().snapshot()
            result['gateway']['hostname'] = 'Fixture USBTMC (no hardware)'
            for slot in result['slots'].values():
                slot['accessible'] = slot['connected']
            return result

    app = RecordedGateway(cfg, RecordedUSB)
    app.status = {name: slot['status'] for name, slot in recorded['slots'].items()}
    app.events.extend(recorded['events'])
    with patch('labinstruments.service.usb_devices', return_value=recorded['usb']):
        server = make_server(cfg, app, development=True)
        print(f'Fixture without hardware: http://127.0.0.1:{server.server_port}', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()


if __name__ == '__main__':
    main()
