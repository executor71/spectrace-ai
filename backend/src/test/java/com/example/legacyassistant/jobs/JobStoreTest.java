package com.example.legacyassistant.jobs;
import com.example.legacyassistant.analysis.AnalysisException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
@SpringBootTest(properties="analysis.jobs.enabled=false") @AutoConfigureMockMvc @Transactional
class JobStoreTest {
 @Autowired JobStore store;@Autowired JdbcTemplate jdbc;@Autowired MockMvc mvc;@Autowired ObjectMapper json;@Autowired AnalysisGate gate;
 UUID req(){UUID id=UUID.randomUUID();jdbc.update("INSERT INTO app.requirement(id,title,description) VALUES (?,'Job test','합성 요청')",id);return id;}
 UUID id(com.fasterxml.jackson.databind.JsonNode n){return UUID.fromString(n.path("jobId").asText());}
 @Test void create202ImmediateAndDurableQueued()throws Exception{UUID req=req();long start=System.nanoTime();var response=mvc.perform(post("/api/requirements/"+req+"/analysis-jobs")).andExpect(status().isAccepted()).andExpect(header().exists("Location")).andExpect(jsonPath("$.status").value("QUEUED")).andReturn().getResponse();assertTrue((System.nanoTime()-start)/1e6<1000);UUID job=id(json.readTree(response.getContentAsString()));assertEquals("QUEUED",store.get(job).path("status").asText());assertEquals(1,store.get(job).path("queuePosition").asInt());}
 @Test void duplicateReturnsActiveIdentityAndTerminalAllowsExplicitNewJob(){UUID req=req();var first=store.create(req);assertEquals(first.path("jobId"),store.create(req).path("jobId"));store.cancel(id(first));assertNotEquals(first.path("jobId"),store.create(req).path("jobId"));}
 @Test void differentRequirementsQueueAndCapacityIsExplicit(){for(int i=0;i<5;i++)assertEquals("QUEUED",store.create(req()).path("status").asText());var e=assertThrows(AnalysisException.class,()->store.create(req()));assertEquals("JOB_QUEUE_FULL",e.code());}
 @Test void claimCancellationAndTerminalTransitions(){UUID first=id(store.create(req()));var claimed=store.claim("worker-a").orElseThrow();assertEquals("RUNNING",claimed.path("status").asText());assertTrue(store.claim("worker-b").isEmpty());assertThrows(AnalysisException.class,()->store.cancel(first));assertTrue(store.fail(first,UUID.fromString(claimed.path("executionToken").asText()),"FAILED","LLM_UNAVAILABLE"));assertFalse(store.fail(first,UUID.randomUUID(),"FAILED","JOB_WORKER_ERROR"));assertEquals("FAILED",store.get(first).path("status").asText());}
 @Test void expiredOwnerIsFencedAndQueuedSurvivesRecovery(){UUID job=id(store.create(req()));var claim=store.claim("dead").orElseThrow();UUID token=UUID.fromString(claim.path("executionToken").asText());UUID queued=id(store.create(req()));jdbc.update("UPDATE app.analysis_job SET lease_expires_at=clock_timestamp()-interval '1 second' WHERE job_id=?",job);assertEquals(1,store.recover());assertFalse(store.complete(job,token,json.createObjectNode()));assertEquals("QUEUED",store.get(queued).path("status").asText());assertEquals("FAILED",store.get(job).path("status").asText());}
 @Test void globalExecutionLockExcludesOtherConnections(){try(var a=gate.tryAcquire()){assertNotNull(a);assertNull(gate.tryAcquire());assertTrue(a.valid());}try(var b=gate.tryAcquire()){assertNotNull(b);}}
 @Test void resultAndJobCommitTogetherAndLateCompletionCannotOverwrite(){UUID req=req();UUID job=id(store.create(req));var claim=store.claim("worker").orElseThrow();UUID token=UUID.fromString(claim.path("executionToken").asText());var value=json.createObjectNode().put("requirementId",req.toString());for(String key:List.of("confirmedConditions","ambiguousExpressions","missingConditions","relatedBusinessRules","relatedApis","clarificationQuestions","evidence"))value.putArray(key);assertTrue(store.complete(job,token,value));assertEquals("SUCCEEDED",store.get(job).path("status").asText());assertTrue(store.get(job).path("resultAvailable").asBoolean());assertFalse(store.complete(job,token,json.createObjectNode().put("tampered",true)));assertTrue(jdbc.queryForObject("SELECT result_json::text FROM app.requirement_analysis WHERE requirement_id=?",String.class,req).contains("requirementId"));}
 @Test void noPrivilegeExpansion(){assertEquals("app_user",jdbc.queryForObject("SELECT current_user",String.class));for(String schema:List.of("rag","evaluation"))assertFalse(jdbc.queryForObject("SELECT has_schema_privilege(current_user,?,'USAGE')",Boolean.class,schema));}
}
