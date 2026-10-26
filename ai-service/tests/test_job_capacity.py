import unittest
from unittest.mock import patch,Mock
from urllib.error import URLError
from fastapi.testclient import TestClient
from app.main import app
from app.analysis_api import get_analysis_service
from app.llm_provider import LocalLlmProvider,LlmTimeoutError
class JobCapacityTests(unittest.TestCase):
 def test_capacity_read_does_not_invoke_model_or_search(self):
  with patch('app.analysis_api.slot') as slot:
   slot.acquire.return_value=False
   self.assertFalse(TestClient(app).get('/internal/v1/analysis-capacity').json()['available']);slot.release.assert_not_called()
   slot.acquire.return_value=True
   self.assertTrue(TestClient(app).get('/internal/v1/analysis-capacity').json()['available']);slot.release.assert_called_once()
 def test_timeout_is_typed_without_changing_generation_parameters(self):
  with patch('app.llm_provider.urlopen',side_effect=TimeoutError()):
   with self.assertRaises(LlmTimeoutError):LocalLlmProvider().generate([],{'type':'object'})
 def test_api_exposes_timeout_and_releases_guard(self):
  service=Mock();service.analyze.side_effect=LlmTimeoutError('safe timeout');app.dependency_overrides[get_analysis_service]=lambda:service
  try:
   r=TestClient(app).post('/internal/v1/requirement-analysis',json={'requirementId':'11111111-1111-4111-8111-111111111111','title':'합성','description':'합성'})
   self.assertEqual(504,r.status_code);self.assertEqual('LLM_TIMEOUT',r.json()['detail']['code']);self.assertTrue(TestClient(app).get('/internal/v1/analysis-capacity').json()['available'])
  finally:app.dependency_overrides.clear()
