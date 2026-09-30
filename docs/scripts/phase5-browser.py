from pathlib import Path
import json,os,sys,urllib.request,urllib.error
root=Path(__file__).resolve().parents[2];dest=root/'docs/phase5-evidence'
sys.path.insert(0,str(Path(os.environ['TEMP'])/'legacy-phase0-browser-tools'))
from playwright.sync_api import sync_playwright
rows=json.loads((root/'docs/phase4-evidence/final-test-cases.json').read_text(encoding='utf-8'))
requirement=rows[0]['requirementId']
def api(method,path,body=None):
    request=urllib.request.Request('http://localhost:8080'+path,data=None if body is None else json.dumps(body).encode(),method=method,headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(request,timeout=15) as response:return response.status,json.load(response)
    except urllib.error.HTTPError as error:return error.code,json.load(error)
status,initial=api('GET',f'/api/requirements/{requirement}/test-cases');assert status==200
assert len(initial['testCases'])==5 and not initial['stale']
for item in initial['testCases']:
    original=next(c for c in rows[0]['result']['testCases'] if c['testCaseId']==item['testCaseId'])
    assert original==item['generatedContent']
    assert item['evidence']==original['evidence']
(dest/'initial-test-cases.json').write_text(json.dumps(initial,ensure_ascii=False,indent=2),encoding='utf-8')
with sync_playwright() as p:
    browser=p.chromium.launch(channel='chrome',headless=True,timeout=15000)
    page=browser.new_page(viewport={'width':1440,'height':1080});page.set_default_timeout(15000)
    errors=[];ai_requests=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.on('request',lambda r:ai_requests.append(r.url) if r.method=='POST' and ('generate' in r.url or r.url.endswith('/analyze')) else None)
    def lookup():
        page.locator('#requirement-id').fill(requirement);page.get_by_role('button',name='조회',exact=True).click()
        page.get_by_role('button',name='저장된 분석 조회',exact=True).click();page.locator('.analysis-result').wait_for()
        page.get_by_role('button',name='저장된 테스트 조회',exact=True).click();page.locator('.test-case-detail').wait_for()
    page.goto('http://localhost:5173',wait_until='networkidle');lookup()
    assert page.locator('.analysis-evidence').count()==5
    review=page.get_by_role('region',name='테스트 검토')
    assert page.locator('.test-case-list button').count()==5
    page.locator('.test-case-evidence summary').first.click()
    assert page.locator('.test-case-evidence input, .test-case-evidence textarea').count()==0
    review.screenshot(path=str(dest/'01-draft-review.png'))
    scenario=initial['testCases'][0]['generatedContent']['scenario']+' [Phase 5 사용자 검토 완료]'
    page.locator('#review-scenario').fill(scenario)
    assert page.get_by_role('button',name='승인',exact=True).is_disabled()
    with page.expect_response(lambda r:r.request.method=='PATCH' and '/api/test-cases/' in r.url) as saved:
        page.get_by_role('button',name='수정 저장',exact=True).click()
    assert saved.value.status==200;edited=saved.value.json();assert edited['approvalStatus']=='DRAFT' and edited['scenario']==scenario
    page.locator('#review-comment').fill('근거와 수정 내용을 확인하여 승인합니다.')
    with page.expect_response(lambda r:r.url.endswith('/approve')) as response:
        page.get_by_role('button',name='승인',exact=True).click()
    assert response.value.status==200;approved=response.value.json();assert approved['approvalStatus']=='APPROVED'
    page.get_by_role('status').filter(has_text='승인 상태: APPROVED').wait_for()
    review.screenshot(path=str(dest/'02-approved.png'))
    (dest/'approve-response.json').write_text(json.dumps(approved,ensure_ascii=False,indent=2),encoding='utf-8')
    page.locator('.test-case-list button').nth(1).click();page.locator('#review-comment').fill('예외 조건의 추가 검토가 필요하여 반려합니다.')
    with page.expect_response(lambda r:r.url.endswith('/reject')) as response:
        page.get_by_role('button',name='반려',exact=True).click()
    assert response.value.status==200;rejected=response.value.json();assert rejected['approvalStatus']=='REJECTED'
    page.get_by_role('status').filter(has_text='승인 상태: REJECTED').wait_for()
    review.screenshot(path=str(dest/'03-rejected.png'))
    (dest/'reject-response.json').write_text(json.dumps(rejected,ensure_ascii=False,indent=2),encoding='utf-8')
    attacks=[]
    for field,value in [('evidence',[]),('requirementId','00000000-0000-0000-0000-000000000000'),('approvalStatus','APPROVED'),('executable',True),('type','MODIFIED'),('scenario','')]:
        status,result=api('PATCH','/api/test-cases/'+approved['testCaseId'],{'reviewRevision':approved['reviewRevision'],field:value});assert status==400
        attacks.append({'field':field,'status':status,'response':result})
    for method,suffix in [('PATCH',''),('POST','/approve'),('POST','/reject')]:
        status,_=api(method,'/api/test-cases/00000000-0000-0000-0000-000000000000'+suffix,{'reviewRevision':0});assert status==404
    page.reload(wait_until='networkidle');lookup()
    assert page.locator('#review-scenario').input_value()==scenario
    assert 'APPROVED' in review.inner_text()
    page.locator('.test-case-evidence summary').first.click();page.locator('.test-case-detail').screenshot(path=str(dest/'04-reloaded-evidence.png'))
    page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    review.screenshot(path=str(dest/'05-mobile-review.png'))
    page.locator('.test-case-list button').nth(1).click();assert 'REJECTED' in review.inner_text()
    status,final=api('GET',f'/api/requirements/{requirement}/test-cases');assert status==200
    assert final['testCases'][0]==approved and final['testCases'][1]==rejected
    for original,current in zip(initial['testCases'],final['testCases']):
        assert original['generatedContent']==current['generatedContent'] and original['evidence']==current['evidence']
    assert not errors and not ai_requests
    report={'result':'PASS','browser':browser.version,'channel':'chrome','requirementId':requirement,'initialStatuses':[c['approvalStatus'] for c in initial['testCases']],
        'edit':True,'approve':True,'reject':True,'readOnlyEvidence':True,'evidenceUnchanged':True,'generatedOriginalUnchanged':True,
        'reloadPersisted':True,'mobileNoHorizontalOverflow':True,'invalidIdStatus':404,'invalidRequests':attacks,'browserErrors':errors,'llmRequests':ai_requests}
    (dest/'browser-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True));browser.close()
