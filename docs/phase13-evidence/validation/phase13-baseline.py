from pathlib import Path
import subprocess,json,sys,urllib.request
out=Path('phase13-evidence');out.mkdir(exist_ok=True)
root=Path('D:/MASTER과정')
def cmd(args):return subprocess.check_output(args,cwd=root).decode('utf8')
sql="SELECT json_build_object('requirements',(SELECT count(*) FROM app.requirement),'currentTCs',(SELECT count(*) FROM app.test_case t JOIN app.test_case_generation g USING(generation_id)),'executions',(SELECT count(*) FROM app.test_execution),'reviews',(SELECT json_object_agg(approval_status,n) FROM (SELECT approval_status,count(*) n FROM app.test_case GROUP BY approval_status)s))"
data={'commit':cmd(['git','rev-parse','HEAD']).strip(),'status':cmd(['git','status','--porcelain']),'counts':json.loads(cmd(['docker','exec','master-postgres-1','psql','-U','postgres','-d','legacy_assistant','-tAc',sql]))}
(out/'baseline.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
sys.path.insert(0,str(Path('phase11-browser-tools').resolve()))
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
 b=p.chromium.launch(channel='chrome',headless=True);page=b.new_page(viewport={'width':1440,'height':1000});page.goto('http://localhost:5173',wait_until='networkidle');page.screenshot(path=str(out/'before-desktop.png'),full_page=True);page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(out/'before-mobile.png'),full_page=True);b.close()
print(json.dumps(data,ensure_ascii=False))
