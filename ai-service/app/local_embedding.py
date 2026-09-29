"""Configurable local dense embedding adapter; no model names or dimensions in code."""
from dataclasses import dataclass
from functools import lru_cache
import json
import logging
import os
from pathlib import Path
from threading import Lock
from typing import Sequence

from app.embedding_contract import EmbeddingIdentity, EmbeddingProvider, validate_vectors

LOG = logging.getLogger(__name__)


class EmbeddingInputTooLongError(ValueError):
    pass


@dataclass(frozen=True)
class EmbeddingSettings:
    provider: str
    model: str
    revision: str
    dimensions: int
    device: str
    batch_size: int
    max_sequence_length: int
    cpu_threads: int
    cache_dir: str

    @classmethod
    def load(cls, path: Path | None = None):
        path = path or Path(os.getenv('EMBEDDING_CONFIG_PATH', str(Path(__file__).parents[1] / 'config/embedding.json')))
        values = json.loads(path.read_text(encoding='utf-8'))
        overrides = {'provider':'EMBEDDING_PROVIDER','model':'EMBEDDING_MODEL','revision':'EMBEDDING_REVISION',
                     'dimensions':'EMBEDDING_DIMENSIONS','device':'EMBEDDING_DEVICE',
                     'batch_size':'EMBEDDING_BATCH_SIZE','max_sequence_length':'EMBEDDING_MAX_SEQUENCE_LENGTH',
                     'cpu_threads':'EMBEDDING_CPU_THREADS','cache_dir':'EMBEDDING_CACHE_DIR'}
        for field, env in overrides.items():
            if os.getenv(env):
                values[field] = os.environ[env]
        for field in ('dimensions','batch_size','max_sequence_length','cpu_threads'):
            values[field] = int(values[field])
            if values[field] < 1:
                raise ValueError(f'{field} must be positive')
        if not values['model'] or not values['revision']:
            raise ValueError('Explicit model and pinned revision are required')
        return cls(**values)


class LocalEmbeddingProvider:
    def __init__(self, settings: EmbeddingSettings):
        self.settings = settings
        self._model = None
        self._lock = Lock()

    @property
    def identity(self) -> EmbeddingIdentity:
        s = self.settings
        return EmbeddingIdentity(s.provider, s.model, s.revision, s.dimensions)

    def _load(self):
        import torch
        from sentence_transformers import SentenceTransformer
        torch.set_num_threads(self.settings.cpu_threads)
        LOG.info('Loading local embedding model %s at %s', self.settings.model, self.settings.revision)
        from huggingface_hub import snapshot_download
        snapshot = snapshot_download(repo_id=self.settings.model, revision=self.settings.revision,
            cache_dir=self.settings.cache_dir,
            allow_patterns=['*.json', '*.safetensors', '*.bin', '*.model', '*.txt'],
            ignore_patterns=['onnx/*', 'openvino/*'], max_workers=4)
        # Load a local snapshot so Transformers never starts a remote weight-conversion thread.
        model = SentenceTransformer(snapshot, device=self.settings.device,
            local_files_only=True, trust_remote_code=False)
        actual = model.get_sentence_embedding_dimension()
        if actual != self.settings.dimensions:
            raise ValueError(f'Configured embedding dimension {self.settings.dimensions} differs from model output {actual}')
        model.max_seq_length = self.settings.max_sequence_length
        self._model = model

    def _encode(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        with self._lock:
            if self._model is None:
                self._load()
            lengths = self._model.tokenizer(list(texts), truncation=False, add_special_tokens=True, return_length=True)['length']
            if any(length > self.settings.max_sequence_length for length in lengths):
                raise EmbeddingInputTooLongError('Input exceeds configured token limit; split the section or shorten the query')
            vectors = self._model.encode(list(texts), batch_size=self.settings.batch_size,
                normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False).tolist()
            validate_vectors(vectors, len(texts), self.settings.dimensions)
            return vectors

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return self._encode(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._encode([text])[0]


@lru_cache(maxsize=1)
def get_embedding_provider() -> EmbeddingProvider:
    settings = EmbeddingSettings.load()
    if settings.provider != 'local_sentence_transformers':
        raise ValueError('Configured embedding provider is not installed')
    return LocalEmbeddingProvider(settings)
