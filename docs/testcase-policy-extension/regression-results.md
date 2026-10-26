# 회귀 및 성과 검증

| 검사 | 결과 |
|---|---|
| Spring 전체: 기존 API·승인·실행·대시보드·Job + 신규 정책 | 117개, 실패/오류/skip 0 |
| ai | 76개 통과 |
| retrieval | 27개 통과 |
| evaluation-metrics | 22개 통과 |
| evaluation-api | 12개 통과 |
| mcp | 18개 통과 |
| graph-projection | 18개 통과 |
| graph-analysis | 4개 통과 |
| observability | 9개 통과 |
| 평가 DB 저장·재현·권한 테스트 | 격리 DB 9개 통과 |
| React TypeScript / Vite build | 통과, 출력은 node_modules/.tmp 아래 |
| 랜덤 예제 단위 테스트 | 5개 통과 |
| 정책 보류/시스템 오류 React UI | 1440·390px 총 8개 상태 검사 통과 |
| 기존 랜덤 예제·카운터·덮어쓰기·명시적 저장 UI | 1440·390px 통과, 실제 쓰기는 mock |
| 8개 주요 화면 반응형 | 1440·1024·390px 24조합 통과, 브라우저 오류/자동 변경 요청 0 |
| 실제 MCP get_test_cases | 표준 MCP 클라이언트, 8개 Tool 및 엄격한 입력 계약, 4개 TC·Evidence·최종 실행 차단 통과 |

## 동일 반납 스냅샷 비교

| 지표 | 변경 전 | 변경 후 |
|---|---:|---:|
| 확정 조건 | 4 | 4 |
| 생성 TC | 0 | 4 |
| 근거 없는 생성 TC | 0 (생성 0건) | 0 (모든 TC의 문서·Section·Evidence 및 Expected Result 검증) |
| 확정 조건 중 TC 지원 | 0/4 (0%) | 3/4 (75%) |
| 랜덤 예제 TC 지원 | 2/5 | 5/5 (실제 검색 + Fake 분석·생성) |
| 기존 승인 템플릿 | 5 | 원본 JSON 객체 5개 동일, 기존 회귀 통과 |

**이는 정책 지원 범위 확장 결과이며 AI 정확도 향상 측정이 아니다.** 기존 분석·합성 RAG·Ground Truth·평가 기준을 변경하지 않았다.

## 실제 Qwen 대표 1건

- HTTP 200, 소요 약 104.3초(브라우저 재조회 검증 포함), 실제 LLM 호출 1회.
- 유형: {'NORMAL': 1, 'EXCEPTION': 1, 'AUTHORIZATION': 1, 'BUSINESS_RULE': 1}. TC 수를 5개로 강제하지 않았다.
- 원래 저장된 반납 분석 4조건을 변경하지 않고 4개 TC 생성·DB 저장·GET 재조회·React reload를 확인했다.
- 상태 PARTIALLY_GENERATED. 부속품·접수일·담당자 기록 문장 1개는 정책 미지원으로 남는다.
- 데스크톱·모바일 화면 확인. 생성 executable=false이며 실제 실행 요청은 수행하지 않았다.
- 대표 TC 조회만 기존 사용자 데이터에 저장했다. 기존 승인·실행 이력은 삭제/수정하지 않았다.

## 검증 중 조치와 제한

- 첫 Graph/OTel 실행은 필요한 /evidence Fixture·출력 마운트 누락으로 실패했다. 마운트 보완 후 해당 suite만 재실행하여 통과했다.
- 첫 실제 브라우저 검사에서 같은 이름의 탐색 버튼과 생성 버튼을 구분하지 못했다. 모델 호출 전 선택자를 수정했고 이후 실제 생성은 한 번만 실행했다.
- 최초 MCP 검사는 런타임 executable을 최종 실행 가능성으로 잘못 가정했다. 기존 generationExecutable/실행 적격성 의미를 확인하여 검증식을 바로잡았으며 실행 로직은 변경하지 않았다.
- 최종 미해결 자동 테스트 실패 없음. 실제 모델은 대표 1건만 사용했으며 예제 5개의 실모델 분석 성공률은 측정하지 않았다.
- 독립 평가 역할·app 역할 접근 차단 회귀를 통과했고 평가 관련 14개 파일 hash가 변경되지 않았다. 생성 코드에 GT 접근 경로를 추가하지 않았다.
- 정책 hash 변경으로 기존 배치가 stale로 표시될 수 있다. 정책/명세 변경 후 재생성 요구는 기존 설계를 따른다.

검증 원본: `backend-results.json`, `regression-results.json`, `evaluation-db-result.json`, `mcp-live-result.json`, `protected-audit.json`, `return-scenario-tests.json`, `random-example-results.json`. 임시 로그/JUnit는 OS temp의 spectrace-policy-extension에 보관했다.

## 별도 커밋 전 검증

- 현재 브랜치: `appmod/java-upgrade-20261026122936`. Phase 14 기준 커밋 `1301db4`는 이미 포함되어 있으며 중복 커밋하지 않는다.
- 다른 미커밋 Java 업그레이드·리디자인·랜덤 예제 구현을 제외한 Git 인덱스 스냅샷을 별도 임시 폴더로 내보내 검증했다.
- 해당 스냅샷의 Java 21 백엔드 전체 117개 테스트: failures/errors/skipped 0. Python AI 76개 통과.
- 해당 스냅샷의 프런트엔드 Docker 빌드(TypeScript·Vite) 통과. 임시 포트에서 정책 보류/시스템 오류 UI 8개 검사 통과.
- Requirements.tsx는 정책 지원 범위 안내만, style.css는 정책 결과 표현 규칙만 포함했다. 제품의 랜덤 예제 기능과 리디자인은 이 커밋에서 제외한다.
- 예제 재검증은 이 폴더의 고정 random-examples.json을 사용하므로 별도 미커밋 제품 파일에 의존하지 않는다.
- 민감 파일·추가된 비밀값 검사 통과. 기존 승인 템플릿 5개, 실행 AllowList·fixtureReady, Ground Truth·평가 파일은 유지한다.
- origin은 Public으로 확인했으며, 사용자가 현재 Public 저장소로 Push를 명시적으로 승인했다. 저장소 공개 설정은 변경하지 않는다.