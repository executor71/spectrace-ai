import copy
from unittest.mock import Mock,patch
import pytest
from app.refresh import Refresher
from app.queries import traverse,QUERIES

@pytest.fixture(autouse=True)
def no_database_credentials_required(monkeypatch):
    monkeypatch.setenv('NEO4J_PASSWORD','unit-test-unused')

def test_lifecycle_reprojects_only_committed_changes():
    store=Mock()
    worker=Refresher(store)
    client=Mock()
    client.get.return_value.json.return_value={'requirements':[{'id':'r'}]}
    source={'requirement':{'id':'r'},'analysis':None,'batch':None,'executions':{}}
    with patch('app.refresh.httpx.Client') as factory, patch('app.refresh.collect') as collect, patch('app.refresh.project',side_effect=lambda s,c:copy.deepcopy(s)):
        factory.return_value.__enter__.return_value=client
        collect.side_effect=lambda **kwargs:([copy.deepcopy(source)],[])
        worker.cycle()
        worker.cycle()
        assert store.sync.call_count==1
        for key,value in [('analysis',{'conditions':[1]}),('batch',{'testCases':[{'approvalStatus':'DRAFT'}]}),('batch',{'testCases':[{'approvalStatus':'APPROVED','reviewRevision':2}]}),('executions',{'t':[{'result':'PASS'}]})]:
            source[key]=value
            worker.cycle()
        assert store.sync.call_count==5
        assert worker.states['r']=='SYNCED'

def test_failed_sync_retries_unchanged_source_and_preserves_hash():
    store=Mock()
    worker=Refresher(store)
    client=Mock()
    client.get.return_value.json.return_value={'requirements':[{'id':'r'}]}
    with patch('app.refresh.httpx.Client') as factory, patch('app.refresh.collect',return_value=([{'requirement':{'id':'r'}}],[])), patch('app.refresh.project',return_value={}):
        factory.return_value.__enter__.return_value=client
        store.sync.side_effect=RuntimeError('offline')
        worker.cycle()
        assert worker.states['r']=='FAILED' and not worker.hashes
        store.sync.side_effect=None
        worker.cycle()
        assert worker.states['r']=='SYNCED'
        assert store.sync.call_count==2

def test_failure_isolated_between_requirements():
    worker=Refresher(Mock())
    client=Mock()
    client.get.return_value.json.return_value={'requirements':[{'id':'bad'},{'id':'good'}]}
    with patch('app.refresh.httpx.Client') as factory, patch('app.refresh.collect',side_effect=[ValueError(),([{}],[])]), patch('app.refresh.project',return_value={}):
        factory.return_value.__enter__.return_value=client
        worker.cycle()
        assert worker.states=={'bad':'FAILED','good':'SYNCED'}

def test_root_survives_without_execution_or_any_relationships():
    store=Mock()
    store.read.side_effect=[[{'n':{'id':'r','type':'Requirement'}}]]+[[]]*len(QUERIES['find_requirement_context'][1])
    result=traverse(store,'find_requirement_context','r')
    assert result['nodeCount']==1 and result['edgeCount']==0
    assert result['executions']==[]

def test_full_execution_path_is_scoped():
    queries=QUERIES['find_requirement_context'][1]
    assert any('IMPLEMENTED_BY' in q and 'EXECUTED_AS' in q and 't.requirementId=$id' in q for q in queries)

@pytest.mark.parametrize('state,code',[('PENDING','GRAPH_SYNC_PENDING'),('FAILED','GRAPH_SYNC_FAILED')])
def test_missing_projection_status(state,code):
    from app import main
    from fastapi.testclient import TestClient
    from app.queries import EntityMissing
    rid='c9e5d1d8-6de2-487e-8ae6-9cf6c7b99eae'
    with patch.dict(main.refresher.states,{rid:state}),patch('app.main.traverse',side_effect=EntityMissing):
        response=TestClient(main.app).post('/api/graph/find_requirement_context',json={'requirementId':rid})
    assert response.status_code==404
    assert response.json()['detail']['errorCode']==code

def test_connection_failure_separate_from_pending():
    from app import main
    from fastapi.testclient import TestClient
    with patch('app.main.traverse',side_effect=OSError):
        response=TestClient(main.app).post('/api/graph/find_requirement_context',json={'requirementId':'c9e5d1d8-6de2-487e-8ae6-9cf6c7b99eae'})
    assert response.status_code==503
    assert response.json()['detail']['errorCode']=='GRAPH_UNAVAILABLE'
