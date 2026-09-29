CREATE TABLE app.requirement_analysis (
    requirement_id uuid PRIMARY KEY REFERENCES app.requirement(id) ON DELETE CASCADE,
    result_json jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT analysis_is_object CHECK (jsonb_typeof(result_json) = 'object'),
    CONSTRAINT analysis_matches_requirement CHECK (result_json->>'requirementId' = requirement_id::text),
    CONSTRAINT analysis_required_fields CHECK (result_json ?& ARRAY[
        'requirementId','confirmedConditions','ambiguousExpressions','missingConditions',
        'relatedBusinessRules','relatedApis','clarificationQuestions','evidence'])
);
-- Existing app default privileges apply. No rag/evaluation grants or role changes.
