CREATE TABLE app.requirement (
    id UUID PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'DRAFT',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT requirement_status_check CHECK (status IN ('DRAFT', 'ANALYZED', 'REVIEWED'))
);

CREATE TABLE rag.knowledge_document (
    id UUID PRIMARY KEY,
    document_type VARCHAR(30) NOT NULL,
    title VARCHAR(300) NOT NULL,
    source_name VARCHAR(300) NOT NULL,
    version VARCHAR(100) NOT NULL,
    CONSTRAINT knowledge_document_type_check CHECK (document_type IN ('BUSINESS_RULE', 'API_SPEC'))
);

CREATE TABLE rag.knowledge_chunk (
    id UUID PRIMARY KEY,
    document_id UUID NOT NULL REFERENCES rag.knowledge_document(id),
    section VARCHAR(300) NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding public.vector
);
