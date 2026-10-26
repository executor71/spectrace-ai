package com.example.legacyassistant.jobs;
import com.example.legacyassistant.analysis.*;
import com.example.legacyassistant.requirement.RequirementService;
import com.example.legacyassistant.observability.Tracing;
import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import io.opentelemetry.api.trace.*;
import io.opentelemetry.context.Context;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.*;
import java.util.*;
import java.util.function.Supplier;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class JobStore {
    private final JdbcClient jdbc;private final ObjectMapper json;private final RequirementService requirements;
    private final AnalysisRepository results;private final Tracing tracing;private final int queueLimit,leaseSeconds,concurrency;
    public JobStore(JdbcClient jdbc,ObjectMapper json,RequirementService requirements,AnalysisRepository results,Tracing tracing,
      @Value("${analysis.jobs.queue-limit:5}")int queueLimit,@Value("${analysis.jobs.lease-seconds:30}")int leaseSeconds,@Value("${analysis.jobs.max-concurrent:1}")int concurrency){
        if(queueLimit<1||leaseSeconds<3||concurrency<1)throw new IllegalArgumentException("Invalid job settings");
        this.jdbc=jdbc;this.json=json;this.requirements=requirements;this.results=results;this.tracing=tracing;this.queueLimit=queueLimit;this.leaseSeconds=leaseSeconds;this.concurrency=concurrency;
    }
    public static String fingerprint(String value){try{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8)));}catch(Exception e){throw new IllegalStateException(e);}}
    private ObjectNode parse(String value){try{return (ObjectNode)json.readTree(value);}catch(Exception e){throw new IllegalStateException("Invalid stored job");}}
    private static final String PROJECTION="jsonb_build_object('jobId',j.job_id,'requirementId',j.requirement_id,'status',j.status,'stage',j.stage,'createdAt',j.created_at,'startedAt',j.started_at,'completedAt',j.completed_at,'updatedAt',j.updated_at,'attemptCount',j.attempt_count,'errorCode',j.error_code,'errorMessage',j.error_message,'analysisResultId',j.analysis_result_id,'workerId',j.worker_id,'leaseExpiresAt',j.lease_expires_at,'executionToken',j.execution_token,'traceParent',j.trace_parent,'resultAvailable',j.status='SUCCEEDED' AND j.result_fingerprint=md5(a.result_json::text),'queuePosition',CASE WHEN j.status='QUEUED' THEN (SELECT count(*) FROM app.analysis_job q WHERE q.status='QUEUED' AND (q.created_at,q.job_id)<=(j.created_at,j.job_id)) ELSE NULL END)::text";
    private ObjectNode row(UUID id){return jdbc.sql("SELECT "+PROJECTION+" FROM app.analysis_job j LEFT JOIN app.requirement_analysis a ON a.requirement_id=j.requirement_id WHERE j.job_id=:id").param("id",id).query((r,n)->parse(r.getString(1))).optional().orElseThrow(()->new AnalysisException(404,"JOB_NOT_FOUND","分析 Job이 없습니다."));}
    private <T>T span(String name,UUID id,Supplier<T> action){
        Span s=tracing.tracer.spanBuilder(name).startSpan();if(id!=null)s.setAttribute("jobId",id.toString());
        try(var scope=s.makeCurrent()){
            T result=action.get();
            try{
                ObjectNode node=null;
                if(result instanceof ObjectNode n)node=n;
                else if(result instanceof Optional<?> optional && optional.orElse(null) instanceof ObjectNode n)node=n;
                else if(id!=null)node=row(id);
                if(node!=null){s.setAttribute("jobId",node.path("jobId").asText()).setAttribute("requirementId",node.path("requirementId").asText()).setAttribute("status",node.path("status").asText()).setAttribute("stage",node.path("stage").asText()).setAttribute("attemptCount",node.path("attemptCount").asLong());
                    if(node.hasNonNull("errorCode"))s.setAttribute("errorCode",node.path("errorCode").asText());
                    for(String key:List.of("queueWaitMs","executionDurationMs","totalDurationMs"))if(node.hasNonNull(key))s.setAttribute(key,node.path(key).asLong());}
            }catch(Exception ignored){/* Metadata never changes the business outcome. */}
            return result;
        }catch(AnalysisException e){s.setStatus(StatusCode.ERROR).setAttribute("errorCode",e.code());throw e;}finally{s.end();}
    }
    @Transactional public ObjectNode create(UUID requirementId){return span("analysis.job.create",null,()->{
        var req=requirements.get(requirementId);
        jdbc.sql("SELECT pg_advisory_xact_lock(140002)").query((r,n)->1).single();
        var active=jdbc.sql("SELECT job_id FROM app.analysis_job WHERE requirement_id=:id AND status IN ('QUEUED','RUNNING')").param("id",requirementId).query(UUID.class).optional();
        if(active.isPresent())return publicView(row(active.get()));
        if(jdbc.sql("SELECT count(*) FROM app.analysis_job WHERE status='QUEUED'").query(Long.class).single()>=queueLimit)throw new AnalysisException(429,"JOB_QUEUE_FULL","대기열이 가득 찼습니다. 진행 중인 분석이 끝난 뒤 다시 접수해 주세요.");
        UUID id=UUID.randomUUID();var parent=Span.current().getSpanContext();String trace=parent.isValid()?"00-"+parent.getTraceId()+"-"+parent.getSpanId()+"-01":null;
        span("analysis.job.enqueue",id,()->jdbc.sql("INSERT INTO app.analysis_job(job_id,requirement_id,status,stage,request_fingerprint,trace_parent) VALUES (:id,:req,'QUEUED','WAITING',:fingerprint,:trace)")
            .param("id",id).param("req",requirementId).param("fingerprint",fingerprint(req.title()+"\n"+req.description())).param("trace",trace,java.sql.Types.VARCHAR).update());
        Span.current().setAttribute("jobId",id.toString()).setAttribute("requirementId",requirementId.toString());return publicView(row(id));
    });}
    @Transactional public Optional<ObjectNode> claim(String owner){return span("analysis.job.claim",null,()->{
        UUID token=UUID.randomUUID();var id=jdbc.sql("UPDATE app.analysis_job SET status='RUNNING',stage='LLM_ANALYSIS',started_at=clock_timestamp(),updated_at=clock_timestamp(),attempt_count=attempt_count+1,worker_id=:owner,execution_token=:token,lease_expires_at=clock_timestamp()+make_interval(secs=>:lease) WHERE job_id=(SELECT job_id FROM app.analysis_job WHERE status='QUEUED' AND (SELECT count(*) FROM app.analysis_job WHERE status='RUNNING')<:concurrency ORDER BY created_at,job_id FOR UPDATE SKIP LOCKED LIMIT 1) AND status='QUEUED' RETURNING job_id")
            .param("owner",owner).param("token",token).param("lease",leaseSeconds).param("concurrency",concurrency).query(UUID.class).optional();return id.map(this::row);
    });}
    public boolean heartbeat(UUID id,UUID token){return jdbc.sql("UPDATE app.analysis_job SET lease_expires_at=clock_timestamp()+make_interval(secs=>:lease),updated_at=clock_timestamp() WHERE job_id=:id AND execution_token=:token AND status='RUNNING'").param("lease",leaseSeconds).param("id",id).param("token",token).update()==1;}
    public void stage(UUID id,UUID token,String stage){jdbc.sql("UPDATE app.analysis_job SET stage=:stage,updated_at=clock_timestamp() WHERE job_id=:id AND execution_token=:token AND status='RUNNING' AND lease_expires_at>clock_timestamp()").param("stage",stage).param("id",id).param("token",token).update();}
    @Transactional public boolean complete(UUID id,UUID token,JsonNode output){return span("analysis.job.complete",id,()->{
        var req=jdbc.sql("SELECT requirement_id FROM app.analysis_job WHERE job_id=:id AND execution_token=:token AND status='RUNNING' AND lease_expires_at>clock_timestamp() FOR UPDATE").param("id",id).param("token",token).query(UUID.class).optional();
        if(req.isEmpty())return false;
        results.save(req.get(),output);
        jdbc.sql("UPDATE app.analysis_job SET status='SUCCEEDED',stage='COMPLETED',completed_at=clock_timestamp(),updated_at=clock_timestamp(),analysis_result_id=requirement_id,result_fingerprint=(SELECT md5(result_json::text) FROM app.requirement_analysis WHERE requirement_id=:req),lease_expires_at=NULL WHERE job_id=:id")
            .param("id",id).param("req",req.get()).update();return true;
    });}
    @Transactional public boolean fail(UUID id,UUID token,String status,String code){
        if(!Set.of("FAILED","TIMED_OUT").contains(status))throw new IllegalArgumentException("Invalid terminal status");
        return span("analysis.job.fail",id,()->jdbc.sql("UPDATE app.analysis_job SET status=:status,error_code=:code,error_message=:message,completed_at=clock_timestamp(),updated_at=clock_timestamp(),lease_expires_at=NULL WHERE job_id=:id AND execution_token=:token AND status='RUNNING'")
            .param("status",status).param("code",code).param("message",message(code)).param("id",id).param("token",token).update()==1);
    }
    /** Caller must own the global execution lock AND confirm remote capacity is idle. Never replays crashed work. */
    @Transactional public int recover(){return jdbc.sql("UPDATE app.analysis_job SET status='FAILED',error_code='JOB_WORKER_ERROR',error_message='이전 Worker가 종료되었습니다. 기존 결과는 유지됩니다. 명시적으로 재시도해 주세요.',completed_at=clock_timestamp(),updated_at=clock_timestamp(),execution_token=NULL,lease_expires_at=NULL WHERE status='RUNNING' AND lease_expires_at<clock_timestamp()").update();}
    @Transactional public ObjectNode cancel(UUID id){
        if(jdbc.sql("UPDATE app.analysis_job SET status='CANCELLED',completed_at=clock_timestamp(),updated_at=clock_timestamp() WHERE job_id=:id AND status='QUEUED'").param("id",id).update()!=1){row(id);throw new AnalysisException(409,"JOB_NOT_CANCELLABLE","실행 전 대기 Job만 취소할 수 있습니다.");}return publicView(row(id));
    }
    public ObjectNode get(UUID id){return span("analysis.job.poll",id,()->publicView(row(id)));}
    public List<ObjectNode> list(UUID req){requirements.get(req);return jdbc.sql("SELECT job_id FROM app.analysis_job WHERE requirement_id=:id ORDER BY (status IN ('QUEUED','RUNNING')) DESC,created_at DESC,job_id DESC LIMIT 20").param("id",req).query(UUID.class).list().stream().map(this::get).toList();}
    public ObjectNode summary(UUID req){
        String where=req==null?"":" AND requirement_id=:req";
        var q=jdbc.sql("SELECT jsonb_build_object('running',count(*) FILTER(WHERE status='RUNNING'),'queued',count(*) FILTER(WHERE status='QUEUED'),'succeeded',count(*) FILTER(WHERE status='SUCCEEDED' AND completed_at>clock_timestamp()-interval '24 hours'),'failed',count(*) FILTER(WHERE status IN ('FAILED','TIMED_OUT') AND completed_at>clock_timestamp()-interval '24 hours'))::text FROM app.analysis_job WHERE true"+where);if(req!=null){requirements.get(req);q.param("req",req);}
        ObjectNode out=q.query((r,n)->parse(r.getString(1))).single();var ids=jdbc.sql("SELECT job_id FROM app.analysis_job WHERE true"+where+" ORDER BY created_at DESC,job_id DESC LIMIT 20");if(req!=null)ids.param("req",req);out.set("jobs",json.valueToTree(ids.query(UUID.class).list().stream().map(this::get).toList()));return out;
    }
    private ObjectNode publicView(ObjectNode node){
        node.remove(List.of("executionToken","traceParent","workerId","leaseExpiresAt"));
        Instant end=node.path("completedAt").isNull()?Instant.now():OffsetDateTime.parse(node.path("completedAt").asText()).toInstant();
        Instant start=OffsetDateTime.parse(node.path("createdAt").asText()).toInstant();node.put("elapsedSeconds",Math.max(0,Duration.between(start,end).toSeconds()));
        if(!node.path("startedAt").isNull()){Instant running=OffsetDateTime.parse(node.path("startedAt").asText()).toInstant();node.put("queueWaitMs",Math.max(0,Duration.between(start,running).toMillis()));node.put("executionDurationMs",Math.max(0,Duration.between(running,end).toMillis()));}
        node.put("totalDurationMs",Math.max(0,Duration.between(start,end).toMillis()));
        if(node.path("resultAvailable").asBoolean())node.put("resultUrl","/api/requirements/"+node.path("requirementId").asText()+"/analysis");
        node.put("message",switch(node.path("status").asText()){case "QUEUED"->"분석 요청이 접수되어 순서를 기다립니다.";case "RUNNING"->"AI 서비스가 분석을 처리하고 있습니다. 세부 검색·추론 진행률은 제공되지 않습니다.";case "SUCCEEDED"->node.path("resultAvailable").asBoolean()?"분석과 저장이 완료되었습니다.":"분석은 완료됐으며 이후 저장 결과가 갱신되었습니다. 최신 저장 결과를 확인하세요.";case "CANCELLED"->"대기 작업이 취소되었습니다.";default->message(node.path("errorCode").asText());});return node;
    }
    public static String message(String code){return switch(code){case "LLM_TIMEOUT"->"분석 제한시간을 초과했습니다. 기존 저장 결과는 유지됩니다. 다시 시도할 수 있습니다.";case "ANALYSIS_BUSY"->"기존 분석이 아직 처리 중입니다. 종료 후 명시적으로 재시도해 주세요.";case "LLM_INVALID_OUTPUT","VALIDATION_FAILED"->"모델 출력의 형식 또는 근거 검증에 실패했습니다. 요청 내용을 확인한 뒤 재시도해 주세요.";case "RAG_RETRIEVAL_ERROR"->"관련 자료를 검색하지 못했습니다. 검색 서비스 상태를 확인해 주세요.";case "ANALYSIS_INPUT_TOO_LONG"->"요청이 검색 입력 제한을 초과했습니다. 내용을 나누어 새 요청으로 저장하세요.";case "LLM_UNAVAILABLE"->"분석 서비스 또는 로컬 모델에 연결하지 못했습니다. 서비스 상태를 확인한 뒤 다시 시도해 주세요.";default->"Worker 처리에 실패했습니다. 기존 저장 결과는 유지됩니다. 상태를 확인한 뒤 재시도해 주세요.";};}
}
