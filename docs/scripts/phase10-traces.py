from pathlib import Path
import json,urllib.request,statistics,math
root=Path(__file__).resolve().parents[2];dest=root/'docs/phase10-evidence';archive=dest/'traces';archive.mkdir(exist_ok=True)
def read(name):return json.loads((dest/name).read_text(encoding='utf-8'))
rows=read('demo-trace-ids.json')+read('mock-trace-ids.json')+read('mock-mcp-trace-ids.json')
if (dest/'browser-trace-ids.json').exists():rows+=read('browser-trace-ids.json')
real=read('real-analysis.json');rows.append(dict(real,case='B_REAL_ANALYSIS'))
def tags(s):return {t['key']:t['value'] for t in s['tags']}
all_spans=[];records=[];errors=[];checks=[]
for row in rows:
    tid=row['traceId']
    with urllib.request.urlopen('http://127.0.0.1:16686/api/traces/'+tid,timeout=15) as response:data=json.load(response)
    assert data['data'],row
    item=data['data'][0];spans=item['spans'];processes=item['processes']
    assert all(s['traceID']==tid for s in spans)
    ids={s['spanID'] for s in spans}
    # Every non-root reference must resolve inside this full captured workflow.
    assert all(r['spanID'] in ids for s in spans for r in s.get('references',[]) if r['refType']=='CHILD_OF'),row
    (archive/(row['case']+'-'+tid+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    names={s['operationName'] for s in spans};services={p['serviceName'] for p in processes.values()}
    if row['case']=='A_HYBRID':assert {'backend.requirement','rag.search','query.embedding','vector.search','lexical.search'}<=names
    if row['case']=='C_MCP':assert {'legacy-assistant-mcp','legacy-assistant-backend'}<=services and 'mcp.tool' in names
    if row['case']=='B_REAL_ANALYSIS':
        assert {'legacy-assistant-backend','legacy-assistant-ai'}<=services
        assert {'requirement.analysis','rag.search','query.embedding','vector.search','llm.generate'}<=names
        llm=[s for s in spans if s['operationName']=='llm.generate'];assert len(llm)==1
        attrs=tags(llm[0]);assert attrs['model']=='qwen2.5:7b-instruct' and attrs['retryCount']==0 and attrs['success'] is True
        assert attrs['inputTokens']+attrs['outputTokens']==attrs['totalTokens']
    for s in spans:
        t=tags(s)
        if t.get('error.code'):errors.append({'case':row['case'],'traceId':tid,'spanId':s['spanID'],'operation':s['operationName'],'code':t['error.code'],'synthetic':row.get('synthetic',False)})
        all_spans.append((row,s,t))
    records.append({**row,'services':sorted(services),'operations':sorted(names),'jaegerUrl':'http://localhost:16686/trace/'+tid})
required={'LLM_TIMEOUT','LLM_INVALID_OUTPUT','RAG_NO_RESULT','VALIDATION_FAILED','MCP_TOOL_REJECTED','TEST_NOT_APPROVED','TEST_NOT_EXECUTABLE','FIXTURE_NOT_READY','API_NOT_ALLOWED','DUMMY_TEST_FAIL'}
assert required<={e['code'] for e in errors}
(dest/'trace-ids.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
(dest/'error-traces.json').write_text(json.dumps({'requiredCodes':sorted(required),'result':'PASS','errors':errors},indent=2))
def stats(values):return dict(count=len(values),mean=statistics.mean(values),p50=statistics.median(values),p95=sorted(values)[math.ceil(.95*len(values))-1],max=max(values))
groups={}
span_names={(s['traceID'],s['spanID']):s['operationName'] for row,s,t in all_spans}
for strategy in ['VECTOR','HYBRID','HYBRID_RERANK']:
    values=[s['duration']/1000 for row,s,t in all_spans if row['case']=='MEASURE_'+strategy and s['operationName']=='rag.search' and t.get('retrieval.strategy')==strategy
        and not any(span_names.get((s['traceID'],r['spanID']))=='rag.search' for r in s.get('references',[]))]
    groups[strategy]=stats(values)
groups['reranker']=stats([s['duration']/1000 for row,s,t in all_spans if row['case']=='MEASURE_HYBRID_RERANK' and s['operationName']=='rerank'])
groups['LLM analysis']=stats([s['duration']/1000 for row,s,t in all_spans if row['case']=='B_REAL_ANALYSIS' and s['operationName']=='llm.generate'])
groups['MCP tool']=stats([s['duration']/1000 for row,s,t in all_spans if row['case']=='C_MCP' and s['operationName']=='mcp.tool'])
groups['dummy execution']=stats([s['duration']/1000 for row,s,t in all_spans if row['case'] in ['D_PASS','E_FAIL'] and s['operationName']=='dummy.execution'])
# Rank non-overlapping leaf work, excluding startup/warmup and synthetic failures.
leaf_groups={}
for row,s,t in all_spans:
    if row.get('synthetic') or row['case'].startswith('WARMUP'):continue
    if s['operationName'] not in {'llm.generate','rerank','query.embedding','vector.search','lexical.search','dummy.execution','evaluation'}:continue
    leaf_groups.setdefault(s['operationName'],[]).append(s['duration']/1000)
bottlenecks=sorted([{'operation':name,**stats(v)} for name,v in leaf_groups.items()],key=lambda r:r['p50'],reverse=True)[:3]
(dest/'latency-summary.json').write_text(json.dumps({'unit':'ms','source':'actual Jaeger span durations; warmup excluded','workflows':groups,'bottleneckTop3':bottlenecks},indent=2))
before=read('overhead-before.json');after=read('overhead-after.json')
comparison={name:{'before':before['workflows'][name],'after':after['workflows'][name],
    'p50DeltaMs':after['workflows'][name]['p50']-before['workflows'][name]['p50'],
    'p95DeltaMs':after['workflows'][name]['p95']-before['workflows'][name]['p95']} for name in before['workflows']}
(dest/'overhead-comparison.json').write_text(json.dumps({'unit':'ms','design':'12 warm calls per condition; same host, query, endpoints; before/after sequential, not a causal overhead estimate','workflows':comparison},indent=2))
# Audit complete serialized trace data, not just selected attributes.
serialized='\n'.join(p.read_text(encoding='utf-8') for p in archive.glob('*.json'))
sentinels=['SECRET_TIMEOUT_INPUT','SECRET_PROMPT','SECRET_REASONING','SECRET_EXCEPTION','SECRET_USER_SENTINEL','SECRET_AUTH_SENTINEL','SECRET_OVERRIDE_SENTINEL']
assert not any(s in serialized for s in sentinels)
forbidden={'prompt','messages','contentSnippet','groundTruth','thinking','reasoning','authorization','db.statement','db.password','http.request.body','http.response.body'}
keys={t['key'] for row,s,a in all_spans for t in s['tags']}
assert not (keys & forbidden)
assert all(not s['logs'] for row,s,t in all_spans), 'Unexpected event/exception payload'
(dest/'sensitive-data-check.json').write_text(json.dumps({'result':'PASS','tracesScanned':len(records),'spansScanned':len(all_spans),'forbiddenKeys':sorted(forbidden),'sentinelsAbsent':sentinels,'exceptionEventsAbsent':True,'observedAttributeKeys':sorted(keys)},indent=2))
print(json.dumps({'result':'PASS','traces':len(records),'spans':len(all_spans),'bottleneckTop3':bottlenecks},ensure_ascii=False))
