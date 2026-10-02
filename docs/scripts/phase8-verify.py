"""Independently verify stored final experiment results against the frozen inputs."""
from pathlib import Path
from collections import Counter
import hashlib,json,sys,urllib.request,urllib.error
root=Path(__file__).resolve().parents[2];dest=root/'docs/phase8-evidence'
sys.path.insert(0,str(root/'evaluation-service'))
from retrieval_eval.metrics import evaluate,summarize
def read(name):return json.loads((dest/name).read_text(encoding='utf-8'))
dataset=read('evaluation-dataset.json');queries={q['queryId']:q for q in dataset['queries']};freeze=read('dataset-freeze.json')
assert hashlib.sha256((dest/'evaluation-dataset.json').read_bytes()).hexdigest()==freeze['datasetSha256']
assert hashlib.sha256((root/'evaluation-service/datasets/retrieval-v1.json').read_bytes()).hexdigest()==freeze['datasetSha256']
summary=read('comparison-summary.json');latency=read('latency-results.json');config=summary['config']
config_hash=hashlib.sha256(json.dumps(config,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
strategies=['VECTOR','LEXICAL','HYBRID','HYBRID_RERANK'];rows={s:read(f) for s,f in zip(strategies,['vector-results.json','lexical-results.json','hybrid-results.json','reranker-results.json'])}
raw=[json.loads(line) for line in (dest/'final-raw-samples.jsonl').read_text(encoding='utf-8').splitlines()]
assert len(raw)==384
counts=Counter()
for sample in raw:
    r=sample['response'];query=queries[r['queryId']];counts[r['queryId'],r['strategy']]+=1
    assert sample['queryText']==query['queryText'] and r['corpusHash']==freeze['corpusHash'] and r['configHash']==config_hash
    assert r['finalTopK']==5 and r['latencyMs']>=0
    assert [h['rank'] for h in r['results']]==list(range(1,len(r['results'])+1))
    for hit in r['results']:
        assert all(k in hit for k in ['documentId','chunkId','documentType','section','contentSnippet','vectorScore','lexicalScore','fusionScore','rerankScore'])
    saved=next(v for v in rows[r['strategy']] if v['queryId']==r['queryId'])
    assert saved['results']==r['results']
assert len(counts)==128 and set(counts.values())=={3}
for strategy in strategies:
    assert {r['queryId'] for r in rows[strategy]}==set(queries)
    for split in ['all','phase2-original-8','synthetic-24']:
        selected=[r for r in rows[strategy] if split=='all' or queries[r['queryId']]['split']==split];ids={r['queryId'] for r in selected}
        calculated=summarize([evaluate(r['results'],queries[r['queryId']]['chunkRelevanceGrades']) for r in selected],[r['latencyMs'] for r in latency['steadyStateSamples'][strategy] if r['queryId'] in ids])
        assert calculated==summary['groups'][split][strategy]
for hybrid,rerank in zip(rows['HYBRID'],rows['HYBRID_RERANK']):
    assert hybrid['queryId']==rerank['queryId']
    assert {r['chunkId'] for r in hybrid['candidates']}=={r['chunkId'] for r in rerank['candidates']}
    assert len(rerank['candidates'])<=20
    assert [r['rerankScore'] for r in rerank['candidates']]==sorted([r['rerankScore'] for r in rerank['candidates']],reverse=True)
edge=[]
for payload,expected in [({'queryId':'empty-lexical','queryText':'zzzznonexistentterm987654','strategy':'LEXICAL'},200),({'queryId':'../../bad','queryText':'x','strategy':'VECTOR'},422),({'queryId':'labels','queryText':'x','strategy':'VECTOR','relevantChunkIds':['secret']},422)]:
    request=urllib.request.Request('http://127.0.0.1:8010/internal/v1/retrieval',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(request,timeout=30) as response:code=response.status;body=json.load(response)
    except urllib.error.HTTPError as e:code=e.code;body=json.load(e)
    assert code==expected
    if code==200:assert body['results']==[]
    edge.append({'request':payload,'status':code,'response':body})
(dest/'api-edge-cases.json').write_text(json.dumps(edge,ensure_ascii=False,indent=2),encoding='utf-8')
result={'result':'PASS','frozenInputHashes':True,'same32QueriesAllStrategies':True,'measuredRequests':384,'repetitions':3,'rankAndScoreRepeatable':True,'metricsRecomputed':True,'rerankerCandidateSubsetVerified':True,'commonSchemaVerified':True,'actualApiEdgeCases':3}
(dest/'experiment-verification.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
