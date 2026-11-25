"""Scoped single-use authorization & fail-closed runner for CORRECTIVE_REPLAY_01.

Implements ONLY the `OWNER_CHAT_READONLY_V1_CORRECTIVE_REPLAY_01` branch authorized by
Owner decision `OD-W07-STUB01-05-CORRECTIVE-REPLAY-01-OWNER-CHAT-20261121-01`:
1. Validates full-file SHA-256 digests across all 13 pinned baseline bindings
   (Protocol v1.0 LF, Annex v0.2.2, Stage A manifest, Waiver v1.0, corrected
   `chunker_c1.py` and `real_corpus_preflight.py`, unchanged `visibility.py` and
   `runner.py`, and preserved historical first-run failure artifacts).
2. Enforces strict single-replay binding to the fresh non-overwriting output path
   (`W07_STUB01_05_REAL_CORPUS_CORRECTIVE_REPLAY_01_2026-11-21`), blocking
   replay #02, wrong paths, wrong digests, plain env-var overrides, test keys, and
   scope escalation (`STUB-06`, `G2..G6`, `FINAL-50`, `DEV`, `T0`, live APIs, push/merge).
3. Keeps `chunker_c1.py`, `real_corpus_preflight.py`, `visibility.py`, and `runner.py`
   byte-identical to their Owner-approved SHA-256 digests while delegating STUB-01..05
   scientific checks to `w07_retrieval.real_corpus_preflight`.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import socket
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from w07_retrieval.real_corpus_preflight import (
    ALLOWED_READONLY_STUB_IDS,
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
    execute_stub01_fx01_hash_and_arm_p_counts,
    execute_stub02_fx02_canonical_conservation,
    execute_stub03_fx03_audit_tags_and_v_hash,
    execute_stub04_fx04_c1_token_ceiling,
    execute_stub05_fx05_overture_visibility,
    validate_stub01_05_readonly_preflight_gate,
)
from w07_retrieval.runner import EXPECTED_ELIGIBLE_DOC_COUNT

CORRECTIVE_REPLAY_01_ID = "CORRECTIVE_REPLAY_01"
CORRECTIVE_REPLAY_01_AUTH_MODE = "OWNER_CHAT_READONLY_V1_CORRECTIVE_REPLAY_01"
CORRECTIVE_REPLAY_01_SCHEMA_V1 = (
    "GOMATE_W07_STUB01_05_OWNER_CHAT_CORRECTIVE_REPLAY_AUTH_V1"
)
CORRECTIVE_REPLAY_01_DECISION_ID = (
    "OD-W07-STUB01-05-CORRECTIVE-REPLAY-01-OWNER-CHAT-20261121-01"
)
CORRECTIVE_REPLAY_01_AUTHORIZATION_STATUS = "APPROVED_SCOPED_ONCE_NOT_YET_EXECUTED"
CORRECTIVE_REPLAY_01_AUTHORIZATION_ASSURANCE = (
    "CHAT_APPROVAL_NOT_CRYPTOGRAPHIC_IDENTITY_VERIFICATION"
)

CORRECTIVE_REPLAY_01_DECISION_MD_SHA256 = (
    "faa7d745d8ee51bd5716543465d5fa6a330c11e561b13b3843c9e8fc70467957"
)
CORRECTIVE_REPLAY_01_DECISION_MD_BYTES = 4514
CORRECTIVE_REPLAY_01_RECEIPT_JSON_SHA256 = (
    "4350b901d52b08d8c2705c4e6f778f59452bfcd034d5b812604b9dd839eceda6"
)
CORRECTIVE_REPLAY_01_RECEIPT_JSON_BYTES = 2875

PINNED_CHUNKER_C1_CORRECTED_SHA256 = (
    "f74c9f87f15dfeb4bb7f71bf0ac9a56947264c77dbc9aa91b66a52b6364e9ac3"
)
PINNED_PREFLIGHT_CORRECTED_SHA256 = (
    "f206d79a734a9f9f5ab298ab206a030626114e3446729b04106aba6212ce82b9"
)
# Superseding Owner-approved STUB-05 narrow harness corrective digest ratified by
# OD-W07-G15-TARGETED-STUB05-ONLY-REPLAY-20261121-01 (order MD 4880e96c..., permit 6cd7c4d7...).
PINNED_PREFLIGHT_POST_STUB05_V2_SHA256 = (
    "f6d56da87a88bc102a26165482ad0704dfa84b1d845c3b399128dfc4f8859a97"
)
ALLOWED_ON_DISK_PREFLIGHT_SHA256S = frozenset(
    {
        PINNED_PREFLIGHT_CORRECTED_SHA256,
        PINNED_PREFLIGHT_POST_STUB05_V2_SHA256,
    }
)
PINNED_VISIBILITY_UNCHANGED_SHA256 = (
    "b2a65676c33a27b50694891c7adfc041d09ace8bd210239d5e75f366ad9690b6"
)
PINNED_FORMAL_RUNNER_UNCHANGED_SHA256 = (
    "bcc93c100c52dd08ee51737655c5bf9d8ac2e759a0bad8f0b24ee065befae10d"
)

PINNED_PREVIOUS_REAL_RUN_ZIP_SHA256 = (
    "1ab49ab74acec9f5a85b1e15bb34024fd5eeb60423b26e24d9413066cd52f9a4"
)
PINNED_PREVIOUS_REAL_RUN_SUMMARY_SHA256 = (
    "e00963ead4026f388decd63299977f51600155b23d28f01a56cf6c22c74effe4"
)
PINNED_PREVIOUS_STUB01_PASS_SHA256 = (
    "9573a9065939d24e9844cabfd719071cb7d2284d2cf93e5f5493897a4d4a40b8"
)
PINNED_PREVIOUS_STUB02_FAIL_SHA256 = (
    "e1fdef0a42c974dc6dc96c944bf339aed3b5df81b298ed975bd879707dc28fec"
)
PINNED_PRIOR_C1_CORRECTIVE_ZIP_SHA256 = (
    "2481cd2f73af0b5ee644cf9343faa1fac6e9070208aa70b37dff99a7faa7d34d"
)

_HOST_WORKSPACE_PARENT = Path(__file__).resolve().parents[3]
PINNED_CORRECTIVE_REPLAY_01_OUTPUT_DIR = (
    _HOST_WORKSPACE_PARENT / "W07_STUB01_05_REAL_CORPUS_CORRECTIVE_REPLAY_01_2026-11-21"
)
PINNED_HISTORICAL_FIRST_RUN_DIR = (
    _HOST_WORKSPACE_PARENT / "W07_STUB01_05_REAL_CORPUS_PREFLIGHT_RUN_2026-11-21"
)

PINNED_REPLAY_01_BASELINE_SHA256: Dict[str, str] = {
    "approved_annex_v0_2_2_sha256": APPROVED_ANNEX_V0_2_2_SHA256,
    "chunker_c1_corrected_sha256": PINNED_CHUNKER_C1_CORRECTED_SHA256,
    "formal_runner_unchanged_sha256": PINNED_FORMAL_RUNNER_UNCHANGED_SHA256,
    "owner_chat_auth_waiver_sha256": OWNER_CHAT_AUTH_WAIVER_MD_SHA256,
    "previous_real_run_summary_sha256": PINNED_PREVIOUS_REAL_RUN_SUMMARY_SHA256,
    "previous_real_run_zip_sha256": PINNED_PREVIOUS_REAL_RUN_ZIP_SHA256,
    "previous_stub01_pass_sha256": PINNED_PREVIOUS_STUB01_PASS_SHA256,
    "previous_stub02_fail_sha256": PINNED_PREVIOUS_STUB02_FAIL_SHA256,
    "prior_c1_corrective_zip_sha256": PINNED_PRIOR_C1_CORRECTIVE_ZIP_SHA256,
    "real_corpus_preflight_corrected_sha256": PINNED_PREFLIGHT_CORRECTED_SHA256,
    "scientific_protocol_v1_lf_sha256": PROTOCOL_V1_0_LF_SHA256,
    "stage_a_manifest_sha256": PINNED_STAGE_A_CORPUS_BUNDLE_MANIFEST_SHA256,
    "visibility_unchanged_sha256": PINNED_VISIBILITY_UNCHANGED_SHA256,
}

_ENV_SPOOF_VARS: Tuple[str, ...] = (
    "W07_G15_FROZEN",
    "W07_OWNER_AUTHORIZED",
    "W07_STUB_01_05_AUTHORIZED",
    "W07_CORRECTIVE_REPLAY_01_AUTHORIZED",
    "W07_REPLAY_01_AUTHORIZED",
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
    synthetic_fixture_mode: bool,
) -> Path:
    out_p = Path(output_dir).resolve()
    approved_p = Path(approved_output_dir_str).resolve()
    hist_p = Path(historical_run_dir).resolve()

    if out_p == hist_p:
        raise PermissionError(
            "CORRECTIVE_REPLAY_01_BLOCKED_CANNOT_OVERWRITE_HISTORICAL_RUN: "
            f"output_dir ({out_p}) must not collide with historical first run ({hist_p})."
        )

    if out_p != approved_p:
        raise PermissionError(
            "CORRECTIVE_REPLAY_01_BLOCKED_OUTPUT_PATH_MISMATCH: "
            f"output_dir ({out_p}) != receipt output_directory ({approved_p})."
        )

    if (
        not synthetic_fixture_mode
        and out_p != PINNED_CORRECTIVE_REPLAY_01_OUTPUT_DIR.resolve()
    ):
        raise PermissionError(
            "CORRECTIVE_REPLAY_01_BLOCKED_UNPINNED_LIVE_OUTPUT_PATH: "
            f"{out_p} != {PINNED_CORRECTIVE_REPLAY_01_OUTPUT_DIR.resolve()}."
        )

    if out_p.exists():
        if not out_p.is_dir() or out_p.is_symlink():
            raise PermissionError(
                f"CORRECTIVE_REPLAY_01_BLOCKED_INVALID_OUTPUT_PATH: {out_p}"
            )
        summary_p = out_p / "execution_summary.json"
        if summary_p.exists():
            raise RuntimeError(
                "CORRECTIVE_REPLAY_01_BLOCKED_ALREADY_EXECUTED: replay execution_summary.json "
                f"already exists at {summary_p}; duplicate replay #02 is forbidden."
            )
        for idx in range(1, 6):
            stub_f = out_p / f"stub_0{idx}_result.json"
            if stub_f.exists():
                raise RuntimeError(
                    "CORRECTIVE_REPLAY_01_BLOCKED_ALREADY_EXECUTED: existing stub artifact "
                    f"detected at {stub_f}; duplicate replay #02 is forbidden."
                )
        existing_entries = list(out_p.iterdir())
        if existing_entries:
            raise PermissionError(
                "CORRECTIVE_REPLAY_01_BLOCKED_OUTPUT_DIR_NOT_EMPTY: "
                f"{out_p} must be absent or empty before CORRECTIVE_REPLAY_01."
            )

    return out_p


def validate_corrective_replay_01_gate(
    *,
    requested_stubs: Sequence[str] = ALLOWED_READONLY_STUB_IDS,
    output_dir: Optional[Path],
    replay_decision_path: Optional[Path],
    replay_approval_receipt_path: Optional[Path],
    annex_v0_2_2_path: Optional[Path],
    tech_freeze_receipt_path: Optional[Path],
    owner_chat_policy_receipt_path: Optional[Path],
    chat_auth_waiver_path: Optional[Path],
    original_exec_decision_path: Optional[Path],
    corpus_bundle_manifest_path: Optional[Path],
    protocol_v1_path: Optional[Path],
    historical_run_dir: Path = PINNED_HISTORICAL_FIRST_RUN_DIR,
    previous_real_run_zip_path: Optional[Path] = None,
    prior_c1_corrective_zip_path: Optional[Path] = None,
    _test_only_trusted_owner_pubkey_hex: Optional[str] = None,
    _synthetic_fixture_mode: bool = False,
) -> Dict[str, Any]:
    """Fail-closed gate for single-use CORRECTIVE_REPLAY_01 under Owner Chat approval."""
    if _test_only_trusted_owner_pubkey_hex is not None:
        raise PermissionError(
            "CORRECTIVE_REPLAY_01_BLOCKED_TEST_KEY_FORBIDDEN: "
            "test public keys are forbidden under OWNER_CHAT_READONLY_V1_CORRECTIVE_REPLAY_01."
        )

    stubs_list = list(requested_stubs)
    if not stubs_list or any(s not in ALLOWED_READONLY_STUB_IDS for s in stubs_list):
        raise PermissionError(
            "CORRECTIVE_REPLAY_01_BLOCKED_FORBIDDEN_STUB_ID: "
            f"requested_stubs {stubs_list!r} must be a non-empty subset of {ALLOWED_READONLY_STUB_IDS}."
        )

    env_spoof_active = any(os.environ.get(k) == "1" for k in _ENV_SPOOF_VARS)
    if (
        replay_decision_path is None
        or replay_approval_receipt_path is None
        or output_dir is None
    ):
        spoof_note = (
            " Plain environment variables cannot authorize CORRECTIVE_REPLAY_01."
            if env_spoof_active
            else ""
        )
        raise PermissionError(
            "CORRECTIVE_REPLAY_01_BLOCKED_MISSING_RECEIPTS: missing replay decision, "
            f"approval receipt, or output_dir.{spoof_note}"
        )

    dec_p = _require_clean_file(
        replay_decision_path, "CORRECTIVE_REPLAY_01_BLOCKED_MISSING_DECISION_DOC"
    )
    rec_p = _require_clean_file(
        replay_approval_receipt_path,
        "CORRECTIVE_REPLAY_01_BLOCKED_MISSING_APPROVAL_RECEIPT",
    )

    dec_bytes = dec_p.read_bytes()
    dec_sha = _sha256_bytes(dec_bytes)
    if (
        len(dec_bytes) != CORRECTIVE_REPLAY_01_DECISION_MD_BYTES
        or dec_sha != CORRECTIVE_REPLAY_01_DECISION_MD_SHA256
    ):
        raise PermissionError(
            "CORRECTIVE_REPLAY_01_BLOCKED_DECISION_DOC_HASH_MISMATCH: "
            f"({len(dec_bytes)} B, {dec_sha}) != expected "
            f"({CORRECTIVE_REPLAY_01_DECISION_MD_BYTES} B, {CORRECTIVE_REPLAY_01_DECISION_MD_SHA256})."
        )

    rec_bytes = rec_p.read_bytes()
    rec_sha = _sha256_bytes(rec_bytes)
    if not _synthetic_fixture_mode:
        if (
            len(rec_bytes) != CORRECTIVE_REPLAY_01_RECEIPT_JSON_BYTES
            or rec_sha != CORRECTIVE_REPLAY_01_RECEIPT_JSON_SHA256
        ):
            raise PermissionError(
                "CORRECTIVE_REPLAY_01_BLOCKED_APPROVAL_RECEIPT_HASH_MISMATCH: "
                f"({len(rec_bytes)} B, {rec_sha}) != expected "
                f"({CORRECTIVE_REPLAY_01_RECEIPT_JSON_BYTES} B, {CORRECTIVE_REPLAY_01_RECEIPT_JSON_SHA256})."
            )

    try:
        rec_obj = json.loads(rec_bytes.decode("utf-8"))
    except Exception as exc:
        raise PermissionError(
            f"CORRECTIVE_REPLAY_01_BLOCKED_MALFORMED_RECEIPT_JSON: {exc}"
        ) from exc

    if not isinstance(rec_obj, dict):
        raise PermissionError("CORRECTIVE_REPLAY_01_BLOCKED_RECEIPT_NOT_JSON_OBJECT")

    # Reject non-executable draft proposal permits and legacy unsigned drafts
    if (
        "_proposal_status" in rec_obj
        or rec_obj.get("owner_chat_authorized_for_replay") is False
        or rec_obj.get("schema_version")
        == "GOMATE_W07_STUB01_05_CORRECTIVE_REPLAY_PROPOSAL_V1"
    ):
        raise PermissionError(
            "CORRECTIVE_REPLAY_01_BLOCKED_PROPOSAL_DRAFT_NOT_AUTHORIZED: "
            "the prior non-executable proposal draft cannot unlock execution."
        )

    if rec_obj.get("schema_version") != CORRECTIVE_REPLAY_01_SCHEMA_V1:
        raise PermissionError(
            "CORRECTIVE_REPLAY_01_BLOCKED_INVALID_SCHEMA: "
            f"expected {CORRECTIVE_REPLAY_01_SCHEMA_V1!r}, got {rec_obj.get('schema_version')!r}."
        )
    if rec_obj.get("replay_id") != CORRECTIVE_REPLAY_01_ID:
        raise PermissionError("CORRECTIVE_REPLAY_01_BLOCKED_REPLAY_ID_MISMATCH")
    if rec_obj.get("auth_mode") != CORRECTIVE_REPLAY_01_AUTH_MODE:
        raise PermissionError("CORRECTIVE_REPLAY_01_BLOCKED_AUTH_MODE_MISMATCH")
    if rec_obj.get("decision_id") != CORRECTIVE_REPLAY_01_DECISION_ID:
        raise PermissionError("CORRECTIVE_REPLAY_01_BLOCKED_DECISION_ID_MISMATCH")
    if rec_obj.get("authorization_status") != CORRECTIVE_REPLAY_01_AUTHORIZATION_STATUS:
        raise PermissionError("CORRECTIVE_REPLAY_01_BLOCKED_AUTH_STATUS_MISMATCH")
    if (
        rec_obj.get("authorization_assurance")
        != CORRECTIVE_REPLAY_01_AUTHORIZATION_ASSURANCE
    ):
        raise PermissionError("CORRECTIVE_REPLAY_01_BLOCKED_AUTH_ASSURANCE_MISMATCH")
    if rec_obj.get("authorizes_once") is not True:
        raise PermissionError("CORRECTIVE_REPLAY_01_BLOCKED_AUTHORIZES_ONCE_NOT_TRUE")
    if rec_obj.get("max_successful_or_failed_replay_attempts") != 1:
        raise PermissionError("CORRECTIVE_REPLAY_01_BLOCKED_MAX_ATTEMPTS_MUST_BE_1")
    if rec_obj.get("one_shot_stop_on_failure") is not True:
        raise PermissionError("CORRECTIVE_REPLAY_01_BLOCKED_STOP_ON_FAILURE_MUST_BE_TRUE")
    if rec_obj.get("preserve_historical_first_run") is not True:
        raise PermissionError(
            "CORRECTIVE_REPLAY_01_BLOCKED_PRESERVE_HISTORICAL_MUST_BE_TRUE"
        )
    if rec_obj.get("prechecks_required") is not True:
        raise PermissionError("CORRECTIVE_REPLAY_01_BLOCKED_PRECHECKS_MUST_BE_TRUE")
    if rec_obj.get("allowed_stubs") != list(ALLOWED_READONLY_STUB_IDS):
        raise PermissionError(
            f"CORRECTIVE_REPLAY_01_BLOCKED_INVALID_ALLOWED_STUBS: {rec_obj.get('allowed_stubs')!r}"
        )
    if any(s not in rec_obj["allowed_stubs"] for s in stubs_list):
        raise PermissionError("CORRECTIVE_REPLAY_01_BLOCKED_STUB_NOT_ALLOWED")

    corpus_meta = rec_obj.get("corpus")
    if corpus_meta != {
        "arm": "P",
        "b1b_count": 97,
        "count": EXPECTED_ELIGIBLE_DOC_COUNT,
        "osm_count": 40,
    }:
        raise PermissionError(
            f"CORRECTIVE_REPLAY_01_BLOCKED_CORPUS_SPEC_MISMATCH: {corpus_meta!r}"
        )

    for forbidden_flag in (
        "corpus_writes_authorized",
        "final50_dev_t0_authorized",
        "formal_g3_g4_authorized",
        "full_g15_closed",
        "network_authorized",
        "paid_api_authorized",
        "repo_push_pr_merge_authorized",
        "stub06_authorized",
    ):
        if rec_obj.get(forbidden_flag) is not False:
            raise PermissionError(
                f"CORRECTIVE_REPLAY_01_BLOCKED_SCOPE_ESCALATION_FORBIDDEN: {forbidden_flag} must be False."
            )
    if rec_obj.get("od_g15_05") != "HOLD":
        raise PermissionError("CORRECTIVE_REPLAY_01_BLOCKED_OD_G15_05_MUST_BE_HOLD")

    baseline = rec_obj.get("baseline_sha256")
    if not isinstance(baseline, dict) or baseline != PINNED_REPLAY_01_BASELINE_SHA256:
        raise PermissionError(
            "CORRECTIVE_REPLAY_01_BLOCKED_BASELINE_SHA256_MISMATCH: receipt baseline_sha256 "
            "does not match exact pinned 13-entry digest table."
        )

    # Verify exact live source module hashes (`chunker_c1.py`, `real_corpus_preflight.py`,
    # `visibility.py`, `runner.py`) directly on disk against pinned receipt digests.
    pkg_dir = Path(__file__).resolve().parent
    src_hash_targets = (
        ("chunker_c1.py", frozenset({PINNED_CHUNKER_C1_CORRECTED_SHA256})),
        ("real_corpus_preflight.py", ALLOWED_ON_DISK_PREFLIGHT_SHA256S),
        ("visibility.py", frozenset({PINNED_VISIBILITY_UNCHANGED_SHA256})),
        ("runner.py", frozenset({PINNED_FORMAL_RUNNER_UNCHANGED_SHA256})),
    )
    actual_src_hashes: Dict[str, str] = {}
    for fname, allowed_shas in src_hash_targets:
        sp = pkg_dir / fname
        if not sp.is_file() or sp.is_symlink():
            raise PermissionError(f"CORRECTIVE_REPLAY_01_BLOCKED_MISSING_SRC: {sp}")
        act = _sha256_file(sp)
        actual_src_hashes[fname] = act
        if act not in allowed_shas:
            raise PermissionError(
                f"CORRECTIVE_REPLAY_01_BLOCKED_SRC_SHA256_MISMATCH for {fname}: "
                f"{act} not in {sorted(allowed_shas)}."
            )

    # Verify Scientific Protocol v1.0 LF SHA-256
    proto_p = _require_clean_file(
        protocol_v1_path, "CORRECTIVE_REPLAY_01_BLOCKED_MISSING_PROTOCOL_V1"
    )
    proto_lf_sha = _sha256_bytes(proto_p.read_bytes().replace(b"\r\n", b"\n"))
    if proto_lf_sha != PROTOCOL_V1_0_LF_SHA256:
        raise PermissionError(
            "CORRECTIVE_REPLAY_01_BLOCKED_PROTOCOL_SHA256_MISMATCH: "
            f"{proto_lf_sha} != {PROTOCOL_V1_0_LF_SHA256}."
        )

    # Verify preserved historical first-run failure receipts are intact
    hist_dir = Path(historical_run_dir)
    hist_targets = (
        ("execution_summary.json", PINNED_PREVIOUS_REAL_RUN_SUMMARY_SHA256),
        ("stub_01_result.json", PINNED_PREVIOUS_STUB01_PASS_SHA256),
        ("stub_02_result.json", PINNED_PREVIOUS_STUB02_FAIL_SHA256),
    )
    for fname, exp_sha in hist_targets:
        hp = _require_clean_file(
            hist_dir / fname,
            f"CORRECTIVE_REPLAY_01_BLOCKED_MISSING_HISTORICAL_{fname}",
        )
        act_h = _sha256_file(hp)
        if act_h != exp_sha:
            raise PermissionError(
                f"CORRECTIVE_REPLAY_01_BLOCKED_HISTORICAL_HASH_MISMATCH for {fname}: "
                f"{act_h} != {exp_sha}."
            )

    if not _synthetic_fixture_mode:
        prev_zip_p = _require_clean_file(
            previous_real_run_zip_path,
            "CORRECTIVE_REPLAY_01_BLOCKED_MISSING_PREVIOUS_RUN_ZIP",
        )
        if _sha256_file(prev_zip_p) != PINNED_PREVIOUS_REAL_RUN_ZIP_SHA256:
            raise PermissionError(
                "CORRECTIVE_REPLAY_01_BLOCKED_PREVIOUS_RUN_ZIP_HASH_MISMATCH"
            )
        prior_corr_zip_p = _require_clean_file(
            prior_c1_corrective_zip_path,
            "CORRECTIVE_REPLAY_01_BLOCKED_MISSING_PRIOR_CORRECTIVE_ZIP",
        )
        if _sha256_file(prior_corr_zip_p) != PINNED_PRIOR_C1_CORRECTIVE_ZIP_SHA256:
            raise PermissionError(
                "CORRECTIVE_REPLAY_01_BLOCKED_PRIOR_CORRECTIVE_ZIP_HASH_MISMATCH"
            )

    # Check output directory freshness & path binding (prevents replay #02 or overwriting)
    approved_out_raw = rec_obj.get("output_directory")
    if type(approved_out_raw) is not str or not approved_out_raw.strip():
        raise PermissionError("CORRECTIVE_REPLAY_01_BLOCKED_MISSING_OUTPUT_DIR_IN_RECEIPT")
    resolved_out = _assert_fresh_unused_output_dir(
        output_dir=Path(output_dir),
        approved_output_dir_str=approved_out_raw,
        historical_run_dir=hist_dir,
        synthetic_fixture_mode=_synthetic_fixture_mode,
    )

    # Delegate underlying Annex v0.2.2, Tech Freeze, Waiver, Stage A manifest & 7-artifact
    # checks to unmodified real_corpus_preflight.validate_stub01_05_readonly_preflight_gate.
    underlying_gates: Dict[str, Any] = {}
    for stub_id in stubs_list:
        underlying_gates[stub_id] = validate_stub01_05_readonly_preflight_gate(
            requested_stub_id=stub_id,
            annex_v0_2_2_path=annex_v0_2_2_path,
            tech_freeze_receipt_path=tech_freeze_receipt_path,
            stub_auth_receipt_path=owner_chat_policy_receipt_path,
            corpus_bundle_manifest_path=corpus_bundle_manifest_path,
            auth_mode="OWNER_CHAT_READONLY_V1",
            chat_auth_waiver_path=chat_auth_waiver_path,
            original_exec_decision_path=original_exec_decision_path,
            _synthetic_fixture_mode=_synthetic_fixture_mode,
        )

    # Also verify exact Stage A SHA-256 + 7 frozen artifacts explicitly in live mode
    verified_artifacts_info: List[Dict[str, Any]] = []
    bundle_p = Path(corpus_bundle_manifest_path)  # verified non-None above
    if not _synthetic_fixture_mode:
        if _sha256_file(bundle_p) != PINNED_STAGE_A_CORPUS_BUNDLE_MANIFEST_SHA256:
            raise PermissionError("CORRECTIVE_REPLAY_01_BLOCKED_STAGE_A_MANIFEST_HASH")
        bundle_obj = json.loads(bundle_p.read_text(encoding="utf-8"))
        verified_artifacts_info = _verify_bundle_artifacts_against_pinned_specs(
            corpus_bundle_manifest_path=bundle_p,
            bundle_obj=bundle_obj,
            expected_artifact_count=7,
            expected_pinned_artifacts=PINNED_LIVE_137_CORPUS_7_ARTIFACTS,
        )

    return {
        "replay_id": CORRECTIVE_REPLAY_01_ID,
        "auth_mode": CORRECTIVE_REPLAY_01_AUTH_MODE,
        "decision_id": CORRECTIVE_REPLAY_01_DECISION_ID,
        "authorization_assurance": CORRECTIVE_REPLAY_01_AUTHORIZATION_ASSURANCE,
        "identity_authentication": "NOT_CRYPTOGRAPHICALLY_VERIFIED",
        "replay_decision_sha256": dec_sha,
        "replay_approval_receipt_sha256": rec_sha,
        "approved_annex_v0_2_2_sha256": APPROVED_ANNEX_V0_2_2_SHA256,
        "tech_freeze_receipt_sha256": APPROVED_TECH_FREEZE_RECEIPT_SHA256,
        "owner_chat_waiver_sha256": OWNER_CHAT_AUTH_WAIVER_MD_SHA256,
        "owner_chat_policy_receipt_sha256": underlying_gates[stubs_list[0]][
            "policy_receipt_sha256"
        ],
        "protocol_v1_lf_sha256": proto_lf_sha,
        "stage_a_manifest_sha256": _sha256_file(bundle_p),
        "verified_source_sha256": actual_src_hashes,
        "verified_7_artifacts_count": len(verified_artifacts_info),
        "output_directory": str(resolved_out),
        "historical_first_run_dir": str(hist_dir.resolve()),
        "trust_anchor_mode": (
            "SYNTHETIC_FIXTURE_CORRECTIVE_REPLAY_TEST_ONLY"
            if _synthetic_fixture_mode
            else "OWNER_CHAT_READONLY_V1_CORRECTIVE_REPLAY_01_LOCAL_HOST"
        ),
    }


def run_corrective_replay_01(
    *,
    output_dir: Path,
    replay_decision_path: Path,
    replay_approval_receipt_path: Path,
    annex_v0_2_2_path: Path,
    tech_freeze_receipt_path: Path,
    owner_chat_policy_receipt_path: Path,
    chat_auth_waiver_path: Path,
    corpus_bundle_manifest_path: Path,
    protocol_v1_path: Path,
    original_exec_decision_path: Optional[Path] = None,
    historical_run_dir: Path = PINNED_HISTORICAL_FIRST_RUN_DIR,
    previous_real_run_zip_path: Optional[Path] = None,
    prior_c1_corrective_zip_path: Optional[Path] = None,
    snapshot_dir: Optional[Path] = None,
    expectations: CorpusPreflightExpectations = LIVE_137_CORPUS_EXPECTATIONS,
    _synthetic_fixture_mode: bool = False,
) -> Dict[str, Any]:
    """Execute one offline read-only pass of STUB-01..STUB-05 under CORRECTIVE_REPLAY_01."""
    replay_wall_t0 = time.perf_counter()
    replay_cpu_t0 = time.process_time()

    gate_info = validate_corrective_replay_01_gate(
        requested_stubs=ALLOWED_READONLY_STUB_IDS,
        output_dir=output_dir,
        replay_decision_path=replay_decision_path,
        replay_approval_receipt_path=replay_approval_receipt_path,
        annex_v0_2_2_path=annex_v0_2_2_path,
        tech_freeze_receipt_path=tech_freeze_receipt_path,
        owner_chat_policy_receipt_path=owner_chat_policy_receipt_path,
        chat_auth_waiver_path=chat_auth_waiver_path,
        original_exec_decision_path=original_exec_decision_path,
        corpus_bundle_manifest_path=corpus_bundle_manifest_path,
        protocol_v1_path=protocol_v1_path,
        historical_run_dir=historical_run_dir,
        previous_real_run_zip_path=previous_real_run_zip_path,
        prior_c1_corrective_zip_path=prior_c1_corrective_zip_path,
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
        execution_id = f"{CORRECTIVE_REPLAY_01_ID}__{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"

        common_kwargs: Dict[str, Any] = {
            "annex_v0_2_2_path": annex_v0_2_2_path,
            "tech_freeze_receipt_path": tech_freeze_receipt_path,
            "stub_auth_receipt_path": owner_chat_policy_receipt_path,
            "corpus_bundle_manifest_path": corpus_bundle_manifest_path,
            "expectations": expectations,
            "auth_mode": "OWNER_CHAT_READONLY_V1",
            "chat_auth_waiver_path": chat_auth_waiver_path,
            "original_exec_decision_path": original_exec_decision_path,
            "_synthetic_fixture_mode": _synthetic_fixture_mode,
        }

        stub_dispatch: Sequence[Tuple[str, str, Callable[[], Dict[str, Any]]]] = (
            (
                "STUB-01",
                "stub_01_result.json",
                lambda: execute_stub01_fx01_hash_and_arm_p_counts(**common_kwargs),
            ),
            (
                "STUB-02",
                "stub_02_result.json",
                lambda: execute_stub02_fx02_canonical_conservation(
                    **common_kwargs, snapshot_dir=snapshot_dir
                ),
            ),
            (
                "STUB-03",
                "stub_03_result.json",
                lambda: execute_stub03_fx03_audit_tags_and_v_hash(**common_kwargs),
            ),
            (
                "STUB-04",
                "stub_04_result.json",
                lambda: execute_stub04_fx04_c1_token_ceiling(
                    **common_kwargs, snapshot_dir=snapshot_dir
                ),
            ),
            (
                "STUB-05",
                "stub_05_result.json",
                lambda: execute_stub05_fx05_overture_visibility(
                    **common_kwargs, snapshot_dir=snapshot_dir
                ),
            ),
        )

        per_stub_records: List[Dict[str, Any]] = []
        all_passed = True
        stopped_on_stub: Optional[str] = None

        for stub_id, filename, fn in stub_dispatch:
            started_at = _utc_iso_now()
            w0 = time.perf_counter()
            c0 = time.process_time()
            try:
                raw_metrics = fn()
                completed_at = _utc_iso_now()
                elapsed_s = round(time.perf_counter() - w0, 4)
                cpu_s = round(time.process_time() - c0, 4)
                metrics_body = {
                    k: v for k, v in raw_metrics.items() if k != "gate"
                }
                ev_sha = _sha256_bytes(
                    json.dumps(
                        metrics_body, ensure_ascii=False, sort_keys=True
                    ).encode("utf-8")
                )
                stub_payload: Dict[str, Any] = {
                    "execution_id": execution_id,
                    "replay_id": CORRECTIVE_REPLAY_01_ID,
                    "stub_id": stub_id,
                    "status": "PASS",
                    "metrics": metrics_body,
                    "evidence_sha256": ev_sha,
                    "chunker_c1_sha256": gate_info["verified_source_sha256"][
                        "chunker_c1.py"
                    ],
                    "real_corpus_preflight_sha256": gate_info["verified_source_sha256"][
                        "real_corpus_preflight.py"
                    ],
                    "manifest_sha256": gate_info["stage_a_manifest_sha256"],
                    "error_code": None,
                    "started_at": started_at,
                    "completed_at": completed_at,
                    "elapsed_seconds": elapsed_s,
                    "cpu_seconds": cpu_s,
                }
            except Exception as exc:
                completed_at = _utc_iso_now()
                elapsed_s = round(time.perf_counter() - w0, 4)
                cpu_s = round(time.process_time() - c0, 4)
                err_msg = f"{type(exc).__name__}: {exc}"
                ev_sha = _sha256_bytes(err_msg.encode("utf-8"))
                stub_payload = {
                    "execution_id": execution_id,
                    "replay_id": CORRECTIVE_REPLAY_01_ID,
                    "stub_id": stub_id,
                    "status": "FAIL",
                    "metrics": {},
                    "evidence_sha256": ev_sha,
                    "chunker_c1_sha256": gate_info["verified_source_sha256"][
                        "chunker_c1.py"
                    ],
                    "real_corpus_preflight_sha256": gate_info["verified_source_sha256"][
                        "real_corpus_preflight.py"
                    ],
                    "manifest_sha256": gate_info["stage_a_manifest_sha256"],
                    "error_code": err_msg,
                    "started_at": started_at,
                    "completed_at": completed_at,
                    "elapsed_seconds": elapsed_s,
                    "cpu_seconds": cpu_s,
                }
                all_passed = False
                stopped_on_stub = stub_id

            stub_bytes = (
                json.dumps(stub_payload, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n"
            ).encode("utf-8")
            (out_p / filename).write_bytes(stub_bytes)
            per_stub_records.append(
                {
                    "stub_id": stub_id,
                    "result_file": filename,
                    "status": stub_payload["status"],
                    "evidence_sha256": stub_payload["evidence_sha256"],
                    "result_file_sha256": _sha256_bytes(stub_bytes),
                    "error_code": stub_payload["error_code"],
                    "elapsed_seconds": elapsed_s,
                    "cpu_seconds": cpu_s,
                }
            )
            if not all_passed:
                break

        total_elapsed_s = round(time.perf_counter() - replay_wall_t0, 4)
        total_cpu_s = round(time.process_time() - replay_cpu_t0, 4)
        replay_status = "EXECUTED_ONCE_PASS" if all_passed else "EXECUTED_ONCE_FAIL"

        summary_obj: Dict[str, Any] = {
            "schema_version": "W07_CORRECTIVE_REPLAY_01_EXECUTION_SUMMARY_V1",
            "execution_id": execution_id,
            "replay_id": CORRECTIVE_REPLAY_01_ID,
            "decision_id": CORRECTIVE_REPLAY_01_DECISION_ID,
            "auth_mode": CORRECTIVE_REPLAY_01_AUTH_MODE,
            "authorization_assurance": CORRECTIVE_REPLAY_01_AUTHORIZATION_ASSURANCE,
            "identity_authentication": "NOT_CRYPTOGRAPHICALLY_VERIFIED",
            "overall_status": replay_status,
            "stopped_on_stub": stopped_on_stub,
            "executed_stub_count": len(per_stub_records),
            "replay_consumed_guard": {
                "single_use_consumed": True,
                "future_auto_replay_blocked": True,
            },
            "bindings": {
                "replay_decision_sha256": gate_info["replay_decision_sha256"],
                "replay_approval_receipt_sha256": gate_info[
                    "replay_approval_receipt_sha256"
                ],
                "approved_annex_v0_2_2_sha256": APPROVED_ANNEX_V0_2_2_SHA256,
                "tech_freeze_receipt_sha256": APPROVED_TECH_FREEZE_RECEIPT_SHA256,
                "owner_chat_waiver_sha256": OWNER_CHAT_AUTH_WAIVER_MD_SHA256,
                "owner_chat_policy_receipt_sha256": gate_info[
                    "owner_chat_policy_receipt_sha256"
                ],
                "protocol_v1_lf_sha256": gate_info["protocol_v1_lf_sha256"],
                "stage_a_manifest_sha256": gate_info["stage_a_manifest_sha256"],
                "source_sha256": gate_info["verified_source_sha256"],
                "corrective_replay_01_module_sha256": _sha256_file(
                    Path(__file__).resolve()
                ),
            },
            "preserved_historical_first_run": {
                "historical_run_dir": gate_info["historical_first_run_dir"],
                "execution_summary_sha256": PINNED_PREVIOUS_REAL_RUN_SUMMARY_SHA256,
                "stub_01_result_sha256": PINNED_PREVIOUS_STUB01_PASS_SHA256,
                "stub_02_result_sha256": PINNED_PREVIOUS_STUB02_FAIL_SHA256,
                "audit_zip_sha256": PINNED_PREVIOUS_REAL_RUN_ZIP_SHA256,
                "prior_c1_corrective_zip_sha256": PINNED_PRIOR_C1_CORRECTIVE_ZIP_SHA256,
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
            "stubs": per_stub_records,
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
