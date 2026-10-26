"""Rebuild only the bounded policy extension from the public synthetic corpus."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'ai-service'))
from app.knowledge import load_corpus

_, chunks = load_corpus(ROOT / 'knowledge')
policy_path = ROOT / 'contracts/test-case-policy.json'
policy = json.loads(policy_path.read_text(encoding='utf8'))
policy['plans'] = [plan for plan in policy['plans'] if plan['id'].startswith('approval-')]
policy['version'] = 'grounded-policy-v2'
policy['apiEvidence'] = [dict(documentId=str(c.document.id), chunkId=str(c.id),
    documentType=c.document.document_type, section=c.section, contentSnippet=c.content,
    score=0.0, relatedApis=list(c.related_apis), sourceName=c.document.source_name)
    for c in chunks if c.document.document_type == 'API_SPEC']

def section(key, heading):
    return next(c for c in chunks if c.document.key == key and c.section == heading)

def plan(id, kind, anchor_chunk, anchor, api_chunk, route, description, assertions,
         body=None, preconditions=None, extra=None, covered=None):
    assert anchor in anchor_chunk.content
    assert description in api_chunk.content or description in anchor_chunk.content
    sources = [{'documentType': anchor_chunk.document.document_type, 'quotes': [anchor]},
               {'documentType': 'API_SPEC', 'quotes': [route, description] if description in api_chunk.content else [route]}]
    for assertion in assertions:
        if assertion['kind'] == 'HTTP_STATUS':
            sentence = next(s.strip()+'.' for s in api_chunk.content.split('.') if 'HTTP '+str(assertion['value']) in s)
            if sentence not in sources[1]['quotes']:
                sources[1]['quotes'].append(sentence)
    for condition in covered or []:
        assert condition in anchor_chunk.content
        if condition not in sources[0]['quotes']:
            sources[0]['quotes'].append(condition)
    for chunk, quote in extra or []:
        assert quote in chunk.content
        sources.append({'documentType': chunk.document.document_type, 'quotes': [quote]})
    endpoint = route.split(' ', 1)[1]
    params = {name: '00000000-0000-4000-8000-000000000041' for name in ['loanId', 'returnId'] if '{'+name+'}' in endpoint}
    policy['plans'].append({'id': id, 'confirmedCondition': anchor, 'coveredConditions': covered or [anchor],
        'sources': sources, 'case': {'type': kind, 'scenario': description,
        'preconditions': preconditions or ['명세에 맞는 합성 계정과 업무 상태를 격리 환경에 준비한다. 자동 실행 Fixture는 아직 제공되지 않는다.'],
        'input': {'method': 'POST', 'endpoint': endpoint, 'pathParameters': params, 'body': body or {}, 'actorFixture': ''},
        'steps': ['문서에 명시된 권한과 상태를 확인하고 실행 전 관측값을 기록한다.',
                  'input의 명세 경로와 본문으로 요청한다. 자동 실행 미지원 시 검토용 절차로 사용한다.',
                  '응답과 상태를 원문 근거에 연결된 expectedResult와 비교한다.'],
        'expectedResult': {'description': description, 'assertions': assertions}}})

def http(status): return {'kind': 'HTTP_STATUS', 'value': status}
def token(value): return {'kind': 'RESPONSE_TOKEN', 'value': value}
def state(field, value): return {'kind': 'OBSERVATION_EQUALS', 'field': field, 'value': value}

returns = section('return-rules', '반납 접수와 검사 대기')
inspection = section('return-rules', '파손 장비의 수리 전환')
return_api = section('return-api', 'POST /loans/{loanId}/returns 반납 접수')
inspection_api = section('return-api', 'POST /returns/{returnId}/inspection 검사 완료')
return_route = 'POST /loans/{loanId}/returns'
inspection_route = 'POST /returns/{returnId}/inspection'
borrower = '현재 대여자 또는 자산 담당자만 반납 접수를 할 수 있다.'
pending = '반납 건은 INSPECTION_PENDING으로 생성되고 자산은 검사 완료 전까지 새로운 대여에서 제외한다.'
not_available = '반납 접수만으로 재고를 AVAILABLE로 변경하지 않는다.'
plan('return-normal', 'NORMAL', returns, borrower, return_api, return_route,
     '성공 시 HTTP 201과 returnId, status=INSPECTION_PENDING을 반환한다.', [http(201), state('returnStatus', 'INSPECTION_PENDING')],
     {'accessoriesReturned': True, 'note': '합성 반납 검증'}, ['현재 대여자 또는 자산 담당자 계정을 사용한다.', '해당 대여에 기존 반납 접수가 없는 상태를 준비한다.'], covered=[borrower, pending])
plan('return-duplicate', 'EXCEPTION', returns, borrower, return_api, return_route,
     '같은 대여에 반납 접수가 이미 있으면 HTTP 409 RETURN_ALREADY_REQUESTED다.', [http(409), token('RETURN_ALREADY_REQUESTED')],
     {'accessoriesReturned': True, 'note': '합성 중복 검증'}, ['같은 대여에 반납 접수가 이미 존재하는 상태를 준비한다.', '현재 대여자 또는 자산 담당자 계정을 사용한다.'])
plan('return-authorization', 'AUTHORIZATION', returns, borrower, return_api, return_route,
     '현재 대여자가 아니고 자산 담당자도 아닌 호출자는 HTTP 403 ACCESS_DENIED다.', [http(403), token('ACCESS_DENIED')],
     {'accessoriesReturned': True}, ['현재 대여자도 자산 담당자도 아닌 합성 계정을 준비한다.'])
plan('return-inspection-pending', 'BUSINESS_RULE', returns, not_available, return_api, return_route,
     not_available, [http(201), state('returnStatus', 'INSPECTION_PENDING'), {'kind': 'UNCHANGED', 'field': 'assetStatus'}],
     {'accessoriesReturned': True}, ['현재 대여자 또는 자산 담당자 계정과 반납 접수 전 ON_LOAN 자산을 준비한다.'], covered=[not_available, pending])
passed = '이상 없는 장비는 검사 결과 PASSED와 함께 AVAILABLE로 전환한다.'
damaged = '파손 또는 기능 이상이 있으면 검사 결과를 DAMAGED로 기록하고 자산 상태를 MAINTENANCE로 바꾼다.'
for suffix, anchor, result, asset in [('passed', passed, 'PASSED', 'AVAILABLE'), ('damaged', damaged, 'DAMAGED', 'MAINTENANCE')]:
    plan('inspection-'+suffix, 'BUSINESS_RULE', inspection, anchor, inspection_api, inspection_route,
         'PASSED는 AVAILABLE, DAMAGED는 MAINTENANCE로 자산 상태를 전환한다.', [state('assetStatus', asset)],
         {'result': result, **({'damageDescription': '합성 파손', 'photoReferences': ['synthetic-photo']} if result == 'DAMAGED' else {})},
         ['자산 담당자 계정과 미완료 반납 검사 건을 준비한다.'])
plan('inspection-damage-required', 'EXCEPTION', inspection, '사진과 파손 설명은 필수이며 정상 재고로 바로 돌릴 수 없다.', inspection_api, inspection_route,
     'DAMAGED에서는 파손 설명과 최소 한 개의 사진 참조가 필수이며 누락 시 HTTP 400 VALIDATION_ERROR다.', [http(400), token('VALIDATION_ERROR')],
     {'result': 'DAMAGED', 'photoReferences': []}, ['자산 담당자 계정과 미완료 반납 검사 건을 준비한다.'])

inventory = section('asset-lifecycle', '대여 가능한 재고 판정')
loan_api = section('loan-api', 'POST /loans/{loanId}/approve 승인')
restriction = 'RESERVED(예약), ON_LOAN(대여 중), MAINTENANCE(수리 중), LOST(분실), RETIRED(폐기) 상태는 대여할 수 없다.'
plan('inventory-unavailable', 'BUSINESS_RULE', inventory, restriction, loan_api, 'POST /loans/{loanId}/approve',
     '자산 재고 충돌은 HTTP 409 ASSET_NOT_AVAILABLE, 신청 상태 충돌은 HTTP 409 LOAN_STATE_CONFLICT다.', [http(409), token('ASSET_NOT_AVAILABLE')],
     preconditions=['승인 권한이 있는 부서장과 PENDING_APPROVAL 신청을 준비한다.', '자산 상태는 AVAILABLE이 아닌 ON_LOAN으로 준비한다.'])
registration = section('asset-lifecycle', '자산 등록과 관리번호')
asset_api = section('asset-api', 'POST /assets 자산 등록')
plan('asset-registration', 'NORMAL', registration, '신규 등록 시 자산 상태는 AVAILABLE(대여 가능)이다.', asset_api, 'POST /assets',
     '성공 시 HTTP 201과 Location: /assets/{assetId}를 반환한다.', [http(201), state('assetStatus', 'AVAILABLE')],
     {'assetNumber': 'SYNTHETIC-NEW', 'serialNumber': 'SYNTHETIC-SERIAL', 'assetType': 'LAPTOP', 'purchasedAt': '2026-01-01', 'departmentId': 'synthetic-department'},
     ['자산 관리자 계정과 중복되지 않는 자산번호·일련번호 및 유효한 필수 입력을 준비한다.'])
approval = section('loan-rules', '부서장 승인과 자기 승인 금지')
plan('duplicate-approval', 'EXCEPTION', approval, '취소되었거나 이미 승인된 신청을 다시 승인하면 상태 충돌 오류를 반환한다.', loan_api, 'POST /loans/{loanId}/approve',
     '자산 재고 충돌은 HTTP 409 ASSET_NOT_AVAILABLE, 신청 상태 충돌은 HTTP 409 LOAN_STATE_CONFLICT다.', [http(409), token('LOAN_STATE_CONFLICT')],
     preconditions=['승인 권한이 있는 부서장 계정과 이미 APPROVED인 대여 신청을 준비한다.'])

policy_path.write_text(json.dumps(policy, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
print('Policy plans:', len(policy['plans']))
