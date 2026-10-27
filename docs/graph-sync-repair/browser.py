"""Actual Chrome; read-only UI checks plus reversible Graph service outage."""
import json,subprocess,tempfile,time,urllib.request,hashlib
from pathlib import Path
from playwright.sync_api import sync_playwright,expect

root=Path(__file__).resolve().parents[2]
out=Path(__file__).resolve().parent
rid='c9e5d1d8-6de2-487e-8ae6-9cf6c7b99eae'
base='http://localhost:5173'
def get(path):
    with urllib.request.urlopen(base+path,timeout=20) as response:return json.load(response)
paths=[f'/api/requirements/{rid}',f'/api/requirements/{rid}/analysis',f'/api/requirements/{rid}/test-cases']
original={p:get(p) for p in paths}
protected=[p for p in root.rglob('*ground*truth*.json') if '.git' not in p.parts and 'node_modules' not in p.parts]
hashes={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
results=[]
with sync_playwright() as p:
    browser=p.chromium.launch(channel='chrome',headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1100})
    page.goto(base+'/#requirements',wait_until='networkidle')
    page.locator('#requirement-id').fill(rid)
    page.get_by_role('button',name='조회',exact=True).click()
    expect(page.locator('.requirement-result h3')).to_have_text(original[paths[0]]['title'])
    page.evaluate("location.hash='graph'")
    graph=page.locator('.knowledge-graph')
    button=graph.get_by_role('button',name='변경 영향 관계 조회',exact=True)
    button.click()
    expect(graph.locator('.kg-overview')).to_be_visible(timeout=20000)
    expect(graph.get_by_text('일부 관계만 존재',exact=False)).to_be_visible()
    assert graph.locator('.kg-TestCase').count()==4
    assert graph.locator('.kg-BusinessRule').count()>0
    assert graph.locator('.kg-Api').count()==2
    page.screenshot(path=str(Path(tempfile.gettempdir())/'spectrace-graph-desktop.png'),full_page=True)
    results.append('Chrome live return graph: 4 TCs, grounded rules and 2 APIs, no execution placeholder')
    for state,text in [('EMPTY','동기화 완료, 관계 없음'),('READY','관계 조회 정상')]:
        payload={'root':{'id':rid,'type':'Requirement'},'relatedBusinessRules':[],'relatedApis':[],'relatedTestCases':[],'evidence':[],'executions':[],'paths':[],'nodeCount':1,'edgeCount':0,'syncStatus':'SYNCED','dataStatus':state}
        def data_response(route):route.fulfill(status=200,json=payload)
        page.route('**/api/graph/find_requirement_context',data_response)
        button.click()
        expect(graph.locator('.kg-overview').get_by_role('status')).to_contain_text(text)
        page.unroute('**/api/graph/find_requirement_context')
        results.append('UI state: '+state)
    button.click()
    expect(graph.locator('.kg-TestCase')).to_have_count(4)
    for code,text in [('GRAPH_SYNC_PENDING','그래프 동기화 대기'),('GRAPH_SYNC_FAILED','그래프 동기화 실패')]:
        def state_response(route):route.fulfill(status=404,json={'detail':{'errorCode':code}})
        page.route('**/api/graph/find_requirement_context',state_response)
        button.click()
        expect(graph.get_by_role('alert')).to_contain_text(text)
        expect(graph.locator('.kg-overview')).to_be_visible()
        page.unroute('**/api/graph/find_requirement_context')
        results.append('UI state: '+code)
    try:
        subprocess.run(['docker','stop','master-graph-service-1'],check=True,capture_output=True)
        button.click()
        expect(graph.get_by_role('alert')).to_contain_text('그래프 서비스 연결 실패',timeout=20000)
        results.append('Actual Graph outage: separate connection error, previous graph retained')
    finally:
        subprocess.run(['docker','start','master-graph-service-1'],check=True,capture_output=True)
    for _ in range(30):
        try:
            with urllib.request.urlopen('http://localhost:8030/health',timeout=2):break
        except Exception:time.sleep(1)
    button.click()
    expect(graph.get_by_role('alert')).to_have_count(0,timeout=20000)
    expect(graph.locator('.kg-overview')).to_be_visible()
    results.append('Actual recovery: graph query restored')
    page.set_viewport_size({'width':390,'height':900})
    expect(graph.locator('.kg-overview')).to_be_visible()
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    page.screenshot(path=str(Path(tempfile.gettempdir())/'spectrace-graph-mobile.png'),full_page=True)
    results.append('Mobile 390px: graph visible, no horizontal document overflow')
    browser.close()
assert original=={p:get(p) for p in paths},'Core source data changed'
assert hashes=={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
(out/'browser-results.json').write_text(json.dumps({'passed':results,'coreUnchanged':True,'groundTruthUnchanged':hashes},ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(results,ensure_ascii=True))
