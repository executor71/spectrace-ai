# SpecTrace AI — Phase 13 결과

2026-10-20 (Asia/Seoul). Phase 13-A 대시보드·탐색을 먼저 구현하고 Chrome에서 확인한 뒤 Phase 13-B Excel을 구현했다. 로컬 시연 주소: http://localhost:5173/#dashboard

## 사전 확인과 재사용

- 시작 Git HEAD: `0cf8516abe75493cdb9f64b5579d3323420e4c95`. 미커밋 변경 없음. 작업 브랜치: `phase12/ui-redesign` (새 commit 생성하지 않음).
- README는 초기 Phase 설명이 남아 있으나 실제 코드는 Phase 12 React 19 UI와 검토·실행·평가·Graph를 포함한다. 실제 구현을 기준으로 진행했다.
- 기존 Requirements 컨텍스트, card/metric/workflow-tabs 스타일, 분석·TC·검토·실행·평가·Graph 화면과 조회 계약을 재사용했다. Dashboard/Export의 완성된 기존 구현은 없었다.
- 차트는 Recharts 도입을 검토했지만 두 개의 단순 상태 막대에는 추가 의존성 없이 CSS와 접근 가능한 버튼·수치를 사용했다. 상태 이름·건수·모수를 함께 제공한다. 새 UI 프레임워크 없음.
- 원본 요구사항/분석/현재 생성 TC·검토본/보존 실행 이력은 실제 저장 데이터로 집계 가능하다. 업무시간 절감률, 보존하지 않는 과거 검토 이력, 최신 차단 건수는 임의 생성하지 않았다.

## 구현과 API

| GET API | 동작 |
| --- | --- |
| `/api/dashboard/summary?requirementId={UUID}` | 전체 또는 요구사항 1건의 요약·목록·현재 TC 상태. 파라미터 생략 시 전체 |
| `/api/dashboard/requirements?requirementId={UUID}` | 동일 스냅샷 계약으로 요구사항 목록과 TC 탐색 자료 반환 |
| `/api/requirements/{id}/reports/test-report.xlsx` | 선택 요구사항의 서버 저장 데이터로 XLSX 생성 |

대시보드에는 범위 필터·마지막 조회·새로고침·등록 진입·4개 카드·검토/실행 차트·요구사항 목록·검토 대기/실패 목록이 있다. 제목 검색과 10건 단위 페이지를 제공한다. 카드/차트 클릭은 해당 TC 조건을 적용하고 목록으로 이동한다. TC 행은 정확한 TC와 요구사항을 선택해 기존 상세 화면을 연다. 요구사항별 상세·Excel 버튼 및 상세 상단 탐색·다운로드를 제공한다. 새로고침과 다운로드는 GET만 사용한다.

TC 상세 진입 시 저장 TC를 GET으로 불러온다. 평가 화면의 등록된 대상에 저장 결과가 없는 경우 ‘미평가’를 표시한다. 기존 분석의 429 ANALYSIS_BUSY 처리와 수동 재시도 동작은 유지한다.

## 지표 정의와 검증 값

| 지표 | 모수 / 기준 | 확인 값 |
| --- | --- | ---: |
| 등록 요구사항 | 선택 범위의 app.requirement 행 | 28건 |
| 현재 생성 TC | 현재 app.test_case_generation에 연결된 TC. 현재 검토본 사용 | 15건 |
| 검토 대기 / 승인 / 반려 | 위 TC의 현재 approval_status | 9 / 5 / 1건 |
| 일반 실행 PASS / FAIL / ERROR TC | TC ID + 현재 generationId + 현재 reviewRevision에 일치하는 최신 일반 실행 1건 | 3 / 0 / 0건 |
| 일반 실행 미실행 TC | 위 조건에 일치하는 일반 실행 없음. 과거 revision 실행만 있는 TC 포함 | 12건 |
| 의도적 결함 실행 TC | 현재 batch/revision의 syntheticDefect 실행 존재 TC. 일반 통계 제외 | 1건 |
| 보존 실행 횟수 | 과거 batch/revision·반복 실행 포함 전체 기록. TC 수와 다름 | 145회 |
| 일반 실행 PASS 비율 | PASS / (PASS+FAIL); ERROR·미실행·의도적 결함 제외 | 100% (3/3) |

PASS 비율은 AI 정확도나 커버리지가 아니다. 분모가 0이면 ‘집계 대상 없음’. 현재 생성 TC는 활성 batch 소속이라는 뜻이며 최신 실행 가능성을 보장하지 않는다. 분석 변경 여부는 목록 및 보고서에 표시하고 실행 가능성·실행 차단은 임의 추정하지 않는다. 차단은 FAIL에 합산하지 않는다. 과거 생성 batch의 실행은 보고서에 보존하되 현재 TC 통계에서는 제외한다. 저장되지 않는 과거 승인 활동 이력은 복원하지 않는다.

독립 SQL, 기존 `/test-cases` GET, 새 집계를 대조했다. 작업 전후 요구사항 28건/TC 15건/실행 145회는 동일하다. 근거: `db-api-verification.json`, `baseline.json`, `final-summary.json`.

## Excel 범위와 품질

Apache POI XSSF `poi-ooxml:5.5.1` 고정. 공식 릴리스 확인: [Apache POI](https://poi.apache.org/index.html?lang=eng).

시트는 **요약 / 요구사항 분석 / 테스트케이스 / 실행결과 / 근거 연결 / 평가결과** 6개다.

- 현재 검토본과 원본 출처·수정 여부·reviewRevision·검토자·시각·의견·생성 시점 executable을 보존한다. 생성 시점 executable을 현재 실행 가능성으로 표현하지 않는다.
- 실행 시점에 저장된 Expected/Actual, 당시 revision, batch, 결과, 불일치, 소요시간, 의도적 결함 여부를 기록한다. 과거 실행을 현재 수정본으로 재해석하지 않는다.
- 분석 및 TC의 저장 근거 식별자와 기존 공개 근거 스니펫만 내보낸다.
- 평가는 기존 서비스의 공개 GET `/api/evaluations/targets`, `/api/requirements/{id}/evaluations`만 이용한다. 결과에서 지표 값·분모·dataset version/case ID·시각·contentMode·generationId·inputHash만 선택한다. 정답 원문·누락 필수 시나리오·내부 Prompt·비밀키·Ground Truth hash는 내보내지 않는다.
- 미등록/미평가/조회 실패를 구분한다. 과거 batch 평가를 표시하며, 기존 공개 결과에 review revision 매핑이 없으면 일치 확인 불가라고 명시한다. 없는 점수는 0으로 채우지 않는다.
- 한글 헤더, 고정 첫 행, 자동 필터, 줄바꿈, 열 너비, 날짜·숫자 서식, 상태 색상, 문자열 UUID를 제공한다. 날짜 셀은 Asia/Seoul이다.
- 모든 사용자 문자열은 명시적 문자열 셀이다. `=`, `+`, `-`, `@` 입력으로 수식·외부 연결을 만들지 않는다.
- 30,000 UTF-16 문자 단위로 초과 내용을 분할 행에 기록하고 첫 식별자에 분할 번호를 표기한다. Unicode surrogate pair를 자르지 않는다. 원문을 조용히 잘라 버리지 않는다.
- Workbook/출력 자원은 try-with-resources로 닫는다. 보고서 한도는 데이터 행 합계 10,000행, 원문 문자열 합계 2천만자, 완성 XLSX 10 MiB다. 초과는 HTTP 413 JSON이다. 요구사항 미존재 404, 잘못된 UUID 400, 생성 실패 500. 클라이언트는 성공 상태와 XLSX Content-Type을 확인한 뒤 저장한다.
- app 조회는 REPEATABLE_READ 스냅샷이다. 평가는 이후 공개 GET으로 조회하므로 서비스 간 원자적 스냅샷은 아니다. 보고서에 이를 명시한다.

최종 Chrome 다운로드 샘플: [검증보고서](phase13-evidence/SpecTrace_AI_80e2d374-0825-4811-a11e-03ade256b6e8_검증보고서_20261020_195439.xlsx). HTTP 200, 올바른 Content-Type/UTF-8 파일명, 14933 bytes. TC 5건/실행 20건을 포함하며 UI와 요약 집계가 일치했다. 별도 `registered-evaluation-report.xlsx`에는 기존 저장 평가 지표도 포함된다.

POI 테스트·openpyxl 3.1.5·설치된 Microsoft Excel 16.0의 읽기 전용 실제 열기에서 6개 시트와 행을 확인했다. Excel을 저장/수정하지 않고 닫았다. openpyxl은 POI 기본 스타일 명칭이 없다는 경고를 출력하지만 실제 Excel에서 정상 개방됐으며 데이터/수식/링크 검사도 통과했다. 근거: `browser-results.json`, `excel-desktop-reopen.json`, `edge-results.json`.

## 기술 검증 결과

업무 대시보드와 분리된 ‘기술 검증 결과’ 탭에서 Phase 8 원본 저장 요약을 읽는다. JSX에 수치를 넣지 않았다. `frontend/public/technical-results.json`은 `docs/phase8-evidence/comparison-summary.json`과 `corpus-snapshot.json`에서 지표와 메타데이터만 추출했다. Vector/Hybrid/Hybrid+Reranker의 Recall@5·MRR@5·nDCG@5·동일 실험 평균/P95 지연시간을 비교한다.

측정일·32개 질의·27 chunks·모델·평가셋 hash·출처·소규모 합성 환경 한계를 표시한다. 검색 실험이나 LLM 평가를 다시 실행하지 않았다. Graph 평가를 업무 통계에 혼합하지 않았고 업무시간 절감률은 미측정이다.

## 검증 결과

- 분리된 tmpfs PostgreSQL에서 기존 회귀와 새 집계·보고서 테스트 **94개 통과**, 실패/오류/건너뜀 0. 반복 실행 중복 집계 방지·과거 revision/batch 제외·의도적 결함 분리·수정본·공개 GET 경계·Excel 재열기·수식 방지·Unicode 분할을 포함한다. `backend-tests.log`, `backend-junit/`.
- 최종 frontend TypeScript/Vite 및 backend 빌드 성공. `build-final.log`.
- 실제 Chrome: 카드/차트 필터, UUID 없는 선택, 특정 TC 상세, 저장 분석/TC/실행결과, 다운로드, 오류 JSON 미저장, 빈 상태/조회 실패 확인. 콘솔 오류 0, 브라우저 변경 요청 0. `browser-results.json`.
- 평가 미등록은 실제 데이터로 확인. ‘등록됐으나 미평가’는 현재 실제 등록 대상 모두 기존 결과가 있어 GET `[]`를 가로채는 테스트로 확인했으며, 해당 스크린샷에 mocked를 명시했다. 운영 DB를 바꾸지 않았다.
- 1440px / 1024px / 390px 확인. 390px 새 Chrome 세션에서 사이드바 닫힘, 단일 차트 열, 페이지 가로 넘침 없음. 표 영역만 가로 스크롤. 실제 아이폰 Safari는 미검증이며 데스크톱 Chrome viewport 에뮬레이션이다.
- 실제 LLM 호출 0회. 브라우저에 생성/실행 POST 없음, Ollama baseline 이후 `/api/chat`·`/api/generate` POST 0건. `final-integrity.json`.

## 변경 파일과 보존 범위

새 파일: `backend/src/main/java/com/example/legacyassistant/dashboard/{DashboardService,DashboardController,ReportService,ReportController}.java`, 같은 dashboard 패키지의 `ReportTest`, `DashboardIntegrationTest`, `ReportPublicEvaluationTest`, `frontend/src/Dashboard.tsx`, `frontend/src/dashboard.css`, `frontend/public/technical-results.json`.

수정 파일: `backend/pom.xml`, `frontend/src/Requirements.tsx`, `frontend/src/TestCases.tsx`, `frontend/src/Evaluations.tsx`. 본 보고서와 `docs/phase13-evidence/`도 추가했다.

기존 RAG/LLM/Prompt·검토/승인·실행 통제·평가 서비스/기준·MCP·Graph·contracts·DB migration은 시작 commit 대비 바이트 변경 없음. DB 권한, 환경 파일, 기존 API 계약, 공인 접속 범위를 바꾸지 않았다. 기존 Compose 오버라이드(Phase 8/9/10/11)를 포함해 backend/frontend만 재기동했다. 기존 DB volume은 유지했다.

## 한계와 시연

소규모 로컬 PoC에 맞춘 조회다. 대시보드는 최대 요구사항 1,000건, 현재 TC 10,000건, 요구사항당 보존 실행 10,000행을 읽으며 한도 초과는 명시적으로 거절한다. 현재 데이터에서는 단순 검색/페이지가 적합하며 대규모 서버 페이지 API는 별도 범위다. 실행 차단·업무시간 절감·미보관 검토 이력은 측정하거나 복원하지 않았다. 기존 공개 평가 계약에 revision 매핑이 없다는 한계와 서비스 간 snapshot 시점 차이가 있다. 실제 iPhone Safari와 사람의 인쇄/디자인 검수는 수행하지 않았다.

1. http://localhost:5173/#dashboard 접속 → 카드/차트 클릭 → 목록 필터 확인.
2. ‘요구사항 범위’에서 `Phase 7 synthetic fixture` 제목의 요구사항 선택 → ‘상세 보기’ → 테스트/검토/실행 이동. UUID 복사 불필요.
3. 목록 또는 상세 상단의 ‘Excel 다운로드’ → 6개 시트 확인.
4. 대시보드 ‘기술 검증 결과’ 탭에서 저장 실험 비교 확인.

Phase 13 완료 후 멈추며 다음 Phase는 시작하지 않는다. 전체 증거 파일 hash는 `phase13-evidence/manifest.json` 참조.
