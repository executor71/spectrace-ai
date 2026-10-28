package com.example.legacyassistant.testcase;

import com.fasterxml.jackson.databind.JsonNode;
import java.util.UUID;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/test-cases")
public class TestCaseReviewController {
    private final TestCaseReviewService reviews;
    public TestCaseReviewController(TestCaseReviewService reviews){this.reviews=reviews;}
    @PatchMapping("/{id}") public JsonNode edit(@PathVariable UUID id,@RequestBody JsonNode body){return reviews.edit(id,body);}
    @PostMapping("/{id}/approve") public JsonNode approve(@PathVariable UUID id,@RequestBody JsonNode body){return reviews.decide(id,body,true);}
    @PostMapping("/{id}/reject") public JsonNode reject(@PathVariable UUID id,@RequestBody JsonNode body){return reviews.decide(id,body,false);}
    @PostMapping("/{id}/return-execution-setup") public JsonNode prepareReturn(@PathVariable UUID id,@RequestBody JsonNode body){return reviews.prepareReturn(id,body);}
}
