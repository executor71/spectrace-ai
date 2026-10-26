"""Mock API UI tests: distinguish policy, evidence, clarification and system errors."""
import json
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

base=sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:5173'
rid='11111111-1111-4111-8111-111111111111'
states={
 'BLOCKED_UNSUPPORTED_TEMPLATE':'요구사항 분석은 완료됐지만 현재 테스트 생성 정책에서 해당 업무 시나리오를 지원하지 않습니다.',
 'BLOCKED_INSUFFICIENT_EVIDENCE':'테스트에 필요한 업무규칙 또는 API 근거가 부족합니다.',
 'BLOCKED_CLARIFICATION_REQUIRED':'요구사항의 일부 조건이 불명확하여 추가 확인이 필요합니다.',
}
with sync_playwright() as playwright:
 browser=playwright.chromium.launch(channel='chrome',headless=True)
 checks=0
 for width in [1440,390]:
  for status,title in states.items():
   context=browser.new_context(viewport={'width':width,'height':1000})
   context.add_init_script(f'localStorage.setItem("spectrace.selectedRequirement",{json.dumps(rid)})')
   page=context.new_page();writes=[];errors=[]
   page.on('pageerror',lambda error:errors.append(str(error)))
   def api(route):
    url=route.request.url
    if route.request.method!='GET':writes.append(url)
    if url.endswith('/api/requirements/'+rid):
     route.fulfill(json={'id':rid,'title':'합성 검증','description':'정책 지원 범위 검증','status':'ANALYZED','createdAt':'2026-10-26T00:00:00Z'})
    elif url.endswith('/test-cases'):
     route.fulfill(json={'requirementId':rid,'generationId':rid,'generationStatus':status,'testCases':[],
      'clarificationRequired':['보류 상세 사유'],'uncoveredTypes':[],'sourceAnalysis':{'evidence':[]},'stale':False,
      'conditionCoverage':[{'text':'확인된 합성 조건','chunkId':rid,'status':'UNSUPPORTED_TEMPLATE' if status.endswith('UNSUPPORTED_TEMPLATE') else 'INSUFFICIENT_EVIDENCE' if status.endswith('INSUFFICIENT_EVIDENCE') else 'CLARIFICATION_REQUIRED','templateIds':[],'testCaseIds':[]}],
      'generationLatencyMs':0,'llmCalls':0,'executionDecisions':[]})
    elif url.endswith('/dashboard/summary'):route.fulfill(json={'queriedAt':'2026-10-26T00:00:00Z','requirements':[],'cases':[],'counts':{},'basis':'fixture'})
    else:route.fulfill(status=404,json={'message':'No data'})
   context.route('**/api/**',api)
   context.route('**/actuator/health',lambda route:route.fulfill(json={'status':'UP'}))
   context.route('**/ai-health/health',lambda route:route.fulfill(json={'status':'UP'}))
   page.goto(base+'/#testcases',wait_until='networkidle')
   expect(page.get_by_role('heading',name=title,exact=True)).to_be_visible()
   expect(page.get_by_text('확인된 합성 조건',exact=True)).to_be_visible()
   button=page.locator('.test-cases').get_by_role('button',name='테스트 자동 생성',exact=True)
   if status.endswith('UNSUPPORTED_TEMPLATE'):
    expect(button).to_be_disabled()
    expect(page.get_by_text('확정 조건은 확인되었으나 매칭되는 테스트 템플릿이 없습니다. 같은 내용을 반복 입력해도 해결되지 않습니다. 정책 지원 범위를 확인하세요.',exact=True)).to_be_visible()
   else:expect(button).to_be_enabled()
   # A system failure is distinct from a successful zero-case result.
   if status.endswith('INSUFFICIENT_EVIDENCE'):
    page.route('**/api/requirements/*/test-cases/generate',lambda route:route.fulfill(status=503,json={'message':'검증용 서비스 연결 실패'}))
    button.click()
    expect(page.get_by_role('alert').filter(has_text='테스트 생성 처리 중 오류가 발생했습니다.')).to_be_visible()
    checks+=1
   assert not errors,errors
   checks+=1;context.close()
 browser.close()
print(json.dumps({'stateAndErrorChecks':checks,'widths':[1440,390],'result':'PASS'}))
