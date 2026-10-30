#!/usr/bin/env python3
"""Strictly offline Owner Provider Readiness Attestation Receipt generator and verifier for W06 DEV-SELECT Amendment 01.

TASK: W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-OWNER-PROVIDER-READINESS-ATTESTATION-RECEIPT-PREP

PURPOSE:
Create and statelessly verify a sanitized, repository-auditable Owner Provider
Readiness Attestation Receipt (`W06-DEV-SELECT-AMENDMENT-01-OWNER-PROVIDER-READINESS-ATTESTATION-V1`)
for the approved W06 secondary post-hoc execution-environment stabilization track:
1. `data/evaluation/w06/w06_dev_select_amendment_01_owner_provider_readiness_attestation_v1.json`
2. `docs/research/w06_dev_select_amendment_01_owner_provider_readiness_attestation.md`

STRICT FIREWALLS:
- Records OWNER-OBSERVED PROVIDER READINESS ONLY (`OWNER_PROVIDER_READINESS_ATTESTED = true`,
  `C1/C2/C3_PROVIDER_READINESS = "READY_FOR_CANARY"`, `ALL_CANARY_PROVIDER_READINESS = "READY"`).
- Does NOT authorize or execute any live provider call (`AMENDED_CANARY_LIVE_AUTHORIZED = false`,
  `AMENDED_COMPARATIVE_LIVE_AUTHORIZED = false`, `AMENDED_LIVE_AUTHORIZED = false`,
  `AMENDED_LIVE_EXECUTED = false`, `CANARY_EXECUTED = false`, `COMPARATIVE_EXECUTED = false`,
  `LIVE_PROVIDER_CALLS_NEW = 0`).
- Does NOT read `.env`, API keys, or secrets (`ENV_FILE_READ = false`, `API_KEYS_INSPECTED = false`).
- Does NOT store screenshots, API keys, key prefixes/suffixes, payment card details, billing
  account IDs, project numeric IDs, organization IDs, email addresses, personal names,
  payment transaction IDs, or exact prepaid VND/USD account balances.
- Does NOT generalize C3 Evaluation Tier limits as readiness proof for the future 60-call
  comparative run (`CANARY_READINESS_ATTESTATION_ONLY`; comparative readiness must be
  rechecked before comparative authorization).
- Does NOT select a model (`MODEL_WINNER_SELECTED = false`, `SELECTED_MODEL_ID = null`).
- Does NOT touch Final100 (`FINAL100_USED = false`, `FINAL100_STATUS = "NO-GO"`).
- Does NOT mutate primary DEV-SELECT evidence (`PRIMARY_EXPERIMENT_MUTATED = false`,
  `C1 = 1/60`, `C2 = 8/60`, `C3 = 0/60`).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

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
    EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
    EXPECTED_SEMANTIC_SCHEMA_SHA256,
    FORBIDDEN_FINAL100_BUNDLE_SHA256,
    FORBIDDEN_P11_MANIFEST_SHA256,
    canonical_json_bytes,
    compute_provider_config_registry_sha256,
    compute_scientific_code_bundle_sha256,
    load_and_verify_candidate_registry,
    load_and_verify_frozen_dev_bundle,
    normalize_lf_bytes,
    sha256_bytes,
)
import diagnose_w06_dev_select_failures as _diag_mod  # noqa: E402
import freeze_w06_dev_select_execution_environment_amendment_01_approval_receipt as _app_mod  # noqa: E402
import freeze_w06_dev_select_execution_environment_amendment_01_decision as _dec_mod  # noqa: E402
import freeze_w06_dev_select_live_results as _freeze_mod  # noqa: E402
import prepare_w06_dev_select_amendment_01_provider_readiness_pricing as _prp_mod  # noqa: E402
import prepare_w06_dev_select_execution_environment_amendment_01 as _prep_mod  # noqa: E402
from prepare_w06_dev_select_execution_environment_amendment_01 import (  # noqa: E402
    NetworkKillSwitchGuard,
)


# ==============================================================================
# 1. FROZEN AUTHORITIES & CONSTANTS
# ==============================================================================

TASK_ID = (
    "W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-OWNER-PROVIDER-READINESS-ATTESTATION-RECEIPT-PREP"
)
OWNER_READINESS_ATTESTATION_ARTIFACT_ID = (
    "W06-DEV-SELECT-AMENDMENT-01-OWNER-PROVIDER-READINESS-ATTESTATION-V1"
)
OWNER_READINESS_ATTESTATION_REL_PATH = (
    "data/evaluation/w06/w06_dev_select_amendment_01_owner_provider_readiness_attestation_v1.json"
)
OWNER_READINESS_ATTESTATION_DOC_REL_PATH = (
    "docs/research/w06_dev_select_amendment_01_owner_provider_readiness_attestation.md"
)

AUTHORITATIVE_BASE_DEVELOP_SHA = "ef78127ef06215849861e7d3358e24cb5222281e"
PRICING_PREP_PR_NUMBER = 70
PRICING_PREP_PR_STATE = "MERGED"
PRICING_PREP_MERGE_COMMIT_SHA = "ef78127ef06215849861e7d3358e24cb5222281e"
PRICING_PREP_MERGE_PARENT_1 = "c2e5126b7e1d3aa25ef6e46352e030c346fc733a"
PRICING_PREP_MERGE_PARENT_2 = "ceb41980545982ac1a664a59d8caf8eb4526f90c"
PRICING_PREP_POST_MERGE_CI_RUN_ID = 40162573640
PRICING_PREP_POST_MERGE_CI_EVENT = "push"
PRICING_PREP_POST_MERGE_CI_HEAD_SHA = "ef78127ef06215849861e7d3358e24cb5222281e"
PRICING_PREP_POST_MERGE_CI_CONCLUSION = "success"
PRICING_PREP_POST_MERGE_CI_REQUIRED_JOBS: dict[str, str] = {
    "ai-service": "success",
    "backend": "success",
    "data-contract": "success",
    "mobile": "success",
}

OWNER_ATTESTATION_EVIDENCE_DATE = "2026-10-30"
OWNER_ATTESTATION_AUTHORITY = "PROJECT_OWNER"
OWNER_ATTESTATION_OBSERVATION_MODE = "MANUAL_PROVIDER_DASHBOARD_OBSERVATION_SANITIZED"
OWNER_ATTESTATION_SCOPE = "CANARY_READINESS_ATTESTATION_ONLY"

RECEIPT_CANDIDATE_STATUS = "PENDING_CHATGPT_AUDIT_AND_REPOSITORY_FREEZE"
REPOSITORY_AUTHORITATIVE_BEFORE_MERGE = False
BECOMES_REPOSITORY_AUTHORITATIVE_AFTER_CHATGPT_PASS_MERGE_AND_POSTMERGE_CI = True

PROVIDER_READINESS_READY_FOR_CANARY = "READY_FOR_CANARY"
ALL_CANARY_PROVIDER_READINESS_STATUS = "READY"
EFFECTIVE_AMENDMENT_STATUS = (
    "METHODOLOGY_APPROVED_OWNER_CANARY_READINESS_ATTESTED_LIVE_UNAUTHORIZED"
)
NEXT_GATE_ID = (
    "W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-OWNER-PROVIDER-READINESS-ATTESTATION-CHATGPT-AUDIT"
)

# Bound upstream artifact paths and hashes
PROVIDER_READINESS_PRICING_PREP_REL_PATH = (
    _prp_mod.PROVIDER_READINESS_PRICING_PREP_REL_PATH
)
EXPECTED_PROVIDER_READINESS_PRICING_PREP_FILE_SHA256 = (
    "ef94513ceb5d64a84da2ee3a4890e563dde19fb597e27d3e545bdbe4add58006"
)
EXPECTED_PROVIDER_READINESS_PRICING_PREP_INTERNAL_SHA256 = (
    "07f61e211c6e77ee3ed08936b04ee07ac090398e50047c7534ab30d32d24506e"
)

PUBLIC_PRICING_SNAPSHOT_REL_PATH = _prp_mod.PUBLIC_PRICING_SNAPSHOT_REL_PATH
EXPECTED_PUBLIC_PRICING_SNAPSHOT_FILE_SHA256 = (
    "2302724e26c24c7eec09ecafaa3a707bc51a45e505d4954f3661601473946cf6"
)
EXPECTED_PUBLIC_PRICING_SNAPSHOT_INTERNAL_SHA256 = (
    "bcc8daeb0d5feae6426446ffc206726f8d91c07bdad3b82df2b8bcddcacb5ffe"
)

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

# Deterministic self-hashes for the owner readiness attestation receipt artifact
EXPECTED_OWNER_READINESS_ATTESTATION_FILE_SHA256 = (
    "622878407081f5bb4566d8a29d827258031b52edecb067e0cf1ebe253a162a9d"
)
EXPECTED_OWNER_READINESS_ATTESTATION_INTERNAL_SHA256 = (
    "45af6219a72bcef6c79bd6b83d7a95f6c549342e13d73e266abe4ac1260edf86"
)


# ==============================================================================
# 2. DETERMINISTIC HELPERS, SANITIZATION & IMMUTABILITY GUARDS
# ==============================================================================


def _read_lf_sha256(path: Path) -> str:
    if not path.is_file():
        raise PlanBeforeLiveProtocolError(f"MISSING_REQUIRED_FILE: {path}")
    return sha256_bytes(normalize_lf_bytes(path.read_bytes()))


def _load_json_dict(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PlanBeforeLiveProtocolError(f"MISSING_REQUIRED_JSON_FILE: {path}")
    data = json.loads(normalize_lf_bytes(path.read_bytes()).decode("utf-8"))
    if not isinstance(data, dict):
        raise PlanBeforeLiveProtocolError(f"JSON_OBJECT_REQUIRED: {path}")
    return data


def _assert_not_inside_raw_evidence(path: Path, repo_root: Path) -> None:
    resolved = path.resolve()
    raw_root = (repo_root / _prep_mod.RAW_OUTPUT_ROOT_REL_PATH).resolve()
    if resolved == raw_root or raw_root in resolved.parents:
        raise PlanBeforeLiveProtocolError(
            f"RAW_EVIDENCE_WRITE_FORBIDDEN: {resolved} is inside {raw_root}"
        )


def _assert_not_immutable_upstream_artifact(path: Path, repo_root: Path) -> None:
    resolved = path.resolve()
    protected_rel_paths = (
        PROVIDER_READINESS_PRICING_PREP_REL_PATH,
        PUBLIC_PRICING_SNAPSHOT_REL_PATH,
        APPROVAL_RECEIPT_REL_PATH,
        DECISION_ARTIFACT_REL_PATH,
        CANARY_MANIFEST_REL_PATH,
        PREP_ARTIFACT_REL_PATH,
        PRIMARY_RESULTS_FREEZE_RECEIPT_REL_PATH,
        PRIMARY_RESULTS_MANIFEST_REL_PATH,
        FAILURE_DIAGNOSTIC_REL_PATH,
    )
    for rel_path in protected_rel_paths:
        target = (repo_root / rel_path).resolve()
        if resolved == target:
            raise PlanBeforeLiveProtocolError(
                f"IMMUTABLE_UPSTREAM_ARTIFACT_MUTATION_FORBIDDEN: {resolved}"
            )


FORBIDDEN_SCREENSHOT_EXTENSIONS: tuple[str, ...] = (
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".bmp",
    ".tiff",
)

SENSITIVE_ACCOUNT_AND_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("API_KEY_OPENAI_OR_ANTHROPIC", re.compile(r"\bsk-(?:proj-|ant-|live-|test-)?[A-Za-z0-9_\-]{6,}\b")),
    ("API_KEY_GOOGLE_AIZA", re.compile(r"\bAIza[0-9A-Za-z_\-]{10,}\b")),
    ("API_KEY_MASKED_AIZA", re.compile(r"\bAIza[0-9A-Za-z_\-*.\u2026]{2,}\b")),
    ("API_KEY_MASKED_SK", re.compile(r"\bsk-[A-Za-z0-9_\-*.\u2026]{3,}\b")),
    ("GOOGLE_BILLING_ACCOUNT_ID", re.compile(r"\b[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}\b", re.IGNORECASE)),
    ("OPENAI_ORG_ID", re.compile(r"\borg-[A-Za-z0-9]{8,}\b")),
    (
        "GOOGLE_PROJECT_NUMERIC_ID",
        re.compile(r"\b(?!40162573640\b|40099797847\b|40094419087\b)\d{11,15}\b"),
    ),
    ("EMAIL_ADDRESS", re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")),
    ("PAYMENT_CARD_PAN", re.compile(r"\b(?:\d{4}[ -]){3}\d{4}\b")),
    ("PAYMENT_TRANSACTION_ID", re.compile(r"\b(?:pi|ch|in|txn|py|seti)_[A-Za-z0-9]{10,}\b")),
    ("EXACT_VND_MONETARY_BALANCE", re.compile(r"\b\d[\d,._]*\s*(?:VND|₫)\b", re.IGNORECASE)),
)

FORBIDDEN_SENSITIVE_KEY_NAMES: frozenset[str] = frozenset(
    {
        "api_key",
        "api_key_prefix",
        "api_key_suffix",
        "card_last4",
        "payment_card_number",
        "billing_account_id",
        "project_numeric_id",
        "project_number",
        "organization_id",
        "org_id",
        "email",
        "owner_email",
        "owner_name",
        "personal_name",
        "transaction_id",
        "payment_transaction_id",
        "exact_vnd_balance",
        "exact_prepaid_vnd_balance",
        "exact_usd_balance",
        "exact_dollar_balance",
    }
)


def assert_no_sensitive_account_or_secret_data_in_attestation(
    payload: Any,
    *,
    context: str = "OWNER_PROVIDER_READINESS_ATTESTATION",
) -> None:
    """Reject secrets, API key suffixes/prefixes, card details, account/project/org IDs, emails, and exact balances."""
    assert_no_secrets_in_payload(payload, context=context)

    def _walk(node: Any, path_prefix: str) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                k_str = str(k)
                if k_str.lower() in FORBIDDEN_SENSITIVE_KEY_NAMES:
                    raise PlanBeforeLiveProtocolError(
                        f"SENSITIVE_FIELD_FORBIDDEN ({context}): forbidden key '{k_str}' at {path_prefix}"
                    )
                _walk(v, f"{path_prefix}.{k_str}")
        elif isinstance(node, list):
            for idx, item in enumerate(node):
                _walk(item, f"{path_prefix}[{idx}]")
        elif isinstance(node, str):
            for label, pattern in SENSITIVE_ACCOUNT_AND_SECRET_PATTERNS:
                if pattern.search(node):
                    raise PlanBeforeLiveProtocolError(
                        f"SENSITIVE_DATA_LEAK_DETECTED ({context}): pattern {label} matched at {path_prefix}"
                    )

    _walk(payload, "$")


def assert_no_screenshots_in_evaluation_or_research_dirs(
    repo_root: Path = REPO_ROOT,
) -> None:
    """Ensure no dashboard screenshot files are stored in data/evaluation/w06 or docs/research."""
    for rel_dir in ("data/evaluation/w06", "docs/research"):
        target_dir = repo_root / rel_dir
        if not target_dir.is_dir():
            continue
        for file_path in target_dir.rglob("*"):
            if (
                file_path.is_file()
                and file_path.suffix.lower() in FORBIDDEN_SCREENSHOT_EXTENSIONS
            ):
                raise PlanBeforeLiveProtocolError(
                    f"SCREENSHOT_STORAGE_FORBIDDEN: found {file_path.relative_to(repo_root).as_posix()}"
                )


def _verify_git_base_and_merge_lineage(repo_root: Path) -> None:
    cat_proc = subprocess.run(
        ["git", "cat-file", "-e", f"{AUTHORITATIVE_BASE_DEVELOP_SHA}^{{commit}}"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if cat_proc.returncode == 0:
        proc = subprocess.run(
            [
                "git",
                "merge-base",
                "--is-ancestor",
                AUTHORITATIVE_BASE_DEVELOP_SHA,
                "HEAD",
            ],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise PlanBeforeLiveProtocolError(
                f"GIT_BASE_LINEAGE_MISMATCH: HEAD does not descend from {AUTHORITATIVE_BASE_DEVELOP_SHA}"
            )

        p1_cat = subprocess.run(
            ["git", "cat-file", "-e", f"{PRICING_PREP_MERGE_COMMIT_SHA}^1"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        p2_cat = subprocess.run(
            ["git", "cat-file", "-e", f"{PRICING_PREP_MERGE_COMMIT_SHA}^2"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        if p1_cat.returncode == 0 and p2_cat.returncode == 0:
            p1 = subprocess.run(
                ["git", "rev-parse", f"{PRICING_PREP_MERGE_COMMIT_SHA}^1"],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
            ).stdout.strip()
            p2 = subprocess.run(
                ["git", "rev-parse", f"{PRICING_PREP_MERGE_COMMIT_SHA}^2"],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
            ).stdout.strip()
            if p1 != PRICING_PREP_MERGE_PARENT_1:
                raise PlanBeforeLiveProtocolError(
                    f"MERGE_PARENT_1_MISMATCH: expected {PRICING_PREP_MERGE_PARENT_1}, got {p1}"
                )
            if p2 != PRICING_PREP_MERGE_PARENT_2:
                raise PlanBeforeLiveProtocolError(
                    f"MERGE_PARENT_2_MISMATCH: expected {PRICING_PREP_MERGE_PARENT_2}, got {p2}"
                )


# ==============================================================================
# 3. CANDIDATE READINESS VALIDATION & EFFECTIVE STATE DERIVATION
# ==============================================================================


def validate_sanitized_candidate_attestations(
    candidate_attestations: dict[str, dict[str, Any]],
) -> None:
    """Validate C1, C2, and C3 sanitized owner readiness attestations against frozen amendment requirements."""
    if set(candidate_attestations.keys()) != {"C1", "C2", "C3"}:
        raise PlanBeforeLiveProtocolError(
            "CANDIDATE_ATTESTATION_KEYS_MISMATCH: must be C1, C2, C3"
        )

    # C1 / GOOGLE
    c1 = candidate_attestations["C1"]
    if (
        c1.get("candidate_id") != "C1"
        or c1.get("provider") != "GOOGLE"
        or c1.get("exact_model_id") != "gemini-3.8-flash"
    ):
        raise PlanBeforeLiveProtocolError("C1_IDENTITY_MISMATCH")
    if (
        c1.get("billing_surface")
        != "GEMINI_DEVELOPER_API_GOOGLE_AI_STUDIO_STANDARD_PAID_TIER"
    ):
        raise PlanBeforeLiveProtocolError("C1_BILLING_SURFACE_MISMATCH")
    c1_obs = c1.get("owner_observed", {})
    if c1_obs.get("billing_active") is not True:
        raise PlanBeforeLiveProtocolError("C1_BILLING_ACTIVE_MUST_BE_TRUE")
    if c1_obs.get("paid_tier_active") is not True:
        raise PlanBeforeLiveProtocolError("C1_PAID_TIER_ACTIVE_MUST_BE_TRUE")
    if c1_obs.get("usage_tier") != "TIER_1":
        raise PlanBeforeLiveProtocolError("C1_USAGE_TIER_MUST_BE_TIER_1")
    if c1_obs.get("positive_prepaid_credit_available") is not True:
        raise PlanBeforeLiveProtocolError(
            "C1_POSITIVE_PREPAID_CREDIT_AVAILABLE_MUST_BE_TRUE"
        )
    if c1_obs.get("exact_model_visible_in_rate_limit_dashboard") is not True:
        raise PlanBeforeLiveProtocolError(
            "C1_EXACT_MODEL_VISIBLE_IN_RATE_LIMIT_DASHBOARD_MUST_BE_TRUE"
        )
    if c1_obs.get("standard_rpm_limit") != 1000:
        raise PlanBeforeLiveProtocolError("C1_STANDARD_RPM_LIMIT_MUST_BE_1000")
    if c1_obs.get("standard_input_tpm_limit") != 2000000:
        raise PlanBeforeLiveProtocolError(
            "C1_STANDARD_INPUT_TPM_LIMIT_MUST_BE_2000000"
        )
    if c1_obs.get("standard_rpd_limit") != 10000:
        raise PlanBeforeLiveProtocolError("C1_STANDARD_RPD_LIMIT_MUST_BE_10000")
    if (
        c1_obs.get("required_max_candidate_calls_under_frozen_amendment") != 63
        or c1_obs.get("canary_assigned_calls") != 3
    ):
        raise PlanBeforeLiveProtocolError("C1_CALL_BUDGET_REFERENCE_MISMATCH")
    if (
        c1_obs.get("rpm_sufficient_for_frozen_canary") is not True
        or c1_obs.get("tpm_sufficient_for_frozen_canary") is not True
        or c1_obs.get("rpd_sufficient_for_frozen_canary") is not True
    ):
        raise PlanBeforeLiveProtocolError("C1_CANARY_CAPACITY_SUFFICIENCY_MISMATCH")
    if c1.get("provider_readiness") != PROVIDER_READINESS_READY_FOR_CANARY:
        raise PlanBeforeLiveProtocolError("C1_PROVIDER_READINESS_MUST_BE_READY_FOR_CANARY")
    if c1.get("exact_prepaid_vnd_balance_stored") is not False:
        raise PlanBeforeLiveProtocolError("C1_EXACT_VND_BALANCE_MUST_NOT_BE_STORED")

    # C2 / OPENAI
    c2 = candidate_attestations["C2"]
    if (
        c2.get("candidate_id") != "C2"
        or c2.get("provider") != "OPENAI"
        or c2.get("exact_model_id") != "gpt-6.1-sol"
    ):
        raise PlanBeforeLiveProtocolError("C2_IDENTITY_MISMATCH")
    if (
        c2.get("billing_surface")
        != "OPENAI_STANDARD_API_CHAT_COMPLETIONS_DEFAULT_SERVICE_TIER"
    ):
        raise PlanBeforeLiveProtocolError("C2_BILLING_SURFACE_MISMATCH")
    c2_obs = c2.get("owner_observed", {})
    if c2_obs.get("billing_active") is not True:
        raise PlanBeforeLiveProtocolError("C2_BILLING_ACTIVE_MUST_BE_TRUE")
    if c2_obs.get("positive_api_credit_available") is not True:
        raise PlanBeforeLiveProtocolError(
            "C2_POSITIVE_API_CREDIT_AVAILABLE_MUST_BE_TRUE"
        )
    if c2_obs.get("api_credit_sufficient_for_canary_planning_envelope") is not True:
        raise PlanBeforeLiveProtocolError(
            "C2_API_CREDIT_SUFFICIENT_FOR_CANARY_PLANNING_ENVELOPE_MUST_BE_TRUE"
        )
    if c2_obs.get("usage_tier") != "BUILD":
        raise PlanBeforeLiveProtocolError("C2_USAGE_TIER_MUST_BE_BUILD")
    if c2_obs.get("organization_spend_limit_blocking") is not False:
        raise PlanBeforeLiveProtocolError(
            "C2_ORGANIZATION_SPEND_LIMIT_BLOCKING_MUST_BE_FALSE"
        )
    if c2_obs.get("standard_rpm_limit") != 5000:
        raise PlanBeforeLiveProtocolError("C2_STANDARD_RPM_LIMIT_MUST_BE_5000")
    if c2_obs.get("standard_tpm_limit") != 1000000:
        raise PlanBeforeLiveProtocolError("C2_STANDARD_TPM_LIMIT_MUST_BE_1000000")
    if (
        c2_obs.get("required_max_candidate_calls_under_frozen_amendment") != 63
        or c2_obs.get("canary_assigned_calls") != 3
    ):
        raise PlanBeforeLiveProtocolError("C2_CALL_BUDGET_REFERENCE_MISMATCH")
    if (
        c2_obs.get("rpm_sufficient_for_frozen_canary") is not True
        or c2_obs.get("tpm_sufficient_for_frozen_canary") is not True
    ):
        raise PlanBeforeLiveProtocolError("C2_CANARY_CAPACITY_SUFFICIENCY_MISMATCH")
    if c2.get("provider_readiness") != PROVIDER_READINESS_READY_FOR_CANARY:
        raise PlanBeforeLiveProtocolError("C2_PROVIDER_READINESS_MUST_BE_READY_FOR_CANARY")
    if c2.get("exact_current_dollar_balance_stored") is not False:
        raise PlanBeforeLiveProtocolError("C2_EXACT_DOLLAR_BALANCE_MUST_NOT_BE_STORED")

    # C3 / ANTHROPIC
    c3 = candidate_attestations["C3"]
    if (
        c3.get("candidate_id") != "C3"
        or c3.get("provider") != "ANTHROPIC"
        or c3.get("exact_model_id") != "claude-sonnet-5-5"
    ):
        raise PlanBeforeLiveProtocolError("C3_IDENTITY_MISMATCH")
    if (
        c3.get("billing_surface")
        != "ANTHROPIC_CLAUDE_API_FIRST_PARTY_DIRECT_MESSAGES_STANDARD_GLOBAL"
    ):
        raise PlanBeforeLiveProtocolError("C3_BILLING_SURFACE_MISMATCH")
    c3_obs = c3.get("owner_observed", {})
    if c3_obs.get("billing_active") is not True:
        raise PlanBeforeLiveProtocolError("C3_BILLING_ACTIVE_MUST_BE_TRUE")
    if c3_obs.get("positive_credit_available") is not True:
        raise PlanBeforeLiveProtocolError(
            "C3_POSITIVE_CREDIT_AVAILABLE_MUST_BE_TRUE"
        )
    if c3_obs.get("exact_model_visible_in_rate_limit_dashboard") is not True:
        raise PlanBeforeLiveProtocolError(
            "C3_EXACT_MODEL_VISIBLE_IN_RATE_LIMIT_DASHBOARD_MUST_BE_TRUE"
        )
    if c3_obs.get("account_tier") != "EVALUATION_TIER":
        raise PlanBeforeLiveProtocolError(
            "C3_ACCOUNT_TIER_MUST_BE_EVALUATION_TIER"
        )
    if c3_obs.get("input_token_limit") != 500000:
        raise PlanBeforeLiveProtocolError("C3_INPUT_TOKEN_LIMIT_MUST_BE_500000")
    if c3_obs.get("output_token_limit") != 80000:
        raise PlanBeforeLiveProtocolError("C3_OUTPUT_TOKEN_LIMIT_MUST_BE_80000")
    if c3_obs.get("request_limit") != 1000:
        raise PlanBeforeLiveProtocolError("C3_REQUEST_LIMIT_MUST_BE_1000")
    if c3_obs.get("canary_assigned_calls") != 3:
        raise PlanBeforeLiveProtocolError("C3_CANARY_ASSIGNED_CALLS_MUST_BE_3")
    if c3_obs.get("configured_max_output_tokens_per_call") != 16384:
        raise PlanBeforeLiveProtocolError(
            "C3_CONFIGURED_MAX_OUTPUT_TOKENS_PER_CALL_MUST_BE_16384"
        )
    expected_three_call_ref = (
        c3_obs["canary_assigned_calls"]
        * c3_obs["configured_max_output_tokens_per_call"]
    )
    if (
        expected_three_call_ref != 49152
        or c3_obs.get("configured_three_call_max_output_reference") != 49152
    ):
        raise PlanBeforeLiveProtocolError(
            "C3_THREE_CALL_MAX_OUTPUT_REFERENCE_MUST_BE_49152"
        )
    if not (
        c3_obs["configured_three_call_max_output_reference"]
        < c3_obs["output_token_limit"]
    ):
        raise PlanBeforeLiveProtocolError(
            "C3_THREE_CALL_MAX_OUTPUT_REFERENCE_MUST_BE_LESS_THAN_OUTPUT_TOKEN_LIMIT"
        )
    if (
        c3_obs.get(
            "three_call_max_output_reference_strictly_less_than_output_token_limit"
        )
        is not True
    ):
        raise PlanBeforeLiveProtocolError(
            "C3_THREE_CALL_COMPARISON_FLAG_MUST_BE_TRUE"
        )
    if (
        c3_obs.get("input_capacity_sufficient_for_frozen_canary_planning_envelope")
        is not True
        or c3_obs.get("output_capacity_sufficient_for_frozen_canary_reference")
        is not True
        or c3_obs.get("request_capacity_sufficient_for_frozen_canary") is not True
    ):
        raise PlanBeforeLiveProtocolError("C3_CANARY_CAPACITY_SUFFICIENCY_MISMATCH")
    if c3.get("provider_readiness") != PROVIDER_READINESS_READY_FOR_CANARY:
        raise PlanBeforeLiveProtocolError("C3_PROVIDER_READINESS_MUST_BE_READY_FOR_CANARY")
    if (
        c3.get("generalized_as_readiness_proof_for_future_60_call_comparative_run")
        is not False
    ):
        raise PlanBeforeLiveProtocolError(
            "C3_EVALUATION_TIER_LIMITS_MUST_NOT_BE_GENERALIZED_TO_60_CALL_COMPARATIVE_RUN"
        )
    if (
        c3.get("comparative_readiness_must_be_rechecked_before_comparative_authorization")
        is not True
    ):
        raise PlanBeforeLiveProtocolError(
            "C3_COMPARATIVE_READINESS_RECHECK_REQUIREMENT_MUST_BE_TRUE"
        )


def derive_effective_owner_readiness_state(
    *,
    pricing_prep_payload: dict[str, Any],
    approval_receipt_payload: dict[str, Any],
    owner_attestation_payload: dict[str, Any],
) -> dict[str, Any]:
    """Derive effective owner readiness state while preserving strict live/authorization firewalls."""
    if (
        pricing_prep_payload.get("artifact_id")
        != _prp_mod.PROVIDER_READINESS_PRICING_PREP_ARTIFACT_ID
    ):
        raise PlanBeforeLiveProtocolError("INVALID_PRICING_PREP_ARTIFACT_ID")
    prep_flags = pricing_prep_payload.get(
        "scientific_and_execution_firewall_flags", {}
    )
    prep_matrix = pricing_prep_payload.get("provider_readiness_matrix", {})
    if (
        prep_flags.get("C1_PROVIDER_READINESS") != "NOT_YET_ATTESTED"
        or prep_flags.get("C2_PROVIDER_READINESS") != "NOT_YET_ATTESTED"
        or prep_flags.get("C3_PROVIDER_READINESS") != "NOT_YET_ATTESTED"
        or prep_matrix.get("C1_PROVIDER_READINESS") != "NOT_YET_ATTESTED"
        or prep_matrix.get("C2_PROVIDER_READINESS") != "NOT_YET_ATTESTED"
        or prep_matrix.get("C3_PROVIDER_READINESS") != "NOT_YET_ATTESTED"
    ):
        raise PlanBeforeLiveProtocolError(
            "HISTORICAL_PRICING_PREP_MUST_PRESERVE_NOT_YET_ATTESTED"
        )

    if (
        approval_receipt_payload.get("artifact_id")
        != _app_mod.APPROVAL_RECEIPT_ARTIFACT_ID
    ):
        raise PlanBeforeLiveProtocolError("INVALID_APPROVAL_RECEIPT_ARTIFACT_ID")
    if approval_receipt_payload.get("AMENDMENT_APPROVED") is not True:
        raise PlanBeforeLiveProtocolError("APPROVAL_RECEIPT_MUST_BE_APPROVED")

    if (
        owner_attestation_payload.get("artifact_id")
        != OWNER_READINESS_ATTESTATION_ARTIFACT_ID
    ):
        raise PlanBeforeLiveProtocolError("INVALID_OWNER_ATTESTATION_ARTIFACT_ID")

    validate_sanitized_candidate_attestations(
        owner_attestation_payload.get("candidate_readiness_attestations", {})
    )

    if owner_attestation_payload.get("OWNER_PROVIDER_READINESS_ATTESTED") is not True:
        raise PlanBeforeLiveProtocolError(
            "OWNER_PROVIDER_READINESS_ATTESTED_MUST_BE_TRUE"
        )
    for cid in ("C1", "C2", "C3"):
        if (
            owner_attestation_payload.get(f"{cid}_PROVIDER_READINESS")
            != PROVIDER_READINESS_READY_FOR_CANARY
        ):
            raise PlanBeforeLiveProtocolError(
                f"{cid}_PROVIDER_READINESS_MUST_BE_READY_FOR_CANARY"
            )
    if (
        owner_attestation_payload.get("ALL_CANARY_PROVIDER_READINESS")
        != ALL_CANARY_PROVIDER_READINESS_STATUS
    ):
        raise PlanBeforeLiveProtocolError(
            "ALL_CANARY_PROVIDER_READINESS_MUST_BE_READY"
        )

    if (
        owner_attestation_payload.get("READY_FOR_CANARY_IS_NOT_CANARY_AUTHORIZATION")
        is not True
        or owner_attestation_payload.get("CANARY_OPERATIONAL_PASS_STILL_REQUIRES_9_OF_9")
        is not True
        or owner_attestation_payload.get(
            "CANARY_PASS_DOES_NOT_AUTO_AUTHORIZE_COMPARATIVE"
        )
        is not True
    ):
        raise PlanBeforeLiveProtocolError(
            "READINESS_NON_AUTHORIZATION_SEMANTIC_GUARDS_MUST_BE_TRUE"
        )

    for live_flag in (
        "AMENDED_CANARY_LIVE_AUTHORIZED",
        "AMENDED_COMPARATIVE_LIVE_AUTHORIZED",
        "AMENDED_LIVE_AUTHORIZED",
        "AMENDED_LIVE_EXECUTED",
        "CANARY_EXECUTED",
        "COMPARATIVE_EXECUTED",
    ):
        if owner_attestation_payload.get(live_flag) is not False:
            raise PlanBeforeLiveProtocolError(
                f"OWNER_READINESS_ATTESTATION_MUST_NOT_AUTHORIZE_OR_EXECUTE_LIVE_CALLS: {live_flag} must be False"
            )

    if owner_attestation_payload.get("LIVE_PROVIDER_CALLS_NEW") != 0:
        raise PlanBeforeLiveProtocolError("LIVE_PROVIDER_CALLS_NEW_MUST_BE_ZERO")

    return {
        "derivation_rule": (
            "approval_receipt.AMENDMENT_APPROVED == true "
            "AND pricing_prep.C1/C2/C3_PROVIDER_READINESS == 'NOT_YET_ATTESTED' (historical immutable PREP) "
            "AND owner_attestation.OWNER_PROVIDER_READINESS_ATTESTED == true "
            "AND owner_attestation.C1/C2/C3_PROVIDER_READINESS == 'READY_FOR_CANARY' "
            "=> all_canary_provider_readiness = 'READY', amended_canary_live_authorized = false, "
            "amended_comparative_live_authorized = false"
        ),
        "historical_pricing_prep_readiness_not_yet_attested_preserved": True,
        "historical_pricing_prep_contradiction": False,
        "owner_provider_readiness_attested": True,
        "c1_provider_readiness": PROVIDER_READINESS_READY_FOR_CANARY,
        "c2_provider_readiness": PROVIDER_READINESS_READY_FOR_CANARY,
        "c3_provider_readiness": PROVIDER_READINESS_READY_FOR_CANARY,
        "all_canary_provider_readiness": ALL_CANARY_PROVIDER_READINESS_STATUS,
        "attestation_scope": OWNER_ATTESTATION_SCOPE,
        "comparative_60_call_readiness_attested": False,
        "comparative_readiness_must_be_rechecked_before_comparative_authorization": True,
        "ready_for_canary_is_not_canary_authorization": True,
        "canary_operational_pass_still_requires_9_of_9": True,
        "canary_pass_does_not_auto_authorize_comparative": True,
        "effective_amendment_status": EFFECTIVE_AMENDMENT_STATUS,
        "effective_amended_canary_live_authorized": False,
        "effective_amended_comparative_live_authorized": False,
        "effective_amended_live_authorized": False,
        "effective_amended_live_executed": False,
        "effective_live_provider_calls_new": 0,
    }


def _verify_all_upstream_authorities(repo_root: Path) -> dict[str, Any]:
    _verify_git_base_and_merge_lineage(repo_root)
    assert_no_screenshots_in_evaluation_or_research_dirs(repo_root)

    # Verify primary freeze, diagnostic, prep, decision, approval receipt, and pricing prep verifiers
    freeze_summary = _freeze_mod.verify_committed_results_freeze_artifacts_from_disk(
        repo_root=repo_root, verify_preflight_dry_run=False
    )
    if not freeze_summary.get("verified"):
        raise PlanBeforeLiveProtocolError("PRIMARY_FREEZE_VERIFICATION_FAILED")

    diag_summary = _diag_mod.verify_w06_dev_select_failure_diagnostic(
        repo_root=repo_root
    )
    if not diag_summary.get("verified"):
        raise PlanBeforeLiveProtocolError("FAILURE_DIAGNOSTIC_VERIFICATION_FAILED")

    prep_summary = _prep_mod.verify_w06_execution_environment_amendment_prep(
        repo_root=repo_root
    )
    if not prep_summary.get("verified"):
        raise PlanBeforeLiveProtocolError("PREP_ARTIFACT_VERIFICATION_FAILED")

    dec_summary = _dec_mod.verify_w06_execution_environment_amendment_decision_freeze(
        repo_root=repo_root
    )
    if not dec_summary.get("verified"):
        raise PlanBeforeLiveProtocolError("DECISION_FREEZE_VERIFICATION_FAILED")

    app_summary = _app_mod.verify_w06_execution_environment_amendment_approval_receipt(
        repo_root=repo_root
    )
    if not app_summary.get("verified"):
        raise PlanBeforeLiveProtocolError("APPROVAL_RECEIPT_VERIFICATION_FAILED")

    prp_summary = _prp_mod.verify_provider_readiness_pricing_prep_artifacts(
        repo_root=repo_root
    )
    if prp_summary.get("status") != "PASS":
        raise PlanBeforeLiveProtocolError(
            "PROVIDER_READINESS_PRICING_PREP_VERIFICATION_FAILED"
        )

    # Cross-check exact file & internal SHA256s for all bound upstream artifacts
    pricing_prep_path = repo_root / PROVIDER_READINESS_PRICING_PREP_REL_PATH
    if (
        _read_lf_sha256(pricing_prep_path)
        != EXPECTED_PROVIDER_READINESS_PRICING_PREP_FILE_SHA256
    ):
        raise PlanBeforeLiveProtocolError("PRICING_PREP_FILE_SHA256_MISMATCH")
    pricing_prep_payload = _load_json_dict(pricing_prep_path)
    if (
        pricing_prep_payload.get("provider_readiness_pricing_prep_sha256")
        != EXPECTED_PROVIDER_READINESS_PRICING_PREP_INTERNAL_SHA256
    ):
        raise PlanBeforeLiveProtocolError("PRICING_PREP_INTERNAL_SHA256_MISMATCH")

    pricing_snap_path = repo_root / PUBLIC_PRICING_SNAPSHOT_REL_PATH
    if (
        _read_lf_sha256(pricing_snap_path)
        != EXPECTED_PUBLIC_PRICING_SNAPSHOT_FILE_SHA256
    ):
        raise PlanBeforeLiveProtocolError("PUBLIC_PRICING_SNAPSHOT_FILE_SHA256_MISMATCH")
    pricing_snap_payload = _load_json_dict(pricing_snap_path)
    if (
        pricing_snap_payload.get("public_pricing_snapshot_sha256")
        != EXPECTED_PUBLIC_PRICING_SNAPSHOT_INTERNAL_SHA256
    ):
        raise PlanBeforeLiveProtocolError(
            "PUBLIC_PRICING_SNAPSHOT_INTERNAL_SHA256_MISMATCH"
        )

    approval_path = repo_root / APPROVAL_RECEIPT_REL_PATH
    if _read_lf_sha256(approval_path) != EXPECTED_APPROVAL_RECEIPT_FILE_SHA256:
        raise PlanBeforeLiveProtocolError("APPROVAL_RECEIPT_FILE_SHA256_MISMATCH")
    approval_payload = _load_json_dict(approval_path)
    if (
        approval_payload.get("approval_receipt_internal_sha256")
        != EXPECTED_APPROVAL_RECEIPT_INTERNAL_SHA256
    ):
        raise PlanBeforeLiveProtocolError("APPROVAL_RECEIPT_INTERNAL_SHA256_MISMATCH")

    decision_path = repo_root / DECISION_ARTIFACT_REL_PATH
    if _read_lf_sha256(decision_path) != EXPECTED_DECISION_ARTIFACT_FILE_SHA256:
        raise PlanBeforeLiveProtocolError("DECISION_ARTIFACT_FILE_SHA256_MISMATCH")
    decision_payload = _load_json_dict(decision_path)
    if (
        decision_payload.get("decision_artifact_internal_sha256")
        != EXPECTED_DECISION_ARTIFACT_INTERNAL_SHA256
    ):
        raise PlanBeforeLiveProtocolError("DECISION_ARTIFACT_INTERNAL_SHA256_MISMATCH")

    canary_path = repo_root / CANARY_MANIFEST_REL_PATH
    if _read_lf_sha256(canary_path) != EXPECTED_CANARY_MANIFEST_FILE_SHA256:
        raise PlanBeforeLiveProtocolError("CANARY_MANIFEST_FILE_SHA256_MISMATCH")
    canary_payload = _load_json_dict(canary_path)
    if (
        canary_payload.get("canary_manifest_internal_sha256")
        != EXPECTED_CANARY_MANIFEST_INTERNAL_SHA256
    ):
        raise PlanBeforeLiveProtocolError("CANARY_MANIFEST_INTERNAL_SHA256_MISMATCH")

    freeze_receipt_path = repo_root / PRIMARY_RESULTS_FREEZE_RECEIPT_REL_PATH
    if (
        _read_lf_sha256(freeze_receipt_path)
        != EXPECTED_PRIMARY_RESULTS_FREEZE_RECEIPT_FILE_SHA256
    ):
        raise PlanBeforeLiveProtocolError(
            "PRIMARY_RESULTS_FREEZE_RECEIPT_FILE_SHA256_MISMATCH"
        )
    freeze_receipt_payload = _load_json_dict(freeze_receipt_path)
    if (
        freeze_receipt_payload.get("results_freeze_receipt_sha256")
        != EXPECTED_PRIMARY_RESULTS_FREEZE_RECEIPT_INTERNAL_SHA256
    ):
        raise PlanBeforeLiveProtocolError(
            "PRIMARY_RESULTS_FREEZE_RECEIPT_INTERNAL_SHA256_MISMATCH"
        )

    bundle_sha = compute_scientific_code_bundle_sha256(repo_root)
    if bundle_sha != EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"SCIENTIFIC_CODE_BUNDLE_SHA256_MISMATCH: expected {EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256}, got {bundle_sha}"
        )

    primary_metric_auth = _prp_mod.read_and_crosscheck_primary_metric_authority(
        repo_root
    )

    dev_bundle = load_and_verify_frozen_dev_bundle()
    if (
        len(dev_bundle.dev_tune_fixtures) != 20
        or len(dev_bundle.dev_select_fixtures) != 60
    ):
        raise PlanBeforeLiveProtocolError("DEV_FIXTURE_BUNDLE_COUNT_MISMATCH")

    cand_reg = load_and_verify_candidate_registry()
    if cand_reg.registry_sha256 != _dec_mod.EXPECTED_CANDIDATE_REGISTRY_SHA256:
        raise PlanBeforeLiveProtocolError("CANDIDATE_REGISTRY_SHA256_MISMATCH")

    if (
        compute_provider_config_registry_sha256(cand_reg)
        != _dec_mod.EXPECTED_PROVIDER_CONFIG_REGISTRY_SHA256
    ):
        raise PlanBeforeLiveProtocolError("PROVIDER_CONFIG_REGISTRY_SHA256_MISMATCH")

    final100_sha = _read_lf_sha256(
        repo_root / "data/evaluation/w06/w06_scenarios_freeze_v1.json"
    )
    if final100_sha != FORBIDDEN_FINAL100_BUNDLE_SHA256:
        raise PlanBeforeLiveProtocolError("FINAL100_SCENARIOS_FREEZE_TOUCHED")
    p11_sha = _read_lf_sha256(
        repo_root / "data/evaluation/w06/w06_p11_assignment_manifest_v1.json"
    )
    if p11_sha != FORBIDDEN_P11_MANIFEST_SHA256:
        raise PlanBeforeLiveProtocolError("P11_MANIFEST_TOUCHED")

    return {
        "pricing_prep_payload": pricing_prep_payload,
        "pricing_snap_payload": pricing_snap_payload,
        "approval_payload": approval_payload,
        "decision_payload": decision_payload,
        "canary_payload": canary_payload,
        "primary_metric_auth": primary_metric_auth,
    }


# ==============================================================================
# 4. BUILD OWNER PROVIDER READINESS ATTESTATION RECEIPT PAYLOAD & MARKDOWN
# ==============================================================================


def build_w06_owner_provider_readiness_attestation_payload(
    *,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    with NetworkKillSwitchGuard():
        verified = _verify_all_upstream_authorities(repo_root)
        pricing_prep_payload = verified["pricing_prep_payload"]
        approval_payload = verified["approval_payload"]
        primary_metric_auth = verified["primary_metric_auth"]

        candidate_attestations: dict[str, dict[str, Any]] = {
            "C1": {
                "candidate_id": "C1",
                "provider": "GOOGLE",
                "exact_model_id": "gemini-3.8-flash",
                "billing_surface": "GEMINI_DEVELOPER_API_GOOGLE_AI_STUDIO_STANDARD_PAID_TIER",
                "owner_observed_evidence_date": OWNER_ATTESTATION_EVIDENCE_DATE,
                "owner_observed": {
                    "billing_active": True,
                    "paid_tier_active": True,
                    "usage_tier": "TIER_1",
                    "positive_prepaid_credit_available": True,
                    "exact_model_visible_in_rate_limit_dashboard": True,
                    "standard_rpm_limit": 1000,
                    "standard_input_tpm_limit": 2000000,
                    "standard_rpd_limit": 10000,
                    "required_max_candidate_calls_under_frozen_amendment": 63,
                    "canary_assigned_calls": 3,
                    "rpm_sufficient_for_frozen_canary": True,
                    "tpm_sufficient_for_frozen_canary": True,
                    "rpd_sufficient_for_frozen_canary": True,
                },
                "provider_readiness": PROVIDER_READINESS_READY_FOR_CANARY,
                "exact_prepaid_vnd_balance_stored": False,
                "sanitization_note": (
                    "Exact prepaid VND balance is operational account evidence, not a scientific "
                    "experiment variable; boolean positive_prepaid_credit_available=true is recorded."
                ),
            },
            "C2": {
                "candidate_id": "C2",
                "provider": "OPENAI",
                "exact_model_id": "gpt-6.1-sol",
                "billing_surface": "OPENAI_STANDARD_API_CHAT_COMPLETIONS_DEFAULT_SERVICE_TIER",
                "owner_observed_evidence_date": OWNER_ATTESTATION_EVIDENCE_DATE,
                "owner_observed": {
                    "billing_active": True,
                    "positive_api_credit_available": True,
                    "api_credit_sufficient_for_canary_planning_envelope": True,
                    "usage_tier": "BUILD",
                    "organization_spend_limit_blocking": False,
                    "exact_model_access_supported_by": [
                        "current official gpt-6.1-sol model availability for Build tier",
                        "historical successful frozen primary C2 responses using the exact candidate family/config",
                    ],
                    "standard_rpm_limit": 5000,
                    "standard_tpm_limit": 1000000,
                    "required_max_candidate_calls_under_frozen_amendment": 63,
                    "canary_assigned_calls": 3,
                    "rpm_sufficient_for_frozen_canary": True,
                    "tpm_sufficient_for_frozen_canary": True,
                },
                "public_model_rate_limit_authority_domains": list(
                    _prp_mod.ALLOWLISTED_PRICING_DOMAINS_BY_PROVIDER["OPENAI"]
                ),
                "provider_readiness": PROVIDER_READINESS_READY_FOR_CANARY,
                "exact_current_dollar_balance_stored": False,
                "sanitization_note": (
                    "Exact current USD balance is omitted; boolean positive_api_credit_available=true "
                    "and api_credit_sufficient_for_canary_planning_envelope=true are recorded."
                ),
            },
            "C3": {
                "candidate_id": "C3",
                "provider": "ANTHROPIC",
                "exact_model_id": "claude-sonnet-5-5",
                "billing_surface": "ANTHROPIC_CLAUDE_API_FIRST_PARTY_DIRECT_MESSAGES_STANDARD_GLOBAL",
                "owner_observed_evidence_date": OWNER_ATTESTATION_EVIDENCE_DATE,
                "owner_observed": {
                    "billing_active": True,
                    "positive_credit_available": True,
                    "exact_model_visible_in_rate_limit_dashboard": True,
                    "account_tier": "EVALUATION_TIER",
                    "input_token_limit": 500000,
                    "output_token_limit": 80000,
                    "request_limit": 1000,
                    "canary_assigned_calls": 3,
                    "configured_max_output_tokens_per_call": 16384,
                    "configured_three_call_max_output_reference": 49152,
                    "three_call_max_output_reference_comparison": "49152 < 80000",
                    "three_call_max_output_reference_strictly_less_than_output_token_limit": True,
                    "input_capacity_sufficient_for_frozen_canary_planning_envelope": True,
                    "output_capacity_sufficient_for_frozen_canary_reference": True,
                    "request_capacity_sufficient_for_frozen_canary": True,
                },
                "provider_readiness": PROVIDER_READINESS_READY_FOR_CANARY,
                "attestation_scope": OWNER_ATTESTATION_SCOPE,
                "generalized_as_readiness_proof_for_future_60_call_comparative_run": False,
                "comparative_readiness_must_be_rechecked_before_comparative_authorization": True,
                "comparative_scope_firewall_note": (
                    "Evaluation Tier limits (500,000 input / 80,000 output / 1,000 requests) are "
                    "attested ONLY for the 3-call C3 canary slice (3 * 16,384 = 49,152 < 80,000). "
                    "They are NOT generalized as readiness proof for the future 60-call comparative "
                    "run; comparative readiness must be rechecked before comparative authorization."
                ),
            },
        }

        payload_without_hash: dict[str, Any] = {
            "artifact_id": OWNER_READINESS_ATTESTATION_ARTIFACT_ID,
            "task_id": TASK_ID,
            "schema_version": "1.0.0",
            "authoritative_base_develop_sha": AUTHORITATIVE_BASE_DEVELOP_SHA,
            "owner_attestation_authority": OWNER_ATTESTATION_AUTHORITY,
            "owner_observed_readiness_evidence_date": OWNER_ATTESTATION_EVIDENCE_DATE,
            "observation_mode": OWNER_ATTESTATION_OBSERVATION_MODE,
            "attestation_scope": OWNER_ATTESTATION_SCOPE,
            "track_classification": _prp_mod.TRACK_CLASSIFICATION,
            "primary_experiment_classification": _dec_mod.PRIMARY_EXPERIMENT_CLASSIFICATION,
            "AMENDMENT_METHODOLOGY_SELECTED": True,
            "AMENDMENT_APPROVED": True,
            "OWNER_PROVIDER_READINESS_ATTESTED": True,
            "C1_PROVIDER_READINESS": PROVIDER_READINESS_READY_FOR_CANARY,
            "C2_PROVIDER_READINESS": PROVIDER_READINESS_READY_FOR_CANARY,
            "C3_PROVIDER_READINESS": PROVIDER_READINESS_READY_FOR_CANARY,
            "ALL_CANARY_PROVIDER_READINESS": ALL_CANARY_PROVIDER_READINESS_STATUS,
            "READY_FOR_CANARY_IS_NOT_CANARY_AUTHORIZATION": True,
            "CANARY_OPERATIONAL_PASS_STILL_REQUIRES_9_OF_9": True,
            "CANARY_PASS_DOES_NOT_AUTO_AUTHORIZE_COMPARATIVE": True,
            "receipt_candidate_status": RECEIPT_CANDIDATE_STATUS,
            "repository_authoritative_before_merge": REPOSITORY_AUTHORITATIVE_BEFORE_MERGE,
            "becomes_repository_authoritative_after_chatgpt_pass_merge_and_postmerge_ci": BECOMES_REPOSITORY_AUTHORITATIVE_AFTER_CHATGPT_PASS_MERGE_AND_POSTMERGE_CI,
            "receipt_authority_model": {
                "receipt_candidate_status": RECEIPT_CANDIDATE_STATUS,
                "repository_authoritative_before_merge": REPOSITORY_AUTHORITATIVE_BEFORE_MERGE,
                "becomes_repository_authoritative_after_chatgpt_pass_merge_and_postmerge_ci": BECOMES_REPOSITORY_AUTHORITATIVE_AFTER_CHATGPT_PASS_MERGE_AND_POSTMERGE_CI,
                "required_steps_for_repository_authority": [
                    "1. ChatGPT independent audit = PASS",
                    "2. normal merge into develop",
                    "3. exact-head post-merge CI success",
                ],
            },
            "sanitization_and_privacy_attestation": {
                "screenshots_stored_in_repository": False,
                "api_keys_stored": False,
                "api_key_prefixes_or_suffixes_stored": False,
                "payment_card_details_stored": False,
                "billing_account_ids_stored": False,
                "project_numeric_ids_stored": False,
                "organization_ids_stored": False,
                "email_addresses_stored": False,
                "personal_names_stored": False,
                "payment_transaction_identifiers_stored": False,
                "exact_prepaid_vnd_balance_stored": False,
                "exact_current_dollar_balance_stored": False,
                "env_file_read": False,
                "api_keys_inspected": False,
                "only_sanitized_readiness_facts_persisted": True,
            },
            "bound_authorities": {
                "develop_base_sha": AUTHORITATIVE_BASE_DEVELOP_SHA,
                "provider_readiness_pricing_prep_merge": {
                    "pr_number": PRICING_PREP_PR_NUMBER,
                    "pr_state": PRICING_PREP_PR_STATE,
                    "merge_commit_sha": PRICING_PREP_MERGE_COMMIT_SHA,
                    "parent1": PRICING_PREP_MERGE_PARENT_1,
                    "parent2": PRICING_PREP_MERGE_PARENT_2,
                    "post_merge_ci_run_id": PRICING_PREP_POST_MERGE_CI_RUN_ID,
                    "post_merge_ci_event": PRICING_PREP_POST_MERGE_CI_EVENT,
                    "post_merge_ci_head_sha": PRICING_PREP_POST_MERGE_CI_HEAD_SHA,
                    "post_merge_ci_conclusion": PRICING_PREP_POST_MERGE_CI_CONCLUSION,
                    "post_merge_ci_required_jobs": dict(
                        PRICING_PREP_POST_MERGE_CI_REQUIRED_JOBS
                    ),
                },
                "provider_readiness_pricing_prep": {
                    "artifact_id": _prp_mod.PROVIDER_READINESS_PRICING_PREP_ARTIFACT_ID,
                    "path": PROVIDER_READINESS_PRICING_PREP_REL_PATH,
                    "file_sha256": EXPECTED_PROVIDER_READINESS_PRICING_PREP_FILE_SHA256,
                    "internal_sha256": EXPECTED_PROVIDER_READINESS_PRICING_PREP_INTERNAL_SHA256,
                    "historical_prep_c1_provider_readiness": "NOT_YET_ATTESTED",
                    "historical_prep_c2_provider_readiness": "NOT_YET_ATTESTED",
                    "historical_prep_c3_provider_readiness": "NOT_YET_ATTESTED",
                    "historical_prep_state_immutable": True,
                },
                "public_pricing_snapshot": {
                    "artifact_id": _prp_mod.PUBLIC_PRICING_SNAPSHOT_ARTIFACT_ID,
                    "path": PUBLIC_PRICING_SNAPSHOT_REL_PATH,
                    "file_sha256": EXPECTED_PUBLIC_PRICING_SNAPSHOT_FILE_SHA256,
                    "internal_sha256": EXPECTED_PUBLIC_PRICING_SNAPSHOT_INTERNAL_SHA256,
                },
                "approval_receipt": {
                    "artifact_id": _app_mod.APPROVAL_RECEIPT_ARTIFACT_ID,
                    "path": APPROVAL_RECEIPT_REL_PATH,
                    "file_sha256": EXPECTED_APPROVAL_RECEIPT_FILE_SHA256,
                    "internal_sha256": EXPECTED_APPROVAL_RECEIPT_INTERNAL_SHA256,
                },
                "formal_decision": {
                    "artifact_id": _dec_mod.DECISION_ARTIFACT_ID,
                    "path": DECISION_ARTIFACT_REL_PATH,
                    "file_sha256": EXPECTED_DECISION_ARTIFACT_FILE_SHA256,
                    "internal_sha256": EXPECTED_DECISION_ARTIFACT_INTERNAL_SHA256,
                },
                "canary_manifest": {
                    "artifact_id": _dec_mod.CANARY_MANIFEST_ID,
                    "path": CANARY_MANIFEST_REL_PATH,
                    "file_sha256": EXPECTED_CANARY_MANIFEST_FILE_SHA256,
                    "internal_sha256": EXPECTED_CANARY_MANIFEST_INTERNAL_SHA256,
                },
                "amendment_prep": {
                    "path": PREP_ARTIFACT_REL_PATH,
                    "file_sha256": EXPECTED_PREP_ARTIFACT_FILE_SHA256,
                    "internal_sha256": EXPECTED_PREP_ARTIFACT_INTERNAL_SHA256,
                },
                "primary_results_freeze_receipt": {
                    "path": PRIMARY_RESULTS_FREEZE_RECEIPT_REL_PATH,
                    "file_sha256": EXPECTED_PRIMARY_RESULTS_FREEZE_RECEIPT_FILE_SHA256,
                    "internal_sha256": EXPECTED_PRIMARY_RESULTS_FREEZE_RECEIPT_INTERNAL_SHA256,
                },
                "primary_results_manifest": {
                    "path": PRIMARY_RESULTS_MANIFEST_REL_PATH,
                    "file_sha256": EXPECTED_PRIMARY_RESULTS_MANIFEST_FILE_SHA256,
                    "internal_sha256": EXPECTED_PRIMARY_RESULTS_MANIFEST_INTERNAL_SHA256,
                },
                "failure_diagnostics": {
                    "path": FAILURE_DIAGNOSTIC_REL_PATH,
                    "file_sha256": EXPECTED_FAILURE_DIAGNOSTIC_FILE_SHA256,
                    "internal_sha256": EXPECTED_FAILURE_DIAGNOSTIC_INTERNAL_SHA256,
                },
                "scientific_code_bundle_sha256": EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256,
                "portable_schema_v2_sha256": EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
                "semantic_schema_sha256": EXPECTED_SEMANTIC_SCHEMA_SHA256,
            },
            "primary_authority_firewall": {
                "authoritative_primary_strict_rates": dict(
                    AUTHORITATIVE_PRIMARY_METRIC_RATES
                ),
                "rejected_erroneous_human_report_rates": dict(
                    REJECTED_ERRONEOUS_REPORT_METRIC_RATES
                ),
                "erroneous_report_propagated": False,
                "verified_metrics_cross_checked": primary_metric_auth[
                    "verified_metrics"
                ],
            },
            "frozen_scientific_policy": {
                "fairness_policy": _prp_mod.SELECTED_FAIRNESS_POLICY,
                "timeout_policy": _prp_mod.SELECTED_TIMEOUT_POLICY,
                "timeout_ms": _prp_mod.SELECTED_TIMEOUT_MS,
                "pacing_policy": _prp_mod.SELECTED_PACING_POLICY,
                "inter_call_delay_ms": _prp_mod.SELECTED_INTER_CALL_DELAY_MS,
                "retry_policy": _prp_mod.SELECTED_RETRY_POLICY,
                "automatic_retry": 0,
                "transport_retry": 0,
                "manual_retry": 0,
                "llm_repair": 0,
                "semantic_repair": 0,
                "fallback": False,
                "fixture_policy": _prp_mod.SELECTED_FIXTURE_POLICY,
                "call_budget_policy": _prp_mod.SELECTED_CALL_BUDGET_POLICY,
                "canary_assigned_calls": 9,
                "comparative_assigned_calls": 180,
                "maximum_generation_calls": 189,
                "maximum_candidate_calls": 63,
                "exact_canary_fixtures": list(CANARY_FIXTURE_IDS),
                "exact_candidates": {
                    cid: dict(info) for cid, info in FROZEN_CANDIDATES.items()
                },
            },
            "candidate_readiness_attestations": candidate_attestations,
            "readiness_semantics_and_non_implication_firewall": {
                "provider_readiness_meaning": (
                    "The owner-observed account state has sufficient billing/model/quota evidence "
                    "to proceed to a SEPARATE canary authorization gate."
                ),
                "does_not_mean": {
                    "provider_availability_is_guaranteed": False,
                    "all_9_canary_calls_will_complete": False,
                    "schema_or_core_quality_will_pass": False,
                    "provider_5xx_cannot_occur": False,
                    "provider_high_demand_failures_cannot_occur": False,
                    "comparative_execution_is_authorized": False,
                    "final100_is_authorized": False,
                },
                "READY_FOR_CANARY_IS_NOT_CANARY_AUTHORIZATION": True,
                "CANARY_OPERATIONAL_PASS_STILL_REQUIRES_9_OF_9": True,
                "CANARY_PASS_DOES_NOT_AUTO_AUTHORIZE_COMPARATIVE": True,
                "comparative_60_call_readiness_requires_separate_recheck_before_comparative_authorization": True,
            },
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
            "ENV_FILE_READ": False,
            "API_KEYS_INSPECTED": False,
            "NEXT_GATE": NEXT_GATE_ID,
        }

        effective_state = derive_effective_owner_readiness_state(
            pricing_prep_payload=pricing_prep_payload,
            approval_receipt_payload=approval_payload,
            owner_attestation_payload=payload_without_hash,
        )
        payload_without_hash["effective_owner_readiness_state"] = effective_state

        internal_sha = sha256_bytes(canonical_json_bytes(payload_without_hash))
        full_payload = dict(payload_without_hash)
        full_payload["owner_readiness_attestation_internal_sha256"] = internal_sha
        assert_no_sensitive_account_or_secret_data_in_attestation(
            full_payload, context=OWNER_READINESS_ATTESTATION_ARTIFACT_ID
        )
        return full_payload


def render_owner_provider_readiness_attestation_markdown(
    payload: dict[str, Any],
    *,
    receipt_file_sha256: str,
) -> str:
    """Deterministically render the Markdown documentation from the canonical receipt JSON payload."""
    c1 = payload["candidate_readiness_attestations"]["C1"]
    c1_obs = c1["owner_observed"]
    c2 = payload["candidate_readiness_attestations"]["C2"]
    c2_obs = c2["owner_observed"]
    c3 = payload["candidate_readiness_attestations"]["C3"]
    c3_obs = c3["owner_observed"]
    pol = payload["frozen_scientific_policy"]
    ba = payload["bound_authorities"]
    sem = payload["readiness_semantics_and_non_implication_firewall"]
    san = payload["sanitization_and_privacy_attestation"]

    lines = [
        "# W06 DEV-SELECT Amendment 01 — Owner Provider Readiness Attestation Receipt",
        "",
        "## 1. Purpose & Candidate Authority Status",
        "",
        f"- **Task ID**: `{payload['task_id']}`",
        f"- **Artifact ID**: `{payload['artifact_id']}`",
        f"- **Authoritative Base (`develop`)**: `{payload['authoritative_base_develop_sha']}`",
        f"- **Owner Attestation Evidence Date**: `{payload['owner_observed_readiness_evidence_date']}`",
        f"- **Observation Mode**: `{payload['observation_mode']}`",
        f"- **Attestation Scope**: `{payload['attestation_scope']}`",
        f"- **Receipt Candidate Status**: `{payload['receipt_candidate_status']}`",
        f"- **Repository Authoritative Before Merge**: `{str(payload['repository_authoritative_before_merge']).lower()}`",
        f"- **Becomes Repository Authoritative After ChatGPT PASS + Normal Merge + Post-Merge CI**: `{str(payload['becomes_repository_authoritative_after_chatgpt_pass_merge_and_postmerge_ci']).lower()}`",
        f"- **Receipt File SHA256**: `{receipt_file_sha256}`",
        f"- **Receipt Internal SHA256**: `{payload['owner_readiness_attestation_internal_sha256']}`",
        "",
        "> **Strictly Offline Readiness Attestation Only**: This receipt records sanitized owner-observed provider readiness for the 9-cell readiness canary gate. It does **NOT** authorize or execute any live provider or model generation call (`LIVE_PROVIDER_CALLS_NEW = 0`).",
        "",
        "## 2. Sanitization & Secret / Account-Identifier Firewall",
        "",
        f"- `screenshots_stored_in_repository`: `{str(san['screenshots_stored_in_repository']).lower()}`",
        f"- `api_keys_stored`: `{str(san['api_keys_stored']).lower()}`",
        f"- `api_key_prefixes_or_suffixes_stored`: `{str(san['api_key_prefixes_or_suffixes_stored']).lower()}`",
        f"- `payment_card_details_stored`: `{str(san['payment_card_details_stored']).lower()}`",
        f"- `billing_account_ids_stored`: `{str(san['billing_account_ids_stored']).lower()}`",
        f"- `project_numeric_ids_stored`: `{str(san['project_numeric_ids_stored']).lower()}`",
        f"- `organization_ids_stored`: `{str(san['organization_ids_stored']).lower()}`",
        f"- `email_addresses_stored`: `{str(san['email_addresses_stored']).lower()}`",
        f"- `personal_names_stored`: `{str(san['personal_names_stored']).lower()}`",
        f"- `payment_transaction_identifiers_stored`: `{str(san['payment_transaction_identifiers_stored']).lower()}`",
        f"- `exact_prepaid_vnd_balance_stored`: `{str(san['exact_prepaid_vnd_balance_stored']).lower()}`",
        f"- `exact_current_dollar_balance_stored`: `{str(san['exact_current_dollar_balance_stored']).lower()}`",
        f"- `env_file_read`: `{str(san['env_file_read']).lower()}`",
        f"- `api_keys_inspected`: `{str(san['api_keys_inspected']).lower()}`",
        "",
        "## 3. Sanitized Owner-Observed Provider Readiness by Candidate",
        "",
        "### 3.1 Google / `C1` (`gemini-3.8-flash`)",
        "",
        f"- `candidate_id`: `{c1['candidate_id']}`",
        f"- `provider`: `{c1['provider']}`",
        f"- `exact_model_id`: `{c1['exact_model_id']}`",
        f"- `billing_surface`: `{c1['billing_surface']}`",
        f"- `billing_active`: `{str(c1_obs['billing_active']).lower()}`",
        f"- `paid_tier_active`: `{str(c1_obs['paid_tier_active']).lower()}`",
        f"- `usage_tier`: `{c1_obs['usage_tier']}`",
        f"- `positive_prepaid_credit_available`: `{str(c1_obs['positive_prepaid_credit_available']).lower()}`",
        f"- `exact_model_visible_in_rate_limit_dashboard`: `{str(c1_obs['exact_model_visible_in_rate_limit_dashboard']).lower()}`",
        f"- `standard_rpm_limit`: `{c1_obs['standard_rpm_limit']}`",
        f"- `standard_input_tpm_limit`: `{c1_obs['standard_input_tpm_limit']}`",
        f"- `standard_rpd_limit`: `{c1_obs['standard_rpd_limit']}`",
        f"- `required_max_candidate_calls_under_frozen_amendment`: `{c1_obs['required_max_candidate_calls_under_frozen_amendment']}`",
        f"- `canary_assigned_calls`: `{c1_obs['canary_assigned_calls']}`",
        f"- `rpm_sufficient_for_frozen_canary`: `{str(c1_obs['rpm_sufficient_for_frozen_canary']).lower()}`",
        f"- `tpm_sufficient_for_frozen_canary`: `{str(c1_obs['tpm_sufficient_for_frozen_canary']).lower()}`",
        f"- `rpd_sufficient_for_frozen_canary`: `{str(c1_obs['rpd_sufficient_for_frozen_canary']).lower()}`",
        f"- `provider_readiness`: `{c1['provider_readiness']}`",
        "",
        "### 3.2 OpenAI / `C2` (`gpt-6.1-sol`)",
        "",
        f"- `candidate_id`: `{c2['candidate_id']}`",
        f"- `provider`: `{c2['provider']}`",
        f"- `exact_model_id`: `{c2['exact_model_id']}`",
        f"- `billing_surface`: `{c2['billing_surface']}`",
        f"- `billing_active`: `{str(c2_obs['billing_active']).lower()}`",
        f"- `positive_api_credit_available`: `{str(c2_obs['positive_api_credit_available']).lower()}`",
        f"- `api_credit_sufficient_for_canary_planning_envelope`: `{str(c2_obs['api_credit_sufficient_for_canary_planning_envelope']).lower()}`",
        f"- `usage_tier`: `{c2_obs['usage_tier']}`",
        f"- `organization_spend_limit_blocking`: `{str(c2_obs['organization_spend_limit_blocking']).lower()}`",
        "- `exact_model_access_supported_by`:",
        f"  - `{c2_obs['exact_model_access_supported_by'][0]}`",
        f"  - `{c2_obs['exact_model_access_supported_by'][1]}`",
        f"- `standard_rpm_limit`: `{c2_obs['standard_rpm_limit']}`",
        f"- `standard_tpm_limit`: `{c2_obs['standard_tpm_limit']}`",
        f"- `required_max_candidate_calls_under_frozen_amendment`: `{c2_obs['required_max_candidate_calls_under_frozen_amendment']}`",
        f"- `canary_assigned_calls`: `{c2_obs['canary_assigned_calls']}`",
        f"- `rpm_sufficient_for_frozen_canary`: `{str(c2_obs['rpm_sufficient_for_frozen_canary']).lower()}`",
        f"- `tpm_sufficient_for_frozen_canary`: `{str(c2_obs['tpm_sufficient_for_frozen_canary']).lower()}`",
        f"- `provider_readiness`: `{c2['provider_readiness']}`",
        "",
        "### 3.3 Anthropic / `C3` (`claude-sonnet-5-5`)",
        "",
        f"- `candidate_id`: `{c3['candidate_id']}`",
        f"- `provider`: `{c3['provider']}`",
        f"- `exact_model_id`: `{c3['exact_model_id']}`",
        f"- `billing_surface`: `{c3['billing_surface']}`",
        f"- `billing_active`: `{str(c3_obs['billing_active']).lower()}`",
        f"- `positive_credit_available`: `{str(c3_obs['positive_credit_available']).lower()}`",
        f"- `exact_model_visible_in_rate_limit_dashboard`: `{str(c3_obs['exact_model_visible_in_rate_limit_dashboard']).lower()}`",
        f"- `account_tier`: `{c3_obs['account_tier']}`",
        f"- `input_token_limit`: `{c3_obs['input_token_limit']}`",
        f"- `output_token_limit`: `{c3_obs['output_token_limit']}`",
        f"- `request_limit`: `{c3_obs['request_limit']}`",
        f"- `canary_assigned_calls`: `{c3_obs['canary_assigned_calls']}`",
        f"- `configured_max_output_tokens_per_call`: `{c3_obs['configured_max_output_tokens_per_call']}`",
        f"- `configured_three_call_max_output_reference`: `{c3_obs['configured_three_call_max_output_reference']}` (`{c3_obs['three_call_max_output_reference_comparison']}`)",
        f"- `input_capacity_sufficient_for_frozen_canary_planning_envelope`: `{str(c3_obs['input_capacity_sufficient_for_frozen_canary_planning_envelope']).lower()}`",
        f"- `output_capacity_sufficient_for_frozen_canary_reference`: `{str(c3_obs['output_capacity_sufficient_for_frozen_canary_reference']).lower()}`",
        f"- `request_capacity_sufficient_for_frozen_canary`: `{str(c3_obs['request_capacity_sufficient_for_frozen_canary']).lower()}`",
        f"- `provider_readiness`: `{c3['provider_readiness']}`",
        f"- `generalized_as_readiness_proof_for_future_60_call_comparative_run`: `{str(c3['generalized_as_readiness_proof_for_future_60_call_comparative_run']).lower()}`",
        f"- `comparative_readiness_must_be_rechecked_before_comparative_authorization`: `{str(c3['comparative_readiness_must_be_rechecked_before_comparative_authorization']).lower()}`",
        "",
        "## 4. Effective Readiness State & Non-Authorization Semantics",
        "",
        f"- `OWNER_PROVIDER_READINESS_ATTESTED`: `{str(payload['OWNER_PROVIDER_READINESS_ATTESTED']).lower()}`",
        f"- `C1_PROVIDER_READINESS`: `{payload['C1_PROVIDER_READINESS']}`",
        f"- `C2_PROVIDER_READINESS`: `{payload['C2_PROVIDER_READINESS']}`",
        f"- `C3_PROVIDER_READINESS`: `{payload['C3_PROVIDER_READINESS']}`",
        f"- `ALL_CANARY_PROVIDER_READINESS`: `{payload['ALL_CANARY_PROVIDER_READINESS']}`",
        f"- `READY_FOR_CANARY_IS_NOT_CANARY_AUTHORIZATION`: `{str(sem['READY_FOR_CANARY_IS_NOT_CANARY_AUTHORIZATION']).lower()}`",
        f"- `CANARY_OPERATIONAL_PASS_STILL_REQUIRES_9_OF_9`: `{str(sem['CANARY_OPERATIONAL_PASS_STILL_REQUIRES_9_OF_9']).lower()}`",
        f"- `CANARY_PASS_DOES_NOT_AUTO_AUTHORIZE_COMPARATIVE`: `{str(sem['CANARY_PASS_DOES_NOT_AUTO_AUTHORIZE_COMPARATIVE']).lower()}`",
        f"- `AMENDED_CANARY_LIVE_AUTHORIZED`: `{str(payload['AMENDED_CANARY_LIVE_AUTHORIZED']).lower()}`",
        f"- `AMENDED_COMPARATIVE_LIVE_AUTHORIZED`: `{str(payload['AMENDED_COMPARATIVE_LIVE_AUTHORIZED']).lower()}`",
        f"- `AMENDED_LIVE_AUTHORIZED`: `{str(payload['AMENDED_LIVE_AUTHORIZED']).lower()}`",
        f"- `AMENDED_LIVE_EXECUTED`: `{str(payload['AMENDED_LIVE_EXECUTED']).lower()}`",
        f"- `CANARY_EXECUTED`: `{str(payload['CANARY_EXECUTED']).lower()}`",
        f"- `COMPARATIVE_EXECUTED`: `{str(payload['COMPARATIVE_EXECUTED']).lower()}`",
        f"- `LIVE_PROVIDER_CALLS_NEW`: `{payload['LIVE_PROVIDER_CALLS_NEW']}`",
        "",
        "## 5. Bound Upstream Authorities & Frozen Scientific Policy",
        "",
        f"- `develop` base SHA: `{ba['develop_base_sha']}`",
        f"- Provider Readiness / Pricing PREP (`{ba['provider_readiness_pricing_prep']['path']}`): file `{ba['provider_readiness_pricing_prep']['file_sha256']}`, internal `{ba['provider_readiness_pricing_prep']['internal_sha256']}`",
        f"- Public Pricing Snapshot (`{ba['public_pricing_snapshot']['path']}`): file `{ba['public_pricing_snapshot']['file_sha256']}`, internal `{ba['public_pricing_snapshot']['internal_sha256']}`",
        f"- Approval Receipt (`{ba['approval_receipt']['path']}`): file `{ba['approval_receipt']['file_sha256']}`, internal `{ba['approval_receipt']['internal_sha256']}`",
        f"- Formal Decision (`{ba['formal_decision']['path']}`): file `{ba['formal_decision']['file_sha256']}`, internal `{ba['formal_decision']['internal_sha256']}`",
        f"- Canary Manifest (`{ba['canary_manifest']['path']}`): file `{ba['canary_manifest']['file_sha256']}`, internal `{ba['canary_manifest']['internal_sha256']}`",
        f"- Primary Results-Freeze Receipt (`{ba['primary_results_freeze_receipt']['path']}`): file `{ba['primary_results_freeze_receipt']['file_sha256']}`, internal `{ba['primary_results_freeze_receipt']['internal_sha256']}`",
        f"- Scientific Code Bundle SHA256: `{ba['scientific_code_bundle_sha256']}`",
        f"- Primary Strict Metric Rates Preserved: `C1 = {payload['primary_authority_firewall']['authoritative_primary_strict_rates']['C1']}`, `C2 = {payload['primary_authority_firewall']['authoritative_primary_strict_rates']['C2']}`, `C3 = {payload['primary_authority_firewall']['authoritative_primary_strict_rates']['C3']}` (erroneous report `0/60, 43/60, 0/60` rejected)",
        f"- Fairness / Environment Policy: `{pol['fairness_policy']}`, `timeout_ms = {pol['timeout_ms']}`, `inter_call_delay_ms = {pol['inter_call_delay_ms']}`, zero retries/repairs/fallbacks, `9 + 180 = 189` calls (`63` max per candidate)",
        f"- Next Gate: `{payload['NEXT_GATE']}`",
        "",
    ]
    return "\n".join(lines)


# ==============================================================================
# 5. WRITE & STATELESS VERIFY FUNCTIONS
# ==============================================================================


def write_w06_owner_provider_readiness_attestation(
    *,
    receipt_path: Path = REPO_ROOT / OWNER_READINESS_ATTESTATION_REL_PATH,
    doc_path: Path = REPO_ROOT / OWNER_READINESS_ATTESTATION_DOC_REL_PATH,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    _assert_not_inside_raw_evidence(receipt_path, repo_root)
    _assert_not_inside_raw_evidence(doc_path, repo_root)
    _assert_not_immutable_upstream_artifact(receipt_path, repo_root)
    _assert_not_immutable_upstream_artifact(doc_path, repo_root)

    payload = build_w06_owner_provider_readiness_attestation_payload(
        repo_root=repo_root
    )
    serialized = (
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    )
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_bytes(serialized.encode("utf-8"))
    file_sha = _read_lf_sha256(receipt_path)

    md_content = render_owner_provider_readiness_attestation_markdown(
        payload, receipt_file_sha256=file_sha
    )
    assert_no_sensitive_account_or_secret_data_in_attestation(
        {"markdown": md_content}, context="OWNER_READINESS_ATTESTATION_MARKDOWN"
    )
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.write_bytes(normalize_lf_bytes(md_content.encode("utf-8")))
    doc_sha = _read_lf_sha256(doc_path)

    return {
        "owner_readiness_attestation_path": receipt_path.relative_to(
            repo_root
        ).as_posix()
        if receipt_path.is_relative_to(repo_root)
        else str(receipt_path),
        "owner_readiness_attestation_file_sha256": file_sha,
        "owner_readiness_attestation_internal_sha256": payload[
            "owner_readiness_attestation_internal_sha256"
        ],
        "owner_readiness_attestation_doc_path": doc_path.relative_to(
            repo_root
        ).as_posix()
        if doc_path.is_relative_to(repo_root)
        else str(doc_path),
        "owner_readiness_attestation_doc_sha256": doc_sha,
    }


def verify_w06_owner_provider_readiness_attestation(
    *,
    receipt_path: Path = REPO_ROOT / OWNER_READINESS_ATTESTATION_REL_PATH,
    doc_path: Path = REPO_ROOT / OWNER_READINESS_ATTESTATION_DOC_REL_PATH,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    with NetworkKillSwitchGuard():
        _assert_not_inside_raw_evidence(receipt_path, repo_root)
        _assert_not_inside_raw_evidence(doc_path, repo_root)
        _assert_not_immutable_upstream_artifact(receipt_path, repo_root)
        _assert_not_immutable_upstream_artifact(doc_path, repo_root)
        assert_no_screenshots_in_evaluation_or_research_dirs(repo_root)

        if not receipt_path.is_file():
            raise PlanBeforeLiveProtocolError(
                f"MISSING_OWNER_READINESS_ATTESTATION_ARTIFACT: {receipt_path}"
            )
        if not doc_path.is_file():
            raise PlanBeforeLiveProtocolError(
                f"MISSING_OWNER_READINESS_ATTESTATION_DOC: {doc_path}"
            )

        raw_bytes = normalize_lf_bytes(receipt_path.read_bytes())
        disk_payload = json.loads(raw_bytes.decode("utf-8"))
        if not isinstance(disk_payload, dict):
            raise PlanBeforeLiveProtocolError(
                "OWNER_READINESS_ATTESTATION_MUST_BE_JSON_OBJECT"
            )

        assert_no_sensitive_account_or_secret_data_in_attestation(
            disk_payload, context="DISK_OWNER_READINESS_ATTESTATION_ARTIFACT"
        )

        expected_formatted_bytes = (
            json.dumps(
                disk_payload, indent=2, sort_keys=True, ensure_ascii=False
            )
            + "\n"
        ).encode("utf-8")
        if raw_bytes != expected_formatted_bytes:
            raise PlanBeforeLiveProtocolError(
                "OWNER_READINESS_ATTESTATION_NOT_DETERMINISTIC_FORMATTED_JSON"
            )

        recorded_internal = disk_payload.get(
            "owner_readiness_attestation_internal_sha256"
        )
        disk_without_internal = {
            k: v
            for k, v in disk_payload.items()
            if k != "owner_readiness_attestation_internal_sha256"
        }
        recomputed_internal = sha256_bytes(
            canonical_json_bytes(disk_without_internal)
        )
        if recorded_internal != recomputed_internal:
            raise PlanBeforeLiveProtocolError(
                f"OWNER_READINESS_ATTESTATION_INTERNAL_SHA256_TAMPERED: recorded {recorded_internal}, recomputed {recomputed_internal}"
            )

        expected_payload = build_w06_owner_provider_readiness_attestation_payload(
            repo_root=repo_root
        )
        if disk_payload != expected_payload:
            raise PlanBeforeLiveProtocolError(
                "OWNER_READINESS_ATTESTATION_CONTENT_DRIFT_FROM_DETERMINISTIC_REBUILD"
            )

        file_sha = sha256_bytes(raw_bytes)
        if (
            EXPECTED_OWNER_READINESS_ATTESTATION_FILE_SHA256
            != "0000000000000000000000000000000000000000000000000000000000000000"
            and file_sha != EXPECTED_OWNER_READINESS_ATTESTATION_FILE_SHA256
        ):
            raise PlanBeforeLiveProtocolError(
                f"OWNER_READINESS_ATTESTATION_FILE_SHA256_MISMATCH: expected {EXPECTED_OWNER_READINESS_ATTESTATION_FILE_SHA256}, got {file_sha}"
            )
        if (
            EXPECTED_OWNER_READINESS_ATTESTATION_INTERNAL_SHA256
            != "0000000000000000000000000000000000000000000000000000000000000000"
            and recorded_internal
            != EXPECTED_OWNER_READINESS_ATTESTATION_INTERNAL_SHA256
        ):
            raise PlanBeforeLiveProtocolError(
                f"OWNER_READINESS_ATTESTATION_INTERNAL_SHA256_MISMATCH: expected {EXPECTED_OWNER_READINESS_ATTESTATION_INTERNAL_SHA256}, got {recorded_internal}"
            )

        disk_md = normalize_lf_bytes(doc_path.read_bytes()).decode("utf-8")
        assert_no_sensitive_account_or_secret_data_in_attestation(
            {"markdown": disk_md}, context="DISK_OWNER_READINESS_ATTESTATION_MARKDOWN"
        )
        expected_md = render_owner_provider_readiness_attestation_markdown(
            disk_payload, receipt_file_sha256=file_sha
        )
        if disk_md != expected_md:
            raise PlanBeforeLiveProtocolError(
                "OWNER_READINESS_ATTESTATION_MARKDOWN_DRIFT_FROM_CANONICAL_JSON"
            )

        pricing_prep_payload = _load_json_dict(
            repo_root / PROVIDER_READINESS_PRICING_PREP_REL_PATH
        )
        approval_payload = _load_json_dict(repo_root / APPROVAL_RECEIPT_REL_PATH)
        effective_state = derive_effective_owner_readiness_state(
            pricing_prep_payload=pricing_prep_payload,
            approval_receipt_payload=approval_payload,
            owner_attestation_payload=disk_payload,
        )

        return {
            "verified": True,
            "status": "PASS",
            "task_id": TASK_ID,
            "artifact_id": OWNER_READINESS_ATTESTATION_ARTIFACT_ID,
            "authoritative_base_develop_sha": AUTHORITATIVE_BASE_DEVELOP_SHA,
            "owner_observed_readiness_evidence_date": disk_payload[
                "owner_observed_readiness_evidence_date"
            ],
            "owner_provider_readiness_attested": disk_payload[
                "OWNER_PROVIDER_READINESS_ATTESTED"
            ],
            "c1_provider_readiness": disk_payload["C1_PROVIDER_READINESS"],
            "c2_provider_readiness": disk_payload["C2_PROVIDER_READINESS"],
            "c3_provider_readiness": disk_payload["C3_PROVIDER_READINESS"],
            "all_canary_provider_readiness": disk_payload[
                "ALL_CANARY_PROVIDER_READINESS"
            ],
            "receipt_candidate_status": disk_payload["receipt_candidate_status"],
            "repository_authoritative_before_merge": disk_payload[
                "repository_authoritative_before_merge"
            ],
            "effective_amendment_status": effective_state[
                "effective_amendment_status"
            ],
            "owner_readiness_attestation_file_sha256": file_sha,
            "owner_readiness_attestation_internal_sha256": recorded_internal,
            "owner_readiness_attestation_doc_sha256": _read_lf_sha256(doc_path),
            "ready_for_canary_is_not_canary_authorization": disk_payload[
                "READY_FOR_CANARY_IS_NOT_CANARY_AUTHORIZATION"
            ],
            "canary_operational_pass_still_requires_9_of_9": disk_payload[
                "CANARY_OPERATIONAL_PASS_STILL_REQUIRES_9_OF_9"
            ],
            "canary_pass_does_not_auto_authorize_comparative": disk_payload[
                "CANARY_PASS_DOES_NOT_AUTO_AUTHORIZE_COMPARATIVE"
            ],
            "amended_canary_live_authorized": disk_payload[
                "AMENDED_CANARY_LIVE_AUTHORIZED"
            ],
            "amended_comparative_live_authorized": disk_payload[
                "AMENDED_COMPARATIVE_LIVE_AUTHORIZED"
            ],
            "amended_live_authorized": disk_payload["AMENDED_LIVE_AUTHORIZED"],
            "amended_live_executed": disk_payload["AMENDED_LIVE_EXECUTED"],
            "canary_executed": disk_payload["CANARY_EXECUTED"],
            "comparative_executed": disk_payload["COMPARATIVE_EXECUTED"],
            "live_provider_calls_new": disk_payload["LIVE_PROVIDER_CALLS_NEW"],
            "model_winner_selected": disk_payload["MODEL_WINNER_SELECTED"],
            "selected_model_id": disk_payload["SELECTED_MODEL_ID"],
            "stochasticity_execution_started": disk_payload[
                "STOCHASTICITY_EXECUTION_STARTED"
            ],
            "final100_used": disk_payload["FINAL100_USED"],
            "final100_status": disk_payload["FINAL100_STATUS"],
            "primary_experiment_mutated": disk_payload["PRIMARY_EXPERIMENT_MUTATED"],
            "primary_results_replaced": disk_payload["PRIMARY_RESULTS_REPLACED"],
            "primary_denominators_changed": disk_payload[
                "PRIMARY_DENOMINATORS_CHANGED"
            ],
            "next_gate": disk_payload["NEXT_GATE"],
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Strictly offline W06 DEV-SELECT Amendment 01 Owner Provider Readiness "
            "Attestation Receipt generator and verifier."
        )
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify the existing owner readiness attestation receipt and Markdown without modifying any files.",
    )
    group.add_argument(
        "--write",
        action="store_true",
        help="Deterministically write the owner readiness attestation receipt and Markdown documentation.",
    )
    args = parser.parse_args(argv)

    if args.write:
        written = write_w06_owner_provider_readiness_attestation(repo_root=REPO_ROOT)
        print(json.dumps(written, indent=2, sort_keys=True))
    summary = verify_w06_owner_provider_readiness_attestation(repo_root=REPO_ROOT)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
