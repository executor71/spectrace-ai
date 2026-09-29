# Phase 4: 근거 기반 TestCase Generation

## 입력과 신뢰 경계

Spring Boot가 저장된 Requirement 및 Phase 3 Analysis를 읽고 기존 AnalysisValidator로 재검증한다. 생성 경로는 검색을 다시 수행하지 않으며 Ground Truth 또는 evaluation DB에 접근하지 않는다. AI Service는 입력된 분석 snapshot만 사용한다. 기존 Phase 2 검색/임베딩 및 Phase 3 분석 구현은 변경하지 않는다.

`POST /api/requirements/{id}/test-cases/generate`는 새 batch를 생성하고, `GET /api/requirements/{id}/test-cases`는 저장된 batch와 원본 분석 snapshot을 반환한다. 분석이 없으면 409 ANALYSIS_REQUIRED, 결과가 없으면 404 TEST_CASES_NOT_FOUND다. 모델 형식/근거 검증 실패는 502, 모델 연결 실패는 503, 동시 AI 생성 요청은 429다.

## 생성 및 서버 검증

공유 읽기 전용 `contracts/test-case-policy.json`에는 대여 승인용 5개 테스트 계획과 근거 인용문, API AllowList가 있다. Python과 Java는 각각 저장된 confirmed condition, relatedApis, evidence 안의 필수 인용문을 확인하여 사용 가능한 계획을 계산한다. 조건/인용문이 맞지 않는 계획은 모델에 제공하지 않는다.

모델은 원문, 분석 및 사용 가능한 계획을 입력받아 candidateIds만 Structured Output으로 선택·정렬한다. 기대결과, API, evidence를 직접 작성할 수 없다. 모델 응답은 strict schema와 허용 ID/중복/누락 검사에 통과해야 하며 한 번만 재시도한다. 실패 시 저장하지 않는다. 선택된 계획을 서버가 10개 필드의 TestCase로 구체화한다. Spring은 AI 응답을 자체 계산 결과와 정확히 비교하므로 임의의 기대결과/업무규칙/API/근거/실행 가능성 수정은 저장 단계에서 거부된다.

이는 자유 생성형 범용 테스트 생성기가 아닌 **근거 검증 템플릿 기반 PoC**다. 현재 대여 부서장 승인과 자기 승인 금지 조건을 지원한다. 다른 확정 조건은 테스트 절차·판정 기준 확인 필요로 반환한다. 템플릿 확장은 코드/정책 검토와 추가 검증이 필요하다. 근거 없는 일반화를 하지 않는다.

ambiguousExpressions, missingConditions, clarificationQuestions 중 하나라도 있으면 전체 생성을 보류하고 clarificationRequired로 반환한다. 부분적으로 확정된 조건이 있어도 보류하는 보수적 정책이다. 확정 조건이 없거나 사용 가능한 계획이 없을 때도 LLM을 호출하지 않는다. 따라서 불충분한 입력에서 불필요한 모델 호출을 하지 않는다.

## 출력

TestCase 필드: testCaseId(UUID), requirementId(UUID), type(NORMAL/EXCEPTION/AUTHORIZATION/BOUNDARY/BUSINESS_RULE), scenario, preconditions[], input(object), steps[], expectedResult(description + assertions[]), evidence(documentId/chunkId 쌍만), executable(boolean).

batch에는 clarificationRequired, uncoveredTypes, policyHash, llmCalls, generationId, createdAt, generationLatencyMs, sourceAnalysis, stale, executionDecisions를 추가한다. evidence의 실제 인용문/유형/score는 sourceAnalysis.evidence에서 확인한다. testCase evidence는 해당 snapshot의 ID만 참조한다.

BOUNDARY는 같은 부서/타 부서라는 권한 범위 경계다. 문서에 없는 수치 경계를 만들어 내지 않는다. input의 UUID, comment, actorFixture는 합성 시험 데이터이며 새 업무규칙이 아니다. expectedResult.description은 원본 문장의 정확한 인용이며 assertion은 해당 문장의 상태·HTTP 코드·오류 토큰·상태 불변성을 표현한다. 오류 응답에 문서화되지 않은 JSON 경로를 가정하지 않는다.

## 실행 가능성

API AllowList, Method/Endpoint, 사전조건 재현, Input 정의, 코드 판정의 5개 조건이 모두 true일 때만 executable 후보가 된다. 현재 fixtureReady=false이므로 모든 실제 결과는 false다. 합성 계정/장비 상태를 만드는 fixture provider 및 실제 API adapter는 구현하지 않았다. 코드 테스트에서만 준비된 fixture 능력을 주입하여 true 분기와 각 false 분기를 검증한다.

`evaluate_assertions`는 순수 관측값 비교 함수다. HTTP_STATUS, RESPONSE_TOKEN, OBSERVATION_EQUALS, UNCHANGED를 지원한다. 네트워크 실행이나 Dummy API 호출은 하지 않는다. 관측 필드 loanStatus/assetStatus는 향후 adapter가 제공할 비교 입력이며 실제 API response JSON field라는 주장이 아니다. 사용자 Approval/Review 기능도 없다.

## 저장과 동시성

V7은 app.test_case_generation과 app.test_case만 생성한다. 기존 schema/role/default privileges는 변경하지 않는다. batch와 각 TestCase row는 한 트랜잭션으로 교체된다. 모델 호출 중 DB 연결/트랜잭션을 잡지 않는다. 저장 직전에 원본 analysis row를 잠그고 snapshot을 비교한다. 변경되었으면 409 TEST_CASE_SOURCE_CHANGED로 거부한다. 실패한 재생성은 이전 성공 결과를 유지한다.

조회 시 analysis 또는 policyHash가 변경되면 stale=true, executable=false로 반환한다. 원래 분석 snapshot도 보존하여 이전 근거를 최신 근거와 혼동하지 않게 한다. generationId와 testCaseId는 성공적인 재생성 시 새 값이다.

## 범위 제외

TestCase 실행, Approval/Review, Ground Truth Evaluation, Hybrid/Reranking, Query Rewrite, GraphRAG, MCP는 포함하지 않는다. 모델의 임의 주장을 저장하지 않는 것은 구조적으로 제한하지만 템플릿 자체의 오류 가능성까지 수학적으로 보장하는 것은 아니다. 원문 근거와 템플릿은 검토 가능한 파일로 남긴다.

## 검증 실행

실행 환경은 `docker compose up --build -d`로 구성한다. 앱 런타임은 컨테이너 이미지이며 호스트 PostgreSQL/JDK/Python 설치를 전제로 하지 않는다. 아래 Python 스크립트는 개발 검증 도구다.

개발: Phase 4 Python 코드 테스트와 Backend 통합 테스트 → `docs/scripts/phase4-live.py smoke` (2개 사례; 충분 근거 1회 모델 호출, 부족 근거 0회).

완료 직전: Python 전체 코드 테스트, 격리 Compose Backend 전체 테스트, phase4-regression.py (health/고정 Vector Top-5 8건/보호 파일 hash), phase4-analysis-regression.py (기존 5개 Phase 3 사례, 한 차례), phase4-live.py final (5개 Phase 4 사례), phase4-boundary.sql 및 runtime-security.py, phase4-browser.py. 모델 검증과 코드 검증 로그는 분리한다. 일반적인 재실행에서는 final 스크립트가 실제 LLM을 호출함에 유의한다.
