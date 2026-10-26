# 지원 범위 조사 및 구현 결정

조사 기준: 2026-10-26 작업 시작 시점. 문서는 `knowledge/documents/`, 생성 정책은 `contracts/test-case-policy.json`, 실행 계층은 `DummyApiRegistry`와 실행 정책을 직접 확인했다.

| 업무 시나리오 | RAG 근거 | 기존 TC 템플릿 | 자동 실행 API | Fixture | 기존 지원 단계 / 구현 결정 |
|---|---|---|---|---|---|
| 대여 승인 권한 | loan-rules, loan-api, loan-test-guide | 5개 | approve | 승인용 격리 Fixture만 존재 | 기존 5개 유지 |
| 반납 접수 | return-rules §반납 접수와 검사 대기, return-api §returns | 없음 | 없음 | 없음 | 생성 추가, 실행 차단 |
| 중복 반납 | return-api, error-codes §RETURN_ALREADY_REQUESTED | 없음 | 없음 | 없음 | 생성 추가, 실행 차단 |
| 반납 검사 | return-rules §파손 장비의 수리 전환, return-api §inspection | 없음 | 없음 | 없음 | 명시적 검사 조건·명세 근거가 있을 때만 생성 |
| 반납 후 상태 변경 | 위 문서: 접수 INSPECTION_PENDING / 검사 PASSED→AVAILABLE, DAMAGED→MAINTENANCE | 없음 | 없음 | 없음 | 접수와 검사 구분하여 생성 |
| 자산 상태별 대여 제한 | asset-lifecycle §대여 가능한 재고 판정, loan-rules §동시 승인과 자산 예약, loan-api | 없음 | approve만 허용 | 재고 충돌용 실행 Fixture 없음 | 승인 시 AVAILABLE 검증 생성 추가 |
| 자산 정보 수정 권한 | 수정 API·규칙 없음 | 없음 | 없음 | 없음 | 지원하지 않음. 기존 랜덤 예제는 근거가 있는 자산 등록으로 이미 교체됨 |
| 자산 등록 | asset-lifecycle §자산 등록과 관리번호, asset-api §POST /assets | 없음 | 없음 | 없음 | 생성 추가, 실행 차단 |
| 중복 승인 | loan-rules §부서장 승인과 자기 승인 금지, loan-api §approve | 없음 | approve | 중복 승인용 실행 Fixture 없음 | 상태 충돌 생성 추가, 실행 범위 확대 안 함 |

확장 원칙: 확정 조건은 저장된 분석에서만 가져온다. API 명세 연결은 분석이 이미 참조한 API와 동일한 경로에 한정하며 합성 corpus의 원문·Section·UUID를 검증한다. Ground Truth와 평가 기준은 생성 입력으로 사용하지 않는다. API AllowList 및 실행 Fixture는 변경하지 않는다.
