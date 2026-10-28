"""Run current Phase 0-15 behavioral suites without rewriting archived evidence."""
import concurrent.futures
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/workflow-logging'
LOGS = Path(tempfile.mkdtemp(prefix='spectrace-workflow-tests-'))
for name in ['source-facts.json', 'analysis-context.json']:
    shutil.copy2(ROOT / 'docs/phase11-evidence' / name, LOGS / name)

SUITES = [
    ('ai', 'master-ai-service', ['python', '-m', 'unittest', 'discover', '-s', '/app/tests', '-p', 'test_*.py', '-q'],
     [('ai-service/app', '/app/app'), ('ai-service/tests', '/app/tests'), ('ai-service', '/ai-service'), ('contracts', '/contracts'), ('knowledge', '/knowledge')]),
    ('retrieval', 'master-retrieval-service', ['python', '-m', 'unittest', 'discover', '-s', '/app/tests', '-p', 'test_*.py', '-q'],
     [('retrieval-service/tests', '/app/tests'), ('retrieval-service/retrieval', '/app/retrieval')]),
    ('evaluation-metrics', 'master-evaluation-service', ['python', '-m', 'unittest', 'discover', '-s', '/app/tests', '-p', 'test_metrics.py', '-q'], [('evaluation-service/tests', '/app/tests')]),
    ('evaluation-api', 'master-evaluation-service', ['python', '-m', 'unittest', 'discover', '-s', '/app/tests', '-p', 'test_api.py', '-q'], [('evaluation-service/tests', '/app/tests')]),
    ('mcp', 'master-mcp-server', ['python', '-m', 'unittest', 'discover', '-s', '/tests', '-p', 'test_*.py', '-q'], [('mcp-server/tests', '/tests')]),
    ('graph-projection', 'master-graph-service', ['python', '-m', 'pytest', '/graph/tests/test_projection.py', '/graph/tests/test_refresh.py', '-q', '-p', 'no:cacheprovider'], [('graph-service', '/graph')]),
    ('graph-analysis', 'master-ai-service', ['python', '/graph-tests/test_analysis.py', '-q'], [('graph-service/tests', '/graph-tests'), ('ai-service/app', '/app/app'), ('contracts', '/contracts'), ('knowledge', '/knowledge')]),
    ('observability', 'master-ai-service', ['python', '/oteltests/test_observability.py'], [('observability/tests', '/oteltests'), ('ai-service/app', '/app/app'), ('ai-service/tests', '/app/tests'), ('contracts', '/contracts'), ('knowledge', '/knowledge')]),
]


def run(suite):
    name, image, args, mounts = suite
    cmd = ['docker', 'run', '--rm', '--network', 'master_default', '-e', 'APP_OTEL_ENABLED=' + ('true' if name == 'observability' else 'false')]
    cmd += ['--mount', f'type=bind,source={LOGS},target=/evidence']
    mounts += [('observability/python', '/opt/observability')]
    for source, target in mounts:
        cmd += ['--mount', f'type=bind,source={ROOT / source},target={target},readonly']
    completed = subprocess.run(cmd + [image, *args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    text = completed.stdout.decode('utf8', errors='replace')
    (LOGS / (name + '.log')).write_text(text, encoding='utf8')
    count = re.search(r'Ran (\d+) tests?', text) or re.search(r'(\d+) passed', text)
    result = {'suite': name, 'exitCode': completed.returncode, 'tests': int(count[1]) if count else None}
    print(json.dumps(result), flush=True)
    if completed.returncode:
        print(text[-4000:], flush=True)
    return result


if __name__ == '__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(run, SUITES))
    report = {'suites': results, 'rawLogs': str(LOGS), 'realModelCalls': 0}
    (OUT / 'python-regression-results.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    raise SystemExit(int(any(result['exitCode'] for result in results)))
