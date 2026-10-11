"""Graph relations annotate Hybrid evidence; neither ranking nor text is changed."""
import httpx
from workflow_otel import span,attrs
from .queries import traverse,EntityMissing
from neo4j.exceptions import Neo4jError,DriverError

def assemble(store,requirement_id):
    with httpx.Client(timeout=20,trust_env=False,follow_redirects=False) as http:
        response=http.get('http://backend:8080/api/requirements/'+requirement_id)
        response.raise_for_status();requirement=response.json()
        # Same query composition and 2000-char contract as the existing analyzer.
        response=http.post('http://retrieval-service:8010/internal/v1/retrieval',json={
            'queryId':'graph-context','queryText':requirement['title']+'\n'+requirement['description'],'strategy':'HYBRID'})
        response.raise_for_status();retrieval=response.json()
    with span('graph.context_merge') as s:
        try:graph=traverse(store,'find_requirement_context',requirement_id);status='AVAILABLE'
        except EntityMissing:graph=None;status='NOT_SYNCED'
        except (Neo4jError,DriverError,OSError,ValueError):graph=None;status='UNAVAILABLE'
        hits=retrieval['results']
        ids={h['chunkId'] for h in hits}
        # Only provenance paths with supporting chunks in this exact retrieval can annotate analysis.
        grounded_paths=[]
        if graph:
            for p in graph['paths']:
                refs=set(p['evidenceChunkIds'])
                if refs and refs.issubset(ids):
                    grounded_paths.append({'path':[{'type':n['type'],'id':n['id']} for n in p['path']],
                        'relations':p['relations'],'evidenceChunkIds':sorted(refs)})
        attrs(s,{'nodeCount':graph['nodeCount'] if graph else 0,'edgeCount':graph['edgeCount'] if graph else 0,
            'hopCount':graph['hopCount'] if graph else 0,'resultCount':len(grounded_paths)})
        return {'requirement':requirement,'strategy':'HYBRID','textEvidence':hits,'retrievalMetadata':{k:retrieval[k] for k in ('configHash','corpusHash','latencyMs') if k in retrieval},
            'graphStatus':status,'graphContext':graph,'analysisRelations':grounded_paths,
            'policy':'Relations identify objects only. Facts and expected results require the unchanged text evidence.'}
