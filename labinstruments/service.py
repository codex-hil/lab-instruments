"""Two deliberately separate modes: protected typed control and trusted USB bridge."""
import base64
import hmac
import json
import logging
import os
from pathlib import Path
import ssl
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from .drivers import Driver, PROFILES, ACTIVE, validate
from .transport import Transport, usb_devices


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
        self.cfg=config;self.factory=factory;self.slots=config.get('slots',{})
        self.lock=threading.Lock();self.status={}
        # A single gateway-wide lock also protects against aliases selecting the same USB device.
    def snapshot(self):
        devices=usb_devices(); slots={}
        for name, spec in self.slots.items():
            selectors={k:spec[k] for k in ('serial','topology','vendor','product_id') if k in spec}
            matches=[d for d in devices if selectors and all(d[k]==v for k,v in selectors.items())]
            slots[name]={'connected':len(matches)==1,'matches':matches,'status':self.status.get(name,{})}
        return {'usb':devices,'slots':slots}
    def transaction(self, body):
        if set(body)!={'slot','data','reply'} or type(body['reply']) is not bool:raise ValueError('invalid transaction')
        slot=body['slot']
        if slot not in self.slots:raise ValueError('unknown slot')
        data=base64.b64decode(body['data'],validate=True)
        with self.lock:
            try:
                with self.factory(dict(self.slots[slot],kind='usb')) as io:
                    reply=io.transaction(data,body['reply'])
                self.status[slot]={'last_ok':time.time(),'error':None}
                return {'data':base64.b64encode(reply).decode()}
            except Exception as error:
                self.status[slot]={'last_error':time.time(),'error':str(error)}
                raise


PAGE = b'''<!doctype html><html lang="en"><meta charset="utf-8"><title>Lab instruments</title>
<style>body{font:16px system-ui;max-width:960px;margin:40px auto;background:#101b2b;color:#e4edf6}input,button{font:inherit;padding:8px}pre{white-space:pre-wrap;background:#192a40;padding:20px}</style>
<h1>Lab instruments</h1><p>Local dashboard. Token stays in this page's memory.</p>
<input id="token" type="password" placeholder="Access token"><button id="connect">Refresh status</button><pre id="status">Not connected</pre>
<script>async function refresh(){try{let r=await fetch('/v1/status',{headers:{Authorization:'Bearer '+document.getElementById('token').value}});document.getElementById('status').textContent=JSON.stringify(await r.json(),null,2)}catch(e){document.getElementById('status').textContent=String(e)}}document.getElementById('connect').onclick=refresh;setInterval(()=>{if(document.getElementById('token').value)refresh()},5000)</script></html>'''


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
