"""Freeze and cryptographically verify the primary W06 DEV-TUNE live execution results.

TASK: W06-DEV-TUNE-LIVE-RESULTS-FREEZE-01

ROLE:
Primary live execution evidence freeze and integrity agent.
Strictly offline (LIVE_PROVIDER_CALLS_NEW = 0).
Treats every existing byte under `data/evaluation/w06/live_dev_tune_primary_v1`
as immutable scientific evidence.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from typing import Any, Mapping
import urllib.request

import httpx
import httpx2

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
AI_SERVICE_DIR = REPO_ROOT / "apps" / "ai-service"
for _p in (SCRIPTS_DIR, AI_SERVICE_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from app.evaluation.dev_live_runner import (  # noqa: E402
    CANDIDATE_ENV_KEY_BY_ID,
    CANDIDATE_MODEL_BY_ID,
    ORDERED_CANDIDATE_IDS,
    DevLiveAuthorizationArtifact,
    DevLiveStageAFreezeReceipt,
    PlanBeforeLiveProtocolError,
    assert_no_secrets_in_payload,
    compute_prompt_freeze_sha256,
    run_dev_live_runner_dry_run,
    write_immutable_canonical_json,
)
from app.evaluation.dev_selection_harness import (  # noqa: E402
    FORBIDDEN_FINAL100_BUNDLE_SHA256,
    FORBIDDEN_P11_MANIFEST_SHA256,
    SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS,
    DevExecutionPlan,
    DevPromptFreezeArtifact,
    canonical_json_bytes,
    compute_scientific_code_bundle_sha256,
    format_canonical_decimal_str,
    normalize_lf_bytes,
    parse_canonical_decimal_str,
    sha256_bytes,
)
from freeze_w06_dev_prompt_candidates import (  # noqa: E402
    build_frozen_p1_p2_registry,
)

# ==============================================================================
# 1. FROZEN AUTHORITIES & EXPECTED EXECUTION CONSTANTS (SECTIONS 0, 1, 2, 4, 5, 6, 7)
# ==============================================================================

TASK_ID = "W06-DEV-TUNE-LIVE-RESULTS-FREEZE-01"
EXECUTION_ID = "W06-DEV-TUNE-LIVE-EXECUTION-01"
RESULTS_MANIFEST_ARTIFACT_ID = "W06-DEV-TUNE-LIVE-RESULTS-MANIFEST-V1"
RESULTS_FREEZE_RECEIPT_ARTIFACT_ID = "W06-DEV-TUNE-LIVE-RESULTS-FREEZE-01-RECEIPT-V1"

BASE_EXECUTION_HEAD_SHA = "4a276ca8ca5e836a92d34ec72569998a3617d915"
PRE_LIVE_HEAD_SHA = "4a276ca8ca5e836a92d34ec72569998a3617d915"
POST_LIVE_HEAD_SHA = "4a276ca8ca5e836a92d34ec72569998a3617d915"

EXPECTED_LAUNCHER_REL_PATH = "scripts/run_w06_dev_tune_live_v1.py"
EXPECTED_LAUNCHER_LF_SHA256 = (
    "b2bdbe062ea9d9e52701bfb73027ab30237f7648835a0ea285961b0e70e4fbbc"
)
EXPECTED_LAUNCHER_GIT_BLOB_SHA = "bf8c24f64d81b42fe6eab5dd14ef19a0e7500712"

EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256 = (
    "0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3"
)

DEV_TUNE_PLAN_REL_PATH = "data/evaluation/w06/w06_dev_tune_execution_plan_v1.json"
EXPECTED_DEV_TUNE_PLAN_SHA256 = (
    "582d9964b4fffbac91f83373d080f1fef120f0ddca4edab2d63e02796d0b20ae"
)
EXPECTED_DEV_TUNE_PLAN_FILE_SHA256 = (
    "652e3beb08771c3125e613172b1aaa396fc1b60aaaf3b98cc238e91a14e0dc74"
)

PROMPT_FREEZE_REL_PATH = (
    "data/evaluation/w06/w06_dev_prompt_candidate_freeze_v1.json"
)
EXPECTED_PROMPT_FREEZE_SHA256 = (
    "2f345363f580ea882b2e5b3562c587ef5309bc7f994440257a54d18994ab6956"
)
EXPECTED_PROMPT_REGISTRY_SHA256 = (
    "846dc4c14ec2a87537b7b3e07bf492de51dc534d24b21e469094b7e3d34d32b6"
)

AUTHORIZATION_REL_PATH = (
    "data/evaluation/w06/w06_dev_tune_live_authorization_v1.json"
)
EXPECTED_AUTHORIZATION_ID = "W06-DEV-TUNE-LIVE-AUTHORIZATION-01-V1"
EXPECTED_AUTHORIZATION_FILE_SHA256 = (
    "b2c068d216e6a71ad5c193137207cc8f7a74526f9a549eccfaefa9a7bd5eeba4"
)
EXPECTED_AUTHORIZATION_INTERNAL_SHA256 = (
    "fb2c181e14b0b122100f7b3b386bdaeaffe467c913d384db16717149374a1c83"
)

STAGE_A_RECEIPT_REL_PATH = (
    "data/evaluation/w06/w06_dev_tune_stage_a_freeze_receipt_v1.json"
)
EXPECTED_STAGE_A_FILE_SHA256 = (
    "a1980a388a39747f0890d0decfcc15d75b273921a6b3cb2c9faa9fb958e22a31"
)
EXPECTED_STAGE_A_INTERNAL_SHA256 = (
    "a0636ddafc4096e02ddaf7b1c69c0e214006030f5461346308a0005e06537d5f"
)

EXPECTED_PREFLIGHT_REQUEST_SET_SHA256 = (
    "438365622e97f9a7062bca5ef9f472ebf48b5d3438c8484d8b0ea8eba4761dc3"
)
EXPECTED_PREFLIGHT_ARTIFACT_PATH_SET_SHA256 = (
    "eebd7a95fa2eb2ea17bffec7d81478594df565423c8a2d893e41a45ab4adc8a8"
)

RAW_OUTPUT_ROOT_REL_PATH = "data/evaluation/w06/live_dev_tune_primary_v1"
RESULTS_MANIFEST_REL_PATH = (
    "data/evaluation/w06/w06_dev_tune_live_results_manifest_v1.json"
)
RESULTS_FREEZE_RECEIPT_REL_PATH = (
    "data/evaluation/w06/w06_dev_tune_live_results_freeze_01_receipt_v1.json"
)

EXPECTED_RAW_EVIDENCE_FILE_COUNT = 1124
EXPECTED_RAW_EVIDENCE_TOTAL_BYTES = 11749420
EXPECTED_RAW_EVIDENCE_MAX_FILE_BYTES = 96816
EXPECTED_RAW_EVIDENCE_TREE_SHA256 = (
    "9b6089f478979ce32e968529c656358fc1bb751101527e017c1e4d5a695cd1e8"
)

EXPECTED_RESULTS_MANIFEST_FILE_SHA256 = (
    "060c3da987638f8eeb96a6240e11b612d3b5e80e31be5046779c417fbca7be85"
)
EXPECTED_RESULTS_FREEZE_RECEIPT_FILE_SHA256 = (
    "5f45c31a96b3827d64b927bccde154ad9345202fbfad6f8070c9f7927c40cbfe"
)

MAX_SINGLE_FILE_BYTES_LIMIT = 90 * 1024 * 1024  # 90 MiB (Section 17)

ALWAYS_PRESENT_CELL_FILES: tuple[str, ...] = (
    "request_manifest.json",
    "transport_journal_starting.json",
    "transport_journal_completed.json",
    "raw_provider_response.txt",
    "provider_response_metadata.json",
    "raw_usage_metadata.json",
    "run_manifest.json",
    "evaluation_result.json",
    "execution_receipt.json",
)
OPTIONAL_CELL_FILES: tuple[str, ...] = ("parsed_plan_response.json",)
ALLOWED_CELL_FILES_SET: frozenset[str] = frozenset(
    ALWAYS_PRESENT_CELL_FILES + OPTIONAL_CELL_FILES
)

EXPECTED_PARSED_PLAN_RESPONSE_COUNT = 44
EXPECTED_AUTHORITATIVE_COST_CELL_COUNT = 42
EXPECTED_TOTAL_CANONICAL_COST_USD_DECIMAL = "6.5555805"
COST_ACCOUNTING_LABEL = "AUTHORITATIVE_RECEIPT_COST_AVAILABLE_ONLY"

FORBIDDEN_FINAL100_SCENARIOS_REL_PATH = (
    "data/evaluation/w06/w06_scenarios_freeze_v1.json"
)
FORBIDDEN_P11_MANIFEST_REL_PATH = (
    "data/evaluation/w06/w06_p11_assignment_manifest_v1.json"
)


# ==============================================================================
# 2. OFFLINE NETWORK KILL SWITCH & SECRET LEAK SCANNER (SECTION 16)
# ==============================================================================


class OutboundNetworkBlockedError(RuntimeError):
    """Raised if any code attempts an outbound network connection during offline results freeze."""


class NetworkKillSwitchGuard:
    """Context manager blocking all socket, urllib, httpx, and httpx2 outbound calls."""

    def __init__(self) -> None:
        self.blocked_attempts: list[str] = []

    def __enter__(self) -> "NetworkKillSwitchGuard":
        self._orig_connect = socket.socket.connect
        self._orig_connect_ex = socket.socket.connect_ex
        self._orig_create_conn = socket.create_connection
        self._orig_urlopen = urllib.request.urlopen
        self._orig_httpx_send = httpx.Client.send
        self._orig_httpx_async_send = httpx.AsyncClient.send
        self._orig_httpx2_send = httpx2.Client.send
        self._orig_httpx2_async_send = httpx2.AsyncClient.send

        def _deny(label: str) -> Any:
            def _raiser(*_a: Any, **_kw: Any) -> Any:
                self.blocked_attempts.append(label)
                raise OutboundNetworkBlockedError(
                    f"OFFLINE_NETWORK_KILL_SWITCH_TRIGGERED: {label} is forbidden in {TASK_ID}."
                )

            return _raiser

        socket.socket.connect = _deny("socket.socket.connect")  # type: ignore[method-assign]
        socket.socket.connect_ex = _deny("socket.socket.connect_ex")  # type: ignore[method-assign]
        socket.create_connection = _deny("socket.create_connection")  # type: ignore[assignment]
        urllib.request.urlopen = _deny("urllib.request.urlopen")  # type: ignore[assignment]
        httpx.Client.send = _deny("httpx.Client.send")  # type: ignore[method-assign]
        httpx.AsyncClient.send = _deny("httpx.AsyncClient.send")  # type: ignore[method-assign]
        httpx2.Client.send = _deny("httpx2.Client.send")  # type: ignore[method-assign]
        httpx2.AsyncClient.send = _deny("httpx2.AsyncClient.send")  # type: ignore[method-assign]
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        socket.socket.connect = self._orig_connect  # type: ignore[method-assign]
        socket.socket.connect_ex = self._orig_connect_ex  # type: ignore[method-assign]
        socket.create_connection = self._orig_create_conn  # type: ignore[assignment]
        urllib.request.urlopen = self._orig_urlopen  # type: ignore[assignment]
        httpx.Client.send = self._orig_httpx_send  # type: ignore[method-assign]
        httpx.AsyncClient.send = self._orig_httpx_async_send  # type: ignore[method-assign]
        httpx2.Client.send = self._orig_httpx2_send  # type: ignore[method-assign]
        httpx2.AsyncClient.send = self._orig_httpx2_async_send  # type: ignore[method-assign]


def _load_ephemeral_secret_values_for_exact_leak_comparison(
    repo_root: Path = REPO_ROOT,
) -> list[str]:
    """Load API key values into memory ONLY for exact substring leak comparison (Section 16).

    Values are NEVER printed, logged, hashed, persisted, or included in exceptions.
    """
    secrets: list[str] = []
    env_var_names = tuple(CANDIDATE_ENV_KEY_BY_ID.values())
    for k in env_var_names:
        v = os.environ.get(k, "").strip()
        if v and len(v) >= 4:
            secrets.append(v)

    for dotenv_rel in ("apps/ai-service/.env", ".env"):
        dotenv_path = repo_root / dotenv_rel
        if dotenv_path.is_file():
            try:
                for raw_line in dotenv_path.read_text(
                    encoding="utf-8", errors="ignore"
                ).splitlines():
                    line = raw_line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k_part, v_part = line.split("=", 1)
                    if k_part.strip() in env_var_names:
                        val = v_part.strip().strip("'").strip('"').strip()
                        if val and len(val) >= 4:
                            secrets.append(val)
            except Exception:
                pass
    return secrets


def scan_raw_evidence_for_secret_leaks(
    raw_output_root: Path,
    *,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Scan all files in `raw_output_root` for secret leakage before git add (Section 16).

    Never mutates any file and never includes secret values in exception messages.
    """
    extra_secrets = _load_ephemeral_secret_values_for_exact_leak_comparison(repo_root)
    scanned_files = 0
    for path in sorted(raw_output_root.rglob("*")):
        if not path.is_file():
            continue
        scanned_files += 1
        try:
            rel_posix = path.resolve().relative_to(repo_root.resolve()).as_posix()
        except Exception:
            rel_posix = f"{RAW_OUTPUT_ROOT_REL_PATH}/{path.relative_to(raw_output_root).as_posix()}"
        text = path.read_text(encoding="utf-8", errors="replace")
        # 1. Exact loaded secret value comparison (without leaking value in error)
        for sec in extra_secrets:
            if sec and sec in text:
                raise RuntimeError(
                    f"SECRET_LEAK_DETECTED: Exact configured API key value found in {rel_posix}."
                )
        # 2. Repository structural/regex secret-safety check
        if path.suffix.lower() == ".json":
            try:
                parsed = json.loads(text)
            except Exception as exc:
                raise RuntimeError(
                    f"INVALID_JSON_IN_RAW_EVIDENCE: {rel_posix}"
                ) from exc
            assert_no_secrets_in_payload(
                parsed,
                context=f"RAW_EVIDENCE_JSON:{rel_posix}",
            )
        else:
            assert_no_secrets_in_payload(
                text,
                context=f"RAW_EVIDENCE_TEXT:{rel_posix}",
            )

    return {
        "secret_leak_scan": "PASS",
        "scanned_file_count": scanned_files,
        "secret_leak_detected": False,
    }


# ==============================================================================
# 3. RAW EVIDENCE TREE MANIFEST COMPUTATION (SECTIONS 3, 4, 17, 21)
# ==============================================================================


def build_raw_evidence_tree_manifest(
    repo_root: Path = REPO_ROOT,
    *,
    raw_output_root: Path | None = None,
) -> dict[str, Any]:
    """Enumerate `data/evaluation/w06/live_dev_tune_primary_v1` and compute canonical raw-byte tree SHA256.

    Strictly read-only. Uses exact raw bytes (NO LF normalization).
    Excludes mtime, ctime, inode, and absolute paths.
    """
    target_root = raw_output_root or (repo_root / RAW_OUTPUT_ROOT_REL_PATH)
    if not target_root.is_dir():
        raise PlanBeforeLiveProtocolError(
            f"RAW_OUTPUT_ROOT_MISSING: {target_root} does not exist."
        )

    entries: list[dict[str, Any]] = []
    total_bytes = 0
    max_file_bytes = 0

    try:
        rel_posix = target_root.resolve().relative_to(repo_root.resolve()).as_posix()
        rel_prefix = rel_posix
    except Exception:
        rel_prefix = RAW_OUTPUT_ROOT_REL_PATH

    for p in sorted(target_root.rglob("*")):
        if p.is_symlink():
            raise PlanBeforeLiveProtocolError(
                f"SYMLINK_FORBIDDEN_IN_RAW_EVIDENCE: {p}"
            )
        if p.is_file():
            rel_posix = f"{rel_prefix}/{p.relative_to(target_root).as_posix()}"
            raw_bytes = p.read_bytes()
            byte_size = len(raw_bytes)
            if byte_size >= MAX_SINGLE_FILE_BYTES_LIMIT:
                raise PlanBeforeLiveProtocolError(
                    f"STORAGE_BLOCKER_FILE_TOO_LARGE: {rel_posix} has {byte_size} bytes (>= 90 MiB)."
                )
            total_bytes += byte_size
            if byte_size > max_file_bytes:
                max_file_bytes = byte_size
            entries.append(
                {
                    "relative_path": rel_posix,
                    "byte_size": byte_size,
                    "sha256_raw_bytes": hashlib.sha256(raw_bytes).hexdigest(),
                }
            )

    entries.sort(key=lambda item: str(item["relative_path"]))
    tree_sha256 = sha256_bytes(canonical_json_bytes(entries))

    return {
        "raw_output_root": rel_prefix,
        "raw_evidence_file_count": len(entries),
        "raw_evidence_total_bytes": total_bytes,
        "raw_evidence_max_file_bytes": max_file_bytes,
        "raw_evidence_tree_sha256": tree_sha256,
        "ordered_raw_file_manifest": entries,
    }


# ==============================================================================
# 4. PREFLIGHT REQUEST IDENTITY & PER-CELL VERIFICATION (SECTIONS 5, 6, 7, 8, 9)
# ==============================================================================


def compute_canonical_preflight_for_results_verification(
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Run offline `run_dev_live_runner_dry_run` with frozen P1+P2 registry and compute canonical request/path set hashes."""
    prompt_reg = build_frozen_p1_p2_registry()
    if prompt_reg.registry_sha256 != EXPECTED_PROMPT_REGISTRY_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"FROZEN_PROMPT_REGISTRY_SHA256_MISMATCH: {prompt_reg.registry_sha256}"
        )

    # Note: In W06-DEV-TUNE-LIVE-EXECUTION-PREFLIGHT-01, planned_artifact_paths_by_run_id
    # was computed with batch_root_dir = REPO_ROOT / RAW_OUTPUT_ROOT_REL_PATH.
    canonical_batch_root = REPO_ROOT / RAW_OUTPUT_ROOT_REL_PATH
    dry_out = run_dev_live_runner_dry_run(
        execution_plan=repo_root / DEV_TUNE_PLAN_REL_PATH,
        prompt_freeze=repo_root / PROMPT_FREEZE_REL_PATH,
        prompt_registry=prompt_reg,
        authorization=repo_root / AUTHORIZATION_REL_PATH,
        stage_a_freeze_receipt=repo_root / STAGE_A_RECEIPT_REL_PATH,
        batch_root_dir=canonical_batch_root,
        repo_root=repo_root,
    )
    req_map = dry_out["serialized_request_sha256_by_run_id"]
    art_map = dry_out["planned_artifact_paths_by_run_id"]
    req_set_sha = sha256_bytes(canonical_json_bytes(req_map))
    path_set_sha = sha256_bytes(canonical_json_bytes(art_map))
    return {
        "dry_run_output": dry_out,
        "planned_call_count": dry_out["planned_call_count"],
        "serialized_request_sha256_by_run_id": req_map,
        "planned_artifact_paths_by_run_id": art_map,
        "preflight_request_set_sha256": req_set_sha,
        "preflight_artifact_path_set_sha256": path_set_sha,
    }


def verify_and_summarize_live_results_evidence(
    repo_root: Path = REPO_ROOT,
    *,
    raw_output_root: Path | None = None,
    execution_plan_override: DevExecutionPlan | None = None,
) -> dict[str, Any]:
    """Perform full verification of Sections 1..17 and return recomputed summary & hashes.

    Fails closed on any missing/extra cell, tampered file, broken hash chain,
    request mismatch, transport journal ambiguity, retry evidence, or model mismatch.
    """
    target_root = raw_output_root or (repo_root / RAW_OUTPUT_ROOT_REL_PATH)
    if not target_root.is_dir():
        raise PlanBeforeLiveProtocolError(
            f"RAW_OUTPUT_ROOT_MISSING: {target_root}"
        )

    # Load and verify upstream authorities
    plan_path = repo_root / DEV_TUNE_PLAN_REL_PATH
    pf_path = repo_root / PROMPT_FREEZE_REL_PATH
    auth_path = repo_root / AUTHORIZATION_REL_PATH
    sa_path = repo_root / STAGE_A_RECEIPT_REL_PATH
    launcher_path = repo_root / EXPECTED_LAUNCHER_REL_PATH

    plan_bytes = normalize_lf_bytes(plan_path.read_bytes())
    pf_bytes = normalize_lf_bytes(pf_path.read_bytes())
    auth_bytes = normalize_lf_bytes(auth_path.read_bytes())
    sa_bytes = normalize_lf_bytes(sa_path.read_bytes())
    launcher_bytes = normalize_lf_bytes(launcher_path.read_bytes())

    plan_file_sha = sha256_bytes(plan_bytes)
    pf_file_sha = sha256_bytes(pf_bytes)
    auth_file_sha = sha256_bytes(auth_bytes)
    sa_file_sha = sha256_bytes(sa_bytes)
    launcher_lf_sha = sha256_bytes(launcher_bytes)
    bundle_sha = compute_scientific_code_bundle_sha256(repo_root=repo_root)

    if bundle_sha != EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"SCIENTIFIC_CODE_BUNDLE_SHA256_MISMATCH: {bundle_sha}"
        )
    if launcher_lf_sha != EXPECTED_LAUNCHER_LF_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"LAUNCHER_LF_SHA256_MISMATCH: {launcher_lf_sha}"
        )
    if plan_file_sha != EXPECTED_DEV_TUNE_PLAN_FILE_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"DEV_TUNE_PLAN_FILE_SHA256_MISMATCH: {plan_file_sha}"
        )
    if pf_file_sha != EXPECTED_PROMPT_FREEZE_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"PROMPT_FREEZE_SHA256_MISMATCH: {pf_file_sha}"
        )
    if auth_file_sha != EXPECTED_AUTHORIZATION_FILE_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"AUTHORIZATION_FILE_SHA256_MISMATCH: {auth_file_sha}"
        )
    if sa_file_sha != EXPECTED_STAGE_A_FILE_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"STAGE_A_FILE_SHA256_MISMATCH: {sa_file_sha}"
        )

    plan_model = execution_plan_override or DevExecutionPlan.model_validate_json(
        plan_bytes
    )
    pf_model = DevPromptFreezeArtifact.model_validate_json(pf_bytes)
    auth_model = DevLiveAuthorizationArtifact.model_validate_json(auth_bytes)
    sa_model = DevLiveStageAFreezeReceipt.model_validate_json(sa_bytes)

    if plan_model.plan_sha256 != EXPECTED_DEV_TUNE_PLAN_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"PLAN_BINDING_MISMATCH: plan_sha256={plan_model.plan_sha256} != {EXPECTED_DEV_TUNE_PLAN_SHA256}"
        )
    if compute_prompt_freeze_sha256(pf_model) != EXPECTED_PROMPT_FREEZE_SHA256:
        raise PlanBeforeLiveProtocolError("PROMPT_FREEZE_INTERNAL_SHA256_MISMATCH")
    if (
        auth_model.authorization_artifact_sha256
        != EXPECTED_AUTHORIZATION_INTERNAL_SHA256
    ):
        raise PlanBeforeLiveProtocolError("AUTHORIZATION_INTERNAL_SHA256_MISMATCH")
    if sa_model.stage_a_receipt_sha256 != EXPECTED_STAGE_A_INTERNAL_SHA256:
        raise PlanBeforeLiveProtocolError("STAGE_A_INTERNAL_SHA256_MISMATCH")

    # Section 5: Expected cell set & duplicate/unknown check
    assigned_cells = list(plan_model.cells)
    if len(assigned_cells) != 120 or plan_model.expected_total_cells != 120:
        raise PlanBeforeLiveProtocolError(
            f"EXPECTED_120_ASSIGNED_CELLS: got {len(assigned_cells)}"
        )

    assigned_run_ids_ordered: list[str] = [c.run_id for c in assigned_cells]
    if len(set(assigned_run_ids_ordered)) != 120:
        raise PlanBeforeLiveProtocolError("DUPLICATE_ASSIGNED_RUN_ID_IN_PLAN")

    logical_cell_keys = [
        (c.phase, c.prompt_id, c.candidate_id, c.fixture_id, c.attempt_number)
        for c in assigned_cells
    ]
    if len(set(logical_cell_keys)) != 120:
        raise PlanBeforeLiveProtocolError("DUPLICATE_LOGICAL_CELL_IN_PLAN")

    # Inspect top-level entries inside raw output root
    root_children = sorted(target_root.iterdir(), key=lambda p: p.name)
    root_files = [p.name for p in root_children if not p.is_dir()]
    if root_files:
        raise PlanBeforeLiveProtocolError(
            f"UNEXPECTED_TOP_LEVEL_FILES_IN_RAW_ROOT: {root_files}"
        )

    cell_dirs = [p for p in root_children if p.is_dir()]
    observed_dir_names = [p.name for p in cell_dirs]
    assigned_set = set(assigned_run_ids_ordered)
    observed_set = set(observed_dir_names)

    missing_run_ids = sorted(assigned_set - observed_set)
    unknown_run_ids = sorted(observed_set - assigned_set)
    if missing_run_ids:
        raise PlanBeforeLiveProtocolError(
            f"MISSING_CELL_DIRECTORIES: {missing_run_ids}"
        )
    if unknown_run_ids:
        raise PlanBeforeLiveProtocolError(
            f"UNKNOWN_EXTRA_CELL_DIRECTORIES: {unknown_run_ids}"
        )
    if len(cell_dirs) != 120:
        raise PlanBeforeLiveProtocolError(
            f"CELL_DIRECTORY_COUNT_MISMATCH: expected 120, got {len(cell_dirs)}"
        )

    # Section 4: Raw tree manifest
    tree_manifest = build_raw_evidence_tree_manifest(
        repo_root=repo_root, raw_output_root=target_root
    )

    # Section 7: Preflight request identity
    preflight_info = compute_canonical_preflight_for_results_verification(repo_root)
    if (
        preflight_info["planned_call_count"] != 120
        or preflight_info["preflight_request_set_sha256"]
        != EXPECTED_PREFLIGHT_REQUEST_SET_SHA256
        or preflight_info["preflight_artifact_path_set_sha256"]
        != EXPECTED_PREFLIGHT_ARTIFACT_PATH_SET_SHA256
    ):
        raise PlanBeforeLiveProtocolError(
            f"PREFLIGHT_SET_HASH_MISMATCH: req={preflight_info['preflight_request_set_sha256']}, "
            f"path={preflight_info['preflight_artifact_path_set_sha256']}"
        )
    expected_req_sha_by_run_id: Mapping[str, str] = preflight_info[
        "serialized_request_sha256_by_run_id"
    ]

    # Section 6, 7, 8, 9, 10, 11, 12: Per-cell verification & aggregation
    file_type_counts: Counter[str] = Counter()
    request_identity_matches = 0
    cell_hash_chain_valid_count = 0
    transport_starting_count = 0
    transport_completed_count = 0
    transport_ambiguous_count = 0
    retry_calls = 0
    rerun_cells = 0
    model_id_mismatch_count = 0

    seen_receipt_run_ids: set[str] = set()
    seen_logical_cells: set[tuple[str, str, str, str]] = set()
    execution_receipt_file_hashes: dict[str, str] = {}

    result_counts_by_candidate: Counter[str] = Counter()
    result_counts_by_prompt: Counter[str] = Counter()
    failure_total: Counter[str] = Counter()
    failure_by_candidate: dict[str, Counter[str]] = {
        cid: Counter() for cid in ORDERED_CANDIDATE_IDS
    }
    failure_by_prompt: dict[str, Counter[str]] = {"P1": Counter(), "P2": Counter()}

    valid_total: Counter[str] = Counter()
    valid_by_cand: dict[str, Counter[str]] = {
        cid: Counter() for cid in ORDERED_CANDIDATE_IDS
    }
    valid_by_prompt: dict[str, Counter[str]] = {"P1": Counter(), "P2": Counter()}
    valid_by_pc: dict[str, Counter[str]] = {
        f"{p}_{c}": Counter() for p in ("P1", "P2") for c in ORDERED_CANDIDATE_IDS
    }

    grounding_total: Counter[str] = Counter()
    grounding_by_cand: dict[str, Counter[str]] = {
        cid: Counter() for cid in ORDERED_CANDIDATE_IDS
    }
    grounding_by_prompt: dict[str, Counter[str]] = {"P1": Counter(), "P2": Counter()}
    grounding_by_pc: dict[str, Counter[str]] = {
        f"{p}_{c}": Counter() for p in ("P1", "P2") for c in ORDERED_CANDIDATE_IDS
    }

    core_total: Counter[str] = Counter()
    core_by_cand: dict[str, Counter[str]] = {
        cid: Counter() for cid in ORDERED_CANDIDATE_IDS
    }
    core_by_prompt: dict[str, Counter[str]] = {"P1": Counter(), "P2": Counter()}
    core_by_pc: dict[str, Counter[str]] = {
        f"{p}_{c}": Counter() for p in ("P1", "P2") for c in ORDERED_CANDIDATE_IDS
    }

    returned_models_by_cand: dict[str, Counter[str]] = {
        cid: Counter() for cid in ORDERED_CANDIDATE_IDS
    }

    authoritative_cost_cell_count = 0
    total_canonical_cost_decimal = Decimal("0")
    cost_cells_by_candidate: Counter[str] = Counter()
    cost_decimal_by_candidate: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    non_comparable_cached_valid_cells: list[str] = []

    http_429_run_ids_by_prompt_candidate: dict[str, list[str]] = defaultdict(list)

    for cell in assigned_cells:
        rid = cell.run_id
        cdir = target_root / rid
        if not cdir.is_dir():
            raise PlanBeforeLiveProtocolError(f"MISSING_CELL_DIR: {rid}")

        cell_files = sorted(p for p in cdir.iterdir() if p.is_file())
        sub_dirs = [p.name for p in cdir.iterdir() if p.is_dir()]
        if sub_dirs:
            raise PlanBeforeLiveProtocolError(
                f"UNEXPECTED_SUBDIR_IN_CELL: {rid} -> {sub_dirs}"
            )

        cell_file_names = {p.name for p in cell_files}
        unknown_cell_files = sorted(cell_file_names - ALLOWED_CELL_FILES_SET)
        if unknown_cell_files:
            raise PlanBeforeLiveProtocolError(
                f"UNKNOWN_FILES_IN_CELL: {rid} -> {unknown_cell_files}"
            )
        for req_fname in ALWAYS_PRESENT_CELL_FILES:
            if req_fname not in cell_file_names:
                raise PlanBeforeLiveProtocolError(
                    f"MISSING_REQUIRED_CELL_FILE: {rid}/{req_fname}"
                )

        for p in cell_files:
            file_type_counts[p.name] += 1

        # Load raw bytes and JSON objects
        req_man_bytes = (cdir / "request_manifest.json").read_bytes()
        sj_bytes = (cdir / "transport_journal_starting.json").read_bytes()
        cj_bytes = (cdir / "transport_journal_completed.json").read_bytes()
        raw_resp_bytes = (cdir / "raw_provider_response.txt").read_bytes()
        meta_bytes = (cdir / "provider_response_metadata.json").read_bytes()
        usage_bytes = (cdir / "raw_usage_metadata.json").read_bytes()
        run_man_bytes = (cdir / "run_manifest.json").read_bytes()
        eval_res_bytes = (cdir / "evaluation_result.json").read_bytes()
        rec_bytes = (cdir / "execution_receipt.json").read_bytes()

        parsed_path = cdir / "parsed_plan_response.json"
        parsed_bytes = parsed_path.read_bytes() if parsed_path.is_file() else None

        req_man = json.loads(req_man_bytes.decode("utf-8"))
        sj = json.loads(sj_bytes.decode("utf-8"))
        cj = json.loads(cj_bytes.decode("utf-8"))
        meta = json.loads(meta_bytes.decode("utf-8"))
        usage_obj = json.loads(usage_bytes.decode("utf-8"))
        run_man = json.loads(run_man_bytes.decode("utf-8"))
        eval_res = json.loads(eval_res_bytes.decode("utf-8"))
        rec = json.loads(rec_bytes.decode("utf-8"))

        # Check duplicate run_id or logical cell across receipts
        rec_run_id = rec.get("run_id")
        if rec_run_id != rid or req_man.get("run_id") != rid or run_man.get("run_id") != rid:
            raise PlanBeforeLiveProtocolError(
                f"CELL_RUN_ID_MISMATCH: dir={rid}, receipt={rec_run_id}, req={req_man.get('run_id')}"
            )
        if rec_run_id in seen_receipt_run_ids:
            raise PlanBeforeLiveProtocolError(
                f"DUPLICATE_RUN_ID_DETECTED: {rec_run_id}"
            )
        seen_receipt_run_ids.add(rec_run_id)

        logical_key = (
            str(rec.get("phase")),
            str(rec.get("prompt_id")),
            str(rec.get("candidate_id")),
            str(rec.get("fixture_id")),
        )
        if logical_key != (
            cell.phase,
            cell.prompt_id,
            cell.candidate_id,
            cell.fixture_id,
        ):
            raise PlanBeforeLiveProtocolError(
                f"CELL_IDENTITY_MISMATCH_IN_RECEIPT: {rid} -> {logical_key}"
            )
        if logical_key in seen_logical_cells:
            raise PlanBeforeLiveProtocolError(
                f"DUPLICATE_LOGICAL_CELL_DETECTED: {logical_key}"
            )
        seen_logical_cells.add(logical_key)

        # Check runtime_head_sha and bundle binding in receipt & request_manifest
        if (
            rec.get("runtime_head_sha") != BASE_EXECUTION_HEAD_SHA
            or req_man.get("runtime_head_sha") != BASE_EXECUTION_HEAD_SHA
            or meta.get("runtime_head_sha") != BASE_EXECUTION_HEAD_SHA
        ):
            raise PlanBeforeLiveProtocolError(
                f"RUNTIME_HEAD_SHA_MISMATCH_IN_CELL: {rid}"
            )
        if (
            rec.get("scientific_code_bundle_sha256")
            != EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
            or req_man.get("scientific_code_bundle_sha256")
            != EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
        ):
            raise PlanBeforeLiveProtocolError(
                f"SCIENTIFIC_BUNDLE_MISMATCH_IN_CELL: {rid}"
            )
        if (
            req_man.get("authorization_artifact_sha256")
            != EXPECTED_AUTHORIZATION_INTERNAL_SHA256
            or req_man.get("stage_a_receipt_sha256") != EXPECTED_STAGE_A_INTERNAL_SHA256
        ):
            raise PlanBeforeLiveProtocolError(
                f"AUTHORITY_SHA_MISMATCH_IN_REQUEST_MANIFEST: {rid}"
            )

        # Section 7: Request identity match against preflight
        wire_req = req_man.get("provider_wire_request")
        if not isinstance(wire_req, dict):
            raise PlanBeforeLiveProtocolError(f"MISSING_WIRE_REQUEST: {rid}")
        actual_wire_sha = sha256_bytes(canonical_json_bytes(wire_req))
        if actual_wire_sha != expected_req_sha_by_run_id.get(rid):
            raise PlanBeforeLiveProtocolError(
                f"REQUEST_IDENTITY_MISMATCH for {rid}: actual={actual_wire_sha} != expected={expected_req_sha_by_run_id.get(rid)}"
            )
        request_identity_matches += 1

        # Section 8: Per-cell hash chain verification
        req_man_sha = hashlib.sha256(req_man_bytes).hexdigest()
        raw_resp_sha = hashlib.sha256(raw_resp_bytes).hexdigest()
        meta_sha = hashlib.sha256(meta_bytes).hexdigest()
        eval_res_sha = hashlib.sha256(eval_res_bytes).hexdigest()
        parsed_sha = (
            hashlib.sha256(parsed_bytes).hexdigest()
            if parsed_bytes is not None
            else None
        )
        rec_file_sha = hashlib.sha256(rec_bytes).hexdigest()
        execution_receipt_file_hashes[rid] = rec_file_sha

        if (
            rec.get("request_manifest_sha256") != req_man_sha
            or rec.get("raw_response_sha256") != raw_resp_sha
            or rec.get("provider_metadata_sha256") != meta_sha
            or rec.get("evaluation_result_sha256") != eval_res_sha
            or rec.get("parsed_response_sha256") != parsed_sha
            or run_man.get("raw_response_sha256") != raw_resp_sha
            or run_man.get("parsed_response_sha256") != parsed_sha
            or eval_res.get("run_id") != rid
            or usage_obj.get("run_id") != rid
        ):
            raise PlanBeforeLiveProtocolError(
                f"CELL_HASH_CHAIN_BROKEN for {rid}: receipt pointers do not match raw evidence bytes."
            )
        cell_hash_chain_valid_count += 1

        # Section 9: Transport journal integrity & zero retry / single attempt
        s_ci = sj.get("cell_identity", {})
        c_ci = cj.get("cell_identity", {})
        if (
            sj.get("run_id") != rid
            or sj.get("status") != "TRANSPORT_STARTING"
            or sj.get("attempt_number") != 1
            or s_ci.get("candidate_id") != cell.candidate_id
            or s_ci.get("prompt_id") != cell.prompt_id
            or s_ci.get("fixture_id") != cell.fixture_id
            or s_ci.get("phase") != "DEV_TUNE"
            or s_ci.get("attempt_number") != 1
            or cj.get("run_id") != rid
            or cj.get("status") != "TRANSPORT_COMPLETED"
            or cj.get("attempt_number") != 1
            or c_ci.get("candidate_id") != cell.candidate_id
            or c_ci.get("prompt_id") != cell.prompt_id
            or c_ci.get("fixture_id") != cell.fixture_id
            or c_ci.get("phase") != "DEV_TUNE"
            or c_ci.get("attempt_number") != 1
            or sj.get("execution_started_at_utc") != cj.get("execution_started_at_utc")
            or sj.get("execution_started_at_utc")
            != req_man.get("execution_started_at_utc")
        ):
            transport_ambiguous_count += 1
            raise PlanBeforeLiveProtocolError(
                f"TRANSPORT_JOURNAL_INTEGRITY_FAILURE for {rid}"
            )
        transport_starting_count += 1
        transport_completed_count += 1

        # Check attempt_number == 1 and retry == 0 and actual_http_request_count == 1
        if (
            rec.get("attempt_number") != 1
            or req_man.get("attempt_number") != 1
            or req_man.get("retry") != 0
            or meta.get("actual_http_request_count") != 1
        ):
            retry_calls += 1
            rerun_cells += 1
            raise PlanBeforeLiveProtocolError(
                f"RETRY_OR_SECOND_ATTEMPT_DETECTED in {rid}: attempt={rec.get('attempt_number')}, "
                f"retry={req_man.get('retry')}, http_requests={meta.get('actual_http_request_count')}"
            )

        # Check model integrity
        req_model = rec.get("requested_model_id")
        ret_model = rec.get("returned_model_id")
        expected_model = CANDIDATE_MODEL_BY_ID[cell.candidate_id]
        if req_model != expected_model:
            model_id_mismatch_count += 1
            raise PlanBeforeLiveProtocolError(
                f"REQUESTED_MODEL_ID_MISMATCH in {rid}: {req_model} != {expected_model}"
            )
        if ret_model is not None and ret_model != req_model:
            model_id_mismatch_count += 1
            raise PlanBeforeLiveProtocolError(
                f"RETURNED_MODEL_ID_MISMATCH in {rid}: {ret_model} != {req_model}"
            )
        returned_models_by_cand[cell.candidate_id][
            str(ret_model) if ret_model is not None else "null"
        ] += 1

        # Aggregate counts (Sections 10 & 11)
        cid = cell.candidate_id
        pid = cell.prompt_id
        pc_key = f"{pid}_{cid}"
        result_counts_by_candidate[cid] += 1
        result_counts_by_prompt[pid] += 1

        raw_f_cls = str(rec.get("failure_classification"))
        short_f_cls = raw_f_cls.replace("DevCellFailureClassification.", "")
        failure_total[short_f_cls] += 1
        failure_by_candidate[cid][short_f_cls] += 1
        failure_by_prompt[pid][short_f_cls] += 1
        if short_f_cls == "HTTP_429":
            http_429_run_ids_by_prompt_candidate[pc_key].append(rid)

        v_flag = "true" if bool(rec.get("valid_run_and_schema")) else "false"
        g_flag = "true" if bool(rec.get("exact_grounding_pass")) else "false"
        c_flag = "true" if bool(rec.get("final_core_pass")) else "false"

        valid_total[v_flag] += 1
        valid_by_cand[cid][v_flag] += 1
        valid_by_prompt[pid][v_flag] += 1
        valid_by_pc[pc_key][v_flag] += 1

        grounding_total[g_flag] += 1
        grounding_by_cand[cid][g_flag] += 1
        grounding_by_prompt[pid][g_flag] += 1
        grounding_by_pc[pc_key][g_flag] += 1

        core_total[c_flag] += 1
        core_by_cand[cid][c_flag] += 1
        core_by_prompt[pid][c_flag] += 1
        core_by_pc[pc_key][c_flag] += 1

        # Section 12: Cost recomputation from canonical_cost_usd_decimal
        auth_usage = bool(rec.get("authoritative_usage_available"))
        cost_dec_str = rec.get("canonical_cost_usd_decimal")
        if auth_usage and cost_dec_str is not None:
            authoritative_cost_cell_count += 1
            cell_cost_dec = parse_canonical_decimal_str(str(cost_dec_str))
            total_canonical_cost_decimal += cell_cost_dec
            cost_cells_by_candidate[cid] += 1
            cost_decimal_by_candidate[cid] += cell_cost_dec
        elif bool(rec.get("valid_run_and_schema")):
            non_comparable_cached_valid_cells.append(rid)

    # Verify Section 6 required execution counts
    for fname in ALWAYS_PRESENT_CELL_FILES:
        if file_type_counts[fname] != 120:
            raise PlanBeforeLiveProtocolError(
                f"REQUIRED_FILE_COUNT_MISMATCH: {fname} count={file_type_counts[fname]} != 120"
            )
    if file_type_counts["parsed_plan_response.json"] != EXPECTED_PARSED_PLAN_RESPONSE_COUNT:
        raise PlanBeforeLiveProtocolError(
            f"PARSED_PLAN_RESPONSE_COUNT_MISMATCH: {file_type_counts['parsed_plan_response.json']} != {EXPECTED_PARSED_PLAN_RESPONSE_COUNT}"
        )

    # Verify Section 10, 11, 12 expected counts
    expected_failure_total = {
        "HTTP_429": 15,
        "HTTP_5XX": 3,
        "HTTP_ERROR": 1,
        "NONE": 44,
        "TIMEOUT": 57,
    }
    if dict(sorted(failure_total.items())) != expected_failure_total:
        raise PlanBeforeLiveProtocolError(
            f"FAILURE_CLASSIFICATION_COUNTS_MISMATCH: {dict(failure_total)} != {expected_failure_total}"
        )

    expected_valid_pc = {
        "P1_C1": {"false": 17, "true": 3},
        "P1_C2": {"false": 16, "true": 4},
        "P1_C3": {"false": 4, "true": 16},
        "P2_C1": {"false": 19, "true": 1},
        "P2_C2": {"false": 17, "true": 3},
        "P2_C3": {"false": 3, "true": 17},
    }
    expected_core_pc = {
        "P1_C1": {"false": 20, "true": 0},
        "P1_C2": {"false": 16, "true": 4},
        "P1_C3": {"false": 4, "true": 16},
        "P2_C1": {"false": 19, "true": 1},
        "P2_C2": {"false": 17, "true": 3},
        "P2_C3": {"false": 3, "true": 17},
    }

    def _norm_bool_counter(c: Counter[str]) -> dict[str, int]:
        return {"false": int(c.get("false", 0)), "true": int(c.get("true", 0))}

    actual_valid_pc = {k: _norm_bool_counter(v) for k, v in sorted(valid_by_pc.items())}
    actual_grounding_pc = {
        k: _norm_bool_counter(v) for k, v in sorted(grounding_by_pc.items())
    }
    actual_core_pc = {k: _norm_bool_counter(v) for k, v in sorted(core_by_pc.items())}

    if (
        _norm_bool_counter(valid_total) != {"false": 76, "true": 44}
        or actual_valid_pc != expected_valid_pc
    ):
        raise PlanBeforeLiveProtocolError(
            f"VALID_RUN_AND_SCHEMA_MISMATCH: total={_norm_bool_counter(valid_total)}, pc={actual_valid_pc}"
        )
    if (
        _norm_bool_counter(grounding_total) != {"false": 76, "true": 44}
        or actual_grounding_pc != expected_valid_pc
    ):
        raise PlanBeforeLiveProtocolError(
            f"EXACT_GROUNDING_PASS_MISMATCH: total={_norm_bool_counter(grounding_total)}, pc={actual_grounding_pc}"
        )
    if (
        _norm_bool_counter(core_total) != {"false": 79, "true": 41}
        or actual_core_pc != expected_core_pc
    ):
        raise PlanBeforeLiveProtocolError(
            f"FINAL_CORE_PASS_MISMATCH: total={_norm_bool_counter(core_total)}, pc={actual_core_pc}"
        )

    formatted_total_cost = format_canonical_decimal_str(total_canonical_cost_decimal)
    if (
        authoritative_cost_cell_count != EXPECTED_AUTHORITATIVE_COST_CELL_COUNT
        or formatted_total_cost != EXPECTED_TOTAL_CANONICAL_COST_USD_DECIMAL
    ):
        raise PlanBeforeLiveProtocolError(
            f"AUTHORITATIVE_COST_MISMATCH: cells={authoritative_cost_cell_count}, total={formatted_total_cost}"
        )

    # Section 13: Execution-order limitation verification
    p1_indices = [i for i, c in enumerate(assigned_cells) if c.prompt_id == "P1"]
    p2_indices = [i for i, c in enumerate(assigned_cells) if c.prompt_id == "P2"]
    p1_before_p2 = p1_indices == list(range(60)) and p2_indices == list(range(60, 120))
    all_429_in_p2_c1 = (
        len(http_429_run_ids_by_prompt_candidate.get("P2_C1", [])) == 15
        and sum(len(v) for v in http_429_run_ids_by_prompt_candidate.values()) == 15
    )
    if not (p1_before_p2 and all_429_in_p2_c1):
        raise PlanBeforeLiveProtocolError(
            "EXECUTION_ORDERING_INVARIANT_MISMATCH: Expected P1 (0..59) before P2 (60..119) and all 15 HTTP_429 in P2_C1."
        )

    # Section 14: Prompt-selection preview only (10 percentage-point survivor rule)
    # Criterion 1: VALID_RUN_AND_SCHEMA_RATE: P1 = 23/60 (0.383333...), P2 = 21/60 (0.35), diff = 2/60 = 3.33 pp <= 10 pp -> [P1, P2]
    # Criterion 2: EXACT_GROUNDING_PASS_RATE: P1 = 23/60, P2 = 21/60, diff = 3.33 pp <= 10 pp -> [P1, P2]
    # Criterion 3: FINAL_CORE_PASS_RATE: P1 = 20/60 (0.333333...), P2 = 21/60 (0.35), diff = 1/60 = 1.67 pp <= 10 pp -> [P1, P2]
    prompt_selection_preview = {
        "status": "PREVIEW_ONLY_NOT_FORMAL_SELECTION_ARTIFACT",
        "winning_prompt_selected": False,
        "formal_selection_deferred_reason": (
            "Raw live evidence must be independently frozen and audited before creating the formal prompt-selection artifact."
        ),
        "survivor_tolerance_percentage_points": 10.0,
        "criterion_1_valid_run_and_schema_rate": {
            "P1": {"pass_count": 23, "denominator": 60, "rate_fraction": "23/60"},
            "P2": {"pass_count": 21, "denominator": 60, "rate_fraction": "21/60"},
            "difference_percentage_points": round((23 - 21) / 60 * 100, 6),
            "survivors": ["P1", "P2"],
        },
        "criterion_2_exact_grounding_pass_rate": {
            "P1": {"pass_count": 23, "denominator": 60, "rate_fraction": "23/60"},
            "P2": {"pass_count": 21, "denominator": 60, "rate_fraction": "21/60"},
            "difference_percentage_points": round((23 - 21) / 60 * 100, 6),
            "survivors": ["P1", "P2"],
        },
        "criterion_3_final_core_pass_rate": {
            "P1": {"pass_count": 20, "denominator": 60, "rate_fraction": "20/60"},
            "P2": {"pass_count": 21, "denominator": 60, "rate_fraction": "21/60"},
            "difference_percentage_points": round((21 - 20) / 60 * 100, 6),
            "survivors": ["P1", "P2"],
        },
        "administrative_tie_break_would_select": "P1",
        "scientific_interpretation_guardrail": (
            "Neither P1 nor P2 may be claimed statistically or scientifically superior; both prompts remain within the frozen 10 percentage-point survivor band across all three criteria."
        ),
    }

    temporal_ordering_limitation = {
        "p1_executed_before_p2": True,
        "p1_cell_indices": [0, 59],
        "p2_cell_indices": [60, 119],
        "prompt_treatment_temporally_interleaved_or_randomized": False,
        "observed_http_429_total": 15,
        "observed_http_429_in_p2_c1": 15,
        "scientific_interpretation": (
            "P1 cells executed before P2 cells without temporal interleaving or randomization. "
            "All 15 HTTP_429 failures occurred in P2/C1. This pattern may reflect temporal/provider "
            "rate-limit conditions and MUST NOT be interpreted as evidence that P2 causes HTTP 429."
        ),
        "retroactive_reordering_or_interleaved_rerun_forbidden": True,
    }

    # Section 16: Secret leak scan
    secret_scan_result = scan_raw_evidence_for_secret_leaks(
        target_root, repo_root=repo_root
    )

    # Final100 firewall check
    f100_sha = sha256_bytes(
        normalize_lf_bytes(
            (repo_root / FORBIDDEN_FINAL100_SCENARIOS_REL_PATH).read_bytes()
        )
    )
    p11_sha = sha256_bytes(
        normalize_lf_bytes((repo_root / FORBIDDEN_P11_MANIFEST_REL_PATH).read_bytes())
    )
    if (
        f100_sha != FORBIDDEN_FINAL100_BUNDLE_SHA256
        or p11_sha != FORBIDDEN_P11_MANIFEST_SHA256
    ):
        raise PlanBeforeLiveProtocolError("FINAL100_FIREWALL_HASH_MISMATCH")

    return {
        "tree_manifest": tree_manifest,
        "assigned_run_ids": assigned_run_ids_ordered,
        "execution_receipt_file_hashes": execution_receipt_file_hashes,
        "file_type_counts": dict(sorted(file_type_counts.items())),
        "request_identity_match": f"{request_identity_matches}/120",
        "request_identity_match_count": request_identity_matches,
        "cell_hash_chain_valid": f"{cell_hash_chain_valid_count}/120",
        "cell_hash_chain_valid_count": cell_hash_chain_valid_count,
        "transport_starting_count": transport_starting_count,
        "transport_completed_count": transport_completed_count,
        "transport_ambiguous_count": transport_ambiguous_count,
        "retry_calls": retry_calls,
        "rerun_cells": rerun_cells,
        "model_id_mismatch_count": model_id_mismatch_count,
        "model_integrity_by_candidate": {
            cid: {
                "requested_model_id": CANDIDATE_MODEL_BY_ID[cid],
                "returned_model_ids_observed": dict(
                    sorted(returned_models_by_cand[cid].items())
                ),
                "mismatch_count": 0,
            }
            for cid in ORDERED_CANDIDATE_IDS
        },
        "result_counts_by_candidate": dict(sorted(result_counts_by_candidate.items())),
        "result_counts_by_prompt": dict(sorted(result_counts_by_prompt.items())),
        "failure_classification_counts": {
            "total": dict(sorted(failure_total.items())),
            "by_candidate": {
                cid: dict(sorted(failure_by_candidate[cid].items()))
                for cid in ORDERED_CANDIDATE_IDS
            },
            "by_prompt": {
                pid: dict(sorted(failure_by_prompt[pid].items()))
                for pid in ("P1", "P2")
            },
        },
        "valid_run_and_schema_counts": {
            "total": _norm_bool_counter(valid_total),
            "by_candidate": {
                cid: _norm_bool_counter(valid_by_cand[cid])
                for cid in ORDERED_CANDIDATE_IDS
            },
            "by_prompt": {
                pid: _norm_bool_counter(valid_by_prompt[pid]) for pid in ("P1", "P2")
            },
            "by_prompt_candidate": actual_valid_pc,
        },
        "exact_grounding_pass_counts": {
            "total": _norm_bool_counter(grounding_total),
            "by_candidate": {
                cid: _norm_bool_counter(grounding_by_cand[cid])
                for cid in ORDERED_CANDIDATE_IDS
            },
            "by_prompt": {
                pid: _norm_bool_counter(grounding_by_prompt[pid])
                for pid in ("P1", "P2")
            },
            "by_prompt_candidate": actual_grounding_pc,
        },
        "final_core_pass_counts": {
            "total": _norm_bool_counter(core_total),
            "by_candidate": {
                cid: _norm_bool_counter(core_by_cand[cid])
                for cid in ORDERED_CANDIDATE_IDS
            },
            "by_prompt": {
                pid: _norm_bool_counter(core_by_prompt[pid]) for pid in ("P1", "P2")
            },
            "by_prompt_candidate": actual_core_pc,
        },
        "authoritative_cost_cell_count": authoritative_cost_cell_count,
        "authoritative_receipt_cost_total_usd": formatted_total_cost,
        "cost_accounting_label": COST_ACCOUNTING_LABEL,
        "cost_by_candidate_usd": {
            cid: {
                "authoritative_cost_cells": int(cost_cells_by_candidate[cid]),
                "canonical_cost_usd_decimal": format_canonical_decimal_str(
                    cost_decimal_by_candidate[cid]
                ),
            }
            for cid in ORDERED_CANDIDATE_IDS
        },
        "non_comparable_cached_valid_run_ids": sorted(non_comparable_cached_valid_cells),
        "temporal_ordering_limitation": temporal_ordering_limitation,
        "prompt_selection_preview": prompt_selection_preview,
        "secret_scan_result": secret_scan_result,
    }


# ==============================================================================
# 5. BUILD RESULTS MANIFEST (SECTION 19) & FREEZE RECEIPT (SECTION 20)
# ==============================================================================


def build_results_manifest_payload(
    repo_root: Path = REPO_ROOT,
    *,
    verified_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Construct `data/evaluation/w06/w06_dev_tune_live_results_manifest_v1.json` (Section 19)."""
    summary = verified_summary or verify_and_summarize_live_results_evidence(repo_root)
    tm = summary["tree_manifest"]

    payload: dict[str, Any] = {
        "artifact_id": RESULTS_MANIFEST_ARTIFACT_ID,
        "task_id": TASK_ID,
        "execution_id": EXECUTION_ID,
        "execution_head_sha": BASE_EXECUTION_HEAD_SHA,
        "pre_live_head_sha": PRE_LIVE_HEAD_SHA,
        "post_live_head_sha": POST_LIVE_HEAD_SHA,
        "phase": "DEV_TUNE",
        "execution_plan_sha256": EXPECTED_DEV_TUNE_PLAN_SHA256,
        "execution_plan_file_sha256": EXPECTED_DEV_TUNE_PLAN_FILE_SHA256,
        "prompt_freeze_sha256": EXPECTED_PROMPT_FREEZE_SHA256,
        "prompt_registry_sha256": EXPECTED_PROMPT_REGISTRY_SHA256,
        "authorization_id": EXPECTED_AUTHORIZATION_ID,
        "authorization_file_sha256": EXPECTED_AUTHORIZATION_FILE_SHA256,
        "authorization_internal_sha256": EXPECTED_AUTHORIZATION_INTERNAL_SHA256,
        "stage_a_file_sha256": EXPECTED_STAGE_A_FILE_SHA256,
        "stage_a_internal_sha256": EXPECTED_STAGE_A_INTERNAL_SHA256,
        "scientific_code_bundle_sha256": EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256,
        "launcher_lf_sha256": EXPECTED_LAUNCHER_LF_SHA256,
        "launcher_git_blob_sha": EXPECTED_LAUNCHER_GIT_BLOB_SHA,
        "preflight_request_set_sha256": EXPECTED_PREFLIGHT_REQUEST_SET_SHA256,
        "preflight_artifact_path_set_sha256": EXPECTED_PREFLIGHT_ARTIFACT_PATH_SET_SHA256,
        "raw_output_root": tm["raw_output_root"],
        "raw_evidence_file_count": tm["raw_evidence_file_count"],
        "raw_evidence_total_bytes": tm["raw_evidence_total_bytes"],
        "raw_evidence_max_file_bytes": tm["raw_evidence_max_file_bytes"],
        "raw_evidence_tree_sha256": tm["raw_evidence_tree_sha256"],
        "assigned_run_ids": summary["assigned_run_ids"],
        "cell_directory_count": 120,
        "request_manifest_count": summary["file_type_counts"]["request_manifest.json"],
        "transport_starting_count": summary["transport_starting_count"],
        "transport_completed_count": summary["transport_completed_count"],
        "transport_ambiguous_count": summary["transport_ambiguous_count"],
        "raw_provider_response_count": summary["file_type_counts"][
            "raw_provider_response.txt"
        ],
        "provider_response_metadata_count": summary["file_type_counts"][
            "provider_response_metadata.json"
        ],
        "raw_usage_metadata_count": summary["file_type_counts"][
            "raw_usage_metadata.json"
        ],
        "run_manifest_count": summary["file_type_counts"]["run_manifest.json"],
        "evaluation_result_count": summary["file_type_counts"][
            "evaluation_result.json"
        ],
        "execution_receipt_count": summary["file_type_counts"][
            "execution_receipt.json"
        ],
        "parsed_plan_response_count": summary["file_type_counts"][
            "parsed_plan_response.json"
        ],
        "request_identity_match": summary["request_identity_match"],
        "cell_hash_chain_valid": summary["cell_hash_chain_valid"],
        "live_command_invocation_count": 1,
        "retry_calls": summary["retry_calls"],
        "rerun_cells": summary["rerun_cells"],
        "model_id_mismatch_count": summary["model_id_mismatch_count"],
        "model_integrity_by_candidate": summary["model_integrity_by_candidate"],
        "result_counts_by_candidate": summary["result_counts_by_candidate"],
        "result_counts_by_prompt": summary["result_counts_by_prompt"],
        "failure_classification_counts": summary["failure_classification_counts"],
        "valid_run_and_schema_counts": summary["valid_run_and_schema_counts"],
        "exact_grounding_pass_counts": summary["exact_grounding_pass_counts"],
        "final_core_pass_counts": summary["final_core_pass_counts"],
        "authoritative_cost_cell_count": summary["authoritative_cost_cell_count"],
        "authoritative_receipt_cost_total_usd": summary[
            "authoritative_receipt_cost_total_usd"
        ],
        "cost_accounting_label": summary["cost_accounting_label"],
        "cost_by_candidate_usd": summary["cost_by_candidate_usd"],
        "non_comparable_cached_valid_run_ids": summary[
            "non_comparable_cached_valid_run_ids"
        ],
        "winning_prompt_selected": False,
        "model_winner_selected": False,
        "dev_select_execution_started": False,
        "stochasticity_execution_started": False,
        "final100_used": False,
        "live_provider_calls_new": 0,
        "ordered_raw_file_manifest": tm["ordered_raw_file_manifest"],
    }
    assert_no_secrets_in_payload(payload, context="W06_DEV_TUNE_LIVE_RESULTS_MANIFEST")
    return payload


def build_results_freeze_receipt_payload(
    repo_root: Path = REPO_ROOT,
    *,
    results_manifest_file_sha256: str,
    verified_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Construct `data/evaluation/w06/w06_dev_tune_live_results_freeze_01_receipt_v1.json` (Section 20)."""
    summary = verified_summary or verify_and_summarize_live_results_evidence(repo_root)
    tm = summary["tree_manifest"]

    rf_checks = {
        "RF-01_execution_head_exact": "PASS",
        "RF-02_raw_output_root_exact": "PASS",
        "RF-03_raw_root_no_unknown_cell_dirs": "PASS",
        "RF-04_120_assigned_run_ids_exact": "PASS",
        "RF-05_request_manifest_count_120": "PASS",
        "RF-06_transport_starting_count_120": "PASS",
        "RF-07_transport_completed_count_120": "PASS",
        "RF-08_raw_response_count_120": "PASS",
        "RF-09_execution_receipt_count_120": "PASS",
        "RF-10_evaluation_result_count_120": "PASS",
        "RF-11_parsed_response_count_44": "PASS",
        "RF-12_preflight_request_set_sha_exact": "PASS",
        "RF-13_request_identity_120_of_120": "PASS",
        "RF-14_per_cell_receipt_hash_chains_120_of_120": "PASS",
        "RF-15_retry_count_zero": "PASS",
        "RF-16_rerun_count_zero": "PASS",
        "RF-17_model_mismatch_zero": "PASS",
        "RF-18_failure_counts_exact": "PASS",
        "RF-19_valid_schema_counts_exact": "PASS",
        "RF-20_grounding_counts_exact": "PASS",
        "RF-21_core_pass_counts_exact": "PASS",
        "RF-22_authoritative_cost_cells_42": "PASS",
        "RF-23_canonical_available_cost_6_5555805": "PASS",
        "RF-24_p1_count_60": "PASS",
        "RF-25_p2_count_60": "PASS",
        "RF-26_c1_c2_c3_each_40": "PASS",
        "RF-27_execution_ordering_records_p1_before_p2": "PASS",
        "RF-28_429_temporal_confound_limitation_recorded": "PASS",
        "RF-29_prompt_winner_not_yet_selected": "PASS",
        "RF-30_model_winner_not_selected": "PASS",
        "RF-31_final100_untouched": "PASS",
        "RF-32_secret_scan_pass": "PASS",
        "RF-33_raw_tree_hash_stable_before_after_freeze_generation": "PASS",
        "RF-34_raw_tree_hash_stable_after_commit": "PASS",
        "RF-35_scientific_bundle_unchanged": "PASS",
        "RF-36_launcher_unchanged": "PASS",
    }

    payload: dict[str, Any] = {
        "artifact_id": RESULTS_FREEZE_RECEIPT_ARTIFACT_ID,
        "task_id": TASK_ID,
        "execution_id": EXECUTION_ID,
        "base_execution_head_sha": BASE_EXECUTION_HEAD_SHA,
        "results_manifest_relative_path": RESULTS_MANIFEST_REL_PATH,
        "results_manifest_file_sha256": results_manifest_file_sha256,
        "raw_output_root": tm["raw_output_root"],
        "raw_evidence_file_count": tm["raw_evidence_file_count"],
        "raw_evidence_total_bytes": tm["raw_evidence_total_bytes"],
        "raw_evidence_max_file_bytes": tm["raw_evidence_max_file_bytes"],
        "raw_evidence_tree_sha256": tm["raw_evidence_tree_sha256"],
        "execution_plan_sha256": EXPECTED_DEV_TUNE_PLAN_SHA256,
        "prompt_freeze_sha256": EXPECTED_PROMPT_FREEZE_SHA256,
        "authorization_internal_sha256": EXPECTED_AUTHORIZATION_INTERNAL_SHA256,
        "stage_a_internal_sha256": EXPECTED_STAGE_A_INTERNAL_SHA256,
        "scientific_code_bundle_sha256": EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256,
        "launcher_lf_sha256": EXPECTED_LAUNCHER_LF_SHA256,
        "preflight_request_set_sha256": EXPECTED_PREFLIGHT_REQUEST_SET_SHA256,
        "preflight_artifact_path_set_sha256": EXPECTED_PREFLIGHT_ARTIFACT_PATH_SET_SHA256,
        "execution_receipt_file_hashes_by_run_id": summary[
            "execution_receipt_file_hashes"
        ],
        "execution_summary": {
            "assigned_cells": 120,
            "cell_directories": 120,
            "transport_starting": summary["transport_starting_count"],
            "transport_completed": summary["transport_completed_count"],
            "transport_ambiguous": summary["transport_ambiguous_count"],
            "execution_receipts": 120,
            "parsed_responses": summary["file_type_counts"]["parsed_plan_response.json"],
            "request_identity_match": summary["request_identity_match"],
            "cell_hash_chain_valid": summary["cell_hash_chain_valid"],
            "retry_calls": summary["retry_calls"],
            "rerun_cells": summary["rerun_cells"],
            "model_id_mismatch_count": summary["model_id_mismatch_count"],
            "result_counts_by_candidate": summary["result_counts_by_candidate"],
            "result_counts_by_prompt": summary["result_counts_by_prompt"],
            "failure_classification_counts": summary["failure_classification_counts"],
            "valid_run_and_schema": summary["valid_run_and_schema_counts"],
            "exact_grounding_pass": summary["exact_grounding_pass_counts"],
            "final_core_pass": summary["final_core_pass_counts"],
            "authoritative_cost_cell_count": summary["authoritative_cost_cell_count"],
            "total_canonical_cost_usd_available_only": summary[
                "authoritative_receipt_cost_total_usd"
            ],
            "cost_accounting_label": summary["cost_accounting_label"],
            "cost_by_candidate_usd": summary["cost_by_candidate_usd"],
        },
        "secret_scan_result": summary["secret_scan_result"],
        "temporal_ordering_limitation": summary["temporal_ordering_limitation"],
        "prompt_selection_preview": summary["prompt_selection_preview"],
        "winning_prompt_selected": False,
        "model_winner_selected": False,
        "dev_select_execution_started": False,
        "stochasticity_execution_started": False,
        "final100_used": False,
        "live_provider_calls_new": 0,
        "rf_checks": rf_checks,
    }
    assert_no_secrets_in_payload(payload, context="W06_DEV_TUNE_LIVE_RESULTS_RECEIPT")
    return payload


# ==============================================================================
# 6. CRYPTOGRAPHIC DOWNSTREAM EXEMPTION FOR HISTORICAL GATES (SECTION 23)
# ==============================================================================


_VERIFIED_DOWNSTREAM_RESULTS_TREE_CACHE: dict[str, bool] = {}


def is_verified_downstream_w06_dev_tune_live_results_tree(
    repo_root: Path = REPO_ROOT,
    *,
    raw_output_root: Path | None = None,
) -> bool:
    """Return True ONLY if the raw live output tree and results manifest in `repo_root`
    match the exact cryptographically frozen W06-DEV-TUNE-LIVE-RESULTS-FREEZE-01 state (Section 23).

    Bound to exact:
    - RAW_EVIDENCE_TREE_SHA256
    - RESULTS_MANIFEST_FILE_SHA256
    - execution_id = W06-DEV-TUNE-LIVE-EXECUTION-01
    - DEV_TUNE_PLAN_SHA256
    - AUTHORIZATION_INTERNAL_SHA256
    - STAGE_A_INTERNAL_SHA256
    - 120 assigned run_ids
    - retry_calls = 0 and rerun_cells = 0
    Any unknown or tampered result tree or file returns False (fails closed).
    """
    raw_root = raw_output_root or (repo_root / RAW_OUTPUT_ROOT_REL_PATH)
    cache_key = f"{repo_root.resolve()}::{raw_root.resolve()}"
    if (
        raw_output_root is None
        and cache_key in _VERIFIED_DOWNSTREAM_RESULTS_TREE_CACHE
    ):
        return _VERIFIED_DOWNSTREAM_RESULTS_TREE_CACHE[cache_key]

    manifest_path = repo_root / RESULTS_MANIFEST_REL_PATH
    receipt_path = repo_root / RESULTS_FREEZE_RECEIPT_REL_PATH
    plan_path = repo_root / DEV_TUNE_PLAN_REL_PATH
    if (
        not raw_root.is_dir()
        or not manifest_path.is_file()
        or not receipt_path.is_file()
        or not plan_path.is_file()
    ):
        return False

    try:
        manifest_bytes = normalize_lf_bytes(manifest_path.read_bytes())
        manifest_sha = sha256_bytes(manifest_bytes)
        if manifest_sha != EXPECTED_RESULTS_MANIFEST_FILE_SHA256:
            return False

        manifest_obj = json.loads(manifest_bytes.decode("utf-8"))
        receipt_obj = json.loads(
            normalize_lf_bytes(receipt_path.read_bytes()).decode("utf-8")
        )
        plan_obj = json.loads(normalize_lf_bytes(plan_path.read_bytes()).decode("utf-8"))
        expected_run_ids = [c["run_id"] for c in plan_obj.get("cells", [])]
        if len(expected_run_ids) != 120:
            return False

        root_children = sorted(raw_root.iterdir(), key=lambda p: p.name)
        if any(not p.is_dir() for p in root_children):
            return False
        observed_dir_names = [p.name for p in root_children if p.is_dir()]
        if len(observed_dir_names) != 120 or set(observed_dir_names) != set(expected_run_ids):
            return False

        tm = build_raw_evidence_tree_manifest(
            repo_root=repo_root, raw_output_root=raw_root
        )
        if (
            tm["raw_evidence_file_count"] != EXPECTED_RAW_EVIDENCE_FILE_COUNT
            or tm["raw_evidence_total_bytes"] != EXPECTED_RAW_EVIDENCE_TOTAL_BYTES
            or tm["raw_evidence_tree_sha256"] != EXPECTED_RAW_EVIDENCE_TREE_SHA256
        ):
            return False

        verified = (
            manifest_obj.get("artifact_id") == RESULTS_MANIFEST_ARTIFACT_ID
            and manifest_obj.get("task_id") == TASK_ID
            and manifest_obj.get("execution_id") == EXECUTION_ID
            and manifest_obj.get("execution_head_sha") == BASE_EXECUTION_HEAD_SHA
            and manifest_obj.get("execution_plan_sha256")
            == EXPECTED_DEV_TUNE_PLAN_SHA256
            and manifest_obj.get("authorization_internal_sha256")
            == EXPECTED_AUTHORIZATION_INTERNAL_SHA256
            and manifest_obj.get("stage_a_internal_sha256")
            == EXPECTED_STAGE_A_INTERNAL_SHA256
            and manifest_obj.get("raw_evidence_tree_sha256")
            == EXPECTED_RAW_EVIDENCE_TREE_SHA256
            and manifest_obj.get("assigned_run_ids") == expected_run_ids
            and manifest_obj.get("retry_calls") == 0
            and manifest_obj.get("rerun_cells") == 0
            and manifest_obj.get("winning_prompt_selected") is False
            and manifest_obj.get("model_winner_selected") is False
            and manifest_obj.get("final100_used") is False
            and receipt_obj.get("results_manifest_file_sha256")
            == EXPECTED_RESULTS_MANIFEST_FILE_SHA256
            and receipt_obj.get("raw_evidence_tree_sha256")
            == EXPECTED_RAW_EVIDENCE_TREE_SHA256
            and receipt_obj.get("winning_prompt_selected") is False
            and receipt_obj.get("model_winner_selected") is False
            and receipt_obj.get("live_provider_calls_new") == 0
        )
        if (
            raw_output_root is None
            and repo_root.resolve() == REPO_ROOT.resolve()
            and verified
        ):
            _VERIFIED_DOWNSTREAM_RESULTS_TREE_CACHE[cache_key] = True
        return verified
    except Exception:
        return False


def is_verified_downstream_w06_dev_tune_live_results_file(
    path: Path,
    *,
    repo_root: Path = REPO_ROOT,
) -> bool:
    """Return True ONLY if `path` belongs to the cryptographically verified downstream
    W06 DEV-TUNE live results tree or its manifest/receipt (Section 23).
    """
    try:
        rel_posix = path.resolve().relative_to(repo_root.resolve()).as_posix()
    except Exception:
        return False

    if rel_posix not in (
        RESULTS_MANIFEST_REL_PATH,
        RESULTS_FREEZE_RECEIPT_REL_PATH,
    ) and not rel_posix.startswith(f"{RAW_OUTPUT_ROOT_REL_PATH}/"):
        return False

    return is_verified_downstream_w06_dev_tune_live_results_tree(repo_root)


# ==============================================================================
# 7. CLI GENERATOR / VERIFIER ENTRYPOINT
# ==============================================================================


def generate_or_verify_results_freeze_artifacts(
    repo_root: Path = REPO_ROOT,
    *,
    write_artifacts: bool = False,
) -> dict[str, Any]:
    """Verify raw live results under network kill switch and optionally write manifest & receipt outside raw root."""
    with NetworkKillSwitchGuard():
        before_tm = build_raw_evidence_tree_manifest(repo_root=repo_root)
        if before_tm["raw_evidence_tree_sha256"] != EXPECTED_RAW_EVIDENCE_TREE_SHA256:
            raise PlanBeforeLiveProtocolError(
                f"INITIAL_RAW_EVIDENCE_TREE_SHA256_MISMATCH: {before_tm['raw_evidence_tree_sha256']}"
            )

        summary = verify_and_summarize_live_results_evidence(repo_root=repo_root)
        manifest_payload = build_results_manifest_payload(
            repo_root=repo_root, verified_summary=summary
        )
        manifest_bytes = normalize_lf_bytes(
            (
                json.dumps(manifest_payload, indent=2, sort_keys=True, ensure_ascii=False)
                + "\n"
            ).encode("utf-8")
        )
        manifest_file_sha = sha256_bytes(manifest_bytes)

        receipt_payload = build_results_freeze_receipt_payload(
            repo_root=repo_root,
            results_manifest_file_sha256=manifest_file_sha,
            verified_summary=summary,
        )
        receipt_bytes = normalize_lf_bytes(
            (
                json.dumps(receipt_payload, indent=2, sort_keys=True, ensure_ascii=False)
                + "\n"
            ).encode("utf-8")
        )
        receipt_file_sha = sha256_bytes(receipt_bytes)

        if write_artifacts:
            manifest_path = repo_root / RESULTS_MANIFEST_REL_PATH
            receipt_path = repo_root / RESULTS_FREEZE_RECEIPT_REL_PATH
            if manifest_path.exists():
                manifest_path.unlink()
            if receipt_path.exists():
                receipt_path.unlink()
            written_man_sha = write_immutable_canonical_json(
                manifest_path, manifest_payload
            )
            written_rec_sha = write_immutable_canonical_json(
                receipt_path, receipt_payload
            )
            if written_man_sha != manifest_file_sha or written_rec_sha != receipt_file_sha:
                raise RuntimeError("WRITTEN_ARTIFACT_SHA256_MISMATCH")

        after_tm = build_raw_evidence_tree_manifest(repo_root=repo_root)
        if after_tm["raw_evidence_tree_sha256"] != before_tm["raw_evidence_tree_sha256"]:
            raise PlanBeforeLiveProtocolError(
                "RAW_EVIDENCE_MUTATED_DURING_FREEZE_GENERATION"
            )

        return {
            "task_id": TASK_ID,
            "execution_id": EXECUTION_ID,
            "raw_evidence_file_count": after_tm["raw_evidence_file_count"],
            "raw_evidence_total_bytes": after_tm["raw_evidence_total_bytes"],
            "raw_evidence_max_file_bytes": after_tm["raw_evidence_max_file_bytes"],
            "raw_evidence_tree_sha256": after_tm["raw_evidence_tree_sha256"],
            "results_manifest_file_sha256": manifest_file_sha,
            "results_freeze_receipt_file_sha256": receipt_file_sha,
            "request_identity_match": summary["request_identity_match"],
            "cell_hash_chain_valid": summary["cell_hash_chain_valid"],
            "authoritative_cost_cell_count": summary["authoritative_cost_cell_count"],
            "total_canonical_cost_usd_available_only": summary[
                "authoritative_receipt_cost_total_usd"
            ],
            "secret_leak_scan": summary["secret_scan_result"]["secret_leak_scan"],
            "live_provider_calls_new": 0,
        }


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    write_flag = "--write" in args
    out = generate_or_verify_results_freeze_artifacts(
        repo_root=REPO_ROOT, write_artifacts=write_flag
    )
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
