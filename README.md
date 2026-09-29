# Legacy Change Assistant PoC

현재 완료 범위는 Phase 0 기동/권한 경계, Phase 1 Requirement 등록·조회, Phase 2 합성 Knowledge와 기본 Vector 검색, Phase 3 근거 기반 Requirement 분석입니다.

## 실행

Docker Desktop을 실행하고 프로젝트 루트에서:

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
docker compose up --build -d
```

React: http://localhost:5173 에서 제목과 내용을 저장하고 반환된 ID로 조회합니다. Spring health는 http://localhost:8080/actuator/health, AI health는 http://localhost:8000/health 입니다.

PostgreSQL/pgvector, JDK/Maven, Python, Node는 컨테이너 이미지에서 제공합니다. 호스트에 별도 런타임을 설치할 필요가 없습니다. .env는 로컬 개발용이며 commit하지 않습니다.

## Backend 테스트

```powershell
docker compose -f compose.test.yaml -p master-phase3-test up --build --abort-on-container-exit --exit-code-from backend-test
docker compose -f compose.test.yaml -p master-phase3-test down
```

별도 PostgreSQL tmpfs DB에서 실제 V1~V6 migration을 적용하고 app_user로 단위/통합 테스트를 실행합니다. 테스트 DB는 호스트 포트를 열지 않고 앱 DB volume과 분리됩니다. JDK/Python/PostgreSQL의 호스트 설치나 Docker socket 마운트가 필요 없습니다. 테스트 컨테이너는 유한 작업이며 종료코드가 테스트 결과입니다. 결과는 docs/phase3-evidence/test-results에 저장됩니다.

## 경계와 기준점

- app: Spring 업무 계정 app_user. migration_owner는 migration 전용.
- rag: AI의 rag_reader만 읽기. evaluation은 별도 evaluation_reader.
- Phase 0 원본은 docs/phase0-baseline/source.zip과 sha256.json에 보존했습니다(.env 제외).
- Phase 2 원본은 docs/phase2-baseline에 보존했습니다. V1~V5와 Vector 검색, DB bootstrap 권한은 유지하고 Phase 3는 app 분석 테이블 V6를 추가합니다.
- 기존 DB volume은 삭제하지 않습니다. 새 volume은 bootstrap 후 V1~V6, 기존 volume은 아직 적용되지 않은 migration만 적용합니다.

Hybrid Search/Reranking/Query Rewrite/LangGraph 분석/테스트케이스 생성/Evaluation/Dummy 실행/GraphRAG/MCP는 미구현입니다.

[API 계약](docs/api.md) · [Phase 1 결과](docs/phase1-result.md) · [Phase 0 결과](docs/phase0-recheck.md)

## Phase 2 검색

POST http://localhost:8000/internal/v1/search 에 {"query":"반납한 노트북이 파손된 경우 어떻게 처리하나요?","topK":5}를 보냅니다.

기본 모델/차원/revision은 ai-service/config/embedding.json에서 지정하고 EMBEDDING_MODEL / EMBEDDING_DIMENSIONS / EMBEDDING_REVISION 환경변수로 덮어쓸 수 있습니다. 초기 embedding은 V5로 자동 적재되며 질의 모델과 corpus profile은 반드시 일치해야 합니다. 최초 검색은 로컬 모델 다운로드가 필요하고 이후 Docker volume 캐시를 사용합니다.

[Phase 2 전체 결과와 Top-5](docs/phase2-result.md)

## Phase 3 분석

React에서 기존 요구사항을 조회한 뒤 **요구사항 분석** 또는 **저장된 분석 조회**를 누릅니다. 확인된 조건·모호함·누락·업무규칙·API·질문과 검색 근거를 표시합니다.
분석은 Docker Ollama의 로컬 Qwen2.5 7B Instruct를 사용합니다. 최초 Compose 실행은 모델 약 4.7GB 다운로드를 기다립니다. 모델/timeout은 `.env.example`의 ANALYSIS_LLM 설정으로 분리했습니다. 외부 API 키는 필요 없습니다.

POST/GET `/api/requirements/{id}/analysis`. 모델 Schema/근거 검증 실패는 저장하지 않으며 최대 재시도 1회입니다. 기존 검색 입력 제한(2,000자/512토큰)을 넘는 요구사항은 명시적으로 422를 반환합니다.

[Phase 3 설계와 API](docs/phase3-design.md) · [Phase 3 검증 결과](docs/phase3-result.md)

분석 기본값은 `qwen2.5:7b-instruct`, `ANALYSIS_LLM_THINK=false`다. Qwen3 4B는 이 PC에서 의미 분류/형식 호환/추론 timeout 검증을 통과하지 못해 기본값에서 제외했다. 기존 BAAI/bge-m3 Embedding과는 별개의 모델이다.
