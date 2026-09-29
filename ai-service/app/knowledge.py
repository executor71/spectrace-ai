"""Section-based synthetic corpus loading; never scans arbitrary files or schemas."""
from dataclasses import dataclass
import json
from pathlib import Path
import re
from uuid import UUID, uuid5

NAMESPACE = UUID('55a34fc8-9a8e-4a01-8f23-c82a21d00002')
DOCUMENT_TYPES = {'BUSINESS_RULE', 'API_SPEC', 'TEST_GUIDE', 'ERROR_CODE', 'POLICY'}


@dataclass(frozen=True)
class KnowledgeDocument:
    id: UUID
    key: str
    title: str
    document_type: str
    domain: str
    version: str
    source_name: str


@dataclass(frozen=True)
class KnowledgeChunk:
    id: UUID
    document: KnowledgeDocument
    section: str
    content: str
    related_apis: tuple[str, ...]

    @property
    def metadata(self) -> dict:
        return {
            'documentId': str(self.document.id), 'chunkId': str(self.id),
            'documentType': self.document.document_type, 'domain': self.document.domain,
            'version': self.document.version, 'section': self.section,
            'relatedApis': list(self.related_apis),
        }

    @property
    def embedding_text(self) -> str:
        return f'{self.document.title}\n{self.section}\n{self.content}'


def section_chunks(document: KnowledgeDocument, markdown: str, related_apis: dict) -> list[KnowledgeChunk]:
    parts = re.split(r'^## (.+)\s*$', markdown.replace('\r\n', '\n'), flags=re.MULTILINE)
    if len(parts) < 3:
        raise ValueError('Document must have semantic ## sections')
    if parts[0].strip() != f'# {document.title}':
        raise ValueError('Manifest title must match the document heading; no unchunked preface')
    chunks = []
    sections = set()
    for heading, content in zip(parts[1::2], parts[2::2]):
        heading, content = heading.strip(), content.strip()
        if not heading or heading in sections or not content:
            raise ValueError('Empty or duplicate semantic section')
        if len(content) > 2000:
            raise ValueError('Split this section into smaller semantic sections before ingestion')
        if heading not in related_apis:
            raise ValueError('Each section must explicitly declare relatedApis')
        apis = related_apis[heading]
        if not isinstance(apis, list) or any(not isinstance(a, str) for a in apis):
            raise ValueError('relatedApis must be a list of strings')
        sections.add(heading)
        chunks.append(KnowledgeChunk(uuid5(document.id, heading), document, heading, content, tuple(apis)))
    if set(related_apis) != sections:
        raise ValueError('Manifest sections and Markdown headings differ')
    return chunks


def load_corpus(root: Path) -> tuple[list[KnowledgeDocument], list[KnowledgeChunk]]:
    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('synthetic') is not True:
        raise ValueError('Only explicitly synthetic initial data is accepted')
    documents, chunks, keys = [], [], set()
    for entry in manifest['documents']:
        key = entry['key']
        if key in keys or entry['documentType'] not in DOCUMENT_TYPES:
            raise ValueError('Duplicate key or unsupported document type')
        source = (root / entry['sourceName']).resolve()
        if not source.is_relative_to((root / 'documents').resolve()) or source.suffix != '.md':
            raise ValueError('Source must be a Markdown file within knowledge/documents')
        keys.add(key)
        document = KnowledgeDocument(uuid5(NAMESPACE, f"{key}:{entry['version']}"), key,
            entry['title'], entry['documentType'], entry['domain'], entry['version'], entry['sourceName'])
        documents.append(document)
        chunks.extend(section_chunks(document, source.read_text(encoding='utf-8'), entry['sections']))
    if not documents or not chunks:
        raise ValueError('Corpus is empty')
    return documents, chunks
