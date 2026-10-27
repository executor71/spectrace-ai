# 조건 대응 비교

새 LangGraph 흐름: retrieve → diff → impact. 기존 SearchRequest/SearchHit, get_search, LocalLlmProvider, Python 공유 slot을 재사용한다. 기존 분석의 confirmedConditions를 Baseline으로 사용하여 분석을 다시 호출하지 않는다. 실제 모델 호출은 diff 1회이며 자동 repair 재호출 없음.

Structured Output은 beforeIndex, optional beforeText, afterText, ADDED/REMOVED/MODIFIED/UNCHANGED/UNCERTAIN, rationale만 허용한다. 인덱스는 Baseline 범위를 벗어날 수 없고 인용문은 각각 원문에 실제 포함되어야 한다. API/TC/Cypher 등 임의 추가 필드는 거부한다. 복합 기준 조건은 여러 atomic 대응에서 같은 index를 참조할 수 있다. 모델이 누락한 기준 조건은 UNCERTAIN, 기준 근거가 없는 대응도 UNCERTAIN이다.

EXACT_TEXT는 원문 동일, SEMANTIC_PROPOSAL은 모델 의미 대응 제안, UNCERTAIN은 확정 불가이다. 수치 확률이 아니며 모두 requiresConfirmation=true, businessPolicyApproved=false. 신규 역할은 승인된 RAG 규칙으로 바뀌지 않는다. 모호한 삭제와 제안에서의 단순 생략은 구분하도록 지시하나 의미 분류 오류는 여전히 가능하므로 개발자 검토가 필수다.

검색 결과는 기존 근거와 함께 evidenceRefs로 저장하며 신규 정책을 입증했다는 뜻이 아니다. 새 Expected Result를 생성하지 않는다. schema/원문/참조 오류는 실패, timeout은 별도 오류, Graph 실패는 검색 근거를 보존한 PARTIAL_REVIEW_REQUIRED로 명시한다.

대표 실모델은 유지된 자기 승인 금지를 REMOVED로 오분류했다. 이를 숨기지 않고 최초 원본 결과를 보존했다. `condition_atoms.py`의 제한적 원문 대조는 명시된 긍정 승인 주체와 자기 승인 금지를 분리한다. 전부 인식되는 승인 Baseline에서 삭제 제안과 실제 유지 원문이 모순될 때만 원문 기반 atomic 대응으로 조정한다. 금지 해제/승인 불허는 유지 허용으로 단정하지 않는다. SOURCE_RULE_ATOM도 확정 정책이 아니라 검토 후보이며 다른 업무의 일반 의미 파서가 아니다.

동일 불변 변경안/Baseline/정책 hash에 이전 성공 비교가 있으면 검증된 modelConditionChanges를 재사용하여 RAG/Graph를 갱신하고 재검증한다. 최초 모델 출력과 재사용한 analysisId, modelVersion, llmCallCount를 보존한다. 대표 사례는 Qwen 1회, 그 응답 재사용 Job 1회(모델 호출 0회)다. 최초 결과는 수정하지 않고 새 analysisId로 쌓았다. 설정 모델만 변경한 경우에도 기존 비교 재사용이 우선되며 새 모델 호출을 원하면 새 변경안을 만들어야 한다.
