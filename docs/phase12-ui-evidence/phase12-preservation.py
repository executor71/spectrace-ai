import os
﻿from pathlib import Path
import subprocess,json,urllib.request
out=Path(os.environ.get('PHASE12_EVIDENCE_DIR',str(Path(__file__).resolve().parent)));before=json.loads((out/'production-before.json').read_text());keys={'app.requirement':'id','app.requirement_analysis':'requirement_id','app.test_case_generation':'requirement_id','app.test_case':'test_case_id','app.test_execution':'execution_id','evaluation.ground_truth':'case_id','evaluation.requirement_binding':'requirement_id','evaluation.evidence_catalog':'chunk_id','evaluation.evaluation_run':'id','rag.knowledge_document':'id','rag.knowledge_chunk':'id'}
after={}
for table,key in keys.items():
 p=subprocess.run(['docker','exec','master-postgres-1','psql','-U','postgres','-d','legacy_assistant','-At','-c',f"SELECT count(*) || ':' || COALESCE(md5(jsonb_agg(to_jsonb(t) ORDER BY {key})::text),'empty') FROM {table} t;"],capture_output=True);assert p.returncode==0,p.stderr;after[table]=p.stdout.decode().strip()
assert before==after,{key:(before[key],after[key]) for key in before if before[key]!=after[key]};(out/'production-after.json').write_text(json.dumps(after,indent=2),encoding='utf8')
health=[]
for name,url in [('frontend','http://localhost:5173'),('backend','http://localhost:8080/actuator/health'),('ai','http://localhost:8000/health'),('evaluation','http://localhost:8090/health'),('graph','http://localhost:8030/health')]:
 with urllib.request.urlopen(url,timeout=15) as response:health.append({'name':name,'url':url,'status':response.status,'body':json.load(response) if name!='frontend' else 'HTML'})
(out/'final-health.json').write_text(json.dumps(health,ensure_ascii=False,indent=2),encoding='utf8');print('Production tables identical:',len(after));print([(item['name'],item['status']) for item in health])
# Only this phase's isolated test resources are removed.
p=subprocess.run(['docker','rm','-f','spectrace-phase12-backend'],capture_output=True);assert p.returncode==0,p.stderr
p=subprocess.run(['docker','compose','-p','spectrace-phase12-tests','-f','D:/MASTER\uacfc\uc815/compose.test.yaml','down'],capture_output=True);(out/'isolated-cleanup.log').write_bytes(p.stdout+p.stderr);assert p.returncode==0,p.stderr
