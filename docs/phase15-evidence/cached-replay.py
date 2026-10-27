"""Reprocess saved provider output through the shared queue, zero new LLM calls."""
import json,time,urllib.request
from pathlib import Path
out=Path(__file__).resolve().parent
original=json.loads((out/'real-e2e-results.json').read_text(encoding='utf8'));impact=original['impactId']
def call(path,body=None):
 req=urllib.request.Request('http://localhost:8080'+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=20) as r:return json.load(r)
def save(name,value):(out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
file=out/'reprocessing-job.json'
if file.exists():job=json.loads(file.read_text(encoding='utf8'))
else:job=call(f'/api/change-impacts/{impact}/analysis-jobs',{});save(file.name,job)
for _ in range(120):
 job=call('/api/analysis-jobs/'+job['jobId']);save(file.name,job)
 if job['status'] not in ('QUEUED','RUNNING'):break
 time.sleep(1)
assert job['status']=='SUCCEEDED',job
result=call(f'/api/change-impacts/{impact}/results')
assert result['llmCallCount']==0,'Reprocessing unexpectedly invoked model'
assert result['reusedModelAnalysisId']==original['jobId']
assert [c['changeType'] for c in result['conditionChanges']].count('UNCHANGED')==2
assert [c['changeType'] for c in result['conditionChanges']].count('ADDED')==1
save('final-analysis-result.json',result)
for key,name in [('conditionChanges','condition-diff.json'),('affectedApis','impacted-apis.json'),('affectedTestCases','impacted-testcases.json')]:save(name,result[key])
save('cached-replay-results.json',dict(jobId=job['jobId'],modelCalls=0,reusedModelAnalysisId=result['reusedModelAnalysisId'],conditionTypes=[c['changeType'] for c in result['conditionChanges']],queueWaitMs=job['queueWaitMs'],executionDurationMs=job['executionDurationMs'],graphStatus=result['graphStatus']))
print(json.dumps(json.loads((out/'cached-replay-results.json').read_text(encoding='utf8'))),flush=True)
