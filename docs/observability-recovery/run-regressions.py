"""Reuse existing suites, preserve previous evidence, test exporters offline."""
import concurrent.futures
import importlib.util
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
ORIGINAL=ROOT/'docs/workflow-logging'


def python_suites():
    spec=importlib.util.spec_from_file_location('prior_regression',ORIGINAL/'run-regression.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.OUT=OUT
    for suite in module.SUITES:
        if suite[0]=='mcp':
            suite[3].extend((path.relative_to(ROOT).as_posix(),'/gateway/app/'+path.name) for path in (ROOT/'mcp-server/app').glob('*.py'))
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(module.run,module.SUITES))
    (OUT/'python-regression-results.json').write_text(json.dumps({'suites':results,'rawLogs':str(module.LOGS),'realQwenCalls':0},indent=2))
    raise SystemExit(int(any(row['exitCode'] for row in results)))


def existing(name):
    source=(ORIGINAL/name).read_text(encoding='utf8')
    source=source.replace("OUT = ROOT / 'docs/workflow-logging'","OUT = ROOT / 'docs/observability-recovery'")
    source=source.replace("str(OUT / 'compose.test.yaml')","str(ROOT / 'docs/workflow-logging/compose.test.yaml')")
    source=source.replace("str(OUT / 'compose.evaluation-test.yaml')","str(ROOT / 'docs/workflow-logging/compose.evaluation-test.yaml')")
    if name=='run-java-regression.py':
        source=source.replace('\ntry:\n',"\ncompose += ['-f', str(OUT / 'compose.outage-test.yaml')]\ntry:\n",1)
    exec(compile(source,name,'exec'),{'__file__':str(ORIGINAL/name),'__name__':'__main__'})


if __name__=='__main__':
    if sys.argv[1]=='python':python_suites()
    existing({'java':'run-java-regression.py','extra':'run-extra-regression.py','evaluation-db':'run-evaluation-db-regression.py'}[sys.argv[1]])
