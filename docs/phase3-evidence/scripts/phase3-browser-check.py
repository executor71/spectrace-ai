from pathlib import Path
import json,os,sys,time
root=Path(__file__).resolve().parents[3];dest=root/'docs/phase3-evidence'
sys.path.insert(0,str(Path(os.environ['TEMP'])/'legacy-phase0-browser-tools'))
from playwright.sync_api import sync_playwright
sample=json.loads((dest/'live-analysis-results.json').read_text(encoding='utf-8'))[0]
rid=sample['requirement']['id']
with sync_playwright() as p:
    browser=p.chromium.launch(channel='chrome',headless=True,timeout=15000)
    page=browser.new_page(viewport={'width':1440,'height':1080});page.set_default_timeout(12000)
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://localhost:5173',wait_until='networkidle',timeout=15000)
    assert page.locator('.status-online').count()==2
    page.locator('#requirement-id').fill(rid);page.get_by_role('button',name='조회',exact=True).click()
    page.get_by_role('button',name='저장된 분석 조회',exact=True).click()
    page.locator('.analysis-result').wait_for()
    assert page.locator('.analysis-evidence').count()==5
    assert sample['analysis']['confirmedConditions'][0]['text'] in page.locator('.analysis-result').inner_text()
    print('PASS React stored analysis, evidence and both health cards',flush=True)
    page.locator('#requirement-title-input').fill(sample['requirement']['title'])
    page.locator('#requirement-description').fill(sample['requirement']['description'])
    with page.expect_response(lambda r:r.url.endswith('/api/requirements') and r.request.method=='POST') as created:
        page.get_by_role('button',name='요구사항 저장',exact=True).click()
    assert created.value.status==201
    rid=created.value.json()['id']
    page.locator('.requirement-result').get_by_text(rid,exact=True).wait_for()
    page.locator('.requirement-result').get_by_text('DRAFT',exact=True).wait_for()
    print('PASS React creates new Requirement',rid,flush=True)
    start=time.perf_counter()
    with page.expect_response(lambda r:r.url.endswith('/analysis') and r.request.method=='POST',timeout=650000) as pending:
        page.get_by_role('button',name='요구사항 분석',exact=True).click()
        assert page.get_by_role('button',name='요구사항 분석',exact=True).is_disabled()
        print('START React real analysis POST',flush=True)
    response=pending.value
    assert response.status==200,response.text()
    page.get_by_role('button',name='요구사항 분석',exact=True).wait_for(state='visible')
    page.wait_for_function("!Array.from(document.querySelectorAll('button')).find(b => b.textContent === '요구사항 분석').disabled")
    page.locator('.requirement-result').get_by_text('ANALYZED',exact=True).wait_for()
    assert page.locator('.analysis-evidence').count()==5
    page.reload(wait_until='networkidle')
    page.locator('#requirement-id').fill(rid);page.get_by_role('button',name='조회',exact=True).click()
    page.get_by_role('button',name='저장된 분석 조회',exact=True).click();page.locator('.analysis-result').wait_for()
    assert page.locator('.analysis-evidence').count()==5
    assert not errors,errors
    page.screenshot(path=str(dest/'react-analysis.png'),full_page=True)
    result={'result':'PASS','requirementId':rid,'analysisPostStatus':response.status,'elapsedSeconds':round(time.perf_counter()-start,3),
        'healthCards':2,'evidenceCards':5,'requirementCreatedInReact':True,'statusUpdatedToAnalyzed':True,'persistedAfterReload':True,'browserErrors':errors}
    (dest/'browser-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result),flush=True);browser.close()
