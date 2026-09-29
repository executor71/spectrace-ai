package com.example.legacyassistant.requirement;

public class RequirementNotFoundException extends RuntimeException {
    public RequirementNotFoundException() { super("요구사항을 찾을 수 없습니다."); }
}
