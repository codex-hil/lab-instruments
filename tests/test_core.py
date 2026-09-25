import base64
import json
import math
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
import urllib.request
import urllib.error
from unittest.mock import patch
from labinstruments.drivers import Driver, validate
from labinstruments.service import Controller, Gateway, make_server, load_config
from labinstruments.transport import Transport

LIMITS={'allow_output':True,'voltage_min':0,'voltage_max':10,'current_min':0.001,'current_max':.5,'power_max':3}
STATE={'channel':1,'enable':True,'voltage':5,'current':.5}

class Fake:
    def __init__(self, config=None):
        self.values={'OUTP':'0'};self.writes=[];self.bad_readback=False
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def write(self,c):
        self.writes.append(c);key,value=c.split(' ',1);self.values[key]={'OFF':'0','ON':'1'}.get(value,value)
    def query(self,c):
        if c=='*IDN?':return 'GW-INSTEK,PSW800-1.44,TEST,1.0'
        if c=='SOUR:VOLT?' and self.bad_readback:return '100'
        return self.values[c[:-1]]

def config():
    return {'mode':'control','devices':{'supply':{'model':'psw800-1.44','serial':'TEST','commissioned':True,
        'transport':{'kind':'tcp','host':'127.0.0.1','port':1},'limits':LIMITS,'lease_seconds':1}}}

class PolicyTests(unittest.TestCase):
    def test_complete_state_and_power(self):
        validate('psw800-1.44',STATE,LIMITS)
        for changes in [{'voltage':11},{'current':.6},{'voltage':10},{'enable':'yes'}, {'channel':True},
                        {'voltage':float('nan')},{'voltage':float('inf')},{'current':True},
                        {'voltage':'1;OUTP ON'},{'channel':2},{'current':0}]:
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                validate('psw800-1.44',dict(STATE,**changes),LIMITS)
        with self.assertRaises(ValueError):validate('psw800-1.44',dict(STATE,raw='*RST'),LIMITS)
        with self.assertRaises(ValueError):validate('psw800-1.44',{'voltage':1},LIMITS)
    def test_disabled_enable(self):
        with self.assertRaises(ValueError):validate('psw800-1.44',STATE,dict(LIMITS,allow_output=False))
    def test_awg_offset_and_50ohm_envelope(self):
        limits={'allow_output':True,'frequency_min':1,'frequency_max':1e6,'vpp_min':.01,'vpp_max':2,
                'voltage_peak_max':2,'current_max':.04,'power_max':.08}
        p={'channel':1,'enable':True,'frequency':1000,'vpp':1,'offset':.4}
        validate('afg1062',p,limits)
        with self.assertRaises(ValueError):validate('afg1062',dict(p,offset=.6),limits)
    def test_rf_power(self):
        l={'allow_output':True,'frequency_min':1e6,'frequency_max':1e9,'dbm_min':-120,'dbm_max':20,'power_max':.01}
        p={'channel':1,'enable':True,'frequency':1e8,'dbm':0}
        validate('smb100a',p,l)
        with self.assertRaises(ValueError):validate('smb100a',dict(p,dbm=20),l)
    def test_invalid_request_no_writes(self):
        io=Fake()
        with self.assertRaises(ValueError):Driver(io,'psw800-1.44','TEST').apply(dict(STATE,voltage=100),LIMITS)
        self.assertEqual(io.writes,[])
    def test_identity_mismatch_no_writes(self):
        io=Fake()
        with self.assertRaises(ValueError):Driver(io,'psw800-1.44','OTHER').apply(STATE,LIMITS)
        self.assertEqual(io.writes,[])
    def test_off_before_change_on_after_readback(self):
        io=Fake();Driver(io,'psw800-1.44','TEST').apply(STATE,LIMITS)
        self.assertEqual(io.writes[0],'OUTP OFF');self.assertEqual(io.writes[-1],'OUTP ON')
    def test_bad_readback_stays_off(self):
        io=Fake();io.bad_readback=True
        with self.assertRaises(OSError):Driver(io,'psw800-1.44','TEST').apply(STATE,LIMITS)
        self.assertNotIn('OUTP ON',io.writes);self.assertEqual(io.writes[-1],'OUTP OFF')
    def test_fault_latched(self):
        io=Fake();c=Controller(config(),lambda _:io);io.bad_readback=True
        with self.assertRaises(OSError):c.call('supply','apply',STATE)
        io.bad_readback=False
        with self.assertRaises(ValueError):c.call('supply','apply',STATE)
        c.call('supply','identify',{})
        with self.assertRaises(ValueError):c.call('supply','apply',STATE)
        c.call('supply','off',{});c.call('supply','apply',STATE)
    def test_watchdog(self):
        io=Fake();c=Controller(config(),lambda _:io);c.start()
        try:
            c.call('supply','apply',STATE)
            time.sleep(1.5)
            self.assertEqual(io.values['OUTP'],'0');self.assertNotIn('supply',c.leases)
        finally:c.close()
    def test_uncommissioned_and_gateway_blocked(self):
        for changes in [{'commissioned':False},{'transport':{'kind':'gateway'}}]:
            cfg=config();cfg['devices']['supply'].update(changes);c=Controller(cfg,Fake)
            with self.assertRaises(ValueError):c.call('supply','apply',STATE)
    def test_raw_and_unknown_operations_blocked(self):
        c=Controller(config(),Fake)
        with self.assertRaises(ValueError):c.call('supply','write',{'command':'OUTP ON'})
        with self.assertRaises(ValueError):c.call('supply','read',{'operation':'OUTP ON'})
    def test_expired_renewal_rejected(self):
        c=Controller(config(),Fake);c.leases['supply']=time.monotonic()-1
        with self.assertRaises(ValueError):c.call('supply','renew',{})

class FramingTests(unittest.TestCase):
    def exercise(self, fragments, term='\n', maximum=10000):
        a,b=socket.socketpair();io=Transport({'kind':'tcp','read_termination':term,'max_message':maximum});io.handle=a
        def send():
            with b:
                for piece in fragments:b.sendall(piece);time.sleep(.002)
        t=threading.Thread(target=send);t.start()
        try:return io._tcp_message()
        finally:a.close();t.join()
    def test_fragmented_binary_embedded_newline(self):
        payload=b'\x00\n\xff12345';packet=b'#18'+payload+b'\n'
        self.assertEqual(self.exercise([packet[:1],packet[1:4],packet[4:7],packet[7:]]),packet)
    def test_tektronix_lf_cr_between_messages(self):
        a,b=socket.socketpair()
        io=Transport({'kind':'tcp','read_padding':'\r'});io.handle=a
        # Embedded LF must remain in the binary payload, even with a residual CR prefix.
        b.sendall(b'identity\n\r#13A\nB\n\r')
        try:
            self.assertEqual(io._tcp_message(),b'identity\n')
            self.assertEqual(io._tcp_message(),b'#13A\nB\n')
        finally:a.close();b.close()

    def test_cr_keithley(self):self.assertEqual(self.exercise([b'KEITH',b'LEY\r'],'\r'),b'KEITHLEY\r')
    def test_truncated_block(self):
        with self.assertRaises(OSError):self.exercise([b'#210tiny'])
    def test_indefinite_rejected(self):
        with self.assertRaises(ValueError):self.exercise([b'#0abc\n'])
    def test_limit(self):
        with self.assertRaises(ValueError):self.exercise([b'#3100'],maximum=10)
    def test_usb_eom_not_short_read(self):
        io=Transport({'kind':'usb','delay':0});io.handle=1
        attrs=iter([0,1])
        def ioctl(fd,cmd,buf,mutate):buf[0]=next(attrs)
        with patch('os.write',return_value=5),patch('os.read',side_effect=[b'ab\n',b'cd']),patch('fcntl.ioctl',side_effect=ioctl):
            self.assertEqual(io.transaction(b'CURV?'),b'ab\ncd')

class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.token='x'*40
        p=Path(self.tmp.name)/'token';p.write_text(self.token)
        cfg=config();cfg.update(listen=['127.0.0.1',0],token_file=str(p))
        self.io=Fake();self.server=make_server(cfg,Controller(cfg,lambda _:self.io),development=True)
        self.thread=threading.Thread(target=self.server.serve_forever);self.thread.start()
        self.url=f'http://127.0.0.1:{self.server.server_port}'
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()
    def request(self,path,body=None,token=None):
        req=urllib.request.Request(self.url+path,None if body is None else json.dumps(body).encode(),
                                   {'Authorization':'Bearer '+(token or '')})
        with urllib.request.urlopen(req) as r:return json.load(r)
    def test_auth_required(self):
        with self.assertRaises(urllib.error.HTTPError) as e:self.request('/v1/status')
        self.assertEqual(e.exception.code,401)
    def test_no_raw_gateway_route_in_control_mode(self):
        with self.assertRaises(urllib.error.HTTPError) as e:self.request('/v1/transaction',{'data':'T1VUUCBPTg=='},self.token)
        self.assertEqual(e.exception.code,404);self.assertEqual(self.io.writes,[])
    def test_limit_via_http(self):
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.request('/v1/control',{'device':'supply','action':'apply','args':dict(STATE,voltage=100)},self.token)
        self.assertEqual(e.exception.code,400);self.assertEqual(self.io.writes,[])
    def test_tls_required_remote(self):
        cfg=config();cfg.update(listen=['0.0.0.0',0],token_file='/unused')
        with self.assertRaises(ValueError):make_server(cfg,Controller(cfg),development=True)

if __name__=='__main__':unittest.main()
