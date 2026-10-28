"""Remaining existing retrieval metrics, frontend, frozen RAG and role checks."""
import json
from pathlib import Path
import re
import subprocess
import tempfile
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/workflow-logging'
LOGS = Path(tempfile.mkdtemp(prefix='spectrace-workflow-extra-'))
results = []


def run(name, command, cwd=None, data=None):
    result = subprocess.run(command, cwd=cwd or ROOT, input=data, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (LOGS / (name + '.log')).write_bytes(result.stdout)
    assert result.returncode == 0, (name, str(LOGS))
    text = result.stdout.decode('utf8', errors='replace')
    count = re.search(r'Ran (\d+) tests?', text) or re.search(r'# tests (\d+)', text)
    results.append({'suite': name, 'exitCode': result.returncode, 'tests': int(count[1]) if count else None})


run('retrieval-metrics', ['docker', 'run', '--rm', '--mount', f'type=bind,source={ROOT / "evaluation-service/retrieval_eval"},target=/evaluation/retrieval_eval,readonly',
                        '--mount', f'type=bind,source={ROOT / "evaluation-service/retrieval_tests"},target=/tests,readonly',
                        'master-evaluation-service', 'python', '-m', 'unittest', 'discover', '-s', '/tests', '-q'])
run('frontend-unit', ['node', '--test', 'frontend/tests/requirementExamples.test.mjs'])
run('frontend-build', ['npm.cmd', '--prefix', 'frontend', 'run', 'build', '--', '--outDir', str(LOGS / 'frontend-dist')])
cases = json.loads((ROOT / 'docs/phase2-evidence/top5-results.json').read_text(encoding='utf8'))
for case in cases:
    request = Request('http://localhost:8000/internal/v1/search', data=json.dumps({'query': case['query'], 'topK': 5}).encode(), headers={'Content-Type': 'application/json'})
    with urlopen(request, timeout=120) as response:
        hits = json.load(response)
    assert [hit['chunkId'] for hit in hits] == [hit['chunkId'] for hit in case['hits']]
    assert all(abs(a['score'] - b['score']) < 1e-6 for a, b in zip(hits, case['hits']))
results.append({'suite': 'frozen-rag-top5-and-scores', 'queries': len(cases), 'exitCode': 0})
sql = """SELECT json_build_object(
 'appCanReadGroundTruth',has_schema_privilege('app_user','evaluation','USAGE'),
 'ragCanReadGroundTruth',has_schema_privilege('rag_reader','evaluation','USAGE'),
 'appCanRecordEvaluation',has_function_privilege('app_user','evaluation.record_run(uuid,uuid,text,jsonb,jsonb)','EXECUTE'),
 'ragCanRecordEvaluation',has_function_privilege('rag_reader','evaluation.record_run(uuid,uuid,text,jsonb,jsonb)','EXECUTE'));
"""
raw = subprocess.check_output(['docker', 'compose', 'exec', '-T', 'postgres', 'psql', '-U', 'postgres', '-d', 'legacy_assistant', '-At'], input=sql.encode())
roles = json.loads(raw)
assert not any(roles.values())
results.append({'suite': 'database-role-boundaries', 'exitCode': 0, **roles})
run('frozen-source-contracts', ['git', 'diff', '--exit-code', '--', 'contracts', 'knowledge', 'ai-service/app/llm_provider.py',
                              'backend/src/main/resources/db/migration', 'evaluation-service/datasets'])
(OUT / 'extra-regression-results.json').write_text(json.dumps({'suites': results, 'rawLogs': str(LOGS), 'realModelCalls': 0}, indent=2), encoding='utf8')
print(json.dumps(results), flush=True)
