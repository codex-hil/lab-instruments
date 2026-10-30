#!/usr/bin/env python3
"""Single-plug cooperative reservation and MQTT control; JSON output."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time

DEVICE = '0xa4c1386c56ee225b'
ROOT = Path.home() / '.local/share/hil-plug'
MQTT = '/nix/store/mpmyyx77pcfi4vdzhnagg62fdlfbhqq5-mosquitto-2.1.2/bin/'
TOPIC = 'zigbee-poc/' + DEVICE


def run(args):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=25).stdout


def mqtt(tool):
    return [MQTT + 'mosquitto_' + tool, '-o', '/dev/null', '-h', '127.0.0.1', '-p', '18884']


def publish(suffix, payload):
    run(mqtt('pub') + ['-q', '1', '-t', TOPIC + suffix, '-m', json.dumps(payload)])


def store(path, value):
    tmp = path.with_suffix('.tmp')
    with tmp.open('w') as f:
        json.dump(value, f)
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)
    fd = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def execute(a):
    ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (ROOT / 'operation.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = ROOT / 'lease.json'
        lease = json.loads(path.read_text()) if path.exists() else None
        if a.action == 'reservation':
            return {'lease': {k: v for k, v in lease.items() if k != 'token'} if lease else None}
        if a.action == 'reserve':
            if not a.owner:
                raise ValueError('--owner must identify the thread and purpose')
            if lease:
                raise ValueError('LEASE_BUSY: ' + lease['owner'])
            lease = {'owner': a.owner, 'token': secrets.token_hex(24), 'created_at': time.time(), 'device': DEVICE}
            store(path, lease)
            return lease
        token = a.token or os.environ.get('HIL_PLUG_TOKEN', '')
        if not lease or not secrets.compare_digest(lease['token'], token):
            raise ValueError('LEASE_REQUIRED: reserve and supply --token or HIL_PLUG_TOKEN')
        if a.action == 'release':
            store(path, None)
            return {'released': True, 'power_changed': False}
        if run(['systemctl', '--user', 'is-active', 'zigbee-poc.service']).strip() != 'active':
            raise ValueError('Z2M_OFFLINE')
        devices = json.loads(run(mqtt('sub') + ['-t', 'zigbee-poc/bridge/devices', '-C', '1', '-W', '5']))
        device = next((d for d in devices if d.get('ieee_address') == DEVICE), None)
        if not device or device.get('manufacturer') != '_TZ3000_xzhnra8x' or device.get('friendly_name') != DEVICE:
            raise ValueError('IDENTITY_MISMATCH')
        if a.action in ('on', 'off'):
            # Audit intent before publishing; never retained and never TOGGLE.
            with (ROOT / 'audit.jsonl').open('a') as f:
                f.write(json.dumps({'time': time.time(), 'owner': lease['owner'], 'action': a.action, 'device': DEVICE}) + '\n')
                f.flush()
                os.fsync(f.fileno())
            publish('/set', {'state': a.action.upper()})
            return {'requested_state': a.action.upper(), 'mqtt_delivered': True,
                    'physical_state_confirmed': False, 'next': 'status'}
        # Fresh MQTT publication; Z2M may merge old measurement fields into it.
        proc = subprocess.Popen(mqtt('sub') + ['-t', TOPIC, '-R', '-C', '1', '-W', str(a.timeout)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            if a.action in ('status', 'power'):
                time.sleep(0.4)
                publish('/get', {'state': ''})
            output, err = proc.communicate(timeout=a.timeout + 3)
            if proc.returncode or not output.strip():
                raise ValueError('NO_REPORT: no live publication within timeout; values unknown')
            data = json.loads(output)
            return {'device': DEVICE, 'received_at': time.time(),
                    'state': data.get('state', 'UNKNOWN'),
                    'measurements': {k: data.get(k) for k in ('power', 'current', 'voltage', 'energy')},
                    'units': {'power': 'W', 'current': 'A', 'voltage': 'V', 'energy': 'kWh'},
                    'field_sample_age': 'UNKNOWN (Z2M may merge cached fields)',
                    'physical_state_confirmed': False, 'linkquality': data.get('linkquality')}
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.wait()


def main():
    os.umask(0o077)
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['reserve', 'reservation', 'release', 'status', 'power', 'on', 'off'])
    p.add_argument('--owner')
    p.add_argument('--token')
    p.add_argument('--timeout', type=int, default=20)
    a = p.parse_args()
    if not 1 <= a.timeout <= 60:
        p.error('--timeout must be 1..60 seconds')
    try:
        if socket.gethostname() != 'codex-hil-debug-station2':
            raise ValueError('WRONG_HOST: use hil-plug launcher from Optiplex')
        print(json.dumps(execute(a), ensure_ascii=False))
    except (ValueError, OSError, subprocess.SubprocessError) as e:
        print(json.dumps({'error': str(e)}), file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())
