"""Explicit operational metadata only. No body, exception text or DB instrumentation."""
import contextvars
import functools
import inspect
import json
import logging
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import UUID, uuid4
from opentelemetry import trace
from opentelemetry.context import attach, detach
from opentelemetry.propagators.textmap import DefaultGetter
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

request_id=contextvars.ContextVar('request_id',default='')
operation=contextvars.ContextVar('operation',default='generate')
attempt=contextvars.ContextVar('attempt',default=0)
propagator=TraceContextTextMapPropagator()
service='unconfigured'
configured=False
ALLOWED={
    'nodeCount','edgeCount','hopCount',
    'retrieval.strategy','topK','candidateCount','resultCount','latencyMs','durationMs',
    'embedding.model','inputLength','vectorDimension','model','provider','operation','success','retryCount','timeout',
    'inputTokens','outputTokens','totalTokens','generatedTestCaseCount','executableCandidateCount','evidenceCount',
    'recallAt5','scenarioCoverage','validityRate','evaluatedItemCount','toolName','requestId','resultStatus','downstreamService',
    'apiId','result','mismatchCount','requirementId','testCaseId','error.type','error.code','error.message','http.response.status_code','synthetic'
}
ERRORS={'LLM_TIMEOUT','LLM_INVALID_OUTPUT','RAG_NO_RESULT','VALIDATION_FAILED','MCP_TOOL_REJECTED','TEST_NOT_APPROVED',
    'TEST_NOT_EXECUTABLE','FIXTURE_NOT_READY','API_NOT_ALLOWED','DUMMY_TEST_FAIL','DOWNSTREAM_UNAVAILABLE'}

def setup(name):
    global configured,service
    service=name
    if configured:return
    configured=True
    if os.getenv('APP_OTEL_ENABLED','false').lower()!='true':return
    provider=TracerProvider(resource=Resource.create({'service.name':name,'service.version':'phase10','deployment.environment':'local'}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=os.getenv('OTEL_EXPORTER_OTLP_TRACES_ENDPOINT','http://otel-collector:4318/v1/traces'),timeout=1),
        max_queue_size=2048,max_export_batch_size=128,schedule_delay_millis=500))
    trace.set_tracer_provider(provider)

def attrs(span,values):
    for key,value in values.items():
        if key in {'requirementId','testCaseId','requestId'}:
            try:value=str(UUID(value))
            except (ValueError,TypeError,AttributeError):continue
        if key in ALLOWED and isinstance(value,(str,bool,int,float)):
            span.set_attribute(key,value)

def fail(span,code):
    code={'NOT_APPROVED':'TEST_NOT_APPROVED','NOT_EXECUTABLE':'TEST_NOT_EXECUTABLE'}.get(code,code)
    if code not in ERRORS:code='VALIDATION_FAILED'
    attrs(span,{'error.type':code,'error.code':code,'error.message':code,'success':False})
    span.set_status(trace.Status(trace.StatusCode.ERROR))

def classify(error):
    current=error
    while current:
        if isinstance(current,TimeoutError) or 'Timeout' in type(current).__name__:return 'LLM_TIMEOUT'
        current=getattr(current,'__cause__',None)
    if type(error).__name__ in {'InvalidAnalysisError','InvalidTestCasesError'}:return 'LLM_INVALID_OUTPUT'
    return 'VALIDATION_FAILED'

def correlation():
    current=trace.get_current_span().get_span_context()
    return {'traceId':format(current.trace_id,'032x'),'spanId':format(current.span_id,'016x'),'requestId':request_id.get()}

@contextmanager
def span(name,values=None,context=None,kind=trace.SpanKind.INTERNAL):
    start=time.perf_counter()
    with trace.get_tracer('legacy-workflow').start_as_current_span(name,context=context,kind=kind,record_exception=False,set_status_on_exception=False) as current:
        attrs(current,dict(values or {},requestId=request_id.get()))
        try:
            yield current
        except Exception as error:
            fail(current,classify(error));raise
        finally:
            duration=(time.perf_counter()-start)*1000
            attrs(current,{'latencyMs':duration,'durationMs':duration})
            logging.getLogger('workflow').warning(json.dumps({'timestamp':datetime.now(timezone.utc).isoformat(),'service':service,
                'level':'INFO',**correlation(),'event':name,'durationMs':duration}))

def inject(headers):
    propagator.inject(headers)
    if request_id.get():headers['x-request-id']=request_id.get()

class TraceMiddleware:
    def __init__(self,app):self.app=app
    async def __call__(self,scope,receive,send):
        if scope['type']!='http' or scope.get('path') in {'/health','/metrics'}:
            return await self.app(scope,receive,send)
        headers={k.decode('latin1'):v.decode('latin1') for k,v in scope.get('headers',[])}
        try:rid=str(UUID(headers.get('x-request-id','')))
        except ValueError:rid=str(uuid4())
        token=request_id.set(rid)
        parent=propagator.extract(headers)
        try:
            with span('http.server',context=parent,kind=trace.SpanKind.SERVER) as current:
                async def traced_send(message):
                    if message['type']=='http.response.start':
                        attrs(current,{'http.response.status_code':message['status']})
                        if message['status']>=400:fail(current,'VALIDATION_FAILED')
                        message=dict(message,headers=list(message.get('headers',[]))+[(b'x-trace-id',correlation()['traceId'].encode())])
                    await send(message)
                await self.app(scope,receive,traced_send)
        finally:request_id.reset(token)

def wrap(owner,method,name,before=None,after=None):
    original=getattr(owner,method)
    if getattr(original,'_observed',False):return
    @functools.wraps(original)
    def observed(*args,**kwargs):
        try:values=before(*args,**kwargs) if before else {}
        except Exception:values={}
        with span(name,values) as current:
            op=operation.set(name);retry=attempt.set(0) if name in {'requirement.analysis','testcase.generate'} else None
            try:
                result=original(*args,**kwargs)
                if after:
                    try:after(current,result,*args,**kwargs)
                    except Exception:pass
                return result
            finally:
                operation.reset(op)
                if retry is not None:attempt.reset(retry)
    observed._observed=True
    setattr(owner,method,observed)

def httpx_propagation():
    import httpx
    if getattr(httpx.Client.send,'_observed',False):return
    sync=httpx.Client.send;async_send=httpx.AsyncClient.send
    @functools.wraps(sync)
    def send(self,request,*args,**kwargs):
        inject(request.headers);return sync(self,request,*args,**kwargs)
    @functools.wraps(async_send)
    async def asend(self,request,*args,**kwargs):
        inject(request.headers);return await async_send(self,request,*args,**kwargs)
    send._observed=True;httpx.Client.send=send;httpx.AsyncClient.send=asend

def record_usage(data):
    # No content/thinking fields are read or stored here.
    values={}
    for source,target in [('prompt_eval_count','inputTokens'),('eval_count','outputTokens')]:
        value=data.get(source)
        if isinstance(value,int) and not isinstance(value,bool) and value>=0:values[target]=value
    if len(values)==2:values['totalTokens']=values['inputTokens']+values['outputTokens']
    attrs(trace.get_current_span(),values)

def observed_tool(function):
    @functools.wraps(function)
    async def observed(name,arguments):
        from app.schemas import INPUTS
        safe=name if name in INPUTS else 'UNKNOWN_TOOL'
        graph_tool=name in {'find_requirement_context','find_impacted_tests','trace_test_case_origin'}
        with span('mcp.'+safe if graph_tool else 'mcp.tool',{'toolName':safe}) as current:
            result=await function(name,arguments)
            attrs(current,{'resultStatus':'ERROR' if result.isError else 'SUCCESS',
                'downstreamService':'graph' if graph_tool else 'ai/retrieval' if name=='search_knowledge' else 'evaluation' if name=='get_evaluation_result' else 'backend'})
            if result.isError:
                code=(result.structuredContent or {}).get('errorCode')
                fail(current,code if code in {'NOT_APPROVED','NOT_EXECUTABLE','FIXTURE_NOT_READY','API_NOT_ALLOWED'} else 'MCP_TOOL_REJECTED')
            return result
    return observed
