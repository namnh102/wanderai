"""Evaluation-only W06 Model/Provider Technical Preflight package (Phase 01A Offline).

Exposes offline candidate adapters C1 (Google), C2 (OpenAI), C3 (Anthropic),
common schema adapter, synthetic smoke builders, secret hygiene checks,
and read-only opening-hours catalog coverage audit.
"""
from typing import Dict

from app.evaluation.model_preflight.anthropic_adapter import AnthropicPreflightAdapter
from app.evaluation.model_preflight.base import (
    FROZEN_ARCHITECTURE_CLASS,
    FROZEN_ARCHITECTURE_ID,
    FROZEN_MAX_OUTPUT_TOKENS,
    FROZEN_SAMPLING_SEED,
    FROZEN_SAMPLING_TEMPERATURE,
    FROZEN_TIMEOUT_MS,
    PREFLIGHT_SHARED_SYSTEM_PROMPT,
    REQUIRED_ENV_KEY_NAMES,
    SYNTHETIC_SMOKE_SCENARIO_IDS,
    W06_PREFLIGHT_LIVE_ALLOWED_DEFAULT,
    BasePreflightProviderAdapter,
    build_shared_semantic_user_prompt,
    build_synthetic_smoke_fixtures,
    build_synthetic_valid_plan_json,
    check_dotenv_key_presence,
    enforce_offline_preflight_guard,
    is_preflight_live_allowed,
    run_readonly_opening_hours_catalog_audit,
    scan_tracked_files_for_secret_leaks,
    verify_model_metadata_integrity,
)
from app.evaluation.model_preflight.google_adapter import GooglePreflightAdapter
from app.evaluation.model_preflight.openai_adapter import OpenAIPreflightAdapter
from app.evaluation.model_preflight.schema_adapter import (
    COMMON_BENCHMARK_PLAN_JSON_SCHEMA,
    COMMON_SCHEMA_SHA256,
    build_anthropic_structured_output_wiring,
    build_common_benchmark_plan_json_schema,
    build_google_structured_output_wiring,
    build_openai_structured_output_wiring,
    compute_common_schema_sha256,
    schema_encodes_place_id_as_catalog_enum,
)
from app.evaluation.model_preflight.types import (
    CONFIGURATION_INTEGRITY_FAILURE_CODE,
    LIVE_PROVIDER_CALL_FORBIDDEN_CODE,
    ONE_CALL_INVARIANT_VIOLATION_CODE,
    CandidateModelMetadataCheckRecord,
    CandidatePreflightRecord,
    CandidateRetryConfigRecord,
    CapabilityVerificationStatus,
    ConfigurationIntegrityError,
    LiveProviderCallForbiddenError,
    OneCallInvariantViolationError,
    PreflightExecutionResult,
    PreflightFailureClassification,
    SamplingCapabilitySpec,
)


def build_all_candidate_preflight_adapters(
    *,
    live_allowed: bool | None = None,
) -> Dict[str, BasePreflightProviderAdapter]:
    """Instantiate all three frozen candidate preflight adapters (C1, C2, C3)."""
    return {
        "C1": GooglePreflightAdapter(live_allowed=live_allowed),
        "C2": OpenAIPreflightAdapter(live_allowed=live_allowed),
        "C3": AnthropicPreflightAdapter(live_allowed=live_allowed),
    }


__all__ = [
    "AnthropicPreflightAdapter",
    "BasePreflightProviderAdapter",
    "COMMON_BENCHMARK_PLAN_JSON_SCHEMA",
    "COMMON_SCHEMA_SHA256",
    "CONFIGURATION_INTEGRITY_FAILURE_CODE",
    "CandidateModelMetadataCheckRecord",
    "CandidatePreflightRecord",
    "CandidateRetryConfigRecord",
    "CapabilityVerificationStatus",
    "ConfigurationIntegrityError",
    "FROZEN_ARCHITECTURE_CLASS",
    "FROZEN_ARCHITECTURE_ID",
    "FROZEN_MAX_OUTPUT_TOKENS",
    "FROZEN_SAMPLING_SEED",
    "FROZEN_SAMPLING_TEMPERATURE",
    "FROZEN_TIMEOUT_MS",
    "GooglePreflightAdapter",
    "LIVE_PROVIDER_CALL_FORBIDDEN_CODE",
    "LiveProviderCallForbiddenError",
    "ONE_CALL_INVARIANT_VIOLATION_CODE",
    "OpenAIPreflightAdapter",
    "OneCallInvariantViolationError",
    "PREFLIGHT_SHARED_SYSTEM_PROMPT",
    "PreflightExecutionResult",
    "PreflightFailureClassification",
    "REQUIRED_ENV_KEY_NAMES",
    "SYNTHETIC_SMOKE_SCENARIO_IDS",
    "SamplingCapabilitySpec",
    "W06_PREFLIGHT_LIVE_ALLOWED_DEFAULT",
    "build_all_candidate_preflight_adapters",
    "build_anthropic_structured_output_wiring",
    "build_common_benchmark_plan_json_schema",
    "build_google_structured_output_wiring",
    "build_openai_structured_output_wiring",
    "build_shared_semantic_user_prompt",
    "build_synthetic_smoke_fixtures",
    "build_synthetic_valid_plan_json",
    "check_dotenv_key_presence",
    "compute_common_schema_sha256",
    "enforce_offline_preflight_guard",
    "is_preflight_live_allowed",
    "run_readonly_opening_hours_catalog_audit",
    "scan_tracked_files_for_secret_leaks",
    "schema_encodes_place_id_as_catalog_enum",
    "verify_model_metadata_integrity",
]
