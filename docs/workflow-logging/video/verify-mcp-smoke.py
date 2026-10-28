"""Read-only standard MCP call against the final deployed gateway."""
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

OUT=Path('/evidence')


async def main():
    state=json.loads((OUT/'real-results.json').read_text())
    report={'since':datetime.now(timezone.utc).isoformat(),'realModelCalls':0,'tool':'get_test_cases'}
    async with streamablehttp_client('http://mcp-server:8020/mcp') as (read,write,_):
        async with ClientSession(read,write) as session:
            await session.initialize()
            result=await session.call_tool('get_test_cases',{'requirementId':state['generation']['requirementId']})
            assert not result.isError
            report['count']=len(result.structuredContent['testCases'])
            assert report['count']==state['generation']['testCases']
    report['result']='PASS'
    (OUT/'mcp-final-smoke.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(report))


asyncio.run(main())
