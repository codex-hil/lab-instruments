import socket
import threading
import unittest
from hioki_lab.driver import MR8875, InstrumentError

class WireTest(unittest.TestCase):
    def listener(self, reply):
        server=socket.socket(); server.bind(('127.0.0.1',0)); server.listen()
        def run():
            conn,_=server.accept()
            with conn:
                conn.recv(1024)
                for fragment in reply:conn.sendall(fragment)
            server.close()
        threading.Thread(target=run,daemon=True).start()
        return MR8875('127.0.0.1',server.getsockname()[1],.5)

    def test_fragmented_header_and_delimiter(self):
        d=self.listener([b':MEMORY:REAL CH2_',b'1,+1.25E-3\r',b'\n'])
        self.assertEqual(d.query(':MEMory:REAL? CH2_1'),'CH2_1,+1.25E-3');d.close()

    def test_partial_response_disconnect_discards_socket(self):
        d=self.listener([b'123'])
        with self.assertRaises(InstrumentError):d.query('*IDN?')
        self.assertIsNone(d.sock);self.assertEqual(d.buffer,b'')

    def test_injection_rejected(self):
        with self.assertRaises(ValueError):MR8875().query('*IDN?\n:STARt')

    def test_waveform_block_boundaries_and_physical_units(self):
        d=MR8875();d.channels=['CH2_1'];commands=[]
        def query(command):
            commands.append(command)
            if command==':STATus?':return '0'
            if command==':MEMory:MAXPoint?':return '2001'
            if command.startswith(':MEMory:VDATa?'):
                return ','.join(['1.25']*int(command.split()[-1]))
            raise AssertionError(command)
        d.query=query;d.checked=lambda cmd:commands.append(cmd)
        d.configuration=lambda:{'sample_seconds':.01,'channels':[{'id':'CH2_1','enabled':True}]}
        result=d.waveform(['CH2_1'])
        self.assertEqual(len(result['data']['CH2_1']),2001)
        self.assertEqual(result['data']['CH2_1'][-1],1.25)
        self.assertIn(':MEMory:VDATa? 2000',commands)
        self.assertIn(':MEMory:VDATa? 1',commands)

    def test_busy_instrument_blocks_configuration(self):
        d=MR8875();d.query=lambda c:'17'
        with self.assertRaises(InstrumentError):d.configure_acquisition(.01,5)

if __name__=='__main__':unittest.main()
