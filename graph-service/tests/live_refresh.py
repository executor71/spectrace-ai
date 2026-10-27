"""Read source snapshots and idempotently refresh only their owned relationships."""
import json
from app.source import collect,project
from app.store import Store
from app.queries import traverse

rid='c9e5d1d8-6de2-487e-8ae6-9cf6c7b99eae'
store=Store()
try:
    before=store.export()
    sources,chunks=collect(requirement_ids=[rid])
    for _ in range(2):store.sync(project(sources,chunks))
    after=store.export()
    assert before==after,'Repeated scoped refresh changed semantic graph'
    assert len(after['nodes'])==len({(n['type'],n['id']) for n in after['nodes']})
    assert len(after['edges'])==len({(e['sourceType'],e['source'],e['relation'],e['targetType'],e['target']) for e in after['edges']})
    original=['438c6b1b-e41e-4083-93da-72c0be1597bf','80e2d374-0825-4811-a11e-03ade256b6e8','b5270f71-c92c-48ae-8530-8946f1cfce62']
    results=[]
    for identifier in original+[rid]:
        graph=traverse(store,'find_requirement_context',identifier)
        assert graph['edgeCount']>0
        results.append(dict(requirementId=identifier,nodes=graph['nodeCount'],edges=graph['edgeCount'],testCases=len(graph['relatedTestCases']),executions=len(graph['executions']),hops=graph['hopCount']))
    print('RESULT:'+json.dumps(dict(idempotent=True,noDuplicates=True,unrelatedPreserved=True,totalNodes=len(after['nodes']),totalEdges=len(after['edges']),requirements=results)))
finally:store.driver.close()
