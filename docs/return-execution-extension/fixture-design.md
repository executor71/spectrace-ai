# 실행별 합성 Fixture

각 호출은 새로운 ObjectNode를 준비한다. mutable static 상태·운영 DB·외부 API는 없다. 표준 ID는 기존 LOAN/ASSET과 고정된 synthetic return UUID를 사용하지만 값만 같을 뿐 상태 객체는 공유되지 않는다.

| Template / mode | Actor | 초기 상태 | 기대 결과 |
|---|---|---|---|
| return-normal / standard | current-borrower | ACTIVE, ON_LOAN, returnCount=0 | 201, 접수 1건, INSPECTION_PENDING, 자산 ON_LOAN |
| return-normal / asset-admin | asset-admin | 위와 동일 | 위와 동일 |
| return-duplicate / standard | current-borrower | returnCount=1, 검사 미완료 | 409, 모든 관측 상태 불변 |
| return-duplicate / completed-return | current-borrower | returnCount=1, 검사 완료, 자산 AVAILABLE | 409, 이력 수/완료 상태/자산 상태 불변 |
| return-authorization / standard | return-other | 접수 없음 | 403, 모든 관측 상태 불변 |
| return-inspection-pending / standard | current-borrower | ON_LOAN, 접수 없음 | 201, 검사 전 AVAILABLE 금지 |
| inspection-damage-required / standard | asset-admin | 반납 1건, 검사 미완료 | 400 VALIDATION_ERROR, 상태 불변 |
| 정상/검사대기 / intentional-defect | current-borrower | 정상과 동일 | **고의로** 검사 전 AVAILABLE 전이. HTTP 201은 정상이나 상태 assertion이 FAIL |
| 정상/검사대기 / fixture-error | current-borrower | 초기화 시 예외 주입 | ERROR / FIXTURE_INITIALIZATION_ERROR. API·assertion 실행 안 함 |

결함/오류 모드는 기본값이 아니다. 준비 API로 명시적으로 선택한 검토본을 개발자가 승인해야 한다. 실행 POST body로 모드를 바꾸는 것은 금지한다. 원본과 다른 임의 body, actor, preconditions, contractVersion, assertion은 exact contract 비교에서 차단한다.

ERROR 검증 모드는 실제 외부 네트워크를 중단하지 않는다. 네트워크 장애는 테스트에서 SocketTimeoutException을 가진 Adapter 예외로 검증한다. 실제 서비스 ERROR 증거는 명시적인 Fixture 초기화 실패다.

의도적 결함과 오류 주입은 syntheticDefect=true로 명시되어 일반 실패·성공 통계에서 제외된다. 모든 결과와 과거 revision은 전체 실행 이력·Excel에 남는다. 동시 40회 교차 정상/결함 실행 테스트와 반복 실행 테스트로 상태 격리를 확인했다.
