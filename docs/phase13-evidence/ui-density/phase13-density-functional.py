from pathlib import Path
import sys,json,hashlib
sys.stdout.reconfigure(encoding='utf8');sys.path.insert(0,str(Path('phase11-browser-tools').resolve()))
from playwright.sync_api import sync_playwright
out=Path('phase13-density-evidence');root=Path('D:/MASTER과정');result={}
with sync_playwright() as p:
 b=p.chromium.launch(channel='chrome',headless=True);page=b.new_page(viewport={'width':1440,'height':900},reduced_motion='reduce',accept_downloads=True)
 errors=[];writes=[];page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:writes.append(r.method+' '+r.url) if r.method not in ['GET','HEAD','OPTIONS'] else None)
 def dashboard():
  page.goto('http://localhost:5173/#dashboard',wait_until='networkidle');page.get_by_role('heading',name='최근 요구사항 목록',exact=True).wait_for()
 dashboard();data=page.request.get('http://localhost:5173/api/dashboard/summary').json()
 with page.expect_response(lambda r:r.url.endswith('/api/dashboard/summary')) as response:page.get_by_role('button',name='새로고침',exact=True).click()
 assert response.value.ok;page.get_by_role('heading',name='최근 요구사항 목록',exact=True).wait_for();result['refreshReadOnly']=True
 page.get_by_role('button',name='검토 대기 TC',exact=False).click();assert page.locator('#dashboard-cases select').input_value()=='DRAFT';assert page.locator('.p13-case-list li').count()==data['counts']['DRAFT'];result['KPIFilter']=True
 for key in ['APPROVED','REJECTED','PASS','FAIL','ERROR']:
  label={'APPROVED':'승인','REJECTED':'반려'}.get(key,key);page.get_by_role('button',name=f'{label} {data["counts"][key]}건',exact=True).click();assert page.locator('#dashboard-cases select').input_value()==key
 result['chartFilters']=True
 page.get_by_role('button',name='다음',exact=True).click();assert '2 /' in page.locator('.p13-pagination').inner_text();page.get_by_role('button',name='이전',exact=True).click();result['pagination']=True
 target=next(row for row in data['requirements'] if row['counts']['PASS'])
 page.locator('.p13-toolbar select').select_option(target['id']);assert page.locator('#dashboard-requirements tbody tr').count()==1
 page.get_by_placeholder('요구사항 제목',exact=True).fill('no-matching-title-density');assert page.locator('#dashboard-requirements tbody tr').count()==0;page.get_by_placeholder('요구사항 제목',exact=True).fill('');result['scopeAndSearch']=True
 with page.expect_download() as download:page.locator('#dashboard-requirements').get_by_role('button',name='Excel 다운로드',exact=True).click()
 file=download.value;file.save_as(str(out/file.suggested_filename));assert file.suggested_filename.endswith('.xlsx');result['excelDownload']=file.suggested_filename
 page.locator('#dashboard-requirements').get_by_role('button',name='상세 보기',exact=True).click();page.get_by_role('article',name='요구사항 상세').wait_for();assert target['title'] in page.get_by_role('article',name='요구사항 상세').inner_text();result['detailNavigation']=True
 dashboard();page.get_by_role('button',name='새 요구사항 등록',exact=True).click();page.get_by_role('form',name='요구사항 등록',exact=True).wait_for();result['createNavigation']=True
 dashboard();page.get_by_role('button',name='기술 검증 결과',exact=True).click();page.get_by_role('cell',name='HYBRID_RERANK',exact=True).wait_for();page.get_by_role('button',name='업무 현황',exact=True).click();page.get_by_role('heading',name='최근 요구사항 목록',exact=True).wait_for();result['tabs']=True
 page.set_viewport_size({'width':390,'height':844});page.get_by_role('button',name='새로고침',exact=True).click();page.get_by_role('heading',name='최근 요구사항 목록',exact=True).wait_for();assert not page.evaluate('document.documentElement.scrollWidth>innerWidth');result['mobileRefresh']=True
 assert not errors,errors;assert not writes,writes;result['consoleErrors']=errors;result['mutatingRequests']=writes;b.close()
baseline=json.loads((out/'source-baseline.json').read_text(encoding='utf8'));changed=[]
for relative,expected in baseline['hashes'].items():
 actual=hashlib.sha256((root/relative).read_bytes()).hexdigest()
 if expected!=actual:changed.append(relative)
assert not changed,changed;result['protectedFilesUnchanged']=len(baseline['hashes'])
before=(out/'before-Dashboard.tsx').read_text(encoding='utf8');after=(root/'frontend/src/Dashboard.tsx').read_text(encoding='utf8')
assert before[:before.index('  return <section')]==after[:after.index('  return <section')]
assert before[before.index('export function ExportButton'):]==after[after.index('export function ExportButton'):]
result['dataLogicAndExportUnchanged']=True
(out/'functional-check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(result,ensure_ascii=False,indent=2))
