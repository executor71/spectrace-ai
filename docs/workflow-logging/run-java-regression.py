import json
import os
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/workflow-logging'
LOGS = Path(tempfile.mkdtemp(prefix='spectrace-workflow-java-'))
REPORTS = LOGS / 'reports'
REPORTS.mkdir()
env = dict(os.environ, WORKFLOW_TEST_REPORTS=str(REPORTS))
compose = ['docker', 'compose', '-p', 'spectrace-workflow-tests', '--project-directory', str(ROOT),
           '-f', str(ROOT / 'compose.test.yaml'), '-f', str(OUT / 'compose.test.yaml')]
try:
    build = subprocess.run(compose + ['build', 'backend-test'], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (LOGS / 'build.log').write_bytes(build.stdout)
    if build.returncode:
        raise RuntimeError('Backend test image build failed; see ' + str(LOGS))
    result = subprocess.run(compose + ['up', '--no-build', '--abort-on-container-exit', '--exit-code-from', 'backend-test', 'backend-test'],
                            env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (LOGS / 'maven.log').write_bytes(result.stdout)
    totals = dict(tests=0, failures=0, errors=0, skipped=0)
    for path in REPORTS.glob('TEST-*.xml'):
        suite = ET.parse(path).getroot()
        for key in totals:
            totals[key] += int(suite.attrib.get(key, 0))
    report = dict(exitCode=result.returncode, **totals, rawLogs=str(LOGS), database='isolated tmpfs PostgreSQL')
    (OUT / 'java-regression-results.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    print(json.dumps(report), flush=True)
    if result.returncode:
        print(result.stdout.decode('utf8', errors='replace')[-6000:], flush=True)
finally:
    subprocess.run(compose + ['down', '-v'], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
raise SystemExit(result.returncode)
