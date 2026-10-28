# Configuration audit

이번 복구 조작의 Compose 병합: `compose.yaml`, `compose.phase8.yaml`, `compose.phase9.yaml`, `compose.phase10.yaml`, `compose.phase11.yaml`. 프로젝트 `master`. 기존 컨테이너는 생성 시점에 따라 Phase7 local override 등 서로 다른 config_files label을 가지고 있다. 각 컨테이너의 실제 label·허용된 환경값·포트·이미지 ID는 `runtime-before.json`, 원본 설정은 `*.before`에 보존했다. 기존 정상 서비스를 일괄 재생성하지 않았다.

| 항목 | Before | After |
|---|---|---|
| Jaeger image | `jaegertracing/jaeger:2.6.0` | `jaegertracing/jaeger:2.12.0` (Badger preload 중복 제거 수정) |
| Collector image | `otel/opentelemetry-collector-contrib:0.128.0` | 동일 |
| Jaeger 저장소 | `master_jaeger-data:/tmp`; `/tmp/jaeger/keys`, `/tmp/jaeger/values` | 동일, 기존 데이터 유지 |
| AI exporter | HTTP `http://otel-collector:4318/v1/traces`, timeout 1s | 동일 |
| Spring exporter | HTTP `http://otel-collector:4318/v1/traces`, timeout 1s | 동일 |
| Collector → Jaeger | OTLP gRPC `jaeger:4317`, `tls.insecure: true` | 동일 |
| SDK queues/batch | 2048 spans / 128 batch / 500ms | 동일 |
| Collector pipeline | otlp → memory_limiter → batch → otlp/jaeger | 동일 |
| Jaeger pipeline | otlp → batch → jaeger_storage_exporter | 동일 |
| AI validation 관측 | materialize에 개별 Span 없음 | `analysis.validation` wrapper (기존 업무 함수 유지) |

AI validation 행은 기존 evidence/schema materialize 함수를 관측하는 Span만 추가했다는 뜻이다. `wrap`이 staticmethod binding을 보존하도록 수정하고 클래스/인스턴스 호출과 기존 분석 반환·호출 수를 자동 테스트했다. 모델/분석/생성 함수의 입력, 반환, retry와 결정 로직은 유지한다.

## Ports, receivers and TLS

| 경로 | 실제 주소 | Host publish |
|---|---|---|
| 앱 → Collector HTTP | `otel-collector:4318/v1/traces` | `127.0.0.1:14318:4318` |
| Collector gRPC receiver (사용 가능) | `otel-collector:4317` | `127.0.0.1:14317:4317` |
| Collector → Jaeger gRPC | `jaeger:4317` | 없음; Docker 내부 |
| Jaeger HTTP receiver (사용 가능) | `jaeger:4318` | 없음; Docker 내부 |
| Jaeger Query/UI | `jaeger:16686` | `127.0.0.1:16686:16686` |
| Collector health | `otel-collector:13133` | `127.0.0.1:13133:13133` |
| Collector metrics | container loopback `127.0.0.1:8888` | 없음; helper가 Collector network namespace 공유 |

컨테이너 내부 localhost 오용이나 HTTP/gRPC 포트 혼용은 없었다. 내부 receiver는 `0.0.0.0`, Collector exporter는 plaintext gRPC와 Jaeger plaintext receiver로 일치한다. Docker 내부 DNS는 서비스 이름을 사용하며 IP를 설정에 고정하지 않았다. `network-final.json`의 8888 외부 연결 거부는 기본 loopback metrics 바인딩으로, Trace receiver 장애가 아니다. healthv2의 존재하지 않는 `/health/status`에 대한 404도 준비 판정으로 사용하지 않았다.

Collector memory limiter는 128MiB, spike 32MiB, batch 1s/128, export queue 256 batches, retry 1–5s/max10s. Jaeger receiver에 HTTP/gRPC가 명시돼 있으므로 구형 v1의 `COLLECTOR_OTLP_ENABLED` 환경변수는 이 v2 YAML 구성에 추가할 필요가 없다. 호환성은 실제 OTLP/HTTP → OTLP/gRPC → Badger → Query 경로로 검증했다.

서비스 이름은 Python `setup(...)`, Java `Tracing` resource에서 기존 `legacy-assistant-ai`, `legacy-assistant-backend` 등으로 지정한다. `OTEL_SERVICE_NAME`이 따로 없어도 이 resource 값이 사용된다. Traceparent 전파를 유지하며 Phase14 Job 실행은 생성 요청과 span link로 연결된 별도 실행 Trace를 사용한다.
