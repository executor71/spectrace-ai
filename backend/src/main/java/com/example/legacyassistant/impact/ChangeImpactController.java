package com.example.legacyassistant.impact;
import com.example.legacyassistant.jobs.JobStore;
import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.web.bind.annotation.*;
import org.springframework.http.*;
import java.util.*;

@RestController @RequestMapping("/api/change-impacts")
public class ChangeImpactController {
 private final ChangeImpactService service;private final JobStore jobs;private final ImpactExport export;
 public ChangeImpactController(ChangeImpactService service,JobStore jobs,ImpactExport export){this.service=service;this.jobs=jobs;this.export=export;}
 public record Proposal(UUID baselineRequirementId,String baselineRevision,String proposalTitle,String proposalContent){}
 @GetMapping("/baselines/{id}") public JsonNode baseline(@PathVariable UUID id){return service.baseline(id);}
 @PostMapping public JsonNode create(@RequestBody Proposal input){if(input.baselineRequirementId()==null)throw ChangeImpactService.error(422,"BASELINE_REQUIRED");return service.create(input.baselineRequirementId(),input.baselineRevision(),input.proposalTitle(),input.proposalContent());}
 @GetMapping public List<?> list(){return service.list();}
 @GetMapping("/{id}") public JsonNode get(@PathVariable UUID id){return service.get(id);}
 @PostMapping("/{id}/analysis-jobs") public ResponseEntity<?> analyze(@PathVariable UUID id){return ResponseEntity.accepted().body(jobs.createImpact(id));}
 @GetMapping("/{id}/analysis-jobs") public List<?> jobs(@PathVariable UUID id){return jobs.listImpact(id);}
 @GetMapping("/{id}/results") public JsonNode result(@PathVariable UUID id){return service.result(id);}
 @GetMapping("/{id}/reviews") public List<?> reviews(@PathVariable UUID id){return service.reviews(id);}
 @PostMapping("/{id}/reviews") public JsonNode review(@PathVariable UUID id,@RequestBody JsonNode value){if(!value.isObject())throw ChangeImpactService.error(422,"REVIEW_INVALID");return service.review(id,value);}
 @GetMapping("/{id}/export") public ResponseEntity<byte[]> export(@PathVariable UUID id){return ResponseEntity.ok().contentType(MediaType.parseMediaType("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")).header("Content-Disposition","attachment; filename=change-impact-"+id+".xlsx").body(export.export(id));}
}
