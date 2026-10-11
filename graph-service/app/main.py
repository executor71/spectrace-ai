from fastapi import FastAPI,HTTPException
from workflow_otel import setup,TraceMiddleware,httpx_propagation
from .store import Store
from .queries import traverse,EntityMissing,TooManyPaths
from pydantic import BaseModel,ConfigDict
from uuid import UUID
from neo4j.exceptions import Neo4jError,DriverError
setup('legacy-assistant-graph');httpx_propagation()
app=FastAPI(title='Graph extension',docs_url=None,redoc_url=None,openapi_url=None)
app.add_middleware(TraceMiddleware)
store=Store()
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
def requirement(body:RequirementInput):return query('find_requirement_context',body.requirementId)
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
