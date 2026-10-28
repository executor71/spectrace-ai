# 07. 보안·운영 안정성의 구현 근거

보호장치의 구현과 해당 검증 범위를 연결한다. 로컬 합성 PoC의 검증이며 운영 인증·규제 준수·완전한 보안 보증을 뜻하지 않는다. 이번 작업에서는 장애를 새로 주입하거나 DB/설정을 변경하지 않았다.

| 보호장치 | 실제 구현 / 동작 | 테스트·실행 근거 | 한계 |
|---|---|---|---|
| 합성 데이터만 사용 | `knowledge/README.md`, `manifest.json`, `documents/`; 명시된9문서/27청크 | `ai-service/tests/test_knowledge.py`, Phase2 corpus 증거 | 실제 회사 문서/개인정보 데이터의 처리 검증이 아님 |
| Ground Truth 경계 | `docker/postgres/init/001-roles.sql`, Flyway; app/rag/evaluation 역할 분리. 생성기에 평가 credential·GT mount 없음 | [실제 역할 검증](../observability-recovery/extra-regression-results.json), `evaluation-service/tests/test_database.py`, [Phase6](../phase6-result.md) | 개발 저장소의 공개 합성 GT를 숨긴다는 뜻이 아니라 **실행 경로/권한 경계** |
| 평가 쓰기 제한 | `evaluation-service/app/main.py`의 전용 연결·Frozen binding/hash와 제한된 `evaluation.record_run` | 격리 평가 DB9건, [기존 결과](../observability-recovery/evaluation-db-regression-results.json) | evaluation_reader의 제한된 평가 저장과 app_user의 GT 접근 불가를 구분 |
| Evidence·Schema 검증 | `analysis_models.py`, `analysis_service.py:materialize`, `test_case_registry.py`, Backend `AnalysisValidator`, `TestCasePolicy` | `test_analysis.py`, `test_test_case_generation.py`, `test_policy_extension.py`, `AnalysisIntegrationTest.java`; [실제 Validation Span](../observability-recovery/analysis-query-result.json) | UUID/원문/문서종류/ID와 Schema 검증은 의미 정확도 보장이 아님 |
| Prompt injection 제한 | 사용자/검색 자료는 데이터로 전달; 모델은 카탈로그 ID/적격 plan만 선택, extra field 거부 | [Phase3 실제 지시문 삽입 사례](../phase3-result.md), 단위 위조/근거 오류 검증 | 5개 합성 사례와 고정 검증을 넘어선 red-team 보증 없음 |
| API AllowList/입력 계약 | `DummyApiRegistry`의4개 고정 method/path/API ID, 닫힌 DTO/Fixture, 외부 URL·알 수 없는 필드·실행 body 거부 | `ExecutionIntegrationTest.java`, `ReturnExecutionIntegrationTest.java`, [확장 보안](../return-execution-extension/security-and-hitl.md) |4개 API에 모든 성공/오류 시나리오가 지원되는 것은 아님 |
| HITL·revision | `TestCaseReviewService`가 수정/Fixture 준비 시 DRAFT·revision 증가. 승인된 현재 저장 TC만 실행, 필요 시 If-Match 충돌 검사 | Review 통합/단위, Return 통합, [승인 차단 실제 MCP](../observability-recovery/mcp-approval-blocked-query-result.json) | 로그인/principal 없음. reviewer 이름은 자기 기입, 실제 사람 승인 신원 증명이 아님 |
| 실행 Fixture 격리 | `ReturnExecutionAdapter`, `DummyApiRegistry`의 호출별 독립 메모리; 실제 자산/대여 DB 미변경. 감사 execution만 저장 | Return Adapter4건/통합20건, 동시40개 Fixture 테스트, 실제 PASS/FAIL/초기화 ERROR | 실제 자산 시스템의 트랜잭션/동시성 검증이 아님 |
| 비동기 중복/유실 결과 방지 | `JobStore`, `JobWorker`, `AnalysisGate`: bounded DB queue, unique active job, claim/token/lease/fence·advisory lock·Python slot | `JobStoreTest.java`, `JobWorkerTest.java`, `test_job_capacity.py`, [재시작 기록](../phase14-evidence/restart-recovery.json) | stale RUNNING은 안전한 조건 확인 후 FAILED로 정리하며 모델 작업을 자동 replay하지 않음 |
| Graph 입력·쓰기 격리 | `graph-service/app/model.py`, `queries.py` 고정 label/path/parameter; 수집은 읽기 REST, 별도 background projection | `test_projection.py`, `test_refresh.py`, [실제 Graph 복구](../graph-sync-repair/README.md) | 비동기 최종 일관성·현재 배치 범위; 임의 Cypher/즉시 정합성/과거 전체 이력 보장 아님 |
| MCP 경계 | `schemas.py` additionalProperties=false/UUID, `clients.py` 고정 목적지; UID10001·read-only root·cap_drop·Host/Origin allowlist | `test_gateway.py`, [보안 검사](../phase9-evidence/security-tests.json), [실제 MCP](../observability-recovery/mcp-results.json) | 로컬 loopback 보호이며 인증된 원격 사용자/테넌트 권한 제어 아님 |
| XLSX 안전성 | Backend POI의 문자열 셀·수식 방어, 저장 revision/Expected/Actual 구분 | `ReportTest.java`, `ChangeImpactIntegrationTest.java`, [실제 XLSX](../return-execution-extension/return-report.xlsx) | 임의 대용량/다국가 문서 통합 검증은 별도 |

위 테스트 경로의 전체 prefix: Backend `backend/src/test/java/com/example/legacyassistant/`, AI `ai-service/tests/`, Graph `graph-service/tests/`. 실제 클릭 가능한 파일 매핑은 [05](05-implementation-evidence.md)다.

## Neo4j 장애와 Core 기능

일반 요구사항/분석/TC/승인/실행/DB 저장은 Neo4j를 필수 동기 호출하지 않는다. Graph 서비스가 Core REST를 읽는 방향이므로 동기화 실패가 Core 트랜잭션을 되돌리지 않는다. 관계 화면은 UNAVAILABLE/PENDING/FAILED/PARTIAL을 구분한다. Phase15는 명시적으로 Graph를 읽지만 장애 시 UNAVAILABLE/부분 검토 결과로 표시하고 영향 확정을 하지 않는다. opt-in Graph-assisted API의 오류를 기본 분석 fallback 성공으로 꾸미지 않는다.

근거: [Phase11 실제 Neo4j outage](../phase11-evidence/neo4j-outage.json), [후속 실제 컨테이너 중단/복구와 UI 검사](../graph-sync-repair/browser-results.json), `graph-service/app/refresh.py`, `ai-service/app/change_impact.py:graph_context`. 이번에는 Neo4j를 중단하거나 해당 테스트를 재실행하지 않았다.

## 관측 장애와 업무 격리

Python `workflow_otel.setup`과 Java `Tracing`은 SDK BatchSpanProcessor(큐2048/batch128/500ms)와 exporter timeout1초를 사용한다. Collector는 제한된 memory/queue/retry를 사용한다. 실패한 export를 업무 결과로 전환하지 않는다. 관측이 중단되면 Trace는 유실될 수 있으며 내구성 있는 무손실 전송은 구현하지 않았다.

[2026-10-28 복구 기록](../observability-recovery/root-cause.md): Jaeger2.6 Badger 시작 중복 검색으로 receiver가 열리지 않아 Collector export가 실패했다(C). 결함 수정 포함2.12.0으로만 변경, 원래 Badger 볼륨/경로 유지, 재시작 후 같은 probe 조회 성공. [설정 전후](../observability-recovery/config-before-after.md), [재시작 저장 검증](../observability-recovery/persistent-restart-validation.json).

실제 Qwen 분석 중 Collector/Jaeger 모두 stopped 상태에서 검증 스크립트의 TC 승인·Dummy PASS·결과 재조회가 성공했고 관측 복구 후 분석이 SUCCEEDED·저장됐다. **TC의 새 Qwen 호출은 정상 관측 상태에서 수행했다.** 장애 중 새 Qwen TC 호출을 했다고 주장하지 않는다. 대신 Java166건은 불통 exporter 조건, Python129개는 network=none/OTel enabled 조건으로 재실행했다. 근거 [outage-validation](../observability-recovery/outage-validation.json), [Python outage](../observability-recovery/python-outage-results.json), [회귀](../observability-recovery/regression-results.md).

## 로그·Trace 민감정보

`observability/python/workflow_otel/__init__.py`의 attribute allowlist, UUID 검사·안전한 오류코드·exception event 제외와 Backend `Tracing`/`WorkflowSummary`가 근거다. prompt/요구사항 본문/LLM 응답/추론/GT/credential/SQL parameter를 로그·Span에 넣지 않는다. 입력 길이·토큰 수·모델·ID·상태·측정 시간 등 운영 메타데이터만 사용한다. 증거는 [Phase10 sensitive-data-check](../phase10-evidence/sensitive-data-check.json), `observability/tests/test_observability.py`, [실제 summary 검사](../observability-recovery/evidence-verification.json)다.

UI Evidence 및 권한이 있는 평가 snapshot은 로그가 아니며 합성 원문/평가 내용을 포함할 수 있다. 기존 `.env`/DB/모델 캐시를 제출 문서에 복사하지 않는다. 로컬 개발의 plaintext 내부 통신·기본 개발 설정·인증 부재는 운영 전 보완사항이다. [한계/후속 과제](08-limitations-and-future-work.md) 참조.
