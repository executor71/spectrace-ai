"""One representative real analysis only. Marker prevents accidental repetition."""
import asyncio,json,time
from pathlib import Path
import httpx
from workflow_otel import setup,span,trace,httpx_propagation
setup('legacy-assistant-demo');httpx_propagation()
dest=Path('/evidence');marker=dest/'real-analysis.json'
async def main():
    if marker.exists():raise SystemExit('Existing real analysis marker: refusing another LLM call')
    async with httpx.AsyncClient(timeout=660) as http:
        old=(await http.get('http://backend:8080/api/requirements/b5270f71-c92c-48ae-8530-8946f1cfce62')).json()
        response=await http.post('http://backend:8080/api/requirements',json={k:old[k] for k in ['title','description']});response.raise_for_status()
        identifier=response.json()['id']
        with span('workflow.real_analysis') as root:
            record={'requirementId':identifier,'traceId':format(root.get_span_context().trace_id,'032x'),'status':'STARTED','representativeRequirements':1}
            marker.write_text(json.dumps(record,indent=2));print('Starting single real analysis',identifier,flush=True)
            start=time.perf_counter()
            response=await http.post(f'http://backend:8080/api/requirements/{identifier}/analysis')
            record.update(status='COMPLETED' if response.status_code==200 else 'FAILED',httpStatus=response.status_code,latencyMs=(time.perf_counter()-start)*1000)
            marker.write_text(json.dumps(record,indent=2));response.raise_for_status()
            saved=await http.get(f'http://backend:8080/api/requirements/{identifier}/analysis');assert saved.json()==response.json()
            record['savedResultVerified']=True;marker.write_text(json.dumps(record,indent=2))
    trace.get_tracer_provider().force_flush();print(json.dumps(record))
asyncio.run(main())
