import asyncio,json,time,urllib.request
from pathlib import Path
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from workflow_otel import setup,span,inject,trace,httpx_propagation
setup('legacy-assistant-demo');httpx_propagation()
async def main():
    with span('workflow.mcp') as root:
        tid=format(root.get_span_context().trace_id,'032x')
        headers={};inject(headers)
        async with streamablehttp_client('http://mcp-server:8020/mcp/',headers=headers) as (r,w,_):
            async with ClientSession(r,w) as s:
                await s.initialize()
                result=await s.call_tool('search_knowledge',{'query':'자산 대여 승인','strategy':'HYBRID'})
                assert not result.isError,result
                print('Search OK',tid,flush=True)
    trace.get_tracer_provider().force_flush()
    await asyncio.sleep(3)
    async with httpx.AsyncClient() as http:
        data=(await http.get('http://jaeger:16686/api/traces/'+tid)).json()
    Path('/evidence/context-smoke.json').write_text(json.dumps(data,ensure_ascii=False,indent=2))
    item=data['data'][0];services={p['serviceName'] for p in item['processes'].values()}
    assert {'legacy-assistant-demo','legacy-assistant-mcp','legacy-assistant-retrieval'}<=services,services
    names={s['operationName'] for s in item['spans']}
    assert {'mcp.tool','rag.search','query.embedding','vector.search','lexical.search'}<=names,names
    print('PASS',services,names)
asyncio.run(main())
