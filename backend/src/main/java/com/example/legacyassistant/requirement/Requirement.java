package com.example.legacyassistant.requirement;

import java.time.Instant;
import java.util.UUID;

public record Requirement(UUID id, String title, String description, String status, Instant createdAt) {}
