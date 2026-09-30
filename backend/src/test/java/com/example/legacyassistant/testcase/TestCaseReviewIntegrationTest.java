package com.example.legacyassistant.testcase;

import com.example.legacyassistant.analysis.AnalysisRepository;
import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@AutoConfigureMockMvc
@Transactional
class TestCaseReviewIntegrationTest {
    @Autowired MockMvc mvc; @Autowired ObjectMapper json; @Autowired JdbcTemplate jdbc;
    @Autowired AnalysisRepository analyses; @Autowired TestCasePolicy policy; @Autowired TestCaseRepository repository;
    @MockitoBean TestCaseClient client;
    UUID requirement() throws Exception {
        var response=mvc.perform(post("/api/requirements").contentType("application/json").content("{\"title\":\"승인\",\"description\":\"부서장 승인 및 자기 승인 금지\"}"))
            .andExpect(status().isCreated()).andReturn().getResponse();
        return UUID.fromString(json.readTree(response.getContentAsString()).get("id").asText());
    }
    ObjectNode source(UUID id) throws Exception {
        ObjectNode source=(ObjectNode)json.readTree(getClass().getResourceAsStream("/test-case-analysis.json"));source.put("requirementId",id.toString());return source;
    }
    ObjectNode response(UUID id,JsonNode source) {
        var candidates=policy.candidates(id,source);ObjectNode result=json.createObjectNode();
        result.put("policyHash",policy.hash);result.put("llmCalls",candidates.isEmpty()?0:1);
        var cases=result.putArray("testCases");var types=new HashSet<String>();
        candidates.values().forEach(c -> {var copy=c.deepCopy();copy.put("testCaseId",UUID.randomUUID().toString());cases.add(copy);types.add(c.get("type").asText());});
        result.set("clarificationRequired",json.valueToTree(policy.clarification(source,candidates)));
        result.set("uncoveredTypes",json.valueToTree(TestCasePolicy.TYPES.stream().filter(t -> !types.contains(t)).toList()));
        return result;
    }
    String route(UUID id) { return "/api/requirements/"+id+"/test-cases"; }

    ObjectNode generate() throws Exception {
        UUID id=requirement();var source=source(id);analyses.save(id,source);
        when(client.generate(any(),any())).thenReturn(response(id,source));
        var result=mvc.perform(post(route(id)+"/generate")).andExpect(status().isOk()).andReturn();
        clearInvocations(client);
        return (ObjectNode)json.readTree(result.getResponse().getContentAsString()).get("testCases").get(0);
    }
    String tc(JsonNode item){return "/api/test-cases/"+item.path("testCaseId").asText();}
    String revision(JsonNode item){return "{\"reviewRevision\":"+item.path("reviewRevision").asLong()+"}";}
    ObjectNode decision(JsonNode item,String action) throws Exception {
        var result=mvc.perform(post(tc(item)+"/"+action).contentType("application/json").content(revision(item))).andExpect(status().isOk()).andReturn();
        return (ObjectNode)json.readTree(result.getResponse().getContentAsString());
    }
    @Test void generatedDraftAndOriginalImmutable() throws Exception {
        var item=generate();assertEquals("DRAFT",item.path("approvalStatus").asText());
        assertTrue(item.path("reviewedContent").isNull());assertTrue(item.path("reviewedAt").isNull());
        assertFalse(item.path("executionEligible").asBoolean());assertFalse(item.path("generatedContent").has("approvalStatus"));
        mvc.perform(get(route(UUID.fromString(item.path("requirementId").asText())))).andExpect(jsonPath("$.testCases[0].approvalStatus").value("DRAFT"));
        verifyNoInteractions(client);
    }
    @Test void editAllFieldsApproveAndReload() throws Exception {
        var item=generate();var body=json.createObjectNode().put("reviewRevision",0).put("type","BOUNDARY").put("scenario","Reviewed scenario");
        body.putArray("preconditions").add("Reviewed precondition");body.putArray("steps").add("Reviewed step");
        body.putObject("input").put("manual","reviewed input");body.putObject("expectedResult").put("description","Reviewed outcome").putArray("assertions");
        var edited=mvc.perform(patch(tc(item)).contentType("application/json").content(body.toString())).andExpect(status().isOk())
            .andExpect(jsonPath("$.approvalStatus").value("DRAFT")).andExpect(jsonPath("$.modified").value(true)).andReturn();
        var value=json.readTree(edited.getResponse().getContentAsString());assertEquals(item.get("generatedContent"),value.get("generatedContent"));
        var approved=decision(value,"approve");assertEquals("APPROVED",approved.path("approvalStatus").asText());
        assertEquals("demo/local",approved.path("reviewer").asText());assertFalse(approved.path("reviewedAt").isNull());
        assertFalse(approved.path("executable").asBoolean());assertFalse(approved.path("executionEligible").asBoolean());
        var result=mvc.perform(get(route(UUID.fromString(item.path("requirementId").asText())))).andExpect(status().isOk()).andReturn();
        var reloaded=json.readTree(result.getResponse().getContentAsString()).get("testCases").get(0);
        assertEquals(approved,reloaded);assertEquals(item.get("evidence"),reloaded.get("evidence"));
        for(String key:TestCaseReviewService.EDITABLE)assertEquals(body.get(key),reloaded.get(key));verifyNoInteractions(client);
    }
    @Test void rejectPreservesEvidenceAndMetadata() throws Exception {
        var item=generate();var result=mvc.perform(post(tc(item)+"/reject").contentType("application/json")
            .content("{\"reviewRevision\":0,\"reviewer\":\"local-developer\",\"reviewComment\":\"Needs clarification\"}"))
            .andExpect(status().isOk()).andExpect(jsonPath("$.approvalStatus").value("REJECTED"))
            .andExpect(jsonPath("$.reviewer").value("local-developer")).andExpect(jsonPath("$.reviewComment").value("Needs clarification")).andReturn();
        var rejected=json.readTree(result.getResponse().getContentAsString());assertEquals(item.get("evidence"),rejected.get("evidence"));
        assertEquals(item.get("generatedContent"),rejected.get("generatedContent"));verifyNoInteractions(client);
    }
    @Test void protectedFieldsAndMassAssignmentAreRejected() throws Exception {
        var item=generate();for(String field:List.of("evidence","requirementId","documentId","chunkId","testCaseId","executable","approvalStatus","generatedContent","reviewedContent","reviewer","reviewedAt")) {
            var body=json.createObjectNode().put("reviewRevision",0).put(field,"forged");
            mvc.perform(patch(tc(item)).contentType("application/json").content(body.toString())).andExpect(status().isBadRequest());
        }
        for(String action:List.of("approve","reject"))mvc.perform(post(tc(item)+"/"+action).contentType("application/json").content("{\"reviewRevision\":0,\"evidence\":[]}")).andExpect(status().isBadRequest());
        assertEquals(item.get("evidence"),decision(item,"approve").get("evidence"));verifyNoInteractions(client);
    }
    @Test void invalidInputsAre400() throws Exception {
        var item=generate();for(String body:List.of("{}","[]","null","{","{\"reviewRevision\":0}","{\"reviewRevision\":0,\"type\":\"MODIFIED\"}",
            "{\"reviewRevision\":0,\"scenario\":\" \"}","{\"reviewRevision\":0,\"steps\":[]}","{\"reviewRevision\":0,\"input\":[]}",
            "{\"reviewRevision\":0,\"preconditions\":[2]}","{\"reviewRevision\":0,\"expectedResult\":{}}","{\"reviewRevision\":0,\"scenario\":null}"))
            mvc.perform(patch(tc(item)).contentType("application/json").content(body)).andExpect(status().isBadRequest());
        for(String body:List.of("{\"reviewRevision\":0,\"reviewer\":null}","{\"reviewRevision\":0,\"reviewer\":\" \"}","{\"reviewRevision\":0,\"reviewComment\":4}"))
            mvc.perform(post(tc(item)+"/approve").contentType("application/json").content(body)).andExpect(status().isBadRequest());
        verifyNoInteractions(client);
    }
    @Test void unknownAndMalformedIds() throws Exception {
        for(String suffix:List.of("/approve","/reject")) {
            mvc.perform(post("/api/test-cases/"+UUID.randomUUID()+suffix).contentType("application/json").content("{\"reviewRevision\":0}")).andExpect(status().isNotFound());
            mvc.perform(post("/api/test-cases/invalid"+suffix).contentType("application/json").content("{}")).andExpect(status().isBadRequest());
        }
        mvc.perform(patch("/api/test-cases/"+UUID.randomUUID()).contentType("application/json").content("{}")).andExpect(status().isNotFound());
        mvc.perform(patch("/api/test-cases/invalid").contentType("application/json").content("{}")).andExpect(status().isBadRequest());verifyNoInteractions(client);
    }
    @Test void editApprovedOrRejectedRequiresNewApproval() throws Exception {
        var item=generate();for(String action:List.of("approve","reject")) {
            item=decision(item,action);
            var result=mvc.perform(patch(tc(item)).contentType("application/json").content("{\"reviewRevision\":"+item.path("reviewRevision").asLong()+",\"scenario\":\"Updated after "+action+"\"}"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.approvalStatus").value("DRAFT")).andReturn();
            item=(ObjectNode)json.readTree(result.getResponse().getContentAsString());assertTrue(item.path("reviewer").isNull());assertTrue(item.path("reviewedAt").isNull());assertTrue(item.path("reviewComment").isNull());
        }
    }
    @Test void staleRevisionCannotOverwriteReview() throws Exception {
        var item=generate();decision(item,"approve");
        mvc.perform(post(tc(item)+"/reject").contentType("application/json").content(revision(item))).andExpect(status().isConflict());
        mvc.perform(patch(tc(item)).contentType("application/json").content("{\"reviewRevision\":0,\"scenario\":\"Old tab\"}")).andExpect(status().isConflict());
    }
    @Test void staleAnalysisOrPolicyCannotApprove() throws Exception {
        var item=generate();UUID id=UUID.fromString(item.path("requirementId").asText());var changed=source(id);changed.withArray("missingConditions").add("New question");analyses.save(id,changed);
        mvc.perform(post(tc(item)+"/approve").contentType("application/json").content(revision(item))).andExpect(status().isConflict());
        assertEquals("REJECTED",decision(item,"reject").path("approvalStatus").asText());
        item=generate();jdbc.update("UPDATE app.test_case_generation SET metadata=jsonb_set(metadata,'{policyHash}','\"different\"') WHERE requirement_id=?",UUID.fromString(item.path("requirementId").asText()));
        mvc.perform(post(tc(item)+"/approve").contentType("application/json").content(revision(item))).andExpect(status().isConflict());
    }
    @Test void regenerationStartsDraftAndOldIdDisappears() throws Exception {
        var item=generate();decision(item,"approve");UUID id=UUID.fromString(item.path("requirementId").asText());when(client.generate(any(),any())).thenReturn(response(id,source(id)));
        mvc.perform(post(route(id)+"/generate")).andExpect(status().isOk()).andExpect(jsonPath("$.testCases[0].approvalStatus").value("DRAFT"));
        mvc.perform(post(tc(item)+"/approve").contentType("application/json").content(revision(item))).andExpect(status().isNotFound());
    }
    @Test void databaseRejectsOriginalEvidenceUpdate() throws Exception {
        var item=generate();assertThrows(org.springframework.dao.DataAccessException.class,()->jdbc.update("UPDATE app.test_case SET result_json=jsonb_set(result_json,'{evidence}','[]') WHERE test_case_id=?",UUID.fromString(item.path("testCaseId").asText())));
    }
    @Test void unverifiedStoredEvidenceCannotBeApproved() throws Exception {
        var item=generate();UUID id=UUID.fromString(item.path("requirementId").asText());var invalid=source(id);invalid.putArray("evidence");analyses.save(id,invalid);
        jdbc.update("UPDATE app.test_case_generation SET source_analysis=CAST(? AS jsonb) WHERE requirement_id=?",invalid.toString(),id);
        mvc.perform(post(tc(item)+"/approve").contentType("application/json").content(revision(item))).andExpect(status().isConflict());
    }
}
