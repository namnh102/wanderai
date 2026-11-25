"""Pure-Python/NumPy Okapi BM25 retriever with fail-closed underthesea analyzer."""

from __future__ import annotations

import math
import unicodedata
from collections import Counter
from typing import Callable, Dict, Literal, Sequence, Tuple

import numpy as np
import regex

from w07_retrieval.schema import ChunkRecord

BM25_K1: float = 1.5
BM25_B: float = 0.75
BM25_TOKEN_PATTERN = regex.compile(
    r"\p{L}[\p{L}\p{M}\p{N}_]*|\p{N}+(?:[.,]\p{N}+)*"
)


def analyze_text(text: str) -> list[str]:
    """Fail-closed vi/en analyzer: NFC -> lower -> underthesea -> regex -> stopwords=NONE."""
    if not isinstance(text, str):
        raise TypeError(f"Expected str for analyze_text, got {type(text).__name__}")

    from underthesea import word_tokenize

    normalized = unicodedata.normalize("NFC", text).lower()
    tokenized_text = word_tokenize(normalized, format="text")
    if not isinstance(tokenized_text, str):
        raise RuntimeError(
            f"underthesea.word_tokenize returned non-str: {type(tokenized_text).__name__}"
        )
    return BM25_TOKEN_PATTERN.findall(tokenized_text)


class BM25Index:
    """Deterministic Okapi BM25 over all N_C assembled chunk strings A(c)."""

    def __init__(
        self,
        chunks: Sequence[ChunkRecord],
        *,
        k1: float = BM25_K1,
        b: float = BM25_B,
        analyzer: Callable[[str], list[str]] = analyze_text,
        query_term_aggregation: Literal["multiset", "unique"] = "multiset",
    ) -> None:
        self.chunks = list(chunks)
        self.num_chunks = len(self.chunks)
        self.k1 = float(k1)
        self.b = float(b)
        self._analyzer = analyzer
        self.query_term_aggregation = query_term_aggregation

        self._doc_lens = np.zeros(self.num_chunks, dtype=np.int64)
        df: Counter[str] = Counter()
        raw_postings: Dict[str, list[Tuple[int, int]]] = {}

        for idx, chunk in enumerate(self.chunks):
            tokens = self._analyzer(chunk.assembled_text)
            self._doc_lens[idx] = len(tokens)
            tf_map = Counter(tokens)
            for term, tf in tf_map.items():
                raw_postings.setdefault(term, []).append((idx, tf))
                df[term] += 1

        self.avgdl: float = (
            float(self._doc_lens.sum()) / self.num_chunks if self.num_chunks > 0 else 0.0
        )
        self._idf: Dict[str, float] = {
            term: math.log(1.0 + (self.num_chunks - doc_freq + 0.5) / (doc_freq + 0.5))
            for term, doc_freq in df.items()
        }
        self._postings: Dict[str, Tuple[np.ndarray, np.ndarray]] = {
            term: (
                np.asarray([p[0] for p in pairs], dtype=np.int64),
                np.asarray([p[1] for p in pairs], dtype=np.float64),
            )
            for term, pairs in raw_postings.items()
        }

    def idf(self, term: str) -> float:
        """Return IDF(term) for inspection/testing."""
        return self._idf.get(term, 0.0)

    def score_chunks(self, query_text: str) -> np.ndarray:
        """Return float64 Okapi BM25 scores over all N_C chunks (unthresholded)."""
        q_tokens = self._analyzer(query_text)
        scores = np.zeros(self.num_chunks, dtype=np.float64)
        if self.num_chunks == 0 or self.avgdl == 0.0 or not q_tokens:
            return scores

        if self.query_term_aggregation == "multiset":
            q_items = list(Counter(q_tokens).items())
        elif self.query_term_aggregation == "unique":
            q_items = [(t, 1) for t in dict.fromkeys(q_tokens)]
        else:
            raise ValueError(
                f"Unknown query_term_aggregation: {self.query_term_aggregation!r}"
            )

        for term, qtf in q_items:
            posting = self._postings.get(term)
            if posting is None:
                continue
            c_idxs, tf_arr = posting
            dl_arr = self._doc_lens[c_idxs]
            denom = tf_arr + self.k1 * (1.0 - self.b + self.b * (dl_arr / self.avgdl))
            term_scores = self._idf[term] * (tf_arr * (self.k1 + 1.0)) / denom
            scores[c_idxs] += float(qtf) * term_scores

        return scores
