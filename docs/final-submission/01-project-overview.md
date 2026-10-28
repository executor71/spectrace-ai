# 01. 프로젝트 현황과 범위

조사 기준: 2026-10-28 KST. 현재 작업 트리의 소스·저장된 검증 산출물·읽기 전용 재조회가 근거다. 이번 문서 수집에서는 모델 호출, 성능 재측정, 테스트 재실행, 승인·실행·평가 생성, 기능/소스/설정/평가셋 변경을 하지 않았다.

## 프로젝트와 대상 사용자

**SpecTrace AI**는 변경 요구사항을 합성 IT 자산관리 업무규칙·API 명세에 연결하고, 근거가 있는 테스트 설계·검토·합성 실행·변경 영향 추적을 돕는 로컬 PoC다. 저장소·패키지의 이전 명칭은 `Legacy Change Assistant` / `legacy-change-assistant`다. 현재 제품 명칭은 `frontend/index.html`, `frontend/src/App.tsx`, `frontend/src/navigation.ts`에서 확인한다.

제품이 대상으로 하는 역할은 요구사항을 검토하는 개발자·QA/테스트 담당자·검토자다. 이는 화면의 입력→분석→테스트→승인→실행 업무에서 확인되는 대상이며 실제 고객 인터뷰·운영 도입·사용자 수를 증명하는 자료는 없다. 합성 시스템의 EMPLOYEE/DEPARTMENT_MANAGER/ASSET_ADMIN은 **테스트 대상 업무의 Fixture 역할**이며 SpecTrace 사용자의 실명 인증/RBAC와 다르다.

해결하려는 문제는 변경 조건의 누락·모호함, 문서/규칙/API/테스트 간 추적 어려움, 근거 없는 기대결과 생성 위험, 승인 없는 실행, 변경 후 검토할 기존 TC를 찾는 비용이다. 사람이 하던 검토를 보조하는 목적은 확인되지만 수작업 시간 대비 절감률은 미측정이다. 근거: [업무 안내](../../frontend/src/GettingStarted.tsx), [화면 구성](../../frontend/src/navigation.ts), [Phase15 범위](../phase15-evidence/README.md).

## Git와 재현 기준

- Branch: `phase15/change-impact-analysis`
- HEAD: `155c2664c44df2c902a168a3264c049cb318cf8a` — 2026-10-27 09:48:44 KST, `feat(impact): add evidence-grounded change impact analysis`.
- 선행 Graph 복구 커밋 `692d8ae`, 정책 확장 `6e4a095`, 비동기 Job `1301db4`가 이력에 있다.
- **작업 트리는 dirty**다. 반납 실행 확장, Java 25 전환, 추가 UI/랜덤 예제, 요약 로그, Jaeger 복구 등에는 미커밋 변경이 포함된다. HEAD만 checkout한 결과를 현재 전체 구현과 동일하다고 쓰면 안 된다.
- [Phase15 커밋 검증](../phase15-evidence/commit-validation.md)의 Java21/353건은 당시 분리된 커밋 스냅샷이다. [최신 보관 회귀](../observability-recovery/completion.json)의 445건은 후속 개선을 포함한 작업 트리다. 이번에는 commit/push를 하지 않았다.

## Phase별 구현·검증 현황

표의 PASS는 **각 당시 기록**을 뜻한다. 현재 소스 전체를 이번에 다시 테스트했다는 뜻이 아니다. 초기 문서의 ‘다음 Phase 미구현’은 작성 당시 범위다.

이 표의 테스트 수는 회귀 suite 건수로서 품질 평가셋 크기가 아니다(평가셋 크기: 해당 없음, fixture/격리 DB 등 조건은 원본 참조). 일부 단계의 요약에는 실행 timestamp가 없어 정확한 테스트 시각은 미확정이다. 문서 날짜·Git 보존일을 실제 실행 시각으로 대체하지 않는다. 시각·분모·환경이 확인되는 성능/품질 측정은 [06](06-evaluation-metrics.md)에 별도로 기록했다.

| Phase | 실제 구현 | 당시 검증 근거/결과 | 판정 |
|---|---|---|---|
| 0 | Compose·health·schema/role·Flyway 경계 | [재검증](../phase0-recheck.md): 권한 검사 36, 허용 조회 3, HTTP/Chrome 정상 | 구현·검증 기록 |
| 1 | 요구사항 등록·조회·입력 오류 | [결과](../phase1-result.md): Backend 17건, 실제 DB/API/화면 | 구현·검증 기록 |
| 2 | 합성 9문서/27청크·bge-m3 Vector 검색 | [결과](../phase2-result.md): 8질의 Hit@5 8/8, 기대 문서 전체 포함 7/8; AI 14건/Backend17건 원본 로그 | 구현·검증 기록 |
| 3 | Qwen 근거 선택·구조화 분석·저장 | [결과](../phase3-result.md): Python37/Backend26, 실제 5입력의 분석 기록 | 구현·검증 기록 |
| 4 | 정책 기반 TC Selection·생성 배치 저장 | [결과](../phase4-result.md), [회귀](../phase4-evidence/regression-results.json): Backend39, 기존/신규 Python61; 실제 TC5 | 구현·검증 기록 |
| 5 | TC 수정·승인·반려·revision | [결과](../phase5-result.md): Backend55/Python61, 실제 Chrome | 구현·검증 기록 |
| 6 | 격리 GT 평가·재현 가능한 지표·평가 UI | [집계](../phase6-evidence/completion-summary.json): 자동156건; 합성3사례의 생성본 평가 | 구현·제한적 평가 |
| 7 | 닫힌 Dummy dispatch·Expected/Actual·PASS/FAIL | [집계](../phase7-evidence/completion-summary.json): 자동185건, 당시 API2종, 실제 PASS/합성 결함 FAIL | 구현·검증 기록 |
| 8 | BM25/RRF Hybrid·로컬 reranker·검색 비교 | [결과](../phase8-result.md): 자동225건, 고정32질의 실험 | 구현·실험 검증 |
| 9 | MCP Gateway·초기5 Tool·Resource | [결과](../phase9-result.md): 자동243건, 실제 MCP70검사; 현재8 Tool은 Phase11 확장 포함 | 구현·검증 기록 |
| 10 | OTel→Collector→Jaeger·민감정보 제한 | [결과](../phase10-result.md): 자동252건; 이후 장애와 복구는 별도 기록 | 구현·후속 복구 확인 |
| 11 | Neo4j 관계 추적·Graph API/MCP3종 | [결과](../phase11-result.md): 자동274건, 관계20문항; 후속 동기화 복구 결과 별도 | 구현·관계 평가 |
| 12 | React19 워크스페이스·반응형/접근성 UI | [보고서](../phase12-ui-evidence/report.json): Backend84, Chrome/격리 DB UI, 운영 쓰기0 | 구현·화면 검증 기록 |
| 13 | 업무 대시보드·Excel·저장 기술지표 표시 | [결과](../phase13-result.md): Backend94, 실제 DB/API/Excel/화면 | 구현·검증 기록 |
| 14 | DB Job Queue·상태/복구·진행 화면 | [결과](../phase14-result.md): Backend111/AI64 등, 실제 Qwen Job1건 | 구현·검증 기록 |
| 15 | Baseline·변경안·고정 LangGraph·영향 후보·별도 검토·Excel | [결과](../phase15-evidence/README.md): 당시 전체382/분리 스냅샷353, 실제 Qwen1/캐시 재처리0회 | 구현·단일 사례 검증 |

후속 개선: [TC정책 확장](../testcase-policy-extension/regression-results.md), [반납 실행 확장](../return-execution-extension/regression-results.md), [Graph 동기화 복구](../graph-sync-repair/README.md), [Workflow 로그](../workflow-logging/video/README.md), [Jaeger 복구](../observability-recovery/root-cause.md). 최신 보관 회귀는 자동445건 PASS + 중복 Python 장애 조건129건 재실행 PASS다. 서로 다른 시점의 누적 회귀 수를 합산하지 않는다.

## 현재 실제 사용 범위와 확인 수준

요구사항 등록/저장 분석/TC 생성, 현재 revision 검토·승인, 지원된 Dummy 실행과 이력, 제한된 Frozen 평가, Graph 조회, 대시보드/Excel, 비동기 Job, 변경 영향 후보 비교가 소스와 저장 증거로 확인된다. 2026-10-28 읽기 전용 조사에서 Phase15 최종 결과/성공 Job, 과거 반납 PASS·FAIL·ERROR·복구 이력, Jaeger Trace를 재조회했다. 세부 식별자와 현재 배치 주의사항은 [구현 증거](05-implementation-evidence.md)에 있다.

계획/미구현 또는 미검증: 동적 실행 계획 생성·자율 Tool 선택, 운영 시스템 연동, 인증된 사용자/RBAC, 임의 API 실행, 성공 반납 검사 자동 실행, 일반화된 영향 정확도·생산성 개선·대규모 부하 검증. [한계](08-limitations-and-future-work.md) 참조.

초기 [README](../../README.md), [architecture.md](../architecture.md), [phase2-status.md](../phase2-status.md)는 최신 완료 범위를 설명하지 않는다. 최종 제출에는 해당 과거 문장을 현재 상태로 그대로 옮기지 않는다.
