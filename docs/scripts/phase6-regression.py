from pathlib import Path
import hashlib,json,subprocess,urllib.request,xml.etree.ElementTree as ET
root=Path(__file__).resolve().parents[2];dest=root/'docs/phase6-evidence'
baseline=json.loads((root/'docs/phase5-baseline/sha256.json').read_text())
allowed={'compose.yaml','frontend/src/Requirements.tsx','frontend/src/style.css','frontend/vite.config.ts'}
changed=[name for name,h in baseline.items() if hashlib.sha256((root/name).read_bytes()).hexdigest()!=h]
assert set(changed)==allowed,changed
def run(args,name,data=None):
    result=subprocess.run(args,input=data,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);(dest/name).write_bytes(result.stdout)
    assert result.returncode==0,(name,result.stdout[-2000:]);return result.stdout.decode()
run(['docker','cp',str(root/'ai-service/tests')+'/.','master-ai-service-1:/app/tests'],'python-provision.log')
run(['docker','exec','master-ai-service-1','python','-m','unittest','discover','-s','tests','-v'],'python-tests.log')
assert 'Ran 61 tests' in (dest/'python-tests.log').read_text()
health=[]
for url in ['http://localhost:8080/actuator/health','http://localhost:8000/health','http://localhost:8090/health']:
    with urllib.request.urlopen(url,timeout=15) as response:body=json.load(response);assert body['status']=='UP';health.append({'url':url,'body':body})
retrieval=[]
for case in json.loads((root/'docs/phase2-evidence/top5-results.json').read_text(encoding='utf-8')):
    request=urllib.request.Request('http://localhost:8000/internal/v1/search',data=json.dumps({'query':case['query'],'topK':5}).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=60) as response:hits=json.load(response)
    assert [h['chunkId'] for h in hits]==[h['chunkId'] for h in case['hits']]
    assert all(abs(a['score']-b['score'])<1e-6 for a,b in zip(hits,case['hits']))
    retrieval.append({'number':case['number'],'sameTop5AndScores':True})
    print('PASS Phase 2 frozen query',case['number'],flush=True)
suites=[ET.parse(p).getroot().attrib for p in (dest/'backend-tests').glob('TEST-*.xml')]
assert sum(int(s['tests']) for s in suites)==55 and all(int(s['failures'])+int(s['errors'])+int(s['skipped'])==0 for s in suites)
# Phase 5 persisted approved/rejected objects must remain byte-for-byte equivalent as JSON.
for name in ['approve-response.json','reject-response.json']:
    original=json.loads((root/'docs/phase5-evidence'/name).read_text(encoding='utf-8'))
    with urllib.request.urlopen('http://localhost:8080/api/requirements/'+original['requirementId']+'/test-cases') as response:batch=json.load(response)
    current=next(c for c in batch['testCases'] if c['testCaseId']==original['testCaseId']);assert current==original
result={'result':'PASS','baselineFiles':len(baseline),'unchangedFiles':len(baseline)-len(changed),'allowedChangedFiles':changed,'health':health,'backendTests':[{k:s[k] for k in ['name','tests','failures','errors','skipped']} for s in suites],
        'pythonTests':61,'phase2Retrieval':retrieval,'phase5ApprovedRejectedPreserved':True}
(dest/'regression-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print('PASS Phase 0-5 regression')
