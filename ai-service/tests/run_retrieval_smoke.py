"""Real HTTP search checks; expectations stay outside the RAG corpus."""
import json
import os
import time
import urllib.request
from pathlib import Path
from uuid import UUID,uuid5

root=Path(__file__).resolve().parents[2]
evidence=root/'docs/phase2-evidence'
manifest=json.loads((root/'knowledge/manifest.json').read_text(encoding='utf-8'))
namespace=UUID('55a34fc8-9a8e-4a01-8f23-c82a21d00002')
documents={str(uuid5(namespace,f"{d['key']}:{d['version']}")):d for d in manifest['documents']}
cases=json.loads((root/'ai-service/tests/fixtures/retrieval_cases.json').read_text(encoding='utf-8'))
results=[]
for number,case in enumerate(cases,1):
    start=time.perf_counter()
    request=urllib.request.Request(os.getenv('SEARCH_BASE_URL','http://localhost:8000').rstrip('/')+'/internal/v1/search',
        data=json.dumps({'query':case['query'],'topK':5}).encode(),headers={'Content-Type':'application/json'})
    # Initial local model load is a known long task; subsequent requests are timed independently.
    with urllib.request.urlopen(request,timeout=180) as response:
        hits=json.load(response)
        assert response.status==200 and len(hits)==5
    assert all({'documentId','chunkId','documentType','section','contentSnippet','score'} <= h.keys() for h in hits)
    assert all(h['documentId'] in documents for h in hits)
    assert all(hits[i]['score'] >= hits[i+1]['score'] for i in range(len(hits)-1))
    hit_keys=[documents[h['documentId']]['key'] for h in hits]
    for hit in hits:
        hit['documentKey']=documents[hit['documentId']]['key']
    matched=sorted(set(hit_keys)&set(case['expectedDocumentKeys']))
    row={'number':number,'query':case['query'],'expectedDocumentKeys':case['expectedDocumentKeys'],
         'included':bool(matched),'matchedDocumentKeys':matched,'hits':hits,'elapsed_seconds':round(time.perf_counter()-start,3)}
    results.append(row)
    print(json.dumps({'number':number,'included':bool(matched),'top5':[(h['documentKey'],h['section'],round(h['score'],4)) for h in hits],'elapsed_seconds':row['elapsed_seconds']},ensure_ascii=False),flush=True)
    (evidence/'retrieval-smoke-latest.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print(f'HIT@5={sum(r["included"] for r in results)}/{len(results)}',flush=True)
# Report every result even if a query misses; never tune expectations after running.

if not all(row["included"] for row in results):
    raise SystemExit("One or more retrieval smoke cases missed the expected documents")
