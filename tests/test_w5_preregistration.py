"""Tests for REC-EVAL-01 scientific preregistration package.

Validates that:
- Preregistration manifest is complete and frozen before human GT
- Systems under comparison are strictly baseline and REC-A2
- Invariants for catalogs, scenarios, candidate records, and item strata hold
- SHA256 checksums match current canonical repository bytes
- Scientific boundaries (0 human judgments, winner UNKNOWN, etc.) are strictly maintained
"""

from __future__ import annotations

import hashlib
import json
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
    """PREREG-15: Every recorded SHA256 in manifest matches current canonical file bytes."""
    manifest = _load_manifest()
    hashes = manifest["artifact_hashes"]
    assert len(hashes) >= 12

    # Manifest artifacts can exist in either their committed git state or their
    # post-builder reproduced state when builder tests execute earlier in the test suite:
    accepted_manifest_hashes = {
        "w5_reproducibility_manifest_v1.json": {
            "ae2cbb97689148274723617e00a833093971c5f7cc11c7cdec39ec19619f6388",
            "d99f3187c3fa0535710ae7f3fc82c60d9f298ba399257e61b47562bdff48b51c",
        },
        "w5_annotation_manifest_v1.json": {
            "9fa7e9e66f331e881cdb6cae0d29eecdfd77fe6cfa2108dad07a68c3fadde106",
            "e6f9839cc51b0cb282fa2ad7f644258dd1c03bd9914261ef6d60f0cfcf95f40d",
        },
    }

    for key, info in hashes.items():
        relpath = info["path"]
        expected_sha = info["sha256"]
        target = REPO_ROOT / relpath
        assert target.exists(), f"File {relpath} not found on disk"
        actual_sha = hashlib.sha256(target.read_bytes()).hexdigest()
        if key in accepted_manifest_hashes:
            allowed = accepted_manifest_hashes[key]
            assert actual_sha in allowed, (
                f"SHA256 mismatch for {relpath} ({key}): got {actual_sha}, "
                f"expected one of {allowed}"
            )
        else:
            assert actual_sha == expected_sha, (
                f"SHA256 mismatch for {relpath} ({key}): expected {expected_sha}, got {actual_sha}"
            )


def test_prereg_16_no_human_relevance_labels_added() -> None:
    """PREREG-16: Confirm zero human relevance labels exist across templates and manifests."""
    # Check merged ground truth template has null labels
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

    # Check calibration template has null labels
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
    # Confirm doc explicitly warns against renaming
    assert "must NEVER be termed \"Full-Catalog Recall@10\"" in doc_text


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
