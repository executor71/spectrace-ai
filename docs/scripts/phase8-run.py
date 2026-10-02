"""Evaluation-side orchestrator: sends only query text/id and strategy, never relevance labels."""
from pathlib import Path
import argparse,hashlib,json,sys,time,urllib.request,datetime,statistics
root=Path(__file__).resolve().parents[2];dest=root/'docs/phase8-evidence'
sys.path.insert(0,str(root/'evaluation-service'))
from retrieval_eval.metrics import evaluate,summarize,query_by_id
def save(name,value):(dest/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
def fingerprint(path):return hashlib.sha256(path.read_bytes()).hexdigest()
args=argparse.ArgumentParser();args.add_argument('--stage',choices=['hybrid','final'],required=True);args.add_argument('--query-id');opts=args.parse_args()
dataset_path=root/'evaluation-service/datasets/retrieval-v1.json';dataset=json.loads(dataset_path.read_text(encoding='utf-8'))
freeze=json.loads((dest/'dataset-freeze.json').read_text());assert fingerprint(dataset_path)==freeze['datasetSha256'];assert fingerprint(dest/'evaluation-dataset.json')==freeze['datasetSha256']
queries=[query_by_id(dataset,opts.query_id)] if opts.query_id else dataset['queries']
strategies=['VECTOR','LEXICAL','HYBRID']+(['HYBRID_RERANK'] if opts.stage=='final' else [])
config=json.loads((root/'retrieval-service/config/retrieval.json').read_text());assert all(config[k]==freeze[k] for k in ['finalTopK','retrievalCandidateK','rrfK','bm25K1','bm25B'])
if opts.query_id:
    dest=dest/('single-query-'+opts.query_id);dest.mkdir(exist_ok=True)
elif opts.stage=='final' and (dest/'comparison-summary.json').exists():
    dest=dest/'reruns'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');dest.mkdir(parents=True)
def call(query,strategy):
    payload={'queryId':query['queryId'],'queryText':query['queryText'],'strategy':strategy}
    request=urllib.request.Request('http://127.0.0.1:8010/internal/v1/retrieval',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    start=time.perf_counter()
    with urllib.request.urlopen(request,timeout=600) as response:result=json.load(response)
    result['clientLatencyMs']=(time.perf_counter()-start)*1000
    assert result['queryId']==query['queryId'] and result['strategy']==strategy and result['corpusHash']==freeze['corpusHash'] and result['finalTopK']==5
    assert result['configHash']==hashlib.sha256(json.dumps(config,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return result
started=datetime.datetime.now(datetime.timezone.utc).isoformat();cold={}
for strategy in strategies:
    cold[strategy]=call(queries[0],strategy);print('initial',strategy,round(cold[strategy]['clientLatencyMs'],1),'ms',flush=True)
save(opts.stage+'-initial-requests.json',cold)
if opts.stage=='final':
    for n,query in enumerate(queries):
        for strategy in strategies:call(query,strategy)
        print('warmup',n+1,'/',len(queries),flush=True)
    save('warmup.json',{'passes':1,'queries':len(queries),'requests':len(queries)*len(strategies),'excludedFromSteadyState':True})
results={s:[] for s in strategies};samples={s:[] for s in strategies};per_query=[];repetitions=3 if opts.stage=='final' else 1
for qi,query in enumerate(queries):
    record={'queryId':query['queryId'],'queryText':query['queryText'],'split':query['split'],'relevantDocumentIds':query['relevantDocumentIds'],'relevantChunkIds':query['relevantChunkIds'],'chunkRelevanceGrades':query['chunkRelevanceGrades'],'strategies':{}}
    for repetition in range(repetitions):
        # Rotate order; each strategy gets the same inputs without shared query result caches.
        order=strategies[(qi+repetition)%len(strategies):]+strategies[:(qi+repetition)%len(strategies)]
        for strategy in order:
            value=call(query,strategy)
            with (dest/(opts.stage+'-raw-samples.jsonl')).open('a',encoding='utf-8') as raw:
                raw.write(json.dumps({'repetition':repetition+1,'queryText':query['queryText'],'response':value},ensure_ascii=False)+'\n')
            samples[strategy].append({'queryId':query['queryId'],'repetition':repetition+1,'latencyMs':value['latencyMs'],'clientLatencyMs':value['clientLatencyMs'],'candidateCount':value['candidateCount'],'timing':value['timing']})
            if repetition==0:
                results[strategy].append(value);metrics=evaluate(value['results'],query['chunkRelevanceGrades'])
                ranks={row['chunkId']:row['rank'] for row in value['results']}
                record['strategies'][strategy]={'metrics':metrics,'top5':value['results'],'relevantRanks':{cid:ranks.get(cid) for cid in query['relevantChunkIds']},'candidateCount':value['candidateCount']}
            else:
                previous=next(r for r in results[strategy] if r['queryId']==query['queryId'])
                assert previous['results']==value['results'],('Non-deterministic ranking',query['queryId'],strategy)
    base=record['strategies']['VECTOR']['metrics'];changes={}
    for strategy in ['HYBRID']+(['HYBRID_RERANK'] if opts.stage=='final' else []):
        m=record['strategies'][strategy]['metrics'];changes[strategy]={k:m[k]-base[k] for k in ['hitAt5','recallAt5','mrrAt5','ndcgAt5']}
    record['changesVsVector']=changes;per_query.append(record)
    save(opts.stage+'-progress.json',{'completed':qi+1,'total':len(queries),'samples':sum(map(len,samples.values())),'lastQueryId':query['queryId']})
    print(opts.stage,qi+1,'/',len(queries),query['queryId'],flush=True)
summary={}
for split in ['all','phase2-original-8','synthetic-24']:
    selected=[r for r in per_query if split=='all' or r['split']==split];ids={r['queryId'] for r in selected}
    summary[split]={s:summarize([r['strategies'][s]['metrics'] for r in selected],[r['latencyMs'] for r in samples[s] if r['queryId'] in ids]) for s in strategies}
suffix='' if opts.stage=='final' else 'stage-hybrid-'
for strategy,name in [('VECTOR','vector-results.json'),('LEXICAL','lexical-results.json'),('HYBRID','hybrid-results.json'),('HYBRID_RERANK','reranker-results.json')]:
    if strategy in results:save(suffix+name,results[strategy])
save(suffix+'query-by-query-comparison.json',per_query)
save(suffix+'latency-results.json',{'initialRequests':cold,'steadyStateSamples':samples,'repetitions':repetitions,'percentileMethod':'linear interpolation at (n-1)*p','timingDefinition':'latencyMs is service search time; clientLatencyMs includes serialization/network/engine initialization; initialRequests and warmup excluded from steady-state'})
save(suffix+'comparison-summary.json',{'datasetHash':freeze['datasetSha256'],'corpusHash':freeze['corpusHash'],'startedAt':started,'finishedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'primaryUnit':'chunk','MRR':'truncated MRR@5; no relevant item in final Top-5 -> 0','config':config,'groups':summary,'improvedQueries':{s:[r['queryId'] for r in per_query if any(v>0 for v in r['changesVsVector'][s].values())] for s in ['HYBRID']+(['HYBRID_RERANK'] if opts.stage=='final' else [])},'worsenedQueries':{s:[r['queryId'] for r in per_query if any(v<0 for v in r['changesVsVector'][s].values())] for s in ['HYBRID']+(['HYBRID_RERANK'] if opts.stage=='final' else [])}})
assert fingerprint(dataset_path)==freeze['datasetSha256']
print(json.dumps(summary['all'],ensure_ascii=False),flush=True)
