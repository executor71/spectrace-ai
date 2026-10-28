"""Reuse existing frozen evaluation fixtures in a separate tmpfs database."""
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/workflow-logging'
LOGS = Path(tempfile.mkdtemp(prefix='spectrace-workflow-eval-'))
compose = ['docker', 'compose', '-p', 'spectrace-workflow-eval', '--project-directory', str(ROOT),
           '-f', str(ROOT / 'compose.test.yaml'), '-f', str(OUT / 'compose.evaluation-test.yaml')]
try:
    subprocess.run(compose + ['up', '-d', '--no-build', 'backend-init'], check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    for _ in range(45):
        result = subprocess.run(compose + ['exec', '-T', 'postgres-test', 'psql', '-U', 'postgres', '-d', 'legacy_assistant_test', '-At', '-c', 'SELECT count(*) FROM app.requirement'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if result.returncode == 0:
            break
        time.sleep(1)
    assert result.returncode == 0, 'Isolated database migrations unavailable'
    # Execute the original provisioner; change only the Compose project destination.
    source = (ROOT / 'docs/scripts/phase6-seed.py').read_text(encoding='utf8').replace("'legacy-phase6-tests'", "'spectrace-workflow-eval'")
    sys.argv = ['phase6-seed.py', '--test']
    exec(compile(source, 'phase6-seed.py', 'exec'), {'__file__': str(ROOT / 'docs/scripts/phase6-seed.py'), '__name__': '__main__'})
    command = ['docker', 'run', '--rm', '--network', 'spectrace-workflow-eval_default',
               '-e', 'APP_OTEL_ENABLED=false', '-e', 'EVALUATION_DB_HOST=postgres-test', '-e', 'EVALUATION_DB_NAME=legacy_assistant_test',
               '-e', 'EVALUATION_DB_USER=evaluation_reader', '-e', 'EVALUATION_DB_PASSWORD=test_evaluation_only', '-e', 'TEST_MIGRATION_PASSWORD=test_migration_only',
               '--mount', f'type=bind,source={ROOT / "evaluation-service/tests"},target=/evaluation/tests,readonly',
               'master-evaluation-service', 'python', '-m', 'unittest', 'discover', '-s', '/evaluation/tests', '-p', 'test_database.py', '-v']
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (LOGS / 'database-tests.log').write_bytes(result.stdout)
    count = re.search(r'Ran (\d+) tests?', result.stdout.decode('utf8'))
    report = {'exitCode': result.returncode, 'tests': int(count[1]) if count else None, 'rawLogs': str(LOGS), 'database': 'isolated tmpfs PostgreSQL', 'realModelCalls': 0}
    (OUT / 'evaluation-db-regression-results.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    print(json.dumps(report), flush=True)
    if result.returncode:
        print(result.stdout.decode('utf8', errors='replace')[-3000:])
finally:
    subprocess.run(compose + ['down', '-v'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
raise SystemExit(result.returncode)
