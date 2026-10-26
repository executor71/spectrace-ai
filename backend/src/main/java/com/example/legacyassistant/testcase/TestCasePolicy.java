package com.example.legacyassistant.testcase;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/** Independently re-derives allowed output from the saved analysis, never from model claims. */
@Component
public class TestCasePolicy {
    public static final List<String> TYPES=List.of("NORMAL","EXCEPTION","AUTHORIZATION","BOUNDARY","BUSINESS_RULE");
    private final ObjectMapper json;
    private final JsonNode policy;
    public final String hash;
    public TestCasePolicy(ObjectMapper json, @Value("${TEST_CASE_POLICY:/contracts/test-case-policy.json}") String path) throws Exception {
        this.json=json; byte[] raw=Files.readAllBytes(Path.of(path)); policy=json.readTree(raw); PolicyRegistry.validate(policy,json); hash=digest(raw);
    }
    public static String digest(byte[] bytes) {
        try { return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes)); }
        catch(Exception e) { throw new IllegalStateException(e); }
    }
    public List<String> pending(JsonNode analysis) {
        Set<String> result=new LinkedHashSet<>();
        for(String key:List.of("ambiguousExpressions","missingConditions","clarificationQuestions"))
            analysis.get(key).forEach(v -> result.add(v.asText()));
        if(result.isEmpty() && analysis.get("confirmedConditions").isEmpty()) result.add("확정된 조건이 없어 사용자 확인이 필요합니다.");
        return new ArrayList<>(result);
    }
    public Map<String,ObjectNode> candidates(UUID id, JsonNode analysis) {
        Map<String,ObjectNode> result=new LinkedHashMap<>();
        if(!pending(analysis).isEmpty()) return result;
        Map<String,JsonNode> sources=new LinkedHashMap<>();
        for(var source:analysis.get("evidence"))sources.put(source.get("chunkId").asText(),source);
        for(var plan:policy.get("plans")) {
            JsonNode anchor=null;
            for(var condition:analysis.get("confirmedConditions"))
                if(condition.get("text").equals(plan.get("confirmedCondition"))) { anchor=condition; break; }
            if(anchor==null) continue;
            sources=PolicyRegistry.sources(analysis,policy,plan);
            Map<String,JsonNode> refs=new LinkedHashMap<>();
            String anchorId=anchor.get("chunkId").asText();refs.put(anchorId,sources.get(anchorId));
            boolean supported=true;
            for(var required:plan.get("sources")) {
                JsonNode matched=null;
                for(var source:sources.values()) {
                    boolean matches=source.get("documentType").equals(required.get("documentType"));
                    for(var quote:required.get("quotes")) matches &= source.get("contentSnippet").asText().contains(quote.asText());
                    if(matches) { matched=source;break; }
                }
                if(matched==null) { supported=false;break; }
                refs.put(matched.get("chunkId").asText(),matched);
            }
            if(!supported) continue;
            ObjectNode value=plan.get("case").deepCopy();
            String route=value.at("/input/method").asText()+" "+value.at("/input/endpoint").asText();
            boolean apiSupported=false;
            for(var api:analysis.get("relatedApis")) {
                JsonNode source=sources.get(api.get("chunkId").asText());
                if(api.get("api").asText().equals(route) && source!=null && source.get("contentSnippet").asText().contains(route)) apiSupported=true;
            }
            if(plan.has("coveredConditions"))for(var source:sources.values())if(source.path("documentType").asText().equals("API_SPEC") && source.path("contentSnippet").asText().contains(route))apiSupported=true;
            if(!apiSupported) continue;
            value.put("requirementId",id.toString());
            ArrayNode evidence=value.putArray("evidence");
            refs.values().forEach(s -> evidence.addObject().setAll(Map.of("documentId",s.get("documentId"),"chunkId",s.get("chunkId"))));
            value.put("executable",gates(value).values().stream().allMatch(Boolean::booleanValue));
            result.put(plan.get("id").asText(),value);
        }
        return result;
    }
    /** Additive public metadata; internal model selection and original snapshot remain unchanged. */
    public void describe(ObjectNode result) {
        JsonNode analysis=result.path("sourceAnalysis");
        UUID id=UUID.fromString(analysis.path("requirementId").asText());
        var eligible=candidates(id,analysis);var coverage=result.putArray("conditionCoverage");
        boolean clarification=!pending(analysis).isEmpty() && !analysis.path("confirmedConditions").isEmpty();
        boolean insufficient=analysis.path("confirmedConditions").isEmpty();
        int supported=0;
        for(var condition:analysis.path("confirmedConditions")) {
            var row=coverage.addObject();row.setAll(Map.of("text",condition.path("text"),"chunkId",condition.path("chunkId")));
            List<String> registered=new ArrayList<>(),matched=new ArrayList<>();
            for(var plan:policy.path("plans")) {
                boolean covers=plan.path("confirmedCondition").equals(condition.path("text"));
                for(var text:plan.path("coveredConditions"))covers|=text.equals(condition.path("text"));
                if(covers){registered.add(plan.path("id").asText());if(eligible.containsKey(plan.path("id").asText()))matched.add(plan.path("id").asText());}
            }
            String status=clarification?"CLARIFICATION_REQUIRED":!matched.isEmpty()?"SUPPORTED":registered.isEmpty()?"UNSUPPORTED_TEMPLATE":"INSUFFICIENT_EVIDENCE";
            if(status.equals("SUPPORTED"))supported++;if(status.equals("INSUFFICIENT_EVIDENCE"))insufficient=true;
            row.put("status",status);row.set("templateIds",json.valueToTree(matched));
            var tcIds=row.putArray("testCaseIds");
            for(var tc:result.path("testCases"))for(String planId:matched)if(tc.path("scenario").equals(eligible.get(planId).path("scenario")) && tc.path("expectedResult").equals(eligible.get(planId).path("expectedResult")))tcIds.add(tc.path("testCaseId").asText());
        }
        String status=clarification?"BLOCKED_CLARIFICATION_REQUIRED":result.path("testCases").isEmpty()?(insufficient?"BLOCKED_INSUFFICIENT_EVIDENCE":"BLOCKED_UNSUPPORTED_TEMPLATE"):
            supported<analysis.path("confirmedConditions").size()?"PARTIALLY_GENERATED":"GENERATED";
        result.put("generationStatus",status);
        // Public generation context includes only API specs used by grounded cases. The DB comparison snapshot stays original.
        ObjectNode context=analysis.deepCopy();var evidence=(ArrayNode)context.path("evidence");
        Set<String> present=new HashSet<>(),used=new HashSet<>();evidence.forEach(s->present.add(s.path("chunkId").asText()));
        result.path("testCases").forEach(tc->tc.path("evidence").forEach(ref->used.add(ref.path("chunkId").asText())));
        var added=result.putArray("policyEvidence");
        for(var source:policy.path("apiEvidence"))if(used.contains(source.path("chunkId").asText()) && present.add(source.path("chunkId").asText())) {
            ObjectNode copy=source.deepCopy();copy.remove(List.of("relatedApis","sourceName"));evidence.add(copy);added.add(copy);
        }
        result.set("sourceAnalysis",context);
    }
    public Map<String,Boolean> gates(JsonNode value) {
        var input=value.get("input");
        String route=input.path("method").asText()+" "+input.path("endpoint").asText();
        boolean allowed=false; for(var entry:policy.get("allowList")) if(entry.asText().equals(route)) allowed=true;
        var assertions=value.at("/expectedResult/assertions"); boolean checkable=!assertions.isEmpty();
        Set<String> kinds=new HashSet<>();policy.get("assertionKinds").forEach(k -> kinds.add(k.asText()));
        for(var assertion:assertions) checkable &= kinds.contains(assertion.path("kind").asText());
        Map<String,Boolean> gates=new LinkedHashMap<>();
        gates.put("apiAllowListed",allowed);
        gates.put("methodEndpointKnown",!input.path("method").asText().isBlank() && !input.path("endpoint").asText().isBlank());
        gates.put("preconditionsReproducible",policy.get("fixtureReady").asBoolean() && !input.path("actorFixture").asText().isBlank());
        gates.put("inputDefined",!input.path("pathParameters").isEmpty() && input.has("body"));
        gates.put("expectedResultCheckable",checkable);
        return gates;
    }
    public List<String> clarification(JsonNode analysis, Map<String,ObjectNode> candidates) {
        var pending=pending(analysis);
        if(pending.isEmpty() && candidates.isEmpty()) {
            boolean known=false;
            for(var condition:analysis.path("confirmedConditions"))for(var plan:policy.path("plans")) {
                known|=plan.path("confirmedCondition").equals(condition.path("text"));
                for(var covered:plan.path("coveredConditions"))known|=covered.equals(condition.path("text"));
            }
            pending.add(known?"테스트에 필요한 업무규칙 또는 API 근거가 부족합니다.":"확정 조건을 지원하는 근거 검증 테스트 템플릿이 없습니다. 테스트 절차와 판정 기준을 확인해 주세요.");
        }
        return pending;
    }
    public void validate(UUID id, JsonNode analysis, JsonNode response) {
        try {
            Set<String> fields=new HashSet<>();response.fieldNames().forEachRemaining(fields::add);
            check(fields.equals(Set.of("testCases","clarificationRequired","uncoveredTypes","policyHash","llmCalls")));
            check(response.get("policyHash").asText().equals(hash));
            var expected=candidates(id,analysis);
            check(response.get("testCases").isArray() && response.get("testCases").size()==expected.size());
            check(response.get("clarificationRequired").equals(json.valueToTree(clarification(analysis,expected))));
            Set<String> ids=new HashSet<>(), matched=new HashSet<>(), types=new HashSet<>();
            for(var item:response.get("testCases")) {
                check(item.isObject() && item.path("testCaseId").isTextual());
                check(ids.add(UUID.fromString(item.get("testCaseId").asText()).toString()));
                ObjectNode body=item.deepCopy();body.remove("testCaseId");String match=null;
                for(var entry:expected.entrySet()) if(entry.getValue().equals(body)) { match=entry.getKey();break; }
                check(match!=null && matched.add(match));types.add(item.get("type").asText());
            }
            check(response.get("uncoveredTypes").equals(json.valueToTree(TYPES.stream().filter(t -> !types.contains(t)).toList())));
            var calls=response.get("llmCalls");check(calls.isIntegralNumber() && calls.asInt()>=(expected.isEmpty()?0:1) && calls.asInt()<=(expected.isEmpty()?0:2));
        } catch(RuntimeException e) { throw new TestCaseException(502,"INVALID_TEST_CASE_OUTPUT","테스트의 형식, 근거 또는 실행 가능성 검증에 실패하여 저장하지 않았습니다."); }
    }
    private static void check(boolean value) { if(!value) throw new IllegalArgumentException("Invalid generated test case"); }
}
