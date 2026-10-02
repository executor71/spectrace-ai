"""Administrative dataset provisioner, never called by generation or runtime APIs."""
from pathlib import Path
import hashlib,json,subprocess,sys
root=Path(__file__).resolve().parents[2]
rows=json.loads((root/'evaluation-service/datasets/ground-truth-v1.json').read_text(encoding='utf-8'))
def digest(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
manifest=json.loads((root/'evaluation-service/datasets/manifest.json').read_text(encoding='utf-8'))
assert digest(rows)==manifest['datasetHash'],'Frozen dataset changed'
def quote(v):return "'"+v.replace("'","''")+"'"
sql=['BEGIN;']
for row in rows:
    assert digest(row['truth'])==row['truthHash']
    values=','.join(quote(row[k]) for k in ['datasetVersion','caseId','split','requirementHash','truthHash'])+','+quote(json.dumps(row['truth'],ensure_ascii=False))+'::jsonb'
    sql.append('INSERT INTO evaluation.ground_truth VALUES ('+values+') ON CONFLICT DO NOTHING;')
    sql.append("DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM evaluation.ground_truth WHERE dataset_version="+quote(row['datasetVersion'])+' AND case_id='+quote(row['caseId'])+' AND truth_hash='+quote(row['truthHash'])+') THEN RAISE EXCEPTION \'Frozen Ground Truth mismatch\'; END IF; END $$;')
sql.append('COMMIT;')
if '--test' in sys.argv:
    command=['docker','compose','-p','legacy-phase6-tests','-f',str(root/'compose.test.yaml'),'-f',str(root/'compose.phase6-test.yaml'),'exec','-T','postgres-test','psql','-U','postgres','-d','legacy_assistant_test','-v','ON_ERROR_STOP=1']
else:command=['docker','exec','-i','master-postgres-1','psql','-U','postgres','-d','legacy_assistant','-v','ON_ERROR_STOP=1']
result=subprocess.run(command,input='\n'.join(sql).encode(),stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
assert result.returncode==0,result.stdout.decode();print('Frozen Ground Truth seed verified:',manifest['datasetHash'])
