"""Opt-in, allow-listed workflow metadata. Never serialize inputs or exceptions."""
import functools
import os
import re
import time
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

incoming = ContextVar('workflow_summary_incoming', default=None)
current = ContextVar('workflow_summary_current', default=None)
KST = timezone(timedelta(hours=9))
FIELDS = {'count', 'total', 'durationMs', 'attempt', 'schema', 'evidence', 'templates',
          'conditions', 'testCases', 'changes', 'graphStatus', 'persistence', 'outcome', 'errorCode', 'model', 'object', 'result', 'mode', 'steps'}


def enabled():
    return os.getenv('WORKFLOW_SUMMARY_LOG', 'false').lower() == 'true'


def uuid_value(value):
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        return '-'


def trace_id():
    try:
        from opentelemetry import trace
        context = trace.get_current_span().get_span_context()
        if context.is_valid:
            return format(context.trace_id, '032x')
    except ImportError:
        pass
    return (incoming.get() or {}).get('traceId', '-')


def step(name):
    state = current.get()
    if state:
        state['stage'] = name


def emit(event, label, message, **values):
    state = current.get()
    if not state or not state['enabled']:
        return
    # All messages, event names and enum values originate in code, never model/user text.
    state['seq'] += 1
    status = 'START' if event.endswith('_STARTED') else 'FAILED' if event.endswith('_FAILED') else 'COMPLETE'
    short = {'RETRIEVAL': 'RAG', 'LLM': 'Qwen', 'PROVIDER': 'Provider', 'VALIDATION': 'Schema',
             'EVIDENCE': 'Evidence', 'MATCHING': 'Policy', 'GENERATION': 'TC', 'ANALYSIS': 'Analysis',
             'STRUCTURED_OUTPUT': 'Schema'}.get(label, 'Workflow')
    if event.startswith('WORKFLOW_'): short = 'Workflow'
    result = 'RUNNING' if status == 'START' else 'ERROR' if status == 'FAILED' else 'PASS'
    if event == 'LLM_COMPLETED': result = 'RETURNED'
    if event == 'WORKFLOW_INITIALIZED': result = 'READY'
    if event == 'WORKFLOW_COMPLETED' and state['provider'] == 'POLICY_BLOCKED': result = 'HELD'
    fields = dict(stream='SUMMARY', label=short, seq=state['seq'], status=status, result=result,
                  service='ai-service', workflow=state['workflow'], jobId=state['jobId'],
                  runId=state['runId'], requirementId=state['requirementId'], traceId=trace_id(),
                  stage=state['stage'], provider=state['provider'],
                  elapsedMs=round((time.monotonic() - state['start']) * 1000))
    fields.update({key: (value if not isinstance(value, str) or re.fullmatch(r'[A-Za-z0-9_.:-]{1,80}', value) else 'UNKNOWN')
                   for key, value in values.items() if key in FIELDS})
    if event == 'WORKFLOW_INITIALIZED': fields['mode'] = 'FIXED'
    try:
        print(f"[{datetime.now(KST):%H:%M:%S}] [{label}] {message} event={event} "
              + ' '.join(f'{key}={value}' for key, value in fields.items()), flush=True)
    except OSError:
        pass  # Observability must not change a workflow result.


@contextmanager
def phase(event, label, completed=None, **values):
    """Record actual entry, return or failure; preserve exception handling."""
    step(event)
    emit(event + '_STARTED', label, label + ' started',
         **{key: value for key, value in values.items() if key not in {'schema', 'evidence', 'count', 'total', 'result'}})
    try:
        yield values
    except Exception as error:
        emit(event + '_FAILED', label, label + ' failed', errorCode=error_code(error))
        raise
    else:
        emit(completed or event + '_COMPLETED', label, label + ' completed', **values)


def underlying_provider(provider):
    # Adapters explicitly expose their delegate; no RAG/API modules are imported.
    delegate = getattr(type(provider), 'summary_provider', None)
    return delegate(provider) if callable(delegate) else provider


def provider_mode(provider):
    from app.llm_provider import LocalLlmProvider
    provider = underlying_provider(provider)
    return 'REAL_LLM' if isinstance(provider, LocalLlmProvider) else 'FAKE_PROVIDER'


def generate(provider, messages, schema):
    state = current.get()
    if not state:
        return provider.generate(messages, schema)
    state['provider'] = provider_mode(provider)
    state['calls'] += 1
    real = state['provider'] == 'REAL_LLM'
    event, label = ('LLM', 'LLM') if real else ('PROVIDER', 'PROVIDER')
    actual = underlying_provider(provider)
    model = actual.model if real else 'FAKE'
    step(event)
    emit(event + '_STARTED', label, 'Model inference started' if real else 'Fake provider started', attempt=state['calls'], model=model)
    started = time.monotonic()
    try:
        result = provider.generate(messages, schema)
    except Exception as error:
        emit(event + '_FAILED', label, 'Provider failed', attempt=state['calls'],
             errorCode=error_code(error), durationMs=round((time.monotonic() - started) * 1000))
        raise
    emit(event + '_COMPLETED', label, 'Model inference completed' if real else 'Fake provider completed', attempt=state['calls'],
         durationMs=round((time.monotonic() - started) * 1000), model=model)
    return result


def no_llm(mode):
    state = current.get()
    if state:
        state['provider'] = mode


def error_code(error):
    from app.llm_provider import LlmTimeoutError, LlmUnavailableError
    if isinstance(error, (LlmTimeoutError, TimeoutError)):
        return 'LLM_TIMEOUT'
    if isinstance(error, LlmUnavailableError):
        return 'LLM_UNAVAILABLE'
    if type(error).__name__ in {'InvalidAnalysisError', 'InvalidTestCasesError'}:
        return 'INVALID_OUTPUT'
    if type(error).__name__ in {'AnalysisInputError', 'EmbeddingInputTooLongError'}:
        return 'INVALID_INPUT'
    state = current.get()
    return {'RETRIEVAL': 'RAG_RETRIEVAL_ERROR', 'POLICY_MATCHING': 'INVALID_ANALYSIS_SNAPSHOT',
            'STRUCTURED_OUTPUT': 'INVALID_OUTPUT', 'EVIDENCE_VALIDATION': 'INVALID_OUTPUT',
            'OUTPUT_VALIDATION': 'INVALID_OUTPUT'}.get(state['stage'] if state else '', 'WORKFLOW_ERROR')


def workflow(kind, initialized):
    def decorate(function):
        @functools.wraps(function)
        def run(self, request, *args, **kwargs):
            metadata = incoming.get() or {}
            rid = request.get('baselineRequirementId') if isinstance(request, dict) else request.requirementId
            state = dict(enabled=enabled(), workflow=kind, requirementId=uuid_value(rid),
                         jobId=metadata.get('jobId', '-'), runId=metadata.get('runId') or str(uuid4()),
                         start=time.monotonic(), stage='INITIALIZATION', provider='NO_LLM_CALL', calls=0, seq=0)
            token = current.set(state)
            try:
                emit('WORKFLOW_STARTED', kind, 'Workflow started')
                if initialized:
                    emit('WORKFLOW_INITIALIZED', kind, initialized)
                result = function(self, request, *args, **kwargs)
                step('COMPUTATION_COMPLETED')
                emit('WORKFLOW_COMPLETED', 'COMPLETE', 'AI computation completed',
                     persistence='NOT_SAVED', outcome=state['provider'])
                return result
            except Exception as error:
                emit('WORKFLOW_FAILED', 'FAILED', 'Workflow failed', errorCode=error_code(error))
                raise
            finally:
                current.reset(token)
        return run
    return decorate


class SummaryContextMiddleware:
    """Pure ASGI context propagation also works with FastAPI's worker threads."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        headers = {key.decode('latin1').lower(): value.decode('latin1')
                   for key, value in scope.get('headers', [])}
        parent = headers.get('traceparent', '')
        valid = re.fullmatch(r'00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})', parent)
        tid = valid[1] if valid and int(valid[1], 16) and int(valid[2], 16) else '-'
        run_id = uuid_value(headers.get('x-workflow-run-id'))
        token = incoming.set({'jobId': uuid_value(headers.get('x-job-id')),
                              'runId': None if run_id == '-' else run_id, 'traceId': tid})
        try:
            await self.app(scope, receive, send)
        finally:
            incoming.reset(token)
