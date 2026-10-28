# 09. 근거 자료집 인덱스와 수집 감사

이 자료집은 최종 결과보고서의 초안 자체가 아니라 검증 가능한 주장·출처·한계를 모은 준비 자료다. 코드·결과·화면을 대조하고, 실제로 하지 않은 시험을 완료로 기록하지 않는다.

## 문서 안내

| 문서 | 용도 |
|---|---|
| [01 프로젝트](01-project-overview.md) | 목적/사용자/브랜치·HEAD/Phase0~15 상태 |
| [02 구성](02-architecture-inventory.md) | 실제 서비스·모델·권한·Graph/OTel 연결 |
| [03 Workflow](03-agent-workflow.md) | 실제 Node/Edge, Qwen·Schema·정책·MCP·Job 경로 |
| [04 시나리오](04-service-scenarios.md) | 업무10단계·실API·배치/실행ID·대표 시나리오 |
| [05 구현 증거](05-implementation-evidence.md) | 구현/테스트/결과/화면/검증 상태 매핑 |
| [06 정량평가](06-evaluation-metrics.md) | 수치·분모·조건·시점·원본·목표/실측 구분 |
| [07 보호장치](07-security-and-reliability.md) | 보안·승인·실행 격리·장애 복구·테스트 |
| [08 한계](08-limitations-and-future-work.md) | 미구현·미검증·추가 증빙·제출 문장 주의 |

## 증거 수준의 읽는 법

- **코드 확인**: 실제 실행 경로가 존재한다. 이것만으로 실모델/운영 검증 완료를 뜻하지 않는다.
- **단위·Fake/Mock**: 정책/Schema/오류/복구 분기의 결정적 검증. 실제 Qwen 성능이나 외부 시스템 성공률이 아니다.
- **실제 서비스·실Qwen**: 실제 API/Provider 호출 및 저장 결과. 요청 수/Provider 시도 수/모델 재사용은 별도다.
- **UI**: 보관된 실제 Chrome/headless 캡처. 일부 오류상태는 intercepted response 또는 격리 DB이며 원본에서 구분한다. 사람의 독립적 판단과 다르다.
- **이번 재조회**: 저장된 결과를 읽어 존재·상태를 재확인했다. 성능/기능 전체를 새로 시험한 것이 아니다.

## 주요 Evidence 목록

| ID | 주장 영역 | 원본 | 적용 범위·주의 |
|---|---|---|---|
| E01 | 프로젝트·초기 DB 경계 | [phase0-recheck](../phase0-recheck.md), [phase1](../phase1-result.md), [bootstrap](../../docker/postgres/init/001-roles.sql) | 당시 실제 health/권한/API. 초기4서비스 상태를 현재 구성으로 재사용하지 않음 |
| E02 | 합성 corpus·기본 검색 | [knowledge](../../knowledge/README.md), [manifest](../../knowledge/manifest.json), [Phase2](../phase2-result.md), [검색 로그](../phase2-evidence/final-ai-tests.log) | 9문서/27청크,8질의 문서 기대값. 검색 GT와 corpus 분리 |
| E03 | 실제 분석·근거 검증 | [5사례](../phase3-evidence/live-analysis-results.json), [결과](../phase3-result.md), [Schema](../../ai-service/app/analysis_models.py) | 실제 API/모델 기록. API 요청5건을 Provider 누적 호출5회로 추정하지 않음 |
| E04 | 원 TC 생성·HITL | [Phase4](../phase4-result.md), [Phase5](../phase5-result.md), [통합 결과](../phase5-evidence/regression-results.json) | 원본 생성본·검토본·revision 분리. 당시 다음 Phase 미구현 문구는 시점 한정 |
| E05 | Frozen 평가 | [GT 파일](../../evaluation-service/datasets/ground-truth-v1.json), [측정3건](../phase6-evidence/measurement-results.json), [결과](../phase6-result.md) | 2026-09-30 생성본 평가. 자유 서술 의미 검증 제외 |
| E06 | Dummy·초기 MCP | [Phase7](../phase7-evidence/completion-summary.json), [Phase9 MCP](../phase9-evidence/mcp-e2e-results.json), [보안](../phase9-evidence/security-tests.json) | 실제 승인/거부/합성 PASS·FAIL. 모델0 호출의 MCP 조회도 존재 |
| E07 | 검색 정량 비교 | [summary](../phase8-evidence/comparison-summary.json), [원시 표본](../phase8-evidence/final-raw-samples.jsonl), [freeze](../phase8-evidence/dataset-freeze.json), [환경](../phase8-evidence/environment.json) | 2026-10-02,32질의/전략96표본. 후보·warmup·모델·hash 고정 |
| E08 | 원래 OTel 실측 | [Phase10](../phase10-result.md), [latency](../phase10-evidence/latency-summary.json), [민감정보 검사](../phase10-evidence/sensitive-data-check.json) | 당시 Trace/지연·30Trace/176Span 검사. 후속 수신 장애는 별도 |
| E09 | Graph 원 평가 | [GT](../phase11-evidence/relation-ground-truth.json), [20문항 원시 결과](../phase11-evidence/multi-hop-evaluation.json), [설명](../phase11-result.md) | 관계 평가·당시 scope. 검색 Recall/일반 LLM 답변 정확도 아님 |
| E10 | Graph 동기화 복구·재평가 | [진단/범위](../graph-sync-repair/README.md), [live](../graph-sync-repair/live-results.json), [새 평가](../graph-sync-repair/multi-hop-evaluation.json), [browser](../graph-sync-repair/browser-results.json) | 음성0.8과 GQ13 범위 충돌 보존. 일부 PNG는 TEMP에만 존재 |
| E11 | UI12·집계/Excel13 | [UI 보고서](../phase12-ui-evidence/report.json), [Phase13](../phase13-result.md), [DB/API 검증](../phase13-evidence/db-api-verification.json) | 실제/격리 DB/응답 대체 상태 구분. 과거 대시보드 건수는 현재 DB 건수가 아님 |
| E12 | 비동기 Job | [Phase14](../phase14-result.md), [실모델 요청](../phase14-evidence/real-llm-result.json), [Fake 복구](../phase14-evidence/fake-provider-results.json), [restart](../phase14-evidence/restart-recovery.json) | 실제1요청과 Fake 두Worker/timeout 시험 구분 |
| E13 | 15개 정책 확장 | [정책](../../contracts/test-case-policy.json), [같은 snapshot](../testcase-policy-extension/same-snapshot-comparison.json), [예제 Fake](../testcase-policy-extension/random-example-validation.md), [실 Qwen TC](../testcase-policy-extension/return-scenario-tests.json) | 0→4 TC/3 of4조건 지원. 예제2/5→5/5는 Fake 조건 |
| E14 | 반납 실행 확장 | [검증 결과](../return-execution-extension/regression-results.md), [실행 지원](../return-execution-extension/execution-support-matrix.md), [PASS](../return-execution-extension/return-pass.json), [FAIL](../return-execution-extension/return-fail.json), [ERROR](../return-execution-extension/return-error.json), [복구](../return-execution-extension/return-restored-pass.json) | 실제6회 이력·신규Qwen0. 현재 활성 TC배치와 다름 |
| E15 | Phase15 구현·최초 모델·캐시 | [README](../phase15-evidence/README.md), [실Qwen](../phase15-evidence/real-e2e-results.json), [최초](../phase15-evidence/analysis-result.json), [최종](../phase15-evidence/final-analysis-result.json), [평가](../phase15-evidence/evaluation-results.json) | 작성자1사례·최초 오분류·독립사람평가 미완료 |
| E16 | Phase15 저장·검토·회귀 스냅샷 | [브라우저](../phase15-evidence/browser-results.json), [회귀382](../phase15-evidence/regression-results.md), [커밋353](../phase15-evidence/commit-validation.json), [보존/Span](../phase15-evidence/preservation-and-traces.json) | 전체 작업 트리와 분리 커밋 스냅샷이 다름 |
| E17 | Workflow 로그·Fake | [실제 영상 증거](../workflow-logging/video/evidence-verification.json), [Fake 결과](../workflow-logging/video/fake/fake-results.json), [시연 예시](../workflow-logging/video/illustrative-output.txt) | 실제 stdout/FAKE/illustrative 예시를 구분. 예시를 실행 증거로 인용 금지 |
| E18 | Jaeger 원인·최소 복구 | [원인](../observability-recovery/root-cause.md), [설정 전후](../observability-recovery/config-before-after.md), [Collector 원본](../observability-recovery/collector-validation.log), [probe 조회](../observability-recovery/jaeger-query-result.json), [재시작](../observability-recovery/persistent-restart-validation.json) | 2026-10-28 원래 Badger 데이터 유지·실저장/조회. UI 열림만으로 판정하지 않음 |
| E19 | 최신 보관 실 Qwen·MCP·회귀 | [trace-index](../observability-recovery/trace-index.json), [실제 결과](../observability-recovery/real-results.json), [MCP](../observability-recovery/mcp-results.json), [회귀](../observability-recovery/regression-results.md), [완료](../observability-recovery/completion.json) | Qwen2/MCP6,445자동+중복129. TC는 별도 grounded fixture 입력 |
| E20 | 이번 읽기 재검증 | [상세](05-implementation-evidence.md), [현재 배치 비교](04-service-scenarios.md) | 2026-10-28 GET/읽기 Graph 조회. 모델·업무 쓰기·평가/테스트 재실행 없음 |

## 대표 화면 원본

| 설명 | 파일 | 상태/시점 |
|---|---|---|
| 일반 입력·Evidence·검토 | [요구사항](../phase12-ui-evidence/requirements-desktop.png), [분석](../phase12-ui-evidence/analysis-desktop.png), [검토](../phase12-ui-evidence/review-desktop.png) | Phase12 보관 화면; 현재 UI를 재촬영하지 않음 |
| 반납 생성 | [Desktop](../testcase-policy-extension/return-desktop.png), [Mobile](../testcase-policy-extension/return-mobile.png) | 실제 Qwen 생성 검증 당시 |
| 반납 결과 | [PASS](../return-execution-extension/return-pass.png), [FAIL](../return-execution-extension/return-fail.png), [ERROR](../return-execution-extension/return-error.png), [차단](../return-execution-extension/return-blocked.png) | 과거 배치/revision의 실제 실행. 현재 DRAFT와 구분 |
| Phase15 | [조건](../phase15-evidence/condition-comparison.png), [후보](../phase15-evidence/affected-testcases.png), [별도검토](../phase15-evidence/developer-review.png), [모바일](../phase15-evidence/mobile.png) | 단일 대표 변경안·보정 후 저장 결과 |
| Jaeger | [분석 Job](../observability-recovery/ui-analysis-job.png), [실제 Qwen](../observability-recovery/ui-analysis-qwen.png), [TC](../observability-recovery/ui-tc-generation-qwen.png), [MCP FAIL](../observability-recovery/ui-mcp-defect-fail.png) | 복구 시 실제 Chrome UI 확인. 이번에는 API 재조회 |

## 이번 읽기 검증 감사

조회 기준시각 `2026-10-28T06:13:01.881841+00:00` UTC, Graph 조회 `2026-10-28T06:14:46.221860+00:00` UTC. 상세 API·식별자·응답200·확인 값은 05와04에 기록했다. 새 Requirement·모델·TC·승인·execution·evaluation 생성 요청, Graph 수동 sync, 컨테이너 시작/중단/재빌드는 수행하지 않았다. Graph POST는 `main.py`에서 `store.read`로 이어지는 사전 정의 **읽기** 조회다.

현재 반납 generationId=`c007519e-fe3b-49e5-8b79-b0dcfe1b20c9`, 과거 대표 실행 generationId=`be9667b9-f10f-49b6-badf-571fd479a491`. 활성 TC4개 DRAFT와 과거 PASS/FAIL/ERROR가 공존한다. 현재 Graph의 Execution0을 실패로 감추거나 임의 실행 노드로 채우지 않는다.

현재 HEAD `155c2664c44df2c902a168a3264c049cb318cf8a`, branch `phase15/change-impact-analysis`, dirty working tree. 이번 문서는 기존 코드/DB/평가셋을 고치지 않고 `docs/final-submission/`의 Markdown9개만 추가하는 범위다. 아래의 기존 파일 SHA는 이번 읽기 기준으로 채집했다.

서비스 상태는 읽기 전용 `docker ps`로, 현재 런타임 버전은 `docker exec ... python -c`의 버전 metadata / `java -version` / `node --version`으로 확인했다. 상세 값과 lock/manifest의 차이는 [02](02-architecture-inventory.md)에 기록했다. 소스/DB/모델을 갱신하거나 의존성을 설치하지 않았다.

## 중요 원본 bytes SHA-256

| 원본 파일 | SHA-256 |
|---|---|
| [contracts/test-case-policy.json](../../contracts/test-case-policy.json) | `c5dab337817d0788228a1ed0cd5cebc74980e5eb7e88303a89ce312717bc2875` |
| [docs/phase8-evidence/comparison-summary.json](../../docs/phase8-evidence/comparison-summary.json) | `69492fc549b60cf6616ef7cbc922cf4cfb6c0af9fda8d08215b90f0fb0e6cfcd` |
| [docs/phase8-evidence/evaluation-dataset.json](../../docs/phase8-evidence/evaluation-dataset.json) | `16cef486474fc0fe35195866e93bf475b0d2c230a71f9ea2e9d2a1c9d6656ff4` |
| [evaluation-service/datasets/ground-truth-v1.json](../../evaluation-service/datasets/ground-truth-v1.json) | `d551efb32fb683f9f6a7e9302c8d5e6750b9efee5e29e4bfde6989511374f8a7` |
| [docs/phase11-evidence/relation-ground-truth.json](../../docs/phase11-evidence/relation-ground-truth.json) | `b37c36e71d49f6e42468d6afa095492bc48cad042a7245577a6fa87f99319772` |
| [docs/graph-sync-repair/multi-hop-evaluation.json](../../docs/graph-sync-repair/multi-hop-evaluation.json) | `827409c9af160969ba1e7087646bb8d615ff0f2e2692ce6b3e47d61f0e793ff6` |
| [docs/phase15-evidence/evaluation-results.json](../../docs/phase15-evidence/evaluation-results.json) | `eb848252b61f91edc45c91a607b0247d170f524ffbde2709225620a54d110981` |
| [docs/observability-recovery/trace-index.json](../../docs/observability-recovery/trace-index.json) | `196060b690f7a0beccdeedd723377f1001b82b6e90e58053ef575d49bd40b12b` |
| [docs/return-execution-extension/return-pass.json](../../docs/return-execution-extension/return-pass.json) | `01a1bb2946369dadaf135c79bf99e8ca48166f3c0f60a35b886eef78a526055e` |

SHA 정의를 구분한다. `ground-truth-v1.json`의 bytes hash와 Phase6의 logical datasetHash는 다르다. `evaluation-service/app/metrics.py:digest` 및 `docs/scripts/phase6-seed.py`가 canonical JSON(정렬/공백 규칙)으로 계산한 datasetHash=`76fbdc9ee68f64c8c88c963920560bfdbafc2aae7b94e70fad72453fd5bd6577`을 사용한다. Phase8의 dataset freeze hash도 해당 원본/실험에서 정의한 hash를 그대로 쓴다. 서로 다른 정의를 비교하여 파일이 변조됐다고 단정하지 않는다.

## 증거 보존과 보고서 작성

보관 결과의 일부 raw 로그/JUnit·Graph PNG는 OS TEMP 경로만 남아 있다. 소스에 없는 파일을 제출 첨부가 완료된 것처럼 쓰지 않는다. 기존 source.zip·baseline hash는 시점별 원본이며 현재 dirty 작업 트리 전체를 대체하지 않는다. 최종 제출 범위 확정과 동일ID E2E 영상·독립 검토는08의 추가 증빙으로 남긴다.

최종 보고서는 기능의 업무 가치→실제 구현→검증 방법→수치/분모→한계 순서로 작성하면 된다. Phase별 PASS를 합산한 총 테스트 수, 예시 로그를 실제 실행, 정적 계획을 동적 Planning, TC 수를 실행 단계 수로 바꾸지 않는다. Git commit/push는 수행하지 않았다.

## 자료집 자체 최종 검사

- 검사 시각: `2026-10-28T06:27:54.150305+00:00` UTC.
- 요청한 Markdown9개가 모두 존재하고 UTF-8로 읽힌다.
- 문서 내 로컬 근거 링크347개를 검사했으며 누락0개다.
- 수집 시작 시 존재한 Git 관리/비ignore 미추적 파일1609개의 SHA-256을 다시 비교했다. 기존 파일 변경0개, 이 폴더 밖 신규 파일0개다. 기존 미커밋 변경을 그대로 보존했다.
- HEAD/branch도 시작 때와 같다. 기능·소스·설정·평가셋 수정, 업무 DB 쓰기 요청, Git commit/push는 수행하지 않았다.
- 문서 링크·hash·원본 숫자/canonical digest 검사는 완료했지만 제품의 자동 회귀/성능 시험을 이번에 재실행한 것은 아니다.

## ?? ?? ??

? HEAD?dirty ??? ?? ?? ??? ?? ??? ?? ??? ????. ?? ???? ??? ???GitHub Push ???? ?? ???UI/Java25?Workflow ???Jaeger ???? ???? ?? ???? ??? ????. ?? ?? ??? ?? ????????? ??? ??? ???.
