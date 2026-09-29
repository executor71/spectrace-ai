import os


def rag_connection_settings() -> dict:
    return {
        'host': os.getenv('RAG_DB_HOST', 'localhost'),
        'dbname': os.getenv('RAG_DB_NAME', 'legacy_assistant'),
        'user': os.getenv('RAG_DB_USER', 'rag_reader'),
        'password': os.getenv('RAG_DB_PASSWORD', 'local_rag_reader_only'),
        'connect_timeout': 3,
        'options': '-c search_path=rag',
    }
