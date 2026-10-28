"""Explicit manual verification: creates one synthetic requirement and calls Qwen.

Run once for the demo evidence. Existing requirements/results are not overwritten.
Only metadata and allow-listed summary lines are saved.
"""
import json
from pathlib import Path
import re
import subprocess
import time
from urllib.request import Request, urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/workflow-logging'
report = {'realAnalysisRequests': 0, 'realGenerationRequests': 0}


def api(path, body=None, port=8080, timeout=700):
    request = Request(f'http://localhost:{port}' + path,
                      data=None if body is None else json.dumps(body, ensure_ascii=False).encode(),
                      headers={'Content-Type': 'application/json'})
    with urlopen(request, timeout=timeout) as response:
        return json.load(response)


def save():
    (OUT / 'live-results.json').write_text(json.dumps(report, indent=2), encoding='utf8')


if __name__ == '__main__':
    assert api('/health', port=8000, timeout=10)['status'] == 'UP'
    policy = json.loads((ROOT / 'contracts/test-case-policy.json').read_text(encoding='utf8'))
    requirement = api('/api/requirements', {'title': '대여 승인 권한 및 자기 승인 금지',
                                           'description': policy['plans'][0]['confirmedCondition']})
    rid = requirement['id']
    report['requirementId'] = rid
    job = api(f'/api/requirements/{rid}/analysis-jobs', {})
    report['jobId'] = job['jobId']; report['realAnalysisRequests'] = 1
    save(); print(json.dumps(report), flush=True)
    started = time.monotonic(); previous = None
    while time.monotonic() - started < 720:
        job = api('/api/analysis-jobs/' + report['jobId'])
        state = (job['status'], job['stage'])
        if state != previous:
            print(json.dumps({'status': state[0], 'stage': state[1]}), flush=True); previous = state
        if state[0] in {'SUCCEEDED', 'FAILED', 'TIMED_OUT', 'CANCELLED'}:
            break
        time.sleep(1)
    report['jobStatus'] = job['status']
    save()
    assert job['status'] == 'SUCCEEDED', job.get('errorCode')
    analysis = api(f'/api/requirements/{rid}/analysis')
    report['analysis'] = {'conditions': len(analysis['confirmedConditions']), 'evidence': len(analysis['evidence'])}
    print(json.dumps(report['analysis']), flush=True)
    report['realGenerationRequests'] = 1; save()
    generated = api(f'/api/requirements/{rid}/test-cases/generate', {})
    report['generation'] = {'testCases': len(generated['testCases']), 'llmCalls': generated['llmCalls']}
    persisted = api(f'/api/requirements/{rid}/test-cases')
    assert len(persisted['testCases']) == len(generated['testCases'])
    report['generation']['persistedCountMatches'] = True
    save(); print(json.dumps(report['generation']), flush=True)
    # Read container stdout only; persist neither HTTP bodies nor model output.
    raw = subprocess.check_output(['docker', 'compose', 'logs', '--no-color', '--no-log-prefix', 'ai-service', 'backend']).decode('utf8')
    lines = [line for line in raw.splitlines() if f'requirementId={rid}' in line and re.search(r'event=[A-Z_]+ ', line)]
    (OUT / 'real-workflow.log').write_text('\n'.join(lines) + '\n', encoding='utf8')
    traces = sorted(set(re.findall(r'traceId=([0-9a-f]{32})', '\n'.join(lines))))
    report['traceIds'] = traces
    report['summaryLines'] = len(lines)
    report['checks'] = {'analysisModelStarts': sum('event=LLM_STARTED' in line and 'workflow=ANALYSIS ' in line for line in lines),
                        'generationModelStarts': sum('event=LLM_STARTED' in line and 'workflow=TEST_GENERATION ' in line for line in lines),
                        'committedResults': sum('event=RESULT_SAVED' in line for line in lines),
                        'jobCorrelation': all(f'jobId={report["jobId"]}' in line for line in lines if 'workflow=ANALYSIS ' in line)}
    save()
    assert report['checks']['analysisModelStarts'] >= 1
    # A real analysis can legitimately be held by the unchanged closed policy.
    # Use verify-real-generation.py for a supported, frozen analysis snapshot.
    assert report['checks']['generationModelStarts'] == generated['llmCalls']
    assert report['checks']['committedResults'] == 2
    assert report['checks']['jobCorrelation']
    assert generated['llmCalls'] == report['checks']['generationModelStarts']
    if generated['testCases']:
        assert any(f'testCases={len(generated["testCases"])}' in line for line in lines)
    print(json.dumps(report['checks']), flush=True)
