"""Closed, source-gated plans; no retrieval or database access in generation."""
import hashlib
import json
import os
from copy import deepcopy
from pathlib import Path
from uuid import UUID
from app.test_case_registry import validate_policy, plan_sources

TYPES = ['NORMAL', 'EXCEPTION', 'AUTHORIZATION', 'BOUNDARY', 'BUSINESS_RULE']


def load_policy():
    path = Path(os.getenv('TEST_CASE_POLICY', '/contracts/test-case-policy.json'))
    raw = path.read_bytes()
    policy = json.loads(raw)
    validate_policy(policy)
    return policy, hashlib.sha256(raw).hexdigest()


def execution_gates(case, policy):
    value = case['input']
    route = value.get('method', '') + ' ' + value.get('endpoint', '')
    return {
        'apiAllowListed': route in policy['allowList'],
        'methodEndpointKnown': bool(value.get('method') and value.get('endpoint')),
        'preconditionsReproducible': bool(policy['fixtureReady'] and value.get('actorFixture')),
        'inputDefined': bool(value.get('pathParameters') and 'body' in value),
        'expectedResultCheckable': bool(case['expectedResult']['assertions']) and all(
            x.get('kind') in policy['assertionKinds'] for x in case['expectedResult']['assertions']),
    }


def compile_candidates(request, policy):
    analysis = request.analysis.model_dump()
    if analysis['requirementId'] != request.requirementId:
        raise ValueError('Requirement identity mismatch')
    UUID(request.requirementId)
    sources = {}
    for source in analysis['evidence']:
        UUID(source['documentId']); UUID(source['chunkId'])
        if source['chunkId'] in sources:
            raise ValueError('Duplicate evidence')
        sources[source['chunkId']] = source
    for condition in analysis['confirmedConditions']:
        source = sources.get(condition['chunkId'])
        if not source or condition['text'] not in source['contentSnippet']:
            raise ValueError('Unverified condition')
    pending = list(dict.fromkeys(analysis['ambiguousExpressions'] + analysis['missingConditions'] + analysis['clarificationQuestions']))
    if pending or not analysis['confirmedConditions']:
        return {}, pending or ['확정된 조건이 없어 사용자 확인이 필요합니다.']
    candidates = {}
    for plan in policy['plans']:
        anchors = [c for c in analysis['confirmedConditions'] if c['text'] == plan['confirmedCondition']]
        if not anchors:
            continue
        sources = plan_sources(analysis, policy, plan)
        refs = [sources[anchors[0]['chunkId']]]
        for requirement in plan['sources']:
            source = next((s for s in sources.values() if s['documentType'] == requirement['documentType']
                           and all(q in s['contentSnippet'] for q in requirement['quotes'])), None)
            if source is None:
                break
            refs.append(source)
        else:
            route = plan['case']['input']['method'] + ' ' + plan['case']['input']['endpoint']
            api_supported = any(a['api'] == route and a['chunkId'] in sources and route in sources[a['chunkId']]['contentSnippet']
                                for a in analysis['relatedApis'])
            if 'coveredConditions' in plan:
                api_supported |= any(s['documentType'] == 'API_SPEC' and route in s['contentSnippet'] for s in sources.values())
            if not api_supported:
                continue
            case = deepcopy(plan['case'])
            case['requirementId'] = request.requirementId
            case['evidence'] = [{'documentId': s['documentId'], 'chunkId': s['chunkId']} for s in
                                {s['chunkId']: s for s in refs}.values()]
            case['executable'] = all(execution_gates(case, policy).values())
            candidates[plan['id']] = case
    if not candidates:
        known = any(condition['text'] in plan.get('coveredConditions', [plan['confirmedCondition']])
                    for condition in analysis['confirmedConditions'] for plan in policy['plans'])
        pending = ['테스트에 필요한 업무규칙 또는 API 근거가 부족합니다.' if known else
                   '확정 조건을 지원하는 근거 검증 테스트 템플릿이 없습니다. 테스트 절차와 판정 기준을 확인해 주세요.']
    return candidates, pending


def evaluate_assertions(assertions, observation):
    """Pure comparison only: does not connect to or execute an API."""
    if not assertions:
        return False
    for a in assertions:
        kind = a.get('kind')
        if kind == 'HTTP_STATUS':
            valid = observation.get('httpStatus') == a['value']
        elif kind == 'RESPONSE_TOKEN':
            valid = a['value'] in observation.get('responseTokens', [])
        elif kind == 'OBSERVATION_EQUALS':
            valid = observation.get('after', {}).get(a['field']) == a['value']
        elif kind == 'UNCHANGED':
            valid = a['field'] in observation.get('before', {}) and a['field'] in observation.get('after', {}) and observation['before'][a['field']] == observation['after'][a['field']
            ]
        else:
            valid = False
        if not valid:
            return False
    return True
