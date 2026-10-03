from pathlib import Path
import os,sys,json,time,urllib.request
root=Path(__file__).resolve().parents[2];dest=root/'docs/phase10-evidence'
browser_trace_responses=[]
source=(root/'docs/scripts/phase8-browser-regression.py').read_text(encoding='utf-8')
source=source.replace("dest=root/'docs/phase8-evidence'","dest=root/'docs/phase10-evidence'")
source=source.replace("page.goto('http://localhost:5173'", "page.on('response',lambda r: browser_trace_responses.append({'traceId':r.headers.get('x-trace-id'),'status':r.status}) if r.request.method=='POST' and r.url.endswith('/executions') else None)\n    page.goto('http://localhost:5173'")
exec(compile(source,'phase8-browser-regression.py','exec'),{'__file__':str(root/'docs/scripts/phase8-browser-regression.py'),'__name__':'__main__','browser_trace_responses':browser_trace_responses})
assert len(browser_trace_responses)==2 and all(r['traceId'] for r in browser_trace_responses)
for r,name in zip(browser_trace_responses,['BROWSER_PASS','BROWSER_FAIL']):r['case']=name
(dest/'browser-trace-ids.json').write_text(json.dumps(browser_trace_responses,indent=2))
sys.path.insert(0,str(Path(os.environ['TEMP'])/'legacy-phase0-browser-tools'))
from playwright.sync_api import sync_playwright
rows=json.loads((dest/'trace-ids.json').read_text());ids={r['case']:r['traceId'] for r in rows};ids.update({r['case']:r['traceId'] for r in browser_trace_responses})
targets=[('trace-overview.png','B_REAL_ANALYSIS',None),('rag-span.png','A_HYBRID','rag.search'),
    ('llm-span.png','B_REAL_ANALYSIS','llm.generate'),('mcp-span.png','C_MCP','mcp.tool'),
    ('execution-pass-span.png','BROWSER_PASS','dummy.execution'),('execution-fail-span.png','BROWSER_FAIL','dummy.execution')]
with sync_playwright() as p:
    browser=p.chromium.launch(channel='chrome',headless=True)
    page=browser.new_page(viewport={'width':1600,'height':1100});page.set_default_timeout(30000)
    evidence=[]
    for filename,case,operation in targets:
        tid=ids[case]
        for _ in range(15):
            with urllib.request.urlopen('http://127.0.0.1:16686/api/traces/'+tid) as response:data=json.load(response)
            if data.get('data'):break
            time.sleep(1)
        assert data.get('data'),case
        page.goto('http://localhost:16686/trace/'+tid,wait_until='networkidle')
        page.get_by_text('Trace Timeline',exact=False).first.wait_for()
        if operation:
            locator=page.get_by_text(operation,exact=True)
            if locator.count():locator.first.click()
        page.screenshot(path=str(dest/filename),full_page=True)
        body=page.locator('body').inner_text()
        (dest/(filename+'.txt')).write_text(body,encoding='utf-8')
        assert (operation in body) if operation else ('llm.generate' in body)
        evidence.append({'file':filename,'traceId':tid,'case':case,'url':page.url,'operationVisible':operation or 'llm.generate'})
    (dest/'jaeger-browser-results.json').write_text(json.dumps({'result':'PASS','browser':'Chrome '+browser.version,'screenshots':evidence},indent=2))
    browser.close()
print('PASS actual Chrome workflow + six Jaeger screenshots')
