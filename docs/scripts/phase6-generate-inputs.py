"""Generation driver reads public inputs ONLY. Never imports/loads Ground Truth."""
from pathlib import Path
import json,time,urllib.request,urllib.error
root=Path(__file__).resolve().parents[2];dest=root/'docs/phase6-evidence'
public=json.loads((root/'evaluation-service/datasets/public-requirements.json').read_text(encoding='utf-8'))
state=dest/'generation-inputs.json'
results=json.loads(state.read_text(encoding='utf-8')) if state.exists() else []
def save():state.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
def call(path,body=None):
    request=urllib.request.Request('http://localhost:8080'+path,data=None if body is None else json.dumps(body,ensure_ascii=False).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=650) as response:return json.load(response)
for spec in public:
    row=next((r for r in results if r['caseId']==spec['caseId']),None)
    if row is None:
        requirement=call('/api/requirements/'+spec['existingRequirementId']) if 'existingRequirementId' in spec else call('/api/requirements',{k:spec[k] for k in ['title','description']})
        row={'caseId':spec['caseId'],'split':spec['split'],'requirement':requirement};results.append(row);save()
    rid=row['requirement']['id']
    if row.get('complete'):continue
    print('START public input',spec['caseId'],rid,flush=True);start=time.perf_counter()
    try:
        if spec['split']=='development':
            row['analysis']=call('/api/requirements/'+rid+'/analysis');row['generation']=call('/api/requirements/'+rid+'/test-cases');row['newLlmCalls']=0
        else:
            # Reuse saved partial work on retries; never silently rerun successful model calls.
            if 'analysis' not in row:row['analysis']=call('/api/requirements/'+rid+'/analysis',{});save()
            if 'generation' not in row:row['generation']=call('/api/requirements/'+rid+'/test-cases/generate',{});save()
            row['newLlmCalls']=row['generation']['llmCalls']
        row['complete']=True;row['elapsedSeconds']=round(time.perf_counter()-start,3);save()
        print('DONE',spec['caseId'],'testCases',len(row['generation']['testCases']),'seconds',row['elapsedSeconds'],flush=True)
    except urllib.error.HTTPError as error:
        row['error']={'status':error.code,'body':error.read().decode()};save();raise
