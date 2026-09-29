# 자산관리 업무 오류 코드 사전

## ASSET_NOT_AVAILABLE 재고 충돌
HTTP 409 ASSET_NOT_AVAILABLE은 대여 승인 시 장비가 AVAILABLE이 아니거나 이미 다른 신청에 예약된 경우다. 사용자에게 최신 재고를 조회하고 다른 장비를 선택하도록 안내한다. 같은 승인 요청을 무조건 반복하면 성공을 보장할 수 없다. 단순 입력 누락인 VALIDATION_ERROR와 구분한다.

## SELF_APPROVAL_FORBIDDEN 자기 승인
HTTP 403 SELF_APPROVAL_FORBIDDEN은 승인자와 신청자가 동일할 때 발생한다. 부서장 역할이 있어도 자기 신청을 승인할 수 없다. 상위 조직의 지정 승인자를 통해 진행한다. 로그인 실패가 아니라 업무 권한 위반이므로 신청이나 자산 상태는 변경하지 않는다.

## RETURN_ALREADY_REQUESTED 중복 반납
HTTP 409 RETURN_ALREADY_REQUESTED는 같은 대여에 반납 접수가 이미 존재하는 경우다. 새 반납 건을 생성하지 않고 기존 returnId의 진행 상태를 조회한다. 첫 요청의 응답을 받지 못한 재시도에서도 반납이 두 번 기록되지 않아야 한다. 검사 완료 후 재접수도 동일하게 거부한다.
