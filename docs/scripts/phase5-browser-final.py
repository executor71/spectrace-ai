from pathlib import Path
import json,os,sys,urllib.request
root=Path(__file__).resolve().parents[2];dest=root/'docs/phase5-evidence'
sys.path.insert(0,str(Path(os.environ['TEMP'])/'legacy-phase0-browser-tools'))
from playwright.sync_api import sync_playwright
report=json.loads((dest/'browser-results.json').read_text(encoding='utf-8'));requirement=report['requirementId']
with urllib.request.urlopen(f'http://localhost:8080/api/requirements/{requirement}/test-cases') as response:cases=json.load(response)['testCases']
original=cases[2]
with sync_playwright() as p:
    browser=p.chromium.launch(channel='chrome',headless=True);page=browser.new_page(viewport={'width':1440,'height':1080});page.set_default_timeout(15000)
    errors=[];posts=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.on('request',lambda r:posts.append(r.url) if r.method=='POST' else None)
    def lookup():
        page.locator('#requirement-id').fill(requirement);page.get_by_role('button',name='조회',exact=True).click()
        page.get_by_role('button',name='저장된 분석 조회',exact=True).click();page.locator('.analysis-result').wait_for()
        page.get_by_role('button',name='저장된 테스트 조회',exact=True).click();page.locator('.test-case-detail').wait_for()
    def save():
        with page.expect_response(lambda r:r.request.method=='GET' and r.url.endswith('/test-cases')):
            with page.expect_response(lambda r:r.request.method=='PATCH') as response:
                page.get_by_role('button',name='수정 저장',exact=True).click()
        assert response.value.status==200;return response.value.json()
    page.goto('http://localhost:5173',wait_until='networkidle');lookup();page.locator('.test-case-list button').nth(2).click()
    for key,value in {'scenario':'Five editable fields verified in Chrome','preconditions':'Reviewed precondition','steps':'Reviewed step','input':'{invalid','expectedResult':json.dumps({'description':'Reviewed result','assertions':[]})}.items():page.locator('#review-'+key).fill(value)
    page.get_by_role('button',name='수정 저장',exact=True).click();page.get_by_role('alert').filter(has_text='올바른 JSON').wait_for()
    page.locator('#review-input').fill('{"manual": true}')
    edited=save();assert edited['scenario']=='Five editable fields verified in Chrome' and edited['input']=={'manual':True}
    assert edited['preconditions']==['Reviewed precondition'] and edited['steps']==['Reviewed step'] and edited['expectedResult']['description']=='Reviewed result'
    page.get_by_text('API AllowList: false',exact=True).wait_for()
    assert edited['approvalStatus']=='DRAFT' and edited['generatedContent']==original['generatedContent'] and edited['evidence']==original['evidence']
    page.get_by_role('region',name='테스트 검토').screenshot(path=str(dest/'06-all-fields-edited.png'))
    for key in ['scenario','preconditions','steps','input','expectedResult']:
        value=original[key]
        if isinstance(value,list):value='\n'.join(value)
        elif isinstance(value,dict):value=json.dumps(value,ensure_ascii=False,indent=2)
        page.locator('#review-'+key).fill(value)
    restored=save();assert restored['modified']==original['modified']
    page.get_by_text('API AllowList: true',exact=True).wait_for()
    page.reload(wait_until='networkidle');lookup()
    assert 'APPROVED' in page.get_by_role('region',name='테스트 검토').inner_text()
    page.locator('.test-case-evidence summary').first.click()
    page.screenshot(path=str(dest/'07-final-review-flow.png'),full_page=True)
    assert not errors and not posts
    result={'result':'PASS','allFiveFieldsEditedInChrome':True,'invalidJsonFeedback':True,'technicalGatesRefreshAfterEdit':True,'originalRestored':True,'approvedPersistedAfterFinalBuild':True,'browserErrors':errors,'postRequests':posts}
    (dest/'browser-final-results.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result));browser.close()
