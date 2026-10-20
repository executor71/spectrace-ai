package com.example.legacyassistant.dashboard;
import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import java.io.*;
import java.util.*;
import org.apache.poi.ss.usermodel.*;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class ReportTest {
    final ObjectMapper json=new ObjectMapper();
    ObjectNode tc(String id,long revision){return json.createObjectNode().put("testCaseId",id).put("reviewRevision",revision).put("approvalStatus","DRAFT");}
    ObjectNode run(String tc,String gen,long revision,String status,boolean defect){return json.createObjectNode().put("testCaseId",tc).put("generationId",gen).put("testCaseRevision",revision).put("result",status).put("syntheticDefect",defect);}
    @Test void repeatedRunsCountUniqueCurrentCasesAndIgnoreOldRevisionsAndBatches(){
        var batch=json.createObjectNode().put("generationId","new");batch.putArray("testCases").add(tc("a",2)).add(tc("b",3)).add(tc("c",1));
        var runs=List.<JsonNode>of(run("a","new",2,"PASS",false),run("a","new",2,"FAIL",false),run("b","new",2,"FAIL",false),run("c","old",1,"PASS",false),run("c","new",1,"FAIL",true));
        var counts=DashboardService.counts(json,batch,runs,json.createArrayNode(),"req","title");
        assertEquals(3,counts.path("total").asInt());assertEquals(1,counts.path("PASS").asInt());assertEquals(0,counts.path("FAIL").asInt());assertEquals(2,counts.path("NOT_RUN").asInt());assertEquals(1,counts.path("SYNTHETIC").asInt());
    }
    @Test void emptyDenominatorIsNotZeroPercent(){var batch=json.createObjectNode();batch.putArray("testCases").add(tc("a",1));assertTrue(DashboardService.counts(json,batch,List.of(),json.createArrayNode(),"req","title").path("passRatio").isNull());}
    ObjectNode data(){var d=json.createObjectNode().put("queriedAt","2026-10-20T01:00:00Z");d.putObject("requirement").put("id","00000000-0000-0000-0000-000000000001").put("title","=1+1").put("description","한글\n특수문자 + - @ & < > 😀");d.putObject("batch");d.putObject("analysis");d.putObject("counts").putNull("passRatio");d.putArray("executions");d.putObject("evaluation").put("status","평가 대상 미등록");return d;}
    @Test void reopenWorkbookPreservesUnicodeAndNeverCreatesFormulasOrExternalLinks()throws Exception{
        var d=data();var t=d.withObject("/batch").putArray("testCases").addObject();t.put("testCaseId","tc").put("scenario","한글".repeat(20000)).put("reviewComment","@SUM(1+1)").put("reviewRevision",42);t.putObject("input").put("formula","+1+1");t.putObject("expectedResult").put("description","-2+2");
        try(var book=new XSSFWorkbook(new ByteArrayInputStream(ReportService.workbook(d)))){
            assertEquals(List.of("요약","요구사항 분석","테스트케이스","실행결과","근거 연결","평가결과"),java.util.stream.IntStream.range(0,6).mapToObj(book::getSheetName).toList());
            assertEquals("=1+1",book.getSheet("요약").getRow(3).getCell(1).getStringCellValue());
            assertEquals(2,book.getSheet("테스트케이스").getLastRowNum());
            String restored=book.getSheet("테스트케이스").getRow(1).getCell(2).getStringCellValue()+book.getSheet("테스트케이스").getRow(2).getCell(2).getStringCellValue();assertEquals("한글".repeat(20000),restored);
            for(Sheet sheet:book){assertNotNull(sheet.getPaneInformation());for(Row row:sheet)for(Cell cell:row){assertNotEquals(CellType.FORMULA,cell.getCellType());assertNull(cell.getHyperlink());}}
            assertTrue(book.getExternalLinksTable().isEmpty());assertEquals(CellType.NUMERIC,book.getSheet("테스트케이스").getRow(1).getCell(9).getCellType());
        }
    }
    @Test void limitsFailExplicitly(){assertThrows(org.springframework.web.server.ResponseStatusException.class,()->DashboardService.limit(10001));}
    @Test void longUnicodeNeverSplitsSurrogatePairs()throws Exception{
        var d=data();String input="a".repeat(29999)+"😀"+"나".repeat(30000);
        d.withObject("/requirement").put("description",input);
        try(var book=new XSSFWorkbook(new ByteArrayInputStream(ReportService.workbook(d)))){
            var sheet=book.getSheet("요구사항 분석");String restored="";for(int i=1;i<=3;i++)restored+=sheet.getRow(i).getCell(2).getStringCellValue();assertEquals(input,restored);
        }
    }
    @Test void evaluationExportDoesNotIncludeHiddenScenarioDetails()throws Exception{
        var d=data();var r=d.withObject("/evaluation").putArray("runs").addObject().put("id","run").put("generationId","old");var metrics=r.putObject("metrics");metrics.putObject("scenarioCoverage").put("value",0.5).put("denominator",4).put("missingScenarios","SECRET_GROUND_TRUTH");
        try(var book=new XSSFWorkbook(new ByteArrayInputStream(ReportService.workbook(d)))){for(Sheet sheet:book)for(Row row:sheet)for(Cell cell:row)assertFalse(cell.toString().contains("SECRET_GROUND_TRUTH"));}
    }
}
