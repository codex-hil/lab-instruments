"""Deterministic, noninteractive HIL removable storage CLI."""
import argparse
import json
import os
from pathlib import Path
import signal
import sys
from .storage import (RemovableStorage, MockRemovableStorage, SDWireStorage,
                      StorageError, discover_sdwire, commissioned_reader_candidate, fail, token)

EXIT = {'CONFIG': 2, 'LOCKED': 3, 'LOCK': 3, 'IDENTITY': 4,
        'OFF_UNSUPPORTED': 5, 'DUT_NOT_QUIESCED': 5, 'UNSAFE_SWITCH': 5,
        'RECOVERY_REQUIRED': 5, 'NO_CARD': 6, 'NO_PARTITION': 6,
        'CAPACITY': 7, 'IMAGE': 7, 'VERIFY': 8, 'INTERRUPTED': 130}


def load(path):
    try:
        data = json.loads(Path(path).read_text())
        entries = data.get('storage')
        if entries is None and 'dut' in data:
            entries = {data['dut']['name']: data['dut']['storage']}
        if not isinstance(entries, dict):
            fail('CONFIG', 'Expected storage mapping or dut.name/dut.storage')
        seen = set()
        for name, config in entries.items():
            token(name)
            serial = token(config['serial'])
            if serial in seen:
                fail('CONFIG', 'Duplicate serial aliases are not allowed')
            seen.add(serial)
            if config['backend'] not in {'sdwire', 'mock'}:
                fail('CONFIG', 'Unsupported storage backend')
        return entries
    except (OSError, ValueError, KeyError, TypeError) as e:
        fail('CONFIG', f'Invalid config: {e}')


def create(name, cfg, runtime):
    if cfg['backend'] == 'mock':
        backend = MockRemovableStorage(cfg['serial'], Path(runtime) / 'mock',
                                       cfg.get('capacity', 67108864), cfg.get('faults', []))
    else:
        backend = SDWireStorage(cfg['serial'], cfg.get('vid', '04e8'),
                                cfg.get('pid', '6001'), cfg.get('reader'))
    return RemovableStorage(name, backend, runtime)


def main(argv=None):
    parser = argparse.ArgumentParser(prog='hil-storage')
    parser.add_argument('--config', default=os.environ.get('HIL_STORAGE_CONFIG', str(Path.home() / '.config/hil-storage.json')))
    parser.add_argument('--runtime', default=os.environ.get('HIL_STORAGE_RUNTIME',
                        str(Path.home() / '.local/state/hil-storage')))
    parser.add_argument('--json', action='store_true')
    parser.add_argument('name', help='alias, or list, discover, bringup')
    parser.add_argument('--report', help='new directory for bring-up inventory and configuration')
    parser.add_argument('--alias', help='bringup alias; requires exactly one discovered device')
    parser.add_argument('operation', nargs='?', choices=['status', 'host', 'target', 'off',
                        'device', 'partitions', 'mount', 'flash', 'recover'])
    parser.add_argument('image', nargs='?')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--verify', action='store_true')
    parser.add_argument('--partition', default='boot')
    parser.add_argument('--copy', nargs=2, action='append', default=[], metavar=('SOURCE', 'DEST'))
    args = parser.parse_args(argv)
    def interrupt(signum, frame):
        raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM, interrupt)
    try:
        if args.name == 'bringup':
            if not args.report:
                fail('CONFIG', 'bringup requires --report NEW_DIRECTORY')
            devices = discover_sdwire()
            if args.alias and len(devices) != 1:
                fail('IDENTITY', '--alias requires exactly one discovered SDWire')
            entries = {}
            for i, device in enumerate(sorted(devices, key=lambda d: d['serial'] or '')):
                name = token(args.alias) if args.alias else f'sdwire-{i+1:02d}'
                serial = token(device['serial'])
                if serial in {entry['serial'] for entry in entries.values()}:
                    fail('IDENTITY', 'Duplicate hardware serial; do not program EEPROM automatically')
                entries[name] = {key: device[key] for key in ['backend', 'serial', 'vid', 'pid']}
                storage = create(name, entries[name], args.runtime)
                try:
                    reader = commissioned_reader_candidate(storage.backend)
                    entries[name]['reader'] = reader
                    storage.backend.reader = reader
                except StorageError as e:
                    device['reader_error'] = {'code': e.code, 'message': str(e)}
                try:
                    with storage:
                        device['status'] = storage.info()
                        device['partitions'] = storage.partitions() if storage.backend.reader else []
                except StorageError as e:
                    device['error'] = {'code': e.code, 'message': str(e)}
                device['mode_tests'] = 'BLOCKED_OFF_UNSUPPORTED'
                device['write_test'] = 'NOT_RUN'
            result = {'devices': devices, 'validation': 'REQUIRES HARDWARE',
                      'result': 'BLOCKED_OFF_UNSUPPORTED' if devices else 'NO_DEVICE',
                      'configuration': str(Path(args.report) / 'storage.json')}
            report = Path(args.report)
            report.mkdir(parents=True, exist_ok=False)
            (report / 'storage.json').write_text(json.dumps({'storage': entries}, indent=2)+'\n')
            (report / 'report.json').write_text(json.dumps(result, indent=2)+'\n')
            print(json.dumps({'ok': False, **result}, sort_keys=True))
            return 5 if devices else 6
        elif args.name == 'discover':
            result = {'devices': discover_sdwire(), 'validation': 'REQUIRES HARDWARE'}
        else:
            entries = {} if args.name == 'list' and not Path(args.config).exists() else load(args.config)
            if args.name == 'list':
                devices = []
                for name, cfg in sorted(entries.items()):
                    storage = create(name, cfg, args.runtime)
                    try:
                        with storage:
                            devices.append(storage.info())
                    except StorageError as e:
                        devices.append({'storage': name, 'backend': cfg['backend'],
                                        'serial': cfg['serial'], 'state': 'unknown',
                                        'error': {'code': e.code, 'message': str(e)}})
                known = {c['serial'] for c in entries.values()}
                devices.extend(d | {'storage': None} for d in discover_sdwire() if d['serial'] not in known)
                result = {'devices': devices}
            else:
                if args.name not in entries or args.operation is None:
                    fail('CONFIG', 'Specify a configured alias and operation')
                storage = create(args.name, entries[args.name], args.runtime)
                with storage:
                    op = args.operation
                    if op == 'recover':
                        storage.recover()
                        result = storage.info()
                    elif op == 'flash':
                        if not args.image:
                            fail('CONFIG', 'flash requires IMAGE')
                        result = storage.flash(args.image, args.dry_run, args.verify)
                    elif op == 'device':
                        result = storage.block_device()
                    elif op == 'partitions':
                        result = {'partitions': storage.partitions()}
                    elif op == 'mount':
                        # A bounded transaction, never leaves an unlocked mounted filesystem.
                        with storage.host(args.partition) as sd:
                            for source, destination in args.copy:
                                sd.copy(source, destination)
                            result = {'mount': str(sd.root), 'partitions': storage.partitions(),
                                      'simulated': storage.backend.simulated}
                        result['state'] = 'off'
                        result['mounted'] = False
                    else:
                        if op == 'host':
                            storage.acquire_host()
                        elif op == 'target':
                            storage.acquire_target()
                        elif op == 'off':
                            storage.disconnect()
                        result = storage.info()
        if args.json:
            print(json.dumps({'ok': True, **result}, sort_keys=True))
        elif 'devices' in result:
            print('NAME\tTYPE\tSERIAL\tSTATE')
            for d in result['devices']:
                print(f"{d.get('storage') or '-'}\t{d['backend']}\t{d['serial']}\t{d['state']}")
        else:
            print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except BaseException as e:
        if isinstance(e, (SystemExit, GeneratorExit)):
            raise
        code = 'INTERRUPTED' if isinstance(e, KeyboardInterrupt) else getattr(e, 'code', 'IO')
        error = {'ok': False, 'storage': args.name, 'error': {'code': code, 'message': str(e) or code}}
        print(json.dumps(error, sort_keys=True), file=sys.stdout if args.json else sys.stderr)
        return EXIT.get(code, 9)


if __name__ == '__main__':
    sys.exit(main())
