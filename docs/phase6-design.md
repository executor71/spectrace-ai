# Phase 6 Evaluation 설계

## 접근 경계

Evaluation은 별도 Python/FastAPI 서비스(port 8090)다. 기존 Java app DB 연결, Python RAG/Analysis/Generation, Review 코드는 변경하지 않았다. app_user와 rag_reader는 evaluation 스키마 및 평가 저장 함수에 접근할 수 없다. evaluation_reader는 app/rag 스키마를 읽지 못한다. 요구사항과 TC는 기존 Backend의 GET, 검색은 기존 `/internal/v1/search`를 사용한다.

Ground Truth는 evaluation 스키마에만 저장하며 평가 전용 데이터 파일은 `evaluation-service/datasets/`에 둔다. Backend와 AI 서비스에는 해당 파일/mount/EVALUATION 자격증명이 없다. 기존 migration_owner의 초기화 권한은 유지한다. Backend V9 migration에는 DDL과 공개 corpus 참조 복사만 포함하며 Ground Truth seed 내용은 포함하지 않는다. seed는 `docs/scripts/phase6-seed.py`가 관리자 초기화 단계에서 수행한다. runtime API에는 Ground Truth 조회·등록·수정 API가 없다.

evaluation_reader의 직접 테이블 쓰기는 금지한다. SECURITY DEFINER `evaluation.record_run` 함수에만 EXECUTE를 부여하여 결과를 append한다. 함수는 고정 search_path와 완전 한정 table 이름을 사용한다. GT, binding, corpus 참조, run의 UPDATE/DELETE는 트리거로 거부한다. GT를 수정하려면 새 버전을 추가해야 하며 기존 결과는 바꾸지 않는다.

## 데이터셋 및 재현성

`phase6-v1`은 synthetic knowledge v1.0.0에 근거한 세 사례다. development는 기존 승인 권한 사례, validation은 새로운 반납 검사 사례, final은 새로운 동시 승인 사례다. 동일 원문을 서로 다른 split에 중복 배정하지 않았다. 같은 자산관리 도메인/corpus를 공유하므로 도메인 외 일반화 평가를 의미하지 않는다.

Ground Truth에는 expectedEvidenceDocumentIds, expectedBusinessRules, expectedApis, requiredTestScenarios, optionalTestScenarios, forbiddenAssertions를 둔다. requiredTestScenarios에는 scenarioId/category/description/requiredConditions가 있다. 규칙은 when + allowedAssertions, 금지 단언은 when + assertion으로 표현한다. 입력 title/description SHA-256과 requirement binding이 일치해야 평가할 수 있다. 공개 입력 파일과 정답 파일을 분리하며 생성 driver는 공개 입력만 읽고 기존 분석/생성 API에 title/description만 보낸다.

GT hash, dataset/split/version, metric version, metric engine hash, requirement/generation/review revision, 실제 Top-5, 평가한 TC와 분석 근거·corpus 참조를 immutable snapshot으로 저장한다. GET은 재평가하지 않고 저장값을 반환한다. 재현은 snapshot의 GT/inputs만 사용하며 검색·LLM·현재 TC를 다시 읽지 않는다. GENERATED(기본값)은 generatedContent이고 REVIEWED는 사용자 현재값이다. 승인 여부로 TC를 필터링하지 않으며 두 모드 결과를 혼합하지 않는다.

## KPI 공식

### Recall@5

질의 q는 고정 요구사항의 title + newline + description이다. 기존 retriever의 상위 **5개 chunk**를 먼저 고른 뒤 documentId를 중복 제거한다. 정답 문서 집합 G, Top-5 chunk의 문서 집합 D5에 대해 `|G ∩ D5| / |G|`. 여섯 번째 chunk는 포함하지 않는다. 분모가 0이면 N/A다. missingDocumentIds=G-D5를 저장한다. LLM Judge, 검색 재작성, reranking을 사용하지 않는다.

### Test Scenario Coverage

`적어도 하나의 유효 TC가 매칭한 required scenario 수 / required scenario 전체 수`.

TC의 category(type)가 같고 한 TC가 해당 requiredConditions를 전부 충족해야 한다. 서로 다른 TC의 조건을 합쳐 통과시키지 않는다. 중복 TC도 같은 scenario 분자를 증가시키지 않는다. 매칭은 JSON pointer의 타입을 포함한 equals, 구조화된 expectedResult.assertions의 항목, 제한적으로 명시적 preconditionState를 사용한다. 시나리오 설명 문자열의 동일성/유사도는 점수에 사용하지 않는다. 코드 validity PASS인 TC만 coverage에 반영한다. optional scenario는 별도 수치로 계산하고 required 분모에 섞지 않는다. 조건 추출이 지원되지 않는 표현을 임의로 semantic match로 인정하지 않는다.

PoC의 structured contract는 actorFixture, method/endpoint, assertion kind/field/value 등 명시적 필드를 사용한다. validation 사진/설명 및 final 동시성 필드도 고정된 구조 계약으로 정의되어 있다. 임의의 동의어/다른 표현 방식에 대한 자동 semantic 매칭은 지원하지 않는다.

### TestCase Validity

`8개 deterministic checklist가 모두 PASS인 TC 수 / 평가 대상 TC 전체 수`.

1. scenario: 공백이 아닌 문자열.
2. preconditions: 문자열 배열로 명시됨(빈 배열도 명시적인 정의로 인정).
3. input: 비어 있지 않은 객체.
4. steps: 비어 있지 않은 문자열 배열.
5. expectedResult: description 문자열과 assertions 배열.
6. evidence: 비어 있지 않은 배열.
7. evidence 참조: documentId/chunkId 쌍이 frozen corpus와 sourceAnalysis에 모두 존재하고 requirementId가 일치.
8. 구조화된 모순: forbiddenAssertions와 충돌하지 않고 적용 가능한 사전 규칙의 허용 assertion에 부합.

알려진 동일 subject의 다른 값이나 금지 단언은 FAIL, 적용 규칙 또는 assertion 의미를 자동 검증할 수 없으면 UNKNOWN이다. UNKNOWN을 PASS로 보지 않으며 전체 TC 분모에 남긴다. 자유 서술의 일반적인 의미적 모순은 `manualSemanticConsistency: NOT_ASSESSED`로 분리한다. 따라서 코드 Validity 100%가 모든 자연어의 의미적 정확성을 보증하지 않는다. TC 0개면 Coverage는 0%, Validity는 N/A이며 100%로 처리하지 않는다.

## API

전용 서비스 `http://localhost:8090` 또는 React proxy `http://localhost:5173`에서 사용한다. 기존 Backend 8080에 평가 로직을 추가하지 않았다.

- POST `/api/evaluations`: 새 평가와 snapshot을 저장하고 201 반환.
- GET `/api/evaluations/{id}`: immutable 저장 결과 조회.
- GET `/api/requirements/{id}/evaluations`: 해당 요구사항의 평가 이력.

```json
{"requirementId":"<UUID>","datasetVersion":"phase6-v1","contentMode":"GENERATED"}
```

현재 지원 datasetVersion은 phase6-v1, contentMode는 GENERATED/REVIEWED다. 임의 GT/TC/search 입력은 API가 받지 않는다. 잘못된 UUID/enum/추가 필드는 400, 없는 요구사항/평가는 404, 미등록 dataset binding 또는 requirement hash 불일치는 409다. 검색/입력 upstream 장애는 FAILED run으로 저장하며 metrics=null이다. KPI가 낮거나 시나리오가 누락된 정상 계산 결과는 COMPLETED로 저장하고 낮은 값을 그대로 표시한다.

## 재실행

1. `docker compose up -d --build`로 V9와 서비스를 준비한다.
2. `python docs/scripts/phase6-seed.py`로 frozen GT를 검증/초기화한다.
3. 공개 생성 입력은 `phase6-generate-inputs.py`로 준비한다. 이 스크립트는 저장된 성공 결과를 재사용하며 정답 파일을 읽지 않는다.
4. `phase6-run.py`가 입력 hash를 확인하고 binding을 등록한 뒤 측정한다.
5. `phase6-tests.py`, `phase6-regression.py`, `phase6-browser.py`, `phase6-runtime.py`로 검증한다.

개발 중 GT seed를 Backend 배포물에서 분리하면서 **신규 V9 초안**의 checksum만 한 번 정리했다. `phase6-evidence/draft-migration-repair.log`에 기록했고 V1~V8 checksum/파일은 변경하지 않았다. 신규 설치와 최종 isolated DB는 최종 V9 + 분리된 seed로 정상 적용/검증했다. 정답 JSON 및 dataset hash는 초기 고정값과 동일하다.
