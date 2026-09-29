\set ON_ERROR_STOP on
SELECT version,description,success FROM app.flyway_schema_history ORDER BY installed_rank;
SELECT r.rolname, n.nspname, has_schema_privilege(r.rolname,n.oid,'USAGE') AS usage
FROM pg_roles r CROSS JOIN pg_namespace n
WHERE r.rolname IN ('app_user','rag_reader','evaluation_reader') AND n.nspname IN ('app','rag','evaluation')
ORDER BY r.rolname,n.nspname;
SELECT rolname, has_table_privilege(rolname,'app.requirement_analysis','SELECT') AS read_analysis,
  has_table_privilege(rolname,'app.requirement_analysis','INSERT') AS write_analysis
FROM pg_roles WHERE rolname IN ('app_user','rag_reader','evaluation_reader');
DO $$ BEGIN
  IF NOT has_table_privilege('app_user','app.requirement_analysis','INSERT')
     OR has_table_privilege('rag_reader','app.requirement_analysis','SELECT')
     OR has_table_privilege('evaluation_reader','app.requirement_analysis','SELECT') THEN
    RAISE EXCEPTION 'Analysis table boundary failed';
  END IF;
  IF (SELECT count(*) FROM app.flyway_schema_history WHERE success) <> 6 THEN RAISE EXCEPTION 'Migration count mismatch'; END IF;
  RAISE NOTICE 'PASS: V1-V6 migrations and new analysis table privileges';
END $$;
