# MCP Tool Gateway (Phase 9)

기존 REST/AI 서비스의 어댑터. DB 접근, 검색/평가/승인 로직 재구현 및 신규 분석 프롬프트가 없다.

## 실행

프로젝트 루트에서:

```powershell
docker compose -p master -f compose.yaml -f compose.phase7-local.yaml -f compose.phase8.yaml -f compose.phase9.yaml up -d --build
```

MCP Streamable HTTP: `http://127.0.0.1:8020/mcp/` (마지막 `/` 포함). Health: `/health`.
공식 Python SDK `mcp==1.26.0`의 `ClientSession` / `streamablehttp_client`를 사용한다.
독립 Client 예제와 보안/E2E/latency 검증은 `tests/e2e.py`에 있다.
로컬 Python 환경에서 requirements를 설치한 후:

```powershell
python mcp-server/tests/e2e.py --url http://127.0.0.1:8020/mcp/ --backend http://127.0.0.1:8080 --ai http://127.0.0.1:8000 --evaluation http://127.0.0.1:8090 --retrieval http://127.0.0.1:8010 --output docs/phase9-evidence
```

이 클라이언트는 기존 합성 검증 TC의 실행 기록을 추가한다. 승인/Review/Requirement는 수정하지 않는다.

## 계약

모든 Tool은 `additionalProperties: false`이다. UUID는 canonical UUID 형식만 받는다.

| Tool | 입력 | 출력 / 동작 |
|---|---|---|
| search_knowledge | query(1~2000, 공백 제외), topK(1~5, 기본 5), strategy(VECTOR/HYBRID, 기본 VECTOR) | strategy, hits(documentId/chunkId/documentType/section/contentSnippet/rank/score) |
| analyze_requirement | requirementId | analysis(기존 AnalysisResult 그대로), analysisSource(SAVED/GENERATED) |
| get_test_cases | requirementId | 기존 batch + 각 TC의 Phase 7 실행 판정 |
| get_evaluation_result | requirementId | retrievalMetrics, testScenarioCoverage, testCaseValidity, missingScenarios, evaluationMetadata |
| execute_approved_test | testCaseId | 기존 execution JSON 그대로: PASS/FAIL/ERROR, expected/actual/mismatches 등 |

분석은 저장본을 먼저 조회하고 없을 때만 기존 POST 분석 API를 사용한다. 조회 전용 Tool로 표시하지 않는다.
AnalysisResult는 이미지 빌드 시 기존 `ai-service/app/analysis_models.py`를 직접 복사하여 JSON Schema를 생성한다.
get_test_cases는 생성 당시 executable을 generationExecutable로 보존하며, 현재 executable/fixtureReady/executionEligible은 기존 execution-eligibility API 결과다. review와 evidence는 유지한다.
HYBRID의 score는 기존 fusionScore이며 VECTOR cosine score와 척도가 다르다. Reranker는 이 Gateway에서 제외한다.
평가 출력은 명시한 필드만 선택하며 raw Ground Truth, snapshot, dataset, 판정 규칙을 노출하지 않는다.

읽기 전용 Resource: `requirement://{requirementId}`. 원문과 현재 상태, analysisExists, testCaseCount, reviewSummary를 반환한다.
Tool 실패는 MCP CallToolResult `isError: true`와 `errorCode`, `requestId`를 반환한다. 잘못된 Resource는 MCP 표준 오류를 반환한다.

## 경계와 계측

고정된 4개 내부 HTTP destination만 사용한다. 호출자가 URL/endpoint/method를 지정할 수 없고 redirect를 따라가지 않는다.
execute_approved_test는 body 없이 기존 Phase 7 POST 실행 API만 호출한다. 승인·executable·fixtureReady·AllowList 검사는 기존 서버가 매번 수행한다.
임의 Tool, shell, SQL, 인터넷 Tool은 없다. 검색 query의 명령문/URL은 검색 데이터이며 실행하지 않는다.
컨테이너는 DB 자격증명/볼륨 없이 UID 10001, read-only root, cap_drop ALL로 실행한다. 로컬 loopback 포트와 Host/Origin allowlist를 사용한다.
OAuth/다중 사용자 인증이 없는 로컬 합성 PoC이며 공개 인터넷 서비스로 배포하지 않는다.

각 Tool 호출을 JSON 로그로 기록한다: toolName/requestId/startedAt/durationMs/resultStatus/downstreamService/errorCode.
resultStatus는 Tool 호출 성공/실패이며 Dummy PASS/FAIL은 응답의 result이다. 전체 입력/출력/프롬프트/Ground Truth는 기록하지 않는다.
통계는 테스트 클라이언트가 측정한다. 실행 Tool 자동 재시도는 없다(응답 유실 시 기존 실행 이력 API로 확인).

공식 SDK 근거: https://github.com/modelcontextprotocol/python-sdk/tree/v1.26.0
