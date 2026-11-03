"""W07-B1B tests: Targeted POI knowledge acquisition, two-gate governance, lineage separation, and B2 readiness."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "apps" / "ai-service") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "apps" / "ai-service"))

from scripts import (  # noqa: E402
    acquire_w07_b1b_poi_knowledge as b1b_acquire,
    validate_w07_review_corpus_v1 as w07_a2,
    verify_w07_b1b_poi_knowledge as b1b_verify,
)


def test_01_b1b_verification_passes():
    result = b1b_verify.verify_b1b_artifacts()
    assert result["status"] == "PASS"
    assert result["candidates_evaluated"] == 132
    assert result["accepted_primary_documents"] == 101
    assert result["accepted_independent_lineages"] == 82
    assert result["pois_with_rag_evidence"] == 52
    assert result["W07_B1B_CORPUS_ACQUISITION_READY_FOR_B2"] is True


def test_02_source_decisions_schema_and_two_gate_rules():
    decisions = json.loads(b1b_acquire.DECISIONS_JSON_PATH.read_text(encoding="utf-8"))
    assert decisions["HIGH_AUTHORITY_DOES_NOT_IMPLY_REUSE_PERMISSION"] is True
    assert decisions["OVERTURE_LICENSE_IS_THEME_AND_SOURCE_SPECIFIC"] is True

    records = decisions["candidate_decisions"]
    assert len(records) == 132

    jsonl_lines = [
        json.loads(line)
        for line in b1b_acquire.ACQUIRED_JSONL_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    jsonl_lineages = {doc["source_lineage_id"] for doc in jsonl_lines}
    jsonl_urls = {doc["source_url"] for doc in jsonl_lines}

    for rec in records:
        for field in b1b_verify.REQUIRED_CANDIDATE_FIELDS:
            assert field in rec and rec[field] is not None and rec[field] != ""
        dec = rec["final_b1b_decision"]
        if dec == "ACCEPT_PRIMARY_CORPUS":
            assert rec["canonical_mapping_status"] == "EXACT_MAPPED"
            assert rec["reuse_storage_class"] == "OPEN_REUSABLE"
            assert rec["redistributable_in_git"] is True
            assert rec["raw_text_permitted"] is True
            assert rec["content_utility_status"] in ("USEFUL_NARRATIVE", "USEFUL_STRUCTURED_FACTS")
            assert rec["source_lineage_id"] in jsonl_lineages
        elif dec == "REFERENCE_ONLY":
            assert rec["source_tier"] in ("TIER_A", "TIER_B")
            assert rec["reuse_storage_class"] == "REFERENCE_ONLY"
            assert rec["redistributable_in_git"] is False
            assert rec["raw_text_permitted"] is False
            assert rec["source_lineage_id"] not in jsonl_lineages
            assert rec["source_url"] not in jsonl_urls
        elif dec == "REJECT":
            assert rec["redistributable_in_git"] is False
            assert rec["raw_text_permitted"] is False
            assert rec["canonical_mapping_status"] != "EXACT_MAPPED" or rec["content_utility_status"] in (
                "LOW_INFORMATION",
                "EMPTY_OR_INVALID",
            )


def test_03_acquired_jsonl_20_field_schema_and_hashes():
    raw_lines = [
        line for line in b1b_acquire.ACQUIRED_JSONL_PATH.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    assert len(raw_lines) == 101

    seen_doc_ids: set[str] = set()
    for line in raw_lines:
        doc = json.loads(line)
        for field in b1b_verify.REQUIRED_DOCUMENT_FIELDS:
            assert field in doc and doc[field] is not None and doc[field] != ""
        assert doc["document_id"] not in seen_doc_ids
        seen_doc_ids.add(doc["document_id"])

        assert doc["reuse_storage_class"] == "OPEN_REUSABLE"
        assert doc["redistributable_in_git"] is True
        assert doc["provenance_status"] == "VERIFIED_PRIMARY_PROVENANCE"
        assert doc["content_utility_status"] in ("USEFUL_NARRATIVE", "USEFUL_STRUCTURED_FACTS")
        expected_sha = hashlib.sha256(doc["raw_text"].encode("utf-8")).hexdigest()
        assert doc["content_sha256"] == expected_sha


def test_04_lineage_vs_evidence_unit_separation():
    summary = json.loads(b1b_acquire.SUMMARY_JSON_PATH.read_text(encoding="utf-8"))
    linked = summary["linked_artifacts"]
    breakdown = summary["acquired_corpus_breakdown"]

    assert linked["acquired_corpus_document_count"] == 101
    assert linked["accepted_independent_source_lineage_count"] == 82

    by_type = breakdown["by_source_type"]
    assert by_type["overture_places_parquet"] == 26
    assert by_type["wikipedia_article"] == 26
    assert by_type["wikidata_entity"] == 29
    assert by_type["wikivoyage_poi_listing"] == 20

    lineages = breakdown["accepted_independent_source_lineages"]
    assert len(lineages) == 82
    assert sum(1 for lid in lineages if lid.startswith("overture:")) == 26
    assert sum(1 for lid in lineages if lid.startswith("wikipedia:")) == 25
    assert sum(1 for lid in lineages if lid.startswith("wikidata:")) == 29
    assert sum(1 for lid in lineages if lid.startswith("wikivoyage:")) == 2


def test_05_coverage_improvement_and_priority_shift():
    summary = json.loads(b1b_acquire.SUMMARY_JSON_PATH.read_text(encoding="utf-8"))
    overall = summary["coverage_after_acquisition"]["overall_60_pois"]
    by_city = summary["coverage_after_acquisition"]["by_city"]
    shift = summary["priority_shift_summary"]

    assert overall["total_pois"] == 60
    assert overall["pois_with_any_primary_eligible_evidence"] == 60
    assert overall["pois_with_rag_candidate_evidence"] == 52
    assert overall["pois_with_2_plus_eligible_lineages"] == 45
    assert overall["pois_with_narrative_evidence"] == 32
    assert overall["pois_with_structured_evidence"] == 50
    assert overall["pois_with_both_structured_and_narrative"] == 30

    assert shift["before_b1b"] == {"P0": 20, "P1": 19, "P2": 21, "P3": 0}
    assert shift["after_b1b"] == {"P0": 8, "P1": 7, "P2": 15, "P3": 30}
    assert shift["p0_before_after"] == {"before": 20, "after": 8, "closed": 12}

    assert by_city["Hà Nội"]["pois_with_rag_candidate_evidence"] == 18
    assert by_city["Đà Nẵng"]["pois_with_rag_candidate_evidence"] == 20
    assert by_city["Hạ Long"]["pois_with_rag_candidate_evidence"] == 14


def test_06_activity_counters_and_no_paid_social_google_llm():
    summary = json.loads(b1b_acquire.SUMMARY_JSON_PATH.read_text(encoding="utf-8"))
    counters = summary["external_activity_counters"]
    assert counters["PAID_DATA_API_USED"] is False
    assert counters["NEW_SOCIAL_COLLECTION"] == 0
    assert counters["NEW_GOOGLE_MAPS_REVIEW_COLLECTION"] == 0
    assert counters["NEW_LLM_PROVIDER_CALLS"] == 0
    assert summary["existing_controlled_db_baseline"]["db_mutated_in_b1b"] is False
    assert summary["W07_B1B_CORPUS_ACQUISITION_READY_FOR_B2"] is True
    assert all(v is False for v in summary["no_chunking_or_retrieval_methodology_freeze"].values())


def test_07_verifier_rejects_tampered_artifacts(monkeypatch, tmp_path):
    bad_jsonl = tmp_path / "bad_acquired.jsonl"
    raw_lines = [
        json.loads(line)
        for line in b1b_acquire.ACQUIRED_JSONL_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    raw_lines[0]["reuse_storage_class"] = "REFERENCE_ONLY"
    bad_jsonl.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in raw_lines) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(b1b_acquire, "ACQUIRED_JSONL_PATH", bad_jsonl)
    with pytest.raises(ValueError, match="must be OPEN_REUSABLE"):
        b1b_verify.verify_b1b_artifacts()


def test_08_upstream_artifacts_immutable():
    for rel_path, expected_sha in b1b_acquire.UPSTREAM_ARTIFACT_LF_HASHES.items():
        actual_sha = w07_a2.compute_file_sha256(REPO_ROOT / rel_path)
        assert actual_sha == expected_sha, f"Upstream artifact modified: {rel_path}"
