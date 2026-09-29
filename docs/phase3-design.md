# Phase 3 요구사항 분석

Phase 2 기준점: `docs/phase2-baseline/source.zip`, `sha256.json`. `.env` 제외.
기존 BGE-M3 모델·차원·데이터·Vector similarity SQL·Top-5 순서·점수는 변경하지 않는다.

## 실행

```powershell
docker compose config --quiet
docker compose up --build -d
```

Docker의 Ollama 0.11.10과 로컬 Qwen2.5 7B Instruct를 사용한다. 최초 시작 시 `analysis-model-init`이 모델을 받고 AI 서비스는 완료를 기다린다. 모델 캐시는 별도 볼륨이다. 호스트 JDK/Python/PostgreSQL/LLM 설치 및 외부 API 키가 필요하지 않다.
`ANALYSIS_LLM_MODEL`, `ANALYSIS_LLM_THINK`(기본 false), `ANALYSIS_LLM_TIMEOUT_SECONDS`, AI 내부 `ANALYSIS_LLM_URL`로 공급자를 설정한다. EmbeddingProvider와 LlmProvider는 별개다. 모델 교체 시 별도 검증이 필요하다.

## 처리와 저장

1. Spring이 app_user로 기존 Requirement를 조회한다.
2. AI 서비스에 ID/title/description만 보낸다. 클라이언트의 evidence나 분석 결과는 받지 않는다.
3. 원문 `title + "\n" + description`을 기존 VectorSearch에 Top-K=5로 전달한다. 변환·요약·절단·재정렬하지 않는다.
4. 검색 결과의 완전한 문장과 relatedApis metadata에 선택용 ID를 붙인다. 이는 분석용 근거 표현이며 검색 알고리즘이나 chunk를 변경하지 않는다.
5. LLM은 근거 충족 여부(SUFFICIENT/PARTIAL/NONE), 확정 조건/업무규칙/API의 ID와 미확정 항목을 내부 JSON Schema로 응답한다. NONE인데 확정/규칙/API를 선택하면 실패한다. TEST_GUIDE의 문장을 확정 조건으로 승격하지 않는다. 외부 결과는 지정된 8개 필드만 반환한다.
6. 서버가 ID 실재 여부와 문서 타입을 검사하고 확정 내용을 원문으로 복원한다. ID/score/snippet은 LLM이 작성하지 않는다.
7. Spring이 최종 Schema/ID/근거 참조를 다시 검사하고 V6의 `app.requirement_analysis`에 JSONB를 저장한다. 한 요구사항당 최신 성공 결과 1건이다.
8. 성공 시 DRAFT만 ANALYZED로 변경한다. 실패한 재분석은 기존 결과와 상태를 보존한다. 모델 대기 중에는 DB transaction을 유지하지 않는다.

V1~V5, role, schema grant, seed 및 모델 설정은 그대로다. AI에는 rag_reader 접속 정보만 있고 app/evaluation 접근이 금지된다.

## 외부 API

`POST /api/requirements/{id}/analysis`: 기존 요구사항 분석, 성공 200. 요청 body는 필요 없다.
`GET /api/requirements/{id}/analysis`: 저장된 결과와 당시 evidence, 성공 200. GET은 모델이나 검색을 재실행하지 않는다.

| 필드 | 구조/의미 |
|---|---|
| requirementId | 기존 UUID |
| confirmedConditions | `{text, chunkId}[]`; 검색 원문에서 확인된 조건 |
| ambiguousExpressions | `string[]`; 모호하거나 근거와 충돌하는 표현, 확정 사실 아님 |
| missingConditions | `string[]`; 빠진 조건 또는 검색 근거로 확인할 수 없는 조건 |
| relatedBusinessRules | `{text, chunkId}[]`; BUSINESS_RULE 원문만 |
| relatedApis | `{api, chunkId}[]`; 검색된 chunk의 relatedApis metadata만 |
| clarificationQuestions | `string[]`; 사용자 확인 질문 |
| evidence | `{documentId, chunkId, documentType, section, contentSnippet, score}[]`; 검색 순서/값 그대로 |

명시적 오류: UUID 400, 요구사항 없음 404 REQUIREMENT_NOT_FOUND, 분석 없음 404 ANALYSIS_NOT_FOUND, 입력 제한 422 ANALYSIS_INPUT_TOO_LONG, 동시 실행 429 ANALYSIS_BUSY, 응답 검증 실패 502 INVALID_ANALYSIS_OUTPUT, 모델/검색/연결 실패 503 ANALYSIS_UNAVAILABLE.
AI 내부에서는 model 오류를 ANALYSIS_MODEL_UNAVAILABLE로 구분한다.

기존 검색의 2,000자/512토큰 제한을 넘는 Requirement는 조용히 자르지 않고 422로 실패한다. 등록/조회 10,000자 제한은 유지한다.
Schema 또는 근거 참조 오류는 최대 2회 호출(재시도 1회). 모델의 내부 추론 텍스트는 응답/DB/로그에 저장하지 않는다. 네트워크/모델 timeout은 자동 재시도하지 않는다. 모델 호출 기본 300초/회, Spring 630초, UI 660초. AI worker의 분석 슬롯은 1개이며 동시 요청은 429다.

## hallucination 방지 범위

확정 사실의 자유 문장 생성을 허용하지 않고 근거 원문과 metadata에서 복원한다. 존재하지 않는 규칙 ID/API ID, 잘못된 문서 타입, 위조 evidence, 다른 requirementId, 잘못된 Schema를 거부한다. 미확정 항목이 있으면 질문이 있어야 하고 확정 조건이 없으면 근거 부족을 명시해야 한다.
Requirement 및 검색 자료는 신뢰할 수 없는 데이터로 취급하며 지시문 실행을 금지한다. 모델에게 SQL/도구 실행 권한을 주지 않는다.
이 검증은 원문 출처 일치와 구조를 보장한다. 선택한 근거의 의미상 관련성, 모든 누락 조건의 발견, 자유 텍스트 질문의 품질을 수학적으로 보장하지는 않는다. 검색되지 않은 문서의 존재 여부를 부정하지 않는다.

## 검증 재실행

```powershell
docker compose -f compose.test.yaml -p master-phase3-test up --build --abort-on-container-exit --exit-code-from backend-test
docker compose -f compose.test.yaml -p master-phase3-test down
docker run --rm --mount "type=bind,source=D:\MASTER과정,target=/work,readonly" -w /work/ai-service master-ai-service python -m unittest discover -s tests -v
python docs/phase3-evidence/scripts/phase3-live-check.py
python docs/phase3-evidence/scripts/phase3-regression.py
```

실제 분석 검증은 합성 Requirement를 새로 등록한다. 기대 결과와 검사 스크립트는 RAG corpus에 적재하지 않는다. Browser 검증은 검증 PC의 Playwright/Chrome을 이용하며 애플리케이션 실행 의존성이 아니다.
TestCase Generation/Hybrid/Reranking/Query Rewrite/LangGraph/Dummy/GraphRAG/MCP는 추가하지 않는다.

참조: [Ollama Structured Outputs](https://docs.ollama.com/capabilities/structured-outputs), [Qwen2.5 7B Instruct 모델](https://ollama.com/library/qwen2.5:7b-instruct).

분석 기본값은 `qwen2.5:7b-instruct`, `ANALYSIS_LLM_THINK=false`다. Qwen3 4B는 이 PC에서 의미 분류/형식 호환/추론 timeout 검증을 통과하지 못해 기본값에서 제외했다. 기존 BAAI/bge-m3 Embedding과는 별개의 모델이다.

기본 모호 표현(빠르게/필요한 경우/적절히/가능하면/충분히/쉽게)이 입력에 있으나 모델이 ambiguousExpressions에서 누락하면 해당 원문 표현과 판단 기준 질문을 보완한다. 업무규칙이나 실행 조건을 새로 만들지 않는다. 최종 모호 사례는 두 표현의 식별까지 검증한다.

실제 API/검색 검증 스크립트도 호스트 Python 없이 컨테이너에서 실행할 수 있다(브라우저 검증은 별도):

```powershell
docker compose run --rm --no-deps -v 'D:\MASTER과정:/work' -e API_BASE_URL=http://backend:8080 -e SEARCH_BASE_URL=http://ai-service:8000 ai-service python /work/docs/phase3-evidence/scripts/phase3-live-check.py
docker compose run --rm --no-deps -v 'D:\MASTER과정:/work' -e API_BASE_URL=http://backend:8080 -e SEARCH_BASE_URL=http://ai-service:8000 ai-service python /work/docs/phase3-evidence/scripts/phase3-regression.py
```
