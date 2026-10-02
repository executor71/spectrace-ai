"""Deterministic evaluation only. No model, generation or database dependencies."""
import hashlib
import json
import re

VERSION = 'phase6-deterministic-v1'


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def pointer(value, path):
    for part in path.lstrip('/').split('/'):
        part = part.replace('~1', '/').replace('~0', '~')
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def subset(value, expected):
    return isinstance(value, dict) and all(k in value and type(value[k]) is type(v) and value[k] == v for k, v in expected.items())


def matches(case, condition):
    op = condition['op']
    if op == 'equals':
        actual = pointer(case, condition['path'])
        return type(actual) is type(condition['value']) and actual == condition['value']
    if op == 'assertion':
        assertions = pointer(case, '/expectedResult/assertions')
        return isinstance(assertions, list) and any(subset(a, condition['value']) for a in assertions)
    if op == 'preconditionState':
        # Deliberately narrow, explicit state declaration, not a semantic string similarity.
        pattern = {'loanStatus': r'(?:합성 )?대여 신청의 상태는 ([A-Z_]+)이다\.', 'assetStatus': r'(?:해당 )?자산의 상태는 ([A-Z_]+)이다\.'}[condition['field']]
        values = [m.group(1) for text in case.get('preconditions', []) if isinstance(text, str) for m in re.finditer(pattern, text)]
        return bool(values) and set(values) == {condition['value']}
    raise ValueError('Unsupported condition operator')


def text(value):
    return isinstance(value, str) and bool(value.strip())


def strings(value, nonempty=True):
    return isinstance(value, list) and (bool(value) or not nonempty) and all(text(v) for v in value)


def consistency(case, truth):
    for forbidden in truth['forbiddenAssertions']:
        if all(matches(case, c) for c in forbidden['when']) and matches(case, {'op':'assertion','value':forbidden['assertion']}):
            return 'FAIL', ['forbidden:' + forbidden['id']]
    relevant = [r for r in truth['expectedBusinessRules'] if all(matches(case, c) for c in r['when'])]
    assertions = pointer(case, '/expectedResult/assertions')
    if not relevant or not isinstance(assertions, list) or not assertions:
        return 'UNKNOWN', ['structured-consistency-not-provable']
    allowed = [a for r in relevant for a in r['allowedAssertions']]
    unknown = False
    for assertion in assertions:
        if not isinstance(assertion, dict):
            return 'FAIL', ['malformed-assertion']
        if assertion in allowed:
            continue
        same_subject = [a for a in allowed if a.get('kind') == assertion.get('kind') and a.get('field') == assertion.get('field')]
        if same_subject:
            return 'FAIL', ['contradictory-assertion']
        unknown = True
    return ('UNKNOWN', ['unsupported-assertion']) if unknown else ('PASS', [r['id'] for r in relevant])


def validity(case, truth, source, catalog, requirement_id):
    refs = case.get('evidence')
    registry = {(e['documentId'], e['chunkId']) for e in catalog}
    provenance = {(e['documentId'], e['chunkId']) for e in source.get('evidence', [])}
    reference_ok = isinstance(refs, list) and bool(refs) and all(isinstance(r, dict) and (r.get('documentId'), r.get('chunkId')) in registry & provenance for r in refs)
    expected = case.get('expectedResult')
    check = {
        'scenarioPresent': text(case.get('scenario')),
        'preconditionsDefined': strings(case.get('preconditions'), nonempty=False),
        'inputDefined': isinstance(case.get('input'), dict) and bool(case['input']),
        'stepsPresent': strings(case.get('steps')),
        'expectedResultDefined': isinstance(expected, dict) and text(expected.get('description')) and isinstance(expected.get('assertions'), list),
        'evidencePresent': isinstance(refs, list) and bool(refs),
        'evidenceReferencesValid': reference_ok and case.get('requirementId') == requirement_id,
    }
    checks = {k: 'PASS' if v else 'FAIL' for k,v in check.items()}
    state, reasons = consistency(case, truth)
    checks['noStructuredContradiction'] = state
    status = 'FAIL' if 'FAIL' in checks.values() else 'UNKNOWN' if 'UNKNOWN' in checks.values() else 'PASS'
    return {'testCaseId':case.get('testCaseId'), 'status':status, 'checks':checks, 'consistencyReasons':reasons}


def ratio(numerator, denominator):
    return {'numerator':numerator, 'denominator':denominator, 'value':numerator / denominator if denominator else None,
            'status':'MEASURED' if denominator else 'NOT_APPLICABLE'}


def evaluate(truth, inputs):
    cases = inputs['testCases']
    results = [validity(c, truth, inputs['sourceAnalysis'], inputs['evidenceCatalog'], inputs['requirementId']) for c in cases]
    hits = inputs['searchHits'][:5]  # Five chunks from the unchanged Phase 2 retriever, then document deduplication.
    expected = set(truth['expectedEvidenceDocumentIds'])
    found = {h['documentId'] for h in hits}
    retrieval = {**ratio(len(expected & found), len(expected)), 'topK':5, 'retrievedChunkCount':len(hits),
                 'retrievedDocumentIds':sorted(found), 'matchedDocumentIds':sorted(expected & found), 'missingDocumentIds':sorted(expected - found)}
    def coverage(scenarios):
        rows = []
        for scenario in scenarios:
            matched = []
            for case, valid in zip(cases, results):
                if valid['status'] == 'PASS' and case.get('type') == scenario['category'] and all(matches(case, c) for c in scenario['requiredConditions']):
                    matched.append(case['testCaseId'])
            rows.append({'scenarioId':scenario['scenarioId'], 'category':scenario['category'], 'description':scenario['description'], 'matchedTestCaseIds':matched, 'covered':bool(matched)})
        return {**ratio(sum(r['covered'] for r in rows), len(rows)), 'scenarios':rows, 'missingScenarios':[r for r in rows if not r['covered']]}
    return {'recallAt5':retrieval, 'scenarioCoverage':coverage(truth['requiredTestScenarios']),
            'optionalScenarioCoverage':coverage(truth['optionalTestScenarios']),
            'testCaseValidity':{**ratio(sum(r['status']=='PASS' for r in results),len(results)), 'failedCount':sum(r['status']=='FAIL' for r in results),
                                'unknownCount':sum(r['status']=='UNKNOWN' for r in results), 'cases':results},
            'manualSemanticConsistency':{'status':'NOT_ASSESSED', 'targetCount':len(cases), 'includedInDeterministicScore':False},
            'counts':{'queries':1,'testCases':len(cases),'requiredScenarios':len(truth['requiredTestScenarios']), 'expectedDocuments':len(expected)}}
