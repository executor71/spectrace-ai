package com.example.legacyassistant.analysis;

public class AnalysisException extends RuntimeException {
    private final int status;
    private final String code;
    public AnalysisException(int status, String code, String message) {
        super(message); this.status = status; this.code = code;
    }
    public int status() { return status; }
    public String code() { return code; }
}
