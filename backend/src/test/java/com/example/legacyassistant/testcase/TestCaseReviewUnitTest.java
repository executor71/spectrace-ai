package com.example.legacyassistant.testcase;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.Map;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class TestCaseReviewUnitTest {
    final ObjectMapper json=new ObjectMapper();
    @Test void technicalExecutabilityDoesNotImplyApproval() {
        var policy=mock(TestCasePolicy.class);when(policy.gates(any())).thenReturn(Map.of("allTechnicalChecks",true));
        var item=json.createObjectNode().put("scenario","original");TestCaseReviewService.decorate(item,policy,false);
        assertTrue(item.path("executable").asBoolean());assertEquals("DRAFT",item.path("approvalStatus").asText());assertFalse(item.path("executionEligible").asBoolean());
        item.put("approvalStatus","APPROVED");TestCaseReviewService.decorate(item,policy,false);assertTrue(item.path("executionEligible").asBoolean());
        item.put("approvalStatus","REJECTED");TestCaseReviewService.decorate(item,policy,false);assertTrue(item.path("executable").asBoolean());assertFalse(item.path("executionEligible").asBoolean());
    }
    @Test void approvalCannotBypassTechnicalFailureOrStaleSource() {
        var policy=mock(TestCasePolicy.class);when(policy.gates(any())).thenReturn(Map.of("fixtureReady",false));
        var item=json.createObjectNode().put("approvalStatus","APPROVED");TestCaseReviewService.decorate(item,policy,false);
        assertFalse(item.path("executable").asBoolean());assertFalse(item.path("executionEligible").asBoolean());
        when(policy.gates(any())).thenReturn(Map.of("allChecks",true));TestCaseReviewService.decorate(item,policy,true);
        assertFalse(item.path("executable").asBoolean());assertEquals("APPROVED",item.path("approvalStatus").asText());
    }
    @Test void textRequiresNonblankBoundedString() {
        for(var invalid:new com.fasterxml.jackson.databind.JsonNode[]{null,json.nullNode(),json.getNodeFactory().numberNode(12),json.getNodeFactory().textNode(" "),json.getNodeFactory().textNode("12345")})
            assertThrows(TestCaseException.class,()->TestCaseReviewService.text(invalid,4,"field"));
        assertDoesNotThrow(()->TestCaseReviewService.text(json.getNodeFactory().textNode("test"),4,"field"));
    }
    @Test void generatedSnapshotDoesNotAliasCurrentContent() {
        var policy=mock(TestCasePolicy.class);when(policy.gates(any())).thenReturn(Map.of("check",false));
        var item=json.createObjectNode().put("scenario","original");TestCaseReviewService.decorate(item,policy,false);item.put("scenario","edited");
        assertEquals("original",item.path("generatedContent").path("scenario").asText());
    }
}
