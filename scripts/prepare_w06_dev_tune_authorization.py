#!/usr/bin/env python3
"""Offline preparation script for W06-DEV-TUNE-LIVE-AUTHORIZATION-PREP-01.

Strictly offline:
- Installs an outbound network kill-switch blocking socket, urllib, httpx, and httpx2.
- Never reads or prints or hashes secret key values; checks key presence ONLY as PRESENT / MISSING.
- Verifies all frozen DEV-TUNE authorities, prompt freeze, 120-cell execution plan, and 14-file scientific bundle.
- Prepares execution policy, failure policy, call-budget policy, cost envelope, pricing evidence,
  live readiness matrix, and proposed Project Owner authorization text.
- Enforces the Pre-Authorization Firewall:
  NEVER creates DevLiveAuthorizationArtifact, Stage-A freeze receipt, LiveExecutionCapability,
  transport journals, or live cell result directories.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import socket
import subprocess
import sys
import urllib.request
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterator

import httpx
import httpx2

REPO_ROOT = Path(__file__).resolve().parents[1]
AI_SERVICE_ROOT = REPO_ROOT / "apps" / "ai-service"
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import freeze_w06_dev_prompt_candidates as pf_mod  # noqa: E402
from app.evaluation.dev_live_runner import (  # noqa: E402
    CANDIDATE_ENV_KEY_BY_ID,
    CANDIDATE_MODEL_BY_ID,
    CANDIDATE_PROVIDER_BY_ID,
    DEFAULT_COST_COMPARABILITY_BY_CANDIDATE,
    DEFAULT_RUNNER_RECEIPT_PATH,
    assert_no_secrets_in_payload,
    verify_runner_prompt_freeze_artifact,
)
from app.evaluation.dev_selection_harness import (  # noqa: E402
    BATCH_STOP_FAILURE_CLASSIFICATIONS,
    DEV_SELECT_COUNT,
    DEV_TOTAL_COUNT,
    DEV_TUNE_COUNT,
    DEV_TUNE_MAX_CALLS_TWO_PROMPTS,
    EXPECTED_FROZEN_AUTHORITY_SHAS_DEV_HARNESS,
    EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
    EXPECTED_SEMANTIC_SCHEMA_SHA256,
    FORBIDDEN_FINAL100_BUNDLE_SHA256,
    FORBIDDEN_P11_MANIFEST_SHA256,
    FROZEN_MAX_OUTPUT_TOKENS,
    FROZEN_TIMEOUT_MS,
    ORDERED_CANDIDATE_IDS,
    ORDINARY_DENOMINATOR_FAILURE_CLASSIFICATIONS,
    SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS,
    CandidateCostComparabilityRecord,
    DevExecutionPlan,
    DevPromptFreezeArtifact,
    canonical_json_bytes,
    compute_canonical_cell_cost_decimal,
    compute_provider_config_registry_sha256,
    compute_scientific_code_bundle_file_hashes,
    compute_scientific_code_bundle_sha256,
    get_cached_provider_config_sha256,
    load_and_verify_candidate_registry,
    load_and_verify_frozen_dev_bundle,
    normalize_lf_bytes,
    sha256_bytes,
    verify_dev_execution_plan_for_execution,
    verify_prompt_candidate_freeze_artifact,
)

# ==============================================================================
# 1. FROZEN AUTHORITIES & CONSTANTS
# ==============================================================================

TASK_ID = "W06-DEV-TUNE-LIVE-AUTHORIZATION-PREP-01"
PREPARATION_ARTIFACT_ID = "W06-DEV-TUNE-AUTHORIZATION-PREP-01-V1"
PREPARATION_ARTIFACT_VERSION = "1.0.0"

SOURCE_DEVELOP_SHA = "443634e1f7583f334dec0315bb3816d249feb124"
CODE_BASIS_COMMIT_SHA = "60d52d720e66f5af8e82fabf9cebe2ea0e8a9e26"

PHASE_BEING_PREPARED = "DEV_TUNE"

EXPECTED_PROMPT_FREEZE_SHA256 = (
    "2f345363f580ea882b2e5b3562c587ef5309bc7f994440257a54d18994ab6956"
)
EXPECTED_DEV_TUNE_PLAN_SHA256 = (
    "582d9964b4fffbac91f83373d080f1fef120f0ddca4edab2d63e02796d0b20ae"
)
EXPECTED_DEV_TUNE_PLAN_FILE_SHA256 = (
    "652e3beb08771c3125e613172b1aaa396fc1b60aaaf3b98cc238e91a14e0dc74"
)
EXPECTED_PROMPT_REGISTRY_SHA256 = (
    "846dc4c14ec2a87537b7b3e07bf492de51dc534d24b21e469094b7e3d34d32b6"
)
EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256 = (
    "0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3"
)
EXPECTED_P1_SEMANTIC_PROMPT_SHA256 = (
    "096ff4c74dd8d1aed1c0abe501b97c8dfd0f6424dbca535f2b79a242637a1c11"
)
EXPECTED_P2_SEMANTIC_PROMPT_SHA256 = (
    "0679dd9463d6cebf04ccb5571a403331eea3ab6819bd6a0e8b2ee1fc08c99fdf"
)
P2_CANDIDATE_DEFINITION_ID = "W06_DEV_TUNE_CANDIDATE_P2_V1"

PROMPT_FREEZE_REL_PATH = "data/evaluation/w06/w06_dev_prompt_candidate_freeze_v1.json"
DEV_TUNE_PLAN_REL_PATH = "data/evaluation/w06/w06_dev_tune_execution_plan_v1.json"
PREP_ARTIFACT_REL_PATH = "data/evaluation/w06/w06_dev_tune_authorization_prep_v1.json"
PREP_REPORT_REL_PATH = "docs/research/w06_dev_tune_authorization_prep_01.md"
RUNNER_QA_RECEIPT_REL_PATH = (
    "data/evaluation/w06/w06_dev_live_runner_qa_01_receipt_v1.json"
)
PREFLIGHT_01D_RECEIPT_REL_PATH = (
    "data/evaluation/w06/w06_model_preflight_01d_v2_live_receipt_v1.json"
)
FORBIDDEN_FINAL100_SCENARIOS_REL_PATH = (
    "data/evaluation/w06/w06_scenarios_freeze_v1.json"
)
FORBIDDEN_P11_MANIFEST_REL_PATH = (
    "data/evaluation/w06/w06_p11_assignment_manifest_v1.json"
)

PROJECT_OWNER_AUTHORIZATION_STATUS = "NOT_GRANTED"

PROPOSED_OWNER_AUTHORIZATION_TEXT = (
    f"I authorize W06 DEV-TUNE live execution for exactly the frozen "
    f"120-cell plan {EXPECTED_DEV_TUNE_PLAN_SHA256}, using frozen prompt artifact "
    f"{EXPECTED_PROMPT_FREEZE_SHA256}, candidates C1/C2/C3, maximum 120 generation calls, "
    f"zero retry, no DEV-SELECT, no stochasticity, and no Final100."
)

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
    "PROMPT_FREEZE_INTEGRITY_FAILURE",
    "EXECUTION_PLAN_INTEGRITY_FAILURE",
    "AUTHORIZATION_INTEGRITY_FAILURE",
    "STAGE_A_INTEGRITY_FAILURE",
)

REQUIRED_ENV_KEYS: tuple[str, str, str] = (
    "GEMINI_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
)


# ==============================================================================
# 2. NETWORK KILL SWITCH & KEY PRESENCE CHECKER (NO SECRET VALUES READ/STORED)
# ==============================================================================


class OutboundNetworkBlockedError(RuntimeError):
    """Raised if any code attempts an outbound network connection during offline authorization prep."""


class NetworkKillSwitchGuard:
    """Context manager blocking all socket, urllib, httpx, and httpx2 outbound calls."""

    def __init__(self) -> None:
        self.blocked_attempts: list[str] = []

    @contextlib.contextmanager
    def activate(self) -> Iterator["NetworkKillSwitchGuard"]:
        orig_connect = socket.socket.connect
        orig_connect_ex = socket.socket.connect_ex
        orig_create_conn = socket.create_connection
        orig_urlopen = urllib.request.urlopen
        orig_httpx_send = httpx.Client.send
        orig_httpx_async_send = httpx.AsyncClient.send
        orig_httpx2_send = httpx2.Client.send
        orig_httpx2_async_send = httpx2.AsyncClient.send

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
        try:
            yield self
        finally:
            socket.socket.connect = orig_connect  # type: ignore[method-assign]
            socket.socket.connect_ex = orig_connect_ex  # type: ignore[method-assign]
            socket.create_connection = orig_create_conn  # type: ignore[assignment]
            urllib.request.urlopen = orig_urlopen  # type: ignore[assignment]
            httpx.Client.send = orig_httpx_send  # type: ignore[method-assign]
            httpx.AsyncClient.send = orig_httpx_async_send  # type: ignore[method-assign]
            httpx2.Client.send = orig_httpx2_send  # type: ignore[method-assign]
            httpx2.AsyncClient.send = orig_httpx2_async_send  # type: ignore[method-assign]


def check_key_presence_status_only(
    repo_root: Path = REPO_ROOT,
    *,
    env_override: dict[str, str] | None = None,
    include_dotenv_files: bool = True,
) -> dict[str, str]:
    """Return ONLY 'PRESENT' or 'MISSING' for GEMINI_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY.

    Never prints, hashes, or returns key values. Does not fail if .env is absent.
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


def verify_source_develop_commit_or_shallow_fallback(
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Verify SOURCE_DEVELOP_SHA exists and is ancestor of HEAD, with shallow-clone fallback for CI."""
    exists_proc = subprocess.run(
        ["git", "cat-file", "-e", f"{SOURCE_DEVELOP_SHA}^{{commit}}"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    commit_exists = exists_proc.returncode == 0
    if commit_exists:
        anc_proc = subprocess.run(
            ["git", "merge-base", "--is-ancestor", SOURCE_DEVELOP_SHA, "HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        is_ancestor = anc_proc.returncode == 0
        return {
            "source_develop_sha": SOURCE_DEVELOP_SHA,
            "commit_exists_in_local_git": True,
            "is_ancestor_of_head": is_ancestor,
            "shallow_repository_fallback_used": False,
            "verified": is_ancestor,
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
    bundle_sha = compute_scientific_code_bundle_sha256(repo_root=repo_root)
    pf_sha = sha256_bytes(
        normalize_lf_bytes((repo_root / PROMPT_FREEZE_REL_PATH).read_bytes())
    )
    plan_file_sha = sha256_bytes(
        normalize_lf_bytes((repo_root / DEV_TUNE_PLAN_REL_PATH).read_bytes())
    )
    fallback_ok = (
        is_shallow
        and bundle_sha == EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
        and pf_sha == EXPECTED_PROMPT_FREEZE_SHA256
        and plan_file_sha == EXPECTED_DEV_TUNE_PLAN_FILE_SHA256
    )
    return {
        "source_develop_sha": SOURCE_DEVELOP_SHA,
        "commit_exists_in_local_git": False,
        "is_ancestor_of_head": fallback_ok,
        "shallow_repository_fallback_used": True,
        "verified": fallback_ok,
    }


# ==============================================================================
# 3. PRICING EVIDENCE & CONSERVATIVE COST ENVELOPE (SECTIONS 8 & 9)
# ==============================================================================


def build_pricing_evidence_and_cost_envelope(
    repo_root: Path = REPO_ROOT,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build candidate-aware pricing evidence and truthful cost envelope without calling provider APIs."""
    receipt_01d_path = repo_root / PREFLIGHT_01D_RECEIPT_REL_PATH
    receipt_01d = json.loads(
        normalize_lf_bytes(receipt_01d_path.read_bytes()).decode("utf-8")
    )
    c_01d = receipt_01d["candidates"]

    plan_path = repo_root / DEV_TUNE_PLAN_REL_PATH
    plan = DevExecutionPlan.model_validate_json(
        normalize_lf_bytes(plan_path.read_bytes())
    )
    dev_bundle = load_and_verify_frozen_dev_bundle()
    registry = pf_mod.build_frozen_p1_p2_registry()
    p1 = registry.prompts[0]
    p2 = registry.prompts[1]

    # Measure exact UTF-8 byte lengths of rendered user prompts across the 20 DEV-TUNE fixtures
    from app.evaluation.dev_selection_harness import (
        build_destination_catalog_context,
        build_deterministic_dev_scenario_context,
    )

    preloaded_catalog_by_dest = {
        dest: build_destination_catalog_context(dest)
        for dest in {sc.destination_slug for sc in dev_bundle.dev_tune_fixtures}
    }
    rendered_user_utf8_bytes_per_fixture: list[int] = []
    for scenario in dev_bundle.dev_tune_fixtures:
        ctx_p1 = build_deterministic_dev_scenario_context(
            scenario, p1, preloaded_catalog_by_dest=preloaded_catalog_by_dest
        )
        rendered_user_utf8_bytes_per_fixture.append(
            len(ctx_p1.user_prompt.encode("utf-8"))
        )

    total_rendered_user_bytes_20_fixtures = sum(rendered_user_utf8_bytes_per_fixture)
    min_user_bytes = min(rendered_user_utf8_bytes_per_fixture)
    max_user_bytes = max(rendered_user_utf8_bytes_per_fixture)
    p1_sys_bytes = len(p1.system_prompt.encode("utf-8"))
    p2_sys_bytes = len(p2.system_prompt.encode("utf-8"))

    # Pricing authorities recorded in frozen repository artifacts:
    # 1. Phase 01D live receipt (data/evaluation/w06/w06_model_preflight_01d_v2_live_receipt_v1.json, checked 2026-10-17)
    # 2. Runner DEFAULT_COST_COMPARABILITY_BY_CANDIDATE (apps/ai-service/app/evaluation/dev_live_runner.py, checked 2026-10-16)
    pricing_by_candidate: dict[str, Any] = {
        "C1": {
            "candidate_id": "C1",
            "provider": "google",
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
            "preflight_01d_observed_smoke_call": {
                "input_tokens": c_01d["C1"]["usage_metadata"]["input_tokens"],
                "output_tokens": c_01d["C1"]["usage_metadata"]["output_tokens"],
                "thought_tokens": c_01d["C1"]["usage_metadata"]["thought_tokens"],
                "total_tokens": c_01d["C1"]["usage_metadata"]["total_tokens"],
                "observed_cost_usd_01d_basis": c_01d["C1"][
                    "estimated_standard_api_cost_usd"
                ],
            },
        },
        "C2": {
            "candidate_id": "C2",
            "provider": "openai",
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
            "preflight_01d_observed_smoke_call": {
                "input_tokens": c_01d["C2"]["usage_metadata"]["input_tokens"],
                "output_tokens": c_01d["C2"]["usage_metadata"]["output_tokens"],
                "reasoning_tokens": c_01d["C2"]["usage_metadata"]["reasoning_tokens"],
                "total_tokens": c_01d["C2"]["usage_metadata"]["total_tokens"],
                "observed_cost_usd_01d_basis": c_01d["C2"][
                    "estimated_standard_api_cost_usd"
                ],
            },
        },
        "C3": {
            "candidate_id": "C3",
            "provider": "anthropic",
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
            "preflight_01d_observed_smoke_call": {
                "input_tokens": c_01d["C3"]["usage_metadata"]["input_tokens"],
                "output_tokens": c_01d["C3"]["usage_metadata"]["output_tokens"],
                "total_tokens": c_01d["C3"]["usage_metadata"]["total_tokens"],
                "observed_cost_usd_01d_basis": c_01d["C3"][
                    "estimated_standard_api_cost_usd"
                ],
            },
        },
    }

    # Compute conservative expected planning range using compute_canonical_cell_cost_decimal
    # without claiming a false-precision single point estimate or an unconditional hard max.
    # For each candidate (40 cells = 20 fixtures x 2 prompts):
    # - Expected/typical per-cell usage on full destination catalog: ~8,000 to 14,000 input tokens, ~2,500 to 5,000 billable output+thinking tokens.
    # - Conditional full-cap reference (if every cell hit 16,384 billable output tokens + 18,000 input tokens).
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
        # Low typical: 8,000 input tokens, 2,500 billable output tokens per cell x 40 cells
        c_low_cell = compute_canonical_cell_cost_decimal(
            input_tokens=8000,
            output_tokens=2500,
            thought_tokens=0,
            cost_record=rec,
        )
        # High typical: 14,000 input tokens, 5,500 billable output tokens per cell x 40 cells
        c_high_cell = compute_canonical_cell_cost_decimal(
            input_tokens=14000,
            output_tokens=5500,
            thought_tokens=0,
            cost_record=rec,
        )
        # Conditional cap reference: 18,000 input tokens, 16,384 billable output tokens per cell x 40 cells
        c_cap_cell = compute_canonical_cell_cost_decimal(
            input_tokens=18000,
            output_tokens=FROZEN_MAX_OUTPUT_TOKENS,
            thought_tokens=0,
            cost_record=rec,
        )
        assert (
            c_low_cell is not None and c_high_cell is not None and c_cap_cell is not None
        )
        c_low_40 = c_low_cell * Decimal(40)
        c_high_40 = c_high_cell * Decimal(40)
        c_cap_40 = c_cap_cell * Decimal(40)
        low_expected_total += c_low_40
        high_expected_total += c_high_40
        conditional_cap_reference_total += c_cap_40
        per_candidate_envelope[cid] = {
            "cells_in_dev_tune": 40,
            "conservative_input_price_per_1m_usd": rec.input_price_per_million_usd,
            "conservative_output_price_per_1m_usd": rec.output_price_per_million_usd,
            "estimated_expected_range_40_cells_usd": {
                "low_usd": round(float(c_low_40), 4),
                "high_usd": round(float(c_high_40), 4),
            },
            "conditional_16384_billable_output_cap_reference_40_cells_usd": round(
                float(c_cap_40), 4
            ),
        }

    cost_envelope = {
        "cost_estimation_policy": "CONSERVATIVE_PLANNING_RANGE_NO_FALSE_PRECISION",
        "dev_tune_uses_cost_for_prompt_selection": False,
        "estimated_expected_cost_usd": {
            "status": "CONSERVATIVE_AUTHORIZATION_PLANNING_RANGE",
            "range_usd": f"${float(low_expected_total):.2f} - ${float(high_expected_total):.2f} USD",
            "low_expected_usd": round(float(low_expected_total), 2),
            "high_expected_usd": round(float(high_expected_total), 2),
            "assumptions": (
                "40 cells per candidate (120 cells total, retry=0), using the elementwise maximum of "
                "Phase 01D live receipt pricing (2026-10-17) and Runner DEFAULT_COST_COMPARABILITY_BY_CANDIDATE (2026-10-16), "
                "with 8,000-14,000 input tokens and 2,500-5,500 billable output+thinking tokens per cell."
            ),
        },
        "hard_max_cost_usd": "NOT_DEFENSIBLY_COMPUTABLE",
        "hard_max_cost_explanation": (
            "Exact pre-execution token counts require provider-proprietary tokenizers (which cannot be called offline) "
            "and provider-internal structured-output grammar injection into input_tokens; furthermore, in C1 (Google gemini-3.8-flash) "
            "thoughts_token_count is billed disjointly from candidates_token_count (billable_output_tokens = output_tokens + thought_tokens). "
            "Therefore an unconditional deterministic HARD_MAX_COST is marked NOT_DEFENSIBLY_COMPUTABLE to prevent false precision."
        ),
        "conditional_16384_billable_output_cap_reference_120_cells_usd": round(
            float(conditional_cap_reference_total), 2
        ),
        "rendered_prompt_utf8_byte_statistics_across_20_fixtures": {
            "fixture_count": len(dev_bundle.dev_tune_fixtures),
            "total_cells": len(plan.cells),
            "p1_system_prompt_utf8_bytes": p1_sys_bytes,
            "p2_system_prompt_utf8_bytes": p2_sys_bytes,
            "min_rendered_user_prompt_utf8_bytes": min_user_bytes,
            "max_rendered_user_prompt_utf8_bytes": max_user_bytes,
            "sum_rendered_user_prompt_utf8_bytes_20_fixtures": total_rendered_user_bytes_20_fixtures,
        },
        "per_candidate_conservative_envelope": per_candidate_envelope,
    }
    return pricing_by_candidate, cost_envelope


# ==============================================================================
# 4. PRE-AUTHORIZATION FIREWALL & LIVE READINESS MATRIX (SECTIONS 11, 12, 13)
# ==============================================================================


def verify_pre_authorization_firewall(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Verify that zero live authorization artifacts, Stage-A receipts, transport journals, or live cell outputs exist."""
    w06_dir = repo_root / "data" / "evaluation" / "w06"
    forbidden_auth_files: list[str] = []
    forbidden_stage_a_files: list[str] = []
    forbidden_transport_journals: list[str] = []
    forbidden_live_cell_dirs: list[str] = []

    if w06_dir.is_dir():
        from freeze_w06_dev_tune_stage_a import (
            is_verified_downstream_w06_dev_tune_stage_a_file,
        )
        from issue_w06_dev_tune_live_authorization import (
            is_verified_downstream_w06_dev_tune_authorization_file,
        )

        for path in sorted(w06_dir.rglob("*")):
            rel = path.relative_to(repo_root).as_posix()
            name_lower = path.name.lower()
            if path.is_file():
                is_verified_downstream_auth01 = (
                    is_verified_downstream_w06_dev_tune_authorization_file(
                        path, repo_root=repo_root
                    )
                )
                is_verified_downstream_stage_a = (
                    is_verified_downstream_w06_dev_tune_stage_a_file(
                        path, repo_root=repo_root
                    )
                )
                if (
                    (
                        "stage_a" in name_lower
                        or "stage-a" in name_lower
                        or name_lower == "stage_a_freeze_receipt.json"
                    )
                    and not is_verified_downstream_stage_a
                ):
                    forbidden_stage_a_files.append(rel)
                if "transport_journal" in name_lower:
                    forbidden_transport_journals.append(rel)
                if (
                    "live_authorization" in name_lower
                    and name_lower != "w06_dev_tune_authorization_prep_v1.json"
                    and not is_verified_downstream_auth01
                ):
                    forbidden_auth_files.append(rel)
                # Also inspect JSON files in w06_dir root for DevLiveAuthorizationArtifact or DevLiveStageAFreezeReceipt signatures
                if path.suffix.lower() == ".json" and path.parent == w06_dir:
                    try:
                        data = json.loads(path.read_text(encoding="utf-8"))
                        if isinstance(data, dict):
                            if (
                                (
                                    "authorization_id" in data
                                    or data.get("authorization_status") == "AUTHORIZED"
                                )
                                and not is_verified_downstream_auth01
                            ):
                                forbidden_auth_files.append(rel)
                            if (
                                (
                                    data.get("artifact_id")
                                    == "W06-DEV-LIVE-STAGE-A-FREEZE-RECEIPT-V1"
                                    or "stage_a_process_token" in data
                                )
                                and not is_verified_downstream_stage_a
                            ):
                                forbidden_stage_a_files.append(rel)
                    except Exception:
                        pass
            elif path.is_dir():
                if any(
                    tok in name_lower
                    for tok in (
                        "dev_tune_live",
                        "dev_select_live",
                        "stochasticity_live",
                        "live_runs",
                        "cell_outputs",
                    )
                ):
                    forbidden_live_cell_dirs.append(rel)

    firewall_clean = (
        len(forbidden_auth_files) == 0
        and len(forbidden_stage_a_files) == 0
        and len(forbidden_transport_journals) == 0
        and len(forbidden_live_cell_dirs) == 0
    )
    return {
        "live_authorization_artifact_created": len(forbidden_auth_files) > 0,
        "stage_a_receipt_created": len(forbidden_stage_a_files) > 0,
        "live_execution_capability_minted": False,
        "transport_journal_created": len(forbidden_transport_journals) > 0,
        "provider_result_directories_created": len(forbidden_live_cell_dirs) > 0,
        "model_output_artifacts_created": False,
        "forbidden_auth_files": forbidden_auth_files,
        "forbidden_stage_a_files": forbidden_stage_a_files,
        "forbidden_transport_journals": forbidden_transport_journals,
        "forbidden_live_cell_dirs": forbidden_live_cell_dirs,
        "pre_authorization_firewall_intact": firewall_clean,
    }


def build_live_readiness_matrix(
    repo_root: Path = REPO_ROOT,
    *,
    key_presence: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build Section 11 Live Readiness Matrix."""
    kp = (
        key_presence
        if key_presence is not None
        else check_key_presence_status_only(repo_root)
    )
    dev_bundle = load_and_verify_frozen_dev_bundle()
    cand_reg = load_and_verify_candidate_registry()
    prompt_reg = pf_mod.build_frozen_p1_p2_registry()

    pf_path = repo_root / PROMPT_FREEZE_REL_PATH
    plan_path = repo_root / DEV_TUNE_PLAN_REL_PATH
    runner_qa_path = repo_root / RUNNER_QA_RECEIPT_REL_PATH

    pf_sha = sha256_bytes(normalize_lf_bytes(pf_path.read_bytes()))
    plan_file_sha = sha256_bytes(normalize_lf_bytes(plan_path.read_bytes()))
    plan_model = DevExecutionPlan.model_validate_json(
        normalize_lf_bytes(plan_path.read_bytes())
    )

    verify_dev_execution_plan_for_execution(
        plan_model, candidate_registry=cand_reg, repo_root=repo_root
    )
    verify_prompt_candidate_freeze_artifact(
        pf_path,
        prompt_registry=prompt_reg,
        dev_tune_plan=plan_model,
        dev_bundle=dev_bundle,
        candidate_registry=cand_reg,
        repo_root=repo_root,
    )
    verify_runner_prompt_freeze_artifact(
        pf_path,
        prompt_registry=prompt_reg,
        execution_plan=plan_model,
        dev_bundle=dev_bundle,
        candidate_registry=cand_reg,
        repo_root=repo_root,
    )

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
    pconf_reg_sha = compute_provider_config_registry_sha256(cand_reg)

    final100_sha = sha256_bytes(
        normalize_lf_bytes(
            (repo_root / FORBIDDEN_FINAL100_SCENARIOS_REL_PATH).read_bytes()
        )
    )
    p11_sha = sha256_bytes(
        normalize_lf_bytes((repo_root / FORBIDDEN_P11_MANIFEST_REL_PATH).read_bytes())
    )
    firewall = verify_pre_authorization_firewall(repo_root)

    scientific_items = {
        "prompt_freeze": (
            "READY" if pf_sha == EXPECTED_PROMPT_FREEZE_SHA256 else "NOT_READY"
        ),
        "dev_tune_plan": (
            "READY"
            if (
                plan_model.plan_sha256 == EXPECTED_DEV_TUNE_PLAN_SHA256
                and plan_file_sha == EXPECTED_DEV_TUNE_PLAN_FILE_SHA256
            )
            else "NOT_READY"
        ),
        "runner": "READY" if runner_receipt_ready else "NOT_READY",
        "runner_qa": "READY" if runner_qa_ready else "NOT_READY",
        "candidate_registry": (
            "READY"
            if tuple(cand_reg.ordered_candidate_ids) == ORDERED_CANDIDATE_IDS
            else "NOT_READY"
        ),
        "provider_configs": (
            "READY"
            if pconf_reg_sha
            == "3dc05d29acc2f647cba58303865bd7406b8c1d9f7ccbe0f120e87ad471190938"
            else "NOT_READY"
        ),
        "schema_v2": (
            "READY"
            if (
                EXPECTED_PORTABLE_SCHEMA_V2_SHA256
                == "825a4ff912d851a95f7392cb564b7d7ca3588135508dc6eb3ac6304cdde3c490"
                and EXPECTED_SEMANTIC_SCHEMA_SHA256
                == "e4169f7b890f77d13af65e9f2070b6071c535b206d88440f5e8f28c179977555"
            )
            else "NOT_READY"
        ),
        "scientific_bundle": (
            "READY"
            if bundle_sha == EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
            else "NOT_READY"
        ),
        "final100_firewall": (
            "READY"
            if (
                final100_sha == FORBIDDEN_FINAL100_BUNDLE_SHA256
                and p11_sha == FORBIDDEN_P11_MANIFEST_SHA256
            )
            else "NOT_READY"
        ),
    }
    all_sci_ready = all(v == "READY" for v in scientific_items.values())

    return {
        **scientific_items,
        "all_scientific_prereqs": "READY" if all_sci_ready else "NOT_READY",
        "authorization_state": (
            "NOT_YET_GRANTED"
            if not firewall["live_authorization_artifact_created"]
            else "VIOLATION_CREATED_EARLY"
        ),
        "stage_a_state": (
            "NOT_YET_CREATED"
            if not firewall["stage_a_receipt_created"]
            else "VIOLATION_CREATED_EARLY"
        ),
        "key_presence": {
            "status_by_env_var": kp,
            "all_three_keys_present_locally": all(v == "PRESENT" for v in kp.values()),
            "operational_only_not_scientific_blocker": True,
        },
    }


# ==============================================================================
# 5. BUILD PREP ARTIFACT & RUN AP-01..AP-30 CHECKS
# ==============================================================================


def build_authorization_prep_payload(
    repo_root: Path = REPO_ROOT,
    *,
    key_presence_override: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Construct the canonical Section 15 authorization preparation artifact payload."""
    dev_bundle = load_and_verify_frozen_dev_bundle()
    cand_reg = load_and_verify_candidate_registry()
    prompt_reg = pf_mod.build_frozen_p1_p2_registry()

    pf_path = repo_root / PROMPT_FREEZE_REL_PATH
    plan_path = repo_root / DEV_TUNE_PLAN_REL_PATH
    freeze_model = DevPromptFreezeArtifact.model_validate_json(
        normalize_lf_bytes(pf_path.read_bytes())
    )
    plan_model = DevExecutionPlan.model_validate_json(
        normalize_lf_bytes(plan_path.read_bytes())
    )
    pair_audit = pf_mod.build_per_fixture_pair_audit(dev_bundle, prompt_reg, plan_model)
    pricing_by_candidate, cost_envelope = build_pricing_evidence_and_cost_envelope(
        repo_root
    )
    kp = (
        key_presence_override
        if key_presence_override is not None
        else check_key_presence_status_only(repo_root)
    )
    readiness_matrix = build_live_readiness_matrix(repo_root, key_presence=kp)
    firewall = verify_pre_authorization_firewall(repo_root)
    bundle_file_hashes = compute_scientific_code_bundle_file_hashes(repo_root=repo_root)

    candidates_list = [
        {
            "candidate_id": cid,
            "provider": CANDIDATE_PROVIDER_BY_ID[cid],
            "requested_model_id": CANDIDATE_MODEL_BY_ID[cid],
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
            "cells_in_dev_tune": 40,
        }
        for cid in ORDERED_CANDIDATE_IDS
    ]

    prompts_list = [
        {
            "prompt_id": "P1",
            "prompt_version": prompt_reg.prompts[0].prompt_version,
            "system_prompt_sha256": pf_mod.P1_EXPECTED_SYSTEM_PROMPT_SHA256,
            "user_prompt_template_sha256": pf_mod.P1_EXPECTED_USER_PROMPT_TEMPLATE_SHA256,
            "semantic_prompt_sha256": prompt_reg.prompts[0].semantic_prompt_sha256,
            "cells_in_dev_tune": 60,
        },
        {
            "prompt_id": "P2",
            "prompt_version": prompt_reg.prompts[1].prompt_version,
            "p2_candidate_definition_id": P2_CANDIDATE_DEFINITION_ID,
            "system_prompt_sha256": pf_mod.P2_EXPECTED_SYSTEM_PROMPT_SHA256,
            "user_prompt_template_sha256": pf_mod.P2_EXPECTED_USER_PROMPT_TEMPLATE_SHA256,
            "semantic_prompt_sha256": prompt_reg.prompts[1].semantic_prompt_sha256,
            "cells_in_dev_tune": 60,
        },
    ]

    payload: dict[str, Any] = {
        "artifact_id": PREPARATION_ARTIFACT_ID,
        "version": PREPARATION_ARTIFACT_VERSION,
        "task_id": TASK_ID,
        "source_develop_sha": SOURCE_DEVELOP_SHA,
        "code_basis_commit_sha": CODE_BASIS_COMMIT_SHA,
        "phase": PHASE_BEING_PREPARED,
        "phase_scope_restrictions": {
            "allowed_phase": "DEV_TUNE",
            "dev_select_authorized": False,
            "stochasticity_authorized": False,
            "final100_authorized": False,
        },
        "execution_plan_sha256": plan_model.plan_sha256,
        "execution_plan_file_sha256": sha256_bytes(
            normalize_lf_bytes(plan_path.read_bytes())
        ),
        "execution_plan_relative_path": DEV_TUNE_PLAN_REL_PATH,
        "prompt_freeze_sha256": sha256_bytes(normalize_lf_bytes(pf_path.read_bytes())),
        "prompt_freeze_relative_path": PROMPT_FREEZE_REL_PATH,
        "prompt_freeze_artifact_id": freeze_model.artifact_id,
        "prompt_registry_sha256": prompt_reg.registry_sha256,
        "scientific_code_bundle_sha256": compute_scientific_code_bundle_sha256(
            repo_root=repo_root
        ),
        "scientific_code_bundle_file_count": len(bundle_file_hashes),
        "scientific_code_bundle_file_hashes": bundle_file_hashes,
        "portable_schema_v2_sha256": EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
        "semantic_schema_sha256": EXPECTED_SEMANTIC_SCHEMA_SHA256,
        "candidate_registry_sha256": cand_reg.registry_sha256,
        "provider_config_registry_sha256": compute_provider_config_registry_sha256(
            cand_reg
        ),
        "candidate_list": candidates_list,
        "prompt_list": prompts_list,
        "controlled_experiment_parity": {
            "p1_p2_rendered_user_prompts_identical_all_20": pair_audit[
                "all_20_rendered_user_prompts_byte_identical"
            ],
            "only_system_prompt_suffix_differs": (
                pair_audit[
                    "all_60_p1_p2_cell_pairs_identical_except_prompt_identity_and_system_prompt"
                ]
                and pair_audit["differing_manifest_fields_across_all_60_pairs"]
                == ["prompt_id", "run_id", "system_prompt_sha256"]
            ),
            "differing_cell_manifest_fields": pair_audit[
                "differing_manifest_fields_across_all_60_pairs"
            ],
            "fixture_001_rendered_user_prompt_sha256": pf_mod.EXPECTED_FIXTURE_001_RENDERED_USER_PROMPT_SHA256,
        },
        "fixture_count": DEV_TUNE_COUNT,
        "fixture_ids": list(dev_bundle.dev_tune_ids),
        "prompt_count": len(prompts_list),
        "candidate_count": len(candidates_list),
        "attempts_per_cell": 1,
        "cell_count": len(plan_model.cells),
        "cells_per_prompt": {"P1": 60, "P2": 60},
        "cells_per_candidate": {"C1": 40, "C2": 40, "C3": 40},
        "cells_per_fixture": 6,
        "maximum_generation_calls": DEV_TUNE_MAX_CALLS_TWO_PROMPTS,
        "call_budget_policy": {
            "maximum_live_generation_calls": 120,
            "reserve_calls_beyond_120": 0,
            "retry_calls": 0,
            "diagnostic_calls": 0,
            "final100_calls": 0,
            "dev_select_calls": 0,
            "stochasticity_calls": 0,
            "max_outbound_http_requests_per_cell": 1,
            "no_hidden_calls": True,
            "future_owner_authorization_contract_requirements": {
                "allowed_phase": "DEV_TUNE",
                "maximum_live_generation_calls": 120,
                "allowed_candidate_ids": ["C1", "C2", "C3"],
                "allowed_execution_plan_sha256": EXPECTED_DEV_TUNE_PLAN_SHA256,
                "allowed_prompt_freeze_sha256": EXPECTED_PROMPT_FREEZE_SHA256,
            },
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
            "no_retry_until_success": True,
            "max_outbound_generation_http_requests_per_cell": 1,
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
        "cost_envelope": cost_envelope,
        "pricing_evidence": pricing_by_candidate,
        "key_presence_status": kp,
        "scientific_readiness_matrix": readiness_matrix,
        "pre_authorization_firewall": firewall,
        "project_owner_authorization_status": PROJECT_OWNER_AUTHORIZATION_STATUS,
        "proposed_owner_authorization_text": PROPOSED_OWNER_AUTHORIZATION_TEXT,
        "live_authorization_artifact_created": False,
        "stage_a_created": False,
        "live_provider_calls": 0,
        "provider_cost_usd": 0.0,
        "dev_tune_execution_started": False,
        "dev_select_execution_started": False,
        "stochasticity_execution_started": False,
        "final100_used": False,
    }
    assert_prep_payload_secret_free(payload, context="W06_DEV_TUNE_AUTHORIZATION_PREP")
    return payload


def assert_prep_payload_secret_free(
    payload: dict[str, Any], *, context: str
) -> None:
    """Verify key-presence status fields contain strictly PRESENT/MISSING and run assert_no_secrets_in_payload on the full payload."""
    kp = payload.get("key_presence_status", {})
    if not isinstance(kp, dict) or set(kp.keys()) != set(REQUIRED_ENV_KEYS):
        raise ValueError(
            f"{context}: key_presence_status must map {REQUIRED_ENV_KEYS}"
        )
    for k, v in kp.items():
        if v not in ("PRESENT", "MISSING"):
            raise ValueError(
                f"{context}: key_presence_status[{k!r}] has forbidden value {v!r}; only PRESENT or MISSING allowed"
            )

    sanitized_copy: dict[str, Any] = dict(payload)
    sanitized_copy["key_presence_status"] = [
        {"env_var": k, "status": v} for k, v in sorted(kp.items())
    ]
    if isinstance(sanitized_copy.get("scientific_readiness_matrix"), dict):
        rm_copy = dict(sanitized_copy["scientific_readiness_matrix"])
        if isinstance(rm_copy.get("key_presence"), dict):
            kp_rm = dict(rm_copy["key_presence"])
            status_map = kp_rm.get("status_by_env_var", {})
            if not isinstance(status_map, dict) or set(status_map.keys()) != set(
                REQUIRED_ENV_KEYS
            ):
                raise ValueError(
                    f"{context}: scientific_readiness_matrix.key_presence.status_by_env_var must map {REQUIRED_ENV_KEYS}"
                )
            for k, v in status_map.items():
                if v not in ("PRESENT", "MISSING"):
                    raise ValueError(
                        f"{context}: status_by_env_var[{k!r}] has forbidden value {v!r}"
                    )
            kp_rm["status_by_env_var"] = [
                {"env_var": k, "status": v} for k, v in sorted(status_map.items())
            ]
            rm_copy["key_presence"] = kp_rm
        sanitized_copy["scientific_readiness_matrix"] = rm_copy

    assert_no_secrets_in_payload(sanitized_copy, context=context)



def run_all_ap_checks(
    repo_root: Path = REPO_ROOT,
    *,
    prep_artifact_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Run all 30 offline checks AP-01 through AP-30 under the outbound-network kill switch."""
    results: list[dict[str, Any]] = []

    def record(
        check_id: str,
        domain: str,
        description: str,
        expected: Any,
        observed: Any,
        passed: bool,
    ) -> None:
        results.append(
            {
                "check_id": check_id,
                "domain": domain,
                "description": description,
                "expected": expected,
                "observed": observed,
                "status": "PASS" if passed else "FAIL",
            }
        )

    guard = NetworkKillSwitchGuard()
    with guard.activate():
        # AP-01: source develop exact
        src_info = verify_source_develop_commit_or_shallow_fallback(repo_root)
        record(
            "AP-01",
            "SOURCE_STATE",
            "Source develop SHA 443634e1f7583f334dec0315bb3816d249feb124 exists and is ancestor of HEAD",
            {
                "source_develop_sha": SOURCE_DEVELOP_SHA,
                "verified": True,
            },
            {
                "source_develop_sha": src_info["source_develop_sha"],
                "verified": src_info["verified"],
            },
            bool(src_info["verified"]),
        )

        dev_bundle = load_and_verify_frozen_dev_bundle()
        cand_reg = load_and_verify_candidate_registry()
        prompt_reg = pf_mod.build_frozen_p1_p2_registry()

        pf_path = repo_root / PROMPT_FREEZE_REL_PATH
        plan_path = repo_root / DEV_TUNE_PLAN_REL_PATH
        pf_bytes = normalize_lf_bytes(pf_path.read_bytes())
        plan_bytes = normalize_lf_bytes(plan_path.read_bytes())
        pf_sha = sha256_bytes(pf_bytes)
        plan_file_sha = sha256_bytes(plan_bytes)
        freeze_model = DevPromptFreezeArtifact.model_validate_json(pf_bytes)
        plan_model = DevExecutionPlan.model_validate_json(plan_bytes)

        verify_dev_execution_plan_for_execution(
            plan_model, candidate_registry=cand_reg, repo_root=repo_root
        )
        verify_prompt_candidate_freeze_artifact(
            pf_path,
            prompt_registry=prompt_reg,
            dev_tune_plan=plan_model,
            dev_bundle=dev_bundle,
            candidate_registry=cand_reg,
            repo_root=repo_root,
        )
        verify_runner_prompt_freeze_artifact(
            pf_path,
            prompt_registry=prompt_reg,
            execution_plan=plan_model,
            dev_bundle=dev_bundle,
            candidate_registry=cand_reg,
            repo_root=repo_root,
        )

        # AP-02: prompt freeze exact
        ap02_ok = (
            pf_sha == EXPECTED_PROMPT_FREEZE_SHA256
            and freeze_model.freeze_status == "FROZEN_FOR_LIVE_DEV_TUNE"
            and freeze_model.created_before_live_dev_execution is True
        )
        record(
            "AP-02",
            "FROZEN_AUTHORITIES",
            "Prompt freeze artifact SHA256 matches 2f345363f580ea882b2e5b3562c587ef5309bc7f994440257a54d18994ab6956 and passes runner/harness validation",
            EXPECTED_PROMPT_FREEZE_SHA256,
            pf_sha,
            ap02_ok,
        )

        # AP-03: DEV-TUNE plan exact
        ap03_ok = (
            plan_model.plan_sha256 == EXPECTED_DEV_TUNE_PLAN_SHA256
            and freeze_model.dev_tune_execution_plan_sha256
            == EXPECTED_DEV_TUNE_PLAN_SHA256
        )
        record(
            "AP-03",
            "FROZEN_AUTHORITIES",
            "DEV-TUNE execution plan SHA256 matches 582d9964b4fffbac91f83373d080f1fef120f0ddca4edab2d63e02796d0b20ae",
            EXPECTED_DEV_TUNE_PLAN_SHA256,
            plan_model.plan_sha256,
            ap03_ok,
        )

        # AP-04: plan file SHA exact
        ap04_ok = plan_file_sha == EXPECTED_DEV_TUNE_PLAN_FILE_SHA256
        record(
            "AP-04",
            "FROZEN_AUTHORITIES",
            "Persisted DEV-TUNE execution plan file SHA256 matches 652e3beb08771c3125e613172b1aaa396fc1b60aaaf3b98cc238e91a14e0dc74",
            EXPECTED_DEV_TUNE_PLAN_FILE_SHA256,
            plan_file_sha,
            ap04_ok,
        )

        # AP-05: scientific bundle exact
        bundle_sha = compute_scientific_code_bundle_sha256(repo_root=repo_root)
        bundle_hashes = compute_scientific_code_bundle_file_hashes(repo_root=repo_root)
        ap05_ok = (
            bundle_sha == EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
            and len(bundle_hashes) == len(SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS) == 14
        )
        record(
            "AP-05",
            "SCIENTIFIC_CODE_BUNDLE",
            "14-file scientific code bundle SHA256 matches 0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3",
            {
                "file_count": 14,
                "scientific_code_bundle_sha256": EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256,
            },
            {
                "file_count": len(bundle_hashes),
                "scientific_code_bundle_sha256": bundle_sha,
            },
            ap05_ok,
        )

        prep_payload = build_authorization_prep_payload(repo_root)
        if prep_artifact_path is not None and prep_artifact_path.is_file():
            persisted_prep = json.loads(prep_artifact_path.read_text(encoding="utf-8"))
        else:
            persisted_prep = prep_payload

        # AP-06: phase DEV_TUNE only
        ap06_ok = (
            persisted_prep["phase"] == "DEV_TUNE"
            and plan_model.phase == "DEV_TUNE"
            and all(c.phase == "DEV_TUNE" for c in plan_model.cells)
        )
        record(
            "AP-06",
            "PHASE_SCOPE",
            "Prepared phase is strictly DEV_TUNE across prep artifact and all 120 plan cells",
            "DEV_TUNE",
            persisted_prep["phase"],
            ap06_ok,
        )

        # AP-07: exact C1/C2/C3
        obs_cands = [
            (
                c["candidate_id"],
                c["provider"],
                c["requested_model_id"],
                c["technical_preflight_v2_status"],
            )
            for c in persisted_prep["candidate_list"]
        ]
        exp_cands = [
            (
                "C1",
                "google",
                "gemini-3.8-flash",
                "PASSED_TECHNICAL_PREFLIGHT_SCHEMA_V2",
            ),
            ("C2", "openai", "gpt-6.1-sol", "PASSED_TECHNICAL_PREFLIGHT_SCHEMA_V2"),
            (
                "C3",
                "anthropic",
                "claude-sonnet-5-5",
                "PASSED_TECHNICAL_PREFLIGHT_SCHEMA_V2",
            ),
        ]
        ap07_ok = obs_cands == exp_cands
        record(
            "AP-07",
            "CANDIDATE_MODELS",
            "Candidate models are exactly C1 (google/gemini-3.8-flash), C2 (openai/gpt-6.1-sol), C3 (anthropic/claude-sonnet-5-5)",
            exp_cands,
            obs_cands,
            ap07_ok,
        )

        # AP-08: exact P1/P2
        pair_audit = pf_mod.build_per_fixture_pair_audit(
            dev_bundle, prompt_reg, plan_model
        )
        ap08_ok = (
            [p.prompt_id for p in prompt_reg.prompts] == ["P1", "P2"]
            and prompt_reg.prompts[0].semantic_prompt_sha256
            == EXPECTED_P1_SEMANTIC_PROMPT_SHA256
            and prompt_reg.prompts[1].semantic_prompt_sha256
            == EXPECTED_P2_SEMANTIC_PROMPT_SHA256
            and prompt_reg.registry_sha256 == EXPECTED_PROMPT_REGISTRY_SHA256
            and pair_audit["all_20_rendered_user_prompts_byte_identical"] is True
            and pair_audit[
                "all_60_p1_p2_cell_pairs_identical_except_prompt_identity_and_system_prompt"
            ]
            is True
        )
        record(
            "AP-08",
            "PROMPT_AUTHORITIES",
            "Prompts are exactly P1 and P2 with frozen semantic SHA256s, registry SHA256, and rendered user prompt parity across all 20 fixtures",
            {
                "P1": EXPECTED_P1_SEMANTIC_PROMPT_SHA256,
                "P2": EXPECTED_P2_SEMANTIC_PROMPT_SHA256,
                "registry_sha256": EXPECTED_PROMPT_REGISTRY_SHA256,
                "rendered_user_prompts_identical_all_20": True,
            },
            {
                "P1": prompt_reg.prompts[0].semantic_prompt_sha256,
                "P2": prompt_reg.prompts[1].semantic_prompt_sha256,
                "registry_sha256": prompt_reg.registry_sha256,
                "rendered_user_prompts_identical_all_20": pair_audit[
                    "all_20_rendered_user_prompts_byte_identical"
                ],
            },
            ap08_ok,
        )

        # AP-09: exact 20 fixtures
        expected_fids = [f"W06-DEV-TUNE-{i:03d}" for i in range(1, 21)]
        plan_cell_fids = sorted({c.fixture_id for c in plan_model.cells})
        ap09_ok = (
            persisted_prep["fixture_count"] == 20
            and plan_model.fixture_count == 20
            and persisted_prep["fixture_ids"] == expected_fids
            and plan_cell_fids == expected_fids
        )
        record(
            "AP-09",
            "EXPERIMENT_MATRIX",
            "DEV-TUNE fixture list is exactly the 20 frozen W06-DEV-TUNE-001..020 scenarios",
            {"fixture_count": 20, "first": "W06-DEV-TUNE-001", "last": "W06-DEV-TUNE-020"},
            {
                "fixture_count": persisted_prep["fixture_count"],
                "first": persisted_prep["fixture_ids"][0],
                "last": persisted_prep["fixture_ids"][-1],
            },
            ap09_ok,
        )

        # AP-10: exact 120 cells
        ap10_ok = (
            persisted_prep["cell_count"] == 120
            and len(plan_model.cells) == 120
            and persisted_prep["cells_per_prompt"] == {"P1": 60, "P2": 60}
            and persisted_prep["cells_per_candidate"]
            == {"C1": 40, "C2": 40, "C3": 40}
            and persisted_prep["cells_per_fixture"] == 6
        )
        record(
            "AP-10",
            "EXPERIMENT_MATRIX",
            "Experiment matrix is 20 fixtures x 2 prompts x 3 candidates x 1 attempt = 120 unique assigned cells",
            120,
            len(plan_model.cells),
            ap10_ok,
        )

        # AP-11: max call budget 120
        cb = persisted_prep["call_budget_policy"]
        ap11_ok = (
            persisted_prep["maximum_generation_calls"] == 120
            and cb["maximum_live_generation_calls"] == 120
            and cb["reserve_calls_beyond_120"] == 0
            and cb["retry_calls"] == 0
            and cb["diagnostic_calls"] == 0
            and cb["max_outbound_http_requests_per_cell"] == 1
            and cb["no_hidden_calls"] is True
        )
        record(
            "AP-11",
            "CALL_BUDGET_POLICY",
            "Maximum live generation calls is 120 with zero reserve/retry/diagnostic calls and at most 1 HTTP request per cell",
            {"max_calls": 120, "reserve_calls": 0, "max_http_per_cell": 1},
            {
                "max_calls": cb["maximum_live_generation_calls"],
                "reserve_calls": cb["reserve_calls_beyond_120"],
                "max_http_per_cell": cb["max_outbound_http_requests_per_cell"],
            },
            ap11_ok,
        )

        # AP-12: retry zero
        rp = persisted_prep["retry_policy"]
        ap12_ok = (
            rp["attempt_number"] == 1
            and rp["sdk_retry"] == 0
            and rp["transport_retry"] == 0
            and rp["manual_retry"] == 0
            and rp["automatic_retry"] == 0
            and rp["no_retry_until_success"] is True
            and all(
                c.attempt_number == 1
                and c.retry == 0
                and c.automatic_retry == 0
                and c.transport_retry == 0
                and c.manual_retry == 0
                for c in plan_model.cells
            )
        )
        record(
            "AP-12",
            "EXECUTION_POLICY",
            "attempt_number=1 and all retry counters (sdk, transport, manual, automatic) equal 0 across policy and all 120 cells",
            0,
            {
                "sdk_retry": rp["sdk_retry"],
                "transport_retry": rp["transport_retry"],
                "manual_retry": rp["manual_retry"],
                "automatic_retry": rp["automatic_retry"],
            },
            ap12_ok,
        )

        # AP-13: no fallback
        ap13_ok = (
            rp["fallback"] is False
            and rp["best_of"] is False
            and all(c.fallback is False for c in plan_model.cells)
        )
        record(
            "AP-13",
            "EXECUTION_POLICY",
            "fallback=false and best_of=false across policy and all 120 cells",
            {"fallback": False, "best_of": False},
            {"fallback": rp["fallback"], "best_of": rp["best_of"]},
            ap13_ok,
        )

        # AP-14: no repair
        ap14_ok = (
            rp["llm_repair"] == 0
            and rp["deterministic_semantic_repair"] is False
            and all(
                c.repair == 0
                and c.llm_repair == 0
                and c.deterministic_semantic_repair is False
                for c in plan_model.cells
            )
        )
        record(
            "AP-14",
            "EXECUTION_POLICY",
            "llm_repair=0 and deterministic_semantic_repair=false across policy and all 120 cells",
            {"llm_repair": 0, "deterministic_semantic_repair": False},
            {
                "llm_repair": rp["llm_repair"],
                "deterministic_semantic_repair": rp["deterministic_semantic_repair"],
            },
            ap14_ok,
        )

        # AP-15: no tools
        ap15_ok = rp["tools"] is False and all(
            c.tools is False for c in plan_model.cells
        )
        record(
            "AP-15",
            "EXECUTION_POLICY",
            "tools=false across policy and all 120 cells",
            False,
            rp["tools"],
            ap15_ok,
        )

        # AP-16: ordinary failure denominator policy
        fp = persisted_prep["failure_policy"]
        harness_ordinary = {f.value for f in ORDINARY_DENOMINATOR_FAILURE_CLASSIFICATIONS}
        ap16_ok = (
            tuple(fp["ordinary_denominator_preserving_failures"])
            == ORDINARY_DENOMINATOR_FAILURE_TYPES
            and set(ORDINARY_DENOMINATOR_FAILURE_TYPES).issubset(harness_ordinary)
            and fp["ordinary_failure_treatment"]["counts_in_denominator"] is True
            and fp["ordinary_failure_treatment"]["retry"] == 0
            and fp["ordinary_failure_treatment"]["batch_stop_required"] is False
        )
        record(
            "AP-16",
            "FAILURE_POLICY",
            "All 10 ordinary provider/validation failures remain denominator-preserving with zero retry",
            list(ORDINARY_DENOMINATOR_FAILURE_TYPES),
            fp["ordinary_denominator_preserving_failures"],
            ap16_ok,
        )

        # AP-17: batch-fatal policy
        harness_fatal = {f.value for f in BATCH_STOP_FAILURE_CLASSIFICATIONS}
        ap17_ok = (
            tuple(fp["batch_fatal_integrity_failures"])
            == BATCH_FATAL_INTEGRITY_FAILURE_TYPES
            and harness_fatal.issubset(set(BATCH_FATAL_INTEGRITY_FAILURE_TYPES))
            and fp["batch_fatal_treatment"]["batch_stop_required"] is True
            and fp["batch_fatal_treatment"]["counts_in_denominator"] is False
        )
        record(
            "AP-17",
            "FAILURE_POLICY",
            "All 8 batch-fatal integrity failures trigger immediate fail-closed batch stop",
            list(BATCH_FATAL_INTEGRITY_FAILURE_TYPES),
            fp["batch_fatal_integrity_failures"],
            ap17_ok,
        )

        # AP-18: no DEV_SELECT authority
        ap18_ok = (
            persisted_prep["phase_scope_restrictions"]["dev_select_authorized"] is False
            and persisted_prep["dev_select_execution_started"] is False
            and cb["dev_select_calls"] == 0
        )
        record(
            "AP-18",
            "PHASE_FIREWALL",
            "Preparation does NOT authorize or start DEV_SELECT",
            {"dev_select_authorized": False, "dev_select_execution_started": False},
            {
                "dev_select_authorized": persisted_prep["phase_scope_restrictions"][
                    "dev_select_authorized"
                ],
                "dev_select_execution_started": persisted_prep[
                    "dev_select_execution_started"
                ],
            },
            ap18_ok,
        )

        # AP-19: no stochasticity authority
        ap19_ok = (
            persisted_prep["phase_scope_restrictions"]["stochasticity_authorized"]
            is False
            and persisted_prep["stochasticity_execution_started"] is False
            and cb["stochasticity_calls"] == 0
        )
        record(
            "AP-19",
            "PHASE_FIREWALL",
            "Preparation does NOT authorize or start STOCHASTICITY",
            {
                "stochasticity_authorized": False,
                "stochasticity_execution_started": False,
            },
            {
                "stochasticity_authorized": persisted_prep["phase_scope_restrictions"][
                    "stochasticity_authorized"
                ],
                "stochasticity_execution_started": persisted_prep[
                    "stochasticity_execution_started"
                ],
            },
            ap19_ok,
        )

        # AP-20: no Final100 authority
        ap20_ok = (
            persisted_prep["phase_scope_restrictions"]["final100_authorized"] is False
            and persisted_prep["final100_used"] is False
            and cb["final100_calls"] == 0
        )
        record(
            "AP-20",
            "FINAL100_FIREWALL",
            "Preparation does NOT authorize or use Final100",
            {"final100_authorized": False, "final100_used": False},
            {
                "final100_authorized": persisted_prep["phase_scope_restrictions"][
                    "final100_authorized"
                ],
                "final100_used": persisted_prep["final100_used"],
            },
            ap20_ok,
        )

        # AP-21: authorization artifact absent
        fw = verify_pre_authorization_firewall(repo_root)
        ap21_ok = (
            fw["live_authorization_artifact_created"] is False
            and persisted_prep["live_authorization_artifact_created"] is False
            and "authorization_id" not in persisted_prep
            and persisted_prep.get("authorization_status") != "AUTHORIZED"
        )
        record(
            "AP-21",
            "PRE_AUTHORIZATION_FIREWALL",
            "No DevLiveAuthorizationArtifact, authorization_id, or AUTHORIZED status exists",
            {
                "live_authorization_artifact_created": False,
                "has_authorization_id": False,
            },
            {
                "live_authorization_artifact_created": fw[
                    "live_authorization_artifact_created"
                ],
                "has_authorization_id": "authorization_id" in persisted_prep,
            },
            ap21_ok,
        )

        # AP-22: Stage-A artifact absent
        ap22_ok = (
            fw["stage_a_receipt_created"] is False
            and fw["transport_journal_created"] is False
            and fw["provider_result_directories_created"] is False
            and persisted_prep["stage_a_created"] is False
        )
        record(
            "AP-22",
            "PRE_AUTHORIZATION_FIREWALL",
            "No Stage-A freeze receipt, transport journal, or live cell result directory exists",
            {
                "stage_a_receipt_created": False,
                "transport_journal_created": False,
                "provider_result_directories_created": False,
            },
            {
                "stage_a_receipt_created": fw["stage_a_receipt_created"],
                "transport_journal_created": fw["transport_journal_created"],
                "provider_result_directories_created": fw[
                    "provider_result_directories_created"
                ],
            },
            ap22_ok,
        )

        # AP-23: authorization status NOT_GRANTED
        rm = persisted_prep["scientific_readiness_matrix"]
        ap23_ok = (
            persisted_prep["project_owner_authorization_status"] == "NOT_GRANTED"
            and rm["all_scientific_prereqs"] == "READY"
            and rm["authorization_state"] == "NOT_YET_GRANTED"
            and rm["stage_a_state"] == "NOT_YET_CREATED"
        )
        record(
            "AP-23",
            "AUTHORIZATION_STATUS",
            "project_owner_authorization_status is NOT_GRANTED, scientific prereqs are READY, authorization is NOT_YET_GRANTED, Stage-A is NOT_YET_CREATED",
            {
                "project_owner_authorization_status": "NOT_GRANTED",
                "all_scientific_prereqs": "READY",
                "authorization_state": "NOT_YET_GRANTED",
                "stage_a_state": "NOT_YET_CREATED",
            },
            {
                "project_owner_authorization_status": persisted_prep[
                    "project_owner_authorization_status"
                ],
                "all_scientific_prereqs": rm["all_scientific_prereqs"],
                "authorization_state": rm["authorization_state"],
                "stage_a_state": rm["stage_a_state"],
            },
            ap23_ok,
        )

        # AP-24: proposed authorization text exact hashes
        prop_text = persisted_prep["proposed_owner_authorization_text"]
        ap24_ok = (
            prop_text == PROPOSED_OWNER_AUTHORIZATION_TEXT
            and EXPECTED_DEV_TUNE_PLAN_SHA256 in prop_text
            and EXPECTED_PROMPT_FREEZE_SHA256 in prop_text
            and "120-cell plan" in prop_text
            and "candidates C1/C2/C3" in prop_text
            and "maximum 120 generation calls" in prop_text
            and "zero retry" in prop_text
            and "no DEV-SELECT" in prop_text
            and "no stochasticity" in prop_text
            and "no Final100" in prop_text
        )
        record(
            "AP-24",
            "OWNER_AUTHORIZATION_TEXT",
            "Proposed Project Owner authorization sentence contains exact plan and prompt freeze SHA256s and all scope constraints",
            PROPOSED_OWNER_AUTHORIZATION_TEXT,
            prop_text,
            ap24_ok,
        )

        # AP-25: no secret values printed/persisted
        kp_obs = persisted_prep["key_presence_status"]
        no_secret_exc = True
        try:
            assert_prep_payload_secret_free(persisted_prep, context="AP_25_CHECK")
        except Exception:
            no_secret_exc = False
        ap25_ok = (
            no_secret_exc
            and set(kp_obs.keys()) == set(REQUIRED_ENV_KEYS)
            and all(v in ("PRESENT", "MISSING") for v in kp_obs.values())
        )
        record(
            "AP-25",
            "SECRET_HYGIENE",
            "Key presence records strictly PRESENT/MISSING without any secret values or hashes",
            {"allowed_values": ["PRESENT", "MISSING"], "secret_free": True},
            {"observed_keys": sorted(kp_obs.keys()), "secret_free": no_secret_exc},
            ap25_ok,
        )

        # AP-26: zero network generation calls
        ap26_ok = (
            len(guard.blocked_attempts) == 0
            and persisted_prep["live_provider_calls"] == 0
            and persisted_prep["provider_cost_usd"] == 0.0
            and persisted_prep["dev_tune_execution_started"] is False
        )
        record(
            "AP-26",
            "NETWORK_ISOLATION",
            "Zero outbound network calls and zero live provider calls occurred",
            {"blocked_attempts": 0, "live_provider_calls": 0, "provider_cost_usd": 0.0},
            {
                "blocked_attempts": len(guard.blocked_attempts),
                "live_provider_calls": persisted_prep["live_provider_calls"],
                "provider_cost_usd": persisted_prep["provider_cost_usd"],
            },
            ap26_ok,
        )

        # AP-27: pricing evidence explicit
        pe = persisted_prep["pricing_evidence"]
        required_pricing_fields = {
            "pricing_source",
            "pricing_checked_at_utc",
            "input_price_basis",
            "output_price_basis",
            "reasoning_thought_billing_treatment",
            "cache_billing_treatment",
        }
        ap27_ok = set(pe.keys()) == {"C1", "C2", "C3"} and all(
            required_pricing_fields.issubset(set(pe[cid].keys()))
            and bool(pe[cid]["pricing_source"])
            and bool(pe[cid]["pricing_checked_at_utc"])
            for cid in ("C1", "C2", "C3")
        )
        record(
            "AP-27",
            "PRICING_EVIDENCE",
            "Explicit provider pricing evidence and candidate-aware billing treatment recorded for C1, C2, and C3",
            sorted(required_pricing_fields),
            sorted(
                required_pricing_fields.intersection(
                    set(pe["C1"].keys()), set(pe["C2"].keys()), set(pe["C3"].keys())
                )
            ),
            ap27_ok,
        )

        # AP-28: cost uncertainty truthfully represented
        ce = persisted_prep["cost_envelope"]
        ap28_ok = (
            "estimated_expected_cost_usd" in ce
            and ce["hard_max_cost_usd"] == "NOT_DEFENSIBLY_COMPUTABLE"
            and bool(ce.get("hard_max_cost_explanation"))
            and ce["estimated_expected_cost_usd"]["low_expected_usd"]
            < ce["estimated_expected_cost_usd"]["high_expected_usd"]
        )
        record(
            "AP-28",
            "COST_ENVELOPE",
            "Cost envelope distinguishes ESTIMATED_EXPECTED_COST range from HARD_MAX_COST = NOT_DEFENSIBLY_COMPUTABLE without false precision",
            {
                "hard_max_cost_usd": "NOT_DEFENSIBLY_COMPUTABLE",
                "has_expected_range": True,
            },
            {
                "hard_max_cost_usd": ce["hard_max_cost_usd"],
                "has_expected_range": "range_usd" in ce["estimated_expected_cost_usd"],
            },
            ap28_ok,
        )

        # AP-29: production scientific files unchanged
        expected_bundle_map = {
            entry["path"]: entry["sha256"]
            for entry in pf_mod.EXPECTED_SCIENTIFIC_CODE_BUNDLE_FILE_HASHES
        }
        actual_bundle_map = {
            entry["path"]: entry["sha256"] for entry in bundle_hashes
        }
        ap29_ok = (
            actual_bundle_map == expected_bundle_map
            and bundle_sha == EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
        )
        record(
            "AP-29",
            "SCIENTIFIC_CODE_BUNDLE",
            "All 14 production scientific files are 100% byte-for-byte unchanged",
            {"unchanged_files": 14},
            {
                "unchanged_files": sum(
                    1
                    for k, v in expected_bundle_map.items()
                    if actual_bundle_map.get(k) == v
                )
            },
            ap29_ok,
        )

        # AP-30: Final100 untouched
        final100_sha = sha256_bytes(
            normalize_lf_bytes(
                (repo_root / FORBIDDEN_FINAL100_SCENARIOS_REL_PATH).read_bytes()
            )
        )
        p11_sha = sha256_bytes(
            normalize_lf_bytes(
                (repo_root / FORBIDDEN_P11_MANIFEST_REL_PATH).read_bytes()
            )
        )
        ap30_ok = (
            final100_sha == FORBIDDEN_FINAL100_BUNDLE_SHA256
            and p11_sha == FORBIDDEN_P11_MANIFEST_SHA256
            and persisted_prep["final100_used"] is False
        )
        record(
            "AP-30",
            "FINAL100_FIREWALL",
            "Final100 scenarios freeze and P11 assignment manifest are untouched and unused",
            {
                "final100_sha256": FORBIDDEN_FINAL100_BUNDLE_SHA256,
                "p11_manifest_sha256": FORBIDDEN_P11_MANIFEST_SHA256,
                "final100_used": False,
            },
            {
                "final100_sha256": final100_sha,
                "p11_manifest_sha256": p11_sha,
                "final100_used": persisted_prep["final100_used"],
            },
            ap30_ok,
        )

    return results


def generate_and_persist_prep_artifact(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Generate and persist `data/evaluation/w06/w06_dev_tune_authorization_prep_v1.json`."""
    prep_path = repo_root / PREP_ARTIFACT_REL_PATH
    base_payload = build_authorization_prep_payload(repo_root)
    ap_checks = run_all_ap_checks(repo_root)
    failed = [c for c in ap_checks if c["status"] != "PASS"]
    if failed:
        raise RuntimeError(f"AP checks failed: {failed}")

    full_payload = {
        **base_payload,
        "verification_summary": {
            "total_checks": len(ap_checks),
            "passed_checks": sum(1 for c in ap_checks if c["status"] == "PASS"),
            "failed_checks": sum(1 for c in ap_checks if c["status"] != "PASS"),
            "overall_status": "PASS",
        },
        "checks": ap_checks,
    }
    assert_prep_payload_secret_free(
        full_payload, context="W06_DEV_TUNE_AUTHORIZATION_PREP_FINAL"
    )
    prep_bytes = canonical_json_bytes(full_payload)
    prep_path.write_bytes(prep_bytes)
    return full_payload


if __name__ == "__main__":
    artifact = generate_and_persist_prep_artifact()
    prep_file_sha = hashlib.sha256(
        (REPO_ROOT / PREP_ARTIFACT_REL_PATH).read_bytes()
    ).hexdigest()
    print(
        json.dumps(
            {
                "task_id": artifact["task_id"],
                "phase": artifact["phase"],
                "ap_checks": f"{artifact['verification_summary']['passed_checks']}/{artifact['verification_summary']['total_checks']}",
                "prep_artifact_sha256": prep_file_sha,
                "project_owner_authorization_status": artifact[
                    "project_owner_authorization_status"
                ],
                "live_authorization_artifact_created": artifact[
                    "live_authorization_artifact_created"
                ],
                "stage_a_created": artifact["stage_a_created"],
                "live_provider_calls": artifact["live_provider_calls"],
                "provider_cost_usd": artifact["provider_cost_usd"],
                "key_presence_status": artifact["key_presence_status"],
                "estimated_expected_cost_usd": artifact["cost_envelope"][
                    "estimated_expected_cost_usd"
                ]["range_usd"],
                "hard_max_cost_usd": artifact["cost_envelope"]["hard_max_cost_usd"],
            },
            indent=2,
        )
    )
