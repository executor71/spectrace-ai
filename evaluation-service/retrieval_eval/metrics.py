"""Deterministic retrieval metrics. Only evaluation code receives relevance labels."""
import math,statistics

def evaluate(results,grades,k=5,key='chunkId'):
    ids=[row[key] for row in results]
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate results')
    if any(item not in grades for item in ids):raise ValueError('Result outside frozen corpus')
    relevant={cid for cid,g in grades.items() if g>0};top=ids[:k]
    found=[rank for rank,cid in enumerate(top,1) if cid in relevant]
    dcg=sum((2**grades[cid]-1)/math.log2(rank+1) for rank,cid in enumerate(top,1))
    ideal=sum((2**g-1)/math.log2(rank+1) for rank,g in enumerate(sorted(grades.values(),reverse=True)[:k],1))
    return {'hitAt5':int(bool(found)),'recallAt5':len(found)/len(relevant) if relevant else None,
            'mrrAt5':1/found[0] if found else 0,'ndcgAt5':dcg/ideal if ideal else None,
            'firstRelevantRank':found[0] if found else None,'meanRelevantRank':statistics.mean(found) if found else None,'relevantCount':len(relevant)}

def percentile(values,p):
    if not values:return None
    xs=sorted(values);position=(len(xs)-1)*p;low=math.floor(position);high=math.ceil(position)
    return xs[low]+(xs[high]-xs[low])*(position-low)

def summarize(metrics,latencies):
    result={key:statistics.mean([m[key] for m in metrics if m[key] is not None]) if any(m[key] is not None for m in metrics) else None for key in ['hitAt5','recallAt5','mrrAt5','ndcgAt5']}
    result.update(failedQueries=sum(m['hitAt5']==0 for m in metrics),queryCount=len(metrics),
        latencyMs={'mean':statistics.mean(latencies) if latencies else None,'p50':percentile(latencies,.5),'p95':percentile(latencies,.95),'samples':len(latencies)})
    return result

def query_by_id(dataset,query_id):
    for query in dataset['queries']:
        if query['queryId']==query_id:return query
    raise ValueError('UNKNOWN_QUERY_ID: '+query_id)
