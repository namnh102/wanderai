"""Tests for R8B Contingency and Final Method Decision (R8B-CONTINGENCY-01).

Validates R8B-CONT-01 to R8B-CONT-17 specifications:
- R8B-CONT-01: Artifact version correct (R8B-CONTINGENCY-V1).
- R8B-CONT-02: external_report_received == false.
- R8B-CONT-03: external_cross_check_completed == false.
- R8B-CONT-04: external_agreement_claimed == false.
- R8B-CONT-05: final_method_decision == METHOD_RETAINED.
- R8B-CONT-06: methodology_changed == false.
- R8B-CONT-07: Human judgments remain 0.
- R8B-CONT-08: HUMAN-GT == false.
- R8B-CONT-09: Calibration status == NOT_STARTED.
- R8B-CONT-10: Scientific winner == UNKNOWN.
- R8B-CONT-11: Duplicate policy == CLOSED_NO_PRIMARY_EVAL_IMPACT.
- R8B-CONT-12: Retained preregistration == REC-EVAL-01-PREREG-V1.
- R8B-CONT-13: Systems under test strictly [shared_a0_a1_baseline, rec-a2].
- R8B-CONT-14: Primary metric remains NDCG@10.
- R8B-CONT-15: Primary scenarios count remains 30.
- R8B-CONT-16: No human labels were populated.
- R8B-CONT-17: No frozen W5 artifact bytes changed.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent

EVAL_DIR = REPO_ROOT / "data" / "evaluation" / "reca_w5"
CONTINGENCY_JSON_PATH = EVAL_DIR / "r8b_contingency_method_decision_v1.json"
CONTINGENCY_DOC_PATH = REPO_ROOT / "docs" / "research" / "r8b_contingency_method_decision_v1.md"
PREREG_MANIFEST_PATH = EVAL_DIR / "rec_eval_01_prereg_manifest_v1.json"
GATE_RESULT_PATH = EVAL_DIR / "w5_duplicate_gate_result_v1.json"

FREEZE_V2_PATH = REPO_ROOT / "data" / "curated" / "gomate_places_freeze_v2.json"
INTERNAL_POOL_PATH = EVAL_DIR / "w5_candidate_pool_internal_v1.json"
BLINDED_POOL_PATH = EVAL_DIR / "w5_candidate_pool_blinded_v1.json"
PRIMARY_SCENARIOS_PATH = EVAL_DIR / "w5_primary_scenarios_v1.json"

EXPECTED_FREEZE_V2_SHA256 = "f7517938598e3923906763f8f31334a500ee88bc06232f2992d38e2fcb28a444"
EXPECTED_INTERNAL_POOL_SHA256 = "32b25ef8ffc19d671513f771d3d3a0d23ceb9d0cf614ace1eded94d8c84126c6"
EXPECTED_BLINDED_POOL_SHA256 = "8f178e06b1b93e59b3a53f1b2bf1b6ecc697ccfa610d56783b613b6aa2f06ec7"
EXPECTED_PRIMARY_SCENARIOS_SHA256 = "4f0c77dccc2c0bae32f5d87f1364a8e1487a83e9b7344a9d8d3c9d0528bc29fb"

BASE_DEVELOP_COMMIT = "e21f5d60c58d8ff1a63a85e14169190b8f5879ee"


def _ensure_commit(commit_sha: str) -> None:
    """Ensure commit is available locally; shallow-fetches from origin in CI if missing."""
    res = subprocess.run(
        ["git", "cat-file", "-e", f"{commit_sha}^{{commit}}"],
        cwd=REPO_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if res.returncode != 0:
        subprocess.run(
            ["git", "fetch", "origin", commit_sha, "--depth=1"],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )


def _sha256_bytes(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def _load_json(path: Path) -> Any:
    assert path.exists(), f"File not found: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def test_r8b_cont_01_artifact_version() -> None:
    """R8B-CONT-01: Artifact version and status valid."""
    data = _load_json(CONTINGENCY_JSON_PATH)
    assert data["artifact_version"] == "R8B-CONTINGENCY-V1"
    assert data["status"] == "CLOSED_WITHOUT_EXTERNAL_REPORT"
    assert data["closure_reason"] == "PROJECT_OWNER_ELECTED_TO_PROCEED_WITHOUT_WAITING_FURTHER"
    assert CONTINGENCY_DOC_PATH.exists()
    doc_text = CONTINGENCY_DOC_PATH.read_text(encoding="utf-8")
    assert "R8B Contingency & Final Method Decision V1" in doc_text
    assert "CLOSED_WITHOUT_EXTERNAL_REPORT" in doc_text


def test_r8b_cont_02_external_report_not_received() -> None:
    """R8B-CONT-02: external_report_received == false."""
    data = _load_json(CONTINGENCY_JSON_PATH)
    assert data["external_report_received"] is False


def test_r8b_cont_03_external_cross_check_not_completed() -> None:
    """R8B-CONT-03: external_cross_check_completed == false."""
    data = _load_json(CONTINGENCY_JSON_PATH)
    assert data["external_cross_check_completed"] is False


def test_r8b_cont_04_external_agreement_claimed_false() -> None:
    """R8B-CONT-04: external_agreement_claimed == false."""
    data = _load_json(CONTINGENCY_JSON_PATH)
    assert data["external_agreement_claimed"] is False

    doc_text = CONTINGENCY_DOC_PATH.read_text(encoding="utf-8")
    assert "Researcher-1 approved" not in doc_text
    assert "external review passed" not in doc_text
    assert "independent validation completed" not in doc_text


def test_r8b_cont_05_final_method_decision_retained() -> None:
    """R8B-CONT-05: final_method_decision == METHOD_RETAINED."""
    data = _load_json(CONTINGENCY_JSON_PATH)
    assert data["final_method_decision"] == "METHOD_RETAINED"

    doc_text = CONTINGENCY_DOC_PATH.read_text(encoding="utf-8")
    assert "METHOD_RETAINED" in doc_text


def test_r8b_cont_06_methodology_changed_false() -> None:
    """R8B-CONT-06: methodology_changed == false."""
    data = _load_json(CONTINGENCY_JSON_PATH)
    assert data["methodology_changed"] is False


def test_r8b_cont_07_human_judgments_remain_zero() -> None:
    """R8B-CONT-07: Human judgments remain 0."""
    data = _load_json(CONTINGENCY_JSON_PATH)
    assert data["human_judgments_collected"] == 0

    manifest = _load_json(PREREG_MANIFEST_PATH)
    assert manifest["human_judgments_collected"] == 0


def test_r8b_cont_08_human_gt_false() -> None:
    """R8B-CONT-08: HUMAN-GT == false."""
    data = _load_json(CONTINGENCY_JSON_PATH)
    assert data["human_gt_available"] is False

    manifest = _load_json(PREREG_MANIFEST_PATH)
    assert manifest["human_gt_available"] is False


def test_r8b_cont_09_calibration_not_started() -> None:
    """R8B-CONT-09: Calibration status == NOT_STARTED."""
    data = _load_json(CONTINGENCY_JSON_PATH)
    assert data["calibration_status"] == "NOT_STARTED"


def test_r8b_cont_10_scientific_winner_unknown() -> None:
    """R8B-CONT-10: Scientific winner == UNKNOWN."""
    data = _load_json(CONTINGENCY_JSON_PATH)
    assert data["scientific_winner"] == "UNKNOWN"


def test_r8b_cont_11_duplicate_policy_closed() -> None:
    """R8B-CONT-11: Duplicate policy == CLOSED_NO_PRIMARY_EVAL_IMPACT."""
    data = _load_json(CONTINGENCY_JSON_PATH)
    assert data["duplicate_policy_status"] == "CLOSED_NO_PRIMARY_EVAL_IMPACT"

    gate = _load_json(GATE_RESULT_PATH)
    assert gate["duplicate_policy_status"] == "CLOSED_NO_PRIMARY_EVAL_IMPACT"
    assert gate["status"] == "PASS"


def test_r8b_cont_12_retained_preregistration() -> None:
    """R8B-CONT-12: Retained preregistration == REC-EVAL-01-PREREG-V1."""
    data = _load_json(CONTINGENCY_JSON_PATH)
    assert data["retained_preregistration"] == "REC-EVAL-01-PREREG-V1"

    manifest = _load_json(PREREG_MANIFEST_PATH)
    assert manifest["preregistration_version"] == "REC-EVAL-01-PREREG-V1"


def test_r8b_cont_13_systems_under_test() -> None:
    """R8B-CONT-13: Systems strictly [shared_a0_a1_baseline, rec-a2]."""
    data = _load_json(CONTINGENCY_JSON_PATH)
    expected_systems = ["shared_a0_a1_baseline", "rec-a2"]
    assert data["systems"] == expected_systems

    manifest = _load_json(PREREG_MANIFEST_PATH)
    assert manifest["systems"] == expected_systems


def test_r8b_cont_14_primary_metric_ndcg10() -> None:
    """R8B-CONT-14: Primary metric remains NDCG@10."""
    data = _load_json(CONTINGENCY_JSON_PATH)
    assert data["primary_metric"] == "NDCG@10"

    manifest = _load_json(PREREG_MANIFEST_PATH)
    assert manifest["primary_metric"] == "NDCG@10"
    assert manifest["endpoint_roles"]["NDCG@10"] == "PRIMARY_CONFIRMATORY"


def test_r8b_cont_15_primary_scenarios_count() -> None:
    """R8B-CONT-15: Primary scenarios count remains 30."""
    data = _load_json(CONTINGENCY_JSON_PATH)
    assert data["primary_scenarios"] == 30
    assert data["u1_scenarios"] == 15
    assert data["u2_scenarios"] == 15

    scenarios = _load_json(PRIMARY_SCENARIOS_PATH)
    assert len(scenarios) == 30


def test_r8b_cont_16_no_human_labels_populated() -> None:
    """R8B-CONT-16: No human labels were populated."""
    annotation_dir = EVAL_DIR / "annotation"
    for judge_id in ["J1", "J2", "J3"]:
        pkg_path = annotation_dir / f"w5_judge_{judge_id}_v1.json"
        assert pkg_path.exists(), f"Package missing: {pkg_path}"
        pkg = _load_json(pkg_path)
        for scn in pkg["scenarios"]:
            for item in scn["items"]:
                assert item["label"] is None, (
                    f"Found populated label in {judge_id} scenario {scn['scenario_id']}"
                )
                assert item["judge_note"] is None, (
                    f"Found populated note in {judge_id} scenario {scn['scenario_id']}"
                )


def test_r8b_cont_17_no_frozen_w5_artifact_bytes_changed() -> None:
    """R8B-CONT-17: No frozen W5 artifact bytes changed."""
    assert _sha256_bytes(FREEZE_V2_PATH) == EXPECTED_FREEZE_V2_SHA256
    assert _sha256_bytes(INTERNAL_POOL_PATH) == EXPECTED_INTERNAL_POOL_SHA256
    assert _sha256_bytes(BLINDED_POOL_PATH) == EXPECTED_BLINDED_POOL_SHA256
    assert _sha256_bytes(PRIMARY_SCENARIOS_PATH) == EXPECTED_PRIMARY_SCENARIOS_SHA256

    _ensure_commit(BASE_DEVELOP_COMMIT)
    frozen_files = [
        str(FREEZE_V2_PATH),
        str(INTERNAL_POOL_PATH),
        str(BLINDED_POOL_PATH),
        str(PRIMARY_SCENARIOS_PATH),
        str(PREREG_MANIFEST_PATH),
        str(GATE_RESULT_PATH),
    ]
    res = subprocess.run(
        ["git", "diff", BASE_DEVELOP_COMMIT, "--", *frozen_files],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    assert res.stdout.strip() == "", "Frozen W5 artifacts modified relative to base commit!"
