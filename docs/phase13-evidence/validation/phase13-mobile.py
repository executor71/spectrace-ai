from pathlib import Path
import sys,json
sys.path.insert(0,str(Path('phase11-browser-tools').resolve()))
from playwright.sync_api import sync_playwright
out=Path('phase13-evidence')
with sync_playwright() as p:
 b=p.chromium.launch(channel='chrome',headless=True);page=b.new_page(viewport={'width':390,'height':844},reduced_motion='reduce');page.goto('http://localhost:5173',wait_until='networkidle');page.get_by_role('heading',name='최근 요구사항 목록',exact=True).wait_for()
 assert not page.locator('.sidebar').is_visible()
 page.screenshot(path=str(out/'dashboard-390.png'),full_page=True,animations='disabled');page.screenshot(path=str(out/'mobile-viewport.png'),animations='disabled')
 checks={'width':390,'sidebarHidden':not page.locator('.sidebar').is_visible(),'pageOverflow':page.evaluate('document.documentElement.scrollWidth>innerWidth'),'chartColumns':page.locator('.p13-charts').evaluate('(e)=>getComputedStyle(e).gridTemplateColumns'),'browser':'Desktop Chrome viewport emulation; real iPhone Safari not tested'}
 assert not checks['pageOverflow'];(out/'mobile-layout.json').write_text(json.dumps(checks,indent=2),encoding='utf8');b.close()
print('mobile verified')
