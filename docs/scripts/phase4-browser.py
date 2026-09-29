from pathlib import Path
import json,os,sys,time

root=Path(__file__).resolve().parents[2];dest=root/'docs/phase4-evidence'
sys.path.insert(0,str(Path(os.environ['TEMP'])/'legacy-phase0-browser-tools'))
from playwright.sync_api import sync_playwright
rows=json.loads((dest/'final-test-cases.json').read_text(encoding='utf-8'))
with sync_playwright() as p:
    browser=p.chromium.launch(channel='chrome',headless=True,timeout=15000)
    page=browser.new_page(viewport={'width':1440,'height':1080});page.set_default_timeout(12000)
    errors=[];posts=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.on('request',lambda request:posts.append(request.url) if request.method=='POST' else None)
    page.goto('http://localhost:5173',wait_until='networkidle',timeout=15000)
    assert page.locator('.status-online').count()==2
    page.locator('#requirement-id').fill(rows[0]['requirementId']);page.get_by_role('button',name='조회',exact=True).click()
    page.get_by_role('button',name='저장된 분석 조회',exact=True).click();page.locator('.analysis-result').wait_for()
    assert page.locator('.analysis-evidence').count()==5
    page.get_by_role('button',name='저장된 테스트 조회',exact=True).click();page.locator('.test-case-detail').wait_for()
    assert page.locator('.test-case-list button').count()==5
    for button in page.locator('.test-case-list button').all():
        button.click();assert '실행 가능 후보: false' in page.locator('.test-case-detail').inner_text()
        assert page.locator('.test-case-evidence details').count()>=3
    page.locator('.test-case-evidence summary').first.click()
    assert 'documentId:' in page.locator('.test-case-evidence').inner_text()
    page.screenshot(path=str(dest/'react-test-cases.png'),full_page=True)
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1')
    page.screenshot(path=str(dest/'react-test-cases-mobile.png'),full_page=True)
    page.set_viewport_size({'width':1440,'height':1080})
    for row in rows[1:]:
        page.locator('#requirement-id').fill(row['requirementId']);page.get_by_role('button',name='조회',exact=True).click()
        page.get_by_role('button',name='저장된 테스트 조회',exact=True).click();page.locator('.test-case-result').wait_for()
        assert page.locator('.test-case-list button').count()==0
        assert '사용자 확인 필요' in page.locator('.test-case-result').inner_text()
    page.screenshot(path=str(dest/'react-clarification.png'),full_page=True)
    # Browser POST path is verified on a no-evidence case; no additional LLM call.
    with page.expect_response(lambda r:r.url.endswith('/test-cases/generate')) as response:
        page.get_by_role('button',name='테스트 생성',exact=True).click()
    assert response.value.status==200 and response.value.json()['llmCalls']==0
    page.reload(wait_until='networkidle')
    page.locator('#requirement-id').fill(rows[0]['requirementId']);page.get_by_role('button',name='조회',exact=True).click()
    page.get_by_role('button',name='저장된 테스트 조회',exact=True).click();page.locator('.test-case-detail').wait_for()
    assert page.locator('.test-case-list button').count()==5
    assert not errors,errors
    result={'result':'PASS','healthCards':2,'analysisEvidenceCards':5,'typesDisplayed':5,'referenceDetailsOpened':True,
            'negativeCasesDisplayed':4,'mobileNoHorizontalOverflow':True,'persistedAfterReload':True,
            'generationPostStatus':response.value.status,'extraLlmCalls':0,'browserErrors':errors}
    (dest/'browser-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result),flush=True);browser.close()
