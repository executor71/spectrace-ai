# 자동 실행 지원 격차

이번 작업은 생성 지원만 확장했다. 반납·검사·자산 등록용 Dummy handler, Fixture, AllowList를 추가하지 않았다. 신규 TC는 생성 응답에서 `executable=false`다. 승인만으로 실행이 가능해지지 않는다.

현재 DummyApiRegistry는 `GET /assets/{assetId}`, `POST /loans/{loanId}/approve`만 제공한다. 생성 정책의 AllowList는 기존 approve 경로만이며 `fixtureReady=false`를 유지했다. 실제 실행 계층은 별도의 닫힌 승인 Fixture를 사용한다. 재고 충돌·중복 승인용 신규 TC도 그 Fixture와 일치하지 않아 자동 실행할 수 없다.

| 필요한 확장 | 명세 / Method·Endpoint | 필수 Fixture와 관측값 |
|---|---|---|
| 반납 접수 | POST /loans/{loanId}/returns | 현재 대여자/자산 담당자/무권한 계정, 활성 대여, 미접수 상태; 정상 201·INSPECTION_PENDING, 자산은 즉시 AVAILABLE 금지 |
| 중복 반납 | 위와 동일 | 접수 완료 및 검사 완료 후 재접수 상태; 409·RETURN_ALREADY_REQUESTED, 새 반납 건 수 증가 없음 |
| 반납 권한 | 위와 동일 | 현재 대여자도 담당자도 아닌 계정; 403·ACCESS_DENIED |
| 검사 완료 | POST /returns/{returnId}/inspection | 자산 담당자, INSPECTION_PENDING, PASSED/DAMAGED, 파손 설명·사진 유무; AVAILABLE/MAINTENANCE 및 400·VALIDATION_ERROR |
| 자산 등록 | POST /assets | 자산 관리자, 필수 필드, 고유 자산번호/일련번호; 201·Location·AVAILABLE, 중복 409, 누락 400 |
| 재고/신청 상태 충돌 | POST /loans/{loanId}/approve | ON_LOAN 등 가용하지 않은 자산, APPROVED 신청; 409·ASSET_NOT_AVAILABLE / LOAN_STATE_CONFLICT |

자동 실행을 추가할 때는 다음을 별도 구현·검증해야 한다.

1. 문서의 Method·Endpoint·입력 필드를 그대로 사용하는 닫힌 handler와 입력 검증
2. 운영 DB를 사용하지 않는 실행별 독립 메모리 상태와 정상·예외 계정 Fixture
3. HTTP 상태·오류 토큰·업무 상태의 실행 전후 관측값 및 명세 기반 comparator
4. 접수/검사/자산의 상태와 생성 이력 수를 함께 검증하는 판정 계약
5. 매 실행의 Fixture 초기화, 재실행과 중복 요청의 구분, 실행 간 부작용 격리
6. 승인된 현재 revision만 실행하고 stale·미승인·미지원 경로를 차단하는 기존 방어 유지

현재 분석에 등장하는 포괄적인 '기존 대여 이력 확인/일관성 변경'의 필드·조회 범위·업무 단계 계약은 명확하지 않다. 임의의 loanStatus 변경이나 신규 이력 생성 규칙을 추가하지 않았다.

MCP의 기존 필드 의미도 유지했다. `generationExecutable=false`는 생성 정책 판정이고, 런타임 `executable`은 assertion/input의 기술적 판정이므로 true일 수 있다. 최종 실행 가능 여부는 `executionEligible`이며 실제 반납 4개 모두 false, apiAllowed/fixtureReady도 false다. 이 차이를 확인한 뒤 MCP 호환성 검사를 수행했으며 실행 로직은 변경하지 않았다.
