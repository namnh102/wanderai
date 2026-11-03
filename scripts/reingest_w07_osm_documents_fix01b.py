"""W07-B1-FIX-01B — Controlled OSM Re-ingestion Executor & Receipt Verifier (v1).

Safely re-generates the 759 stored OSM RAG documents in the local PostgreSQL
`documents` table using the repaired nested-tag renderer (`FIX-01A` / `PDG-001`),
archives superseded pre-fix OSM rows into `document_quarantine`, and proves
RUN-1 expected-state equality plus RUN-2 semantic idempotency and Wikivoyage
invariance.

Modes:
- `--preflight`: Read-only preflight check of DB counts, quarantine table,
  offline embedding model cache, expected 759 chunks, delta, and collision guard.
- `--execute`: Controlled RUN 1 + RUN 2 execution, verification of all safety
  invariants, and deterministic generation of receipt JSON and Markdown report.
- `--verify-receipt` (or `--verify-only`): Offline verification of committed
  receipt JSON, Markdown report, B1A historical immutability, and upstream
  W06..W07-B0 hashes.

Execution never occurs implicitly on import or test collection.
Zero web downloads, zero social collection, zero Google Maps collection,
zero LLM provider calls, zero model downloads (`HF_HUB_OFFLINE=1`).
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "apps" / "ai-service") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "apps" / "ai-service"))

from app.rag.chunker import RAGChunk  # noqa: E402
from app.rag.evaluate import GROUNDING_CULTURE_HANOI, opening_hours_query  # noqa: E402
from app.rag.osm_documents import OSM_ATTRIBUTION, OSM_LICENSE, build_osm_place_chunk  # noqa: E402
from scripts import (  # noqa: E402
    audit_w07_b1a_existing_poi_knowledge as w07_b1a,
    validate_w07_review_corpus_v1 as w07_a2,
)

RECEIPT_JSON_RELPATH = "data/evaluation/w07/w07_b1_fix_01b_reingestion_v1.json"
REPORT_MD_RELPATH = "docs/research/w07_b1_fix_01b_reingestion.md"
TARGET_60_MANIFEST_RELPATH = "data/evaluation/w07/w07_review_target_60_pois_v1.json"

TASK_ID = "W07-B1-FIX-01B-CONTROLLED-OSM-REINGESTION"
RECEIPT_VERSION = "1.0.0"
AUTHORITATIVE_BASE_DEVELOP_SHA = "b4db0655070cd0b404891964d57241032e08ed84"
PREVIOUS_ACCEPTED_GATE = "W07-B1-FIX-01A-POSTMERGE-CHATGPT-AUDIT = PASS"
W07_B1_FIX_01A_STATUS = "CLOSED"
NEXT_GATE = "W07-B1-FIX-01B-CONTROLLED-REINGESTION-CHATGPT-AUDIT"

EXPECTED_TOTAL_DOCUMENTS = 1223
EXPECTED_OSM_DOCUMENTS = 759
EXPECTED_WIKIVOYAGE_DOCUMENTS = 464
EXPECTED_TARGET_POIS = 60
EXPECTED_TARGET_USEFUL_STRUCTURED = 40
EXPECTED_TARGET_LOW_INFORMATION = 20
EXPECTED_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EXPECTED_EMBEDDING_DIM = 384
QUARANTINE_SUPERSEDED_REASON = "osm_document_superseded_by_task_07_5_regeneration"

EXPECTED_B1A_JSON_INTERNAL_SHA256 = (
    "27d6dae8fd3ec284ea92806080a044b6745fb30abdddc265297e0f9da1d1c5b2"
)
EXPECTED_B1A_JSON_LF_SHA256 = (
    "433c722dd2f03946ab0a15830b53ef628d76937fa2e8e63a9939e73bb469e563"
)
EXPECTED_B1A_MD_LF_SHA256 = (
    "130aca652c9b808a8b7e5fac50d070dd0c3f36a8e94f7693cfac8793643d0ac5"
)

# Deterministic 5-POI sample from the frozen 60 target manifest covering all 3 cities
# and diverse newly surfaced factual fields (addr:*, opening_hours, website, phone,
# email, cuisine, wheelchair, operator, wikidata, wikipedia, description)
SAMPLE_TARGET_POI_IDS: tuple[str, ...] = (
    "698ee756-6062-5f47-955b-bdf458682e57",  # Lăng Chủ tịch Hồ Chí Minh (Hà Nội)
    "f0d424bd-f722-540f-8964-5e6fd8875b56",  # Bảo tàng Dân tộc học Việt Nam (Hà Nội)
    "acb22336-1124-49d5-a279-6357c2b2b445",  # Quán Ăn Ngon - Phan Bội Châu (Hà Nội)
    "9974ff88-5418-5867-ae49-1b72e0f0861f",  # Cầu Rồng (Đà Nẵng)
    "b37d68ee-0cb3-49f0-a399-cac4c8e2732c",  # Nhà hàng Hồng Hạnh 3 (Hạ Long)
)


def _canonical_sha256(obj: Any) -> str:
    payload = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _normalize_timestamp(val: Any) -> str | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        dt = val if val.tzinfo is not None else val.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    s = str(val).strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
        dt = dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except ValueError:
        return s


def _normalize_metadata(meta: Any) -> dict[str, Any]:
    if meta is None:
        return {}
    if isinstance(meta, str):
        parsed = json.loads(meta)
        return parsed if isinstance(parsed, dict) else {}
    if isinstance(meta, dict):
        return dict(meta)
    return {}


def validate_preflight_state(counts: dict[str, Any]) -> None:
    """Section 3 & 4: Fail-closed validation of pre-reingestion DB state and quarantine table."""
    if not counts.get("quarantine_table_exists", False):
        raise ValueError(
            "QUARANTINE_TABLE_REQUIRED: document_quarantine table does not exist"
        )

    total = counts.get("total_documents")
    osm = counts.get("osm_documents")
    wv = counts.get("wikivoyage_documents")
    if (
        total != EXPECTED_TOTAL_DOCUMENTS
        or osm != EXPECTED_OSM_DOCUMENTS
        or wv != EXPECTED_WIKIVOYAGE_DOCUMENTS
        or total != (osm + wv)
    ):
        raise ValueError(
            "PRE_REINGESTION_STATE_MISMATCH: expected total=1223, osm=759, wikivoyage=464, "
            f"got total={total}, osm={osm}, wikivoyage={wv}"
        )

    if counts.get("unique_osm_document_ids") != EXPECTED_OSM_DOCUMENTS:
        raise ValueError(
            "PRE_REINGESTION_STATE_MISMATCH: unique_osm_document_ids="
            f"{counts.get('unique_osm_document_ids')} != {EXPECTED_OSM_DOCUMENTS}"
        )
    if counts.get("duplicate_osm_document_ids", -1) != 0:
        raise ValueError(
            "PRE_REINGESTION_STATE_MISMATCH: duplicate_osm_document_ids="
            f"{counts.get('duplicate_osm_document_ids')} != 0"
        )
    if counts.get("unique_osm_place_ids") != EXPECTED_OSM_DOCUMENTS:
        raise ValueError(
            "PRE_REINGESTION_STATE_MISMATCH: unique_osm_place_ids="
            f"{counts.get('unique_osm_place_ids')} != {EXPECTED_OSM_DOCUMENTS}"
        )
    if counts.get("null_place_id_osm_documents", -1) != 0:
        raise ValueError(
            "PRE_REINGESTION_STATE_MISMATCH: null_place_id_osm_documents="
            f"{counts.get('null_place_id_osm_documents')} != 0"
        )
    if counts.get("unverified_osm_documents", -1) != 0:
        raise ValueError(
            "PRE_REINGESTION_STATE_MISMATCH: unverified_osm_documents="
            f"{counts.get('unverified_osm_documents')} != 0"
        )


def generate_expected_osm_chunks(places: list[dict[str, Any]]) -> list[RAGChunk]:
    """Section 6: Generate expected 759 OSM chunks in memory and validate ID invariants."""
    chunks: list[RAGChunk] = []
    for place in places:
        chunk = build_osm_place_chunk(place)
        if chunk is not None:
            chunks.append(chunk)

    if len(chunks) != EXPECTED_OSM_DOCUMENTS:
        raise ValueError(
            f"EXPECTED_OSM_DOCUMENTS_MISMATCH: expected {EXPECTED_OSM_DOCUMENTS}, got {len(chunks)}"
        )

    doc_ids = [c.document_id for c in chunks]
    place_ids = [c.place_id for c in chunks if c.place_id]
    if len(set(doc_ids)) != EXPECTED_OSM_DOCUMENTS:
        raise ValueError(
            f"EXPECTED_OSM_DOCUMENT_ID_DUPLICATES: unique={len(set(doc_ids))} != {EXPECTED_OSM_DOCUMENTS}"
        )
    if len(set(place_ids)) != EXPECTED_OSM_DOCUMENTS:
        raise ValueError(
            f"EXPECTED_OSM_PLACE_ID_DUPLICATES: unique={len(set(place_ids))} != {EXPECTED_OSM_DOCUMENTS}"
        )

    for c in chunks:
        expected_doc_id = f"osm-place-{c.place_id}"
        if c.document_id != expected_doc_id or c.chunk_id != expected_doc_id:
            raise ValueError(
                f"INVALID_EXPECTED_DOCUMENT_ID: got document_id={c.document_id}, chunk_id={c.chunk_id}, expected={expected_doc_id}"
            )

    return sorted(chunks, key=lambda x: x.document_id)


def compute_expected_delta_and_collision_guard(
    db_osm_rows: list[dict[str, Any]],
    expected_chunks: list[RAGChunk],
) -> dict[str, Any]:
    """Section 7 & 8: Precompute expected delta and enforce pairwise stale-safety collision guard."""
    db_by_doc_id: dict[str, str] = {}
    for row in db_osm_rows:
        did = str(row["document_id"])
        if did in db_by_doc_id:
            raise ValueError(
                f"PRE_REINGESTION_STATE_MISMATCH: duplicate OSM document_id in DB: {did}"
            )
        db_by_doc_id[did] = str(row["content_hash"])

    exp_by_doc_id: dict[str, str] = {}
    for ch in expected_chunks:
        if ch.document_id in exp_by_doc_id:
            raise ValueError(
                f"EXPECTED_OSM_DOCUMENT_ID_DUPLICATES: duplicate expected document_id: {ch.document_id}"
            )
        exp_by_doc_id[ch.document_id] = ch.content_hash

    exp_hashes = [ch.content_hash for ch in expected_chunks]
    expected_content_hash_duplicates = len(exp_hashes) - len(set(exp_hashes))
    if expected_content_hash_duplicates != 0:
        raise ValueError(
            f"EXPECTED_CONTENT_HASH_DUPLICATES_DETECTED: {expected_content_hash_duplicates} duplicate hashes"
        )

    exp_hash_set = set(exp_hashes)
    missing_in_db = sorted(set(exp_by_doc_id) - set(db_by_doc_id))
    unexpected_in_db = sorted(set(db_by_doc_id) - set(exp_by_doc_id))
    if missing_in_db or unexpected_in_db:
        raise ValueError(
            "PRE_REINGESTION_STATE_MISMATCH: "
            f"missing_in_db={len(missing_in_db)}, unexpected_in_db={len(unexpected_in_db)}"
        )

    changed_doc_ids: list[str] = []
    unchanged_doc_ids: list[str] = []
    cross_pair_collisions: list[str] = []

    for did in sorted(exp_by_doc_id):
        old_hash = db_by_doc_id[did]
        new_hash = exp_by_doc_id[did]
        if old_hash == new_hash:
            unchanged_doc_ids.append(did)
        else:
            changed_doc_ids.append(did)
            if old_hash in exp_hash_set:
                cross_pair_collisions.append(did)

    cross_pair_collision_count = len(cross_pair_collisions)
    if cross_pair_collision_count != 0:
        raise ValueError(
            f"CROSS_PAIR_HASH_COLLISION_DETECTED: {cross_pair_collision_count} collisions ({cross_pair_collisions[:5]})"
        )

    if len(changed_doc_ids) + len(unchanged_doc_ids) != EXPECTED_OSM_DOCUMENTS:
        raise ValueError(
            "DELTA_TOTAL_MISMATCH: "
            f"{len(changed_doc_ids)} + {len(unchanged_doc_ids)} != {EXPECTED_OSM_DOCUMENTS}"
        )

    return {
        "EXPECTED_OSM_DOCUMENTS": len(expected_chunks),
        "MISSING_IN_DB": len(missing_in_db),
        "UNEXPECTED_IN_DB": len(unexpected_in_db),
        "EXPECTED_CHANGED_CONTENT_HASH_COUNT": len(changed_doc_ids),
        "EXPECTED_UNCHANGED_CONTENT_HASH_COUNT": len(unchanged_doc_ids),
        "EXPECTED_CONTENT_HASH_DUPLICATES": expected_content_hash_duplicates,
        "CROSS_PAIR_HASH_COLLISION_COUNT": cross_pair_collision_count,
        "changed_document_ids": changed_doc_ids,
        "unchanged_document_ids": unchanged_doc_ids,
    }


def build_osm_semantic_snapshot(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Section 9 & 21: Build deterministic semantic snapshot for OSM documents excluding id, created_at, updated_at."""
    snapshot: list[dict[str, Any]] = []
    for r in rows:
        item = {
            "document_id": str(r["document_id"]),
            "place_id": str(r["place_id"]) if r.get("place_id") is not None else None,
            "source_name": str(r["source_name"]),
            "source_url": str(r.get("source_url") or ""),
            "license": str(r.get("license") or ""),
            "attribution": str(r.get("attribution") or ""),
            "language": str(r.get("language") or ""),
            "topic": str(r.get("topic") or ""),
            "title": str(r.get("title") or ""),
            "category": str(r["category"]) if r.get("category") is not None else None,
            "content": str(r.get("content") or ""),
            "content_hash": str(r.get("content_hash") or ""),
            "embedding_model": str(r.get("embedding_model") or ""),
            "metadata": _normalize_metadata(r.get("metadata")),
            "retrieved_at": _normalize_timestamp(r.get("retrieved_at")),
        }
        snapshot.append(item)
    snapshot.sort(key=lambda x: (x["document_id"], x["content_hash"]))
    return snapshot


def compute_osm_semantic_sha256(rows: list[dict[str, Any]]) -> str:
    """Compute SHA-256 of the canonical OSM semantic snapshot."""
    return _canonical_sha256(build_osm_semantic_snapshot(rows))


def build_wikivoyage_semantic_snapshot(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Section 9 & 18: Build deterministic semantic snapshot for Wikivoyage documents."""
    snapshot: list[dict[str, Any]] = []
    for r in rows:
        item = {
            "document_id": str(r["document_id"]),
            "destination_id": (
                str(r["destination_id"]) if r.get("destination_id") is not None else None
            ),
            "place_id": str(r["place_id"]) if r.get("place_id") is not None else None,
            "source_name": str(r["source_name"]),
            "source_url": str(r.get("source_url") or ""),
            "license": str(r.get("license") or ""),
            "attribution": str(r.get("attribution") or ""),
            "language": str(r.get("language") or ""),
            "topic": str(r.get("topic") or ""),
            "section_heading": (
                str(r["section_heading"])
                if r.get("section_heading") is not None
                else None
            ),
            "title": str(r.get("title") or ""),
            "category": str(r["category"]) if r.get("category") is not None else None,
            "content": str(r.get("content") or ""),
            "content_hash": str(r.get("content_hash") or ""),
            "embedding_model": str(r.get("embedding_model") or ""),
            "metadata": _normalize_metadata(r.get("metadata")),
            "retrieved_at": _normalize_timestamp(r.get("retrieved_at")),
        }
        snapshot.append(item)
    snapshot.sort(key=lambda x: (x["document_id"], x["content_hash"]))
    return snapshot


def compute_wikivoyage_semantic_sha256(rows: list[dict[str, Any]]) -> str:
    """Compute SHA-256 of the canonical Wikivoyage semantic snapshot."""
    return _canonical_sha256(build_wikivoyage_semantic_snapshot(rows))


def verify_run1_post_state(
    *,
    before_osm_snapshot: list[dict[str, Any]],
    after_run1_osm_snapshot: list[dict[str, Any]],
    expected_chunks: list[RAGChunk],
    expected_changed_count: int,
    expected_unchanged_count: int,
    after_run1_counts: dict[str, Any],
    quarantine_before: dict[str, int],
    quarantine_after_run1: dict[str, int],
    wikivoyage_before_sha256: str,
    wikivoyage_after_run1_sha256: str,
) -> dict[str, Any]:
    """Sections 12, 13, 14, 15, 18, 19: Verify RUN 1 post-ingestion invariants."""
    validate_preflight_state(after_run1_counts)

    if len(after_run1_osm_snapshot) != EXPECTED_OSM_DOCUMENTS:
        raise ValueError(
            f"RUN1_OSM_COUNT_MISMATCH: expected {EXPECTED_OSM_DOCUMENTS}, got {len(after_run1_osm_snapshot)}"
        )

    if wikivoyage_after_run1_sha256 != wikivoyage_before_sha256:
        raise ValueError(
            "WIKIVOYAGE_INVARIANCE_VIOLATION: "
            f"after_run1={wikivoyage_after_run1_sha256} != before={wikivoyage_before_sha256}"
        )

    exp_by_doc_id = {c.document_id: c for c in expected_chunks}
    before_by_doc_id = {r["document_id"]: r for r in before_osm_snapshot}
    after_by_doc_id = {r["document_id"]: r for r in after_run1_osm_snapshot}

    if set(after_by_doc_id) != set(exp_by_doc_id):
        raise ValueError("RUN1_DOCUMENT_ID_SET_MISMATCH")

    mismatch_count = 0
    actual_changed = 0
    actual_unchanged = 0

    for did, row in after_by_doc_id.items():
        exp = exp_by_doc_id[did]
        exp_meta = _normalize_metadata(exp.metadata)
        exp_ret = _normalize_timestamp(getattr(exp, "retrieved_at", None))
        if (
            row["content"] != exp.content
            or row["content_hash"] != exp.content_hash
            or row["place_id"] != exp.place_id
            or row["source_name"] != exp.source_name
            or row["license"] != exp.license
            or row["attribution"] != exp.attribution
            or row["category"] != exp.category
            or row["metadata"] != exp_meta
            or (exp_ret is not None and row["retrieved_at"] != exp_ret)
        ):
            mismatch_count += 1

        old_row = before_by_doc_id[did]
        if row["content_hash"] != old_row["content_hash"]:
            actual_changed += 1
        else:
            actual_unchanged += 1

    if mismatch_count != 0:
        raise ValueError(
            f"OSM_EXPECTED_STATE_MISMATCH: {mismatch_count} documents did not match expected chunks"
        )

    if actual_changed != expected_changed_count or actual_unchanged != expected_unchanged_count:
        raise ValueError(
            "RUN1_CHANGED_COUNT_MISMATCH: "
            f"actual=({actual_changed}, {actual_unchanged}) != expected=({expected_changed_count}, {expected_unchanged_count})"
        )

    new_q_total = quarantine_after_run1["total_rows"] - quarantine_before["total_rows"]
    new_q_superseded = (
        quarantine_after_run1["osm_superseded_rows"]
        - quarantine_before["osm_superseded_rows"]
    )
    if new_q_total != new_q_superseded or new_q_superseded != actual_changed:
        raise ValueError(
            "RUN1_QUARANTINE_MISMATCH: "
            f"new_q_total={new_q_total}, new_q_superseded={new_q_superseded}, actual_changed={actual_changed}"
        )

    return {
        "TOTAL_DOCUMENTS_AFTER_RUN1": after_run1_counts["total_documents"],
        "OSM_DOCUMENTS_AFTER_RUN1": after_run1_counts["osm_documents"],
        "WIKIVOYAGE_DOCUMENTS_AFTER_RUN1": after_run1_counts["wikivoyage_documents"],
        "OSM_EXPECTED_STATE_MISMATCH_COUNT": mismatch_count,
        "ACTUAL_CHANGED_CONTENT_HASH_COUNT": actual_changed,
        "ACTUAL_UNCHANGED_CONTENT_HASH_COUNT": actual_unchanged,
        "NEW_OSM_QUARANTINE_ROWS_RUN1": new_q_superseded,
        "QUARANTINE_REASON_VERIFIED": QUARANTINE_SUPERSEDED_REASON,
        "WIKIVOYAGE_AFTER_RUN1_SHA256": wikivoyage_after_run1_sha256,
    }


def verify_run2_idempotency(
    *,
    after_run1_osm_snapshot: list[dict[str, Any]],
    after_run2_osm_snapshot: list[dict[str, Any]],
    after_run2_counts: dict[str, Any],
    quarantine_after_run1: dict[str, int],
    quarantine_after_run2: dict[str, int],
    wikivoyage_before_sha256: str,
    wikivoyage_after_run2_sha256: str,
) -> dict[str, Any]:
    """Sections 21, 22, 23: Verify RUN 2 semantic idempotency and zero new quarantine rows."""
    validate_preflight_state(after_run2_counts)

    run1_sha = _canonical_sha256(after_run1_osm_snapshot)
    run2_sha = _canonical_sha256(after_run2_osm_snapshot)

    r1_by_id = {r["document_id"]: r for r in after_run1_osm_snapshot}
    r2_by_id = {r["document_id"]: r for r in after_run2_osm_snapshot}
    semantic_changes = 0
    for did in set(r1_by_id) | set(r2_by_id):
        if r1_by_id.get(did) != r2_by_id.get(did):
            semantic_changes += 1

    if run1_sha != run2_sha or semantic_changes != 0:
        raise ValueError(
            "RUN2_SEMANTIC_IDEMPOTENCY_VIOLATION: "
            f"run1_sha={run1_sha}, run2_sha={run2_sha}, semantic_changes={semantic_changes}"
        )

    new_q_total_run2 = (
        quarantine_after_run2["total_rows"] - quarantine_after_run1["total_rows"]
    )
    new_q_superseded_run2 = (
        quarantine_after_run2["osm_superseded_rows"]
        - quarantine_after_run1["osm_superseded_rows"]
    )
    if new_q_total_run2 != 0 or new_q_superseded_run2 != 0:
        raise ValueError(
            "RUN2_QUARANTINE_VIOLATION: "
            f"new_q_total_run2={new_q_total_run2}, new_q_superseded_run2={new_q_superseded_run2}"
        )

    if wikivoyage_after_run2_sha256 != wikivoyage_before_sha256:
        raise ValueError(
            "WIKIVOYAGE_RUN2_INVARIANCE_VIOLATION: "
            f"after_run2={wikivoyage_after_run2_sha256} != before={wikivoyage_before_sha256}"
        )

    return {
        "TOTAL_DOCUMENTS_AFTER_RUN2": after_run2_counts["total_documents"],
        "OSM_DOCUMENTS_AFTER_RUN2": after_run2_counts["osm_documents"],
        "WIKIVOYAGE_DOCUMENTS_AFTER_RUN2": after_run2_counts["wikivoyage_documents"],
        "OSM_AFTER_RUN1_SEMANTIC_SHA256": run1_sha,
        "OSM_AFTER_RUN2_SEMANTIC_SHA256": run2_sha,
        "RUN2_SEMANTIC_CHANGE_COUNT": semantic_changes,
        "NEW_OSM_QUARANTINE_ROWS_RUN2": new_q_superseded_run2,
        "WIKIVOYAGE_AFTER_RUN2_SHA256": wikivoyage_after_run2_sha256,
    }


def evaluate_target_60_stored_docs(
    *,
    before_osm_snapshot: list[dict[str, Any]],
    after_osm_snapshot: list[dict[str, Any]],
    target_manifest_pois: list[dict[str, Any]],
) -> dict[str, Any]:
    """Sections 16 & 17: Inspect actual stored DB documents for the frozen 60 target POIs."""
    if len(target_manifest_pois) != EXPECTED_TARGET_POIS:
        raise ValueError(
            f"TARGET_POI_MANIFEST_MISMATCH: expected {EXPECTED_TARGET_POIS}, got {len(target_manifest_pois)}"
        )

    before_by_pid = {r["place_id"]: r for r in before_osm_snapshot if r.get("place_id")}
    after_by_pid = {r["place_id"]: r for r in after_osm_snapshot if r.get("place_id")}

    useful_count = 0
    low_info_count = 0
    changed_target_count = 0
    unchanged_target_count = 0
    sample_by_pid: dict[str, dict[str, Any]] = {}

    for tp in target_manifest_pois:
        pid = str(tp["poi_id"])
        if pid not in after_by_pid or pid not in before_by_pid:
            raise ValueError(f"MISSING_STORED_TARGET_POI_DOCUMENT: {pid}")

        old_doc = before_by_pid[pid]
        new_doc = after_by_pid[pid]
        has_addr = "Địa chỉ:" in new_doc["content"]
        tags_used = list(new_doc["metadata"].get("osm_tags_used") or [])

        if has_addr or len(tags_used) > 0:
            useful_count += 1
        else:
            low_info_count += 1

        if old_doc["content_hash"] != new_doc["content_hash"]:
            changed_target_count += 1
        else:
            unchanged_target_count += 1

        if pid in SAMPLE_TARGET_POI_IDS:
            old_tags = set(old_doc["metadata"].get("osm_tags_used") or [])
            newly_surfaced = [t for t in tags_used if t not in old_tags]
            if has_addr and "Địa chỉ:" not in old_doc["content"]:
                newly_surfaced = ["address (addr:*)"] + newly_surfaced
            sample_by_pid[pid] = {
                "poi_id": pid,
                "poi_name": new_doc["title"],
                "city": str(tp.get("city") or ""),
                "old_content_hash": old_doc["content_hash"],
                "new_content_hash": new_doc["content_hash"],
                "fields_newly_surfaced": newly_surfaced,
            }

    if (
        useful_count != EXPECTED_TARGET_USEFUL_STRUCTURED
        or low_info_count != EXPECTED_TARGET_LOW_INFORMATION
    ):
        raise ValueError(
            "TARGET_60_UTILITY_MISMATCH: "
            f"useful={useful_count} (expected {EXPECTED_TARGET_USEFUL_STRUCTURED}), "
            f"low_info={low_info_count} (expected {EXPECTED_TARGET_LOW_INFORMATION})"
        )

    ordered_samples = [
        sample_by_pid[pid] for pid in SAMPLE_TARGET_POI_IDS if pid in sample_by_pid
    ]
    if len(ordered_samples) != len(SAMPLE_TARGET_POI_IDS):
        raise ValueError("MISSING_SAMPLE_TARGET_POI_EVIDENCE")

    return {
        "TARGET_POI_DOCUMENTS": len(target_manifest_pois),
        "TARGET_USEFUL_STRUCTURED_DOCUMENTS": useful_count,
        "TARGET_LOW_INFORMATION_DOCUMENTS": low_info_count,
        "TARGET_CHANGED_CONTENT_HASH_COUNT": changed_target_count,
        "TARGET_UNCHANGED_CONTENT_HASH_COUNT": unchanged_target_count,
        "sample_before_after_evidence": ordered_samples,
    }


async def _fetch_db_counts_and_quarantine(conn: Any) -> tuple[dict[str, Any], dict[str, int]]:
    has_q = bool(
        await conn.fetchval("SELECT to_regclass('document_quarantine') IS NOT NULL")
    )
    total = int(await conn.fetchval("SELECT count(*) FROM documents"))
    osm = int(
        await conn.fetchval("SELECT count(*) FROM documents WHERE source_name = 'osm'")
    )
    wv = int(
        await conn.fetchval(
            "SELECT count(*) FROM documents WHERE source_name = 'wikivoyage'"
        )
    )
    uniq_doc_id = int(
        await conn.fetchval(
            "SELECT count(DISTINCT document_id) FROM documents WHERE source_name = 'osm'"
        )
    )
    uniq_place_id = int(
        await conn.fetchval(
            "SELECT count(DISTINCT place_id) FROM documents WHERE source_name = 'osm'"
        )
    )
    null_place = int(
        await conn.fetchval(
            "SELECT count(*) FROM documents WHERE source_name = 'osm' AND place_id IS NULL"
        )
    )
    unverified_osm = int(
        await conn.fetchval(
            """
            SELECT count(*) FROM documents d
            WHERE d.source_name = 'osm' AND NOT (
                  d.place_id IS NOT NULL
              AND EXISTS (SELECT 1 FROM places p WHERE p.id = d.place_id AND p.deleted_at IS NULL)
              AND EXISTS (
                  SELECT 1 FROM place_sources ps
                  WHERE ps.place_id = d.place_id
                    AND ps.source_name = d.source_name
                    AND ps.source_id = d.metadata->>'source_id'
              )
              AND d.license = $1
              AND d.attribution = $2
              AND d.source_url = 'https://www.openstreetmap.org/' || (d.metadata->>'source_id')
              AND d.embedding_model = $3
              AND d.retrieved_at IS NOT NULL
              AND length(d.content_hash) = 64
            )
            """,
            OSM_LICENSE,
            OSM_ATTRIBUTION,
            EXPECTED_EMBEDDING_MODEL,
        )
    )
    counts = {
        "quarantine_table_exists": has_q,
        "total_documents": total,
        "osm_documents": osm,
        "wikivoyage_documents": wv,
        "unique_osm_document_ids": uniq_doc_id,
        "duplicate_osm_document_ids": osm - uniq_doc_id,
        "unique_osm_place_ids": uniq_place_id,
        "duplicate_osm_place_ids": osm - uniq_place_id,
        "null_place_id_osm_documents": null_place,
        "unverified_osm_documents": unverified_osm,
    }
    if has_q:
        q_total = int(await conn.fetchval("SELECT count(*) FROM document_quarantine"))
        q_sup = int(
            await conn.fetchval(
                "SELECT count(*) FROM document_quarantine WHERE reason = $1",
                QUARANTINE_SUPERSEDED_REASON,
            )
        )
    else:
        q_total = 0
        q_sup = 0
    quarantine = {
        "total_rows": q_total,
        "osm_superseded_rows": q_sup,
    }
    return counts, quarantine


async def _fetch_osm_rows(conn: Any) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        """
        SELECT document_id, place_id::text AS place_id, source_name, source_url,
               license, attribution, language, topic, title, category,
               content, content_hash, embedding_model, metadata, retrieved_at
        FROM documents
        WHERE source_name = 'osm'
        ORDER BY document_id
        """
    )
    return [dict(r) for r in rows]


async def _fetch_wikivoyage_rows(conn: Any) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        """
        SELECT document_id, destination_id::text AS destination_id, place_id::text AS place_id,
               source_name, source_url, license, attribution, language, topic,
               section_heading, title, category, content, content_hash,
               embedding_model, metadata, retrieved_at
        FROM documents
        WHERE source_name = 'wikivoyage'
        ORDER BY document_id, content_hash
        """
    )
    return [dict(r) for r in rows]


async def _verify_embedding_validity(conn: Any) -> dict[str, Any]:
    null_emb = int(
        await conn.fetchval("SELECT count(*) FROM documents WHERE embedding IS NULL")
    )
    osm_null_emb = int(
        await conn.fetchval(
            "SELECT count(*) FROM documents WHERE source_name = 'osm' AND embedding IS NULL"
        )
    )
    dims_rows = await conn.fetch(
        "SELECT DISTINCT vector_dims(embedding) AS dim FROM documents ORDER BY dim"
    )
    dims = [int(r["dim"]) for r in dims_rows]
    model_rows = await conn.fetch(
        "SELECT DISTINCT embedding_model FROM documents WHERE source_name = 'osm' ORDER BY embedding_model"
    )
    osm_models = [str(r["embedding_model"]) for r in model_rows]
    all_model_rows = await conn.fetch(
        "SELECT DISTINCT embedding_model FROM documents ORDER BY embedding_model"
    )
    all_models = [str(r["embedding_model"]) for r in all_model_rows]
    dup_hash_model = int(
        await conn.fetchval(
            "SELECT count(*) - count(DISTINCT (content_hash, embedding_model)) FROM documents"
        )
    )
    hnsw_idx = int(
        await conn.fetchval(
            "SELECT count(*) FROM pg_indexes WHERE indexname = 'documents_embedding_hnsw_idx'"
        )
    )

    if (
        null_emb != 0
        or osm_null_emb != 0
        or dims != [EXPECTED_EMBEDDING_DIM]
        or osm_models != [EXPECTED_EMBEDDING_MODEL]
        or all_models != [EXPECTED_EMBEDDING_MODEL]
        or dup_hash_model != 0
        or hnsw_idx != 1
    ):
        raise ValueError(
            "EMBEDDING_VALIDITY_FAILURE: "
            f"null_emb={null_emb}, dims={dims}, osm_models={osm_models}, dup_hash_model={dup_hash_model}, hnsw_idx={hnsw_idx}"
        )

    return {
        "null_embedding_count_all": null_emb,
        "null_embedding_count_osm": osm_null_emb,
        "distinct_vector_dims": dims,
        "OSM_EMBEDDING_MODEL_SET": osm_models,
        "ALL_DOCUMENTS_EMBEDDING_MODEL_SET": all_models,
        "duplicate_content_hash_embedding_model_count": dup_hash_model,
        "hnsw_index_present": hnsw_idx == 1,
    }


async def _run_retrieval_smoke_checks(retriever: Any, pool: Any) -> dict[str, Any]:
    """Section 25: Read-only retrieval smoke checks proving repaired stored OSM documents are retrievable."""
    async with pool.acquire() as conn:
        hanoi_id = await conn.fetchval(
            "SELECT id::text FROM destinations WHERE name = 'Hà Nội'"
        )

    # 1. Culture/museum Hà Nội query
    res_culture = await retriever.search(
        GROUNDING_CULTURE_HANOI,
        top_k=5,
        destination_id=hanoi_id,
        source_name="osm",
        min_similarity=0.3,
    )
    if not res_culture or not any(r["category"] == "culture" for r in res_culture):
        raise ValueError("RETRIEVAL_SMOKE_FAILURE: culture/museum Hà Nội query returned no culture hits")

    # 2. Opening-hours query on a nested-tags target POI (Lăng Chủ tịch Hồ Chí Minh)
    oh_place_name = "Lăng Chủ tịch Hồ Chí Minh"
    res_oh = await retriever.search(
        opening_hours_query(oh_place_name),
        top_k=5,
        source_name="osm",
        min_similarity=0.3,
    )
    oh_hits = [
        r
        for r in res_oh
        if r["title"] == oh_place_name and "Giờ mở cửa:" in r["content"]
    ]
    if not oh_hits:
        raise ValueError(
            f"RETRIEVAL_SMOKE_FAILURE: opening-hours query for {oh_place_name} did not return rendered opening hours"
        )

    # 3. Restaurant/cuisine query in Hà Nội
    cuisine_query = "Nhà hàng ẩm thực Việt Nam tại Hà Nội Quán Ăn Ngon"
    res_cuisine = await retriever.search(
        cuisine_query,
        top_k=5,
        destination_id=hanoi_id,
        source_name="osm",
        min_similarity=0.3,
    )
    cuisine_hits = [
        r
        for r in res_cuisine
        if r["category"] == "restaurant" and "Ẩm thực:" in r["content"]
    ]
    if not cuisine_hits:
        raise ValueError(
            "RETRIEVAL_SMOKE_FAILURE: restaurant/cuisine query did not return rendered cuisine facts"
        )

    return {
        "status": "PASS",
        "checks": [
            {
                "check_id": "SMOKE-01-CULTURE-HANOI",
                "query": GROUNDING_CULTURE_HANOI,
                "source_filter": "osm",
                "hits_returned": len(res_culture),
                "top_hit_document_id": res_culture[0]["document_id"],
                "top_hit_title": res_culture[0]["title"],
                "top_hit_category": res_culture[0]["category"],
                "verified_fact_present": True,
            },
            {
                "check_id": "SMOKE-02-OPENING-HOURS-NESTED-TAG",
                "query": opening_hours_query(oh_place_name),
                "source_filter": "osm",
                "hits_returned": len(res_oh),
                "matched_document_id": oh_hits[0]["document_id"],
                "matched_title": oh_hits[0]["title"],
                "verified_fact_present": "Giờ mở cửa:" in oh_hits[0]["content"],
            },
            {
                "check_id": "SMOKE-03-RESTAURANT-CUISINE-NESTED-TAG",
                "query": cuisine_query,
                "source_filter": "osm",
                "hits_returned": len(res_cuisine),
                "matched_document_id": cuisine_hits[0]["document_id"],
                "matched_title": cuisine_hits[0]["title"],
                "verified_fact_present": "Ẩm thực:" in cuisine_hits[0]["content"],
            },
        ],
    }


def _load_offline_embedder() -> Any:
    """Section 5: Enforce offline mode and verify local cache for SentenceTransformerEmbedder."""
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    from app.rag.embedder import SentenceTransformerEmbedder

    embedder = SentenceTransformerEmbedder(EXPECTED_EMBEDDING_MODEL)
    probe_vec = embedder.embed_text("preflight offline cache check")
    if len(probe_vec) != EXPECTED_EMBEDDING_DIM:
        raise ValueError(
            f"EMBEDDING_DIM_MISMATCH: expected {EXPECTED_EMBEDDING_DIM}, got {len(probe_vec)}"
        )
    return embedder


async def run_preflight() -> dict[str, Any]:
    """Execute read-only preflight (--preflight) without mutating the database."""
    embedder = _load_offline_embedder()
    from app.rag.ingestion import WikivoyageIngester
    from app.rag.retriever import RAGRetriever

    retriever = RAGRetriever(embedder=embedder)
    try:
        pool = await retriever.get_pool()
        async with pool.acquire() as conn:
            counts_before, quarantine_before = await _fetch_db_counts_and_quarantine(
                conn
            )
            validate_preflight_state(counts_before)
            osm_rows_before = await _fetch_osm_rows(conn)
            wv_rows_before = await _fetch_wikivoyage_rows(conn)

        ingester = WikivoyageIngester(retriever)
        places = await ingester.fetch_verified_places()
        expected_chunks = generate_expected_osm_chunks(places)
        delta_info = compute_expected_delta_and_collision_guard(
            osm_rows_before, expected_chunks
        )
        osm_before_sha = compute_osm_semantic_sha256(osm_rows_before)
        wv_before_sha = compute_wikivoyage_semantic_sha256(wv_rows_before)

        return {
            "status": "PREFLIGHT_PASS",
            "db_mutation_executed": False,
            "before_counts": counts_before,
            "quarantine_baseline": quarantine_before,
            "embedding_preflight": {
                "embedding_model": embedder.model_name,
                "dimension": embedder.dimension,
                "offline_cache_verified": True,
                "HF_HUB_OFFLINE": os.environ.get("HF_HUB_OFFLINE"),
                "NEW_MODEL_DOWNLOADS": 0,
            },
            "expected_generation_and_delta": {
                k: v
                for k, v in delta_info.items()
                if k not in ("changed_document_ids", "unchanged_document_ids")
            },
            "OSM_BEFORE_SEMANTIC_SHA256": osm_before_sha,
            "WIKIVOYAGE_BEFORE_SHA256": wv_before_sha,
        }
    finally:
        await retriever.close()


def _verify_b1a_and_upstream_hashes(repo_root: Path = REPO_ROOT) -> dict[str, str]:
    b1a_res = w07_b1a.verify_b1a_audit_artifacts(repo_root)
    if b1a_res["audit_internal_sha256"] != EXPECTED_B1A_JSON_INTERNAL_SHA256:
        raise ValueError("B1A_JSON_INTERNAL_SHA256_MISMATCH")
    if b1a_res["audit_file_lf_sha256"] != EXPECTED_B1A_JSON_LF_SHA256:
        raise ValueError("B1A_JSON_LF_SHA256_MISMATCH")
    if b1a_res["audit_md_lf_sha256"] != EXPECTED_B1A_MD_LF_SHA256:
        raise ValueError("B1A_MD_LF_SHA256_MISMATCH")

    upstream = w07_b1a.verify_all_upstream_immutability(repo_root)
    return {
        **upstream,
        "w07_b1a_audit_internal_sha256": b1a_res["audit_internal_sha256"],
        "w07_b1a_audit_lf_sha256": b1a_res["audit_file_lf_sha256"],
        "w07_b1a_md_lf_sha256": b1a_res["audit_md_lf_sha256"],
    }


def _build_markdown_report(receipt: dict[str, Any]) -> str:
    bc = receipt["before_counts"]
    qb = receipt["quarantine_baseline"]
    ed = receipt["expected_generation_and_delta"]
    r1 = receipt["run_1"]
    r2 = receipt["run_2"]
    t60 = receipt["target_60_verification"]
    emb = receipt["embedding_validity"]
    smoke = receipt["retrieval_smoke"]
    up = receipt["upstream_frozen_hashes"]

    lines = [
        "# W07-B1-FIX-01B — Controlled OSM Re-ingestion Evidence Report",
        "",
        "## 1. Authority & Gate Status",
        "",
        f"- **Task ID**: `{receipt['task_id']}`",
        f"- **Authoritative Base (`develop`)**: `{receipt['authoritative_develop_sha']}`",
        f"- **Accepted Upstream Gate**: `{receipt['previous_accepted_gate']}` (`W07_B1_FIX_01A_STATUS = {receipt['w07_b1_fix_01a_status']}`)",
        f"- **Execution Status**: `{receipt['W07_B1_FIX_01B_EXECUTION']}`",
        f"- **`PDG_001_RENDERER_FIX_IMPLEMENTED`**: `{str(receipt['PDG_001_RENDERER_FIX_IMPLEMENTED']).lower()}`",
        f"- **`PDG_001_CONTROLLED_REINGESTION_VERIFIED`**: `{str(receipt['PDG_001_CONTROLLED_REINGESTION_VERIFIED']).lower()}`",
        f"- **`PDG_001_STATUS`**: `{receipt['PDG_001_STATUS']}`",
        f"- **Next Gate**: `{receipt['next_gate']}`",
        "",
        "---",
        "",
        "## 2. Preflight, Quarantine Baseline & Expected Delta",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| `TOTAL_DOCUMENTS_BEFORE` | `{bc['TOTAL_DOCUMENTS_BEFORE']}` |",
        f"| `OSM_DOCUMENTS_BEFORE` | `{bc['OSM_DOCUMENTS_BEFORE']}` |",
        f"| `WIKIVOYAGE_DOCUMENTS_BEFORE` | `{bc['WIKIVOYAGE_DOCUMENTS_BEFORE']}` |",
        f"| `unique_osm_document_ids` / `unique_osm_place_ids` | `{bc['unique_osm_document_ids']}` / `{bc['unique_osm_place_ids']}` |",
        f"| `quarantine_table_exists` | `{str(bc['quarantine_table_exists']).lower()}` |",
        f"| `QUARANTINE_ROWS_BEFORE` | `{qb['QUARANTINE_ROWS_BEFORE']}` (`{qb['QUARANTINE_OSM_SUPERSEDED_ROWS_BEFORE']}` with `{QUARANTINE_SUPERSEDED_REASON}`) |",
        f"| `EXPECTED_OSM_DOCUMENTS` | `{ed['EXPECTED_OSM_DOCUMENTS']}` |",
        f"| `EXPECTED_CHANGED_CONTENT_HASH_COUNT` | `{ed['EXPECTED_CHANGED_CONTENT_HASH_COUNT']}` |",
        f"| `EXPECTED_UNCHANGED_CONTENT_HASH_COUNT` | `{ed['EXPECTED_UNCHANGED_CONTENT_HASH_COUNT']}` |",
        f"| `CROSS_PAIR_HASH_COLLISION_COUNT` | `{ed['CROSS_PAIR_HASH_COLLISION_COUNT']}` |",
        f"| `EXPECTED_CONTENT_HASH_DUPLICATES` | `{ed['EXPECTED_CONTENT_HASH_DUPLICATES']}` |",
        f"| `OSM_BEFORE_SEMANTIC_SHA256` | `{receipt['OSM_BEFORE_SEMANTIC_SHA256']}` |",
        f"| `WIKIVOYAGE_BEFORE_SHA256` | `{receipt['WIKIVOYAGE_BEFORE_SHA256']}` |",
        "",
        "---",
        "",
        "## 3. Controlled Re-ingestion — RUN 1 & RUN 2",
        "",
        "| Metric | RUN 1 | RUN 2 (Semantic Idempotency) |",
        "|---|---|---|",
        f"| `verified_places` | `{r1['ingestion_result']['verified_places']}` | `{r2['ingestion_result']['verified_places']}` |",
        f"| `documents_generated` | `{r1['ingestion_result']['documents_generated']}` | `{r2['ingestion_result']['documents_generated']}` |",
        f"| `chunks_upserted` | `{r1['ingestion_result']['chunks_upserted']}` | `{r2['ingestion_result']['chunks_upserted']}` |",
        f"| `stale_osm_documents_quarantined_and_removed` | `{r1['ingestion_result']['stale_osm_documents_quarantined_and_removed']}` | `{r2['ingestion_result']['stale_osm_documents_quarantined_and_removed']}` |",
        f"| `TOTAL_DOCUMENTS_AFTER` | `{r1['TOTAL_DOCUMENTS_AFTER_RUN1']}` | `{r2['TOTAL_DOCUMENTS_AFTER_RUN2']}` |",
        f"| `OSM_DOCUMENTS_AFTER` | `{r1['OSM_DOCUMENTS_AFTER_RUN1']}` | `{r2['OSM_DOCUMENTS_AFTER_RUN2']}` |",
        f"| `WIKIVOYAGE_DOCUMENTS_AFTER` | `{r1['WIKIVOYAGE_DOCUMENTS_AFTER_RUN1']}` | `{r2['WIKIVOYAGE_DOCUMENTS_AFTER_RUN2']}` |",
        f"| `NEW_OSM_QUARANTINE_ROWS` | `{r1['NEW_OSM_QUARANTINE_ROWS_RUN1']}` | `{r2['NEW_OSM_QUARANTINE_ROWS_RUN2']}` |",
        f"| `OSM_SEMANTIC_SHA256` | `{r2['OSM_AFTER_RUN1_SEMANTIC_SHA256']}` | `{r2['OSM_AFTER_RUN2_SEMANTIC_SHA256']}` |",
        f"| `WIKIVOYAGE_SHA256` | `{r1['WIKIVOYAGE_AFTER_RUN1_SHA256']}` | `{r2['WIKIVOYAGE_AFTER_RUN2_SHA256']}` |",
        "",
        f"- **`ACTUAL_CHANGED_CONTENT_HASH_COUNT`**: `{r1['ACTUAL_CHANGED_CONTENT_HASH_COUNT']}` (`== EXPECTED_CHANGED_CONTENT_HASH_COUNT`)",
        f"- **`ACTUAL_UNCHANGED_CONTENT_HASH_COUNT`**: `{r1['ACTUAL_UNCHANGED_CONTENT_HASH_COUNT']}` (`== EXPECTED_UNCHANGED_CONTENT_HASH_COUNT`)",
        f"- **`OSM_EXPECTED_STATE_MISMATCH_COUNT`**: `{r1['OSM_EXPECTED_STATE_MISMATCH_COUNT']}`",
        f"- **`RUN2_SEMANTIC_CHANGE_COUNT`**: `{r2['RUN2_SEMANTIC_CHANGE_COUNT']}`",
        "",
        "---",
        "",
        "## 4. Frozen 60 Target POI Verification in Stored Documents",
        "",
        f"- **`TARGET_POI_DOCUMENTS`**: `{t60['TARGET_POI_DOCUMENTS']}`",
        f"- **`TARGET_USEFUL_STRUCTURED_DOCUMENTS`**: `{t60['TARGET_USEFUL_STRUCTURED_DOCUMENTS']}`",
        f"- **`TARGET_LOW_INFORMATION_DOCUMENTS`**: `{t60['TARGET_LOW_INFORMATION_DOCUMENTS']}`",
        f"- **`TARGET_CHANGED_CONTENT_HASH_COUNT`**: `{t60['TARGET_CHANGED_CONTENT_HASH_COUNT']}` / `60`",
        "",
        "### Deterministic 5-POI Before/After Sample",
        "",
        "| POI ID | Name | City | Old Content Hash | New Content Hash | Newly Surfaced Fields |",
        "|---|---|---|---|---|---|",
    ]

    for s in t60["sample_before_after_evidence"]:
        fields_str = ", ".join(f"`{f}`" for f in s["fields_newly_surfaced"])
        lines.append(
            f"| `{s['poi_id']}` | {s['poi_name']} | {s['city']} | `{s['old_content_hash'][:16]}...` | `{s['new_content_hash'][:16]}...` | {fields_str} |"
        )

    lines.extend(
        [
            "",
            "---",
            "",
            "## 5. Embedding Validity & Retrieval Smoke Checks",
            "",
            f"- **`OSM_EMBEDDING_MODEL_SET`**: `{emb['OSM_EMBEDDING_MODEL_SET']}`",
            f"- **`distinct_vector_dims`**: `{emb['distinct_vector_dims']}`",
            f"- **`null_embedding_count_all`**: `{emb['null_embedding_count_all']}`",
            f"- **`duplicate_content_hash_embedding_model_count`**: `{emb['duplicate_content_hash_embedding_model_count']}`",
            f"- **Retrieval Smoke Status**: `{smoke['status']}` (`{len(smoke['checks'])}` checks passed)",
            "",
            "---",
            "",
            "## 6. Historical B1A & Upstream Immutability",
            "",
            f"- **B1A JSON Internal SHA-256**: `{up['w07_b1a_audit_internal_sha256']}`",
            f"- **B1A JSON LF SHA-256**: `{up['w07_b1a_audit_lf_sha256']}`",
            f"- **B1A Markdown LF SHA-256**: `{up['w07_b1a_md_lf_sha256']}`",
            f"- **`NEW_WEB_DOCUMENT_DOWNLOADS`**: `{receipt['no_external_activity']['NEW_WEB_DOCUMENT_DOWNLOADS']}`",
            f"- **`NEW_SOCIAL_COLLECTION`**: `{receipt['no_external_activity']['NEW_SOCIAL_COLLECTION']}`",
            f"- **`NEW_GOOGLE_MAPS_COLLECTION`**: `{receipt['no_external_activity']['NEW_GOOGLE_MAPS_COLLECTION']}`",
            f"- **`NEW_LLM_PROVIDER_CALLS`**: `{receipt['no_external_activity']['NEW_LLM_PROVIDER_CALLS']}`",
            f"- **`NEW_EXTERNAL_API_CALLS_FOR_CORPUS`**: `{receipt['no_external_activity']['NEW_EXTERNAL_API_CALLS_FOR_CORPUS']}`",
            f"- **`NEW_MODEL_DOWNLOADS`**: `{receipt['no_external_activity']['NEW_MODEL_DOWNLOADS']}`",
            "",
        ]
    )
    return "\n".join(lines)


async def execute_controlled_reingestion(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Execute controlled RUN 1 + RUN 2 OSM re-ingestion and write receipt/report artifacts."""
    upstream_hashes = _verify_b1a_and_upstream_hashes(repo_root)
    embedder = _load_offline_embedder()

    from app.rag.ingestion import WikivoyageIngester
    from app.rag.retriever import RAGRetriever

    retriever = RAGRetriever(embedder=embedder)
    try:
        pool = await retriever.get_pool()
        async with pool.acquire() as conn:
            counts_before, quarantine_before = await _fetch_db_counts_and_quarantine(
                conn
            )
            validate_preflight_state(counts_before)
            osm_rows_before = await _fetch_osm_rows(conn)
            wv_rows_before = await _fetch_wikivoyage_rows(conn)

        ingester = WikivoyageIngester(retriever)
        places = await ingester.fetch_verified_places()
        expected_chunks = generate_expected_osm_chunks(places)
        delta_info = compute_expected_delta_and_collision_guard(
            osm_rows_before, expected_chunks
        )

        osm_before_snapshot = build_osm_semantic_snapshot(osm_rows_before)
        osm_before_sha = _canonical_sha256(osm_before_snapshot)
        wv_before_sha = compute_wikivoyage_semantic_sha256(wv_rows_before)

        # Controlled RUN 1
        run1_ingest_res = await ingester.ingest_canonical_places()
        if (
            run1_ingest_res.get("verified_places") != EXPECTED_OSM_DOCUMENTS
            or run1_ingest_res.get("documents_generated") != EXPECTED_OSM_DOCUMENTS
        ):
            raise ValueError(f"RUN1_INGEST_RESULT_MISMATCH: {run1_ingest_res}")

        async with pool.acquire() as conn:
            counts_after_run1, quarantine_after_run1 = (
                await _fetch_db_counts_and_quarantine(conn)
            )
            osm_rows_after_run1 = await _fetch_osm_rows(conn)
            wv_rows_after_run1 = await _fetch_wikivoyage_rows(conn)

        osm_after_run1_snapshot = build_osm_semantic_snapshot(osm_rows_after_run1)
        wv_after_run1_sha = compute_wikivoyage_semantic_sha256(wv_rows_after_run1)

        run1_ver = verify_run1_post_state(
            before_osm_snapshot=osm_before_snapshot,
            after_run1_osm_snapshot=osm_after_run1_snapshot,
            expected_chunks=expected_chunks,
            expected_changed_count=delta_info["EXPECTED_CHANGED_CONTENT_HASH_COUNT"],
            expected_unchanged_count=delta_info[
                "EXPECTED_UNCHANGED_CONTENT_HASH_COUNT"
            ],
            after_run1_counts=counts_after_run1,
            quarantine_before=quarantine_before,
            quarantine_after_run1=quarantine_after_run1,
            wikivoyage_before_sha256=wv_before_sha,
            wikivoyage_after_run1_sha256=wv_after_run1_sha,
        )

        target_manifest = json.loads(
            (repo_root / TARGET_60_MANIFEST_RELPATH).read_text(encoding="utf-8")
        )
        target_60_ver = evaluate_target_60_stored_docs(
            before_osm_snapshot=osm_before_snapshot,
            after_osm_snapshot=osm_after_run1_snapshot,
            target_manifest_pois=target_manifest["pois"],
        )

        # Controlled RUN 2 (Semantic Idempotency)
        run2_ingest_res = await ingester.ingest_canonical_places()
        if (
            run2_ingest_res.get("verified_places") != EXPECTED_OSM_DOCUMENTS
            or run2_ingest_res.get("documents_generated") != EXPECTED_OSM_DOCUMENTS
            or run2_ingest_res.get("stale_osm_documents_quarantined_and_removed") != 0
        ):
            raise ValueError(f"RUN2_INGEST_RESULT_MISMATCH: {run2_ingest_res}")

        async with pool.acquire() as conn:
            counts_after_run2, quarantine_after_run2 = (
                await _fetch_db_counts_and_quarantine(conn)
            )
            osm_rows_after_run2 = await _fetch_osm_rows(conn)
            wv_rows_after_run2 = await _fetch_wikivoyage_rows(conn)
            embedding_ver = await _verify_embedding_validity(conn)

        osm_after_run2_snapshot = build_osm_semantic_snapshot(osm_rows_after_run2)
        wv_after_run2_sha = compute_wikivoyage_semantic_sha256(wv_rows_after_run2)

        run2_ver = verify_run2_idempotency(
            after_run1_osm_snapshot=osm_after_run1_snapshot,
            after_run2_osm_snapshot=osm_after_run2_snapshot,
            after_run2_counts=counts_after_run2,
            quarantine_after_run1=quarantine_after_run1,
            quarantine_after_run2=quarantine_after_run2,
            wikivoyage_before_sha256=wv_before_sha,
            wikivoyage_after_run2_sha256=wv_after_run2_sha,
        )

        smoke_ver = await _run_retrieval_smoke_checks(retriever, pool)
    finally:
        await retriever.close()

    receipt_body: dict[str, Any] = {
        "task_id": TASK_ID,
        "receipt_version": RECEIPT_VERSION,
        "authoritative_develop_sha": AUTHORITATIVE_BASE_DEVELOP_SHA,
        "previous_accepted_gate": PREVIOUS_ACCEPTED_GATE,
        "w07_b1_fix_01a_status": W07_B1_FIX_01A_STATUS,
        "W07_B1_FIX_01B_EXECUTION": "PASS",
        "PDG_001_RENDERER_FIX_IMPLEMENTED": True,
        "PDG_001_CONTROLLED_REINGESTION_VERIFIED": True,
        "PDG_001_STATUS": "REINGESTION_VERIFIED_PENDING_CHATGPT_AUDIT",
        "next_gate": NEXT_GATE,
        "before_counts": {
            "TOTAL_DOCUMENTS_BEFORE": counts_before["total_documents"],
            "OSM_DOCUMENTS_BEFORE": counts_before["osm_documents"],
            "WIKIVOYAGE_DOCUMENTS_BEFORE": counts_before["wikivoyage_documents"],
            "unique_osm_document_ids": counts_before["unique_osm_document_ids"],
            "duplicate_osm_document_ids": counts_before["duplicate_osm_document_ids"],
            "unique_osm_place_ids": counts_before["unique_osm_place_ids"],
            "duplicate_osm_place_ids": counts_before["duplicate_osm_place_ids"],
            "null_place_id_osm_documents": counts_before["null_place_id_osm_documents"],
            "unverified_osm_documents": counts_before["unverified_osm_documents"],
            "quarantine_table_exists": counts_before["quarantine_table_exists"],
        },
        "quarantine_baseline": {
            "QUARANTINE_ROWS_BEFORE": quarantine_before["total_rows"],
            "QUARANTINE_OSM_SUPERSEDED_ROWS_BEFORE": quarantine_before[
                "osm_superseded_rows"
            ],
            "superseded_reason": QUARANTINE_SUPERSEDED_REASON,
        },
        "embedding_preflight": {
            "embedding_model": EXPECTED_EMBEDDING_MODEL,
            "dimension": EXPECTED_EMBEDDING_DIM,
            "offline_cache_verified": True,
            "HF_HUB_OFFLINE": "1",
            "NEW_MODEL_DOWNLOADS": 0,
        },
        "expected_generation_and_delta": {
            "EXPECTED_OSM_DOCUMENTS": delta_info["EXPECTED_OSM_DOCUMENTS"],
            "MISSING_IN_DB": delta_info["MISSING_IN_DB"],
            "UNEXPECTED_IN_DB": delta_info["UNEXPECTED_IN_DB"],
            "EXPECTED_CHANGED_CONTENT_HASH_COUNT": delta_info[
                "EXPECTED_CHANGED_CONTENT_HASH_COUNT"
            ],
            "EXPECTED_UNCHANGED_CONTENT_HASH_COUNT": delta_info[
                "EXPECTED_UNCHANGED_CONTENT_HASH_COUNT"
            ],
            "EXPECTED_CONTENT_HASH_DUPLICATES": delta_info[
                "EXPECTED_CONTENT_HASH_DUPLICATES"
            ],
            "CROSS_PAIR_HASH_COLLISION_COUNT": delta_info[
                "CROSS_PAIR_HASH_COLLISION_COUNT"
            ],
        },
        "OSM_BEFORE_SEMANTIC_SHA256": osm_before_sha,
        "WIKIVOYAGE_BEFORE_SHA256": wv_before_sha,
        "run_1": {
            "ingestion_result": run1_ingest_res,
            **run1_ver,
            "QUARANTINE_ROWS_AFTER_RUN1": quarantine_after_run1["total_rows"],
            "QUARANTINE_OSM_SUPERSEDED_ROWS_AFTER_RUN1": quarantine_after_run1[
                "osm_superseded_rows"
            ],
        },
        "target_60_verification": target_60_ver,
        "run_2": {
            "ingestion_result": run2_ingest_res,
            **run2_ver,
            "QUARANTINE_ROWS_AFTER_RUN2": quarantine_after_run2["total_rows"],
            "QUARANTINE_OSM_SUPERSEDED_ROWS_AFTER_RUN2": quarantine_after_run2[
                "osm_superseded_rows"
            ],
        },
        "duplicate_and_provenance_checks_after_run2": {
            "duplicate_osm_document_ids": counts_after_run2[
                "duplicate_osm_document_ids"
            ],
            "duplicate_osm_place_ids": counts_after_run2["duplicate_osm_place_ids"],
            "null_place_id_osm_documents": counts_after_run2[
                "null_place_id_osm_documents"
            ],
            "unverified_osm_documents": counts_after_run2["unverified_osm_documents"],
        },
        "embedding_validity": embedding_ver,
        "retrieval_smoke": smoke_ver,
        "no_external_activity": {
            "NEW_WEB_DOCUMENT_DOWNLOADS": 0,
            "NEW_SOCIAL_COLLECTION": 0,
            "NEW_GOOGLE_MAPS_COLLECTION": 0,
            "NEW_LLM_PROVIDER_CALLS": 0,
            "NEW_EXTERNAL_API_CALLS_FOR_CORPUS": 0,
            "NEW_MODEL_DOWNLOADS": 0,
            "SOCIAL_FRESHNESS_01_STATUS": "RESERVED",
        },
        "upstream_frozen_hashes": upstream_hashes,
    }

    internal_sha256 = _canonical_sha256(receipt_body)
    full_receipt = {
        **receipt_body,
        "internal_sha256": internal_sha256,
    }

    receipt_path = repo_root / RECEIPT_JSON_RELPATH
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_json_text = json.dumps(full_receipt, ensure_ascii=False, indent=2) + "\n"
    receipt_path.write_bytes(receipt_json_text.encode("utf-8"))

    report_path = repo_root / REPORT_MD_RELPATH
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_md_text = _build_markdown_report(full_receipt)
    report_path.write_bytes(report_md_text.encode("utf-8"))

    return verify_fix01b_receipt(repo_root)


def verify_fix01b_receipt(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Verify committed FIX-01B receipt JSON, Markdown report, B1A immutability, and upstream hashes."""
    receipt_path = repo_root / RECEIPT_JSON_RELPATH
    report_path = repo_root / REPORT_MD_RELPATH
    if not receipt_path.exists():
        raise FileNotFoundError(f"Missing FIX-01B receipt JSON: {receipt_path}")
    if not report_path.exists():
        raise FileNotFoundError(f"Missing FIX-01B report Markdown: {report_path}")

    raw_text = receipt_path.read_text(encoding="utf-8")
    for forbidden in ("postgresql://", "postgres://", "DATABASE_URL"):
        if forbidden in raw_text:
            raise ValueError(
                f"RECEIPT_SECURITY_VIOLATION: forbidden substring '{forbidden}' found in receipt JSON"
            )

    receipt = json.loads(raw_text)
    recorded_internal = receipt.get("internal_sha256")
    body_without_sha = {k: v for k, v in receipt.items() if k != "internal_sha256"}
    computed_internal = _canonical_sha256(body_without_sha)
    if recorded_internal != computed_internal:
        raise ValueError(
            f"RECEIPT_INTERNAL_SHA256_MISMATCH: recorded={recorded_internal} != computed={computed_internal}"
        )

    expected_md = _build_markdown_report(receipt)
    actual_md = report_path.read_text(encoding="utf-8").replace("\r\n", "\n")
    if actual_md != expected_md:
        raise ValueError("REPORT_MD_CONTENT_MISMATCH: report does not match receipt JSON")

    upstream_hashes = _verify_b1a_and_upstream_hashes(repo_root)
    if receipt.get("upstream_frozen_hashes") != upstream_hashes:
        raise ValueError("UPSTREAM_FROZEN_HASHES_MISMATCH")

    # Verify core receipt invariants
    bc = receipt["before_counts"]
    if (
        bc["TOTAL_DOCUMENTS_BEFORE"] != EXPECTED_TOTAL_DOCUMENTS
        or bc["OSM_DOCUMENTS_BEFORE"] != EXPECTED_OSM_DOCUMENTS
        or bc["WIKIVOYAGE_DOCUMENTS_BEFORE"] != EXPECTED_WIKIVOYAGE_DOCUMENTS
        or not bc["quarantine_table_exists"]
    ):
        raise ValueError("RECEIPT_BEFORE_COUNTS_INVALID")

    ed = receipt["expected_generation_and_delta"]
    if (
        ed["EXPECTED_OSM_DOCUMENTS"] != EXPECTED_OSM_DOCUMENTS
        or ed["MISSING_IN_DB"] != 0
        or ed["UNEXPECTED_IN_DB"] != 0
        or ed["EXPECTED_CONTENT_HASH_DUPLICATES"] != 0
        or ed["CROSS_PAIR_HASH_COLLISION_COUNT"] != 0
        or (
            ed["EXPECTED_CHANGED_CONTENT_HASH_COUNT"]
            + ed["EXPECTED_UNCHANGED_CONTENT_HASH_COUNT"]
        )
        != EXPECTED_OSM_DOCUMENTS
    ):
        raise ValueError("RECEIPT_EXPECTED_DELTA_INVALID")

    r1 = receipt["run_1"]
    if (
        r1["TOTAL_DOCUMENTS_AFTER_RUN1"] != EXPECTED_TOTAL_DOCUMENTS
        or r1["OSM_DOCUMENTS_AFTER_RUN1"] != EXPECTED_OSM_DOCUMENTS
        or r1["WIKIVOYAGE_DOCUMENTS_AFTER_RUN1"] != EXPECTED_WIKIVOYAGE_DOCUMENTS
        or r1["OSM_EXPECTED_STATE_MISMATCH_COUNT"] != 0
        or r1["ACTUAL_CHANGED_CONTENT_HASH_COUNT"]
        != ed["EXPECTED_CHANGED_CONTENT_HASH_COUNT"]
        or r1["ACTUAL_UNCHANGED_CONTENT_HASH_COUNT"]
        != ed["EXPECTED_UNCHANGED_CONTENT_HASH_COUNT"]
        or r1["NEW_OSM_QUARANTINE_ROWS_RUN1"]
        != r1["ACTUAL_CHANGED_CONTENT_HASH_COUNT"]
        or r1["WIKIVOYAGE_AFTER_RUN1_SHA256"] != receipt["WIKIVOYAGE_BEFORE_SHA256"]
    ):
        raise ValueError("RECEIPT_RUN1_INVARIANTS_INVALID")

    t60 = receipt["target_60_verification"]
    if (
        t60["TARGET_POI_DOCUMENTS"] != EXPECTED_TARGET_POIS
        or t60["TARGET_USEFUL_STRUCTURED_DOCUMENTS"]
        != EXPECTED_TARGET_USEFUL_STRUCTURED
        or t60["TARGET_LOW_INFORMATION_DOCUMENTS"] != EXPECTED_TARGET_LOW_INFORMATION
        or len(t60["sample_before_after_evidence"]) != len(SAMPLE_TARGET_POI_IDS)
    ):
        raise ValueError("RECEIPT_TARGET_60_INVARIANTS_INVALID")

    r2 = receipt["run_2"]
    if (
        r2["TOTAL_DOCUMENTS_AFTER_RUN2"] != EXPECTED_TOTAL_DOCUMENTS
        or r2["OSM_DOCUMENTS_AFTER_RUN2"] != EXPECTED_OSM_DOCUMENTS
        or r2["WIKIVOYAGE_DOCUMENTS_AFTER_RUN2"] != EXPECTED_WIKIVOYAGE_DOCUMENTS
        or r2["OSM_AFTER_RUN1_SEMANTIC_SHA256"] != r2["OSM_AFTER_RUN2_SEMANTIC_SHA256"]
        or r2["RUN2_SEMANTIC_CHANGE_COUNT"] != 0
        or r2["NEW_OSM_QUARANTINE_ROWS_RUN2"] != 0
        or r2["WIKIVOYAGE_AFTER_RUN2_SHA256"] != receipt["WIKIVOYAGE_BEFORE_SHA256"]
    ):
        raise ValueError("RECEIPT_RUN2_INVARIANTS_INVALID")

    no_ext = receipt["no_external_activity"]
    for counter_key in (
        "NEW_WEB_DOCUMENT_DOWNLOADS",
        "NEW_SOCIAL_COLLECTION",
        "NEW_GOOGLE_MAPS_COLLECTION",
        "NEW_LLM_PROVIDER_CALLS",
        "NEW_EXTERNAL_API_CALLS_FOR_CORPUS",
        "NEW_MODEL_DOWNLOADS",
    ):
        if no_ext.get(counter_key) != 0:
            raise ValueError(f"NON_ZERO_EXTERNAL_ACTIVITY_COUNTER: {counter_key}")

    if (
        receipt.get("W07_B1_FIX_01B_EXECUTION") != "PASS"
        or receipt.get("PDG_001_RENDERER_FIX_IMPLEMENTED") is not True
        or receipt.get("PDG_001_CONTROLLED_REINGESTION_VERIFIED") is not True
        or receipt.get("PDG_001_STATUS")
        != "REINGESTION_VERIFIED_PENDING_CHATGPT_AUDIT"
    ):
        raise ValueError("RECEIPT_PDG_STATUS_INVALID")

    receipt_lf_sha256 = w07_a2.compute_file_sha256(receipt_path)
    report_lf_sha256 = w07_a2.compute_file_sha256(report_path)

    return {
        "status": "PASS",
        "receipt_json_path": RECEIPT_JSON_RELPATH,
        "receipt_internal_sha256": recorded_internal,
        "receipt_file_lf_sha256": receipt_lf_sha256,
        "report_md_path": REPORT_MD_RELPATH,
        "report_md_lf_sha256": report_lf_sha256,
        "W07_B1_FIX_01B_EXECUTION": receipt["W07_B1_FIX_01B_EXECUTION"],
        "PDG_001_RENDERER_FIX_IMPLEMENTED": receipt["PDG_001_RENDERER_FIX_IMPLEMENTED"],
        "PDG_001_CONTROLLED_REINGESTION_VERIFIED": receipt[
            "PDG_001_CONTROLLED_REINGESTION_VERIFIED"
        ],
        "PDG_001_STATUS": receipt["PDG_001_STATUS"],
        "before_counts": receipt["before_counts"],
        "quarantine_baseline": receipt["quarantine_baseline"],
        "expected_generation_and_delta": receipt["expected_generation_and_delta"],
        "OSM_BEFORE_SEMANTIC_SHA256": receipt["OSM_BEFORE_SEMANTIC_SHA256"],
        "WIKIVOYAGE_BEFORE_SHA256": receipt["WIKIVOYAGE_BEFORE_SHA256"],
        "run_1": receipt["run_1"],
        "target_60_verification": receipt["target_60_verification"],
        "run_2": receipt["run_2"],
        "embedding_validity": receipt["embedding_validity"],
        "retrieval_smoke": receipt["retrieval_smoke"],
        "no_external_activity": receipt["no_external_activity"],
        "upstream_frozen_hashes": receipt["upstream_frozen_hashes"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="W07-B1-FIX-01B Controlled OSM Re-ingestion Executor & Verifier"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--preflight",
        action="store_true",
        help="Run read-only preflight checks without mutating DB",
    )
    group.add_argument(
        "--execute",
        action="store_true",
        help="Execute controlled RUN 1 + RUN 2 re-ingestion and write receipt/report",
    )
    group.add_argument(
        "--verify-receipt",
        "--verify-only",
        dest="verify_receipt",
        action="store_true",
        help="Verify committed receipt JSON, report Markdown, and upstream hashes",
    )
    args = parser.parse_args(argv)

    if args.preflight:
        res = asyncio.run(run_preflight())
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0
    if args.execute:
        res = asyncio.run(execute_controlled_reingestion(REPO_ROOT))
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0
    if args.verify_receipt:
        res = verify_fix01b_receipt(REPO_ROOT)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
