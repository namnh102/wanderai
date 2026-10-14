"""Tests for W5 Human Calibration Operational Readiness (W5-CAL-OPS-PREP-01 & FIX-01).

Covers required tests CAL-OPS-01 through CAL-OPS-45:
- CAL-OPS-01: Exactly 3 judge packages exist: J1/J2/J3.
- CAL-OPS-02: Each judge package contains exactly 45 items.
- CAL-OPS-03: J1/J2/J3 contain identical canonical item membership.
- CAL-OPS-04: Independent deterministic presentation order differs for at least two judge packages.
- CAL-OPS-05: Presentation ordering is deterministic.
- CAL-OPS-06: Calibration scenarios are exactly: CAL-HN-01, CAL-DN-01, CAL-HL-01.
- CAL-OPS-07: Calibration scenario overlap with primary = 0.
- CAL-OPS-08: Calibration place_id overlap with primary pool = 0.
- CAL-OPS-09: All labels are null.
- CAL-OPS-10: All judge_note fields are null.
- CAL-OPS-11: No model/rank/score/strategy/control leakage.
- CAL-OPS-12: Each CSV membership/order matches corresponding JSON.
- CAL-OPS-13: Empty-package validation PASS.
- CAL-OPS-14: Completed validator rejects missing item.
- CAL-OPS-15: Completed validator rejects extra item.
- CAL-OPS-16: Completed validator rejects duplicate item.
- CAL-OPS-17: Invalid labels rejected.
- CAL-OPS-18: True/False rejected.
- CAL-OPS-19: Numeric-string labels rejected.
- CAL-OPS-20: Version mismatch rejected.
- CAL-OPS-21: Canonical w5_calibration_v1.json unchanged.
- CAL-OPS-22: Primary scenarios/pools unchanged.
- CAL-OPS-23: W5-RUBRIC-V1 unchanged.
- CAL-OPS-24: Human judgment count remains 0.
- CAL-OPS-25: R8B artifact remains: METHOD_RETAINED, CLOSED_WITHOUT_EXTERNAL_REPORT.
- CAL-OPS-26: Duplicate policy remains: CLOSED_NO_PRIMARY_EVAL_IMPACT.
- CAL-OPS-27: JSON completed submission rejects modified name.
- CAL-OPS-28: JSON rejects modified category.
- CAL-OPS-29: JSON rejects modified destination.
- CAL-OPS-30: JSON rejects modified declared_interests.
- CAL-OPS-31: JSON rejects modified factual_context address.
- CAL-OPS-32: JSON rejects modified coordinate.
- CAL-OPS-33: JSON rejects modified OSM factual tag/source.
- CAL-OPS-34: JSON rejects modified global_presentation_index.
- CAL-OPS-35: JSON rejects missing factual_context.
- CAL-OPS-36: CSV rejects modified read-only name.
- CAL-OPS-37: CSV rejects modified address.
- CAL-OPS-38: CSV rejects modified coordinate.
- CAL-OPS-39: CSV rejects modified declared_interests.
- CAL-OPS-40: CSV rejects modified OSM tags/source.
- CAL-OPS-41: CSV still permits editing ONLY label and judge_note.
- CAL-OPS-42: Submission contract states exact frozen read-only-context policy.
- CAL-OPS-43: Operations doc does NOT define .80/.67 as an automatic calibration PASS/FAIL gate.
- CAL-OPS-44: Operations doc routes post-submission decision to W5-CAL-REVIEW + RUBRIC-FREEZE.
- CAL-OPS-45: external_help_used remains null in template and operational wording requires truthful recording rather than forced false.
"""

from __future__ import annotations

import copy
import csv
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from scripts.validate_w5_calibration_submission import (
    ALLOWED_JUDGES,
    CALIBRATION_OPS_DIR,
    CANONICAL_CALIBRATION_PATH,
    CSV_ALL_COLUMNS,
    FORBIDDEN_LEAKAGE_KEYS,
    REQUIRED_ATTESTATION_STATEMENTS,
    build_judge_calibration_package,
    load_canonical_calibration,
    load_csv_package_as_submission_dict,
    main as validator_cli_main,
    package_to_csv_rows,
    validate_calibration_submission,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = REPO_ROOT / "data" / "evaluation" / "reca_w5"
ANNOTATION_DIR = EVAL_DIR / "annotation"

PRIMARY_SCENARIOS_PATH = EVAL_DIR / "w5_primary_scenarios_v1.json"
BLINDED_POOL_PATH = EVAL_DIR / "w5_candidate_pool_blinded_v1.json"
INTERNAL_POOL_PATH = EVAL_DIR / "w5_candidate_pool_internal_v1.json"
RUBRIC_PATH = ANNOTATION_DIR / "w5_rubric_v1.md"
PREREG_MANIFEST_PATH = EVAL_DIR / "rec_eval_01_prereg_manifest_v1.json"
R8B_JSON_PATH = EVAL_DIR / "r8b_contingency_method_decision_v1.json"
DUP_GATE_PATH = EVAL_DIR / "w5_duplicate_gate_result_v1.json"
SESSION_LOG_TEMPLATE_PATH = (
    CALIBRATION_OPS_DIR / "w5_calibration_session_log_template_v1.json"
)
SUBMISSION_CONTRACT_PATH = (
    CALIBRATION_OPS_DIR / "w5_calibration_submission_contract_v1.json"
)
CALIBRATION_OPS_DOC_PATH = REPO_ROOT / "docs" / "research" / "w5_calibration_ops_v1.md"


def _load_json(path: Path) -> Any:
    assert path.exists(), f"Missing file: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def _git_blob_sha256(relpath: str, ref: str = "HEAD") -> str:
    res = subprocess.run(
        ["git", "show", f"{ref}:{relpath}"],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return hashlib.sha256(res.stdout).hexdigest()


def _make_valid_synthetic_completed_fixture(judge_id: str = "J1") -> dict[str, Any]:
    """Build an in-memory synthetic submission purely for validator unit tests."""
    canonical_doc = load_canonical_calibration()
    pkg = build_judge_calibration_package(canonical_doc, judge_id)
    cycle = [0, 1, 2, "NA"]
    idx = 0
    for sc in pkg["scenarios"]:
        for item in sc["items"]:
            item["label"] = cycle[idx % len(cycle)]
            item["judge_note"] = "synthetic test note" if item["label"] == "NA" else None
            idx += 1
    return pkg


def _write_csv_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(CSV_ALL_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)


def _make_valid_synthetic_completed_csv_rows(judge_id: str = "J1") -> list[dict[str, str]]:
    """Build in-memory synthetic CSV rows with valid labels/notes for validator unit tests."""
    pkg = _make_valid_synthetic_completed_fixture(judge_id)
    return package_to_csv_rows(pkg)


def test_cal_ops_01_three_judge_packages_exist() -> None:
    """CAL-OPS-01: Exactly 3 judge packages exist: J1/J2/J3."""
    json_files = sorted(CALIBRATION_OPS_DIR.glob("w5_calibration_J*_v1.json"))
    csv_files = sorted(CALIBRATION_OPS_DIR.glob("w5_calibration_J*_v1.csv"))
    assert [p.name for p in json_files] == [
        "w5_calibration_J1_v1.json",
        "w5_calibration_J2_v1.json",
        "w5_calibration_J3_v1.json",
    ]
    assert [p.name for p in csv_files] == [
        "w5_calibration_J1_v1.csv",
        "w5_calibration_J2_v1.csv",
        "w5_calibration_J3_v1.csv",
    ]
    assert SESSION_LOG_TEMPLATE_PATH.exists()
    assert CALIBRATION_OPS_DOC_PATH.exists()

    tpl = _load_json(SESSION_LOG_TEMPLATE_PATH)
    assert tpl["judge_id"] is None
    assert tpl["started_at"] is None
    assert tpl["completed_at"] is None
    assert tpl["submission_sha256"] is None
    assert tpl["independence_attestation"] is None
    assert tpl["external_help_used"] is None
    assert tpl["issues_reported"] is None
    assert tpl["discussion_started"] is False

    doc_text = CALIBRATION_OPS_DOC_PATH.read_text(encoding="utf-8")
    for statement in REQUIRED_ATTESTATION_STATEMENTS:
        assert statement in doc_text


def test_cal_ops_02_each_package_has_45_items() -> None:
    """CAL-OPS-02: Each judge package contains exactly 45 items."""
    for jid in ALLOWED_JUDGES:
        pkg = _load_json(CALIBRATION_OPS_DIR / f"w5_calibration_{jid}_v1.json")
        assert pkg["judge_id"] == jid
        assert pkg["scenario_count"] == 3
        assert pkg["total_items"] == 45
        flat_items = [it for sc in pkg["scenarios"] for it in sc["items"]]
        assert len(flat_items) == 45
        for sc in pkg["scenarios"]:
            assert sc["item_count"] == 15
            assert len(sc["items"]) == 15


def test_cal_ops_03_identical_canonical_membership() -> None:
    """CAL-OPS-03: J1/J2/J3 contain identical canonical item membership."""
    canonical = load_canonical_calibration()
    canonical_membership = {
        (sc["scenario_id"], it["judge_item_id"], it["place_id"])
        for sc in canonical["scenarios"]
        for it in sc["items"]
    }
    assert len(canonical_membership) == 45

    for jid in ALLOWED_JUDGES:
        pkg = _load_json(CALIBRATION_OPS_DIR / f"w5_calibration_{jid}_v1.json")
        pkg_membership = {
            (sc["scenario_id"], it["judge_item_id"], it["place_id"])
            for sc in pkg["scenarios"]
            for it in sc["items"]
        }
        assert pkg_membership == canonical_membership


def test_cal_ops_04_independent_presentation_order_differs() -> None:
    """CAL-OPS-04: Independent deterministic presentation order differs across judge packages."""
    orders: dict[str, list[str]] = {}
    for jid in ALLOWED_JUDGES:
        pkg = _load_json(CALIBRATION_OPS_DIR / f"w5_calibration_{jid}_v1.json")
        orders[jid] = [it["judge_item_id"] for sc in pkg["scenarios"] for it in sc["items"]]

    assert orders["J1"] != orders["J2"]
    assert orders["J1"] != orders["J3"]
    assert orders["J2"] != orders["J3"]


def test_cal_ops_05_presentation_ordering_is_deterministic() -> None:
    """CAL-OPS-05: Presentation ordering is deterministic."""
    canonical = load_canonical_calibration()
    for jid in ALLOWED_JUDGES:
        on_disk = _load_json(CALIBRATION_OPS_DIR / f"w5_calibration_{jid}_v1.json")
        recomputed_1 = build_judge_calibration_package(canonical, jid)
        recomputed_2 = build_judge_calibration_package(canonical, jid)
        assert recomputed_1 == recomputed_2
        assert on_disk == recomputed_1


def test_cal_ops_06_calibration_scenarios_exact() -> None:
    """CAL-OPS-06: Calibration scenarios are exactly CAL-HN-01, CAL-DN-01, CAL-HL-01."""
    for jid in ALLOWED_JUDGES:
        pkg = _load_json(CALIBRATION_OPS_DIR / f"w5_calibration_{jid}_v1.json")
        sc_ids = [sc["scenario_id"] for sc in pkg["scenarios"]]
        assert sc_ids == ["CAL-HN-01", "CAL-DN-01", "CAL-HL-01"]
        assert pkg["track"] == "CALIBRATION_ONLY"
        assert pkg["excluded_from_final_metrics"] is True


def test_cal_ops_07_scenario_overlap_with_primary_zero() -> None:
    """CAL-OPS-07: Calibration scenario overlap with primary = 0."""
    primary_scenarios = _load_json(PRIMARY_SCENARIOS_PATH)
    primary_ids = {sc["scenario_id"] for sc in primary_scenarios}
    assert len(primary_ids) == 30

    for jid in ALLOWED_JUDGES:
        pkg = _load_json(CALIBRATION_OPS_DIR / f"w5_calibration_{jid}_v1.json")
        cal_ids = {sc["scenario_id"] for sc in pkg["scenarios"]}
        assert len(cal_ids & primary_ids) == 0


def test_cal_ops_08_place_id_overlap_with_primary_pool_zero() -> None:
    """CAL-OPS-08: Calibration place_id overlap with primary pool = 0."""
    blinded_pool = _load_json(BLINDED_POOL_PATH)
    primary_place_ids = {
        it["place_id"] for sc in blinded_pool for it in sc["items"]
    }
    assert len(primary_place_ids) == 255

    for jid in ALLOWED_JUDGES:
        pkg = _load_json(CALIBRATION_OPS_DIR / f"w5_calibration_{jid}_v1.json")
        cal_place_ids = {
            it["place_id"] for sc in pkg["scenarios"] for it in sc["items"]
        }
        assert len(cal_place_ids) == 45
        assert len(cal_place_ids & primary_place_ids) == 0


def test_cal_ops_09_all_labels_are_null() -> None:
    """CAL-OPS-09: All labels are null in JSON and blank in CSV."""
    for jid in ALLOWED_JUDGES:
        pkg = _load_json(CALIBRATION_OPS_DIR / f"w5_calibration_{jid}_v1.json")
        for sc in pkg["scenarios"]:
            for it in sc["items"]:
                assert it["label"] is None

        csv_path = CALIBRATION_OPS_DIR / f"w5_calibration_{jid}_v1.csv"
        with csv_path.open("r", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                assert row["label"] == ""


def test_cal_ops_10_all_judge_notes_are_null() -> None:
    """CAL-OPS-10: All judge_note fields are null in JSON and blank in CSV."""
    for jid in ALLOWED_JUDGES:
        pkg = _load_json(CALIBRATION_OPS_DIR / f"w5_calibration_{jid}_v1.json")
        for sc in pkg["scenarios"]:
            for it in sc["items"]:
                assert it["judge_note"] is None

        csv_path = CALIBRATION_OPS_DIR / f"w5_calibration_{jid}_v1.csv"
        with csv_path.open("r", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                assert row["judge_note"] == ""


def test_cal_ops_11_no_model_rank_score_strategy_control_leakage() -> None:
    """CAL-OPS-11: No model/rank/score/strategy/control/metadata_sufficiency leakage."""
    for jid in ALLOWED_JUDGES:
        pkg = _load_json(CALIBRATION_OPS_DIR / f"w5_calibration_{jid}_v1.json")
        for sc in pkg["scenarios"]:
            assert not (set(sc.keys()) & FORBIDDEN_LEAKAGE_KEYS)
            for it in sc["items"]:
                assert not (set(it.keys()) & FORBIDDEN_LEAKAGE_KEYS)
                fctx = it.get("factual_context", {})
                assert not (set(fctx.keys()) & FORBIDDEN_LEAKAGE_KEYS)

    leaked = _make_valid_synthetic_completed_fixture("J1")
    leaked["scenarios"][0]["items"][0]["rank"] = 1
    with pytest.raises(ValueError, match="Forbidden leakage fields"):
        validate_calibration_submission(leaked)


def test_cal_ops_12_csv_membership_and_order_match_json() -> None:
    """CAL-OPS-12: Each CSV membership/order matches corresponding JSON."""
    for jid in ALLOWED_JUDGES:
        pkg = _load_json(CALIBRATION_OPS_DIR / f"w5_calibration_{jid}_v1.json")
        json_items = [
            (
                it["judge_id"],
                it["scenario_id"],
                it["presentation_index"],
                it["global_presentation_index"],
                it["calibration_item_id"],
                it["judge_item_id"],
                it["place_id"],
                it["name"],
                it["category"],
            )
            for sc in pkg["scenarios"]
            for it in sc["items"]
        ]

        csv_path = CALIBRATION_OPS_DIR / f"w5_calibration_{jid}_v1.csv"
        with csv_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            assert tuple(reader.fieldnames or ()) == CSV_ALL_COLUMNS
            rows = list(reader)

        assert len(rows) == 45
        csv_items = [
            (
                r["judge_id"],
                r["scenario_id"],
                int(r["presentation_index"]),
                int(r["global_presentation_index"]),
                r["calibration_item_id"],
                r["judge_item_id"],
                r["place_id"],
                r["name"],
                r["category"],
            )
            for r in rows
        ]
        assert csv_items == json_items


def test_cal_ops_13_empty_package_validation_pass() -> None:
    """CAL-OPS-13: Empty-package validation PASS on all J1/J2/J3 JSON and CSV packages."""
    for jid in ALLOWED_JUDGES:
        json_path = CALIBRATION_OPS_DIR / f"w5_calibration_{jid}_v1.json"
        csv_path = CALIBRATION_OPS_DIR / f"w5_calibration_{jid}_v1.csv"

        assert (
            validator_cli_main(
                ["--package", str(json_path), "--validate-empty-package"]
            )
            == 0
        )
        assert (
            validator_cli_main(
                ["--package", str(csv_path), "--validate-empty-package"]
            )
            == 0
        )

        with pytest.raises(ValueError, match="cannot be null"):
            validate_calibration_submission(
                _load_json(json_path), validate_empty_package=False
            )
        with pytest.raises(ValueError, match="cannot be null"):
            validate_calibration_submission(
                load_csv_package_as_submission_dict(csv_path, validate_empty_package=False),
                validate_empty_package=False,
            )


def test_cal_ops_14_completed_validator_rejects_missing_item() -> None:
    """CAL-OPS-14: Completed validator rejects missing item."""
    sub = _make_valid_synthetic_completed_fixture("J1")
    res = validate_calibration_submission(sub)
    assert res["status"] == "PASS"

    sub["scenarios"][0]["items"].pop()
    with pytest.raises(ValueError, match="Missing canonical calibration item"):
        validate_calibration_submission(sub)


def test_cal_ops_15_completed_validator_rejects_extra_item() -> None:
    """CAL-OPS-15: Completed validator rejects extra item."""
    sub = _make_valid_synthetic_completed_fixture("J1")
    extra_item = copy.deepcopy(sub["scenarios"][0]["items"][0])
    extra_item["judge_item_id"] = "CAL-HN-01-J99"
    extra_item["calibration_item_id"] = "CAL-HN-01-J99"
    extra_item["place_id"] = "00000000-0000-0000-0000-000000000099"
    sub["scenarios"][0]["items"].append(extra_item)

    with pytest.raises(ValueError, match="Extra or unknown calibration item"):
        validate_calibration_submission(sub)


def test_cal_ops_16_completed_validator_rejects_duplicate_item() -> None:
    """CAL-OPS-16: Completed validator rejects duplicate item."""
    sub = _make_valid_synthetic_completed_fixture("J1")
    dup_item = copy.deepcopy(sub["scenarios"][0]["items"][0])
    sub["scenarios"][0]["items"][1] = dup_item

    with pytest.raises(ValueError, match="Duplicate calibration item"):
        validate_calibration_submission(sub)


def test_cal_ops_17_invalid_labels_rejected() -> None:
    """CAL-OPS-17: Invalid labels rejected (-1, 3, 1.5, 'na', 'N/A', 'UNKNOWN', '')."""
    for bad_label in [-1, 3, 99, 0.0, 1.0, 1.5, "na", "N/A", "null", "None", "", ["1"], {"v": 1}]:
        sub = _make_valid_synthetic_completed_fixture("J1")
        sub["scenarios"][0]["items"][0]["label"] = bad_label
        with pytest.raises(ValueError):
            validate_calibration_submission(sub)


def test_cal_ops_18_true_false_rejected() -> None:
    """CAL-OPS-18: Boolean True/False rejected."""
    for bad_bool in [True, False]:
        sub = _make_valid_synthetic_completed_fixture("J1")
        sub["scenarios"][0]["items"][0]["label"] = bad_bool
        with pytest.raises(ValueError, match="Boolean label"):
            validate_calibration_submission(sub)


def test_cal_ops_19_numeric_string_labels_rejected() -> None:
    """CAL-OPS-19: Numeric-string labels ('0', '1', '2') rejected."""
    for num_str in ["0", "1", "2", " 1 "]:
        sub = _make_valid_synthetic_completed_fixture("J1")
        sub["scenarios"][0]["items"][0]["label"] = num_str
        with pytest.raises(ValueError, match="Numeric string label"):
            validate_calibration_submission(sub)


def test_cal_ops_20_version_and_judge_mismatch_rejected() -> None:
    """CAL-OPS-20: Version mismatch and wrong judge_id rejected."""
    sub_cal = _make_valid_synthetic_completed_fixture("J1")
    sub_cal["calibration_version"] = "W5-CALIBRATION-V99"
    with pytest.raises(ValueError, match="Invalid calibration_version"):
        validate_calibration_submission(sub_cal)

    sub_rubric = _make_valid_synthetic_completed_fixture("J1")
    sub_rubric["rubric_version"] = "W5-RUBRIC-V1.1"
    with pytest.raises(ValueError, match="Invalid rubric_version"):
        validate_calibration_submission(sub_rubric)

    sub_pres = _make_valid_synthetic_completed_fixture("J1")
    sub_pres["presentation_version"] = "W5-CAL-OPS-V0"
    with pytest.raises(ValueError, match="Invalid presentation_version"):
        validate_calibration_submission(sub_pres)

    sub_judge = _make_valid_synthetic_completed_fixture("J1")
    sub_judge["judge_id"] = "J9"
    with pytest.raises(ValueError, match="Invalid judge_id"):
        validate_calibration_submission(sub_judge)


def test_cal_ops_21_canonical_calibration_unchanged() -> None:
    """CAL-OPS-21: Canonical w5_calibration_v1.json unchanged."""
    manifest = _load_json(PREREG_MANIFEST_PATH)
    expected_sha = manifest["artifact_hashes"]["w5_calibration_v1.json"]["sha256"]
    relpath = "data/evaluation/reca_w5/annotation/w5_calibration_v1.json"
    assert _git_blob_sha256(relpath) == expected_sha

    res = subprocess.run(
        ["git", "diff", "--", str(CANONICAL_CALIBRATION_PATH)],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    assert res.stdout.strip() == ""


def test_cal_ops_22_primary_scenarios_and_pools_unchanged() -> None:
    """CAL-OPS-22: Primary scenarios and candidate pools unchanged."""
    manifest = _load_json(PREREG_MANIFEST_PATH)
    for key in (
        "gomate_places_freeze_v2.json",
        "w5_primary_scenarios_v1.json",
        "w5_thin_diagnostic_scenarios_v1.json",
        "w5_candidate_pool_internal_v1.json",
        "w5_candidate_pool_blinded_v1.json",
    ):
        info = manifest["artifact_hashes"][key]
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


def test_cal_ops_23_rubric_v1_unchanged() -> None:
    """CAL-OPS-23: W5-RUBRIC-V1 unchanged."""
    manifest = _load_json(PREREG_MANIFEST_PATH)
    expected_sha = manifest["artifact_hashes"]["w5_rubric_v1.md"]["sha256"]
    relpath = "data/evaluation/reca_w5/annotation/w5_rubric_v1.md"
    assert _git_blob_sha256(relpath) == expected_sha

    res = subprocess.run(
        ["git", "diff", "--", str(RUBRIC_PATH)],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    assert res.stdout.strip() == ""


def test_cal_ops_24_human_judgment_count_remains_zero() -> None:
    """CAL-OPS-24: Human judgment count remains 0 across all manifests and packages."""
    manifest = _load_json(PREREG_MANIFEST_PATH)
    assert manifest["human_judgments_collected"] == 0
    assert manifest["human_gt_available"] is False
    assert manifest["calibration_status"] == "NOT_STARTED"

    r8b = _load_json(R8B_JSON_PATH)
    assert r8b["human_judgments_collected"] == 0
    assert r8b["human_gt_available"] is False
    assert r8b["calibration_status"] == "NOT_STARTED"


def test_cal_ops_25_r8b_artifact_remains_closed_and_retained() -> None:
    """CAL-OPS-25: R8B artifact remains METHOD_RETAINED and CLOSED_WITHOUT_EXTERNAL_REPORT."""
    r8b = _load_json(R8B_JSON_PATH)
    assert r8b["final_method_decision"] == "METHOD_RETAINED"
    assert r8b["status"] == "CLOSED_WITHOUT_EXTERNAL_REPORT"
    assert r8b["external_report_received"] is False
    assert r8b["external_cross_check_completed"] is False
    assert r8b["external_agreement_claimed"] is False


def test_cal_ops_26_duplicate_policy_remains_closed_no_impact() -> None:
    """CAL-OPS-26: Duplicate policy remains CLOSED_NO_PRIMARY_EVAL_IMPACT."""
    gate = _load_json(DUP_GATE_PATH)
    assert gate["duplicate_policy_status"] == "CLOSED_NO_PRIMARY_EVAL_IMPACT"
    assert gate["status"] == "PASS"

    r8b = _load_json(R8B_JSON_PATH)
    assert r8b["duplicate_policy_status"] == "CLOSED_NO_PRIMARY_EVAL_IMPACT"


def test_cal_ops_27_json_rejects_modified_name() -> None:
    """CAL-OPS-27: JSON completed submission rejects modified name."""
    sub = _make_valid_synthetic_completed_fixture("J1")
    sub["scenarios"][0]["items"][0]["name"] = "Tampered Place Name"
    with pytest.raises(ValueError, match="Read-only field 'name' modified"):
        validate_calibration_submission(sub)


def test_cal_ops_28_json_rejects_modified_category() -> None:
    """CAL-OPS-28: JSON rejects modified category."""
    sub = _make_valid_synthetic_completed_fixture("J1")
    sub["scenarios"][0]["items"][0]["category"] = "tampered_category"
    with pytest.raises(ValueError, match="Read-only field 'category' modified"):
        validate_calibration_submission(sub)


def test_cal_ops_29_json_rejects_modified_destination() -> None:
    """CAL-OPS-29: JSON rejects modified destination."""
    sub = _make_valid_synthetic_completed_fixture("J1")
    sub["scenarios"][0]["items"][0]["destination"] = "da-nang"
    with pytest.raises(ValueError, match="Read-only field 'destination' modified"):
        validate_calibration_submission(sub)

    sub_sc = _make_valid_synthetic_completed_fixture("J1")
    sub_sc["scenarios"][0]["destination"] = "da-nang"
    with pytest.raises(ValueError, match="destination modified"):
        validate_calibration_submission(sub_sc)


def test_cal_ops_30_json_rejects_modified_declared_interests() -> None:
    """CAL-OPS-30: JSON rejects modified declared_interests."""
    sub = _make_valid_synthetic_completed_fixture("J1")
    sub["scenarios"][0]["items"][0]["declared_interests"] = ["beach_island"]
    with pytest.raises(ValueError, match="Read-only field 'declared_interests' modified"):
        validate_calibration_submission(sub)

    sub_sc = _make_valid_synthetic_completed_fixture("J1")
    sub_sc["scenarios"][0]["declared_interests"] = ["beach_island"]
    with pytest.raises(ValueError, match="declared_interests modified"):
        validate_calibration_submission(sub_sc)


def test_cal_ops_31_json_rejects_modified_factual_context_address() -> None:
    """CAL-OPS-31: JSON rejects modified factual_context address."""
    sub = _make_valid_synthetic_completed_fixture("J1")
    sub["scenarios"][0]["items"][0]["factual_context"]["address"] = "999 Fake Street"
    with pytest.raises(ValueError, match="factual_context.address modified"):
        validate_calibration_submission(sub)


def test_cal_ops_32_json_rejects_modified_coordinate() -> None:
    """CAL-OPS-32: JSON rejects modified coordinate."""
    sub_lat = _make_valid_synthetic_completed_fixture("J1")
    sub_lat["scenarios"][0]["items"][0]["factual_context"]["latitude"] = 10.123456
    with pytest.raises(ValueError, match="factual_context.latitude modified"):
        validate_calibration_submission(sub_lat)

    sub_lng = _make_valid_synthetic_completed_fixture("J1")
    sub_lng["scenarios"][0]["items"][0]["factual_context"]["longitude"] = 106.123456
    with pytest.raises(ValueError, match="factual_context.longitude modified"):
        validate_calibration_submission(sub_lng)


def test_cal_ops_33_json_rejects_modified_osm_tag_or_source() -> None:
    """CAL-OPS-33: JSON rejects modified OSM factual tag/source."""
    sub_tag = _make_valid_synthetic_completed_fixture("J1")
    sub_tag["scenarios"][0]["items"][0]["factual_context"]["osm_factual_tags"] = {
        "cuisine": "tampered"
    }
    with pytest.raises(ValueError, match="factual_context.osm_factual_tags modified"):
        validate_calibration_submission(sub_tag)

    sub_src = _make_valid_synthetic_completed_fixture("J1")
    sub_src["scenarios"][0]["items"][0]["factual_context"]["osm_source"] = {
        "source_name": "osm",
        "source_id": "node/999999999",
    }
    with pytest.raises(ValueError, match="factual_context.osm_source modified"):
        validate_calibration_submission(sub_src)


def test_cal_ops_34_json_rejects_modified_global_presentation_index() -> None:
    """CAL-OPS-34: JSON rejects modified global_presentation_index."""
    sub = _make_valid_synthetic_completed_fixture("J1")
    sub["scenarios"][0]["items"][0]["global_presentation_index"] = 99
    with pytest.raises(
        ValueError, match="Read-only field 'global_presentation_index' modified"
    ):
        validate_calibration_submission(sub)


def test_cal_ops_35_json_rejects_missing_factual_context() -> None:
    """CAL-OPS-35: JSON rejects missing factual_context."""
    sub = _make_valid_synthetic_completed_fixture("J1")
    del sub["scenarios"][0]["items"][0]["factual_context"]
    with pytest.raises(ValueError, match="missing required 'factual_context'"):
        validate_calibration_submission(sub)


def test_cal_ops_36_csv_rejects_modified_read_only_name(tmp_path: Path) -> None:
    """CAL-OPS-36: CSV rejects modified read-only name."""
    rows = _make_valid_synthetic_completed_csv_rows("J1")
    rows[0]["name"] = "Tampered CSV Name"
    csv_file = tmp_path / "tampered_name.csv"
    _write_csv_rows(csv_file, rows)

    with pytest.raises(ValueError, match="CSV read-only column 'name' modified"):
        load_csv_package_as_submission_dict(csv_file)


def test_cal_ops_37_csv_rejects_modified_address(tmp_path: Path) -> None:
    """CAL-OPS-37: CSV rejects modified address."""
    rows = _make_valid_synthetic_completed_csv_rows("J1")
    rows[0]["address"] = "Tampered CSV Address"
    csv_file = tmp_path / "tampered_address.csv"
    _write_csv_rows(csv_file, rows)

    with pytest.raises(ValueError, match="CSV read-only column 'address' modified"):
        load_csv_package_as_submission_dict(csv_file)


def test_cal_ops_38_csv_rejects_modified_coordinate(tmp_path: Path) -> None:
    """CAL-OPS-38: CSV rejects modified coordinate."""
    rows = _make_valid_synthetic_completed_csv_rows("J1")
    rows[0]["latitude"] = "12.345678"
    csv_file = tmp_path / "tampered_lat.csv"
    _write_csv_rows(csv_file, rows)

    with pytest.raises(ValueError, match="CSV read-only column 'latitude' modified"):
        load_csv_package_as_submission_dict(csv_file)


def test_cal_ops_39_csv_rejects_modified_declared_interests(tmp_path: Path) -> None:
    """CAL-OPS-39: CSV rejects modified declared_interests."""
    rows = _make_valid_synthetic_completed_csv_rows("J1")
    rows[0]["declared_interests"] = json.dumps(["nature_outdoor"])
    csv_file = tmp_path / "tampered_interests.csv"
    _write_csv_rows(csv_file, rows)

    with pytest.raises(
        ValueError, match="CSV read-only column 'declared_interests' modified"
    ):
        load_csv_package_as_submission_dict(csv_file)


def test_cal_ops_40_csv_rejects_modified_osm_tags_or_source(tmp_path: Path) -> None:
    """CAL-OPS-40: CSV rejects modified OSM tags/source."""
    rows_tags = _make_valid_synthetic_completed_csv_rows("J1")
    rows_tags[0]["osm_factual_tags_json"] = json.dumps({"tourism": "museum"})
    csv_tags = tmp_path / "tampered_tags.csv"
    _write_csv_rows(csv_tags, rows_tags)

    with pytest.raises(
        ValueError, match="CSV read-only column 'osm_factual_tags_json' modified"
    ):
        load_csv_package_as_submission_dict(csv_tags)

    rows_src = _make_valid_synthetic_completed_csv_rows("J1")
    rows_src[0]["osm_source_id"] = "osm:node/123"
    csv_src = tmp_path / "tampered_src.csv"
    _write_csv_rows(csv_src, rows_src)

    with pytest.raises(
        ValueError, match="CSV read-only column 'osm_source_id' modified"
    ):
        load_csv_package_as_submission_dict(csv_src)


def test_cal_ops_41_csv_permits_editing_only_label_and_judge_note(
    tmp_path: Path,
) -> None:
    """CAL-OPS-41: CSV still permits editing ONLY label and judge_note."""
    rows = _make_valid_synthetic_completed_csv_rows("J1")
    csv_file = tmp_path / "valid_completed.csv"
    _write_csv_rows(csv_file, rows)

    loaded = load_csv_package_as_submission_dict(csv_file, validate_empty_package=False)
    res = validate_calibration_submission(loaded, validate_empty_package=False)
    assert res["status"] == "PASS"
    assert res["mode"] == "COMPLETED_SUBMISSION"
    assert validator_cli_main(["--package", str(csv_file)]) == 0


def test_cal_ops_42_submission_contract_states_frozen_read_only_policy() -> None:
    """CAL-OPS-42: Submission contract states exact frozen read-only-context policy."""
    contract = _load_json(SUBMISSION_CONTRACT_PATH)
    assert (
        contract["read_only_context_policy"]
        == "EXACT_MATCH_TO_FROZEN_PRESENTATION_PACKAGE"
    )
    assert contract["editable_fields"] == ["label", "judge_note"]
    assert contract["read_only_context_mutation"] == "REJECT"


def test_cal_ops_43_ops_doc_has_no_unregistered_alpha_auto_gate() -> None:
    """CAL-OPS-43: Operations doc does NOT define .80/.67 as an automatic calibration PASS/FAIL gate."""
    doc_text = CALIBRATION_OPS_DOC_PATH.read_text(encoding="utf-8")
    assert "0.80" not in doc_text
    assert "0.67" not in doc_text
    assert "USABLE_WITH_QUALIFICATION" not in doc_text
    assert "STOP_REVIEW_RUBRIC" not in doc_text


def test_cal_ops_44_ops_doc_routes_post_submission_to_cal_review_and_rubric_freeze() -> None:
    """CAL-OPS-44: Operations doc routes post-submission decision to W5-CAL-REVIEW + RUBRIC-FREEZE."""
    doc_text = CALIBRATION_OPS_DOC_PATH.read_text(encoding="utf-8")
    assert "W5-CAL-REVIEW" in doc_text
    assert "RUBRIC-FREEZE" in doc_text
    assert "CALIBRATION_ONLY" in doc_text


def test_cal_ops_45_external_help_used_template_and_truthful_wording() -> None:
    """CAL-OPS-45: external_help_used remains null in template and wording requires truthful recording."""
    tpl = _load_json(SESSION_LOG_TEMPLATE_PATH)
    assert tpl["external_help_used"] is None

    doc_text = CALIBRATION_OPS_DOC_PATH.read_text(encoding="utf-8").lower()
    assert "truthfully" in doc_text
    assert "external_help_used" in doc_text
    assert "falsify" in doc_text
    assert "w5-cal-review" in doc_text
