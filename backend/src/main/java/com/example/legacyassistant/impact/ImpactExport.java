package com.example.legacyassistant.impact;
import com.fasterxml.jackson.databind.*;
import com.example.legacyassistant.observability.Tracing;
import org.springframework.stereotype.Service;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.apache.poi.ss.usermodel.*;
import java.io.*;
import java.util.*;

@Service
public class ImpactExport {
 private final ChangeImpactService service;private final Tracing tracing;
 public ImpactExport(ChangeImpactService service,Tracing tracing){this.service=service;this.tracing=tracing;}
 public byte[] export(UUID id){var span=tracing.tracer.spanBuilder("change_impact.export").startSpan();try(var scope=span.makeCurrent();var book=new XSSFWorkbook();var stream=new ByteArrayOutputStream()){
  JsonNode result=service.result(id);write(book,"Change Summary",List.of(service.get(id),result.path("graphStatus"),result.path("baselineStale")));write(book,"Condition Diff",result.path("conditionChanges"));write(book,"Affected APIs",result.path("affectedApis"));write(book,"Affected TestCases",result.path("affectedTestCases"));write(book,"New Test Suggestions",result.path("newTestSuggestions"));write(book,"Evidence & Graph Paths",List.of(result.path("evidenceRefs"),result.path("graphPaths")));write(book,"Review History",service.reviews(id));book.write(stream);return stream.toByteArray();
 }catch(IOException e){throw new IllegalStateException("Export failed");}finally{span.end();}}
 static void write(XSSFWorkbook book,String name,Iterable<? extends JsonNode> values){var sheet=book.createSheet(name);var header=sheet.createRow(0);header.createCell(0,CellType.STRING).setCellValue("저장된 자료 (제안 / 검토 기록)");int index=1;for(var value:values){String text=value.toPrettyString();for(int offset=0;offset<Math.max(1,text.length());offset+=30000){if(index>10000)throw ChangeImpactService.error(413,"EXPORT_LIMIT");var row=sheet.createRow(index++);row.createCell(0,CellType.STRING).setCellValue(text.substring(offset,Math.min(offset+30000,text.length())));}}sheet.setColumnWidth(0,100*256);sheet.createFreezePane(0,1);}
}
