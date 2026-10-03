package com.example.legacyassistant.observability;

import io.opentelemetry.api.trace.*;
import io.opentelemetry.context.*;
import io.opentelemetry.context.propagation.TextMapGetter;
import jakarta.servlet.*;
import jakarta.servlet.http.*;
import java.io.IOException;
import java.util.*;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

@Component
public class TraceFilter extends OncePerRequestFilter {
    private final Tracing tracing;
    public TraceFilter(Tracing tracing){this.tracing=tracing;}
    private static final TextMapGetter<HttpServletRequest> GETTER=new TextMapGetter<>() {
        public Iterable<String> keys(HttpServletRequest request){return List.of("traceparent","tracestate");}
        public String get(HttpServletRequest request,String key){return request.getHeader(key);}
    };
    @Override protected boolean shouldNotFilter(HttpServletRequest request){return !request.getRequestURI().startsWith("/api/");}
    @Override protected void doFilterInternal(HttpServletRequest request,HttpServletResponse response,FilterChain chain) throws ServletException,IOException {
        Context parent=Tracing.PROPAGATOR.extract(Context.root(),request,GETTER);
        String rid=request.getHeader("x-request-id");
        if(rid==null || !rid.matches("[0-9a-fA-F-]{36}"))rid=UUID.randomUUID().toString();
        Span span=tracing.tracer.spanBuilder("backend.request").setParent(parent).setSpanKind(SpanKind.SERVER).startSpan();
        long start=System.nanoTime();
        response.setHeader("X-Trace-Id",span.getSpanContext().getTraceId());
        try(Scope scope=parent.with(Tracing.REQUEST_ID,rid).with(span).makeCurrent()) {
            try {chain.doFilter(request,response);if(response.getStatus()>=400)Tracing.error(span,"VALIDATION_FAILED");}
            catch(IOException|ServletException|RuntimeException e){Tracing.error(span,"VALIDATION_FAILED");throw e;}
            finally {span.setAttribute("http.response.status_code",response.getStatus());Tracing.log(span,"backend.request",start);}
        } finally {span.end();}
    }
}
