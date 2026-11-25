"""Fail-closed offline MiniLM Dense embedder & unthresholded exact cosine index."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, NoReturn, Sequence

import numpy as np

from w07_retrieval.schema import (
    DEFAULT_SNAPSHOT_DIR,
    PINNED_MODEL_NAME,
    PINNED_SNAPSHOT_ID,
    PINNED_TOKENIZER_SHA256,
    ChunkRecord,
)
from w07_retrieval.visibility import resolve_snapshot_dir, verify_tokenizer_json_sha256

PINNED_TOKENIZER_JSON_SHA256 = PINNED_TOKENIZER_SHA256
EXPECTED_MAX_SEQ_LENGTH = 128
EXPECTED_EMBEDDING_DIM = 384


class MockEmbedder:
    """Hard-blocked stub: MockEmbedder is strictly prohibited in W07 evaluation."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise RuntimeError(
            "MockEmbedder is strictly prohibited in W07 offline evaluation (D04.3 / FX-07)."
        )

    def embed_text(self, text: str) -> list[float]:
        raise RuntimeError("MockEmbedder is strictly prohibited.")

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("MockEmbedder is strictly prohibited.")


def get_embedder(*args: Any, **kwargs: Any) -> NoReturn:
    """Hard-blocked stub: silent MockEmbedder fallback is strictly prohibited."""
    raise RuntimeError(
        "get_embedder() silent MockEmbedder fallback is strictly prohibited in W07 offline evaluation; "
        "use OfflineDenseEmbedder(snapshot_dir=...) directly (D04.3 / FX-07)."
    )


def assert_not_mock_embedder(embedder: Any) -> None:
    """Reject any mock or non-OfflineDenseEmbedder instance/stub."""
    cls_name = type(embedder).__name__.lower()
    model_name = str(getattr(embedder, "model_name", "")).lower()
    if isinstance(embedder, MockEmbedder) or "mock" in cls_name or "mock" in model_name:
        raise RuntimeError(
            f"Refusing mock embedder {type(embedder).__name__!r} (D04.3 / FX-07)."
        )
    if not isinstance(embedder, OfflineDenseEmbedder) or not getattr(
        embedder, "_is_offline_dense_embedder", False
    ):
        raise RuntimeError(
            f"Refusing non-OfflineDenseEmbedder stub {type(embedder).__name__!r} (D04.3 / FX-07)."
        )


class OfflineDenseEmbedder:
    """Fail-closed offline SentenceTransformer loader pinned to local MiniLM snapshot."""

    def __init__(
        self,
        snapshot_dir: str | Path | None = None,
        *,
        verify_tokenizer_sha256: bool = True,
        batch_size: int = 32,
        num_threads: int | None = 4,
    ) -> None:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["HF_DATASETS_OFFLINE"] = "1"
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

        resolved = resolve_snapshot_dir(snapshot_dir)
        if not resolved.is_dir():
            raise FileNotFoundError(
                f"Offline MiniLM snapshot directory not found: {resolved}"
            )
        config_path = resolved / "config.json"
        tok_path = resolved / "tokenizer.json"
        if not config_path.is_file():
            raise FileNotFoundError(f"Missing config.json in snapshot: {config_path}")
        if not tok_path.is_file():
            raise FileNotFoundError(f"Missing tokenizer.json in snapshot: {tok_path}")

        if verify_tokenizer_sha256:
            self.tokenizer_json_sha256 = verify_tokenizer_json_sha256(
                tok_path, PINNED_TOKENIZER_JSON_SHA256
            )
        else:
            import hashlib

            self.tokenizer_json_sha256 = hashlib.sha256(
                tok_path.read_bytes()
            ).hexdigest()

        import torch
        from sentence_transformers import SentenceTransformer

        if num_threads is not None:
            torch.set_num_threads(int(num_threads))

        self._model = SentenceTransformer(
            str(resolved),
            device="cpu",
            local_files_only=True,
        )
        if int(self._model.max_seq_length) != EXPECTED_MAX_SEQ_LENGTH:
            raise RuntimeError(
                f"Expected max_seq_length={EXPECTED_MAX_SEQ_LENGTH}, got {self._model.max_seq_length}"
            )
        dim = self._model.get_embedding_dimension()
        if dim != EXPECTED_EMBEDDING_DIM:
            raise RuntimeError(
                f"Expected embedding dim={EXPECTED_EMBEDDING_DIM}, got {dim}"
            )

        self.snapshot_dir = resolved
        self.snapshot_id = resolved.name
        self.model_name = PINNED_MODEL_NAME
        self.batch_size = int(batch_size)
        self._is_offline_dense_embedder = True

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        """Encode texts to L2-normalized float32 embeddings of shape (N, 384)."""
        if not texts:
            return np.zeros((0, EXPECTED_EMBEDDING_DIM), dtype=np.float32)

        vecs = self._model.encode(
            list(texts),
            batch_size=self.batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        arr = np.asarray(vecs, dtype=np.float32)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        if arr.shape != (len(texts), EXPECTED_EMBEDDING_DIM):
            raise RuntimeError(
                f"Unexpected embedding array shape {arr.shape} for {len(texts)} texts"
            )
        if not np.all(np.isfinite(arr)):
            raise RuntimeError("Non-finite values detected in dense embeddings")
        norms = np.linalg.norm(arr, axis=1)
        if not np.allclose(norms, 1.0, atol=1e-4):
            raise RuntimeError(f"Dense embeddings are not unit-normalized: norms={norms}")
        return arr


class DenseIndex:
    """Exact unthresholded cosine similarity index over all N_C chunks (no min_similarity=0.3)."""

    def __init__(
        self, chunks: Sequence[ChunkRecord], embedder: OfflineDenseEmbedder
    ) -> None:
        assert_not_mock_embedder(embedder)
        self.chunks = list(chunks)
        self.embedder = embedder
        self.chunk_embeddings: np.ndarray = embedder.encode(
            [c.assembled_text for c in self.chunks]
        )

    def score_chunks(self, query_text: str) -> np.ndarray:
        """Return float64 exact cosine similarities across 100% of chunks (no 0.3 cutoff)."""
        assert_not_mock_embedder(self.embedder)
        if not self.chunks:
            return np.zeros(0, dtype=np.float64)
        q_vec = self.embedder.encode([query_text])[0]
        scores = self.chunk_embeddings @ q_vec
        return np.asarray(scores, dtype=np.float64)
