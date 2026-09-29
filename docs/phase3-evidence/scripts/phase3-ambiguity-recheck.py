from pathlib import Path
import json,time,urllib.request
root=Path(__file__).resolve().parents[3];dest=root/'docs/phase3-evidence'
rows=json.loads((dest/'live-analysis-results.json').read_text(encoding='utf-8'))
row=next(r for r in rows if r['case']=='ambiguous');rid=row['requirement']['id']
url='http://localhost:8080/api/requirements/'+rid+'/analysis'
start=time.perf_counter()
with urllib.request.urlopen(urllib.request.Request(url,data=b'{}',headers={'Content-Type':'application/json'}),timeout=650) as response:
    result=json.load(response);assert response.status==200
with urllib.request.urlopen(url,timeout=15) as response:assert json.load(response)==result
assert '빠르게' in ' '.join(result['ambiguousExpressions'])
assert '필요한 경우' in ' '.join(result['ambiguousExpressions'])
assert any('필요한 경우' in q for q in result['clarificationQuestions'])
assert not result['confirmedConditions']
row.update(analysis=result,checks='PASS',httpStatus=200,elapsedSeconds=round(time.perf_counter()-start,3),qualifierCoverageRechecked=True)
(dest/'live-analysis-results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
print('PASS real ambiguity recheck: both qualifiers identified; notification condition question present',row['elapsedSeconds'],flush=True)
