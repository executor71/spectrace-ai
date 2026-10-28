"""Real MCP client + actual review APIs; run inside the MCP client container.

Approvals are submitted by this validation script, not represented as human clicks.
Only the newly created synthetic validation test cases may be edited/approved.
"""
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import json
import sys
from pathlib import Path
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

OUT=Path('/evidence')
state=json.loads((OUT/'real-results.json').read_text())
generation=state['generation']
assert generation['analysisSource']=='EXISTING_GROUNDED_FIXTURE'
report={'since':datetime.now(timezone.utc).isoformat(),'client':'standard MCP ClientSession over Streamable HTTP',
        'approvalOrigin':'VALIDATION_SCRIPT_REVIEW_API','realModelCalls':0,'tools':[],'reviews':[]}


def save(): (OUT/'mcp-results.json').write_text(json.dumps(report,indent=2),encoding='utf8')


async def main():
    save()
    async with httpx.AsyncClient(base_url='http://backend:8080',trust_env=False,timeout=30) as rest:
        async def api(method,path,body=None):
            response=await rest.request(method,path,json=body) if body is not None else await rest.request(method,path)
            response.raise_for_status();return response.json()
        batch=await api('GET',f'/api/requirements/{generation["requirementId"]}/test-cases')
        cases={case['testCaseId']:case for case in batch['testCases']}
        assert all(case['requirementId']==generation['requirementId'] for case in cases.values())
        if '--repeat' in sys.argv:
            # Only our newly created validation IDs may be reset for a repeat.
            # The normal edit API resets approval and increments the real revision.
            for key in ['normalId','defectId']:
                case=cases[generation[key]]
                cases[case['testCaseId']]=await api('PATCH',f'/api/test-cases/{case["testCaseId"]}',
                                                   {'reviewRevision':case['reviewRevision'],'scenario':case['scenario']})
        async with streamablehttp_client('http://mcp-server:8020/mcp') as (read,write,_):
            async with ClientSession(read,write) as session:
                await session.initialize()
                listing=await session.list_tools();report['advertisedTools']=[tool.name for tool in listing.tools]
                async def call(name,args):
                    result=await session.call_tool(name,args)
                    value=result.structuredContent or {}
                    info={'tool':name,'isError':bool(result.isError)}
                    for field in ['result','errorCode','analysisSource','executionId']:
                        if field in value: info[field]=value[field]
                    if isinstance(value.get('hits'),list):info['count']=len(value['hits'])
                    if isinstance(value.get('testCases'),list):info['count']=len(value['testCases'])
                    report['tools'].append(info);save();print(json.dumps(info),flush=True)
                    return result,value
                result,_=await call('search_knowledge',{'query':'자기 승인 금지','topK':5});assert not result.isError
                result,value=await call('analyze_requirement',{'requirementId':state['analysis']['requirementId']})
                assert not result.isError and value['analysisSource']=='SAVED'
                result,_=await call('get_test_cases',{'requirementId':generation['requirementId']});assert not result.isError
                result,value=await call('execute_approved_test',{'testCaseId':generation['normalId']})
                assert result.isError and value['errorCode']=='NOT_APPROVED'
                for key,profile in [('normalId','standard'),('defectId','synthetic-self-approval-bug')]:
                    original=cases[generation[key]];tcid=original['testCaseId']
                    assert original['approvalStatus']=='DRAFT', 'Do not modify previously reviewed records'
                    input=deepcopy(original['input']);input['pathParameters']={'loanId':'00000000-0000-4000-8000-000000000041'}
                    input['fixtureProfile']=profile
                    actor=input['actorFixture']
                    if key=='normalId':assert actor=='same-department-manager'
                    else:assert actor=='requester'
                    preconditions=[f'합성 계정과 부서 관계를 시험 환경에 준비한다: {actor}',
                                   '합성 대여 신청의 상태는 PENDING_APPROVAL이다.','해당 자산의 상태는 AVAILABLE이다.',
                                   '상태 변경 비교를 위해 실행 전 신청 상태와 자산 상태를 기록한다.']
                    edited=await api('PATCH',f'/api/test-cases/{tcid}',{'reviewRevision':original['reviewRevision'],'input':input,'preconditions':preconditions})
                    approved=await api('POST',f'/api/test-cases/{tcid}/approve',{'reviewRevision':edited['reviewRevision'],'reviewer':'demo-validation-script'})
                    assert approved['approvalStatus']=='APPROVED'
                    eligibility=await api('GET',f'/api/test-cases/{tcid}/execution-eligibility')
                    assert eligibility['executionEligible'],eligibility['blockedReason']
                    report['reviews'].append({'testCaseId':tcid,'approvalStatus':approved['approvalStatus'],'revision':approved['reviewRevision'],
                                              'origin':'VALIDATION_SCRIPT_REVIEW_API','fixtureProfile':profile});save()
                    result,value=await call('execute_approved_test',{'testCaseId':tcid})
                    expected='PASS' if key=='normalId' else 'FAIL'
                    assert not result.isError and value['result']==expected
                    assert value['syntheticDefect']==(key=='defectId')
                    persisted=await api('GET','/api/executions/'+value['executionId'])
                    assert persisted==value
                    report[key]={'testCaseId':tcid,'executionId':value['executionId'],'result':value['result'],
                                 'mismatches':len(value['mismatches']),'syntheticDefect':value['syntheticDefect'],'persistedExactMatch':True,
                                 'expectedHttpStatus':value['expected']['httpStatus'],'actualHttpStatus':value['actual']['httpStatus']}
                    save()
    report['result']='PASS';save()


asyncio.run(main())
