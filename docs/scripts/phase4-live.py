"""smoke: two cases only; final: five saved analysis cases. Never runs a new search."""
import json, sys, time, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
DEST=ROOT/'docs/phase4-evidence'
CASES=json.loads((ROOT/'docs/phase3-evidence/live-analysis-results.json').read_text(encoding='utf-8'))
mode=sys.argv[1]
if mode=='smoke': CASES=[x for x in CASES if x['case'] in ['sufficient','insufficient']]
assert mode in ['smoke','final']

def call(path, post=False):
    req=urllib.request.Request('http://localhost:8080'+path, data=b'{}' if post else None,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=650) as response: return json.load(response)

rows=[]
for entry in CASES:
    name=entry['case'];rid=entry['requirement']['id'];route='/api/requirements/'+rid+'/test-cases'
    print('START',mode,name,flush=True);start=time.perf_counter()
    result=call(route+'/generate',True);elapsed=round(time.perf_counter()-start,3)
    saved=call(route);assert result==saved,'POST/GET differs'
    analysis=call('/api/requirements/'+rid+'/analysis');assert result['sourceAnalysis']==analysis
    refs={(e['documentId'],e['chunkId']) for e in analysis['evidence']}
    for case in result['testCases']:
        assert case['requirementId']==rid and len(case)==10
        assert all((e['documentId'],e['chunkId']) in refs for e in case['evidence'])
        assert not case['executable'],'No fixture provider in Phase 4'
        assert any(case['expectedResult']['description'] in e['contentSnippet'] for e in analysis['evidence'])
        assert case['input']['method']=='POST' and case['input']['endpoint']=='/loans/{loanId}/approve'
    if name=='sufficient':
        assert {c['type'] for c in result['testCases']}=={'NORMAL','EXCEPTION','AUTHORIZATION','BOUNDARY','BUSINESS_RULE'}
        assert not result['clarificationRequired'] and not result['uncoveredTypes']
        assert 1<=result['llmCalls']<=2
    else:
        assert not result['testCases'] and result['clarificationRequired'] and result['llmCalls']==0
    row={'case':name,'requirementId':rid,'checks':'PASS','httpElapsedSeconds':elapsed,'result':result}
    rows.append(row);(DEST/(mode+'-test-cases.json')).write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    print('PASS',name,'cases',len(result['testCases']),'llmCalls',result['llmCalls'],'http_seconds',elapsed,flush=True)
print('ALL_PASS',len(rows),flush=True)
