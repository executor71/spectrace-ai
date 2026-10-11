# Phase 11 — Knowledge Graph / Graph-assisted RAG 결과

Phase 10 기준점 717개 파일을 SHA-256과 ZIP으로 고정한 뒤 구현했다. 기존 파일 변경은 선택 경로 연결에 필요한 8개이며 709개는 동일하다. 기본 RAG·Analysis·TestCase·Review·Evaluation·Dummy 실행 로직과 저장된 분석·검토·근거는 보존했다. 실제 Qwen 호출은 0회다.

## 1. 도입 목적과 범위

텍스트 검색만으로 조회할 수 없었던 Requirement → 업무규칙 → API → TestCase → Execution 관계를 조회하는 별도 확장이다. PostgreSQL 업무·vector·evaluation 저장소를 Neo4j로 이전하지 않았다. 자동 실행, 임의 Cypher, LLM graph mutation, A2A는 구현하지 않았다.

현재 투영 범위는 기존 Requirement 3개, TC 10개, Phase 2의 합성 문서 9개/청크 27개와 해당 실행 이력이다. 최초 Sync는 161 nodes / 191 edges였고, 회귀·장애 테스트가 기존 승인 TC의 실행 이력을 추가한 뒤 최종 Sync는 **190 nodes / 220 edges**다.

## 2. Graph Data Model / Node

| Node | 기존 식별자 | 최종 개수 |
|---|---|---:|
| Requirement | Requirement UUID | 3 |
| BusinessRule | BUSINESS_RULE documentId | 3 |
| Api | 기존 Phase 7 apiId | 2 |
| TestCase | testCaseId | 10 |
| Evidence | chunkId | 27 |
| Execution | executionId | 145 |

별도 임의 업무 ID를 만들지 않았다. 실행 노드에 실행 당시 `testCaseRevision`, `apiId`, `result`, `executedAt`, `durationMs`, 합성 결함 표시를 보존한다. 현재 TC revision과 과거 실행 revision을 구분한다. Review는 별도 노드 대신 현재 TC의 approvalStatus/reviewRevision으로 표시한다.

## 3. Edge와 근거

| 관계 | 생성 기준 | 개수 |
|---|---|---:|
| Requirement → SUPPORTED_BY → BusinessRule | 저장 분석의 chunkId와 원문 문장 일치 | 3 |
| Requirement → AFFECTS → Api | 저장 분석 API와 청크 relatedApis의 일치 | 3 |
| Requirement → GENERATES → TestCase | 기존 생성 결과의 소속 Requirement | 10 |
| BusinessRule → IMPLEMENTED_BY → Api | 기존 업무규칙 청크의 relatedApis | 2 |
| BusinessRule → VERIFIED_BY → TestCase | TC 근거 문서와 현재 canonical endpoint 일치 | 8 |
| Api → VERIFIED_BY → TestCase | 기존 apiId·method·pathTemplate 일치 | 9 |
| TestCase → BASED_ON → Evidence | 원본 documentId/chunkId 쌍 | 40 |
| TestCase → EXECUTED_AS → Execution | 저장 실행의 TC/Requirement ID 일치 | 145 |

관계에는 해당 evidenceChunkIds를 보존한다. BASED_ON은 생성 근거 이력이다. 자산 조회로 수정된 TC에 승인 업무 근거가 남아 있어도 승인 규칙의 VERIFIED_BY 관계를 만들지 않는다. 변조 Endpoint TC는 API 관계에서 제외하며 `NO_CANONICAL_API_MATCH`를 기록한다.

API 범위는 기존 `API-LOAN-APPROVE` (`POST /loans/{loanId}/approve`)와 `API-ASSET-001` (`GET /assets/{assetId}`)다. 다른 명세 Endpoint에 임의 API ID를 부여하지 않았다.

## 4. Neo4j / Schema / Sync

Neo4j Community 5.26.0, Python driver 5.28.1을 별도 Compose 서비스로 추가했다. Bolt/Neo4j Browser는 호스트에 공개하지 않고 Graph HTTP만 loopback 8030에 바인딩했다. PostgreSQL migration과 권한 변경은 **없다**.

Neo4j에는 업무 Node 6종과 내부 Projection 잠금 레코드의 ID uniqueness constraint 7개를 생성한다. 명시적 Sync CLI는 기존 REST 저장 결과와 동결 KB export를 읽는다. Graph 서비스에 PostgreSQL/evaluation 자격증명이나 Ground Truth mount가 없다.

```powershell
docker exec master-graph-service-1 python -m app.sync
```

단일 트랜잭션에서 Projection 잠금 → Node/Edge MERGE → 오래된 관계/노드 정리를 수행한다. 동일 Sync 반복 시 export가 완전히 같았고, 동시 Sync에도 중복이 없었다. 잘못된 속성 쓰기로 실패시킨 Sync는 전체 rollback되었다. [Neo4j 트랜잭션 문서](https://neo4j.com/docs/python-manual/current/transactions/)에 따른 원자적 쓰기 구조다.

원본 business data는 수정하지 않는다. 운영자가 관리하는 `graph-service/data/scope.json`으로 Requirement 범위를 정한다. KB는 명시적으로 갱신하는 버전 고정 export이며 CDC는 없다.

## 5. Graph-assisted RAG

기존 기본 Vector 분석과 Phase 8 Hybrid/Reranker 검색은 그대로 유지한다. 별도 Context 경로는 저장 Requirement의 같은 title+description으로 기존 Hybrid top5를 조회하고 Graph 관계를 결합한다. 기존 top5 순서·점수·텍스트를 변경하지 않는다.

분석에 전달하는 관계는 그 관계를 뒷받침하는 모든 chunkId가 **이번 top5 텍스트 근거 안에 있을 때만** 포함한다. 관계 입력에는 객체 ID와 관계 종류를 담으며 업무규칙 문장을 만들어 넣지 않는다. 기존 AnalysisService의 문장/API catalog와 grounding validator를 그대로 사용한다.

새로운 선택 API:

| API | 용도 |
|---|---|
| POST `/api/graph/find_requirement_context` | Requirement 관계/경로 |
| POST `/api/graph/find_impacted_tests` | 규칙 변경 영향 API·TC·경로 |
| POST `/api/graph/trace_test_case_origin` | TC 생성 근거 및 실행 이력 |
| POST `/api/graph/analysis-context` | Hybrid text + Graph context 미리보기 |
| POST `/internal/v1/graph-assisted-analysis` | 선택적 분석, `persisted:false` |

선택적 분석 API는 필요시 기존 로컬 모델을 사용할 수 있으나 이번 검증에서는 모의 provider로 실제 HTTP 경로와 grounding 거부를 확인했다. 저장된 Phase 3 분석을 덮어쓰지 않는다. Neo4j 장애 시 Context 미리보기는 `graphStatus:UNAVAILABLE`과 원래 textEvidence를 반환한다.

## 6. MCP Graph Tools / 보안

`find_requirement_context`, `find_impacted_tests`, `trace_test_case_origin` 3개를 추가해 총 8개 도구다. 새 도구는 readOnlyHint/idempotentHint=true이고 UUID만 허용하며 추가 필드는 금지한다. 고정 parameterized query만 실행한다.

임의 도구 `execute_cypher`, Cypher 문자열을 UUID로 전달하는 입력, 정상 UUID와 함께 붙인 `cypher` 필드 모두 차단했다. HTTP에서도 422/404로 거부한다. 없는 엔티티는 404, Graph 장애는 503, 경로 수 제한 초과는 413이다. Sync는 HTTP/MCP에 노출하지 않았다.

Graph 노드에 API key, password, 전체 prompt, reasoning, Ground Truth, evaluation snapshot을 저장하지 않는다. Neo4j Community의 별도 읽기 권한 체계를 구현한 것은 아니며, MCP 읽기 제한은 엄격한 도구 계약과 서버의 고정 조회 경로에서 강제한다.

## 7. Multi-hop 평가셋

Graph schema/첫 Sync 전에 원본 저장 결과를 확인하여 **20문항(관계 질문 15 + 부정/없는 관계 5)**을 고정했다. `relation-ground-truth.json`과 SHA-256 파일로 보존하며 평가 때 checksum을 검증한다. 정답 생성 스크립트는 Graph 코드나 Graph 응답을 참조하지 않는다.

원 TC 5개·합성 승인 TC 3개의 생성 경로, Requirement 영향 경로, 규칙 변경 영향, PASS/FAIL 실행 출처, 수정된 자산 TC·변조 endpoint·존재하지 않는 엔티티를 포함한다. 긍정 질문은 모두 2-hop 이상이다.

## 8. Hybrid-only vs Graph-assisted 결과

| 지표 | Hybrid only | Hybrid + Graph |
|---|---:|---:|
| Entity Recall | 40.0% | 100.0% |
| Path Accuracy | 0.0% | 100.0% |
| Multi-hop Success, 긍정 15문항 | 0/15 | 15/15 |
| 부정 질문 정확도, 5문항 | 0/5 | 5/5 |

Entity Recall은 정답 typed ID의 micro recall이다. Path Accuracy는 **정답 경로 중 노드 순서와 관계 종류까지 일치하여 반환된 비율**로, 반환된 모든 경로의 precision은 아니다. 완전 성공은 해당 질문의 정답 엔티티와 경로를 모두 찾았을 때만 인정한다. 엔티티 precision/반환 수는 문항별 JSON에도 기록한다.

Hybrid-only는 변경하지 않은 top5 청크 metadata에서 엔티티와 명시적 Rule→API 관계를 추출한다. Graph 방식은 같은 검색에 저장 업무 데이터의 관계 탐색을 추가한다. LLM answer-quality 비교가 아니다. 텍스트 코퍼스에는 TC·Execution 관계가 없으므로 Graph에 구조적 정보 접근의 이점이 있다. 이 결과를 일반 검색 우월성이나 Vector Recall@5 상승으로 해석하지 않는다.

## 9. Latency

각 문항/방식 3회, 방식당 60회 end-to-end 측정:

| 방식 | p50 | p95 |
|---|---:|---:|
| Hybrid only | 158.01 ms | 225.80 ms |
| Hybrid + Graph | 188.49 ms | 269.13 ms |

로컬 환경의 순차 반복 측정이며 부하 실험이나 통계적 유의성 검증은 아니다. 고정 질문이 같은 소규모 합성 도메인을 공유한다.

## 10. 대표 경로와 React

실제 원본 ID를 사용한 예:

```text
80e2d374-0825-4811-a11e-03ade256b6e8 (Requirement)
 → SUPPORTED_BY → 7cea4fe7-6b00-56c9-be35-3194aeecb923 (BusinessRule)
 → IMPLEMENTED_BY → API-LOAN-APPROVE
 → VERIFIED_BY → 4611bca5-0d0c-45dd-9793-75566c432c89 (TestCase)
 → EXECUTED_AS → 기존 executionId, FAIL, revision 4
```

React에서 Requirement 조회 → 저장 Analysis → 저장 TC → 관계 그래프 → Rule 영향 경로 → TC 생성 근거/실행 이력 → PASS/FAIL → 새로고침/재조회 순서로 확인했다. 실제 Chrome **155.0.8059.40**, 콘솔 오류 0, 모델 호출 요청 0이다. 의도적 자기 승인 결함의 기존 FAIL을 표시하며 Graph가 결과를 재판정하지 않는다.

스크린샷: [전체 그래프](phase11-evidence/graph-overview.png), [규칙 영향 경로](phase11-evidence/requirement-impact-path.png), [TC 근거/FAIL](phase11-evidence/testcase-origin-path.png), [Jaeger](phase11-evidence/jaeger-graph-trace.png).

## 11. OpenTelemetry

`graph.sync`, `graph.query`, `graph.traversal`, `graph.context_merge`를 추가했다. nodeCount/edgeCount/hopCount/resultCount/durationMs를 관련 span에 기록하며 Cypher 원문·파라미터·prompt·Ground Truth는 기록하지 않는다.

실제 검증은 **4 traces / 56 spans**. MCP → Graph 부모/자식 span이 같은 Trace ID로 연결됨을 확인했다.

* MCP Graph: `04c97f85eb01d204641ab1ad90ec6b07`
* Context merge: `d9f414c82c5813f5cc48c4d7a9a7589a`
* Sync: `3197fd16589c3519ac4a12d36dbfb529`, `a73c80b848498f0b8493f15dcc4503e5`

## 12. 장애 격리

Neo4j 컨테이너를 실제 중단하고 **15개 검사**를 통과했다. Requirement, 저장 Analysis, TC/Review, Evaluation 조회, Vector/Hybrid, 승인된 Dummy 실행, 기존 MCP 도구 5개가 정상 동작했다. Context는 text-only로 저하되고 Graph 도구만 오류를 반환했다. 중단 중 새 분석 모델 호출은 하지 않았다.

첫 실험에서 Docker DNS 해제 시 Neo4j driver의 ValueError가 fallback을 우회한 문제를 발견해 수정했다. 재실험은 전부 통과했고 Neo4j를 복구했다.

## 13. 회귀 및 테스트

| 검증 | 결과 |
|---|---:|
| 기존 Backend | 84 PASS |
| 기존 AI | 61 PASS |
| 기존 Evaluation | 40 PASS |
| 기존 Retrieval | 27 PASS |
| 기존 Retrieval metrics | 13 PASS |
| 기존 MCP unit | 18 PASS |
| 기존 OTel | 9 PASS |
| 신규 Graph projection unit | 18 PASS |
| 신규 Graph-assisted 분석 unit/HTTP | 4 PASS |
| **위 테스트 합계** | **274 PASS, 실패 0** |
| 기존 MCP E2E | 70 assertions PASS |
| Graph 실제 통합 | 22 assertions PASS |
| MCP Graph | 도구 3개 성공 / 공격 3개 차단 |
| Neo4j 장애 격리 | 15 checks PASS |
| Chrome E2E | PASS |

Phase 2 고정 8쿼리 top5/score와 Phase 5 승인/반려 JSON을 보존했다. Phase 6 evaluation replay와 app/rag/evaluation DB 권한 검사가 통과했다. Phase 8 저장된 384샘플의 지표를 재계산해 일치시켰으며 현재 API로 Vector 32 + Hybrid 32 + Reranker 대표 1쿼리의 순위/점수를 대조했다.

lexicalScore만 기존 Phase 10에서 입증된 부동소수점 합산 차이 때문에 1e-12 허용오차를 적용했고 나머지 반환 필드는 정확히 일치했다. 원본 Requirement 3개의 분석·TC·review·evidence와 기존 execution JSON은 전부 동일하다. 회귀/장애 검증의 승인 실행은 append-only 이력 29개를 추가했다.

## 14. 변경 파일과 Evidence

기존 파일 변경 8개:

* `ai-service/app/main.py`: 선택 분석 router 등록
* `frontend/src/Requirements.tsx`, `frontend/vite.config.ts`: Graph panel/proxy
* `mcp-server/app/{schemas,clients,tools,server}.py`: 읽기 도구 3개
* `observability/python/workflow_otel/__init__.py`: Graph 속성/도구 span

추가 파일:

* `graph-service/`: 모델, 결정적 source projection, Neo4j store/sync, 고정 query, context, HTTP, 합성 KB export/scope, 테스트, Dockerfile/README
* `ai-service/app/graph_analysis_api.py`
* `frontend/src/KnowledgeGraph.tsx`, `KnowledgeGraph.css`
* `compose.phase11.yaml`, `compose.phase11-test.yaml`
* `docs/scripts/phase11-*.py`, `docs/phase10-baseline/`, 본 보고서
* `docs/phase11-evidence/`: 요청한 JSON 10종과 스크린샷 4종, 동결 평가셋, 테스트 로그, DB 경계/원본 보존 증거

기존 backend 로직, DB migration, RAG ranking, 모델, prompt, Ground Truth, 과거 Phase 보고서·evidence는 변경하지 않았다.

## 15. 알려진 한계 / 미해결 사항

필수 검증을 막는 미해결 오류는 없다. 다음은 구현 범위의 한계다.

* 기존 ID가 명시된 API 2개와 설정된 Requirement 3개만 투영한다. BusinessRule은 개별 문장이 아닌 문서 단위다.
* 명시적 Sync 이전에는 관계와 실행 표시가 오래될 수 있다. 실시간 CDC/자동 실행은 없다.
* Graph-assisted 실제 Qwen 출력 품질은 이번에 재평가하지 않았다. 모의 모델과 기존 grounding validator의 HTTP/단위 검증을 수행했다.
* 관계 평가는 소규모 합성 데이터와 구조화된 데이터 접근 효과를 측정한다. 100%를 일반화하지 않는다.
* 다중 경로는 2~3-hop, 경로 쿼리당 최대 2,000개이며 초과시 명시적으로 거부한다. 대규모 그래프/운영 인증 체계는 범위 밖이다.

Phase 11에서 작업을 마쳤으며 Phase 12 기능은 추가하지 않았다.
