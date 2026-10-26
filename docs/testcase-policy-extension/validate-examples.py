"""Real vector retrieval + explicitly fake extractive analysis/model selection.

No generation database write or LLM call. Does not load Ground Truth.
"""
import json
import os
import re
import urllib.request
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4
from app.test_case_models import GenerationRequest
from app.test_case_policy import load_policy, compile_candidates
from app.test_case_service import TestCaseGenerator
from app.test_case_registry import plan_sources
from app.analysis_models import AnalysisRequest
from app.analysis_service import AnalysisService, catalog
from app.vector_search import SearchHit

root = Path('/repo')
out = Path('/evidence')
policy, policy_hash = load_policy()
before = json.loads((out / 'policy-before.json').read_text(encoding='utf8'))
fixture = json.loads((out/'random-examples.json').read_text(encoding='utf8'))
examples = [(str(example['id']), example['title'], example['description']) for example in fixture]
assert len(examples) == 5
results = []
for id, title, description in examples:
    query = description.replace('\\n', '\n')
    request = urllib.request.Request('http://ai-service:8000/internal/v1/search', data=json.dumps({'query': title+'\n'+query, 'topK': 5}).encode(), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=45) as response:
        hits = json.load(response)
    confirmed = []
    # Fixed extractive fake analysis: select up to four grounded registry anchors in retrieved text.
    for plan in policy['plans']:
        for hit in hits:
            fact = {'text': plan['confirmedCondition'], 'chunkId': hit['chunkId']}
            if fact['text'] in hit['contentSnippet'] and fact not in confirmed:
                confirmed.append(fact)
    confirmed = confirmed[:4]
    rid = str(uuid4())
    search=Mock();search.search.return_value=[SearchHit(**hit) for hit in hits]
    sentences,apis=catalog(search.search.return_value)
    selected=[key for key,value in sentences.items() if any(value['text']==fact['text'] and value['chunkId']==fact['chunkId'] for fact in confirmed)]
    routes={p['case']['input']['method']+' '+p['case']['input']['endpoint'] for p in policy['plans'] if any(p['confirmedCondition']==fact['text'] for fact in confirmed)}
    types={hit['chunkId']:hit['documentType'] for hit in hits}
    api_ids=[key for key,value in sorted(apis.items(),key=lambda entry:types[entry[1]['chunkId']]!='API_SPEC') if value['api'] in routes][:3]
    analysis_model=Mock();analysis_model.generate.return_value=json.dumps(dict(evidenceSufficiency='SUFFICIENT',confirmedConditionIds=selected,
        relatedBusinessRuleIds=selected,relatedApiIds=api_ids,ambiguousExpressions=[],missingConditions=[],clarificationQuestions=[]))
    source=AnalysisService(search,analysis_model).analyze(AnalysisRequest(requirementId=rid,title=title,description=query)).model_dump()
    generation = GenerationRequest(requirementId=rid, title=title, description=query, analysis=source)
    candidates, pending = compile_candidates(generation, policy)
    old_candidates, _ = compile_candidates(generation, before)
    fake = Mock()
    fake.generate.return_value = json.dumps({'candidateIds': list(candidates)})
    result = TestCaseGenerator(fake, policy, policy_hash).generate(generation)
    refs = {s['chunkId']: s for plan in policy['plans'] for s in plan_sources(source, policy, plan).values()}
    grounded = all(all(ref.chunkId in refs and refs[ref.chunkId]['documentId'] == ref.documentId for ref in tc.evidence) for tc in result.testCases)
    assert grounded
    results.append(dict(id=int(id), title=title, retrieval='REAL_VECTOR_TOP5', analysis='FAKE_EXTRACTIVE_ANCHORS', selection='FAKE_PROVIDER',
                        ragHits=len(hits), confirmedConditions=len(confirmed), beforeTestCount=len(old_candidates), testCount=len(result.testCases),
                        templateIds=list(candidates), grounded=grounded, automaticallyExecutable=any(tc.executable for tc in result.testCases),
                        clarificationRequired=result.clarificationRequired, analysisSnapshot=source, testCases=[tc.model_dump() for tc in result.testCases]))

# Same saved four-condition return snapshot before/after. No analysis changes.
source = json.loads((out / 'before-analysis.json').read_text(encoding='utf8'))
generation = GenerationRequest(requirementId=source['requirementId'], title='대여 자산 반납 및 상태 변경 검증', description='동일 저장 분석 스냅샷 비교', analysis=source)
old, _ = compile_candidates(generation, before)
new, pending = compile_candidates(generation, policy)
covered = {condition['text'] for condition in source['confirmedConditions'] for plan in policy['plans']
           if plan['id'] in new and condition['text'] in plan.get('coveredConditions', [plan['confirmedCondition']])}
comparison = dict(confirmedConditions=4, beforeCount=len(old), afterCount=len(new), supportedConditions=len(covered), supportRatio=len(covered)/4,
                  unsupportedConditions=[c['text'] for c in source['confirmedConditions'] if c['text'] not in covered], templateIds=list(new))
(out / 'random-example-results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf8')
(out / 'same-snapshot-comparison.json').write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding='utf8')

# The request's broader wording is tested separately; it must not invent an unspecified history contract.
description='대여 중인 IT 자산을 반납할 때 기존 대여 이력을 확인해야 한다.\n\n정상적인 반납 요청이 처리되면 대여 기록과 자산 상태를 일관되게 변경한다.\n\n이미 반납이 완료된 자산에 대한 중복 반납 요청은 허용하지 않는다.\n\n반납 권한이 없는 사용자의 요청은 거부되어야 한다.'
title='대여 자산 반납 및 상태 변경 검증'
request=urllib.request.Request('http://ai-service:8000/internal/v1/search',data=json.dumps({'query':title+'\n'+description,'topK':5}).encode(),headers={'Content-Type':'application/json'})
with urllib.request.urlopen(request,timeout=45) as response:hits=json.load(response)
search=Mock();search.search.return_value=[SearchHit(**hit) for hit in hits]
sentences,apis=catalog(search.search.return_value)
selected=[key for key,value in sentences.items() if value['text']=='현재 대여자 또는 자산 담당자만 반납 접수를 할 수 있다.'][:1]
fake=Mock();fake.generate.return_value=json.dumps(dict(evidenceSufficiency='PARTIAL',confirmedConditionIds=selected,
    relatedBusinessRuleIds=selected,relatedApiIds=[key for key,value in apis.items() if value['api']=='POST /loans/{loanId}/returns'][:1],
    ambiguousExpressions=[],missingConditions=['기존 대여 이력의 조회 범위 및 대여 기록의 일관성 판정 계약은 검색 근거만으로 확정할 수 없습니다.'],
    clarificationQuestions=['반납 접수와 검사 완료 중 어느 단계에서 어떤 대여 이력 필드를 확인·변경해야 하나요?']))
rid=str(uuid4());analysis=AnalysisService(search,fake).analyze(AnalysisRequest(requirementId=rid,title=title,description=description))
fake_selection=Mock()
blocked=TestCaseGenerator(fake_selection,policy,policy_hash).generate(GenerationRequest(requirementId=rid,title=title,description=description,analysis=analysis))
assert not blocked.testCases and blocked.llmCalls==0
fake_selection.generate.assert_not_called()
(out/'broader-request-validation.json').write_text(json.dumps(dict(title=title,description=description,analysisProvider='FAKE_PARTIAL',retrieval='REAL_VECTOR_TOP5',
    analysis=analysis.model_dump(),generation=blocked.model_dump(),expectedStatus='BLOCKED_CLARIFICATION_REQUIRED'),ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'examples': [{key:r[key] for key in ['id','testCount','grounded','templateIds']} for r in results], 'sameSnapshot': comparison}, ensure_ascii=False))
