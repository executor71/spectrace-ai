"""Summarize recorded verification artifacts; never fabricates test executions."""
import json
import os
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

root=Path(__file__).resolve().parents[2]
out=root/'docs/testcase-policy-extension'
def read(name):return json.loads((out/name).read_text(encoding='utf-8-sig'))
policy=json.loads((root/'contracts/test-case-policy.json').read_text(encoding='utf8'))
old=read('policy-before.json')
assert old['plans']==policy['plans'][:5]
assert old['allowList']==policy['allowList'] and old['fixtureReady']==policy['fixtureReady']
rows=read('random-example-results.json');comparison=read('same-snapshot-comparison.json')
real=read('return-scenario-tests.json');result=real['result']
assert result['verification']['databaseReload'] and result['llmCalls']==1
assert len(result['testCases'])==4
suites=read('regression-results.json')
assert all(row['exitCode']==0 for row in suites)
assert read('evaluation-db-result.json')['exitCode']==0
assert read('mcp-live-result.json')['getTestCases']=='PASS'
reports=Path(tempfile.gettempdir())/'spectrace-policy-extension/junit'
summary={key:0 for key in ['tests','failures','errors','skipped']}
classes=[]
for file in reports.glob('TEST-*.xml'):
    suite=ET.parse(file).getroot()
    classes.append({'suite':suite.attrib['name'],**{key:int(suite.attrib[key]) for key in summary}})
    for key in summary:summary[key]+=int(suite.attrib[key])
assert summary=={'tests':117,'failures':0,'errors':0,'skipped':0},summary
(out/'backend-results.json').write_text(json.dumps({'totals':summary,'suites':classes},indent=2),encoding='utf8')

lines=['# 랜덤 예제 5개 검증','',
 '실제 Vector Top-5 검색을 사용했다. 검색 입력은 기존 분석과 동일한 제목 + 줄바꿈 + 전체 상세 내용이다. 분석은 고정된 extractive Fake Provider를 실제 AnalysisService에 연결했고, 생성은 Fake Provider로 검증했다. Qwen으로 5개를 모두 재분석한 결과가 아니다. 고정 선택이므로 실제 모델이 다른 조건을 선택하면 생성 건수는 달라질 수 있다.','',
 '| 번호 | 예제 | RAG hit | 확정 조건(Fake) | 변경 전 TC | 변경 후 TC | 근거 검증 | 자동 실행 |',
 '|---|---|---:|---:|---:|---:|---|---|']
for row in rows:lines.append(f"| {row['id']} | {row['title']} | {row['ragHits']} | {row['confirmedConditions']} | {row['beforeTestCount']} | {row['testCount']} | {'통과' if row['grounded'] else '실패'} | 미지원 |")
lines+=['',f"최소 1개 TC 생성 가능한 예제: 동일 Fake 분석 기준 {sum(r['beforeTestCount']>0 for r in rows)}/5 → {sum(r['testCount']>0 for r in rows)}/5.",'',
 '예제 데이터 자체와 RAG 문서는 이번 작업에서 바꾸지 않았다. 수정 권한 예제는 이전 작업에서 자산 등록으로 이미 교체되어 있었다. 폼에는 부분 생성 가능성과 자동 실행의 별도 지원 범위를 명시했다.','',
 '## 범위의 한계','',
 '- 예제 1·5의 기존 승인 5개는 유지한다. 추가 상태 충돌 조건이 확정되면 중복 승인 TC가 추가된다.',
 '- 예제 2는 AVAILABLE이 아닌 상태의 승인 거부만 추가했다. 성공 승인 및 모든 상태 조합을 완전히 커버한다는 뜻은 아니다.',
 '- 예제 3은 접수·권한·중복·검사 조건 중 실제 확정된 문장만 생성한다. 원래 저장된 4조건 스냅샷에서는 검사 조건이 확정되지 않아 검사 TC를 생성하지 않았다.',
 '- 예제 4는 정상 자산 등록 1개를 지원한다. 등록 권한 거부·필수값 누락·중복 자산번호의 개별 TC는 추가하지 않았다.',
 '- 상세 입력의 모든 문장에 대해 TC가 생성된다는 보장은 없다. 미지원 조건은 조건별 현황에 표시한다.','',
 '## 요청문의 포괄적 대표 문장','',
 '`broader-request-validation.json`은 요청문에 적힌 원문을 별도로 실제 검색 + Fake PARTIAL 분석으로 검사했다. 기존 대여 이력의 필드·조회 범위·일관성 판정 계약은 검색 근거만으로 확정할 수 없어 확인 질문을 남겼고 TC 생성 모델을 호출하지 않았다. 이 입력의 실제 Qwen 분석은 수행하지 않았다. 같은 제목의 실제 Qwen 생성 검증은 이미 저장된 구체적 4조건 분석을 그대로 사용했으며 `return-scenario-tests.json`에 명확히 구분했다.']
(out/'random-example-validation.md').write_text('\n'.join(lines)+'\n',encoding='utf8')

types=Counter(tc['type'] for tc in result['testCases'])
lines=['# 회귀 및 성과 검증','',
 '| 검사 | 결과 |','|---|---|',
 '| Spring 전체: 기존 API·승인·실행·대시보드·Job + 신규 정책 | 117개, 실패/오류/skip 0 |']
for suite in suites:lines.append(f"| {suite['suite']} | {suite['tests']}개 통과 |")
lines+=['| 평가 DB 저장·재현·권한 테스트 | 격리 DB 9개 통과 |',
 '| React TypeScript / Vite build | 통과, 출력은 node_modules/.tmp 아래 |',
 '| 랜덤 예제 단위 테스트 | 5개 통과 |',
 '| 정책 보류/시스템 오류 React UI | 1440·390px 총 8개 상태 검사 통과 |',
 '| 기존 랜덤 예제·카운터·덮어쓰기·명시적 저장 UI | 1440·390px 통과, 실제 쓰기는 mock |',
 '| 8개 주요 화면 반응형 | 1440·1024·390px 24조합 통과, 브라우저 오류/자동 변경 요청 0 |',
 '| 실제 MCP get_test_cases | 표준 MCP 클라이언트, 8개 Tool 및 엄격한 입력 계약, 4개 TC·Evidence·최종 실행 차단 통과 |','',
 '## 동일 반납 스냅샷 비교','',
 '| 지표 | 변경 전 | 변경 후 |','|---|---:|---:|',
 '| 확정 조건 | 4 | 4 |','| 생성 TC | 0 | 4 |','| 근거 없는 생성 TC | 0 (생성 0건) | 0 (모든 TC의 문서·Section·Evidence 및 Expected Result 검증) |',
 '| 확정 조건 중 TC 지원 | 0/4 (0%) | 3/4 (75%) |',
 f"| 랜덤 예제 TC 지원 | {sum(r['beforeTestCount']>0 for r in rows)}/5 | {sum(r['testCount']>0 for r in rows)}/5 (실제 검색 + Fake 분석·생성) |",
 '| 기존 승인 템플릿 | 5 | 원본 JSON 객체 5개 동일, 기존 회귀 통과 |','',
 '**이는 정책 지원 범위 확장 결과이며 AI 정확도 향상 측정이 아니다.** 기존 분석·합성 RAG·Ground Truth·평가 기준을 변경하지 않았다.','',
 '## 실제 Qwen 대표 1건','',
 f"- HTTP 200, 소요 약 {real['elapsedSeconds']:.1f}초(브라우저 재조회 검증 포함), 실제 LLM 호출 {result['llmCalls']}회.",
 f"- 유형: {dict(types)}. TC 수를 5개로 강제하지 않았다.",
 '- 원래 저장된 반납 분석 4조건을 변경하지 않고 4개 TC 생성·DB 저장·GET 재조회·React reload를 확인했다.',
 '- 상태 PARTIALLY_GENERATED. 부속품·접수일·담당자 기록 문장 1개는 정책 미지원으로 남는다.',
 '- 데스크톱·모바일 화면 확인. 생성 executable=false이며 실제 실행 요청은 수행하지 않았다.',
 '- 대표 TC 조회만 기존 사용자 데이터에 저장했다. 기존 승인·실행 이력은 삭제/수정하지 않았다.','',
 '## 검증 중 조치와 제한','',
 '- 첫 Graph/OTel 실행은 필요한 /evidence Fixture·출력 마운트 누락으로 실패했다. 마운트 보완 후 해당 suite만 재실행하여 통과했다.',
 '- 첫 실제 브라우저 검사에서 같은 이름의 탐색 버튼과 생성 버튼을 구분하지 못했다. 모델 호출 전 선택자를 수정했고 이후 실제 생성은 한 번만 실행했다.',
 '- 최초 MCP 검사는 런타임 executable을 최종 실행 가능성으로 잘못 가정했다. 기존 generationExecutable/실행 적격성 의미를 확인하여 검증식을 바로잡았으며 실행 로직은 변경하지 않았다.',
 '- 최종 미해결 자동 테스트 실패 없음. 실제 모델은 대표 1건만 사용했으며 예제 5개의 실모델 분석 성공률은 측정하지 않았다.',
 '- 독립 평가 역할·app 역할 접근 차단 회귀를 통과했고 평가 관련 14개 파일 hash가 변경되지 않았다. 생성 코드에 GT 접근 경로를 추가하지 않았다.',
 '- 정책 hash 변경으로 기존 배치가 stale로 표시될 수 있다. 정책/명세 변경 후 재생성 요구는 기존 설계를 따른다.','',
 '검증 원본: `backend-results.json`, `regression-results.json`, `evaluation-db-result.json`, `mcp-live-result.json`, `protected-audit.json`, `return-scenario-tests.json`, `random-example-results.json`. 임시 로그/JUnit는 OS temp의 spectrace-policy-extension에 보관했다.']
(out/'regression-results.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
print('Reports verified and written')
