from pathlib import Path
import os,sys,json
root=Path(__file__).resolve().parents[2];dest=root/'docs/phase8-evidence'
sys.path.insert(0,str(Path(os.environ['TEMP'])/'legacy-phase0-browser-tools'))
from playwright.sync_api import sync_playwright,expect
fixture=json.loads((root/'docs/phase7-evidence/synthetic-cases.json').read_text(encoding='utf-8'))
with sync_playwright() as p:
    browser=p.chromium.launch(channel='chrome',headless=True);page=browser.new_page(viewport={'width':1440,'height':1080});page.set_default_timeout(20000)
    errors=[];model=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('request',lambda r:model.append(r.url) if r.method=='POST' and ('/generate' in r.url or '/analysis' in r.url) else None)
    def lookup():
        page.locator('#requirement-id').fill(fixture['requirementId']);page.get_by_role('button',name='조회',exact=True).click()
        page.get_by_role('button',name='저장된 분석 조회',exact=True).click();page.locator('.analysis-result').wait_for()
        page.get_by_role('button',name='저장된 테스트 조회',exact=True).click();page.locator('.test-case-detail').wait_for()
    page.goto('http://localhost:5173',wait_until='networkidle');lookup();runs=[]
    for index,result in [(0,'PASS'),(1,'FAIL')]:
        page.locator('.test-case-list button').nth(index).click();expect(page.get_by_role('button',name='Dummy 실행',exact=True)).to_be_enabled()
        with page.expect_response(lambda r:r.request.method=='POST' and r.url.endswith('/executions')) as response:page.get_by_role('button',name='Dummy 실행',exact=True).click()
        run=response.value.json();assert response.value.status==201 and run['result']==result;runs.append(run)
        expect(page.locator('.execution-result')).to_contain_text(run['executionId'])
        page.locator('.test-case-executions').screenshot(path=str(dest/('phase7-regression-'+result.lower()+'.png')))
    page.reload(wait_until='networkidle');lookup();page.locator('.test-case-list button').nth(1).click();expect(page.locator('.execution-result')).to_contain_text(runs[1]['executionId'])
    assert not errors and not model
    report={'result':'PASS','browser':'Chrome '+browser.version,'requirementAnalysisReviewFlow':True,'dummyPass':runs[0]['executionId'],'dummyFail':runs[1]['executionId'],'reloadPersisted':True,'pageErrors':errors,'modelRequests':model}
    (dest/'browser-regression.json').write_text(json.dumps(report,indent=2));print(json.dumps(report));browser.close()
