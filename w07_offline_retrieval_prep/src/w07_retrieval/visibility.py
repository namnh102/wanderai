"""Provenance-aware A(c) -> V -> S visibility mapping and offline MiniLM tokenizer loader."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from tokenizers import Tokenizer

from w07_retrieval.sanitizer import merge_intervals, project_v_span_to_s
from w07_retrieval.schema import (
    DEFAULT_SNAPSHOT_DIR,
    PINNED_TOKENIZER_SHA256,
    ChunkRecord,
)


def resolve_snapshot_dir(snapshot_dir: str | Path | None = None) -> Path:
    """Resolve local HuggingFace snapshot directory without network access."""
    if snapshot_dir is not None:
        return Path(snapshot_dir)
    env_dir = os.environ.get("W07_HF_SNAPSHOT_DIR")
    if env_dir:
        return Path(env_dir)
    return DEFAULT_SNAPSHOT_DIR


def verify_tokenizer_json_sha256(
    tokenizer_json_path: Path,
    expected_sha256: str = PINNED_TOKENIZER_SHA256,
) -> str:
    """Verify tokenizer.json SHA-256 on disk against pinned digest."""
    if not tokenizer_json_path.is_file():
        raise FileNotFoundError(f"Missing tokenizer.json at {tokenizer_json_path}")
    actual = hashlib.sha256(tokenizer_json_path.read_bytes()).hexdigest()
    if actual != expected_sha256:
        raise RuntimeError(
            f"tokenizer.json SHA-256 mismatch at {tokenizer_json_path}: "
            f"expected {expected_sha256}, got {actual}"
        )
    return actual


def load_minilm_tokenizer(
    snapshot_dir: str | Path | None = None,
    *,
    verify_sha256: bool = True,
) -> Tokenizer:
    """Load cached MiniLM tokenizers.Tokenizer offline with no_truncation()."""
    resolved = resolve_snapshot_dir(snapshot_dir)
    if not resolved.is_dir():
        raise FileNotFoundError(f"Offline MiniLM snapshot directory not found: {resolved}")
    tok_json = resolved / "tokenizer.json"
    if verify_sha256:
        verify_tokenizer_json_sha256(tok_json, PINNED_TOKENIZER_SHA256)
    elif not tok_json.is_file():
        raise FileNotFoundError(f"Missing tokenizer.json at {tok_json}")
    tok = Tokenizer.from_file(str(tok_json))
    # tokenizer.json in the cached snapshot carries a default max_length=128 truncation rule;
    # disable truncation on the base tokenizer so untruncated counts and offsets are exact.
    tok.no_truncation()
    return tok


def _clone_tokenizer(tokenizer: Any, max_tokens: Optional[int]) -> Tokenizer:
    """Return a configured tokenizers.Tokenizer without mutating caller's tokenizer."""
    backend = getattr(tokenizer, "backend_tokenizer", tokenizer)
    if not isinstance(backend, Tokenizer):
        raise TypeError(
            f"Expected tokenizers.Tokenizer or PreTrainedTokenizerFast, got {type(tokenizer).__name__}"
        )
    cloned = Tokenizer.from_str(backend.to_str())
    if max_tokens is None:
        cloned.no_truncation()
    else:
        cloned.enable_truncation(max_length=int(max_tokens))
    return cloned


def count_tokens_with_special(text: str, tokenizer: Any) -> int:
    """Return exact untruncated MiniLM token count including <s> and </s>."""
    tok = _clone_tokenizer(tokenizer, max_tokens=None)
    return len(tok.encode(text, add_special_tokens=True).ids)


def get_token_offset_spans(
    assembled_text: str,
    tokenizer: Any,
    max_tokens: Optional[int] = 128,
) -> List[Tuple[int, int]]:
    """Return tokenizer offset spans [(a_start, a_end), ...] including (0, 0) specials.

    When max_tokens is set (e.g. 128 for Dense), configures truncation(max_length=max_tokens)
    so token 0 is <s> (0, 0), tokens 1..126 are the 126 visible content subwords, and token 127
    is </s> (0, 0), matching SentenceTransformer / AutoTokenizer identically.
    When max_tokens is None, uses no_truncation() for untruncated BM25/C_full coverage.
    """
    tok = _clone_tokenizer(tokenizer, max_tokens=max_tokens)
    enc = tok.encode(assembled_text, add_special_tokens=True)
    return [(int(a), int(b)) for a, b in enc.offsets]


def compute_full_s_spans(
    assembled_segments: Sequence[Mapping[str, Any]],
    v_to_s_segments: Sequence[Tuple[int, int, int, int]],
) -> List[Tuple[int, int]]:
    """Compute C_full(c) subset of S from all canonical provenance segments in A(c)."""
    s_intervals: List[Tuple[int, int]] = []
    for seg in assembled_segments:
        kind = seg["kind"]
        if kind == "SYNTHETIC_HEADER":
            continue
        elif kind == "CANONICAL_HEADING_S":
            s_intervals.append((int(seg["s_start"]), int(seg["s_end"])))
        elif kind == "CANONICAL_BODY_V":
            s_intervals.extend(
                project_v_span_to_s(
                    int(seg["v_start"]), int(seg["v_end"]), v_to_s_segments
                )
            )
        else:
            raise ValueError(f"Unexpected segment kind: {kind!r}")
    return merge_intervals(s_intervals)


def compute_provenance_visible_s_spans(
    assembled_text: str,
    assembled_segments: Sequence[Mapping[str, Any]],
    token_offset_spans: Sequence[Tuple[int, int]],
    max_tokens: Optional[int],
    v_to_s_segments: Sequence[Tuple[int, int, int, int]],
) -> List[Tuple[int, int]]:
    """Map individual encoder-visible token offset spans in A(c) onto canonical S intervals.

    SYNTHETIC_HEADER slices map to the empty set in S.
    Purely-whitespace gaps are bridged ONLY between consecutive visible tokens inside the SAME
    canonical segment.
    """
    if max_tokens is None:
        sliced = token_offset_spans
    elif max_tokens <= 0:
        sliced = ()
    elif (
        len(token_offset_spans) > max_tokens
        and tuple(token_offset_spans[max_tokens - 1]) != (0, 0)
    ):
        # Untruncated offsets lack the synthetic </s> (0, 0) at slot max_tokens - 1;
        # reserve that slot so at most max_tokens - 2 content tokens are visible.
        sliced = token_offset_spans[: max_tokens - 1]
    else:
        sliced = token_offset_spans[:max_tokens]
    visible_tokens = [(int(a), int(b)) for a, b in sliced if a < b]
    if not visible_tokens:
        return []

    seg_hits: List[Tuple[int, int, int]] = []
    for tok_a, tok_b in visible_tokens:
        for seg_idx, seg in enumerate(assembled_segments):
            if seg["kind"] == "SYNTHETIC_HEADER":
                continue
            ov_a = max(tok_a, int(seg["a_start"]))
            ov_b = min(tok_b, int(seg["a_end"]))
            if ov_a >= ov_b:
                continue
            seg_hits.append((seg_idx, ov_a, ov_b))

    if not seg_hits:
        return []

    bridged: List[Tuple[int, int, int]] = []
    for seg_idx, a, b in sorted(seg_hits):
        if bridged and bridged[-1][0] == seg_idx:
            prev_b = bridged[-1][2]
            if a <= prev_b or assembled_text[prev_b:a].isspace():
                bridged[-1] = (seg_idx, bridged[-1][1], max(prev_b, b))
                continue
        bridged.append((seg_idx, a, b))

    s_intervals: List[Tuple[int, int]] = []
    for seg_idx, ov_a, ov_b in bridged:
        seg = assembled_segments[seg_idx]
        kind = seg["kind"]
        if kind == "CANONICAL_HEADING_S":
            s_a = int(seg["s_start"]) + (ov_a - int(seg["a_start"]))
            s_b = int(seg["s_start"]) + (ov_b - int(seg["a_start"]))
            s_intervals.append((s_a, s_b))
        elif kind == "CANONICAL_BODY_V":
            v_a = int(seg["v_start"]) + (ov_a - int(seg["a_start"]))
            v_b = int(seg["v_start"]) + (ov_b - int(seg["a_start"]))
            s_intervals.extend(project_v_span_to_s(v_a, v_b, v_to_s_segments))
        else:
            raise ValueError(f"Unexpected segment kind: {kind!r}")
    return merge_intervals(s_intervals)


def populate_chunk_provenance(
    chunk: ChunkRecord,
    tokenizer: Any,
    v_to_s_segments: Sequence[Tuple[int, int, int, int]],
    *,
    max_dense_tokens: int = 128,
) -> ChunkRecord:
    """Compute and attach c_full_s_spans, c_vis_s_spans_dense, c_vis_s_spans_bm25, and token count."""
    tok_untrunc = _clone_tokenizer(tokenizer, max_tokens=None)
    tok_trunc = _clone_tokenizer(tokenizer, max_tokens=max_dense_tokens)

    untrunc_offsets = [(int(a), int(b)) for a, b in tok_untrunc.encode(chunk.assembled_text, add_special_tokens=True).offsets]
    trunc_offsets = [(int(a), int(b)) for a, b in tok_trunc.encode(chunk.assembled_text, add_special_tokens=True).offsets]

    full_s = compute_full_s_spans(chunk.assembled_segments, v_to_s_segments)
    vis_dense = compute_provenance_visible_s_spans(
        chunk.assembled_text,
        chunk.assembled_segments,
        trunc_offsets,
        max_dense_tokens,
        v_to_s_segments,
    )
    vis_bm25 = compute_provenance_visible_s_spans(
        chunk.assembled_text,
        chunk.assembled_segments,
        untrunc_offsets,
        None,
        v_to_s_segments,
    )

    chunk.c_full_s_spans = [[a, b] for a, b in full_s]
    chunk.c_vis_s_spans_dense = [[a, b] for a, b in vis_dense]
    chunk.c_vis_s_spans_bm25 = [[a, b] for a, b in vis_bm25]
    chunk.token_count_with_special = len(untrunc_offsets)
    return chunk
