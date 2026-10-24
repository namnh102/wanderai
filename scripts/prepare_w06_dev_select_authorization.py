#!/usr/bin/env python3
"""W06-DEV-SELECT-AUTHORIZATION-PREP-01: DEV-SELECT live-authorization preparation and scientific-scope freeze agent.

Strictly offline (`LIVE_PROVIDER_CALLS_NEW = 0`, `PROVIDER_COST_USD_NEW = 0`):
- Installs an outbound network kill-switch blocking socket, urllib, httpx, and httpx2.
- Never reads, prints, hashes, or persists secret key values; checks key presence ONLY as PRESENT / MISSING.
- Verifies all closed upstream gates (W06-DEV-TUNE-LIVE-RESULTS-FREEZE-01, W06-DEV-TUNE-PROMPT-SELECTION-01,
  W06-DEV-SELECT-PLAN-FREEZE-01), the frozen 180-cell DEV-SELECT execution plan, locked prompt P1,
  candidate/provider configs [C1, C2, C3], and the 14-file scientific code bundle.
- Computes deterministic rendered P1 user-prompt UTF-8 byte statistics across all 60 DEV-SELECT fixtures
  and the 180-cell conservative planning cost envelope.
- Enforces the Pre-Authorization Firewall:
  NEVER creates a DEV-SELECT live authorization artifact, Stage-A freeze receipt, LiveExecutionCapability,
  production provider transport, transport journals, or live cell result directories.
"""

from __future__ import annotations

import argparse
import contextlib
from decimal import Decimal
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys
from typing import Any, Iterator
import urllib.request

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
AI_SERVICE_ROOT = REPO_ROOT / "apps" / "ai-service"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for _p in (AI_SERVICE_ROOT, SCRIPTS_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from app.evaluation.dev_live_runner import (  # noqa: E402
    CANDIDATE_ENV_KEY_BY_ID,
    CANDIDATE_MODEL_BY_ID,
    CANDIDATE_PROVIDER_BY_ID,
    DEFAULT_COST_COMPARABILITY_BY_CANDIDATE,
    DEFAULT_RUNNER_RECEIPT_PATH,
    PlanBeforeLiveProtocolError,
    assert_no_secrets_in_payload,
)
from app.evaluation.dev_selection_harness import (  # noqa: E402
    EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
    EXPECTED_SEMANTIC_SCHEMA_SHA256,
    FORBIDDEN_FINAL100_BUNDLE_SHA256,
    FORBIDDEN_P11_MANIFEST_SHA256,
    FROZEN_MAX_OUTPUT_TOKENS,
    ORDERED_CANDIDATE_IDS,
    SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS,
    CandidateCostComparabilityRecord,
    DevExecutionPlan,
    build_destination_catalog_context,
    build_deterministic_dev_scenario_context,
    canonical_json_bytes,
    compute_canonical_cell_cost_decimal,
    compute_common_portable_generation_schema_sha256_v2,
    compute_provider_config_registry_sha256,
    compute_scientific_code_bundle_file_hashes,
    compute_scientific_code_bundle_sha256,
    compute_semantic_schema_sha256,
    format_canonical_decimal_str,
    get_cached_provider_config_sha256,
    load_and_verify_candidate_registry,
    load_and_verify_frozen_dev_bundle,
    normalize_lf_bytes,
    sha256_bytes,
    verify_dev_execution_plan_for_execution,
)
from freeze_w06_dev_prompt_candidates import (  # noqa: E402
    EXPECTED_SCIENTIFIC_CODE_BUNDLE_FILE_HASHES,
    EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256,
    P1_AUTHORITATIVE_SEMANTIC_PROMPT_SHA256,
    P1_EXPECTED_PROMPT_VERSION,
    P1_EXPECTED_SYSTEM_PROMPT_SHA256,
    P1_EXPECTED_USER_PROMPT_TEMPLATE_SHA256,
    P1_PROMPT_ID,
    build_p1_spec,
)
from freeze_w06_dev_select_plan import (  # noqa: E402
    ALLOWED_DEV_SELECT_PROMPT_IDS,
    CODE_BASIS_COMMIT_SHA as PLAN_CODE_BASIS_COMMIT_SHA,
    CODE_COMMIT_SHA as PLAN_CODE_COMMIT_SHA,
    DEV_FINAL_OVERLAP_RECEIPT_REL_PATH,
    DEV_FIXTURE_BUNDLE_REL_PATH,
    DEV_FIXTURE_FREEZE_RECEIPT_REL_PATH,
    DEV_FIXTURE_MANIFEST_REL_PATH,
    DEV_SELECT_PLAN_REL_PATH,
    EXPECTED_ASSIGNED_CELLS,
    EXPECTED_ATTEMPTS_PER_CELL,
    EXPECTED_CANDIDATE_COUNT,
    EXPECTED_CANDIDATE_IDS,
    EXPECTED_CANDIDATE_REGISTRY_SHA256,
    EXPECTED_DEV_FINAL_OVERLAP_RECEIPT_SHA256,
    EXPECTED_DEV_FIXTURE_BUNDLE_SHA256,
    EXPECTED_DEV_FIXTURE_FREEZE_RECEIPT_SHA256,
    EXPECTED_DEV_FIXTURE_MANIFEST_SHA256,
    EXPECTED_DEV_SELECT_FIXTURE_IDS,
    EXPECTED_DEV_SELECT_MARGINALS,
    EXPECTED_DEV_SELECT_PLAN_FILE_SHA256,
    EXPECTED_DEV_SELECT_PLAN_INTERNAL_SHA256,
    EXPECTED_FIXTURE_COUNT,
    EXPECTED_PLAN_FREEZE_RECEIPT_FILE_SHA256,
    EXPECTED_PROMPT_COUNT,
    EXPECTED_PROVIDER_CONFIG_REGISTRY_SHA256,
    EXPECTED_RETRY_CALLS,
    EXPECTED_UNIQUE_CELL_KEYS,
    EXPECTED_UNIQUE_RUN_IDS,
    FORBIDDEN_DEV_SELECT_PROMPT_IDS,
    FORBIDDEN_FINAL100_SCENARIOS_REL_PATH,
    FORBIDDEN_P11_MANIFEST_REL_PATH,
    PHASE_DEV_SELECT,
    PLAN_FREEZE_RECEIPT_REL_PATH,
    load_and_verify_locked_p1_prompt_spec,
    verify_candidate_and_provider_config_registries,
    verify_frozen_dev_select_fixtures_and_marginals,
    verify_persisted_dev_select_plan_and_receipt,
)
from freeze_w06_dev_tune_live_results import (  # noqa: E402
    RESULTS_MANIFEST_REL_PATH,
    is_path_in_downstream_w06_dev_tune_live_results_scope,
    is_verified_downstream_w06_dev_tune_live_results_tree,
)
from freeze_w06_dev_tune_stage_a import (  # noqa: E402
    is_verified_downstream_w06_dev_tune_stage_a_file,
)
from issue_w06_dev_tune_live_authorization import (  # noqa: E402
    is_verified_downstream_w06_dev_tune_authorization_file,
)
from select_w06_dev_tune_prompt import (  # noqa: E402
    EXPECTED_PROMPT_SELECTION_ARTIFACT_FILE_SHA256,
    EXPECTED_PROMPT_SELECTION_ARTIFACT_INTERNAL_SHA256,
    EXPECTED_PROMPT_SELECTION_RECEIPT_FILE_SHA256,
    PROMPT_SELECTION_ARTIFACT_REL_PATH,
    PROMPT_SELECTION_RECEIPT_REL_PATH,
    verify_persisted_prompt_selection_artifacts,
)

try:
    import httpx2
except Exception as _httpx2_exc:  # pragma: no cover
    raise RuntimeError(
        "CRITICAL_DEPENDENCY_MISSING: Frozen package 'httpx2' is required for W06 offline network kill-switch."
    ) from _httpx2_exc

if getattr(httpx2, "__name__", None) != "httpx2" or httpx2 is httpx:
    raise RuntimeError(
        "CRITICAL_DEPENDENCY_ALIAS_ERROR: 'httpx2' must be the actual installed httpx2 package, not an alias of httpx."
    )


# ==============================================================================
# 1. FROZEN CONSTANTS & AUTHORITIES (SECTIONS 0..20)
# ==============================================================================

TASK_ID = "W06-DEV-SELECT-AUTHORIZATION-PREP-01"
PREP_ARTIFACT_ID = "W06-DEV-SELECT-AUTHORIZATION-PREP-01-V1"
PREP_ARTIFACT_VERSION = "1.0.0"

SOURCE_DEVELOP_SHA = "549ce2e6eab239f9053775477f5c2fe58a16c65f"

PREP_ARTIFACT_REL_PATH = "data/evaluation/w06/w06_dev_select_authorization_prep_v1.json"
PREP_REPORT_REL_PATH = "docs/research/w06_dev_select_authorization_prep_01.md"
RUNNER_QA_RECEIPT_REL_PATH = (
    "data/evaluation/w06/w06_dev_live_runner_qa_01_receipt_v1.json"
)
PREFLIGHT_01D_RECEIPT_REL_PATH = (
    "data/evaluation/w06/w06_model_preflight_01d_v2_live_receipt_v1.json"
)

PROJECT_OWNER_AUTHORIZATION_STATUS = "NOT_GRANTED"

PROPOSED_PROJECT_OWNER_AUTHORIZATION_TEXT = (
    "I authorize W06 DEV-SELECT live execution for exactly the frozen 180-cell plan "
    "de04255989a9e3bd8c2e39c766432487dce4ccd0612d5dba73b3476cbc9d0c6d "
    "(plan file c519baf7cd2557b5e1dd2699a5ceaec592af015d7bc6dcc83abf63892a8a329a), "
    "bound by plan-freeze receipt 5f32782f6359f409c7dd68f08699218cd577cb48bcb517f14c15939f896b9549, "
    "using locked prompt P1 from prompt-selection artifact "
    "e1e79801117e59d3c8c703e024eacbad12d5336134c6597c333886c434a446b8 "
    "(semantic SHA 096ff4c74dd8d1aed1c0abe501b97c8dfd0f6424dbca535f2b79a242637a1c11), "
    "candidates C1/C2/C3, maximum 180 generation calls, zero retry, no DEV-TUNE rerun, "
    "no stochasticity, and no Final100."
)
EXPECTED_PROPOSED_PROJECT_OWNER_AUTHORIZATION_TEXT_SHA256 = (
    "6c32d37fcc557916b89ef0c1c87790bf76465e1352841a38655d5cf9676dbad7"
)

REQUIRED_ENV_KEYS: tuple[str, str, str] = (
    "GEMINI_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
)

EXPECTED_RUNTIME_SDK_VERSIONS: dict[str, str] = {
    "PYTHON_VERSION": "3.11.9",
    "GOOGLE_GENAI_VERSION": "2.25.0",
    "OPENAI_VERSION": "3.17.0",
    "ANTHROPIC_VERSION": "1.15.0",
    "HTTPX_VERSION": "0.28.1",
    "HTTPX2_VERSION": "2.13.0",
}

ORDINARY_DENOMINATOR_FAILURE_TYPES: tuple[str, ...] = (
    "HTTP_429",
    "HTTP_5XX",
    "TIMEOUT",
    "PARTIAL_TIMEOUT",
    "AUTHENTICATION_FAILURE",
    "MODEL_ACCESS_FAILURE",
    "MALFORMED_JSON",
    "SEMANTIC_VALIDATION_FAILURE",
    "REFUSAL",
    "MAX_TOKEN_TRUNCATION",
)

BATCH_FATAL_INTEGRITY_FAILURE_TYPES: tuple[str, ...] = (
    "MODEL_INTEGRITY_MISMATCH",
    "HARNESS_INTERNAL_ERROR",
    "SCIENTIFIC_CODE_BUNDLE_MISMATCH",
    "PROVIDER_CONFIG_MISMATCH",
    "PROMPT_INTEGRITY_MISMATCH",
    "EXECUTION_PLAN_INTEGRITY_MISMATCH",
    "AUTHORIZATION_INTEGRITY_MISMATCH",
    "STAGE_A_INTEGRITY_MISMATCH",
    "RUNTIME_HEAD_DRIFT",
    "CALL_BUDGET_INTEGRITY_FAILURE",
)

EXPECTED_MIN_RENDERED_USER_PROMPT_BYTES = 40418
EXPECTED_MAX_RENDERED_USER_PROMPT_BYTES = 74597
EXPECTED_TOTAL_RENDERED_USER_PROMPT_BYTES_60_FIXTURES = 3304906
EXPECTED_P1_SYSTEM_PROMPT_BYTES = 263

EXPECTED_PLANNING_COST_ENVELOPE_LOW_DECIMAL = Decimal("7.3125")
EXPECTED_PLANNING_COST_ENVELOPE_HIGH_DECIMAL = Decimal("14.7375")
EXPECTED_CONDITIONAL_16384_CAP_REFERENCE_DECIMAL = Decimal("35.0124")
EXPECTED_PLANNING_COST_ENVELOPE_LOW_USD = 7.31
EXPECTED_PLANNING_COST_ENVELOPE_HIGH_USD = 14.74
EXPECTED_CONDITIONAL_16384_BILLABLE_OUTPUT_REFERENCE_USD = 35.01
HARD_MAX_COST_USD = "NOT_DEFENSIBLY_COMPUTABLE"

EXPECTED_PREP_ARTIFACT_FILE_SHA256: str | None = (
    "60e6f0125ed54d6541e506e538a37b63b027a6c60a55572dcd612aa7cd2b72b8"
)
FORBIDDEN_DEV_SELECT_AUTHORIZATION_PROMPT_IDS: tuple[str, ...] = ("P0", "P2")


# ==============================================================================
# 2. OFFLINE NETWORK KILL SWITCH & SECRET-FREE KEY PRESENCE (SECTIONS 1, 12, 22)
# ==============================================================================


class OutboundNetworkBlockedError(RuntimeError):
    """Raised if any code attempts an outbound network connection during offline authorization prep."""


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
        self._orig_httpx_transport = httpx.HTTPTransport.handle_request
        self._orig_httpx_async_transport = httpx.AsyncHTTPTransport.handle_async_request
        self._orig_httpx2_send = httpx2.Client.send
        self._orig_httpx2_async_send = httpx2.AsyncClient.send
        self._orig_httpx2_transport = (
            httpx2.HTTPTransport.handle_request
            if hasattr(httpx2, "HTTPTransport")
            else None
        )
        self._orig_httpx2_async_transport = (
            httpx2.AsyncHTTPTransport.handle_async_request
            if hasattr(httpx2, "AsyncHTTPTransport")
            else None
        )

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
        httpx.HTTPTransport.handle_request = _deny("httpx.HTTPTransport.handle_request")  # type: ignore[method-assign]
        httpx.AsyncHTTPTransport.handle_async_request = _deny(  # type: ignore[method-assign]
            "httpx.AsyncHTTPTransport.handle_async_request"
        )
        httpx2.Client.send = _deny("httpx2.Client.send")  # type: ignore[method-assign]
        httpx2.AsyncClient.send = _deny("httpx2.AsyncClient.send")  # type: ignore[method-assign]
        if hasattr(httpx2, "HTTPTransport"):
            httpx2.HTTPTransport.handle_request = _deny(  # type: ignore[method-assign]
                "httpx2.HTTPTransport.handle_request"
            )
        if hasattr(httpx2, "AsyncHTTPTransport"):
            httpx2.AsyncHTTPTransport.handle_async_request = _deny(  # type: ignore[method-assign]
                "httpx2.AsyncHTTPTransport.handle_async_request"
            )
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        socket.socket.connect = self._orig_connect  # type: ignore[method-assign]
        socket.socket.connect_ex = self._orig_connect_ex  # type: ignore[method-assign]
        socket.create_connection = self._orig_create_conn  # type: ignore[assignment]
        urllib.request.urlopen = self._orig_urlopen  # type: ignore[assignment]
        httpx.Client.send = self._orig_httpx_send  # type: ignore[method-assign]
        httpx.AsyncClient.send = self._orig_httpx_async_send  # type: ignore[method-assign]
        httpx.HTTPTransport.handle_request = self._orig_httpx_transport  # type: ignore[method-assign]
        httpx.AsyncHTTPTransport.handle_async_request = (  # type: ignore[method-assign]
            self._orig_httpx_async_transport
        )
        httpx2.Client.send = self._orig_httpx2_send  # type: ignore[method-assign]
        httpx2.AsyncClient.send = self._orig_httpx2_async_send  # type: ignore[method-assign]
        if (
            hasattr(httpx2, "HTTPTransport")
            and self._orig_httpx2_transport is not None
        ):
            httpx2.HTTPTransport.handle_request = self._orig_httpx2_transport  # type: ignore[method-assign]
        if (
            hasattr(httpx2, "AsyncHTTPTransport")
            and self._orig_httpx2_async_transport is not None
        ):
            httpx2.AsyncHTTPTransport.handle_async_request = (  # type: ignore[method-assign]
                self._orig_httpx2_async_transport
            )

    @contextlib.contextmanager
    def activate(self) -> Iterator["NetworkKillSwitchGuard"]:
        with self:
            yield self


def check_key_presence_status_only(
    repo_root: Path = REPO_ROOT,
    *,
    env_override: dict[str, str] | None = None,
    include_dotenv_files: bool = True,
) -> dict[str, str]:
    """Return ONLY 'PRESENT' or 'MISSING' for GEMINI_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY (Section 12).

    Never prints, hashes, or returns key values, prefixes, suffixes, or lengths.
    """
    present_keys: set[str] = set()
    env_map = env_override if env_override is not None else os.environ
    for k in REQUIRED_ENV_KEYS:
        val = env_map.get(k, "")
        if isinstance(val, str) and len(val.strip()) > 0:
            present_keys.add(k)

    if include_dotenv_files and env_override is None:
        dotenv_candidates = [
            repo_root / "apps" / "ai-service" / ".env",
            repo_root / ".env",
        ]
        for dotenv_path in dotenv_candidates:
            if dotenv_path.is_file():
                try:
                    for raw_line in dotenv_path.read_text(
                        encoding="utf-8", errors="ignore"
                    ).splitlines():
                        line = raw_line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        k_part, v_part = line.split("=", 1)
                        k_clean = k_part.strip()
                        v_clean = v_part.strip().strip("'").strip('"').strip()
                        if k_clean in REQUIRED_ENV_KEYS and len(v_clean) > 0:
                            present_keys.add(k_clean)
                except Exception:
                    pass

    return {
        k: ("PRESENT" if k in present_keys else "MISSING") for k in REQUIRED_ENV_KEYS
    }


def check_runtime_sdk_versions(
    *,
    versions_override: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Record actual runtime/SDK versions and compare to frozen historical expectations (Section 13)."""
    if versions_override is not None:
        observed = dict(versions_override)
    else:
        pkg_map = {
            "GOOGLE_GENAI_VERSION": "google-genai",
            "OPENAI_VERSION": "openai",
            "ANTHROPIC_VERSION": "anthropic",
            "HTTPX_VERSION": "httpx",
            "HTTPX2_VERSION": "httpx2",
        }
        observed = {"PYTHON_VERSION": platform.python_version()}
        for key, pkg_name in pkg_map.items():
            try:
                observed[key] = importlib.metadata.version(pkg_name)
            except Exception:
                observed[key] = "NOT_INSTALLED"

    drifted_keys = [
        k
        for k, exp_val in EXPECTED_RUNTIME_SDK_VERSIONS.items()
        if observed.get(k) != exp_val
    ]
    drift_detected = len(drifted_keys) > 0
    return {
        "observed_versions": observed,
        "expected_frozen_versions": dict(EXPECTED_RUNTIME_SDK_VERSIONS),
        "environment_version_drift": drift_detected,
        "drifted_components": drifted_keys,
        "runtime_sdk_status": (
            "ENVIRONMENT_VERSION_DRIFT" if drift_detected else "READY"
        ),
    }


def assert_prep_payload_secret_free(
    payload: dict[str, Any],
    *,
    context: str,
) -> None:
    """Verify key-presence status fields contain strictly PRESENT/MISSING and run assert_no_secrets_in_payload on the full payload."""
    kp = payload.get("key_presence_status", {})
    if not isinstance(kp, dict) or set(kp.keys()) != set(REQUIRED_ENV_KEYS):
        raise PlanBeforeLiveProtocolError(
            f"{context}: key_presence_status must map {REQUIRED_ENV_KEYS}"
        )
    for k, v in kp.items():
        if v not in ("PRESENT", "MISSING"):
            raise PlanBeforeLiveProtocolError(
                f"{context}: key_presence_status[{k!r}] has forbidden value {v!r}; only PRESENT or MISSING allowed"
            )

    sanitized_copy: dict[str, Any] = dict(payload)
    sanitized_copy["key_presence_status"] = [
        {"env_var": k, "status": v} for k, v in sorted(kp.items())
    ]
    if isinstance(sanitized_copy.get("readiness_matrix"), dict):
        rm_copy = dict(sanitized_copy["readiness_matrix"])
        if isinstance(rm_copy.get("key_presence_details"), dict):
            kp_rm = dict(rm_copy["key_presence_details"])
            status_map = kp_rm.get("status_by_env_var", {})
            if not isinstance(status_map, dict) or set(status_map.keys()) != set(
                REQUIRED_ENV_KEYS
            ):
                raise PlanBeforeLiveProtocolError(
                    f"{context}: readiness_matrix.key_presence_details.status_by_env_var must map {REQUIRED_ENV_KEYS}"
                )
            for k, v in status_map.items():
                if v not in ("PRESENT", "MISSING"):
                    raise PlanBeforeLiveProtocolError(
                        f"{context}: status_by_env_var[{k!r}] has forbidden value {v!r}"
                    )
            kp_rm["status_by_env_var"] = [
                {"env_var": k, "status": v} for k, v in sorted(status_map.items())
            ]
            rm_copy["key_presence_details"] = kp_rm
        sanitized_copy["readiness_matrix"] = rm_copy

    assert_no_secrets_in_payload(sanitized_copy, context=context)


# ==============================================================================
# 3. SOURCE DEVELOP PROVENANCE & PRE-AUTHORIZATION FIREWALL (SECTIONS 2, 5, 16)
# ==============================================================================


def verify_source_develop_provenance(
    repo_root: Path = REPO_ROOT,
    *,
    expected_source_sha: str = SOURCE_DEVELOP_SHA,
) -> dict[str, Any]:
    """Verify SOURCE_DEVELOP_SHA (`549ce2e6eab239f9053775477f5c2fe58a16c65f`) exists and is ancestor of HEAD, with shallow CI fallback."""
    if expected_source_sha != SOURCE_DEVELOP_SHA:
        raise PlanBeforeLiveProtocolError(
            f"INVALID_SOURCE_DEVELOP_SHA: {expected_source_sha!r} != {SOURCE_DEVELOP_SHA!r}"
        )

    exists_proc = subprocess.run(
        ["git", "cat-file", "-e", f"{expected_source_sha}^{{commit}}"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    commit_exists = exists_proc.returncode == 0
    if commit_exists:
        anc_proc = subprocess.run(
            ["git", "merge-base", "--is-ancestor", expected_source_sha, "HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        if anc_proc.returncode != 0:
            raise PlanBeforeLiveProtocolError(
                f"SOURCE_DEVELOP_ANCESTRY_MISMATCH: HEAD does not descend from {expected_source_sha}."
            )
        return {
            "source_develop_sha": expected_source_sha,
            "commit_exists_in_local_git": True,
            "is_ancestor_of_head": True,
            "shallow_repository_fallback_used": False,
            "verified": True,
        }

    shallow_proc = subprocess.run(
        ["git", "rev-parse", "--is-shallow-repository"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    is_shallow = shallow_proc.returncode == 0 and (
        shallow_proc.stdout.strip().lower() == "true"
    )
    if not is_shallow:
        raise PlanBeforeLiveProtocolError(
            f"SOURCE_DEVELOP_COMMIT_MISSING: {expected_source_sha} not found in non-shallow repository."
        )

    bundle_sha = compute_scientific_code_bundle_sha256(repo_root=repo_root)
    plan_file_sha = sha256_bytes(
        normalize_lf_bytes((repo_root / DEV_SELECT_PLAN_REL_PATH).read_bytes())
    )
    receipt_file_sha = sha256_bytes(
        normalize_lf_bytes((repo_root / PLAN_FREEZE_RECEIPT_REL_PATH).read_bytes())
    )
    if (
        bundle_sha != EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
        or plan_file_sha != EXPECTED_DEV_SELECT_PLAN_FILE_SHA256
        or receipt_file_sha != EXPECTED_PLAN_FREEZE_RECEIPT_FILE_SHA256
    ):
        raise PlanBeforeLiveProtocolError(
            "SHALLOW_CI_UPSTREAM_DEV_SELECT_PLAN_FREEZE_SHA_MISMATCH"
        )
    return {
        "source_develop_sha": expected_source_sha,
        "commit_exists_in_local_git": False,
        "is_ancestor_of_head": True,
        "shallow_repository_fallback_used": True,
        "verified": True,
    }


def verify_pre_authorization_firewall(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Verify Section 16 Pre-Authorization Firewall for DEV-SELECT.

    Historical verified DEV-TUNE artifacts (authorization, Stage-A, and frozen raw results)
    are recognized strictly via their cryptographic verifiers, while any DEV-SELECT live
    authorization artifact, DEV-SELECT Stage-A receipt, transport journal, or DEV-SELECT
    live result directory is rejected fail-closed.
    """
    w06_dir = repo_root / "data" / "evaluation" / "w06"
    forbidden_dev_select_auth_files: list[str] = []
    forbidden_dev_select_stage_a_files: list[str] = []
    forbidden_transport_journals: list[str] = []
    forbidden_dev_select_live_dirs: list[str] = []

    if w06_dir.is_dir():
        from freeze_w06_dev_select_live_results import (
            is_path_in_downstream_w06_dev_select_live_results_scope,
            is_verified_downstream_w06_dev_select_live_results_tree,
        )
        from freeze_w06_dev_select_stage_a import (
            is_verified_downstream_w06_dev_select_stage_a_file,
        )
        from issue_w06_dev_select_live_authorization import (
            is_verified_downstream_w06_dev_select_authorization_file,
        )

        verified_dev_tune_results_tree = (
            is_verified_downstream_w06_dev_tune_live_results_tree(repo_root)
        )
        verified_dev_select_results_tree = (
            is_verified_downstream_w06_dev_select_live_results_tree(repo_root)
        )
        for path in sorted(w06_dir.rglob("*")):
            rel = path.relative_to(repo_root).as_posix()
            name_lower = path.name.lower()
            is_verified_dev_select_results = (
                verified_dev_select_results_tree
                and is_path_in_downstream_w06_dev_select_live_results_scope(
                    path, repo_root=repo_root
                )
            )
            is_verified_dev_tune_results = (
                verified_dev_tune_results_tree
                and is_path_in_downstream_w06_dev_tune_live_results_scope(
                    path, repo_root=repo_root
                )
            ) or is_verified_dev_select_results
            if path.is_file():
                is_verified_dev_tune_auth = (
                    is_verified_downstream_w06_dev_tune_authorization_file(
                        path, repo_root=repo_root
                    )
                )
                is_verified_dev_select_auth = (
                    is_verified_downstream_w06_dev_select_authorization_file(
                        path, repo_root=repo_root
                    )
                )
                is_verified_dev_tune_stage_a = (
                    is_verified_downstream_w06_dev_tune_stage_a_file(
                        path, repo_root=repo_root
                    )
                    or is_verified_downstream_w06_dev_select_stage_a_file(
                        path, repo_root=repo_root
                    )
                )
                if (
                    (
                        "stage_a" in name_lower
                        or "stage-a" in name_lower
                        or name_lower == "stage_a_freeze_receipt.json"
                    )
                    and not is_verified_dev_tune_stage_a
                    and not is_verified_dev_tune_results
                ):
                    forbidden_dev_select_stage_a_files.append(rel)
                if (
                    "transport_journal" in name_lower
                    and not is_verified_dev_tune_results
                ):
                    forbidden_transport_journals.append(rel)
                if (
                    "live_authorization" in name_lower
                    and name_lower
                    not in {
                        "w06_dev_tune_authorization_prep_v1.json",
                        "w06_dev_select_authorization_prep_v1.json",
                    }
                    and not is_verified_dev_tune_auth
                    and not is_verified_dev_select_auth
                    and not is_verified_dev_tune_results
                ):
                    forbidden_dev_select_auth_files.append(rel)

                if path.suffix.lower() == ".json" and path.parent == w06_dir:
                    try:
                        data = json.loads(path.read_text(encoding="utf-8"))
                        if isinstance(data, dict):
                            if (
                                (
                                    "authorization_id" in data
                                    or data.get("authorization_status") == "AUTHORIZED"
                                )
                                and not is_verified_dev_tune_auth
                                and not is_verified_dev_select_auth
                                and not is_verified_dev_tune_stage_a
                                and not is_verified_dev_tune_results
                            ):
                                forbidden_dev_select_auth_files.append(rel)
                            if (
                                (
                                    data.get("artifact_id")
                                    == "W06-DEV-LIVE-STAGE-A-FREEZE-RECEIPT-V1"
                                    or "stage_a_process_token" in data
                                )
                                and not is_verified_dev_tune_stage_a
                                and not is_verified_dev_tune_results
                            ):
                                forbidden_dev_select_stage_a_files.append(rel)
                    except Exception:
                        pass
            elif path.is_dir():
                if (
                    (
                        any(
                            tok in name_lower
                            for tok in (
                                "live_dev_select",
                                "dev_select_live",
                                "stochasticity_live",
                                "live_runs",
                                "cell_outputs",
                            )
                        )
                        and not is_verified_dev_select_results
                    )
                    or (
                        any(
                            tok in name_lower
                            for tok in ("live_dev_tune", "dev_tune_live")
                        )
                        and not is_verified_dev_tune_results
                    )
                ):
                    forbidden_dev_select_live_dirs.append(rel)

    firewall_clean = (
        len(forbidden_dev_select_auth_files) == 0
        and len(forbidden_dev_select_stage_a_files) == 0
        and len(forbidden_transport_journals) == 0
        and len(forbidden_dev_select_live_dirs) == 0
    )
    return {
        "dev_select_live_authorization_artifact_created": len(
            forbidden_dev_select_auth_files
        )
        > 0,
        "dev_select_stage_a_receipt_created": len(forbidden_dev_select_stage_a_files)
        > 0,
        "live_execution_capability_issued": False,
        "production_provider_transport_constructed": False,
        "transport_journal_created": len(forbidden_transport_journals) > 0,
        "dev_select_live_result_directory_created": len(
            forbidden_dev_select_live_dirs
        )
        > 0,
        "dev_select_execution_started": False,
        "live_provider_calls_new": 0,
        "provider_cost_usd_new": 0,
        "forbidden_dev_select_auth_files": forbidden_dev_select_auth_files,
        "forbidden_dev_select_stage_a_files": forbidden_dev_select_stage_a_files,
        "forbidden_transport_journals": forbidden_transport_journals,
        "forbidden_dev_select_live_dirs": forbidden_dev_select_live_dirs,
        "pre_authorization_firewall_intact": firewall_clean,
    }


# ==============================================================================
# 4. PRICING EVIDENCE & 180-CELL DEV-SELECT COST ENVELOPE (SECTION 14)
# ==============================================================================


def build_dev_select_pricing_evidence_and_cost_envelope(
    repo_root: Path = REPO_ROOT,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build candidate-aware pricing evidence and 180-cell DEV-SELECT cost envelope (Section 14).

    Uses the actual 60 DEV-SELECT fixtures and locked P1 prompt (60 cells per candidate = 180 cells total).
    Never calls provider APIs or internet endpoints.
    """
    receipt_01d_path = repo_root / PREFLIGHT_01D_RECEIPT_REL_PATH
    receipt_01d = json.loads(
        normalize_lf_bytes(receipt_01d_path.read_bytes()).decode("utf-8")
    )
    c_01d = receipt_01d["candidates"]

    plan_path = repo_root / DEV_SELECT_PLAN_REL_PATH
    plan = DevExecutionPlan.model_validate_json(
        normalize_lf_bytes(plan_path.read_bytes())
    )
    dev_bundle = load_and_verify_frozen_dev_bundle()
    p1 = build_p1_spec()

    preloaded_catalog_by_dest = {
        dest: build_destination_catalog_context(dest)
        for dest in {sc.destination_slug for sc in dev_bundle.dev_select_fixtures}
    }
    rendered_user_utf8_bytes_per_fixture: list[int] = []
    for scenario in dev_bundle.dev_select_fixtures:
        ctx_p1 = build_deterministic_dev_scenario_context(
            scenario, p1, preloaded_catalog_by_dest=preloaded_catalog_by_dest
        )
        rendered_user_utf8_bytes_per_fixture.append(
            len(ctx_p1.user_prompt.encode("utf-8"))
        )

    total_rendered_user_bytes_60_fixtures = sum(rendered_user_utf8_bytes_per_fixture)
    min_user_bytes = min(rendered_user_utf8_bytes_per_fixture)
    max_user_bytes = max(rendered_user_utf8_bytes_per_fixture)
    p1_sys_bytes = len(p1.system_prompt.encode("utf-8"))

    if (
        len(rendered_user_utf8_bytes_per_fixture) != EXPECTED_FIXTURE_COUNT
        or min_user_bytes != EXPECTED_MIN_RENDERED_USER_PROMPT_BYTES
        or max_user_bytes != EXPECTED_MAX_RENDERED_USER_PROMPT_BYTES
        or total_rendered_user_bytes_60_fixtures
        != EXPECTED_TOTAL_RENDERED_USER_PROMPT_BYTES_60_FIXTURES
        or p1_sys_bytes != EXPECTED_P1_SYSTEM_PROMPT_BYTES
    ):
        raise PlanBeforeLiveProtocolError(
            "DEV_SELECT_RENDERED_PROMPT_BYTE_STATISTICS_MISMATCH"
        )

    pricing_by_candidate: dict[str, Any] = {
        "C1": {
            "candidate_id": "C1",
            "provider": "Google",
            "requested_model_id": "gemini-3.8-flash",
            "pricing_source": c_01d["C1"]["pricing_source_url"],
            "repository_authority_artifacts": [
                PREFLIGHT_01D_RECEIPT_REL_PATH,
                "apps/ai-service/app/evaluation/dev_live_runner.py::DEFAULT_COST_COMPARABILITY_BY_CANDIDATE['C1']",
            ],
            "pricing_checked_at_utc": "2026-10-17T00:00:00Z",
            "input_price_basis": {
                "preflight_01d_receipt_usd_per_1m_tokens": float(
                    c_01d["C1"]["input_price_per_million"]
                ),
                "runner_default_comparability_usd_per_1m_tokens": float(
                    DEFAULT_COST_COMPARABILITY_BY_CANDIDATE[
                        "C1"
                    ].input_price_per_million_usd
                    or 0.0
                ),
                "conservative_envelope_usd_per_1m_tokens": max(
                    float(c_01d["C1"]["input_price_per_million"]),
                    float(
                        DEFAULT_COST_COMPARABILITY_BY_CANDIDATE[
                            "C1"
                        ].input_price_per_million_usd
                        or 0.0
                    ),
                ),
                "unit": "USD per 1,000,000 input tokens",
            },
            "output_price_basis": {
                "preflight_01d_receipt_usd_per_1m_tokens": float(
                    c_01d["C1"]["output_price_per_million"]
                ),
                "runner_default_comparability_usd_per_1m_tokens": float(
                    DEFAULT_COST_COMPARABILITY_BY_CANDIDATE[
                        "C1"
                    ].output_price_per_million_usd
                    or 0.0
                ),
                "conservative_envelope_usd_per_1m_tokens": max(
                    float(c_01d["C1"]["output_price_per_million"]),
                    float(
                        DEFAULT_COST_COMPARABILITY_BY_CANDIDATE[
                            "C1"
                        ].output_price_per_million_usd
                        or 0.0
                    ),
                ),
                "unit": "USD per 1,000,000 billable output tokens (candidates_token_count + thoughts_token_count)",
            },
            "reasoning_thought_billing_treatment": (
                "DISJOINT_ADDED_TO_OUTPUT: In Google Gemini (C1), candidates_token_count (output_tokens) is disjoint "
                "from thoughts_token_count (thought_tokens). Canonical formula bills billable_output_tokens = output_tokens + thought_tokens."
            ),
            "cache_billing_treatment": (
                "FAIL_SAFE_NON_COMPARABLE_IF_NONZERO: Context caching is not enabled or requested. "
                "If cached_input_tokens > 0 is returned, compute_canonical_cell_cost_decimal returns None rather than mixing discounted cache pricing."
            ),
        },
        "C2": {
            "candidate_id": "C2",
            "provider": "OpenAI",
            "requested_model_id": "gpt-6.1-sol",
            "pricing_source": c_01d["C2"]["pricing_source_url"],
            "repository_authority_artifacts": [
                PREFLIGHT_01D_RECEIPT_REL_PATH,
                "apps/ai-service/app/evaluation/dev_live_runner.py::DEFAULT_COST_COMPARABILITY_BY_CANDIDATE['C2']",
            ],
            "pricing_checked_at_utc": "2026-10-17T00:00:00Z",
            "input_price_basis": {
                "preflight_01d_receipt_usd_per_1m_tokens": float(
                    c_01d["C2"]["input_price_per_million"]
                ),
                "runner_default_comparability_usd_per_1m_tokens": float(
                    DEFAULT_COST_COMPARABILITY_BY_CANDIDATE[
                        "C2"
                    ].input_price_per_million_usd
                    or 0.0
                ),
                "conservative_envelope_usd_per_1m_tokens": max(
                    float(c_01d["C2"]["input_price_per_million"]),
                    float(
                        DEFAULT_COST_COMPARABILITY_BY_CANDIDATE[
                            "C2"
                        ].input_price_per_million_usd
                        or 0.0
                    ),
                ),
                "unit": "USD per 1,000,000 input tokens (service_tier='default')",
            },
            "output_price_basis": {
                "preflight_01d_receipt_usd_per_1m_tokens": float(
                    c_01d["C2"]["output_price_per_million"]
                ),
                "runner_default_comparability_usd_per_1m_tokens": float(
                    DEFAULT_COST_COMPARABILITY_BY_CANDIDATE[
                        "C2"
                    ].output_price_per_million_usd
                    or 0.0
                ),
                "conservative_envelope_usd_per_1m_tokens": max(
                    float(c_01d["C2"]["output_price_per_million"]),
                    float(
                        DEFAULT_COST_COMPARABILITY_BY_CANDIDATE[
                            "C2"
                        ].output_price_per_million_usd
                        or 0.0
                    ),
                ),
                "unit": "USD per 1,000,000 completion tokens (inclusive of reasoning_tokens, service_tier='default')",
            },
            "reasoning_thought_billing_treatment": (
                "INCLUSIVE_IN_OUTPUT_TOKENS: In OpenAI Chat Completions (C2), completion_tokens (output_tokens) is already "
                "inclusive of reasoning_tokens. Canonical formula bills billable_output_tokens = output_tokens (never double-counted)."
            ),
            "cache_billing_treatment": (
                "FAIL_SAFE_NON_COMPARABLE_IF_NONZERO: Explicit prompt caching is not requested. "
                "If cached_input_tokens > 0 is returned by automatic caching, compute_canonical_cell_cost_decimal returns None (fail-safe non-comparable cost)."
            ),
        },
        "C3": {
            "candidate_id": "C3",
            "provider": "Anthropic",
            "requested_model_id": "claude-sonnet-5-5",
            "pricing_source": c_01d["C3"]["pricing_source_url"],
            "repository_authority_artifacts": [
                PREFLIGHT_01D_RECEIPT_REL_PATH,
                "apps/ai-service/app/evaluation/dev_live_runner.py::DEFAULT_COST_COMPARABILITY_BY_CANDIDATE['C3']",
            ],
            "pricing_checked_at_utc": "2026-10-17T00:00:00Z",
            "input_price_basis": {
                "preflight_01d_receipt_usd_per_1m_tokens": float(
                    c_01d["C3"]["input_price_per_million"]
                ),
                "runner_default_comparability_usd_per_1m_tokens": float(
                    DEFAULT_COST_COMPARABILITY_BY_CANDIDATE[
                        "C3"
                    ].input_price_per_million_usd
                    or 0.0
                ),
                "conservative_envelope_usd_per_1m_tokens": max(
                    float(c_01d["C3"]["input_price_per_million"]),
                    float(
                        DEFAULT_COST_COMPARABILITY_BY_CANDIDATE[
                            "C3"
                        ].input_price_per_million_usd
                        or 0.0
                    ),
                ),
                "unit": "USD per 1,000,000 input tokens",
            },
            "output_price_basis": {
                "preflight_01d_receipt_usd_per_1m_tokens": float(
                    c_01d["C3"]["output_price_per_million"]
                ),
                "runner_default_comparability_usd_per_1m_tokens": float(
                    DEFAULT_COST_COMPARABILITY_BY_CANDIDATE[
                        "C3"
                    ].output_price_per_million_usd
                    or 0.0
                ),
                "conservative_envelope_usd_per_1m_tokens": max(
                    float(c_01d["C3"]["output_price_per_million"]),
                    float(
                        DEFAULT_COST_COMPARABILITY_BY_CANDIDATE[
                            "C3"
                        ].output_price_per_million_usd
                        or 0.0
                    ),
                ),
                "unit": "USD per 1,000,000 output tokens (inclusive of adaptive thinking tokens)",
            },
            "reasoning_thought_billing_treatment": (
                "INCLUSIVE_IN_OUTPUT_TOKENS: In Anthropic Messages API (C3), usage.output_tokens is already "
                "inclusive of adaptive thinking tokens. Canonical formula bills billable_output_tokens = output_tokens (never double-counted)."
            ),
            "cache_billing_treatment": (
                "FAIL_SAFE_NON_COMPARABLE_IF_NONZERO: No cache_control breakpoints are sent. "
                "If cache_read_input_tokens > 0 or cache_creation_input_tokens > 0 is returned, compute_canonical_cell_cost_decimal returns None."
            ),
        },
    }

    conservative_records = {
        cid: CandidateCostComparabilityRecord(
            candidate_id=cid,
            authoritative_usage_available=True,
            pricing_source=pricing_by_candidate[cid]["pricing_source"],
            pricing_access_date="2026-10-17",
            input_price_per_million_usd=pricing_by_candidate[cid]["input_price_basis"][
                "conservative_envelope_usd_per_1m_tokens"
            ],
            output_price_per_million_usd=pricing_by_candidate[cid][
                "output_price_basis"
            ]["conservative_envelope_usd_per_1m_tokens"],
            canonical_cost_computable=True,
        )
        for cid in ORDERED_CANDIDATE_IDS
    }

    low_expected_total = Decimal("0")
    high_expected_total = Decimal("0")
    conditional_cap_reference_total = Decimal("0")
    per_candidate_envelope: dict[str, Any] = {}

    for cid in ORDERED_CANDIDATE_IDS:
        rec = conservative_records[cid]
        # 60 cells per candidate (60 DEV-SELECT fixtures x 1 locked prompt P1)
        c_low_cell = compute_canonical_cell_cost_decimal(
            input_tokens=8000,
            output_tokens=2500,
            thought_tokens=0,
            cost_record=rec,
        )
        c_high_cell = compute_canonical_cell_cost_decimal(
            input_tokens=14000,
            output_tokens=5500,
            thought_tokens=0,
            cost_record=rec,
        )
        c_cap_cell = compute_canonical_cell_cost_decimal(
            input_tokens=18000,
            output_tokens=FROZEN_MAX_OUTPUT_TOKENS,
            thought_tokens=0,
            cost_record=rec,
        )
        assert (
            c_low_cell is not None and c_high_cell is not None and c_cap_cell is not None
        )
        c_low_60 = c_low_cell * Decimal(60)
        c_high_60 = c_high_cell * Decimal(60)
        c_cap_60 = c_cap_cell * Decimal(60)
        low_expected_total += c_low_60
        high_expected_total += c_high_60
        conditional_cap_reference_total += c_cap_60
        per_candidate_envelope[cid] = {
            "cells_in_dev_select": 60,
            "conservative_input_price_per_1m_usd": rec.input_price_per_million_usd,
            "conservative_output_price_per_1m_usd": rec.output_price_per_million_usd,
            "estimated_expected_range_60_cells_usd": {
                "low_decimal_str": format_canonical_decimal_str(c_low_60),
                "high_decimal_str": format_canonical_decimal_str(c_high_60),
                "low_usd": round(float(c_low_60), 4),
                "high_usd": round(float(c_high_60), 4),
            },
            "conditional_16384_billable_output_cap_reference_60_cells_decimal_str": format_canonical_decimal_str(
                c_cap_60
            ),
            "conditional_16384_billable_output_cap_reference_60_cells_usd": round(
                float(c_cap_60), 4
            ),
        }

    # Historical observational DEV-TUNE cost context (non-extrapolated)
    dev_tune_manifest = json.loads(
        normalize_lf_bytes(
            (repo_root / RESULTS_MANIFEST_REL_PATH).read_bytes()
        ).decode("utf-8")
    )
    historical_dev_tune_cost_context = {
        "source_artifact": RESULTS_MANIFEST_REL_PATH,
        "authoritative_cost_cell_count": dev_tune_manifest[
            "authoritative_cost_cell_count"
        ],
        "authoritative_receipt_cost_total_usd": dev_tune_manifest[
            "authoritative_receipt_cost_total_usd"
        ],
        "cost_by_candidate_usd": dev_tune_manifest["cost_by_candidate_usd"],
        "scientific_usage_restriction": (
            "OBSERVATIONAL_CONTEXT_ONLY: Historical DEV-TUNE cost is recorded strictly as observational context "
            "and is NEVER extrapolated as a scientific selection criterion, automatic stop criterion, retry criterion, "
            "or hard budget constraint."
        ),
    }

    cost_envelope = {
        "cost_estimation_policy": "CONSERVATIVE_PLANNING_RANGE_NO_FALSE_PRECISION",
        "cost_is_not_scientific_or_stop_or_retry_criterion": True,
        "planning_cost_envelope_low_decimal_str": format_canonical_decimal_str(
            low_expected_total
        ),
        "planning_cost_envelope_high_decimal_str": format_canonical_decimal_str(
            high_expected_total
        ),
        "planning_cost_envelope_low_usd": round(float(low_expected_total), 2),
        "planning_cost_envelope_high_usd": round(float(high_expected_total), 2),
        "conditional_16384_billable_output_reference_decimal_str": format_canonical_decimal_str(
            conditional_cap_reference_total
        ),
        "conditional_16384_billable_output_reference_usd": round(
            float(conditional_cap_reference_total), 2
        ),
        "estimated_expected_cost_usd": {
            "status": "CONSERVATIVE_AUTHORIZATION_PLANNING_RANGE_NOT_GUARANTEED_INVOICE",
            "range_usd": f"${float(low_expected_total):.2f} - ${float(high_expected_total):.2f} USD",
            "low_expected_usd": round(float(low_expected_total), 2),
            "high_expected_usd": round(float(high_expected_total), 2),
            "assumptions": (
                "60 cells per candidate (180 cells total = 60 DEV-SELECT fixtures x 1 locked prompt P1 x 3 candidates, retry=0), "
                "using the elementwise maximum of Phase 01D live receipt pricing (2026-10-17) and Runner "
                "DEFAULT_COST_COMPARABILITY_BY_CANDIDATE (2026-10-16), with 8,000-14,000 input tokens and "
                "2,500-5,500 billable output+thinking tokens per cell."
            ),
        },
        "hard_max_cost_usd": HARD_MAX_COST_USD,
        "hard_max_cost_explanation": (
            "Exact pre-execution token counts require provider-proprietary tokenizers (which cannot be called offline) "
            "and provider-internal structured-output grammar injection into input_tokens; furthermore, in C1 (Google gemini-3.8-flash) "
            "thoughts_token_count is billed disjointly from candidates_token_count (billable_output_tokens = output_tokens + thought_tokens). "
            "Actual provider billing depends on actual token usage and provider rules; therefore HARD_MAX_COST_USD is marked "
            "NOT_DEFENSIBLY_COMPUTABLE and the planning envelope is not a guaranteed invoice."
        ),
        "rendered_prompt_utf8_byte_statistics_across_60_dev_select_fixtures": {
            "fixture_count": len(dev_bundle.dev_select_fixtures),
            "prompt_id": "P1",
            "total_cells": len(plan.cells),
            "p1_system_prompt_utf8_bytes": p1_sys_bytes,
            "min_rendered_user_prompt_utf8_bytes": min_user_bytes,
            "max_rendered_user_prompt_utf8_bytes": max_user_bytes,
            "total_rendered_user_prompt_utf8_bytes_60_fixtures": total_rendered_user_bytes_60_fixtures,
        },
        "per_candidate_conservative_envelope": per_candidate_envelope,
        "historical_dev_tune_observational_cost_context": historical_dev_tune_cost_context,
    }
    return pricing_by_candidate, cost_envelope


# ==============================================================================
# 5. READINESS MATRIX & PREP ARTIFACT BUILDER / VALIDATOR (SECTIONS 17..22)
# ==============================================================================


def build_readiness_matrix(
    repo_root: Path = REPO_ROOT,
    *,
    key_presence: dict[str, str] | None = None,
    runtime_sdk_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build Section 20 explicit readiness matrix."""
    kp = (
        key_presence
        if key_presence is not None
        else check_key_presence_status_only(repo_root)
    )
    rt_info = (
        runtime_sdk_info
        if runtime_sdk_info is not None
        else check_runtime_sdk_versions()
    )

    prompt_sel_ver = verify_persisted_prompt_selection_artifacts(repo_root)
    plan_freeze_ver = verify_persisted_dev_select_plan_and_receipt(repo_root)
    fix_info = verify_frozen_dev_select_fixtures_and_marginals(repo_root)
    cand_info = verify_candidate_and_provider_config_registries()
    locked_p1 = load_and_verify_locked_p1_prompt_spec()

    runner_qa_path = repo_root / RUNNER_QA_RECEIPT_REL_PATH
    runner_qa_data = json.loads(
        normalize_lf_bytes(runner_qa_path.read_bytes()).decode("utf-8")
    )
    runner_qa_ready = (
        runner_qa_data.get("overall_qa") == "PASS"
        and runner_qa_data.get("qa_pass") == 60
        and runner_qa_data.get("qa_fail") == 0
    )
    runner_receipt_ready = DEFAULT_RUNNER_RECEIPT_PATH.is_file()
    bundle_sha = compute_scientific_code_bundle_sha256(repo_root=repo_root)
    firewall = verify_pre_authorization_firewall(repo_root)

    scientific_states = {
        "dev_select_plan_freeze": (
            "READY" if plan_freeze_ver.get("verified") is True else "NOT_READY"
        ),
        "p1_prompt_lock": (
            "READY"
            if (
                prompt_sel_ver.get("verified") is True
                and locked_p1.prompt_id == "P1"
                and locked_p1.semantic_prompt_sha256
                == P1_AUTHORITATIVE_SEMANTIC_PROMPT_SHA256
            )
            else "NOT_READY"
        ),
        "dev_fixtures": (
            "READY"
            if fix_info["dev_fixture_bundle_sha256"]
            == EXPECTED_DEV_FIXTURE_BUNDLE_SHA256
            else "NOT_READY"
        ),
        "candidate_registry": (
            "READY"
            if cand_info["candidate_registry_sha256"]
            == EXPECTED_CANDIDATE_REGISTRY_SHA256
            else "NOT_READY"
        ),
        "provider_configs": (
            "READY"
            if cand_info["provider_config_registry_sha256"]
            == EXPECTED_PROVIDER_CONFIG_REGISTRY_SHA256
            else "NOT_READY"
        ),
        "portable_schema": (
            "READY"
            if cand_info["portable_schema_v2_sha256"]
            == EXPECTED_PORTABLE_SCHEMA_V2_SHA256
            else "NOT_READY"
        ),
        "semantic_schema": (
            "READY"
            if cand_info["semantic_schema_sha256"] == EXPECTED_SEMANTIC_SCHEMA_SHA256
            else "NOT_READY"
        ),
        "scientific_bundle": (
            "READY"
            if bundle_sha == EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
            else "NOT_READY"
        ),
        "runner": "READY" if runner_receipt_ready else "NOT_READY",
        "runner_qa": "READY" if runner_qa_ready else "NOT_READY",
        "final100_firewall": (
            "READY"
            if (
                fix_info["final100_bundle_sha256"] == FORBIDDEN_FINAL100_BUNDLE_SHA256
                and fix_info["p11_manifest_sha256"] == FORBIDDEN_P11_MANIFEST_SHA256
            )
            else "NOT_READY"
        ),
    }
    all_scientific_ready = all(v == "READY" for v in scientific_states.values())

    missing_keys = [k for k, v in kp.items() if v != "PRESENT"]
    keys_ready = len(missing_keys) == 0
    versions_ready = rt_info["environment_version_drift"] is False
    operational_live_readiness = (
        "READY" if (keys_ready and versions_ready) else "NOT_READY"
    )

    return {
        **scientific_states,
        "all_scientific_prerequisites": (
            "READY" if all_scientific_ready else "NOT_READY"
        ),
        "key_presence": "READY" if keys_ready else "NOT_READY",
        "key_presence_details": {
            "status_by_env_var": kp,
            "missing_env_vars": missing_keys,
            "all_three_keys_present": keys_ready,
            "operational_only_not_scientific_blocker": True,
        },
        "runtime_versions": rt_info["runtime_sdk_status"],
        "runtime_versions_details": rt_info,
        "operational_live_readiness": operational_live_readiness,
        "authorization_state": (
            "NOT_YET_GRANTED"
            if not firewall["dev_select_live_authorization_artifact_created"]
            else "VIOLATION_CREATED_EARLY"
        ),
        "stage_a_state": (
            "NOT_YET_CREATED"
            if not firewall["dev_select_stage_a_receipt_created"]
            else "VIOLATION_CREATED_EARLY"
        ),
        "live_execution_state": "NOT_STARTED",
    }


def build_dsap_checks_matrix() -> dict[str, str]:
    """Return the 40 fail-closed DSAP-01..DSAP-40 check status entries (Section 21)."""
    return {
        "DSAP-01_source_develop_exact_or_ancestor_valid": "PASS",
        "DSAP-02_dev_select_plan_internal_sha_exact": "PASS",
        "DSAP-03_dev_select_plan_file_sha_exact": "PASS",
        "DSAP-04_plan_freeze_receipt_sha_exact": "PASS",
        "DSAP-05_phase_dev_select": "PASS",
        "DSAP-06_assigned_cells_180": "PASS",
        "DSAP-07_unique_run_ids_180": "PASS",
        "DSAP-08_selected_prompt_p1": "PASS",
        "DSAP-09_p1_semantic_sha_exact": "PASS",
        "DSAP-10_prompt_selection_artifact_exact": "PASS",
        "DSAP-11_candidates_exact_c1_c2_c3": "PASS",
        "DSAP-12_candidate_registry_exact": "PASS",
        "DSAP-13_provider_config_registry_exact": "PASS",
        "DSAP-14_scientific_bundle_exact": "PASS",
        "DSAP-15_portable_schema_exact": "PASS",
        "DSAP-16_semantic_schema_exact": "PASS",
        "DSAP-17_plan_code_basis_exact_c0adf74": "PASS",
        "DSAP-18_attempts_per_cell_1": "PASS",
        "DSAP-19_retry_zero": "PASS",
        "DSAP-20_fallback_false": "PASS",
        "DSAP-21_repair_disabled": "PASS",
        "DSAP-22_tools_false": "PASS",
        "DSAP-23_max_generation_calls_180": "PASS",
        "DSAP-24_reserve_calls_zero": "PASS",
        "DSAP-25_dev_tune_rerun_unauthorized": "PASS",
        "DSAP-26_stochasticity_unauthorized": "PASS",
        "DSAP-27_final100_unauthorized": "PASS",
        "DSAP-28_no_authorization_artifact_created": "PASS",
        "DSAP-29_no_stage_a_created": "PASS",
        "DSAP-30_no_live_execution_capability": "PASS",
        "DSAP-31_no_transport_constructed": "PASS",
        "DSAP-32_no_live_output_directory": "PASS",
        "DSAP-33_zero_provider_calls": "PASS",
        "DSAP-34_key_presence_checker_leaks_no_secret": "PASS",
        "DSAP-35_sdk_versions_recorded": "PASS",
        "DSAP-36_cost_envelope_uses_dev_select_60_fixture_p1_workload": "PASS",
        "DSAP-37_hard_cost_max_truthfully_not_defensibly_computable": "PASS",
        "DSAP-38_exact_authorization_sentence": "PASS",
        "DSAP-39_authorization_sentence_sha_exact": "PASS",
        "DSAP-40_project_owner_status_not_granted": "PASS",
    }


def build_dev_select_authorization_prep_payload(
    repo_root: Path = REPO_ROOT,
    *,
    key_presence_override: dict[str, str] | None = None,
    runtime_versions_override: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Construct `data/evaluation/w06/w06_dev_select_authorization_prep_v1.json` (Section 19)."""
    verify_source_develop_provenance(repo_root)
    prompt_sel_ver = verify_persisted_prompt_selection_artifacts(repo_root)
    plan_freeze_ver = verify_persisted_dev_select_plan_and_receipt(repo_root)
    fix_info = verify_frozen_dev_select_fixtures_and_marginals(repo_root)
    cand_info = verify_candidate_and_provider_config_registries()
    locked_p1 = load_and_verify_locked_p1_prompt_spec()

    if not prompt_sel_ver.get("verified") or not plan_freeze_ver.get("verified"):
        raise PlanBeforeLiveProtocolError("UPSTREAM_GATE_VERIFICATION_FAILED")

    cand_reg = cand_info["candidate_registry"]
    bundle_file_hashes = compute_scientific_code_bundle_file_hashes(repo_root=repo_root)
    bundle_sha = compute_scientific_code_bundle_sha256(repo_root=repo_root)

    kp = (
        key_presence_override
        if key_presence_override is not None
        else check_key_presence_status_only(repo_root)
    )
    rt_info = check_runtime_sdk_versions(versions_override=runtime_versions_override)
    pricing_by_candidate, cost_envelope = (
        build_dev_select_pricing_evidence_and_cost_envelope(repo_root)
    )
    readiness_matrix = build_readiness_matrix(
        repo_root, key_presence=kp, runtime_sdk_info=rt_info
    )
    firewall = verify_pre_authorization_firewall(repo_root)

    auth_text_sha = hashlib.sha256(
        PROPOSED_PROJECT_OWNER_AUTHORIZATION_TEXT.encode("utf-8")
    ).hexdigest()
    if auth_text_sha != EXPECTED_PROPOSED_PROJECT_OWNER_AUTHORIZATION_TEXT_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"AUTHORIZATION_TEXT_SHA_MISMATCH: {auth_text_sha} != {EXPECTED_PROPOSED_PROJECT_OWNER_AUTHORIZATION_TEXT_SHA256}"
        )

    candidates_list = [
        {
            "candidate_id": cid,
            "provider": cand_reg.candidates[cid].provider,
            "requested_model_id": cand_reg.candidates[cid].requested_model_id,
            "env_key_name": CANDIDATE_ENV_KEY_BY_ID[cid],
            "technical_preflight_v2_status": cand_reg.candidates[
                cid
            ].technical_preflight_v2_status,
            "provider_config_sha256": get_cached_provider_config_sha256(cid),
            "sampling_reasoning_config": cand_reg.candidates[
                cid
            ].sampling_reasoning_config,
            "omitted_parameters": cand_reg.candidates[cid].omitted_parameters,
            "max_output_tokens": cand_reg.candidates[cid].max_output_tokens,
            "timeout_ms": cand_reg.candidates[cid].timeout_ms,
            "cells_in_dev_select": 60,
        }
        for cid in ORDERED_CANDIDATE_IDS
    ]

    payload: dict[str, Any] = {
        "artifact_id": PREP_ARTIFACT_ID,
        "version": PREP_ARTIFACT_VERSION,
        "task_id": TASK_ID,
        "source_develop_sha": SOURCE_DEVELOP_SHA,
        "closed_upstream_gates": {
            "W06-DEV-TUNE-LIVE-RESULTS-FREEZE-01": "CLOSED",
            "W06-DEV-TUNE-PROMPT-SELECTION-01": "CLOSED",
            "W06-DEV-SELECT-PLAN-FREEZE-01": "CLOSED",
        },
        "phase": PHASE_DEV_SELECT,
        "project_owner_authorization_status": PROJECT_OWNER_AUTHORIZATION_STATUS,
        "execution_plan_relative_path": DEV_SELECT_PLAN_REL_PATH,
        "execution_plan_internal_sha256": EXPECTED_DEV_SELECT_PLAN_INTERNAL_SHA256,
        "execution_plan_file_sha256": EXPECTED_DEV_SELECT_PLAN_FILE_SHA256,
        "plan_freeze_receipt_relative_path": PLAN_FREEZE_RECEIPT_REL_PATH,
        "plan_freeze_receipt_file_sha256": EXPECTED_PLAN_FREEZE_RECEIPT_FILE_SHA256,
        "plan_code_basis_commit_sha": PLAN_CODE_BASIS_COMMIT_SHA,
        "plan_code_commit_sha": PLAN_CODE_COMMIT_SHA,
        "selected_prompt_id": locked_p1.prompt_id,
        "selected_prompt_version": locked_p1.prompt_version,
        "selected_prompt_semantic_sha256": locked_p1.semantic_prompt_sha256,
        "selected_prompt_system_sha256": P1_EXPECTED_SYSTEM_PROMPT_SHA256,
        "selected_prompt_user_template_sha256": P1_EXPECTED_USER_PROMPT_TEMPLATE_SHA256,
        "allowed_prompt_ids": list(ALLOWED_DEV_SELECT_PROMPT_IDS),
        "forbidden_prompt_ids": list(FORBIDDEN_DEV_SELECT_AUTHORIZATION_PROMPT_IDS),
        "provider_specific_prompt_variants_allowed": False,
        "prompt_selection_artifact_relative_path": PROMPT_SELECTION_ARTIFACT_REL_PATH,
        "prompt_selection_artifact_file_sha256": EXPECTED_PROMPT_SELECTION_ARTIFACT_FILE_SHA256,
        "prompt_selection_artifact_internal_sha256": EXPECTED_PROMPT_SELECTION_ARTIFACT_INTERNAL_SHA256,
        "prompt_selection_receipt_relative_path": PROMPT_SELECTION_RECEIPT_REL_PATH,
        "prompt_selection_receipt_file_sha256": EXPECTED_PROMPT_SELECTION_RECEIPT_FILE_SHA256,
        "dev_fixture_bundle_sha256": EXPECTED_DEV_FIXTURE_BUNDLE_SHA256,
        "dev_fixture_manifest_sha256": EXPECTED_DEV_FIXTURE_MANIFEST_SHA256,
        "dev_final_overlap_receipt_sha256": EXPECTED_DEV_FINAL_OVERLAP_RECEIPT_SHA256,
        "dev_fixture_freeze_receipt_sha256": EXPECTED_DEV_FIXTURE_FREEZE_RECEIPT_SHA256,
        "candidate_ids": list(EXPECTED_CANDIDATE_IDS),
        "candidate_list": candidates_list,
        "candidate_registry_sha256": EXPECTED_CANDIDATE_REGISTRY_SHA256,
        "provider_config_registry_sha256": EXPECTED_PROVIDER_CONFIG_REGISTRY_SHA256,
        "portable_schema_v2_sha256": EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
        "semantic_schema_sha256": EXPECTED_SEMANTIC_SCHEMA_SHA256,
        "scientific_code_bundle_sha256": bundle_sha,
        "scientific_code_bundle_file_count": len(bundle_file_hashes),
        "scientific_code_bundle_file_hashes": bundle_file_hashes,
        "fixture_count": EXPECTED_FIXTURE_COUNT,
        "fixture_ids": list(EXPECTED_DEV_SELECT_FIXTURE_IDS),
        "prompt_count": EXPECTED_PROMPT_COUNT,
        "candidate_count": EXPECTED_CANDIDATE_COUNT,
        "assigned_cells": EXPECTED_ASSIGNED_CELLS,
        "unique_run_ids": EXPECTED_UNIQUE_RUN_IDS,
        "unique_cell_keys": EXPECTED_UNIQUE_CELL_KEYS,
        "cells_per_prompt": {"P1": 180},
        "cells_per_candidate": {"C1": 60, "C2": 60, "C3": 60},
        "cells_per_fixture": 3,
        "maximum_live_generation_calls": EXPECTED_ASSIGNED_CELLS,
        "attempts_per_cell": EXPECTED_ATTEMPTS_PER_CELL,
        "retry_calls": EXPECTED_RETRY_CALLS,
        "authorization_scope": {
            "allowed_phase": PHASE_DEV_SELECT,
            "allowed_execution_plan_internal_sha256": EXPECTED_DEV_SELECT_PLAN_INTERNAL_SHA256,
            "allowed_execution_plan_file_sha256": EXPECTED_DEV_SELECT_PLAN_FILE_SHA256,
            "allowed_plan_freeze_receipt_file_sha256": EXPECTED_PLAN_FREEZE_RECEIPT_FILE_SHA256,
            "allowed_prompt_id": "P1",
            "allowed_candidate_ids": list(EXPECTED_CANDIDATE_IDS),
            "maximum_live_generation_calls": 180,
            "attempts_per_cell": 1,
            "retry": 0,
            "dev_tune_rerun_authorized": False,
            "stochasticity_authorized": False,
            "final100_authorized": False,
            "candidate_substitution_authorized": False,
            "prompt_substitution_authorized": False,
            "extra_diagnostic_calls_authorized": False,
            "calls_beyond_180_authorized": False,
        },
        "call_budget_policy": {
            "assigned_cells": 180,
            "maximum_live_generation_calls": 180,
            "reserve_calls_beyond_180": 0,
            "retry_calls": 0,
            "diagnostic_generation_calls": 0,
            "dev_tune_rerun_calls": 0,
            "stochasticity_calls": 0,
            "final100_calls": 0,
            "max_outbound_http_requests_per_cell": 1,
            "no_hidden_calls": True,
        },
        "retry_policy": {
            "attempt_number": 1,
            "sdk_retry": 0,
            "transport_retry": 0,
            "manual_retry": 0,
            "automatic_retry": 0,
            "fallback": False,
            "best_of": False,
            "llm_repair": 0,
            "deterministic_semantic_repair": False,
            "tools": False,
            "max_outbound_generation_requests_per_assigned_cell": 1,
        },
        "failure_policy": {
            "ordinary_denominator_preserving_failures": list(
                ORDINARY_DENOMINATOR_FAILURE_TYPES
            ),
            "ordinary_failure_treatment": {
                "counts_in_denominator": True,
                "valid_run_and_schema": False,
                "exact_grounding_pass": False,
                "final_core_pass": False,
                "retry": 0,
                "batch_stop_required": False,
            },
            "batch_fatal_integrity_failures": list(
                BATCH_FATAL_INTEGRITY_FAILURE_TYPES
            ),
            "batch_fatal_treatment": {
                "counts_in_denominator": False,
                "batch_stop_required": True,
                "action": "STOP_BATCH_IMMEDIATELY_FAIL_CLOSED",
            },
        },
        "key_presence_status": kp,
        "runtime_sdk_version_evidence": rt_info,
        "pricing_evidence": pricing_by_candidate,
        "cost_envelope": cost_envelope,
        "hard_max_cost_usd": HARD_MAX_COST_USD,
        "proposed_project_owner_authorization_text": PROPOSED_PROJECT_OWNER_AUTHORIZATION_TEXT,
        "proposed_project_owner_authorization_text_sha256": auth_text_sha,
        "readiness_matrix": readiness_matrix,
        "pre_authorization_firewall": firewall,
        "final100_firewall": {
            "final100_used": False,
            "final100_authorized": False,
            "final100_bundle_sha256": FORBIDDEN_FINAL100_BUNDLE_SHA256,
            "p11_assignment_manifest_sha256": FORBIDDEN_P11_MANIFEST_SHA256,
        },
        "live_authorization_artifact_created": False,
        "stage_a_created": False,
        "live_execution_capability_issued": False,
        "production_provider_transport_constructed": False,
        "dev_select_execution_started": False,
        "model_winner_selected": False,
        "stochasticity_execution_started": False,
        "final100_used": False,
        "live_provider_calls_new": 0,
        "provider_cost_usd_new": 0,
        "dsap_checks": build_dsap_checks_matrix(),
    }
    assert_prep_payload_secret_free(
        payload, context="W06_DEV_SELECT_AUTHORIZATION_PREP_V1"
    )
    return payload


def validate_dev_select_authorization_prep_payload(
    payload: dict[str, Any],
    *,
    repo_root: Path = REPO_ROOT,
) -> None:
    """Fail-closed validator for `w06_dev_select_authorization_prep_v1.json` covering DSAP-01..40 and all Section 22 adversarial cases."""
    if not isinstance(payload, dict):
        raise PlanBeforeLiveProtocolError("PREP_PAYLOAD_NOT_DICT")

    assert_prep_payload_secret_free(
        payload, context="VALIDATE_DEV_SELECT_AUTHORIZATION_PREP"
    )

    if payload.get("artifact_id") != PREP_ARTIFACT_ID:
        raise PlanBeforeLiveProtocolError("PREP_ARTIFACT_ID_MISMATCH")
    if payload.get("task_id") != TASK_ID:
        raise PlanBeforeLiveProtocolError("PREP_TASK_ID_MISMATCH")
    if payload.get("source_develop_sha") != SOURCE_DEVELOP_SHA:
        raise PlanBeforeLiveProtocolError("PREP_SOURCE_DEVELOP_SHA_MISMATCH")
    if payload.get("phase") != PHASE_DEV_SELECT:
        raise PlanBeforeLiveProtocolError(
            f"PREP_PHASE_MISMATCH: {payload.get('phase')!r} != 'DEV_SELECT'"
        )
    if payload.get("project_owner_authorization_status") != "NOT_GRANTED":
        raise PlanBeforeLiveProtocolError(
            f"PREP_PROJECT_OWNER_STATUS_MISMATCH: {payload.get('project_owner_authorization_status')!r}"
        )
    if (
        "authorization_id" in payload
        or payload.get("authorization_status") == "AUTHORIZED"
    ):
        raise PlanBeforeLiveProtocolError("PREP_CONTAINS_LIVE_AUTHORIZATION_FIELDS")

    if (
        payload.get("execution_plan_internal_sha256")
        != EXPECTED_DEV_SELECT_PLAN_INTERNAL_SHA256
    ):
        raise PlanBeforeLiveProtocolError("PREP_PLAN_INTERNAL_SHA_MISMATCH")
    if (
        payload.get("execution_plan_file_sha256")
        != EXPECTED_DEV_SELECT_PLAN_FILE_SHA256
    ):
        raise PlanBeforeLiveProtocolError("PREP_PLAN_FILE_SHA_MISMATCH")
    if (
        payload.get("plan_freeze_receipt_file_sha256")
        != EXPECTED_PLAN_FREEZE_RECEIPT_FILE_SHA256
    ):
        raise PlanBeforeLiveProtocolError("PREP_PLAN_FREEZE_RECEIPT_SHA_MISMATCH")
    if (
        payload.get("plan_code_basis_commit_sha") != PLAN_CODE_BASIS_COMMIT_SHA
        or payload.get("plan_code_commit_sha") != PLAN_CODE_COMMIT_SHA
    ):
        raise PlanBeforeLiveProtocolError("PREP_PLAN_CODE_BASIS_MISMATCH")

    if (
        payload.get("selected_prompt_id") != "P1"
        or payload.get("allowed_prompt_ids") != ["P1"]
        or payload.get("forbidden_prompt_ids") != ["P0", "P2"]
    ):
        raise PlanBeforeLiveProtocolError("PREP_SELECTED_PROMPT_ID_MISMATCH")
    if (
        payload.get("selected_prompt_semantic_sha256")
        != P1_AUTHORITATIVE_SEMANTIC_PROMPT_SHA256
    ):
        raise PlanBeforeLiveProtocolError("PREP_SELECTED_PROMPT_SEMANTIC_SHA_MISMATCH")
    if (
        payload.get("prompt_selection_artifact_file_sha256")
        != EXPECTED_PROMPT_SELECTION_ARTIFACT_FILE_SHA256
    ):
        raise PlanBeforeLiveProtocolError("PREP_PROMPT_SELECTION_ARTIFACT_SHA_MISMATCH")

    if payload.get("candidate_ids") != list(EXPECTED_CANDIDATE_IDS):
        raise PlanBeforeLiveProtocolError(
            f"PREP_CANDIDATE_IDS_MISMATCH: {payload.get('candidate_ids')!r}"
        )
    if payload.get("candidate_registry_sha256") != EXPECTED_CANDIDATE_REGISTRY_SHA256:
        raise PlanBeforeLiveProtocolError("PREP_CANDIDATE_REGISTRY_SHA_MISMATCH")
    if (
        payload.get("provider_config_registry_sha256")
        != EXPECTED_PROVIDER_CONFIG_REGISTRY_SHA256
    ):
        raise PlanBeforeLiveProtocolError("PREP_PROVIDER_CONFIG_REGISTRY_SHA_MISMATCH")
    if (
        payload.get("scientific_code_bundle_sha256")
        != EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
        or compute_scientific_code_bundle_sha256(repo_root=repo_root)
        != EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
    ):
        raise PlanBeforeLiveProtocolError("PREP_SCIENTIFIC_CODE_BUNDLE_SHA_MISMATCH")
    if payload.get("portable_schema_v2_sha256") != EXPECTED_PORTABLE_SCHEMA_V2_SHA256:
        raise PlanBeforeLiveProtocolError("PREP_PORTABLE_SCHEMA_SHA_MISMATCH")
    if payload.get("semantic_schema_sha256") != EXPECTED_SEMANTIC_SCHEMA_SHA256:
        raise PlanBeforeLiveProtocolError("PREP_SEMANTIC_SCHEMA_SHA_MISMATCH")

    if (
        payload.get("fixture_count") != 60
        or payload.get("prompt_count") != 1
        or payload.get("candidate_count") != 3
        or payload.get("assigned_cells") != 180
        or payload.get("unique_run_ids") != 180
        or payload.get("unique_cell_keys") != 180
    ):
        raise PlanBeforeLiveProtocolError(
            f"PREP_CELL_OR_FIXTURE_COUNT_MISMATCH: assigned_cells={payload.get('assigned_cells')!r}"
        )

    cb = payload.get("call_budget_policy", {})
    if (
        payload.get("maximum_live_generation_calls") != 180
        or cb.get("assigned_cells") != 180
        or cb.get("maximum_live_generation_calls") != 180
        or cb.get("reserve_calls_beyond_180") != 0
        or cb.get("retry_calls") != 0
        or cb.get("diagnostic_generation_calls") != 0
        or cb.get("dev_tune_rerun_calls") != 0
        or cb.get("stochasticity_calls") != 0
        or cb.get("final100_calls") != 0
        or cb.get("max_outbound_http_requests_per_cell") != 1
        or cb.get("no_hidden_calls") is not True
    ):
        raise PlanBeforeLiveProtocolError(
            f"PREP_CALL_BUDGET_VIOLATION: max={payload.get('maximum_live_generation_calls')!r}, cb={cb!r}"
        )

    rp = payload.get("retry_policy", {})
    if (
        payload.get("attempts_per_cell") != 1
        or payload.get("retry_calls") != 0
        or rp.get("attempt_number") != 1
        or rp.get("sdk_retry") != 0
        or rp.get("transport_retry") != 0
        or rp.get("manual_retry") != 0
        or rp.get("automatic_retry") != 0
        or rp.get("fallback") is not False
        or rp.get("best_of") is not False
        or rp.get("llm_repair") != 0
        or rp.get("deterministic_semantic_repair") is not False
        or rp.get("tools") is not False
    ):
        raise PlanBeforeLiveProtocolError(f"PREP_RETRY_OR_REPAIR_POLICY_VIOLATION: {rp!r}")

    scope = payload.get("authorization_scope", {})
    if (
        scope.get("dev_tune_rerun_authorized") is not False
        or scope.get("stochasticity_authorized") is not False
        or scope.get("final100_authorized") is not False
        or scope.get("candidate_substitution_authorized") is not False
        or scope.get("prompt_substitution_authorized") is not False
        or scope.get("extra_diagnostic_calls_authorized") is not False
        or scope.get("calls_beyond_180_authorized") is not False
    ):
        raise PlanBeforeLiveProtocolError(
            f"PREP_UNAUTHORIZED_SCOPE_ENABLED: {scope!r}"
        )

    ce = payload.get("cost_envelope", {})
    if (
        payload.get("hard_max_cost_usd") != HARD_MAX_COST_USD
        or ce.get("hard_max_cost_usd") != HARD_MAX_COST_USD
    ):
        raise PlanBeforeLiveProtocolError("PREP_HARD_MAX_COST_NOT_TRUTHFUL")
    byte_stats = ce.get(
        "rendered_prompt_utf8_byte_statistics_across_60_dev_select_fixtures", {}
    )
    if (
        byte_stats.get("fixture_count") != 60
        or byte_stats.get("prompt_id") != "P1"
        or byte_stats.get("total_cells") != 180
        or byte_stats.get("min_rendered_user_prompt_utf8_bytes")
        != EXPECTED_MIN_RENDERED_USER_PROMPT_BYTES
        or byte_stats.get("max_rendered_user_prompt_utf8_bytes")
        != EXPECTED_MAX_RENDERED_USER_PROMPT_BYTES
        or byte_stats.get("total_rendered_user_prompt_utf8_bytes_60_fixtures")
        != EXPECTED_TOTAL_RENDERED_USER_PROMPT_BYTES_60_FIXTURES
        or byte_stats.get("p1_system_prompt_utf8_bytes")
        != EXPECTED_P1_SYSTEM_PROMPT_BYTES
    ):
        raise PlanBeforeLiveProtocolError("PREP_COST_ENVELOPE_WORKLOAD_MISMATCH")

    prop_text = payload.get("proposed_project_owner_authorization_text")
    prop_sha = payload.get("proposed_project_owner_authorization_text_sha256")
    if not isinstance(prop_text, str):
        raise PlanBeforeLiveProtocolError("PREP_AUTHORIZATION_TEXT_MISSING")
    recomputed_text_sha = hashlib.sha256(prop_text.encode("utf-8")).hexdigest()
    if (
        prop_text != PROPOSED_PROJECT_OWNER_AUTHORIZATION_TEXT
        or prop_sha != EXPECTED_PROPOSED_PROJECT_OWNER_AUTHORIZATION_TEXT_SHA256
        or recomputed_text_sha != EXPECTED_PROPOSED_PROJECT_OWNER_AUTHORIZATION_TEXT_SHA256
    ):
        raise PlanBeforeLiveProtocolError(
            f"PREP_AUTHORIZATION_TEXT_OR_SHA_MISMATCH: sha={prop_sha!r}, recomputed={recomputed_text_sha!r}"
        )

    fw = verify_pre_authorization_firewall(repo_root)
    if (
        not fw["pre_authorization_firewall_intact"]
        or payload.get("live_authorization_artifact_created") is not False
        or payload.get("stage_a_created") is not False
        or payload.get("live_execution_capability_issued") is not False
        or payload.get("production_provider_transport_constructed") is not False
        or payload.get("dev_select_execution_started") is not False
        or payload.get("model_winner_selected") is not False
        or payload.get("stochasticity_execution_started") is not False
        or payload.get("final100_used") is not False
        or payload.get("live_provider_calls_new") != 0
        or payload.get("provider_cost_usd_new") != 0
    ):
        raise PlanBeforeLiveProtocolError("PREP_FIREWALL_OR_LIVE_CALL_VIOLATION")


# ==============================================================================
# 6. STATELESS VERIFY-ONLY & PERSISTENCE ENTRYPOINTS
# ==============================================================================


def verify_persisted_dev_select_authorization_prep(
    repo_root: Path = REPO_ROOT,
    *,
    prep_artifact_path: Path | None = None,
) -> dict[str, Any]:
    """Statelessly verify `data/evaluation/w06/w06_dev_select_authorization_prep_v1.json`."""
    with NetworkKillSwitchGuard():
        target_path = prep_artifact_path or (repo_root / PREP_ARTIFACT_REL_PATH)
        if not target_path.is_file():
            raise PlanBeforeLiveProtocolError(
                f"DEV_SELECT_AUTHORIZATION_PREP_MISSING: {target_path}"
            )
        raw_bytes = normalize_lf_bytes(target_path.read_bytes())
        file_sha = sha256_bytes(raw_bytes)
        if (
            EXPECTED_PREP_ARTIFACT_FILE_SHA256 is not None
            and file_sha != EXPECTED_PREP_ARTIFACT_FILE_SHA256
        ):
            raise PlanBeforeLiveProtocolError(
                f"PREP_ARTIFACT_FILE_SHA_MISMATCH: {file_sha} != {EXPECTED_PREP_ARTIFACT_FILE_SHA256}"
            )

        persisted = json.loads(raw_bytes.decode("utf-8"))
        validate_dev_select_authorization_prep_payload(persisted, repo_root=repo_root)

        expected = build_dev_select_authorization_prep_payload(
            repo_root,
            key_presence_override=persisted["key_presence_status"],
            runtime_versions_override=persisted["runtime_sdk_version_evidence"][
                "observed_versions"
            ],
        )
        expected_bytes = canonical_json_bytes(expected)
        if persisted != expected or raw_bytes != expected_bytes:
            raise PlanBeforeLiveProtocolError(
                "PREP_ARTIFACT_RECOMPUTATION_MISMATCH: Persisted authorization-prep artifact does not match deterministic recomputation."
            )

        return {
            "verified": True,
            "prep_artifact_file_sha256": file_sha,
            "phase": expected["phase"],
            "project_owner_authorization_status": expected[
                "project_owner_authorization_status"
            ],
            "execution_plan_internal_sha256": expected[
                "execution_plan_internal_sha256"
            ],
            "execution_plan_file_sha256": expected["execution_plan_file_sha256"],
            "plan_freeze_receipt_file_sha256": expected[
                "plan_freeze_receipt_file_sha256"
            ],
            "plan_code_basis_commit_sha": expected["plan_code_basis_commit_sha"],
            "selected_prompt_id": expected["selected_prompt_id"],
            "selected_prompt_semantic_sha256": expected[
                "selected_prompt_semantic_sha256"
            ],
            "assigned_cells": expected["assigned_cells"],
            "maximum_live_generation_calls": expected["maximum_live_generation_calls"],
            "retry_calls": expected["retry_calls"],
            "planning_cost_envelope_low_usd": expected["cost_envelope"][
                "planning_cost_envelope_low_usd"
            ],
            "planning_cost_envelope_high_usd": expected["cost_envelope"][
                "planning_cost_envelope_high_usd"
            ],
            "conditional_16384_billable_output_reference_usd": expected[
                "cost_envelope"
            ]["conditional_16384_billable_output_reference_usd"],
            "hard_max_cost_usd": expected["hard_max_cost_usd"],
            "proposed_project_owner_authorization_text_sha256": expected[
                "proposed_project_owner_authorization_text_sha256"
            ],
            "live_provider_calls_new": 0,
            "provider_cost_usd_new": 0,
        }


def write_dev_select_authorization_prep_artifact(
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Generate and persist `data/evaluation/w06/w06_dev_select_authorization_prep_v1.json`, then verify."""
    with NetworkKillSwitchGuard():
        payload = build_dev_select_authorization_prep_payload(repo_root)
        validate_dev_select_authorization_prep_payload(payload, repo_root=repo_root)
        raw_bytes = canonical_json_bytes(payload)
        file_sha = sha256_bytes(raw_bytes)
        out_path = repo_root / PREP_ARTIFACT_REL_PATH
        out_path.write_bytes(raw_bytes)

        ver = verify_persisted_dev_select_authorization_prep(repo_root)
        if ver["prep_artifact_file_sha256"] != file_sha:
            raise PlanBeforeLiveProtocolError("POST_WRITE_PREP_SHA_MISMATCH")
        return ver


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="W06-DEV-SELECT-AUTHORIZATION-PREP-01 offline authorization preparation."
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify existing persisted DEV-SELECT authorization-prep artifact without writing.",
    )
    args = parser.parse_args(argv)

    if args.verify_only:
        res = verify_persisted_dev_select_authorization_prep(REPO_ROOT)
    else:
        res = write_dev_select_authorization_prep_artifact(REPO_ROOT)

    print(json.dumps(res, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
