package com.example.legacyassistant.testcase;

import java.util.Map;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestControllerAdvice
@Order(Ordered.HIGHEST_PRECEDENCE)
public class TestCaseAdvice {
    @ExceptionHandler(TestCaseException.class)
    public ResponseEntity<?> handle(TestCaseException error) {
        return ResponseEntity.status(error.status()).body(Map.of("code",error.code(),"message",error.getMessage(),"fieldErrors",Map.of()));
    }
}
