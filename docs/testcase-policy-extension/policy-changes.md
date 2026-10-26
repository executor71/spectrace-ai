# 테스트 생성 정책 확장

## 범위

기존 승인 템플릿 5개를 그대로 보존하고 10개를 추가하여 총 15개다. 기존 JSON 정책 구조, 5개 Test Type, 모델의 `candidateIds` Structured Output, TC 필드 구조는 유지했다. 모델은 검증된 후보 ID만 선택하며 TC 수를 5개로 고정하지 않는다.

| 추가 ID | 유형 | 검증 범위 |
|---|---|---|
| return-normal | NORMAL | 정상 반납 201 / INSPECTION_PENDING |
| return-duplicate | EXCEPTION | 중복 접수 409 / RETURN_ALREADY_REQUESTED |
| return-authorization | AUTHORIZATION | 현재 대여자·자산 담당자 외 호출 403 / ACCESS_DENIED |
| return-inspection-pending | BUSINESS_RULE | 접수만으로 AVAILABLE로 변경하지 않음 |
| inspection-passed | BUSINESS_RULE | 명시적으로 확정된 PASSED 검사 → AVAILABLE |
| inspection-damaged | BUSINESS_RULE | 명시적으로 확정된 DAMAGED 검사 → MAINTENANCE |
| inspection-damage-required | EXCEPTION | DAMAGED 증빙 누락 400 / VALIDATION_ERROR |
| inventory-unavailable | BUSINESS_RULE | 승인 시 대여 불가 자산 409 / ASSET_NOT_AVAILABLE |
| asset-registration | NORMAL | 자산 관리자 정상 등록 201 / AVAILABLE |
| duplicate-approval | EXCEPTION | 이미 승인된 신청 재승인 409 / LOAN_STATE_CONFLICT |

검사 TC는 검사 조건이 확정된 경우만 생성된다. 단순 반납 접수 조건을 검사 완료 조건으로 확대하지 않는다. 신규 Expected Result는 합성 문서의 정확한 인용이며 상태·오류 코드·HTTP assertion도 인용에서 확인한다.

## 제한된 API Evidence Adapter

기존 반납 분석의 Top-5에는 업무규칙과 오류 문서는 있지만 API 명세 본문이 없다. 검색 알고리즘·Top-K·분석 프롬프트를 변경하거나 근거 검증을 완화하지 않았다.

`apiEvidence`는 공개 합성 `knowledge/documents`의 API_SPEC Section에서 내보낸 카탈로그다. 신규 템플릿의 확정 조건이 원래 분석에 존재하고, 같은 Method/Endpoint가 그 분석의 `relatedApis`에 이미 있는 경우만 해당 명세를 연결한다. Python과 Java가 각각 후보·근거를 재구성한다. 임의 검색, DB 조회, 외부 도구, Ground Truth는 사용하지 않는다.

로딩 시 corpus의 synthetic 표시, 원문·문서 유형·Section·UUIDv5·관련 API 메타데이터를 비교한다. 중복 템플릿 ID, 잘못된 Expected Result, 없는 Endpoint, 변조된 명세 참조는 실패한다. AI는 lifespan 시작 시, Spring은 Bean 생성 시 검사한다. `KNOWLEDGE_ROOT`의 기본값은 `/knowledge`이며 Compose에서 read-only 마운트한다.

원래 분석 API와 DB의 `source_analysis` 비교 스냅샷은 변경하지 않는다. 공개 TC 응답의 `sourceAnalysis.evidence`에는 실제 사용한 정책 API 근거만 추가하여 Evidence가 해석되도록 한다. 추가분은 `policyEvidence`에도 별도로 표시한다. `score=0`은 벡터 검색 점수가 아닌 정책 연결 근거임을 나타낸다. 정책 파일에 원문이 포함되므로 명세 변경 시 재생성·로딩 검증이 필요하다.

## 상태와 조건 매핑

외부 TC 응답에 `generationStatus`, `conditionCoverage`, `policyEvidence`를 추가했다. 내부 AI 생성 응답의 기존 5개 필드와 TC의 기존 필드는 유지한다. 상태는 조회 시 저장된 원본 스냅샷과 정책으로 재계산한다. 신규 DB 상태나 마이그레이션은 없다.

- GENERATED: 모든 확정 조건이 생성된 템플릿으로 지원됨
- PARTIALLY_GENERATED: 일부 TC 생성, 일부 확정 조건은 미지원/근거 부족
- BLOCKED_UNSUPPORTED_TEMPLATE: 등록된 템플릿 자체가 없음
- BLOCKED_INSUFFICIENT_EVIDENCE: 확정 조건 없음 또는 알려진 템플릿의 명세/업무규칙/전제 근거 부족
- BLOCKED_CLARIFICATION_REQUIRED: 분석의 확인 필요 항목이 남음
- FAILED: 기존 HTTP 오류 응답을 유지하며 React에서 시스템 오류로 표시. 실패한 배치를 저장하지 않음

`conditionCoverage`에는 확정 문장·chunkId·지원 상태·적용 템플릿 ID·생성 TC ID가 포함된다. 확인 질문/모호함/누락이 남은 경우의 전체 보류 규칙은 안전성을 위해 유지했다. 부분 생성은 미지원 조건이 있어도 검증 완료된 다른 조건이 존재하는 경우를 지원한다.

## 호환성과 영향

승인/검토/실행 상태와 Dummy API Registry는 변경하지 않았다. MCP Tool 이름·입력 스키마·기존 필드는 유지한다. GT·평가 코드·평가셋·RAG 문서는 변경하지 않았다.

정책 hash 변경으로 이전 정책으로 생성한 배치는 기존 설계대로 `stale=true`가 된다. 기존 승인·실행 이력은 지우지 않았으며, 새 정책으로 사용하려는 배치는 재생성이 필요하다. 원래 승인 5개 템플릿 자체의 동작은 회귀 테스트로 확인했다.

## 이번 작업의 수정 파일

- `contracts/test-case-policy.json`
- `ai-service/app/main.py`, `test_case_policy.py`, 신규 `test_case_registry.py`
- `ai-service/tests/test_test_case_generation.py`, 신규 `test_policy_extension.py`
- `backend/.../testcase/TestCasePolicy.java`, `TestCaseService.java`, 신규 `PolicyRegistry.java`
- 신규 `backend/.../testcase/PolicyExtensionTest.java`, `backend/src/test/resources/policy-extension-return.json`
- `compose.yaml`, `compose.test.yaml`: 합성 문서 read-only 마운트
- `frontend/src/TestCases.tsx`, `Requirements.tsx`의 정책 지원 안내 부분, `style.css`의 정책 결과 스타일
- 신규 `frontend/tests/policyGeneration.browser.py`
- 이 폴더의 조사·검증 코드와 결과

작업 시작 전 존재하던 리디자인·랜덤 예제 변경과 `backend/Dockerfile`, `backend/pom.xml`의 사용자 변경은 보존했다. Phase 15·Git 커밋·Push는 수행하지 않았다.
