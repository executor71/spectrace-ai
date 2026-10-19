import sys,json,re,os
from pathlib import Path
sys.path.insert(0,os.environ.get('PLAYWRIGHT_PYTHON_PATH',str(Path('phase11-browser-tools').resolve())))
from playwright.sync_api import sync_playwright,expect
out=Path(os.environ.get('PHASE12_EVIDENCE_DIR',str(Path(__file__).resolve().parent)));checks=[];errors=[];mutations=[];sizes=[];consoleErrors=[]
labels={'dashboard':'대시보드','requirements':'요구사항 관리','analysis':'AI 요구사항 분석','testcases':'테스트케이스','review':'검토 및 승인','execution':'실행 및 검증','evaluation':'Ground Truth 평가','graph':'Knowledge Graph'}
with sync_playwright() as p:
 b=p.chromium.launch(channel='chrome',headless=True);page=b.new_page(viewport={'width':1440,'height':1000});page.set_default_timeout(12000);page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:mutations.append({'method':r.method,'url':r.url}) if r.method not in ['GET','HEAD','OPTIONS'] else None)
 page.on('console',lambda message:consoleErrors.append(message.text) if message.type=='error' else None)
 def capture(**options):
  page.evaluate('window.scrollTo(0,0)')
  page.screenshot(animations='disabled',**options)
 def nav(key):
  if page.viewport_size['width'] <= 700 and not page.locator('.sidebar').evaluate('(el)=>el.classList.contains("is-open")'):page.get_by_role('button',name='메뉴 열기',exact=True).click()
  page.get_by_role('navigation',name='주 메뉴').get_by_role('button',name=re.compile(labels[key])).click();expect(page.locator('.page-heading h1')).to_have_text(labels[key])
 def lookup(id):
  page.locator('#requirement-id').fill(id)
  with page.expect_response(lambda r:r.url.endswith('/api/requirements/'+id)) as response:page.locator('.lookup-form button').click()
  assert response.value.status==200
  expect(page.locator('.context-identity strong')).not_to_have_text('선택된 요구사항이 없습니다')
 def overflow(label):
  values=page.evaluate('({width:innerWidth,scroll:document.documentElement.scrollWidth})');sizes.append({'screen':label,**values});assert values['scroll']<=values['width'],(label,values)
 page.goto('http://localhost:5173',wait_until='networkidle');expect(page.locator('.connection-online')).to_have_count(2);overflow('dashboard-1440');capture(path=str(out/'dashboard-desktop.png'),full_page=True)
 nav('requirements');page.locator('#requirement-title-input').fill('화면 이동 중 유지되는 작성 제목');page.locator('#requirement-description').fill('입력 중인 요구사항 내용입니다.');nav('analysis');expect(page.get_by_text('먼저 요구사항을 선택해 주세요',exact=True)).to_be_visible();nav('requirements');expect(page.locator('#requirement-title-input')).to_have_value('화면 이동 중 유지되는 작성 제목');checks.append('requirement draft survives navigation')
 lookup('b5270f71-c92c-48ae-8530-8946f1cfce62');capture(path=str(out/'requirements-desktop.png'),full_page=True)
 nav('analysis');page.get_by_role('button',name='저장된 분석 조회',exact=True).click();expect(page.locator('.analysis-evidence')).to_have_count(5);capture(path=str(out/'analysis-desktop.png'),full_page=True);page.locator('.analysis-card a').first.click();expect(page.locator('.page-heading h1')).to_have_text('AI 요구사항 분석');checks.append('real saved analysis/evidence displayed; evidence anchor preserves active view')
 nav('testcases');page.get_by_role('button',name='저장된 테스트 조회',exact=True).click();expect(page.locator('.test-case-list li')).to_have_count(5);expect(page.locator('.test-scenario-content')).to_be_visible();capture(path=str(out/'testcases-desktop.png'),full_page=True)
 page.locator('#test-type-filter').select_option('AUTHORIZATION');expect(page.locator('.test-case-list li')).to_have_count(1);page.locator('#test-type-filter').select_option('ALL');checks.append('real TC list, typed tags, status, detail and filter')
 nav('review');page.locator('.review-editor summary').click();old=page.locator('#review-scenario').input_value();page.locator('#review-scenario').fill(old+' 미저장 검토');page.locator('#review-comment').fill('화면 이동 보존 확인');nav('execution');expect(page.get_by_role('button',name='Dummy 실행',exact=True)).to_be_disabled();nav('review');expect(page.locator('#review-comment')).to_have_value('화면 이동 보존 확인');expect(page.locator('#review-scenario')).to_have_value(old+' 미저장 검토');page.locator('#review-scenario').fill(old);page.locator('.review-editor summary').click();capture(path=str(out/'review-desktop.png'),full_page=True);checks.append('review edits survive navigation and dirty content blocks execution')
 lookup('80e2d374-0825-4811-a11e-03ade256b6e8');nav('testcases');page.get_by_role('button',name='저장된 테스트 조회',exact=True).click();expect(page.locator('.test-case-list li')).to_have_count(5);nav('execution');expect(page.locator('.execution-result')).to_be_visible();capture(path=str(out/'execution-pass-desktop.png'),full_page=True);page.locator('.test-case-list button').nth(1).click();expect(page.locator('.execution-result')).to_contain_text('FAIL');expect(page.locator('.mismatch-panel.has-mismatch')).to_be_visible();capture(path=str(out/'execution-fail-desktop.png'),full_page=True);checks.append('existing real PASS/FAIL history and TC revisions; Expected/Actual and mismatch display')
 nav('evaluation');expect(page.get_by_text('현재 요구사항은 정량평가 대상에 등록되어 있지 않습니다',exact=True)).to_be_visible();expect(page.get_by_role('button',name='평가 실행',exact=True)).to_be_disabled();capture(path=str(out/'evaluation-unregistered.png'),full_page=True)
 page.locator('#evaluation-sample').select_option('b5270f71-c92c-48ae-8530-8946f1cfce62');page.get_by_role('button',name='샘플 요구사항 조회').click();expect(page.get_by_role('button',name='평가 실행',exact=True)).to_be_enabled();page.get_by_role('button',name='저장된 평가 조회',exact=True).click();expect(page.locator('.evaluation-metric-grid .metric-card')).to_have_count(3);capture(path=str(out/'evaluation-desktop.png'),full_page=True);checks.append('Frozen eligibility guidance and real saved evaluation KPI cards/table')
 nav('graph');page.get_by_role('button',name='관계 그래프 조회').click();expect(page.locator('.kg-overview')).to_be_visible();capture(path=str(out/'graph-desktop.png'),full_page=True);page.locator('.kg-BusinessRule button').first.click();expect(page.locator('.kg-detail')).to_be_visible();checks.append('real Knowledge Graph overview and rule impact paths')
 for width,height in [(1024,900),(390,844)]:
  page.set_viewport_size({'width':width,'height':height})
  for key in labels:
   nav(key);overflow(f'{key}-{width}')
   if key in ['dashboard','testcases','execution','evaluation','graph']:
    capture(path=str(out/f'{key}-{width}.png'),full_page=True)
  nav('evaluation');assert page.locator('.table-scroll').evaluate('(el)=>el.scrollWidth > el.clientWidth') if width==390 else True
 checks.append('all 8 screens at 1024px and 390px: no document horizontal overflow; table scrolls internally')
 page.get_by_role('button',name='메뉴 열기',exact=True).click();expect(page.locator('.sidebar')).to_be_visible();capture(path=str(out/'drawer-mobile.png'),full_page=False);page.keyboard.press('Shift+Tab');assert page.evaluate('document.activeElement.closest(".sidebar") !== null');page.keyboard.press('Escape');expect(page.locator('.sidebar')).not_to_be_visible();expect(page.get_by_role('button',name='메뉴 열기',exact=True)).to_be_focused();checks.append('mobile drawer keyboard focus trap and Escape restoration')
 normalConsoleErrors=consoleErrors.copy();assert not normalConsoleErrors,normalConsoleErrors
 page.set_viewport_size({'width':1440,'height':1000});nav('analysis');pending=[];page.route('**/api/requirements/*/analysis',lambda route:pending.append(route) if route.request.method=='POST' else route.continue_());page.get_by_role('button',name='요구사항 분석',exact=True).click();expect(page.locator('.loading-panel')).to_contain_text('경과시간 0분 2초',timeout=6000);capture(path=str(out/'analysis-loading.png'),full_page=True);nav('dashboard');expect(page.locator('.analysis-indicator')).to_contain_text('분석 처리 중');nav('analysis');pending[0].fulfill(status=429,json={'code':'ANALYSIS_BUSY','message':'Busy'});expect(page.locator('.analysis-panel [role=alert]')).to_contain_text('다른 AI 분석이 진행 중입니다');capture(path=str(out/'analysis-busy-429.png'),full_page=True);page.unroute('**/api/requirements/*/analysis');checks.append('intercepted busy analysis: spinner/elapsed time persists during navigation; 429 Korean guidance; no real LLM call')
 assert not errors,errors
 assert all('/api/graph/' in request['url'] or request['url'].endswith('/analysis') for request in mutations),mutations
 (out/'live-chrome-results.json').write_text(json.dumps({'result':'PASS','browser':b.version,'checks':checks,'errors':errors,'normalConsoleErrors':normalConsoleErrors,'expectedHttpConsoleMessages':consoleErrors[len(normalConsoleErrors):],'mutationRequests':mutations,'responsive':sizes},ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps({'checks':checks,'errors':errors},ensure_ascii=True));b.close()
