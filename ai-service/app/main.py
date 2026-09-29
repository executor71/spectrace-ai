import os

import psycopg
from fastapi import FastAPI, HTTPException

app = FastAPI(title="Legacy Change Assistant AI Service", version="0.1.0")


@app.get("/health")
def health() -> dict[str, object]:
    connection_settings = {
        "host": os.getenv("RAG_DB_HOST", "localhost"),
        "dbname": os.getenv("RAG_DB_NAME", "legacy_assistant"),
        "user": os.getenv("RAG_DB_USER", "rag_reader"),
        "password": os.getenv("RAG_DB_PASSWORD", "local_rag_reader_only"),
        "connect_timeout": 3,
        "options": "-c search_path=rag",
    }
    try:
        with psycopg.connect(**connection_settings) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_schema(), extversion FROM pg_extension WHERE extname = 'vector'")
                row = cursor.fetchone()
                if row is None:
                    raise RuntimeError("pgvector extension is unavailable")
                return {
                    "status": "UP",
                    "database": "UP",
                    "schema": row[0],
                    "pgvector": row[1],
                }
    except Exception as error:
        raise HTTPException(status_code=503, detail={"status": "DOWN", "database": str(error)}) from error
