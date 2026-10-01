"""Embedding model abstraction for WanderAI RAG."""

import hashlib
import numpy as np
from abc import ABC, abstractmethod
from typing import List, Union


class BaseEmbedder(ABC):
    """Abstract base class for text embedding models."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the vector dimensionality."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier."""
        pass

    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """Embed a single text string into a float vector."""
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed a batch of text strings into float vectors."""
        pass


class SentenceTransformerEmbedder(BaseEmbedder):
    """Embedder using SentenceTransformers (default: paraphrase-multilingual-MiniLM-L12-v2)."""

    def __init__(self, model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"):
        self._model_name = model_name
        self._model = None
        self._dimension = 384

    def _load_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self._model_name)
        return self._model

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    def embed_text(self, text: str) -> List[float]:
        model = self._load_model()
        vec = model.encode(text, normalize_embeddings=True)
        return vec.tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        model = self._load_model()
        vecs = model.encode(texts, batch_size=32, normalize_embeddings=True)
        return vecs.tolist()


class MockEmbedder(BaseEmbedder):
    """Deterministic hash-based mock embedder for rapid testing without GPU/CPU overhead."""

    def __init__(self, dimension: int = 384, model_name: str = "mock-embedder-384"):
        self._dimension = dimension
        self._model_name = model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    def embed_text(self, text: str) -> List[float]:
        # Generate pseudo-random vector deterministically from text hash
        h = hashlib.sha256(text.encode("utf-8")).digest()
        # Seed numpy generator with first 4 bytes
        seed = int.from_bytes(h[:4], "little")
        rng = np.random.default_rng(seed)
        vec = rng.normal(size=self._dimension)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.embed_text(t) for t in texts]


_GLOBAL_EMBEDDER = None

def get_embedder(prefer_mock: bool = False) -> BaseEmbedder:
    """Singleton getter for embedder."""
    global _GLOBAL_EMBEDDER
    if prefer_mock:
        return MockEmbedder()
    if _GLOBAL_EMBEDDER is None:
        try:
            _GLOBAL_EMBEDDER = SentenceTransformerEmbedder()
        except Exception:
            _GLOBAL_EMBEDDER = MockEmbedder()
    return _GLOBAL_EMBEDDER
