# 데이터 모델

| Schema.Table | 필드 | 설명 |
|---|---|---|
| `app.requirement` | `id`, `title`, `description`, `status`, `created_at` | 변경 요구사항과 업무 상태 |
| `app.analysis_result` | `id`, `requirement_id`, `result_json`, `created_at` | 구조화된 분석 결과와 evidence |
| `app.test_case` | `id`, `requirement_id`, `category`, `test_case_json`, `approval_status`, `executable` | 테스트 초안과 향후 승인/실행 가능 상태 |
| `app.review` | `id`, `requirement_id`, `reviewer`, `decision`, `comment`, `reviewed_at` | 다음 단계에서 추가할 검토 이력 |
| `rag.knowledge_document` | `id`, `document_type`, `title`, `source_name`, `version` | 합성 업무 규칙/API 명세 문서 |
| `rag.knowledge_chunk` | `id`, `document_id`, `section`, `content`, `metadata`, `embedding` | 검색 단위와 pgvector 임베딩 |
| `evaluation.ground_truth` | `id`, `name`, `version`, `expected_json` | 격리된 Ground Truth 정답 데이터 |
| `evaluation.evaluation_run` | `id`, `ground_truth_id`, `requirement_id`, `metrics`, `created_at` | 기준 데이터 기반 평가 결과 |
| `app.dummy_execution` | `id`, `test_case_id`, `status`, `actual_result`, `executed_at` | 이후 승인된 테스트만 실행한 결과 |

초기 migration은 health/연결 검증과 다음 단계의 기반을 위해 Requirement 및 RAG 문서 테이블만 생성합니다. 나머지 업무 기능 테이블과 Evaluation/Dummy 데이터는 해당 기능 단계에서 migration으로 추가합니다. Embedding은 모델 선택을 미루기 위해 vector dimension을 schema에서 고정하지 않습니다.

## 역할

- `migration_owner`: migration 전용 DDL 계정.
- `app_user`: `app` 업무 데이터 DML 계정.
- `rag_reader`: `rag` 읽기 전용 계정. AI Service가 받는 유일한 DB 계정.
- `evaluation_reader`: 향후 Evaluation Service 전용 읽기 계정. AI Service에는 전달하지 않음.

Ground Truth는 `evaluation` schema에만 저장하고 `rag` 문서/chunk 테이블에 넣지 않습니다. Evaluation용 Repository/Service와 일반 생성 workflow의 Repository/Service를 코드 및 credential 수준에서 분리합니다.
