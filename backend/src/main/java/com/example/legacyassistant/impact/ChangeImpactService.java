package com.example.legacyassistant.impact;

import com.example.legacyassistant.analysis.*;
import com.example.legacyassistant.requirement.RequirementService;
import com.example.legacyassistant.testcase.*;
import com.example.legacyassistant.jobs.JobStore;
import com.example.legacyassistant.observability.Tracing;
import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.util.*;

@Service
public class ChangeImpactService {
 private final JdbcClient db;private final ObjectMapper json;private final RequirementService requirements;private final AnalysisService analyses;private final TestCaseService tests;private final TestCasePolicy policy;private final ExecutionService executions;private final AnalysisClient client;private final Tracing tracing;
 public ChangeImpactService(JdbcClient db,ObjectMapper json,RequirementService requirements,AnalysisService analyses,TestCaseService tests,TestCasePolicy policy,ExecutionService executions,AnalysisClient client,Tracing tracing){this.db=db;this.json=json;this.requirements=requirements;this.analyses=analyses;this.tests=tests;this.policy=policy;this.executions=executions;this.client=client;this.tracing=tracing;}
 private ObjectNode parse(String text){try{return (ObjectNode)json.readTree(text);}catch(Exception e){throw new IllegalStateException("Invalid persisted impact");}}
 private String encode(JsonNode value){return value.toString();}
 private String revision(JsonNode value){try{return JobStore.fingerprint(json.writer().with(SerializationFeature.ORDER_MAP_ENTRIES_BY_KEYS).writeValueAsString(json.convertValue(value,Object.class)));}catch(Exception e){throw new IllegalStateException(e);}}
 public static AnalysisException error(int status,String code){return new AnalysisException(status,code,code);}
 @Transactional(readOnly=true,isolation=org.springframework.transaction.annotation.Isolation.REPEATABLE_READ)
 public ObjectNode baseline(UUID id){
  var span=tracing.tracer.spanBuilder("change_impact.baseline_load").startSpan();try(var scope=span.makeCurrent()){
   ObjectNode value=json.createObjectNode();value.set("requirement",json.valueToTree(requirements.get(id)));value.set("analysis",analyses.get(id));
   try{value.set("testCases",tests.get(id));}catch(TestCaseException e){if(e.status()!=404)throw e;ObjectNode empty=json.createObjectNode();empty.putArray("testCases");value.set("testCases",empty);}
   value.put("currentPolicyHash",policy.hash);
   value.set("policyRegistry",policy.snapshot());
   // Executions are copied through a fixed local repository query, never arbitrary URLs.
   var history=db.sql("SELECT result_json::text FROM app.test_execution WHERE requirement_id=:id ORDER BY executed_at,execution_id").param("id",id).query((r,n)->parse(r.getString(1))).list();
   value.set("executions",json.valueToTree(history));
   value.put("revision",revision(value));return value;
  }finally{span.end();}
 }
 @Transactional(isolation=org.springframework.transaction.annotation.Isolation.REPEATABLE_READ)
 public ObjectNode create(UUID baselineId,String revision,String title,String content){
  var span=tracing.tracer.spanBuilder("change_impact.create").startSpan();try(var scope=span.makeCurrent()){
   if(title==null||title.isBlank()||title.length()>200||content==null||content.isBlank()||title.length()+content.length()>1900)throw error(422,"IMPACT_INPUT_INVALID");
   var snapshot=baseline(baselineId);if(!snapshot.path("revision").asText().equals(revision))throw error(409,"BASELINE_REVISION_MISMATCH");
   snapshot.put("capturedAt",java.time.Instant.now().toString());UUID id=UUID.randomUUID();
   db.sql("INSERT INTO app.change_impact(impact_id,baseline_requirement_id,baseline_revision,baseline_snapshot,proposal_title,proposal_content) VALUES(:id,:base,:revision,CAST(:snapshot AS jsonb),:title,:content)").param("id",id).param("base",baselineId).param("revision",revision).param("snapshot",encode(snapshot)).param("title",title).param("content",content).update();return get(id);
  }finally{span.end();}
 }
 public ObjectNode get(UUID id){return db.sql("SELECT jsonb_build_object('impactId',impact_id,'baselineRequirementId',baseline_requirement_id,'baselineRevision',baseline_revision,'baselineSnapshot',baseline_snapshot,'proposalTitle',proposal_title,'proposalContent',proposal_content,'createdAt',created_at)::text FROM app.change_impact WHERE impact_id=:id").param("id",id).query((r,n)->parse(r.getString(1))).optional().orElseThrow(()->error(404,"IMPACT_NOT_FOUND"));}
 public List<ObjectNode> list(){return db.sql("SELECT impact_id FROM app.change_impact ORDER BY created_at DESC LIMIT 100").query(UUID.class).list().stream().map(this::get).toList();}
 public ObjectNode analyze(UUID id){
  ObjectNode request=get(id);request.put("currentPolicyHash",policy.hash);
  var previous=db.sql("SELECT (result_json || jsonb_build_object('analysisId',analysis_id))::text FROM app.change_impact_analysis WHERE impact_id=:id ORDER BY created_at DESC,analysis_id DESC LIMIT 1").param("id",id).query((r,n)->parse(r.getString(1))).optional();
  previous.ifPresent(old->{if(old.path("baselineRevision").equals(request.path("baselineRevision"))&&old.path("policyHash").asText().equals(policy.hash)){
    request.set("cachedModelChanges",old.has("modelConditionChanges")?old.path("modelConditionChanges"):old.path("conditionChanges"));request.put("cachedModelVersion",old.path("modelVersion").asText());request.put("cachedAnalysisId",old.path("analysisId").asText());
  }});
  var output=client.impact(request);
  if(output==null||!output.isObject()||!output.path("impactId").asText().equals(id.toString())||!output.path("baselineRevision").equals(request.path("baselineRevision")))throw error(502,"INVALID_ANALYSIS_OUTPUT");
  for(String key:List.of("conditionChanges","affectedApis","affectedTestCases","newTestSuggestions","evidenceRefs","graphPaths"))if(!output.path(key).isArray())throw error(502,"INVALID_ANALYSIS_OUTPUT");
  return (ObjectNode)output;
 }
 public void ensureCurrent(UUID id){var impact=get(id);if(!baseline(UUID.fromString(impact.path("baselineRequirementId").asText())).path("revision").equals(impact.path("baselineRevision")))throw error(409,"BASELINE_STALE");}
 public void save(UUID id,UUID analysisId,JsonNode output){
  lock(id);
  get(id);db.sql("INSERT INTO app.change_impact_analysis(analysis_id,impact_id,result_json) VALUES(:analysis,:id,CAST(:output AS jsonb))").param("analysis",analysisId).param("id",id).param("output",encode(output)).update();
 }
 public ObjectNode result(UUID id){var impact=get(id);ObjectNode value=db.sql("SELECT (result_json || jsonb_build_object('analysisId',analysis_id))::text FROM app.change_impact_analysis WHERE impact_id=:id ORDER BY created_at DESC,analysis_id DESC LIMIT 1").param("id",id).query((r,n)->parse(r.getString(1))).optional().orElseThrow(()->error(404,"IMPACT_RESULT_NOT_FOUND"));
  value.put("baselineStale",!baseline(UUID.fromString(impact.path("baselineRequirementId").asText())).path("revision").equals(impact.path("baselineRevision")));return value;}
 public List<ObjectNode> reviews(UUID id){get(id);return db.sql("SELECT result_json::text FROM app.change_impact_review WHERE impact_id=:id ORDER BY review_revision").param("id",id).query((r,n)->parse(r.getString(1))).list();}
 @Transactional public ObjectNode review(UUID id,JsonNode input){
  var span=tracing.tracer.spanBuilder("change_impact.review").startSpan();try(var scope=span.makeCurrent()){
   lock(id);get(id);
   var result=result(id);if(result.path("baselineStale").asBoolean())throw error(409,"BASELINE_STALE");
   if(!result.path("analysisId").asText().equals(input.path("analysisId").asText()))throw error(409,"ANALYSIS_REVISION_MISMATCH");
   int revision=db.sql("SELECT coalesce(max(review_revision),0) FROM app.change_impact_review WHERE impact_id=:id").param("id",id).query(Integer.class).single();
   if(input.path("expectedRevision").asInt(-1)!=revision)throw error(409,"REVIEW_REVISION_MISMATCH");
   if(!Set.of("DRAFT","IN_REVIEW","REVIEWED").contains(input.path("status").asText())||input.path("reviewer").asText().isBlank()||input.toString().length()>100000)throw error(422,"REVIEW_INVALID");
   validateEdits(result,input,"conditionChanges","changeId",Set.of("changeType"));
   validateEdits(result,input,"affectedApis","apiId",Set.of("reviewDecision"));
   validateEdits(result,input,"affectedTestCases","testCaseId",Set.of("classification"));
   for(var api:input.path("affectedApis"))if(api.has("reviewDecision")&&!Set.of("PENDING","INCLUDED","EXCLUDED").contains(api.path("reviewDecision").asText()))throw error(422,"REVIEW_INVALID");
   for(var change:input.path("conditionChanges"))if(!Set.of("ADDED","REMOVED","MODIFIED","UNCHANGED","UNCERTAIN").contains(change.path("changeType").asText()))throw error(422,"REVIEW_INVALID");
   for(var tc:input.path("affectedTestCases"))if(!Set.of("KEEP","REVIEW","UPDATE_CANDIDATE","OBSOLETE_CANDIDATE").contains(tc.path("classification").asText()))throw error(422,"REVIEW_INVALID");
   ObjectNode value=(ObjectNode)input.deepCopy();value.put("reviewId",UUID.randomUUID().toString());value.put("reviewRevision",revision+1);value.put("reviewedAt",java.time.Instant.now().toString());value.put("businessPolicyApproved",false);
   db.sql("INSERT INTO app.change_impact_review(review_id,impact_id,analysis_id,review_revision,result_json) VALUES(:review,:id,:analysis,:revision,CAST(:value AS jsonb))").param("review",UUID.fromString(value.path("reviewId").asText())).param("id",id).param("analysis",UUID.fromString(result.path("analysisId").asText())).param("revision",revision+1).param("value",encode(value)).update();return value;
  }finally{span.end();}
 }
 private void validateEdits(JsonNode result,JsonNode input,String section,String id,Set<String> editable){
  if(!input.path(section).isArray()||input.path(section).size()!=result.path(section).size())throw error(422,"REVIEW_INVALID");
  Map<String,JsonNode> originals=new HashMap<>();for(var row:result.path(section))originals.put(row.path(id).asText(),row);
  Set<String> seen=new HashSet<>();for(var row:input.path(section)){
   String key=row.path(id).asText();if(!seen.add(key)||!originals.containsKey(key)||!row.isObject())throw error(422,"REVIEW_INVALID");
   ObjectNode original=(ObjectNode)originals.get(key).deepCopy(),edited=(ObjectNode)row.deepCopy();editable.forEach(field->{original.remove(field);edited.remove(field);});if(!original.equals(edited))throw error(422,"REVIEW_SOURCE_TAMPERED");
  }
 }
 private void lock(UUID id){db.sql("SELECT pg_advisory_xact_lock(hashtextextended(CAST(:id AS text),150001))").param("id",id).query((r,n)->1).single();}
}
