from pathlib import Path
import json,urllib.request,urllib.error,time
from uuid import uuid4
root=Path(__file__).resolve().parents[3];dest=root/'docs/phase3-evidence';checks=[]
def call(path,expected,body=None,base='http://localhost:8080'):
    start=time.perf_counter()
    request=urllib.request.Request(base+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(request,timeout=15) as response:status=response.status;data=json.load(response)
    except urllib.error.HTTPError as error:status=error.code;data=json.load(error)
    assert status==expected,(path,status,data)
    checks.append({'path':path,'status':status,'expected':expected,'elapsedSeconds':round(time.perf_counter()-start,3)})
    return data
call('/api/requirements/invalid/analysis',400,{})
call('/api/requirements/'+str(uuid4())+'/analysis',404,{})
call('/api/requirements',400,{'title':' ','description':'bad'})
saved=call('/api/requirements',201,{'title':'[Phase 3 검증] 긴 입력 제한','description':'가'*2001})
call('/api/requirements/'+saved['id']+'/analysis',404)
call('/api/requirements/'+saved['id']+'/analysis',422,{})
after=call('/api/requirements/'+saved['id'],200);assert after['status']=='DRAFT'
call('/internal/v1/search',422,{'query':'Ground Truth','topK':5,'schema':'evaluation'},'http://localhost:8000')
call('/internal/v1/requirement-analysis',422,{'requirementId':saved['id'],'title':'x','description':'x','schema':'evaluation'},'http://localhost:8000')
(dest/'api-error-results.json').write_text(json.dumps({'result':'PASS','requirementId':saved['id'],'checks':checks},ensure_ascii=False,indent=2),encoding='utf-8')
print('PASS 9 live API validation/isolation checks')
