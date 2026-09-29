# Workspace Instructions

- Keep Ground Truth in PostgreSQL `evaluation`; never index it into `rag` or expose its credentials to the normal LangGraph workflow.
- Keep Spring-owned business data in `app`. The AI Service may only use the read-only `rag_reader` credential and must not mutate Requirement or TestCase data.
- Spring Boot owns user approval, business state transitions, and authorization for any future Dummy API execution.
- Preserve structured JSON contracts and evidence fields: `documentId`, `chunkId`, `documentType`, `section`, `contentSnippet`, `score`.
- Keep the first implementation scope to service health, DB connectivity, and migrations until Requirement registration is explicitly the next task.
- Do not add GraphRAG, MCP, hybrid search, reranking, or advanced observability in this PoC.
