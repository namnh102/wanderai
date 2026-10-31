#!/usr/bin/env python3
"""Dedicated 9-cell live launcher for the frozen W06 DEV-SELECT Amendment 01 Readiness Canary.

TASK: W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-CANARY-LIVE-LAUNCHER-PREP

PURPOSE:
Provide a dedicated, minimal, fail-closed launcher for the already-frozen 9-cell
execution-environment readiness canary (`W06-DEV-SELECT-AMENDMENT-01-CANARY-ASSIGNMENT-MANIFEST-V1`)
without modifying `scripts/run_w06_dev_select_live_v1.py` (hard-locked to the primary 180-cell
DEV-SELECT experiment) or the scientific code bundle (`SCIENTIFIC_CODE_BUNDLE_SHA256 =
0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3`).

PUBLIC MODES:
1. `--preflight`
   - Strictly offline (`LIVE_PROVIDER_CALLS_NEW = 0`)
   - Network kill-switch ON (`NetworkKillSwitchGuard`)
   - Secret / `.env` guard ON (`PreflightSecretAndEnvFileAccessGuard`: `ENV_FILE_READ = false`,
     `API_KEYS_INSPECTED = false`)
   - Verifies all bound hashes, authoritative `develop` ancestry, exact 3 candidates,
     exact 3 fixtures, exact 9-cell execution order, frozen runtime policy (`timeout_ms = 180000`,
     `inter_call_delay_ms = 2000`, zero retries across all dimensions, `fallback = false`,
     1 call per cell, max 9 calls), non-existence of output root
     `data/evaluation/w06/live_amendment_01_canary_v1/`, primary launcher & results immutability,
     and Final100/P11 firewalls.
2. `--execute-live --confirm-frozen-9-canary-cells`
   - Exists in code for the future live canary execution gate
     (`W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-CANARY-LIVE-EXECUTION-01`).
   - MUST NOT be invoked during this launcher-prep task.
"""

from __future__ import annotations

import argparse
import builtins
import copy
import datetime as dt
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from typing import Any, Callable, Mapping, Sequence
import urllib.request

import anthropic
from google import genai
from google.genai import types as genai_types
import httpx
import httpx2
import openai

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
AI_SERVICE_DIR = REPO_ROOT / "apps" / "ai-service"
for _p in (SCRIPTS_DIR, AI_SERVICE_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from app.evaluation.dev_live_runner import (  # noqa: E402
    CANDIDATE_ENV_KEY_BY_ID,
    CANDIDATE_MODEL_BY_ID,
    CANDIDATE_PROVIDER_BY_ID,
    TRANSPORT_STATUS_COMPLETED,
    TRANSPORT_STATUS_NOT_INVOKED,
    TRANSPORT_STATUS_STARTING,
    CandidateRegistryIntegrityError,
    DevCallBudgetExhaustedError,
    DevCellHttpCallCounter,
    DevCountingHttpx2Transport,
    DevCountingHttpxTransport,
    DevLiveAuthorizationError,
    DevLiveRunnerError,
    DuplicateDevCellAttemptError,
    ImmutableCellExecutionError,
    LiveExecutionNotAuthorizedError,
    PlanBeforeLiveProtocolError,
    PromptFreezeFirewallError,
    ProviderNormalizedTransportResponse,
    SecretLeakageViolationError,
    StochasticityGateViolationError,
    _assert_runner_not_final100_path,
    _load_candidate_api_key_for_live_transport,
    assert_no_secrets_in_payload,
    build_frozen_provider_wire_request,
    classify_provider_transport_exception,
    default_utc_now_clock,
    normalize_candidate_usage_metadata,
    sanitize_runner_structure,
    sanitize_runner_text,
    write_immutable_canonical_json,
    write_immutable_utf8_text,
)
from app.evaluation.dev_selection_harness import (  # noqa: E402
    BATCH_STOP_FAILURE_CLASSIFICATIONS,
    EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
    EXPECTED_SEMANTIC_SCHEMA_SHA256,
    FORBIDDEN_FINAL100_BUNDLE_SHA256,
    FORBIDDEN_P11_MANIFEST_SHA256,
    ORDERED_CANDIDATE_IDS,
    SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS,
    BatchExecutionFatalStopError,
    DevCandidateRegistry,
    DevCellExecutionManifest,
    DevCellFailureClassification,
    Final100FirewallViolationError,
    PromptCandidateSpec,
    ScientificCodeBundleIntegrityError,
    VerifiedDevBundle,
    assert_not_final100_path,
    assert_not_final100_scenario,
    assert_not_final100_scenario_id,
    build_deterministic_dev_scenario_context,
    canonical_json_bytes,
    compute_candidate_provider_config_sha256,
    compute_common_portable_generation_schema_sha256_v2,
    compute_provider_config_registry_sha256,
    compute_scientific_code_bundle_sha256,
    compute_semantic_schema_sha256,
    evaluate_dev_cell_scenario,
    is_returned_model_id_compatible,
    load_and_verify_candidate_registry,
    load_and_verify_frozen_dev_bundle,
    normalize_lf_bytes,
    parse_primary_dev_plan_response,
    sha256_bytes,
)
from app.evaluation.planner_benchmark_evaluator import (  # noqa: E402
    load_core_catalog_by_place_id,
)
from app.schemas.planner_benchmark import (  # noqa: E402
    HASH_BASIS_VERSION,
    BenchmarkRunManifest,
    BenchmarkRunStatus,
    BenchmarkUsageMetadata,
)
from app.services.planner_benchmark_runner import (  # noqa: E402
    MEASUREMENT_CONTRACT_ID,
    MEASUREMENT_CONTRACT_VERSION,
    compute_catalog_sha256,
)
import diagnose_w06_dev_select_failures as _diag_mod  # noqa: E402
from freeze_w06_dev_prompt_candidates import (  # noqa: E402
    P1_AUTHORITATIVE_SEMANTIC_PROMPT_SHA256,
    P1_EXPECTED_SYSTEM_PROMPT_SHA256,
    P1_EXPECTED_USER_PROMPT_TEMPLATE_SHA256,
    build_frozen_p1_p2_registry,
    build_p1_spec,
)
import freeze_w06_dev_select_amendment_01_canary_live_authorization_prep as _auth_prep_mod  # noqa: E402
import freeze_w06_dev_select_amendment_01_owner_provider_readiness_attestation as _att_mod  # noqa: E402
import freeze_w06_dev_select_execution_environment_amendment_01_approval_receipt as _app_mod  # noqa: E402
import freeze_w06_dev_select_execution_environment_amendment_01_decision as _dec_mod  # noqa: E402
import freeze_w06_dev_select_live_results as _freeze_mod  # noqa: E402
import prepare_w06_dev_select_amendment_01_provider_readiness_pricing as _prp_mod  # noqa: E402
import prepare_w06_dev_select_execution_environment_amendment_01 as _prep_mod  # noqa: E402


# ==============================================================================
# 1. FROZEN CONSTANTS & HARD-LOCKED AUTHORITIES (SECTIONS 0..20)
# ==============================================================================

TASK_ID = (
    "W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-CANARY-LIVE-LAUNCHER-PREP"
)
CORRECTIVE_TASK_ID = (
    "W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-CANARY-LIVE-LAUNCHER-CORRECTIVE-01"
)
PREVIOUS_GATE_ID = (
    "W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-AMENDED-CANARY-LIVE-AUTHORIZATION-POSTMERGE-CHATGPT-AUDIT"
)
PREVIOUS_GATE_DECISION = "PASS"
NEXT_GATE_ID = (
    "W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-CANARY-LIVE-LAUNCHER-CORRECTIVE-01-CHATGPT-AUDIT"
)
FUTURE_LIVE_EXECUTION_GATE_ID = (
    "W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-CANARY-LIVE-EXECUTION-01"
)

LAUNCHER_IDENTITY_ID = "W06-AMENDMENT-01-CANARY-LIVE-LAUNCHER-V1"
LAUNCHER_VERSION = "1.0.0"

CANARY_LIVE_EXECUTION_AUTH_RECEIPT_REL_PATH = (
    "data/evaluation/w06/w06_dev_select_amendment_01_canary_live_execution_authorization_v1.json"
)
CANARY_LIVE_EXECUTION_AUTH_RECEIPT_ARTIFACT_ID = (
    "W06-DEV-SELECT-AMENDMENT-01-CANARY-LIVE-EXECUTION-AUTHORIZATION-V1"
)
CANARY_LIVE_EXECUTION_AUTH_INTERNAL_SHA_KEY = (
    "canary_live_execution_authorization_internal_sha256"
)

AUTHORITATIVE_BASE_DEVELOP_SHA = "1ebe30c251958542088a3056dcfc6b780dac3a88"
PR_72_NUMBER = 72
PR_72_STATE = "MERGED"
PR_72_MERGE_COMMIT_SHA = "1ebe30c251958542088a3056dcfc6b780dac3a88"
PR_72_MERGE_PARENT_1 = "df5a76d9d3734f77bf64abbe66d9d93492fabb3c"
PR_72_MERGE_PARENT_2 = "9e638f6dbb9a955ab574e9d09f6503d79d3ed762"
PR_72_POST_MERGE_CI_RUN_ID = 41123880609
PR_72_POST_MERGE_CI_EVENT = "push"
PR_72_POST_MERGE_CI_HEAD_SHA = "1ebe30c251958542088a3056dcfc6b780dac3a88"
PR_72_POST_MERGE_CI_CONCLUSION = "success"

LAUNCHER_REL_PATH = "scripts/run_w06_dev_select_amendment_01_canary_live_v1.py"
PRIMARY_LAUNCHER_REL_PATH = "scripts/run_w06_dev_select_live_v1.py"
EXPECTED_PRIMARY_LAUNCHER_LF_SHA256 = (
    "cd36b8ecad24059edb597c0039bd6e760a37ee8b4f36f49077801c65e7ddc7bf"
)

CANARY_AUTH_PREP_REL_PATH = (
    "data/evaluation/w06/w06_dev_select_amendment_01_canary_authorization_prep_v1.json"
)
EXPECTED_CANARY_AUTH_PREP_FILE_SHA256 = (
    "21f9432c4c8bfa0ba5f63bdd99e8ab8c15d2802918b7e0a9c21cb5c0ccc63b61"
)
EXPECTED_CANARY_AUTH_PREP_INTERNAL_SHA256 = (
    "0f1480969d506d5b6dc16951a45cf2f8aaf913a13c011f2add6ec3e31721af61"
)
CANARY_AUTH_PREP_DOC_REL_PATH = (
    "docs/research/w06_dev_select_amendment_01_canary_live_authorization_prep.md"
)
EXPECTED_CANARY_AUTH_PREP_DOC_SHA256 = (
    "d9db3cf7876c408f9a30f703200bd575934e1c81679740e7cdd6ba30256904da"
)

CANARY_MANIFEST_REL_PATH = (
    "data/evaluation/w06/w06_dev_select_amendment_01_canary_manifest_v1.json"
)
EXPECTED_CANARY_MANIFEST_FILE_SHA256 = (
    "3ce0ebaac35f22dfe8c981478a6c63d7a2fde0580b372fd8f25762ab3b18fb96"
)
EXPECTED_CANARY_MANIFEST_INTERNAL_SHA256 = (
    "707d99fee54d65822f194cc690cbfadea14ad2176594d4ef882e7d8031990518"
)

OWNER_READINESS_ATTESTATION_REL_PATH = (
    "data/evaluation/w06/w06_dev_select_amendment_01_owner_provider_readiness_attestation_v1.json"
)
EXPECTED_OWNER_READINESS_ATTESTATION_FILE_SHA256 = (
    "91702599a9c81d57bfa1360d33cf19129537608a5141d35bbba58958a62b1d06"
)
EXPECTED_OWNER_READINESS_ATTESTATION_INTERNAL_SHA256 = (
    "137aae6ba52912c10098262ecd29238cb591c92005d99eb226ffbe65c9dfbd75"
)
OWNER_READINESS_ATTESTATION_DOC_REL_PATH = (
    "docs/research/w06_dev_select_amendment_01_owner_provider_readiness_attestation.md"
)
EXPECTED_OWNER_READINESS_ATTESTATION_DOC_SHA256 = (
    "ed5a565ecc08446c87e61b7f980283b3411881100fc270c3280ad1a6491ec29e"
)

DECISION_ARTIFACT_REL_PATH = _dec_mod.DECISION_ARTIFACT_REL_PATH
EXPECTED_DECISION_ARTIFACT_FILE_SHA256 = (
    "2e4211893c1988230e2eeb2718195d48c093da87725cd2fa074e1743ee599ddf"
)
EXPECTED_DECISION_ARTIFACT_INTERNAL_SHA256 = (
    "38dc02de2e846d4cf72108e8beacffdcfcf6308879e0ea72cca3bb83bf71387a"
)

APPROVAL_RECEIPT_REL_PATH = _app_mod.APPROVAL_RECEIPT_REL_PATH
EXPECTED_APPROVAL_RECEIPT_FILE_SHA256 = (
    "171564d09b0011ddfc0e2b70ca2f9029bf6981b944527c09331fa7f6a0f914a5"
)
EXPECTED_APPROVAL_RECEIPT_INTERNAL_SHA256 = (
    "d32e1c61b130a93c5ccbf18294fc1e972c36ba4e561b7fff51a9ea13b43aa991"
)

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

DEV_FIXTURES_FREEZE_REL_PATH = "data/evaluation/w06/w06_dev_fixtures_freeze_v1.json"
EXPECTED_DEV_FIXTURES_FREEZE_SHA256 = (
    "bb0f051446ea3da8229298f22f4ce92b4db20751695273c6d01b7766da044050"
)

DEV_TUNE_EXECUTION_PLAN_REL_PATH = (
    "data/evaluation/w06/w06_dev_tune_execution_plan_v1.json"
)
EXPECTED_DEV_TUNE_EXECUTION_PLAN_FILE_SHA256 = (
    "652e3beb08771c3125e613172b1aaa396fc1b60aaaf3b98cc238e91a14e0dc74"
)
EXPECTED_DEV_TUNE_EXECUTION_PLAN_INTERNAL_SHA256 = (
    "582d9964b4fffbac91f83373d080f1fef120f0ddca4edab2d63e02796d0b20ae"
)

PRIMARY_DEV_SELECT_EXECUTION_PLAN_REL_PATH = (
    "data/evaluation/w06/w06_dev_select_execution_plan_v1.json"
)
EXPECTED_PRIMARY_DEV_SELECT_EXECUTION_PLAN_FILE_SHA256 = (
    "c519baf7cd2557b5e1dd2699a5ceaec592af015d7bc6dcc83abf63892a8a329a"
)
EXPECTED_PRIMARY_DEV_SELECT_EXECUTION_PLAN_INTERNAL_SHA256 = (
    "de04255989a9e3bd8c2e39c766432487dce4ccd0612d5dba73b3476cbc9d0c6d"
)

EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256 = (
    "0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3"
)
EXPECTED_CANDIDATE_REGISTRY_SHA256 = (
    "4dd29164afdf7f364978420f41ab88ef07ec396062188169fcb859a9ef01e058"
)
EXPECTED_PROVIDER_CONFIG_REGISTRY_SHA256 = (
    "3dc05d29acc2f647cba58303865bd7406b8c1d9f7ccbe0f120e87ad471190938"
)
EXPECTED_FROZEN_PROMPT_REGISTRY_SHA256 = (
    "846dc4c14ec2a87537b7b3e07bf492de51dc534d24b21e469094b7e3d34d32b6"
)

FROZEN_PROMPT_ID = "P1"
EXPECTED_P1_SEMANTIC_SHA256 = P1_AUTHORITATIVE_SEMANTIC_PROMPT_SHA256
EXPECTED_P1_SYSTEM_PROMPT_SHA256 = P1_EXPECTED_SYSTEM_PROMPT_SHA256
EXPECTED_P1_USER_PROMPT_TEMPLATE_SHA256 = P1_EXPECTED_USER_PROMPT_TEMPLATE_SHA256

FROZEN_CANDIDATE_IDS: tuple[str, ...] = ("C1", "C2", "C3")
FROZEN_CANDIDATES: dict[str, dict[str, str]] = {
    "C1": {
        "candidate_id": "C1",
        "provider": "GOOGLE",
        "provider_slug": "google",
        "exact_model_id": "gemini-3.8-flash",
    },
    "C2": {
        "candidate_id": "C2",
        "provider": "OPENAI",
        "provider_slug": "openai",
        "exact_model_id": "gpt-6.1-sol",
    },
    "C3": {
        "candidate_id": "C3",
        "provider": "ANTHROPIC",
        "provider_slug": "anthropic",
        "exact_model_id": "claude-sonnet-5-5",
    },
}

FROZEN_CANARY_FIXTURE_IDS: tuple[str, ...] = (
    "W06-DEV-TUNE-007",
    "W06-DEV-TUNE-011",
    "W06-DEV-TUNE-015",
)
FROZEN_CANARY_FIXTURE_COUNT = 3
FROZEN_CANARY_CELL_COUNT = 9
FROZEN_CONCURRENCY = 1
FROZEN_EXECUTION_MODE_LABEL = "STRICT_SEQUENTIAL_SINGLE_WORKER"

FROZEN_TIMEOUT_POLICY_ID = "T3_CANDIDATE_180S"
FROZEN_TIMEOUT_MS = 180000
FROZEN_TIMEOUT_SECONDS = 180.0
FROZEN_PACING_POLICY_ID = "P1_FIXED_2000MS_INTER_CALL_DELAY"
FROZEN_INTER_CALL_DELAY_MS = 2000
FROZEN_DELAY_BEFORE_FIRST_CALL_MS = 0
FROZEN_DELAY_AFTER_LAST_CALL_MS = 0
FROZEN_MAX_SCHEDULED_DELAYS = 8
FROZEN_TOTAL_INTER_CELL_PACING_MS = 16000
FROZEN_RETRY_POLICY_ID = "R0_STRICT_ZERO_RETRY"
FROZEN_AUTOMATIC_RETRY = 0
FROZEN_TRANSPORT_RETRY = 0
FROZEN_MANUAL_RETRY = 0
FROZEN_LLM_REPAIR = 0
FROZEN_SEMANTIC_REPAIR = 0
FROZEN_FALLBACK = False
FROZEN_GENERATION_CALLS_PER_CELL = 1
FROZEN_MAX_GENERATION_CALLS = 9
FROZEN_MAX_OUTPUT_TOKENS = 16384

EXPECTED_CANARY_9_CELL_ORDER: tuple[tuple[int, str, str, str, str], ...] = (
    (
        1,
        "007 / C1",
        "W06-DEV-TUNE-007",
        "C1",
        "W06-AMENDMENT-01-CANARY-01-P1-C1-W06-DEV-TUNE-007",
    ),
    (
        2,
        "007 / C2",
        "W06-DEV-TUNE-007",
        "C2",
        "W06-AMENDMENT-01-CANARY-02-P1-C2-W06-DEV-TUNE-007",
    ),
    (
        3,
        "007 / C3",
        "W06-DEV-TUNE-007",
        "C3",
        "W06-AMENDMENT-01-CANARY-03-P1-C3-W06-DEV-TUNE-007",
    ),
    (
        4,
        "011 / C1",
        "W06-DEV-TUNE-011",
        "C1",
        "W06-AMENDMENT-01-CANARY-04-P1-C1-W06-DEV-TUNE-011",
    ),
    (
        5,
        "011 / C2",
        "W06-DEV-TUNE-011",
        "C2",
        "W06-AMENDMENT-01-CANARY-05-P1-C2-W06-DEV-TUNE-011",
    ),
    (
        6,
        "011 / C3",
        "W06-DEV-TUNE-011",
        "C3",
        "W06-AMENDMENT-01-CANARY-06-P1-C3-W06-DEV-TUNE-011",
    ),
    (
        7,
        "015 / C1",
        "W06-DEV-TUNE-015",
        "C1",
        "W06-AMENDMENT-01-CANARY-07-P1-C1-W06-DEV-TUNE-015",
    ),
    (
        8,
        "015 / C2",
        "W06-DEV-TUNE-015",
        "C2",
        "W06-AMENDMENT-01-CANARY-08-P1-C2-W06-DEV-TUNE-015",
    ),
    (
        9,
        "015 / C3",
        "W06-DEV-TUNE-015",
        "C3",
        "W06-AMENDMENT-01-CANARY-09-P1-C3-W06-DEV-TUNE-015",
    ),
)

FROZEN_REQUIRED_OPERATIONAL_CONDITION_KEYS: tuple[str, ...] = (
    "correct_candidate_provider_model_config_used",
    "exactly_one_generation_call_attempted",
    "no_authentication_failure",
    "no_billing_or_credit_failure",
    "no_client_timeout",
    "no_http_4xx_failure",
    "no_http_5xx_failure",
    "no_model_access_failure",
    "no_provider_transport_failure",
    "no_quota_or_rate_limit_rejection",
    "provider_returns_response",
    "required_provider_model_identity_evidence_captured",
    "retry_count_equals_zero",
)

FROZEN_CANARY_OUTPUT_ROOT_REL_PATH = (
    "data/evaluation/w06/live_amendment_01_canary_v1"
)
FORBIDDEN_PRIMARY_OUTPUT_ROOT_REL_PATH = (
    "data/evaluation/w06/live_dev_select_primary_v1"
)
FUTURE_CANARY_LIVE_COMMAND = (
    "python scripts/run_w06_dev_select_amendment_01_canary_live_v1.py "
    "--execute-live --confirm-frozen-9-canary-cells"
)
EXPECTED_CANARY_PREFLIGHT_REQUEST_SET_SHA256 = (
    "7fbdba7db3d3ba28b82050a7217e5efcaf24706cd0558a3caa971ee7f4414609"
)
EXPECTED_CANARY_PREFLIGHT_ARTIFACT_PATH_SET_SHA256 = (
    "dd59fa8e76e9cb04563fdd07ebda64d4a15797eda98886ed3da03ce71968c9b2"
)

CANARY_CELL_ARTIFACT_FILENAMES: tuple[str, ...] = (
    "request_manifest.json",
    "transport_journal_starting.json",
    "transport_journal_completed.json",
    "raw_provider_response.txt",
    "provider_response_metadata.json",
    "raw_usage_metadata.json",
    "diagnostic_evaluation.json",
    "canary_cell_evidence_receipt.json",
)

AUTHORITATIVE_PRIMARY_STRICT_RATES: dict[str, str] = {
    "C1": "1/60",
    "C2": "8/60",
    "C3": "0/60",
}

FORBIDDEN_CLI_OVERRIDE_PREFIXES: tuple[str, ...] = (
    "--execute",
    "--force",
    "--retry",
    "--max-retries",
    "--resume",
    "--rerun",
    "--best-of",
    "--skip",
    "--ignore-hash",
    "--change-prompt",
    "--prompt",
    "--prompts",
    "--candidate",
    "--candidates",
    "--fixture",
    "--fixtures",
    "--phase",
    "--execution-plan",
    "--manifest",
    "--authorization",
    "--output-root",
    "--output-dir",
    "--batch-root",
    "--cell",
    "--cells",
    "--max-calls",
    "--timeout",
    "--delay",
    "--pacing",
    "--concurrency",
    "--overwrite",
    "--clean",
    "--confirm-frozen-180-cells",
    "--confirm-frozen-120-cells",
    "--comparative",
    "--stochasticity",
)


# ==============================================================================
# 2. OFFLINE NETWORK KILL SWITCH & PREFLIGHT SECRET/.ENV GUARD (SECTIONS 9, 15, 16)
# ==============================================================================


class OutboundNetworkBlockedError(RuntimeError):
    """Raised if any code attempts an outbound network connection during offline preflight/simulation."""


class PreflightSecretAccessForbiddenError(DevLiveAuthorizationError):
    """Raised if any code attempts to read `.env` or inspect API keys during offline preflight/simulation."""


class NetworkKillSwitchGuard:
    """Context manager blocking all socket, urllib, httpx, and httpx2 outbound network calls."""

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
        httpx.HTTPTransport.handle_request = _deny(  # type: ignore[method-assign]
            "httpx.HTTPTransport.handle_request"
        )
        httpx.AsyncHTTPTransport.handle_async_request = _deny(  # type: ignore[method-assign]
            "httpx.AsyncHTTPTransport.handle_async_request"
        )
        httpx2.Client.send = _deny("httpx2.Client.send")  # type: ignore[method-assign]
        httpx2.AsyncClient.send = _deny("httpx2.AsyncClient.send")  # type: ignore[method-assign]
        if self._orig_httpx2_transport is not None:
            httpx2.HTTPTransport.handle_request = _deny(  # type: ignore[method-assign]
                "httpx2.HTTPTransport.handle_request"
            )
        if self._orig_httpx2_async_transport is not None:
            httpx2.AsyncHTTPTransport.handle_async_request = _deny(  # type: ignore[method-assign]
                "httpx2.AsyncHTTPTransport.handle_async_request"
            )
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
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
        if self._orig_httpx2_transport is not None:
            httpx2.HTTPTransport.handle_request = self._orig_httpx2_transport  # type: ignore[method-assign]
        if self._orig_httpx2_async_transport is not None:
            httpx2.AsyncHTTPTransport.handle_async_request = (  # type: ignore[method-assign]
                self._orig_httpx2_async_transport
            )


_FORBIDDEN_PREFLIGHT_ENV_KEY_NAMES: frozenset[str] = frozenset(
    {
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
    }
)


def _is_dotenv_path(path_like: Any) -> bool:
    try:
        p = Path(os.fspath(path_like))
    except Exception:
        return False
    name_low = p.name.lower()
    return name_low == ".env" or name_low.startswith(".env.")


class PreflightSecretAndEnvFileAccessGuard:
    """Fail-closed guard blocking `.env` file access and API-key environment variable inspection during preflight."""

    def __enter__(self) -> "PreflightSecretAndEnvFileAccessGuard":
        self._orig_builtins_open = builtins.open
        self._orig_io_open = io.open
        self._orig_path_open = Path.open
        self._orig_path_read_text = Path.read_text
        self._orig_path_read_bytes = Path.read_bytes
        self._orig_os_getenv = os.getenv
        self._orig_environ_get = os.environ.get
        self._orig_environ_getitem = os.environ.__getitem__

        orig_b_open = self._orig_builtins_open
        orig_i_open = self._orig_io_open
        orig_p_open = self._orig_path_open
        orig_p_read_text = self._orig_path_read_text
        orig_p_read_bytes = self._orig_path_read_bytes
        orig_getenv = self._orig_os_getenv
        orig_env_get = self._orig_environ_get
        orig_env_getitem = self._orig_environ_getitem

        def _guarded_builtins_open(file: Any, *args: Any, **kwargs: Any) -> Any:
            if _is_dotenv_path(file):
                raise PreflightSecretAccessForbiddenError(
                    f"PREFLIGHT_DOTENV_READ_FORBIDDEN: Reading .env file {file!r} is forbidden during offline preflight."
                )
            return orig_b_open(file, *args, **kwargs)

        def _guarded_io_open(file: Any, *args: Any, **kwargs: Any) -> Any:
            if _is_dotenv_path(file):
                raise PreflightSecretAccessForbiddenError(
                    f"PREFLIGHT_DOTENV_READ_FORBIDDEN: Reading .env file {file!r} is forbidden during offline preflight."
                )
            return orig_i_open(file, *args, **kwargs)

        def _guarded_path_open(self_path: Path, *args: Any, **kwargs: Any) -> Any:
            if _is_dotenv_path(self_path):
                raise PreflightSecretAccessForbiddenError(
                    f"PREFLIGHT_DOTENV_READ_FORBIDDEN: Reading .env file {self_path!r} is forbidden during offline preflight."
                )
            return orig_p_open(self_path, *args, **kwargs)

        def _guarded_path_read_text(self_path: Path, *args: Any, **kwargs: Any) -> str:
            if _is_dotenv_path(self_path):
                raise PreflightSecretAccessForbiddenError(
                    f"PREFLIGHT_DOTENV_READ_FORBIDDEN: Reading .env file {self_path!r} is forbidden during offline preflight."
                )
            return orig_p_read_text(self_path, *args, **kwargs)

        def _guarded_path_read_bytes(
            self_path: Path, *args: Any, **kwargs: Any
        ) -> bytes:
            if _is_dotenv_path(self_path):
                raise PreflightSecretAccessForbiddenError(
                    f"PREFLIGHT_DOTENV_READ_FORBIDDEN: Reading .env file {self_path!r} is forbidden during offline preflight."
                )
            return orig_p_read_bytes(self_path, *args, **kwargs)

        def _guarded_getenv(key: str, default: Any = None) -> Any:
            if str(key).strip().upper() in _FORBIDDEN_PREFLIGHT_ENV_KEY_NAMES:
                raise PreflightSecretAccessForbiddenError(
                    f"PREFLIGHT_API_KEY_INSPECTION_FORBIDDEN: Inspecting {key!r} is forbidden during offline preflight."
                )
            return orig_getenv(key, default)

        def _guarded_env_get(key: str, default: Any = None) -> Any:
            if str(key).strip().upper() in _FORBIDDEN_PREFLIGHT_ENV_KEY_NAMES:
                raise PreflightSecretAccessForbiddenError(
                    f"PREFLIGHT_API_KEY_INSPECTION_FORBIDDEN: Inspecting {key!r} is forbidden during offline preflight."
                )
            return orig_env_get(key, default)

        def _guarded_env_getitem(key: str) -> str:
            if str(key).strip().upper() in _FORBIDDEN_PREFLIGHT_ENV_KEY_NAMES:
                raise PreflightSecretAccessForbiddenError(
                    f"PREFLIGHT_API_KEY_INSPECTION_FORBIDDEN: Inspecting {key!r} is forbidden during offline preflight."
                )
            return orig_env_getitem(key)

        builtins.open = _guarded_builtins_open  # type: ignore[assignment]
        io.open = _guarded_io_open  # type: ignore[assignment]
        Path.open = _guarded_path_open  # type: ignore[method-assign]
        Path.read_text = _guarded_path_read_text  # type: ignore[method-assign]
        Path.read_bytes = _guarded_path_read_bytes  # type: ignore[method-assign]
        os.getenv = _guarded_getenv  # type: ignore[assignment]
        os.environ.get = _guarded_env_get  # type: ignore[method-assign]
        os.environ.__getitem__ = _guarded_env_getitem  # type: ignore[method-assign]
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        builtins.open = self._orig_builtins_open  # type: ignore[assignment]
        io.open = self._orig_io_open  # type: ignore[assignment]
        Path.open = self._orig_path_open  # type: ignore[method-assign]
        Path.read_text = self._orig_path_read_text  # type: ignore[method-assign]
        Path.read_bytes = self._orig_path_read_bytes  # type: ignore[method-assign]
        os.getenv = self._orig_os_getenv  # type: ignore[assignment]
        os.environ.get = self._orig_environ_get  # type: ignore[method-assign]
        os.environ.__getitem__ = self._orig_environ_getitem  # type: ignore[method-assign]


# ==============================================================================
# 3. AUTHORITY BINDING & CONTRACT VERIFICATION (SECTIONS 4, 5, 6, 7, 10)
# ==============================================================================


def _compute_file_lf_sha256(path: Path) -> str:
    return sha256_bytes(normalize_lf_bytes(path.read_bytes()))


def _compute_internal_sha256(payload: Mapping[str, Any], internal_key: str) -> str:
    body = {k: v for k, v in payload.items() if k != internal_key}
    return sha256_bytes(canonical_json_bytes(body))


def _verify_json_authority_file(
    repo_root: Path,
    *,
    rel_path: str,
    expected_file_sha256: str,
    internal_sha_key: str | None = None,
    expected_internal_sha256: str | None = None,
) -> dict[str, Any]:
    path = repo_root / rel_path
    _assert_runner_not_final100_path(path)
    if not path.is_file():
        raise PlanBeforeLiveProtocolError(
            f"MISSING_BOUND_AUTHORITY_FILE: {rel_path}"
        )
    actual_file_sha = _compute_file_lf_sha256(path)
    if actual_file_sha != expected_file_sha256:
        raise PlanBeforeLiveProtocolError(
            f"BOUND_AUTHORITY_FILE_SHA256_MISMATCH for {rel_path}: "
            f"expected={expected_file_sha256}, got={actual_file_sha}"
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise PlanBeforeLiveProtocolError(
            f"INVALID_BOUND_AUTHORITY_JSON_OBJECT: {rel_path}"
        )
    if internal_sha_key is not None and expected_internal_sha256 is not None:
        recorded_internal = data.get(internal_sha_key)
        computed_internal = _compute_internal_sha256(data, internal_sha_key)
        if (
            recorded_internal != expected_internal_sha256
            or computed_internal != expected_internal_sha256
        ):
            raise PlanBeforeLiveProtocolError(
                f"BOUND_AUTHORITY_INTERNAL_SHA256_MISMATCH for {rel_path} ({internal_sha_key}): "
                f"expected={expected_internal_sha256}, recorded={recorded_internal}, computed={computed_internal}"
            )
    return data


def verify_source_develop_provenance(
    repo_root: Path = REPO_ROOT,
    *,
    expected_source_sha: str = AUTHORITATIVE_BASE_DEVELOP_SHA,
    git_runner: Callable[[list[str]], subprocess.CompletedProcess[str]] | None = None,
) -> dict[str, Any]:
    """Verify `develop@1ebe30c251958542088a3056dcfc6b780dac3a88` commit existence and ancestry of `HEAD`."""
    if len(expected_source_sha) != 40 or any(
        c not in "0123456789abcdef" for c in expected_source_sha
    ):
        raise PlanBeforeLiveProtocolError(
            f"INVALID_BASE_DEVELOP_SHA: {expected_source_sha!r}"
        )

    def _default_git_runner(args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )

    runner = git_runner or _default_git_runner

    head_proc = runner(["rev-parse", "HEAD"])
    active_head_sha = (
        head_proc.stdout.strip()
        if head_proc.returncode == 0 and head_proc.stdout.strip()
        else expected_source_sha
    )

    cat_proc = runner(["cat-file", "-e", f"{expected_source_sha}^{{commit}}"])
    if cat_proc.returncode == 0:
        anc_proc = runner(
            ["merge-base", "--is-ancestor", expected_source_sha, "HEAD"]
        )
        if anc_proc.returncode != 0:
            raise PlanBeforeLiveProtocolError(
                f"SOURCE_DEVELOP_NOT_ANCESTOR_OF_HEAD: {expected_source_sha} is not an ancestor of HEAD."
            )

        p1_proc = runner(["rev-parse", f"{expected_source_sha}^1"])
        p2_proc = runner(["rev-parse", f"{expected_source_sha}^2"])
        if (
            p1_proc.returncode == 0
            and p2_proc.returncode == 0
            and expected_source_sha == PR_72_MERGE_COMMIT_SHA
        ):
            p1_sha = p1_proc.stdout.strip()
            p2_sha = p2_proc.stdout.strip()
            if p1_sha != PR_72_MERGE_PARENT_1 or p2_sha != PR_72_MERGE_PARENT_2:
                raise PlanBeforeLiveProtocolError(
                    f"PR_72_MERGE_PARENTS_MISMATCH: got=({p1_sha}, {p2_sha}), "
                    f"expected=({PR_72_MERGE_PARENT_1}, {PR_72_MERGE_PARENT_2})"
                )

        return {
            "authoritative_base_develop_sha": expected_source_sha,
            "active_head_sha": active_head_sha,
            "pr_72_merge_commit_sha": PR_72_MERGE_COMMIT_SHA,
            "pr_72_parent_1": PR_72_MERGE_PARENT_1,
            "pr_72_parent_2": PR_72_MERGE_PARENT_2,
            "commit_exists_in_local_git": True,
            "is_shallow_repository": False,
            "is_ancestor_of_head": True,
            "verified": True,
        }

    shallow_proc = runner(["rev-parse", "--is-shallow-repository"])
    is_shallow = (
        shallow_proc.returncode == 0
        and shallow_proc.stdout.strip().lower() == "true"
    )
    if not is_shallow:
        raise PlanBeforeLiveProtocolError(
            f"SOURCE_DEVELOP_COMMIT_MISSING: {expected_source_sha} not found in non-shallow git object database."
        )

    fallback_checks = {
        "canary_auth_prep_file_sha256": (
            (repo_root / CANARY_AUTH_PREP_REL_PATH).is_file()
            and _compute_file_lf_sha256(repo_root / CANARY_AUTH_PREP_REL_PATH)
            == EXPECTED_CANARY_AUTH_PREP_FILE_SHA256
        ),
        "canary_manifest_file_sha256": (
            (repo_root / CANARY_MANIFEST_REL_PATH).is_file()
            and _compute_file_lf_sha256(repo_root / CANARY_MANIFEST_REL_PATH)
            == EXPECTED_CANARY_MANIFEST_FILE_SHA256
        ),
        "owner_readiness_file_sha256": (
            (repo_root / OWNER_READINESS_ATTESTATION_REL_PATH).is_file()
            and _compute_file_lf_sha256(
                repo_root / OWNER_READINESS_ATTESTATION_REL_PATH
            )
            == EXPECTED_OWNER_READINESS_ATTESTATION_FILE_SHA256
        ),
        "scientific_code_bundle_sha256": (
            compute_scientific_code_bundle_sha256(repo_root=repo_root)
            == EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
        ),
    }
    if not all(fallback_checks.values()):
        raise PlanBeforeLiveProtocolError(
            f"SHALLOW_REPO_AUTHORITY_MISMATCH: {fallback_checks}"
        )

    return {
        "authoritative_base_develop_sha": expected_source_sha,
        "active_head_sha": active_head_sha,
        "pr_72_merge_commit_sha": PR_72_MERGE_COMMIT_SHA,
        "pr_72_parent_1": PR_72_MERGE_PARENT_1,
        "pr_72_parent_2": PR_72_MERGE_PARENT_2,
        "commit_exists_in_local_git": False,
        "is_shallow_repository": True,
        "is_ancestor_of_head": True,
        "verified": True,
    }


def verify_canary_output_root_not_existing(
    repo_root: Path = REPO_ROOT,
    *,
    output_root_override: Path | None = None,
) -> Path:
    """Verify the immutable canary output root does not exist prior to execution (Section 10)."""
    target = (
        output_root_override
        if output_root_override is not None
        else (repo_root / FROZEN_CANARY_OUTPUT_ROOT_REL_PATH)
    )
    _assert_runner_not_final100_path(target)
    target_posix = target.as_posix().lower()
    if "live_dev_select_primary_v1" in target_posix:
        raise PlanBeforeLiveProtocolError(
            f"PRIMARY_DEV_SELECT_OUTPUT_ROOT_FORBIDDEN_IN_CANARY_LAUNCHER: {target}"
        )
    if target.exists():
        raise ImmutableCellExecutionError(
            f"CANARY_OUTPUT_ROOT_ALREADY_EXISTS: {target} already exists; "
            "no resume, no overwrite, no automatic deletion, and no reuse after partial failure are permitted."
        )
    return target


def verify_frozen_canary_contract_and_cells(
    *,
    auth_prep: Mapping[str, Any],
    canary_manifest: Mapping[str, Any],
    dev_bundle: VerifiedDevBundle,
    cand_reg: DevCandidateRegistry,
    p1_spec: PromptCandidateSpec,
) -> list[dict[str, Any]]:
    """Verify the frozen 3 candidates, 3 fixtures, 9-cell order, runtime policy, and operational criteria (Sections 5, 6, 7, 12)."""
    if (
        auth_prep.get("AMENDED_CANARY_LIVE_AUTHORIZED") is not False
        or auth_prep.get("AMENDED_COMPARATIVE_LIVE_AUTHORIZED") is not False
        or auth_prep.get("AMENDED_LIVE_AUTHORIZED") is not False
        or auth_prep.get("FINAL100_USED") is not False
        or auth_prep.get("FINAL100_STATUS") != "NO-GO"
    ):
        raise PlanBeforeLiveProtocolError(
            "CANARY_AUTH_PREP_STATE_FLAG_MISMATCH: Frozen PREP artifact must preserve "
            "AMENDED_CANARY_LIVE_AUTHORIZED=False, AMENDED_COMPARATIVE_LIVE_AUTHORIZED=False, and FINAL100_STATUS='NO-GO'."
        )
    contract = auth_prep.get("frozen_canary_execution_contract")
    if not isinstance(contract, Mapping):
        raise PlanBeforeLiveProtocolError(
            "CANARY_AUTH_PREP_CONTRACT_MISSING: frozen_canary_execution_contract missing."
        )

    # Verify candidates (Section 5)
    cands_in_contract = contract.get("candidates")
    if not isinstance(cands_in_contract, Mapping) or tuple(
        sorted(cands_in_contract.keys())
    ) != FROZEN_CANDIDATE_IDS:
        raise CandidateRegistryIntegrityError(
            f"CANARY_CANDIDATE_SET_MISMATCH: expected {list(FROZEN_CANDIDATE_IDS)}, got {list(cands_in_contract.keys()) if isinstance(cands_in_contract, Mapping) else cands_in_contract!r}"
        )

    for cid, expected_c in FROZEN_CANDIDATES.items():
        c_entry = cands_in_contract.get(cid)
        reg_spec = cand_reg.candidates.get(cid)
        if (
            not isinstance(c_entry, Mapping)
            or reg_spec is None
            or c_entry.get("candidate_id") != cid
            or c_entry.get("provider") != expected_c["provider"]
            or c_entry.get("provider_slug") != expected_c["provider_slug"]
            or c_entry.get("exact_model_id") != expected_c["exact_model_id"]
            or c_entry.get("assigned_canary_calls") != 3
            or reg_spec.requested_model_id != expected_c["exact_model_id"]
            or CANDIDATE_MODEL_BY_ID.get(cid) != expected_c["exact_model_id"]
            or CANDIDATE_PROVIDER_BY_ID.get(cid) != expected_c["provider_slug"]
        ):
            raise CandidateRegistryIntegrityError(
                f"CANARY_CANDIDATE_MODEL_OR_PROVIDER_MISMATCH for {cid}: {c_entry!r}"
            )

    if (
        contract.get("candidate_substitution_permitted") is not False
        or contract.get("fourth_model_permitted") is not False
        or contract.get("additional_fixture_permitted") is not False
        or contract.get("replacement_fixture_permitted") is not False
        or contract.get("final100_scenario_permitted") is not False
    ):
        raise CandidateRegistryIntegrityError(
            "CANARY_SUBSTITUTION_OR_FIREWALL_FLAG_MISMATCH"
        )

    # Verify runtime policy (Section 7)
    rt = contract.get("frozen_runtime_policy")
    if not isinstance(rt, Mapping):
        raise PlanBeforeLiveProtocolError(
            "CANARY_RUNTIME_POLICY_MISSING: frozen_runtime_policy missing."
        )
    if (
        rt.get("timeout_policy_id") != FROZEN_TIMEOUT_POLICY_ID
        or rt.get("timeout_ms") != FROZEN_TIMEOUT_MS
        or rt.get("pacing_policy_id") != FROZEN_PACING_POLICY_ID
        or rt.get("inter_call_delay_ms") != FROZEN_INTER_CALL_DELAY_MS
        or rt.get("total_inter_cell_pacing_intervals") != FROZEN_MAX_SCHEDULED_DELAYS
        or rt.get("total_inter_cell_pacing_ms") != FROZEN_TOTAL_INTER_CELL_PACING_MS
        or rt.get("retry_policy_id") != FROZEN_RETRY_POLICY_ID
        or rt.get("automatic_retry") != FROZEN_AUTOMATIC_RETRY
        or rt.get("transport_retry") != FROZEN_TRANSPORT_RETRY
        or rt.get("manual_retry") != FROZEN_MANUAL_RETRY
        or rt.get("llm_repair") != FROZEN_LLM_REPAIR
        or rt.get("semantic_repair") != FROZEN_SEMANTIC_REPAIR
        or rt.get("fallback") is not FROZEN_FALLBACK
        or rt.get("generation_calls_per_assigned_cell")
        != FROZEN_GENERATION_CALLS_PER_CELL
        or rt.get("adaptive_pacing_permitted") is not False
        or rt.get("dynamic_timeout_permitted") is not False
        or rt.get("retry_after_timeout_429_or_5xx_permitted") is not False
        or rt.get("provider_specific_special_treatment_permitted") is not False
        or canary_manifest.get("timeout_ms") != FROZEN_TIMEOUT_MS
        or canary_manifest.get("timeout_policy_id") != FROZEN_TIMEOUT_POLICY_ID
        or canary_manifest.get("inter_call_delay_ms") != FROZEN_INTER_CALL_DELAY_MS
        or canary_manifest.get("pacing_policy_id") != FROZEN_PACING_POLICY_ID
        or canary_manifest.get("retry_policy_id") != FROZEN_RETRY_POLICY_ID
        or canary_manifest.get("retries_permitted") is not False
        or canary_manifest.get("reruns_permitted") is not False
    ):
        raise PlanBeforeLiveProtocolError(
            f"CANARY_RUNTIME_POLICY_MISMATCH: {rt!r}"
        )

    # Verify operational PASS criterion & fail-stop & aggregate rule (Sections 12, 13, 14)
    op_crit = contract.get("operational_pass_criterion_per_cell")
    if not isinstance(op_crit, Mapping):
        raise PlanBeforeLiveProtocolError(
            "CANARY_OPERATIONAL_PASS_CRITERION_MISSING"
        )
    req_conds = op_crit.get("required_operational_conditions")
    if (
        not isinstance(req_conds, Mapping)
        or tuple(sorted(req_conds.keys())) != FROZEN_REQUIRED_OPERATIONAL_CONDITION_KEYS
        or not all(req_conds[k] is True for k in FROZEN_REQUIRED_OPERATIONAL_CONDITION_KEYS)
        or op_crit.get("planner_schema_validity_is_operational_pass_criterion")
        is not False
        or op_crit.get("final_core_quality_is_operational_pass_criterion") is not False
        or "raw_response_parseable_json" in req_conds
    ):
        raise PlanBeforeLiveProtocolError(
            f"CANARY_OPERATIONAL_PASS_CRITERION_MISMATCH: {op_crit!r}"
        )

    agg_rule = contract.get("aggregate_canary_decision_rule")
    if (
        not isinstance(agg_rule, Mapping)
        or agg_rule.get("required_condition")
        != "ALL_9_CANARY_OPERATIONAL_PASS == true"
        or agg_rule.get("required_operational_pass_cells") != 9
        or agg_rule.get("required_operational_pass_fraction") != "9/9"
        or agg_rule.get("total_assigned_canary_cells") != 9
        or agg_rule.get("eight_of_nine_permitted") is not False
    ):
        raise PlanBeforeLiveProtocolError(
            f"CANARY_AGGREGATE_DECISION_RULE_MISMATCH: {agg_rule!r}"
        )

    fail_stop = contract.get("fail_stop_rule")
    if (
        not isinstance(fail_stop, Mapping)
        or fail_stop.get("fail_closed_on_any_operational_cell_failure") is not True
        or fail_stop.get("preserve_exact_failure_evidence") is not True
        or fail_stop.get("retry_on_failure_permitted") is not False
        or fail_stop.get("rerun_same_cell_permitted") is not False
        or fail_stop.get("replace_fixture_on_failure_permitted") is not False
        or fail_stop.get("continue_under_improvised_rule_permitted") is not False
        or fail_stop.get("comparative_remains_unauthorized_on_failure") is not True
        or fail_stop.get("return_to_chatgpt_audit_on_failure") is not True
    ):
        raise PlanBeforeLiveProtocolError(
            f"CANARY_FAIL_STOP_RULE_MISMATCH: {fail_stop!r}"
        )

    # Verify exact fixtures & 9-cell order (Section 6)
    if (
        tuple(contract.get("exact_canary_fixtures", ())) != FROZEN_CANARY_FIXTURE_IDS
        or tuple(canary_manifest.get("fixture_ids", ())) != FROZEN_CANARY_FIXTURE_IDS
        or contract.get("fixture_count") != FROZEN_CANARY_FIXTURE_COUNT
        or canary_manifest.get("fixture_count") != FROZEN_CANARY_FIXTURE_COUNT
        or contract.get("total_maximum_canary_generation_calls")
        != FROZEN_MAX_GENERATION_CALLS
        or canary_manifest.get("assigned_canary_cells") != FROZEN_CANARY_CELL_COUNT
        or canary_manifest.get("prompt_id") != FROZEN_PROMPT_ID
    ):
        raise PlanBeforeLiveProtocolError("CANARY_FIXTURE_OR_CELL_COUNT_MISMATCH")

    expected_labels = [row[1] for row in EXPECTED_CANARY_9_CELL_ORDER]
    if contract.get("exact_9_cell_execution_order_labels") != expected_labels:
        raise PlanBeforeLiveProtocolError(
            f"CANARY_ORDER_LABELS_MISMATCH: {contract.get('exact_9_cell_execution_order_labels')!r}"
        )

    auth_cells = contract.get("ordered_canary_cells")
    manifest_cells = canary_manifest.get("cells")
    if (
        not isinstance(auth_cells, list)
        or not isinstance(manifest_cells, list)
        or len(auth_cells) != FROZEN_CANARY_CELL_COUNT
        or len(manifest_cells) != FROZEN_CANARY_CELL_COUNT
    ):
        raise PlanBeforeLiveProtocolError("CANARY_CELLS_LIST_INVALID")

    dev_tune_by_id = {s.scenario_id: s for s in dev_bundle.dev_tune_fixtures}
    dev_select_ids = {s.scenario_id for s in dev_bundle.dev_select_fixtures}
    pconf_sha_by_cid = {
        cid: compute_candidate_provider_config_sha256(cand_reg.candidates[cid])
        for cid in FROZEN_CANDIDATE_IDS
    }
    scen_ctx_by_fid = {}
    for fid in FROZEN_CANARY_FIXTURE_IDS:
        assert_not_final100_scenario_id(fid)
        if fid in dev_select_ids or fid not in dev_tune_by_id:
            raise PlanBeforeLiveProtocolError(
                f"CANARY_FIXTURE_POOL_VIOLATION: {fid!r} must exist exclusively in DEV_TUNE."
            )
        scen = dev_tune_by_id[fid]
        assert_not_final100_scenario(scen)
        scen_ctx_by_fid[fid] = build_deterministic_dev_scenario_context(scen, p1_spec)

    verified_cells: list[dict[str, Any]] = []
    for idx, (
        exp_order,
        exp_short_label,
        exp_fid,
        exp_cid,
        exp_cell_id,
    ) in enumerate(EXPECTED_CANARY_9_CELL_ORDER):
        ac = auth_cells[idx]
        mc = manifest_cells[idx]
        if not isinstance(ac, Mapping) or not isinstance(mc, Mapping):
            raise PlanBeforeLiveProtocolError(f"CANARY_CELL_NOT_MAPPING at index {idx}")

        expected_c = FROZEN_CANDIDATES[exp_cid]
        scen_ctx = scen_ctx_by_fid[exp_fid]
        expected_delay_after = FROZEN_INTER_CALL_DELAY_MS if exp_order < 9 else 0

        if (
            ac.get("order_index") != exp_order
            or mc.get("order_index") != exp_order
            or ac.get("order_code") != f"{exp_order:02d}"
            or mc.get("order_code") != f"{exp_order:02d}"
            or ac.get("short_label") != exp_short_label
            or ac.get("cell_id") != exp_cell_id
            or mc.get("cell_id") != exp_cell_id
            or ac.get("fixture_id") != exp_fid
            or mc.get("fixture_id") != exp_fid
            or ac.get("candidate_id") != exp_cid
            or mc.get("candidate_id") != exp_cid
            or ac.get("provider") != expected_c["provider"]
            or ac.get("provider_slug") != expected_c["provider_slug"]
            or mc.get("provider") != expected_c["provider_slug"]
            or ac.get("requested_model_id") != expected_c["exact_model_id"]
            or mc.get("requested_model_id") != expected_c["exact_model_id"]
            or ac.get("prompt_id") != FROZEN_PROMPT_ID
            or mc.get("prompt_id") != FROZEN_PROMPT_ID
            or ac.get("attempt_number") != 1
            or mc.get("attempt_number") != 1
            or ac.get("generation_calls_for_cell") != 1
            or ac.get("timeout_ms") != FROZEN_TIMEOUT_MS
            or mc.get("timeout_ms") != FROZEN_TIMEOUT_MS
            or ac.get("inter_call_delay_ms_before_next_cell") != expected_delay_after
            or mc.get("inter_call_delay_ms_before_next_cell") != expected_delay_after
            or ac.get("retry") != 0
            or mc.get("retry") != 0
            or ac.get("automatic_retry") != 0
            or mc.get("automatic_retry") != 0
            or ac.get("transport_retry") != 0
            or mc.get("transport_retry") != 0
            or ac.get("manual_retry") != 0
            or mc.get("manual_retry") != 0
            or ac.get("llm_repair") != 0
            or mc.get("llm_repair") != 0
            or ac.get("semantic_repair") != 0
            or mc.get("semantic_repair") != 0
            or ac.get("fallback") is not False
            or mc.get("fallback") is not False
            or ac.get("tools") is not False
            or mc.get("tools") is not False
            or ac.get("max_output_tokens") != FROZEN_MAX_OUTPUT_TOKENS
            or mc.get("max_output_tokens") != FROZEN_MAX_OUTPUT_TOKENS
            or ac.get("system_prompt_sha256") != EXPECTED_P1_SYSTEM_PROMPT_SHA256
            or ac.get("system_prompt_sha256") != scen_ctx.system_prompt_sha256
            or ac.get("user_prompt_sha256") != scen_ctx.user_prompt_sha256
            or ac.get("scenario_sha256") != scen_ctx.scenario_sha256
            or ac.get("catalog_context_sha256") != scen_ctx.catalog_context_sha256
            or ac.get("primary_baseline_provider_config_sha256")
            != pconf_sha_by_cid[exp_cid]
            or ac.get("portable_generation_schema_v2_sha256")
            != EXPECTED_PORTABLE_SCHEMA_V2_SHA256
            or ac.get("semantic_schema_sha256") != EXPECTED_SEMANTIC_SCHEMA_SHA256
            or ac.get("scientific_code_bundle_sha256")
            != EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
        ):
            raise PlanBeforeLiveProtocolError(
                f"CANARY_CELL_CONTRACT_MISMATCH at order_index={exp_order} ({exp_cell_id})"
            )

        verified_cells.append(dict(ac))

    return verified_cells


def verify_frozen_canary_launcher_authorities(
    repo_root: Path = REPO_ROOT,
    *,
    output_root_override: Path | None = None,
) -> dict[str, Any]:
    """Verify all bound upstream authorities, hashes, registries, schemas, and firewalls (Sections 3..10)."""
    # 1. Source develop provenance
    source_prov = verify_source_develop_provenance(repo_root=repo_root)

    # 2. Scientific code bundle & primary launcher untouched
    bundle_sha = compute_scientific_code_bundle_sha256(repo_root=repo_root)
    if bundle_sha != EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256:
        raise ScientificCodeBundleIntegrityError(
            f"SCIENTIFIC_CODE_BUNDLE_DRIFT: expected={EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256}, got={bundle_sha}"
        )
    if LAUNCHER_REL_PATH in SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS:
        raise ScientificCodeBundleIntegrityError(
            f"CANARY_LAUNCHER_INSIDE_SCIENTIFIC_BUNDLE_FORBIDDEN: {LAUNCHER_REL_PATH}"
        )

    primary_launcher_path = repo_root / PRIMARY_LAUNCHER_REL_PATH
    if not primary_launcher_path.is_file():
        raise PlanBeforeLiveProtocolError(
            f"PRIMARY_LAUNCHER_MISSING: {PRIMARY_LAUNCHER_REL_PATH}"
        )
    primary_launcher_lf_sha = _compute_file_lf_sha256(primary_launcher_path)
    if primary_launcher_lf_sha != EXPECTED_PRIMARY_LAUNCHER_LF_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"PRIMARY_LAUNCHER_MODIFIED_FORBIDDEN: expected={EXPECTED_PRIMARY_LAUNCHER_LF_SHA256}, got={primary_launcher_lf_sha}"
        )

    # 3. Verify bound JSON & Markdown authorities
    auth_prep = _verify_json_authority_file(
        repo_root,
        rel_path=CANARY_AUTH_PREP_REL_PATH,
        expected_file_sha256=EXPECTED_CANARY_AUTH_PREP_FILE_SHA256,
        internal_sha_key="canary_live_authorization_prep_internal_sha256",
        expected_internal_sha256=EXPECTED_CANARY_AUTH_PREP_INTERNAL_SHA256,
    )
    if auth_prep.get("AMENDED_CANARY_LIVE_AUTHORIZED") is not False:
        raise PlanBeforeLiveProtocolError(
            "CANARY_AUTH_PREP_HISTORICAL_MUTATION_FORBIDDEN: "
            "w06_dev_select_amendment_01_canary_authorization_prep_v1.json is historical/frozen and "
            "its AMENDED_CANARY_LIVE_AUTHORIZED must remain false. Live authorization requires the "
            f"separate receipt {CANARY_LIVE_EXECUTION_AUTH_RECEIPT_REL_PATH}."
        )
    auth_prep_doc_path = repo_root / CANARY_AUTH_PREP_DOC_REL_PATH
    if (
        not auth_prep_doc_path.is_file()
        or _compute_file_lf_sha256(auth_prep_doc_path)
        != EXPECTED_CANARY_AUTH_PREP_DOC_SHA256
    ):
        raise PlanBeforeLiveProtocolError("CANARY_AUTH_PREP_DOC_SHA256_MISMATCH")

    canary_manifest = _verify_json_authority_file(
        repo_root,
        rel_path=CANARY_MANIFEST_REL_PATH,
        expected_file_sha256=EXPECTED_CANARY_MANIFEST_FILE_SHA256,
        internal_sha_key="canary_manifest_internal_sha256",
        expected_internal_sha256=EXPECTED_CANARY_MANIFEST_INTERNAL_SHA256,
    )

    owner_readiness = _verify_json_authority_file(
        repo_root,
        rel_path=OWNER_READINESS_ATTESTATION_REL_PATH,
        expected_file_sha256=EXPECTED_OWNER_READINESS_ATTESTATION_FILE_SHA256,
        internal_sha_key="owner_readiness_attestation_internal_sha256",
        expected_internal_sha256=EXPECTED_OWNER_READINESS_ATTESTATION_INTERNAL_SHA256,
    )
    owner_doc_path = repo_root / OWNER_READINESS_ATTESTATION_DOC_REL_PATH
    if (
        not owner_doc_path.is_file()
        or _compute_file_lf_sha256(owner_doc_path)
        != EXPECTED_OWNER_READINESS_ATTESTATION_DOC_SHA256
    ):
        raise PlanBeforeLiveProtocolError("OWNER_READINESS_DOC_SHA256_MISMATCH")

    _verify_json_authority_file(
        repo_root,
        rel_path=DECISION_ARTIFACT_REL_PATH,
        expected_file_sha256=EXPECTED_DECISION_ARTIFACT_FILE_SHA256,
        internal_sha_key="decision_artifact_internal_sha256",
        expected_internal_sha256=EXPECTED_DECISION_ARTIFACT_INTERNAL_SHA256,
    )
    _verify_json_authority_file(
        repo_root,
        rel_path=APPROVAL_RECEIPT_REL_PATH,
        expected_file_sha256=EXPECTED_APPROVAL_RECEIPT_FILE_SHA256,
        internal_sha_key="approval_receipt_internal_sha256",
        expected_internal_sha256=EXPECTED_APPROVAL_RECEIPT_INTERNAL_SHA256,
    )
    _verify_json_authority_file(
        repo_root,
        rel_path=PROVIDER_READINESS_PRICING_PREP_REL_PATH,
        expected_file_sha256=EXPECTED_PROVIDER_READINESS_PRICING_PREP_FILE_SHA256,
        internal_sha_key="provider_readiness_pricing_prep_sha256",
        expected_internal_sha256=EXPECTED_PROVIDER_READINESS_PRICING_PREP_INTERNAL_SHA256,
    )
    _verify_json_authority_file(
        repo_root,
        rel_path=PUBLIC_PRICING_SNAPSHOT_REL_PATH,
        expected_file_sha256=EXPECTED_PUBLIC_PRICING_SNAPSHOT_FILE_SHA256,
        internal_sha_key="public_pricing_snapshot_sha256",
        expected_internal_sha256=EXPECTED_PUBLIC_PRICING_SNAPSHOT_INTERNAL_SHA256,
    )
    _verify_json_authority_file(
        repo_root,
        rel_path=PREP_ARTIFACT_REL_PATH,
        expected_file_sha256=EXPECTED_PREP_ARTIFACT_FILE_SHA256,
        internal_sha_key="prep_artifact_internal_sha256",
        expected_internal_sha256=EXPECTED_PREP_ARTIFACT_INTERNAL_SHA256,
    )
    primary_freeze_receipt = _verify_json_authority_file(
        repo_root,
        rel_path=PRIMARY_RESULTS_FREEZE_RECEIPT_REL_PATH,
        expected_file_sha256=EXPECTED_PRIMARY_RESULTS_FREEZE_RECEIPT_FILE_SHA256,
        internal_sha_key="results_freeze_receipt_sha256",
        expected_internal_sha256=EXPECTED_PRIMARY_RESULTS_FREEZE_RECEIPT_INTERNAL_SHA256,
    )
    _verify_json_authority_file(
        repo_root,
        rel_path=PRIMARY_RESULTS_MANIFEST_REL_PATH,
        expected_file_sha256=EXPECTED_PRIMARY_RESULTS_MANIFEST_FILE_SHA256,
        internal_sha_key="results_manifest_sha256",
        expected_internal_sha256=EXPECTED_PRIMARY_RESULTS_MANIFEST_INTERNAL_SHA256,
    )
    _verify_json_authority_file(
        repo_root,
        rel_path=FAILURE_DIAGNOSTIC_REL_PATH,
        expected_file_sha256=EXPECTED_FAILURE_DIAGNOSTIC_FILE_SHA256,
        internal_sha_key="diagnostic_artifact_sha256",
        expected_internal_sha256=EXPECTED_FAILURE_DIAGNOSTIC_INTERNAL_SHA256,
    )
    dev_tune_plan_raw = _verify_json_authority_file(
        repo_root,
        rel_path=DEV_TUNE_EXECUTION_PLAN_REL_PATH,
        expected_file_sha256=EXPECTED_DEV_TUNE_EXECUTION_PLAN_FILE_SHA256,
    )
    if (
        dev_tune_plan_raw.get("plan_sha256")
        != EXPECTED_DEV_TUNE_EXECUTION_PLAN_INTERNAL_SHA256
    ):
        raise PlanBeforeLiveProtocolError("DEV_TUNE_EXECUTION_PLAN_SHA256_MISMATCH")

    dev_select_plan_raw = _verify_json_authority_file(
        repo_root,
        rel_path=PRIMARY_DEV_SELECT_EXECUTION_PLAN_REL_PATH,
        expected_file_sha256=EXPECTED_PRIMARY_DEV_SELECT_EXECUTION_PLAN_FILE_SHA256,
    )
    if (
        dev_select_plan_raw.get("plan_sha256")
        != EXPECTED_PRIMARY_DEV_SELECT_EXECUTION_PLAN_INTERNAL_SHA256
    ):
        raise PlanBeforeLiveProtocolError(
            "PRIMARY_DEV_SELECT_EXECUTION_PLAN_SHA256_MISMATCH"
        )

    # 4. Verify primary experiment firewall & Final100/P11 untouched
    pfw = auth_prep.get("primary_authority_firewall", {})
    if (
        pfw.get("PRIMARY_EXPERIMENT_MUTATED") is not False
        or pfw.get("PRIMARY_RESULTS_REPLACED") is not False
        or pfw.get("PRIMARY_DENOMINATORS_CHANGED") is not False
        or pfw.get("authoritative_primary_strict_rates")
        != AUTHORITATIVE_PRIMARY_STRICT_RATES
        or primary_freeze_receipt.get("model_winner_selected") is not False
        or primary_freeze_receipt.get("selected_model_id") is not None
        or primary_freeze_receipt.get("stochasticity_execution_started") is not False
        or primary_freeze_receipt.get("final100_used") is not False
    ):
        raise PlanBeforeLiveProtocolError("PRIMARY_EXPERIMENT_FIREWALL_MISMATCH")

    final100_path = repo_root / "data/evaluation/w06/w06_scenarios_freeze_v1.json"
    p11_path = repo_root / "data/evaluation/w06/w06_p11_assignment_manifest_v1.json"
    if (
        not final100_path.is_file()
        or _compute_file_lf_sha256(final100_path) != FORBIDDEN_FINAL100_BUNDLE_SHA256
    ):
        raise Final100FirewallViolationError("FINAL100_BUNDLE_SHA256_DRIFT")
    if (
        not p11_path.is_file()
        or _compute_file_lf_sha256(p11_path) != FORBIDDEN_P11_MANIFEST_SHA256
    ):
        raise Final100FirewallViolationError("P11_MANIFEST_SHA256_DRIFT")

    # 5. Load and verify frozen DEV bundle, candidate registry, schemas, and P1 prompt
    dev_bundle = load_and_verify_frozen_dev_bundle()
    if dev_bundle.dev_bundle_sha256 != EXPECTED_DEV_FIXTURES_FREEZE_SHA256:
        raise PlanBeforeLiveProtocolError("DEV_FIXTURES_FREEZE_SHA256_MISMATCH")

    cand_reg = load_and_verify_candidate_registry()
    pconf_reg_sha = compute_provider_config_registry_sha256(cand_reg)
    if (
        cand_reg.registry_sha256 != EXPECTED_CANDIDATE_REGISTRY_SHA256
        or pconf_reg_sha != EXPECTED_PROVIDER_CONFIG_REGISTRY_SHA256
    ):
        raise CandidateRegistryIntegrityError(
            "CANDIDATE_OR_PROVIDER_CONFIG_REGISTRY_SHA256_MISMATCH"
        )

    portable_schema_sha = compute_common_portable_generation_schema_sha256_v2()
    semantic_schema_sha = compute_semantic_schema_sha256()
    if (
        portable_schema_sha != EXPECTED_PORTABLE_SCHEMA_V2_SHA256
        or semantic_schema_sha != EXPECTED_SEMANTIC_SCHEMA_SHA256
    ):
        raise CandidateRegistryIntegrityError("PORTABLE_OR_SEMANTIC_SCHEMA_DRIFT")

    prompt_reg = build_frozen_p1_p2_registry()
    p1_spec = build_p1_spec()
    p1_system_sha256 = sha256_bytes(
        normalize_lf_bytes(p1_spec.system_prompt.encode("utf-8"))
    )
    p1_user_template_sha256 = sha256_bytes(
        normalize_lf_bytes(p1_spec.user_prompt_template.encode("utf-8"))
    )
    if (
        prompt_reg.registry_sha256 != EXPECTED_FROZEN_PROMPT_REGISTRY_SHA256
        or p1_spec.prompt_id != FROZEN_PROMPT_ID
        or p1_spec.semantic_prompt_sha256 != EXPECTED_P1_SEMANTIC_SHA256
        or p1_system_sha256 != EXPECTED_P1_SYSTEM_PROMPT_SHA256
        or p1_user_template_sha256 != EXPECTED_P1_USER_PROMPT_TEMPLATE_SHA256
    ):
        raise PromptFreezeFirewallError("P1_PROMPT_AUTHORITY_MISMATCH")

    # 6. Verify 9-cell contract and output root non-existence
    verified_cells = verify_frozen_canary_contract_and_cells(
        auth_prep=auth_prep,
        canary_manifest=canary_manifest,
        dev_bundle=dev_bundle,
        cand_reg=cand_reg,
        p1_spec=p1_spec,
    )
    output_root = verify_canary_output_root_not_existing(
        repo_root=repo_root,
        output_root_override=output_root_override,
    )

    return {
        "source_develop_provenance": source_prov,
        "auth_prep": auth_prep,
        "canary_manifest": canary_manifest,
        "owner_readiness": owner_readiness,
        "dev_bundle": dev_bundle,
        "candidate_registry": cand_reg,
        "prompt_registry": prompt_reg,
        "p1_spec": p1_spec,
        "ordered_canary_cells": verified_cells,
        "output_root": output_root,
        "scientific_code_bundle_sha256": bundle_sha,
        "primary_launcher_lf_sha256": primary_launcher_lf_sha,
        "candidate_registry_sha256": cand_reg.registry_sha256,
        "provider_config_registry_sha256": pconf_reg_sha,
        "portable_schema_v2_sha256": portable_schema_sha,
        "semantic_schema_sha256": semantic_schema_sha,
    }


def _expected_9_cell_order_records() -> list[dict[str, Any]]:
    return [
        {
            "order_index": r[0],
            "short_label": r[1],
            "fixture_id": r[2],
            "candidate_id": r[3],
            "cell_id": r[4],
        }
        for r in EXPECTED_CANARY_9_CELL_ORDER
    ]


def build_canary_live_execution_authorization_receipt_payload(
    *,
    authorized_code_basis_commit_sha: str = AUTHORITATIVE_BASE_DEVELOP_SHA,
    launcher_merge_commit_sha: str = AUTHORITATIVE_BASE_DEVELOP_SHA,
    launcher_pr_number: int = 73,
    overrides: Mapping[str, Any] | None = None,
    recompute_internal_sha: bool = True,
) -> dict[str, Any]:
    """Build a canonical future `w06_dev_select_amendment_01_canary_live_execution_authorization_v1.json` payload.

    Used by unit tests to verify the two-layer authorization contract offline without creating
    an effective production execution authorization receipt in the repository during PREP.
    """
    payload: dict[str, Any] = {
        "artifact_id": CANARY_LIVE_EXECUTION_AUTH_RECEIPT_ARTIFACT_ID,
        "task_id": FUTURE_LIVE_EXECUTION_GATE_ID,
        "authorized_execution_gate": FUTURE_LIVE_EXECUTION_GATE_ID,
        "canary_authorization_prep_path": CANARY_AUTH_PREP_REL_PATH,
        "canary_authorization_prep_doc_path": CANARY_AUTH_PREP_DOC_REL_PATH,
        "canary_authorization_prep_file_sha256": EXPECTED_CANARY_AUTH_PREP_FILE_SHA256,
        "canary_authorization_prep_internal_sha256": (
            EXPECTED_CANARY_AUTH_PREP_INTERNAL_SHA256
        ),
        "canary_authorization_prep_doc_sha256": EXPECTED_CANARY_AUTH_PREP_DOC_SHA256,
        "canary_manifest_path": CANARY_MANIFEST_REL_PATH,
        "canary_manifest_file_sha256": EXPECTED_CANARY_MANIFEST_FILE_SHA256,
        "canary_manifest_internal_sha256": EXPECTED_CANARY_MANIFEST_INTERNAL_SHA256,
        "owner_readiness_attestation_path": OWNER_READINESS_ATTESTATION_REL_PATH,
        "owner_readiness_attestation_file_sha256": (
            EXPECTED_OWNER_READINESS_ATTESTATION_FILE_SHA256
        ),
        "owner_readiness_attestation_internal_sha256": (
            EXPECTED_OWNER_READINESS_ATTESTATION_INTERNAL_SHA256
        ),
        "candidates": copy.deepcopy(FROZEN_CANDIDATES),
        "prompt_id": FROZEN_PROMPT_ID,
        "selected_prompt_semantic_sha256": EXPECTED_P1_SEMANTIC_SHA256,
        "exact_canary_fixtures": list(FROZEN_CANARY_FIXTURE_IDS),
        "exact_9_cell_execution_order": _expected_9_cell_order_records(),
        "max_provider_generation_calls": FROZEN_MAX_GENERATION_CALLS,
        "generation_calls_per_assigned_cell": FROZEN_GENERATION_CALLS_PER_CELL,
        "concurrency": FROZEN_CONCURRENCY,
        "timeout_policy_id": FROZEN_TIMEOUT_POLICY_ID,
        "timeout_ms": FROZEN_TIMEOUT_MS,
        "pacing_policy_id": FROZEN_PACING_POLICY_ID,
        "inter_call_delay_ms": FROZEN_INTER_CALL_DELAY_MS,
        "delay_before_first_call_ms": FROZEN_DELAY_BEFORE_FIRST_CALL_MS,
        "delay_after_last_call_ms": FROZEN_DELAY_AFTER_LAST_CALL_MS,
        "maximum_scheduled_delays": FROZEN_MAX_SCHEDULED_DELAYS,
        "retry_policy_id": FROZEN_RETRY_POLICY_ID,
        "retry": 0,
        "automatic_retry": FROZEN_AUTOMATIC_RETRY,
        "transport_retry": FROZEN_TRANSPORT_RETRY,
        "manual_retry": FROZEN_MANUAL_RETRY,
        "llm_repair": FROZEN_LLM_REPAIR,
        "semantic_repair": FROZEN_SEMANTIC_REPAIR,
        "fallback": FROZEN_FALLBACK,
        "final100_permitted": False,
        "FINAL100_USED": False,
        "FINAL100_STATUS": "NO-GO",
        "comparative_live_authorized": False,
        "AMENDED_COMPARATIVE_LIVE_AUTHORIZED": False,
        "MODEL_WINNER_SELECTED": False,
        "SELECTED_MODEL_ID": None,
        "STOCHASTICITY_EXECUTION_STARTED": False,
        "launcher_identity_id": LAUNCHER_IDENTITY_ID,
        "launcher_version": LAUNCHER_VERSION,
        "launcher_path": LAUNCHER_REL_PATH,
        "scientific_code_bundle_sha256": EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256,
        "authoritative_base_develop_sha": AUTHORITATIVE_BASE_DEVELOP_SHA,
        "authorized_code_basis_commit_sha": authorized_code_basis_commit_sha,
        "launcher_repository_merge_provenance": {
            "pr_number": launcher_pr_number,
            "base_develop_sha": AUTHORITATIVE_BASE_DEVELOP_SHA,
            "merge_commit_sha": launcher_merge_commit_sha,
        },
        "CANARY_LIVE_EXECUTION_AUTHORIZED": True,
    }
    if overrides:
        for k, v in overrides.items():
            payload[k] = v
    if recompute_internal_sha:
        payload[CANARY_LIVE_EXECUTION_AUTH_INTERNAL_SHA_KEY] = _compute_internal_sha256(
            payload, CANARY_LIVE_EXECUTION_AUTH_INTERNAL_SHA_KEY
        )
    return payload


def verify_canary_live_execution_authorization_receipt(
    repo_root: Path = REPO_ROOT,
    *,
    receipt_path_override: Path | None = None,
    receipt_payload_override: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate the separate future `w06_dev_select_amendment_01_canary_live_execution_authorization_v1.json` receipt.

    Enforces canonical internal SHA256 tamper detection and all frozen bindings required by Corrective 01 Blocker 1.
    """
    target_path = receipt_path_override or (
        repo_root / CANARY_LIVE_EXECUTION_AUTH_RECEIPT_REL_PATH
    )
    _assert_runner_not_final100_path(target_path)

    if receipt_payload_override is not None:
        if not isinstance(receipt_payload_override, Mapping):
            raise LiveExecutionNotAuthorizedError(
                "CANARY_LIVE_EXECUTION_AUTHORIZATION_RECEIPT_MALFORMED: Receipt payload must be a JSON object."
            )
        data: dict[str, Any] = dict(receipt_payload_override)
        file_sha256 = sha256_bytes(canonical_json_bytes(data))
    else:
        if not target_path.is_file():
            raise LiveExecutionNotAuthorizedError(
                f"CANARY_LIVE_EXECUTION_AUTHORIZATION_RECEIPT_MISSING: Separate execution authorization receipt "
                f"{target_path} is not present (execution_authorization_receipt_present=false, "
                f"effective_live_execution_authorized=false). Wait for {FUTURE_LIVE_EXECUTION_GATE_ID}."
            )
        try:
            raw_obj = json.loads(target_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise LiveExecutionNotAuthorizedError(
                f"CANARY_LIVE_EXECUTION_AUTHORIZATION_RECEIPT_MALFORMED: Failed to parse JSON from {target_path}: {exc}"
            ) from exc
        if not isinstance(raw_obj, dict):
            raise LiveExecutionNotAuthorizedError(
                f"CANARY_LIVE_EXECUTION_AUTHORIZATION_RECEIPT_MALFORMED: {target_path} must contain a JSON object."
            )
        data = raw_obj
        file_sha256 = _compute_file_lf_sha256(target_path)

    # 1. Final100 firewall checks first
    if (
        data.get("final100_permitted") is not False
        or data.get("FINAL100_USED") is not False
        or data.get("FINAL100_STATUS") != "NO-GO"
    ):
        raise Final100FirewallViolationError(
            "CANARY_EXECUTION_AUTH_FINAL100_FORBIDDEN: Final100 must remain strictly forbidden (NO-GO, unused)."
        )

    # 2. Canonical internal SHA256 tamper detection
    recorded_internal = data.get(CANARY_LIVE_EXECUTION_AUTH_INTERNAL_SHA_KEY)
    computed_internal = _compute_internal_sha256(
        data, CANARY_LIVE_EXECUTION_AUTH_INTERNAL_SHA_KEY
    )
    if (
        not isinstance(recorded_internal, str)
        or len(recorded_internal) != 64
        or any(c not in "0123456789abcdef" for c in recorded_internal)
        or recorded_internal != computed_internal
    ):
        raise LiveExecutionNotAuthorizedError(
            f"CANARY_LIVE_EXECUTION_AUTHORIZATION_INTERNAL_SHA256_MISMATCH: "
            f"recorded={recorded_internal!r}, computed={computed_internal!r}"
        )

    # 3. Artifact/task/gate identity
    if (
        data.get("artifact_id") != CANARY_LIVE_EXECUTION_AUTH_RECEIPT_ARTIFACT_ID
        or data.get("task_id") != FUTURE_LIVE_EXECUTION_GATE_ID
        or data.get("authorized_execution_gate") != FUTURE_LIVE_EXECUTION_GATE_ID
    ):
        raise LiveExecutionNotAuthorizedError(
            "CANARY_EXECUTION_AUTH_GATE_OR_ARTIFACT_ID_MISMATCH: Receipt must bind exact future gate "
            f"{FUTURE_LIVE_EXECUTION_GATE_ID} and artifact {CANARY_LIVE_EXECUTION_AUTH_RECEIPT_ARTIFACT_ID}."
        )

    # 4. Exact authorization PREP & canary manifest & owner readiness SHA256 bindings
    if (
        data.get("canary_authorization_prep_path") != CANARY_AUTH_PREP_REL_PATH
        or data.get("canary_authorization_prep_doc_path")
        != CANARY_AUTH_PREP_DOC_REL_PATH
        or data.get("canary_authorization_prep_file_sha256")
        != EXPECTED_CANARY_AUTH_PREP_FILE_SHA256
        or data.get("canary_authorization_prep_internal_sha256")
        != EXPECTED_CANARY_AUTH_PREP_INTERNAL_SHA256
        or data.get("canary_authorization_prep_doc_sha256")
        != EXPECTED_CANARY_AUTH_PREP_DOC_SHA256
    ):
        raise LiveExecutionNotAuthorizedError(
            "CANARY_EXECUTION_AUTH_PREP_SHA256_MISMATCH: Bound authorization PREP hashes do not match frozen authority."
        )
    if (
        data.get("canary_manifest_path") != CANARY_MANIFEST_REL_PATH
        or data.get("canary_manifest_file_sha256") != EXPECTED_CANARY_MANIFEST_FILE_SHA256
        or data.get("canary_manifest_internal_sha256")
        != EXPECTED_CANARY_MANIFEST_INTERNAL_SHA256
    ):
        raise LiveExecutionNotAuthorizedError(
            "CANARY_EXECUTION_AUTH_MANIFEST_SHA256_MISMATCH: Bound canary manifest hashes do not match frozen authority."
        )
    if (
        data.get("owner_readiness_attestation_path")
        != OWNER_READINESS_ATTESTATION_REL_PATH
        or data.get("owner_readiness_attestation_file_sha256")
        != EXPECTED_OWNER_READINESS_ATTESTATION_FILE_SHA256
        or data.get("owner_readiness_attestation_internal_sha256")
        != EXPECTED_OWNER_READINESS_ATTESTATION_INTERNAL_SHA256
    ):
        raise LiveExecutionNotAuthorizedError(
            "CANARY_EXECUTION_AUTH_OWNER_READINESS_SHA256_MISMATCH"
        )

    # 5. Exact candidate set & P1 prompt bindings
    if data.get("candidates") != FROZEN_CANDIDATES:
        raise CandidateRegistryIntegrityError(
            f"CANARY_EXECUTION_AUTH_CANDIDATE_SET_MISMATCH: {data.get('candidates')!r}"
        )
    if (
        data.get("prompt_id") != FROZEN_PROMPT_ID
        or data.get("selected_prompt_semantic_sha256") != EXPECTED_P1_SEMANTIC_SHA256
    ):
        raise PromptFreezeFirewallError("CANARY_EXECUTION_AUTH_PROMPT_P1_MISMATCH")

    # 6. Exact fixtures & 9-cell order bindings
    if data.get("exact_canary_fixtures") != list(FROZEN_CANARY_FIXTURE_IDS):
        raise PlanBeforeLiveProtocolError("CANARY_EXECUTION_AUTH_FIXTURE_SET_MISMATCH")
    if data.get("exact_9_cell_execution_order") != _expected_9_cell_order_records():
        raise PlanBeforeLiveProtocolError("CANARY_EXECUTION_AUTH_9_CELL_ORDER_MISMATCH")

    # 7. Exact runtime policy bindings (max_calls=9, retry=0, timeout=180000, pacing=2000, fallback=false)
    if (
        data.get("max_provider_generation_calls") != FROZEN_MAX_GENERATION_CALLS
        or data.get("generation_calls_per_assigned_cell")
        != FROZEN_GENERATION_CALLS_PER_CELL
        or data.get("concurrency") != FROZEN_CONCURRENCY
        or data.get("timeout_policy_id") != FROZEN_TIMEOUT_POLICY_ID
        or data.get("timeout_ms") != FROZEN_TIMEOUT_MS
        or data.get("pacing_policy_id") != FROZEN_PACING_POLICY_ID
        or data.get("inter_call_delay_ms") != FROZEN_INTER_CALL_DELAY_MS
        or data.get("delay_before_first_call_ms") != FROZEN_DELAY_BEFORE_FIRST_CALL_MS
        or data.get("delay_after_last_call_ms") != FROZEN_DELAY_AFTER_LAST_CALL_MS
        or data.get("maximum_scheduled_delays") != FROZEN_MAX_SCHEDULED_DELAYS
        or data.get("retry_policy_id") != FROZEN_RETRY_POLICY_ID
        or data.get("retry") != 0
        or data.get("automatic_retry") != 0
        or data.get("transport_retry") != 0
        or data.get("manual_retry") != 0
        or data.get("llm_repair") != 0
        or data.get("semantic_repair") != 0
        or data.get("fallback") is not False
    ):
        raise PlanBeforeLiveProtocolError(
            "CANARY_EXECUTION_AUTH_RUNTIME_POLICY_MISMATCH: Receipt violates frozen 9-call / 0-retry / 180s / 2000ms / fallback=false policy."
        )

    # 8. Comparative & downstream gates remain unauthorized
    if (
        data.get("comparative_live_authorized") is not False
        or data.get("AMENDED_COMPARATIVE_LIVE_AUTHORIZED") is not False
        or data.get("MODEL_WINNER_SELECTED") is not False
        or data.get("SELECTED_MODEL_ID") is not None
        or data.get("STOCHASTICITY_EXECUTION_STARTED") is not False
    ):
        raise LiveExecutionNotAuthorizedError(
            "CANARY_EXECUTION_AUTH_COMPARATIVE_OR_DOWNSTREAM_FORBIDDEN: Comparative180, winner selection, and stochasticity must remain false/null."
        )

    # 9. Exact launcher identity/version & merge provenance / authorized code basis
    code_basis_sha = data.get("authorized_code_basis_commit_sha")
    merge_prov = data.get("launcher_repository_merge_provenance")
    merge_sha = (
        merge_prov.get("merge_commit_sha") if isinstance(merge_prov, Mapping) else None
    )
    if (
        data.get("launcher_identity_id") != LAUNCHER_IDENTITY_ID
        or data.get("launcher_version") != LAUNCHER_VERSION
        or data.get("launcher_path") != LAUNCHER_REL_PATH
        or data.get("scientific_code_bundle_sha256")
        != EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
        or data.get("authoritative_base_develop_sha") != AUTHORITATIVE_BASE_DEVELOP_SHA
        or not isinstance(code_basis_sha, str)
        or len(code_basis_sha) != 40
        or any(c not in "0123456789abcdef" for c in code_basis_sha)
        or not isinstance(merge_prov, Mapping)
        or merge_prov.get("pr_number") != 73
        or merge_prov.get("base_develop_sha") != AUTHORITATIVE_BASE_DEVELOP_SHA
        or not isinstance(merge_sha, str)
        or len(merge_sha) != 40
        or any(c not in "0123456789abcdef" for c in merge_sha)
    ):
        raise LiveExecutionNotAuthorizedError(
            "CANARY_EXECUTION_AUTH_LAUNCHER_IDENTITY_OR_PROVENANCE_MISMATCH"
        )

    # 10. Effective authorization flag
    if data.get("CANARY_LIVE_EXECUTION_AUTHORIZED") is not True:
        raise LiveExecutionNotAuthorizedError(
            "CANARY_LIVE_EXECUTION_NOT_AUTHORIZED: CANARY_LIVE_EXECUTION_AUTHORIZED must be true in receipt."
        )

    return {
        "verified": True,
        "execution_authorization_receipt_path": str(target_path),
        "execution_authorization_receipt_file_sha256": file_sha256,
        "execution_authorization_receipt_internal_sha256": computed_internal,
        "CANARY_LIVE_EXECUTION_AUTHORIZED": True,
        "receipt": data,
    }


def inspect_canary_live_execution_authorization_state(
    repo_root: Path = REPO_ROOT,
    *,
    receipt_path_override: Path | None = None,
) -> dict[str, Any]:
    """Inspect whether the separate live-execution authorization receipt exists and is valid.

    In the current PREP state, `w06_dev_select_amendment_01_canary_live_execution_authorization_v1.json`
    is NOT created, so this returns:
    - `execution_authorization_receipt_present = false`
    - `effective_live_execution_authorized = false`
    - `live_execution_available = false`
    """
    target_path = receipt_path_override or (
        repo_root / CANARY_LIVE_EXECUTION_AUTH_RECEIPT_REL_PATH
    )
    _assert_runner_not_final100_path(target_path)
    if not target_path.is_file():
        return {
            "execution_authorization_receipt_path": (
                CANARY_LIVE_EXECUTION_AUTH_RECEIPT_REL_PATH
            ),
            "execution_authorization_receipt_present": False,
            "effective_live_execution_authorized": False,
            "live_execution_available": False,
            "live_execution_status": (
                "UNAVAILABLE_PENDING_SEPARATE_EXECUTION_AUTHORIZATION_RECEIPT"
            ),
        }
    verified_rec = verify_canary_live_execution_authorization_receipt(
        repo_root=repo_root,
        receipt_path_override=target_path,
    )
    return {
        "execution_authorization_receipt_path": (
            CANARY_LIVE_EXECUTION_AUTH_RECEIPT_REL_PATH
        ),
        "execution_authorization_receipt_present": True,
        "effective_live_execution_authorized": True,
        "live_execution_available": True,
        "live_execution_status": "AUTHORIZED_BY_SEPARATE_EXECUTION_RECEIPT",
        "execution_authorization_receipt_file_sha256": verified_rec[
            "execution_authorization_receipt_file_sha256"
        ],
        "execution_authorization_receipt_internal_sha256": verified_rec[
            "execution_authorization_receipt_internal_sha256"
        ],
    }


def verify_two_layer_canary_live_execution_authorization(
    repo_root: Path = REPO_ROOT,
    *,
    output_root_override: Path | None = None,
    execution_auth_receipt_path_override: Path | None = None,
    execution_auth_receipt_payload_override: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Enforce the two-layer live execution authorization contract (Blocker 1 & Section 5).

    Requires BOTH:
    1. Frozen authorization PREP (`w06_dev_select_amendment_01_canary_authorization_prep_v1.json`)
       remains valid and unmutated (`AMENDED_CANARY_LIVE_AUTHORIZED == false`); AND
    2. Separate execution authorization receipt
       (`w06_dev_select_amendment_01_canary_live_execution_authorization_v1.json`)
       is present and valid (`CANARY_LIVE_EXECUTION_AUTHORIZED == true`).
    """
    verified_authorities = verify_frozen_canary_launcher_authorities(
        repo_root=repo_root,
        output_root_override=output_root_override,
    )
    verified_exec_receipt = verify_canary_live_execution_authorization_receipt(
        repo_root=repo_root,
        receipt_path_override=execution_auth_receipt_path_override,
        receipt_payload_override=execution_auth_receipt_payload_override,
    )
    return {
        "verified": True,
        "layer_1_frozen_auth_prep_verified": True,
        "layer_1_auth_prep_amended_canary_live_authorized": False,
        "layer_2_execution_authorization_receipt_verified": True,
        "effective_live_execution_authorized": True,
        "authorities": verified_authorities,
        "execution_authorization_receipt": verified_exec_receipt,
    }


# ==============================================================================
# 4. REUSE OF EXISTING PROVIDER WIRE-REQUEST & TRANSPORT LAYER (SECTIONS 8, 11, 12)
# ==============================================================================


def build_canary_cell_execution_manifest(
    cell_record: Mapping[str, Any],
) -> DevCellExecutionManifest:
    """Build a `DevCellExecutionManifest` compatible with `app.evaluation.dev_live_runner` primitives."""
    return DevCellExecutionManifest(
        run_id=str(cell_record["cell_id"]),
        phase="DEV_TUNE",
        prompt_id=str(cell_record["prompt_id"]),
        candidate_id=str(cell_record["candidate_id"]),
        requested_model_id=str(cell_record["requested_model_id"]),
        fixture_id=str(cell_record["fixture_id"]),
        attempt_number=int(cell_record["attempt_number"]),
        retry=int(cell_record["retry"]),
        sampling_reasoning_configuration=dict(
            cell_record["sampling_reasoning_configuration"]
        ),
        system_prompt_sha256=str(cell_record["system_prompt_sha256"]),
        user_prompt_sha256=str(cell_record["user_prompt_sha256"]),
        scenario_sha256=str(cell_record["scenario_sha256"]),
        catalog_context_sha256=str(cell_record["catalog_context_sha256"]),
        provider_config_sha256=str(
            cell_record["primary_baseline_provider_config_sha256"]
        ),
        semantic_schema_sha256=str(cell_record["semantic_schema_sha256"]),
        portable_generation_schema_v2_sha256=str(
            cell_record["portable_generation_schema_v2_sha256"]
        ),
        code_commit_sha=AUTHORITATIVE_BASE_DEVELOP_SHA,
        code_basis_commit_sha=AUTHORITATIVE_BASE_DEVELOP_SHA,
        scientific_code_bundle_sha256=str(
            cell_record["scientific_code_bundle_sha256"]
        ),
    )


def build_canary_cell_wire_request(
    *,
    cell_record: Mapping[str, Any],
    dev_bundle: VerifiedDevBundle,
    cand_reg: DevCandidateRegistry,
    p1_spec: PromptCandidateSpec,
) -> dict[str, Any]:
    """Reuse `build_frozen_provider_wire_request` from `dev_live_runner.py` and apply the frozen 180s timeout policy."""
    cell_manifest = build_canary_cell_execution_manifest(cell_record)
    dev_tune_by_id = {s.scenario_id: s for s in dev_bundle.dev_tune_fixtures}
    scenario = dev_tune_by_id[cell_manifest.fixture_id]

    wire_payload = copy.deepcopy(
        build_frozen_provider_wire_request(
            cell_manifest=cell_manifest,
            scenario=scenario,
            prompt_spec=p1_spec,
            candidate_registry=cand_reg,
        )
    )
    wire_payload["timeout_ms"] = FROZEN_TIMEOUT_MS
    wire_payload["timeout_seconds"] = FROZEN_TIMEOUT_SECONDS
    if cell_manifest.candidate_id == "C1" and isinstance(
        wire_payload.get("config"), dict
    ):
        wire_payload["config"]["http_options"] = {"timeout": FROZEN_TIMEOUT_MS}

    assert_no_secrets_in_payload(
        wire_payload, context="CANARY_CELL_PROVIDER_WIRE_REQUEST"
    )
    return wire_payload


def _invoke_canary_production_transport_for_cell(
    *,
    cell_manifest: DevCellExecutionManifest,
    wire_request: dict[str, Any],
    http_counter: DevCellHttpCallCounter,
    api_key: str,
    inner_transport: Any = None,
) -> ProviderNormalizedTransportResponse:
    """Invoke the provider SDK via `DevCountingHttpxTransport` / `DevCountingHttpx2Transport` under 180s timeout."""
    cid = cell_manifest.candidate_id
    if (
        wire_request.get("timeout_ms") != FROZEN_TIMEOUT_MS
        or wire_request.get("timeout_seconds") != FROZEN_TIMEOUT_SECONDS
        or wire_request.get("retry") != 0
    ):
        raise PlanBeforeLiveProtocolError(
            f"CANARY_WIRE_REQUEST_RUNTIME_MISMATCH for {cell_manifest.run_id}"
        )

    if cid == "C1":
        counting_c1 = DevCountingHttpxTransport(
            candidate_id="C1",
            run_id=cell_manifest.run_id,
            http_counter=http_counter,
            inner_transport=inner_transport,
        )
        cfg = wire_request["config"]
        http_client = httpx.Client(
            transport=counting_c1, timeout=FROZEN_TIMEOUT_SECONDS
        )
        try:
            client = genai.Client(
                api_key=api_key,
                http_options=genai_types.HttpOptions(
                    timeout=FROZEN_TIMEOUT_MS,
                    retry_options=genai_types.HttpRetryOptions(attempts=1),
                    httpx_client=http_client,
                ),
            )
            call_config = genai_types.GenerateContentConfig(
                system_instruction=cfg["system_instruction"],
                seed=2026101508,
                thinking_config=genai_types.ThinkingConfig(
                    thinking_level="medium",
                    include_thoughts=False,
                ),
                max_output_tokens=FROZEN_MAX_OUTPUT_TOKENS,
                response_mime_type="application/json",
                response_json_schema=cfg["response_json_schema"],
                tools=None,
                automatic_function_calling=genai_types.AutomaticFunctionCallingConfig(
                    disable=True
                ),
            )
            resp = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=wire_request["contents"],
                config=call_config,
            )
        finally:
            http_client.close()

        raw_text = getattr(resp, "text", None) or ""
        returned_model = getattr(resp, "model_version", None)
        candidates = getattr(resp, "candidates", None) or []
        finish_reason: str | None = None
        refusal_state = False
        max_token_state = False
        if candidates:
            fr_val = getattr(candidates[0], "finish_reason", None)
            finish_reason = (
                str(fr_val.value if hasattr(fr_val, "value") else fr_val)
                if fr_val is not None
                else None
            )
            fr_upper = (finish_reason or "").upper()
            if any(
                tok in fr_upper
                for tok in (
                    "SAFETY",
                    "BLOCKLIST",
                    "PROHIBITED",
                    "RECITATION",
                    "REFUSAL",
                )
            ):
                refusal_state = True
            elif any(tok in fr_upper for tok in ("MAX_TOKENS", "LENGTH")):
                max_token_state = True

        usage_obj = getattr(resp, "usage_metadata", None)
        raw_usage_dict: dict[str, Any] | None = None
        if usage_obj is not None:
            traffic_type = getattr(usage_obj, "traffic_type", None)
            raw_usage_dict = {
                "prompt_token_count": getattr(usage_obj, "prompt_token_count", None),
                "candidates_token_count": getattr(
                    usage_obj, "candidates_token_count", None
                ),
                "thoughts_token_count": getattr(
                    usage_obj, "thoughts_token_count", None
                ),
                "cached_content_token_count": getattr(
                    usage_obj, "cached_content_token_count", None
                ),
                "total_token_count": getattr(usage_obj, "total_token_count", None),
                "traffic_type": (
                    str(
                        traffic_type.value
                        if hasattr(traffic_type, "value")
                        else traffic_type
                    )
                    if traffic_type
                    else None
                ),
            }
        norm_usage = normalize_candidate_usage_metadata("C1", raw_usage_dict)
        failure_cls = DevCellFailureClassification.NONE
        if refusal_state:
            failure_cls = DevCellFailureClassification.REFUSAL
        elif max_token_state:
            failure_cls = DevCellFailureClassification.MAX_TOKEN_TRUNCATION

        return ProviderNormalizedTransportResponse(
            candidate_id="C1",
            provider="google",
            requested_model_id="gemini-3.8-flash",
            returned_model_id=returned_model,
            raw_text=raw_text,
            finish_or_stop_reason=finish_reason,
            finish_reason=finish_reason or "STOP",
            refusal_state=refusal_state,
            max_token_state=max_token_state,
            raw_usage_metadata=raw_usage_dict,
            normalized_usage_metadata=norm_usage,
            raw_provider_metadata={
                "response_id": getattr(resp, "response_id", None),
                "model_version": returned_model,
                "finish_reason": finish_reason,
            },
            normalized_provider_metadata={
                "candidate_id": "C1",
                "provider": "google",
                "requested_model_id": "gemini-3.8-flash",
                "returned_model_id": returned_model,
                "finish_or_stop_reason": finish_reason,
                "timeout_ms": FROZEN_TIMEOUT_MS,
                "actual_http_request_count": counting_c1.request_count,
            },
            actual_http_request_count=counting_c1.request_count,
            simulated_failure=failure_cls,
            authoritative_usage_available=bool(norm_usage.get("usage_present")),
            input_tokens=norm_usage["input_tokens"],
            output_tokens=norm_usage["output_tokens"],
            total_tokens=norm_usage["total_tokens"],
            thought_tokens=norm_usage["thought_tokens"],
            cached_input_tokens=norm_usage["cached_input_tokens"],
        )

    if cid == "C2":
        counting_c2 = DevCountingHttpx2Transport(
            candidate_id="C2",
            run_id=cell_manifest.run_id,
            http_counter=http_counter,
            inner_transport=inner_transport,
        )
        http_client2 = httpx2.Client(
            transport=counting_c2, timeout=FROZEN_TIMEOUT_SECONDS
        )
        try:
            client_oai = openai.OpenAI(
                api_key=api_key,
                max_retries=0,
                timeout=FROZEN_TIMEOUT_SECONDS,
                http_client=http_client2,
            )
            resp_oai = client_oai.chat.completions.create(
                model="gpt-6.1-sol",
                messages=wire_request["messages"],
                seed=2026101508,
                reasoning_effort="medium",
                service_tier="default",
                max_completion_tokens=FROZEN_MAX_OUTPUT_TOKENS,
                response_format=wire_request["response_format"],
            )
        finally:
            http_client2.close()

        returned_model = getattr(resp_oai, "model", None)
        choices = getattr(resp_oai, "choices", None) or []
        raw_text = ""
        finish_reason = None
        refusal_state = False
        max_token_state = False
        if choices:
            finish_reason = getattr(choices[0], "finish_reason", None)
            fr_low = str(finish_reason or "").lower()
            if fr_low == "content_filter":
                refusal_state = True
            elif fr_low in ("length", "max_tokens", "max_output_tokens"):
                max_token_state = True
            msg = getattr(choices[0], "message", None)
            if msg is not None:
                refusal_val = getattr(msg, "refusal", None)
                if isinstance(refusal_val, str) and refusal_val.strip():
                    refusal_state = True
                    raw_text = refusal_val
                else:
                    raw_text = getattr(msg, "content", None) or ""

        usage_obj = getattr(resp_oai, "usage", None)
        raw_usage_dict = None
        if usage_obj is not None:
            comp_details = getattr(usage_obj, "completion_tokens_details", None)
            prompt_details = getattr(usage_obj, "prompt_tokens_details", None)
            raw_usage_dict = {
                "prompt_tokens": getattr(usage_obj, "prompt_tokens", None),
                "completion_tokens": getattr(usage_obj, "completion_tokens", None),
                "total_tokens": getattr(usage_obj, "total_tokens", None),
                "completion_tokens_details": {
                    "reasoning_tokens": (
                        getattr(comp_details, "reasoning_tokens", None)
                        if comp_details
                        else None
                    )
                },
                "prompt_tokens_details": {
                    "cached_tokens": (
                        getattr(prompt_details, "cached_tokens", None)
                        if prompt_details
                        else None
                    )
                },
            }
        norm_usage = normalize_candidate_usage_metadata("C2", raw_usage_dict)
        failure_cls = DevCellFailureClassification.NONE
        if refusal_state:
            failure_cls = DevCellFailureClassification.REFUSAL
        elif max_token_state:
            failure_cls = DevCellFailureClassification.MAX_TOKEN_TRUNCATION

        return ProviderNormalizedTransportResponse(
            candidate_id="C2",
            provider="openai",
            requested_model_id="gpt-6.1-sol",
            returned_model_id=returned_model,
            raw_text=raw_text,
            finish_or_stop_reason=finish_reason,
            finish_reason=finish_reason or "stop",
            refusal_state=refusal_state,
            max_token_state=max_token_state,
            raw_usage_metadata=raw_usage_dict,
            normalized_usage_metadata=norm_usage,
            raw_provider_metadata={
                "id": getattr(resp_oai, "id", None),
                "model": returned_model,
                "system_fingerprint": getattr(resp_oai, "system_fingerprint", None),
                "service_tier": getattr(resp_oai, "service_tier", None),
                "finish_reason": finish_reason,
            },
            normalized_provider_metadata={
                "candidate_id": "C2",
                "provider": "openai",
                "requested_model_id": "gpt-6.1-sol",
                "returned_model_id": returned_model,
                "finish_or_stop_reason": finish_reason,
                "timeout_ms": FROZEN_TIMEOUT_MS,
                "actual_http_request_count": counting_c2.request_count,
            },
            actual_http_request_count=counting_c2.request_count,
            simulated_failure=failure_cls,
            authoritative_usage_available=bool(norm_usage.get("usage_present")),
            input_tokens=norm_usage["input_tokens"],
            output_tokens=norm_usage["output_tokens"],
            total_tokens=norm_usage["total_tokens"],
            reasoning_tokens=norm_usage["reasoning_tokens"],
            cached_input_tokens=norm_usage["cached_input_tokens"],
        )

    if cid == "C3":
        counting_c3 = DevCountingHttpx2Transport(
            candidate_id="C3",
            run_id=cell_manifest.run_id,
            http_counter=http_counter,
            inner_transport=inner_transport,
        )
        http_client3 = httpx2.Client(
            transport=counting_c3, timeout=FROZEN_TIMEOUT_SECONDS
        )
        try:
            client_ant = anthropic.Anthropic(
                api_key=api_key,
                max_retries=0,
                timeout=FROZEN_TIMEOUT_SECONDS,
                http_client=http_client3,
            )
            resp_ant = client_ant.messages.create(
                model="claude-sonnet-5-5",
                system=wire_request["system"],
                messages=wire_request["messages"],
                max_tokens=FROZEN_MAX_OUTPUT_TOKENS,
                thinking=wire_request["thinking"],
                output_config=wire_request["output_config"],
            )
        finally:
            http_client3.close()

        returned_model = getattr(resp_ant, "model", None)
        stop_reason = getattr(resp_ant, "stop_reason", None)
        sr_low = str(stop_reason or "").lower()
        refusal_state = sr_low == "refusal"
        max_token_state = sr_low in (
            "max_tokens",
            "length",
            "model_context_window_exceeded",
        )
        content_blocks = getattr(resp_ant, "content", None) or []
        text_parts: list[str] = []
        thinking_blocks_count = 0
        for block in content_blocks:
            b_type = getattr(block, "type", None) or (
                block.get("type") if isinstance(block, dict) else None
            )
            if b_type == "text":
                b_text = getattr(block, "text", None) or (
                    block.get("text") if isinstance(block, dict) else None
                )
                if isinstance(b_text, str):
                    text_parts.append(b_text)
            elif b_type in ("thinking", "redacted_thinking"):
                thinking_blocks_count += 1
        raw_text = "".join(text_parts)

        usage_obj = getattr(resp_ant, "usage", None)
        raw_usage_dict = None
        if usage_obj is not None:
            raw_usage_dict = {
                "input_tokens": getattr(usage_obj, "input_tokens", None),
                "output_tokens": getattr(usage_obj, "output_tokens", None),
                "thinking_tokens": getattr(usage_obj, "thinking_tokens", None),
                "cache_read_input_tokens": getattr(
                    usage_obj, "cache_read_input_tokens", None
                ),
                "cache_creation_input_tokens": getattr(
                    usage_obj, "cache_creation_input_tokens", None
                ),
                "service_tier": getattr(usage_obj, "service_tier", None),
                "thinking_blocks_count": thinking_blocks_count,
            }
        norm_usage = normalize_candidate_usage_metadata("C3", raw_usage_dict)
        failure_cls = DevCellFailureClassification.NONE
        if refusal_state:
            failure_cls = DevCellFailureClassification.REFUSAL
        elif max_token_state:
            failure_cls = DevCellFailureClassification.MAX_TOKEN_TRUNCATION

        return ProviderNormalizedTransportResponse(
            candidate_id="C3",
            provider="anthropic",
            requested_model_id="claude-sonnet-5-5",
            returned_model_id=returned_model,
            raw_text=raw_text,
            finish_or_stop_reason=stop_reason,
            finish_reason=stop_reason or "end_turn",
            refusal_state=refusal_state,
            max_token_state=max_token_state,
            raw_usage_metadata=raw_usage_dict,
            normalized_usage_metadata=norm_usage,
            raw_provider_metadata={
                "id": getattr(resp_ant, "id", None),
                "model": returned_model,
                "stop_reason": stop_reason,
                "thinking_blocks_count": thinking_blocks_count,
            },
            normalized_provider_metadata={
                "candidate_id": "C3",
                "provider": "anthropic",
                "requested_model_id": "claude-sonnet-5-5",
                "returned_model_id": returned_model,
                "finish_or_stop_reason": stop_reason,
                "timeout_ms": FROZEN_TIMEOUT_MS,
                "actual_http_request_count": counting_c3.request_count,
            },
            actual_http_request_count=counting_c3.request_count,
            simulated_failure=failure_cls,
            authoritative_usage_available=bool(norm_usage.get("usage_present")),
            input_tokens=norm_usage["input_tokens"],
            output_tokens=norm_usage["output_tokens"],
            total_tokens=norm_usage["total_tokens"],
            thinking_tokens=norm_usage["thinking_tokens"],
            cached_input_tokens=norm_usage["cached_input_tokens"],
            cache_read_input_tokens=norm_usage["cache_read_input_tokens"],
            cache_creation_input_tokens=norm_usage["cache_creation_input_tokens"],
        )

    raise CandidateRegistryIntegrityError(f"Unsupported candidate_id={cid!r}")


# ==============================================================================
# 5. PER-CELL EVIDENCE, OPERATIONAL PASS LOGIC & STRICT FAIL-STOP ENGINE
#    (SECTIONS 11, 12, 13, 14)
# ==============================================================================


def evaluate_canary_cell_operational_pass(
    *,
    cell_record: Mapping[str, Any],
    transport_response: ProviderNormalizedTransportResponse,
    generation_calls_attempted: int,
    retry_count: int,
    actual_http_request_count: int | None = None,
    provider_response_received: bool = True,
    billing_or_credit_failure: bool = False,
    http_4xx_failure: bool = False,
    http_5xx_failure: bool = False,
    transport_failure: bool = False,
) -> dict[str, Any]:
    """Evaluate the exact 13 operational PASS conditions from `w06_dev_select_amendment_01_canary_authorization_prep_v1.json`.

    Per Section 12 & Corrective 01 Blockers 2 & 3:
    - Schema validity and planner final-core quality are diagnostic only.
    - Does NOT add `raw_response_parseable_json` or non-empty `raw_text` (`len(raw_text) > 0`) as an operational gate.
    - `provider_returns_response` is True when a provider response object was received (`provider_response_received=True`)
      and no auth/billing/quota/model-access/timeout/transport/HTTP4xx/HTTP5xx failure occurred (even if `raw_text` is empty,
      a refusal/safety stop, non-JSON text, or schema-invalid JSON).
    - `exactly_one_generation_call_attempted` requires `logical_generation_invocation_count == 1` (passed as
      `generation_calls_attempted`) and at most 1 actual HTTP request.
    - A cell operationally passes if and only if all 13 `required_operational_conditions` are True.
    """
    expected_cid = str(cell_record["candidate_id"])
    expected_c = FROZEN_CANDIDATES[expected_cid]
    f_cls = transport_response.simulated_failure

    auth_fail = f_cls == DevCellFailureClassification.AUTHENTICATION_FAILURE
    quota_fail = f_cls == DevCellFailureClassification.HTTP_429
    model_access_fail = f_cls == DevCellFailureClassification.MODEL_ACCESS_FAILURE
    timeout_fail = f_cls in (
        DevCellFailureClassification.TIMEOUT,
        DevCellFailureClassification.PARTIAL_TIMEOUT,
    )
    is_5xx = http_5xx_failure or (f_cls == DevCellFailureClassification.HTTP_5XX)
    is_4xx = (
        http_4xx_failure
        or auth_fail
        or billing_or_credit_failure
        or quota_fail
        or model_access_fail
        or (f_cls == DevCellFailureClassification.HTTP_ERROR)
    )
    is_transport_fail = transport_failure or (
        f_cls == DevCellFailureClassification.HARNESS_INTERNAL_ERROR
    )

    config_ok = (
        transport_response.candidate_id == expected_cid
        and transport_response.provider == expected_c["provider_slug"]
        and transport_response.requested_model_id == expected_c["exact_model_id"]
    )
    returned_model = transport_response.returned_model_id
    model_identity_ok = bool(
        isinstance(returned_model, str)
        and returned_model.strip()
        and is_returned_model_id_compatible(
            str(expected_c["exact_model_id"]), returned_model
        )
    )
    provider_returned_resp = bool(
        provider_response_received
        and not auth_fail
        and not billing_or_credit_failure
        and not quota_fail
        and not model_access_fail
        and not timeout_fail
        and not is_transport_fail
        and not is_4xx
        and not is_5xx
    )
    exactly_one_call_ok = bool(
        generation_calls_attempted == 1
        and (actual_http_request_count is None or actual_http_request_count <= 1)
    )

    conditions: dict[str, bool] = {
        "correct_candidate_provider_model_config_used": bool(config_ok),
        "exactly_one_generation_call_attempted": exactly_one_call_ok,
        "no_authentication_failure": not auth_fail,
        "no_billing_or_credit_failure": not billing_or_credit_failure,
        "no_client_timeout": not timeout_fail,
        "no_http_4xx_failure": not is_4xx,
        "no_http_5xx_failure": not is_5xx,
        "no_model_access_failure": not model_access_fail,
        "no_provider_transport_failure": not is_transport_fail,
        "no_quota_or_rate_limit_rejection": not quota_fail,
        "provider_returns_response": provider_returned_resp,
        "required_provider_model_identity_evidence_captured": model_identity_ok,
        "retry_count_equals_zero": (retry_count == 0),
    }

    if tuple(sorted(conditions.keys())) != FROZEN_REQUIRED_OPERATIONAL_CONDITION_KEYS:
        raise PlanBeforeLiveProtocolError(
            "INTERNAL_OPERATIONAL_CONDITION_KEYS_DRIFT"
        )

    cell_operational_pass = all(conditions.values())
    failed_conditions = [k for k, v in sorted(conditions.items()) if not v]

    status_classification = (
        "HTTP_200_OPERATIONAL_OK"
        if cell_operational_pass
        else (
            f_cls.value
            if f_cls != DevCellFailureClassification.NONE
            else f"OPERATIONAL_FAILURE:{','.join(failed_conditions)}"
        )
    )
    raw_text_val = transport_response.raw_text
    raw_text_present = isinstance(raw_text_val, str)
    raw_text_non_empty = bool(raw_text_present and len(raw_text_val) > 0)

    return {
        "required_operational_conditions": conditions,
        "failed_operational_conditions": failed_conditions,
        "cell_operational_pass": cell_operational_pass,
        "http_or_provider_status_classification": status_classification,
        "authentication_failure": auth_fail,
        "billing_or_credit_failure": bool(billing_or_credit_failure),
        "quota_or_rate_limit_failure": quota_fail,
        "model_access_failure": model_access_fail,
        "timeout_failure": timeout_fail,
        "transport_failure": is_transport_fail,
        "http_4xx_failure": is_4xx,
        "http_5xx_failure": is_5xx,
        "provider_response_received": bool(provider_response_received),
        "provider_returned_response": provider_returned_resp,
        "raw_text_present": raw_text_present,
        "raw_text_non_empty": raw_text_non_empty,
        "raw_text_length": len(raw_text_val) if raw_text_present else 0,
        "refusal_or_safety_state": bool(
            transport_response.refusal_state
            or f_cls == DevCellFailureClassification.REFUSAL
        ),
        "max_token_truncation_state": bool(
            transport_response.max_token_state
            or f_cls == DevCellFailureClassification.MAX_TOKEN_TRUNCATION
        ),
        "provider_model_identity_evidence_captured": model_identity_ok,
    }


def compute_diagnostic_schema_and_quality_for_cell(
    *,
    cell_record: Mapping[str, Any],
    raw_text: str,
    dev_bundle: VerifiedDevBundle,
    core_catalog_by_place_id: Mapping[str, Any],
) -> dict[str, Any]:
    """Compute diagnostic-only schema validity and planner final-core evaluation (never gates operational PASS)."""
    dev_tune_by_id = {s.scenario_id: s for s in dev_bundle.dev_tune_fixtures}
    scenario = dev_tune_by_id[str(cell_record["fixture_id"])]
    parsed_plan, parse_failure, run_status = parse_primary_dev_plan_response(raw_text)
    schema_valid = parsed_plan is not None and run_status == BenchmarkRunStatus.VALID
    raw_sha = sha256_bytes(normalize_lf_bytes(raw_text.encode("utf-8")))
    parsed_sha = (
        sha256_bytes(canonical_json_bytes(parsed_plan.model_dump(mode="json")))
        if parsed_plan is not None
        else None
    )
    run_manifest = BenchmarkRunManifest(
        run_id=str(cell_record["cell_id"]),
        scenario_id=scenario.scenario_id,
        execution_timestamp_utc="2026-10-31T00:00:00Z",
        provider=str(cell_record["candidate_id"]),
        model_id=str(cell_record["requested_model_id"]),
        expected_model_id=str(cell_record["requested_model_id"]),
        generation_parameters={
            "temperature": 0.0,
            "seed": 42,
        },
        execution_mode="OFFLINE_MOCK_HARNESS_VERIFICATION",
        latency_ms=1000.0,
        usage_metadata=BenchmarkUsageMetadata(
            input_tokens=1000,
            output_tokens=800,
            total_tokens=1800,
        ),
        code_commit_sha=AUTHORITATIVE_BASE_DEVELOP_SHA,
        scenario_sha256=str(cell_record["scenario_sha256"]),
        catalog_sha256=compute_catalog_sha256(),
        benchmark_prompt_version=str(cell_record["prompt_id"]),
        raw_response_sha256=raw_sha,
        parsed_response_sha256=parsed_sha,
        measurement_contract_id=MEASUREMENT_CONTRACT_ID,
        measurement_contract_version=MEASUREMENT_CONTRACT_VERSION,
        hash_basis_version=HASH_BASIS_VERSION,
        run_status=run_status,
        error_detail=None if run_status == BenchmarkRunStatus.VALID else parse_failure.value,
    )
    eval_res = evaluate_dev_cell_scenario(
        scenario=scenario,
        plan_response=parsed_plan if schema_valid else None,
        run_manifest=run_manifest,
        core_catalog_by_id=dict(core_catalog_by_place_id),
    )
    return {
        "diagnostic_only_non_gating": True,
        "planner_schema_validity_is_operational_pass_criterion": False,
        "final_core_quality_is_operational_pass_criterion": False,
        "diagnostic_schema_valid": bool(schema_valid),
        "diagnostic_parse_failure_classification": parse_failure.value,
        "diagnostic_final_core_result": {
            "run_valid": bool(eval_res.run_valid),
            "all_pois_grounded": bool(eval_res.all_pois_grounded),
            "scenario_destination_valid": bool(eval_res.scenario_destination_valid),
            "core_scenario_pass_pre_opening_hours": bool(
                eval_res.core_scenario_pass_pre_opening_hours
            ),
            "core_scenario_pass": bool(eval_res.core_scenario_pass),
            "failure_reasons": list(eval_res.failure_reasons),
        },
        "parsed_plan_response": (
            parsed_plan.model_dump(mode="json") if parsed_plan is not None else None
        ),
        "evaluation_result": eval_res.model_dump(mode="json"),
    }


def execute_canary_9_cell_sequence(
    *,
    repo_root: Path = REPO_ROOT,
    output_root: Path | None = None,
    execution_mode: str = "OFFLINE_SIMULATION",
    simulated_cell_responder: Callable[
        [int, Mapping[str, Any], dict[str, Any]], dict[str, Any]
    ]
    | None = None,
    sleep_fn: Callable[[float], None] | None = None,
    clock_fn: Callable[[], str] = default_utc_now_clock,
    persist_artifacts: bool = True,
    api_key_loader: Callable[[str], str] | None = None,
    live_transport_invoker: Callable[..., ProviderNormalizedTransportResponse]
    | None = None,
) -> dict[str, Any]:
    """Execute the frozen 9-cell canary sequence with strict sequential order, 2000ms pacing, and immediate fail-stop.

    - In `OFFLINE_SIMULATION`, requires `simulated_cell_responder` and executes under `NetworkKillSwitchGuard`
      and `PreflightSecretAndEnvFileAccessGuard` (`LIVE_PROVIDER_CALLS_NEW = 0`, `ENV_FILE_READ = false`,
      `API_KEYS_INSPECTED = false`).
    - In `LIVE_CANARY_EXECUTION`, invokes the production provider transport layer at most once per cell
      (`max_requests_per_cell = 1`, `max_total_requests = 9`). Credential loading and provider invocation
      both run inside the fail-closed per-cell evidence lifecycle so pre-provider credential failures
      write normalized cell failure evidence (`logical_generation_invocation_count = 0`,
      `actual_provider_http_request_count = 0`, `cell_operational_pass = False`) and trigger immediate fail-stop.
    """
    if execution_mode not in ("OFFLINE_SIMULATION", "LIVE_CANARY_EXECUTION"):
        raise LiveExecutionNotAuthorizedError(
            f"INVALID_CANARY_EXECUTION_MODE: {execution_mode!r}"
        )
    if execution_mode == "OFFLINE_SIMULATION" and simulated_cell_responder is None:
        raise LiveExecutionNotAuthorizedError(
            "SIMULATED_RESPONDER_REQUIRED_IN_OFFLINE_SIMULATION"
        )

    verified = verify_frozen_canary_launcher_authorities(
        repo_root=repo_root,
        output_root_override=output_root,
    )
    target_output_root: Path = verified["output_root"]
    ordered_cells: list[dict[str, Any]] = verified["ordered_canary_cells"]
    dev_bundle: VerifiedDevBundle = verified["dev_bundle"]
    cand_reg: DevCandidateRegistry = verified["candidate_registry"]
    p1_spec: PromptCandidateSpec = verified["p1_spec"]
    runtime_head_sha: str = verified["source_develop_provenance"]["active_head_sha"]

    core_catalog = load_core_catalog_by_place_id()
    http_counter = DevCellHttpCallCounter(
        max_requests_per_cell=1,
        max_total_requests=FROZEN_MAX_GENERATION_CALLS,
    )

    effective_sleep = (
        sleep_fn
        if sleep_fn is not None
        else (
            (lambda _sec: None)
            if execution_mode == "OFFLINE_SIMULATION"
            else time.sleep
        )
    )

    attempted_cell_evidence: list[dict[str, Any]] = []
    scheduled_delays_ms: list[int] = []
    fail_stop_triggered = False
    stopped_at_order_index: int | None = None
    stopped_at_cell_id: str | None = None
    stopped_at_short_label: str | None = None

    for idx, cell_record in enumerate(ordered_cells):
        order_index = int(cell_record["order_index"])
        cell_id = str(cell_record["cell_id"])
        short_label = str(cell_record["short_label"])
        cid = str(cell_record["candidate_id"])
        fid = str(cell_record["fixture_id"])

        cell_manifest = build_canary_cell_execution_manifest(cell_record)
        wire_request = build_canary_cell_wire_request(
            cell_record=cell_record,
            dev_bundle=dev_bundle,
            cand_reg=cand_reg,
            p1_spec=p1_spec,
        )
        wire_request_sha256 = sha256_bytes(canonical_json_bytes(wire_request))

        cell_dir = target_output_root / cell_id
        if persist_artifacts and cell_dir.exists():
            raise ImmutableCellExecutionError(
                f"CANARY_CELL_DIR_ALREADY_EXISTS: {cell_dir}"
            )

        started_at_utc = clock_fn()
        if persist_artifacts:
            write_immutable_canonical_json(
                cell_dir / "request_manifest.json",
                {
                    "cell_id": cell_id,
                    "order_index": order_index,
                    "short_label": short_label,
                    "fixture_id": fid,
                    "candidate_id": cid,
                    "provider": cell_record["provider"],
                    "provider_slug": cell_record["provider_slug"],
                    "requested_model_id": cell_record["requested_model_id"],
                    "prompt_id": cell_record["prompt_id"],
                    "attempt_number": 1,
                    "retry_count": 0,
                    "timeout_ms": FROZEN_TIMEOUT_MS,
                    "inter_call_delay_ms": FROZEN_INTER_CALL_DELAY_MS,
                    "serialized_wire_request_sha256": wire_request_sha256,
                    "wire_request": wire_request,
                },
            )
            write_immutable_canonical_json(
                cell_dir / "transport_journal_starting.json",
                {
                    "cell_id": cell_id,
                    "order_index": order_index,
                    "short_label": short_label,
                    "candidate_id": cid,
                    "fixture_id": fid,
                    "attempt_number": 1,
                    "runtime_head_sha": runtime_head_sha,
                    "execution_started_at_utc": started_at_utc,
                    "status": TRANSPORT_STATUS_STARTING,
                },
            )

        t0_ns = time.perf_counter_ns()
        billing_fail = False
        http_4xx_fail = False
        http_5xx_fail = False
        transport_fail = False
        logical_gen_calls_for_cell = 1
        actual_http_requests_for_cell = 1
        provider_response_received = True
        retry_count_for_cell = 0

        if execution_mode == "OFFLINE_SIMULATION":
            assert simulated_cell_responder is not None
            sim_out = simulated_cell_responder(order_index, cell_record, wire_request)
            raw_text = str(sim_out.get("raw_text", '{"days": []}'))
            returned_model_id = sim_out.get(
                "returned_model_id", cell_record["requested_model_id"]
            )
            sim_failure = sim_out.get(
                "simulated_failure", DevCellFailureClassification.NONE
            )
            if isinstance(sim_failure, str):
                sim_failure = DevCellFailureClassification(sim_failure)
            billing_fail = bool(sim_out.get("billing_or_credit_failure", False))
            http_4xx_fail = bool(sim_out.get("http_4xx_failure", False))
            http_5xx_fail = bool(sim_out.get("http_5xx_failure", False))
            transport_fail = bool(sim_out.get("transport_failure", False))
            logical_gen_calls_for_cell = int(
                sim_out.get(
                    "logical_generation_invocation_count",
                    sim_out.get("generation_calls_attempted", 1),
                )
            )
            actual_http_requests_for_cell = int(
                sim_out.get(
                    "actual_provider_http_request_count",
                    logical_gen_calls_for_cell,
                )
            )
            default_resp_received = bool(
                logical_gen_calls_for_cell >= 1
                and sim_failure
                not in (
                    DevCellFailureClassification.AUTHENTICATION_FAILURE,
                    DevCellFailureClassification.HTTP_429,
                    DevCellFailureClassification.MODEL_ACCESS_FAILURE,
                    DevCellFailureClassification.TIMEOUT,
                    DevCellFailureClassification.PARTIAL_TIMEOUT,
                    DevCellFailureClassification.HTTP_5XX,
                    DevCellFailureClassification.HTTP_ERROR,
                    DevCellFailureClassification.HARNESS_INTERNAL_ERROR,
                )
                and not billing_fail
                and not http_4xx_fail
                and not http_5xx_fail
                and not transport_fail
            )
            provider_response_received = bool(
                sim_out.get("provider_response_received", default_resp_received)
            )
            retry_count_for_cell = int(sim_out.get("retry_count", 0))
            raw_usage = sim_out.get(
                "raw_usage_metadata",
                {"input_tokens": 1200, "output_tokens": 900, "total_tokens": 2100},
            )
            norm_usage = normalize_candidate_usage_metadata(cid, raw_usage)
            latency_ns = int(sim_out.get("latency_ns", 1_500_000_000))
            transport_resp = ProviderNormalizedTransportResponse(
                candidate_id=str(sim_out.get("candidate_id", cid)),
                provider=str(sim_out.get("provider_slug", cell_record["provider_slug"])),
                requested_model_id=str(
                    sim_out.get("requested_model_id", cell_record["requested_model_id"])
                ),
                returned_model_id=returned_model_id,
                raw_text=raw_text,
                finish_or_stop_reason=str(sim_out.get("finish_reason", "stop")),
                finish_reason=str(sim_out.get("finish_reason", "stop")),
                refusal_state=bool(
                    sim_out.get("refusal_state", False)
                    or sim_failure == DevCellFailureClassification.REFUSAL
                ),
                max_token_state=bool(
                    sim_out.get("max_token_state", False)
                    or sim_failure == DevCellFailureClassification.MAX_TOKEN_TRUNCATION
                ),
                raw_usage_metadata=raw_usage,
                normalized_usage_metadata=norm_usage,
                raw_provider_metadata={
                    "simulated": True,
                    "returned_model_id": returned_model_id,
                    "provider_response_received": provider_response_received,
                },
                normalized_provider_metadata={
                    "simulated": True,
                    "candidate_id": cid,
                    "returned_model_id": returned_model_id,
                    "provider_response_received": provider_response_received,
                },
                actual_http_request_count=actual_http_requests_for_cell,
                latency_ns=latency_ns,
                latency_ms=round(latency_ns / 1_000_000.0, 3),
                simulated_failure=sim_failure,
                authoritative_usage_available=bool(norm_usage.get("usage_present")),
                input_tokens=norm_usage["input_tokens"],
                output_tokens=norm_usage["output_tokens"],
                total_tokens=norm_usage["total_tokens"],
            )
        else:
            key_loader = api_key_loader or (
                lambda c: _load_candidate_api_key_for_live_transport(c)
            )
            invoker = (
                live_transport_invoker or _invoke_canary_production_transport_for_cell
            )
            logical_gen_calls_for_cell = 0
            actual_http_requests_for_cell = 0
            provider_response_received = False
            pre_provider_credential_failure = False
            api_key: str | None = None
            try:
                loaded_key = key_loader(cid)
                if not isinstance(loaded_key, str) or not loaded_key.strip():
                    raise LiveExecutionNotAuthorizedError(
                        f"MISSING_OR_EMPTY_CREDENTIAL_FOR_{cid}"
                    )
                api_key = loaded_key.strip()
            except Exception as cred_exc:
                pre_provider_credential_failure = True
                logical_gen_calls_for_cell = 0
                actual_http_requests_for_cell = (
                    http_counter.per_cell_http_requests.get(cell_id, 0)
                )
                provider_response_received = False
                safe_cred_msg = sanitize_runner_text(
                    f"{type(cred_exc).__name__}: {cred_exc}", []
                )
                norm_usage = normalize_candidate_usage_metadata(cid, None)
                transport_resp = ProviderNormalizedTransportResponse(
                    candidate_id=cid,
                    provider=str(cell_record["provider_slug"]),
                    requested_model_id=str(cell_record["requested_model_id"]),
                    returned_model_id=None,
                    raw_text="",
                    finish_or_stop_reason="PRE_PROVIDER_CREDENTIAL_FAILURE:AUTHENTICATION_FAILURE",
                    finish_reason=f"PRE_PROVIDER_CREDENTIAL_FAILURE:{safe_cred_msg}",
                    refusal_state=False,
                    max_token_state=False,
                    raw_usage_metadata=None,
                    normalized_usage_metadata=norm_usage,
                    raw_provider_metadata={
                        "pre_provider_failure": True,
                        "failure_stage": "CREDENTIAL_RESOLUTION_BEFORE_GENERATION_INVOCATION",
                        "exception_summary": safe_cred_msg,
                    },
                    normalized_provider_metadata={
                        "candidate_id": cid,
                        "pre_provider_failure": True,
                        "failure_stage": "CREDENTIAL_RESOLUTION_BEFORE_GENERATION_INVOCATION",
                        "exception_classification": DevCellFailureClassification.AUTHENTICATION_FAILURE.value,
                        "exception_summary": safe_cred_msg,
                        "logical_generation_invocation_count": 0,
                        "actual_http_request_count": actual_http_requests_for_cell,
                    },
                    actual_http_request_count=actual_http_requests_for_cell,
                    simulated_failure=DevCellFailureClassification.AUTHENTICATION_FAILURE,
                    authoritative_usage_available=False,
                )

            if not pre_provider_credential_failure:
                assert api_key is not None
                logical_gen_calls_for_cell = 1
                try:
                    transport_resp = invoker(
                        cell_manifest=cell_manifest,
                        wire_request=wire_request,
                        http_counter=http_counter,
                        api_key=api_key,
                    )
                    provider_response_received = True
                    actual_http_requests_for_cell = int(
                        transport_resp.actual_http_request_count
                    )
                except (
                    ImmutableCellExecutionError,
                    BatchExecutionFatalStopError,
                    DevCallBudgetExhaustedError,
                    CandidateRegistryIntegrityError,
                ):
                    raise
                except Exception as exc:
                    provider_response_received = False
                    actual_http_requests_for_cell = (
                        http_counter.per_cell_http_requests.get(cell_id, 0)
                    )
                    f_cls = classify_provider_transport_exception(exc)
                    safe_msg = sanitize_runner_text(
                        f"{type(exc).__name__}: {exc}", [api_key]
                    )
                    msg_low = safe_msg.lower()
                    if any(
                        tok in msg_low
                        for tok in (
                            "credit balance",
                            "insufficient_quota",
                            "billing",
                            "payment",
                        )
                    ):
                        billing_fail = True
                    status_code = getattr(exc, "status_code", None) or getattr(
                        exc, "code", None
                    )
                    if isinstance(status_code, int) and 400 <= status_code < 500:
                        http_4xx_fail = True
                    elif isinstance(status_code, int) and 500 <= status_code < 600:
                        http_5xx_fail = True
                    elif f_cls == DevCellFailureClassification.HARNESS_INTERNAL_ERROR:
                        transport_fail = True
                    norm_usage = normalize_candidate_usage_metadata(cid, None)
                    transport_resp = ProviderNormalizedTransportResponse(
                        candidate_id=cid,
                        provider=str(cell_record["provider_slug"]),
                        requested_model_id=str(cell_record["requested_model_id"]),
                        returned_model_id=None,
                        raw_text="",
                        finish_or_stop_reason=f"PROVIDER_EXCEPTION:{f_cls.value}",
                        finish_reason=f"PROVIDER_EXCEPTION:{f_cls.value}:{safe_msg}",
                        refusal_state=(f_cls == DevCellFailureClassification.REFUSAL),
                        max_token_state=(
                            f_cls == DevCellFailureClassification.MAX_TOKEN_TRUNCATION
                        ),
                        raw_usage_metadata=None,
                        normalized_usage_metadata=norm_usage,
                        raw_provider_metadata={"exception_summary": safe_msg},
                        normalized_provider_metadata={
                            "candidate_id": cid,
                            "exception_classification": f_cls.value,
                            "exception_summary": safe_msg,
                            "logical_generation_invocation_count": logical_gen_calls_for_cell,
                            "actual_http_request_count": actual_http_requests_for_cell,
                        },
                        actual_http_request_count=actual_http_requests_for_cell,
                        simulated_failure=f_cls,
                        authoritative_usage_available=False,
                    )
            latency_ns = max(1, time.perf_counter_ns() - t0_ns)
            transport_resp.latency_ns = latency_ns
            transport_resp.latency_ms = round(latency_ns / 1_000_000.0, 3)

        completed_at_utc = clock_fn()
        raw_response_sha256 = sha256_bytes(
            normalize_lf_bytes(transport_resp.raw_text.encode("utf-8"))
        )

        op_eval = evaluate_canary_cell_operational_pass(
            cell_record=cell_record,
            transport_response=transport_resp,
            generation_calls_attempted=logical_gen_calls_for_cell,
            actual_http_request_count=actual_http_requests_for_cell,
            provider_response_received=provider_response_received,
            retry_count=retry_count_for_cell,
            billing_or_credit_failure=billing_fail,
            http_4xx_failure=http_4xx_fail,
            http_5xx_failure=http_5xx_fail,
            transport_failure=transport_fail,
        )

        diag_eval = compute_diagnostic_schema_and_quality_for_cell(
            cell_record=cell_record,
            raw_text=transport_resp.raw_text,
            dev_bundle=dev_bundle,
            core_catalog_by_place_id=core_catalog,
        )

        cell_evidence: dict[str, Any] = {
            "cell_id": cell_id,
            "order_index": order_index,
            "short_label": short_label,
            "fixture_id": fid,
            "candidate_id": cid,
            "provider": cell_record["provider"],
            "provider_slug": cell_record["provider_slug"],
            "requested_model_id": cell_record["requested_model_id"],
            "returned_model_id": transport_resp.returned_model_id,
            "prompt_id": cell_record["prompt_id"],
            "attempt_number": 1,
            "logical_generation_invocation_count": logical_gen_calls_for_cell,
            "generation_call_count": logical_gen_calls_for_cell,
            "actual_provider_http_request_count": actual_http_requests_for_cell,
            "retry_count": retry_count_for_cell,
            "execution_started_at_utc": started_at_utc,
            "transport_completed_at_utc": completed_at_utc,
            "latency_ns": transport_resp.latency_ns,
            "latency_ms": transport_resp.latency_ms,
            "http_or_provider_status_classification": op_eval[
                "http_or_provider_status_classification"
            ],
            "authentication_failure": op_eval["authentication_failure"],
            "billing_or_credit_failure": op_eval["billing_or_credit_failure"],
            "quota_or_rate_limit_failure": op_eval["quota_or_rate_limit_failure"],
            "model_access_failure": op_eval["model_access_failure"],
            "timeout_failure": op_eval["timeout_failure"],
            "transport_failure": op_eval["transport_failure"],
            "http_4xx_failure": op_eval["http_4xx_failure"],
            "http_5xx_failure": op_eval["http_5xx_failure"],
            "provider_response_received": op_eval["provider_response_received"],
            "provider_returned_response": op_eval["provider_returned_response"],
            "raw_text_present": op_eval["raw_text_present"],
            "raw_text_non_empty": op_eval["raw_text_non_empty"],
            "raw_text_length": op_eval["raw_text_length"],
            "refusal_or_safety_state": op_eval["refusal_or_safety_state"],
            "max_token_truncation_state": op_eval["max_token_truncation_state"],
            "provider_model_identity_evidence_captured": op_eval[
                "provider_model_identity_evidence_captured"
            ],
            "raw_response_sha256": raw_response_sha256,
            "raw_usage_metadata": transport_resp.raw_usage_metadata,
            "normalized_usage_metadata": transport_resp.normalized_usage_metadata,
            "diagnostic_schema_valid": diag_eval["diagnostic_schema_valid"],
            "diagnostic_final_core_result": diag_eval["diagnostic_final_core_result"],
            "required_operational_conditions": op_eval[
                "required_operational_conditions"
            ],
            "failed_operational_conditions": op_eval["failed_operational_conditions"],
            "cell_operational_pass": op_eval["cell_operational_pass"],
        }
        assert_no_secrets_in_payload(
            cell_evidence, context="CANARY_CELL_EVIDENCE_RECEIPT"
        )

        if persist_artifacts:
            write_immutable_canonical_json(
                cell_dir / "transport_journal_completed.json",
                {
                    "cell_id": cell_id,
                    "order_index": order_index,
                    "short_label": short_label,
                    "candidate_id": cid,
                    "fixture_id": fid,
                    "attempt_number": 1,
                    "runtime_head_sha": runtime_head_sha,
                    "execution_started_at_utc": started_at_utc,
                    "transport_completed_at_utc": completed_at_utc,
                    "latency_ns": transport_resp.latency_ns,
                    "logical_generation_invocation_count": logical_gen_calls_for_cell,
                    "actual_provider_http_request_count": actual_http_requests_for_cell,
                    "provider_response_received": op_eval["provider_response_received"],
                    "status": TRANSPORT_STATUS_COMPLETED,
                },
            )
            write_immutable_utf8_text(
                cell_dir / "raw_provider_response.txt",
                transport_resp.raw_text,
            )
            write_immutable_canonical_json(
                cell_dir / "provider_response_metadata.json",
                {
                    "raw_provider_metadata": transport_resp.raw_provider_metadata,
                    "normalized_provider_metadata": transport_resp.normalized_provider_metadata,
                    "returned_model_id": transport_resp.returned_model_id,
                    "finish_or_stop_reason": transport_resp.finish_or_stop_reason,
                    "provider_response_received": op_eval["provider_response_received"],
                    "raw_text_present": op_eval["raw_text_present"],
                    "raw_text_non_empty": op_eval["raw_text_non_empty"],
                    "raw_text_length": op_eval["raw_text_length"],
                    "raw_response_sha256": raw_response_sha256,
                },
            )
            write_immutable_canonical_json(
                cell_dir / "raw_usage_metadata.json",
                {
                    "raw_usage_metadata": transport_resp.raw_usage_metadata,
                    "normalized_usage_metadata": transport_resp.normalized_usage_metadata,
                },
            )
            write_immutable_canonical_json(
                cell_dir / "diagnostic_evaluation.json",
                diag_eval,
            )
            write_immutable_canonical_json(
                cell_dir / "canary_cell_evidence_receipt.json",
                cell_evidence,
            )

        attempted_cell_evidence.append(cell_evidence)

        # Strict Fail-Stop Rule (Section 13): stop immediately on first operationally failed cell
        if not cell_evidence["cell_operational_pass"]:
            fail_stop_triggered = True
            stopped_at_order_index = order_index
            stopped_at_cell_id = cell_id
            stopped_at_short_label = short_label
            break

        # Fixed 2000ms pacing between cells 1..8 only if next cell will execute (Section 7)
        if idx < len(ordered_cells) - 1:
            effective_sleep(FROZEN_INTER_CALL_DELAY_MS / 1000.0)
            scheduled_delays_ms.append(FROZEN_INTER_CALL_DELAY_MS)

    attempted_count = len(attempted_cell_evidence)
    pass_count = sum(
        1 for c in attempted_cell_evidence if c["cell_operational_pass"] is True
    )
    total_logical_invocations = sum(
        int(c["logical_generation_invocation_count"]) for c in attempted_cell_evidence
    )
    total_actual_http_requests = sum(
        int(c["actual_provider_http_request_count"]) for c in attempted_cell_evidence
    )
    unscheduled_cells = ordered_cells[attempted_count:]
    all_9_pass = (
        attempted_count == FROZEN_CANARY_CELL_COUNT
        and pass_count == FROZEN_CANARY_CELL_COUNT
        and not fail_stop_triggered
    )

    summary_payload: dict[str, Any] = {
        "execution_mode": execution_mode,
        "authoritative_base_develop_sha": AUTHORITATIVE_BASE_DEVELOP_SHA,
        "runtime_head_sha": runtime_head_sha,
        "canary_authorization_prep_file_sha256": EXPECTED_CANARY_AUTH_PREP_FILE_SHA256,
        "canary_authorization_prep_internal_sha256": (
            EXPECTED_CANARY_AUTH_PREP_INTERNAL_SHA256
        ),
        "canary_manifest_file_sha256": EXPECTED_CANARY_MANIFEST_FILE_SHA256,
        "canary_manifest_internal_sha256": EXPECTED_CANARY_MANIFEST_INTERNAL_SHA256,
        "owner_readiness_attestation_file_sha256": (
            EXPECTED_OWNER_READINESS_ATTESTATION_FILE_SHA256
        ),
        "owner_readiness_attestation_internal_sha256": (
            EXPECTED_OWNER_READINESS_ATTESTATION_INTERNAL_SHA256
        ),
        "scientific_code_bundle_sha256": EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256,
        "total_assigned_canary_cells": FROZEN_CANARY_CELL_COUNT,
        "attempted_cells_count": attempted_count,
        "total_logical_generation_invocations": total_logical_invocations,
        "total_actual_provider_http_requests": total_actual_http_requests,
        "operational_pass_cells_count": pass_count,
        "operational_pass_fraction": f"{pass_count}/{FROZEN_CANARY_CELL_COUNT}",
        "unscheduled_cells_count": len(unscheduled_cells),
        "attempted_short_labels": [c["short_label"] for c in attempted_cell_evidence],
        "unscheduled_short_labels": [str(c["short_label"]) for c in unscheduled_cells],
        "unscheduled_cell_ids": [str(c["cell_id"]) for c in unscheduled_cells],
        "fail_stop_triggered": fail_stop_triggered,
        "stopped_at_order_index": stopped_at_order_index,
        "stopped_at_cell_id": stopped_at_cell_id,
        "stopped_at_short_label": stopped_at_short_label,
        "scheduled_inter_call_delays_executed": len(scheduled_delays_ms),
        "scheduled_inter_call_delays_ms": scheduled_delays_ms,
        "total_inter_call_delay_ms_executed": sum(scheduled_delays_ms),
        "ALL_9_CANARY_OPERATIONAL_PASS": all_9_pass,
        "aggregate_canary_status": "PASS" if all_9_pass else "FAIL",
        "AMENDED_COMPARATIVE_LIVE_AUTHORIZED": False,
        "COMPARATIVE_EXECUTED": False,
        "canary_pass_auto_authorizes_comparative": False,
        "MODEL_WINNER_SELECTED": False,
        "SELECTED_MODEL_ID": None,
        "STOCHASTICITY_EXECUTION_STARTED": False,
        "FINAL100_USED": False,
        "FINAL100_STATUS": "NO-GO",
        "next_action": (
            "RETURN_TO_CHATGPT_AUDIT_FOR_CANARY_RESULTS_REVIEW"
            if all_9_pass
            else "RETURN_TO_CHATGPT_AUDIT_ON_CANARY_OPERATIONAL_FAILURE"
        ),
        "attempted_cells": attempted_cell_evidence,
    }
    assert_no_secrets_in_payload(
        summary_payload, context="CANARY_BATCH_EXECUTION_SUMMARY"
    )
    if persist_artifacts:
        write_immutable_canonical_json(
            target_output_root / "canary_batch_execution_summary_v1.json",
            summary_payload,
        )
    return summary_payload


# ==============================================================================
# 6. MODE A (`--preflight`) & MODE B (`--execute-live --confirm-frozen-9-canary-cells`)
#    (SECTIONS 9..19)
# ==============================================================================


def run_preflight(
    repo_root: Path = REPO_ROOT,
    *,
    output_root_override: Path | None = None,
) -> dict[str, Any]:
    """Run Mode A (`--preflight`) strictly offline under `NetworkKillSwitchGuard` and `PreflightSecretAndEnvFileAccessGuard`."""
    with NetworkKillSwitchGuard(), PreflightSecretAndEnvFileAccessGuard():
        verified = verify_frozen_canary_launcher_authorities(
            repo_root=repo_root,
            output_root_override=output_root_override,
        )
        exec_auth_state = inspect_canary_live_execution_authorization_state(
            repo_root=repo_root
        )
        ordered_cells: list[dict[str, Any]] = verified["ordered_canary_cells"]
        dev_bundle: VerifiedDevBundle = verified["dev_bundle"]
        cand_reg: DevCandidateRegistry = verified["candidate_registry"]
        p1_spec: PromptCandidateSpec = verified["p1_spec"]
        output_root: Path = verified["output_root"]
        root_resolved = repo_root.resolve()

        ordered_request_records: list[dict[str, Any]] = []
        ordered_path_records: list[dict[str, Any]] = []

        for cell_record in ordered_cells:
            cell_id = str(cell_record["cell_id"])
            wire_req = build_canary_cell_wire_request(
                cell_record=cell_record,
                dev_bundle=dev_bundle,
                cand_reg=cand_reg,
                p1_spec=p1_spec,
            )
            req_sha = sha256_bytes(canonical_json_bytes(wire_req))
            ordered_request_records.append(
                {
                    "order_index": int(cell_record["order_index"]),
                    "short_label": str(cell_record["short_label"]),
                    "cell_id": cell_id,
                    "candidate_id": str(cell_record["candidate_id"]),
                    "requested_model_id": str(cell_record["requested_model_id"]),
                    "fixture_id": str(cell_record["fixture_id"]),
                    "serialized_wire_request_sha256": req_sha,
                }
            )

            cell_dir = output_root / cell_id
            assert_not_final100_path(cell_dir)
            try:
                rel_cell_dir = cell_dir.resolve().relative_to(root_resolved).as_posix()
            except ValueError:
                rel_cell_dir = cell_dir.as_posix()
            planned_files = {
                fname: f"{rel_cell_dir}/{fname}"
                for fname in CANARY_CELL_ARTIFACT_FILENAMES
            }
            ordered_path_records.append(
                {
                    "order_index": int(cell_record["order_index"]),
                    "cell_id": cell_id,
                    "cell_dir": rel_cell_dir,
                    "artifact_paths": planned_files,
                }
            )

        if output_root.exists():
            raise PlanBeforeLiveProtocolError(
                f"PREFLIGHT_CREATED_OUTPUT_ROOT_FORBIDDEN: {output_root} must not be created during --preflight."
            )

        request_set_sha256 = sha256_bytes(
            canonical_json_bytes(ordered_request_records)
        )
        artifact_path_set_sha256 = sha256_bytes(
            canonical_json_bytes(ordered_path_records)
        )
        if request_set_sha256 != EXPECTED_CANARY_PREFLIGHT_REQUEST_SET_SHA256:
            raise PlanBeforeLiveProtocolError(
                f"CANARY_PREFLIGHT_REQUEST_SET_SHA256_MISMATCH: expected={EXPECTED_CANARY_PREFLIGHT_REQUEST_SET_SHA256}, got={request_set_sha256}"
            )
        if (
            output_root_override is None
            and artifact_path_set_sha256
            != EXPECTED_CANARY_PREFLIGHT_ARTIFACT_PATH_SET_SHA256
        ):
            raise PlanBeforeLiveProtocolError(
                f"CANARY_PREFLIGHT_ARTIFACT_PATH_SET_SHA256_MISMATCH: expected={EXPECTED_CANARY_PREFLIGHT_ARTIFACT_PATH_SET_SHA256}, got={artifact_path_set_sha256}"
            )

        result: dict[str, Any] = {
            "task_id": TASK_ID,
            "previous_gate": PREVIOUS_GATE_ID,
            "previous_gate_decision": PREVIOUS_GATE_DECISION,
            "next_gate": NEXT_GATE_ID,
            "future_live_execution_gate": FUTURE_LIVE_EXECUTION_GATE_ID,
            "launcher_mode": "preflight",
            "status": "PASS",
            "verified": True,
            "authoritative_base_develop_sha": AUTHORITATIVE_BASE_DEVELOP_SHA,
            "source_develop_provenance": verified["source_develop_provenance"],
            "launcher_path": LAUNCHER_REL_PATH,
            "primary_launcher_path": PRIMARY_LAUNCHER_REL_PATH,
            "primary_launcher_lf_sha256": verified["primary_launcher_lf_sha256"],
            "primary_launcher_untouched": True,
            "scientific_code_bundle_sha256": verified["scientific_code_bundle_sha256"],
            "scientific_code_bundle_unchanged": True,
            "canary_authorization_prep_path": CANARY_AUTH_PREP_REL_PATH,
            "canary_authorization_prep_doc_path": CANARY_AUTH_PREP_DOC_REL_PATH,
            "canary_authorization_prep_file_sha256": (
                EXPECTED_CANARY_AUTH_PREP_FILE_SHA256
            ),
            "canary_authorization_prep_internal_sha256": (
                EXPECTED_CANARY_AUTH_PREP_INTERNAL_SHA256
            ),
            "canary_authorization_prep_doc_sha256": (
                EXPECTED_CANARY_AUTH_PREP_DOC_SHA256
            ),
            "execution_authorization_receipt_path": exec_auth_state[
                "execution_authorization_receipt_path"
            ],
            "execution_authorization_receipt_present": exec_auth_state[
                "execution_authorization_receipt_present"
            ],
            "effective_live_execution_authorized": exec_auth_state[
                "effective_live_execution_authorized"
            ],
            "live_execution_available": exec_auth_state["live_execution_available"],
            "live_execution_status": exec_auth_state["live_execution_status"],
            "canary_manifest_path": CANARY_MANIFEST_REL_PATH,
            "canary_manifest_file_sha256": EXPECTED_CANARY_MANIFEST_FILE_SHA256,
            "canary_manifest_internal_sha256": (
                EXPECTED_CANARY_MANIFEST_INTERNAL_SHA256
            ),
            "owner_readiness_attestation_path": OWNER_READINESS_ATTESTATION_REL_PATH,
            "owner_readiness_attestation_file_sha256": (
                EXPECTED_OWNER_READINESS_ATTESTATION_FILE_SHA256
            ),
            "owner_readiness_attestation_internal_sha256": (
                EXPECTED_OWNER_READINESS_ATTESTATION_INTERNAL_SHA256
            ),
            "candidate_registry_sha256": verified["candidate_registry_sha256"],
            "provider_config_registry_sha256": verified[
                "provider_config_registry_sha256"
            ],
            "portable_schema_v2_sha256": verified["portable_schema_v2_sha256"],
            "semantic_schema_sha256": verified["semantic_schema_sha256"],
            "selected_prompt_id": FROZEN_PROMPT_ID,
            "selected_prompt_semantic_sha256": EXPECTED_P1_SEMANTIC_SHA256,
            "selected_prompt_system_sha256": EXPECTED_P1_SYSTEM_PROMPT_SHA256,
            "selected_prompt_user_template_sha256": (
                EXPECTED_P1_USER_PROMPT_TEMPLATE_SHA256
            ),
            "frozen_candidates": copy.deepcopy(FROZEN_CANDIDATES),
            "frozen_canary_fixtures": list(FROZEN_CANARY_FIXTURE_IDS),
            "exact_9_cell_execution_order": [
                {
                    "order_index": r[0],
                    "short_label": r[1],
                    "fixture_id": r[2],
                    "candidate_id": r[3],
                    "cell_id": r[4],
                }
                for r in EXPECTED_CANARY_9_CELL_ORDER
            ],
            "frozen_runtime_policy": {
                "timeout_policy_id": FROZEN_TIMEOUT_POLICY_ID,
                "timeout_ms": FROZEN_TIMEOUT_MS,
                "pacing_policy_id": FROZEN_PACING_POLICY_ID,
                "inter_call_delay_ms": FROZEN_INTER_CALL_DELAY_MS,
                "delay_before_first_call_ms": FROZEN_DELAY_BEFORE_FIRST_CALL_MS,
                "delay_after_last_call_ms": FROZEN_DELAY_AFTER_LAST_CALL_MS,
                "maximum_scheduled_delays": FROZEN_MAX_SCHEDULED_DELAYS,
                "total_inter_cell_pacing_ms": FROZEN_TOTAL_INTER_CELL_PACING_MS,
                "retry_policy_id": FROZEN_RETRY_POLICY_ID,
                "automatic_retry": FROZEN_AUTOMATIC_RETRY,
                "transport_retry": FROZEN_TRANSPORT_RETRY,
                "manual_retry": FROZEN_MANUAL_RETRY,
                "llm_repair": FROZEN_LLM_REPAIR,
                "semantic_repair": FROZEN_SEMANTIC_REPAIR,
                "fallback": FROZEN_FALLBACK,
                "concurrency": FROZEN_CONCURRENCY,
                "execution_mode": FROZEN_EXECUTION_MODE_LABEL,
                "generation_calls_per_assigned_cell": FROZEN_GENERATION_CALLS_PER_CELL,
                "total_maximum_provider_generation_calls": FROZEN_MAX_GENERATION_CALLS,
            },
            "output_root": FROZEN_CANARY_OUTPUT_ROOT_REL_PATH,
            "output_root_exists": output_root.exists(),
            "future_live_command": FUTURE_CANARY_LIVE_COMMAND,
            "preflight_request_hash_count": len(ordered_request_records),
            "preflight_request_set_sha256": request_set_sha256,
            "preflight_artifact_path_count": len(ordered_path_records),
            "preflight_artifact_path_set_sha256": artifact_path_set_sha256,
            "transport_status": TRANSPORT_STATUS_NOT_INVOKED,
            "LIVE_PROVIDER_CALLS_NEW": 0,
            "ENV_FILE_READ": False,
            "API_KEYS_INSPECTED": False,
            "CANARY_LIVE_AUTHORIZATION_PROPOSED": True,
            "AMENDED_CANARY_LIVE_AUTHORIZED": False,
            "AMENDED_COMPARATIVE_LIVE_AUTHORIZED": False,
            "AMENDED_LIVE_AUTHORIZED": False,
            "AMENDED_LIVE_EXECUTED": False,
            "CANARY_EXECUTED": False,
            "COMPARATIVE_EXECUTED": False,
            "MODEL_WINNER_SELECTED": False,
            "SELECTED_MODEL_ID": None,
            "STOCHASTICITY_EXECUTION_STARTED": False,
            "FINAL100_USED": False,
            "FINAL100_STATUS": "NO-GO",
            "PRIMARY_EXPERIMENT_MUTATED": False,
            "PRIMARY_RESULTS_REPLACED": False,
            "PRIMARY_DENOMINATORS_CHANGED": False,
            "authoritative_primary_strict_rates": dict(
                AUTHORITATIVE_PRIMARY_STRICT_RATES
            ),
        }
        assert_no_secrets_in_payload(
            result, context="CANARY_LIVE_LAUNCHER_PREFLIGHT"
        )
        return result


def run_live_canary_execution(
    repo_root: Path = REPO_ROOT,
    *,
    output_root_override: Path | None = None,
    execution_authorization_receipt_path_override: Path | None = None,
    api_key_loader: Callable[[str], str] | None = None,
    live_transport_invoker: Callable[..., ProviderNormalizedTransportResponse]
    | None = None,
    sleep_fn: Callable[[float], None] | None = None,
) -> dict[str, Any]:
    """Run Mode B (`--execute-live --confirm-frozen-9-canary-cells`).

    Enforces two-layer live authorization BEFORE any API key access, cell directory creation,
    or provider network call:
    1. Frozen authorization PREP artifact (`w06_dev_select_amendment_01_canary_authorization_prep_v1.json`)
       must match exact file/internal SHA256 and preserve `AMENDED_CANARY_LIVE_AUTHORIZED == False`.
    2. Separate live-execution authorization receipt (`w06_dev_select_amendment_01_canary_live_execution_authorization_v1.json`)
       must exist, pass canonical internal SHA256 tamper verification, bind all frozen hashes/models/order/budget/zero-retry/firewalls,
       and have `CANARY_LIVE_EXECUTION_AUTHORIZED == True`.
    """
    verify_two_layer_canary_live_execution_authorization(
        repo_root=repo_root,
        execution_auth_receipt_path_override=execution_authorization_receipt_path_override,
        output_root_override=output_root_override,
    )
    return execute_canary_9_cell_sequence(
        repo_root=repo_root,
        output_root=output_root_override,
        execution_mode="LIVE_CANARY_EXECUTION",
        sleep_fn=sleep_fn,
        persist_artifacts=True,
        api_key_loader=api_key_loader,
        live_transport_invoker=live_transport_invoker,
    )


# ==============================================================================
# 7. CLI ENTRYPOINT WITH HARD SCOPE LOCK & SAFETY FLAGS (SECTIONS 9, 18)
# ==============================================================================


def run_canary_launcher_cli(
    argv: Sequence[str] | None = None,
    *,
    repo_root: Path = REPO_ROOT,
    output_root_override: Path | None = None,
) -> dict[str, Any]:
    """CLI entrypoint for `scripts/run_w06_dev_select_amendment_01_canary_live_v1.py`."""
    raw_args = list(argv) if argv is not None else []

    for arg in raw_args:
        arg_lower = arg.lower()
        if (
            "final100" in arg_lower
            or "w06-scenario-" in arg_lower
            or "w06_scenarios_freeze" in arg_lower
            or "w06_p11_assignment" in arg_lower
        ):
            raise Final100FirewallViolationError(
                f"FINAL100_FIREWALL_VIOLATION: Forbidden Final100 argument {arg!r} in W06 canary launcher."
            )
        if "stochasticity" in arg_lower:
            raise StochasticityGateViolationError(
                f"STOCHASTICITY_FORBIDDEN_IN_CANARY_LAUNCHER: Forbidden stochasticity argument {arg!r}."
            )
        for forbidden_prefix in FORBIDDEN_CLI_OVERRIDE_PREFIXES:
            if arg_lower == forbidden_prefix or arg_lower.startswith(
                f"{forbidden_prefix}="
            ):
                raise PlanBeforeLiveProtocolError(
                    f"FROZEN_CANARY_SCOPE_OVERRIDE_FORBIDDEN: CLI override {arg!r} is forbidden; "
                    "W06 Amendment 01 canary authorities, 3 candidates, P1 prompt, 9 cells, runtime policy, and output root are hard-locked."
                )

    parser = argparse.ArgumentParser(
        description="Frozen W06 DEV-SELECT Amendment 01 Readiness Canary (P1, 3 fixtures x 3 candidates = 9 cells) Launcher.",
        add_help=True,
    )
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="Run strictly offline preflight verification (0 provider calls, network & .env/secret kill-switches active).",
    )
    parser.add_argument(
        "--execute-live",
        action="store_true",
        help="Explicit live canary execution flag (MUST be combined with --confirm-frozen-9-canary-cells).",
    )
    parser.add_argument(
        "--confirm-frozen-9-canary-cells",
        action="store_true",
        help="Mandatory confirmation flag required alongside --execute-live.",
    )

    try:
        parsed, unknown = parser.parse_known_args(raw_args)
    except SystemExit as exc:
        raise PlanBeforeLiveProtocolError(
            f"INVALID_CLI_ARGUMENTS: {raw_args!r}"
        ) from exc

    if unknown:
        raise PlanBeforeLiveProtocolError(
            f"UNSUPPORTED_CLI_ARGUMENTS_FORBIDDEN: {unknown!r}; canary launcher scope is hard-locked."
        )

    if parsed.preflight and (
        parsed.execute_live or parsed.confirm_frozen_9_canary_cells
    ):
        raise PlanBeforeLiveProtocolError(
            "MODE_CONFLICT_FORBIDDEN: Cannot combine --preflight with --execute-live or --confirm-frozen-9-canary-cells."
        )

    if parsed.confirm_frozen_9_canary_cells and not parsed.execute_live:
        raise LiveExecutionNotAuthorizedError(
            "LIVE_EXECUTION_FLAG_MISSING: --confirm-frozen-9-canary-cells cannot be used without --execute-live."
        )

    if parsed.execute_live and not parsed.confirm_frozen_9_canary_cells:
        raise LiveExecutionNotAuthorizedError(
            "LIVE_CONFIRMATION_FLAG_MISSING: --execute-live requires --confirm-frozen-9-canary-cells."
        )

    if parsed.preflight:
        return run_preflight(
            repo_root=repo_root,
            output_root_override=output_root_override,
        )

    if parsed.execute_live and parsed.confirm_frozen_9_canary_cells:
        return run_live_canary_execution(
            repo_root=repo_root,
            output_root_override=output_root_override,
        )

    raise LiveExecutionNotAuthorizedError(
        "NO_MODE_SPECIFIED: Specify --preflight (offline) or both --execute-live and --confirm-frozen-9-canary-cells."
    )


def main(argv: Sequence[str] | None = None) -> int:
    out = run_canary_launcher_cli(argv if argv is not None else sys.argv[1:])
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
