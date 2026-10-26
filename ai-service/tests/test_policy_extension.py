import json
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4
from app.knowledge import load_corpus
from app.test_case_models import GenerationRequest
from app.test_case_policy import load_policy, compile_candidates
from app.test_case_registry import validate_policy
from app.test_case_service import TestCaseGenerator

POLICY, HASH = load_policy()
_, CHUNKS = load_corpus(Path('/knowledge'))


def request_for(sections, conditions, routes=None):
    chunks = [c for c in CHUNKS if (c.document.key, c.section) in sections]
    evidence = [dict(documentId=str(c.document.id), chunkId=str(c.id), documentType=c.document.document_type,
                     section=c.section, contentSnippet=c.content, score=1.0) for c in chunks]
    confirmed = []
    for text in conditions:
        chunk = next(c for c in chunks if text in c.content)
        confirmed.append({'text': text, 'chunkId': str(chunk.id)})
    apis = [{'api': route, 'chunkId': str(c.id)} for c in chunks for route in c.related_apis if routes is None or route in routes]
    rid = str(uuid4())
    analysis = dict(requirementId=rid, confirmedConditions=confirmed, evidence=evidence, relatedApis=apis,
                    relatedBusinessRules=confirmed, missingConditions=[], ambiguousExpressions=[], clarificationQuestions=[])
    return GenerationRequest(requirementId=rid, title='합성 정책 검증', description='공개 합성 규칙과 API 명세 검증', analysis=analysis)


def generate(request):
    candidates, _ = compile_candidates(request, POLICY)
    model = Mock()
    model.generate.return_value = json.dumps({'candidateIds': list(candidates)})
    return TestCaseGenerator(model, POLICY, HASH).generate(request), model


class PolicyExtensionTests(unittest.TestCase):
    def returns(self):
        return request_for({('return-rules', '반납 접수와 검사 대기')}, [
            '현재 대여자 또는 자산 담당자만 반납 접수를 할 수 있다.',
            '반납 접수만으로 재고를 AVAILABLE로 변경하지 않는다.',
            '반납 건은 INSPECTION_PENDING으로 생성되고 자산은 검사 완료 전까지 새로운 대여에서 제외한다.',
            '본체, 충전기, 부속품의 반납 여부를 기록하며 접수일과 담당자를 보관한다.'])

    def test_return_normal_duplicate_authorization_and_pending_are_grounded(self):
        request = self.returns()
        candidates, _ = compile_candidates(request, POLICY)
        self.assertEqual(set(candidates), {'return-normal', 'return-duplicate', 'return-authorization', 'return-inspection-pending'})
        result, model = generate(request)
        self.assertEqual(len(result.testCases), 4)
        self.assertEqual(result.llmCalls, 1)
        self.assertTrue(all(not case.executable for case in result.testCases))
        canonical = {str(c.id): c for c in CHUNKS}
        for case in result.testCases:
            for ref in case.evidence:
                self.assertEqual(str(canonical[ref.chunkId].document.id), ref.documentId)
            self.assertTrue(any(case.expectedResult.description in canonical[ref.chunkId].content for ref in case.evidence))
        model.generate.assert_called_once()

    def test_inspection_requires_its_own_confirmed_condition(self):
        request = request_for({('return-rules', '파손 장비의 수리 전환')}, [
            '이상 없는 장비는 검사 결과 PASSED와 함께 AVAILABLE로 전환한다.',
            '파손 또는 기능 이상이 있으면 검사 결과를 DAMAGED로 기록하고 자산 상태를 MAINTENANCE로 바꾼다.',
            '사진과 파손 설명은 필수이며 정상 재고로 바로 돌릴 수 없다.'])
        result, _ = generate(request)
        self.assertEqual(len(result.testCases), 3)
        self.assertTrue(all(not case.executable for case in result.testCases))
        self.assertFalse(any(key.startswith('inspection') for key in compile_candidates(self.returns(), POLICY)[0]))

    def test_catalog_requires_a_route_referenced_by_saved_analysis(self):
        request = self.returns()
        request.analysis.relatedApis = []
        result, model = generate(request)
        self.assertEqual(result.testCases, [])
        model.generate.assert_not_called()

    def test_unknown_business_condition_is_never_replaced_by_another_anchor(self):
        request = self.returns()
        request.analysis.confirmedConditions = request.analysis.confirmedConditions[-1:]
        result, model = generate(request)
        self.assertEqual(result.testCases, [])
        model.generate.assert_not_called()

    def test_forged_or_duplicate_evidence_id_fails(self):
        for mutate in [lambda e: e.append(deepcopy(e[0])), lambda e: e[0].update(chunkId='forged')]:
            body = self.returns().model_dump()
            mutate(body['analysis']['evidence'])
            with self.assertRaises(ValueError):
                compile_candidates(GenerationRequest.model_validate(body), POLICY)

    def test_missing_business_evidence_cannot_be_supplied_by_api_adapter(self):
        request = self.returns()
        request.analysis.evidence = []
        with self.assertRaises(ValueError):
            compile_candidates(request, POLICY)

    def test_duplicate_template_id_rejected_at_load(self):
        policy = deepcopy(POLICY)
        policy['plans'].append(deepcopy(policy['plans'][0]))
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            validate_policy(policy)

    def test_fake_endpoint_and_expected_result_rejected_at_load(self):
        for field in ['endpoint', 'expected']:
            policy = deepcopy(POLICY)
            plan = policy['plans'][5]
            if field == 'endpoint':
                plan['case']['input']['endpoint'] = '/admin/erase'
            else:
                plan['case']['expectedResult']['description'] = '모든 자산을 자동 승인한다.'
            with self.assertRaises(ValueError):
                validate_policy(policy)

    def test_modified_catalog_document_or_chunk_rejected(self):
        for field in ['documentId', 'chunkId', 'contentSnippet']:
            policy = deepcopy(POLICY)
            policy['apiEvidence'][0][field] = str(uuid4())
            with self.assertRaises(ValueError):
                validate_policy(policy)

    def test_pending_clarification_blocks_without_model(self):
        request = self.returns()
        request.analysis.clarificationQuestions = ['반납 이력 일관성의 판정 기준은?']
        result, model = generate(request)
        self.assertEqual(result.testCases, [])
        self.assertTrue(result.clarificationRequired)
        model.generate.assert_not_called()

    def test_existing_approval_plans_remain_exactly_five(self):
        self.assertEqual([p['id'] for p in POLICY['plans'][:5]], [
            'approval-normal', 'approval-self', 'approval-employee', 'approval-department-boundary', 'approval-no-mutation'])

    def test_schema_refuses_ground_truth_input(self):
        request = self.returns().model_dump()
        request['groundTruth'] = {'anything': 'secret'}
        with self.assertRaises(ValueError):
            GenerationRequest.model_validate(request)
