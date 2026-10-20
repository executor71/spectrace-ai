package com.example.legacyassistant.dashboard;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import java.io.*;
import java.time.*;
import java.util.*;
import org.apache.poi.ss.usermodel.*;
import org.apache.poi.ss.util.CellRangeAddress;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;
import org.springframework.web.server.ResponseStatusException;

@Service
public class ReportService {
    private final DashboardService dashboard;private final RestClient evaluations;private final ObjectMapper json;
    public ReportService(DashboardService dashboard,ObjectMapper json,@Value("${EVALUATION_SERVICE_URL:http://evaluation-service:8090}")String url){
        this.dashboard=dashboard;this.json=json;
        var factory=new SimpleClientHttpRequestFactory();factory.setConnectTimeout(Duration.ofSeconds(3));factory.setReadTimeout(Duration.ofSeconds(10));
        evaluations=RestClient.builder().baseUrl(url).requestFactory(factory).build();
    }
    public byte[] export(UUID id) {
        ObjectNode data=dashboard.reportData(id);ObjectNode evaluation=json.createObjectNode();
        try {
            JsonNode targets=evaluations.get().uri("/api/evaluations/targets").retrieve().body(JsonNode.class);
            boolean registered=false;
            if(targets==null || !targets.path("requirements").isArray())throw new IllegalStateException("Invalid evaluation registration response");
            for(var target:targets.path("requirements"))if(target.path("requirementId").asText().equals(id.toString())){registered=true;evaluation.set("target",target);}
            evaluation.put("status",registered?"미평가":"평가 대상 미등록");
            if(registered){JsonNode runs=evaluations.get().uri("/api/requirements/{id}/evaluations",id).retrieve().body(JsonNode.class);
                if(runs==null || !runs.isArray())throw new IllegalStateException("Invalid evaluation results response");
                DashboardService.limit(runs.size());evaluation.set("runs",runs);if(!runs.isEmpty())evaluation.put("status","저장 평가 있음");}
        }catch(Exception unavailable){evaluation.removeAll();evaluation.put("status","평가 조회 실패: 등록 여부 및 결과 확인 불가 (다른 저장 데이터는 정상 내보냄)");}
        data.set("evaluation",evaluation);return workbook(data);
    }
    static String text(JsonNode n) {
        if(n==null||n.isNull()||n.isMissingNode())return "";
        if(n.isValueNode())return n.asText();
        if(n.isArray()){var list=new ArrayList<String>();for(var item:n)list.add(text(item));return String.join("\n",list);}
        var list=new ArrayList<String>();n.fields().forEachRemaining(e->list.add(e.getKey()+": "+text(e.getValue())));return String.join("\n",list);
    }
    static String api(JsonNode n){return n.isMissingNode()||n.isNull()?"":n.toPrettyString();}
    static class Writer {
        final XSSFWorkbook book;final CellStyle header,body,number,date,green,red;int totalRows=0;long chars=0;
        Writer(XSSFWorkbook book){this.book=book;body=book.createCellStyle();body.setWrapText(true);body.setVerticalAlignment(VerticalAlignment.TOP);
            header=book.createCellStyle();header.cloneStyleFrom(body);header.setFillForegroundColor(IndexedColors.DARK_BLUE.getIndex());header.setFillPattern(FillPatternType.SOLID_FOREGROUND);
            var font=book.createFont();font.setBold(true);font.setColor(IndexedColors.WHITE.getIndex());header.setFont(font);
            number=book.createCellStyle();number.cloneStyleFrom(body);number.setDataFormat(book.createDataFormat().getFormat("#,##0.####"));
            date=book.createCellStyle();date.cloneStyleFrom(body);date.setDataFormat(book.createDataFormat().getFormat("yyyy-mm-dd hh:mm:ss"));
            green=book.createCellStyle();green.cloneStyleFrom(body);green.setFillForegroundColor(IndexedColors.LIGHT_GREEN.getIndex());green.setFillPattern(FillPatternType.SOLID_FOREGROUND);
            red=book.createCellStyle();red.cloneStyleFrom(body);red.setFillForegroundColor(IndexedColors.ROSE.getIndex());red.setFillPattern(FillPatternType.SOLID_FOREGROUND);
        }
        Sheet sheet(String name,String...headers){Sheet sheet=book.createSheet(name);var row=sheet.createRow(0);for(int i=0;i<headers.length;i++){var cell=row.createCell(i,CellType.STRING);cell.setCellValue(headers[i]);cell.setCellStyle(header);sheet.setColumnWidth(i,(i==0?40:32)*256);}sheet.createFreezePane(0,1);return sheet;}
        void row(Sheet sheet,Object...values){
            int parts=1;List<List<String>> strings=new ArrayList<>();
            for(Object value:values){
                if(value instanceof String s){
                    chars+=s.length();List<String> slices=new ArrayList<>();
                    for(int start=0;start<s.length();){int end=Math.min(start+30000,s.length());
                        if(end<s.length()&&Character.isHighSurrogate(s.charAt(end-1))&&Character.isLowSurrogate(s.charAt(end)))end--;
                        slices.add(s.substring(start,end));start=end;
                    }
                    if(slices.isEmpty())slices.add("");strings.add(slices);parts=Math.max(parts,slices.size());
                }else strings.add(null);
            }
            if(chars>20_000_000)throw new ResponseStatusException(HttpStatus.PAYLOAD_TOO_LARGE,"보고서 원문 2천만자 한도 초과");
            for(int part=0;part<parts;part++){
                DashboardService.limit(++totalRows);var row=sheet.createRow(sheet.getLastRowNum()+1);
                for(int i=0;i<values.length;i++){
                    Object value=values[i];var cell=row.createCell(i);cell.setCellStyle(body);
                    if(value instanceof Number n){cell.setCellValue(n.doubleValue());cell.setCellStyle(number);}
                    else if(value instanceof Instant instant){cell.setCellValue(LocalDateTime.ofInstant(instant,ZoneId.of("Asia/Seoul")));cell.setCellStyle(date);}
                    else {String s=Objects.toString(value,"");var slices=strings.get(i);String chunk=slices!=null&&slices.size()>1?(part<slices.size()?slices.get(part):""):s;
                        if(parts>1&&i==0)chunk+=" [분할 "+(part+1)+"/"+parts+"]";
                        // Explicit STRING cells: user input never becomes a formula, link, or external relationship.
                        cell.setCellValue(chunk);if(Set.of("PASS","APPROVED").contains(s))cell.setCellStyle(green);if(Set.of("FAIL","ERROR","REJECTED").contains(s))cell.setCellStyle(red);
                    }
                }
            }
        }
        void finish(){for(Sheet sheet:book){if(sheet.getLastRowNum()>0)sheet.setAutoFilter(new CellRangeAddress(0,sheet.getLastRowNum(),0,sheet.getRow(0).getLastCellNum()-1));}}
    }
    private static Object time(JsonNode value){try{return Instant.parse(value.asText());}catch(Exception ignored){return text(value);}}
    public static byte[] workbook(ObjectNode data){
        try(var book=new XSSFWorkbook();var output=new ByteArrayOutputStream()){
            Writer w=new Writer(book);JsonNode req=data.path("requirement"),batch=data.path("batch"),analysis=data.path("analysis"),counts=data.path("counts"),evaluation=data.path("evaluation");
            var summary=w.sheet("요약","항목","값","기준 / 안내");
            w.row(summary,"프로젝트명","SpecTrace AI","합성 PoC 데이터 · 실제 운영 성능으로 일반화 불가");
            w.row(summary,"요구사항 ID",text(req.path("id")),"");w.row(summary,"요구사항 제목",text(req.path("title")),"");
            w.row(summary,"보고서 생성 시각",Instant.now(),"Asia/Seoul (UTC+09:00)");w.row(summary,"데이터 기준 시점",time(data.path("queriedAt")),"app 데이터는 REPEATABLE_READ 스냅샷 · 평가는 후속 공개 GET 조회");
            w.row(summary,"내보내기 범위","선택한 요구사항 1건","현재 생성 batch·현재 검토본 + 요구사항의 보존된 모든 실행 이력 + 공개 저장 평가 지표");
            w.row(summary,"현재 생성 batch",text(batch.path("generationId")),"과거 batch TC는 현재 통계 제외");
            w.row(summary,"분석 변경 여부",text(batch.path("stale")),"현재 batch와 저장 분석 비교. 최신 실행 가능성은 조회하지 않음");
            Map<String,String> labels=Map.ofEntries(Map.entry("total","현재 생성 TC"),Map.entry("DRAFT","검토 대기"),Map.entry("APPROVED","승인"),Map.entry("REJECTED","반려"),Map.entry("PASS","일반 실행 PASS TC"),Map.entry("FAIL","일반 실행 FAIL TC"),Map.entry("ERROR","일반 실행 ERROR TC"),Map.entry("NOT_RUN","일반 실행 미실행 TC"),Map.entry("SYNTHETIC","의도적 결함 실행 TC"));
            for(String key:List.of("total","DRAFT","APPROVED","REJECTED","PASS","FAIL","ERROR","NOT_RUN","SYNTHETIC"))w.row(summary,labels.get(key),counts.path(key).asInt(),"건 · 現 batch / 現 revision의 최신 일반 실행 기준. 의도적 결함 별도·일반 실행 통계 제외");
            w.row(summary,"일반 실행 PASS 비율",counts.path("passRatio").isNull()?"집계 대상 없음":counts.path("passRatio").asDouble(),"PASS / (PASS + FAIL). ERROR·미실행·의도적 결함 제외. AI 정확도·커버리지가 아님");
            w.row(summary,"실행 차단","미조회","차단 이력은 저장 실행 결과가 아니며 FAIL과 합산하지 않음");
            w.row(summary,"평가 여부",text(evaluation.path("status")),"과거 평가와 현재 revision의 일치 여부는 평가결과 시트 참고");
            w.row(summary,"보존 실행 횟수",data.path("executions").size(),"반복 실행 포함. TC 수와 다른 모수");
            w.row(summary,"업무시간 절감률","미측정","");
            var a=w.sheet("요구사항 분석","항목 식별자","항목","내용","근거 chunkId");
            w.row(a,text(req.path("id")),"요구사항 원문",text(req.path("description")),"");
            if(analysis.isEmpty())w.row(a,text(req.path("id")),"저장 분석 없음","분석을 실행하지 않고 저장 상태만 내보냄","");
            String[] fields={"confirmedConditions","ambiguousExpressions","missingConditions","clarificationQuestions","relatedApis","relatedBusinessRules"};String[] titles={"확인된 조건","모호한 표현","누락 의심 조건","확인 질문","관련 API","관련 업무규칙"};
            for(int i=0;i<fields.length;i++){int ordinal=0;for(JsonNode item:analysis.path(fields[i])){w.row(a,fields[i]+"["+(ordinal++)+"]",titles[i],item.isTextual()?item.asText():text(item.path(i==4?"api":"text")),text(item.path("chunkId")));}}
            var t=w.sheet("테스트케이스","TC ID","유형","시나리오","사전조건","입력값","실행 절차","기대결과","현재 승인 상태","수정 여부","reviewRevision","검토자 표시값","검토 시각 (Asia/Seoul)","검토 의견","생성 시점 executable 기록","내용 출처","생성 batch");
            if(!batch.path("testCases").isArray()||batch.path("testCases").isEmpty())w.row(t,text(req.path("id")),"저장된 TC 없음");
            for(JsonNode tc:batch.path("testCases"))w.row(t,text(tc.path("testCaseId")),text(tc.path("type")),text(tc.path("scenario")),text(tc.path("preconditions")),api(tc.path("input")),text(tc.path("steps")),text(tc.at("/expectedResult/description"))+"\n"+api(tc.at("/expectedResult/assertions")),text(tc.path("approvalStatus")),tc.path("modified").asBoolean()?"수정됨":"원본",tc.path("reviewRevision").asLong(),text(tc.path("reviewer")),time(tc.path("reviewedAt")),text(tc.path("reviewComment")),text(tc.at("/generatedContent/executable")),tc.path("modified").asBoolean()?"사용자 수정 현재 검토본":"AI 생성 원본 (현재 검토 상태)",text(batch.path("generationId")));
            var e=w.sheet("실행결과","실행 ID","TC ID","실행 당시 revision","실행 시각 (Asia/Seoul)","API ID","Expected (실행 시점 저장)","Actual (실행 시점 저장)","결과","불일치 항목","소요시간 (ms)","의도적 결함 여부","실행 batch","현재 검토본과의 관계");
            for(JsonNode run:data.path("executions")){
                boolean current=false;for(JsonNode tc:batch.path("testCases"))if(tc.path("testCaseId").equals(run.path("testCaseId"))&&tc.path("reviewRevision").asLong()==run.path("testCaseRevision").asLong(-1)&&batch.path("generationId").equals(run.path("generationId")))current=true;
                w.row(e,text(run.path("executionId")),text(run.path("testCaseId")),run.path("testCaseRevision").asLong(),time(run.path("executedAt")),text(run.path("apiId")),api(run.path("expected")),api(run.path("actual")),text(run.path("result")),text(run.path("mismatches")),run.path("durationMs").asLong(),run.path("syntheticDefect").asBoolean()?"의도적 결함":"일반 실행",text(run.path("generationId")),current?"현재 batch / revision 일치":"과거 batch 또는 revision (현재 통계 제외)");
            }
            if(data.path("executions").isEmpty())w.row(e,text(req.path("id")),"저장된 실행결과 없음");
            var links=w.sheet("근거 연결","TC / 분석 항목 식별자","documentId","chunkId","문서 유형","section","공개 근거 내용","출처");
            for(JsonNode source:analysis.path("evidence")){
                var owners=new ArrayList<String>();
                for(String field:fields){int ordinal=0;for(JsonNode item:analysis.path(field)){
                    if(item.path("chunkId").equals(source.path("chunkId")))owners.add(field+"["+ordinal+"]");ordinal++;
                }}
                evidence(w,links,owners.isEmpty()?"analysis.evidence["+text(source.path("chunkId"))+"]":String.join("\n",owners),source,"현재 저장 분석");
            }
            for(JsonNode tc:batch.path("testCases"))for(JsonNode ref:tc.path("evidence")){
                JsonNode found=ref;for(JsonNode source:batch.at("/sourceAnalysis/evidence"))if(source.path("chunkId").equals(ref.path("chunkId"))&&source.path("documentId").equals(ref.path("documentId")))found=source;
                evidence(w,links,text(tc.path("testCaseId")),found,"생성 시점 저장 분석 근거");
            }
            var ev=w.sheet("평가결과","평가 ID / 항목","평가셋 식별자","평가셋 버전","평가 시각 (Asia/Seoul)","지표명","값 / 상태","표본 수 (분모)","지표 버전","평가 내용 출처","생성 batch","입력 스냅샷 식별자","현재 검토본과의 관계");
            w.row(ev,"평가 상태",text(evaluation.at("/target/caseId")),text(evaluation.at("/target/datasetVersion")),"","",text(evaluation.path("status")),"","","","","","검토 revision 매핑은 기존 공개 평가 결과에 없음. 정확한 revision 일치는 확인 불가");
            for(JsonNode run:evaluation.path("runs")){
                String relation=run.hasNonNull("generationId")&&!run.path("generationId").equals(batch.path("generationId"))?"과거 생성 batch 평가 (현재 검토본 평가 아님)":"revision 일치 확인 불가: 공개 결과에 revision 매핑 없음";
                for(String metric:List.of("recallAt5","scenarioCoverage","testCaseValidity")){
                    JsonNode value=run.path("metrics").path(metric);Object score=value.path("value").isNumber()?value.path("value").asDouble():"집계 대상 없음 / "+run.path("status").asText();
                    w.row(ev,text(run.path("id")),text(run.at("/dataset/caseId")),text(run.at("/dataset/datasetVersion")),time(run.path("createdAt")),metric,score,value.path("denominator").isNumber()?value.path("denominator").asInt():"",text(run.path("metricVersion")),text(run.path("contentMode")),text(run.path("generationId")),text(run.path("inputHash")),relation);
                }
            }
            w.finish();book.write(output);if(output.size()>10*1024*1024)throw new ResponseStatusException(HttpStatus.PAYLOAD_TOO_LARGE,"XLSX 10 MiB 한도 초과");return output.toByteArray();
        }catch(IOException ex){throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR,"Excel 생성 실패",ex);}
    }
    private static void evidence(Writer w,Sheet sheet,String owner,JsonNode source,String origin){w.row(sheet,owner,text(source.path("documentId")),text(source.path("chunkId")),text(source.path("documentType")),text(source.path("section")),text(source.path("contentSnippet")),origin);}
}
