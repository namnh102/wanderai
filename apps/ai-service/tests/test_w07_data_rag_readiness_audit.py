"""Offline deterministic tests for W07-0 Data + RAG Readiness Audit."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.run_w07_data_rag_readiness_audit import (  # noqa: E402
    AUDIT_JSON_RELPATH,
    AUDIT_MD_RELPATH,
    AUTHORITATIVE_DEVELOP_BASE_SHA,
    NEXT_GATE,
    PREVIOUS_GATE,
    PREVIOUS_GATE_DECISION,
    SECTION_6_REQUIRED_FIELDS,
    classify_language_deterministic,
    compute_internal_sha256,
    verify_w07_audit_artifacts,
)

EXPECTED_AUDIT_JSON_FILE_SHA256 = (
    "e12211886cf38c09e2ccd59d65f380c4688ee42bac6d6c8dcbade6c02a2f4d89"
)
EXPECTED_AUDIT_JSON_INTERNAL_SHA256 = (
    "c5728d6249a1f99c1f1f3309d041023562f7954cb8a739302edab7aa3298a58c"
)
EXPECTED_AUDIT_MD_LF_SHA256 = (
    "8d918f184d32dbaf419d36dc8a858a4b04235b50a666e8c363a474c8fa112864"
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

    # Section 17 & 19: API firewall and explicit boolean flags
    s17 = payload["section_17_api_external_ai_firewall"]
    assert s17["NEW_LLM_PROVIDER_CALLS"] == 0
    assert s17["secrets_inspected_or_printed"] is False

    s19 = payload["section_19_decision_categories"]
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
