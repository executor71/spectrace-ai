package com.example.legacyassistant.observability;

import io.opentelemetry.api.trace.Span;
import io.opentelemetry.context.Context;
import io.opentelemetry.context.ContextKey;
import io.opentelemetry.context.Scope;
import java.time.*;
import java.time.format.DateTimeFormatter;
import java.util.UUID;

/** Fixed operational metadata only. Never accepts prompts, responses or exception text. */
public final class WorkflowSummary implements AutoCloseable {
    public static final ContextKey<WorkflowSummary> KEY=ContextKey.named("workflow-summary");
    public static final ContextKey<String> RUN_ID=ContextKey.named("workflow-summary-run-id");
    private final String workflow,jobId,requirementId,runId;
    private final long start=System.nanoTime();
    private final Scope scope;
    private String stage="AI_REQUEST";
    private long seq;
    private String testCaseId="-";
    private WorkflowSummary(String workflow,UUID jobId,UUID requirementId){
        this.workflow=workflow;this.jobId=jobId==null?"-":jobId.toString();this.requirementId=requirementId==null?"-":requirementId.toString();
        String inherited=Context.current().get(RUN_ID);
        this.runId=inherited==null?UUID.randomUUID().toString():inherited;this.scope=Context.current().with(KEY,this).makeCurrent();
    }
    public static WorkflowSummary open(String workflow,UUID jobId,UUID requirementId){return new WorkflowSummary(workflow,jobId,requirementId);}
    public static void headers(org.springframework.http.HttpHeaders headers){
        var value=Context.current().get(KEY);if(value==null)return;
        headers.set("x-workflow-run-id",value.runId);
        if(!value.jobId.equals("-"))headers.set("x-job-id",value.jobId);
    }
    public static void stage(String stage){var value=Context.current().get(KEY);if(value!=null)value.stage=stage;}
    private void emit(String event,String message,String details){
        if(!"true".equalsIgnoreCase(System.getenv("WORKFLOW_SUMMARY_LOG")))return;
        var trace=Span.current().getSpanContext();
        String time=OffsetDateTime.now(ZoneOffset.ofHours(9)).format(DateTimeFormatter.ofPattern("HH:mm:ss"));
        String status=event.endsWith("_STARTED")?"START":event.endsWith("_FAILED")?"FAILED":"COMPLETE";
        String label=event.startsWith("HITL_")?"HITL":event.startsWith("DUMMY_")?"Dummy":event.startsWith("ASSERTION_")?"Assert":event.equals("RESULT_SAVED")?"Save":event.startsWith("EXECUTION_")?"Execute":"Workflow";
        System.out.printf("[%s] [%s] %s event=%s stream=SUMMARY label=%s seq=%d status=%s service=backend workflow=%s jobId=%s runId=%s requirementId=%s testCaseId=%s traceId=%s stage=%s elapsedMs=%d %s%n",
            time,label,message,event,label,++seq,status,workflow,jobId,runId,requirementId,testCaseId,trace.isValid()?trace.getTraceId():"-",stage,(System.nanoTime()-start)/1_000_000,details);
        System.out.flush();
    }
    public static void saved(){
        var value=Context.current().get(KEY);if(value==null)return;
        committed(()->{value.stage="SAVING_RESULT";value.emit("RESULT_SAVED","Result saved","result=COMMITTED provider=NO_LLM_CALL persistence=COMMITTED");});
    }
    public static void completed(){
        var value=Context.current().get(KEY);if(value==null)return;
        committed(()->{value.stage="COMPLETED";value.emit("WORKFLOW_COMPLETED","Workflow completed","result=COMMITTED provider=NO_LLM_CALL persistence=COMMITTED");});
    }
    static void committed(Runnable event){
        if(org.springframework.transaction.support.TransactionSynchronizationManager.isSynchronizationActive()){
            var context=Context.current();
            org.springframework.transaction.support.TransactionSynchronizationManager.registerSynchronization(new org.springframework.transaction.support.TransactionSynchronization(){
                @Override public void afterCommit(){try(var scope=context.makeCurrent()){event.run();}}
            });
        }else event.run();
    }
    public static void failed(String code){
        var value=Context.current().get(KEY);if(value==null)return;
        String safe=code!=null&&code.matches("[A-Z_0-9]{1,64}")?code:"WORKFLOW_ERROR";
        value.emit("WORKFLOW_FAILED","Workflow failed","result=ERROR provider=NO_LLM_CALL errorCode="+safe);
    }
    public static WorkflowSummary current(){return Context.current().get(KEY);}
    public void testCase(UUID id){this.testCaseId=id.toString();}
    public void event(String event,String result,String details){
        this.stage=event;
        emit(event,"Execution evidence","result="+safe(result)+" provider=NO_LLM_CALL "+details);
    }
    public void afterCommit(String event,String result,String details){committed(()->event(event,result,details));}
    private static String safe(String value){return value!=null&&value.matches("[A-Z_0-9]{1,64}")?value:"UNKNOWN";}
    @Override public void close(){scope.close();}
}
