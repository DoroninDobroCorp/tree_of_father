import concurrent.futures
import copy
import json
import pathlib
import subprocess
import sys
import tempfile
import threading
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from tech_store import TechStore, validate
from workshop_store import Conflict
ROOT=pathlib.Path(__file__).resolve().parents[1]
TREE=json.loads((ROOT/'tech-src'/'tech-tree.json').read_text())
IDS=[t['id'] for t in TREE['techs']]
STATE={'schema':1,'marks':{'sanding':'done','fdm':'active','clean':'todo'},'target':'bench','money':'balance'}
class TechStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.temp.name);self.store=TechStore(self.root,IDS,threading.Lock(),3)
        (self.root/'workshop.json').write_text('PLAN MUST REMAIN EXACT')
    def tearDown(self):self.temp.cleanup()
    def req(self,rev,state=None,id=None):return dict(baseRevision=rev,requestId=id or 'request-%08d'%rev,state=copy.deepcopy(state or STATE))
    def test_roundtrip_and_plan_isolation(self):
        self.assertEqual(self.store.read(),{'revision':0,'state':None});self.store.write(self.req(0))
        self.assertEqual(self.store.read()['state'],STATE);self.assertEqual((self.root/'workshop.json').read_text(),'PLAN MUST REMAIN EXACT')
    def test_stale_revision_is_rejected(self):
        self.store.write(self.req(0));r=self.req(0,id='other-device');r['state']['marks']={}
        with self.assertRaises(Conflict):self.store.write(r)
        self.assertEqual(self.store.read()['state'],STATE)
    def test_lost_response_retry_is_idempotent(self):
        req=self.req(0);self.assertEqual(self.store.write(req),self.store.write(req));self.assertEqual(self.store.read()['revision'],1)
    def test_backup_contains_previous_state_and_rotates(self):
        for i in range(6):self.store.write(self.req(i))
        copies=sorted(self.store.backups.glob('*.json'));self.assertEqual(len(copies),3);self.assertEqual(json.loads(copies[-1].read_text())['revision'],5)
    def test_concurrent_writers_cannot_replace_each_other(self):
        def writer(i):
            try:return self.store.write(self.req(0,id='parallel-%08d'%i))['revision']
            except Conflict:return 'conflict'
        with concurrent.futures.ThreadPoolExecutor(8) as pool:out=list(pool.map(writer,range(8)))
        self.assertEqual(out.count(1),1);self.assertEqual(out.count('conflict'),7)
    def test_bad_marks_preserve_disk(self):
        self.store.write(self.req(0));before=self.store.path.read_bytes()
        mutations=[lambda s:s['marks'].update(unknown='done'),lambda s:s['marks'].update(sanding='mastered'),lambda s:s.update(target='nowhere'),lambda s:s.update(money='free'),lambda s:s.update(schema=2),lambda s:s.update(extra=1)]
        for mutate in mutations:
            state=copy.deepcopy(STATE);mutate(state)
            with self.assertRaises(ValueError):self.store.write(dict(baseRevision=1,requestId='bad-request-1',state=state))
            self.assertEqual(self.store.path.read_bytes(),before)
    def test_validate_accepts_minimal_state(self):
        self.assertEqual(validate({'schema':1,'marks':{}},set(IDS)),{'schema':1,'marks':{}})
class TechTreeBuildTests(unittest.TestCase):
    def test_build_checks_tree_and_covers_every_plan_step(self):
        out=subprocess.run([sys.executable,str(ROOT/'tech-src'/'build_tech.py')],capture_output=True,text=True,cwd=ROOT)
        self.assertEqual(out.returncode,0,out.stderr);self.assertNotIn('Шаги плана без технологии',out.stderr)
        page=(ROOT/'tech.html').read_text();self.assertIn('id="tech-data"',page);self.assertNotIn('__DATA__',page)
if __name__=='__main__':unittest.main()
