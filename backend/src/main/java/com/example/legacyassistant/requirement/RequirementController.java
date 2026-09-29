package com.example.legacyassistant.requirement;

import jakarta.validation.Valid;
import java.net.URI;
import java.util.UUID;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/requirements")
public class RequirementController {
    private final RequirementService service;

    public RequirementController(RequirementService service) { this.service = service; }

    @PostMapping
    public ResponseEntity<Requirement> create(@Valid @RequestBody CreateRequirementRequest request) {
        Requirement result = service.create(request);
        return ResponseEntity.created(URI.create("/api/requirements/" + result.id())).body(result);
    }

    @GetMapping("/{id}")
    public Requirement get(@PathVariable UUID id) { return service.get(id); }
}
