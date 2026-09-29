package com.example.legacyassistant.requirement;

import java.time.Instant;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class RequirementServiceTest {
    @Mock RequirementRepository repository;

    @Test void createsWithServerGeneratedIdAndNormalizedInput() {
        when(repository.insert(any(UUID.class), eq("제목"), eq("내용")))
            .thenAnswer(i -> new Requirement(i.getArgument(0), i.getArgument(1), i.getArgument(2), "DRAFT", Instant.now()));
        var service = new RequirementService(repository);
        var first = service.create(new CreateRequirementRequest("  제목  ", "\n내용\n"));
        var second = service.create(new CreateRequirementRequest("제목", "내용"));
        assertNotNull(first.id());
        assertNotEquals(first.id(), second.id());
        assertEquals("DRAFT", first.status());
        verify(repository, times(2)).insert(any(UUID.class), eq("제목"), eq("내용"));
    }

    @Test void returnsExistingRequirement() {
        UUID id = UUID.randomUUID();
        var result = new Requirement(id, "title", "description", "DRAFT", Instant.now());
        when(repository.findById(id)).thenReturn(Optional.of(result));
        assertEquals(result, new RequirementService(repository).get(id));
    }

    @Test void missingRequirementThrowsNotFound() {
        UUID id = UUID.randomUUID();
        when(repository.findById(id)).thenReturn(Optional.empty());
        assertThrows(RequirementNotFoundException.class, () -> new RequirementService(repository).get(id));
    }
}
