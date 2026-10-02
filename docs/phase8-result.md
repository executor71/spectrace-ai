# Phase 8 검색 비교 결과

Hybrid의 Recall@5는 90.10% → 93.49%로 증가했고 p50 latency는 109.88ms → 111.34ms였다. Hybrid+Reranker는 nDCG@5 0.8772로 가장 높지만 Recall@5 91.15%는 Hybrid보다 낮고 p50 5648.10ms를 소모했다. 이 작은 CPU 실험에서 reranker의 비용 대비 이점은 제한적이며 기존 사용자 검색을 자동 교체하지 않았다.

## 1. Vector Baseline 보존

Phase 7 기준 소스 125개 파일을 `docs/phase7-baseline/source.zip`과 SHA-256 목록으로 고정했다. 기존 파일 변경은 0개다. Phase 2의 기존 8개 query는 시작 시점·최종 비교·종료 시점 모두 Top-5 chunk 순위와 score가 **정확히 동일**했다. 허용 오차 비교가 아닌 숫자 equality로 검증했다.

BGE-M3 모델/revision, 9 documents, 27 chunks, content, metadata, embedding 벡터 해시, 기존 similarity SQL을 보존했다. `VectorSearch.search`를 그대로 재사용하며 후보 20개를 위한 별도 내부 request 어댑터만 추가했다. 기존 API의 topK 제한과 사용자 Flow는 바꾸지 않았다.

## 2. Hybrid Search 설계

독립 `retrieval-service`는 rag_reader만 사용한다. 기존 Vector 검색과 별도 BM25를 실행하고 `1/(60+vectorRank)+1/(60+lexicalRank)`로 결합한다. 한 branch에 없는 항목은 그 branch 기여가 0이다. 원시 vector/BM25 score를 더하지 않는다. 동점은 chunkId로 정렬한다.

Kiwi(kiwipiepy 0.24.0) 형태소 분석으로 한국어 조사·어미 영향을 줄인다. 명사/용언/수식언/어근을 사용하고, 영문 API 식별자와 오류코드는 정규식으로 원형 단위 보존 후 소문자화한다. BM25 k1=1.5, b=0.75, RRF k=60, branch 후보 수=20, rerank 후보 수=20, 최종 Top-K=5를 결과 조회 전에 고정했다. 튜닝 횟수는 0이다. [Kiwi 공식 설명](https://github.com/bab2min/kiwipiepy)

## 3. Reranker 모델 및 선정 근거

모델은 `BAAI/bge-reranker-v2-m3`, revision `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`이다. 공식 모델 문서의 다국어 cross-encoder이며 별도 원격 코드 없이 Transformers로 로컬 실행할 수 있어 선택했다. 모델명·revision·batchSize=4·maxLength=512·CPU threads=4는 설정 파일로 관리한다. `RerankerProvider` 인터페이스와 `LocalRerankerProvider`를 분리했다. [공식 모델 카드](https://huggingface.co/BAAI/bge-reranker-v2-m3)

Hybrid Top-20의 동일 contentSnippet에 대해서만 raw logit을 계산한다. CPU float32, eval/inference_mode를 사용하며 외부 추론 API는 없다. 실패·비정상 score는 HTTP 503 RERANKER_UNAVAILABLE이며 묵시적 fallback은 없다. 모델 파일별 SHA-256은 `model-artifacts.json`에 있다.

## 4. Evaluation dataset

총 32 query = 기존 8개 + 신규 합성 24개. 모든 query마다 27 chunks를 0/1/2로 사전 판정했다. 2는 직접 답변, 1은 실질적 보조 근거, 0은 무관이다. queryId/queryText/relevantDocumentIds/relevantChunkIds/category/domain 및 모든 grade가 포함된다. Dataset SHA-256: `16cef486474fc0fe35195866e93bf475b0d2c230a71f9ea2e9d2a1c9d6656ff4`.

새로운 검색용 annotation이며 기존 Phase 2의 expectedDocumentKeys 및 Phase 6 Ground Truth를 수정하지 않았다. 기존 8개의 legacy 문서 기대값은 별도로 보존한다. 평가 정답은 evaluation-service/datasets와 평가 산출물에만 존재하고 검색 컨테이너에 복사하거나 mount하지 않는다. 검색 API에는 queryId/queryText/strategy만 전달하며 label 필드는 422로 거부한다.

## 5. Metric 정의

- 평가 기본 단위는 chunk, relevant는 grade > 0이다. 문서 기준 결과와 섞지 않는다.
- Hit@5: Top-5에 relevant chunk가 한 개 이상 있으면 1, 그 외 0; query macro average.
- Recall@5: Top-5 relevant chunk 수 / 해당 query의 전체 relevant chunk 수; query macro average.
- MRR@5: Top-5 내 첫 relevant rank의 역수. Top-5 밖은 0. 전체 27개에 대한 무절단 MRR은 아니다.
- nDCG@5: DCG=sum((2^grade-1)/log2(rank+1)), 같은 query 전체 GT의 이상적 Top-5 DCG로 정규화.
- Latency: 전체 query 1회 워밍업 뒤 각 전략/query 3회 실행. 전략당 96개 sample의 mean/p50/p95. 분위수는 (n-1)*p 선형 보간.
- 실패 query: Hit@5=0. 빈 정답 분모는 N/A이며 100%로 간주하지 않는다.

## 6. 전체 비교 결과

동일 corpus/query/GT/finalTopK/embedding/프로세스에서 측정한 실제 값이다. Lexical은 보조 비교다.

| Strategy | Hit@5 | Recall@5 | MRR@5 | nDCG@5 | mean ms | p50 ms | p95 ms | 실패 query |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Vector Baseline | 96.88% | 90.10% | 0.8854 | 0.8626 | 112.19 | 109.88 | 134.03 | 1 |
| Lexical only | 100.00% | 88.54% | 0.8589 | 0.8026 | 0.75 | 0.71 | 0.93 | 0 |
| Hybrid (BM25 + RRF) | 100.00% | 93.49% | 0.8760 | 0.8598 | 114.42 | 111.34 | 137.92 | 0 |
| Hybrid + Reranker | 96.88% | 91.15% | 0.8854 | 0.8772 | 5670.67 | 5648.10 | 6132.68 | 1 |

### 기존 Phase 2 query 8개

| Strategy | Hit@5 | Recall@5 | MRR@5 | nDCG@5 | mean ms | p50 ms | p95 ms | 실패 query |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Vector Baseline | 100.00% | 87.50% | 1.0000 | 0.9147 | 108.15 | 109.37 | 118.57 | 0 |
| Lexical only | 100.00% | 81.25% | 0.9375 | 0.8294 | 0.75 | 0.70 | 0.92 | 0 |
| Hybrid (BM25 + RRF) | 100.00% | 84.38% | 1.0000 | 0.8919 | 110.40 | 108.96 | 121.46 | 0 |
| Hybrid + Reranker | 100.00% | 93.75% | 0.9375 | 0.9150 | 5583.80 | 5578.71 | 5925.34 | 0 |

### 추가 synthetic query 24개

| Strategy | Hit@5 | Recall@5 | MRR@5 | nDCG@5 | mean ms | p50 ms | p95 ms | 실패 query |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Vector Baseline | 95.83% | 90.97% | 0.8472 | 0.8453 | 113.54 | 110.39 | 135.39 | 1 |
| Lexical only | 100.00% | 90.97% | 0.8326 | 0.7937 | 0.75 | 0.71 | 0.92 | 0 |
| Hybrid (BM25 + RRF) | 100.00% | 96.53% | 0.8347 | 0.8491 | 115.77 | 111.98 | 143.22 | 0 |
| Hybrid + Reranker | 95.83% | 90.28% | 0.8681 | 0.8646 | 5699.63 | 5659.86 | 6227.27 | 1 |

## 7. Query별 개선 및 악화

아래 개선/악화 목록은 4개 metric 중 하나라도 증가/감소한 경우다. 다른 metric이 반대 방향으로 움직이면 양쪽 목록에 들어갈 수 있다. 모든 query의 원문, 정답, Top-5, relevant rank와 성공/실패 변화는 `query-by-query-comparison.json`에 저장했다.

- Hybrid (BM25 + RRF) 개선: phase2-1, phase2-2, phase2-4, synthetic-07, synthetic-09, synthetic-10, synthetic-11, synthetic-13, synthetic-19
- Hybrid (BM25 + RRF) 악화: phase2-8, synthetic-02, synthetic-04, synthetic-14, synthetic-16, synthetic-20, synthetic-22
- Hybrid + Reranker 개선: phase2-1, phase2-2, phase2-3, phase2-4, synthetic-01, synthetic-07, synthetic-09, synthetic-10, synthetic-11, synthetic-13, synthetic-17
- Hybrid + Reranker 악화: phase2-8, synthetic-10, synthetic-16, synthetic-20
- Reranker vs Hybrid 개선: phase2-1, phase2-2, phase2-3, phase2-8, synthetic-01, synthetic-02, synthetic-04, synthetic-07, synthetic-10, synthetic-14, synthetic-17, synthetic-22
- Reranker vs Hybrid 악화: phase2-8, synthetic-10, synthetic-11, synthetic-16, synthetic-19, synthetic-20

실제 검색 성공→실패 사례: **synthetic-19: 이미 완료한 반납 검사를 다시 완료하려 하면 어떻게 되나요?**. Relevant chunk 후보 순위는 Vector Baseline [6] → Hybrid (BM25 + RRF) [5] → Hybrid + Reranker [7]. Hybrid가 Top-5로 복구한 근거를 reranker가 다시 Top-5 밖으로 밀어냈다.

| Query | Vector Recall@5 | Hybrid Recall@5 | Rerank Recall@5 | Vector nDCG@5 | Hybrid nDCG@5 | Rerank nDCG@5 |
|---|---:|---:|---:|---:|---:|---:|
| phase2-1 | 1.0000 | 1.0000 | 1.0000 | 0.9328 | 0.9448 | 0.9639 |
| phase2-2 | 0.7500 | 1.0000 | 1.0000 | 0.7215 | 0.8916 | 0.9604 |
| phase2-3 | 0.5000 | 0.5000 | 0.7500 | 0.8402 | 0.8402 | 0.9260 |
| phase2-4 | 0.7500 | 0.7500 | 0.7500 | 0.8228 | 0.8454 | 0.8454 |
| phase2-5 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| phase2-6 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| phase2-7 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| phase2-8 | 1.0000 | 0.5000 | 1.0000 | 1.0000 | 0.6131 | 0.6241 |
| synthetic-01 | 1.0000 | 1.0000 | 1.0000 | 0.7967 | 0.7967 | 0.9448 |
| synthetic-02 | 0.5000 | 0.5000 | 0.5000 | 0.5213 | 0.4131 | 0.5213 |
| synthetic-03 | 1.0000 | 1.0000 | 1.0000 | 0.6309 | 0.6309 | 0.6309 |
| synthetic-04 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.6309 | 1.0000 |
| synthetic-05 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| synthetic-06 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| synthetic-07 | 1.0000 | 1.0000 | 1.0000 | 0.6313 | 0.7967 | 1.0000 |
| synthetic-08 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| synthetic-09 | 1.0000 | 1.0000 | 1.0000 | 0.6934 | 1.0000 | 1.0000 |
| synthetic-10 | 1.0000 | 1.0000 | 0.5000 | 0.5706 | 0.6509 | 0.6131 |
| synthetic-11 | 0.6667 | 1.0000 | 1.0000 | 0.5906 | 0.6623 | 0.6461 |
| synthetic-12 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| synthetic-13 | 1.0000 | 1.0000 | 1.0000 | 0.9448 | 1.0000 | 1.0000 |
| synthetic-14 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.9639 | 1.0000 |
| synthetic-15 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| synthetic-16 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.6309 | 0.5000 |
| synthetic-17 | 0.6667 | 0.6667 | 1.0000 | 0.9073 | 0.9073 | 0.9871 |
| synthetic-18 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| synthetic-19 | 0.0000 | 1.0000 | 0.0000 | 0.0000 | 0.3869 | 0.0000 |
| synthetic-20 | 1.0000 | 1.0000 | 0.6667 | 1.0000 | 0.9871 | 0.9073 |
| synthetic-21 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| synthetic-22 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.9197 | 1.0000 |
| synthetic-23 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| synthetic-24 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |

### 변경하지 않은 Phase 2 문서 기대값 기준

아래는 새 graded annotation을 사용하지 않고 Phase 2의 기존 expectedDocumentKeys를 그대로 사용한 별도 비교다. Recall 분자는 Top-5 chunks에 포함된 relevant document를 중복 제거한 수다. MRR은 첫 relevant 문서가 등장한 원래 chunk rank의 역수다. 위 chunk 기준 수치와 혼합하지 않는다.

| Strategy | Legacy Hit@5 | Legacy Document Recall@5 | MRR@5 |
|---|---:|---:|---:|
| Vector Baseline | 100.00% | 93.75% | 1.0000 |
| Lexical only | 100.00% | 93.75% | 0.9375 |
| Hybrid (BM25 + RRF) | 100.00% | 93.75% | 1.0000 |
| Hybrid + Reranker | 100.00% | 100.00% | 0.9375 |

### 기존 누락 문서의 rank 변화

rank는 해당 문서 chunk가 처음 등장하는 위치다. 후보 Top-20 밖은 미포함으로 표시한다. 기존 baseline 순위는 수정하지 않았다.

- phase2-2 / error-codes: Vector Baseline 6 → Hybrid (BM25 + RRF) 5 → Hybrid + Reranker 2

## 8. Latency 및 비용 trade-off

실행 환경: Docker Linux 16 CPUs, RAM 30.19 GiB, CPU float32, inference threads=4. 서비스별 인위적 CPU/메모리 제한은 없다. 초기 요청·전체 워밍업은 steady-state 통계에서 제외했다. 최종 측정 동안 다른 테스트·모델 다운로드를 병행하지 않았다.

최초 모델 다운로드와 체크섬 계산: 109.32초, 총 2.293 GB. 이는 매 query 비용이 아니다. 과금형 추론 API 호출은 0회이며 CPU/RAM/전력 비용은 별도다. 실험 후 메모리 관측값은 `resource-snapshot.jsonl`에 저장했으며 peak 메모리라고 주장하지 않는다.

| 초기 요청 | Client ms | Search ms | Reranker model load ms |
|---|---:|---:|---:|
| Vector Baseline | 7640.81 | 5919.71 | 0.00 |
| Lexical only | 4.07 | 0.63 | 0.00 |
| Hybrid (BM25 + RRF) | 132.06 | 102.19 | 0.00 |
| Hybrid + Reranker | 6384.12 | 6379.16 | 520.57 |

Hybrid+Reranker의 steady-state p50은 Vector의 51.40배다. 검색 latencyMs는 서비스 내부 검색 시간이며 clientLatencyMs는 직렬화·로컬 전송을 포함한다. 최초 엔진/토크나이저 준비는 client 첫 요청에 포함되고 initializationMs도 별도 기록한다. 초기 단계 Hybrid 실험에는 localhost 접속 지연이 있어 최종 실험은 IPv4 loopback을 사용했다. 본 표는 최종 실험의 service latency만 사용한다.

## 9. 발견한 한계

- 9 documents / 27 chunks는 매우 작은 합성 corpus다. 후보 20개가 corpus 대부분을 포괄하므로 큰 corpus의 recall/latency로 일반화할 수 없다.
- 32 query와 relevance는 이번 작업에서 corpus 내용을 바탕으로 구성한 단일 synthetic annotation이다. 독립적인 사람 검수·annotator 합의나 미공개 실사용 평가를 대체하지 않는다.
- 원래 8개 query의 과거 검색 결과는 이미 알려져 있었다. 추가 24개는 결과 확인 전에 고정했으며 이후 정답/query/corpus를 수정하지 않았다.
- query당 3회 반복은 PoC latency 관측이며 높은 부하·동시성·cold OS cache를 대표하지 않는다. 통계적 유의성을 주장하지 않는다.
- 제목/section을 검색 입력에 추가하지 않고 기존 snippet과 동일한 본문을 사용한다. 미지원 전략·장애를 성공 결과로 대체하지 않는다.
- 실제 query/chunk 864쌍의 최대 길이는 154 tokens로 512 제한 이내이며 truncation은 0건이다. 원본 chunk 최대 길이도 284자로 snippet 700자 제한보다 짧다.
- Hybrid나 Reranker가 모든 query와 모든 metric을 개선한다고 주장하지 않는다. 악화 사례를 포함한 원시 결과를 보존했다.

## 10. Phase 0~7 회귀 결과

자동 테스트 225개 통과: 기존 Backend 84, RAG/Analysis/Generation Python 61, Evaluation 40, 신규 Retrieval 27, 신규 Metric 13. 실패/오류/skip 0. 기존 React 화면은 변경하지 않았으며 Chrome에서 Requirement/Analysis 조회, 승인 TC Dummy PASS/FAIL, 새로고침 후 이력 유지가 통과했다.

app/rag/evaluation 권한 경계를 보존했고 추가 DB migration은 없다. 검색 역할은 rag_reader이며 app/evaluation SELECT 및 rag DELETE가 실제 거부된다. 기존 Evaluation snapshot 재현, 기존 승인/반려 JSON 보존, Phase 2 Top-5와 score의 정확한 일치를 확인했다.

## 11. 변경 파일 및 재현

기존 파일 변경 0개. 추가 파일 목록은 `phase8-evidence/changed-files.json`을 참조한다. 기존 사용자 API/UI/프롬프트/Dummy API는 그대로다.

1. 기존 Phase 7 서비스를 기동한 상태에서 `docker compose -p master -f compose.yaml -f compose.phase7-local.yaml -f compose.phase8.yaml build retrieval-service` 실행. 신규 이미지는 기존 `master-ai-service:latest`의 고정 환경을 재사용하며 baseline 파일 해시 검증으로 다른 소스를 거부한다.
2. 모델 최초 준비: 같은 compose 인자로 `run --rm --no-deps -e HF_HUB_OFFLINE=0 -e TRANSFORMERS_OFFLINE=0 retrieval-service python -m retrieval.download`.
3. 같은 compose 인자로 `up -d --no-deps retrieval-service`. 정상 추론은 offline이다.
4. `python docs/scripts/phase8-run.py --stage final`. 기존 최종 결과가 있으면 reruns 하위에 저장하여 덮어쓰지 않는다. `--query-id`는 개별 query 진단용이며 unknown ID는 명시적 오류다.
5. 개발용 API: `POST http://127.0.0.1:8010/internal/v1/retrieval` with queryId/queryText/strategy. queryId는 correlation ID이며 정답 목록 조회는 evaluation-side CLI에서만 수행한다.
6. `phase8-regression.py`, `phase8-runtime.py`, `phase8-browser-regression.py`로 회귀·권한 경계를 검증한다.

## 12. 미해결 사항

이번 Phase 완료 조건을 막는 미해결 사항은 없다. 결과의 일반화 가능성은 위 synthetic corpus/annotation 한계 내에서 해석해야 한다. Query Rewrite, GraphRAG, MCP, fine-tuning, prompt 튜닝, Dummy 확대, 인증, Failure Analysis는 구현하지 않았다.
