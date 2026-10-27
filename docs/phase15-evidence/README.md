# Phase 15 — 변경 영향 분석 결과

브랜치 `phase15/change-impact-analysis`. 구현 시작 HEAD `6e4a095`. 기존 105개 미커밋 파일의 시작 경로/hash 기록을 남기고 같은 HEAD에서 브랜치를 생성했다. 구현 당시 기존 작업을 삭제·stash·커밋하지 않았다. 이후 사용자의 커밋·Push 요청에 따른 분리 범위와 독립 검증은 `commit-validation.md`에 기록했다.

## 구현

- 불변 Baseline Snapshot + revision 해시, 별도 변경안 저장.
- 기존 단일 Job Worker/Queue/전역 모델 잠금에 CHANGE_IMPACT_ANALYSIS 추가. 별도 무제한 Worker 없음. 기존 Requirement Job 조회는 기존 유형으로 유지한다.
- LangGraph 기반 기존 근거 재사용·조건 비교·실제 Graph API/TC 후보 매핑, 새 TC 필요성 제안. 승인되지 않은 새 정책/Expected Result/실행 권한을 만들지 않는다.
- 신규 3개 app 테이블: change_impact, change_impact_analysis, change_impact_review. V12 additive migration. rag/evaluation 권한 확대 없음.
- React `/#impact`: Baseline, 조건 좌우 비교, API/TC 후보, 신규 TC 제안, 관계·Evidence, 검토 Revision/원문 이력, Excel 7개 시트.
- 검토 시 API 포함/제외 및 TC·조건 분류만 변경하며 원본 TC/승인 상태/실행 기록을 쓰지 않는다. 최신 검토본의 편집값도 재조회한다.
- create/baseline/diff/RAG/Graph/TC match/review/export OTel 실제 span 8종 확인. Job 대기시간과 실행시간 분리.

API 상세는 `change-impact-api-contract.md`, 각 설계는 필수 문서 10종에 기록했다.

## 실제 대표 결과

Baseline `80e2d374-0825-4811-a11e-03ade256b6e8`, 변경안 `88a0794d-e08b-480f-b6cc-0599ba81b080`.

Qwen 1회: Job `46e9d66e-8e97-4b1a-a122-60db300927d2`, QUEUED→RUNNING→SUCCEEDED, 대기 868ms/실행 39,658ms. 최초 모델은 자기 승인 금지 유지를 REMOVED로 오분류했다. 이 원본은 분석 이력에 그대로 보존했다.

원문 기반 승인 역할/자기 승인 금지 검증을 추가하고 기존 응답 재사용 Job `ec5e37bb-3f83-4dab-a09b-43c11d5bed5b`으로 새 결과를 저장했다. 추가 Qwen 호출 0회, 대기 397ms/실행 4,895ms. 부서장 유지·자산관리 담당자 추가 제안·자기 승인 금지 유지로 분리했다. 새 정책을 기존 RAG 확정 규칙으로 승격하지 않는다.

실제 Graph의 API-LOAN-APPROVE와 기존 TC 5건이 후보로 나온다. 해당 Baseline은 이전 정책 hash의 TC라 API는 REVIEW_REQUIRED, TC는 모두 REVIEW로 제안한다. 일부 TC는 검토 과정에서 endpoint/scenario가 수정된 기록이 있어 templateId를 알 수 없으며 UNKNOWN/null로 유지한다. 신규 역할 TC는 TEMPLATE_UNSUPPORTED/Expected Result null/자동 실행 false다.

Chrome에서 API 후보 포함 및 TC 분류 조정과 별도 검토 Revision 저장/재조회, 7-sheet XLSX, 모바일 표시를 확인했다. 비교 결과 원본과 검토본은 별개다. 저장된 예제는 추가 모델 호출 없이 다시 열 수 있다.

## 검증과 보존

최종 자동 테스트 **382건 통과**(Java 158 + Python 219 + frontend 단위 5). Phase 15 실제 Chrome 9개 확인, 기존 업무 화면 24개 해상도 조합, 랜덤 예제 desktop/mobile 회귀 통과. 프론트엔드 TypeScript/Vite 및 Docker 빌드 성공.

기존 Core 요구사항/분석/TC의 전후 JSON 동일. Ground Truth 2종, 기존 Graph 평가 결과 2종, 기존 정책 hash를 보존했다. 반납 요구사항 사전 Graph는 10 nodes/20 edges/4 TC로 정상이며 원본은 유지했다. 기존 평가셋이나 정책 AllowList를 수정하지 않았다.

평가는 작성자 초안의 합성 사례 1건에 대한 fixture 일치 검사다. 독립 사람 검토는 미완료이며 일반 정확도/정밀도 100%를 주장하지 않는다. 최초 모델 오분류, 제한적 도메인 보정, 넓은 TC 후보, 로그인 없는 로컬 앱의 신원 한계, 미실행한 동시 부하/실모델 실행 중 재시작 테스트를 문서화했다.

## 이번 작업 소스 목록

추가:

- backend/src/main/resources/db/migration/V12__change_impacts.sql
- backend/src/main/java/com/example/legacyassistant/impact/ChangeImpactService.java
- backend/src/main/java/com/example/legacyassistant/impact/ChangeImpactController.java
- backend/src/main/java/com/example/legacyassistant/impact/ImpactExport.java
- backend/src/test/java/com/example/legacyassistant/impact/ChangeImpactIntegrationTest.java
- ai-service/app/change_impact.py
- ai-service/app/condition_atoms.py
- ai-service/tests/test_change_impact.py
- frontend/src/ChangeImpact.tsx
- frontend/src/change-impact.css

수정:

- backend/src/main/java/com/example/legacyassistant/analysis/AnalysisClient.java
- backend/src/main/java/com/example/legacyassistant/jobs/JobStore.java
- backend/src/main/java/com/example/legacyassistant/jobs/JobWorker.java
- backend/src/main/java/com/example/legacyassistant/testcase/TestCasePolicy.java (읽기 전용 정책 snapshot 접근)
- backend/src/test/java/com/example/legacyassistant/jobs/JobWorkerTest.java
- ai-service/app/main.py
- frontend/src/App.tsx
- frontend/src/Icon.tsx
- frontend/src/navigation.ts

기존 미커밋 변경이 있던 파일은 그 내용을 보존하며 위 범위만 추가했다. Graph 오류 수정 파일은 이번 Phase에서 다시 수정하지 않았다. 이 폴더의 설계 문서/JSON/스크린샷/다운로드 XLSX는 증거 산출물이다. Phase 16/17 개발은 하지 않았다.
