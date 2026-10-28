"""Run in an isolated AI test container; produces metadata-only fake examples."""
import contextlib
from copy import deepcopy
import io
import json
from pathlib import Path
import sys
from unittest.mock import Mock

sys.path.insert(0, '/app/tests')
import test_analysis as analysis
import test_test_case_generation as generation
import test_change_impact as impact
from app.analysis_service import AnalysisService
from app.llm_provider import LlmTimeoutError

OUT = Path('/evidence')
results = []


def capture(name, operation, expected=None):
    output = io.StringIO()
    error = None
    with contextlib.redirect_stdout(output):
        try:
            result = operation()
        except Exception as caught:
            if expected is None or not isinstance(caught, expected):
                raise
            error = type(caught).__name__
    assert bool(expected) == bool(error)
    (OUT / (name + '.log')).write_text(output.getvalue(), encoding='utf8')
    results.append({'case': name, 'expectedError': error, 'summaryLines': len(output.getvalue().splitlines()), 'realModelCalls': 0})


fixture = generation.TestCaseGenerationTest()
generator, provider = fixture.generator()
capture('fake-generation', lambda: generator.generate(fixture.request()))
source = deepcopy(generation.SOURCE)
source['confirmedConditions'][0]['text'] = '대여 신청은 PENDING_APPROVAL로 생성된다.'
generator, provider = fixture.generator()
capture('policy-blocked', lambda: generator.generate(fixture.request(source)))
provider.generate.assert_not_called()
generator, provider = fixture.generator()
provider.generate.side_effect = LlmTimeoutError('SENSITIVE_EXCEPTION_MUST_NOT_APPEAR')
capture('fake-timeout', lambda: generator.generate(fixture.request()), LlmTimeoutError)
generator, provider = fixture.generator('SENSITIVE_MODEL_OUTPUT_MUST_NOT_APPEAR')
capture('invalid-output', lambda: generator.generate(fixture.request()), generation.InvalidTestCasesError)
search = Mock(); search.search.return_value = [analysis.HIT]
provider = Mock(); provider.generate.return_value = analysis.draft()
capture('fake-analysis', lambda: AnalysisService(search, provider).analyze(analysis.REQUEST))
request = impact.request(); request['cachedModelChanges'] = impact.condition_diff(request, impact.provider())
provider = Mock(); search = Mock(); search.search.return_value = []
capture('cached-impact', lambda: impact.Workflow(search, provider, lambda _: impact.graph()).analyze(request))
provider.generate.assert_not_called()
assert all('SENSITIVE' not in path.read_text() for path in OUT.glob('*.log'))
(OUT / 'fake-results.json').write_text(json.dumps(results, indent=2), encoding='utf8')
print(json.dumps(results), flush=True)
