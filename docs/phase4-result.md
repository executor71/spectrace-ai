# Phase 4 완료 결과

Phase 3 기준점: `docs/phase3-baseline/source.zip` 및 `sha256.json`. Phase 2 Vector RAG와 Phase 3 분석 구현, 기존 migration V1~V6, schema/role 경계를 유지했다.

## 결과

대여 승인 확정 조건에서 NORMAL / EXCEPTION / AUTHORIZATION / BOUNDARY / BUSINESS_RULE 5개 유형을 생성하고 DB 저장·조회 및 React 목록/상세/근거 표시를 확인했다. 미확정·근거 부족 사례는 테스트 0건과 확인 필요 항목으로 분리했다. Phase 5 기능은 구현하지 않았다.

| 대표 사례 | 생성 수 | 확인 필요 | LLM 호출 | HTTP latency (s) |
|---|---:|---:|---:|---:|
| sufficient | 5 | 0 | 1 | 76.217 |
| ambiguous | 0 | 5 | 0 | 0.038 |
| insufficient | 0 | 3 | 0 | 0.014 |
| nonexistent-rule | 0 | 4 | 0 | 0.021 |
| prompt-injection | 0 | 4 | 0 | 0.029 |

## 생성 예시와 근거

전체 JSON은 `phase4-evidence/final-test-cases.json`, 단일 TC는 `phase4-evidence/test-case-example.json`에 보관했다.

```json
{
  "testCaseId": "c53be0ea-3157-49be-a922-efa378d6ca11",
  "requirementId": "b5270f71-c92c-48ae-8530-8946f1cfce62",
  "type": "NORMAL",
  "scenario": "같은 부서 직원의 신청을 부서장이 승인한다.",
  "preconditions": [
    "합성 계정과 부서 관계를 시험 환경에 준비한다: same-department-manager",
    "합성 대여 신청의 상태는 PENDING_APPROVAL이다.",
    "해당 자산의 상태는 AVAILABLE이다.",
    "상태 변경 비교를 위해 실행 전 신청 상태와 자산 상태를 기록한다."
  ],
  "input": {
    "method": "POST",
    "endpoint": "/loans/{loanId}/approve",
    "pathParameters": {
      "loanId": "00000000-0000-4000-8000-000000000041"
    },
    "body": {
      "comment": "합성 검증"
    },
    "actorFixture": "same-department-manager"
  },
  "steps": [
    "사전조건과 합성 계정의 역할 및 부서 관계를 확인한다.",
    "지정 계정으로 input의 승인 요청을 보낸다.",
    "응답과 실행 전후 상태를 expectedResult의 판정 기준과 비교한다."
  ],
  "expectedResult": {
    "description": "성공 시 HTTP 200과 status=APPROVED를 반환하고 자산은 RESERVED가 된다.",
    "assertions": [
      {
        "kind": "HTTP_STATUS",
        "value": 200
      },
      {
        "kind": "OBSERVATION_EQUALS",
        "field": "loanStatus",
        "value": "APPROVED"
      },
      {
        "kind": "OBSERVATION_EQUALS",
        "field": "assetStatus",
        "value": "RESERVED"
      }
    ]
  },
  "evidence": [
    {
      "documentId": "7cea4fe7-6b00-56c9-be35-3194aeecb923",
      "chunkId": "29068730-5e86-57f1-bee2-ffaae1575a08"
    },
    {
      "documentId": "7cea4fe7-6b00-56c9-be35-3194aeecb923",
      "chunkId": "fac8b9c8-cab2-54a6-a555-f938e47ec23a"
    },
    {
      "documentId": "e7cb1b5c-9e68-5f36-b3cb-96c36d4f3520",
      "chunkId": "7c7eda12-4b56-5ad1-a30d-627031666355"
    },
    {
      "documentId": "34b91c10-3bd5-547e-97c2-18641d80eb14",
      "chunkId": "d10c2901-6178-56c5-a019-c45bb1ce5520"
    }
  ],
  "executable": false
}
```

| 유형 | 기대결과 | executable |
|---|---|---|
| NORMAL | 성공 시 HTTP 200과 status=APPROVED를 반환하고 자산은 RESERVED가 된다. | false |
| EXCEPTION | 본인 신청 승인 시 HTTP 403 SELF_APPROVAL_FORBIDDEN을 반환한다. | false |
| AUTHORIZATION | 일반 직원, 타 부서 부서장, 신청자 본인의 승인은 HTTP 403으로 거부되어야 한다. | false |
| BOUNDARY | 일반 직원, 타 부서 부서장, 신청자 본인의 승인은 HTTP 403으로 거부되어야 한다. | false |
| BUSINESS_RULE | 거부된 요청은 신청 상태와 자산 상태를 변경하지 않아야 한다. | false |

각 TC의 evidence는 Phase 3 snapshot에 존재하는 documentId/chunkId 쌍만 참조한다. API 명세, 부서장 승인/자기 승인 금지 규칙, AVAILABLE 전제, 권한 테스트 가이드의 정확한 인용문이 모두 충족될 때만 해당 계획을 사용한다. 기대결과/API/근거를 모델이 임의로 추가하면 서버의 정확 일치 검증에서 거부한다.

| documentId | chunkId | 역할 |
|---|---|---|
| 7cea4fe7-6b00-56c9-be35-3194aeecb923 | 29068730-5e86-57f1-bee2-ffaae1575a08 | BUSINESS_RULE / 부서장 승인과 자기 승인 금지 |
| 34b91c10-3bd5-547e-97c2-18641d80eb14 | d10c2901-6178-56c5-a019-c45bb1ce5520 | TEST_GUIDE / 대여 승인 권한 테스트 |
| e7cb1b5c-9e68-5f36-b3cb-96c36d4f3520 | 7c7eda12-4b56-5ad1-a30d-627031666355 | API_SPEC / POST /loans/{loanId}/approve 승인 |
| 7cea4fe7-6b00-56c9-be35-3194aeecb923 | fac8b9c8-cab2-54a6-a555-f938e47ec23a | BUSINESS_RULE / 동시 승인과 자산 예약 |

## executable 판정

현재 실제 결과는 모두 false다. API AllowList, Method/Endpoint, Input 정의, 코드 판정 가능성은 통과하지만 사전조건 재현용 fixture provider가 없어 해당 조건은 false다. 코드 테스트에서만 fixture 능력을 주입하여 5개 조건이 모두 충족될 때 true가 되고, 각각 하나라도 실패하면 false가 됨을 확인했다. true는 실행 후보일 뿐 사용자 승인이나 API 실행을 의미하지 않는다.

## 검증

- Python 61건 / Backend 39건 통과. 실제 모델 없는 코드 검증과 모델 검증 로그를 분리했다.
- 개발 smoke 2개 사례: 충분 근거 5개 생성(LLM 1회), 부족 근거 생성 보류(LLM 0회). 첫 HTTP 생성 226.447초. 중복 프롬프트 설명을 축약한 뒤 최종 사례에서 검증했다.
- 완료 직전 Phase 3 대표 5건 전체 통과. Phase 4 대표 5건 전체 통과. 불필요한 전체 모델 재실행 없음.
- Phase 0 health 2개 UP, PostgreSQL/pgvector 정상, Flyway V1~V7 성공. app/rag/evaluation 역할 경계 유지.
- Phase 1 등록/조회/Validation 회귀 통과. Phase 2 9문서/27chunk 유지, 8개 질의 Top-5와 score 기준점 동일.
- evaluation probe에는 실제 데이터를 넣고 evaluation_reader의 읽기 성공과 rag_reader의 SQLSTATE 42501 거부를 비교했다. probe는 rollback했다. 실제 AI runtime도 app/evaluation 접근 거부, 추가 DB 자격증명 없음.
- React에서 5개 유형 상세와 evidence, 4개 보류 사례, 새로고침 후 저장 결과 및 모바일 너비를 검증했다. 추가 모델 호출 없이 보류 사례 POST 버튼도 확인했다.
- 임의 candidate/API/expectedResult/evidence/executable, 중복 ID, 정책 불일치, 스키마 오류를 코드 테스트로 거부했다. LLM 형식 오류는 최대 1회 재시도 후 502 실패 처리한다. 재생성 실패 시 이전 결과 유지, 분석 변경 시 409, 이전 snapshot 조회 시 stale 처리도 확인했다.

## latency와 명령 시간

HTTP/생성 latency는 `final-test-cases.json`의 httpElapsedSeconds 및 generationLatencyMs에 별도 기록했다. 명령 자체 시간은 PowerShell Stopwatch, 최초 도구 반환 시간은 호출 전후 wall clock으로 측정했다. 비동기 session 반환은 작업 완료 시간이 아니며 표의 두 수치를 혼동하면 안 된다. `phase4-evidence/timings.json` 참조.

| Phase 3 실제 모델 회귀 | HTTP latency (s) |
|---|---:|
| sufficient | 116.006 |
| ambiguous | 85.201 |
| insufficient | 79.212 |
| nonexistent-rule | 78.556 |
| prompt-injection | 71.705 |

## 제한 및 미해결 사항

- 안전한 템플릿 기반 PoC이며 현재 대여 승인/자기 승인 금지 조건만 구체적인 5개 유형을 지원한다. 범용 자유 생성이나 임의 업무 도메인 지원은 구현하지 않았다. 지원되지 않는 확정 조건은 명시적으로 확인 필요로 반환한다.
- ambiguous/missing/question이 하나라도 있으면 전체 생성을 보류한다. 부분 생성은 지원하지 않는다.
- 사전조건 fixture와 실제 API adapter가 없으므로 실행 가능한 실제 TC는 없다. 사용자 승인, Dummy 실행, 최종 Evaluation은 범위 밖이다.
- 로컬 CPU LLM latency가 크다. 기존 모델/검색 구조를 유지했으며, 모델 출력의 구조적 제한은 템플릿 자체의 무오류까지 보장하지 않는다.

## 변경 파일

기존 파일 변경:

- `compose.test.yaml`
- `compose.yaml`
- `frontend/src/Requirements.tsx`
- `frontend/src/style.css`
- `ai-service/app/main.py`

추가 구현/검증 파일:

- `ai-service/app/test_case_api.py`
- `ai-service/app/test_case_models.py`
- `ai-service/app/test_case_policy.py`
- `ai-service/app/test_case_service.py`
- `ai-service/tests/fixtures/test-case-analysis.json`
- `ai-service/tests/test_test_case_generation.py`
- `backend/src/main/java/com/example/legacyassistant/testcase/TestCaseAdvice.java`
- `backend/src/main/java/com/example/legacyassistant/testcase/TestCaseClient.java`
- `backend/src/main/java/com/example/legacyassistant/testcase/TestCaseController.java`
- `backend/src/main/java/com/example/legacyassistant/testcase/TestCaseException.java`
- `backend/src/main/java/com/example/legacyassistant/testcase/TestCasePolicy.java`
- `backend/src/main/java/com/example/legacyassistant/testcase/TestCaseRepository.java`
- `backend/src/main/java/com/example/legacyassistant/testcase/TestCaseService.java`
- `backend/src/main/resources/db/migration/V7__store_grounded_test_cases.sql`
- `backend/src/test/java/com/example/legacyassistant/testcase/TestCaseIntegrationTest.java`
- `backend/src/test/resources/test-case-analysis.json`
- `contracts/test-case-policy.json`
- `docs/phase4-design.md`
- `docs/phase4-result.md`
- `docs/phase4-test-cases.schema.json`
- `docs/scripts/phase4-analysis-regression.py`
- `docs/scripts/phase4-boundary.sql`
- `docs/scripts/phase4-browser.py`
- `docs/scripts/phase4-live.py`
- `docs/scripts/phase4-regression.py`
- `docs/scripts/phase4-runtime-security.py`
- `frontend/src/TestCases.tsx`

상세 설계: `phase4-design.md`. 코드/DB/모델/브라우저 증거: `phase4-evidence/`. 비밀값을 결과나 저장소에 추가하지 않았다.
