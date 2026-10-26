"""Provision unchanged frozen evaluation data in the isolated test DB only."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

root=Path(__file__).resolve().parents[2]
script=root/'docs/scripts/phase6-seed.py'
# Reuse the existing hash-checking provisioner, replacing only the test project name.
source=script.read_text(encoding='utf8').replace("'legacy-phase6-tests'", "'policy-extension-tests'")
sys.argv=[str(script),'--test']
exec(compile(source,str(script),'exec'),{'__file__':str(script),'__name__':'__main__'})
command=['docker','run','--rm','--network','policy-extension-tests_default','-e','APP_OTEL_ENABLED=false',
    '-e','EVALUATION_DB_HOST=postgres-test','-e','EVALUATION_DB_NAME=legacy_assistant_test',
    '-e','EVALUATION_DB_USER=evaluation_reader','-e','EVALUATION_DB_PASSWORD=test_evaluation_only',
    '-e','TEST_MIGRATION_PASSWORD=test_migration_only','--mount',f'type=bind,source={root/"evaluation-service/tests"},target=/app/tests,readonly',
    'master-evaluation-service','python','-m','unittest','discover','-s','/app/tests','-p','test_database.py','-q']
result=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
text=result.stdout.decode('utf8',errors='replace')
(Path(tempfile.gettempdir())/'spectrace-policy-extension/evaluation-database.log').write_text(text,encoding='utf8')
print(text[-2400:])
(root/'docs/testcase-policy-extension/evaluation-db-result.json').write_text(json.dumps({'exitCode':result.returncode,'environment':'isolated policy-extension-tests DB','frozenDatasetModified':False}),encoding='utf8')
raise SystemExit(result.returncode)
