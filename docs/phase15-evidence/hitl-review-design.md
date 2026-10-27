# 검토와 실행 분리

검토는 DRAFT/IN_REVIEW/REVIEWED이며 실제 정책 승인과 무관하다. reviewRevision을 증가시키며 reviewedAt/reviewer/notes/analysisId와 조정된 후보 목록을 append-only 저장한다. 최신 분석 ID 및 expectedRevision 검증, Baseline stale 차단을 수행한다.

changeId별 changeType, apiId별 reviewDecision, testCaseId별 classification만 편집한다. 근거/ID/원문/기존 승인 상태/기대결과를 임의 변경한 요청은 거부한다. 리뷰 의견으로 의미 대응의 이견을 기록할 수 있으며 자유 원문 재작성은 허용하지 않는다.

불변 테이블은 SELECT FOR UPDATE 권한을 주지 않는다. 변경안 ID의 advisory transaction lock으로 검토 및 분석 결과 저장을 직렬화하여 권한 확대 없이 revision 경합을 방지한다. 기존 TC의 APPROVED, 검토 revision, 실행 가능 여부는 변경하지 않는다. 로그인 기능 없는 기존 로컬 앱과 동일한 신원 한계가 있다.
