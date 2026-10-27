"""Actual Chrome against saved real-model result; never starts a model job."""
import json,urllib.request,zipfile,io
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
out=Path(__file__).resolve().parent
impact=json.loads((out/'real-e2e-results.json').read_text(encoding='utf8'))['impactId']
base='http://localhost:5173'
results=[]
with urllib.request.urlopen('http://localhost:8080/api/change-impacts/'+impact+'/reviews') as response:next_revision=len(json.load(response))+1
with sync_playwright() as p:
 browser=p.chromium.launch(channel='chrome',headless=True)
 page=browser.new_page(viewport={'width':1440,'height':1100},accept_downloads=True)
 errors=[];writes=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.on('request',lambda r:writes.append(r.url) if r.method=='POST' else None)
 page.goto(base+'/#impact',wait_until='networkidle')
 page.get_by_label('저장된 변경안').select_option(impact)
 expect(page.get_by_role('heading',name='조건 변경 비교',exact=True)).to_be_visible(timeout=15000)
 expect(page.get_by_role('heading',name='기존 확정 조건')).to_be_visible()
 for heading,name in [('기존 확정 조건','baseline-selection'),('조건 변경 비교','condition-comparison'),('관련 API 영향 후보','affected-apis'),('기존 TC 영향','affected-testcases'),('신규 TC 필요성 제안','new-test-suggestions')]:
  section=page.get_by_role('heading',name=heading,exact=True).locator('..')
  section.screenshot(path=str(out/(name+'.png')))
  results.append(heading+' visible')
 expect(page.get_by_text('TEMPLATE_UNSUPPORTED',exact=True)).to_be_visible()
 page.get_by_label('검토자').fill('합성 검토자')
 page.get_by_label('API API-LOAN-APPROVE 검토').select_option('INCLUDED')
 first_tc=page.locator('select[aria-label^="TC "]').first
 first_tc.select_option('UPDATE_CANDIDATE')
 page.get_by_label('검토 의견').fill('신규 자산관리 담당자 권한은 제안 상태이며 기존 자기 승인 금지와 부서장 권한 유지 대응을 확인했습니다. 업무정책 변경 승인은 별도입니다.')
 page.get_by_label('검토 상태').select_option('REVIEWED')
 page.get_by_role('button',name='검토 결과 저장',exact=True).click()
 expect(page.get_by_text(f'검토 이력 {next_revision}건',exact=True)).to_be_visible(timeout=10000)
 page.get_by_role('heading',name='개발자 검토',exact=True).locator('..').screenshot(path=str(out/'developer-review.png'))
 results.append(f'API inclusion and TC candidate adjustment saved as append-only review revision {next_revision}')
 with page.expect_download() as download:
  page.get_by_role('link',name='변경 영향 Excel 다운로드').click()
 downloaded=download.value
 temp=out/'change-impact-export.xlsx';downloaded.save_as(str(temp))
 with zipfile.ZipFile(temp) as archive:
  workbook=archive.read('xl/workbook.xml').decode()
  assert workbook.count('<sheet ')==7
  assert not any(b'<f>' in archive.read(n) for n in archive.namelist() if n.startswith('xl/worksheets/'))
 results.append('XLSX: 7 sheets, no formula cells')
 page.get_by_role('heading',name='개발자 검토',exact=True).locator('..').screenshot(path=str(out/'excel-download.png'))
 page.reload(wait_until='networkidle');page.get_by_label('저장된 변경안').select_option(impact)
 expect(page.get_by_text(f'검토 이력 {next_revision}건',exact=True)).to_be_visible(timeout=15000)
 expect(page.get_by_label('API API-LOAN-APPROVE 검토')).to_have_value('INCLUDED')
 expect(page.locator('select[aria-label^="TC "]').first).to_have_value('UPDATE_CANDIDATE')
 results.append('Saved analysis/review reload without model invocation')
 page.set_viewport_size({'width':390,'height':900})
 expect(page.get_by_role('heading',name='조건 변경 비교',exact=True)).to_be_visible()
 assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
 page.screenshot(path=str(out/'mobile.png'),full_page=True)
 results.append('Mobile 390px: no document overflow')
 assert not errors,errors
 assert writes and all(url.endswith('/reviews') for url in writes),writes
 browser.close()
with urllib.request.urlopen('http://localhost:8080/api/change-impacts/'+impact+'/reviews') as response:reviews=json.load(response)
(out/'review-result.json').write_text(json.dumps(reviews,ensure_ascii=False,indent=2),encoding='utf8')
(out/'browser-results.json').write_text(json.dumps({'passed':results,'browserErrors':errors,'postRequests':writes},ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(results,ensure_ascii=True))
