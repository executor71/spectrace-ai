from pathlib import Path
import json,subprocess
root=Path(__file__).resolve().parents[2];dest=root/'docs/phase6-evidence'
def run(args,name,data=None):
    result=subprocess.run(args,input=data,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);(dest/name).write_bytes(result.stdout)
    assert result.returncode==0,(name,result.stdout[-2000:]);return result.stdout.decode()
evaluation_code='''
import json,os
from uuid import UUID
import psycopg
from app.main import connection,ENGINE_HASH
from app.metrics import evaluate,digest
with connection() as db:
    assert db.execute('SELECT current_user').fetchone()[0]=='evaluation_reader'
    truths=db.execute('SELECT truth_json,truth_hash FROM evaluation.ground_truth').fetchall()
    assert len(truths)==3 and all(digest(t)==h for t,h in truths)
    rows=db.execute('SELECT result_json,snapshot_json FROM evaluation.evaluation_run').fetchall()
    assert len(rows)>=5
    for report,snapshot in rows:
        assert report['engineHash']==ENGINE_HASH
        assert digest(snapshot['groundTruth'])==report['dataset']['groundTruthHash']
        if report['status']=='COMPLETED':
            assert evaluate(snapshot['groundTruth'],snapshot['inputs'])==report['metrics']
            assert digest(snapshot['inputs'])==report['inputHash']
for sql in ['SELECT * FROM app.requirement','SELECT * FROM rag.knowledge_chunk',"UPDATE evaluation.ground_truth SET split='development' WHERE false",'DELETE FROM evaluation.evaluation_run WHERE false']:
    try:
        with connection() as db:db.execute(sql)
    except psycopg.errors.InsufficientPrivilege:pass
    else:raise AssertionError(sql)
assert not any(k.startswith(('DB_APP','DB_MIGRATION','RAG_DB')) for k in os.environ)
print(json.dumps({'result':'PASS','frozenGroundTruthCases':len(truths),'savedRunsReplayed':len(rows),'appAndRagDenied':True,'groundTruthWritesDenied':True,'runUpdateDeleteDenied':True,'onlyEvaluationCredentials':True,'modelCallsForReplay':0}))
'''
evaluation=json.loads(run(['docker','exec','-i','master-evaluation-service-1','python','-'],'replay-results.json',evaluation_code.encode()))
generator_code='''
import os,json,psycopg
from app.db import rag_connection_settings
for table in ['evaluation.ground_truth','evaluation.evaluation_run','app.test_case']:
    try:
        with psycopg.connect(**rag_connection_settings()) as db:db.execute('SELECT * FROM '+table)
    except psycopg.errors.InsufficientPrivilege:pass
    else:raise AssertionError(table)
assert not any('EVALUATION' in k or 'MIGRATION' in k or 'DB_APP' in k for k in os.environ)
print(json.dumps({'result':'PASS','generationRole':'rag_reader','groundTruthAndEvaluationRunsDenied':True,'evaluationCredentialsAbsent':True}))
'''
generator=json.loads(run(['docker','exec','-i','master-ai-service-1','python','-'],'generation-boundary.json',generator_code.encode()))
sql='''
SELECT json_build_object(
 'migrations',(SELECT json_agg(version ORDER BY installed_rank) FROM app.flyway_schema_history WHERE success),
 'appGroundTruthUsage',has_schema_privilege('app_user','evaluation','USAGE'),
 'ragGroundTruthUsage',has_schema_privilege('rag_reader','evaluation','USAGE'),
 'appCanRecordEvaluation',has_function_privilege('app_user','evaluation.record_run(uuid,uuid,text,jsonb,jsonb)','EXECUTE'),
 'ragCanRecordEvaluation',has_function_privilege('rag_reader','evaluation.record_run(uuid,uuid,text,jsonb,jsonb)','EXECUTE'),
 'documents',(SELECT count(*) FROM rag.knowledge_document),'chunks',(SELECT count(*) FROM rag.knowledge_chunk));
SET ROLE app_user;
DO $$ BEGIN
 BEGIN PERFORM * FROM evaluation.ground_truth; RAISE EXCEPTION 'Unexpected GT access'; EXCEPTION WHEN insufficient_privilege THEN NULL; END;
 BEGIN PERFORM * FROM evaluation.evaluation_run; RAISE EXCEPTION 'Unexpected evaluation access'; EXCEPTION WHEN insufficient_privilege THEN NULL; END;
END $$;
'''
raw=run(['docker','exec','-i','master-postgres-1','psql','-U','postgres','-d','legacy_assistant','-At','-v','ON_ERROR_STOP=1'],'database-boundary.log',sql.encode())
database=json.loads(raw.splitlines()[0]);assert database['migrations']==list(map(str,range(1,10)))
assert not any(database[k] for k in ['appGroundTruthUsage','ragGroundTruthUsage','appCanRecordEvaluation','ragCanRecordEvaluation'])
assert database['documents']==9 and database['chunks']==27
container_data=json.loads(subprocess.check_output(['docker','inspect','master-ai-service-1','master-backend-1']))
for c in container_data:
    assert not any(e.startswith('EVALUATION_') for e in c['Config']['Env'])
    assert not any('evaluation-service' in m.get('Source','') for m in c['Mounts'])
assert 'INSERT INTO evaluation.ground_truth' not in (root/'backend/src/main/resources/db/migration/V9__isolated_evaluation.sql').read_text()
result={'result':'PASS','evaluation':evaluation,'generation':generator,'database':database,'labelsNotPackagedInBackend':True,'noEvaluationMountOrCredentialsInGenerationOrReview':True}
(dest/'runtime-results.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
