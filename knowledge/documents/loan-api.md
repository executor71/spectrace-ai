# 장비 대여 신청과 승인 API 명세

## POST /loans 대여 신청
POST /loans의 JSON 요청 필드는 assetId, dueDate, purpose다. requesterId는 요청 본문에서 받지 않고 인증된 직원으로 결정한다. 성공 시 HTTP 201과 loanId, status=PENDING_APPROVAL을 반환한다. ACTIVE가 아닌 직원은 HTTP 403 EMPLOYEE_INACTIVE, 노트북 활성 대여가 이미 있으면 HTTP 409 ACTIVE_LOAN_EXISTS다. dueDate는 YYYY-MM-DD 형식이며 미래 날짜여야 한다.

## POST /loans/{loanId}/approve 승인
POST /loans/{loanId}/approve는 승인 권한이 있는 부서장만 호출한다. body의 comment는 선택 항목이다. 성공 시 HTTP 200과 status=APPROVED를 반환하고 자산은 RESERVED가 된다. 본인 신청 승인 시 HTTP 403 SELF_APPROVAL_FORBIDDEN을 반환한다. 자산 재고 충돌은 HTTP 409 ASSET_NOT_AVAILABLE, 신청 상태 충돌은 HTTP 409 LOAN_STATE_CONFLICT다.

## POST /loans/{loanId}/issue 지급 확인
POST /loans/{loanId}/issue는 자산 담당자가 실물 장비를 지급한 뒤 호출한다. 승인된 신청만 처리할 수 있으며 성공 시 HTTP 200, 대여 상태 ACTIVE와 자산 상태 ON_LOAN을 반환한다. 승인 전 지급 요청은 HTTP 409 LOAN_STATE_CONFLICT다. 수령 확인 시각과 담당자 ID는 서버에서 기록한다.
