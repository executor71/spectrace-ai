# 자산 조회와 등록 API 명세

## GET /assets 재고 조회
GET /assets는 가상 자산 목록 조회 API다. query parameter로 status, assetType, page, size를 받는다. size는 1부터 100까지이며 기본 20이다. status=AVAILABLE로 대여 가능 장비를 조회한다. 응답은 items 배열과 total을 포함하고 각 항목에 assetId, assetNumber, assetType, status를 반환한다. 임직원은 자기 조직의 재고만 볼 수 있다.

## POST /assets 자산 등록
POST /assets는 자산 관리자 전용이다. JSON 필드는 assetNumber, serialNumber, assetType, purchasedAt, departmentId다. 성공 시 HTTP 201과 Location: /assets/{assetId}를 반환한다. 자산번호 또는 일련번호가 이미 존재하면 HTTP 409와 DUPLICATE_ASSET 오류를 반환한다. 필수값 누락은 HTTP 400 VALIDATION_ERROR다.

## GET /assets/{assetId} 상세 조회
GET /assets/{assetId}는 UUID 자산 식별자로 상세 정보를 반환한다. 성공은 HTTP 200이며 status와 현재 대여 상태를 포함한다. 다른 조직 자산은 권한 정책에 따라 HTTP 403 ACCESS_DENIED다. UUID 형식 오류는 HTTP 400, 존재하지 않는 자산은 HTTP 404 ASSET_NOT_FOUND다. 직원 개인정보와 구입 금액은 일반 임직원 응답에서 제외한다.
