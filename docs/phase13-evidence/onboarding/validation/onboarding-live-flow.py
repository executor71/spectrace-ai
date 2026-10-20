from pathlib import Path
import sys,json,time,traceback
sys.stdout.reconfigure(encoding='utf8');sys.path.insert(0,str(Path('phase11-browser-tools').resolve()))
from playwright.sync_api import sync_playwright
out=Path('onboarding-evidence');result={'kind':'real Chrome; real existing backend/AI; no intercepted responses','steps':[]};started=time.monotonic()
def progress(stage,**extra):
 item={'stage':stage,'elapsedSeconds':round(time.monotonic()-started,1),**extra};result['steps'].append(item);(out/'live-progress.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(item,ensure_ascii=False),flush=True)
with sync_playwright() as p:
 b=p.chromium.launch(channel='chrome',headless=True);page=b.new_page(viewport={'width':1440,'height':1000},reduced_motion='reduce',accept_downloads=True);page.set_default_timeout(30000)
 errors=[];mutations=[];page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:mutations.append({'method':r.method,'url':r.url}) if r.method in ['POST','PATCH','PUT','DELETE'] else None)
 try:
  page.goto('http://localhost:5173/#dashboard',wait_until='networkidle');page.get_by_role('heading',name='최근 요구사항 목록',exact=True).wait_for()
  purpose='프로그램 변경 요청을 입력하면 AI가 관련 업무규칙을 찾아 분석하고, 필요한 테스트를 생성하며, 승인된 테스트를 실행해 결과까지 검증하는 개발자용 업무 지원 시스템'
  assert page.get_by_text(purpose,exact=True).is_visible();assert page.locator('.guide-steps li').count()==4
  page.screenshot(path=str(out/'landing-desktop.png'),full_page=True,animations='disabled');page.screenshot(path=str(out/'landing-viewport.png'),animations='disabled');progress('landing purpose and four steps visible')
  page.get_by_role('button',name='예제 불러오기',exact=True).click();assert page.locator('#requirement-description').input_value().startswith('요청자 소속 부서의 부서장만 대여 신청을 승인할 수 있다.');assert '본인의 신청을 직접 승인하는 것은 허용하지 않는다.' in page.locator('#requirement-description').input_value();assert not mutations
  page.screenshot(path=str(out/'example-filled.png'),full_page=True,animations='disabled');progress('example fills form only; zero mutating requests')
  with page.expect_response(lambda r:r.url.endswith('/api/requirements') and r.request.method=='POST') as response:page.get_by_role('button',name='변경 요청 저장',exact=True).click()
  saved=response.value.json();assert response.value.status==201;result['requirementId']=saved['id'];page.get_by_role('article',name='요구사항 상세').wait_for();page.screenshot(path=str(out/'saved-request.png'),full_page=True,animations='disabled');progress('saved real example',requirementId=saved['id'])
  page.get_by_role('button',name='다음: 변경 요청 분석',exact=True).click();progress('analysis started')
  with page.expect_response(lambda r:r.url.endswith('/analysis') and r.request.method=='POST',timeout=660000) as response:
   page.get_by_role('button',name='변경 요청 분석 시작',exact=True).click();page.locator('.analysis-panel .loading-panel').wait_for();page.screenshot(path=str(out/'analysis-in-progress.png'),full_page=True,animations='disabled');progress('local LLM progress indicator visible')
  analysis=response.value.json();result['analysisHTTP']=response.value.status
  if not response.value.ok:raise RuntimeError('Real analysis failed: '+json.dumps(analysis,ensure_ascii=False))
  result['analysisCounts']={key:len(analysis.get(key,[])) for key in ['confirmedConditions','ambiguousExpressions','missingConditions','clarificationQuestions','evidence']};page.locator('.analysis-result').wait_for();page.screenshot(path=str(out/'analysis-complete.png'),full_page=True,animations='disabled');progress('analysis complete',counts=result['analysisCounts'])
  page.get_by_role('button',name='다음: 테스트 자동 생성',exact=True).click()
  with page.expect_response(lambda r:r.url.endswith('/test-cases/generate') and r.request.method=='POST',timeout=660000) as response:page.locator('.test-cases').get_by_role('button',name='테스트 자동 생성',exact=True).click()
  batch=response.value.json();result['generationHTTP']=response.value.status
  if not response.value.ok:raise RuntimeError('Generation failed: '+json.dumps(batch,ensure_ascii=False))
  result['generation']={'count':len(batch['testCases']),'clarificationRequired':batch['clarificationRequired'],'generationId':batch['generationId'],'llmCalls':batch.get('llmCalls')};page.screenshot(path=str(out/'test-generation.png'),full_page=True,animations='disabled');progress('test generation complete',**result['generation'])
  if not batch['testCases']:raise RuntimeError('Existing generation policy held this example; see saved clarification reasons. No approval or execution bypassed.')
  page.get_by_role('button',name='다음: 테스트 검토·승인',exact=True).click();tc=batch['testCases'][0];result['testCaseId']=tc['testCaseId']
  page.locator('#review-comment').fill('안내 UX 검증: 합성 예제의 사전조건과 기대결과를 확인했습니다.')
  with page.expect_response(lambda r:r.url.endswith('/approve') and r.request.method=='POST') as response:page.get_by_role('button',name='승인',exact=True).click()
  assert response.value.ok,response.value.text();page.get_by_role('button',name='다음: 테스트 실행·결과 확인',exact=True).wait_for();page.screenshot(path=str(out/'test-approved.png'),full_page=True,animations='disabled');progress('review and approval saved')
  page.get_by_role('button',name='다음: 테스트 실행·결과 확인',exact=True).click();execute=page.get_by_role('button',name='테스트 실행',exact=True)
  if execute.is_disabled():
   status=page.request.get('http://localhost:5173/api/test-cases/'+tc['testCaseId']+'/execution-eligibility').json();raise RuntimeError('Existing execution gate blocked test: '+json.dumps(status,ensure_ascii=False))
  with page.expect_response(lambda r:r.url.endswith('/executions') and r.request.method=='POST') as response:execute.click()
  execution=response.value.json();assert response.value.status==201;result['execution']={k:execution.get(k) for k in ['executionId','result','testCaseRevision','syntheticDefect']};page.locator('.execution-result').wait_for();page.screenshot(path=str(out/'execution-result.png'),full_page=True,animations='disabled');progress('real synthetic API execution complete',**result['execution'])
  with page.expect_download() as download:page.locator('.p13-context-actions').get_by_role('button',name='Excel 다운로드',exact=True).click()
  result['xlsx']=download.value.suggested_filename;download.value.save_as(str(out/result['xlsx']));progress('report downloaded')
  result['success']=True
 except Exception as error:
  result['success']=False;result['error']=str(error);page.screenshot(path=str(out/'live-flow-blocked.png'),full_page=True,animations='disabled');progress('flow stopped at existing error or safety gate',error=str(error));traceback.print_exc()
 finally:
  result['consoleErrors']=errors;result['mutatingRequests']=mutations;(out/'live-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');b.close()
print('Live flow success:',result['success'],flush=True)
