package com.example.legacyassistant.observability;

import com.example.legacyassistant.testcase.TestCaseException;
import com.fasterxml.jackson.databind.JsonNode;
import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.*;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.http.ResponseEntity;
import java.util.UUID;

/** Observe real review, local Dummy dispatch and assertions; never call them MCP. */
@Aspect @Component @Order(-10)
public class ExecutionSummaryAspect {
    @Around("execution(public * com.example.legacyassistant.testcase.TestCaseReviewService.decide(..)) || execution(public * com.example.legacyassistant.testcase.TestCaseReviewService.edit(..)) || execution(public * com.example.legacyassistant.testcase.ExecutionService.execute*(..))")
    public Object action(ProceedingJoinPoint point) throws Throwable {
        // Self-invocation execute -> executeRevision is not a second intercepted action.
        boolean execution=point.getSignature().getName().startsWith("execute");
        String prefix=execution?"EXECUTION":"HITL";
        try(var summary=WorkflowSummary.open(execution?"DUMMY_EXECUTION":"HITL_REVIEW",null,null)){
            summary.testCase((UUID)point.getArgs()[0]);
            String operation=execution?"EXECUTE":point.getSignature().getName().equals("decide")?((boolean)point.getArgs()[2]?"APPROVE":"REJECT"):"EDIT";
            summary.event(prefix+"_STARTED","RUNNING","operation="+operation+(execution?" origin=EXECUTION_API":" origin=REVIEW_API"));
            try{
                Object output=point.proceed();
                JsonNode result=(JsonNode)output;
                String outcome=execution?result.path("result").asText():result.path("approvalStatus").asText();
                String details=execution?"mismatches="+result.path("mismatches").size()+" synthetic="+result.path("syntheticDefect").asBoolean():"revision="+result.path("reviewRevision").asLong()+" operation="+operation+" origin=REVIEW_API";
                // Order makes this aspect enclose Spring's transaction interceptor;
                // the return is committed, or an outer transaction defers these events.
                summary.afterCommit("RESULT_SAVED","COMMITTED","persistence=COMMITTED");
                summary.afterCommit(prefix+"_COMPLETED",outcome,details+" persistence=COMMITTED");
                return output;
            }catch(Throwable error){
                String code=error instanceof TestCaseException e?e.code():"EXECUTION_ERROR";
                summary.event(prefix+"_FAILED","ERROR","errorCode="+safeCode(code));throw error;
            }
        }
    }

    @Around("execution(public * com.example.legacyassistant.testcase.DummyApiRegistry.invoke(..))")
    public Object dummy(ProceedingJoinPoint point) throws Throwable {
        var summary=WorkflowSummary.current();if(summary==null)return point.proceed();
        // Registry entries are a fixed server allowlist. Do not log request payloads.
        var api=(com.example.legacyassistant.testcase.DummyApiRegistry.Entry)point.getArgs()[0];
        summary.event("DUMMY_STARTED","RUNNING","api="+api.apiId()+" dispatch=IN_PROCESS");
        try{
            Object output=point.proceed();
            summary.event("DUMMY_COMPLETED","RETURNED","api="+api.apiId()+" dispatch=IN_PROCESS httpStatus="+((ResponseEntity<?>)output).getStatusCode().value());
            return output;
        }catch(Throwable error){summary.event("DUMMY_FAILED","ERROR","errorCode=DUMMY_EXECUTION_ERROR");throw error;}
    }

    @Around("execution(public * com.example.legacyassistant.testcase.ExecutionComparator.compare(..))")
    public Object assertions(ProceedingJoinPoint point) throws Throwable {
        var summary=WorkflowSummary.current();if(summary==null)return point.proceed();
        summary.event("ASSERTION_STARTED","RUNNING","");
        try{
            Object output=point.proceed();int count=((JsonNode)output).size();
            summary.event(count==0?"ASSERTION_COMPLETED":"ASSERTION_FAILED",count==0?"PASS":"FAIL","mismatches="+count);
            return output;
        }catch(Throwable error){summary.event("ASSERTION_FAILED","ERROR","errorCode=ASSERTION_ERROR");throw error;}
    }
    private static String safeCode(String value){return value!=null&&value.matches("[A-Z_0-9]{1,64}")?value:"EXECUTION_ERROR";}
}
