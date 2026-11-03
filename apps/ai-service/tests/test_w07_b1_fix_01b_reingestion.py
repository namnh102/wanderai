"""W07-B1-FIX-01B tests: Controlled OSM re-ingestion preflight, collision guard, semantic idempotency, and receipt verification."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys
import uuid

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "apps" / "ai-service") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "apps" / "ai-service"))

from app.rag.chunker import RAGChunk  # noqa: E402
from scripts import (  # noqa: E402
    audit_w07_b1a_existing_poi_knowledge as w07_b1a,
    reingest_w07_osm_documents_fix01b as fix01b,
)


def _valid_preflight_counts() -> dict[str, int | bool]:
    return {
        "quarantine_table_exists": True,
        "total_documents": 1223,
        "osm_documents": 759,
        "wikivoyage_documents": 464,
        "unique_osm_document_ids": 759,
        "duplicate_osm_document_ids": 0,
        "unique_osm_place_ids": 759,
        "duplicate_osm_place_ids": 0,
        "null_place_id_osm_documents": 0,
        "unverified_osm_documents": 0,
    }


def _make_chunk(idx: int, content_suffix: str = "") -> RAGChunk:
    pid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"place-{idx}"))
    doc_id = f"osm-place-{pid}"
    content = f"Place {idx} content {content_suffix}".strip()
    return RAGChunk(
        chunk_id=doc_id,
        document_id=doc_id,
        title=f"Place {idx}",
        section_heading="OSM Metadata",
        topic="place",
        content=content,
        content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        source_name="osm",
        source_url=f"https://www.openstreetmap.org/node/{idx}",
        license="ODbL 1.0",
        attribution="© OpenStreetMap contributors",
        language="vi",
        destination_id=None,
        place_id=pid,
        category="culture",
        metadata={"source_id": f"node/{idx}", "osm_tags_used": ["opening_hours"]},
        retrieved_at="2026-10-03T18:49:34+00:00",
    )


def _chunk_to_db_row(ch: RAGChunk, **overrides) -> dict:
    row = {
        "id": str(uuid.uuid4()),
        "document_id": ch.document_id,
        "place_id": ch.place_id,
        "source_name": ch.source_name,
        "source_url": ch.source_url,
        "license": ch.license,
        "attribution": ch.attribution,
        "language": ch.language,
        "topic": ch.topic,
        "title": ch.title,
        "category": ch.category,
        "content": ch.content,
        "content_hash": ch.content_hash,
        "embedding_model": fix01b.EXPECTED_EMBEDDING_MODEL,
        "metadata": copy.deepcopy(ch.metadata),
        "retrieved_at": ch.retrieved_at,
        "created_at": "2026-10-03T18:49:34+00:00",
        "updated_at": "2026-10-03T18:49:34+00:00",
    }
    row.update(overrides)
    return row


def test_01_preflight_refuses_wrong_total_counts():
    counts = _valid_preflight_counts()
    fix01b.validate_preflight_state(counts)

    for field, bad_val in (
        ("total_documents", 1222),
        ("osm_documents", 758),
        ("wikivoyage_documents", 463),
        ("null_place_id_osm_documents", 1),
        ("unverified_osm_documents", 2),
    ):
        bad = dict(counts)
        bad[field] = bad_val
        with pytest.raises(ValueError, match="PRE_REINGESTION_STATE_MISMATCH"):
            fix01b.validate_preflight_state(bad)


def test_02_preflight_refuses_missing_quarantine_table():
    counts = _valid_preflight_counts()
    counts["quarantine_table_exists"] = False
    with pytest.raises(ValueError, match="QUARANTINE_TABLE_REQUIRED"):
        fix01b.validate_preflight_state(counts)


def test_03_preflight_detects_duplicate_osm_document_ids():
    counts = _valid_preflight_counts()
    counts["unique_osm_document_ids"] = 758
    counts["duplicate_osm_document_ids"] = 1
    with pytest.raises(ValueError, match="PRE_REINGESTION_STATE_MISMATCH"):
        fix01b.validate_preflight_state(counts)

    # Also test duplicate detection inside compute_expected_delta_and_collision_guard
    chunks = [_make_chunk(i) for i in range(759)]
    rows = [_chunk_to_db_row(ch) for ch in chunks]
    rows[1]["document_id"] = rows[0]["document_id"]
    with pytest.raises(ValueError, match="PRE_REINGESTION_STATE_MISMATCH"):
        fix01b.compute_expected_delta_and_collision_guard(rows, chunks)


def test_04_expected_generation_count_is_759():
    places_v2 = json.loads(
        (REPO_ROOT / "data/curated/gomate_places_freeze_v2.json").read_text(
            encoding="utf-8"
        )
    )
    canonical_places = [
        {
            "id": p["place_id"],
            "name": p["name"],
            "category": p.get("category"),
            "destination_id": None,
            "destination_name": p.get("destination"),
            "latitude": p.get("latitude"),
            "longitude": p.get("longitude"),
            "sources": p["sources"],
        }
        for p in places_v2
    ]
    expected_chunks = fix01b.generate_expected_osm_chunks(canonical_places)
    assert len(expected_chunks) == 759
    assert len({c.document_id for c in expected_chunks}) == 759
    assert len({c.place_id for c in expected_chunks}) == 759

    with pytest.raises(ValueError, match="EXPECTED_OSM_DOCUMENTS_MISMATCH"):
        fix01b.generate_expected_osm_chunks(canonical_places[:758])


def test_05_pairwise_collision_guard_works():
    chunks = [_make_chunk(i, "new") for i in range(759)]
    old_rows = [
        _chunk_to_db_row(_make_chunk(i, "old" if i < 10 else "new"))
        for i in range(759)
    ]

    res = fix01b.compute_expected_delta_and_collision_guard(old_rows, chunks)
    assert res["EXPECTED_CHANGED_CONTENT_HASH_COUNT"] == 10
    assert res["EXPECTED_UNCHANGED_CONTENT_HASH_COUNT"] == 749
    assert res["CROSS_PAIR_HASH_COLLISION_COUNT"] == 0
    assert res["EXPECTED_CONTENT_HASH_DUPLICATES"] == 0

    # Inject a cross-pair collision: old row 0 has the same content_hash as expected chunk 50
    colliding_rows = copy.deepcopy(old_rows)
    colliding_rows[0]["content_hash"] = chunks[50].content_hash
    with pytest.raises(ValueError, match="CROSS_PAIR_HASH_COLLISION_DETECTED"):
        fix01b.compute_expected_delta_and_collision_guard(colliding_rows, chunks)

    # Inject duplicate expected content_hash
    dup_chunks = copy.deepcopy(chunks)
    dup_chunks[1].content_hash = dup_chunks[0].content_hash
    with pytest.raises(ValueError, match="EXPECTED_CONTENT_HASH_DUPLICATES_DETECTED"):
        fix01b.compute_expected_delta_and_collision_guard(old_rows, dup_chunks)


def test_06_semantic_snapshot_excludes_operational_timestamps():
    ch = _make_chunk(1, "v1")
    row_a = _chunk_to_db_row(
        ch,
        id=str(uuid.uuid4()),
        created_at="2026-10-01T00:00:00+00:00",
        updated_at="2026-10-01T00:00:00+00:00",
    )
    row_b = _chunk_to_db_row(
        ch,
        id=str(uuid.uuid4()),
        created_at="2026-11-03T12:00:00+00:00",
        updated_at="2026-11-03T19:30:00+00:00",
    )
    snap_a = fix01b.build_osm_semantic_snapshot([row_a])
    snap_b = fix01b.build_osm_semantic_snapshot([row_b])
    assert snap_a == snap_b
    for forbidden_key in ("id", "created_at", "updated_at"):
        assert forbidden_key not in snap_a[0]
    assert fix01b.compute_osm_semantic_sha256([row_a]) == fix01b.compute_osm_semantic_sha256([row_b])


def test_07_and_08_run1_expected_actual_comparison_and_wikivoyage_invariance():
    expected_chunks = [_make_chunk(i, "repaired") for i in range(759)]
    before_rows = [
        _chunk_to_db_row(_make_chunk(i, "legacy" if i < 616 else "repaired"))
        for i in range(759)
    ]
    after_rows = [_chunk_to_db_row(ch) for ch in expected_chunks]

    before_snap = fix01b.build_osm_semantic_snapshot(before_rows)
    after_snap = fix01b.build_osm_semantic_snapshot(after_rows)

    ver = fix01b.verify_run1_post_state(
        before_osm_snapshot=before_snap,
        after_run1_osm_snapshot=after_snap,
        expected_chunks=expected_chunks,
        expected_changed_count=616,
        expected_unchanged_count=143,
        after_run1_counts=_valid_preflight_counts(),
        quarantine_before={"total_rows": 274, "osm_superseded_rows": 207},
        quarantine_after_run1={"total_rows": 274 + 616, "osm_superseded_rows": 207 + 616},
        wikivoyage_before_sha256="abc123",
        wikivoyage_after_run1_sha256="abc123",
    )
    assert ver["OSM_EXPECTED_STATE_MISMATCH_COUNT"] == 0
    assert ver["ACTUAL_CHANGED_CONTENT_HASH_COUNT"] == 616
    assert ver["NEW_OSM_QUARANTINE_ROWS_RUN1"] == 616

    # Wikivoyage invariance violation
    with pytest.raises(ValueError, match="WIKIVOYAGE_INVARIANCE_VIOLATION"):
        fix01b.verify_run1_post_state(
            before_osm_snapshot=before_snap,
            after_run1_osm_snapshot=after_snap,
            expected_chunks=expected_chunks,
            expected_changed_count=616,
            expected_unchanged_count=143,
            after_run1_counts=_valid_preflight_counts(),
            quarantine_before={"total_rows": 274, "osm_superseded_rows": 207},
            quarantine_after_run1={"total_rows": 274 + 616, "osm_superseded_rows": 207 + 616},
            wikivoyage_before_sha256="abc123",
            wikivoyage_after_run1_sha256="tampered",
        )

    # Content mismatch violation
    tampered_after = copy.deepcopy(after_snap)
    tampered_after[0]["content"] = "tampered content"
    with pytest.raises(ValueError, match="OSM_EXPECTED_STATE_MISMATCH"):
        fix01b.verify_run1_post_state(
            before_osm_snapshot=before_snap,
            after_run1_osm_snapshot=tampered_after,
            expected_chunks=expected_chunks,
            expected_changed_count=616,
            expected_unchanged_count=143,
            after_run1_counts=_valid_preflight_counts(),
            quarantine_before={"total_rows": 274, "osm_superseded_rows": 207},
            quarantine_after_run1={"total_rows": 274 + 616, "osm_superseded_rows": 207 + 616},
            wikivoyage_before_sha256="abc123",
            wikivoyage_after_run1_sha256="abc123",
        )


def test_09_and_10_run2_semantic_idempotency_and_quarantine_guard():
    expected_chunks = [_make_chunk(i, "repaired") for i in range(759)]
    run1_rows = [
        _chunk_to_db_row(ch, updated_at="2026-11-03T19:00:00+00:00")
        for ch in expected_chunks
    ]
    run2_rows = [
        _chunk_to_db_row(ch, updated_at="2026-11-03T19:05:00+00:00")
        for ch in expected_chunks
    ]

    run1_snap = fix01b.build_osm_semantic_snapshot(run1_rows)
    run2_snap = fix01b.build_osm_semantic_snapshot(run2_rows)

    ver2 = fix01b.verify_run2_idempotency(
        after_run1_osm_snapshot=run1_snap,
        after_run2_osm_snapshot=run2_snap,
        after_run2_counts=_valid_preflight_counts(),
        quarantine_after_run1={"total_rows": 890, "osm_superseded_rows": 823},
        quarantine_after_run2={"total_rows": 890, "osm_superseded_rows": 823},
        wikivoyage_before_sha256="wv_hash",
        wikivoyage_after_run2_sha256="wv_hash",
    )
    assert ver2["OSM_AFTER_RUN1_SEMANTIC_SHA256"] == ver2["OSM_AFTER_RUN2_SEMANTIC_SHA256"]
    assert ver2["RUN2_SEMANTIC_CHANGE_COUNT"] == 0
    assert ver2["NEW_OSM_QUARANTINE_ROWS_RUN2"] == 0

    # New RUN-2 quarantine rows cause failure
    with pytest.raises(ValueError, match="RUN2_QUARANTINE_VIOLATION"):
        fix01b.verify_run2_idempotency(
            after_run1_osm_snapshot=run1_snap,
            after_run2_osm_snapshot=run2_snap,
            after_run2_counts=_valid_preflight_counts(),
            quarantine_after_run1={"total_rows": 890, "osm_superseded_rows": 823},
            quarantine_after_run2={"total_rows": 891, "osm_superseded_rows": 824},
            wikivoyage_before_sha256="wv_hash",
            wikivoyage_after_run2_sha256="wv_hash",
        )

    # Semantic drift in RUN 2 causes failure
    drifted_run2 = copy.deepcopy(run2_snap)
    drifted_run2[0]["content_hash"] = "0" * 64
    with pytest.raises(ValueError, match="RUN2_SEMANTIC_IDEMPOTENCY_VIOLATION"):
        fix01b.verify_run2_idempotency(
            after_run1_osm_snapshot=run1_snap,
            after_run2_osm_snapshot=drifted_run2,
            after_run2_counts=_valid_preflight_counts(),
            quarantine_after_run1={"total_rows": 890, "osm_superseded_rows": 823},
            quarantine_after_run2={"total_rows": 890, "osm_superseded_rows": 823},
            wikivoyage_before_sha256="wv_hash",
            wikivoyage_after_run2_sha256="wv_hash",
        )


def test_11_and_12_frozen_b1a_immutability_and_fix01b_receipt_verification():
    b1a_res = w07_b1a.verify_b1a_audit_artifacts(REPO_ROOT)
    assert b1a_res["status"] == "PASS"
    assert (
        b1a_res["audit_internal_sha256"]
        == "27d6dae8fd3ec284ea92806080a044b6745fb30abdddc265297e0f9da1d1c5b2"
    )
    assert (
        b1a_res["audit_file_lf_sha256"]
        == "433c722dd2f03946ab0a15830b53ef628d76937fa2e8e63a9939e73bb469e563"
    )
    assert (
        b1a_res["audit_md_lf_sha256"]
        == "130aca652c9b808a8b7e5fac50d070dd0c3f36a8e94f7693cfac8793643d0ac5"
    )

    res = fix01b.verify_fix01b_receipt(REPO_ROOT)
    assert res["status"] == "PASS"
    assert res["W07_B1_FIX_01B_EXECUTION"] == "PASS"
    assert res["PDG_001_RENDERER_FIX_IMPLEMENTED"] is True
    assert res["PDG_001_CONTROLLED_REINGESTION_VERIFIED"] is True
    assert res["PDG_001_STATUS"] == "REINGESTION_VERIFIED_PENDING_CHATGPT_AUDIT"
    assert res["no_external_activity"] == {
        "NEW_WEB_DOCUMENT_DOWNLOADS": 0,
        "NEW_SOCIAL_COLLECTION": 0,
        "NEW_GOOGLE_MAPS_COLLECTION": 0,
        "NEW_LLM_PROVIDER_CALLS": 0,
        "NEW_EXTERNAL_API_CALLS_FOR_CORPUS": 0,
        "NEW_MODEL_DOWNLOADS": 0,
        "SOCIAL_FRESHNESS_01_STATUS": "RESERVED",
    }
