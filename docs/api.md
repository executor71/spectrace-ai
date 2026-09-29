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

## Phase 2: 내부 Vector 검색

POST /internal/v1/search (AI Service :8000)

요청: {"query":"반납 파손 처리 규칙","topK":5}. query는 공백 제거 후 1~2000자, topK는 정수 1~10이다. 모델 설정의 token 한도 초과도 422로 거부한다. schema 등 정의되지 않은 필드는 거부한다.

응답: documentId/chunkId/documentType/section/contentSnippet/score/domain/version/relatedApis 객체 배열. score는 cosine similarity, chunk별 내림차순이며 같은 문서의 여러 section이 반환될 수 있다. 모델/corpus 불일치는 503 CORPUS_NOT_READY, 내부 오류는 세부정보 없는 503 SEARCH_UNAVAILABLE이다. 모델 초기화는 첫 요청에서 수행한다.

[실제 검색 결과](phase2-result.md)

## Phase 3: 근거 기반 요구사항 분석

`POST /api/requirements/{id}/analysis`: 기존 요구사항으로 Vector 검색과 로컬 LLM 분석을 수행하고 저장한다. 성공 200.
`GET /api/requirements/{id}/analysis`: 저장된 결과와 당시 evidence를 조회한다. 성공 200.

외부 결과는 requirementId/confirmedConditions/ambiguousExpressions/missingConditions/relatedBusinessRules/relatedApis/clarificationQuestions/evidence의 8개 필드이다.
AI 내부 endpoint는 `POST /internal/v1/requirement-analysis`, 입력은 `{requirementId, title, description}`이다. AI는 app DB를 조회하지 않는다.

세부 타입, 근거 검증과 오류 코드는 [Phase 3 설계](phase3-design.md), 기계 판독 계약은 [JSON Schema](phase3-analysis.schema.json)를 따른다.

## 후속 기능 (미구현)

TestCase Generation, Hybrid Search, Reranking, Query Rewrite, LangGraph, Evaluation, Dummy API 실행, GraphRAG/MCP는 구현하지 않았다.
