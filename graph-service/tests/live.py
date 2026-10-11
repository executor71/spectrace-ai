import json,time,hashlib,copy
from concurrent.futures import ThreadPoolExecutor
from neo4j.exceptions import Neo4jError
from pathlib import Path
import httpx
from app.store import Store
from app.source import collect,project
from app.queries import one_hop
from workflow_otel import setup,trace
setup('legacy-assistant-graph')
out=Path('/evidence');s=Store();records=[]
def check(name,condition):
    assert condition,name;records.append({'test':name,'result':'PASS'})
try:
    check('Neo4j health',s.read('RETURN 1 AS ok')==[{'ok':1}])
    sources,chunks=collect();p=project(sources,chunks)
    a=s.sync(p);before=s.export();b=s.sync(p);after=s.export()
    check('Repeated sync exact nodes and edges',before==after)
    check('Original IDs, properties, edges',p['nodes']==after['nodes'] and p['edges']==after['edges'])
    # Only the disposable graph projection changes; restore even if an assertion fails.
    try:
        trimmed=copy.deepcopy(p);removed=next(n for n in trimmed['nodes'] if n['type']=='Execution')
        trimmed['nodes'].remove(removed);trimmed['edges']=[e for e in trimmed['edges'] if e['target']!=removed['id']]
        s.sync(trimmed);current=s.export()
        check('Stale nodes and edges removed atomically',not any(n['id']==removed['id'] for n in current['nodes']) and not any(e['target']==removed['id'] for e in current['edges']))
    finally:s.sync(p)
    invalid=copy.deepcopy(p);invalid['nodes'][0]['invalidNestedProperty']={'not':'neo4j scalar'}
    try:s.sync(invalid);raise AssertionError('Expected invalid property rollback')
    except (ValueError,TypeError,Neo4jError):pass
    check('Failed sync rolls back whole projection',s.export()==after)
    with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(s.sync,[p,p]))
    check('Concurrent sync does not duplicate nodes or edges',s.export()==after)
    check('Requirement 1-hop',len(one_hop(s,'b5270f71-c92c-48ae-8530-8946f1cfce62'))==7)
    for kind in ['nodes','edges']:(out/f'graph-{kind}.json').write_text(json.dumps(after[kind],ensure_ascii=False,indent=2))
    (out/'graph-sync-result.json').write_text(json.dumps({'first':a,'second':b,'idempotent':True},indent=2))
    (out/'graph-summary.json').write_text(json.dumps({'nodes':{t:sum(n['type']==t for n in after['nodes']) for t in sorted({n['type'] for n in after['nodes']})},'relations':{r:sum(e['relation']==r for e in after['edges']) for r in sorted({e['relation'] for e in after['edges']})}},indent=2))
    results={}
    with httpx.Client(base_url='http://graph-service:8030',timeout=15) as http:
        for tool,args in [('find_requirement_context',{'requirementId':'b5270f71-c92c-48ae-8530-8946f1cfce62'}),('find_impacted_tests',{'businessRuleId':'7cea4fe7-6b00-56c9-be35-3194aeecb923'}),('trace_test_case_origin',{'testCaseId':'4611bca5-0d0c-45dd-9793-75566c432c89'})]:
            r=http.post('/api/graph/'+tool,json=args);check(tool,r.status_code==200)
            results[tool]=r.json();check(tool+' multi-hop',r.json()['hopCount']>=2)
        r=http.post('/api/graph/find_requirement_context',json={'requirementId':'00000000-0000-4000-8000-000000000999'})
        check('Missing entity 404',r.status_code==404)
        for value in ["MATCH (n) DETACH DELETE n",'http://outside.example','../admin/reset']:
            check('Injection rejected '+value,http.post('/api/graph/find_impacted_tests',json={'businessRuleId':value}).status_code==422)
        check('Extra Cypher field rejected',http.post('/api/graph/find_requirement_context',json={'requirementId':'b5270f71-c92c-48ae-8530-8946f1cfce62','cypher':'MATCH(n) RETURN n'}).status_code==422)
        check('No arbitrary query route',http.post('/api/graph/execute_cypher',json={'query':'MATCH(n) RETURN n'}).status_code==404)
        check('No public sync route',http.post('/api/graph/sync').status_code==404)
        r=http.post('/api/graph/analysis-context',json={'requirementId':'b5270f71-c92c-48ae-8530-8946f1cfce62'});r.raise_for_status();context=r.json()
        check('Graph context retains five text hits',len(context['textEvidence'])==5)
        ids={h['chunkId'] for h in context['textEvidence']}
        check('Graph annotations grounded in retrieved text',all(set(p['evidenceChunkIds'])<=ids for p in context['analysisRelations']))
        (out/'analysis-context.json').write_text(json.dumps(context,ensure_ascii=False,indent=2))
    (out/'graph-query-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
    (out/'graph-live-tests.json').write_text(json.dumps(records,indent=2));print('PASS',len(records),'graph live assertions')
finally:
    s.driver.close();trace.get_tracer_provider().force_flush()
