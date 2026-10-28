"""Live browser demo using existing Phase 14 analysis/TCs; no LLM or generation call.

Only the selected synthetic return cases are explicitly prepared, approved and run.
Completed steps are recorded so a test-script correction does not repeat executions.
"""
import json
import time
import urllib.parse
import urllib.request
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

root=Path(__file__).resolve().parents[2];out=root/'docs/return-execution-extension'
rid='c9e5d1d8-6de2-487e-8ae6-9cf6c7b99eae';base='http://localhost:5173'
def get(path):
    with urllib.request.urlopen('http://localhost:8080'+path,timeout=30) as response:return json.load(response)
def save(name,data):(out/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
source=get('/api/requirements/'+rid+'/analysis')
assert source==json.loads((out/'before-analysis.json').read_text(encoding='utf8'))
jobs=get('/api/requirements/'+rid+'/analysis-jobs');assert any(job['status']=='SUCCEEDED' for job in jobs)
batch=get('/api/requirements/'+rid+'/test-cases');assert not batch['stale']
policy=json.loads((root/'contracts/test-case-policy.json').read_text(encoding='utf8'))
plans={plan['id']:plan for plan in policy['plans']}
ids={}
for name in ['return-normal','return-duplicate','return-authorization','return-inspection-pending']:
    case=next(tc for tc in batch['testCases'] if tc['generatedContent']['scenario']==plans[name]['case']['scenario'] and tc['generatedContent']['expectedResult']==plans[name]['case']['expectedResult'])
    ids[name]=case['testCaseId']
completed=json.loads((out/'demo-progress.json').read_text(encoding='utf8')) if (out/'demo-progress.json').exists() else {}

with sync_playwright() as playwright:
    browser=playwright.chromium.launch(channel='chrome',headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1000},reduced_motion='reduce')
    errors=[];forbidden=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    def guard(route):
        request=route.request
        if request.method=='POST' and (request.url.endswith('/generate') or request.url.endswith('/analysis') or request.url.endswith('/analysis-jobs')):
            forbidden.append(request.url);route.abort()
        else:route.continue_()
    page.route('**/api/**',guard)
    page.goto(base+'/#requirements',wait_until='networkidle')
    page.locator('#requirement-id').fill(rid);page.get_by_role('button',name='조회',exact=True).click()
    expect(page.locator('.requirement-result h3')).to_have_text('대여 자산 반납 및 상태 변경 검증')
    def select(name):
        current=next(tc for tc in get('/api/requirements/'+rid+'/test-cases')['testCases'] if tc['testCaseId']==ids[name])
        page.evaluate('location.hash="execution"')
        page.locator('.test-case-list button').filter(has_text=current['scenario']).click()
        expect(page.locator('.test-case-detail>.metadata')).to_contain_text(ids[name])
        return current
    def run(key,name,mode,expected):
        if key in completed:return completed[key]
        current=select(name)
        page.locator('.return-execution-setup select').select_option(mode)
        with page.expect_response(lambda r:r.request.method=='POST' and r.url.endswith('/return-execution-setup')) as response:
            page.get_by_role('button',name='반납 실행 Fixture 준비',exact=True).click()
        assert response.value.status==200,response.value.text()
        prepared=response.value.json();assert prepared['approvalStatus']=='DRAFT'
        expect(page.get_by_role('button',name='테스트 실행',exact=True)).to_be_disabled()
        if key=='return-pass':page.screenshot(path=str(out/'return-blocked.png'),full_page=True)
        page.evaluate('location.hash="review"')
        page.locator('#review-reviewer').fill('return-demo/developer')
        page.locator('#review-comment').fill('명시적으로 선택한 합성 Fixture의 계약과 Expected Result를 검토하여 승인합니다.')
        with page.expect_response(lambda r:r.request.method=='POST' and r.url.endswith('/approve')) as response:
            page.get_by_role('button',name='승인',exact=True).click()
        assert response.value.status==200,response.value.text()
        approved=response.value.json();assert approved['approvalStatus']=='APPROVED'
        assert approved['reviewRevision']>prepared['reviewRevision']
        page.evaluate('location.hash="execution"')
        button=page.get_by_role('button',name='테스트 실행',exact=True);expect(button).to_be_enabled()
        with page.expect_response(lambda r:r.request.method=='POST' and r.url.endswith('/executions')) as response:
            button.click()
        assert response.value.status==201,response.value.text()
        report=response.value.json();save(key+'.json',report)
        completed[key]=report;save('demo-progress.json',completed)
        assert report['result']==expected,report
        assert report['testCaseRevision']==approved['reviewRevision']
        expect(page.locator('.execution-result>h4')).to_contain_text(expected)
        assert get('/api/executions/'+report['executionId'])==report
        if key in ['return-pass','return-fail','return-error']:
            page.screenshot(path=str(out/(key+'.png')),full_page=True)
        return report
    passed=run('return-pass','return-normal','standard','PASS')
    duplicate=run('duplicate-pass','return-duplicate','standard','PASS')
    authorization=run('authorization-pass','return-authorization','standard','PASS')
    failed=run('return-fail','return-inspection-pending','intentional-defect','FAIL')
    error=run('return-error','return-normal','fixture-error','ERROR')
    restored=run('return-restored-pass','return-normal','standard','PASS')
    assert passed['actual']['state']['returnCount']==1 and passed['actual']['state']['assetStatus']=='ON_LOAN'
    assert duplicate['fixtureBefore']==duplicate['actual']['state']
    assert authorization['fixtureBefore']==authorization['actual']['state']
    assert failed['expected']['httpStatus']==failed['actual']['httpStatus']==201
    assert any(m['field']=='state.assetStatus' for m in failed['mismatches'])
    assert error['errorStage']=='FIXTURE_INITIALIZATION' and error['fixtureBefore'] is None
    history={name:get('/api/test-cases/'+identifier+'/executions') for name,identifier in ids.items()}
    save('execution-history.json',history)
    assert get('/api/requirements/'+rid+'/analysis')==source
    assert len(get('/api/requirements/'+rid+'/analysis-jobs'))==len(jobs)
    summary=get('/api/dashboard/summary?requirementId='+rid);save('dashboard-summary.json',summary)
    assert summary['counts']['PASS']==3 and summary['counts']['FAIL']==0 and summary['counts']['ERROR']==0 and summary['counts']['SYNTHETIC']==1,summary['counts']
    page.evaluate('location.hash="dashboard"')
    page.locator('.p13-scope select').select_option(rid)
    page.screenshot(path=str(out/'dashboard-return.png'),full_page=True)
    with page.expect_download() as download:
        page.locator('.p13-context-actions').get_by_role('button',name='Excel 다운로드',exact=True).click()
    download.value.save_as(str(out/'return-report.xlsx'))
    with zipfile.ZipFile(out/'return-report.xlsx') as archive:
        ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        strings=[''.join(t.itertext()) for t in ET.fromstring(archive.read('xl/sharedStrings.xml')).findall('s:si',ns)]
        cells=ET.fromstring(archive.read('xl/worksheets/sheet4.xml'))
        assert not cells.findall('.//s:f',ns)
        statuses=[]
        for cell in cells.findall('.//s:c',ns):
            if cell.attrib['r'].startswith('H') and cell.get('t')=='s':
                value=cell.find('s:v',ns);statuses.append(strings[int(value.text)])
        assert {'PASS','FAIL','ERROR'}<=set(statuses),statuses
    select('return-inspection-pending')
    page.set_viewport_size({'width':390,'height':900});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    page.screenshot(path=str(out/'return-fail-mobile.png'),full_page=True)
    assert not errors,errors
    assert not forbidden,forbidden
    save('browser-results.json',dict(result='PASS',realExecutions=len(completed),outcomes={key:r['result'] for key,r in completed.items()},
        newLlmCalls=0,phase14Job=jobs[0]['jobId'],analysisUnchanged=True,generationIdUnchanged=batch['generationId']==get('/api/requirements/'+rid+'/test-cases')['generationId'],
        currentRevisionCounts=summary['counts'],excelOutcomes=sorted(set(statuses)&{'PASS','FAIL','ERROR'}),widths=[1440,390]))
    browser.close()
print(json.dumps({'result':'PASS','realExecutions':len(completed),'newLlmCalls':0}))
