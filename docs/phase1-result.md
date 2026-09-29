# Phase 1 — Requirement 등록·조회 완료

검증일: 2026-09-29. 프로젝트: D:\MASTER과정. 결과: PASS.

## 완료 기능

- Requirement record 및 app.requirement의 추가 제약 migration V3.
- JdbcClient Repository / 트랜잭션 Service / Controller.
- POST /api/requirements: HTTP 201 및 Location, 서버 UUID·DRAFT·DB 생성시각.
- GET /api/requirements/{id}: 저장된 객체 HTTP 200.
- 공백/누락/길이 검증, JSON·UUID 오류 400, 미존재 ID 404, 내부 오류의 안전한 500 응답.
- React 입력·저장 결과, ID 조회, 처리 중 상태·실패 안내, 화면 새로고침 후 저장 데이터 조회.

## 기준점과 경계

[Phase 0 소스 ZIP](phase0-baseline/source.zip) 및 [SHA-256](phase0-baseline/sha256.json)을 변경 전에 보관했다. .env는 포함하지 않았다. Git 저장소가 없는 상태이므로 Git tag 대신 파일 기준점이다.

기존 compose.yaml, DB role bootstrap, backend application.yml, V1/V2, AI Service 파일은 원본 해시와 일치한다. app/rag/evaluation 소유자 및 권한은 유지했다. V3는 app.requirement 제약만 추가한다.

## 실제 검증

| 검증 | 결과 |
|---|---|
| Backend 단위 테스트 | 3/3 통과 |
| Backend 실제 PostgreSQL 통합 테스트 | 14/14 통과 |
| 테스트 총계 | 17 passed, failures=0, errors=0, skipped=0 |
| 테스트 DB | 별도 tmpfs PostgreSQL, 실제 bootstrap 및 V1~V3, runtime app_user |
| Compose 빌드·기동 | 성공; frontend TypeScript/Vite 빌드 포함 |
| 기존 앱 DB migration | V1/V2/V3 모두 success=true |
| 실제 API | POST 201, GET 200, 입력 오류 400, 잘못된 UUID 400, 미존재 UUID 404 |
| React Chrome | 등록 및 새로고침 후 GET 조회, 공백/UUID/404 오류 표시 통과 |
| 모바일 | 390px에서 가로 overflow 없음 |
| JavaScript page errors | 0 |
| Phase 0 회귀 | 두 서비스 health 정상, 권한 검사 36건 + 실제 허용 조회 3건 + Flyway 이력 보호 통과 |

[테스트 원본](phase1-evidence/test-run.log) · [Surefire 결과](phase1-evidence/test-results) · [API/브라우저 결과](phase1-evidence/browser-api-result.json) · [데스크톱](phase1-evidence/requirement-desktop.png) · [모바일](phase1-evidence/requirement-mobile.png)

테스트 전용 컨테이너/네트워크는 정리했고 애플리케이션 컨테이너는 실행 상태다. 실제 등록 검증에 사용한 합성 샘플 2건은 로컬 앱 DB에 남겼다:

- API 샘플: 9fe79a4c-54ce-4810-8a99-2d5c9b3f1203
- 화면 샘플: 6f1fd8bb-b9c2-4be9-a095-879a30447376

## 변경 파일

- backend/pom.xml: Validation 및 Spring Boot 테스트 의존성.
- backend/src/main/java/com/example/legacyassistant/requirement/Requirement.java
- backend/src/main/java/com/example/legacyassistant/requirement/CreateRequirementRequest.java
- backend/src/main/java/com/example/legacyassistant/requirement/RequirementRepository.java
- backend/src/main/java/com/example/legacyassistant/requirement/RequirementService.java
- backend/src/main/java/com/example/legacyassistant/requirement/RequirementController.java
- backend/src/main/java/com/example/legacyassistant/requirement/RequirementNotFoundException.java
- backend/src/main/java/com/example/legacyassistant/requirement/ApiExceptionHandler.java
- backend/src/main/resources/db/migration/V3__validate_requirement_content.sql
- backend/src/test/java/com/example/legacyassistant/requirement/RequirementServiceTest.java
- backend/src/test/java/com/example/legacyassistant/requirement/RequirementIntegrationTest.java
- frontend/src/Requirements.tsx, frontend/src/App.tsx, frontend/src/style.css
- frontend/vite.config.ts: /api backend 프록시 추가.
- frontend/Dockerfile: 이미지 빌드 시 TypeScript/Vite 검증.
- compose.test.yaml: 독립 테스트 DB/실행기.
- README.md, docs/api.md, docs/data-model.md: 현재 범위 및 재현 명령.
- docs/phase0-baseline/* 및 docs/phase1-evidence/*, 본 보고서: 기준점·검증 증거.

[기존 파일 변경 diff](phase1-evidence/existing-files.diff) · [파일 목록](phase1-evidence/changed-files.json)

## 시간 기록

명령 시간은 PowerShell Stopwatch, 도구 반환은 exec_command/write_stdin 호출 전후로 측정했다. 비동기 테스트의 초기 도구 반환은 테스트 완료시간이 아니다. 테스트 전체 명령은 30.846초였으며 빌드·독립 DB 초기화·테스트·정지를 포함한다. 테스트 로그의 Maven test 자체는 5.479초다.

| 구간 | 명령 실행 초 | 도구 반환 초 |
|---|---:|---:|
| apply | 0.318 | 5.774 |
| backend-tests | 비동기 실행 중 | 13.524 |
| backend-tests-poll | 30.846 | 0.001 |
| compose-build | 7.952 | 11.180 |
| api-browser | 3.439 | 7.224 |
| migration | 0.190 | 2.855 |
| phase0-boundaries | 0.224 | 3.810 |
| docs-baseline-audit | 0.186 | 4.434 |
| test-cleanup | 0.428 | 3.915 |

짧은 명령의 20초 이상 지연은 없었다. [전체 시간·출력](phase1-evidence/timings.json).

## 미해결 사항

요청한 Phase 1 범위에서 확인된 미해결 오류는 없다. RAG, Embedding, LangGraph 분석, 테스트케이스 생성, Evaluation, Dummy API 실행, GraphRAG/MCP는 구현하지 않았다. 다음 단계 작업으로 진행하지 않는다.

