"""Tests for W07-B1A Existing POI Knowledge Corpus Audit (v1)."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import audit_w07_b1a_existing_poi_knowledge as w07_b1a  # noqa: E402


def test_w07_b1a_artifacts_verify_cleanly() -> None:
    """Committed W07-B1A JSON and Markdown artifacts must match deterministic builder output."""
    res = w07_b1a.verify_b1a_audit_artifacts(REPO_ROOT)
    assert res["status"] == "PASS"
    assert (
        res["audit_json_path"]
        == "data/evaluation/w07/w07_b1a_existing_poi_knowledge_audit_v1.json"
    )
    assert (
        res["audit_md_path"] == "docs/research/w07_b1a_existing_poi_knowledge_audit.md"
    )
    assert res["CURRENT_LOCAL_CORPUS_READY_FOR_B2"] is False


def test_w07_b1a_inventory_and_lineage_counting_rules() -> None:
    """Section 2 & 3: Verify existing inventory counts and strict separation of units vs lineages."""
    payload = w07_b1a.build_b1a_audit_payload(REPO_ROOT)
    inv = payload["verified_existing_inventory"]

    assert inv["NON_REVIEW_RAG_EVIDENCE_UNITS_EXISTING"] == 1223
    assert inv["OSM_METADATA_UNITS"] == 759
    assert inv["WIKIVOYAGE_DESTINATION_CHUNKS"] == 464
    assert inv["VERIFIED_OSM_POIS"] == 759
    assert inv["REC_A_CORE_3_CITY_POIS"] == 622
    assert inv["OVERTURE_LINKED_POIS"] == 247
    assert inv["TOTAL_REPOSITORY_NON_REVIEW_UNITS_INCLUDING_OVERTURE"] == 1470
    assert inv["TARGET_POIS"] == 60
    assert inv["target_pois_by_city"] == {"Hà Nội": 20, "Đà Nẵng": 20, "Hạ Long": 20}

    # Evidence units must not be equated with independent lineages
    assert inv["rag_documents_independent_source_lineages"] == 769
    assert inv["osm_independent_source_lineages_total"] == 759
    assert inv["wikivoyage_independent_source_lineages_total"] == 10
    assert inv["overture_independent_source_lineages_total"] == 247
    assert inv["repository_independent_source_lineages_including_overture"] == 1016


def test_w07_b1a_60_poi_mapping_and_governance_invariants() -> None:
    """Sections 4..14: Verify 60-POI mapping, B0 two-gate rule, content utility, and Overture/Wikivoyage handling."""
    payload = w07_b1a.build_b1a_audit_payload(REPO_ROOT)
    records = payload["target_poi_audit_records"]
    assert len(records) == 60

    for rec in records:
        osm = rec["osm_evidence"]
        assert osm["source_lineage_id"].startswith("osm:")
        assert osm["source_tier"] == "TIER_C"
        assert osm["evidence_type"] == "STRUCTURED_METADATA"
        assert osm["license_or_usage_class"] == "ODbL-1.0"
        assert osm["reuse_storage_class"] == "OPEN_REUSABLE"
        assert osm["CANONICAL_MAPPING_OK"] is True
        assert osm["REUSE_STATUS_ALLOWED"] is True
        assert osm["PRIMARY_CORPUS_ELIGIBLE"] is True
        assert (
            osm["RAG_CANDIDATE_ELIGIBLE"]
            == (osm["PRIMARY_CORPUS_ELIGIBLE"] and osm["CONTENT_UTILITY_OK"])
        )

        ov = rec["overture_evidence"]
        if ov["mapping_status"] == "AUTO_LINK_VERIFIED":
            assert ov["source_lineage_id"].startswith("overture:")
            assert ov["overture_theme"] == "places"
            assert ov["overture_contributing_source"] == "meta,Overture"
            assert ov["license_or_usage_class"] == "CDLA-Permissive-2.0"
            assert ov["reuse_storage_class"] == "OPEN_REUSABLE"
            assert ov["CANONICAL_MAPPING_OK"] is True
            assert ov["PRIMARY_CORPUS_ELIGIBLE"] is True
            assert ov["CONTENT_UTILITY_STATUS"] == "LOW_INFORMATION"
            assert ov["RAG_CANDIDATE_ELIGIBLE"] is False
        elif ov["mapping_status"] == "MAPPING_REVIEW_REQUIRED":
            assert ov["CANONICAL_MAPPING_OK"] is False
            assert ov["PRIMARY_CORPUS_ELIGIBLE"] is False
            assert ov["RAG_CANDIDATE_ELIGIBLE"] is False

    # Wikivoyage audit invariants (Section 12)
    wv = payload["wikivoyage_audit"]
    assert wv["total_chunks_in_freeze_v2"] == 464
    assert wv["independent_article_lineages"] == 10
    assert wv["chunks_mapped_to_frozen_60_pois"] == 0
    assert wv["chunks_city_context_only"] == 157
    assert wv["chunks_unmapped_to_frozen_poi"] == 307
    assert wv["chunks_city_context_only"] + wv["chunks_unmapped_to_frozen_poi"] == 464


def test_w07_b1a_coverage_priorities_and_b2_readiness() -> None:
    """Sections 15..22: Verify coverage metrics, duplicate audit, B2 readiness, and P0/P1/P2/P3 priorities."""
    payload = w07_b1a.build_b1a_audit_payload(REPO_ROOT)
    cov = payload["coverage_metrics"]["overall"]
    by_city = payload["coverage_metrics"]["by_city"]

    assert cov["TARGET_POIS"] == 60
    assert cov["POIS_WITH_ANY_EXISTING_EVIDENCE"] == 60
    assert cov["POIS_WITH_PRIMARY_CORPUS_ELIGIBLE_EVIDENCE"] == 60
    assert cov["POIS_WITH_RAG_CANDIDATE_EVIDENCE"] == 40
    assert cov["POIS_WITH_1_INDEPENDENT_LINEAGE"] == 34
    assert cov["POIS_WITH_2_PLUS_INDEPENDENT_LINEAGES"] == 26
    assert cov["POIS_WITH_NARRATIVE_TEXT"] == 0
    assert cov["POIS_WITH_STRUCTURED_METADATA"] == 60
    assert cov["POIS_WITH_USEFUL_STRUCTURED_METADATA"] == 40
    assert cov["POIS_WITH_BOTH_STRUCTURED_AND_NARRATIVE"] == 0

    assert by_city["Hà Nội"]["POIS_WITH_RAG_CANDIDATE_EVIDENCE"] == 18
    assert by_city["Đà Nẵng"]["POIS_WITH_RAG_CANDIDATE_EVIDENCE"] == 15
    assert by_city["Hạ Long"]["POIS_WITH_RAG_CANDIDATE_EVIDENCE"] == 7

    assert by_city["Hà Nội"]["POIS_WITH_2_PLUS_INDEPENDENT_LINEAGES"] == 7
    assert by_city["Đà Nẵng"]["POIS_WITH_2_PLUS_INDEPENDENT_LINEAGES"] == 10
    assert by_city["Hạ Long"]["POIS_WITH_2_PLUS_INDEPENDENT_LINEAGES"] == 9

    prio = payload["b1b_priority_summary"]
    assert prio["P0"] == 20
    assert prio["P1"] == 19
    assert prio["P2"] == 21
    assert prio["P3"] == 0
    assert prio["P0"] + prio["P1"] + prio["P2"] + prio["P3"] == 60

    dup = payload["duplicate_and_lineage_audit"]
    assert dup["osm_759_unique_source_ids"] == 759
    assert dup["osm_759_unique_content_sha256_unwrapped"] == 759
    assert dup["osm_exact_duplicate_content_hashes"] == 0
    assert dup["overture_247_unique_gers_ids"] == 247
    assert dup["overture_duplicate_gers_ids"] == 0
    assert dup["upstream_data_deleted"] is False

    assert payload["CURRENT_LOCAL_CORPUS_READY_FOR_B2"] is False


def test_w07_b1a_zero_external_calls_and_tamper_detection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sections 23..28: Verify zero external collection, role preservation, upstream immutability, and tamper detection."""
    payload = w07_b1a.build_b1a_audit_payload(REPO_ROOT)
    no_ext = payload["no_external_collection_at_b1a"]
    assert no_ext == {
        "NEW_WEB_DOCUMENT_DOWNLOADS": 0,
        "NEW_SOCIAL_COLLECTION": 0,
        "NEW_GOOGLE_MAPS_COLLECTION": 0,
        "NEW_LLM_PROVIDER_CALLS": 0,
        "NEW_EXTERNAL_API_CALLS_FOR_CORPUS": 0,
    }
    assert (
        payload["SOCIAL_PLATFORM_ROLE"]
        == "DYNAMIC_FRESHNESS_LAYER_NOT_PRIMARY_CORPUS"
    )
    assert payload["SOCIAL_FUTURE_RESERVED_TASK_ID"] == "SOCIAL-FRESHNESS-01"
    assert payload["GOOGLE_MAPS_ROLE"] == "RUNTIME_ENRICHMENT_ONLY"
    assert payload["method_drift_guard"]["method_choices_selected_in_b1a"] is False

    hashes = w07_b1a.verify_all_upstream_immutability(REPO_ROOT)
    assert (
        hashes["w07_b0_amendment_internal_sha256"]
        == "365b00607737f01f02753595f5ce65092e2622bfbe3a8bb4ed20e464daf7a12f"
    )
    assert (
        hashes["w07_b0_amendment_lf_sha256"]
        == "896fb5f90bce36610f9e82e23f52e56e0f93d90ecb81f564b6a1360b8e4b3c94"
    )
    assert (
        hashes["w07_b0_md_lf_sha256"]
        == "0f1ef9fcb9500882ce3dbbbea148d2d592fbe7211eb1e91f86855d6ed08af585"
    )

    # Copy B1A artifacts to tmp_path and test tamper detection
    for rel in (w07_b1a.AUDIT_JSON_RELPATH, w07_b1a.AUDIT_MD_RELPATH):
        src = REPO_ROOT / rel
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    monkeypatch.setattr(
        w07_b1a,
        "verify_all_upstream_immutability",
        lambda _root=REPO_ROOT: hashes,
    )
    monkeypatch.setattr(
        w07_b1a,
        "build_b1a_audit_payload",
        lambda _root=REPO_ROOT: payload,
    )

    assert w07_b1a.verify_b1a_audit_artifacts(tmp_path)["status"] == "PASS"

    tampered_path = tmp_path / w07_b1a.AUDIT_JSON_RELPATH
    tampered = json.loads(tampered_path.read_text(encoding="utf-8"))
    tampered["CURRENT_LOCAL_CORPUS_READY_FOR_B2"] = True
    tampered_path.write_text(json.dumps(tampered, indent=2), encoding="utf-8")

    with pytest.raises(ValueError, match="internal SHA mismatch"):
        w07_b1a.verify_b1a_audit_artifacts(tmp_path)

