> 이 문서는 모델 확정 전의 준비 기록입니다. 최종 완료 결과는 [Phase 2 결과](phase2-result.md)를 참고하세요.

# Phase 2 준비 상태 — 승인 Embedding 모델 정보 대기

2026-09-29. 프로젝트 D:\MASTER과정.

**Phase 2는 아직 완료되지 않았다.** 기존 문서에는 Embedding 모델 선택이 보류되어 있다. 승인 모델의 정확한 ID와 실행 방식(로컬 또는 API), 필요 시 endpoint와 키 환경변수 이름이 필요하다. 임의 모델을 승인된 것으로 간주하거나 테스트 벡터를 실제 검색 데이터로 적재하지 않았다.

## Phase 1 기준점

- docs/phase1-baseline/source.zip 및 sha256.json 생성, .env 제외.
- 기존 소스/설정/문서 54개 해시가 모두 동일함을 재확인했다.
- 기존 Compose, AI health, Requirement API/UI, migration V1~V3 및 DB role은 변경하지 않았다.

## 준비한 데이터와 코드

| 유형 | 문서 수 | 섹션/chunk 수 |
|---|---:|---:|
| BUSINESS_RULE | 3 | 9 |
| API_SPEC | 3 | 9 |
| TEST_GUIDE | 1 | 3 |
| POLICY | 1 | 3 |
| ERROR_CODE | 1 | 3 |
| 합계 | 9 | 27 |

가상 IT 자산관리의 재고/대여 승인/동시성/지급/반납/파손/연체/접근 정책/오류 코드를 다룬다. 실제 회사 자료는 없다. 문서 manifest에 지정한 Markdown만 읽고 ## 섹션을 의미 단위로 chunk화한다. documentId/chunkId/documentType/domain/version/section/relatedApis metadata를 생성한다. ID는 UUIDv5로 재현 가능하다.

- knowledge/README.md, knowledge/manifest.json, knowledge/documents/*.md: 초기 합성 문서 9개.
- ai-service/app/knowledge.py: 문서·chunk 모델과 제한된 manifest loader.
- ai-service/app/embedding_contract.py: 승인 모델을 연결할 provider 인터페이스와 벡터 검증.
- ai-service/app/seed_export.py: 실제 승인 embedding을 Flyway SQL로 내보내는 함수. DB 자격 증명 없이 파일만 생성한다.
- ai-service/app/vector_search.py: rag 전용 read-only SQL, cosine similarity, 프로필 일치 검사와 입력/출력 모델. 아직 실제 provider/HTTP route와 연결하지 않았다.
- ai-service/tests/test_knowledge.py, test_vector_search.py: 준비 코드 단위 테스트.
- ai-service/tests/fixtures/retrieval_cases.json: 별도 Top-5 검증 질의 8건. 적재 manifest에 포함하지 않는다.
- docs/phase2-pending/V4__prepare_synthetic_knowledge.sql: migration 초안. Flyway 경로 밖에 있으며 DB에 적용하지 않았다.

[준비 파일 목록](phase2-evidence/prepared-files.json)

## 실제 테스트 결과

- 신규 단위 테스트 6개 통과: chunk/metadata/ID, 빈 섹션·중복·크기 제한, 벡터 형식, 검색 요청 Validation, SQL의 rag 범위, embedding 프로필 불일치 차단.
- SQL 배선 단위 테스트의 2차원 벡터는 명시적인 mock이며 의미 검색 품질을 증명하지 않는다. DB에 적재하지 않았다.
- Phase 1 Backend 테스트 17개 통과: 단위 3 + PostgreSQL 통합 14. 별도 tmpfs DB에서 실제 V1~V3와 app_user 사용.
- 두 health endpoint HTTP 200/UP, 기존 Requirement GET 성공, Chrome React 조회 및 두 정상 상태 표시 성공.
- DB 권한 36개 검사와 허용 조회 3건, Flyway 이력 보호 통과. evaluation 검증용 임시 테이블은 ROLLBACK으로 제거.
- 테스트 컨테이너는 정리했고 기존 앱 컨테이너는 그대로 실행 중이다.

[회귀 결과](phase2-evidence/regression.json) · [Backend 로그](phase2-evidence/phase1-regression.log) · [화면](phase2-evidence/phase1-regression.png)

## 검색 예시의 현재 상태

다음은 작성한 테스트 질의이며 실제 검색 결과는 아니다:

- “부서장이 자기 장비 대여 신청을 직접 승인해도 되나요?” → 예상 관련 문서: loan-rules/error-codes.
- “반납한 노트북이 파손된 경우 어떤 상태로 전환해야 하나요?” → return-rules/return-api.
- “대여 내역 CSV를 직원이 내려받을 수 있나요?” → access-policy.

실제 embedding 생성·pgvector 저장·HTTP 검색·Top-K 품질 검증은 승인 모델 확정 후 수행해야 한다. 검색 성공률이나 점수를 아직 보고할 수 없다.

## 시간

명령 시간은 PowerShell Stopwatch, 도구 반환은 호출 전후 측정이다. 비동기 명령의 초기 반환은 완료시간이 아니다.

| 작업 | 명령 실행 초 | 도구 반환 초 |
|---|---:|---:|
| inspect | 0.073 | 0.357 |
| baseline | 0.274 | 3.388 |
| prepare-corpus | 0.139 | 0.430 |
| corpus-unit-tests | 3.513 | 8.240 |
| save-preparation | 0.146 | 3.900 |
| preparation-unit-tests | 1.238 | 4.716 |
| phase1-regression | 진행 중 반환 | 13.215 |
| phase1-regression-poll | 12.638 | 0.010 |
| baseline-health-ui-regression | 2.015 | 5.502 |
| schema-boundary-regression | 0.205 | 3.170 |
| cleanup-test-containers | 0.427 | 3.384 |

[시간·출력 원본](phase2-evidence/timings.json). 20초 이상 지연된 짧은 명령 없음.

## 다음 실행에 필요한 정보

정확한 승인 Embedding 모델 ID, 로컬/API 실행 방식, API인 경우 endpoint와 키 환경변수 이름. 키 값은 채팅에 전달하지 않는다. 해당 정보 없이 provider 또는 vector dimension을 임의로 결정하지 않는다. Phase 3 및 이번 요청에서 제외된 검색/분석 기능은 구현하지 않았다.

