from pathlib import Path
import json,os,sys
root=Path(__file__).resolve().parents[2];dest=root/'docs/phase6-evidence'
sys.path.insert(0,str(Path(os.environ['TEMP'])/'legacy-phase0-browser-tools'))
from playwright.sync_api import sync_playwright
rows=json.loads((dest/'measurement-results.json').read_text(encoding='utf-8'))
with sync_playwright() as p:
    browser=p.chromium.launch(channel='chrome',headless=True);page=browser.new_page(viewport={'width':1440,'height':1080});page.set_default_timeout(15000)
    errors=[];model_requests=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('request',lambda r:model_requests.append(r.url) if r.method=='POST' and ('/generate' in r.url or '/analysis' in r.url) else None)
    def lookup(rid):
        page.locator('#requirement-id').fill(rid);page.get_by_role('button',name='조회',exact=True).click()
        page.get_by_role('button',name='저장된 평가 조회',exact=True).click();page.locator('.evaluation-result').wait_for()
    page.goto('http://localhost:5173',wait_until='networkidle')
    captures=[]
    for row in rows:
        lookup(row['requirementId']);m=row['metrics']
        assert page.locator('.evaluation-missing-scenarios li').count()==len(m['scenarioCoverage']['missingScenarios'])
        assert page.locator('.evaluation-missing-documents li').count()==len(m['recallAt5']['missingDocumentIds'])
        if m['counts']['testCases']==0:assert 'N/A (0/0)' in page.locator('.evaluation-kpis').inner_text()
        page.get_by_text('시나리오별 매칭 결과',exact=True).click()
        name='react-'+row['dataset']['split']+'.png';page.locator('.evaluations').screenshot(path=str(dest/name));captures.append(name)
    lookup(rows[0]['requirementId'])
    with page.expect_response(lambda r:r.request.method=='POST' and r.url.endswith('/api/evaluations'),timeout=90000) as response:
        page.get_by_role('button',name='평가 실행',exact=True).click()
    assert response.value.status==201;created=response.value.json();assert created['metrics']==rows[0]['metrics']
    page.locator('#evaluation-mode').select_option('REVIEWED')
    with page.expect_response(lambda r:r.request.method=='POST' and r.url.endswith('/api/evaluations'),timeout=90000) as response:
        page.get_by_role('button',name='평가 실행',exact=True).click()
    reviewed=response.value.json();assert reviewed['contentMode']=='REVIEWED' and reviewed['status']=='COMPLETED'
    page.reload(wait_until='networkidle');lookup(rows[0]['requirementId'])
    assert reviewed['id'] in page.locator('.evaluation-result').inner_text()
    page.locator('.evaluation-history button').last.click();page.get_by_text('평가 ID: '+rows[0]['id'],exact=True).wait_for()
    page.get_by_text('TC별 validity checklist',exact=True).click();assert 'noStructuredContradiction: PASS' in page.locator('.evaluation-result').inner_text()
    page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    page.locator('.evaluations').screenshot(path=str(dest/'react-mobile.png'));page.set_viewport_size({'width':1440,'height':1080})
    unbound=json.loads((root/'docs/phase4-evidence/final-test-cases.json').read_text(encoding='utf-8'))[1]['requirementId']
    page.locator('#requirement-id').fill(unbound);page.get_by_role('button',name='조회',exact=True).click()
    page.get_by_role('button',name='평가 실행',exact=True).click();page.get_by_role('alert').filter(has_text='not bound').wait_for()
    page.locator('.evaluations').screenshot(path=str(dest/'react-unbound-error.png'))
    assert not errors and not model_requests
    result={'result':'PASS','browser':browser.version,'channel':'chrome','threeSplitsDisplayed':True,'missingScenariosDisplayed':True,'missingDocumentsDisplayed':True,'zeroTCValidityNA':True,
            'create201':True,'savedGetAndHistory':True,'reloadPersisted':True,'reviewedModeSeparate':True,'unbound409Visible':True,'mobileNoOverflow':True,'pageErrors':errors,'modelRequests':model_requests}
    (dest/'browser-results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    (dest/'browser-created-runs.json').write_text(json.dumps([created,reviewed],ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result));browser.close()
