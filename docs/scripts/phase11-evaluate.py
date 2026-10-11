"""Retrieval-capability benchmark, not an LLM answer-quality comparison."""
from pathlib import Path
import json,hashlib,time,urllib.request,urllib.error,statistics,math
root=Path(__file__).resolve().parents[2];out=root/'docs/phase11-evidence'
truth=out/'relation-ground-truth.json'
assert hashlib.sha256(truth.read_bytes()).hexdigest()==(out/'relation-ground-truth.sha256').read_text()
queries=json.loads(truth.read_text(encoding='utf8'))['queries']
apis={'POST /loans/{loanId}/approve':'API-LOAN-APPROVE','GET /assets/{assetId}':'API-ASSET-001'}
catalog={c['chunkId']:c for c in json.loads((root/'graph-service/data/knowledge.json').read_text(encoding='utf8'))}
def post(port,path,body):
    req=urllib.request.Request(f'http://127.0.0.1:{port}'+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code==404:return None
        raise
def nk(n):return (n['type'],n['id'])
def pk(p):return (tuple(nk(n) for n in p['path']),tuple(p['relations']))
def extract_text(hits):
    nodes=set();paths=set()
    for h in hits:
        c=catalog[h['chunkId']];b=('BusinessRule',c['documentId'])
        if c['documentType']=='BUSINESS_RULE':nodes.add(b)
        for route in c['metadata']['relatedApis']:
            if route not in apis:continue
            a=('Api',apis[route]);nodes.add(a)
            if c['documentType']=='BUSINESS_RULE':paths.add(((b,a),('IMPLEMENTED_BY',)))
    return nodes,paths
records=[]
for q in queries:
    sample={};outputs={}
    for strategy in ['HYBRID_ONLY','HYBRID_GRAPH']:
        timings=[]
        for repeat in range(3):
            started=time.perf_counter()
            retrieval=post(8010,'/internal/v1/retrieval',{'queryId':q['id'],'queryText':q['question'],'strategy':'HYBRID'})
            text_nodes,text_paths=extract_text(retrieval['results'])
            if strategy=='HYBRID_GRAPH':
                graph=post(8030,'/api/graph/'+q['tool'],q['arguments'])
                # Structured graph task uses the anchored traversal; text remains as evidence.
                nodes={nk(n) for key in ['relatedRequirements','relatedBusinessRules','relatedApis','relatedTestCases','evidence','executions'] for n in (graph or {}).get(key,[])}
                paths={pk(p) for p in (graph or {}).get('paths',[])}
            else:nodes,paths=text_nodes,text_paths
            timings.append((time.perf_counter()-started)*1000)
        expected={nk(n) for n in q['expectedEntities']};wanted={pk(p) for p in q['expectedPaths']}
        relevant={n for n in nodes if n[0] in q['targetTypes']}
        recall=len(relevant&expected)/len(expected) if expected else None
        accuracy=len(wanted&paths)/len(wanted) if wanted else None
        success=(not relevant) if q['negative'] else expected<=relevant and wanted<=paths
        sample[strategy]={'entityRecall':recall,'matchedEntities':len(relevant&expected),'expectedEntities':len(expected),'returnedEntities':len(relevant),'entityPrecision':len(relevant&expected)/len(relevant) if relevant else None,'pathAccuracy':accuracy,'matchedPaths':len(wanted&paths),'expectedPaths':len(wanted),'multiHopSuccess':success,'negative':q['negative'],'latencyMs':timings,'retrievedChunkIds':[h['chunkId'] for h in retrieval['results']]}
    records.append({'id':q['id'],'question':q['question'],'results':sample})
    print(q['id'],[(k,v['multiHopSuccess']) for k,v in sample.items()],flush=True)
def percentile(values,p):
    values=sorted(values);idx=(len(values)-1)*p;lo=int(idx);return values[lo]+(values[min(lo+1,len(values)-1)]-values[lo])*(idx-lo)
summary={}
for strategy in ['HYBRID_ONLY','HYBRID_GRAPH']:
    values=[r['results'][strategy] for r in records];positive=[v for v in values if not v['negative']];negative=[v for v in values if v['negative']]
    times=[t for v in values for t in v['latencyMs']]
    summary[strategy]={'entityRecall':sum(v['matchedEntities'] for v in positive)/sum(v['expectedEntities'] for v in positive),
        'pathAccuracy':sum(v['matchedPaths'] for v in positive)/sum(v['expectedPaths'] for v in positive),
        'multiHopSuccessRate':sum(v['multiHopSuccess'] for v in positive)/len(positive),'negativeAccuracy':sum(v['multiHopSuccess'] for v in negative)/len(negative),
        'positiveQueries':len(positive),'negativeQueries':len(negative),'latencyP50Ms':percentile(times,.5),'latencyP95Ms':percentile(times,.95),'samples':len(times)}
report={'groundTruthSha256':hashlib.sha256(truth.read_bytes()).hexdigest(),'queries':records,'comparison':summary,
 'methodology':{'entityRecall':'Micro recall over positive expected typed IDs; precision per query is also reported.','pathAccuracy':'Exact ordered typed nodes AND relation labels matched / expected paths (path coverage, not returned-path precision).','multiHopSuccess':'All expected entities AND paths present on positive 2+ hop queries; negative abstention scored separately.','baseline':'Unchanged Hybrid top5 + deterministic entity/path extraction from retrieved chunk metadata; no runtime TestCase/Execution lookup. No LLM.','graph':'Same Hybrid top5 + fixed anchored Graph traversal over persisted runtime data. Retrieval ranks/scores unchanged.','limitations':['20 curated queries share a small synthetic domain; not independent broad-domain samples.','Graph has structured runtime relations unavailable in the text corpus; measures added relation access, not intrinsic search superiority.','No new LLM calls or answer-quality judging.','One cold request may affect latency; three sequential repetitions per query.']}}
(out/'multi-hop-evaluation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
(out/'hybrid-vs-graph-comparison.json').write_text(json.dumps({'comparison':summary,'methodology':report['methodology']},ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(summary,indent=2))
