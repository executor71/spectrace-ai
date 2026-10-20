from pathlib import Path
import os,sys,json
sys.stdout.reconfigure(encoding='utf8');os.environ['PLAYWRIGHT_BROWSERS_PATH']=str(Path('onboarding-browsers').resolve());sys.path.insert(0,str(Path('phase11-browser-tools').resolve()))
from playwright.sync_api import sync_playwright
out=Path('onboarding-evidence')
with sync_playwright() as p:
 b=p.webkit.launch(headless=True);context=b.new_context(**p.devices['iPhone 13'],locale='ko-KR',reduced_motion='reduce');page=context.new_page();errors=[];mutations=[];page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:mutations.append(r.url) if r.method in ['POST','PATCH','PUT','DELETE'] else None)
 page.goto('http://localhost:5173/#dashboard',wait_until='networkidle');page.get_by_role('heading',name='최근 요구사항 목록',exact=True).wait_for()
 assert not page.evaluate('document.documentElement.scrollWidth>innerWidth');assert page.locator('.guide-steps li').count()==4
 page.screenshot(path=str(out/'webkit-iphone13-landing.png'),full_page=True,animations='disabled');page.screenshot(path=str(out/'webkit-iphone13-viewport.png'),animations='disabled')
 page.get_by_role('button',name='예제 불러오기',exact=True).click();assert '본인의 신청을 직접 승인하는 것은 허용하지 않는다.' in page.locator('#requirement-description').input_value();assert not mutations;page.screenshot(path=str(out/'webkit-iphone13-example.png'),full_page=True,animations='disabled')
 page.get_by_role('button',name='메뉴 열기',exact=True).click();page.locator('nav[aria-label="기술 메뉴"]').get_by_role('button',name='기술 검증·관리',exact=True).click();page.get_by_role('heading',name='기술 검증·관리',exact=True).first.wait_for();assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
 result={'engine':'Playwright WebKit','device':'iPhone 13 emulation','viewport':page.viewport_size,'userAgent':page.evaluate('navigator.userAgent'),'realIPhoneSafari':False,'overflow':False,'fourStepsVisible':True,'exampleFillsFormOnly':True,'mobileMenuAndTechnicalNavigation':True,'consoleErrors':errors,'mutatingRequests':mutations};assert not errors
 (out/'webkit-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');b.close()
print(json.dumps(result,ensure_ascii=False,indent=2))
