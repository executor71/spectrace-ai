import asyncio,json,time,statistics,math,argparse
from pathlib import Path
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
RID='b5270f71-c92c-48ae-8530-8946f1cfce62';TC='c53be0ea-3157-49be-a922-efa378d6ca11'
def stats(values):
    return dict(count=len(values),mean=statistics.mean(values),p50=statistics.median(values),p95=sorted(values)[math.ceil(.95*len(values))-1],max=max(values),samples=values)
async def main(args):
    result={}
    async with httpx.AsyncClient(timeout=120) as http:
      async with streamablehttp_client('http://mcp-server:8020/mcp/') as (r,w,_):
       async with ClientSession(r,w) as session:
        await session.initialize()
        for name in ['VECTOR','HYBRID','MCP_READ','DUMMY']:
            values=[]
            for index in range(14):
                t=time.perf_counter()
                if name=='VECTOR':
                    response=await http.post('http://ai-service:8000/internal/v1/search',json={'query':'자산 대여 승인','topK':5});response.raise_for_status()
                elif name=='HYBRID':
                    response=await http.post('http://retrieval-service:8010/internal/v1/retrieval',json={'queryId':'phase10-measure','queryText':'자산 대여 승인','strategy':'HYBRID'});response.raise_for_status()
                elif name=='MCP_READ':assert not (await session.call_tool('get_test_cases',{'requirementId':RID})).isError
                else:
                    response=await http.post(f'http://backend:8080/api/test-cases/{TC}/executions');response.raise_for_status();assert response.json()['result']=='PASS'
                duration=(time.perf_counter()-t)*1000
                if index>=2:values.append(duration)
            result[name]=stats(values)
    Path(args.output).write_text(json.dumps({'mode':args.mode,'unit':'ms','warmupCalls':2,'workflows':result},indent=2))
    print(json.dumps({name:{k:round(v,2) for k,v in s.items() if k!='samples'} for name,s in result.items()}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--mode',required=True);p.add_argument('--output',required=True);asyncio.run(main(p.parse_args()))
