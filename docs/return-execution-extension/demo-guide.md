# 반납 실행 시연

실제 서비스: http://localhost:5173/#requirements . Git 커밋/Push는 수행하지 않았다.

1. 요구사항 ID `c9e5d1d8-6de2-487e-8ae6-9cf6c7b99eae`를 조회한다.
2. 저장된 Phase 14 성공 Job과 분석을 확인한다. 이번 시연은 기존 generationId와 TC를 재사용했으며 Qwen 호출은 0회다.
3. 테스트 실행·결과 확인에서 정상 반납 TC를 선택한다. `반납 실행 Fixture 준비`에서 정상 계약을 선택하여 준비한다.
4. DRAFT로 변경되고 실행 버튼이 차단되는지 확인한다. 검토·승인 화면에서 Expected·전제·합성 역할을 확인하고 현재 revision을 승인한다.
5. 실행 화면에서 실행하여 201 / INSPECTION_PENDING / 자산 ON_LOAN / 반납 이력 1건과 PASS를 확인한다.
6. 중복 반납·무권한 TC도 같은 준비·승인 절차로 각각 409·403의 정상 거부 PASS를 확인한다.
7. 검사 전 재고 불변 TC의 `의도적 결함 검증` Fixture를 준비하고 **새 revision을 다시 승인**한다. 실행 결과의 HTTP는 201이지만 assetStatus 불일치로 FAIL이 발생한다.
8. 정상 TC에서 `인프라 ERROR 검증`을 선택·재승인하면 초기화 ERROR를 확인할 수 있다. 이후 정상 Fixture로 준비·재승인해 복구한다.
9. 전체 실행 이력에서 과거 revision별 PASS/FAIL/ERROR를 확인한다. Dashboard는 현재 revision 최신 일반 실행과 synthetic 실행을 구분한다.
10. Excel 다운로드의 실행결과 시트에 세 결과와 revision·API·불일치가 포함되는지 확인한다.

저장된 실제 시연은 `demo-progress.json`, `execution-history.json`, `return-pass.json`, `return-fail.json`, `return-error.json`, `return-report.xlsx`에 있다. UI 증거는 같은 이름 PNG 및 return-blocked.png, return-fail-mobile.png에 있다.

현재 시연 완료 상태: 정상/중복/권한 TC는 일반 PASS, 검사 전 불변 TC는 의도적 결함 FAIL이다. 정상 TC의 과거 ERROR는 과거 revision으로 보존됐으며 현재 일반 ERROR 집계에는 포함하지 않는다. 새 실행은 새 UUID로 기록되므로 단순 확인 목적이라면 저장 이력 조회만 사용한다.

## Trace와 Graph 범위

Jaeger의 backend 실행 Trace는 `trace-results.json`의 executionId/traceId로 조회한다. `execution.allowlist`, `execution.fixture.initialize`, `execution.dummy.invoke`, `execution.assertions`가 연결되며 ERROR는 실패한 초기화 단계까지만 존재한다.

기존 Graph projection이 실제 반납 실행 6건의 Execution 노드·EXECUTED_AS 관계를 생성하는 회귀를 통과했다. 운영 Neo4j의 수집 scope는 기존 3개 요구사항 그대로이며 반납 canonical Api 노드/운영 projection sync는 확장하지 않았다. 따라서 새 반납 요구사항이 운영 Graph 화면에 자동 등장한다고 주장하지 않는다. 전체 Graph Schema나 Phase 15 변경 영향 분석은 변경하지 않았다.
