# AI Masters 영상용 실행 증거 로그 v2

검증일 2026-10-28, 로그 시각 KST. 이전 보고서와 로그는 상위 폴더에 보존했다. 이번 결과는 이 `video/` 폴더에 따로 기록했다. 커밋·Push는 수행하지 않았다.

요약 행에 `stream=SUMMARY`, 짧은 영어 `label`, `seq`, `status=START|COMPLETE|FAILED`, 실제 `result`를 추가했다. 기존 이벤트와 Job/run/Trace 식별자를 유지하면서 RAG·구조화 출력·Evidence·모델 호출의 실제 시작/실패 지점을 보강했다. 실제 MCP 수신 경계, 승인 API, 로컬 Dummy dispatcher, assertion comparator에도 같은 형식을 연결했다. 업무 로직·Prompt·정책·평가·DB 스키마는 변경하지 않았다.

## 영상 터미널 명령

프로젝트 루트 `D:\MASTER과정`에서 실행한다. 현재 세 서비스는 요약 로그가 활성화된 최종 이미지로 적용되어 있다.

```powershell
python -u docs/workflow-logging/video/watch-summary.py --follow
```

기존 다중 Compose 구성을 사용하여 AI Service·Backend·MCP 서버를 모두 구독한다. 기본 `--tail 0`은 새로 발생한 행만 표시한다. 이 프로그램은 실제 summary 행을 축약할 뿐 이벤트·시각·카운트·상태를 생성하지 않는다. `Ctrl+C`로 종료하면 로그 구독 자식 프로세스도 정리한다.

요약 원문과 일반 로그를 별도 파일로 보존하려면 다음과 같이 실행한다.

```powershell
python -u docs/workflow-logging/video/watch-summary.py --follow --raw-log summary-raw.log --debug-log ordinary.log
```

기존 행까지 읽으려면 `--tail 100`을 추가한다. 실시간 영상에서는 `--tail 0`을 권장한다. 사후 Compose 조회는 서비스별 과거 행을 묶어 반환할 수 있다.

기본 필터만 사용하는 PowerShell 명령은 다음과 같다. MCP 서비스는 기본 compose.yaml에 없으므로 실제 사용 중인 Compose 파일을 모두 지정한다.

```powershell
$compose = @('-f','compose.yaml','-f','compose.phase8.yaml','-f','compose.phase9.yaml','-f','compose.phase10.yaml','-f','compose.phase11.yaml')
docker compose @compose logs -f --tail 0 --no-color --no-log-prefix ai-service backend mcp-server | Select-String 'stream=SUMMARY'
```

컨테이너를 재생성할 때 활성화하려면 다음을 실행한다. `.env`는 변경하지 않았다.

```powershell
$env:WORKFLOW_SUMMARY_LOG = 'true'
docker compose @compose up -d --no-deps --build ai-service backend mcp-server
```

`WORKFLOW_SUMMARY_LOG=false`가 기본값이다. 비활성화도 환경변수를 설정한 후 컨테이너를 재생성한다. summary는 stdout/flush 출력이며 일반 HTTP·OTel 운영 로그와 `stream=SUMMARY`로 분리한다. 기존 OTel span 전파는 유지한다.

## 식별자와 상태 해석

- `AI`, `BE`, `MCP`는 각각 AI Service, Backend, MCP 서버다.
- `#seq`는 **해당 service/run의 실제 로그 발생 순번**이다. 전역 순번, 계획 단계 번호, 동적으로 생성한 실행 계획의 길이가 아니다. 전체 원문에는 service/runId/traceId/jobId가 있다.
- 축약본에도 실제 전체 Job ID 또는 Trace ID를 표시한다. OTel을 끈 Fake 테스트에서는 실제 runId를 대신 표시한다. ID를 임의로 만들거나 짧은 ID로 치환하지 않는다.
- `START`는 실제 작업 진입, `COMPLETE`는 해당 경계 정상 반환, `FAILED`는 실제 예외 또는 assertion 실패다. `result`는 그 경계의 실제 결과다.
- `Qwen COMPLETE result=RETURNED`는 provider가 응답을 반환했다는 뜻이다. 후속 Schema/Evidence PASS와 구분한다.
- `Tool COMPLETE result=FAIL toolStatus=SUCCESS`는 **MCP 호출 자체는 성공했고 실행한 테스트가 FAIL**이라는 뜻이다. 승인 거부/Timeout 같은 도구 실패는 `TOOL_FAILED/status=FAILED`다.
- AI의 Workflow 완료는 `persistence=NOT_SAVED`, Backend의 저장·완료는 커밋 확인 후 `COMMITTED`다. 두 서비스의 완료 범위를 구분한다.
- `provider`는 **그 서비스 경계에서의 직접 모델 호출**을 뜻한다. AI의 실제 호출은 REAL_LLM, Fake는 FAKE_PROVIDER다. Backend 저장·승인·실행은 NO_LLM_CALL이다. MCP gateway도 모델을 직접 호출하지 않으므로 `NO_LLM_CALL callScope=GATEWAY`다. Gateway가 새 분석을 요청하는 경우 실제 모델 증거는 같은 Trace의 AI 로그에서 확인해야 한다. 저장된 분석을 읽으면 `source=SAVED`가 나온다.
- 기존 정책 보류·캐시 재사용은 POLICY_BLOCKED/CACHED_RESULT를 유지한다. 실제로 실행하지 않은 LLM_* 행은 출력하지 않는다. Fake에는 PROVIDER_*를 사용한다.

## Workflow와 Planning

동적 Planning은 구현되어 있지 않다. 요구사항 분석과 TC 생성은 기존 Python의 고정 흐름이다. 초기화에는 `mode=FIXED`를 표시하고 실행 단계 개수를 임의로 붙이지 않는다.

실제 LangGraph는 변경 영향 분석의 `retrieve → diff → impact` 고정 3노드다. 이 경로만 컴파일 성공 직후 `mode=FIXED steps=3`을 표시한다. START/END는 업무 실행 노드 수에 포함하지 않는다. 기존 노드와 edge는 그대로다. `Planning: 5-step plan generated`, `5 execution steps initialized` 또는 `5 steps generated`를 사실과 다르게 출력하지 않는다. 생성된 TC 5건은 `testCases=5`로만 표시한다.

TC 생성에서 Qwen은 기존 정책 후보 ID를 선택·정렬한다. 실제 TC 본문은 서버가 검증된 후보로 materialize한다. 이를 LLM의 동적 작업 계획 생성이나 자유로운 API 작성으로 표현하지 않는다.

## 실제 실행 증거

다음 파일은 이번에 실제 실행한 로그다. `*.actual.log`는 애플리케이션이 출력한 행을 그대로 보존한 것이고, `*.video.log`는 그 행에서 필드만 선택한 축약본이다. **축약본도 실제 값**이며 시연용 가짜 예시가 아니다.

| 검증 | 실제 결과 | 파일 |
| --- | --- | --- |
| Qwen 요구사항 분석 | Phase 14 Job SUCCEEDED, 검색 5건, 확정 조건 1건, 실제 모델 호출 1회, 저장 커밋 | [qwen-analysis.actual.log](qwen-analysis.actual.log), [영상용 축약본](qwen-analysis.video.log) |
| Qwen TC 생성 | 실제 Qwen 호출 1회, TC 5건 생성·검증·Backend 저장, 재조회 수 일치 | [qwen-generation.actual.log](qwen-generation.actual.log), [축약본](qwen-generation.video.log) |
| 실제 MCP 호출 | 표준 ClientSession + Streamable HTTP, 최종 수집 6회 | [mcp-hitl-execution.actual.log](mcp-hitl-execution.actual.log), [축약본](mcp-hitl-execution.video.log) |
| 승인 전 차단 | MCP execute_approved_test → NOT_APPROVED. Dummy dispatch·저장 없음 | [approval-blocked.actual.log](approval-blocked.actual.log) |
| 승인 API | 실제 edit/approve 및 revision·커밋 확인 | [hitl-review.actual.log](hitl-review.actual.log), [축약본](hitl-review.video.log) |
| 정상 실행 | 실제 MCP → Dummy → 비교 → 저장 → PASS, mismatch 0 | [normal-pass.actual.log](normal-pass.actual.log), [축약본](normal-pass.video.log) |
| 의도적 결함 | 실제 MCP → 기존 synthetic-self-approval-bug → assertion FAIL, mismatch **2**, 저장·재조회 일치 | [intentional-fail.actual.log](intentional-fail.actual.log), [축약본](intentional-fail.video.log) |

Qwen은 `qwen2.5:7b-instruct`를 사용했고 이번 작업의 실제 모델 호출은 **총 2회**다. 실제 소요시간은 각 원문 행의 durationMs/elapsedMs에 기록했으며 성능 평균·평가 점수로 일반화하지 않았다.

분석 Job ID는 `3e0a30a0-ed8c-4667-b915-4b0f978a7f3a`, 분석 요구사항은 `677d8665-eec6-45e3-abda-44a7b6a16efc`다. TC 생성 요구사항은 별도 검증용 `069a6263-54fa-4757-af05-ee37da81035e`다. TC 생성 입력은 기존 `test-case-analysis.json`의 근거 검증 fixture이며, 그 요구사항의 입력 준비용 분석 snapshot만 새 행에 seed했다. **이 snapshot을 방금 Qwen 분석이 생성한 결과라고 주장하지 않는다.** TC 선택/생성 호출과 이후 저장·승인·실행은 실제 서비스 경로를 이용했다. 기존 요구사항·TC·평가 데이터는 덮어쓰지 않았다.

실제 MCP 최종 수집 호출은 다음 6회다.

1. `search_knowledge`: 5건 검색.
2. `analyze_requirement`: 앞서 저장한 실제 Qwen 분석 조회, `source=SAVED`, 추가 모델 호출 없음.
3. `get_test_cases`: 5건 조회.
4. `execute_approved_test`: DRAFT 상태에서 NOT_APPROVED로 차단.
5. `execute_approved_test`: 승인한 정상 TC의 PASS.
6. `execute_approved_test`: 승인한 합성 결함 TC의 FAIL. MCP transport/tool dispatch는 정상 완료.

내부 RAG 검색 함수, provider.generate, DummyApiRegistry.invoke를 MCP Tool Invocation으로 기록하지 않는다. `Tool` 행은 오직 실제 `server.call_tool` 요청 수신 경계에서 나온다. Dummy는 실제 `dispatch=IN_PROCESS`인 기존 합성 API이며 외부 HTTP API 호출이라고 표현하지 않는다.

검증은 첫 확인과 최종 요청 경로 메타데이터 확인을 위해 같은 새 TC에서 MCP 시나리오를 반복했다. 최종 파일에는 마지막 6회 호출을 수집했으며 반복을 실제 모델 호출이나 추가 TC 생성으로 계산하지 않았다. 기존 execution 이력은 보존했고 최종 실행 ID는 [mcp-results.json](mcp-results.json)에 있다.

### HITL 증거의 범위

이번 자동 검증의 승인 요청자는 `demo-validation-script`다. 실제 승인 API와 트랜잭션·revision·실행 전 승인 재검사가 작동했음을 확인했지만 **사람이 UI에서 클릭한 장면을 검증한 것은 아니다**. `origin=REVIEW_API`와 별도 검증 메타데이터 `approvalOrigin=VALIDATION_SCRIPT_REVIEW_API`를 기록했다. 로그에는 검토자 이름/댓글을 노출하지 않는다.

제출 영상에서 사람의 HITL 장면을 증명하려면 실제 검토자가 기존 TC 검토 화면에서 내용을 확인하고 승인 버튼을 누르는 장면과 연결된 HITL 로그를 함께 촬영한다. 기존 UI에서 TC를 수정하면 기존 로직대로 DRAFT로 돌아가고 재승인이 필요하다. 이 작업은 해당 로직이나 승인 조건을 변경하지 않았다.

### 순서·Trace 검증

원문의 seq는 service/run 단위로 1부터 연속임을 검사했다. MCP와 Backend의 runId·Trace ID가 일치하고, Tool START → Dummy START/COMPLETE → Assert PASS/FAIL → 커밋 → Tool COMPLETE가 연결됨을 확인했다.

컨테이너별 사후 로그 조회를 합칠 때는 임의의 원하는 이벤트 순서로 재배열하지 않고 **실제 Docker UTC timestamp**로 정렬했다. [mcp-hitl-execution.transport.log](mcp-hitl-execution.transport.log)에 그 timestamp와 원문을 함께 보존했다. Qwen 원본은 각 호출 직후 수집했으며 이후 Backend 재생성 전에 저장했다. 실시간 viewer는 도착한 행을 그대로 표시한다. seq와 실제 노드 수를 혼동하지 않는다.

Trace **식별자 전파**는 실제 로그에서 확인했다. 이전에 확인된 Jaeger 저장/조회 장애를 이번 작업에서 수정하거나 실제 trace 저장 성공으로 주장하지 않았다. 기존 OTel 자동 테스트도 별도로 통과했다.

## 시연용 출력 예시: 실제 증거와 분리

[illustrative-output.txt](illustrative-output.txt)는 **미실행 형식 예시**다. 시각·ID·숫자를 placeholder로 표기했고 첫 줄에 `ILLUSTRATIVE ONLY - NOT EXECUTED`를 넣었다. 이 파일을 실제 실행 증거로 사용하지 않는다. 실제 제출 근거에는 위 `*.actual.log`와 검증 JSON을 사용한다.

`fake/`에는 이번에 실제로 실행한 **Fake Provider/정책 보류/캐시/Timeout 테스트**의 로그가 있다. 실행 자체는 실제지만 Qwen 추론 증거가 아니다. [fake/fake-results.json](fake/fake-results.json)의 realModelCalls는 모두 0이다. Fake의 PROVIDER_*와 REAL_LLM의 LLM_*를 혼용하지 않는다.

## 이벤트와 실제 발생 코드 연결

| 영어 라벨 / 이벤트 | 실제 코드 지점 |
| --- | --- |
| Workflow / WORKFLOW_STARTED, INITIALIZED, COMPLETED, FAILED | [workflow_summary.py](../../../ai-service/app/workflow_summary.py)의 workflow wrapper. [change_impact.py](../../../ai-service/app/change_impact.py)의 컴파일 직후에는 실제 고정 3노드 초기화 표시 |
| RAG / RETRIEVAL_STARTED, COMPLETED, FAILED | [analysis_service.py](../../../ai-service/app/analysis_service.py)의 search.search 호출을 phase로 감싼 경계. 변경 영향은 기존 retrieve node의 검색 경계 |
| Qwen / LLM_STARTED, COMPLETED, FAILED | workflow_summary.generate에서 LocalLlmProvider.generate 실제 dispatch 전·반환 후·예외. ContextLlm adapter의 실제 delegate도 구분 |
| Provider / PROVIDER_STARTED, COMPLETED, FAILED | 동일 wrapper의 Fake Provider 경로. LLM 이벤트를 생성하지 않음 |
| Schema / STRUCTURED_OUTPUT_STARTED, COMPLETED, FAILED | AnalysisDraft.model_validate_json, Selection.model_validate_json + 정확한 후보 집합 검사, Change Draft.model_validate_json의 실제 호출 경계 |
| Evidence / EVIDENCE_VALIDATION_STARTED, EVIDENCE_VALIDATED, FAILED | AnalysisService.materialize의 기존 인용 ID/유형 검사, [test_case_service.py](../../../ai-service/app/test_case_service.py)의 compile_candidates 기존 identity/source 검사. 새 의미 평가를 추가한 것이 아님 |
| Policy / POLICY_MATCHING_STARTED, POLICY_MATCHED | 기존 compile_candidates의 실제 시작과 반환된 후보 수/로드된 templates 수 |
| TC / TESTCASE_GENERATION_STARTED, TESTCASE_GENERATED | 후보 선택 검사 통과 뒤 서버 materialization 시작, GenerationResult 검사 통과 뒤 실제 건수 |
| Tool / TOOL_STARTED, COMPLETED, FAILED | [mcp-server/app/server.py](../../../mcp-server/app/server.py)의 실제 call_tool 수신·기존 입력/출력 검사·Gateway 반환·예외. 출력은 [MCP workflow_summary.py](../../../mcp-server/app/workflow_summary.py) |
| Tool의 downstream 연결 | [clients.py](../../../mcp-server/app/clients.py)의 HTTP 전달에 실제 MCP request/run UUID 추가. [TraceFilter.java](../../../backend/src/main/java/com/example/legacyassistant/observability/TraceFilter.java)에서 UUID 검증·Context 연결. 기존 traceparent 전파 유지 |
| HITL / HITL_STARTED, COMPLETED, FAILED | [ExecutionSummaryAspect.java](../../../backend/src/main/java/com/example/legacyassistant/observability/ExecutionSummaryAspect.java)가 TestCaseReviewService.edit/decide의 실제 호출을 관찰. 완료·저장은 커밋 후에만 출력 |
| Execute / EXECUTION_STARTED, COMPLETED, FAILED | 동일 aspect의 ExecutionService.execute/executeRevision 경계. 반환된 report.result를 그대로 기록 |
| Dummy / DUMMY_STARTED, COMPLETED, FAILED | 실제 Spring bean DummyApiRegistry.invoke 경계. allowlist Entry의 API ID, 실제 response status만 기록. in-process dispatch 명시 |
| Assert / ASSERTION_STARTED, COMPLETED, FAILED | 실제 ExecutionComparator.compare의 반환 mismatch 배열 크기. 결과 0이면 PASS, 1개 이상이면 FAIL. 예상 assertion이나 비교 로직 변경 없음 |
| Save / RESULT_SAVED | [WorkflowSummary.java](../../../backend/src/main/java/com/example/legacyassistant/observability/WorkflowSummary.java)의 커밋 callback 또는 이미 커밋된 service 반환. 롤백/차단/저장 실패에는 성공 행 없음 |

출력에는 Prompt, 전체 요구사항, 전체 모델 응답/추론, evidence 원문, Ground Truth, 인증정보를 포함하지 않는다. MCP Tool 이름은 기존 allowlist, 식별자는 UUID/W3C 형식, 오류는 고정 코드, Dummy API는 서버 allowlist Entry만 사용한다.

## 자동 검증

중복 재실행을 합산하지 않은 현재 결과는 **443건 통과**, 실패·오류·skip 0이다.

| Suite | 통과 수 | 근거 |
| --- | ---: | --- |
| Java 기존 회귀 + 로그/승인/실행 관찰 | 166 | [java-regression-results.json](java-regression-results.json) |
| Python AI/Retrieval/Evaluation/MCP/Graph/OTel | 246 | [python-regression-results.json](python-regression-results.json) |
| 검색 평가 메트릭 | 13 | [extra-regression-results.json](extra-regression-results.json) |
| Frontend 기존 단위 | 5 | 동일 파일 |
| 평가 DB 저장·재현·권한·불변성 | 9 | [evaluation-db-regression-results.json](evaluation-db-regression-results.json) |
| 영상 필터 projection | 4 | [test_projection.py](test_projection.py), 자동 실행 결과는 최종 검증 요약 참조 |

고정 RAG 8개 질의의 top5 ID·score 동일, Frontend TypeScript/Vite 빌드, AI/Backend/MCP Docker 빌드도 확인했다. Frontend 빌드는 OS 임시 폴더로 출력해 기존 dist를 변경하지 않았다. 승인·실행 Java 업무 소스의 작업 시작 hash, 기존 Prompt의 AST, LangGraph 노드/edge AST, 정책·knowledge·평가 데이터·LLM provider·migration의 불변 검사도 통과했다.

신규/보강 검사에는 RAG·Schema·Evidence의 시작/실패, Fake와 Qwen의 이벤트 분리, 조기 PASS 방지, 실제 MCP handler의 이름/상태/민감정보 차단, tool 성공과 test FAIL 구분, 실제 header 전달, 승인 롤백 시 커밋 로그 부재, 승인 전 Dummy 호출 부재, 실제 mismatch 수 유지가 포함된다. 첫 Python 실행의 MCP 계약 import 오류는 테스트 마운트가 이미지에서 생성한 app/contracts를 가린 문제였고, 개별 소스 파일 마운트로 수정 후 전체 통과했다.

[evidence-verification.json](evidence-verification.json)은 실제 수집 행의 이벤트 순서·수량·Trace 연결 검증이다. [source-preservation.json](source-preservation.json)은 업무 로직 보존 검사다. 과거 UI 전체 브라우저 행렬, 새 사람 클릭 테스트, 실제 Qwen Timeout 유발, Jaeger UI 저장 조회는 이번 작업에서 수행하지 않았다.

회귀 재실행(실제 모델 호출 없음):

```powershell
python docs/workflow-logging/video/run-regression.py python
python docs/workflow-logging/video/run-regression.py java
python docs/workflow-logging/video/run-regression.py extra
python docs/workflow-logging/video/run-regression.py evaluation-db
python -m unittest discover -s docs/workflow-logging/video -p test_projection.py -v
```

`verify-real.py`는 새 합성 데이터를 만들고 실제 모델을 호출하므로 자동 회귀에 포함하지 않는다. `verify-mcp.py`는 실제 MCP·승인·실행 API로 검증용 TC의 상태를 변경한다. 일반 시연 로그를 보기만 할 때에는 viewer만 실행한다.

변경 파일 목록과 최종 검증 요약은 [completion.json](completion.json)에 기록한다. 기존 사용자 변경과 상위 폴더의 이전 실행 증거는 보존했다.
