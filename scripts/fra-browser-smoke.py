#!/usr/bin/env python3
"""Optional Firefox/Marionette GUI smoke. Does not install browser or use hardware.
Start FRA GUI with --simulate and a private Firefox profile with marionette.port=2829.
"""
import argparse
import base64
import json
from pathlib import Path
import socket
import time

p=argparse.ArgumentParser();p.add_argument('--url',default='http://127.0.0.1:8851');p.add_argument('--port',type=int,default=2829)
p.add_argument('--screenshot',default='local/fra-gui.png');a=p.parse_args()
s=socket.create_connection(('127.0.0.1',a.port),5);s.settimeout(15);seq=0

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

receive();call('WebDriver:NewSession',{'capabilities':{}})
try:
    call('WebDriver:Navigate',{'url':a.url})
    wait('return document.querySelectorAll("#controls input,#controls select").length===18')
    # Check server was explicitly launched in simulation before pressing any START.
    import urllib.request
    # A fresh server has no result; obtain explicit mode from a read-only metadata endpoint.
    with urllib.request.urlopen(a.url+'/api/mode') as response:mode=json.load(response)
    assert mode['simulation'], 'browser smoke requires --simulate'
    assert js('return Number(document.getElementById("c_amplitude").value)')==100
    js('Array.from(document.querySelectorAll("[data-amplitude-mv]")).find(b=>b.dataset.amplitudeMv==="10").click();return true')
    assert js('return readConfig().amplitude')==.01
    js('Array.from(document.querySelectorAll("[data-amplitude-factor]")).find(b=>b.dataset.amplitudeFactor==="0.5").click();return true')
    assert js('return readConfig().amplitude')==.005
    js('Array.from(document.querySelectorAll("[data-amplitude-factor]")).find(b=>b.dataset.amplitudeFactor==="2").click();return true')
    assert js('return readConfig().amplitude')==.01
    js('populate(readConfig());return true')
    assert js('return Number(document.getElementById("c_amplitude").value)')==10
    js('document.getElementById("c_start_frequency").value=100;document.getElementById("c_stop_frequency").value=10000;document.getElementById("c_points").value=5;document.getElementById("start").click();return true')
    wait('return document.getElementById("state").textContent==="completed"')
    assert js('return document.getElementById("trust").textContent.includes("SIMULATION")')
    assert js('return document.getElementById("warnings").textContent')==''
    assert js('return document.getElementById("stats").textContent.includes("mVpp")')
    with urllib.request.urlopen(a.url+'/api/status') as response:completed=json.load(response)
    assert completed['result']['config']['amplitude']==.01
    assert completed['result']['points'][0]['source_settings']['state']['vpp']==.01
    wait('return document.getElementById("plot").naturalWidth>0')
    shot=call('WebDriver:TakeScreenshot',{'id':None,'full':True,'scroll':True})
    if isinstance(shot,dict):shot=shot['value']
    path=Path(a.screenshot);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(base64.b64decode(shot))
    js('document.getElementById("c_points").value=200;document.getElementById("start").click();return true')
    wait('return document.getElementById("state").textContent.startsWith("Measuring")')
    assert js('return [...document.querySelectorAll(".amplitude-buttons button")].every(b=>b.disabled)')
    js('document.getElementById("stop").click();return true')
    wait('return document.getElementById("state").textContent==="cancelled"')
    assert js('return document.getElementById("details").textContent.includes("off_confirmed")')
    js('document.getElementById("single").click();return true')
    wait('return document.getElementById("state").textContent==="completed"')
    assert js('return document.getElementById("progress").max')==1
    print(json.dumps({'browser_smoke':'PASS','controls':18,'amplitude_mV_conversion_and_lock':'PASS','sweep':'PASS','single':'PASS','stop':'PASS','plot':'PASS','screenshot':str(path)}))
finally:
    call('Marionette:Quit',{'flags':['eForceQuit']});s.close()
