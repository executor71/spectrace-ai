import unittest,math
from unittest.mock import patch
from fastapi.testclient import TestClient
from retrieval.lexical import BM25,rrf,KoreanTokenizer
from retrieval.api import app,engine
from retrieval.core import SearchEngine,RerankerUnavailable,normalize

def row(cid,text='text',**kwargs):return {'chunkId':cid,'documentId':'doc-'+cid,'documentType':'API_SPEC','section':cid,'contentSnippet':text,**kwargs}
class LexicalTests(unittest.TestCase):
    def test_exact_error_code(self):
        tokenizer=KoreanTokenizer();terms=tokenizer('SELF_APPROVAL_FORBIDDEN 자기 신청을 승인합니다.')
        self.assertIn('self_approval_forbidden',terms);self.assertIn('승인',terms)
    def test_korean_inflections(self):
        tokenizer=KoreanTokenizer();self.assertTrue(set(tokenizer('장비를 반납했습니다.'))&set(tokenizer('반납하는 장비')))
    def test_bm25_exact(self):
        bm=BM25([row('a','error error'),row('b','other')],str.split)
        result=bm.search('error',5);self.assertEqual([r['chunkId'] for r in result],['a']);self.assertGreater(result[0]['lexicalScore'],0)
    def test_bm25_math(self):
        bm=BM25([row('a','term'),row('b','else')],str.split)
        self.assertAlmostEqual(bm.search('term',5)[0]['lexicalScore'],math.log(2))
    def test_empty_corpus(self):self.assertEqual(BM25([],str.split).search('query',5),[])
    def test_no_match(self):self.assertEqual(BM25([row('a')],str.split).search('missing',5),[])
    def test_tie_is_deterministic(self):self.assertEqual([r['chunkId'] for r in BM25([row('b'),row('a')],str.split).search('text',5)],['a','b'])
    def test_invalid_settings(self):
        for k,b in [(0,.75),(1,-1),(1,2)]:
            with self.assertRaises(ValueError):BM25([],str.split,k,b)
class FusionTests(unittest.TestCase):
    def test_rrf_formula(self):
        result=rrf([row('a',vectorScore=100),row('b',vectorScore=1)],[row('b',lexicalScore=99)],60)
        self.assertEqual(result[0]['chunkId'],'b');self.assertAlmostEqual(result[0]['fusionScore'],1/62+1/61)
    def test_scores_not_added(self):
        a=rrf([row('a',vectorScore=.1)],[row('b',lexicalScore=999999)],60)
        self.assertEqual(a[0]['fusionScore'],a[1]['fusionScore'])
    def test_union_empty_and_single_branch(self):
        self.assertEqual(rrf([],[]),[]);self.assertEqual(len(rrf([row('a',vectorScore=1)],[])),1)
    def test_duplicate_rejected(self):
        with self.assertRaises(ValueError):rrf([row('a',vectorScore=1)]*2,[])
    def test_invalid_rrf(self):
        with self.assertRaises(ValueError):rrf([],[],0)
class ApiTests(unittest.TestCase):
    def setUp(self):self.client=TestClient(app)
    def test_malformed_id(self):self.assertEqual(self.client.post('/internal/v1/retrieval',json={'queryId':'../../secret','queryText':'test','strategy':'VECTOR'}).status_code,422)
    def test_empty_query(self):self.assertEqual(self.client.post('/internal/v1/retrieval',json={'queryId':'q','queryText':' ','strategy':'VECTOR'}).status_code,422)
    def test_extra_ground_truth_rejected(self):self.assertEqual(self.client.post('/internal/v1/retrieval',json={'queryId':'q','queryText':'x','strategy':'VECTOR','relevantChunkIds':[]}).status_code,422)
    def test_reranker_failure_no_silent_fallback(self):
        with patch('retrieval.api.engine') as factory:
            factory.return_value.search.side_effect=RerankerUnavailable()
            response=self.client.post('/internal/v1/retrieval',json={'queryId':'q','queryText':'x','strategy':'HYBRID_RERANK'})
        self.assertEqual(response.status_code,503);self.assertEqual(response.json()['detail'],{'code':'RERANKER_UNAVAILABLE','fallback':None})
    def test_empty_result_schema(self):
        with patch('retrieval.api.engine') as factory:
            factory.return_value.search.return_value={'queryId':'q','strategy':'LEXICAL','results':[],'latencyMs':0}
            self.assertEqual(self.client.post('/internal/v1/retrieval',json={'queryId':'q','queryText':'x','strategy':'LEXICAL'}).json()['results'],[])
    def test_score_nulls(self):
        value=normalize(row('a'));self.assertTrue(all(value[k] is None for k in ['vectorScore','lexicalScore','fusionScore','rerankScore']))
if __name__=='__main__':unittest.main()
