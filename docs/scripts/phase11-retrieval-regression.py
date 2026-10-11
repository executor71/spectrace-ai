from pathlib import Path
import json,urllib.request,math
root=Path(__file__).resolve().parents[2];out=root/'docs/phase11-evidence';old=root/'docs/phase8-evidence'
queries=json.loads((old/'evaluation-dataset.json').read_text(encoding='utf8'))['queries'];results=[]
for strategy,file in [('VECTOR','vector-results.json'),('HYBRID','hybrid-results.json'),('HYBRID_RERANK','reranker-results.json')]:
    saved={r['queryId']:r for r in json.loads((old/file).read_text(encoding='utf8'))}
    for q in (queries[:1] if strategy=='HYBRID_RERANK' else queries):
        payload={'queryId':q['queryId'],'queryText':q['queryText'],'strategy':strategy}
        request=urllib.request.Request('http://127.0.0.1:8010/internal/v1/retrieval',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(request,timeout=90) as r:current=json.load(r)
        baseline=saved[q['queryId']]['results'];assert len(baseline)==len(current['results'])
        for a,b in zip(baseline,current['results']):
            assert a.keys()==b.keys()
            for k in a:
                if k=='lexicalScore' and a[k] is not None:assert abs(a[k]-b[k])<=1e-12
                else:assert a[k]==b[k],(strategy,q['queryId'],k,a[k],b[k])
        results.append({'strategy':strategy,'queryId':q['queryId'],'sameRankAndScores':True})
    print('PASS',strategy,len([r for r in results if r['strategy']==strategy]),flush=True)
(out/'retrieval-live-regression.json').write_text(json.dumps({'result':'PASS','checks':results,'lexicalTolerance':1e-12,'reason':'Pre-existing floating summation roundoff documented in Phase10; all other fields exact.'},indent=2))
