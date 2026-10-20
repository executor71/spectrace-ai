package com.example.legacyassistant.dashboard;
import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import com.sun.net.httpserver.HttpServer;
import java.net.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class ReportPublicEvaluationTest {
    @Test void onlyPublicGetResultsAreUsedAndTruthDetailsAreExcluded()throws Exception{
        var json=new ObjectMapper();var data=new ReportTest().data();UUID id=UUID.randomUUID();
        var dashboard=mock(DashboardService.class);when(dashboard.reportData(id)).thenReturn(data);
        List<String> calls=new ArrayList<>();var server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
        server.createContext("/api/",exchange->{String path=exchange.getRequestURI().getPath();calls.add(exchange.getRequestMethod()+" "+path);
            String response=path.endsWith("targets")?"{\"requirements\":[{\"requirementId\":\""+id+"\",\"caseId\":\"case\",\"datasetVersion\":\"v1\"}]}":"[{\"id\":\"run\",\"metrics\":{\"scenarioCoverage\":{\"value\":0.5,\"denominator\":2,\"missingScenarios\":[\"HIDDEN_TRUTH\"]}}}]";
            byte[] body=response.getBytes(StandardCharsets.UTF_8);exchange.getResponseHeaders().add("Content-Type","application/json");exchange.sendResponseHeaders(200,body.length);exchange.getResponseBody().write(body);exchange.close();});server.start();
        try{
            var service=new ReportService(dashboard,json,"http://127.0.0.1:"+server.getAddress().getPort());
            try(var book=new XSSFWorkbook(new ByteArrayInputStream(service.export(id)))){for(var sheet:book)for(var row:sheet)for(var cell:row)assertFalse(cell.toString().contains("HIDDEN_TRUTH"));assertEquals("저장 평가 있음",book.getSheet("요약").getRow(20).getCell(1).toString());}
            assertEquals(List.of("GET /api/evaluations/targets","GET /api/requirements/"+id+"/evaluations"),calls);verify(dashboard).reportData(id);verifyNoMoreInteractions(dashboard);
        }finally{server.stop(0);}
    }
}
