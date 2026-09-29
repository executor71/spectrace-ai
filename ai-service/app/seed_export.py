"""Build-time exporter: approved embeddings become a reviewable Flyway seed.

No DB credential is accepted here. Flyway applies the generated SQL as migration_owner;
the online AI service continues to receive only rag_reader credentials.
"""
import json
from pathlib import Path

from app.embedding_contract import EmbeddingProvider, validate_vectors
from app.knowledge import load_corpus


def literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def export_seed(root: Path, model: EmbeddingProvider, output: Path) -> dict:
    if output.exists():
        raise ValueError('Refusing to overwrite a versioned Flyway seed')
    documents, chunks = load_corpus(root)
    identity = model.identity
    if not identity.provider or not identity.model or not identity.revision or identity.dimensions < 1:
        raise ValueError('An explicit approved embedding identity is required')
    vectors = model.embed_documents([c.embedding_text for c in chunks])
    validate_vectors(vectors, len(chunks), identity.dimensions)
    dataset_version = json.loads((root/'manifest.json').read_text(encoding='utf-8'))['datasetVersion']
    statements = ['-- Generated from synthetic knowledge only; apply with Flyway, never with the online AI role.',
        'INSERT INTO rag.embedding_profile(id,provider,model,revision,dimensions,dataset_version) VALUES (1,' +
        ','.join([literal(identity.provider),literal(identity.model),literal(identity.revision),
                  str(identity.dimensions),literal(dataset_version)]) + ');']
    for d in documents:
        statements.append('INSERT INTO rag.knowledge_document(id,source_key,title,document_type,domain,version,source_name) VALUES (' +
            ','.join(literal(s) for s in [str(d.id),d.key,d.title,d.document_type,d.domain,d.version,d.source_name]) + ');')
    for chunk, vector in zip(chunks, vectors):
        statements.append('INSERT INTO rag.knowledge_chunk(id,document_id,section,content,metadata,embedding,embedding_profile_id,embedding_dimensions) VALUES (' +
            ','.join([literal(str(chunk.id)),literal(str(chunk.document.id)),literal(chunk.section),literal(chunk.content),
                      literal(json.dumps(chunk.metadata,ensure_ascii=False))+'::jsonb',
                      literal(json.dumps(vector))+'::public.vector','1',str(identity.dimensions)]) + ');')
    output.write_text('\n\n'.join(statements)+'\n',encoding='utf-8')
    return {'documents':len(documents),'chunks':len(chunks),'model':identity.model,'revision':identity.revision,
            'dimensions':identity.dimensions,'datasetVersion':dataset_version}
