from fastapi import FastAPI,HTTPException
from workflow_otel import setup,TraceMiddleware,httpx_propagation
from .store import Store
from .queries import traverse,EntityMissing,TooManyPaths
from pydantic import BaseModel,ConfigDict
from uuid import UUID
from neo4j.exceptions import Neo4jError,DriverError
from contextlib import asynccontextmanager
from threading import Thread
from .refresh import Refresher
setup('legacy-assistant-graph');httpx_propagation()
@asynccontextmanager
async def lifespan(app):
    worker=Thread(target=refresher.run,daemon=True)
    worker.start()
    yield
    refresher.stopped.set()
    worker.join(timeout=2)
app=FastAPI(title='Graph extension',docs_url=None,redoc_url=None,openapi_url=None,lifespan=lifespan)
app.add_middleware(TraceMiddleware)
store=Store()
refresher=Refresher(store)
@app.get('/health')
def health():
    try:store.read('RETURN 1 AS ok');return {'status':'UP'}
    except Exception:raise HTTPException(503,detail={'errorCode':'GRAPH_UNAVAILABLE'}) from None

class RequirementInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    requirementId:UUID
class RuleInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    businessRuleId:UUID
class TestInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    testCaseId:UUID

def query(tool,identifier):
    try:return traverse(store,tool,str(identifier))
    except EntityMissing:raise HTTPException(404,detail={'errorCode':'GRAPH_ENTITY_NOT_FOUND'}) from None
    except TooManyPaths:raise HTTPException(413,detail={'errorCode':'GRAPH_RESULT_LIMIT'}) from None
    except (Neo4jError,DriverError,OSError,ValueError):raise HTTPException(503,detail={'errorCode':'GRAPH_UNAVAILABLE'}) from None

@app.post('/api/graph/find_requirement_context')
def requirement(body:RequirementInput):
    rid=str(body.requirementId)
    state=refresher.states.get(rid,'PENDING')
    try:
        result=query('find_requirement_context',rid)
        result['syncStatus']=state
        result['dataStatus']='EMPTY' if not result['edgeCount'] else ('READY' if all(result[k] for k in ('relatedBusinessRules','relatedApis','relatedTestCases','executions')) else 'PARTIAL')
        return result
    except HTTPException as error:
        if error.status_code==404:
            if rid not in refresher.states:
                import httpx
                try:
                    response=httpx.get('http://backend:8080/api/requirements/'+rid,timeout=5,trust_env=False)
                    if response.status_code==404:raise error
                    response.raise_for_status()
                except httpx.HTTPError:
                    raise HTTPException(503,detail={'errorCode':'GRAPH_SYNC_FAILED'}) from None
            error.detail={'errorCode':'GRAPH_SYNC_FAILED' if state=='FAILED' else 'GRAPH_SYNC_PENDING'}
        raise
@app.post('/api/graph/find_impacted_tests')
def impacted(body:RuleInput):return query('find_impacted_tests',body.businessRuleId)
@app.post('/api/graph/trace_test_case_origin')
def origin(body:TestInput):return query('trace_test_case_origin',body.testCaseId)

@app.post('/api/graph/analysis-context')
def analysis_context(body:RequirementInput):
    from .context import assemble
    import httpx
    try:return assemble(store,str(body.requirementId))
    except httpx.HTTPStatusError as e:
        raise HTTPException(e.response.status_code if e.response.status_code in (404,422) else 503,detail={'errorCode':'TEXT_CONTEXT_UNAVAILABLE'}) from None
    except httpx.HTTPError:raise HTTPException(503,detail={'errorCode':'TEXT_CONTEXT_UNAVAILABLE'}) from None
