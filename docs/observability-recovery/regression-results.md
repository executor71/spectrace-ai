# Regression results

2026-10-28 실제 수행. 주 회귀 **445개 PASS**, 실패/오류/skip 0. 추가로 네트워크 차단 Python **129개 PASS** 재실행(주 회귀와 중복이므로 445개에 합산하지 않음). 실제 Qwen 분석 1회와 TC 1회 외에 모델을 추가 호출하지 않았다.

| Python suite | Tests | 결과 |
|---|---:|---|
| ai | 118 | PASS |
| retrieval | 27 | PASS |
| evaluation-metrics | 22 | PASS |
| evaluation-api | 12 | PASS |
| mcp | 26 | PASS |
| graph-projection | 28 | PASS |
| graph-analysis | 4 | PASS |
| observability | 11 | PASS |

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
