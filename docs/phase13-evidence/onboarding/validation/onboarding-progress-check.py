from pathlib import Path
import sys,json,asyncio
sys.stdout.reconfigure(encoding='utf8');sys.path.insert(0,str(Path('phase11-browser-tools').resolve()))
from playwright.async_api import async_playwright
out=Path('onboarding-evidence')
async def main():
 async with async_playwright() as p:
  b=await p.chromium.launch(channel='chrome',headless=True);page=await b.new_page(viewport={'width':1440,'height':900},reduced_motion='reduce');await page.goto('http://localhost:5173/#dashboard',wait_until='networkidle');await page.get_by_role('heading',name='최근 요구사항 목록',exact=True).wait_for()
  data=await (await page.request.get('http://localhost:5173/api/dashboard/summary')).json();target=next(r for r in data['requirements'] if r['counts']['PASS'])
  await page.locator('.p13-toolbar select').select_option(target['id']);await page.locator('#dashboard-requirements').get_by_role('button',name='상세 보기',exact=True).click();await page.locator('.p13-context-actions').get_by_role('button',name='변경 요청 분석',exact=True).click()
  calls=[]
  async def slow(route):
   calls.append(route.request.method);await asyncio.sleep(4);await route.fulfill(status=429,json={'code':'ANALYSIS_BUSY','message':'mocked busy'})
  await page.route('**/api/requirements/*/analysis',slow);button=page.get_by_role('button',name='변경 요청 분석 시작',exact=True);await button.click();await page.locator('.analysis-panel .loading-panel').wait_for();await page.wait_for_timeout(2200)
  text=await page.locator('.analysis-panel .loading-panel').inner_text();assert '경과시간' in text and ('2초' in text or '3초' in text);assert await button.is_disabled();await page.screenshot(path=str(out/'analysis-pending-timer-mocked.png'),full_page=True,animations='disabled');await page.get_by_role('alert').filter(has_text='다른 분석이 진행 중이라').wait_for();await page.wait_for_timeout(500);assert calls==['POST']
  (out/'progress-results.json').write_text(json.dumps({'fixture':'intercepted POST delays four seconds and returns 429; no actual analysis request forwarded','elapsedTimerAdvances':True,'duplicateStartDisabled':True,'noAutomaticRetry':True,'requestCount':len(calls)},ensure_ascii=False,indent=2),encoding='utf8');await b.close()
asyncio.run(main());print('elapsed timer, disabled button and manual retry verified')
