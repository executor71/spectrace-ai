"""Generate reports only from this recovery's measured and queried evidence."""
import json
from pathlib import Path

OUT=Path(__file__).resolve().parent
def read(name):return json.loads((OUT/name).read_text(encoding='utf8'))
def write(name,text):(OUT/name).write_text(text,encoding='utf8')
index=read('trace-index.json');live=read('real-results.json');mcp=read('mcp-results.json')
outage=read('outage-validation.json');probe=read('minimal-probe.json')
assert live['analysis']['status']=='SUCCEEDED' and mcp['result']==outage['result']=='PASS'
assert all(item['queryResult']=='PASS' for item in index.values())
assert all(item['result']=='PASS' for item in read('ui-validation.json').values())
assert read('persistent-restart-validation.json')['sameTraceAfterRestart']
assert read('source-preservation.json')['result']=='PASS'
analysis=index['analysis'];tc=index['tc-generation'];job=live['analysis']['jobId']
model=lambda item:next(s for s in item['spans'] if s['operation']=='llm.generate')

trace_rows='\n'.join(f"| {name} | `{item['traceId']}` | {', '.join(item['services'])} | {item['durationMs']:.3f} |" for name,item in index.items())
text=f'''# Actual workflow trace verification

검증일: 2026-10-28 KST. 아래는 실제 실행·저장·조회 결과다. 단일 합성 시나리오의 측정치이며 성능 벤치마크가 아니다. 실제 Qwen 호출은 분석 1회 + TC 선택/생성 1회 = **2회**다.

## Stored and queried traces

| 실행 | 실제 Trace ID | Service Name | Trace 경과 ms |
|---|---|---|---:|
{trace_rows}

별도 최소 SDK probe는 `{probe['traceId']}`, service `{probe['serviceName']}`, Span `recovery.minimum`이다. `jaeger-query-result.json`은 이 최소 probe의 실제 Query API 응답이다. `persistent-restart-validation.json`은 Jaeger 재시작 후 같은 ID가 조회됐음을 기록한다. 각 업무 Trace의 원본은 `<실행명>-query-result.json`, 실제 duration 및 tags 전체 목록은 `trace-index.json`에 있다.

## Requirement Analysis Job

- Requirement ID: `{live['analysis']['requirementId']}`
- Job ID: `{job}` — 상태 **SUCCEEDED**
- Trace ID: `{analysis['traceId']}`
- 분석 결과: confirmed conditions {live['analysis']['conditions']}개, evidence {live['analysis']['evidence']}개
- 실제 `llm.generate`: {model(analysis)['durationMs']:.3f} ms, model `qwen2.5:7b-instruct`, provider `ollama`, retryCount=0, inputTokens={model(analysis)['tags']['inputTokens']}, outputTokens={model(analysis)['tags']['outputTokens']}

`analysis.job.execute`와 `analysis.job.complete`의 `jobId`가 위 Job ID다. AI/Backend 요약 로그의 Job ID·Trace ID·runId를 대조했고 RAG → Qwen → schema/evidence → 저장 순서를 확인했다. Job 생성 요청과 실행은 기존 설계대로 span link로 연결된 서로 다른 Trace이며, 조회할 대상은 **실행 Trace**다. TC 생성은 동기 API이므로 Job ID를 꾸며 넣지 않고 Trace ID로 연결한다.

## TC generation and MCP

TC 입력 분석은 `ai-service/tests/fixtures/test-case-analysis.json`의 **기존 grounded fixture**를 새 요구사항에만 저장했다. 위 실제 분석 Job의 출력이 TC fixture라고 주장하지 않는다. 기존 정책 15개에서 5개가 매칭되고 Qwen이 구조화된 Selection을 반환한 뒤 서버가 기존 템플릿을 materialize했다. 실제 생성 수·저장 수·로그 수 모두 **{live['generation']['testCases']}**개, llmCalls={live['generation']['llmCalls']}이다. Qwen Span은 {model(tc)['durationMs']:.3f} ms다. 이것을 동적 실행 계획이나 5개 execution steps 생성이라고 표현하지 않는다.

이번 분석은 AI Service의 `AnalysisService` 고정 경로이며 RAG도 해당 프로세스의 `VectorSearch`에서 실행됐다. TC 생성은 저장된 분석 근거를 사용하며 새 retrieval을 했다고 표시하지 않는다. 이번에는 change-impact의 LangGraph `retrieve → diff → impact`를 실행하지 않았다. 이 별도 그래프가 이번 분석의 동적 Planning을 수행한 것처럼 설명하지 않는다.

표준 MCP `ClientSession` / Streamable HTTP로 `search_knowledge`, `analyze_requirement`(SAVED), `get_test_cases`, `execute_approved_test` 3회를 실행했다. 총 6회이며 추가 모델 호출은 0회다. 실제 MCP 서버의 `mcp.tool`과 Backend 하위 Span이 같은 Trace로 이어진다. 내부 Dummy dispatch는 `IN_PROCESS`이며 MCP 호출로 포장하지 않는다.

정상 실행은 PASS, mismatches=0이다. 의도적 `synthetic-self-approval-bug` fixture는 기대 HTTP403 / 실제 HTTP200 및 mismatches={mcp['defectId']['mismatches']}로 FAIL을 반환·저장했다. 이 경우 MCP 전달 자체는 SUCCESS이지만 업무 결과는 FAIL이다. DRAFT 실행 거부는 `NOT_APPROVED`이고 MCP/Backend에 ERROR Span이 있다. HITL 검증은 실제 edit/approve API를 **검증 스크립트**로 호출한 것으로, 사람이 클릭한 증거가 아니다.

## Actual outage exercise and limits

Qwen 분석 실행 중 Collector와 Jaeger가 둘 다 stopped임을 inspect로 확인했다. Job은 RUNNING이었고 새 TC 승인, Dummy PASS 실행과 저장 결과 재조회가 성공했다. 관측 서비스는 finally에서 복구했고 전체 검증 경과시간은 {outage['totalExerciseMs']:.2f} ms다. Qwen 종료 후 분석 결과가 저장되고 위 10개 Span을 모두 Query API/UI에서 확인했다. `outage-validation.json` 참조.

첫 장애 검증 스크립트가 실행 API에 빈 JSON 본문을 보내 `EXECUTION_INPUT_NOT_ALLOWED` HTTP400을 받았다. 기존 API는 본문 없는 실행만 허용한다. 서비스는 즉시 복구됐으며 본문 없는 정상 요청으로 스크립트를 고쳐 재검증했다. `outage-first-attempt.json`을 보존했다. 제품 로직을 완화하지 않았다.

실제 TC의 Qwen 호출은 관측 계층이 정상인 상태에서 실행했다. 관측 장애 상태에서 **새 Qwen TC 호출을 추가로 수행하지 않았다**. 대신 네트워크가 없는 Python Fake 분석·TC/관측 테스트와 exporter 실패 조건의 Java 회귀 테스트로 해당 오류 격리 범위를 확인했다. 장애 중 종료된 짧은 review/실행 Span은 유실될 수 있으므로 그 outage 실행의 Jaeger 보존을 주장하지 않는다. 복구 후 별도 MCP 실행의 저장된 Trace가 PASS/FAIL 증거다.

## Measured span lists
'''
for name,item in index.items():
    text+=f"\n### {name}\n\n| Service | Span | 실제 duration ms |\n|---|---|---:|\n"
    text+='\n'.join(f"| {s['service']} | `{s['operation']}` | {s['durationMs']:.3f} |" for s in item['spans'])+'\n'
text+='''
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
'''
write('real-workflow-trace.md',text)

py=read('python-regression-results.json');java=read('java-regression-results.json');extra=read('extra-regression-results.json');ev=read('evaluation-db-regression-results.json');offline=read('python-outage-results.json')
assert all(s['exitCode']==0 for s in py['suites']+extra['suites']+offline['suites'])
assert java['exitCode']==ev['exitCode']==0
counts={'python':sum(s['tests'] for s in py['suites']),'java':java['tests'],'retrievalMetricsAndFrontendUnit':18,'evaluationDatabase':ev['tests'],'existingVideoProjection':4}
assert sum(counts.values())==445
rows='\n'.join(f"| {s['suite']} | {s['tests']} | PASS |" for s in py['suites'])
write('regression-results.md',f'''# Regression results

2026-10-28 실제 수행. 주 회귀 **445개 PASS**, 실패/오류/skip 0. 추가로 네트워크 차단 Python **129개 PASS** 재실행(주 회귀와 중복이므로 445개에 합산하지 않음). 실제 Qwen 분석 1회와 TC 1회 외에 모델을 추가 호출하지 않았다.

| Python suite | Tests | 결과 |
|---|---:|---|
{rows}

| 기타 | Tests | 결과 |
|---|---:|---|
| Java unit/integration, 기존 Phase0–15 동작 | 166 | PASS |
| retrieval metrics | 13 | PASS |
| frontend unit | 5 | PASS |
| evaluation DB | 9 | PASS |
| 기존 video projection | 4 | PASS |

추가 frontend build, frozen RAG 8개 query의 top5/score 비교, DB role 경계, frozen source contracts 검사를 통과했다. 새로 추가한 관측 테스트 2개는 staticmethod 클래스/인스턴스 binding 보존과 실제 기존 materialize의 안전한 Validation Span 및 분석 반환/모델 호출 수 보존을 확인한다.

## Telemetry outage isolation

- Java 전체 166개는 `APP_OTEL_ENABLED=true`, OTLP endpoint `http://127.0.0.1:1/v1/traces` 조건에서 수행했다. 실제 export 실패 문장은 `maven.log.outage-excerpt.log`에 보존했다.
- 별도 Python 컨테이너 `--network none`, OTel enabled + 같은 불통 endpoint에서 기존 AI 118개 및 observability 11개가 PASS했다. Fake 성공, 정책 보류, 모델 timeout/invalid output 및 안전한 오류 메타데이터 등 기존 검증을 포함한다. `python-outage-results.json`과 exporter 거부 로그 발췌 참조.
- 실제 live outage: Qwen 분석이 진행되는 동안 Collector·Jaeger stopped를 확인했고, 신규 TC 승인·Dummy PASS·DB 결과 재조회가 성공했다. 이후 분석 SUCCEEDED/저장 및 완전한 Trace를 확인했다. 범위와 첫 스크립트 HTTP400 수정 이력은 `real-workflow-trace.md` / `outage-*.json`에 구분했다.
- 모델 timeout은 Fake/Mock 테스트로 검증했다. 불필요한 실제 Qwen timeout 호출은 하지 않았다.

DB 회귀는 각각 별도 Compose project와 **격리된 tmpfs PostgreSQL**을 사용했다. 테스트 전용 `down -v`는 해당 project만 대상으로 했고 master 업무 DB/Neo4j는 초기화하지 않았다. 최종 12개 서비스 running, model-init exited(0). PostgreSQL·Neo4j·Ollama·Backend의 StartedAt은 작업 시작 때와 동일하다.

## Reproduction and evidence

```powershell
python docs/observability-recovery/run-regressions.py python
python docs/observability-recovery/run-regressions.py java
python docs/observability-recovery/run-regressions.py extra
python docs/observability-recovery/run-regressions.py evaluation-db
python -m unittest discover -s docs/workflow-logging/video -p test_projection.py -q
python docs/observability-recovery/run-python-outage.py
```

결과 JSON에 원시 테스트 로그의 실제 임시 경로가 있다. `python-regression-results.json`, `java-regression-results.json`, `extra-regression-results.json`, `evaluation-db-regression-results.json`, `python-outage-results.json` 참조. 이번 결과는 보관된 이전 작업 결과를 성공으로 재인용한 것이 아니라 현재 소스에서 다시 실행한 결과다.

프로덕션/관측 소스 변경은 `compose.phase10.yaml`, `observability/python/workflow_otel/__init__.py`, `observability/python/workflow_otel/install.py`, `observability/tests/test_observability.py` 4개다. 나머지는 이 폴더의 진단·검증·보고 자료다. 이전에 있던 작업 변경은 허용된 관측 helper 변경 외에 hash가 모두 유지됐다 (`source-preservation.json`). Qwen·Prompt·RAG·Graph·정책·평가·승인·Ground Truth·DB 스키마는 이 작업에서 변경하지 않았다. commit/push 없음.
''')

write('demo-instructions.md',f'''# Demo observability instructions

작업 디렉터리 `D:\\MASTER과정`. 실제 실행 결과만 아래 Trace에 연결한다. 기존 그래프/분석 흐름은 고정된 흐름이므로 `Workflow`, `mode=FIXED`를 사용한다. 동적 Planning이나 임의의 5-step plan이라고 설명하지 않는다.

## Live summary and debug separation

현재 AI/Backend/MCP에 `WORKFLOW_SUMMARY_LOG=true`가 설정돼 있고 Python은 `PYTHONUNBUFFERED=1`이다. 일반 debug 로그와 별개로 stdout의 `stream=SUMMARY` 행만 선택할 수 있다.

짧은 영어 라벨을 사용하는 기존 영상 viewer (전체 식별자는 원본 로그에도 저장):

```powershell
python -u docs/workflow-logging/video/watch-summary.py --follow --raw-log docs/observability-recovery/demo-summary.raw.log --debug-log docs/observability-recovery/demo-debug.log
```

viewer는 서비스/run별 seq와 Job ID를 우선 표시한다. **Job ID와 Trace ID, 누적 elapsedMs를 동시에 확인**하려면 별도 터미널에서 원본 요약을 필터링한다:

```powershell
docker compose -f compose.yaml -f compose.phase8.yaml -f compose.phase9.yaml -f compose.phase10.yaml -f compose.phase11.yaml logs -f --no-color --no-log-prefix ai-service backend mcp-server | Select-String 'stream=SUMMARY'
```

기존 단일 서비스 명령도 가능하다:

```powershell
docker compose logs -f ai-service | Select-String 'stream=SUMMARY'
```

현재 저장된 실제 Job 로그를 확인할 때 (새 실행이 아니라 **실제 과거 실행의 로그 조회**):

```powershell
Get-Content docs/observability-recovery/qwen-analysis.actual.log | Select-String '{job}'
Get-Content docs/observability-recovery/qwen-generation.video.log
Get-Content docs/observability-recovery/normal-pass.video.log
Get-Content docs/observability-recovery/intentional-fail.video.log
```

실제 로그 파일을 정적으로 보여줄 경우 live 재실행 장면이라고 설명하지 않는다. 이 폴더에는 illustrative/synthetic log generator가 없다. `run-live.py`는 신규 요구사항과 실제 모델 호출을 만드는 검증 도구이며 기록된 실행을 중복하지 않도록 guard가 있다. 단순 시연을 위해 guard를 지우거나 실제 모델 호출을 반복할 필요가 없다.

## Jaeger search and exact query

Jaeger UI: http://127.0.0.1:16686 . 상단 **Lookup by Trace ID**에 아래 ID를 넣거나 링크를 연다. Service 검색은 `legacy-assistant-backend` 또는 `legacy-assistant-ai`, 실제 실행 시각 **2026-10-28 13:48–13:53 KST**를 포함하는 범위를 사용한다. 시간이 지난 뒤 기본 최근 1시간 필터로 과거 실행이 안 보이는 것을 수신 장애로 오해하지 않는다.

- [Actual analysis](http://127.0.0.1:16686/trace/{analysis['traceId']}): `{analysis['traceId']}` / Job `{job}`
- [Actual Qwen TC generation](http://127.0.0.1:16686/trace/{tc['traceId']}): `{tc['traceId']}`
- [Actual MCP PASS](http://127.0.0.1:16686/trace/{index['mcp-pass']['traceId']}): `{index['mcp-pass']['traceId']}`
- [Actual intentional FAIL](http://127.0.0.1:16686/trace/{index['mcp-defect-fail']['traceId']}): `{index['mcp-defect-fail']['traceId']}`

```powershell
$traceId = '{analysis['traceId']}'
$stored = Invoke-RestMethod "http://127.0.0.1:16686/api/traces/$traceId"
$stored.data[0].spans | Select-Object operationName, spanID, @{{Name='durationMs';Expression={{$_.duration / 1000}}}}
```

UI에서 `analysis.job.execute`를 클릭하고 **Tags**를 펼쳐 Job ID를 확인한다. `rag.search → query.embedding/vector.search`, `llm.generate`, `analysis.validation`, `analysis.job.complete`를 확인하고 `llm.generate`의 model=`qwen2.5:7b-instruct`, provider=`ollama`, 실제 duration을 보여준다. `ui-analysis-job.png`, `ui-analysis-qwen.png`는 이 화면을 실제 Chrome에서 확인한 증거다.

TC는 기존 정책 매칭과 Qwen Selection의 결과를 materialize하는 구조다. 생성 5개를 실행 계획 5단계라고 부르지 않는다. MCP는 실제 `mcp.tool`의 toolName과 Backend 하위 Span 연결을 보여준다. Dummy의 `execution.dummy.invoke`는 내부 함수 dispatch다. 정상 PASS와 합성 결함 FAIL(2 mismatches)을 구분한다. 이번 HITL은 검증 스크립트의 실제 승인 API 실행이며 인간 클릭 시연으로 설명하지 않는다.

## Safe recovery / read-only checks

Jaeger를 재생성했다면 먼저 Query 준비를 확인한 뒤 Collector를 재시작해 Docker DNS를 갱신한다. 업무 DB를 내리거나 `down -v`하지 않는다. 고정된 이번 Compose로 **관측 서비스만** 올릴 때:

```powershell
docker compose -f compose.yaml -f compose.phase8.yaml -f compose.phase9.yaml -f compose.phase10.yaml -f compose.phase11.yaml up -d --no-deps jaeger
Invoke-RestMethod http://127.0.0.1:16686/api/services
docker compose -f compose.yaml -f compose.phase8.yaml -f compose.phase9.yaml -f compose.phase10.yaml -f compose.phase11.yaml restart otel-collector
```

```powershell
python docs/observability-recovery/verify-traces.py
```

위 Query 검증은 모델 호출 없이 기존 Trace를 재조회한다. 새 최소 probe가 필요할 때만 `python docs/observability-recovery/validate-pipeline.py`를 사용한다(새 Trace를 생성하고 최소 probe 결과 파일을 갱신함). UI 검증 스크립트는 별도 TEMP 경로의 Playwright와 설치된 Chrome을 사용한다. 버전 호환 설정과 원인은 `config-before-after.md`, `root-cause.md`에 있다. 현재 남은 수신 장애는 없으며 무기한 장애 중 Trace 유실을 방지하는 내구성 큐를 새로 구현한 것은 아니다.
''')

write('completion.json',json.dumps({'result':'PASS','rootFailureStage':'C','rootCause':'Jaeger 2.6 Badger quadratic startup preload; issue7608',
     'jaegerBefore':'2.6.0','jaegerAfter':'2.12.0','originalStorePreserved':True,'probeTraceId':probe['traceId'],
     'analysisTraceId':analysis['traceId'],'analysisJobId':job,'generationTraceId':tc['traceId'],
     'automatedTests':counts,'totalMainTests':sum(counts.values()),'additionalRepeatedPythonOutageTests':129,
     'actualQwenCalls':2,'actualMcpCalls':6,'normalResult':'PASS','intentionalDefectResult':'FAIL',
     'originalStoreRestartQuery':'PASS','actualUiVerification':'PASS','liveOutageExercise':'PASS',
     'sourcePreservation':'PASS','gitCommit':False,'gitPush':False},indent=2))
print('Wrote actual workflow, regression and demo reports; main tests=445, real Qwen calls=2')
