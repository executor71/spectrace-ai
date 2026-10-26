package com.example.legacyassistant.testcase;

import com.fasterxml.jackson.databind.*;
import java.nio.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;

/** Fail-closed, read-only validation of the synthetic policy registry. */
final class PolicyRegistry {
    private static final UUID NAMESPACE=UUID.fromString("55a34fc8-9a8e-4a01-8f23-c82a21d00002");
    static UUID uuid5(UUID namespace,String name) throws Exception {
        var digest=MessageDigest.getInstance("SHA-1");
        digest.update(ByteBuffer.allocate(16).putLong(namespace.getMostSignificantBits()).putLong(namespace.getLeastSignificantBits()).array());
        byte[] bytes=digest.digest(name.getBytes(StandardCharsets.UTF_8));bytes[6]=(byte)((bytes[6]&15)|80);bytes[8]=(byte)((bytes[8]&63)|128);
        var buffer=ByteBuffer.wrap(bytes);return new UUID(buffer.getLong(),buffer.getLong());
    }
    static void validate(JsonNode policy,ObjectMapper json) throws Exception {
        require(policy.path("plans").isArray() && policy.path("plans").size()<=30 && policy.path("fixtureReady").isBoolean(),"Invalid policy schema");
        Set<String> ids=new HashSet<>(), evidenceIds=new HashSet<>();
        Map<String,String> corpus=new HashMap<>();
        Map<String,JsonNode> documents=new HashMap<>();
        Path root=Path.of(System.getenv().getOrDefault("KNOWLEDGE_ROOT","/knowledge")).toRealPath();
        var manifest=json.readTree(Files.readAllBytes(root.resolve("manifest.json")));
        require(manifest.path("synthetic").asBoolean(),"Synthetic corpus required");
        for(var document:manifest.path("documents")) {
            Path file=root.resolve(document.path("sourceName").asText()).normalize();
            require(file.toRealPath().startsWith(root.resolve("documents").toRealPath()),"Invalid corpus path");
            documents.put(document.path("sourceName").asText(),document);
            corpus.put(document.path("sourceName").asText(),Files.readString(file).replace("\r\n","\n"));
        }
        for(var source:policy.path("apiEvidence")) {
            String id=source.path("chunkId").asText(), name=source.path("sourceName").asText(), heading=source.path("section").asText();
            require(evidenceIds.add(id),"Duplicate policy evidence ID");
            var document=documents.get(name);
            require(document!=null && document.path("documentType").asText().equals("API_SPEC") && source.path("documentType").asText().equals("API_SPEC"),"Invalid API evidence source");
            UUID documentId=uuid5(NAMESPACE,document.path("key").asText()+":"+document.path("version").asText());
            require(source.path("documentId").asText().equals(documentId.toString()) && id.equals(uuid5(documentId,heading).toString()),"Invalid evidence identity");
            String marker="## "+heading+"\n", markdown=corpus.get(name);int start=markdown.indexOf(marker);
            require(start>=0,"Unknown evidence section");start+=marker.length();int end=markdown.indexOf("\n## ",start);
            String content=markdown.substring(start,end<0?markdown.length():end).strip();
            require(content.equals(source.path("contentSnippet").asText()) && document.path("sections").path(heading).equals(source.path("relatedApis")),"Evidence differs from canonical corpus");
        }
        for(var plan:policy.path("plans")) {
            require(plan.path("id").isTextual() && !plan.path("id").asText().isBlank() && ids.add(plan.path("id").asText()),"Empty or duplicate template ID");
            require(!plan.path("confirmedCondition").asText().isBlank() && plan.path("sources").isArray() && !plan.path("sources").isEmpty(),"Template grounding required");
            var value=plan.path("case");TestCaseReviewService.validateContent(value);
            require(TestCasePolicy.TYPES.contains(value.path("type").asText()) && value.path("evidence").isMissingNode() && !value.path("expectedResult").path("assertions").isEmpty(),"Invalid template schema");
            for(var assertion:value.path("expectedResult").path("assertions")) {
                boolean known=false;for(var kind:policy.path("assertionKinds"))known|=kind.equals(assertion.path("kind"));
                require(known,"Unknown assertion kind");
            }
            List<String> quotes=new ArrayList<>();
            for(var source:plan.path("sources")) {
                require(source.path("quotes").isArray() && !source.path("quotes").isEmpty(),"Source quotes required");
                for(var quote:source.path("quotes")){require(quote.isTextual() && !quote.asText().isBlank(),"Empty quote");quotes.add(quote.asText());}
            }
            if(plan.has("coveredConditions")) {
                require(quotes.contains(plan.path("confirmedCondition").asText()),"Template anchor must quote source");
                for(var required:plan.path("sources")) {
                    boolean grounded=false;
                    for(var entry:documents.entrySet())if(entry.getValue().path("documentType").equals(required.path("documentType"))) {
                        boolean matches=true;for(var quote:required.path("quotes"))matches&=corpus.get(entry.getKey()).contains(quote.asText());
                        grounded|=matches;
                    }
                    require(grounded,"Template quotes missing from declared corpus type");
                }
                String route=value.path("input").path("method").asText()+" "+value.path("input").path("endpoint").asText();
                boolean api=false;for(var source:policy.path("apiEvidence"))for(var related:source.path("relatedApis"))api|=related.asText().equals(route) && source.path("contentSnippet").asText().contains(route);
                require(api,"Template API absent from public specification");
                for(var condition:plan.path("coveredConditions"))require(quotes.contains(condition.asText()) && corpus.values().stream().anyMatch(text->text.contains(condition.asText())),"Unknown covered condition");
                require(quotes.contains(value.path("expectedResult").path("description").asText()),"Expected result must quote source");
                for(var assertion:value.path("expectedResult").path("assertions")) {
                    String kind=assertion.path("kind").asText(), expected=assertion.path("value").asText();
                    if(kind.equals("HTTP_STATUS"))require(quotes.stream().anyMatch(q->q.contains("HTTP "+expected)),"HTTP assertion lacks source");
                    if(Set.of("RESPONSE_TOKEN","OBSERVATION_EQUALS").contains(kind))require(quotes.stream().anyMatch(q->q.contains(expected)),"Expected value lacks source");
                    if(kind.equals("UNCHANGED"))require(quotes.stream().anyMatch(q->q.contains("변경하지 않는다")),"State preservation lacks source");
                }
            }
        }
    }
    static Map<String,JsonNode> sources(JsonNode analysis,JsonNode policy,JsonNode plan) {
        Map<String,JsonNode> sources=new LinkedHashMap<>();analysis.path("evidence").forEach(s->sources.put(s.path("chunkId").asText(),s));
        if(!plan.has("coveredConditions"))return sources;
        String route=plan.at("/case/input/method").asText()+" "+plan.at("/case/input/endpoint").asText();
        boolean referenced=false;for(var api:analysis.path("relatedApis"))referenced|=api.path("api").asText().equals(route);
        if(referenced)for(var source:policy.path("apiEvidence"))for(var related:source.path("relatedApis"))if(related.asText().equals(route) && source.path("contentSnippet").asText().contains(route)) {
            com.fasterxml.jackson.databind.node.ObjectNode copy=source.deepCopy();copy.remove(List.of("relatedApis","sourceName"));sources.putIfAbsent(source.path("chunkId").asText(),copy);
        }
        return sources;
    }
    private static void require(boolean valid,String message){if(!valid)throw new IllegalArgumentException(message);}
}
