"""Summary events exclusively at the actual MCP protocol handler boundary."""
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
import os
import time
from uuid import UUID

current = ContextVar('mcp_summary', default=None)


def safe_uuid(value):
    try: return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError): return '-'


def begin(request_id, tool, arguments):
    args = arguments if isinstance(arguments, dict) else {}
    token = current.set(dict(runId=request_id, toolName=tool, seq=0, start=time.monotonic(),
                             requirementId=safe_uuid(args.get('requirementId')), testCaseId=safe_uuid(args.get('testCaseId'))))
    emit('TOOL_STARTED', 'START', 'RUNNING')
    return token


def emit(event, status, result, **details):
    state = current.get()
    if not state or os.getenv('WORKFLOW_SUMMARY_LOG', 'false').lower() != 'true': return
    try:
        from opentelemetry import trace
        span = trace.get_current_span().get_span_context()
        tid = format(span.trace_id, '032x') if span.is_valid else '-'
    except ImportError: tid = '-'
    state['seq'] += 1
    values = dict(stream='SUMMARY', label='Tool', seq=state['seq'], status=status, result=result,
                  service='mcp-server', workflow='MCP_TOOL', toolName=state['toolName'], runId=state['runId'],
                  jobId='-', traceId=tid,
                  requirementId=state['requirementId'], testCaseId=state['testCaseId'],
                  provider='NO_LLM_CALL', callScope='GATEWAY', elapsedMs=round((time.monotonic()-state['start'])*1000))
    allowed = {'SUCCESS', 'ERROR', 'PASS', 'FAIL', 'SAVED', 'GENERATED', 'UNKNOWN_TOOL', 'INVALID_ARGUMENTS',
               'DOWNSTREAM_TIMEOUT', 'DOWNSTREAM_UNAVAILABLE', 'NOT_APPROVED', 'NOT_EXECUTABLE', 'API_NOT_ALLOWED',
               'FIXTURE_NOT_READY', 'DOWNSTREAM_ERROR', 'NOT_FOUND', 'INTERNAL_ERROR', 'INVALID_DOWNSTREAM_RESPONSE',
               'EVALUATION_NOT_FOUND', 'EVALUATION_NOT_COMPLETED'}
    for key, value in details.items():
        if key in {'errorCode', 'source', 'toolStatus'} and isinstance(value, str) and value in allowed: values[key] = value
        if key == 'count' and isinstance(value, int) and value >= 0: values[key] = value
    stamp = datetime.now(timezone(timedelta(hours=9))).strftime('%H:%M:%S')
    try:
        print(f'[{stamp}] [Tool] {state["toolName"]} event={event} ' + ' '.join(f'{k}={v}' for k,v in values.items()), flush=True)
    except OSError: pass


def finish(result):
    values = result if isinstance(result, dict) else {}
    test_result = values.get('result')
    outcome = test_result if isinstance(test_result, str) and test_result in {'PASS', 'FAIL', 'ERROR'} else 'SUCCESS'
    detail = {'toolStatus': 'SUCCESS'}
    if 'analysisSource' in values: detail['source'] = values['analysisSource']
    for key in ['hits', 'testCases']:
        if isinstance(values.get(key), list): detail['count'] = len(values[key])
    emit('TOOL_COMPLETED', 'COMPLETE', outcome, **detail)


def headers():
    state = current.get()
    return {'x-workflow-run-id': state['runId']} if state else {}
