"""Freeze REST/source facts and independent evaluation expectations BEFORE any graph sync."""
from pathlib import Path
import json, hashlib, urllib.request, datetime
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'docs/phase11-evidence'; OUT.mkdir(exist_ok=True)
def get(path):
    try:
        with urllib.request.urlopen('http://localhost:8080'+path,timeout=20) as r:return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code==404:return None
        raise
ids=['b5270f71-c92c-48ae-8530-8946f1cfce62','80e2d374-0825-4811-a11e-03ade256b6e8','438c6b1b-e41e-4083-93da-72c0be1597bf']
sources=[]
for rid in ids:
    path='/api/requirements/'+rid
    batch=get(path+'/test-cases')
    sources.append(dict(requirement=get(path),analysis=get(path+'/analysis'),batch=batch,
        executions={c['testCaseId']:get('/api/test-cases/'+c['testCaseId']+'/executions') for c in (batch or {}).get('testCases',[])}))
(OUT/'source-facts.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2),encoding='utf8')
print([(s['requirement']['id'],[(c['testCaseId'],c['input']['endpoint'],[e['chunkId'] for e in c['evidence']]) for c in (s['batch'] or {}).get('testCases',[])]) for s in sources])
