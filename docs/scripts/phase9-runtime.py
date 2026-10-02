"""Runtime boundary, immutable benchmark and actual Chrome regression evidence."""
from pathlib import Path
import ast
import hashlib
import json
import subprocess
root=Path(__file__).resolve().parents[2];dest=root/'docs/phase9-evidence'
container=json.loads(subprocess.check_output(['docker','inspect','master-mcp-server-1']))[0]
env=[e.split('=',1)[0] for e in container['Config']['Env']]
assert not any('DB_' in k or 'PASSWORD' in k or k.startswith('EVALUATION_') for k in env)
assert not container['Mounts'],container['Mounts']
assert container['Config']['User']=='10001'
assert container['HostConfig']['ReadonlyRootfs']
assert container['HostConfig']['PortBindings']['8020/tcp'][0]['HostIp']=='127.0.0.1'
for file in (root/'mcp-server/app').glob('*.py'):
    code=file.read_text(encoding='utf-8');tree=ast.parse(code)
    imports=[n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
    imports += [a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names]
    assert not any(name and name.split('.')[0] in {'psycopg','psycopg2','sqlalchemy','subprocess','sqlite3'} for name in imports)
source_hash=hashlib.sha256((root/'ai-service/app/analysis_models.py').read_bytes()).hexdigest()
copied_hash=subprocess.check_output(['docker','exec','master-mcp-server-1','python','-c',"import hashlib;print(hashlib.sha256(open('/gateway/app/contracts/analysis_models.py','rb').read()).hexdigest())"]).decode().strip()
assert source_hash==copied_hash
boundary={'result':'PASS','noDatabaseCredentials':True,'noMounts':True,'noDatabaseOrShellImports':True,'user':10001,'readOnlyRoot':True,'loopbackOnly':True,'analysisSchemaExactSourceHash':source_hash}
(dest/'gateway-boundary.json').write_text(json.dumps(boundary,indent=2))
# Prior experiment verification reads its frozen inputs and writes only Phase 9 outputs.
source=(root/'docs/scripts/phase8-verify.py').read_text(encoding='utf-8')
source=source.replace("(dest/'api-edge-cases.json').write_text", "(root/'docs/phase9-evidence/retrieval-api-edge-cases.json').write_text")
source=source.replace("(dest/'experiment-verification.json').write_text", "(root/'docs/phase9-evidence/phase8-experiment-verification.json').write_text")
exec(compile(source,'phase8-verify.py','exec'),{'__file__':str(root/'docs/scripts/phase8-verify.py'),'__name__':'__main__'})
source=(root/'docs/scripts/phase8-browser-regression.py').read_text(encoding='utf-8')
source=source.replace("dest=root/'docs/phase8-evidence'","dest=root/'docs/phase9-evidence'")
exec(compile(source,'phase8-browser-regression.py','exec'),{'__file__':str(root/'docs/scripts/phase8-browser-regression.py'),'__name__':'__main__'})
print('PASS runtime boundaries, Phase 8 metrics and actual Chrome',flush=True)
