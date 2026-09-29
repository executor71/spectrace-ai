-- Preserve Phase 0 tables and ownership; runtime still uses app_user.
ALTER TABLE app.requirement
    ADD CONSTRAINT requirement_title_not_blank CHECK (char_length(btrim(title)) > 0),
    ADD CONSTRAINT requirement_description_length CHECK (
        char_length(btrim(description)) > 0 AND char_length(description) <= 10000
    );
