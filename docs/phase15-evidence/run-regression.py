"""Containerized unit regressions; logs stay in the OS temporary directory."""
import concurrent.futures
import json
import re
import subprocess
import shutil
import sys
import tempfile
from pathlib import Path

root=Path(__file__).resolve().parents[2]
out=root/'docs/phase15-evidence'
logs=Path(tempfile.gettempdir())/'spectrace-phase15'
logs.mkdir(exist_ok=True)
for name in ['source-facts.json','analysis-context.json']:
 shutil.copy2(root/'docs/phase11-evidence'/name,logs/name)
selected=set(sys.argv[1:])
previous=json.loads((out/'regression-results.json').read_text()) if (out/'regression-results.json').exists() else []
suites=[
 ('ai','master-ai-service',['python','-m','unittest','discover','-s','/app/tests','-p','test_*.py','-q'],
  [('ai-service/app','/app/app'),('ai-service/tests','/app/tests'),('ai-service','/ai-service'),('contracts','/contracts'),('knowledge','/knowledge')]),
 ('retrieval','master-retrieval-service',['python','-m','unittest','discover','-s','/app/tests','-p','test_*.py','-q'],[('retrieval-service/tests','/app/tests'),('retrieval-service/retrieval','/app/retrieval')]),
 ('evaluation-metrics','master-evaluation-service',['python','-m','unittest','discover','-s','/app/tests','-p','test_metrics.py','-q'],[('evaluation-service/tests','/app/tests')]),
 ('evaluation-api','master-evaluation-service',['python','-m','unittest','discover','-s','/app/tests','-p','test_api.py','-q'],[('evaluation-service/tests','/app/tests')]),
 ('mcp','master-mcp-server',['python','-m','unittest','discover','-s','/tests','-p','test_*.py','-q'],[('mcp-server/tests','/tests')]),
 ('graph-projection','master-graph-service',['python','-m','pytest','/graph/tests/test_projection.py','/graph/tests/test_refresh.py','-q','-p','no:cacheprovider'],[('graph-service','/graph')]),
 ('graph-analysis','master-ai-service',['python','/graph-tests/test_analysis.py','-q'],[('graph-service/tests','/graph-tests'),('contracts','/contracts'),('knowledge','/knowledge')]),
 ('observability','master-ai-service',['python','/oteltests/test_observability.py'],[('observability/tests','/oteltests'),('ai-service/tests','/app/tests'),('contracts','/contracts'),('knowledge','/knowledge')]),
]

def run(suite):
 name,image,args,mounts=suite
 if selected and name not in selected:
  return next(result for result in previous if result['suite']==name)
 cmd=['docker','run','--rm','--network','master_default','-e','APP_OTEL_ENABLED='+('true' if name=='observability' else 'false')]
 cmd+=['--mount',f'type=bind,source={logs},target=/evidence']
 for source,target in mounts:cmd+=['--mount',f'type=bind,source={root/source},target={target},readonly']
 completed=subprocess.run(cmd+[image,*args],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 text=completed.stdout.decode('utf8',errors='replace');(logs/(name+'.log')).write_text(text,encoding='utf8')
 count=re.search(r'Ran (\d+) tests?',text) or re.search(r'(\d+) passed',text)
 result={'suite':name,'exitCode':completed.returncode,'tests':int(count.group(1)) if count else None}
 print(json.dumps(result),flush=True)
 if completed.returncode:print(text[-3000:],flush=True)
 return result

with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(run,suites))
(out/'regression-results.json').write_text(json.dumps(results,indent=2),encoding='utf8')
raise SystemExit(int(any(r['exitCode'] for r in results)))
