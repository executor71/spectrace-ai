# 실제 Graph 영향 후보

고정 주소 Graph Service의 기존 `find_requirement_context`만 호출한다. 기존 bounded query의 Requirement→Rule→Api→TC→Execution 및 Evidence 경로를 그대로 사용한다. 외부 Cypher, 새로운 Graph 노드, 임의 URL, MCP allowlist 변경 없음.

API 후보는 실제 응답 relatedApis에서만 만든다. method/path/id, 관련 BusinessRule IDs, 경로 근거 chunk IDs, 확인 가능한 계약 버전, 조건 IDs, 실제 graphPaths를 보존한다. 새로운 역할과 연결된 구체 경로가 없는 경우 Baseline에 연결된 API를 넓은 영향 후보로 제시하며 관계를 새로 발명하지 않는다. 이 때문에 false positive 후보가 있을 수 있다.

상태: Graph AVAILABLE + 관계 없음은 정상 빈 결과, NOT_SYNCED/GRAPH_SYNC_PENDING/SYNC_PENDING은 대기, SYNC_FAILED/GRAPH_SYNC_FAILED는 실패, UNAVAILABLE은 연결 실패다. 후자는 분석 전체 완료로 표시하지 않고 PARTIAL_REVIEW_REQUIRED다. API는 POTENTIALLY_AFFECTED, REVIEW_REQUIRED(정책 버전 불일치), UNKNOWN(조건 불확실), NO_EVIDENCED_IMPACT(근거상 영향 미발견)를 구분한다.

원본 Graph 경로와 조회 시점 결과는 분석에 저장한다. 현재 Graph를 추가 조회하는 UI 영역과 분석 시점 관계를 분리 표시한다. Graph 평가셋/기존 결과는 이 기능의 성능 근거로 재사용하지 않는다.
