# Phase 15 구현 전 실제 아키텍처 점검

작업 브랜치: `phase15/change-impact-analysis`, 시작 HEAD `6e4a095`.
기존 미커밋 작업은 `preexisting-worktree.json`에 경로/해시를 기록하고 같은 HEAD에서 브랜치만 생성하여 보존했다. origin HEAD도 동일하며 원격 읽기 연결 성공. 자동 커밋/Push 없음.

React/Vite → Spring REST → PostgreSQL app 스키마가 Core 저장 경로다. Requirement는 수정 Revision 필드가 없는 생성형 데이터이며 분석 JSON 및 TC 검토본은 별도 저장된다. 따라서 Phase 15 Baseline Revision은 존재하지 않는 정수 Revision을 만들어내지 않고 저장 스냅샷의 SHA-256 토큰으로 정의한다. 서로 다른 Requirement 비교는 명시적 Baseline+분리된 변경안 비교로 지원하고, 과거에 저장되지 않은 Requirement Revision 복원은 지원하지 않는다.

Spring AnalysisClient → Python FastAPI → AnalysisService 및 LocalLlmProvider → 로컬 Ollama Qwen2.5 7B. 점검한 기존 분석 코드에는 명시적 StateGraph가 없고 langgraph 의존성만 설치되어 있었다. Phase 15는 해당 의존성으로 별도 작은 StateGraph를 구성하고 기존 검색/Provider를 재사용한다. Python의 공유 semaphore와 Spring AnalysisGate advisory lock, 단일 JobWorker/JobStore가 기존 동시성 경계다. 새 무제한 Worker를 만들지 않고 job type을 확장하여 lease/token/queue-limit/재시작 복구/실패 시 정상 결과 보존을 재사용한다.

RAG는 rag_reader 권한의 기존 벡터 검색/Hybrid 검색을 사용한다. policy registry는 contracts/test-case-policy.json의 15개 plan과 hash, canonical Evidence를 검증한다. TC는 불변 생성본과 검토 revision/approval 및 Dummy execution 기록이 분리된다. 반납/검사 Dummy 확장은 기존 미커밋 코드에 존재하며 기존 회귀 테스트에 포함되어 있다. Phase 15는 해당 실행 게이트를 호출하거나 수정하지 않는다.

Graph는 React→Graph 조회, Graph→Spring 읽기 스냅샷 자동 동기화 구조다. Neo4j는 고정 label/relation과 bounded query만 허용하며 MCP도 기존 read-only allowlist를 유지한다. 사전 점검 대상 반납 요구사항은 HTTP 200 SYNCED/PARTIAL, 10 nodes/20 edges/4 TC이고 실행 이력은 없다. 기존 Graph 오류 복구가 동작한다. Phase 15는 실제 Graph 조회 결과를 분석별로 동결하고 조회 실패와 빈 관계를 구분한다.

app/rag/evaluation DB 권한 분리와 기존 Ground Truth를 유지한다. 기존 Excel은 XLSX 작성/문자열 셀로 수식 주입을 방어한다. OTel은 Spring Tracing 및 Python workflow_otel을 통해 Jaeger로 전송되며 프롬프트 본문을 span에 기록하지 않는다.

추가할 경계: 불변 Baseline+변경안 저장, change-impact analysis/review 이력, 공유 Queue의 CHANGE_IMPACT_ANALYSIS job type, 별도 Python 조건 대응 LangGraph(원문 ID 검증 및 불확실성), 실제 Graph API/TC 후보 매핑, React 워크벤치, 문자열 셀 Excel, 별도 평가 fixture/결과. 기존 Requirement/정책/TC/Graph 노드를 제안에 따라 수정하는 경로는 만들지 않는다.

권한 한계: 현재 앱에는 로그인/사용자 principal 기반 인증 체계가 없다. 로컬 합성 워크스페이스와 기존 HTTP 접근 경계를 그대로 사용하며 실제 사용자 인증이 있는 것처럼 표시하지 않는다. 검토자 이름은 감사용 자기 기입이며 인증된 신원 증명이 아니다. 신규 기능도 임의 URL/임의 Cypher/실행 권한을 제공하지 않는다.

직전 검증: 자동 테스트 337건, React 빌드, 실제 Chrome Graph/장애 복구 통과. Phase 15 변경 후 별도 회귀를 다시 수행한다. 기존 Graph GQ13 음성 문항의 범위 충돌은 기존 보고서대로 보존한다.
