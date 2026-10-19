import os
﻿import subprocess,json,urllib.request,time
from pathlib import Path
out=Path(os.environ.get('PHASE12_EVIDENCE_DIR',str(Path(__file__).resolve().parent)))
def get(url):
 with urllib.request.urlopen(url,timeout=15) as response:return json.load(response)
for attempt in range(30):
 try:
  if get('http://localhost:18080/actuator/health')['status']=='UP':break
 except Exception:time.sleep(1)
else:raise RuntimeError('Isolated backend did not start')
id='80e2d374-0825-4811-a11e-03ade256b6e8'
sql="SELECT jsonb_build_object('requirement',to_jsonb(r),'analysis',to_jsonb(a),'generation',to_jsonb(g),'cases',(SELECT jsonb_agg(to_jsonb(t) ORDER BY ordinal) FROM app.test_case t WHERE t.requirement_id=r.id)) FROM app.requirement r JOIN app.requirement_analysis a ON a.requirement_id=r.id JOIN app.test_case_generation g ON g.requirement_id=r.id WHERE r.id='"+id+"'::uuid;"
p=subprocess.run(['docker','exec','master-postgres-1','psql','-U','postgres','-d','legacy_assistant','-At','-c',sql],capture_output=True);assert p.returncode==0,p.stderr;data=json.loads(p.stdout)
def quoted(obj):return "'"+json.dumps(obj,ensure_ascii=False).replace("'","''")+"'::jsonb"
statements=['BEGIN;']
for key,table in [('requirement','app.requirement'),('analysis','app.requirement_analysis'),('generation','app.test_case_generation')]:
 statements.append(f'INSERT INTO {table} SELECT * FROM jsonb_populate_record(NULL::{table}, {quoted(data[key])});')
for item in data['cases']:
 item.update(approval_status='DRAFT',reviewed_at=None,reviewer=None,review_comment=None,review_revision=0)
 statements.append(f'INSERT INTO app.test_case SELECT * FROM jsonb_populate_record(NULL::app.test_case, {quoted(item)});')
statements.append('COMMIT;')
p=subprocess.run(['docker','exec','-i','spectrace-phase12-tests-postgres-test-1','psql','-U','postgres','-d','legacy_assistant_test','-v','ON_ERROR_STOP=1'],input='\n'.join(statements).encode(),capture_output=True);assert p.returncode==0,p.stderr
batch=get('http://localhost:18080/api/requirements/'+id+'/test-cases')
print('isolated seeded',[(tc['testCaseId'],tc['type'],tc['approvalStatus'],tc['executable']) for tc in batch['testCases']])
(out/'isolated-fixture.json').write_text(json.dumps({'requirementId':id,'testCaseIds':[tc['testCaseId'] for tc in batch['testCases']]},indent=2),encoding='utf8')
tables=[('app.requirement','id'),('app.requirement_analysis','requirement_id'),('app.test_case_generation','requirement_id'),('app.test_case','test_case_id'),('app.test_execution','execution_id'),('evaluation.ground_truth','case_id'),('evaluation.requirement_binding','requirement_id'),('evaluation.evidence_catalog','chunk_id'),('evaluation.evaluation_run','id'),('rag.knowledge_document','id'),('rag.knowledge_chunk','id')]
results={}
for table,key in tables:
 p=subprocess.run(['docker','exec','master-postgres-1','psql','-U','postgres','-d','legacy_assistant','-At','-c',f"SELECT count(*) || ':' || COALESCE(md5(jsonb_agg(to_jsonb(t) ORDER BY {key})::text),'empty') FROM {table} t;"],capture_output=True)
 if p.returncode!=0:raise RuntimeError(p.stderr.decode())
 results[table]=p.stdout.decode().strip()
(out/'production-before.json').write_text(json.dumps(results,indent=2),encoding='utf8')
