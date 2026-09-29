package com.example.legacyassistant.analysis;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.util.Map;
import java.util.UUID;
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
class AnalysisIntegrationTest {
    @Autowired MockMvc mvc;
    @Autowired ObjectMapper json;
    @Autowired JdbcTemplate jdbc;
    @MockitoBean AnalysisClient client;

    UUID requirement() throws Exception {
        var response=mvc.perform(post("/api/requirements").contentType("application/json")
            .content("{\"title\":\"승인\",\"description\":\"자기 승인 금지\"}"))
            .andExpect(status().isCreated()).andReturn().getResponse();
        return UUID.fromString(json.readTree(response.getContentAsString()).get("id").asText());
    }
    ObjectNode result(UUID id) {
        String chunk="33333333-3333-4333-8333-333333333333";
        var node=json.createObjectNode();node.put("requirementId",id.toString());
        for(String key:new String[]{"confirmedConditions","ambiguousExpressions","missingConditions","relatedBusinessRules","relatedApis","clarificationQuestions","evidence"}) node.putArray(key);
        node.withArray("confirmedConditions").addObject().put("text","자기 승인은 금지한다.").put("chunkId",chunk);
        node.withArray("evidence").addObject().put("documentId","22222222-2222-4222-8222-222222222222")
            .put("chunkId",chunk).put("documentType","BUSINESS_RULE").put("section","승인")
            .put("contentSnippet","자기 승인은 금지한다.").put("score",0.8);
        return node;
    }
    @Test void savesAndFetchesExactStructuredResultAndEvidence() throws Exception {
        UUID id=requirement();var body=result(id);when(client.analyze(any())).thenReturn(body);
        mvc.perform(post("/api/requirements/"+id+"/analysis")).andExpect(status().isOk()).andExpect(content().json(body.toString()));
        mvc.perform(get("/api/requirements/"+id+"/analysis")).andExpect(status().isOk()).andExpect(content().json(body.toString()));
        assertEquals("ANALYZED",jdbc.queryForObject("SELECT status FROM app.requirement WHERE id=?",String.class,id));
        assertEquals(1,jdbc.queryForObject("SELECT count(*) FROM app.requirement_analysis WHERE requirement_id=?",Integer.class,id));
    }
    @Test void nonexistentRequirementDoesNotCallModel() throws Exception {
        mvc.perform(post("/api/requirements/"+UUID.randomUUID()+"/analysis")).andExpect(status().isNotFound()).andExpect(jsonPath("$.code").value("REQUIREMENT_NOT_FOUND"));
        verifyNoInteractions(client);
    }
    @Test void missingAnalysisHasDistinct404() throws Exception {
        mvc.perform(get("/api/requirements/"+requirement()+"/analysis")).andExpect(status().isNotFound()).andExpect(jsonPath("$.code").value("ANALYSIS_NOT_FOUND"));
    }
    @Test void invalidUuidIs400() throws Exception {
        mvc.perform(post("/api/requirements/invalid/analysis")).andExpect(status().isBadRequest());verifyNoInteractions(client);
    }
    @Test void malformedModelOutputDoesNotPersistOrChangeStatus() throws Exception {
        UUID id=requirement();var invalid=result(id);invalid.remove("evidence");when(client.analyze(any())).thenReturn(invalid);
        mvc.perform(post("/api/requirements/"+id+"/analysis")).andExpect(status().isBadGateway()).andExpect(jsonPath("$.code").value("INVALID_ANALYSIS_OUTPUT"));
        assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM app.requirement_analysis WHERE requirement_id=?",Integer.class,id));
        assertEquals("DRAFT",jdbc.queryForObject("SELECT status FROM app.requirement WHERE id=?",String.class,id));
    }
    @Test void inventedClaimRejectedEvenWhenChunkIdExists() throws Exception {
        UUID id=requirement();var invalid=result(id);((ObjectNode)invalid.get("confirmedConditions").get(0)).put("text","대표이사는 24시간 후 자동 승인한다.");when(client.analyze(any())).thenReturn(invalid);
        mvc.perform(post("/api/requirements/"+id+"/analysis")).andExpect(status().isBadGateway());
    }
    @Test void failedReanalysisPreservesPreviousResult() throws Exception {
        UUID id=requirement();var valid=result(id);when(client.analyze(any())).thenReturn(valid);
        mvc.perform(post("/api/requirements/"+id+"/analysis")).andExpect(status().isOk());
        when(client.analyze(any())).thenThrow(new AnalysisException(503,"ANALYSIS_UNAVAILABLE","unavailable"));
        mvc.perform(post("/api/requirements/"+id+"/analysis")).andExpect(status().isServiceUnavailable());
        mvc.perform(get("/api/requirements/"+id+"/analysis")).andExpect(content().json(valid.toString()));
    }
    @Test void successfulReanalysisReplacesOneRow() throws Exception {
        UUID id=requirement();when(client.analyze(any())).thenReturn(result(id));
        mvc.perform(post("/api/requirements/"+id+"/analysis")).andExpect(status().isOk());
        mvc.perform(post("/api/requirements/"+id+"/analysis")).andExpect(status().isOk());
        assertEquals(1,jdbc.queryForObject("SELECT count(*) FROM app.requirement_analysis WHERE requirement_id=?",Integer.class,id));
    }
    @Test void appRoleHasNoRagOrEvaluationAccess() {
        assertEquals("app_user",jdbc.queryForObject("SELECT current_user",String.class));
        assertEquals(false,jdbc.queryForObject("SELECT has_schema_privilege(current_user,'evaluation','USAGE')",Boolean.class));
        assertEquals(false,jdbc.queryForObject("SELECT has_schema_privilege(current_user,'rag','USAGE')",Boolean.class));
        assertEquals(true,jdbc.queryForObject("SELECT has_table_privilege(current_user,'app.requirement_analysis','INSERT')",Boolean.class));
    }
}
