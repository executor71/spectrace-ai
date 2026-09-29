import io,json,unittest
from unittest.mock import patch
from app.llm_provider import LocalLlmProvider,LlmUnavailableError


class LlmProviderTests(unittest.TestCase):
    def response(self,**changes):
        data={'done':True,'done_reason':'stop','message':{'content':'{}','thinking':'private reasoning is never returned'}}
        data.update(changes)
        return io.BytesIO(json.dumps(data).encode())

    def test_thinking_does_not_use_incompatible_decoder_constraint(self):
        with patch.dict('os.environ',{'ANALYSIS_LLM_THINK':'true'}),patch('app.llm_provider.urlopen',return_value=self.response()) as call:
            self.assertEqual(LocalLlmProvider().generate([{'role':'user','content':'schema in prompt'}],{'type':'object'}),'{}')
        payload=json.loads(call.call_args.args[0].data)
        self.assertTrue(payload['think']);self.assertNotIn('format',payload)
        self.assertFalse(payload['stream'])

    def test_non_thinking_uses_json_schema_format(self):
        schema={'type':'object'}
        with patch.dict('os.environ',{'ANALYSIS_LLM_THINK':'false'}),patch('app.llm_provider.urlopen',return_value=self.response()) as call:
            LocalLlmProvider().generate([],schema)
        self.assertEqual(json.loads(call.call_args.args[0].data)['format'],schema)

    def test_truncated_generation_is_explicit_failure(self):
        with patch('app.llm_provider.urlopen',return_value=self.response(done_reason='length')):
            with self.assertRaises(LlmUnavailableError):LocalLlmProvider().generate([],{})

    def test_transport_timeout_is_explicit_failure(self):
        with patch('app.llm_provider.urlopen',side_effect=TimeoutError()):
            with self.assertRaises(LlmUnavailableError):LocalLlmProvider().generate([],{})
