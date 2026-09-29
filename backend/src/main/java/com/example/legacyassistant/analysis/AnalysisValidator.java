package com.example.legacyassistant.analysis;

import com.fasterxml.jackson.databind.JsonNode;
import java.util.*;
import org.springframework.stereotype.Component;

@Component
public class AnalysisValidator {
    private static final Set<String> FIELDS = Set.of("requirementId", "confirmedConditions", "ambiguousExpressions",
        "missingConditions", "relatedBusinessRules", "relatedApis", "clarificationQuestions", "evidence");

    public void validate(UUID id, JsonNode result) {
        try {
            check(result != null && result.isObject());
            Set<String> keys = new HashSet<>(); result.fieldNames().forEachRemaining(keys::add);
            check(keys.equals(FIELDS));
            check(result.get("requirementId").isTextual() && id.toString().equals(result.get("requirementId").asText()));
            for (String key : FIELDS) if (!key.equals("requirementId")) check(result.get(key).isArray() && result.get(key).size() <= 12);
            Map<String, JsonNode> evidence = new HashMap<>();
            check(result.get("evidence").size() <= 5);
            for (var item : result.get("evidence")) {
                exactFields(item, Set.of("documentId", "chunkId", "documentType", "section", "contentSnippet", "score"));
                for (String key : List.of("documentId", "chunkId", "documentType", "section", "contentSnippet")) text(item.get(key));
                UUID.fromString(item.get("documentId").asText()); UUID.fromString(item.get("chunkId").asText());
                check(item.get("score").isNumber() && Double.isFinite(item.get("score").asDouble()) && Math.abs(item.get("score").asDouble()) <= 1.001);
                check(evidence.put(item.get("chunkId").asText(), item) == null);
            }
            for (String key : List.of("confirmedConditions", "relatedBusinessRules")) {
                for (var item : result.get(key)) {
                    exactFields(item, Set.of("text", "chunkId")); text(item.get("text")); text(item.get("chunkId"));
                    var source = evidence.get(item.get("chunkId").asText());
                    check(source != null && source.get("contentSnippet").asText().contains(item.get("text").asText()));
                    if (key.equals("relatedBusinessRules")) check(source.get("documentType").asText().equals("BUSINESS_RULE"));
                }
            }
            for (var item : result.get("relatedApis")) {
                exactFields(item, Set.of("api", "chunkId")); text(item.get("api")); text(item.get("chunkId"));
                check(evidence.containsKey(item.get("chunkId").asText()));
                // The AI service additionally checks the exact trusted relatedApis metadata.
            }
            for (String key : List.of("ambiguousExpressions", "missingConditions", "clarificationQuestions"))
                for (var item : result.get(key)) text(item);
            if (result.get("confirmedConditions").isEmpty()) check(!result.get("missingConditions").isEmpty());
            if (!result.get("missingConditions").isEmpty() || !result.get("ambiguousExpressions").isEmpty()) check(!result.get("clarificationQuestions").isEmpty());
        } catch (RuntimeException e) {
            throw new AnalysisException(502, "INVALID_ANALYSIS_OUTPUT", "분석 결과의 형식 또는 근거가 올바르지 않아 저장하지 않았습니다.");
        }
    }
    private static void exactFields(JsonNode node, Set<String> expected) {
        check(node.isObject()); Set<String> keys = new HashSet<>(); node.fieldNames().forEachRemaining(keys::add); check(keys.equals(expected));
    }
    private static void text(JsonNode node) { check(node != null && node.isTextual() && !node.asText().isBlank() && node.asText().length() <= 2000); }
    private static void check(boolean valid) { if (!valid) throw new IllegalArgumentException("Invalid analysis"); }
}
