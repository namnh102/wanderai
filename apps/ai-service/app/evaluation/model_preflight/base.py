"""Base offline provider preflight adapter, one-call invariant enforcement, synthetic smoke fixtures,
secret hygiene checks, and read-only opening-hours catalog audit (W06-MODEL-PREFLIGHT-01A-OFFLINE).
"""
from abc import ABC, abstractmethod
import json
import os
from pathlib import Path
import re
import subprocess
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from pydantic import ValidationError

from app.evaluation.model_preflight.schema_adapter import (
    COMMON_BENCHMARK_PLAN_JSON_SCHEMA,
    COMMON_SCHEMA_SHA256,
    schema_encodes_place_id_as_catalog_enum,
)
from app.evaluation.model_preflight.types import (
    CONFIGURATION_INTEGRITY_FAILURE_CODE,
    FROZEN_ARCHITECTURE_CLASS,
    FROZEN_ARCHITECTURE_ID,
    FROZEN_MAX_OUTPUT_TOKENS,
    FROZEN_SAMPLING_SEED,
    FROZEN_SAMPLING_TEMPERATURE,
    FROZEN_TIMEOUT_MS,
    CandidatePreflightRecord,
    ConfigurationIntegrityError,
    LiveProviderCallForbiddenError,
    OneCallInvariantViolationError,
    PreflightExecutionResult,
    PreflightFailureClassification,
)
from app.evaluation.opening_hours_evaluator import (
    OPENING_HOURS_PARSER_VERSION,
    build_opening_hours_parser_coverage_report,
)
from app.prompts.planner_benchmark_prompt import (
    BENCHMARK_PROMPT_VERSION,
    DEFAULT_CATALOG_PATH,
    REPO_ROOT,
)
from app.schemas.planner_benchmark import (
    BenchmarkCatalogPOI,
    BenchmarkPlanResponse,
    BenchmarkRunStatus,
    BenchmarkScenarioInput,
    BenchmarkUsageMetadata,
)
from app.services.planner_benchmark_runner import (
    canonical_json_bytes,
    clean_benchmark_json_response,
    compute_catalog_sha256,
    parse_strict_benchmark_plan_response,
    sha256_bytes,
    write_canonical_json,
    write_exact_utf8_text,
)

W06_PREFLIGHT_LIVE_ALLOWED_DEFAULT: bool = False

PREFLIGHT_SHARED_SYSTEM_PROMPT: str = (
    "You are the W06 Benchmark Itinerary Planner operating under architecture "
    "LLM_BASED_ITINERARY_PLANNER_WITH_DETERMINISTIC_GROUNDING_AND_VALIDATION_V1. "
    "Return strictly one JSON object conforming to BenchmarkPlanResponse with zero markdown fences "
    "and zero tool calls."
)

SYNTHETIC_SMOKE_SCENARIO_IDS: Tuple[str, str] = (
    "W06-PREFLIGHT-SMOKE-001",
    "W06-PREFLIGHT-SMOKE-002",
)

REQUIRED_ENV_KEY_NAMES: Tuple[str, str, str] = (
    "GEMINI_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
)

# Redacted secret-pattern detectors (matched values are NEVER logged or returned)
_SECRET_LEAK_PATTERNS: Tuple[re.Pattern[str], ...] = (
    re.compile(r"AIza[0-9A-Za-z\-_]{35}"),
    re.compile(r"sk-ant-[0-9A-Za-z\-_]{20,}"),
    re.compile(r"sk-proj-[0-9A-Za-z\-_]{20,}"),
    re.compile(r"sk-[0-9A-Za-z]{32,}"),
)


def is_preflight_live_allowed(explicit_flag: Optional[bool] = None) -> bool:
    """Return True only if Phase-01B live preflight is explicitly enabled."""
    if explicit_flag is not None:
        return bool(explicit_flag)
    env_val = os.environ.get("W06_PREFLIGHT_LIVE_ALLOWED", "false").strip().lower()
    return env_val == "true"


def enforce_offline_preflight_guard(
    *,
    offline_simulated: bool,
    live_allowed_override: Optional[bool] = None,
) -> None:
    """Fail closed with LIVE_PROVIDER_CALL_FORBIDDEN if a live call is attempted while live mode is disabled."""
    if offline_simulated:
        return
    if not is_preflight_live_allowed(live_allowed_override):
        raise LiveProviderCallForbiddenError(
            "Attempted live provider execution while W06_PREFLIGHT_LIVE_ALLOWED is false."
        )


def build_synthetic_smoke_fixtures() -> List[Tuple[BenchmarkScenarioInput, List[BenchmarkCatalogPOI]]]:
    """Build synthetic technical smoke fixtures (W06-PREFLIGHT-SMOKE-001, W06-PREFLIGHT-SMOKE-002).

    Strictly isolated from:
    - data/evaluation/w06/w06_scenarios_freeze_v1.json (final 100 scenarios)
    - data/evaluation/w06/w06_dev_fixtures_freeze_v1.json (80 DEV fixtures)
    """
    smoke_1_scenario = BenchmarkScenarioInput(
        scenario_id="W06-PREFLIGHT-SMOKE-001",
        destination_slug="ha-noi",
        destination="Hà Nội",
        days=2,
        start_date="2026-11-02",
        end_date="2026-11-03",
        budget=4000000,
        currency="VND",
        travel_style="COMFORT",
        interests=["culture_history"],
        notes="Synthetic technical preflight smoke fixture 001 (non-benchmark, non-DEV).",
        allow_revisit_place_ids=False,
        fixture_label="SYNTHETIC_TECHNICAL_PREFLIGHT_SMOKE",
    )
    smoke_1_pois = [
        BenchmarkCatalogPOI(
            place_id="smoke-hn-poi-001",
            name="Synthetic Hanoi Heritage Museum",
            category="culture_history",
            destination_slug="ha-noi",
            lat=21.0285,
            lng=105.8542,
            opening_hours="Mo-Su 08:00-17:00",
        ),
        BenchmarkCatalogPOI(
            place_id="smoke-hn-poi-002",
            name="Synthetic Hanoi Old Quarter Citadel",
            category="culture_history",
            destination_slug="ha-noi",
            lat=21.0352,
            lng=105.8401,
            opening_hours="Mo-Su 08:00-17:00",
        ),
    ]

    smoke_2_scenario = BenchmarkScenarioInput(
        scenario_id="W06-PREFLIGHT-SMOKE-002",
        destination_slug="da-nang",
        destination="Đà Nẵng",
        days=2,
        start_date="2026-11-09",
        end_date="2026-11-10",
        budget=3000000,
        currency="VND",
        travel_style="BUDGET",
        interests=["food_cuisine"],
        notes="Synthetic technical preflight smoke fixture 002 (non-benchmark, non-DEV).",
        allow_revisit_place_ids=False,
        fixture_label="SYNTHETIC_TECHNICAL_PREFLIGHT_SMOKE",
    )
    smoke_2_pois = [
        BenchmarkCatalogPOI(
            place_id="smoke-dn-poi-001",
            name="Synthetic Da Nang Riverside Market",
            category="food_cuisine",
            destination_slug="da-nang",
            lat=16.0678,
            lng=108.2208,
            opening_hours="Mo-Su 07:00-21:00",
        ),
        BenchmarkCatalogPOI(
            place_id="smoke-dn-poi-002",
            name="Synthetic Da Nang Coastal Noodle House",
            category="food_cuisine",
            destination_slug="da-nang",
            lat=16.0544,
            lng=108.2422,
            opening_hours="Mo-Su 07:00-21:00",
        ),
    ]
    return [
        (smoke_1_scenario, smoke_1_pois),
        (smoke_2_scenario, smoke_2_pois),
    ]


def build_shared_semantic_user_prompt(
    scenario: BenchmarkScenarioInput,
    catalog_pois: List[BenchmarkCatalogPOI],
) -> str:
    """Build deterministic provider-neutral user prompt for a preflight smoke fixture."""
    catalog_payload = [p.model_dump() for p in sorted(catalog_pois, key=lambda x: x.place_id)]
    catalog_sha = sha256_bytes(canonical_json_bytes(catalog_payload))
    catalog_json = json.dumps(catalog_payload, ensure_ascii=False, indent=2)
    interests_str = ", ".join(scenario.interests)
    budget_str = (
        f"{scenario.budget:,} {scenario.currency}"
        if scenario.budget is not None
        else "UNCONSTRAINED (null)"
    )
    return (
        f"[W06 SCIENTIFIC BENCHMARK PROMPT VERSION: {BENCHMARK_PROMPT_VERSION}]\n"
        f"[SOURCE CATALOG SHA256: {catalog_sha}]\n\n"
        f"SCENARIO CONSTRAINTS:\n"
        f"- scenario_id: {scenario.scenario_id}\n"
        f"- destination_slug: {scenario.destination_slug}\n"
        f"- destination: {scenario.destination}\n"
        f"- days: {scenario.days} ({scenario.start_date} to {scenario.end_date})\n"
        f"- budget: {budget_str}\n"
        f"- travel_style: {scenario.travel_style}\n"
        f"- canonical_interests: {interests_str}\n"
        f"- allow_revisit_place_ids: {str(scenario.allow_revisit_place_ids).lower()}\n\n"
        f"ALLOWED DETERMINISTIC CATALOG POIS ({len(catalog_payload)} entries):\n"
        f"{catalog_json}\n"
    )


def build_synthetic_valid_plan_json(
    scenario: BenchmarkScenarioInput,
    catalog_pois: List[BenchmarkCatalogPOI],
    *,
    plan_id: str = "preflight-plan-001",
) -> str:
    """Build a valid canonical JSON string conforming to BenchmarkPlanResponse for offline adapter verification."""
    p1 = catalog_pois[0]
    p2 = catalog_pois[1] if len(catalog_pois) > 1 else catalog_pois[0]
    days_list = []
    total_cost = 0
    for day_idx in range(scenario.days):
        day_num = day_idx + 1
        day_date = scenario.start_date if day_num == 1 else scenario.end_date
        day_cost = 300000
        total_cost += day_cost
        days_list.append(
            {
                "day_number": day_num,
                "date": day_date,
                "title": f"Day {day_num} in {scenario.destination}",
                "day_cost": day_cost,
                "items": [
                    {
                        "order_index": 1,
                        "start_time": "09:00",
                        "end_time": "11:00",
                        "activity_kind": "POI_VISIT",
                        "activity": f"Visit {p1.name}",
                        "place_name": p1.name,
                        "place_id": p1.place_id,
                        "notes": "Morning visit",
                        "estimated_cost": 150000,
                        "transport_mode": "taxi",
                    },
                    {
                        "order_index": 2,
                        "start_time": "14:00",
                        "end_time": "16:00",
                        "activity_kind": "POI_VISIT",
                        "activity": f"Visit {p2.name}",
                        "place_name": p2.name,
                        "place_id": p2.place_id,
                        "notes": "Afternoon visit",
                        "estimated_cost": 150000,
                        "transport_mode": "walk",
                    },
                ],
            }
        )
    budget_val = scenario.budget
    variance_val = (budget_val - total_cost) if budget_val is not None else 0
    payload = {
        "plan_id": plan_id,
        "scenario_id": scenario.scenario_id,
        "destination_slug": scenario.destination_slug,
        "destination": scenario.destination,
        "total_days": scenario.days,
        "overview": f"Synthetic preflight itinerary for {scenario.destination}.",
        "best_time_to_visit": "October to April",
        "general_tips": ["Carry water", "Respect local hours"],
        "budget_analysis": {
            "total_budget": budget_val,
            "estimated_cost": total_cost,
            "currency": scenario.currency,
            "is_over_budget": bool(budget_val is not None and total_cost > budget_val),
            "variance": variance_val,
        },
        "days": days_list,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def verify_model_metadata_integrity(
    *,
    candidate_id: str,
    requested_model_id: str,
    returned_model_id: Optional[str],
    raise_on_mismatch: bool = False,
) -> Tuple[bool, Optional[str]]:
    """Verify returned/resolved model metadata against requested model ID (Section 11).

    Never silently accepts a different model or fallback model.
    Returns (is_valid, error_detail).
    """
    req = (requested_model_id or "").strip()
    ret = (returned_model_id or "").strip()
    if not ret:
        detail = (
            f"{CONFIGURATION_INTEGRITY_FAILURE_CODE}: Provider response did not expose "
            f"returned model metadata for requested model {req!r}."
        )
        if raise_on_mismatch:
            raise ConfigurationIntegrityError(
                candidate_id=candidate_id,
                requested_model_id=req,
                returned_model_id=returned_model_id,
                detail=detail,
            )
        return False, detail

    # Exact match or official date/version snapshot suffix of the exact requested model (e.g., model-id-2026...)
    is_exact_or_snapshot = (ret == req) or ret.startswith(f"{req}-")
    if not is_exact_or_snapshot:
        detail = (
            f"{CONFIGURATION_INTEGRITY_FAILURE_CODE}: Returned model {ret!r} does not match "
            f"requested model {req!r}; silent routing or fallback is forbidden."
        )
        if raise_on_mismatch:
            raise ConfigurationIntegrityError(
                candidate_id=candidate_id,
                requested_model_id=req,
                returned_model_id=returned_model_id,
                detail=detail,
            )
        return False, detail

    return True, None


class BasePreflightProviderAdapter(ABC):
    """Common evaluation-only base adapter for W06 candidate models (C1, C2, C3).

    Enforces:
    - Live call guard (W06_PREFLIGHT_LIVE_ALLOWED = False by default)
    - One-call invariant (llm_calls_per_execution = 1, tool_calls = 0, repair = 0, fallback = False)
    - Retry = 0 (sdk_automatic_retry = 0, transport_retry = 0)
    - Strict primary JSON parsing without calling clean_benchmark_json_response
    """

    candidate_id: str
    provider_name: str
    requested_model_id: str
    sdk_package: str
    sdk_version: str

    def __init__(self, *, live_allowed: Optional[bool] = None) -> None:
        self._live_allowed = live_allowed
        if schema_encodes_place_id_as_catalog_enum(COMMON_BENCHMARK_PLAN_JSON_SCHEMA):
            raise ValueError("Invariant violation: place_id must never be encoded as a catalog enum.")

    @abstractmethod
    def get_preflight_record(self) -> CandidatePreflightRecord:
        """Return the machine-readable offline preflight record for this candidate."""

    @abstractmethod
    def serialize_smoke_request(
        self,
        scenario: BenchmarkScenarioInput,
        catalog_pois: List[BenchmarkCatalogPOI],
    ) -> Dict[str, Any]:
        """Serialize the exact SDK request payload for a synthetic smoke fixture without network I/O."""

    @abstractmethod
    def _invoke_single_sdk_call_with_transport(
        self,
        *,
        request_payload: Dict[str, Any],
        mock_transport: Any,
    ) -> Tuple[Optional[str], Optional[str], BenchmarkUsageMetadata, bool]:
        """Execute exactly 1 SDK request using the provided offline mock transport.

        Returns (raw_response_text, returned_model_id, usage_metadata, is_refusal).
        """

    def execute_offline_simulated_request(
        self,
        *,
        scenario: BenchmarkScenarioInput,
        catalog_pois: List[BenchmarkCatalogPOI],
        mock_transport: Optional[Any],
        request_counter: Callable[[], int],
        output_dir: Optional[Path] = None,
        run_id: str = "preflight-offline-run-001",
        simulated_call_count: int = 1,
        simulated_tool_calls: int = 0,
        simulated_repair_calls: int = 0,
        simulated_fallback: bool = False,
        raise_on_integrity_failure: bool = False,
    ) -> PreflightExecutionResult:
        """Execute a single offline preflight request under strict 1-call and retry=0 invariants."""
        # Guard 1: Enforce live call guard when no offline mock_transport is supplied
        enforce_offline_preflight_guard(
            offline_simulated=(mock_transport is not None),
            live_allowed_override=self._live_allowed,
        )

        # Guard 2: Enforce 1-call architecture invariants before execution
        if simulated_call_count != 1:
            raise OneCallInvariantViolationError(
                f"llm_calls_per_execution must equal 1 (got {simulated_call_count})."
            )
        if simulated_tool_calls != 0:
            raise OneCallInvariantViolationError(
                f"model_initiated_tool_calls must equal 0 (got {simulated_tool_calls})."
            )
        if simulated_repair_calls != 0:
            raise OneCallInvariantViolationError(
                f"llm_repair_calls must equal 0 (got {simulated_repair_calls})."
            )
        if simulated_fallback:
            raise OneCallInvariantViolationError("fallback model/provider execution is forbidden.")

        request_payload = self.serialize_smoke_request(scenario, catalog_pois)
        t_start = time.perf_counter()
        try:
            raw_text, returned_model_id, usage, is_refusal = (
                self._invoke_single_sdk_call_with_transport(
                    request_payload=request_payload,
                    mock_transport=mock_transport,
                )
            )
        except Exception as exc:
            t_end = time.perf_counter()
            latency_ms = round((t_end - t_start) * 1000.0, 3)
            attempts = request_counter()
            classification = self._classify_transport_or_sdk_exception(exc)
            return PreflightExecutionResult(
                candidate_id=self.candidate_id,
                provider=self.provider_name,
                requested_model_id=self.requested_model_id,
                returned_model_id=None,
                scenario_id=scenario.scenario_id,
                run_id=run_id,
                run_status=BenchmarkRunStatus.API_ERROR,
                failure_classification=classification,
                request_attempt_count=attempts,
                llm_calls_per_execution=1,
                model_initiated_tool_calls=0,
                llm_repair_calls=0,
                fallback_called=False,
                primary_json_repair_called=False,
                raw_artifact_preserved=False,
                latency_ms=latency_ms,
                error_detail=f"{type(exc).__name__}: {exc}",
            )

        t_end = time.perf_counter()
        latency_ms = round((t_end - t_start) * 1000.0, 3)
        attempts = request_counter()

        raw_str = raw_text if isinstance(raw_text, str) else ""
        raw_sha256 = sha256_bytes(raw_str.encode("utf-8"))
        if output_dir is not None:
            output_dir.mkdir(parents=True, exist_ok=True)
            write_exact_utf8_text(output_dir / "raw_provider_response.txt", raw_str)

        # Model metadata integrity check (Section 11)
        model_ok, model_err = verify_model_metadata_integrity(
            candidate_id=self.candidate_id,
            requested_model_id=self.requested_model_id,
            returned_model_id=returned_model_id,
            raise_on_mismatch=raise_on_integrity_failure,
        )
        if not model_ok:
            return PreflightExecutionResult(
                candidate_id=self.candidate_id,
                provider=self.provider_name,
                requested_model_id=self.requested_model_id,
                returned_model_id=returned_model_id,
                scenario_id=scenario.scenario_id,
                run_id=run_id,
                run_status=BenchmarkRunStatus.MODEL_ID_MISMATCH,
                failure_classification=PreflightFailureClassification.CONFIGURATION_INTEGRITY_FAILURE,
                request_attempt_count=attempts,
                llm_calls_per_execution=1,
                model_initiated_tool_calls=0,
                llm_repair_calls=0,
                fallback_called=False,
                primary_json_repair_called=False,
                raw_artifact_preserved=True,
                raw_response_text=raw_str,
                raw_response_sha256=raw_sha256,
                usage_metadata=usage,
                latency_ms=latency_ms,
                error_detail=model_err,
            )

        # Refusal check (Section 10)
        if is_refusal:
            return PreflightExecutionResult(
                candidate_id=self.candidate_id,
                provider=self.provider_name,
                requested_model_id=self.requested_model_id,
                returned_model_id=returned_model_id,
                scenario_id=scenario.scenario_id,
                run_id=run_id,
                run_status=BenchmarkRunStatus.UNPARSABLE_MODEL_OUTPUT,
                failure_classification=PreflightFailureClassification.REFUSAL,
                request_attempt_count=attempts,
                llm_calls_per_execution=1,
                model_initiated_tool_calls=0,
                llm_repair_calls=0,
                fallback_called=False,
                primary_json_repair_called=False,
                raw_artifact_preserved=True,
                raw_response_text=raw_str,
                raw_response_sha256=raw_sha256,
                usage_metadata=usage,
                latency_ms=latency_ms,
                error_detail="Provider returned refusal response without a valid JSON plan.",
            )

        # Primary parse path: strict json.loads WITHOUT calling clean_benchmark_json_response
        try:
            decoded_json = json.loads(raw_str)
        except json.JSONDecodeError as exc:
            # Diagnostic-only check: could legacy cleaner have recovered it? Never affects primary status!
            legacy_recoverable = False
            try:
                cleaned = clean_benchmark_json_response(raw_str)
                json.loads(cleaned)
                legacy_recoverable = True
            except Exception:
                legacy_recoverable = False

            return PreflightExecutionResult(
                candidate_id=self.candidate_id,
                provider=self.provider_name,
                requested_model_id=self.requested_model_id,
                returned_model_id=returned_model_id,
                scenario_id=scenario.scenario_id,
                run_id=run_id,
                run_status=BenchmarkRunStatus.UNPARSABLE_MODEL_OUTPUT,
                failure_classification=PreflightFailureClassification.UNPARSABLE_MODEL_OUTPUT,
                request_attempt_count=attempts,
                llm_calls_per_execution=1,
                model_initiated_tool_calls=0,
                llm_repair_calls=0,
                fallback_called=False,
                primary_json_repair_called=False,
                raw_artifact_preserved=True,
                raw_response_text=raw_str,
                raw_response_sha256=raw_sha256,
                usage_metadata=usage,
                latency_ms=latency_ms,
                error_detail=f"Primary strict JSON decode failed: {exc}",
                legacy_recoverable_parse_diagnostic=legacy_recoverable,
            )

        # Strict schema validation via BenchmarkPlanResponse and parse_strict_benchmark_plan_response
        try:
            BenchmarkPlanResponse.model_validate(decoded_json)
            parsed_plan = parse_strict_benchmark_plan_response(
                raw_data=decoded_json,
                scenario=scenario,
                plan_id=decoded_json.get("plan_id") or run_id,
            )
        except (ValidationError, ValueError, TypeError, KeyError) as exc:
            return PreflightExecutionResult(
                candidate_id=self.candidate_id,
                provider=self.provider_name,
                requested_model_id=self.requested_model_id,
                returned_model_id=returned_model_id,
                scenario_id=scenario.scenario_id,
                run_id=run_id,
                run_status=BenchmarkRunStatus.SCHEMA_NONCOMPLIANT_OUTPUT,
                failure_classification=PreflightFailureClassification.SCHEMA_NONCOMPLIANT_OUTPUT,
                request_attempt_count=attempts,
                llm_calls_per_execution=1,
                model_initiated_tool_calls=0,
                llm_repair_calls=0,
                fallback_called=False,
                primary_json_repair_called=False,
                raw_artifact_preserved=True,
                raw_response_text=raw_str,
                raw_response_sha256=raw_sha256,
                usage_metadata=usage,
                latency_ms=latency_ms,
                error_detail=f"Strict BenchmarkPlanResponse validation failed: {exc}",
            )

        parsed_sha256 = sha256_bytes(canonical_json_bytes(parsed_plan.model_dump()))
        if output_dir is not None:
            write_canonical_json(output_dir / "parsed_plan_response.json", parsed_plan.model_dump())

        return PreflightExecutionResult(
            candidate_id=self.candidate_id,
            provider=self.provider_name,
            requested_model_id=self.requested_model_id,
            returned_model_id=returned_model_id,
            scenario_id=scenario.scenario_id,
            run_id=run_id,
            run_status=BenchmarkRunStatus.VALID,
            failure_classification=PreflightFailureClassification.NONE,
            request_attempt_count=attempts,
            llm_calls_per_execution=1,
            model_initiated_tool_calls=0,
            llm_repair_calls=0,
            fallback_called=False,
            primary_json_repair_called=False,
            raw_artifact_preserved=True,
            raw_response_text=raw_str,
            raw_response_sha256=raw_sha256,
            parsed_response=parsed_plan,
            parsed_response_sha256=parsed_sha256,
            usage_metadata=usage,
            latency_ms=latency_ms,
            legacy_recoverable_parse_diagnostic=False,
        )

    @staticmethod
    def _classify_transport_or_sdk_exception(exc: Exception) -> PreflightFailureClassification:
        """Deterministically classify SDK/transport exceptions into HTTP_429, HTTP_5XX, TIMEOUT, or API_ERROR."""
        cls_name = type(exc).__name__.lower()
        msg = str(exc).lower()
        status_code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
        if "timeout" in cls_name or "timed out" in msg or "timeout" in msg:
            return PreflightFailureClassification.TIMEOUT
        if status_code == 429 or "ratelimit" in cls_name or "429" in msg or "resource_exhausted" in msg:
            return PreflightFailureClassification.HTTP_429
        if (isinstance(status_code, int) and 500 <= status_code <= 599) or "internalserver" in cls_name or "500" in msg:
            return PreflightFailureClassification.HTTP_5XX
        return PreflightFailureClassification.API_ERROR

    @staticmethod
    def common_architecture_invariants() -> Dict[str, Any]:
        """Return frozen architecture invariants shared across all candidate adapters."""
        return {
            "architecture_id": FROZEN_ARCHITECTURE_ID,
            "architecture_class": FROZEN_ARCHITECTURE_CLASS,
            "llm_calls_per_execution": 1,
            "model_initiated_tool_calls": 0,
            "llm_repair_calls": 0,
            "fallback": False,
            "primary_json_repair": False,
            "raw_provider_response_preserved": True,
            "common_schema_sha256": COMMON_SCHEMA_SHA256,
            "sampling_seed_policy": FROZEN_SAMPLING_SEED,
            "sampling_temperature_policy": FROZEN_SAMPLING_TEMPERATURE,
            "max_output_tokens": FROZEN_MAX_OUTPUT_TOKENS,
            "timeout_ms": FROZEN_TIMEOUT_MS,
        }


def check_dotenv_key_presence(dotenv_path: Optional[Path] = None) -> Dict[str, str]:
    """Check presence of GEMINI_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY in apps/ai-service/.env.

    SECURITY INVARIANT (Section 13):
    - Reports ONLY 'PRESENT' or 'MISSING'.
    - NEVER returns or logs key values, prefixes, suffixes, lengths, or hashes.
    """
    target_path = dotenv_path or (REPO_ROOT / "apps" / "ai-service" / ".env")
    found_keys: Dict[str, bool] = {k: False for k in REQUIRED_ENV_KEY_NAMES}

    if target_path.exists():
        for raw_line in target_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key_part, val_part = line.split("=", 1)
            key_name = key_part.strip()
            val_clean = val_part.strip().strip("'").strip('"').strip()
            if key_name in found_keys and bool(val_clean):
                found_keys[key_name] = True

    return {
        key_name: ("PRESENT" if found_keys[key_name] else "MISSING")
        for key_name in REQUIRED_ENV_KEY_NAMES
    }


def scan_tracked_files_for_secret_leaks(repo_root: Optional[Path] = None) -> Dict[str, Any]:
    """Scan all git-tracked files for secret patterns (Section 13).

    SECURITY INVARIANT:
    - Outputs ONLY secret_leak_count and affected_file_paths.
    - NEVER outputs matched strings or line contents.
    """
    root = repo_root or REPO_ROOT
    res = subprocess.run(
        ["git", "ls-files"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    tracked_files = [line.strip() for line in res.stdout.splitlines() if line.strip()]
    affected_paths: List[str] = []
    leak_count = 0

    for rel_path in tracked_files:
        file_path = root / rel_path
        if not file_path.is_file():
            continue
        try:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        file_matches = 0
        for pattern in _SECRET_LEAK_PATTERNS:
            matches = pattern.findall(text)
            if matches:
                file_matches += len(matches)
        if file_matches > 0:
            leak_count += file_matches
            affected_paths.append(rel_path)

    return {
        "secret_leak_count": leak_count,
        "affected_file_paths": sorted(affected_paths),
    }


def run_readonly_opening_hours_catalog_audit(
    catalog_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Run the authorized read-only opening-hours coverage audit over gomate_places_freeze_v2.json (Section 14).

    Authorized fields per w06_model_arch_selection_method_lock_v1.json:
    - total_reca_core_pois
    - known_opening_hours_count
    - unknown_opening_hours_count
    - coverage_rate
    - per_destination_coverage
    - catalog_sha256
    - parser_version
    """
    target = catalog_path or DEFAULT_CATALOG_PATH
    catalog_sha = compute_catalog_sha256(catalog_path=target)
    report = build_opening_hours_parser_coverage_report(catalog_path=target)

    total_core = int(report["total_core_pois"])
    raw_with_oh = int(report["core_with_opening_hours"])
    parser_supported = int(report["parser_supported_record_count"])
    parser_unsupported = int(report["parser_unsupported_record_count"])
    missing_raw_oh = total_core - raw_with_oh

    # Deterministically evaluable ('known' opening hours under conservative parser) vs 'unknown' (missing or unsupported syntax)
    known_count = parser_supported
    unknown_count = total_core - known_count
    coverage_rate = round(known_count / total_core, 6) if total_core > 0 else 0.0
    raw_presence_rate = round(raw_with_oh / total_core, 6) if total_core > 0 else 0.0

    per_dest_out: Dict[str, Dict[str, Any]] = {}
    for dest, counts in report["per_destination_coverage"].items():
        d_total = int(counts["total_core"])
        d_with_oh = int(counts["with_opening_hours"])
        d_sup = int(counts["parser_supported"])
        d_unsup = int(counts["parser_unsupported"])
        d_unknown = d_total - d_sup
        per_dest_out[dest] = {
            "total_reca_core_pois": d_total,
            "raw_opening_hours_present_count": d_with_oh,
            "raw_opening_hours_missing_count": d_total - d_with_oh,
            "known_opening_hours_count": d_sup,
            "parser_unsupported_opening_hours_count": d_unsup,
            "unknown_opening_hours_count": d_unknown,
            "coverage_rate": round(d_sup / d_total, 6) if d_total > 0 else 0.0,
            "raw_presence_rate": round(d_with_oh / d_total, 6) if d_total > 0 else 0.0,
        }

    return {
        "mode": "READ_ONLY_CATALOG_EVIDENCE_AUDIT",
        "reporting_role": "BENCHMARK_EVIDENCE_COVERAGE_ONLY",
        "target_catalog_path": "data/curated/gomate_places_freeze_v2.json",
        "catalog_sha256": catalog_sha,
        "parser_version": OPENING_HOURS_PARSER_VERSION,
        "total_reca_core_pois": total_core,
        "raw_opening_hours_present_count": raw_with_oh,
        "raw_opening_hours_missing_count": missing_raw_oh,
        "parser_supported_opening_hours_count": parser_supported,
        "parser_unsupported_opening_hours_count": parser_unsupported,
        "known_opening_hours_count": known_count,
        "unknown_opening_hours_count": unknown_count,
        "coverage_rate": coverage_rate,
        "raw_presence_rate": raw_presence_rate,
        "parser_supported_ratio_among_present": float(report["parser_supported_ratio"]),
        "per_destination_coverage": per_dest_out,
    }
