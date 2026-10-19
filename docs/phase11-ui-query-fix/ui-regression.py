import subprocess,json,concurrent.futures
from pathlib import Path
r=Path('D:/MASTER과정');out=Path('ui-investigation').resolve()
def mount(a,b):return ['--mount',f'type=bind,source={a},target={b},readonly']
suites=[('ai','master-ai-service',[('ai-service/tests','/app/tests')],['python','-m','unittest','discover','-s','/app/tests','-v']),('evaluation','master-evaluation-service',[('evaluation-service/tests','/app/tests')],['python','-m','unittest','discover','-s','/app/tests','-v']),('retrieval','master-retrieval-service',[('retrieval-service/tests','/app/tests')],['python','-m','unittest','discover','-s','/app/tests','-v']),('mcp','master-mcp-server',[('mcp-server/tests','/app/tests')],['python','-m','unittest','discover','-s','/app/tests','-v']),('graph','master-graph-service',[('graph-service','/graph'),('docs/phase11-evidence','/evidence')],['python','-m','pytest','/graph/tests/test_projection.py','-q','-p','no:cacheprovider']),('graph-analysis','master-ai-service',[('graph-service/tests','/graph-tests'),('docs/phase11-evidence','/evidence')],['python','/graph-tests/test_analysis.py','-v']),('observability','master-ai-service',[('ai-service/tests','/app/tests'),('observability/tests','/otel-tests')],['python','/otel-tests/test_observability.py','-v'])]
def run(s):
 name,image,mounts,cmd=s;args=['docker','run','--rm','--network','none','-e','PYTHONDONTWRITEBYTECODE=1','-e','OTEL_SDK_DISABLED=true']
 for a,b in mounts:args+=mount(r/a,b)
 p=subprocess.run(args+[image,*cmd],stdout=subprocess.PIPE,stderr=subprocess.STDOUT);(out/(name+'-tests.log')).write_bytes(p.stdout);return {'suite':name,'exitCode':p.returncode,'tail':p.stdout.decode(errors='replace')[-700:]}
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(run,suites))
(out/'regression.json').write_text(json.dumps(results,indent=2),encoding='utf8');print(json.dumps(results,indent=2))
