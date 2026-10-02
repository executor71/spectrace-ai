from copy import deepcopy
import json
from pathlib import Path
import unittest
from app.metrics import evaluate, digest, validity, matches, consistency

FIXTURE=json.loads((Path(__file__).parent/'fixtures/development.json').read_text(encoding='utf-8'))

class MetricsTests(unittest.TestCase):
    def setUp(self):
        self.truth=deepcopy(FIXTURE['truth']);self.inputs=deepcopy(FIXTURE['inputs'])
    def result(self):return evaluate(self.truth,self.inputs)
    def test_document_recall_deduplicates_chunks(self):
        expected=self.truth['expectedEvidenceDocumentIds'];self.inputs['searchHits']=[{'documentId':expected[0]}]*4+[{'documentId':expected[1]}]
        self.assertEqual(self.result()['recallAt5']['value'],.5)
    def test_sixth_chunk_does_not_count(self):
        expected=self.truth['expectedEvidenceDocumentIds'];self.inputs['searchHits']=[{'documentId':'not-expected'}]*5+[{'documentId':expected[0]}]
        self.assertEqual(self.result()['recallAt5']['value'],0)
    def test_missing_documents_preserved(self):
        self.inputs['searchHits']=[];m=self.result()['recallAt5'];self.assertEqual(m['missingDocumentIds'],sorted(self.truth['expectedEvidenceDocumentIds']));self.assertEqual(m['denominator'],4)
    def test_empty_expected_documents_are_na(self):
        self.truth['expectedEvidenceDocumentIds']=[];self.assertIsNone(self.result()['recallAt5']['value'])
    def test_strict_coverage_exposes_missing_state_checks(self):
        result=self.result();self.assertEqual(result['scenarioCoverage']['numerator'],2);self.assertEqual(result['scenarioCoverage']['denominator'],5)
        self.assertEqual(result['testCaseValidity']['value'],1)
    def test_description_paraphrase_does_not_change_structural_match(self):
        prior=self.result();self.inputs['testCases'][0]['scenario']='Different words; identical structured contract'
        self.assertEqual(self.result()['scenarioCoverage'],prior['scenarioCoverage'])
    def test_wrong_category_cannot_match(self):
        self.inputs['testCases'][0]['type']='EXCEPTION';self.assertEqual(self.result()['scenarioCoverage']['numerator'],1)
    def test_conditions_are_not_merged_across_test_cases(self):
        case=self.inputs['testCases'][0];other=deepcopy(case);other['testCaseId']='split';other['expectedResult']['assertions']=case['expectedResult']['assertions'][1:]
        case['expectedResult']['assertions']=case['expectedResult']['assertions'][:1];self.inputs['testCases'].append(other)
        self.assertEqual(self.result()['scenarioCoverage']['numerator'],1)
    def test_duplicate_tc_does_not_inflate_coverage(self):
        self.inputs['testCases']+=deepcopy(self.inputs['testCases']);self.assertEqual(self.result()['scenarioCoverage']['value'],.4)
    def test_optional_scenarios_not_in_required_denominator(self):
        self.truth['optionalTestScenarios']*=3;self.assertEqual(self.result()['scenarioCoverage']['denominator'],5)
    def test_forbidden_self_approval_fails(self):
        case=self.inputs['testCases'][1];case['expectedResult']['assertions']=[{'kind':'HTTP_STATUS','value':200}]
        result=self.result()['testCaseValidity'];self.assertEqual(result['failedCount'],1);self.assertEqual(result['value'],.8)
    def test_contradictory_status_fails(self):
        self.inputs['testCases'][0]['expectedResult']['assertions'][0]['value']=500
        self.assertEqual(self.result()['testCaseValidity']['cases'][0]['checks']['noStructuredContradiction'],'FAIL')
    def test_unsupported_assertion_is_unknown_not_pass(self):
        self.inputs['testCases'][0]['expectedResult']['assertions'].append({'kind':'SOMETHING_NEW','value':1})
        result=self.result();self.assertEqual(result['testCaseValidity']['unknownCount'],1);self.assertEqual(result['testCaseValidity']['value'],.8)
        self.assertEqual(result['manualSemanticConsistency']['status'],'NOT_ASSESSED')
    def test_forged_evidence_pair_fails(self):
        self.inputs['testCases'][0]['evidence'][0]['documentId']='forged';self.assertEqual(self.result()['testCaseValidity']['failedCount'],1)
    def test_evidence_must_exist_in_source_and_catalog(self):
        self.inputs['evidenceCatalog']=[];self.assertEqual(self.result()['testCaseValidity']['value'],0)
    def test_foreign_requirement_fails(self):
        self.inputs['testCases'][0]['requirementId']='other';self.assertEqual(self.result()['testCaseValidity']['failedCount'],1)
    def test_all_required_checklist_fields(self):
        for field in ['scenario','preconditions','input','steps','expectedResult','evidence']:
            with self.subTest(field=field):
                case=deepcopy(self.inputs['testCases'][0]);case.pop(field)
                self.assertEqual(validity(case,self.truth,self.inputs['sourceAnalysis'],self.inputs['evidenceCatalog'],self.inputs['requirementId'])['status'],'FAIL')
    def test_zero_testcases_not_perfect_validity(self):
        self.inputs['testCases']=[];result=self.result();self.assertEqual(result['scenarioCoverage']['value'],0);self.assertIsNone(result['testCaseValidity']['value'])
    def test_deterministic_hash_and_replay(self):
        self.assertEqual(digest({'a':1,'b':2}),digest({'b':2,'a':1}));self.assertEqual(self.result(),evaluate(json.loads(json.dumps(self.truth)),json.loads(json.dumps(self.inputs))))
    def test_unknown_operator_fails_closed(self):
        with self.assertRaises(ValueError):matches({}, {'op':'llmJudge'})
    def test_structured_match_does_not_coerce_boolean_to_integer(self):
        self.assertFalse(matches({'input':{'count':True}},{'op':'equals','path':'/input/count','value':1}))
    def test_empty_assertions_require_manual_consistency(self):
        self.inputs['testCases'][0]['expectedResult']['assertions']=[];self.assertEqual(self.result()['testCaseValidity']['unknownCount'],1)
