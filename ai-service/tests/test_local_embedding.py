import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from app.local_embedding import EmbeddingSettings, LocalEmbeddingProvider, EmbeddingInputTooLongError


class LocalEmbeddingTests(unittest.TestCase):
    def settings(self):
        return EmbeddingSettings('local_sentence_transformers','unit-test-model','revision',3,'cpu',2,20,1,'/tmp/test-cache')

    def test_settings_are_external_and_overridable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'config.json'
            path.write_text(json.dumps(self.settings().__dict__))
            with patch.dict('os.environ',{'EMBEDDING_MODEL':'different-model','EMBEDDING_DIMENSIONS':'7'}):
                settings=EmbeddingSettings.load(path)
            self.assertEqual('different-model',settings.model)
            self.assertEqual(7,settings.dimensions)

    def test_query_and_documents_share_dense_embedding_path(self):
        provider=LocalEmbeddingProvider(self.settings())
        provider._model=MagicMock()
        provider._model.tokenizer.return_value={'length':[3]}
        provider._model.encode.return_value.tolist.return_value=[[1.0,0.0,0.0]]
        self.assertEqual(provider.embed_documents(['sample'])[0],provider.embed_query('sample'))
        self.assertTrue(provider._model.encode.call_args.kwargs['normalize_embeddings'])

    def test_input_is_not_silently_truncated(self):
        provider=LocalEmbeddingProvider(self.settings())
        provider._model=MagicMock()
        provider._model.tokenizer.return_value={'length':[21]}
        with self.assertRaises(EmbeddingInputTooLongError):
            provider.embed_query('long input')
        provider._model.encode.assert_not_called()

    def test_wrong_dimension_is_rejected(self):
        provider=LocalEmbeddingProvider(self.settings())
        with patch('huggingface_hub.snapshot_download', return_value='/tmp/mock-model'), patch('sentence_transformers.SentenceTransformer') as model:
            model.return_value.get_sentence_embedding_dimension.return_value=9
            with self.assertRaises(ValueError):
                provider.embed_query('sample')
