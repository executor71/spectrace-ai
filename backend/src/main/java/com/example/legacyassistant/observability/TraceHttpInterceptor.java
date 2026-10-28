package com.example.legacyassistant.observability;
import io.opentelemetry.context.Context;
import java.io.IOException;
import org.springframework.http.HttpRequest;
import org.springframework.http.client.*;
public class TraceHttpInterceptor implements ClientHttpRequestInterceptor {
    @Override public ClientHttpResponse intercept(HttpRequest request,byte[] body,ClientHttpRequestExecution execution) throws IOException {
        WorkflowSummary.headers(request.getHeaders());
        Tracing.PROPAGATOR.inject(Context.current(),request.getHeaders(),(headers,key,value)->headers.set(key,value));
        String id=Context.current().get(Tracing.REQUEST_ID);if(id!=null)request.getHeaders().set("x-request-id",id);
        return execution.execute(request,body);
    }
}
