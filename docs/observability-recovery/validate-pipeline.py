"""Validate real SDK -> receiver counters -> stored/queryable trace, not UI alone."""
import json
from pathlib import Path
import subprocess
import time
from urllib.request import build_opener, ProxyHandler

OUT=Path(__file__).resolve().parent
http=build_opener(ProxyHandler({}))


def metrics():
    code="from urllib.request import urlopen\nprint(urlopen('http://127.0.0.1:8888/metrics',timeout=3).read().decode())"
    return subprocess.check_output(['docker','run','-i','--rm','--network','container:master-otel-collector-1','master-ai-service','python','-'],input=code.encode()).decode('utf8')


def query(tid):
    with http.open('http://127.0.0.1:16686/api/traces/'+tid,timeout=5) as response:return json.load(response)


before=metrics()
raw=subprocess.check_output(['docker','compose','exec','-T','ai-service','python','-'],input=(OUT/'trace-probe.py').read_bytes())
probe=json.loads(raw);print(json.dumps(probe),flush=True)
for attempt in range(25):
    try:
        result=query(probe['traceId'])
        if result.get('data'):break
    except Exception:pass
    time.sleep(1)
else:raise RuntimeError('The emitted trace was not stored/queryable')
after=metrics()
(OUT/'collector-validation.log').write_text('BEFORE SDK PROBE\n'+before+'\nSDK EMITTED\n'+json.dumps(probe)+'\nAFTER STORED QUERY\n'+after,encoding='utf8')
(OUT/'minimal-probe.json').write_text(json.dumps(probe,indent=2),encoding='utf8')
(OUT/'jaeger-query-result.json').write_text(json.dumps(result,indent=2),encoding='utf8')
traces=result['data'];assert any(trace['traceID']==probe['traceId'] for trace in traces)
assert any(process['serviceName']==probe['serviceName'] for trace in traces for process in trace['processes'].values())
assert any(span['operationName']=='recovery.minimum' for trace in traces for span in trace['spans'])
print('PASS: SDK span stored and queried by its actual Trace ID',flush=True)
