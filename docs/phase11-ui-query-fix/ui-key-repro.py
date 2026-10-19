import sys,json
from pathlib import Path
sys.path.insert(0,str(Path('phase11-browser-tools').resolve()))
from playwright.sync_api import sync_playwright,expect
out=Path('ui-investigation');results=[]
with sync_playwright() as p:
 for original in [True,False]:
  b=p.chromium.launch(channel='chrome',headless=True);page=b.new_page();logs=[];page.on('console',lambda m: logs.append({'type':m.type,'text':m.text}) if m.type in ['error','warning'] else None)
  if original:page.route('**/src/Requirements.tsx',lambda route:route.fulfill(status=200,content_type='application/javascript',body=(out/'live-Requirements.tsx.txt').read_text(encoding='utf8')))
  page.goto('http://localhost:5173',wait_until='networkidle')
  for id in ['b5270f71-c92c-48ae-8530-8946f1cfce62','a8e38276-f033-4cb6-b1f4-b44811778a1b']:
   page.locator('#requirement-id').fill(id)
   with page.expect_response(lambda r:r.url.endswith('/'+id)):page.locator('.lookup-form button').click()
   expect(page.locator('.requirement-result dd').first).to_have_text(id)
   if id.startswith('b527'):
    page.locator('.analysis-actions button:nth-child(2)').click();expect(page.locator('.analysis-result')).to_be_visible()
  results.append({'original':original,'analysisResultsAfterSwitch':page.locator('.analysis-result').count(),'analysisPanelsAfterSwitch':page.locator('.analysis-panel').count(),'console':logs})
  b.close()
(out/'key-reproduction.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(results,ensure_ascii=True)[:2500])
