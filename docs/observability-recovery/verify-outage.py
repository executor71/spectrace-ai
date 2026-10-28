"""Brief telemetry-only outage during a real Qwen job; always restore services.

Only newly created recovery cases are reviewed through the existing REST API.
These are scripted approvals, not evidence of a human clicking the UI.
"""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.request import Request, urlopen

OUT=Path(__file__).resolve().parent
report={'approvalOrigin':'VALIDATION_SCRIPT_REVIEW_API','realQwenCallsAdded':0}

def save(): (OUT/'outage-validation.json').write_text(json.dumps(report,indent=2),encoding='utf8')
def api(path,body=None,method=None):
    request=Request('http://127.0.0.1:8080'+path,data=None if body is None else json.dumps(body,ensure_ascii=False).encode(),headers={'Content-Type':'application/json'},method=method)
    with urlopen(request,timeout=20) as response:return json.load(response)
def docker(*args):return subprocess.check_output(['docker',*args],stderr=subprocess.STDOUT).decode('utf8')
def job():return api('/api/analysis-jobs/'+state['analysis']['jobId'])

state=json.loads((OUT/'real-results.json').read_text())
generation=state['generation'];analysis=state['analysis']
cases=api(f'/api/requirements/{generation["requirementId"]}/test-cases')['testCases']
case=next(c for c in cases if c['testCaseId']==generation['normalId'])
if '--retry' in sys.argv:
    previous=json.loads((OUT/'outage-validation.json').read_text())
    previous.update(result='HARNESS_REQUEST_REJECTED',errorCode='EXECUTION_INPUT_NOT_ALLOWED',reason='Execution API forbids any request body; first harness sent an empty object')
    (OUT/'outage-first-attempt.json').write_text(json.dumps(previous,indent=2))
    case=api(f'/api/test-cases/{case["testCaseId"]}',{'reviewRevision':case['reviewRevision'],'scenario':case['scenario']},'PATCH')
assert case['approvalStatus']=='DRAFT'
for _ in range(90):
    rows=docker('logs','--since',analysis['since'],'master-ai-service-1')
    selected=[line for line in rows.splitlines() if analysis['requirementId'] in line and 'event=LLM_STARTED ' in line]
    if selected:break
    time.sleep(1)
else:raise RuntimeError('No actual LLM start; do not stop telemetry')
trace_id=re.search(r'traceId=([0-9a-f]{32})',selected[0]).group(1)
assert job()['status']=='RUNNING'
# Confirm already-ended retrieval spans reached storage before the outage.
for _ in range(20):
    try:
        with urlopen('http://127.0.0.1:16686/api/traces/'+trace_id,timeout=3) as response: partial=json.load(response)
        if any(s['operationName']=='rag.search' for s in partial['data'][0]['spans']):break
    except Exception:pass
    time.sleep(.5)
else:raise RuntimeError('Retrieval trace not stored before outage')
(OUT/'analysis-before-outage-query.json').write_text(json.dumps(partial,indent=2))
report.update(jobId=analysis['jobId'],requirementId=analysis['requirementId'],traceId=trace_id,startedAt=datetime.now(timezone.utc).isoformat())
save()
start=time.monotonic()
try:
    docker('stop','-t','5','master-otel-collector-1','master-jaeger-1')
    report['servicesStopped']={name:docker('inspect','--format','{{.State.Running}}','master-'+name+'-1').strip()=='false' for name in ['otel-collector','jaeger']}
    assert all(report['servicesStopped'].values())
    report['jobDuringOutage']=job()['status'];assert report['jobDuringOutage']=='RUNNING'
    value=deepcopy(case['input']);value['pathParameters']={'loanId':'00000000-0000-4000-8000-000000000041'};value['fixtureProfile']='standard'
    actor=value['actorFixture'];assert actor=='same-department-manager'
    preconditions=[f'합성 계정과 부서 관계를 시험 환경에 준비한다: {actor}',
                   '합성 대여 신청의 상태는 PENDING_APPROVAL이다.','해당 자산의 상태는 AVAILABLE이다.',
                   '상태 변경 비교를 위해 실행 전 신청 상태와 자산 상태를 기록한다.']
    tcid=case['testCaseId']
    edited=api(f'/api/test-cases/{tcid}',{'reviewRevision':case['reviewRevision'],'input':value,'preconditions':preconditions},'PATCH')
    approved=api(f'/api/test-cases/{tcid}/approve',{'reviewRevision':edited['reviewRevision'],'reviewer':'demo-validation-script'})
    assert approved['approvalStatus']=='APPROVED'
    result=api(f'/api/test-cases/{tcid}/executions',method='POST')
    assert result['result']=='PASS'
    persisted=api('/api/executions/'+result['executionId']);assert persisted==result
    report.update(approvalStatus='APPROVED',testCaseId=tcid,executionId=result['executionId'],executionResult='PASS',persistedExactMatch=True)
    report['result']='PASS'
finally:
    docker('start','master-jaeger-1')
    for _ in range(40):
        try:
            with urlopen('http://127.0.0.1:16686/api/services',timeout=2) as response:json.load(response)
            break
        except Exception:time.sleep(.5)
    else:raise RuntimeError('Jaeger did not recover; collector remains stopped')
    docker('start','master-otel-collector-1')
    report['restoredAt']=datetime.now(timezone.utc).isoformat()
    report['totalExerciseMs']=round((time.monotonic()-start)*1000,2)
    report['servicesRunning']={name:docker('inspect','--format','{{.State.Running}}','master-'+name+'-1').strip()=='true' for name in ['otel-collector','jaeger']}
    save()
print(json.dumps(report),flush=True)
