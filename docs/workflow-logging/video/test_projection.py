import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('projection',Path(__file__).with_name('watch-summary.py'))
projection=importlib.util.module_from_spec(spec);spec.loader.exec_module(projection)


class ProjectionTests(unittest.TestCase):
    def row(self,extra=''):
        return '[13:00:01] [Tool] fixture event=TOOL_COMPLETED stream=SUMMARY label=Tool seq=2 status=COMPLETE result=FAIL service=mcp-server jobId=- traceId=1234567890abcdef1234567890abcdef runId=11111111-1111-4111-8111-111111111111 provider=NO_LLM_CALL toolName=execute_approved_test '+extra
    def test_ordinary_logs_are_excluded(self):
        self.assertIsNone(projection.project('INFO GET /health 200'))
        self.assertIsNone(projection.project('[13:00:01] event=LLM_STARTED'))
    def test_failed_assertion_keeps_successful_tool_dispatch_and_full_trace(self):
        output=projection.project(self.row())
        self.assertIn('COMPLETE result=FAIL',output)
        self.assertIn('traceId=1234567890abcdef1234567890abcdef',output)
        self.assertIn('toolName=execute_approved_test',output)
    def test_projection_preserves_measured_values_and_ignores_arbitrary_payload(self):
        output=projection.project(self.row('count=5 durationMs=123 payload=PRIVATE'))
        self.assertIn('#2',output);self.assertIn('count=5',output);self.assertIn('durationMs=123',output)
        self.assertNotIn('PRIVATE',output)
    def test_incomplete_lines_cannot_be_presented_as_evidence(self):
        self.assertIsNone(projection.project('[13:00:01] stream=SUMMARY label=Workflow'))


if __name__=='__main__':unittest.main()
