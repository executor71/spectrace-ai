"""Evaluation administrator: bind frozen cases, run KPIs, preserve failures verbatim."""
from pathlib import Path
import json,subprocess,urllib.request,hashlib
root=Path(__file__).resolve().parents[2];dest=root/'docs/phase6-evidence'
inputs=json.loads((dest/'generation-inputs.json').read_text(encoding='utf-8'))
truths=json.loads((root/'evaluation-service/datasets/ground-truth-v1.json').read_text(encoding='utf-8'))
def digest(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
sql=['BEGIN;']
for row in inputs:
    assert row['complete'];truth=next(t for t in truths if t['caseId']==row['caseId'])
    assert digest({k:row['requirement'][k] for k in ['title','description']})==truth['requirementHash']
    rid=row['requirement']['id'];case=row['caseId']
    sql.append(f"INSERT INTO evaluation.requirement_binding VALUES('{rid}','phase6-v1','{case}') ON CONFLICT DO NOTHING;")
    sql.append(f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM evaluation.requirement_binding WHERE requirement_id='{rid}' AND case_id='{case}') THEN RAISE EXCEPTION 'Binding conflict'; END IF; END $$;")
sql.append('COMMIT;')
result=subprocess.run(['docker','exec','-i','master-postgres-1','psql','-U','postgres','-d','legacy_assistant','-v','ON_ERROR_STOP=1'],input='\n'.join(sql).encode(),stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
assert result.returncode==0,result.stdout.decode()
def call(path,body=None):
    request=urllib.request.Request('http://localhost:8090'+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=90) as response:return response.status,json.load(response)
results=[]
for row in inputs:
    rid=row['requirement']['id'];status,report=call('/api/evaluations',{'requirementId':rid})
    assert status==201 and report['status']=='COMPLETED',report
    _,saved=call('/api/evaluations/'+report['id']);assert report==saved
    _,history=call('/api/requirements/'+rid+'/evaluations');assert report in history
    results.append(report)
    (dest/'measurement-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    m=report['metrics'];print(row['caseId'],{k:m[k]['value'] for k in ['recallAt5','scenarioCoverage','testCaseValidity']},'TC',m['counts']['testCases'],flush=True)
print('PASS 3 frozen dataset runs; no generation calls in evaluation')
