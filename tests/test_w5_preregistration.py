"""Tests for REC-EVAL-01 scientific preregistration package.

Validates:
- PREREG-01 to PREREG-20: Base preregistration manifest and invariant specifications
- PREREG-21 to PREREG-33: Hardened scientific semantics, consensus policies, and provenance
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Dict

REPO_ROOT = Path(__file__).resolve().parent.parent

MANIFEST_PATH = REPO_ROOT / "data" / "evaluation" / "reca_w5" / "rec_eval_01_prereg_manifest_v1.json"
DOC_PATH = REPO_ROOT / "docs" / "research" / "rec_eval_01_prereg_v1.md"


def _load_manifest() -> Dict[str, Any]:
    assert MANIFEST_PATH.exists(), f"Preregistration manifest not found at {MANIFEST_PATH}"
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_prereg_01_manifest_version_and_status() -> None:
    """PREREG-01: Verify manifest version and frozen status."""
    manifest = _load_manifest()
    assert manifest["preregistration_version"] == "REC-EVAL-01-PREREG-V1"
    assert manifest["status"] == "FROZEN_BEFORE_HUMAN_GT"
    assert manifest["roadmap_package"] == "REC-EVAL-01"


def test_prereg_02_systems_under_comparison() -> None:
    """PREREG-02: Systems must be exactly shared baseline and REC-A2."""
    manifest = _load_manifest()
    expected_systems = ["shared_a0_a1_baseline", "rec-a2"]
    assert manifest["systems"] == expected_systems
    assert len(manifest["systems"]) == 2


def test_prereg_03_top_k() -> None:
    """PREREG-03: K must be exactly 10."""
    manifest = _load_manifest()
    assert manifest["top_k"] == 10


def test_prereg_04_primary_metric() -> None:
    """PREREG-04: Primary metric must be NDCG@10 with graded gain 2^rel - 1."""
    manifest = _load_manifest()
    assert manifest["primary_metric"] == "NDCG@10"
    assert manifest["relevance_scale"] == [0, 1, 2, "NA"]
    assert manifest["binary_relevance_threshold"] == 1
    assert manifest.get("gain_formula") == "2^rel - 1"


def test_prereg_05_bootstrap_seed() -> None:
    """PREREG-05: Bootstrap seed must be exactly 20261013."""
    manifest = _load_manifest()
    assert manifest["bootstrap"]["seed"] == 20261013
    assert manifest["bootstrap"]["paired"] is True
    assert manifest["bootstrap"]["destination_stratified"] is True


def test_prereg_06_bootstrap_replicates() -> None:
    """PREREG-06: Bootstrap replicates must be exactly 10,000."""
    manifest = _load_manifest()
    assert manifest["bootstrap"]["replicates"] == 10000


def test_prereg_07_scenario_invariants() -> None:
    """PREREG-07: Scenario invariants (30 primary, 15 U1, 15 U2, 6 THIN)."""
    manifest = _load_manifest()
    assert manifest["primary_scenarios"] == 30
    assert manifest["u1"] == 15
    assert manifest["u2"] == 15
    assert manifest["thin"] == 6

    # Verify actual scenario files match
    primary_p = REPO_ROOT / "data" / "evaluation" / "reca_w5" / "w5_primary_scenarios_v1.json"
    scenarios = json.loads(primary_p.read_text(encoding="utf-8"))
    assert len(scenarios) == 30
    u1_scenarios = [s for s in scenarios if s.get("user_stratum") == "U1"]
    u2_scenarios = [s for s in scenarios if s.get("user_stratum") == "U2"]
    assert len(u1_scenarios) == 15
    assert len(u2_scenarios) == 15

    thin_p = REPO_ROOT / "data" / "evaluation" / "reca_w5" / "w5_thin_diagnostic_scenarios_v1.json"
    thin_scenarios = json.loads(thin_p.read_text(encoding="utf-8"))
    assert len(thin_scenarios) == 6


def test_prereg_08_catalog_invariants() -> None:
    """PREREG-08: Catalog invariants (622 core, HN=145, DN=289, HL=188)."""
    manifest = _load_manifest()
    assert manifest["rec_a_core"] == 622
    assert manifest["destinations"]["ha-noi"] == 145
    assert manifest["destinations"]["da-nang"] == 289
    assert manifest["destinations"]["ha-long"] == 188
    assert sum(manifest["destinations"].values()) == 622


def test_prereg_09_candidate_records() -> None:
    """PREREG-09: Candidate pool records must equal exactly 474."""
    manifest = _load_manifest()
    assert manifest["candidate_records"] == 474

    blinded_p = REPO_ROOT / "data" / "evaluation" / "reca_w5" / "w5_candidate_pool_blinded_v1.json"
    blinded_pool = json.loads(blinded_p.read_text(encoding="utf-8"))
    total_records = sum(len(s.get("items", [])) for s in blinded_pool)
    assert total_records == 474


def test_prereg_10_human_judgments_zero() -> None:
    """PREREG-10: Human judgments collected must be exactly 0."""
    manifest = _load_manifest()
    assert manifest["human_judgments_collected"] == 0


def test_prereg_11_human_gt_false() -> None:
    """PREREG-11: HUMAN-GT available must be False."""
    manifest = _load_manifest()
    assert manifest["human_gt_available"] is False


def test_prereg_12_winner_unknown() -> None:
    """PREREG-12: Scientific winner must be strictly UNKNOWN."""
    manifest = _load_manifest()
    assert manifest["scientific_winner"] == "UNKNOWN"


def test_prereg_13_duplicate_policy_pending() -> None:
    """PREREG-13: Duplicate policy status must be PENDING."""
    manifest = _load_manifest()
    assert manifest["duplicate_policy_status"] == "PENDING"


def test_prereg_14_calibration_not_started() -> None:
    """PREREG-14: Calibration status must be NOT_STARTED."""
    manifest = _load_manifest()
    assert manifest["calibration_status"] == "NOT_STARTED"


def test_prereg_15_recorded_sha256_matches_canonical() -> None:
    """PREREG-15: Every recorded SHA256 in manifest matches committed Git blob content at source commit."""
    manifest = _load_manifest()
    source_commit = manifest["source_commit_sha"]
    assert source_commit == "6ef96664c994cb2c1da4d94820ee78f4b4b48805"
    assert manifest["artifact_hash_basis"] == "sha256_git_committed_blob_content"

    hashes = manifest["artifact_hashes"]
    assert len(hashes) >= 12

    for key, info in hashes.items():
        relpath = info["path"]
        expected_sha = info["sha256"]
        # Fetch committed blob from Git
        res = subprocess.run(
            ["git", "show", f"{source_commit}:{relpath}"],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            check=True,
        )
        actual_sha = hashlib.sha256(res.stdout).hexdigest()
        assert actual_sha == expected_sha, (
            f"Committed blob SHA256 mismatch for {relpath} ({key}): expected {expected_sha}, got {actual_sha}"
        )


def test_prereg_16_no_human_relevance_labels_added() -> None:
    """PREREG-16: Confirm zero human relevance labels exist across templates and manifests."""
    template_p = (
        REPO_ROOT / "data" / "evaluation" / "reca_w5" / "annotation" / "w5_merged_ground_truth_template_v1.json"
    )
    if template_p.exists():
        tpl = json.loads(template_p.read_text(encoding="utf-8"))
        records = tpl.get("records", [])
        for r in records:
            assert r.get("j1_label") is None
            assert r.get("j2_label") is None
            assert r.get("j3_label") is None
            assert r.get("consensus_label") is None

    calib_p = REPO_ROOT / "data" / "evaluation" / "reca_w5" / "annotation" / "w5_calibration_v1.json"
    if calib_p.exists():
        cal = json.loads(calib_p.read_text(encoding="utf-8"))
        for it in cal.get("calibration_items", []):
            assert it.get("relevance_label") is None


def test_prereg_17_category_ild_semantics() -> None:
    """PREREG-17: Category-ILD semantics must be structural_category_diversity_proxy."""
    manifest = _load_manifest()
    assert manifest["category_ild_semantics"] == "structural_category_diversity_proxy"


def test_prereg_18_pooled_recall_terminology_preserved() -> None:
    """PREREG-18: Terminology must strictly preserve 'Pooled Recall' and prohibit 'Full-Catalog Recall'."""
    manifest = _load_manifest()
    assert manifest.get("recall_metric_name") == "Pooled Recall@10"

    doc_text = DOC_PATH.read_text(encoding="utf-8")
    assert "Pooled Recall@10" in doc_text
    assert "Full-Catalog Recall" in doc_text
    assert 'must NEVER be termed "Full-Catalog Recall@10"' in doc_text


def test_prereg_19_thin_diagnostic_only() -> None:
    """PREREG-19: THIN scenarios must be marked DIAGNOSTIC_ONLY."""
    manifest = _load_manifest()
    assert manifest.get("thin_role") == "DIAGNOSTIC_ONLY"


def test_prereg_20_u0_excluded_from_personalized_winner() -> None:
    """PREREG-20: U0 stratum must be excluded from personalized relevance winner evaluation."""
    manifest = _load_manifest()
    assert "EXCLUDED_FROM_PERSONALIZED_WINNER" in manifest.get("u0_role", "")
    assert manifest.get("item_strata") == {"I0": 405, "I1": 217}
    assert manifest.get("i1_exposure_role") == "DIAGNOSTIC_ONLY"


# ============================================================
# EXTENDED PREREG TESTS (W5-METH-LOCK-01-FIX-01)
# ============================================================


def test_prereg_21_na_is_non_ordinal() -> None:
    """PREREG-21: NA is non-ordinal missingness code, not a fourth ordinal relevance level."""
    manifest = _load_manifest()
    sem = manifest["relevance_semantics"]
    assert sem["na_is_ordinal"] is False
    assert sem["na_is_zero"] is False
    assert sem["missing_code"] == "NA"

    doc_text = DOC_PATH.read_text(encoding="utf-8")
    assert "NA is NOT an ordinal relevance level" in doc_text
    assert "NA != 0" in doc_text


def test_prereg_22_ordinal_labels_exactly_0_1_2() -> None:
    """PREREG-22: Ordinal labels must be strictly [0, 1, 2]."""
    manifest = _load_manifest()
    sem = manifest["relevance_semantics"]
    assert sem["ordinal_labels"] == [0, 1, 2]


def test_prereg_23_any_na_requires_evidence_adjudication() -> None:
    """PREREG-23: Any NA among primary judges mandates evidence adjudication (no median calculation)."""
    manifest = _load_manifest()
    agg = manifest["gt_aggregation"]
    assert agg["any_na_action"] == "PENDING_EVIDENCE_ADJUDICATION"

    doc_text = DOC_PATH.read_text(encoding="utf-8")
    assert "PENDING_EVIDENCE_ADJUDICATION" in doc_text
    assert "DO NOT compute median from the remaining numeric labels" in doc_text or "DO NOT take median" in doc_text


def test_prereg_24_severe_numeric_disagreement_requires_adjudication() -> None:
    """PREREG-24: Severe numeric disagreement (max-min = 2) mandates blind adjudication."""
    manifest = _load_manifest()
    agg = manifest["gt_aggregation"]
    assert agg["severe_range"] == 2
    assert agg["severe_action"] == "BLIND_ADJUDICATION"

    doc_text = DOC_PATH.read_text(encoding="utf-8")
    assert "PENDING_ADJUDICATION" in doc_text


def test_prereg_25_primary_confirmatory_endpoint_ndcg10() -> None:
    """PREREG-25: Primary confirmatory endpoint is strictly NDCG@10."""
    manifest = _load_manifest()
    roles = manifest["endpoint_roles"]
    assert roles["NDCG@10"] == "PRIMARY_CONFIRMATORY"
    assert manifest["primary_metric"] == "NDCG@10"

    doc_text = DOC_PATH.read_text(encoding="utf-8")
    assert "PRIMARY_CONFIRMATORY" in doc_text
    assert "Primary Confirmatory Hypothesis" in doc_text


def test_prereg_26_category_ild_and_coverage_are_supporting_secondary() -> None:
    """PREREG-26: Category-ILD and Coverage are supporting secondary endpoints (not confirmatory)."""
    manifest = _load_manifest()
    roles = manifest["endpoint_roles"]
    assert roles["Category-ILD@10"] == "SECONDARY_SUPPORTING_STRUCTURAL_PROXY"
    assert roles["CatalogCoverage@10"] == "SECONDARY_SUPPORTING"

    doc_text = DOC_PATH.read_text(encoding="utf-8")
    assert "SECONDARY_SUPPORTING" in doc_text
    assert "not evaluated as independently confirmatory" in doc_text


def test_prereg_27_u1_u2_comparison_marked_exploratory() -> None:
    """PREREG-27: U1 vs U2 subgroup analysis is explicitly designated exploratory."""
    manifest = _load_manifest()
    assert manifest["u1_u2_analysis_role"] == "EXPLORATORY_SUBGROUP"

    doc_text = DOC_PATH.read_text(encoding="utf-8")
    assert "EXPLORATORY_SUBGROUP_ANALYSIS" in doc_text


def test_prereg_28_ndcg_ci_including_zero_not_equivalence_or_parity() -> None:
    """PREREG-28: NDCG CI spanning zero means difference is not demonstrated / inconclusive, NOT equivalence/parity."""
    doc_text = DOC_PATH.read_text(encoding="utf-8")
    assert "relevance difference is not demonstrated / remains inconclusive" in doc_text
    assert "NOT establish relevance parity, equivalence, or non-inferiority" in doc_text
    assert "No non-inferiority margin has been preregistered" in doc_text


def test_prereg_29_coverage_primary_claim_is_destination_macro() -> None:
    """PREREG-29: Primary coverage claim is destination-macro, not an all-three-destinations improvement."""
    manifest = _load_manifest()
    assert manifest["aggregation_strategy"] == "destination_macro_mean"

    doc_text = DOC_PATH.read_text(encoding="utf-8")
    assert "positive destination-macro catalog coverage effect" in doc_text
    assert "Report HN/DN/HL individually as mandatory breakdowns" in doc_text or "mandatory breakdowns" in doc_text


def test_prereg_30_future_gt_uses_final_frozen_rubric_policy() -> None:
    """PREREG-30: Future GT references exact final frozen rubric version, not hard-coded V1."""
    manifest = _load_manifest()
    assert manifest["current_rubric_version"] == "W5-RUBRIC-V1"
    assert manifest["final_gt_rubric_policy"] == "REFERENCE_EXACT_FROZEN_RUBRIC_USED_FOR_PRIMARY_ANNOTATION"

    doc_text = DOC_PATH.read_text(encoding="utf-8")
    assert "exact final frozen rubric version used for primary annotation" in doc_text
    assert "W5-RUBRIC-V1 is immutable and must never be edited in place" in doc_text


def test_prereg_31_artifact_hash_basis_is_committed_blob() -> None:
    """PREREG-31: Artifact hash basis is committed Git blob content at source commit."""
    manifest = _load_manifest()
    assert manifest["source_commit_sha"] == "6ef96664c994cb2c1da4d94820ee78f4b4b48805"
    assert manifest["artifact_hash_basis"] == "sha256_git_committed_blob_content"


def test_prereg_32_every_artifact_has_exactly_one_canonical_hash() -> None:
    """PREREG-32: Every artifact in manifest has exactly one string-valued SHA256 hash (no allowlists)."""
    manifest = _load_manifest()
    hashes = manifest["artifact_hashes"]
    assert len(hashes) >= 14
    for key, info in hashes.items():
        sha = info["sha256"]
        assert isinstance(sha, str), f"Hash for {key} is not a string: {sha!r}"
        assert len(sha) == 64, f"Hash for {key} is not 64 chars: {sha}"
        assert all(c in "0123456789abcdef" for c in sha), f"Hash for {key} has non-hex characters: {sha}"


def test_prereg_33_historical_roadmap_wording() -> None:
    """PREREG-33: Methodology amendment accurately cites @K roadmap and K=5/K=10 engineering benchmarks."""
    doc_text = DOC_PATH.read_text(encoding="utf-8")
    assert "NDCG@K" in doc_text
    assert "Recall@K" in doc_text
    assert "K=5 and K=10" in doc_text
    assert "top-10 recommendation lists" in doc_text
    # Prohibit travel itineraries wording for recommender evaluation
    assert "10-item travel itineraries" not in doc_text
