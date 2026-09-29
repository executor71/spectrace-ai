"""Provider boundary shared by initial corpus embedding and query embedding."""
from dataclasses import dataclass
import math
from typing import Protocol, Sequence


@dataclass(frozen=True)
class EmbeddingIdentity:
    provider: str
    model: str
    revision: str
    dimensions: int


class EmbeddingProvider(Protocol):
    @property
    def identity(self) -> EmbeddingIdentity: ...

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


def validate_vectors(vectors: list[list[float]], expected_count: int, dimensions: int) -> None:
    if len(vectors) != expected_count:
        raise ValueError('Embedding result count mismatch')
    for vector in vectors:
        if len(vector) != dimensions or not all(math.isfinite(v) for v in vector):
            raise ValueError('Embedding dimension mismatch or non-finite value')
        if sum(v*v for v in vector) <= 0:
            raise ValueError('Zero vector cannot be used for cosine search')
