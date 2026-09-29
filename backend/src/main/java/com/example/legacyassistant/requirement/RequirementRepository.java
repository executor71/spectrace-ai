package com.example.legacyassistant.requirement;

import java.time.OffsetDateTime;
import java.util.Optional;
import java.util.UUID;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

@Repository
public class RequirementRepository {
    private final JdbcClient jdbc;
    private static final RowMapper<Requirement> ROW = (rs, row) -> new Requirement(
            rs.getObject("id", UUID.class), rs.getString("title"), rs.getString("description"),
            rs.getString("status"), rs.getObject("created_at", OffsetDateTime.class).toInstant());

    public RequirementRepository(JdbcClient jdbc) { this.jdbc = jdbc; }

    public Requirement insert(UUID id, String title, String description) {
        return jdbc.sql("""
                INSERT INTO app.requirement (id, title, description)
                VALUES (:id, :title, :description)
                RETURNING id, title, description, status, created_at
                """).param("id", id).param("title", title).param("description", description)
                .query(ROW).single();
    }

    public Optional<Requirement> findById(UUID id) {
        return jdbc.sql("""
                SELECT id, title, description, status, created_at FROM app.requirement WHERE id = :id
                """).param("id", id).query(ROW).optional();
    }
}
