# Legacy Change Assistant PoC

현재 완료 범위는 Phase 0 기동/권한 경계와 Phase 1 Requirement 등록·조회입니다.

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
docker compose -f compose.test.yaml -p master-phase1-test up --build --abort-on-container-exit --exit-code-from backend-test
docker compose -f compose.test.yaml -p master-phase1-test down
```

별도 PostgreSQL tmpfs DB에서 실제 V1~V3 migration을 적용하고 app_user로 단위/통합 테스트를 실행합니다. 테스트 DB는 호스트 포트를 열지 않고 앱 DB volume과 분리됩니다. JDK/Python/PostgreSQL의 호스트 설치나 Docker socket 마운트가 필요 없습니다. 테스트 컨테이너는 유한 작업이며 종료코드가 테스트 결과입니다. 결과는 docs/phase1-evidence/test-results에 저장됩니다.

## 경계와 기준점

- app: Spring 업무 계정 app_user. migration_owner는 migration 전용.
- rag: AI의 rag_reader만 읽기. evaluation은 별도 evaluation_reader.
- Phase 0 원본은 docs/phase0-baseline/source.zip과 sha256.json에 보존했습니다(.env 제외).
- V1/V2와 기존 Compose/DB bootstrap/AI Service는 그대로 유지합니다. V3는 Requirement 입력 제약만 추가합니다.
- 기존 DB volume은 삭제하지 않습니다. 새 volume은 bootstrap 후 V1~V3, 기존 Phase 0 volume은 V3를 적용합니다.

RAG/Embedding/LangGraph 분석/테스트케이스 생성/Evaluation/Dummy 실행/GraphRAG/MCP는 미구현입니다.

[API 계약](docs/api.md) · [Phase 1 결과](docs/phase1-result.md) · [Phase 0 결과](docs/phase0-recheck.md)
