"""Run in the AI image with a fake provider; never invokes Qwen."""
import json,unittest
from unittest.mock import patch,MagicMock
from fastapi.testclient import TestClient
from pathlib import Path
from app.graph_analysis_api import analyze_context
from app.analysis_service import InvalidAnalysisError,SYSTEM
class Llm:
    def __init__(self,invalid=False):self.invalid=invalid;self.calls=0
    def generate(self,messages,schema):
        self.calls+=1
        assert messages[0]['content']==SYSTEM
        payload=json.loads(messages[1]['content']);assert payload['relationshipContext']['relations']
        selected=schema['properties']['relatedBusinessRuleIds']['items']['enum'][0]
        return json.dumps({'evidenceSufficiency':'SUFFICIENT','confirmedConditionIds':['FORGED' if self.invalid else selected],
            'relatedBusinessRuleIds':[selected],'relatedApiIds':[],'ambiguousExpressions':[],'missingConditions':[],'clarificationQuestions':[]})
class GraphAnalysisTests(unittest.TestCase):
    def test_opt_in_http_route_does_not_persist(self):
        from app.main import app
        from app.graph_analysis_api import get_llm
        context=json.loads(Path('/evidence/analysis-context.json').read_text());llm=Llm()
        app.dependency_overrides[get_llm]=lambda:llm
        try:
            client=TestClient(app)
            response=MagicMock();response.json.return_value=context
            with patch('app.graph_analysis_api.httpx.Client') as http:
                http.return_value.__enter__.return_value.post.return_value=response
                result=client.post('/internal/v1/graph-assisted-analysis',json={'requirementId':context['requirement']['id']})
            self.assertEqual(200,result.status_code);self.assertFalse(result.json()['persisted']);self.assertEqual(1,llm.calls)
        finally:app.dependency_overrides.clear()
    def test_opt_in_rejects_caller_graph_context(self):
        from app.main import app
        from app.graph_analysis_api import get_llm
        app.dependency_overrides[get_llm]=lambda:Llm()
        try:
            response=TestClient(app).post('/internal/v1/graph-assisted-analysis',json={'requirementId':'b5270f71-c92c-48ae-8530-8946f1cfce62','graphContext':{'fake':'fact'}})
            self.assertEqual(422,response.status_code)
        finally:app.dependency_overrides.clear()
    def test_graph_context_reaches_unchanged_grounding_validator(self):
        context=json.loads(Path('/evidence/analysis-context.json').read_text());llm=Llm()
        result=analyze_context(context,llm)
        self.assertFalse(result['persisted']);self.assertEqual(1,llm.calls)
        self.assertEqual([h['chunkId'] for h in context['textEvidence']],[e['chunkId'] for e in result['analysis']['evidence']])
    def test_graph_cannot_create_ungrounded_fact(self):
        context=json.loads(Path('/evidence/analysis-context.json').read_text());llm=Llm(True)
        with self.assertRaises(InvalidAnalysisError):analyze_context(context,llm)
        self.assertEqual(2,llm.calls)
if __name__=='__main__':unittest.main()
