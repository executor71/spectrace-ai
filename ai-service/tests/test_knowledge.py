import unittest
from pathlib import Path
from uuid import UUID

from app.knowledge import KnowledgeDocument, load_corpus, section_chunks
from app.embedding_contract import validate_vectors


class KnowledgeTests(unittest.TestCase):
    def test_corpus_is_deterministic_and_complete(self):
        root = Path(__file__).resolve().parents[2] / 'knowledge'
        documents, chunks = load_corpus(root)
        self.assertEqual(9, len(documents))
        self.assertEqual(27, len(chunks))
        self.assertEqual(chunks, load_corpus(root)[1])
        self.assertEqual(27, len({c.id for c in chunks}))
        self.assertEqual({'BUSINESS_RULE','API_SPEC','TEST_GUIDE','POLICY','ERROR_CODE'}, {d.document_type for d in documents})
        for chunk in chunks:
            self.assertEqual({'documentId','chunkId','documentType','domain','version','section','relatedApis'}, set(chunk.metadata))
            self.assertNotIn('expected', chunk.metadata)
            self.assertIn(chunk.section, chunk.embedding_text)

    def test_empty_duplicate_and_oversized_sections_are_rejected(self):
        doc = KnowledgeDocument(UUID(int=1),'test','Title','TEST_GUIDE','IT_ASSET','1','documents/test.md')
        for markdown in ['# Title', '# Title\n## A\n', '# Title\n## A\none\n## A\ntwo', '# Title\n## A\n'+'x'*2001]:
            with self.subTest(markdown=markdown[:40]), self.assertRaises(ValueError):
                section_chunks(doc,markdown,{'A':[]})

    def test_embedding_shape_and_values_are_validated(self):
        validate_vectors([[1.0,0.0]],1,2)
        for vectors in [[], [[1.0]], [[0.0,0.0]], [[float('nan'),1.0]], [[float('inf'),1.0]]]:
            with self.subTest(vectors=vectors), self.assertRaises(ValueError):
                validate_vectors(vectors,1,2)


if __name__ == '__main__':
    unittest.main()
