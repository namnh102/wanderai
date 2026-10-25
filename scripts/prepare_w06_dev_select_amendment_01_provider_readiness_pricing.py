#!/usr/bin/env python3
"""Fail-closed provider-readiness and current-pricing PREP generator and verifier for W06 DEV-SELECT Amendment 01.

TASK: W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-PROVIDER-READINESS-AND-PRICING-CORRECTIVE-01

PURPOSE:
Prepare and statelessly verify the fail-closed provider-readiness and current-pricing
evidence package for the approved W06 secondary post-hoc execution-environment
stabilization amendment:
1. `data/evaluation/w06/w06_dev_select_amendment_01_public_pricing_snapshot_v1.json`
2. `data/evaluation/w06/w06_dev_select_amendment_01_provider_readiness_pricing_prep_v1.json`
3. `docs/research/w06_dev_select_amendment_01_provider_readiness_pricing_prep.md`

STRICT FIREWALLS:
- PREP ONLY: Does NOT authorize or execute any live provider call (`LIVE_PROVIDER_CALLS_NEW = 0`).
- Does NOT read `.env`, API keys, or secrets (`ENV_FILE_READ = false`, `API_KEYS_INSPECTED = false`).
- Does NOT mark any provider ready (`C1/C2/C3_PROVIDER_READINESS = "NOT_YET_ATTESTED"`).
- Does NOT select a model (`MODEL_WINNER_SELECTED = false`, `SELECTED_MODEL_ID = null`).
- Does NOT touch Final100 (`FINAL100_USED = false`, `FINAL100_STATUS = "NO-GO"`).
- Does NOT mutate primary DEV-SELECT evidence (`PRIMARY_EXPERIMENT_MUTATED = false`).
- ONE calculation authority: `analyze_requests_and_costs()` -> `cost_analysis` -> JSON artifact -> Markdown renderer.
"""

from __future__ import annotations

import argparse
from decimal import Decimal, ROUND_HALF_UP
import json
from pathlib import Path
import re
import sys
from typing import Any
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
AI_SERVICE_DIR = REPO_ROOT / "apps" / "ai-service"
for _p in (SCRIPTS_DIR, AI_SERVICE_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from app.evaluation.dev_live_runner import (  # noqa: E402
    ORDERED_CANDIDATE_IDS,
    PlanBeforeLiveProtocolError,
    assert_no_secrets_in_payload,
)
from app.evaluation.dev_selection_harness import (  # noqa: E402
    canonical_json_bytes,
    compute_scientific_code_bundle_sha256,
    normalize_lf_bytes,
    sha256_bytes,
)
import diagnose_w06_dev_select_failures as _diag_mod  # noqa: E402
import freeze_w06_dev_select_execution_environment_amendment_01_approval_receipt as _app_mod  # noqa: E402
import freeze_w06_dev_select_execution_environment_amendment_01_decision as _dec_mod  # noqa: E402
import freeze_w06_dev_select_live_results as _freeze_mod  # noqa: E402
import prepare_w06_dev_select_execution_environment_amendment_01 as _prep_mod  # noqa: E402
from prepare_w06_dev_select_execution_environment_amendment_01 import (  # noqa: E402
    NetworkKillSwitchGuard,
)


# ==============================================================================
# 1. FROZEN AUTHORITIES & CONSTANTS
# ==============================================================================

TASK_ID = (
    "W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-PROVIDER-READINESS-AND-PRICING-PREP"
)
CORRECTIVE_TASK_ID = (
    "W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-PROVIDER-READINESS-AND-PRICING-CORRECTIVE-01"
)
PUBLIC_PRICING_SNAPSHOT_ARTIFACT_ID = (
    "W06-DEV-SELECT-AMENDMENT-01-PUBLIC-PRICING-SNAPSHOT-V1"
)
PUBLIC_PRICING_SNAPSHOT_REL_PATH = (
    "data/evaluation/w06/w06_dev_select_amendment_01_public_pricing_snapshot_v1.json"
)
PROVIDER_READINESS_PRICING_PREP_ARTIFACT_ID = (
    "W06-DEV-SELECT-AMENDMENT-01-PROVIDER-READINESS-PRICING-PREP-V1"
)
PROVIDER_READINESS_PRICING_PREP_REL_PATH = (
    "data/evaluation/w06/w06_dev_select_amendment_01_provider_readiness_pricing_prep_v1.json"
)
PROVIDER_READINESS_PRICING_PREP_DOC_REL_PATH = (
    "docs/research/w06_dev_select_amendment_01_provider_readiness_pricing_prep.md"
)

AUTHORITATIVE_BASE_DEVELOP_SHA = "c2e5126b7e1d3aa25ef6e46352e030c346fc733a"
APPROVAL_RECEIPT_PR_NUMBER = 69
APPROVAL_RECEIPT_PR_STATE = "MERGED"
APPROVAL_RECEIPT_MERGE_COMMIT_SHA = "c2e5126b7e1d3aa25ef6e46352e030c346fc733a"
APPROVAL_RECEIPT_MERGE_PARENT_1 = "1de6ad5288f2fc5f3036145f4089d3e1bb46f1ab"
APPROVAL_RECEIPT_MERGE_PARENT_2 = "11fa0338e0f35ea2afce8747002789a36525868b"
APPROVAL_RECEIPT_POST_MERGE_CI_RUN_ID = 40099797847

# Bound upstream artifact hashes
APPROVAL_RECEIPT_REL_PATH = _app_mod.APPROVAL_RECEIPT_REL_PATH
EXPECTED_APPROVAL_RECEIPT_FILE_SHA256 = (
    "171564d09b0011ddfc0e2b70ca2f9029bf6981b944527c09331fa7f6a0f914a5"
)
EXPECTED_APPROVAL_RECEIPT_INTERNAL_SHA256 = (
    "d32e1c61b130a93c5ccbf18294fc1e972c36ba4e561b7fff51a9ea13b43aa991"
)

DECISION_ARTIFACT_REL_PATH = _dec_mod.DECISION_ARTIFACT_REL_PATH
EXPECTED_DECISION_ARTIFACT_FILE_SHA256 = (
    "2e4211893c1988230e2eeb2718195d48c093da87725cd2fa074e1743ee599ddf"
)
EXPECTED_DECISION_ARTIFACT_INTERNAL_SHA256 = (
    "38dc02de2e846d4cf72108e8beacffdcfcf6308879e0ea72cca3bb83bf71387a"
)

CANARY_MANIFEST_REL_PATH = _dec_mod.CANARY_MANIFEST_REL_PATH
EXPECTED_CANARY_MANIFEST_FILE_SHA256 = (
    "3ce0ebaac35f22dfe8c981478a6c63d7a2fde0580b372fd8f25762ab3b18fb96"
)
EXPECTED_CANARY_MANIFEST_INTERNAL_SHA256 = (
    "707d99fee54d65822f194cc690cbfadea14ad2176594d4ef882e7d8031990518"
)

PREP_ARTIFACT_REL_PATH = _prep_mod.PREP_ARTIFACT_REL_PATH
EXPECTED_PREP_ARTIFACT_FILE_SHA256 = (
    "e8786c4f538b86c8aa1d6b2c0cfb4afd6b8b6a1efa5b51799e44bd6bdd5a9a91"
)
EXPECTED_PREP_ARTIFACT_INTERNAL_SHA256 = (
    "49c24e65690cb4fb947d2733ddf8b019d863046cf955d9415eec1d16e9eaaf7a"
)

PRIMARY_RESULTS_FREEZE_RECEIPT_REL_PATH = _freeze_mod.RESULTS_FREEZE_RECEIPT_REL_PATH
EXPECTED_PRIMARY_RESULTS_FREEZE_RECEIPT_FILE_SHA256 = (
    "c021094e26277d41664c4ae2f0560b7684435b6002c5b7ba742a17808c5b07a4"
)
EXPECTED_PRIMARY_RESULTS_FREEZE_RECEIPT_INTERNAL_SHA256 = (
    "7b270de482f0b077e79bbba40a0c662851da46355a18b5e05f8fdf572880943a"
)

PRIMARY_RESULTS_MANIFEST_REL_PATH = _freeze_mod.RESULTS_MANIFEST_REL_PATH
EXPECTED_PRIMARY_RESULTS_MANIFEST_FILE_SHA256 = (
    "1d303e1c07b627c3f3eb87287b744f55ba3f6d3d85bd5cec36959b01919d26c0"
)
EXPECTED_PRIMARY_RESULTS_MANIFEST_INTERNAL_SHA256 = (
    "4e2f8f0df0a6e069d65b563b8221c3ba3086bb50ad73854e9cc592a9beb05011"
)

FAILURE_DIAGNOSTIC_REL_PATH = _diag_mod.DIAGNOSTIC_ARTIFACT_REL_PATH
EXPECTED_FAILURE_DIAGNOSTIC_FILE_SHA256 = (
    "b729883505ecfc98f15917347239ea6d09cede106691b155026891996391e692"
)
EXPECTED_FAILURE_DIAGNOSTIC_INTERNAL_SHA256 = (
    "509528413e1d9eb8408943867be21f83dc2dda72acd53fe9028e3c37c7db05c8"
)

EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256 = (
    "0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3"
)

# Section 1: Authoritative Primary Metric Tuple & Rejected Report Tuple
AUTHORITATIVE_PRIMARY_METRIC_RATES: dict[str, str] = {
    "C1": "1/60",
    "C2": "8/60",
    "C3": "0/60",
}
REJECTED_ERRONEOUS_REPORT_METRIC_RATES: dict[str, str] = {
    "C1": "0/60",
    "C2": "43/60",
    "C3": "0/60",
}

# Section 3 & 4: Immutable Approved Policy & Frozen Candidates
TRACK_CLASSIFICATION = (
    "SECONDARY_POST_HOC_EXECUTION_ENVIRONMENT_STABILIZATION_TRACK"
)
SELECTED_FAIRNESS_POLICY = "OPTION_B_CONSERVATIVE_RELIABILITY_ENVIRONMENT"
SELECTED_TIMEOUT_POLICY = "T3_CANDIDATE_180S"
SELECTED_TIMEOUT_MS = 180000
SELECTED_PACING_POLICY = "P1_FIXED_2000MS_INTER_CALL_DELAY"
SELECTED_INTER_CALL_DELAY_MS = 2000
SELECTED_RETRY_POLICY = "R0_STRICT_ZERO_RETRY"
SELECTED_FIXTURE_POLICY = (
    "POLICY_F3_ENGINEERING_READINESS_SUBSET_PLUS_AMENDED_COMPARATIVE_SET"
)
SELECTED_CALL_BUDGET_POLICY = "S2_READINESS_CANARY_PLUS_COMPARATIVE_180"
CANARY_CALL_COUNT = 9
COMPARATIVE_CALL_COUNT = 180
MAX_GENERATION_CALL_COUNT = 189
MAX_CALLS_PER_CANDIDATE = 63

FROZEN_CANDIDATES: dict[str, dict[str, str]] = {
    "C1": {"provider": "GOOGLE", "model": "gemini-3.8-flash"},
    "C2": {"provider": "OPENAI", "model": "gpt-6.1-sol"},
    "C3": {"provider": "ANTHROPIC", "model": "claude-sonnet-5-5"},
}

CANARY_FIXTURE_IDS: tuple[str, ...] = (
    "W06-DEV-TUNE-007",
    "W06-DEV-TUNE-011",
    "W06-DEV-TUNE-015",
)

# Section 5 (and Corrective Section 4): Direct Allowlisted Pricing Domains
# Note: platform.claude.com is NOT a direct authority domain; it may only appear
# as a subordinate redirect target bound to an already-allowlisted docs.anthropic.com URL.
ALLOWLISTED_PRICING_DOMAINS_BY_PROVIDER: dict[str, tuple[str, ...]] = {
    "GOOGLE": ("ai.google.dev",),
    "OPENAI": ("developers.openai.com", "platform.openai.com", "openai.com"),
    "ANTHROPIC": ("docs.anthropic.com", "anthropic.com"),
}
ALLOWED_REDIRECT_TARGET_DOMAINS_BY_SOURCE_DOMAIN: dict[str, tuple[str, ...]] = {
    "docs.anthropic.com": ("platform.claude.com", "docs.anthropic.com"),
    "platform.openai.com": ("developers.openai.com", "platform.openai.com"),
}
FORBIDDEN_GOOGLE_CLOUD_DOMAIN = "cloud.google.com"

# Section 9, 10, 11, 18, 21: Status Constants
OPENAI_LONG_CONTEXT_THRESHOLD_INPUT_TOKENS = 272000
OPENAI_LONG_CONTEXT_SURCHARGE_STATUS = "NOT_APPLICABLE_PROVEN"
HARD_MAXIMUM_STATUS = "NOT_DEFENSIBLY_COMPUTABLE"
PROVIDER_READINESS_NOT_YET_ATTESTED = "NOT_YET_ATTESTED"
EFFECTIVE_AMENDMENT_STATUS = "METHODOLOGY_APPROVED_LIVE_UNAUTHORIZED"
NEXT_GATE_ID = (
    "W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-PROVIDER-READINESS-AND-PRICING-CORRECTIVE-01-CHATGPT-AUDIT"
)


# ==============================================================================
# 2. REPORT CORRECTION FIREWALL & PRIMARY METRIC AUTHORITY
# ==============================================================================


def validate_primary_metric_tuple(candidate_rates: dict[str, str]) -> None:
    """Reject the erroneous report tuple (0/60, 43/60, 0/60) or any non-authoritative primary tuple."""
    if candidate_rates == REJECTED_ERRONEOUS_REPORT_METRIC_RATES:
        raise PlanBeforeLiveProtocolError(
            "REPORT_CORRECTION_FIREWALL_VIOLATION: Erroneous human-readable report tuple "
            "C1=0/60, C2=43/60, C3=0/60 is NOT authoritative and must never be accepted "
            "as primary DEV-SELECT authority."
        )
    if candidate_rates != AUTHORITATIVE_PRIMARY_METRIC_RATES:
        raise PlanBeforeLiveProtocolError(
            f"Primary DEV-SELECT metric authority mismatch: expected "
            f"{AUTHORITATIVE_PRIMARY_METRIC_RATES}, got {candidate_rates}"
        )


def read_and_crosscheck_primary_metric_authority(
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Independently read primary metrics from manifest and cross-check against freeze receipt."""
    manifest_path = repo_root / PRIMARY_RESULTS_MANIFEST_REL_PATH
    receipt_path = repo_root / PRIMARY_RESULTS_FREEZE_RECEIPT_REL_PATH
    if not manifest_path.is_file():
        raise PlanBeforeLiveProtocolError(
            f"Missing primary results manifest: {PRIMARY_RESULTS_MANIFEST_REL_PATH}"
        )
    if not receipt_path.is_file():
        raise PlanBeforeLiveProtocolError(
            f"Missing primary results freeze receipt: {PRIMARY_RESULTS_FREEZE_RECEIPT_REL_PATH}"
        )

    manifest_raw = normalize_lf_bytes(manifest_path.read_bytes())
    receipt_raw = normalize_lf_bytes(receipt_path.read_bytes())
    manifest_file_sha = sha256_bytes(manifest_raw)
    receipt_file_sha = sha256_bytes(receipt_raw)
    if manifest_file_sha != EXPECTED_PRIMARY_RESULTS_MANIFEST_FILE_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"Primary results manifest file SHA256 mismatch: {manifest_file_sha}"
        )
    if receipt_file_sha != EXPECTED_PRIMARY_RESULTS_FREEZE_RECEIPT_FILE_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"Primary results freeze receipt file SHA256 mismatch: {receipt_file_sha}"
        )

    manifest = json.loads(manifest_raw.decode("utf-8"))
    receipt = json.loads(receipt_raw.decode("utf-8"))
    if (
        manifest.get("results_manifest_sha256")
        != EXPECTED_PRIMARY_RESULTS_MANIFEST_INTERNAL_SHA256
    ):
        raise PlanBeforeLiveProtocolError(
            "Primary results manifest internal SHA256 mismatch."
        )
    if (
        receipt.get("results_freeze_receipt_sha256")
        != EXPECTED_PRIMARY_RESULTS_FREEZE_RECEIPT_INTERNAL_SHA256
    ):
        raise PlanBeforeLiveProtocolError(
            "Primary results freeze receipt internal SHA256 mismatch."
        )
    if (
        receipt.get("results_manifest_file_sha256")
        != EXPECTED_PRIMARY_RESULTS_MANIFEST_FILE_SHA256
        or receipt.get("results_manifest_internal_sha256")
        != EXPECTED_PRIMARY_RESULTS_MANIFEST_INTERNAL_SHA256
    ):
        raise PlanBeforeLiveProtocolError(
            "Freeze receipt -> manifest hash cross-check failed."
        )

    metric_mapping = (
        ("VALID_RUN_AND_SCHEMA", "valid_run_and_schema_counts", "valid_run_and_schema"),
        ("EXACT_GROUNDING_PASS", "exact_grounding_pass_counts", "exact_grounding_pass"),
        ("FINAL_CORE_PASS", "final_core_pass_counts", "final_core_pass"),
    )
    exec_summary = receipt.get("execution_summary", {})
    verified_metrics: dict[str, dict[str, Any]] = {}

    for metric_label, manifest_key, receipt_key in metric_mapping:
        m_by_cand = manifest.get(manifest_key, {}).get("by_candidate", {})
        r_by_cand = exec_summary.get(receipt_key, {}).get("by_candidate", {})
        rates_from_manifest: dict[str, str] = {}
        rates_from_receipt: dict[str, str] = {}
        per_candidate_detail: dict[str, dict[str, Any]] = {}

        for cid in ORDERED_CANDIDATE_IDS:
            m_entry = m_by_cand.get(cid, {})
            r_entry = r_by_cand.get(cid, {})
            if m_entry != r_entry:
                raise PlanBeforeLiveProtocolError(
                    f"Manifest vs freeze receipt mismatch for {metric_label}/{cid}: "
                    f"{m_entry} != {r_entry}"
                )
            pass_count = int(m_entry.get("pass_count", -1))
            denom = int(m_entry.get("denominator", -1))
            rate_frac = str(m_entry.get("rate_fraction", ""))
            if f"{pass_count}/{denom}" != rate_frac or denom != 60:
                raise PlanBeforeLiveProtocolError(
                    f"Invalid pass_count/denominator in {metric_label}/{cid}: {m_entry}"
                )
            rates_from_manifest[cid] = rate_frac
            rates_from_receipt[cid] = str(r_entry.get("rate_fraction", ""))
            per_candidate_detail[cid] = {
                "pass_count": pass_count,
                "fail_count": int(m_entry.get("fail_count", 0)),
                "denominator": denom,
                "rate_fraction": rate_frac,
            }

        validate_primary_metric_tuple(rates_from_manifest)
        validate_primary_metric_tuple(rates_from_receipt)
        verified_metrics[metric_label] = {
            "rates_by_candidate": rates_from_manifest,
            "details_by_candidate": per_candidate_detail,
            "manifest_key": manifest_key,
            "receipt_key": f"execution_summary.{receipt_key}",
            "cross_checked_identical": True,
        }

    # Historical cost cross-check
    m_cost_cells = int(manifest.get("authoritative_cost_cell_count", -1))
    r_cost_cells = int(exec_summary.get("authoritative_cost_cell_count", -1))
    m_cost_total = str(manifest.get("total_canonical_cost_usd", ""))
    r_cost_total = str(exec_summary.get("total_canonical_cost_usd", ""))
    if m_cost_cells != 9 or r_cost_cells != 9:
        raise PlanBeforeLiveProtocolError(
            f"Expected 9 authoritative cost cells in primary DEV-SELECT, got {m_cost_cells}/{r_cost_cells}"
        )
    if m_cost_total != "0.6468966" or r_cost_total != "0.6468966":
        raise PlanBeforeLiveProtocolError(
            f"Expected primary canonical receipt cost 0.6468966 USD, got {m_cost_total}/{r_cost_total}"
        )

    return {
        "source_manifest_relative_path": PRIMARY_RESULTS_MANIFEST_REL_PATH,
        "source_manifest_file_sha256": manifest_file_sha,
        "source_manifest_internal_sha256": manifest["results_manifest_sha256"],
        "cross_check_receipt_relative_path": PRIMARY_RESULTS_FREEZE_RECEIPT_REL_PATH,
        "cross_check_receipt_file_sha256": receipt_file_sha,
        "cross_check_receipt_internal_sha256": receipt[
            "results_freeze_receipt_sha256"
        ],
        "verified_metrics": verified_metrics,
        "rejected_erroneous_report_tuple": REJECTED_ERRONEOUS_REPORT_METRIC_RATES,
        "rejected_erroneous_report_status": "REJECTED_NOT_AUTHORITATIVE",
        "historical_primary_cost_reference": {
            "authoritative_cost_cells": m_cost_cells,
            "total_canonical_cost_usd": m_cost_total,
            "cost_by_candidate_usd": manifest.get("cost_by_candidate_usd"),
            "cost_accounting_label": manifest.get("cost_accounting_label"),
        },
    }


# ==============================================================================
# 3. BILLING SURFACE RESOLUTION (SECTION 6)
# ==============================================================================


def resolve_google_billing_surface_or_fail_closed(
    *,
    vertexai_enabled: bool,
    endpoint_path: str,
    observed_quota_metric: str,
    observed_rate_limit_doc_url: str,
) -> dict[str, str]:
    """Fail-closed guard for Google billing surface selection (Section 6 & 7).

    Does NOT infer Gemini Developer API merely from `google-genai` SDK name.
    Requires consistent proof from client initialization (`vertexai=False`),
    endpoint path (`/v1beta/models/gemini-3.8-flash:generateContent`), and
    primary provider error metadata (`generativelanguage.googleapis.com`).
    """
    is_developer_api = (
        not vertexai_enabled
        and endpoint_path == "/v1beta/models/gemini-3.8-flash:generateContent"
        and observed_quota_metric.startswith("generativelanguage.googleapis.com/")
        and observed_rate_limit_doc_url.startswith("https://ai.google.dev/")
    )
    is_vertex_ai = (
        vertexai_enabled
        or "aiplatform.googleapis.com" in observed_quota_metric
        or "cloud.google.com" in observed_rate_limit_doc_url
    )
    if not is_developer_api or is_vertex_ai:
        return {
            "billing_surface_status": "BILLING_SURFACE_NOT_YET_DETERMINISTICALLY_RESOLVED",
            "pricing_status": "BILLING_SURFACE_NOT_YET_DETERMINISTICALLY_RESOLVED",
            "selected_billing_surface": "UNRESOLVED",
        }
    return {
        "billing_surface_status": "DETERMINISTICALLY_RESOLVED_GEMINI_DEVELOPER_API_STANDARD",
        "pricing_status": "SELECTED_APPLICABLE_TO_FROZEN_W06_CONFIG",
        "selected_billing_surface": "GEMINI_DEVELOPER_API_GOOGLE_AI_STUDIO_STANDARD_PAID_TIER",
    }


def inspect_billing_surfaces_from_repo(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Inspect repository code and frozen primary request/response artifacts without reading .env."""
    runner_path = repo_root / "apps/ai-service/app/evaluation/dev_live_runner.py"
    google_adapter_path = (
        repo_root / "apps/ai-service/app/evaluation/model_preflight/google_adapter.py"
    )
    openai_adapter_path = (
        repo_root / "apps/ai-service/app/evaluation/model_preflight/openai_adapter.py"
    )
    anthropic_adapter_path = (
        repo_root
        / "apps/ai-service/app/evaluation/model_preflight/anthropic_adapter.py"
    )

    runner_src = runner_path.read_text(encoding="utf-8")
    google_adapter_src = google_adapter_path.read_text(encoding="utf-8")
    openai_adapter_src = openai_adapter_path.read_text(encoding="utf-8")
    anthropic_adapter_src = anthropic_adapter_path.read_text(encoding="utf-8")

    # Verify C1 Google code + primary transport evidence
    if "genai.Client(" not in runner_src or "vertexai=True" in runner_src:
        raise PlanBeforeLiveProtocolError(
            "Unexpected Google client initialization in dev_live_runner.py"
        )
    if (
        "/v1beta/models/{model}:generateContent" not in google_adapter_src
        or 'requested_model_id = "gemini-3.8-flash"' not in google_adapter_src
    ):
        raise PlanBeforeLiveProtocolError(
            "Expected Gemini Developer API endpoint not found in google_adapter.py"
        )

    c1_429_meta_path = (
        repo_root
        / "data/evaluation/w06/live_dev_select_primary_v1"
        / "W06-DEV-SELECT-P1-C1-W06-DEV-SELECT-027"
        / "provider_response_metadata.json"
    )
    c1_429_meta = json.loads(c1_429_meta_path.read_text(encoding="utf-8"))
    c1_429_msg = str(
        c1_429_meta.get("raw_provider_metadata", {}).get(
            "error_detail_sanitized", ""
        )
    )
    if (
        "generativelanguage.googleapis.com/generate_content_free_tier_requests"
        not in c1_429_msg
        or "https://ai.google.dev/gemini-api/docs/rate-limits" not in c1_429_msg
    ):
        raise PlanBeforeLiveProtocolError(
            "Primary C1 429 metadata missing expected generativelanguage.googleapis.com proof."
        )

    c1_ok_meta_path = (
        repo_root
        / "data/evaluation/w06/live_dev_select_primary_v1"
        / "W06-DEV-SELECT-P1-C1-W06-DEV-SELECT-026"
        / "provider_response_metadata.json"
    )
    c1_ok_meta = json.loads(c1_ok_meta_path.read_text(encoding="utf-8"))
    c1_resolution = resolve_google_billing_surface_or_fail_closed(
        vertexai_enabled=False,
        endpoint_path="/v1beta/models/gemini-3.8-flash:generateContent",
        observed_quota_metric="generativelanguage.googleapis.com/generate_content_free_tier_requests",
        observed_rate_limit_doc_url="https://ai.google.dev/gemini-api/docs/rate-limits",
    )
    if (
        c1_resolution["pricing_status"]
        != "SELECTED_APPLICABLE_TO_FROZEN_W06_CONFIG"
    ):
        raise PlanBeforeLiveProtocolError(
            f"Google billing surface ambiguous: {c1_resolution}"
        )

    # Verify C2 OpenAI code + primary transport evidence
    if "/v1/chat/completions" not in openai_adapter_src:
        raise PlanBeforeLiveProtocolError(
            "Expected /v1/chat/completions endpoint not found in openai_adapter.py"
        )
    c2_ok_meta_path = (
        repo_root
        / "data/evaluation/w06/live_dev_select_primary_v1"
        / "W06-DEV-SELECT-P1-C2-W06-DEV-SELECT-001"
        / "provider_response_metadata.json"
    )
    c2_ok_meta = json.loads(c2_ok_meta_path.read_text(encoding="utf-8"))
    c2_service_tier = c2_ok_meta.get("raw_provider_metadata", {}).get(
        "service_tier"
    )
    if c2_service_tier != "default":
        raise PlanBeforeLiveProtocolError(
            f"Expected C2 service_tier='default', got {c2_service_tier}"
        )

    # Verify C3 Anthropic code + primary DEV-TUNE transport evidence
    if "/v1/messages" not in anthropic_adapter_src:
        raise PlanBeforeLiveProtocolError(
            "Expected /v1/messages endpoint not found in anthropic_adapter.py"
        )
    c3_ok_rec_path = (
        repo_root
        / "data/evaluation/w06/live_dev_tune_primary_v1"
        / "W06-DEV-TUNE-P1-C3-W06-DEV-TUNE-011"
        / "execution_receipt.json"
    )
    c3_ok_rec = json.loads(c3_ok_rec_path.read_text(encoding="utf-8"))
    c3_raw_usage = c3_ok_rec.get("raw_usage_metadata", {})
    if (
        c3_raw_usage.get("service_tier") != "standard"
        or c3_ok_rec.get("cache_creation_input_tokens") != 0
        or c3_ok_rec.get("cache_read_input_tokens") != 0
    ):
        raise PlanBeforeLiveProtocolError(
            f"Unexpected C3 service_tier or cache token usage: {c3_raw_usage}"
        )

    return {
        "env_file_read": False,
        "api_keys_inspected": False,
        "candidates": {
            "C1": {
                "candidate_id": "C1",
                "provider": "GOOGLE",
                "exact_model_id": "gemini-3.8-flash",
                "sdk_package": "google-genai==2.25.0",
                "adapter_entrypoints": [
                    "apps/ai-service/app/evaluation/dev_live_runner.py::_invoke_c1_google_production",
                    "apps/ai-service/app/evaluation/dev_live_runner.py::GoogleGeminiProductionTransport",
                    "apps/ai-service/app/evaluation/model_preflight/google_adapter.py::build_c1_preflight_request_manifest",
                ],
                "api_product_billing_surface": c1_resolution[
                    "selected_billing_surface"
                ],
                "billing_surface_status": c1_resolution["billing_surface_status"],
                "pricing_status": c1_resolution["pricing_status"],
                "request_endpoint_family": "POST https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent",
                "vertex_ai_or_google_cloud_surface_used": False,
                "transport_proof_without_secrets": [
                    "dev_live_runner.py instantiates google.genai.Client(api_key=..., http_options=...) without vertexai=True (defaulting to vertexai=False, which routes to generativelanguage.googleapis.com rather than *-aiplatform.googleapis.com).",
                    "google_adapter.py explicitly binds endpoint = '/v1beta/models/gemini-3.8-flash:generateContent' and client_method = 'client.models.generate_content'.",
                    "Primary DEV-SELECT execution evidence (e.g. W06-DEV-SELECT-P1-C1-W06-DEV-SELECT-027/provider_response_metadata.json) records quotaMetric = 'generativelanguage.googleapis.com/generate_content_free_tier_requests', quotaId = 'GenerateRequestsPerDayPerProjectPerModel-FreeTier', and official link 'https://ai.google.dev/gemini-api/docs/rate-limits'.",
                    "Completed C1 response metadata (W06-DEV-SELECT-P1-C1-W06-DEV-SELECT-026/provider_response_metadata.json) records traffic_type = null and model_version = 'gemini-3.8-flash'.",
                ],
                "service_tier_or_processing_mode": "SYNCHRONOUS_STANDARD_ON_DEMAND (traffic_type=null; Batch/Flex/Priority disabled)",
                "prompt_caching_enabled": False,
                "prompt_caching_detail": "Explicit context caching is disabled (cached_content is not configured in GenerateContentConfig; cached_content_token_count=null in observed usage). Implicit caching is not relied upon; 100% of input tokens are priced at the uncached standard rate.",
                "batch_flex_priority_fast_mode_enabled": False,
                "tools_or_grounding_enabled": False,
                "thinking_configuration": {
                    "thinking_level": "medium",
                    "include_thoughts": False,
                    "thought_tokens_billed_as_output": True,
                },
                "long_context_surcharge_applicability": "NOT_APPLICABLE (Official Gemini 3.8 Flash pricing on ai.google.dev has a single flat per-1M rate up to the 1,048,576 input-token window).",
                "observed_primary_traffic_type": c1_ok_meta.get("usage", {}).get(
                    "traffic_type"
                ),
            },
            "C2": {
                "candidate_id": "C2",
                "provider": "OPENAI",
                "exact_model_id": "gpt-6.1-sol",
                "sdk_package": "openai==3.17.0",
                "adapter_entrypoints": [
                    "apps/ai-service/app/evaluation/dev_live_runner.py::_invoke_c2_openai_production",
                    "apps/ai-service/app/evaluation/dev_live_runner.py::OpenAIChatCompletionsProductionTransport",
                    "apps/ai-service/app/evaluation/model_preflight/openai_adapter.py::build_c2_preflight_request_manifest",
                ],
                "api_product_billing_surface": "OPENAI_STANDARD_API_CHAT_COMPLETIONS_DEFAULT_SERVICE_TIER",
                "billing_surface_status": "DETERMINISTICALLY_RESOLVED_OPENAI_STANDARD_API_DEFAULT_TIER",
                "pricing_status": "SELECTED_APPLICABLE_TO_FROZEN_W06_CONFIG",
                "request_endpoint_family": "POST https://api.openai.com/v1/chat/completions",
                "transport_proof_without_secrets": [
                    "dev_live_runner.py instantiates openai.OpenAI(api_key=..., timeout=..., max_retries=0) and calls client.chat.completions.create with service_tier='default'.",
                    "openai_adapter.py binds endpoint = '/v1/chat/completions' and service_tier = 'default'.",
                    "Completed C2 response metadata (e.g. W06-DEV-SELECT-P1-C2-W06-DEV-SELECT-001/provider_response_metadata.json) confirms service_tier = 'default' and model = 'gpt-6.1-sol-2026-08-05'.",
                ],
                "service_tier_or_processing_mode": "STANDARD_DEFAULT (service_tier='default' explicitly pinned in request and verified in response metadata)",
                "prompt_caching_enabled": False,
                "prompt_caching_detail": "Explicit cache retention/write parameters are not configured. Provider-automatic prompt caching is conservatively assumed to be 0% (cached_tokens=0 in all 12 observed P1 C2 cells); 100% of input tokens are priced at the uncached Standard rate ($2.00 / 1M).",
                "batch_flex_priority_fast_mode_enabled": False,
                "tools_or_grounding_enabled": False,
                "thinking_configuration": {
                    "reasoning_effort": "medium",
                    "reasoning_tokens_included_in_completion_tokens": True,
                },
                "long_context_surcharge_applicability": OPENAI_LONG_CONTEXT_SURCHARGE_STATUS,
            },
            "C3": {
                "candidate_id": "C3",
                "provider": "ANTHROPIC",
                "exact_model_id": "claude-sonnet-5-5",
                "sdk_package": "anthropic==1.15.0",
                "adapter_entrypoints": [
                    "apps/ai-service/app/evaluation/dev_live_runner.py::_invoke_c3_anthropic_production",
                    "apps/ai-service/app/evaluation/dev_live_runner.py::AnthropicMessagesProductionTransport",
                    "apps/ai-service/app/evaluation/model_preflight/anthropic_adapter.py::build_c3_preflight_request_manifest",
                ],
                "api_product_billing_surface": "ANTHROPIC_CLAUDE_API_FIRST_PARTY_DIRECT_MESSAGES_STANDARD_GLOBAL",
                "billing_surface_status": "DETERMINISTICALLY_RESOLVED_ANTHROPIC_CLAUDE_API_STANDARD",
                "pricing_status": "SELECTED_APPLICABLE_TO_FROZEN_W06_CONFIG",
                "request_endpoint_family": "POST https://api.anthropic.com/v1/messages",
                "transport_proof_without_secrets": [
                    "dev_live_runner.py instantiates anthropic.Anthropic(api_key=..., timeout=..., max_retries=0) and calls client.messages.create without cache_control, speed, or inference_geo parameters.",
                    "anthropic_adapter.py binds endpoint = '/v1/messages' and client_method = 'client.messages.create'.",
                    "Completed C3 DEV-TUNE P1 execution receipts (e.g. W06-DEV-TUNE-P1-C3-W06-DEV-TUNE-011/execution_receipt.json) confirm raw_usage_metadata.service_tier = 'standard', inference_geo = 'not_available' (global routing), cache_creation_input_tokens = 0, and cache_read_input_tokens = 0.",
                ],
                "service_tier_or_processing_mode": "STANDARD_SYNCHRONOUS_GLOBAL (service_tier='standard'; Batch, fast mode, and US-only inference_geo='us' 1.1x multiplier not used)",
                "prompt_caching_enabled": False,
                "prompt_caching_detail": "No cache_control breakpoints are included in frozen C3 system or user message payloads (cache_creation_input_tokens=0 and cache_read_input_tokens=0 across all 33 completed C3 DEV-TUNE cells). Cache write/read rates are excluded from the selected C3 cost equation.",
                "batch_flex_priority_fast_mode_enabled": False,
                "tools_or_grounding_enabled": False,
                "thinking_configuration": {
                    "thinking": {"type": "adaptive"},
                    "output_config_effort": "high",
                    "thinking_tokens_included_in_output_tokens": True,
                },
                "long_context_surcharge_applicability": "NOT_APPLICABLE (Official Claude API pricing includes the full 1M context window at standard pricing for Claude Sonnet 5.5).",
            },
        },
    }


# ==============================================================================
# 4. PUBLIC PRICING SNAPSHOT BUILDER & SOURCE AUTHORITY GUARD (SECTIONS 5, 7, 8)
# ==============================================================================


def _host_matches_domain_tuple(host: str, allowed_domains: tuple[str, ...]) -> bool:
    return any(host == d or host.endswith("." + d) for d in allowed_domains)


def validate_pricing_source_urls(records: dict[str, dict[str, Any]]) -> None:
    """Enforce frozen direct source domain allowlist and subordinate redirect rules.

    - Direct authority URLs (`official_source_url`, `exact_model_official_source_url`,
      `additional_official_source_urls`) MUST belong to `ALLOWLISTED_PRICING_DOMAINS_BY_PROVIDER[provider]`.
    - For Anthropic, only `docs.anthropic.com` and `anthropic.com` (including `www.anthropic.com`)
      are valid direct authority domains. An arbitrary direct `platform.claude.com` URL is REJECTED.
    - `platform.claude.com` is accepted ONLY inside `official_redirect_resolutions` when bound to
      an already-allowlisted `docs.anthropic.com` source URL present in the candidate's direct source list.
    """
    for cid, rec in records.items():
        provider = str(rec.get("provider", ""))
        allowed_domains = ALLOWLISTED_PRICING_DOMAINS_BY_PROVIDER.get(provider, ())
        if not allowed_domains:
            raise PlanBeforeLiveProtocolError(
                f"Unknown provider in pricing snapshot for {cid}: {provider}"
            )

        direct_urls: list[str] = [str(rec.get("official_source_url", ""))]
        if rec.get("exact_model_official_source_url") is not None:
            direct_urls.append(str(rec.get("exact_model_official_source_url", "")))
        direct_urls.extend(
            str(u) for u in rec.get("additional_official_source_urls", [])
        )

        for url in direct_urls:
            parsed = urlparse(url)
            host = (parsed.hostname or "").lower()
            if parsed.scheme != "https" or not host:
                raise PlanBeforeLiveProtocolError(
                    f"Invalid pricing source URL for {cid}: {url}"
                )
            if provider == "GOOGLE" and (
                host == FORBIDDEN_GOOGLE_CLOUD_DOMAIN
                or host.endswith("." + FORBIDDEN_GOOGLE_CLOUD_DOMAIN)
            ):
                raise PlanBeforeLiveProtocolError(
                    f"cloud.google.com is forbidden for C1 because frozen C1 transport uses Gemini Developer API (ai.google.dev), not Google Cloud/Vertex AI: {url}"
                )
            if not _host_matches_domain_tuple(host, allowed_domains):
                raise PlanBeforeLiveProtocolError(
                    f"Disallowed direct pricing authority domain '{host}' for {cid} ({provider}); allowed direct domains: {allowed_domains}"
                )

        # Validate optional subordinate redirect resolutions
        direct_url_set = set(direct_urls)
        for redirect_entry in rec.get("official_redirect_resolutions", []):
            src_url = str(redirect_entry.get("allowlisted_source_url", ""))
            dst_url = str(redirect_entry.get("resolved_destination_url", ""))
            if src_url not in direct_url_set:
                raise PlanBeforeLiveProtocolError(
                    f"Redirect source URL '{src_url}' for {cid} is not bound to an allowlisted direct source URL in {direct_urls}"
                )
            src_parsed = urlparse(src_url)
            dst_parsed = urlparse(dst_url)
            src_host = (src_parsed.hostname or "").lower()
            dst_host = (dst_parsed.hostname or "").lower()
            if dst_parsed.scheme != "https" or not dst_host:
                raise PlanBeforeLiveProtocolError(
                    f"Invalid redirect destination URL for {cid}: {dst_url}"
                )
            allowed_redirect_targets = (
                ALLOWED_REDIRECT_TARGET_DOMAINS_BY_SOURCE_DOMAIN.get(src_host, ())
            )
            if not _host_matches_domain_tuple(dst_host, allowed_redirect_targets):
                raise PlanBeforeLiveProtocolError(
                    f"Disallowed redirect destination domain '{dst_host}' from source '{src_host}' for {cid}; allowed redirect targets: {allowed_redirect_targets}"
                )


def build_public_pricing_snapshot_payload() -> dict[str, Any]:
    """Construct the canonical machine-readable public pricing snapshot artifact (Section 7 & 8)."""
    candidate_records: dict[str, dict[str, Any]] = {
        "C1": {
            "candidate_id": "C1",
            "provider": "GOOGLE",
            "exact_model_id": "gemini-3.8-flash",
            "official_source_url": "https://ai.google.dev/gemini-api/docs/pricing",
            "exact_model_official_source_url": "https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash",
            "additional_official_source_urls": [
                "https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash",
                "https://ai.google.dev/gemini-api/docs/rate-limits",
            ],
            "official_redirect_resolutions": [],
            "retrieval_timestamp_utc": "2026-10-25T03:05:48Z",
            "source_retrieval_timestamps_utc": {
                "https://ai.google.dev/gemini-api/docs/pricing": "2026-10-25T03:05:48Z",
                "https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash": "2026-10-25T03:05:48Z",
                "https://ai.google.dev/gemini-api/docs/rate-limits": "2026-10-25T03:05:08Z",
            },
            "pricing_effective_date": "Current promotional pricing effective through 2026-12-31 (scheduled standard adjustment on 2027-01-01)",
            "promotional_expiration_date": "2026-12-31",
            "post_promotional_effective_date": "2027-01-01",
            "currency": "USD",
            "pricing_surface_product": "Gemini Developer API (Google AI Studio / generativelanguage.googleapis.com) — Standard Paid Tier (Synchronous generateContent)",
            "selected_as_applicable_to_frozen_w06_config": True,
            "evidence_status": "VERIFIED_OFFICIAL_PUBLIC_DOCUMENTATION",
            "selected_unit_pricing_usd_per_1m_tokens": {
                "input_usd_per_1m_tokens": "0.75",
                "output_including_thinking_usd_per_1m_tokens": "3.75",
            },
            "post_2026_12_31_scheduled_unit_pricing_usd_per_1m_tokens": {
                "effective_date": "2027-01-01",
                "input_usd_per_1m_tokens": "1.50",
                "output_including_thinking_usd_per_1m_tokens": "7.50",
                "applicable_during_2026_execution": False,
            },
            "non_applicable_pricing_dimensions": {
                "context_caching": {
                    "applicable_to_frozen_w06_config": False,
                    "reason": "Explicit context caching (cached_content) is not enabled in the frozen C1 wire request.",
                    "cached_input_usd_per_1m_tokens_through_2026_12_31": "0.075",
                    "cached_input_usd_per_1m_tokens_from_2027_01_01": "0.15",
                    "cache_storage_usd_per_1m_tokens_per_hour_through_2026_12_31": "0.50",
                    "cache_storage_usd_per_1m_tokens_per_hour_from_2027_01_01": "1.00",
                },
                "batch_or_flex_tier": {
                    "applicable_to_frozen_w06_config": False,
                    "reason": "Frozen W06 runner executes synchronous on-demand generateContent calls, not Batch or Flex jobs.",
                    "batch_input_usd_per_1m_tokens_through_2026_12_31": "0.375",
                    "batch_output_usd_per_1m_tokens_through_2026_12_31": "1.875",
                },
                "long_context_surcharge": {
                    "applicable_to_frozen_w06_config": False,
                    "rule": "None stated for gemini-3.8-flash up to its 1,048,576 input-token window.",
                },
                "free_tier": {
                    "applicable_to_frozen_w06_config": False,
                    "reason": "Free Tier ($0.00) is subject to the 20-RPD quota ceiling that caused 35 HTTP_429 failures in primary DEV-SELECT; amended execution requires Standard Paid Tier.",
                },
            },
            "note_on_stale_repo_rate_table": (
                "Frozen primary runner (dev_live_runner.py) contains a historical 2026-10-16 rate constant "
                "($0.30 input / $2.50 output per 1M). Per Section 7, this PREP package uses the current official "
                "ai.google.dev Standard Paid promotional pricing ($0.75 input / $3.75 output per 1M through 2026-12-31) "
                "without mutating dev_live_runner.py."
            ),
        },
        "C2": {
            "candidate_id": "C2",
            "provider": "OPENAI",
            "exact_model_id": "gpt-6.1-sol",
            "official_source_url": "https://developers.openai.com/api/docs/pricing",
            "exact_model_official_source_url": "https://developers.openai.com/api/docs/models/gpt-6.1-sol",
            "additional_official_source_urls": [
                "https://developers.openai.com/api/docs/models/gpt-6.1-sol",
                "https://developers.openai.com/api/docs/guides/rate-limits",
            ],
            "official_redirect_resolutions": [],
            "retrieval_timestamp_utc": "2026-10-25T03:05:50Z",
            "source_retrieval_timestamps_utc": {
                "https://developers.openai.com/api/docs/pricing": "2026-10-25T03:05:50Z",
                "https://developers.openai.com/api/docs/models/gpt-6.1-sol": "2026-10-25T03:05:50Z",
                "https://developers.openai.com/api/docs/guides/rate-limits": "2026-10-25T03:05:50Z",
            },
            "pricing_effective_date": "Current published Standard tier pricing (model snapshot gpt-6.1-sol-2026-08-05)",
            "promotional_expiration_date": None,
            "currency": "USD",
            "pricing_surface_product": "OpenAI Standard API (api.openai.com /v1/chat/completions) — Standard Processing (service_tier='default'), Short Context (<= 272,000 input tokens)",
            "selected_as_applicable_to_frozen_w06_config": True,
            "evidence_status": "VERIFIED_OFFICIAL_PUBLIC_DOCUMENTATION",
            "selected_unit_pricing_usd_per_1m_tokens": {
                "input_usd_per_1m_tokens": "2.00",
                "output_including_reasoning_usd_per_1m_tokens": "10.00",
                "cached_input_usd_per_1m_tokens": "0.10",
                "cached_input_planning_assumption": "0% cached tokens assumed for conservative cost planning (100% of input tokens billed at $2.00 / 1M).",
            },
            "non_applicable_pricing_dimensions": {
                "long_context_over_272k_input_tokens": {
                    "applicable_to_frozen_w06_config": False,
                    "surcharge_status": OPENAI_LONG_CONTEXT_SURCHARGE_STATUS,
                    "threshold_input_tokens": OPENAI_LONG_CONTEXT_THRESHOLD_INPUT_TOKENS,
                    "rule": "For requests with >272,000 input tokens, input/cache tokens are charged at 2x ($4.00 / 1M uncached input, $0.20 / 1M cached input) and output tokens at 1.5x ($15.00 / 1M output) for the full request.",
                    "reason": "Proven NOT_APPLICABLE_PROVEN: maximum serialized UTF-8 wire request across all 63 frozen W06 fixtures is 89,435 bytes (<89,435 tokens under any byte-level BPE tokenizer, and empirical prompt_tokens across 12 completed P1 C2 cells is 16,086..29,633 tokens, <11% of 272,000).",
                },
                "explicit_cache_write": {
                    "applicable_to_frozen_w06_config": False,
                    "cache_write_30m_usd_per_1m_tokens": "2.50",
                    "cache_write_12h_usd_per_1m_tokens": "5.00",
                    "reason": "Frozen C2 request does not configure explicit cache retention writes.",
                },
                "batch_or_flex_or_fast_or_ultrafast_tiers": {
                    "applicable_to_frozen_w06_config": False,
                    "reason": "Frozen C2 wire request explicitly pins service_tier='default'.",
                    "batch_or_flex_input_usd_per_1m_tokens": "1.00",
                    "batch_or_flex_output_usd_per_1m_tokens": "5.00",
                    "fast_input_usd_per_1m_tokens": "4.00",
                    "fast_output_usd_per_1m_tokens": "20.00",
                    "ultrafast_input_usd_per_1m_tokens": "12.00",
                    "ultrafast_output_usd_per_1m_tokens": "60.00",
                },
                "regional_data_residency_surcharge": {
                    "applicable_to_frozen_w06_config": False,
                    "multiplier": "1.10",
                    "reason": "Standard global api.openai.com endpoint is used without regional residency routing.",
                },
            },
            "note_on_stale_repo_rate_table": (
                "Frozen primary runner (dev_live_runner.py) contains a historical 2026-10-16 rate constant "
                "($2.50 input / $10.00 output per 1M). Per Section 7, this PREP package uses the current official "
                "developers.openai.com Standard pricing ($2.00 input / $10.00 output per 1M) without mutating dev_live_runner.py."
            ),
        },
        "C3": {
            "candidate_id": "C3",
            "provider": "ANTHROPIC",
            "exact_model_id": "claude-sonnet-5-5",
            "official_source_url": "https://docs.anthropic.com/en/docs/about-claude/pricing",
            "exact_model_official_source_url": "https://www.anthropic.com/claude/sonnet",
            "additional_official_source_urls": [
                "https://www.anthropic.com/claude/sonnet",
                "https://www.anthropic.com/claude-sonnet-5-5",
                "https://docs.anthropic.com/en/api/rate-limits",
            ],
            "official_redirect_resolutions": [
                {
                    "allowlisted_source_url": "https://docs.anthropic.com/en/docs/about-claude/pricing",
                    "resolved_destination_url": "https://platform.claude.com/docs/en/about-claude/pricing",
                    "authority_rule": "platform.claude.com is recorded strictly as the HTTP 308 redirect destination of the allowlisted docs.anthropic.com URL and is NOT an independent direct authority domain.",
                },
                {
                    "allowlisted_source_url": "https://docs.anthropic.com/en/api/rate-limits",
                    "resolved_destination_url": "https://platform.claude.com/docs/en/api/rate-limits",
                    "authority_rule": "platform.claude.com is recorded strictly as the HTTP 308 redirect destination of the allowlisted docs.anthropic.com URL and is NOT an independent direct authority domain.",
                },
            ],
            "retrieval_timestamp_utc": "2026-10-25T03:05:51Z",
            "source_retrieval_timestamps_utc": {
                "https://docs.anthropic.com/en/docs/about-claude/pricing": "2026-10-25T03:05:51Z",
                "https://docs.anthropic.com/en/api/rate-limits": "2026-10-25T03:05:54Z",
                "https://www.anthropic.com/claude/sonnet": "2026-10-25T03:58:45Z",
                "https://www.anthropic.com/claude-sonnet-5-5": "2026-10-25T03:58:46Z",
            },
            "exact_model_anthropic_com_evidence": {
                "model_page_url": "https://www.anthropic.com/claude/sonnet",
                "announcement_page_url": "https://www.anthropic.com/claude-sonnet-5-5",
                "announcement_published_date": "2026-09-28",
                "verified_api_model_id": "claude-sonnet-5-5",
                "verified_input_usd_per_1m_tokens": "2.00",
                "verified_output_usd_per_1m_tokens": "10.00",
                "verified_cache_read_usd_per_1m_tokens_non_applicable": "0.10",
            },
            "pricing_effective_date": "Current published Claude API Standard pricing (Claude Sonnet 5.5 released 2026-09-28)",
            "promotional_expiration_date": None,
            "currency": "USD",
            "pricing_surface_product": "Anthropic Claude API First-Party Direct (api.anthropic.com /v1/messages) — Standard Synchronous Global Routing",
            "selected_as_applicable_to_frozen_w06_config": True,
            "evidence_status": "VERIFIED_OFFICIAL_PUBLIC_DOCUMENTATION",
            "selected_unit_pricing_usd_per_1m_tokens": {
                "input_usd_per_1m_tokens": "2.00",
                "output_including_thinking_usd_per_1m_tokens": "10.00",
            },
            "non_applicable_pricing_dimensions": {
                "prompt_caching": {
                    "applicable_to_frozen_w06_config": False,
                    "reason": "Frozen C3 wire requests send no cache_control breakpoints (cache_creation_input_tokens=0 and cache_read_input_tokens=0 in all 33 completed C3 DEV-TUNE cells). Excluded from selected C3 cost equation per Section 7.",
                    "cache_write_5m_usd_per_1m_tokens": "2.50",
                    "cache_write_1h_usd_per_1m_tokens": "4.00",
                    "cache_read_usd_per_1m_tokens": "0.10",
                },
                "batch_api": {
                    "applicable_to_frozen_w06_config": False,
                    "reason": "Frozen C3 runner uses synchronous /v1/messages, not Batch API.",
                    "batch_input_usd_per_1m_tokens": "1.00",
                    "batch_output_usd_per_1m_tokens": "5.00",
                },
                "us_only_inference_geo_surcharge": {
                    "applicable_to_frozen_w06_config": False,
                    "multiplier": "1.10",
                    "reason": "Frozen C3 wire request does not set inference_geo='us'.",
                },
                "long_context_surcharge": {
                    "applicable_to_frozen_w06_config": False,
                    "rule": "Official Claude API documentation states Claude 4.6 and later models (including Claude Sonnet 5.5) include the full 1M context window at standard pricing.",
                },
            },
            "note_on_stale_repo_rate_table": (
                "Frozen primary runner (dev_live_runner.py) contains a historical 2026-10-16 rate constant "
                "($3.00 input / $15.00 output per 1M). Per Section 7, this PREP package uses the current official "
                "docs.anthropic.com and anthropic.com Standard pricing ($2.00 input / $10.00 output per 1M) without mutating dev_live_runner.py."
            ),
        },
    }

    validate_pricing_source_urls(candidate_records)

    payload: dict[str, Any] = {
        "artifact_id": PUBLIC_PRICING_SNAPSHOT_ARTIFACT_ID,
        "task_id": TASK_ID,
        "corrective_task_id": CORRECTIVE_TASK_ID,
        "authoritative_base_develop_sha": AUTHORITATIVE_BASE_DEVELOP_SHA,
        "approval_receipt_file_sha256": EXPECTED_APPROVAL_RECEIPT_FILE_SHA256,
        "approval_receipt_internal_sha256": EXPECTED_APPROVAL_RECEIPT_INTERNAL_SHA256,
        "decision_artifact_file_sha256": EXPECTED_DECISION_ARTIFACT_FILE_SHA256,
        "decision_artifact_internal_sha256": EXPECTED_DECISION_ARTIFACT_INTERNAL_SHA256,
        "canary_manifest_file_sha256": EXPECTED_CANARY_MANIFEST_FILE_SHA256,
        "canary_manifest_internal_sha256": EXPECTED_CANARY_MANIFEST_INTERNAL_SHA256,
        "scientific_code_bundle_sha256": EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256,
        "snapshot_scope": "CANONICAL_EXTRACTED_PUBLIC_PRICING_FACTS_ONLY",
        "contains_copyrighted_full_webpage_dump": False,
        "allowlisted_domains_by_provider": {
            k: list(v) for k, v in ALLOWLISTED_PRICING_DOMAINS_BY_PROVIDER.items()
        },
        "redirect_target_policy_by_source_domain": {
            k: list(v)
            for k, v in ALLOWED_REDIRECT_TARGET_DOMAINS_BY_SOURCE_DOMAIN.items()
        },
        "forbidden_google_cloud_domain_used": False,
        "candidates": candidate_records,
        "live_provider_calls_new": 0,
        "env_file_read": False,
        "api_keys_inspected": False,
    }
    payload["public_pricing_snapshot_sha256"] = sha256_bytes(
        canonical_json_bytes(payload)
    )
    return payload


# ==============================================================================
# 5. OPENAI LONG-CONTEXT PROOF & EMPIRICAL COST ANALYSIS (SECTIONS 9 & 10)
# ==============================================================================


def _fmt_usd(val: Decimal) -> str:
    return str(val.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def analyze_requests_and_costs(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Inspect frozen wire requests and historical P1 receipts to prove OpenAI <272K and compute cost tables."""
    w06_dir = repo_root / "data/evaluation/w06"
    tune_dir = w06_dir / "live_dev_tune_primary_v1"
    select_dir = w06_dir / "live_dev_select_primary_v1"

    # 1. Inspect all 63 frozen C2 wire requests (3 canary + 60 comparative)
    canary_c2_stats: list[dict[str, Any]] = []
    for fid in CANARY_FIXTURE_IDS:
        req_path = tune_dir / f"W06-DEV-TUNE-P1-C2-{fid}" / "request_manifest.json"
        req = json.loads(req_path.read_text(encoding="utf-8"))
        wire = req["provider_wire_request"]
        wire_bytes = len(
            json.dumps(wire, ensure_ascii=False, sort_keys=True).encode("utf-8")
        )
        sys_b = len(wire["messages"][0]["content"].encode("utf-8"))
        usr_b = len(wire["messages"][1]["content"].encode("utf-8"))
        sch_b = len(
            json.dumps(
                wire["response_format"], ensure_ascii=False, sort_keys=True
            ).encode("utf-8")
        )
        dest_match = re.search(
            r'"destination_slug":\s*"([^"]+)"', wire["messages"][1]["content"]
        )
        dest = dest_match.group(1) if dest_match else "unknown"
        canary_c2_stats.append(
            {
                "fixture_id": fid,
                "destination_slug": dest,
                "wire_payload_utf8_bytes": wire_bytes,
                "system_prompt_utf8_bytes": sys_b,
                "user_prompt_utf8_bytes": usr_b,
                "response_format_schema_utf8_bytes": sch_b,
                "combined_content_and_schema_utf8_bytes": sys_b + usr_b + sch_b,
            }
        )

    comparative_c2_stats: list[dict[str, Any]] = []
    comparative_dest_counts: dict[str, int] = {}
    for idx in range(1, 61):
        fid = f"W06-DEV-SELECT-{idx:03d}"
        req_path = select_dir / f"W06-DEV-SELECT-P1-C2-{fid}" / "request_manifest.json"
        req = json.loads(req_path.read_text(encoding="utf-8"))
        wire = req["provider_wire_request"]
        wire_bytes = len(
            json.dumps(wire, ensure_ascii=False, sort_keys=True).encode("utf-8")
        )
        sys_b = len(wire["messages"][0]["content"].encode("utf-8"))
        usr_b = len(wire["messages"][1]["content"].encode("utf-8"))
        sch_b = len(
            json.dumps(
                wire["response_format"], ensure_ascii=False, sort_keys=True
            ).encode("utf-8")
        )
        dest_match = re.search(
            r'"destination_slug":\s*"([^"]+)"', wire["messages"][1]["content"]
        )
        dest = dest_match.group(1) if dest_match else "unknown"
        comparative_dest_counts[dest] = comparative_dest_counts.get(dest, 0) + 1
        comparative_c2_stats.append(
            {
                "fixture_id": fid,
                "destination_slug": dest,
                "wire_payload_utf8_bytes": wire_bytes,
                "system_prompt_utf8_bytes": sys_b,
                "user_prompt_utf8_bytes": usr_b,
                "response_format_schema_utf8_bytes": sch_b,
                "combined_content_and_schema_utf8_bytes": sys_b + usr_b + sch_b,
            }
        )

    all_63_c2 = canary_c2_stats + comparative_c2_stats
    max_wire_entry = max(all_63_c2, key=lambda x: x["wire_payload_utf8_bytes"])
    min_wire_entry = min(all_63_c2, key=lambda x: x["wire_payload_utf8_bytes"])
    if (
        max_wire_entry["wire_payload_utf8_bytes"]
        >= OPENAI_LONG_CONTEXT_THRESHOLD_INPUT_TOKENS
    ):
        raise PlanBeforeLiveProtocolError(
            f"C2 serialized wire bytes ({max_wire_entry['wire_payload_utf8_bytes']}) exceed 272K threshold!"
        )

    # 2. Collect all completed P1 cells with authoritative_usage_available across DEV_TUNE and DEV_SELECT
    observed_p1_by_candidate: dict[str, list[dict[str, Any]]] = {
        "C1": [],
        "C2": [],
        "C3": [],
    }
    for phase_label, base_dir in (("DEV_TUNE", tune_dir), ("DEV_SELECT", select_dir)):
        for cell_dir in sorted(base_dir.iterdir()):
            if not cell_dir.is_dir() or "-P1-" not in cell_dir.name:
                continue
            rec = json.loads(
                (cell_dir / "execution_receipt.json").read_text(encoding="utf-8")
            )
            if not rec.get("authoritative_usage_available"):
                continue
            req = json.loads(
                (cell_dir / "request_manifest.json").read_text(encoding="utf-8")
            )
            wire = req["provider_wire_request"]
            usr_text = (
                wire.get("contents")
                if isinstance(wire.get("contents"), str)
                else wire["messages"][-1]["content"]
            )
            dest = re.search(r'"destination_slug":\s*"([^"]+)"', usr_text).group(1)
            cid = rec["candidate_id"]
            in_tok = int(rec["input_tokens"])
            out_tok = int(rec["output_tokens"])
            th_tok = int(rec.get("thought_tokens") or 0)
            reas_tok = int(rec.get("reasoning_tokens") or 0)
            billable_out = out_tok + th_tok if cid == "C1" else out_tok
            observed_p1_by_candidate[cid].append(
                {
                    "phase": phase_label,
                    "run_id": rec["run_id"],
                    "fixture_id": rec["fixture_id"],
                    "destination_slug": dest,
                    "input_tokens": in_tok,
                    "output_tokens": out_tok,
                    "thought_tokens": th_tok if cid == "C1" else None,
                    "reasoning_tokens": reas_tok if cid == "C2" else None,
                    "billable_output_tokens": billable_out,
                    "total_tokens": int(rec["total_tokens"]),
                    "primary_receipt_cost_usd": str(
                        rec.get("canonical_cost_usd_decimal")
                    ),
                }
            )

    if (
        len(observed_p1_by_candidate["C1"]) != 4
        or len(observed_p1_by_candidate["C2"]) != 12
        or len(observed_p1_by_candidate["C3"]) != 16
    ):
        raise PlanBeforeLiveProtocolError(
            "Unexpected count of observed P1 cells with authoritative token usage."
        )

    c2_obs_in = [x["input_tokens"] for x in observed_p1_by_candidate["C2"]]
    openai_long_context_check = {
        "openai_long_context_surcharge_status": OPENAI_LONG_CONTEXT_SURCHARGE_STATUS,
        "threshold_input_tokens": OPENAI_LONG_CONTEXT_THRESHOLD_INPUT_TOKENS,
        "short_context_rates_usd_per_1m": {
            "input": "2.00",
            "output": "10.00",
            "cached_input": "0.10",
        },
        "long_context_over_272k_rates_usd_per_1m": {
            "input": "4.00",
            "output": "15.00",
            "cached_input": "0.20",
        },
        "proof_methods": [
            {
                "method": "DETERMINISTIC_SERIALIZED_WIRE_PAYLOAD_UTF8_BYTE_UPPER_BOUND",
                "inspected_canary_c2_requests": 3,
                "inspected_comparative_c2_requests": 60,
                "total_inspected_frozen_c2_requests": 63,
                "canary_wire_payload_utf8_bytes_by_fixture": {
                    x["fixture_id"]: x["wire_payload_utf8_bytes"]
                    for x in canary_c2_stats
                },
                "comparative_wire_payload_utf8_bytes_min": min_wire_entry[
                    "wire_payload_utf8_bytes"
                ],
                "comparative_wire_payload_utf8_bytes_max": max_wire_entry[
                    "wire_payload_utf8_bytes"
                ],
                "comparative_max_fixture_id": max_wire_entry["fixture_id"],
                "comparative_combined_content_and_schema_utf8_bytes_min": min(
                    x["combined_content_and_schema_utf8_bytes"] for x in all_63_c2
                ),
                "comparative_combined_content_and_schema_utf8_bytes_max": max(
                    x["combined_content_and_schema_utf8_bytes"] for x in all_63_c2
                ),
                "justification": (
                    "Every OpenAI byte-level BPE tokenizer encodes UTF-8 byte sequences by merging single-byte base tokens "
                    "(so token_count <= utf8_byte_count + small fixed message/schema framing overhead). Across all 63 frozen C2 "
                    "requests (3 canary + 60 comparative), the maximum total serialized provider_wire_request JSON size is "
                    "89,435 UTF-8 bytes (and maximum combined system_prompt + user_prompt + response_format JSON schema is "
                    "79,332 UTF-8 bytes on fixture W06-DEV-SELECT-032). Even under the theoretical worst-case 1-token-per-UTF-8-byte "
                    "bound, input tokens cannot exceed ~90,000 tokens, which is <33.1% of the 272,000 input-token threshold "
                    "(at least 182,565 tokens below 272,000)."
                ),
            },
            {
                "method": "EMPIRICAL_PROVIDER_USAGE_ACROSS_ALL_THREE_FROZEN_DEV_DESTINATIONS",
                "observed_p1_c2_cell_count": len(c2_obs_in),
                "observed_prompt_tokens_min": min(c2_obs_in),
                "observed_prompt_tokens_max": max(c2_obs_in),
                "observed_prompt_tokens_by_destination": {
                    "ha-noi": {
                        "cell_count": 5,
                        "min_input_tokens": 16086,
                        "max_input_tokens": 16115,
                    },
                    "ha-long": {
                        "cell_count": 5,
                        "min_input_tokens": 19785,
                        "max_input_tokens": 19823,
                    },
                    "da-nang": {
                        "cell_count": 2,
                        "min_input_tokens": 29631,
                        "max_input_tokens": 29633,
                    },
                },
                "justification": (
                    "Authoritative gpt-6.1-sol usage metadata under locked prompt P1 and portable_schema_v2 exists for all "
                    "three frozen DEV destinations (ha-noi, ha-long, da-nang). Even on the largest catalog (da-nang, ~74.5 KB user prompt), "
                    "provider-reported prompt_tokens is 29,631..29,633 tokens (10.89% of the 272,000 threshold)."
                ),
            },
        ],
    }

    # 3. Cost calculations under current official public pricing
    c1_in_rate = Decimal("0.75") / Decimal("1000000")
    c1_out_rate = Decimal("3.75") / Decimal("1000000")
    c2_in_rate = Decimal("2.00") / Decimal("1000000")
    c2_out_rate = Decimal("10.00") / Decimal("1000000")
    c3_in_rate = Decimal("2.00") / Decimal("1000000")
    c3_out_rate = Decimal("10.00") / Decimal("1000000")

    c1_emp_in_per_call = Decimal("29180.5")
    c1_emp_out_per_call = Decimal("5718.25")
    c1_emp_cost_per_call = (
        c1_emp_in_per_call * c1_in_rate + c1_emp_out_per_call * c1_out_rate
    )

    c2_emp_in_per_call = (
        Decimal("16098.0") + Decimal("29632.0") + Decimal("19803.6")
    ) / Decimal("3")
    c2_emp_out_per_call = Decimal("2742.0")
    c2_emp_cost_per_call = (
        c2_emp_in_per_call * c2_in_rate + c2_emp_out_per_call * c2_out_rate
    )

    c3_emp_in_per_call = (
        Decimal("23642.8")
        + Decimal("41151.6")
        + (Decimal("170645") / Decimal("6"))
    ) / Decimal("3")
    c3_emp_out_per_call = Decimal("98289") / Decimal("16")
    c3_emp_cost_per_call = (
        c3_emp_in_per_call * c3_in_rate + c3_emp_out_per_call * c3_out_rate
    )

    c1_cons_per_call = Decimal("40000") * c1_in_rate + Decimal("10000") * c1_out_rate
    c2_cons_per_call = Decimal("32000") * c2_in_rate + Decimal("8000") * c2_out_rate
    c3_cons_per_call = Decimal("42000") * c3_in_rate + Decimal("10000") * c3_out_rate

    c1_maxref_per_call = Decimal("40000") * c1_in_rate + Decimal("16384") * c1_out_rate
    c2_maxref_per_call = Decimal("32000") * c2_in_rate + Decimal("16384") * c2_out_rate
    c3_maxref_per_call = Decimal("42000") * c3_in_rate + Decimal("16384") * c3_out_rate

    def _build_scope_cost_block(
        scope_id: str, total_calls: int, calls_per_candidate: int
    ) -> dict[str, Any]:
        mult = Decimal(calls_per_candidate)
        emp_c1 = mult * c1_emp_cost_per_call
        emp_c2 = mult * c2_emp_cost_per_call
        emp_c3 = mult * c3_emp_cost_per_call
        emp_tot = emp_c1 + emp_c2 + emp_c3

        cons_c1 = mult * c1_cons_per_call
        cons_c2 = mult * c2_cons_per_call
        cons_c3 = mult * c3_cons_per_call
        cons_tot = cons_c1 + cons_c2 + cons_c3

        mref_c1 = mult * c1_maxref_per_call
        mref_c2 = mult * c2_maxref_per_call
        mref_c3 = mult * c3_maxref_per_call
        mref_tot = mref_c1 + mref_c2 + mref_c3

        return {
            "scope_id": scope_id,
            "total_calls": total_calls,
            "calls_per_candidate": calls_per_candidate,
            "EXPECTED_OR_EMPIRICAL_PLANNING_ESTIMATE": {
                "category": "EXPECTED_OR_EMPIRICAL_PLANNING_ESTIMATE",
                "is_hard_maximum": False,
                "by_candidate_usd": {
                    "C1": _fmt_usd(emp_c1),
                    "C2": _fmt_usd(emp_c2),
                    "C3": _fmt_usd(emp_c3),
                },
                "total_usd": _fmt_usd(emp_tot),
            },
            "CONSERVATIVE_PLANNING_ENVELOPE": {
                "category": "CONSERVATIVE_PLANNING_ENVELOPE",
                "is_hard_maximum": False,
                "by_candidate_usd": {
                    "C1": _fmt_usd(cons_c1),
                    "C2": _fmt_usd(cons_c2),
                    "C3": _fmt_usd(cons_c3),
                },
                "total_usd": _fmt_usd(cons_tot),
            },
            "CONFIGURED_MAX_OUTPUT_16384_REFERENCE": {
                "category": "CONFIGURED_MAX_OUTPUT_16384_REFERENCE_NOT_HARD_MAXIMUM",
                "is_hard_maximum": False,
                "configured_max_output_tokens": 16384,
                "by_candidate_usd": {
                    "C1": _fmt_usd(mref_c1),
                    "C2": _fmt_usd(mref_c2),
                    "C3": _fmt_usd(mref_c3),
                },
                "total_usd": _fmt_usd(mref_tot),
            },
            "HARD_MAXIMUM": {
                "category": "HARD_MAXIMUM",
                "hard_maximum_status": HARD_MAXIMUM_STATUS,
                "hard_maximum_usd": None,
                "reason": (
                    "NOT_DEFENSIBLY_COMPUTABLE: (1) exact server-side input token counts are not available for all 189 cells "
                    "(only 2/9 canary cells and 9/180 primary comparative cells returned usage metadata, and C1 has 0 observed completions on ha-long); "
                    "(2) for C1 (gemini-3.8-flash), thought_tokens are billed as output tokens alongside output_tokens under thinking_level='medium', "
                    "and provider-internal thinking token allocation vs max_output_tokens=16384 is server-controlled; "
                    "(3) timed-out or aborted calls can incur partial server-side token charges without returning usage receipts."
                ),
            },
        }

    return {
        "openai_long_context_check": openai_long_context_check,
        "cost_analysis": {
            "cost_categories_distinguished": [
                "PUBLIC_UNIT_PRICING",
                "HISTORICAL_OBSERVED_COST_REFERENCE",
                "EXPECTED_OR_EMPIRICAL_PLANNING_ESTIMATE",
                "CONSERVATIVE_PLANNING_ENVELOPE",
                "HARD_MAXIMUM",
            ],
            "planning_envelope_is_hard_maximum": False,
            "hard_maximum_status": HARD_MAXIMUM_STATUS,
            "PUBLIC_UNIT_PRICING": {
                "C1": {
                    "model": "gemini-3.8-flash",
                    "billing_surface": "GEMINI_DEVELOPER_API_GOOGLE_AI_STUDIO_STANDARD_PAID_TIER",
                    "input_usd_per_1m_tokens": "0.75",
                    "output_including_thinking_usd_per_1m_tokens": "3.75",
                    "promotional_through": "2026-12-31",
                },
                "C2": {
                    "model": "gpt-6.1-sol",
                    "billing_surface": "OPENAI_STANDARD_API_CHAT_COMPLETIONS_DEFAULT_SERVICE_TIER",
                    "input_usd_per_1m_tokens": "2.00",
                    "output_including_reasoning_usd_per_1m_tokens": "10.00",
                    "cached_input_usd_per_1m_tokens": "0.10",
                },
                "C3": {
                    "model": "claude-sonnet-5-5",
                    "billing_surface": "ANTHROPIC_CLAUDE_API_FIRST_PARTY_DIRECT_MESSAGES_STANDARD_GLOBAL",
                    "input_usd_per_1m_tokens": "2.00",
                    "output_including_thinking_usd_per_1m_tokens": "10.00",
                },
            },
            "HISTORICAL_OBSERVED_COST_REFERENCE": {
                "source_artifact": PRIMARY_RESULTS_MANIFEST_REL_PATH,
                "authoritative_cost_cells": 9,
                "total_canonical_receipt_cost_usd": "0.6468966",
                "by_candidate_usd": {
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
                },
                "usage_restriction": (
                    "Descriptive historical evidence from the 9 completed primary DEV-SELECT cells only (computed under "
                    "frozen 2026-10-16 runner rate constants). Must NOT be scaled blindly to 189 calls because the 9 completed "
                    "cells exclude all C3 calls (0/60) and exclude all 3-day and 5-day C2 calls (0/40)."
                ),
                "blind_scaling_to_189_calls_performed": False,
            },
            "documented_derivation_and_assumptions": {
                "silent_imputation_performed": False,
                "observed_p1_usage_cell_counts": {
                    "C1": 4,
                    "C2": 12,
                    "C3": 16,
                    "total_observed_p1_cells_in_repo": 32,
                },
                "canary_cells_with_historical_p1_usage": {
                    "W06-DEV-TUNE-P1-C3-W06-DEV-TUNE-011": {
                        "input_tokens": 41165,
                        "output_tokens": 6162,
                    },
                    "W06-DEV-TUNE-P1-C3-W06-DEV-TUNE-015": {
                        "input_tokens": 28412,
                        "output_tokens": 5691,
                    },
                    "remaining_7_of_9_canary_cells": "Failed in primary DEV-TUNE (C1: 2 HTTP_429 + 1 TIMEOUT; C2: 3 TIMEOUT at 55s; C3-007: 1 TIMEOUT at 55s) without returning provider token usage metadata.",
                },
                "candidate_derivation_notes": {
                    "C1": (
                        f"4 completed P1 cells exist in repository (2 ha-noi: mean input 20,106.0 tokens; 2 da-nang: mean input 38,255.0 tokens; "
                        f"0 ha-long completions because Free-Tier 20-RPD quota was exhausted before ha-long fixtures). "
                        f"Unimputed 4-cell observed mean is 29,180.5 input tokens and 5,718.25 billable output tokens "
                        f"(3,246.0 output_tokens + 2,472.25 thought_tokens), yielding ${_fmt_usd(c1_emp_cost_per_call)}/call under current $0.75/$3.75 pricing. "
                        f"Conservative planning envelope bounds every C1 call at 40,000 input tokens (above max observed da-nang 38,272) "
                        f"and 10,000 billable output tokens (above max observed 6,183), yielding ${_fmt_usd(c1_cons_per_call)}/call."
                    ),
                    "C2": (
                        f"12 completed P1 cells exist across all 3 destinations (5 ha-noi: mean input 16,098.0; 5 ha-long: mean input 19,803.6; "
                        f"2 da-nang: mean input 29,632.0). Because both the 3-fixture canary and 60-fixture comparative set are balanced 1:1:1 "
                        f"across destinations, the destination-balanced empirical mean input is 21,844.53 tokens/call and mean output "
                        f"(including reasoning_tokens) is 2,742.0 tokens/call, yielding ${_fmt_usd(c2_emp_cost_per_call)}/call under current $2.00/$10.00 pricing. "
                        f"Conservative planning envelope bounds every C2 call at 32,000 input tokens and 8,000 output tokens (more than 2x max observed 3,822 "
                        f"to account for 3-day and 5-day itineraries that timed out at 55s), yielding ${_fmt_usd(c2_cons_per_call)}/call."
                    ),
                    "C3": (
                        f"16 completed P1 cells exist across all 3 destinations (5 ha-noi: mean input 23,642.8; 6 ha-long: mean input 28,440.83; "
                        f"5 da-nang: mean input 41,151.6), including 2 of the 3 exact canary fixtures (011 and 015). Destination-balanced empirical "
                        f"mean input is 31,078.39 tokens/call and mean output (including adaptive thinking) is 6,143.06 tokens/call, yielding "
                        f"${_fmt_usd(c3_emp_cost_per_call)}/call under current $2.00/$10.00 pricing. Conservative planning envelope bounds every C3 call at 42,000 input tokens "
                        f"and 10,000 output tokens (above max observed 8,060), yielding ${_fmt_usd(c3_cons_per_call)}/call."
                    ),
                },
            },
            "A_readiness_canary_9_calls": _build_scope_cost_block(
                "A_READINESS_CANARY_9_CALLS",
                total_calls=CANARY_CALL_COUNT,
                calls_per_candidate=3,
            ),
            "B_amended_comparative_180_calls": _build_scope_cost_block(
                "B_AMENDED_COMPARATIVE_180_CALLS",
                total_calls=COMPARATIVE_CALL_COUNT,
                calls_per_candidate=60,
            ),
            "C_total_amendment_track_189_calls": _build_scope_cost_block(
                "C_TOTAL_AMENDMENT_TRACK_189_CALLS",
                total_calls=MAX_GENERATION_CALL_COUNT,
                calls_per_candidate=MAX_CALLS_PER_CANDIDATE,
            ),
        },
    }


# ==============================================================================
# 6. PROVIDER READINESS MATRIX, OWNER ATTESTATION & RATE-LIMIT ANALYSIS (SECTIONS 11-14)
# ==============================================================================


def build_provider_readiness_and_attestation_package(
    cost_analysis: dict[str, Any],
) -> dict[str, Any]:
    """Construct Sections 11, 12, 13, and 14 structures consuming canonical cost_analysis."""
    can_cons = cost_analysis["A_readiness_canary_9_calls"][
        "CONSERVATIVE_PLANNING_ENVELOPE"
    ]["by_candidate_usd"]
    cmp_cons = cost_analysis["B_amended_comparative_180_calls"][
        "CONSERVATIVE_PLANNING_ENVELOPE"
    ]["by_candidate_usd"]
    tot_cons = cost_analysis["C_total_amendment_track_189_calls"][
        "CONSERVATIVE_PLANNING_ENVELOPE"
    ]["by_candidate_usd"]
    tot_mref = cost_analysis["C_total_amendment_track_189_calls"][
        "CONFIGURED_MAX_OUTPUT_16384_REFERENCE"
    ]["by_candidate_usd"]

    provider_readiness_matrix = {
        "C1_PROVIDER_READINESS": PROVIDER_READINESS_NOT_YET_ATTESTED,
        "C2_PROVIDER_READINESS": PROVIDER_READINESS_NOT_YET_ATTESTED,
        "C3_PROVIDER_READINESS": PROVIDER_READINESS_NOT_YET_ATTESTED,
        "owner_action_occurred": False,
        "candidates": {
            "C1": {
                "candidate_id": "C1",
                "provider": "GOOGLE",
                "exact_model_id": "gemini-3.8-flash",
                "current_readiness_status": PROVIDER_READINESS_NOT_YET_ATTESTED,
                "A_billing_readiness": "Paid / billing-enabled tier active on the Google AI Studio / Gemini Developer API project bound to GEMINI_API_KEY (explicitly upgraded out of the Free Tier that caused 35 HTTP_429 GenerateRequestsPerDayPerProjectPerModel-FreeTier failures).",
                "B_exact_model_access": "Confirmed access to exact model ID 'gemini-3.8-flash' on Gemini Developer API (generativelanguage.googleapis.com).",
                "C_quota_request_volume_readiness": "Remaining daily/request quota (RPD) not constrained by the prior Free Tier 20-RPD ceiling and sufficient for the exact authorized S2 volume (up to 63 C1 generation calls: 3 canary + 60 comparative).",
                "D_rpm_readiness": "Project RPM limit for gemini-3.8-flash sufficient for the frozen deterministic schedule (client issues at most 1 request per >=2,000ms inter-call delay plus model execution time; sequential C1-only upper bound <= 30 RPM, interleaved 3-candidate cadence <= 10 RPM per provider).",
                "E_tpm_readiness": "Project TPM limit for gemini-3.8-flash sufficient for ~20K-40K input tokens + up to 16,384 output/thought tokens per call under the frozen schedule.",
                "F_credit_spend_readiness": (
                    f"Active Cloud Billing linkage / spend cap sufficient to cover the C1 conservative planning envelope "
                    f"(${can_cons['C1']} canary / ${cmp_cons['C1']} comparative / ${tot_cons['C1']} total 63 calls; "
                    f"${tot_mref['C1']} max-output-16384 reference)."
                ),
                "G_selected_billing_surface": "GEMINI_DEVELOPER_API_GOOGLE_AI_STUDIO_STANDARD_PAID_TIER",
                "H_evidence_required_from_project_owner": "Sanitized Project Owner attestation confirming Paid Tier active, exact gemini-3.8-flash access, Free-Tier 20-RPD ceiling no longer active, and RPD/RPM/TPM + spend cap sufficient for 63 C1 calls.",
                "I_sanitization_requirements": "Must NOT include GEMINI_API_KEY, key prefix, Google Cloud billing account ID, project number/ID, organization ID, payment instrument details, or personal email/account identifiers.",
            },
            "C2": {
                "candidate_id": "C2",
                "provider": "OPENAI",
                "exact_model_id": "gpt-6.1-sol",
                "current_readiness_status": PROVIDER_READINESS_NOT_YET_ATTESTED,
                "A_billing_readiness": "Active OpenAI API billing state with positive credit balance or active auto-recharge.",
                "B_exact_model_access": "Confirmed access to exact model ID 'gpt-6.1-sol' on /v1/chat/completions with service_tier='default'.",
                "C_quota_request_volume_readiness": "Usage tier and monthly spend/quota limits sufficient for the exact authorized S2 volume (up to 63 C2 generation calls: 3 canary + 60 comparative).",
                "D_rpm_readiness": "Account RPM limit for gpt-6.1-sol sufficient for the frozen 2,000ms deterministic pacing schedule.",
                "E_tpm_readiness": "Account TPM limit for gpt-6.1-sol sufficient for ~16K-30K input tokens + up to 16,384 completion tokens per call under the frozen schedule.",
                "F_credit_spend_readiness": (
                    f"Available API credits / remaining monthly budget sufficient to cover the C2 conservative planning envelope "
                    f"(${can_cons['C2']} canary / ${cmp_cons['C2']} comparative / ${tot_cons['C2']} total 63 calls; "
                    f"${tot_mref['C2']} max-output-16384 reference)."
                ),
                "G_selected_billing_surface": "OPENAI_STANDARD_API_CHAT_COMPLETIONS_DEFAULT_SERVICE_TIER",
                "H_evidence_required_from_project_owner": "Sanitized Project Owner attestation confirming active OpenAI API billing, gpt-6.1-sol access, and credit/spend + RPM/TPM/RPD limits sufficient for 63 C2 calls.",
                "I_sanitization_requirements": "Must NOT include OPENAI_API_KEY, key prefix, OpenAI organization ID, project ID, billing account ID, credit-card details, or personal account identifiers.",
            },
            "C3": {
                "candidate_id": "C3",
                "provider": "ANTHROPIC",
                "exact_model_id": "claude-sonnet-5-5",
                "current_readiness_status": PROVIDER_READINESS_NOT_YET_ATTESTED,
                "A_billing_readiness": "Active Anthropic Claude API billing state (remediating the primary DEV-SELECT 60/60 HTTP 400 'Your credit balance is too low to access the Anthropic API' failure mode).",
                "B_exact_model_access": "Confirmed access to exact model ID 'claude-sonnet-5-5' on /v1/messages.",
                "C_quota_request_volume_readiness": "Account usage tier and monthly spend limits sufficient for the exact authorized S2 volume (up to 63 C3 generation calls: 3 canary + 60 comparative).",
                "D_rpm_readiness": "Account RPM limit for claude-sonnet-5-5 sufficient for the frozen 2,000ms deterministic pacing schedule.",
                "E_tpm_readiness": "Account ITPM/OTPM limits for claude-sonnet-5-5 sufficient for ~23.6K-41.2K input tokens and ~4.5K-8.1K (up to 16,384 max_tokens) output tokens per call under the frozen schedule.",
                "F_credit_spend_readiness": (
                    f"Positive, sufficient API credit balance or approved billing state covering the C3 conservative planning envelope "
                    f"(${can_cons['C3']} canary / ${cmp_cons['C3']} comparative / ${tot_cons['C3']} total 63 calls; "
                    f"${tot_mref['C3']} max-output-16384 reference)."
                ),
                "G_selected_billing_surface": "ANTHROPIC_CLAUDE_API_FIRST_PARTY_DIRECT_MESSAGES_STANDARD_GLOBAL",
                "H_evidence_required_from_project_owner": "Sanitized Project Owner attestation confirming active Anthropic API billing, positive credit balance sufficient for the planning budget, claude-sonnet-5-5 access, and RPM/ITPM/OTPM limits sufficient for 63 C3 calls.",
                "I_sanitization_requirements": "Must NOT include ANTHROPIC_API_KEY, key prefix, Anthropic organization/workspace ID, billing account ID, credit-card details, or personal account identifiers.",
            },
        },
    }

    owner_attestation_template = {
        "template_id": "W06-DEV-SELECT-AMENDMENT-01-SANITIZED-OWNER-ATTESTATION-TEMPLATE-V1",
        "template_status": "DESIGNED_FOR_FUTURE_GATE_NOT_YET_EXECUTED",
        "owner_action_requested_in_this_prep_task": False,
        "owner_attestation_executed": False,
        "separate_authority_rule": (
            "Project Owner attestation and 9-call engineering readiness canary evidence remain separate authorities. "
            "Three canary calls per provider (9 total) verify live transport/authentication/model wiring on 3 DEV-TUNE fixtures, "
            "but CANNOT by themselves prove that the account has sufficient remaining quota or credit balance for all 63 calls per candidate."
        ),
        "forbidden_fields_never_recorded": [
            "api_key",
            "api_key_prefix",
            "secret",
            "organization_id",
            "project_id_or_number",
            "billing_account_id",
            "credit_card_information",
            "personal_account_identifier_or_email",
        ],
        "per_candidate_attestation_fields_schema": {
            "billing_active": "YES | NO",
            "model_access_confirmed": "YES | NO",
            "quota_sufficient_for_authorized_volume": "YES | NO",
            "credit_sufficient_for_authorized_planning_budget": "YES | NO",
            "prior_blocking_condition_remediated": "YES | NO",
            "optional_sanitized_numeric_limits": {
                "rpm_limit_sanitized": "integer_or_null (no account IDs/secrets)",
                "tpm_limit_sanitized": "integer_or_null (no account IDs/secrets)",
                "rpd_limit_sanitized": "integer_or_null (no account IDs/secrets)",
            },
        },
    }

    rate_limit_analysis = {
        "pacing_policy": SELECTED_PACING_POLICY,
        "inter_call_delay_ms": SELECTED_INTER_CALL_DELAY_MS,
        "deterministic": True,
        "fixed": True,
        "adaptive": False,
        "response_dependent": False,
        "counterfactual_firewall": (
            "A fixed 2,000ms inter-call delay bounds client-issued request cadence only; it does NOT guarantee "
            "that provider-side HTTP 429 (rate-limit/quota) or HTTP 503/5xx (overload) errors will not occur."
        ),
        "defensible_client_cadence_bounds": {
            "minimum_inter_call_gap_seconds": 2.0,
            "theoretical_zero_latency_upper_bound_calls_per_minute_total": 30.0,
            "theoretical_zero_latency_upper_bound_calls_per_minute_per_provider_if_interleaved": 10.0,
            "empirical_latency_inclusive_cadence_note": (
                "Because the runner executes calls strictly sequentially (concurrency = 1) and waits 2,000ms between "
                "completion of call N and dispatch of call N+1, a typical completed generation taking ~20s-60s results in "
                "~1 to 2.7 requests/minute total across the harness (and <1.5 RPM per provider)."
            ),
        },
        "provider_limit_dimensions": {
            "GOOGLE": {
                "official_rate_limits_url": "https://ai.google.dev/gemini-api/docs/rate-limits",
                "retrieval_timestamp_utc": "2026-10-25T03:05:08Z",
                "documented_dimensions": ["RPM", "TPM", "RPD", "project_usage_tier"],
                "authority_note": (
                    "Official Google Gemini API documentation states that rate limits are applied per project across "
                    "RPM, TPM (input), and RPD, vary by model and project usage tier (Free, Tier 1, Tier 2, Tier 3), "
                    "and active limits for a specific project must be checked in Google AI Studio. Generic public table examples "
                    "must not be substituted for actual project limits."
                ),
            },
            "OPENAI": {
                "official_rate_limits_url": "https://developers.openai.com/api/docs/guides/rate-limits",
                "retrieval_timestamp_utc": "2026-10-25T03:05:50Z",
                "documented_dimensions": ["RPM", "RPD", "TPM", "TPD", "usage_tier_1_to_5"],
                "authority_note": (
                    "Official OpenAI documentation defines rate limits across RPM, RPD, TPM, and TPD by organization/project "
                    "usage tier (Tier 1 through Tier 5) and monthly spend limit. Actual account limits remain Project Owner evidence."
                ),
            },
            "ANTHROPIC": {
                "official_rate_limits_url": "https://docs.anthropic.com/en/api/rate-limits",
                "retrieval_timestamp_utc": "2026-10-25T03:05:54Z",
                "documented_dimensions": ["RPM", "ITPM", "OTPM", "usage_tier_1_to_4", "monthly_spend_limit"],
                "authority_note": (
                    "Official Anthropic Claude API documentation defines rate limits across RPM, ITPM (input tokens/min), "
                    "and OTPM (output tokens/min) across Tiers 1-4 plus monthly spend limits. Actual account limits and credit "
                    "balance remain Project Owner evidence."
                ),
            },
        },
    }

    frozen_canary_summary = {
        "canary_manifest_relative_path": CANARY_MANIFEST_REL_PATH,
        "canary_manifest_file_sha256": EXPECTED_CANARY_MANIFEST_FILE_SHA256,
        "canary_manifest_internal_sha256": EXPECTED_CANARY_MANIFEST_INTERNAL_SHA256,
        "fixture_ids": list(CANARY_FIXTURE_IDS),
        "candidate_ids": list(ORDERED_CANDIDATE_IDS),
        "total_canary_cells": CANARY_CALL_COUNT,
        "calls_per_candidate": 3,
        "selection_weight": 0,
        "operational_gate_required_pass_count": "9/9",
        "canary_executed_in_this_task": False,
        "live_provider_calls_new": 0,
    }

    return {
        "provider_readiness_matrix": provider_readiness_matrix,
        "owner_attestation_template": owner_attestation_template,
        "rate_limit_analysis": rate_limit_analysis,
        "frozen_canary_summary": frozen_canary_summary,
    }


# ==============================================================================
# 7. MAIN PREP ARTIFACT & MARKDOWN BUILDERS (SINGLE COST CALCULATION AUTHORITY)
# ==============================================================================


def build_provider_readiness_pricing_prep_payload(
    pricing_snapshot: dict[str, Any],
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Build the complete `w06_dev_select_amendment_01_provider_readiness_pricing_prep_v1.json` payload."""
    primary_authority = read_and_crosscheck_primary_metric_authority(repo_root)
    billing_surfaces = inspect_billing_surfaces_from_repo(repo_root)
    cost_and_long_context = analyze_requests_and_costs(repo_root)
    readiness_pkg = build_provider_readiness_and_attestation_package(
        cost_and_long_context["cost_analysis"]
    )

    pricing_snapshot_raw = canonical_json_bytes(pricing_snapshot)
    pricing_snapshot_file_sha256 = sha256_bytes(pricing_snapshot_raw)
    pricing_snapshot_internal_sha256 = str(
        pricing_snapshot["public_pricing_snapshot_sha256"]
    )

    payload: dict[str, Any] = {
        "artifact_id": PROVIDER_READINESS_PRICING_PREP_ARTIFACT_ID,
        "task_id": TASK_ID,
        "corrective_task_id": CORRECTIVE_TASK_ID,
        "authoritative_base_develop_sha": AUTHORITATIVE_BASE_DEVELOP_SHA,
        "approval_receipt_merge_governance": {
            "pr_number": APPROVAL_RECEIPT_PR_NUMBER,
            "pr_state": APPROVAL_RECEIPT_PR_STATE,
            "merge_commit_sha": APPROVAL_RECEIPT_MERGE_COMMIT_SHA,
            "merge_parent_1": APPROVAL_RECEIPT_MERGE_PARENT_1,
            "merge_parent_2": APPROVAL_RECEIPT_MERGE_PARENT_2,
            "post_merge_ci_run_id": APPROVAL_RECEIPT_POST_MERGE_CI_RUN_ID,
        },
        "bound_authorities": {
            "approval_receipt_relative_path": APPROVAL_RECEIPT_REL_PATH,
            "approval_receipt_file_sha256": EXPECTED_APPROVAL_RECEIPT_FILE_SHA256,
            "approval_receipt_internal_sha256": EXPECTED_APPROVAL_RECEIPT_INTERNAL_SHA256,
            "decision_artifact_relative_path": DECISION_ARTIFACT_REL_PATH,
            "decision_artifact_file_sha256": EXPECTED_DECISION_ARTIFACT_FILE_SHA256,
            "decision_artifact_internal_sha256": EXPECTED_DECISION_ARTIFACT_INTERNAL_SHA256,
            "canary_manifest_relative_path": CANARY_MANIFEST_REL_PATH,
            "canary_manifest_file_sha256": EXPECTED_CANARY_MANIFEST_FILE_SHA256,
            "canary_manifest_internal_sha256": EXPECTED_CANARY_MANIFEST_INTERNAL_SHA256,
            "prep_artifact_relative_path": PREP_ARTIFACT_REL_PATH,
            "prep_artifact_file_sha256": EXPECTED_PREP_ARTIFACT_FILE_SHA256,
            "prep_artifact_internal_sha256": EXPECTED_PREP_ARTIFACT_INTERNAL_SHA256,
            "primary_results_freeze_receipt_relative_path": PRIMARY_RESULTS_FREEZE_RECEIPT_REL_PATH,
            "primary_results_freeze_receipt_file_sha256": EXPECTED_PRIMARY_RESULTS_FREEZE_RECEIPT_FILE_SHA256,
            "primary_results_freeze_receipt_internal_sha256": EXPECTED_PRIMARY_RESULTS_FREEZE_RECEIPT_INTERNAL_SHA256,
            "primary_results_manifest_relative_path": PRIMARY_RESULTS_MANIFEST_REL_PATH,
            "primary_results_manifest_file_sha256": EXPECTED_PRIMARY_RESULTS_MANIFEST_FILE_SHA256,
            "primary_results_manifest_internal_sha256": EXPECTED_PRIMARY_RESULTS_MANIFEST_INTERNAL_SHA256,
            "failure_diagnostic_relative_path": FAILURE_DIAGNOSTIC_REL_PATH,
            "failure_diagnostic_file_sha256": EXPECTED_FAILURE_DIAGNOSTIC_FILE_SHA256,
            "failure_diagnostic_internal_sha256": EXPECTED_FAILURE_DIAGNOSTIC_INTERNAL_SHA256,
            "scientific_code_bundle_sha256": EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256,
            "public_pricing_snapshot_relative_path": PUBLIC_PRICING_SNAPSHOT_REL_PATH,
            "public_pricing_snapshot_file_sha256": pricing_snapshot_file_sha256,
            "public_pricing_snapshot_internal_sha256": pricing_snapshot_internal_sha256,
        },
        "report_correction_firewall": primary_authority,
        "immutable_approved_amendment_policy": {
            "track_classification": TRACK_CLASSIFICATION,
            "fairness_policy": SELECTED_FAIRNESS_POLICY,
            "timeout_policy": SELECTED_TIMEOUT_POLICY,
            "timeout_ms": SELECTED_TIMEOUT_MS,
            "pacing_policy": SELECTED_PACING_POLICY,
            "inter_call_delay_ms": SELECTED_INTER_CALL_DELAY_MS,
            "pacing_fixed": True,
            "pacing_deterministic": True,
            "pacing_adaptive": False,
            "pacing_response_dependent": False,
            "retry_policy": SELECTED_RETRY_POLICY,
            "automatic_retry": 0,
            "sdk_retry": 0,
            "transport_retry": 0,
            "manual_retry": 0,
            "repair": 0,
            "fallback": False,
            "fixture_policy": SELECTED_FIXTURE_POLICY,
            "call_budget_policy": SELECTED_CALL_BUDGET_POLICY,
            "canary_calls": CANARY_CALL_COUNT,
            "comparative_calls": COMPARATIVE_CALL_COUNT,
            "maximum_generation_calls": MAX_GENERATION_CALL_COUNT,
            "maximum_calls_per_candidate": MAX_CALLS_PER_CANDIDATE,
        },
        "exact_frozen_candidates": FROZEN_CANDIDATES,
        "billing_surface_determination": billing_surfaces,
        "openai_long_context_check": cost_and_long_context[
            "openai_long_context_check"
        ],
        "cost_analysis": cost_and_long_context["cost_analysis"],
        "provider_readiness_matrix": readiness_pkg["provider_readiness_matrix"],
        "owner_attestation_template": readiness_pkg["owner_attestation_template"],
        "rate_limit_analysis": readiness_pkg["rate_limit_analysis"],
        "frozen_canary_summary": readiness_pkg["frozen_canary_summary"],
        "scientific_and_execution_firewall_flags": {
            "AMENDMENT_METHODOLOGY_SELECTED": True,
            "AMENDMENT_APPROVED": True,
            "effective_amendment_status": EFFECTIVE_AMENDMENT_STATUS,
            "AMENDED_CANARY_LIVE_AUTHORIZED": False,
            "AMENDED_COMPARATIVE_LIVE_AUTHORIZED": False,
            "AMENDED_LIVE_AUTHORIZED": False,
            "AMENDED_LIVE_EXECUTED": False,
            "CANARY_EXECUTED": False,
            "COMPARATIVE_EXECUTED": False,
            "LIVE_PROVIDER_CALLS_NEW": 0,
            "MODEL_WINNER_SELECTED": False,
            "SELECTED_MODEL_ID": None,
            "STOCHASTICITY_EXECUTION_STARTED": False,
            "FINAL100_USED": False,
            "FINAL100_STATUS": "NO-GO",
            "PRIMARY_EXPERIMENT_MUTATED": False,
            "PRIMARY_RESULTS_REPLACED": False,
            "PRIMARY_DENOMINATORS_CHANGED": False,
            "C1_PROVIDER_READINESS": PROVIDER_READINESS_NOT_YET_ATTESTED,
            "C2_PROVIDER_READINESS": PROVIDER_READINESS_NOT_YET_ATTESTED,
            "C3_PROVIDER_READINESS": PROVIDER_READINESS_NOT_YET_ATTESTED,
            "OWNER_ACTION_OCCURRED": False,
            "ENV_FILE_READ": False,
            "API_KEYS_INSPECTED": False,
        },
        "next_gate": NEXT_GATE_ID,
    }
    payload["provider_readiness_pricing_prep_sha256"] = sha256_bytes(
        canonical_json_bytes(payload)
    )
    return payload


COST_TABLE_SCOPE_SPECS: tuple[tuple[str, str], ...] = (
    ("A_readiness_canary_9_calls", "**A. Readiness Canary**"),
    ("B_amended_comparative_180_calls", "**B. Amended Comparative**"),
    ("C_total_amendment_track_189_calls", "**C. Total Amendment Track**"),
)

COST_TABLE_CATEGORY_SPECS: tuple[tuple[str, str], ...] = (
    (
        "EXPECTED_OR_EMPIRICAL_PLANNING_ESTIMATE",
        "`EXPECTED_OR_EMPIRICAL_PLANNING_ESTIMATE`",
    ),
    (
        "CONSERVATIVE_PLANNING_ENVELOPE",
        "`CONSERVATIVE_PLANNING_ENVELOPE`",
    ),
    (
        "CONFIGURED_MAX_OUTPUT_16384_REFERENCE",
        "`CONFIGURED_MAX_OUTPUT_16384_REFERENCE` (not hard max)",
    ),
)


def build_markdown_report(
    pricing_snapshot: dict[str, Any],
    prep_payload: dict[str, Any],
) -> str:
    """Render human-readable markdown documentation directly from canonical JSON structures.

    ZERO duplicate hard-coded cost literals: every cost cell is rendered from
    `prep_payload["cost_analysis"]` and `pricing_snapshot["candidates"]`.
    """
    snap_file_sha = sha256_bytes(canonical_json_bytes(pricing_snapshot))
    snap_int_sha = pricing_snapshot["public_pricing_snapshot_sha256"]
    prep_file_sha = sha256_bytes(canonical_json_bytes(prep_payload))
    prep_int_sha = prep_payload["provider_readiness_pricing_prep_sha256"]

    cost_analysis = prep_payload["cost_analysis"]
    hist_ref = cost_analysis["HISTORICAL_OBSERVED_COST_REFERENCE"]
    hist_by_cand = hist_ref["by_candidate_usd"]

    cands_snap = pricing_snapshot["candidates"]
    c1_unit = cands_snap["C1"]["selected_unit_pricing_usd_per_1m_tokens"]
    c2_unit = cands_snap["C2"]["selected_unit_pricing_usd_per_1m_tokens"]
    c3_unit = cands_snap["C3"]["selected_unit_pricing_usd_per_1m_tokens"]

    cost_rows: list[str] = []
    for scope_key, scope_label in COST_TABLE_SCOPE_SPECS:
        scope_block = cost_analysis[scope_key]
        calls_str = f"`{scope_block['total_calls']}` (`{scope_block['calls_per_candidate']}`/cand)"
        for cat_key, cat_label in COST_TABLE_CATEGORY_SPECS:
            cat_block = scope_block[cat_key]
            by_cand = cat_block["by_candidate_usd"]
            tot_val = cat_block["total_usd"]
            cost_rows.append(
                f"| {scope_label} | {calls_str} | {cat_label} | "
                f"`${by_cand['C1']}` | `${by_cand['C2']}` | `${by_cand['C3']}` | **`${tot_val}`** |"
            )

    lines = [
        "# W06 DEV-SELECT Amendment 01 — Provider Readiness & Current Pricing PREP",
        "",
        "## 1. Governance & Scope Boundary",
        "",
        f"- **Task ID:** `{TASK_ID}`",
        f"- **Corrective Task ID:** `{CORRECTIVE_TASK_ID}`",
        f"- **Authoritative Base:** `develop@{AUTHORITATIVE_BASE_DEVELOP_SHA}` (PR #{APPROVAL_RECEIPT_PR_NUMBER} merged, post-merge CI run `{APPROVAL_RECEIPT_POST_MERGE_CI_RUN_ID}` green)",
        f"- **Public Pricing Snapshot Artifact:** `{PUBLIC_PRICING_SNAPSHOT_REL_PATH}`",
        f"  - `file_sha256`: `{snap_file_sha}`",
        f"  - `internal_sha256`: `{snap_int_sha}`",
        f"- **Provider Readiness & Pricing PREP Artifact:** `{PROVIDER_READINESS_PRICING_PREP_REL_PATH}`",
        f"  - `file_sha256`: `{prep_file_sha}`",
        f"  - `internal_sha256`: `{prep_int_sha}`",
        f"- **Effective Amendment Status:** `{EFFECTIVE_AMENDMENT_STATUS}`",
        f"- **Next Gate:** `{NEXT_GATE_ID}`",
        "",
        "**Strict Execution & Privacy Firewalls:**",
        "- `LIVE_PROVIDER_CALLS_NEW = 0` (`CANARY_EXECUTED = false`, `COMPARATIVE_EXECUTED = false`)",
        "- `AMENDED_CANARY_LIVE_AUTHORIZED = false`, `AMENDED_COMPARATIVE_LIVE_AUTHORIZED = false`, `AMENDED_LIVE_AUTHORIZED = false`, `AMENDED_LIVE_EXECUTED = false`",
        "- `C1_PROVIDER_READINESS = NOT_YET_ATTESTED`, `C2_PROVIDER_READINESS = NOT_YET_ATTESTED`, `C3_PROVIDER_READINESS = NOT_YET_ATTESTED`",
        "- `OWNER_ACTION_OCCURRED = false`, `ENV_FILE_READ = false`, `API_KEYS_INSPECTED = false`",
        "- `MODEL_WINNER_SELECTED = false`, `SELECTED_MODEL_ID = null`, `STOCHASTICITY_EXECUTION_STARTED = false`, `FINAL100_USED = false` (`NO-GO`)",
        "- `PRIMARY_EXPERIMENT_MUTATED = false`, `PRIMARY_RESULTS_REPLACED = false`, `PRIMARY_DENOMINATORS_CHANGED = false`",
        "",
        "## 2. Report Correction Firewall & Primary Metric Authority",
        "",
        f"Independently read from `{PRIMARY_RESULTS_MANIFEST_REL_PATH}` (`{EXPECTED_PRIMARY_RESULTS_MANIFEST_FILE_SHA256}`) and cross-checked against `{PRIMARY_RESULTS_FREEZE_RECEIPT_REL_PATH}` (`{EXPECTED_PRIMARY_RESULTS_FREEZE_RECEIPT_FILE_SHA256}` / internal `{EXPECTED_PRIMARY_RESULTS_FREEZE_RECEIPT_INTERNAL_SHA256}`):",
        "",
        "| Metric | C1 (`gemini-3.8-flash`) | C2 (`gpt-6.1-sol`) | C3 (`claude-sonnet-5-5`) | Total |",
        "| --- | --- | --- | --- | --- |",
        "| `VALID_RUN_AND_SCHEMA` | `1/60` | `8/60` | `0/60` | `9/180` |",
        "| `EXACT_GROUNDING_PASS` | `1/60` | `8/60` | `0/60` | `9/180` |",
        "| `FINAL_CORE_PASS` | `1/60` | `8/60` | `0/60` | `9/180` |",
        "",
        "- **Rejected Erroneous Report Tuple:** `C1 = 0/60, C2 = 43/60, C3 = 0/60` is explicitly rejected by regression guard (`validate_primary_metric_tuple`) as non-authoritative.",
        "",
        "## 3. Exact Billing Surface & Official Public Pricing Summary",
        "",
        "| Candidate | Provider / Model | Determined Billing Surface | Input / 1M | Output / 1M | Official Source URL | Retrieved (UTC) |",
        "| --- | --- | --- | --- | --- | --- | --- |",
        (
            f"| `C1` | `GOOGLE` / `{cands_snap['C1']['exact_model_id']}` | Gemini Developer API (AI Studio / `generativelanguage.googleapis.com`) Standard Paid Tier (promotional through `{cands_snap['C1']['promotional_expiration_date']}`) | "
            f"`${c1_unit['input_usd_per_1m_tokens']}` | `${c1_unit['output_including_thinking_usd_per_1m_tokens']}` (incl. thinking) | `{cands_snap['C1']['official_source_url']}` (`{cands_snap['C1']['exact_model_official_source_url']}`) | `{cands_snap['C1']['retrieval_timestamp_utc']}` |"
        ),
        (
            f"| `C2` | `OPENAI` / `{cands_snap['C2']['exact_model_id']}` | OpenAI Standard API (`api.openai.com` `/v1/chat/completions`, `service_tier='default'`, `<=272K` input) | "
            f"`${c2_unit['input_usd_per_1m_tokens']}` (cached `${c2_unit['cached_input_usd_per_1m_tokens']}`, assumed `0%`) | `${c2_unit['output_including_reasoning_usd_per_1m_tokens']}` (incl. reasoning) | `{cands_snap['C2']['official_source_url']}` (`{cands_snap['C2']['exact_model_official_source_url']}`) | `{cands_snap['C2']['retrieval_timestamp_utc']}` |"
        ),
        (
            f"| `C3` | `ANTHROPIC` / `{cands_snap['C3']['exact_model_id']}` | Anthropic Claude API First-Party Direct (`api.anthropic.com` `/v1/messages`, `service_tier='standard'`, global, caching disabled) | "
            f"`${c3_unit['input_usd_per_1m_tokens']}` | `${c3_unit['output_including_thinking_usd_per_1m_tokens']}` (incl. thinking) | `{cands_snap['C3']['official_source_url']}` (`{cands_snap['C3']['exact_model_official_source_url']}`) | `{cands_snap['C3']['retrieval_timestamp_utc']}` |"
        ),
        "",
        "- **OpenAI Long-Context (`>272,000` input tokens) Surcharge Status:** `NOT_APPLICABLE_PROVEN` (maximum serialized UTF-8 wire payload across all 63 frozen C2 requests is `89,435` bytes on `W06-DEV-SELECT-032`, strictly `<90,000` tokens under any byte-level BPE tokenizer, and empirical `prompt_tokens` across all 12 completed P1 C2 cells is `16,086..29,633` tokens).",
        "",
        "## 4. Cost Analysis Across S2 Call Scopes",
        "",
        "| Scope | Calls | Category | C1 (`gemini-3.8-flash`) | C2 (`gpt-6.1-sol`) | C3 (`claude-sonnet-5-5`) | Total (USD) |",
        "| --- | --- | --- | --- | --- | --- | --- |",
        *cost_rows,
        "",
        (
            f"- **Historical Observed Primary Reference:** `{hist_ref['authoritative_cost_cells']}` authoritative cost cells = "
            f"`{hist_ref['total_canonical_receipt_cost_usd']} USD` (`C1 = {hist_by_cand['C1']['canonical_cost_usd_decimal']} USD`, "
            f"`C2 = {hist_by_cand['C2']['canonical_cost_usd_decimal']} USD`, `C3 = {hist_by_cand['C3']['canonical_cost_usd_decimal']} USD`). "
            "Not scaled blindly to 189 calls."
        ),
        f"- **Hard Maximum Status:** `{HARD_MAXIMUM_STATUS}` (`hard_maximum_usd = null`).",
        "",
    ]
    return "\n".join(lines)


def parse_markdown_cost_table_values(md_text: str) -> dict[tuple[str, str], dict[str, str]]:
    """Extract every displayed cost cell from Section 4 of the Markdown report for consistency verification."""
    scope_by_label = {label: key for key, label in COST_TABLE_SCOPE_SPECS}
    cat_by_label = {label: key for key, label in COST_TABLE_CATEGORY_SPECS}
    extracted: dict[tuple[str, str], dict[str, str]] = {}

    for raw_line in md_text.splitlines():
        line = raw_line.strip()
        if not line.startswith("| **"):
            continue
        parts = [p.strip() for p in line.strip("|").split("|")]
        if len(parts) != 7:
            raise PlanBeforeLiveProtocolError(
                f"Malformed cost table row in Markdown: {raw_line}"
            )
        scope_label, _calls_col, cat_label, c1_col, c2_col, c3_col, tot_col = parts
        if scope_label not in scope_by_label or cat_label not in cat_by_label:
            raise PlanBeforeLiveProtocolError(
                f"Unrecognized scope or category in Markdown cost table row: {raw_line}"
            )
        scope_key = scope_by_label[scope_label]
        cat_key = cat_by_label[cat_label]

        def _strip_currency(cell: str) -> str:
            cleaned = cell.replace("*", "").replace("`", "").strip()
            if not cleaned.startswith("$"):
                raise PlanBeforeLiveProtocolError(
                    f"Expected $-prefixed currency cell in Markdown, got: {cell}"
                )
            return cleaned[1:]

        extracted[(scope_key, cat_key)] = {
            "C1": _strip_currency(c1_col),
            "C2": _strip_currency(c2_col),
            "C3": _strip_currency(c3_col),
            "total_usd": _strip_currency(tot_col),
        }

    return extracted


def verify_markdown_cost_consistency(
    cost_analysis: dict[str, Any],
    md_text: str,
) -> None:
    """Verify every numeric cost cell in the Markdown table equals the canonical JSON cost_analysis."""
    extracted = parse_markdown_cost_table_values(md_text)
    expected_keys: set[tuple[str, str]] = set()
    for scope_key, _ in COST_TABLE_SCOPE_SPECS:
        for cat_key, _ in COST_TABLE_CATEGORY_SPECS:
            expected_keys.add((scope_key, cat_key))
            if (scope_key, cat_key) not in extracted:
                raise PlanBeforeLiveProtocolError(
                    f"Missing Markdown cost table row for ({scope_key}, {cat_key})"
                )
            row = extracted[(scope_key, cat_key)]
            cat_block = cost_analysis[scope_key][cat_key]
            expected_row = {
                "C1": str(cat_block["by_candidate_usd"]["C1"]),
                "C2": str(cat_block["by_candidate_usd"]["C2"]),
                "C3": str(cat_block["by_candidate_usd"]["C3"]),
                "total_usd": str(cat_block["total_usd"]),
            }
            if row != expected_row:
                raise PlanBeforeLiveProtocolError(
                    f"Markdown vs JSON cost drift for ({scope_key}, {cat_key}): "
                    f"markdown={row} != json={expected_row}"
                )
    if set(extracted.keys()) != expected_keys:
        raise PlanBeforeLiveProtocolError(
            f"Unexpected rows in Markdown cost table: {set(extracted.keys()) ^ expected_keys}"
        )


# ==============================================================================
# 8. STATELESS VERIFIER & CLI ENTRYPOINT
# ==============================================================================


def verify_provider_readiness_pricing_prep_artifacts(
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Statelessly verify the public pricing snapshot and provider readiness/pricing PREP artifacts."""
    with NetworkKillSwitchGuard():
        # Verify upstream approval receipt (which also verifies decision, canary, prep, primary results freeze, and diagnostic)
        _app_mod.verify_w06_execution_environment_amendment_approval_receipt(
            repo_root=repo_root
        )

        if (
            compute_scientific_code_bundle_sha256()
            != EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
        ):
            raise PlanBeforeLiveProtocolError(
                "Scientific code bundle SHA256 drifted!"
            )

        # Verify pricing snapshot on disk
        snap_path = repo_root / PUBLIC_PRICING_SNAPSHOT_REL_PATH
        if not snap_path.is_file():
            raise PlanBeforeLiveProtocolError(
                f"Missing public pricing snapshot: {PUBLIC_PRICING_SNAPSHOT_REL_PATH}"
            )
        snap_raw = normalize_lf_bytes(snap_path.read_bytes())
        snap_disk = json.loads(snap_raw.decode("utf-8"))
        assert_no_secrets_in_payload(
            snap_disk, context=PUBLIC_PRICING_SNAPSHOT_ARTIFACT_ID
        )

        expected_snap = build_public_pricing_snapshot_payload()
        expected_snap_raw = canonical_json_bytes(expected_snap)
        if snap_raw != expected_snap_raw:
            raise PlanBeforeLiveProtocolError(
                "Public pricing snapshot byte/hash tamper detected or out of sync with canonical builder."
            )

        # Verify PREP artifact on disk
        prep_path = repo_root / PROVIDER_READINESS_PRICING_PREP_REL_PATH
        if not prep_path.is_file():
            raise PlanBeforeLiveProtocolError(
                f"Missing provider readiness/pricing PREP artifact: {PROVIDER_READINESS_PRICING_PREP_REL_PATH}"
            )
        prep_raw = normalize_lf_bytes(prep_path.read_bytes())
        prep_disk = json.loads(prep_raw.decode("utf-8"))
        assert_no_secrets_in_payload(
            prep_disk, context=PROVIDER_READINESS_PRICING_PREP_ARTIFACT_ID
        )

        expected_prep = build_provider_readiness_pricing_prep_payload(
            expected_snap, repo_root=repo_root
        )
        expected_prep_raw = canonical_json_bytes(expected_prep)
        if prep_raw != expected_prep_raw:
            raise PlanBeforeLiveProtocolError(
                "Provider readiness/pricing PREP artifact byte/hash tamper detected or out of sync with canonical builder."
            )

        # Verify Markdown doc on disk and exact machine <-> human cost consistency
        doc_path = repo_root / PROVIDER_READINESS_PRICING_PREP_DOC_REL_PATH
        if not doc_path.is_file():
            raise PlanBeforeLiveProtocolError(
                f"Missing markdown report: {PROVIDER_READINESS_PRICING_PREP_DOC_REL_PATH}"
            )
        doc_raw = normalize_lf_bytes(doc_path.read_bytes())
        doc_text = doc_raw.decode("utf-8")
        assert_no_secrets_in_payload(
            doc_text,
            context=PROVIDER_READINESS_PRICING_PREP_DOC_REL_PATH,
        )
        expected_md_text = build_markdown_report(expected_snap, expected_prep)
        if doc_raw != normalize_lf_bytes(expected_md_text.encode("utf-8")):
            raise PlanBeforeLiveProtocolError(
                "Markdown report out of sync with canonical JSON authorities."
            )
        verify_markdown_cost_consistency(
            prep_disk["cost_analysis"], doc_text
        )

        return {
            "status": "PASS",
            "public_pricing_snapshot_file_sha256": sha256_bytes(snap_raw),
            "public_pricing_snapshot_internal_sha256": snap_disk[
                "public_pricing_snapshot_sha256"
            ],
            "prep_artifact_file_sha256": sha256_bytes(prep_raw),
            "prep_artifact_internal_sha256": prep_disk[
                "provider_readiness_pricing_prep_sha256"
            ],
        }


def write_provider_readiness_pricing_prep_artifacts(
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Generate and write all required artifacts under strict offline guard."""
    with NetworkKillSwitchGuard():
        snap_payload = build_public_pricing_snapshot_payload()
        snap_bytes = canonical_json_bytes(snap_payload)
        snap_path = repo_root / PUBLIC_PRICING_SNAPSHOT_REL_PATH
        snap_path.parent.mkdir(parents=True, exist_ok=True)
        snap_path.write_bytes(snap_bytes)

        prep_payload = build_provider_readiness_pricing_prep_payload(
            snap_payload, repo_root=repo_root
        )
        prep_bytes = canonical_json_bytes(prep_payload)
        prep_path = repo_root / PROVIDER_READINESS_PRICING_PREP_REL_PATH
        prep_path.parent.mkdir(parents=True, exist_ok=True)
        prep_path.write_bytes(prep_bytes)

        md_text = build_markdown_report(snap_payload, prep_payload)
        doc_path = repo_root / PROVIDER_READINESS_PRICING_PREP_DOC_REL_PATH
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        doc_path.write_bytes(normalize_lf_bytes(md_text.encode("utf-8")))

    return verify_provider_readiness_pricing_prep_artifacts(repo_root=repo_root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate or verify W06 Amendment 01 provider-readiness and current-pricing PREP artifacts."
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify existing artifacts on disk without writing.",
    )
    args = parser.parse_args(argv)

    if args.verify_only:
        res = verify_provider_readiness_pricing_prep_artifacts(REPO_ROOT)
    else:
        res = write_provider_readiness_pricing_prep_artifacts(REPO_ROOT)
    print(json.dumps(res, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
