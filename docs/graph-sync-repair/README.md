# Knowledge Graph 동기화 오류 수정 결과

대상: `c9e5d1d8-6de2-487e-8ae6-9cf6c7b99eae` — 대여 자산 반납 및 상태 변경 검증.

## 원인과 실제 진단

- Docker Graph Service 및 Neo4j는 실행 중이며 `/health`는 HTTP 200 UP이었다. Neo4j 로그에서도 정상 기동을 확인했다.
- PostgreSQL 직접 SELECT 결과 요구사항은 ANALYZED, 분석 조건 4건, 저장 TC 4건, 해당 비동기 Job은 SUCCEEDED 1건이었다.
- React/Vite 경유 및 Graph 직접 POST `/api/graph/find_requirement_context` `{requirementId: ...}` 모두 수정 전 HTTP 404 `GRAPH_ENTITY_NOT_FOUND`였다.
- Neo4j에는 기존 Phase 11 요구사항 3개만 있었다. 대상 요구사항 및 대상 소유 관계는 없었다. 전체 GraphEntity 190개, 관계 220개였다.
- 기존 동기화는 `python -m app.sync` 운영자 CLI만 지원하고 `scope.json`의 3개 ID만 읽었다. 비동기 분석 성공, TC 생성·검토·실행 후 자동 반영 지점이 없었다.
- Spring→Graph 통신 코드는 존재하지 않는다. React→Graph 조회와 Graph→Spring 읽기 REST 구조다. Spring 연결 실패가 원인이 아니다.
- API 정본 매핑도 대여 승인·자산 조회 2종만 포함하여 반납·검사 TC의 API/Rule 검증 관계를 만들지 못했다.
- 기존 조회는 부분 그래프를 허용했으나 UI가 서비스 장애와 미동기화를 같은 안내로 표현했다. 전체 4-hop 실행 경로 조회도 누락되어 있었다.

## 수정과 복구

- `app/refresh.py`: Graph 서비스 생명주기에 독립 백그라운드 작업을 연결했다. 기존 Core 대시보드에서 요구사항을 발견하고 저장된 분석·TC·검토 revision·실행 이력을 읽는다. 변경된 스냅샷만 기존 projection으로 반영한다. 한 순회 완료 후 10초 간격이며 처리 시간에 따라 반영 지연이 더해질 수 있다.
- Job 성공이나 TC 저장 완료가 다음 REST 스냅샷에서 관측되면 갱신한다. Core 트랜잭션에서 Graph를 호출하지 않으므로 Graph 장애는 Core 작업을 차단하지 않는다. 요청별 실패는 격리하고 다음 순회에 자동 재시도한다.
- `source.py`: 운영자 CLI도 고정 scope와 실제 저장 요구사항의 합집합을 발견한다. 기존 고정 scope는 보존했다.
- `store.py`: 기존 전역 삭제를 제거했다. 동기화 대상 요구사항이 소유한 오래된 관계만 트랜잭션 내 교체하며 공유 정본·다른 요구사항·기존 노드는 보존한다. 기존 ID 기반 MERGE 및 전역 쓰기 lock을 유지한다. 연결되지 않은 과거 노드는 삭제하지 않는다.
- `model.py`: 실제 DummyApiRegistry 및 합성 `knowledge/documents/return-api.md`와 일치하는 `API-RETURN-CREATE` (`POST /loans/{loanId}/returns`), `API-RETURN-INSPECT` (`POST /returns/{returnId}/inspection`)를 추가했다. 고정 RAG 정본의 API_SPEC와 BUSINESS_RULE metadata, 저장 TC의 Evidence document/chunk ID 및 현재 endpoint 일치 검증을 그대로 적용한다.
- `queries.py`: 해당 요구사항의 TC만 포함하는 Rule→Api→TC→Execution 4-hop 경로를 추가했다. 실행 이력이 없는 기존 부분 조회도 유지한다.
- `main.py`, `KnowledgeGraph.tsx`: 연결 실패, 동기화 대기, 동기화 실패, 완료/관계 없음, 부분 관계, 정상 상태를 구분한다. 실패 시 마지막 조회 자료를 유지한다. 자동 동기화 재시도를 안내하며 기존 조회 버튼으로 다시 확인한다. 관리자 쓰기 API를 추가하지 않았다.

재기동한 Graph 서비스가 대상 요구사항을 자동 복구했다. Vite 경유 실제 응답은 HTTP 200, SYNCED/PARTIAL, 노드 10개·관계 20개·TC 4개다. 현재 대상 TC는 DRAFT이고 저장된 Execution은 0건이다. 따라서 대상에 실행 노드를 임의 생성하지 않으며 실제 실행 이력이 있는 기존 요구사항에서는 4-hop 경로가 조회된다.

## 검증

- Java 전체 141건 통과: Job Store/Worker, 분석, TC 생성·정책, 검토, Dummy 실행 및 반납 회귀 포함. 별도 tmpfs PostgreSQL 테스트 DB 사용. Maven BUILD SUCCESS / 컨테이너 exit 0 확인.
- Python 196건 통과: AI 76, retrieval 27, evaluation metrics 22, evaluation API 12, MCP 18, Graph projection/refresh/HTTP 28, Graph 분석 4, observability 9. 합계 Java 포함 **337건 통과**.
- 신규 Graph 테스트는 저장 스냅샷의 분석→TC 생성→승인 revision→실행 변화 감지, 동일 입력 건너뛰기, 실패 재시도·격리, 실행 없는 부분 그래프, HTTP 장애 상태 구분, 반납 정본 일치/위조 endpoint 배제를 검증한다. 이 단계별 변경 테스트는 mock 기반이며 운영 대상의 승인·실행 기록을 새로 만들지 않았다.
- 실제 Neo4j에서 기존 요구사항 3개와 대상 요구사항 조회 성공. 대상만 두 번 재동기화 전후 semantic export 완전 동일, 중복 노드·관계 없음, 다른 요구사항 보존. 전체 노드 284개, 관계 451개.
- 실제 Chrome(headless Chrome 채널)에서 대상 Graph 표시, 여섯 UI 상태, 기존 자료 유지, Graph 컨테이너 실제 중단→연결 실패→재시작→조회 정상화, 모바일 390px 가로 넘침 없음 확인. 일부 오류/완료 상태는 응답 대체로 검증했고 연결 중단·복구와 대상 부분 Graph는 실제 서비스로 검증했다.
- 프론트엔드 TypeScript/Vite 빌드 및 프론트엔드 Docker 빌드 성공. 수정 UI를 실행 컨테이너에도 반영했다.
- PostgreSQL 원본 요구사항·분석·TC의 브라우저 검증 전후 JSON 동일. Ground Truth 해시 동일. 기존 Phase 11 평가 파일, RAG, 평가셋 수정 없음.
- 동일 고정 평가 20문항 재실행: 양성 entity recall/path accuracy/multi-hop success 모두 1.0 유지. 음성 정확도는 1.0→0.8이다. GQ13이 “반납 Rule에는 대표 API/TC가 없음”을 전제로 한 옛 범위의 음성 문항인데 실제 반납 관계를 지원하면서 기대와 달라졌다. Ground Truth나 기존 지표 파일을 바꾸지 않고 별도 평가 결과와 이 차이를 보존했다. 전체 평가가 모두 통과했다고 해석하면 안 된다.

증거: `diagnostic-results.json`, `live-results.json`, `regression-results.json`, `browser-results.json`, `multi-hop-evaluation.json`, `hybrid-vs-graph-comparison.json`.
Chrome 스크린샷은 OS 임시 폴더의 `spectrace-graph-desktop.png`, `spectrace-graph-mobile.png`에 저장한다. 원시 테스트 로그도 OS 임시 폴더에만 저장한다.

## 변경 파일과 한계

제품 코드: `graph-service/app/main.py`, `model.py`, `queries.py`, `source.py`, `store.py`, 신규 `refresh.py`, `frontend/src/KnowledgeGraph.tsx`.
테스트: `graph-service/tests/test_projection.py`, 신규 `test_refresh.py`, `live_refresh.py`. 실행·증거 문서는 이 폴더에 별도로 저장한다.

현재 정본 매핑은 승인·자산 조회·반납·검사 4개 API다. 이 밖의 endpoint는 기존처럼 검증 관계 생성을 생략한다. 근거가 없는 Rule/Evidence/Api 관계와 아직 저장되지 않은 Execution은 지원하지 않는다. 동기화는 즉시성이 아닌 주기적 최종 일관성 방식이며 상태 캐시는 프로세스 재시작 후 다시 구성된다.

기존 미커밋 변경사항 보존. Git 스테이징·커밋·Push, DB 초기화, Neo4j 전체 삭제, Phase 15 개발은 수행하지 않았다.
