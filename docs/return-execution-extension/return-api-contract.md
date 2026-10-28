# 반납 Dummy 실행 API 계약

외부 자산관리 시스템을 호출하지 않는다. 기존 `DummyApiRegistry`의 in-process dispatch에 두 항목을 추가했다. 일반 사용자가 직접 호출하는 별도 /dummy HTTP Controller나 범용 URL 실행기는 만들지 않았다.

| Registry ID | 기존 명세의 Method / Endpoint | 지원 요청 / 응답 |
|---|---|---|
| API-RETURN-CREATE | POST /loans/{loanId}/returns | accessoriesReturned(boolean), note(string 선택). 정상 201 `{returnId,status:INSPECTION_PENDING}`, 중복 409 RETURN_ALREADY_REQUESTED, 무권한 403 ACCESS_DENIED |
| API-RETURN-INSPECT | POST /returns/{returnId}/inspection | result=DAMAGED, 증빙 누락. 명세에 명시된 400 VALIDATION_ERROR만 실행 지원 |

`ReturnExecutionAdapter`는 ReturnRequest/ReturnResponse/InspectionRequest/ErrorResponse DTO를 사용한다. Registry는 입력 필드, UUID, 템플릿/모드/version, 역할, body 자료형을 검증하고 Adapter는 닫힌 업무 동작만 처리한다. 존재하지 않는 API나 임의 URL은 dispatch되지 않는다.

검사 성공의 HTTP 상태는 합성 명세에 없다. PASSED→AVAILABLE / DAMAGED→MAINTENANCE 규칙은 분석·TC 생성에 존재하지만 성공 자동 실행은 미지원으로 유지했다. 이를 해결하려고 RAG 문서나 GT를 수정하지 않았다.

## 실제 HTTP 진입점

- 기존 `GET /api/test-cases/{id}/execution-eligibility`: 최종 실행 가능 여부, 차단 사유, 지원 Fixture 목록 및 contract version 반환
- 신규 `POST /api/test-cases/{id}/return-execution-setup`: body는 reviewRevision과 fixtureProfile만 허용. 이미 검증된 원본 템플릿을 확인하여 검토본의 입력/전제/기대결과를 준비하고 revision 증가 + DRAFT 처리. 실행·자동 승인은 하지 않음
- 기존 `POST /api/test-cases/{id}/approve`: 현재 revision의 별도 개발자 승인
- 기존 `POST /api/test-cases/{id}/executions`: body는 계속 금지. React는 If-Match에 선택한 revision을 전달하며 불일치는 409 REVIEW_CONFLICT. 기존 MCP의 ID-only 계약은 현재 승인 revision을 transaction lock 아래 읽어 실행
- 기존 실행 GET/이력 조회 API 유지

생성 정책 JSON의 AllowList와 15개 TC·원본 policyHash는 변경하지 않았다. 런타임 Registry AllowList만 기존 자산 조회/대여 승인에 반납 2개를 추가했다. 따라서 기존 TC 재생성이나 Qwen 호출 없이, 원본 근거 확인 → 명시적 실행 준비 → 재승인으로 연결할 수 있다.

## 상태 및 트랜잭션

상태 전이와 이력 수 비교는 실행별 메모리 안에서 원자적으로 완료한다. 자산/대여 업무 DB에는 쓰지 않는다. DB transaction은 현재 승인 revision 잠금 및 기존 `app.test_execution` 감사 결과 저장에만 사용한다. 정상 접수는 새 합성 반납 1건과 INSPECTION_PENDING을 만들며 자산은 ON_LOAN으로 유지한다.

실제 명세에 대여 이력 완료 상태명이나 변경 시점은 없다. loanStatus=ACTIVE는 초기 Fixture의 관측값이며 임의의 RETURNED 상태를 추가하지 않았다. returnStatus=NONE은 반납 건 부재를 나타내는 내부 관측 표식이다. 검사 완료 중복 Fixture의 inspectionCompleted=true는 완료 여부를 나타내고 returnStatus는 접수 시 선언된 상태를 보존한다.
