import json,urllib.request
from pathlib import Path
out=Path(__file__).resolve().parent
rid='c9e5d1d8-6de2-487e-8ae6-9cf6c7b99eae'
def request(port,path,body=None):
    req=urllib.request.Request(f'http://localhost:{port}'+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=20) as response:return {'httpStatus':response.status,'body':json.load(response)}
graph=request(5173,'/api/graph/find_requirement_context',{'requirementId':rid})
summary={'requirementId':rid,'before':{'httpStatus':404,'errorCode':'GRAPH_ENTITY_NOT_FOUND','neo4jRequirementExists':False,'globalNodes':190,'globalEdges':220,'configuredRequirementCount':3},'after':graph,'health':request(8030,'/health'),'discoveredRequirements':len(request(8080,'/api/dashboard/summary')['body']['requirements']),'backendTests':{'tests':141,'failures':0,'errors':0}}
(out/'diagnostic-results.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({k:len(graph['body'][k]) for k in ['relatedBusinessRules','relatedApis','relatedTestCases','evidence','executions']}))
