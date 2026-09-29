# Phase 2 완료 — 합성 Knowledge 및 기본 Vector RAG

검증일: 2026-09-29. 프로젝트: D:\MASTER과정. 결과: 요청 범위 완료.

## 구성과 데이터

- 합성 IT 자산관리 문서 9개, 의미별 Markdown section chunk 27개.
- BUSINESS_RULE 3개, API_SPEC 3개, TEST_GUIDE/POLICY/ERROR_CODE 각 1개; 모든 문서는 3개 section.
- documentId/chunkId는 UUIDv5로 생성한다. 모든 chunk에 documentId, chunkId, documentType, domain, version, section, relatedApis를 저장했다.
- EmbeddingProvider 인터페이스와 LocalEmbeddingProvider 구현을 분리했다.
- 기본값은 ai-service/config/embedding.json에만 정의한다: BAAI/bge-m3, 1024차원, pinned revision 5617a9f61b028005a4858fdac845db406aefb181. 모델명/차원을 provider 코드에 고정하지 않았다.
- .env의 EMBEDDING_MODEL, EMBEDDING_DIMENSIONS, EMBEDDING_REVISION, EMBEDDING_PROVIDER로 설정을 덮어쓸 수 있다. 빈 값은 JSON 설정을 따른다. 실제 모델 출력과 설정 차원이 다르면 실패한다.
- CPU FP32 dense embedding, L2 normalization, query prefix 없음. 512 token 입력 한도를 설정으로 사용하며 초과 입력을 조용히 자르지 않고 거부한다.
- Docker CPU PyTorch/Sentence Transformers를 사용한다. 호스트 Python/JDK/PostgreSQL 설치는 서비스 기동에 필요 없다. 모델 캐시는 embedding-model-cache volume에 보존된다.

## 적재와 검색

- V1~V3는 변경하지 않았다. V4는 Knowledge 모델·profile·metadata 제약을 추가하고 V5는 실제 모델로 생성한 문서/벡터를 초기 적재한다.
- 기존 DB에서 V4/V5 적용 성공. 별도 빈 테스트 DB에서도 V1~V5 전부 성공했다.
- DB 조회: 문서 9, chunk 27, non-null vector 27, 모든 차원 1024. metadata와 원본 문서 타입/버전/domain 일치.
- 적재는 migration_owner의 Flyway만 수행한다. embedding exporter는 DB에 연결하지 않는다. 온라인 AI에는 기존 rag_reader 자격 증명만 전달한다.
- 검색은 정확한 pgvector cosine distance 정렬이다. score=1-cosine_distance이며 topK 범위는 1~10(기본 5). chunk 단위 순위이며 같은 문서가 여러 번 나타날 수 있다. threshold나 문서 중복 제거를 추가하지 않았다.
- API: POST http://localhost:8000/internal/v1/search, JSON {"query":"질의","topK":5}.
- 응답은 배열이며 각 항목에 documentId, chunkId, documentType, section, contentSnippet, score, domain, version, relatedApis가 있다.
- corpus profile과 질의 provider/model/revision/dimension이 다르면 HTTP 503 CORPUS_NOT_READY. schema 선택 인자를 받지 않으며 잘못된 입력은 HTTP 422.

## 8개 질의의 실제 Top-5

검증 fixture는 모델 실행 전에 정한 것을 그대로 사용했다. 기대 문서 목록 중 하나 이상 포함을 Hit@5로 집계한다. “포함 x/y”는 기대 문서 목록에서 실제 포함된 개수다.

| # | 질의 | Top-5 (순위: 문서 / section / cosine score) | 기대 문서 포함 |
|---|---|---|---|
| 1 | 노트북을 이미 빌린 직원이 한 대 더 신청할 수 있나요? | 1. loan-rules / 신청 자격과 중복 대여 제한 / 0.7217<br>2. loan-rules / 동시 승인과 자산 예약 / 0.5881<br>3. asset-lifecycle / 자산 등록과 관리번호 / 0.5867<br>4. loan-test-guide / 동시 대여 승인 테스트 / 0.5787<br>5. loan-api / POST /loans 대여 신청 / 0.5724 | 예 (1/1) |
| 2 | 부서장이 자기 장비 대여 신청을 직접 승인해도 되나요? | 1. loan-rules / 부서장 승인과 자기 승인 금지 / 0.7607<br>2. loan-test-guide / 대여 승인 권한 테스트 / 0.7111<br>3. loan-rules / 동시 승인과 자산 예약 / 0.6430<br>4. loan-api / POST /loans/{loanId}/approve 승인 / 0.6376<br>5. loan-rules / 신청 자격과 중복 대여 제한 / 0.6364 | 예 (1/2) |
| 3 | 동일한 장비를 두 사람이 동시에 승인하면 어떻게 검증하나요? | 1. loan-test-guide / 동시 대여 승인 테스트 / 0.7103<br>2. loan-rules / 동시 승인과 자산 예약 / 0.6635<br>3. loan-test-guide / 대여 승인 권한 테스트 / 0.6560<br>4. loan-api / POST /loans/{loanId}/approve 승인 / 0.5816<br>5. loan-rules / 부서장 승인과 자기 승인 금지 / 0.5810 | 예 (2/2) |
| 4 | 반납한 노트북이 파손된 경우 어떤 상태로 전환해야 하나요? | 1. return-rules / 파손 장비의 수리 전환 / 0.6578<br>2. asset-lifecycle / 수리와 폐기 상태 전이 / 0.6152<br>3. return-rules / 반납 접수와 검사 대기 / 0.5905<br>4. asset-lifecycle / 자산 등록과 관리번호 / 0.5766<br>5. return-api / POST /returns/{returnId}/inspection 검사 완료 / 0.5546 | 예 (2/2) |
| 5 | 대여 신청 API의 요청 필드와 성공 응답 상태는 무엇인가요? | 1. loan-api / POST /loans 대여 신청 / 0.7139<br>2. loan-api / POST /loans/{loanId}/issue 지급 확인 / 0.6946<br>3. loan-test-guide / 동시 대여 승인 테스트 / 0.6822<br>4. loan-api / POST /loans/{loanId}/approve 승인 / 0.6799<br>5. return-api / POST /loans/{loanId}/returns 반납 접수 / 0.6338 | 예 (1/1) |
| 6 | 반납 예정일 당일에 접수해도 연체로 계산하나요? | 1. return-rules / 반납 기한과 연체 계산 / 0.7949<br>2. loan-test-guide / 반납 연체 경계값 테스트 / 0.7071<br>3. return-api / GET /loans/overdue 연체 조회 / 0.6718<br>4. return-rules / 반납 접수와 검사 대기 / 0.6606<br>5. error-codes / RETURN_ALREADY_REQUESTED 중복 반납 / 0.5352 | 예 (2/2) |
| 7 | 대여 내역 CSV를 직원이 내려받을 수 있나요? | 1. access-policy / 대여 내역 CSV 다운로드 / 0.7435<br>2. access-policy / 역할별 조회 범위 / 0.5842<br>3. asset-lifecycle / 대여 가능한 재고 판정 / 0.5754<br>4. loan-test-guide / 대여 승인 권한 테스트 / 0.5697<br>5. loan-rules / 동시 승인과 자산 예약 / 0.5589 | 예 (1/1) |
| 8 | 동일 장비에 반납 요청을 두 번 보내면 어떤 오류가 발생하나요? | 1. error-codes / RETURN_ALREADY_REQUESTED 중복 반납 / 0.6843<br>2. return-api / POST /loans/{loanId}/returns 반납 접수 / 0.6499<br>3. return-rules / 반납 접수와 검사 대기 / 0.5996<br>4. loan-test-guide / 동시 대여 승인 테스트 / 0.5925<br>5. loan-test-guide / 대여 승인 권한 테스트 / 0.5711 | 예 (2/2) |

Hit@5: **8/8**. 기대 목록 전체 포함: **7/8**. 2번 질의는 loan-rules만 포함됐고 error-codes는 Top-5에 없었다. 기대 목록을 결과에 맞추어 수정하지 않았다.

[40개 결과 JSON](phase2-evidence/top5-results.json) · [40개 결과 CSV](phase2-evidence/top5-results.csv)

각 JSON/CSV 결과에는 UUID, documentType, section, 실제 contentSnippet, score를 포함한다. 위 수치는 작은 합성 smoke dataset의 결과이며 일반적인 검색 품질 평가나 최종 Ground Truth Evaluation 결과가 아니다.

## 경계 및 회귀 결과

- evaluation에 검증용 비공개 정답 행을 만든 트랜잭션에서 evaluation_reader는 읽고 rag_reader는 읽지 못하는 것을 확인했다. 전체 ROLLBACK 후 검증 테이블 제거 확인.
- 실제 AI 컨테이너의 rag_reader 로그인으로 app/evaluation SELECT와 rag UPDATE가 SQLSTATE 42501로 거부됐다. AI 환경에는 evaluation/migration/app credential이 없다.
- 검색 API에서 schema=evaluation은 422. SQL은 rag.knowledge_chunk와 rag.knowledge_document만 조회하며 read-only transaction을 사용한다. 검증 질의/기대 문서 fixture와 evaluation은 corpus manifest에 포함하지 않는다.
- AI 단위 테스트 14개, Backend 단위/통합 테스트 17개: 모두 통과.
- 두 health endpoint HTTP 200/UP, 저장된 Requirement 실제 GET 및 React 조회 성공, 두 서비스 정상 표시, JS 오류 없음.
- Phase 1 기존 backend/frontend/DB bootstrap 파일 30개 해시 불변. app/rag/evaluation role grant 변경 없음.

[DB 검증](phase2-evidence/database-check.log) · [실제 AI 계정 검증](phase2-evidence/runtime-security.log) · [AI 테스트](phase2-evidence/final-ai-tests.log) · [Backend 테스트](phase2-evidence/final-backend-tests.log) · [회귀 결과](phase2-evidence/final-regression.json)

## 재실행과 모델 교체

프로젝트 루트에서 docker compose up --build -d로 전체 서비스를 실행한다. V5에 초기 embedding이 포함되어 있어 DB 적재에 별도 모델 호출은 필요 없다. 첫 검색 시 모델 파일을 다운로드하므로 최초 실행은 네트워크와 시간이 필요하며 이후 캐시를 재사용한다.

모델/차원/revision 변경은 설정 변경만으로 기존 corpus와 혼용하지 않는다. 새 설정으로 export_seed를 실행해 embedding을 다시 만들고 **새 migration**으로 교체한 뒤 AI를 재시작한다. 이미 적용된 V4/V5를 수정하지 않는다. 현재 모델의 결과를 자동으로 다른 모델 차원으로 자르거나 변환하지 않는다.

8개 HTTP 질의 재검증(호스트 Python 불필요):

```powershell
$projectPath = (Get-Location).Path
docker compose run --rm --no-deps -v ($projectPath + ':/work') -e SEARCH_BASE_URL=http://ai-service:8000 ai-service python /work/ai-service/tests/run_retrieval_smoke.py
```

## 실행시간과 종료 지연 조치

초기 embedding exporter는 모델 다운로드/추론 결과를 132.126초에 출력했지만 프로세스 반환은 233.328초였다. Transformers 설치 코드의 Thread-auto_conversion 시작 경로를 확인했고, snapshot_download 후 local_files_only로 로드하도록 변경하여 이 경로를 피했다. 캐시 기반 재생성 및 정상 종료는 14.531초였고 최초/재생성 SQL SHA-256은 동일했다. 이전 대화의 모든 120초 지연 원인까지 확정한 것은 아니다.

실제 검색: 첫 질의(모델 로드 포함) 5.708초, 이후 7개 0.096~0.112초. 이는 모델 실행환경에 따른 측정값이다. [명령/도구 분리 시간](phase2-evidence/final-timings.json).

## 변경 파일

- ai-service/app/embedding_contract.py, local_embedding.py: provider 계약/설정/로컬 모델.
- ai-service/app/knowledge.py, seed_export.py, export_seed.py: 섹션 chunk 및 실제 vector seed 내보내기.
- ai-service/app/vector_search.py, search_api.py, db.py, main.py: 읽기 전용 검색 API.
- ai-service/config/embedding.json, requirements-embedding.txt, Dockerfile: 설정·컨테이너 런타임.
- ai-service/tests/test_knowledge.py, test_vector_search.py, test_local_embedding.py, test_search_api.py, run_retrieval_smoke.py, fixtures/retrieval_cases.json.
- backend/src/main/resources/db/migration/V4__prepare_synthetic_knowledge.sql, V5__seed_synthetic_knowledge.sql.
- knowledge/manifest.json, documents/*.md, README.md: 합성 corpus.
- compose.yaml: AI 모델 설정 및 캐시 volume만 추가; DB 역할/credential 경계 유지.
- .env.example, README.md, docs/api.md, docs/architecture.md, docs/data-model.md 및 결과/증거 문서.

## 미해결 사항과 범위

요청 기능의 실행 오류는 없다. 2번 질의의 보조 기대 문서(error-codes)가 Top-5 밖이라는 검색 품질 한계는 그대로 남겼다. Hybrid Search, Reranking, Query Rewrite, LangGraph Requirement Analysis 및 Phase 3로 진행하지 않았다.

참고한 공식 문서: [BGE-M3 모델 카드](https://huggingface.co/BAAI/bge-m3), [SentenceTransformer API](https://sbert.net/docs/package_reference/sentence_transformer/model.html).
