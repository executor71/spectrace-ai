"""Read-only final service and reload verification. No extra executions."""
import json
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

out=Path(__file__).resolve().parent;rid='c9e5d1d8-6de2-487e-8ae6-9cf6c7b99eae'
def get(path):
    with urllib.request.urlopen('http://localhost:8080'+path,timeout=20) as response:return json.load(response)
def read(name):return json.loads((out/name).read_text(encoding='utf8'))
before=read('before-test-cases.json');after=get('/api/requirements/'+rid+'/test-cases')
assert before['generationId']==after['generationId'] and before['policyHash']==after['policyHash'] and not after['stale']
assert get('/api/requirements/'+rid+'/analysis')==read('before-analysis.json')
rows=[]
for previous in before['testCases']:
    current=next(tc for tc in after['testCases'] if tc['testCaseId']==previous['testCaseId'])
    assert current['generatedContent']==previous['generatedContent'] and current['evidence']==previous['evidence']
    eligibility=get('/api/test-cases/'+current['testCaseId']+'/execution-eligibility')
    assert eligibility['executable'] and eligibility['fixtureReady'] and eligibility['executionEligible']
    rows.append(dict(testCaseId=current['testCaseId'],templateId=eligibility['templateId'],reviewRevision=current['reviewRevision'],
        approvalStatus=current['approvalStatus'],generationExecutable=current['generatedContent']['executable'],runtimeEligibility=eligibility,
        evidenceUnchanged=True,generatedContentUnchanged=True))
assert get('/actuator/health')['status']=='UP'
with sync_playwright() as playwright:
    browser=playwright.chromium.launch(channel='chrome',headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1000},reduced_motion='reduce');writes=[];errors=[]
    page.add_init_script(f'localStorage.setItem("spectrace.selectedRequirement",{json.dumps(rid)})')
    def guard(route):
        if route.request.method not in ['GET','HEAD','OPTIONS']:writes.append(route.request.url);route.abort()
        else:route.continue_()
    page.route('**/api/**',guard);page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto('http://localhost:5173/#execution',wait_until='networkidle')
    expect(page.locator('.execution-result>h4')).to_contain_text('PASS')
    page.reload(wait_until='networkidle')
    expect(page.locator('.execution-result>h4')).to_contain_text('PASS')
    expect(page.get_by_role('button',name='테스트 실행',exact=True)).to_be_enabled()
    expect(page.locator('.execution-result')).to_contain_text(read('return-restored-pass.json')['executionId'])
    page.locator('.execution-history button').filter(has_text='ERROR').click()
    expect(page.locator('.execution-result>h4')).to_contain_text('ERROR')
    page.set_viewport_size({'width':390,'height':900});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    page.screenshot(path=str(out/'return-error-mobile.png'),full_page=True)
    assert not writes and not errors,(writes,errors)
    browser.close()
(out/'execution-support-results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
(out/'final-service-check.json').write_text(json.dumps(dict(backend='UP',preparedApprovedReturnCases=4,analysisUnchanged=True,generationIdUnchanged=True,
    generatedContentAndEvidenceUnchanged=True,browserReload='PASS',pastErrorVisible=True,extraWrites=0),indent=2),encoding='utf8')
print('FINAL_READ_ONLY_SERVICE_CHECK_PASS')
