"""Exactly one representative generate request through Chrome. Never runs tests/APIs.

Requires Playwright, an idle model, and the existing saved return analysis.
The attempt guard prevents accidental repeat model calls.
"""
import json
import time
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

root=Path(__file__).resolve().parents[2]
out=root/'docs/testcase-policy-extension'
rid='c9e5d1d8-6de2-487e-8ae6-9cf6c7b99eae'
guard=out/'real-attempt.json'
assert not guard.exists() and not (out/'return-scenario-tests.json').exists(), 'A real attempt is already recorded; refuse a repeat call'

def get(path):
    with urllib.request.urlopen('http://localhost:8080'+path, timeout=30) as response:
        return json.load(response)

source=get('/api/requirements/'+rid+'/analysis')
assert source==json.loads((out/'before-analysis.json').read_text(encoding='utf8'))
assert not get('/api/analysis-jobs')['running']
with sync_playwright() as playwright:
    browser=playwright.chromium.launch(channel='chrome',headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1000})
    page.goto('http://localhost:5173/#requirements',wait_until='networkidle')
    page.locator('#requirement-id').fill(rid)
    page.get_by_role('button',name='조회',exact=True).click()
    expect(page.locator('.requirement-result h3')).to_have_text('대여 자산 반납 및 상태 변경 검증')
    page.evaluate('location.hash="testcases"')
    button=page.locator('.test-cases').get_by_role('button',name='테스트 자동 생성',exact=True)
    expect(button).to_be_enabled()
    guard.write_text(json.dumps({'requirementId':rid,'representativeRequests':1,'startedAt':time.time()}),encoding='utf8')
    start=time.perf_counter()
    with page.expect_response(lambda response: response.request.method=='POST' and response.url.endswith('/test-cases/generate'),timeout=660000) as pending:
        button.click()
    response=pending.value
    body=response.json()
    (out/'return-scenario-tests.json').write_text(json.dumps({'httpStatus':response.status,'elapsedSeconds':time.perf_counter()-start,
        'provider':'REAL_QWEN','analysis':'EXISTING_UNCHANGED_SNAPSHOT','result':body},ensure_ascii=False,indent=2),encoding='utf8')
    assert response.status==200,body
    assert len(body['testCases'])==4 and body['generationStatus']=='PARTIALLY_GENERATED',body
    assert body['llmCalls']==1, 'Model retried; report actual count instead of retrying again'
    expect(page.get_by_role('heading',name='지원되는 조건의 테스트를 부분 생성했습니다.',exact=True)).to_be_visible()
    page.screenshot(path=str(out/'return-desktop.png'),full_page=True)
    page.reload(wait_until='networkidle')
    expect(page.get_by_role('heading',name='지원되는 조건의 테스트를 부분 생성했습니다.',exact=True)).to_be_visible()
    saved=get('/api/requirements/'+rid+'/test-cases')
    assert len(saved['testCases'])==4 and not saved['stale']
    assert get('/api/requirements/'+rid+'/analysis')==source
    assert all(not tc['executable'] for tc in saved['testCases'])
    page.set_viewport_size({'width':390,'height':900})
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1')
    page.screenshot(path=str(out/'return-mobile.png'),full_page=True)
    body['verification']={'databaseReload':True,'analysisUnchanged':True,'desktopAndMobile':True,'automaticExecution':False}
    (out/'return-scenario-tests.json').write_text(json.dumps({'httpStatus':response.status,'elapsedSeconds':time.perf_counter()-start,
        'provider':'REAL_QWEN','analysis':'EXISTING_UNCHANGED_SNAPSHOT','result':body},ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'status':body['generationStatus'],'testCases':len(body['testCases']),'llmCalls':body['llmCalls'],'verified':body['verification']}))
    browser.close()
