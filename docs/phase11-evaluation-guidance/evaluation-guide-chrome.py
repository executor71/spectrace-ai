import json,sys
from pathlib import Path
sys.path.insert(0,str(Path('phase11-browser-tools').resolve()))
from playwright.sync_api import sync_playwright,expect
out=Path('evaluation-guide-evidence');unbound='a8e38276-f033-4cb6-b1f4-b44811778a1b';registered='b5270f71-c92c-48ae-8530-8946f1cfce62';checks=[];requests=[];errors=[];console=[]
with sync_playwright() as p:
 b=p.chromium.launch(channel='chrome',headless=True);page=b.new_page(viewport={'width':1440,'height':1150});page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:requests.append({'method':r.method,'url':r.url}) if r.method not in ['GET','HEAD','OPTIONS'] else None)
 page.on('console',lambda m:console.append(m.text) if m.type=='error' and 'Encountered two children' in m.text else None)
 page.goto('http://localhost:5173',wait_until='networkidle');panel=page.locator('.evaluations');run=panel.get_by_role('button',name='평가 실행',exact=True)
 expect(panel.locator('#evaluation-sample option')).to_have_count(4);expect(run).to_be_disabled();checks.append('catalog available without selecting requirement; execution disabled')
 page.locator('#requirement-id').fill(unbound);page.locator('.lookup-form button').click();expect(panel.get_by_text('현재 요구사항은 정량평가 대상에 등록되어 있지 않습니다',exact=True)).to_be_visible();expect(run).to_be_disabled();panel.screenshot(path=str(out/'unregistered-requirement.png'));checks.append('unregistered requirement exact guidance + disabled button; no evaluation POST')
 assert not requests,requests
 panel.locator('#evaluation-sample').select_option(registered)
 with page.expect_response(lambda r:r.url.endswith('/api/requirements/'+registered)) as sample:panel.get_by_role('button',name='샘플 요구사항 조회').click()
 assert sample.value.status==200;expect(page.locator('.requirement-result dd').first).to_have_text(registered);expect(page.locator('#requirement-id')).to_have_value(registered);expect(run).to_be_enabled();checks.append('Frozen sample selector loads the existing requirement and enables evaluation')
 with page.expect_response(lambda r:r.url.endswith('/api/evaluations') and r.request.method=='POST',timeout=90000) as evaluated:run.click()
 response=evaluated.value;body=response.json();assert response.status==201 and body['status']=='COMPLETED' and body['metrics'] is not None,(response.status,body)
 expect(panel.locator('.evaluation-result')).to_contain_text(body['id']);expect(panel.locator('.evaluation-kpis tbody tr')).to_have_count(3);panel.screenshot(path=str(out/'registered-evaluation-success.png'));checks.append('real HTTP 201 COMPLETED evaluation with KPI results for registered sample')
 page.reload(wait_until='networkidle');panel.locator('#evaluation-sample').select_option(registered);panel.get_by_role('button',name='샘플 요구사항 조회').click();expect(run).to_be_enabled()
 panel.get_by_role('button',name='저장된 평가 조회').click();expect(panel.locator('.evaluation-result')).to_contain_text(body['id']);checks.append('sample lookup and saved evaluation work after reload')
 page.locator('#requirement-id').fill(unbound);page.locator('.lookup-form button').click();expect(panel.get_by_text('현재 요구사항은 정량평가 대상에 등록되어 있지 않습니다',exact=True)).to_be_visible();expect(run).to_be_disabled();expect(panel.locator('.evaluation-result')).to_have_count(0);checks.append('switching back to unregistered requirement removes old evaluation results and disables execution')
 page.route('**/api/evaluations/targets',lambda route:route.fulfill(status=503,json={'detail':'Target catalog unavailable'}));page.reload(wait_until='networkidle');expect(panel.get_by_role('alert')).to_contain_text('평가 대상 등록 여부를 확인하지 못했습니다');expect(run).to_be_disabled();page.unroute('**/api/evaluations/targets');panel.get_by_role('button',name='평가 대상 다시 확인').click();expect(panel.locator('#evaluation-sample option')).to_have_count(4);checks.append('catalog failure blocks execution and offers working retry')
 assert len(requests)==1 and requests[0]['url'].endswith('/api/evaluations'),requests;assert not errors and not console,(errors,console)
 result={'result':'PASS','browser':b.version,'checks':checks,'consoleErrors':errors+console,'mutationRequests':requests,'evaluationHttpStatus':response.status,'evaluation':body};(out/'chrome-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps({'checks':checks,'status':body['status'],'id':body['id'],'requests':requests},ensure_ascii=True));b.close()
