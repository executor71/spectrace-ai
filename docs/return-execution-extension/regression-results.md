# 반납 자동 실행 확장 회귀 결과

| 검사 | 실제 결과 |
|---|---|
| Spring 전체 | 141개, failures/errors/skipped 0. 기존 117개 + 신규 24개 |
| ai | 76개 통과 |
| retrieval | 27개 통과 |
| evaluation-metrics | 22개 통과 |
| evaluation-api | 12개 통과 |
| mcp | 18개 통과 |
| graph-projection | 18개 통과 |
| graph-analysis | 4개 통과 |
| observability | 9개 통과 |
| 평가 DB/GT 역할 경계 | 격리 DB 9개 통과, 동결 데이터셋 hash 확인 |
| 프런트엔드 | TypeScript + Vite build 통과 |
| 실제 Chrome E2E | 1440px, 390px; 승인 차단·준비·승인·PASS/FAIL/ERROR·reload·Excel 확인 |
| 실제 실행 결과 저장·재조회 | 6개 실행, 원본 분석·generationId 유지, 새 LLM 호출 0회 |
| MCP | 8개 기존 Tool·엄격한 입력 계약 유지, 반납 4개 적격성 조회, override 거부. 추가 실행 없음 |
| Graph | 기존 projection으로 실제 Execution 6개와 EXECUTED_AS 6개 확인 |
| Jaeger | PASS/FAIL/ERROR 실행 ID별 Trace 및 AllowList·Fixture·호출·판정 span 확인, 본문 태그 없음 |
| 보호 파일 | 26개 hash 동일. RAG 문서·15개 생성 정책·GT·평가 코드/데이터 불변 |

## 실제 실행

| 기록 | 결과 | API / 관측 |
|---|---|---|
| return-pass | PASS | API-RETURN-CREATE, 승인 revision 2, executionId `6e8fb563-fbd9-4b03-975f-dd6699077c0f` |
| duplicate-pass | PASS | API-RETURN-CREATE, 승인 revision 2, executionId `c949daa3-593a-4fca-b247-61b99bb3534d` |
| authorization-pass | PASS | API-RETURN-CREATE, 승인 revision 2, executionId `09bd228b-7a8a-448d-892e-c995c7a5fa2d` |
| return-fail | FAIL | API-RETURN-CREATE, 승인 revision 2, executionId `40179f20-9335-4705-910c-cfaa16f6083f` |
| return-error | ERROR | API-RETURN-CREATE, 승인 revision 4, executionId `08d3c4f8-a981-4465-aab0-90f96ec1118c` |
| return-restored-pass | PASS | API-RETURN-CREATE, 승인 revision 6, executionId `bba2f38c-c97b-432d-a8e9-cc0791a00f46` |

- 정상 접수: HTTP 201 + INSPECTION_PENDING + 반납 이력 1건 + ON_LOAN 유지.
- 중복: 409 RETURN_ALREADY_REQUESTED, 전체 관측 상태/이력 수 불변. 권한: 403 ACCESS_DENIED, 상태 불변.
- 의도적 결함: Expected/Actual HTTP는 둘 다 201, state.assetStatus가 ON_LOAN/AVAILABLE로 달라 실제 comparator FAIL.
- ERROR: 명시적인 Fixture 초기화 예외, API 미호출, fixtureBefore=null, errorStage=FIXTURE_INITIALIZATION. 정상 Fixture로 재준비·재승인한 뒤 PASS로 복구.
- Dashboard 현재 revision 기준: APPROVED 4, 일반 PASS 3, 일반 FAIL 0, 일반 ERROR 0, 미실행(일반) 1, synthetic 1. 과거 ERROR revision은 현재 통계 제외.
- Excel은 6개 전체 실행의 PASS/FAIL/ERROR·revision·API·Expected/Actual·불일치를 보존했다. 현재 revision과 과거 이력을 구분하며 수식 셀은 생성하지 않았다.

## HITL 및 보안 검증

DRAFT/REJECTED 차단, 준비/수정 후 재승인, 과거 If-Match 거부, 원본 TC·Evidence·검토본 불변, 이력 영속성, 외부 URL·알 수 없는 필드 거부, 실행 body override 거부, 부족한 Fixture 차단, assertion 약화 차단, 다른 허용 Adapter로 돌리는 경로 변경 차단을 검사했다.
동시 40개 표준/고의 결함 Fixture의 상태 격리를 확인했다. 네트워크 장애는 SocketTimeoutException을 가진 mock Adapter 예외로 ERROR 저장을 확인했으며 실제 외부 네트워크는 호출하지 않았다.

## 검증 중 수정

- 초기 React 콜백 타입을 동기/비동기 기존 인터페이스와 호환되도록 수정했다.
- 신규 검사 테스트 Fixture에 빠졌던 원문 조건을 보완했다. 새 Excel 통합 테스트는 결과 열 인덱스를 실제 헤더와 일치시켰고 revision·수식 검사까지 유지했다. 기존 테스트 assertion은 약화하지 않았다.
- 최종 테스트 실패는 없다. 신규 범위를 벗어난 시나리오는 실행하지 않고 명시적으로 차단한다.

## 알려진 한계

- 검사 성공의 HTTP 상태 및 대여 기록 완료 상태 전이는 합성 명세에 없어 자동 실행 미지원이다. 정상 반납은 접수와 검사 전 자산 불변까지 검증한다.
- 동작 상태는 실행별 메모리다. 실제 자산/대여 DB는 변경하지 않으며 실행 감사 이력만 DB에 저장한다. 운영 사용자 인증을 새로 구현한 것이 아니다.
- Neo4j 운영 수집 scope와 canonical Api 목록은 기존 그대로다. 새 반납 요구사항에 대해 projection을 검증했지만 운영 Graph 자동 반영/Schema 확장은 수행하지 않았다.
- ERROR 실서비스 증거는 명시적 초기화 오류 주입이며 실제 서비스/네트워크 중단 시험이 아니다.
- 생성 시 executable=false 기록과 런타임 eligibility는 별도다. DB 일괄 활성화·재생성·재분석은 하지 않았다.

## 수정 파일

- backend testcase: 신규 ReturnExecutionAdapter.java, DummyApiRegistry.java, ExecutionComparator.java, ExecutionService.java, ExecutionController.java, TestCasePolicy.java(원본 검증 helper), TestCaseReviewService.java, TestCaseReviewController.java
- backend observability: Tracing.java, WorkflowAspect.java
- 신규 테스트: ReturnExecutionIntegrationTest.java(20개), ReturnExecutionAdapterTest.java(4개), return-execution-inspection.json
- frontend: TestCaseExecutions.tsx, TestCaseReview.tsx, style.css
- docs/return-execution-extension/: 문서·검증 코드·실제 결과 JSON/PNG/XLSX
- 기존 Java 업그레이드·리디자인·랜덤 예제 미커밋 변경은 보존했다. 생성 정책 JSON·LLM/RAG·Job Queue·GT·평가셋·MCP Tool·Graph Schema는 변경하지 않았다.
- 커밋·Push·Phase 15 개발은 수행하지 않았다.

검증 자료: backend-results.json, regression-results.json, browser-results.json, trace-results.json, graph-results.json, mcp-results.json, protected-audit.json 및 각 실행 JSON. raw 로그와 JUnit는 OS temp/spectrace-return-execution에 보관한다.
