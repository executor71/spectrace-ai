from pathlib import Path
import sys,json,urllib.request
out=Path('phase13-evidence');sys.path.insert(0,str(Path('phase11-browser-tools').resolve()))
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
 b=p.chromium.launch(channel='chrome',headless=True);page=b.new_page(viewport={'width':1440,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto('http://localhost:5173',wait_until='networkidle');page.get_by_role('heading',name='業務現況').count() # no action
 page.get_by_role('heading',name='최근 요구사항 목록',exact=True).wait_for()
 data=page.request.get('http://localhost:5173/api/dashboard/summary').json();assert data['counts']['requirements']==28 and data['counts']['total']==15
 (out/'phase13-a-summary.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
 page.screenshot(path=str(out/'phase13-a-desktop.png'),full_page=True)
 page.get_by_role('button',name='검토 대기 TC',exact=False).click();assert page.locator('#dashboard-cases select').input_value()=='DRAFT'
 target=next(r for r in data['requirements'] if r['counts']['total'])
 page.locator('.p13-toolbar select').select_option(target['id']);page.locator('#dashboard-requirements').get_by_role('button',name='상세 보기',exact=True).click()
 page.get_by_role('article',name='요구사항 상세').wait_for();assert page.get_by_role('article',name='요구사항 상세').inner_text().find(target['title'])>=0
 page.screenshot(path=str(out/'phase13-a-detail.png'),full_page=True)
 assert not errors,errors
 (out/'phase13-a-check.json').write_text(json.dumps({'counts':data['counts'],'cardFilter':True,'selectionWithoutUUID':True,'errors':errors},ensure_ascii=False,indent=2),encoding='utf8');b.close()
print('Phase 13-A verified')
