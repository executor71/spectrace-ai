# API 계약 및 단계

## 서비스 health (현재 구현)

| 서비스 | Method | Endpoint | 확인 항목 |
|---|---|---|---|
| Spring Boot | GET | `/actuator/health` | 애플리케이션 및 datasource |
| Python AI Service | GET | `/health` | 애플리케이션 및 `rag_reader` DB 연결 |

## 사용자 API (후속 구현)

| Method | Endpoint | 책임 |
|---|---|---|
| POST | `/api/requirements` | 요구사항 등록, Spring 업무 데이터 저장 |
| POST | `/api/requirements/{id}/analysis` | AI Service 분석/TC 생성 요청 후 결과 저장 |
| GET | `/api/requirements/{id}` | 요구사항 조회 |
| GET | `/api/requirements/{id}/analysis` | 분석 JSON 및 evidence 조회 |
| GET | `/api/requirements/{id}/test-cases` | 생성된 TC 초안 조회 |

이 단계에서는 위 사용자 API를 구현하지 않습니다. Review, Evaluation, Dummy Execution endpoint도 후속 단계입니다.

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
