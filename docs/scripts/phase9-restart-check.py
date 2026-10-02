from pathlib import Path
import json,subprocess,time,urllib.request,hashlib
root=Path(__file__).resolve().parents[2];dest=root/'docs/phase9-evidence'
urls=['http://127.0.0.1:8080/actuator/health','http://127.0.0.1:8000/health','http://127.0.0.1:8090/health','http://127.0.0.1:8010/health','http://127.0.0.1:8020/health','http://127.0.0.1:5173']
health=[]
for url in urls:
    deadline=time.monotonic()+180
    while True:
        try:
            with urllib.request.urlopen(url,timeout=15) as response:
                raw=response.read();assert response.status==200
                if '5173' not in url:assert json.loads(raw)['status']=='UP'
            health.append({'url':url,'status':'UP'});break
        except Exception:
            if time.monotonic()>deadline:raise
            time.sleep(3)
    print('UP',url,flush=True)
code="""
import asyncio,json
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
async def main():
 async with streamablehttp_client('http://127.0.0.1:8020/mcp/') as (r,w,_):
  async with ClientSession(r,w) as s:
   await s.initialize();assert len((await s.list_tools()).tools)==5
   result=await s.call_tool('analyze_requirement',{'requirementId':'b5270f71-c92c-48ae-8530-8946f1cfce62'})
   assert not result.isError and result.structuredContent['analysisSource']=='SAVED'
   print(json.dumps({'result':'PASS','reconnected':True,'savedAnalysis':True}))
asyncio.run(main())
"""
client=json.loads(subprocess.check_output(['docker','exec','-i','master-mcp-server-1','python','-'],input=code.encode()))
baseline=json.loads((root/'docs/phase8-baseline/sha256.json').read_text(encoding='utf-8'))
assert all(hashlib.sha256((root/r).read_bytes()).hexdigest()==h for r,h in baseline.items())
containers=json.loads(subprocess.check_output(['docker','inspect']+['master-'+n+'-1' for n in ['postgres','ollama','backend','ai-service','evaluation-service','retrieval-service','frontend','mcp-server']]))
states=[{'name':c['Name'],'running':c['State']['Running'],'health':c['State'].get('Health',{}).get('Status')} for c in containers]
assert all(c['running'] and c['health'] in {None,'healthy'} for c in states),states
logs=subprocess.run(['docker','logs','master-mcp-server-1'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT).stdout.decode()
rows=[]
for line in logs.splitlines():
    if line.startswith('WARNING:gateway:'):line=line[len('WARNING:gateway:'):]
    try:row=json.loads(line)
    except ValueError:continue
    if isinstance(row,dict) and 'toolName' in row:
        assert set(row)=={'toolName','requestId','startedAt','durationMs','resultStatus','downstreamService','errorCode'}
        rows.append(row)
assert rows
(dest/'tool-call-logs.json').write_text(json.dumps(rows,indent=2))
report={'result':'PASS','health':health,'containers':states,'mcpAfterRestart':client,'phase8HashesUnchanged':len(baseline),'observabilityRecords':len(rows)}
(dest/'restart-results.json').write_text(json.dumps(report,indent=2));print('PASS Compose restart',flush=True)
