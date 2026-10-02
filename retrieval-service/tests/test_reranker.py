import unittest
from unittest.mock import Mock
from retrieval.reranker import LocalRerankerProvider
from retrieval.core import SearchEngine,RerankerUnavailable
from retrieval.lexical import BM25
class RerankerTests(unittest.TestCase):
    def config(self):return {'provider':'local_transformers','model':'test/model','revision':'pinned','device':'cpu','batchSize':4,'maxLength':512,'cpuThreads':4,'cacheDir':'/tmp/models'}
    def engine(self,provider):
        engine=object.__new__(SearchEngine);engine.config={'finalTopK':5,'retrievalCandidateK':20,'rrfK':60};engine.corpus_hash='hash';engine.reranker=provider;engine.initialization_ms=0
        engine.rows=[{'chunkId':str(i),'documentId':'d','documentType':'API_SPEC','section':str(i),'contentSnippet':'text','vectorScore':1-i*.01} for i in range(27)]
        engine.vector_search=lambda q,k:engine.rows[:k];engine.lexical=BM25(engine.rows,str.split);return engine
    def test_empty_does_not_load(self):
        provider=LocalRerankerProvider(self.config());provider.load=Mock();self.assertEqual(provider.score('q',[]),[]);provider.load.assert_not_called()
    def test_model_is_configured(self):
        config=self.config();provider=LocalRerankerProvider(config);self.assertEqual(provider.config['model'],'test/model')
    def test_invalid_provider(self):
        config=self.config();config['provider']='remote'
        with self.assertRaises(ValueError):LocalRerankerProvider(config)
    def test_only_top_twenty_passed_to_model(self):
        provider=Mock();provider.load_ms=0;provider.score.return_value=list(range(20));result=self.engine(provider).search('q','text','HYBRID_RERANK')
        self.assertEqual(len(provider.score.call_args.args[1]),20);self.assertEqual(len(result['results']),5);self.assertEqual(result['results'][0]['rerankScore'],19)
    def test_bad_score_count_is_error(self):
        provider=Mock();provider.score.return_value=[1]
        with self.assertRaises(RerankerUnavailable):self.engine(provider).search('q','text','HYBRID_RERANK')
    def test_nonfinite_scores_are_error(self):
        provider=Mock();provider.score.return_value=[float('nan')]*20
        with self.assertRaises(RerankerUnavailable):self.engine(provider).search('q','text','HYBRID_RERANK')
    def test_failure_is_error(self):
        provider=Mock();provider.score.side_effect=RuntimeError('unavailable')
        with self.assertRaises(RerankerUnavailable):self.engine(provider).search('q','text','HYBRID_RERANK')
    def test_empty_candidates(self):
        provider=Mock();provider.load_ms=0;provider.score.return_value=[];engine=self.engine(provider);engine.rows=[];engine.vector_search=lambda q,k:[];engine.lexical=BM25([],str.split)
        self.assertEqual(engine.search('q','text','HYBRID_RERANK')['results'],[])
if __name__=='__main__':unittest.main()
