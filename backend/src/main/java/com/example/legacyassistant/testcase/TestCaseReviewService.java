package com.example.legacyassistant.testcase;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.util.*;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class TestCaseReviewService {
    static final Set<String> EDITABLE=Set.of("type","scenario","preconditions","input","steps","expectedResult");
    // Top-level fields remain compatible with Phase 4 readers; originals are always separate.
    static final String PROJECTION="(t.result_json || COALESCE(t.reviewed_content,'{}'::jsonb) || jsonb_build_object("+
        "'generatedContent',t.result_json,'reviewedContent',t.reviewed_content,'approvalStatus',t.approval_status,"+
        "'reviewedAt',t.reviewed_at,'reviewer',t.reviewer,'reviewComment',t.review_comment,'reviewRevision',t.review_revision,"+
        "'modified',t.reviewed_content IS NOT NULL))";
    private final JdbcClient jdbc; private final ObjectMapper json; private final TestCasePolicy policy;
    public TestCaseReviewService(JdbcClient jdbc,ObjectMapper json,TestCasePolicy policy) {this.jdbc=jdbc;this.json=json;this.policy=policy;}
    private JsonNode parse(String value) {try{return json.readTree(value);}catch(Exception e){throw new IllegalStateException(e);}}
    private record Row(ObjectNode content,JsonNode source,boolean stale) {}
    private Row lock(UUID id) {
        return jdbc.sql("SELECT "+PROJECTION+"::text AS content,g.source_analysis::text AS source,"+
            "(g.source_analysis IS DISTINCT FROM a.result_json OR g.metadata->>'policyHash' IS DISTINCT FROM :hash) AS stale "+
            "FROM app.test_case t JOIN app.test_case_generation g ON g.generation_id=t.generation_id "+
            "LEFT JOIN app.requirement_analysis a ON a.requirement_id=t.requirement_id WHERE t.test_case_id=:id FOR UPDATE OF t")
            .param("id",id).param("hash",policy.hash)
            .query((rs,n)->new Row((ObjectNode)parse(rs.getString("content")),parse(rs.getString("source")),rs.getBoolean("stale")))
            .optional().orElseThrow(()->new TestCaseException(404,"TEST_CASE_NOT_FOUND","테스트케이스가 없습니다."));
    }
    static void check(boolean valid,String message) {if(!valid)throw new TestCaseException(400,"INVALID_REVIEW_INPUT",message);}
    static void text(JsonNode value,int max,String field) {
        check(value!=null && value.isTextual() && !value.asText().isBlank() && value.asText().length()<=max,field+" 값을 확인해 주세요.");
    }
    static void validateContent(JsonNode value) {
        check(TestCasePolicy.TYPES.contains(value.path("type").asText()),"잘못된 Test Type입니다.");
        text(value.get("scenario"),10000,"scenario");
        for(String field:List.of("preconditions","steps")) {
            JsonNode items=value.path(field);check(items.isArray() && items.size()<=100 && (!field.equals("steps") || !items.isEmpty()),field+" 배열을 확인해 주세요.");
            for(var item:items)text(item,10000,field);
        }
        check(value.path("input").isObject() && value.path("input").toString().length()<=100000,"input은 JSON 객체여야 합니다.");
        JsonNode expected=value.path("expectedResult");check(expected.isObject(),"expectedResult는 JSON 객체여야 합니다.");
        Set<String> fields=new HashSet<>();expected.fieldNames().forEachRemaining(fields::add);
        check(fields.equals(Set.of("description","assertions")),"expectedResult에는 description과 assertions만 허용됩니다.");
        text(expected.get("description"),10000,"expectedResult.description");
        check(expected.path("assertions").isArray() && expected.path("assertions").size()<=100 && expected.toString().length()<=100000,"assertions 배열을 확인해 주세요.");
        for(var assertion:expected.path("assertions"))check(assertion.isObject(),"assertions 항목은 객체여야 합니다.");
    }
    private void request(JsonNode body,Set<String> allowed,Row row) {
        check(body!=null && body.isObject(),"JSON 객체가 필요합니다.");
        body.fieldNames().forEachRemaining(key->check(allowed.contains(key),"변경할 수 없는 필드: "+key));
        check(body.path("reviewRevision").isIntegralNumber() && body.path("reviewRevision").canConvertToLong(),"reviewRevision이 필요합니다.");
        if(body.path("reviewRevision").asLong()!=row.content.path("reviewRevision").asLong())
            throw new TestCaseException(409,"REVIEW_CONFLICT","다른 검토 결과가 저장되었습니다. 다시 조회해 주세요.");
    }
    @Transactional
    public JsonNode edit(UUID id,JsonNode body) {
        Row row=lock(id);Set<String> allowed=new HashSet<>(EDITABLE);allowed.add("reviewRevision");request(body,allowed,row);
        check(body.size()>1,"수정할 항목이 필요합니다.");
        ObjectNode content=row.content.deepCopy();body.fields().forEachRemaining(e->{if(EDITABLE.contains(e.getKey()))content.set(e.getKey(),e.getValue());});
        validateContent(content);ObjectNode reviewed=json.createObjectNode();for(String key:EDITABLE)reviewed.set(key,content.get(key));
        boolean changed=EDITABLE.stream().anyMatch(key->!Objects.equals(content.get(key),row.content.path("generatedContent").get(key)));
        jdbc.sql("UPDATE app.test_case SET reviewed_content=CAST(:content AS jsonb),approval_status='DRAFT',reviewed_at=NULL,reviewer=NULL,review_comment=NULL,review_revision=review_revision+1 WHERE test_case_id=:id")
            .param("content",changed?reviewed.toString():null,java.sql.Types.VARCHAR).param("id",id).update();
        return response(lock(id));
    }
    @Transactional
    public JsonNode decide(UUID id,JsonNode body,boolean approve) {
        Row row=lock(id);request(body,Set.of("reviewRevision","reviewer","reviewComment"),row);
        String reviewer=body.has("reviewer")?body.get("reviewer").asText():"demo/local";
        if(body.has("reviewer"))text(body.get("reviewer"),100,"reviewer");
        JsonNode comment=body.get("reviewComment");check(comment==null || comment.isTextual() && comment.asText().length()<=4000,"reviewComment 값을 확인해 주세요.");
        if(approve) {
            if(row.stale)throw new TestCaseException(409,"STALE_TEST_CASE","분석 또는 정책이 변경된 테스트는 승인할 수 없습니다.");
            validateContent(row.content);
            JsonNode generated=row.content.get("generatedContent");ObjectNode candidate=generated.deepCopy();candidate.remove("testCaseId");
            boolean verified;
            try { verified=policy.candidates(UUID.fromString(generated.path("requirementId").asText()),row.source).values().stream().anyMatch(candidate::equals); }
            catch(RuntimeException invalidSource) { verified=false; }
            if(!verified || !row.content.path("evidence").equals(generated.path("evidence")))
                throw new TestCaseException(409,"INVALID_REVIEW_EVIDENCE","Phase 4에서 검증한 원본 근거를 확인할 수 없습니다.");
        }
        jdbc.sql("UPDATE app.test_case SET approval_status=:status,reviewed_at=CURRENT_TIMESTAMP,reviewer=:reviewer,review_comment=:comment,review_revision=review_revision+1 WHERE test_case_id=:id")
            .param("status",approve?"APPROVED":"REJECTED").param("reviewer",reviewer).param("comment",comment==null?null:comment.asText(),java.sql.Types.VARCHAR).param("id",id).update();
        return response(lock(id));
    }
    private JsonNode response(Row row) {decorate(row.content,policy,row.stale);return row.content;}
    static void decorate(ObjectNode item,TestCasePolicy policy,boolean stale) {
        if(!item.has("approvalStatus")) {
            item.set("generatedContent",item.deepCopy());item.putNull("reviewedContent");item.put("approvalStatus","DRAFT");
            item.putNull("reviewedAt");item.putNull("reviewer");item.putNull("reviewComment");item.put("reviewRevision",0);item.put("modified",false);
        }
        // Approval is never an input to technical executability.
        item.put("executable",!stale && policy.gates(item).values().stream().allMatch(Boolean::booleanValue));
        item.put("executionEligible",item.path("executable").asBoolean() && item.path("approvalStatus").asText().equals("APPROVED"));
    }
}
