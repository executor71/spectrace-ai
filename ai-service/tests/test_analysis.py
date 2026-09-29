import json
import unittest
from unittest.mock import Mock
from fastapi.testclient import TestClient
from app.analysis_models import AnalysisRequest, AnalysisDraft
from app.analysis_service import AnalysisService, InvalidAnalysisError, AnalysisInputError, catalog
from app.analysis_api import get_analysis_service, slot
from app.llm_provider import LlmUnavailableError
from app.main import app
from app.vector_search import SearchHit

RID='11111111-1111-4111-8111-111111111111'
HIT=SearchHit(documentId='22222222-2222-4222-8222-222222222222',chunkId='33333333-3333-4333-8333-333333333333',
    documentType='BUSINESS_RULE',section='승인',contentSnippet='자기 승인은 금지한다. 부서장이 승인한다.',score=0.8,
    domain='IT_ASSET',version='1.0.0',relatedApis=['POST /loans/{id}/approve'])
REQUEST=AnalysisRequest(requirementId=RID,title='승인',description='자기 승인을 금지한다.')


def draft(**changes):
    value=dict(evidenceSufficiency="SUFFICIENT",confirmedConditionIds=['E1S1'],ambiguousExpressions=[],missingConditions=[],
        relatedBusinessRuleIds=['E1S1'],relatedApiIds=['E1A1'],clarificationQuestions=[])
    value.update(changes)
    return json.dumps(value,ensure_ascii=False)


class AnalysisTests(unittest.TestCase):
    def service(self, values, hits=None):
        search=Mock();search.search.return_value=[HIT] if hits is None else hits
        llm=Mock();llm.generate.side_effect=values
        return AnalysisService(search,llm)

    def test_exact_evidence_and_original_query(self):
        service=self.service([draft()]); result=service.analyze(REQUEST)
        self.assertEqual(result.confirmedConditions[0].text,'자기 승인은 금지한다.')
        self.assertEqual(result.evidence[0].score,0.8)
        self.assertEqual(result.evidence[0].chunkId,HIT.chunkId)
        self.assertEqual(result.relatedApis[0].api,HIT.relatedApis[0])
        sent=service.search.search.call_args.args[0]
        self.assertEqual(sent.query,REQUEST.title+'\n'+REQUEST.description)
        self.assertEqual(sent.topK,5)

    def test_invalid_schema_retried_once_then_fails(self):
        service=self.service(['{}','not JSON'])
        with self.assertRaises(InvalidAnalysisError):service.analyze(REQUEST)
        self.assertEqual(service.llm.generate.call_count,2)

    def test_recover_after_single_invalid_response(self):
        service=self.service(['{}',draft()])
        self.assertEqual(service.analyze(REQUEST).requirementId,RID)
        self.assertEqual(service.llm.generate.call_count,2)

    def test_invented_rule_id_rejected(self):
        service=self.service([draft(confirmedConditionIds=['CEO_AUTO_APPROVAL_24H'])]*2)
        with self.assertRaises(InvalidAnalysisError):service.analyze(REQUEST)

    def test_invented_api_rejected(self):
        service=self.service([draft(relatedApiIds=['POST /vip/approve'])]*2)
        with self.assertRaises(InvalidAnalysisError):service.analyze(REQUEST)

    def test_model_cannot_supply_forged_evidence_or_claim_text(self):
        for field in ['evidence','confirmedConditions','requirementId']:
            with self.subTest(field=field):
                service=self.service([draft(**{field:'fabricated'})]*2)
                with self.assertRaises(InvalidAnalysisError):service.analyze(REQUEST)

    def test_non_business_rule_cannot_be_reported_as_business_rule(self):
        hit=HIT.model_copy(update={'documentType':'TEST_GUIDE'})
        with self.assertRaises(InvalidAnalysisError):self.service([draft()]*2,[hit]).analyze(REQUEST)

    def test_empty_search_requires_missing_and_questions(self):
        raw=draft(evidenceSufficiency='NONE',confirmedConditionIds=[],relatedBusinessRuleIds=[],relatedApiIds=[],
            missingConditions=['검색 근거가 없어 조건을 확인할 수 없습니다.'],clarificationQuestions=['승인 기준 문서를 제공해 주시겠습니까?'])
        result=self.service([raw],[]).analyze(REQUEST)
        self.assertEqual(result.confirmedConditions,[])
        self.assertEqual(result.evidence,[])
        self.assertTrue(result.missingConditions)

    def test_silent_insufficient_evidence_fails(self):
        with self.assertRaises(InvalidAnalysisError):self.service([draft(confirmedConditionIds=[])]*2).analyze(REQUEST)

    def test_uncertainty_requires_questions(self):
        with self.assertRaises(InvalidAnalysisError):self.service([draft(ambiguousExpressions=['빠르게'])]*2).analyze(REQUEST)

    def test_none_cannot_select_unrelated_existing_facts(self):
        with self.assertRaises(InvalidAnalysisError):self.service([draft(evidenceSufficiency='NONE')]*2).analyze(REQUEST)

    def test_input_qualifier_omitted_by_model_still_requires_clarification(self):
        request=REQUEST.model_copy(update={'description':'대여 신청을 빠르게 승인하고 필요한 경우 알림을 보낸다.'})
        result=self.service([draft()]).analyze(request)
        self.assertIn('빠르게',result.ambiguousExpressions)
        self.assertIn('필요한 경우',result.ambiguousExpressions)
        self.assertTrue(any('필요한 경우' in q for q in result.clarificationQuestions))
        self.assertEqual(result.confirmedConditions[0].text,'자기 승인은 금지한다.')

    def test_existing_ambiguity_is_not_duplicated(self):
        request=REQUEST.model_copy(update={'description':'빠르게 승인한다.'})
        result=self.service([draft(ambiguousExpressions=['빠르게'],clarificationQuestions=['빠르게의 시간 기준은?'])]).analyze(request)
        self.assertEqual(result.ambiguousExpressions,['빠르게'])
        self.assertEqual(len(result.clarificationQuestions),1)

    def test_full_sentence_preserves_negation(self):
        sentences,_=catalog([HIT])
        self.assertEqual(sentences['E1S1']['text'],'자기 승인은 금지한다.')
        self.assertFalse(any(v['text']=='자기 승인' for v in sentences.values()))

    def test_long_input_is_not_silently_truncated(self):
        service=self.service([])
        with self.assertRaises(AnalysisInputError):service.analyze(REQUEST.model_copy(update={'description':'가'*2001}))
        service.search.search.assert_not_called();service.llm.generate.assert_not_called()


class AnalysisApiTests(unittest.TestCase):
    def tearDown(self):app.dependency_overrides.clear()
    def test_explicit_invalid_output_failure(self):
        service=Mock();service.analyze.side_effect=InvalidAnalysisError('private model response')
        app.dependency_overrides[get_analysis_service]=lambda:service
        with TestClient(app) as client:
            response=client.post('/internal/v1/requirement-analysis',json=REQUEST.model_dump())
        self.assertEqual(response.status_code,502)
        self.assertEqual(response.json()['detail']['code'],'INVALID_ANALYSIS_OUTPUT')
        self.assertNotIn('private',response.text)
    def test_unavailable_model_is_not_success(self):
        service=Mock();service.analyze.side_effect=LlmUnavailableError('private URL')
        app.dependency_overrides[get_analysis_service]=lambda:service
        with TestClient(app) as client:response=client.post('/internal/v1/requirement-analysis',json=REQUEST.model_dump())
        self.assertEqual(response.status_code,503)
        self.assertNotIn('private',response.text)
    def test_unknown_schema_selector_rejected(self):
        with TestClient(app) as client:response=client.post('/internal/v1/requirement-analysis',json={**REQUEST.model_dump(),'schema':'evaluation'})
        self.assertEqual(response.status_code,422)
    def test_concurrent_call_is_explicitly_busy(self):
        service=Mock();app.dependency_overrides[get_analysis_service]=lambda:service
        slot.acquire()
        try:
            with TestClient(app) as client:response=client.post('/internal/v1/requirement-analysis',json=REQUEST.model_dump())
            self.assertEqual(response.status_code,429);service.analyze.assert_not_called()
        finally:slot.release()
