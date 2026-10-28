package com.example.legacyassistant.observability;

import com.example.legacyassistant.testcase.TestCaseException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.Signature;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.boot.test.system.*;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import java.util.UUID;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

@ExtendWith(OutputCaptureExtension.class)
@EnabledIfEnvironmentVariable(named="WORKFLOW_SUMMARY_LOG",matches="true")
class ExecutionSummaryAspectTest {
    final ObjectMapper json=new ObjectMapper();
    final ExecutionSummaryAspect aspect=new ExecutionSummaryAspect();
    ProceedingJoinPoint action(String name) {
        var point=mock(ProceedingJoinPoint.class);var signature=mock(Signature.class);
        when(point.getSignature()).thenReturn(signature);when(signature.getName()).thenReturn(name);
        when(point.getArgs()).thenReturn(new Object[]{UUID.randomUUID(),json.createObjectNode(),true});return point;
    }
    @Test void assertionMismatchKeepsFailWhileExecutionCompletes(CapturedOutput output) throws Throwable {
        var point=action("executeRevision");var report=json.createObjectNode().put("result","FAIL").put("syntheticDefect",true);
        report.putArray("mismatches").addObject();when(point.proceed()).thenReturn(report);
        assertSame(report,aspect.action(point));String text=output.getOut();
        assertTrue(text.contains("event=EXECUTION_STARTED"));assertTrue(text.contains("event=EXECUTION_COMPLETED"));
        assertTrue(text.contains("origin=EXECUTION_API"));
        assertTrue(text.contains("result=FAIL"));assertTrue(text.contains("synthetic=true"));assertTrue(text.contains("status=COMPLETE"));
        assertTrue(text.indexOf("event=RESULT_SAVED")<text.indexOf("event=EXECUTION_COMPLETED"));
    }
    @Test void reviewRollbackCannotClaimHumanApprovalCommitted(CapturedOutput output) throws Throwable {
        var point=action("decide");when(point.proceed()).thenReturn(json.createObjectNode().put("approvalStatus","APPROVED").put("reviewRevision",1));
        TransactionSynchronizationManager.initSynchronization();
        try{
            aspect.action(point);assertTrue(output.getOut().contains("event=HITL_STARTED"));
            assertFalse(output.getOut().contains("event=HITL_COMPLETED"));
            TransactionSynchronizationManager.getSynchronizations().forEach(s->s.afterCompletion(1));
            assertFalse(output.getOut().contains("event=RESULT_SAVED"));
        }finally{TransactionSynchronizationManager.clearSynchronization();}
    }
    @Test void blockedExecutionHasNoDummyInvocationOrSavedClaim(CapturedOutput output) throws Throwable {
        var point=action("execute");when(point.proceed()).thenThrow(new TestCaseException(409,"NOT_APPROVED","PRIVATE_INPUT"));
        assertThrows(TestCaseException.class,()->aspect.action(point));String text=output.getOut();
        assertTrue(text.contains("event=EXECUTION_FAILED"));assertTrue(text.contains("errorCode=NOT_APPROVED"));
        assertFalse(text.contains("DUMMY_STARTED"));assertFalse(text.contains("RESULT_SAVED"));assertFalse(text.contains("PRIVATE_INPUT"));
    }
    @Test void assertionsUseActualMismatchCount(CapturedOutput output) throws Throwable {
        var point=mock(ProceedingJoinPoint.class);
        // A single mismatch array is returned unchanged by the logger.
        var actual=json.createArrayNode();actual.addObject().put("payload","PRIVATE");when(point.proceed()).thenReturn(actual);
        try(var summary=WorkflowSummary.open("DUMMY_EXECUTION",null,null)){
            assertSame(actual,aspect.assertions(point));
        }
        assertTrue(output.getOut().contains("event=ASSERTION_FAILED"));assertTrue(output.getOut().contains("mismatches=1"));
        assertFalse(output.getOut().contains("PRIVATE"));
    }
}
