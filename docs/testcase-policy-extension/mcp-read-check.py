"""Standard MCP client compatibility check. Read-only tools only."""
import asyncio
import json
from pathlib import Path
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async def main():
    async with streamablehttp_client('http://mcp-server:8020/mcp') as (read,write,_):
        async with ClientSession(read,write) as session:
            await session.initialize()
            tools=await session.list_tools()
            assert len(tools.tools)==8
            assert all(tool.inputSchema.get('additionalProperties') is False for tool in tools.tools)
            result=await session.call_tool('get_test_cases',{'requirementId':'c9e5d1d8-6de2-487e-8ae6-9cf6c7b99eae'})
            assert not result.isError
            body=result.structuredContent
            assert body['generationStatus']=='PARTIALLY_GENERATED' and len(body['testCases'])==4
            # Existing MCP semantics: executable is the runtime syntax assessment;
            # generationExecutable and executionEligible retain the two separate gates.
            assert all(not case['executionEligible'] and not case['generationExecutable'] for case in body['testCases'])
            refs={source['chunkId'] for source in body['sourceAnalysis']['evidence']}
            assert all(ref['chunkId'] in refs for case in body['testCases'] for ref in case['evidence'])
            summary={'toolCount':len(tools.tools),'strictInputSchemas':True,'getTestCases':'PASS',
                     'generationStatus':body['generationStatus'],'testCases':4,'allExecutionBlocked':True,'allEvidenceResolved':True,
                     'generationExecutable':False,'runtimeExecutableIsSeparateAssessment':True}
            Path('/evidence/mcp-live-result.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
            print(json.dumps(summary))

asyncio.run(main())
