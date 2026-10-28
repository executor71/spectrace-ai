package com.example.legacyassistant.observability;

import java.util.UUID;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.boot.test.system.CapturedOutput;
import org.springframework.boot.test.system.OutputCaptureExtension;
import org.springframework.http.HttpHeaders;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import static org.junit.jupiter.api.Assertions.*;

@ExtendWith(OutputCaptureExtension.class)
class WorkflowSummaryTest {
    @Test void scopedCorrelationIsForwardedAndRestored(){
        UUID job=UUID.randomUUID(),requirement=UUID.randomUUID();
        try(var summary=WorkflowSummary.open("ANALYSIS",job,requirement)){
            var headers=new HttpHeaders();WorkflowSummary.headers(headers);
            assertEquals(job.toString(),headers.getFirst("x-job-id"));
            assertNotNull(UUID.fromString(headers.getFirst("x-workflow-run-id")));
            try(var nested=WorkflowSummary.open("TEST_GENERATION",null,requirement)){
                var nestedHeaders=new HttpHeaders();WorkflowSummary.headers(nestedHeaders);
                assertNull(nestedHeaders.getFirst("x-job-id"));
                assertNotEquals(headers.getFirst("x-workflow-run-id"),nestedHeaders.getFirst("x-workflow-run-id"));
            }
            var restored=new HttpHeaders();WorkflowSummary.headers(restored);assertEquals(headers,restored);
        }
        var empty=new HttpHeaders();WorkflowSummary.headers(empty);assertTrue(empty.isEmpty());
    }
    @Test @EnabledIfEnvironmentVariable(named="WORKFLOW_SUMMARY_LOG",matches="true")
    void savingWaitsForCommitAndPreservesCorrelation(CapturedOutput output){
        UUID job=UUID.randomUUID(),req=UUID.randomUUID();
        TransactionSynchronizationManager.initSynchronization();
        try{
            try(var summary=WorkflowSummary.open("ANALYSIS",job,req)){WorkflowSummary.saved();WorkflowSummary.completed();}
            assertFalse(output.getOut().contains("event=RESULT_SAVED"));
            TransactionSynchronizationManager.getSynchronizations().forEach(s->s.afterCommit());
            String text=output.getOut();
            assertTrue(text.contains("event=RESULT_SAVED"));assertTrue(text.contains("jobId="+job));assertTrue(text.contains("requirementId="+req));
            assertTrue(text.indexOf("event=RESULT_SAVED")<text.indexOf("event=WORKFLOW_COMPLETED"));
            assertTrue(text.contains("persistence=COMMITTED"));
        }finally{TransactionSynchronizationManager.clearSynchronization();}
    }
    @Test @EnabledIfEnvironmentVariable(named="WORKFLOW_SUMMARY_LOG",matches="true")
    void rolledBackTransactionNeverClaimsSaved(CapturedOutput output){
        TransactionSynchronizationManager.initSynchronization();
        try{
            try(var summary=WorkflowSummary.open("ANALYSIS",UUID.randomUUID(),UUID.randomUUID())){WorkflowSummary.saved();WorkflowSummary.completed();}
            TransactionSynchronizationManager.getSynchronizations().forEach(s->s.afterCompletion(1));
            assertFalse(output.getOut().contains("event=RESULT_SAVED"));
            assertFalse(output.getOut().contains("event=WORKFLOW_COMPLETED"));
        }finally{TransactionSynchronizationManager.clearSynchronization();}
    }
    @Test @EnabledIfEnvironmentVariable(named="WORKFLOW_SUMMARY_LOG",matches="true")
    void failureContainsOnlySafeCodeAndElapsedTime(CapturedOutput output){
        try(var summary=WorkflowSummary.open("TEST_GENERATION",null,UUID.randomUUID())){
            WorkflowSummary.stage("SAVING_RESULT");WorkflowSummary.failed("secret credential\nInjected");
        }
        assertTrue(output.getOut().contains("errorCode=WORKFLOW_ERROR"));
        assertTrue(output.getOut().contains("stage=SAVING_RESULT"));assertTrue(output.getOut().contains("elapsedMs="));
        assertFalse(output.getOut().contains("secret"));assertFalse(output.getOut().contains("event=RESULT_SAVED"));
    }
}
