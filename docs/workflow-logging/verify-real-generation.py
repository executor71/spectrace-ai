"""One real TC generation against an existing grounded test fixture; no DB write."""
import json
from pathlib import Path
import re
import subprocess
from urllib.request import Request, urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/workflow-logging'
rid = json.loads((OUT / 'live-results.json').read_text())['requirementId']
analysis = json.loads((ROOT / 'ai-service/tests/fixtures/test-case-analysis.json').read_text(encoding='utf8'))
analysis['requirementId'] = rid
run_id = str(uuid4())
body = {'requirementId': rid, 'title': '대여 승인', 'description': '같은 부서 직원의 대여 승인, 자기 승인 금지', 'analysis': analysis}
request = Request('http://localhost:8000/internal/v1/test-cases/generate',
                  data=json.dumps(body, ensure_ascii=False).encode(),
                  headers={'Content-Type': 'application/json', 'x-workflow-run-id': run_id})
print(json.dumps({'runId': run_id, 'realGenerationRequests': 1}), flush=True)
with urlopen(request, timeout=630) as response:
    result = json.load(response)
raw = subprocess.check_output(['docker', 'compose', 'logs', '--no-color', '--no-log-prefix', 'ai-service']).decode('utf8')
lines = [line for line in raw.splitlines() if f'runId={run_id}' in line and re.search(r'event=[A-Z_]+ ', line)]
(OUT / 'real-generation.log').write_text('\n'.join(lines) + '\n', encoding='utf8')
report = {'runId': run_id, 'requirementId': rid, 'testCases': len(result['testCases']), 'llmCalls': result['llmCalls'],
          'source': 'existing grounded analysis fixture (unchanged)', 'persisted': False,
          'modelStarts': sum('event=LLM_STARTED ' in line for line in lines),
          'modelCompletions': sum('event=LLM_COMPLETED ' in line for line in lines),
          'traceIds': sorted(set(re.findall(r'traceId=([0-9a-f]{32})', '\n'.join(lines))))}
(OUT / 'real-generation-results.json').write_text(json.dumps(report, indent=2), encoding='utf8')
assert report['modelStarts'] == report['modelCompletions'] == report['llmCalls'] >= 1
assert any(f'testCases={report["testCases"]}' in line for line in lines)
assert report['testCases'] > 0
assert not any('event=RESULT_SAVED' in line for line in lines)
print(json.dumps(report), flush=True)
