# Phase 11 graph extension

Neo4j stores a disposable relationship projection; PostgreSQL remains authoritative.
The projection reads saved Requirement/Analysis/TestCase/Execution REST responses and
the frozen Phase 2 knowledge export. It has no PostgreSQL or evaluation credentials.

Add `-f compose.phase11.yaml` to the existing Phase 10 Compose command, then start
`neo4j graph-service`. The local synthetic-only Neo4j password can be overridden by
`PHASE11_NEO4J_PASSWORD`. Bolt and Neo4j Browser are not published to the host.

Explicit full-scope sync:

```powershell
docker exec master-graph-service-1 python -m app.sync
```

`data/scope.json` contains the three existing demonstration Requirement UUIDs.
Edit this operator-owned scope and rebuild to include more requirements. Each sync
re-reads current stored business results. `data/knowledge.json` is the frozen 27-chunk
Phase 2 corpus export, not evaluation ground truth. Re-export it explicitly when the
knowledge version changes; this phase does not implement CDC.

Seven unique-ID constraints cover six domain labels and the projection lock record.
One transaction locks the projection, MERGEs nodes/edges, and removes stale projected
records. Concurrent syncs serialize; failed writes roll back. Existing UUIDs and the
two Phase 7 API IDs are used without replacement identifiers.

Read-only POST routes (port 8030, loopback):

* `/api/graph/find_requirement_context`: `{ "requirementId": "UUID" }`
* `/api/graph/find_impacted_tests`: `{ "businessRuleId": "document UUID" }`
* `/api/graph/trace_test_case_origin`: `{ "testCaseId": "UUID" }`
* `/api/graph/analysis-context`: `{ "requirementId": "UUID" }`

The first three are also MCP tools. UUID-only, extra-field-forbidden inputs select
fixed parameterized queries. There is no HTTP/MCP mutation or Cypher endpoint.
Missing entities return 404, graph outages 503, invalid inputs 422, and oversized
path results 413 rather than silently truncating. Paths are bounded and scoped to
the originating Requirement. The projection may be stale until the next sync.

The context route retains the unchanged Hybrid top five. Graph annotations supplied
to analysis must have all supporting chunk IDs in those exact text hits. Neo4j
failure degrades context to text. Optional `/internal/v1/graph-assisted-analysis`
on the AI service uses the existing AnalysisService grounding validator with that
context and returns `persisted: false`. It can invoke the existing local model when
explicitly requested; the Phase 11 validation uses a fake provider and makes zero
real model calls. The default analysis route and stored results are unchanged.

Execution nodes carry the original execution ID and TestCase revision. BASED_ON is
historical evidence provenance; VERIFIED_BY additionally requires agreement with
the current canonical TC endpoint. A copied loan evidence reference on an edited
asset-query TC does not become a loan-rule verification claim.

See `docs/phase11-result.md` for the frozen evaluation protocol, measured limitations,
Chrome screenshots, trace IDs, regression and outage evidence.
