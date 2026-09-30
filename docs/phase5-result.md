# Phase 5 완료 결과

Phase 5 범위 구현 및 실제 검증을 완료했다. Phase 6으로 진행하지 않았다. 실제 LLM 추가 호출은 0회다.

## 검증 결과

| 검증 | 결과 |
|---|---|
| Backend | 55/55 통과: 기존 39 + Phase 5 통합 12 + 단위 4, 실패/오류/스킵 0 |
| Python 기존 회귀 | 61/61 통과, 저장 fixture 및 mock 사용 |
| React | TypeScript/Vite production build 성공 |
| Chrome | 수정 5항목, 승인, 반려, 변조 차단, 재조회, 모바일 모두 통과 |
| Phase 0 | Backend/AI health UP, PostgreSQL/pgvector 정상, V1~V8 성공 |
| Phase 1 | 기존 Requirement 통합 테스트 통과 |
| Phase 2 | 9 documents / 27 chunks 유지, 8 검색의 Top-5 순서 및 score 동일 |
| Phase 3/4 | 기존 Backend/Python 분석·생성 테스트 통과, 기존 실제 모델 생성 5건의 원본/evidence 유지 |
| 기존 경계 | 기준점 83개 파일 중 78개 동일, 5개는 Review 응답/UI/테스트 출력 경로 확장 |
| DB 권한 | app→rag/evaluation, rag→app/evaluation 접근 불가 확인 |

Python 첫 실행의 2개 오류는 컨테이너에 테스트용 corpus/소스 검사 경로가 없어서 발생했다. 기존 코드는 수정하지 않고 테스트 리소스를 제공한 뒤 61개가 통과했다. 최종 subprocess exit code=0을 확인했다.

### Backend 세부

| Suite | Tests |
|---|---|
| AnalysisIntegrationTest | 9 |
| RequirementIntegrationTest | 14 |
| RequirementServiceTest | 3 |
| TestCaseIntegrationTest | 13 |
| TestCaseReviewIntegrationTest | 12 |
| TestCaseReviewUnitTest | 4 |

## 실제 React 사용자 흐름

Chrome 154.0.8037.58 (channel=chrome, headless), `http://localhost:5173`. 요구사항 `b5270f71-c92c-48ae-8530-8946f1cfce62`를 사용했다.

1. 요구사항을 조회하고 기존 분석 근거 5개와 생성 TC 5개를 확인했다. V8 적용 직후 모두 DRAFT였다.
2. 첫 TC의 scenario를 수정하고 저장했다. DRAFT와 사용자 수정본 표시, 원본 보존을 확인했다.
3. 검토 의견을 입력하고 승인했다. APPROVED, 검토자, 시각, 의견이 저장되었다.
4. 두 번째 TC에 의견을 입력하고 반려했다. REJECTED가 저장되었다.
5. 실제 API로 evidence, requirementId, approvalStatus, executable 위조, enum/빈 scenario를 전송하여 모두 400을 확인했다. 없는 ID의 PATCH/approve/reject는 404였다.
6. 페이지를 새로고침하고 다시 조회하여 수정값, 승인/반려, AI 원본과 evidence가 유지됨을 확인했다.
7. 별도 TC에서 다섯 편집 항목 모두를 Chrome으로 저장했다. 잘못된 JSON 안내와 input 수정 직후 기술 조건 갱신도 확인하고 해당 TC 내용은 원래대로 복원했다.
8. 모바일 390px 가로 넘침 없음, 브라우저 오류 0건, 생성/분석 요청 0건을 확인했다.

스크린샷:

- `phase5-evidence/01-draft-review.png`
- `phase5-evidence/02-approved.png`
- `phase5-evidence/03-rejected.png`
- `phase5-evidence/04-reloaded-evidence.png`
- `phase5-evidence/05-mobile-review.png`
- `phase5-evidence/06-all-fields-edited.png`
- `phase5-evidence/07-final-review-flow.png`

## Migration 및 API

`V8__test_case_review.sql`: reviewed_content, approval_status(DRAFT 기본값), reviewed_at, reviewer, review_comment, review_revision. 상태/Review 객체/메타데이터 CHECK 및 원본·식별자 변경 금지 트리거. 기존 V1~V7과 DB 권한 변경 없음.

- `PATCH /api/test-cases/{id}`
- `POST /api/test-cases/{id}/approve`
- `POST /api/test-cases/{id}/reject`
- `GET /api/requirements/{requirementId}/test-cases` (기존 API 확장)

변경 요청에는 GET에서 받은 reviewRevision을 포함한다. detailed 계약은 `phase5-design.md`를 참조한다.

## 승인/반려 실제 JSON (발췌)

```json
{
  "approve": {
    "testCaseId": "c53be0ea-3157-49be-a922-efa378d6ca11",
    "approvalStatus": "APPROVED",
    "reviewedAt": "2026-09-30T10:03:21.895379+00:00",
    "reviewer": "demo/local",
    "reviewComment": "근거와 수정 내용을 확인하여 승인합니다.",
    "reviewRevision": 2,
    "modified": true,
    "executable": false,
    "executionEligible": false
  },
  "reject": {
    "testCaseId": "c0dca00f-7a4c-4861-ba42-06c7588235b1",
    "approvalStatus": "REJECTED",
    "reviewedAt": "2026-09-30T10:03:22.032836+00:00",
    "reviewer": "demo/local",
    "reviewComment": "예외 조건의 추가 검토가 필요하여 반려합니다.",
    "reviewRevision": 1,
    "modified": false,
    "executable": false,
    "executionEligible": false
  }
}
```

전체 응답은 `phase5-evidence/approve-response.json`, `reject-response.json`에 저장했다.

## 변경 파일

기존 파일 변경:

- `backend/src/main/java/com/example/legacyassistant/testcase/TestCaseRepository.java`
- `backend/src/main/java/com/example/legacyassistant/testcase/TestCaseService.java`
- `frontend/src/style.css`
- `frontend/src/TestCases.tsx`
- `compose.test.yaml`

추가 파일:

- `backend/src/main/java/com/example/legacyassistant/testcase/TestCaseReviewController.java`
- `backend/src/main/java/com/example/legacyassistant/testcase/TestCaseReviewService.java`
- `backend/src/main/resources/db/migration/V8__test_case_review.sql`
- `backend/src/test/java/com/example/legacyassistant/testcase/TestCaseReviewIntegrationTest.java`
- `backend/src/test/java/com/example/legacyassistant/testcase/TestCaseReviewUnitTest.java`
- `docs/phase4-baseline/sha256.json`
- `docs/phase4-baseline/source.zip`
- `docs/phase5-design.md`
- `docs/phase5-result.md`
- `docs/scripts/phase5-browser-final.py`
- `docs/scripts/phase5-browser.py`
- `docs/scripts/phase5-regression.py`
- `docs/scripts/phase5-runtime.py`
- `frontend/src/TestCaseReview.tsx`

검증 산출물: `docs/phase5-evidence/`의 JSON/로그/스크린샷/Surefire XML.

## 미해결 사항 및 유지한 제한

- Phase 5 완료를 막는 미해결 사항 없음.
- 인증 없이 demo/local 사용자 값을 사용한다. 검토자 값은 신원 인증을 의미하지 않는다.
- 과거 검토 이력 전체를 보관하지 않고 원본 + 최신 수정본/최신 결정을 보관한다.
- 재생성 시 기존 Phase 4 batch 교체 정책을 유지하므로 기존 검토 결과도 교체되며 새 TC는 DRAFT다.
- 현 fixtureReady=false 때문에 실제 TC는 승인되어도 실행 대상이 아니다. true/false와 approval의 독립성은 단위 테스트로 검증했다.
- Phase 6 Evaluation, Phase 7 Dummy 실행, PASS/FAIL 및 추가 검색 기법은 구현하지 않았다. Ground Truth는 생성·검토에서 접근하지 않았다.
