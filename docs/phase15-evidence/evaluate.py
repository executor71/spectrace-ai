"""Offline fixture conformity only. Never imported by generation or service code."""
import json
from pathlib import Path
out=Path(__file__).resolve().parent
read=lambda name:json.loads((out/name).read_text(encoding='utf8'))
fixture=read('evaluation-fixture.json');baseline=read('baseline-snapshot.json');raw=read('analysis-result.json');final=read('final-analysis-result.json')
expected={'approval.actor.부서장':'UNCHANGED','approval.actor.자산관리 담당자':'ADDED','approval.self.denied':'UNCHANGED'}
actual={c.get('conditionKey'):c['changeType'] for c in final['conditionChanges']}
def pr(actual,expected):return dict(precision=len(actual&expected)/len(actual) if actual else None,recall=len(actual&expected)/len(expected) if expected else None,returned=len(actual),expected=len(expected))
expected_apis=set(fixture['cases'][0]['expectedApiIds']);actual_apis={a['apiId'] for a in final['affectedApis']}
expected_tcs={t['testCaseId'] for t in baseline['testCases']['testCases']};actual_tcs={t['testCaseId'] for t in final['affectedTestCases']}
known={e['chunkId'] for e in final['evidenceRefs']};citations=[c for item in final['conditionChanges'] for c in item['evidenceChunkIds']]
report=dict(scope='Single author-draft synthetic fixture; human reference review pending; not a general accuracy estimate',cases=1,humanApproved=False,rawModelRequiredClassCoverage=len({'ADDED','UNCHANGED'}&{c['changeType'] for c in raw['conditionChanges']})/2,finalAtomicClassificationConformity=sum(actual.get(k)==v for k,v in expected.items())/len(expected),impactedApi=pr(actual_apis,expected_apis),impactedTcCandidateSet=pr(actual_tcs,expected_tcs),evidenceCitationIdValidity=sum(c in known for c in citations)/len(citations) if citations else None,unsupportedChangeDetected=all(s['templateSupport']=='TEMPLATE_UNSUPPORTED' and s['expectedResult'] is None and not s['automaticExecutionSupported'] for s in final['newTestSuggestions']),realProviderCalls=1,rawModelAnalysisDurationMs=raw['analysisDurationMs'],reprocessingProviderCalls=final['llmCallCount'],reprocessingDurationMs=final['analysisDurationMs'],developerReviewCorrectionRate=None,limitations=['One curated source fixture, no independent human approval','Model missed unchanged self-approval prohibition; narrow source-quoted guard reconciled cached output','TC candidate set conformity does not establish precise semantic impact relevance','Human correction rate not measured','Existing Phase11 metrics and Ground Truth remain separate'])
(out/'evaluation-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(report,ensure_ascii=True,indent=2))
