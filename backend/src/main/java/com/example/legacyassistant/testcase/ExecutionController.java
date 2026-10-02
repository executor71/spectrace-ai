package com.example.legacyassistant.testcase;

import com.fasterxml.jackson.databind.JsonNode;
import java.util.*;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;

@RestController
public class ExecutionController {
    private final ExecutionService service;
    public ExecutionController(ExecutionService service){this.service=service;}
    @PostMapping("/api/test-cases/{id}/executions")
    public ResponseEntity<JsonNode> execute(@PathVariable UUID id,@RequestBody(required=false) JsonNode body){
        if(body!=null)throw new TestCaseException(400,"EXECUTION_INPUT_NOT_ALLOWED","실행 요청은 저장된 승인 TC만 사용하며 요청 본문을 받지 않습니다.");
        return ResponseEntity.status(201).body(service.execute(id));
    }
    @GetMapping("/api/test-cases/{id}/executions") public List<JsonNode> history(@PathVariable UUID id){return service.history(id);}
    @GetMapping("/api/test-cases/{id}/execution-eligibility") public JsonNode eligibility(@PathVariable UUID id){return service.eligibility(id);}
    @GetMapping("/api/executions/{id}") public JsonNode get(@PathVariable UUID id){return service.get(id);}
}
