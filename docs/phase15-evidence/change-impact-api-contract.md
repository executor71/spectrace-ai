# API 계약

기존 `/api` REST 및 ApiError `{code,message,fieldErrors}` 방식을 따른다.

| Method | Path | 의미 |
|---|---|---|
| GET | `/api/change-impacts/baselines/{requirementId}` | 저장 분석이 있는 요구사항의 현재 snapshot / revision 토큰 |
| POST | `/api/change-impacts` | `{baselineRequirementId,baselineRevision,proposalTitle,proposalContent}` 동결 저장 |
| GET | `/api/change-impacts` | 최근 변경안 목록 (최대 100) |
| GET | `/api/change-impacts/{impactId}` | 동결 Baseline과 별도 변경안 |
| POST | `/api/change-impacts/{impactId}/analysis-jobs` | 202, 기존 Queue에 CHANGE_IMPACT_ANALYSIS 접수; active 중복은 같은 Job |
| GET | `/api/change-impacts/{impactId}/analysis-jobs` | 최대 20개 Job; 진행 작업 우선 |
| GET | `/api/analysis-jobs/{jobId}` | 기존 계약 + jobType/impactId; 시간/상태/오류/결과 URL |
| GET | `/api/change-impacts/{impactId}/results` | 최신 성공 결과 + analysisId + 현재 baselineStale |
| GET/POST | `/api/change-impacts/{impactId}/reviews` | 검토본 append-only 저장/이력 |
| GET | `/api/change-impacts/{impactId}/export` | 7-sheet XLSX, 문자열 셀 |

제목 1–200자, 제목+내용 1900자 이내. baselineRevision 불일치 409, 없는 Baseline/분석/변경안/결과 404, 잘못된 입력 422. Job은 기존 Queue 제한 429, 모델 timeout TIMED_OUT/LLM_TIMEOUT, Structured Output 오류 FAILED/LLM_INVALID_OUTPUT 또는 VALIDATION_FAILED, 검색 오류 FAILED/RAG_RETRIEVAL_ERROR. 재분석 실패는 이전 정상 결과를 지우지 않는다.

검토 요청: `{analysisId,expectedRevision,reviewer,reviewerNotes,status,conditionChanges,affectedApis,affectedTestCases}`. 배열 항목은 조회 결과를 기초로 하고 조건 changeType, API reviewDecision(PENDING/INCLUDED/EXCLUDED), TC classification만 수정 가능하다. 근거/ID/원문 변조 422, 검토 revision 또는 최신 analysisId 불일치 409, Baseline 변경 409. reviewStatus는 DRAFT/IN_REVIEW/REVIEWED이며 정책 승인과 무관하다.

Python 내부 `/internal/v1/change-impact-analysis`는 고정 Snapshot을 입력받는다. 임의 URL/임의 Cypher/실행 경로/정책 변경 endpoint 없음. 현재 앱의 로그인 없는 로컬 합성 환경 경계를 따른다. reviewer는 자기 기입 감사 표시값이며 인증된 사용자라고 주장하지 않는다.
