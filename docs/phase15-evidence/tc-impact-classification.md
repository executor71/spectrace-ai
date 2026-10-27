# TC 영향 후보

동결 batch의 TC와 조건 Evidence chunk 교집합을 우선 연결한다. REMOVED 연결은 OBSOLETE_CANDIDATE, MODIFIED 연결은 UPDATE_CANDIDATE, 신규/불확실/연결 없음/정책 hash 불일치는 REVIEW, 확인된 유지 조건만 있는 경우 KEEP이다. 기준과 실제 Graph에서 조회되는 TC ID의 일치 여부를 함께 기록한다. 조건 추가는 기존 권한 테스트의 의미를 바꿀 수 있어 보수적으로 넓은 REVIEW 후보를 제시한다.

TC ID/type/scenario/evidence/approval/reviewRevision/executable/최신 실행/정책 hash를 보존한다. 원래 TC 계약에 templateId가 없는 경우 동결 정책 case의 scenario/type이 유일하게 일치하면 SNAPSHOT_CASE_MATCH로 추정 출처를 명시하고, 그렇지 않으면 UNKNOWN/null로 둔다. 이를 저장된 원래 template ID라고 오인하지 않는다.

ADDED/MODIFIED/UNCERTAIN의 새 조건은 NEW_CANDIDATE 필요성 제안이다. 기존 정책 confirmedCondition과 정확히 일치하는 plan이 없으면 TEMPLATE_UNSUPPORTED, 있더라도 SUPPORTED_REVIEW_REQUIRED다. Expected Result는 null, 자동 실행 지원은 false이며 확정된 근거와 별도 기존 TC 생성/승인/실행 흐름이 필요하다. 삭제된 조건은 신규 생성 대상으로 만들지 않는다.

이 분류는 결정적 휴리스틱과 의미 비교 제안을 조합한다. 정밀한 변경 코드/분기 단위 영향 확정이나 실제 수정/삭제를 수행하지 않는다.
