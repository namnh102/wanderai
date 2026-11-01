"""Offline deterministic tests for W07-0 Data + RAG Readiness Audit (Corrective 01)."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import verify_w06_scientific_closure as closure_verifier  # noqa: E402
from scripts.run_w07_data_rag_readiness_audit import (  # noqa: E402
    AUDIT_JSON_RELPATH,
    AUDIT_MD_RELPATH,
    AUTHORITATIVE_DEVELOP_BASE_SHA,
    GOOGLE_PLACES_MAX_REVIEWS_PER_PLACE,
    GOOGLE_PLACES_OFFLINE_CORPUS_ROLE,
    NEXT_GATE,
    PLANNING_ESTIMATE_LABEL,
    PREVIOUS_GATE,
    PREVIOUS_GATE_DECISION,
    SECTION_6_REQUIRED_FIELDS,
    SECTION_8_TARGET_CORPUS_SCHEMA_FIELDS,
    TRIPADVISOR_CONTENT_API_ACADEMIC_CORPUS_ROLE,
    classify_language_deterministic,
    compute_internal_sha256,
    verify_w07_audit_artifacts,
)

EXPECTED_AUDIT_JSON_FILE_SHA256 = (
    "2727cb23ea63af6eada16deba558a82f6329b13ebccb09133c32042466bd2b16"
)
EXPECTED_AUDIT_JSON_INTERNAL_SHA256 = (
    "7a951b5f93473998d4032aabfeaa250ac8e7ba2ea42cbdaf230389cd5fe3a6a9"
)
EXPECTED_AUDIT_MD_LF_SHA256 = (
    "8afab0f4fd21295c728b588542402b8b6788f9d2bb9382964a4962782bfb15a8"
)


def test_w07_audit_artifacts_verify_and_match_hashes() -> None:
    res = verify_w07_audit_artifacts(REPO_ROOT)
    assert res["status"] == "PASS"
    assert res["json_file_sha256"] == EXPECTED_AUDIT_JSON_FILE_SHA256
    assert res["json_internal_sha256"] == EXPECTED_AUDIT_JSON_INTERNAL_SHA256
    assert res["md_lf_sha256"] == EXPECTED_AUDIT_MD_LF_SHA256


def test_w07_audit_json_invariants_and_decision_flags() -> None:
    payload = json.loads((REPO_ROOT / AUDIT_JSON_RELPATH).read_text(encoding="utf-8"))

    assert payload["previous_gate"] == PREVIOUS_GATE
    assert payload["previous_gate_decision"] == PREVIOUS_GATE_DECISION
    assert payload["authoritative_base_commit"] == AUTHORITATIVE_DEVELOP_BASE_SHA
    assert payload["w06_status"] == "CLOSED_UNMODIFIED"
    assert payload["next_gate"] == NEXT_GATE
    assert payload["artifact_sha256"] == compute_internal_sha256(payload)

    # Section 4: POI authority invariants
    s4 = payload["section_4_poi_authority"]
    assert s4["total_canonical_pois_db"] == 882
    assert s4["verified_pois_freeze_v2"] == 759
    assert s4["core_pois_rec_a_v2"] == 622
    assert s4["counts_by_core_city_verified_v2"] == {
        "ha_noi": 145,
        "da_nang_total_verified": 293,
        "da_nang_rec_a_core": 289,
        "da_nang_outside_core": 4,
        "ha_long": 188,
    }
    assert (
        s4["review_to_poi_mapping_audit"][
            "real_text_reviews_against_freeze_v2_759"
        ]["EXACT_MAPPING"]
        == 0
    )
    assert (
        s4["review_to_poi_mapping_audit"][
            "synthetic_reviews_curated_9_rows_against_freeze_v2_759"
        ]["EXACT_MAPPING"]
        == 0
    )

    # Section 5: Review corpus inventory invariants
    s5 = payload["section_5_review_corpus_inventory"]
    real_inv = s5["authoritative_real_review_text_corpus_against_freeze_v2_759"]
    assert real_inv["total_rows"] == 0
    assert real_inv["unique_reviews"] == 0
    assert real_inv["reviews_by_city"] == {"Hà Nội": 0, "Đà Nẵng": 0, "Hạ Long": 0}
    assert (
        real_inv["reviews_per_poi_across_759_verified_pois"]["pois_with_0_reviews"]
        == 759
    )
    assert (
        real_inv["reviews_per_poi_across_622_core_pois"]["pois_with_0_reviews"] == 622
    )

    synth_inv = s5["quarantined_synthetic_reviews_curated"]
    assert synth_inv["total_rows"] == 9
    assert synth_inv["unique_reviews"] == 9
    assert synth_inv["core_three_city_coverage"] == {
        "Hà Nội": 2,
        "Đà Nẵng": 4,
        "Hạ Long": 0,
    }

    vh_inv = s5["vihorec_rating_interactions"]
    assert vh_inv["total_hotels"] == 560
    assert vh_inv["total_users"] == 6822
    assert vh_inv["total_interactions"] == 17911
    assert vh_inv["review_text_rows"] == 0

    # Section 6: All 13 fields present with missingness percentages
    s6 = payload["section_6_review_field_quality"]
    assert s6["required_fields"] == SECTION_6_REQUIRED_FIELDS
    for src_data in s6["sources"].values():
        assert list(src_data["missingness_pct_by_field"].keys()) == SECTION_6_REQUIRED_FIELDS

    # Section 12: Synthetic data firewall
    s12 = payload["section_12_synthetic_data_firewall"]
    assert s12["REAL_REVIEW_DATA"]["text_review_rows"] == 0
    assert s12["SYNTHETIC_REVIEW_DATA"]["text_review_rows"] == 9
    assert s12["UNKNOWN_PROVENANCE"]["text_review_rows"] == 0

    # Section 13 & 14: Retrieval unit and W07 evaluation feasibility
    assert (
        payload["section_13_retrieval_unit_recommendation"][
            "recommended_primary_unit"
        ]
        == "one_review_equals_one_retrieval_unit"
    )
    assert (
        payload["section_14_w07_evaluation_feasibility"]["RAG_READINESS_STATUS"]
        == "NOT_READY"
    )
    assert (
        payload["section_14_w07_evaluation_feasibility"][
            "can_create_human_relevance_labels_from_current_corpus"
        ]
        is False
    )


def test_corrective_01_regression_assertions() -> None:
    """Covers the 7 required regression assertions from Corrective 01 Section 12."""
    payload = json.loads((REPO_ROOT / AUDIT_JSON_RELPATH).read_text(encoding="utf-8"))
    s15 = payload["section_15_technology_decision_matrix"]
    s16 = payload["section_16_infrastructure_readiness"]
    s17 = payload["section_17_api_external_ai_firewall"]
    s19 = payload["section_19_decision_categories"]
    s20 = payload["section_20_review_data_acquisition_specification"]

    # 1. Google max-review feasibility constraint & storage policy role
    g_corr = s20["api_feasibility_corrections"]["google_places"]
    assert GOOGLE_PLACES_MAX_REVIEWS_PER_PLACE == 5
    assert g_corr["GOOGLE_PLACES_MAX_REVIEWS_PER_PLACE"] == 5
    assert (
        g_corr["GOOGLE_PLACES_OFFLINE_CORPUS_ROLE"]
        == "NOT_APPROVED_PENDING_STORAGE_TERMS_REVIEW"
    )
    assert g_corr["GOOGLE_PLACES_OFFLINE_CORPUS_ROLE"] == GOOGLE_PLACES_OFFLINE_CORPUS_ROLE
    assert g_corr["can_satisfy_10_to_15_reviews_per_poi_by_itself"] is False

    # 2. Tripadvisor academic-role exclusion
    ta_corr = s20["api_feasibility_corrections"]["tripadvisor"]
    assert (
        ta_corr["TRIPADVISOR_CONTENT_API_ACADEMIC_CORPUS_ROLE"]
        == "NOT_RECOMMENDED"
    )
    assert (
        ta_corr["TRIPADVISOR_CONTENT_API_ACADEMIC_CORPUS_ROLE"]
        == TRIPADVISOR_CONTENT_API_ACADEMIC_CORPUS_ROLE
    )

    # 3. Three-tier acquisition target
    tiers = s20["acquisition_target_tiers"]
    assert set(tiers.keys()) == {"scientific_minimum", "preferred", "stretch"}
    assert tiers["scientific_minimum"]["min_canonical_pois"] == 60
    assert tiers["scientific_minimum"]["min_reviews_per_poi"] == 5
    assert tiers["scientific_minimum"]["min_total_usable_reviews"] == 300
    assert tiers["preferred"]["target_canonical_pois_range"] == "75-100"
    assert tiers["preferred"]["target_reviews_per_poi_range"] == "8-12"
    assert tiers["preferred"]["target_total_usable_reviews_range"] == "600-1,200"
    assert tiers["stretch"]["target_canonical_pois_approx"] == 110
    assert tiers["stretch"]["target_reviews_per_poi_range"] == "10-15"
    assert tiers["stretch"]["target_total_usable_reviews_range"] == "1,100-1,650"
    assert tiers["stretch"]["is_prerequisite_for_starting_w07"] is False

    # 4. No Google/Tripadvisor primary-corpus claim + candidate queue + mapping & schema rules
    assert g_corr["approved_as_primary_frozen_w07_corpus"] is False
    assert ta_corr["approved_as_primary_frozen_w07_corpus"] is False
    tier_names = [t["tier"] for t in s20["candidate_source_classes_ranked"]]
    assert tier_names == ["Tier A", "Tier B", "Tier C", "Excluded"]

    queue = {c["candidate_slot"]: c for c in s20["candidate_dataset_feasibility_queue"]}
    assert queue["Candidate A"]["dataset_id"] == "ThanThoai9x/vietnamese-food-images"
    assert queue["Candidate A"]["status"] == "PROMISING_BUT_NOT_YET_APPROVED"
    assert queue["Candidate A"]["acquired_or_downloaded_in_w07_0"] is False
    assert (
        queue["Candidate B"]["dataset_id"]
        == "pqthinh232/vietnamese-restaurant-review-sentiment-dataset"
    )
    assert queue["Candidate B"]["status"] == "AUXILIARY_TEXT_DATA_ONLY"
    assert queue["Candidate B"]["usable_for_authoritative_poi_grounded_retrieval"] is False
    assert queue["Candidate C"]["dataset_id"] == "VLSP2018-ABSA-Restaurant"
    assert queue["Candidate C"]["status"] == "AUXILIARY_ABSA_DATASET"
    assert queue["Candidate C"]["usable_for_authoritative_poi_grounded_retrieval"] is False

    mapping_req = s20["canonical_mapping_requirements"]
    assert mapping_req["name_only_automatic_linking_forbidden"] is True
    assert s20["required_primary_corpus_schema_fields"] == SECTION_8_TARGET_CORPUS_SCHEMA_FIELDS
    assert len(SECTION_8_TARGET_CORPUS_SCHEMA_FIELDS) == 17
    assert s20["do_not_fabricate_missing_upstream_fields"] is True

    # 5. Planning estimates explicitly non-measured
    assert PLANNING_ESTIMATE_LABEL == "PLANNING_ESTIMATE_NOT_MEASURED"
    assert s15["winner_frozen_in_w07_0"] is False
    assert s15["measurement_hygiene_label"] == PLANNING_ESTIMATE_LABEL
    assert s15["lexical_baseline"]["measurement_status"] == PLANNING_ESTIMATE_LABEL
    for cand in s15["dense_retrieval_candidate_families"]:
        assert cand["measurement_status"] == PLANNING_ESTIMATE_LABEL
        assert PLANNING_ESTIMATE_LABEL in cand["cpu_latency_and_memory"]
    for idx_opt in s15["index_and_vector_store_comparison"]:
        assert idx_opt["measurement_status"] == PLANNING_ESTIMATE_LABEL
    assert s16["measurement_hygiene_label"] == PLANNING_ESTIMATE_LABEL
    for item in s16["items"].values():
        assert item["measurement_status"] == PLANNING_ESTIMATE_LABEL

    # 6. Infrastructure flags & API/acquisition firewall unchanged
    assert s19 == {
        "CURRENT_REVIEW_DATA_SUFFICIENT_FOR_W07": False,
        "ADDITIONAL_REVIEW_DATA_REQUIRED": True,
        "HUMAN_LABELING_REQUIRED": True,
        "GPU_REQUIRED_NOW": False,
        "SERVER_REQUIRED_NOW": False,
        "VECTOR_DB_SERVER_REQUIRED_NOW": False,
        "PAID_EMBEDDING_API_REQUIRED": False,
        "LLM_API_REQUIRED_NOW": False,
    }
    assert s17["NEW_LLM_PROVIDER_CALLS"] == 0
    assert s17["NEW_REVIEW_DATA_ACQUIRED"] == 0
    assert s17["google_places_calls"] == 0
    assert s17["tripadvisor_calls"] == 0
    assert s17["secrets_inspected_or_printed"] is False

    # 7. W06 untouched
    w06_json_path = REPO_ROOT / closure_verifier.CLOSURE_JSON_REL_PATH
    w06_md_path = REPO_ROOT / closure_verifier.CLOSURE_MD_REL_PATH
    assert w06_json_path.is_file()
    assert w06_md_path.is_file()
    w06_payload = json.loads(w06_json_path.read_text(encoding="utf-8"))
    assert w06_payload == closure_verifier.build_closure_payload()
    assert (
        w06_payload["closure_internal_sha256"]
        == closure_verifier.compute_closure_internal_sha256(w06_payload)
    )


def test_deterministic_language_classifier_offline() -> None:
    assert classify_language_deterministic("Bãi biển Mỹ Khê rất đẹp và sạch sẽ.") == "vi"
    assert classify_language_deterministic("Loved visiting this place!") == "en"
    assert classify_language_deterministic("") == "unknown_or_empty"


def test_w07_audit_tamper_detection(tmp_path: Path) -> None:
    # Copy required tracked files to a temp workspace without restricted vihorec
    for rel in [
        "data/manifests/dataset-freeze-v2.yaml",
        "data/curated/gomate_places_freeze_v2.json",
        "data/curated/places_canonical.json",
        "data/raw/vietnam_travel_reviews.json",
        "data/processed/reviews_normalized.json",
        "data/curated/reviews_curated.json",
        "data/manifests/review-provenance.json",
        "data/manifests/review-dataset-candidates.yaml",
        "data/research/preferences/synthetic_preferences_v1.jsonl",
        "data/seed/synthetic_places.json",
        "data/seed/synthetic_destinations.json",
        AUDIT_JSON_RELPATH,
        AUDIT_MD_RELPATH,
    ]:
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / rel, dst)

    # Verify fallback without local data/restricted/vihorec works cleanly (simulating GitHub Actions CI)
    ci_sim_result = verify_w07_audit_artifacts(tmp_path)
    assert ci_sim_result["status"] == "PASS"

    # Mutate Markdown -> must fail verification
    md_file = tmp_path / AUDIT_MD_RELPATH
    md_file.write_text(md_file.read_text(encoding="utf-8") + "\nTAMPER\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Markdown differs"):
        verify_w07_audit_artifacts(tmp_path)
