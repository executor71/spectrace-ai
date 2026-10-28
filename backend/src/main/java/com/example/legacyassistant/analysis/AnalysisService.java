package com.example.legacyassistant.analysis;

import com.example.legacyassistant.requirement.RequirementService;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.UUID;
import org.springframework.stereotype.Service;

@Service
public class AnalysisService {
    private final com.example.legacyassistant.jobs.AnalysisGate gate;
    private final RequirementService requirements;
    private final AnalysisClient client;
    private final AnalysisValidator validator;
    private final AnalysisRepository repository;
    public AnalysisService(RequirementService requirements, AnalysisClient client, AnalysisValidator validator, AnalysisRepository repository, com.example.legacyassistant.jobs.AnalysisGate gate) {
        this.gate=gate; this.requirements=requirements; this.client=client; this.validator=validator; this.repository=repository;
    }
    // No business transaction is held during inference; a dedicated session lock excludes async workers.
    public JsonNode create(UUID id) {
        var requirement = requirements.get(id);
        try(var lease=gate.tryAcquire()){
        if(lease==null)throw new AnalysisException(429,"ANALYSIS_BUSY","다른 분석이 진행 중입니다. Job 대기열을 이용하거나 나중에 다시 요청해 주세요.");
        JsonNode result = client.analyze(requirement);
        com.example.legacyassistant.observability.WorkflowSummary.stage("VALIDATING_OUTPUT");
        validator.validate(id, result);
        if(!lease.valid())throw new AnalysisException(503,"JOB_WORKER_ERROR","분석 소유권이 종료되어 결과를 저장하지 않았습니다.");
        com.example.legacyassistant.observability.WorkflowSummary.stage("SAVING_RESULT");
        repository.save(id, result);
        com.example.legacyassistant.observability.WorkflowSummary.saved();
        return result;
        }
    }
    public JsonNode get(UUID id) {
        requirements.get(id);
        return repository.find(id).orElseThrow(() -> new AnalysisException(404, "ANALYSIS_NOT_FOUND", "저장된 분석 결과가 없습니다."));
    }
}
