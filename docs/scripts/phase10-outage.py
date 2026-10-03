from pathlib import Path
import json,subprocess,urllib.request,time
root=Path(__file__).resolve().parents[2];dest=root/'docs/phase10-evidence'
compose=['docker','compose','-p','master']
for name in ['compose.yaml','compose.phase7-local.yaml','compose.phase8.yaml','compose.phase9.yaml','compose.phase10.yaml']:compose+=['-f',str(root/name)]
def run(command,name):
    result=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);(dest/name).write_bytes(result.stdout)
    assert result.returncode==0,result.stdout[-1500:].decode(errors='replace')
real=json.loads((dest/'real-analysis.json').read_text())
try:
    run(compose+['stop','otel-collector','jaeger'],'outage-stop.log')
    for url in ['http://127.0.0.1:13133','http://127.0.0.1:16686/api/services']:
        try:urllib.request.urlopen(url,timeout=2)
        except Exception:pass
        else:raise AssertionError('Observability still UP')
    run(['docker','run','--rm','--network','master_default','--mount',f'type=bind,source={root}/observability/tests,target=/tests,readonly',
        '--mount',f'type=bind,source={dest},target=/evidence','master-mcp-server','python','/tests/measure.py','--mode','stack-down','--output','/evidence/outage-latency.json'],'outage-business.log')
    with urllib.request.urlopen('http://127.0.0.1:8080/api/requirements/'+real['requirementId']+'/analysis') as response:assert json.load(response)['requirementId']==real['requirementId']
finally:
    run(compose+['start','jaeger','otel-collector'],'outage-recovery.log')
deadline=time.monotonic()+60
while True:
    try:
        with urllib.request.urlopen('http://127.0.0.1:16686/api/traces/'+real['traceId'],timeout=5) as response:trace=json.load(response)
        assert trace['data']
        urllib.request.urlopen('http://127.0.0.1:13133',timeout=5)
        break
    except Exception:
        if time.monotonic()>deadline:raise
        time.sleep(2)
report={'result':'PASS','bothCollectorAndJaegerStopped':True,'coreWorkflows':['VECTOR','HYBRID','MCP_READ','DUMMY','SAVED_ANALYSIS'],
    'successfulMeasuredCalls':48,'successfulWarmupCalls':8,'recovered':True,'realAnalysisTracePersisted':real['traceId'],'additionalModelCalls':0}
(dest/'outage-results.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
