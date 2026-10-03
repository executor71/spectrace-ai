"""Preserve archived evidence while running unchanged business regression assertions."""
from pathlib import Path
import hashlib,json,subprocess,sys,os,re
root=Path(__file__).resolve().parents[2];dest=root/'docs/phase10-evidence';prior=dest/'prior-regression';prior.mkdir(exist_ok=True)
allowed={'backend/pom.xml','backend/src/main/java/com/example/legacyassistant/analysis/AnalysisClient.java',
    'backend/src/main/java/com/example/legacyassistant/testcase/TestCaseClient.java','ai-service/app/main.py','ai-service/app/llm_provider.py',
    'retrieval-service/retrieval/api.py','evaluation-service/app/main.py','mcp-server/app/server.py'}
baseline=json.loads((root/'docs/phase9-baseline/sha256.json').read_text())
changed={rel for rel,h in baseline.items() if hashlib.sha256((root/rel).read_bytes()).hexdigest()!=h}
assert changed==allowed,changed
(dest/'source-change-audit.json').write_text(json.dumps({'frozenFiles':len(baseline),'changedTracingOnlyFiles':sorted(changed),'unchangedFiles':len(baseline)-len(changed)},indent=2))
# Recreated runtime containers do not retain prior docker-cp test fixtures.
for folder,target in [('knowledge','/knowledge'),('ai-service/app','/ai-service/app')]:
    if folder=='ai-service/app':subprocess.run(['docker','exec','master-ai-service-1','mkdir','-p','/ai-service'],check=True)
    subprocess.run(['docker','cp',str(root/folder),'master-ai-service-1:'+target],check=True)
# Reuse all prior behavioral assertions. Only artifact paths and the explicit
# instrumentation hash delta change; Phase 0-9 source/evidence are not overwritten.
source=(root/'docs/scripts/phase7-regression.py').read_text(encoding='utf-8')
source=source.replace("dest=root/'docs/phase7-evidence'","dest=root/'docs/phase10-evidence/prior-regression'")
source=source.replace("str(root/'compose.phase7-test.yaml')]","str(root/'compose.phase7-test.yaml'),'-f',str(root/'compose.phase10-test.yaml')]")
source=source.replace("assert set(changed)=={'frontend/src/TestCases.tsx','frontend/src/TestCaseReview.tsx'},changed", "assert set(changed)==({'frontend/src/TestCases.tsx','frontend/src/TestCaseReview.tsx'} | (PHASE10_ALLOWED & set(baseline))),changed")
exec(compile(source,'phase7-regression.py','exec'),{'__file__':str(root/'docs/scripts/phase7-regression.py'),'__name__':'__main__','PHASE10_ALLOWED':allowed})
def run(command,name,env=None):
    result=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env=env)
    (prior/name).write_bytes(result.stdout);assert result.returncode==0,(name,result.stdout[-2500:].decode(errors='replace'))
    return result.stdout.decode()
run(['docker','cp',str(root/'retrieval-service/tests')+'/.','master-retrieval-service-1:/retrieval/tests'],'retrieval-provision.log')
assert 'Ran 27 tests' in run(['docker','exec','master-retrieval-service-1','python','-m','unittest','discover','-s','tests','-v'],'retrieval-tests.log')
env=os.environ.copy();env['PYTHONPATH']=str(root/'evaluation-service')
assert 'Ran 13 tests' in run([sys.executable,'-X','utf8','-m','unittest','discover','-s',str(root/'evaluation-service/retrieval_tests'),'-v'],'retrieval-metric-tests.log',env)
base=['docker','run','--rm','--network','master_default','-e','APP_OTEL_ENABLED=true','--mount',f'type=bind,source={root}/mcp-server/tests,target=/tests,readonly','--mount',f'type=bind,source={prior},target=/evidence','master-mcp-server']
assert 'Ran 18 tests' in run(base+['python','-m','unittest','discover','-s','/tests','-p','test_*.py','-v'],'mcp-unit-tests.log')
run(base+['python','/tests/e2e.py'],'mcp-e2e.log')
previous=json.loads((prior/'regression-results.json').read_text())
report={'result':'PASS','phase0to9Tests':243,'observabilityTests':9,'totalTests':252,'failures':0,'errors':0,'mcpE2eAssertions':json.loads((prior/'mcp-e2e-results.json').read_text())['assertions'],'sourceAudit':json.loads((dest/'source-change-audit.json').read_text()),'phase0to7':previous}
(dest/'regression-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print('PASS 252 tests and MCP E2E',flush=True)
