import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

out=Path(__file__).resolve().parent
results={}
for name in ['return-pass','return-fail','return-error']:
    run=json.loads((out/(name+'.json')).read_text(encoding='utf8'))
    query=urllib.parse.urlencode({'service':'legacy-assistant-backend','limit':20,'lookback':'1h','tags':json.dumps({'executionId':run['executionId']})})
    with urllib.request.urlopen('http://localhost:16686/api/traces?'+query,timeout=20) as response:traces=json.load(response)['data']
    assert traces,(name,'Trace missing')
    trace=traces[0];spans={span['operationName'] for span in trace['spans']}
    assert {'dummy.execution','execution.allowlist','execution.fixture.initialize'}<=spans,spans
    if name!='return-error':assert {'execution.dummy.invoke','execution.assertions'}<=spans,spans
    roots=[span for span in trace['spans'] if span['operationName']=='dummy.execution']
    tags={tag['key']:tag['value'] for span in roots for tag in span['tags']}
    assert tags.get('executionId')==run['executionId'] and tags.get('testCaseId')==run['testCaseId']
    assert tags.get('result')==run['result'] and tags.get('allowListValidated') is True
    serialized=json.dumps(trace)
    assert 'accessoriesReturned' not in serialized and 'damageDescription' not in serialized
    results[name]={'traceId':trace['traceID'],'executionId':run['executionId'],'result':run['result'],'spans':sorted(spans),'noRequestBodyTags':True}
    (out/(name+'-trace.json')).write_text(json.dumps(trace,ensure_ascii=False,indent=2),encoding='utf8')
(out/'trace-results.json').write_text(json.dumps(results,indent=2),encoding='utf8')
print(json.dumps(results))
