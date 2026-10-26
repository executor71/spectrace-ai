package com.example.legacyassistant.jobs;
import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
@Component public class AnalysisCapacity {
 public enum State { IDLE, BUSY, UNAVAILABLE }
 private final RestClient client;
 public AnalysisCapacity(@Value("${AI_SERVICE_URL:http://ai-service:8000}")String url){var f=new SimpleClientHttpRequestFactory();f.setConnectTimeout(1500);f.setReadTimeout(2000);client=RestClient.builder().baseUrl(url).requestFactory(f).build();}
 public State state(){try{var result=client.get().uri("/internal/v1/analysis-capacity").retrieve().body(JsonNode.class);if(result==null||!result.path("available").isBoolean())return State.UNAVAILABLE;return result.path("available").asBoolean()?State.IDLE:State.BUSY;}catch(Exception e){return State.UNAVAILABLE;}}
}
