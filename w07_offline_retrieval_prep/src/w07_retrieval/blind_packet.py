"""Rank-invariant 7-key blind annotation packet exporter (D05.3 / FX-11)."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, Mapping, Sequence

import numpy as np

BLIND_PACKET_ALLOWLIST_KEYS: frozenset[str] = frozenset(
    {
        "packet_item_uuid",
        "query_id",
        "query_text",
        "document_id",
        "source_type",
        "language",
        "canonical_text_S",
    }
)


def compute_query_seed(query_id: str, packet_salt: str) -> int:
    """Compute deterministic 64-bit PCG64 seed from query_id and packet_salt."""
    return int.from_bytes(
        hashlib.sha256(f"{query_id}::{packet_salt}".encode("utf-8")).digest()[:8],
        "big",
    )


def compute_packet_item_uuid(query_id: str, document_id: str, packet_salt: str) -> str:
    """Compute rank- and order-independent HMAC-SHA256[:32] item UUID."""
    return hmac.new(
        packet_salt.encode("utf-8"),
        f"{query_id}::{document_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:32]


def _extract_doc_fields(doc: Any) -> tuple[str, str, str]:
    if isinstance(doc, Mapping):
        source_type = str(doc["source_type"])
        language = str(doc["language"])
        if "canonical_text_S" in doc:
            canon_s = str(doc["canonical_text_S"])
        elif "S" in doc:
            canon_s = str(doc["S"])
        else:
            raise KeyError("corpus_lookup entry missing 'canonical_text_S' or 'S'")
        return source_type, language, canon_s
    return (
        str(doc.source_type),
        str(doc.language),
        str(doc.canonical_text_S),
    )


def build_blind_packet_rows_for_query(
    query_id: str,
    query_text: str,
    raw_rankings: Sequence[Mapping[str, Any] | str],
    corpus_lookup: Mapping[str, Any],
    packet_salt: str,
) -> list[dict[str, str]]:
    """Build strictly 7-key, rank-invariant blinded packet rows for a single query."""
    if not isinstance(packet_salt, str) or not packet_salt:
        raise ValueError("packet_salt must be a non-empty string")

    doc_ids = sorted(
        {
            item if isinstance(item, str) else str(item["document_id"])
            for item in raw_rankings
        }
    )
    if not doc_ids:
        return []

    seed_int = compute_query_seed(query_id, packet_salt)
    perm = np.random.Generator(np.random.PCG64(seed_int)).permutation(len(doc_ids))

    rows: list[dict[str, str]] = []
    for idx in perm:
        did = doc_ids[int(idx)]
        source_type, language, canon_s = _extract_doc_fields(corpus_lookup[did])
        row = {
            "packet_item_uuid": compute_packet_item_uuid(query_id, did, packet_salt),
            "query_id": query_id,
            "query_text": query_text,
            "document_id": did,
            "source_type": source_type,
            "language": language,
            "canonical_text_S": canon_s,
        }
        if set(row.keys()) != BLIND_PACKET_ALLOWLIST_KEYS:
            raise AssertionError("Blind packet row keys violated allowlist!")
        rows.append(row)
    return rows


def export_blind_packet_jsonl(
    query_id: str,
    query_text: str,
    raw_rankings: Sequence[Mapping[str, Any] | str],
    corpus_lookup: Mapping[str, Any],
    packet_salt: str,
) -> str:
    """Export single-query blinded packet JSONL (matches verify_v0_2_1_real_corpus_g15_r01.py)."""
    rows = build_blind_packet_rows_for_query(
        query_id=query_id,
        query_text=query_text,
        raw_rankings=raw_rankings,
        corpus_lookup=corpus_lookup,
        packet_salt=packet_salt,
    )
    return "\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in rows)


def export_multi_query_blind_packet_jsonl(
    queries: Mapping[str, str],
    rankings_by_query: Mapping[str, Sequence[Mapping[str, Any] | str]],
    corpus_lookup: Mapping[str, Any],
    packet_salt: str,
) -> str:
    """Export deterministic multi-query blinded packet JSONL sorted by query_id ASC."""
    lines: list[str] = []
    for query_id in sorted(rankings_by_query.keys()):
        rows = build_blind_packet_rows_for_query(
            query_id=query_id,
            query_text=queries[query_id],
            raw_rankings=rankings_by_query[query_id],
            corpus_lookup=corpus_lookup,
            packet_salt=packet_salt,
        )
        for r in rows:
            lines.append(json.dumps(r, ensure_ascii=False, sort_keys=True))
    return "\n".join(lines)
