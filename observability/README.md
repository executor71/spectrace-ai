# Phase 10 Observability

기존 업무 로직과 JSON 계약 위에 수동 OpenTelemetry 계측을 추가한다. 공식 SDK의 비동기 BatchSpanProcessor → OTLP/HTTP → Collector → OTLP/gRPC → Jaeger 구조다. SQL/HTTP body/프롬프트를 자동 수집하지 않는다.

## 실행

```powershell
docker compose -p master -f compose.yaml -f compose.phase7-local.yaml -f compose.phase8.yaml -f compose.phase9.yaml -f compose.phase10.yaml up -d --build
```

Jaeger: http://localhost:16686 / Collector health: http://localhost:13133.
OTLP gRPC host14317 / HTTP host14318 → container4317/4318. 관측 포트는 loopback에만 공개한다.
Jaeger 2.6.0, Collector contrib 0.128.0, Java SDK 1.49.0, Python SDK/OTLP exporter 1.34.1을 고정했다.
Jaeger는 `jaeger-data` volume의 로컬 Badger 저장소를 사용한다. 스택 중단/복구 뒤 Trace를 보존한다. 로컬 PoC이며 인증/고가용성/보관 기간 운영 정책은 포함하지 않는다.

Python용 Dockerfile은 보존된 `master-{ai-service,retrieval-service,evaluation-service,mcp-server}:phase9-baseline` 이미지를 기반으로 한다. 이 태그는 Phase 10 첫 작업에서 원래 이미지를 보존한 것이다. 새 환경에서는 `docs/phase9-baseline/source.zip`을 별도 폴더에 해제한 뒤 해당 원본 Dockerfile로 다음 태그를 순서대로 빌드한다:

```powershell
docker build -t master-ai-service:phase9-baseline ./ai-service
docker build -t master-evaluation-service:phase9-baseline ./evaluation-service
docker build --build-arg BASELINE_IMAGE=master-ai-service:phase9-baseline -f retrieval-service/Dockerfile -t master-retrieval-service:phase9-baseline .
docker build -f mcp-server/Dockerfile -t master-mcp-server:phase9-baseline .
```

위 4개 명령은 해제한 Phase 9 원본 폴더에서 실행한다. 이어서 현재 프로젝트에서 Phase 10 Compose를 실행한다. 기존 DB와 모델 cache volume은 유지한다.

## 계측 경계

- `APP_OTEL_ENABLED=true`일 때 활성화한다. OTLP endpoint 기본값은 내부 Collector다.
- Java는 API Filter, 서비스 AOP, 기존 RestClient의 Trace Context interceptor를 사용한다.
- Python은 ASGI middleware, 기존 메서드 wrapper, HTTPX/urllib의 W3C header 전파를 사용한다. vector.search는 기존 거리 검색 SQL 실행 시간만 감싸며 SQL/매개변수를 읽어 export하지 않는다.
- `traceparent`/`tracestate`로 서비스 간 parent/child를 연결한다. requestId는 별도 유지한다. MCP의 기존 Tool requestId가 하위 호출에도 전달된다.
- span 이름은 실행한 실제 작업만 나타낸다. 저장 분석 조회는 LLM span을 생성하지 않는다. 분석은 기존 VECTOR 검색을 유지하며 waterfall을 꾸미기 위한 reranker 호출을 추가하지 않는다.
- SDK export는 비동기이며 큐는 2048, batch128, export timeout1초다. Collector에는 메모리 한도와 bounded queue/retry를 둔다. 장애 시 일부 Trace가 유실될 수 있으나 업무 요청은 exporter 응답을 기다리지 않는다.
- Ground Truth, prompt, thinking/reasoning, 문서/입력 원문, contentSnippet, header, secret, SQL 및 exception text/stack을 기록하지 않는다. UUID와 허용한 숫자·상태·설정 이름만 기록한다.
- token usage는 Ollama가 반환한 prompt_eval_count/eval_count만 사용한다. 미제공 시 생략하며 추정하지 않는다.
- 단위 오류 fixture는 `synthetic=true` root로 구분한다. 실제 성능 통계에서 mock 및 warmup을 제외한다.

서비스 이름: legacy-assistant-backend / legacy-assistant-ai / legacy-assistant-mcp / legacy-assistant-retrieval / legacy-assistant-evaluation. 테스트 Client는 legacy-assistant-demo다.
관측 로그는 timestamp/service/level/traceId/spanId/requestId/event/durationMs를 포함한다. Jaeger `/trace/{traceId}`로 연결할 수 있다.
Metrics/Prometheus는 이번 구현에서 생략했다. span duration과 원시 표본으로 count/mean/p50/p95/max를 계산한다.

## 재검증과 실제 모델 호출 제한

`docs/scripts/phase10-regression.py`: 기존 업무 테스트와 MCP E2E. 테스트는 mock 모델만 사용한다.
`observability/tests/test_observability.py`: 민감정보·오류·usage·전파·계측 장애 테스트(테스트 fixture mount 필요).
`docs/scripts/phase10-traces.py`: 실제 Jaeger Trace 구조·오류 코드·민감 필드 검사 및 통계.
`docs/scripts/phase10-outage.py`: Collector/Jaeger 중단→업무 기능 확인→finally 복구.
`docs/scripts/phase10-browser.py`, `phase10-jaeger-details.py`: 실제 Chrome 업무 흐름 및 Jaeger 캡처.
`docs/scripts/phase10-final-check.py`: health·로그 상관관계·기준 파일·Phase 8 저장 실험 재검증.

`observability/tests/real_analysis.py`는 **실제 Qwen을 호출**한다. 이미 검증한 대표 1건의 `real-analysis.json` marker가 있으면 재호출을 거부한다. 일반 회귀나 보고서 재생성을 위해 이 파일을 지우거나 모델 호출을 반복하지 않는다.

과거 Phase 3/8/9 Evidence는 변경하지 않는다. 새 자료는 `docs/phase10-evidence`에만 저장한다. 기존 BM25의 Python set 순회로 프로세스 재시작 간 보조 점수에 ~10^-15 오차가 있을 수 있으며 원래 이미지에서도 재현했다. 이 Phase에서 검색 구현을 튜닝하지 않는다.

공식 참고: [OpenTelemetry Python](https://opentelemetry.io/docs/languages/python/instrumentation/), [Java SDK](https://opentelemetry.io/docs/languages/java/sdk/), [Collector](https://opentelemetry.io/docs/collector/configuration/), [Jaeger v2.6 Badger 구성](https://github.com/jaegertracing/jaeger/blob/v2.6.0/cmd/jaeger/config-badger.yaml).
