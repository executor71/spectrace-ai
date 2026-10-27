# Baseline과 변경안

V12 Flyway가 app.change_impact, app.change_impact_analysis, app.change_impact_review를 추가한다. 기존 app/rag/evaluation 권한을 유지하고 신규 세 테이블의 app_user UPDATE/DELETE를 제거한다. snapshot/결과/검토본은 append-only다.

Baseline은 Requirement 전체, 저장 Analysis와 Evidence의 document/chunk/version, TC batch와 review revision, 정책 registry 15개 plan 및 hash, 실행 이력을 복사한다. API 계약은 분석 Evidence/API_SPEC의 문서 버전·chunk 참조로 보존한다. 생성 시점을 capturedAt으로 기록한다. 서버 정렬 직렬화 SHA-256이 revision이며 숫자 Requirement revision을 발명하지 않는다. 조회 snapshot은 repeatable-read, 변경안 저장은 repeatable-read에서 revision을 재검증한다.

지원: 저장된 Requirement를 Baseline으로 고정하고 별도 제안과 비교. 동일 Requirement의 여러 시점 Snapshot 비교는 별도 변경안/스냅샷을 통해 추적 가능하나 존재하지 않는 과거 숫자 revision의 조회/복원 API는 없다. 두 기존 Requirement를 직접 선택하는 전용 모드도 없으며 대상 Requirement의 내용을 변경안으로 입력하는 의미와 구분한다.

새 분석은 별도 analysisId(동일 Job ID)로 쌓인다. Baseline 최신 값은 과거 결과를 덮어쓰지 않고 baselineStale 표시와 새 Job/검토 차단에만 사용한다. 검토 중 원본 변경은 이후 재조회에서 stale로 드러나며 기존 snapshot/검토 이력은 보존한다. 새 Baseline으로 재등록해야 한다.

Graph는 Baseline 생성 시점과 분석 실행 시점이 다를 수 있다. 실제 Graph 조회 결과를 분석 결과의 graphPaths로 고정한다. Graph 동기화 중 PENDING/FAILED는 완료로 오인하지 않고 partial 상태다. 이는 전체 데이터베이스의 분산 트랜잭션 Snapshot은 아니다.
