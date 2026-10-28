package com.example.legacyassistant.observability;

import com.example.legacyassistant.analysis.AnalysisException;
import com.example.legacyassistant.testcase.TestCaseException;
import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.*;
import org.springframework.stereotype.Component;
import java.util.UUID;

@Aspect @Component
public class WorkflowSummaryAspect {
    @Around("execution(public * com.example.legacyassistant.analysis.AnalysisService.create(..)) || execution(public * com.example.legacyassistant.testcase.TestCaseService.generate(..))")
    public Object observe(ProceedingJoinPoint point) throws Throwable {
        String workflow=point.getSignature().getName().equals("generate")?"TEST_GENERATION":"ANALYSIS";
        try(var summary=WorkflowSummary.open(workflow,null,(UUID)point.getArgs()[0])){
            try{Object result=point.proceed();WorkflowSummary.completed();return result;}
            catch(Throwable error){
                WorkflowSummary.failed(error instanceof AnalysisException e?e.code():error instanceof TestCaseException e?e.code():"WORKFLOW_ERROR");
                throw error;
            }
        }
    }
}
