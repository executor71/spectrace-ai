"""One explicit real-model job, restartable observer; never enqueues a second job."""
import json,time,urllib.request,hashlib
from pathlib import Path
out=Path(__file__).resolve().parent
base='http://localhost:8080'
rid='80e2d374-0825-4811-a11e-03ade256b6e8'
def call(path,body=None):
 req=urllib.request.Request(base+path,data=json.dumps(body,ensure_ascii=False).encode() if body is not None else None,headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=30) as response:return json.load(response)
def save(name,value):(out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
def source():return {path:call(path) for path in [f'/api/requirements/{rid}',f'/api/requirements/{rid}/analysis',f'/api/requirements/{rid}/test-cases']}
jobfile=out/'job-result.json'
if jobfile.exists():
 job=json.loads(jobfile.read_text(encoding='utf8'));impact=call('/api/change-impacts/'+job['impactId'])
else:
 baseline=call('/api/change-impacts/baselines/'+rid);save('baseline-snapshot.json',baseline)
 save('core-before.json',source())
 proposal='요청자 소속 부서의 부서장 또는 자산관리 담당자가 대여 신청을 승인할 수 있다. 자기 승인은 계속 금지한다.'
 impact=call('/api/change-impacts',dict(baselineRequirementId=rid,baselineRevision=baseline['revision'],proposalTitle='합성 대여 승인 권한 확장 검토',proposalContent=proposal))
 save('proposal.json',impact)
 job=call('/api/change-impacts/'+impact['impactId']+'/analysis-jobs',{})
 save('job-result.json',job)
 print('Enqueued exactly one real model job: '+job['jobId'],flush=True)
started=time.monotonic();seen=[]
for _ in range(450):
 job=call('/api/analysis-jobs/'+job['jobId'])
 if not seen or seen[-1]!=job['status']:seen.append(job['status']);print(job['status'],flush=True)
 save('job-result.json',job)
 if job['status'] not in ('QUEUED','RUNNING'):break
 time.sleep(2)
assert job['status']=='SUCCEEDED',job
result=call('/api/change-impacts/'+impact['impactId']+'/results')
for field,name in [('conditionChanges','condition-diff.json'),('affectedApis','impacted-apis.json'),('affectedTestCases','impacted-testcases.json')]:save(name,result[field])
save('analysis-result.json',result)
assert json.loads((out/'core-before.json').read_text(encoding='utf8'))==source(),'Existing Core changed'
save('real-e2e-results.json',dict(jobId=job['jobId'],impactId=impact['impactId'],observedStatuses=seen,providerCalls=result['llmCallCount'],queueWaitMs=job.get('queueWaitMs'),executionDurationMs=job.get('executionDurationMs'),analysisDurationMs=result['analysisDurationMs'],graphStatus=result['graphStatus'],conditionTypes=[c['changeType'] for c in result['conditionChanges']],apiIds=[a['apiId'] for a in result['affectedApis']],testCases=len(result['affectedTestCases']),coreUnchanged=True))
print(json.dumps(json.loads((out/'real-e2e-results.json').read_text(encoding='utf8')),ensure_ascii=True),flush=True)
