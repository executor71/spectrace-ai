-- Additive Phase 2 model only; ownership and default role grants remain unchanged.
ALTER TABLE rag.knowledge_document DROP CONSTRAINT knowledge_document_type_check;
ALTER TABLE rag.knowledge_document ADD CONSTRAINT knowledge_document_type_check
    CHECK (document_type IN ('BUSINESS_RULE', 'API_SPEC', 'TEST_GUIDE', 'ERROR_CODE', 'POLICY'));
ALTER TABLE rag.knowledge_document
    ADD COLUMN source_key VARCHAR(100) NOT NULL,
    ADD COLUMN domain VARCHAR(100) NOT NULL,
    ADD CONSTRAINT knowledge_document_source_version_unique UNIQUE (source_key, version);

CREATE TABLE rag.embedding_profile (
    id SMALLINT PRIMARY KEY CHECK (id = 1),
    provider VARCHAR(100) NOT NULL,
    model VARCHAR(300) NOT NULL,
    revision VARCHAR(200) NOT NULL,
    dimensions INTEGER NOT NULL CHECK (dimensions > 0),
    dataset_version VARCHAR(100) NOT NULL
);

ALTER TABLE rag.knowledge_chunk
    ALTER COLUMN embedding SET NOT NULL,
    ADD COLUMN embedding_profile_id SMALLINT NOT NULL REFERENCES rag.embedding_profile(id),
    ADD COLUMN embedding_dimensions INTEGER NOT NULL CHECK (embedding_dimensions > 0),
    ADD CONSTRAINT knowledge_chunk_embedding_dimensions_match
        CHECK (public.vector_dims(embedding) = embedding_dimensions),
    ADD CONSTRAINT knowledge_chunk_metadata_complete CHECK (
        metadata ?& ARRAY['documentId','chunkId','documentType','domain','version','section','relatedApis']
        AND metadata->>'documentId' = document_id::text
        AND metadata->>'chunkId' = id::text
        AND metadata->>'section' = section
        AND jsonb_typeof(metadata->'relatedApis') = 'array'
    );

-- Phase 2 uses exact cosine distance over the small synthetic corpus.
-- No Hybrid Search, full-text ranking, ANN index, or reranking is added.
