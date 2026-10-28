"""Explicit live validation; creates new synthetic records and makes real Qwen calls.

Stages are separate to prevent accidental repeated model calls after a later failure.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import Request, urlopen
from watch_summary_import import capture

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
STATE=OUT/'real-results.json'
report=json.loads(STATE.read_text()) if STATE.exists() else {}


def save(): STATE.write_text(json.dumps(report,indent=2),encoding='utf8')


def api(path,body=None,method=None,port=8080):
    request=Request(f'http://localhost:{port}'+path,data=None if body is None else json.dumps(body,ensure_ascii=False).encode(),
                    headers={'Content-Type':'application/json'},method=method)
    with urlopen(request,timeout=660) as response: return json.load(response)


def analysis():
    assert 'analysis' not in report, 'Already run; do not repeat real model calls'
    since=datetime.now(timezone.utc).isoformat()
    policy=json.loads((ROOT/'contracts/test-case-policy.json').read_text(encoding='utf8'))
    requirement=api('/api/requirements',{'title':'대여 승인 권한과 자기 승인 금지','description':policy['plans'][0]['confirmedCondition']})
    rid=requirement['id'];job=api(f'/api/requirements/{rid}/analysis-jobs',{})
    report['analysis']={'requirementId':rid,'jobId':job['jobId'],'since':since};save()
    print(json.dumps(report['analysis']),flush=True)
    start=time.monotonic();last=None
    while time.monotonic()-start<720:
        job=api('/api/analysis-jobs/'+job['jobId'])
        if job['status']!=last: print(job['status'],flush=True);last=job['status']
        if job['status'] in {'SUCCEEDED','FAILED','TIMED_OUT','CANCELLED'}: break
        time.sleep(1)
    report['analysis']['status']=job['status'];save()
    assert job['status']=='SUCCEEDED',job.get('errorCode')
    result=api(f'/api/requirements/{rid}/analysis')
    report['analysis'].update(conditions=len(result['confirmedConditions']),evidence=len(result['evidence']))
    capture('qwen-analysis',since,{rid});save()
    print(json.dumps(report['analysis']),flush=True)


def generation():
    assert 'generation' not in report, 'Already run; do not repeat real model calls'
    since=datetime.now(timezone.utc).isoformat()
    requirement=api('/api/requirements',{'title':'영상 검증용 대여 승인','description':'같은 부서 직원의 대여 승인, 자기 승인 금지'})
    rid=requirement['id']
    # Match the existing integration test setup. This is a labelled analysis fixture,
    # not a claim that Qwen produced this snapshot. No existing rows are overwritten.
    source=json.loads((ROOT/'ai-service/tests/fixtures/test-case-analysis.json').read_text(encoding='utf8'))
    source['requirementId']=rid
    quoted=json.dumps(source,ensure_ascii=False).replace("'","''")
    sql=f"BEGIN; INSERT INTO app.requirement_analysis(requirement_id,result_json) VALUES ('{rid}','{quoted}'::jsonb); UPDATE app.requirement SET status='ANALYZED' WHERE id='{rid}' AND status='DRAFT'; COMMIT;"
    subprocess.run(['docker','compose','exec','-T','postgres','psql','-U','postgres','-d','legacy_assistant','-v','ON_ERROR_STOP=1'],input=sql.encode(),check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    report['generation']={'requirementId':rid,'analysisSource':'EXISTING_GROUNDED_FIXTURE','fixtureHash':hashlib.sha256((ROOT/'ai-service/tests/fixtures/test-case-analysis.json').read_bytes()).hexdigest(),'since':since};save()
    print(json.dumps(report['generation']),flush=True)
    result=api(f'/api/requirements/{rid}/test-cases/generate',{})
    cases=result['testCases']
    normal=next(case for case in cases if case['type']=='NORMAL')
    defect=next(case for case in cases if any(a.get('kind')=='RESPONSE_TOKEN' and a.get('value')=='SELF_APPROVAL_FORBIDDEN' for a in case['expectedResult']['assertions']))
    report['generation'].update(testCases=len(cases),llmCalls=result['llmCalls'],normalId=normal['testCaseId'],defectId=defect['testCaseId'])
    saved=api(f'/api/requirements/{rid}/test-cases')
    assert len(saved['testCases'])==len(cases)>0 and result['llmCalls']>=1
    report['generation']['persistedCountMatches']=True
    capture('qwen-generation',since,{rid});save();print(json.dumps(report['generation']),flush=True)


if __name__=='__main__': {'analysis':analysis,'generation':generation}[sys.argv[1]]()
