from pathlib import Path
import json,subprocess,hashlib,sys
root=Path(__file__).resolve().parents[2];dest=root/'docs/phase8-evidence'
def run(command,name,data=None):
    result=subprocess.run(command,input=data,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (dest/name).write_bytes(result.stdout);assert result.returncode==0,(name,result.stdout[-2000:].decode(errors='replace'));return result.stdout.decode()
code='''
import os,json,hashlib,psycopg
from pathlib import Path
from app.db import rag_connection_settings
from retrieval.core import corpus_snapshot,digest,settings
assert not any(k.startswith(('EVALUATION_','DB_APP','DB_MIGRATION')) for k in os.environ)
denied=[]
for sql in ['SELECT * FROM evaluation.ground_truth','SELECT * FROM evaluation.evaluation_run','SELECT * FROM app.requirement','SELECT * FROM app.test_execution','DELETE FROM rag.knowledge_chunk WHERE false']:
 try:
  with psycopg.connect(**rag_connection_settings()) as db:db.execute(sql)
 except psycopg.errors.InsufficientPrivilege:denied.append(sql)
 else:raise AssertionError(sql)
snapshot=corpus_snapshot(rag_connection_settings());assert snapshot['role']=='rag_reader';assert digest(snapshot)==settings()['expectedCorpusHash']
for base in ['/app','/retrieval']:
 assert not any('ground-truth' in str(p) or 'retrieval-v1.json' in str(p) or 'evaluation-dataset' in str(p) for p in Path(base).rglob('*.json'))
print(json.dumps({'result':'PASS','role':snapshot['role'],'deniedStatements':denied,'corpusHash':digest(snapshot),'documents':len({c['documentId'] for c in snapshot['chunks']}),'chunks':len(snapshot['chunks']),'vectorSourceHash':hashlib.sha256(Path('/app/app/vector_search.py').read_bytes()).hexdigest(),'embeddingSourceHash':hashlib.sha256(Path('/app/app/local_embedding.py').read_bytes()).hexdigest(),'groundTruthFilesAbsent':True,'evaluationCredentialsAbsent':True}))
'''
boundary=json.loads(run(['docker','exec','-i','master-retrieval-service-1','python','-'],'retriever-boundary.json',code.encode()))
assert boundary['vectorSourceHash']==hashlib.sha256((root/'ai-service/app/vector_search.py').read_bytes()).hexdigest()
assert boundary['embeddingSourceHash']==hashlib.sha256((root/'ai-service/app/local_embedding.py').read_bytes()).hexdigest()
containers=json.loads(subprocess.check_output(['docker','inspect','master-retrieval-service-1']))
assert not any(any(part in m.get('Source','').lower() for part in ['evaluation','phase8-evidence','datasets']) for m in containers[0]['Mounts'])
run(['docker','exec','master-retrieval-service-1','pip','freeze'],'retrieval-package-versions.txt')
info=json.loads(subprocess.check_output(['docker','info','--format','{{json .}}']))
environment={'cpuCount':info['NCPU'],'memoryBytes':info['MemTotal'],'os':info['OperatingSystem'],'architecture':info['Architecture'],
 'retrieverImage':containers[0]['Image'],'cpuLimit':containers[0]['HostConfig']['NanoCpus'],'memoryLimit':containers[0]['HostConfig']['Memory'],
 'settings':json.loads((root/'retrieval-service/config/retrieval.json').read_text()),'embedding':json.loads((root/'ai-service/config/embedding.json').read_text()),
 'inferenceDevice':'CPU','inferenceDtype':'float32','remoteInferenceRequests':0,'perCallApiFees':0}
(dest/'environment.json').write_text(json.dumps(environment,indent=2))
run(['docker','stats','--no-stream','--format','{{json .}}','master-retrieval-service-1','master-ai-service-1'],'resource-snapshot.jsonl')
print('PASS retrieval role, Ground Truth isolation, original vector/embedding source hashes and unchanged corpus')
