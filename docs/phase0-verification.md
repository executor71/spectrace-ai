# Phase 0 실제 실행 검증 결과

검증일: 2026-09-29 (KST)
프로젝트: D:\MASTER과정
결과: PASS — Phase 0 완료. Requirement 등록 기능은 구현하지 않음.

## 사전 확인 및 환경

- compose.yaml, .env.example, frontend, backend, ai-service, docs 모두 존재함을 먼저 확인했다.
- 기존 .env가 없어 .env.example의 로컬 개발용 값으로 준비했다. .gitignore의 .env 제외 규칙을 확인했다.
- 이 폴더에는 .git이 없으며 Git 초기화나 commit은 수행하지 않았다. 실제 운영 secret을 추가하지 않았다.
- Docker Engine 29.8.1 / Compose v5.5.1.
- docker compose config --quiet 성공.
- docker compose up --build -d 성공. -d는 검증 중 컨테이너를 유지하기 위해 사용했다.

## 발견한 문제와 최소 수정

1. 첫 Flyway 실행이 SQLSTATE 42704, type "vector" does not exist로 실패했다. pgvector는 public에 설치됐지만 migration 검색 경로는 app이었다. V1의 embedding 타입을 public.vector로 명시했다. V1 성공 이력이 0건이고 실패 작업이 롤백된 상태임을 확인한 후 수정했다.
2. backend/pom.xml에 HTTP 서버 의존성이 없어 spring-boot-starter-web을 추가했다.
3. app의 기본 DML 권한이 Flyway 이력에도 적용됐다. V2__protect_flyway_history.sql을 추가하여 app_user의 해당 테이블 권한을 회수했다.
4. frontend/.dockerignore를 추가하여 호스트 node_modules/dist/env 파일이 이미지의 설치 결과를 덮어쓰거나 빌드에 포함되지 않게 했다.

기존 프로젝트를 재생성하지 않았고 DB volume을 삭제하지 않았다. 수정 후 Compose 설정 검증과 전체 빌드/기동을 다시 수행했다.

## DB 검증

- pg_isready: accepting connections.
- PostgreSQL 16.15, pgvector 0.8.6, extension schema public.
- 실제 vector 거리 연산: [1,2,3] <-> [1,2,4] = 1.
- Flyway: Successfully applied 2 migrations, schema version v2.
- app.flyway_schema_history에서 V1/V2 모두 success=true.
- app/rag/evaluation 소유자: migration_owner.
- migration_owner/app_user/rag_reader/evaluation_reader 모두 superuser/createdb/createrole/bypassrls=false.

| Role | app | rag | evaluation |
|---|---|---|---|
| app_user | 업무 SELECT/INSERT/UPDATE/DELETE | 접근 거부 | 접근 거부 |
| rag_reader | 접근 거부 | SELECT만 허용 | 접근 거부 |
| evaluation_reader | 접근 거부 | 접근 거부 | SELECT만 허용 |

런타임 3개 role 모두 담당 schema의 CREATE 권한이 없다. 실제 SET LOCAL ROLE로 허용 및 거부 동작 23건을 검사하여 모두 통과했다. app_user의 Flyway 이력 수정도 거부된다.

evaluation은 현재 빈 schema이므로 migration_owner로 검증용 테이블을 트랜잭션 내 생성하여 기본 SELECT 권한과 쓰기/교차 접근 차단을 검사했다. 검사 전체를 ROLLBACK했으며 검증 테이블이 사라지고 app.requirement가 0건임을 확인했다. 평가 업무 테이블은 추가하지 않았다.

AI 컨테이너에서 실제 비밀번호 연결 후 current_user=rag_reader, RAG 조회 성공, app 조회 권한 거부를 확인했다. AI 환경의 DB 관련 변수는 RAG_DB_HOST/NAME/USER/PASSWORD뿐이며 Evaluation 및 migration/업무 계정 정보는 없다.

## HTTP 및 React 검증

| URL | 실제 응답 |
|---|---|
| http://localhost:8080/actuator/health | HTTP 200, status=UP, components.db.status=UP |
| http://localhost:8000/health | HTTP 200, status=UP, database=UP, schema=rag, pgvector=0.8.6 |
| http://localhost:5173/actuator/health | HTTP 200, status=UP |
| http://localhost:5173/ai-health/health | HTTP 200, status=UP |

실제 Chrome 153.0.8010.53을 Playwright로 실행했다. React가 두 health endpoint를 실제 호출하고 두 서비스 모두 '정상'으로 표시함을 DOM assertion과 스크린샷으로 확인했다. JavaScript page error는 0건이다. PostgreSQL 행은 원래 설계대로 'AI health로 확인' 문구를 표시한다.

frontend 컨테이너의 npm run build (TypeScript + Vite)도 성공했다.

- [HTTP 원본 결과](phase0-evidence/http-results.json)
- [브라우저 원본 결과](phase0-evidence/browser-result.json)
- [React 스크린샷](phase0-evidence/react-health.png)
- [최종 컨테이너 상태](phase0-evidence/compose-ps.txt)
- [Backend 로그](phase0-evidence/backend.log)
- [DB 상태 및 권한](phase0-evidence/database.txt)

Phase 0 검증을 완료하고 멈춘다. 컨테이너는 로컬 확인을 위해 실행 상태로 둔다. Requirement API/UI 및 이후 단계 기능은 구현하지 않았다.