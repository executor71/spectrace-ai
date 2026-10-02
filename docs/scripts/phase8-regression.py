from pathlib import Path
import json,subprocess,sys,shutil,hashlib
root=Path(__file__).resolve().parents[2];dest=root/'docs/phase8-evidence'
def run(args,name,env=None):
    result=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env=env)
    (dest/name).write_bytes(result.stdout);assert result.returncode==0,(name,result.stdout[-2500:].decode(errors='replace'));return result.stdout.decode()
run([sys.executable,'-X','utf8',str(root/'docs/scripts/phase7-regression.py')],'phase0-7-regression.log')
for name in ['backend-tests.log','python-tests.log','evaluation-tests.log','database-boundary.log','evaluation-replay.json','generation-boundary.json']:
    shutil.copyfile(root/'docs/phase7-evidence'/name,dest/name)
previous=json.loads((root/'docs/phase7-evidence/regression-results.json').read_text(encoding='utf-8'));assert previous['totalAutomatedTests']==185
run(['docker','cp',str(root/'retrieval-service/tests')+'/.','master-retrieval-service-1:/retrieval/tests'],'test-provision.log')
text=run(['docker','exec','master-retrieval-service-1','python','-m','unittest','discover','-s','tests','-v'],'retrieval-tests.log');assert 'Ran 27 tests' in text
import os
env=os.environ.copy();env['PYTHONPATH']=str(root/'evaluation-service')
text=run([sys.executable,'-X','utf8','-m','unittest','discover','-s',str(root/'evaluation-service/retrieval_tests'),'-v'],'retrieval-metric-tests.log',env);assert 'Ran 13 tests' in text
baseline=json.loads((root/'docs/phase7-baseline/sha256.json').read_text())
assert all(hashlib.sha256((root/rel).read_bytes()).hexdigest()==h for rel,h in baseline.items())
report={'result':'PASS','existingPhase0to7Tests':185,'retrieverTests':27,'retrievalMetricTests':13,'totalTests':225,'failures':0,'errors':0,'skipped':0,'phase7BaselineFilesUnchanged':len(baseline),'phase0to7':previous}
(dest/'regression-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print('PASS 225 tests; Phase 0-7 and all Phase 7 source hashes unchanged')
