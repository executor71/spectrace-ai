# 실행 지원 범위 (구현 전 조사)

기준: 정책 확장 커밋 6e4a095. 기존 미커밋 UI/Java 업그레이드는 보존한다. 생성 정책 15개·분석·GT는 변경하지 않는다.

| Template | 저장 TC ID | 근거 / Section | API | 명시 응답 | 이번 실행 범위 |
|---|---|---|---|---|---|
| return-normal | 82f12fb5-961b-44c2-b3fb-ca4d40b26f08 | return-rules / 반납 접수와 검사 대기, return-api / 반납 접수 | POST /loans/{loanId}/returns | 201, returnId, INSPECTION_PENDING | 현재 대여자 또는 담당자의 정상 접수 |
| return-duplicate | e502f2c9-cfc1-48cc-83da-7d0c3ff0f5da | 동일 API 및 RETURN_ALREADY_REQUESTED 오류 규칙 | 동일 | 409, RETURN_ALREADY_REQUESTED | 기존 접수·검사 완료 후 재접수, 이력 수·상태 불변 |
| return-authorization | 075b3943-f42e-47b8-8b67-a7dedb1b030c | return-rules / 반납 권한, return-api | 동일 | 403, ACCESS_DENIED | 대여자도 담당자도 아닌 계정, 상태 불변 |
| return-inspection-pending | 83a38d0b-705a-4cd3-9af8-5c7ac7d47054 | return-rules / 반납 접수와 검사 대기 | 동일 | 201, INSPECTION_PENDING | 검사 전 AVAILABLE 금지, 합성 접수 이력 1건 |
| inspection-damage-required | 저장 TC 없음 | return-rules / 파손 장비의 수리 전환, return-api / 검사 완료 | POST /returns/{returnId}/inspection | 400, VALIDATION_ERROR | 파손 설명·사진 누락 거부만 지원 |
| inspection-passed / inspection-damaged | 저장 TC 없음 | return-api / 검사 완료 | 동일 | 성공 HTTP 상태 미명시 | 성공 자동 실행은 UNSUPPORTED. AVAILABLE/MAINTENANCE 규칙 자체는 분석·생성 가능 |

실제 자산/대여 DB 변경은 없다. 모든 상태는 호출별 독립 메모리이며 DB에는 기존 실행 감사 이력만 저장한다. 대여 이력의 완료 상태명·변경 시점은 명시되지 않아 새로운 loanStatus를 만들어 전이시키지 않는다. 초기 loanStatus=ACTIVE는 합성 Fixture 관측값이며 반납 접수 중 변경하지 않는다.

준비 전에는 저장 TC를 일괄 true로 바꾸지 않는다. 닫힌 Fixture 준비를 요청하면 검토본만 수정되고 revision이 증가하며 DRAFT로 돌아간다. 사용자가 새 revision을 별도로 승인해야 실행된다.

## 최종 결과

기존 저장 반납 4개는 실행 준비 후 별도 승인한 현재 revision에서 실행 가능하다. 기존 생성 정책의 executable 기록은 false로 보존하고 런타임 eligibility로 판정한다. NORMAL·EXCEPTION·AUTHORIZATION·BUSINESS_RULE은 지원되며 반납 BOUNDARY 템플릿은 없다.
파손 증빙 누락 검사 1개는 고정 테스트 Fixture로 400 PASS를 확인했다. 실제 저장된 대표 분석은 검사 조건이 확정되지 않아 이 TC를 새로 만들지 않았다. 성공 검사 2개, 자산 등록·재고 충돌·중복 승인 등은 이번 반납 실행 계약 범위 밖이다.
