import json
import threading
import time
import unittest
import urllib.request
import urllib.error
from labinstruments.fra_engine import FRAConfig,FRAEngine
from labinstruments.fra_simulation import Simulation
from labinstruments.fra_web import make_server


class WebTests(unittest.TestCase):
    def setUp(self):
        self.server=make_server(FRAEngine(Simulation),FRAConfig(),port=0)
        self.thread=threading.Thread(target=self.server.serve_forever);self.thread.start()
        self.url=f'http://127.0.0.1:{self.server.server_port}'
    def tearDown(self):
        self.server.jobs.close();self.server.shutdown();self.server.server_close();self.thread.join()
    def request(self,path,body=None,token=True):
        headers={'Content-Type':'application/json'}
        if token:headers['X-FRA-Token']=self.server.api_token
        req=urllib.request.Request(self.url+path,data=None if body is None else json.dumps(body).encode(),headers=headers)
        return urllib.request.urlopen(req,timeout=3)
    def test_gui_assets_and_csrf(self):
        with self.request('/') as r:
            text=r.read();self.assertIn(b'STOP',text);self.assertIn(b'/api/start',text);self.assertNotIn(b'__TOKEN__',text)
        with self.assertRaises(urllib.error.HTTPError) as e:self.request('/api/start',{},False)
        self.assertEqual(e.exception.code,403)
    def test_job_progress_export_stop(self):
        with self.request('/api/start',{'start_frequency':1000,'stop_frequency':10000,'points':10,'averages':1,'minimum_settling_s':.1}) as r:self.assertEqual(r.status,202)
        with self.assertRaises(urllib.error.HTTPError):self.request('/api/start',{})
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            with self.request('/api/status') as r:s=json.load(r)
            if s['completed']>0:break
            time.sleep(.02)
        self.assertTrue(s['running']);self.assertGreater(s['completed'],0)
        with self.request('/api/stop',{}):pass
        self.server.jobs.close()
        with self.request('/api/status') as r:s=json.load(r)
        self.assertEqual(s['result']['status'],'cancelled');self.assertTrue(s['result']['cleanup']['source_off'])
        for kind in ['json','png','csv','svg']:
            with self.request('/api/export/'+kind) as r:self.assertEqual(r.status,200);self.assertGreater(len(r.read()),30)
    def test_validate_invalid_and_single(self):
        with self.assertRaises(urllib.error.HTTPError):self.request('/api/validate',{'amplitude':-1})
        with self.request('/api/start',{'start_frequency':1000,'stop_frequency':1000,'points':1,'averages':1}):pass
        self.server.jobs.close()
        # close is an explicit stop; outcome may be cancelled before acquiring.
        self.assertFalse(self.server.jobs.snapshot()['running'])
    def test_persistence(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            self.server.jobs.results_dir=Path(directory)
            with self.request('/api/start',{'start_frequency':1000,'stop_frequency':1000,'averages':1,'settling_cycles':0,'minimum_settling_s':0}):pass
            self.server.jobs.thread.join(timeout=3)
            files=list(Path(directory).glob('*.json'));self.assertEqual(len(files),1)
            self.assertEqual(json.loads(files[0].read_text())['status'],'completed')
