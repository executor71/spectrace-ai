CREATE TABLE app.analysis_job (
 job_id uuid PRIMARY KEY,
 requirement_id uuid NOT NULL REFERENCES app.requirement(id),
 status text NOT NULL CHECK(status IN ('QUEUED','RUNNING','SUCCEEDED','FAILED','TIMED_OUT','CANCELLED')),
 stage text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 started_at timestamptz, completed_at timestamptz,
 updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 attempt_count integer NOT NULL DEFAULT 0 CHECK(attempt_count>=0),
 error_code text, error_message text, analysis_result_id uuid,
 request_fingerprint text NOT NULL,
 worker_id text, execution_token uuid, lease_expires_at timestamptz,
 trace_parent text, result_fingerprint text,
 CHECK ((status IN ('SUCCEEDED','FAILED','TIMED_OUT','CANCELLED')) = (completed_at IS NOT NULL))
);
CREATE UNIQUE INDEX analysis_job_one_active ON app.analysis_job(requirement_id) WHERE status IN ('QUEUED','RUNNING');
CREATE INDEX analysis_job_queue ON app.analysis_job(status,created_at,job_id);
CREATE FUNCTION app.protect_analysis_job() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF OLD.status IS DISTINCT FROM NEW.status AND NOT (
  (OLD.status='QUEUED' AND NEW.status IN ('RUNNING','CANCELLED')) OR
  (OLD.status='RUNNING' AND NEW.status IN ('SUCCEEDED','FAILED','TIMED_OUT'))
 ) THEN RAISE EXCEPTION 'Invalid analysis job transition'; END IF;
 IF OLD.status IN ('SUCCEEDED','FAILED','TIMED_OUT','CANCELLED') THEN RAISE EXCEPTION 'Terminal job is immutable'; END IF;
 IF NEW.requirement_id IS DISTINCT FROM OLD.requirement_id OR NEW.request_fingerprint IS DISTINCT FROM OLD.request_fingerprint THEN
  RAISE EXCEPTION 'Job input identity is immutable'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER protect_analysis_job BEFORE UPDATE ON app.analysis_job FOR EACH ROW EXECUTE FUNCTION app.protect_analysis_job();
REVOKE DELETE ON app.analysis_job FROM app_user;
-- Existing app default privileges only; no rag/evaluation or administrator grants.
