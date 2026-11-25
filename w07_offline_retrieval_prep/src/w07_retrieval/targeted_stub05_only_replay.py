"""Scoped single-use authorization & fail-closed runner for TARGETED_STUB05_ONLY_REPLAY.

Implements ONLY the `OWNER_CHAT_READONLY_V1_TARGETED_STUB05_ONLY` execution branch
authorized by Owner Decision `OD-W07-G15-TARGETED-STUB05-ONLY-REPLAY-20261121-01`:
1. Verifies exact SHA-256 and byte-size bindings across the Owner Parallel Execution
   Order Markdown, the bound permit receipt, all 6 source/test files (`chunker_c0.py`,
   `chunker_c1.py`, `visibility.py`, `runner.py`, `real_corpus_preflight.py`, and
   `tests/test_real_corpus_gated_stubs.py`), frozen inputs (Protocol v1.0 LF,
   Annex v0.2.2, `tokenizer.json`, Stage A manifest + 7 pinned corpus bundle specs),
   the corrective audit ZIP, and preserved historical `CORRECTIVE_REPLAY_01` outputs.
2. Enforces single-use scope: strictly `STUB-05` / `FX-05-C0-TRUNCATION-AND-MULTI-SPAN-VIS`
   on target Overture document `w07-b1b-doc-overture-f0d424bd-e55bab3c`, writing only to
   the unused `W07_STUB05_TARGETED_REPLAY_01_2026-11-21` directory and leaving
   consumed `CORRECTIVE_REPLAY_01` locks and `STUB-01..04` receipts untouched.
3. Delegates `STUB-05` scientific evaluation verbatim to unmodified
   `w07_retrieval.real_corpus_preflight.execute_stub05_fx05_overture_visibility`.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import socket
import sys
import time
from typing import Any, Dict, Optional, Sequence

from w07_retrieval.real_corpus_preflight import (
    APPROVED_ANNEX_V0_2_2_SHA256,
    APPROVED_TECH_FREEZE_RECEIPT_SHA256,
    LIVE_137_CORPUS_EXPECTATIONS,
    OWNER_CHAT_AUTH_POLICY_RECEIPT_SHA256,
    OWNER_CHAT_AUTH_WAIVER_MD_SHA256,
    PINNED_LIVE_137_CORPUS_7_ARTIFACTS,
    PINNED_STAGE_A_CORPUS_BUNDLE_MANIFEST_SHA256,
    PROTOCOL_V1_0_LF_SHA256,
    CorpusPreflightExpectations,
    _verify_bundle_artifacts_against_pinned_specs,
    execute_stub05_fx05_overture_visibility,
    validate_stub01_05_readonly_preflight_gate,
)
from w07_retrieval.schema import PINNED_TOKENIZER_SHA256
from w07_retrieval.visibility import resolve_snapshot_dir

TARGETED_REPLAY_ID = "TARGETED_STUB05_ONLY_REPLAY_01"
TARGETED_REPLAY_AUTH_MODE = "OWNER_CHAT_READONLY_V1_TARGETED_STUB05_ONLY"
TARGETED_REPLAY_SCHEMA_V1 = "GOMATE_W07_STUB05_TARGETED_ONLY_REPLAY_AUTH_V1"
TARGETED_REPLAY_DECISION_ID = "OD-W07-G15-TARGETED-STUB05-ONLY-REPLAY-20261121-01"
TARGETED_REPLAY_AUTHORIZATION_STATUS = "APPROVED_SCOPED_ONCE_NOT_YET_EXECUTED"
TARGETED_REPLAY_AUTHORIZATION_ASSURANCE = (
    "OWNER_ORDER_MARKDOWN_AND_CHAT_APPROVAL_NOT_CRYPTOGRAPHIC_IDENTITY_VERIFICATION"
)

ALLOWED_TARGET_STUB_ID = "STUB-05"
ALLOWED_TARGET_FX_ID = "FX-05-C0-TRUNCATION-AND-MULTI-SPAN-VIS"
PINNED_TARGET_OVERTURE_DOC_ID = "w07-b1b-doc-overture-f0d424bd-e55bab3c"

PINNED_OWNER_ORDER_MD_SHA256 = (
    "4880e96c46148c03b24481c4ba197a580f068176babaa575f0af36cc259503e2"
)
PINNED_OWNER_ORDER_MD_BYTES = 8041
PINNED_PERMIT_RECEIPT_SHA256 = (
    "6cd7c4d79efd7df4692fb140348bb346d7621b2039bf3918f8441c4b91d2076d"
)
PINNED_PERMIT_RECEIPT_BYTES = 3420

PINNED_PREFLIGHT_CORRECTED_V2_SHA256 = (
    "f6d56da87a88bc102a26165482ad0704dfa84b1d845c3b399128dfc4f8859a97"
)
PINNED_PREFLIGHT_CORRECTED_V2_BYTES = 80683
PINNED_GATED_TESTS_CORRECTED_SHA256 = (
    "029a28d0d2576495939813a78f7d41d7a082382f73f2a70d3c67c339bff01ddb"
)
PINNED_GATED_TESTS_CORRECTED_BYTES = 73801
PINNED_CHUNKER_C0_UNCHANGED_SHA256 = (
    "8d5e793773a73d4b0d1776fcb30268edeeb3eb89638564cb3a25b1f9394ce517"
)
PINNED_CHUNKER_C1_UNCHANGED_SHA256 = (
    "f74c9f87f15dfeb4bb7f71bf0ac9a56947264c77dbc9aa91b66a52b6364e9ac3"
)
PINNED_VISIBILITY_UNCHANGED_SHA256 = (
    "b2a65676c33a27b50694891c7adfc041d09ace8bd210239d5e75f366ad9690b6"
)
PINNED_FORMAL_RUNNER_UNCHANGED_SHA256 = (
    "bcc93c100c52dd08ee51737655c5bf9d8ac2e759a0bad8f0b24ee065befae10d"
)

PINNED_CORRECTIVE_AUDIT_ZIP_SHA256 = (
    "430e00b438f3bea5317f74d2c479dc176d268cb4136ecb7774bcca750f6c43d0"
)
PINNED_CORRECTIVE_AUDIT_ZIP_BYTES = 73513

PINNED_REPLAY01_SUMMARY_SHA256 = (
    "5d1ff1542c5c30d27cd82277daa8f22a170fff3a81922c27bf7889e4d144b84e"
)
PINNED_REPLAY01_STUB01_PASS_SHA256 = (
    "58f8125ee69ac45af8c3027051585cf10fbb5e4ae6d7ed7ca5732681b20925b3"
)
PINNED_REPLAY01_STUB02_PASS_SHA256 = (
    "a5e01cc4fcc053dfc09a0ed6115fea12946f691ff20550bc2e99fbcf34e6cca0"
)
PINNED_REPLAY01_STUB03_PASS_SHA256 = (
    "2c08d7d2e502fe76eb7efb9e8e1d5661f923daa10f40c5a46f881d4f2050672f"
)
PINNED_REPLAY01_STUB04_PASS_SHA256 = (
    "0bdc8bd057819b237cdb4b1d74dd4bcc9f8bcc9a3dbe56df114452db6310372d"
)
PINNED_REPLAY01_STUB05_FAIL_SHA256 = (
    "9542672f2fc2c90acc84855f2a5c5a8c4bb48ccc87865089e9b059e0674cc341"
)

_HOST_WORKSPACE_PARENT = Path(__file__).resolve().parents[3]
PINNED_HISTORICAL_FIRST_RUN_DIR = (
    _HOST_WORKSPACE_PARENT / "W07_STUB01_05_REAL_CORPUS_PREFLIGHT_RUN_2026-11-21"
)
PINNED_CORRECTIVE_REPLAY_01_DIR = (
    _HOST_WORKSPACE_PARENT / "W07_STUB01_05_REAL_CORPUS_CORRECTIVE_REPLAY_01_2026-11-21"
)
PINNED_TARGETED_STUB05_OUTPUT_DIR = (
    _HOST_WORKSPACE_PARENT / "W07_STUB05_TARGETED_REPLAY_01_2026-11-21"
)

PINNED_TARGETED_REPLAY_BASELINE_SHA256: Dict[str, str] = {
    "approved_annex_v0_2_2_sha256": APPROVED_ANNEX_V0_2_2_SHA256,
    "chunker_c0_sha256": PINNED_CHUNKER_C0_UNCHANGED_SHA256,
    "chunker_c1_sha256": PINNED_CHUNKER_C1_UNCHANGED_SHA256,
    "corrective_audit_zip_sha256": PINNED_CORRECTIVE_AUDIT_ZIP_SHA256,
    "formal_runner_sha256": PINNED_FORMAL_RUNNER_UNCHANGED_SHA256,
    "owner_execution_order_md_sha256": PINNED_OWNER_ORDER_MD_SHA256,
    "real_corpus_preflight_sha256": PINNED_PREFLIGHT_CORRECTED_V2_SHA256,
    "replay01_execution_summary_sha256": PINNED_REPLAY01_SUMMARY_SHA256,
    "replay01_stub01_pass_sha256": PINNED_REPLAY01_STUB01_PASS_SHA256,
    "replay01_stub02_pass_sha256": PINNED_REPLAY01_STUB02_PASS_SHA256,
    "replay01_stub03_pass_sha256": PINNED_REPLAY01_STUB03_PASS_SHA256,
    "replay01_stub04_pass_sha256": PINNED_REPLAY01_STUB04_PASS_SHA256,
    "replay01_stub05_fail_sha256": PINNED_REPLAY01_STUB05_FAIL_SHA256,
    "scientific_protocol_v1_lf_sha256": PROTOCOL_V1_0_LF_SHA256,
    "stage_a_manifest_sha256": PINNED_STAGE_A_CORPUS_BUNDLE_MANIFEST_SHA256,
    "test_real_corpus_gated_stubs_sha256": PINNED_GATED_TESTS_CORRECTED_SHA256,
    "tokenizer_json_sha256": PINNED_TOKENIZER_SHA256,
    "visibility_sha256": PINNED_VISIBILITY_UNCHANGED_SHA256,
}

_ENV_SPOOF_VARS = (
    "W07_G15_FROZEN",
    "W07_OWNER_AUTHORIZED",
    "W07_STUB_01_05_AUTHORIZED",
    "W07_CORRECTIVE_REPLAY_01_AUTHORIZED",
    "W07_REPLAY_01_AUTHORIZED",
    "W07_TARGETED_STUB05_ONLY_AUTHORIZED",
)
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def _utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _require_clean_file(path: Optional[Path], error_code: str) -> Path:
    if path is None:
        raise PermissionError(error_code)
    p = Path(path)
    if not p.is_file() or p.is_symlink():
        raise PermissionError(f"{error_code}: missing or invalid file {p}")
    return p


def _assert_fresh_unused_output_dir(
    *,
    output_dir: Path,
    approved_output_dir_str: str,
    historical_run_dir: Path,
    corrective_replay_01_dir: Path,
    synthetic_fixture_mode: bool,
) -> Path:
    out_p = Path(output_dir).resolve()
    approved_p = Path(approved_output_dir_str).resolve()
    hist_p = Path(historical_run_dir).resolve()
    replay01_p = Path(corrective_replay_01_dir).resolve()

    if out_p == hist_p or out_p == replay01_p:
        raise PermissionError(
            "TARGETED_STUB05_REPLAY_BLOCKED_CANNOT_OVERWRITE_PRIOR_RUN: "
            f"output_dir ({out_p}) collides with preserved prior run directory."
        )

    if out_p != approved_p:
        raise PermissionError(
            "TARGETED_STUB05_REPLAY_BLOCKED_OUTPUT_PATH_MISMATCH: "
            f"output_dir ({out_p}) != receipt output_directory ({approved_p})."
        )

    if (
        not synthetic_fixture_mode
        and out_p != PINNED_TARGETED_STUB05_OUTPUT_DIR.resolve()
    ):
        raise PermissionError(
            "TARGETED_STUB05_REPLAY_BLOCKED_UNPINNED_LIVE_OUTPUT_PATH: "
            f"{out_p} != {PINNED_TARGETED_STUB05_OUTPUT_DIR.resolve()}."
        )

    if out_p.exists():
        if not out_p.is_dir() or out_p.is_symlink():
            raise PermissionError(
                f"TARGETED_STUB05_REPLAY_BLOCKED_INVALID_OUTPUT_PATH: {out_p}"
            )
        for marker in (
            "execution_summary.json",
            "stub_05_result.json",
            "single_use_consumed_lock.json",
        ):
            marker_p = out_p / marker
            if marker_p.exists():
                raise RuntimeError(
                    "TARGETED_STUB05_REPLAY_BLOCKED_ALREADY_EXECUTED: consumed marker "
                    f"detected at {marker_p}; single-use replay #02 is forbidden."
                )
        if list(out_p.iterdir()):
            raise PermissionError(
                "TARGETED_STUB05_REPLAY_BLOCKED_OUTPUT_DIR_NOT_EMPTY: "
                f"{out_p} must be absent or empty before execution."
            )

    return out_p


def _verify_exact_source_and_test_files(repo_root: Path) -> Dict[str, str]:
    src_pkg = repo_root / "src" / "w07_retrieval"
    tests_dir = repo_root / "tests"
    targets = (
        ("chunker_c0.py", src_pkg / "chunker_c0.py", PINNED_CHUNKER_C0_UNCHANGED_SHA256, None),
        ("chunker_c1.py", src_pkg / "chunker_c1.py", PINNED_CHUNKER_C1_UNCHANGED_SHA256, None),
        ("visibility.py", src_pkg / "visibility.py", PINNED_VISIBILITY_UNCHANGED_SHA256, None),
        ("runner.py", src_pkg / "runner.py", PINNED_FORMAL_RUNNER_UNCHANGED_SHA256, None),
        (
            "real_corpus_preflight.py",
            src_pkg / "real_corpus_preflight.py",
            PINNED_PREFLIGHT_CORRECTED_V2_SHA256,
            PINNED_PREFLIGHT_CORRECTED_V2_BYTES,
        ),
        (
            "test_real_corpus_gated_stubs.py",
            tests_dir / "test_real_corpus_gated_stubs.py",
            PINNED_GATED_TESTS_CORRECTED_SHA256,
            PINNED_GATED_TESTS_CORRECTED_BYTES,
        ),
    )
    verified: Dict[str, str] = {}
    for label, fpath, exp_sha, exp_bytes in targets:
        clean_p = _require_clean_file(
            fpath, f"TARGETED_STUB05_REPLAY_BLOCKED_MISSING_CODE_{label}"
        )
        raw = clean_p.read_bytes()
        act_sha = _sha256_bytes(raw)
        if act_sha != exp_sha or (exp_bytes is not None and len(raw) != exp_bytes):
            raise PermissionError(
                f"TARGETED_STUB05_REPLAY_BLOCKED_CODE_HASH_MISMATCH for {label}: "
                f"({len(raw)} B, {act_sha}) != expected ({exp_bytes}, {exp_sha})."
            )
        verified[label] = act_sha
    return verified


def _verify_preserved_replay01_outputs(corrective_replay_01_dir: Path) -> Dict[str, str]:
    r01_dir = Path(corrective_replay_01_dir)
    expected_files = (
        ("execution_summary.json", PINNED_REPLAY01_SUMMARY_SHA256),
        ("stub_01_result.json", PINNED_REPLAY01_STUB01_PASS_SHA256),
        ("stub_02_result.json", PINNED_REPLAY01_STUB02_PASS_SHA256),
        ("stub_03_result.json", PINNED_REPLAY01_STUB03_PASS_SHA256),
        ("stub_04_result.json", PINNED_REPLAY01_STUB04_PASS_SHA256),
        ("stub_05_result.json", PINNED_REPLAY01_STUB05_FAIL_SHA256),
    )
    verified: Dict[str, str] = {}
    for fname, exp_sha in expected_files:
        fp = _require_clean_file(
            r01_dir / fname,
            f"TARGETED_STUB05_REPLAY_BLOCKED_MISSING_REPLAY01_{fname}",
        )
        act_sha = _sha256_file(fp)
        if act_sha != exp_sha:
            raise PermissionError(
                f"TARGETED_STUB05_REPLAY_BLOCKED_REPLAY01_HASH_MISMATCH for {fname}: "
                f"{act_sha} != {exp_sha}."
            )
        verified[fname] = act_sha

    summary_obj = json.loads((r01_dir / "execution_summary.json").read_text(encoding="utf-8"))
    if summary_obj.get("replay_consumed_guard", {}).get("single_use_consumed") is not True:
        raise PermissionError(
            "TARGETED_STUB05_REPLAY_BLOCKED_REPLAY01_LOCK_TAMPERED: "
            "CORRECTIVE_REPLAY_01 must remain permanently consumed."
        )
    return verified


def _validate_permit_receipt_fields(
    *,
    rec_obj: Dict[str, Any],
    stubs_list: Sequence[str],
    expectations: CorpusPreflightExpectations,
    synthetic_fixture_mode: bool,
) -> None:
    if rec_obj.get("schema_version") != TARGETED_REPLAY_SCHEMA_V1:
        raise PermissionError(
            f"TARGETED_STUB05_REPLAY_BLOCKED_INVALID_SCHEMA: {rec_obj.get('schema_version')!r}"
        )
    if rec_obj.get("replay_id") != TARGETED_REPLAY_ID:
        raise PermissionError("TARGETED_STUB05_REPLAY_BLOCKED_REPLAY_ID_MISMATCH")
    if rec_obj.get("auth_mode") != TARGETED_REPLAY_AUTH_MODE:
        raise PermissionError("TARGETED_STUB05_REPLAY_BLOCKED_AUTH_MODE_MISMATCH")
    if rec_obj.get("decision_id") != TARGETED_REPLAY_DECISION_ID:
        raise PermissionError("TARGETED_STUB05_REPLAY_BLOCKED_DECISION_ID_MISMATCH")
    if rec_obj.get("authorization_status") != TARGETED_REPLAY_AUTHORIZATION_STATUS:
        raise PermissionError("TARGETED_STUB05_REPLAY_BLOCKED_AUTH_STATUS_MISMATCH")
    if rec_obj.get("authorization_assurance") != TARGETED_REPLAY_AUTHORIZATION_ASSURANCE:
        raise PermissionError("TARGETED_STUB05_REPLAY_BLOCKED_AUTH_ASSURANCE_MISMATCH")
    if rec_obj.get("authorizes_once") is not True:
        raise PermissionError("TARGETED_STUB05_REPLAY_BLOCKED_AUTHORIZES_ONCE_NOT_TRUE")
    if rec_obj.get("max_successful_or_failed_replay_attempts") != 1:
        raise PermissionError("TARGETED_STUB05_REPLAY_BLOCKED_MAX_ATTEMPTS_MUST_BE_1")
    if rec_obj.get("one_shot_stop_on_failure") is not True:
        raise PermissionError("TARGETED_STUB05_REPLAY_BLOCKED_STOP_ON_FAILURE_NOT_TRUE")
    if rec_obj.get("prechecks_required") is not True:
        raise PermissionError("TARGETED_STUB05_REPLAY_BLOCKED_PRECHECKS_REQUIRED")
    if rec_obj.get("preserve_historical_runs") is not True:
        raise PermissionError("TARGETED_STUB05_REPLAY_BLOCKED_PRESERVE_PRIOR_REQUIRED")

    if list(stubs_list) != [ALLOWED_TARGET_STUB_ID]:
        raise PermissionError(
            "TARGETED_STUB05_REPLAY_BLOCKED_FORBIDDEN_STUB_SELECTION: "
            f"only {[ALLOWED_TARGET_STUB_ID]!r} is authorized, got {list(stubs_list)!r}."
        )
    if rec_obj.get("allowed_stubs") != [ALLOWED_TARGET_STUB_ID]:
        raise PermissionError(
            "TARGETED_STUB05_REPLAY_BLOCKED_PERMIT_STUBS_MISMATCH: "
            f"{rec_obj.get('allowed_stubs')!r} != {[ALLOWED_TARGET_STUB_ID]!r}."
        )
    if rec_obj.get("target_fx_id") != ALLOWED_TARGET_FX_ID:
        raise PermissionError("TARGETED_STUB05_REPLAY_BLOCKED_TARGET_FX_MISMATCH")

    doc_in_receipt = rec_obj.get("target_document_id")
    if doc_in_receipt != expectations.overture_target_doc_id:
        raise PermissionError(
            "TARGETED_STUB05_REPLAY_BLOCKED_TARGET_DOC_MISMATCH: "
            f"{doc_in_receipt!r} != {expectations.overture_target_doc_id!r}."
        )
    if not synthetic_fixture_mode and doc_in_receipt != PINNED_TARGET_OVERTURE_DOC_ID:
        raise PermissionError(
            "TARGETED_STUB05_REPLAY_BLOCKED_UNPINNED_LIVE_DOC: "
            f"{doc_in_receipt!r} != {PINNED_TARGET_OVERTURE_DOC_ID!r}."
        )

    for forbidden_flag in (
        "corpus_writes_authorized",
        "network_authorized",
        "paid_api_authorized",
        "stub01_04_rerun_authorized",
        "stub06_authorized",
        "full_g15_closed",
        "formal_g3_g4_authorized",
        "final50_dev_t0_authorized",
        "repo_push_pr_merge_authorized",
    ):
        if rec_obj.get(forbidden_flag) is not False:
            raise PermissionError(
                f"TARGETED_STUB05_REPLAY_BLOCKED_SCOPE_ESCALATION: {forbidden_flag} must be False."
            )
    if rec_obj.get("od_g15_05") != "HOLD":
        raise PermissionError("TARGETED_STUB05_REPLAY_BLOCKED_OD_G15_05_MUST_BE_HOLD")

    baseline = rec_obj.get("baseline_sha256")
    if (
        not isinstance(baseline, dict)
        or baseline != PINNED_TARGETED_REPLAY_BASELINE_SHA256
    ):
        raise PermissionError(
            "TARGETED_STUB05_REPLAY_BLOCKED_BASELINE_SHA256_MISMATCH: receipt baseline_sha256 "
            "does not match exact pinned 18-entry digest table."
        )


def validate_targeted_stub05_only_gate(
    *,
    requested_stubs: Sequence[str] = (ALLOWED_TARGET_STUB_ID,),
    output_dir: Optional[Path],
    owner_order_md_path: Optional[Path],
    permit_receipt_path: Optional[Path],
    annex_v0_2_2_path: Optional[Path],
    tech_freeze_receipt_path: Optional[Path],
    owner_chat_policy_receipt_path: Optional[Path],
    chat_auth_waiver_path: Optional[Path],
    original_exec_decision_path: Optional[Path],
    corpus_bundle_manifest_path: Optional[Path],
    protocol_v1_path: Optional[Path],
    corrective_audit_zip_path: Optional[Path],
    corrective_replay_01_dir: Path = PINNED_CORRECTIVE_REPLAY_01_DIR,
    historical_run_dir: Path = PINNED_HISTORICAL_FIRST_RUN_DIR,
    snapshot_dir: Optional[Path] = None,
    expectations: CorpusPreflightExpectations = LIVE_137_CORPUS_EXPECTATIONS,
    _test_only_trusted_owner_pubkey_hex: Optional[str] = None,
    _synthetic_fixture_mode: bool = False,
) -> Dict[str, Any]:
    """Fail-closed permission & preflight hash verifier for TARGETED_STUB05_ONLY_REPLAY."""
    if _test_only_trusted_owner_pubkey_hex is not None:
        raise PermissionError(
            "TARGETED_STUB05_REPLAY_BLOCKED_TEST_KEY_FORBIDDEN: "
            "test public keys are forbidden under OWNER_CHAT_READONLY_V1_TARGETED_STUB05_ONLY."
        )

    env_spoof_active = any(os.environ.get(k) == "1" for k in _ENV_SPOOF_VARS)
    if output_dir is None or owner_order_md_path is None or permit_receipt_path is None:
        spoof_note = (
            " Plain environment variables cannot authorize TARGETED_STUB05_ONLY_REPLAY."
            if env_spoof_active
            else ""
        )
        raise PermissionError(
            "TARGETED_STUB05_REPLAY_BLOCKED_MISSING_RECEIPTS: missing owner_order_md_path, "
            f"permit_receipt_path, or output_dir.{spoof_note}"
        )

    order_p = _require_clean_file(
        owner_order_md_path, "TARGETED_STUB05_REPLAY_BLOCKED_MISSING_OWNER_ORDER_MD"
    )
    order_bytes = order_p.read_bytes()
    order_sha = _sha256_bytes(order_bytes)
    if (
        len(order_bytes) != PINNED_OWNER_ORDER_MD_BYTES
        or order_sha != PINNED_OWNER_ORDER_MD_SHA256
    ):
        raise PermissionError(
            "TARGETED_STUB05_REPLAY_BLOCKED_OWNER_ORDER_HASH_MISMATCH: "
            f"({len(order_bytes)} B, {order_sha}) != expected "
            f"({PINNED_OWNER_ORDER_MD_BYTES} B, {PINNED_OWNER_ORDER_MD_SHA256})."
        )
    order_text = order_bytes.decode("utf-8")
    for required_token in (
        TARGETED_REPLAY_DECISION_ID,
        "TARGETED_STUB05_ONLY_REPLAY",
        PINNED_TARGET_OVERTURE_DOC_ID,
    ):
        if required_token not in order_text:
            raise PermissionError(
                f"TARGETED_STUB05_REPLAY_BLOCKED_OWNER_ORDER_MISSING_TOKEN: {required_token}"
            )

    permit_p = _require_clean_file(
        permit_receipt_path, "TARGETED_STUB05_REPLAY_BLOCKED_MISSING_PERMIT_RECEIPT"
    )
    permit_bytes = permit_p.read_bytes()
    permit_sha = _sha256_bytes(permit_bytes)
    if not _synthetic_fixture_mode and (
        len(permit_bytes) != PINNED_PERMIT_RECEIPT_BYTES
        or permit_sha != PINNED_PERMIT_RECEIPT_SHA256
    ):
        raise PermissionError(
            "TARGETED_STUB05_REPLAY_BLOCKED_PERMIT_RECEIPT_HASH_MISMATCH: "
            f"({len(permit_bytes)} B, {permit_sha}) != expected "
            f"({PINNED_PERMIT_RECEIPT_BYTES} B, {PINNED_PERMIT_RECEIPT_SHA256})."
        )

    try:
        rec_obj = json.loads(permit_bytes.decode("utf-8"))
    except Exception as exc:
        raise PermissionError(
            f"TARGETED_STUB05_REPLAY_BLOCKED_MALFORMED_PERMIT_JSON: {exc}"
        ) from exc
    if not isinstance(rec_obj, dict):
        raise PermissionError("TARGETED_STUB05_REPLAY_BLOCKED_PERMIT_NOT_JSON_OBJECT")

    _validate_permit_receipt_fields(
        rec_obj=rec_obj,
        stubs_list=list(requested_stubs),
        expectations=expectations,
        synthetic_fixture_mode=_synthetic_fixture_mode,
    )

    repo_root = Path(__file__).resolve().parents[2]
    verified_code_hashes = _verify_exact_source_and_test_files(repo_root)

    proto_p = _require_clean_file(
        protocol_v1_path, "TARGETED_STUB05_REPLAY_BLOCKED_MISSING_PROTOCOL_V1"
    )
    proto_lf_sha = _sha256_bytes(proto_p.read_bytes().replace(b"\r\n", b"\n"))
    if proto_lf_sha != PROTOCOL_V1_0_LF_SHA256:
        raise PermissionError(
            "TARGETED_STUB05_REPLAY_BLOCKED_PROTOCOL_SHA256_MISMATCH: "
            f"{proto_lf_sha} != {PROTOCOL_V1_0_LF_SHA256}."
        )

    zip_p = _require_clean_file(
        corrective_audit_zip_path,
        "TARGETED_STUB05_REPLAY_BLOCKED_MISSING_CORRECTIVE_AUDIT_ZIP",
    )
    zip_bytes = zip_p.read_bytes()
    zip_sha = _sha256_bytes(zip_bytes)
    if (
        len(zip_bytes) != PINNED_CORRECTIVE_AUDIT_ZIP_BYTES
        or zip_sha != PINNED_CORRECTIVE_AUDIT_ZIP_SHA256
    ):
        raise PermissionError(
            "TARGETED_STUB05_REPLAY_BLOCKED_CORRECTIVE_ZIP_HASH_MISMATCH: "
            f"({len(zip_bytes)} B, {zip_sha}) != expected "
            f"({PINNED_CORRECTIVE_AUDIT_ZIP_BYTES} B, {PINNED_CORRECTIVE_AUDIT_ZIP_SHA256})."
        )

    verified_replay01_hashes = _verify_preserved_replay01_outputs(corrective_replay_01_dir)

    resolved_snap = resolve_snapshot_dir(snapshot_dir)
    tok_p = _require_clean_file(
        resolved_snap / "tokenizer.json",
        "TARGETED_STUB05_REPLAY_BLOCKED_MISSING_TOKENIZER_JSON",
    )
    tok_sha = _sha256_file(tok_p)
    if tok_sha != PINNED_TOKENIZER_SHA256:
        raise PermissionError(
            "TARGETED_STUB05_REPLAY_BLOCKED_TOKENIZER_HASH_MISMATCH: "
            f"{tok_sha} != {PINNED_TOKENIZER_SHA256}."
        )

    approved_out_raw = rec_obj.get("output_directory")
    if type(approved_out_raw) is not str or not approved_out_raw.strip():
        raise PermissionError("TARGETED_STUB05_REPLAY_BLOCKED_MISSING_OUTPUT_DIR")
    resolved_out = _assert_fresh_unused_output_dir(
        output_dir=Path(output_dir),
        approved_output_dir_str=approved_out_raw,
        historical_run_dir=Path(historical_run_dir),
        corrective_replay_01_dir=Path(corrective_replay_01_dir),
        synthetic_fixture_mode=_synthetic_fixture_mode,
    )

    underlying_gate = validate_stub01_05_readonly_preflight_gate(
        requested_stub_id=ALLOWED_TARGET_STUB_ID,
        annex_v0_2_2_path=annex_v0_2_2_path,
        tech_freeze_receipt_path=tech_freeze_receipt_path,
        stub_auth_receipt_path=owner_chat_policy_receipt_path,
        corpus_bundle_manifest_path=corpus_bundle_manifest_path,
        auth_mode="OWNER_CHAT_READONLY_V1",
        chat_auth_waiver_path=chat_auth_waiver_path,
        original_exec_decision_path=original_exec_decision_path,
        _synthetic_fixture_mode=_synthetic_fixture_mode,
    )

    bundle_p = Path(corpus_bundle_manifest_path)  # verified by underlying gate
    verified_artifacts_count = 0
    if not _synthetic_fixture_mode:
        if _sha256_file(bundle_p) != PINNED_STAGE_A_CORPUS_BUNDLE_MANIFEST_SHA256:
            raise PermissionError(
                "TARGETED_STUB05_REPLAY_BLOCKED_STAGE_A_MANIFEST_HASH_MISMATCH"
            )
        bundle_obj = json.loads(bundle_p.read_text(encoding="utf-8"))
        verified_list = _verify_bundle_artifacts_against_pinned_specs(
            corpus_bundle_manifest_path=bundle_p,
            bundle_obj=bundle_obj,
            expected_artifact_count=7,
            expected_pinned_artifacts=PINNED_LIVE_137_CORPUS_7_ARTIFACTS,
        )
        verified_artifacts_count = len(verified_list)

    return {
        "replay_id": TARGETED_REPLAY_ID,
        "auth_mode": TARGETED_REPLAY_AUTH_MODE,
        "decision_id": TARGETED_REPLAY_DECISION_ID,
        "authorization_assurance": TARGETED_REPLAY_AUTHORIZATION_ASSURANCE,
        "identity_authentication": "NOT_CRYPTOGRAPHICALLY_VERIFIED",
        "owner_execution_order_md_sha256": order_sha,
        "permit_receipt_sha256": permit_sha,
        "approved_annex_v0_2_2_sha256": APPROVED_ANNEX_V0_2_2_SHA256,
        "tech_freeze_receipt_sha256": APPROVED_TECH_FREEZE_RECEIPT_SHA256,
        "owner_chat_waiver_sha256": OWNER_CHAT_AUTH_WAIVER_MD_SHA256,
        "owner_chat_policy_receipt_sha256": underlying_gate["policy_receipt_sha256"],
        "protocol_v1_lf_sha256": proto_lf_sha,
        "tokenizer_json_sha256": tok_sha,
        "corrective_audit_zip_sha256": zip_sha,
        "stage_a_manifest_sha256": _sha256_file(bundle_p),
        "verified_code_sha256": verified_code_hashes,
        "verified_replay01_sha256": verified_replay01_hashes,
        "verified_7_artifacts_count": verified_artifacts_count,
        "target_stub_id": ALLOWED_TARGET_STUB_ID,
        "target_fx_id": ALLOWED_TARGET_FX_ID,
        "target_document_id": expectations.overture_target_doc_id,
        "output_directory": str(resolved_out),
        "trust_anchor_mode": (
            "SYNTHETIC_FIXTURE_TARGETED_STUB05_TEST_ONLY"
            if _synthetic_fixture_mode
            else "OWNER_CHAT_READONLY_V1_TARGETED_STUB05_LOCAL_HOST"
        ),
    }


def run_targeted_stub05_only_replay(
    *,
    requested_stubs: Sequence[str] = (ALLOWED_TARGET_STUB_ID,),
    output_dir: Path,
    owner_order_md_path: Path,
    permit_receipt_path: Path,
    annex_v0_2_2_path: Path,
    tech_freeze_receipt_path: Path,
    owner_chat_policy_receipt_path: Path,
    chat_auth_waiver_path: Path,
    original_exec_decision_path: Path,
    corpus_bundle_manifest_path: Path,
    protocol_v1_path: Path,
    corrective_audit_zip_path: Path,
    corrective_replay_01_dir: Path = PINNED_CORRECTIVE_REPLAY_01_DIR,
    historical_run_dir: Path = PINNED_HISTORICAL_FIRST_RUN_DIR,
    snapshot_dir: Optional[Path] = None,
    expectations: CorpusPreflightExpectations = LIVE_137_CORPUS_EXPECTATIONS,
    _test_only_trusted_owner_pubkey_hex: Optional[str] = None,
    _synthetic_fixture_mode: bool = False,
) -> Dict[str, Any]:
    """Execute exactly one offline read-only STUB-05 replay on the target Overture doc."""
    wall_t0 = time.perf_counter()
    cpu_t0 = time.process_time()

    gate_info = validate_targeted_stub05_only_gate(
        requested_stubs=requested_stubs,
        output_dir=output_dir,
        owner_order_md_path=owner_order_md_path,
        permit_receipt_path=permit_receipt_path,
        annex_v0_2_2_path=annex_v0_2_2_path,
        tech_freeze_receipt_path=tech_freeze_receipt_path,
        owner_chat_policy_receipt_path=owner_chat_policy_receipt_path,
        chat_auth_waiver_path=chat_auth_waiver_path,
        original_exec_decision_path=original_exec_decision_path,
        corpus_bundle_manifest_path=corpus_bundle_manifest_path,
        protocol_v1_path=protocol_v1_path,
        corrective_audit_zip_path=corrective_audit_zip_path,
        corrective_replay_01_dir=corrective_replay_01_dir,
        historical_run_dir=historical_run_dir,
        snapshot_dir=snapshot_dir,
        expectations=expectations,
        _test_only_trusted_owner_pubkey_hex=_test_only_trusted_owner_pubkey_hex,
        _synthetic_fixture_mode=_synthetic_fixture_mode,
    )

    out_p = Path(gate_info["output_directory"])

    for env_k in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE"):
        os.environ[env_k] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"

    network_counter = {"non_loopback_attempts": 0}
    orig_connect = socket.socket.connect
    orig_connect_ex = socket.socket.connect_ex
    orig_create_conn = socket.create_connection

    def _extract_host(addr: Any) -> Optional[str]:
        if isinstance(addr, tuple) and len(addr) >= 1 and isinstance(addr[0], str):
            return addr[0]
        return None

    def _guarded_connect(self: socket.socket, address: Any) -> Any:
        host = _extract_host(address)
        if host is not None and host not in _LOOPBACK_HOSTS:
            network_counter["non_loopback_attempts"] += 1
            raise RuntimeError(f"OUTBOUND_NETWORK_BLOCKED: target={host!r}")
        return orig_connect(self, address)

    def _guarded_connect_ex(self: socket.socket, address: Any) -> int:
        host = _extract_host(address)
        if host is not None and host not in _LOOPBACK_HOSTS:
            network_counter["non_loopback_attempts"] += 1
            raise RuntimeError(f"OUTBOUND_NETWORK_BLOCKED: target={host!r}")
        return orig_connect_ex(self, address)

    def _guarded_create_conn(address: Any, *args: Any, **kwargs: Any) -> Any:
        host = _extract_host(address)
        if host is not None and host not in _LOOPBACK_HOSTS:
            network_counter["non_loopback_attempts"] += 1
            raise RuntimeError(f"OUTBOUND_NETWORK_BLOCKED: target={host!r}")
        return orig_create_conn(address, *args, **kwargs)

    socket.socket.connect = _guarded_connect  # type: ignore[method-assign]
    socket.socket.connect_ex = _guarded_connect_ex  # type: ignore[method-assign]
    socket.create_connection = _guarded_create_conn  # type: ignore[assignment]

    try:
        out_p.mkdir(parents=True, exist_ok=True)
        execution_id = (
            f"{TARGETED_REPLAY_ID}__{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        )

        started_at = _utc_iso_now()
        stub_w0 = time.perf_counter()
        stub_c0 = time.process_time()
        try:
            raw_metrics = execute_stub05_fx05_overture_visibility(
                annex_v0_2_2_path=annex_v0_2_2_path,
                tech_freeze_receipt_path=tech_freeze_receipt_path,
                stub_auth_receipt_path=owner_chat_policy_receipt_path,
                corpus_bundle_manifest_path=corpus_bundle_manifest_path,
                snapshot_dir=snapshot_dir,
                expectations=expectations,
                auth_mode="OWNER_CHAT_READONLY_V1",
                chat_auth_waiver_path=chat_auth_waiver_path,
                original_exec_decision_path=original_exec_decision_path,
                _synthetic_fixture_mode=_synthetic_fixture_mode,
            )
            if raw_metrics.get("target_document_id") != expectations.overture_target_doc_id:
                raise ValueError(
                    "TARGETED_STUB05_REPLAY_TARGET_DOC_MISMATCH: executed document "
                    f"{raw_metrics.get('target_document_id')!r} != {expectations.overture_target_doc_id!r}."
                )
            completed_at = _utc_iso_now()
            elapsed_s = round(time.perf_counter() - stub_w0, 4)
            cpu_s = round(time.process_time() - stub_c0, 4)
            metrics_body = {k: v for k, v in raw_metrics.items() if k != "gate"}
            ev_sha = _sha256_bytes(
                json.dumps(metrics_body, ensure_ascii=False, sort_keys=True).encode("utf-8")
            )
            stub_passed = metrics_body.get("status") == "PASS"
            stub_payload: Dict[str, Any] = {
                "execution_id": execution_id,
                "replay_id": TARGETED_REPLAY_ID,
                "decision_id": TARGETED_REPLAY_DECISION_ID,
                "stub_id": ALLOWED_TARGET_STUB_ID,
                "target_fx_id": ALLOWED_TARGET_FX_ID,
                "target_document_id": expectations.overture_target_doc_id,
                "status": "PASS" if stub_passed else "FAIL",
                "metrics": metrics_body,
                "evidence_sha256": ev_sha,
                "code_sha256": gate_info["verified_code_sha256"],
                "manifest_sha256": gate_info["stage_a_manifest_sha256"],
                "error_code": None,
                "started_at": started_at,
                "completed_at": completed_at,
                "elapsed_seconds": elapsed_s,
                "cpu_seconds": cpu_s,
            }
        except Exception as exc:
            completed_at = _utc_iso_now()
            elapsed_s = round(time.perf_counter() - stub_w0, 4)
            cpu_s = round(time.process_time() - stub_c0, 4)
            err_msg = f"{type(exc).__name__}: {exc}"
            ev_sha = _sha256_bytes(err_msg.encode("utf-8"))
            stub_passed = False
            stub_payload = {
                "execution_id": execution_id,
                "replay_id": TARGETED_REPLAY_ID,
                "decision_id": TARGETED_REPLAY_DECISION_ID,
                "stub_id": ALLOWED_TARGET_STUB_ID,
                "target_fx_id": ALLOWED_TARGET_FX_ID,
                "target_document_id": expectations.overture_target_doc_id,
                "status": "FAIL",
                "metrics": {},
                "evidence_sha256": ev_sha,
                "code_sha256": gate_info["verified_code_sha256"],
                "manifest_sha256": gate_info["stage_a_manifest_sha256"],
                "error_code": err_msg,
                "started_at": started_at,
                "completed_at": completed_at,
                "elapsed_seconds": elapsed_s,
                "cpu_seconds": cpu_s,
            }

        stub_bytes = (
            json.dumps(stub_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        stub_file = out_p / "stub_05_result.json"
        stub_file.write_bytes(stub_bytes)
        stub_file_sha = _sha256_bytes(stub_bytes)

        total_elapsed_s = round(time.perf_counter() - wall_t0, 4)
        total_cpu_s = round(time.process_time() - cpu_t0, 4)
        replay_status = "EXECUTED_ONCE_PASS" if stub_passed else "EXECUTED_ONCE_FAIL"

        lock_obj: Dict[str, Any] = {
            "schema_version": "W07_TARGETED_STUB05_ONLY_SINGLE_USE_LOCK_V1",
            "execution_id": execution_id,
            "replay_id": TARGETED_REPLAY_ID,
            "decision_id": TARGETED_REPLAY_DECISION_ID,
            "single_use_consumed": True,
            "future_auto_replay_blocked": True,
            "consumed_at_utc": _utc_iso_now(),
            "stub_05_status": stub_payload["status"],
            "stub_05_result_sha256": stub_file_sha,
        }
        lock_bytes = (
            json.dumps(lock_obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        lock_file = out_p / "single_use_consumed_lock.json"
        lock_file.write_bytes(lock_bytes)
        lock_sha = _sha256_bytes(lock_bytes)

        summary_obj: Dict[str, Any] = {
            "schema_version": "W07_TARGETED_STUB05_ONLY_EXECUTION_SUMMARY_V1",
            "execution_id": execution_id,
            "replay_id": TARGETED_REPLAY_ID,
            "decision_id": TARGETED_REPLAY_DECISION_ID,
            "auth_mode": TARGETED_REPLAY_AUTH_MODE,
            "authorization_assurance": TARGETED_REPLAY_AUTHORIZATION_ASSURANCE,
            "identity_authentication": "NOT_CRYPTOGRAPHICALLY_VERIFIED",
            "overall_status": replay_status,
            "executed_stub_count": 1,
            "executed_stub_id": ALLOWED_TARGET_STUB_ID,
            "target_fx_id": ALLOWED_TARGET_FX_ID,
            "target_document_id": expectations.overture_target_doc_id,
            "stub01_04_rerun": False,
            "replay_consumed_guard": {
                "single_use_consumed": True,
                "future_auto_replay_blocked": True,
                "lock_file": "single_use_consumed_lock.json",
                "lock_file_sha256": lock_sha,
            },
            "bindings": {
                "owner_execution_order_md_sha256": gate_info[
                    "owner_execution_order_md_sha256"
                ],
                "permit_receipt_sha256": gate_info["permit_receipt_sha256"],
                "approved_annex_v0_2_2_sha256": APPROVED_ANNEX_V0_2_2_SHA256,
                "tech_freeze_receipt_sha256": APPROVED_TECH_FREEZE_RECEIPT_SHA256,
                "owner_chat_waiver_sha256": OWNER_CHAT_AUTH_WAIVER_MD_SHA256,
                "owner_chat_policy_receipt_sha256": OWNER_CHAT_AUTH_POLICY_RECEIPT_SHA256,
                "protocol_v1_lf_sha256": gate_info["protocol_v1_lf_sha256"],
                "tokenizer_json_sha256": gate_info["tokenizer_json_sha256"],
                "stage_a_manifest_sha256": gate_info["stage_a_manifest_sha256"],
                "corrective_audit_zip_sha256": gate_info["corrective_audit_zip_sha256"],
                "code_sha256": gate_info["verified_code_sha256"],
                "targeted_stub05_only_replay_module_sha256": _sha256_file(
                    Path(__file__).resolve()
                ),
            },
            "preserved_prior_replay01_receipts": {
                "directory": str(Path(corrective_replay_01_dir).resolve()),
                "execution_summary_sha256": gate_info["verified_replay01_sha256"][
                    "execution_summary.json"
                ],
                "stub_01_pass_sha256": gate_info["verified_replay01_sha256"][
                    "stub_01_result.json"
                ],
                "stub_02_pass_sha256": gate_info["verified_replay01_sha256"][
                    "stub_02_result.json"
                ],
                "stub_03_pass_sha256": gate_info["verified_replay01_sha256"][
                    "stub_03_result.json"
                ],
                "stub_04_pass_sha256": gate_info["verified_replay01_sha256"][
                    "stub_04_result.json"
                ],
                "stub_05_historical_fail_sha256": gate_info["verified_replay01_sha256"][
                    "stub_05_result.json"
                ],
            },
            "stub_05_result": {
                "result_file": "stub_05_result.json",
                "result_file_sha256": stub_file_sha,
                "status": stub_payload["status"],
                "evidence_sha256": stub_payload["evidence_sha256"],
                "error_code": stub_payload["error_code"],
                "elapsed_seconds": elapsed_s,
                "cpu_seconds": cpu_s,
            },
            "profile_name": expectations.profile_name,
            "runtime_metrics": {
                "total_elapsed_seconds": total_elapsed_s,
                "total_cpu_seconds": total_cpu_s,
            },
            "host_environment": {
                "platform": platform.platform(),
                "python_version": platform.python_version(),
            },
            "observable_counters": {
                "live_api_calls": 0,
                "network_requests": network_counter["non_loopback_attempts"],
                "paid_api_spend_usd": 0.0,
            },
            "downstream_governance_hold": {
                "stub_06": "HOLD",
                "od_g15_05": "HOLD",
                "full_g15_closed": False,
                "g2_g3_g4_g5_g6_authorized": False,
                "final50_dev_t0_live_api_authorized": False,
                "public_push_merge_authorized": False,
            },
        }
        summary_bytes = (
            json.dumps(summary_obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        (out_p / "execution_summary.json").write_bytes(summary_bytes)
        return summary_obj
    finally:
        socket.socket.connect = orig_connect  # type: ignore[method-assign]
        socket.socket.connect_ex = orig_connect_ex  # type: ignore[method-assign]
        socket.create_connection = orig_create_conn  # type: ignore[assignment]


def _default_cli_args() -> argparse.Namespace:
    prep = Path(__file__).resolve().parents[2]
    do_an = prep.parent
    return argparse.Namespace(
        output_dir=PINNED_TARGETED_STUB05_OUTPUT_DIR,
        owner_order_md_path=(
            do_an
            / "W07_STUB05_TARGETED_REPLAY_01_PACK_2026-11-21"
            / "GOMATE_OWNER_APPROVED_PARALLEL_EXECUTION_ORDER_2026-11-21.md"
        ),
        permit_receipt_path=(
            do_an
            / "W07_STUB05_TARGETED_REPLAY_01_PACK_2026-11-21"
            / "GOMATE_W07_STUB05_TARGETED_REPLAY_01_PERMIT_RECEIPT_2026-11-21.json"
        ),
        annex_v0_2_2_path=(
            prep
            / "authorities_v0_2_2_tech_freeze"
            / "GOMATE_W07_G15_TECHNICAL_ANNEX_V0_2_2_CANDIDATE_2026-11-21.md"
        ),
        tech_freeze_receipt_path=(
            prep
            / "authorities_v0_2_2_tech_freeze"
            / "GOMATE_W07_G15_TECH_FREEZE_OWNER_APPROVAL_RECEIPT_2026-11-21.json"
        ),
        owner_chat_policy_receipt_path=(
            prep
            / "authorities_v0_2_2_tech_freeze"
            / "GOMATE_W07_STUB01_05_OWNER_CHAT_AUTH_POLICY_RECEIPT_V1_2026-11-21.json"
        ),
        chat_auth_waiver_path=(
            prep
            / "authorities_v0_2_2_tech_freeze"
            / "GOMATE_W07_STUB01_05_OWNER_CHAT_AUTH_WAIVER_V1_0_2026-11-21.md"
        ),
        original_exec_decision_path=(
            do_an
            / "W07_STUB01_05_LOCAL_ACTIVATION_2026-11-21"
            / "GOMATE_W07_STUB01_05_OWNER_CHAT_EXECUTION_DECISION_2026-11-21.md"
        ),
        corpus_bundle_manifest_path=(
            do_an
            / "W07_STUB01_05_LOCAL_ACTIVATION_2026-11-21"
            / "W07_G15_STUB01_05_CORPUS_BUNDLE_MANIFEST_V1.json"
        ),
        protocol_v1_path=(
            do_an
            / "W07_B2_G1_5_ANNEX_CORRECTIVE_02"
            / "01_controlling_authorities_and_audit_receipts"
            / "W07_B2_SCIENTIFIC_PROTOCOL_V1_0_OWNER_APPROVED_2026-11-04.md"
        ),
        corrective_audit_zip_path=(
            do_an / "GOMATE_W07_STUB05_NARROW_HARNESS_CORRECTIVE_AUDIT_2026-11-21.zip"
        ),
        corrective_replay_01_dir=PINNED_CORRECTIVE_REPLAY_01_DIR,
        historical_run_dir=PINNED_HISTORICAL_FIRST_RUN_DIR,
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    defaults = _default_cli_args()
    parser = argparse.ArgumentParser(
        description="Execute single-use offline read-only STUB-05 replay."
    )
    parser.add_argument("--output-dir", type=Path, default=defaults.output_dir)
    summary = run_targeted_stub05_only_replay(
        requested_stubs=(ALLOWED_TARGET_STUB_ID,),
        output_dir=parser.parse_args(argv).output_dir,
        owner_order_md_path=defaults.owner_order_md_path,
        permit_receipt_path=defaults.permit_receipt_path,
        annex_v0_2_2_path=defaults.annex_v0_2_2_path,
        tech_freeze_receipt_path=defaults.tech_freeze_receipt_path,
        owner_chat_policy_receipt_path=defaults.owner_chat_policy_receipt_path,
        chat_auth_waiver_path=defaults.chat_auth_waiver_path,
        original_exec_decision_path=defaults.original_exec_decision_path,
        corpus_bundle_manifest_path=defaults.corpus_bundle_manifest_path,
        protocol_v1_path=defaults.protocol_v1_path,
        corrective_audit_zip_path=defaults.corrective_audit_zip_path,
        corrective_replay_01_dir=defaults.corrective_replay_01_dir,
        historical_run_dir=defaults.historical_run_dir,
    )
    sys.stdout.write(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    return 0 if summary["overall_status"] == "EXECUTED_ONCE_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
