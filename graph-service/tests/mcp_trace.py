import asyncio,json,time
from pathlib import Path
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from workflow_otel import setup,span,inject,trace,httpx_propagation
setup('legacy-assistant-demo');httpx_propagation()
out=Path('/evidence');records=[];traces=[]
async def main():
    with span('workflow.graph-tools') as root:
        headers={};inject(headers)
        async with streamablehttp_client('http://mcp-server:8020/mcp/',headers=headers) as (r,w,_):
            async with ClientSession(r,w) as session:
                await session.initialize();tools=(await session.list_tools()).tools
                assert len(tools)==8
                for tool,args in [('find_requirement_context',{'requirementId':'80e2d374-0825-4811-a11e-03ade256b6e8'}),('find_impacted_tests',{'businessRuleId':'7cea4fe7-6b00-56c9-be35-3194aeecb923'}),('trace_test_case_origin',{'testCaseId':'4611bca5-0d0c-45dd-9793-75566c432c89'})]:
                    assert next(t for t in tools if t.name==tool).annotations.readOnlyHint
                    result=await session.call_tool(tool,args);assert not result.isError
                    assert result.structuredContent['hopCount']>=2
                    records.append({'tool':tool,'input':args,'result':result.structuredContent})
                for tool,args in [('execute_cypher',{'query':'MATCH (n) DELETE n'}),('find_impacted_tests',{'businessRuleId':"MATCH (n) RETURN n"}),('find_requirement_context',{'requirementId':'80e2d374-0825-4811-a11e-03ade256b6e8','cypher':'DELETE n'})]:
                    result=await session.call_tool(tool,args);assert result.isError
                    records.append({'tool':tool,'blocked':True,'error':result.structuredContent})
        traces.append({'case':'MCP_GRAPH_TOOLS','traceId':format(root.get_span_context().trace_id,'032x')})
    with span('workflow.graph-context') as root:
        async with httpx.AsyncClient(timeout=30) as http:
            response=await http.post('http://graph-service:8030/api/graph/analysis-context',json={'requirementId':'b5270f71-c92c-48ae-8530-8946f1cfce62'});response.raise_for_status()
        traces.append({'case':'GRAPH_CONTEXT','traceId':format(root.get_span_context().trace_id,'032x')})
    (out/'mcp-graph-tool-results.json').write_text(json.dumps(records,ensure_ascii=False,indent=2))
    (out/'graph-trace-ids.json').write_text(json.dumps(traces,indent=2))
asyncio.run(main());trace.get_tracer_provider().force_flush();print('PASS 3 graph tools, readonly hints, 3 rejected attacks, context trace')
