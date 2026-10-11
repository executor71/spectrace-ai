from pathlib import Path
import os,sys,json
sys.path.insert(0,str(Path(os.environ['TEMP'])/'legacy-phase0-browser-tools'))
sys.path.insert(0,str(Path.cwd()/'phase11-browser-tools'))
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[2];out=root/'docs/phase11-evidence'
R='80e2d374-0825-4811-a11e-03ade256b6e8';T='4611bca5-0d0c-45dd-9793-75566c432c89'
with sync_playwright() as p:
    browser=p.chromium.launch(channel='chrome',headless=True)
    page=browser.new_page(viewport={'width':1600,'height':1100},device_scale_factor=1)
    errors=[];model_requests=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('request',lambda r:model_requests.append(r.url) if r.method=='POST' and (r.url.endswith('/analysis') or r.url.endswith('/generate')) else None)
    def lookup():
        page.goto('http://127.0.0.1:5173',wait_until='networkidle')
        page.locator('#requirement-id').fill(R);page.get_by_role('button',name='조회',exact=True).click()
        page.locator('.requirement-result').wait_for()
        page.get_by_role('button',name='저장된 분석 조회',exact=True).click();page.locator('.analysis-result').wait_for()
        page.get_by_role('button',name='저장된 테스트 조회',exact=True).click();page.locator('.test-case-detail').wait_for()
        page.get_by_role('button',name='관계 그래프 조회',exact=True).click();page.locator('.kg-overview').wait_for()
    lookup()
    graph=page.locator('.knowledge-graph')
    assert graph.locator('.kg-PASS').count()>0 and graph.locator('.kg-FAIL').count()>0
    graph.screenshot(path=str(out/'graph-overview.png'))
    graph.get_by_role('button',name='영향 경로',exact=True).first.click()
    detail=page.locator('.kg-detail');detail.wait_for();assert detail.locator('.kg-path').count()==8
    detail.screenshot(path=str(out/'requirement-impact-path.png'))
    page.locator('.kg-overview .kg-TestCase').filter(has_text=T).get_by_role('button',name='생성 근거 추적').click()
    page.wait_for_function("document.querySelector('.kg-detail')?.textContent.includes('테스트 생성 근거 및 실행 이력')")
    assert detail.locator('.kg-FAIL').count()>0
    detail.get_by_text('관련 Evidence',exact=False).click()
    detail.screenshot(path=str(out/'testcase-origin-path.png'))
    page.reload(wait_until='networkidle');lookup()
    assert page.locator('.kg-overview .kg-FAIL').count()>0
    trace=json.loads((out/'graph-trace-ids.json').read_text())[0]['traceId']
    page.goto('http://127.0.0.1:16686/trace/'+trace,wait_until='networkidle')
    page.get_by_text('Trace Timeline',exact=False).first.wait_for()
    page.get_by_text('mcp.find_impacted_tests',exact=True).first.click()
    page.screenshot(path=str(out/'jaeger-graph-trace.png'),full_page=True)
    assert not errors,errors;assert not model_requests,model_requests
    (out/'react-e2e-results.json').write_text(json.dumps({'result':'PASS','browser':browser.version,'channel':'chrome','requirementId':R,'testCaseId':T,'flow':['Requirement','stored Analysis','stored TestCases','Graph','Rule impact','Test origin','PASS/FAIL','reload','Graph persisted','Jaeger same trace'],'consoleErrors':errors,'modelRequests':model_requests,'screenshots':['graph-overview.png','requirement-impact-path.png','testcase-origin-path.png','jaeger-graph-trace.png']},ensure_ascii=False,indent=2),encoding='utf8')
    browser.close();print('PASS Chrome graph flow, refresh persistence, 4 screenshots')
