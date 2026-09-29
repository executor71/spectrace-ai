-- Runtime access is limited to business tables, not migration metadata.
REVOKE ALL PRIVILEGES ON TABLE app.flyway_schema_history FROM app_user;
