"""Prepare explicitly synthetic copies from saved Phase 3/4 results; never call a model or read Ground Truth."""
from pathlib import Path
import copy,json,subprocess,urllib.request,urllib.error,uuid
root=Path(__file__).resolve().parents[2];dest=root/'docs/phase7-evidence';dest.mkdir(exist_ok=True)
def api(path,method='GET',body=None):
    request=urllib.request.Request('http://localhost:8080'+path,method=method,data=json.dumps(body,ensure_ascii=False).encode() if body is not None else None,headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(request,timeout=30) as response:return response.status,json.load(response)
    except urllib.error.HTTPError as error:return error.code,json.load(error)
def save(name,data):(dest/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
def quote(value):return "'"+value.replace("'","''")+"'"
baseline=json.loads((root/'docs/phase5-evidence/approve-response.json').read_text(encoding='utf-8'))
code,run=api('/api/test-cases/'+baseline['testCaseId']+'/executions','POST');assert code==201 and run['result']=='PASS',(code,run)
save('pass.json',run)
code,again=api('/api/test-cases/'+baseline['testCaseId']+'/executions','POST');assert code==201
for field in ['result','expected','actual','mismatches','fixtureBefore']:assert again[field]==run[field]
code,batch=api('/api/requirements/'+baseline['requirementId']+'/test-cases');assert code==200
assert next(tc for tc in batch['testCases'] if tc['testCaseId']==baseline['testCaseId'])==baseline
marker=dest/'synthetic-cases.json'
if marker.exists():fixture=json.loads(marker.read_text(encoding='utf-8'))
else:
    code,req=api('/api/requirements','POST',{'title':'[Phase 7 synthetic fixture] 제한된 Dummy API 실행 검증','description':'저장된 Phase 3/4 합성 결과를 복제한 실행 전용 fixture. Qwen 호출 없음. 정상 승인, 자기 승인 결함 및 자산 조회를 코드로 검증한다.'});assert code==201
    rid=req['id'];gid=str(uuid.uuid4());source=copy.deepcopy(batch['sourceAnalysis']);source['requirementId']=rid
    metadata=copy.deepcopy(batch)
    for key in ['testCases','sourceAnalysis','stale','executionDecisions']:metadata.pop(key,None)
    metadata['generationId']=gid;metadata['requirementId']=rid
    originals=[]
    for item in batch['testCases']:
        tc=copy.deepcopy(item['generatedContent']);tc['testCaseId']=str(uuid.uuid4());tc['requirementId']=rid;originals.append(tc)
    sql=['BEGIN;SET ROLE app_user;']
    sql.append(f"INSERT INTO app.requirement_analysis(requirement_id,result_json) VALUES ({quote(rid)},{quote(json.dumps(source,ensure_ascii=False))}::jsonb);")
    sql.append(f"INSERT INTO app.test_case_generation(requirement_id,generation_id,source_analysis,metadata) VALUES ({quote(rid)},{quote(gid)},{quote(json.dumps(source,ensure_ascii=False))}::jsonb,{quote(json.dumps(metadata,ensure_ascii=False))}::jsonb);")
    for n,tc in enumerate(originals):sql.append(f"INSERT INTO app.test_case(test_case_id,requirement_id,generation_id,ordinal,result_json) VALUES ({quote(tc['testCaseId'])},{quote(rid)},{quote(gid)},{n},{quote(json.dumps(tc,ensure_ascii=False))}::jsonb);")
    sql.append('COMMIT;')
    result=subprocess.run(['docker','exec','-i','master-postgres-1','psql','-U','postgres','-d','legacy_assistant','-v','ON_ERROR_STOP=1'],input='\n'.join(sql).encode(),capture_output=True)
    assert result.returncode==0,result.stderr.decode()
    fixture={'requirementId':rid,'generationId':gid,'testCaseIds':[tc['testCaseId'] for tc in originals],'sourceRequirementId':baseline['requirementId'],'modelCalls':0,'synthetic':True};save('synthetic-cases.json',fixture)
rid=fixture['requirementId'];code,batch=api('/api/requirements/'+rid+'/test-cases');assert code==200
def edit(tc,**changes):
    code,result=api('/api/test-cases/'+tc['testCaseId'],'PATCH',{'reviewRevision':tc['reviewRevision'],**changes});assert code==200,(code,result);return result
def approve(tc):
    code,result=api('/api/test-cases/'+tc['testCaseId']+'/approve','POST',{'reviewRevision':tc['reviewRevision'],'reviewer':'phase7/synthetic-test','reviewComment':'합성 실행 검증 전용'});assert code==200,(code,result);return result
# Leave normal/self-defect DRAFT for real Chrome review/approval actions.
normal=batch['testCases'][0]
defect=batch['testCases'][1];input=copy.deepcopy(defect['input']);input['fixtureProfile']='synthetic-self-approval-bug'
expected=copy.deepcopy(defect['expectedResult'])
expected['assertions']=[{'kind':'HTTP_STATUS','value':403},{'kind':'RESPONSE_TOKEN','value':'SELF_APPROVAL_FORBIDDEN'},{'kind':'UNCHANGED','field':'loanStatus'},{'kind':'UNCHANGED','field':'assetStatus'}]
defect=edit(defect,input=input,expectedResult=expected,scenario='[합성 의도적 결함] 자기 승인 검사가 누락되면 FAIL이어야 한다.')
asset=batch['testCases'][2]
asset=edit(asset,input={'apiId':'API-ASSET-001','method':'GET','endpoint':'/assets/{assetId}','pathParameters':{'assetId':'00000000-0000-4000-8000-000000000101'},'body':{},'actorFixture':'ordinary-employee'},preconditions=['합성 자산의 상태는 AVAILABLE이며 호출자와 같은 부서이다.'],scenario='[합성 수동 검토 TC] 자산 상세 조회',expectedResult={'description':'API_SPEC asset-api.md: 상세 조회 HTTP 200, status 및 현재 대여 상태','assertions':[{'kind':'HTTP_STATUS','value':200},{'kind':'RESPONSE_FIELD','field':'status','value':'AVAILABLE'},{'kind':'RESPONSE_FIELD','field':'assetId','value':'00000000-0000-4000-8000-000000000101'},{'kind':'RESPONSE_FIELD','field':'currentLoan','value':None}]})
asset=approve(asset);code,asset_run=api('/api/test-cases/'+asset['testCaseId']+'/executions','POST');assert code==201 and asset_run['result']=='PASS';save('asset-pass.json',asset_run)
blocked=batch['testCases'][3];checks=[]
for endpoint in ['http://example.com','https://example.com/admin/reset','//example.com','/admin/reset','/loans/{loanId}/approve?redirect=http://example.com','DELETE /']:
    changed=copy.deepcopy(blocked['input']);changed['endpoint']=endpoint;blocked=approve(edit(blocked,input=changed))
    code,response=api('/api/test-cases/'+blocked['testCaseId']+'/executions','POST');assert code==409 and response['code']=='API_NOT_ALLOWED',(code,response)
    checks.append({'endpoint':endpoint,'httpStatus':code,'response':response})
save('allowlist-blocks.json',checks)
fixture.update({'normalId':normal['testCaseId'],'defectId':defect['testCaseId'],'assetId':asset['testCaseId'],'blockedId':blocked['testCaseId']});save('synthetic-cases.json',fixture)
save('live-results.json',{'result':'PASS','approvedBaselineExecuted':run['executionId'],'repeatReproducible':True,'oldReviewUnchanged':True,'dummyApisExecuted':['API-LOAN-APPROVE','API-ASSET-001'],'blockedEndpoints':len(checks),'newModelCalls':0})
print(json.dumps({'result':'PASS','requirementId':rid,'dummyApis':2,'blockedEndpoints':len(checks)}))
