# 장비 반납 및 검사 API 명세

## POST /loans/{loanId}/returns 반납 접수
POST /loans/{loanId}/returns 요청은 accessoriesReturned와 note를 받는다. 성공 시 HTTP 201과 returnId, status=INSPECTION_PENDING을 반환한다. 같은 대여에 반납 접수가 이미 있으면 HTTP 409 RETURN_ALREADY_REQUESTED다. 현재 대여자가 아니고 자산 담당자도 아닌 호출자는 HTTP 403 ACCESS_DENIED다.

## POST /returns/{returnId}/inspection 검사 완료
POST /returns/{returnId}/inspection 요청 필드는 result, damageDescription, photoReferences다. result는 PASSED 또는 DAMAGED다. DAMAGED에서는 파손 설명과 최소 한 개의 사진 참조가 필수이며 누락 시 HTTP 400 VALIDATION_ERROR다. PASSED는 AVAILABLE, DAMAGED는 MAINTENANCE로 자산 상태를 전환한다. 이미 완료된 검사는 HTTP 409 RETURN_STATE_CONFLICT다.

## GET /loans/overdue 연체 조회
GET /loans/overdue는 기준일 asOf와 departmentId로 연체 대여를 조회한다. 부서장은 자기 부서, 자산 관리자는 전체 부서를 조회할 수 있다. 응답은 loanId, dueDate, overdueDays를 포함한다. 예정일 당일 및 반납 접수 완료 건은 결과에서 제외한다. asOf 생략 시 서버의 업무 날짜를 사용한다.
