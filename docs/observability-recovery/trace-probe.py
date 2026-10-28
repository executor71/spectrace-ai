"""One real SDK span using the application's actual OTLP HTTP destination."""
import json
import os
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

endpoint=os.getenv('OTEL_EXPORTER_OTLP_TRACES_ENDPOINT','http://otel-collector:4318/v1/traces')
provider=TracerProvider(resource=Resource.create({'service.name':'spectrace-recovery-probe'}))
provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter(endpoint=endpoint,timeout=2)))
with provider.get_tracer('spectrace.recovery').start_as_current_span('recovery.minimum') as span:
    span.set_attribute('synthetic',True)
    span.set_attribute('recovery.purpose','collector-to-jaeger-storage')
    trace_id=format(span.get_span_context().trace_id,'032x')
    sampled=bool(span.get_span_context().trace_flags.sampled)
provider.force_flush(timeout_millis=5000)
provider.shutdown()
print(json.dumps({'traceId':trace_id,'serviceName':'spectrace-recovery-probe','spanName':'recovery.minimum',
                  'endpoint':endpoint,'sampled':sampled}))
