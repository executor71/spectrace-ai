import sys,re,json,os
from pathlib import Path
sys.path.insert(0,os.environ.get('PLAYWRIGHT_PYTHON_PATH',str(Path('phase11-browser-tools').resolve())))
from playwright.sync_api import sync_playwright,expect
out=Path(os.environ.get('PHASE12_EVIDENCE_DIR',str(Path(__file__).resolve().parent)));checks=[];errors=[];console=[]
with sync_playwright() as p:
 b=p.chromium.launch(channel='chrome',headless=True);page=b.new_page(viewport={'width':1440,'height':1000});page.on('pageerror',lambda e:errors.append(str(e)));page.on('console',lambda m:console.append(m.text) if m.type=='error' else None)
 def nav(text):page.get_by_role('navigation',name='주 메뉴').get_by_role('button',name=re.compile(text)).click()
 def shot(name):page.evaluate('window.scrollTo(0,0)');page.screenshot(path=str(out/name),full_page=True,animations='disabled')
 def lookup(id):
  page.locator('#requirement-id').fill(id)
  with page.expect_response(lambda r:r.url.endswith('/api/requirements/'+id)):page.locator('.lookup-form button').click()
 page.goto('http://localhost:5173',wait_until='networkidle');nav('AI 요구사항 분석');lookup('b5270f71-c92c-48ae-8530-8946f1cfce62');page.get_by_role('button',name='저장된 분석 조회',exact=True).click();expect(page.locator('.analysis-result')).to_be_visible()
 bad_labels=page.evaluate('''() => [...document.querySelectorAll('input,textarea,select')].filter(el=>el.getClientRects().length&&!el.closest('[hidden]')).filter(el=>!el.labels?.length&&!el.getAttribute('aria-label')).map(el=>el.id)''');assert not bad_labels,bad_labels
 page.get_by_role('button',name='저장된 분석 조회',exact=True).focus();page.keyboard.press('Shift+Tab');assert page.evaluate('getComputedStyle(document.activeElement).outlineStyle')!='none';checks.append('visible form fields have labels and keyboard focus has visible outline')
 page.route('**/api/requirements/*/analysis',lambda route:route.fulfill(status=503,json={'message':'검증용 분석 조회 오류'}));page.get_by_role('button',name='저장된 분석 조회',exact=True).click();expect(page.locator('.analysis-panel [role=alert]')).to_contain_text('검증용 분석 조회 오류');expect(page.locator('.analysis-result')).to_have_count(0);page.unroute('**/api/requirements/*/analysis');checks.append('intercepted API 503 message replaces stale analysis result')
 nav('Knowledge Graph');page.get_by_role('button',name='관계 그래프 조회').click();expect(page.locator('.edge-legend')).to_be_visible();assert page.locator('.edge-legend .edge-type').count()>1
 page.locator('.kg-overview > details summary').click();expect(page.locator('.kg-overview .kg-path .edge-type').first).to_be_visible();shot('graph-paths-desktop.png');checks.append('actual node/edge labels visually distinguished; stored execution paths exposed')
 for status in [404,503]:
  page.route('**/api/graph/find_requirement_context',lambda route,request,status=status:route.fulfill(status=status,json={'detail':'simulated graph absence/unavailability'}));page.get_by_role('button',name='관계 그래프 조회').click();expect(page.locator('.kg-overview')).to_have_count(0);expect(page.get_by_text('관계를 표시할 수 없습니다',exact=True)).to_be_visible();page.unroute('**/api/graph/find_requirement_context')
 shot('graph-unavailable.png');checks.append('intercepted Graph 404/503 produce a clear empty/error state without stale graph')
 nav('테스트케이스');page.get_by_role('button',name='저장된 테스트 조회',exact=True).click();expect(page.locator('.test-case-list li')).to_have_count(5);checks.append('other workflows remain available after graph error')
 assert not errors,errors
 (out/'edge-case-results.json').write_text(json.dumps({'result':'PASS','checks':checks,'runtimeErrors':errors,'consoleMessagesDuringExpectedHttpFailures':console},ensure_ascii=False,indent=2),encoding='utf8');b.close()
# Refresh isolated execution evidence at scroll top using saved results only.
with sync_playwright() as p:
 b=p.chromium.launch(channel='chrome',headless=True);page=b.new_page(viewport={'width':1440,'height':1000})
 def proxy(route):route.fulfill(response=route.fetch(url=route.request.url.replace('http://localhost:5173','http://localhost:18080')))
 page.route(re.compile(r'http://localhost:5173/api/(requirements|test-cases)(/|$)'),proxy)
 page.goto('http://localhost:5173#requirements',wait_until='networkidle');lookup('80e2d374-0825-4811-a11e-03ade256b6e8');nav('테스트케이스');page.get_by_role('button',name='저장된 테스트 조회',exact=True).click();expect(page.locator('.test-case-list li')).to_have_count(5);nav('실행 및 검증');expect(page.locator('.execution-result')).to_be_visible();shot('isolated-execution-pass.png');page.locator('.test-case-list button').nth(1).click();expect(page.locator('.execution-result')).to_contain_text('FAIL');shot('isolated-execution-fail.png')
 page.set_viewport_size({'width':390,'height':844});shot('execution-fail-mobile.png');b.close()
print(json.dumps(checks,ensure_ascii=True))

