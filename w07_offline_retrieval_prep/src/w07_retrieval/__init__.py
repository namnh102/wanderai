"""Standalone offline 2x3 retrieval engine for GOMATE W07 (pre-freeze)."""

from __future__ import annotations

from typing import Any

from w07_retrieval.blind_packet import (
    BLIND_PACKET_ALLOWLIST_KEYS,
    build_blind_packet_rows_for_query,
    export_blind_packet_jsonl,
    export_multi_query_blind_packet_jsonl,
)
from w07_retrieval.bm25 import BM25Index, analyze_text
from w07_retrieval.chunker_c0 import C0Chunker, chunk_corpus_c0
from w07_retrieval.chunker_c1 import (
    BOILERPLATE_FOOTER_ALLOWLIST,
    C1Chunker,
    chunk_corpus_c1,
)
from w07_retrieval.fusion import RankedDocument, collapse_chunk_scores, fuse_rrf
from w07_retrieval.sanitizer import (
    KNOWN_FAMILIES,
    R_AUDIT,
    SanitizationResult,
    cp_to_utf8_byte_offsets,
    intervals_contain,
    merge_intervals,
    project_v_span_to_s,
    sanitize_canonical_to_view,
    subtract_intervals,
)
from w07_retrieval.schema import (
    CanonicalDocument,
    ChunkRecord,
    ProvenanceSegment,
    QueryRecord,
    RankingRow,
    load_canonical_document,
    load_corpus_jsonl,
    load_queries_jsonl,
)
from w07_retrieval.visibility import (
    compute_full_s_spans,
    compute_provenance_visible_s_spans,
    get_token_offset_spans,
    load_minilm_tokenizer,
    populate_chunk_provenance,
)

__all__ = [
    "ALL_CELLS",
    "BLIND_PACKET_ALLOWLIST_KEYS",
    "BM25Index",
    "BOILERPLATE_FOOTER_ALLOWLIST",
    "C0Chunker",
    "C1Chunker",
    "CanonicalDocument",
    "ChunkRecord",
    "DenseIndex",
    "ED25519_FORMAL_EXECUTION_DOMAIN_ASCII",
    "ED25519_FORMAL_EXECUTION_DOMAIN_TAG",
    "ExecutionMode",
    "FROZEN_CORPUS_RECEIPT_SCHEMA_V1",
    "KNOWN_FAMILIES",
    "MockEmbedder",
    "OWNER_AUTH_RECEIPT_SCHEMA_V1",
    "OfflineDenseEmbedder",
    "PINNED_LIVE_OWNER_G3_PUBKEY_HEX",
    "ProvenanceSegment",
    "QueryRecord",
    "R_AUDIT",
    "RankedDocument",
    "RankingRow",
    "SanitizationResult",
    "VALID_EXECUTION_MODES",
    "analyze_text",
    "build_blind_packet_rows_for_query",
    "canonical_owner_auth_signing_bytes",
    "chunk_corpus_c0",
    "chunk_corpus_c1",
    "collapse_chunk_scores",
    "compute_full_s_spans",
    "compute_provenance_visible_s_spans",
    "cp_to_utf8_byte_offsets",
    "export_blind_packet_jsonl",
    "export_multi_query_blind_packet_jsonl",
    "fuse_rrf",
    "get_embedder",
    "get_token_offset_spans",
    "intervals_contain",
    "load_canonical_document",
    "load_corpus_jsonl",
    "load_minilm_tokenizer",
    "load_queries_jsonl",
    "merge_intervals",
    "populate_chunk_provenance",
    "project_v_span_to_s",
    "run_benchmark",
    "sanitize_canonical_to_view",
    "subtract_intervals",
    "validate_formal_execution_gate",
    "validate_synthetic_prep_boundaries",
]

_RUNNER_ATTRS = frozenset(
    {
        "ALL_CELLS",
        "ED25519_FORMAL_EXECUTION_DOMAIN_ASCII",
        "ED25519_FORMAL_EXECUTION_DOMAIN_TAG",
        "ExecutionMode",
        "FROZEN_CORPUS_RECEIPT_SCHEMA_V1",
        "OWNER_AUTH_RECEIPT_SCHEMA_V1",
        "PINNED_LIVE_OWNER_G3_PUBKEY_HEX",
        "VALID_EXECUTION_MODES",
        "canonical_owner_auth_signing_bytes",
        "run_benchmark",
        "validate_formal_execution_gate",
        "validate_synthetic_prep_boundaries",
    }
)


def __getattr__(name: str) -> Any:
    if name in ("DenseIndex", "MockEmbedder", "OfflineDenseEmbedder", "get_embedder"):
        from w07_retrieval import dense

        return getattr(dense, name)
    if name in _RUNNER_ATTRS:
        from w07_retrieval import runner

        return getattr(runner, name)
    raise AttributeError(f"module 'w07_retrieval' has no attribute {name!r}")
