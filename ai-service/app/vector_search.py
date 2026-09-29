"""Read-only exact pgvector search, restricted to the rag schema."""
import json
from typing import Annotated

import psycopg
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.embedding_contract import EmbeddingProvider, validate_vectors


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    query: Annotated[str, Field(min_length=1, max_length=2000)]
    topK: Annotated[int, Field(strict=True, ge=1, le=10)] = 5

    @field_validator('query', mode='before')
    @classmethod
    def trim_query(cls, value):
        return value.strip() if isinstance(value, str) else value


class SearchHit(BaseModel):
    documentId: str
    chunkId: str
    documentType: str
    section: str
    contentSnippet: str
    score: float
    domain: str
    version: str
    relatedApis: list[str]


class CorpusNotReadyError(RuntimeError):
    pass


class VectorSearch:
    def __init__(self, model: EmbeddingProvider, connection_settings: dict):
        self.model = model
        self.connection_settings = connection_settings

    def search(self, request: SearchRequest) -> list[SearchHit]:
        identity = self.model.identity
        with psycopg.connect(**self.connection_settings) as connection:
            with connection.cursor() as cursor:
                cursor.execute('SET TRANSACTION READ ONLY')
                cursor.execute("SET LOCAL statement_timeout = '5s'")
                cursor.execute('SELECT provider, model, revision, dimensions FROM rag.embedding_profile WHERE id = 1')
                profile = cursor.fetchone()
                if profile != (identity.provider, identity.model, identity.revision, identity.dimensions):
                    raise CorpusNotReadyError('Corpus embedding profile does not match the approved query model')
                vector = self.model.embed_query(request.query)
                validate_vectors([vector], 1, identity.dimensions)
                # Explicit operator qualification is required because the connection search_path is rag.
                cursor.execute('''
                    SELECT d.id::text, c.id::text, d.document_type, c.section,
                           left(c.content, 700),
                           1 - (c.embedding OPERATOR(public.<=>) %s::public.vector) AS score,
                           d.domain, d.version, c.metadata->'relatedApis'
                    FROM rag.knowledge_chunk c
                    JOIN rag.knowledge_document d ON d.id = c.document_id
                    WHERE c.embedding_profile_id = 1 AND c.embedding_dimensions = %s
                    ORDER BY c.embedding OPERATOR(public.<=>) %s::public.vector ASC, c.id ASC
                    LIMIT %s
                ''', (json.dumps(vector), identity.dimensions, json.dumps(vector), request.topK))
                return [SearchHit(documentId=row[0], chunkId=row[1], documentType=row[2],
                    section=row[3], contentSnippet=row[4], score=row[5], domain=row[6],
                    version=row[7], relatedApis=row[8]) for row in cursor.fetchall()]
