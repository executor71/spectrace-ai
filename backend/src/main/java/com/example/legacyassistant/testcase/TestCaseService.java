package com.example.legacyassistant.testcase;

import com.example.legacyassistant.analysis.*;
import com.example.legacyassistant.requirement.RequirementService;
import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.time.Instant;
import java.util.UUID;
import org.springframework.stereotype.Service;

@Service
public class TestCaseService {
    private final RequirementService requirements; private final AnalysisService analyses; private final AnalysisValidator analysisValidator;
    private final TestCaseClient client; private final TestCasePolicy policy; private final TestCaseRepository repository; private final ObjectMapper json;
    public TestCaseService(RequirementService requirements,AnalysisService analyses,AnalysisValidator analysisValidator,TestCaseClient client,
            TestCasePolicy policy,TestCaseRepository repository,ObjectMapper json) {
        this.requirements=requirements;this.analyses=analyses;this.analysisValidator=analysisValidator;this.client=client;this.policy=policy;this.repository=repository;this.json=json;
    }
    public JsonNode generate(UUID id) {
        var requirement=requirements.get(id);JsonNode source;
        try { source=analyses.get(id); }
        catch(AnalysisException e) { if(e.status()==404) throw new TestCaseException(409,"ANALYSIS_REQUIRED","먼저 요구사항 분석을 저장해 주세요.");throw e; }
        analysisValidator.validate(id,source);
        long start=System.nanoTime();var response=client.generate(requirement,source);policy.validate(id,source,response);
        ObjectNode result=response.deepCopy();result.put("requirementId",id.toString());result.put("generationId",UUID.randomUUID().toString());
        result.put("createdAt",Instant.now().toString());result.put("generationLatencyMs",(System.nanoTime()-start)/1_000_000);
        result.set("sourceAnalysis",source);result.put("stale",false);
        repository.save(id,source,result);decorate(result);return result;
    }
    public JsonNode get(UUID id) {
        requirements.get(id);
        ObjectNode result=(ObjectNode)repository.find(id).orElseThrow(() -> new TestCaseException(404,"TEST_CASES_NOT_FOUND","저장된 테스트가 없습니다."));
        if(!result.path("policyHash").asText().equals(policy.hash)) result.put("stale",true);
        decorate(result);return result;
    }
    private void decorate(ObjectNode result) {
        policy.describe(result);
        var decisions=result.putArray("executionDecisions");
        boolean stale=result.path("stale").asBoolean();
        for(var item:result.get("testCases")) {
            TestCaseReviewService.decorate((ObjectNode)item,policy,stale);
            var decision=decisions.addObject().put("testCaseId",item.get("testCaseId").asText());
            decision.set("gates",json.valueToTree(policy.gates(item)));decision.put("sourceCurrent",!stale);
            decision.put("reason",stale?"분석 또는 정책이 변경되어 다시 생성해야 합니다.":item.get("executable").asBoolean()?"기술적 실행 조건을 충족합니다. 실행에는 별도 사용자 승인이 필요합니다.":"실행 조건이 충족되지 않았습니다. false인 판정 항목을 확인해 주세요.");
        }
    }
}
