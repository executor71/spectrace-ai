package com.example.legacyassistant.dashboard;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.util.UUID;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/dashboard")
public class DashboardController {
    private final DashboardService service;
    public DashboardController(DashboardService service){this.service=service;}
    @GetMapping("/summary") public ObjectNode summary(@RequestParam(required=false) UUID requirementId){return service.dashboard(requirementId);}
    @GetMapping("/requirements") public ObjectNode requirements(@RequestParam(required=false) UUID requirementId){return service.dashboard(requirementId);}
}
