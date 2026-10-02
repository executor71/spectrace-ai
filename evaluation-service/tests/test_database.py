from copy import deepcopy
import json,os,unittest
from uuid import UUID,uuid4
from unittest.mock import patch
import psycopg
from fastapi.testclient import TestClient
from app.main import app,connection
from app.metrics import evaluate,digest
from test_metrics import FIXTURE

@unittest.skipUnless(os.getenv('TEST_MIGRATION_PASSWORD'),'Isolated integration database required')
class DatabaseTests(unittest.TestCase):
    @classmethod
    def admin(cls):return psycopg.connect(host=os.environ['EVALUATION_DB_HOST'],dbname=os.environ['EVALUATION_DB_NAME'],user='migration_owner',password=os.environ['TEST_MIGRATION_PASSWORD'])
    @classmethod
    def setUpClass(cls):
        with cls.admin() as db:
            old=db.execute("SELECT requirement_id FROM evaluation.requirement_binding WHERE case_id='access-development'").fetchone()
            if old:cls.rid=str(old[0])
            else:
                cls.rid=str(uuid4());db.execute("INSERT INTO app.requirement(id,title,description) VALUES(%s,%s,%s)",(UUID(cls.rid),FIXTURE['requirement']['title'],FIXTURE['requirement']['description']))
                db.execute("INSERT INTO evaluation.requirement_binding VALUES(%s,'phase6-v1','access-development')",(UUID(cls.rid),))
    def setUp(self):self.client=TestClient(app)
    def run_evaluation(self,fail=False):
        fixture=deepcopy(FIXTURE)
        for case in fixture['inputs']['testCases']:case['requirementId']=self.rid
        batch={'testCases':[dict(c,generatedContent=deepcopy(c),reviewRevision=0) for c in fixture['inputs']['testCases']],
               'sourceAnalysis':fixture['inputs']['sourceAnalysis'],'generationId':str(uuid4()),'stale':False}
        with patch('app.main.backend',side_effect=lambda path,allow_missing=False:batch if path.endswith('/test-cases') else fixture['requirement']),patch('app.main.search',return_value=fixture['inputs']['searchHits']):
            response=self.client.post('/api/evaluations',json={'requirementId':self.rid});self.assertEqual(response.status_code,201,response.text);return response.json()
    def test_run_persists_and_get_list_match(self):
        report=self.run_evaluation();self.assertEqual(self.client.get('/api/evaluations/'+report['id']).json(),report)
        with patch('app.main.backend',return_value=FIXTURE['requirement']):
            rows=self.client.get('/api/requirements/'+self.rid+'/evaluations').json();self.assertIn(report,rows)
    def test_replay_uses_only_saved_snapshots(self):
        report=self.run_evaluation()
        with connection() as db:snapshot=db.execute('SELECT snapshot_json FROM evaluation.evaluation_run WHERE id=%s',(UUID(report['id']),)).fetchone()[0]
        self.assertEqual(evaluate(snapshot['groundTruth'],snapshot['inputs']),report['metrics']);self.assertEqual(digest(snapshot['inputs']),report['inputHash'])
    def test_reader_can_read_truth_but_not_change_it(self):
        with connection() as db:self.assertEqual(db.execute('SELECT count(*) FROM evaluation.ground_truth').fetchone()[0],3)
        for sql in ["UPDATE evaluation.ground_truth SET split='development'",'DELETE FROM evaluation.ground_truth',"INSERT INTO evaluation.evidence_catalog VALUES(gen_random_uuid(),'{}')"]:
            with self.assertRaises(psycopg.errors.InsufficientPrivilege),connection() as db:db.execute(sql)
    def test_evaluation_role_cannot_read_app_or_rag(self):
        for sql in ['SELECT * FROM app.test_case','SELECT * FROM rag.knowledge_chunk']:
            with self.assertRaises(psycopg.errors.InsufficientPrivilege),connection() as db:db.execute(sql)
    def test_app_and_rag_roles_cannot_access_truth_or_writer_function(self):
        with self.admin() as db:
            for role in ['app_user','rag_reader']:
                self.assertFalse(db.execute("SELECT has_schema_privilege(%s,'evaluation','USAGE')",(role,)).fetchone()[0])
                self.assertFalse(db.execute("SELECT has_function_privilege(%s,'evaluation.record_run(uuid,uuid,text,jsonb,jsonb)','EXECUTE')",(role,)).fetchone()[0])
    def test_immutability_also_applies_to_owner(self):
        report=self.run_evaluation()
        for sql,args in [("UPDATE evaluation.ground_truth SET truth_hash='tamper'",()),('DELETE FROM evaluation.evaluation_run WHERE id=%s',(UUID(report['id']),))]:
            with self.assertRaises(psycopg.Error),self.admin() as db:db.execute(sql,args)
    def test_unknown_run_and_requirement_ids404(self):
        self.assertEqual(self.client.get('/api/evaluations/'+str(uuid4())).status_code,404)
    def test_api_has_no_groundtruth_or_update_endpoint(self):
        self.assertEqual(self.client.get('/api/ground-truth').status_code,404)
        self.assertEqual(self.client.patch('/api/evaluations/'+str(uuid4()),json={}).status_code,405)
