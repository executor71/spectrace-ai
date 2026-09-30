# Phase 5 TestCase Review / Approval

## 저장과 상태

Phase 4 기준점은 `docs/phase4-baseline/source.zip`과 `sha256.json`에 보존했다. 기존 migration V1~V7, AI 생성 정책·모델·프롬프트, Requirement, Vector RAG, Analysis, corpus, DB 역할은 변경하지 않았다.

`app.test_case.result_json`은 생성 시 검증된 AI 원본이다. API의 `generatedContent`가 이 원본을 그대로 반환한다. `reviewed_content`에는 type/scenario/preconditions/input/steps/expectedResult만 저장한다. API의 `reviewedContent`는 이 객체 또는 null이다. 최상위 내용 필드는 수정본을 원본 위에 합성한 현재값이다. 원본과 모든 편집 가능 항목이 동일해지면 reviewedContent=null, modified=false가 된다.

V8은 reviewed_content, approval_status, reviewed_at, reviewer, review_comment, review_revision을 추가한다. 기존 행도 DRAFT/revision=0으로 초기화한다. DRAFT/APPROVED/REJECTED CHECK, Review JSON 허용 키 CHECK, 검토 메타데이터 CHECK, AI 원본과 식별자 변경 차단 트리거를 둔다. 역할/권한 추가는 없다.

생성은 DRAFT다. 사용자 PATCH 성공은 이전 승인·반려 여부와 관계없이 DRAFT로 전환하고 검토자·시각·의견을 초기화한다. 승인/반려는 전용 POST에서만 일어난다. 모든 현재 상태에서 수정·승인·반려를 허용하되 오래된 revision은 409다. 별도 MODIFIED 상태나 다단계 이력은 없다. 승인/반려 이력 전체가 아닌 최신 결정만 보관한다.

승인은 필수 필드, 현재 분석/정책, 원본이 Phase 4 정책 후보와 일치하는지, 기존 evidence 동일성을 검증한다. 수정 내용 자체가 업무적으로 올바른지는 사용자 검토 책임이다. 반려는 stale인 테스트에도 허용한다. 잘못된 원본/근거 또는 stale 승인은 409다.

재생성은 기존 Phase 4의 batch 교체 동작을 유지한다. 이전 ID와 검토 결과는 교체되고 새 ID는 DRAFT다. 과거 generation을 보관하는 versioning은 추가하지 않았다.

## API

| Method | Path | 결과 |
|---|---|---|
| PATCH | /api/test-cases/{id} | 허용된 내용만 부분 수정, DRAFT 전환 |
| POST | /api/test-cases/{id}/approve | 검증 후 APPROVED |
| POST | /api/test-cases/{id}/reject | REJECTED |
| GET | /api/requirements/{requirementId}/test-cases | 기존 목록에 원본·수정본·Review 메타데이터 추가 |
| POST | /api/requirements/{requirementId}/test-cases/generate | 기존 생성 유지, 새 결과는 DRAFT |

세 변경 API는 현재 GET 응답의 정수 `reviewRevision`을 필수로 받는다. 행 잠금과 revision 비교로 같은 버전을 읽은 요청 간 덮어쓰기를 방지한다. 성공 시 revision을 1 증가시킨다. 없는 UUID는 404, UUID 형식/JSON/enum/내용/허용하지 않은 필드는 400, revision 충돌은 409다.

PATCH 예:

```json
{"reviewRevision":0,"scenario":"유지보수 개발자가 검토한 시나리오"}
```

승인/반려 요청 예 (reviewer와 reviewComment는 선택):

```json
{"reviewRevision":1,"reviewer":"demo/local","reviewComment":"근거와 수정 내용을 확인했습니다."}
```

type은 NORMAL/EXCEPTION/AUTHORIZATION/BOUNDARY/BUSINESS_RULE만 허용한다. scenario는 공백이 아닌 문자열, preconditions는 문자열 배열, steps는 비어 있지 않은 문자열 배열, input은 JSON 객체, expectedResult는 description 문자열과 assertions 객체 배열이다. 빈 preconditions와 빈 assertions는 수동 테스트를 위해 허용된다. 크기 제한으로 과도한 입력을 거부한다. reviewer는 인증되지 않은 데모 표시값이며 생략 시 demo/local이다.

requirementId, evidence, documentId/chunkId, executable, approvalStatus, generatedContent, reviewedContent 및 Review 메타데이터를 PATCH로 설정할 수 없다. 승인/반려 요청에도 revision/reviewer/reviewComment 이외의 키를 허용하지 않는다.

## 실행 경계

executable은 기존 TestCasePolicy.gates로 현재 편집 내용에 대해 계산한다. approvalStatus는 이 계산에 영향을 주지 않는다. source가 stale이면 기존 동작처럼 executable=false다. executionEligible은 `executable && approvalStatus == APPROVED`로 계산하는 읽기 전용 값이다. 기술적으로 false인 수동 테스트도 사용자가 승인할 수 있다.

현재 fixtureReady=false이므로 실제 저장된 다섯 TC는 승인 후에도 executable=false다. true인 경우의 독립성과 조합은 Backend 단위 테스트로 검증했다. 실행 API, Dummy 호출, PASS/FAIL, Evaluation은 구현하지 않았다.

## UI

기존 Requirement 조회 → 저장된 Analysis → 저장된 TestCase 목록·상세 흐름에 Review를 추가했다. type/select, scenario, preconditions/steps 줄별 편집, input/expectedResult JSON 편집, 수정 저장, 검토자/의견, 승인/반려를 제공한다. 저장 전 승인·반려 버튼을 막고 오류를 표시한다. Evidence는 읽기 전용이며 AI 원본을 펼쳐 비교할 수 있다. 수정 저장 후 목록을 재조회하여 실행 조건도 최신값으로 표시한다. 새로고침 후 요구사항 ID로 재조회하면 DB 값이 유지된다.
