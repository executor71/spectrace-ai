"""Use the existing projection with live REST data; do not alter Neo4j schema/scope."""
import json
from pathlib import Path
import httpx
from app.source import project

rid='c9e5d1d8-6de2-487e-8ae6-9cf6c7b99eae'
with httpx.Client(base_url='http://backend:8080',timeout=20) as client:
    def get(path):
        response=client.get(path);response.raise_for_status();return response.json()
    batch=get('/api/requirements/'+rid+'/test-cases')
    source=dict(requirement=get('/api/requirements/'+rid),analysis=get('/api/requirements/'+rid+'/analysis'),batch=batch,
        executions={tc['testCaseId']:get('/api/test-cases/'+tc['testCaseId']+'/executions') for tc in batch['testCases']})
projection=project([source],json.loads(Path('/graph/data/knowledge.json').read_text()))
ids={run['executionId'] for runs in source['executions'].values() for run in runs}
assert len(ids)==6
assert ids=={node['id'] for node in projection['nodes'] if node['type']=='Execution'}
assert ids=={edge['target'] for edge in projection['edges'] if edge['relation']=='EXECUTED_AS'}
report={'liveReturnExecutions':len(ids),'executionNodes':len(ids),'EXECUTED_AS':len(ids),'existingProjection':'PASS','neo4jScopeModified':False,
    'limitation':'Live Neo4j scope remains the existing three requirements. New return Api canonical nodes are not added in this task.'}
Path('/evidence/graph-results.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report))
