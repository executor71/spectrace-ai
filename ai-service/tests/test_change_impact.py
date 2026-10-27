import copy,json,unittest
from unittest.mock import Mock,patch
from app.change_impact import condition_diff,assemble,Workflow,analyze,Input
from app.analysis_service import InvalidAnalysisError
from app.llm_provider import LlmTimeoutError,LlmUnavailableError
from fastapi import HTTPException

def request():
 return dict(impactId='impact',baselineRequirementId='req',baselineRevision='frozen',proposalTitle='권한 변경',proposalContent='부서장 또는 자산관리 담당자가 승인한다. 자기 승인은 계속 금지한다.',currentPolicyHash='policy',createdAt='2026-10-27T00:00:00Z',baselineSnapshot=dict(analysis=dict(confirmedConditions=[dict(text='부서장만 승인한다.',chunkId='c1'),dict(text='자기 승인은 금지한다.',chunkId='c2')],evidence=[dict(chunkId='c1',documentId='d1')]),testCases=dict(policyHash='policy',testCases=[dict(testCaseId='tc',scenario='승인',type='AUTHORIZATION',evidence=[dict(chunkId='c1',documentId='d1')],approvalStatus='APPROVED',reviewRevision=2,executable=True)]),policyRegistry={'plans':[]},executions=[]))
def pairs():return [dict(beforeIndex=0,afterText='부서장',changeType='UNCHANGED',rationale='기존 역할 유지 제안'),dict(beforeIndex=None,afterText='자산관리 담당자',changeType='ADDED',rationale='새 역할 제안'),dict(beforeIndex=1,afterText='자기 승인은 계속 금지한다.',changeType='UNCHANGED',rationale='자기 승인 금지 유지')]
def provider(values=None):
 llm=Mock();llm.generate.return_value=json.dumps({'changes':pairs() if values is None else values},ensure_ascii=False);return llm
def graph():return dict(status='AVAILABLE',paths=[dict(path=[dict(type='Requirement',id='req'),dict(type='Api',id='API-LOAN-APPROVE')],relations=['AFFECTS'],evidenceChunkIds=['c1'])],relatedApis=[dict(id='API-LOAN-APPROVE',method='POST',pathTemplate='/loans/{loanId}/approve')],relatedTestCases=[dict(id='tc')])

class ComparisonTests(unittest.TestCase):
 def test_source_guard_reconciles_self_prohibition_false_removal(self):
  from app.condition_atoms import reconcile
  req=request();conditions=req['baselineSnapshot']['analysis']['confirmedConditions']
  bad=[dict(changeType='REMOVED',beforeCondition=conditions[1]['text'],baselineCondition=conditions[1]['text'])]
  changes=reconcile(req,bad)
  self.assertEqual(['UNCHANGED','ADDED','UNCHANGED'],[c['changeType'] for c in changes])
  self.assertTrue(all(c['requiresConfirmation'] for c in changes))
 def test_source_guard_does_not_invent_allowance_for_negative_role(self):
  from app.condition_atoms import atoms
  self.assertNotIn('approval.actor.부서장',atoms('부서장은 승인할 수 없다.'))
 def test_lifted_self_prohibition_is_not_unchanged_denial(self):
  from app.condition_atoms import atoms
  self.assertNotIn('approval.self.denied',atoms('자기 승인 금지를 해제한다.'))
 def test_cached_comparison_uses_no_model_call(self):
  req=request();req['cachedModelChanges']=condition_diff(req,provider());req['cachedAnalysisId']='old';p=Mock();search=Mock();search.search.return_value=[]
  r=Workflow(search,p,lambda _:graph()).analyze(req)
  p.generate.assert_not_called();self.assertEqual(0,r['llmCallCount']);self.assertEqual('old',r['reusedModelAnalysisId'])
 def test_added_and_unchanged_with_no_policy_mutation(self):
  req=request();original=copy.deepcopy(req);changes=condition_diff(req,provider());self.assertEqual(['UNCHANGED','ADDED','UNCHANGED'],[c['changeType'] for c in changes]);self.assertEqual(original,req);self.assertTrue(all(c['requiresConfirmation'] for c in changes));self.assertFalse(any(c['businessPolicyApproved'] for c in changes))
 def test_modified(self):
  p=pairs();p[0]['changeType']='MODIFIED';self.assertEqual('MODIFIED',condition_diff(request(),provider(p))[0]['changeType'])
 def test_removed(self):
  p=pairs();p[0].update(changeType='REMOVED',afterText=None);self.assertEqual('REMOVED',condition_diff(request(),provider(p))[0]['changeType'])
 def test_unknown_baseline_index_rejected(self):
  p=pairs();p[0]['beforeIndex']=99
  with self.assertRaises(InvalidAnalysisError):condition_diff(request(),provider(p))
 def test_invented_proposal_quote_rejected(self):
  p=pairs();p[1]['afterText']='모든 사용자가 승인한다'
  with self.assertRaises(InvalidAnalysisError):condition_diff(request(),provider(p))
 def test_arbitrary_api_in_output_rejected(self):
  p=provider();p.generate.return_value=json.dumps({'changes':pairs(),'api':'https://arbitrary.invalid'})
  with self.assertRaises(InvalidAnalysisError):condition_diff(request(),p)
 def test_bad_json(self):
  p=provider();p.generate.return_value='not JSON'
  with self.assertRaises(InvalidAnalysisError):condition_diff(request(),p)
 def test_omitted_existing_condition_uncertain(self):self.assertEqual('UNCERTAIN',condition_diff(request(),provider(pairs()[:2]))[-1]['changeType'])
 def test_no_baseline_evidence_uncertain(self):
  req=request();req['baselineSnapshot']['analysis']['confirmedConditions']=[]
  self.assertEqual('UNCERTAIN',condition_diff(req,provider([pairs()[1]]))[0]['changeType'])
 def test_no_output_rejected(self):
  req=request();req['baselineSnapshot']['analysis']['confirmedConditions']=[]
  with self.assertRaises(InvalidAnalysisError):condition_diff(req,provider([]))
 def test_graph_api_and_tc_grounded(self):
  req=request();r=assemble(req,condition_diff(req,provider()),[],graph());self.assertEqual('API-LOAN-APPROVE',r['affectedApis'][0]['apiId']);self.assertEqual('REVIEW',r['affectedTestCases'][0]['classification']);self.assertEqual('TEMPLATE_UNSUPPORTED',r['newTestSuggestions'][0]['templateSupport']);self.assertIsNone(r['newTestSuggestions'][0]['expectedResult'])
 def test_graph_outage_partial_not_fake_success(self):
  req=request();r=assemble(req,condition_diff(req,provider()),[],{'status':'UNAVAILABLE','paths':[]});self.assertEqual('PARTIAL_REVIEW_REQUIRED',r['analysisCompleteness']);self.assertEqual([],r['affectedApis']);self.assertTrue(r['evidenceRefs'])
 def test_graph_empty_is_distinct(self):
  req=request();r=assemble(req,condition_diff(req,provider()),[],{'status':'AVAILABLE','paths':[]});self.assertEqual('AVAILABLE',r['graphStatus']);self.assertEqual([],r['affectedApis'])
 def test_unchanged_tc_keep(self):
  req=request();changes=condition_diff(req,provider([pairs()[0],pairs()[2]]));r=assemble(req,changes,[],graph());self.assertEqual('KEEP',r['affectedTestCases'][0]['classification'])
 def test_policy_hash_mismatch_review(self):
  req=request();req['currentPolicyHash']='new';changes=condition_diff(req,provider([pairs()[0],pairs()[2]]));r=assemble(req,changes,[],graph());self.assertFalse(r['affectedTestCases'][0]['policyCompatible']);self.assertEqual('REVIEW',r['affectedTestCases'][0]['classification'])
 def test_langgraph_one_provider_call(self):
  p=provider();search=Mock();search.search.return_value=[];r=Workflow(search,p,lambda _:graph()).analyze(request());self.assertEqual(1,p.generate.call_count);self.assertEqual(1,r['llmCallCount']);self.assertGreaterEqual(r['analysisDurationMs'],0)
 def test_timeout_http(self):
  worker=Mock();worker.analyze.side_effect=LlmTimeoutError()
  with self.assertRaises(HTTPException) as caught:analyze(Input(**request()),worker)
  self.assertEqual(504,caught.exception.status_code)
 def test_invalid_output_http(self):
  worker=Mock();worker.analyze.side_effect=InvalidAnalysisError()
  with self.assertRaises(HTTPException) as caught:analyze(Input(**request()),worker)
  self.assertEqual(502,caught.exception.status_code)
 def test_capacity_shared(self):
  from app.analysis_api import slot
  slot.acquire()
  try:
   with self.assertRaises(HTTPException) as caught:analyze(Input(**request()),Mock())
   self.assertEqual(429,caught.exception.status_code)
  finally:slot.release()

if __name__=='__main__':unittest.main()
