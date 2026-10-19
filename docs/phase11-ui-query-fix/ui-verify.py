import sys,json
from pathlib import Path
sys.path.insert(0,str(Path('phase11-browser-tools').resolve()))
from playwright.sync_api import sync_playwright,expect
out=Path('ui-investigation');checks=[];responses=[];errors=[];mutations=[]
existing='b5270f71-c92c-48ae-8530-8946f1cfce62';recent='a8e38276-f033-4cb6-b1f4-b44811778a1b';empty='df315eb4-e6fd-4f97-a92c-565e1ba999f0'
with sync_playwright() as p:
 b=p.chromium.launch(channel='chrome',headless=True);page=b.new_page(viewport={'width':1440,'height':1100});page.on('pageerror',lambda e:errors.append(str(e)))
 page.on('request',lambda r:mutations.append(r.url) if r.method not in ['GET','HEAD','OPTIONS'] else None)
 def lookup(id):
  page.locator('#requirement-id').fill(id);page.locator('.lookup-form button').click();expect(page.locator('.requirement-result dd').first).to_have_text(id)
 def click(kind,status=200):
  sel='.analysis-actions button:nth-child(2)' if kind=='analysis' else '.test-cases .lookup-controls button:nth-child(2)'
  with page.expect_response(lambda r:r.url.endswith('/'+kind)) as res:page.locator(sel).click()
  r=res.value;assert r.status==status;responses.append({'url':r.url,'status':r.status,'body':r.json()});page.wait_for_timeout(150)
 page.goto('http://localhost:5173',wait_until='networkidle');lookup(existing);click('analysis');click('test-cases')
 expect(page.locator('.analysis-evidence')).to_have_count(5);expect(page.locator('.test-case-list li')).to_have_count(5);expect(page.locator('.test-case-detail')).to_be_visible()
 page.locator('.analysis-result').screenshot(path=str(out/'analysis-evidence.png'))
 page.locator('.test-cases').screenshot(path=str(out/'testcase-list-detail.png'));checks.append('real HTTP 200: analysis/evidence + 5 TC/detail')
 page.locator('.test-case-list button').nth(1).click();expect(page.locator('.test-case-list button').nth(1)).to_have_attribute('aria-pressed','true')
 lookup(existing);expect(page.locator('.analysis-result')).to_be_visible();expect(page.locator('.test-case-list button').nth(1)).to_have_attribute('aria-pressed','true');checks.append('same requirement parent lookup preserves results and selected TC')
 page.reload(wait_until='networkidle');lookup(existing);click('analysis');click('test-cases');expect(page.locator('.test-case-detail')).to_be_visible();checks.append('reload and GET persisted data')
 lookup(recent);expect(page.locator('.analysis-result')).to_have_count(0);expect(page.locator('.test-case-result')).to_have_count(0);click('analysis');click('test-cases');expect(page.locator('.test-cases [role=status]')).to_contain_text('0건');expect(page.locator('.test-case-list li')).to_have_count(0);expect(page.locator('.test-case-result')).to_contain_text('템플릿이 없습니다');page.locator('.test-cases').screenshot(path=str(out/'empty-200.png'));checks.append('real HTTP 200 empty testCases explains generation deferral')
 lookup(empty);click('analysis',404);click('test-cases',404);expect(page.locator('.analysis-panel [role=status]')).to_contain_text('HTTP 404');expect(page.locator('.test-cases [role=status]')).to_contain_text('HTTP 404');page.locator('.requirements').screenshot(path=str(out/'not-found-404.png'));checks.append('real HTTP 404 no stored data for both GETs')
 for kind,panel in [('analysis','.analysis-panel'),('test-cases','.test-cases')]:
  pattern='**/api/requirements/*/'+kind
  page.route(pattern,lambda route:route.fulfill(status=503,json={'code':'UPSTREAM_ERROR','message':'검증용 API 오류'}));click(kind,503);expect(page.locator(panel+' [role=alert]')).to_have_text('검증용 API 오류');page.unroute(pattern)
  page.route(pattern,lambda route:route.fulfill(status=200,json={'unexpected':True}));click(kind);expect(page.locator(panel+' [role=alert]')).to_contain_text('응답 형식');page.unroute(pattern)
 checks.append('intercepted HTTP 503 message and malformed HTTP 200 explicit error, no render crash')
 assert not errors and not mutations,(errors,mutations)
 (out/'verification.json').write_text(json.dumps({'result':'PASS','browser':b.version,'checks':checks,'consoleErrors':errors,'mutationRequests':mutations,'responses':responses},ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps({'checks':checks,'errors':errors,'mutationRequests':mutations},ensure_ascii=True));b.close()
