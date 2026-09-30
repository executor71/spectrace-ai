from pathlib import Path
import subprocess,json,hashlib,xml.etree.ElementTree as ET
root=Path(__file__).resolve().parents[2];dest=root/'docs/phase5-evidence'
def run(args,name,data=None):
    result=subprocess.run(args,input=data,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (dest/name).write_bytes(result.stdout);assert result.returncode==0,(args,result.returncode,result.stdout[-2000:]);return result.stdout.decode()
run(['docker','exec','master-ai-service-1','python','-m','unittest','discover','-s','tests','-v'],'python-tests.log')
run(['docker','exec','-i','master-ai-service-1','python','-'],'runtime-security.log',(root/'docs/scripts/phase4-runtime-security.py').read_bytes())
sql='''
SELECT json_build_object(
 'migrations', (SELECT json_agg(version ORDER BY installed_rank) FROM app.flyway_schema_history WHERE success),
 'vectorExtension',(SELECT extversion FROM pg_extension WHERE extname='vector'),
 'documents',(SELECT count(*) FROM rag.knowledge_document),
 'chunks',(SELECT count(*) FROM rag.knowledge_chunk),
 'appToRag',has_schema_privilege('app_user','rag','USAGE'),
 'appToEvaluation',has_schema_privilege('app_user','evaluation','USAGE'),
 'ragToApp',has_schema_privilege('rag_reader','app','USAGE'),
 'ragToEvaluation',has_schema_privilege('rag_reader','evaluation','USAGE'),
 'reviewTrigger',(SELECT count(*) FROM pg_trigger WHERE tgname='protect_generated_test_case'),
 'reviewStatuses',(SELECT json_agg(s) FROM (SELECT approval_status,count(*) FROM app.test_case GROUP BY approval_status) s)
);
'''
raw=run(['docker','exec','-i','master-postgres-1','psql','-U','postgres','-d','legacy_assistant','-At','-v','ON_ERROR_STOP=1'],'database-results.json',sql.encode())
database=json.loads(raw);assert database['migrations']==list(map(str,range(1,9)))
assert database['documents']==9 and database['chunks']==27 and database['reviewTrigger']==1
assert not any(database[k] for k in ['appToRag','appToEvaluation','ragToApp','ragToEvaluation'])
baseline=json.loads((root/'docs/phase4-baseline/sha256.json').read_text())
allowed={'backend/src/main/java/com/example/legacyassistant/testcase/TestCaseRepository.java','backend/src/main/java/com/example/legacyassistant/testcase/TestCaseService.java','frontend/src/TestCases.tsx','frontend/src/style.css','compose.test.yaml'}
changed=[name for name,digest in baseline.items() if hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest]
assert set(changed)==allowed,changed
protected=[name for name in baseline if name not in allowed]
result={'result':'PASS','phase4BaselineFiles':len(baseline),'unchangedFiles':len(protected),'allowedChangedFiles':changed,'llmCalls':0,'database':database}
(dest/'runtime-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=True))
