# Demo observability instructions

작업 디렉터리 `D:\MASTER과정`. 실제 실행 결과만 아래 Trace에 연결한다. 기존 그래프/분석 흐름은 고정된 흐름이므로 `Workflow`, `mode=FIXED`를 사용한다. 동적 Planning이나 임의의 5-step plan이라고 설명하지 않는다.

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
Get-Content docs/observability-recovery/qwen-analysis.actual.log | Select-String '63dc4444-ab3a-45b5-b4f5-652a2a7a77bc'
Get-Content docs/observability-recovery/qwen-generation.video.log
Get-Content docs/observability-recovery/normal-pass.video.log
Get-Content docs/observability-recovery/intentional-fail.video.log
```

실제 로그 파일을 정적으로 보여줄 경우 live 재실행 장면이라고 설명하지 않는다. 이 폴더에는 illustrative/synthetic log generator가 없다. `run-live.py`는 신규 요구사항과 실제 모델 호출을 만드는 검증 도구이며 기록된 실행을 중복하지 않도록 guard가 있다. 단순 시연을 위해 guard를 지우거나 실제 모델 호출을 반복할 필요가 없다.

## Jaeger search and exact query

Jaeger UI: http://127.0.0.1:16686 . 상단 **Lookup by Trace ID**에 아래 ID를 넣거나 링크를 연다. Service 검색은 `legacy-assistant-backend` 또는 `legacy-assistant-ai`, 실제 실행 시각 **2026-10-28 13:48–13:53 KST**를 포함하는 범위를 사용한다. 시간이 지난 뒤 기본 최근 1시간 필터로 과거 실행이 안 보이는 것을 수신 장애로 오해하지 않는다.

- [Actual analysis](http://127.0.0.1:16686/trace/669dae9a85fc56beda25818ed582da92): `669dae9a85fc56beda25818ed582da92` / Job `63dc4444-ab3a-45b5-b4f5-652a2a7a77bc`
- [Actual Qwen TC generation](http://127.0.0.1:16686/trace/a9e694e521a4f2c03250f963198cb88d): `a9e694e521a4f2c03250f963198cb88d`
- [Actual MCP PASS](http://127.0.0.1:16686/trace/f8c2ed73f0452934e049a59877a03a18): `f8c2ed73f0452934e049a59877a03a18`
- [Actual intentional FAIL](http://127.0.0.1:16686/trace/554e370d399cd2e2bc3ec5f3e41dad78): `554e370d399cd2e2bc3ec5f3e41dad78`

```powershell
$traceId = '669dae9a85fc56beda25818ed582da92'
$stored = Invoke-RestMethod "http://127.0.0.1:16686/api/traces/$traceId"
$stored.data[0].spans | Select-Object operationName, spanID, @{Name='durationMs';Expression={$_.duration / 1000}}
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
