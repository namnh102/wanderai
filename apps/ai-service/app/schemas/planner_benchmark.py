"""Strict benchmark-only schemas for W06 Itinerary Agent Evaluation (W06-INSTRUMENT-01A).

Grounded in W06-MEASUREMENT-CONTRACT-01 v1.1.0 (7fd5364ed4671c06b0c911b6fd53bd9f54cbc322).
Does NOT modify production /planner schemas in apps/ai-service/app/schemas/planner.py.
"""
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ActivityKind(str, Enum):
    """Controlled itinerary activity universe frozen by W06-MEASUREMENT-CONTRACT-01 FIX-01C."""

    POI_VISIT = "POI_VISIT"
    TRANSIT_ONLY = "TRANSIT_ONLY"


class BenchmarkRunStatus(str, Enum):
    """Execution/instrumentation status vocabulary for W06 benchmark runs."""

    VALID = "VALID"
    LIVE_PROVIDER_REQUIRED = "LIVE_PROVIDER_REQUIRED"
    MOCK_OR_FALLBACK_RUN = "MOCK_OR_FALLBACK_RUN"
    API_ERROR = "API_ERROR"
    UNPARSABLE_MODEL_OUTPUT = "UNPARSABLE_MODEL_OUTPUT"
    MODEL_ID_MISMATCH = "MODEL_ID_MISMATCH"
    SCHEMA_NONCOMPLIANT_OUTPUT = "SCHEMA_NONCOMPLIANT_OUTPUT"
    MISSING_REQUIRED_RUN_METADATA = "MISSING_REQUIRED_RUN_METADATA"


CANONICAL_BENCHMARK_INTERESTS: tuple[str, ...] = (
    "food_cuisine",
    "culture_history",
    "nature_outdoor",
    "coffee_culture",
    "beach_island",
    "shopping_local",
    "nightlife_entertainment",
)

PRIMARY_BENCHMARK_DESTINATIONS: Dict[str, str] = {
    "ha-noi": "Hà Nội",
    "da-nang": "Đà Nẵng",
    "ha-long": "Hạ Long",
}

EXPECTED_PRIMARY_CATALOG_COUNTS: Dict[str, int] = {
    "ha-noi": 145,
    "da-nang": 289,
    "ha-long": 188,
}


class BenchmarkCatalogPOI(BaseModel):
    """Deterministic REC-A-CORE-V2 catalog entry exposed to the benchmark prompt."""

    model_config = ConfigDict(extra="forbid")

    place_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    category: str = Field(..., min_length=1)
    destination_slug: str = Field(..., min_length=1)
    lat: Optional[float] = None
    lng: Optional[float] = None
    opening_hours: Optional[str] = None


class BenchmarkScenarioInput(BaseModel):
    """Validated scientific scenario input for W06 benchmark planning."""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str = Field(..., min_length=1)
    destination_slug: str = Field(..., min_length=1)
    destination: str = Field(..., min_length=1)
    days: int = Field(..., ge=1, le=14)
    start_date: str = Field(..., min_length=1)
    end_date: str = Field(..., min_length=1)
    budget: Optional[int] = Field(default=None, ge=0)
    currency: str = "VND"
    travel_style: str = Field(..., min_length=1)
    interests: List[str] = Field(..., min_length=1)
    notes: Optional[str] = None
    allow_revisit_place_ids: bool = False
    fixture_label: Optional[str] = None

    @field_validator("destination_slug")
    @classmethod
    def validate_primary_destination_slug(cls, v: str) -> str:
        slug = v.strip()
        if slug not in PRIMARY_BENCHMARK_DESTINATIONS:
            raise ValueError(
                f"Unsupported or non-primary benchmark destination_slug '{v}'. "
                f"Allowed primary destinations: {sorted(PRIMARY_BENCHMARK_DESTINATIONS.keys())}"
            )
        return slug

    @field_validator("interests")
    @classmethod
    def validate_canonical_interests(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("Benchmark scenario must specify at least one canonical interest.")
        invalid = [item for item in v if item not in CANONICAL_BENCHMARK_INTERESTS]
        if invalid:
            raise ValueError(
                f"Non-canonical interest keys rejected: {invalid}. "
                f"Allowed canonical taxonomy: {list(CANONICAL_BENCHMARK_INTERESTS)}"
            )
        return v


class BenchmarkItineraryItem(BaseModel):
    """Strict benchmark itinerary item enforcing POI_VISIT vs TRANSIT_ONLY contract rules."""

    model_config = ConfigDict(extra="forbid")

    order_index: int = Field(..., ge=1)
    start_time: str = Field(..., min_length=1)
    end_time: str = Field(..., min_length=1)
    activity_kind: ActivityKind = Field(...)
    activity: str = Field(..., min_length=1)
    place_name: Optional[str] = Field(...)
    place_id: Optional[str] = Field(...)
    notes: Optional[str] = Field(...)
    estimated_cost: int = Field(..., ge=0)
    transport_mode: Optional[str] = Field(...)

    @model_validator(mode="after")
    def validate_activity_kind_and_place_id_semantics(self) -> "BenchmarkItineraryItem":
        if self.activity_kind == ActivityKind.POI_VISIT:
            if self.place_id is None or not str(self.place_id).strip():
                raise ValueError(
                    "POI_VISIT item requires a non-empty canonical place_id; "
                    "missing or blank place_id is rejected."
                )
            if self.place_name is None or not str(self.place_name).strip():
                raise ValueError(
                    "POI_VISIT item requires a non-empty place_name corresponding to the catalog entry."
                )
            self.place_id = str(self.place_id).strip()
            self.place_name = str(self.place_name).strip()
        elif self.activity_kind == ActivityKind.TRANSIT_ONLY:
            if self.place_id is not None:
                raise ValueError(
                    f"TRANSIT_ONLY item must have place_id=null (got {self.place_id!r})."
                )
        return self


class BenchmarkItineraryDay(BaseModel):
    """Strict benchmark itinerary day."""

    model_config = ConfigDict(extra="forbid")

    day_number: int = Field(..., ge=1)
    date: Optional[str] = None
    title: str = Field(..., min_length=1)
    items: List[BenchmarkItineraryItem] = Field(..., min_length=1)
    day_cost: int = Field(default=0, ge=0)


class BenchmarkBudgetAnalysis(BaseModel):
    """Deterministic budget summary for a benchmark itinerary response."""

    model_config = ConfigDict(extra="forbid")

    total_budget: Optional[int] = None
    estimated_cost: int = 0
    currency: str = "VND"
    is_over_budget: bool = False
    variance: int = 0


class BenchmarkPlanResponse(BaseModel):
    """Strict parsed benchmark plan response persisted as parsed_plan_response.json."""

    model_config = ConfigDict(extra="forbid")

    plan_id: str = Field(..., min_length=1)
    scenario_id: str = Field(..., min_length=1)
    destination_slug: str = Field(..., min_length=1)
    destination: str = Field(..., min_length=1)
    total_days: int = Field(..., ge=1, le=14)
    overview: str = Field(..., min_length=1)
    best_time_to_visit: str = Field(..., min_length=1)
    general_tips: List[str] = []
    budget_analysis: BenchmarkBudgetAnalysis
    days: List[BenchmarkItineraryDay] = Field(..., min_length=1)


class BenchmarkUsageMetadata(BaseModel):
    """Nullable authoritative provider token usage metadata (never estimated from string length)."""

    model_config = ConfigDict(extra="forbid")

    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None


HASH_BASIS_VERSION: str = "W06-ARTIFACT-HASH-BASIS-V1"

HASH_BASIS_BY_ARTIFACT: Dict[str, str] = {
    "RAW_PROVIDER_RESPONSE": "SHA256_EXACT_PERSISTED_UTF8_BYTES",
    "BENCHMARK_PROMPT": "SHA256_EXACT_PERSISTED_UTF8_BYTES",
    "SCENARIO_INPUT": "SHA256_CANONICAL_JSON_UTF8_LF_BYTES",
    "PARSED_PLAN_RESPONSE": "SHA256_CANONICAL_JSON_UTF8_LF_BYTES",
    "RUN_MANIFEST": "SHA256_CANONICAL_JSON_UTF8_LF_BYTES",
    "CATALOG_CONTEXT": "SHA256_CANONICAL_JSON_UTF8_LF_BYTES",
    "SOURCE_CATALOG": "SHA256_LF_NORMALIZED_SOURCE_BYTES",
    "PREPARATION_MANIFEST": "SHA256_CANONICAL_JSON_UTF8_LF_BYTES",
}

MANIFEST_HASH_FIELD_TO_ARTIFACT_MAP: Dict[str, str] = {
    "scenario_sha256": "SCENARIO_INPUT",
    "catalog_sha256": "SOURCE_CATALOG",
    "raw_response_sha256": "RAW_PROVIDER_RESPONSE",
    "parsed_response_sha256": "PARSED_PLAN_RESPONSE",
}

NORMALIZED_TOKEN_USAGE_FIELDS: tuple[str, ...] = (
    "input_tokens",
    "output_tokens",
    "total_tokens",
)


class BenchmarkRunManifest(BaseModel):
    """Deterministic cryptographic run manifest for W06 benchmark executions."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    scenario_id: str
    execution_timestamp_utc: str
    provider: str
    model_id: str
    expected_model_id: Optional[str] = None
    generation_parameters: Dict[str, Any]
    execution_mode: str
    latency_ms: Optional[float] = None
    usage_metadata: BenchmarkUsageMetadata
    code_commit_sha: str
    scenario_sha256: str
    catalog_sha256: str
    benchmark_prompt_version: str
    raw_response_sha256: Optional[str] = None
    parsed_response_sha256: Optional[str] = None
    measurement_contract_id: str = "W06-MEASUREMENT-CONTRACT-01"
    measurement_contract_version: str = "1.1.0"
    measurement_contract_source_commit: str = "7fd5364ed4671c06b0c911b6fd53bd9f54cbc322"
    hash_basis_version: str = HASH_BASIS_VERSION
    hash_basis_by_artifact: Dict[str, str] = Field(
        default_factory=lambda: dict(HASH_BASIS_BY_ARTIFACT)
    )
    claims_bitwise_model_determinism: bool = False
    run_status: BenchmarkRunStatus
    error_detail: Optional[str] = None
