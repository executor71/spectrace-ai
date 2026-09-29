# 아키텍처 결정

## 서비스 책임

- React는 입력·검토·결과 화면을 담당합니다. 이 단계에는 서비스 상태를 보여주는 화면만 있습니다.
- Spring Boot는 업무 API, 업무 데이터 변경, 사용자 승인 및 Dummy 실행 권한 검증의 최종 소유자입니다.
- Python AI Service는 vector 우선 근거 검색, 요구사항 분석, 테스트 케이스 생성과 향후 AI 평가 계산만 담당합니다. 현재는 health, DB 연결 및 Phase 2 dense vector 검색을 구현합니다. 분석과 테스트케이스 생성은 미구현입니다.
- PostgreSQL 16 + pgvector 한 인스턴스를 사용하되 `app`, `rag`, `evaluation` schema와 Repository/DB role을 분리합니다.

## 데이터 경계

| Schema | 소유/접근 | 용도 |
|---|---|---|
| `app` | Spring의 `app_user`는 업무 DML, `migration_owner`는 DDL | Requirement, AnalysisResult, TestCase, Review |
| `rag` | `rag_reader`는 SELECT만, AI Service에만 전달 | KnowledgeDocument, KnowledgeChunk, embedding, evidence 원천 |
| `evaluation` | 향후 전용 Evaluation Repository/Service와 `evaluation_reader` | Ground Truth와 Evaluation 데이터 |

DB bootstrap이 role을 생성하고 schema 권한을 부여합니다. AI Service에는 `rag_reader`만 제공하며 이 role은 `rag` 이외 schema 권한이 없습니다. Evaluation 자격 증명은 일반 AI workflow에 설정하지 않고, RAG query도 `rag` schema에 한정합니다. 따라서 Ground Truth는 검색 입력/인덱싱 대상이 아니며 일반 생성 workflow에서 접근할 수 없습니다. Evaluation 기능을 추가할 때는 별도 Repository/Service 경로로만 `evaluation`에 접근합니다.

Flyway는 별도 `migration_owner` 계정으로 DDL을 실행합니다. Spring 업무 런타임은 `app_user`를 사용하며 `app` schema 밖의 업무 데이터에 직접 접근하지 않습니다. AI Service는 `app`의 Requirement/TestCase를 읽거나 수정하지 않습니다.

## 생성 데이터 계약

`AnalysisResult` 필드: `confirmedConditions`, `ambiguousExpressions`, `missingConditions`, `relatedBusinessRules`, `relatedApis`, `clarificationQuestions`, `evidence`.

각 evidence 객체는 다음 필드를 가집니다.

```json
{
  "documentId": "uuid",
  "chunkId": "uuid",
  "documentType": "BUSINESS_RULE",
  "section": "주문 취소",
  "contentSnippet": "합성 샘플 근거 발췌",
  "score": 0.91
}
```

각 evidence는 화면에서 원본 KnowledgeDocument와 KnowledgeChunk로 추적할 수 있는 ID를 포함합니다. 테스트 케이스 category는 `NORMAL`, `EXCEPTION`, `AUTHORIZATION`, `BOUNDARY`, `BUSINESS_RULE`입니다.

## 향후 LangGraph 경계

일반 생성 graph는 `retrieve_evidence(rag only) → analyze_requirement → generate_test_cases → validate_structured_output`으로 제한합니다. Graph 입력은 Spring이 전달한 요구사항 payload와 검색된 근거뿐입니다. Evaluation 단계는 이 graph의 도구나 repository를 재사용해 Ground Truth에 접근하지 않고, 별도 Evaluation Service가 정답 데이터를 가져와 AI 평가 계산 입력으로 전달합니다.

## Phase 2 적재/검색 경계

초기 합성 Markdown은 manifest와 section 기준으로 처리합니다. LocalEmbeddingProvider는 설정된 모델을 CPU 컨테이너에서 실행하고 exporter는 SQL 파일만 만듭니다. Flyway가 migration_owner로 V4/V5를 적용합니다. 온라인 AI에는 rag_reader만 전달하며 app/evaluation credential이나 쓰기 권한은 추가하지 않습니다. 검색 기대 문서 fixture는 corpus가 아니며 evaluation schema도 적재/검색 대상이 아닙니다.
