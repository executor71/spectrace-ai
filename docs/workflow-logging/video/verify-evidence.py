"""Verify captured actual rows and preserve a source-to-event audit."""
import ast
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import subprocess
from watch_summary_import import capture, viewer

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
live=json.loads((OUT/'real-results.json').read_text())
mcp=json.loads((OUT/'mcp-results.json').read_text())
assert mcp['result']=='PASS'
archive=OUT/'mcp-hitl-execution.actual.log'
all_lines=archive.read_text(encoding='utf8').splitlines() if archive.exists() else capture('mcp-hitl-execution',mcp['since'])


def fields(line):return dict(re.findall(r'\b([A-Za-z]+)=([^\s]+)',line))


def save_subset(name,lines):
    assert lines
    (OUT/(name+'.actual.log')).write_text('\n'.join(lines)+'\n',encoding='utf8')
    (OUT/(name+'.video.log')).write_text('\n'.join(viewer.project(line) for line in lines)+'\n',encoding='utf8')


for name,outcome in [('normal-pass','PASS'),('intentional-fail','FAIL'),('approval-blocked','ERROR')]:
    final=next(fields(line) for line in all_lines if 'service=mcp-server ' in line and 'toolName=execute_approved_test ' in line and 'status=START ' not in line and fields(line)['result']==outcome)
    trace=final['traceId'];assert re.fullmatch(r'[0-9a-f]{32}',trace)
    lines=[line for line in all_lines if fields(line)['traceId']==trace]
    assert fields(lines[0])['event']=='TOOL_STARTED'
    assert fields(lines[-1])['event'] in {'TOOL_COMPLETED','TOOL_FAILED'}
    backend=[fields(line) for line in lines if 'service=backend ' in line]
    assert backend and all(row['runId']==final['runId'] for row in backend)
    events=[row['event'] for row in backend]
    if outcome=='ERROR':
        assert events==['EXECUTION_STARTED','EXECUTION_FAILED']
    else:
        assert events==['EXECUTION_STARTED','DUMMY_STARTED','DUMMY_COMPLETED','ASSERTION_STARTED',
                        'ASSERTION_COMPLETED' if outcome=='PASS' else 'ASSERTION_FAILED','RESULT_SAVED','EXECUTION_COMPLETED']
        assert backend[-1]['result']==outcome
        assert int(backend[-1]['mismatches'])==mcp['normalId' if outcome=='PASS' else 'defectId']['mismatches']
        assert final['toolStatus']=='SUCCESS'
        assert next(row for row in backend if row['event']=='DUMMY_STARTED')['dispatch']=='IN_PROCESS'
    save_subset(name,lines)
save_subset('hitl-review',[line for line in all_lines if fields(line)['workflow']=='HITL_REVIEW'])
for key in ['qwen-analysis','qwen-generation']:
    path=OUT/(key+'.actual.log');lines=path.read_text(encoding='utf8').splitlines();save_subset(key,lines)
    rows=[fields(line) for line in lines]
    assert sum(row['event']=='LLM_STARTED' for row in rows)==1
    assert sum(row['event']=='LLM_COMPLETED' for row in rows)==1
    assert any(row['event']=='STRUCTURED_OUTPUT_COMPLETED' for row in rows)
    assert any(row['event']=='EVIDENCE_VALIDATED' for row in rows)
    assert any(row['event']=='RESULT_SAVED' for row in rows)
    if key=='qwen-analysis':
        assert int(next(row['conditions'] for row in rows if row['event']=='ANALYSIS_COMPLETED'))==live['analysis']['conditions']
    else:
        assert int(next(row['testCases'] for row in rows if row['event']=='TESTCASE_GENERATED'))==live['generation']['testCases']==5
groups=defaultdict(list)
for path in [OUT/'qwen-analysis.actual.log',OUT/'qwen-generation.actual.log',OUT/'mcp-hitl-execution.actual.log']:
    for line in path.read_text(encoding='utf8').splitlines():
        row=fields(line)
        assert row['status'] in {'START','COMPLETE','FAILED'}
        assert 'result' in row and 'provider' in row
        assert row['jobId']!='-' or re.fullmatch(r'[0-9a-f]{32}',row['traceId'])
        groups[(row['service'],row['runId'])].append(int(row['seq']))
        assert not re.search(r'PRIVATE|SECRET|groundTruth|contentSnippet=|messages=|Bearer ',line,re.I)
for seqs in groups.values(): assert seqs==list(range(1,len(seqs)+1)),seqs
report={'result':'PASS','realQwenAnalysisCalls':1,'realQwenGenerationCalls':1,'generatedAndPersistedTestCases':5,
        'realMcpCalls':len(mcp['tools']),'mcpProtocol':'Streamable HTTP / ClientSession','normalResult':mcp['normalId']['result'],
        'defectResult':mcp['defectId']['result'],'defectMismatches':mcp['defectId']['mismatches'],'approvalBlocked':'NOT_APPROVED',
        'approvalOrigin':'VALIDATION_SCRIPT_REVIEW_API (not human click evidence)','perServiceRunSequence':'PASS',
        'mcpBackendTraceAndRunCorrelation':'PASS','safeMetadata':'PASS'}
(OUT/'evidence-verification.json').write_text(json.dumps(report,indent=2),encoding='utf8')
print(json.dumps(report))

# Compare business prompts, graph topology, policy/corpus/evaluation contracts.
def tree(rel,old=False):
    text=subprocess.check_output(['git','show','HEAD:'+rel]).decode('utf8') if old else (ROOT/rel).read_text(encoding='utf8')
    return ast.parse(text)
def assigns(t,name):
    return [ast.dump(node.value,include_attributes=False) for node in ast.walk(t) if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id==name for target in node.targets)]
preservation={}
for rel in ['ai-service/app/analysis_service.py','ai-service/app/test_case_service.py','ai-service/app/change_impact.py']:
    preservation[rel+':messagesUnchanged']=assigns(tree(rel),'messages')==assigns(tree(rel,True),'messages')
preservation['analysisSystemUnchanged']=assigns(tree('ai-service/app/analysis_service.py'),'SYSTEM')==assigns(tree('ai-service/app/analysis_service.py',True),'SYSTEM')
def topology(t):
    return [ast.dump(n,include_attributes=False) for n in ast.walk(t) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in {'add_node','add_edge','add_conditional_edges'}]
preservation['langgraphTopologyUnchanged']=topology(tree('ai-service/app/change_impact.py'))==topology(tree('ai-service/app/change_impact.py',True))
preservation['frozenContractsUnchanged']=subprocess.run(['git','diff','--quiet','--','contracts','knowledge','evaluation-service/datasets','ai-service/app/llm_provider.py','backend/src/main/resources/db/migration']).returncode==0
starting=json.loads((OUT/'starting-worktree.json').read_text())
for rel in ['backend/src/main/java/com/example/legacyassistant/testcase/ExecutionService.java','backend/src/main/java/com/example/legacyassistant/testcase/TestCaseReviewService.java']:
    preservation[rel+':businessSourceUnchanged']=hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()==starting[rel]
assert all(preservation.values())
(OUT/'source-preservation.json').write_text(json.dumps(preservation,indent=2),encoding='utf8')
