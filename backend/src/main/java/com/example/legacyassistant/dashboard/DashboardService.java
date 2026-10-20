package com.example.legacyassistant.dashboard;

import com.example.legacyassistant.analysis.AnalysisRepository;
import com.example.legacyassistant.requirement.RequirementService;
import com.example.legacyassistant.testcase.TestCaseRepository;
import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import java.time.Instant;
import java.util.*;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.*;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.http.HttpStatus;

@Service
public class DashboardService {
    private final JdbcClient jdbc; private final ObjectMapper json; private final RequirementService requirements;
    private final TestCaseRepository tests; private final AnalysisRepository analyses;
    public DashboardService(JdbcClient jdbc,ObjectMapper json,RequirementService requirements,TestCaseRepository tests,AnalysisRepository analyses) {
        this.jdbc=jdbc;this.json=json;this.requirements=requirements;this.tests=tests;this.analyses=analyses;
    }
    private JsonNode parse(String value) {try{return json.readTree(value);}catch(Exception e){throw new IllegalStateException("Invalid stored data",e);}}
    public static final int MAX_ROWS=10000;
    public static void limit(int n) {if(n>MAX_ROWS)throw new ResponseStatusException(HttpStatus.PAYLOAD_TOO_LARGE,"조회 한도 10,000행을 초과했습니다. 요구사항 범위를 좁혀 주세요.");}
    public List<JsonNode> executions(UUID id) {
        var rows=jdbc.sql("SELECT result_json::text FROM app.test_execution WHERE requirement_id=:id ORDER BY executed_at DESC,execution_id DESC LIMIT 10001")
            .param("id",id).query((rs,n)->parse(rs.getString(1))).list();limit(rows.size());return rows;
    }
    public static ObjectNode counts(ObjectMapper json,JsonNode batch,List<JsonNode> runs,ArrayNode cases,String requirementId,String title) {
        ObjectNode result=json.createObjectNode();for(String key:List.of("total","DRAFT","APPROVED","REJECTED","PASS","FAIL","ERROR","NOT_RUN","SYNTHETIC"))result.put(key,0);
        for(JsonNode tc:batch.path("testCases")) {
            String tcId=tc.path("testCaseId").asText();
            JsonNode latest=runs.stream().filter(r->r.path("testCaseId").asText().equals(tcId)
                && r.path("generationId").asText().equals(batch.path("generationId").asText())
                && r.path("testCaseRevision").asLong(-1)==tc.path("reviewRevision").asLong()
                && !r.path("syntheticDefect").asBoolean()).findFirst().orElse(null);
            boolean synthetic=runs.stream().anyMatch(r->r.path("testCaseId").asText().equals(tcId)
                && r.path("generationId").asText().equals(batch.path("generationId").asText())
                && r.path("testCaseRevision").asLong(-1)==tc.path("reviewRevision").asLong() && r.path("syntheticDefect").asBoolean());
            String status=latest==null?"NOT_RUN":latest.path("result").asText("ERROR");
            if(!Set.of("PASS","FAIL","ERROR","NOT_RUN").contains(status))status="ERROR";
            result.put("total",result.path("total").asInt()+1);
            String approval=tc.path("approvalStatus").asText("DRAFT");result.put(approval,result.path(approval).asInt()+1);
            result.put(status,result.path(status).asInt()+1);if(synthetic)result.put("SYNTHETIC",result.path("SYNTHETIC").asInt()+1);
            ObjectNode item=cases.addObject().put("testCaseId",tcId).put("requirementId",requirementId).put("title",title)
                .put("scenario",tc.path("scenario").asText()).put("approvalStatus",approval).put("reviewRevision",tc.path("reviewRevision").asLong())
                .put("executionStatus",status).put("syntheticExecution",synthetic);
            if(latest!=null)item.put("executedAt",latest.path("executedAt").asText());
        }
        int denominator=result.path("PASS").asInt()+result.path("FAIL").asInt();
        if(denominator==0)result.putNull("passRatio");else result.put("passRatio",(double)result.path("PASS").asInt()/denominator);
        result.put("blocked","미조회: 실행 차단은 결과 FAIL에 포함하지 않음");return result;
    }
    @Transactional(readOnly=true,isolation=Isolation.REPEATABLE_READ)
    public ObjectNode dashboard(UUID selected) {
        String sql="SELECT id FROM app.requirement"+(selected==null?"":" WHERE id=:id")+" ORDER BY created_at DESC,id DESC LIMIT 1001";
        var query=jdbc.sql(sql);if(selected!=null){requirements.get(selected);query.param("id",selected);}
        var ids=query.query(UUID.class).list();if(ids.size()>1000)throw new ResponseStatusException(HttpStatus.PAYLOAD_TOO_LARGE,"요구사항 1,000건 조회 한도 초과");
        ObjectNode out=json.createObjectNode().put("queriedAt",Instant.now().toString());ArrayNode rows=out.putArray("requirements"),cases=out.putArray("cases");
        ObjectNode totals=json.createObjectNode();for(String key:List.of("total","DRAFT","APPROVED","REJECTED","PASS","FAIL","ERROR","NOT_RUN","SYNTHETIC"))totals.put(key,0);
        for(UUID id:ids) {
            var req=requirements.get(id);JsonNode batch=tests.find(id).orElse(json.createObjectNode());
            var count=counts(json,batch,executions(id),cases,id.toString(),req.title());limit(cases.size());
            ObjectNode row=rows.addObject().put("id",id.toString()).put("title",req.title()).put("createdAt",req.createdAt().toString())
                .put("status",req.status()).put("hasAnalysis",analyses.find(id).isPresent()).put("stale",batch.path("stale").asBoolean());
            row.set("counts",count);
            for(String key:List.of("total","DRAFT","APPROVED","REJECTED","PASS","FAIL","ERROR","NOT_RUN","SYNTHETIC"))totals.put(key,totals.path(key).asInt()+count.path(key).asInt());
        }
        totals.put("requirements",ids.size());int d=totals.path("PASS").asInt()+totals.path("FAIL").asInt();
        if(d==0)totals.putNull("passRatio");else totals.put("passRatio",(double)totals.path("PASS").asInt()/d);
        out.set("counts",totals);out.put("basis","현재 생성 batch·현재 검토본 / 현재 revision의 최신 일반 실행. 의도적 결함은 별도 집계·PASS 비율에서 제외. 차단은 미조회이며 FAIL 아님.");return out;
    }
    @Transactional(readOnly=true,isolation=Isolation.REPEATABLE_READ)
    public ObjectNode reportData(UUID id) {
        var req=requirements.get(id);ObjectNode data=json.createObjectNode().put("queriedAt",Instant.now().toString());
        data.set("requirement",json.valueToTree(req));data.set("analysis",analyses.find(id).orElse(json.createObjectNode()));
        JsonNode batch=tests.find(id).orElse(json.createObjectNode());data.set("batch",batch);
        var runs=executions(id);data.set("executions",json.valueToTree(runs));
        data.set("counts",counts(json,batch,runs,json.createArrayNode(),id.toString(),req.title()));return data;
    }
}
