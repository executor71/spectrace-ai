package com.example.legacyassistant.dashboard;
import java.nio.charset.StandardCharsets;
import java.time.*;
import java.time.format.DateTimeFormatter;
import java.util.UUID;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;

@RestController
public class ReportController {
    private final ReportService reports;public ReportController(ReportService reports){this.reports=reports;}
    @GetMapping("/api/requirements/{id}/reports/test-report.xlsx")
    public ResponseEntity<byte[]> download(@PathVariable UUID id){
        byte[] bytes=reports.export(id);
        String filename="SpecTrace_AI_"+id+"_검증보고서_"+ZonedDateTime.now(ZoneId.of("Asia/Seoul")).format(DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss"))+".xlsx";
        return ResponseEntity.ok().contentType(MediaType.parseMediaType("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))
            .header(HttpHeaders.CONTENT_DISPOSITION,ContentDisposition.attachment().filename(filename,StandardCharsets.UTF_8).build().toString())
            .header(HttpHeaders.CACHE_CONTROL,"no-store").contentLength(bytes.length).body(bytes);
    }
}
