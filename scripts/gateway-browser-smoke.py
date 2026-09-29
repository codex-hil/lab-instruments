#!/usr/bin/env python3
"""Optional Firefox/Marionette dashboard smoke; sends explicit *IDN? requests.
Run against a development fixture or an authorized idle gateway.
"""
import argparse
import base64
import json
from pathlib import Path
import socket
import time

p=argparse.ArgumentParser()
p.add_argument('--url', default='http://127.0.0.1:8841')
p.add_argument('--port', type=int, default=2832)
p.add_argument('--token-file', required=True)
p.add_argument('--output', default='local/gateway-browser')
a=p.parse_args()
s=socket.create_connection(('127.0.0.1',a.port),5)
s.settimeout(20)
seq=0

def receive():
    prefix=b''
    while not prefix.endswith(b':'):
        c=s.recv(1)
        if not c:raise OSError('browser closed connection')
        prefix+=c
    count=int(prefix[:-1]);body=b''
    while len(body)<count:
        c=s.recv(count-len(body))
        if not c:raise OSError('browser closed connection')
        body+=c
    return json.loads(body)

def call(name,args=None):
    global seq
    seq+=1;msg=json.dumps([0,seq,name,args or {}]).encode();s.sendall(str(len(msg)).encode()+b':'+msg)
    r=receive()
    if r[2]:raise RuntimeError(r[2])
    return r[3]

def js(code):return call('WebDriver:ExecuteScript',{'script':code,'args':[],'newSandbox':False})['value']

def wait(code,timeout=8):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        if js(code):return
        time.sleep(.1)
    raise AssertionError('browser condition timeout: '+code)


receive()
call('WebDriver:NewSession', {'capabilities': {}})
try:
    call('WebDriver:SetWindowRect', {'width': 1280, 'height': 1100})
    call('WebDriver:Navigate', {'url': a.url})
    token=Path(a.token_file).read_text().strip()
    call('WebDriver:ExecuteScript', {'script': "document.getElementById('token').value=arguments[0];document.getElementById('connect').click()", 'args': [token]})
    wait('return document.querySelectorAll("#slots article").length===4')
    assert js('return document.getElementById("count").textContent')=='4 / 4'
    assert js('return [...document.querySelectorAll("[data-identify]")].every(b=>!b.disabled)')
    js('document.getElementById("identify-all").click();return true')
    wait('return !document.getElementById("identify-all").disabled && document.querySelectorAll("#events tbody tr").length>=4',timeout=35)
    assert js('return [...document.querySelectorAll(".identity")].every(e=>e.textContent.includes("SCPI:")||e.textContent.includes("CF:"))')
    def screenshot(suffix):
        shot=call('WebDriver:TakeScreenshot', {'id': None,'full': True,'scroll': True})
        if isinstance(shot,dict):shot=shot['value']
        path=Path(a.output+'-'+suffix+'.png');path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(base64.b64decode(shot))
    screenshot('desktop')
    call('WebDriver:SetWindowRect', {'width': 390, 'height': 844})
    assert js('return document.documentElement.scrollWidth<=window.innerWidth')
    screenshot('mobile')
    js("const data=JSON.parse(document.getElementById('status').textContent);data.slots.afg1062.status.identity='<img src=x onerror=alert(1)>';window.render(data);return true")
    assert js('return document.querySelectorAll(".identity img").length')==0
    js("document.getElementById('token').value='wrong';document.getElementById('connect').click();return true")
    wait('return document.getElementById("notice").textContent.includes("unauthorized")')
    assert js('return document.querySelectorAll("#slots article").length')==0
    assert js('return document.getElementById("download").disabled')
    js("document.getElementById('logout').click();return true")
    assert js('return document.getElementById("token").value')==''
    assert js('return localStorage.length===0 && sessionStorage.length===0')
    print(json.dumps({'browser':'Firefox','four_cards':'PASS','identify_all':'PASS','mobile_no_overflow':'PASS','untrusted_text':'PASS','invalid_token_clears_status':'PASS','logout':'PASS','screenshots':a.output}))
finally:
    call('Marionette:Quit',{'flags':['eForceQuit']})
    s.close()
