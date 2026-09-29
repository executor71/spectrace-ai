package com.example.legacyassistant.testcase;

import com.example.legacyassistant.requirement.Requirement;
import com.fasterxml.jackson.databind.JsonNode;
import java.time.Duration;
import java.util.Map;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.*;

@Component
public class TestCaseClient {
    private final RestClient client;
    public TestCaseClient(@Value("${AI_SERVICE_URL:http://ai-service:8000}") String url,
            @Value("${TEST_CASE_TIMEOUT_SECONDS:630}") int timeout) {
        var factory=new SimpleClientHttpRequestFactory();factory.setConnectTimeout(Duration.ofSeconds(5));factory.setReadTimeout(Duration.ofSeconds(timeout));
        client=RestClient.builder().baseUrl(url).requestFactory(factory).build();
    }
    public JsonNode generate(Requirement requirement, JsonNode analysis) {
        try {
            return client.post().uri("/internal/v1/test-cases/generate").body(Map.of("requirementId",requirement.id(),
                "title",requirement.title(),"description",requirement.description(),"analysis",analysis)).retrieve().body(JsonNode.class);
        } catch(RestClientResponseException error) {
            int status=error.getStatusCode().value();
            if(status==502) throw new TestCaseException(502,"INVALID_TEST_CASE_OUTPUT","모델 응답 검증에 실패했습니다. 이전 결과는 유지됩니다.");
            if(status==429) throw new TestCaseException(429,"TEST_CASE_BUSY","다른 생성이 진행 중입니다. 잠시 후 다시 요청해 주세요.");
            throw new TestCaseException(503,"TEST_CASE_UNAVAILABLE","테스트 생성 모델을 사용할 수 없습니다.");
        } catch(RestClientException error) { throw new TestCaseException(503,"TEST_CASE_UNAVAILABLE","테스트 생성 서비스 연결 또는 응답 시간이 초과되었습니다."); }
    }
}
