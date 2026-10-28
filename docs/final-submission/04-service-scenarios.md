# 04. 업무 시나리오와 API·화면 연결

조사일 2026-10-28. 구현 경로와 저장된 실제 증거를 연결한다. 이번에는 저장·분석·생성·승인·실행 요청을 새로 수행하지 않았다. 화면은 보관된 PNG이며 현재 UI 전체를 재촬영한 것이 아니다.

## 요구사항에서 실행·추적까지

| 업무 단계 | 실제 API | 주요 구현 | 사용 데이터 / 결과 화면·증거 |
|---|---|---|---|
| 1 변경 요구사항 입력 | POST `/api/requirements`, GET `/{id}` | `backend/.../requirement/RequirementController.java`, `frontend/src/Requirements.tsx` | 서버 UUID/DRAFT/본문 저장; `docs/phase1-evidence/requirement-desktop.png` |
| 2 관련 근거 검색 | AI POST `/internal/v1/search`; 비교 검색은 Retrieval `/internal/v1/retrieval` | `ai-service/app/vector_search.py`, `retrieval-service/retrieval/core.py` | 합성 문서·청크ID/Section/score; `docs/phase12-ui-evidence/analysis-desktop.png`의 Evidence |
| 3 Qwen 분석 | POST `/api/requirements/{id}/analysis-jobs`, GET `/api/analysis-jobs/{jobId}`; 기존 동기 분석 유지 | `jobs/JobWorker.java`, `analysis/AnalysisClient.java`, `app/analysis_service.py`, `llm_provider.py` | Qwen·Schema/근거 검증·저장; `docs/phase14-evidence/real-job-succeeded.png`, 복구 분석 로그/Trace |
| 4 TC 생성 | POST `/api/requirements/{id}/test-cases/generate`, GET 같은 TC 경로 | `testcase/TestCaseService.java`, `app/test_case_service.py`, `test_case_policy.py` | 저장 분석+정책+근거, 불변 생성본·배치·policyHash·clarification; `docs/testcase-policy-extension/return-desktop.png` |
| 5 검토·승인 | PATCH `/api/test-cases/{id}`, POST `/{id}/approve` 또는 `/reject` | `TestCaseReviewService.java`, `frontend/src/TestCaseReview.tsx` | 검토본·revision·승인 상태. Fixture 준비도 revision 증가/DRAFT; `docs/phase12-ui-evidence/review-desktop.png` |
| 6 Dummy 실행 | GET `/{id}/execution-eligibility`, POST `/{id}/executions` | `ExecutionService.java`, `DummyApiRegistry.java`, `ReturnExecutionAdapter.java` | 승인된 저장 TC만, 실행 body 금지; `docs/return-execution-extension/return-blocked.png`, `return-pass.png` |
| 7 Expected/Actual 비교 | 실행 API 내부 | `ExecutionComparator.java` | HTTP/token/상태/불변 비교; Expected/Actual/mismatches 저장; LLM 호출 없음 |
| 8 PASS/FAIL/ERROR·이력 | GET `/api/executions/{id}`, GET `/api/test-cases/{id}/executions` | `ExecutionController.java`, `frontend/src/TestCaseExecutions.tsx` | `docs/return-execution-extension/return-pass/fail/error.json` 및 개별 PNG. ERROR를 FAIL과 분리 |
| 9 관계 추적 | Graph POST `/api/graph/find_requirement_context`, `/find_impacted_tests`, `/trace_test_case_origin` | `graph-service/app/source.py`, `queries.py`, `frontend/src/KnowledgeGraph.tsx` | 존재하는 규칙→API→TC→실행 경로; `docs/phase11-evidence/testcase-origin-path.png` |
| 10 변경 영향 분석 | GET `/api/change-impacts/baselines/{id}` → POST `/api/change-impacts` → `/{id}/analysis-jobs` → GET `/{id}/results` → POST `/{id}/reviews` | `impact/ChangeImpactService.java`, `app/change_impact.py`, `frontend/src/ChangeImpact.tsx` | 동결 Baseline·별도 변경안·검토 후보; `docs/phase15-evidence/condition-comparison.png` |

`backend/...`의 전체 prefix는 `backend/src/main/java/com/example/legacyassistant/`다. 테스트·원본 결과·화면의 클릭 가능한 매핑은 [05](05-implementation-evidence.md), [09](09-evidence-index.md)에 있다.

## 반납: 같은 업무의 단계별 증거

- Requirement `c9e5d1d8-6de2-487e-8ae6-9cf6c7b99eae`: 기존 저장 분석4조건을 사용했다. 그 분석의 실제 모델 호출 수를 이번에 새로 확정한 것은 아니다.
- [실제 Qwen TC 생성](../testcase-policy-extension/return-scenario-tests.json)은1회, TC4개, HTTP200, 브라우저 재조회 포함104.327초다. 부속품·접수일·담당자 기록 조건은 미지원으로 남아 PARTIALLY_GENERATED였다.
- 반납 실행 확장은 생성본/Evidence를 유지하고 검토본에 닫힌 Fixture를 준비·재승인했다. [정상](../return-execution-extension/return-pass.json): 201/INSPECTION_PENDING/asset ON_LOAN/이력1건 → PASS.
- [의도적 결함](../return-execution-extension/return-fail.json): HTTP는 둘 다201이지만 assetStatus ON_LOAN/AVAILABLE 불일치로 FAIL. [초기화 오류](../return-execution-extension/return-error.json)는 API 미호출 ERROR, [재준비 후 복구](../return-execution-extension/return-restored-pass.json)는 PASS다. 실행 확장 검증의 신규 Qwen 호출은0회다.

**현재와 과거를 구분한다.** 이번 GET에서 과거 실행4종은 모두200으로 재조회됐다. 현재 활성 generationId=`c007519e-fe3b-49e5-8b79-b0dcfe1b20c9`, 과거 실행 generationId=`be9667b9-f10f-49b6-badf-571fd479a491`다. 현재 TC4개는 모두DRAFT이고 과거 승인 TC는 현재 배치에 없다. 과거 실행 증거로 현재 배치도 승인됐다고 설명하지 않는다.

현재 Graph 읽기 조회 `2026-10-28T06:14:46.221860+00:00`: HTTP200, SYNCED/PARTIAL, nodes10/edges20/TC4/Execution0. `source.collect`는 현재 배치 TC와 해당 실행을 수집한다. 따라서 과거 실행이 DB에서 사라졌다고 해석하거나 모든 과거 실행이 현재 Graph에 연결됐다고 주장하지 않는다.

## 실제 고정 LangGraph 시나리오

대여 승인 권한을 부서장 또는 자산관리 담당자로 확장하는 **별도 변경 제안**이다. Baseline Requirement `80e2d374-0825-4811-a11e-03ade256b6e8`, impactId `88a0794d-e08b-480f-b6cc-0599ba81b080`. 이 제안이 승인 정책을 바꾸거나 새 역할의 테스트 실행을 허용하지 않는다.

최초 Qwen Job `46e9d66e-8e97-4b1a-a122-60db300927d2`는 유지 조건을 REMOVED로 오분류했다. 원본을 보존하고 캐시+원문 제한 보정 Job `ec5e37bb-3f83-4dab-a09b-43c11d5bed5b`으로 재처리했다(새 Qwen0회). 이번 GET은 후자 SUCCEEDED, 조건3/API후보1/TC후보5/새제안1을 확인했다. 최종 fixture 부합3/3은 최초 모델 의미 정확도100%가 아니다.

화면: [조건 비교](../phase15-evidence/condition-comparison.png), [API 후보](../phase15-evidence/affected-apis.png), [TC 후보](../phase15-evidence/affected-testcases.png), [미지원 새 TC](../phase15-evidence/new-test-suggestions.png), [별도 검토](../phase15-evidence/developer-review.png), [Excel](../phase15-evidence/excel-download.png).

## 제출용 대표 시나리오와 추가 촬영

대표 업무는 **대여 승인·자기 승인 금지의 근거 추적과 변경 영향 검토**가 적합하다. 반납은 HTTP가 같아도 상태 차이로 FAIL을 검출하는 보조 사례로 사용한다. 이는 시연 구성 제안이며 실측 생산성 개선 주장이 아니다.

기존 증거를 편집할 때 실행 ID를 분리한다. 복구 분석 Requirement `b8267284-936f-43a5-a516-6d7d689a6d51`와 TC Requirement `eeaccd3d-75a6-4ade-8865-971ef058534f`는 다르다. TC 입력 분석은 명시된 grounded fixture이며 앞선 Qwen 분석 출력이 아니다. Phase15 역시 별도 Baseline이다.

5분 영상은 업무/근거 → 실제 Qwen 분석 Trace → 정책 TC/승인/MCP Dummy PASS·FAIL → 고정 LangGraph 영향 후보 순서로 구성할 수 있다. 저장된 실행을 여는 장면은 저장 이력 조회로 표시한다. **같은 Requirement에서 입력부터 전 단계까지 연결된 최신 E2E 녹화**와 실제 사람 검토 장면은 추가 증빙이 필요하다. 이번에 이를 실행하거나 사람 승인으로 꾸미지 않았다.

로그 필터/Jaeger 링크: [실제 시연 안내](../observability-recovery/demo-instructions.md). `.actual.log`·표시용 projection·시연 예시를 구분한다.
