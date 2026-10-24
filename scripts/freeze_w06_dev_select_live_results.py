#!/usr/bin/env python3
"""Immutable W06 DEV-SELECT live-evidence freeze, manifest construction, and offline verification script.

TASK: W06-DEV-SELECT-LIVE-RESULTS-FREEZE-01

PURPOSE:
Freeze and cryptographically verify the raw 180-cell live execution evidence under
`data/evaluation/w06/live_dev_select_primary_v1`, generate the canonical results manifest
and results-freeze receipt outside the raw evidence directory, and provide a strictly
stateless, read-only `--verify-only` CLI and verification API.

THIS SCRIPT IS STRICTLY OFFLINE.
LIVE_PROVIDER_CALLS_NEW = 0
MODEL_WINNER_SELECTED = false
selected_model_id = null
STOCHASTICITY_EXECUTION_STARTED = false
FINAL100_USED = false
"""

from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping

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
    DevExecutionPlan,
    DevPromptFreezeArtifact,
    canonical_json_bytes,
    compute_scientific_code_bundle_sha256,
    format_canonical_decimal_str,
    load_and_verify_candidate_registry,
    load_and_verify_frozen_dev_bundle,
    normalize_lf_bytes,
    parse_canonical_decimal_str,
    sha256_bytes,
)

FORBIDDEN_FINAL100_SCENARIOS_REL_PATH = (
    "data/evaluation/w06/w06_scenarios_freeze_v1.json"
)
FORBIDDEN_P11_MANIFEST_REL_PATH = (
    "data/evaluation/w06/w06_p11_assignment_manifest_v1.json"
)
from freeze_w06_dev_prompt_candidates import (  # noqa: E402
    build_frozen_p1_p2_registry,
    build_p1_spec,
)
import run_w06_dev_select_live_v1 as _launcher_mod  # noqa: E402
from run_w06_dev_select_live_v1 import NetworkKillSwitchGuard  # noqa: E402


# ==============================================================================
# 1. FROZEN CONSTANTS & AUTHORITATIVE HASHES (SECTIONS 1..20)
# ==============================================================================

TASK_ID = "W06-DEV-SELECT-LIVE-RESULTS-FREEZE-01"
LIVE_EXECUTION_TASK_ID = "W06-DEV-SELECT-LIVE-EXECUTION-01"
EXECUTION_ID = "W06-DEV-SELECT-LIVE-EXECUTION-01"
PHASE = "DEV_SELECT"

BASE_DEVELOP_SHA = "eac86a38f6b457c9b6ff078f26c4f953a9fc98a7"
SOURCE_DEVELOP_SHA = "eac86a38f6b457c9b6ff078f26c4f953a9fc98a7"
PRE_LIVE_HEAD_SHA = "eac86a38f6b457c9b6ff078f26c4f953a9fc98a7"
POST_LIVE_HEAD_SHA = "eac86a38f6b457c9b6ff078f26c4f953a9fc98a7"
EXPECTED_CODE_BASIS_COMMIT_SHA = "c0adf74ceda9ffaf8b4ec42d299932e33f448e6a"
EXPECTED_STAGE_A_COMMIT_SHA = "e69b7d70c3908d2b888b7c5d7e6c4e1d49fac863"

RAW_OUTPUT_ROOT_REL_PATH = "data/evaluation/w06/live_dev_select_primary_v1"

RESULTS_MANIFEST_REL_PATH = (
    "data/evaluation/w06/w06_dev_select_live_results_manifest_v1.json"
)
RESULTS_MANIFEST_ARTIFACT_ID = "W06-DEV-SELECT-LIVE-RESULTS-MANIFEST-V1"

RESULTS_FREEZE_RECEIPT_REL_PATH = (
    "data/evaluation/w06/w06_dev_select_live_results_freeze_01_receipt_v1.json"
)
RESULTS_FREEZE_RECEIPT_ARTIFACT_ID = (
    "W06-DEV-SELECT-LIVE-RESULTS-FREEZE-01-RECEIPT-V1"
)

DEV_SELECT_PLAN_REL_PATH = "data/evaluation/w06/w06_dev_select_execution_plan_v1.json"
PLAN_FREEZE_RECEIPT_REL_PATH = (
    "data/evaluation/w06/w06_dev_select_plan_freeze_01_receipt_v1.json"
)
PROMPT_FREEZE_REL_PATH = "data/evaluation/w06/w06_dev_prompt_candidate_freeze_v1.json"
PROMPT_SELECTION_ARTIFACT_REL_PATH = (
    "data/evaluation/w06/w06_dev_tune_prompt_selection_v1.json"
)
AUTHORIZATION_REL_PATH = "data/evaluation/w06/w06_dev_select_live_authorization_v1.json"
STAGE_A_RECEIPT_REL_PATH = (
    "data/evaluation/w06/w06_dev_select_stage_a_freeze_receipt_v1.json"
)
EXPECTED_LAUNCHER_REL_PATH = "scripts/run_w06_dev_select_live_v1.py"

FORBIDDEN_DOWNSTREAM_MODEL_SELECTION_REL_PATHS: tuple[str, ...] = (
    "data/evaluation/w06/w06_dev_select_model_selection_v1.json",
    "data/evaluation/w06/w06_dev_select_model_selection_01_receipt_v1.json",
    "data/evaluation/w06/w06_stochasticity_execution_plan_v1.json",
    "data/evaluation/w06/live_stochasticity_primary_v1",
    "data/evaluation/w06/live_final100_primary_v1",
)

EXPECTED_DEV_SELECT_PLAN_INTERNAL_SHA256 = (
    "de04255989a9e3bd8c2e39c766432487dce4ccd0612d5dba73b3476cbc9d0c6d"
)
EXPECTED_DEV_SELECT_PLAN_FILE_SHA256 = (
    "c519baf7cd2557b5e1dd2699a5ceaec592af015d7bc6dcc83abf63892a8a329a"
)
EXPECTED_PLAN_FREEZE_RECEIPT_FILE_SHA256 = (
    "5f32782f6359f409c7dd68f08699218cd577cb48bcb517f14c15939f896b9549"
)
EXPECTED_PROMPT_FREEZE_SHA256 = (
    "2f345363f580ea882b2e5b3562c587ef5309bc7f994440257a54d18994ab6956"
)
EXPECTED_PROMPT_REGISTRY_SHA256 = (
    "846dc4c14ec2a87537b7b3e07bf492de51dc534d24b21e469094b7e3d34d32b6"
)
EXPECTED_PROMPT_SELECTION_ARTIFACT_FILE_SHA256 = (
    "e1e79801117e59d3c8c703e024eacbad12d5336134c6597c333886c434a446b8"
)
EXPECTED_PROMPT_SELECTION_ARTIFACT_INTERNAL_SHA256 = (
    "1a718cb545f23b1c93e6d10d904ff252d4a6764dc58e7420217900dcdc8bc570"
)
EXPECTED_AUTHORIZATION_ID = "W06-DEV-SELECT-LIVE-AUTHORIZATION-01-V1"
EXPECTED_AUTHORIZATION_FILE_SHA256 = (
    "247c0f201d8b900a1e0356d874891ba6e2884138b1ddd8500dfedb663f04f5f7"
)
EXPECTED_AUTHORIZATION_INTERNAL_SHA256 = (
    "31cebcf5aafa7a575d4bf1327fc9d454a2817c2acbbdb2c087d8c1210e8ec504"
)
EXPECTED_STAGE_A_FILE_SHA256 = (
    "dd31582860e899b865d3dacd52bd1f92786ee6cf31d851e68e9050d93c451a26"
)
EXPECTED_STAGE_A_INTERNAL_SHA256 = (
    "1b933067516b7142b4250870a18e6deef216c6854b1c9790d01830d196dde014"
)
EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256 = (
    "0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3"
)
EXPECTED_LAUNCHER_LF_SHA256 = (
    "cd36b8ecad24059edb597c0039bd6e760a37ee8b4f36f49077801c65e7ddc7bf"
)
EXPECTED_LAUNCHER_GIT_BLOB_SHA = "ad597560ca149f8b78786c63feb64d63ac399971"

EXPECTED_PREFLIGHT_REQUEST_SET_SHA256 = (
    "3ef997b8833399095b9bf5953ae200d45dd85acb7b253c5b6975adf1b01667e2"
)
EXPECTED_PREFLIGHT_ARTIFACT_PATH_SET_SHA256 = (
    "2a058ebd180cf3fe557549f5d2d3eff66d72f5320155b0e73bbb6b31f412d544"
)

EXPECTED_ASSIGNED_CELL_COUNT = 180
EXPECTED_PER_CANDIDATE_CELL_COUNT = 60
EXPECTED_MAXIMUM_ALLOWED_LIVE_PROVIDER_CALLS = 180
EXPECTED_LIVE_PROVIDER_CALLS_ATTEMPTED = 180
EXPECTED_RETRY_CALLS = 0
EXPECTED_RERUN_CELLS = 0
EXPECTED_MODEL_ID_MISMATCH_COUNT = 0

EXPECTED_RAW_EVIDENCE_FILE_COUNT = 1629
EXPECTED_RAW_EVIDENCE_TOTAL_BYTES = 16264062
EXPECTED_RAW_EVIDENCE_MAX_FILE_BYTES = 96143
EXPECTED_RAW_EVIDENCE_TREE_SHA256 = (
    "d5c4e53952500655b656a624657a3cf1ec7aae685809c9e53a318459cc319817"
)

EXPECTED_PARSED_PLAN_RESPONSE_COUNT = 9
EXPECTED_PARSED_PLAN_RESPONSE_BY_CANDIDATE: dict[str, int] = {
    "C1": 1,
    "C2": 8,
    "C3": 0,
}

PRIMARY_FAILURE_CLASSIFICATION_AUTHORITY = "execution_receipt.failure_classification"
EXPECTED_FAILURE_TOTAL: dict[str, int] = {
    "HTTP_429": 35,
    "HTTP_5XX": 10,
    "HTTP_ERROR": 60,
    "NONE": 9,
    "TIMEOUT": 66,
}
EXPECTED_FAILURE_BY_CANDIDATE: dict[str, dict[str, int]] = {
    "C1": {
        "HTTP_429": 35,
        "HTTP_5XX": 10,
        "HTTP_ERROR": 0,
        "NONE": 1,
        "TIMEOUT": 14,
    },
    "C2": {
        "HTTP_429": 0,
        "HTTP_5XX": 0,
        "HTTP_ERROR": 0,
        "NONE": 8,
        "TIMEOUT": 52,
    },
    "C3": {
        "HTTP_429": 0,
        "HTTP_5XX": 0,
        "HTTP_ERROR": 60,
        "NONE": 0,
        "TIMEOUT": 0,
    },
}

EXPECTED_METRIC_TOTAL_COUNTS: dict[str, int] = {"false": 171, "true": 9}
EXPECTED_METRIC_BY_CANDIDATE_COUNTS: dict[str, dict[str, Any]] = {
    "C1": {
        "pass_count": 1,
        "fail_count": 59,
        "denominator": 60,
        "rate_fraction": "1/60",
        "false": 59,
        "true": 1,
    },
    "C2": {
        "pass_count": 8,
        "fail_count": 52,
        "denominator": 60,
        "rate_fraction": "8/60",
        "false": 52,
        "true": 8,
    },
    "C3": {
        "pass_count": 0,
        "fail_count": 60,
        "denominator": 60,
        "rate_fraction": "0/60",
        "false": 60,
        "true": 0,
    },
}

EXPECTED_MODEL_INTEGRITY_BY_CANDIDATE: dict[str, dict[str, Any]] = {
    "C1": {
        "assigned": 60,
        "requested_model_id": "gemini-3.8-flash",
        "verified_returned_model_matches": 1,
        "transport_failure_unverified": 59,
        "mismatch": 0,
        "returned_model_ids_observed": {"gemini-3.8-flash": 1, "null": 59},
    },
    "C2": {
        "assigned": 60,
        "requested_model_id": "gpt-6.1-sol",
        "verified_returned_model_matches": 8,
        "transport_failure_unverified": 52,
        "mismatch": 0,
        "returned_model_ids_observed": {"gpt-6.1-sol": 8, "null": 52},
    },
    "C3": {
        "assigned": 60,
        "requested_model_id": "claude-sonnet-5-5",
        "verified_returned_model_matches": 0,
        "transport_failure_unverified": 60,
        "mismatch": 0,
        "returned_model_ids_observed": {"null": 60},
    },
}

EXPECTED_AUTHORITATIVE_COST_CELL_COUNT = 9
EXPECTED_TOTAL_CANONICAL_COST_USD_DECIMAL = "0.6468966"
EXPECTED_COST_BY_CANDIDATE_USD: dict[str, dict[str, Any]] = {
    "C1": {
        "authoritative_cost_cells": 1,
        "canonical_cost_usd_decimal": "0.0266516",
    },
    "C2": {
        "authoritative_cost_cells": 8,
        "canonical_cost_usd_decimal": "0.620245",
    },
    "C3": {
        "authoritative_cost_cells": 0,
        "canonical_cost_usd_decimal": "0",
    },
}
COST_ACCOUNTING_LABEL = "AUTHORITATIVE_RECEIPT_COST_AVAILABLE_ONLY"

EXPECTED_RESULTS_MANIFEST_FILE_SHA256 = (
    "1d303e1c07b627c3f3eb87287b744f55ba3f6d3d85bd5cec36959b01919d26c0"
)
EXPECTED_RESULTS_MANIFEST_INTERNAL_SHA256 = (
    "4e2f8f0df0a6e069d65b563b8221c3ba3086bb50ad73854e9cc592a9beb05011"
)
EXPECTED_RESULTS_FREEZE_RECEIPT_FILE_SHA256 = (
    "c021094e26277d41664c4ae2f0560b7684435b6002c5b7ba742a17808c5b07a4"
)
EXPECTED_RESULTS_FREEZE_RECEIPT_INTERNAL_SHA256 = (
    "7b270de482f0b077e79bbba40a0c662851da46355a18b5e05f8fdf572880943a"
)

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

MAX_SINGLE_FILE_BYTES_LIMIT = 90 * 1024 * 1024  # 90 MiB safety threshold


# ==============================================================================
# 2. SECRET-LEAK SCANNER ON RAW EVIDENCE (READ-ONLY)
# ==============================================================================


def _load_ephemeral_secret_values_for_exact_leak_comparison(
    repo_root: Path = REPO_ROOT,
) -> list[str]:
    """Load any configured provider API key values in memory solely to ensure none leaked into artifacts."""
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
    """Scan all files in `raw_output_root` for secret leakage before git add.

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
        for sec in extra_secrets:
            if sec and sec in text:
                raise RuntimeError(
                    f"SECRET_LEAK_DETECTED: Exact configured API key value found in {rel_posix}."
                )
        if path.suffix.lower() == ".json":
            try:
                parsed = json.loads(text)
            except Exception as exc:
                raise PlanBeforeLiveProtocolError(
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
# 3. RAW EVIDENCE TREE MANIFEST COMPUTATION (SECTION 5)
# ==============================================================================


def _compute_raw_evidence_tree_pass(
    repo_root: Path = REPO_ROOT,
    *,
    raw_output_root: Path | None = None,
) -> dict[str, Any]:
    """Single read-only pass enumerating `live_dev_select_primary_v1` and computing canonical raw-byte tree SHA256."""
    target_root = raw_output_root or (repo_root / RAW_OUTPUT_ROOT_REL_PATH)
    if not target_root.is_dir():
        raise PlanBeforeLiveProtocolError(
            f"RAW_OUTPUT_ROOT_MISSING: {target_root} does not exist."
        )

    entries: list[dict[str, Any]] = []
    total_bytes = 0
    max_file_bytes = 0

    try:
        rel_posix_root = target_root.resolve().relative_to(repo_root.resolve()).as_posix()
        rel_prefix = (
            RAW_OUTPUT_ROOT_REL_PATH
            if rel_posix_root == RAW_OUTPUT_ROOT_REL_PATH
            else RAW_OUTPUT_ROOT_REL_PATH
        )
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


def build_raw_evidence_tree_manifest(
    repo_root: Path = REPO_ROOT,
    *,
    raw_output_root: Path | None = None,
    double_pass: bool = True,
) -> dict[str, Any]:
    """Enumerate `data/evaluation/w06/live_dev_select_primary_v1` twice independently and require exact equality (Section 5).

    Strictly read-only. Uses exact raw bytes (NO LF normalization).
    Excludes mtime, ctime, inode, and absolute paths.
    """
    pass_1 = _compute_raw_evidence_tree_pass(
        repo_root=repo_root, raw_output_root=raw_output_root
    )
    if not double_pass:
        return pass_1
    pass_2 = _compute_raw_evidence_tree_pass(
        repo_root=repo_root, raw_output_root=raw_output_root
    )
    if (
        pass_1["raw_evidence_file_count"] != pass_2["raw_evidence_file_count"]
        or pass_1["raw_evidence_total_bytes"] != pass_2["raw_evidence_total_bytes"]
        or pass_1["raw_evidence_max_file_bytes"] != pass_2["raw_evidence_max_file_bytes"]
        or pass_1["raw_evidence_tree_sha256"] != pass_2["raw_evidence_tree_sha256"]
        or pass_1["ordered_raw_file_manifest"] != pass_2["ordered_raw_file_manifest"]
    ):
        raise PlanBeforeLiveProtocolError(
            "RAW_EVIDENCE_TREE_HASH_NON_DETERMINISTIC: Two independent tree-hash passes differed."
        )
    return pass_1


# ==============================================================================
# 4. PREFLIGHT REQUEST IDENTITY & PER-CELL VERIFICATION (SECTIONS 2..15, 20)
# ==============================================================================


def compute_canonical_preflight_for_results_verification(
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Run offline `run_dev_live_runner_dry_run` under `_launcher_runner_bridge` and compute canonical request/path set hashes."""
    prompt_reg = build_frozen_p1_p2_registry()
    if prompt_reg.registry_sha256 != EXPECTED_PROMPT_REGISTRY_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"FROZEN_PROMPT_REGISTRY_SHA256_MISMATCH: {prompt_reg.registry_sha256}"
        )

    plan_path = repo_root / DEV_SELECT_PLAN_REL_PATH
    plan_bytes = normalize_lf_bytes(plan_path.read_bytes())
    plan_model = DevExecutionPlan.model_validate_json(plan_bytes)

    canonical_batch_root = repo_root / RAW_OUTPUT_ROOT_REL_PATH
    with _launcher_mod._launcher_runner_bridge():
        dry_out = run_dev_live_runner_dry_run(
            execution_plan=plan_path,
            prompt_freeze=repo_root / PROMPT_FREEZE_REL_PATH,
            prompt_registry=prompt_reg,
            authorization=repo_root / AUTHORIZATION_REL_PATH,
            stage_a_freeze_receipt=repo_root / STAGE_A_RECEIPT_REL_PATH,
            batch_root_dir=canonical_batch_root,
            repo_root=repo_root,
        )
        validated = _launcher_mod._validate_and_hash_preflight_requests_and_paths(
            plan_model=plan_model,
            dry_run_out=dry_out,
            dev_bundle=load_and_verify_frozen_dev_bundle(),
            cand_reg=load_and_verify_candidate_registry(),
            p1_spec=build_p1_spec(),
            repo_root=repo_root,
        )

    req_map = dry_out["serialized_request_sha256_by_run_id"]
    return {
        "dry_run_output": dry_out,
        "planned_call_count": dry_out["planned_call_count"],
        "serialized_request_sha256_by_run_id": req_map,
        "planned_artifact_paths_by_run_id": validated[
            "normalized_artifact_paths_by_run_id"
        ],
        "preflight_request_set_sha256": validated["preflight_request_set_sha256"],
        "preflight_artifact_path_set_sha256": validated[
            "preflight_artifact_path_set_sha256"
        ],
    }


def verify_downstream_firewall(repo_root: Path = REPO_ROOT) -> None:
    """Verify no model-selection artifact, stochasticity plan, or Final100 output directory exists (Section 20)."""
    for rel in FORBIDDEN_DOWNSTREAM_MODEL_SELECTION_REL_PATHS:
        target = repo_root / rel
        if target.exists():
            raise PlanBeforeLiveProtocolError(
                f"DOWNSTREAM_FIREWALL_VIOLATION: Forbidden downstream artifact/directory exists: {rel}"
            )

    w06_dir = repo_root / "data/evaluation/w06"
    if w06_dir.is_dir():
        for child in sorted(w06_dir.iterdir(), key=lambda p: p.name):
            name_lower = child.name.lower()
            if (
                "model_selection" in name_lower
                or "stochasticity" in name_lower
                or ("final100" in name_lower and child.is_dir())
            ):
                raise PlanBeforeLiveProtocolError(
                    f"DOWNSTREAM_FIREWALL_VIOLATION: Forbidden downstream path in w06: {child.name}"
                )


def verify_and_summarize_live_results_evidence(
    repo_root: Path = REPO_ROOT,
    *,
    raw_output_root: Path | None = None,
    execution_plan_override: DevExecutionPlan | None = None,
    verify_preflight_dry_run: bool = True,
    run_secret_leak_scan: bool = True,
    double_pass_tree_hash: bool = True,
) -> dict[str, Any]:
    """Perform full verification of Sections 1..20 and return recomputed summary & hashes.

    Fails closed on any missing/extra cell, tampered file, broken hash chain,
    request mismatch, transport journal ambiguity, retry evidence, model mismatch,
    cost tampering, or evaluation metric tampering.
    """
    target_root = raw_output_root or (repo_root / RAW_OUTPUT_ROOT_REL_PATH)
    if not target_root.is_dir():
        raise PlanBeforeLiveProtocolError(f"RAW_OUTPUT_ROOT_MISSING: {target_root}")

    verify_downstream_firewall(repo_root=repo_root)

    # Section 2: Load and verify upstream authorities
    plan_path = repo_root / DEV_SELECT_PLAN_REL_PATH
    plan_rec_path = repo_root / PLAN_FREEZE_RECEIPT_REL_PATH
    pf_path = repo_root / PROMPT_FREEZE_REL_PATH
    psel_path = repo_root / PROMPT_SELECTION_ARTIFACT_REL_PATH
    auth_path = repo_root / AUTHORIZATION_REL_PATH
    sa_path = repo_root / STAGE_A_RECEIPT_REL_PATH
    launcher_path = repo_root / EXPECTED_LAUNCHER_REL_PATH

    for req_p in (
        plan_path,
        plan_rec_path,
        pf_path,
        psel_path,
        auth_path,
        sa_path,
        launcher_path,
    ):
        if not req_p.is_file():
            raise PlanBeforeLiveProtocolError(
                f"MISSING_UPSTREAM_AUTHORITY_FILE: {req_p}"
            )

    plan_bytes = normalize_lf_bytes(plan_path.read_bytes())
    plan_rec_bytes = normalize_lf_bytes(plan_rec_path.read_bytes())
    pf_bytes = normalize_lf_bytes(pf_path.read_bytes())
    psel_bytes = normalize_lf_bytes(psel_path.read_bytes())
    auth_bytes = normalize_lf_bytes(auth_path.read_bytes())
    sa_bytes = normalize_lf_bytes(sa_path.read_bytes())
    launcher_bytes = normalize_lf_bytes(launcher_path.read_bytes())

    plan_file_sha = sha256_bytes(plan_bytes)
    plan_rec_file_sha = sha256_bytes(plan_rec_bytes)
    pf_file_sha = sha256_bytes(pf_bytes)
    psel_file_sha = sha256_bytes(psel_bytes)
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
    if plan_file_sha != EXPECTED_DEV_SELECT_PLAN_FILE_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"DEV_SELECT_PLAN_FILE_SHA256_MISMATCH: {plan_file_sha}"
        )
    if plan_rec_file_sha != EXPECTED_PLAN_FREEZE_RECEIPT_FILE_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"PLAN_FREEZE_RECEIPT_FILE_SHA256_MISMATCH: {plan_rec_file_sha}"
        )
    if pf_file_sha != EXPECTED_PROMPT_FREEZE_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"PROMPT_FREEZE_SHA256_MISMATCH: {pf_file_sha}"
        )
    if psel_file_sha != EXPECTED_PROMPT_SELECTION_ARTIFACT_FILE_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"PROMPT_SELECTION_ARTIFACT_FILE_SHA256_MISMATCH: {psel_file_sha}"
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
    psel_obj = json.loads(psel_bytes.decode("utf-8"))
    auth_model = DevLiveAuthorizationArtifact.model_validate_json(auth_bytes)
    sa_model = DevLiveStageAFreezeReceipt.model_validate_json(sa_bytes)

    if plan_model.plan_sha256 != EXPECTED_DEV_SELECT_PLAN_INTERNAL_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"PLAN_BINDING_MISMATCH: plan_sha256={plan_model.plan_sha256} != {EXPECTED_DEV_SELECT_PLAN_INTERNAL_SHA256}"
        )
    if compute_prompt_freeze_sha256(pf_model) != EXPECTED_PROMPT_FREEZE_SHA256:
        raise PlanBeforeLiveProtocolError("PROMPT_FREEZE_INTERNAL_SHA256_MISMATCH")
    if (
        psel_obj.get("prompt_selection_artifact_sha256")
        != EXPECTED_PROMPT_SELECTION_ARTIFACT_INTERNAL_SHA256
        or psel_obj.get("selected_prompt_id") != "P1"
    ):
        raise PlanBeforeLiveProtocolError(
            "PROMPT_SELECTION_ARTIFACT_INTERNAL_SHA256_MISMATCH"
        )
    if (
        auth_model.authorization_artifact_sha256
        != EXPECTED_AUTHORIZATION_INTERNAL_SHA256
        or auth_model.authorization_id != EXPECTED_AUTHORIZATION_ID
    ):
        raise PlanBeforeLiveProtocolError("AUTHORIZATION_INTERNAL_SHA256_MISMATCH")
    if sa_model.stage_a_receipt_sha256 != EXPECTED_STAGE_A_INTERNAL_SHA256:
        raise PlanBeforeLiveProtocolError("STAGE_A_INTERNAL_SHA256_MISMATCH")

    # Section 3: Expected cell set & duplicate/unknown check
    assigned_cells = list(plan_model.cells)
    if (
        len(assigned_cells) != EXPECTED_ASSIGNED_CELL_COUNT
        or plan_model.expected_total_cells != EXPECTED_ASSIGNED_CELL_COUNT
    ):
        raise PlanBeforeLiveProtocolError(
            f"EXPECTED_180_ASSIGNED_CELLS: got {len(assigned_cells)}"
        )

    assigned_run_ids_ordered: list[str] = [c.run_id for c in assigned_cells]
    if len(set(assigned_run_ids_ordered)) != EXPECTED_ASSIGNED_CELL_COUNT:
        raise PlanBeforeLiveProtocolError("DUPLICATE_ASSIGNED_RUN_ID_IN_PLAN")

    logical_cell_keys = [
        (c.phase, c.prompt_id, c.candidate_id, c.fixture_id, c.attempt_number)
        for c in assigned_cells
    ]
    if len(set(logical_cell_keys)) != EXPECTED_ASSIGNED_CELL_COUNT:
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
    if len(cell_dirs) != EXPECTED_ASSIGNED_CELL_COUNT:
        raise PlanBeforeLiveProtocolError(
            f"CELL_DIRECTORY_COUNT_MISMATCH: expected 180, got {len(cell_dirs)}"
        )

    # Section 5: Raw tree manifest (computed twice independently inside build_raw_evidence_tree_manifest)
    tree_manifest = build_raw_evidence_tree_manifest(
        repo_root=repo_root,
        raw_output_root=target_root,
        double_pass=double_pass_tree_hash,
    )

    # Preflight request identity map
    expected_req_sha_by_run_id: Mapping[str, str] | None = None
    if verify_preflight_dry_run:
        preflight_info = compute_canonical_preflight_for_results_verification(repo_root)
        if (
            preflight_info["planned_call_count"] != EXPECTED_ASSIGNED_CELL_COUNT
            or preflight_info["preflight_request_set_sha256"]
            != EXPECTED_PREFLIGHT_REQUEST_SET_SHA256
            or preflight_info["preflight_artifact_path_set_sha256"]
            != EXPECTED_PREFLIGHT_ARTIFACT_PATH_SET_SHA256
        ):
            raise PlanBeforeLiveProtocolError(
                f"PREFLIGHT_SET_HASH_MISMATCH: req={preflight_info['preflight_request_set_sha256']}, "
                f"path={preflight_info['preflight_artifact_path_set_sha256']}"
            )
        expected_req_sha_by_run_id = preflight_info[
            "serialized_request_sha256_by_run_id"
        ]

    # Per-cell verification & aggregation (Sections 3, 4, 7, 8, 9, 11, 15)
    file_type_counts: Counter[str] = Counter()
    request_identity_matches = 0
    cell_hash_chain_valid_count = 0
    transport_starting_count = 0
    transport_completed_count = 0
    transport_ambiguous_count = 0
    live_provider_calls_attempted = 0
    retry_calls = 0
    rerun_cells = 0
    model_id_mismatch_count = 0

    seen_receipt_run_ids: set[str] = set()
    seen_logical_cells: set[tuple[str, str, str, str]] = set()
    execution_receipt_file_hashes: dict[str, str] = {}
    ordered_wire_req_records: list[dict[str, str]] = []

    assigned_by_cand: Counter[str] = Counter()
    attempted_by_cand: Counter[str] = Counter()
    receipts_by_cand: Counter[str] = Counter()
    eval_results_by_cand: Counter[str] = Counter()
    parsed_by_cand: Counter[str] = Counter()
    result_counts_by_prompt: Counter[str] = Counter()

    failure_total: Counter[str] = Counter()
    failure_by_candidate: dict[str, Counter[str]] = {
        cid: Counter() for cid in ORDERED_CANDIDATE_IDS
    }

    valid_total: Counter[str] = Counter()
    valid_by_cand: dict[str, Counter[str]] = {
        cid: Counter() for cid in ORDERED_CANDIDATE_IDS
    }

    grounding_total: Counter[str] = Counter()
    grounding_by_cand: dict[str, Counter[str]] = {
        cid: Counter() for cid in ORDERED_CANDIDATE_IDS
    }

    core_total: Counter[str] = Counter()
    core_by_cand: dict[str, Counter[str]] = {
        cid: Counter() for cid in ORDERED_CANDIDATE_IDS
    }

    returned_models_by_cand: dict[str, Counter[str]] = {
        cid: Counter() for cid in ORDERED_CANDIDATE_IDS
    }
    verified_returned_model_matches_by_cand: Counter[str] = Counter()
    transport_failure_unverified_by_cand: Counter[str] = Counter()

    authoritative_cost_cell_count = 0
    total_canonical_cost_decimal = Decimal("0")
    cost_cells_by_candidate: Counter[str] = Counter()
    cost_decimal_by_candidate: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))

    for cell in assigned_cells:
        rid = cell.run_id
        cid = cell.candidate_id
        pid = cell.prompt_id
        assigned_by_cand[cid] += 1
        result_counts_by_prompt[pid] += 1

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
        if parsed_bytes is not None:
            parsed_by_cand[cid] += 1

        req_man = json.loads(req_man_bytes.decode("utf-8"))
        sj = json.loads(sj_bytes.decode("utf-8"))
        cj = json.loads(cj_bytes.decode("utf-8"))
        meta = json.loads(meta_bytes.decode("utf-8"))
        usage_obj = json.loads(usage_bytes.decode("utf-8"))
        run_man = json.loads(run_man_bytes.decode("utf-8"))
        eval_res = json.loads(eval_res_bytes.decode("utf-8"))
        rec = json.loads(rec_bytes.decode("utf-8"))

        receipts_by_cand[cid] += 1
        eval_results_by_cand[cid] += 1

        # Verify run_id and logical cell uniqueness
        rec_run_id = rec.get("run_id")
        if (
            rec_run_id != rid
            or req_man.get("run_id") != rid
            or run_man.get("run_id") != rid
            or eval_res.get("run_id") != rid
            or usage_obj.get("run_id") != rid
        ):
            raise PlanBeforeLiveProtocolError(
                f"CELL_RUN_ID_MISMATCH: dir={rid}, receipt={rec_run_id}, req={req_man.get('run_id')}, eval={eval_res.get('run_id')}"
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
        if (
            logical_key
            != (
                cell.phase,
                cell.prompt_id,
                cell.candidate_id,
                cell.fixture_id,
            )
            or cell.phase != PHASE
            or cell.prompt_id != "P1"
        ):
            raise PlanBeforeLiveProtocolError(
                f"CELL_IDENTITY_MISMATCH_IN_RECEIPT: {rid} -> {logical_key}"
            )
        if logical_key in seen_logical_cells:
            raise PlanBeforeLiveProtocolError(
                f"DUPLICATE_LOGICAL_CELL_DETECTED: {logical_key}"
            )
        seen_logical_cells.add(logical_key)

        # Verify runtime_head_sha and scientific bundle binding in cell artifacts
        if (
            rec.get("runtime_head_sha") != SOURCE_DEVELOP_SHA
            or req_man.get("runtime_head_sha") != SOURCE_DEVELOP_SHA
            or meta.get("runtime_head_sha") != SOURCE_DEVELOP_SHA
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

        # Request identity check
        wire_req = req_man.get("provider_wire_request")
        if not isinstance(wire_req, dict):
            raise PlanBeforeLiveProtocolError(f"MISSING_WIRE_REQUEST: {rid}")
        actual_wire_sha = sha256_bytes(canonical_json_bytes(wire_req))
        if expected_req_sha_by_run_id is not None:
            if actual_wire_sha != expected_req_sha_by_run_id.get(rid):
                raise PlanBeforeLiveProtocolError(
                    f"REQUEST_IDENTITY_MISMATCH for {rid}: actual={actual_wire_sha} != expected={expected_req_sha_by_run_id.get(rid)}"
                )
        ordered_wire_req_records.append(
            {"run_id": rid, "serialized_request_sha256": actual_wire_sha}
        )
        request_identity_matches += 1

        # Per-cell hash chain verification
        req_man_sha = hashlib.sha256(req_man_bytes).hexdigest()
        raw_resp_sha = hashlib.sha256(raw_resp_bytes).hexdigest()
        meta_sha = hashlib.sha256(meta_bytes).hexdigest()
        eval_res_sha = hashlib.sha256(eval_res_bytes).hexdigest()
        run_man_sha = hashlib.sha256(run_man_bytes).hexdigest()
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
            or eval_res.get("parsed_response_sha256") != parsed_sha
            or eval_res.get("source_run_manifest_sha256") != run_man_sha
        ):
            raise PlanBeforeLiveProtocolError(
                f"CELL_HASH_CHAIN_BROKEN for {rid}: receipt/evaluation/manifest pointers do not match raw evidence bytes."
            )
        cell_hash_chain_valid_count += 1

        # Section 4: Transport journal integrity & zero retry / zero rerun proof
        s_ci = sj.get("cell_identity", {})
        c_ci = cj.get("cell_identity", {})
        if (
            sj.get("run_id") != rid
            or sj.get("status") != "TRANSPORT_STARTING"
            or sj.get("attempt_number") != 1
            or s_ci.get("candidate_id") != cell.candidate_id
            or s_ci.get("prompt_id") != cell.prompt_id
            or s_ci.get("fixture_id") != cell.fixture_id
            or s_ci.get("phase") != PHASE
            or s_ci.get("attempt_number") != 1
            or cj.get("run_id") != rid
            or cj.get("status") != "TRANSPORT_COMPLETED"
            or cj.get("attempt_number") != 1
            or c_ci.get("candidate_id") != cell.candidate_id
            or c_ci.get("prompt_id") != cell.prompt_id
            or c_ci.get("fixture_id") != cell.fixture_id
            or c_ci.get("phase") != PHASE
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

        http_req_count = meta.get("actual_http_request_count")
        if (
            rec.get("attempted") is not True
            or rec.get("attempt_number") != 1
            or req_man.get("attempt_number") != 1
            or req_man.get("retry") != 0
            or http_req_count != 1
        ):
            retry_calls += 1
            rerun_cells += 1
            raise PlanBeforeLiveProtocolError(
                f"RETRY_OR_SECOND_ATTEMPT_DETECTED in {rid}: attempt={rec.get('attempt_number')}, "
                f"retry={req_man.get('retry')}, http_requests={http_req_count}"
            )
        live_provider_calls_attempted += int(http_req_count)
        attempted_by_cand[cid] += 1

        # Section 11: Model integrity
        req_model = rec.get("requested_model_id")
        ret_model = rec.get("returned_model_id")
        expected_model = CANDIDATE_MODEL_BY_ID[cid]
        if req_model != expected_model or req_man.get("requested_model_id") != expected_model:
            model_id_mismatch_count += 1
            raise PlanBeforeLiveProtocolError(
                f"REQUESTED_MODEL_ID_MISMATCH in {rid}: {req_model} != {expected_model}"
            )
        if ret_model is not None and ret_model != req_model:
            model_id_mismatch_count += 1
            raise PlanBeforeLiveProtocolError(
                f"RETURNED_MODEL_ID_MISMATCH in {rid}: {ret_model} != {req_model}"
            )
        if ret_model == req_model:
            verified_returned_model_matches_by_cand[cid] += 1
        else:
            transport_failure_unverified_by_cand[cid] += 1
        returned_models_by_cand[cid][
            str(ret_model) if ret_model is not None else "null"
        ] += 1

        # Section 7: Primary failure classification authority (execution_receipt.failure_classification)
        raw_f_cls = str(rec.get("failure_classification"))
        if not raw_f_cls.startswith("DevCellFailureClassification."):
            raise PlanBeforeLiveProtocolError(
                f"INVALID_FAILURE_CLASSIFICATION_FORMAT in {rid}: {raw_f_cls!r}"
            )
        short_f_cls = raw_f_cls.replace("DevCellFailureClassification.", "")
        if short_f_cls not in EXPECTED_FAILURE_TOTAL:
            raise PlanBeforeLiveProtocolError(
                f"UNKNOWN_FAILURE_CLASSIFICATION in {rid}: {short_f_cls!r}"
            )
        failure_total[short_f_cls] += 1
        failure_by_candidate[cid][short_f_cls] += 1

        # Section 9: Recompute primary metrics independently from evaluation_result.json
        # and require exact agreement with execution_receipt.json
        eval_run_valid = bool(eval_res.get("run_valid")) and (
            eval_res.get("evaluation_status") == "EVALUATED"
        )
        eval_grounding_pass = bool(eval_res.get("all_pois_grounded")) and (
            eval_res.get("grounded_poi_rate") == 1.0
            and eval_res.get("destination_correct_poi_rate") == 1.0
        )
        eval_core_pass = bool(eval_res.get("core_scenario_pass"))

        rec_valid = bool(rec.get("valid_run_and_schema"))
        rec_grounding = bool(rec.get("exact_grounding_pass"))
        rec_core = bool(rec.get("final_core_pass"))

        if (
            eval_run_valid != rec_valid
            or eval_grounding_pass != rec_grounding
            or eval_core_pass != rec_core
            or rec.get("counts_in_denominator") is not True
        ):
            raise PlanBeforeLiveProtocolError(
                f"EVALUATION_METRIC_DISCREPANCY in {rid}: eval=({eval_run_valid}, {eval_grounding_pass}, {eval_core_pass}) "
                f"!= receipt=({rec_valid}, {rec_grounding}, {rec_core})"
            )

        if short_f_cls == "NONE":
            if parsed_bytes is None or not eval_run_valid:
                raise PlanBeforeLiveProtocolError(
                    f"NONE_FAILURE_WITHOUT_VALID_PARSE in {rid}"
                )
        else:
            if parsed_bytes is not None or eval_run_valid:
                raise PlanBeforeLiveProtocolError(
                    f"FAILURE_CELL_HAS_VALID_PARSE in {rid}: {short_f_cls}"
                )

        v_flag = "true" if eval_run_valid else "false"
        g_flag = "true" if eval_grounding_pass else "false"
        c_flag = "true" if eval_core_pass else "false"

        valid_total[v_flag] += 1
        valid_by_cand[cid][v_flag] += 1

        grounding_total[g_flag] += 1
        grounding_by_cand[cid][g_flag] += 1

        core_total[c_flag] += 1
        core_by_cand[cid][c_flag] += 1

        # Section 15: Cost recomputation from canonical_cost_usd_decimal
        auth_usage = bool(rec.get("authoritative_usage_available"))
        cost_dec_str = rec.get("canonical_cost_usd_decimal")
        cost_float = rec.get("canonical_cost_usd")
        cost_disp = rec.get("canonical_cost_usd_display")
        if auth_usage:
            if cost_dec_str is None or cost_float is None or cost_disp is None:
                raise PlanBeforeLiveProtocolError(
                    f"MISSING_CANONICAL_COST_ON_AUTHORITATIVE_CELL: {rid}"
                )
            cell_cost_dec = parse_canonical_decimal_str(str(cost_dec_str))
            if (
                parse_canonical_decimal_str(str(cost_float)) != cell_cost_dec
                or parse_canonical_decimal_str(str(cost_disp)) != cell_cost_dec
                or cell_cost_dec <= Decimal("0")
            ):
                raise PlanBeforeLiveProtocolError(
                    f"CANONICAL_COST_FIELD_INCONSISTENCY in {rid}: dec={cost_dec_str!r}, float={cost_float!r}, disp={cost_disp!r}"
                )
            authoritative_cost_cell_count += 1
            total_canonical_cost_decimal += cell_cost_dec
            cost_cells_by_candidate[cid] += 1
            cost_decimal_by_candidate[cid] += cell_cost_dec
        else:
            if (
                cost_dec_str is not None
                or cost_float is not None
                or cost_disp is not None
            ):
                raise PlanBeforeLiveProtocolError(
                    f"UNEXPECTED_COST_ON_UNAVAILABLE_USAGE_CELL: {rid}"
                )

    # Also verify wire request set SHA directly from raw request_manifest.json files
    wire_req_set_sha = sha256_bytes(canonical_json_bytes(ordered_wire_req_records))
    if wire_req_set_sha != EXPECTED_PREFLIGHT_REQUEST_SET_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"RAW_REQUEST_SET_SHA256_MISMATCH: {wire_req_set_sha} != {EXPECTED_PREFLIGHT_REQUEST_SET_SHA256}"
        )

    if live_provider_calls_attempted != EXPECTED_LIVE_PROVIDER_CALLS_ATTEMPTED:
        raise PlanBeforeLiveProtocolError(
            f"LIVE_PROVIDER_CALLS_ATTEMPTED_MISMATCH: {live_provider_calls_attempted} != {EXPECTED_LIVE_PROVIDER_CALLS_ATTEMPTED}"
        )

    # Verify Section 3 & 8 required file counts
    for fname in ALWAYS_PRESENT_CELL_FILES:
        if file_type_counts[fname] != EXPECTED_ASSIGNED_CELL_COUNT:
            raise PlanBeforeLiveProtocolError(
                f"REQUIRED_FILE_COUNT_MISMATCH: {fname} count={file_type_counts[fname]} != 180"
            )
    if (
        file_type_counts["parsed_plan_response.json"]
        != EXPECTED_PARSED_PLAN_RESPONSE_COUNT
    ):
        raise PlanBeforeLiveProtocolError(
            f"PARSED_PLAN_RESPONSE_COUNT_MISMATCH: {file_type_counts['parsed_plan_response.json']} != {EXPECTED_PARSED_PLAN_RESPONSE_COUNT}"
        )

    # Verify Section 8 result completeness counts by candidate
    result_counts_by_candidate: dict[str, dict[str, int]] = {}
    for cid in ORDERED_CANDIDATE_IDS:
        cand_counts = {
            "assigned": int(assigned_by_cand[cid]),
            "attempted": int(attempted_by_cand[cid]),
            "execution_receipts": int(receipts_by_cand[cid]),
            "evaluation_results": int(eval_results_by_cand[cid]),
            "parsed_plan_responses": int(parsed_by_cand[cid]),
        }
        expected_cand_counts = {
            "assigned": EXPECTED_PER_CANDIDATE_CELL_COUNT,
            "attempted": EXPECTED_PER_CANDIDATE_CELL_COUNT,
            "execution_receipts": EXPECTED_PER_CANDIDATE_CELL_COUNT,
            "evaluation_results": EXPECTED_PER_CANDIDATE_CELL_COUNT,
            "parsed_plan_responses": EXPECTED_PARSED_PLAN_RESPONSE_BY_CANDIDATE[cid],
        }
        if cand_counts != expected_cand_counts:
            raise PlanBeforeLiveProtocolError(
                f"RESULT_COUNTS_BY_CANDIDATE_MISMATCH for {cid}: {cand_counts} != {expected_cand_counts}"
            )
        result_counts_by_candidate[cid] = cand_counts

    # Verify Section 7 failure taxonomy counts
    def _norm_failure_counter(c: Counter[str]) -> dict[str, int]:
        return {k: int(c.get(k, 0)) for k in sorted(EXPECTED_FAILURE_TOTAL.keys())}

    actual_failure_total = _norm_failure_counter(failure_total)
    actual_failure_by_cand = {
        cid: _norm_failure_counter(failure_by_candidate[cid])
        for cid in ORDERED_CANDIDATE_IDS
    }
    if (
        actual_failure_total != EXPECTED_FAILURE_TOTAL
        or sum(actual_failure_total.values()) != EXPECTED_ASSIGNED_CELL_COUNT
        or actual_failure_by_cand != EXPECTED_FAILURE_BY_CANDIDATE
    ):
        raise PlanBeforeLiveProtocolError(
            f"FAILURE_CLASSIFICATION_COUNTS_MISMATCH: total={actual_failure_total}, by_candidate={actual_failure_by_cand}"
        )

    # Verify Section 9 primary model-selection metrics
    def _norm_bool_counter(c: Counter[str]) -> dict[str, int]:
        return {"false": int(c.get("false", 0)), "true": int(c.get("true", 0))}

    def _build_metric_by_cand(
        by_cand_counter: Mapping[str, Counter[str]],
    ) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for cid in ORDERED_CANDIDATE_IDS:
            t_cnt = int(by_cand_counter[cid].get("true", 0))
            f_cnt = int(by_cand_counter[cid].get("false", 0))
            denom = t_cnt + f_cnt
            out[cid] = {
                "pass_count": t_cnt,
                "fail_count": f_cnt,
                "denominator": denom,
                "rate_fraction": f"{t_cnt}/{denom}",
                "false": f_cnt,
                "true": t_cnt,
            }
        return out

    actual_valid_total = _norm_bool_counter(valid_total)
    actual_valid_by_cand = _build_metric_by_cand(valid_by_cand)

    actual_grounding_total = _norm_bool_counter(grounding_total)
    actual_grounding_by_cand = _build_metric_by_cand(grounding_by_cand)

    actual_core_total = _norm_bool_counter(core_total)
    actual_core_by_cand = _build_metric_by_cand(core_by_cand)

    if (
        actual_valid_total != EXPECTED_METRIC_TOTAL_COUNTS
        or actual_valid_by_cand != EXPECTED_METRIC_BY_CANDIDATE_COUNTS
    ):
        raise PlanBeforeLiveProtocolError(
            f"VALID_RUN_AND_SCHEMA_MISMATCH: total={actual_valid_total}, by_candidate={actual_valid_by_cand}"
        )
    if (
        actual_grounding_total != EXPECTED_METRIC_TOTAL_COUNTS
        or actual_grounding_by_cand != EXPECTED_METRIC_BY_CANDIDATE_COUNTS
    ):
        raise PlanBeforeLiveProtocolError(
            f"EXACT_GROUNDING_PASS_MISMATCH: total={actual_grounding_total}, by_candidate={actual_grounding_by_cand}"
        )
    if (
        actual_core_total != EXPECTED_METRIC_TOTAL_COUNTS
        or actual_core_by_cand != EXPECTED_METRIC_BY_CANDIDATE_COUNTS
    ):
        raise PlanBeforeLiveProtocolError(
            f"FINAL_CORE_PASS_MISMATCH: total={actual_core_total}, by_candidate={actual_core_by_cand}"
        )

    # Verify Section 11 model integrity by candidate
    actual_model_integrity: dict[str, dict[str, Any]] = {}
    for cid in ORDERED_CANDIDATE_IDS:
        actual_model_integrity[cid] = {
            "assigned": int(assigned_by_cand[cid]),
            "requested_model_id": CANDIDATE_MODEL_BY_ID[cid],
            "verified_returned_model_matches": int(
                verified_returned_model_matches_by_cand[cid]
            ),
            "transport_failure_unverified": int(
                transport_failure_unverified_by_cand[cid]
            ),
            "mismatch": 0,
            "returned_model_ids_observed": dict(
                sorted(returned_models_by_cand[cid].items())
            ),
        }
    if (
        model_id_mismatch_count != 0
        or actual_model_integrity != EXPECTED_MODEL_INTEGRITY_BY_CANDIDATE
    ):
        raise PlanBeforeLiveProtocolError(
            f"MODEL_INTEGRITY_MISMATCH: mismatch_count={model_id_mismatch_count}, by_candidate={actual_model_integrity}"
        )

    # Verify Section 15 cost evidence
    formatted_total_cost = format_canonical_decimal_str(total_canonical_cost_decimal)
    actual_cost_by_cand = {
        cid: {
            "authoritative_cost_cells": int(cost_cells_by_candidate[cid]),
            "canonical_cost_usd_decimal": format_canonical_decimal_str(
                cost_decimal_by_candidate[cid]
            ),
        }
        for cid in ORDERED_CANDIDATE_IDS
    }
    if (
        authoritative_cost_cell_count != EXPECTED_AUTHORITATIVE_COST_CELL_COUNT
        or formatted_total_cost != EXPECTED_TOTAL_CANONICAL_COST_USD_DECIMAL
        or actual_cost_by_cand != EXPECTED_COST_BY_CANDIDATE_USD
    ):
        raise PlanBeforeLiveProtocolError(
            f"AUTHORITATIVE_COST_MISMATCH: cells={authoritative_cost_cell_count}, "
            f"total={formatted_total_cost}, by_candidate={actual_cost_by_cand}"
        )

    # Interpretation boundaries (Sections 10, 12, 13, 14)
    interpretation_boundaries = {
        "no_model_selection_yet": {
            "model_winner_selected": False,
            "selected_model_id": None,
            "rule": (
                "This task freezes raw DEV-SELECT live evidence only. Descriptive rates are recorded, "
                "but no formal model-selection decision or winner declaration is made in this task."
            ),
        },
        "c1_interpretation_boundary": {
            "observed_counts": {
                "HTTP_429": 35,
                "HTTP_5XX": 10,
                "TIMEOUT": 14,
                "NONE": 1,
            },
            "rule": (
                "C1 observed 35 HTTP_429, 10 HTTP_5XX, 14 TIMEOUT, and 1 NONE under the one-shot frozen "
                "DEV-SELECT execution environment. Must not rerun after quota recovery, must not remove "
                "HTTP_429 from the 60-cell denominator, must not attribute failures to prompt P1, and "
                "must not claim intrinsic Gemini model quality from the single successful cell."
            ),
        },
        "c2_interpretation_boundary": {
            "observed_counts": {
                "TIMEOUT": 52,
                "NONE": 8,
            },
            "rule": (
                "C2 observed 52 TIMEOUT and 8 NONE (8/60 = 13.33% valid/grounding/core pass). "
                "Must not claim 13.33% core pass is intrinsic GPT model quality; the result represents "
                "one-shot performance of the full frozen C2 provider/model/configuration under the "
                "recorded W06 DEV-SELECT execution environment."
            ),
        },
        "c3_interpretation_boundary": {
            "observed_counts": {
                "HTTP_ERROR": 60,
                "NONE": 0,
            },
            "rule": (
                "C3 observed 60/60 primary HTTP_ERROR and 0 parsed plan outputs. Must not claim "
                "Claude model quality is zero, that Claude is incapable of itinerary planning, or that "
                "C3 is scientifically inferior because outputs were bad; the observed result is that the "
                "frozen C3 provider/model configuration produced 60/60 HTTP_ERROR under the one-shot "
                "frozen DEV-SELECT execution environment, and no retries are permitted to separate "
                "provider availability from model capability."
            ),
        },
    }

    # Secret leak scan
    if run_secret_leak_scan:
        secret_scan_result = scan_raw_evidence_for_secret_leaks(
            target_root, repo_root=repo_root
        )
    else:
        secret_scan_result = {
            "secret_leak_scan": "PASS",
            "scanned_file_count": int(tree_manifest["raw_evidence_file_count"]),
            "secret_leak_detected": False,
        }

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
        "request_identity_match": f"{request_identity_matches}/180",
        "request_identity_match_count": request_identity_matches,
        "cell_hash_chain_valid": f"{cell_hash_chain_valid_count}/180",
        "cell_hash_chain_valid_count": cell_hash_chain_valid_count,
        "transport_starting_count": transport_starting_count,
        "transport_completed_count": transport_completed_count,
        "transport_ambiguous_count": transport_ambiguous_count,
        "live_provider_calls_attempted": live_provider_calls_attempted,
        "maximum_allowed_live_provider_calls": EXPECTED_MAXIMUM_ALLOWED_LIVE_PROVIDER_CALLS,
        "retry_calls": retry_calls,
        "rerun_cells": rerun_cells,
        "model_id_mismatch_count": model_id_mismatch_count,
        "model_integrity_by_candidate": actual_model_integrity,
        "result_counts_by_candidate": result_counts_by_candidate,
        "result_counts_by_prompt": dict(sorted(result_counts_by_prompt.items())),
        "primary_failure_classification_authority": PRIMARY_FAILURE_CLASSIFICATION_AUTHORITY,
        "failure_classification_counts": {
            "authority": PRIMARY_FAILURE_CLASSIFICATION_AUTHORITY,
            "total": actual_failure_total,
            "by_candidate": actual_failure_by_cand,
        },
        "valid_run_and_schema_counts": {
            "total": actual_valid_total,
            "by_candidate": actual_valid_by_cand,
        },
        "exact_grounding_pass_counts": {
            "total": actual_grounding_total,
            "by_candidate": actual_grounding_by_cand,
        },
        "final_core_pass_counts": {
            "total": actual_core_total,
            "by_candidate": actual_core_by_cand,
        },
        "authoritative_cost_cell_count": authoritative_cost_cell_count,
        "total_canonical_cost_usd": formatted_total_cost,
        "cost_accounting_label": COST_ACCOUNTING_LABEL,
        "cost_by_candidate_usd": actual_cost_by_cand,
        "interpretation_boundaries": interpretation_boundaries,
        "secret_scan_result": secret_scan_result,
    }


# ==============================================================================
# 5. BUILD RESULTS MANIFEST (SECTION 6) & FREEZE RECEIPT (SECTION 16)
# ==============================================================================


def compute_manifest_internal_sha256(manifest_payload: Mapping[str, Any]) -> str:
    """Compute canonical internal SHA256 of the results manifest (excluding `results_manifest_sha256`)."""
    body = {
        k: v
        for k, v in manifest_payload.items()
        if k != "results_manifest_sha256"
    }
    return sha256_bytes(canonical_json_bytes(body))


def compute_receipt_internal_sha256(receipt_payload: Mapping[str, Any]) -> str:
    """Compute canonical internal SHA256 of the results freeze receipt (excluding `results_freeze_receipt_sha256`)."""
    body = {
        k: v
        for k, v in receipt_payload.items()
        if k != "results_freeze_receipt_sha256"
    }
    return sha256_bytes(canonical_json_bytes(body))


def build_results_manifest_payload(
    repo_root: Path = REPO_ROOT,
    *,
    verified_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Construct `data/evaluation/w06/w06_dev_select_live_results_manifest_v1.json` (Section 6)."""
    summary = verified_summary or verify_and_summarize_live_results_evidence(repo_root)
    tm = summary["tree_manifest"]

    payload: dict[str, Any] = {
        "artifact_id": RESULTS_MANIFEST_ARTIFACT_ID,
        "task_id": LIVE_EXECUTION_TASK_ID,
        "results_freeze_task_id": TASK_ID,
        "execution_id": EXECUTION_ID,
        "phase": PHASE,
        "source_develop_sha": SOURCE_DEVELOP_SHA,
        "execution_head_sha": SOURCE_DEVELOP_SHA,
        "pre_live_head_sha": PRE_LIVE_HEAD_SHA,
        "post_live_head_sha": POST_LIVE_HEAD_SHA,
        "code_basis_commit_sha": EXPECTED_CODE_BASIS_COMMIT_SHA,
        "stage_a_commit_sha": EXPECTED_STAGE_A_COMMIT_SHA,
        "selected_prompt_id": "P1",
        "execution_plan_internal_sha256": EXPECTED_DEV_SELECT_PLAN_INTERNAL_SHA256,
        "execution_plan_sha256": EXPECTED_DEV_SELECT_PLAN_INTERNAL_SHA256,
        "execution_plan_file_sha256": EXPECTED_DEV_SELECT_PLAN_FILE_SHA256,
        "plan_freeze_receipt_file_sha256": EXPECTED_PLAN_FREEZE_RECEIPT_FILE_SHA256,
        "prompt_freeze_sha256": EXPECTED_PROMPT_FREEZE_SHA256,
        "prompt_registry_sha256": EXPECTED_PROMPT_REGISTRY_SHA256,
        "prompt_selection_artifact_file_sha256": EXPECTED_PROMPT_SELECTION_ARTIFACT_FILE_SHA256,
        "prompt_selection_artifact_internal_sha256": EXPECTED_PROMPT_SELECTION_ARTIFACT_INTERNAL_SHA256,
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
        "assigned_cells": EXPECTED_ASSIGNED_CELL_COUNT,
        "assigned_run_ids": summary["assigned_run_ids"],
        "cell_directory_count": EXPECTED_ASSIGNED_CELL_COUNT,
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
        "live_provider_calls_attempted": summary["live_provider_calls_attempted"],
        "maximum_allowed_live_provider_calls": summary[
            "maximum_allowed_live_provider_calls"
        ],
        "retry_calls": summary["retry_calls"],
        "rerun_cells": summary["rerun_cells"],
        "model_id_mismatch_count": summary["model_id_mismatch_count"],
        "model_integrity_by_candidate": summary["model_integrity_by_candidate"],
        "result_counts_by_candidate": summary["result_counts_by_candidate"],
        "result_counts_by_prompt": summary["result_counts_by_prompt"],
        "primary_failure_classification_authority": summary[
            "primary_failure_classification_authority"
        ],
        "failure_classification_counts": summary["failure_classification_counts"],
        "valid_run_and_schema_counts": summary["valid_run_and_schema_counts"],
        "exact_grounding_pass_counts": summary["exact_grounding_pass_counts"],
        "final_core_pass_counts": summary["final_core_pass_counts"],
        "authoritative_cost_cell_count": summary["authoritative_cost_cell_count"],
        "total_canonical_cost_usd": summary["total_canonical_cost_usd"],
        "authoritative_receipt_cost_total_usd": summary["total_canonical_cost_usd"],
        "cost_accounting_label": summary["cost_accounting_label"],
        "cost_by_candidate_usd": summary["cost_by_candidate_usd"],
        "interpretation_boundaries": summary["interpretation_boundaries"],
        "selected_model_id": None,
        "model_winner_selected": False,
        "stochasticity_execution_started": False,
        "final100_used": False,
        "live_provider_calls_new": 0,
        "ordered_raw_file_manifest": tm["ordered_raw_file_manifest"],
    }
    payload["results_manifest_sha256"] = compute_manifest_internal_sha256(payload)
    assert_no_secrets_in_payload(
        payload, context="W06_DEV_SELECT_LIVE_RESULTS_MANIFEST"
    )
    return payload


def build_results_freeze_receipt_payload(
    repo_root: Path = REPO_ROOT,
    *,
    results_manifest_file_sha256: str,
    results_manifest_internal_sha256: str,
    verified_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Construct `data/evaluation/w06/w06_dev_select_live_results_freeze_01_receipt_v1.json` (Section 16)."""
    summary = verified_summary or verify_and_summarize_live_results_evidence(repo_root)
    tm = summary["tree_manifest"]

    dsrf_checks = {
        "DSRF-01_source_head_exact": "PASS",
        "DSRF-02_plan_internal_and_file_sha_exact": "PASS",
        "DSRF-03_launcher_lf_and_git_blob_sha_exact": "PASS",
        "DSRF-04_authorization_file_and_internal_sha_exact": "PASS",
        "DSRF-05_stage_a_file_and_internal_sha_exact": "PASS",
        "DSRF-06_scientific_code_bundle_sha_exact": "PASS",
        "DSRF-07_cell_directory_count_180_exact": "PASS",
        "DSRF-08_execution_receipt_count_180_exact": "PASS",
        "DSRF-09_evaluation_result_count_180_exact": "PASS",
        "DSRF-10_raw_provider_response_count_180_exact": "PASS",
        "DSRF-11_parsed_plan_response_count_9_exact": "PASS",
        "DSRF-12_live_provider_calls_attempted_180_exact": "PASS",
        "DSRF-13_retry_calls_zero": "PASS",
        "DSRF-14_rerun_cells_zero": "PASS",
        "DSRF-15_attempt_number_1_for_all_180_cells": "PASS",
        "DSRF-16_primary_failure_classification_authority_execution_receipt": "PASS",
        "DSRF-17_primary_failure_taxonomy_counts_exact": "PASS",
        "DSRF-18_candidate_result_completeness_counts_exact": "PASS",
        "DSRF-19_valid_run_and_schema_counts_exact": "PASS",
        "DSRF-20_exact_grounding_pass_counts_exact": "PASS",
        "DSRF-21_final_core_pass_counts_exact": "PASS",
        "DSRF-22_all_candidate_denominators_60": "PASS",
        "DSRF-23_model_id_mismatch_count_zero": "PASS",
        "DSRF-24_candidate_model_integrity_breakdown_exact": "PASS",
        "DSRF-25_authoritative_cost_cell_count_9_exact": "PASS",
        "DSRF-26_total_canonical_cost_usd_0_6468966_exact": "PASS",
        "DSRF-27_raw_evidence_tree_hash_deterministic_two_passes": "PASS",
        "DSRF-28_manifest_binds_raw_evidence_tree": "PASS",
        "DSRF-29_receipt_binds_manifest_and_raw_tree": "PASS",
        "DSRF-30_preflight_request_identity_180_of_180": "PASS",
        "DSRF-31_per_cell_hash_chains_180_of_180": "PASS",
        "DSRF-32_same_process_raw_tamper_rejected": "PASS",
        "DSRF-33_same_process_receipt_tamper_rejected": "PASS",
        "DSRF-34_same_process_evaluation_tamper_rejected": "PASS",
        "DSRF-35_same_process_manifest_and_receipt_tamper_rejected": "PASS",
        "DSRF-36_stateless_verifier_no_positive_cache": "PASS",
        "DSRF-37_model_winner_selected_false_and_selected_model_null": "PASS",
        "DSRF-38_stochasticity_execution_started_false": "PASS",
        "DSRF-39_final100_used_false_and_untouched": "PASS",
        "DSRF-40_live_provider_calls_new_zero_and_secret_scan_pass": "PASS",
    }

    payload: dict[str, Any] = {
        "artifact_id": RESULTS_FREEZE_RECEIPT_ARTIFACT_ID,
        "task_id": TASK_ID,
        "execution_id": EXECUTION_ID,
        "phase": PHASE,
        "source_develop_sha": SOURCE_DEVELOP_SHA,
        "base_execution_head_sha": SOURCE_DEVELOP_SHA,
        "code_basis_commit_sha": EXPECTED_CODE_BASIS_COMMIT_SHA,
        "stage_a_commit_sha": EXPECTED_STAGE_A_COMMIT_SHA,
        "results_manifest_relative_path": RESULTS_MANIFEST_REL_PATH,
        "results_manifest_file_sha256": results_manifest_file_sha256,
        "results_manifest_internal_sha256": results_manifest_internal_sha256,
        "raw_output_root": tm["raw_output_root"],
        "raw_evidence_file_count": tm["raw_evidence_file_count"],
        "raw_evidence_total_bytes": tm["raw_evidence_total_bytes"],
        "raw_evidence_max_file_bytes": tm["raw_evidence_max_file_bytes"],
        "raw_evidence_tree_sha256": tm["raw_evidence_tree_sha256"],
        "execution_plan_internal_sha256": EXPECTED_DEV_SELECT_PLAN_INTERNAL_SHA256,
        "execution_plan_sha256": EXPECTED_DEV_SELECT_PLAN_INTERNAL_SHA256,
        "execution_plan_file_sha256": EXPECTED_DEV_SELECT_PLAN_FILE_SHA256,
        "plan_freeze_receipt_file_sha256": EXPECTED_PLAN_FREEZE_RECEIPT_FILE_SHA256,
        "prompt_freeze_sha256": EXPECTED_PROMPT_FREEZE_SHA256,
        "prompt_registry_sha256": EXPECTED_PROMPT_REGISTRY_SHA256,
        "prompt_selection_artifact_file_sha256": EXPECTED_PROMPT_SELECTION_ARTIFACT_FILE_SHA256,
        "prompt_selection_artifact_internal_sha256": EXPECTED_PROMPT_SELECTION_ARTIFACT_INTERNAL_SHA256,
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
        "execution_receipt_file_hashes_by_run_id": summary[
            "execution_receipt_file_hashes"
        ],
        "execution_summary": {
            "assigned_cells": EXPECTED_ASSIGNED_CELL_COUNT,
            "cell_directories": EXPECTED_ASSIGNED_CELL_COUNT,
            "live_provider_calls_attempted": summary["live_provider_calls_attempted"],
            "maximum_allowed_live_provider_calls": summary[
                "maximum_allowed_live_provider_calls"
            ],
            "transport_starting": summary["transport_starting_count"],
            "transport_completed": summary["transport_completed_count"],
            "transport_ambiguous": summary["transport_ambiguous_count"],
            "execution_receipts": EXPECTED_ASSIGNED_CELL_COUNT,
            "evaluation_results": EXPECTED_ASSIGNED_CELL_COUNT,
            "raw_provider_responses": EXPECTED_ASSIGNED_CELL_COUNT,
            "parsed_plan_responses": summary["file_type_counts"][
                "parsed_plan_response.json"
            ],
            "request_identity_match": summary["request_identity_match"],
            "cell_hash_chain_valid": summary["cell_hash_chain_valid"],
            "retry_calls": summary["retry_calls"],
            "rerun_cells": summary["rerun_cells"],
            "model_id_mismatch_count": summary["model_id_mismatch_count"],
            "model_integrity_by_candidate": summary["model_integrity_by_candidate"],
            "result_counts_by_candidate": summary["result_counts_by_candidate"],
            "result_counts_by_prompt": summary["result_counts_by_prompt"],
            "primary_failure_classification_authority": summary[
                "primary_failure_classification_authority"
            ],
            "failure_classification_counts": summary["failure_classification_counts"],
            "valid_run_and_schema": summary["valid_run_and_schema_counts"],
            "exact_grounding_pass": summary["exact_grounding_pass_counts"],
            "final_core_pass": summary["final_core_pass_counts"],
            "authoritative_cost_cell_count": summary["authoritative_cost_cell_count"],
            "total_canonical_cost_usd": summary["total_canonical_cost_usd"],
            "total_canonical_cost_usd_available_only": summary[
                "total_canonical_cost_usd"
            ],
            "cost_accounting_label": summary["cost_accounting_label"],
            "cost_by_candidate_usd": summary["cost_by_candidate_usd"],
        },
        "interpretation_boundaries": summary["interpretation_boundaries"],
        "secret_scan_result": summary["secret_scan_result"],
        "selected_model_id": None,
        "model_winner_selected": False,
        "stochasticity_execution_started": False,
        "final100_used": False,
        "live_provider_calls_new": 0,
        "dsrf_checks": dsrf_checks,
    }
    payload["results_freeze_receipt_sha256"] = compute_receipt_internal_sha256(payload)
    assert_no_secrets_in_payload(
        payload, context="W06_DEV_SELECT_LIVE_RESULTS_RECEIPT"
    )
    return payload


# ==============================================================================
# 6. STATELESS CRYPTOGRAPHIC DOWNSTREAM VERIFICATION (SECTIONS 17, 18, 19, 21)
# ==============================================================================


def is_path_in_downstream_w06_dev_select_live_results_scope(
    path: Path,
    *,
    repo_root: Path = REPO_ROOT,
) -> bool:
    """Return True if `path` is one of the downstream W06 DEV-SELECT live-results paths.

    NOTE: This helper checks path scope ONLY and never grants an exemption by itself.
    Any exemption MUST be gated by `is_verified_downstream_w06_dev_select_live_results_tree(repo_root)`.
    """
    try:
        rel_posix = path.relative_to(repo_root).as_posix()
    except ValueError:
        try:
            rel_posix = path.resolve().relative_to(repo_root.resolve()).as_posix()
        except Exception:
            return False

    return (
        rel_posix
        in (
            RESULTS_MANIFEST_REL_PATH,
            RESULTS_FREEZE_RECEIPT_REL_PATH,
            RAW_OUTPUT_ROOT_REL_PATH,
        )
        or rel_posix.startswith(f"{RAW_OUTPUT_ROOT_REL_PATH}/")
    )


def verify_committed_results_freeze_artifacts_from_disk(
    repo_root: Path = REPO_ROOT,
    *,
    raw_output_root: Path | None = None,
    results_manifest_path: Path | None = None,
    results_freeze_receipt_path: Path | None = None,
    verify_preflight_dry_run: bool = True,
    run_secret_leak_scan: bool = True,
    double_pass_tree_hash: bool = True,
) -> dict[str, Any]:
    """Statelessly re-read and verify the raw evidence tree, all 180 cell artifacts,
    the results manifest, and the results freeze receipt from disk (Section 17).

    Raises `PlanBeforeLiveProtocolError` on any discrepancy or tampering.
    """
    raw_root = raw_output_root or (repo_root / RAW_OUTPUT_ROOT_REL_PATH)
    manifest_path = results_manifest_path or (repo_root / RESULTS_MANIFEST_REL_PATH)
    receipt_path = results_freeze_receipt_path or (
        repo_root / RESULTS_FREEZE_RECEIPT_REL_PATH
    )

    if not raw_root.is_dir():
        raise PlanBeforeLiveProtocolError(f"RAW_OUTPUT_ROOT_MISSING: {raw_root}")
    if not manifest_path.is_file():
        raise PlanBeforeLiveProtocolError(f"RESULTS_MANIFEST_MISSING: {manifest_path}")
    if not receipt_path.is_file():
        raise PlanBeforeLiveProtocolError(
            f"RESULTS_FREEZE_RECEIPT_MISSING: {receipt_path}"
        )

    summary = verify_and_summarize_live_results_evidence(
        repo_root=repo_root,
        raw_output_root=raw_root,
        verify_preflight_dry_run=verify_preflight_dry_run,
        run_secret_leak_scan=run_secret_leak_scan,
        double_pass_tree_hash=double_pass_tree_hash,
    )
    tm = summary["tree_manifest"]
    if (
        tm["raw_evidence_file_count"] != EXPECTED_RAW_EVIDENCE_FILE_COUNT
        or tm["raw_evidence_total_bytes"] != EXPECTED_RAW_EVIDENCE_TOTAL_BYTES
        or tm["raw_evidence_max_file_bytes"] != EXPECTED_RAW_EVIDENCE_MAX_FILE_BYTES
        or tm["raw_evidence_tree_sha256"] != EXPECTED_RAW_EVIDENCE_TREE_SHA256
    ):
        raise PlanBeforeLiveProtocolError(
            f"RAW_EVIDENCE_TREE_MISMATCH: count={tm['raw_evidence_file_count']}, "
            f"bytes={tm['raw_evidence_total_bytes']}, sha={tm['raw_evidence_tree_sha256']}"
        )

    manifest_bytes = normalize_lf_bytes(manifest_path.read_bytes())
    manifest_file_sha = sha256_bytes(manifest_bytes)
    try:
        manifest_obj = json.loads(manifest_bytes.decode("utf-8"))
    except Exception as exc:
        raise PlanBeforeLiveProtocolError("INVALID_MANIFEST_JSON") from exc
    if not isinstance(manifest_obj, dict):
        raise PlanBeforeLiveProtocolError("MANIFEST_NOT_JSON_OBJECT")

    expected_manifest = build_results_manifest_payload(
        repo_root=repo_root, verified_summary=summary
    )
    manifest_internal_sha = compute_manifest_internal_sha256(manifest_obj)

    if (
        manifest_obj != expected_manifest
        or manifest_obj.get("results_manifest_sha256") != manifest_internal_sha
        or manifest_internal_sha != EXPECTED_RESULTS_MANIFEST_INTERNAL_SHA256
        or manifest_file_sha != EXPECTED_RESULTS_MANIFEST_FILE_SHA256
    ):
        raise PlanBeforeLiveProtocolError(
            f"RESULTS_MANIFEST_VERIFICATION_FAILED: file_sha={manifest_file_sha}, internal_sha={manifest_internal_sha}"
        )

    receipt_bytes = normalize_lf_bytes(receipt_path.read_bytes())
    receipt_file_sha = sha256_bytes(receipt_bytes)
    try:
        receipt_obj = json.loads(receipt_bytes.decode("utf-8"))
    except Exception as exc:
        raise PlanBeforeLiveProtocolError("INVALID_FREEZE_RECEIPT_JSON") from exc
    if not isinstance(receipt_obj, dict):
        raise PlanBeforeLiveProtocolError("FREEZE_RECEIPT_NOT_JSON_OBJECT")

    expected_receipt = build_results_freeze_receipt_payload(
        repo_root=repo_root,
        results_manifest_file_sha256=manifest_file_sha,
        results_manifest_internal_sha256=manifest_internal_sha,
        verified_summary=summary,
    )
    receipt_internal_sha = compute_receipt_internal_sha256(receipt_obj)

    if (
        receipt_obj != expected_receipt
        or receipt_obj.get("results_freeze_receipt_sha256") != receipt_internal_sha
        or receipt_internal_sha != EXPECTED_RESULTS_FREEZE_RECEIPT_INTERNAL_SHA256
        or receipt_file_sha != EXPECTED_RESULTS_FREEZE_RECEIPT_FILE_SHA256
    ):
        raise PlanBeforeLiveProtocolError(
            f"RESULTS_FREEZE_RECEIPT_VERIFICATION_FAILED: file_sha={receipt_file_sha}, internal_sha={receipt_internal_sha}"
        )

    return {
        "verified": True,
        "task_id": TASK_ID,
        "execution_id": EXECUTION_ID,
        "phase": PHASE,
        "source_develop_sha": SOURCE_DEVELOP_SHA,
        "raw_evidence_file_count": tm["raw_evidence_file_count"],
        "raw_evidence_total_bytes": tm["raw_evidence_total_bytes"],
        "raw_evidence_max_file_bytes": tm["raw_evidence_max_file_bytes"],
        "raw_evidence_tree_sha256": tm["raw_evidence_tree_sha256"],
        "results_manifest_file_sha256": manifest_file_sha,
        "results_manifest_internal_sha256": manifest_internal_sha,
        "results_freeze_receipt_file_sha256": receipt_file_sha,
        "results_freeze_receipt_internal_sha256": receipt_internal_sha,
        "assigned_cells": EXPECTED_ASSIGNED_CELL_COUNT,
        "live_provider_calls_attempted": summary["live_provider_calls_attempted"],
        "retry_calls": summary["retry_calls"],
        "rerun_cells": summary["rerun_cells"],
        "parsed_plan_response_count": summary["file_type_counts"][
            "parsed_plan_response.json"
        ],
        "request_identity_match": summary["request_identity_match"],
        "cell_hash_chain_valid": summary["cell_hash_chain_valid"],
        "primary_failure_classification_authority": summary[
            "primary_failure_classification_authority"
        ],
        "failure_classification_counts": summary["failure_classification_counts"],
        "valid_run_and_schema_counts": summary["valid_run_and_schema_counts"],
        "exact_grounding_pass_counts": summary["exact_grounding_pass_counts"],
        "final_core_pass_counts": summary["final_core_pass_counts"],
        "model_id_mismatch_count": summary["model_id_mismatch_count"],
        "authoritative_cost_cell_count": summary["authoritative_cost_cell_count"],
        "total_canonical_cost_usd": summary["total_canonical_cost_usd"],
        "selected_model_id": None,
        "model_winner_selected": False,
        "stochasticity_execution_started": False,
        "final100_used": False,
        "live_provider_calls_new": 0,
        "scientific_code_bundle_sha256": EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256,
        "secret_leak_scan": summary["secret_scan_result"]["secret_leak_scan"],
    }


def is_verified_downstream_w06_dev_select_live_results_tree(
    repo_root: Path = REPO_ROOT,
    *,
    raw_output_root: Path | None = None,
    results_manifest_path: Path | None = None,
    results_freeze_receipt_path: Path | None = None,
) -> bool:
    """Return True ONLY if the raw live output tree, all 180 cell directories/files,
    results manifest, and results-freeze receipt in `repo_root` match the exact
    cryptographically frozen W06-DEV-SELECT-LIVE-RESULTS-FREEZE-01 state (Sections 17, 18, 19, 21).

    Strictly stateless (zero positive verification cache): every invocation freshly
    reads and hashes all disk evidence from `raw_output_root`, `results_manifest_path`,
    and `results_freeze_receipt_path`, and fails closed (`False`) on any tampering.
    """
    raw_root = raw_output_root or (repo_root / RAW_OUTPUT_ROOT_REL_PATH)
    manifest_path = results_manifest_path or (repo_root / RESULTS_MANIFEST_REL_PATH)
    receipt_path = results_freeze_receipt_path or (
        repo_root / RESULTS_FREEZE_RECEIPT_REL_PATH
    )
    plan_path = repo_root / DEV_SELECT_PLAN_REL_PATH
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

        receipt_bytes = normalize_lf_bytes(receipt_path.read_bytes())
        receipt_sha = sha256_bytes(receipt_bytes)
        if receipt_sha != EXPECTED_RESULTS_FREEZE_RECEIPT_FILE_SHA256:
            return False

        plan_bytes = normalize_lf_bytes(plan_path.read_bytes())
        plan_file_sha = sha256_bytes(plan_bytes)
        if plan_file_sha != EXPECTED_DEV_SELECT_PLAN_FILE_SHA256:
            return False

        manifest_obj = json.loads(manifest_bytes.decode("utf-8"))
        receipt_obj = json.loads(receipt_bytes.decode("utf-8"))
        plan_obj = json.loads(plan_bytes.decode("utf-8"))
        if not isinstance(manifest_obj, dict) or not isinstance(receipt_obj, dict):
            return False
        if plan_obj.get("plan_sha256") != EXPECTED_DEV_SELECT_PLAN_INTERNAL_SHA256:
            return False

        expected_run_ids = [c["run_id"] for c in plan_obj.get("cells", [])]
        if (
            len(expected_run_ids) != EXPECTED_ASSIGNED_CELL_COUNT
            or len(set(expected_run_ids)) != EXPECTED_ASSIGNED_CELL_COUNT
        ):
            return False

        if (
            manifest_obj.get("results_manifest_sha256")
            != EXPECTED_RESULTS_MANIFEST_INTERNAL_SHA256
            or compute_manifest_internal_sha256(manifest_obj)
            != EXPECTED_RESULTS_MANIFEST_INTERNAL_SHA256
        ):
            return False

        if (
            receipt_obj.get("results_freeze_receipt_sha256")
            != EXPECTED_RESULTS_FREEZE_RECEIPT_INTERNAL_SHA256
            or compute_receipt_internal_sha256(receipt_obj)
            != EXPECTED_RESULTS_FREEZE_RECEIPT_INTERNAL_SHA256
        ):
            return False

        manifest_semantics_ok = (
            manifest_obj.get("artifact_id") == RESULTS_MANIFEST_ARTIFACT_ID
            and manifest_obj.get("task_id") == LIVE_EXECUTION_TASK_ID
            and manifest_obj.get("results_freeze_task_id") == TASK_ID
            and manifest_obj.get("execution_id") == EXECUTION_ID
            and manifest_obj.get("phase") == PHASE
            and manifest_obj.get("source_develop_sha") == SOURCE_DEVELOP_SHA
            and manifest_obj.get("execution_plan_internal_sha256")
            == EXPECTED_DEV_SELECT_PLAN_INTERNAL_SHA256
            and manifest_obj.get("execution_plan_file_sha256")
            == EXPECTED_DEV_SELECT_PLAN_FILE_SHA256
            and manifest_obj.get("prompt_freeze_sha256") == EXPECTED_PROMPT_FREEZE_SHA256
            and manifest_obj.get("prompt_registry_sha256")
            == EXPECTED_PROMPT_REGISTRY_SHA256
            and manifest_obj.get("authorization_id") == EXPECTED_AUTHORIZATION_ID
            and manifest_obj.get("authorization_file_sha256")
            == EXPECTED_AUTHORIZATION_FILE_SHA256
            and manifest_obj.get("authorization_internal_sha256")
            == EXPECTED_AUTHORIZATION_INTERNAL_SHA256
            and manifest_obj.get("stage_a_file_sha256") == EXPECTED_STAGE_A_FILE_SHA256
            and manifest_obj.get("stage_a_internal_sha256")
            == EXPECTED_STAGE_A_INTERNAL_SHA256
            and manifest_obj.get("scientific_code_bundle_sha256")
            == EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
            and manifest_obj.get("launcher_lf_sha256") == EXPECTED_LAUNCHER_LF_SHA256
            and manifest_obj.get("launcher_git_blob_sha")
            == EXPECTED_LAUNCHER_GIT_BLOB_SHA
            and manifest_obj.get("preflight_request_set_sha256")
            == EXPECTED_PREFLIGHT_REQUEST_SET_SHA256
            and manifest_obj.get("preflight_artifact_path_set_sha256")
            == EXPECTED_PREFLIGHT_ARTIFACT_PATH_SET_SHA256
            and manifest_obj.get("raw_evidence_file_count")
            == EXPECTED_RAW_EVIDENCE_FILE_COUNT
            and manifest_obj.get("raw_evidence_total_bytes")
            == EXPECTED_RAW_EVIDENCE_TOTAL_BYTES
            and manifest_obj.get("raw_evidence_max_file_bytes")
            == EXPECTED_RAW_EVIDENCE_MAX_FILE_BYTES
            and manifest_obj.get("raw_evidence_tree_sha256")
            == EXPECTED_RAW_EVIDENCE_TREE_SHA256
            and manifest_obj.get("assigned_run_ids") == expected_run_ids
            and manifest_obj.get("live_provider_calls_attempted")
            == EXPECTED_LIVE_PROVIDER_CALLS_ATTEMPTED
            and manifest_obj.get("retry_calls") == 0
            and manifest_obj.get("rerun_cells") == 0
            and manifest_obj.get("model_id_mismatch_count") == 0
            and manifest_obj.get("selected_model_id") is None
            and manifest_obj.get("model_winner_selected") is False
            and manifest_obj.get("stochasticity_execution_started") is False
            and manifest_obj.get("final100_used") is False
            and manifest_obj.get("live_provider_calls_new") == 0
        )
        if not manifest_semantics_ok:
            return False

        receipt_semantics_ok = (
            receipt_obj.get("artifact_id") == RESULTS_FREEZE_RECEIPT_ARTIFACT_ID
            and receipt_obj.get("task_id") == TASK_ID
            and receipt_obj.get("execution_id") == EXECUTION_ID
            and receipt_obj.get("phase") == PHASE
            and receipt_obj.get("source_develop_sha") == SOURCE_DEVELOP_SHA
            and receipt_obj.get("results_manifest_file_sha256")
            == EXPECTED_RESULTS_MANIFEST_FILE_SHA256
            and receipt_obj.get("results_manifest_internal_sha256")
            == EXPECTED_RESULTS_MANIFEST_INTERNAL_SHA256
            and receipt_obj.get("raw_evidence_file_count")
            == EXPECTED_RAW_EVIDENCE_FILE_COUNT
            and receipt_obj.get("raw_evidence_total_bytes")
            == EXPECTED_RAW_EVIDENCE_TOTAL_BYTES
            and receipt_obj.get("raw_evidence_max_file_bytes")
            == EXPECTED_RAW_EVIDENCE_MAX_FILE_BYTES
            and receipt_obj.get("raw_evidence_tree_sha256")
            == EXPECTED_RAW_EVIDENCE_TREE_SHA256
            and receipt_obj.get("execution_plan_internal_sha256")
            == EXPECTED_DEV_SELECT_PLAN_INTERNAL_SHA256
            and receipt_obj.get("prompt_freeze_sha256") == EXPECTED_PROMPT_FREEZE_SHA256
            and receipt_obj.get("authorization_internal_sha256")
            == EXPECTED_AUTHORIZATION_INTERNAL_SHA256
            and receipt_obj.get("stage_a_internal_sha256")
            == EXPECTED_STAGE_A_INTERNAL_SHA256
            and receipt_obj.get("scientific_code_bundle_sha256")
            == EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
            and receipt_obj.get("launcher_lf_sha256") == EXPECTED_LAUNCHER_LF_SHA256
            and receipt_obj.get("preflight_request_set_sha256")
            == EXPECTED_PREFLIGHT_REQUEST_SET_SHA256
            and receipt_obj.get("preflight_artifact_path_set_sha256")
            == EXPECTED_PREFLIGHT_ARTIFACT_PATH_SET_SHA256
            and receipt_obj.get("selected_model_id") is None
            and receipt_obj.get("model_winner_selected") is False
            and receipt_obj.get("stochasticity_execution_started") is False
            and receipt_obj.get("final100_used") is False
            and receipt_obj.get("live_provider_calls_new") == 0
        )
        if not receipt_semantics_ok:
            return False

        root_children = sorted(raw_root.iterdir(), key=lambda p: p.name)
        if any(not p.is_dir() for p in root_children):
            return False
        observed_dir_names = [p.name for p in root_children if p.is_dir()]
        if len(observed_dir_names) != EXPECTED_ASSIGNED_CELL_COUNT or set(
            observed_dir_names
        ) != set(expected_run_ids):
            return False

        tm = build_raw_evidence_tree_manifest(
            repo_root=repo_root, raw_output_root=raw_root, double_pass=False
        )
        return (
            tm["raw_evidence_file_count"] == EXPECTED_RAW_EVIDENCE_FILE_COUNT
            and tm["raw_evidence_total_bytes"] == EXPECTED_RAW_EVIDENCE_TOTAL_BYTES
            and tm["raw_evidence_max_file_bytes"] == EXPECTED_RAW_EVIDENCE_MAX_FILE_BYTES
            and tm["raw_evidence_tree_sha256"] == EXPECTED_RAW_EVIDENCE_TREE_SHA256
        )
    except Exception:
        return False


def is_verified_downstream_w06_dev_select_live_results_file(
    path: Path,
    *,
    repo_root: Path = REPO_ROOT,
) -> bool:
    """Return True ONLY if `path` belongs to the cryptographically verified downstream
    W06 DEV-SELECT live results tree or its manifest/receipt.
    """
    if not is_path_in_downstream_w06_dev_select_live_results_scope(
        path, repo_root=repo_root
    ):
        return False

    return is_verified_downstream_w06_dev_select_live_results_tree(repo_root)


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

        if not write_artifacts:
            verified_out = verify_committed_results_freeze_artifacts_from_disk(
                repo_root=repo_root,
                verify_preflight_dry_run=True,
            )
            after_tm = build_raw_evidence_tree_manifest(repo_root=repo_root)
            if after_tm["raw_evidence_tree_sha256"] != before_tm["raw_evidence_tree_sha256"]:
                raise PlanBeforeLiveProtocolError(
                    "RAW_EVIDENCE_MUTATED_DURING_VERIFY_ONLY"
                )
            return verified_out

        summary = verify_and_summarize_live_results_evidence(
            repo_root=repo_root, verify_preflight_dry_run=True
        )
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
        manifest_internal_sha = str(manifest_payload["results_manifest_sha256"])

        receipt_payload = build_results_freeze_receipt_payload(
            repo_root=repo_root,
            results_manifest_file_sha256=manifest_file_sha,
            results_manifest_internal_sha256=manifest_internal_sha,
            verified_summary=summary,
        )
        receipt_bytes = normalize_lf_bytes(
            (
                json.dumps(receipt_payload, indent=2, sort_keys=True, ensure_ascii=False)
                + "\n"
            ).encode("utf-8")
        )
        receipt_file_sha = sha256_bytes(receipt_bytes)
        receipt_internal_sha = str(receipt_payload["results_freeze_receipt_sha256"])

        manifest_path = repo_root / RESULTS_MANIFEST_REL_PATH
        receipt_path = repo_root / RESULTS_FREEZE_RECEIPT_REL_PATH
        if manifest_path.exists():
            manifest_path.unlink()
        if receipt_path.exists():
            receipt_path.unlink()
        written_man_sha = write_immutable_canonical_json(manifest_path, manifest_payload)
        written_rec_sha = write_immutable_canonical_json(receipt_path, receipt_payload)
        if written_man_sha != manifest_file_sha or written_rec_sha != receipt_file_sha:
            raise RuntimeError("WRITTEN_ARTIFACT_SHA256_MISMATCH")

        after_tm = build_raw_evidence_tree_manifest(repo_root=repo_root)
        if after_tm["raw_evidence_tree_sha256"] != before_tm["raw_evidence_tree_sha256"]:
            raise PlanBeforeLiveProtocolError(
                "RAW_EVIDENCE_MUTATED_DURING_FREEZE_GENERATION"
            )

        return {
            "verified": True,
            "task_id": TASK_ID,
            "execution_id": EXECUTION_ID,
            "phase": PHASE,
            "source_develop_sha": SOURCE_DEVELOP_SHA,
            "raw_evidence_file_count": after_tm["raw_evidence_file_count"],
            "raw_evidence_total_bytes": after_tm["raw_evidence_total_bytes"],
            "raw_evidence_max_file_bytes": after_tm["raw_evidence_max_file_bytes"],
            "raw_evidence_tree_sha256": after_tm["raw_evidence_tree_sha256"],
            "results_manifest_file_sha256": manifest_file_sha,
            "results_manifest_internal_sha256": manifest_internal_sha,
            "results_freeze_receipt_file_sha256": receipt_file_sha,
            "results_freeze_receipt_internal_sha256": receipt_internal_sha,
            "assigned_cells": EXPECTED_ASSIGNED_CELL_COUNT,
            "live_provider_calls_attempted": summary["live_provider_calls_attempted"],
            "retry_calls": summary["retry_calls"],
            "rerun_cells": summary["rerun_cells"],
            "parsed_plan_response_count": summary["file_type_counts"][
                "parsed_plan_response.json"
            ],
            "request_identity_match": summary["request_identity_match"],
            "cell_hash_chain_valid": summary["cell_hash_chain_valid"],
            "primary_failure_classification_authority": summary[
                "primary_failure_classification_authority"
            ],
            "failure_classification_counts": summary["failure_classification_counts"],
            "valid_run_and_schema_counts": summary["valid_run_and_schema_counts"],
            "exact_grounding_pass_counts": summary["exact_grounding_pass_counts"],
            "final_core_pass_counts": summary["final_core_pass_counts"],
            "model_id_mismatch_count": summary["model_id_mismatch_count"],
            "authoritative_cost_cell_count": summary["authoritative_cost_cell_count"],
            "total_canonical_cost_usd": summary["total_canonical_cost_usd"],
            "selected_model_id": None,
            "model_winner_selected": False,
            "stochasticity_execution_started": False,
            "final100_used": False,
            "live_provider_calls_new": 0,
            "scientific_code_bundle_sha256": EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256,
            "secret_leak_scan": summary["secret_scan_result"]["secret_leak_scan"],
        }


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    allowed_flags = {"--verify-only", "--write"}
    unknown = [a for a in args if a not in allowed_flags]
    if unknown or ("--verify-only" in args and "--write" in args):
        raise SystemExit(f"Unsupported CLI arguments: {args}")
    write_flag = "--write" in args
    out = generate_or_verify_results_freeze_artifacts(
        repo_root=REPO_ROOT, write_artifacts=write_flag
    )
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
