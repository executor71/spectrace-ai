"""Query actual stored spans and correlate unchanged stdout summary identifiers."""
import json
from pathlib import Path
import re
import time
from urllib.request import urlopen

OUT=Path(__file__).resolve().parent
state=json.loads((OUT/'real-results.json').read_text())
index={}

def fields(line):return dict(re.findall(r'\b([A-Za-z]+)=([^\s]+)',line))
def query(tid):
    with urlopen('http://127.0.0.1:16686/api/traces/'+tid,timeout=10) as response:return json.load(response)

def verify(name,tid,required,job_id=None):
    for _ in range(30):
        result=query(tid)
        data=result.get('data') or []
        if data and required.issubset({s['operationName'] for s in data[0]['spans']}):break
        time.sleep(1)
    else:raise RuntimeError('Stored trace missing required spans: '+name)
    trace=data[0];assert trace['traceID']==tid
    rows=[]
    for span in sorted(trace['spans'],key=lambda s:s['startTime']):
        tags={t['key']:t['value'] for t in span['tags']}
        rows.append({'spanId':span['spanID'],'operation':span['operationName'],
                     'service':trace['processes'][span['processID']]['serviceName'],
                     'durationMs':span['duration']/1000,'tags':tags})
    if job_id:assert any(r['tags'].get('jobId')==job_id for r in rows)
    (OUT/(name+'-query-result.json')).write_text(json.dumps(result,indent=2),encoding='utf8')
    index[name]={'traceId':tid,'queryResult':'PASS','services':sorted({r['service'] for r in rows}),
                 'durationMs':(max(s['startTime']+s['duration'] for s in trace['spans'])-min(s['startTime'] for s in trace['spans']))/1000,
                 'spans':rows}

for name,required,key in [('analysis',{'analysis.job.execute','requirement.analysis','rag.search','query.embedding','vector.search','llm.generate','analysis.validation'},'qwen-analysis'),
                          ('tc-generation',{'testcase.generate','llm.generate'},'qwen-generation')]:
    rows=[fields(line) for line in (OUT/(key+'.actual.log')).read_text(encoding='utf8').splitlines()]
    llm=next(r for r in rows if r['event']=='LLM_STARTED')
    assert llm['provider']=='REAL_LLM' and llm['model']=='qwen2.5:7b-instruct'
    assert sum(r['event']=='LLM_STARTED' for r in rows)==sum(r['event']=='LLM_COMPLETED' for r in rows)==1
    assert any(r['event']=='RESULT_SAVED' and r['traceId']==llm['traceId'] for r in rows)
    job_id=state['analysis']['jobId'] if name=='analysis' else None
    if job_id:assert all(r['jobId']==job_id for r in rows)
    verify(name,llm['traceId'],required,job_id)
    index[name]['requirementId']=state['analysis' if name=='analysis' else 'generation']['requirementId']
    index[name]['jobId']=job_id
    index[name]['stdoutTraceCorrelation']='PASS'
    model_spans=[s for s in index[name]['spans'] if s['operation']=='llm.generate']
    assert len(model_spans)==1 and model_spans[0]['tags']['model']=='qwen2.5:7b-instruct'
    index[name]['realModelCalls']=1
if (OUT/'mcp-hitl-execution.actual.log').exists():
    rows=[fields(line) for line in (OUT/'mcp-hitl-execution.actual.log').read_text(encoding='utf8').splitlines()]
    for name,outcome in [('mcp-pass','PASS'),('mcp-defect-fail','FAIL'),('mcp-approval-blocked','ERROR')]:
        final=next(r for r in rows if r['service']=='mcp-server' and r.get('toolName')=='execute_approved_test' and r['status']!='START' and r['result']==outcome)
        verify(name,final['traceId'],{'mcp.tool'})
        index[name]['businessResult']=outcome
    review=next(r for r in rows if r['workflow']=='HITL_REVIEW' and r['event']=='HITL_COMPLETED' and r['result']=='APPROVED')
    verify('hitl-review',review['traceId'],set())
    index['hitl-review']['approvalOrigin']='VALIDATION_SCRIPT_REVIEW_API'
(OUT/'trace-index.json').write_text(json.dumps(index,indent=2),encoding='utf8')
print(json.dumps({name:{k:v for k,v in item.items() if k!='spans'} for name,item in index.items()}),flush=True)
