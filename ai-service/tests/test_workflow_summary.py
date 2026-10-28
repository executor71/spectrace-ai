import contextlib
import io
import json
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from app import workflow_summary as summary
from app.analysis_service import AnalysisService, InvalidAnalysisError
from app.analysis_api import get_analysis_service
from app.llm_provider import LocalLlmProvider, LlmTimeoutError, LlmUnavailableError
from app.main import app
from app.test_case_service import TestCaseGenerator
import test_analysis as analysis_fixture
import test_test_case_generation as generation_fixture
import test_change_impact as impact_fixture


class SummaryTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, WORKFLOW_SUMMARY_LOG='true')
        self.env.start()
        self.output = io.StringIO()
        self.redirect = contextlib.redirect_stdout(self.output)
        self.redirect.__enter__()

    def tearDown(self):
        self.redirect.__exit__(None, None, None)
        self.env.stop()
        app.dependency_overrides.clear()

    def service(self, values=None):
        search = Mock(); search.search.return_value = [analysis_fixture.HIT]
        provider = Mock(); provider.generate.side_effect = values or [analysis_fixture.draft()]
        return AnalysisService(search, provider)

    def events(self):
        return [line.split('event=')[1].split()[0] for line in self.output.getvalue().splitlines()]

    def test_analysis_event_order_and_real_counts(self):
        result = self.service().analyze(analysis_fixture.REQUEST)
        self.assertEqual(['WORKFLOW_STARTED', 'WORKFLOW_INITIALIZED', 'RETRIEVAL_STARTED', 'RETRIEVAL_COMPLETED',
                          'PROVIDER_STARTED', 'PROVIDER_COMPLETED', 'STRUCTURED_OUTPUT_STARTED', 'STRUCTURED_OUTPUT_COMPLETED',
                          'EVIDENCE_VALIDATION_STARTED', 'EVIDENCE_VALIDATED', 'OUTPUT_VALIDATED',
                          'ANALYSIS_COMPLETED', 'WORKFLOW_COMPLETED'], self.events())
        text = self.output.getvalue()
        self.assertIn(f'conditions={len(result.confirmedConditions)}', text)
        self.assertIn('provider=FAKE_PROVIDER', text)
        self.assertIn('persistence=NOT_SAVED', text)
        self.assertNotIn('RESULT_SAVED', text)
        self.assertNotIn(analysis_fixture.REQUEST.description, text)

    def test_off_by_default(self):
        with patch.dict(os.environ, WORKFLOW_SUMMARY_LOG='false'):
            self.service().analyze(analysis_fixture.REQUEST)
        self.assertEqual('', self.output.getvalue())

    def test_retry_logged_per_actual_provider_call(self):
        service = self.service(['{}', analysis_fixture.draft()])
        service.analyze(analysis_fixture.REQUEST)
        self.assertEqual(2, self.events().count('PROVIDER_STARTED'))
        self.assertEqual(service.llm.generate.call_count, self.events().count('PROVIDER_COMPLETED'))
        self.assertEqual(1, self.events().count('OUTPUT_VALIDATED'))
        self.assertIn('attempt=2', self.output.getvalue())

    def test_final_invalid_output_has_failure_without_success(self):
        with self.assertRaises(InvalidAnalysisError):
            self.service(['private raw output', '{}']).analyze(analysis_fixture.REQUEST)
        self.assertEqual('WORKFLOW_FAILED', self.events()[-1])
        self.assertNotIn('WORKFLOW_COMPLETED', self.events())
        self.assertIn('stage=STRUCTURED_OUTPUT', self.output.getvalue())
        self.assertIn('errorCode=INVALID_OUTPUT', self.output.getvalue())
        self.assertNotIn('private raw output', self.output.getvalue())

    def test_timeout_has_no_llm_completed_and_no_secret(self):
        with self.assertRaises(LlmTimeoutError):
            self.service([LlmTimeoutError('secret prompt/credential')]).analyze(analysis_fixture.REQUEST)
        self.assertNotIn('LLM_COMPLETED', self.events())
        self.assertIn('errorCode=LLM_TIMEOUT', self.output.getvalue())
        self.assertIn('stage=PROVIDER', self.output.getvalue())
        self.assertIn('elapsedMs=', self.output.getvalue())
        self.assertNotIn('secret', self.output.getvalue())

    def test_retrieval_failure_has_no_llm_events(self):
        service = self.service(); service.search.search.side_effect = RuntimeError('private DB URL')
        with self.assertRaises(RuntimeError): service.analyze(analysis_fixture.REQUEST)
        self.assertNotIn('LLM_STARTED', self.events())
        self.assertIn('provider=NO_LLM_CALL', self.output.getvalue())
        self.assertIn('errorCode=RAG_RETRIEVAL_ERROR', self.output.getvalue())
        self.assertNotIn('private DB URL', self.output.getvalue())

    def test_real_provider_classification_at_transport_boundary(self):
        provider = LocalLlmProvider()
        response = Mock()
        response.__enter__ = Mock(return_value=io.StringIO(json.dumps({'done': True, 'message': {'content': analysis_fixture.draft()}})))
        response.__exit__ = Mock(return_value=False)
        service = self.service(); service.llm = provider
        with patch('app.llm_provider.urlopen', return_value=response):
            service.analyze(analysis_fixture.REQUEST)
        self.assertIn('provider=REAL_LLM', self.output.getvalue())
        self.assertEqual(1, self.events().count('LLM_STARTED'))
        self.assertEqual(1, self.events().count('LLM_COMPLETED'))

    def test_real_provider_timeout_never_claims_completed(self):
        service = self.service(); service.llm = LocalLlmProvider()
        with patch('app.llm_provider.urlopen', side_effect=TimeoutError('private prompt')):
            with self.assertRaises(LlmTimeoutError): service.analyze(analysis_fixture.REQUEST)
        self.assertEqual(1, self.events().count('LLM_STARTED'))
        self.assertNotIn('LLM_COMPLETED', self.events())
        self.assertIn('stage=LLM', self.output.getvalue())

    def test_unavailable_has_safe_error_code(self):
        with self.assertRaises(LlmUnavailableError):
            self.service([LlmUnavailableError('private host')]).analyze(analysis_fixture.REQUEST)
        self.assertIn('errorCode=LLM_UNAVAILABLE', self.output.getvalue())

    def test_generation_order_counts_and_provider_calls(self):
        fixture = generation_fixture.TestCaseGenerationTest()
        generator, provider = fixture.generator()
        result = generator.generate(fixture.request())
        self.assertEqual(['WORKFLOW_STARTED', 'WORKFLOW_INITIALIZED', 'POLICY_MATCHING_STARTED', 'EVIDENCE_VALIDATION_STARTED', 'EVIDENCE_VALIDATED',
                          'POLICY_MATCHED', 'PROVIDER_STARTED', 'PROVIDER_COMPLETED', 'STRUCTURED_OUTPUT_STARTED', 'STRUCTURED_OUTPUT_COMPLETED',
                          'TESTCASE_GENERATION_STARTED', 'TESTCASE_GENERATED',
                          'OUTPUT_VALIDATED', 'WORKFLOW_COMPLETED'], self.events())
        self.assertIn(f'testCases={len(result.testCases)}', self.output.getvalue())
        self.assertEqual(result.llmCalls, self.events().count('PROVIDER_STARTED'))
        self.assertNotIn('LLM_STARTED', self.events())
        self.assertEqual(1, provider.generate.call_count)

    def test_unsupported_policy_makes_no_provider_call_or_generated_event(self):
        fixture = generation_fixture.TestCaseGenerationTest()
        source = deepcopy(generation_fixture.SOURCE)
        source['confirmedConditions'][0]['text'] = '대여 신청은 PENDING_APPROVAL로 생성된다.'
        generator, provider = fixture.generator()
        result = generator.generate(fixture.request(source))
        self.assertEqual([], result.testCases)
        self.assertEqual(0, result.llmCalls)
        provider.generate.assert_not_called()
        self.assertNotIn('LLM_STARTED', self.events())
        self.assertNotIn('TESTCASE_GENERATED', self.events())
        self.assertIn('provider=POLICY_BLOCKED', self.output.getvalue())
        self.assertIn('0 templates matched', self.output.getvalue())

    def test_generation_timeout_is_failure(self):
        fixture = generation_fixture.TestCaseGenerationTest()
        generator, provider = fixture.generator(); provider.generate.side_effect = LlmTimeoutError('private')
        with self.assertRaises(LlmTimeoutError): generator.generate(fixture.request())
        self.assertEqual('WORKFLOW_FAILED', self.events()[-1])
        self.assertNotIn('OUTPUT_VALIDATED', self.events())

    def test_langgraph_is_fixed_and_cached_path_has_no_llm_events(self):
        req = impact_fixture.request()
        req['cachedModelChanges'] = impact_fixture.condition_diff(req, impact_fixture.provider())
        search = Mock(); search.search.return_value = []
        provider = Mock()
        result = impact_fixture.Workflow(search, provider, lambda _: impact_fixture.graph()).analyze(req)
        provider.generate.assert_not_called()
        self.assertEqual(0, result['llmCallCount'])
        self.assertNotIn('LLM_STARTED', self.events())
        self.assertNotIn('EVIDENCE_VALIDATED', self.events())
        self.assertIn('provider=CACHED_RESULT', self.output.getvalue())
        self.assertIn('Fixed LangGraph initialized: retrieve -> diff -> impact', self.output.getvalue())
        self.assertIn('mode=FIXED', self.output.getvalue())
        self.assertIn('steps=3', self.output.getvalue())
        self.assertNotIn('steps=5', self.output.getvalue())
        self.assertNotIn('event=PLANNING', self.output.getvalue())

    def test_job_trace_and_run_headers_propagate_in_worker_thread(self):
        service = self.service()
        app.dependency_overrides[get_analysis_service] = lambda: service
        rid = analysis_fixture.RID
        with TestClient(app) as client:
            response = client.post('/internal/v1/requirement-analysis', json=analysis_fixture.REQUEST.model_dump(),
                                   headers={'x-job-id': rid, 'x-workflow-run-id': rid,
                                            'traceparent': '00-1234567890abcdef1234567890abcdef-1234567890abcdef-01'})
        self.assertEqual(200, response.status_code)
        self.assertEqual(13, len(self.output.getvalue().splitlines()))
        for line in self.output.getvalue().splitlines():
            self.assertIn('jobId=' + rid, line)
            self.assertIn('runId=' + rid, line)
            self.assertIn('requirementId=' + rid, line)
            self.assertIn('traceId=1234567890abcdef1234567890abcdef', line)
        self.assertIsNone(summary.incoming.get())
        self.assertIsNone(summary.current.get())

    def test_invalid_header_cannot_inject_log_fields(self):
        app.dependency_overrides[get_analysis_service] = lambda: self.service()
        with TestClient(app) as client:
            client.post('/internal/v1/requirement-analysis', json=analysis_fixture.REQUEST.model_dump(),
                        headers={'x-job-id': 'secret', 'x-workflow-run-id': 'secret', 'traceparent': 'secret'})
        self.assertNotIn('secret', self.output.getvalue())
        self.assertIn('jobId=-', self.output.getvalue())

    def test_concurrent_runs_keep_distinct_ids_and_do_not_leak_context(self):
        def invoke(i):
            request = analysis_fixture.REQUEST.model_copy(update={'requirementId': f'{i:08d}-1111-4111-8111-111111111111'})
            self.service().analyze(request)
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(invoke, [1, 2]))
        groups = {}
        for line in self.output.getvalue().splitlines():
            fields = dict(part.split('=', 1) for part in line.split() if '=' in part)
            groups.setdefault(fields['runId'], set()).add(fields['requirementId'])
        self.assertEqual(2, len(groups))
        self.assertTrue(all(len(ids) == 1 for ids in groups.values()))
        self.assertIsNone(summary.current.get())

    def test_graph_assisted_adapter_retains_real_provider_identity(self):
        from app.graph_analysis_api import ContextLlm
        self.assertEqual('REAL_LLM', summary.provider_mode(ContextLlm(LocalLlmProvider(), [])))

    def test_video_status_sequence_and_no_early_validation_pass(self):
        self.service().analyze(analysis_fixture.REQUEST)
        lines = self.output.getvalue().splitlines()
        for index, line in enumerate(lines, 1):
            self.assertIn('stream=SUMMARY', line)
            self.assertIn(f'seq={index} ', line)
            self.assertRegex(line, r'status=(START|COMPLETE|FAILED) ')
            self.assertRegex(line, r'result=[A-Z_]+ ')
        starts = [line for line in lines if 'status=START ' in line]
        self.assertTrue(starts)
        self.assertTrue(all('evidence=PASS' not in line and 'schema=PASS' not in line for line in starts))

    def test_failed_model_call_has_paired_failed_status(self):
        service = self.service(); service.llm = LocalLlmProvider()
        with patch('app.llm_provider.urlopen', side_effect=TimeoutError('PRIVATE')):
            with self.assertRaises(LlmTimeoutError): service.analyze(analysis_fixture.REQUEST)
        self.assertIn('LLM_FAILED', self.events())
        self.assertNotIn('LLM_COMPLETED', self.events())
        self.assertNotIn('PRIVATE', self.output.getvalue())


if __name__ == '__main__':
    unittest.main()
