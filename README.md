# Legacy Change Assistant PoC

레거시 업무시스템 변경 요구사항을 대상으로 RAG 근거 검색, 분석, 테스트 케이스 초안을 제공하기 위한 PoC입니다. 이 단계는 실행 가능한 서비스 뼈대와 DB 경계만 포함하며, Requirement 등록을 포함한 제품 기능은 다음 단계에서 구현합니다.

## 실행

Docker Desktop을 실행한 뒤 저장소 루트에서 다음 명령을 실행합니다.

```powershell
Copy-Item .env.example .env
docker compose up --build
```

`.env`의 값은 로컬 개발 전용입니다. 운영 환경에서는 반드시 별도 비밀 값과 관리 방식을 사용해야 합니다. 첫 DB 초기화 시 PostgreSQL volume이 새로 만들어지고 Flyway가 스키마와 초기 테이블을 생성합니다.

- React: http://localhost:5173
- Spring Boot health: http://localhost:8080/actuator/health
- Python AI Service health: http://localhost:8000/health

Compose 로그에서 `Successfully applied 2 migrations`을 확인하고, health 응답에서 Spring의 `db` 상태 및 AI Service의 PostgreSQL 연결 상태가 정상인지 확인합니다.

초기화 SQL은 빈 PostgreSQL volume에서만 실행됩니다. 기존 volume이 있는 경우 기존 데이터를 제거하지 말고 별도 검토 후 마이그레이션하십시오. 이 PoC는 샘플 데이터만 사용하며 실제 회사 데이터를 넣지 않습니다.

## 현재 범위

현재 구현: 서비스 health, PostgreSQL 연결, schema/role 초기화, Flyway 초기 migration.

다음 단계: Requirement 등록부터 시작합니다. 이후 RAG 검색, 요구사항 분석, 테스트 케이스 생성, Review, Ground Truth Evaluation, Dummy Execution 순으로 확장합니다. Review, Evaluation, Dummy Execution은 아직 구현하지 않습니다.

## 데이터 접근 경계

- `app`: Spring Boot가 소유하는 업무 데이터. `app_user`는 이 schema의 업무 테이블만 읽고 씁니다.
- `rag`: 지식 문서, chunk, embedding. Spring Boot의 migration role이 schema를 준비하고 `rag_reader`는 읽기 전용입니다. AI Service는 이 계정만 사용합니다.
- `evaluation`: 향후 Ground Truth와 평가 데이터를 위한 별도 schema. `evaluation_reader` 전용이며 AI Service 환경에는 해당 자격 증명을 전달하지 않습니다.

일반 LangGraph workflow에는 Evaluation repository/service 또는 evaluation 자격 증명을 연결하지 않습니다. 사용자 승인, 업무 상태 변경, Dummy API 실행 권한 검증은 향후에도 Spring Boot가 최종 책임을 가집니다.
