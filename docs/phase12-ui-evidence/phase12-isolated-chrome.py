import sys,json,re,os
from pathlib import Path
sys.path.insert(0,os.environ.get('PLAYWRIGHT_PYTHON_PATH',str(Path('phase11-browser-tools').resolve())))
from playwright.sync_api import sync_playwright,expect
out=Path(os.environ.get('PHASE12_EVIDENCE_DIR',str(Path(__file__).resolve().parent)));checks=[];errors=[];destinations=[];responses=[]
labels={'requirements':'요구사항 관리','analysis':'AI 요구사항 분석','testcases':'테스트케이스','review':'검토 및 승인','execution':'실행 및 검증'}
with sync_playwright() as p:
 b=p.chromium.launch(channel='chrome',headless=True);page=b.new_page(viewport={'width':1440,'height':1000});page.set_default_timeout(12000);page.on('pageerror',lambda e:errors.append(str(e)))
 def proxy(route):
  upstream=route.request.url.replace('http://localhost:5173','http://localhost:18080');destinations.append({'method':route.request.method,'upstream':upstream});response=route.fetch(url=upstream);route.fulfill(response=response)
 page.route(re.compile(r'http://localhost:5173/api/(requirements|test-cases)(/|$)'),proxy)
 def capture(**options):
  page.evaluate('window.scrollTo(0,0)')
  page.screenshot(animations='disabled',**options)
 def nav(key):
  if page.viewport_size['width']<=700 and not page.locator('.sidebar').evaluate('(el)=>el.classList.contains("is-open")'):page.get_by_role('button',name='메뉴 열기',exact=True).click()
  page.get_by_role('navigation',name='주 메뉴').get_by_role('button',name=re.compile(labels[key])).click()
 def lookup(id):
  page.locator('#requirement-id').fill(id)
  with page.expect_response(lambda r:r.url.endswith('/api/requirements/'+id)) as res:page.locator('.lookup-form button').click()
  assert res.value.status==200
 def post(button,suffix,status):
  with page.expect_response(lambda r:r.url.endswith(suffix) and r.request.method in ['POST','PATCH']) as res:page.get_by_role('button',name=button,exact=True).click()
  body=res.value.json();assert res.value.status==status,(res.value.status,body);responses.append({'path':suffix,'status':status,'body':body});return body
 page.goto('http://localhost:5173',wait_until='networkidle');nav('requirements');page.locator('#requirement-title-input').fill('Phase 12 UI 검증용 요구사항');page.locator('#requirement-description').fill('분리된 임시 DB에서 요구사항 등록 및 조회 화면을 검증합니다.');saved=post('요구사항 저장','/api/requirements',201);expect(page.locator('.toast')).to_contain_text('요구사항이 등록되었습니다.');expect(page.locator('.requirement-result h3')).to_have_text(saved['title']);capture(path=str(out/'registration-toast.png'),full_page=True);lookup(saved['id']);checks.append('real isolated HTTP 201 registration, toast, title/status and GET lookup')
 nav('analysis');page.get_by_role('button',name='저장된 분석 조회',exact=True).click();expect(page.locator('.analysis-panel')).to_contain_text('HTTP 404');nav('testcases');page.get_by_role('button',name='저장된 테스트 조회',exact=True).click();expect(page.locator('.test-cases')).to_contain_text('HTTP 404');checks.append('real isolated HTTP 404 analysis/test absence is explicit')
 fixture=json.loads((out/'isolated-fixture.json').read_text())['requirementId'];lookup(fixture);page.get_by_role('button',name='저장된 테스트 조회',exact=True).click();expect(page.locator('.test-case-list li')).to_have_count(5);nav('execution');expect(page.get_by_role('button',name='Dummy 실행',exact=True)).to_be_disabled();expect(page.locator('.eligibility-grid')).to_contain_text('DRAFT');checks.append('server DRAFT execution gate remains disabled')
 nav('review');approved=post('승인','/approve',200);expect(page.locator('.test-case-detail > .status-badge')).to_have_text('APPROVED');rejected=post('반려','/reject',200);expect(page.locator('.test-case-detail > .status-badge')).to_have_text('REJECTED');nav('execution');expect(page.get_by_role('button',name='Dummy 실행',exact=True)).to_be_disabled();checks.append('real isolated approve/reject API transitions; REJECTED execution gate preserved')
 nav('review');approved=post('승인','/approve',200);expect(page.locator('.test-case-detail > .status-badge')).to_have_text('APPROVED');nav('execution');expect(page.get_by_role('button',name='Dummy 실행',exact=True)).to_be_enabled();passed=post('Dummy 실행','/executions',201);assert passed['result']=='PASS';expect(page.locator('.execution-comparison > section')).to_have_count(2);expect(page.locator('.mismatch-panel')).to_contain_text('불일치 항목이 없습니다.');capture(path=str(out/'isolated-execution-pass.png'),full_page=True);checks.append('real isolated approved Dummy execution PASS with Expected/Actual comparison')
 nav('review');page.locator('.review-editor summary').click();page.locator('#review-scenario').fill(approved['scenario']+' · Phase 12 검토');updated=post('수정 저장','/api/test-cases/'+approved['testCaseId'],200);assert updated['approvalStatus']=='DRAFT' and updated['reviewRevision']>passed['testCaseRevision'];expect(page.locator('.test-case-detail > .status-badge')).to_have_text('DRAFT');nav('execution');expect(page.get_by_role('button',name='Dummy 실행',exact=True)).to_be_disabled();expect(page.locator('.execution-result')).to_contain_text('현재 TC와 revision이 다른 과거 실행 결과입니다.');checks.append('real edit creates DRAFT/new revision and preserves historical execution revision')
 page.locator('.test-case-list button').nth(1).click();nav('review');approved2=post('승인','/approve',200);expect(page.locator('.test-case-detail > .status-badge')).to_have_text('APPROVED');nav('execution');expect(page.get_by_role('button',name='Dummy 실행',exact=True)).to_be_enabled();failed=post('Dummy 실행','/executions',201);assert failed['result']=='FAIL' and failed['mismatches'];expect(page.locator('.mismatch-panel.has-mismatch')).to_be_visible();capture(path=str(out/'isolated-execution-fail.png'),full_page=True);checks.append('real isolated synthetic-defect Dummy execution FAIL and mismatch details')
 error_run={**failed,'result':'ERROR','actual':{'errorCode':'DUMMY_EXECUTION_ERROR','message':'검증용 오류 표시'},'mismatches':[]};pattern='**/api/test-cases/'+approved2['testCaseId']+'/executions';page.route(pattern,lambda route:route.fulfill(status=200,json=[error_run]) if route.request.method=='GET' else route.fallback());page.locator('.test-case-list button').first.click();page.locator('.test-case-list button').nth(1).click();expect(page.locator('.execution-result')).to_contain_text('ERROR');capture(path=str(out/'execution-error-simulated.png'),full_page=True);checks.append('intercepted ERROR contract renders separately without backend fault injection')
 assert not errors,errors
 (out/'isolated-chrome-results.json').write_text(json.dumps({'result':'PASS','browser':b.version,'checks':checks,'errors':errors,'upstreamRequests':destinations,'responses':responses},ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps({'checks':checks,'errors':errors},ensure_ascii=True));b.close()
