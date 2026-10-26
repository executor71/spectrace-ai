package com.example.legacyassistant.jobs;
import com.example.legacyassistant.analysis.*;
import com.example.legacyassistant.requirement.*;
import com.example.legacyassistant.observability.Tracing;
import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import java.time.*;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;
class JobWorkerTest {
 JobStore store;AnalysisGate gate;AnalysisGate.Lease lease;AnalysisCapacity capacity;AnalysisClient client;RequirementService requirements;Tracing tracing;JobWorker worker;
 final ObjectMapper json=new ObjectMapper();UUID req,job,token;
 ObjectNode output(){var n=json.createObjectNode().put("requirementId",req.toString());for(String key:List.of("confirmedConditions","ambiguousExpressions","missingConditions","relatedBusinessRules","relatedApis","clarificationQuestions","evidence"))n.putArray(key);n.withArray("missingConditions").add("근거 없음");n.withArray("clarificationQuestions").add("명세 확인");return n;}
 @BeforeEach void setup(){req=UUID.randomUUID();job=UUID.randomUUID();token=UUID.randomUUID();store=mock(JobStore.class);gate=mock(AnalysisGate.class);lease=mock(AnalysisGate.Lease.class);capacity=mock(AnalysisCapacity.class);client=mock(AnalysisClient.class);requirements=mock(RequirementService.class);tracing=new Tracing();worker=new JobWorker(store,gate,capacity,client,new AnalysisValidator(),requirements,tracing,1);
  var row=json.createObjectNode().put("jobId",job.toString()).put("requirementId",req.toString()).put("executionToken",token.toString()).put("createdAt",Instant.now().toString()).put("startedAt",Instant.now().toString()).put("attemptCount",1).put("stage","LLM_ANALYSIS");
  when(gate.tryAcquire()).thenReturn(lease);when(lease.valid()).thenReturn(true);when(capacity.state()).thenReturn(AnalysisCapacity.State.IDLE);when(store.claim(anyString())).thenReturn(Optional.of(row));when(requirements.get(req)).thenReturn(new Requirement(req,"합성","합성", "DRAFT",Instant.now()));when(store.complete(eq(job),eq(token),any())).thenReturn(true);when(client.analyze(any())).thenReturn(output());
 }
 @AfterEach void cleanup(){worker.close();tracing.close();}
 @Test void successValidatesBeforeAtomicSave(){worker.tick();verify(store).stage(job,token,"VALIDATING_OUTPUT");verify(store).stage(job,token,"SAVING_RESULT");verify(store).complete(job,token,output());verify(store,never()).fail(any(),any(),any(),any());}
 @Test void unavailableProviderFailsWithoutOverwriting(){when(capacity.state()).thenReturn(AnalysisCapacity.State.UNAVAILABLE);worker.tick();verify(store).fail(job,token,"FAILED","LLM_UNAVAILABLE");verifyNoInteractions(client);verify(store,never()).complete(any(),any(),any());}
 @Test void invalidOutputDoesNotRetryOrSave(){when(client.analyze(any())).thenReturn(json.createObjectNode());worker.tick();verify(store).fail(job,token,"FAILED","VALIDATION_FAILED");verify(client,times(1)).analyze(any());verify(store,never()).complete(any(),any(),any());}
 @Test void errorCodesAreDistinct(){when(client.analyze(any())).thenThrow(new AnalysisException(503,"RAG_RETRIEVAL_ERROR","safe"));worker.tick();verify(store).fail(job,token,"FAILED","RAG_RETRIEVAL_ERROR");}
 @Test void llmTimeoutDrainsBeforeNextJob(){when(client.analyze(any())).thenThrow(new AnalysisException(504,"LLM_TIMEOUT","timeout"));worker.tick();verify(store).fail(job,token,"TIMED_OUT","LLM_TIMEOUT");doReturn(output()).when(client).analyze(any());worker.tick();verify(store).complete(job,token,output());}
 @Test void elapsedTimeoutDoesNotPretendAnActiveCallWasCancelled()throws Exception{CountDownLatch active=new CountDownLatch(1),release=new CountDownLatch(1);when(client.analyze(any())).thenAnswer(call->{active.countDown();release.await(3,TimeUnit.SECONDS);return output();});var future=CompletableFuture.runAsync(worker::tick);assertTrue(active.await(2,TimeUnit.SECONDS));Thread.sleep(1100);verify(store,never()).fail(any(),any(),any(),any());release.countDown();future.get(5,TimeUnit.SECONDS);verify(store).fail(job,token,"TIMED_OUT","LLM_TIMEOUT");verify(store,never()).complete(any(),any(),any());}
 @Test void busyRemoteAndAnotherWorkerNeverCallModel(){when(capacity.state()).thenReturn(AnalysisCapacity.State.BUSY);worker.tick();verify(store,never()).claim(any());verify(store,never()).recover();verifyNoInteractions(client);when(gate.tryAcquire()).thenReturn(null);worker.tick();verifyNoInteractions(client);}
 @Test void busyRaceHasBoundedRetries(){when(client.analyze(any())).thenThrow(new AnalysisException(429,"ANALYSIS_BUSY","busy"));worker.tick();verify(client,times(3)).analyze(any());verify(store).fail(job,token,"FAILED","ANALYSIS_BUSY");verify(store,never()).complete(any(),any(),any());}
 @Test void staleOwnershipNeverSavesLateOutput(){when(lease.valid()).thenReturn(false);worker.tick();verify(store,never()).complete(any(),any(),any());verify(store).fail(job,token,"FAILED","JOB_WORKER_ERROR");}
}
