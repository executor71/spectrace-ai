"""Verify the actual recorded events, counts, correlation and safe metadata."""
import json
from pathlib import Path
import re

OUT = Path(__file__).resolve().parent


def rows(name):
    result = []
    for line in (OUT / name).read_text(encoding='utf8').splitlines():
        assert '\r' not in line and re.match(r'^\[\d{2}:\d{2}:\d{2}\] \[', line)
        fields = dict(re.findall(r'\b([A-Za-z]+)=([^\s]+)', line))
        assert {'event', 'service', 'workflow', 'jobId', 'runId', 'requirementId', 'traceId', 'stage', 'elapsedMs'} <= fields.keys()
        result.append(fields)
    return result


live = json.loads((OUT / 'live-results.json').read_text())
generated = json.loads((OUT / 'real-generation-results.json').read_text())
recorded = rows('real-workflow.log')
analysis = [row for row in recorded if row['workflow'] == 'ANALYSIS']
assert all(row['jobId'] == live['jobId'] for row in analysis)
assert len({row['runId'] for row in analysis}) == 1
assert len({row['traceId'] for row in analysis}) == 1
ai = [row for row in analysis if row['service'] == 'ai-service']
assert [row['event'] for row in ai] == ['WORKFLOW_STARTED', 'WORKFLOW_INITIALIZED', 'RETRIEVAL_COMPLETED', 'LLM_STARTED',
                                      'LLM_COMPLETED', 'EVIDENCE_VALIDATED', 'OUTPUT_VALIDATED', 'ANALYSIS_COMPLETED', 'WORKFLOW_COMPLETED']
assert int(next(row['count'] for row in ai if row['event'] == 'RETRIEVAL_COMPLETED')) == live['analysis']['evidence']
assert int(next(row['conditions'] for row in ai if row['event'] == 'ANALYSIS_COMPLETED')) == live['analysis']['conditions']
saved = [row for row in analysis if row['service'] == 'backend']
assert [row['event'] for row in saved] == ['RESULT_SAVED', 'WORKFLOW_COMPLETED']
assert all(row['persistence'] == 'COMMITTED' for row in saved)
held = [row for row in recorded if row['service'] == 'ai-service' and row['workflow'] == 'TEST_GENERATION']
assert not any(row['event'].startswith('LLM_') or row['event'] == 'TESTCASE_GENERATED' for row in held)
assert held[-1]['provider'] == 'POLICY_BLOCKED'
tc = rows('real-generation.log')
assert [row['event'] for row in tc] == ['WORKFLOW_STARTED', 'WORKFLOW_INITIALIZED', 'EVIDENCE_VALIDATED', 'POLICY_MATCHED',
                                      'LLM_STARTED', 'LLM_COMPLETED', 'TESTCASE_GENERATED', 'OUTPUT_VALIDATED', 'WORKFLOW_COMPLETED']
assert sum(row['event'] == 'LLM_STARTED' for row in tc) == generated['llmCalls'] == 1
assert int(next(row['testCases'] for row in tc if row['event'] == 'TESTCASE_GENERATED')) == generated['testCases'] == 5
assert not any(row['event'] == 'RESULT_SAVED' for row in tc)
for name in ['fake-analysis.log', 'fake-generation.log', 'policy-blocked.log', 'fake-timeout.log', 'invalid-output.log', 'cached-impact.log']:
    sample = rows(name)
    assert not any(row['event'].startswith('LLM_') for row in sample)
    assert not any(row['event'] == 'RESULT_SAVED' for row in sample)
    if name in {'fake-timeout.log', 'invalid-output.log'}:
        assert sample[-1]['event'] == 'WORKFLOW_FAILED'
        assert not any(row['event'] == 'WORKFLOW_COMPLETED' for row in sample)
for path in OUT.glob('*.log'):
    text = path.read_text(encoding='utf8')
    assert not re.search(r'SENSITIVE|SECRET|authorization:|Bearer |groundTruth|messages=|contentSnippet=', text, re.I)
report = {'result': 'PASS', 'realAnalysisProviderCalls': 1, 'realGenerationProviderCalls': 1, 'realTestCases': 5,
          'realPolicyHeldProviderCalls': 0, 'countEquality': 'PASS', 'eventOrderPerWorkflowAndService': 'PASS',
          'jobRunTraceCorrelation': 'PASS', 'safeSummaryMetadata': 'PASS'}
(OUT / 'artifact-verification.json').write_text(json.dumps(report, indent=2), encoding='utf8')
print(json.dumps(report))
