ALTER TABLE app.test_case
    ADD COLUMN reviewed_content jsonb,
    ADD COLUMN approval_status varchar(16) NOT NULL DEFAULT 'DRAFT'
        CHECK (approval_status IN ('DRAFT','APPROVED','REJECTED')),
    ADD COLUMN reviewed_at timestamptz,
    ADD COLUMN reviewer varchar(100),
    ADD COLUMN review_comment varchar(4000),
    ADD COLUMN review_revision bigint NOT NULL DEFAULT 0 CHECK (review_revision >= 0),
    ADD CONSTRAINT review_content_object CHECK (reviewed_content IS NULL OR
        (jsonb_typeof(reviewed_content) = 'object' AND
         reviewed_content - ARRAY['type','scenario','preconditions','input','steps','expectedResult']::text[] = '{}'::jsonb)),
    ADD CONSTRAINT review_decision_metadata CHECK (
        (approval_status = 'DRAFT' AND reviewed_at IS NULL AND reviewer IS NULL AND review_comment IS NULL) OR
        (approval_status IN ('APPROVED','REJECTED') AND reviewed_at IS NOT NULL AND reviewer IS NOT NULL));

-- AI output and its evidence remain immutable. Regeneration retains Phase 4 delete/insert semantics.
CREATE FUNCTION app.protect_generated_test_case() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.result_json IS DISTINCT FROM OLD.result_json OR
       NEW.requirement_id IS DISTINCT FROM OLD.requirement_id OR
       NEW.test_case_id IS DISTINCT FROM OLD.test_case_id OR
       NEW.generation_id IS DISTINCT FROM OLD.generation_id THEN
        RAISE EXCEPTION 'Generated test case and evidence are immutable';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER protect_generated_test_case BEFORE UPDATE ON app.test_case
FOR EACH ROW EXECUTE FUNCTION app.protect_generated_test_case();
-- No role grants, RAG access or evaluation access added.
