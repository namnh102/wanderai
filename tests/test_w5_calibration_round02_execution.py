"""Tests for W5-CAL-R02-EXEC-PREP-01 (Round 02 Safe Human Collection Execution Kit)."""

from __future__ import annotations

import copy
import csv
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from scripts.manage_w5_calibration_round02_execution import (
    DISTRIBUTION_RECEIPT_TEMPLATE_PATH,
    EXECUTION_STATE_TEMPLATE_PATH,
    EXECUTION_TEMPLATES_DIR,
    FORBIDDEN_PRELOCK_OUTPUT_KEYS,
    PRIVATE_INTAKE_DIR,
    ROUND01_INCIDENT_PATH,
    ROUND01_MANIFEST_PATH,
    SUBMISSION_RECEIPT_TEMPLATE_PATH,
    build_blank_judge_attestation_template,
    check_round02_lock_readiness,
    check_round02_readiness,
    validate_round02_submission_and_attestation,
)
from scripts.prepare_w5_calibration_round02 import (
    ALLOWED_JUDGES,
    CALIBRATION_VERSION,
    PRESENTATION_VERSION,
    REQUIRED_ATTESTATION_BOOLEANS,
    ROUND02_CALIBRATION_PATH,
    ROUND02_MANIFEST_PATH,
    ROUND02_PACKAGES_DIR,
    ROUND_ID,
    RUBRIC_VERSION,
    build_round02_judge_package,
    canonical_json_sha256,
    canonical_lf_sha256_file,
    write_csv_lf,
    write_json_lf,
)
from scripts.validate_w5_calibration_submission import (
    CSV_ALL_COLUMNS,
    package_to_csv_rows,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
CLI_SCRIPT = REPO_ROOT / "scripts" / "manage_w5_calibration_round02_execution.py"
EXEC_KIT_DOC_PATH = (
    REPO_ROOT / "docs" / "research" / "w5_calibration_round02_execution_kit_v1.md"
)
JUDGE_HANDOUT_DOC_PATH = (
    REPO_ROOT / "docs" / "research" / "w5_calibration_round02_judge_handout_v1.md"
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _make_synthetic_valid_attestation_dict(judge_id: str) -> dict[str, Any]:
    """Build a synthetic test-only qualifying attestation dictionary."""
    doc = build_blank_judge_attestation_template(judge_id)
    for k, expected_val in REQUIRED_ATTESTATION_BOOLEANS.items():
        doc[k] = expected_val
    doc["completed_at_utc"] = "2026-10-14T15:00:00Z"
    return doc


def _make_synthetic_completed_csv(
    judge_id: str,
    target_path: Path,
    *,
    canonical_doc: dict[str, Any] | None = None,
    label_override_by_index: dict[int, str] | None = None,
    mutate_read_only_col: tuple[int, str, str] | None = None,
) -> Path:
    """Create a synthetic test-only completed CSV fixture for a judge."""
    if canonical_doc is None:
        canonical_doc = _load_json(ROUND02_CALIBRATION_PATH)
    pkg = build_round02_judge_package(canonical_doc, judge_id)
    rows = package_to_csv_rows(pkg)
    cycle = ("0", "1", "2", "NA")
    for idx, row in enumerate(rows):
        row["label"] = cycle[idx % len(cycle)]
        row["judge_note"] = f"synthetic_test_only_fixture_note_{idx + 1}"
    if label_override_by_index:
        for idx, val in label_override_by_index.items():
            rows[idx]["label"] = val
    if mutate_read_only_col:
        r_idx, col_name, new_val = mutate_read_only_col
        rows[r_idx][col_name] = new_val
    write_csv_lf(target_path, CSV_ALL_COLUMNS, rows)
    return target_path


def test_r02_exec_01_check_readiness_passes_on_prepared_not_started() -> None:
    """R02-EXEC-01: check-readiness PASS on current official PREPARED_NOT_STARTED state."""
    res = check_round02_readiness()
    assert res["overall_status"] == "PASS"
    assert res["round_status"] == "PREPARED_NOT_STARTED"
    assert res["actual_human_judgments_collected"] == 0
    assert res["qualifying_independent_human_judgments"] == 0
    assert all(res["checks"].values())
    assert res["reasons"] == []

    # Verify CLI invocation
    proc = subprocess.run(
        [sys.executable, str(CLI_SCRIPT), "check-readiness"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    cli_out = json.loads(proc.stdout)
    assert cli_out["overall_status"] == "PASS"


def test_r02_exec_02_frozen_round02_package_hashes_unchanged() -> None:
    """R02-EXEC-02: frozen Round 02 package hashes remain unchanged."""
    manifest = _load_json(ROUND02_MANIFEST_PATH)
    for key, art in manifest["artifacts"].items():
        p = REPO_ROOT / art["path"]
        assert canonical_lf_sha256_file(p) == art["canonical_lf_sha256"], key
        assert canonical_json_sha256(_load_json(p)) == art["canonical_json_sha256"], key

    for jid in ALLOWED_JUDGES:
        pkg = manifest["judge_packages"][jid]
        jp = REPO_ROOT / pkg["json_path"]
        cp = REPO_ROOT / pkg["csv_path"]
        assert canonical_lf_sha256_file(jp) == pkg["json_canonical_lf_sha256"], jid
        assert (
            canonical_json_sha256(_load_json(jp)) == pkg["json_canonical_object_sha256"]
        ), jid
        assert canonical_lf_sha256_file(cp) == pkg["csv_canonical_lf_sha256"], jid


def test_r02_exec_03_blank_j1_j2_j3_attestations_contain_null_booleans(
    tmp_path: Path,
) -> None:
    """R02-EXEC-03: blank J1/J2/J3 attestations contain null qualification booleans."""
    for jid in ALLOWED_JUDGES:
        committed_tpl_path = (
            EXECUTION_TEMPLATES_DIR
            / f"w5_calibration_round02_{jid}_attestation_template_v1.json"
        )
        assert committed_tpl_path.is_file()
        tpl = _load_json(committed_tpl_path)
        assert tpl["judge_id"] == jid
        assert tpl["round_id"] == ROUND_ID
        assert tpl["calibration_version"] == CALIBRATION_VERSION
        assert tpl["rubric_version"] == RUBRIC_VERSION
        assert tpl["presentation_version"] == PRESENTATION_VERSION
        for key in REQUIRED_ATTESTATION_BOOLEANS:
            assert key in tpl
            assert tpl[key] is None, f"{jid} {key} must be None"
        assert tpl["completed_at_utc"] is None
        for forbidden_pii in ("name", "email", "phone", "contact", "github"):
            assert forbidden_pii not in tpl

    # Also test CLI make-attestation-template
    cli_target = tmp_path / "synthetic_blank_J1_attestation.json"
    subprocess.run(
        [
            sys.executable,
            str(CLI_SCRIPT),
            "make-attestation-template",
            "--judge",
            "J1",
            "--output",
            str(cli_target),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    cli_tpl = _load_json(cli_target)
    for key in REQUIRED_ATTESTATION_BOOLEANS:
        assert cli_tpl[key] is None


def test_r02_exec_04_execution_state_template_does_not_claim_humans_assigned() -> None:
    """R02-EXEC-04: execution-state template does not claim humans assigned."""
    assert EXECUTION_STATE_TEMPLATE_PATH.is_file()
    state = _load_json(EXECUTION_STATE_TEMPLATE_PATH)
    assert state["execution_version"] == "W5-CAL-R02-EXEC-V1"
    assert state["round_id"] == "W5-CAL-ROUND-02"
    assert state["calibration_version"] == "W5-CALIBRATION-V2"
    assert state["status"] == "READY_FOR_HUMAN_ASSIGNMENT"
    assert state["actual_human_roles_assigned"] is False
    assert state["distinct_actual_humans_confirmed"] is False
    assert state["packages_distributed"] is False
    assert state["human_submissions_received"] == 0
    assert state["qualifying_submissions"] == 0
    assert state["all_three_submissions_received"] is False
    assert state["all_three_submissions_qualifying"] is False
    assert state["all_three_submissions_locked"] is False
    assert state["calibration_review_eligible"] is False
    assert state["human_gt"] is False
    assert state["primary_annotation_started"] is False
    assert state["recommender_evaluation_performed"] is False


def test_r02_exec_05_distribution_template_does_not_claim_packages_distributed() -> None:
    """R02-EXEC-05: distribution template does not claim packages distributed."""
    assert DISTRIBUTION_RECEIPT_TEMPLATE_PATH.is_file()
    dist = _load_json(DISTRIBUTION_RECEIPT_TEMPLATE_PATH)
    manifest = _load_json(ROUND02_MANIFEST_PATH)
    assert dist["actual_human_roles_assigned"] is False
    assert dist["distinct_actual_humans_confirmed"] is False
    assert dist["packages_distributed"] is False
    for jid in ALLOWED_JUDGES:
        j_entry = dist["judges"][jid]
        assert j_entry["judge_id"] == jid
        assert j_entry["assigned"] is False
        assert j_entry["distinct_actual_human_confirmed"] is False
        assert j_entry["package_distributed"] is False
        assert (
            j_entry["package_path"] == manifest["judge_packages"][jid]["csv_path"]
        )
        assert (
            j_entry["package_hash"]
            == manifest["judge_packages"][jid]["csv_canonical_lf_sha256"]
        )
        assert j_entry["distribution_timestamp_utc"] is None


def test_r02_exec_06_submission_template_reports_zero_submissions() -> None:
    """R02-EXEC-06: submission template reports 0 submissions."""
    assert SUBMISSION_RECEIPT_TEMPLATE_PATH.is_file()
    sub = _load_json(SUBMISSION_RECEIPT_TEMPLATE_PATH)
    assert sub["all_three_received"] is False
    assert sub["all_three_qualifying"] is False
    assert sub["round_ready_to_lock"] is False
    for jid in ALLOWED_JUDGES:
        j_entry = sub["judges"][jid]
        assert j_entry["judge_id"] == jid
        assert j_entry["submission_received"] is False
        assert j_entry["submission_path"] is None
        assert j_entry["submission_sha256"] is None
        assert j_entry["file_validation_status"] == "NOT_RUN"
        assert j_entry["attestation_validation_status"] == "NOT_RUN"
        assert j_entry["qualification_status"] == "NOT_EVALUATED"
        assert j_entry["received_at_utc"] is None
        assert j_entry["locked"] is False


def test_r02_exec_07_missing_attestation_is_non_qualifying(tmp_path: Path) -> None:
    """R02-EXEC-07: missing attestation => NON_QUALIFYING."""
    sub_csv = _make_synthetic_completed_csv(
        "J1", tmp_path / "synthetic_J1_completed.csv"
    )
    res = validate_round02_submission_and_attestation(
        judge_id="J1",
        submission_path=sub_csv,
        attestation_path=None,
    )
    assert res["file_validation_status"] == "PASS"
    assert res["attestation_validation_status"] == "FAIL"
    assert res["qualification_status"] == "NON_QUALIFYING"


def test_r02_exec_08_ai_use_is_non_qualifying(tmp_path: Path) -> None:
    """R02-EXEC-08: AI use => NON_QUALIFYING."""
    sub_csv = _make_synthetic_completed_csv(
        "J1", tmp_path / "synthetic_J1_completed.csv"
    )
    att = _make_synthetic_valid_attestation_dict("J1")
    att["ai_llm_used_for_label_decisions"] = True
    att_path = tmp_path / "synthetic_J1_att.json"
    write_json_lf(att_path, att)

    res = validate_round02_submission_and_attestation(
        judge_id="J1", submission_path=sub_csv, attestation_path=att_path
    )
    assert res["file_validation_status"] == "PASS"
    assert res["attestation_validation_status"] == "FAIL"
    assert res["qualification_status"] == "NON_QUALIFYING"
    assert any("ai_llm_used_for_label_decisions" in r for r in res["reasons"])


def test_r02_exec_09_external_search_is_non_qualifying(tmp_path: Path) -> None:
    """R02-EXEC-09: external search => NON_QUALIFYING."""
    sub_csv = _make_synthetic_completed_csv(
        "J1", tmp_path / "synthetic_J1_completed.csv"
    )
    att = _make_synthetic_valid_attestation_dict("J1")
    att["external_search_used"] = True
    att_path = tmp_path / "synthetic_J1_att.json"
    write_json_lf(att_path, att)

    res = validate_round02_submission_and_attestation(
        judge_id="J1", submission_path=sub_csv, attestation_path=att_path
    )
    assert res["attestation_validation_status"] == "FAIL"
    assert res["qualification_status"] == "NON_QUALIFYING"
    assert any("external_search_used" in r for r in res["reasons"])


def test_r02_exec_10_prior_label_exposure_is_non_qualifying(tmp_path: Path) -> None:
    """R02-EXEC-10: prior label exposure => NON_QUALIFYING."""
    sub_csv = _make_synthetic_completed_csv(
        "J2", tmp_path / "synthetic_J2_completed.csv"
    )
    for field in (
        "inspected_other_judge_labels_before_submission",
        "exposed_to_other_judge_label_summary_before_submission",
        "direct_label_discussion_before_all_submissions_locked",
    ):
        att = _make_synthetic_valid_attestation_dict("J2")
        att[field] = True
        att_path = tmp_path / f"synthetic_J2_att_{field}.json"
        write_json_lf(att_path, att)
        res = validate_round02_submission_and_attestation(
            judge_id="J2", submission_path=sub_csv, attestation_path=att_path
        )
        assert res["attestation_validation_status"] == "FAIL"
        assert res["qualification_status"] == "NON_QUALIFYING"
        assert any(field in r for r in res["reasons"])


def test_r02_exec_11_own_label_publication_before_lock_is_non_qualifying(
    tmp_path: Path,
) -> None:
    """R02-EXEC-11: own-label publication before lock => NON_QUALIFYING."""
    sub_csv = _make_synthetic_completed_csv(
        "J1", tmp_path / "synthetic_J1_completed.csv"
    )
    att = _make_synthetic_valid_attestation_dict("J1")
    att[
        "published_or_shared_own_labels_or_summary_before_all_submissions_locked"
    ] = True
    att_path = tmp_path / "synthetic_J1_att.json"
    write_json_lf(att_path, att)

    res = validate_round02_submission_and_attestation(
        judge_id="J1", submission_path=sub_csv, attestation_path=att_path
    )
    assert res["attestation_validation_status"] == "FAIL"
    assert res["qualification_status"] == "NON_QUALIFYING"
    assert any(
        "published_or_shared_own_labels_or_summary_before_all_submissions_locked" in r
        for r in res["reasons"]
    )


def test_r02_exec_12_non_private_submission_is_non_qualifying(tmp_path: Path) -> None:
    """R02-EXEC-12: non-private submission => NON_QUALIFYING."""
    sub_csv = _make_synthetic_completed_csv(
        "J3", tmp_path / "synthetic_J3_completed.csv"
    )
    att = _make_synthetic_valid_attestation_dict("J3")
    att["submitted_privately_to_project_owner"] = False
    att_path = tmp_path / "synthetic_J3_att.json"
    write_json_lf(att_path, att)

    res = validate_round02_submission_and_attestation(
        judge_id="J3", submission_path=sub_csv, attestation_path=att_path
    )
    assert res["attestation_validation_status"] == "FAIL"
    assert res["qualification_status"] == "NON_QUALIFYING"
    assert any("submitted_privately_to_project_owner" in r for r in res["reasons"])


def test_r02_exec_13_modified_read_only_context_rejected(tmp_path: Path) -> None:
    """R02-EXEC-13: modified read-only context => REJECT."""
    sub_csv = _make_synthetic_completed_csv(
        "J1",
        tmp_path / "synthetic_J1_tampered.csv",
        mutate_read_only_col=(0, "name", "Tampered Place Name"),
    )
    att_path = tmp_path / "synthetic_J1_att.json"
    write_json_lf(att_path, _make_synthetic_valid_attestation_dict("J1"))

    res = validate_round02_submission_and_attestation(
        judge_id="J1", submission_path=sub_csv, attestation_path=att_path
    )
    assert res["file_validation_status"] == "REJECT"
    assert res["qualification_status"] == "NON_QUALIFYING"


def test_r02_exec_14_missing_one_of_45_labels_rejected(tmp_path: Path) -> None:
    """R02-EXEC-14: missing one of 45 labels => REJECT."""
    sub_csv = _make_synthetic_completed_csv(
        "J1",
        tmp_path / "synthetic_J1_blank_label.csv",
        label_override_by_index={12: ""},
    )
    att_path = tmp_path / "synthetic_J1_att.json"
    write_json_lf(att_path, _make_synthetic_valid_attestation_dict("J1"))

    res = validate_round02_submission_and_attestation(
        judge_id="J1", submission_path=sub_csv, attestation_path=att_path
    )
    assert res["file_validation_status"] == "REJECT"
    assert res["qualification_status"] == "NON_QUALIFYING"


def test_r02_exec_15_invalid_label_rejected(tmp_path: Path) -> None:
    """R02-EXEC-15: invalid label => REJECT."""
    att_path = tmp_path / "synthetic_J1_att.json"
    write_json_lf(att_path, _make_synthetic_valid_attestation_dict("J1"))

    for idx, bad_label in enumerate(("3", "-1", "1.0", "na", "N/A", "true", "false")):
        sub_csv = _make_synthetic_completed_csv(
            "J1",
            tmp_path / f"synthetic_J1_bad_{idx}.csv",
            label_override_by_index={0: bad_label},
        )
        res = validate_round02_submission_and_attestation(
            judge_id="J1", submission_path=sub_csv, attestation_path=att_path
        )
        assert res["file_validation_status"] == "REJECT", f"Expected REJECT for {bad_label!r}"
        assert res["qualification_status"] == "NON_QUALIFYING"


def test_r02_exec_16_three_synthetically_valid_fixtures_ready_to_lock(
    tmp_path: Path,
) -> None:
    """R02-EXEC-16: three synthetically valid submission+attestation fixtures => READY_TO_LOCK."""
    intake = tmp_path / "synthetic_intake_ready"
    intake.mkdir(parents=True, exist_ok=True)
    canonical_doc = _load_json(ROUND02_CALIBRATION_PATH)

    for jid in ALLOWED_JUDGES:
        _make_synthetic_completed_csv(
            jid,
            intake / f"w5_calibration_round02_{jid}_completed.csv",
            canonical_doc=canonical_doc,
        )
        write_json_lf(
            intake / f"w5_calibration_round02_{jid}_attestation.json",
            _make_synthetic_valid_attestation_dict(jid),
        )

    res = check_round02_lock_readiness(intake)
    assert res["lock_readiness_status"] == "READY_TO_LOCK"
    assert res["round_ready_to_lock"] is True
    assert res["all_three_received"] is True
    assert res["all_three_qualifying"] is True
    assert res["qualifying_submissions_count"] == 3
    assert res["duplicate_judge_ids_detected"] is False
    assert res["reasons"] == []
    assert all(
        v is False for v in res["scientific_side_effects"].values()
    )


def test_r02_exec_17_two_valid_and_one_invalid_not_ready_to_lock(
    tmp_path: Path,
) -> None:
    """R02-EXEC-17: 2 valid + 1 invalid => NOT_READY_TO_LOCK."""
    intake = tmp_path / "synthetic_intake_2valid_1invalid"
    intake.mkdir(parents=True, exist_ok=True)
    canonical_doc = _load_json(ROUND02_CALIBRATION_PATH)

    for jid in ALLOWED_JUDGES:
        _make_synthetic_completed_csv(
            jid,
            intake / f"w5_calibration_round02_{jid}_completed.csv",
            canonical_doc=canonical_doc,
        )
        att = _make_synthetic_valid_attestation_dict(jid)
        if jid == "J3":
            att["ai_llm_used_for_label_decisions"] = True
        write_json_lf(
            intake / f"w5_calibration_round02_{jid}_attestation.json",
            att,
        )

    res = check_round02_lock_readiness(intake)
    assert res["lock_readiness_status"] == "NOT_READY_TO_LOCK"
    assert res["round_ready_to_lock"] is False
    assert res["all_three_qualifying"] is False
    assert res["qualifying_submissions_count"] == 2
    assert res["judge_summaries"]["J3"]["qualification_status"] == "NON_QUALIFYING"


def test_r02_exec_18_duplicate_judge_ids_not_ready_to_lock(tmp_path: Path) -> None:
    """R02-EXEC-18: duplicate judge IDs => NOT_READY_TO_LOCK."""
    intake = tmp_path / "synthetic_intake_dup_judge"
    intake.mkdir(parents=True, exist_ok=True)
    canonical_doc = _load_json(ROUND02_CALIBRATION_PATH)

    # Two J1 submissions and one J2 submission (missing J3, duplicate J1)
    _make_synthetic_completed_csv(
        "J1", intake / "sub_a_J1.csv", canonical_doc=canonical_doc
    )
    _make_synthetic_completed_csv(
        "J1", intake / "sub_b_J1_copy.csv", canonical_doc=canonical_doc
    )
    _make_synthetic_completed_csv(
        "J2", intake / "sub_c_J2.csv", canonical_doc=canonical_doc
    )
    write_json_lf(
        intake / "att_J1.json", _make_synthetic_valid_attestation_dict("J1")
    )
    write_json_lf(
        intake / "att_J2.json", _make_synthetic_valid_attestation_dict("J2")
    )

    res = check_round02_lock_readiness(intake)
    assert res["lock_readiness_status"] == "NOT_READY_TO_LOCK"
    assert res["round_ready_to_lock"] is False
    assert res["duplicate_judge_ids_detected"] is True
    assert any("duplicate_judge_ids_detected" in r for r in res["reasons"])


def test_r02_exec_19_no_labels_or_statistics_leaked_by_status_output(
    tmp_path: Path,
) -> None:
    """R02-EXEC-19: no labels/statistics leaked by pre-lock status output."""
    intake = tmp_path / "synthetic_intake_privacy"
    intake.mkdir(parents=True, exist_ok=True)
    canonical_doc = _load_json(ROUND02_CALIBRATION_PATH)

    sub_j1 = _make_synthetic_completed_csv(
        "J1",
        intake / "w5_calibration_round02_J1_completed.csv",
        canonical_doc=canonical_doc,
    )
    att_j1 = intake / "w5_calibration_round02_J1_attestation.json"
    write_json_lf(att_j1, _make_synthetic_valid_attestation_dict("J1"))

    val_res = validate_round02_submission_and_attestation(
        judge_id="J1", submission_path=sub_j1, attestation_path=att_j1
    )
    lock_res = check_round02_lock_readiness(intake)

    def _assert_no_forbidden_keys(obj: Any) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                assert k not in FORBIDDEN_PRELOCK_OUTPUT_KEYS, f"Leaked key: {k}"
                _assert_no_forbidden_keys(v)
        elif isinstance(obj, list):
            for item in obj:
                _assert_no_forbidden_keys(item)

    _assert_no_forbidden_keys(val_res)
    _assert_no_forbidden_keys(lock_res)
    serialized = json.dumps(val_res) + json.dumps(lock_res)
    assert "synthetic_test_only_fixture_note" not in serialized


def test_r02_exec_20_round01_remains_invalidated_for_protocol() -> None:
    """R02-EXEC-20: Round 01 remains INVALIDATED_FOR_PROTOCOL."""
    r1_m = _load_json(ROUND01_MANIFEST_PATH)
    r1_i = _load_json(ROUND01_INCIDENT_PATH)
    assert r1_m["round_status"] == "INVALIDATED_FOR_PROTOCOL"
    assert r1_m["qualifying_independent_human_judgments"] == 0
    assert r1_i["round_status"] == "INVALIDATED_FOR_PROTOCOL"
    assert r1_i["scientific_use"] == "FORENSIC_NON_QUALIFYING_EVIDENCE_ONLY"


def test_r02_exec_21_human_gt_remains_false() -> None:
    """R02-EXEC-21: human_gt remains false."""
    manifest = _load_json(ROUND02_MANIFEST_PATH)
    state = _load_json(EXECUTION_STATE_TEMPLATE_PATH)
    assert manifest["human_gt"] is False
    assert state["human_gt"] is False


def test_r02_exec_22_primary_annotation_started_remains_false() -> None:
    """R02-EXEC-22: primary_annotation_started remains false."""
    manifest = _load_json(ROUND02_MANIFEST_PATH)
    state = _load_json(EXECUTION_STATE_TEMPLATE_PATH)
    assert manifest["primary_annotation_started"] is False
    assert state["primary_annotation_started"] is False


def test_r02_exec_23_recommender_evaluation_performed_remains_false() -> None:
    """R02-EXEC-23: recommender_evaluation_performed remains false."""
    manifest = _load_json(ROUND02_MANIFEST_PATH)
    state = _load_json(EXECUTION_STATE_TEMPLATE_PATH)
    assert manifest["recommender_evaluation_performed"] is False
    assert state["recommender_evaluation_performed"] is False

    # Also verify private_intake firewall and docs exist with LF line endings
    assert (PRIVATE_INTAKE_DIR / ".gitignore").is_file()
    assert (PRIVATE_INTAKE_DIR / "README.md").is_file()
    readme_text = (PRIVATE_INTAKE_DIR / "README.md").read_text(encoding="utf-8")
    assert "THIS DIRECTORY IS LOCAL PRIVATE INTAKE." in readme_text
    assert EXEC_KIT_DOC_PATH.is_file()
    assert JUDGE_HANDOUT_DOC_PATH.is_file()
    for p in (
        PRIVATE_INTAKE_DIR / ".gitignore",
        PRIVATE_INTAKE_DIR / "README.md",
        EXEC_KIT_DOC_PATH,
        JUDGE_HANDOUT_DOC_PATH,
        EXECUTION_STATE_TEMPLATE_PATH,
        DISTRIBUTION_RECEIPT_TEMPLATE_PATH,
        SUBMISSION_RECEIPT_TEMPLATE_PATH,
    ):
        assert b"\r\n" not in p.read_bytes(), f"CRLF detected in {p}"
