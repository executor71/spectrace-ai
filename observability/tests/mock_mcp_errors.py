import asyncio,json
from pathlib import Path
from unittest.mock import AsyncMock
from app import server
from app.clients import GatewayError
from app.tools import Gateway
from workflow_otel import span,trace
async def main():
    services=AsyncMock();server.gateway=Gateway(services);rows=[]
    for code in ['NOT_EXECUTABLE','FIXTURE_NOT_READY']:
        services.request.side_effect=GatewayError(code,'backend')
        with span('fixture.mcp_gate',{'synthetic':True}) as root:
            result=await server.call_tool('execute_approved_test',{'testCaseId':'c53be0ea-3157-49be-a922-efa378d6ca11'})
            assert result.isError and result.structuredContent['errorCode']==code
            rows.append({'case':code,'traceId':format(root.get_span_context().trace_id,'032x'),'synthetic':True})
    trace.get_tracer_provider().force_flush()
    Path('/evidence/mock-mcp-trace-ids.json').write_text(json.dumps(rows,indent=2));print('PASS 2 mock downstream gate traces; no DB or model calls')
asyncio.run(main())
