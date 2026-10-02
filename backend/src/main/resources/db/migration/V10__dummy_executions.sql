-- Phase 7 adds only app-owned execution history. No Ground Truth access.
CREATE TABLE app.test_execution (
 execution_id uuid PRIMARY KEY,
 test_case_id uuid NOT NULL,
 requirement_id uuid NOT NULL,
 executed_at timestamptz NOT NULL,
 result_json jsonb NOT NULL,
 CHECK (result_json->>'result' IN ('PASS','FAIL','ERROR')),
 CHECK ((result_json->>'executionId')::uuid=execution_id),
 CHECK ((result_json->>'testCaseId')::uuid=test_case_id),
 CHECK ((result_json->>'requirementId')::uuid=requirement_id)
);
-- No cascading FK: historical snapshots survive regeneration of a TestCase.
CREATE INDEX test_execution_case_time ON app.test_execution(test_case_id,executed_at DESC,execution_id);
REVOKE UPDATE, DELETE ON app.test_execution FROM app_user;
CREATE FUNCTION app.immutable_execution() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Execution history is immutable'; END;
$$;
CREATE TRIGGER immutable_execution BEFORE UPDATE OR DELETE ON app.test_execution
FOR EACH ROW EXECUTE FUNCTION app.immutable_execution();
