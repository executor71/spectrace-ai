from copy import deepcopy
from unittest.mock import patch
from uuid import uuid4
import unittest
from fastapi.testclient import TestClient
from fastapi import HTTPException
from app.main import app
from app.metrics import digest
from test_metrics import FIXTURE

class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client=TestClient(app);self.fixture=deepcopy(FIXTURE);self.req=self.fixture['requirement'];self.rid=self.fixture['inputs']['requirementId']
        self.batch={'testCases':[dict(c,generatedContent=deepcopy(c),reviewRevision=0) for c in self.fixture['inputs']['testCases']],
                    'sourceAnalysis':self.fixture['inputs']['sourceAnalysis'],'generationId':str(uuid4()),'stale':False}
        self.dataset={'datasetVersion':'phase6-v1','caseId':'access-development','split':'development','groundTruthHash':digest(self.fixture['truth']),'requirementHash':digest(self.req)}
        self.backend=patch('app.main.backend',side_effect=self.source).start()
        self.search=patch('app.main.search',return_value=self.fixture['inputs']['searchHits']).start()
        self.truth=patch('app.main.load_truth',return_value=(self.fixture['truth'],self.dataset,self.fixture['inputs']['evidenceCatalog'])).start()
        self.save=patch('app.main.save').start();self.addCleanup(patch.stopall)
    def source(self,path,allow_missing=False):
        return self.batch if path.endswith('/test-cases') else self.fixture['inputs']['sourceAnalysis'] if path.endswith('/analysis') else self.req
    def post(self,**extra):return self.client.post('/api/evaluations',json={'requirementId':self.rid,**extra})
    def test_create_persists_exact_snapshot_and_hash(self):
        response=self.post();self.assertEqual(response.status_code,201);report=response.json();snapshot=self.save.call_args.args[1]
        self.assertEqual(report['inputHash'],digest(snapshot['inputs']));self.assertEqual(report['metrics']['scenarioCoverage']['value'],.4)
    def test_groundtruth_is_never_sent_to_search_or_generation(self):
        self.post();self.search.assert_called_once_with(self.req['title']+'\n'+self.req['description'])
        self.assertTrue(all('/api/requirements/' in c.args[0] and not c.args[0].endswith('/generate') for c in self.backend.call_args_list))
    def test_generated_default_is_not_reviewed_content(self):
        self.batch['testCases'][0]['scenario']='';response=self.post();self.assertEqual(response.json()['metrics']['testCaseValidity']['value'],1)
        response=self.post(contentMode='REVIEWED');self.assertEqual(response.json()['metrics']['testCaseValidity']['value'],.8)
    def test_unknown_fields_enums_and_bad_ids_are400(self):
        for extra in [{'contentMode':'APPROVED_ONLY'},{'datasetVersion':'forged'},{'groundTruth':{}},{'requirementId':'bad'}]:
            self.assertEqual(self.post(**extra).status_code,400)
        self.assertEqual(self.client.get('/api/evaluations/bad').status_code,400)
    def test_missing_requirement404(self):
        self.backend.side_effect=HTTPException(404,'Not found');self.assertEqual(self.post().status_code,404);self.save.assert_not_called()
    def test_unbound_requirement409(self):
        self.truth.side_effect=HTTPException(409,'Not bound');self.assertEqual(self.post().status_code,409)
    def test_requirement_fingerprint_mismatch409(self):
        self.req['description']='changed';self.assertEqual(self.post().status_code,409);self.search.assert_not_called()
    def test_search_failure_is_persisted_without_fake_score(self):
        self.search.side_effect=HTTPException(503,'Search unavailable');response=self.post();self.assertEqual(response.status_code,201)
        self.assertEqual(response.json()['status'],'FAILED');self.assertIsNone(response.json()['metrics']);self.save.assert_called_once()
    def test_missing_generation_is_explicit_and_validity_na(self):
        self.batch=None;response=self.post();self.assertIn('NO_SAVED_GENERATION',response.json()['issues']);self.assertIsNone(response.json()['metrics']['testCaseValidity']['value'])
    def test_stale_snapshot_is_visible_not_silently_dropped(self):
        self.batch['stale']=True;self.assertIn('STALE_GENERATION_SNAPSHOT',self.post().json()['issues'])
