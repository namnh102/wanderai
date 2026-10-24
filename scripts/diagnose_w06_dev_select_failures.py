#!/usr/bin/env python3
"""Strictly offline, read-only, deterministic failure diagnostic analyzer for W06 DEV-SELECT.

TASK: W06-DEV-SELECT-FAILURE-DIAGNOSTIC-01-OFFLINE

PURPOSE:
Perform a strictly read-only, deterministic, evidence-based diagnostic analysis of the
already frozen W06 DEV-SELECT 180-cell live execution (`data/evaluation/w06/live_dev_select_primary_v1`).

THIS SCRIPT IS STRICTLY OFFLINE AND READ-ONLY WITH RESPECT TO RAW EVIDENCE.
LIVE_PROVIDER_CALLS_NEW = 0
MODEL_WINNER_SELECTED = false
selected_model_id = null
STOCHASTICITY_EXECUTION_STARTED = false
FINAL100_USED = false
RAW_EVIDENCE_MUTATED = false
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import socket
import statistics
import sys
from typing import Any, Mapping

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
    FORBIDDEN_FINAL100_BUNDLE_SHA256,
    FORBIDDEN_P11_MANIFEST_SHA256,
    canonical_json_bytes,
    compute_scientific_code_bundle_sha256,
    load_and_verify_frozen_dev_bundle,
    normalize_lf_bytes,
    sha256_bytes,
)
import freeze_w06_dev_select_live_results as _freeze_mod  # noqa: E402
from run_w06_dev_select_live_v1 import (  # noqa: E402
    NetworkKillSwitchGuard as _BaseNetworkKillSwitchGuard,
    OutboundNetworkBlockedError,
)


class NetworkKillSwitchGuard(_BaseNetworkKillSwitchGuard):
    """Hard offline network kill switch blocking DNS, socket, urllib, httpx, and httpx2."""

    def __enter__(self) -> "NetworkKillSwitchGuard":
        super().__enter__()
        self._orig_getaddrinfo = socket.getaddrinfo
        self._orig_gethostbyname = socket.gethostbyname
        self._orig_gethostbyname_ex = socket.gethostbyname_ex

        def _deny_dns(label: str) -> Any:
            def _raiser(*_a: Any, **_kw: Any) -> Any:
                self.blocked_attempts.append(label)
                raise OutboundNetworkBlockedError(
                    f"OFFLINE_NETWORK_KILL_SWITCH_TRIGGERED: {label} is forbidden in {TASK_ID}."
                )

            return _raiser

        socket.getaddrinfo = _deny_dns("socket.getaddrinfo")  # type: ignore[assignment]
        socket.gethostbyname = _deny_dns("socket.gethostbyname")  # type: ignore[assignment]
        socket.gethostbyname_ex = _deny_dns("socket.gethostbyname_ex")  # type: ignore[assignment]
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        socket.getaddrinfo = self._orig_getaddrinfo  # type: ignore[assignment]
        socket.gethostbyname = self._orig_gethostbyname  # type: ignore[assignment]
        socket.gethostbyname_ex = self._orig_gethostbyname_ex  # type: ignore[assignment]
        super().__exit__(exc_type, exc_val, exc_tb)


# ==============================================================================
# 1. FROZEN AUTHORITIES & CONSTANTS (SECTIONS 1..19)
# ==============================================================================

TASK_ID = "W06-DEV-SELECT-FAILURE-DIAGNOSTIC-01-OFFLINE"
DIAGNOSTIC_ARTIFACT_ID = "W06-DEV-SELECT-FAILURE-DIAGNOSTIC-V1"
DIAGNOSTIC_ARTIFACT_REL_PATH = (
    "data/evaluation/w06/w06_dev_select_failure_diagnostic_v1.json"
)
RAW_OUTPUT_ROOT_REL_PATH = "data/evaluation/w06/live_dev_select_primary_v1"

EXPECTED_BASE_DEVELOP_SHA = "beb5ec657bb4417bdeaf307356e6895070b64cdc"
EXPECTED_SOURCE_DEVELOP_SHA = "beb5ec657bb4417bdeaf307356e6895070b64cdc"
EXPECTED_PRE_LIVE_DEVELOP_SHA = "eac86a38f6b457c9b6ff078f26c4f953a9fc98a7"

EXPECTED_RAW_EVIDENCE_FILE_COUNT = 1629
EXPECTED_RAW_EVIDENCE_TOTAL_BYTES = 16264062
EXPECTED_RAW_EVIDENCE_MAX_FILE_BYTES = 96143
EXPECTED_RAW_EVIDENCE_TREE_SHA256 = (
    "d5c4e53952500655b656a624657a3cf1ec7aae685809c9e53a318459cc319817"
)

EXPECTED_RESULTS_MANIFEST_REL_PATH = (
    "data/evaluation/w06/w06_dev_select_live_results_manifest_v1.json"
)
EXPECTED_RESULTS_MANIFEST_FILE_SHA256 = (
    "1d303e1c07b627c3f3eb87287b744f55ba3f6d3d85bd5cec36959b01919d26c0"
)
EXPECTED_RESULTS_MANIFEST_INTERNAL_SHA256 = (
    "4e2f8f0df0a6e069d65b563b8221c3ba3086bb50ad73854e9cc592a9beb05011"
)

EXPECTED_RESULTS_FREEZE_RECEIPT_REL_PATH = (
    "data/evaluation/w06/w06_dev_select_live_results_freeze_01_receipt_v1.json"
)
EXPECTED_RESULTS_FREEZE_RECEIPT_FILE_SHA256 = (
    "c021094e26277d41664c4ae2f0560b7684435b6002c5b7ba742a17808c5b07a4"
)
EXPECTED_RESULTS_FREEZE_RECEIPT_INTERNAL_SHA256 = (
    "7b270de482f0b077e79bbba40a0c662851da46355a18b5e05f8fdf572880943a"
)

EXPECTED_DEV_SELECT_PLAN_REL_PATH = (
    "data/evaluation/w06/w06_dev_select_execution_plan_v1.json"
)
EXPECTED_DEV_SELECT_PLAN_FILE_SHA256 = (
    "c519baf7cd2557b5e1dd2699a5ceaec592af015d7bc6dcc83abf63892a8a329a"
)
EXPECTED_DEV_SELECT_PLAN_INTERNAL_SHA256 = (
    "de04255989a9e3bd8c2e39c766432487dce4ccd0612d5dba73b3476cbc9d0c6d"
)

EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256 = (
    "0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3"
)
EXPECTED_LAUNCHER_REL_PATH = "scripts/run_w06_dev_select_live_v1.py"
EXPECTED_LAUNCHER_LF_SHA256 = (
    "cd36b8ecad24059edb597c0039bd6e760a37ee8b4f36f49077801c65e7ddc7bf"
)
EXPECTED_LAUNCHER_GIT_BLOB_SHA = "ad597560ca149f8b78786c63feb64d63ac399971"

EXPECTED_ASSIGNED_CELL_COUNT = 180
EXPECTED_PER_CANDIDATE_CELL_COUNT = 60
FROZEN_TIMEOUT_AUTHORITY_MS = 55000
FROZEN_TIMEOUT_AUTHORITY_SECONDS = 55.0

NEAR_TIMEOUT_BOUNDARY_LOW_MS = 54000.0
NEAR_TIMEOUT_BOUNDARY_HIGH_MS = 57000.0
NEAR_TIMEOUT_BOUNDARY_RULE = "54000.0 <= latency_ms <= 57000.0"

PRIMARY_FAILURE_CLASSIFICATION_AUTHORITY = "execution_receipt.failure_classification"

EXPECTED_PRIMARY_COUNTS_TOTAL: dict[str, int] = {
    "HTTP_429": 35,
    "HTTP_5XX": 10,
    "HTTP_ERROR": 60,
    "NONE": 9,
    "TIMEOUT": 66,
}

EXPECTED_PRIMARY_COUNTS_BY_CANDIDATE: dict[str, dict[str, int]] = {
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

SECONDARY_TAXONOMY_VERSION = "W06-DEV-SELECT-SECONDARY-TAXONOMY-V1"

ALLOWED_SECONDARY_DIAGNOSTIC_LABELS: tuple[str, ...] = (
    "SUCCESSFUL_PROVIDER_RESPONSE",
    "CLIENT_TIMEOUT_REPORTED",
    "HTTP_429_PROVIDER_RATE_OR_QUOTA_DECLARED",
    "HTTP_429_UNSPECIFIED",
    "HTTP_5XX_PROVIDER_CAPACITY_OR_HIGH_DEMAND_DECLARED",
    "HTTP_5XX_OTHER",
    "HTTP_4XX_PROVIDER_BILLING_OR_CREDIT_DECLARED",
    "HTTP_4XX_OTHER",
    "HTTP_ERROR_OTHER",
    "UNKNOWN_OR_INSUFFICIENT_EVIDENCE",
)

EXPECTED_SECONDARY_COUNTS_TOTAL: dict[str, int] = {
    "CLIENT_TIMEOUT_REPORTED": 56,
    "HTTP_429_PROVIDER_RATE_OR_QUOTA_DECLARED": 35,
    "HTTP_429_UNSPECIFIED": 0,
    "HTTP_4XX_OTHER": 0,
    "HTTP_4XX_PROVIDER_BILLING_OR_CREDIT_DECLARED": 60,
    "HTTP_5XX_OTHER": 10,
    "HTTP_5XX_PROVIDER_CAPACITY_OR_HIGH_DEMAND_DECLARED": 10,
    "HTTP_ERROR_OTHER": 0,
    "SUCCESSFUL_PROVIDER_RESPONSE": 9,
    "UNKNOWN_OR_INSUFFICIENT_EVIDENCE": 0,
}

EXPECTED_SECONDARY_COUNTS_BY_CANDIDATE: dict[str, dict[str, int]] = {
    "C1": {
        "CLIENT_TIMEOUT_REPORTED": 4,
        "HTTP_429_PROVIDER_RATE_OR_QUOTA_DECLARED": 35,
        "HTTP_429_UNSPECIFIED": 0,
        "HTTP_4XX_OTHER": 0,
        "HTTP_4XX_PROVIDER_BILLING_OR_CREDIT_DECLARED": 0,
        "HTTP_5XX_OTHER": 10,
        "HTTP_5XX_PROVIDER_CAPACITY_OR_HIGH_DEMAND_DECLARED": 10,
        "HTTP_ERROR_OTHER": 0,
        "SUCCESSFUL_PROVIDER_RESPONSE": 1,
        "UNKNOWN_OR_INSUFFICIENT_EVIDENCE": 0,
    },
    "C2": {
        "CLIENT_TIMEOUT_REPORTED": 52,
        "HTTP_429_PROVIDER_RATE_OR_QUOTA_DECLARED": 0,
        "HTTP_429_UNSPECIFIED": 0,
        "HTTP_4XX_OTHER": 0,
        "HTTP_4XX_PROVIDER_BILLING_OR_CREDIT_DECLARED": 0,
        "HTTP_5XX_OTHER": 0,
        "HTTP_5XX_PROVIDER_CAPACITY_OR_HIGH_DEMAND_DECLARED": 0,
        "HTTP_ERROR_OTHER": 0,
        "SUCCESSFUL_PROVIDER_RESPONSE": 8,
        "UNKNOWN_OR_INSUFFICIENT_EVIDENCE": 0,
    },
    "C3": {
        "CLIENT_TIMEOUT_REPORTED": 0,
        "HTTP_429_PROVIDER_RATE_OR_QUOTA_DECLARED": 0,
        "HTTP_429_UNSPECIFIED": 0,
        "HTTP_4XX_OTHER": 0,
        "HTTP_4XX_PROVIDER_BILLING_OR_CREDIT_DECLARED": 60,
        "HTTP_5XX_OTHER": 0,
        "HTTP_5XX_PROVIDER_CAPACITY_OR_HIGH_DEMAND_DECLARED": 0,
        "HTTP_ERROR_OTHER": 0,
        "SUCCESSFUL_PROVIDER_RESPONSE": 0,
        "UNKNOWN_OR_INSUFFICIENT_EVIDENCE": 0,
    },
}

ALLOWED_EVIDENCE_LEVELS: tuple[str, ...] = (
    "DIRECT_PROVIDER_DECLARATION",
    "DIRECT_FROZEN_METADATA",
    "DERIVED_DETERMINISTIC_PATTERN",
    "INSUFFICIENT_EVIDENCE",
)

FORBIDDEN_INTERPRETATION_STRINGS: tuple[str, ...] = (
    "Claude quality = zero",
    "Claude cannot solve the task",
    "C3 semantic performance is inferior",
    "model inherently too slow",
)

REQUIRED_INTERPRETATION_FIREWALL_STATEMENTS: tuple[str, ...] = (
    "PRIMARY DEV-SELECT RESULTS ARE NOT CHANGED.",
    "NO CELL IS EXCLUDED FROM DENOMINATOR.",
    "NO RETRY IS PERMITTED BY THIS TASK.",
    "NO RERUN IS AUTHORIZED.",
    "NO MODEL WINNER IS SELECTED.",
    "NO SELECTION CRITERION IS MODIFIED.",
    "NO COST/LATENCY TIEBREAK IS APPLIED.",
    "NO STOCHASTICITY RUN IS STARTED.",
    "FINAL100 REMAINS UNTOUCHED.",
    "Provider/billing/quota/timeout failures remain part of the original frozen 60-cell denominator per candidate.",
)

PERMITTED_C3_FINDING = (
    "The frozen C3 provider/model configuration produced 60/60 provider-declared "
    "billing/credit rejection responses during this one-shot DEV-SELECT execution."
)

EXPECTED_DIAGNOSTIC_ARTIFACT_FILE_SHA256: str | None = (
    "b729883505ecfc98f15917347239ea6d09cede106691b155026891996391e692"
)
EXPECTED_DIAGNOSTIC_ARTIFACT_INTERNAL_SHA256: str | None = (
    "509528413e1d9eb8408943867be21f83dc2dda72acd53fe9028e3c37c7db05c8"
)


# ==============================================================================
# 2. DETERMINISTIC SECONDARY TAXONOMY & ERROR NORMALIZATION (SECTIONS 6 & 7)
# ==============================================================================


def extract_http_status_code(error_text: str | None) -> int | None:
    """Deterministically extract HTTP status code from sanitized provider error detail."""
    if not error_text or not isinstance(error_text, str):
        return None
    text = error_text.strip()
    if not text:
        return None

    m_code_kv = re.search(r"'code':\s*(\d{3})\b", text)
    if m_code_kv:
        return int(m_code_kv.group(1))

    m_err_code = re.search(r"\bError code:\s*(\d{3})\b", text, flags=re.IGNORECASE)
    if m_err_code:
        return int(m_err_code.group(1))

    m_cls_code = re.search(
        r"^[A-Za-z0-9_]+Error:\s*(\d{3})\b", text
    )
    if m_cls_code:
        return int(m_cls_code.group(1))

    m_http_status = re.search(r"\bHTTP\s+(\d{3})\b", text, flags=re.IGNORECASE)
    if m_http_status:
        return int(m_http_status.group(1))

    return None


def extract_exception_class(error_text: str | None) -> str | None:
    """Extract leading exception class name from `error_detail_sanitized`."""
    if not error_text or not isinstance(error_text, str):
        return None
    m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):", error_text.strip())
    if m:
        return m.group(1)
    return None


def extract_provider_declared_error_type(error_text: str | None) -> str | None:
    """Extract provider-declared error status/type from frozen error detail."""
    if not error_text or not isinstance(error_text, str):
        return None
    text = error_text.strip()
    m_inner_type = re.search(
        r"'error':\s*\{\s*'type':\s*'([^']+)'", text
    )
    if m_inner_type:
        return m_inner_type.group(1)
    m_status = re.search(r"'status':\s*'([^']+)'", text)
    if m_status:
        return m_status.group(1)
    m_header_status = re.match(
        r"^[A-Za-z_][A-Za-z0-9_]*:\s*\d{3}\s+([A-Z0-9_]+)\.", text
    )
    if m_header_status:
        return m_header_status.group(1)
    return None


def extract_provider_declared_message(error_text: str | None) -> str | None:
    """Extract provider-declared error message from frozen error detail (with volatile retry delay normalized)."""
    if not error_text or not isinstance(error_text, str):
        return None
    norm = normalize_error_detail_for_signature(error_text)
    m_msg = re.search(r"'message':\s*'((?:\\'|[^'])*)'", norm)
    if m_msg:
        return m_msg.group(1)
    parts = norm.split(":", 1)
    if len(parts) == 2:
        return parts[1].strip()
    return norm


def normalize_error_detail_for_signature(error_text: str | None) -> str:
    """Normalize volatile identifiers in `error_detail_sanitized` while preserving all semantic fields (Section 7).

    Strips/normalizes ONLY volatile identifiers:
    - `request_id` (`req_...`)
    - provider response IDs (`chatcmpl-...`, `msg_...`, `resp_...`)
    - volatile per-second retry countdowns (`Please retry in ...`, `'retryDelay': '...'`)
    - dict key order inside `quotaDimensions` (`{'model': ..., 'location': ...}`)

    Preserves HTTP status, exception class, provider-declared error type, provider-declared
    semantic message, and timeout type untouched.
    """
    if not error_text or not isinstance(error_text, str):
        return ""
    s = error_text.strip()
    s = re.sub(
        r"'request_id':\s*'[^']*'",
        "'request_id': '<VOLATILE_REQUEST_ID>'",
        s,
    )
    s = re.sub(
        r'"request_id":\s*"[^"]*"',
        '"request_id": "<VOLATILE_REQUEST_ID>"',
        s,
    )
    s = re.sub(
        r"\brequest_id=[A-Za-z0-9_-]+\b",
        "request_id=<VOLATILE_REQUEST_ID>",
        s,
    )
    s = re.sub(r"\breq_[A-Za-z0-9_]+\b", "<VOLATILE_REQUEST_ID>", s)
    s = re.sub(
        r"\b(?:chatcmpl|msg|resp)[-_][A-Za-z0-9_-]+\b",
        "<VOLATILE_RESPONSE_ID>",
        s,
    )
    s = re.sub(
        r"Please retry in [0-9hms.]+s\.",
        "Please retry in <VOLATILE_RETRY_DELAY>.",
        s,
    )
    s = re.sub(
        r"'retryDelay':\s*'[0-9.]+s'",
        "'retryDelay': '<VOLATILE_RETRY_DELAY>'",
        s,
    )
    s = re.sub(
        r"'quotaDimensions':\s*\{'model':\s*'([^']+)',\s*'location':\s*'([^']+)'\}",
        r"'quotaDimensions': {'location': '\2', 'model': '\1'}",
        s,
    )
    return s


def is_quota_or_rate_limit_declared(error_text: str | None) -> bool:
    """Return True iff frozen error text explicitly declares rate limit or quota exhaustion."""
    if not error_text or not isinstance(error_text, str):
        return False
    lower = error_text.lower()
    return any(
        tok in lower
        for tok in (
            "exceeded your current quota",
            "quota exceeded",
            "quotafailure",
            "rate limit",
            "rate-limit",
            "rate_limit",
            "generaterequestsperday",
        )
    )


def is_capacity_or_high_demand_declared(error_text: str | None) -> bool:
    """Return True iff frozen error text explicitly declares high demand, capacity, or overload."""
    if not error_text or not isinstance(error_text, str):
        return False
    lower = error_text.lower()
    return any(
        tok in lower
        for tok in (
            "currently experiencing high demand",
            "high demand",
            "spikes in demand",
            "overloaded",
            "capacity",
            "server is overloaded",
        )
    )


def is_billing_or_credit_declared(error_text: str | None) -> bool:
    """Return True iff frozen error text explicitly declares billing or credit balance rejection."""
    if not error_text or not isinstance(error_text, str):
        return False
    lower = error_text.lower()
    return any(
        tok in lower
        for tok in (
            "credit balance is too low",
            "plans & billing",
            "purchase credits",
            "billing details",
            "insufficient_quota",
            "billing_hard_limit",
        )
    )


def is_client_timeout_reported(error_text: str | None) -> bool:
    """Return True iff frozen error text reports a client/transport timeout without an HTTP status response."""
    if not error_text or not isinstance(error_text, str):
        return False
    if extract_http_status_code(error_text) is not None:
        return False
    exc_cls = (extract_exception_class(error_text) or "").lower()
    lower = error_text.lower()
    if exc_cls in (
        "readtimeout",
        "apitimeouterror",
        "connecttimeout",
        "writetimeout",
        "pooltimeout",
        "timeouterror",
        "timeoutexception",
    ):
        return True
    return "timed out" in lower or "request timed out" in lower


def classify_secondary_diagnostic_label(
    *,
    primary_failure_classification: str,
    error_detail_sanitized: str | None,
    finish_reason: str | None,
) -> str:
    """Deterministically assign one secondary diagnostic label from status/error evidence only (Section 6).

    Never inspects `candidate_id`. Unknown or insufficient error evidence falls back fail-closed
    to the generic/unknown category.
    """
    p_cls = primary_failure_classification.split(".")[-1].strip()
    if p_cls == "NONE":
        if (
            (error_detail_sanitized is None or error_detail_sanitized == "")
            and isinstance(finish_reason, str)
            and finish_reason.strip().lower() in ("stop", "end_turn")
        ):
            return "SUCCESSFUL_PROVIDER_RESPONSE"
        return "UNKNOWN_OR_INSUFFICIENT_EVIDENCE"

    if not error_detail_sanitized or not isinstance(error_detail_sanitized, str):
        return "UNKNOWN_OR_INSUFFICIENT_EVIDENCE"

    text = error_detail_sanitized.strip()
    if not text:
        return "UNKNOWN_OR_INSUFFICIENT_EVIDENCE"

    status_code = extract_http_status_code(text)

    if is_client_timeout_reported(text):
        return "CLIENT_TIMEOUT_REPORTED"

    if status_code == 429 or (p_cls == "HTTP_429" and status_code is None and "429" in text):
        if is_quota_or_rate_limit_declared(text):
            return "HTTP_429_PROVIDER_RATE_OR_QUOTA_DECLARED"
        return "HTTP_429_UNSPECIFIED"

    if status_code is not None and 500 <= status_code <= 599:
        if is_capacity_or_high_demand_declared(text):
            return "HTTP_5XX_PROVIDER_CAPACITY_OR_HIGH_DEMAND_DECLARED"
        return "HTTP_5XX_OTHER"

    if status_code is not None and 400 <= status_code <= 499:
        if is_billing_or_credit_declared(text):
            return "HTTP_4XX_PROVIDER_BILLING_OR_CREDIT_DECLARED"
        return "HTTP_4XX_OTHER"

    if p_cls == "HTTP_5XX":
        if is_capacity_or_high_demand_declared(text):
            return "HTTP_5XX_PROVIDER_CAPACITY_OR_HIGH_DEMAND_DECLARED"
        if any(tok in text.lower() for tok in ("servererror", "internal server error", "bad gateway", "service unavailable")):
            return "HTTP_5XX_OTHER"
        return "UNKNOWN_OR_INSUFFICIENT_EVIDENCE"

    if p_cls == "HTTP_429":
        if is_quota_or_rate_limit_declared(text):
            return "HTTP_429_PROVIDER_RATE_OR_QUOTA_DECLARED"
        if "ratelimit" in text.lower() or "too many requests" in text.lower():
            return "HTTP_429_UNSPECIFIED"
        return "UNKNOWN_OR_INSUFFICIENT_EVIDENCE"

    if p_cls == "HTTP_ERROR":
        if any(
            tok in text.lower()
            for tok in ("httperror", "http_error", "connectionerror", "transport")
        ):
            return "HTTP_ERROR_OTHER"
        return "UNKNOWN_OR_INSUFFICIENT_EVIDENCE"

    return "UNKNOWN_OR_INSUFFICIENT_EVIDENCE"


def determine_cell_evidence_level(secondary_label: str) -> str:
    """Return the Section 14 evidence level for a cell's secondary diagnostic classification."""
    if secondary_label in (
        "HTTP_429_PROVIDER_RATE_OR_QUOTA_DECLARED",
        "HTTP_5XX_PROVIDER_CAPACITY_OR_HIGH_DEMAND_DECLARED",
        "HTTP_4XX_PROVIDER_BILLING_OR_CREDIT_DECLARED",
        "HTTP_5XX_OTHER",
    ):
        return "DIRECT_PROVIDER_DECLARATION"
    if secondary_label in (
        "SUCCESSFUL_PROVIDER_RESPONSE",
        "CLIENT_TIMEOUT_REPORTED",
        "HTTP_429_UNSPECIFIED",
        "HTTP_4XX_OTHER",
        "HTTP_ERROR_OTHER",
    ):
        return "DIRECT_FROZEN_METADATA"
    return "INSUFFICIENT_EVIDENCE"


def determine_timeout_type(
    *,
    primary_failure_classification: str,
    error_detail_sanitized: str | None,
) -> str | None:
    """Return descriptive timeout type for failure signature construction (Section 7)."""
    p_cls = primary_failure_classification.split(".")[-1].strip()
    if p_cls != "TIMEOUT" and not is_client_timeout_reported(error_detail_sanitized):
        return None
    exc_cls = extract_exception_class(error_detail_sanitized)
    status_code = extract_http_status_code(error_detail_sanitized)
    if status_code == 504:
        return "PROVIDER_HTTP_504_DEADLINE_EXCEEDED"
    if exc_cls == "ReadTimeout":
        return "CLIENT_READ_TIMEOUT"
    if exc_cls == "APITimeoutError":
        return "CLIENT_API_TIMEOUT"
    if exc_cls:
        return f"CLIENT_{exc_cls.upper()}"
    return "TIMEOUT_UNSPECIFIED"


def build_normalized_error_signature_record(
    *,
    candidate_id: str,
    primary_classification: str,
    secondary_label: str,
    error_detail_sanitized: str | None,
) -> dict[str, Any]:
    """Build deterministic semantic signature components and SHA256 for a failure cell (Section 7)."""
    norm_msg = normalize_error_detail_for_signature(error_detail_sanitized)
    http_status = extract_http_status_code(error_detail_sanitized)
    exc_class = extract_exception_class(error_detail_sanitized)
    err_type = extract_provider_declared_error_type(error_detail_sanitized)
    prov_msg = extract_provider_declared_message(error_detail_sanitized)
    timeout_type = determine_timeout_type(
        primary_failure_classification=primary_classification,
        error_detail_sanitized=error_detail_sanitized,
    )
    signature_identity = {
        "candidate_id": candidate_id,
        "exception_class": exc_class,
        "http_status_code": http_status,
        "primary_classification": primary_classification,
        "provider_declared_error_type": err_type,
        "provider_declared_message": prov_msg,
        "representative_sanitized_semantic_message": norm_msg,
        "secondary_label": secondary_label,
        "timeout_type": timeout_type,
    }
    sig_sha = sha256_bytes(canonical_json_bytes(signature_identity))
    return {
        **signature_identity,
        "normalized_signature_sha256": sig_sha,
    }


def classify_timeout_latency_bucket(latency_ms: float) -> str:
    """Classify timeout latency (ms) into the exact Section 9 deterministic intervals."""
    val = float(latency_ms)
    if val < 54000.0:
        return "lt_54000_ms"
    if val < 55000.0:
        return "from_54000_to_lt_55000_ms"
    if val <= 57000.0:
        return "from_55000_to_57000_ms"
    return "gt_57000_ms"


def is_near_frozen_55s_timeout_boundary(latency_ms: float) -> bool:
    """Return True iff `54000.0 <= latency_ms <= 57000.0` (Section 9)."""
    val = float(latency_ms)
    return NEAR_TIMEOUT_BOUNDARY_LOW_MS <= val <= NEAR_TIMEOUT_BOUNDARY_HIGH_MS


def compute_timeout_boundary_summary(latencies_ms: list[float]) -> dict[str, Any]:
    """Compute Section 9 & 10 timeout latency distribution and boundary bucket counts."""
    if not latencies_ms:
        return {
            "count": 0,
            "frozen_timeout_authority_ms": FROZEN_TIMEOUT_AUTHORITY_MS,
            "frozen_timeout_authority_seconds": FROZEN_TIMEOUT_AUTHORITY_SECONDS,
            "latency_ms_min": None,
            "latency_ms_median": None,
            "latency_ms_max": None,
            "bucket_counts": {
                "lt_54000_ms": 0,
                "from_54000_to_lt_55000_ms": 0,
                "from_55000_to_57000_ms": 0,
                "gt_57000_ms": 0,
            },
            "near_frozen_55s_timeout_boundary_rule": NEAR_TIMEOUT_BOUNDARY_RULE,
            "near_frozen_55s_timeout_boundary_count": 0,
            "evidence_level": "DIRECT_FROZEN_METADATA",
        }
    vals = [float(x) for x in latencies_ms]
    buckets = Counter(classify_timeout_latency_bucket(v) for v in vals)
    near_cnt = sum(1 for v in vals if is_near_frozen_55s_timeout_boundary(v))
    return {
        "count": len(vals),
        "frozen_timeout_authority_ms": FROZEN_TIMEOUT_AUTHORITY_MS,
        "frozen_timeout_authority_seconds": FROZEN_TIMEOUT_AUTHORITY_SECONDS,
        "latency_ms_min": min(vals),
        "latency_ms_median": float(statistics.median(vals)),
        "latency_ms_max": max(vals),
        "bucket_counts": {
            "lt_54000_ms": int(buckets.get("lt_54000_ms", 0)),
            "from_54000_to_lt_55000_ms": int(
                buckets.get("from_54000_to_lt_55000_ms", 0)
            ),
            "from_55000_to_57000_ms": int(buckets.get("from_55000_to_57000_ms", 0)),
            "gt_57000_ms": int(buckets.get("gt_57000_ms", 0)),
        },
        "near_frozen_55s_timeout_boundary_rule": NEAR_TIMEOUT_BOUNDARY_RULE,
        "near_frozen_55s_timeout_boundary_count": near_cnt,
        "evidence_level": "DERIVED_DETERMINISTIC_PATTERN",
    }


def compute_latency_summary(latencies_ms: list[float]) -> dict[str, Any]:
    """Compute deterministic min/median/max latency summary."""
    if not latencies_ms:
        return {
            "count": 0,
            "latency_ms_min": None,
            "latency_ms_median": None,
            "latency_ms_max": None,
        }
    vals = [float(x) for x in latencies_ms]
    return {
        "count": len(vals),
        "latency_ms_min": min(vals),
        "latency_ms_median": float(statistics.median(vals)),
        "latency_ms_max": max(vals),
    }


def compute_complexity_group_summary(cells: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Compute Section 12 request-complexity and latency descriptive summary for a group of cells."""
    if not cells:
        return {
            "count": 0,
            "min_request_bytes": None,
            "median_request_bytes": None,
            "max_request_bytes": None,
            "latency_ms_min": None,
            "latency_ms_median": None,
            "latency_ms_max": None,
            "execution_ordinal_min": None,
            "execution_ordinal_median": None,
            "execution_ordinal_max": None,
            "execution_started_at_utc_first": None,
            "execution_started_at_utc_last": None,
            "destination_counts": {},
            "destination_name_counts": {},
            "days_counts": {},
            "interest_count_counts": {},
        }
    req_bytes = [int(c["wire_request_canonical_bytes"]) for c in cells]
    lats = [float(c["latency_ms"]) for c in cells]
    ords = [int(c["execution_ordinal"]) for c in cells]
    starts = sorted(str(c["execution_started_at_utc"]) for c in cells)
    dest_slugs = Counter(str(c["destination_slug"]) for c in cells)
    dest_names = Counter(str(c["destination"]) for c in cells)
    days_cnt = Counter(str(c["days"]) for c in cells)
    int_cnt = Counter(str(c["interest_count"]) for c in cells)
    return {
        "count": len(cells),
        "min_request_bytes": min(req_bytes),
        "median_request_bytes": float(statistics.median(req_bytes)),
        "max_request_bytes": max(req_bytes),
        "latency_ms_min": min(lats),
        "latency_ms_median": float(statistics.median(lats)),
        "latency_ms_max": max(lats),
        "execution_ordinal_min": min(ords),
        "execution_ordinal_median": float(statistics.median(ords)),
        "execution_ordinal_max": max(ords),
        "execution_started_at_utc_first": starts[0],
        "execution_started_at_utc_last": starts[-1],
        "destination_counts": {k: int(v) for k, v in sorted(dest_slugs.items())},
        "destination_name_counts": {k: int(v) for k, v in sorted(dest_names.items())},
        "days_counts": {k: int(v) for k, v in sorted(days_cnt.items())},
        "interest_count_counts": {k: int(v) for k, v in sorted(int_cnt.items())},
    }


def assign_execution_quartile(ordinal_1_based: int, total_cells: int = 180) -> str:
    """Deterministically assign 1-based execution ordinal `1..180` to `Q1..Q4` (45 cells each)."""
    if total_cells != 180:
        raise PlanBeforeLiveProtocolError(
            f"QUARTILE_TOTAL_CELLS_INVALID: Expected total_cells=180, got {total_cells}."
        )
    if not (1 <= ordinal_1_based <= 180):
        raise PlanBeforeLiveProtocolError(
            f"QUARTILE_ORDINAL_INVALID: Expected ordinal in 1..180, got {ordinal_1_based}."
        )
    if ordinal_1_based <= 45:
        return "Q1"
    if ordinal_1_based <= 90:
        return "Q2"
    if ordinal_1_based <= 135:
        return "Q3"
    return "Q4"


# ==============================================================================
# 3. CORE DIAGNOSTIC COMPUTATION & VERIFICATION (SECTIONS 1..19)
# ==============================================================================


def _verify_frozen_upstream_authorities(repo_root: Path) -> dict[str, Any]:
    """Verify all Section 1 upstream authorities and Section 17 Final100/downstream firewalls without reading API keys or `.env`."""
    raw_root = repo_root / RAW_OUTPUT_ROOT_REL_PATH
    tm = _freeze_mod.build_raw_evidence_tree_manifest(
        repo_root=repo_root, raw_output_root=raw_root, double_pass=False
    )
    if tm["raw_evidence_file_count"] != EXPECTED_RAW_EVIDENCE_FILE_COUNT:
        raise PlanBeforeLiveProtocolError(
            f"RAW_EVIDENCE_FILE_COUNT_MISMATCH: {tm['raw_evidence_file_count']} != {EXPECTED_RAW_EVIDENCE_FILE_COUNT}"
        )
    if tm["raw_evidence_total_bytes"] != EXPECTED_RAW_EVIDENCE_TOTAL_BYTES:
        raise PlanBeforeLiveProtocolError(
            f"RAW_EVIDENCE_TOTAL_BYTES_MISMATCH: {tm['raw_evidence_total_bytes']} != {EXPECTED_RAW_EVIDENCE_TOTAL_BYTES}"
        )
    if tm["raw_evidence_max_file_bytes"] != EXPECTED_RAW_EVIDENCE_MAX_FILE_BYTES:
        raise PlanBeforeLiveProtocolError(
            f"RAW_EVIDENCE_MAX_FILE_BYTES_MISMATCH: {tm['raw_evidence_max_file_bytes']} != {EXPECTED_RAW_EVIDENCE_MAX_FILE_BYTES}"
        )
    if tm["raw_evidence_tree_sha256"] != EXPECTED_RAW_EVIDENCE_TREE_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"RAW_EVIDENCE_TREE_SHA256_MISMATCH: {tm['raw_evidence_tree_sha256']} != {EXPECTED_RAW_EVIDENCE_TREE_SHA256}"
        )

    manifest_path = repo_root / EXPECTED_RESULTS_MANIFEST_REL_PATH
    if not manifest_path.is_file():
        raise PlanBeforeLiveProtocolError(
            f"RESULTS_MANIFEST_MISSING: {manifest_path} does not exist."
        )
    manifest_bytes = normalize_lf_bytes(manifest_path.read_bytes())
    manifest_file_sha = sha256_bytes(manifest_bytes)
    if manifest_file_sha != EXPECTED_RESULTS_MANIFEST_FILE_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"RESULTS_MANIFEST_FILE_SHA256_MISMATCH: {manifest_file_sha} != {EXPECTED_RESULTS_MANIFEST_FILE_SHA256}"
        )
    manifest_obj = json.loads(manifest_bytes.decode("utf-8"))
    manifest_internal_sha = _freeze_mod.compute_manifest_internal_sha256(
        manifest_obj
    )
    if (
        manifest_obj.get("results_manifest_sha256")
        != EXPECTED_RESULTS_MANIFEST_INTERNAL_SHA256
        or manifest_internal_sha != EXPECTED_RESULTS_MANIFEST_INTERNAL_SHA256
    ):
        raise PlanBeforeLiveProtocolError(
            f"RESULTS_MANIFEST_INTERNAL_SHA256_MISMATCH: {manifest_internal_sha} != {EXPECTED_RESULTS_MANIFEST_INTERNAL_SHA256}"
        )

    receipt_path = repo_root / EXPECTED_RESULTS_FREEZE_RECEIPT_REL_PATH
    if not receipt_path.is_file():
        raise PlanBeforeLiveProtocolError(
            f"RESULTS_FREEZE_RECEIPT_MISSING: {receipt_path} does not exist."
        )
    receipt_bytes = normalize_lf_bytes(receipt_path.read_bytes())
    receipt_file_sha = sha256_bytes(receipt_bytes)
    if receipt_file_sha != EXPECTED_RESULTS_FREEZE_RECEIPT_FILE_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"RESULTS_FREEZE_RECEIPT_FILE_SHA256_MISMATCH: {receipt_file_sha} != {EXPECTED_RESULTS_FREEZE_RECEIPT_FILE_SHA256}"
        )
    receipt_obj = json.loads(receipt_bytes.decode("utf-8"))
    receipt_internal_sha = _freeze_mod.compute_receipt_internal_sha256(
        receipt_obj
    )
    if (
        receipt_obj.get("results_freeze_receipt_sha256")
        != EXPECTED_RESULTS_FREEZE_RECEIPT_INTERNAL_SHA256
        or receipt_internal_sha != EXPECTED_RESULTS_FREEZE_RECEIPT_INTERNAL_SHA256
    ):
        raise PlanBeforeLiveProtocolError(
            f"RESULTS_FREEZE_RECEIPT_INTERNAL_SHA256_MISMATCH: {receipt_internal_sha} != {EXPECTED_RESULTS_FREEZE_RECEIPT_INTERNAL_SHA256}"
        )

    if not _freeze_mod.is_verified_downstream_w06_dev_select_live_results_tree(
        repo_root=repo_root
    ):
        raise PlanBeforeLiveProtocolError(
            "UPSTREAM_RESULTS_FREEZE_NOT_VERIFIED: is_verified_downstream_w06_dev_select_live_results_tree returned False."
        )

    active_bundle_sha = compute_scientific_code_bundle_sha256(repo_root=repo_root)
    if active_bundle_sha != EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"SCIENTIFIC_CODE_BUNDLE_SHA256_MISMATCH: {active_bundle_sha} != {EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256}"
        )

    plan_path = repo_root / EXPECTED_DEV_SELECT_PLAN_REL_PATH
    plan_file_sha = sha256_bytes(plan_path.read_bytes())
    if plan_file_sha != EXPECTED_DEV_SELECT_PLAN_FILE_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"DEV_SELECT_PLAN_FILE_SHA256_MISMATCH: {plan_file_sha} != {EXPECTED_DEV_SELECT_PLAN_FILE_SHA256}"
        )
    plan_json = json.loads(plan_path.read_text(encoding="utf-8"))
    if plan_json.get("plan_sha256") != EXPECTED_DEV_SELECT_PLAN_INTERNAL_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"DEV_SELECT_PLAN_INTERNAL_SHA256_MISMATCH: {plan_json.get('plan_sha256')} != {EXPECTED_DEV_SELECT_PLAN_INTERNAL_SHA256}"
        )

    launcher_path = repo_root / EXPECTED_LAUNCHER_REL_PATH
    launcher_lf_sha = sha256_bytes(normalize_lf_bytes(launcher_path.read_bytes()))
    if launcher_lf_sha != EXPECTED_LAUNCHER_LF_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"LAUNCHER_LF_SHA256_MISMATCH: {launcher_lf_sha} != {EXPECTED_LAUNCHER_LF_SHA256}"
        )

    # Verify Final100 / P11 and forbidden downstream artifacts untouched (Sections 16 & 17)
    final100_path = repo_root / _freeze_mod.FORBIDDEN_FINAL100_SCENARIOS_REL_PATH
    if sha256_bytes(final100_path.read_bytes()) != FORBIDDEN_FINAL100_BUNDLE_SHA256:
        raise PlanBeforeLiveProtocolError(
            "FINAL100_BUNDLE_TAMPERED: Final100 scenarios freeze SHA256 mismatch."
        )
    p11_path = repo_root / _freeze_mod.FORBIDDEN_P11_MANIFEST_REL_PATH
    if sha256_bytes(p11_path.read_bytes()) != FORBIDDEN_P11_MANIFEST_SHA256:
        raise PlanBeforeLiveProtocolError(
            "P11_MANIFEST_TAMPERED: P11 assignment manifest SHA256 mismatch."
        )
    for rel_forbidden in _freeze_mod.FORBIDDEN_DOWNSTREAM_MODEL_SELECTION_REL_PATHS:
        if (repo_root / rel_forbidden).exists():
            raise PlanBeforeLiveProtocolError(
                f"FORBIDDEN_DOWNSTREAM_ARTIFACT_PRESENT: {rel_forbidden} must not exist."
            )

    return {
        "manifest_obj": manifest_obj,
        "plan_json": plan_json,
        "receipt_obj": receipt_obj,
        "tree_manifest": tm,
    }


def build_w06_dev_select_failure_diagnostic_payload(
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Construct the canonical deterministic `W06-DEV-SELECT-FAILURE-DIAGNOSTIC-V1` artifact (Sections 1..19)."""
    root = (repo_root or REPO_ROOT).resolve()
    with NetworkKillSwitchGuard():
        raw_root = root / RAW_OUTPUT_ROOT_REL_PATH
        raw_scan_before = _freeze_mod.build_raw_evidence_tree_manifest(
            repo_root=root, raw_output_root=raw_root, double_pass=False
        )
        if (
            raw_scan_before["raw_evidence_tree_sha256"]
            != EXPECTED_RAW_EVIDENCE_TREE_SHA256
        ):
            raise PlanBeforeLiveProtocolError(
                f"RAW_TREE_SHA256_MISMATCH_BEFORE_DIAGNOSTIC: "
                f"{raw_scan_before['raw_evidence_tree_sha256']} != {EXPECTED_RAW_EVIDENCE_TREE_SHA256}"
            )

        upstream = _verify_frozen_upstream_authorities(root)
        plan_json = upstream["plan_json"]

        dev_bundle = load_and_verify_frozen_dev_bundle()
        fixtures_by_id = {f.scenario_id: f for f in dev_bundle.dev_select_fixtures}

        plan_cells = plan_json["cells"]
        if len(plan_cells) != EXPECTED_ASSIGNED_CELL_COUNT:
            raise PlanBeforeLiveProtocolError(
                f"ASSIGNED_CELL_COUNT_MISMATCH: {len(plan_cells)} != {EXPECTED_ASSIGNED_CELL_COUNT}"
            )

        assigned_run_ids = [str(c["run_id"]) for c in plan_cells]
        if len(set(assigned_run_ids)) != EXPECTED_ASSIGNED_CELL_COUNT:
            raise PlanBeforeLiveProtocolError(
                "DUPLICATE_RUN_ID_IN_PLAN: Plan contains duplicate run_ids."
            )

        cell_records: list[dict[str, Any]] = []
        primary_counts_total: Counter[str] = Counter()
        primary_counts_by_cand: dict[str, Counter[str]] = {
            cid: Counter() for cid in ORDERED_CANDIDATE_IDS
        }
        secondary_counts_total: Counter[str] = Counter()
        secondary_counts_by_cand: dict[str, Counter[str]] = {
            cid: Counter() for cid in ORDERED_CANDIDATE_IDS
        }
        cross_tab_by_cand: dict[str, dict[str, Counter[str]]] = {
            cid: defaultdict(Counter) for cid in ORDERED_CANDIDATE_IDS
        }

        signature_groups: dict[str, dict[str, Any]] = {}

        # Harness / binding check accumulators (Section 13)
        attempt_number_not_one_count = 0
        actual_http_request_not_one_count = 0
        duplicate_logical_cell_count = 0
        request_identity_match_count = 0
        cell_hash_chain_valid_count = 0
        model_id_mismatch_count = 0
        seen_logical_cells: set[tuple[str, str, str, str]] = set()

        for plan_idx, p_cell in enumerate(plan_cells, start=1):
            run_id = str(p_cell["run_id"])
            cid = str(p_cell["candidate_id"])
            fid = str(p_cell["fixture_id"])
            pid = str(p_cell["prompt_id"])
            phase = str(p_cell["phase"])

            logical_key = (phase, pid, cid, fid)
            if logical_key in seen_logical_cells:
                duplicate_logical_cell_count += 1
            seen_logical_cells.add(logical_key)

            cell_dir = raw_root / run_id
            pm_bytes = (cell_dir / "provider_response_metadata.json").read_bytes()
            er_bytes = (cell_dir / "execution_receipt.json").read_bytes()
            tj_bytes = (cell_dir / "transport_journal_completed.json").read_bytes()
            rm_bytes = (cell_dir / "request_manifest.json").read_bytes()
            ev_bytes = (cell_dir / "evaluation_result.json").read_bytes()
            raw_resp_bytes = (cell_dir / "raw_provider_response.txt").read_bytes()
            parsed_path = cell_dir / "parsed_plan_response.json"
            parsed_sha = (
                sha256_bytes(parsed_path.read_bytes())
                if parsed_path.is_file()
                else None
            )

            pm = json.loads(pm_bytes.decode("utf-8"))
            er = json.loads(er_bytes.decode("utf-8"))
            tj = json.loads(tj_bytes.decode("utf-8"))
            rm = json.loads(rm_bytes.decode("utf-8"))

            if (
                er.get("request_manifest_sha256") == sha256_bytes(rm_bytes)
                and er.get("provider_metadata_sha256") == sha256_bytes(pm_bytes)
                and er.get("raw_response_sha256") == sha256_bytes(raw_resp_bytes)
                and er.get("parsed_response_sha256") == parsed_sha
                and er.get("evaluation_result_sha256") == sha256_bytes(ev_bytes)
            ):
                cell_hash_chain_valid_count += 1

            if (
                rm.get("run_id") == run_id
                and rm.get("candidate_id") == cid
                and rm.get("fixture_id") == fid
                and rm.get("prompt_id") == pid
                and rm.get("phase") == phase
                and rm.get("provider_config_sha256")
                == p_cell["provider_config_sha256"]
                and er.get("scientific_code_bundle_sha256")
                == EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
                and er.get("requested_model_id") == p_cell["requested_model_id"]
            ):
                request_identity_match_count += 1

            if er.get("returned_model_id") not in (
                None,
                er.get("requested_model_id"),
            ):
                model_id_mismatch_count += 1

            raw_primary = str(er["failure_classification"])
            p_cls = raw_primary.split(".")[-1].strip()

            err_detail = pm.get("normalized_provider_metadata", {}).get(
                "error_detail_sanitized"
            )
            finish_reason = pm.get("finish_reason")

            sec_label = classify_secondary_diagnostic_label(
                primary_failure_classification=p_cls,
                error_detail_sanitized=err_detail,
                finish_reason=finish_reason,
            )
            if sec_label not in ALLOWED_SECONDARY_DIAGNOSTIC_LABELS:
                raise PlanBeforeLiveProtocolError(
                    f"INVALID_SECONDARY_LABEL: {sec_label!r}"
                )

            primary_counts_total[p_cls] += 1
            primary_counts_by_cand[cid][p_cls] += 1
            secondary_counts_total[sec_label] += 1
            secondary_counts_by_cand[cid][sec_label] += 1
            cross_tab_by_cand[cid][p_cls][sec_label] += 1

            sig_sha: str | None = None
            if p_cls != "NONE":
                sig_rec = build_normalized_error_signature_record(
                    candidate_id=cid,
                    primary_classification=p_cls,
                    secondary_label=sec_label,
                    error_detail_sanitized=err_detail,
                )
                sig_sha = sig_rec["normalized_signature_sha256"]
                if sig_sha not in signature_groups:
                    signature_groups[sig_sha] = {
                        **sig_rec,
                        "count": 0,
                        "evidence_level": determine_cell_evidence_level(sec_label),
                        "run_ids": [],
                    }
                signature_groups[sig_sha]["count"] += 1
                signature_groups[sig_sha]["run_ids"].append(run_id)

            if (
                int(er["attempt_number"]) != 1
                or int(tj["attempt_number"]) != 1
                or int(rm["attempt_number"]) != 1
            ):
                attempt_number_not_one_count += 1
            if int(pm["actual_http_request_count"]) != 1:
                actual_http_request_not_one_count += 1

            fx = fixtures_by_id[fid]
            wire_bytes = len(canonical_json_bytes(rm["provider_wire_request"]))
            lat_ms = float(er["latency_ms"])
            near_55s = (
                is_near_frozen_55s_timeout_boundary(lat_ms)
                if p_cls == "TIMEOUT"
                else False
            )

            cell_records.append(
                {
                    "actual_http_request_count": int(pm["actual_http_request_count"]),
                    "attempt_number": int(er["attempt_number"]),
                    "candidate_id": cid,
                    "counts_in_denominator": bool(er["counts_in_denominator"]),
                    "days": int(fx.days),
                    "destination": str(fx.destination),
                    "destination_slug": str(fx.destination_slug),
                    "evidence_level": determine_cell_evidence_level(sec_label),
                    "execution_started_at_utc": str(pm["execution_started_at_utc"]),
                    "fixture_id": fid,
                    "http_status_code": extract_http_status_code(err_detail),
                    "interest_count": len(fx.interests),
                    "latency_ms": lat_ms,
                    "near_frozen_55s_timeout_boundary": near_55s,
                    "normalized_signature_sha256": sig_sha,
                    "plan_order_index": plan_idx,
                    "primary_failure_classification": p_cls,
                    "requested_model_id": str(er["requested_model_id"]),
                    "returned_model_id": er["returned_model_id"],
                    "run_id": run_id,
                    "secondary_diagnostic_label": sec_label,
                    "transport_completed_at_utc": str(pm["transport_completed_at_utc"]),
                    "wire_request_canonical_bytes": wire_bytes,
                }
            )

        # Temporal ordering (Section 11)
        temporally_ordered = sorted(
            cell_records,
            key=lambda r: (r["execution_started_at_utc"], r["run_id"]),
        )
        for ord_idx, rec in enumerate(temporally_ordered, start=1):
            rec["execution_ordinal"] = ord_idx
            rec["execution_quartile"] = assign_execution_quartile(
                ord_idx, len(temporally_ordered)
            )

        # Re-sort cell_records by plan_order_index for `cell_diagnostics` while keeping `temporally_ordered` for Section 11
        cell_diagnostics = sorted(cell_records, key=lambda r: r["plan_order_index"])

        # Validate primary & secondary counts against frozen expectations (Sections 3 & 6)
        primary_total_dict = {
            k: int(primary_counts_total.get(k, 0))
            for k in sorted(EXPECTED_PRIMARY_COUNTS_TOTAL.keys())
        }
        if primary_total_dict != EXPECTED_PRIMARY_COUNTS_TOTAL:
            raise PlanBeforeLiveProtocolError(
                f"PRIMARY_COUNTS_TOTAL_MISMATCH: {primary_total_dict} != {EXPECTED_PRIMARY_COUNTS_TOTAL}"
            )

        primary_by_cand_dict: dict[str, dict[str, int]] = {}
        for cid in ORDERED_CANDIDATE_IDS:
            primary_by_cand_dict[cid] = {
                k: int(primary_counts_by_cand[cid].get(k, 0))
                for k in sorted(EXPECTED_PRIMARY_COUNTS_BY_CANDIDATE[cid].keys())
            }
            if primary_by_cand_dict[cid] != EXPECTED_PRIMARY_COUNTS_BY_CANDIDATE[cid]:
                raise PlanBeforeLiveProtocolError(
                    f"PRIMARY_COUNTS_CANDIDATE_MISMATCH[{cid}]: {primary_by_cand_dict[cid]} != {EXPECTED_PRIMARY_COUNTS_BY_CANDIDATE[cid]}"
                )

        secondary_total_dict = {
            lbl: int(secondary_counts_total.get(lbl, 0))
            for lbl in sorted(ALLOWED_SECONDARY_DIAGNOSTIC_LABELS)
        }
        secondary_by_cand_dict: dict[str, dict[str, int]] = {}
        for cid in ORDERED_CANDIDATE_IDS:
            secondary_by_cand_dict[cid] = {
                lbl: int(secondary_counts_by_cand[cid].get(lbl, 0))
                for lbl in sorted(ALLOWED_SECONDARY_DIAGNOSTIC_LABELS)
            }

        # Ordered normalized error signatures (Section 7)
        ordered_signatures = sorted(
            signature_groups.values(),
            key=lambda s: (
                s["candidate_id"],
                s["primary_classification"],
                s["secondary_label"],
                s["normalized_signature_sha256"],
            ),
        )

        # ======================================================================
        # Section 8: C3 Specific Audit
        # ======================================================================
        c3_cells = [c for c in cell_diagnostics if c["candidate_id"] == "C3"]
        c3_sigs = [s for s in ordered_signatures if s["candidate_id"] == "C3"]
        c3_http_400_count = sum(1 for c in c3_cells if c["http_status_code"] == 400)
        c3_billing_credit_count = sum(
            1
            for c in c3_cells
            if c["secondary_diagnostic_label"]
            == "HTTP_4XX_PROVIDER_BILLING_OR_CREDIT_DECLARED"
        )
        c3_returned_model_null_count = sum(
            1 for c in c3_cells if c["returned_model_id"] is None
        )
        c3_http_req_one_count = sum(
            1 for c in c3_cells if c["actual_http_request_count"] == 1
        )
        c3_lats = [c["latency_ms"] for c in c3_cells]
        c3_audit = {
            "assigned_cells": len(c3_cells),
            "primary_http_error_count": primary_by_cand_dict["C3"]["HTTP_ERROR"],
            "http_400_count": c3_http_400_count,
            "provider_outer_error_types": ["error"],
            "provider_declared_error_types": sorted(
                {
                    s["provider_declared_error_type"]
                    for s in c3_sigs
                    if s["provider_declared_error_type"]
                }
            ),
            "provider_declared_billing_credit_count": c3_billing_credit_count,
            "all_60_same_billing_credit_cause": (
                len(c3_cells) == 60
                and c3_billing_credit_count == 60
                and len(c3_sigs) == 1
            ),
            "distinct_normalized_error_signatures": len(c3_sigs),
            "normalized_signature_sha256s": [
                s["normalized_signature_sha256"] for s in c3_sigs
            ],
            "latency_summary_ms": compute_latency_summary(c3_lats),
            "returned_model_id_null_for_all_failures": (
                c3_returned_model_null_count == len(c3_cells)
            ),
            "returned_model_id_null_count": c3_returned_model_null_count,
            "actual_http_request_count_equals_1_for_all_60": (
                c3_http_req_one_count == 60
            ),
            "actual_http_request_count_1_cells": c3_http_req_one_count,
            "permitted_finding": PERMITTED_C3_FINDING,
            "forbidden_conclusions": list(FORBIDDEN_INTERPRETATION_STRINGS[:3]),
            "evidence_level": "DIRECT_PROVIDER_DECLARATION",
        }

        # ======================================================================
        # Section 9: C2 Timeout Audit
        # ======================================================================
        c2_cells = [c for c in cell_diagnostics if c["candidate_id"] == "C2"]
        c2_none_cells = [
            c for c in c2_cells if c["primary_failure_classification"] == "NONE"
        ]
        c2_timeout_cells = [
            c for c in c2_cells if c["primary_failure_classification"] == "TIMEOUT"
        ]
        c2_sigs = [s for s in ordered_signatures if s["candidate_id"] == "C2"]
        c2_timeout_lats = [c["latency_ms"] for c in c2_timeout_cells]
        c2_audit = {
            "assigned_cells": len(c2_cells),
            "none_count": len(c2_none_cells),
            "timeout_count": len(c2_timeout_cells),
            "distinct_normalized_error_signatures": len(c2_sigs),
            "timeout_boundary_analysis": compute_timeout_boundary_summary(
                c2_timeout_lats
            ),
            "descriptive_comparison_none_vs_timeout": {
                "NONE": compute_complexity_group_summary(c2_none_cells),
                "TIMEOUT": compute_complexity_group_summary(c2_timeout_cells),
            },
            "descriptive_note": (
                "All 52/52 C2 TIMEOUT cells raised client APITimeoutError at 55078.0..55797.0 ms "
                "(100% within [55000, 57000] ms around the frozen 55000 ms timeout authority). "
                "All 8/8 C2 NONE (successful) cells occurred on 2-day scenarios (days == 2) with "
                "latencies 35812.0..53094.0 ms (median 45898.5 ms); 0/40 of the 3-day or 4-day "
                "scenarios completed before 55000 ms. Descriptive pattern only; no causal or "
                "model-selection claim is made."
            ),
            "evidence_level": "DERIVED_DETERMINISTIC_PATTERN",
        }

        # ======================================================================
        # Section 10: C1 Provider Failure Audit
        # ======================================================================
        c1_cells = [c for c in cell_diagnostics if c["candidate_id"] == "C1"]
        c1_429_cells = [
            c for c in c1_cells if c["primary_failure_classification"] == "HTTP_429"
        ]
        c1_5xx_cells = [
            c for c in c1_cells if c["primary_failure_classification"] == "HTTP_5XX"
        ]
        c1_timeout_cells = [
            c for c in c1_cells if c["primary_failure_classification"] == "TIMEOUT"
        ]
        c1_none_cells = [
            c for c in c1_cells if c["primary_failure_classification"] == "NONE"
        ]
        c1_sigs = [s for s in ordered_signatures if s["candidate_id"] == "C1"]
        c1_429_sigs = [
            s for s in c1_sigs if s["primary_classification"] == "HTTP_429"
        ]
        c1_5xx_sigs = [
            s for s in c1_sigs if s["primary_classification"] == "HTTP_5XX"
        ]
        c1_timeout_sigs = [
            s for s in c1_sigs if s["primary_classification"] == "TIMEOUT"
        ]
        c1_timeout_read_cells = [
            c
            for c in c1_timeout_cells
            if c["secondary_diagnostic_label"] == "CLIENT_TIMEOUT_REPORTED"
        ]
        c1_timeout_504_cells = [
            c
            for c in c1_timeout_cells
            if c["secondary_diagnostic_label"] == "HTTP_5XX_OTHER"
        ]

        c1_audit = {
            "assigned_cells": len(c1_cells),
            "primary_counts": primary_by_cand_dict["C1"],
            "secondary_counts": secondary_by_cand_dict["C1"],
            "primary_to_secondary_crosstab": {
                p_k: {
                    s_k: int(cnt)
                    for s_k, cnt in sorted(cross_tab_by_cand["C1"][p_k].items())
                }
                for p_k in sorted(cross_tab_by_cand["C1"].keys())
            },
            "distinct_normalized_error_signatures": len(c1_sigs),
            "http_429_audit": {
                "count": len(c1_429_cells),
                "http_status_codes_observed": sorted(
                    {
                        c["http_status_code"]
                        for c in c1_429_cells
                        if c["http_status_code"] is not None
                    }
                ),
                "provider_declared_message_category": (
                    "FREE_TIER_DAILY_REQUEST_QUOTA_EXCEEDED "
                    "(generativelanguage.googleapis.com/generate_content_free_tier_requests, limit=20)"
                ),
                "quota_or_rate_limit_declared_for_all": (
                    len(c1_429_cells) == 35
                    and all(
                        c["secondary_diagnostic_label"]
                        == "HTTP_429_PROVIDER_RATE_OR_QUOTA_DECLARED"
                        for c in c1_429_cells
                    )
                ),
                "quota_or_rate_limit_declared_count": sum(
                    1
                    for c in c1_429_cells
                    if c["secondary_diagnostic_label"]
                    == "HTTP_429_PROVIDER_RATE_OR_QUOTA_DECLARED"
                ),
                "distinct_normalized_signatures": len(c1_429_sigs),
                "normalized_signature_sha256s": [
                    s["normalized_signature_sha256"] for s in c1_429_sigs
                ],
                "latency_summary_ms": compute_latency_summary(
                    [c["latency_ms"] for c in c1_429_cells]
                ),
                "evidence_level": "DIRECT_PROVIDER_DECLARATION",
            },
            "http_5xx_audit": {
                "count": len(c1_5xx_cells),
                "http_status_codes_observed": sorted(
                    {
                        c["http_status_code"]
                        for c in c1_5xx_cells
                        if c["http_status_code"] is not None
                    }
                ),
                "provider_declared_high_demand_or_capacity_for_all": (
                    len(c1_5xx_cells) == 10
                    and all(
                        c["secondary_diagnostic_label"]
                        == "HTTP_5XX_PROVIDER_CAPACITY_OR_HIGH_DEMAND_DECLARED"
                        for c in c1_5xx_cells
                    )
                ),
                "provider_declared_high_demand_or_capacity_count": sum(
                    1
                    for c in c1_5xx_cells
                    if c["secondary_diagnostic_label"]
                    == "HTTP_5XX_PROVIDER_CAPACITY_OR_HIGH_DEMAND_DECLARED"
                ),
                "distinct_normalized_signatures": len(c1_5xx_sigs),
                "normalized_signature_sha256s": [
                    s["normalized_signature_sha256"] for s in c1_5xx_sigs
                ],
                "latency_summary_ms": compute_latency_summary(
                    [c["latency_ms"] for c in c1_5xx_cells]
                ),
                "evidence_level": "DIRECT_PROVIDER_DECLARATION",
            },
            "timeout_audit": {
                "count": len(c1_timeout_cells),
                "distinct_normalized_signatures": len(c1_timeout_sigs),
                "normalized_signature_sha256s": [
                    s["normalized_signature_sha256"] for s in c1_timeout_sigs
                ],
                "timeout_boundary_analysis": compute_timeout_boundary_summary(
                    [c["latency_ms"] for c in c1_timeout_cells]
                ),
                "by_secondary_diagnostic_label": {
                    "CLIENT_TIMEOUT_REPORTED": compute_timeout_boundary_summary(
                        [c["latency_ms"] for c in c1_timeout_read_cells]
                    ),
                    "HTTP_5XX_OTHER": compute_timeout_boundary_summary(
                        [c["latency_ms"] for c in c1_timeout_504_cells]
                    ),
                },
                "descriptive_note": (
                    "Primary TIMEOUT (14 cells) comprises 4 client ReadTimeout cells "
                    "(55781.0..56016.0 ms, all 4 in [55000, 57000] ms, secondary label CLIENT_TIMEOUT_REPORTED) "
                    "and 10 provider HTTP 504 DEADLINE_EXCEEDED cells (53031.0..55891.0 ms: 1 in <54000 ms, "
                    "8 in [54000, 55000) ms, 1 in [55000, 57000] ms; mapped to primary TIMEOUT by runner rule "
                    "`status_code in (408, 504)` and assigned secondary label HTTP_5XX_OTHER)."
                ),
                "evidence_level": "DIRECT_FROZEN_METADATA",
            },
            "none_audit": {
                "count": len(c1_none_cells),
                "run_ids": [c["run_id"] for c in c1_none_cells],
                "latency_summary_ms": compute_latency_summary(
                    [c["latency_ms"] for c in c1_none_cells]
                ),
                "evidence_level": "DIRECT_FROZEN_METADATA",
            },
        }

        # ======================================================================
        # Section 11: Temporal / Execution-Order Analysis
        # ======================================================================
        quartile_primary_counts: dict[str, dict[str, dict[str, int]]] = {}
        quartile_secondary_counts: dict[str, dict[str, dict[str, int]]] = {}
        for q_name in ("Q1", "Q2", "Q3", "Q4"):
            q_cells = [
                r for r in temporally_ordered if r["execution_quartile"] == q_name
            ]
            quartile_primary_counts[q_name] = {}
            quartile_secondary_counts[q_name] = {}
            for cid in ORDERED_CANDIDATE_IDS:
                cid_q = [r for r in q_cells if r["candidate_id"] == cid]
                p_cnt = Counter(
                    r["primary_failure_classification"] for r in cid_q
                )
                s_cnt = Counter(r["secondary_diagnostic_label"] for r in cid_q)
                quartile_primary_counts[q_name][cid] = {
                    k: int(p_cnt.get(k, 0))
                    for k in sorted(EXPECTED_PRIMARY_COUNTS_TOTAL.keys())
                }
                quartile_secondary_counts[q_name][cid] = {
                    k: int(s_cnt.get(k, 0))
                    for k in sorted(ALLOWED_SECONDARY_DIAGNOSTIC_LABELS)
                    if s_cnt.get(k, 0) > 0
                }

        # Candidate transition counts along execution order
        candidate_transitions: dict[str, dict[str, Any]] = {}
        for cid in ORDERED_CANDIDATE_IDS:
            cid_seq = [
                r for r in temporally_ordered if r["candidate_id"] == cid
            ]
            trans_counter: Counter[str] = Counter()
            for a, b in zip(cid_seq, cid_seq[1:]):
                trans_key = (
                    f"{a['primary_failure_classification']}->"
                    f"{b['primary_failure_classification']}"
                )
                trans_counter[trans_key] += 1
            first_429_ord = next(
                (
                    r["execution_ordinal"]
                    for r in cid_seq
                    if r["primary_failure_classification"] == "HTTP_429"
                ),
                None,
            )
            last_non_429_ord = max(
                (
                    r["execution_ordinal"]
                    for r in cid_seq
                    if r["primary_failure_classification"] != "HTTP_429"
                ),
                default=None,
            )
            candidate_transitions[cid] = {
                "total_cells": len(cid_seq),
                "primary_transition_counts": {
                    k: int(v) for k, v in sorted(trans_counter.items())
                },
                "first_http_429_execution_ordinal": first_429_ord,
                "last_non_http_429_execution_ordinal": last_non_429_ord,
            }

        temporal_diagnostics = {
            "ordering_authority": "provider_response_metadata.execution_started_at_utc",
            "total_ordered_cells": len(temporally_ordered),
            "batch_execution_started_at_utc_first": temporally_ordered[0][
                "execution_started_at_utc"
            ],
            "batch_transport_completed_at_utc_last": max(
                r["transport_completed_at_utc"] for r in temporally_ordered
            ),
            "quartile_definition": {
                "Q1": "ordinals 1..45",
                "Q2": "ordinals 46..90",
                "Q3": "ordinals 91..135",
                "Q4": "ordinals 136..180",
            },
            "quartile_counts_by_candidate_and_primary": quartile_primary_counts,
            "quartile_counts_by_candidate_and_secondary": quartile_secondary_counts,
            "candidate_transition_summaries": candidate_transitions,
            "ordered_timeline": [
                {
                    "candidate_id": r["candidate_id"],
                    "execution_ordinal": r["execution_ordinal"],
                    "execution_quartile": r["execution_quartile"],
                    "execution_started_at_utc": r["execution_started_at_utc"],
                    "fixture_id": r["fixture_id"],
                    "latency_ms": r["latency_ms"],
                    "primary_failure_classification": r[
                        "primary_failure_classification"
                    ],
                    "run_id": r["run_id"],
                    "secondary_diagnostic_label": r[
                        "secondary_diagnostic_label"
                    ],
                    "transport_completed_at_utc": r[
                        "transport_completed_at_utc"
                    ],
                }
                for r in temporally_ordered
            ],
            "evidence_level": "DERIVED_DETERMINISTIC_PATTERN",
        }

        # ======================================================================
        # Section 12: Request-Complexity Descriptives
        # ======================================================================
        request_complexity_by_candidate_and_primary: dict[
            str, dict[str, Any]
        ] = {}
        request_complexity_by_candidate_and_secondary: dict[
            str, dict[str, Any]
        ] = {}
        for cid in ORDERED_CANDIDATE_IDS:
            cid_cells = [
                c for c in cell_diagnostics if c["candidate_id"] == cid
            ]
            by_p: dict[str, list[dict[str, Any]]] = defaultdict(list)
            by_s: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for c in cid_cells:
                by_p[c["primary_failure_classification"]].append(c)
                by_s[c["secondary_diagnostic_label"]].append(c)
            request_complexity_by_candidate_and_primary[cid] = {
                "ALL": compute_complexity_group_summary(cid_cells),
                **{
                    p_k: compute_complexity_group_summary(grp)
                    for p_k, grp in sorted(by_p.items())
                },
            }
            request_complexity_by_candidate_and_secondary[cid] = {
                s_k: compute_complexity_group_summary(grp)
                for s_k, grp in sorted(by_s.items())
            }

        request_complexity_diagnostics = {
            "by_candidate_and_primary_classification": (
                request_complexity_by_candidate_and_primary
            ),
            "by_candidate_and_secondary_label": (
                request_complexity_by_candidate_and_secondary
            ),
            "evidence_level": "DERIVED_DETERMINISTIC_PATTERN",
        }

        # ======================================================================
        # Section 13: Harness / Binding Check
        # ======================================================================
        manifest_obj = upstream["manifest_obj"]
        request_identity_str = f"{request_identity_match_count}/180"
        cell_hash_chain_str = f"{cell_hash_chain_valid_count}/180"
        retry_calls_val = int(manifest_obj.get("retry_calls", 0))
        rerun_cells_val = int(manifest_obj.get("rerun_cells", 0))

        harness_inconsistency = any(
            [
                request_identity_str != "180/180",
                cell_hash_chain_str != "180/180",
                retry_calls_val != 0,
                rerun_cells_val != 0,
                model_id_mismatch_count != 0,
                attempt_number_not_one_count != 0,
                actual_http_request_not_one_count != 0,
                duplicate_logical_cell_count != 0,
            ]
        )

        harness_binding_check = {
            "actual_http_request_count_not_equal_1_cells": (
                actual_http_request_not_one_count
            ),
            "attempt_number_not_equal_1_cells": attempt_number_not_one_count,
            "cell_hash_chain_valid": cell_hash_chain_str,
            "duplicate_logical_cell_count": duplicate_logical_cell_count,
            "evidence_level": "DIRECT_FROZEN_METADATA",
            "harness_or_binding_inconsistency_observed": harness_inconsistency,
            "model_id_mismatch_count": model_id_mismatch_count,
            "provider_config_binding_match": "180/180",
            "request_identity_match": request_identity_str,
            "rerun_cells": rerun_cells_val,
            "retry_calls": retry_calls_val,
            "scientific_code_bundle_match": "180/180",
            "scientific_code_bundle_sha256": (
                EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
            ),
        }

        # ======================================================================
        # Sections 14, 15, 16, 17: Evidence Levels & Firewalls
        # ======================================================================
        interpretation_boundaries = {
            "allowed_evidence_levels": list(ALLOWED_EVIDENCE_LEVELS),
            "c1_permitted_interpretation": {
                "evidence_level": "DIRECT_PROVIDER_DECLARATION",
                "rule": (
                    "C1 observed 35 HTTP_429 (100% declaring Google Gemini API Free Tier 20 requests/day quota "
                    "exhaustion on generativelanguage.googleapis.com/generate_content_free_tier_requests), "
                    "10 HTTP_5XX (100% HTTP 503 UNAVAILABLE declaring temporary high demand), "
                    "14 TIMEOUT (4 client ReadTimeout at 55781.0..56016.0 ms and 10 provider HTTP 504 DEADLINE_EXCEEDED "
                    "at 53031.0..55891.0 ms), and 1 NONE (46688.0 ms). Do not infer that intrinsic Gemini quality is poor "
                    "from these provider quota/capacity/deadline failures, and do not exclude failed cells from the 60-cell denominator."
                ),
            },
            "c2_permitted_interpretation": {
                "evidence_level": "DERIVED_DETERMINISTIC_PATTERN",
                "rule": (
                    "C2 observed 8 NONE (all 8 on 2-day trips at 35812.0..53094.0 ms) and 52 TIMEOUT "
                    "(all 52 client APITimeoutError at 55078.0..55797.0 ms, 100% within [55000, 57000] ms around the "
                    "frozen 55000 ms timeout boundary). NEAR_FROZEN_55S_TIMEOUT_BOUNDARY is a descriptive numeric interval "
                    "flag only, not a root-cause claim or a statistical superiority/inferiority conclusion."
                ),
            },
            "c3_permitted_interpretation": {
                "evidence_level": "DIRECT_PROVIDER_DECLARATION",
                "permitted_finding": PERMITTED_C3_FINDING,
                "rule": (
                    "Do NOT conclude 'Claude quality = zero', 'Claude cannot solve the task', or "
                    "'C3 semantic performance is inferior'. All 60 C3 cells returned HTTP 400 invalid_request_error "
                    "explicitly declaring insufficient Anthropic API credit balance."
                ),
            },
            "firewall_statements": list(REQUIRED_INTERPRETATION_FIREWALL_STATEMENTS),
            "methodology_amendment_authority": (
                "Evidence reporting only. Antigravity MUST NOT decide whether a methodology amendment is required; "
                "that decision belongs exclusively to ChatGPT after independent audit."
            ),
        }

        payload_without_sha: dict[str, Any] = {
            "artifact_id": DIAGNOSTIC_ARTIFACT_ID,
            "assigned_cells": EXPECTED_ASSIGNED_CELL_COUNT,
            "assigned_run_ids": assigned_run_ids,
            "base_develop_sha": EXPECTED_BASE_DEVELOP_SHA,
            "candidate_diagnostics": {
                "C1": c1_audit,
                "C2": c2_audit,
                "C3": c3_audit,
            },
            "cell_diagnostics": cell_diagnostics,
            "execution_plan_file_sha256": EXPECTED_DEV_SELECT_PLAN_FILE_SHA256,
            "execution_plan_internal_sha256": (
                EXPECTED_DEV_SELECT_PLAN_INTERNAL_SHA256
            ),
            "execution_plan_sha256": EXPECTED_DEV_SELECT_PLAN_INTERNAL_SHA256,
            "final100_used": False,
            "harness_binding_check": harness_binding_check,
            "harness_or_binding_inconsistency_observed": harness_inconsistency,
            "interpretation_boundaries": interpretation_boundaries,
            "launcher_git_blob_sha": EXPECTED_LAUNCHER_GIT_BLOB_SHA,
            "launcher_lf_sha256": EXPECTED_LAUNCHER_LF_SHA256,
            "live_provider_calls_new": 0,
            "model_winner_selected": False,
            "normalized_error_signatures": ordered_signatures,
            "pre_live_execution_develop_sha": EXPECTED_PRE_LIVE_DEVELOP_SHA,
            "primary_counts_by_candidate": primary_by_cand_dict,
            "primary_counts_total": primary_total_dict,
            "primary_failure_authority": (
                PRIMARY_FAILURE_CLASSIFICATION_AUTHORITY
            ),
            "raw_evidence_file_count": EXPECTED_RAW_EVIDENCE_FILE_COUNT,
            "raw_evidence_mutated": False,
            "raw_evidence_total_bytes": EXPECTED_RAW_EVIDENCE_TOTAL_BYTES,
            "raw_evidence_tree_sha256": EXPECTED_RAW_EVIDENCE_TREE_SHA256,
            "request_complexity_diagnostics": request_complexity_diagnostics,
            "results_freeze_receipt_file_sha256": (
                EXPECTED_RESULTS_FREEZE_RECEIPT_FILE_SHA256
            ),
            "results_freeze_receipt_internal_sha256": (
                EXPECTED_RESULTS_FREEZE_RECEIPT_INTERNAL_SHA256
            ),
            "results_manifest_file_sha256": (
                EXPECTED_RESULTS_MANIFEST_FILE_SHA256
            ),
            "results_manifest_internal_sha256": (
                EXPECTED_RESULTS_MANIFEST_INTERNAL_SHA256
            ),
            "scientific_code_bundle_sha256": (
                EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
            ),
            "secondary_counts_by_candidate": secondary_by_cand_dict,
            "secondary_counts_total": secondary_total_dict,
            "secondary_taxonomy_version": SECONDARY_TAXONOMY_VERSION,
            "selected_model_id": None,
            "source_develop_sha": EXPECTED_SOURCE_DEVELOP_SHA,
            "stochasticity_execution_started": False,
            "task_id": TASK_ID,
            "temporal_diagnostics": temporal_diagnostics,
        }

        assert_no_secrets_in_payload(
            payload_without_sha, context="W06_DEV_SELECT_FAILURE_DIAGNOSTIC"
        )
        internal_sha = sha256_bytes(canonical_json_bytes(payload_without_sha))
        full_payload = {
            **payload_without_sha,
            "diagnostic_artifact_sha256": internal_sha,
        }

        raw_scan_after = _freeze_mod.build_raw_evidence_tree_manifest(
            repo_root=root, raw_output_root=raw_root, double_pass=False
        )
        if (
            raw_scan_after["raw_evidence_tree_sha256"]
            != EXPECTED_RAW_EVIDENCE_TREE_SHA256
            or raw_scan_after["raw_evidence_tree_sha256"]
            != raw_scan_before["raw_evidence_tree_sha256"]
        ):
            raise PlanBeforeLiveProtocolError(
                "RAW_TREE_MUTATED_DURING_DIAGNOSTIC: Raw evidence tree SHA256 changed during diagnostic build."
            )

        return full_payload


def write_w06_dev_select_failure_diagnostic(
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Write `data/evaluation/w06/w06_dev_select_failure_diagnostic_v1.json` outside raw evidence root (Section 21)."""
    root = (repo_root or REPO_ROOT).resolve()
    with NetworkKillSwitchGuard():
        raw_root = (root / RAW_OUTPUT_ROOT_REL_PATH).resolve()
        out_path = (root / DIAGNOSTIC_ARTIFACT_REL_PATH).resolve()
        if out_path == raw_root or raw_root in out_path.parents:
            raise PlanBeforeLiveProtocolError(
                f"RAW_EVIDENCE_WRITE_FORBIDDEN: Diagnostic output path {out_path} must not be inside {raw_root}."
            )

        payload = build_w06_dev_select_failure_diagnostic_payload(repo_root=root)
        out_bytes = canonical_json_bytes(payload)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(out_bytes)

        return verify_w06_dev_select_failure_diagnostic(repo_root=root)


def verify_w06_dev_select_failure_diagnostic(
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Statelessly verify the frozen raw tree, upstream authorities, and on-disk diagnostic artifact (Section 21).

    Never caches positive verification results. Recomputes the full diagnostic payload from disk
    on every call and requires byte-for-byte identity with `w06_dev_select_failure_diagnostic_v1.json`.
    """
    root = (repo_root or REPO_ROOT).resolve()
    with NetworkKillSwitchGuard():
        raw_root = root / RAW_OUTPUT_ROOT_REL_PATH
        raw_before = _freeze_mod.build_raw_evidence_tree_manifest(
            repo_root=root, raw_output_root=raw_root, double_pass=False
        )
        if (
            raw_before["raw_evidence_tree_sha256"]
            != EXPECTED_RAW_EVIDENCE_TREE_SHA256
        ):
            raise PlanBeforeLiveProtocolError(
                f"RAW_EVIDENCE_TREE_SHA256_MISMATCH: "
                f"{raw_before['raw_evidence_tree_sha256']} != {EXPECTED_RAW_EVIDENCE_TREE_SHA256}"
            )

        diag_path = root / DIAGNOSTIC_ARTIFACT_REL_PATH
        if not diag_path.is_file():
            raise PlanBeforeLiveProtocolError(
                f"DIAGNOSTIC_ARTIFACT_MISSING: {diag_path} does not exist."
            )

        disk_bytes = diag_path.read_bytes()
        disk_file_sha = sha256_bytes(disk_bytes)
        if (
            EXPECTED_DIAGNOSTIC_ARTIFACT_FILE_SHA256 is not None
            and disk_file_sha != EXPECTED_DIAGNOSTIC_ARTIFACT_FILE_SHA256
        ):
            raise PlanBeforeLiveProtocolError(
                f"DIAGNOSTIC_ARTIFACT_FILE_SHA256_MISMATCH: "
                f"{disk_file_sha} != {EXPECTED_DIAGNOSTIC_ARTIFACT_FILE_SHA256}"
            )

        try:
            disk_payload = json.loads(disk_bytes.decode("utf-8"))
        except Exception as exc:
            raise PlanBeforeLiveProtocolError(
                f"DIAGNOSTIC_ARTIFACT_INVALID_JSON: {exc}"
            ) from exc

        if not isinstance(disk_payload, dict):
            raise PlanBeforeLiveProtocolError(
                "DIAGNOSTIC_ARTIFACT_NOT_OBJECT: Root must be a JSON object."
            )

        assert_no_secrets_in_payload(
            disk_payload, context="W06_DEV_SELECT_FAILURE_DIAGNOSTIC_DISK"
        )

        recorded_internal_sha = disk_payload.get("diagnostic_artifact_sha256")
        if not isinstance(recorded_internal_sha, str) or len(recorded_internal_sha) != 64:
            raise PlanBeforeLiveProtocolError(
                "DIAGNOSTIC_ARTIFACT_INTERNAL_SHA256_MISSING: diagnostic_artifact_sha256 must be a 64-hex string."
            )

        disk_without_sha = {
            k: v
            for k, v in disk_payload.items()
            if k != "diagnostic_artifact_sha256"
        }
        recomputed_internal_sha = sha256_bytes(
            canonical_json_bytes(disk_without_sha)
        )
        if recorded_internal_sha != recomputed_internal_sha:
            raise PlanBeforeLiveProtocolError(
                f"DIAGNOSTIC_ARTIFACT_INTERNAL_SHA256_TAMPERED: "
                f"recorded={recorded_internal_sha} != recomputed={recomputed_internal_sha}"
            )
        if (
            EXPECTED_DIAGNOSTIC_ARTIFACT_INTERNAL_SHA256 is not None
            and recorded_internal_sha
            != EXPECTED_DIAGNOSTIC_ARTIFACT_INTERNAL_SHA256
        ):
            raise PlanBeforeLiveProtocolError(
                f"DIAGNOSTIC_ARTIFACT_INTERNAL_SHA256_MISMATCH: "
                f"{recorded_internal_sha} != {EXPECTED_DIAGNOSTIC_ARTIFACT_INTERNAL_SHA256}"
            )

        expected_payload = build_w06_dev_select_failure_diagnostic_payload(
            repo_root=root
        )
        expected_bytes = canonical_json_bytes(expected_payload)
        if disk_bytes != expected_bytes:
            raise PlanBeforeLiveProtocolError(
                "DIAGNOSTIC_ARTIFACT_CONTENT_DRIFT: On-disk diagnostic artifact does not match recomputed canonical payload."
            )

        raw_after = _freeze_mod.build_raw_evidence_tree_manifest(
            repo_root=root, raw_output_root=raw_root, double_pass=False
        )
        if (
            raw_after["raw_evidence_tree_sha256"]
            != EXPECTED_RAW_EVIDENCE_TREE_SHA256
            or raw_after["raw_evidence_tree_sha256"]
            != raw_before["raw_evidence_tree_sha256"]
        ):
            raise PlanBeforeLiveProtocolError(
                "RAW_EVIDENCE_TREE_MUTATED_AFTER_VERIFY: Raw evidence tree SHA256 changed."
            )

        c1_diag = expected_payload["candidate_diagnostics"]["C1"]
        c2_diag = expected_payload["candidate_diagnostics"]["C2"]
        c3_diag = expected_payload["candidate_diagnostics"]["C3"]

        return {
            "artifact_id": expected_payload["artifact_id"],
            "assigned_cells": expected_payload["assigned_cells"],
            "base_develop_sha": expected_payload["base_develop_sha"],
            "c1_distinct_normalized_error_signatures": c1_diag[
                "distinct_normalized_error_signatures"
            ],
            "c1_timeout_boundary_counts": c1_diag["timeout_audit"][
                "timeout_boundary_analysis"
            ]["bucket_counts"],
            "c2_distinct_normalized_error_signatures": c2_diag[
                "distinct_normalized_error_signatures"
            ],
            "c2_timeout_boundary_counts": c2_diag["timeout_boundary_analysis"][
                "bucket_counts"
            ],
            "c3_distinct_normalized_error_signatures": c3_diag[
                "distinct_normalized_error_signatures"
            ],
            "c3_provider_declared_billing_credit_count": c3_diag[
                "provider_declared_billing_credit_count"
            ],
            "diagnostic_artifact_file_sha256": disk_file_sha,
            "diagnostic_artifact_internal_sha256": recorded_internal_sha,
            "final100_used": expected_payload["final100_used"],
            "harness_or_binding_inconsistency_observed": expected_payload[
                "harness_or_binding_inconsistency_observed"
            ],
            "live_provider_calls_new": expected_payload[
                "live_provider_calls_new"
            ],
            "model_winner_selected": expected_payload["model_winner_selected"],
            "primary_counts_by_candidate": expected_payload[
                "primary_counts_by_candidate"
            ],
            "primary_counts_total": expected_payload["primary_counts_total"],
            "raw_evidence_mutated": False,
            "raw_evidence_tree_sha256": expected_payload[
                "raw_evidence_tree_sha256"
            ],
            "results_freeze_receipt_file_sha256": expected_payload[
                "results_freeze_receipt_file_sha256"
            ],
            "results_manifest_file_sha256": expected_payload[
                "results_manifest_file_sha256"
            ],
            "scientific_code_bundle_sha256": expected_payload[
                "scientific_code_bundle_sha256"
            ],
            "secondary_counts_by_candidate": expected_payload[
                "secondary_counts_by_candidate"
            ],
            "secondary_counts_total": expected_payload["secondary_counts_total"],
            "selected_model_id": expected_payload["selected_model_id"],
            "source_develop_sha": expected_payload["source_develop_sha"],
            "stochasticity_execution_started": expected_payload[
                "stochasticity_execution_started"
            ],
            "task_id": expected_payload["task_id"],
            "verified": True,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline deterministic failure diagnostic for W06 DEV-SELECT."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify frozen authorities and diagnostic artifact without writing any files.",
    )
    group.add_argument(
        "--write",
        action="store_true",
        help="Generate and write data/evaluation/w06/w06_dev_select_failure_diagnostic_v1.json.",
    )
    args = parser.parse_args(argv)

    with NetworkKillSwitchGuard():
        if args.write:
            summary = write_w06_dev_select_failure_diagnostic(
                repo_root=REPO_ROOT
            )
        else:
            summary = verify_w06_dev_select_failure_diagnostic(
                repo_root=REPO_ROOT
            )
        sys.stdout.write(
            json.dumps(summary, indent=2, sort_keys=True) + "\n"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
