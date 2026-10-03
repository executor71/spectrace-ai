import asyncio,json,time
from pathlib import Path
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from workflow_otel import setup,span,inject,trace,httpx_propagation
setup('legacy-assistant-demo');httpx_propagation()
RID='b5270f71-c92c-48ae-8530-8946f1cfce62';TC='c53be0ea-3157-49be-a922-efa378d6ca11'
dest=Path('/evidence');records=[]
def record(case,root,**extra):
    records.append({'case':case,'traceId':format(root.get_span_context().trace_id,'032x'),**extra})
    (dest/'demo-trace-ids.json').write_text(json.dumps(records,indent=2))
async def main():
 async with httpx.AsyncClient(timeout=120) as http:
    async def retrieval(strategy):
        response=await http.post('http://retrieval-service:8010/internal/v1/retrieval',json={'queryId':'phase10','queryText':'자산 대여 승인','strategy':strategy});response.raise_for_status();return response.json()
    with span('workflow.retrieval') as root:
        (await http.get('http://backend:8080/api/requirements/'+RID)).raise_for_status()
        result=await retrieval('HYBRID');assert len(result['results'])==5;record('A_HYBRID',root)
    with span('workflow.mcp') as root:
        headers={};inject(headers)
        async with streamablehttp_client('http://mcp-server:8020/mcp/',headers=headers) as (r,w,_):
          async with ClientSession(r,w) as session:
            await session.initialize();result=await session.call_tool('get_test_cases',{'requirementId':RID});assert not result.isError
        record('C_MCP',root)
    for case,identifier,expected in [('D_PASS',TC,'PASS'),('E_FAIL','4611bca5-0d0c-45dd-9793-75566c432c89','FAIL')]:
        with span('workflow.'+case.lower()) as root:
            response=await http.post(f'http://backend:8080/api/test-cases/{identifier}/executions');response.raise_for_status()
            data=response.json();assert data['result']==expected
            (dest/(case+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2));record(case,root,executionId=data['executionId'])
    for case,identifier,code in [('F_NOT_APPROVED','e35a6d9c-e7f2-4546-9f34-d597e9ae9627','NOT_APPROVED'),('F_API_NOT_ALLOWED','1f521e4c-458b-4c09-95f3-4e6d26ea112a','API_NOT_ALLOWED')]:
        with span('workflow.blocked') as root:
            response=await http.post(f'http://backend:8080/api/test-cases/{identifier}/executions')
            assert response.status_code==409 and response.json()['code']==code;record(case,root)
    with span('workflow.no_result') as root:
        response=await http.post('http://retrieval-service:8010/internal/v1/retrieval',json={'queryId':'none','queryText':'zzzznonexistentterm987654','strategy':'LEXICAL'})
        assert response.json()['results']==[];record('RAG_NO_RESULT',root)
    with span('workflow.validation') as root:
        response=await http.post('http://ai-service:8000/internal/v1/search',json={'query':'SECRET_USER_SENTINEL','topK':1000},headers={'Authorization':'Bearer SECRET_AUTH_SENTINEL'})
        assert response.status_code==422;record('VALIDATION_FAILED',root)
    with span('workflow.mcp_rejected') as root:
        headers={};inject(headers)
        async with streamablehttp_client('http://mcp-server:8020/mcp/',headers=headers) as (r,w,_):
          async with ClientSession(r,w) as session:
            await session.initialize();result=await session.call_tool('execute_approved_test',{'testCaseId':TC,'approvalStatus':'SECRET_OVERRIDE_SENTINEL'})
            assert result.isError
        record('MCP_TOOL_REJECTED',root)
    with span('workflow.evaluation') as root:
        response=await http.post('http://evaluation-service:8090/api/evaluations',json={'requirementId':RID})
        response.raise_for_status();assert response.json()['status']=='COMPLETED';record('EVALUATION',root,evaluationId=response.json()['id'])
    for strategy in ['VECTOR','HYBRID','HYBRID_RERANK']:
        # Keep cold model load separate from steady inference measurements.
        with span('workflow.warmup') as root:
            await retrieval(strategy);record('WARMUP_'+strategy,root)
        for index in range(3):
            with span('workflow.measure.'+strategy.lower()) as root:
                result=await retrieval(strategy);record('MEASURE_'+strategy,root,iteration=index,serverLatencyMs=result['latencyMs'])
    trace.get_tracer_provider().force_flush()
    print(json.dumps({'result':'PASS','traceCount':len(records),'realModelCalls':0}))
asyncio.run(main())
