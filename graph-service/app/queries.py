"""Predefined, bounded paths only. No Cypher or labels accepted from callers."""
from workflow_otel import span,attrs

NEIGHBORS='MATCH p=(n:GraphEntity {id:$id})-[*1..1]-(m:GraphEntity) RETURN p LIMIT 2001'

def serialize(rows):
    paths=[];nodes={}
    for row in rows:
        path=row['p']
        # Neo4j driver Record.data() turns Paths into lists, so store queries return maps.
        for node in path['path']:nodes[node['type'],node['id']]=node
        paths.append(path)
    unique={str(p):p for p in paths}
    return sorted(nodes.values(),key=lambda n:(n['type'],n['id'])),list(unique.values())

RETURN=" RETURN {path:[n IN nodes(p) | n {.*,epoch:null}], relations:[r IN relationships(p) | type(r)], evidenceChunkIds:reduce(e=[], r IN relationships(p) | e + coalesce(r.evidenceChunkIds,[]))} AS p LIMIT 2001"

def one_hop(store,identifier):
    return store.read('MATCH p=(n:GraphEntity {id:$id})-[*1..1]-(m:GraphEntity)'+RETURN,id=identifier)

QUERIES={
 'find_requirement_context':('Requirement',[
  'MATCH p=(r:Requirement {id:$id})-[:SUPPORTED_BY|AFFECTS|GENERATES]->(n)',
  'MATCH p=(r:Requirement {id:$id})-[:SUPPORTED_BY]->(:BusinessRule)-[:IMPLEMENTED_BY]->(:Api)',
  'MATCH p=(r:Requirement {id:$id})-[:SUPPORTED_BY]->(:BusinessRule)-[:IMPLEMENTED_BY]->(:Api)-[:VERIFIED_BY]->(t:TestCase) WHERE t.requirementId=$id',
  'MATCH p=(r:Requirement {id:$id})-[:GENERATES]->(:TestCase)-[:BASED_ON|EXECUTED_AS]->(n)']),
 'find_impacted_tests':('BusinessRule',[
  'MATCH p=(b:BusinessRule {id:$id})-[:IMPLEMENTED_BY|VERIFIED_BY]->(n)',
  'MATCH p=(b:BusinessRule {id:$id})-[:IMPLEMENTED_BY]->(:Api)-[:VERIFIED_BY]->(:TestCase)']),
 'trace_test_case_origin':('TestCase',[
  'MATCH p=(:Requirement)-[:GENERATES]->(t:TestCase {id:$id})',
  'MATCH p=(t:TestCase {id:$id})-[:BASED_ON|EXECUTED_AS]->(n)',
  'MATCH p=(b:BusinessRule)-[:VERIFIED_BY]->(t:TestCase {id:$id})',
  'MATCH p=(a:Api)-[:VERIFIED_BY]->(t:TestCase {id:$id})',
  'MATCH p=(r:Requirement)-[:SUPPORTED_BY]->(:BusinessRule)-[:IMPLEMENTED_BY]->(:Api)-[:VERIFIED_BY]->(t:TestCase {id:$id}) WHERE r.id=t.requirementId',
  'MATCH p=(r:Requirement)-[:GENERATES]->(t:TestCase {id:$id})-[:EXECUTED_AS]->(:Execution)'])}

class EntityMissing(Exception):pass
class TooManyPaths(Exception):pass

def traverse(store,tool,identifier):
    label,queries=QUERIES[tool]
    with span('graph.traversal') as s:
        found=store.read(f'MATCH (n:{label} {{id:$id}}) RETURN properties(n) AS n',id=identifier)
        if not found:raise EntityMissing()
        rows=[]
        for query in queries:
            current=store.read(query+RETURN,id=identifier)
            if len(current)>2000:raise TooManyPaths()
            rows.extend(current)
        nodes,paths=serialize(rows)
        root={k:v for k,v in found[0]['n'].items() if k!='epoch'}
        if not any((n['type'],n['id'])==(label,identifier) for n in nodes):nodes.append(root)
        for n in nodes:n.pop('epoch',None)
        for p in paths:
            for n in p['path']:n.pop('epoch',None)
        kinds=lambda kind:[n for n in nodes if n['type']==kind]
        values={'nodeCount':len(nodes),'edgeCount':len({(p['path'][i]['id'],rel,p['path'][i+1]['id']) for p in paths for i,rel in enumerate(p['relations'])}),'hopCount':max([len(p['relations']) for p in paths] or [0]),'resultCount':len(paths)}
        attrs(s,values)
        return dict(root=root,relatedRequirements=kinds('Requirement'),relatedBusinessRules=kinds('BusinessRule'),relatedApis=kinds('Api'),relatedTestCases=kinds('TestCase'),evidence=kinds('Evidence'),executions=kinds('Execution'),paths=paths,**values)
