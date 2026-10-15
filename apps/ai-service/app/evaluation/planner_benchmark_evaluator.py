"""Deterministic Core & Opening-Hours Constraint Evaluator for W06 Itinerary Agent Benchmark (W06-INSTRUMENT-01B / 01C).

Grounded in:
- W06-MEASUREMENT-CONTRACT-01 v1.1.0 (data/evaluation/w06/w06_measurement_contract_v1.json)
- W06-INSTRUMENT-01A v1.1.0 (data/evaluation/w06/w06_instrument_01a_receipt_v1.json)
- W06-INSTRUMENT-01B v1.0.0 (data/evaluation/w06/w06_instrument_01b_receipt_v1.json)

Strict scientific rules:
- Deterministic only: no LLM calls, no fuzzy place-name matching, no web/API calls, no random operations.
- Evaluates conservative three-state OSM opening_hours (COMPLIANT / VIOLATION / UNKNOWN) for grounded POI_VISIT items.
- Enforces scenario day/date alignment (YYYY-MM-DD matching scenario.start_date..end_date) so missing/invalid dates
  cannot turn a known opening-hours constraint into a harmless pass.
- Computes both core_scenario_pass_pre_opening_hours and final evidence-conditional core_scenario_pass.
- Per-scenario schedule and budget severity fields are named schedule_violation_event_density and budget_overrun_fraction
  so they cannot be naively averaged across scenarios as batch violation rates.
- Haversine distance is strictly GEO_DISTANCE_PROXY (diagnostic only; excluded from core pass).
- No weighted composite score is produced.
"""
from collections import Counter
import datetime
import json
import math
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

from app.evaluation.opening_hours_evaluator import (
    OPENING_HOURS_PARSER_VERSION,
    OpeningHoursItemEvaluation,
    evaluate_poi_visit_opening_hours,
)
from app.prompts.planner_benchmark_prompt import DEFAULT_CATALOG_PATH
from app.schemas.planner_benchmark import (
    HASH_BASIS_VERSION,
    ActivityKind,
    BenchmarkCatalogPOI,
    BenchmarkPlanResponse,
    BenchmarkRunManifest,
    BenchmarkRunStatus,
    BenchmarkScenarioInput,
)
from app.services.planner_benchmark_runner import (
    MEASUREMENT_CONTRACT_ID,
    MEASUREMENT_CONTRACT_VERSION,
    canonical_json_bytes,
    compute_catalog_sha256,
    normalize_lf_bytes,
    sha256_bytes,
    write_canonical_json,
)

EVALUATOR_VERSION_01B: str = "W06-CORE-EVALUATOR-01B-V1.0.0"
EVALUATOR_VERSION: str = "W06-CORE-EVALUATOR-01C-V1.0.0"
INSTRUMENT_01A_RECEIPT_VERSION: str = "1.1.0"
INSTRUMENT_01B_RECEIPT_VERSION: str = "1.0.0"
OPENING_HOURS_STATUS_01B: str = "NOT_EVALUATED_IN_01B"
FINAL_CORE_PASS_STATUS_01B: str = "NOT_COMPUTED_IN_01B_REQUIRES_01C_OPENING_HOURS"
OPENING_HOURS_STATUS_01C: str = "EVALUATED"
FINAL_CORE_PASS_STATUS_01C: str = "COMPUTED_IN_01C"

MINIMUM_ITEMS_PER_DAY_CONTRACT_STATUS: str = "NOT_FORMALLY_FROZEN"
MINIMUM_ITEMS_PER_DAY_RULE_SOURCE: str = (
    "data/evaluation/w06/w06_measurement_contract_v1.json "
    "(DAY_STRUCTURE lists minimum_required_items_per_day without freezing a numeric constant > 1; "
    "apps/ai-service/app/schemas/planner_benchmark.py BenchmarkItineraryDay.items enforces min_length=1 "
    "and legacy data/evaluation/planner/evaluate_planner.py:L39 defaults min_items_per_day=1)"
)

STRICT_HHMM_PATTERN = re.compile(r"^(\d{2}):(\d{2})$")
STRICT_ISO_DATE_PATTERN = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
EARTH_RADIUS_KM: float = 6371.0


class ScenarioEvaluationResult(BaseModel):
    """Machine-readable deterministic evaluation output for a single W06 benchmark scenario run."""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    run_id: str
    destination_slug: str

    evaluation_status: str
    evidence_integrity_valid: bool
    run_valid: bool
    run_status: str

    poi_visit_item_count: int
    transit_only_item_count: int
    grounded_item_count: int
    ungrounded_item_count: int
    grounded_poi_rate: float
    all_pois_grounded: bool

    destination_correct_item_count: int
    destination_incorrect_item_count: int
    destination_correct_poi_rate: float
    scenario_destination_valid: bool

    duplicate_poi_violation_count: int
    duplicate_poi_violation_rate: float
    duplicate_poi_pass: bool

    transit_only_named_poi_violation_count: int
    transit_only_pass: bool

    day_count_expected: int
    day_count_actual: int
    day_count_pass: bool
    minimum_items_per_day_contract_status: str = MINIMUM_ITEMS_PER_DAY_CONTRACT_STATUS
    minimum_items_per_day_rule_source: str = MINIMUM_ITEMS_PER_DAY_RULE_SOURCE
    min_items_observed_per_day: int
    day_structure_pass: bool

    scenario_date_alignment_pass: bool
    scenario_date_alignment_status: str

    schedule_violation_count: int
    time_parse_invalid_count: int
    time_interval_invalid_count: int
    schedule_overlap_count: int
    schedule_violation_event_density: float
    schedule_pass: bool

    budget_status: str
    estimated_total_cost: int
    budget_ceiling: Optional[int] = None
    estimated_budget_compliant: Optional[bool] = None
    estimated_budget_violation_amount: Optional[int] = None
    budget_overrun_fraction: Optional[float] = None
    arithmetic_self_consistency: bool

    geo_leg_count: int
    total_geo_distance_proxy_km: float
    mean_leg_geo_distance_proxy_km: float
    max_leg_geo_distance_proxy_km: float

    opening_hours_status: str = OPENING_HOURS_STATUS_01C
    opening_hours_evidence_status: str = "NO_EVALUABLE_EVIDENCE"
    opening_hours_poi_visit_items: int = 0
    opening_hours_evaluable_items: int = 0
    opening_hours_compliant_items: int = 0
    opening_hours_known_violation_count: int = 0
    opening_hours_unknown_items: int = 0
    opening_hours_evidence_coverage: float = 0.0
    opening_hours_compliance_rate_on_evaluable_items: Optional[float] = None
    opening_hours_item_evaluations: List[OpeningHoursItemEvaluation] = Field(default_factory=list)
    opening_hours_parser_version: str = OPENING_HOURS_PARSER_VERSION

    final_core_scenario_pass_status: str = FINAL_CORE_PASS_STATUS_01C
    core_scenario_pass_pre_opening_hours: bool
    core_scenario_pass: bool
    failure_reasons: List[str] = Field(default_factory=list)

    measurement_contract_id: str = MEASUREMENT_CONTRACT_ID
    measurement_contract_version: str = MEASUREMENT_CONTRACT_VERSION
    instrument_01a_receipt_version: str = INSTRUMENT_01A_RECEIPT_VERSION
    instrument_01b_receipt_version: str = INSTRUMENT_01B_RECEIPT_VERSION
    source_run_manifest_sha256: str
    evaluator_version: str = EVALUATOR_VERSION
    evaluator_code_sha256: str
    catalog_sha256: str
    scenario_sha256: str
    parsed_response_sha256: Optional[str] = None
    hash_basis_version: str = HASH_BASIS_VERSION


def compute_evaluator_code_sha256() -> str:
    """Compute SHA256 over LF-normalized UTF-8 bytes of this evaluator module."""
    evaluator_path = Path(__file__).resolve()
    return sha256_bytes(normalize_lf_bytes(evaluator_path.read_bytes()))


def load_core_catalog_by_place_id(
    catalog_path: Optional[Path] = None,
) -> Dict[str, BenchmarkCatalogPOI]:
    """Load all 622 REC-A-CORE-V2 POIs from the frozen catalog indexed by canonical place_id."""
    target = catalog_path or DEFAULT_CATALOG_PATH
    if not target.exists():
        raise FileNotFoundError(f"Frozen POI catalog not found at {target}")

    raw_places: List[Dict[str, Any]] = json.loads(target.read_text(encoding="utf-8"))
    core_map: Dict[str, BenchmarkCatalogPOI] = {}
    for p in raw_places:
        if p.get("is_rec_a_core_v2") is True:
            pid = str(p["place_id"])
            core_map[pid] = BenchmarkCatalogPOI(
                place_id=pid,
                name=str(p["name"]),
                category=str(p["category"]),
                destination_slug=str(p["destination_slug"]),
                lat=float(p["latitude"]) if p.get("latitude") is not None else None,
                lng=float(p["longitude"]) if p.get("longitude") is not None else None,
                opening_hours=str(p["opening_hours"]) if p.get("opening_hours") is not None else None,
            )
    return core_map


def parse_strict_hhmm(value: Any) -> Optional[int]:
    """Strictly parse a 24-hour HH:MM string (00:00 through 23:59) into minutes since midnight.

    Returns None for any invalid format or out-of-range hour/minute.
    """
    if not isinstance(value, str):
        return None
    match = STRICT_HHMM_PATTERN.match(value)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2))
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return hour * 60 + minute


def parse_strict_iso_date(value: Any) -> Optional[datetime.date]:
    """Strictly parse a YYYY-MM-DD ISO date string."""
    if not isinstance(value, str):
        return None
    if not STRICT_ISO_DATE_PATTERN.match(value):
        return None
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        return None


def validate_scenario_date_alignment(
    scenario: BenchmarkScenarioInput,
    plan_response: BenchmarkPlanResponse,
) -> Tuple[bool, Dict[int, bool]]:
    """Validate that BenchmarkItineraryDay.date values are strict YYYY-MM-DD and align with scenario.start_date..end_date."""
    start_dt = parse_strict_iso_date(scenario.start_date)
    end_dt = parse_strict_iso_date(scenario.end_date)
    if start_dt is None or end_dt is None:
        return False, {}

    expected_end_dt = start_dt + datetime.timedelta(days=scenario.days - 1)
    scenario_dates_consistent = end_dt == expected_end_dt

    day_count_matches = len(plan_response.days) == scenario.days
    per_day_trusted: Dict[int, bool] = {}
    all_days_aligned = True

    for idx, day in enumerate(plan_response.days):
        expected_day_number = idx + 1
        expected_day_date = start_dt + datetime.timedelta(days=idx)
        parsed_day_date = parse_strict_iso_date(day.date)

        day_aligned = (
            day.day_number == expected_day_number
            and parsed_day_date is not None
            and parsed_day_date == expected_day_date
            and scenario_dates_consistent
        )
        per_day_trusted[idx] = day_aligned
        if not day_aligned:
            all_days_aligned = False

    overall_pass = scenario_dates_consistent and day_count_matches and all_days_aligned
    return overall_pass, per_day_trusted


def compute_haversine_geo_distance_proxy_km(
    lat1: float, lng1: float, lat2: float, lng2: float
) -> float:
    """Compute Haversine great-circle distance in km (GEO_DISTANCE_PROXY diagnostic only)."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = (
        math.sin(d_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * (math.sin(d_lambda / 2.0) ** 2)
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return EARTH_RADIUS_KM * c


def _build_non_evaluated_result(
    *,
    scenario: BenchmarkScenarioInput,
    run_manifest: BenchmarkRunManifest,
    evaluation_status: str,
    evidence_integrity_valid: bool,
    failure_reasons: List[str],
    source_run_manifest_sha256: str,
    evaluator_code_sha256: str,
    catalog_sha256: str,
    scenario_sha256: str,
    parsed_response_sha256: Optional[str],
) -> ScenarioEvaluationResult:
    """Build a fail-closed ScenarioEvaluationResult for INVALID_RUN or EVIDENCE_INTEGRITY_FAILURE."""
    return ScenarioEvaluationResult(
        scenario_id=scenario.scenario_id,
        run_id=run_manifest.run_id,
        destination_slug=scenario.destination_slug,
        evaluation_status=evaluation_status,
        evidence_integrity_valid=evidence_integrity_valid,
        run_valid=False,
        run_status=run_manifest.run_status.value,
        poi_visit_item_count=0,
        transit_only_item_count=0,
        grounded_item_count=0,
        ungrounded_item_count=0,
        grounded_poi_rate=0.0,
        all_pois_grounded=False,
        destination_correct_item_count=0,
        destination_incorrect_item_count=0,
        destination_correct_poi_rate=0.0,
        scenario_destination_valid=False,
        duplicate_poi_violation_count=0,
        duplicate_poi_violation_rate=0.0,
        duplicate_poi_pass=False,
        transit_only_named_poi_violation_count=0,
        transit_only_pass=False,
        day_count_expected=scenario.days,
        day_count_actual=0,
        day_count_pass=False,
        min_items_observed_per_day=0,
        day_structure_pass=False,
        scenario_date_alignment_pass=False,
        scenario_date_alignment_status="NOT_EVALUATED",
        schedule_violation_count=0,
        time_parse_invalid_count=0,
        time_interval_invalid_count=0,
        schedule_overlap_count=0,
        schedule_violation_event_density=0.0,
        schedule_pass=False,
        budget_status="NOT_EVALUATED",
        estimated_total_cost=0,
        budget_ceiling=scenario.budget,
        estimated_budget_compliant=None,
        estimated_budget_violation_amount=None,
        budget_overrun_fraction=None,
        arithmetic_self_consistency=False,
        geo_leg_count=0,
        total_geo_distance_proxy_km=0.0,
        mean_leg_geo_distance_proxy_km=0.0,
        max_leg_geo_distance_proxy_km=0.0,
        opening_hours_status="NOT_EVALUATED",
        opening_hours_evidence_status="NO_EVALUABLE_EVIDENCE",
        opening_hours_poi_visit_items=0,
        opening_hours_evaluable_items=0,
        opening_hours_compliant_items=0,
        opening_hours_known_violation_count=0,
        opening_hours_unknown_items=0,
        opening_hours_evidence_coverage=0.0,
        opening_hours_compliance_rate_on_evaluable_items=None,
        opening_hours_item_evaluations=[],
        final_core_scenario_pass_status="NOT_EVALUATED",
        core_scenario_pass_pre_opening_hours=False,
        core_scenario_pass=False,
        failure_reasons=failure_reasons,
        source_run_manifest_sha256=source_run_manifest_sha256,
        evaluator_code_sha256=evaluator_code_sha256,
        catalog_sha256=catalog_sha256,
        scenario_sha256=scenario_sha256,
        parsed_response_sha256=parsed_response_sha256,
    )


def verify_artifact_hashes(
    *,
    run_manifest: BenchmarkRunManifest,
    scenario_bytes: bytes,
    catalog_path: Optional[Path] = None,
    parsed_response_bytes: Optional[bytes] = None,
) -> Tuple[bool, List[str], str, str, Optional[str]]:
    """Verify persisted scenario, catalog, and parsed response SHA256 digests against run_manifest.

    Uses W06-ARTIFACT-HASH-BASIS-V1 semantics:
    - SCENARIO_INPUT: SHA256_CANONICAL_JSON_UTF8_LF_BYTES (exact persisted bytes)
    - SOURCE_CATALOG: SHA256_LF_NORMALIZED_SOURCE_BYTES
    - PARSED_PLAN_RESPONSE: SHA256_CANONICAL_JSON_UTF8_LF_BYTES (exact persisted bytes)
    """
    mismatches: List[str] = []
    actual_scenario_sha = sha256_bytes(scenario_bytes)
    actual_catalog_sha = compute_catalog_sha256(catalog_path=catalog_path)
    actual_parsed_sha = (
        sha256_bytes(parsed_response_bytes) if parsed_response_bytes is not None else None
    )

    if actual_scenario_sha != run_manifest.scenario_sha256:
        mismatches.append("SCENARIO_SHA256_MISMATCH")

    if actual_catalog_sha != run_manifest.catalog_sha256:
        mismatches.append("CATALOG_SHA256_MISMATCH")

    if run_manifest.run_status == BenchmarkRunStatus.VALID or parsed_response_bytes is not None:
        if (
            parsed_response_bytes is None
            or not run_manifest.parsed_response_sha256
            or actual_parsed_sha != run_manifest.parsed_response_sha256
        ):
            mismatches.append("PARSED_RESPONSE_SHA256_MISMATCH")

    is_intact = len(mismatches) == 0
    return is_intact, mismatches, actual_catalog_sha, actual_scenario_sha, actual_parsed_sha


def evaluate_benchmark_scenario(
    scenario: BenchmarkScenarioInput,
    plan_response: Optional[BenchmarkPlanResponse],
    run_manifest: BenchmarkRunManifest,
    *,
    catalog_path: Optional[Path] = None,
    core_catalog_by_id: Optional[Dict[str, BenchmarkCatalogPOI]] = None,
    source_run_manifest_sha256: Optional[str] = None,
    verify_hashes: bool = True,
    persisted_scenario_bytes: Optional[bytes] = None,
    persisted_parsed_bytes: Optional[bytes] = None,
) -> ScenarioEvaluationResult:
    """Deterministically evaluate a single W06 benchmark scenario against core and opening-hours constraints."""
    evaluator_code_sha = compute_evaluator_code_sha256()
    effective_manifest_sha = source_run_manifest_sha256 or sha256_bytes(
        canonical_json_bytes(run_manifest.model_dump())
    )

    scenario_bytes = (
        persisted_scenario_bytes
        if persisted_scenario_bytes is not None
        else canonical_json_bytes(scenario.model_dump())
    )
    parsed_bytes = (
        persisted_parsed_bytes
        if persisted_parsed_bytes is not None
        else (
            canonical_json_bytes(plan_response.model_dump())
            if plan_response is not None
            else None
        )
    )

    if verify_hashes:
        is_intact, hash_mismatches, actual_cat_sha, actual_scen_sha, actual_parsed_sha = (
            verify_artifact_hashes(
                run_manifest=run_manifest,
                scenario_bytes=scenario_bytes,
                catalog_path=catalog_path,
                parsed_response_bytes=parsed_bytes,
            )
        )
        if not is_intact:
            reasons = ["EVIDENCE_INTEGRITY_FAILURE"] + hash_mismatches
            return _build_non_evaluated_result(
                scenario=scenario,
                run_manifest=run_manifest,
                evaluation_status="EVIDENCE_INTEGRITY_FAILURE",
                evidence_integrity_valid=False,
                failure_reasons=reasons,
                source_run_manifest_sha256=effective_manifest_sha,
                evaluator_code_sha256=evaluator_code_sha,
                catalog_sha256=actual_cat_sha,
                scenario_sha256=actual_scen_sha,
                parsed_response_sha256=actual_parsed_sha,
            )
    else:
        actual_cat_sha = compute_catalog_sha256(catalog_path=catalog_path)
        actual_scen_sha = sha256_bytes(scenario_bytes)
        actual_parsed_sha = sha256_bytes(parsed_bytes) if parsed_bytes is not None else None

    # Run Validity Gate
    if run_manifest.run_status != BenchmarkRunStatus.VALID or plan_response is None:
        reasons = ["INVALID_RUN", f"RUN_STATUS_{run_manifest.run_status.value}"]
        return _build_non_evaluated_result(
            scenario=scenario,
            run_manifest=run_manifest,
            evaluation_status="INVALID_RUN",
            evidence_integrity_valid=True,
            failure_reasons=reasons,
            source_run_manifest_sha256=effective_manifest_sha,
            evaluator_code_sha256=evaluator_code_sha,
            catalog_sha256=actual_cat_sha,
            scenario_sha256=actual_scen_sha,
            parsed_response_sha256=actual_parsed_sha,
        )

    catalog_index = (
        core_catalog_by_id
        if core_catalog_by_id is not None
        else load_core_catalog_by_place_id(catalog_path=catalog_path)
    )

    failure_reasons: List[str] = []

    # Collect items across all days
    poi_visit_items = []
    transit_only_items = []
    all_items_count = 0

    for day in plan_response.days:
        for item in day.items:
            all_items_count += 1
            if item.activity_kind == ActivityKind.POI_VISIT:
                poi_visit_items.append(item)
            elif item.activity_kind == ActivityKind.TRANSIT_ONLY:
                transit_only_items.append(item)

    poi_visit_item_count = len(poi_visit_items)
    transit_only_item_count = len(transit_only_items)

    # Catalog Grounding (strict exact place_id lookup in REC-A-CORE-V2 catalog)
    grounded_pois: List[BenchmarkCatalogPOI] = []
    grounded_item_count = 0
    ungrounded_item_count = 0

    for item in poi_visit_items:
        pid = item.place_id or ""
        if pid in catalog_index:
            grounded_item_count += 1
            grounded_pois.append(catalog_index[pid])
        else:
            ungrounded_item_count += 1

    grounded_poi_rate = (
        round(grounded_item_count / poi_visit_item_count, 6)
        if poi_visit_item_count > 0
        else 0.0
    )
    all_pois_grounded = (poi_visit_item_count >= 1) and (ungrounded_item_count == 0)

    if poi_visit_item_count == 0:
        failure_reasons.append("ZERO_POI_VISIT_ITEMS")
    if ungrounded_item_count > 0:
        failure_reasons.append("UNGROUNDED_POI_VISIT_ITEMS")

    # Destination Correctness
    destination_correct_item_count = 0
    destination_incorrect_item_count = 0
    for cat_poi in grounded_pois:
        if cat_poi.destination_slug == scenario.destination_slug:
            destination_correct_item_count += 1
        else:
            destination_incorrect_item_count += 1

    destination_correct_poi_rate = (
        round(destination_correct_item_count / grounded_item_count, 6)
        if grounded_item_count > 0
        else 0.0
    )
    scenario_destination_valid = (
        all_pois_grounded and (destination_incorrect_item_count == 0)
    )
    if destination_incorrect_item_count > 0:
        failure_reasons.append("DESTINATION_MISMATCH")

    # Duplicate POI (strictly by canonical place_id across POI_VISIT items)
    poi_id_counts = Counter(item.place_id for item in poi_visit_items if item.place_id)
    repeated_occurrences = sum(cnt - 1 for cnt in poi_id_counts.values() if cnt > 1)
    if scenario.allow_revisit_place_ids:
        duplicate_poi_violation_count = 0
        duplicate_poi_violation_rate = 0.0
        duplicate_poi_pass = True
    else:
        duplicate_poi_violation_count = repeated_occurrences
        duplicate_poi_violation_rate = (
            round(duplicate_poi_violation_count / poi_visit_item_count, 6)
            if poi_visit_item_count > 0
            else 0.0
        )
        duplicate_poi_pass = duplicate_poi_violation_count == 0
        if not duplicate_poi_pass:
            failure_reasons.append("DUPLICATE_POI_VIOLATION")

    # TRANSIT_ONLY Anti-Gaming (deterministic field check on place_name)
    transit_only_named_poi_violation_count = sum(
        1
        for item in transit_only_items
        if item.place_name is not None
    )
    transit_only_pass = transit_only_named_poi_violation_count == 0
    if not transit_only_pass:
        failure_reasons.append("TRANSIT_ONLY_NAMED_POI_VIOLATION")

    # Day Structure
    day_count_expected = scenario.days
    day_count_actual = len(plan_response.days)
    expected_day_numbers = list(range(1, day_count_expected + 1))
    actual_day_numbers = [d.day_number for d in plan_response.days]
    day_count_pass = (
        day_count_actual == day_count_expected
        and plan_response.total_days == day_count_expected
        and actual_day_numbers == expected_day_numbers
    )
    min_items_observed_per_day = min((len(d.items) for d in plan_response.days), default=0)
    non_empty_days_pass = min_items_observed_per_day >= 1 and day_count_actual >= 1
    day_structure_pass = day_count_pass and non_empty_days_pass
    if not day_structure_pass:
        failure_reasons.append("DAY_STRUCTURE_VIOLATION")

    # Day / Date Alignment (Section 7 of W06-INSTRUMENT-01C)
    scenario_date_alignment_pass, per_day_date_trusted = validate_scenario_date_alignment(
        scenario, plan_response
    )
    if scenario_date_alignment_pass:
        scenario_date_alignment_status = "VALID"
    else:
        scenario_date_alignment_status = "SCENARIO_DATE_ALIGNMENT_FAILURE"
        failure_reasons.append("SCENARIO_DATE_ALIGNMENT_FAILURE")

    # Schedule Validity (strict HH:MM, start_time < end_time, intra-day [start, end) non-overlap)
    time_parse_invalid_count = 0
    time_interval_invalid_count = 0
    schedule_overlap_count = 0

    for day in plan_response.days:
        valid_intervals: List[Tuple[int, int, int]] = []
        for idx, item in enumerate(day.items):
            start_min = parse_strict_hhmm(item.start_time)
            end_min = parse_strict_hhmm(item.end_time)
            if start_min is None or end_min is None:
                time_parse_invalid_count += 1
            elif start_min >= end_min:
                time_interval_invalid_count += 1
            else:
                valid_intervals.append((start_min, end_min, idx))

        valid_intervals.sort(key=lambda t: (t[0], t[1], t[2]))
        for i in range(len(valid_intervals)):
            for j in range(i + 1, len(valid_intervals)):
                # Half-open intervals [start_i, end_i) and [start_j, end_j) with start_i <= start_j
                if valid_intervals[i][1] > valid_intervals[j][0]:
                    schedule_overlap_count += 1

    schedule_violation_count = (
        time_parse_invalid_count + time_interval_invalid_count + schedule_overlap_count
    )
    schedule_violation_event_density = (
        round(schedule_violation_count / all_items_count, 6)
        if all_items_count > 0
        else 0.0
    )
    schedule_pass = schedule_violation_count == 0
    if time_parse_invalid_count > 0:
        failure_reasons.append("TIME_PARSE_INVALID")
    if time_interval_invalid_count > 0:
        failure_reasons.append("TIME_INTERVAL_INVALID")
    if schedule_overlap_count > 0:
        failure_reasons.append("SCHEDULE_OVERLAP")

    # Estimated Budget Compliance & Arithmetic Self-Consistency
    day_sums_consistent = True
    estimated_total_cost = 0
    for day in plan_response.days:
        day_sum = sum(item.estimated_cost for item in day.items)
        estimated_total_cost += day_sum
        if day.day_cost != day_sum:
            day_sums_consistent = False

    reported_total_cost = plan_response.budget_analysis.estimated_cost
    arithmetic_self_consistency = (
        day_sums_consistent and (estimated_total_cost == reported_total_cost)
    )
    if not arithmetic_self_consistency:
        failure_reasons.append("ARITHMETIC_SELF_CONSISTENCY_FAILURE")

    budget_ceiling = scenario.budget
    if budget_ceiling is None:
        budget_status = "NOT_APPLICABLE"
        estimated_budget_compliant: Optional[bool] = None
        estimated_budget_violation_amount: Optional[int] = None
        budget_overrun_fraction: Optional[float] = None
        budget_pass_for_core = True
    else:
        if estimated_total_cost <= budget_ceiling:
            budget_status = "COMPLIANT"
            estimated_budget_compliant = True
            estimated_budget_violation_amount = 0
            budget_overrun_fraction = 0.0
            budget_pass_for_core = True
        else:
            budget_status = "VIOLATION"
            estimated_budget_compliant = False
            estimated_budget_violation_amount = estimated_total_cost - budget_ceiling
            budget_overrun_fraction = (
                round(max(0, estimated_total_cost - budget_ceiling) / budget_ceiling, 6)
                if budget_ceiling > 0
                else 1.0
            )
            budget_pass_for_core = False
            failure_reasons.append("ESTIMATED_BUDGET_VIOLATION")

    # GEO_DISTANCE_PROXY (diagnostic only; consecutive grounded POI_VISIT items)
    coords_sequence: List[Tuple[float, float]] = [
        (cat_poi.lat, cat_poi.lng)
        for cat_poi in grounded_pois
        if cat_poi.lat is not None and cat_poi.lng is not None
    ]
    leg_distances: List[float] = []
    for idx in range(len(coords_sequence) - 1):
        lat1, lng1 = coords_sequence[idx]
        lat2, lng2 = coords_sequence[idx + 1]
        leg_distances.append(compute_haversine_geo_distance_proxy_km(lat1, lng1, lat2, lng2))

    geo_leg_count = len(leg_distances)
    if geo_leg_count > 0:
        total_geo_distance_proxy_km = round(sum(leg_distances), 6)
        mean_leg_geo_distance_proxy_km = round(sum(leg_distances) / geo_leg_count, 6)
        max_leg_geo_distance_proxy_km = round(max(leg_distances), 6)
    else:
        total_geo_distance_proxy_km = 0.0
        mean_leg_geo_distance_proxy_km = 0.0
        max_leg_geo_distance_proxy_km = 0.0

    # Opening-Hours Evaluation (Sections 6 & 8 of W06-INSTRUMENT-01C)
    opening_hours_item_evaluations: List[OpeningHoursItemEvaluation] = []
    for day_idx, day in enumerate(plan_response.days):
        day_date_trusted = per_day_date_trusted.get(day_idx, False)
        for item in day.items:
            if item.activity_kind != ActivityKind.POI_VISIT:
                continue
            pid = item.place_id or ""
            is_grounded = pid in catalog_index
            oh_raw = catalog_index[pid].opening_hours if is_grounded else None
            oh_eval = evaluate_poi_visit_opening_hours(
                day_number=day.day_number,
                date_str=day.date,
                date_context_trusted=day_date_trusted,
                order_index=item.order_index,
                place_id=item.place_id,
                is_grounded=is_grounded,
                opening_hours_raw=oh_raw,
                start_time=item.start_time,
                end_time=item.end_time,
            )
            opening_hours_item_evaluations.append(oh_eval)

    opening_hours_poi_visit_items = poi_visit_item_count
    opening_hours_compliant_items = sum(
        1 for ev in opening_hours_item_evaluations if ev.opening_hours_state == "COMPLIANT"
    )
    opening_hours_known_violation_count = sum(
        1 for ev in opening_hours_item_evaluations if ev.opening_hours_state == "VIOLATION"
    )
    opening_hours_unknown_items = sum(
        1 for ev in opening_hours_item_evaluations if ev.opening_hours_state == "UNKNOWN"
    )
    opening_hours_evaluable_items = (
        opening_hours_compliant_items + opening_hours_known_violation_count
    )

    opening_hours_evidence_coverage = (
        round(opening_hours_evaluable_items / opening_hours_poi_visit_items, 6)
        if opening_hours_poi_visit_items > 0
        else 0.0
    )
    opening_hours_compliance_rate_on_evaluable_items: Optional[float] = (
        round(opening_hours_compliant_items / opening_hours_evaluable_items, 6)
        if opening_hours_evaluable_items > 0
        else None
    )

    if opening_hours_evaluable_items == 0:
        opening_hours_evidence_status = "NO_EVALUABLE_EVIDENCE"
    elif (
        opening_hours_poi_visit_items > 0
        and opening_hours_evaluable_items == opening_hours_poi_visit_items
    ):
        opening_hours_evidence_status = "FULLY_EVALUABLE"
    else:
        opening_hours_evidence_status = "PARTIALLY_EVALUABLE"

    if opening_hours_known_violation_count > 0:
        failure_reasons.append("OPENING_HOURS_KNOWN_VIOLATION")

    # Pre-opening-hours pass (01B contract) and final core_scenario_pass (01C contract)
    core_scenario_pass_pre_opening_hours = all(
        [
            poi_visit_item_count >= 1,
            all_pois_grounded,
            scenario_destination_valid,
            duplicate_poi_pass,
            transit_only_pass,
            day_structure_pass,
            schedule_pass,
            arithmetic_self_consistency,
            budget_pass_for_core,
        ]
    )

    core_scenario_pass = (
        core_scenario_pass_pre_opening_hours
        and scenario_date_alignment_pass
        and (opening_hours_known_violation_count == 0)
    )

    return ScenarioEvaluationResult(
        scenario_id=scenario.scenario_id,
        run_id=run_manifest.run_id,
        destination_slug=scenario.destination_slug,
        evaluation_status="EVALUATED",
        evidence_integrity_valid=True,
        run_valid=True,
        run_status=run_manifest.run_status.value,
        poi_visit_item_count=poi_visit_item_count,
        transit_only_item_count=transit_only_item_count,
        grounded_item_count=grounded_item_count,
        ungrounded_item_count=ungrounded_item_count,
        grounded_poi_rate=grounded_poi_rate,
        all_pois_grounded=all_pois_grounded,
        destination_correct_item_count=destination_correct_item_count,
        destination_incorrect_item_count=destination_incorrect_item_count,
        destination_correct_poi_rate=destination_correct_poi_rate,
        scenario_destination_valid=scenario_destination_valid,
        duplicate_poi_violation_count=duplicate_poi_violation_count,
        duplicate_poi_violation_rate=duplicate_poi_violation_rate,
        duplicate_poi_pass=duplicate_poi_pass,
        transit_only_named_poi_violation_count=transit_only_named_poi_violation_count,
        transit_only_pass=transit_only_pass,
        day_count_expected=day_count_expected,
        day_count_actual=day_count_actual,
        day_count_pass=day_count_pass,
        min_items_observed_per_day=min_items_observed_per_day,
        day_structure_pass=day_structure_pass,
        scenario_date_alignment_pass=scenario_date_alignment_pass,
        scenario_date_alignment_status=scenario_date_alignment_status,
        schedule_violation_count=schedule_violation_count,
        time_parse_invalid_count=time_parse_invalid_count,
        time_interval_invalid_count=time_interval_invalid_count,
        schedule_overlap_count=schedule_overlap_count,
        schedule_violation_event_density=schedule_violation_event_density,
        schedule_pass=schedule_pass,
        budget_status=budget_status,
        estimated_total_cost=estimated_total_cost,
        budget_ceiling=budget_ceiling,
        estimated_budget_compliant=estimated_budget_compliant,
        estimated_budget_violation_amount=estimated_budget_violation_amount,
        budget_overrun_fraction=budget_overrun_fraction,
        arithmetic_self_consistency=arithmetic_self_consistency,
        geo_leg_count=geo_leg_count,
        total_geo_distance_proxy_km=total_geo_distance_proxy_km,
        mean_leg_geo_distance_proxy_km=mean_leg_geo_distance_proxy_km,
        max_leg_geo_distance_proxy_km=max_leg_geo_distance_proxy_km,
        opening_hours_status=OPENING_HOURS_STATUS_01C,
        opening_hours_evidence_status=opening_hours_evidence_status,
        opening_hours_poi_visit_items=opening_hours_poi_visit_items,
        opening_hours_evaluable_items=opening_hours_evaluable_items,
        opening_hours_compliant_items=opening_hours_compliant_items,
        opening_hours_known_violation_count=opening_hours_known_violation_count,
        opening_hours_unknown_items=opening_hours_unknown_items,
        opening_hours_evidence_coverage=opening_hours_evidence_coverage,
        opening_hours_compliance_rate_on_evaluable_items=opening_hours_compliance_rate_on_evaluable_items,
        opening_hours_item_evaluations=opening_hours_item_evaluations,
        opening_hours_parser_version=OPENING_HOURS_PARSER_VERSION,
        final_core_scenario_pass_status=FINAL_CORE_PASS_STATUS_01C,
        core_scenario_pass_pre_opening_hours=core_scenario_pass_pre_opening_hours,
        core_scenario_pass=core_scenario_pass,
        failure_reasons=failure_reasons,
        source_run_manifest_sha256=effective_manifest_sha,
        evaluator_code_sha256=evaluator_code_sha,
        catalog_sha256=actual_cat_sha,
        scenario_sha256=actual_scen_sha,
        parsed_response_sha256=actual_parsed_sha,
    )


def evaluate_run_directory(
    run_dir: Path,
    *,
    output_path: Optional[Path] = None,
    catalog_path: Optional[Path] = None,
) -> ScenarioEvaluationResult:
    """Evaluate a persisted single-scenario run directory and write scenario_evaluation.json."""
    if not run_dir.exists() or not run_dir.is_dir():
        raise FileNotFoundError(f"Run directory not found: {run_dir}")

    manifest_path = run_dir / "run_manifest.json"
    scenario_path = run_dir / "scenario_input.json"
    parsed_path = run_dir / "parsed_plan_response.json"

    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing required run_manifest.json in {run_dir}")
    if not scenario_path.exists():
        raise FileNotFoundError(f"Missing required scenario_input.json in {run_dir}")

    manifest_bytes = manifest_path.read_bytes()
    scenario_bytes = scenario_path.read_bytes()

    run_manifest = BenchmarkRunManifest.model_validate(
        json.loads(manifest_bytes.decode("utf-8"))
    )
    scenario = BenchmarkScenarioInput.model_validate(
        json.loads(scenario_bytes.decode("utf-8"))
    )

    parsed_bytes: Optional[bytes] = None
    plan_response: Optional[BenchmarkPlanResponse] = None

    if parsed_path.exists():
        parsed_bytes = parsed_path.read_bytes()
        try:
            plan_response = BenchmarkPlanResponse.model_validate(
                json.loads(parsed_bytes.decode("utf-8"))
            )
        except Exception:
            if sha256_bytes(parsed_bytes) == run_manifest.parsed_response_sha256:
                raise

    result = evaluate_benchmark_scenario(
        scenario=scenario,
        plan_response=plan_response,
        run_manifest=run_manifest,
        catalog_path=catalog_path,
        source_run_manifest_sha256=sha256_bytes(manifest_bytes),
        verify_hashes=True,
        persisted_scenario_bytes=scenario_bytes,
        persisted_parsed_bytes=parsed_bytes,
    )

    target_output = output_path or (run_dir / "scenario_evaluation.json")
    write_canonical_json(target_output, result.model_dump())
    return result
