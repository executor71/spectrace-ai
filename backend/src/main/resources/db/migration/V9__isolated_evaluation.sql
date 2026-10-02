-- Evaluation-only storage. Existing app/rag grants are unchanged.
CREATE TABLE evaluation.ground_truth (
 dataset_version text NOT NULL, case_id text NOT NULL, split text NOT NULL CHECK(split IN ('development','validation','final')),
 requirement_hash char(64) NOT NULL, truth_hash char(64) NOT NULL, truth_json jsonb NOT NULL,
 PRIMARY KEY(dataset_version,case_id), CHECK(jsonb_typeof(truth_json)='object')
);
CREATE TABLE evaluation.requirement_binding (
 requirement_id uuid PRIMARY KEY REFERENCES app.requirement(id), dataset_version text NOT NULL, case_id text NOT NULL,
 UNIQUE(dataset_version,case_id), FOREIGN KEY(dataset_version,case_id) REFERENCES evaluation.ground_truth(dataset_version,case_id)
);
CREATE TABLE evaluation.evidence_catalog (chunk_id uuid PRIMARY KEY,entry jsonb NOT NULL);
INSERT INTO evaluation.evidence_catalog SELECT id,jsonb_build_object('documentId',document_id,'chunkId',id,'section',section,'contentSnippet',content,'metadata',metadata) FROM rag.knowledge_chunk;
CREATE TABLE evaluation.evaluation_run (
 id uuid PRIMARY KEY, requirement_id uuid NOT NULL REFERENCES evaluation.requirement_binding(requirement_id), dataset_version text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP, result_json jsonb NOT NULL, snapshot_json jsonb NOT NULL,
 CHECK(jsonb_typeof(result_json)='object' AND jsonb_typeof(snapshot_json)='object'),
 CHECK(result_json->>'status' IN ('COMPLETED','FAILED')), CHECK((result_json->>'id')::uuid=id),
 CHECK((result_json->>'requirementId')::uuid=requirement_id)
);
CREATE INDEX evaluation_run_requirement ON evaluation.evaluation_run(requirement_id,created_at DESC);
CREATE FUNCTION evaluation.immutable_record() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Evaluation data is immutable; add a new version or run'; END;
$$;
CREATE TRIGGER immutable_ground_truth BEFORE UPDATE OR DELETE ON evaluation.ground_truth FOR EACH ROW EXECUTE FUNCTION evaluation.immutable_record();
CREATE TRIGGER immutable_binding BEFORE UPDATE OR DELETE ON evaluation.requirement_binding FOR EACH ROW EXECUTE FUNCTION evaluation.immutable_record();
CREATE TRIGGER immutable_catalog BEFORE UPDATE OR DELETE ON evaluation.evidence_catalog FOR EACH ROW EXECUTE FUNCTION evaluation.immutable_record();
CREATE TRIGGER immutable_run BEFORE UPDATE OR DELETE ON evaluation.evaluation_run FOR EACH ROW EXECUTE FUNCTION evaluation.immutable_record();
-- evaluation_reader remains read-only on tables; only this bounded append function is executable.
CREATE FUNCTION evaluation.record_run(run_id uuid, req_id uuid, version text, result jsonb, snapshot jsonb)
RETURNS void LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog AS $$
 INSERT INTO evaluation.evaluation_run(id,requirement_id,dataset_version,result_json,snapshot_json)
 VALUES(run_id,req_id,version,result,snapshot);
$$;
REVOKE ALL ON FUNCTION evaluation.record_run(uuid,uuid,text,jsonb,jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION evaluation.record_run(uuid,uuid,text,jsonb,jsonb) TO evaluation_reader;
