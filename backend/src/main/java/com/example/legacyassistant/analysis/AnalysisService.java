package com.example.legacyassistant.analysis;

import com.example.legacyassistant.requirement.RequirementService;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.UUID;
import org.springframework.stereotype.Service;

@Service
public class AnalysisService {
    private final RequirementService requirements;
    private final AnalysisClient client;
    private final AnalysisValidator validator;
    private final AnalysisRepository repository;
    public AnalysisService(RequirementService requirements, AnalysisClient client, AnalysisValidator validator, AnalysisRepository repository) {
        this.requirements=requirements; this.client=client; this.validator=validator; this.repository=repository;
    }
    // No database transaction/connection is held while the local model runs.
    public JsonNode create(UUID id) {
        var requirement = requirements.get(id);
        JsonNode result = client.analyze(requirement);
        validator.validate(id, result);
        repository.save(id, result);
        return result;
    }
    public JsonNode get(UUID id) {
        requirements.get(id);
        return repository.find(id).orElseThrow(() -> new AnalysisException(404, "ANALYSIS_NOT_FOUND", "저장된 분석 결과가 없습니다."));
    }
}
