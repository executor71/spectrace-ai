package com.example.legacyassistant.testcase;

import com.example.legacyassistant.analysis.AnalysisRepository;
import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.bean.override.mockito.*;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest(properties="analysis.jobs.enabled=false") @AutoConfigureMockMvc @Transactional
class ReturnExecutionIntegrationTest {
    @Autowired MockMvc mvc;@Autowired ObjectMapper json;@Autowired JdbcTemplate jdbc;
    @Autowired AnalysisRepository analyses;@Autowired TestCasePolicy policy;@Autowired TestCaseRepository repository;
    @Autowired com.example.legacyassistant.dashboard.DashboardService dashboard;
    @MockitoBean TestCaseClient client;@MockitoSpyBean DummyApiRegistry registry;
    TestCaseReviewIntegrationTest helper;
    @BeforeEach void setup(){helper=new TestCaseReviewIntegrationTest();helper.mvc=mvc;helper.json=json;helper.jdbc=jdbc;helper.analyses=analyses;helper.policy=policy;helper.repository=repository;helper.client=client;}
    ObjectNode draft(String plan)throws Exception{
        UUID id=helper.requirement();String file=plan.startsWith("inspection")?"/return-execution-inspection.json":"/policy-extension-return.json";
        ObjectNode source=(ObjectNode)json.readTree(getClass().getResourceAsStream(file));source.put("requirementId",id.toString());analyses.save(id,source);
        when(client.generate(any(),any())).thenReturn(helper.response(id,source));
        var batch=json.readTree(mvc.perform(post(helper.route(id)+"/generate")).andExpect(status().isOk()).andReturn().getResponse().getContentAsString());
        var expected=policy.candidates(id,source).get(plan);assertNotNull(expected,plan);
        for(var tc:batch.path("testCases"))if(tc.path("scenario").equals(expected.path("scenario")) && tc.path("expectedResult").equals(expected.path("expectedResult")))return (ObjectNode)tc;
        throw new AssertionError("No matching template "+plan);
    }
    ObjectNode prepare(JsonNode tc,String mode)throws Exception{
        var body=json.createObjectNode().put("reviewRevision",tc.path("reviewRevision").asLong()).put("fixtureProfile",mode);
        return (ObjectNode)json.readTree(mvc.perform(post(helper.tc(tc)+"/return-execution-setup").contentType("application/json").content(body.toString())).andExpect(status().isOk()).andReturn().getResponse().getContentAsString());
    }
    ObjectNode approved(String plan,String mode)throws Exception{return helper.decision(prepare(draft(plan),mode),"approve");}
    JsonNode run(JsonNode tc)throws Exception{return json.readTree(mvc.perform(post(helper.tc(tc)+"/executions").header("If-Match",tc.path("reviewRevision").asLong())).andExpect(status().isCreated()).andReturn().getResponse().getContentAsString());}
    JsonNode eligibility(JsonNode tc)throws Exception{return json.readTree(mvc.perform(get(helper.tc(tc)+"/execution-eligibility")).andExpect(status().isOk()).andReturn().getResponse().getContentAsString());}
    void blocked(JsonNode tc,String reason)throws Exception{mvc.perform(post(helper.tc(tc)+"/executions")).andExpect(status().isConflict()).andExpect(jsonPath("$.code").value(reason));verify(registry,never()).invoke(any(),any(),any());}
    @Test void normalPassChecksBodyAndStateAndPersists()throws Exception{
        var tc=approved("return-normal","standard");assertTrue(eligibility(tc).path("executionEligible").asBoolean());
        var result=run(tc);assertEquals("PASS",result.path("result").asText());assertEquals(201,result.at("/actual/httpStatus").asInt());assertEquals("INSPECTION_PENDING",result.at("/actual/response/status").asText());
        assertEquals("ON_LOAN",result.at("/actual/state/assetStatus").asText());assertEquals(1,result.at("/actual/state/returnCount").asInt());
        var saved=json.readTree(mvc.perform(get("/api/executions/"+result.path("executionId").asText())).andReturn().getResponse().getContentAsString());assertEquals(result,saved);
        assertEquals(tc.path("reviewRevision"),result.path("testCaseRevision"));assertTrue(result.path("sourceEvidence").findValuesAsText("documentType").contains("API_SPEC"));
    }
    @Test void authorizedAssetAdminPasses()throws Exception{assertEquals("PASS",run(approved("return-normal","asset-admin")).path("result").asText());}
    @Test void duplicateRejectDoesNotCreateHistory()throws Exception{var result=run(approved("return-duplicate","standard"));assertEquals("PASS",result.path("result").asText());assertEquals(409,result.at("/actual/httpStatus").asInt());assertEquals(result.path("fixtureBefore"),result.at("/actual/state"));}
    @Test void completedReturnRejectsAndPreservesAvailable()throws Exception{var result=run(approved("return-duplicate","completed-return"));assertEquals("PASS",result.path("result").asText());assertEquals("AVAILABLE",result.at("/actual/state/assetStatus").asText());assertTrue(result.at("/actual/state/inspectionCompleted").asBoolean());}
    @Test void unauthorizedRejectPreservesAllState()throws Exception{var result=run(approved("return-authorization","standard"));assertEquals("PASS",result.path("result").asText());assertEquals(403,result.at("/actual/httpStatus").asInt());assertEquals(result.path("fixtureBefore"),result.at("/actual/state"));}
    @Test void pendingInspectionDoesNotReleaseAsset()throws Exception{var result=run(approved("return-inspection-pending","standard"));assertEquals("PASS",result.path("result").asText());assertEquals("ON_LOAN",result.at("/actual/state/assetStatus").asText());}
    @Test void successfulHttpWithWrongStateIsRealFail()throws Exception{var result=run(approved("return-normal","intentional-defect"));assertEquals("FAIL",result.path("result").asText());assertEquals(201,result.at("/expected/httpStatus").asInt());assertEquals(201,result.at("/actual/httpStatus").asInt());assertEquals("state.assetStatus",result.at("/mismatches/0/field").asText());assertTrue(result.path("syntheticDefect").asBoolean());}
    @Test void fixtureInitializationFailureIsSavedAsError()throws Exception{var result=run(approved("return-normal","fixture-error"));assertEquals("ERROR",result.path("result").asText());assertEquals("FIXTURE_INITIALIZATION_ERROR",result.path("errorCode").asText());assertTrue(result.path("fixtureBefore").isNull());assertTrue(result.path("mismatches").isEmpty());verify(registry,never()).invoke(any(),any(),any());}
    @Test void transportFailureIsErrorNotFail()throws Exception{var tc=approved("return-normal","standard");doThrow(new IllegalStateException(new java.net.SocketTimeoutException())).when(registry).invoke(any(),any(),any());assertEquals("ERROR",run(tc).path("result").asText());}
    @Test void draftAndRejectedRemainBlocked()throws Exception{var tc=prepare(draft("return-normal"),"standard");blocked(tc,"NOT_APPROVED");blocked(helper.decision(tc,"reject"),"NOT_APPROVED");}
    @Test void existingUnpreparedCaseIsNotBulkEnabled()throws Exception{var tc=helper.decision(draft("return-normal"),"approve");blocked(tc,"FIXTURE_NOT_READY");}
    @Test void prepareInvalidatesApprovalAndStaleRevisionIsRejected()throws Exception{
        var tc=approved("return-normal","standard");var updated=prepare(tc,"intentional-defect");assertEquals("DRAFT",updated.path("approvalStatus").asText());assertTrue(updated.path("reviewRevision").asLong()>tc.path("reviewRevision").asLong());
        blocked(updated,"NOT_APPROVED");var reapproved=helper.decision(updated,"approve");mvc.perform(post(helper.tc(reapproved)+"/executions").header("If-Match",tc.path("reviewRevision").asLong())).andExpect(status().isConflict()).andExpect(jsonPath("$.code").value("REVIEW_CONFLICT"));
    }
    @Test void weakenedAssertionsFailClosed()throws Exception{var tc=approved("return-normal","standard");var body=json.createObjectNode().put("reviewRevision",tc.path("reviewRevision").asLong());var expected=tc.path("expectedResult").deepCopy();((ObjectNode)expected).putArray("assertions").addObject().put("kind","HTTP_STATUS").put("value",201);body.set("expectedResult",expected);
        var changed=(ObjectNode)json.readTree(mvc.perform(patch(helper.tc(tc)).contentType("application/json").content(body.toString())).andReturn().getResponse().getContentAsString());blocked(helper.decision(changed,"approve"),"EXECUTION_CONTRACT_UNSUPPORTED");}
    @Test void unsupportedInspectionSuccessRemainsBlocked()throws Exception{var tc=helper.decision(draft("inspection-passed"),"approve");blocked(tc,"EXECUTION_CONTRACT_UNSUPPORTED");}
    @Test void returnCannotBeRedirectedToAnotherAllowedAdapter()throws Exception{
        var tc=approved("return-normal","standard");var body=json.createObjectNode().put("reviewRevision",tc.path("reviewRevision").asLong());
        var input=(ObjectNode)tc.path("input").deepCopy();input.put("endpoint","/loans/{loanId}/approve");body.set("input",input);
        var changed=(ObjectNode)json.readTree(mvc.perform(patch(helper.tc(tc)).contentType("application/json").content(body.toString())).andExpect(status().isOk()).andReturn().getResponse().getContentAsString());
        blocked(helper.decision(changed,"approve"),"EXECUTION_CONTRACT_UNSUPPORTED");
    }
    @Test void inspectionMissingDamageEvidencePasses400Contract()throws Exception{var result=run(approved("inspection-damage-required","standard"));assertEquals("PASS",result.path("result").asText());assertEquals(400,result.at("/actual/httpStatus").asInt());assertEquals(result.path("fixtureBefore"),result.at("/actual/state"));}
    @Test void executionBodyCannotSelectFaultMode()throws Exception{var tc=approved("return-normal","standard");mvc.perform(post(helper.tc(tc)+"/executions").contentType("application/json").content("{\"fixtureProfile\":\"intentional-defect\"}")).andExpect(status().isBadRequest());verify(registry,never()).invoke(any(),any(),any());}
    @Test void unknownSetupFieldsAndProfilesRejected()throws Exception{var tc=draft("return-normal");mvc.perform(post(helper.tc(tc)+"/return-execution-setup").contentType("application/json").content("{\"reviewRevision\":0,\"fixtureProfile\":\"standard\",\"url\":\"http://outside.invalid\"}")).andExpect(status().isBadRequest());
        mvc.perform(post(helper.tc(tc)+"/return-execution-setup").contentType("application/json").content("{\"reviewRevision\":0,\"fixtureProfile\":\"unknown\"}")).andExpect(status().isConflict());}
    @Test void repeatedRunsAreIsolatedAndDoNotModifyReview()throws Exception{var tc=approved("return-normal","standard");var a=run(tc);var b=run(tc);assertEquals(a.path("actual"),b.path("actual"));assertEquals(a.path("fixtureBefore"),b.path("fixtureBefore"));assertNotEquals(a.path("executionId"),b.path("executionId"));var batch=json.readTree(mvc.perform(get(helper.route(UUID.fromString(tc.path("requirementId").asText())))).andReturn().getResponse().getContentAsString());assertEquals(tc,batch.at("/testCases/0"));}
    @Test void realReturnRunsFlowToDashboardAndExcelWithoutFormulaOrSyntheticMixup()throws Exception{
        var tc=approved("return-normal","standard");run(tc);UUID rid=UUID.fromString(tc.path("requirementId").asText());
        var batch=json.readTree(mvc.perform(get(helper.route(rid))).andReturn().getResponse().getContentAsString());
        var pending=batch.path("testCases").get(3);run(helper.decision(prepare(pending,"intentional-defect"),"approve"));
        var data=dashboard.reportData(rid);assertEquals(1,data.at("/counts/PASS").asInt());assertEquals(0,data.at("/counts/FAIL").asInt());assertEquals(1,data.at("/counts/SYNTHETIC").asInt());assertEquals(2,data.path("executions").size());
        try(var book=new org.apache.poi.xssf.usermodel.XSSFWorkbook(new java.io.ByteArrayInputStream(com.example.legacyassistant.dashboard.ReportService.workbook(data)))){
            var executions=book.getSheet("실행결과");assertEquals(2,executions.getLastRowNum());Set<String> statuses=new HashSet<>();
            assertEquals("결과",executions.getRow(0).getCell(7).getStringCellValue());
            for(var row:executions){if(row.getRowNum()>0){statuses.add(row.getCell(7).getStringCellValue());assertEquals("API-RETURN-CREATE",row.getCell(4).getStringCellValue());assertTrue(row.getCell(2).getNumericCellValue()>0);}for(var cell:row)assertNotEquals(org.apache.poi.ss.usermodel.CellType.FORMULA,cell.getCellType());}
            assertEquals(Set.of("PASS","FAIL"),statuses);
        }
    }
}
