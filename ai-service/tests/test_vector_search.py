import unittest
from unittest.mock import MagicMock, patch

from pydantic import ValidationError
from app.embedding_contract import EmbeddingIdentity
from app.vector_search import CorpusNotReadyError, SearchRequest, VectorSearch


class VectorSearchTests(unittest.TestCase):
    def test_query_validation_rejects_empty_and_schema_override(self):
        for request in [dict(query=' '),dict(query='x',topK=0),dict(query='x',topK=11),
                        dict(query='x',topK=True),dict(query='x'*2001),
                        dict(query='x',schema='evaluation')]:
            with self.subTest(request=request), self.assertRaises(ValidationError):
                SearchRequest(**request)
        self.assertEqual('hello',SearchRequest(query=' hello ').query)

    @patch('app.vector_search.psycopg.connect')
    def test_only_rag_is_queried_and_parameters_are_bound(self,connect):
        # Deliberately tiny test vectors test SQL plumbing, not semantic retrieval quality.
        model=MagicMock()
        model.identity=EmbeddingIdentity('unit-test-only','test-model','test-revision',2)
        model.embed_query.return_value=[1.0,0.0]
        cursor=connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value=('unit-test-only','test-model','test-revision',2)
        cursor.fetchall.return_value=[('document','chunk','BUSINESS_RULE','Section','content',0.8,'IT_ASSET','1',[])]
        hits=VectorSearch(model,{'user':'rag_reader'}).search(SearchRequest(query="'; SELECT * FROM evaluation.ground_truth; --",topK=3))
        self.assertEqual(0.8,hits[0].score)
        search_sql,params=cursor.execute.call_args.args
        self.assertIn('FROM rag.knowledge_chunk',search_sql)
        self.assertIn('JOIN rag.knowledge_document',search_sql)
        self.assertIn('OPERATOR(public.<=>)',search_sql)
        self.assertNotIn('evaluation.',search_sql)
        self.assertNotIn('app.',search_sql)
        self.assertEqual(3,params[-1])
        cursor.execute.assert_any_call('SET TRANSACTION READ ONLY')

    @patch('app.vector_search.psycopg.connect')
    def test_profile_mismatch_fails_before_embedding(self,connect):
        model=MagicMock()
        model.identity=EmbeddingIdentity('unit-test-only','new-model','r1',2)
        cursor=connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value=('unit-test-only','old-model','r1',2)
        with self.assertRaises(CorpusNotReadyError):
            VectorSearch(model,{}).search(SearchRequest(query='sample'))
        model.embed_query.assert_not_called()


if __name__=='__main__':
    unittest.main()
