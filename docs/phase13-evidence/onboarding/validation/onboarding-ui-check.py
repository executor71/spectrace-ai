from pathlib import Path
import sys,json,hashlib
sys.stdout.reconfigure(encoding='utf8');sys.path.insert(0,str(Path('phase11-browser-tools').resolve()))
from playwright.sync_api import sync_playwright
out=Path('onboarding-evidence');result={'viewports':[],'states':{},'interceptedOnly':[]}
with sync_playwright() as p:
 b=p.chromium.launch(channel='chrome',headless=True);errors=[]
 for width in [1920,1440,1024,390]:
  page=b.new_page(viewport={'width':width,'height':900 if width!=390 else 844},reduced_motion='reduce');page.on('pageerror',lambda e:errors.append(str(e)));page.goto('http://localhost:5173/#dashboard',wait_until='networkidle');page.get_by_role('heading',name='최근 요구사항 목록',exact=True).wait_for()
  assert page.locator('.guide-steps li').count()==4;assert page.get_by_role('button',name='예제 불러오기',exact=True).is_visible();assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
  page.screenshot(path=str(out/f'landing-{width}.png'),full_page=True,animations='disabled');page.screenshot(path=str(out/f'landing-{width}-viewport.png'),animations='disabled');result['viewports'].append({'width':width,'overflow':False,'fourSteps':True});page.close()
 page=b.new_page(viewport={'width':1440,'height':900},reduced_motion='reduce');page.on('pageerror',lambda e:errors.append(str(e)));page.goto('http://localhost:5173/#dashboard',wait_until='networkidle');page.get_by_role('heading',name='최근 요구사항 목록',exact=True).wait_for()
 data=page.request.get('http://localhost:5173/api/dashboard/summary').json();target=next(r for r in data['requirements'] if r['counts']['PASS']>0)
 page.locator('.p13-toolbar select').select_option(target['id']);page.locator('#dashboard-requirements').get_by_role('button',name='상세 보기',exact=True).click()
 page.locator('.p13-context-actions').get_by_role('button',name='변경 요청 분석',exact=True).click()
 page.route('**/api/requirements/*/analysis',lambda route:route.fulfill(status=404,json={'message':'missing'}) if route.request.method=='GET' else route.fulfill(status=429,json={'code':'ANALYSIS_BUSY','message':'busy'}))
 page.get_by_role('button',name='저장된 분석 조회',exact=True).click();page.get_by_text('AI 분석 결과가 아직 없습니다.',exact=False).wait_for();page.screenshot(path=str(out/'state-no-analysis-mocked.png'),full_page=True,animations='disabled');result['states']['noAnalysisCauseAndNextAction']=True
 page.get_by_role('button',name='변경 요청 분석 시작',exact=True).click();page.get_by_role('alert').filter(has_text='다른 분석이 진행 중이라').wait_for();page.screenshot(path=str(out/'state-analysis-busy-mocked.png'),full_page=True,animations='disabled');result['states']['analysisBusyCauseAndManualNextAction']=True;result['interceptedOnly'].append('POST analysis returns 429; never forwarded to backend')
 page.unroute('**/api/requirements/*/analysis');page.locator('.p13-context-actions').get_by_role('button',name='테스트 자동 생성',exact=True).click()
 empty={'requirementId':target['id'],'generationId':'mocked-ui-empty','testCases':[],'clarificationRequired':['합성 테스트용 확인 사유: 업무조건을 더 구체적으로 입력해 주세요.'],'uncoveredTypes':['NORMAL'],'executionDecisions':[],'sourceAnalysis':{'evidence':[]},'stale':False,'generationLatencyMs':0,'llmCalls':0}
 page.route('**/api/requirements/*/test-cases/generate',lambda route:route.fulfill(status=200,json=empty));page.locator('.test-cases').get_by_role('button',name='테스트 자동 생성',exact=True).click();page.get_by_role('button',name='변경 요청 분석으로 돌아가기',exact=True).wait_for();page.get_by_text('조건 확인이 필요하여 테스트 생성 보류',exact=True).wait_for();page.screenshot(path=str(out/'state-generation-held-mocked.png'),full_page=True,animations='disabled');result['states']['generationHeldCauseAndNextAction']=True;result['interceptedOnly'].append('POST test generation returns zero cases; never forwarded to backend')
 page.locator('.p13-context-actions').get_by_role('button',name='기술 검증',exact=True).click();page.get_by_text('평가셋 미등록:',exact=False).wait_for();page.screenshot(path=str(out/'state-unregistered-evaluation.png'),full_page=True,animations='disabled');result['states']['evaluationNotRegisteredExplained']=True
 page.get_by_text('기술 용어와 검증 범위 알아보기',exact=True).click();assert page.get_by_text('RAG · 관련 자료 검색',exact=True).is_visible();assert page.get_by_text('MCP · 도구 연결 규약',exact=True).is_visible();page.screenshot(path=str(out/'technical-management.png'),full_page=True,animations='disabled');result['technicalTermsInManagementArea']=True
 page.locator('.p13-context-actions').get_by_role('button',name='변경 영향 관계 확인',exact=True).click()
 with page.expect_response(lambda r:'/api/graph/find_requirement_context' in r.url) as graph:page.get_by_role('button',name='변경 영향 관계 조회',exact=True).click()
 result['graphReadHTTP']=graph.value.status;page.screenshot(path=str(out/'graph-preserved.png'),full_page=True,animations='disabled');page.close();b.close()
result['consoleErrors']=errors;assert not errors
root=Path('D:/MASTER과정');baseline=json.loads((out/'baseline.json').read_text(encoding='utf8'))
for name,digest in baseline['hashes'].items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest,name
result['protectedSourceFilesUnchanged']=len(baseline['hashes']);(out/'ui-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(result,ensure_ascii=False,indent=2))
