package com.example.legacyassistant.testcase;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import java.util.*;
import org.springframework.http.ResponseEntity;

/** Closed synthetic return contracts. No HTTP client or business database access. */
final class ReturnExecutionAdapter {
    static final String VERSION="return-execution-v1";
    static final String RETURN="00000000-0000-4000-8000-000000000201";
    static final Set<String> SUPPORTED=Set.of("return-normal","return-duplicate","return-authorization","return-inspection-pending","inspection-damage-required");
    record ReturnRequest(boolean accessoriesReturned,String note) {}
    record ReturnResponse(String returnId,String status) {}
    record InspectionRequest(String result,String damageDescription,List<String> photoReferences) {}
    record ErrorResponse(String errorCode) {}
    private final ObjectMapper json;
    ReturnExecutionAdapter(ObjectMapper json){this.json=json;}
    static boolean route(JsonNode input){return Set.of("/loans/{loanId}/returns","/returns/{returnId}/inspection").contains(input.path("endpoint").asText());}
    List<String> modes(String plan){
        return switch(plan){case "return-normal","return-inspection-pending"->List.of("standard","asset-admin","intentional-defect","fixture-error");
            case "return-duplicate"->List.of("standard","completed-return");default->SUPPORTED.contains(plan)?List.of("standard"):List.of();};
    }
    ObjectNode setup(JsonNode tc,String plan,String mode){
        if(!modes(plan).contains(mode))throw new TestCaseException(409,"EXECUTION_CONTRACT_UNSUPPORTED","이 템플릿과 Fixture 조합은 자동 실행 계약을 지원하지 않습니다.");
        JsonNode original=tc.has("generatedContent")?tc.path("generatedContent"):tc;
        ObjectNode input=original.path("input").deepCopy();
        String actor=plan.equals("return-authorization")?"return-other":plan.startsWith("inspection")||mode.equals("asset-admin")?"asset-admin":"current-borrower";
        input.put("actorFixture",actor).put("fixtureProfile",mode).put("executionContractVersion",VERSION).put("returnTemplateId",plan);
        input.putObject("pathParameters").put(plan.startsWith("inspection")?"returnId":"loanId",plan.startsWith("inspection")?RETURN:DummyApiRegistry.LOAN);
        var pre=json.createArrayNode().add("Isolated synthetic return fixture: "+plan).add("Fixture profile: "+mode).add("Actor: "+actor).add("Execution contract: "+VERSION);
        ObjectNode expected=json.createObjectNode();expected.set("description",original.path("expectedResult").path("description"));
        var assertions=expected.putArray("assertions");
        int status=plan.equals("return-duplicate")?409:plan.equals("return-authorization")?403:plan.startsWith("inspection")?400:201;
        assertions.addObject().put("kind","HTTP_STATUS").put("value",status);
        if(status!=201){assertions.addObject().put("kind","RESPONSE_TOKEN").put("value",status==409?"RETURN_ALREADY_REQUESTED":status==403?"ACCESS_DENIED":"VALIDATION_ERROR");
            for(String field:List.of("loanStatus","assetStatus","returnStatus","returnCount","inspectionCompleted"))assertions.addObject().put("kind","UNCHANGED").put("field",field);
        }else{
            assertions.addObject().put("kind","RESPONSE_FIELD").put("field","status").put("value","INSPECTION_PENDING");
            assertions.addObject().put("kind","RESPONSE_FIELD").put("field","returnId").put("value",RETURN);
            assertions.addObject().put("kind","OBSERVATION_EQUALS").put("field","returnStatus").put("value","INSPECTION_PENDING");
            assertions.addObject().put("kind","OBSERVATION_EQUALS").put("field","returnCount").put("value",1);
            assertions.addObject().put("kind","OBSERVATION_EQUALS").put("field","inspectionCompleted").put("value",false);
            assertions.addObject().put("kind","UNCHANGED").put("field","assetStatus");
        }
        ObjectNode edit=json.createObjectNode();edit.set("input",input);edit.set("preconditions",pre);edit.set("expectedResult",expected);return edit;
    }
    boolean matches(JsonNode tc,String plan){
        if(plan==null||!SUPPORTED.contains(plan))return false;
        try{var expected=setup(tc,plan,tc.at("/input/fixtureProfile").asText());
            return List.of("input","preconditions","expectedResult").stream().allMatch(key->expected.get(key).equals(tc.path(key)));
        }catch(RuntimeException invalid){return false;}
    }
    boolean inputValid(JsonNode input){
        if(!input.path("executionContractVersion").asText().equals(VERSION)||!SUPPORTED.contains(input.path("returnTemplateId").asText()))return false;
        var body=input.path("body");
        if(input.path("endpoint").asText().endsWith("/returns"))return body.path("accessoriesReturned").isBoolean() && (!body.has("note")||body.path("note").isTextual() && body.path("note").asText().length()<=2000);
        if(!body.path("result").isTextual()||!Set.of("PASSED","DAMAGED").contains(body.path("result").asText()))return false;
        if(body.has("damageDescription")&&(!body.path("damageDescription").isTextual()||body.path("damageDescription").asText().length()>2000))return false;
        if(body.has("photoReferences")){if(!body.path("photoReferences").isArray()||body.path("photoReferences").size()>20)return false;
            for(var photo:body.path("photoReferences"))if(!photo.isTextual()||photo.asText().length()>2000)return false;}
        return true;
    }
    ObjectNode prepare(JsonNode tc){
        String profile=tc.at("/input/fixtureProfile").asText(),plan=tc.at("/input/returnTemplateId").asText();
        if(profile.equals("fixture-error"))throw new IllegalStateException("Synthetic fixture initialization failure");
        boolean exists=plan.equals("return-duplicate")||plan.startsWith("inspection"),complete=profile.equals("completed-return");
        return json.createObjectNode().put("loanStatus","ACTIVE").put("assetStatus",complete?"AVAILABLE":"ON_LOAN")
            .put("returnStatus",exists?"INSPECTION_PENDING":"NONE").put("returnCount",exists?1:0).put("inspectionCompleted",complete);
    }
    ResponseEntity<JsonNode> invoke(JsonNode input,ObjectNode state){
        String actor=input.path("actorFixture").asText();var body=input.path("body");
        if(input.path("endpoint").asText().endsWith("/inspection")){
            // Only the fully specified validation-error contract is executable.
            InspectionRequest request=json.convertValue(body,InspectionRequest.class);
            if(!actor.equals("asset-admin"))throw new IllegalStateException("Unsupported inspection actor");
            if(request.result().equals("DAMAGED")&&(request.damageDescription()==null||request.damageDescription().isBlank()||request.photoReferences()==null||request.photoReferences().isEmpty()))return error(400,"VALIDATION_ERROR");
            throw new IllegalStateException("Successful inspection HTTP contract is unspecified");
        }
        ReturnRequest request=json.convertValue(body,ReturnRequest.class);
        if(!Set.of("current-borrower","asset-admin").contains(actor))return error(403,"ACCESS_DENIED");
        if(state.path("returnCount").asInt()>0)return error(409,"RETURN_ALREADY_REQUESTED");
        state.put("returnCount",1).put("returnStatus","INSPECTION_PENDING");
        if(input.path("fixtureProfile").asText().equals("intentional-defect"))state.put("assetStatus","AVAILABLE");
        // request DTO is validated before dispatch. It never contains role/fixture overrides.
        if(request.note()!=null && request.note().length()>2000)throw new IllegalArgumentException("Invalid note");
        return ResponseEntity.status(201).body(json.valueToTree(new ReturnResponse(RETURN,"INSPECTION_PENDING")));
    }
    private ResponseEntity<JsonNode> error(int status,String code){return ResponseEntity.status(status).body(json.valueToTree(new ErrorResponse(code)));}
}
