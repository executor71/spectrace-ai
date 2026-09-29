CREATE TABLE app.test_case_generation (
    requirement_id uuid PRIMARY KEY REFERENCES app.requirement(id) ON DELETE CASCADE,
    generation_id uuid NOT NULL UNIQUE,
    source_analysis jsonb NOT NULL CHECK (jsonb_typeof(source_analysis) = 'object'),
    metadata jsonb NOT NULL CHECK (jsonb_typeof(metadata) = 'object'),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (generation_id, requirement_id)
);

CREATE TABLE app.test_case (
    test_case_id uuid PRIMARY KEY,
    requirement_id uuid NOT NULL,
    generation_id uuid NOT NULL,
    ordinal integer NOT NULL CHECK (ordinal >= 0),
    result_json jsonb NOT NULL CHECK (jsonb_typeof(result_json) = 'object'),
    FOREIGN KEY (generation_id, requirement_id) REFERENCES app.test_case_generation(generation_id, requirement_id) ON DELETE CASCADE,
    UNIQUE (generation_id, ordinal),
    CHECK ((result_json->>'testCaseId')::uuid = test_case_id),
    CHECK ((result_json->>'requirementId')::uuid = requirement_id),
    CHECK (result_json->>'type' IN ('NORMAL','EXCEPTION','AUTHORIZATION','BOUNDARY','BUSINESS_RULE')),
    CHECK (jsonb_typeof(result_json->'evidence') = 'array'),
    CHECK (jsonb_typeof(result_json->'executable') = 'boolean')
);
-- Existing app default privileges apply. No RAG/evaluation grants or role changes.
