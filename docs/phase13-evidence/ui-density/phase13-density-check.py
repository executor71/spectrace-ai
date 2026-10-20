from pathlib import Path
import sys,json,hashlib
sys.stdout.reconfigure(encoding='utf8')
sys.path.insert(0,str(Path('phase11-browser-tools').resolve()))
from playwright.sync_api import sync_playwright
phase=sys.argv[1];out=Path('phase13-density-evidence');out.mkdir(exist_ok=True)
with sync_playwright() as p:
 b=p.chromium.launch(channel='chrome',headless=True);results=[]
 for width in [1920,1440,1024,390]:
  page=b.new_page(viewport={'width':width,'height':1080 if width==1920 else 900 if width==1024 else 844 if width==390 else 900},reduced_motion='reduce')
  page.goto('http://localhost:5173/#dashboard',wait_until='networkidle');page.get_by_role('heading',name='최근 요구사항 목록',exact=True).wait_for()
  page.screenshot(path=str(out/f'{phase}-{width}.png'),full_page=True,animations='disabled');page.screenshot(path=str(out/f'{phase}-{width}-viewport.png'),animations='disabled')
  measures=page.evaluate('''() => {
    const rect=s=>{const e=document.querySelector(s),r=e.getBoundingClientRect(),c=getComputedStyle(e);return {x:r.x,y:r.y,width:r.width,height:r.height,bottom:r.bottom,padding:c.padding,margin:c.margin,gap:c.gap,display:c.display,alignItems:c.alignItems,minHeight:c.minHeight}}
    return {width:innerWidth,viewportHeight:innerHeight,overflow:document.documentElement.scrollWidth>innerWidth,toolbar:rect('.p13-toolbar'),select:rect('.p13-toolbar select'),refresh:rect('.p13-toolbar>button'),register:rect('.p13-toolbar>button:not(.secondary)'),grid:rect('.phase13-dashboard .metric-grid'),cards:[...document.querySelectorAll('.p13-metric')].map(e=>{let r=e.getBoundingClientRect();return {x:r.x,y:r.y,height:r.height,bottom:r.bottom}}),charts:rect('.p13-charts'),table:rect('#dashboard-requirements'),tabs:rect('.phase13-dashboard .workflow-tabs')}
  }''');results.append(measures);page.close()
 b.close()
(out/f'{phase}-measurements.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(results,ensure_ascii=False,indent=2))
