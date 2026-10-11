import copy,json
from pathlib import Path
import pytest
from app.source import project
from app.model import APIS
from app.queries import QUERIES

@pytest.fixture
def facts():return json.loads(Path('/evidence/source-facts.json').read_text())
@pytest.fixture
def chunks():return json.loads(Path('/graph/data/knowledge.json').read_text())
@pytest.fixture
def projection(facts,chunks):return project(facts,chunks)

def test_deterministic(facts,chunks):assert project(facts,chunks)==project(facts,chunks)
def test_unique_ids(projection):
    ns=projection['nodes'];es=projection['edges']
    assert len(ns)==len({(n['type'],n['id']) for n in ns})
    assert len(es)==len({(e['sourceType'],e['source'],e['relation'],e['targetType'],e['target']) for e in es})
def test_original_ids(projection,facts,chunks):
    allowed={c['chunkId'] for c in chunks}|{c['documentId'] for c in chunks}|set(APIS.values())
    for s in facts:
        allowed.add(s['requirement']['id'])
        allowed.update(c['testCaseId'] for c in (s['batch'] or {}).get('testCases',[]))
        allowed.update(e['executionId'] for history in s['executions'].values() for e in history)
    assert all(n['id'] in allowed for n in projection['nodes'])
@pytest.mark.parametrize('relation',['SUPPORTED_BY','AFFECTS','GENERATES','IMPLEMENTED_BY','VERIFIED_BY','BASED_ON','EXECUTED_AS'])
def test_required_relations(projection,relation):assert any(e['relation']==relation for e in projection['edges'])
def test_no_false_api_or_rule_for_tampered_endpoint(projection):
    assert not any(e['target']=='1f521e4c-458b-4c09-95f3-4e6d26ea112a' and e['relation']=='VERIFIED_BY' for e in projection['edges'])
def test_asset_review_does_not_verify_copied_loan_rules(projection):
    edges=[e for e in projection['edges'] if e['target']=='889ea853-67f3-49a0-b2b3-2ff94520f094' and e['relation']=='VERIFIED_BY']
    assert [e['source'] for e in edges]==['API-ASSET-001']
def test_revision_and_review_unchanged(facts,chunks):
    before=copy.deepcopy(facts);p=project(facts,chunks);assert facts==before
    assert all('testCaseRevision' in n for n in p['nodes'] if n['type']=='Execution')
def test_removed_evidence_drops_relation(facts,chunks):
    case=facts[0]['batch']['testCases'][0];case['evidence']=[]
    assert not any(e['source']==case['testCaseId'] and e['relation']=='BASED_ON' for e in project(facts,chunks)['edges'])
def test_mismatching_document_is_not_linked(facts,chunks):
    case=facts[0]['batch']['testCases'][0]
    for e in case['evidence']:e['documentId']='wrong'
    assert not any(e['source']==case['testCaseId'] and e['relation']=='BASED_ON' for e in project(facts,chunks)['edges'])
def test_spoof_apiid_not_linked(facts,chunks):
    case=facts[0]['batch']['testCases'][0];case['input']['apiId']='API-ASSET-001'
    assert not any(e['target']==case['testCaseId'] and e['relation']=='VERIFIED_BY' for e in project(facts,chunks)['edges'])
def test_no_sensitive_properties(projection):
    forbidden={'password','apiKey','prompt','reasoning','groundTruth','expected','actual','reviewComment'}
    assert all(not forbidden.intersection(n) for n in projection['nodes'])
def test_fixed_bounded_query_catalog():
    assert len(QUERIES)==3
    assert all('$id' in query and not any(v in query for v in ('CREATE','DELETE','SET ')) for _,queries in QUERIES.values() for query in queries)
