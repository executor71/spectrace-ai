from pathlib import Path
import hashlib,json,subprocess,urllib.request,socket
root=Path(__file__).resolve().parents[2];dest=root/'docs/phase10-evidence'
def get(url):
    with urllib.request.urlopen(url,timeout=15) as response:return json.load(response)
health=[]
for port,path in [(8080,'/actuator/health'),(8000,'/health'),(8090,'/health'),(8010,'/health'),(8020,'/health')]:
    body=get(f'http://127.0.0.1:{port}{path}');assert body['status']=='UP';health.append({'port':port,'status':'UP'})
assert get('http://127.0.0.1:13133')['status']=='Server available'
services=get('http://127.0.0.1:16686/api/services')['data']
assert {'legacy-assistant-backend','legacy-assistant-ai','legacy-assistant-mcp','legacy-assistant-retrieval','legacy-assistant-evaluation'}<=set(services)
for port in [14317,14318]:
    with socket.create_connection(('127.0.0.1',port),timeout=5):pass
(dest/'service-health.json').write_text(json.dumps({'result':'PASS','services':health,'collector':'UP','jaeger':'UP','jaegerServices':services,'otlpReceivers':{'grpc':14317,'http':14318}},indent=2))
logs=[]
for service in ['backend','ai-service','retrieval-service','evaluation-service','mcp-server']:
    text=subprocess.run(['docker','logs','master-'+service+'-1'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,check=True).stdout.decode()
    for line in text.splitlines():
        if '{' not in line:continue
        try:row=json.loads(line[line.index('{'):])
        except ValueError:continue
        if isinstance(row,dict) and 'event' in row and 'traceId' in row:
            assert {'timestamp','service','level','traceId','spanId','requestId','event','durationMs'}<=set(row)
            logs.append(row)
assert logs
(dest/'correlated-logs.json').write_text(json.dumps(logs,ensure_ascii=False,indent=2),encoding='utf-8')
real=json.loads((dest/'real-analysis.json').read_text());selected=[r for r in logs if r['traceId']==real['traceId'] and r['requestId']]
assert {'legacy-assistant-backend','legacy-assistant-ai'}<={r['service'] for r in selected}
llm=next(r for r in selected if r['event']=='llm.generate')
assert any(r['service']=='legacy-assistant-backend' and r['requestId']==llm['requestId'] for r in selected)
(dest/'log-correlation-check.json').write_text(json.dumps({'result':'PASS','records':len(logs),'realAnalysisTraceId':real['traceId'],'sharedRequestId':llm['requestId'],'services':['legacy-assistant-backend','legacy-assistant-ai']},indent=2))
assert not any(v in json.dumps(logs) for v in ['SECRET_PROMPT','SECRET_REASONING','SECRET_USER_SENTINEL','SECRET_AUTH_SENTINEL'])
baseline=json.loads((root/'docs/phase9-baseline/sha256.json').read_text());changed=[rel for rel,h in baseline.items() if hashlib.sha256((root/rel).read_bytes()).hexdigest()!=h]
expected=json.loads((dest/'source-change-audit.json').read_text())['changedTracingOnlyFiles'];assert sorted(changed)==expected
# Original Phase 8 benchmark data and deterministic metric computations remain unchanged.
source=(root/'docs/scripts/phase8-verify.py').read_text(encoding='utf-8')
source=source.replace("(dest/'api-edge-cases.json').write_text","(root/'docs/phase10-evidence/phase8-api-edge-cases.json').write_text")
source=source.replace("(dest/'experiment-verification.json').write_text","(root/'docs/phase10-evidence/phase8-experiment-verification.json').write_text")
exec(compile(source,'phase8-verify.py','exec'),{'__file__':str(root/'docs/scripts/phase8-verify.py'),'__name__':'__main__'})
print('PASS health, receiver ports, log correlation, frozen evidence and Phase 8 replay')
