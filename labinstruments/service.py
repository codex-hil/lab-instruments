"""Two deliberately separate modes: protected typed control and trusted USB bridge."""
import base64
from collections import deque
import hmac
import json
import logging
import os
import socket
from pathlib import Path
import ssl
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from .drivers import Driver, PROFILES, ACTIVE, validate
from .gateway_dashboard import PAGE
from .transport import MAX_MESSAGE, Transport, usb_devices, usb_selectors


def load_config(path, strict=False):
    p = Path(path).absolute()
    if strict:
        for item in {p, *p.parents, p.resolve(), *p.resolve().parents}:
            st = item.stat()
            if st.st_uid != 0 or st.st_mode & 0o022:
                raise ValueError(f'root ownership and no group/world write required: {item}')
    cfg = json.loads(p.read_text())
    if cfg.get('mode') not in {'control','usb-gateway'}:
        raise ValueError('mode must be control or usb-gateway')
    return cfg


class Controller:
    def __init__(self, config, factory=Transport):
        self.cfg, self.factory = config, factory
        self.devices = config.get('devices', {})
        self.locks = {name:threading.Lock() for name in self.devices}
        self.status = {}; self.leases = {}; self.stopping = threading.Event()
        for name, spec in self.devices.items():
            if spec['model'] not in PROFILES:raise ValueError('unknown model '+name)
            if PROFILES[spec['model']][1] in ACTIVE and not spec.get('serial'):
                raise ValueError('active device requires expected serial')
        self.thread = None

    def driver(self, name, io):
        d = self.devices[name]
        return Driver(io, d['model'], d.get('serial'))

    def start(self):
        # Initial shutdown is explicit service behavior, not performed by probe or CLI reads.
        for name, d in self.devices.items():
            if PROFILES[d['model']][1] in ACTIVE | {'picoammeter'}:
                self.call(name, 'off', {})
        self.thread = threading.Thread(target=self.watchdog, daemon=True);self.thread.start()

    def watchdog(self):
        while not self.stopping.wait(.25):
            for name in self.devices:
                # Expiry check and OFF share the same lock as apply/renew; no stale timer race.
                with self.locks[name]:
                    if self.leases.get(name, float('inf')) <= time.monotonic():
                        try:self._call(name,'off',{})
                        except Exception:logging.exception('lease shutdown failed: %s', name)

    def call(self, name, action, args):
        if name not in self.devices:raise ValueError('unknown device')
        with self.locks[name]:return self._call(name, action, args)

    def _call(self, name, action, args):
        d = self.devices[name]
        if action not in {'identify','read','apply','off','renew'}:raise ValueError('unknown action')
        if action in {'identify','off','renew'} and args:raise ValueError('unexpected arguments')
        if action=='read' and (set(args)-{'operation','channel'} or 'operation' not in args):raise ValueError('invalid read arguments')
        if action=='apply':
            if d['transport']['kind'] == 'gateway':raise ValueError('protected outputs require local TCP/USB; run control service on the Pi')
            if not d.get('commissioned', False):raise ValueError('source profile not commissioned by administrator')
            if self.status.get(name,{}).get('fault'):raise ValueError('fault latched; successful OFF required')
            validate(d['model'], args, d['limits'])
        ttl = float(d.get('lease_seconds', 10))
        if not 1 <= ttl <= 30:raise ValueError('lease must be 1..30 seconds')
        if action=='renew':
            if name not in self.leases or self.leases[name] <= time.monotonic():raise ValueError('no live lease')
            self.leases[name] = time.monotonic()+ttl
            return {'lease_seconds':ttl}
        try:
            with self.factory(d['transport']) as io:
                driver = self.driver(name,io)
                identity = driver.identify()
                if action=='identify':result={'identity':identity}
                elif action=='off':
                    result=driver.off();self.leases.pop(name,None)
                elif action=='read':result={'value':driver.read(**args)}
                else:
                    self.leases.pop(name,None)
                    result=driver.apply(args,d['limits'])
                    if args['enable']:self.leases[name]=time.monotonic()+ttl;result['lease_seconds']=ttl
                previous_fault = self.status.get(name, {}).get('fault', False)
                self.status[name]={'identity':identity,'last_ok':time.time(),'fault':False if action=='off' else previous_fault}
            logging.info(json.dumps({'device':name,'action':action,'args':args,'ok':True}))
            return result
        except Exception as error:
            self.status[name]={'fault':True,'error':str(error),'last_error':time.time()}
            # Retry shutdown from watchdog when an enabled/uncertain output lost communication.
            if action in {'apply','off'} or name in self.leases:
                self.leases[name]=time.monotonic()+1
            logging.error(json.dumps({'device':name,'action':action,'ok':False,'error':str(error)}))
            raise

    def close(self):
        self.stopping.set()
        if self.thread:self.thread.join(timeout=2)
        for name,d in self.devices.items():
            if PROFILES[d['model']][1] in ACTIVE | {'picoammeter'}:
                try:self.call(name,'off',{})
                except Exception:logging.exception('shutdown OFF unconfirmed: %s',name)

    def snapshot(self):
        return [{'name':name,'model':d['model'],'status':self.status.get(name,{}),
                 'leased':name in self.leases} for name,d in self.devices.items()]


class Gateway:
    def __init__(self, config, factory=Transport):
        self.cfg = config
        self.factory = factory
        self.slots = config.get('slots', {})
        # Serialize commands even when two slots select the same physical device.
        self.lock = threading.Lock()
        self.state_lock = threading.Lock()
        self.status = {}
        self.events = deque(maxlen=40)
        self.active = None
        self.started = time.monotonic()
        for spec in self.slots.values():
            usb_selectors(spec)
            Transport(dict(spec, kind='usb'))

    def snapshot(self):
        devices = usb_devices()
        with self.state_lock:
            statuses = {name: dict(state) for name, state in self.status.items()}
            events = list(self.events)
            active = self.active
        slots = {}
        for name, spec in self.slots.items():
            selectors = usb_selectors(spec)
            matches = [d for d in devices if all(d[k] == v for k, v in selectors.items())]
            slots[name] = {
                'label': spec.get('label', name),
                'connected': len(matches) == 1,
                'state': 'connected' if len(matches) == 1 else 'ambiguous' if matches else 'disconnected',
                'accessible': len(matches) == 1 and os.access(matches[0]['path'], os.R_OK | os.W_OK),
                'selectors': selectors, 'matches': matches,
                'status': statuses.get(name, {}),
            }
        return {'usb': devices, 'slots': slots, 'events': events,
                'gateway': {'hostname': socket.gethostname(), 'uptime_seconds': round(time.monotonic() - self.started),
                            'active_slot': active, 'serialization': 'global', 'mode': 'usb-gateway'}}

    def identify(self, body):
        if not isinstance(body, dict) or set(body) != {'slot'} or not isinstance(body['slot'], str):
            raise ValueError('identify requires a slot string')
        slot = body['slot']
        if slot not in self.slots:
            raise ValueError('unknown slot')
        # An explicit diagnostic, never a background poll or a driver initialization.
        data = b'*IDN?' + self.slots[slot].get('write_termination', '\n').encode('ascii')
        reply = self._transaction(slot, data, True, 'identify')
        return {'identity': reply.decode('ascii', errors='replace').strip()}

    def transaction(self, body):
        if not isinstance(body, dict) or set(body) != {'slot', 'data', 'reply'} or type(body['reply']) is not bool:
            raise ValueError('invalid transaction')
        slot = body['slot']
        if not isinstance(slot, str) or not isinstance(body['data'], str):
            raise ValueError('slot and data must be strings')
        if slot not in self.slots:
            raise ValueError('unknown slot')
        data = base64.b64decode(body['data'], validate=True)
        reply = self._transaction(slot, data, body['reply'], 'transaction')
        return {'data': base64.b64encode(reply).decode()}

    def _transaction(self, slot, data, expect_reply, operation):
        if not 0 < len(data) <= int(self.slots[slot].get('max_message', MAX_MESSAGE)):
            raise ValueError('invalid message length')
        # Reject a busy gateway before writing, instead of building an unbounded queue.
        if not self.lock.acquire(blocking=False):
            raise OSError('gateway busy; no command sent')
        started = time.monotonic()
        with self.state_lock:
            self.active = slot
        reply = b''
        error = None
        try:
            with self.factory(dict(self.slots[slot], kind='usb')) as io:
                reply = io.transaction(data, expect_reply)
            return reply
        except Exception as exc:
            error = str(exc)
            raise
        finally:
            elapsed = round((time.monotonic() - started) * 1000, 1)
            now = time.time()
            with self.state_lock:
                previous = self.status.get(slot, {})
                state = dict(previous, duration_ms=elapsed, error=error,
                             transactions=previous.get('transactions', 0) + 1,
                             failures=previous.get('failures', 0) + int(error is not None))
                state['last_error' if error is not None else 'last_ok'] = now
                if operation == 'identify' and error is None:
                    state['identity'] = reply[:4096].decode('ascii', errors='replace').strip()
                    state['identified_at'] = now
                self.status[slot] = state
                self.events.appendleft({'time': now, 'slot': slot, 'operation': operation,
                                        'ok': error is None, 'duration_ms': elapsed,
                                        'tx_bytes': len(data), 'rx_bytes': len(reply), 'error': error})
                self.active = None
            self.lock.release()


def make_server(cfg, app, development=False):
    host,port=cfg.get('listen', ['127.0.0.1',8840])
    tls=cfg.get('tls')
    if not tls and (not development or host not in {'127.0.0.1','::1'}):
        raise ValueError('TLS mandatory except explicit loopback development')
    token=Path(cfg['token_file']).read_text().strip()
    if len(token)<32:raise ValueError('token must contain at least 32 characters')
    class Handler(BaseHTTPRequestHandler):
        protocol_version='HTTP/1.0'
        def setup(self):
            super().setup();self.connection.settimeout(10)
        def log_message(self, fmt,*args):
            logging.info('%s %s',self.client_address[0],fmt % args)
        def send(self, code, obj, content='application/json'):
            data=obj if isinstance(obj,bytes) else json.dumps(obj,allow_nan=False).encode()
            self.send_response(code);self.send_header('Content-Type',content)
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        def authorized(self):
            header=self.headers.get('Authorization','')
            if not hmac.compare_digest(header.encode(),('Bearer '+token).encode()):
                self.send(401,{'error':'unauthorized'});return False
            return True
        def do_GET(self):
            if self.path=='/':self.send(200,PAGE,'text/html; charset=utf-8');return
            if not self.authorized():return
            if self.path!='/v1/status':self.send(404,{'error':'not found'});return
            self.send(200,app.snapshot())
        def do_POST(self):
            if not self.authorized():return
            try:
                n=int(self.headers.get('Content-Length','0'))
                if not 0<n<=24*1024*1024:raise ValueError('request size out of bounds')
                data=self.rfile.read(n)
                if len(data)!=n:raise ValueError('incomplete request')
                body=json.loads(data,parse_constant=lambda x: (_ for _ in ()).throw(ValueError('nonfinite JSON')))
                if not isinstance(body,dict):raise ValueError('object required')
                if cfg['mode']=='usb-gateway' and self.path=='/v1/transaction':
                    result=app.transaction(body)
                elif cfg['mode']=='usb-gateway' and self.path=='/v1/identify':
                    result=app.identify(body)
                elif cfg['mode']=='control' and self.path=='/v1/control':
                    if set(body)!={'device','action','args'} or not isinstance(body['args'],dict):raise ValueError('invalid request')
                    result=app.call(body['device'],body['action'],body['args'])
                else:self.send(404,{'error':'not found'});return
                self.send(200,result)
            except (ValueError,KeyError,TypeError) as e:self.send(400,{'error':str(e)})
            except Exception as e:
                logging.exception('transaction failed');self.send(503,{'error':str(e)})
    class Server(ThreadingHTTPServer):
        daemon_threads=True
        def __init__(self,*args,**kwargs):
            self.capacity=threading.BoundedSemaphore(16);super().__init__(*args,**kwargs)
        def process_request(self,request,address):
            if not self.capacity.acquire(blocking=False):request.close();return
            try:super().process_request(request,address)
            except BaseException:self.capacity.release();raise
        def process_request_thread(self,request,address):
            try:super().process_request_thread(request,address)
            finally:self.capacity.release()
        def get_request(self):
            conn,addr=super().get_request()
            if tls:
                conn.settimeout(3)
                try:conn=context.wrap_socket(conn,server_side=True)
                except BaseException:conn.close();raise
            return conn,addr
    if tls:
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.minimum_version=ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(tls['cert'],tls['key'])
    return Server((host,int(port)),Handler)
