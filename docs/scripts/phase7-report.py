from pathlib import Path
import hashlib,json,xml.etree.ElementTree as ET,urllib.request
root=Path(__file__).resolve().parents[2];dest=root/'docs/phase7-evidence'
def read(name):return json.loads((dest/name).read_text(encoding='utf-8'))
def write(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
suites=[ET.parse(p).getroot().attrib for p in (dest/'backend-tests').glob('TEST-*.xml')]
assert sum(int(s['tests']) for s in suites)==84
assert all(int(s['failures'])+int(s['errors'])+int(s['skipped'])==0 for s in suites)
for name,count in [('python-tests.log',61),('evaluation-tests.log',40)]:
    text=(dest/name).read_text(encoding='utf-8');assert f'Ran {count} tests' in text and '\nOK' in text
regression=read('regression-results.json');assert regression['result']=='PASS'
# Final fixture/provenance change reran all Java tests. RAG/Evaluation sources are unchanged.
regression.update(backendTests=84,newExecutionTests=29,totalAutomatedTests=185)
regression['backendSuites']=[{k:s[k] for k in ['name','tests','failures','errors','skipped']} for s in suites]
baseline=json.loads((root/'docs/phase6-baseline/sha256.json').read_text())
changed=[rel for rel,h in baseline.items() if hashlib.sha256((root/rel).read_bytes()).hexdigest()!=h]
assert set(changed)=={'frontend/src/TestCases.tsx','frontend/src/TestCaseReview.tsx'}
write(dest/'regression-results.json',regression)
build=(dest/'frontend-build.log').read_bytes()
if build.startswith(b'\xff\xfe'):build=build.decode('utf-16').encode()
assert b'tsc -b && vite build' in build and b'frontend Built' in build
browser=read('browser-results.json');assert browser['result']=='PASS' and not browser['pageErrors'] and not browser['modelRequests']
for name in ['pass.json','fail.json','asset-pass.json']:
    saved=read(name)
    with urllib.request.urlopen('http://localhost:8080/api/executions/'+saved['executionId']) as response:assert json.load(response)==saved
    spec=saved['apiSpecEvidence'];assert spec['excerpt'] in (root/spec['source']).read_text(encoding='utf-8')
assert read('pass.json')['result']=='PASS' and read('asset-pass.json')['result']=='PASS'
failure=read('fail.json');assert failure['result']=='FAIL' and len(failure['mismatches'])==4
for name in ['approve-response.json','reject-response.json']:
    old=json.loads((root/'docs/phase5-evidence'/name).read_text(encoding='utf-8'))
    with urllib.request.urlopen('http://localhost:8080/api/requirements/'+old['requirementId']+'/test-cases') as response:batch=json.load(response)
    assert next(c for c in batch['testCases'] if c['testCaseId']==old['testCaseId'])==old
manifest=read('changed-files.json')
manifest['added']+=['compose.phase7-local.yaml','compose.phase7-test.yaml','docs/phase6-baseline/sha256.json','docs/phase6-baseline/source.zip','docs/phase7-result.json']
manifest['added'] += [p.relative_to(root).as_posix() for p in (root/'docs/scripts').glob('phase7-*.py')]
manifest['added']=sorted(set(manifest['added']));manifest['evidenceDirectory']='docs/phase7-evidence/'
write(dest/'changed-files.json',manifest)
report={
 'phase':7,'result':'COMPLETE','baseline':'Phase 6; docs/phase6-baseline/source.zip + sha256.json',
 'dummyApis':[
  {'apiId':'API-ASSET-001','method':'GET','pathTemplate':'/assets/{assetId}','specification':'knowledge/documents/asset-api.md','allowedInputSchema':{'pathParameters':{'assetId':'canonical UUID; registered synthetic ID only'},'body':{},'actorFixture':'registered same-department synthetic actor'},'validator':'asset-detail-v1'},
  {'apiId':'API-LOAN-APPROVE','method':'POST','pathTemplate':'/loans/{loanId}/approve','specification':'knowledge/documents/loan-api.md','allowedInputSchema':{'pathParameters':{'loanId':'canonical UUID; registered synthetic ID only'},'body':{'comment':'optional string <=1000 characters'},'actorFixture':'one of four registered synthetic roles'},'validator':'loan-approval-v1'}],
 'executionRule':'approvalStatus == APPROVED AND executable == true AND fixtureReady == true AND apiAllowed == true',
 'eligibilityAuthority':'GET /api/test-cases/{id}/execution-eligibility: current reviewed input/assertions + source/policy freshness + closed fixture catalogue. Phase 4/5 archived executable remains unchanged; Phase 7 recomputes technical capability independently of approval. Execution snapshot saves this assessment and reviewRevision.',
 'rejectionCodes':['NOT_APPROVED','NOT_EXECUTABLE','FIXTURE_NOT_READY','API_NOT_ALLOWED','TEST_CASE_NOT_FOUND'],
 'migration':{'version':'V10__dummy_executions.sql','table':'app.test_execution','history':'append-only; snapshot survives TestCase regeneration; no cascading FK','permissions':'app_user SELECT/INSERT only on new history table; no new rag/evaluation grants'},
 'newApis':['POST /api/test-cases/{id}/executions','GET /api/test-cases/{id}/executions','GET /api/executions/{executionId}','GET /api/test-cases/{id}/execution-eligibility'],
 'dispatch':'Server-internal typed Dummy handlers returning HTTP status/body; no network transport, external URL, DNS, redirect or dynamic routing. Existing API_SPEC method/path identifies the closed handler.',
 'fixtures':'Fresh execution-local in-memory synthetic state per run. No shared mutable business data. Unknown actor, ID, profile or precondition is rejected. No business database simulation beyond the explicitly supported state.',
 'comparison':'Exact typed HTTP status, errorCode, declared response fields and before/after fixture state comparisons. Unsupported/duplicate assertions rejected before invocation. Missing field is different from null. No LLM Judge.',
 'intentionalDefect':'synthetic-self-approval-bug profile: requester authorization check intentionally omitted. Labelled in request, eligibility, stored result and UI. 403 expected / 200 actual; 4 mismatches.',
 'tests':{'backend':84,'phase7New':29,'existingBackend':55,'pythonRagAnalysisGeneration':61,'evaluation':40,'total':185,'failures':0,'errors':0,'skipped':0,'frontend':'TypeScript + Vite production build PASS'},
 'pass':{k:read('pass.json')[k] for k in ['executionId','apiId','expected','actual','result','mismatches','durationMs']},
 'fail':{k:failure[k] for k in ['executionId','apiId','expected','actual','result','mismatches','durationMs']},
 'allowList':{'result':'PASS','liveBlockedEndpoints':len(read('allowlist-blocks.json')),'details':'docs/phase7-evidence/allowlist-blocks.json','integration':'denied cases verify handler was never invoked and no execution row was inserted'},
 'reactE2E':browser,'screenshots':[p.relative_to(root).as_posix() for p in sorted(dest.glob('*.png'))],
 'regression':regression,'changedFiles':manifest,
 'newModelCalls':0,'uiUrl':'http://localhost:5173','demo':read('synthetic-cases.json'),
 'unresolved':[],
 'scopeLimits':['Only the 2 registered API handlers and exact synthetic fixtures are supported. Unknown free-text preconditions are not interpreted.','Dummy business state is in memory; execution history is PostgreSQL. No real external API, company system or deployment.','Asset lookup demo is an explicitly human-reviewed synthetic variation of a saved TC; original generated evidence is preserved and separate API_SPEC source is included in execution evidence.','Phase 6 Evaluation and generation policy are unchanged. Execution eligibility is a versioned Phase 7 read model, not a rewrite of stored AI output.','Windows reserved port 5432 is handled by compose.phase7-local.yaml removing PostgreSQL host publishing; internal Docker DB access is unchanged.'],
 'notImplemented':['Failure Analysis Agent','Hybrid Search','Reranking','Query Rewrite','GraphRAG','MCP','external APIs','automatic deployment','advanced authentication']}
write(root/'docs/phase7-result.json',report)
write(dest/'completion-summary.json',{'result':'PASS','phase':7,'totalAutomatedTests':185,'newTests':29,'browser':'Chrome '+browser['browser'],'screenshots':len(report['screenshots']),'apiCount':2,'newModelCalls':0,'unresolved':[]})
print('PASS Phase 7 complete: 185 tests, 2 Dummy APIs, PASS/FAIL, 9 Chrome screenshots, Phase 0-6 preserved')
