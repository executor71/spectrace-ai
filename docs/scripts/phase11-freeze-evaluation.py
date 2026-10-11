"""Curated source assertions. Never imports graph code or queries Neo4j."""
from pathlib import Path
import json,hashlib,datetime
root=Path(__file__).resolve().parents[2]; out=root/'docs/phase11-evidence'
target=out/'relation-ground-truth.json'
if target.exists():raise SystemExit('Already frozen: refusing to overwrite')
sources=json.loads((out/'source-facts.json').read_text(encoding='utf8'))
R='b5270f71-c92c-48ae-8530-8946f1cfce62'; S='80e2d374-0825-4811-a11e-03ade256b6e8'; R10='438c6b1b-e41e-4083-93da-72c0be1597bf'
B='7cea4fe7-6b00-56c9-be35-3194aeecb923'; A='API-LOAN-APPROVE'
original=['c53be0ea-3157-49be-a922-efa378d6ca11','c0dca00f-7a4c-4861-ba42-06c7588235b1','0cdd544d-a755-412a-88e5-78f570c427c2','4b357887-da03-4295-9399-78b5ae5a587d','f25fc98b-f047-4799-88dc-7fa77dd579b1']
synthetic=['d4723cf0-56bd-46ff-b572-7ca83c586e29','4611bca5-0d0c-45dd-9793-75566c432c89','e35a6d9c-e7f2-4546-9f34-d597e9ae9627']
def n(t,i):return {'type':t,'id':i}
def p(nodes,rels):return {'path':nodes,'relations':rels}
def chain(r,t):return p([n('Requirement',r),n('BusinessRule',B),n('Api',A),n('TestCase',t)],['SUPPORTED_BY','IMPLEMENTED_BY','VERIFIED_BY'])
queries=[]
def add(text,tool,args,paths,target_types,negative=False):
    entities=sorted({(v['type'],v['id']) for path in paths for v in path['path'] if v['type'] in target_types})
    queries.append(dict(id=f'GQ{len(queries)+1:02}',question=text,tool=tool,arguments=args,expectedEntities=[n(*e) for e in entities],expectedPaths=paths,targetTypes=target_types,negative=negative,hops=max([len(x['relations']) for x in paths] or [2])))
for r,ts in [(R,original),(S,synthetic)]:
    for t in ts:
        add(f'대여 승인 테스트 {t}의 원 요구사항, 업무규칙, API를 근거 경로로 추적한다.','trace_test_case_origin',{'testCaseId':t},[chain(r,t)],['Requirement','BusinessRule','Api'])
for r,ts in [(R,original),(S,synthetic)]:
    add(f'자기 승인 금지 요구사항 {r}에서 승인 규칙과 API를 거쳐 생성된 테스트까지 추적한다.','find_requirement_context',{'requirementId':r},[chain(r,t) for t in ts],['BusinessRule','Api','TestCase'])
add(f'업무규칙 {B} 변경 시 승인 API를 거쳐 영향받는 테스트는?','find_impacted_tests',{'businessRuleId':B},[p([n('BusinessRule',B),n('Api',A),n('TestCase',t)],['IMPLEMENTED_BY','VERIFIED_BY']) for t in original+synthetic],['Api','TestCase'])
add('가용 재고 판정 규칙 변경 시 대여 승인 API를 사용하는 테스트 영향 범위는?','find_impacted_tests',{'businessRuleId':'ebe8e234-e065-5b9d-b9ba-b09cccbc3ec6'},[p([n('BusinessRule','ebe8e234-e065-5b9d-b9ba-b09cccbc3ec6'),n('Api',A),n('TestCase',t)],['IMPLEMENTED_BY','VERIFIED_BY']) for t in original+synthetic],['Api','TestCase'])
add('반납 규칙에서 현재 등록된 대표 API와 테스트까지 영향 경로가 존재하는가?','find_impacted_tests',{'businessRuleId':'94dcaeab-5ab5-5aff-9af6-8e78cbe0f429'},[],['Api','TestCase'],True)
add('변조 Endpoint 테스트를 승인 API 검증 테스트로 오인하지 않는가?','trace_test_case_origin',{'testCaseId':'1f521e4c-458b-4c09-95f3-4e6d26ea112a'},[],['Api'],True)
add('자산 조회로 수정된 테스트의 생성 근거를 승인 업무 검증 관계로 오인하지 않는가?','trace_test_case_origin',{'testCaseId':'889ea853-67f3-49a0-b2b3-2ff94520f094'},[],['BusinessRule'],True)
add('Phase 10의 저장된 자기 승인 금지 분석에서 규칙과 API까지 추적한다.','find_requirement_context',{'requirementId':R10},[p([n('Requirement',R10),n('BusinessRule',B),n('Api',A)],['SUPPORTED_BY','IMPLEMENTED_BY'])],['BusinessRule','Api'])
# Historic executions are fixed by source identifiers, never by graph output.
for tid in synthetic[:2]:
    history=sources[1]['executions'][tid]
    assert history
    ex=history[0]
    add(f'테스트 {tid}의 요구사항부터 저장된 {ex["result"]} 실행 {ex["executionId"]}까지 경로는?','trace_test_case_origin',{'testCaseId':tid},[p([n('Requirement',S),n('TestCase',tid),n('Execution',ex['executionId'])],['GENERATES','EXECUTED_AS'])],['Requirement','Execution'])
add('존재하지 않는 요구사항의 관계를 추정하지 않는가?','find_requirement_context',{'requirementId':'00000000-0000-4000-8000-000000000999'},[],['BusinessRule','Api','TestCase'],True)
add('존재하지 않는 업무규칙의 영향 테스트를 추정하지 않는가?','find_impacted_tests',{'businessRuleId':'00000000-0000-4000-8000-000000000998'},[],['Api','TestCase'],True)
assert len(queries)==20
doc=dict(frozenAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),sourceSha256=hashlib.sha256((out/'source-facts.json').read_bytes()).hexdigest(),method='Source-reviewed ID/path assertions frozen before graph schema or sync. No graph imports or graph responses. API scope is the two existing Phase7 registry IDs.',queries=queries)
target.write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf8')
(out/'relation-ground-truth.sha256').write_text(hashlib.sha256(target.read_bytes()).hexdigest())
print('Frozen',len(queries),'queries',doc['frozenAt'])
