package com.example.legacyassistant.analysis;

import com.example.legacyassistant.requirement.Requirement;
import com.fasterxml.jackson.databind.JsonNode;
import java.time.Duration;
import java.util.Map;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientResponseException;

@Component
public class AnalysisClient {
    private final RestClient client;
    public AnalysisClient(@Value("${AI_SERVICE_URL:http://ai-service:8000}") String url,
            @Value("${ANALYSIS_TIMEOUT_SECONDS:630}") int timeoutSeconds) {
        var factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(Duration.ofSeconds(5));
        factory.setReadTimeout(Duration.ofSeconds(timeoutSeconds));
        client = RestClient.builder().baseUrl(url).requestFactory(factory).requestInterceptor(new com.example.legacyassistant.observability.TraceHttpInterceptor()).build();
    }
    public JsonNode analyze(Requirement requirement) {
        try {
            return client.post().uri("/internal/v1/requirement-analysis")
                .body(Map.of("requirementId", requirement.id(), "title", requirement.title(), "description", requirement.description()))
                .retrieve().body(JsonNode.class);
        } catch (RestClientResponseException e) {
            int status = e.getStatusCode().value();
            if (status == 422) throw new AnalysisException(422, "ANALYSIS_INPUT_TOO_LONG", "분석 입력이 기존 검색 제한(2,000자/512 토큰)을 초과했습니다. 요구사항을 나누어 주세요.");
            if (status == 429) throw new AnalysisException(429, "ANALYSIS_BUSY", "다른 분석이 진행 중입니다. 잠시 후 다시 요청해 주세요.");
            if (status == 502) throw new AnalysisException(502, "INVALID_ANALYSIS_OUTPUT", "모델 응답이 형식 또는 근거 검증에 실패하여 저장하지 않았습니다.");
            throw new AnalysisException(503, "ANALYSIS_UNAVAILABLE", "분석 모델 또는 검색 서비스가 준비되지 않았습니다.");
        } catch (Exception e) {
            throw new AnalysisException(503, "ANALYSIS_UNAVAILABLE", "분석 서비스 연결 또는 응답 시간이 초과되었습니다.");
        }
    }
}
