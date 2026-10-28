package com.example.legacyassistant.testcase;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import java.time.*;
import java.util.*;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import com.example.legacyassistant.observability.Tracing;
import java.util.function.Supplier;

@Service
public class ExecutionService {
    private final JdbcClient jdbc;private final ObjectMapper json;private final TestCasePolicy policy;
    private final DummyApiRegistry registry;private final ExecutionComparator comparator;
    private final Tracing tracing;
    public ExecutionService(JdbcClient jdbc,ObjectMapper json,TestCasePolicy policy,DummyApiRegistry registry,ExecutionComparator comparator,Tracing tracing){
        this.jdbc=jdbc;this.json=json;this.policy=policy;this.registry=registry;this.comparator=comparator;this.tracing=tracing;
    }
    private JsonNode parse(String value){try{return json.readTree(value);}catch(Exception e){throw new IllegalStateException(e);}}
    private record Case(ObjectNode content,JsonNode source,boolean stale,UUID generation){}
    private Case find(UUID id,boolean lock){
        return jdbc.sql("SELECT "+TestCaseReviewService.PROJECTION+"::text AS content,g.source_analysis::text AS source,g.generation_id,"+
            "(g.source_analysis IS DISTINCT FROM a.result_json OR g.metadata->>'policyHash' IS DISTINCT FROM :hash) AS stale "+
            "FROM app.test_case t JOIN app.test_case_generation g ON t.generation_id=g.generation_id "+
            "JOIN app.requirement_analysis a ON a.requirement_id=t.requirement_id WHERE t.test_case_id=:id"+(lock?" FOR SHARE OF a,g,t":""))
            .param("id",id).param("hash",policy.hash).query((rs,n)->new Case((ObjectNode)parse(rs.getString("content")),parse(rs.getString("source")),rs.getBoolean("stale"),rs.getObject("generation_id",UUID.class)))
            .optional().orElseThrow(()->new TestCaseException(404,"TEST_CASE_NOT_FOUND","테스트케이스가 없습니다."));
    }
    private ObjectNode assess(Case row) {
        var tc=row.content;var input=tc.path("input");var api=registry.resolve(input);
        // Phase 4's archived executable was provisional (fixtures did not exist). Recompute from current reviewed content.
        boolean executable=!row.stale && input.isObject() && comparator.checkable(tc.at("/expectedResult/assertions")) &&
            (api==null || registry.inputValid(input,api));
        boolean fixtureReady=registry.fixtureReady(tc,api);
        String returnPlan=null;boolean returnContract=true;boolean returnCase=DummyApiRegistry.isReturn(api)||ReturnExecutionAdapter.route(tc.path("generatedContent").path("input"));
        if(returnCase){try{returnPlan=policy.verifiedPlan(tc,row.source);}catch(RuntimeException invalid){/* fail closed */}
            returnContract=registry.returnContract(tc,returnPlan);executable=executable && fixtureReady && returnContract;}
        String reason=!tc.path("approvalStatus").asText().equals("APPROVED")?"NOT_APPROVED":
            !executable?"NOT_EXECUTABLE":api==null?"API_NOT_ALLOWED":!fixtureReady?"FIXTURE_NOT_READY":null;
        if(returnCase && tc.path("approvalStatus").asText().equals("APPROVED") && !row.stale){
            if(api==null)reason="API_NOT_ALLOWED";
            else if(returnPlan==null||registry.returnModes(returnPlan).isEmpty())reason="EXECUTION_CONTRACT_UNSUPPORTED";
            else if(!input.has("executionContractVersion"))reason="FIXTURE_NOT_READY";
            else if(!returnContract)reason="EXECUTION_CONTRACT_UNSUPPORTED";
        }
        ObjectNode result=json.createObjectNode().put("testCaseId",tc.path("testCaseId").asText()).put("approvalStatus",tc.path("approvalStatus").asText())
            .put("executable",executable).put("fixtureReady",fixtureReady).put("apiAllowed",api!=null).put("executionEligible",reason==null)
            .put("reviewRevision",tc.path("reviewRevision").asLong()).put("assessmentVersion",DummyApiRegistry.VERSION);
        if(api!=null)result.put("apiId",api.apiId());else result.putNull("apiId");
        if(reason!=null)result.put("blockedReason",reason);else result.putNull("blockedReason");
        result.put("syntheticDefect",DummyApiRegistry.synthetic(input));
        if(returnCase){result.put("executionContractVersion",ReturnExecutionAdapter.VERSION);result.put("templateId",returnPlan==null?"":returnPlan);
            result.set("returnFixtureOptions",json.valueToTree(row.stale?List.of():registry.returnModes(returnPlan)));}
        return result;
    }
    private <T>T stage(String name,Supplier<T> action){
        var span=tracing.tracer.spanBuilder(name).startSpan();
        try(var scope=span.makeCurrent()){return action.get();}catch(RuntimeException error){Tracing.error(span,"DUMMY_EXECUTION_ERROR");throw error;}finally{span.end();}
    }
    public JsonNode eligibility(UUID id){return assess(find(id,false));}
    @Transactional
    public JsonNode execute(UUID id) {return executeRevision(id,null);}
    @Transactional
    public JsonNode executeRevision(UUID id,Long expectedRevision) {
        long start=System.nanoTime();Case row=find(id,true);
        if(expectedRevision!=null && expectedRevision.longValue()!=row.content.path("reviewRevision").asLong())throw new TestCaseException(409,"REVIEW_CONFLICT","선택한 승인 Revision이 변경되었습니다. 다시 조회하세요.");
        var eligibility=stage("execution.allowlist",()->assess(row));
        if(!eligibility.path("executionEligible").asBoolean())throw new TestCaseException(409,eligibility.path("blockedReason").asText(),"Dummy 실행 거부: "+eligibility.path("blockedReason").asText());
        var tc=row.content;var input=tc.path("input");var api=registry.resolve(input);
        UUID execution=UUID.randomUUID();Instant now=Instant.now();
        var report=json.createObjectNode().put("executionId",execution.toString()).put("testCaseId",id.toString())
            .put("requirementId",tc.path("requirementId").asText()).put("executedAt",now.toString()).put("apiId",api.apiId())
            .put("testCaseRevision",tc.path("reviewRevision").asLong()).put("generationId",row.generation.toString())
            .put("runnerVersion",DummyApiRegistry.VERSION).put("validator",api.validator()).put("syntheticDefect",eligibility.path("syntheticDefect").asBoolean());
        ObjectNode snapshot=tc.deepCopy();snapshot.put("executable",eligibility.path("executable").asBoolean()).put("fixtureReady",eligibility.path("fixtureReady").asBoolean()).put("executionEligible",true);
        report.set("testCaseSnapshot",snapshot);report.set("evidence",tc.path("evidence"));report.set("sourceEvidence",row.source.path("evidence"));
        if(DummyApiRegistry.isReturn(api)){
            var context=json.createObjectNode();context.set("sourceAnalysis",row.source);context.putArray("testCases").add(tc);policy.describe(context);
            report.set("sourceEvidence",context.path("sourceAnalysis").path("evidence"));report.put("executionContractVersion",ReturnExecutionAdapter.VERSION);
        }
        report.putObject("apiSpecEvidence").put("source",api.specification()).put("route",api.method()+" "+api.pathTemplate()).put("excerpt",api.specificationExcerpt());
        report.set("eligibility",eligibility);
        var request=report.putObject("request").put("method",api.method()).put("path",api.pathTemplate().replace("{"+api.pathKey()+"}",input.at("/pathParameters/"+api.pathKey()).asText()))
            .put("actorFixture",input.path("actorFixture").asText()).put("fixtureProfile",input.path("fixtureProfile").asText("standard"));
        request.set("body",input.path("body"));
        String failureStage="FIXTURE_INITIALIZATION";
        try {
            ObjectNode state=stage("execution.fixture.initialize",()->registry.prepare(tc));ObjectNode before=state.deepCopy();
            ObjectNode expected=comparator.expected(tc.at("/expectedResult/assertions"),before);
            if(api.apiId().equals("API-LOAN-APPROVE") && expected.path("httpStatus").asInt()==200 && expected.at("/state/loanStatus").isTextual())expected.withObject("/response").set("status",expected.at("/state/loanStatus"));
            report.set("expected",expected);report.set("fixtureBefore",before);failureStage="DUMMY_INVOCATION";
            var response=stage("execution.dummy.invoke",()->registry.invoke(api,input,state));var actual=report.putObject("actual").put("httpStatus",response.getStatusCode().value());
            actual.set("response",response.getBody());actual.set("errorCode",response.getBody().path("errorCode").isMissingNode()?json.nullNode():response.getBody().get("errorCode"));actual.set("state",state);
            failureStage="ASSERTION_COMPARISON";var mismatches=stage("execution.assertions",()->comparator.compare(expected,actual));report.set("mismatches",mismatches);report.put("result",mismatches.isEmpty()?"PASS":"FAIL");
        } catch(RuntimeException error) {
            String code=failureStage.equals("FIXTURE_INITIALIZATION")?"FIXTURE_INITIALIZATION_ERROR":"DUMMY_EXECUTION_ERROR";
            report.put("result","ERROR");report.putObject("actual").put("errorCode",code);report.putArray("mismatches");
            report.put("errorCode",code).put("errorStage",failureStage);
            if(!report.has("expected")){report.set("expected",json.createObjectNode().set("assertions",tc.at("/expectedResult/assertions")));report.putNull("fixtureBefore");}
        }
        report.put("durationMs",Math.max(0,(System.nanoTime()-start)/1_000_000));
        jdbc.sql("INSERT INTO app.test_execution(execution_id,test_case_id,requirement_id,executed_at,result_json) VALUES (:execution,:tc,:requirement,:at,CAST(:result AS jsonb))")
            .param("execution",execution).param("tc",id).param("requirement",UUID.fromString(tc.path("requirementId").asText()))
            .param("at",OffsetDateTime.ofInstant(now,ZoneOffset.UTC)).param("result",report.toString()).update();
        return report;
    }
    public JsonNode get(UUID id){return jdbc.sql("SELECT result_json::text FROM app.test_execution WHERE execution_id=:id").param("id",id).query((rs,n)->parse(rs.getString(1))).optional()
        .orElseThrow(()->new TestCaseException(404,"EXECUTION_NOT_FOUND","실행 결과가 없습니다."));}
    public List<JsonNode> history(UUID id){
        var rows=jdbc.sql("SELECT result_json::text FROM app.test_execution WHERE test_case_id=:id ORDER BY executed_at DESC,execution_id").param("id",id).query((rs,n)->parse(rs.getString(1))).list();
        if(rows.isEmpty())find(id,false);return rows;
    }
}
