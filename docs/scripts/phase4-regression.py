from pathlib import Path
import hashlib,json,time,urllib.request,xml.etree.ElementTree as ET,os
root=Path(__file__).resolve().parents[2];dest=root/'docs/phase4-evidence'
baseline=json.loads((root/'docs/phase3-baseline/sha256.json').read_text(encoding='utf-8'))
protected=[name for name in baseline if name.startswith(('knowledge/','docker/','ai-service/config/','backend/src/main/resources/db/migration/'))
    or name.startswith(('ai-service/app/analysis_', 'backend/src/main/java/com/example/legacyassistant/analysis/')) or name in ['ai-service/app/llm_provider.py','frontend/src/RequirementAnalysis.tsx','ai-service/app/vector_search.py','ai-service/app/search_api.py','ai-service/app/local_embedding.py','ai-service/app/embedding_contract.py','ai-service/app/knowledge.py','ai-service/app/seed_export.py','ai-service/requirements-embedding.txt','ai-service/tests/fixtures/retrieval_cases.json','docs/phase2-evidence/top5-results.json']]
for name in protected:assert hashlib.sha256((root/name).read_bytes()).hexdigest()==baseline[name],name
health=[]
for url in [os.getenv('API_BASE_URL','http://localhost:8080')+'/actuator/health',os.getenv('SEARCH_BASE_URL','http://localhost:8000')+'/health']:
    with urllib.request.urlopen(url,timeout=10) as response:
        body=json.load(response);assert response.status==200 and body['status']=='UP'
        health.append({'url':url,'status':response.status,'body':body})
original=json.loads((root/'docs/phase2-evidence/top5-results.json').read_text(encoding='utf-8'))
searches=[]
for case in original:
    start=time.perf_counter()
    request=urllib.request.Request(os.getenv('SEARCH_BASE_URL','http://localhost:8000')+'/internal/v1/search',data=json.dumps({'query':case['query'],'topK':5}).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=30) as response:hits=json.load(response)
    assert [h['chunkId'] for h in hits]==[h['chunkId'] for h in case['hits']]
    assert all(abs(a['score']-b['score'])<1e-6 for a,b in zip(hits,case['hits']))
    searches.append({'number':case['number'],'query':case['query'],'sameTop5':True,'included':case['included'],'elapsedSeconds':round(time.perf_counter()-start,3),'hits':hits})
    print('PASS frozen retrieval query',case['number'],flush=True)
summaries=[]
for path in (dest/'test-results').glob('TEST-*.xml'):
    suite=ET.parse(path).getroot();summaries.append({key:suite.attrib[key] for key in ['name','tests','failures','errors','skipped']})
assert len(summaries)==4 and sum(int(s['tests']) for s in summaries)==39,summaries
assert all(int(s['failures'])+int(s['errors'])+int(s['skipped'])==0 for s in summaries)
result={'result':'PASS','frozenFiles':protected,'health':health,'backendTests':summaries,'retrieval':searches}
(dest/'regression-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print('PASS baseline hashes, health, 8 identical Top-5 results, 39 backend tests',flush=True)
