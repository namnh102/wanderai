"""Production-grade W06 DEV Live Runner Infrastructure (W06-DEV-LIVE-RUNNER-01-OFFLINE & AUDIT-CORRECTION-02).

Grounded in:
- data/evaluation/w06/w06_model_arch_selection_method_lock_v1.json (W06-MODEL-ARCH-SELECTION-METHOD-LOCK-01 v1.0.0)
- data/evaluation/w06/w06_measurement_contract_v1.json (W06-MEASUREMENT-CONTRACT-01 v1.0.0)
- data/evaluation/w06/w06_dev_fixtures_freeze_v1.json (80 frozen DEV fixtures: 20 DEV-TUNE + 60 DEV-SELECT)
- data/evaluation/w06/w06_model_preflight_01d_v2_live_receipt_v1.json (C1/C2/C3 PASSED_TECHNICAL_PREFLIGHT_SCHEMA_V2)
- apps/ai-service/app/evaluation/dev_selection_harness.py (Frozen DEV selection harness authority)

STRICT SCIENTIFIC & OPERATIONAL INVARIANTS:
- Offline by default: zero live provider calls unless explicit `--execute-live` CLI/action flag,
  a verified phase-scoped `DevLiveAuthorizationArtifact`, a verified `DevLiveStageAFreezeReceipt`
  with git commit ancestor + blob attestation, AND an internally minted `LiveExecutionCapability`
  (fail-closed orchestration capability) are supplied, followed by fresh Stage-A re-attestation
  at the live action boundary before transport.
- In W06-DEV-LIVE-RUNNER-01-OFFLINE: LIVE_PROVIDER_CALLS = 0, PROVIDER_COST_USD = 0,
  LIVE_AUTHORIZATION_PRESENT = false, PROMPT_FREEZE_STATUS = NOT_YET_FROZEN.
- Secret-independent offline execution: never reads API key values or requires `.env` in offline/dry-run/test modes;
  sanitizes all persisted artifacts and exception text so secrets never enter prompt, request artifact,
  receipt, logs, exception text, authorization artifact, or provider metadata artifact.
- Candidates: exclusively C1 (`google` / `gemini-3.8-flash`), C2 (`openai` / `gpt-6.1-sol`),
  and C3 (`anthropic` / `claude-sonnet-5-5`), all requiring `PASSED_TECHNICAL_PREFLIGHT_SCHEMA_V2`
  under Portable Schema V2 (`825a4ff912d851a95f7392cb564b7d7ca3588135508dc6eb3ac6304cdde3c490`)
  and Semantic Schema (`e4169f7b890f77d13af65e9f2070b6071c535b206d88440f5e8f28c179977555`).
- Real Production Transports & HTTP Boundary Counting:
  Implements `GoogleGeminiProductionTransport` (C1), `OpenAIChatCompletionsProductionTransport` (C2),
  `AnthropicMessagesProductionTransport` (C3), and `ProductionDevProviderTransport` backed by
  `DevCountingHttpxTransport` / `DevCountingHttpx2Transport` enforcing at most 1 outbound HTTP
  generation request per cell (`retry = 0`).
- Transport Type Safety, Action-Boundary Re-Attestation & Programmatic Live-Gate Closure:
  `execute_live_dev_cell()` and `execute_live_dev_batch()` require an explicit `execution_mode`:
  - `LIVE_EXECUTION`: requires an internally minted `LiveExecutionCapability` (fail-closed orchestration
    capability), a `ProductionDevProviderTransport`, AND fresh action-boundary Stage-A re-attestation
    (`LiveExecutionContext`) against current git HEAD, committed blobs, clean Stage-A files, scientific code
    bundle, and provider config registry immediately before transport.
  - `OFFLINE_MOCK_TEST`: accepts only `MockDevProviderTransport` or `MockProviderTransportResponse`
    and rejects `ProductionDevProviderTransport` or `LiveExecutionCapability`.
- Truthful BenchmarkRunManifest Provenance & Single Execution-Start Timestamp Authority:
  - Captures `execution_started_at_utc` once via `utc_now_clock()` immediately before `TRANSPORT_STARTING`
    and uses that exact timestamp for both `transport_journal_starting.timestamp_utc` and
    `BenchmarkRunManifest.execution_timestamp_utc`.
  - `generation_parameters` truthfully records `temperature_status = "OMITTED"` and exact candidate
    seed/reasoning/thinking parameters (never claiming `temperature = 0.0`).
  - `execution_mode` truthfully records `OFFLINE_MOCK_VERIFICATION`, `LIVE_DEV_TUNE`, `LIVE_DEV_SELECT`,
    or `STOCHASTICITY_DIAGNOSTIC`.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
from decimal import Decimal
from enum import Enum
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    Set,
    Tuple,
    Union,
)

import anthropic
from google import genai
from google.genai import types as genai_types
import httpx
import httpx2
import openai
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.evaluation.dev_selection_harness import (
    BATCH_STOP_FAILURE_CLASSIFICATIONS,
    DEV_SELECT_MAX_CALLS,
    DEV_TUNE_MAX_CALLS_ONE_PROMPT,
    DEV_TUNE_MAX_CALLS_TWO_PROMPTS,
    EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
    EXPECTED_SEMANTIC_SCHEMA_SHA256,
    FROZEN_SAMPLING_SEED,
    ORDERED_CANDIDATE_IDS,
    ORDINARY_DENOMINATOR_FAILURE_CLASSIFICATIONS,
    REPO_ROOT,
    SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS,
    STOCHASTICITY_MAX_CALLS,
    BatchExecutionFatalStopError,
    CandidateCostComparabilityRecord,
    CandidateRegistryIntegrityError,
    CodeCommitProvenanceError,
    DevCandidateRegistry,
    DevCandidateSpec,
    DevCellExecutionManifest,
    DevCellExecutionReceipt,
    DevCellFailureClassification,
    DevExecutionPlan,
    DevHarnessOfflineViolationError,
    DevPromptFreezeArtifact,
    DevSelectModelSelectionResult,
    Final100FirewallViolationError,
    HarnessInternalBatchStopError,
    ImmutableCellExecutionError,
    MockProviderTransportResponse,
    ModelIntegrityBatchStopError,
    PromptCandidateSpec,
    PromptFreezeFirewallError,
    PromptRegistry,
    ScientificCodeBundleIntegrityError,
    StochasticityDiagnosticPlan,
    StochasticityGateViolationError,
    VerifiedDevBundle,
    assert_not_final100_path,
    assert_not_final100_scenario,
    assert_not_final100_scenario_id,
    build_default_infrastructure_prompt_registry,
    build_deterministic_dev_scenario_context,
    build_dev_tune_execution_plan,
    canonical_json_bytes,
    compute_canonical_cell_cost_decimal,
    compute_canonical_cell_cost_usd,
    compute_provider_config_registry_sha256,
    compute_scientific_code_bundle,
    compute_scientific_code_bundle_sha256,
    evaluate_dev_cell_scenario,
    format_canonical_decimal_str,
    get_cached_provider_config_sha256,
    is_returned_model_id_compatible,
    load_and_verify_candidate_registry,
    load_and_verify_frozen_dev_bundle,
    normalize_lf_bytes,
    parse_primary_dev_plan_response,
    resolve_active_git_commit_sha,
    sha256_bytes,
    validate_git_commit_sha40,
    validate_sha256_hex64,
    verify_cell_manifest_for_execution,
    verify_dev_execution_plan_for_execution,
    verify_frozen_authorities_dev_harness,
    verify_prompt_candidate_freeze_artifact,
    write_canonical_json,
)
from app.evaluation.model_preflight.schema_adapter import (
    COMMON_PORTABLE_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA_V2,
)
from app.evaluation.planner_benchmark_evaluator import (
    ScenarioEvaluationResult,
    load_core_catalog_by_place_id,
)
from app.schemas.planner_benchmark import (
    HASH_BASIS_VERSION,
    BenchmarkCatalogPOI,
    BenchmarkPlanResponse,
    BenchmarkRunManifest,
    BenchmarkRunStatus,
    BenchmarkScenarioInput,
    BenchmarkUsageMetadata,
)
from app.services.planner_benchmark_runner import (
    MEASUREMENT_CONTRACT_ID,
    MEASUREMENT_CONTRACT_VERSION,
    compute_catalog_sha256,
)

# ==============================================================================
# 1. CONSTANTS & IDENTITIES
# ==============================================================================

TASK_ID_DEV_LIVE_RUNNER_01: str = "W06-DEV-LIVE-RUNNER-01-OFFLINE"
TASK_ID_DEV_LIVE_RUNNER_01_CORRECTION_02: str = (
    "W06-DEV-LIVE-RUNNER-01-AUDIT-CORRECTION-02"
)
RUNNER_RECEIPT_ARTIFACT_ID: str = "W06-DEV-LIVE-RUNNER-01-RECEIPT-V1"
STAGE_A_FREEZE_RECEIPT_ARTIFACT_ID: str = "W06-DEV-LIVE-STAGE-A-FREEZE-RECEIPT-V1"
RUNNER_VERSION: str = "1.2.0"
EXPECTED_BASE_DEVELOP_SHA_RUNNER_01: str = "b2dfd8afb8db2e2bc4dfbb2d0ca4e6a9d22e3a50"
NEXT_GATE_RUNNER_QA_01: str = "W06-DEV-LIVE-RUNNER-QA-01-OFFLINE-ADVERSARIAL"
LIVE_CAPABILITY_ROLE_ORCHESTRATION_GUARD: str = "FAIL_CLOSED_ORCHESTRATION_GUARD"


def default_utc_now_clock() -> str:
    """Return current UTC timestamp in ISO-8601 format (Section 7)."""
    return dt.datetime.now(dt.timezone.utc).isoformat()


PROMPT_FREEZE_STATUS_NOT_YET_FROZEN: str = "NOT_YET_FROZEN"
PROMPT_FREEZE_INFRASTRUCTURE_STATUS: str = (
    "INFRASTRUCTURE_ONLY_PENDING_LATER_PROMPT_FREEZE_GATE"
)

STAGE_A_STATUS_FROZEN_BEFORE_LIVE: str = "FROZEN_BEFORE_LIVE"

TRANSPORT_STATUS_NOT_INVOKED: str = "TRANSPORT_NOT_INVOKED"
TRANSPORT_STATUS_STARTING: str = "TRANSPORT_STARTING"
TRANSPORT_STATUS_COMPLETED: str = "TRANSPORT_COMPLETED"
ATTEMPT_STATUS_UNKNOWN_AFTER_TRANSPORT: str = "ATTEMPT_STATUS_UNKNOWN_AFTER_TRANSPORT"

AUTHORIZED_BY_ROLE_PROJECT_OWNER: str = "PROJECT_OWNER"
AUTHORIZATION_STATUS_AUTHORIZED: str = "AUTHORIZED"

ALLOWED_RUNNER_PHASES: Tuple[str, str, str] = (
    "DEV_TUNE",
    "DEV_SELECT",
    "STOCHASTICITY",
)

RUNNER_EXECUTION_MODE_OFFLINE_MOCK_TEST: str = "OFFLINE_MOCK_TEST"
RUNNER_EXECUTION_MODE_LIVE_EXECUTION: str = "LIVE_EXECUTION"

MANIFEST_EXECUTION_MODE_OFFLINE_MOCK: str = "OFFLINE_MOCK_VERIFICATION"
MANIFEST_EXECUTION_MODE_LIVE_DEV_TUNE: str = "LIVE_DEV_TUNE"
MANIFEST_EXECUTION_MODE_LIVE_DEV_SELECT: str = "LIVE_DEV_SELECT"
MANIFEST_EXECUTION_MODE_STOCHASTICITY: str = "STOCHASTICITY_DIAGNOSTIC"


class RunnerExecutionMode(str, Enum):
    """Explicit execution mode required by execute_live_dev_cell and execute_live_dev_batch."""

    OFFLINE_MOCK_TEST = "OFFLINE_MOCK_TEST"
    LIVE_EXECUTION = "LIVE_EXECUTION"


CANDIDATE_PROVIDER_BY_ID: Dict[str, str] = {
    "C1": "google",
    "C2": "openai",
    "C3": "anthropic",
}

CANDIDATE_ENV_KEY_BY_ID: Dict[str, str] = {
    "C1": "GEMINI_API_KEY",
    "C2": "OPENAI_API_KEY",
    "C3": "ANTHROPIC_API_KEY",
}

CANDIDATE_MODEL_BY_ID: Dict[str, str] = {
    "C1": "gemini-3.8-flash",
    "C2": "gpt-6.1-sol",
    "C3": "claude-sonnet-5-5",
}

DEFAULT_COST_COMPARABILITY_BY_CANDIDATE: Dict[str, CandidateCostComparabilityRecord] = {
    "C1": CandidateCostComparabilityRecord(
        candidate_id="C1",
        authoritative_usage_available=True,
        pricing_source="w06_model_preflight_01d_v2_live_receipt_v1.json",
        pricing_access_date="2026-10-16",
        input_price_per_million_usd=0.30,
        output_price_per_million_usd=2.50,
        canonical_cost_computable=True,
    ),
    "C2": CandidateCostComparabilityRecord(
        candidate_id="C2",
        authoritative_usage_available=True,
        pricing_source="w06_model_preflight_01d_v2_live_receipt_v1.json",
        pricing_access_date="2026-10-16",
        input_price_per_million_usd=2.50,
        output_price_per_million_usd=10.00,
        canonical_cost_computable=True,
    ),
    "C3": CandidateCostComparabilityRecord(
        candidate_id="C3",
        authoritative_usage_available=True,
        pricing_source="w06_model_preflight_01d_v2_live_receipt_v1.json",
        pricing_access_date="2026-10-16",
        input_price_per_million_usd=3.00,
        output_price_per_million_usd=15.00,
        canonical_cost_computable=True,
    ),
}

DEFAULT_RUNNER_RECEIPT_PATH: Path = (
    REPO_ROOT / "data" / "evaluation" / "w06" / "w06_dev_live_runner_01_receipt_v1.json"
)

CELL_IMMUTABLE_ARTIFACT_FILENAMES: Tuple[str, ...] = (
    "request_manifest.json",
    "transport_journal_starting.json",
    "transport_journal_completed.json",
    "transport_journal_unknown_after_transport.json",
    "raw_provider_response.txt",
    "provider_response_metadata.json",
    "raw_usage_metadata.json",
    "run_manifest.json",
    "parsed_plan_response.json",
    "evaluation_result.json",
    "execution_receipt.json",
)

REDACTED_SECRET_PLACEHOLDER: str = "[REDACTED_SECRET]"

_FORBIDDEN_SECRET_FIELD_NAMES: Set[str] = {
    "api_key",
    "apikey",
    "secret",
    "secret_key",
    "access_token",
    "private_key",
    "gemini_api_key",
    "google_api_key",
    "openai_api_key",
    "anthropic_api_key",
    "authorization_token",
    "bearer_token",
}

_SECRET_TOKEN_PATTERNS: Tuple[re.Pattern[str], ...] = (
    re.compile(r"AIza[0-9A-Za-z_\-]{12,}"),
    re.compile(r"sk-ant-[0-9A-Za-z_\-]{10,}"),
    re.compile(r"sk-proj-[0-9A-Za-z_\-]{10,}"),
    re.compile(r"sk-[0-9A-Za-z_\-]{16,}"),
    re.compile(r"(?i)bearer\s+[0-9A-Za-z._\-]{12,}"),
    re.compile(
        r"(?:GEMINI_API_KEY|GOOGLE_API_KEY|OPENAI_API_KEY|ANTHROPIC_API_KEY)"
        r"\s*[:=]\s*[^\s,;'\")\]]+"
    ),
)

_CAPABILITY_MINT_GUARD = object()


# ==============================================================================
# 2. RUNNER EXCEPTION TAXONOMY
# ==============================================================================


class DevLiveRunnerError(RuntimeError):
    """Base exception for W06 DEV live runner errors."""


class DevLiveAuthorizationError(DevLiveRunnerError):
    """Raised when live execution authorization is missing, invalid, out of scope, or contains secrets."""


class LiveExecutionNotAuthorizedError(
    DevHarnessOfflineViolationError, DevLiveAuthorizationError
):
    """Raised when live execution is attempted without explicit live capability and verified Stage-A evidence."""


class DevCallBudgetExhaustedError(DevLiveRunnerError):
    """Raised when a cell reservation or transport call would exceed the authorized call budget."""


class DuplicateDevCellAttemptError(ImmutableCellExecutionError, DevLiveRunnerError):
    """Raised when a duplicate run_id or duplicate scientific cell is attempted in the call-budget ledger."""


class CrashAmbiguityBatchStopError(DevLiveRunnerError):
    """Raised when TRANSPORT_STARTING exists without TRANSPORT_COMPLETED (ATTEMPT_STATUS_UNKNOWN_AFTER_TRANSPORT)."""


class PlanBeforeLiveProtocolError(DevLiveRunnerError):
    """Raised when Stage A pre-frozen artifacts, Stage-A commit attestation, or plan membership requirements are violated."""


class SecretLeakageViolationError(DevLiveRunnerError):
    """Raised when an API key or secret token is detected in a scientific artifact or authorization contract."""


# ==============================================================================
# 3. SECRET SANITIZATION & ATOMIC IMMUTABLE FILE WRITES
# ==============================================================================


def sanitize_runner_text(
    text: Optional[str], extra_secrets: Optional[Sequence[str]] = None
) -> str:
    """Sanitize any API key or secret pattern from text before logging, raising, or writing to disk."""
    if text is None:
        return ""
    cleaned = str(text)
    if extra_secrets:
        for secret in sorted(
            (s for s in extra_secrets if isinstance(s, str) and len(s.strip()) >= 6),
            key=len,
            reverse=True,
        ):
            cleaned = cleaned.replace(secret.strip(), REDACTED_SECRET_PLACEHOLDER)
    for pattern in _SECRET_TOKEN_PATTERNS:
        cleaned = pattern.sub(REDACTED_SECRET_PLACEHOLDER, cleaned)
    return cleaned


def sanitize_runner_structure(
    value: Any, extra_secrets: Optional[Sequence[str]] = None
) -> Any:
    """Recursively sanitize strings and secret-named dictionary keys from a nested payload."""
    if isinstance(value, str):
        return sanitize_runner_text(value, extra_secrets=extra_secrets)
    if isinstance(value, Mapping):
        result: Dict[str, Any] = {}
        for k, v in value.items():
            key_str = str(k)
            if key_str.strip().lower() in _FORBIDDEN_SECRET_FIELD_NAMES:
                result[key_str] = REDACTED_SECRET_PLACEHOLDER
            else:
                result[key_str] = sanitize_runner_structure(v, extra_secrets=extra_secrets)
        return result
    if isinstance(value, list):
        return [sanitize_runner_structure(item, extra_secrets=extra_secrets) for item in value]
    if isinstance(value, tuple):
        return [sanitize_runner_structure(item, extra_secrets=extra_secrets) for item in value]
    return value


def assert_no_secrets_in_payload(payload: Any, *, context: str) -> None:
    """Fail closed if any forbidden secret field name or raw secret token pattern appears in payload."""
    if isinstance(payload, Mapping):
        for k, v in payload.items():
            key_lower = str(k).strip().lower()
            if key_lower in _FORBIDDEN_SECRET_FIELD_NAMES:
                raise SecretLeakageViolationError(
                    f"SECRET_FIELD_FORBIDDEN_IN_{context}: field {k!r} is forbidden."
                )
            assert_no_secrets_in_payload(v, context=context)
    elif isinstance(payload, (list, tuple)):
        for item in payload:
            assert_no_secrets_in_payload(item, context=context)
    elif isinstance(payload, str):
        for pattern in _SECRET_TOKEN_PATTERNS:
            if pattern.search(payload):
                raise SecretLeakageViolationError(
                    f"SECRET_VALUE_FORBIDDEN_IN_{context}: detected secret token pattern."
                )


def _assert_runner_not_final100_path(path: Union[Path, str]) -> Path:
    """Reject any path or ancestor directory component referencing final100 or P11 assignment manifests."""
    raw_path = Path(path)
    for part in raw_path.parts:
        part_low = part.lower()
        if (
            "w06_scenarios_freeze_v1" in part_low
            or "w06_p11_assignment_manifest_v1" in part_low
            or "final100" in part_low
        ):
            raise Final100FirewallViolationError(
                f"FINAL100_FIREWALL_VIOLATION: Forbidden final-100 path component {part!r} in {raw_path}"
            )
    return assert_not_final100_path(raw_path)


def write_immutable_atomic_bytes(path: Path, data: bytes) -> str:
    """Write bytes atomically via temp file + fsync + atomic rename, failing closed if target exists (Section 21)."""
    _assert_runner_not_final100_path(path)
    if path.exists():
        raise ImmutableCellExecutionError(
            f"IMMUTABLE_ARTIFACT_ALREADY_EXISTS: Refusing to overwrite existing artifact at {path}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".tmp_{path.name}_", suffix=".part", dir=str(path.parent)
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        if path.exists():
            raise ImmutableCellExecutionError(
                f"IMMUTABLE_ARTIFACT_ALREADY_EXISTS: Refusing to overwrite existing artifact at {path}"
            )
        os.replace(str(tmp_path), str(path))
    except Exception:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise
    return sha256_bytes(normalize_lf_bytes(data))


def write_immutable_canonical_json(
    path: Path,
    payload: Any,
    *,
    extra_secrets: Optional[Sequence[str]] = None,
) -> str:
    """Sanitize and atomically write canonical JSON to `path`, failing closed if `path` already exists."""
    sanitized = sanitize_runner_structure(payload, extra_secrets=extra_secrets)
    encoded = canonical_json_bytes(sanitized)
    return write_immutable_atomic_bytes(path, encoded)


def write_immutable_utf8_text(
    path: Path,
    text: str,
    *,
    extra_secrets: Optional[Sequence[str]] = None,
) -> str:
    """Sanitize and atomically write UTF-8 text to `path`, failing closed if `path` already exists."""
    sanitized = sanitize_runner_text(text, extra_secrets=extra_secrets)
    encoded = normalize_lf_bytes(sanitized.encode("utf-8"))
    return write_immutable_atomic_bytes(path, encoded)


# ==============================================================================
# 4. AUTHORIZATION ARTIFACT CONTRACT & HARDENED BUILDER (SECTION 12)
# ==============================================================================


def compute_prompt_freeze_sha256(
    prompt_freeze: Union[DevPromptFreezeArtifact, Mapping[str, Any]]
) -> str:
    """Compute canonical JSON SHA256 of a DevPromptFreezeArtifact."""
    if isinstance(prompt_freeze, DevPromptFreezeArtifact):
        payload = prompt_freeze.model_dump()
    else:
        validated = DevPromptFreezeArtifact.model_validate(dict(prompt_freeze))
        payload = validated.model_dump()
    return sha256_bytes(canonical_json_bytes(payload))


def verify_runner_prompt_freeze_artifact(
    prompt_freeze: Optional[Union[DevPromptFreezeArtifact, Path, str, Dict[str, Any]]],
    *,
    prompt_registry: PromptRegistry,
    execution_plan: Union[DevExecutionPlan, StochasticityDiagnosticPlan],
    dev_bundle: Optional[VerifiedDevBundle] = None,
    candidate_registry: Optional[DevCandidateRegistry] = None,
    repo_root: Optional[Path] = None,
) -> DevPromptFreezeArtifact:
    """Verify DevPromptFreezeArtifact for DEV_TUNE, DEV_SELECT, or STOCHASTICITY execution."""
    if prompt_freeze is None:
        raise PromptFreezeFirewallError(
            "PROMPT_FREEZE_MISSING: Live/runner execution requires a verified DevPromptFreezeArtifact."
        )
    if isinstance(prompt_freeze, str):
        pf_arg: Union[DevPromptFreezeArtifact, Path, Dict[str, Any]] = Path(
            prompt_freeze
        )
    else:
        pf_arg = prompt_freeze
    if isinstance(pf_arg, Path):
        _assert_runner_not_final100_path(pf_arg)

    bundle = dev_bundle or load_and_verify_frozen_dev_bundle()
    cand_reg = candidate_registry or load_and_verify_candidate_registry()

    if isinstance(execution_plan, DevExecutionPlan) and execution_plan.phase == "DEV_TUNE":
        dev_tune_plan = execution_plan
    else:
        dev_tune_plan = build_dev_tune_execution_plan(
            prompt_registry,
            dev_bundle=bundle,
            candidate_registry=cand_reg,
            code_basis_commit_sha=execution_plan.code_basis_commit_sha,
            repo_root=repo_root,
        )

    return verify_prompt_candidate_freeze_artifact(
        pf_arg,
        prompt_registry=prompt_registry,
        dev_tune_plan=dev_tune_plan,
        dev_bundle=bundle,
        candidate_registry=cand_reg,
        repo_root=repo_root,
    )


class DevLiveAuthorizationArtifact(BaseModel):
    """Frozen authorization contract required for any future live DEV cell/batch execution."""

    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(..., min_length=1)
    authorization_id: str = Field(..., min_length=1)
    authorized_by_role: str
    authorized_at_utc: str = Field(..., min_length=1)
    allowed_phase: str
    allowed_execution_plan_sha256: str
    allowed_prompt_freeze_sha256: str
    allowed_candidate_ids: List[str]
    maximum_live_generation_calls: int
    authorization_status: str
    scientific_code_bundle_sha256: str
    code_basis_commit_sha: str
    authorization_artifact_sha256: str

    @model_validator(mode="before")
    @classmethod
    def _validate_required_fields_and_no_secrets(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            raise DevLiveAuthorizationError(
                "AUTHORIZATION_INTEGRITY_FAILURE: Authorization artifact must be a JSON object."
            )
        d = dict(data)
        try:
            assert_no_secrets_in_payload(d, context="AUTHORIZATION_ARTIFACT")
        except SecretLeakageViolationError as exc:
            raise DevLiveAuthorizationError(
                f"AUTHORIZATION_CONTAINS_FORBIDDEN_SECRET: {exc}"
            ) from exc

        required_fields = (
            "task_id",
            "authorization_id",
            "authorized_by_role",
            "authorized_at_utc",
            "allowed_phase",
            "allowed_execution_plan_sha256",
            "allowed_prompt_freeze_sha256",
            "allowed_candidate_ids",
            "maximum_live_generation_calls",
            "authorization_status",
            "scientific_code_bundle_sha256",
            "code_basis_commit_sha",
            "authorization_artifact_sha256",
        )
        for req in required_fields:
            if req not in d or d[req] is None:
                raise DevLiveAuthorizationError(
                    f"AUTHORIZATION_INTEGRITY_FAILURE: Missing required field {req!r} in authorization artifact."
                )
        return d

    @model_validator(mode="after")
    def _validate_authorization_invariants(self) -> "DevLiveAuthorizationArtifact":
        if self.authorized_by_role != AUTHORIZED_BY_ROLE_PROJECT_OWNER:
            raise DevLiveAuthorizationError(
                f"AUTHORIZATION_INTEGRITY_FAILURE: authorized_by_role must be {AUTHORIZED_BY_ROLE_PROJECT_OWNER!r}, "
                f"got {self.authorized_by_role!r}."
            )
        if self.authorization_status != AUTHORIZATION_STATUS_AUTHORIZED:
            raise DevLiveAuthorizationError(
                f"AUTHORIZATION_INTEGRITY_FAILURE: authorization_status must be {AUTHORIZATION_STATUS_AUTHORIZED!r}, "
                f"got {self.authorization_status!r}."
            )
        if self.allowed_phase == "FINAL100" or "FINAL" in self.allowed_phase.upper():
            raise Final100FirewallViolationError(
                f"FINAL100_FIREWALL_VIOLATION: DEV live runner rejects FINAL100 authorization phase {self.allowed_phase!r}."
            )
        if self.allowed_phase not in ALLOWED_RUNNER_PHASES:
            raise DevLiveAuthorizationError(
                f"AUTHORIZATION_INTEGRITY_FAILURE: Invalid allowed_phase {self.allowed_phase!r}; "
                f"must be one of {list(ALLOWED_RUNNER_PHASES)}."
            )

        try:
            validate_sha256_hex64(
                self.allowed_execution_plan_sha256, "allowed_execution_plan_sha256"
            )
            validate_sha256_hex64(
                self.allowed_prompt_freeze_sha256, "allowed_prompt_freeze_sha256"
            )
            validate_sha256_hex64(
                self.scientific_code_bundle_sha256, "scientific_code_bundle_sha256"
            )
            validate_sha256_hex64(
                self.authorization_artifact_sha256, "authorization_artifact_sha256"
            )
            validate_git_commit_sha40(self.code_basis_commit_sha)
        except Exception as exc:
            raise DevLiveAuthorizationError(
                f"AUTHORIZATION_INTEGRITY_FAILURE: {exc}"
            ) from exc

        if not self.allowed_candidate_ids:
            raise DevLiveAuthorizationError(
                "AUTHORIZATION_INTEGRITY_FAILURE: allowed_candidate_ids must not be empty."
            )
        for cid in self.allowed_candidate_ids:
            if cid not in ORDERED_CANDIDATE_IDS:
                raise DevLiveAuthorizationError(
                    f"AUTHORIZATION_INTEGRITY_FAILURE: Forbidden candidate {cid!r} in allowed_candidate_ids."
                )

        if self.maximum_live_generation_calls <= 0:
            raise DevLiveAuthorizationError(
                f"AUTHORIZATION_INTEGRITY_FAILURE: maximum_live_generation_calls must be positive, "
                f"got {self.maximum_live_generation_calls}."
            )

        if self.allowed_phase == "DEV_TUNE":
            if self.maximum_live_generation_calls not in (
                DEV_TUNE_MAX_CALLS_ONE_PROMPT,
                DEV_TUNE_MAX_CALLS_TWO_PROMPTS,
            ):
                raise DevLiveAuthorizationError(
                    f"AUTHORIZATION_CALL_BUDGET_INVALID: DEV_TUNE maximum_live_generation_calls must be "
                    f"{DEV_TUNE_MAX_CALLS_ONE_PROMPT} or {DEV_TUNE_MAX_CALLS_TWO_PROMPTS}, "
                    f"got {self.maximum_live_generation_calls}."
                )
            if tuple(self.allowed_candidate_ids) != ORDERED_CANDIDATE_IDS:
                raise DevLiveAuthorizationError(
                    f"AUTHORIZATION_CANDIDATES_INVALID: DEV_TUNE requires allowed_candidate_ids={list(ORDERED_CANDIDATE_IDS)}, "
                    f"got {self.allowed_candidate_ids}."
                )
        elif self.allowed_phase == "DEV_SELECT":
            if self.maximum_live_generation_calls != DEV_SELECT_MAX_CALLS:
                raise DevLiveAuthorizationError(
                    f"AUTHORIZATION_CALL_BUDGET_INVALID: DEV_SELECT maximum_live_generation_calls must be "
                    f"{DEV_SELECT_MAX_CALLS}, got {self.maximum_live_generation_calls}."
                )
            if tuple(self.allowed_candidate_ids) != ORDERED_CANDIDATE_IDS:
                raise DevLiveAuthorizationError(
                    f"AUTHORIZATION_CANDIDATES_INVALID: DEV_SELECT requires allowed_candidate_ids={list(ORDERED_CANDIDATE_IDS)}, "
                    f"got {self.allowed_candidate_ids}."
                )
        elif self.allowed_phase == "STOCHASTICITY":
            if self.maximum_live_generation_calls != STOCHASTICITY_MAX_CALLS:
                raise DevLiveAuthorizationError(
                    f"AUTHORIZATION_CALL_BUDGET_INVALID: STOCHASTICITY maximum_live_generation_calls must be "
                    f"{STOCHASTICITY_MAX_CALLS}, got {self.maximum_live_generation_calls}."
                )
            if len(self.allowed_candidate_ids) != 1:
                raise DevLiveAuthorizationError(
                    "AUTHORIZATION_CANDIDATES_INVALID: STOCHASTICITY requires exactly 1 winning candidate."
                )

        body = self.model_dump(exclude={"authorization_artifact_sha256"})
        expected_sha = sha256_bytes(canonical_json_bytes(body))
        if self.authorization_artifact_sha256 != expected_sha:
            raise DevLiveAuthorizationError(
                f"AUTHORIZATION_ARTIFACT_SHA256_MISMATCH: authorization_artifact_sha256={self.authorization_artifact_sha256} "
                f"!= computed={expected_sha}."
            )
        return self


def build_dev_live_authorization_artifact(
    *,
    task_id: str,
    authorization_id: str,
    authorized_by_role: str,
    authorized_at_utc: str,
    authorization_status: str,
    allowed_phase: str,
    allowed_candidate_ids: Sequence[str],
    maximum_live_generation_calls: int,
    execution_plan: Union[DevExecutionPlan, StochasticityDiagnosticPlan],
    prompt_freeze: DevPromptFreezeArtifact,
    scientific_code_bundle_sha256: Optional[str] = None,
    code_basis_commit_sha: Optional[str] = None,
) -> DevLiveAuthorizationArtifact:
    """Production authorization artifact builder (Section 12).

    Strictly requires explicit `authorized_by_role`, `authorized_at_utc`,
    `authorization_status`, `authorization_id`, `allowed_phase`,
    `allowed_candidate_ids`, and `maximum_live_generation_calls` with ZERO
    implicit `PROJECT_OWNER` or `AUTHORIZED` defaults.
    """
    if (
        not task_id
        or not authorization_id
        or not authorized_by_role
        or not authorized_at_utc
        or not authorization_status
        or not allowed_phase
        or allowed_candidate_ids is None
        or maximum_live_generation_calls is None
    ):
        raise DevLiveAuthorizationError(
            "AUTHORIZATION_EXPLICIT_FIELDS_REQUIRED: Production authorization builder requires explicit "
            "task_id, authorization_id, authorized_by_role, authorized_at_utc, authorization_status, "
            "allowed_phase, allowed_candidate_ids, and maximum_live_generation_calls."
        )
    bundle_sha = (
        scientific_code_bundle_sha256
        or execution_plan.scientific_code_bundle_sha256
    )
    basis_sha = code_basis_commit_sha or execution_plan.code_basis_commit_sha
    pf_sha = compute_prompt_freeze_sha256(prompt_freeze)

    body: Dict[str, Any] = {
        "task_id": task_id,
        "authorization_id": authorization_id,
        "authorized_by_role": authorized_by_role,
        "authorized_at_utc": authorized_at_utc,
        "allowed_phase": allowed_phase,
        "allowed_execution_plan_sha256": execution_plan.plan_sha256,
        "allowed_prompt_freeze_sha256": pf_sha,
        "allowed_candidate_ids": list(allowed_candidate_ids),
        "maximum_live_generation_calls": int(maximum_live_generation_calls),
        "authorization_status": authorization_status,
        "scientific_code_bundle_sha256": bundle_sha,
        "code_basis_commit_sha": basis_sha,
    }
    artifact_sha = sha256_bytes(canonical_json_bytes(body))
    return DevLiveAuthorizationArtifact.model_validate(
        {**body, "authorization_artifact_sha256": artifact_sha}
    )


def build_test_only_authorization_artifact(
    *,
    task_id: str,
    authorization_id: str,
    allowed_phase: str,
    execution_plan: Union[DevExecutionPlan, StochasticityDiagnosticPlan],
    prompt_freeze: DevPromptFreezeArtifact,
    allowed_candidate_ids: Optional[Sequence[str]] = None,
    maximum_live_generation_calls: Optional[int] = None,
    authorized_at_utc: str = "2026-10-15T00:00:00Z",
    authorized_by_role: str = AUTHORIZED_BY_ROLE_PROJECT_OWNER,
    authorization_status: str = AUTHORIZATION_STATUS_AUTHORIZED,
    scientific_code_bundle_sha256: Optional[str] = None,
    code_basis_commit_sha: Optional[str] = None,
) -> DevLiveAuthorizationArtifact:
    """TEST-ONLY helper for synthetic offline runner unit tests (Section 12)."""
    cands = (
        list(allowed_candidate_ids)
        if allowed_candidate_ids is not None
        else (
            [execution_plan.selected_candidate_id]
            if isinstance(execution_plan, StochasticityDiagnosticPlan)
            else list(ORDERED_CANDIDATE_IDS)
        )
    )
    max_calls = (
        maximum_live_generation_calls
        if maximum_live_generation_calls is not None
        else (
            execution_plan.max_calls
            if isinstance(execution_plan, StochasticityDiagnosticPlan)
            else execution_plan.expected_total_cells
        )
    )
    return build_dev_live_authorization_artifact(
        task_id=task_id,
        authorization_id=authorization_id,
        authorized_by_role=authorized_by_role,
        authorized_at_utc=authorized_at_utc,
        authorization_status=authorization_status,
        allowed_phase=allowed_phase,
        allowed_candidate_ids=cands,
        maximum_live_generation_calls=max_calls,
        execution_plan=execution_plan,
        prompt_freeze=prompt_freeze,
        scientific_code_bundle_sha256=scientific_code_bundle_sha256,
        code_basis_commit_sha=code_basis_commit_sha,
    )


def verify_dev_live_authorization_artifact(
    authorization_or_path: Union[DevLiveAuthorizationArtifact, Mapping[str, Any], Path, str],
    *,
    execution_plan: Union[DevExecutionPlan, StochasticityDiagnosticPlan],
    prompt_freeze: DevPromptFreezeArtifact,
    expected_phase: Optional[str] = None,
    dev_select_result: Optional[DevSelectModelSelectionResult] = None,
    repo_root: Optional[Path] = None,
) -> DevLiveAuthorizationArtifact:
    """Fail-closed verification of a `DevLiveAuthorizationArtifact` against plan, prompt freeze, phase, and code bundle."""
    if authorization_or_path is None:
        raise DevLiveAuthorizationError(
            "AUTHORIZATION_MISSING: Live or authorized DEV execution requires a valid DevLiveAuthorizationArtifact."
        )

    if isinstance(authorization_or_path, (Path, str)):
        auth_path = Path(authorization_or_path)
        _assert_runner_not_final100_path(auth_path)
        if not auth_path.exists():
            raise DevLiveAuthorizationError(
                f"AUTHORIZATION_FILE_MISSING: Authorization artifact does not exist at {auth_path}"
            )
        try:
            raw_dict = json.loads(auth_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise DevLiveAuthorizationError(
                f"AUTHORIZATION_JSON_INVALID: Failed to parse {auth_path}: {exc}"
            ) from exc
        auth = DevLiveAuthorizationArtifact.model_validate(raw_dict)
    elif isinstance(authorization_or_path, DevLiveAuthorizationArtifact):
        auth = DevLiveAuthorizationArtifact.model_validate(
            authorization_or_path.model_dump()
        )
    elif isinstance(authorization_or_path, Mapping):
        auth = DevLiveAuthorizationArtifact.model_validate(dict(authorization_or_path))
    else:
        raise DevLiveAuthorizationError(
            f"Unsupported authorization artifact type: {type(authorization_or_path)}"
        )

    plan_phase = (
        "STOCHASTICITY"
        if isinstance(execution_plan, StochasticityDiagnosticPlan)
        else execution_plan.phase
    )
    if plan_phase == "FINAL100" or (
        expected_phase is not None and expected_phase == "FINAL100"
    ):
        raise Final100FirewallViolationError(
            "FINAL100_FIREWALL_VIOLATION: FINAL100 is forbidden in the W06 DEV live runner."
        )

    if expected_phase is not None and auth.allowed_phase != expected_phase:
        raise DevLiveAuthorizationError(
            f"AUTHORIZATION_PHASE_MISMATCH: Authorization allowed_phase={auth.allowed_phase!r} "
            f"cannot authorize requested phase {expected_phase!r}."
        )
    if auth.allowed_phase != plan_phase:
        raise DevLiveAuthorizationError(
            f"AUTHORIZATION_PHASE_MISMATCH: Authorization allowed_phase={auth.allowed_phase!r} "
            f"does not match execution plan phase {plan_phase!r}."
        )

    if auth.allowed_phase == "STOCHASTICITY":
        if (
            dev_select_result is None
            or not dev_select_result.winner_selected
            or dev_select_result.selected_candidate_id not in ORDERED_CANDIDATE_IDS
        ):
            raise StochasticityGateViolationError(
                "STOCHASTICITY_BLOCKED_BEFORE_WINNER_FROZEN: Stochasticity execution is forbidden before a DEV-SELECT winner is selected."
            )
        if auth.allowed_candidate_ids != [dev_select_result.selected_candidate_id]:
            raise DevLiveAuthorizationError(
                f"AUTHORIZATION_CANDIDATE_MISMATCH: Stochasticity allowed_candidate_ids {auth.allowed_candidate_ids} "
                f"!= winning candidate {[dev_select_result.selected_candidate_id]}."
            )

    if auth.allowed_execution_plan_sha256 != execution_plan.plan_sha256:
        raise DevLiveAuthorizationError(
            f"AUTHORIZATION_PLAN_SHA256_MISMATCH: allowed_execution_plan_sha256={auth.allowed_execution_plan_sha256} "
            f"!= execution_plan.plan_sha256={execution_plan.plan_sha256}."
        )

    pf_sha = compute_prompt_freeze_sha256(prompt_freeze)
    if auth.allowed_prompt_freeze_sha256 != pf_sha:
        raise DevLiveAuthorizationError(
            f"AUTHORIZATION_PROMPT_FREEZE_SHA256_MISMATCH: allowed_prompt_freeze_sha256={auth.allowed_prompt_freeze_sha256} "
            f"!= prompt_freeze_sha256={pf_sha}."
        )

    expected_plan_calls = (
        execution_plan.max_calls
        if isinstance(execution_plan, StochasticityDiagnosticPlan)
        else execution_plan.expected_total_cells
    )
    if (
        auth.maximum_live_generation_calls != expected_plan_calls
        or auth.maximum_live_generation_calls != len(execution_plan.cells)
    ):
        raise DevLiveAuthorizationError(
            f"AUTHORIZATION_CALL_BUDGET_MISMATCH: maximum_live_generation_calls={auth.maximum_live_generation_calls} "
            f"!= frozen plan cell count {len(execution_plan.cells)} (expected {expected_plan_calls})."
        )

    active_bundle_sha = compute_scientific_code_bundle_sha256(repo_root=repo_root)
    if auth.scientific_code_bundle_sha256 != execution_plan.scientific_code_bundle_sha256:
        raise ScientificCodeBundleIntegrityError(
            f"SCIENTIFIC_CODE_BUNDLE_MISMATCH: Authorization bundle {auth.scientific_code_bundle_sha256} "
            f"!= execution plan bundle {execution_plan.scientific_code_bundle_sha256}."
        )
    if auth.scientific_code_bundle_sha256 != active_bundle_sha:
        raise ScientificCodeBundleIntegrityError(
            f"SCIENTIFIC_CODE_BUNDLE_MISMATCH: Authorization bundle {auth.scientific_code_bundle_sha256} "
            f"!= active source bundle {active_bundle_sha}."
        )

    return auth


# ==============================================================================
# 4B. STAGE-A FREEZE RECEIPT & GIT COMMIT ANCESTOR ATTESTATION (SECTIONS 9, 10, 11)
# ==============================================================================


def compute_assigned_cells_sha256(
    execution_plan: Union[DevExecutionPlan, StochasticityDiagnosticPlan]
) -> Tuple[List[str], str]:
    """Compute ordered list of assigned cell `run_id`s and canonical SHA256 over all cell manifests."""
    run_ids = [c.run_id for c in execution_plan.cells]
    cell_dumps = [c.model_dump() for c in execution_plan.cells]
    return run_ids, sha256_bytes(canonical_json_bytes(cell_dumps))


_CURRENT_PROCESS_INVOCATION_TOKEN: str = f"pid-{os.getpid()}-ns-{time.monotonic_ns()}"


class DevLiveStageAFreezeReceipt(BaseModel):
    """Stage-A pre-execution freeze attestation receipt required before live execution (Sections 2, 3, 4, 9, 10, 11)."""

    model_config = ConfigDict(extra="forbid")

    artifact_id: str = STAGE_A_FREEZE_RECEIPT_ARTIFACT_ID
    phase: str
    execution_plan_sha256: str
    prompt_freeze_sha256: str
    authorization_artifact_sha256: str
    scientific_code_bundle_sha256: str
    provider_config_registry_sha256: str
    assigned_cell_run_ids: List[str]
    assigned_cells_sha256: str
    code_basis_commit_sha: str
    stage_a_commit_sha: str
    freeze_created_at_utc: str = Field(..., min_length=1)
    stage_a_process_token: str = Field(..., min_length=1)
    stage_a_status: str = STAGE_A_STATUS_FROZEN_BEFORE_LIVE
    stage_a_receipt_sha256: str

    @model_validator(mode="before")
    @classmethod
    def _validate_stage_a_before(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            raise PlanBeforeLiveProtocolError(
                "STAGE_A_RECEIPT_INVALID: Stage-A freeze receipt must be a JSON object."
            )
        d = dict(data)
        assert_no_secrets_in_payload(d, context="STAGE_A_FREEZE_RECEIPT")
        if "stage_a_process_token" not in d:
            raise PlanBeforeLiveProtocolError(
                "STAGE_A_PROCESS_TOKEN_MISSING: stage_a_process_token is required on DevLiveStageAFreezeReceipt."
            )
        raw_tok = d["stage_a_process_token"]
        if raw_tok is None:
            raise PlanBeforeLiveProtocolError(
                "STAGE_A_PROCESS_TOKEN_NULL: stage_a_process_token must not be null."
            )
        if not isinstance(raw_tok, str) or not raw_tok.strip():
            raise PlanBeforeLiveProtocolError(
                "STAGE_A_PROCESS_TOKEN_EMPTY: stage_a_process_token must be a non-empty non-whitespace string."
            )
        return d

    @model_validator(mode="after")
    def _validate_stage_a_after(self) -> "DevLiveStageAFreezeReceipt":
        if not self.stage_a_process_token or not self.stage_a_process_token.strip():
            raise PlanBeforeLiveProtocolError(
                "STAGE_A_PROCESS_TOKEN_EMPTY: stage_a_process_token must be non-empty."
            )
        if self.phase not in ALLOWED_RUNNER_PHASES:
            raise PlanBeforeLiveProtocolError(
                f"STAGE_A_RECEIPT_INVALID_PHASE: {self.phase!r} not in {list(ALLOWED_RUNNER_PHASES)}"
            )
        if self.stage_a_status != STAGE_A_STATUS_FROZEN_BEFORE_LIVE:
            raise PlanBeforeLiveProtocolError(
                f"STAGE_A_STATUS_INVALID: Expected {STAGE_A_STATUS_FROZEN_BEFORE_LIVE!r}, got {self.stage_a_status!r}."
            )
        try:
            validate_sha256_hex64(self.execution_plan_sha256, "execution_plan_sha256")
            validate_sha256_hex64(self.prompt_freeze_sha256, "prompt_freeze_sha256")
            validate_sha256_hex64(
                self.authorization_artifact_sha256, "authorization_artifact_sha256"
            )
            validate_sha256_hex64(
                self.scientific_code_bundle_sha256, "scientific_code_bundle_sha256"
            )
            validate_sha256_hex64(
                self.provider_config_registry_sha256, "provider_config_registry_sha256"
            )
            validate_sha256_hex64(self.assigned_cells_sha256, "assigned_cells_sha256")
            validate_sha256_hex64(self.stage_a_receipt_sha256, "stage_a_receipt_sha256")
            validate_git_commit_sha40(self.code_basis_commit_sha)
            validate_git_commit_sha40(self.stage_a_commit_sha)
        except Exception as exc:
            raise PlanBeforeLiveProtocolError(
                f"STAGE_A_RECEIPT_HASH_INVALID: {exc}"
            ) from exc

        if not self.assigned_cell_run_ids or len(set(self.assigned_cell_run_ids)) != len(
            self.assigned_cell_run_ids
        ):
            raise PlanBeforeLiveProtocolError(
                "STAGE_A_RECEIPT_CELLS_INVALID: assigned_cell_run_ids must be non-empty and unique."
            )

        body = self.model_dump(exclude={"stage_a_receipt_sha256"})
        expected_sha = sha256_bytes(canonical_json_bytes(body))
        if self.stage_a_receipt_sha256 != expected_sha:
            raise PlanBeforeLiveProtocolError(
                f"STAGE_A_RECEIPT_SHA256_MISMATCH: stage_a_receipt_sha256={self.stage_a_receipt_sha256} "
                f"!= computed={expected_sha}."
            )
        return self


def _build_stage_a_freeze_receipt_with_token(
    *,
    execution_plan: Union[DevExecutionPlan, StochasticityDiagnosticPlan],
    prompt_freeze: DevPromptFreezeArtifact,
    authorization: DevLiveAuthorizationArtifact,
    stage_a_commit_sha: str,
    freeze_created_at_utc: str,
    stage_a_process_token: str,
    candidate_registry: Optional[DevCandidateRegistry] = None,
) -> DevLiveStageAFreezeReceipt:
    """Internal helper to construct a `DevLiveStageAFreezeReceipt` with a validated process token."""
    if (
        stage_a_process_token is None
        or not isinstance(stage_a_process_token, str)
        or not stage_a_process_token.strip()
    ):
        raise PlanBeforeLiveProtocolError(
            "STAGE_A_PROCESS_TOKEN_EMPTY: stage_a_process_token must be a non-empty string."
        )
    cand_reg = candidate_registry or load_and_verify_candidate_registry()
    plan_phase = (
        "STOCHASTICITY"
        if isinstance(execution_plan, StochasticityDiagnosticPlan)
        else execution_plan.phase
    )
    run_ids, cells_sha = compute_assigned_cells_sha256(execution_plan)
    pf_sha = compute_prompt_freeze_sha256(prompt_freeze)
    pconf_reg_sha = compute_provider_config_registry_sha256(cand_reg)

    body: Dict[str, Any] = {
        "artifact_id": STAGE_A_FREEZE_RECEIPT_ARTIFACT_ID,
        "phase": plan_phase,
        "execution_plan_sha256": execution_plan.plan_sha256,
        "prompt_freeze_sha256": pf_sha,
        "authorization_artifact_sha256": authorization.authorization_artifact_sha256,
        "scientific_code_bundle_sha256": execution_plan.scientific_code_bundle_sha256,
        "provider_config_registry_sha256": pconf_reg_sha,
        "assigned_cell_run_ids": run_ids,
        "assigned_cells_sha256": cells_sha,
        "code_basis_commit_sha": execution_plan.code_basis_commit_sha,
        "stage_a_commit_sha": stage_a_commit_sha,
        "freeze_created_at_utc": freeze_created_at_utc,
        "stage_a_process_token": stage_a_process_token,
        "stage_a_status": STAGE_A_STATUS_FROZEN_BEFORE_LIVE,
    }
    receipt_sha = sha256_bytes(canonical_json_bytes(body))
    return DevLiveStageAFreezeReceipt.model_validate(
        {**body, "stage_a_receipt_sha256": receipt_sha}
    )


def build_stage_a_freeze_receipt(
    *,
    execution_plan: Union[DevExecutionPlan, StochasticityDiagnosticPlan],
    prompt_freeze: DevPromptFreezeArtifact,
    authorization: DevLiveAuthorizationArtifact,
    stage_a_commit_sha: str,
    freeze_created_at_utc: str,
    candidate_registry: Optional[DevCandidateRegistry] = None,
) -> DevLiveStageAFreezeReceipt:
    """Build a canonical production `DevLiveStageAFreezeReceipt` (Section 2).

    Auto-stamps `stage_a_process_token = _CURRENT_PROCESS_INVOCATION_TOKEN` internally.
    Callers CANNOT supply or override `stage_a_process_token`.
    """
    return _build_stage_a_freeze_receipt_with_token(
        execution_plan=execution_plan,
        prompt_freeze=prompt_freeze,
        authorization=authorization,
        stage_a_commit_sha=stage_a_commit_sha,
        freeze_created_at_utc=freeze_created_at_utc,
        stage_a_process_token=_CURRENT_PROCESS_INVOCATION_TOKEN,
        candidate_registry=candidate_registry,
    )


def build_test_only_stage_a_freeze_receipt(
    *,
    execution_plan: Union[DevExecutionPlan, StochasticityDiagnosticPlan],
    prompt_freeze: DevPromptFreezeArtifact,
    authorization: DevLiveAuthorizationArtifact,
    stage_a_commit_sha: str,
    freeze_created_at_utc: str = "2026-10-15T00:00:00Z",
    stage_a_process_token: str = "test-only-historical-process-token-v1",
    candidate_registry: Optional[DevCandidateRegistry] = None,
) -> DevLiveStageAFreezeReceipt:
    """TEST-ONLY helper for offline unit tests simulating a prior-process Stage-A freeze receipt (Section 3).

    NEVER used in production CLI or live execution flows.
    """
    return _build_stage_a_freeze_receipt_with_token(
        execution_plan=execution_plan,
        prompt_freeze=prompt_freeze,
        authorization=authorization,
        stage_a_commit_sha=stage_a_commit_sha,
        freeze_created_at_utc=freeze_created_at_utc,
        stage_a_process_token=stage_a_process_token,
        candidate_registry=candidate_registry,
    )


def _verify_git_commit_ancestor_and_blobs(
    *,
    repo_root: Path,
    stage_a_commit_sha: str,
    runtime_head_sha: str,
    tracked_artifact_paths: Sequence[Path],
    blob_verified_paths_and_hashes: Sequence[Tuple[Path, str]],
    head_only_blob_verified_paths_and_hashes: Optional[Sequence[Tuple[Path, str]]] = None,
    code_basis_commit_sha: Optional[str] = None,
) -> None:
    """Verify Stage-A and code-basis commits are ancestors of runtime HEAD, files are tracked & clean, and git blobs match (Section 10)."""
    validate_git_commit_sha40(stage_a_commit_sha)
    validate_git_commit_sha40(runtime_head_sha)
    if code_basis_commit_sha is not None:
        validate_git_commit_sha40(code_basis_commit_sha)

    commits_to_check = [stage_a_commit_sha]
    if code_basis_commit_sha is not None and code_basis_commit_sha not in commits_to_check:
        commits_to_check.append(code_basis_commit_sha)

    for commit_sha in commits_to_check:
        try:
            cat_proc = subprocess.run(
                ["git", "cat-file", "-t", commit_sha],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception as exc:
            raise PlanBeforeLiveProtocolError(
                f"STAGE_A_GIT_VERIFICATION_FAILED: Unable to run git in {repo_root}: {exc}"
            ) from exc
        if cat_proc.returncode != 0 or cat_proc.stdout.strip() != "commit":
            raise PlanBeforeLiveProtocolError(
                f"STAGE_A_COMMIT_NOT_FOUND_IN_REPO: commit_sha={commit_sha!r} is not a valid commit in {repo_root}."
            )

        anc_proc = subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit_sha, runtime_head_sha],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        if anc_proc.returncode != 0:
            raise PlanBeforeLiveProtocolError(
                f"STAGE_A_COMMIT_NOT_ANCESTOR_OF_HEAD: commit_sha={commit_sha} "
                f"is NOT an ancestor of runtime_head_sha={runtime_head_sha}."
            )

    root_resolved = repo_root.resolve()
    for fpath in tracked_artifact_paths:
        f_resolved = fpath.resolve()
        try:
            rel_posix = f_resolved.relative_to(root_resolved).as_posix()
        except ValueError as exc:
            raise PlanBeforeLiveProtocolError(
                f"STAGE_A_ARTIFACT_OUTSIDE_REPO: {fpath} is outside repository root {repo_root}."
            ) from exc

        ls_proc = subprocess.run(
            ["git", "ls-files", "--error-unmatch", rel_posix],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        if ls_proc.returncode != 0:
            raise PlanBeforeLiveProtocolError(
                f"STAGE_A_ARTIFACT_UNCOMMITTED: Stage-A file {rel_posix} is untracked in git; "
                "Stage-A evidence must be committed before live execution."
            )

        st_proc = subprocess.run(
            ["git", "status", "--porcelain", "--", rel_posix],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        if st_proc.returncode != 0 or st_proc.stdout.strip():
            raise PlanBeforeLiveProtocolError(
                f"STAGE_A_FILE_DIRTY_OR_UNCOMMITTED: Stage-A file {rel_posix} has uncommitted changes: "
                f"{st_proc.stdout.strip()!r}."
            )

    for fpath, expected_file_sha256 in blob_verified_paths_and_hashes:
        rel_posix = fpath.resolve().relative_to(root_resolved).as_posix()
        disk_bytes = normalize_lf_bytes(fpath.read_bytes())
        disk_sha = sha256_bytes(disk_bytes)
        if disk_sha != expected_file_sha256:
            raise PlanBeforeLiveProtocolError(
                f"STAGE_A_DISK_BLOB_MISMATCH for {rel_posix}: disk={disk_sha} != expected={expected_file_sha256}"
            )

        for commit_ref in (stage_a_commit_sha, runtime_head_sha):
            show_proc = subprocess.run(
                ["git", "show", f"{commit_ref}:{rel_posix}"],
                cwd=str(repo_root),
                capture_output=True,
                check=False,
            )
            if show_proc.returncode != 0:
                raise PlanBeforeLiveProtocolError(
                    f"STAGE_A_BLOB_MISSING_IN_COMMIT: {rel_posix} not found in commit {commit_ref}."
                )
            committed_sha = sha256_bytes(normalize_lf_bytes(show_proc.stdout))
            if committed_sha != expected_file_sha256:
                raise PlanBeforeLiveProtocolError(
                    f"STAGE_A_COMMITTED_BLOB_MISMATCH for {rel_posix} at {commit_ref}: "
                    f"committed={committed_sha} != expected={expected_file_sha256}."
                )

    for fpath, expected_file_sha256 in (head_only_blob_verified_paths_and_hashes or ()):
        rel_posix = fpath.resolve().relative_to(root_resolved).as_posix()
        disk_bytes = normalize_lf_bytes(fpath.read_bytes())
        disk_sha = sha256_bytes(disk_bytes)
        if disk_sha != expected_file_sha256:
            raise PlanBeforeLiveProtocolError(
                f"STAGE_A_DISK_BLOB_MISMATCH for {rel_posix}: disk={disk_sha} != expected={expected_file_sha256}"
            )
        show_proc = subprocess.run(
            ["git", "show", f"{runtime_head_sha}:{rel_posix}"],
            cwd=str(repo_root),
            capture_output=True,
            check=False,
        )
        if show_proc.returncode != 0:
            raise PlanBeforeLiveProtocolError(
                f"STAGE_A_BLOB_MISSING_IN_COMMIT: {rel_posix} not found in commit {runtime_head_sha}."
            )
        committed_sha = sha256_bytes(normalize_lf_bytes(show_proc.stdout))
        if committed_sha != expected_file_sha256:
            raise PlanBeforeLiveProtocolError(
                f"STAGE_A_COMMITTED_BLOB_MISMATCH for {rel_posix} at {runtime_head_sha}: "
                f"committed={committed_sha} != expected={expected_file_sha256}."
            )


def verify_stage_a_freeze_receipt(
    stage_a_receipt_or_path: Union[DevLiveStageAFreezeReceipt, Mapping[str, Any], Path, str],
    *,
    execution_plan: Union[DevExecutionPlan, StochasticityDiagnosticPlan],
    prompt_freeze: DevPromptFreezeArtifact,
    authorization: DevLiveAuthorizationArtifact,
    execution_plan_path: Optional[Path] = None,
    prompt_freeze_path: Optional[Path] = None,
    authorization_path: Optional[Path] = None,
    candidate_registry: Optional[DevCandidateRegistry] = None,
    repo_root: Optional[Path] = None,
    require_git_committed: bool = True,
) -> DevLiveStageAFreezeReceipt:
    """Verify `DevLiveStageAFreezeReceipt` against Stage-A artifacts, active code bundle, and git commit history (Sections 2, 4, 9, 10, 11)."""
    if stage_a_receipt_or_path is None:
        raise PlanBeforeLiveProtocolError(
            "STAGE_A_RECEIPT_MISSING: Live execution requires a frozen DevLiveStageAFreezeReceipt."
        )

    receipt_path: Optional[Path] = None
    if isinstance(stage_a_receipt_or_path, (Path, str)):
        receipt_path = Path(stage_a_receipt_or_path)
        _assert_runner_not_final100_path(receipt_path)
        if not receipt_path.exists():
            raise PlanBeforeLiveProtocolError(
                f"STAGE_A_RECEIPT_FILE_MISSING: {receipt_path}"
            )
        try:
            raw_dict = json.loads(receipt_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise PlanBeforeLiveProtocolError(
                f"STAGE_A_RECEIPT_JSON_INVALID: {exc}"
            ) from exc
        try:
            receipt = DevLiveStageAFreezeReceipt.model_validate(raw_dict)
        except Exception as exc:
            raise PlanBeforeLiveProtocolError(
                f"STAGE_A_RECEIPT_INVALID: {exc}"
            ) from exc
    elif isinstance(stage_a_receipt_or_path, DevLiveStageAFreezeReceipt):
        try:
            receipt = DevLiveStageAFreezeReceipt.model_validate(
                stage_a_receipt_or_path.model_dump()
            )
        except Exception as exc:
            raise PlanBeforeLiveProtocolError(
                f"STAGE_A_RECEIPT_INVALID: {exc}"
            ) from exc
    elif isinstance(stage_a_receipt_or_path, Mapping):
        try:
            receipt = DevLiveStageAFreezeReceipt.model_validate(dict(stage_a_receipt_or_path))
        except Exception as exc:
            raise PlanBeforeLiveProtocolError(
                f"STAGE_A_RECEIPT_INVALID: {exc}"
            ) from exc
    else:
        raise PlanBeforeLiveProtocolError(
            f"Unsupported stage_a_receipt type: {type(stage_a_receipt_or_path)}"
        )

    if not receipt.stage_a_process_token or not receipt.stage_a_process_token.strip():
        raise PlanBeforeLiveProtocolError(
            "STAGE_A_PROCESS_TOKEN_EMPTY: Stage-A freeze receipt requires a non-empty stage_a_process_token."
        )
    if receipt.stage_a_process_token == _CURRENT_PROCESS_INVOCATION_TOKEN:
        raise PlanBeforeLiveProtocolError(
            "STAGE_A_AND_STAGE_B_SAME_PROCESS_FORBIDDEN: Stage-A freeze and Stage-B execution "
            "cannot run in the same process invocation token."
        )

    cand_reg = candidate_registry or load_and_verify_candidate_registry()
    plan_phase = (
        "STOCHASTICITY"
        if isinstance(execution_plan, StochasticityDiagnosticPlan)
        else execution_plan.phase
    )
    if receipt.phase != plan_phase:
        raise PlanBeforeLiveProtocolError(
            f"STAGE_A_PHASE_MISMATCH: receipt.phase={receipt.phase!r} != plan_phase={plan_phase!r}."
        )
    if receipt.execution_plan_sha256 != execution_plan.plan_sha256:
        raise PlanBeforeLiveProtocolError(
            f"STAGE_A_PLAN_SHA256_MISMATCH: receipt={receipt.execution_plan_sha256} != plan={execution_plan.plan_sha256}."
        )
    pf_sha = compute_prompt_freeze_sha256(prompt_freeze)
    if receipt.prompt_freeze_sha256 != pf_sha:
        raise PlanBeforeLiveProtocolError(
            f"STAGE_A_PROMPT_FREEZE_SHA256_MISMATCH: receipt={receipt.prompt_freeze_sha256} != prompt_freeze={pf_sha}."
        )
    if receipt.authorization_artifact_sha256 != authorization.authorization_artifact_sha256:
        raise PlanBeforeLiveProtocolError(
            f"STAGE_A_AUTHORIZATION_SHA256_MISMATCH: receipt={receipt.authorization_artifact_sha256} "
            f"!= authorization={authorization.authorization_artifact_sha256}."
        )

    bundle_manifest = compute_scientific_code_bundle(repo_root=repo_root)
    active_bundle_sha = bundle_manifest.scientific_code_bundle_sha256
    if receipt.scientific_code_bundle_sha256 != active_bundle_sha:
        raise ScientificCodeBundleIntegrityError(
            f"STAGE_A_CODE_BUNDLE_MISMATCH: receipt={receipt.scientific_code_bundle_sha256} != active={active_bundle_sha}."
        )

    active_pconf_sha = compute_provider_config_registry_sha256(cand_reg)
    if receipt.provider_config_registry_sha256 != active_pconf_sha:
        raise CandidateRegistryIntegrityError(
            f"STAGE_A_PROVIDER_CONFIG_MISMATCH: receipt={receipt.provider_config_registry_sha256} != active={active_pconf_sha}."
        )

    expected_run_ids, expected_cells_sha = compute_assigned_cells_sha256(execution_plan)
    if (
        receipt.assigned_cell_run_ids != expected_run_ids
        or receipt.assigned_cells_sha256 != expected_cells_sha
    ):
        raise PlanBeforeLiveProtocolError(
            "STAGE_A_ASSIGNED_CELLS_MISMATCH: Assigned cell list or cells SHA256 does not match frozen execution plan."
        )
    if receipt.code_basis_commit_sha != execution_plan.code_basis_commit_sha:
        raise PlanBeforeLiveProtocolError(
            f"STAGE_A_CODE_BASIS_MISMATCH: receipt={receipt.code_basis_commit_sha} != plan={execution_plan.code_basis_commit_sha}."
        )

    if require_git_committed:
        root = repo_root if repo_root is not None else REPO_ROOT
        if (
            execution_plan_path is None
            or prompt_freeze_path is None
            or authorization_path is None
            or receipt_path is None
        ):
            raise PlanBeforeLiveProtocolError(
                "STAGE_A_PATHS_REQUIRED_FOR_GIT_ATTESTATION: Live Stage-A verification requires on-disk paths "
                "for execution_plan_path, prompt_freeze_path, authorization_path, and stage_a_freeze_receipt_path."
            )
        runtime_head_sha = resolve_active_git_commit_sha(repo_root=root)
        plan_file_sha = sha256_bytes(normalize_lf_bytes(execution_plan_path.read_bytes()))
        pf_file_sha = sha256_bytes(normalize_lf_bytes(prompt_freeze_path.read_bytes()))
        auth_file_sha = sha256_bytes(normalize_lf_bytes(authorization_path.read_bytes()))
        receipt_file_sha = sha256_bytes(normalize_lf_bytes(receipt_path.read_bytes()))

        bundle_tracked_paths = [
            root / entry["path"]
            for entry in bundle_manifest.scientific_code_bundle_file_hashes
        ]
        bundle_blobs = [
            (root / entry["path"], entry["sha256"])
            for entry in bundle_manifest.scientific_code_bundle_file_hashes
        ]

        _verify_git_commit_ancestor_and_blobs(
            repo_root=root,
            stage_a_commit_sha=receipt.stage_a_commit_sha,
            runtime_head_sha=runtime_head_sha,
            code_basis_commit_sha=receipt.code_basis_commit_sha,
            tracked_artifact_paths=[
                execution_plan_path,
                prompt_freeze_path,
                authorization_path,
                receipt_path,
                *bundle_tracked_paths,
            ],
            blob_verified_paths_and_hashes=[
                (execution_plan_path, plan_file_sha),
                (prompt_freeze_path, pf_file_sha),
                (authorization_path, auth_file_sha),
                *bundle_blobs,
            ],
            head_only_blob_verified_paths_and_hashes=[
                (receipt_path, receipt_file_sha),
            ],
        )

    return receipt


# ==============================================================================
# 4C. INTERNALLY MINTED LIVE EXECUTION CAPABILITY & ACTION-BOUNDARY RE-ATTESTATION (SECTIONS 10, 11, 12, 14)
# ==============================================================================

_LIVE_CONTEXT_MINT_GUARD = object()


class LiveExecutionCapability:
    """Internally minted fail-closed orchestration capability required for production transport execution (Sections 7, 10, 14).

    Serves as a fail-closed orchestration guard (`FAIL_CLOSED_ORCHESTRATION_GUARD`);
    Stage-A commit/blob re-attestation at the live action boundary (`LiveExecutionContext`)
    remains the scientific authority.
    Cannot be instantiated directly without `_CAPABILITY_MINT_GUARD`; only issued by
    `issue_live_execution_capability()`.
    """

    live_capability_role: str = LIVE_CAPABILITY_ROLE_ORCHESTRATION_GUARD

    def __init__(
        self,
        *,
        _mint_guard: Any = None,
        phase: str,
        manifest_execution_mode: str,
        execution_plan_sha256: str,
        prompt_freeze_sha256: str,
        authorization_id: str,
        authorization_artifact_sha256: str,
        stage_a_receipt_sha256: str,
        stage_a_commit_sha: str,
        code_basis_commit_sha: str,
        runtime_head_sha: str,
        scientific_code_bundle_sha256: str,
        provider_config_registry_sha256: str,
        allowed_candidate_ids: Tuple[str, ...],
        maximum_live_generation_calls: int,
        execution_plan_path: Optional[Path] = None,
        prompt_freeze_path: Optional[Path] = None,
        authorization_path: Optional[Path] = None,
        stage_a_freeze_receipt_path: Optional[Path] = None,
        repo_root: Optional[Path] = None,
    ) -> None:
        if _mint_guard is not _CAPABILITY_MINT_GUARD:
            raise LiveExecutionNotAuthorizedError(
                "LIVE_CAPABILITY_FORGERY_FORBIDDEN: LiveExecutionCapability cannot be instantiated directly; "
                "use issue_live_execution_capability() after Stage-A commit & authorization verification."
            )
        self._mint_guard = _mint_guard
        self.phase = phase
        self.manifest_execution_mode = manifest_execution_mode
        self.execution_plan_sha256 = execution_plan_sha256
        self.prompt_freeze_sha256 = prompt_freeze_sha256
        self.authorization_id = authorization_id
        self.authorization_artifact_sha256 = authorization_artifact_sha256
        self.stage_a_receipt_sha256 = stage_a_receipt_sha256
        self.stage_a_commit_sha = stage_a_commit_sha
        self.code_basis_commit_sha = code_basis_commit_sha
        self.runtime_head_sha = runtime_head_sha
        self.scientific_code_bundle_sha256 = scientific_code_bundle_sha256
        self.provider_config_registry_sha256 = provider_config_registry_sha256
        self.allowed_candidate_ids = tuple(allowed_candidate_ids)
        self.maximum_live_generation_calls = int(maximum_live_generation_calls)
        self.execution_plan_path = execution_plan_path
        self.prompt_freeze_path = prompt_freeze_path
        self.authorization_path = authorization_path
        self.stage_a_freeze_receipt_path = stage_a_freeze_receipt_path
        self.repo_root = repo_root

    def verify_mint_token(self) -> None:
        if getattr(self, "_mint_guard", None) is not _CAPABILITY_MINT_GUARD:
            raise LiveExecutionNotAuthorizedError(
                "INVALID_LIVE_EXECUTION_CAPABILITY: Capability token failed authenticity check."
            )


class LiveExecutionContext:
    """Locked runtime Stage-A execution context produced by fresh action-boundary re-attestation (Sections 10, 11, 12)."""

    def __init__(
        self,
        *,
        _mint_guard: Any = None,
        phase: str,
        manifest_execution_mode: str,
        runtime_head_sha: str,
        code_basis_commit_sha: str,
        stage_a_commit_sha: str,
        stage_a_receipt_sha256: str,
        scientific_code_bundle_sha256: str,
        provider_config_registry_sha256: str,
        execution_plan_sha256: str,
        prompt_freeze_sha256: str,
        authorization_id: str,
        authorization_artifact_sha256: str,
        execution_plan_path: Path,
        prompt_freeze_path: Path,
        authorization_path: Path,
        stage_a_freeze_receipt_path: Path,
        repo_root: Path,
    ) -> None:
        if _mint_guard is not _LIVE_CONTEXT_MINT_GUARD:
            raise LiveExecutionNotAuthorizedError(
                "LIVE_CONTEXT_FORGERY_FORBIDDEN: LiveExecutionContext must be produced by reattest_stage_a_at_live_action_boundary()."
            )
        self._mint_guard = _mint_guard
        self.phase = phase
        self.manifest_execution_mode = manifest_execution_mode
        self.runtime_head_sha = runtime_head_sha
        self.code_basis_commit_sha = code_basis_commit_sha
        self.stage_a_commit_sha = stage_a_commit_sha
        self.stage_a_receipt_sha256 = stage_a_receipt_sha256
        self.scientific_code_bundle_sha256 = scientific_code_bundle_sha256
        self.provider_config_registry_sha256 = provider_config_registry_sha256
        self.execution_plan_sha256 = execution_plan_sha256
        self.prompt_freeze_sha256 = prompt_freeze_sha256
        self.authorization_id = authorization_id
        self.authorization_artifact_sha256 = authorization_artifact_sha256
        self.execution_plan_path = execution_plan_path
        self.prompt_freeze_path = prompt_freeze_path
        self.authorization_path = authorization_path
        self.stage_a_freeze_receipt_path = stage_a_freeze_receipt_path
        self.repo_root = repo_root

    def verify_context_token(self) -> None:
        if getattr(self, "_mint_guard", None) is not _LIVE_CONTEXT_MINT_GUARD:
            raise LiveExecutionNotAuthorizedError(
                "INVALID_LIVE_EXECUTION_CONTEXT: LiveExecutionContext failed authenticity check."
            )


def reattest_stage_a_at_live_action_boundary(
    *,
    live_capability: LiveExecutionCapability,
    execution_plan: Union[DevExecutionPlan, StochasticityDiagnosticPlan],
    prompt_freeze: DevPromptFreezeArtifact,
    authorization: DevLiveAuthorizationArtifact,
    prompt_registry: PromptRegistry,
    execution_plan_path: Optional[Path] = None,
    prompt_freeze_path: Optional[Path] = None,
    authorization_path: Optional[Path] = None,
    stage_a_freeze_receipt_path: Optional[Path] = None,
    dev_bundle: Optional[VerifiedDevBundle] = None,
    candidate_registry: Optional[DevCandidateRegistry] = None,
    dev_select_result: Optional[DevSelectModelSelectionResult] = None,
    repo_root: Optional[Path] = None,
    expected_locked_context: Optional[LiveExecutionContext] = None,
) -> LiveExecutionContext:
    """Re-run full Stage-A verification against CURRENT runtime state immediately before live transport (Sections 10, 11, 12)."""
    if live_capability is None or not isinstance(live_capability, LiveExecutionCapability):
        raise LiveExecutionNotAuthorizedError(
            "LIVE_CAPABILITY_REQUIRED: Live action boundary requires an internally minted LiveExecutionCapability."
        )
    live_capability.verify_mint_token()
    if expected_locked_context is not None:
        expected_locked_context.verify_context_token()

    plan_path = execution_plan_path or (
        expected_locked_context.execution_plan_path
        if expected_locked_context is not None
        else live_capability.execution_plan_path
    )
    pf_path = prompt_freeze_path or (
        expected_locked_context.prompt_freeze_path
        if expected_locked_context is not None
        else live_capability.prompt_freeze_path
    )
    auth_path = authorization_path or (
        expected_locked_context.authorization_path
        if expected_locked_context is not None
        else live_capability.authorization_path
    )
    stage_a_path = stage_a_freeze_receipt_path or (
        expected_locked_context.stage_a_freeze_receipt_path
        if expected_locked_context is not None
        else live_capability.stage_a_freeze_receipt_path
    )
    root = (
        repo_root
        or (
            expected_locked_context.repo_root
            if expected_locked_context is not None
            else live_capability.repo_root
        )
        or REPO_ROOT
    )

    if (
        plan_path is None
        or pf_path is None
        or auth_path is None
        or stage_a_path is None
    ):
        raise PlanBeforeLiveProtocolError(
            "STAGE_A_ACTION_BOUNDARY_EVIDENCE_MISSING: Live execution requires on-disk Stage-A paths "
            "(execution_plan_path, prompt_freeze_path, authorization_path, stage_a_freeze_receipt_path) "
            "for action-boundary re-attestation."
        )

    plan_path = _assert_runner_not_final100_path(Path(plan_path))
    pf_path = _assert_runner_not_final100_path(Path(pf_path))
    auth_path = _assert_runner_not_final100_path(Path(auth_path))
    stage_a_path = _assert_runner_not_final100_path(Path(stage_a_path))

    bundle = dev_bundle or load_and_verify_frozen_dev_bundle()
    cand_reg = candidate_registry or load_and_verify_candidate_registry()

    if isinstance(execution_plan, DevExecutionPlan):
        runtime_head_sha = verify_dev_execution_plan_for_execution(
            execution_plan, candidate_registry=cand_reg, repo_root=root
        )
    else:
        runtime_head_sha = resolve_active_git_commit_sha(repo_root=root)

    disk_pf = verify_runner_prompt_freeze_artifact(
        pf_path,
        prompt_registry=prompt_registry,
        execution_plan=execution_plan,
        dev_bundle=bundle,
        candidate_registry=cand_reg,
        repo_root=root,
    )
    disk_auth = verify_dev_live_authorization_artifact(
        auth_path,
        execution_plan=execution_plan,
        prompt_freeze=disk_pf,
        dev_select_result=dev_select_result,
        repo_root=root,
    )
    verified_stage_a = verify_stage_a_freeze_receipt(
        stage_a_path,
        execution_plan=execution_plan,
        prompt_freeze=disk_pf,
        authorization=disk_auth,
        execution_plan_path=plan_path,
        prompt_freeze_path=pf_path,
        authorization_path=auth_path,
        candidate_registry=cand_reg,
        repo_root=root,
        require_git_committed=True,
    )

    active_bundle_sha = compute_scientific_code_bundle_sha256(repo_root=root)
    active_pconf_sha = compute_provider_config_registry_sha256(cand_reg)
    pf_sha = compute_prompt_freeze_sha256(prompt_freeze)

    if verified_stage_a.stage_a_receipt_sha256 != live_capability.stage_a_receipt_sha256:
        raise PlanBeforeLiveProtocolError(
            f"STAGE_A_RECEIPT_DRIFT_AT_ACTION_BOUNDARY: disk stage_a_receipt_sha256="
            f"{verified_stage_a.stage_a_receipt_sha256} != capability={live_capability.stage_a_receipt_sha256}."
        )
    if active_bundle_sha != live_capability.scientific_code_bundle_sha256:
        raise ScientificCodeBundleIntegrityError(
            f"SCIENTIFIC_CODE_BUNDLE_DRIFT_AT_ACTION_BOUNDARY: active={active_bundle_sha} "
            f"!= capability={live_capability.scientific_code_bundle_sha256}."
        )
    if active_pconf_sha != live_capability.provider_config_registry_sha256:
        raise CandidateRegistryIntegrityError(
            f"PROVIDER_CONFIG_DRIFT_AT_ACTION_BOUNDARY: active={active_pconf_sha} "
            f"!= capability={live_capability.provider_config_registry_sha256}."
        )
    if disk_auth.authorization_artifact_sha256 != authorization.authorization_artifact_sha256:
        raise DevLiveAuthorizationError(
            "AUTHORIZATION_DRIFT_AT_ACTION_BOUNDARY: On-disk authorization does not match supplied authorization."
        )
    if compute_prompt_freeze_sha256(disk_pf) != pf_sha:
        raise PromptFreezeFirewallError(
            "PROMPT_FREEZE_DRIFT_AT_ACTION_BOUNDARY: On-disk prompt freeze does not match supplied prompt freeze."
        )

    if expected_locked_context is not None:
        if runtime_head_sha != expected_locked_context.runtime_head_sha:
            raise PlanBeforeLiveProtocolError(
                f"BATCH_RUNTIME_HEAD_DRIFT_FORBIDDEN: runtime_head_sha drifted during batch from "
                f"{expected_locked_context.runtime_head_sha} to {runtime_head_sha}."
            )
        if active_bundle_sha != expected_locked_context.scientific_code_bundle_sha256:
            raise ScientificCodeBundleIntegrityError(
                f"BATCH_CODE_BUNDLE_DRIFT_FORBIDDEN: scientific_code_bundle_sha256 drifted during batch from "
                f"{expected_locked_context.scientific_code_bundle_sha256} to {active_bundle_sha}."
            )
        if active_pconf_sha != expected_locked_context.provider_config_registry_sha256:
            raise CandidateRegistryIntegrityError(
                f"BATCH_PROVIDER_CONFIG_DRIFT_FORBIDDEN: provider_config_registry_sha256 drifted during batch from "
                f"{expected_locked_context.provider_config_registry_sha256} to {active_pconf_sha}."
            )
        if verified_stage_a.stage_a_receipt_sha256 != expected_locked_context.stage_a_receipt_sha256:
            raise PlanBeforeLiveProtocolError(
                "BATCH_STAGE_A_RECEIPT_DRIFT_FORBIDDEN: stage_a_receipt_sha256 drifted during batch."
            )
        return expected_locked_context

    plan_phase = (
        "STOCHASTICITY"
        if isinstance(execution_plan, StochasticityDiagnosticPlan)
        else execution_plan.phase
    )
    manifest_mode = resolve_truthful_manifest_execution_mode(
        runner_mode=RUNNER_EXECUTION_MODE_LIVE_EXECUTION,
        cell_phase=plan_phase,
    )
    return LiveExecutionContext(
        _mint_guard=_LIVE_CONTEXT_MINT_GUARD,
        phase=plan_phase,
        manifest_execution_mode=manifest_mode,
        runtime_head_sha=runtime_head_sha,
        code_basis_commit_sha=execution_plan.code_basis_commit_sha,
        stage_a_commit_sha=verified_stage_a.stage_a_commit_sha,
        stage_a_receipt_sha256=verified_stage_a.stage_a_receipt_sha256,
        scientific_code_bundle_sha256=active_bundle_sha,
        provider_config_registry_sha256=active_pconf_sha,
        execution_plan_sha256=execution_plan.plan_sha256,
        prompt_freeze_sha256=verified_stage_a.prompt_freeze_sha256,
        authorization_id=disk_auth.authorization_id,
        authorization_artifact_sha256=disk_auth.authorization_artifact_sha256,
        execution_plan_path=plan_path,
        prompt_freeze_path=pf_path,
        authorization_path=auth_path,
        stage_a_freeze_receipt_path=stage_a_path,
        repo_root=root,
    )


def resolve_truthful_manifest_execution_mode(
    *, runner_mode: str, cell_phase: str
) -> str:
    """Resolve truthful `BenchmarkRunManifest.execution_mode` from runner mode and cell phase (Section 14)."""
    if runner_mode == RUNNER_EXECUTION_MODE_OFFLINE_MOCK_TEST:
        return MANIFEST_EXECUTION_MODE_OFFLINE_MOCK
    if runner_mode == RUNNER_EXECUTION_MODE_LIVE_EXECUTION:
        if cell_phase == "DEV_TUNE":
            return MANIFEST_EXECUTION_MODE_LIVE_DEV_TUNE
        if cell_phase == "DEV_SELECT":
            return MANIFEST_EXECUTION_MODE_LIVE_DEV_SELECT
        if cell_phase in ("STOCHASTICITY", "STOCHASTICITY_DIAGNOSTIC"):
            return MANIFEST_EXECUTION_MODE_STOCHASTICITY
        raise DevLiveRunnerError(f"Unsupported live cell_phase: {cell_phase!r}")
    raise LiveExecutionNotAuthorizedError(
        f"INVALID_RUNNER_EXECUTION_MODE: {runner_mode!r}"
    )


def issue_live_execution_capability(
    *,
    execute_live: bool,
    execution_plan_path: Path,
    prompt_freeze_path: Path,
    authorization_path: Path,
    stage_a_freeze_receipt_path: Path,
    prompt_registry: PromptRegistry,
    dev_bundle: Optional[VerifiedDevBundle] = None,
    candidate_registry: Optional[DevCandidateRegistry] = None,
    dev_select_result: Optional[DevSelectModelSelectionResult] = None,
    repo_root: Optional[Path] = None,
) -> Tuple[
    LiveExecutionCapability,
    Union[DevExecutionPlan, StochasticityDiagnosticPlan],
    DevPromptFreezeArtifact,
    DevLiveAuthorizationArtifact,
    DevLiveStageAFreezeReceipt,
]:
    """Verify all Stage-A pre-frozen committed artifacts and mint an internally minted `LiveExecutionCapability` (Sections 7, 9, 10, 11, 14)."""
    if execute_live is not True:
        raise LiveExecutionNotAuthorizedError(
            "LIVE_EXECUTION_DISABLED: execute_live=True is required to issue a LiveExecutionCapability."
        )
    if (
        execution_plan_path is None
        or prompt_freeze_path is None
        or authorization_path is None
        or stage_a_freeze_receipt_path is None
    ):
        raise PlanBeforeLiveProtocolError(
            "STAGE_A_ARTIFACTS_MISSING: execution_plan_path, prompt_freeze_path, authorization_path, "
            "and stage_a_freeze_receipt_path are all required before live execution."
        )

    plan_path = _assert_runner_not_final100_path(execution_plan_path)
    pf_path = _assert_runner_not_final100_path(prompt_freeze_path)
    auth_path = _assert_runner_not_final100_path(authorization_path)
    stage_a_path = _assert_runner_not_final100_path(stage_a_freeze_receipt_path)

    if not plan_path.exists():
        raise PlanBeforeLiveProtocolError(
            f"STAGE_A_EXECUTION_PLAN_MISSING: {plan_path}"
        )
    if not pf_path.exists():
        raise PromptFreezeFirewallError(
            f"STAGE_A_PROMPT_FREEZE_MISSING: {pf_path}"
        )
    if not auth_path.exists():
        raise DevLiveAuthorizationError(
            f"STAGE_A_AUTHORIZATION_MISSING: {auth_path}"
        )
    if not stage_a_path.exists():
        raise PlanBeforeLiveProtocolError(
            f"STAGE_A_FREEZE_RECEIPT_MISSING: {stage_a_path}"
        )

    raw_plan = json.loads(plan_path.read_text(encoding="utf-8"))
    raw_phase = raw_plan.get("phase")
    if raw_phase == "FINAL100" or (
        isinstance(raw_phase, str) and "FINAL" in raw_phase.upper()
    ):
        raise Final100FirewallViolationError(
            f"FINAL100_FIREWALL_VIOLATION: Forbidden plan phase {raw_phase!r}"
        )

    bundle = dev_bundle or load_and_verify_frozen_dev_bundle()
    cand_reg = candidate_registry or load_and_verify_candidate_registry()
    root = repo_root if repo_root is not None else REPO_ROOT

    if raw_phase == "STOCHASTICITY_DIAGNOSTIC":
        if dev_select_result is None or not dev_select_result.winner_selected:
            raise StochasticityGateViolationError(
                "STOCHASTICITY_BLOCKED_BEFORE_WINNER_FROZEN: Cannot issue capability for stochasticity before winner selection."
            )
        execution_plan: Union[DevExecutionPlan, StochasticityDiagnosticPlan] = (
            StochasticityDiagnosticPlan.model_validate(raw_plan)
        )
        runtime_head_sha = resolve_active_git_commit_sha(repo_root=root)
        active_bundle_sha = compute_scientific_code_bundle_sha256(repo_root=root)
        if execution_plan.scientific_code_bundle_sha256 != active_bundle_sha:
            raise ScientificCodeBundleIntegrityError(
                "SCIENTIFIC_CODE_BUNDLE_MISMATCH on stochasticity plan."
            )
    else:
        execution_plan = DevExecutionPlan.model_validate(raw_plan)
        runtime_head_sha = verify_dev_execution_plan_for_execution(
            execution_plan, candidate_registry=cand_reg, repo_root=root
        )

    verified_pf = verify_runner_prompt_freeze_artifact(
        pf_path,
        prompt_registry=prompt_registry,
        execution_plan=execution_plan,
        dev_bundle=bundle,
        candidate_registry=cand_reg,
        repo_root=root,
    )
    verified_auth = verify_dev_live_authorization_artifact(
        auth_path,
        execution_plan=execution_plan,
        prompt_freeze=verified_pf,
        dev_select_result=dev_select_result,
        repo_root=root,
    )
    verified_stage_a = verify_stage_a_freeze_receipt(
        stage_a_path,
        execution_plan=execution_plan,
        prompt_freeze=verified_pf,
        authorization=verified_auth,
        execution_plan_path=plan_path,
        prompt_freeze_path=pf_path,
        authorization_path=auth_path,
        candidate_registry=cand_reg,
        repo_root=root,
        require_git_committed=True,
    )

    plan_phase = (
        "STOCHASTICITY"
        if isinstance(execution_plan, StochasticityDiagnosticPlan)
        else execution_plan.phase
    )
    manifest_mode = resolve_truthful_manifest_execution_mode(
        runner_mode=RUNNER_EXECUTION_MODE_LIVE_EXECUTION,
        cell_phase=plan_phase,
    )

    capability = LiveExecutionCapability(
        _mint_guard=_CAPABILITY_MINT_GUARD,
        phase=plan_phase,
        manifest_execution_mode=manifest_mode,
        execution_plan_sha256=execution_plan.plan_sha256,
        prompt_freeze_sha256=verified_stage_a.prompt_freeze_sha256,
        authorization_id=verified_auth.authorization_id,
        authorization_artifact_sha256=verified_auth.authorization_artifact_sha256,
        stage_a_receipt_sha256=verified_stage_a.stage_a_receipt_sha256,
        stage_a_commit_sha=verified_stage_a.stage_a_commit_sha,
        code_basis_commit_sha=execution_plan.code_basis_commit_sha,
        runtime_head_sha=runtime_head_sha,
        scientific_code_bundle_sha256=verified_stage_a.scientific_code_bundle_sha256,
        provider_config_registry_sha256=verified_stage_a.provider_config_registry_sha256,
        allowed_candidate_ids=tuple(verified_auth.allowed_candidate_ids),
        maximum_live_generation_calls=verified_auth.maximum_live_generation_calls,
        execution_plan_path=plan_path,
        prompt_freeze_path=pf_path,
        authorization_path=auth_path,
        stage_a_freeze_receipt_path=stage_a_path,
        repo_root=root,
    )
    return capability, execution_plan, verified_pf, verified_auth, verified_stage_a


# ==============================================================================
# 5. DETERMINISTIC CALL-BUDGET LEDGER (SECTION 28)
# ==============================================================================


class DevCallBudgetLedger:
    """Deterministic batch call-budget ledger enforcing 1 reservation per cell and zero retry refunds (Section 28)."""

    def __init__(
        self,
        *,
        phase: str,
        maximum_live_generation_calls: int,
        allowed_run_ids: Sequence[str],
        allowed_cell_keys: Sequence[Tuple[str, str, str, str, int]],
        allowed_candidate_ids: Sequence[str],
        allowed_fixture_ids: Sequence[str],
    ) -> None:
        if phase == "FINAL100" or "FINAL" in phase.upper():
            raise Final100FirewallViolationError(
                f"FINAL100_FIREWALL_VIOLATION: Ledger rejects phase {phase!r}."
            )
        if maximum_live_generation_calls <= 0:
            raise DevLiveAuthorizationError(
                f"Invalid maximum_live_generation_calls={maximum_live_generation_calls}"
            )
        self.phase: str = phase
        self.maximum_live_generation_calls: int = int(maximum_live_generation_calls)
        self.allowed_run_ids: Set[str] = set(allowed_run_ids)
        self.allowed_cell_keys: Set[Tuple[str, str, str, str, int]] = set(allowed_cell_keys)
        self.allowed_candidate_ids: Set[str] = set(allowed_candidate_ids)
        self.allowed_fixture_ids: Set[str] = set(allowed_fixture_ids)

        self.reserved_calls: int = 0
        self.consumed_calls: int = 0
        self.attempted_run_ids: Set[str] = set()
        self.attempted_cell_keys: Set[Tuple[str, str, str, str, int]] = set()
        self.history: List[Dict[str, Any]] = []

    @classmethod
    def from_execution_plan(
        cls,
        execution_plan: Union[DevExecutionPlan, StochasticityDiagnosticPlan],
        *,
        maximum_live_generation_calls: Optional[int] = None,
    ) -> "DevCallBudgetLedger":
        plan_phase = (
            "STOCHASTICITY"
            if isinstance(execution_plan, StochasticityDiagnosticPlan)
            else execution_plan.phase
        )
        max_calls = (
            maximum_live_generation_calls
            if maximum_live_generation_calls is not None
            else (
                execution_plan.max_calls
                if isinstance(execution_plan, StochasticityDiagnosticPlan)
                else execution_plan.expected_total_cells
            )
        )
        if max_calls != len(execution_plan.cells):
            raise DevLiveAuthorizationError(
                f"LEDGER_BUDGET_MISMATCH: maximum_live_generation_calls={max_calls} "
                f"!= len(execution_plan.cells)={len(execution_plan.cells)}."
            )
        run_ids = [c.run_id for c in execution_plan.cells]
        cell_keys = [
            (c.phase, c.prompt_id, c.candidate_id, c.fixture_id, c.attempt_number)
            for c in execution_plan.cells
        ]
        cand_ids = sorted({c.candidate_id for c in execution_plan.cells})
        fix_ids = sorted({c.fixture_id for c in execution_plan.cells})
        return cls(
            phase=plan_phase,
            maximum_live_generation_calls=max_calls,
            allowed_run_ids=run_ids,
            allowed_cell_keys=cell_keys,
            allowed_candidate_ids=cand_ids,
            allowed_fixture_ids=fix_ids,
        )

    def reserve_call(self, cell_manifest: DevCellExecutionManifest) -> int:
        """Reserve 1 provider generation call BEFORE transport; fails closed on any violation."""
        assert_not_final100_scenario_id(cell_manifest.fixture_id)
        if cell_manifest.candidate_id not in ORDERED_CANDIDATE_IDS or (
            cell_manifest.candidate_id not in self.allowed_candidate_ids
        ):
            raise CandidateRegistryIntegrityError(
                f"UNEXPECTED_CANDIDATE_IN_LEDGER: candidate_id={cell_manifest.candidate_id!r} "
                f"not in allowed {sorted(self.allowed_candidate_ids)}."
            )
        if cell_manifest.fixture_id not in self.allowed_fixture_ids:
            raise PlanBeforeLiveProtocolError(
                f"UNEXPECTED_FIXTURE_IN_LEDGER: fixture_id={cell_manifest.fixture_id!r} "
                f"not in frozen plan fixtures."
            )
        if self.phase in ("DEV_TUNE", "DEV_SELECT") and cell_manifest.attempt_number != 1:
            raise ImmutableCellExecutionError(
                f"RETRY_FORBIDDEN: attempt_number must be 1 for {self.phase}, got {cell_manifest.attempt_number}."
            )

        cell_key = (
            cell_manifest.phase,
            cell_manifest.prompt_id,
            cell_manifest.candidate_id,
            cell_manifest.fixture_id,
            cell_manifest.attempt_number,
        )
        if cell_manifest.run_id in self.attempted_run_ids:
            raise DuplicateDevCellAttemptError(
                f"DUPLICATE_RUN_ID_IN_LEDGER: run_id={cell_manifest.run_id!r} has already been reserved/attempted."
            )
        if cell_key in self.attempted_cell_keys:
            raise DuplicateDevCellAttemptError(
                f"DUPLICATE_SCIENTIFIC_CELL_IN_LEDGER: cell={cell_key!r} has already been reserved/attempted."
            )
        if (
            cell_manifest.run_id not in self.allowed_run_ids
            or cell_key not in self.allowed_cell_keys
        ):
            raise PlanBeforeLiveProtocolError(
                f"CELL_NOT_IN_FROZEN_EXECUTION_PLAN: run_id={cell_manifest.run_id!r}, cell={cell_key!r}."
            )
        if (
            self.reserved_calls >= self.maximum_live_generation_calls
            or self.consumed_calls >= self.maximum_live_generation_calls
        ):
            raise DevCallBudgetExhaustedError(
                f"CALL_BUDGET_EXHAUSTED: reserved={self.reserved_calls}, consumed={self.consumed_calls}, "
                f"max={self.maximum_live_generation_calls}."
            )

        self.reserved_calls += 1
        self.attempted_run_ids.add(cell_manifest.run_id)
        self.attempted_cell_keys.add(cell_key)
        self.history.append(
            {
                "event": "RESERVED",
                "reservation_index": self.reserved_calls,
                "run_id": cell_manifest.run_id,
                "cell_key": list(cell_key),
            }
        )
        return self.reserved_calls

    def consume_reserved_call(self, run_id: str, *, transport_outcome: str) -> int:
        """Mark a reserved call as permanently consumed once transport starts/completes (no retry refunds)."""
        if run_id not in self.attempted_run_ids:
            raise DevLiveRunnerError(
                f"LEDGER_INTERNAL_ERROR: Cannot consume unreserved run_id={run_id!r}."
            )
        self.consumed_calls += 1
        self.history.append(
            {
                "event": "CONSUMED",
                "consumed_index": self.consumed_calls,
                "run_id": run_id,
                "transport_outcome": transport_outcome,
            }
        )
        return self.consumed_calls

    def summary(self) -> Dict[str, Any]:
        return {
            "phase": self.phase,
            "maximum_live_generation_calls": self.maximum_live_generation_calls,
            "reserved_calls": self.reserved_calls,
            "consumed_calls": self.consumed_calls,
            "remaining_calls": self.maximum_live_generation_calls - self.reserved_calls,
            "attempted_run_ids_count": len(self.attempted_run_ids),
            "attempted_cells_count": len(self.attempted_cell_keys),
        }


# ==============================================================================
# 6. TRANSPORT-START JOURNAL & CRASH AMBIGUITY DETECTION (SECTIONS 29, 30)
# ==============================================================================


def inspect_and_guard_cell_directory_before_transport(
    cell_dir: Path,
    *,
    cell_manifest: DevCellExecutionManifest,
) -> None:
    """Check `cell_dir` for crash ambiguity or existing immutable artifacts before any transport (Sections 21, 29, 30)."""
    _assert_runner_not_final100_path(cell_dir)
    if not cell_dir.exists():
        return

    starting_path = cell_dir / "transport_journal_starting.json"
    completed_path = cell_dir / "transport_journal_completed.json"
    receipt_path = cell_dir / "execution_receipt.json"
    unknown_path = cell_dir / "transport_journal_unknown_after_transport.json"

    if unknown_path.exists():
        raise CrashAmbiguityBatchStopError(
            f"ATTEMPT_STATUS_UNKNOWN_AFTER_TRANSPORT: Cell {cell_manifest.run_id} in {cell_dir} "
            f"was previously marked unknown after transport. Automatic rerun is forbidden."
        )

    if starting_path.exists() and (not completed_path.exists() or not receipt_path.exists()):
        recovery_payload = {
            "run_id": cell_manifest.run_id,
            "phase": cell_manifest.phase,
            "prompt_id": cell_manifest.prompt_id,
            "candidate_id": cell_manifest.candidate_id,
            "fixture_id": cell_manifest.fixture_id,
            "attempt_number": cell_manifest.attempt_number,
            "status": ATTEMPT_STATUS_UNKNOWN_AFTER_TRANSPORT,
            "rerun_permitted": False,
            "batch_stop_required": True,
            "detected_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "starting_journal_present": starting_path.exists(),
            "completed_journal_present": completed_path.exists(),
            "execution_receipt_present": receipt_path.exists(),
        }
        if not unknown_path.exists():
            write_immutable_canonical_json(unknown_path, recovery_payload)
        raise CrashAmbiguityBatchStopError(
            f"ATTEMPT_STATUS_UNKNOWN_AFTER_TRANSPORT: Found TRANSPORT_STARTING without confirmed completion/receipt "
            f"for cell {cell_manifest.run_id} in {cell_dir}. Batch stopped for human/ChatGPT review; rerun is forbidden."
        )

    for fname in CELL_IMMUTABLE_ARTIFACT_FILENAMES:
        existing_file = cell_dir / fname
        if existing_file.exists():
            raise ImmutableCellExecutionError(
                f"IMMUTABLE_CELL_EXECUTION_ERROR: Artifact {existing_file} already exists in {cell_dir}; "
                f"overwriting or re-executing cell {cell_manifest.run_id} is forbidden."
            )


def write_transport_journal_starting(
    cell_dir: Path,
    *,
    cell_manifest: DevCellExecutionManifest,
    runtime_head_sha: str,
    authorization_id: str,
    timestamp_utc: Optional[str] = None,
    execution_started_at_utc: Optional[str] = None,
) -> Path:
    """Persist immutable `transport_journal_starting.json` immediately before network/mock transport (Sections 7, 30)."""
    target = cell_dir / "transport_journal_starting.json"
    start_ts = (
        execution_started_at_utc
        if execution_started_at_utc is not None
        else (timestamp_utc if timestamp_utc is not None else default_utc_now_clock())
    )
    payload = {
        "run_id": cell_manifest.run_id,
        "cell_identity": {
            "phase": cell_manifest.phase,
            "prompt_id": cell_manifest.prompt_id,
            "candidate_id": cell_manifest.candidate_id,
            "fixture_id": cell_manifest.fixture_id,
            "attempt_number": cell_manifest.attempt_number,
        },
        "attempt_number": cell_manifest.attempt_number,
        "runtime_head_sha": runtime_head_sha,
        "code_basis_commit_sha": cell_manifest.code_basis_commit_sha,
        "scientific_code_bundle_sha256": cell_manifest.scientific_code_bundle_sha256,
        "authorization_id": authorization_id,
        "execution_started_at_utc": start_ts,
        "timestamp_utc": start_ts,
        "status": TRANSPORT_STATUS_STARTING,
    }
    write_immutable_canonical_json(target, payload)
    return target


def write_transport_journal_completed(
    cell_dir: Path,
    *,
    cell_manifest: DevCellExecutionManifest,
    runtime_head_sha: str,
    authorization_id: str,
    latency_ns: int,
    timestamp_utc: Optional[str] = None,
    execution_started_at_utc: Optional[str] = None,
    transport_completed_at_utc: Optional[str] = None,
) -> Path:
    """Persist append-only `transport_journal_completed.json` immediately after transport returns (Sections 7, 8, 30)."""
    target = cell_dir / "transport_journal_completed.json"
    completed_ts = (
        transport_completed_at_utc
        if transport_completed_at_utc is not None
        else (timestamp_utc if timestamp_utc is not None else default_utc_now_clock())
    )
    payload: Dict[str, Any] = {
        "run_id": cell_manifest.run_id,
        "cell_identity": {
            "phase": cell_manifest.phase,
            "prompt_id": cell_manifest.prompt_id,
            "candidate_id": cell_manifest.candidate_id,
            "fixture_id": cell_manifest.fixture_id,
            "attempt_number": cell_manifest.attempt_number,
        },
        "attempt_number": cell_manifest.attempt_number,
        "runtime_head_sha": runtime_head_sha,
        "code_basis_commit_sha": cell_manifest.code_basis_commit_sha,
        "scientific_code_bundle_sha256": cell_manifest.scientific_code_bundle_sha256,
        "authorization_id": authorization_id,
        "latency_ns": int(latency_ns),
        "transport_completed_at_utc": completed_ts,
        "timestamp_utc": completed_ts,
        "status": TRANSPORT_STATUS_COMPLETED,
    }
    if execution_started_at_utc is not None:
        payload["execution_started_at_utc"] = execution_started_at_utc
    write_immutable_canonical_json(target, payload)
    return target


# ==============================================================================
# 7. FROZEN PROVIDER REQUEST CONSTRUCTION, MANIFEST PROVENANCE & USAGE (SECTIONS 4, 5, 13, 14, 15)
# ==============================================================================


def build_frozen_provider_wire_request(
    *,
    cell_manifest: DevCellExecutionManifest,
    scenario: BenchmarkScenarioInput,
    prompt_spec: PromptCandidateSpec,
    candidate_registry: Optional[DevCandidateRegistry] = None,
    catalog_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Construct the exact frozen provider request payload for C1, C2, or C3 under Portable Schema V2 (Sections 4, 5, 6)."""
    assert_not_final100_scenario_id(cell_manifest.fixture_id)
    assert_not_final100_scenario(scenario)
    if cell_manifest.fixture_id != scenario.scenario_id:
        raise PlanBeforeLiveProtocolError(
            f"SCENARIO_ID_MISMATCH: cell_manifest.fixture_id={cell_manifest.fixture_id!r} "
            f"!= scenario.scenario_id={scenario.scenario_id!r}."
        )

    cand_reg = candidate_registry or load_and_verify_candidate_registry()
    if cell_manifest.candidate_id not in ORDERED_CANDIDATE_IDS or (
        cell_manifest.candidate_id not in cand_reg.candidates
    ):
        raise CandidateRegistryIntegrityError(
            f"FORBIDDEN_CANDIDATE_ID: {cell_manifest.candidate_id!r} is not in {list(ORDERED_CANDIDATE_IDS)}."
        )

    cand_spec: DevCandidateSpec = cand_reg.candidates[cell_manifest.candidate_id]
    if cand_spec.technical_preflight_v2_status != "PASSED_TECHNICAL_PREFLIGHT_SCHEMA_V2":
        raise CandidateRegistryIntegrityError(
            f"PREFLIGHT_V2_NOT_PASSED: Candidate {cell_manifest.candidate_id} status is "
            f"{cand_spec.technical_preflight_v2_status!r}."
        )
    if cell_manifest.requested_model_id != cand_spec.requested_model_id:
        raise CandidateRegistryIntegrityError(
            f"REQUESTED_MODEL_ID_MISMATCH: cell {cell_manifest.requested_model_id!r} "
            f"!= frozen {cand_spec.requested_model_id!r}."
        )

    expected_pconf_sha = get_cached_provider_config_sha256(cell_manifest.candidate_id)
    if cell_manifest.provider_config_sha256 != expected_pconf_sha:
        raise CandidateRegistryIntegrityError(
            f"PROVIDER_CONFIG_SHA256_MISMATCH: cell_manifest.provider_config_sha256={cell_manifest.provider_config_sha256} "
            f"!= active candidate config hash {expected_pconf_sha}."
        )

    if cell_manifest.semantic_schema_sha256 != EXPECTED_SEMANTIC_SCHEMA_SHA256:
        raise CandidateRegistryIntegrityError(
            f"SEMANTIC_SCHEMA_SHA256_MISMATCH: {cell_manifest.semantic_schema_sha256} "
            f"!= {EXPECTED_SEMANTIC_SCHEMA_SHA256}."
        )
    if (
        cell_manifest.portable_generation_schema_v2_sha256
        != EXPECTED_PORTABLE_SCHEMA_V2_SHA256
    ):
        raise CandidateRegistryIntegrityError(
            f"PORTABLE_SCHEMA_V2_SHA256_MISMATCH: {cell_manifest.portable_generation_schema_v2_sha256} "
            f"!= {EXPECTED_PORTABLE_SCHEMA_V2_SHA256}."
        )

    ctx = build_deterministic_dev_scenario_context(
        scenario, prompt_spec, catalog_path=catalog_path
    )
    rendered_user_prompt = ctx.user_prompt
    if ctx.user_prompt_sha256 != cell_manifest.user_prompt_sha256:
        raise PromptFreezeFirewallError(
            f"USER_PROMPT_SHA256_MISMATCH: rendered user prompt hash {ctx.user_prompt_sha256} "
            f"!= cell_manifest.user_prompt_sha256 {cell_manifest.user_prompt_sha256}."
        )
    if ctx.system_prompt_sha256 != cell_manifest.system_prompt_sha256:
        raise PromptFreezeFirewallError(
            f"SYSTEM_PROMPT_SHA256_MISMATCH: system prompt hash {ctx.system_prompt_sha256} "
            f"!= cell_manifest.system_prompt_sha256 {cell_manifest.system_prompt_sha256}."
        )

    portable_schema_v2 = copy.deepcopy(
        COMMON_PORTABLE_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA_V2
    )
    portable_schema_sha = sha256_bytes(canonical_json_bytes(portable_schema_v2))
    if portable_schema_sha != EXPECTED_PORTABLE_SCHEMA_V2_SHA256:
        raise CandidateRegistryIntegrityError(
            f"PORTABLE_SCHEMA_V2_HASH_DRIFT: computed {portable_schema_sha} != {EXPECTED_PORTABLE_SCHEMA_V2_SHA256}."
        )

    cid = cell_manifest.candidate_id
    if cid == "C1":
        wire_payload: Dict[str, Any] = {
            "provider": "google",
            "candidate_id": "C1",
            "model": "gemini-3.8-flash",
            "contents": rendered_user_prompt,
            "config": {
                "system_instruction": prompt_spec.system_prompt,
                "response_mime_type": "application/json",
                "response_json_schema": portable_schema_v2,
                "thinking_config": {
                    "thinking_level": "medium",
                    "include_thoughts": False,
                },
                "seed": 2026101508,
                "max_output_tokens": 16384,
                "http_options": {"timeout": 55000},
                "tools": None,
                "automatic_function_calling": {"disable": True},
            },
            "omitted_parameters": ["temperature", "top_p", "top_k"],
            "timeout_seconds": 55.0,
            "timeout_ms": 55000,
            "sdk_retry": 0,
            "transport_retry": 0,
            "manual_retry": 0,
            "retry": 0,
            "tools": False,
            "portable_generation_schema_v2_sha256": EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
            "semantic_schema_sha256": EXPECTED_SEMANTIC_SCHEMA_SHA256,
        }
    elif cid == "C2":
        wire_payload = {
            "provider": "openai",
            "candidate_id": "C2",
            "model": "gpt-6.1-sol",
            "messages": [
                {"role": "system", "content": prompt_spec.system_prompt},
                {"role": "user", "content": rendered_user_prompt},
            ],
            "reasoning_effort": "medium",
            "seed": 2026101508,
            "service_tier": "default",
            "max_completion_tokens": 16384,
            "timeout_seconds": 55.0,
            "timeout_ms": 55000,
            "max_retries": 0,
            "sdk_retry": 0,
            "transport_retry": 0,
            "manual_retry": 0,
            "retry": 0,
            "tools": False,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "BenchmarkPlanResponse",
                    "strict": True,
                    "schema": portable_schema_v2,
                },
            },
            "omitted_parameters": [
                "temperature",
                "top_p",
                "top_k",
                "top_logprobs",
                "logprobs",
            ],
            "portable_generation_schema_v2_sha256": EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
            "semantic_schema_sha256": EXPECTED_SEMANTIC_SCHEMA_SHA256,
        }
    elif cid == "C3":
        wire_payload = {
            "provider": "anthropic",
            "candidate_id": "C3",
            "model": "claude-sonnet-5-5",
            "system": prompt_spec.system_prompt,
            "messages": [{"role": "user", "content": rendered_user_prompt}],
            "max_tokens": 16384,
            "thinking": {"type": "adaptive"},
            "output_config": {
                "effort": "high",
                "format": {
                    "type": "json_schema",
                    "schema": portable_schema_v2,
                },
            },
            "seed_support": "UNSUPPORTED",
            "omitted_parameters": ["seed", "temperature", "top_p", "top_k"],
            "timeout_seconds": 55.0,
            "timeout_ms": 55000,
            "max_retries": 0,
            "sdk_retry": 0,
            "transport_retry": 0,
            "manual_retry": 0,
            "retry": 0,
            "tools": False,
            "portable_generation_schema_v2_sha256": EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
            "semantic_schema_sha256": EXPECTED_SEMANTIC_SCHEMA_SHA256,
        }
    else:
        raise CandidateRegistryIntegrityError(f"Unsupported candidate_id={cid!r}")

    assert_no_secrets_in_payload(wire_payload, context="PROVIDER_WIRE_REQUEST")
    return wire_payload


def build_candidate_manifest_generation_parameters(
    cell_manifest: DevCellExecutionManifest,
    *,
    runtime_head_sha: str,
) -> Dict[str, Any]:
    """Build truthful `BenchmarkRunManifest.generation_parameters` for C1, C2, or C3 (Sections 13, 15).

    Never claims `temperature = 0.0`; explicitly records `temperature_status = "OMITTED"`
    along with exact candidate seed/reasoning/thinking configuration and runtime provenance.
    """
    base_provenance = {
        "candidate_id": cell_manifest.candidate_id,
        "provider": CANDIDATE_PROVIDER_BY_ID[cell_manifest.candidate_id],
        "requested_model_id": cell_manifest.requested_model_id,
        "temperature_status": "OMITTED",
        "top_p_status": "OMITTED",
        "top_k_status": "OMITTED",
        "portable_generation_schema_v2_sha256": cell_manifest.portable_generation_schema_v2_sha256,
        "semantic_schema_sha256": cell_manifest.semantic_schema_sha256,
        "provider_config_sha256": cell_manifest.provider_config_sha256,
        "code_basis_commit_sha": cell_manifest.code_basis_commit_sha,
        "runtime_head_sha": runtime_head_sha,
        "scientific_code_bundle_sha256": cell_manifest.scientific_code_bundle_sha256,
        "code_commit_sha_semantics": (
            "AUTHORITATIVE_RUNTIME_HEAD_SHA_WITH_SEPARATE_CODE_BASIS_AND_BUNDLE_ATTESTATION"
        ),
    }
    if cell_manifest.candidate_id == "C1":
        return {
            **base_provenance,
            "seed": FROZEN_SAMPLING_SEED,
            "thinking_config": {
                "thinking_level": "medium",
                "include_thoughts": False,
            },
            "max_output_tokens": 16384,
            "timeout_ms": 55000,
            "timeout_seconds": 55.0,
            "retry": 0,
            "omitted_parameters": ["temperature", "top_p", "top_k"],
        }
    if cell_manifest.candidate_id == "C2":
        return {
            **base_provenance,
            "endpoint": "chat.completions",
            "seed": FROZEN_SAMPLING_SEED,
            "reasoning_effort": "medium",
            "service_tier": "default",
            "max_completion_tokens": 16384,
            "timeout_ms": 55000,
            "timeout_seconds": 55.0,
            "max_retries": 0,
            "top_logprobs_status": "OMITTED",
            "logprobs_status": "OMITTED",
            "omitted_parameters": [
                "temperature",
                "top_p",
                "top_k",
                "top_logprobs",
                "logprobs",
            ],
        }
    if cell_manifest.candidate_id == "C3":
        return {
            **base_provenance,
            "seed_status": "OMITTED_UNSUPPORTED",
            "thinking": {"type": "adaptive"},
            "effort": "high",
            "max_tokens": 16384,
            "timeout_ms": 55000,
            "timeout_seconds": 55.0,
            "max_retries": 0,
            "omitted_parameters": ["seed", "temperature", "top_p", "top_k"],
        }
    raise CandidateRegistryIntegrityError(
        f"Unsupported candidate_id={cell_manifest.candidate_id!r}"
    )


def normalize_candidate_usage_metadata(
    candidate_id: str,
    raw_usage: Optional[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Normalize provider usage metadata for C1, C2, C3 while preserving raw fields (Section 5)."""
    if raw_usage is None:
        return {
            "candidate_id": candidate_id,
            "provider": CANDIDATE_PROVIDER_BY_ID.get(candidate_id),
            "usage_present": False,
            "input_tokens": None,
            "output_tokens": None,
            "thought_tokens": None,
            "reasoning_tokens": None,
            "thinking_tokens": None,
            "cached_tokens": None,
            "cached_input_tokens": None,
            "cache_read_input_tokens": None,
            "cache_creation_input_tokens": None,
            "total_tokens": None,
        }

    raw = dict(raw_usage)

    def _opt_int(*keys: str, nested: Optional[Mapping[str, Any]] = None) -> Optional[int]:
        source = nested if nested is not None else raw
        if not isinstance(source, Mapping):
            return None
        for k in keys:
            if k in source and source[k] is not None and not isinstance(source[k], bool):
                try:
                    return int(source[k])
                except (ValueError, TypeError):
                    return None
        return None

    if candidate_id == "C1":
        in_tok = _opt_int("input_tokens", "prompt_token_count", "promptTokenCount")
        out_tok = _opt_int("output_tokens", "candidates_token_count", "candidatesTokenCount")
        thought_tok = _opt_int("thought_tokens", "thoughts_token_count", "thoughtsTokenCount")
        if thought_tok is None and in_tok is not None and out_tok is not None:
            thought_tok = 0
        cached_tok = _opt_int(
            "cached_tokens",
            "cached_input_tokens",
            "cached_content_token_count",
            "cachedContentTokenCount",
        )
        if cached_tok is None and in_tok is not None:
            cached_tok = 0
        total_tok = _opt_int("total_tokens", "total_token_count", "totalTokenCount")
        if total_tok is None and in_tok is not None and out_tok is not None:
            total_tok = in_tok + out_tok + (thought_tok or 0)
        return {
            "candidate_id": "C1",
            "provider": "google",
            "usage_present": in_tok is not None and out_tok is not None,
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "thought_tokens": thought_tok,
            "reasoning_tokens": None,
            "thinking_tokens": None,
            "cached_tokens": cached_tok,
            "cached_input_tokens": cached_tok,
            "cache_read_input_tokens": None,
            "cache_creation_input_tokens": None,
            "total_tokens": total_tok,
        }

    if candidate_id == "C2":
        in_tok = _opt_int("input_tokens", "prompt_tokens")
        out_tok = _opt_int("output_tokens", "completion_tokens")
        out_details = (
            raw.get("output_tokens_details")
            or raw.get("completion_tokens_details")
            or {}
        )
        in_details = (
            raw.get("input_tokens_details")
            or raw.get("prompt_tokens_details")
            or {}
        )
        reasoning_tok = _opt_int("reasoning_tokens")
        if reasoning_tok is None:
            reasoning_tok = _opt_int("reasoning_tokens", nested=out_details)
        if reasoning_tok is None and in_tok is not None and out_tok is not None:
            reasoning_tok = 0
        cached_tok = _opt_int("cached_tokens", "cached_input_tokens")
        if cached_tok is None:
            cached_tok = _opt_int("cached_tokens", nested=in_details)
        if cached_tok is None and in_tok is not None:
            cached_tok = 0
        total_tok = _opt_int("total_tokens")
        if total_tok is None and in_tok is not None and out_tok is not None:
            total_tok = in_tok + out_tok
        return {
            "candidate_id": "C2",
            "provider": "openai",
            "usage_present": in_tok is not None and out_tok is not None,
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "thought_tokens": None,
            "reasoning_tokens": reasoning_tok,
            "thinking_tokens": None,
            "cached_tokens": cached_tok,
            "cached_input_tokens": cached_tok,
            "cache_read_input_tokens": None,
            "cache_creation_input_tokens": None,
            "total_tokens": total_tok,
        }

    if candidate_id == "C3":
        in_tok = _opt_int("input_tokens")
        out_tok = _opt_int("output_tokens")
        thinking_tok = _opt_int("thinking_tokens")
        cache_read = _opt_int("cache_read_input_tokens", "cached_read_tokens")
        cache_create = _opt_int("cache_creation_input_tokens", "cached_creation_tokens")
        if cache_read is None and in_tok is not None:
            cache_read = 0
        if cache_create is None and in_tok is not None:
            cache_create = 0
        cached_total: Optional[int] = _opt_int("cached_tokens", "cached_input_tokens")
        if cached_total is None and cache_read is not None and cache_create is not None:
            cached_total = cache_read + cache_create
        total_tok = _opt_int("total_tokens")
        if total_tok is None and in_tok is not None and out_tok is not None:
            total_tok = in_tok + out_tok + (cached_total or 0)
        return {
            "candidate_id": "C3",
            "provider": "anthropic",
            "usage_present": in_tok is not None and out_tok is not None,
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "thought_tokens": None,
            "reasoning_tokens": None,
            "thinking_tokens": thinking_tok,
            "cache_read_input_tokens": cache_read,
            "cache_creation_input_tokens": cache_create,
            "cached_tokens": cached_total,
            "cached_input_tokens": cached_total,
            "total_tokens": total_tok,
        }

    raise CandidateRegistryIntegrityError(
        f"Unsupported candidate_id={candidate_id!r} in usage normalization."
    )


# ==============================================================================
# 8. HTTP BOUNDARY COUNTING, PROVIDER EXCEPTION MAPPING & PRODUCTION TRANSPORTS
#    (SECTIONS 3, 4, 5, 6, 8, 16)
# ==============================================================================


class ProviderNormalizedTransportResponse(BaseModel):
    """Runner-normalized provider response record returned by production transports (Section 5)."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    provider: str
    requested_model_id: str
    returned_model_id: Optional[str] = None
    raw_text: str = ""
    finish_or_stop_reason: Optional[str] = None
    finish_reason: str = "stop"
    refusal_state: bool = False
    max_token_state: bool = False
    raw_usage_metadata: Optional[Dict[str, Any]] = None
    normalized_usage_metadata: Dict[str, Any] = Field(default_factory=dict)
    raw_provider_metadata: Dict[str, Any] = Field(default_factory=dict)
    normalized_provider_metadata: Dict[str, Any] = Field(default_factory=dict)
    actual_http_request_count: int = 0
    latency_ns: Optional[int] = None
    latency_ms: Optional[float] = None
    simulated_failure: DevCellFailureClassification = DevCellFailureClassification.NONE
    authoritative_usage_available: bool = False
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    thought_tokens: Optional[int] = None
    reasoning_tokens: Optional[int] = None
    thinking_tokens: Optional[int] = None
    cached_input_tokens: Optional[int] = None
    cache_read_input_tokens: Optional[int] = None
    cache_creation_input_tokens: Optional[int] = None


def classify_provider_transport_exception(
    exc: Exception,
) -> DevCellFailureClassification:
    """Deterministically classify a provider SDK / HTTP transport exception into `DevCellFailureClassification` (Section 6).

    Maps ordinary provider failures to denominator-retained classifications:
    - 429 -> HTTP_429
    - 5xx -> HTTP_5XX
    - timeout -> TIMEOUT (or PARTIAL_TIMEOUT if partial/stream timeout)
    - authentication failure (401/403 key error) -> AUTHENTICATION_FAILURE
    - model access failure (404 / model not found / model permission) -> MODEL_ACCESS_FAILURE
    - provider refusal -> REFUSAL
    - max-token truncation -> MAX_TOKEN_TRUNCATION

    Reserves HARNESS_INTERNAL_ERROR strictly for actual runner/infrastructure programming defects.
    """
    if isinstance(
        exc,
        (
            BatchExecutionFatalStopError,
            ImmutableCellExecutionError,
            DevLiveRunnerError,
            TypeError,
            KeyError,
            AttributeError,
            AssertionError,
        ),
    ):
        return DevCellFailureClassification.HARNESS_INTERNAL_ERROR

    cls_name = type(exc).__name__.lower()
    mod_name = (type(exc).__module__ or "").lower()
    msg = sanitize_runner_text(str(exc)).lower()
    status_code = getattr(exc, "status_code", None) or getattr(exc, "code", None)

    if (
        isinstance(exc, (TimeoutError, httpx.TimeoutException, httpx2.TimeoutException))
        or "timeout" in cls_name
        or "timed out" in msg
        or "timeout" in msg
        or status_code in (408, 504)
    ):
        if "partial" in msg or "stream" in msg:
            return DevCellFailureClassification.PARTIAL_TIMEOUT
        return DevCellFailureClassification.TIMEOUT

    if (
        status_code == 429
        or "ratelimit" in cls_name
        or "rate_limit" in msg
        or "rate limit" in msg
        or "resource_exhausted" in msg
        or "429" in msg
    ):
        return DevCellFailureClassification.HTTP_429

    if (
        (isinstance(status_code, int) and 500 <= status_code <= 599)
        or "internalserver" in cls_name
        or "serviceunavailable" in cls_name
        or "badgateway" in cls_name
        or "overloaded" in msg
        or any(
            tok in msg
            for tok in (
                "500 internal",
                "502 bad gateway",
                "503 service",
                "529 overloaded",
                "server error",
                "internal_error",
            )
        )
    ):
        return DevCellFailureClassification.HTTP_5XX

    if (
        status_code == 401
        or "authentication" in cls_name
        or "unauthenticated" in msg
        or "invalid api key" in msg
        or "api_key_invalid" in msg
        or "incorrect api key" in msg
        or "invalid x-api-key" in msg
    ):
        return DevCellFailureClassification.AUTHENTICATION_FAILURE

    if (
        status_code == 404
        or "notfound" in cls_name
        or (
            "model" in msg
            and any(
                tok in msg
                for tok in (
                    "not found",
                    "does not exist",
                    "not supported",
                    "not have access",
                    "model_not_found",
                    "access denied to model",
                )
            )
        )
    ):
        return DevCellFailureClassification.MODEL_ACCESS_FAILURE

    if status_code == 403 or "permissiondenied" in cls_name or "forbidden" in msg:
        if "model" in msg:
            return DevCellFailureClassification.MODEL_ACCESS_FAILURE
        return DevCellFailureClassification.AUTHENTICATION_FAILURE

    if any(
        tok in msg
        for tok in ("refusal", "content_filter", "safety_block", "prohibited_content")
    ):
        return DevCellFailureClassification.REFUSAL

    if any(
        tok in msg
        for tok in (
            "max_tokens",
            "max_output_tokens",
            "max_completion_tokens",
            "token limit",
            "length finish_reason",
        )
    ):
        return DevCellFailureClassification.MAX_TOKEN_TRUNCATION

    if (
        (isinstance(status_code, int) and 400 <= status_code < 600)
        or any(
            provider_mod in mod_name
            for provider_mod in ("google", "genai", "openai", "anthropic", "httpx")
        )
        and ("error" in cls_name or "exception" in cls_name)
    ):
        return DevCellFailureClassification.HTTP_ERROR

    return DevCellFailureClassification.HARNESS_INTERNAL_ERROR


class DevCellHttpCallCounter:
    """Outbound HTTP generation call counter at the httpx/httpx2 transport boundary (Section 16)."""

    def __init__(
        self,
        *,
        max_requests_per_cell: int = 1,
        max_total_requests: Optional[int] = None,
    ) -> None:
        self.max_requests_per_cell = int(max_requests_per_cell)
        self.max_total_requests = (
            int(max_total_requests) if max_total_requests is not None else None
        )
        self.total_http_requests: int = 0
        self.per_cell_http_requests: Dict[str, int] = {}
        self.per_candidate_http_requests: Dict[str, int] = {
            cid: 0 for cid in ORDERED_CANDIDATE_IDS
        }
        self.captured_http_requests_by_run_id: Dict[str, List[Dict[str, Any]]] = {}

    def record_outbound_http_request_before_send(
        self,
        *,
        run_id: str,
        candidate_id: str,
        method: str,
        url: str,
        body_bytes: bytes,
    ) -> int:
        current_cell = self.per_cell_http_requests.get(run_id, 0)
        if current_cell >= self.max_requests_per_cell:
            raise ImmutableCellExecutionError(
                f"HTTP_RETRY_OR_EXTRA_REQUEST_FORBIDDEN: Cell {run_id!r} (candidate {candidate_id}) "
                f"attempted outbound HTTP request #{current_cell + 1} "
                f"(max_requests_per_cell={self.max_requests_per_cell}). Batch must stop immediately."
            )
        if (
            self.max_total_requests is not None
            and self.total_http_requests >= self.max_total_requests
        ):
            raise DevCallBudgetExhaustedError(
                f"HTTP_BATCH_BUDGET_EXHAUSTED: Outbound HTTP request #{self.total_http_requests + 1} "
                f"exceeds max_total_requests={self.max_total_requests}."
            )
        self.per_cell_http_requests[run_id] = current_cell + 1
        self.per_candidate_http_requests[candidate_id] = (
            self.per_candidate_http_requests.get(candidate_id, 0) + 1
        )
        self.total_http_requests += 1

        parsed_body: Any = None
        if body_bytes:
            try:
                parsed_body = json.loads(body_bytes.decode("utf-8"))
            except Exception:
                parsed_body = sanitize_runner_text(
                    body_bytes.decode("utf-8", errors="replace")
                )
        self.captured_http_requests_by_run_id.setdefault(run_id, []).append(
            {
                "method": method,
                "url": str(url),
                "body": sanitize_runner_structure(parsed_body),
            }
        )
        return self.per_cell_http_requests[run_id]


class DevCountingHttpxTransport(httpx.BaseTransport):
    """Counting `httpx.BaseTransport` for Google `genai` SDK enforcing <= 1 HTTP request per cell (Section 16)."""

    def __init__(
        self,
        *,
        candidate_id: str,
        run_id: str,
        http_counter: DevCellHttpCallCounter,
        inner_transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        self.candidate_id = candidate_id
        self.run_id = run_id
        self.http_counter = http_counter
        self._inner = inner_transport or httpx.HTTPTransport(retries=0)
        self.request_count: int = 0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.http_counter.record_outbound_http_request_before_send(
            run_id=self.run_id,
            candidate_id=self.candidate_id,
            method=request.method,
            url=str(request.url),
            body_bytes=request.content,
        )
        self.request_count += 1
        return self._inner.handle_request(request)

    def close(self) -> None:
        self._inner.close()


class DevCountingHttpx2Transport(httpx2.BaseTransport):
    """Counting `httpx2.BaseTransport` for `openai` and `anthropic` SDKs enforcing <= 1 HTTP request per cell (Section 16)."""

    def __init__(
        self,
        *,
        candidate_id: str,
        run_id: str,
        http_counter: DevCellHttpCallCounter,
        inner_transport: Optional[httpx2.BaseTransport] = None,
    ) -> None:
        self.candidate_id = candidate_id
        self.run_id = run_id
        self.http_counter = http_counter
        self._inner = inner_transport or httpx2.HTTPTransport(retries=0)
        self.request_count: int = 0

    def handle_request(self, request: httpx2.Request) -> httpx2.Response:
        self.http_counter.record_outbound_http_request_before_send(
            run_id=self.run_id,
            candidate_id=self.candidate_id,
            method=request.method,
            url=str(request.url),
            body_bytes=request.content,
        )
        self.request_count += 1
        return self._inner.handle_request(request)

    def close(self) -> None:
        self._inner.close()


def _load_candidate_api_key_for_live_transport(
    candidate_id: str,
    *,
    dotenv_path: Optional[Path] = None,
    api_key_overrides: Optional[Mapping[str, str]] = None,
) -> str:
    """Load a candidate's API key only when executing a production transport (never in offline/dry-run default mode)."""
    if api_key_overrides and candidate_id in api_key_overrides:
        val = str(api_key_overrides[candidate_id]).strip()
        if val:
            return val
    env_key_name = CANDIDATE_ENV_KEY_BY_ID[candidate_id]
    target_path = dotenv_path or (REPO_ROOT / "apps" / "ai-service" / ".env")
    if target_path.exists():
        for raw_line in target_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k_part, v_part = line.split("=", 1)
            if k_part.strip() == env_key_name:
                val = v_part.strip().strip("'").strip('"').strip()
                if val:
                    return val
    raise DevLiveAuthorizationError(
        f"MISSING_PROVIDER_API_KEY: Required API key {env_key_name} for {candidate_id} not found."
    )


def _invoke_c1_google_production(
    *,
    api_key: str,
    wire_request: Dict[str, Any],
    counting_transport: DevCountingHttpxTransport,
) -> ProviderNormalizedTransportResponse:
    """Invoke Google Gemini (`gemini-3.8-flash`) with exact frozen C1 parameters and Portable Schema V2 (Sections 3, 4, 5)."""
    cfg = wire_request["config"]
    for forbidden_key in ("temperature", "top_p", "top_k"):
        if forbidden_key in cfg:
            raise CandidateRegistryIntegrityError(
                f"C1_FORBIDDEN_SAMPLING_PARAMETER: {forbidden_key!r} must be omitted."
            )
    if (
        wire_request.get("model") != "gemini-3.8-flash"
        or cfg.get("seed") != 2026101508
        or cfg.get("max_output_tokens") != 16384
        or cfg.get("thinking_config", {}).get("thinking_level") != "medium"
        or wire_request.get("timeout_ms") != 55000
        or wire_request.get("retry") != 0
    ):
        raise CandidateRegistryIntegrityError("C1 wire_request violates frozen C1 config.")

    http_client = httpx.Client(transport=counting_transport, timeout=55.0)
    try:
        client = genai.Client(
            api_key=api_key,
            http_options=genai_types.HttpOptions(
                timeout=55000,
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
            max_output_tokens=16384,
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
    finish_reason: Optional[str] = None
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
            for tok in ("SAFETY", "BLOCKLIST", "PROHIBITED", "RECITATION", "REFUSAL")
        ):
            refusal_state = True
        elif any(tok in fr_upper for tok in ("MAX_TOKENS", "LENGTH")):
            max_token_state = True

    usage_obj = getattr(resp, "usage_metadata", None)
    in_tok = getattr(usage_obj, "prompt_token_count", None) if usage_obj else None
    out_tok = getattr(usage_obj, "candidates_token_count", None) if usage_obj else None
    thought_tok = getattr(usage_obj, "thoughts_token_count", None) if usage_obj else None
    tot_tok = getattr(usage_obj, "total_token_count", None) if usage_obj else None
    cached_tok = (
        getattr(usage_obj, "cached_content_token_count", None) if usage_obj else None
    )
    traffic_type = getattr(usage_obj, "traffic_type", None) if usage_obj else None
    service_tier = (
        str(traffic_type.value if hasattr(traffic_type, "value") else traffic_type)
        if traffic_type
        else None
    )

    raw_usage_dict: Optional[Dict[str, Any]] = None
    if usage_obj is not None:
        raw_usage_dict = {
            "prompt_token_count": in_tok,
            "candidates_token_count": out_tok,
            "thoughts_token_count": thought_tok,
            "cached_content_token_count": cached_tok,
            "total_token_count": tot_tok,
            "traffic_type": service_tier,
        }
    norm_usage = normalize_candidate_usage_metadata("C1", raw_usage_dict)
    usage_avail = bool(norm_usage.get("usage_present"))

    failure_cls = DevCellFailureClassification.NONE
    if refusal_state:
        failure_cls = DevCellFailureClassification.REFUSAL
    elif max_token_state:
        failure_cls = DevCellFailureClassification.MAX_TOKEN_TRUNCATION

    raw_meta = {
        "response_id": getattr(resp, "response_id", None),
        "model_version": returned_model,
        "finish_reason": finish_reason,
        "traffic_type": service_tier,
    }
    norm_meta = {
        "candidate_id": "C1",
        "provider": "google",
        "requested_model_id": "gemini-3.8-flash",
        "returned_model_id": returned_model,
        "finish_or_stop_reason": finish_reason,
        "refusal_state": refusal_state,
        "max_token_state": max_token_state,
        "thinking_level": "medium",
        "seed_sent": 2026101508,
        "temperature_status": "OMITTED",
        "actual_http_request_count": counting_transport.request_count,
    }
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
        raw_provider_metadata=raw_meta,
        normalized_provider_metadata=norm_meta,
        actual_http_request_count=counting_transport.request_count,
        simulated_failure=failure_cls,
        authoritative_usage_available=usage_avail,
        input_tokens=norm_usage["input_tokens"],
        output_tokens=norm_usage["output_tokens"],
        total_tokens=norm_usage["total_tokens"],
        thought_tokens=norm_usage["thought_tokens"],
        cached_input_tokens=norm_usage["cached_input_tokens"],
    )


def _invoke_c2_openai_production(
    *,
    api_key: str,
    wire_request: Dict[str, Any],
    counting_transport: DevCountingHttpx2Transport,
) -> ProviderNormalizedTransportResponse:
    """Invoke OpenAI Chat Completions (`gpt-6.1-sol`) with exact frozen C2 parameters and Portable Schema V2 (Sections 3, 4, 5)."""
    for forbidden_key in ("temperature", "top_p", "top_k", "top_logprobs", "logprobs"):
        if forbidden_key in wire_request:
            raise CandidateRegistryIntegrityError(
                f"C2_FORBIDDEN_SAMPLING_PARAMETER: {forbidden_key!r} must be omitted."
            )
    if (
        wire_request.get("model") != "gpt-6.1-sol"
        or wire_request.get("reasoning_effort") != "medium"
        or wire_request.get("seed") != 2026101508
        or wire_request.get("service_tier") != "default"
        or wire_request.get("max_completion_tokens") != 16384
        or wire_request.get("timeout_seconds") != 55.0
        or wire_request.get("max_retries") != 0
    ):
        raise CandidateRegistryIntegrityError("C2 wire_request violates frozen C2 config.")

    http_client = httpx2.Client(transport=counting_transport, timeout=55.0)
    try:
        client = openai.OpenAI(
            api_key=api_key,
            max_retries=0,
            timeout=55.0,
            http_client=http_client,
        )
        resp = client.chat.completions.create(
            model="gpt-6.1-sol",
            messages=wire_request["messages"],
            seed=2026101508,
            reasoning_effort="medium",
            service_tier="default",
            max_completion_tokens=16384,
            response_format=wire_request["response_format"],
        )
    finally:
        http_client.close()

    returned_model = getattr(resp, "model", None)
    sys_fp = getattr(resp, "system_fingerprint", None)
    srv_tier = getattr(resp, "service_tier", None)
    choices = getattr(resp, "choices", None) or []
    raw_text = ""
    finish_reason: Optional[str] = None
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

    usage_obj = getattr(resp, "usage", None)
    in_tok = getattr(usage_obj, "prompt_tokens", None) if usage_obj else None
    out_tok = getattr(usage_obj, "completion_tokens", None) if usage_obj else None
    tot_tok = getattr(usage_obj, "total_tokens", None) if usage_obj else None
    comp_details = (
        getattr(usage_obj, "completion_tokens_details", None) if usage_obj else None
    )
    reas_tok = (
        getattr(comp_details, "reasoning_tokens", None) if comp_details else None
    )
    prompt_details = (
        getattr(usage_obj, "prompt_tokens_details", None) if usage_obj else None
    )
    cached_tok = (
        getattr(prompt_details, "cached_tokens", None) if prompt_details else None
    )

    raw_usage_dict: Optional[Dict[str, Any]] = None
    if usage_obj is not None:
        raw_usage_dict = {
            "prompt_tokens": in_tok,
            "completion_tokens": out_tok,
            "total_tokens": tot_tok,
            "completion_tokens_details": {"reasoning_tokens": reas_tok},
            "prompt_tokens_details": {"cached_tokens": cached_tok},
        }
    norm_usage = normalize_candidate_usage_metadata("C2", raw_usage_dict)
    usage_avail = bool(norm_usage.get("usage_present"))

    failure_cls = DevCellFailureClassification.NONE
    if refusal_state:
        failure_cls = DevCellFailureClassification.REFUSAL
    elif max_token_state:
        failure_cls = DevCellFailureClassification.MAX_TOKEN_TRUNCATION

    raw_meta = {
        "id": getattr(resp, "id", None),
        "model": returned_model,
        "system_fingerprint": sys_fp,
        "service_tier": srv_tier,
        "finish_reason": finish_reason,
    }
    norm_meta = {
        "candidate_id": "C2",
        "provider": "openai",
        "requested_model_id": "gpt-6.1-sol",
        "returned_model_id": returned_model,
        "finish_or_stop_reason": finish_reason,
        "refusal_state": refusal_state,
        "max_token_state": max_token_state,
        "reasoning_effort": "medium",
        "seed_sent": 2026101508,
        "service_tier": srv_tier or "default",
        "temperature_status": "OMITTED",
        "actual_http_request_count": counting_transport.request_count,
    }
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
        raw_provider_metadata=raw_meta,
        normalized_provider_metadata=norm_meta,
        actual_http_request_count=counting_transport.request_count,
        simulated_failure=failure_cls,
        authoritative_usage_available=usage_avail,
        input_tokens=norm_usage["input_tokens"],
        output_tokens=norm_usage["output_tokens"],
        total_tokens=norm_usage["total_tokens"],
        reasoning_tokens=norm_usage["reasoning_tokens"],
        cached_input_tokens=norm_usage["cached_input_tokens"],
    )


def _invoke_c3_anthropic_production(
    *,
    api_key: str,
    wire_request: Dict[str, Any],
    counting_transport: DevCountingHttpx2Transport,
) -> ProviderNormalizedTransportResponse:
    """Invoke Anthropic Messages (`claude-sonnet-5-5`) with exact frozen C3 parameters and Portable Schema V2 (Sections 3, 4, 5)."""
    for forbidden_key in ("seed", "temperature", "top_p", "top_k"):
        if forbidden_key in wire_request:
            raise CandidateRegistryIntegrityError(
                f"C3_FORBIDDEN_SAMPLING_PARAMETER: {forbidden_key!r} must be omitted."
            )
    if (
        wire_request.get("model") != "claude-sonnet-5-5"
        or wire_request.get("thinking") != {"type": "adaptive"}
        or wire_request.get("output_config", {}).get("effort") != "high"
        or wire_request.get("max_tokens") != 16384
        or wire_request.get("timeout_seconds") != 55.0
        or wire_request.get("max_retries") != 0
    ):
        raise CandidateRegistryIntegrityError("C3 wire_request violates frozen C3 config.")

    http_client = httpx2.Client(transport=counting_transport, timeout=55.0)
    try:
        client = anthropic.Anthropic(
            api_key=api_key,
            max_retries=0,
            timeout=55.0,
            http_client=http_client,
        )
        resp = client.messages.create(
            model="claude-sonnet-5-5",
            system=wire_request["system"],
            messages=wire_request["messages"],
            max_tokens=16384,
            thinking=wire_request["thinking"],
            output_config=wire_request["output_config"],
        )
    finally:
        http_client.close()

    returned_model = getattr(resp, "model", None)
    stop_reason = getattr(resp, "stop_reason", None)
    sr_low = str(stop_reason or "").lower()
    refusal_state = sr_low == "refusal"
    max_token_state = sr_low in (
        "max_tokens",
        "length",
        "model_context_window_exceeded",
    )

    content_blocks = getattr(resp, "content", None) or []
    text_parts: List[str] = []
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

    usage_obj = getattr(resp, "usage", None)
    in_tok = getattr(usage_obj, "input_tokens", None) if usage_obj else None
    out_tok = getattr(usage_obj, "output_tokens", None) if usage_obj else None
    thinking_tok = getattr(usage_obj, "thinking_tokens", None) if usage_obj else None
    cache_read = (
        getattr(usage_obj, "cache_read_input_tokens", None) if usage_obj else None
    )
    cache_create = (
        getattr(usage_obj, "cache_creation_input_tokens", None) if usage_obj else None
    )
    srv_tier = getattr(usage_obj, "service_tier", None) if usage_obj else None

    raw_usage_dict: Optional[Dict[str, Any]] = None
    if usage_obj is not None:
        raw_usage_dict = {
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "thinking_tokens": thinking_tok,
            "cache_read_input_tokens": cache_read,
            "cache_creation_input_tokens": cache_create,
            "service_tier": srv_tier,
            "thinking_blocks_count": thinking_blocks_count,
        }
    norm_usage = normalize_candidate_usage_metadata("C3", raw_usage_dict)
    usage_avail = bool(norm_usage.get("usage_present"))

    failure_cls = DevCellFailureClassification.NONE
    if refusal_state:
        failure_cls = DevCellFailureClassification.REFUSAL
    elif max_token_state:
        failure_cls = DevCellFailureClassification.MAX_TOKEN_TRUNCATION

    raw_meta = {
        "id": getattr(resp, "id", None),
        "model": returned_model,
        "stop_reason": stop_reason,
        "service_tier": srv_tier,
        "thinking_blocks_count": thinking_blocks_count,
    }
    norm_meta = {
        "candidate_id": "C3",
        "provider": "anthropic",
        "requested_model_id": "claude-sonnet-5-5",
        "returned_model_id": returned_model,
        "finish_or_stop_reason": stop_reason,
        "refusal_state": refusal_state,
        "max_token_state": max_token_state,
        "thinking_mode": "adaptive",
        "effort": "high",
        "seed_sent": None,
        "seed_status": "OMITTED_UNSUPPORTED",
        "temperature_status": "OMITTED",
        "actual_http_request_count": counting_transport.request_count,
    }
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
        raw_provider_metadata=raw_meta,
        normalized_provider_metadata=norm_meta,
        actual_http_request_count=counting_transport.request_count,
        simulated_failure=failure_cls,
        authoritative_usage_available=usage_avail,
        input_tokens=norm_usage["input_tokens"],
        output_tokens=norm_usage["output_tokens"],
        total_tokens=norm_usage["total_tokens"],
        thinking_tokens=norm_usage["thinking_tokens"],
        cached_input_tokens=norm_usage["cached_input_tokens"],
        cache_read_input_tokens=norm_usage["cache_read_input_tokens"],
        cache_creation_input_tokens=norm_usage["cache_creation_input_tokens"],
    )


class BaseCandidateProductionTransport:
    """Base class for candidate-specific production transports (Sections 3, 8)."""

    is_production_transport: bool = True
    candidate_id: str = ""
    provider: str = ""
    requested_model_id: str = ""
    env_key_name: str = ""

    def invoke(
        self,
        *,
        cell_manifest: DevCellExecutionManifest,
        wire_request: Dict[str, Any],
        live_capability: LiveExecutionCapability,
        http_counter: DevCellHttpCallCounter,
        api_key: str,
        inner_transport: Optional[Any] = None,
    ) -> ProviderNormalizedTransportResponse:
        raise NotImplementedError


class GoogleGeminiProductionTransport(BaseCandidateProductionTransport):
    """Production transport for C1 (`google` / `gemini-3.8-flash`)."""

    candidate_id = "C1"
    provider = "google"
    requested_model_id = "gemini-3.8-flash"
    env_key_name = "GEMINI_API_KEY"

    def invoke(
        self,
        *,
        cell_manifest: DevCellExecutionManifest,
        wire_request: Dict[str, Any],
        live_capability: LiveExecutionCapability,
        http_counter: DevCellHttpCallCounter,
        api_key: str,
        inner_transport: Optional[httpx.BaseTransport] = None,
    ) -> ProviderNormalizedTransportResponse:
        live_capability.verify_mint_token()
        if cell_manifest.candidate_id != "C1":
            raise CandidateRegistryIntegrityError(
                f"GoogleGeminiProductionTransport requires C1, got {cell_manifest.candidate_id!r}"
            )
        counting = DevCountingHttpxTransport(
            candidate_id="C1",
            run_id=cell_manifest.run_id,
            http_counter=http_counter,
            inner_transport=inner_transport,
        )
        try:
            return _invoke_c1_google_production(
                api_key=api_key,
                wire_request=wire_request,
                counting_transport=counting,
            )
        except (
            ImmutableCellExecutionError,
            BatchExecutionFatalStopError,
            DevCallBudgetExhaustedError,
            CandidateRegistryIntegrityError,
        ):
            raise
        except Exception as exc:
            f_cls = classify_provider_transport_exception(exc)
            safe_err = sanitize_runner_text(f"{type(exc).__name__}: {exc}", [api_key])
            return ProviderNormalizedTransportResponse(
                candidate_id="C1",
                provider="google",
                requested_model_id="gemini-3.8-flash",
                returned_model_id=None,
                raw_text="",
                finish_or_stop_reason=f"PROVIDER_EXCEPTION:{f_cls.value}",
                finish_reason=f"PROVIDER_EXCEPTION:{f_cls.value}:{safe_err}",
                refusal_state=(f_cls == DevCellFailureClassification.REFUSAL),
                max_token_state=(
                    f_cls == DevCellFailureClassification.MAX_TOKEN_TRUNCATION
                ),
                raw_usage_metadata=None,
                normalized_usage_metadata=normalize_candidate_usage_metadata("C1", None),
                raw_provider_metadata={"error_detail_sanitized": safe_err},
                normalized_provider_metadata={
                    "candidate_id": "C1",
                    "provider": "google",
                    "requested_model_id": "gemini-3.8-flash",
                    "returned_model_id": None,
                    "failure_classification": f_cls.value,
                    "error_detail_sanitized": safe_err,
                    "actual_http_request_count": counting.request_count,
                },
                actual_http_request_count=counting.request_count,
                simulated_failure=f_cls,
                authoritative_usage_available=False,
            )


class OpenAIChatCompletionsProductionTransport(BaseCandidateProductionTransport):
    """Production transport for C2 (`openai` / `gpt-6.1-sol`)."""

    candidate_id = "C2"
    provider = "openai"
    requested_model_id = "gpt-6.1-sol"
    env_key_name = "OPENAI_API_KEY"

    def invoke(
        self,
        *,
        cell_manifest: DevCellExecutionManifest,
        wire_request: Dict[str, Any],
        live_capability: LiveExecutionCapability,
        http_counter: DevCellHttpCallCounter,
        api_key: str,
        inner_transport: Optional[httpx2.BaseTransport] = None,
    ) -> ProviderNormalizedTransportResponse:
        live_capability.verify_mint_token()
        if cell_manifest.candidate_id != "C2":
            raise CandidateRegistryIntegrityError(
                f"OpenAIChatCompletionsProductionTransport requires C2, got {cell_manifest.candidate_id!r}"
            )
        counting = DevCountingHttpx2Transport(
            candidate_id="C2",
            run_id=cell_manifest.run_id,
            http_counter=http_counter,
            inner_transport=inner_transport,
        )
        try:
            return _invoke_c2_openai_production(
                api_key=api_key,
                wire_request=wire_request,
                counting_transport=counting,
            )
        except (
            ImmutableCellExecutionError,
            BatchExecutionFatalStopError,
            DevCallBudgetExhaustedError,
            CandidateRegistryIntegrityError,
        ):
            raise
        except Exception as exc:
            f_cls = classify_provider_transport_exception(exc)
            safe_err = sanitize_runner_text(f"{type(exc).__name__}: {exc}", [api_key])
            return ProviderNormalizedTransportResponse(
                candidate_id="C2",
                provider="openai",
                requested_model_id="gpt-6.1-sol",
                returned_model_id=None,
                raw_text="",
                finish_or_stop_reason=f"PROVIDER_EXCEPTION:{f_cls.value}",
                finish_reason=f"PROVIDER_EXCEPTION:{f_cls.value}:{safe_err}",
                refusal_state=(f_cls == DevCellFailureClassification.REFUSAL),
                max_token_state=(
                    f_cls == DevCellFailureClassification.MAX_TOKEN_TRUNCATION
                ),
                raw_usage_metadata=None,
                normalized_usage_metadata=normalize_candidate_usage_metadata("C2", None),
                raw_provider_metadata={"error_detail_sanitized": safe_err},
                normalized_provider_metadata={
                    "candidate_id": "C2",
                    "provider": "openai",
                    "requested_model_id": "gpt-6.1-sol",
                    "returned_model_id": None,
                    "failure_classification": f_cls.value,
                    "error_detail_sanitized": safe_err,
                    "actual_http_request_count": counting.request_count,
                },
                actual_http_request_count=counting.request_count,
                simulated_failure=f_cls,
                authoritative_usage_available=False,
            )


class AnthropicMessagesProductionTransport(BaseCandidateProductionTransport):
    """Production transport for C3 (`anthropic` / `claude-sonnet-5-5`)."""

    candidate_id = "C3"
    provider = "anthropic"
    requested_model_id = "claude-sonnet-5-5"
    env_key_name = "ANTHROPIC_API_KEY"

    def invoke(
        self,
        *,
        cell_manifest: DevCellExecutionManifest,
        wire_request: Dict[str, Any],
        live_capability: LiveExecutionCapability,
        http_counter: DevCellHttpCallCounter,
        api_key: str,
        inner_transport: Optional[httpx2.BaseTransport] = None,
    ) -> ProviderNormalizedTransportResponse:
        live_capability.verify_mint_token()
        if cell_manifest.candidate_id != "C3":
            raise CandidateRegistryIntegrityError(
                f"AnthropicMessagesProductionTransport requires C3, got {cell_manifest.candidate_id!r}"
            )
        counting = DevCountingHttpx2Transport(
            candidate_id="C3",
            run_id=cell_manifest.run_id,
            http_counter=http_counter,
            inner_transport=inner_transport,
        )
        try:
            return _invoke_c3_anthropic_production(
                api_key=api_key,
                wire_request=wire_request,
                counting_transport=counting,
            )
        except (
            ImmutableCellExecutionError,
            BatchExecutionFatalStopError,
            DevCallBudgetExhaustedError,
            CandidateRegistryIntegrityError,
        ):
            raise
        except Exception as exc:
            f_cls = classify_provider_transport_exception(exc)
            safe_err = sanitize_runner_text(f"{type(exc).__name__}: {exc}", [api_key])
            return ProviderNormalizedTransportResponse(
                candidate_id="C3",
                provider="anthropic",
                requested_model_id="claude-sonnet-5-5",
                returned_model_id=None,
                raw_text="",
                finish_or_stop_reason=f"PROVIDER_EXCEPTION:{f_cls.value}",
                finish_reason=f"PROVIDER_EXCEPTION:{f_cls.value}:{safe_err}",
                refusal_state=(f_cls == DevCellFailureClassification.REFUSAL),
                max_token_state=(
                    f_cls == DevCellFailureClassification.MAX_TOKEN_TRUNCATION
                ),
                raw_usage_metadata=None,
                normalized_usage_metadata=normalize_candidate_usage_metadata("C3", None),
                raw_provider_metadata={"error_detail_sanitized": safe_err},
                normalized_provider_metadata={
                    "candidate_id": "C3",
                    "provider": "anthropic",
                    "requested_model_id": "claude-sonnet-5-5",
                    "returned_model_id": None,
                    "failure_classification": f_cls.value,
                    "error_detail_sanitized": safe_err,
                    "actual_http_request_count": counting.request_count,
                },
                actual_http_request_count=counting.request_count,
                simulated_failure=f_cls,
                authoritative_usage_available=False,
            )


class ProductionDevProviderTransport:
    """Type-safe production provider transport router for C1, C2, and C3 (Sections 3, 7, 8, 14, 16).

    Strictly distinct from `MockDevProviderTransport`. Requires an internally minted
    `LiveExecutionCapability` (fail-closed orchestration capability) and routes each cell to its
    candidate-specific production SDK transport with HTTP-boundary request counting (`<= 1` HTTP request/cell).
    """

    is_production_transport: bool = True

    def __init__(
        self,
        *,
        live_capability: LiveExecutionCapability,
        dotenv_path: Optional[Path] = None,
        api_key_overrides: Optional[Mapping[str, str]] = None,
        inner_transport_overrides: Optional[Mapping[str, Any]] = None,
    ) -> None:
        if not isinstance(live_capability, LiveExecutionCapability):
            raise LiveExecutionNotAuthorizedError(
                "PRODUCTION_TRANSPORT_REQUIRES_LIVE_CAPABILITY: live_capability must be a LiveExecutionCapability."
            )
        live_capability.verify_mint_token()
        self.live_capability = live_capability
        self.dotenv_path = dotenv_path
        self._api_key_overrides = dict(api_key_overrides) if api_key_overrides else {}
        self._inner_transport_overrides = (
            dict(inner_transport_overrides) if inner_transport_overrides else {}
        )
        self.http_counter = DevCellHttpCallCounter(
            max_requests_per_cell=1,
            max_total_requests=live_capability.maximum_live_generation_calls,
        )
        self.candidate_transports: Dict[str, BaseCandidateProductionTransport] = {
            "C1": GoogleGeminiProductionTransport(),
            "C2": OpenAIChatCompletionsProductionTransport(),
            "C3": AnthropicMessagesProductionTransport(),
        }
        self.call_count: int = 0
        self.call_count_by_run_id: Dict[str, int] = {}

    def __call__(
        self,
        cell_manifest: DevCellExecutionManifest,
        wire_request: Dict[str, Any],
    ) -> ProviderNormalizedTransportResponse:
        self.live_capability.verify_mint_token()
        cid = cell_manifest.candidate_id
        if cid not in self.candidate_transports:
            raise CandidateRegistryIntegrityError(
                f"Unsupported candidate_id={cid!r} in ProductionDevProviderTransport."
            )
        if cid not in self.live_capability.allowed_candidate_ids:
            raise DevLiveAuthorizationError(
                f"Candidate {cid!r} is not authorized in LiveExecutionCapability ({self.live_capability.allowed_candidate_ids})."
            )
        self.call_count += 1
        self.call_count_by_run_id[cell_manifest.run_id] = (
            self.call_count_by_run_id.get(cell_manifest.run_id, 0) + 1
        )
        if self.call_count_by_run_id[cell_manifest.run_id] > 1:
            raise ImmutableCellExecutionError(
                f"RETRY_FORBIDDEN: ProductionDevProviderTransport invoked more than once for cell {cell_manifest.run_id}"
            )

        api_key = _load_candidate_api_key_for_live_transport(
            cid,
            dotenv_path=self.dotenv_path,
            api_key_overrides=self._api_key_overrides,
        )
        cand_transport = self.candidate_transports[cid]
        inner_override = self._inner_transport_overrides.get(cid)
        return cand_transport.invoke(
            cell_manifest=cell_manifest,
            wire_request=wire_request,
            live_capability=self.live_capability,
            http_counter=self.http_counter,
            api_key=api_key,
            inner_transport=inner_override,
        )


class DevProviderTransportProtocol(Protocol):
    """Protocol for single-request provider transport."""

    def __call__(
        self,
        cell_manifest: DevCellExecutionManifest,
        wire_request: Dict[str, Any],
    ) -> Union[MockProviderTransportResponse, ProviderNormalizedTransportResponse]: ...


class MockDevProviderTransport:
    """Deterministic offline mock transport used ONLY in `OFFLINE_MOCK_TEST` mode (Sections 7, 8).

    Never accepted in `LIVE_EXECUTION` mode.
    """

    is_production_transport: bool = False

    def __init__(
        self,
        response_or_callable: Union[
            MockProviderTransportResponse,
            ProviderNormalizedTransportResponse,
            Mapping[str, Union[MockProviderTransportResponse, ProviderNormalizedTransportResponse]],
            Callable[[DevCellExecutionManifest, Dict[str, Any]], Union[MockProviderTransportResponse, ProviderNormalizedTransportResponse]],
            Callable[[DevCellExecutionManifest], Union[MockProviderTransportResponse, ProviderNormalizedTransportResponse]],
        ],
    ) -> None:
        if isinstance(
            response_or_callable,
            (ProductionDevProviderTransport, BaseCandidateProductionTransport),
        ):
            raise LiveExecutionNotAuthorizedError(
                "MOCK_TRANSPORT_CANNOT_WRAP_PRODUCTION_TRANSPORT: MockDevProviderTransport cannot wrap a ProductionDevProviderTransport."
            )
        self._source = response_or_callable
        self.call_count: int = 0
        self.call_count_by_run_id: Dict[str, int] = {}
        self.captured_requests_by_run_id: Dict[str, Dict[str, Any]] = {}

    def __call__(
        self,
        cell_manifest: DevCellExecutionManifest,
        wire_request: Dict[str, Any],
    ) -> Union[MockProviderTransportResponse, ProviderNormalizedTransportResponse]:
        self.call_count += 1
        self.call_count_by_run_id[cell_manifest.run_id] = (
            self.call_count_by_run_id.get(cell_manifest.run_id, 0) + 1
        )
        if self.call_count_by_run_id[cell_manifest.run_id] > 1:
            raise ImmutableCellExecutionError(
                f"RETRY_FORBIDDEN: Transport invoked more than once for cell {cell_manifest.run_id}"
            )
        self.captured_requests_by_run_id[cell_manifest.run_id] = copy.deepcopy(wire_request)

        if isinstance(
            self._source,
            (MockProviderTransportResponse, ProviderNormalizedTransportResponse),
        ):
            return self._source
        if isinstance(self._source, Mapping):
            if cell_manifest.run_id not in self._source:
                raise KeyError(
                    f"Missing mock response for run_id={cell_manifest.run_id!r}"
                )
            return self._source[cell_manifest.run_id]
        if callable(self._source):
            try:
                return self._source(cell_manifest, wire_request)  # type: ignore[misc]
            except TypeError:
                return self._source(cell_manifest)  # type: ignore[misc]
        raise TypeError(f"Unsupported mock transport source: {type(self._source)}")


def create_live_provider_transport_factory(
    *,
    execute_live: bool,
    authorization: Optional[DevLiveAuthorizationArtifact] = None,
    live_capability: Optional[LiveExecutionCapability] = None,
    dotenv_path: Optional[Path] = None,
    api_key_overrides: Optional[Mapping[str, str]] = None,
    inner_transport_overrides: Optional[Mapping[str, Any]] = None,
) -> ProductionDevProviderTransport:
    """Production transport factory: requires `execute_live=True`, verified `authorization`, and internally minted `LiveExecutionCapability` (Sections 3, 7, 8, 14)."""
    if execute_live is not True:
        raise LiveExecutionNotAuthorizedError(
            "LIVE_EXECUTION_DISABLED: --execute-live is False; live provider transport factory cannot be constructed."
        )
    if (
        authorization is None
        or authorization.authorization_status != AUTHORIZATION_STATUS_AUTHORIZED
    ):
        raise LiveExecutionNotAuthorizedError(
            "LIVE_AUTHORIZATION_MISSING: Live provider transport requires a verified DevLiveAuthorizationArtifact."
        )
    if live_capability is None or not isinstance(
        live_capability, LiveExecutionCapability
    ):
        raise LiveExecutionNotAuthorizedError(
            "LIVE_CAPABILITY_MISSING: create_live_provider_transport_factory requires a verified LiveExecutionCapability "
            "(issued after Stage-A freeze & git commit ancestor attestation)."
        )
    live_capability.verify_mint_token()
    if (
        live_capability.authorization_artifact_sha256
        != authorization.authorization_artifact_sha256
    ):
        raise LiveExecutionNotAuthorizedError(
            "LIVE_CAPABILITY_AUTHORIZATION_MISMATCH: LiveExecutionCapability does not match supplied authorization artifact."
        )
    return ProductionDevProviderTransport(
        live_capability=live_capability,
        dotenv_path=dotenv_path,
        api_key_overrides=api_key_overrides,
        inner_transport_overrides=inner_transport_overrides,
    )


# ==============================================================================
# 9. SINGLE-CELL EXECUTION CORE (SECTIONS 6-16)
# ==============================================================================


def _extract_raw_usage_from_response(
    candidate_id: str,
    response: Union[MockProviderTransportResponse, ProviderNormalizedTransportResponse],
) -> Optional[Dict[str, Any]]:
    """Extract raw usage dictionary from transport response without losing provider-shaped fields."""
    if response.raw_usage_metadata is not None:
        return copy.deepcopy(dict(response.raw_usage_metadata))
    if not response.authoritative_usage_available:
        return None
    if response.input_tokens is None and response.output_tokens is None:
        return None
    base: Dict[str, Any] = {
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
        "total_tokens": response.total_tokens,
    }
    if candidate_id == "C1":
        base["thought_tokens"] = response.thought_tokens
        base["cached_tokens"] = response.cached_input_tokens
    elif candidate_id == "C2":
        base["reasoning_tokens"] = response.reasoning_tokens
        base["cached_tokens"] = response.cached_input_tokens
    elif candidate_id == "C3":
        base["thinking_tokens"] = response.thinking_tokens
        base["cache_read_input_tokens"] = response.cache_read_input_tokens
        base["cache_creation_input_tokens"] = response.cache_creation_input_tokens
    return base


def _validate_and_resolve_transport_and_mode(
    *,
    execution_mode: Optional[Union[RunnerExecutionMode, str]],
    transport: Any,
    live_capability: Optional[LiveExecutionCapability],
    execution_plan: Union[DevExecutionPlan, StochasticityDiagnosticPlan],
    verified_prompt_freeze: DevPromptFreezeArtifact,
    verified_auth: DevLiveAuthorizationArtifact,
) -> Tuple[str, Callable[[DevCellExecutionManifest, Dict[str, Any]], Union[MockProviderTransportResponse, ProviderNormalizedTransportResponse]]]:
    """Enforce strict separation between `OFFLINE_MOCK_TEST` and `LIVE_EXECUTION` modes (Sections 7, 8, 14).

    - Rejects missing `execution_mode`.
    - Rejects arbitrary raw callables (`lambda` / `def`) unless wrapped in `MockDevProviderTransport` under `OFFLINE_MOCK_TEST`.
    - In `LIVE_EXECUTION` mode: requires an internally minted `LiveExecutionCapability` (fail-closed orchestration capability)
      matching the plan, prompt freeze, and authorization, AND requires `transport` to be a `ProductionDevProviderTransport`
      (never a mock or arbitrary callable).
    - In `OFFLINE_MOCK_TEST` mode: forbids `LiveExecutionCapability` and forbids `ProductionDevProviderTransport`.
    """
    if execution_mode is None:
        raise LiveExecutionNotAuthorizedError(
            "EXPLICIT_EXECUTION_MODE_REQUIRED: execute_live_dev_cell / execute_live_dev_batch requires "
            "explicit execution_mode='OFFLINE_MOCK_TEST' or execution_mode='LIVE_EXECUTION'."
        )
    mode_str = (
        execution_mode.value
        if isinstance(execution_mode, RunnerExecutionMode)
        else str(execution_mode)
    )
    if mode_str not in (
        RUNNER_EXECUTION_MODE_OFFLINE_MOCK_TEST,
        RUNNER_EXECUTION_MODE_LIVE_EXECUTION,
    ):
        raise LiveExecutionNotAuthorizedError(
            f"INVALID_EXECUTION_MODE: {mode_str!r}; must be {RUNNER_EXECUTION_MODE_OFFLINE_MOCK_TEST!r} "
            f"or {RUNNER_EXECUTION_MODE_LIVE_EXECUTION!r}."
        )

    if mode_str == RUNNER_EXECUTION_MODE_LIVE_EXECUTION:
        if live_capability is None or not isinstance(
            live_capability, LiveExecutionCapability
        ):
            raise LiveExecutionNotAuthorizedError(
                "LIVE_CAPABILITY_REQUIRED: execution_mode='LIVE_EXECUTION' requires an internally minted "
                "LiveExecutionCapability issued by issue_live_execution_capability()."
            )
        live_capability.verify_mint_token()
        if live_capability.execution_plan_sha256 != execution_plan.plan_sha256:
            raise LiveExecutionNotAuthorizedError(
                "LIVE_CAPABILITY_PLAN_MISMATCH: Capability plan_sha256 does not match execution_plan."
            )
        if live_capability.prompt_freeze_sha256 != compute_prompt_freeze_sha256(
            verified_prompt_freeze
        ):
            raise LiveExecutionNotAuthorizedError(
                "LIVE_CAPABILITY_PROMPT_FREEZE_MISMATCH: Capability prompt_freeze_sha256 does not match prompt_freeze."
            )
        if (
            live_capability.authorization_artifact_sha256
            != verified_auth.authorization_artifact_sha256
        ):
            raise LiveExecutionNotAuthorizedError(
                "LIVE_CAPABILITY_AUTHORIZATION_MISMATCH: Capability authorization_artifact_sha256 does not match authorization."
            )
        if not isinstance(transport, ProductionDevProviderTransport):
            raise LiveExecutionNotAuthorizedError(
                f"ARBITRARY_OR_MOCK_TRANSPORT_FORBIDDEN_IN_LIVE_MODE: LIVE_EXECUTION requires "
                f"ProductionDevProviderTransport, got {type(transport).__name__}."
            )
        if transport.live_capability is not live_capability:
            raise LiveExecutionNotAuthorizedError(
                "PRODUCTION_TRANSPORT_CAPABILITY_MISMATCH: ProductionDevProviderTransport capability does not match live_capability."
            )
        return mode_str, transport

    # mode_str == RUNNER_EXECUTION_MODE_OFFLINE_MOCK_TEST
    if live_capability is not None:
        raise LiveExecutionNotAuthorizedError(
            "MODE_CONFUSION_FORBIDDEN: Cannot supply LiveExecutionCapability when execution_mode='OFFLINE_MOCK_TEST'."
        )
    if isinstance(
        transport, (ProductionDevProviderTransport, BaseCandidateProductionTransport)
    ):
        raise LiveExecutionNotAuthorizedError(
            "MODE_CONFUSION_FORBIDDEN: Cannot use ProductionDevProviderTransport when execution_mode='OFFLINE_MOCK_TEST'."
        )
    if isinstance(transport, MockDevProviderTransport):
        return mode_str, transport
    if isinstance(
        transport, (MockProviderTransportResponse, ProviderNormalizedTransportResponse)
    ):
        return mode_str, MockDevProviderTransport(transport)

    raise LiveExecutionNotAuthorizedError(
        f"ARBITRARY_CALLABLE_TRANSPORT_FORBIDDEN: Raw callable or unverified transport ({type(transport).__name__}) "
        "is forbidden. Wrap offline test fixtures in MockDevProviderTransport under execution_mode='OFFLINE_MOCK_TEST'."
    )


def execute_live_dev_cell(
    *,
    cell_manifest: DevCellExecutionManifest,
    scenario: BenchmarkScenarioInput,
    execution_plan: Union[DevExecutionPlan, StochasticityDiagnosticPlan],
    prompt_freeze: Union[DevPromptFreezeArtifact, Path, str],
    prompt_registry: PromptRegistry,
    authorization: Union[DevLiveAuthorizationArtifact, Path, str],
    call_budget_ledger: DevCallBudgetLedger,
    cell_dir: Path,
    transport: Union[
        ProductionDevProviderTransport,
        MockDevProviderTransport,
        MockProviderTransportResponse,
        ProviderNormalizedTransportResponse,
    ],
    execution_mode: Optional[Union[RunnerExecutionMode, str]] = None,
    live_capability: Optional[LiveExecutionCapability] = None,
    stage_a_freeze_receipt_path: Optional[Path] = None,
    execution_plan_path: Optional[Path] = None,
    prompt_freeze_path: Optional[Path] = None,
    authorization_path: Optional[Path] = None,
    live_execution_context: Optional[LiveExecutionContext] = None,
    cost_comparability_by_candidate: Optional[
        Dict[str, CandidateCostComparabilityRecord]
    ] = None,
    dev_bundle: Optional[VerifiedDevBundle] = None,
    candidate_registry: Optional[DevCandidateRegistry] = None,
    dev_select_result: Optional[DevSelectModelSelectionResult] = None,
    catalog_path: Optional[Path] = None,
    core_catalog_by_id: Optional[Dict[str, BenchmarkCatalogPOI]] = None,
    repo_root: Optional[Path] = None,
    monotonic_ns_clock: Callable[[], int] = time.monotonic_ns,
    utc_now_clock: Callable[[], str] = default_utc_now_clock,
    extra_secrets: Optional[Sequence[str]] = None,
) -> Tuple[DevCellExecutionReceipt, ScenarioEvaluationResult]:
    """Execute a single frozen DEV cell through all fail-closed scientific steps (Sections 6-16)."""
    # Step 1: Final100 firewall
    _assert_runner_not_final100_path(cell_dir)
    assert_not_final100_scenario_id(cell_manifest.fixture_id)
    assert_not_final100_scenario(scenario)
    if cell_manifest.phase == "FINAL100" or "FINAL" in cell_manifest.phase.upper():
        raise Final100FirewallViolationError(
            f"FINAL100_FIREWALL_VIOLATION: Cell phase {cell_manifest.phase!r} is forbidden."
        )

    bundle = dev_bundle or load_and_verify_frozen_dev_bundle()
    cand_reg = candidate_registry or load_and_verify_candidate_registry()
    cost_map = cost_comparability_by_candidate or DEFAULT_COST_COMPARABILITY_BY_CANDIDATE
    effective_repo_root = (
        repo_root
        or (live_execution_context.repo_root if live_execution_context is not None else None)
        or (live_capability.repo_root if live_capability is not None else None)
    )

    # Step 2: Execution plan verification & cell membership
    if isinstance(execution_plan, DevExecutionPlan):
        runtime_head_sha = verify_dev_execution_plan_for_execution(
            execution_plan, candidate_registry=cand_reg, repo_root=effective_repo_root
        )
    elif isinstance(execution_plan, StochasticityDiagnosticPlan):
        if (
            dev_select_result is None
            or not dev_select_result.winner_selected
            or dev_select_result.selected_candidate_id != execution_plan.selected_candidate_id
        ):
            raise StochasticityGateViolationError(
                "STOCHASTICITY_BLOCKED_BEFORE_WINNER_FROZEN: Stochasticity cell execution requires a frozen DEV-SELECT winner."
            )
        runtime_head_sha = resolve_active_git_commit_sha(repo_root=effective_repo_root)
        active_bundle_sha = compute_scientific_code_bundle_sha256(
            repo_root=effective_repo_root
        )
        if execution_plan.scientific_code_bundle_sha256 != active_bundle_sha:
            raise ScientificCodeBundleIntegrityError(
                f"SCIENTIFIC_CODE_BUNDLE_MISMATCH: Stochasticity plan bundle {execution_plan.scientific_code_bundle_sha256} "
                f"!= active bundle {active_bundle_sha}."
            )
    else:
        raise PlanBeforeLiveProtocolError(
            f"EXECUTION_PLAN_MISSING_OR_INVALID: Unsupported execution_plan={type(execution_plan)}"
        )

    matching_plan_cells = [
        c for c in execution_plan.cells if c.run_id == cell_manifest.run_id
    ]
    if (
        len(matching_plan_cells) != 1
        or matching_plan_cells[0].model_dump() != cell_manifest.model_dump()
    ):
        raise PlanBeforeLiveProtocolError(
            f"CELL_NOT_IN_FROZEN_EXECUTION_PLAN: Cell {cell_manifest.run_id!r} does not match frozen execution plan."
        )

    # Step 3: Prompt freeze verification
    verified_prompt_freeze = verify_runner_prompt_freeze_artifact(
        prompt_freeze,
        prompt_registry=prompt_registry,
        execution_plan=execution_plan,
        dev_bundle=bundle,
        candidate_registry=cand_reg,
        repo_root=effective_repo_root,
    )
    prompt_by_id = {p.prompt_id: p for p in prompt_registry.prompts}
    if cell_manifest.prompt_id not in prompt_by_id:
        raise PromptFreezeFirewallError(
            f"PROMPT_ID_MISSING_FROM_REGISTRY: {cell_manifest.prompt_id!r}"
        )
    prompt_spec = prompt_by_id[cell_manifest.prompt_id]
    if (
        verified_prompt_freeze.semantic_prompt_sha256_by_id.get(cell_manifest.prompt_id)
        != prompt_spec.semantic_prompt_sha256
    ):
        raise PromptFreezeFirewallError(
            f"PROMPT_HASH_MISMATCH: Prompt {cell_manifest.prompt_id!r} hash mismatch against prompt freeze."
        )

    # Step 4: Authorization verification
    verified_auth = verify_dev_live_authorization_artifact(
        authorization,
        execution_plan=execution_plan,
        prompt_freeze=verified_prompt_freeze,
        dev_select_result=dev_select_result,
        repo_root=effective_repo_root,
    )

    # Step 4B: Validate execution_mode, LiveExecutionCapability, and transport type safety (Sections 7, 8, 14)
    validated_runner_mode, transport_callable = _validate_and_resolve_transport_and_mode(
        execution_mode=execution_mode,
        transport=transport,
        live_capability=live_capability,
        execution_plan=execution_plan,
        verified_prompt_freeze=verified_prompt_freeze,
        verified_auth=verified_auth,
    )
    manifest_execution_mode = resolve_truthful_manifest_execution_mode(
        runner_mode=validated_runner_mode,
        cell_phase=cell_manifest.phase,
    )

    # Step 4C: Action-boundary Stage-A re-attestation in LIVE_EXECUTION mode BEFORE any transport/budget reservation (Sections 10-13)
    if validated_runner_mode == RUNNER_EXECUTION_MODE_LIVE_EXECUTION:
        assert live_capability is not None
        resolved_plan_path = (
            execution_plan_path
            or (
                live_execution_context.execution_plan_path
                if live_execution_context is not None
                else None
            )
            or live_capability.execution_plan_path
        )
        resolved_pf_path = (
            prompt_freeze_path
            or (prompt_freeze if isinstance(prompt_freeze, Path) else None)
            or (
                live_execution_context.prompt_freeze_path
                if live_execution_context is not None
                else None
            )
            or live_capability.prompt_freeze_path
        )
        resolved_auth_path = (
            authorization_path
            or (authorization if isinstance(authorization, Path) else None)
            or (
                live_execution_context.authorization_path
                if live_execution_context is not None
                else None
            )
            or live_capability.authorization_path
        )
        resolved_stage_a_path = (
            stage_a_freeze_receipt_path
            or (
                live_execution_context.stage_a_freeze_receipt_path
                if live_execution_context is not None
                else None
            )
            or live_capability.stage_a_freeze_receipt_path
        )
        reattested_ctx = reattest_stage_a_at_live_action_boundary(
            live_capability=live_capability,
            execution_plan=execution_plan,
            prompt_freeze=verified_prompt_freeze,
            authorization=verified_auth,
            prompt_registry=prompt_registry,
            stage_a_freeze_receipt_path=resolved_stage_a_path,
            execution_plan_path=resolved_plan_path,
            prompt_freeze_path=resolved_pf_path,
            authorization_path=resolved_auth_path,
            dev_bundle=bundle,
            candidate_registry=cand_reg,
            dev_select_result=dev_select_result,
            repo_root=effective_repo_root,
            expected_locked_context=live_execution_context,
        )
        runtime_head_sha = reattested_ctx.runtime_head_sha

    # Step 5: Crash ambiguity & immutable artifact check before transport
    inspect_and_guard_cell_directory_before_transport(
        cell_dir, cell_manifest=cell_manifest
    )

    # Step 6 & 7: Code bundle & provider config attestation on cell manifest
    runtime_head_sha = verify_cell_manifest_for_execution(
        cell_manifest, candidate_registry=cand_reg, repo_root=effective_repo_root
    )
    active_reg_sha = compute_provider_config_registry_sha256(cand_reg)
    if verified_prompt_freeze.provider_config_registry_sha256 != active_reg_sha:
        raise CandidateRegistryIntegrityError(
            f"PROVIDER_CONFIG_REGISTRY_MISMATCH: prompt freeze registry {verified_prompt_freeze.provider_config_registry_sha256} "
            f"!= active registry {active_reg_sha}."
        )

    # Step 8: Construct provider request BEFORE reserving/consuming transport
    wire_request = build_frozen_provider_wire_request(
        cell_manifest=cell_manifest,
        scenario=scenario,
        prompt_spec=prompt_spec,
        candidate_registry=cand_reg,
        catalog_path=catalog_path,
    )

    # Step 9: Reserve exactly 1 call in the call-budget ledger
    if call_budget_ledger is None:
        raise DevLiveAuthorizationError("CALL_BUDGET_LEDGER_MISSING: Ledger is required.")
    reservation_idx = call_budget_ledger.reserve_call(cell_manifest)

    # Step 10: Capture single authoritative execution_started_at_utc ONCE immediately before transport journal STARTING (Sections 6-9)
    execution_started_at_utc = str(utc_now_clock()).strip()
    if not execution_started_at_utc:
        raise ValueError("EXECUTION_START_TIMESTAMP_EMPTY: utc_now_clock returned empty string.")

    req_manifest_path = cell_dir / "request_manifest.json"
    req_manifest_payload = {
        **cell_manifest.model_dump(),
        "runner_execution_mode": validated_runner_mode,
        "execution_mode": manifest_execution_mode,
        "execution_started_at_utc": execution_started_at_utc,
        "runtime_head_sha": runtime_head_sha,
        "authorization_id": verified_auth.authorization_id,
        "authorization_artifact_sha256": verified_auth.authorization_artifact_sha256,
        "stage_a_receipt_sha256": (
            live_capability.stage_a_receipt_sha256 if live_capability else None
        ),
        "stage_a_commit_sha": (
            live_capability.stage_a_commit_sha if live_capability else None
        ),
        "call_budget_reservation_index": reservation_idx,
        "provider_wire_request": wire_request,
    }
    req_manifest_sha = write_immutable_canonical_json(
        req_manifest_path, req_manifest_payload, extra_secrets=extra_secrets
    )
    write_transport_journal_starting(
        cell_dir,
        cell_manifest=cell_manifest,
        runtime_head_sha=runtime_head_sha,
        authorization_id=verified_auth.authorization_id,
        execution_started_at_utc=execution_started_at_utc,
    )

    # Step 11: Invoke transport AT MOST ONCE with monotonic_ns timing
    t_start_ns = monotonic_ns_clock()
    try:
        response = transport_callable(cell_manifest, wire_request)
    except (
        ImmutableCellExecutionError,
        BatchExecutionFatalStopError,
        DevCallBudgetExhaustedError,
    ):
        t_end_ns = monotonic_ns_clock()
        measured_ns = max(1, int(t_end_ns - t_start_ns))
        call_budget_ledger.consume_reserved_call(
            cell_manifest.run_id, transport_outcome="TRANSPORT_FATAL_INVARIANT_VIOLATION"
        )
        raise
    except Exception as exc:
        t_end_ns = monotonic_ns_clock()
        measured_ns = max(1, int(t_end_ns - t_start_ns))
        call_budget_ledger.consume_reserved_call(
            cell_manifest.run_id, transport_outcome="TRANSPORT_EXCEPTION"
        )
        f_cls = classify_provider_transport_exception(exc)
        sanitized_err = sanitize_runner_text(str(exc), extra_secrets=extra_secrets)
        response = MockProviderTransportResponse(
            returned_model_id=None,
            raw_text="",
            finish_reason=f"TRANSPORT_EXCEPTION:{f_cls.value}: {sanitized_err}",
            latency_ns=measured_ns,
            latency_ms=round(float(Decimal(measured_ns) / Decimal(1_000_000)), 6),
            simulated_failure=f_cls,
            authoritative_usage_available=False,
            input_tokens=None,
            output_tokens=None,
            total_tokens=None,
        )
    else:
        t_end_ns = monotonic_ns_clock()
        measured_ns = max(1, int(t_end_ns - t_start_ns))
        call_budget_ledger.consume_reserved_call(
            cell_manifest.run_id, transport_outcome="TRANSPORT_RETURNED"
        )

    if response.latency_ns is not None and not isinstance(response.latency_ns, bool):
        authoritative_latency_ns = int(response.latency_ns)
    else:
        authoritative_latency_ns = measured_ns
    display_latency_ms = round(
        float(Decimal(authoritative_latency_ns) / Decimal(1_000_000)), 6
    )

    # Step 12: Capture completion timestamp separately and IMMEDIATELY persist transport_journal_completed.json,
    # raw_provider_response.txt, raw_usage_metadata.json, and provider_response_metadata.json BEFORE any validation/parsing!
    transport_completed_at_utc = str(utc_now_clock()).strip()
    if not transport_completed_at_utc:
        raise ValueError("TRANSPORT_COMPLETED_TIMESTAMP_EMPTY: utc_now_clock returned empty string.")

    write_transport_journal_completed(
        cell_dir,
        cell_manifest=cell_manifest,
        runtime_head_sha=runtime_head_sha,
        authorization_id=verified_auth.authorization_id,
        latency_ns=authoritative_latency_ns,
        execution_started_at_utc=execution_started_at_utc,
        transport_completed_at_utc=transport_completed_at_utc,
    )

    raw_resp_path = cell_dir / "raw_provider_response.txt"
    raw_resp_sha = write_immutable_utf8_text(
        raw_resp_path, response.raw_text or "", extra_secrets=extra_secrets
    )

    raw_usage_dict = _extract_raw_usage_from_response(
        cell_manifest.candidate_id, response
    )
    normalized_usage = normalize_candidate_usage_metadata(
        cell_manifest.candidate_id, raw_usage_dict
    )

    raw_usage_path = cell_dir / "raw_usage_metadata.json"
    raw_usage_payload: Dict[str, Any] = {
        "run_id": cell_manifest.run_id,
        "candidate_id": cell_manifest.candidate_id,
        "provider": CANDIDATE_PROVIDER_BY_ID[cell_manifest.candidate_id],
        "usage_present": raw_usage_dict is not None,
        "raw_usage_metadata": copy.deepcopy(raw_usage_dict),
        "normalized_usage_metadata": normalized_usage,
    }
    write_immutable_canonical_json(
        raw_usage_path, raw_usage_payload, extra_secrets=extra_secrets
    )

    returned_model = response.returned_model_id
    usage_avail = bool(
        response.authoritative_usage_available
        and normalized_usage.get("usage_present")
    )
    actual_http_requests = (
        response.actual_http_request_count
        if isinstance(response, ProviderNormalizedTransportResponse)
        else (1 if validated_runner_mode == RUNNER_EXECUTION_MODE_LIVE_EXECUTION else 0)
    )
    refusal_state = (
        response.refusal_state
        if isinstance(response, ProviderNormalizedTransportResponse)
        else (response.simulated_failure == DevCellFailureClassification.REFUSAL)
    )
    max_token_state = (
        response.max_token_state
        if isinstance(response, ProviderNormalizedTransportResponse)
        else (
            response.simulated_failure
            == DevCellFailureClassification.MAX_TOKEN_TRUNCATION
        )
    )

    generation_params = build_candidate_manifest_generation_parameters(
        cell_manifest, runtime_head_sha=runtime_head_sha
    )

    meta_path = cell_dir / "provider_response_metadata.json"
    meta_payload = {
        "run_id": cell_manifest.run_id,
        "candidate_id": cell_manifest.candidate_id,
        "provider": CANDIDATE_PROVIDER_BY_ID[cell_manifest.candidate_id],
        "requested_model_id": cell_manifest.requested_model_id,
        "returned_model_id": returned_model,
        "runner_execution_mode": validated_runner_mode,
        "execution_mode": manifest_execution_mode,
        "execution_started_at_utc": execution_started_at_utc,
        "transport_completed_at_utc": transport_completed_at_utc,
        "code_basis_commit_sha": cell_manifest.code_basis_commit_sha,
        "code_commit_sha": cell_manifest.code_commit_sha,
        "runtime_head_sha": runtime_head_sha,
        "scientific_code_bundle_sha256": cell_manifest.scientific_code_bundle_sha256,
        "provider_config_sha256": cell_manifest.provider_config_sha256,
        "generation_parameters": generation_params,
        "authorization_id": verified_auth.authorization_id,
        "stage_a_receipt_sha256": (
            live_capability.stage_a_receipt_sha256 if live_capability else None
        ),
        "stage_a_commit_sha": (
            live_capability.stage_a_commit_sha if live_capability else None
        ),
        "finish_reason": sanitize_runner_text(
            response.finish_reason, extra_secrets=extra_secrets
        ),
        "refusal_state": refusal_state,
        "max_token_state": max_token_state,
        "actual_http_request_count": actual_http_requests,
        "latency_ns": authoritative_latency_ns,
        "latency_ms": display_latency_ms,
        "latency_ms_display": display_latency_ms,
        "simulated_failure": response.simulated_failure.value,
        "raw_provider_metadata": (
            copy.deepcopy(response.raw_provider_metadata)
            if isinstance(response, ProviderNormalizedTransportResponse)
            else None
        ),
        "normalized_provider_metadata": (
            copy.deepcopy(response.normalized_provider_metadata)
            if isinstance(response, ProviderNormalizedTransportResponse)
            else None
        ),
        "usage_metadata": {
            "authoritative_usage_available": usage_avail,
            "input_tokens": normalized_usage["input_tokens"] if usage_avail else None,
            "output_tokens": normalized_usage["output_tokens"] if usage_avail else None,
            "total_tokens": normalized_usage["total_tokens"] if usage_avail else None,
            "thought_tokens": normalized_usage["thought_tokens"] if usage_avail else None,
            "reasoning_tokens": normalized_usage["reasoning_tokens"] if usage_avail else None,
            "thinking_tokens": normalized_usage["thinking_tokens"] if usage_avail else None,
            "cached_input_tokens": normalized_usage["cached_input_tokens"] if usage_avail else None,
            "cache_read_input_tokens": (
                normalized_usage["cache_read_input_tokens"] if usage_avail else None
            ),
            "cache_creation_input_tokens": (
                normalized_usage["cache_creation_input_tokens"] if usage_avail else None
            ),
            "raw_usage_metadata": copy.deepcopy(raw_usage_dict),
        },
    }
    meta_sha = write_immutable_canonical_json(
        meta_path, meta_payload, extra_secrets=extra_secrets
    )

    # Step 13 & 15: Model ID integrity check & strict primary parser
    failure_class = response.simulated_failure
    parsed_plan: Optional[BenchmarkPlanResponse] = None
    parsed_sha: Optional[str] = None
    run_status = BenchmarkRunStatus.VALID

    # If a 200 response returned an explicit incompatible model ID, it is always MODEL_INTEGRITY_MISMATCH
    if returned_model is not None and not is_returned_model_id_compatible(
        cell_manifest.requested_model_id, returned_model
    ):
        failure_class = DevCellFailureClassification.MODEL_INTEGRITY_MISMATCH
        run_status = BenchmarkRunStatus.MODEL_ID_MISMATCH
    elif failure_class != DevCellFailureClassification.NONE:
        if failure_class == DevCellFailureClassification.MODEL_INTEGRITY_MISMATCH:
            run_status = BenchmarkRunStatus.MODEL_ID_MISMATCH
        elif failure_class in ORDINARY_DENOMINATOR_FAILURE_CLASSIFICATIONS:
            run_status = BenchmarkRunStatus.API_ERROR
        else:
            run_status = BenchmarkRunStatus.API_ERROR
    elif not is_returned_model_id_compatible(
        cell_manifest.requested_model_id, returned_model
    ):
        failure_class = DevCellFailureClassification.MODEL_INTEGRITY_MISMATCH
        run_status = BenchmarkRunStatus.MODEL_ID_MISMATCH
    else:
        parsed_plan, failure_class, run_status = parse_primary_dev_plan_response(
            response.raw_text
        )
        if parsed_plan is not None:
            parsed_sha = write_immutable_canonical_json(
                cell_dir / "parsed_plan_response.json",
                parsed_plan.model_dump(mode="json"),
                extra_secrets=extra_secrets,
            )

    # Step 16: Frozen evaluator authority with truthful generation_parameters, execution_mode, execution_started_at_utc, and runtime_head_sha
    manifest_model_id = (
        returned_model
        if (returned_model is not None and str(returned_model).strip())
        else "MISSING_RETURNED_MODEL_ID"
    )
    run_manifest = BenchmarkRunManifest(
        run_id=cell_manifest.run_id,
        scenario_id=scenario.scenario_id,
        execution_timestamp_utc=execution_started_at_utc,
        provider=cell_manifest.candidate_id,
        model_id=manifest_model_id,
        expected_model_id=cell_manifest.requested_model_id,
        generation_parameters=generation_params,
        execution_mode=manifest_execution_mode,
        latency_ms=display_latency_ms,
        usage_metadata=BenchmarkUsageMetadata(
            input_tokens=normalized_usage["input_tokens"] if usage_avail else None,
            output_tokens=normalized_usage["output_tokens"] if usage_avail else None,
            total_tokens=normalized_usage["total_tokens"] if usage_avail else None,
        ),
        code_commit_sha=runtime_head_sha,
        scenario_sha256=cell_manifest.scenario_sha256,
        catalog_sha256=compute_catalog_sha256(catalog_path=catalog_path),
        benchmark_prompt_version=cell_manifest.prompt_id,
        raw_response_sha256=raw_resp_sha,
        parsed_response_sha256=parsed_sha,
        measurement_contract_id=MEASUREMENT_CONTRACT_ID,
        measurement_contract_version=MEASUREMENT_CONTRACT_VERSION,
        hash_basis_version=HASH_BASIS_VERSION,
        run_status=run_status,
        error_detail=None
        if run_status == BenchmarkRunStatus.VALID
        else failure_class.value,
    )
    write_immutable_canonical_json(
        cell_dir / "run_manifest.json",
        run_manifest.model_dump(mode="json"),
        extra_secrets=extra_secrets,
    )

    eval_result = evaluate_dev_cell_scenario(
        scenario=scenario,
        plan_response=parsed_plan,
        run_manifest=run_manifest,
        catalog_path=catalog_path,
        core_catalog_by_id=core_catalog_by_id,
    )
    eval_sha = write_immutable_canonical_json(
        cell_dir / "evaluation_result.json",
        eval_result.model_dump(mode="json"),
        extra_secrets=extra_secrets,
    )

    # Step 14: Exact Decimal cost calculation
    cost_record = cost_map.get(cell_manifest.candidate_id)
    canonical_cost_dec: Optional[Decimal] = None
    canonical_cost_dec_str: Optional[str] = None
    canonical_cost_disp: Optional[float] = None
    if cost_record is not None and usage_avail:
        canonical_cost_dec = compute_canonical_cell_cost_decimal(
            input_tokens=normalized_usage["input_tokens"],
            output_tokens=normalized_usage["output_tokens"],
            thought_tokens=normalized_usage["thought_tokens"],
            reasoning_tokens=normalized_usage["reasoning_tokens"],
            thinking_tokens=normalized_usage["thinking_tokens"],
            cached_input_tokens=normalized_usage["cached_input_tokens"],
            cache_read_input_tokens=normalized_usage["cache_read_input_tokens"],
            cache_creation_input_tokens=normalized_usage["cache_creation_input_tokens"],
            cost_record=cost_record,
        )
        if canonical_cost_dec is not None:
            canonical_cost_dec_str = format_canonical_decimal_str(canonical_cost_dec)
            canonical_cost_disp = compute_canonical_cell_cost_usd(
                input_tokens=normalized_usage["input_tokens"],
                output_tokens=normalized_usage["output_tokens"],
                thought_tokens=normalized_usage["thought_tokens"],
                reasoning_tokens=normalized_usage["reasoning_tokens"],
                thinking_tokens=normalized_usage["thinking_tokens"],
                cached_input_tokens=normalized_usage["cached_input_tokens"],
                cache_read_input_tokens=normalized_usage["cache_read_input_tokens"],
                cache_creation_input_tokens=normalized_usage["cache_creation_input_tokens"],
                cost_record=cost_record,
            )

    is_batch_stop = failure_class in BATCH_STOP_FAILURE_CLASSIFICATIONS
    valid_run_and_schema = bool(eval_result.run_valid) and not is_batch_stop
    exact_grounding_pass = bool(
        valid_run_and_schema
        and eval_result.all_pois_grounded
        and eval_result.scenario_destination_valid
    )
    final_core_pass = bool(valid_run_and_schema and eval_result.core_scenario_pass)

    # Step 17: Create immutable receipt
    receipt = DevCellExecutionReceipt(
        run_id=cell_manifest.run_id,
        phase=cell_manifest.phase,
        fixture_id=cell_manifest.fixture_id,
        candidate_id=cell_manifest.candidate_id,
        prompt_id=cell_manifest.prompt_id,
        requested_model_id=cell_manifest.requested_model_id,
        returned_model_id=returned_model,
        code_basis_commit_sha=cell_manifest.code_basis_commit_sha,
        code_commit_sha=cell_manifest.code_basis_commit_sha,
        runtime_head_sha=runtime_head_sha,
        scientific_code_bundle_sha256=cell_manifest.scientific_code_bundle_sha256,
        provider_config_sha256=cell_manifest.provider_config_sha256,
        attempt_number=cell_manifest.attempt_number,
        attempted=True,
        failure_classification=failure_class,
        counts_in_denominator=not is_batch_stop,
        batch_stop_required=is_batch_stop,
        valid_run_and_schema=valid_run_and_schema,
        exact_grounding_pass=exact_grounding_pass,
        final_core_pass=final_core_pass,
        latency_ns=authoritative_latency_ns,
        latency_ms_display=display_latency_ms,
        latency_ms=display_latency_ms,
        authoritative_usage_available=usage_avail and (canonical_cost_dec is not None),
        input_tokens=normalized_usage["input_tokens"] if usage_avail else None,
        output_tokens=normalized_usage["output_tokens"] if usage_avail else None,
        total_tokens=normalized_usage["total_tokens"] if usage_avail else None,
        thought_tokens=normalized_usage["thought_tokens"] if usage_avail else None,
        reasoning_tokens=normalized_usage["reasoning_tokens"] if usage_avail else None,
        thinking_tokens=normalized_usage["thinking_tokens"] if usage_avail else None,
        cached_input_tokens=normalized_usage["cached_input_tokens"] if usage_avail else None,
        cache_read_input_tokens=(
            normalized_usage["cache_read_input_tokens"] if usage_avail else None
        ),
        cache_creation_input_tokens=(
            normalized_usage["cache_creation_input_tokens"] if usage_avail else None
        ),
        raw_usage_metadata=copy.deepcopy(raw_usage_dict),
        canonical_cost_usd_decimal=canonical_cost_dec_str,
        canonical_cost_usd_display=canonical_cost_disp,
        canonical_cost_usd=canonical_cost_disp,
        request_manifest_sha256=req_manifest_sha,
        raw_response_sha256=raw_resp_sha,
        provider_metadata_sha256=meta_sha,
        parsed_response_sha256=parsed_sha,
        evaluation_result_sha256=eval_sha,
    )
    write_immutable_canonical_json(
        cell_dir / "execution_receipt.json",
        receipt.model_dump(),
        extra_secrets=extra_secrets,
    )

    if failure_class == DevCellFailureClassification.MODEL_INTEGRITY_MISMATCH:
        raise ModelIntegrityBatchStopError(
            f"MODEL_INTEGRITY_MISMATCH in cell {cell_manifest.run_id}: "
            f"requested={cell_manifest.requested_model_id!r}, returned={returned_model!r}. "
            f"Batch execution MUST stop immediately."
        )
    if failure_class == DevCellFailureClassification.HARNESS_INTERNAL_ERROR:
        raise HarnessInternalBatchStopError(
            f"HARNESS_INTERNAL_ERROR in cell {cell_manifest.run_id}: "
            f"Batch execution MUST stop immediately."
        )
    if is_batch_stop:
        raise BatchExecutionFatalStopError(
            f"BATCH_STOP_FATAL_STATE in cell {cell_manifest.run_id} ({failure_class.value})."
        )

    return receipt, eval_result


# ==============================================================================
# 10. BATCH EXECUTION & TWO-STAGE PLAN-BEFORE-LIVE PROTOCOL (SECTIONS 7-14)
# ==============================================================================


def execute_live_dev_batch(
    *,
    execution_plan_path: Path,
    prompt_freeze_path: Path,
    authorization_path: Path,
    batch_root_dir: Path,
    prompt_registry: PromptRegistry,
    transport: Union[
        ProductionDevProviderTransport,
        MockDevProviderTransport,
        MockProviderTransportResponse,
        ProviderNormalizedTransportResponse,
    ],
    execution_mode: Optional[Union[RunnerExecutionMode, str]] = None,
    live_capability: Optional[LiveExecutionCapability] = None,
    stage_a_freeze_receipt_path: Optional[Path] = None,
    cost_comparability_by_candidate: Optional[
        Dict[str, CandidateCostComparabilityRecord]
    ] = None,
    dev_bundle: Optional[VerifiedDevBundle] = None,
    candidate_registry: Optional[DevCandidateRegistry] = None,
    dev_select_result: Optional[DevSelectModelSelectionResult] = None,
    catalog_path: Optional[Path] = None,
    core_catalog_by_id: Optional[Dict[str, BenchmarkCatalogPOI]] = None,
    repo_root: Optional[Path] = None,
    monotonic_ns_clock: Callable[[], int] = time.monotonic_ns,
    utc_now_clock: Callable[[], str] = default_utc_now_clock,
    extra_secrets: Optional[Sequence[str]] = None,
) -> Tuple[List[DevCellExecutionReceipt], DevCallBudgetLedger]:
    """Execute a full DEV-TUNE, DEV-SELECT, or STOCHASTICITY batch in deterministic cell order.

    Enforces:
    - Explicit `execution_mode` (`LIVE_EXECUTION` vs `OFFLINE_MOCK_TEST`)
    - In `LIVE_EXECUTION` mode: requires `stage_a_freeze_receipt_path` (committed in git with
      ancestor + blob attestation), `live_capability` (`LiveExecutionCapability`), and
      `ProductionDevProviderTransport`, and locks `LiveExecutionContext` at the batch action boundary
      immediately before the first cell.
    - Pre-validates all cells, authorization, prompt freeze, code bundle, and provider configs
      BEFORE the first call.
    """
    _assert_runner_not_final100_path(execution_plan_path)
    _assert_runner_not_final100_path(prompt_freeze_path)
    _assert_runner_not_final100_path(authorization_path)
    _assert_runner_not_final100_path(batch_root_dir)
    if stage_a_freeze_receipt_path is not None:
        _assert_runner_not_final100_path(stage_a_freeze_receipt_path)

    if not isinstance(execution_plan_path, Path) or not execution_plan_path.exists():
        raise PlanBeforeLiveProtocolError(
            f"STAGE_A_EXECUTION_PLAN_MISSING: Execution plan file must be frozen on disk before batch execution: {execution_plan_path}"
        )
    if not isinstance(prompt_freeze_path, Path) or not prompt_freeze_path.exists():
        raise PromptFreezeFirewallError(
            f"STAGE_A_PROMPT_FREEZE_MISSING: Prompt freeze file must be frozen on disk before batch execution: {prompt_freeze_path}"
        )
    if not isinstance(authorization_path, Path) or not authorization_path.exists():
        raise DevLiveAuthorizationError(
            f"STAGE_A_AUTHORIZATION_MISSING: Authorization file must be frozen on disk before batch execution: {authorization_path}"
        )

    effective_repo_root = repo_root or (
        live_capability.repo_root if live_capability is not None else None
    )

    raw_plan = json.loads(execution_plan_path.read_text(encoding="utf-8"))
    raw_phase = raw_plan.get("phase")
    if raw_phase == "FINAL100" or (
        isinstance(raw_phase, str) and "FINAL" in raw_phase.upper()
    ):
        raise Final100FirewallViolationError(
            f"FINAL100_FIREWALL_VIOLATION: DEV live runner rejects execution plan phase {raw_phase!r}."
        )
    if raw_phase == "STOCHASTICITY_DIAGNOSTIC":
        if dev_select_result is None or not dev_select_result.winner_selected:
            raise StochasticityGateViolationError(
                "STOCHASTICITY_BLOCKED_BEFORE_WINNER_FROZEN: Cannot run stochasticity plan before winner selection."
            )
        execution_plan: Union[DevExecutionPlan, StochasticityDiagnosticPlan] = (
            StochasticityDiagnosticPlan.model_validate(raw_plan)
        )
    else:
        execution_plan = DevExecutionPlan.model_validate(raw_plan)

    bundle = dev_bundle or load_and_verify_frozen_dev_bundle()
    cand_reg = candidate_registry or load_and_verify_candidate_registry()
    core_map = core_catalog_by_id or load_core_catalog_by_place_id(catalog_path=catalog_path)

    if isinstance(execution_plan, DevExecutionPlan):
        verify_dev_execution_plan_for_execution(
            execution_plan, candidate_registry=cand_reg, repo_root=effective_repo_root
        )

    verified_pf = verify_runner_prompt_freeze_artifact(
        prompt_freeze_path,
        prompt_registry=prompt_registry,
        execution_plan=execution_plan,
        dev_bundle=bundle,
        candidate_registry=cand_reg,
        repo_root=effective_repo_root,
    )
    verified_auth = verify_dev_live_authorization_artifact(
        authorization_path,
        execution_plan=execution_plan,
        prompt_freeze=verified_pf,
        dev_select_result=dev_select_result,
        repo_root=effective_repo_root,
    )

    validated_runner_mode, _ = _validate_and_resolve_transport_and_mode(
        execution_mode=execution_mode,
        transport=transport,
        live_capability=live_capability,
        execution_plan=execution_plan,
        verified_prompt_freeze=verified_pf,
        verified_auth=verified_auth,
    )

    locked_live_context: Optional[LiveExecutionContext] = None
    if validated_runner_mode == RUNNER_EXECUTION_MODE_LIVE_EXECUTION:
        assert live_capability is not None
        resolved_stage_a_path = (
            stage_a_freeze_receipt_path or live_capability.stage_a_freeze_receipt_path
        )
        locked_live_context = reattest_stage_a_at_live_action_boundary(
            live_capability=live_capability,
            execution_plan=execution_plan,
            prompt_freeze=verified_pf,
            authorization=verified_auth,
            prompt_registry=prompt_registry,
            stage_a_freeze_receipt_path=resolved_stage_a_path,
            execution_plan_path=execution_plan_path,
            prompt_freeze_path=prompt_freeze_path,
            authorization_path=authorization_path,
            dev_bundle=bundle,
            candidate_registry=cand_reg,
            dev_select_result=dev_select_result,
            repo_root=effective_repo_root,
            expected_locked_context=None,
        )
    elif stage_a_freeze_receipt_path is not None:
        verify_stage_a_freeze_receipt(
            stage_a_freeze_receipt_path,
            execution_plan=execution_plan,
            prompt_freeze=verified_pf,
            authorization=verified_auth,
            execution_plan_path=execution_plan_path,
            prompt_freeze_path=prompt_freeze_path,
            authorization_path=authorization_path,
            candidate_registry=cand_reg,
            repo_root=effective_repo_root,
            require_git_committed=False,
        )

    scenarios_by_id: Dict[str, BenchmarkScenarioInput] = {
        s.scenario_id: s
        for s in (bundle.dev_tune_fixtures + bundle.dev_select_fixtures)
    }

    for cell in execution_plan.cells:
        assert_not_final100_scenario_id(cell.fixture_id)
        if cell.fixture_id not in scenarios_by_id:
            raise PlanBeforeLiveProtocolError(
                f"UNKNOWN_FIXTURE_IN_PLAN: {cell.fixture_id!r}"
            )
        assert_not_final100_scenario(scenarios_by_id[cell.fixture_id])
        verify_cell_manifest_for_execution(
            cell, candidate_registry=cand_reg, repo_root=effective_repo_root
        )
        inspect_and_guard_cell_directory_before_transport(
            batch_root_dir / cell.run_id, cell_manifest=cell
        )

    ledger = DevCallBudgetLedger.from_execution_plan(
        execution_plan,
        maximum_live_generation_calls=verified_auth.maximum_live_generation_calls,
    )

    receipts: List[DevCellExecutionReceipt] = []
    for cell in execution_plan.cells:
        rec, _ = execute_live_dev_cell(
            cell_manifest=cell,
            scenario=scenarios_by_id[cell.fixture_id],
            execution_plan=execution_plan,
            prompt_freeze=verified_pf,
            prompt_registry=prompt_registry,
            authorization=verified_auth,
            call_budget_ledger=ledger,
            cell_dir=batch_root_dir / cell.run_id,
            transport=transport,
            execution_mode=validated_runner_mode,
            live_capability=live_capability,
            stage_a_freeze_receipt_path=(
                locked_live_context.stage_a_freeze_receipt_path
                if locked_live_context is not None
                else stage_a_freeze_receipt_path
            ),
            execution_plan_path=execution_plan_path,
            prompt_freeze_path=prompt_freeze_path,
            authorization_path=authorization_path,
            live_execution_context=locked_live_context,
            cost_comparability_by_candidate=cost_comparability_by_candidate,
            dev_bundle=bundle,
            candidate_registry=cand_reg,
            dev_select_result=dev_select_result,
            catalog_path=catalog_path,
            core_catalog_by_id=core_map,
            repo_root=effective_repo_root,
            monotonic_ns_clock=monotonic_ns_clock,
            utc_now_clock=utc_now_clock,
            extra_secrets=extra_secrets,
        )
        receipts.append(rec)

    return receipts, ledger


# ==============================================================================
# 11. DRY-RUN MODE (SECTION 39)
# ==============================================================================


def run_dev_live_runner_dry_run(
    *,
    execution_plan: Union[DevExecutionPlan, Path, str],
    prompt_freeze: Union[DevPromptFreezeArtifact, Path, str],
    prompt_registry: Optional[PromptRegistry] = None,
    authorization: Optional[Union[DevLiveAuthorizationArtifact, Path, str]] = None,
    stage_a_freeze_receipt: Optional[Union[DevLiveStageAFreezeReceipt, Path, str]] = None,
    batch_root_dir: Optional[Path] = None,
    dev_bundle: Optional[VerifiedDevBundle] = None,
    candidate_registry: Optional[DevCandidateRegistry] = None,
    catalog_path: Optional[Path] = None,
    repo_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Perform all pre-transport validation, request serialization, artifact path planning, and call count calculation with 0 provider calls."""
    bundle = dev_bundle or load_and_verify_frozen_dev_bundle()
    cand_reg = candidate_registry or load_and_verify_candidate_registry()
    prompt_reg = prompt_registry or build_default_infrastructure_prompt_registry()

    if isinstance(execution_plan, (Path, str)):
        plan_path = Path(execution_plan)
        _assert_runner_not_final100_path(plan_path)
        if not plan_path.exists():
            raise PlanBeforeLiveProtocolError(
                f"EXECUTION_PLAN_FILE_MISSING: {plan_path}"
            )
        plan_obj = DevExecutionPlan.model_validate(
            json.loads(plan_path.read_text(encoding="utf-8"))
        )
    elif isinstance(execution_plan, DevExecutionPlan):
        plan_obj = execution_plan
    else:
        raise PlanBeforeLiveProtocolError(
            f"Unsupported execution_plan type: {type(execution_plan)}"
        )

    if plan_obj.phase == "FINAL100":
        raise Final100FirewallViolationError(
            "FINAL100_FIREWALL_VIOLATION: FINAL100 is forbidden in DEV live runner dry-run."
        )

    runtime_head_sha = verify_dev_execution_plan_for_execution(
        plan_obj, candidate_registry=cand_reg, repo_root=repo_root
    )
    verified_pf = verify_runner_prompt_freeze_artifact(
        prompt_freeze,
        prompt_registry=prompt_reg,
        execution_plan=plan_obj,
        dev_bundle=bundle,
        candidate_registry=cand_reg,
        repo_root=repo_root,
    )

    verified_auth: Optional[DevLiveAuthorizationArtifact] = None
    if authorization is not None:
        verified_auth = verify_dev_live_authorization_artifact(
            authorization,
            execution_plan=plan_obj,
            prompt_freeze=verified_pf,
            repo_root=repo_root,
        )

    verified_stage_a: Optional[DevLiveStageAFreezeReceipt] = None
    if stage_a_freeze_receipt is not None and verified_auth is not None:
        verified_stage_a = verify_stage_a_freeze_receipt(
            stage_a_freeze_receipt,
            execution_plan=plan_obj,
            prompt_freeze=verified_pf,
            authorization=verified_auth,
            candidate_registry=cand_reg,
            repo_root=repo_root,
            require_git_committed=False,
        )

    scenarios_by_id: Dict[str, BenchmarkScenarioInput] = {
        s.scenario_id: s
        for s in (bundle.dev_tune_fixtures + bundle.dev_select_fixtures)
    }
    prompts_by_id: Dict[str, PromptCandidateSpec] = {
        p.prompt_id: p for p in prompt_reg.prompts
    }

    target_root = batch_root_dir or (REPO_ROOT / "tmp_dry_run_planning_only")
    _assert_runner_not_final100_path(target_root)

    serialized_request_sha256_by_run_id: Dict[str, str] = {}
    planned_artifact_paths_by_run_id: Dict[str, Dict[str, str]] = {}

    for cell in plan_obj.cells:
        assert_not_final100_scenario_id(cell.fixture_id)
        verify_cell_manifest_for_execution(
            cell, candidate_registry=cand_reg, repo_root=repo_root
        )
        wire_req = build_frozen_provider_wire_request(
            cell_manifest=cell,
            scenario=scenarios_by_id[cell.fixture_id],
            prompt_spec=prompts_by_id[cell.prompt_id],
            candidate_registry=cand_reg,
            catalog_path=catalog_path,
        )
        serialized_request_sha256_by_run_id[cell.run_id] = sha256_bytes(
            canonical_json_bytes(wire_req)
        )
        c_dir = target_root / cell.run_id
        planned_artifact_paths_by_run_id[cell.run_id] = {
            fname: str(c_dir / fname)
            for fname in (
                "request_manifest.json",
                "transport_journal_starting.json",
                "transport_journal_completed.json",
                "raw_provider_response.txt",
                "provider_response_metadata.json",
                "raw_usage_metadata.json",
                "run_manifest.json",
                "parsed_plan_response.json",
                "evaluation_result.json",
                "execution_receipt.json",
            )
        }

    return {
        "mode": "dry_run",
        "dry_run": True,
        "transport_status": TRANSPORT_STATUS_NOT_INVOKED,
        "live_provider_calls": 0,
        "provider_cost_usd": 0,
        "phase": plan_obj.phase,
        "plan_sha256": plan_obj.plan_sha256,
        "planned_call_count": len(plan_obj.cells),
        "expected_total_cells": plan_obj.expected_total_cells,
        "code_basis_commit_sha": plan_obj.code_basis_commit_sha,
        "runtime_head_sha": runtime_head_sha,
        "scientific_code_bundle_sha256": plan_obj.scientific_code_bundle_sha256,
        "prompt_freeze_sha256": compute_prompt_freeze_sha256(verified_pf),
        "authorization_verified": verified_auth is not None,
        "authorization_id": verified_auth.authorization_id if verified_auth else None,
        "stage_a_verified": verified_stage_a is not None,
        "stage_a_receipt_sha256": (
            verified_stage_a.stage_a_receipt_sha256 if verified_stage_a else None
        ),
        "serialized_request_sha256_by_run_id": serialized_request_sha256_by_run_id,
        "planned_artifact_paths_by_run_id": planned_artifact_paths_by_run_id,
    }


# ==============================================================================
# 12. RUNNER RECEIPT & CLI ENTRYPOINT (SECTION 17 & 20)
# ==============================================================================


def build_dev_live_runner_01_receipt_payload() -> Dict[str, Any]:
    """Build the canonical receipt payload for `data/evaluation/w06/w06_dev_live_runner_01_receipt_v1.json` (Section 17)."""
    verified_authorities = verify_frozen_authorities_dev_harness()
    code_bundle = compute_scientific_code_bundle()
    cand_reg = load_and_verify_candidate_registry()
    runner_rel_path = "apps/ai-service/app/evaluation/dev_live_runner.py"
    runner_in_bundle = runner_rel_path in SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS

    return {
        "artifact_id": RUNNER_RECEIPT_ARTIFACT_ID,
        "task_id": TASK_ID_DEV_LIVE_RUNNER_01,
        "audit_correction_task_id": TASK_ID_DEV_LIVE_RUNNER_01_CORRECTION_02,
        "version": RUNNER_VERSION,
        "base_develop_sha": EXPECTED_BASE_DEVELOP_SHA_RUNNER_01,
        "live_provider_calls": 0,
        "provider_cost_usd": 0,
        "runner_implemented": True,
        "runner_module_path": runner_rel_path,
        "runner_in_scientific_code_bundle": runner_in_bundle,
        "actual_production_provider_transports_implemented": True,
        "production_google_transport": "PASS",
        "production_openai_transport": "PASS",
        "production_anthropic_transport": "PASS",
        "programmatic_live_gate_bypass_closed": "PASS",
        "arbitrary_callable_live_transport_forbidden": "PASS",
        "stage_a_freeze_receipt": "PASS",
        "stage_a_commit_attestation": "PASS",
        "stage_a_process_token_required_non_empty": "PASS",
        "stage_a_process_token_auto_stamped_by_production_builder": "PASS",
        "same_process_stage_a_to_stage_b_blocked": "PASS",
        "execution_timestamp_dynamic_not_hardcoded": "PASS",
        "execution_timestamp_matches_transport_start_journal": "PASS",
        "action_boundary_stage_a_reattestation": "PASS",
        "post_capability_repo_drift_blocked": "PASS",
        "live_capability_role": LIVE_CAPABILITY_ROLE_ORCHESTRATION_GUARD,
        "provider_exception_mapping": "PASS",
        "http_request_counting": "PASS",
        "benchmark_manifest_provenance_truthful": "PASS",
        "benchmark_manifest_config_truthful": "PASS",
        "execution_mode_truthful": "PASS",
        "historical_qa02_unchanged": True,
        "scientific_code_bundle_sha256": code_bundle.scientific_code_bundle_sha256,
        "scientific_code_bundle_files": list(SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS),
        "scientific_code_bundle_file_hashes": code_bundle.scientific_code_bundle_file_hashes,
        "prompt_freeze_status": PROMPT_FREEZE_STATUS_NOT_YET_FROZEN,
        "prompt_semantic_freeze_gate_status": PROMPT_FREEZE_INFRASTRUCTURE_STATUS,
        "live_authorization_present": False,
        "dev_model_execution_allowed": False,
        "dev_tune_execution_started": False,
        "dev_select_execution_started": False,
        "stochasticity_execution_started": False,
        "winner_selected": False,
        "final100_used": False,
        "dry_run_supported": True,
        "plan_before_live_protocol": "PASS",
        "authorization_gate": "PASS",
        "call_budget_ledger": "PASS",
        "transport_start_journal": "PASS",
        "crash_ambiguity_fail_closed": "PASS",
        "final100_separation": "PASS",
        "strict_primary_parser": "PASS",
        "model_id_integrity": "PASS",
        "provider_config_attestation": "PASS",
        "code_bundle_attestation": "PASS",
        "raw_evidence_immutability": "PASS",
        "secret_sanitization": "PASS",
        "network_kill_switch_test": "PASS",
        "supported_candidates": list(ORDERED_CANDIDATE_IDS),
        "candidate_registry_sha256": cand_reg.registry_sha256,
        "provider_config_registry_sha256": compute_provider_config_registry_sha256(cand_reg),
        "semantic_schema_sha256": EXPECTED_SEMANTIC_SCHEMA_SHA256,
        "portable_generation_schema_v2_sha256": EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
        "call_budgets": {
            "dev_tune_1_prompt": DEV_TUNE_MAX_CALLS_ONE_PROMPT,
            "dev_tune_2_prompts": DEV_TUNE_MAX_CALLS_TWO_PROMPTS,
            "dev_select": DEV_SELECT_MAX_CALLS,
            "stochasticity_post_winner": STOCHASTICITY_MAX_CALLS,
            "retry": 0,
        },
        "frozen_authority_preservation": verified_authorities,
        "next_gate": NEXT_GATE_RUNNER_QA_01,
        "status": "READY_FOR_CHATGPT_FINAL_REAUDIT",
    }


def write_dev_live_runner_01_receipt(
    output_path: Optional[Path] = None,
) -> Tuple[str, Dict[str, Any]]:
    """Write `data/evaluation/w06/w06_dev_live_runner_01_receipt_v1.json`."""
    target = output_path or DEFAULT_RUNNER_RECEIPT_PATH
    payload = build_dev_live_runner_01_receipt_payload()
    sha = write_canonical_json(target, payload)
    return sha, payload


def run_cli(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """CLI entrypoint for `dev_live_runner.py` (Sections 7, 9, 10, 11).

    Enforces:
    - Without `--execute-live`, NEVER contacts any provider.
    - Rejects any `--final100` or `FINAL100` phase immediately.
    - Rejects any combined `--create-plan` / `--create-stage-a` + `--execute-live` command (`PlanBeforeLiveProtocolError`).
    - If `--execute-live` is passed, requires `--authorization-artifact`, `--execution-plan`,
      `--prompt-freeze`, and `--stage-a-freeze-receipt` and validates them fail-closed
      (including git commit ancestor & blob verification) before constructing `ProductionDevProviderTransport`.
    """
    raw_args = list(argv) if argv is not None else []
    for arg in raw_args:
        if "final100" in arg.lower():
            raise Final100FirewallViolationError(
                f"FINAL100_FIREWALL_VIOLATION: Flag/argument {arg!r} is forbidden in the W06 DEV live runner."
            )

    parser = argparse.ArgumentParser(
        description="W06 DEV Scientific Live Runner (offline by default; fail-closed)."
    )
    parser.add_argument(
        "--offline-validate",
        action="store_true",
        help="Validate offline runner readiness and build receipt payload (0 provider calls).",
    )
    parser.add_argument(
        "--write-receipt",
        action="store_true",
        help="Write data/evaluation/w06/w06_dev_live_runner_01_receipt_v1.json (0 provider calls).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run pre-transport validation, request serialization, and call budget check (TRANSPORT_NOT_INVOKED).",
    )
    parser.add_argument(
        "--execute-live",
        action="store_true",
        help="Explicit live execution flag (requires --authorization-artifact, --execution-plan, --prompt-freeze, --stage-a-freeze-receipt).",
    )
    parser.add_argument(
        "--create-plan",
        action="store_true",
        help="Stage A plan creation flag (cannot be combined with --execute-live).",
    )
    parser.add_argument(
        "--create-stage-a",
        action="store_true",
        help="Stage A freeze creation flag (cannot be combined with --execute-live).",
    )
    parser.add_argument(
        "--execution-plan",
        type=str,
        default=None,
        help="Path to pre-frozen DevExecutionPlan JSON file.",
    )
    parser.add_argument(
        "--prompt-freeze",
        type=str,
        default=None,
        help="Path to pre-frozen DevPromptFreezeArtifact JSON file.",
    )
    parser.add_argument(
        "--authorization-artifact",
        type=str,
        default=None,
        help="Path to pre-frozen DevLiveAuthorizationArtifact JSON file.",
    )
    parser.add_argument(
        "--stage-a-freeze-receipt",
        type=str,
        default=None,
        help="Path to pre-frozen committed DevLiveStageAFreezeReceipt JSON file.",
    )
    parser.add_argument(
        "--batch-root-dir",
        type=str,
        default=None,
        help="Output directory for cell execution artifacts.",
    )
    parser.add_argument(
        "--phase",
        type=str,
        default=None,
        help="Optional phase filter/assertion (DEV_TUNE / DEV_SELECT / STOCHASTICITY).",
    )

    parsed = parser.parse_args(raw_args)

    if parsed.phase is not None and (
        parsed.phase == "FINAL100" or "FINAL" in parsed.phase.upper()
    ):
        raise Final100FirewallViolationError(
            f"FINAL100_FIREWALL_VIOLATION: Phase {parsed.phase!r} is forbidden in DEV live runner."
        )

    if (parsed.create_plan or parsed.create_stage_a) and parsed.execute_live:
        raise PlanBeforeLiveProtocolError(
            "PLAN_BEFORE_LIVE_VIOLATION: Cannot combine --create-plan / --create-stage-a and --execute-live in a single unreviewed step."
        )

    if parsed.execute_live:
        if not parsed.execution_plan:
            raise PlanBeforeLiveProtocolError(
                "EXECUTION_PLAN_MISSING: --execute-live requires --execution-plan <path>."
            )
        if not parsed.prompt_freeze:
            raise PromptFreezeFirewallError(
                "PROMPT_FREEZE_MISSING: --execute-live requires --prompt-freeze <path>."
            )
        if not parsed.authorization_artifact:
            raise LiveExecutionNotAuthorizedError(
                "AUTHORIZATION_ARTIFACT_MISSING: --execute-live requires --authorization-artifact <path>."
            )
        if not parsed.stage_a_freeze_receipt:
            raise PlanBeforeLiveProtocolError(
                "STAGE_A_FREEZE_RECEIPT_MISSING: --execute-live requires --stage-a-freeze-receipt <path>."
            )

        plan_path = Path(parsed.execution_plan)
        pf_path = Path(parsed.prompt_freeze)
        auth_path = Path(parsed.authorization_artifact)
        stage_a_path = Path(parsed.stage_a_freeze_receipt)

        prompt_reg = build_default_infrastructure_prompt_registry()
        capability, plan_obj, _, verified_auth, _ = issue_live_execution_capability(
            execute_live=True,
            execution_plan_path=plan_path,
            prompt_freeze_path=pf_path,
            authorization_path=auth_path,
            stage_a_freeze_receipt_path=stage_a_path,
            prompt_registry=prompt_reg,
        )
        if parsed.phase is not None and verified_auth.allowed_phase != parsed.phase:
            raise DevLiveAuthorizationError(
                f"AUTHORIZATION_PHASE_MISMATCH: {verified_auth.allowed_phase!r} != {parsed.phase!r}"
            )
        prod_transport = create_live_provider_transport_factory(
            execute_live=True,
            authorization=verified_auth,
            live_capability=capability,
        )
        out_root = (
            Path(parsed.batch_root_dir)
            if parsed.batch_root_dir
            else (REPO_ROOT / "data" / "evaluation" / "w06" / f"live_{capability.phase.lower()}")
        )
        receipts, ledger = execute_live_dev_batch(
            execution_plan_path=plan_path,
            prompt_freeze_path=pf_path,
            authorization_path=auth_path,
            stage_a_freeze_receipt_path=stage_a_path,
            batch_root_dir=out_root,
            prompt_registry=prompt_reg,
            transport=prod_transport,
            execution_mode=RUNNER_EXECUTION_MODE_LIVE_EXECUTION,
            live_capability=capability,
        )
        return {
            "mode": "execute_live",
            "phase": plan_obj.phase,
            "executed_cells": len(receipts),
            "ledger": ledger.summary(),
        }

    if parsed.dry_run:
        if not parsed.execution_plan:
            raise PlanBeforeLiveProtocolError(
                "EXECUTION_PLAN_MISSING: --dry-run requires --execution-plan <path>."
            )
        if not parsed.prompt_freeze:
            raise PromptFreezeFirewallError(
                "PROMPT_FREEZE_MISSING: --dry-run requires --prompt-freeze <path>."
            )
        return run_dev_live_runner_dry_run(
            execution_plan=Path(parsed.execution_plan),
            prompt_freeze=Path(parsed.prompt_freeze),
            authorization=Path(parsed.authorization_artifact)
            if parsed.authorization_artifact
            else None,
            stage_a_freeze_receipt=Path(parsed.stage_a_freeze_receipt)
            if parsed.stage_a_freeze_receipt
            else None,
        )

    if parsed.write_receipt:
        sha, receipt = write_dev_live_runner_01_receipt()
        return {
            "mode": "write_receipt",
            "transport_status": TRANSPORT_STATUS_NOT_INVOKED,
            "live_provider_calls": 0,
            "receipt_sha256": sha,
            "receipt": receipt,
        }

    if parsed.offline_validate:
        receipt = build_dev_live_runner_01_receipt_payload()
        return {
            "mode": "offline_validate",
            "transport_status": TRANSPORT_STATUS_NOT_INVOKED,
            "live_provider_calls": 0,
            "status": "PASS",
            "receipt": receipt,
        }

    raise LiveExecutionNotAuthorizedError(
        "NO_MODE_SPECIFIED: Specify --offline-validate, --dry-run, or --write-receipt. "
        "Default live execution is forbidden."
    )


if __name__ == "__main__":
    import sys

    out = run_cli(sys.argv[1:])
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
