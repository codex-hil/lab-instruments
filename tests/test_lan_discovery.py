import unittest
from unittest.mock import patch
from labinstruments.lan_discovery import connect

class Socket:
    def __init__(self, identity):self.identity=identity;self.closed=False;self.sent=[]
    def settimeout(self,t):pass
    def sendall(self,b):self.sent.append(b)
    def recv(self,n):return self.identity
    def close(self):self.closed=True

class DiscoveryTests(unittest.TestCase):
    def config(self):
        return dict(host='192.168.2.1',port=4000,discover=dict(model='DPO4104',serial='C022184',subnet='192.168.2.0/30'))
    def test_hint_verified_without_scan(self):
        sock=Socket(b'TEKTRONIX,DPO4104,C022184,FW\n')
        with patch('labinstruments.lan_discovery.socket.create_connection',return_value=sock) as dial:
            host, got=connect(self.config())
        self.assertEqual(host,'192.168.2.1');self.assertIs(got,sock)
        self.assertEqual(dial.call_count,1);self.assertEqual(sock.sent,[b'*IDN?\n'])
    def test_changed_ip_rejects_wrong_model_and_keeps_verified_socket(self):
        wrong=Socket(b'TEKTRONIX,MSO4104,C022184,FW\n')
        right=Socket(b'TEKTRONIX,DPO4104,C022184,FW\n')
        with patch('labinstruments.lan_discovery.socket.create_connection',side_effect=[wrong,right]):
            host,got=connect(self.config())
        self.assertEqual(host,'192.168.2.2');self.assertIs(got,right)
        self.assertTrue(wrong.closed);self.assertFalse(right.closed)
    def test_missing_wrong_serial_and_unterminated(self):
        for data in [b'TEKTRONIX,DPO4104,OTHER,FW\n',b'X'*1024]:
            with patch('labinstruments.lan_discovery.socket.create_connection',side_effect=lambda *a,**k:Socket(data)):
                with self.assertRaises(OSError):connect(self.config())
    def test_ambiguous_scan_closes_connections(self):
        c=self.config();c.pop('host');socks=[]
        def dial(*a,**k):
            sock=Socket(b'TEKTRONIX,DPO4104,C022184,FW\n');socks.append(sock);return sock
        with patch('labinstruments.lan_discovery.socket.create_connection',side_effect=dial):
            with self.assertRaises(OSError):connect(c)
        self.assertTrue(all(s.closed for s in socks))
    def test_scope_bounds_no_network(self):
        for key,value in [('subnet','192.168.0.0/16'),('model','ANY'),('serial',''),('probe_timeout',10)]:
            c=self.config();c['discover'][key]=value
            with patch('labinstruments.lan_discovery.socket.create_connection') as dial:
                with self.assertRaises(ValueError):connect(c)
                dial.assert_not_called()
