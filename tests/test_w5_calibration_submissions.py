"""Tests for W5 Raw Human Calibration Submissions (W5-CAL-01-SUBMIT-01).

Covers required tests CAL-SUB-01 through CAL-SUB-20:
- CAL-SUB-01: exactly J1/J2/J3 raw files exist.
- CAL-SUB-02: 45 rows each.
- CAL-SUB-03: all three pass frozen submission validator.
- CAL-SUB-04: same canonical item membership.
- CAL-SUB-05: no duplicate item per judge.
- CAL-SUB-06: all labels populated.
- CAL-SUB-07: labels strictly in {0,1,2,NA} under frozen type semantics.
- CAL-SUB-08: read-only context exactly frozen.
- CAL-SUB-09: raw file SHA256 matches manifest.
- CAL-SUB-10: total judgments = 135.
- CAL-SUB-11: calibration_only = true.
- CAL-SUB-12: excluded_from_final_metrics = true.
- CAL-SUB-13: human_gt = false.
- CAL-SUB-14: no consensus/final_relevance field exists.
- CAL-SUB-15: no recommender metric result created.
- CAL-SUB-16: canonical calibration package unchanged.
- CAL-SUB-17: rubric unchanged.
- CAL-SUB-18: primary pool unchanged.
- CAL-SUB-19: R8B remains METHOD_RETAINED.
- CAL-SUB-20: duplicate policy remains CLOSED_NO_PRIMARY_EVAL_IMPACT.
"""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from scripts.validate_w5_calibration_submission import (
    ALLOWED_JUDGES,
    CANONICAL_CALIBRATION_PATH,
    CSV_ALL_COLUMNS,
    CSV_READ_ONLY_COLUMNS,
    build_judge_calibration_package,
    load_canonical_calibration,
    load_csv_package_as_submission_dict,
    main as validator_cli_main,
    package_to_csv_rows,
    validate_calibration_submission,
    validate_completed_calibration_label,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = REPO_ROOT / "data" / "evaluation" / "reca_w5"
ANNOTATION_DIR = EVAL_DIR / "annotation"
SUBMISSIONS_DIR = EVAL_DIR / "calibration_submissions"
INBOX_DIR = SUBMISSIONS_DIR / "inbox"
RAW_V1_DIR = SUBMISSIONS_DIR / "raw_v1"
RAW_MANIFEST_PATH = SUBMISSIONS_DIR / "w5_calibration_raw_manifest_v1.json"
RECEIPT_DOC_PATH = REPO_ROOT / "docs" / "research" / "w5_calibration_submission_receipt_v1.md"

PRIMARY_SCENARIOS_PATH = EVAL_DIR / "w5_primary_scenarios_v1.json"
BLINDED_POOL_PATH = EVAL_DIR / "w5_candidate_pool_blinded_v1.json"
INTERNAL_POOL_PATH = EVAL_DIR / "w5_candidate_pool_internal_v1.json"
RUBRIC_PATH = ANNOTATION_DIR / "w5_rubric_v1.md"
PREREG_MANIFEST_PATH = EVAL_DIR / "rec_eval_01_prereg_manifest_v1.json"
R8B_JSON_PATH = EVAL_DIR / "r8b_contingency_method_decision_v1.json"
DUP_GATE_PATH = EVAL_DIR / "w5_duplicate_gate_result_v1.json"


def _load_json(path: Path) -> Any:
    assert path.exists(), f"Missing file: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_blob_sha256(relpath: str, ref: str = "HEAD") -> str:
    res = subprocess.run(
        ["git", "show", f"{ref}:{relpath}"],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return hashlib.sha256(res.stdout).hexdigest()


def test_cal_sub_01_exact_j1_j2_j3_raw_files_exist() -> None:
    """CAL-SUB-01: Exactly J1/J2/J3 raw files exist."""
    raw_files = sorted(RAW_V1_DIR.glob("*_w5_calibration_raw_v1.csv"))
    assert [p.name for p in raw_files] == [
        "J1_w5_calibration_raw_v1.csv",
        "J2_w5_calibration_raw_v1.csv",
        "J3_w5_calibration_raw_v1.csv",
    ]
    inbox_files = sorted(INBOX_DIR.glob("w5_calibration_J*_completed.csv"))
    assert [p.name for p in inbox_files] == [
        "w5_calibration_J1_completed.csv",
        "w5_calibration_J2_completed.csv",
        "w5_calibration_J3_completed.csv",
    ]
    assert RAW_MANIFEST_PATH.exists()
    assert RECEIPT_DOC_PATH.exists()


def test_cal_sub_02_45_rows_each() -> None:
    """CAL-SUB-02: 45 rows each."""
    for jid in ALLOWED_JUDGES:
        raw_path = RAW_V1_DIR / f"{jid}_w5_calibration_raw_v1.csv"
        with raw_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            assert tuple(reader.fieldnames or ()) == CSV_ALL_COLUMNS
            rows = list(reader)
        assert len(rows) == 45


def test_cal_sub_03_all_three_pass_frozen_validator() -> None:
    """CAL-SUB-03: All three pass frozen submission validator."""
    for jid in ALLOWED_JUDGES:
        raw_path = RAW_V1_DIR / f"{jid}_w5_calibration_raw_v1.csv"
        inbox_path = INBOX_DIR / f"w5_calibration_{jid}_completed.csv"

        assert validator_cli_main(["--package", str(raw_path)]) == 0
        assert validator_cli_main(["--package", str(inbox_path)]) == 0

        sub_doc = load_csv_package_as_submission_dict(raw_path, validate_empty_package=False)
        res = validate_calibration_submission(sub_doc, validate_empty_package=False)
        assert res["status"] == "PASS"
        assert res["mode"] == "COMPLETED_SUBMISSION"
        assert res["judge_id"] == jid
        assert res["total_items"] == 45


def test_cal_sub_04_same_canonical_item_membership() -> None:
    """CAL-SUB-04: Same canonical item membership across J1/J2/J3 and canonical calibration."""
    canonical = load_canonical_calibration()
    canonical_membership = {
        (sc["scenario_id"], it["judge_item_id"], it["place_id"])
        for sc in canonical["scenarios"]
        for it in sc["items"]
    }
    assert len(canonical_membership) == 45

    for jid in ALLOWED_JUDGES:
        raw_path = RAW_V1_DIR / f"{jid}_w5_calibration_raw_v1.csv"
        sub_doc = load_csv_package_as_submission_dict(raw_path, validate_empty_package=False)
        sub_membership = {
            (sc["scenario_id"], it["judge_item_id"], it["place_id"])
            for sc in sub_doc["scenarios"]
            for it in sc["items"]
        }
        assert sub_membership == canonical_membership


def test_cal_sub_05_no_duplicate_item_per_judge() -> None:
    """CAL-SUB-05: No duplicate item per judge."""
    for jid in ALLOWED_JUDGES:
        raw_path = RAW_V1_DIR / f"{jid}_w5_calibration_raw_v1.csv"
        with raw_path.open("r", encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        item_ids = [r["judge_item_id"] for r in rows]
        place_ids = [r["place_id"] for r in rows]
        assert len(item_ids) == 45
        assert len(set(item_ids)) == 45
        assert len(set(place_ids)) == 45


def test_cal_sub_06_all_labels_populated() -> None:
    """CAL-SUB-06: All labels populated in J1/J2/J3 submissions."""
    for jid in ALLOWED_JUDGES:
        raw_path = RAW_V1_DIR / f"{jid}_w5_calibration_raw_v1.csv"
        with raw_path.open("r", encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        for r in rows:
            assert r["label"] != ""
            assert r["label"].strip() != ""


def test_cal_sub_07_labels_strictly_valid_under_frozen_semantics() -> None:
    """CAL-SUB-07: Labels strictly in {0,1,2,NA} under frozen type semantics."""
    for jid in ALLOWED_JUDGES:
        raw_path = RAW_V1_DIR / f"{jid}_w5_calibration_raw_v1.csv"
        sub_doc = load_csv_package_as_submission_dict(raw_path, validate_empty_package=False)
        for sc in sub_doc["scenarios"]:
            for it in sc["items"]:
                lbl = it["label"]
                validated = validate_completed_calibration_label(lbl)
                assert validated == lbl
                assert (type(lbl) is int and lbl in {0, 1, 2}) or (
                    type(lbl) is str and lbl == "NA"
                )


def test_cal_sub_08_read_only_context_exactly_frozen() -> None:
    """CAL-SUB-08: Read-only context in raw CSVs exactly matches frozen presentation packages."""
    canonical = load_canonical_calibration()
    for jid in ALLOWED_JUDGES:
        ref_pkg = build_judge_calibration_package(canonical, jid)
        expected_rows = package_to_csv_rows(ref_pkg)

        raw_path = RAW_V1_DIR / f"{jid}_w5_calibration_raw_v1.csv"
        with raw_path.open("r", encoding="utf-8", newline="") as f:
            actual_rows = list(csv.DictReader(f))

        assert len(actual_rows) == len(expected_rows) == 45
        for act, exp in zip(actual_rows, expected_rows, strict=True):
            for col in CSV_READ_ONLY_COLUMNS:
                assert act[col] == exp[col], (
                    f"Read-only column {col!r} mismatch for {jid} item {exp['judge_item_id']}"
                )


def test_cal_sub_09_raw_file_sha256_matches_manifest() -> None:
    """CAL-SUB-09: Raw file SHA256 matches manifest and inbox copy."""
    manifest = _load_json(RAW_MANIFEST_PATH)
    for jid in ALLOWED_JUDGES:
        rec = manifest["judge_records"][jid]
        raw_path = REPO_ROOT / rec["filename"]
        inbox_path = REPO_ROOT / rec["inbox_filename"]

        raw_sha = _sha256_file(raw_path)
        inbox_sha = _sha256_file(inbox_path)
        assert raw_sha == rec["sha256"]
        assert inbox_sha == rec["sha256"]


def test_cal_sub_10_total_judgments_is_135() -> None:
    """CAL-SUB-10: Total judgments = 135."""
    manifest = _load_json(RAW_MANIFEST_PATH)
    assert manifest["items_per_judge"] == 45
    assert manifest["total_human_judgments"] == 135

    total_counted = 0
    for jid in ALLOWED_JUDGES:
        raw_path = RAW_V1_DIR / f"{jid}_w5_calibration_raw_v1.csv"
        sub_doc = load_csv_package_as_submission_dict(raw_path, validate_empty_package=False)
        judge_count = sum(
            1
            for sc in sub_doc["scenarios"]
            for it in sc["items"]
            if it["label"] in {0, 1, 2, "NA"}
        )
        assert judge_count == 45
        assert manifest["judge_records"][jid]["label_count"] == 45
        assert sum(manifest["judge_records"][jid]["label_distribution"].values()) == 45
        total_counted += judge_count

    assert total_counted == 135


def test_cal_sub_11_calibration_only_true() -> None:
    """CAL-SUB-11: calibration_only = true."""
    manifest = _load_json(RAW_MANIFEST_PATH)
    assert manifest["calibration_only"] is True
    assert manifest["status"] == "RAW_SUBMISSIONS_FROZEN"


def test_cal_sub_12_excluded_from_final_metrics_true() -> None:
    """CAL-SUB-12: excluded_from_final_metrics = true."""
    manifest = _load_json(RAW_MANIFEST_PATH)
    assert manifest["excluded_from_final_metrics"] is True


def test_cal_sub_13_human_gt_false() -> None:
    """CAL-SUB-13: human_gt = false."""
    manifest = _load_json(RAW_MANIFEST_PATH)
    assert manifest["human_gt"] is False
    assert manifest["scientific_boundary"]["human_gt_created"] is False

    prereg = _load_json(PREREG_MANIFEST_PATH)
    assert prereg["human_gt_available"] is False


def test_cal_sub_14_no_consensus_or_final_relevance_field_exists() -> None:
    """CAL-SUB-14: No consensus or final_relevance field exists in raw submissions or manifest."""
    manifest = _load_json(RAW_MANIFEST_PATH)
    assert "consensus_labels" not in manifest
    assert "final_relevance" not in manifest
    assert manifest["descriptive_agreement_summary"]["consensus_generated"] is False
    assert manifest["descriptive_agreement_summary"]["disagreement_resolved"] is False

    for jid in ALLOWED_JUDGES:
        raw_path = RAW_V1_DIR / f"{jid}_w5_calibration_raw_v1.csv"
        with raw_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            fields = set(reader.fieldnames or ())
        assert "consensus_label" not in fields
        assert "final_relevance" not in fields
        assert "majority_vote" not in fields


def test_cal_sub_15_no_recommender_metric_result_created() -> None:
    """CAL-SUB-15: No recommender metric result created."""
    manifest = _load_json(RAW_MANIFEST_PATH)
    assert manifest["scientific_boundary"]["recommender_evaluation_performed"] is False
    assert manifest["scientific_boundary"]["scientific_winner"] == "UNKNOWN"

    for forbidden_key in ("ndcg", "precision", "recall", "hitrate", "category_ild", "coverage"):
        assert forbidden_key not in json.dumps(manifest).lower()


def test_cal_sub_16_canonical_calibration_package_unchanged() -> None:
    """CAL-SUB-16: Canonical calibration package unchanged."""
    prereg = _load_json(PREREG_MANIFEST_PATH)
    expected_sha = prereg["artifact_hashes"]["w5_calibration_v1.json"]["sha256"]
    assert (
        _git_blob_sha256("data/evaluation/reca_w5/annotation/w5_calibration_v1.json")
        == expected_sha
    )
    res = subprocess.run(
        ["git", "diff", "--", str(CANONICAL_CALIBRATION_PATH)],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    assert res.stdout.strip() == ""


def test_cal_sub_17_rubric_unchanged() -> None:
    """CAL-SUB-17: Rubric unchanged."""
    prereg = _load_json(PREREG_MANIFEST_PATH)
    expected_sha = prereg["artifact_hashes"]["w5_rubric_v1.md"]["sha256"]
    assert (
        _git_blob_sha256("data/evaluation/reca_w5/annotation/w5_rubric_v1.md")
        == expected_sha
    )
    res = subprocess.run(
        ["git", "diff", "--", str(RUBRIC_PATH)],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    assert res.stdout.strip() == ""


def test_cal_sub_18_primary_pool_unchanged() -> None:
    """CAL-SUB-18: Primary scenarios and candidate pools unchanged."""
    prereg = _load_json(PREREG_MANIFEST_PATH)
    for key in (
        "gomate_places_freeze_v2.json",
        "w5_primary_scenarios_v1.json",
        "w5_thin_diagnostic_scenarios_v1.json",
        "w5_candidate_pool_internal_v1.json",
        "w5_candidate_pool_blinded_v1.json",
    ):
        info = prereg["artifact_hashes"][key]
        assert _git_blob_sha256(info["path"]) == info["sha256"]

    res = subprocess.run(
        [
            "git",
            "diff",
            "--",
            str(PRIMARY_SCENARIOS_PATH),
            str(INTERNAL_POOL_PATH),
            str(BLINDED_POOL_PATH),
        ],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    assert res.stdout.strip() == ""


def test_cal_sub_19_r8b_remains_method_retained() -> None:
    """CAL-SUB-19: R8B remains METHOD_RETAINED."""
    r8b = _load_json(R8B_JSON_PATH)
    assert r8b["final_method_decision"] == "METHOD_RETAINED"
    assert r8b["status"] == "CLOSED_WITHOUT_EXTERNAL_REPORT"


def test_cal_sub_20_duplicate_policy_remains_closed_no_impact() -> None:
    """CAL-SUB-20: Duplicate policy remains CLOSED_NO_PRIMARY_EVAL_IMPACT."""
    gate = _load_json(DUP_GATE_PATH)
    assert gate["duplicate_policy_status"] == "CLOSED_NO_PRIMARY_EVAL_IMPACT"
    assert gate["status"] == "PASS"
