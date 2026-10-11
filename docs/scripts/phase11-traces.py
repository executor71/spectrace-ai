from pathlib import Path
import urllib.request,json,time
root=Path(__file__).resolve().parents[2];out=root/'docs/phase11-evidence'
records=json.loads((out/'graph-trace-ids.json').read_text())
sync=json.loads((out/'graph-sync-result.json').read_text())
records.extend({'case':'GRAPH_SYNC','traceId':sync[k]['traceId']} for k in ('first','second'))
allspans=[];results=[]
for item in records:
    with urllib.request.urlopen('http://127.0.0.1:16686/api/traces/'+item['traceId'],timeout=10) as r:data=json.load(r)['data'][0]
    spans=data['spans'];allspans+=spans;ids={s['spanID'] for s in spans}
    assert all(ref['spanID'] in ids for s in spans for ref in s['references'] if ref['refType']=='CHILD_OF')
    names={s['operationName'] for s in spans};services={p['serviceName'] for p in data['processes'].values()}
    assert 'legacy-assistant-graph' in services
    if item['case']=='GRAPH_SYNC':assert 'graph.sync' in names
    else:assert {'graph.query','graph.traversal'}<=names
    if item['case']=='MCP_GRAPH_TOOLS':
        assert {'mcp.find_requirement_context','mcp.find_impacted_tests','mcp.trace_test_case_origin'}<=names
        assert 'legacy-assistant-mcp' in services
    elif item['case']=='GRAPH_CONTEXT':assert 'graph.context_merge' in names
    for s in spans:
        tags={t['key']:t['value'] for t in s['tags']}
        assert not any(any(secret in k.lower() for secret in ['password','prompt','reasoning','cypher','db.statement','groundtruth','api_key']) for k in tags)
        if s['operationName'] in {'graph.traversal','graph.context_merge','graph.sync'} and 'error' not in tags:
            assert {'nodeCount','edgeCount','hopCount','resultCount','durationMs'}<=tags.keys(),tags
    results.append({**item,'spans':spans,'services':sorted(services),'parentLinksValid':True,'sensitiveAttributesAbsent':True})
(out/'observability-traces.json').write_text(json.dumps({'result':'PASS','traceCount':len(results),'spanCount':len(allspans),'traces':results},indent=2))
print('PASS',len(results),'traces',len(allspans),'spans')
