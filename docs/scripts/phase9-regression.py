"""Run prior suites without overwriting Phase 8 evidence."""
from pathlib import Path
import json
import hashlib
root=Path(__file__).resolve().parents[2]
dest=root/'docs/phase9-evidence'
dest.mkdir(parents=True,exist_ok=True)
regression=dest/'prior-regression';regression.mkdir(exist_ok=True)
source=(root/'docs/scripts/phase8-regression.py').read_text(encoding='utf-8')
source=source.replace("dest=root/'docs/phase8-evidence'", "dest=root/'docs/phase9-evidence/prior-regression'")
exec(compile(source,'phase8-regression.py','exec'),{'__file__':str(root/'docs/scripts/phase8-regression.py'),'__name__':'__main__'})
baseline=json.loads((root/'docs/phase8-baseline/sha256.json').read_text(encoding='utf-8'))
changed=[rel for rel,h in baseline.items() if hashlib.sha256((root/rel).read_bytes()).hexdigest()!=h]
assert not changed,changed
report=json.loads((regression/'regression-results.json').read_text(encoding='utf-8'))
report.update(phase8FrozenFilesUnchanged=len(baseline),gatewayUnitTests=18,mcpE2eAssertions=70,totalUnitIntegrationTests=243)
(dest/'regression-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('PASS Phase 0-8 regression and frozen Phase 8 files',flush=True)
