#!/usr/bin/env python3
"""Post-Live Repository Lifecycle & Immutable Evidence Verifier for W06 Amendment-01 Canary Live Execution 01.

Task ID:
    `W06-POST-LIVE-REPOSITORY-LIFECYCLE-COMPATIBILITY-CORRECTIVE-01`

Purpose:
    1. Encode the explicit two-state repository lifecycle model (Section 5):
       - `PRE_EXECUTION`: Canonical canary live output root
         (`data/evaluation/w06/live_amendment_01_canary_v1`) is absent prior to the one-shot live run.
       - `POST_EXECUTION_EVIDENCE_PRESENT`: Canonical canary live output root is present after the
         authorized one-shot live run (`W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-CANARY-LIVE-EXECUTION-01`,
         PR #75, evidence commit `f7d3225dc02e9cf8cd34e7142f3d6c242d25a993`) and matches the exact
         9-file cryptographically frozen fail-stopped evidence tree.
    2. Provide stateless, fail-closed cryptographic verification of PR #75 live evidence (Section 11):
       - Exact 9 relative file paths and exact SHA256 hashes (zero extra files, zero extra cell dirs,
         cells 2..9 unscheduled);
       - Exact `canary_batch_execution_summary_v1.json` SHA256
         (`d16a3f5f49101914a584045bee2e7470e4dee7eb7aa106c7e9409b1d3d77a8ec`);
       - Exact Cell 1 `canary_cell_evidence_receipt.json` SHA256
         (`1456833419e4ba76bd52be9f3e4444724febc52e24e08ff30c808379596442c6`);
       - Exact fail-stop operational semantics (`007 / C1`, `gemini-3.8-flash`, `TIMEOUT`, `504 DEADLINE_EXCEEDED`,
         1 logical invocation, 1 HTTP request, 0 retries, 8 unscheduled cells, `ALL_9_CANARY_OPERATIONAL_PASS = false`);
       - Downstream firewalls (`AMENDED_COMPARATIVE_LIVE_AUTHORIZED = false`, `COMPARATIVE_EXECUTED = false`,
         `MODEL_WINNER_SELECTED = false`, `SELECTED_MODEL_ID = null`, `STOCHASTICITY_EXECUTION_STARTED = false`,
         `FINAL100_USED = false`, `FINAL100_STATUS = "NO-GO"`);
       - Secret-free check across all 9 files.
    3. Provide phase/namespace-aware scope and verification helpers (`is_path_in_downstream_w06_amendment_01_canary_live_evidence_scope`,
       `is_verified_downstream_w06_amendment_01_canary_live_evidence_tree`,
       `is_verified_downstream_w06_amendment_01_canary_live_evidence_file`) so historical pre-live
       phase guards do not misinterpret verified downstream Amendment-01 canary evidence as a retroactive
       violation of earlier phases, while still failing closed on any unauthorized or tampered file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
AI_SERVICE_ROOT = REPO_ROOT / "apps" / "ai-service"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for _p in (AI_SERVICE_ROOT, SCRIPTS_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from app.evaluation.dev_live_runner import (  # noqa: E402
    PlanBeforeLiveProtocolError,
)
from app.evaluation.dev_selection_harness import (  # noqa: E402
    ImmutableCellExecutionError,
    canonical_json_bytes,
    normalize_lf_bytes,
    sha256_bytes,
)

# ==============================================================================
# 1. FROZEN LIFECYCLE & PR #75 LIVE EVIDENCE CONSTANTS (SECTIONS 0, 5, 11)
# ==============================================================================

TASK_ID = "W06-POST-LIVE-REPOSITORY-LIFECYCLE-COMPATIBILITY-CORRECTIVE-01"
LIVE_EXECUTION_TASK_ID = (
    "W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-CANARY-LIVE-EXECUTION-01"
)
LIVE_EVIDENCE_PR_NUMBER = 75
LIVE_EVIDENCE_COMMIT_SHA = "f7d3225dc02e9cf8cd34e7142f3d6c242d25a993"
LIVE_EVIDENCE_BASE_DEVELOP_SHA = "4d631da5b5d439d54e511c3561d5e2584765033c"

LIFECYCLE_PRE_EXECUTION = "PRE_EXECUTION"
LIFECYCLE_POST_EXECUTION_EVIDENCE_PRESENT = "POST_EXECUTION_EVIDENCE_PRESENT"

CANARY_LIVE_EVIDENCE_OUTPUT_ROOT_REL_PATH = (
    "data/evaluation/w06/live_amendment_01_canary_v1"
)
CANARY_BATCH_SUMMARY_REL_PATH = (
    "data/evaluation/w06/live_amendment_01_canary_v1/"
    "canary_batch_execution_summary_v1.json"
)
CANARY_CELL_01_ID = "W06-AMENDMENT-01-CANARY-01-P1-C1-W06-DEV-TUNE-007"
CANARY_CELL_01_DIR_REL_PATH = (
    f"{CANARY_LIVE_EVIDENCE_OUTPUT_ROOT_REL_PATH}/{CANARY_CELL_01_ID}"
)
CANARY_CELL_01_RECEIPT_REL_PATH = (
    f"{CANARY_CELL_01_DIR_REL_PATH}/canary_cell_evidence_receipt.json"
)

EXPECTED_CANARY_BATCH_SUMMARY_SHA256 = (
    "d16a3f5f49101914a584045bee2e7470e4dee7eb7aa106c7e9409b1d3d77a8ec"
)
EXPECTED_CANARY_CELL_01_RECEIPT_SHA256 = (
    "1456833419e4ba76bd52be9f3e4444724febc52e24e08ff30c808379596442c6"
)

EXPECTED_CANARY_LIVE_EXECUTION_01_EVIDENCE_FILE_SHA256S: dict[str, str] = {
    "data/evaluation/w06/live_amendment_01_canary_v1/canary_batch_execution_summary_v1.json": (
        "d16a3f5f49101914a584045bee2e7470e4dee7eb7aa106c7e9409b1d3d77a8ec"
    ),
    "data/evaluation/w06/live_amendment_01_canary_v1/W06-AMENDMENT-01-CANARY-01-P1-C1-W06-DEV-TUNE-007/canary_cell_evidence_receipt.json": (
        "1456833419e4ba76bd52be9f3e4444724febc52e24e08ff30c808379596442c6"
    ),
    "data/evaluation/w06/live_amendment_01_canary_v1/W06-AMENDMENT-01-CANARY-01-P1-C1-W06-DEV-TUNE-007/diagnostic_evaluation.json": (
        "fd66de87664c5dbc24adab8c58c7457408e62ca72280f091f52d9d157aef57ff"
    ),
    "data/evaluation/w06/live_amendment_01_canary_v1/W06-AMENDMENT-01-CANARY-01-P1-C1-W06-DEV-TUNE-007/provider_response_metadata.json": (
        "5a3a345baa1bbb116f10a1759801b9d45a22d8d632cdf2b38572aadad438a885"
    ),
    "data/evaluation/w06/live_amendment_01_canary_v1/W06-AMENDMENT-01-CANARY-01-P1-C1-W06-DEV-TUNE-007/raw_provider_response.txt": (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    ),
    "data/evaluation/w06/live_amendment_01_canary_v1/W06-AMENDMENT-01-CANARY-01-P1-C1-W06-DEV-TUNE-007/raw_usage_metadata.json": (
        "6a40b68c53cc49e8f49c22ef79f97dafe36a57f3ed4615eb32e15d0e56d2f9de"
    ),
    "data/evaluation/w06/live_amendment_01_canary_v1/W06-AMENDMENT-01-CANARY-01-P1-C1-W06-DEV-TUNE-007/request_manifest.json": (
        "360db1d7f655705379e3879bcdb0868d772688c5a3e1089a0d3a020e48e61db6"
    ),
    "data/evaluation/w06/live_amendment_01_canary_v1/W06-AMENDMENT-01-CANARY-01-P1-C1-W06-DEV-TUNE-007/transport_journal_completed.json": (
        "f0946e08a666bee2f67776e59696ed3e4e4e433bdc76913ee29fc948f442a78a"
    ),
    "data/evaluation/w06/live_amendment_01_canary_v1/W06-AMENDMENT-01-CANARY-01-P1-C1-W06-DEV-TUNE-007/transport_journal_starting.json": (
        "f8d4fd09fb20f001314ca16bc8133aef0a359a09a6cf1e15e4cecd79d5ac4a7d"
    ),
}

EXPECTED_UNSCHEDULED_CELL_IDS: tuple[str, ...] = (
    "W06-AMENDMENT-01-CANARY-02-P1-C2-W06-DEV-TUNE-007",
    "W06-AMENDMENT-01-CANARY-03-P1-C3-W06-DEV-TUNE-007",
    "W06-AMENDMENT-01-CANARY-04-P1-C1-W06-DEV-TUNE-011",
    "W06-AMENDMENT-01-CANARY-05-P1-C2-W06-DEV-TUNE-011",
    "W06-AMENDMENT-01-CANARY-06-P1-C3-W06-DEV-TUNE-011",
    "W06-AMENDMENT-01-CANARY-07-P1-C1-W06-DEV-TUNE-015",
    "W06-AMENDMENT-01-CANARY-08-P1-C2-W06-DEV-TUNE-015",
    "W06-AMENDMENT-01-CANARY-09-P1-C3-W06-DEV-TUNE-015",
)

_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"AIza[0-9A-Za-z\-_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9\-_]{20,}"),
    re.compile(r"sk-ant-[A-Za-z0-9\-_]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9\-_\.]{16,}", re.IGNORECASE),
)


# ==============================================================================
# 2. SCOPE & STATELESS CRYPTOGRAPHIC VERIFICATION HELPERS (SECTIONS 7, 11)
# ==============================================================================


def is_path_in_downstream_w06_amendment_01_canary_live_evidence_scope(
    path: Path,
    *,
    repo_root: Path = REPO_ROOT,
) -> bool:
    """Return True if `path` is inside `data/evaluation/w06/live_amendment_01_canary_v1`.

    NOTE: This helper checks path scope ONLY and never grants an exemption by itself.
    Any exemption MUST be gated by
    `is_verified_downstream_w06_amendment_01_canary_live_evidence_tree(repo_root)`.
    """
    try:
        rel_posix = path.relative_to(repo_root).as_posix()
    except ValueError:
        try:
            rel_posix = path.resolve().relative_to(repo_root.resolve()).as_posix()
        except Exception:
            return False

    return rel_posix == CANARY_LIVE_EVIDENCE_OUTPUT_ROOT_REL_PATH or rel_posix.startswith(
        f"{CANARY_LIVE_EVIDENCE_OUTPUT_ROOT_REL_PATH}/"
    )


def verify_w06_amendment_01_canary_live_execution_01_evidence_tree(
    repo_root: Path = REPO_ROOT,
    *,
    output_root_override: Path | None = None,
) -> dict[str, Any]:
    """Statelessly verify the PR #75 one-shot live canary evidence directory on disk (Section 11).

    Raises `PlanBeforeLiveProtocolError` on any missing file, extra file, extra cell directory,
    SHA256 mismatch, semantic drift, secret leak, or downstream firewall violation.
    """
    output_root = output_root_override or (
        repo_root / CANARY_LIVE_EVIDENCE_OUTPUT_ROOT_REL_PATH
    )
    if not output_root.is_dir():
        raise PlanBeforeLiveProtocolError(
            f"CANARY_LIVE_EVIDENCE_OUTPUT_ROOT_MISSING: {output_root}"
        )

    # 1. Verify no unscheduled cell directories exist
    for unscheduled_id in EXPECTED_UNSCHEDULED_CELL_IDS:
        unscheduled_dir = output_root / unscheduled_id
        if unscheduled_dir.exists():
            raise PlanBeforeLiveProtocolError(
                f"UNSCHEDULED_CANARY_CELL_DIR_FORBIDDEN: {unscheduled_dir}"
            )

    # 2. Verify exact directory children at root (only `canary_batch_execution_summary_v1.json` and Cell 01 dir)
    root_children = sorted(p.name for p in output_root.iterdir())
    expected_root_children = sorted(
        ["canary_batch_execution_summary_v1.json", CANARY_CELL_01_ID]
    )
    if root_children != expected_root_children:
        raise PlanBeforeLiveProtocolError(
            f"CANARY_LIVE_EVIDENCE_ROOT_CHILDREN_MISMATCH: expected={expected_root_children}, got={root_children}"
        )

    # 3. Collect all files under output_root and map to canonical relative paths
    observed_files = sorted(p for p in output_root.rglob("*") if p.is_file())
    observed_hashes: dict[str, str] = {}
    for file_path in observed_files:
        rel_inside = file_path.relative_to(output_root).as_posix()
        canonical_rel = f"{CANARY_LIVE_EVIDENCE_OUTPUT_ROOT_REL_PATH}/{rel_inside}"
        raw_bytes = normalize_lf_bytes(file_path.read_bytes())
        observed_hashes[canonical_rel] = sha256_bytes(raw_bytes)
        text_content = raw_bytes.decode("utf-8", errors="replace")
        for pat in _SECRET_PATTERNS:
            if pat.search(text_content):
                raise PlanBeforeLiveProtocolError(
                    f"SECRET_LEAK_IN_CANARY_EVIDENCE: pattern={pat.pattern} in {canonical_rel}"
                )

    if set(observed_hashes.keys()) != set(
        EXPECTED_CANARY_LIVE_EXECUTION_01_EVIDENCE_FILE_SHA256S.keys()
    ):
        raise PlanBeforeLiveProtocolError(
            "CANARY_LIVE_EVIDENCE_FILE_SET_MISMATCH: "
            f"expected={sorted(EXPECTED_CANARY_LIVE_EXECUTION_01_EVIDENCE_FILE_SHA256S.keys())}, "
            f"got={sorted(observed_hashes.keys())}"
        )

    for rel_path, expected_sha in EXPECTED_CANARY_LIVE_EXECUTION_01_EVIDENCE_FILE_SHA256S.items():
        actual_sha = observed_hashes[rel_path]
        if actual_sha != expected_sha:
            raise PlanBeforeLiveProtocolError(
                f"CANARY_LIVE_EVIDENCE_FILE_SHA256_MISMATCH: path={rel_path}, "
                f"expected={expected_sha}, got={actual_sha}"
            )

    # 4. Verify batch summary & cell 1 receipt JSON semantics and downstream firewalls
    summary_path = output_root / "canary_batch_execution_summary_v1.json"
    cell01_receipt_path = (
        output_root / CANARY_CELL_01_ID / "canary_cell_evidence_receipt.json"
    )
    summary_obj = json.loads(summary_path.read_text(encoding="utf-8"))
    cell01_obj = json.loads(cell01_receipt_path.read_text(encoding="utf-8"))

    if (
        summary_obj.get("execution_mode") != "LIVE_CANARY_EXECUTION"
        or summary_obj.get("runtime_head_sha") != LIVE_EVIDENCE_BASE_DEVELOP_SHA
        or summary_obj.get("total_assigned_canary_cells") != 9
        or summary_obj.get("attempted_cells_count") != 1
        or summary_obj.get("unscheduled_cells_count") != 8
        or summary_obj.get("operational_pass_cells_count") != 0
        or summary_obj.get("operational_pass_fraction") != "0/9"
        or summary_obj.get("fail_stop_triggered") is not True
        or summary_obj.get("stopped_at_order_index") != 1
        or summary_obj.get("stopped_at_cell_id") != CANARY_CELL_01_ID
        or summary_obj.get("stopped_at_short_label") != "007 / C1"
        or summary_obj.get("total_logical_generation_invocations") != 1
        or summary_obj.get("total_actual_provider_http_requests") != 1
        or summary_obj.get("aggregate_canary_status") != "FAIL"
        or summary_obj.get("ALL_9_CANARY_OPERATIONAL_PASS") is not False
        or tuple(summary_obj.get("unscheduled_cell_ids", ()))
        != EXPECTED_UNSCHEDULED_CELL_IDS
    ):
        raise PlanBeforeLiveProtocolError(
            "CANARY_BATCH_SUMMARY_SEMANTIC_CONTRACT_MISMATCH"
        )

    if (
        summary_obj.get("AMENDED_COMPARATIVE_LIVE_AUTHORIZED") is not False
        or summary_obj.get("COMPARATIVE_EXECUTED") is not False
        or summary_obj.get("MODEL_WINNER_SELECTED") is not False
        or summary_obj.get("SELECTED_MODEL_ID") is not None
        or summary_obj.get("STOCHASTICITY_EXECUTION_STARTED") is not False
        or summary_obj.get("FINAL100_USED") is not False
        or summary_obj.get("FINAL100_STATUS") != "NO-GO"
    ):
        raise PlanBeforeLiveProtocolError(
            "CANARY_BATCH_SUMMARY_DOWNSTREAM_FIREWALL_VIOLATION"
        )

    if (
        cell01_obj.get("cell_id") != CANARY_CELL_01_ID
        or cell01_obj.get("order_index") != 1
        or cell01_obj.get("short_label") != "007 / C1"
        or cell01_obj.get("candidate_id") != "C1"
        or cell01_obj.get("provider") != "GOOGLE"
        or cell01_obj.get("requested_model_id") != "gemini-3.8-flash"
        or cell01_obj.get("fixture_id") != "W06-DEV-TUNE-007"
        or cell01_obj.get("prompt_id") != "P1"
        or cell01_obj.get("logical_generation_invocation_count") != 1
        or cell01_obj.get("actual_provider_http_request_count") != 1
        or cell01_obj.get("generation_call_count") != 1
        or cell01_obj.get("retry_count") != 0
        or cell01_obj.get("provider_response_received") is not False
        or cell01_obj.get("http_or_provider_status_classification") != "TIMEOUT"
        or cell01_obj.get("timeout_failure") is not True
        or cell01_obj.get("http_5xx_failure") is not True
        or cell01_obj.get("cell_operational_pass") is not False
    ):
        raise PlanBeforeLiveProtocolError(
            "CANARY_CELL_01_RECEIPT_SEMANTIC_CONTRACT_MISMATCH"
        )

    return {
        "verified": True,
        "lifecycle_state": LIFECYCLE_POST_EXECUTION_EVIDENCE_PRESENT,
        "live_execution_task_id": LIVE_EXECUTION_TASK_ID,
        "live_evidence_pr_number": LIVE_EVIDENCE_PR_NUMBER,
        "live_evidence_commit_sha": LIVE_EVIDENCE_COMMIT_SHA,
        "output_root": CANARY_LIVE_EVIDENCE_OUTPUT_ROOT_REL_PATH,
        "file_count": len(observed_hashes),
        "batch_summary_sha256": observed_hashes[CANARY_BATCH_SUMMARY_REL_PATH],
        "cell_01_receipt_sha256": observed_hashes[CANARY_CELL_01_RECEIPT_REL_PATH],
        "file_hashes": observed_hashes,
        "ALL_9_CANARY_OPERATIONAL_PASS": False,
        "AMENDED_COMPARATIVE_LIVE_AUTHORIZED": False,
        "COMPARATIVE_EXECUTED": False,
        "MODEL_WINNER_SELECTED": False,
        "SELECTED_MODEL_ID": None,
        "STOCHASTICITY_EXECUTION_STARTED": False,
        "FINAL100_USED": False,
        "FINAL100_STATUS": "NO-GO",
    }


def is_verified_downstream_w06_amendment_01_canary_live_evidence_tree(
    repo_root: Path = REPO_ROOT,
    *,
    output_root_override: Path | None = None,
) -> bool:
    """Return True ONLY if `data/evaluation/w06/live_amendment_01_canary_v1` exists in `repo_root`
    AND matches the exact cryptographically frozen 9-file PR #75 live evidence tree.
    """
    try:
        verify_w06_amendment_01_canary_live_execution_01_evidence_tree(
            repo_root=repo_root,
            output_root_override=output_root_override,
        )
        return True
    except Exception:
        return False


def is_verified_downstream_w06_amendment_01_canary_live_evidence_file(
    path: Path,
    *,
    repo_root: Path = REPO_ROOT,
) -> bool:
    """Return True ONLY if `path` is inside `data/evaluation/w06/live_amendment_01_canary_v1`
    AND the entire 9-file evidence tree in `repo_root` passes stateless cryptographic verification.
    """
    if not is_path_in_downstream_w06_amendment_01_canary_live_evidence_scope(
        path, repo_root=repo_root
    ):
        return False
    return is_verified_downstream_w06_amendment_01_canary_live_evidence_tree(repo_root)


def verify_w06_amendment_01_canary_repository_lifecycle(
    repo_root: Path = REPO_ROOT,
    *,
    output_root_override: Path | None = None,
    require_evidence_present: bool = False,
) -> dict[str, Any]:
    """Evaluate and verify the repository lifecycle state (`PRE_EXECUTION` vs `POST_EXECUTION_EVIDENCE_PRESENT`).

    - If the output root does not exist:
      - If `require_evidence_present` is True, raises `PlanBeforeLiveProtocolError`.
      - Otherwise returns `lifecycle_state = "PRE_EXECUTION"`.
    - If the output root exists:
      - Verifies the exact 9-file PR #75 evidence tree via
        `verify_w06_amendment_01_canary_live_execution_01_evidence_tree` (failing closed if tampered).
      - Also verifies that invoking a second live execution against the existing output root fails
        closed with `ImmutableCellExecutionError("CANARY_OUTPUT_ROOT_ALREADY_EXISTS")`.
      - Returns `lifecycle_state = "POST_EXECUTION_EVIDENCE_PRESENT"`.
    """
    import run_w06_dev_select_amendment_01_canary_live_v1 as canary_launcher

    target_root = output_root_override or (
        repo_root / CANARY_LIVE_EVIDENCE_OUTPUT_ROOT_REL_PATH
    )
    if not target_root.exists():
        if require_evidence_present:
            raise PlanBeforeLiveProtocolError(
                f"CANARY_POST_LIVE_EVIDENCE_REQUIRED_BUT_MISSING: {target_root}"
            )
        return {
            "task_id": TASK_ID,
            "status": "PASS",
            "verified": True,
            "lifecycle_state": LIFECYCLE_PRE_EXECUTION,
            "output_root": CANARY_LIVE_EVIDENCE_OUTPUT_ROOT_REL_PATH,
            "output_root_exists": False,
            "evidence_verified": False,
            "LIVE_PROVIDER_CALLS_NEW": 0,
            "AMENDED_COMPARATIVE_LIVE_AUTHORIZED": False,
            "COMPARATIVE_EXECUTED": False,
            "MODEL_WINNER_SELECTED": False,
            "SELECTED_MODEL_ID": None,
            "STOCHASTICITY_EXECUTION_STARTED": False,
            "FINAL100_USED": False,
            "FINAL100_STATUS": "NO-GO",
        }

    evidence_summary = verify_w06_amendment_01_canary_live_execution_01_evidence_tree(
        repo_root=repo_root,
        output_root_override=target_root,
    )

    # Prove rerun protection remains fail-closed when canonical output root exists
    second_run_blocked = False
    try:
        canary_launcher.verify_canary_output_root_not_existing(
            repo_root=repo_root,
            output_root_override=target_root,
        )
    except ImmutableCellExecutionError:
        second_run_blocked = True

    if not second_run_blocked:
        raise PlanBeforeLiveProtocolError(
            "SECOND_LIVE_EXECUTION_NOT_BLOCKED_WHEN_OUTPUT_ROOT_EXISTS"
        )

    return {
        "task_id": TASK_ID,
        "status": "PASS",
        "verified": True,
        "lifecycle_state": LIFECYCLE_POST_EXECUTION_EVIDENCE_PRESENT,
        "output_root": CANARY_LIVE_EVIDENCE_OUTPUT_ROOT_REL_PATH,
        "output_root_exists": True,
        "evidence_verified": True,
        "second_live_execution_blocked": True,
        "evidence_summary": evidence_summary,
        "LIVE_PROVIDER_CALLS_NEW": 0,
        "AMENDED_COMPARATIVE_LIVE_AUTHORIZED": False,
        "COMPARATIVE_EXECUTED": False,
        "MODEL_WINNER_SELECTED": False,
        "SELECTED_MODEL_ID": None,
        "STOCHASTICITY_EXECUTION_STARTED": False,
        "FINAL100_USED": False,
        "FINAL100_STATUS": "NO-GO",
    }


# ==============================================================================
# 3. ISOLATED TEST FIXTURE HELPER FOR SYNTHETIC POST-LIVE INTEGRATION TESTS
# ==============================================================================


def materialize_frozen_canary_live_execution_01_evidence_tree(
    target_output_root: Path,
    *,
    repo_root: Path = REPO_ROOT,
) -> dict[str, str]:
    """Deterministically materialize the exact 9 byte-identical PR #75 evidence files
    into an isolated test directory `target_output_root` (NEVER into `REPO_ROOT`), and
    verify that all 9 generated files match `EXPECTED_CANARY_LIVE_EXECUTION_01_EVIDENCE_FILE_SHA256S`.
    """
    canonical_prod_root = (
        REPO_ROOT / CANARY_LIVE_EVIDENCE_OUTPUT_ROOT_REL_PATH
    ).resolve()
    if target_output_root.resolve() == canonical_prod_root:
        raise PlanBeforeLiveProtocolError(
            "FORBIDDEN_MATERIALIZE_INTO_CANONICAL_PRODUCTION_OUTPUT_ROOT"
        )

    import run_w06_dev_select_amendment_01_canary_live_v1 as cl

    # Use an isolated non-existent sentinel so authority loading works regardless of repo state
    sentinel_out = (
        target_output_root.parent / "__materialize_authorities_sentinel_never_created__"
    )
    auth = cl.verify_frozen_canary_launcher_authorities(
        repo_root=repo_root,
        output_root_override=sentinel_out,
    )
    cell01 = auth["ordered_canary_cells"][0]
    wire_req = cl.build_canary_cell_wire_request(
        cell_record=cell01,
        dev_bundle=auth["dev_bundle"],
        cand_reg=auth["candidate_registry"],
        p1_spec=auth["p1_spec"],
    )
    wire_sha = hashlib.sha256(cl.canonical_json_bytes(wire_req)).hexdigest()

    cell01_dir = target_output_root / CANARY_CELL_01_ID
    cell01_dir.mkdir(parents=True, exist_ok=True)

    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.write_bytes(
            (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
                "utf-8"
            )
        )

    req_manifest_payload = {
        "attempt_number": 1,
        "candidate_id": "C1",
        "cell_id": CANARY_CELL_01_ID,
        "fixture_id": "W06-DEV-TUNE-007",
        "inter_call_delay_ms": 2000,
        "order_index": 1,
        "prompt_id": "P1",
        "provider": "GOOGLE",
        "provider_slug": "google",
        "requested_model_id": "gemini-3.8-flash",
        "retry_count": 0,
        "serialized_wire_request_sha256": wire_sha,
        "short_label": "007 / C1",
        "timeout_ms": 180000,
        "wire_request": wire_req,
    }
    _write_json(cell01_dir / "request_manifest.json", req_manifest_payload)

    _write_json(
        cell01_dir / "transport_journal_starting.json",
        {
            "attempt_number": 1,
            "candidate_id": "C1",
            "cell_id": CANARY_CELL_01_ID,
            "execution_started_at_utc": "2026-10-31T16:38:27.522525+00:00",
            "fixture_id": "W06-DEV-TUNE-007",
            "order_index": 1,
            "runtime_head_sha": LIVE_EVIDENCE_BASE_DEVELOP_SHA,
            "short_label": "007 / C1",
            "status": "TRANSPORT_STARTING",
        },
    )

    _write_json(
        cell01_dir / "transport_journal_completed.json",
        {
            "actual_provider_http_request_count": 1,
            "attempt_number": 1,
            "candidate_id": "C1",
            "cell_id": CANARY_CELL_01_ID,
            "execution_started_at_utc": "2026-10-31T16:38:27.522525+00:00",
            "fixture_id": "W06-DEV-TUNE-007",
            "latency_ns": 179986664200,
            "logical_generation_invocation_count": 1,
            "order_index": 1,
            "provider_response_received": False,
            "runtime_head_sha": LIVE_EVIDENCE_BASE_DEVELOP_SHA,
            "short_label": "007 / C1",
            "status": "TRANSPORT_COMPLETED",
            "transport_completed_at_utc": "2026-10-31T16:41:27.515438+00:00",
        },
    )

    (cell01_dir / "raw_provider_response.txt").write_bytes(b"")

    exc_msg = (
        "ServerError: 504 DEADLINE_EXCEEDED. "
        "{'error': {'code': 504, 'message': 'Deadline expired before operation could complete.', "
        "'status': 'DEADLINE_EXCEEDED'}}"
    )
    _write_json(
        cell01_dir / "provider_response_metadata.json",
        {
            "finish_or_stop_reason": "PROVIDER_EXCEPTION:TIMEOUT",
            "normalized_provider_metadata": {
                "actual_http_request_count": 1,
                "candidate_id": "C1",
                "exception_classification": "TIMEOUT",
                "exception_summary": exc_msg,
                "logical_generation_invocation_count": 1,
            },
            "provider_response_received": False,
            "raw_provider_metadata": {
                "exception_summary": exc_msg,
            },
            "raw_response_sha256": (
                "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
            ),
            "raw_text_length": 0,
            "raw_text_non_empty": False,
            "raw_text_present": True,
            "returned_model_id": None,
        },
    )

    norm_usage = {
        "cache_creation_input_tokens": None,
        "cache_read_input_tokens": None,
        "cached_input_tokens": None,
        "cached_tokens": None,
        "candidate_id": "C1",
        "input_tokens": None,
        "output_tokens": None,
        "provider": "google",
        "reasoning_tokens": None,
        "thinking_tokens": None,
        "thought_tokens": None,
        "total_tokens": None,
        "usage_present": False,
    }
    _write_json(
        cell01_dir / "raw_usage_metadata.json",
        {
            "normalized_usage_metadata": norm_usage,
            "raw_usage_metadata": None,
        },
    )

    from app.evaluation.dev_selection_harness import load_core_catalog_by_place_id

    core_catalog = load_core_catalog_by_place_id()
    diag_eval = cl.compute_diagnostic_schema_and_quality_for_cell(
        cell_record=cell01,
        raw_text="",
        dev_bundle=auth["dev_bundle"],
        core_catalog_by_place_id=core_catalog,
    )
    _write_json(cell01_dir / "diagnostic_evaluation.json", diag_eval)

    cell01_receipt = {
        "actual_provider_http_request_count": 1,
        "attempt_number": 1,
        "authentication_failure": False,
        "billing_or_credit_failure": False,
        "candidate_id": "C1",
        "cell_id": CANARY_CELL_01_ID,
        "cell_operational_pass": False,
        "diagnostic_final_core_result": diag_eval["diagnostic_final_core_result"],
        "diagnostic_schema_valid": False,
        "execution_started_at_utc": "2026-10-31T16:38:27.522525+00:00",
        "failed_operational_conditions": [
            "no_client_timeout",
            "no_http_5xx_failure",
            "provider_returns_response",
            "required_provider_model_identity_evidence_captured",
        ],
        "fixture_id": "W06-DEV-TUNE-007",
        "generation_call_count": 1,
        "http_4xx_failure": False,
        "http_5xx_failure": True,
        "http_or_provider_status_classification": "TIMEOUT",
        "latency_ms": 179986.664,
        "latency_ns": 179986664200,
        "logical_generation_invocation_count": 1,
        "max_token_truncation_state": False,
        "model_access_failure": False,
        "normalized_usage_metadata": norm_usage,
        "order_index": 1,
        "prompt_id": "P1",
        "provider": "GOOGLE",
        "provider_model_identity_evidence_captured": False,
        "provider_response_received": False,
        "provider_returned_response": False,
        "provider_slug": "google",
        "quota_or_rate_limit_failure": False,
        "raw_response_sha256": (
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        ),
        "raw_text_length": 0,
        "raw_text_non_empty": False,
        "raw_text_present": True,
        "raw_usage_metadata": None,
        "refusal_or_safety_state": False,
        "requested_model_id": "gemini-3.8-flash",
        "required_operational_conditions": {
            "correct_candidate_provider_model_config_used": True,
            "exactly_one_generation_call_attempted": True,
            "no_authentication_failure": True,
            "no_billing_or_credit_failure": True,
            "no_client_timeout": False,
            "no_http_4xx_failure": True,
            "no_http_5xx_failure": False,
            "no_model_access_failure": True,
            "no_provider_transport_failure": True,
            "no_quota_or_rate_limit_rejection": True,
            "provider_returns_response": False,
            "required_provider_model_identity_evidence_captured": False,
            "retry_count_equals_zero": True,
        },
        "retry_count": 0,
        "returned_model_id": None,
        "short_label": "007 / C1",
        "timeout_failure": True,
        "transport_completed_at_utc": "2026-10-31T16:41:27.515438+00:00",
        "transport_failure": False,
    }
    _write_json(cell01_dir / "canary_cell_evidence_receipt.json", cell01_receipt)

    batch_summary = {
        "ALL_9_CANARY_OPERATIONAL_PASS": False,
        "AMENDED_COMPARATIVE_LIVE_AUTHORIZED": False,
        "COMPARATIVE_EXECUTED": False,
        "FINAL100_STATUS": "NO-GO",
        "FINAL100_USED": False,
        "MODEL_WINNER_SELECTED": False,
        "SELECTED_MODEL_ID": None,
        "STOCHASTICITY_EXECUTION_STARTED": False,
        "aggregate_canary_status": "FAIL",
        "attempted_cells": [cell01_receipt],
        "attempted_cells_count": 1,
        "attempted_short_labels": ["007 / C1"],
        "authoritative_base_develop_sha": "1ebe30c251958542088a3056dcfc6b780dac3a88",
        "canary_authorization_prep_file_sha256": (
            "21f9432c4c8bfa0ba5f63bdd99e8ab8c15d2802918b7e0a9c21cb5c0ccc63b61"
        ),
        "canary_authorization_prep_internal_sha256": (
            "0f1480969d506d5b6dc16951a45cf2f8aaf913a13c011f2add6ec3e31721af61"
        ),
        "canary_manifest_file_sha256": (
            "3ce0ebaac35f22dfe8c981478a6c63d7a2fde0580b372fd8f25762ab3b18fb96"
        ),
        "canary_manifest_internal_sha256": (
            "707d99fee54d65822f194cc690cbfadea14ad2176594d4ef882e7d8031990518"
        ),
        "canary_pass_auto_authorizes_comparative": False,
        "execution_mode": "LIVE_CANARY_EXECUTION",
        "fail_stop_triggered": True,
        "next_action": "RETURN_TO_CHATGPT_AUDIT_ON_CANARY_OPERATIONAL_FAILURE",
        "operational_pass_cells_count": 0,
        "operational_pass_fraction": "0/9",
        "owner_readiness_attestation_file_sha256": (
            "91702599a9c81d57bfa1360d33cf19129537608a5141d35bbba58958a62b1d06"
        ),
        "owner_readiness_attestation_internal_sha256": (
            "137aae6ba52912c10098262ecd29238cb591c92005d99eb226ffbe65c9dfbd75"
        ),
        "runtime_head_sha": LIVE_EVIDENCE_BASE_DEVELOP_SHA,
        "scheduled_inter_call_delays_executed": 0,
        "scheduled_inter_call_delays_ms": [],
        "scientific_code_bundle_sha256": (
            "0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3"
        ),
        "stopped_at_cell_id": CANARY_CELL_01_ID,
        "stopped_at_order_index": 1,
        "stopped_at_short_label": "007 / C1",
        "total_actual_provider_http_requests": 1,
        "total_assigned_canary_cells": 9,
        "total_inter_call_delay_ms_executed": 0,
        "total_logical_generation_invocations": 1,
        "unscheduled_cell_ids": list(EXPECTED_UNSCHEDULED_CELL_IDS),
        "unscheduled_cells_count": 8,
        "unscheduled_short_labels": [
            "007 / C2",
            "007 / C3",
            "011 / C1",
            "011 / C2",
            "011 / C3",
            "015 / C1",
            "015 / C2",
            "015 / C3",
        ],
    }
    _write_json(
        target_output_root / "canary_batch_execution_summary_v1.json", batch_summary
    )

    verified = verify_w06_amendment_01_canary_live_execution_01_evidence_tree(
        repo_root=repo_root,
        output_root_override=target_output_root,
    )
    return dict(verified["file_hashes"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify W06 Amendment-01 Canary Live Execution 01 repository lifecycle and immutable evidence."
    )
    parser.add_argument(
        "--verify-lifecycle",
        action="store_true",
        help="Verify repository lifecycle state (PRE_EXECUTION or POST_EXECUTION_EVIDENCE_PRESENT).",
    )
    parser.add_argument(
        "--verify-post-live-evidence",
        action="store_true",
        help="Require POST_EXECUTION_EVIDENCE_PRESENT and verify all 9 frozen PR #75 evidence file hashes.",
    )
    args = parser.parse_args(argv)
    out = verify_w06_amendment_01_canary_repository_lifecycle(
        repo_root=REPO_ROOT,
        require_evidence_present=bool(args.verify_post_live_evidence),
    )
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
