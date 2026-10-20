package com.example.legacyassistant.dashboard;
import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import java.util.*;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;
import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest @AutoConfigureMockMvc @Transactional
class DashboardIntegrationTest {
    @Autowired MockMvc mvc;@Autowired ObjectMapper json;@Autowired JdbcTemplate jdbc;@Autowired DashboardService dashboard;
    UUID id=UUID.randomUUID(),gen=UUID.randomUUID(),tc=UUID.randomUUID();
    @BeforeEach void seed(){
        jdbc.update("INSERT INTO app.requirement(id,title,description) VALUES (?,?,?)",id,"Phase13 저장 데이터","원문");
        jdbc.update("INSERT INTO app.test_case_generation(requirement_id,generation_id,source_analysis,metadata) VALUES (?,?,'{}'::jsonb,?::jsonb)",id,gen,"{\"generationId\":\""+gen+"\"}");
        ObjectNode body=json.createObjectNode().put("testCaseId",tc.toString()).put("requirementId",id.toString()).put("type","NORMAL").put("scenario","저장 시나리오").put("executable",false);body.putArray("evidence");
        jdbc.update("INSERT INTO app.test_case(test_case_id,requirement_id,generation_id,ordinal,result_json) VALUES (?,?,?,0,?::jsonb)",tc,id,gen,body.toString());
    }
    void execution(long revision,String result,boolean defect){UUID execution=UUID.randomUUID();ObjectNode row=json.createObjectNode().put("executionId",execution.toString()).put("testCaseId",tc.toString()).put("requirementId",id.toString()).put("generationId",gen.toString()).put("testCaseRevision",revision).put("result",result).put("syntheticDefect",defect);
        jdbc.update("INSERT INTO app.test_execution(execution_id,test_case_id,requirement_id,executed_at,result_json) VALUES (?,?,?,CURRENT_TIMESTAMP,?::jsonb)",execution,tc,id,row.toString());
    }
    @Test void currentRevisionAndUniqueCaseCountsMatchDatabase() throws Exception {
        execution(0,"PASS",false);execution(0,"PASS",false);execution(0,"FAIL",true);
        var out=dashboard.dashboard(id);assertEquals(1,out.at("/counts/total").asInt());assertEquals(1,out.at("/counts/PASS").asInt());assertEquals(0,out.at("/counts/FAIL").asInt());
        jdbc.update("UPDATE app.test_case SET review_revision=1 WHERE test_case_id=?",tc);
        mvc.perform(get("/api/dashboard/summary").param("requirementId",id.toString())).andExpect(status().isOk()).andExpect(jsonPath("$.counts.NOT_RUN").value(1)).andExpect(jsonPath("$.counts.total").value(1));
        assertEquals(3,jdbc.queryForObject("SELECT count(*) FROM app.test_execution WHERE requirement_id=?",Integer.class,id));
    }
    @Test void listReadsReviewedContentWithoutMutatingAnything()throws Exception{
        jdbc.update("UPDATE app.test_case SET reviewed_content='{\"scenario\":\"사용자 수정 시나리오\"}'::jsonb,review_revision=1 WHERE test_case_id=?",tc);
        mvc.perform(get("/api/dashboard/requirements").param("requirementId",id.toString())).andExpect(status().isOk()).andExpect(jsonPath("$.cases[0].scenario").value("사용자 수정 시나리오"));
        assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM app.test_execution WHERE requirement_id=?",Integer.class,id));
        var report=dashboard.reportData(id);assertEquals("사용자 수정 시나리오",report.at("/batch/testCases/0/scenario").asText());assertEquals("저장 시나리오",report.at("/batch/testCases/0/generatedContent/scenario").asText());
    }
    @Test void invalidAndMissingIdsAreErrors()throws Exception{
        mvc.perform(get("/api/dashboard/summary").param("requirementId","invalid")).andExpect(status().isBadRequest());
        mvc.perform(get("/api/requirements/"+UUID.randomUUID()+"/reports/test-report.xlsx")).andExpect(status().isNotFound()).andExpect(content().contentTypeCompatibleWith("application/json"));
    }
}
