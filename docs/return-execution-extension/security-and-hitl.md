# 보안 및 Human-in-the-Loop

1. 원본 TC와 Evidence는 변경하지 않는다. policyHash와 원래 분석 스냅샷이 유효하고 원본이 현재 근거 기반 정책 후보인지 확인한다.
2. 실행 준비는 검토본의 실행 입력·전제·Expected Result만 바꾸고 기존 edit 경로로 DRAFT 전환·reviewRevision 증가·승인 해제를 수행한다.
3. 별도 approve API/버튼으로 현재 검토본을 승인해야 한다. DRAFT·REJECTED·수정 후 미승인·stale TC는 실행하지 않는다.
4. React의 If-Match revision이 현재 값과 다르면 REVIEW_CONFLICT로 거부한다. MCP Tool 입력은 변경하지 않으며 ID-only 실행도 DB 잠금 아래 현재 승인본만 사용한다. 실행/수정/재생성은 기존 잠금 및 원본 불변 제약을 재사용한다.
5. 실행 POST는 body를 받지 않는다. setup POST는 reviewRevision·fixtureProfile만 받는다. 알 수 없는 URL, endpoint, 임의 역할이나 모드 override는 거부한다.
6. 반납은 AllowList·Adapter·grounded original·exact contract·Fixture가 모두 있어야 executable=true다. 원래 생성 시 executable=false 기록은 DB UPDATE하지 않고 런타임 eligibility에서 재평가한다. MCP의 generationExecutable과 실행 적격성 필드 구분을 유지한다.
7. 정상/고의 결함/오류 주입은 모두 승인 revision과 실제 실행 입력을 snapshot으로 남긴다. 이후 재검토되어도 과거 실행 snapshot은 불변이다.
8. 기존 app_user·rag_reader·evaluation_reader 역할 경계를 유지한다. 생성·실행 코드에 GT 접근 경로를 추가하지 않는다. 실행할 때 자산/대여 실데이터를 수정하지 않으며 기존 실행 감사 테이블에만 기록한다.
9. 인증 없는 기존 로컬 합성 시연 환경이다. current-borrower 등의 actor는 고정 Fixture의 역할이며 운영 인증을 새로 구현했다고 주장하지 않는다.
10. Trace에는 ID·API ID·AllowList/Fixture 검증·결과·기간만 기록한다. 개인정보·비밀값·전체 Request Body를 기록하지 않는다.

자동 테스트: 기존 승인/실행 회귀 유지, 새 Fixture 준비의 승인 해제, 재승인 전 차단, 과거 If-Match 거부, 약화된 assertion 차단, 입력 override 차단, 원본 근거 및 실행 이력 불변을 확인했다.
