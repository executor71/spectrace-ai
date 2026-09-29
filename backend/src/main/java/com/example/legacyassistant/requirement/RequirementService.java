package com.example.legacyassistant.requirement;

import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class RequirementService {
    private final RequirementRepository repository;

    public RequirementService(RequirementRepository repository) { this.repository = repository; }

    @Transactional
    public Requirement create(CreateRequirementRequest request) {
        return repository.insert(UUID.randomUUID(), request.title(), request.description());
    }

    @Transactional(readOnly = true)
    public Requirement get(UUID id) {
        return repository.findById(id).orElseThrow(RequirementNotFoundException::new);
    }
}
