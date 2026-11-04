"""Local Web API: one job, same engine/config as CLI. No instrument commands."""
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import copy
import hmac
import json
import secrets
from pathlib import Path
import threading
from urllib.parse import urlsplit
from .fra_engine import FRAConfig
from .fra_export import export_bytes
from .fra_gui import PAGE


class Jobs:
    def __init__(self,engine,defaults,results_dir=None):
        self.results_dir=Path(results_dir) if results_dir else None
        self.engine=engine;self.defaults=defaults;self.lock=threading.Lock();self.thread=None;self.cancel=threading.Event()
        self.state=dict(running=False,result=None,revision=0,completed=0,total=0,frequency_hz=None)
    def event(self,event):
        with self.lock:
            kind=event['type'];self.state['revision']+=1
            if kind=='started': self.state.update(result=copy.deepcopy(event['result']),total=event['total'],completed=0)
            elif kind=='identified': self.state['result'].update(identities=copy.deepcopy(event['identities']),simulation=event['simulation'])
            elif kind=='progress': self.state['frequency_hz']=event['frequency_hz']
            elif kind=='point': self.state['result']['points'].append(copy.deepcopy(event['point']));self.state['completed']=event['index']
            elif kind=='finished':
                result=copy.deepcopy(event['result'])
                if self.results_dir:
                    try:
                        self.results_dir.mkdir(parents=True,exist_ok=True)
                        path=self.results_dir/(result['id']+'.json')
                        temp=path.with_suffix('.tmp');temp.write_bytes(export_bytes(result,'json'));temp.replace(path)
                    except OSError as e:result['errors'].append('Result could not be saved: '+str(e))
                self.state.update(result=result,running=False)
    def start(self,config):
        config.validate()
        with self.lock:
            if self.state['running'] or (self.thread and self.thread.is_alive()): raise ValueError('measurement already running')
            self.cancel=threading.Event();self.state.update(running=True,result=None,completed=0,frequency_hz=None)
            self.thread=threading.Thread(target=self._run,args=(config,),daemon=False);self.thread.start()
    def _run(self,config):
        try: self.engine.run(config,self.cancel,self.event)
        finally:
            with self.lock:self.state['running']=False
    def snapshot(self):
        with self.lock:return copy.deepcopy(self.state)
    def close(self):
        self.cancel.set()
        if self.thread:self.thread.join()


def make_server(engine,defaults,host='127.0.0.1',port=8850,results_dir=None):
    if host not in ('127.0.0.1','localhost'): raise ValueError('M1 GUI binds only to loopback; use SSH tunnel for a tablet')
    jobs=Jobs(engine,defaults,results_dir); token=secrets.token_urlsafe(32)
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup();self.connection.settimeout(10)
        def log_message(self,*args):pass
        def send(self,status,data,ctype='application/json'):
            if isinstance(data,(dict,list)):data=json.dumps(data,allow_nan=False).encode()
            self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('X-Frame-Options','DENY')
            self.end_headers();self.wfile.write(data)
        def host_ok(self):return self.headers.get('Host') in (f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}')
        def do_GET(self):
            if not self.host_ok():self.send(403,{'error':'invalid Host'});return
            path=urlsplit(self.path).path
            if path=='/':self.send(200,PAGE.replace('__TOKEN__',token).encode(),'text/html; charset=utf-8')
            elif path=='/api/mode':self.send(200,{'simulation':bool(getattr(engine.session_factory,'simulation',False))})
            elif path=='/api/config':self.send(200,asdict(defaults))
            elif path=='/api/status':self.send(200,jobs.snapshot())
            elif path.startswith('/api/export/'):
                kind=path.rsplit('/',1)[1];r=jobs.snapshot()['result']
                if r is None:self.send(404,{'error':'no result'});return
                if kind not in ('json','csv','png','svg'):self.send(404,{'error':'unknown format'});return
                self.send(200,export_bytes(r,kind),{'json':'application/json','csv':'text/csv','png':'image/png','svg':'image/svg+xml'}[kind])
            else:self.send(404,{'error':'not found'})
        def do_POST(self):
            if not self.host_ok() or not hmac.compare_digest(self.headers.get('X-FRA-Token',''),token):self.send(403,{'error':'invalid token/Host'});return
            try:
                n=int(self.headers.get('Content-Length','0'))
                if not 0<n<=32768:raise ValueError('body must be 1..32768 bytes')
                if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise ValueError('JSON required')
                body=json.loads(self.rfile.read(n));path=urlsplit(self.path).path
                if path=='/api/stop':jobs.cancel.set();self.send(202,{'status':'stopping'});return
                c=FRAConfig.from_dict(body)
                if path=='/api/validate':self.send(200,asdict(c))
                elif path=='/api/start':jobs.start(c);self.send(202,{'status':'started'})
                else:self.send(404,{'error':'not found'})
            except (ValueError,TypeError) as e:self.send(400,{'error':str(e)})
    server=ThreadingHTTPServer((host,port),Handler);server.jobs=jobs;server.api_token=token
    return server
