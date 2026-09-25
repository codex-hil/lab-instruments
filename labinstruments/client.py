"""Typed control client. Does not implement or duplicate administrator policy."""
import json
from pathlib import Path
import ssl
import urllib.request

class Client:
    def __init__(self, url, token_file, ca_file=None, timeout=120):
        if not url.startswith('https://'):
            raise ValueError('HTTPS required')
        self.url=url.rstrip('/')
        self.token=Path(token_file).read_text().strip()
        self.timeout=timeout
        context=ssl.create_default_context(cafile=ca_file)
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPSHandler(context=context))

    def call(self, device, action, **args):
        request=urllib.request.Request(self.url+'/v1/control',
            json.dumps(dict(device=device,action=action,args=args),allow_nan=False).encode(),
            {'Authorization':'Bearer '+self.token,'Content-Type':'application/json'})
        with self.opener.open(request,timeout=self.timeout) as response:
            return json.load(response)

    def identify(self,device):return self.call(device,'identify')
    def read(self,device,operation,channel=1):return self.call(device,'read',operation=operation,channel=channel)
    def apply(self,device,**state):return self.call(device,'apply',**state)
    def off(self,device):return self.call(device,'off')
    def renew(self,device):return self.call(device,'renew')
