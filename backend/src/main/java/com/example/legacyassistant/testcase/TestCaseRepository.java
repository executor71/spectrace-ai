package com.example.legacyassistant.testcase;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.util.*;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

@Repository
public class TestCaseRepository {
    private final JdbcClient jdbc; private final ObjectMapper json;
    public TestCaseRepository(JdbcClient jdbc,ObjectMapper json) { this.jdbc=jdbc;this.json=json; }
    private JsonNode parse(String value) { try { return json.readTree(value); } catch(Exception e) { throw new IllegalStateException(e); } }
    @Transactional
    public void save(UUID id, JsonNode source, ObjectNode result) {
        var current=jdbc.sql("SELECT result_json::text FROM app.requirement_analysis WHERE requirement_id=:id FOR UPDATE")
            .param("id",id).query(String.class).optional();
        if(current.isEmpty() || !parse(current.get()).equals(source))
            throw new TestCaseException(409,"TEST_CASE_SOURCE_CHANGED","생성 중 분석 결과가 변경되었습니다. 최신 분석으로 다시 생성해 주세요.");
        // Serializes concurrent generations and analysis writes without holding a connection during LLM calls.
        jdbc.sql("DELETE FROM app.test_case_generation WHERE requirement_id=:id").param("id",id).update();
        UUID generation=UUID.fromString(result.get("generationId").asText());
        ObjectNode metadata=result.deepCopy();metadata.remove("testCases");
        jdbc.sql("INSERT INTO app.test_case_generation(requirement_id,generation_id,source_analysis,metadata) VALUES (:id,:generation,CAST(:source AS jsonb),CAST(:metadata AS jsonb))")
            .param("id",id).param("generation",generation).param("source",source.toString()).param("metadata",metadata.toString()).update();
        int ordinal=0;
        for(var item:result.get("testCases"))
            jdbc.sql("INSERT INTO app.test_case(test_case_id,requirement_id,generation_id,ordinal,result_json) VALUES (:tc,:id,:generation,:ordinal,CAST(:body AS jsonb))")
                .param("tc",UUID.fromString(item.get("testCaseId").asText())).param("id",id).param("generation",generation).param("ordinal",ordinal++)
                .param("body",item.toString()).update();
    }
    public Optional<JsonNode> find(UUID id) {
        return jdbc.sql("SELECT (g.metadata || jsonb_build_object('testCases', COALESCE(jsonb_agg("+TestCaseReviewService.PROJECTION+" ORDER BY t.ordinal) FILTER (WHERE t.test_case_id IS NOT NULL),'[]'::jsonb), 'sourceAnalysis',g.source_analysis, 'stale',g.source_analysis IS DISTINCT FROM a.result_json))::text " +
            "FROM app.test_case_generation g LEFT JOIN app.test_case t ON t.generation_id=g.generation_id LEFT JOIN app.requirement_analysis a ON a.requirement_id=g.requirement_id WHERE g.requirement_id=:id GROUP BY g.requirement_id,a.result_json")
            .param("id",id).query((rs,row) -> parse(rs.getString(1))).optional();
    }
}
