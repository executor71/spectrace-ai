package com.example.legacyassistant.testcase;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import java.util.*;
import org.springframework.stereotype.Component;

/** Exact typed comparisons; unsupported assertions fail closed before dispatch. */
@Component
public class ExecutionComparator {
    private final ObjectMapper json;
    public ExecutionComparator(ObjectMapper json){this.json=json;}
    public boolean checkable(JsonNode assertions) {
        if(!assertions.isArray() || assertions.isEmpty() || assertions.size()>100)return false;
        boolean http=false;Set<String> seen=new HashSet<>();
        for(var a:assertions) {
            var fields=new HashSet<String>();a.fieldNames().forEachRemaining(fields::add);
            String kind=a.path("kind").asText(),field=a.path("field").asText();
            Set<String> required=switch(kind){case "HTTP_STATUS","RESPONSE_TOKEN"->Set.of("kind","value");case "UNCHANGED"->Set.of("kind","field");default->Set.of("kind","field","value");};
            if(!fields.equals(required))return false;
            String target=switch(kind){case "HTTP_STATUS"->"httpStatus";case "RESPONSE_TOKEN"->"errorCode";case "OBSERVATION_EQUALS","UNCHANGED"->"state."+field;default->"response."+field;};
            if(!seen.add(target))return false;
            switch(kind) {
                case "HTTP_STATUS" -> {if(!a.path("value").isInt() || a.path("value").asInt()<100 || a.path("value").asInt()>599)return false;http=true;}
                case "RESPONSE_TOKEN" -> {if(!a.path("value").isTextual() || a.path("value").asText().isBlank())return false;}
                case "OBSERVATION_EQUALS","UNCHANGED" -> {if(!Set.of("loanStatus","assetStatus","returnStatus","returnCount","inspectionCompleted").contains(field))return false;
                    if(kind.equals("OBSERVATION_EQUALS")){var value=a.path("value");if(field.equals("returnCount")?(!value.isInt()||value.asInt()<0):field.equals("inspectionCompleted")?!value.isBoolean():!value.isTextual())return false;}}
                case "RESPONSE_FIELD" -> {if(!Set.of("status","assetId","currentLoan","errorCode","returnId").contains(field) || !a.has("value") || a.get("value").isContainerNode())return false;}
                default -> {return false;}
            }
        }
        return http;
    }
    public ObjectNode expected(JsonNode assertions,JsonNode before) {
        ObjectNode expected=json.createObjectNode();
        for(var a:assertions) {
            String kind=a.path("kind").asText(),field=a.path("field").asText();
            switch(kind) {
                case "HTTP_STATUS" -> expected.set("httpStatus",a.get("value"));
                case "RESPONSE_TOKEN" -> expected.set("errorCode",a.get("value"));
                case "RESPONSE_FIELD" -> expected.withObject("/response").set(field,a.get("value"));
                case "OBSERVATION_EQUALS" -> expected.withObject("/state").set(field,a.get("value"));
                case "UNCHANGED" -> expected.withObject("/state").set(field,before.path(field));
                default -> throw new IllegalArgumentException("Unsupported assertion");
            }
        }
        return expected;
    }
    public ArrayNode compare(JsonNode expected,JsonNode actual) {
        ArrayNode result=json.createArrayNode();compare("",expected,actual,result);return result;
    }
    private void compare(String prefix,JsonNode expected,JsonNode actual,ArrayNode mismatches) {
        expected.fields().forEachRemaining(entry->{
            String field=prefix+entry.getKey();JsonNode value=actual.path(entry.getKey());
            if(entry.getValue().isObject())compare(field+".",entry.getValue(),value,mismatches);
            else if(!entry.getValue().equals(value)) {
                var mismatch=mismatches.addObject().put("field",field);mismatch.set("expected",entry.getValue());
                mismatch.set("actual",value.isMissingNode()?json.nullNode():value);
                if(value.isMissingNode())mismatch.put("actualMissing",true);
            }
        });
    }
}
