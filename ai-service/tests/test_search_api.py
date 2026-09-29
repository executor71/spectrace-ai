import unittest
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.search_api import get_search, router
from app.vector_search import CorpusNotReadyError


class SearchApiTests(unittest.TestCase):
    def setUp(self):
        app=FastAPI()
        app.include_router(router)
        self.engine=MagicMock()
        self.engine.search.return_value=[dict(documentId='doc',chunkId='chunk',documentType='BUSINESS_RULE',
            section='section',contentSnippet='content',score=0.5,domain='IT_ASSET',version='1',relatedApis=[])]
        app.dependency_overrides[get_search]=lambda:self.engine
        self.client=TestClient(app)

    def test_response_contract(self):
        response=self.client.post('/internal/v1/search',json={'query':'test','topK':5})
        self.assertEqual(200,response.status_code)
        self.assertTrue({'documentId','chunkId','documentType','section','contentSnippet','score'} <= set(response.json()[0]))

    def test_invalid_query_and_evaluation_override_rejected(self):
        for body in [{'query':' '},{'query':'x','topK':11},{'query':'x','schema':'evaluation'}]:
            with self.subTest(body=body):
                self.assertEqual(422,self.client.post('/internal/v1/search',json=body).status_code)
        self.engine.search.assert_not_called()

    def test_mismatched_profile_is_unavailable(self):
        self.engine.search.side_effect=CorpusNotReadyError('internal profile')
        response=self.client.post('/internal/v1/search',json={'query':'test'})
        self.assertEqual(503,response.status_code)
        self.assertEqual('CORPUS_NOT_READY',response.json()['detail']['code'])

    def test_database_details_not_leaked(self):
        self.engine.search.side_effect=RuntimeError('private-database-host')
        response=self.client.post('/internal/v1/search',json={'query':'test'})
        self.assertEqual(503,response.status_code)
        self.assertNotIn('private-database-host',response.text)
