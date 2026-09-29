# API 계약 및 단계

## Phase 1: Requirement 등록·조회

두 API는 Spring Boot가 app_user로 app.requirement에 접근한다. 인증/승인 및 후속 AI 기능은 이 단계의 범위가 아니다.

### POST /api/requirements

Content-Type: application/json

```json
{"title":"주문 취소 조건 변경","description":"배송 시작 전 주문만 취소할 수 있습니다."}
```

- 제목과 내용은 필수이며 양끝 공백 제거 후 검증한다. 공백만 있는 문자열은 거부한다.
- 제목 최대 200자, 내용 최대 10,000자(Java 문자열 길이 기준).
- id는 서버 UUID, status는 DB 기본값 DRAFT, createdAt은 DB 생성시각(ISO 8601 UTC)이다. 클라이언트가 상태를 지정할 수 없다.
- 성공: HTTP 201, Location: /api/requirements/{id}. 응답 본문은 아래 객체.

```json
{
  "id":"00000000-0000-4000-8000-000000000001",
  "title":"주문 취소 조건 변경",
  "description":"배송 시작 전 주문만 취소할 수 있습니다.",
  "status":"DRAFT",
  "createdAt":"2026-09-29T12:00:00Z"
}
```

### GET /api/requirements/{id}

저장된 객체를 HTTP 200으로 반환한다. 없는 UUID는 404, UUID 형식 오류는 400이다. 목록/수정/삭제 endpoint는 이번 범위가 아니다.

### 오류 형식

```json
{"code":"VALIDATION_ERROR","message":"입력값을 확인해 주세요.","fieldErrors":{"title":"제목을 입력해 주세요."}}
```

| HTTP | code | 상황 |
|---|---|---|
| 400 | VALIDATION_ERROR | 누락/공백/최대 길이 초과 |
| 400 | INVALID_JSON | 파싱할 수 없는 JSON 또는 요청 본문 누락 |
| 400 | INVALID_ID | 잘못된 UUID |
| 404 | REQUIREMENT_NOT_FOUND | 해당 ID 없음 |
| 405/415 등 | HTTP_{status} | 지원하지 않는 메서드/미디어 타입 등 |
| 500 | INTERNAL_ERROR | 내부 오류; SQL/stack trace는 응답에 노출하지 않음 |

## Phase 0 health (유지)

- Spring Boot: GET /actuator/health
- AI Service: GET /health
- React의 /api는 backend로, /actuator와 /ai-health는 기존 health 경로로 프록시한다.

## 후속 기능 (미구현)

분석, RAG, Embedding, 테스트케이스 생성, Evaluation, Dummy API 실행, GraphRAG/MCP는 구현하지 않았다. 아래 AI 계약은 향후 설계 문서이며 동작하는 endpoint가 아니다.

## 내부 AI 계약 (후속 구현)

`POST /internal/v1/analyze` 입력은 `{ "requirement": { "title": "...", "description": "..." } }`입니다. 출력은 다음 JSON 구조로 고정합니다.

```json
{
  "analysis": {
    "confirmedConditions": [],
    "ambiguousExpressions": [],
    "missingConditions": [],
    "relatedBusinessRules": [],
    "relatedApis": [],
    "clarificationQuestions": [],
    "evidence": []
  },
  "testCases": [
    {
      "category": "NORMAL",
      "title": "합성 샘플 테스트",
      "preconditions": [],
      "steps": [],
      "expectedResult": "...",
      "executable": false
    }
  ]
}
```

Evidence 객체는 `documentId`, `chunkId`, `documentType`, `section`, `contentSnippet`, `score`를 포함합니다. 허용 category는 `NORMAL`, `EXCEPTION`, `AUTHORIZATION`, `BOUNDARY`, `BUSINESS_RULE`입니다. AI Service는 사용자 승인이나 업무 상태를 변경하지 않으며, Dummy 실행 권한 판정도 수행하지 않습니다.
