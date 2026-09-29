package com.example.legacyassistant.analysis;

import com.fasterxml.jackson.databind.JsonNode;
import java.util.UUID;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/requirements/{id}/analysis")
public class AnalysisController {
    private final AnalysisService service;
    public AnalysisController(AnalysisService service) { this.service=service; }
    @PostMapping public JsonNode create(@PathVariable UUID id) { return service.create(id); }
    @GetMapping public JsonNode get(@PathVariable UUID id) { return service.get(id); }
}
