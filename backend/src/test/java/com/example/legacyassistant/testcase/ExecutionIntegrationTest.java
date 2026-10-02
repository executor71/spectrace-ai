package com.example.legacyassistant.testcase;

import com.example.legacyassistant.analysis.AnalysisRepository;
import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import java.util.*;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.bean.override.mockito.*;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest @AutoConfigureMockMvc @Transactional
class ExecutionIntegrationTest {
    @Autowired MockMvc mvc;@Autowired ObjectMapper json;@Autowired JdbcTemplate jdbc;
    @Autowired AnalysisRepository analyses;@Autowired TestCasePolicy policy;@Autowired TestCaseRepository repository;
    @MockitoBean TestCaseClient client;@MockitoSpyBean DummyApiRegistry registry;
    TestCaseReviewIntegrationTest helper;
    @BeforeEach void setup(){helper=new TestCaseReviewIntegrationTest();helper.mvc=mvc;helper.json=json;helper.jdbc=jdbc;helper.analyses=analyses;helper.policy=policy;helper.repository=repository;helper.client=client;}
    ObjectNode draft() throws Exception{return helper.generate();}
    ObjectNode approve(ObjectNode tc) throws Exception{return helper.decision(tc,"approve");}
    String route(JsonNode tc){return helper.tc(tc)+"/executions";}
    JsonNode execute(JsonNode tc) throws Exception{return json.readTree(mvc.perform(post(route(tc))).andExpect(status().isCreated()).andReturn().getResponse().getContentAsString());}
    ObjectNode edit(ObjectNode tc,String field,JsonNode value) throws Exception {
        var body=json.createObjectNode().put("reviewRevision",tc.path("reviewRevision").asLong());body.set(field,value);
        return (ObjectNode)json.readTree(mvc.perform(patch(helper.tc(tc)).contentType("application/json").content(body.toString())).andExpect(status().isOk()).andReturn().getResponse().getContentAsString());
    }
    void blocked(ObjectNode tc,String reason) throws Exception {
        mvc.perform(post(route(tc))).andExpect(status().isConflict()).andExpect(jsonPath("$.code").value(reason));
        verify(registry,never()).invoke(any(),any(),any());
        assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM app.test_execution WHERE test_case_id=?",Integer.class,UUID.fromString(tc.path("testCaseId").asText())));
    }
    @Test void draftExecutableDenied() throws Exception {var tc=draft();mvc.perform(get(helper.tc(tc)+"/execution-eligibility")).andExpect(jsonPath("$.executable").value(true));blocked(tc,"NOT_APPROVED");}
    @Test void rejectedExecutableDenied() throws Exception {blocked(helper.decision(draft(),"reject"),"NOT_APPROVED");}
    @Test void approvedNotExecutableDenied() throws Exception {var tc=draft();var expected=tc.path("expectedResult").deepCopy();((ObjectNode)expected).putArray("assertions");blocked(approve(edit(tc,"expectedResult",expected)),"NOT_EXECUTABLE");}
    @Test void fixtureMissingDenied() throws Exception {var tc=draft();blocked(approve(edit(tc,"preconditions",json.createArrayNode().add("unreproducible condition"))),"FIXTURE_NOT_READY");}
    @Test void unknownApiDenied() throws Exception {var tc=draft();var input=(ObjectNode)tc.path("input").deepCopy();input.put("apiId","API-NOT-ALLOWED");blocked(approve(edit(tc,"input",input)),"API_NOT_ALLOWED");}
    @Test void externalUrlsAndTamperedEndpointsDenied() throws Exception {
        var tc=draft();for(String endpoint:List.of("https://example.com", "http://127.0.0.1:8080/admin/reset","//example.com","/admin/reset","/loans/{loanId}/approve?url=http://example.com","/loans/../admin/reset","DELETE /")){
            var input=(ObjectNode)tc.path("input").deepCopy();input.put("endpoint",endpoint);tc=approve(edit(tc,"input",input));blocked(tc,"API_NOT_ALLOWED");
        }
    }
    @Test void traversalInParametersDenied() throws Exception {var tc=draft();var input=(ObjectNode)tc.path("input").deepCopy();input.withObject("/pathParameters").put("loanId","../../admin/reset");blocked(approve(edit(tc,"input",input)),"NOT_EXECUTABLE");}
    @Test void unknownRequestFieldsDenied() throws Exception {var tc=draft();var input=(ObjectNode)tc.path("input").deepCopy();input.put("url","https://example.com");blocked(approve(edit(tc,"input",input)),"NOT_EXECUTABLE");}
    @Test void postCannotOverrideSavedTestCase() throws Exception {var tc=approve(draft());mvc.perform(post(route(tc)).contentType("application/json").content("{\"fixtureReady\":true,\"endpoint\":\"/admin/reset\"}")).andExpect(status().isBadRequest());verify(registry,never()).invoke(any(),any(),any());}
    @Test void normalPassAndHistorySurviveReload() throws Exception {
        var tc=approve(draft());var run=execute(tc);assertEquals("PASS",run.path("result").asText());assertTrue(run.path("mismatches").isEmpty());assertEquals("APPROVED",run.at("/actual/state/loanStatus").asText());
        var saved=json.readTree(mvc.perform(get("/api/executions/"+run.path("executionId").asText())).andExpect(status().isOk()).andReturn().getResponse().getContentAsString());assertEquals(run,saved);
        var history=json.readTree(mvc.perform(get(route(tc))).andExpect(status().isOk()).andReturn().getResponse().getContentAsString());assertEquals(run,history.get(0));
    }
    ObjectNode self(boolean defect) throws Exception {
        var tc=draft();var input=(ObjectNode)tc.path("input").deepCopy();input.put("actorFixture","requester");if(defect)input.put("fixtureProfile","synthetic-self-approval-bug");tc=edit(tc,"input",input);
        var pre=(ArrayNode)tc.path("preconditions").deepCopy();pre.set(0,json.getNodeFactory().textNode("합성 계정과 부서 관계를 시험 환경에 준비한다: requester"));tc=edit(tc,"preconditions",pre);
        var expected=json.createObjectNode().put("description","Self approval forbidden");var assertions=expected.putArray("assertions");assertions.addObject().put("kind","HTTP_STATUS").put("value",403);
        assertions.addObject().put("kind","RESPONSE_TOKEN").put("value","SELF_APPROVAL_FORBIDDEN");assertions.addObject().put("kind","UNCHANGED").put("field","loanStatus");assertions.addObject().put("kind","UNCHANGED").put("field","assetStatus");
        return approve(edit(tc,"expectedResult",expected));
    }
    @Test void selfApprovalPass() throws Exception {var run=execute(self(false));assertEquals("PASS",run.path("result").asText());assertEquals("SELF_APPROVAL_FORBIDDEN",run.at("/actual/errorCode").asText());}
    @Test void intentionalDefectIsFailAndPersistsAllMismatches() throws Exception {
        var tc=self(true);var run=execute(tc);assertEquals("FAIL",run.path("result").asText());assertTrue(run.path("syntheticDefect").asBoolean());assertEquals(4,run.path("mismatches").size());
        assertEquals(403,run.at("/expected/httpStatus").asInt());assertEquals(200,run.at("/actual/httpStatus").asInt());
        var saved=json.readTree(mvc.perform(get("/api/executions/"+run.path("executionId").asText())).andReturn().getResponse().getContentAsString());assertEquals(run,saved);
    }
    @Test void missingCaseAndExecution404() throws Exception {String id=UUID.randomUUID().toString();mvc.perform(post("/api/test-cases/"+id+"/executions")).andExpect(status().isNotFound());mvc.perform(get("/api/test-cases/"+id+"/executions")).andExpect(status().isNotFound());mvc.perform(get("/api/executions/"+id)).andExpect(status().isNotFound());}
    @Test void repeatedFixtureIsReproducible() throws Exception {var tc=approve(draft());var first=execute(tc);var second=execute(tc);for(String key:List.of("actual","expected","fixtureBefore","result","mismatches"))assertEquals(first.get(key),second.get(key));assertNotEquals(first.get("executionId"),second.get("executionId"));}
    @Test void reviewAndEvidenceAreUntouched() throws Exception {var tc=approve(draft());execute(tc);var batch=json.readTree(mvc.perform(get(helper.route(UUID.fromString(tc.path("requirementId").asText())))).andReturn().getResponse().getContentAsString());assertEquals(tc,batch.path("testCases").get(0));verifyNoInteractions(client);}
    @Test void revisionSnapshotNotConfusedAfterEdit() throws Exception {var tc=approve(draft());var run=execute(tc);tc=edit(tc,"scenario",json.getNodeFactory().textNode("Changed after execution"));assertTrue(tc.path("reviewRevision").asLong()>run.path("testCaseRevision").asLong());assertNotEquals(tc.path("scenario"),run.at("/testCaseSnapshot/scenario"));mvc.perform(post(route(tc))).andExpect(status().isConflict());assertEquals(run,json.readTree(mvc.perform(get("/api/executions/"+run.path("executionId").asText())).andReturn().getResponse().getContentAsString()));}
    @Test void staleAnalysisDenied() throws Exception {var tc=approve(draft());var id=UUID.fromString(tc.path("requirementId").asText());var changed=helper.source(id);changed.withArray("missingConditions").add("new condition");analyses.save(id,changed);blocked(tc,"NOT_EXECUTABLE");}
    @Test void transportFailureIsSavedAsError() throws Exception {var tc=approve(draft());doThrow(new IllegalStateException("synthetic fault")).when(registry).invoke(any(),any(),any());var run=execute(tc);assertEquals("ERROR",run.path("result").asText());assertEquals("DUMMY_EXECUTION_ERROR",run.path("errorCode").asText());mvc.perform(get("/api/executions/"+run.path("executionId").asText())).andExpect(jsonPath("$.result").value("ERROR"));}
    @Test void assetApiPass() throws Exception {
        var tc=draft();var input=json.createObjectNode().put("apiId","API-ASSET-001").put("method","GET").put("endpoint","/assets/{assetId}").put("actorFixture","ordinary-employee");input.putObject("pathParameters").put("assetId",DummyApiRegistry.ASSET);input.putObject("body");tc=edit(tc,"input",input);
        tc=edit(tc,"preconditions",json.createArrayNode().add("합성 자산의 상태는 AVAILABLE이며 호출자와 같은 부서이다."));
        var expected=json.createObjectNode().put("description","Asset details");var assertions=expected.putArray("assertions");assertions.addObject().put("kind","HTTP_STATUS").put("value",200);assertions.addObject().put("kind","RESPONSE_FIELD").put("field","status").put("value","AVAILABLE");assertions.addObject().put("kind","RESPONSE_FIELD").put("field","assetId").put("value",DummyApiRegistry.ASSET);
        var run=execute(approve(edit(tc,"expectedResult",expected)));assertEquals("PASS",run.path("result").asText());assertEquals("API-ASSET-001",run.path("apiId").asText());
    }
    @Test void appCannotMutateHistory() throws Exception {var run=execute(approve(draft()));assertThrows(org.springframework.dao.DataAccessException.class,()->jdbc.update("DELETE FROM app.test_execution WHERE execution_id=?",UUID.fromString(run.path("executionId").asText())));}
    @Test void oldHistorySurvivesRegeneration() throws Exception {var tc=approve(draft());var run=execute(tc);UUID id=UUID.fromString(tc.path("requirementId").asText());when(client.generate(any(),any())).thenReturn(helper.response(id,helper.source(id)));mvc.perform(post(helper.route(id)+"/generate")).andExpect(status().isOk());mvc.perform(get(route(tc))).andExpect(jsonPath("$[0].executionId").value(run.path("executionId").asText()));}
}
