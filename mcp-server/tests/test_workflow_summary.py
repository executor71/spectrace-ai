import contextlib
import io
import os
import unittest
from unittest.mock import AsyncMock, patch
from app import server, workflow_summary as summary
from app.tools import Gateway
from app.clients import Services, GatewayError
import httpx

RID='11111111-1111-4111-8111-111111111111'


class McpSummaryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.output=io.StringIO();self.redirect=contextlib.redirect_stdout(self.output);self.redirect.__enter__()
        self.env=patch.dict(os.environ,WORKFLOW_SUMMARY_LOG='true');self.env.start()
        self.services=AsyncMock();self.previous=getattr(server,'gateway',None);server.gateway=Gateway(self.services)

    async def asyncTearDown(self):
        server.gateway=self.previous;self.env.stop();self.redirect.__exit__(None,None,None)

    async def test_actual_handler_boundary_has_start_complete_and_safe_tool_name(self):
        self.services.request.return_value=[]
        result=await server.call_tool('search_knowledge',{'query':'PRIVATE_PROMPT'})
        self.assertFalse(result.isError)
        lines=self.output.getvalue().splitlines();self.assertEqual(2,len(lines))
        self.assertIn('event=TOOL_STARTED',lines[0]);self.assertIn('status=START',lines[0]);self.assertIn('seq=1 ',lines[0])
        self.assertIn('event=TOOL_COMPLETED',lines[1]);self.assertIn('status=COMPLETE',lines[1]);self.assertIn('count=0',lines[1])
        self.assertIn('toolName=search_knowledge',lines[1]);self.assertNotIn('PRIVATE',self.output.getvalue())
        self.assertIsNone(summary.current.get())

    async def test_test_failure_is_not_tool_transport_failure(self):
        self.services.request.return_value={'result':'FAIL','mismatches':[{'secret':'PRIVATE'}]}
        result=await server.call_tool('execute_approved_test',{'testCaseId':RID})
        self.assertFalse(result.isError)
        text=self.output.getvalue();self.assertIn('event=TOOL_COMPLETED',text);self.assertIn('result=FAIL',text)
        self.assertIn('toolStatus=SUCCESS',text);self.assertIn('provider=NO_LLM_CALL',text);self.assertNotIn('PRIVATE',text)

    async def test_invalid_call_is_failed_and_unknown_name_is_not_logged(self):
        result=await server.call_tool('PRIVATE\nFORGED',{})
        self.assertTrue(result.isError)
        self.assertIn('status=FAILED',self.output.getvalue());self.assertIn('UNKNOWN_TOOL',self.output.getvalue())
        self.assertNotIn('PRIVATE',self.output.getvalue());self.services.request.assert_not_called()

    async def test_saved_analysis_has_no_llm_claim(self):
        self.services.request.side_effect=[{'id':RID},{'saved':True}]
        # Gateway branch is checked separately because public output schema requires full AnalysisResult.
        token=summary.begin(RID,'analyze_requirement',{'requirementId':RID})
        try:
            result=await server.gateway.analyze_requirement({'requirementId':RID});summary.finish(result)
        finally: summary.current.reset(token)
        self.assertIn('source=SAVED',self.output.getvalue());self.assertNotIn('REAL_LLM',self.output.getvalue())

    async def test_downstream_error_does_not_leak_exception_or_response(self):
        self.services.request.side_effect=GatewayError('DOWNSTREAM_TIMEOUT','backend')
        result=await server.call_tool('execute_approved_test',{'testCaseId':RID})
        self.assertTrue(result.isError);self.assertIn('errorCode=DOWNSTREAM_TIMEOUT',self.output.getvalue())
        self.assertNotIn('event=TOOL_COMPLETED',self.output.getvalue())

    async def test_run_header_is_sent_only_inside_actual_handler_context(self):
        seen=[]
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:(seen.append(request.headers.get('x-workflow-run-id')) or httpx.Response(200,json={})))) as client:
            services=Services(client)
            await services.request('backend','GET','/api/requirements/'+RID)
            token=summary.begin(RID,'get_test_cases',{'requirementId':RID})
            try: await services.request('backend','GET','/api/requirements/'+RID)
            finally: summary.current.reset(token)
        self.assertEqual([None,RID],seen)

    async def test_summary_toggle_does_not_change_tool_output(self):
        self.services.request.return_value=[]
        with patch.dict(os.environ,WORKFLOW_SUMMARY_LOG='false'):
            result=await server.call_tool('search_knowledge',{'query':'x'})
        self.assertFalse(result.isError);self.assertEqual('',self.output.getvalue())

    async def test_response_serialization_failure_never_claims_tool_completed(self):
        server.gateway=AsyncMock()
        server.gateway.search_knowledge.return_value={'unserializable':object()}
        result=await server.call_tool('search_knowledge',{'query':'x'})
        self.assertTrue(result.isError)
        self.assertIn('event=TOOL_FAILED',self.output.getvalue())
        self.assertNotIn('event=TOOL_COMPLETED',self.output.getvalue())
