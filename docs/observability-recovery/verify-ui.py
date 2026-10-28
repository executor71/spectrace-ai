"""Open real local Jaeger UI in Chrome, verify trace spans, save screenshots."""
import json
import os
from pathlib import Path
import sys

OUT=Path(__file__).resolve().parent
# Isolated browser automation dependency, installed outside the project.
sys.path.insert(0,str(Path(os.environ['TEMP'])/'spectrace-observability-browser'))
from playwright.sync_api import sync_playwright

probe=json.loads((OUT/'minimal-probe.json').read_text())
items={'minimum':{'traceId':probe['traceId'],'required':['recovery.minimum']}}
if '--probe-only' not in sys.argv:
    index=json.loads((OUT/'trace-index.json').read_text())
    for name in ['analysis','tc-generation','mcp-pass','mcp-defect-fail']:
        if name in index:
            items[name]={'traceId':index[name]['traceId'],'required':list(dict.fromkeys(s['operation'] for s in index[name]['spans']))}
report={}
with sync_playwright() as playwright:
    browser=playwright.chromium.launch(channel='chrome',headless=True)
    page=browser.new_page(viewport={'width':1600,'height':1100},device_scale_factor=1)
    for name,item in items.items():
        url='http://127.0.0.1:16686/trace/'+item['traceId']
        page.goto(url,wait_until='networkidle',timeout=30000)
        page.get_by_text('Trace Timeline',exact=True).wait_for(timeout=20000)
        body=page.locator('body').inner_text()
        for operation in item['required']:assert operation in body,(name,operation)
        page.screenshot(path=str(OUT/('ui-'+name+'.png')),full_page=True)
        (OUT/('ui-'+name+'.txt')).write_text(body,encoding='utf8')
        if name in {'analysis','tc-generation'}:
            page.get_by_text('llm.generate',exact=True).first.click()
            # Tags are collapsed in this Jaeger UI; expand the real span metadata.
            tags=page.get_by_text('Tags:',exact=True)
            if tags.count():tags.first.click()
            llm_body=page.locator('body').inner_text()
            assert 'qwen2.5:7b-instruct' in llm_body
            page.screenshot(path=str(OUT/('ui-'+name+'-qwen.png')),full_page=True)
            (OUT/('ui-'+name+'-qwen.txt')).write_text(llm_body,encoding='utf8')
        if name=='analysis':
            page.goto(url,wait_until='networkidle',timeout=30000)
            page.get_by_text('analysis.job.execute',exact=True).first.click()
            tags=page.get_by_text('Tags:',exact=True)
            if tags.count():tags.first.click()
            job_body=page.locator('body').inner_text()
            assert index[name]['jobId'] in job_body
            page.screenshot(path=str(OUT/'ui-analysis-job.png'),full_page=True)
            (OUT/'ui-analysis-job.txt').write_text(job_body,encoding='utf8')
        report[name]={'result':'PASS','traceId':item['traceId'],'url':url,'actualUiSpansVerified':item['required']}
    browser.close()
(OUT/('ui-probe-validation.json' if '--probe-only' in sys.argv else 'ui-validation.json')).write_text(json.dumps(report,indent=2),encoding='utf8')
print(json.dumps(report),flush=True)
