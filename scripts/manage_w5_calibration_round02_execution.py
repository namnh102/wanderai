"""Safe human collection execution manager and readiness/lock gate for W5 Calibration Round 02.

Implements W5-CAL-R02-EXEC-PREP-01:
- Reuses frozen scientific validation logic from scripts/prepare_w5_calibration_round02.py
  and scripts/validate_w5_calibration_submission.py without duplicating label semantics.
- Provides read-only / validation-oriented CLI commands:
  1. check-readiness
  2. make-attestation-template
  3. validate-submission
  4. check-lock-readiness
- Enforces the Round 02 privacy and anti-contamination firewall: never prints or returns
  label values, example ratings, label distributions, per-category label counts,
  disagreement counts, or agreement statistics.
- Never calculates Krippendorff's alpha, aggregates labels, adjudicates, creates HUMAN-GT,
  commits files, modifies the Round 02 manifest, or starts CAL-REVIEW.
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.prepare_w5_calibration_round02 import (  # noqa: E402
    CALIBRATION_VERSION,
    PRESENTATION_VERSION,
    REQUIRED_ATTESTATION_BOOLEANS,
    ROUND02_ATTESTATION_TEMPLATE_PATH,
    ROUND02_CALIBRATION_PATH,
    ROUND02_MANIFEST_PATH,
    ROUND02_OPS_DIR,
    ROUND02_ROLE_CONTRACT_PATH,
    ROUND02_SUBMISSION_CONTRACT_PATH,
    ROUND_ID,
    RUBRIC_VERSION,
    build_round02_judge_package,
    canonical_json_sha256,
    canonical_lf_sha256_file,
    validate_round02_package_or_submission,
    validate_round02_session_attestation,
    write_json_lf,
)
from scripts.validate_w5_calibration_submission import (  # noqa: E402
    ALLOWED_JUDGES,
    CSV_ALL_COLUMNS,
    CSV_READ_ONLY_COLUMNS,
    _strict_equal,
    package_to_csv_rows,
)

EXECUTION_VERSION = "W5-CAL-R02-EXEC-V1"
DISTRIBUTION_RECEIPT_TEMPLATE_VERSION = "W5-CAL-R02-DISTRIBUTION-RECEIPT-TEMPLATE-V1"
SUBMISSION_RECEIPT_TEMPLATE_VERSION = "W5-CAL-R02-SUBMISSION-RECEIPT-TEMPLATE-V1"

EXECUTION_TEMPLATES_DIR = ROUND02_OPS_DIR / "execution_templates"
PRIVATE_INTAKE_DIR = ROUND02_OPS_DIR / "private_intake"

EXECUTION_STATE_TEMPLATE_PATH = (
    ROUND02_OPS_DIR / "w5_calibration_round02_execution_state_template_v1.json"
)
DISTRIBUTION_RECEIPT_TEMPLATE_PATH = (
    ROUND02_OPS_DIR / "w5_calibration_round02_distribution_receipt_template_v1.json"
)
SUBMISSION_RECEIPT_TEMPLATE_PATH = (
    ROUND02_OPS_DIR / "w5_calibration_round02_submission_receipt_template_v1.json"
)

ROUND01_MANIFEST_PATH = (
    REPO_ROOT
    / "data"
    / "evaluation"
    / "reca_w5"
    / "calibration_submissions"
    / "w5_calibration_raw_manifest_v1.json"
)
ROUND01_INCIDENT_PATH = (
    REPO_ROOT
    / "data"
    / "evaluation"
    / "reca_w5"
    / "calibration_submissions"
    / "w5_calibration_round_01_integrity_incident_v1.json"
)
HASH_ERRATUM_PATH = (
    REPO_ROOT
    / "data"
    / "evaluation"
    / "reca_w5"
    / "audits"
    / "w5_hash_basis_erratum_v1.json"
)

FORBIDDEN_PRELOCK_OUTPUT_KEYS = frozenset(
    {
        "label_counts",
        "label_distribution",
        "labels",
        "example_ratings",
        "category_label_counts",
        "disagreement_counts",
        "disagreement_items",
        "unanimous_items",
        "agreement_statistics",
        "krippendorff_alpha",
        "alpha",
    }
)


def build_blank_judge_attestation_template(judge_id: str) -> dict[str, Any]:
    """Build a blank Round 02 session attestation template for a single judge (J1, J2, or J3).

    Pre-fills only judge_id, round_id, calibration_version, rubric_version, and
    presentation_version. All qualification-critical boolean fields remain None.
    """
    if judge_id not in ALLOWED_JUDGES:
        raise ValueError(
            f"Invalid judge_id {judge_id!r}; expected one of {ALLOWED_JUDGES}."
        )
    doc: dict[str, Any] = {
        "judge_id": judge_id,
        "round_id": ROUND_ID,
        "calibration_version": CALIBRATION_VERSION,
        "rubric_version": RUBRIC_VERSION,
        "presentation_version": PRESENTATION_VERSION,
    }
    for key in REQUIRED_ATTESTATION_BOOLEANS:
        doc[key] = None
    doc["completed_at_utc"] = None
    return doc


def build_execution_state_template_doc() -> dict[str, Any]:
    """Build the machine-readable Round 02 execution state template (not an executed receipt)."""
    return {
        "execution_version": EXECUTION_VERSION,
        "round_id": ROUND_ID,
        "calibration_version": CALIBRATION_VERSION,
        "rubric_version": RUBRIC_VERSION,
        "presentation_version": PRESENTATION_VERSION,
        "template_only": True,
        "status": "READY_FOR_HUMAN_ASSIGNMENT",
        "actual_human_roles_assigned": False,
        "distinct_actual_humans_confirmed": False,
        "packages_distributed": False,
        "human_submissions_received": 0,
        "qualifying_submissions": 0,
        "all_three_submissions_received": False,
        "all_three_submissions_qualifying": False,
        "all_three_submissions_locked": False,
        "calibration_review_eligible": False,
        "human_gt": False,
        "primary_annotation_started": False,
        "recommender_evaluation_performed": False,
    }


def build_distribution_receipt_template_doc(
    manifest_doc: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the machine-readable Round 02 package distribution receipt template."""
    if manifest_doc is None:
        manifest_doc = json.loads(ROUND02_MANIFEST_PATH.read_text(encoding="utf-8"))

    judges_out: dict[str, Any] = {}
    for jid in ALLOWED_JUDGES:
        pkg_meta = manifest_doc["judge_packages"][jid]
        judges_out[jid] = {
            "judge_id": jid,
            "assigned": False,
            "distinct_actual_human_confirmed": False,
            "package_distributed": False,
            "package_path": pkg_meta["csv_path"],
            "package_hash": pkg_meta["csv_canonical_lf_sha256"],
            "json_package_path": pkg_meta["json_path"],
            "json_package_hash": pkg_meta["json_canonical_lf_sha256"],
            "distribution_timestamp_utc": None,
        }

    return {
        "template_version": DISTRIBUTION_RECEIPT_TEMPLATE_VERSION,
        "execution_version": EXECUTION_VERSION,
        "round_id": ROUND_ID,
        "calibration_version": CALIBRATION_VERSION,
        "rubric_version": RUBRIC_VERSION,
        "presentation_version": PRESENTATION_VERSION,
        "template_only": True,
        "personal_identifiable_information_stored": False,
        "actual_human_roles_assigned": False,
        "distinct_actual_humans_confirmed": False,
        "packages_distributed": False,
        "judges": judges_out,
    }


def build_submission_receipt_template_doc() -> dict[str, Any]:
    """Build the machine-readable Round 02 submission receipt template."""
    judges_out: dict[str, Any] = {}
    for jid in ALLOWED_JUDGES:
        judges_out[jid] = {
            "judge_id": jid,
            "submission_received": False,
            "submission_path": None,
            "submission_sha256": None,
            "file_validation_status": "NOT_RUN",
            "attestation_validation_status": "NOT_RUN",
            "qualification_status": "NOT_EVALUATED",
            "received_at_utc": None,
            "locked": False,
        }

    return {
        "template_version": SUBMISSION_RECEIPT_TEMPLATE_VERSION,
        "execution_version": EXECUTION_VERSION,
        "round_id": ROUND_ID,
        "calibration_version": CALIBRATION_VERSION,
        "rubric_version": RUBRIC_VERSION,
        "presentation_version": PRESENTATION_VERSION,
        "template_only": True,
        "judges": judges_out,
        "all_three_received": False,
        "all_three_qualifying": False,
        "round_ready_to_lock": False,
    }


def write_all_execution_prep_templates() -> dict[str, str]:
    """Write all deterministic Round 02 execution kit JSON templates with LF line endings."""
    EXECUTION_TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    manifest_doc = json.loads(ROUND02_MANIFEST_PATH.read_text(encoding="utf-8"))

    written: dict[str, str] = {}
    for jid in ALLOWED_JUDGES:
        att_tpl = build_blank_judge_attestation_template(jid)
        att_path = (
            EXECUTION_TEMPLATES_DIR
            / f"w5_calibration_round02_{jid}_attestation_template_v1.json"
        )
        write_json_lf(att_path, att_tpl)
        written[f"attestation_template_{jid}"] = str(
            att_path.relative_to(REPO_ROOT)
        ).replace("\\", "/")

    exec_state_doc = build_execution_state_template_doc()
    write_json_lf(EXECUTION_STATE_TEMPLATE_PATH, exec_state_doc)
    written["execution_state_template"] = str(
        EXECUTION_STATE_TEMPLATE_PATH.relative_to(REPO_ROOT)
    ).replace("\\", "/")

    dist_doc = build_distribution_receipt_template_doc(manifest_doc)
    write_json_lf(DISTRIBUTION_RECEIPT_TEMPLATE_PATH, dist_doc)
    written["distribution_receipt_template"] = str(
        DISTRIBUTION_RECEIPT_TEMPLATE_PATH.relative_to(REPO_ROOT)
    ).replace("\\", "/")

    sub_doc = build_submission_receipt_template_doc()
    write_json_lf(SUBMISSION_RECEIPT_TEMPLATE_PATH, sub_doc)
    written["submission_receipt_template"] = str(
        SUBMISSION_RECEIPT_TEMPLATE_PATH.relative_to(REPO_ROOT)
    ).replace("\\", "/")

    return written


def check_round02_readiness() -> dict[str, Any]:
    """Verify Round 02 readiness and scientific boundary invariants before human assignment."""
    checks: dict[str, bool] = {}
    reasons: list[str] = []

    if not ROUND02_MANIFEST_PATH.is_file():
        return {
            "command": "check-readiness",
            "overall_status": "FAIL",
            "checks": {"manifest_exists": False},
            "reasons": ["missing_round02_manifest"],
        }

    manifest = json.loads(ROUND02_MANIFEST_PATH.read_text(encoding="utf-8"))
    checks["manifest_exists"] = True

    status_ok = manifest.get("status") == "PREPARED_NOT_STARTED"
    checks["status_prepared_not_started"] = status_ok
    if not status_ok:
        reasons.append(f"unexpected_round02_status:{manifest.get('status')!r}")

    judgments_zero = (
        manifest.get("actual_human_judgments_collected") == 0
        and manifest.get("qualifying_independent_human_judgments") == 0
    )
    checks["human_judgments_zero"] = judgments_zero
    if not judgments_zero:
        reasons.append("non_zero_human_judgments_in_manifest")

    boundaries_ok = (
        manifest.get("calibration_review_eligible") is False
        and manifest.get("human_gt") is False
        and manifest.get("primary_annotation_started") is False
        and manifest.get("recommender_evaluation_performed") is False
    )
    checks["scientific_boundaries_intact"] = boundaries_ok
    if not boundaries_ok:
        reasons.append("scientific_boundary_flag_violation_in_manifest")

    # Verify all Round 02 artifact and judge package hashes
    hashes_ok = True
    for key, art in manifest.get("artifacts", {}).items():
        art_path = REPO_ROOT / art["path"]
        if not art_path.is_file():
            hashes_ok = False
            reasons.append(f"missing_artifact:{key}")
            continue
        if canonical_lf_sha256_file(art_path) != art["canonical_lf_sha256"]:
            hashes_ok = False
            reasons.append(f"artifact_lf_hash_mismatch:{key}")
        obj = json.loads(art_path.read_text(encoding="utf-8"))
        if canonical_json_sha256(obj) != art["canonical_json_sha256"]:
            hashes_ok = False
            reasons.append(f"artifact_json_hash_mismatch:{key}")

    for jid in ALLOWED_JUDGES:
        pkg = manifest.get("judge_packages", {}).get(jid, {})
        json_p = REPO_ROOT / pkg.get("json_path", "")
        csv_p = REPO_ROOT / pkg.get("csv_path", "")
        if not json_p.is_file() or not csv_p.is_file():
            hashes_ok = False
            reasons.append(f"missing_judge_package:{jid}")
            continue
        if canonical_lf_sha256_file(json_p) != pkg.get("json_canonical_lf_sha256"):
            hashes_ok = False
            reasons.append(f"judge_json_lf_hash_mismatch:{jid}")
        if canonical_json_sha256(
            json.loads(json_p.read_text(encoding="utf-8"))
        ) != pkg.get("json_canonical_object_sha256"):
            hashes_ok = False
            reasons.append(f"judge_json_object_hash_mismatch:{jid}")
        if canonical_lf_sha256_file(csv_p) != pkg.get("csv_canonical_lf_sha256"):
            hashes_ok = False
            reasons.append(f"judge_csv_lf_hash_mismatch:{jid}")

    checks["package_hashes_match_manifest"] = hashes_ok

    # Verify role assignment contract remains NOT_STARTED
    role_ok = False
    if ROUND02_ROLE_CONTRACT_PATH.is_file():
        role_doc = json.loads(ROUND02_ROLE_CONTRACT_PATH.read_text(encoding="utf-8"))
        role_ok = (
            role_doc.get("assignment_execution_status") == "NOT_STARTED"
            and role_doc.get("actual_human_roles_assigned") is False
            and role_doc.get("distinct_actual_humans_confirmed") is False
            and role_doc.get("packages_distributed") is False
        )
    checks["role_contract_not_started"] = role_ok
    if not role_ok:
        reasons.append("role_assignment_contract_not_in_not_started_state")

    # Verify Round 01 remains invalidated
    round01_ok = False
    if ROUND01_MANIFEST_PATH.is_file() and ROUND01_INCIDENT_PATH.is_file():
        r1_m = json.loads(ROUND01_MANIFEST_PATH.read_text(encoding="utf-8"))
        r1_i = json.loads(ROUND01_INCIDENT_PATH.read_text(encoding="utf-8"))
        round01_ok = (
            manifest.get("round_01_status") == "INVALIDATED_FOR_PROTOCOL"
            and r1_m.get("round_status") == "INVALIDATED_FOR_PROTOCOL"
            and r1_m.get("qualifying_independent_human_judgments") == 0
            and r1_i.get("round_status") == "INVALIDATED_FOR_PROTOCOL"
            and r1_i.get("scientific_use") == "FORENSIC_NON_QUALIFYING_EVIDENCE_ONLY"
        )
    checks["round01_remains_invalidated"] = round01_ok
    if not round01_ok:
        reasons.append("round01_invalidation_state_violation")

    # Verify W5 hash erratum remains ACTIVE
    erratum_ok = False
    if HASH_ERRATUM_PATH.is_file():
        err_doc = json.loads(HASH_ERRATUM_PATH.read_text(encoding="utf-8"))
        erratum_ok = (
            err_doc.get("erratum_id") == "W5-HASH-ERRATUM-01"
            and err_doc.get("status") == "ACTIVE"
            and err_doc.get("authoritative_w5_hash_basis")
            == "sha256_git_committed_blob_content"
        )
    checks["hash_erratum_active"] = erratum_ok
    if not erratum_ok:
        reasons.append("hash_erratum_not_active")

    overall_pass = all(checks.values()) and len(reasons) == 0
    return {
        "command": "check-readiness",
        "round_id": ROUND_ID,
        "calibration_version": CALIBRATION_VERSION,
        "overall_status": "PASS" if overall_pass else "FAIL",
        "round_status": manifest.get("status"),
        "actual_human_judgments_collected": manifest.get(
            "actual_human_judgments_collected"
        ),
        "qualifying_independent_human_judgments": manifest.get(
            "qualifying_independent_human_judgments"
        ),
        "human_gt": manifest.get("human_gt"),
        "primary_annotation_started": manifest.get("primary_annotation_started"),
        "recommender_evaluation_performed": manifest.get(
            "recommender_evaluation_performed"
        ),
        "checks": checks,
        "reasons": reasons,
    }


def load_round02_csv_as_submission_dict(
    csv_path: Path,
    *,
    expected_judge_id: str | None = None,
    canonical_doc: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Load a completed Round 02 judge CSV submission and convert to a Round 02 submission dict.

    Enforces exact read-only column immutability against build_round02_judge_package
    and package_to_csv_rows before populating mutable 'label' and 'judge_note' fields.
    """
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"CSV file {csv_path} is empty or missing header.")
        if tuple(reader.fieldnames) != CSV_ALL_COLUMNS:
            raise ValueError(
                f"CSV columns mismatch in {csv_path}: got {reader.fieldnames}, "
                f"expected {list(CSV_ALL_COLUMNS)}."
            )
        rows = list(reader)

    if not rows:
        raise ValueError(f"CSV file {csv_path} has 0 data rows.")

    for r_idx, row in enumerate(rows, start=1):
        for col, cell in row.items():
            if isinstance(cell, str) and cell.lstrip().startswith("="):
                raise ValueError(
                    f"Spreadsheet formula detected in row {r_idx}, column {col!r}."
                )

    if canonical_doc is None:
        canonical_doc = json.loads(ROUND02_CALIBRATION_PATH.read_text(encoding="utf-8"))

    row_judge_id = rows[0].get("judge_id")
    if row_judge_id not in ALLOWED_JUDGES:
        raise ValueError(
            f"Invalid judge_id {row_judge_id!r} in CSV row 1; expected one of {ALLOWED_JUDGES}."
        )
    if expected_judge_id is not None and row_judge_id != expected_judge_id:
        raise ValueError(
            f"CSV judge_id mismatch: row 1 has {row_judge_id!r}, expected {expected_judge_id!r}."
        )

    reference_package = build_round02_judge_package(canonical_doc, row_judge_id)
    expected_rows = package_to_csv_rows(reference_package)

    canonical_item_ids = {r["judge_item_id"] for r in expected_rows}
    seen_csv_ids: set[str] = set()
    for r_idx, row in enumerate(rows, start=1):
        item_id = row.get("judge_item_id") or row.get("calibration_item_id") or ""
        if not item_id:
            raise ValueError(
                f"CSV row {r_idx} is missing judge_item_id / calibration_item_id."
            )
        if row.get("calibration_item_id") != row.get("judge_item_id"):
            raise ValueError(
                f"CSV row {r_idx} has mismatched calibration_item_id and judge_item_id."
            )
        if item_id in seen_csv_ids:
            raise ValueError(f"Duplicate calibration item detected in CSV: {item_id!r}.")
        seen_csv_ids.add(item_id)
        if item_id not in canonical_item_ids:
            raise ValueError(
                f"Extra or unknown calibration item detected in CSV: {item_id!r}."
            )

    missing_csv_ids = sorted(canonical_item_ids - seen_csv_ids)
    if missing_csv_ids:
        raise ValueError(f"Missing calibration item(s) in CSV: {missing_csv_ids}")

    if len(rows) != len(expected_rows):
        raise ValueError(f"Expected {len(expected_rows)} CSV rows, got {len(rows)}.")

    for r_idx, (row, exp_row) in enumerate(
        zip(rows, expected_rows, strict=True), start=1
    ):
        item_id = exp_row["judge_item_id"]
        for col in CSV_READ_ONLY_COLUMNS:
            actual_cell = row[col]
            expected_cell = exp_row[col]
            if col in {"declared_interests", "osm_factual_tags_json"}:
                try:
                    actual_parsed = json.loads(actual_cell)
                except Exception as exc:
                    raise ValueError(
                        f"CSV row {r_idx} ({item_id}) has invalid JSON in read-only column {col!r}."
                    ) from exc
                expected_parsed = json.loads(expected_cell)
                if not _strict_equal(actual_parsed, expected_parsed):
                    raise ValueError(
                        f"CSV read-only column {col!r} modified on row {r_idx} ({item_id})."
                    )
            else:
                if actual_cell != expected_cell:
                    raise ValueError(
                        f"CSV read-only column {col!r} modified on row {r_idx} ({item_id})."
                    )

    submission_doc = copy.deepcopy(reference_package)
    row_by_item_id = {r["judge_item_id"]: r for r in rows}

    for sc in submission_doc["scenarios"]:
        for item in sc["items"]:
            row = row_by_item_id[item["judge_item_id"]]
            raw_label = row["label"]
            raw_note = row["judge_note"]

            if raw_label == "":
                parsed_label: Any = None
            elif raw_label in {"0", "1", "2"}:
                parsed_label = int(raw_label)
            else:
                parsed_label = raw_label

            item["label"] = parsed_label
            item["judge_note"] = None if raw_note == "" else raw_note

    return submission_doc


def validate_round02_submission_and_attestation(
    *,
    judge_id: str,
    submission_path: Path,
    attestation_path: Path | None = None,
    canonical_doc: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate a single judge's completed Round 02 submission (.csv or .json) and attestation.

    Privacy guarantee: never returns or logs label values, distributions, or item ratings.
    """
    reasons: list[str] = []
    if judge_id not in ALLOWED_JUDGES:
        return {
            "judge_id": judge_id,
            "file_validation_status": "REJECT",
            "attestation_validation_status": "FAIL",
            "qualification_status": "NON_QUALIFYING",
            "reasons": [f"invalid_judge_id:{judge_id!r}"],
        }

    if canonical_doc is None:
        canonical_doc = json.loads(ROUND02_CALIBRATION_PATH.read_text(encoding="utf-8"))

    # 1. File validation (reusing prepare_w5_calibration_round02 + validate_w5_calibration_submission)
    file_validation_status = "PASS"
    if not submission_path.is_file():
        file_validation_status = "REJECT"
        reasons.append(f"missing_submission_file:{submission_path.name}")
    else:
        try:
            if submission_path.suffix.lower() == ".csv":
                sub_doc = load_round02_csv_as_submission_dict(
                    submission_path,
                    expected_judge_id=judge_id,
                    canonical_doc=canonical_doc,
                )
            elif submission_path.suffix.lower() == ".json":
                sub_doc = json.loads(submission_path.read_text(encoding="utf-8"))
                if not isinstance(sub_doc, dict):
                    raise ValueError("Submission JSON root must be an object.")
                if sub_doc.get("judge_id") != judge_id:
                    raise ValueError(
                        f"Submission judge_id mismatch: got {sub_doc.get('judge_id')!r}, expected {judge_id!r}."
                    )
                for sc in sub_doc.get("scenarios", []):
                    if isinstance(sc, dict):
                        for it in sc.get("items", []):
                            if isinstance(it, dict):
                                note = it.get("judge_note")
                                if note is not None and not isinstance(note, str):
                                    raise ValueError("judge_note must be string or null.")
                                if isinstance(note, str) and note.lstrip().startswith("="):
                                    raise ValueError("Spreadsheet formula forbidden in judge_note.")
            else:
                raise ValueError(
                    f"Unsupported submission file extension: {submission_path.suffix!r}"
                )

            validate_round02_package_or_submission(
                sub_doc,
                canonical_doc=canonical_doc,
                validate_empty_package=False,
                attestation_doc=None,
            )
        except Exception as exc:
            file_validation_status = "REJECT"
            reasons.append(f"file_validation_error:{exc}")

    # 2. Session attestation validation (reusing validate_round02_session_attestation)
    attestation_doc: dict[str, Any] | None = None
    if attestation_path is None or not attestation_path.is_file():
        att_res = validate_round02_session_attestation(
            None, expected_judge_id=judge_id
        )
    else:
        try:
            loaded_att = json.loads(attestation_path.read_text(encoding="utf-8"))
            attestation_doc = loaded_att if isinstance(loaded_att, dict) else None
        except Exception:
            attestation_doc = None
        att_res = validate_round02_session_attestation(
            attestation_doc, expected_judge_id=judge_id
        )

    attestation_validation_status = "PASS" if att_res["valid"] else "FAIL"
    if not att_res["valid"]:
        reasons.extend(att_res["reasons"])

    qualifying = (
        file_validation_status == "PASS" and attestation_validation_status == "PASS"
    )
    return {
        "judge_id": judge_id,
        "file_validation_status": file_validation_status,
        "attestation_validation_status": attestation_validation_status,
        "qualification_status": "QUALIFYING" if qualifying else "NON_QUALIFYING",
        "reasons": reasons,
    }


def _peek_submission_judge_id(path: Path) -> str | None:
    """Inspect a submission file's declared judge_id without exposing any labels."""
    try:
        if path.suffix.lower() == ".csv":
            with path.open("r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                first = next(reader, None)
                return first.get("judge_id") if first else None
        if path.suffix.lower() == ".json":
            doc = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(doc, dict) and "scenarios" in doc:
                jid = doc.get("judge_id")
                return str(jid) if isinstance(jid, str) else None
    except Exception:
        return None
    return None


def _is_attestation_json(path: Path) -> bool:
    """Return True if a JSON file is an attestation document rather than a package/submission."""
    if path.suffix.lower() != ".json":
        return False
    name_lower = path.name.lower()
    if "attestation" in name_lower:
        return True
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        return (
            isinstance(doc, dict)
            and "actual_human_judge" in doc
            and "scenarios" not in doc
        )
    except Exception:
        return False


def _discover_intake_submissions(
    intake_dir: Path,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Discover submission and attestation pairs inside intake_dir.

    Supports either:
    1. An explicit `intake_manifest.json` with `{"submissions": [{"judge_id": ..., "submission": ..., "attestation": ...}]}`
    2. Automatic file discovery in `intake_dir` for J1, J2, J3 submission (.csv/.json) and attestation (.json) files.
    """
    issues: list[str] = []
    manifest_file = intake_dir / "intake_manifest.json"
    if manifest_file.is_file():
        raw = json.loads(manifest_file.read_text(encoding="utf-8"))
        entries: list[dict[str, Any]] = []
        for item in raw.get("submissions", []):
            jid = item.get("judge_id")
            sub_rel = item.get("submission") or item.get("submission_path")
            att_rel = item.get("attestation") or item.get("attestation_path")
            sub_p = (intake_dir / sub_rel) if sub_rel else None
            att_p = (intake_dir / att_rel) if att_rel else None
            entries.append(
                {
                    "judge_id": jid,
                    "submission_path": sub_p,
                    "attestation_path": att_p,
                }
            )
        return entries, issues

    ignored_names = {
        "readme.md",
        ".gitignore",
        "intake_manifest.json",
    }
    candidate_sub_files: list[Path] = []
    attestation_files_by_judge: dict[str, Path] = {}

    if intake_dir.is_dir():
        for p in sorted(intake_dir.iterdir()):
            if not p.is_file() or p.name.lower() in ignored_names:
                continue
            if p.suffix.lower() not in {".csv", ".json"}:
                continue
            if _is_attestation_json(p):
                try:
                    doc = json.loads(p.read_text(encoding="utf-8"))
                    jid = doc.get("judge_id")
                except Exception:
                    jid = None
                if not jid:
                    for allowed_j in ALLOWED_JUDGES:
                        if allowed_j.lower() in p.name.lower():
                            jid = allowed_j
                            break
                if isinstance(jid, str):
                    attestation_files_by_judge[jid] = p
            else:
                candidate_sub_files.append(p)

    discovered_entries: list[dict[str, Any]] = []
    for sub_p in candidate_sub_files:
        declared_jid = _peek_submission_judge_id(sub_p)
        if declared_jid is None:
            for allowed_j in ALLOWED_JUDGES:
                if allowed_j.lower() in sub_p.name.lower():
                    declared_jid = allowed_j
                    break
        att_p = (
            attestation_files_by_judge.get(declared_jid)
            if declared_jid is not None
            else None
        )
        discovered_entries.append(
            {
                "judge_id": declared_jid or "UNKNOWN",
                "submission_path": sub_p,
                "attestation_path": att_p,
            }
        )

    return discovered_entries, issues


def check_round02_lock_readiness(intake_dir: Path) -> dict[str, Any]:
    """Inspect private intake directory and determine whether Round 02 is READY_TO_LOCK.

    Enforces:
    - 3 submissions present for 3 distinct judge IDs (J1, J2, J3)
    - No duplicate judge IDs
    - Each judge passes both file validation and session attestation validation (QUALIFYING)
    - Never computes alpha, aggregates labels, adjudicates, or prints label values/counts.
    """
    canonical_doc = json.loads(ROUND02_CALIBRATION_PATH.read_text(encoding="utf-8"))
    entries, discovery_issues = _discover_intake_submissions(intake_dir)

    reasons: list[str] = list(discovery_issues)
    seen_judges: list[str] = [str(e.get("judge_id")) for e in entries]
    distinct_judges = sorted(set(seen_judges))

    duplicate_judge_ids = len(seen_judges) != len(set(seen_judges))
    if duplicate_judge_ids:
        reasons.append(f"duplicate_judge_ids_detected:{seen_judges}")

    missing_judges = sorted(set(ALLOWED_JUDGES) - set(seen_judges))
    if missing_judges:
        reasons.append(f"missing_required_judges:{missing_judges}")

    if len(entries) != len(ALLOWED_JUDGES):
        reasons.append(
            f"expected_3_submissions_got:{len(entries)}"
        )

    judge_results: dict[str, dict[str, Any]] = {}
    qualifying_count = 0

    for idx, entry in enumerate(entries, start=1):
        jid = str(entry.get("judge_id") or f"UNKNOWN_{idx}")
        sub_p = entry.get("submission_path")
        att_p = entry.get("attestation_path")

        if sub_p is None:
            res = {
                "judge_id": jid,
                "file_validation_status": "REJECT",
                "attestation_validation_status": "FAIL",
                "qualification_status": "NON_QUALIFYING",
                "reasons": ["missing_submission_file"],
            }
        else:
            res = validate_round02_submission_and_attestation(
                judge_id=jid if jid in ALLOWED_JUDGES else "INVALID",
                submission_path=Path(sub_p),
                attestation_path=Path(att_p) if att_p is not None else None,
                canonical_doc=canonical_doc,
            )
            res["judge_id"] = jid

        result_key = jid if jid not in judge_results else f"{jid}__dup_{idx}"
        judge_results[result_key] = res
        if res["qualification_status"] == "QUALIFYING":
            qualifying_count += 1
        else:
            reasons.append(f"judge_{result_key}_non_qualifying")

    for missing_j in missing_judges:
        judge_results[missing_j] = {
            "judge_id": missing_j,
            "file_validation_status": "NOT_RECEIVED",
            "attestation_validation_status": "NOT_RECEIVED",
            "qualification_status": "NON_QUALIFYING",
            "reasons": ["submission_not_received"],
        }

    all_three_received = (
        len(entries) == 3
        and not duplicate_judge_ids
        and set(seen_judges) == set(ALLOWED_JUDGES)
    )
    all_three_qualifying = all_three_received and qualifying_count == 3
    ready_to_lock = all_three_qualifying and len(reasons) == 0

    return {
        "command": "check-lock-readiness",
        "round_id": ROUND_ID,
        "calibration_version": CALIBRATION_VERSION,
        "lock_readiness_status": "READY_TO_LOCK"
        if ready_to_lock
        else "NOT_READY_TO_LOCK",
        "round_ready_to_lock": ready_to_lock,
        "submissions_inspected_count": len(entries),
        "distinct_judges_found": distinct_judges,
        "duplicate_judge_ids_detected": duplicate_judge_ids,
        "qualifying_submissions_count": qualifying_count,
        "all_three_received": all_three_received,
        "all_three_qualifying": all_three_qualifying,
        "judge_summaries": judge_results,
        "reasons": reasons,
        "scientific_side_effects": {
            "alpha_calculated": False,
            "labels_aggregated": False,
            "disagreements_adjudicated": False,
            "human_gt_created": False,
            "files_committed": False,
            "round02_manifest_modified": False,
            "cal_review_started": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Manage W5 Calibration Round 02 safe human collection execution and readiness checks."
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    subparsers.add_parser(
        "check-readiness",
        help="Verify Round 02 manifest, package hashes, role contract, Round 01 invalidation, and hash erratum.",
    )

    p_att = subparsers.add_parser(
        "make-attestation-template",
        help="Generate a blank session attestation JSON template for a single judge (J1, J2, or J3).",
    )
    p_att.add_argument(
        "--judge",
        required=True,
        choices=list(ALLOWED_JUDGES),
        help="Judge ID (J1, J2, or J3).",
    )
    p_att.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Output file path for the blank attestation JSON template.",
    )

    p_val = subparsers.add_parser(
        "validate-submission",
        help="Validate a single judge's completed Round 02 submission (.csv or .json) and session attestation.",
    )
    p_val.add_argument(
        "--judge",
        required=True,
        choices=list(ALLOWED_JUDGES),
        help="Expected Judge ID (J1, J2, or J3).",
    )
    p_val.add_argument(
        "--submission",
        required=True,
        type=Path,
        help="Path to the completed submission file (.csv or .json).",
    )
    p_val.add_argument(
        "--attestation",
        required=False,
        default=None,
        type=Path,
        help="Path to the completed session attestation JSON file.",
    )

    p_lock = subparsers.add_parser(
        "check-lock-readiness",
        help="Inspect J1/J2/J3 completed submissions and attestations in a private intake directory.",
    )
    p_lock.add_argument(
        "--intake-dir",
        required=True,
        type=Path,
        help="Path to the local private intake directory.",
    )

    subparsers.add_parser(
        "write-kit-templates",
        help="Write the committed Round 02 execution kit templates deterministically.",
    )

    args = parser.parse_args(argv)

    if args.subcommand == "check-readiness":
        res = check_round02_readiness()
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0 if res["overall_status"] == "PASS" else 1

    if args.subcommand == "make-attestation-template":
        tpl = build_blank_judge_attestation_template(args.judge)
        write_json_lf(args.output, tpl)
        print(
            json.dumps(
                {
                    "command": "make-attestation-template",
                    "status": "CREATED",
                    "judge_id": args.judge,
                    "output": str(args.output),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.subcommand == "validate-submission":
        res = validate_round02_submission_and_attestation(
            judge_id=args.judge,
            submission_path=args.submission,
            attestation_path=args.attestation,
        )
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0 if res["qualification_status"] == "QUALIFYING" else 1

    if args.subcommand == "check-lock-readiness":
        res = check_round02_lock_readiness(args.intake_dir)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0 if res["lock_readiness_status"] == "READY_TO_LOCK" else 1

    if args.subcommand == "write-kit-templates":
        written = write_all_execution_prep_templates()
        print(json.dumps({"status": "WRITTEN", "files": written}, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
