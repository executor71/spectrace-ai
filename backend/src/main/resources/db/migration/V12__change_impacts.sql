CREATE TABLE app.change_impact (
 impact_id uuid PRIMARY KEY,
 baseline_requirement_id uuid NOT NULL REFERENCES app.requirement(id),
 baseline_revision text NOT NULL,
 baseline_snapshot jsonb NOT NULL,
 proposal_title text NOT NULL,
 proposal_content text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE app.change_impact_analysis (
 analysis_id uuid PRIMARY KEY,
 impact_id uuid NOT NULL REFERENCES app.change_impact(impact_id),
 result_json jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(analysis_id,impact_id)
);
CREATE TABLE app.change_impact_review (
 review_id uuid PRIMARY KEY,
 impact_id uuid NOT NULL,
 analysis_id uuid NOT NULL,
 review_revision integer NOT NULL CHECK(review_revision>0),
 result_json jsonb NOT NULL,
 reviewed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 FOREIGN KEY(analysis_id,impact_id) REFERENCES app.change_impact_analysis(analysis_id,impact_id),
 UNIQUE(impact_id,review_revision)
);
REVOKE UPDATE,DELETE ON app.change_impact,app.change_impact_analysis,app.change_impact_review FROM app_user;
ALTER TABLE app.analysis_job ADD COLUMN job_type text NOT NULL DEFAULT 'REQUIREMENT_ANALYSIS' CHECK(job_type IN ('REQUIREMENT_ANALYSIS','CHANGE_IMPACT_ANALYSIS'));
ALTER TABLE app.analysis_job ADD COLUMN impact_id uuid REFERENCES app.change_impact(impact_id);
ALTER TABLE app.analysis_job ADD CONSTRAINT impact_job_target CHECK((job_type='CHANGE_IMPACT_ANALYSIS')=(impact_id IS NOT NULL));
DROP INDEX app.analysis_job_one_active;
CREATE UNIQUE INDEX analysis_job_one_active ON app.analysis_job(requirement_id) WHERE status IN ('QUEUED','RUNNING') AND job_type='REQUIREMENT_ANALYSIS';
CREATE UNIQUE INDEX analysis_job_one_active_impact ON app.analysis_job(impact_id) WHERE status IN ('QUEUED','RUNNING') AND job_type='CHANGE_IMPACT_ANALYSIS';
CREATE FUNCTION app.protect_impact_job_target() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.job_type IS DISTINCT FROM OLD.job_type OR NEW.impact_id IS DISTINCT FROM OLD.impact_id THEN RAISE EXCEPTION 'Job target is immutable'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER protect_impact_job_target BEFORE UPDATE ON app.analysis_job FOR EACH ROW EXECUTE FUNCTION app.protect_impact_job_target();
