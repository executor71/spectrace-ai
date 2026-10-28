# 08. 한계·미구현·추가 증빙

구현이 확인되지 않았거나 시험 범위가 부족한 항목을 최종 제출의 완료 기능과 분리한다. 아래는 후속 과제이며 이번에 개발하거나 재측정하지 않았다.

## 구현했지만 제한적인 기능

| 항목 | 현재 확인된 범위 | 제출 시 피할 표현 |
|---|---|---|
| Agent/Planning | Phase15 고정 LangGraph3노드; 기본 분석·TC는 함수 기반 고정 흐름 | 자율 계획 생성, 동적5-step plan, LLM이 임의 Tool을 선택한다 |
| 분석 | 근거 ID 선택·strict Schema/원문 검증·미확정 항목 분리 | 의미 정확도 보장, 환각 완전 제거 |
| TC 생성 |15개 source-gated plan의 Selection/materialize; 모호함/근거/정책 미지원 시 보류 | 모든 요구사항/5유형을 항상 자동 생성 |
| 반납 실행 | 접수·중복·권한·검사 전 불변 및 파손 증빙 누락400 | 성공 검사/PASSED·DAMAGED 전이를 전부 실행 |
| Phase15 |1개 실제 모델 사례, 원문 보정·캐시 재처리, 검토 후보 제안 | 영향도 정확도/P/R100%, 최초 모델이3조건 모두 맞춤 |
| Graph | 합성20문항, 구조화 업무 관계 추가, 현재 배치·정본4API | RAG Recall 상승과 동일, 모든 과거 실행 Graph 연결, 일반 GraphRAG 정확도100% |
| 평가 | Frozen3사례의 deterministic 점수; 자유 서술 의미 검증 미평가 | 모든 새 요청의 품질 점수, Code Validity100%=의미 정확도100% |
| HITL | 실제 edit/approve/reject API와 revision 게이트 | 로그인된 사람·조직 권한으로 승인 신원을 보증 |
| Dummy | allowlisted in-process 합성 Adapter·격리 메모리 | 실제 기업 API/자산 DB/외부 MCP 연동 실행 |
| Job | durable DB queue·단일 모델 실행·lease/fence·안전한 실패 정리 | 분산 고처리량, 실행 중 모델 강제 kill, crash 작업 자동 재실행 |
| 관측 | 실제 저장/Query/UI/restart 확인, bounded queue | 무기한 중단에도 Trace 무손실 |

근거: [Agent 구조](03-agent-workflow.md), [반납 지원 계약](../return-execution-extension/execution-support-matrix.md), [Phase15 평가 원문](../phase15-evidence/evaluation-results.md), [Graph 범위 충돌](../graph-sync-repair/README.md), [Frozen 평가](../phase6-result.md), [Job timeout 계약](../phase14-result.md).

## 설계/요구만 있거나 구현 근거가 없는 항목

동적 Planning, 일반 자율 Multi-Agent 협업, LLM 기반 임의 Tool Routing, 무제한 API/임의 Cypher, 운영 사용자 인증·SSO·실제 조직 RBAC, 실제 IT자산관리 운영 연동, 범용 대용량 문서 수집, Query Rewrite의 기본 경로 적용, 운영급 다중 모델 병렬 처리의 구현·완료 근거를 확인하지 못했다. `docs/architecture.md`의 미래 graph 설계를 현재 실제 Graph topology로 쓰지 않는다.

성공 반납 검사 HTTP 상태와 대여 완료 상태 전이 등 합성 명세 자체에 없는 계약은 임의로 만들어 실행하지 않는다. Phase15 새 역할 TC는 TEMPLATE_UNSUPPORTED/expectedResult=null/automaticExecutionSupported=false이며 검토 상태 REVIEWED가 정책 승인·TC 승인·실행 허용은 아니다.

## 데이터·평가 한계

RAG32질의, Graph20문항, Frozen3사례, Phase15 작성자 초안1사례는 같은 작은 합성 도메인이다. 다중 도메인 일반화/통계적 신뢰구간/독립 사람 평가가 없다. Graph 후속 음성0.8과 Phase15 최초 모델 오분류를 포함해 보고해야 한다. 테스트 보강으로 GT·assertion을 결과에 맞춰 완화했다는 근거는 없으며 기존 보고서의 명확한 실패/보류도 보존한다.

실제 Qwen의 전체 기간 누적 호출 수는 중앙 계수로 확인되지 않는다. 대표 기록의 API 요청 수/Provider 호출 수/실패 후 재시도/캐시 재사용은 분리해야 한다. CPU 지연은 세션별 조건이 다르므로39.6초→83.8초 등을 모델 개선/악화 추세로 해석하지 않는다.

수작업 baseline, 실제 사용자 비교군, 요구사항 처리 총소요시간, 개발자 수정률, 업무시간 절감률, 금전 ROI는 미측정이다. `frontend/src/Dashboard.tsx`도 시간 절감 미측정을 표시한다. 목표 숫자가 합의되지 않았으면 임의 목표 달성률을 만들지 않는다.

## 제출 전 필요한 추가 증빙 (이번 범위 밖)

1. **제출 소스 스냅샷 확정**: 현재 HEAD에는 미커밋 반납/Java25/UI/로그/Jaeger 개선 전체가 없다. 승인된 제출 범위·commit 또는 배포 스냅샷·컨테이너 이미지 digest를 하나로 맞추고 그 스냅샷에서 회귀 결과를 확보해야 한다. 이번에는 commit/push/코드 변경을 하지 않았다.
2. **동일 ID 최신 E2E 녹화**: Qwen 분석과 TC의 기존 fixture 기반 검증은 서로 다른 Requirement다. 한 요청에서 근거→분석→정책 TC→실제 사람 검토→실행→Graph/Trace까지 이어지는 장면은 별도 증빙이 필요하다. 저장 조회를 live 재실행으로 설명하지 않는다.
3. **반납 현재 배치 재검토**: 과거 승인·실행 이력과 현재 DRAFT4개 배치를 구분한다. 현재 실행을 촬영하려면 현재 revision의 적격성/Fixture 준비/승인을 다시 거쳐야 한다. 과거 실행을 붙이거나 DB를 초기화해서 장면을 만들면 안 된다.
4. **Phase15 독립 평가**: 실제 개발자가 보정 기준/후보 필요성을 검토한 reference, 최초 원시 모델과 제한적 보정의 분리, 더 많은 독립 변경 사례·과다 후보 precision·수정률을 측정해야 한다. 현재 수정 프롬프트로 실제 모델을 재호출해 성공했다는 증거는 없다.
5. **운영 검증**: 실제 모델 실행 중 Backend/AI 재시작·동시 부하·Graph 갱신 경합, 긴 관측 장애/큐 유실, 인증·접근 제어·로그 보존/삭제 정책 등은 별도 시험이 필요하다.
6. **증거 보존**: 일부 Java JUnit/Graph 화면/원시 회귀 로그는 OS TEMP 경로뿐이다. 최종 제출에 포함할 수 있는 산출물을 별도 보존해야 한다. 측정 timestamp가 없는 Graph 실험은 원시 실행 로그 확인 전 정확한 측정일을 단정하지 않는다.

## 최종 결과보고서 문장 지침

- 사용 가능: ‘합성32질의의 고정 실험에서 Hybrid Recall@5가90.10%에서93.49%로 증가했다.’
- 사용 가능: ‘기존 근거·정책·승인·Fixture를 통과한 합성 API 실행을 비교 코드로 PASS/FAIL 판정했다.’
- 사용 가능: ‘고정3노드 LangGraph로 변경 조건·Graph·TC 검토 후보를 조립했다. 단일 사례의 최초 모델 오분류는 원문 보정 후 별도 결과로 보존했다.’
- 미사용: ‘생산성50% 향상’, ‘실제 사용자 정확도100%’, ‘완전 자율 Planning’, ‘운영 API를 안전하게 자동 배포’, ‘Graph 확장으로 검색 정확도100%’ 등 근거 없는 표현.

주요 값·분모·시점은 [06](06-evaluation-metrics.md), 실제 ID·검증 수준은 [05](05-implementation-evidence.md), 파일 원본은 [09](09-evidence-index.md)를 따른다.
