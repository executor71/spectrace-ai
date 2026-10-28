package com.example.legacyassistant.testcase;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import java.util.*;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;

/** Closed in-process API dispatch: no URL client, DNS, redirects or user-selected handler. */
@Component
public class DummyApiRegistry {
    public static final String LOAN="00000000-0000-4000-8000-000000000041";
    public static final String ASSET="00000000-0000-4000-8000-000000000101";
    public static final String VERSION="return-execution-v1";
    public record Entry(String apiId,String method,String pathTemplate,String pathKey,
                        Set<String> allowedInputSchema,String validator,String specification,String specificationExcerpt) {}
    public static final List<Entry> ALLOW_LIST=List.of(
        new Entry("API-ASSET-001","GET","/assets/{assetId}","assetId",Set.of(),"asset-detail-v1","knowledge/documents/asset-api.md",
            "GET /assets/{assetId}는 UUID 자산 식별자로 상세 정보를 반환한다. 성공은 HTTP 200이며 status와 현재 대여 상태를 포함한다."),
        new Entry("API-LOAN-APPROVE","POST","/loans/{loanId}/approve","loanId",Set.of("comment"),"loan-approval-v1","knowledge/documents/loan-api.md",
            "성공 시 HTTP 200과 status=APPROVED를 반환하고 자산은 RESERVED가 된다. 본인 신청 승인 시 HTTP 403 SELF_APPROVAL_FORBIDDEN을 반환한다."),
        new Entry("API-RETURN-CREATE","POST","/loans/{loanId}/returns","loanId",Set.of("accessoriesReturned","note"),"return-create-v1","knowledge/documents/return-api.md",
            "성공 시 HTTP 201과 returnId, status=INSPECTION_PENDING을 반환한다. 같은 대여에 반납 접수가 이미 있으면 HTTP 409 RETURN_ALREADY_REQUESTED다. 현재 대여자가 아니고 자산 담당자도 아닌 호출자는 HTTP 403 ACCESS_DENIED다."),
        new Entry("API-RETURN-INSPECT","POST","/returns/{returnId}/inspection","returnId",Set.of("result","damageDescription","photoReferences"),"return-inspection-validation-v1","knowledge/documents/return-api.md",
            "DAMAGED에서는 파손 설명과 최소 한 개의 사진 참조가 필수이며 누락 시 HTTP 400 VALIDATION_ERROR다."));
    private static final Set<String> ACTORS=Set.of("same-department-manager","requester","ordinary-employee","other-department-manager");
    private final ObjectMapper json;
    private final ReturnExecutionAdapter returns;
    public DummyApiRegistry(ObjectMapper json){this.json=json;this.returns=new ReturnExecutionAdapter(json);}
    public static boolean isReturn(Entry api){return api!=null && Set.of("API-RETURN-CREATE","API-RETURN-INSPECT").contains(api.apiId());}
    public List<String> returnModes(String plan){return returns.modes(plan==null?"":plan);}
    public ObjectNode returnSetup(JsonNode tc,String plan,String mode){return returns.setup(tc,plan,mode);}
    public boolean returnContract(JsonNode tc,String plan){return returns.matches(tc,plan);}
    public static boolean synthetic(JsonNode input){return Set.of("synthetic-self-approval-bug","intentional-defect","fixture-error").contains(input.path("fixtureProfile").asText());}
    public Entry resolve(JsonNode input) {
        for(var api:ALLOW_LIST) if(api.method.equals(input.path("method").asText()) && api.pathTemplate.equals(input.path("endpoint").asText()) &&
            (!input.has("apiId") || api.apiId.equals(input.path("apiId").asText())))return api;
        return null;
    }
    public boolean inputValid(JsonNode input,Entry api) {
        if(api==null || !input.isObject())return false;
        var fields=new HashSet<String>();input.fieldNames().forEachRemaining(fields::add);
        var allowed=new HashSet<>(Set.of("apiId","method","endpoint","pathParameters","body","actorFixture","fixtureProfile"));
        if(isReturn(api))allowed.addAll(Set.of("executionContractVersion","returnTemplateId"));
        if(!allowed.containsAll(fields))return false;
        var path=input.path("pathParameters");var body=input.path("body");
        if(!path.isObject() || path.size()!=1 || !path.path(api.pathKey).isTextual() || !body.isObject())return false;
        String id=path.path(api.pathKey).asText();
        if(!id.matches("[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"))return false;
        var keys=new HashSet<String>();body.fieldNames().forEachRemaining(keys::add);
        if(!api.allowedInputSchema.containsAll(keys))return false;
        if(body.has("comment") && (!body.get("comment").isTextual() || body.get("comment").asText().length()>1000))return false;
        return input.path("actorFixture").isTextual() && (!input.has("fixtureProfile") || input.get("fixtureProfile").isTextual()) && (!isReturn(api)||returns.inputValid(input));
    }
    public boolean fixtureReady(JsonNode tc,Entry api) {
        if(api==null)return false;
        if(isReturn(api))return returns.matches(tc,tc.at("/input/returnTemplateId").asText());
        var input=tc.path("input");String actor=input.path("actorFixture").asText();
        String profile=input.path("fixtureProfile").asText("standard");
        if(!ACTORS.contains(actor) || !Set.of("standard","synthetic-self-approval-bug").contains(profile))return false;
        if(api.pathKey.equals("assetId") && actor.equals("other-department-manager"))return false;
        if(profile.equals("synthetic-self-approval-bug") && (!api.apiId.equals("API-LOAN-APPROVE") || !actor.equals("requester")))return false;
        if(!input.at("/pathParameters/"+api.pathKey).asText().equals(api.pathKey.equals("loanId")?LOAN:ASSET))return false;
        // Closed precondition catalogue. Unknown prose cannot be silently declared reproducible.
        List<String> known=api.pathKey.equals("loanId")?List.of(
            "합성 계정과 부서 관계를 시험 환경에 준비한다: "+actor,
            "합성 대여 신청의 상태는 PENDING_APPROVAL이다.",
            "해당 자산의 상태는 AVAILABLE이다.",
            "상태 변경 비교를 위해 실행 전 신청 상태와 자산 상태를 기록한다."):
            List.of("합성 자산의 상태는 AVAILABLE이며 호출자와 같은 부서이다.");
        return tc.path("preconditions").equals(json.valueToTree(known));
    }
    public ObjectNode prepare(){return json.createObjectNode().put("loanStatus","PENDING_APPROVAL").put("assetStatus","AVAILABLE");}
    public ObjectNode prepare(JsonNode tc){return isReturn(resolve(tc.path("input")))?returns.prepare(tc):prepare();}
    public ResponseEntity<JsonNode> invoke(Entry api,JsonNode input,ObjectNode state) {
        if(isReturn(api))return returns.invoke(input,state);
        // Each invocation owns its state. Nothing is shared or written into business tables.
        if(api.apiId.equals("API-ASSET-001"))return response(200,json.createObjectNode().put("assetId",ASSET).put("status",state.path("assetStatus").asText()).putNull("currentLoan"));
        String actor=input.path("actorFixture").asText();
        boolean defect=input.path("fixtureProfile").asText().equals("synthetic-self-approval-bug");
        if(actor.equals("requester") && !defect)return response(403,json.createObjectNode().put("errorCode","SELF_APPROVAL_FORBIDDEN"));
        if(!actor.equals("same-department-manager") && !(actor.equals("requester") && defect))return response(403,json.createObjectNode().put("errorCode","ACCESS_DENIED"));
        // Intentional synthetic defect: requester authorization is skipped ONLY in the labelled fixture.
        state.put("loanStatus","APPROVED").put("assetStatus","RESERVED");
        return response(200,json.createObjectNode().put("status","APPROVED"));
    }
    private ResponseEntity<JsonNode> response(int status,JsonNode body){return ResponseEntity.status(status).body(body);}
}
