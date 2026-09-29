package com.example.legacyassistant.requirement;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record CreateRequirementRequest(
        @NotBlank(message = "제목을 입력해 주세요.")
        @Size(max = 200, message = "제목은 200자 이하로 입력해 주세요.") String title,
        @NotBlank(message = "내용을 입력해 주세요.")
        @Size(max = 10000, message = "내용은 10000자 이하로 입력해 주세요.") String description) {
    public CreateRequirementRequest {
        title = title == null ? null : title.strip();
        description = description == null ? null : description.strip();
    }
}
