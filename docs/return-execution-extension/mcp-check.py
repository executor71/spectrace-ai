import asyncio
import json
from pathlib import Path
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async def main():
    async with streamablehttp_client('http://mcp-server:8020/mcp') as (read,write,_):
        async with ClientSession(read,write) as session:
            await session.initialize();tools=await session.list_tools();assert len(tools.tools)==8
            result=await session.call_tool('get_test_cases',{'requirementId':'c9e5d1d8-6de2-487e-8ae6-9cf6c7b99eae'})
            assert not result.isError;cases=result.structuredContent['testCases'];assert len(cases)==4
            assert all(case['executionEligible'] and case['fixtureReady'] for case in cases)
            blocked=await session.call_tool('execute_approved_test',{'testCaseId':cases[0]['testCaseId'],'fixtureProfile':'intentional-defect'})
            assert blocked.isError and blocked.structuredContent['errorCode']=='INVALID_ARGUMENTS'
            report={'tools':8,'readCurrentReturnCases':'PASS','approvedExecutableCases':4,'strictOverrideRejection':'PASS','newExecutions':0}
            Path('/evidence/mcp-results.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report))
asyncio.run(main())
