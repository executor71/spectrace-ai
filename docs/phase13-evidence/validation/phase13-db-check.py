from pathlib import Path
import json,subprocess,urllib.request
out=Path('phase13-evidence');base='http://localhost:5173'
def get(path):return json.load(urllib.request.urlopen(base+path))
sql="""WITH cases AS (
 SELECT t.test_case_id,t.approval_status,t.review_revision,g.generation_id,
 (SELECT e.result_json->>'result' FROM app.test_execution e
 WHERE e.test_case_id=t.test_case_id AND e.result_json->>'generationId'=g.generation_id::text
 AND (e.result_json->>'testCaseRevision')::bigint=t.review_revision
 AND COALESCE((e.result_json->>'syntheticDefect')::boolean,false)=false ORDER BY e.executed_at DESC,e.execution_id DESC LIMIT 1) status
 FROM app.test_case t JOIN app.test_case_generation g ON t.generation_id=g.generation_id)
 SELECT json_build_object('requirements',(SELECT count(*) FROM app.requirement),'total',count(*),
 'DRAFT',count(*) FILTER(WHERE approval_status='DRAFT'),'APPROVED',count(*) FILTER(WHERE approval_status='APPROVED'),
 'REJECTED',count(*) FILTER(WHERE approval_status='REJECTED'),'PASS',count(*) FILTER(WHERE status='PASS'),
 'FAIL',count(*) FILTER(WHERE status='FAIL'),'ERROR',count(*) FILTER(WHERE status='ERROR'),'NOT_RUN',count(*) FILTER(WHERE status IS NULL)) FROM cases"""
db=json.loads(subprocess.check_output(['docker','exec','master-postgres-1','psql','-U','postgres','-d','legacy_assistant','-tAc',sql]).decode('utf8'))
api=get('/api/dashboard/summary');assert all(api['counts'][k]==v for k,v in db.items())
api_counts={'total':0,'DRAFT':0,'APPROVED':0,'REJECTED':0}
for row in api['requirements']:
 if row['counts']['total']:
  batch=get('/api/requirements/'+row['id']+'/test-cases');assert len(batch['testCases'])==row['counts']['total']
  for tc in batch['testCases']:api_counts['total']+=1;api_counts[tc['approvalStatus']]+=1
assert all(api['counts'][k]==v for k,v in api_counts.items())
raw=subprocess.check_output(['docker','exec','master-postgres-1','psql','-U','postgres','-d','legacy_assistant','-tAc',"SELECT json_build_object('requirements',(SELECT count(*) FROM app.requirement),'currentTCs',(SELECT count(*) FROM app.test_case),'executions',(SELECT count(*) FROM app.test_execution))"]).decode('utf8')
after=json.loads(raw);before=json.loads((out/'baseline.json').read_text(encoding='utf8'))['counts'];assert all(after[k]==before[k] for k in after)
targets=get('/api/evaluations/targets')['requirements'];evaluation_states=[]
for target in targets:
 runs=get('/api/requirements/'+target['requirementId']+'/evaluations');evaluation_states.append({'requirementId':target['requirementId'],'caseId':target['caseId'],'runCount':len(runs)})
result={'independentDBCounts':db,'existingAPIReviewCounts':api_counts,'appDataUnchanged':after,'evaluationTargets':evaluation_states,'matched':True}
(out/'db-api-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(result,ensure_ascii=True,indent=2))
