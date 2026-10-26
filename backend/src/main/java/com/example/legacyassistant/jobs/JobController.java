package com.example.legacyassistant.jobs;
import java.net.URI;
import java.util.*;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
@RestController
public class JobController {
    private final JobStore store;public JobController(JobStore store){this.store=store;}
    @PostMapping("/api/requirements/{id}/analysis-jobs") public ResponseEntity<ObjectNode> create(@PathVariable UUID id){var result=store.create(id);return ResponseEntity.accepted().location(URI.create("/api/analysis-jobs/"+result.path("jobId").asText())).body(result);}
    @GetMapping("/api/analysis-jobs/{id}") public ObjectNode get(@PathVariable UUID id){return store.get(id);}
    @GetMapping("/api/requirements/{id}/analysis-jobs") public List<ObjectNode> list(@PathVariable UUID id){return store.list(id);}
    @GetMapping("/api/analysis-jobs") public ObjectNode summary(@RequestParam(required=false) UUID requirementId){return store.summary(requirementId);}
    @PostMapping("/api/analysis-jobs/{id}/cancel") public ObjectNode cancel(@PathVariable UUID id){return store.cancel(id);}
}
