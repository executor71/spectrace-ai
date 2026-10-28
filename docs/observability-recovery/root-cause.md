# OpenTelemetry / Jaeger recovery

검증일: 2026-10-28 KST. 관측 계층만 복구했으며 업무 DB 초기화, Qwen 모델·프롬프트·RAG 정책·LangGraph·평가·승인 로직 변경 및 Git commit/push를 하지 않았다.

## 원인과 실패 구간

**C: Collector 수신 후 Jaeger export 실패**가 주 장애였다. Jaeger 2.6.0 프로세스는 running이었지만 Badger trace reader의 시작 작업이 끝나지 않아 OTLP 4317/4318과 Query 16686이 열리지 않았다. UI 가용성으로 복구를 판단하지 않았다.

`jaeger-goroutines.log`의 실제 SIGQUIT 스택은 `NewTraceReader → preloadOperations → badger.Iterator.Next`에서 CPU를 사용하고 있음을 보여준다. 2.6.0의 `preloadServices`는 Span마다 중복된 서비스 이름을 slice에 추가한다. 생성자가 각 항목에 대해 operation index를 다시 검색하므로 데이터가 늘면 시작 비용이 이차적으로 증가한다. 공식 [Jaeger issue #7608](https://github.com/jaegertracing/jaeger/issues/7608)과 일치한다. [2.6.0 reader](https://github.com/jaegertracing/jaeger/blob/v2.6.0/internal/storage/v1/badger/spanstore/reader.go), [2.12.0 reader](https://github.com/jaegertracing/jaeger/blob/v2.12.0/internal/storage/v1/badger/spanstore/reader.go)의 중복 제거 map 수정은 `upstream-reader-fix.diff`에 보존했다.

처음에는 저장소 문제도 의심했다. 원본을 백업한 뒤 **작업 복사본**만 Badger Flatten을 실행했으나 시작 장애는 해결되지 않았다. 빈 진단용 저장소는 처음 시작됐지만 Span을 받은 후 2.6.0을 재시작하면 같은 장애가 재현됐다. 따라서 새 디렉터리나 압축을 최종 해결책으로 채택하지 않았다. 데이터 손상으로 확정하지 않는다.

최종 수정은 결함 수정이 포함된 Jaeger **2.12.0 고정**이다. 임의 최신 버전으로 전체를 교체하지 않았다. 기존 `master_jaeger-data`의 `/tmp/jaeger/keys`, `/tmp/jaeger/values` 경로를 그대로 사용했다. 이전 서비스 목록이 복원되고 새 Trace가 저장·조회되며 재시작 후 같은 Trace가 다시 조회됐다 (`persistent-restart-validation.json`).

재생성 중 Jaeger IP가 바뀐 뒤 Collector에 `lookup jaeger on 127.0.0.11:53: no such host`가 남은 별도 과도 장애도 있었다. Jaeger Query 준비 후 Collector를 재시작하여 해결했다. 원래 서비스 DNS와 endpoint 자체가 잘못된 것은 아니었다. 초기 실패한 probe는 `pipeline-initial-failure.json`에 남겨 최종 성공과 구분했다.

## A–F 분리

| 구간 | 확인 결과 |
|---|---|
| A 앱 Span 생성 | Collector의 기존 accepted spans와 최종 실제 앱 Trace로 확인. 주 원인 아님 |
| B 앱 → Collector | AI/Java OTLP HTTP 사용. Collector 4318 수신 성공. 주 원인 아님 |
| C Collector → Jaeger | 원래 수신은 증가하나 sent=0, Jaeger 4317 connection refused. 주 장애 |
| D 저장·조회 | 원래 Query 초기화 정체. 수정 후 Query API 결과와 재시작 보존 확인 |
| E 검색 조건 | 기존 `legacy-assistant-*` 이름 유지. 정확한 Trace ID로 API/UI 검증 |
| F sampling/batch | sampler 환경변수 없음, SDK 기본 parent-based always-on. probe sampled=true. 500ms SDK / 1s Collector / 1s Jaeger batch. 원래 지속 실패는 batch 지연이 아님 |

장애 중 export retry의 유한한 한도와 큐 때문에 Trace가 손실될 수 있다. 복구가 과거의 모든 손실 Trace를 복원했다는 의미는 아니다. 원본 저장소에 남은 Trace 및 이번에 실제로 조회한 Trace만 증거로 사용한다.

## 안전한 진단과 보존

전체 시작 상태와 허용된 설정은 `runtime-before.json`, 연결 결과는 `network-before.json`, 원래 오류는 `otel-collector-before.log`와 `jaeger-before.log`에 있다. 당시 12개 서비스가 running이고 `analysis-model-init`는 정상 exited(0)였다. running 상태만으로 receiver 준비를 판단하지 않았다.

원본 관측 볼륨을 `spectrace-jaeger-backup-20261028` 및 `spectrace-jaeger-work-20261028`로 복사했고 파일 SHA-256 및 크기를 `store-backup.json`에 기록했다. PostgreSQL/Neo4j 볼륨은 복사·초기화·삭제하지 않았다. 진단용 이미지와 복사 볼륨은 재검토 가능하도록 보존했다. 원본 볼륨의 작은 `/tmp/jaeger-active` 진단 디렉터리는 최종 설정이 사용하지 않는다.

## Collector counters ?? ??

| Snapshot | accepted | sent | failed export | refused | queue |
|---|---:|---:|---:|---:|---:|
| Before | 998866.0 | 0.0 | 995892.0 | 0.0 | 75.0 |
| Final after restored workflows | 21336.0 | 21336.0 | 0.0 | 0.0 | 0.0 |

?? ?? Collector instance? ?? counter??? ?? ?? ?? ????? ???? ??? ???. ?? Span? ???? ???? ?? probe? Span ?? ??? ???. ?? probe ? ?? ??? ?? ??? ??? Trace ID? Query API ????. ??? `collector-validation.log`, `collector-metrics-before.log`, `collector-metrics-final.log`? ??.
