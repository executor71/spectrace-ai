import asyncio,json,statistics,math
from pathlib import Path
import httpx
from workflow_otel import setup,span,trace,httpx_propagation
setup('legacy-assistant-demo');httpx_propagation()
dest=Path('/evidence');baseline=json.loads((dest/'matched-baseline-input.json').read_text());rows=[]
async def main():
    async with httpx.AsyncClient(timeout=120) as http:
        for strategy,old in baseline.items():
            for index in range(3):
                with span('workflow.baseline_comparison') as root:
                    response=await http.post('http://retrieval-service:8010/internal/v1/retrieval',json={'queryId':'phase2-1','queryText':'노트북을 이미 빌린 직원이 한 대 더 신청할 수 있나요?','strategy':strategy})
                    response.raise_for_status();data=response.json()
                    actual=[{k:h[k] for k in ['chunkId','vectorScore','lexicalScore','fusionScore','rerankScore']} for h in data['results']]
                    lexical_delta=0.0
                    for a,b in zip(actual,old['hits']):
                        for key in a:
                            if key=='lexicalScore' and a[key] is not None and b[key] is not None:
                                lexical_delta=max(lexical_delta,abs(a[key]-b[key]));assert abs(a[key]-b[key])<1e-12
                            else:assert a[key]==b[key],(strategy,key)
                    assert len(actual)==len(old['hits'])
                    assert data['corpusHash']==old['corpusHash'] and data['configHash']==old['configHash']
                    rows.append({'strategy':strategy,'iteration':index,'traceId':format(root.get_span_context().trace_id,'032x'),
                        'latencyMs':data['latencyMs'],'phase8LatencyMs':old['latencyMs'],'sameRanksAndNonLexicalScores':True,
                        'lexicalScoreMaxAbsoluteDelta':lexical_delta,'lexicalTolerance':1e-12,'sameCorpusAndConfig':True})
    trace.get_tracer_provider().force_flush()
    summary={strategy:{'phase8SameQueryMs':old['latencyMs'],'phase10SameQueryP50Ms':statistics.median([r['latencyMs'] for r in rows if r['strategy']==strategy])} for strategy,old in baseline.items()}
    (dest/'matched-baseline-comparison.json').write_text(json.dumps({'result':'PASS','queryId':'phase2-1','results':rows,'summary':summary,'interpretation':'Same query and exact results; historical timing still includes runtime/hardware scheduling differences.'},indent=2))
    print(json.dumps(summary))
asyncio.run(main())
