package com.example.legacyassistant.requirement;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Stream;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.MethodSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;
import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@AutoConfigureMockMvc
@Transactional
class RequirementIntegrationTest {
    @Autowired MockMvc mvc;
    @Autowired ObjectMapper json;
    @Autowired JdbcTemplate jdbc;

    @Test void createsAndFetchesPersistedRequirement() throws Exception {
        var response = mvc.perform(post("/api/requirements").contentType("application/json")
                .content("{\"title\":\"  주문 취소  \",\"description\":\" 미배송 주문만 취소합니다. \",\"status\":\"REVIEWED\"}"))
            .andExpect(status().isCreated()).andExpect(jsonPath("$.status").value("DRAFT"))
            .andExpect(jsonPath("$.title").value("주문 취소"))
            .andExpect(jsonPath("$.createdAt").isNotEmpty()).andReturn().getResponse();
        var body = json.readTree(response.getContentAsString());
        UUID id = UUID.fromString(body.get("id").asText());
        assertEquals("/api/requirements/" + id, response.getHeader("Location"));
        assertEquals("미배송 주문만 취소합니다.", jdbc.queryForObject(
                "SELECT description FROM app.requirement WHERE id=?", String.class, id));
        mvc.perform(get(response.getHeader("Location"))).andExpect(status().isOk())
            .andExpect(content().json(response.getContentAsString()));
    }

    static Stream<String> invalidBodies() throws Exception {
        var mapper = new ObjectMapper();
        return Stream.of("{}", "{\"title\":null,\"description\":\"ok\"}",
            "{\"title\":\" \",\"description\":\"ok\"}", mapper.writeValueAsString(Map.of("title","ok","description"," \n ")),
            mapper.writeValueAsString(Map.of("title","x".repeat(201),"description","ok")),
            mapper.writeValueAsString(Map.of("title","ok","description","x".repeat(10001))));
    }

    @ParameterizedTest @MethodSource("invalidBodies")
    void invalidInputDoesNotPersist(String body) throws Exception {
        int count = jdbc.queryForObject("SELECT count(*) FROM app.requirement", Integer.class);
        mvc.perform(post("/api/requirements").contentType("application/json").content(body))
            .andExpect(status().isBadRequest()).andExpect(jsonPath("$.code").value("VALIDATION_ERROR"))
            .andExpect(jsonPath("$.fieldErrors").isNotEmpty());
        assertEquals(count, jdbc.queryForObject("SELECT count(*) FROM app.requirement", Integer.class));
    }

    @Test void maximumLengthsAccepted() throws Exception {
        mvc.perform(post("/api/requirements").contentType("application/json").content(json.writeValueAsString(
                Map.of("title","가".repeat(200),"description","나".repeat(10000)))))
            .andExpect(status().isCreated());
    }

    @Test void malformedJsonReturnsSafeError() throws Exception {
        mvc.perform(post("/api/requirements").contentType("application/json").content("{"))
            .andExpect(status().isBadRequest()).andExpect(jsonPath("$.code").value("INVALID_JSON"));
    }

    @Test void invalidUuidReturns400() throws Exception {
        mvc.perform(get("/api/requirements/not-a-uuid"))
            .andExpect(status().isBadRequest()).andExpect(jsonPath("$.code").value("INVALID_ID"));
    }

    @Test void missingIdReturns404() throws Exception {
        mvc.perform(get("/api/requirements/" + UUID.randomUUID()))
            .andExpect(status().isNotFound()).andExpect(jsonPath("$.code").value("REQUIREMENT_NOT_FOUND"));
    }

    @Test void sqlLikeTextIsStoredLiterally() throws Exception {
        String title = "'); DROP TABLE app.requirement; --";
        var response = mvc.perform(post("/api/requirements").contentType("application/json")
            .content(json.writeValueAsString(Map.of("title",title,"description","<script>sample</script>"))))
            .andExpect(status().isCreated()).andExpect(jsonPath("$.title").value(title)).andReturn().getResponse();
        mvc.perform(get(response.getHeader("Location"))).andExpect(status().isOk())
            .andExpect(jsonPath("$.description").value("<script>sample</script>"));
    }

    @Test void runtimeUsesRestrictedAppRole() {
        assertEquals("app_user", jdbc.queryForObject("SELECT current_user", String.class));
        assertEquals(false, jdbc.queryForObject("SELECT has_schema_privilege(current_user,'rag','USAGE')", Boolean.class));
        assertEquals(false, jdbc.queryForObject("SELECT has_schema_privilege(current_user,'evaluation','USAGE')", Boolean.class));
        assertEquals(false, jdbc.queryForObject("SELECT has_table_privilege(current_user,'app.flyway_schema_history','UPDATE')", Boolean.class));
    }

    @Test void migrationRejectsBlankDataEvenOutsideApi() {
        assertThrows(DataIntegrityViolationException.class, () -> jdbc.update(
                "INSERT INTO app.requirement(id,title,description) VALUES (?, ?, ?)", UUID.randomUUID(), " ", "sample"));
    }
}
