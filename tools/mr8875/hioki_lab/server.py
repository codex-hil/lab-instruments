"""Dependency-free laboratory panel and session recorder."""
import argparse
import csv
import io
import json
import os
from pathlib import Path
import secrets
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from .driver import MR8875

class Lab:
    def __init__(self, driver, storage):
        self.driver = driver
        self.storage = Path(storage)
        self.storage.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.config = None
        self.latest = None
        self.error = None
        self.selected = []
        self.history = []
        self.record = None
        self.running = True
        self.token = secrets.token_urlsafe(24)

    def connect(self):
        with self.lock:
            self.config = self.driver.discover()
            if not self.selected:
                analog = [c['id'] for c in self.config['channels'] if c['mode'] != 'CAN']
                self.selected = (analog or self.driver.channels)[:4]
            return self.config

    def poll(self):
        while self.running:
            tick = time.monotonic()
            try:
                with self.lock:
                    if not self.config:
                        self.connect()
                    sample = self.driver.live(self.selected)
                    self.latest = sample
                    self.history.append(sample)
                    self.history = self.history[-300:]
                    self.error = None
                    if self.record:
                        self.record['writer'].writerow([sample['time']-self.record['started'],
                                                       sample['time'], *[sample['values'][c] for c in self.record['channels']]])
                        self.record['file'].flush()
                        self.record['rows'] += 1
            except Exception as e:
                with self.lock:
                    self.error = str(e)
                    # Gaps are explicit in the session metadata; do not repeat stale samples.
                    if self.record:
                        self.record['errors'].append({'time': time.time(), 'error': str(e)})
            time.sleep(max(.1, 1-(time.monotonic()-tick)))

    def state(self):
        with self.lock:
            sessions = []
            for p in sorted(self.storage.glob('*/metadata.json'), reverse=True)[:30]:
                try:
                    meta = json.loads(p.read_text())
                    sessions.append({'id': p.parent.name, 'title': meta.get('title'),
                                     'kind': meta.get('kind'), 'rows': meta.get('rows'),
                                     'complete': meta.get('complete', False)})
                except (ValueError, OSError):
                    pass
            return {'config': self.config, 'latest': self.latest, 'error': self.error,
                    'history': self.history, 'selected': self.selected, 'sessions': sessions,
                    'recording': ({'id': self.record['id'], 'rows': self.record['rows']}
                                  if self.record else None)}

    def new_session(self):
        sid = time.strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(3)
        p = self.storage/sid
        p.mkdir()
        return sid, p

    def metadata(self, p, meta):
        tmp = p/'metadata.tmp'
        tmp.write_text(json.dumps(meta, indent=2, ensure_ascii=False, allow_nan=False)+'\n')
        tmp.replace(p/'metadata.json')

    def begin_record(self, title, no_inputs):
        if self.record:
            raise ValueError('Sesja już trwa')
        config = self.driver.configuration()
        sid, path = self.new_session()
        f = (path/'data.csv').open('w', newline='')
        writer = csv.writer(f)
        writer.writerow(['elapsed_s', 'unix_time_s', *self.selected])
        meta = {'id': sid, 'kind': 'host_live', 'title': str(title)[:200],
                'started': time.time(), 'no_inputs': bool(no_inputs),
                'complete': False, 'config': config, 'channels': self.selected[:],
                'time_reference': 'host_snapshot_time', 'poll_interval_target_seconds': 1,
                'note': 'Host polling; not a full-rate instrument waveform. No-input values are not validated measurements.'}
        self.metadata(path, meta)
        self.record = {'id': sid, 'path': path, 'file': f, 'writer': writer,
                       'started': meta['started'], 'rows': 0, 'channels': self.selected[:],
                       'meta': meta, 'errors': []}
        return {'id': sid}

    def end_record(self):
        if not self.record:
            raise ValueError('Brak aktywnej sesji')
        r = self.record
        r['file'].flush()
        os.fsync(r['file'].fileno())
        r['file'].close()
        r['meta'].update(ended=time.time(), rows=r['rows'], complete=True, errors=r['errors'])
        self.metadata(r['path'], r['meta'])
        self.record = None
        return {'id': r['id'], 'rows': r['rows']}

    def action(self, name, body):
        with self.lock:
            if name == 'connect':
                return self.connect()
            if name == 'select':
                if self.record:
                    raise ValueError('Zakończ sesję przed zmianą kanałów')
                channels = body['channels']
                if not isinstance(channels, list) or not 1 <= len(channels) <= 30 or len(set(channels)) != len(channels):
                    raise ValueError('Wybierz 1–30 różnych kanałów')
                for ch in channels:
                    self.driver.validate_channel(ch)
                self.selected = channels[:]
                self.history = []
                self.latest = None
                return {'channels': self.selected}
            if name in ('channel', 'acquisition'):
                if self.record:
                    raise ValueError('Zakończ sesję przed zmianą konfiguracji')
                if name == 'channel':
                    result = self.driver.configure_channel(body['channel'], body['mode'],
                              body['range'], body['enabled'], body.get('sensor', 'K'))
                else:
                    result = self.driver.configure_acquisition(body['sample'], body['divisions'])
                self.config = self.driver.configuration()
                self.history = []
                return result
            if name == 'start':
                return {'status': self.driver.start()}
            if name == 'stop':
                return {'status': self.driver.stop()}
            if name == 'record':
                return self.begin_record(body.get('title', 'Sesja'), body.get('no_inputs', True))
            if name == 'finish':
                return self.end_record()
            if name == 'waveform':
                wave = self.driver.waveform(self.selected)
                sid, path = self.new_session()
                with (path/'data.csv').open('w', newline='') as f:
                    w = csv.writer(f)
                    w.writerow(['time_from_first_sample_s', *self.selected])
                    for i in range(wave['points']):
                        w.writerow([i*wave['config']['sample_seconds'], *[wave['data'][ch][i] for ch in self.selected]])
                self.metadata(path, {'id': sid, 'title': body.get('title', 'Przebieg'),
                           'kind': 'instrument_waveform', 'complete': True, 'rows': wave['points'],
                           'no_inputs': bool(body.get('no_inputs', True)), 'captured': time.time(),
                           'config': wave['config'], 'channels': self.selected[:],
                           'time_reference': wave['time_reference'], 'sample_time_source': wave['sample_time_source']})
                return {'id': sid, 'points': wave['points']}
            raise ValueError('Nieznana operacja')

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def send(self, code, payload, kind='application/json; charset=utf-8'):
        if isinstance(payload, (dict, list)):
            payload = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()
        elif isinstance(payload, str):
            payload = payload.encode()
        self.send_response(code)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/':
            html = Path(__file__).with_name('panel.html').read_text().replace('__TOKEN__', self.server.lab.token)
            return self.send(200, html, 'text/html; charset=utf-8')
        if path == '/api/state':
            return self.send(200, self.server.lab.state())
        if path.startswith('/sessions/'):
            parts = path.split('/')
            if len(parts) == 4 and parts[3] in ('data.csv', 'metadata.json'):
                import re
                if re.fullmatch(r'[0-9]{8}-[0-9]{6}-[a-f0-9]{6}', parts[2]):
                    p = self.server.lab.storage/parts[2]/parts[3]
                    if p.is_file():
                        return self.send(200, p.read_bytes(), 'text/csv; charset=utf-8' if p.suffix == '.csv' else 'application/json')
        self.send(404, {'error': 'Nie znaleziono'})

    def do_POST(self):
        if self.headers.get('X-Lab-Token') != self.server.lab.token:
            return self.send(403, {'error': 'Odśwież stronę panelu'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 16384:
                raise ValueError('Nieprawidłowe żądanie')
            body = json.loads(self.rfile.read(length))
            path = urlparse(self.path).path
            if not path.startswith('/api/') or not isinstance(body, dict):
                raise ValueError('Nieprawidłowe żądanie')
            result = self.server.lab.action(path[5:], body)
            self.send(200, result)
        except Exception as e:
            self.send(400, {'error': str(e)})

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='192.168.2.13')
    parser.add_argument('--instrument-port', type=int, default=8802)
    parser.add_argument('--bind', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8875)
    parser.add_argument('--storage', default='/srv/codex-hil-data/hioki-mr8875/sessions')
    args = parser.parse_args()
    def shutdown_signal(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, shutdown_signal)
    lab = Lab(MR8875(args.host, args.instrument_port), args.storage)
    server = ThreadingHTTPServer((args.bind, args.port), Handler)
    server.lab = lab
    thread = threading.Thread(target=lab.poll, daemon=True)
    thread.start()
    print(f'Panel: http://{args.bind}:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        lab.running = False
        with lab.lock:
            if lab.record:
                lab.end_record()
            lab.driver.close()
        server.server_close()

if __name__ == '__main__':
    main()
