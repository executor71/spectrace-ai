\set ON_ERROR_STOP on
SELECT version, success FROM app.flyway_schema_history ORDER BY installed_rank;
SELECT current_user, extversion FROM pg_extension WHERE extname='vector';
SELECT count(*) AS documents FROM rag.knowledge_document;
SELECT count(*) AS chunks, count(embedding) AS vectors FROM rag.knowledge_chunk;
SELECT r.rolname, n.nspname, has_schema_privilege(r.rolname,n.oid,'USAGE') AS usage
FROM pg_roles r CROSS JOIN pg_namespace n
WHERE r.rolname IN ('app_user','rag_reader','evaluation_reader') AND n.nspname IN ('app','rag','evaluation') ORDER BY 1,2;
SELECT count(*) AS generations FROM app.test_case_generation;
SELECT result_json->>'type' AS type, result_json->>'executable' AS executable, count(*) FROM app.test_case GROUP BY 1,2 ORDER BY 1;
BEGIN;
CREATE TABLE evaluation.phase4_ground_truth_probe(secret text);
INSERT INTO evaluation.phase4_ground_truth_probe VALUES ('never included in generation');
GRANT SELECT ON evaluation.phase4_ground_truth_probe TO evaluation_reader;
SET LOCAL ROLE evaluation_reader;
SELECT count(*) AS evaluation_control FROM evaluation.phase4_ground_truth_probe;
RESET ROLE;
SET LOCAL ROLE rag_reader;
DO $$ BEGIN
  BEGIN
    PERFORM * FROM evaluation.phase4_ground_truth_probe;
    RAISE EXCEPTION 'Ground Truth unexpectedly accessible';
  EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'PASS Ground Truth denied: SQLSTATE 42501'; END;
  BEGIN
    PERFORM * FROM app.test_case;
    RAISE EXCEPTION 'Test cases unexpectedly accessible';
  EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'PASS app test cases denied: SQLSTATE 42501'; END;
END $$;
RESET ROLE;
ROLLBACK;
