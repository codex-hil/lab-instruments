import argparse
import json
import logging
from pathlib import Path
import signal
import ssl
import urllib.request
from .drivers import Driver, PROFILES
from .service import Controller, Gateway, load_config, make_server
from .transport import Transport, usb_devices


def main():
    import sys
    if len(sys.argv)>1 and sys.argv[1]=="fra":
        from .fra_cli import main as fra_main
        raise SystemExit(fra_main(sys.argv[2:]))
    parser=argparse.ArgumentParser(prog='labinst')
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('models');sub.add_parser('usb-list')
    sub.add_parser('fra', help='Frequency Response Analyzer: sweep, measure, gui, export')
    for verb in ['identify','read']:
        p=sub.add_parser(verb);p.add_argument('--model',choices=PROFILES)
        p.add_argument('--host');p.add_argument('--port',type=int);p.add_argument('--usb-serial')
        p.add_argument('--serial');p.add_argument('--config');p.add_argument('--device')
        if verb=='read':p.add_argument('--operation',required=True);p.add_argument('--channel',type=int,default=1)
    p=sub.add_parser('serve');p.add_argument('--config',required=True);p.add_argument('--development',action='store_true')
    p=sub.add_parser('client');p.add_argument('--url',required=True);p.add_argument('--ca-file')
    p.add_argument('--token-file',required=True);p.add_argument('--device',required=True)
    p.add_argument('--action',choices=['identify','read','apply','off','renew'],required=True)
    p.add_argument('--args',default='{}',help='JSON complete state or read arguments')
    a=parser.parse_args()
    if a.command=='models':print(json.dumps(PROFILES,indent=2));return
    if a.command=='usb-list':print(json.dumps(usb_devices(),indent=2));return
    if a.command=='client':
        if not a.url.startswith('https://'):raise ValueError('client requires HTTPS')
        body={'device':a.device,'action':a.action,'args':json.loads(a.args)}
        req=urllib.request.Request(a.url.rstrip('/')+'/v1/control',json.dumps(body,allow_nan=False).encode(),
            {'Authorization':'Bearer '+Path(a.token_file).read_text().strip(),'Content-Type':'application/json'})
        context=ssl.create_default_context(cafile=a.ca_file)
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPSHandler(context=context))
        with opener.open(req,timeout=120) as r:print(r.read().decode())
        return
    if a.command=='serve':
        cfg=load_config(a.config,strict=not a.development)
        logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
        app=Controller(cfg) if cfg['mode']=='control' else Gateway(cfg)
        server=make_server(cfg,app,development=a.development)
        def stop(*unused):raise KeyboardInterrupt
        signal.signal(signal.SIGTERM,stop)
        try:
            if isinstance(app,Controller):app.start()
            server.serve_forever(poll_interval=.2)
        finally:
            server.server_close()
            if isinstance(app,Controller):app.close()
        return
    if a.config:
        spec=load_config(a.config)['devices'][a.device]
        model,serial,transport=spec['model'],spec.get('serial'),spec['transport']
    else:
        if not a.model:parser.error('--model or --config required')
        model,serial=a.model,a.serial
        if a.usb_serial:transport={'kind':'usb','serial':a.usb_serial}
        else:
            port=a.port or PROFILES[model][3]
            if not a.host or not port:parser.error('--host and --port (if no default) required')
            transport={'kind':'tcp','host':a.host,'port':port}
            if model=='6487':transport['read_termination']='\r'
    with Transport(transport) as io:
        d=Driver(io,model,serial)
        result=d.identify() if a.command=='identify' else d.read(a.operation,a.channel)
        print(result)

if __name__=='__main__':main()
