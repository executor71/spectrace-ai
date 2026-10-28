package com.example.legacyassistant.observability;

import com.fasterxml.jackson.databind.JsonNode;
import io.opentelemetry.api.trace.Span;
import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.*;
import org.springframework.stereotype.Component;
import java.util.UUID;
import com.example.legacyassistant.testcase.TestCaseException;
import com.example.legacyassistant.analysis.AnalysisException;

@Aspect @Component
public class WorkflowAspect {
    private final Tracing tracing;
    public WorkflowAspect(Tracing tracing){this.tracing=tracing;}
    @Around("execution(public * com.example.legacyassistant.requirement.RequirementService.*(..)) || execution(public * com.example.legacyassistant.analysis.AnalysisService.*(..)) || execution(public * com.example.legacyassistant.testcase.TestCaseService.*(..)) || execution(public * com.example.legacyassistant.testcase.TestCaseReviewService.*(..)) || execution(public * com.example.legacyassistant.testcase.ExecutionService.*(..))")
    public Object observe(ProceedingJoinPoint point) throws Throwable {
        String type=point.getTarget().getClass().getSimpleName(),method=point.getSignature().getName();
        String name=switch(type) {
            case "RequirementService" -> "backend.requirement";
            case "AnalysisService" -> method.equals("create")?"requirement.analysis":"requirement.analysis.read";
            case "TestCaseService" -> method.equals("generate")?"testcase.generate":"testcase.read";
            case "TestCaseReviewService" -> "review";
            default -> method.startsWith("execute")?"dummy.execution":"dummy.execution.read";
        };
        Span span=tracing.tracer.spanBuilder(name).startSpan();long start=System.nanoTime();
        span.setAttribute("operation",method);
        for(Object arg:point.getArgs())if(arg instanceof UUID id)span.setAttribute(type.equals("RequirementService")||type.equals("AnalysisService")||type.equals("TestCaseService")?"requirementId":"testCaseId",id.toString());
        try(var scope=span.makeCurrent()) {
            try {
                Object result=point.proceed();
                if(name.equals("dummy.execution") && result instanceof JsonNode node) {
                    String api=node.path("apiId").asText();
                    if(java.util.Set.of("API-ASSET-001","API-LOAN-APPROVE","API-RETURN-CREATE","API-RETURN-INSPECT").contains(api))span.setAttribute("apiId",api);
                    span.setAttribute("executionId",node.path("executionId").asText()).setAttribute("allowListValidated",node.path("eligibility").path("apiAllowed").asBoolean());
                    span.setAttribute("fixtureReady",node.path("eligibility").path("fixtureReady").asBoolean());
                    span.setAttribute("result",node.path("result").asText());span.setAttribute("mismatchCount",node.path("mismatches").size());
                    if(node.path("result").asText().equals("FAIL"))Tracing.error(span,"DUMMY_TEST_FAIL");
                    if(node.path("result").asText().equals("ERROR"))Tracing.error(span,"DUMMY_EXECUTION_ERROR");
                }
                return result;
            } catch(Throwable error) {
                String code=error instanceof TestCaseException e?e.code():error instanceof AnalysisException e?e.code():"VALIDATION_FAILED";
                Tracing.error(span,code);throw error;
            } finally {Tracing.log(span,name,start);}
        } finally {span.end();}
    }
}
