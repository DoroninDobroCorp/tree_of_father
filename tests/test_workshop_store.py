import concurrent.futures
import copy
import json
import pathlib
import sys
import tempfile
import threading
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from workshop_store import Store, Conflict, validate
ROOT=pathlib.Path(__file__).resolve().parents[1]
CATALOG=json.loads((ROOT/'workshop-data.json').read_text())
STATE={'schema':4,'config':{'hoursPerMonth':25,'elapsedMonths':0,'monthlyBudget':0,'fx':1535},'steps':[{'id':sid,'title':sid,'module':'base','level':'project','hours':5,'budget':None,'items':(['x-sewing-kit'] if index else []),'deps':[],'result':'Проверка','note':'','basePercent':0,'archived':False} for index,sid in enumerate(['base-demo','sewing-demo'])],'entries':[],'items':{},'changes':[],'original':{'hours':10,'stepCount':2}}
class HoursStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.temp.name);self.store=Store(self.root,CATALOG,threading.Lock(),3)
        (self.root/'save.json').write_text('TREE MUST REMAIN EXACT')
    def tearDown(self):self.temp.cleanup()
    def req(self,rev,state=None,id=None):return dict(baseRevision=rev,requestId=id or 'request-%08d'%rev,state=copy.deepcopy(state or STATE))
    def test_roundtrip_and_tree_isolation(self):
        self.assertEqual(self.store.read()['revision'],0);self.store.write(self.req(0));self.assertEqual(self.store.read()['state'],STATE);self.assertEqual((self.root/'save.json').read_text(),'TREE MUST REMAIN EXACT')
    def test_stale_revision_is_rejected(self):
        self.store.write(self.req(0));r=self.req(0,id='other-device');r['state']['config']['elapsedMonths']=2
        with self.assertRaises(Conflict):self.store.write(r)
        self.assertEqual(self.store.read()['state'],STATE)
    def test_lost_response_retry_is_idempotent(self):
        req=self.req(0);self.assertEqual(self.store.write(req),self.store.write(req));self.assertEqual(self.store.read()['revision'],1)
    def test_backup_contains_previous_state_and_rotates(self):
        for i in range(7):self.store.write(self.req(i))
        copies=sorted(self.store.backups.glob('*.json'));self.assertEqual(len(copies),3);self.assertEqual(json.loads(copies[-1].read_text())['revision'],6)
    def test_concurrent_writers_cannot_replace_each_other(self):
        def writer(i):
            try:return self.store.write(self.req(0,id='parallel-%08d'%i))['revision']
            except Conflict:return 'conflict'
        with concurrent.futures.ThreadPoolExecutor(8) as pool:out=list(pool.map(writer,range(8)))
        self.assertEqual(out.count(1),1);self.assertEqual(out.count('conflict'),7)
    def test_bad_numbers_references_and_cycles_preserve_disk(self):
        self.store.write(self.req(0));before=self.store.path.read_bytes()
        mutations=[lambda s:s['config'].update(hoursPerMonth=0),lambda s:s['steps'][0].update(hours=float('nan')),lambda s:s['steps'][0].update(module='unknown'),lambda s:s['steps'][0].update(deps=[s['steps'][1]['id']])]
        for mutate in mutations:
            state=copy.deepcopy(STATE);mutate(state)
            if state['steps'][0]['deps']:state['steps'][1]['deps']=[state['steps'][0]['id']]
            with self.assertRaises(ValueError):self.store.write(self.req(1,state))
            self.assertEqual(self.store.path.read_bytes(),before)
    def test_calendar_settings_roundtrip_and_validation(self):
        state=copy.deepcopy(STATE);state['config'].update(hoursPerMonth=50,timeMode='calendar',startDate='2026-10-10',reservePercent=15)
        self.assertEqual(self.store.write(self.req(0,state))['state'],state)
        before=self.store.path.read_bytes()
        for patch in [{'startDate':'2026-02-30'},{'startDate':''},{'startDate':[]},{'timeMode':'invalid'},{'reservePercent':101}]:
            bad=copy.deepcopy(state);bad['config'].update(patch)
            with self.assertRaises(ValueError):self.store.write(self.req(1,bad))
            self.assertEqual(self.store.path.read_bytes(),before)
    def test_unique_purchases_and_unknown_budgets(self):
        state=copy.deepcopy(STATE);state['steps'][0]['items']=['x-sewing-kit']
        with self.assertRaises(ValueError):validate(state,CATALOG)
        self.assertEqual(validate(STATE,CATALOG),STATE)
if __name__=='__main__':unittest.main()
