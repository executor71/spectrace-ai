"""Reuse existing behavioral suites; keep prior evidence intact."""
import concurrent.futures
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
original=OUT.parent


def python_suites():
    spec=importlib.util.spec_from_file_location('existing_regression',original/'run-regression.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.OUT=OUT
    for suite in module.SUITES:
        if suite[0]=='mcp':
            # Preserve the image's generated app/contracts package.
            suite[3].extend((path.relative_to(ROOT).as_posix(),'/gateway/app/'+path.name)
                            for path in (ROOT/'mcp-server/app').glob('*.py'))
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(module.run,module.SUITES))
    (OUT/'python-regression-results.json').write_text(json.dumps({'suites':results,'rawLogs':str(module.LOGS),'realModelCalls':0},indent=2),encoding='utf8')
    return int(any(result['exitCode'] for result in results))


def existing_script(name):
    source=(original/name).read_text(encoding='utf8')
    source=source.replace("OUT = ROOT / 'docs/workflow-logging'", "OUT = ROOT / 'docs/workflow-logging/video'")
    source=source.replace("str(OUT / 'compose.test.yaml')", "str(ROOT / 'docs/workflow-logging/compose.test.yaml')")
    source=source.replace("str(OUT / 'compose.evaluation-test.yaml')", "str(ROOT / 'docs/workflow-logging/compose.evaluation-test.yaml')")
    exec(compile(source,name,'exec'),{'__file__':str(original/name),'__name__':'__main__'})


if __name__=='__main__':
    mode=sys.argv[1] if len(sys.argv)>1 else 'python'
    if mode=='python': raise SystemExit(python_suites())
    existing_script({'java':'run-java-regression.py','extra':'run-extra-regression.py','evaluation-db':'run-evaluation-db-regression.py'}[mode])
