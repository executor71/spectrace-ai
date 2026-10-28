# Actual workflow trace verification

검증일: 2026-10-28 KST. 아래는 실제 실행·저장·조회 결과다. 단일 합성 시나리오의 측정치이며 성능 벤치마크가 아니다. 실제 Qwen 호출은 분석 1회 + TC 선택/생성 1회 = **2회**다.

## Stored and queried traces

| 실행 | 실제 Trace ID | Service Name | Trace 경과 ms |
|---|---|---|---:|
| analysis | `669dae9a85fc56beda25818ed582da92` | legacy-assistant-ai, legacy-assistant-backend | 83985.171 |
| tc-generation | `a9e694e521a4f2c03250f963198cb88d` | legacy-assistant-ai, legacy-assistant-backend | 93997.457 |
| mcp-pass | `f8c2ed73f0452934e049a59877a03a18` | legacy-assistant-backend, legacy-assistant-mcp | 7.647 |
| mcp-defect-fail | `554e370d399cd2e2bc3ec5f3e41dad78` | legacy-assistant-backend, legacy-assistant-mcp | 7.094 |
| mcp-approval-blocked | `0537e4ea2ab9614117fae2fa5a4f2131` | legacy-assistant-backend, legacy-assistant-mcp | 4.295 |
| hitl-review | `786ceaf77516759ec143f3616735a457` | legacy-assistant-backend | 3.923 |

별도 최소 SDK probe는 `127dbab8090a305b2d992389b402b9e0`, service `spectrace-recovery-probe`, Span `recovery.minimum`이다. `jaeger-query-result.json`은 이 최소 probe의 실제 Query API 응답이다. `persistent-restart-validation.json`은 Jaeger 재시작 후 같은 ID가 조회됐음을 기록한다. 각 업무 Trace의 원본은 `<실행명>-query-result.json`, 실제 duration 및 tags 전체 목록은 `trace-index.json`에 있다.

## Requirement Analysis Job

- Requirement ID: `b8267284-936f-43a5-a516-6d7d689a6d51`
- Job ID: `63dc4444-ab3a-45b5-b4f5-652a2a7a77bc` — 상태 **SUCCEEDED**
- Trace ID: `669dae9a85fc56beda25818ed582da92`
- 분석 결과: confirmed conditions 1개, evidence 5개
- 실제 `llm.generate`: 83806.662 ms, model `qwen2.5:7b-instruct`, provider `ollama`, retryCount=0, inputTokens=2350, outputTokens=72

`analysis.job.execute`와 `analysis.job.complete`의 `jobId`가 위 Job ID다. AI/Backend 요약 로그의 Job ID·Trace ID·runId를 대조했고 RAG → Qwen → schema/evidence → 저장 순서를 확인했다. Job 생성 요청과 실행은 기존 설계대로 span link로 연결된 서로 다른 Trace이며, 조회할 대상은 **실행 Trace**다. TC 생성은 동기 API이므로 Job ID를 꾸며 넣지 않고 Trace ID로 연결한다.

## TC generation and MCP

TC 입력 분석은 `ai-service/tests/fixtures/test-case-analysis.json`의 **기존 grounded fixture**를 새 요구사항에만 저장했다. 위 실제 분석 Job의 출력이 TC fixture라고 주장하지 않는다. 기존 정책 15개에서 5개가 매칭되고 Qwen이 구조화된 Selection을 반환한 뒤 서버가 기존 템플릿을 materialize했다. 실제 생성 수·저장 수·로그 수 모두 **5**개, llmCalls=1이다. Qwen Span은 93896.917 ms다. 이것을 동적 실행 계획이나 5개 execution steps 생성이라고 표현하지 않는다.

이번 분석은 AI Service의 `AnalysisService` 고정 경로이며 RAG도 해당 프로세스의 `VectorSearch`에서 실행됐다. TC 생성은 저장된 분석 근거를 사용하며 새 retrieval을 했다고 표시하지 않는다. 이번에는 change-impact의 LangGraph `retrieve → diff → impact`를 실행하지 않았다. 이 별도 그래프가 이번 분석의 동적 Planning을 수행한 것처럼 설명하지 않는다.

표준 MCP `ClientSession` / Streamable HTTP로 `search_knowledge`, `analyze_requirement`(SAVED), `get_test_cases`, `execute_approved_test` 3회를 실행했다. 총 6회이며 추가 모델 호출은 0회다. 실제 MCP 서버의 `mcp.tool`과 Backend 하위 Span이 같은 Trace로 이어진다. 내부 Dummy dispatch는 `IN_PROCESS`이며 MCP 호출로 포장하지 않는다.

정상 실행은 PASS, mismatches=0이다. 의도적 `synthetic-self-approval-bug` fixture는 기대 HTTP403 / 실제 HTTP200 및 mismatches=2로 FAIL을 반환·저장했다. 이 경우 MCP 전달 자체는 SUCCESS이지만 업무 결과는 FAIL이다. DRAFT 실행 거부는 `NOT_APPROVED`이고 MCP/Backend에 ERROR Span이 있다. HITL 검증은 실제 edit/approve API를 **검증 스크립트**로 호출한 것으로, 사람이 클릭한 증거가 아니다.

## Actual outage exercise and limits

Qwen 분석 실행 중 Collector와 Jaeger가 둘 다 stopped임을 inspect로 확인했다. Job은 RUNNING이었고 새 TC 승인, Dummy PASS 실행과 저장 결과 재조회가 성공했다. 관측 서비스는 finally에서 복구했고 전체 검증 경과시간은 9825.91 ms다. Qwen 종료 후 분석 결과가 저장되고 위 10개 Span을 모두 Query API/UI에서 확인했다. `outage-validation.json` 참조.

첫 장애 검증 스크립트가 실행 API에 빈 JSON 본문을 보내 `EXECUTION_INPUT_NOT_ALLOWED` HTTP400을 받았다. 기존 API는 본문 없는 실행만 허용한다. 서비스는 즉시 복구됐으며 본문 없는 정상 요청으로 스크립트를 고쳐 재검증했다. `outage-first-attempt.json`을 보존했다. 제품 로직을 완화하지 않았다.

실제 TC의 Qwen 호출은 관측 계층이 정상인 상태에서 실행했다. 관측 장애 상태에서 **새 Qwen TC 호출을 추가로 수행하지 않았다**. 대신 네트워크가 없는 Python Fake 분석·TC/관측 테스트와 exporter 실패 조건의 Java 회귀 테스트로 해당 오류 격리 범위를 확인했다. 장애 중 종료된 짧은 review/실행 Span은 유실될 수 있으므로 그 outage 실행의 Jaeger 보존을 주장하지 않는다. 복구 후 별도 MCP 실행의 저장된 Trace가 PASS/FAIL 증거다.

## Measured span lists

### analysis

| Service | Span | 실제 duration ms |
|---|---|---:|
| legacy-assistant-backend | `analysis.job.execute` | 83985.171 |
| legacy-assistant-backend | `backend.requirement` | 0.338 |
| legacy-assistant-ai | `http.server` | 83965.654 |
| legacy-assistant-ai | `requirement.analysis` | 83964.110 |
| legacy-assistant-ai | `rag.search` | 155.595 |
| legacy-assistant-ai | `query.embedding` | 146.164 |
| legacy-assistant-ai | `vector.search` | 2.292 |
| legacy-assistant-ai | `llm.generate` | 83806.662 |
| legacy-assistant-ai | `analysis.validation` | 0.125 |
| legacy-assistant-backend | `analysis.job.complete` | 2.819 |

### tc-generation

| Service | Span | 실제 duration ms |
|---|---|---:|
| legacy-assistant-backend | `backend.request` | 93997.457 |
| legacy-assistant-backend | `testcase.generate` | 93996.425 |
| legacy-assistant-backend | `backend.requirement` | 0.352 |
| legacy-assistant-backend | `requirement.analysis.read` | 0.889 |
| legacy-assistant-backend | `backend.requirement` | 0.339 |
| legacy-assistant-ai | `http.server` | 93968.901 |
| legacy-assistant-ai | `testcase.generate` | 93899.143 |
| legacy-assistant-ai | `llm.generate` | 93896.917 |

### mcp-pass

| Service | Span | 실제 duration ms |
|---|---|---:|
| legacy-assistant-mcp | `http.server` | 7.647 |
| legacy-assistant-mcp | `mcp.tool` | 6.676 |
| legacy-assistant-backend | `backend.request` | 4.303 |
| legacy-assistant-backend | `dummy.execution` | 2.005 |
| legacy-assistant-backend | `execution.allowlist` | 0.080 |
| legacy-assistant-backend | `execution.fixture.initialize` | 0.044 |
| legacy-assistant-backend | `execution.dummy.invoke` | 0.202 |
| legacy-assistant-backend | `execution.assertions` | 0.195 |

### mcp-defect-fail

| Service | Span | 실제 duration ms |
|---|---|---:|
| legacy-assistant-mcp | `http.server` | 7.094 |
| legacy-assistant-mcp | `mcp.tool` | 6.179 |
| legacy-assistant-backend | `backend.request` | 4.630 |
| legacy-assistant-backend | `dummy.execution` | 1.876 |
| legacy-assistant-backend | `execution.allowlist` | 0.052 |
| legacy-assistant-backend | `execution.fixture.initialize` | 0.003 |
| legacy-assistant-backend | `execution.dummy.invoke` | 0.245 |
| legacy-assistant-backend | `execution.assertions` | 0.328 |

### mcp-approval-blocked

| Service | Span | 실제 duration ms |
|---|---|---:|
| legacy-assistant-mcp | `http.server` | 4.295 |
| legacy-assistant-mcp | `mcp.tool` | 3.603 |
| legacy-assistant-backend | `backend.request` | 2.249 |
| legacy-assistant-backend | `dummy.execution` | 0.958 |
| legacy-assistant-backend | `execution.allowlist` | 0.134 |

### hitl-review

| Service | Span | 실제 duration ms |
|---|---|---:|
| legacy-assistant-backend | `backend.request` | 3.923 |
| legacy-assistant-backend | `review` | 1.258 |

## Source connection

프로젝트 루트 기준 경로다. 코드에 없던 동적 Planning/MCP node를 만들지 않았다.

| 실제 Span / 로그 | 코드 발생 위치 |
|---|---|
| `analysis.job.execute`, Job ID / creation link | `backend/src/main/java/com/example/legacyassistant/jobs/JobWorker.java:41`, `execute` |
| `analysis.job.complete` / 결과 저장 | `backend/src/main/java/com/example/legacyassistant/jobs/JobStore.java:77`, `complete`; `JobWorker.execute`의 완료 후 `WorkflowSummary.saved` |
| `rag.search`, `query.embedding`, `vector.search` | `observability/python/workflow_otel/install.py`, `retrieval_components`; 기존 `VectorSearch.search`, `LocalEmbeddingProvider.embed_query`, vector SQL 호출 래퍼 |
| `requirement.analysis` / Workflow, RAG, Evidence, Schema 요약 | `install.py:ai`; `ai-service/app/analysis_service.py:58`, `AnalysisService.analyze` |
| `llm.generate` / REAL_LLM START/COMPLETE | `install.py:ai`의 `LocalLlmProvider.generate` 래퍼; `ai-service/app/llm_provider.py`의 실제 Ollama `urlopen`; `ai-service/app/workflow_summary.py:generate` |
| `analysis.validation` / Schema·Evidence PASS | `install.py:ai`의 `materialize` 래퍼; `ai-service/app/analysis_service.py:103`의 기존 `AnalysisService.materialize` |
| `testcase.generate` / Policy·Selection·TC·Output 요약 | `install.py:ai`; `ai-service/app/test_case_service.py`, `TestCaseGenerator.generate`; Backend `WorkflowAspect` / `TestCaseService.generate` |
| `mcp.tool` / Tool START·COMPLETE·FAILED, 실제 toolName | `observability/python/workflow_otel/__init__.py:observed_tool`; `mcp-server/app/server.py:call_tool`, `mcp-server/app/workflow_summary.py:begin/finish/emit` |
| `review` / HITL START·COMPLETE, committed save | `backend/.../observability/WorkflowAspect.java`; `ExecutionSummaryAspect.action`에서 기존 `TestCaseReviewService.edit/decide` 관측 |
| `dummy.execution`, `execution.*` / Dummy·Assertion·Save | `backend/.../testcase/ExecutionService.java:stage/executeRevision`; `WorkflowAspect.observe`; `ExecutionSummaryAspect.dummy/assertions/action` |
| Traceparent / Job headers / stdout 공통 필드 | `backend/.../observability/TraceHttpInterceptor.java`, `WorkflowSummary.java`; Python `TraceMiddleware`, `ai-service/app/workflow_summary.py` |

`seq`는 service/run별 순서이고 전역 실행 계획의 단계 번호가 아니다. 원본 요약 행에 Job ID, Trace ID, Workflow, event/START·COMPLETE·FAILED, provider, elapsedMs와 실제 결과가 있다. AI의 `persistence=NOT_SAVED`와 Backend의 `RESULT_SAVED persistence=COMMITTED`를 구분한다. `provider=NO_LLM_CALL`인 Backend 저장 행은 전체 작업에 모델이 없었다는 뜻이 아니라 해당 서비스 단계에서 모델을 호출하지 않았다는 뜻이다.

## Actual logs and UI evidence

- `qwen-analysis.actual.log`, `qwen-generation.actual.log`: 실제 stdout 행. `.transport.log`는 Docker의 실제 타임스탬프를 추가 보존.
- `mcp-hitl-execution.actual.log`, `normal-pass.actual.log`, `intentional-fail.actual.log`, `approval-blocked.actual.log`, `hitl-review.actual.log`: 실제 실행 부분집합.
- `.video.log`: 같은 실제 행의 표시용 projection. 시간을 줄이거나 가상의 이벤트를 추가하지 않았다.
- `ui-validation.json`, `ui-*.png`, `ui-*.txt`: 로컬 Chrome으로 실제 Jaeger UI를 열고 Span 및 모델/Job 태그를 확인한 결과. `ui-analysis-qwen.png`, `ui-analysis-job.png`가 영상용 핵심 증거다.

이번 폴더에 가상의 시연 출력은 만들지 않았다. 예전 `docs/workflow-logging/video/illustrative-output.txt`는 예시이며 이번 실제 Trace 증거와 혼동하지 않는다. 전체 prompt·요구사항 본문·LLM 응답·추론·Ground Truth·인증정보는 이 증거 로그와 Span에 기록하지 않았다.
