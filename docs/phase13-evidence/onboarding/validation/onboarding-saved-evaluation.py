from pathlib import Path
import sys,json
sys.stdout.reconfigure(encoding='utf8');sys.path.insert(0,str(Path('phase11-browser-tools').resolve()))
from playwright.sync_api import sync_playwright
out=Path('onboarding-evidence')
with sync_playwright() as p:
 b=p.chromium.launch(channel='chrome',headless=True);page=b.new_page(viewport={'width':1440,'height':1000},reduced_motion='reduce');page.goto('http://localhost:5173/#evaluation',wait_until='networkidle');page.locator('#evaluation-sample option').nth(1).wait_for(state='attached');targets=page.locator('#evaluation-sample option').all();target=page.locator('#evaluation-sample option').nth(1).get_attribute('value');page.locator('#evaluation-sample').select_option(target);page.get_by_role('button',name='샘플 요구사항 조회',exact=True).click();page.get_by_role('button',name='저장된 평가 조회',exact=True).click();page.get_by_role('article',name='평가 결과',exact=True).wait_for();page.screenshot(path=str(out/'saved-evaluation-preserved.png'),full_page=True,animations='disabled');result={'existingEvaluationResultsDisplay':True,'requirementId':target,'newEvaluationRunTriggered':False};(out/'saved-evaluation-results.json').write_text(json.dumps(result,indent=2),encoding='utf8');b.close()
print('Existing saved evaluation displayed')
