# 반납 판정 규칙

기존 ExecutionComparator를 재사용한다. 생성 엔진·LLM·GT가 실행 결과를 결정하지 않는다.

- HTTP_STATUS: 정상 접수 201, 중복 409, 권한 거부 403, 증빙 누락 400
- RESPONSE_TOKEN: 명세의 오류 코드와 정확히 비교
- RESPONSE_FIELD: 접수 status와 고정 합성 returnId를 비교
- OBSERVATION_EQUALS: returnStatus, returnCount, inspectionCompleted를 타입까지 비교
- UNCHANGED: 실행 전후 자산 상태 및 거부 요청의 대여·반납 상태/이력 수/검사 완료 여부를 비교

허용 필드만 확장했다. returnCount는 비음수 정수, inspectionCompleted는 boolean, 상태는 문자열이다. 알 수 없는 필드·잘못된 자료형·중복 판정 대상·HTTP assertion 누락은 실행 불가다.

반납 실행은 원본 generatedContent가 현재 policy 후보와 정확히 일치해야 하고, 검토본의 input/preconditions/expectedResult가 선택한 Fixture의 닫힌 계약과 일치해야 한다. 예를 들어 상태 assertion을 지우고 HTTP 201만 남기면 EXECUTION_CONTRACT_UNSUPPORTED로 차단한다. Expected Result를 느슨하게 만들어 PASS시키지 않는다.

정상 HTTP만으로 PASS를 결정하지 않는다. 실제 의도적 결함 결과는 Expected/Actual HTTP가 모두 201이지만 Expected assetStatus=ON_LOAN, Actual=AVAILABLE이어서 comparator가 FAIL을 만든다. 결과 값을 직접 FAIL로 지정하지 않는다.

Fixture 초기화·Adapter 통신·판정 인프라 예외는 ERROR로 저장한다. 초기화 실패는 fixtureBefore=null이고 API 호출이나 업무 비교를 수행하지 않았음을 errorStage로 표시한다. ERROR의 빈 mismatch 목록을 PASS나 정상 업무 결과로 해석하지 않는다.

일반 Dashboard는 현재 batch/current revision의 최신 일반 실행만 사용한다. syntheticDefect 실행과 과거 revision은 전체 이력에 남지만 일반 PASS/FAIL/ERROR 지표에 섞지 않는다. 기존 Excel의 STRING 셀·수식 주입 방어는 그대로 유지한다.
