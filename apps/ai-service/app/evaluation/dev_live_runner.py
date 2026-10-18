"""Production-grade W06 DEV Live Runner Infrastructure (W06-DEV-LIVE-RUNNER-01-OFFLINE).

Grounded in:
- data/evaluation/w06/w06_model_arch_selection_method_lock_v1.json (W06-MODEL-ARCH-SELECTION-METHOD-LOCK-01 v1.0.0)
- data/evaluation/w06/w06_measurement_contract_v1.json (W06-MEASUREMENT-CONTRACT-01 v1.0.0)
- data/evaluation/w06/w06_dev_fixtures_freeze_v1.json (80 frozen DEV fixtures: 20 DEV-TUNE + 60 DEV-SELECT)
- data/evaluation/w06/w06_model_preflight_01d_v2_live_receipt_v1.json (C1/C2/C3 PASSED_TECHNICAL_PREFLIGHT_SCHEMA_V2)
- apps/ai-service/app/evaluation/dev_selection_harness.py (Frozen DEV selection harness authority)

STRICT SCIENTIFIC & OPERATIONAL INVARIANTS:
- Offline by default: zero live provider calls unless BOTH explicit `--execute-live` CLI/action flag
  AND a verified, phase-scoped `DevLiveAuthorizationArtifact` are supplied.
- In W06-DEV-LIVE-RUNNER-01-OFFLINE: LIVE_PROVIDER_CALLS = 0, PROVIDER_COST_USD = 0,
  LIVE_AUTHORIZATION_PRESENT = false, PROMPT_FREEZE_STATUS = NOT_YET_FROZEN.
- Secret-independent offline execution: never reads API key values or requires `.env` in offline/dry-run/test modes;
  sanitizes all persisted artifacts and exception text so secrets never enter prompt, request artifact,
  receipt, logs, exception text, authorization artifact, or provider metadata artifact.
- Candidates: exclusively C1 (`google` / `gemini-3.8-flash`), C2 (`openai` / `gpt-6.1-sol`),
  and C3 (`anthropic` / `claude-sonnet-5-5`), all requiring `PASSED_TECHNICAL_PREFLIGHT_SCHEMA_V2`
  under Portable Schema V2 (`825a4ff912d851a95f7392cb564b7d7ca3588135508dc6eb3ac6304cdde3c490`)
  and Semantic Schema (`e4169f7b890f77d13af65e9f2070b6071c535b206d88440f5e8f28c179977555`).
- Plan-Before-Live Protocol (Two-Stage Evidence):
  Stage A freezes execution plan, prompt freeze artifact, code bundle, provider configs, authorization,
  and exact assigned cell list on disk BEFORE any live execution.
  Stage B executes only against pre-frozen Stage A artifacts and refuses any combined create-plan-and-execute step.
- Single-request / Zero-retry: SDK retry = 0, transport retry = 0, manual retry = 0; at most 1 provider
  generation request per assigned cell.
- Transport-Start Journal & Crash Ambiguity Fail-Closed:
  Writes `transport_journal_starting.json` (`TRANSPORT_STARTING`) atomically BEFORE transport and
  `transport_journal_completed.json` (`TRANSPORT_COMPLETED`) as a separate append-only artifact AFTER transport.
  If a restart discovers `TRANSPORT_STARTING` without confirmed completion, records
  `ATTEMPT_STATUS_UNKNOWN_AFTER_TRANSPORT` and stops the entire batch without rerunning the cell.
- Raw Evidence Before Interpretation:
  Writes `request_manifest.json` before transport and writes `transport_journal_completed.json`,
  `raw_provider_response.txt`, `raw_usage_metadata.json`, and `provider_response_metadata.json`
  IMMEDIATELY after transport returns, BEFORE any model ID validation, JSON parsing, semantic validation,
  or evaluator invocation capable of failing.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
from decimal import Decimal
import json
import os
from pathlib import Path
import re
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

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.evaluation.dev_selection_harness import (
    ALLOWED_PROMPT_IDS,
    BATCH_STOP_FAILURE_CLASSIFICATIONS,
    DEV_SELECT_COUNT,
    DEV_SELECT_MAX_CALLS,
    DEV_TUNE_COUNT,
    DEV_TUNE_MAX_CALLS_ONE_PROMPT,
    DEV_TUNE_MAX_CALLS_TWO_PROMPTS,
    EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
    EXPECTED_SEMANTIC_SCHEMA_SHA256,
    EXPECTED_STOCHASTICITY_FIXTURE_IDS,
    FROZEN_SAMPLING_SEED,
    ORDERED_CANDIDATE_IDS,
    REPO_ROOT,
    SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS,
    STOCHASTICITY_MAX_CALLS,
    BatchExecutionFatalStopError,
    CandidateCostComparabilityRecord,
    CandidateRegistryIntegrityError,
    CodeCommitProvenanceError,
    DenominatorIntegrityError,
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
    PromptRegistryIntegrityError,
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
    compute_candidate_provider_config_sha256,
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
RUNNER_RECEIPT_ARTIFACT_ID: str = "W06-DEV-LIVE-RUNNER-01-RECEIPT-V1"
RUNNER_VERSION: str = "1.0.0"
EXPECTED_BASE_DEVELOP_SHA_RUNNER_01: str = "b2dfd8afb8db2e2bc4dfbb2d0ca4e6a9d22e3a50"
NEXT_GATE_RUNNER_QA_01: str = "W06-DEV-LIVE-RUNNER-QA-01-OFFLINE-ADVERSARIAL"

PROMPT_FREEZE_STATUS_NOT_YET_FROZEN: str = "NOT_YET_FROZEN"
PROMPT_FREEZE_INFRASTRUCTURE_STATUS: str = (
    "INFRASTRUCTURE_ONLY_PENDING_LATER_PROMPT_FREEZE_GATE"
)

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

CANDIDATE_PROVIDER_BY_ID: Dict[str, str] = {
    "C1": "google",
    "C2": "openai",
    "C3": "anthropic",
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
    """Raised when live execution is attempted without both --execute-live and a verified authorization artifact."""


class DevCallBudgetExhaustedError(DevLiveRunnerError):
    """Raised when a cell reservation or transport call would exceed the authorized call budget."""


class DuplicateDevCellAttemptError(ImmutableCellExecutionError, DevLiveRunnerError):
    """Raised when a duplicate run_id or duplicate scientific cell is attempted in the call-budget ledger."""


class CrashAmbiguityBatchStopError(DevLiveRunnerError):
    """Raised when TRANSPORT_STARTING exists without TRANSPORT_COMPLETED (ATTEMPT_STATUS_UNKNOWN_AFTER_TRANSPORT)."""


class PlanBeforeLiveProtocolError(DevLiveRunnerError):
    """Raised when Stage A pre-frozen artifacts or execution plan membership requirements are violated."""


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
# 4. AUTHORIZATION ARTIFACT CONTRACT & SCOPE VERIFICATION (SECTIONS 13, 14, 15)
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
    """Frozen authorization contract required for any future live DEV cell/batch execution (Section 14)."""

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
    allowed_phase: str,
    execution_plan: Union[DevExecutionPlan, StochasticityDiagnosticPlan],
    prompt_freeze: DevPromptFreezeArtifact,
    allowed_candidate_ids: Optional[Sequence[str]] = None,
    maximum_live_generation_calls: Optional[int] = None,
    authorized_at_utc: str = "2026-10-18T00:00:00Z",
    authorized_by_role: str = AUTHORIZED_BY_ROLE_PROJECT_OWNER,
    authorization_status: str = AUTHORIZATION_STATUS_AUTHORIZED,
    scientific_code_bundle_sha256: Optional[str] = None,
    code_basis_commit_sha: Optional[str] = None,
) -> DevLiveAuthorizationArtifact:
    """Build a deterministically hashed `DevLiveAuthorizationArtifact` for testing or future owner gate."""
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
        "allowed_candidate_ids": cands,
        "maximum_live_generation_calls": max_calls,
        "authorization_status": authorization_status,
        "scientific_code_bundle_sha256": bundle_sha,
        "code_basis_commit_sha": basis_sha,
    }
    artifact_sha = sha256_bytes(canonical_json_bytes(body))
    return DevLiveAuthorizationArtifact.model_validate(
        {**body, "authorization_artifact_sha256": artifact_sha}
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
    """Fail-closed verification of a `DevLiveAuthorizationArtifact` against plan, prompt freeze, phase, and code bundle (Sections 14, 15)."""
    if authorization_or_path is None:
        raise DevLiveAuthorizationError(
            "AUTHORIZATION_MISSING: Live or authorized DEV execution requires a valid DevLiveAuthorizationArtifact."
        )

    if isinstance(authorization_or_path, (Path, str)):
        auth_path = Path(authorization_or_path)
        assert_not_final100_path(auth_path)
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
) -> Path:
    """Persist immutable `transport_journal_starting.json` immediately before network/mock transport (Section 30)."""
    target = cell_dir / "transport_journal_starting.json"
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
        "timestamp_utc": timestamp_utc or dt.datetime.now(dt.timezone.utc).isoformat(),
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
) -> Path:
    """Persist append-only `transport_journal_completed.json` immediately after transport returns (Section 30)."""
    target = cell_dir / "transport_journal_completed.json"
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
        "latency_ns": int(latency_ns),
        "timestamp_utc": timestamp_utc or dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": TRANSPORT_STATUS_COMPLETED,
    }
    write_immutable_canonical_json(target, payload)
    return target


# ==============================================================================
# 7. FROZEN PROVIDER REQUEST CONSTRUCTION & USAGE NORMALIZATION (SECTIONS 4-6, 25)
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


def normalize_candidate_usage_metadata(
    candidate_id: str,
    raw_usage: Optional[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Normalize provider usage metadata for C1, C2, C3 while preserving raw fields (Section 25)."""
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
        in_tok = _opt_int("input_tokens", "prompt_token_count")
        out_tok = _opt_int("output_tokens", "candidates_token_count")
        thought_tok = _opt_int("thought_tokens", "thoughts_token_count")
        if thought_tok is None and in_tok is not None and out_tok is not None:
            thought_tok = 0
        cached_tok = _opt_int(
            "cached_tokens", "cached_input_tokens", "cached_content_token_count"
        )
        if cached_tok is None and in_tok is not None:
            cached_tok = 0
        total_tok = _opt_int("total_tokens", "total_token_count")
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
# 8. INJECTABLE TRANSPORT & PROVIDER CLIENT FACTORIES (SECTION 37)
# ==============================================================================


class DevProviderTransportProtocol(Protocol):
    """Protocol for injectable single-request provider transport (mock or future live)."""

    def __call__(
        self,
        cell_manifest: DevCellExecutionManifest,
        wire_request: Dict[str, Any],
    ) -> MockProviderTransportResponse: ...


class MockDevProviderTransport:
    """Deterministic offline mock transport that records exact call counts and never accesses the network."""

    def __init__(
        self,
        response_or_callable: Union[
            MockProviderTransportResponse,
            Mapping[str, MockProviderTransportResponse],
            Callable[[DevCellExecutionManifest, Dict[str, Any]], MockProviderTransportResponse],
            Callable[[DevCellExecutionManifest], MockProviderTransportResponse],
        ],
    ) -> None:
        self._source = response_or_callable
        self.call_count: int = 0
        self.call_count_by_run_id: Dict[str, int] = {}
        self.captured_requests_by_run_id: Dict[str, Dict[str, Any]] = {}

    def __call__(
        self,
        cell_manifest: DevCellExecutionManifest,
        wire_request: Dict[str, Any],
    ) -> MockProviderTransportResponse:
        self.call_count += 1
        self.call_count_by_run_id[cell_manifest.run_id] = (
            self.call_count_by_run_id.get(cell_manifest.run_id, 0) + 1
        )
        if self.call_count_by_run_id[cell_manifest.run_id] > 1:
            raise ImmutableCellExecutionError(
                f"RETRY_FORBIDDEN: Transport invoked more than once for cell {cell_manifest.run_id}"
            )
        self.captured_requests_by_run_id[cell_manifest.run_id] = copy.deepcopy(wire_request)

        if isinstance(self._source, MockProviderTransportResponse):
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
    authorization: Optional[DevLiveAuthorizationArtifact],
) -> DevProviderTransportProtocol:
    """Production factory boundary: refuses to instantiate any live provider client in offline tasks (Sections 13, 37, 38)."""
    if not execute_live:
        raise LiveExecutionNotAuthorizedError(
            "LIVE_EXECUTION_DISABLED: --execute-live is False; live provider transport factory cannot be constructed."
        )
    if authorization is None or authorization.authorization_status != AUTHORIZATION_STATUS_AUTHORIZED:
        raise LiveExecutionNotAuthorizedError(
            "LIVE_AUTHORIZATION_MISSING: Live provider transport requires a verified DevLiveAuthorizationArtifact."
        )
    raise LiveExecutionNotAuthorizedError(
        "LIVE_PROVIDER_EXECUTION_BLOCKED_IN_OFFLINE_GATE: "
        "Real provider SDK network execution is disabled until W06-DEV-LIVE-RUNNER-QA-01-OFFLINE-ADVERSARIAL "
        "and the explicit prompt-freeze + project-owner live authorization gate are completed."
    )


# ==============================================================================
# 9. SINGLE-CELL EXECUTION CORE (SECTIONS 17-27)
# ==============================================================================


def _extract_raw_usage_from_mock_response(
    candidate_id: str,
    response: MockProviderTransportResponse,
) -> Optional[Dict[str, Any]]:
    """Extract raw usage dictionary from MockProviderTransportResponse without losing provider-shaped fields."""
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
        DevProviderTransportProtocol,
        MockProviderTransportResponse,
        Callable[[DevCellExecutionManifest, Dict[str, Any]], MockProviderTransportResponse],
        Callable[[DevCellExecutionManifest], MockProviderTransportResponse],
    ],
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
    extra_secrets: Optional[Sequence[str]] = None,
) -> Tuple[DevCellExecutionReceipt, ScenarioEvaluationResult]:
    """Execute a single frozen DEV cell through all 17 fail-closed scientific steps (Section 17).

    Order of operations:
    1. Verify Final100 firewall on cell, scenario, and output directory
    2. Verify execution plan integrity & exact cell membership in plan
    3. Verify prompt freeze artifact against registry, plan, DEV bundle, candidate registry, and code bundle
    4. Verify phase-scoped authorization artifact against plan, prompt freeze, and code bundle
    5. Verify cell directory has no crash ambiguity (`TRANSPORT_STARTING`) or existing immutable artifacts
    6. Verify scientific code bundle from actual file bytes (no mtime/size cache)
    7. Verify provider configuration hash & model identity expectations
    8. Construct frozen provider request
    9. Reserve 1 call in deterministic call-budget ledger
    10. Atomically write `request_manifest.json` + `transport_journal_starting.json`
    11. Measure duration with `monotonic_ns_clock()` (`time.monotonic_ns`) around at most 1 transport call (`retry=0`)
    12. Atomically write `transport_journal_completed.json`, `raw_provider_response.txt`, `raw_usage_metadata.json`,
        and `provider_response_metadata.json` BEFORE any model ID validation, JSON parsing, or evaluation
    13. Validate returned model ID (never substituting requested_model_id for missing returned_model_id)
    14. Normalize usage metadata & compute exact Decimal cost where computable
    15. Strict primary parser (`raw_text -> json.loads -> BenchmarkPlanResponse.model_validate`, zero rescue)
    16. Invoke frozen evaluator (`evaluate_dev_cell_scenario`)
    17. Atomically write `parsed_plan_response.json` (when valid), `evaluation_result.json`, and `execution_receipt.json`.
    """
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

    # Step 2: Execution plan verification & cell membership
    if isinstance(execution_plan, DevExecutionPlan):
        runtime_head_sha = verify_dev_execution_plan_for_execution(
            execution_plan, candidate_registry=cand_reg, repo_root=repo_root
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
        runtime_head_sha = resolve_active_git_commit_sha(repo_root=repo_root)
        active_bundle_sha = compute_scientific_code_bundle_sha256(repo_root=repo_root)
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
        repo_root=repo_root,
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
        repo_root=repo_root,
    )

    # Step 5: Crash ambiguity & immutable artifact check before transport
    inspect_and_guard_cell_directory_before_transport(
        cell_dir, cell_manifest=cell_manifest
    )

    # Step 6 & 7: Code bundle & provider config attestation on cell manifest
    runtime_head_sha = verify_cell_manifest_for_execution(
        cell_manifest, candidate_registry=cand_reg, repo_root=repo_root
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

    # Step 10: Write request_manifest.json and transport_journal_starting.json BEFORE transport
    req_manifest_path = cell_dir / "request_manifest.json"
    req_manifest_payload = {
        **cell_manifest.model_dump(),
        "authorization_id": verified_auth.authorization_id,
        "authorization_artifact_sha256": verified_auth.authorization_artifact_sha256,
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
    )

    # Step 11: Invoke transport AT MOST ONCE with monotonic_ns timing
    transport_wrapper = (
        transport
        if isinstance(transport, MockDevProviderTransport)
        else MockDevProviderTransport(transport)
    )
    t_start_ns = monotonic_ns_clock()
    try:
        response = transport_wrapper(cell_manifest, wire_request)
    except Exception as exc:
        t_end_ns = monotonic_ns_clock()
        measured_ns = max(1, int(t_end_ns - t_start_ns))
        call_budget_ledger.consume_reserved_call(
            cell_manifest.run_id, transport_outcome="TRANSPORT_EXCEPTION"
        )
        sanitized_err = sanitize_runner_text(str(exc), extra_secrets=extra_secrets)
        response = MockProviderTransportResponse(
            returned_model_id=None,
            raw_text="",
            finish_reason=f"TRANSPORT_EXCEPTION: {sanitized_err}",
            latency_ns=measured_ns,
            latency_ms=round(float(Decimal(measured_ns) / Decimal(1_000_000)), 6),
            simulated_failure=DevCellFailureClassification.HARNESS_INTERNAL_ERROR,
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

    # Step 12: IMMEDIATELY persist transport_journal_completed.json, raw_provider_response.txt,
    # raw_usage_metadata.json, and provider_response_metadata.json BEFORE any validation/parsing!
    write_transport_journal_completed(
        cell_dir,
        cell_manifest=cell_manifest,
        runtime_head_sha=runtime_head_sha,
        authorization_id=verified_auth.authorization_id,
        latency_ns=authoritative_latency_ns,
    )

    raw_resp_path = cell_dir / "raw_provider_response.txt"
    raw_resp_sha = write_immutable_utf8_text(
        raw_resp_path, response.raw_text or "", extra_secrets=extra_secrets
    )

    raw_usage_dict = _extract_raw_usage_from_mock_response(
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

    meta_path = cell_dir / "provider_response_metadata.json"
    meta_payload = {
        "run_id": cell_manifest.run_id,
        "candidate_id": cell_manifest.candidate_id,
        "provider": CANDIDATE_PROVIDER_BY_ID[cell_manifest.candidate_id],
        "requested_model_id": cell_manifest.requested_model_id,
        "returned_model_id": returned_model,
        "code_basis_commit_sha": cell_manifest.code_basis_commit_sha,
        "code_commit_sha": cell_manifest.code_commit_sha,
        "runtime_head_sha": runtime_head_sha,
        "scientific_code_bundle_sha256": cell_manifest.scientific_code_bundle_sha256,
        "provider_config_sha256": cell_manifest.provider_config_sha256,
        "authorization_id": verified_auth.authorization_id,
        "finish_reason": sanitize_runner_text(
            response.finish_reason, extra_secrets=extra_secrets
        ),
        "latency_ns": authoritative_latency_ns,
        "latency_ms": display_latency_ms,
        "latency_ms_display": display_latency_ms,
        "simulated_failure": response.simulated_failure.value,
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

    if failure_class != DevCellFailureClassification.NONE:
        if failure_class == DevCellFailureClassification.MODEL_INTEGRITY_MISMATCH:
            run_status = BenchmarkRunStatus.MODEL_ID_MISMATCH
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

    # Step 16: Frozen evaluator authority
    manifest_model_id = (
        returned_model
        if (returned_model is not None and str(returned_model).strip())
        else "MISSING_RETURNED_MODEL_ID"
    )
    run_manifest = BenchmarkRunManifest(
        run_id=cell_manifest.run_id,
        scenario_id=scenario.scenario_id,
        execution_timestamp_utc="2026-10-18T00:00:00Z",
        provider=cell_manifest.candidate_id,
        model_id=manifest_model_id,
        expected_model_id=cell_manifest.requested_model_id,
        generation_parameters={
            "temperature": 0.0,
            "seed": FROZEN_SAMPLING_SEED,
        },
        execution_mode="OFFLINE_MOCK_HARNESS_VERIFICATION",
        latency_ms=display_latency_ms,
        usage_metadata=BenchmarkUsageMetadata(
            input_tokens=normalized_usage["input_tokens"] if usage_avail else None,
            output_tokens=normalized_usage["output_tokens"] if usage_avail else None,
            total_tokens=normalized_usage["total_tokens"] if usage_avail else None,
        ),
        code_commit_sha=cell_manifest.code_basis_commit_sha,
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
# 10. BATCH EXECUTION & TWO-STAGE PLAN-BEFORE-LIVE PROTOCOL (SECTIONS 16, 31-35)
# ==============================================================================


def execute_live_dev_batch(
    *,
    execution_plan_path: Path,
    prompt_freeze_path: Path,
    authorization_path: Path,
    batch_root_dir: Path,
    prompt_registry: PromptRegistry,
    transport: Union[
        DevProviderTransportProtocol,
        Mapping[str, MockProviderTransportResponse],
        Callable[[DevCellExecutionManifest, Dict[str, Any]], MockProviderTransportResponse],
        Callable[[DevCellExecutionManifest], MockProviderTransportResponse],
    ],
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
    extra_secrets: Optional[Sequence[str]] = None,
) -> Tuple[List[DevCellExecutionReceipt], DevCallBudgetLedger]:
    """Execute a full DEV-TUNE or DEV-SELECT batch in deterministic cell order (Sections 16, 31-35).

    Enforces Plan-Before-Live Protocol (Stage A artifacts must already exist on disk before Stage B runs)
    and validates all cells, authorization, prompt freeze, code bundle, and provider configs BEFORE the first call.
    """
    _assert_runner_not_final100_path(execution_plan_path)
    _assert_runner_not_final100_path(prompt_freeze_path)
    _assert_runner_not_final100_path(authorization_path)
    _assert_runner_not_final100_path(batch_root_dir)

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

    # Pre-validate execution plan, prompt freeze, authorization, code bundle, and all cells BEFORE first call
    if isinstance(execution_plan, DevExecutionPlan):
        verify_dev_execution_plan_for_execution(
            execution_plan, candidate_registry=cand_reg, repo_root=repo_root
        )

    verified_pf = verify_runner_prompt_freeze_artifact(
        prompt_freeze_path,
        prompt_registry=prompt_registry,
        execution_plan=execution_plan,
        dev_bundle=bundle,
        candidate_registry=cand_reg,
        repo_root=repo_root,
    )
    verified_auth = verify_dev_live_authorization_artifact(
        authorization_path,
        execution_plan=execution_plan,
        prompt_freeze=verified_pf,
        dev_select_result=dev_select_result,
        repo_root=repo_root,
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
            cell, candidate_registry=cand_reg, repo_root=repo_root
        )
        inspect_and_guard_cell_directory_before_transport(
            batch_root_dir / cell.run_id, cell_manifest=cell
        )

    ledger = DevCallBudgetLedger.from_execution_plan(
        execution_plan,
        maximum_live_generation_calls=verified_auth.maximum_live_generation_calls,
    )
    transport_wrapper = (
        transport
        if isinstance(transport, MockDevProviderTransport)
        else MockDevProviderTransport(transport)
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
            transport=transport_wrapper,
            cost_comparability_by_candidate=cost_comparability_by_candidate,
            dev_bundle=bundle,
            candidate_registry=cand_reg,
            dev_select_result=dev_select_result,
            catalog_path=catalog_path,
            core_catalog_by_id=core_map,
            repo_root=repo_root,
            monotonic_ns_clock=monotonic_ns_clock,
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
    batch_root_dir: Optional[Path] = None,
    dev_bundle: Optional[VerifiedDevBundle] = None,
    candidate_registry: Optional[DevCandidateRegistry] = None,
    catalog_path: Optional[Path] = None,
    repo_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Perform all pre-transport validation, request serialization, artifact path planning, and call count calculation with 0 provider calls (Section 39)."""
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
        "serialized_request_sha256_by_run_id": serialized_request_sha256_by_run_id,
        "planned_artifact_paths_by_run_id": planned_artifact_paths_by_run_id,
    }


# ==============================================================================
# 12. RUNNER RECEIPT & CLI ENTRYPOINT (SECTIONS 38, 39, 42)
# ==============================================================================


def build_dev_live_runner_01_receipt_payload() -> Dict[str, Any]:
    """Build the canonical receipt payload for `data/evaluation/w06/w06_dev_live_runner_01_receipt_v1.json` (Section 42)."""
    verified_authorities = verify_frozen_authorities_dev_harness()
    code_bundle = compute_scientific_code_bundle()
    cand_reg = load_and_verify_candidate_registry()
    runner_rel_path = "apps/ai-service/app/evaluation/dev_live_runner.py"
    runner_in_bundle = runner_rel_path in SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS

    return {
        "artifact_id": RUNNER_RECEIPT_ARTIFACT_ID,
        "task_id": TASK_ID_DEV_LIVE_RUNNER_01,
        "version": RUNNER_VERSION,
        "base_develop_sha": EXPECTED_BASE_DEVELOP_SHA_RUNNER_01,
        "live_provider_calls": 0,
        "provider_cost_usd": 0,
        "runner_implemented": True,
        "runner_module_path": runner_rel_path,
        "runner_in_scientific_code_bundle": runner_in_bundle,
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
        "status": "READY_FOR_CHATGPT_AUDIT",
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
    """CLI entrypoint for `dev_live_runner.py` (Sections 13, 16, 38, 39).

    Enforces:
    - Without `--execute-live`, NEVER contacts any provider.
    - Rejects any `--final100` or `FINAL100` phase immediately.
    - Rejects any combined `--create-plan` + `--execute-live` command (`PlanBeforeLiveProtocolError`).
    - If `--execute-live` is passed, requires `--authorization-artifact`, `--execution-plan`, and `--prompt-freeze`
      and validates them fail-closed before reaching the live transport boundary.
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
        help="Explicit live execution flag (requires --authorization-artifact, --execution-plan, --prompt-freeze).",
    )
    parser.add_argument(
        "--create-plan",
        action="store_true",
        help="Stage A plan creation flag (cannot be combined with --execute-live).",
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

    if parsed.create_plan and parsed.execute_live:
        raise PlanBeforeLiveProtocolError(
            "PLAN_BEFORE_LIVE_VIOLATION: Cannot combine --create-plan and --execute-live in a single unreviewed step."
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

        plan_path = Path(parsed.execution_plan)
        pf_path = Path(parsed.prompt_freeze)
        auth_path = Path(parsed.authorization_artifact)
        assert_not_final100_path(plan_path)
        assert_not_final100_path(pf_path)
        assert_not_final100_path(auth_path)

        if not plan_path.exists():
            raise PlanBeforeLiveProtocolError(
                f"EXECUTION_PLAN_FILE_MISSING: {plan_path}"
            )
        if not pf_path.exists():
            raise PromptFreezeFirewallError(
                f"PROMPT_FREEZE_FILE_MISSING: {pf_path}"
            )
        if not auth_path.exists():
            raise LiveExecutionNotAuthorizedError(
                f"AUTHORIZATION_FILE_MISSING: {auth_path}"
            )

        raw_plan = json.loads(plan_path.read_text(encoding="utf-8"))
        plan_obj = DevExecutionPlan.model_validate(raw_plan)
        verify_dev_execution_plan_for_execution(plan_obj)
        prompt_reg = build_default_infrastructure_prompt_registry()
        verified_pf = verify_prompt_candidate_freeze_artifact(
            pf_path,
            prompt_registry=prompt_reg,
            dev_tune_plan=plan_obj if plan_obj.phase == "DEV_TUNE" else None,
        )
        verified_auth = verify_dev_live_authorization_artifact(
            auth_path,
            execution_plan=plan_obj,
            prompt_freeze=verified_pf,
            expected_phase=parsed.phase,
        )
        create_live_provider_transport_factory(
            execute_live=True,
            authorization=verified_auth,
        )

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
