package com.example.legacyassistant.observability;

import com.fasterxml.jackson.databind.ObjectMapper;
import io.opentelemetry.api.OpenTelemetry;
import io.opentelemetry.api.common.Attributes;
import io.opentelemetry.api.common.AttributeKey;
import io.opentelemetry.api.trace.*;
import io.opentelemetry.api.trace.propagation.W3CTraceContextPropagator;
import io.opentelemetry.context.Context;
import io.opentelemetry.context.ContextKey;
import io.opentelemetry.sdk.OpenTelemetrySdk;
import io.opentelemetry.sdk.resources.Resource;
import io.opentelemetry.sdk.trace.SdkTracerProvider;
import io.opentelemetry.sdk.trace.export.BatchSpanProcessor;
import io.opentelemetry.exporter.otlp.http.trace.OtlpHttpSpanExporter;
import jakarta.annotation.PreDestroy;
import java.time.Duration;
import java.time.Instant;
import java.util.*;
import org.springframework.stereotype.Component;

@Component
public class Tracing {
    public static final ContextKey<String> REQUEST_ID = ContextKey.named("requestId");
    public static final W3CTraceContextPropagator PROPAGATOR = W3CTraceContextPropagator.getInstance();
    private SdkTracerProvider provider;
    public final Tracer tracer;
    private static final ObjectMapper JSON = new ObjectMapper();
    private static final org.slf4j.Logger LOG = org.slf4j.LoggerFactory.getLogger("workflow");
    public Tracing() {
        if ("true".equalsIgnoreCase(System.getenv("APP_OTEL_ENABLED"))) {
            var exporter = OtlpHttpSpanExporter.builder().setEndpoint(System.getenv().getOrDefault("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT","http://otel-collector:4318/v1/traces")).setTimeout(Duration.ofSeconds(1)).build();
            provider=SdkTracerProvider.builder().setResource(Resource.create(Attributes.of(
                AttributeKey.stringKey("service.name"),"legacy-assistant-backend",
                AttributeKey.stringKey("service.version"),"phase10",
                AttributeKey.stringKey("deployment.environment"),"local")))
                .addSpanProcessor(BatchSpanProcessor.builder(exporter).setMaxQueueSize(2048).setMaxExportBatchSize(128).setScheduleDelay(Duration.ofMillis(500)).build()).build();
            tracer=OpenTelemetrySdk.builder().setTracerProvider(provider).build().getTracer("legacy-workflow");
        } else tracer=OpenTelemetry.noop().getTracer("legacy-workflow");
    }
    public static void error(Span span,String code) {
        String safe=switch(code){
            case "NOT_APPROVED" -> "TEST_NOT_APPROVED";
            case "NOT_EXECUTABLE" -> "TEST_NOT_EXECUTABLE";
            case "FIXTURE_NOT_READY","API_NOT_ALLOWED","DUMMY_TEST_FAIL","LLM_TIMEOUT","LLM_INVALID_OUTPUT" -> code;
            default -> "VALIDATION_FAILED";
        };
        span.setStatus(StatusCode.ERROR);
        span.setAttribute("error.type",safe);span.setAttribute("error.code",safe);span.setAttribute("error.message",safe);
    }
    public static void log(Span span,String event,long start) {
        double ms=(System.nanoTime()-start)/1_000_000.0;
        span.setAttribute("latencyMs",ms);span.setAttribute("durationMs",ms);
        String request=Optional.ofNullable(Context.current().get(REQUEST_ID)).orElse("");
        span.setAttribute("requestId",request);
        try { LOG.info(JSON.writeValueAsString(Map.of("timestamp",Instant.now().toString(),"service","legacy-assistant-backend","level","INFO",
            "traceId",span.getSpanContext().getTraceId(),"spanId",span.getSpanContext().getSpanId(),"requestId",request,"event",event,"durationMs",ms))); }
        catch(Exception ignored) { /* Telemetry must never change the business result. */ }
    }
    @PreDestroy public void close(){if(provider!=null)provider.close();}
}
