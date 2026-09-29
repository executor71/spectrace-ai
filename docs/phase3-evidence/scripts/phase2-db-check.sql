\set ON_ERROR_STOP on
SELECT version,description,success FROM app.flyway_schema_history ORDER BY installed_rank;
SELECT count(*) AS documents FROM rag.knowledge_document;
SELECT count(*) AS chunks, count(embedding) AS vectors, min(public.vector_dims(embedding)) AS min_dimensions,
       max(public.vector_dims(embedding)) AS max_dimensions FROM rag.knowledge_chunk;
SELECT provider,model,revision,dimensions,dataset_version FROM rag.embedding_profile;
DO $$ BEGIN
  IF (SELECT count(*) FROM rag.knowledge_document) <> 9
     OR (SELECT count(*) FROM rag.knowledge_chunk) <> 27
     OR EXISTS(SELECT 1 FROM rag.knowledge_chunk c JOIN rag.embedding_profile p ON c.embedding_profile_id=p.id
               WHERE public.vector_dims(c.embedding)<>p.dimensions OR c.embedding_dimensions<>p.dimensions) THEN
    RAISE EXCEPTION 'Knowledge seed or embedding dimensions mismatch';
  END IF;
  IF EXISTS(SELECT 1 FROM rag.knowledge_chunk c JOIN rag.knowledge_document d ON d.id=c.document_id
            WHERE c.metadata->>'documentType'<>d.document_type OR c.metadata->>'domain'<>d.domain
               OR c.metadata->>'version'<>d.version) THEN
    RAISE EXCEPTION 'Chunk metadata mismatch';
  END IF;
  RAISE NOTICE 'PASS: 9 documents, 27 populated vectors, dimensions and metadata agree';
END $$;
BEGIN;
SET LOCAL ROLE migration_owner;
CREATE TABLE evaluation.phase2_ground_truth_probe(id integer, secret_answer text);
INSERT INTO evaluation.phase2_ground_truth_probe VALUES(1,'PHASE2_PRIVATE_GROUND_TRUTH_NOT_FOR_RAG');
SET LOCAL ROLE evaluation_reader;
SELECT count(*) AS evaluation_control_read FROM evaluation.phase2_ground_truth_probe;
SET LOCAL ROLE rag_reader;
DO $$ BEGIN
  BEGIN
    PERFORM secret_answer FROM evaluation.phase2_ground_truth_probe;
    RAISE EXCEPTION 'Ground Truth isolation failed';
  EXCEPTION WHEN insufficient_privilege THEN
    RAISE NOTICE 'PASS: rag_reader cannot read populated evaluation Ground Truth probe';
  END;
  BEGIN
    PERFORM id FROM app.requirement;
    RAISE EXCEPTION 'app isolation failed';
  EXCEPTION WHEN insufficient_privilege THEN
    RAISE NOTICE 'PASS: rag_reader cannot read app';
  END;
  BEGIN
    UPDATE rag.knowledge_chunk SET content='forbidden' WHERE false;
    RAISE EXCEPTION 'RAG readonly isolation failed';
  EXCEPTION WHEN insufficient_privilege THEN
    RAISE NOTICE 'PASS: rag_reader cannot write rag';
  END;
END $$;
ROLLBACK;
SELECT to_regclass('evaluation.phase2_ground_truth_probe') IS NULL AS probe_removed;
