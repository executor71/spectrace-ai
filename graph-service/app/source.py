"""Read-only REST projection source. No PostgreSQL/evaluation credentials or LLM calls."""
import json
from pathlib import Path
import httpx
from .model import APIS

SCOPE=Path('/graph/data/scope.json')
CATALOG=Path('/graph/data/knowledge.json')

def collect(client=None):
    with httpx.Client(base_url='http://backend:8080',timeout=10,trust_env=False,follow_redirects=False) if client is None else client as http:
        def get(path,optional=False):
            response=http.get(path)
            if optional and response.status_code==404:return None
            response.raise_for_status();return response.json()
        result=[]
        for rid in json.loads(SCOPE.read_text()):
            path='/api/requirements/'+rid
            batch=get(path+'/test-cases',True)
            result.append(dict(requirement=get(path),analysis=get(path+'/analysis',True),batch=batch,
                executions={c['testCaseId']:get('/api/test-cases/'+c['testCaseId']+'/executions') for c in (batch or {}).get('testCases',[])}))
    return result,json.loads(CATALOG.read_text())

def project(sources,chunks):
    nodes={}; edges={}; skipped=[]
    by_chunk={c['chunkId']:c for c in chunks}
    def node(t,i,**props):nodes[t,i]={'type':t,'id':i,**props}
    def edge(st,si,rel,tt,ti,evidence=()):
        assert (st,si) in nodes and (tt,ti) in nodes
        k=(st,si,rel,tt,ti)
        old=edges.get(k,{}).get('evidenceChunkIds',[])
        edges[k]=dict(sourceType=st,source=si,relation=rel,targetType=tt,target=ti,evidenceChunkIds=sorted(set(old)|set(evidence)))
    for c in chunks:
        node('Evidence',c['chunkId'],documentId=c['documentId'],documentType=c['documentType'],section=c['section'])
        if c['documentType']=='BUSINESS_RULE':node('BusinessRule',c['documentId'],title=c['documentKey'])
    for route,aid in APIS.items():
        specs=[c for c in chunks if c['documentType']=='API_SPEC' and route in c['metadata']['relatedApis']]
        if not specs:raise ValueError('Missing API specification')
        node('Api',aid,method=route.split(' ',1)[0],pathTemplate=route.split(' ',1)[1],specificationChunkIds=[c['chunkId'] for c in specs])
    for c in chunks:
        if c['documentType']=='BUSINESS_RULE':
            for route in c['metadata']['relatedApis']:
                if route in APIS:edge('BusinessRule',c['documentId'],'IMPLEMENTED_BY','Api',APIS[route],[c['chunkId']])
    for source in sources:
        req=source['requirement'];rid=req['id'];node('Requirement',rid,title=req['title'])
        analysis=source['analysis'] or {}
        for item in analysis.get('relatedBusinessRules',[]):
            c=by_chunk.get(item['chunkId'])
            if c and c['documentType']=='BUSINESS_RULE' and item['text'] in c['content']:
                edge('Requirement',rid,'SUPPORTED_BY','BusinessRule',c['documentId'],[c['chunkId']])
        for item in analysis.get('relatedApis',[]):
            c=by_chunk.get(item['chunkId']);route=item['api']
            if c and route in APIS and route in c['metadata']['relatedApis']:
                edge('Requirement',rid,'AFFECTS','Api',APIS[route],[c['chunkId']])
        for tc in (source['batch'] or {}).get('testCases',[]):
            tid=tc['testCaseId'];revision=tc['reviewRevision']
            node('TestCase',tid,requirementId=rid,scenario=tc['scenario'],approvalStatus=tc['approvalStatus'],reviewRevision=revision)
            edge('Requirement',rid,'GENERATES','TestCase',tid)
            refs=[]
            for ref in tc['evidence']:
                c=by_chunk.get(ref['chunkId'])
                if c and c['documentId']==ref['documentId']:
                    refs.append(c);edge('TestCase',tid,'BASED_ON','Evidence',c['chunkId'],[c['chunkId']])
            inp=tc['input'];route=inp.get('method','')+' '+inp.get('endpoint','');aid=APIS.get(route)
            if aid and inp.get('apiId',aid)==aid:
                edge('Api',aid,'VERIFIED_BY','TestCase',tid,nodes['Api',aid]['specificationChunkIds'])
                # Generated evidence stays BASED_ON; verification requires current endpoint agreement.
                for c in refs:
                    if c['documentType']=='BUSINESS_RULE' and route in c['metadata']['relatedApis']:
                        edge('BusinessRule',c['documentId'],'VERIFIED_BY','TestCase',tid,[c['chunkId']])
            else:skipped.append({'testCaseId':tid,'reason':'NO_CANONICAL_API_MATCH'})
            for ex in source['executions'][tid]:
                assert ex['testCaseId']==tid and ex['requirementId']==rid
                node('Execution',ex['executionId'],testCaseId=tid,requirementId=rid,apiId=ex['apiId'],testCaseRevision=ex['testCaseRevision'],executedAt=ex['executedAt'],result=ex['result'],durationMs=ex['durationMs'],syntheticDefect=ex['syntheticDefect'])
                edge('TestCase',tid,'EXECUTED_AS','Execution',ex['executionId'])
    return {'nodes':sorted(nodes.values(),key=lambda x:(x['type'],x['id'])),'edges':sorted(edges.values(),key=lambda x:(x['sourceType'],x['source'],x['relation'],x['target'])),'skipped':skipped}
