"""Opt-in extension. Does not save/replace Phase 3 analysis or change its default route."""
import json
from uuid import UUID
import httpx
from fastapi import APIRouter,HTTPException,Depends
from pydantic import BaseModel,ConfigDict
from app.analysis_models import AnalysisRequest
from app.analysis_service import AnalysisService,InvalidAnalysisError
from app.analysis_api import slot
from app.llm_provider import LocalLlmProvider,LlmUnavailableError
from app.vector_search import SearchHit

router=APIRouter()
class Request(BaseModel):
    model_config=ConfigDict(extra='forbid')
    requirementId:UUID

class ContextSearch:
    def __init__(self,hits):self.hits=hits
    def search(self,request):return self.hits

class ContextLlm:
    def __init__(self,llm,relations):self.llm,self.relations=llm,relations
    def summary_provider(self):return self.llm
    def generate(self,messages,schema):
        messages=[dict(m) for m in messages]
        data=json.loads(messages[1]['content'])
        data['relationshipContext']={'relations':self.relations,'policy':'Object provenance only; select facts only from evidenceSentences and apiCatalog. No new facts from graph edges.'}
        messages[1]['content']=json.dumps(data,ensure_ascii=False)
        return self.llm.generate(messages,schema)

def analyze_context(context,llm):
    hits=[SearchHit(**{**h,'score':h['fusionScore']}) for h in context['textEvidence']]
    req=context['requirement']
    request=AnalysisRequest(requirementId=req['id'],title=req['title'],description=req['description'])
    result=AnalysisService(ContextSearch(hits),ContextLlm(llm,context['analysisRelations'])).analyze(request)
    return {'analysis':result.model_dump(),'graphStatus':context['graphStatus'],'persisted':False,'retrievalStrategy':'HYBRID'}

def get_llm():return LocalLlmProvider()

@router.post('/internal/v1/graph-assisted-analysis')
def analyze(body:Request,llm=Depends(get_llm)):
    if not slot.acquire(blocking=False):raise HTTPException(429,detail={'code':'ANALYSIS_BUSY'})
    try:
        with httpx.Client(timeout=30,trust_env=False,follow_redirects=False) as http:
            r=http.post('http://graph-service:8030/api/graph/analysis-context',json={'requirementId':str(body.requirementId)})
            r.raise_for_status();context=r.json()
        return analyze_context(context,llm)
    except httpx.HTTPError:raise HTTPException(503,detail={'code':'GRAPH_CONTEXT_UNAVAILABLE'}) from None
    except InvalidAnalysisError:raise HTTPException(502,detail={'code':'INVALID_ANALYSIS_OUTPUT'}) from None
    except LlmUnavailableError:raise HTTPException(503,detail={'code':'ANALYSIS_MODEL_UNAVAILABLE'}) from None
    finally:slot.release()
