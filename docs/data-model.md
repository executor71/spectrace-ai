# 데이터 모델

| Schema.Table | 필드 | 설명 |
|---|---|---|
| `app.requirement` | `id`, `title`, `description`, `status`, `created_at` | 변경 요구사항과 업무 상태 |
| `app.requirement_analysis` | `requirement_id`, `result_json`, `created_at` | 구조화된 분석 결과와 evidence |
| `app.test_case` | `id`, `requirement_id`, `category`, `test_case_json`, `approval_status`, `executable` | 테스트 초안과 향후 승인/실행 가능 상태 |
| `app.review` | `id`, `requirement_id`, `reviewer`, `decision`, `comment`, `reviewed_at` | 다음 단계에서 추가할 검토 이력 |
| `rag.knowledge_document` | `id`, `document_type`, `title`, `source_name`, `version` | 합성 업무 규칙/API 명세 문서 |
| `rag.knowledge_chunk` | `id`, `document_id`, `section`, `content`, `metadata`, `embedding` | 검색 단위와 pgvector 임베딩 |
| `evaluation.ground_truth` | `id`, `name`, `version`, `expected_json` | 격리된 Ground Truth 정답 데이터 |
| `evaluation.evaluation_run` | `id`, `ground_truth_id`, `requirement_id`, `metrics`, `created_at` | 기준 데이터 기반 평가 결과 |
| `app.dummy_execution` | `id`, `test_case_id`, `status`, `actual_result`, `executed_at` | 이후 승인된 테스트만 실행한 결과 |

V1~V6 적용 후 Requirement, requirement_analysis, RAG 문서/chunk/embedding_profile 테이블이 생성됩니다. 표의 test_case/review/ground_truth/evaluation_run/dummy_execution은 미래 설계이며 아직 생성하지 않았습니다. Embedding은 모델 선택을 미루기 위해 vector dimension을 schema에서 고정하지 않습니다.

## 역할

- `migration_owner`: migration 전용 DDL 계정.
- `app_user`: `app` 업무 데이터 DML 계정.
- `rag_reader`: `rag` 읽기 전용 계정. AI Service가 받는 유일한 DB 계정.
- `evaluation_reader`: 향후 Evaluation Service 전용 읽기 계정. AI Service에는 전달하지 않음.

Ground Truth는 `evaluation` schema에만 저장하고 `rag` 문서/chunk 테이블에 넣지 않습니다. Evaluation용 Repository/Service와 일반 생성 workflow의 Repository/Service를 코드 및 credential 수준에서 분리합니다.

## Phase 1 적용

V1/V2는 변경하지 않았다. V3는 기존 app.requirement에 제목 공백 방지와 내용 공백/10,000자 길이 제약을 추가한다. 기존 UUID PK, VARCHAR(200), DRAFT 기본값, 생성시각 및 상태 제약을 유지한다. 소유자/권한 및 rag/evaluation은 변경하지 않는다.

Spring의 Requirement record는 id/title/description/status/createdAt을 반환한다. JdbcClient 기반 Repository는 app.requirement에만 접근하며 Service에서 등록/조회 트랜잭션을 관리한다.

## Phase 2 적용

V4는 rag.knowledge_document에 source_key/domain과 TEST_GUIDE/ERROR_CODE/POLICY 타입을 추가합니다. rag.embedding_profile은 provider/model/revision/dimensions/dataset_version을 기록합니다. chunk는 profile FK, 실제 vector 차원 일치 및 필수 metadata 제약을 갖습니다. vector 타입 자체는 특정 dimension으로 하드코딩하지 않습니다. V5는 설정으로 생성한 실제 모델의 고정 초기 데이터를 담습니다. 다른 모델로 교체할 때는 새 migration과 전체 재임베딩이 필요합니다.

## Phase 3 적용

V6는 app.requirement_analysis만 추가한다. requirement_id가 PK/FK이며 result_json에 8개 필드와 당시 evidence를 저장한다. 재분석 성공은 최신 결과를 교체하고 실패는 기존 결과를 보존한다. 생성 시각도 성공 시 갱신한다.
기존 migration_owner의 app default privileges를 따르며 새로운 GRANT나 role 변경은 없다. app_user는 읽기/쓰기를 수행하고 rag_reader/evaluation_reader는 접근할 수 없다.
