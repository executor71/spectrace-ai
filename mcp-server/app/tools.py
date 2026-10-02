from collections import Counter
from uuid import UUID
from .clients import GatewayError

def select(data, keys):
    return {key: data[key] for key in keys if key in data}

def project_evaluation(report):
    """Allow only published measurements, never raw evaluation snapshots/truth."""
    metrics = report["metrics"]
    summary = ("numerator", "denominator", "value", "status")
    return {
        "retrievalMetrics": {"recallAt5": select(metrics["recallAt5"], (*summary, "topK", "retrievedChunkCount"))},
        "testScenarioCoverage": select(metrics["scenarioCoverage"], summary),
        "testCaseValidity": select(metrics["testCaseValidity"], (*summary, "failedCount", "unknownCount")),
        "missingScenarios": [select(item, ("scenarioId", "category", "description"))
            for item in metrics["scenarioCoverage"].get("missingScenarios", [])],
        "evaluationMetadata": select(report, ("id", "requirementId", "createdAt", "metricVersion", "engineHash", "contentMode", "status"))
    }

class Gateway:
    def __init__(self, services):
        self.services = services

    async def search_knowledge(self, arguments):
        query, top_k, strategy = arguments["query"], arguments.get("topK", 5), arguments.get("strategy", "VECTOR")
        if strategy == "VECTOR":
            hits = await self.services.request("ai", "POST", "/internal/v1/search", {"query": query, "topK": top_k})
        else:
            data = await self.services.request("retrieval", "POST", "/internal/v1/retrieval",
                {"queryId": "mcp-search", "queryText": query, "strategy": strategy})
            hits = data["results"][:top_k]
        return {"strategy": strategy, "hits": [dict(
            {key: hit[key] for key in ("documentId", "chunkId", "documentType", "section", "contentSnippet")},
            rank=index, score=hit["score"] if strategy == "VECTOR" else hit["fusionScore"])
            for index, hit in enumerate(hits, 1)]}

    async def analyze_requirement(self, arguments):
        identifier = str(UUID(arguments["requirementId"]))
        path = f"/api/requirements/{identifier}"
        await self.services.request("backend", "GET", path)
        analysis = await self.services.request("backend", "GET", path + "/analysis", missing=True)
        source = "SAVED"
        if analysis is None:
            analysis = await self.services.request("backend", "POST", path + "/analysis")
            source = "GENERATED"
        return {"analysis": analysis, "analysisSource": source}

    async def get_test_cases(self, arguments):
        identifier = str(UUID(arguments["requirementId"]))
        batch = await self.services.request("backend", "GET", f"/api/requirements/{identifier}/test-cases")
        cases = []
        for case in batch["testCases"]:
            test_id = str(UUID(case["testCaseId"]))
            assessment = await self.services.request("backend", "GET", f"/api/test-cases/{test_id}/execution-eligibility")
            # Keep generation/review content intact; authoritative runtime flags come from Phase 7.
            cases.append(dict(case, generationExecutable=case["executable"],
                **select(assessment, ("executable", "fixtureReady", "executionEligible", "approvalStatus")),
                executionAssessment=assessment))
        return dict(batch, testCases=cases)

    async def get_evaluation_result(self, arguments):
        identifier = str(UUID(arguments["requirementId"]))
        reports = await self.services.request("evaluation", "GET", f"/api/requirements/{identifier}/evaluations")
        if not reports:
            raise GatewayError("EVALUATION_NOT_FOUND", "evaluation")
        if reports[0].get("status") != "COMPLETED":
            raise GatewayError("EVALUATION_NOT_COMPLETED", "evaluation")
        return project_evaluation(reports[0])

    async def requirement_resource(self, identifier):
        path = f"/api/requirements/{str(UUID(identifier))}"
        requirement = await self.services.request("backend", "GET", path)
        analysis = await self.services.request("backend", "GET", path + "/analysis", missing=True)
        batch = await self.services.request("backend", "GET", path + "/test-cases", missing=True)
        cases = batch["testCases"] if batch else []
        return {"requirement": requirement, "analysisExists": analysis is not None,
            "testCaseCount": len(cases), "reviewSummary": dict(Counter(c["approvalStatus"] for c in cases))}

    async def execute_approved_test(self, arguments):
        identifier = str(UUID(arguments["testCaseId"]))
        # Never pre-authorize here. Existing service rechecks persisted approval,
        # fixture readiness and allowlist under its own transaction/locks.
        return await self.services.request("backend", "POST", f"/api/test-cases/{identifier}/executions")
