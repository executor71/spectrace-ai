from . import setup,wrap,span,attrs,fail,attempt,operation,httpx_propagation,TraceMiddleware

def retrieval_components():
    from app.vector_search import VectorSearch
    from app.local_embedding import LocalEmbeddingProvider
    def search_result(current,result,*args,**kwargs):
        attrs(current,{'resultCount':len(result),'candidateCount':len(result)})
        if not result:fail(current,'RAG_NO_RESULT')
    wrap(VectorSearch,'search','rag.search',lambda self,request:{'retrieval.strategy':'VECTOR','topK':request.topK},search_result)
    wrap(LocalEmbeddingProvider,'embed_query','query.embedding',lambda self,text:{'embedding.model':self.identity.model,'inputLength':len(text),'vectorDimension':self.identity.dimensions})
    # Only the existing vector distance query is measured; statement text/params are never attributes.
    import psycopg
    original=psycopg.Cursor.execute
    if not getattr(original,'_observed',False):
        def execute(self,query,*args,**kwargs):
            if isinstance(query,str) and 'OPERATOR(public.<=>)' in query:
                with span('vector.search'):return original(self,query,*args,**kwargs)
            return original(self,query,*args,**kwargs)
        execute._observed=True;psycopg.Cursor.execute=execute

def ai(app):
    setup('legacy-assistant-ai');app.add_middleware(TraceMiddleware);retrieval_components()
    from app.analysis_service import AnalysisService
    from app.test_case_service import TestCaseGenerator
    from app.llm_provider import LocalLlmProvider
    from . import record_usage
    LocalLlmProvider._observe_usage=staticmethod(record_usage)
    import app.llm_provider as provider
    from . import inject
    original_open=provider.urlopen
    def urlopen(request,*args,**kwargs):
        headers={};inject(headers)
        for key,value in headers.items():request.add_header(key,value)
        return original_open(request,*args,**kwargs)
    provider.urlopen=urlopen
    wrap(AnalysisService,'analyze','requirement.analysis',lambda self,request:{'requirementId':request.requirementId})
    # Observe the existing evidence/schema materialization without changing its
    # static binding, arguments, return value, retries or validation decisions.
    wrap(AnalysisService,'materialize','analysis.validation',
         lambda request,draft,hits,sentences,apis:{'requirementId':request.requirementId,'evidenceCount':len(hits)},
         lambda current,result,*a,**k:attrs(current,{'success':True}))
    def generated(current,result,*args,**kwargs):
        attrs(current,{'generatedTestCaseCount':len(result.testCases),'executableCandidateCount':sum(c.executable for c in result.testCases),
            'evidenceCount':sum(len(c.evidence) for c in result.testCases)})
    wrap(TestCaseGenerator,'generate','testcase.generate',lambda self,request:{'requirementId':request.requirementId},generated)
    def llm_values(self,*args,**kwargs):
        retry=attempt.get();attempt.set(retry+1)
        return {'model':self.model,'provider':'ollama','operation':operation.get(),'retryCount':retry,'timeout':self.timeout}
    wrap(LocalLlmProvider,'generate','llm.generate',llm_values,lambda current,result,*a,**k:attrs(current,{'success':True}))

def retrieval(app):
    setup('legacy-assistant-retrieval');app.add_middleware(TraceMiddleware);retrieval_components()
    from retrieval.core import SearchEngine
    from retrieval.lexical import BM25
    from retrieval.reranker import LocalRerankerProvider
    def result(current,data,*args,**kwargs):
        attrs(current,{'candidateCount':data['candidateCount'],'resultCount':len(data['results'])})
        if not data['results']:fail(current,'RAG_NO_RESULT')
    wrap(SearchEngine,'search','rag.search',lambda self,query_id,query,strategy:{'retrieval.strategy':strategy,'topK':self.config['finalTopK']},result)
    wrap(BM25,'search','lexical.search')
    wrap(LocalRerankerProvider,'score','rerank',lambda self,query,passages:{'model':self.config['model'],'candidateCount':len(passages)})

def evaluation(app):
    setup('legacy-assistant-evaluation');app.add_middleware(TraceMiddleware);httpx_propagation()
    import app.main as module
    def result(current,value,*args,**kwargs):
        attrs(current,{'recallAt5':value['recallAt5'].get('value'),'scenarioCoverage':value['scenarioCoverage'].get('value'),
            'validityRate':value['testCaseValidity'].get('value'),'evaluatedItemCount':value['counts']['testCases']})
    wrap(module,'evaluate','evaluation',after=result)

def mcp(app):
    setup('legacy-assistant-mcp');app.add_middleware(TraceMiddleware);httpx_propagation()
