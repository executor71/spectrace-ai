# SpecTrace AI Workflow 실행 요약 로그

검증일: 2026-10-28, 시간 표기 KST(UTC+09:00).

실제 서비스 실행 지점에 선택적으로 출력하는 stdout 로그를 추가했다. 검색/RAG, Prompt, 정책, 출력 계약, DB 스키마, LangGraph 노드와 연결은 그대로 유지했다. 커밋·Push는 수행하지 않았다. 시작 시 존재하던 Backend/Frontend 미커밋 작업도 보존했다.

## 실제 Workflow 조사

| 기능 | 실제 구현과 실행 순서 | Planning / Routing |
| --- | --- | --- |
| 요구사항 분석 | `AnalysisService.analyze`: 입력 검사 → VectorSearch(topK=5) → evidence catalog/제한된 JSON Schema → provider 호출 → AnalysisDraft 검사 → materialize의 근거 ID/유형 검사 → AnalysisResult | 일반 Python의 고정 흐름. 실패한 structured output은 기존대로 최대 2회 호출. LangGraph 아님 |
| TC 생성 | `TestCaseGenerator.generate`: 로드된 정책으로 compile_candidates → 후보 없으면 보류 → 후보 ID의 structured selection → 정확한 후보 집합 검사 → 서버의 후보를 TC로 materialize → GenerationResult 검사 | 일반 Python의 고정 흐름. LLM은 허용 후보 선택/정렬만 수행. 실행 계획을 만들지 않음 |
| Graph 보조 분석 | `graph_analysis_api.analyze_context`: 기존 hybrid context를 ContextSearch/ContextLlm으로 AnalysisService에 전달 | 별도 Planning/Router 노드 없음 |
| 변경 영향 분석 | `change_impact.Workflow.analyze`: LangGraph `START → retrieve → diff → impact → END` | 실제 LangGraph는 이 기능에 존재. 고정 3노드이며 conditional edge나 Planning 노드 없음 |
| 변경 영향 캐시 | `diff` 내부에서 cachedModelChanges가 있으면 기존 비교 결과를 재사용하고 reconcile/impact 실행 | 기존 Python 분기. 새 동적 Routing 노드가 아님 |
| 결과 저장 | Java AnalysisRepository/TestCaseRepository, 비동기는 JobStore.complete의 트랜잭션 | AI Service에는 DB 저장 단계가 없음 |
| Phase 14 Job | JobWorker.execute의 동일 Worker/분석 잠금/lease/검증/저장 경로. Phase 15 유형도 같은 Worker 이용 | DB Job 상태/stage, 잠금, 재시도, fencing 계약 그대로 |
| OTel | 기존 TraceHttpInterceptor, Python TraceMiddleware, workflow_otel의 RAG/LLM/업무 span | 기존 span/traceparent 전파 유지 |

정책의 `plans`는 TC 템플릿 목록이다. 이번 검증에서는 15개 중 5개가 매칭되어 **5 test cases generated**를 기록했다. `5 steps generated`, `PLANNING`, `EXECUTION_PLAN_LOADED`는 출력하지 않는다.

## 활성화와 터미널 명령

기본값은 `WORKFLOW_SUMMARY_LOG=false`다. 현재 시연용 AI Service와 Backend 컨테이너에는 `true`를 적용했다. `.env`는 수정하지 않았다. 다음 재생성 때에도 활성화하려면 PowerShell에서 실행한다.

```powershell
$env:WORKFLOW_SUMMARY_LOG = 'true'
docker compose -f compose.yaml -f compose.phase8.yaml -f compose.phase9.yaml -f compose.phase10.yaml -f compose.phase11.yaml up -d --no-deps --build ai-service backend
docker compose logs -f ai-service
```

DB 저장 완료까지 함께 보려면 Backend도 구독한다. AI Service만 구독하면 계산 과정까지만 보인다.

```powershell
docker compose logs -f ai-service backend
docker compose logs -f --no-color ai-service backend | Select-String 'event=[A-Z_]+ '
```

비활성화는 환경변수를 `false`로 설정한 후 같은 `up` 명령으로 재생성한다. `restart`만으로는 컨테이너 환경변수가 바뀌지 않는다. 기본 Compose만 사용하는 환경에서는 첫 명령의 추가 `-f` 옵션을 생략한다. 이 작업에서는 기존 다중 Compose 구성을 유지했다.

`print(..., flush=True)`와 `PYTHONUNBUFFERED=1`을 적용했다. 기본 AI Dockerfile과 OTel Dockerfile 양쪽에 설정했다. Backend도 stdout에 한 줄씩 출력하고 flush한다. 실제 Qwen 응답 완료 전에 검색/LLM 시작 로그가 보이는 것을 확인했다. OTel이 활성화된 AI Service에서 요약 모드를 켜면 기존 workflow JSON 콘솔 로그를 억제한다. span 생성/전송은 유지하며 HTTP access 로그는 별개다. 위 필터로 시연에 필요한 행만 볼 수 있다.

## 필드와 완료 범위

각 행은 `[HH:mm:ss] [업무 분류] 메시지 event=...` 형식이며 다음 필드를 포함한다.

| 필드 | 의미 |
| --- | --- |
| service | `ai-service` 또는 `backend` |
| workflow | `ANALYSIS`, `TEST_GENERATION`, `CHANGE_IMPACT_ANALYSIS`. DB Job의 REQUIREMENT_ANALYSIS는 로그에서 ANALYSIS로 표시 |
| jobId | 실제 비동기 Job UUID. 동기/직접 호출은 `-` |
| runId | Backend 실행별 UUID. `x-workflow-run-id`로 AI에 전달. Job 호출에는 `x-job-id`도 전달 |
| requirementId | 분석/생성 대상 또는 변경 영향의 baseline Requirement UUID |
| traceId | 활성 OTel span의 trace ID. 없으면 유효한 수신 traceparent에서 추출하며, 둘 다 없으면 `-` |
| stage | 마지막으로 진입한 실제 단계. 실패 위치를 나타냄 |
| elapsedMs | 해당 서비스 실행 시작부터의 실제 monotonic 소요시간 |
| provider / outcome | AI의 현재 호출 상태 / 최종 상태. 초기 `NO_LLM_CALL`은 아직 호출하지 않았다는 뜻 |
| attempt / durationMs | 실제 provider 호출 번호 / 해당 호출 소요시간 |

완료 범위는 `service`와 `persistence`로 구분한다. AI의 `WORKFLOW_COMPLETED`는 **AI computation completed / NOT_SAVED**이며 결과 저장을 주장하지 않는다. Backend는 저장 트랜잭션 커밋 후 `RESULT_SAVED`, 서비스 반환까지 성공하면 `WORKFLOW_COMPLETED / COMMITTED`를 출력한다. 같은 runId에 두 서비스의 완료 행이 존재할 수 있다. 정책 보류의 빈 생성 메타데이터가 커밋된 경우에도 `Result saved`는 유효하며, 생성되지 않은 TC를 저장했다고 표현하지 않는다.

외부 트랜잭션이 있으면 afterCommit callback에서 저장/완료 행을 내보낸다. 롤백, 소유권 상실, 저장 실패에는 성공 행이 없다. 컨텍스트를 callback까지 보존한다. Async Job은 기존 `store.complete`의 성공·커밋을 확인한 뒤 기록한다. 서비스별 로그는 전달 지연으로 섞일 수 있으므로 runId/service/이벤트 순서로 연결한다. 사후 `docker compose logs`로 수집한 두 서비스의 출력은 서비스별로 묶일 수 있다.

## 이벤트 정의와 실제 발생 코드

| 이벤트 | 발생 조건 | 코드 위치 |
| --- | --- | --- |
| WORKFLOW_STARTED | 실제 Python 서비스 실행 진입 | [workflow_summary.py](../../ai-service/app/workflow_summary.py), `workflow.run` |
| WORKFLOW_INITIALIZED | 고정 분석/생성 흐름 진입, 또는 실제 LangGraph compile 성공 | 위 `workflow.run`; [change_impact.py](../../ai-service/app/change_impact.py), `Workflow.analyze`의 compile 직후 |
| RETRIEVAL_COMPLETED | search가 반환한 hits의 실제 길이 | [analysis_service.py](../../ai-service/app/analysis_service.py), `analyze`; change_impact의 `retrieve` |
| EVIDENCE_VALIDATED | Analysis materialize 성공, TC 후보 컴파일의 identity/source 검사 통과, 또는 변경 비교의 baseline/proposal 인용 검사 통과 | AnalysisService.analyze, [test_case_service.py](../../ai-service/app/test_case_service.py)의 generate, change_impact.condition_diff |
| POLICY_MATCHED | compile_candidates가 반환한 후보 수와 로드된 plans 수 확인. 0도 실제 결과 | TestCaseGenerator.generate의 compile_candidates 직후 |
| LLM_STARTED | 실제 LocalLlmProvider/그 어댑터에 generate를 dispatch하기 직전 | workflow_summary.generate |
| LLM_COMPLETED | 해당 provider.generate가 정상 반환. 모델 응답의 업무상 유효성은 후속 검사에서 판정 | workflow_summary.generate |
| PROVIDER_STARTED / PROVIDER_COMPLETED | Fake Provider 호출/정상 반환. 실제 모델 호출로 표시하지 않는 추가 이벤트 | workflow_summary.generate |
| ANALYSIS_COMPLETED | 실제 확정 조건 또는 최종 변경 비교 결과 조립 완료 | AnalysisService.analyze, change_impact의 impact |
| TESTCASE_GENERATED | 실제 materialized TC 결과의 Pydantic 검사 성공 | TestCaseGenerator.generate의 GenerationResult 검증 직후 |
| OUTPUT_VALIDATED | 실제 structured output/후보 집합/근거 검사 성공. 보류는 빈 출력 schema 성공만 표시 | AnalysisService.analyze, TestCaseGenerator.generate, change_impact.condition_diff |
| RESULT_SAVED | 실제 저장 커밋 확인. AI에서는 발생하지 않음 | [Java AnalysisService](../../backend/src/main/java/com/example/legacyassistant/analysis/AnalysisService.java)의 create, [Java TestCaseService](../../backend/src/main/java/com/example/legacyassistant/testcase/TestCaseService.java)의 generate, [JobWorker](../../backend/src/main/java/com/example/legacyassistant/jobs/JobWorker.java)의 execute → [WorkflowSummary.saved](../../backend/src/main/java/com/example/legacyassistant/observability/WorkflowSummary.java) |
| WORKFLOW_COMPLETED | AI 계산 정상 반환 또는 Backend 서비스 성공 및 커밋 | workflow_summary.workflow; [WorkflowSummaryAspect](../../backend/src/main/java/com/example/legacyassistant/observability/WorkflowSummaryAspect.java)의 observe; JobWorker.execute → WorkflowSummary.completed |
| WORKFLOW_FAILED | 실제 예외로 실행 중단 | Python workflow wrapper, Java WorkflowSummaryAspect/JobWorker → failed |
| PLANNING | 발생하지 않음 | 실제 Planning 노드 없음 |

TC의 evidence PASS는 기존 코드가 수행하는 identity/조건 출처 및 선택한 정책 후보 검사를 뜻하며, 새 의미 검증이나 모델 정확도 평가를 추가했다는 뜻이 아니다. Graph 캐시 경로에서는 이번에 수행하지 않은 LLM/비교 schema·인용 검증 이벤트를 출력하지 않는다.

## 모델 호출 구분과 보안

| provider | 실제 동작 |
| --- | --- |
| REAL_LLM | LocalLlmProvider를 통한 기존 Ollama/Qwen 호출. LLM_* 이벤트 발생 |
| FAKE_PROVIDER | 주입한 Fake/Mock Provider 실행. PROVIDER_*만 발생 |
| POLICY_BLOCKED | 정책/근거/미확정 조건 때문에 후보 없음. LLM_*/PROVIDER_* 없음 |
| CACHED_RESULT | 변경 영향 비교 결과 재사용. LLM_*/PROVIDER_* 없음 |
| NO_LLM_CALL | 초기 상태 또는 호출 전에 실패한 경로 |

이번 실제 모델은 `qwen2.5:7b-instruct`다. provider 완료 이벤트는 응답 텍스트나 thinking을 읽어 로그로 내보내지 않는다. 기존 Prompt/재시도 메시지/모델 옵션은 변경하지 않았다. `attempt`를 통해 기존 bounded retry를 구분한다.

UUID와 W3C traceparent 형식을 확인하고 enum/모델 메타데이터의 줄바꿈을 제한한다. Prompt, 전체 요구사항, evidence 원문, 전체 LLM 응답, 내부 추론, Ground Truth, 인증정보는 summary 행에 포함하지 않는다. 실패는 stage/errorCode/elapsedMs만 기록하며 예외 문자열을 보간하지 않는다. 기존 analysis_api의 일반 예외 stack logging도 고정 오류코드로 바꿨다.

주요 오류코드는 `LLM_TIMEOUT`, `LLM_UNAVAILABLE`, `INVALID_OUTPUT`, `INVALID_INPUT`, `RAG_RETRIEVAL_ERROR`, `INVALID_ANALYSIS_SNAPSHOT`, `WORKFLOW_ERROR`다. Backend는 기존 업무 오류코드를 안전한 enum 형태로 기록한다. 실제 Timeout은 완료/저장으로 표현하지 않는다.

## 실제 로그와 검증 결과

원본 행을 그대로 보존한 파일:

- [real-workflow.log](real-workflow.log): 실제 Phase 14 Job 분석과 정책 보류, Backend 커밋.
- [real-generation.log](real-generation.log): 실제 Qwen TC 생성 5건. 기존 근거 검증 fixture를 사용한 내부 API 호출이며 DB 저장 없음.
- [fake-analysis.log](fake-analysis.log), [fake-generation.log](fake-generation.log): Fake Provider 분석/TC.
- [policy-blocked.log](policy-blocked.log): 정책 미지원, 후보 0, provider 호출 0.
- [fake-timeout.log](fake-timeout.log), [invalid-output.log](invalid-output.log): Timeout과 최종 schema 실패.
- [cached-impact.log](cached-impact.log): 실제 LangGraph 캐시 경로, provider 호출 0.

아래는 실제 행의 업무 메시지 부분 발췌다. 전체 식별자/소요시간은 원본 파일에 있다.

```text
[12:51:56] [ANALYSIS] Workflow started
[12:52:02] [RETRIEVAL] 5 evidence chunks retrieved
[12:52:02] [LLM] Model inference started
[12:53:40] [LLM] Model inference completed
[12:53:40] [ANALYSIS] 1 confirmed conditions extracted
[12:53:40] [COMPLETE] Result saved
[12:54:23] [MATCHING] 5 templates matched from 15 loaded templates
[12:54:23] [LLM] Model inference started
[12:55:42] [GENERATION] 5 test cases generated
[12:55:42] [VALIDATION] 5/5 test cases validated
```

실제 Qwen은 총 **2회** 호출했다. 분석 1회(LLM 98,049ms, AI 전체 103,983ms), TC 생성 1회(LLM 78,456ms). 분석 Job `34cb0df4-a322-435a-bd30-6c142c6d92fc`가 SUCCEEDED로 끝났고 새 합성 요구사항 `aa562e00-3148-400a-98ca-8123b08a2851`에 저장했다. 이 분석의 조건 1건은 기존 TC 정책에서 정상 보류됐다. 그래서 실제 TC 생성 검증은 기존 fixture를 사용해 별도로 실행했다. 분석을 TC가 나올 때까지 재호출하거나 정책/분석 결과를 수정하지 않았다. Backend에는 분석과 보류 메타데이터를 저장했고, 내부 API로 생성한 5건은 DB에 저장하지 않았다.

| 검증 | 결과 / 근거 |
| --- | --- |
| Java 전체 | 162 pass / 실패·오류·skip 0, [java-regression-results.json](java-regression-results.json) |
| 기존 Python 서비스/OTel + 신규 summary 17건 | 236 pass, [python-regression-results.json](python-regression-results.json) |
| 별도 검색 평가 메트릭 | 13 pass |
| 평가 DB 저장/재현/권한/불변성 | 격리 tmpfs DB에서 9 pass, [evaluation-db-regression-results.json](evaluation-db-regression-results.json) |
| 기존 frontend 단위 | 5 pass |
| 합계 | **425 pass**, 위 수치는 동일 테스트 재실행을 중복 합산하지 않음 |
| 빌드 | Backend/AI Docker 빌드, frontend TypeScript/Vite pass |
| 기존 RAG | 고정 8개 질의 top5 ID와 score 동일 |
| 불변 범위 | contracts, knowledge, llm_provider, migration, evaluation datasets의 git diff 없음 |
| Prompt / Graph 보존 | [source-preservation.json](source-preservation.json): 분석 SYSTEM, 세 workflow의 messages AST, LangGraph add_node/add_edge 호출 동일 |
| 이벤트/숫자/ID | [artifact-verification.json](artifact-verification.json): 실제 기록 행 순서, 5건 생성 일치, provider 호출 수, Job/run/Trace 연결 pass |
| Fake/오류/Timeout/동시 실행 | 신규 17개 summary 테스트 + 기존 provider/Job 테스트 pass. 실제 모델 Timeout을 유발하는 추가 장시간 호출은 하지 않음 |
| 저장 실패/롤백 | 신규 Java 4건 및 기존 Job fencing/실패 테스트 pass. 커밋 전/롤백 후 저장 행 없음 |

추가 검증은 [extra-regression-results.json](extra-regression-results.json)에 있다. 기존 Phase 0~15의 현재 단위·통합 suite를 실행했다. 과거 단계별 소스 해시의 ‘변경 없음’ assertion은 이후 단계가 있는 현재 트리에 그대로 적용하지 않았다. 과거 UI 브라우저 전체 시나리오, 동시 실모델 부하, 실모델 실행 중 재시작은 이번 작업에서 반복하지 않았다.

최종 이미지 반영 후 [final-runtime-smoke.json](final-runtime-smoke.json)과 [final-runtime-smoke.log](final-runtime-smoke.log)에서 AI/Backend health UP, 추가 모델 호출 0, 같은 runId/traceId, `RESULT_SAVED → WORKFLOW_COMPLETED` 순서를 다시 확인했다. 검증 빌드가 생성한 추적 대상 frontend/dist는 작업 시작 상태로 복원했다. 이후 회귀 도구는 frontend 빌드를 OS 임시 폴더로 출력하도록 했다.

Java 첫 실행의 1건 실패는 기존 예약 Worker와 동기 통합 테스트 간 advisory lock 경합(예상 200, 실제 429)이었다. [java-regression-initial.json](java-regression-initial.json)에 보존했다. 테스트 Compose에서만 `ANALYSIS_JOBS_ENABLED=false`로 설정한 후 전체 suite가 통과했다. 운영 Worker 동작은 바꾸지 않았다. 최초 실검증 스크립트도 실제 분석에서 반드시 TC가 나올 것이라는 assertion으로 실패했으며, 서비스 자체는 정상 정책 보류였다. 이 가정을 제거하고 별도 supported fixture 검증으로 분리했다. 추가 Qwen 분석 호출은 없다.

### Trace 목적지 확인의 제한

AI/Backend summary에서 동일한 jobId/runId/traceId를 확인했다. OTel 기존 9개 테스트에서 in-memory span export, parent 전파, retry/Timeout·보안 검증이 통과했다. 그러나 기존 Jaeger는 query extension 초기화에서 포트를 열지 못했고 Collector의 `jaeger:4317 connection refused` 및 retry 후 drop을 확인했다. 볼륨을 보존한 Jaeger 재시작 1회로도 복구되지 않았다. 따라서 **실제 Trace가 Jaeger에 저장·조회됐다고 주장하지 않는다**. [trace-verification.json](trace-verification.json)에 기록했다. 이 장애는 stdout summary 및 Job/DB 저장과 독립적이다. Jaeger 설정·데이터·스키마는 수정하지 않았다.

## 재검증 도구와 변경 파일

`run-regression.py`, `run-java-regression.py`, `run-extra-regression.py`, `run-evaluation-db-regression.py`는 회귀 실행 도구다. Docker 접근 권한이 필요하다. 기존 증거 폴더는 덮어쓰지 않고 원시 테스트 로그는 OS 임시 폴더에 저장한다. Java/평가 DB는 별도 프로젝트의 tmpfs를 사용하고 종료 시 그 테스트 프로젝트만 정리한다. 테스트용 Java 이미지는 현재 Backend build target으로 생성한다.

`verify-live.py`는 새 합성 요구사항/Job을 생성하여 실제 모델을 호출한다. `verify-real-generation.py`도 실제 모델을 호출하므로 자동 회귀에 포함하지 않는다. `collect-examples.py`는 AI 테스트 컨테이너에서 Fake 로그를 수집하며 모델 호출은 없다. `verify-summary-artifacts.py`는 저장된 로그만 검사한다.

이번 변경 소스(기존 미커밋 변경과 구분):

- `.env.example`, `compose.yaml`: summary 토글 및 버퍼링 설정.
- `ai-service/Dockerfile`, `observability/Dockerfile.ai`: Python unbuffered stdout.
- `ai-service/app/workflow_summary.py` **추가**: context, 출력, provider 구분, 안전한 오류코드.
- `ai-service/app/main.py`: ASGI correlation middleware 등록.
- `ai-service/app/analysis_service.py`, `test_case_service.py`, `change_impact.py`: 실제 단계의 summary hook.
- `ai-service/app/graph_analysis_api.py`: ContextLlm의 provider 식별용 delegate 노출.
- `ai-service/app/analysis_api.py`: 예외 원문/stack 대신 고정 오류코드 logging.
- `ai-service/tests/test_workflow_summary.py` **추가**: 17개 검증.
- `backend/.../observability/WorkflowSummary.java`, `WorkflowSummaryAspect.java` **추가**: 커밋 기준 로그·실행 context.
- `backend/.../observability/TraceHttpInterceptor.java`: Job/run 헤더 전달.
- `backend/.../analysis/AnalysisService.java`, `testcase/TestCaseService.java`, `jobs/JobWorker.java`: 검증·저장·실패 hook.
- `backend/src/test/java/com/example/legacyassistant/observability/WorkflowSummaryTest.java` **추가**: 4개 검증.
- `observability/python/workflow_otel/__init__.py`: summary 모드의 AI workflow JSON 콘솔 중복 억제; span export 유지.
- `docs/workflow-logging/`: 본 문서, 실제/Fake 로그, 결과 JSON, 회귀/검증 도구와 격리 테스트 Compose.

기존 사용자 변경이 있던 `backend/Dockerfile`, `pom.xml`, `Tracing.java`, `WorkflowAspect.java`, 반납 실행 확장, Frontend UI 파일은 이번 작업의 수정 대상에 포함하지 않았다.

정확한 전체 경로 목록은 [changed-files.json](changed-files.json)에 있다.
