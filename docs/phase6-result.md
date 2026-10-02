# Phase 6 완료 결과

Ground Truth 기반 Evaluation 저장/API/React 및 deterministic KPI 측정을 완료했다. Phase 7 Dummy API 실행은 진행하지 않았다.

## 실제 측정값

| Split / 사례 | Recall@5 | Required Scenario Coverage | Code Validity | TC 수 |
|---|---:|---:|---:|---:|
| development / access-development | 75% (3/4) | 40% (2/5) | 100% (5/5) | 5 |
| validation / inspection-validation | 100% (3/3) | 0% (0/3) | N/A (0/0) | 0 |
| final / concurrency-final | 80% (4/5) | 0% (0/2) | N/A (0/0) | 0 |

위 표는 GENERATED(AI 원본) 모드다. 별도의 Chrome REVIEWED 실행도 저장했으며 표에 혼합하지 않았다. 합성 사례 3개, split당 1개인 PoC 측정으로 일반화 성능이나 통계적 신뢰도를 주장하지 않는다.

## 평가 데이터셋

고정 버전: `phase6-v1`, SHA-256: `76fbdc9ee68f64c8c88c963920560bfdbafc2aae7b94e70fad72453fd5bd6577`. 신규 validation/final 생성과 점수 계산 전에 고정했으며 최종 검증에서도 같은 hash였다.

| Split | 공개 입력/출처 | 필수/선택 시나리오 | 기대 문서 |
|---|---|---:|---:|
| development | [Phase 3 검증] 부서장 대여 승인 | 5/1 | 4 |
| validation | [Phase 6 validation] 반납 검사 결과와 필수 증빙 | 3/0 | 3 |
| final | [Phase 6 final] 한 장비에 대한 경합 승인 | 2/0 | 5 |

`evaluation-service/datasets/ground-truth-v1.json`에 요청된 6개 GT 필드와 scenarioId/category/description/requiredConditions를 모두 정의했다. 출처는 기존 synthetic knowledge v1.0.0의 업무규칙/API/테스트 가이드/오류코드다. 개발 사례는 기존 Phase 3~5 튜닝 사례이며 validation과 final은 새로운 입력·시나리오군이다. 같은 도메인 문서를 공유하지만 공개 요구사항과 정답을 생성 요청에 함께 보내지 않았다.

development 생성값은 재사용했다. validation/final의 공개 요구사항에 대해서만 기존 분석 API를 각각 1회 호출했다. 두 TC 생성 요청의 llmCalls는 각각 0이며 기존 정책에 따라 보류 결과가 저장되었다. 분석 모델 내부의 실제 호출/재시도 횟수는 별도 계측하지 않았으므로 이를 0회로 주장하지 않는다. Evaluation 자체와 snapshot 재현의 LLM 호출은 0회다.

## KPI 공식

- Recall@5 = Top-5 chunk에서 중복 제거한 검색 documentId와 정답 문서의 교집합 수 / 정답 문서 수.
- Required Coverage = category와 requiredConditions 전체를 한 유효 TC가 충족한 필수 시나리오 수 / 전체 필수 시나리오 수. 중복 TC 가산 없음, optional 별도.
- Code Validity = 8개 checklist가 전부 PASS인 TC 수 / 평가 TC 전체 수. UNKNOWN은 분모에 남기고 PASS로 처리하지 않음. TC가 없으면 N/A.
- 자유 서술 semantic consistency는 NOT_ASSESSED로 별도 표시하며 deterministic 점수에 혼합하지 않음.

## 실패 및 누락 사례

### development / access-development

- `ACCESS-SELF`: 자기 승인 거부 코드와 상태 불변
- `ACCESS-EMPLOYEE`: 일반 직원 승인 거부와 상태 불변
- `ACCESS-DEPARTMENT`: 타 부서 부서장 승인 거부와 상태 불변
- 검색 실패 문서: `error-codes` (`740cae54-6478-57e7-a4d5-4ccc8fa6655a`).

### validation / inspection-validation

- `INSPECTION-PASSED`: 정상 검사 시 AVAILABLE
- `INSPECTION-DAMAGED`: 파손 검사 시 MAINTENANCE
- `INSPECTION-PHOTO-MISSING`: 파손 사진 누락 거부
- 검색 실패 문서는 없음.
- 실제 생성 보류 이유: 반납 검사에서 정상 장비는 PASSED와 AVAILABLE로, 파손 장비는 DAMAGED와 MAINTENANCE로 처리한다. / 정상 장비가 PASSED와 AVAILABLE로, 파손 장비가 DAMAGED와 MAINTENANCE로 처리되는 기준은 무엇인가요?

### final / concurrency-final

- `CONCURRENCY-SINGLE-WINNER`: 동시 승인 두 건 중 정확히 한 건 승인 및 자산 RESERVED
- `CONCURRENCY-LOSER`: 동시 승인에서 패자 요청의 재고 충돌 코드
- 검색 실패 문서: `error-codes` (`740cae54-6478-57e7-a4d5-4ccc8fa6655a`).
- 실제 생성 보류 이유: 확정 조건을 지원하는 근거 검증 테스트 템플릿이 없습니다. 테스트 절차와 판정 기준을 확인해 주세요.

development의 권한 거부 TC들은 HTTP 403 등을 확인하지만 해당 TC에서 신청/자산 상태 불변 assertion이 빠져 있어 관련 시나리오 3개는 coverage에 반영하지 않았다. 별도 BUSINESS_RULE TC 하나로 다른 category/actor의 누락을 자동 보완하지 않았다. 이 누락을 없애기 위해 GT 또는 매칭 규칙을 완화하지 않았다.

현재 생성 원본 5개의 Code Validity는 100%이지만 자유 서술 의미 검증 5개는 미평가다. 금지 자기 승인, 잘못된 상태값, 근거 위조, 정의되지 않은 assertion은 자동 테스트에서 각각 FAIL/UNKNOWN으로 처리됨을 확인했다. 테스트에 주입한 실패 사례는 실제 생성 KPI에 섞지 않았다.

## 테스트 및 실제 화면

- 기존 Backend 55/55 통과 (Phase 1/3/4/5 포함), 실패/오류/스킵 0.
- 기존 Python 61/61 통과 (RAG/Analysis/Generation fixture 회귀).
- 신규 Evaluation 40/40 통과: metric 22, API 10, 실제 PostgreSQL integration 8. 실패/오류/스킵 0.
- 자동 테스트 총 156개 통과. React TypeScript/Vite build 성공.
- Chrome에서 세 split KPI, 누락 목록, N/A, 평가 POST 201, 저장 GET/이력, REVIEWED 모드 분리, 새로고침, 미등록 요구사항 409, 모바일 레이아웃 확인. 브라우저 오류 0.
- 저장된 평가 5건을 immutable snapshot만으로 재계산하여 metrics와 input hash가 모두 일치함을 확인.
- Phase 0 health 3개 UP / PostgreSQL / pgvector / Flyway V1~V9 정상.
- Phase 2 9 documents / 27 chunks 유지. 기존 8질의 Top-5 및 score 동일.
- Phase 5 기준점 152개 파일 중 148개 byte hash 동일. 기존 변경 4개는 서비스 구성·평가 화면 연결·스타일·proxy뿐이다.
- 기존 Phase 5 승인/반려 JSON은 현재 GET 응답과 완전히 동일했다. AI 원본 및 evidence 유지.
- actual app_user/rag_reader의 evaluation 접근 거부, evaluation_reader의 app/rag 접근과 GT UPDATE 거부 확인. 생성/Review 컨테이너에 평가 자격증명·GT mount 없음.

화면 증거: `phase6-evidence/react-development.png`, `react-validation.png`, `react-final.png`, `react-mobile.png`, `react-unbound-error.png`.

## DB 및 API

V9: evaluation.ground_truth, requirement_binding, evidence_catalog, evaluation_run, immutable triggers, 제한적 append 함수. 이전 migration 및 app/rag 권한은 그대로 유지했다. Ground Truth seed는 evaluation 전용 초기화 스크립트에 분리했다.

- `POST /api/evaluations`
- `GET /api/evaluations/{id}`
- `GET /api/requirements/{id}/evaluations`

직접 API: `http://localhost:8090`, React proxy: `http://localhost:5173`. UI는 요구사항 조회 후 하단 Ground Truth 평가에서 실행/저장값 조회가 가능하다.

| Split | Requirement ID | 대표 Evaluation ID |
|---|---|---|
| development | `b5270f71-c92c-48ae-8530-8946f1cfce62` | `ea81b3da-06be-4ffd-9acc-2f8b7d7839fd` |
| validation | `3f209638-fddf-4c2d-bb10-919601da4df3` | `54acd5e6-8bf6-43d5-a8cd-bfa12739193c` |
| final | `744dd838-dba6-449a-bc01-fe5c3669b048` | `99bd3126-c051-482e-b210-25b0e7a74ae2` |

## 변경 파일

기존 파일:

- `frontend/src/Requirements.tsx`
- `frontend/src/style.css`
- `compose.yaml`
- `frontend/vite.config.ts`

추가 파일:

- `backend/src/main/resources/db/migration/V9__isolated_evaluation.sql`
- `compose.phase6-test.yaml`
- `docs/scripts/phase6-browser.py`
- `docs/scripts/phase6-generate-inputs.py`
- `docs/scripts/phase6-regression.py`
- `docs/scripts/phase6-run.py`
- `docs/scripts/phase6-runtime.py`
- `docs/scripts/phase6-seed.py`
- `docs/scripts/phase6-tests.py`
- `evaluation-service/Dockerfile`
- `evaluation-service/app/__init__.py`
- `evaluation-service/app/main.py`
- `evaluation-service/app/metrics.py`
- `evaluation-service/datasets/ground-truth-v1.json`
- `evaluation-service/datasets/manifest.json`
- `evaluation-service/datasets/public-requirements.json`
- `evaluation-service/requirements.txt`
- `evaluation-service/tests/fixtures/development.json`
- `evaluation-service/tests/test_api.py`
- `evaluation-service/tests/test_database.py`
- `evaluation-service/tests/test_metrics.py`
- `frontend/src/Evaluations.tsx`
- `docs/phase6-design.md`
- `docs/phase6-result.md`
- `docs/phase5-baseline/source.zip`
- `docs/phase5-baseline/sha256.json`

증거 전체는 `docs/phase6-evidence/`에 저장했다. 상세 계약/공식/재실행 방법은 `phase6-design.md`에 있다.

## 미해결 사항 및 제한

- Phase 6 완료 조건을 막는 미해결 사항 없음.
- 평가셋은 합성 3건뿐이며 통계적 성능 추정에 충분하지 않다. GT가 이후 사람이 독립적으로 검수해야 할 annotation이라는 점은 유지된다.
- 다른 표현의 의미적 동일성 및 자유 서술 모순은 자동 판정하지 않는다. 고정 구조 계약 밖의 경우 UNKNOWN 또는 미매칭으로 남는다.
- validation/final TC 0건은 기존 분석/생성 범위의 관측된 한계다. 이를 해결하려고 Phase 0~5 로직이나 GT를 변경하지 않았다.
- runtime 평가 역할은 GT 수정 불가이며 새 dataset version 등록은 관리자 초기화가 필요하다. UI에서 GT 편집이나 평가 결과 수정은 제공하지 않는다.
- Phase 7 Dummy API 실행, Hybrid Search, Reranking, Query Rewrite, GraphRAG, MCP, 모델 fine-tuning은 구현하지 않았다.
