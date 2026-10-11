"""Run only while Neo4j is stopped; uses stored analysis (zero model calls)."""
import asyncio,json
from pathlib import Path
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
R='b5270f71-c92c-48ae-8530-8946f1cfce62';T='c53be0ea-3157-49be-a922-efa378d6ca11'
results=[]
async def main():
 async with httpx.AsyncClient(timeout=30) as http:
    async def check(name,method,url,body=None,status=200):
        r=await http.request(method,url,**({'json':body} if body else {}));assert r.status_code==status,(name,r.status_code,r.text)
        results.append({'name':name,'status':r.status_code});return r.json()
    await check('graph unavailable','POST','http://graph-service:8030/api/graph/find_requirement_context',{'requirementId':R},503)
    for name,path in [('requirement',''),('saved analysis','/analysis'),('testcases and reviews','/test-cases')]:await check(name,'GET','http://backend:8080/api/requirements/'+R+path)
    await check('evaluation','GET','http://evaluation-service:8090/api/requirements/'+R+'/evaluations')
    ex=await check('dummy execution','POST','http://backend:8080/api/test-cases/'+T+'/executions',status=201);assert ex['result']=='PASS'
    await check('vector','POST','http://ai-service:8000/internal/v1/search',{'query':'자산 대여 승인','topK':5})
    await check('hybrid','POST','http://retrieval-service:8010/internal/v1/retrieval',{'queryId':'graph-outage','queryText':'자산 대여 승인','strategy':'HYBRID'})
    context=await check('context degrades to text','POST','http://graph-service:8030/api/graph/analysis-context',{'requirementId':R})
    assert context['graphStatus']=='UNAVAILABLE' and len(context['textEvidence'])==5 and not context['analysisRelations']
 async with streamablehttp_client('http://mcp-server:8020/mcp/') as (r,w,_):
  async with ClientSession(r,w) as session:
    await session.initialize()
    for name,args in [('search_knowledge',{'query':'자산 대여 승인','strategy':'HYBRID'}),('analyze_requirement',{'requirementId':R}),('get_test_cases',{'requirementId':R}),('get_evaluation_result',{'requirementId':R}),('execute_approved_test',{'testCaseId':T})]:
        r=await session.call_tool(name,args);assert not r.isError,(name,r)
        if name=='analyze_requirement':assert r.structuredContent['analysisSource']=='SAVED'
        results.append({'name':'MCP '+name,'status':'PASS'})
    r=await session.call_tool('find_requirement_context',{'requirementId':R});assert r.isError
    results.append({'name':'MCP graph failure isolated','status':'PASS','error':r.structuredContent})
 Path('/evidence/neo4j-outage.json').write_text(json.dumps({'result':'PASS','realModelCalls':0,'checks':results},ensure_ascii=False,indent=2))
asyncio.run(main());print('PASS',len(results),'outage checks')
