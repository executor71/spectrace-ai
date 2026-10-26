package com.example.legacyassistant.testcase;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import org.junit.jupiter.api.*;
import java.nio.file.*;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;

class PolicyExtensionTest {
    final ObjectMapper json=new ObjectMapper();
    TestCasePolicy policy;
    ObjectNode source;
    @BeforeEach void setup() throws Exception {
        policy=new TestCasePolicy(json,"/contracts/test-case-policy.json");
        source=(ObjectNode)json.readTree(getClass().getResourceAsStream("/policy-extension-return.json"));
    }
    ObjectNode response(JsonNode analysis) {
        var expected=policy.candidates(UUID.fromString(analysis.path("requirementId").asText()),analysis);
        ObjectNode out=json.createObjectNode().put("policyHash",policy.hash).put("llmCalls",expected.isEmpty()?0:1);
        var cases=out.putArray("testCases");Set<String> types=new HashSet<>();
        expected.values().forEach(value->{var copy=value.deepCopy();copy.put("testCaseId",UUID.randomUUID().toString());cases.add(copy);types.add(value.path("type").asText());});
        out.set("clarificationRequired",json.valueToTree(policy.clarification(analysis,expected)));
        out.set("uncoveredTypes",json.valueToTree(TestCasePolicy.TYPES.stream().filter(t->!types.contains(t)).toList()));
        return out;
    }
    ObjectNode describe(JsonNode analysis) {
        var out=response(analysis);policy.validate(UUID.fromString(analysis.path("requirementId").asText()),analysis,out);
        out.set("sourceAnalysis",analysis.deepCopy());policy.describe(out);return out;
    }
    @Test void originalFourConditionsGenerateFourGroundedCasesWithPartialCoverage() {
        var out=describe(source);
        assertEquals(4,out.path("testCases").size());assertEquals("PARTIALLY_GENERATED",out.path("generationStatus").asText());
        assertEquals(3,out.path("conditionCoverage").findValuesAsText("status").stream().filter("SUPPORTED"::equals).count());
        assertEquals(1,out.path("policyEvidence").size());
        for(var tc:out.path("testCases")){assertFalse(tc.path("executable").asBoolean());for(var ref:tc.path("evidence"))assertTrue(out.path("sourceAnalysis").path("evidence").findValuesAsText("chunkId").contains(ref.path("chunkId").asText()));}
        assertEquals(5,source.path("evidence").size()); // Original analysis remains untouched.
    }
    @Test void noApplicableTemplateIsNotClarificationRequired() {
        var conditions=(ArrayNode)source.path("confirmedConditions");var unsupported=conditions.get(3).deepCopy();conditions.removeAll();conditions.add(unsupported);
        assertEquals("BLOCKED_UNSUPPORTED_TEMPLATE",describe(source).path("generationStatus").asText());
    }
    @Test void missingApiReferenceIsInsufficientEvidence() {
        ((ArrayNode)source.path("relatedApis")).removeAll();
        assertEquals("BLOCKED_INSUFFICIENT_EVIDENCE",describe(source).path("generationStatus").asText());
    }
    @Test void clarificationAndEmptyEvidenceHaveDistinctStatus() {
        ((ArrayNode)source.path("clarificationQuestions")).add("반납 이력 판정 기준 확인");
        assertEquals("BLOCKED_CLARIFICATION_REQUIRED",describe(source).path("generationStatus").asText());
        ((ArrayNode)source.path("clarificationQuestions")).removeAll();((ArrayNode)source.path("confirmedConditions")).removeAll();
        assertEquals("BLOCKED_INSUFFICIENT_EVIDENCE",describe(source).path("generationStatus").asText());
    }
    @Test void expectedResultAndEvidenceCannotBeOverridden() {
        var out=response(source);((ObjectNode)out.at("/testCases/0/expectedResult")).put("description","무근거 결과");
        assertThrows(TestCaseException.class,()->policy.validate(UUID.fromString(source.path("requirementId").asText()),source,out));
    }
    @Test void duplicateIdsFakeEndpointAndForgedEvidenceFailPolicyLoading() throws Exception {
        for(String mutation:List.of("duplicate","endpoint","evidence","expected")) {
            ObjectNode data=(ObjectNode)json.readTree(Files.readString(Path.of("/contracts/test-case-policy.json")));
            if(mutation.equals("duplicate"))((ArrayNode)data.path("plans")).add(data.path("plans").get(0).deepCopy());
            if(mutation.equals("endpoint"))((ObjectNode)data.at("/plans/5/case/input")).put("endpoint","/admin/erase");
            if(mutation.equals("evidence"))((ObjectNode)data.path("apiEvidence").get(0)).put("chunkId",UUID.randomUUID().toString());
            if(mutation.equals("expected"))((ObjectNode)data.at("/plans/5/case/expectedResult")).put("description","무근거 결과");
            Path temporary=Files.createTempFile("invalid-policy-",".json");
            try {Files.writeString(temporary,data.toString());assertThrows(Exception.class,()->new TestCasePolicy(json,temporary.toString()));}
            finally {Files.deleteIfExists(temporary);}
        }
    }
}
