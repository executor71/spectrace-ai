CREATE EXTENSION IF NOT EXISTS vector;

\getenv migration_password DB_MIGRATION_PASSWORD
\getenv app_password DB_APP_PASSWORD
\getenv rag_password RAG_DB_PASSWORD
\getenv evaluation_password EVALUATION_DB_PASSWORD

SELECT format('CREATE ROLE migration_owner LOGIN PASSWORD %L', :'migration_password') \gexec
SELECT format('CREATE ROLE app_user LOGIN PASSWORD %L', :'app_password') \gexec
SELECT format('CREATE ROLE rag_reader LOGIN PASSWORD %L', :'rag_password') \gexec
SELECT format('CREATE ROLE evaluation_reader LOGIN PASSWORD %L', :'evaluation_password') \gexec

CREATE SCHEMA app AUTHORIZATION migration_owner;
CREATE SCHEMA rag AUTHORIZATION migration_owner;
CREATE SCHEMA evaluation AUTHORIZATION migration_owner;

GRANT USAGE ON SCHEMA app TO app_user;
GRANT USAGE ON SCHEMA rag TO rag_reader;
GRANT USAGE ON SCHEMA evaluation TO evaluation_reader;

ALTER DEFAULT PRIVILEGES FOR ROLE migration_owner IN SCHEMA app
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_user;
ALTER DEFAULT PRIVILEGES FOR ROLE migration_owner IN SCHEMA app
  GRANT USAGE, SELECT ON SEQUENCES TO app_user;
ALTER DEFAULT PRIVILEGES FOR ROLE migration_owner IN SCHEMA rag
  GRANT SELECT ON TABLES TO rag_reader;
ALTER DEFAULT PRIVILEGES FOR ROLE migration_owner IN SCHEMA evaluation
  GRANT SELECT ON TABLES TO evaluation_reader;
