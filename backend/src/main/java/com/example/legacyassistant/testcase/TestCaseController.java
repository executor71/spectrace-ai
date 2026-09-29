package com.example.legacyassistant.testcase;

import com.fasterxml.jackson.databind.JsonNode;
import java.util.UUID;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/requirements/{id}/test-cases")
public class TestCaseController {
    private final TestCaseService service;
    public TestCaseController(TestCaseService service) { this.service=service; }
    @PostMapping("/generate") public JsonNode generate(@PathVariable UUID id) { return service.generate(id); }
    @GetMapping public JsonNode get(@PathVariable UUID id) { return service.get(id); }
}
