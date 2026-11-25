"""Synthetic unit tests for FX-11 (rank-invariant blinded annotation packet)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from fixtures.retrieval_fixtures import build_fx11_canonical_pool
from w07_retrieval.blind_packet import (
    BLIND_PACKET_ALLOWLIST_KEYS,
    export_blind_packet_jsonl,
)

EXPECTED_FX11_SHA256 = (
    "bf30686bd9acd0a9e273cc905ff82d7ce78f7b7ea9e959037a36bcfc73ac4ce4"
)
FORBIDDEN_KEYS = frozenset(
    {
        "rank",
        "score",
        "cell_id",
        "cell",
        "pre_rank_answerability",
        "pool_origin",
        "union_count",
        "chunk_boundaries",
        "assembled_text",
        "leg_ranks",
        "leg_rep_chunks",
    }
)


def _walk_keys(obj: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            found.add(str(k))
            found.update(_walk_keys(v))
    elif isinstance(obj, list):
        for item in obj:
            found.update(_walk_keys(item))
    return found


def test_fx11_canonical_rank_invariance_and_exact_sha256() -> None:
    corpus_mock, run_forward, run_reversed = build_fx11_canonical_pool()
    out_fwd = export_blind_packet_jsonl(
        "Q01", "Test?", run_forward, corpus_mock, "SALT_2026"
    )
    out_rev = export_blind_packet_jsonl(
        "Q01", "Test?", run_reversed, corpus_mock, "SALT_2026"
    )
    assert out_fwd == out_rev
    digest = hashlib.sha256(out_fwd.encode("utf-8")).hexdigest()
    assert digest == EXPECTED_FX11_SHA256


def test_fx11_strict_7_keys_zero_forbidden_tokens_and_row_order_uuid_invariance() -> None:
    corpus_mock, run_forward, run_reversed = build_fx11_canonical_pool()
    out_fwd = export_blind_packet_jsonl(
        "Q01", "Test?", run_forward, corpus_mock, "SALT_2026"
    )
    out_rev = export_blind_packet_jsonl(
        "Q01", "Test?", run_reversed, corpus_mock, "SALT_2026"
    )

    rows_fwd = [json.loads(line) for line in out_fwd.splitlines() if line]
    rows_rev = [json.loads(line) for line in out_rev.splitlines() if line]
    assert len(rows_fwd) == 20
    assert len(rows_rev) == 20

    for row in rows_fwd:
        assert set(row.keys()) == BLIND_PACKET_ALLOWLIST_KEYS
        assert _walk_keys(row).isdisjoint(FORBIDDEN_KEYS)
        raw_line = json.dumps(row, ensure_ascii=False, sort_keys=True)
        assert "C1-RRF" not in raw_line
        assert "C0-BM25" not in raw_line
        assert "ANSWERABLE" not in raw_line

    uuids_fwd = {r["document_id"]: r["packet_item_uuid"] for r in rows_fwd}
    uuids_rev = {r["document_id"]: r["packet_item_uuid"] for r in rows_rev}
    assert uuids_fwd == uuids_rev
    assert len(set(uuids_fwd.values())) == 20
