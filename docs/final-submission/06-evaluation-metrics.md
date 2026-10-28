# 06. 정량평가 근거와 해석 범위

모든 값은 연결한 **기존 측정 파일**에서 수집했다. 이번에는 평가셋/GT를 변경하거나 검색·Qwen·성능을 재측정하지 않았다. 현재 저장 결과를 GET으로 재조회한 것과 원래 처리시간의 측정을 구분한다. 파일 수정시각을 측정시각으로 대신하지 않는다.

## 1. Vector / Hybrid / Reranker 검색 비교

원본: [comparison-summary.json](../phase8-evidence/comparison-summary.json)의 `groups.all`, [dataset-freeze](../phase8-evidence/dataset-freeze.json), [evaluation-dataset](../phase8-evidence/evaluation-dataset.json), [환경](../phase8-evidence/environment.json), [전체 결과](../phase8-result.md).

- 측정: `2026-10-02T12:54:15.977217+00:00` ~ `2026-10-02T13:07:13.489751+00:00` UTC (2026-10-02 21:54~22:07 KST). 2026-10-28 최신 재측정치가 아니다.
- 합성 IT자산관리9문서/27청크, 질의32개=기존8+신규24. 단일 작성자가 query×27청크를 사전 grade0/1/2로 판정했다. 독립 다수 평가자 검증은 아니다.
- 평가셋 SHA-256 `16cef486474fc0fe35195866e93bf475b0d2c230a71f9ea2e9d2a1c9d6656ff4`, corpusHash `182b26215773607d0cab2116e3297181c3736d7bcc15436849746c0cba77cd2c`.
- finalTopK5, 후보20, RRF k60, BM25 k1=1.5/b=0.75. bge-m3/1024차원 및 bge-reranker-v2-m3, CPU float32/4threads, batch4/maxLength512. 호스트 논리CPU16·Docker 메모리 약32GB, 컨테이너 CPU/memory limit0(미지정).
- 전체 질의 warmup1회 후 전략별 query당3회: **각 전략96표본**. 4전략384표본은 반복측정이지 독립 질의384개가 아니다. 분위수는 선형보간이다.

| 방식 | Hit@5 | Recall@5 | MRR@5 | nDCG@5 | mean ms | p50 ms | p95 ms | Hit 실패 query |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| VECTOR | 96.88% | 90.10% | 0.8854 | 0.8626 | 112.19 | 109.88 | 134.03 | 1 |
| LEXICAL | 100.00% | 88.54% | 0.8589 | 0.8026 | 0.75 | 0.71 | 0.93 | 0 |
| HYBRID | 100.00% | 93.49% | 0.8760 | 0.8598 | 114.42 | 111.34 | 137.92 | 0 |
| HYBRID_RERANK | 96.88% | 91.15% | 0.8854 | 0.8772 | 5670.67 | 5648.10 | 6132.68 | 1 |

기본 단위는 **chunk**다. Hit는 relevant≥1, Recall은 Top5 relevant/전체 relevant의 query macro 평균, MRR은 Top5 안 첫 relevant 역순위, nDCG는 grade 기반 정규화다. Phase2의 문서 기준 Hit8/8 또는 Phase6의 document Recall과 직접 비교하지 않는다.

Hybrid는 이 셋에서 Recall을90.10→93.49%로 높였지만 MRR/nDCG가 모두 개선된 것은 아니다. Reranker는 nDCG0.8772로 가장 높지만 Recall은 Hybrid보다 낮고 CPU p50은5648.10ms다. 기본 분석 검색을 자동 교체했다거나 전 도메인에서 우월하다고 주장하지 않는다. 원본 per-query/실패1질의도 [query별 비교](../phase8-evidence/query-by-query-comparison.json)에 보존된다.

## 2. Graph 관계 탐색 평가 — RAG 검색 품질과 별개

원본 [Phase11 comparison](../phase11-evidence/hybrid-vs-graph-comparison.json) / [원시 평가](../phase11-evidence/multi-hop-evaluation.json), 후속 [sync-repair comparison](../graph-sync-repair/hybrid-vs-graph-comparison.json) / [원시 평가](../graph-sync-repair/multi-hop-evaluation.json), [범위 변화 설명](../graph-sync-repair/README.md).

동결20문항=양성15/음성5, query당 순차3회, 방식당60표본. 관계 GT SHA-256은 `b37c36e71d49f6e42468d6afa095492bc48cad042a7245577a6fa87f99319772`다. Hybrid-only는 Top5 metadata의 결정적 entity/path 추출, Graph 방식은 같은 검색에 저장 TC/Execution 관계 탐색을 추가한다. Qwen 답변 품질 평가가 아니며 Vector 순위/score를 바꾸지 않는다.

최초 Phase11 보관 결과: 측정 JSON에 실행 timestamp가 없으므로 정확한 측정시각은 미확정이다. 완료 이력은 2026-10-11 커밋 `912e0ac`와 `phase11-result.md`로 확인한다.

| 방식 | entity recall | pathAccuracy* | multi-hop success | negative accuracy | p50 ms | p95 ms |
|---|---:|---:|---:|---:|---:|---:|
| HYBRID_ONLY | 0.40 | 0.00 | 0.00 | 0.00 | 158.01 | 225.80 |
| HYBRID_GRAPH | 1.00 | 1.00 | 1.00 | 1.00 | 188.49 | 269.13 |

후속 Graph 동기화/반납 관계 확장 보관 결과: 측정 timestamp 미기재, 2026-10-27 `692d8ae`에 보존된 별도 실험이다. 이를 이번 최신 재측정치라고 하지 않는다.

| 방식 | entity recall | pathAccuracy* | multi-hop success | negative accuracy | p50 ms | p95 ms |
|---|---:|---:|---:|---:|---:|---:|
| HYBRID_ONLY | 0.40 | 0.00 | 0.00 | 0.00 | 139.51 | 175.00 |
| HYBRID_GRAPH | 1.00 | 1.00 | 1.00 | 0.80 | 170.53 | 229.54 |

*JSON의 `pathAccuracy`는 **기대 경로의 정확한 node 순서·relation 포함 비율(coverage)**이며 반환한 모든 경로의 precision이 아니다. entityRecall은 양성 expected typed-ID에 대한 micro recall이다. 후속 음성 정확도0.8은 GQ13의 ‘반납 Rule에 대표 API/TC가 없음’이라는 이전 범위 전제가 실제 반납 지원과 달라졌기 때문이다. GT를 결과에 맞춰 고치지 않았다. 양성1.0을 보고 전체 평가가 모두 성공했다고 쓰지 않는다. 구조화 업무 데이터 접근의 이점이며 일반 GraphRAG 정확도100%를 뜻하지 않는다.

## 3. 기존 Frozen 업무 평가

원본 [Phase6 measurement-results](../phase6-evidence/measurement-results.json), [completion](../phase6-evidence/completion-summary.json), [설명](../phase6-result.md), 구현 `evaluation-service/app/metrics.py`.

측정 시각은2026-09-30 10:49:29~30 UTC. GENERATED 원본 모드, development/validation/final 각1개 합성 사례, 총3개다. logical datasetHash는 `76fbdc9ee68f64c8c88c963920560bfdbafc2aae7b94e70fad72453fd5bd6577`. 이는 canonical JSON digest이며 원본 파일 bytes SHA와 구분한다([09](09-evidence-index.md)).

| 사례 | document Recall@5 | Required Scenario Coverage | deterministic Code Validity | TC 수 |
|---|---:|---:|---:|---:|
| access-development | 75% (3/4) | 40% (2/5) | 100% (5/5) | 5 |
| inspection-validation | 100% (3/3) | 0% (0/3) | N/A (0/0) | 0 |
| concurrency-final | 80% (4/5) | 0% (0/2) | N/A (0/0) | 0 |

8개 checklist 기반 Code Validity는 자유 서술 의미 검증과 다르다. 당시 semantic consistency는 NOT_ASSESSED다. 생성0건의 validity를100%로 바꾸지 않는다. 후속15개 정책 확장 후 이 GT를 다시 평가한 값은 없으므로 옛0%를 현재 전체 생성 범위로 단정하거나 반대로 사후 상승값을 추정하지 않는다. 일반 새 Requirement는 Frozen binding이 없어 자동 평가 대상이 아니다.

## 4. 정책 지원 범위와 Phase15 단일 사례

정책 원본 [15개 plan](../../contracts/test-case-policy.json), [같은 반납 snapshot 비교](../testcase-policy-extension/same-snapshot-comparison.json): 확정4조건 중 지원0/4→3/4, TC0→4. 이는 **정책 지원**75%이며 AI 정확도가 아니다. 5개 예제 지원2/5→5/5는 실제 검색+고정 Fake 분석/생성 조건이다. 5예제 모두 실제 Qwen 성공률100%를 측정한 것이 아니다.

15개 plan 구성은 승인5, 반납4, 검사3, 재고불가1, 자산등록1, 중복승인1이다. 생성과 실행을 분리한다. 반납 검사 성공2종은 명세상 HTTP 계약 미확정으로 자동 실행 미지원이며 파손 증빙 누락400만 제한적으로 실행 지원한다.

[Phase15 evaluation-results.json](../phase15-evidence/evaluation-results.json): 작성자 초안 fixture1건, 독립 사람 검토=false. 2026-10-27 09:25 KST 최초 Qwen1회는 필수 ADDED/UNCHANGED 유형 포함률1/2=0.5였다. 원문 보정/캐시 재처리 후3/3 fixture 부합, API후보1/1·TC후보5/5 집합 일치가 기록됐다. 이는 일반 의미 정확도/영향 precision/recall100% 근거가 아니다. 실제 개발자 수정률은null/미측정이다.

## 5. 실제 Qwen 호출과 처리시간

프로젝트 전체 기간의 중앙 누적 호출 계수는 확인되지 않는다. 다음은 식별 가능한 **대표 세션별 기록**이며 전체 호출 합계로 합산하지 않는다. API 요청 수만 있는 기록은 Provider 실제 호출 수로 바꾸지 않는다. 기본 모델은 Qwen2.5 7B Instruct/Ollama, 로컬 CPU이며 각 실험의 캐시·부하 조건이 완전히 통제됐다는 증거는 없다.

| 기록 / 측정시점 | 실제 모델 호출 근거·표본 | 처리시간과 범위 | 원본 |
|---|---|---|---|
| Phase14 2026-10-21 00:29~00:32 KST | 실제 분석 요청1건; Provider 재시도 횟수는 이 요약만으로 별도 확정하지 않음 | Job 실행132584ms, 대기653ms, 총133237ms; 클릭/API접수 시간과 다름 | [real-llm-result](../phase14-evidence/real-llm-result.json) |
| 반납 TC 2026-10-26, guard epoch1793023371.706906 기준 | Qwen1회/TC4, 기존 분석 snapshot 입력 | 104.327초, Chrome 재조회 검증 포함. 순수 추론시간 아님 | [real-attempt](../testcase-policy-extension/real-attempt.json), [결과](../testcase-policy-extension/return-scenario-tests.json) |
| Phase15 2026-10-27 09:25 KST | Qwen1회, 작성자 fixture1건 | 모델분석39612ms, Job39658ms, 대기868ms | [최초 Job](../phase15-evidence/job-result.json), [E2E](../phase15-evidence/real-e2e-results.json) |
| Phase15 재처리 2026-10-27 09:32 KST | Qwen0회/CACHED_RESULT | 분석4838ms, Job4895ms. 모델이 빨라진 결과가 아님 | [재처리 Job](../phase15-evidence/reprocessing-job.json), [평가](../phase15-evidence/evaluation-results.json) |
| 복구 분석 2026-10-28 13:50~13:51 KST | 실제 llm.generate1개 | LLM Span 83806.662ms, Trace 전체 83985.171ms | [trace-index](../observability-recovery/trace-index.json), [로그](../observability-recovery/qwen-analysis.actual.log) |
| 복구 TC 2026-10-28 13:48~13:49 KST | 실제 llm.generate1개/TC5, grounded fixture 입력 | LLM Span 93896.917ms, Trace 전체 93997.457ms | [trace-index](../observability-recovery/trace-index.json), [저장 결과](../observability-recovery/real-results.json) |

복구 검증 2회는 독립 분석/TC 실행이다. TC fixture가 실제 분석 출력에서 자연스럽게 이어진 E2E라고 쓰지 않는다. `docs/workflow-logging/real-generation-results.json`의 이전 검증은 persisted=false이며 후속 실제 저장 검증과 혼합하지 않는다.

## 6. Dummy·회귀·목표 KPI

- [반납 실행](../return-execution-extension/regression-results.md): 2026-10-26 23:43 KST부터 저장된6회, PASS4/FAIL1/ERROR1의 검증 이력. synthetic 결함/초기화 오류가 포함된 시험 구성이며 운영 장애율·AI 정확도로 계산하지 않는다.
- [복구 MCP](../observability-recovery/mcp-results.json): 2026-10-28 13:52 KST, 실제 Tool6회. 정상PASS/mismatch0, 의도적FAIL/mismatch2, DRAFT실행 NOT_APPROVED. 도구 전달 SUCCESS와 업무 FAIL을 구분한다.
- [회귀](../observability-recovery/regression-results.md): 2026-10-28 자동445개 PASS, 별도 중복 Python 장애 조건129개 PASS. 과거 Phase별 누적 회귀 수를 합산하지 않는다. Fake/Mock 포함 자동 테스트는 실모델 품질 표본 수가 아니다.

| 구분 | 목표/목적 | 실측/현재 근거 |
|---|---|---|
| 업무 생산성 | 근거 탐색·TC 설계·검토 부담 감소 | 수작업 시간 baseline·사용자 비교군·절감률 없음. 수치 목표 합의 기록도 확인 못함 |
| 검색 품질 | 관련 근거를 Top5에서 찾기 | 위 고정32질의 지표. 범용 SLA/목표 달성률 아님 |
| 추적성 | 조건→규칙→API→TC→실행 연결 | 존재하는 관계와 부분 Graph·현재 배치 범위 확인. 일반 관계 정확도 보장 아님 |
| 안전한 자동화 | 근거·정책·승인·Fixture를 통과한 실행 | 테스트 및 합성 PASS/FAIL/ERROR. 운영 자율 실행·인증 체계 구축 아님 |

다음 제출 자료에는 값마다 원본 경로·측정일·평가 단위·분모·환경을 함께 둔다. 과거 지표를 ‘현재 최신’으로 표기하거나 누락/미지원/미평가를0 또는100%로 바꾸지 않는다.
