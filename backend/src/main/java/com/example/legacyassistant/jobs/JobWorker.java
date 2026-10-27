package com.example.legacyassistant.jobs;
import com.example.legacyassistant.analysis.*;
import com.example.legacyassistant.requirement.RequirementService;
import com.example.legacyassistant.observability.Tracing;
import com.fasterxml.jackson.databind.node.ObjectNode;
import io.opentelemetry.api.trace.*;
import io.opentelemetry.context.Context;
import io.opentelemetry.context.propagation.TextMapGetter;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.scheduling.annotation.*;
import org.springframework.stereotype.Component;
import java.time.*;
import java.util.*;
import java.util.concurrent.*;
import jakarta.annotation.PreDestroy;

@Component @EnableScheduling
@ConditionalOnProperty(name="analysis.jobs.enabled",havingValue="true",matchIfMissing=true)
public class JobWorker {
 @org.springframework.beans.factory.annotation.Autowired private com.example.legacyassistant.impact.ChangeImpactService impacts;
 private final JobStore store;private final AnalysisGate gate;private final AnalysisCapacity capacity;private final AnalysisClient client;
 private final AnalysisValidator validator;private final RequirementService requirements;private final Tracing tracing;private final long timeoutSeconds;
 private final String owner=UUID.randomUUID().toString();
 private final ScheduledExecutorService heartbeat=Executors.newSingleThreadScheduledExecutor(r->{Thread t=new Thread(r,"analysis-lease");t.setDaemon(true);return t;});
 public JobWorker(JobStore store,AnalysisGate gate,AnalysisCapacity capacity,AnalysisClient client,AnalysisValidator validator,RequirementService requirements,Tracing tracing,@Value("${analysis.jobs.timeout-seconds:660}")long timeoutSeconds){
  if(timeoutSeconds<1)throw new IllegalArgumentException("Job timeout must be positive");this.store=store;this.gate=gate;this.capacity=capacity;this.client=client;this.validator=validator;this.requirements=requirements;this.tracing=tracing;this.timeoutSeconds=timeoutSeconds;
 }
 @Scheduled(fixedDelayString="${analysis.jobs.poll-ms:1000}") public void tick(){
  try(var lease=gate.tryAcquire()){
   if(lease==null)return;
   var state=capacity.state();if(state==AnalysisCapacity.State.BUSY)return;
   if(state==AnalysisCapacity.State.IDLE)store.recover();
   store.claim(owner).ifPresent(job->execute(job,lease,state));
  }catch(Exception ignored){/* Durable state remains recoverable. Never log inputs or retry a live execution. */}
 }
 private Context linked(ObjectNode job){String parent=job.path("traceParent").asText("");return Tracing.PROPAGATOR.extract(Context.root(),Map.of("traceparent",parent),new TextMapGetter<Map<String,String>>(){public Iterable<String> keys(Map<String,String> c){return c.keySet();}public String get(Map<String,String> c,String key){return c.get(key);}});}
 private void execute(ObjectNode job,AnalysisGate.Lease lease,AnalysisCapacity.State initial){
  UUID id=UUID.fromString(job.path("jobId").asText()),req=UUID.fromString(job.path("requirementId").asText()),token=UUID.fromString(job.path("executionToken").asText());
  Span span=tracing.tracer.spanBuilder("analysis.job.execute").setNoParent().addLink(Span.fromContext(linked(job)).getSpanContext()).startSpan();long start=System.nanoTime();
  span.setAttribute("jobId",id.toString()).setAttribute("requirementId",req.toString()).setAttribute("attemptCount",job.path("attemptCount").asLong());
  span.setAttribute("jobType",job.path("jobType").asText("REQUIREMENT_ANALYSIS"));if(job.hasNonNull("impactId"))span.setAttribute("impactId",job.path("impactId").asText());
  var renewal=heartbeat.scheduleAtFixedRate(()->{try{if(lease.valid())store.heartbeat(id,token);}catch(Exception ignored){}},1,1,TimeUnit.SECONDS);
  try(var scope=span.makeCurrent()){
   span.setAttribute("queueWaitMs",Math.max(0,Duration.between(OffsetDateTime.parse(job.path("createdAt").asText()).toInstant(),OffsetDateTime.parse(job.path("startedAt").asText()).toInstant()).toMillis()));
   try{
    if(initial==AnalysisCapacity.State.UNAVAILABLE)throw new AnalysisException(503,"LLM_UNAVAILABLE","Unavailable");
    com.fasterxml.jackson.databind.JsonNode output;int busyAttempts=0;
    while(true){
     if(expired(start))throw new AnalysisException(504,"LLM_TIMEOUT","Timeout");
     try{output=job.path("jobType").asText().equals("CHANGE_IMPACT_ANALYSIS")?impacts.analyze(UUID.fromString(job.path("impactId").asText())):client.analyze(requirements.get(req));break;}
     catch(AnalysisException busy){if(!busy.code().equals("ANALYSIS_BUSY"))throw busy;
      if(++busyAttempts>=3)throw busy;
      // A sync/test generation caller may win the Python slot after the idle probe.
      while(capacity.state()!=AnalysisCapacity.State.IDLE){if(expired(start))throw new AnalysisException(504,"LLM_TIMEOUT","Timeout");sleep();}
     }
    }
    if(!lease.valid())throw new AnalysisException(503,"JOB_WORKER_ERROR","Ownership lost");
    if(expired(start))throw new AnalysisException(504,"LLM_TIMEOUT","Timeout");
    store.stage(id,token,"VALIDATING_OUTPUT");
    try{if(!job.path("jobType").asText().equals("CHANGE_IMPACT_ANALYSIS"))validator.validate(req,output);}catch(AnalysisException invalid){throw new AnalysisException(502,"VALIDATION_FAILED","Validation failed");}
    store.stage(id,token,"SAVING_RESULT");
    if(!store.complete(id,token,output))throw new AnalysisException(503,"JOB_WORKER_ERROR","Stale owner");
    span.setAttribute("status","SUCCEEDED").setAttribute("stage","COMPLETED");
   }catch(Exception error){
    String code=error instanceof AnalysisException e?switch(e.code()){case "INVALID_ANALYSIS_OUTPUT"->"LLM_INVALID_OUTPUT";case "ANALYSIS_UNAVAILABLE"->"LLM_UNAVAILABLE";default->e.code();}:"JOB_WORKER_ERROR";
    // No cancellation-by-interrupt: wait until the original HTTP execution relinquishes the Python slot.
    if(code.equals("LLM_TIMEOUT"))while(capacity.state()!=AnalysisCapacity.State.IDLE && lease.valid())sleep();
    String status=code.equals("LLM_TIMEOUT")?"TIMED_OUT":"FAILED";store.fail(id,token,status,code);
    span.setStatus(StatusCode.ERROR).setAttribute("status",status).setAttribute("errorCode",code).setAttribute("stage",job.path("stage").asText());
   }
  }finally{renewal.cancel(false);span.setAttribute("executionDurationMs",(System.nanoTime()-start)/1_000_000);span.setAttribute("totalDurationMs",Math.max(0,Duration.between(OffsetDateTime.parse(job.path("createdAt").asText()).toInstant(),Instant.now()).toMillis()));span.end();}
 }
 private boolean expired(long start){return (System.nanoTime()-start)/1_000_000_000L>=timeoutSeconds;}
 private static void sleep(){try{Thread.sleep(1000);}catch(InterruptedException e){Thread.currentThread().interrupt();throw new IllegalStateException("Worker interrupted");}}
 @PreDestroy public void close(){heartbeat.shutdownNow();}
}
