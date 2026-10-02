package com.example.legacyassistant.testcase;
import com.fasterxml.jackson.databind.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
class ExecutionComparatorTest {
    ObjectMapper json=new ObjectMapper();ExecutionComparator comparator=new ExecutionComparator(json);
    @Test void numericStringsAreNotEqual() throws Exception {assertEquals(1,comparator.compare(json.readTree("{\"httpStatus\":200}"),json.readTree("{\"httpStatus\":\"200\"}")).size());}
    @Test void missingIsNotNull() throws Exception {assertEquals(1,comparator.compare(json.readTree("{\"response\":{\"currentLoan\":null}}"),json.readTree("{\"response\":{}}")).size());}
    @Test void responseFieldMismatch() throws Exception {assertEquals("response.status",comparator.compare(json.readTree("{\"response\":{\"status\":\"AVAILABLE\"}}"),json.readTree("{\"response\":{\"status\":\"RESERVED\"}}")).get(0).path("field").asText());}
    @Test void unsupportedAndEmptyAssertionsFailClosed() throws Exception {for(String text:new String[]{"[]","[{\"kind\":\"LLM_JUDGE\",\"value\":true}]","[{\"kind\":\"HTTP_STATUS\",\"value\":\"200\"}]","[{\"kind\":\"HTTP_STATUS\",\"value\":200,\"ignore\":true}]","[{\"kind\":\"HTTP_STATUS\",\"value\":200},{\"kind\":\"UNCHANGED\",\"field\":\"unknown\"}]"})assertFalse(comparator.checkable(json.readTree(text)));}
    @Test void duplicateAssertionsFailClosed() throws Exception {assertFalse(comparator.checkable(json.readTree("[{\"kind\":\"HTTP_STATUS\",\"value\":200},{\"kind\":\"HTTP_STATUS\",\"value\":400}]")));}
    @Test void unchangedCannotOverwriteStateAssertion() throws Exception {assertFalse(comparator.checkable(json.readTree("[{\"kind\":\"HTTP_STATUS\",\"value\":200},{\"kind\":\"OBSERVATION_EQUALS\",\"field\":\"loanStatus\",\"value\":\"APPROVED\"},{\"kind\":\"UNCHANGED\",\"field\":\"loanStatus\"}]")));}
    @Test void errorTokenMatchesExactFieldOnly() throws Exception {assertEquals(1,comparator.compare(json.readTree("{\"errorCode\":\"ACCESS_DENIED\"}"),json.readTree("{\"response\":{\"message\":\"ACCESS_DENIED\"},\"errorCode\":\"OTHER\"}")).size());}
    @Test void assetFixtureCannotPretendOtherDepartmentIsSameDepartment() throws Exception {
        var tc=json.createObjectNode();tc.putArray("preconditions").add("합성 자산의 상태는 AVAILABLE이며 호출자와 같은 부서이다.");
        var input=tc.putObject("input").put("method","GET").put("endpoint","/assets/{assetId}").put("actorFixture","other-department-manager");input.putObject("pathParameters").put("assetId",DummyApiRegistry.ASSET);input.putObject("body");
        var registry=new DummyApiRegistry(json);assertFalse(registry.fixtureReady(tc,registry.resolve(input)));
    }
}
