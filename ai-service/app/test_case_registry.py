"""Read-only policy validation and bounded API specification adapter. No GT/DB access."""
import os
from pathlib import Path
from uuid import UUID
from app.knowledge import load_corpus


def validate_policy(policy):
    from app.test_case_models import TestCase
    if not isinstance(policy.get('plans'), list) or not isinstance(policy.get('fixtureReady'), bool):
        raise ValueError('Invalid test policy registry')
    if len(policy['plans']) > 30:
        raise ValueError('Policy exceeds the structured selection limit')
    corpus = None
    if policy.get('apiEvidence'):
        _, chunks = load_corpus(Path(os.getenv('KNOWLEDGE_ROOT', '/knowledge')))
        corpus = {str(chunk.id): chunk for chunk in chunks}
    ids, evidence_ids = set(), set()
    for source in policy.get('apiEvidence', []):
        UUID(source['documentId']); UUID(source['chunkId'])
        if source['chunkId'] in evidence_ids:
            raise ValueError('Duplicate policy evidence ID')
        evidence_ids.add(source['chunkId'])
        chunk = corpus.get(source['chunkId'])
        if not chunk or chunk.document.document_type != 'API_SPEC' or any([
            source['documentId'] != str(chunk.document.id), source['section'] != chunk.section,
            source['contentSnippet'] != chunk.content, source['relatedApis'] != list(chunk.related_apis),
            source['sourceName'] != chunk.document.source_name, source['documentType'] != 'API_SPEC']):
            raise ValueError('Policy evidence differs from the synthetic corpus')
    for plan in policy['plans']:
        if not isinstance(plan.get('id'), str) or not plan['id'] or plan['id'] in ids:
            raise ValueError('Empty or duplicate test template ID')
        ids.add(plan['id'])
        if not plan.get('confirmedCondition') or not plan.get('sources'):
            raise ValueError('Template requires an anchor and source quotes')
        case = TestCase.model_validate(dict(plan['case'], testCaseId=str(UUID(int=1)), requirementId=str(UUID(int=2)), evidence=[], executable=False))
        if not case.expectedResult.assertions or any(a.get('kind') not in policy['assertionKinds'] for a in case.expectedResult.assertions):
            raise ValueError('Invalid expected-result assertion')
        for source in plan['sources']:
            if not source.get('quotes') or any(not isinstance(q, str) or not q for q in source['quotes']):
                raise ValueError('Empty template grounding quote')
        if 'coveredConditions' in plan:
            quotes = [q for source in plan['sources'] for q in source['quotes']]
            if plan['confirmedCondition'] not in quotes:
                raise ValueError('Template anchor must be an exact source quote')
            for source in plan['sources']:
                if not any(c.document.document_type == source['documentType'] and all(q in c.content for q in source['quotes']) for c in corpus.values()):
                    raise ValueError('Template quotes are not grounded in the declared corpus type')
            # Coverage is explicit, extractive and independently checked at load time.
            for condition in plan['coveredConditions']:
                if corpus is None or condition not in quotes or not any(condition in c.content for c in corpus.values()):
                    raise ValueError('Unknown covered condition')
            route = case.input['method'] + ' ' + case.input['endpoint']
            if not any(route in s['relatedApis'] and route in s['contentSnippet'] for s in policy['apiEvidence']):
                raise ValueError('Template API is not in the public synthetic specification')
            if case.expectedResult.description not in quotes:
                raise ValueError('Expected result must be an exact source quote')
            for assertion in case.expectedResult.assertions:
                kind = assertion['kind']
                if kind == 'HTTP_STATUS' and not any('HTTP '+str(assertion['value']) in q for q in quotes):
                    raise ValueError('HTTP assertion lacks a source quote')
                if kind in ['RESPONSE_TOKEN', 'OBSERVATION_EQUALS'] and not any(str(assertion['value']) in q for q in quotes):
                    raise ValueError('Expected value lacks a source quote')
                if kind == 'UNCHANGED' and not any('변경하지 않는다' in q for q in quotes):
                    raise ValueError('State preservation lacks a source quote')


def plan_sources(analysis, policy, plan):
    sources = {s['chunkId']: s for s in analysis['evidence']}
    if 'coveredConditions' not in plan:
        return sources
    route = plan['case']['input']['method'] + ' ' + plan['case']['input']['endpoint']
    if route not in {api['api'] for api in analysis['relatedApis']}:
        return sources
    for source in policy.get('apiEvidence', []):
        if route in source['relatedApis'] and route in source['contentSnippet']:
            sources.setdefault(source['chunkId'], {key: source[key] for key in [
                'documentId', 'chunkId', 'documentType', 'section', 'contentSnippet', 'score']})
    return sources
