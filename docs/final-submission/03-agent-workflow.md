# 03. 실제 Agent/Workflow 동작

조사 기준: 2026-10-28 KST. 현재 작업 트리의 소스·저장된 검증 산출물·읽기 전용 재조회가 근거다. 이번 문서 수집에서는 모델 호출, 성능 재측정, 테스트 재실행, 승인·실행·평가 생성, 기능/소스/설정/평가셋 변경을 하지 않았다.

## 고정 Workflow와 Planning의 경계

명시적 `StateGraph`는 **Phase15 변경 영향 분석**의 `ai-service/app/change_impact.py:Workflow.analyze`에 있다. Node3개와 Edge4개가 코드에 고정돼 있다. 기본 요구사항 분석과 TC 생성은 Python 서비스의 고정 함수 흐름이며 LangGraph 전체를 통과한다고 설명하지 않는다.

```mermaid
flowchart LR
 S([START]) --> R[retrieve]
 R --> D[diff]
 D --> I[impact]
 I --> E([END])
```

| Node | 실제 처리 | 호출/검증 |
|---|---|---|
| retrieve | 변경안 title+content로 기존 Vector Top5 | 기존 SearchRequest/SearchHit, `change_impact.rag_retrieve` |
| diff | 최초에는 Qwen 조건 대응, 캐시가 있으면 기존 응답 재사용; 원문 기반 reconcile | Draft/Pair Schema, baseline index·정확 인용 검증; `condition_atoms.reconcile` |
| impact | 실제 Graph 조회 후 API/TC 검토 후보·새 TC 필요성 조립 | `graph_context` 고정 HTTP 및 `assemble`; 실제 기존 TC/정책을 수정하지 않음 |

`add_conditional_edges`나 LLM이 생성한 실행 계획은 없다. 캐시/오류/정책 if 분기, 고정 MCP dispatch, Queue job type 분기는 존재하지만 **동적 Planning/자율 Tool Routing이 아니다**. 적절한 영상 표현은 `Workflow: 3 execution steps initialized`다. `Planning: 5-step plan generated`는 근거가 없다. TC5개와 노드3개를 혼동하지 않는다.

근거: [실제 Graph](../../ai-service/app/change_impact.py), [초기 구조 조사](../phase15-evidence/current-architecture.md), [기본 분석](../../ai-service/app/analysis_service.py), [생성](../../ai-service/app/test_case_service.py).

## 분석→모델→구조화 결과

1. Spring이 요구사항을 읽어 AnalysisClient로 AI에 전달한다. 동기 `/api/requirements/{id}/analysis`와 비동기 `/analysis-jobs`는 같은 실행 자원 경계를 공유한다.
2. AI `AnalysisService.analyze`가 제목+전체 본문으로 `SearchRequest(topK=5)`를 만들고 VectorSearch로 근거를 읽는다. 검색 한도는 기존2000자/512토큰이며 자동 축약이나 rewrite를 하지 않는다.
3. catalog가 검색 원문의 문장/API에 E... ID를 부여한다. Qwen은 `AnalysisDraft`에서 충분성 및 기존 ID를 선택한다. 확정 사실/API/Evidence를 자유 생성하는 방식이 아니다.
4. `LocalLlmProvider.generate`가 `http://ollama:11434/api/chat`에 model=`qwen2.5:7b-instruct`, stream=false, think=false 기본값, JSON Schema format을 전송한다. temperature0/seed42/num_thread4 등은 실제 소스 설정이다. Qwen과 bge-m3 embedding을 구분한다.
5. Pydantic strict/extra=forbid 및 materialize가 선택 ID, 문서 종류, 근거 연결을 검사하고 AnalysisResult를 만든다. 잘못된 JSON/근거는 최대2회 시도 후 실패하며 검증 실패 결과를 정상 저장하지 않는다. 형식/인용 검증은 의미 정확도 보장이 아니다.
6. Backend가 검증 후 저장한다. AI computation 완료와 DB commit 완료는 다른 이벤트다.

스키마: [analysis_models.py](../../ai-service/app/analysis_models.py)의 AnalysisDraft/AnalysisResult, [analysis_service.py](../../ai-service/app/analysis_service.py)의 catalog/materialize, [llm_provider.py](../../ai-service/app/llm_provider.py). AnalysisResult는 confirmedConditions/ambiguousExpressions/missingConditions/relatedBusinessRules/relatedApis/clarificationQuestions/evidence를 포함한다.

## TestCase Policy Matching

기존 분석 snapshot과 `contracts/test-case-policy.json`의15개 plan이 입력이다. `compile_candidates`는 requirementId·UUID·중복 Evidence·확정 조건 원문·문서/Section/명세/API 경로를 검증한다. 미해결 모호함·누락·확인 질문이 있거나 맞는 plan이 없으면 빈 TC와 clarification을 반환하고 모델을 호출하지 않는다.

Qwen의 구조화 `Selection.candidateIds`는 모든 적격 후보를 정확히 한 번 고르는 제한된 출력이다. 서버가 검증된 템플릿의 steps/Expected/evidence를 materialize한다. Schema는 TestCase/GenerationResult 및 Selection이며 `policyHash`, `llmCalls`, `uncoveredTypes`를 보존한다. 기존15개 정책을 범용 자유 생성/임의 실행 능력으로 설명하면 안 된다. 생성본 executable과 실행 직전 eligibility도 별개다.

근거: [policy](../../contracts/test-case-policy.json), [정책 matcher](../../ai-service/app/test_case_policy.py), [정본 source 검증](../../ai-service/app/test_case_registry.py), [Schema](../../ai-service/app/test_case_models.py).

## MCP 실제 Tool8종

| Tool | 고정 목적지/작업 | 모델·쓰기 의미 |
|---|---|---|
| search_knowledge | AI Vector 또는 Retrieval Hybrid 검색 | Qwen 호출 없음; reranker 임의 선택 불가 |
| analyze_requirement | 저장 분석 조회, 없으면 기존 분석 API | SAVED이면 새 모델0; 없는 분석의 생성 분기는 모델을 호출할 수 있음 |
| get_test_cases | Backend 저장 TC 조회 | 새 TC 생성 아님 |
| get_evaluation_result | 저장 평가 조회 | 평가 생성/GT 공개 아님 |
| execute_approved_test | Backend 승인 TC 실행 | 모델 판정 아님; 실제 승인·적격성 검사 후 실행 |
| find_requirement_context | Graph 요구사항 관계 조회 | 고정 읽기 Tool |
| find_impacted_tests | Graph BusinessRule 영향 후보 | UUID만 입력; 임의 Cypher 없음 |
| trace_test_case_origin | Graph TC 출처·실행 관계 | 고정 읽기 Tool |

`mcp-server/app/schemas.py`, `server.py`, `clients.py`가 실제 목록·엄격한 입력·고정 목적지를 정의한다. 실행 입력은 testCaseId만 허용하고 model/prompt/url/body override나 승인 Tool은 없다. Streamable HTTP ClientSession의 실제 호출 증거는 [복구 MCP 결과](../observability-recovery/mcp-results.json), [실제 요약 로그](../observability-recovery/mcp-hitl-execution.actual.log)에 있다. 내부 `DummyApiRegistry.invoke`와 `graph_context` HTTP 호출을 MCP로 표현하지 않는다.

## Job/HITL/Execution/Trace 연결

DB Queue 기본 대기5·동시1, lease30초·heartbeat1초·poll1초다. session advisory lock + Python slot으로 동기/비동기/TC/영향 분석이 단일 모델 자원을 공유한다. QUEUED/RUNNING/SUCCEEDED/FAILED/TIMED_OUT/CANCELLED를 구분하고, 실행 중 작업의 강제 kill/자동 재실행을 보장하지 않는다. `JobWorker`/`JobStore`/`AnalysisGate`, [Phase14 복구 계약](../phase14-result.md) 참조.

TC 수정·Fixture 준비는 DRAFT와 새 reviewRevision을 만들고 재승인이 필요하다. 실행은 현재 승인 revision·AllowList·입력·Fixture·assertion을 재확인한다. `ExecutionComparator`가 Expected/Actual을 비교하여 PASS/FAIL, 인프라/초기화 예외는 ERROR로 저장한다. LLM이 PASS/FAIL을 채점하지 않는다.

Trace는 Job 실행 root에 jobId/requirementId를 넣고 생성 요청과 span link로 연결한다. stdout `stream=SUMMARY`의 event/status/provider/elapsedMs와 Trace ID를 대조할 수 있다. `REAL_LLM`, `FAKE_PROVIDER`, `POLICY_BLOCKED`, `CACHED_RESULT`, `NO_LLM_CALL`을 구분하며 모델이 없으면 LLM_STARTED/COMPLETED를 만들지 않는다. seq는 service/run별 번호이지 전역 실행 계획 번호가 아니다. [실제 로그·코드 위치](../observability-recovery/real-workflow-trace.md), [계측 wrapper](../../observability/python/workflow_otel/install.py), [JobWorker](../../backend/src/main/java/com/example/legacyassistant/jobs/JobWorker.java) 참조.
