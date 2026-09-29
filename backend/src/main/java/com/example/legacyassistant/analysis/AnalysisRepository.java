package com.example.legacyassistant.analysis;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.Optional;
import java.util.UUID;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

@Repository
public class AnalysisRepository {
    private final JdbcClient jdbc;
    private final ObjectMapper json;
    public AnalysisRepository(JdbcClient jdbc, ObjectMapper json) { this.jdbc = jdbc; this.json = json; }

    @Transactional
    public void save(UUID id, JsonNode result) {
        jdbc.sql("INSERT INTO app.requirement_analysis(requirement_id, result_json) VALUES (:id, CAST(:result AS jsonb)) " +
            "ON CONFLICT(requirement_id) DO UPDATE SET result_json=EXCLUDED.result_json, created_at=CURRENT_TIMESTAMP")
            .param("id", id).param("result", result.toString()).update();
        jdbc.sql("UPDATE app.requirement SET status='ANALYZED' WHERE id=:id AND status='DRAFT'").param("id", id).update();
    }
    public Optional<JsonNode> find(UUID id) {
        return jdbc.sql("SELECT result_json::text FROM app.requirement_analysis WHERE requirement_id=:id")
            .param("id", id).query((rs, row) -> {
                try { return json.readTree(rs.getString(1)); }
                catch (Exception e) { throw new IllegalStateException("Stored analysis is invalid", e); }
            }).optional();
    }
}
