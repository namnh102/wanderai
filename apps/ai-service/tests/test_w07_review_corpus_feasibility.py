"""Offline deterministic verification tests for W07-A1 Public Review Corpus Feasibility."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from scripts import (
    run_w07_data_rag_readiness_audit as w07_0_audit,
    run_w07_review_corpus_feasibility as w07_a1,
    verify_w06_scientific_closure as w06_closure,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
FEASIBILITY_JSON_PATH = REPO_ROOT / w07_a1.FEASIBILITY_JSON_RELPATH
FEASIBILITY_MD_PATH = REPO_ROOT / w07_a1.FEASIBILITY_MD_RELPATH


def test_w07_a1_verifier_passes_and_hashes_match() -> None:
    result = w07_a1.verify_w07_a1_artifacts(REPO_ROOT)
    assert result["status"] == "PASS"
    assert (
        result["internal_sha256"]
        == "6658b23c4f58f9dd05b7739e20eb7bd0543ed93f8dea76010e4ec3639eae6442"
    )
    assert (
        result["file_lf_sha256"]
        == "1790ec89f6660217584db81f1983da88a5aa3d02e2b2190ad4d4d3672faa6c1b"
    )
    assert (
        result["md_lf_sha256"]
        == "5a09b3719af1be0f1e97762491a1073bc63a2f14459c3292c6d3b0a5403395dd"
    )


def test_w07_a1_terminal_decision_keys_order_and_values() -> None:
    payload = json.loads(FEASIBILITY_JSON_PATH.read_text(encoding="utf-8"))
    all_keys = list(payload.keys())
    tail_keys = tuple(all_keys[-11:])
    assert tail_keys == (
        "RECOMMENDED_PRIMARY_SOURCE_STRATEGY",
        "APPROVED_PUBLIC_DATASETS",
        "AUXILIARY_DATASETS",
        "REJECTED_DATASETS",
        "TARGETED_COLLECTION_REQUIRED",
        "TARGETED_COLLECTION_GAPS",
        "USER_ACTION_REQUIRED",
        "EXPECTED_CORPUS_SIZE",
        "EXPECTED_CANONICAL_POI_COVERAGE",
        "EXPECTED_CITY_COVERAGE",
        "EXPECTED_CATEGORY_COVERAGE",
    )
    assert payload["RECOMMENDED_PRIMARY_SOURCE_STRATEGY"] == "TARGETED_COLLECTION_REQUIRED"
    assert payload["APPROVED_PUBLIC_DATASETS"] == []
    assert payload["TARGETED_COLLECTION_REQUIRED"] is True
    assert "phamluan/vn_msa_sar_v3" in payload["AUXILIARY_DATASETS"]
    assert "ThanThoai9x/vietnamese-food-images" in payload["REJECTED_DATASETS"]
    assert payload["EXPECTED_CORPUS_SIZE"]["scientific_minimum_target_reviews"] == 300
    assert payload["EXPECTED_CANONICAL_POI_COVERAGE"]["scientific_minimum_covered_pois"] == 60


def test_w07_a1_candidate_a_deep_audit_hcmc_proof_and_multiplicity() -> None:
    payload = json.loads(FEASIBILITY_JSON_PATH.read_text(encoding="utf-8"))
    ca = payload["candidate_a_deep_audit"]
    assert ca["dataset_id"] == "ThanThoai9x/vietnamese-food-images"
    assert ca["accessibility"]["gated_access_mode"] == "manual"
    assert ca["accessibility"]["download_size_gb"] == 18.2
    assert ca["accessibility"]["bulk_downloaded_in_w07_a1"] is False
    assert ca["actual_schema"]["field_count"] == 35
    assert ca["actual_schema"]["text_is_review_text"] is True
    assert ca["multiplicity_and_unique_review_analysis"]["total_image_rows"] == 34104
    assert ca["multiplicity_and_unique_review_analysis"]["unique_places"] == 1989
    assert (
        ca["multiplicity_and_unique_review_analysis"]["row_granularity"]
        == "IMAGE_ROW_KEYED_BY_PHOTO_ID"
    )
    geo = ca["geographic_coverage_proof"]
    assert sum(geo["search_areas_reported_on_card"].values()) == 34104
    assert geo["sum_of_9_hcmc_districts"] == 34104
    assert geo["hcmc_share_of_dataset_pct"] == 100.0
    assert geo["ha_noi_unique_places"] == 0
    assert geo["ha_noi_unique_reviews"] == 0
    assert geo["da_nang_unique_places"] == 0
    assert geo["da_nang_unique_reviews"] == 0
    assert geo["ha_long_unique_places"] == 0
    assert geo["ha_long_unique_reviews"] == 0
    assert ca["canonical_mapping_to_freeze_v2"]["canonical_freeze_v2_pois_matched"] == 0
    assert ca["classification"] == "REJECTED"


def test_w07_a1_mandatory_candidates_and_license_classifications() -> None:
    payload = json.loads(FEASIBILITY_JSON_PATH.read_text(encoding="utf-8"))
    matrix = payload["candidate_evaluation_matrix"]
    covered_mandatory = {c["mandatory_candidate_covered"] for c in matrix}
    for req in (
        "ThanThoai9x/vietnamese-food-images",
        "pqthinh232/vietnamese-restaurant-review-sentiment-dataset",
        "VLSP2018-ABSA-Restaurant",
        "phamluan/vn_msa_sar",
    ):
        assert req in covered_mandatory

    for cand in matrix:
        assert cand.get("DATASET_LICENSE")
        assert cand.get("UPSTREAM_CONTENT_ORIGIN")
        assert cand.get("RESEARCH_REUSE_CONFIDENCE")
        assert cand["classification"] in {
            "APPROVED_CANDIDATE",
            "CONDITIONAL_CANDIDATE",
            "AUXILIARY_ONLY",
            "REJECTED",
        }
        assert (
            cand["canonical_mapping_feasibility"]["canonical_freeze_v2_pois_matched"] == 0
        )


def test_w07_a1_firewall_and_zero_llm_calls() -> None:
    payload = json.loads(FEASIBILITY_JSON_PATH.read_text(encoding="utf-8"))
    fw = payload["execution_discipline_and_firewall"]
    assert fw["NEW_LLM_PROVIDER_CALLS"] == 0
    assert fw["NEW_EMBEDDING_API_CALLS"] == 0
    assert fw["NEW_RERANKER_API_CALLS"] == 0
    assert fw["NEW_PAID_SERVICE_CALLS"] == 0
    assert fw["SCRAPING_EXECUTED"] is False
    assert fw["BULK_GATED_DATA_DOWNLOADED"] is False
    assert fw["GOOGLE_PLACES_MAX_REVIEWS_PER_PLACE"] == 5
    assert (
        fw["GOOGLE_PLACES_OFFLINE_CORPUS_ROLE"]
        == "NOT_APPROVED_PENDING_STORAGE_TERMS_REVIEW"
    )
    assert (
        fw["TRIPADVISOR_CONTENT_API_ACADEMIC_CORPUS_ROLE"] == "NOT_RECOMMENDED"
    )


def test_w07_a1_preserves_w06_and_w07_0_immutability() -> None:
    w06_payload = w06_closure.build_closure_payload()
    assert (
        w06_closure.compute_closure_internal_sha256(w06_payload)
        == w07_a1.EXPECTED_W06_CLOSURE_INTERNAL_SHA256
    )
    w07_0_res = w07_0_audit.verify_w07_audit_artifacts(REPO_ROOT)
    assert w07_0_res["status"] == "PASS"
    assert (
        w07_0_res["json_internal_sha256"]
        == w07_a1.EXPECTED_W07_0_INTERNAL_SHA256
    )


def test_w07_a1_tamper_detection(tmp_path: Path) -> None:
    # Copy required inputs to tmp_path and verify tamper detection
    for rel in (
        w07_a1.FEASIBILITY_JSON_RELPATH,
        w07_a1.FEASIBILITY_MD_RELPATH,
        w07_a1.W07_0_AUDIT_JSON_RELPATH,
        w07_a1.W06_CLOSURE_JSON_RELPATH,
        "data/curated/gomate_places_freeze_v2.json",
        "data/manifests/review-provenance.json",
        "data/manifests/review-dataset-candidates.yaml",
    ):
        src = REPO_ROOT / rel
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    assert w07_a1.verify_w07_a1_artifacts(tmp_path)["status"] == "PASS"

    # Tamper with JSON terminal key
    tampered_json = json.loads(
        (tmp_path / w07_a1.FEASIBILITY_JSON_RELPATH).read_text(encoding="utf-8")
    )
    tampered_json["TARGETED_COLLECTION_REQUIRED"] = False
    (tmp_path / w07_a1.FEASIBILITY_JSON_RELPATH).write_text(
        json.dumps(tampered_json, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="does not match expected deterministic payload"):
        w07_a1.verify_w07_a1_artifacts(tmp_path)
