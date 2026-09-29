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
class TestCaseIntegrationTest {
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
    @Test void generateSaveGetFiveTypesAndEvidence() throws Exception {
        UUID id=requirement();var source=source(id);analyses.save(id,source);when(client.generate(any(),any())).thenReturn(response(id,source));
        mvc.perform(post(route(id)+"/generate")).andExpect(status().isOk()).andExpect(jsonPath("$.testCases.length()").value(5)).andExpect(jsonPath("$.testCases[0].executable").value(false));
        mvc.perform(get(route(id))).andExpect(status().isOk()).andExpect(jsonPath("$.testCases.length()").value(5)).andExpect(jsonPath("$.stale").value(false));
        assertEquals(5,jdbc.queryForObject("SELECT count(*) FROM app.test_case WHERE requirement_id=?",Integer.class,id));
    }
    @Test void missingRequirementAndAnalysisDoNotCallAi() throws Exception {
        mvc.perform(post(route(UUID.randomUUID())+"/generate")).andExpect(status().isNotFound());
        mvc.perform(post(route(requirement())+"/generate")).andExpect(status().isConflict()).andExpect(jsonPath("$.code").value("ANALYSIS_REQUIRED"));verifyNoInteractions(client);
    }
    @Test void missingGenerationAndBadId() throws Exception {
        mvc.perform(get(route(requirement()))).andExpect(status().isNotFound()).andExpect(jsonPath("$.code").value("TEST_CASES_NOT_FOUND"));
        mvc.perform(post("/api/requirements/invalid/test-cases/generate")).andExpect(status().isBadRequest());verifyNoInteractions(client);
    }
    @Test void rejectInventedOutcomeApiEvidenceAndExecutable() throws Exception {
        UUID id=requirement();var source=source(id);analyses.save(id,source);
        for(String field:List.of("expectedResult","input","evidence","executable","type","extra")) {
            var invalid=response(id,source);((ObjectNode)invalid.get("testCases").get(0)).put(field,"invented");when(client.generate(any(),any())).thenReturn(invalid);
            mvc.perform(post(route(id)+"/generate")).andExpect(status().isBadGateway());
        }
        assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM app.test_case WHERE requirement_id=?",Integer.class,id));
    }
    @Test void rejectDuplicateIdOrCandidate() throws Exception {
        UUID id=requirement();var source=source(id);var invalid=response(id,source);
        ((ObjectNode)invalid.get("testCases").get(1)).put("testCaseId",invalid.at("/testCases/0/testCaseId").asText());
        assertThrows(TestCaseException.class,() -> policy.validate(id,source,invalid));
        var duplicate=response(id,source);((com.fasterxml.jackson.databind.node.ArrayNode)duplicate.get("testCases")).set(1,duplicate.get("testCases").get(0));
        assertThrows(TestCaseException.class,() -> policy.validate(id,source,duplicate));
    }
    @Test void insufficientEvidenceStoresOnlyClarification() throws Exception {
        UUID id=requirement();var source=source(id);source.putArray("confirmedConditions");source.withArray("missingConditions").add("근거 없음");source.withArray("clarificationQuestions").add("업무규칙 확인?");analyses.save(id,source);
        when(client.generate(any(),any())).thenReturn(response(id,source));
        mvc.perform(post(route(id)+"/generate")).andExpect(status().isOk()).andExpect(jsonPath("$.testCases.length()").value(0)).andExpect(jsonPath("$.llmCalls").value(0));
        mvc.perform(get(route(id))).andExpect(jsonPath("$.clarificationRequired[0]").value("근거 없음"));
    }
    @Test void ambiguousConditionCannotBePromoted() throws Exception {
        UUID id=requirement();var source=source(id);var fabricated=response(id,source);source.withArray("ambiguousExpressions").add("빠르게");
        assertThrows(TestCaseException.class,() -> policy.validate(id,source,fabricated));
    }
    @Test void failedRegenerationPreservesSuccessfulBatch() throws Exception {
        UUID id=requirement();var source=source(id);analyses.save(id,source);when(client.generate(any(),any())).thenReturn(response(id,source));
        mvc.perform(post(route(id)+"/generate")).andExpect(status().isOk());
        var prior=repository.find(id).orElseThrow();when(client.generate(any(),any())).thenThrow(new TestCaseException(503,"TEST_CASE_UNAVAILABLE","unavailable"));
        mvc.perform(post(route(id)+"/generate")).andExpect(status().isServiceUnavailable());assertEquals(prior,repository.find(id).orElseThrow());
    }
    @Test void successfulRegenerationAtomicallyReplacesRows() throws Exception {
        UUID id=requirement();var source=source(id);analyses.save(id,source);when(client.generate(any(),any())).thenAnswer(inv -> response(id,source));
        mvc.perform(post(route(id)+"/generate")).andExpect(status().isOk());mvc.perform(post(route(id)+"/generate")).andExpect(status().isOk());
        assertEquals(5,jdbc.queryForObject("SELECT count(*) FROM app.test_case WHERE requirement_id=?",Integer.class,id));
        assertEquals(1,jdbc.queryForObject("SELECT count(*) FROM app.test_case_generation WHERE requirement_id=?",Integer.class,id));
    }
    @Test void analysisChangeDuringGenerationReturnsConflict() throws Exception {
        UUID id=requirement();var source=source(id);analyses.save(id,source);
        when(client.generate(any(),any())).thenAnswer(inv -> {var changed=source.deepCopy();changed.withArray("missingConditions").add("새 조건");analyses.save(id,changed);return response(id,source);});
        mvc.perform(post(route(id)+"/generate")).andExpect(status().isConflict()).andExpect(jsonPath("$.code").value("TEST_CASE_SOURCE_CHANGED"));
        assertTrue(repository.find(id).isEmpty());
    }
    @Test void staleSnapshotRemainsVisibleWithExecutionDisabled() throws Exception {
        UUID id=requirement();var source=source(id);analyses.save(id,source);when(client.generate(any(),any())).thenReturn(response(id,source));
        mvc.perform(post(route(id)+"/generate")).andExpect(status().isOk());var changed=source.deepCopy();changed.withArray("missingConditions").add("새 조건");analyses.save(id,changed);
        mvc.perform(get(route(id))).andExpect(status().isOk()).andExpect(jsonPath("$.stale").value(true)).andExpect(jsonPath("$.testCases[0].executable").value(false));
    }
    @Test void appRoleCannotAccessGroundTruthAndRagRoleCannotReadTests() {
        assertFalse(jdbc.queryForObject("SELECT has_schema_privilege(current_user,'evaluation','USAGE')",Boolean.class));
        assertFalse(jdbc.queryForObject("SELECT has_schema_privilege(current_user,'rag','USAGE')",Boolean.class));
        assertFalse(jdbc.queryForObject("SELECT has_table_privilege('rag_reader','app.test_case','SELECT')",Boolean.class));
        assertTrue(jdbc.queryForObject("SELECT has_table_privilege(current_user,'app.test_case','INSERT')",Boolean.class));
    }
    @Test void policyMismatchRejected() throws Exception {
        UUID id=requirement();var source=source(id);var invalid=response(id,source);invalid.put("policyHash","different");
        assertThrows(TestCaseException.class,() -> policy.validate(id,source,invalid));
    }
}
