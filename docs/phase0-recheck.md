# Phase 0 재검증 — 2026-09-29

프로젝트: D:\MASTER과정

결과: PASS. 기능 개발 없이 현재 Compose 뼈대의 실행 상태를 검증했다. 이번 재검증에서는 애플리케이션 코드나 Compose 설정을 수정하지 않았다.

## 실제 검증 결과

- compose.yaml, .env.example, frontend, backend, ai-service, docs가 존재한다.
- 기존 .env는 보존했고 예제의 필수 키가 모두 채워져 있으며 .gitignore에서 제외됨을 확인했다. secret 출력이나 commit은 하지 않았다.
- docker compose config --quiet 및 docker compose up --build -d가 exit 0으로 완료됐다. -d는 서버를 foreground로 기다리지 않기 위한 옵션이다.
- PostgreSQL 16.15: accepting connections. pgvector 0.8.6은 public에 활성화됐다. 실제 vector 거리 연산 결과는 1이다.
- Flyway V1/V2 모두 success=true. 기존 DB volume의 성공 이력을 재조회했다. 이번 실행에서 migration을 신규 적용한 것은 아니다.
- app/rag/evaluation 소유자는 migration_owner. 런타임 역할은 해당 schema만 USAGE, CREATE는 거부된다. app_user는 업무 DML, rag_reader와 evaluation_reader는 SELECT만 허용된다.
- 권한 검사 36건, 실제 허용 조회 3건, Flyway 이력 쓰기 차단 검사 통과. 교차 schema 조회는 실제 role 전환 후 거부를 확인했다. evaluation 검증 테이블은 트랜잭션 전체 ROLLBACK 후 제거 확인했다.
- http://localhost:8080/actuator/health: HTTP 200, status=UP, components.db.status=UP.
- http://localhost:8000/health: HTTP 200, status=UP, database=UP, schema=rag, pgvector=0.8.6.
- 실제 Chrome에서 http://localhost:5173 접속: Spring Boot 및 AI Service 모두 정상. 프록시 health 호출 모두 HTTP 200, JS page error 0건.
- 최종 컨테이너 4개 모두 Up, PostgreSQL healthy.

## 컨테이너 런타임

| 서비스 | 이미지 구성 |
|---|---|
| DB | pgvector/pgvector:pg16 |
| Spring build | maven:3.9-eclipse-temurin-21: JDK/Maven으로 컨테이너 안에서 빌드 |
| Spring runtime | eclipse-temurin:21-jre: 실제 Java 21.0.12.1 |
| AI | python:3.12-slim: 실제 Python 3.12.14 |
| React | node:22-alpine: 컨테이너에서 npm ci 및 Vite 실행 |

호스트의 PostgreSQL, JDK, Spring Boot, Python 설치를 애플리케이션 기동 조건으로 사용하지 않았다. 호스트 Python은 이번 Chrome 자동 검증 도구로만 사용했고 AI 서비스는 컨테이너 안에서 실행된다.

이번 빌드는 기존 Docker 캐시와 DB volume을 보존해 실행했다. 따라서 빈 캐시·빈 volume의 새 환경 검증과 구분한다. 전체 서비스 실행 명령은 프로젝트 루트에서 docker compose up --build이며 별도 로컬 서비스 기동은 필요 없다.

## 단계별 시간

명령 실행시간: 현재 PowerShell의 Stopwatch로 명령/검사 구간 측정. 도구 반환시간: tools.exec_command 호출 직전부터 결과 수신 직후까지 Date.now로 측정. 도구 반환시간에는 실행시간과 도구/권한 처리 대기가 포함되며 모델의 다음 응답 작성 시간은 제외한다.

| 단계 | 명령 실제 실행(초) | 도구 반환(초) |
|---|---:|---:|
| 1. 기존 파일 | 0.073 | 0.354 |
| 1. 기존 설정 검토 | 0.100 | 0.325 |
| 2. .env 준비·확인 | 0.081 | 0.320 |
| 3. Compose config | 0.309 | 0.588 |
| 4. Compose up --build -d | 3.126 | 9.331 |
| 5. PostgreSQL | 0.168 | 4.502 |
| 6. pgvector | 0.184 | 6.888 |
| 7. Flyway | 0.170 | 4.211 |
| 8. schema·권한 | 0.207 | 4.951 |
| 9. Spring health | 0.111 | 0.358 |
| 10. AI health | 0.109 | 0.345 |
| 11. React 화면 | 1.720 | 6.871 |
| 추가: Dockerfile 확인 | 0.026 | 0.297 |
| 추가: 컨테이너 Java | 0.190 | 3.026 |
| 추가: 컨테이너 Python | 0.155 | 2.914 |
| 최종 컨테이너 상태 | 0.138 | 3.256 |

20초 이상 대기한 검사 명령 없음. 약 120초 지연도 관측되지 않았다.

## 증거

- [전체 단계 출력과 시간](phase0-recheck-evidence/timings.json)
- [브라우저 결과](phase0-recheck-evidence/browser.json)
- [화면](phase0-recheck-evidence/react-health.png)

Requirement 등록, RAG 검색/생성, 테스트케이스 생성 기능은 구현하지 않았다. 검증 완료 후 작업을 종료하고 컨테이너는 실행 상태로 유지한다.

