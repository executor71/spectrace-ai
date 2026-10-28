import io,json,sys,unittest
from pathlib import Path
from unittest.mock import Mock,patch
sys.path.insert(0,'/app/tests')
from app.main import app
from workflow_otel import trace,span,attrs,record_usage,propagator,inject,wrap
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from test_analysis import AnalysisTests,REQUEST,HIT,draft
from test_test_case_generation import TestCaseGenerationTest
from app.llm_provider import LocalLlmProvider,LlmUnavailableError
from app.analysis_service import AnalysisService,InvalidAnalysisError

exporter=InMemorySpanExporter()
trace.get_tracer_provider().add_span_processor(SimpleSpanProcessor(exporter))
records=[]

class ObservabilityTests(unittest.TestCase):
    def setUp(self):exporter.clear()
    def spans(self):return exporter.get_finished_spans()
    def root(self,name):return span(name,{'synthetic':True})
    def save(self,name,root):records.append({'case':name,'traceId':format(root.get_span_context().trace_id,'032x'),'synthetic':True})

    def test_timeout_failure_has_safe_code(self):
        with self.root('fixture.llm_timeout') as root:
            with patch('app.llm_provider.urlopen',side_effect=TimeoutError('SECRET_TIMEOUT_INPUT')):
                with self.assertRaises(LlmUnavailableError):LocalLlmProvider().generate([{'content':'SECRET_PROMPT'}],{})
        values=[dict(s.attributes) for s in self.spans() if s.name=='llm.generate']
        self.assertEqual(values[0]['error.code'],'LLM_TIMEOUT');self.assertNotIn('SECRET',json.dumps(values))
        self.save('LLM_TIMEOUT',root)

    def test_invalid_model_output_records_retry_without_reasoning(self):
        search=Mock();search.search.return_value=[HIT]
        def response(*args,**kwargs):return io.StringIO(json.dumps({'done':True,'message':{'content':'{}','thinking':'SECRET_REASONING'},'prompt_eval_count':7,'eval_count':2}))
        with self.root('fixture.llm_invalid') as root:
            with patch('app.llm_provider.urlopen',side_effect=response):
                with self.assertRaises(InvalidAnalysisError):AnalysisService(search,LocalLlmProvider()).analyze(REQUEST)
        llm=[s for s in self.spans() if s.name=='llm.generate']
        self.assertEqual([s.attributes['retryCount'] for s in llm],[0,1])
        self.assertTrue(any(s.attributes.get('error.code')=='LLM_INVALID_OUTPUT' for s in self.spans()))
        self.assertNotIn('SECRET_REASONING',str([(s.attributes,s.events) for s in self.spans()]))
        self.save('LLM_INVALID_OUTPUT',root)

    def test_provider_tokens_are_actual_counts(self):
        with self.root('fixture.usage') as root:
            record_usage({'prompt_eval_count':11,'eval_count':3,'message':{'thinking':'SECRET'}})
        current=self.spans()[0]
        self.assertEqual(current.attributes['totalTokens'],14)
        self.assertNotIn('SECRET',str(current.attributes))

    def test_missing_usage_is_not_estimated(self):
        with self.root('fixture.usage_absent'):record_usage({'message':{'content':'many words'}})
        self.assertFalse(any('Tokens' in k for k in self.spans()[0].attributes))

    def test_sensitive_attributes_and_invalid_identifiers_are_rejected(self):
        with self.root('fixture.sensitive') as current:
            attrs(current,{'prompt':'SECRET','groundTruth':'SECRET','contentSnippet':'SECRET','Authorization':'SECRET','db.password':'SECRET','requirementId':'SECRET','inputLength':6})
        self.assertNotIn('SECRET',str(self.spans()[0].attributes))
        self.assertEqual(self.spans()[0].attributes['inputLength'],6)

    def test_exception_text_and_stack_are_not_recorded(self):
        with self.assertRaises(ValueError):
            with self.root('fixture.exception'):raise ValueError('SECRET_EXCEPTION')
        self.assertEqual(self.spans()[0].events,())
        self.assertNotIn('SECRET',str(self.spans()[0].attributes))

    def test_w3c_parent_and_tracestate_preserved(self):
        carrier={'traceparent':'00-1234567890abcdef1234567890abcdef-1234567890abcdef-01','tracestate':'test=sample'}
        with span('fixture.propagation',context=propagator.extract(carrier)) as current:
            headers={};inject(headers)
            self.assertEqual(headers['tracestate'],'test=sample')
            self.assertEqual(current.get_span_context().trace_id,int('1234567890abcdef1234567890abcdef',16))
        self.assertEqual(self.spans()[0].parent.span_id,int('1234567890abcdef',16))

    def test_metadata_failure_does_not_change_business_result(self):
        class Business:
            def run(self):return {'result':'unchanged'}
        def broken(*args,**kwargs):raise RuntimeError('Telemetry only')
        wrap(Business,'run','fixture.safe',broken,broken)
        self.assertEqual(Business().run(),{'result':'unchanged'})

    def test_testcase_generation_counts_without_real_model(self):
        helper=TestCaseGenerationTest();generator,model=helper.generator()
        with self.root('fixture.testcase_generation') as root:result=generator.generate(helper.request())
        current=next(s for s in self.spans() if s.name=='testcase.generate')
        self.assertEqual(current.attributes['generatedTestCaseCount'],len(result.testCases))
        self.assertEqual(current.attributes['evidenceCount'],sum(len(c.evidence) for c in result.testCases))
        model.generate.assert_called_once();self.save('TESTCASE_GENERATION_MOCK',root)

    def test_static_validation_wrapper_preserves_class_and_instance_binding(self):
        class Validator:
            @staticmethod
            def validate(value):return value
        wrap(Validator,'validate','fixture.static_validation')
        value={'unchanged':True}
        self.assertIs(value,Validator.validate(value))
        self.assertIs(value,Validator().validate(value))
        self.assertIsInstance(__import__('inspect').getattr_static(Validator,'validate'),staticmethod)

    def test_actual_validation_span_has_only_safe_metadata(self):
        helper=AnalysisTests();service=helper.service([draft()])
        with self.root('fixture.validation'):result=service.analyze(REQUEST)
        current=next(s for s in self.spans() if s.name=='analysis.validation')
        self.assertTrue(current.attributes['success'])
        self.assertEqual(current.attributes['requirementId'],result.requirementId)
        self.assertEqual(current.attributes['evidenceCount'],len(result.evidence))
        self.assertNotIn(HIT.contentSnippet,str(current.attributes))
        self.assertEqual(1,service.llm.generate.call_count)

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(ObservabilityTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    trace.get_tracer_provider().force_flush()
    Path('/evidence/mock-trace-ids.json').write_text(json.dumps(records,indent=2))
    Path('/evidence/observability-unit-results.json').write_text(json.dumps({'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'realModelCalls':0},indent=2))
    sys.exit(not result.wasSuccessful())
