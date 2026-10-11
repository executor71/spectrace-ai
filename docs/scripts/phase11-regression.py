"""Reuse Phase 0-10 assertions, preserving their archived evidence and sources."""
from pathlib import Path
import json,hashlib,shutil
root=Path(__file__).resolve().parents[2];dest=root/'docs/phase11-evidence';dest.mkdir(exist_ok=True)
phase11={'ai-service/app/main.py','frontend/src/Requirements.tsx','frontend/vite.config.ts',
 'mcp-server/app/schemas.py','mcp-server/app/clients.py','mcp-server/app/tools.py','mcp-server/app/server.py',
 'observability/python/workflow_otel/__init__.py'}
baseline=json.loads((root/'docs/phase10-baseline/sha256.json').read_text())
changed={p for p,h in baseline.items() if hashlib.sha256((root/p).read_bytes()).hexdigest()!=h}
assert changed==phase11,changed
(dest/'phase10-source-audit.json').write_text(json.dumps({'frozenFiles':len(baseline),'changedFiles':sorted(changed),'unchangedFiles':len(baseline)-len(changed)},indent=2))
# Legacy behavior checks stay unchanged. Discovery now expects 8 instead of 5 tools.
testdir=dest/'legacy-mcp-tests';shutil.copytree(root/'mcp-server/tests',testdir,dirs_exist_ok=True)
p=testdir/'e2e.py';text=p.read_text(encoding='utf8')
text=text.replace('"five strict tools", len(listing.tools) == 5','"eight strict tools", len(listing.tools) == 8').replace('list_tools()).tools)==5','list_tools()).tools)==8')
p.write_text(text,encoding='utf8')
source=(root/'docs/scripts/phase10-regression.py').read_text(encoding='utf8')
source=source.replace("baseline=json.loads", "allowed |= PHASE11_ALLOWED\nbaseline=json.loads",1)
source=source.replace('assert changed==allowed,changed','assert changed==(allowed & set(baseline)),changed')
source=source.replace('phase10-evidence','phase11-evidence').replace('compose.phase10-test.yaml','compose.phase11-test.yaml')
source=source.replace("root}/mcp-server/tests", "root}/docs/phase11-evidence/legacy-mcp-tests")
exec(compile(source,'phase10-regression.py','exec'),{'__file__':str(root/'docs/scripts/phase10-regression.py'),'__name__':'__main__','PHASE11_ALLOWED':phase11})
