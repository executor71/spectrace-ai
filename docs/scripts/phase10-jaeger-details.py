from pathlib import Path
import json,os,sys
root=Path(__file__).resolve().parents[2];dest=root/'docs/phase10-evidence'
sys.path.insert(0,str(Path(os.environ['TEMP'])/'legacy-phase0-browser-tools'))
from playwright.sync_api import sync_playwright
report=json.loads((dest/'jaeger-browser-results.json').read_text())
rows=json.loads((dest/'trace-ids.json').read_text());rerank=next(r for r in rows if r['case']=='MEASURE_HYBRID_RERANK')
targets=[r for r in report['screenshots'] if r['file']!='reranker-span.png']
targets.append({'file':'reranker-span.png','traceId':rerank['traceId'],'case':'MEASURE_HYBRID_RERANK','url':rerank['jaegerUrl'],'operationVisible':'rerank'})
with sync_playwright() as p:
    browser=p.chromium.launch(channel='chrome',headless=True);page=browser.new_page(viewport={'width':1600,'height':1100})
    for target in targets:
        page.goto(target['url'],wait_until='networkidle');page.get_by_text('Trace Timeline',exact=False).first.wait_for()
        if target['file']!='trace-overview.png':
            page.get_by_text(target['operationVisible'],exact=True).first.click()
            tags=page.get_by_text('Tags:',exact=True)
            if tags.count():tags.first.click()
        page.screenshot(path=str(dest/target['file']),full_page=True)
        (dest/(target['file']+'.txt')).write_text(page.locator('body').inner_text(),encoding='utf-8')
    browser.close()
report['screenshots']=targets;report['detailsExpanded']=True
(dest/'jaeger-browser-results.json').write_text(json.dumps(report,indent=2))
print('Seven actual Jaeger screenshots; expanded metadata; no workflow or model rerun')
