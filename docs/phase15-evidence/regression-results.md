# 자동·통합·브라우저 검증

최종 자동 테스트: Java **158건**, Python **219건**, 기존 frontend 단위 **5건**, 합계 **382건 통과**.

Python: AI 99(신규 조건 비교/가드/캐시 23 포함), retrieval 27, evaluation metrics 22, evaluation API 12, MCP 18, Graph projection/refresh 28, Graph 분석 4, observability 9. Java는 기존 141 및 Phase 15 저장/검토/보안/캐시 16, 공유 Worker 분기 1을 포함한다. `regression-results.json` 및 OS 임시 폴더 spectrace-phase15의 backend-complete.log/junit에서 확인한다. backend-complete는 158 tests, Failures 0, Errors 0, Maven BUILD SUCCESS이며 테스트 DB는 별도 tmpfs PostgreSQL이다.

초기 검토 통합 테스트는 불변 테이블에 대한 FOR UPDATE 권한 오류로 실패했다. UPDATE 권한을 부여하지 않고 advisory transaction lock으로 수정한 뒤 통과했다. 캐시 테스트 Fixture의 policyHash 누락도 실제 계약에 맞게 수정했다. Windows sandbox의 Node spawn EPERM은 권한 있는 동일 테스트 실행으로 해소됐다. 실패했던 실행을 최종 통과로 혼동하지 않는다.

## 필수 시나리오 대응

| 시나리오 | 확인 방식 |
|---|---|
| Baseline/변경안 저장, 잘못된 기준·Revision, 불변 스냅샷 | 실제 API + Java 통합 |
| QUEUED/RUNNING/SUCCEEDED | 실제 Qwen Job에서 세 상태 관측 |
| ADDED/UNCHANGED/MODIFIED/REMOVED/UNCERTAIN | 고정 Provider 단위; 실제 모델 오분류는 원문 보정 재검증 별도 기록 |
| Evidence/Graph/API/TC 후보 | 실제 저장 Baseline·Neo4j·대표 Job 결과 |
| 신규 TC 제안/템플릿 미지원/실행 금지 | Python 고정 Fixture + 실제 결과 |
| 검토 이력·revision·stale·위조 ID 차단 | Java 통합 + Chrome 실제 저장/재조회 |
| XLSX/수식 주입 방어 | POI 통합 + 실제 Chrome 다운로드 7 sheet / formula 없음 |
| 근거 부족/존재하지 않는 조건 참조/임의 API 필드/JSON 오류 | Fake Provider 검증 실패 테스트 |
| Graph 실패와 정상 빈 결과 | Fake Graph 응답 테스트; 기존 실제 Graph 장애/복구 증거는 graph-sync-repair에 보존 |
| LLM timeout/모델 점유/중복 Queue/공유 동시성 | Fake Provider/기존 Job Store·Worker 테스트 |
| 오래된 분석·원본 변경·정책 hash 불일치 | Java/Python 고정 Fixture |
| 서비스 재시작 | 기존 lease 만료 복구·fencing 통합; 실모델 실행 도중 재시작은 수행하지 않음 |
| Graph 재동기화 중 요청 | PENDING/FAILED 분리 및 bounded 읽기 로직; 실시간 동시 부하/경합 스트레스 테스트는 미수행 |
| 정상 결과 후 재분석 실패 | Java 통합에서 timeout 후 이전 analysisId 보존 |
| Ground Truth 권한 | app_user의 evaluation USAGE 없음, 기존 파일/정책 hash 보존 |
| 기존 TC 검토·Dummy·반납·Graph·MCP | 기존 전체 Java/Python 회귀 |

실제 Chrome: Phase 15 결과/검토/Excel/모바일 9개 확인 (`browser-results.json`), 기존 8개 업무 화면×3 해상도 24개 표시 확인(페이지 오류 0/변경 요청 0), 랜덤 예제 desktop/mobile 2개 시나리오 통과(API 고정 응답). 브라우저는 installed Chrome의 headless 채널이며 시각적 클릭과 실제 HTTP를 검증했다.

Jaeger에서 create/baseline_load/condition_diff/rag_retrieve/graph_traverse/tc_match/review/export 8종 실제 span을 확인했다. 프롬프트나 Ground Truth를 태그에 넣지 않는다. 증거 `preservation-and-traces.json`.

React TypeScript/Vite 및 Docker frontend 빌드 성공. 기존 Core 요구사항/분석/TC JSON은 대표 검증 전후 동일. 기존 Ground Truth 2종·Graph 평가 결과 2종·정책 파일의 hash/내용 보존을 확인했다. Phase 15용 평가 파일은 별도 폴더에만 생성했다.
