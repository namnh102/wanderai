"""Evaluation-only types and strict invariants for W06 Model/Provider Technical Preflight (Phase 01A & 01B).

Grounded in W06-MODEL-ARCH-SELECTION-METHOD-LOCK-01 v1.0.0:
- Architecture: LLM_BASED_ITINERARY_PLANNER_WITH_DETERMINISTIC_GROUNDING_AND_VALIDATION_V1
- Direct 1-call architecture (llm_calls_per_execution = 1, model_initiated_tool_calls = 0, llm_repair_calls = 0)
- Zero automatic or transport retries (sdk_automatic_retry = 0, transport_retry = 0)
- Zero fallback or primary JSON repair (fallback = False, primary_json_repair = False)
- Offline runtime guard: W06_PREFLIGHT_LIVE_ALLOWED = False by default.
"""
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.planner_benchmark import BenchmarkPlanResponse, BenchmarkRunStatus, BenchmarkUsageMetadata

FROZEN_ARCHITECTURE_ID: str = (
    "LLM_BASED_ITINERARY_PLANNER_WITH_DETERMINISTIC_GROUNDING_AND_VALIDATION_V1"
)
FROZEN_ARCHITECTURE_CLASS: str = "DIRECT_ONE_CALL_PLUS_READ_ONLY_DETERMINISTIC_VALIDATION"
FROZEN_SAMPLING_SEED: int = 2026101508
FROZEN_SAMPLING_TEMPERATURE: float = 0.0
FROZEN_MAX_OUTPUT_TOKENS: int = 16384
FROZEN_TIMEOUT_MS: int = 55000
FROZEN_GOOGLE_THINKING_LEVEL: str = "medium"
FROZEN_OPENAI_REASONING_EFFORT: str = "medium"
FROZEN_OPENAI_SERVICE_TIER: str = "default"
FROZEN_CLAUDE_THINKING_MODE: str = "adaptive"
FROZEN_CLAUDE_EFFORT: str = "high"
FROZEN_LIVE_SMOKE_FIXTURE_ID: str = "W06-PREFLIGHT-SMOKE-001"
FROZEN_MAX_LIVE_GENERATION_CALLS_TOTAL: int = 3
FROZEN_MAX_LIVE_GENERATION_CALLS_PER_CANDIDATE: int = 1
FROZEN_MAX_CUMULATIVE_COST_USD: float = 1.00
LIVE_PROVIDER_CALL_FORBIDDEN_CODE: str = "LIVE_PROVIDER_CALL_FORBIDDEN"
CONFIGURATION_INTEGRITY_FAILURE_CODE: str = (
    "CONFIGURATION_INTEGRITY_FAILURE_STOP_BATCH_BEFORE_SCIENTIFIC_REPORTING"
)
ONE_CALL_INVARIANT_VIOLATION_CODE: str = "ONE_CALL_INVARIANT_VIOLATION"


class CapabilityVerificationStatus(str, Enum):
    """Allowed capability classification statuses for W06-MODEL-PREFLIGHT-01A-OFFLINE (Section 8)."""

    VERIFIED_BY_SDK_SURFACE = "VERIFIED_BY_SDK_SURFACE"
    VERIFIED_BY_OFFICIAL_DOC_REFERENCE = "VERIFIED_BY_OFFICIAL_DOC_REFERENCE"
    OFFLINE_TEST_VERIFIED = "OFFLINE_TEST_VERIFIED"
    PENDING_LIVE_CONFIRMATION = "PENDING_LIVE_CONFIRMATION"
    UNSUPPORTED = "UNSUPPORTED"
    UNKNOWN = "UNKNOWN"


class CandidateOfflineReadinessStatus(str, Enum):
    """Explicit offline readiness status per candidate before Phase 01B live preflight (Part I)."""

    READY_FOR_LIVE_PREFLIGHT = "READY_FOR_LIVE_PREFLIGHT"
    NOT_READY_FOR_LIVE_PREFLIGHT = "NOT_READY_FOR_LIVE_PREFLIGHT"


class CandidateFinalPreflightStatus(str, Enum):
    """Final technical preflight status per candidate at the end of Phase 01B (Section 20)."""

    PASSED_TECHNICAL_PREFLIGHT = "PASSED_TECHNICAL_PREFLIGHT"
    FAILED_TECHNICAL_PREFLIGHT = "FAILED_TECHNICAL_PREFLIGHT"


class LiveFailureClassification(str, Enum):
    """Deterministic failure classification for W06 Phase 01B live technical smoke preflight (Section 15)."""

    NONE = "NONE"
    PASS_LIVE_PREFLIGHT = "PASS_LIVE_PREFLIGHT"
    FAILED_AUTHENTICATION = "FAILED_AUTHENTICATION"
    FAILED_MODEL_ACCESS = "FAILED_MODEL_ACCESS"
    FAILED_MODEL_ID_INTEGRITY = "FAILED_MODEL_ID_INTEGRITY"
    FAILED_ENDPOINT_COMPATIBILITY = "FAILED_ENDPOINT_COMPATIBILITY"
    FAILED_PARAMETER_COMPATIBILITY = "FAILED_PARAMETER_COMPATIBILITY"
    FAILED_STRUCTURED_OUTPUT_COMPATIBILITY = "FAILED_STRUCTURED_OUTPUT_COMPATIBILITY"
    FAILED_SCHEMA_OUTPUT = "FAILED_SCHEMA_OUTPUT"
    FAILED_REFUSAL = "FAILED_REFUSAL"
    FAILED_MAX_TOKENS = "FAILED_MAX_TOKENS"
    FAILED_TIMEOUT = "FAILED_TIMEOUT"
    FAILED_HTTP_429 = "FAILED_HTTP_429"
    FAILED_HTTP_5XX = "FAILED_HTTP_5XX"
    FAILED_USAGE_METADATA = "FAILED_USAGE_METADATA"
    FAILED_SECRET_SAFETY = "FAILED_SECRET_SAFETY"
    HARNESS_ERROR = "HARNESS_ERROR"


class PreflightFailureClassification(str, Enum):
    """Deterministic failure classification for W06 preflight and benchmark adapters (Section 10)."""

    NONE = "NONE"
    LIVE_PROVIDER_CALL_FORBIDDEN = "LIVE_PROVIDER_CALL_FORBIDDEN"
    HTTP_429 = "HTTP_429"
    HTTP_5XX = "HTTP_5XX"
    TIMEOUT = "TIMEOUT"
    API_ERROR = "API_ERROR"
    REFUSAL = "REFUSAL"
    UNPARSABLE_MODEL_OUTPUT = "UNPARSABLE_MODEL_OUTPUT"
    SCHEMA_NONCOMPLIANT_OUTPUT = "SCHEMA_NONCOMPLIANT_OUTPUT"
    CONFIGURATION_INTEGRITY_FAILURE = "CONFIGURATION_INTEGRITY_FAILURE"
    ONE_CALL_INVARIANT_VIOLATION = "ONE_CALL_INVARIANT_VIOLATION"


class LiveProviderCallForbiddenError(RuntimeError):
    """Raised when any live network call is attempted while W06_PREFLIGHT_LIVE_ALLOWED is false."""

    def __init__(self, message: str = "Live provider API calls are strictly forbidden in Phase 01A offline preflight.") -> None:
        self.code = LIVE_PROVIDER_CALL_FORBIDDEN_CODE
        super().__init__(f"{self.code}: {message}")


class ConfigurationIntegrityError(RuntimeError):
    """Raised when returned/resolved model metadata does not match requested model ID or routes to fallback."""

    def __init__(
        self,
        *,
        candidate_id: str,
        requested_model_id: str,
        returned_model_id: Optional[str],
        detail: str,
    ) -> None:
        self.code = CONFIGURATION_INTEGRITY_FAILURE_CODE
        self.candidate_id = candidate_id
        self.requested_model_id = requested_model_id
        self.returned_model_id = returned_model_id
        super().__init__(
            f"{self.code} [{candidate_id}]: requested={requested_model_id!r}, "
            f"returned={returned_model_id!r} ({detail})"
        )


class OneCallInvariantViolationError(RuntimeError):
    """Raised if an adapter attempts >1 LLM call, any tool call, fallback, or repair call."""

    def __init__(self, detail: str) -> None:
        self.code = ONE_CALL_INVARIANT_VIOLATION_CODE
        super().__init__(f"{self.code}: {detail}")


class DocumentationProvenanceRecord(BaseModel):
    """Claim-specific official provider documentation provenance record (Part J)."""

    model_config = ConfigDict(extra="forbid")

    claim: str
    official_url: str
    access_date: str
    verification_scope: Literal[
        "MODEL_ID",
        "STRUCTURED_OUTPUT",
        "SAMPLING",
        "THINKING_REASONING",
        "MAX_OUTPUT",
        "ENDPOINT",
    ]


class SamplingCapabilitySpec(BaseModel):
    """Explicit per-parameter capability record differentiating SDK surface from model-specific support."""

    model_config = ConfigDict(extra="forbid")

    parameter_name: str
    sdk_parameter_name: Optional[str] = None
    sdk_parameter_status: Literal["SDK_PARAMETER_EXISTS", "SDK_PARAMETER_ABSENT"]
    model_specific_status: Literal[
        "MODEL_SPECIFIC_PARAMETER_CONFIRMED",
        "PENDING_LIVE_CONFIRMATION",
        "DEPRECATED_IGNORED_OMITTED",
        "OMITTED_FOR_REASONING_EFFORT",
        "OMITTED_NOT_SENT",
        "UNSUPPORTED",
    ]
    sent_in_request: bool
    configured_value: Any = None
    verification_status: CapabilityVerificationStatus
    notes: str


class CandidateRetryConfigRecord(BaseModel):
    """Explicit retry=0 technical proof record for a candidate adapter (Section 10)."""

    model_config = ConfigDict(extra="forbid")

    sdk_automatic_retry: int = 0
    transport_retry: int = 0
    sdk_retry_mechanism: str
    verification_status: CapabilityVerificationStatus = (
        CapabilityVerificationStatus.OFFLINE_TEST_VERIFIED
    )


class CandidateModelMetadataCheckRecord(BaseModel):
    """Returned/resolved model metadata inspection contract for a candidate adapter (Section 11)."""

    model_config = ConfigDict(extra="forbid")

    response_metadata_field: str
    verification_status: CapabilityVerificationStatus
    mismatch_policy: str = CONFIGURATION_INTEGRITY_FAILURE_CODE
    live_model_availability_status: CapabilityVerificationStatus = (
        CapabilityVerificationStatus.PENDING_LIVE_CONFIRMATION
    )


class CandidatePreflightRecord(BaseModel):
    """Machine-readable offline preflight record for a candidate model/provider (Sections 8–11, Parts D–J)."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    provider: str
    requested_model_id: str
    role: str = "CANDIDATE_NOT_SELECTED_FINAL_MODEL"
    offline_status: CandidateOfflineReadinessStatus
    blockers: List[str] = Field(default_factory=list)
    sdk_package: str
    sdk_version: str
    provider_documentation_url: str
    access_date: str
    documentation_provenance: List[DocumentationProvenanceRecord]
    endpoint_semantics: str
    endpoint_verification_status: CapabilityVerificationStatus
    live_model_id_status: CapabilityVerificationStatus = (
        CapabilityVerificationStatus.PENDING_LIVE_CONFIRMATION
    )
    structured_output_mode: str
    structured_output_wiring_summary: Dict[str, Any]
    structured_output_capability_status: CapabilityVerificationStatus
    semantic_schema_sha256: str
    common_generation_schema_sha256: str
    common_schema_sha256: str
    place_id_encoded_as_catalog_enum: bool = False
    sampling_capabilities: Dict[str, SamplingCapabilitySpec]
    retry_configuration: CandidateRetryConfigRecord
    model_metadata_check: CandidateModelMetadataCheckRecord
    architecture_invariants: Dict[str, Any]


class PreflightExecutionResult(BaseModel):
    """Result of executing a single 1-call offline simulated preflight request."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    provider: str
    requested_model_id: str
    returned_model_id: Optional[str] = None
    scenario_id: str
    run_id: str
    run_status: BenchmarkRunStatus
    failure_classification: PreflightFailureClassification
    request_attempt_count: int
    llm_calls_per_execution: int
    model_initiated_tool_calls: int
    llm_repair_calls: int
    fallback_called: bool
    primary_json_repair_called: bool
    raw_artifact_preserved: bool
    raw_response_text: Optional[str] = None
    raw_response_sha256: Optional[str] = None
    parsed_response: Optional[BenchmarkPlanResponse] = None
    parsed_response_sha256: Optional[str] = None
    usage_metadata: BenchmarkUsageMetadata = Field(default_factory=BenchmarkUsageMetadata)
    latency_ms: Optional[float] = None
    error_detail: Optional[str] = None
    legacy_recoverable_parse_diagnostic: Optional[bool] = None


class CandidateStandardPricingRecord(BaseModel):
    """Official standard pricing specification for Phase 01B live preflight cost accounting (Section 18)."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    provider: str
    model_id: str
    pricing_source_url: str
    pricing_access_date: str
    input_price_per_million: float
    output_price_per_million: float
    notes: str


class LiveUsageMetadataRecord(BaseModel):
    """Authoritative token usage metadata captured from live provider response (Section 17)."""

    model_config = ConfigDict(extra="forbid")

    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    reasoning_tokens: Optional[int] = None
    thought_tokens: Optional[int] = None
    cache_read_input_tokens: Optional[int] = None
    cache_creation_input_tokens: Optional[int] = None
    cached_content_token_count: Optional[int] = None
    authoritative_usage_available: bool = False


class LiveCandidateExecutionRecord(BaseModel):
    """Machine-readable execution record for a single candidate in W06-MODEL-PREFLIGHT-01B-LIVE-SMOKE."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    attempted: bool
    actual_http_request_count: int
    provider: str
    requested_model_id: str
    returned_model_id: Optional[str] = None
    resolved_model_version: Optional[str] = None
    system_fingerprint: Optional[str] = None
    service_tier: Optional[str] = None
    reasoning_effort: Optional[str] = None
    thinking_mode: Optional[str] = None
    effort: Optional[str] = None
    seed_acceptance_status: Optional[str] = None
    status: CandidateFinalPreflightStatus
    live_preflight_status: str
    failure_classification: LiveFailureClassification
    error_detail_sanitized: Optional[str] = None
    schema_valid: bool
    raw_artifact_preserved: bool
    raw_response_sha256: Optional[str] = None
    parsed_response_sha256: Optional[str] = None
    sanitization_occurred_in_raw_response: bool = False
    usage_metadata: LiveUsageMetadataRecord
    latency_ms: Optional[float] = None
    finish_or_stop_reason: Optional[str] = None
    pricing_source_url: str
    pricing_access_date: str
    input_price_per_million: float
    output_price_per_million: float
    authoritative_usage_available: bool
    estimated_standard_api_cost_usd: Optional[float] = None
    blockers: List[str] = Field(default_factory=list)
