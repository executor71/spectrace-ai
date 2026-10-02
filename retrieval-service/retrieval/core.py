from dataclasses import dataclass
from pathlib import Path
import hashlib,json,os,time
import psycopg
from app.db import rag_connection_settings
from app.local_embedding import get_embedding_provider
from app.vector_search import VectorSearch,SearchRequest
from retrieval.lexical import BM25,KoreanTokenizer,rrf

def digest(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def settings():
    value=json.loads(Path(os.getenv('RETRIEVAL_CONFIG','/retrieval/config/retrieval.json')).read_text())
    for key,env in [('rrfK','RRF_K'),('retrievalCandidateK','RETRIEVAL_CANDIDATE_K'),('finalTopK','FINAL_TOP_K')]:
        if os.getenv(env):value[key]=int(os.environ[env])
    if not 1<=value['finalTopK']<=10 or not value['finalTopK']<=value['retrievalCandidateK']<=100 or value['rrfK']<=0:raise ValueError('Invalid retrieval configuration')
    return value

def corpus_snapshot(connection_settings):
    with psycopg.connect(**connection_settings) as db:
        db.execute('SET TRANSACTION READ ONLY');db.execute("SET LOCAL statement_timeout = '5s'")
        rows=db.execute('SELECT d.id::text,d.source_key,d.document_type,d.domain,d.version,c.id::text,c.section,c.content,c.metadata,c.embedding::text FROM rag.knowledge_chunk c JOIN rag.knowledge_document d ON d.id=c.document_id ORDER BY d.source_key,c.section').fetchall()
        chunks=[dict(zip(['documentId','documentKey','documentType','domain','version','chunkId','section','content','metadata','embeddingSha256'],r[:-1]+(hashlib.sha256(r[-1].encode()).hexdigest(),))) for r in rows]
        return {'role':db.execute('SELECT current_user').fetchone()[0],'profile':list(db.execute('SELECT provider,model,revision,dimensions FROM rag.embedding_profile WHERE id=1').fetchone()),'chunks':chunks}

@dataclass(frozen=True)
class CandidateRequest:
    """Internal Top-N adapter; reuses unchanged Phase 2 VectorSearch SQL and embedding provider."""
    query:str
    topK:int

def normalize(row):
    return {**row,'vectorScore':row.get('vectorScore'),'lexicalScore':row.get('lexicalScore'),
            'fusionScore':row.get('fusionScore'),'rerankScore':row.get('rerankScore')}

class RerankerUnavailable(RuntimeError):pass

class SearchEngine:
    def __init__(self,config=None,reranker=None):
        start=time.perf_counter();self.config=config or settings();self.connection_settings=rag_connection_settings()
        self.snapshot=corpus_snapshot(self.connection_settings);self.corpus_hash=digest(self.snapshot)
        if self.corpus_hash!=self.config['expectedCorpusHash']:raise RuntimeError('CORPUS_CHANGED')
        self.rows=[{k:row[k] for k in ['documentId','chunkId','documentType','section','domain','version']}|{'contentSnippet':row['content'][:700]} for row in self.snapshot['chunks']]
        self.vector=VectorSearch(get_embedding_provider(),self.connection_settings)
        self.lexical=BM25(self.rows,KoreanTokenizer(),self.config['bm25K1'],self.config['bm25B'])
        self.reranker=reranker;self.initialization_ms=(time.perf_counter()-start)*1000

    def vector_search(self,query,k):
        request=SearchRequest(query=query,topK=k) if k<=10 else CandidateRequest(query,k)
        return [normalize({**hit.model_dump(exclude={'score'}),'vectorScore':hit.score}) for hit in self.vector.search(request)]

    def search(self,query_id,query,strategy):
        start=time.perf_counter();cfg=self.config;k=cfg['finalTopK'];candidate_k=cfg['retrievalCandidateK'];timing={}
        vectors=[];lexical=[];candidates=[]
        if strategy=='VECTOR':
            candidates=self.vector_search(query,k)
        elif strategy=='LEXICAL':
            candidates=self.lexical.search(query,candidate_k)
        elif strategy in ['HYBRID','HYBRID_RERANK']:
            t=time.perf_counter();vectors=self.vector_search(query,candidate_k);timing['vectorMs']=(time.perf_counter()-t)*1000
            t=time.perf_counter();lexical=self.lexical.search(query,candidate_k);timing['lexicalMs']=(time.perf_counter()-t)*1000
            t=time.perf_counter();candidates=rrf(vectors,lexical,cfg['rrfK'])[:candidate_k];timing['fusionMs']=(time.perf_counter()-t)*1000
            if strategy=='HYBRID_RERANK':
                if self.reranker is None:raise RerankerUnavailable('RERANKER_UNAVAILABLE')
                t=time.perf_counter()
                try:
                    scores=self.reranker.score(query,[row['contentSnippet'] for row in candidates])
                    import math
                    if len(scores)!=len(candidates) or not all(math.isfinite(s) for s in scores):raise ValueError('Invalid reranker scores')
                    candidates=[{**row,'rerankScore':float(score)} for row,score in zip(candidates,scores)]
                    candidates.sort(key=lambda row:(-row['rerankScore'],row['chunkId']))
                except Exception as error:raise RerankerUnavailable('RERANKER_UNAVAILABLE') from error
                timing['rerankerMs']=(time.perf_counter()-t)*1000
        else:raise ValueError('Unknown strategy')
        result={'queryId':query_id,'strategy':strategy,'results':[{**normalize(row),'rank':rank} for rank,row in enumerate(candidates[:k],1)],
            'latencyMs':(time.perf_counter()-start)*1000,'timing':timing,'candidateCount':len(candidates),'vectorCandidateCount':len(vectors),
            'lexicalCandidateCount':len(lexical),'corpusHash':self.corpus_hash,'configHash':digest(cfg),'finalTopK':k,
            'candidates':[{**normalize(row),'rank':rank} for rank,row in enumerate(candidates,1)],
            'vectorCandidates':vectors,'lexicalCandidates':lexical,
            'initializationMs':self.initialization_ms,'rerankerModelLoadMs':getattr(self.reranker,'load_ms',None)}
        return result
