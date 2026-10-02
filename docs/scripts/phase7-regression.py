"""Regression harness. Evaluation checks stay outside the Dummy execution runtime."""
from pathlib import Path
import ast,hashlib,json,subprocess,urllib.request,xml.etree.ElementTree as ET
root=Path(__file__).resolve().parents[2];dest=root/'docs/phase7-evidence'
def run(args,name,data=None):
    result=subprocess.run(args,input=data,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (dest/name).write_bytes(result.stdout)
    assert result.returncode==0,(name,result.stdout[-2500:].decode(errors='replace'))
    return result.stdout.decode()
compose=['docker','compose','-p','phase7test','-f',str(root/'compose.test.yaml'),'-f',str(root/'compose.phase6-test.yaml'),'-f',str(root/'compose.phase7-test.yaml')]
run(compose+['up','-d','postgres-test'],'regression-db-start.log')
run(compose+['run','--build','--rm','backend-test'],'backend-tests.log')
print('PASS Backend tests',flush=True)
# Provision only the isolated evaluation test DB using the existing Phase 6 provisioner.
seed=(root/'docs/scripts/phase6-seed.py').read_text(encoding='utf-8').replace("'legacy-phase6-tests'","'phase7test'")
import sys
saved=sys.argv;sys.argv=['phase6-seed.py','--test']
try:exec(compile(seed,'phase6-seed.py','exec'),{'__file__':str(root/'docs/scripts/phase6-seed.py'),'__name__':'__main__'})
finally:sys.argv=saved
run(compose+['run','--rm','evaluation-test'],'evaluation-tests.log')
assert 'Ran 40 tests' in (dest/'evaluation-tests.log').read_text() and '\nOK' in (dest/'evaluation-tests.log').read_text()
print('PASS Evaluation 40 tests',flush=True)
run(['docker','cp',str(root/'ai-service/tests')+'/.','master-ai-service-1:/app/tests'],'python-provision.log')
text=run(['docker','exec','master-ai-service-1','python','-m','unittest','discover','-s','tests','-v'],'python-tests.log')
assert 'Ran 61 tests' in text and '\nOK' in text
print('PASS Python 61 tests',flush=True)
health=[]
for url in ['http://localhost:8080/actuator/health','http://localhost:8000/health','http://localhost:8090/health']:
    with urllib.request.urlopen(url,timeout=20) as response:body=json.load(response);assert body['status']=='UP';health.append({'url':url,'body':body})
retrieval=[]
for case in json.loads((root/'docs/phase2-evidence/top5-results.json').read_text(encoding='utf-8')):
    request=urllib.request.Request('http://localhost:8000/internal/v1/search',data=json.dumps({'query':case['query'],'topK':5}).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=90) as response:hits=json.load(response)
    assert [h['chunkId'] for h in hits]==[h['chunkId'] for h in case['hits']]
    assert all(abs(a['score']-b['score'])<1e-6 for a,b in zip(hits,case['hits']))
    retrieval.append({'number':case['number'],'sameTop5AndScores':True});print('PASS RAG frozen query',case['number'],flush=True)
for name in ['approve-response.json','reject-response.json']:
    old=json.loads((root/'docs/phase5-evidence'/name).read_text(encoding='utf-8'))
    with urllib.request.urlopen('http://localhost:8080/api/requirements/'+old['requirementId']+'/test-cases') as response:batch=json.load(response)
    assert next(c for c in batch['testCases'] if c['testCaseId']==old['testCaseId'])==old
# Reuse the unchanged Phase 6 snapshot replay and role-boundary checks.
tree=ast.parse((root/'docs/scripts/phase6-runtime.py').read_text(encoding='utf-8'))
codes={n.targets[0].id:ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id in ['evaluation_code','generator_code','sql']}
evaluation=json.loads(run(['docker','exec','-i','master-evaluation-service-1','python','-'],'evaluation-replay.json',codes['evaluation_code'].encode()))
generator=json.loads(run(['docker','exec','-i','master-ai-service-1','python','-'],'generation-boundary.json',codes['generator_code'].encode()))
extra="""
SET ROLE app_user;
DO $$ BEGIN
 BEGIN PERFORM * FROM rag.knowledge_chunk; RAISE EXCEPTION 'unexpected rag access'; EXCEPTION WHEN insufficient_privilege THEN NULL; END;
 BEGIN DELETE FROM app.test_execution WHERE false; RAISE EXCEPTION 'unexpected execution delete'; EXCEPTION WHEN insufficient_privilege THEN NULL; END;
END $$;
RESET ROLE;
SET ROLE evaluation_reader;
DO $$ BEGIN
 BEGIN PERFORM * FROM app.test_execution; RAISE EXCEPTION 'unexpected execution access'; EXCEPTION WHEN insufficient_privilege THEN NULL; END;
END $$;
RESET ROLE;
SET ROLE rag_reader;
DO $$ BEGIN
 BEGIN PERFORM * FROM app.test_execution; RAISE EXCEPTION 'unexpected execution access'; EXCEPTION WHEN insufficient_privilege THEN NULL; END;
END $$;
"""
raw=run(['docker','exec','-i','master-postgres-1','psql','-U','postgres','-d','legacy_assistant','-At','-v','ON_ERROR_STOP=1'],'database-boundary.log',(codes['sql']+extra).encode())
database=json.loads(raw.splitlines()[0]);assert database['migrations']==list(map(str,range(1,11)))
assert not any(database[k] for k in ['appGroundTruthUsage','ragGroundTruthUsage','appCanRecordEvaluation','ragCanRecordEvaluation'])
assert database['documents']==9 and database['chunks']==27
containers=json.loads(subprocess.check_output(['docker','inspect','master-ai-service-1','master-backend-1']))
for c in containers:
    assert not any(e.startswith('EVALUATION_') for e in c['Config']['Env'])
    assert not any('evaluation-service' in m.get('Source','') for m in c['Mounts'])
baseline=json.loads((root/'docs/phase6-baseline/sha256.json').read_text())
changed=[rel for rel,h in baseline.items() if hashlib.sha256((root/rel).read_bytes()).hexdigest()!=h]
assert set(changed)=={'frontend/src/TestCases.tsx','frontend/src/TestCaseReview.tsx'},changed
suites=[ET.parse(p).getroot().attrib for p in (dest/'backend-tests').glob('TEST-*.xml')]
assert sum(int(s['tests']) for s in suites)==84 and all(int(s['failures'])+int(s['errors'])+int(s['skipped'])==0 for s in suites)
result={'result':'PASS','backendTests':84,'newExecutionTests':29,'pythonTests':61,'evaluationTests':40,'totalAutomatedTests':185,'health':health,'phase2Retrieval':retrieval,'phase5ReviewPreserved':True,'baselineFiles':len(baseline),'unchangedFiles':len(baseline)-len(changed),'changedFiles':changed,'evaluation':evaluation,'generation':generator,'database':database,'executionHistoryImmutableAndRoleIsolated':True,'noEvaluationMountOrCredentialsInRunner':True}
(dest/'regression-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print('PASS Phase 0-6 regression: 185 tests')
