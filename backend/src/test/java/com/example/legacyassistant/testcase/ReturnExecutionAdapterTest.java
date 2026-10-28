package com.example.legacyassistant.testcase;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import org.junit.jupiter.api.*;
import java.util.*;
import java.util.concurrent.*;
import static org.junit.jupiter.api.Assertions.*;

class ReturnExecutionAdapterTest {
    final ObjectMapper json=new ObjectMapper();DummyApiRegistry registry;TestCasePolicy policy;JsonNode source;
    @BeforeEach void setup()throws Exception{registry=new DummyApiRegistry(json);policy=new TestCasePolicy(json,"/contracts/test-case-policy.json");source=json.readTree(getClass().getResourceAsStream("/policy-extension-return.json"));}
    ObjectNode configured(String plan,String mode){var original=policy.candidates(UUID.fromString(source.path("requirementId").asText()),source).get(plan).deepCopy();original.put("testCaseId",UUID.randomUUID().toString());var tc=original.deepCopy();tc.set("generatedContent",original);tc.setAll(registry.returnSetup(tc,plan,mode));return tc;}
    @Test void concurrentIndependentFixturesNeverContaminateEachOther()throws Exception{
        var pool=Executors.newFixedThreadPool(8);
        try{List<Callable<JsonNode>> calls=new ArrayList<>();for(int i=0;i<40;i++){final boolean defect=i%2==0;calls.add(()->{var tc=configured("return-normal",defect?"intentional-defect":"standard");var state=registry.prepare(tc);assertEquals(0,state.path("returnCount").asInt());registry.invoke(registry.resolve(tc.path("input")),tc.path("input"),state);assertEquals(1,state.path("returnCount").asInt());assertEquals(defect?"AVAILABLE":"ON_LOAN",state.path("assetStatus").asText());return state;});}
            for(var result:pool.invokeAll(calls))assertNotNull(result.get());
        }finally{pool.shutdownNow();}
    }
    @Test void arbitraryBodyAndFixtureParametersAreNotAccepted(){var tc=configured("return-normal","standard");var api=registry.resolve(tc.path("input"));assertTrue(registry.inputValid(tc.path("input"),api));((ObjectNode)tc.at("/input/body")).put("role","asset-admin");assertFalse(registry.inputValid(tc.path("input"),api));assertFalse(registry.fixtureReady(tc,api));}
    @Test void unsupportedObservationFieldsAndTypesFailClosed(){var comparator=new ExecutionComparator(json);var assertions=json.createArrayNode();assertions.addObject().put("kind","HTTP_STATUS").put("value",201);assertions.addObject().put("kind","OBSERVATION_EQUALS").put("field","returnCount").put("value","1");assertFalse(comparator.checkable(assertions));((ObjectNode)assertions.get(1)).put("field","arbitraryDatabaseField");assertFalse(comparator.checkable(assertions));}
    @Test void contractVersionAndExpectedResultCannotBeTampered(){var tc=configured("return-normal","standard");assertTrue(registry.returnContract(tc,"return-normal"));((ObjectNode)tc.path("input")).put("executionContractVersion","old");assertFalse(registry.returnContract(tc,"return-normal"));assertFalse(registry.inputValid(tc.path("input"),registry.resolve(tc.path("input"))));}
}
