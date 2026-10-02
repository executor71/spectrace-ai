from pathlib import Path
import json,os,sys
root=Path(__file__).resolve().parents[2];dest=root/'docs/phase7-evidence'
sys.path.insert(0,str(Path(os.environ['TEMP'])/'legacy-phase0-browser-tools'))
from playwright.sync_api import sync_playwright,expect
fixture=json.loads((dest/'synthetic-cases.json').read_text(encoding='utf-8'))
with sync_playwright() as p:
    browser=p.chromium.launch(channel='chrome',headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1080});page.set_default_timeout(20000)
    errors=[];model_requests=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('request',lambda r:model_requests.append(r.url) if r.method=='POST' and ('/generate' in r.url or '/analysis' in r.url) else None)
    def lookup():
        page.locator('#requirement-id').fill(fixture['requirementId']);page.get_by_role('button',name='조회',exact=True).click()
        page.get_by_role('button',name='저장된 분석 조회',exact=True).click();page.locator('.analysis-result').wait_for()
        page.get_by_role('button',name='저장된 테스트 조회',exact=True).click();page.locator('.test-case-detail').wait_for()
    def select(index):
        page.locator('.test-case-list button').nth(index).click();page.locator('.execution-eligibility').wait_for()
    def approve():
        with page.expect_response(lambda r:r.request.method=='POST' and r.url.endswith('/approve')) as response:
            page.get_by_role('button',name='승인',exact=True).click()
        assert response.value.status==200
        expect(page.get_by_role('button',name='Dummy 실행',exact=True)).to_be_enabled()
    def execute(result,name):
        with page.expect_response(lambda r:r.request.method=='POST' and r.url.endswith('/executions')) as response:
            page.get_by_role('button',name='Dummy 실행',exact=True).click()
        run=response.value.json();assert response.value.status==201 and run['result']==result,(response.value.status,run)
        expect(page.locator('.execution-result')).to_contain_text(run['executionId'])
        page.locator('.test-case-executions').screenshot(path=str(dest/name))
        return run
    page.goto('http://localhost:5173',wait_until='networkidle');lookup()
    page.locator('.analysis-result').screenshot(path=str(dest/'01-requirement-analysis.png'))
    select(0)
    if 'approvalStatus: DRAFT' in page.locator('.execution-eligibility').inner_text():
        expect(page.get_by_role('button',name='Dummy 실행',exact=True)).to_be_disabled()
        page.locator('.test-case-executions').screenshot(path=str(dest/'02-draft-blocked.png'));approve()
    normal=execute('PASS','03-pass.png')
    select(1);expect(page.get_by_role('button',name='Dummy 실행',exact=True)).to_be_disabled();approve()
    defect=execute('FAIL','04-intentional-fail.png');assert len(defect['mismatches'])==4
    (dest/'fail.json').write_text(json.dumps(defect,ensure_ascii=False,indent=2),encoding='utf-8')
    page.reload(wait_until='networkidle');lookup();select(1)
    expect(page.locator('.execution-result')).to_contain_text(defect['executionId']);expect(page.locator('.execution-result')).to_contain_text('FAIL')
    page.locator('.test-case-executions').screenshot(path=str(dest/'05-reload-persisted.png'))
    repeated=execute('FAIL','06-repeat-fail.png')
    for field in ['actual','expected','result','mismatches']:assert repeated[field]==defect[field]
    page.locator('.execution-history button').nth(1).click();expect(page.locator('.execution-result')).to_contain_text(defect['executionId'])
    select(2);expect(page.locator('.execution-result')).to_contain_text('AVAILABLE')
    asset=execute('PASS','07-asset-pass.png')
    select(3);expect(page.get_by_role('button',name='Dummy 실행',exact=True)).to_be_disabled();expect(page.locator('.execution-eligibility')).to_contain_text('executionEligible: false')
    page.locator('.test-case-executions').screenshot(path=str(dest/'08-allowlist-blocked.png'))
    select(1);page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    page.locator('.test-case-executions').screenshot(path=str(dest/'09-mobile.png'))
    assert not errors and not model_requests
    result={'result':'PASS','browser':browser.version,'channel':'chrome','requirementAnalysisTestCaseFlow':True,'draftDisabled':True,'approvedEnabled':True,'passExecutionId':normal['executionId'],'failExecutionId':defect['executionId'],'assetExecutionId':asset['executionId'],'reloadPersisted':True,'repeatReproducible':True,'historySelection':True,'allowListBlocked':True,'mobileNoOverflow':True,'pageErrors':errors,'modelRequests':model_requests}
    (dest/'browser-results.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result));browser.close()
