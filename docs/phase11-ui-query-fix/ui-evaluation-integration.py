import subprocess,json,hashlib
from pathlib import Path
r=Path('D:/MASTER과정');out=Path('ui-investigation').resolve();base=['docker','compose','-p','spectrace-ui-regression','-f',str(r/'compose.test.yaml')]
def run(args,name,input=None):
 p=subprocess.run(args,input=input,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);(out/name).write_bytes(p.stdout);assert p.returncode==0,(name,p.stdout.decode(errors='replace')[-1200:])
run(base+['up','-d','postgres-test'],'integration-db-start.log')
run(base+['run','--rm','backend-test','mvn','-B','-ntp','-Dtest=RequirementIntegrationTest','test'],'integration-db-migrate.log')
rows=json.loads((r/'evaluation-service/datasets/ground-truth-v1.json').read_text(encoding='utf8'))
def q(s):return "'"+s.replace("'","''")+"'"
sql=['BEGIN;']
for row in rows:
 values=','.join(q(row[k]) for k in ['datasetVersion','caseId','split','requirementHash','truthHash'])+','+q(json.dumps(row['truth'],ensure_ascii=False))+'::jsonb'
 sql.append('INSERT INTO evaluation.ground_truth VALUES ('+values+') ON CONFLICT DO NOTHING;')
sql.append('COMMIT;')
run(['docker','exec','-i','spectrace-ui-regression-postgres-test-1','psql','-U','postgres','-d','legacy_assistant_test','-v','ON_ERROR_STOP=1'],'isolated-fixture.log','\n'.join(sql).encode())
args=['docker','run','--rm','--network','spectrace-ui-regression_default','-e','EVALUATION_DB_HOST=postgres-test','-e','EVALUATION_DB_NAME=legacy_assistant_test','-e','EVALUATION_DB_USER=evaluation_reader','-e','EVALUATION_DB_PASSWORD=test_evaluation_only','-e','TEST_MIGRATION_PASSWORD=test_migration_only','--mount',f'type=bind,source={r / "evaluation-service/tests"},target=/evaluation/tests,readonly','master-evaluation-service','python','-m','unittest','discover','-s','tests','-v']
run(args,'evaluation-integration-tests.log');print('Evaluation 40 tests including isolated DB: PASS')
