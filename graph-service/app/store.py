import os,time
from uuid import uuid4
from neo4j import GraphDatabase, Query
from workflow_otel import span,attrs,correlation
from .model import LABELS,RELATIONS

class Store:
    def __init__(self):
        self.driver=GraphDatabase.driver('bolt://neo4j:7687',auth=('neo4j',os.environ['NEO4J_PASSWORD']),connection_timeout=2,connection_acquisition_timeout=3,max_transaction_retry_time=0)
    def schema(self):
        with self.driver.session(database='neo4j') as session:
            for label in (*LABELS,'Projection'):
                session.run(f'CREATE CONSTRAINT {label.lower()}_id IF NOT EXISTS FOR (n:{label}) REQUIRE n.id IS UNIQUE').consume()
    def sync(self,projection):
        epoch=str(uuid4())
        with span('graph.sync') as s, self.driver.session(database='neo4j') as session:
            def write(tx):
                # A property update obtains an exclusive lock for concurrent full-scope syncs.
                tx.run("MERGE (m:Projection {id:'phase11'}) SET m.lock=coalesce(m.lock,0)+1").consume()
                for label in LABELS:
                    rows=[dict(n,epoch=epoch) for n in projection['nodes'] if n['type']==label]
                    tx.run(f'UNWIND $rows AS row MERGE (n:GraphEntity:{label} {{id:row.id}}) SET n = row',rows=rows).consume()
                for rel in RELATIONS:
                    for st in LABELS:
                        for tt in LABELS:
                            rows=[dict(e,epoch=epoch) for e in projection['edges'] if (e['relation'],e['sourceType'],e['targetType'])==(rel,st,tt)]
                            if rows:tx.run(f'UNWIND $rows AS row MATCH (a:{st} {{id:row.source}}),(b:{tt} {{id:row.target}}) MERGE (a)-[r:{rel}]->(b) SET r=row',rows=rows).consume()
                scope=[n['id'] for n in projection['nodes'] if n['type']=='Requirement']
                # Only replace relationships owned by this committed source snapshot.
                # Shared corpus and other requirements must survive incremental updates.
                tx.run('MATCH (a:GraphEntity)-[r]->(b:GraphEntity) WHERE r.epoch <> $epoch AND ((a:Requirement AND a.id IN $scope) OR (a:TestCase AND a.requirementId IN $scope) OR (b:TestCase AND b.requirementId IN $scope)) DELETE r',epoch=epoch,scope=scope).consume()
                tx.run("MATCH (m:Projection {id:'phase11'}) SET m.syncedAt=datetime(),m.nodeCount=$nodes,m.edgeCount=$edges",nodes=len(projection['nodes']),edges=len(projection['edges'])).consume()
            session.execute_write(write)
            counts={'nodeCount':len(projection['nodes']),'edgeCount':len(projection['edges'])}
            attrs(s,dict(counts,hopCount=0,resultCount=len(projection['nodes'])));return dict(counts,traceId=correlation()['traceId'],skipped=projection['skipped'],scope='configured requirements + frozen Phase2 corpus',atomic=True)
    def read(self,query,**params):
        with span('graph.query') as s,self.driver.session(database='neo4j',default_access_mode='READ') as session:
            result=session.run(Query(query,timeout=4),**params).data()
            attrs(s,{'resultCount':len(result)});return result
    def export(self):
        nodes=self.read('MATCH (n:GraphEntity) RETURN properties(n) AS n ORDER BY n.type,n.id')
        edges=self.read('MATCH (:GraphEntity)-[r]->(:GraphEntity) RETURN properties(r) AS e ORDER BY r.sourceType,r.source,r.relation,r.target')
        return {'nodes':[{k:v for k,v in x['n'].items() if k!='epoch'} for x in nodes], 'edges':[{k:v for k,v in x['e'].items() if k!='epoch'} for x in edges]}
