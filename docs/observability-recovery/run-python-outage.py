"""Re-run existing fake-business and telemetry tests with no network/exporter."""
import importlib.util
import json
from pathlib import Path
import subprocess

OUT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('outage_suite',OUT.parent/'workflow-logging/run-regression.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
original=subprocess.run
def unreachable(command,*args,**kwargs):
    if command[:2]==['docker','run']:
        command=list(command)
        command[command.index('master_default')]='none'
        command=[value.replace('APP_OTEL_ENABLED=false','APP_OTEL_ENABLED=true') for value in command]
        command[3:3]=['-e','OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://127.0.0.1:1/v1/traces']
    return original(command,*args,**kwargs)
subprocess.run=unreachable
try:results=[module.run(suite) for suite in module.SUITES if suite[0] in {'ai','observability'}]
finally:subprocess.run=original
report={'suites':results,'network':'none','telemetryEnabled':True,'endpoint':'http://127.0.0.1:1/v1/traces',
        'realQwenCalls':0,'rawLogs':str(module.LOGS),'duplicateOfMainSuites':True}
(OUT/'python-outage-results.json').write_text(json.dumps(report,indent=2))
raise SystemExit(int(any(row['exitCode'] for row in results)))
