"""Verify final deployed correlation/commit logging on the already-held demo result.

No model call: the saved demo analysis has zero eligible policy candidates.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
from urllib.request import Request, urlopen

OUT = Path(__file__).resolve().parent
rid = json.loads((OUT / 'live-results.json').read_text())['requirementId']
since = datetime.now(timezone.utc).isoformat()


def api(path, body=None, port=8080):
    request = Request(f'http://localhost:{port}' + path, data=None if body is None else json.dumps(body).encode(),
                      headers={'Content-Type': 'application/json'})
    with urlopen(request, timeout=20) as response:
        return json.load(response)


assert api('/health', port=8000)['status'] == 'UP'
assert api('/actuator/health')['status'] == 'UP'
assert api(f'/api/requirements/{rid}/test-cases')['llmCalls'] == 0
result = api(f'/api/requirements/{rid}/test-cases/generate', {})
assert result['llmCalls'] == 0 and result['testCases'] == []
raw = subprocess.check_output(['docker', 'compose', 'logs', '--since', since, '--no-color', '--no-log-prefix', 'ai-service', 'backend']).decode('utf8')
lines = [line for line in raw.splitlines() if f'requirementId={rid}' in line and re.search(r'event=[A-Z_]+ ', line)]
rows = [dict(re.findall(r'\b([A-Za-z]+)=([^\s]+)', line)) for line in lines]
assert len(rows) == 8
assert len({row['runId'] for row in rows}) == len({row['traceId'] for row in rows}) == 1
assert all(row['jobId'] == '-' for row in rows)
assert not any(row['event'].startswith('LLM_') or row['event'].startswith('PROVIDER_') for row in rows)
backend = [row for row in rows if row['service'] == 'backend']
assert [row['event'] for row in backend] == ['RESULT_SAVED', 'WORKFLOW_COMPLETED']
assert all(row['persistence'] == 'COMMITTED' for row in backend)
(OUT / 'final-runtime-smoke.log').write_text('\n'.join(lines) + '\n', encoding='utf8')
report = {'result': 'PASS', 'aiHealth': 'UP', 'backendHealth': 'UP', 'summaryLines': len(rows),
          'realModelCalls': result['llmCalls'], 'runId': rows[0]['runId'], 'traceId': rows[0]['traceId'],
          'committedEventOrder': 'RESULT_SAVED -> WORKFLOW_COMPLETED', 'crossServiceCorrelation': 'PASS'}
(OUT / 'final-runtime-smoke.json').write_text(json.dumps(report, indent=2), encoding='utf8')
print(json.dumps(report))
