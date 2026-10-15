"""Deterministic W06 Benchmark Scenario Generator Engine (W06-SCENARIO-GENERATOR-01).

Grounded in:
- data/evaluation/w06/w06_scenario_method_lock_v1.json (W06-SCENARIO-METHOD-LOCK-01 v1.0.0)
- data/evaluation/w06/w06_scenario_support_matrix_v1.json (W06-SCENARIO-SUPPORT-MATRIX-V1 v1.0.0)
- apps/ai-service/app/schemas/planner_benchmark.py (BenchmarkScenarioInput)
- apps/ai-service/recommendation/reca/contract.py (CANONICAL_INTERESTS, poi_to_canonical_vector)

IMPORTANT SCIENTIFIC BOUNDARIES:
- This module implements the deterministic scenario generator engine and verification
  machinery only.
- All outputs produced by this module are explicitly marked DRY_RUN / SYNTHETIC_GENERATOR_QA.
- Does NOT persist or freeze the final 100 benchmark scenarios or create P11.
- Never calls Gemini, OpenAI, Claude, or any external model provider.
- Never inspects planner or model outputs.
"""
from collections import Counter
import datetime
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.planner_benchmark import (
    CANONICAL_BENCHMARK_INTERESTS,
    PRIMARY_BENCHMARK_DESTINATIONS,
    BenchmarkScenarioInput,
)
from recommendation.reca.contract import (
    CANONICAL_INTERESTS,
    poi_to_canonical_vector,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_METHOD_LOCK_PATH = (
    REPO_ROOT / "data" / "evaluation" / "w06" / "w06_scenario_method_lock_v1.json"
)
DEFAULT_SUPPORT_MATRIX_PATH = (
    REPO_ROOT / "data" / "evaluation" / "w06" / "w06_scenario_support_matrix_v1.json"
)
DEFAULT_CATALOG_PATH = (
    REPO_ROOT / "data" / "curated" / "gomate_places_freeze_v2.json"
)

SCENARIO_GENERATOR_VERSION: str = "W06-SCENARIO-GENERATOR-01-V1.0.0"
METHOD_LOCK_RULE_VERSION: str = "W06-SCENARIO-METHOD-LOCK-01-V1.0.0"
DEFAULT_SCENARIO_GENERATION_SEED: int = 2026101506

INFEASIBILITY_PROTOCOL_STATUS: str = (
    "STOP_DO_NOT_SILENTLY_RELAX_REQUIRE_FORMAL_METHOD_AMENDMENT"
)
DRY_RUN_MODE: str = "DRY_RUN"
DRY_RUN_FIXTURE_LABEL: str = "SYNTHETIC_GENERATOR_QA"
DRY_RUN_SCENARIO_ID_PREFIX: str = "W06-DRYRUN"

ALLOWED_REJECTION_REASON_CODES: Tuple[str, ...] = (
    "CATALOG_SUPPORT_BELOW_THRESHOLD",
    "TOTAL_INTEREST_CAPACITY_INSUFFICIENT",
    "SCHEMA_INVALID",
    "DATE_RANGE_INVALID",
    "NEAR_DUPLICATE_SIGNATURE",
    "INTEREST_COMBINATION_REPEAT_CAP",
    "ALLOCATION_CELL_FULL",
    "NON_CANONICAL_FIELD",
    "TEXT_AMBIGUOUS_NOTES",
    "MANUAL_QA_REJECT",
)

ORDERED_DESTINATIONS: Tuple[str, ...] = ("ha-noi", "da-nang", "ha-long")
ORDERED_DAYS: Tuple[int, ...] = (2, 3, 4)
ORDERED_INTEREST_COUNTS: Tuple[int, ...] = (1, 2, 3)
ORDERED_BUDGET_TIERS: Tuple[Optional[str], ...] = ("B1", "B2", "B3", None)
ORDERED_TRAVEL_STYLES: Tuple[str, ...] = ("BACKPACKER", "BUDGET", "COMFORT", "LUXURY")


class ScenarioGenerationInfeasibleError(ValueError):
    """Raised when scenario generation constraints are mathematically or structurally infeasible.

    Enforces fail-closed behavior under STOP_DO_NOT_SILENTLY_RELAX_REQUIRE_FORMAL_METHOD_AMENDMENT.
    """

    def __init__(self, reason: str, protocol_status: str = INFEASIBILITY_PROTOCOL_STATUS) -> None:
        self.reason = reason
        self.protocol_status = protocol_status
        super().__init__(f"[{protocol_status}] {reason}")


def canonical_json_bytes(obj: Any) -> bytes:
    """Serialize object to deterministic canonical UTF-8 LF JSON bytes."""
    return (
        json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    """Compute SHA256 hex digest over raw bytes."""
    return hashlib.sha256(data).hexdigest()


def lf_normalized_file_sha256(path: Path) -> str:
    """Compute SHA256 hex digest over LF-normalized UTF-8 file bytes."""
    raw = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return sha256_hex(raw)


def deterministic_tiebreak_digest(seed: int, canonical_key: str) -> str:
    """Compute a deterministic SHA256 digest from seed + canonical representation.

    Uses zero global random state and zero Python hash() ordering.
    """
    payload = f"seed={seed}|key={canonical_key}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class CandidateRejectionEntry(BaseModel):
    """Deterministic log record for a rejected scenario candidate."""

    model_config = ConfigDict(extra="forbid")

    candidate_index: int = Field(..., ge=1)
    candidate_sha256: str = Field(..., min_length=64, max_length=64)
    reason_code: str = Field(..., min_length=1)
    rule_version: str = METHOD_LOCK_RULE_VERSION
    replacement_candidate_index: Optional[int] = Field(default=None, ge=1)
    destination_slug: Optional[str] = None
    days: Optional[int] = None
    interest_count: Optional[int] = None
    interests_sorted: Optional[List[str]] = None

    @field_validator("reason_code")
    @classmethod
    def validate_reason_code(cls, v: str) -> str:
        if v not in ALLOWED_REJECTION_REASON_CODES:
            raise ValueError(
                f"Invalid rejection reason_code '{v}'. Allowed: {list(ALLOWED_REJECTION_REASON_CODES)}"
            )
        return v


class DryRunScenarioSlot(BaseModel):
    """Single deterministic dry-run scenario assignment slot."""

    model_config = ConfigDict(extra="forbid")

    slot_index: int = Field(..., ge=1, le=100)
    scenario_id: str = Field(..., min_length=1)
    candidate_index: int = Field(..., ge=1)
    candidate_sha256: str = Field(..., min_length=64, max_length=64)
    destination_slug: str
    destination: str
    days: int
    interest_count: int
    interests: List[str]
    support_class: str
    rule_a_passed: bool
    rule_b_passed: bool
    union_support: int
    sum_support: int
    min_interest_support: int
    budget_tier_or_null: Optional[str] = None
    budget: Optional[int] = None
    currency: str = "VND"
    travel_style: str
    weekend_exposure: bool
    start_date: str
    end_date: str
    canonical_signature: List[Any]
    canonical_signature_sha256: str
    scenario_input: BenchmarkScenarioInput


class CrossBalanceReport(BaseModel):
    """Complete deterministic marginal and cross-dimension balance report."""

    model_config = ConfigDict(extra="forbid")

    locked_marginal_counts: Dict[str, Any]
    destination_by_days: Dict[str, Dict[str, int]]
    destination_by_interest_count: Dict[str, Dict[str, int]]
    destination_by_budget: Dict[str, Dict[str, int]]
    destination_by_style: Dict[str, Dict[str, int]]
    destination_by_weekend: Dict[str, Dict[str, int]]
    days_by_interest_count: Dict[str, Dict[str, int]]
    days_by_budget: Dict[str, Dict[str, int]]
    days_by_style: Dict[str, Dict[str, int]]
    interest_count_by_budget: Dict[str, Dict[str, int]]
    interest_count_by_style: Dict[str, Dict[str, int]]
    support_class_counts: Dict[str, int]
    support_class_by_destination: Dict[str, Dict[str, int]]
    max_min_cross_cell_imbalance: Dict[str, Dict[str, int]]
    unavoidable_imbalance_notes: List[str]


class DryRunGeneratorBundle(BaseModel):
    """Complete deterministic dry-run output bundle for W06-SCENARIO-GENERATOR-01."""

    model_config = ConfigDict(extra="forbid")

    generator_version: str = SCENARIO_GENERATOR_VERSION
    run_mode: str = DRY_RUN_MODE
    fixture_label: str = DRY_RUN_FIXTURE_LABEL
    is_final_100_scenarios: bool = False
    real_scenarios_generated: bool = False
    p11_created: bool = False
    preregistration_created: bool = False
    gemini_called: bool = False
    seed: int
    method_lock_id: str
    method_lock_version: str
    method_lock_sha256: str
    support_matrix_id: str
    support_matrix_version: str
    support_matrix_sha256: str
    slot_count: int
    slots: List[DryRunScenarioSlot]
    rejection_log_count: int
    rejection_reason_counts: Dict[str, int]
    rejection_log: List[CandidateRejectionEntry]
    cross_balance_report: CrossBalanceReport
    invariants_verified: Dict[str, Any]


def load_method_lock_config(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load and validate the frozen W06 scenario method lock JSON."""
    target = path or DEFAULT_METHOD_LOCK_PATH
    if not target.exists():
        raise ScenarioGenerationInfeasibleError(f"Missing method lock file: {target}")
    data = json.loads(target.read_text(encoding="utf-8"))
    if data.get("method_lock_id") != "W06-SCENARIO-METHOD-LOCK-01":
        raise ScenarioGenerationInfeasibleError(
            f"Unexpected method_lock_id: {data.get('method_lock_id')!r}"
        )
    if data.get("method_lock_version") != "1.0.0":
        raise ScenarioGenerationInfeasibleError(
            f"Unexpected method_lock_version: {data.get('method_lock_version')!r}"
        )
    return data


def load_support_matrix(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load and validate the frozen W06 scenario support matrix JSON."""
    target = path or DEFAULT_SUPPORT_MATRIX_PATH
    if not target.exists():
        raise ScenarioGenerationInfeasibleError(f"Missing support matrix file: {target}")
    data = json.loads(target.read_text(encoding="utf-8"))
    if data.get("artifact_id") != "W06-SCENARIO-SUPPORT-MATRIX-V1":
        raise ScenarioGenerationInfeasibleError(
            f"Unexpected support matrix artifact_id: {data.get('artifact_id')!r}"
        )
    if data.get("artifact_version") != "1.0.0":
        raise ScenarioGenerationInfeasibleError(
            f"Unexpected support matrix artifact_version: {data.get('artifact_version')!r}"
        )
    return data


def load_direct_catalog_interest_sets(
    catalog_path: Optional[Path] = None,
) -> Dict[str, Dict[str, Set[str]]]:
    """Build destination -> canonical_interest -> set(place_id) directly from REC-A-CORE-V2 catalog."""
    target = catalog_path or DEFAULT_CATALOG_PATH
    if not target.exists():
        raise ScenarioGenerationInfeasibleError(f"Missing catalog file: {target}")
    payload = json.loads(target.read_text(encoding="utf-8"))
    places = payload["places"] if isinstance(payload, dict) and "places" in payload else payload
    index: Dict[str, Dict[str, Set[str]]] = {
        dest: {interest: set() for interest in CANONICAL_INTERESTS}
        for dest in ORDERED_DESTINATIONS
    }
    for poi in places:
        if not poi.get("is_rec_a_core_v2", False):
            continue
        dest = poi.get("destination_slug")
        if dest not in index:
            continue
        pid = poi["place_id"]
        vec, _ = poi_to_canonical_vector(poi)
        for idx, interest in enumerate(CANONICAL_INTERESTS):
            if vec[idx] > 0.0:
                index[dest][interest].add(pid)
    return index


def verify_combination_direct_support(
    destination_slug: str,
    days: int,
    interests_sorted: Sequence[str],
    catalog_interest_sets: Dict[str, Dict[str, Set[str]]],
    min_poi_visits_per_day: int = 2,
) -> Dict[str, Any]:
    """Recompute Rule A, Rule B (direct set union), and support_class directly from catalog."""
    dest_map = catalog_interest_sets[destination_slug]
    counts = {i: len(dest_map[i]) for i in interests_sorted}
    sum_support = sum(counts.values())
    union_set: Set[str] = set().union(*(dest_map[i] for i in interests_sorted))
    union_support = len(union_set)
    min_support = min(counts.values())
    rule_a_threshold = days
    rule_b_threshold = days * min_poi_visits_per_day
    rule_a_passed = all(c >= rule_a_threshold for c in counts.values())
    rule_b_passed = (union_support >= rule_b_threshold) and (sum_support >= rule_b_threshold)
    eligible = rule_a_passed and rule_b_passed
    if not eligible:
        support_class = "EXCLUDED"
        exclusion_reason_code = (
            "CATALOG_SUPPORT_BELOW_THRESHOLD"
            if not rule_a_passed
            else "TOTAL_INTEREST_CAPACITY_INSUFFICIENT"
        )
    elif any(rule_a_threshold <= c < rule_b_threshold for c in counts.values()):
        support_class = "STRESS"
        exclusion_reason_code = None
    else:
        support_class = "CLEAR"
        exclusion_reason_code = None
    return {
        "counts": counts,
        "min_interest_support": min_support,
        "sum_support": sum_support,
        "union_support": union_support,
        "rule_a_passed": rule_a_passed,
        "rule_b_passed": rule_b_passed,
        "eligible": eligible,
        "support_class": support_class,
        "exclusion_reason_code": exclusion_reason_code,
    }


def _validate_method_lock_and_support_matrix_invariants(
    method_lock: Dict[str, Any],
    support_matrix: Dict[str, Any],
    seed: int,
) -> None:
    """Validate all frozen marginals and repeat caps before allocation; fail closed on any mismatch."""
    seed_policy = method_lock.get("generation_seed_policy", {})
    expected_seed = seed_policy.get("scenario_generation_seed")
    if seed_policy.get("allowed_seed_count") != 1 or seed_policy.get("seed_shopping_allowed") is not False:
        raise ScenarioGenerationInfeasibleError(
            "Seed policy violated: allowed_seed_count must be 1 and seed_shopping_allowed must be False."
        )
    if seed != expected_seed:
        raise ScenarioGenerationInfeasibleError(
            f"Generator seed {seed} does not match frozen scenario_generation_seed {expected_seed}."
        )

    pb = method_lock.get("primary_benchmark", {})
    if pb.get("benchmark_target") != 100:
        raise ScenarioGenerationInfeasibleError(
            f"Primary benchmark_target must be 100, got {pb.get('benchmark_target')!r}."
        )
    dest_alloc = pb.get("destination_allocation", {})
    if dest_alloc != {"ha-noi": 34, "da-nang": 33, "ha-long": 33}:
        raise ScenarioGenerationInfeasibleError(
            f"Destination allocation mismatch: {dest_alloc!r}"
        )

    tl = method_lock.get("trip_length_target", {})
    if tl.get("allowed_days") != [2, 3, 4] or tl.get("marginal_counts") != {"2": 33, "3": 34, "4": 33}:
        raise ScenarioGenerationInfeasibleError(
            f"Trip length target mismatch: {tl!r}"
        )

    ic = method_lock.get("interest_count_target", {})
    if ic.get("allowed_interest_counts") != [1, 2, 3] or ic.get("marginal_counts") != {"1": 33, "2": 34, "3": 33}:
        raise ScenarioGenerationInfeasibleError(
            f"Interest count target mismatch: {ic!r}"
        )
    if ic.get("canonical_interests") != list(CANONICAL_BENCHMARK_INTERESTS):
        raise ScenarioGenerationInfeasibleError(
            f"Canonical interests mismatch: {ic.get('canonical_interests')!r}"
        )

    cross_d = method_lock.get("destination_days_cross_allocation", {})
    expected_cross_d = {
        "ha-noi": {"2": 11, "3": 12, "4": 11},
        "da-nang": {"2": 11, "3": 11, "4": 11},
        "ha-long": {"2": 11, "3": 11, "4": 11},
    }
    if cross_d != expected_cross_d:
        raise ScenarioGenerationInfeasibleError(
            f"destination_days_cross_allocation mismatch: {cross_d!r}"
        )

    cross_k = method_lock.get("destination_interest_count_cross_allocation", {})
    expected_cross_k = {
        "ha-noi": {"1": 11, "2": 12, "3": 11},
        "da-nang": {"1": 11, "2": 11, "3": 11},
        "ha-long": {"1": 11, "2": 11, "3": 11},
    }
    if cross_k != expected_cross_k:
        raise ScenarioGenerationInfeasibleError(
            f"destination_interest_count_cross_allocation mismatch: {cross_k!r}"
        )

    bp = method_lock.get("budget_policy", {})
    tiers = bp.get("nominal_tiers", {})
    if (
        bp.get("budget_applicable_scenarios") != 80
        or bp.get("budget_null_scenarios") != 20
        or tiers.get("B1", {}).get("scenario_count") != 27
        or tiers.get("B2", {}).get("scenario_count") != 27
        or tiers.get("B3", {}).get("scenario_count") != 26
        or tiers.get("B1", {}).get("daily_nominal_vnd") != 500000
        or tiers.get("B2", {}).get("daily_nominal_vnd") != 1000000
        or tiers.get("B3", {}).get("daily_nominal_vnd") != 2000000
    ):
        raise ScenarioGenerationInfeasibleError(
            f"Budget policy mismatch: {bp!r}"
        )

    tsp = method_lock.get("travel_style_policy", {})
    if tsp.get("marginal_counts") != {
        "BACKPACKER": 25,
        "BUDGET": 25,
        "COMFORT": 25,
        "LUXURY": 25,
    }:
        raise ScenarioGenerationInfeasibleError(
            f"Travel style marginal counts mismatch: {tsp!r}"
        )

    dp = method_lock.get("date_policy", {})
    if (
        dp.get("window_start_date") != "2026-11-02"
        or dp.get("window_end_date") != "2026-12-13"
        or dp.get("weekend_exposed_count") != 50
        or dp.get("non_weekend_exposed_count") != 50
        or dp.get("trip_dates_must_be_contiguous") is not True
    ):
        raise ScenarioGenerationInfeasibleError(
            f"Date policy mismatch: {dp!r}"
        )

    ndp = method_lock.get("near_duplicate_policy", {})
    caps = ndp.get("repeat_caps_by_destination_and_interest_count", {})
    expected_caps = {
        "ha-noi": {"1": 3, "2": 1, "3": 1},
        "da-nang": {"1": 2, "2": 1, "3": 1},
        "ha-long": {"1": 2, "2": 1, "3": 1},
    }
    for dest in ORDERED_DESTINATIONS:
        if dest not in support_matrix.get("destinations", {}):
            raise ScenarioGenerationInfeasibleError(
                f"Destination {dest} missing in support_matrix"
            )
        d_entry = support_matrix["destinations"][dest]
        for k_int in ORDERED_INTEREST_COUNTS:
            k_str = str(k_int)
            distinct_eligible: Set[Tuple[str, ...]] = set()
            for d_int in ORDERED_DAYS:
                d_str = str(d_int)
                for comb in d_entry["by_days"][d_str]["combinations"]:
                    if comb["interest_count"] == k_int and comb["eligible"] is True:
                        distinct_eligible.add(tuple(comb["interests_sorted"]))
            if len(distinct_eligible) == 0:
                raise ScenarioGenerationInfeasibleError(
                    f"Zero eligible combinations for destination={dest}, interest_count={k_int}"
                )
            assigned = cross_k[dest][k_str]
            formula_cap = math.ceil(assigned / len(distinct_eligible))
            locked_cap = caps.get(dest, {}).get(k_str, {}).get("repeat_cap")
            if locked_cap != expected_caps[dest][k_str] or locked_cap != formula_cap:
                raise ScenarioGenerationInfeasibleError(
                    f"Repeat cap mismatch for ({dest}, k={k_int}): locked={locked_cap}, "
                    f"expected={expected_caps[dest][k_str]}, formula={formula_cap}"
                )
            if len(distinct_eligible) * locked_cap < assigned:
                raise ScenarioGenerationInfeasibleError(
                    f"Pigeonhole capacity insufficient for ({dest}, k={k_int}): "
                    f"{len(distinct_eligible)} * {locked_cap} < {assigned}"
                )


def _build_3d_destination_days_interest_grid(
    method_lock: Dict[str, Any],
) -> Dict[str, Dict[Tuple[int, int], int]]:
    """Construct exact 3D cell counts (destination, days, interest_count) satisfying all frozen marginals.

    Rotates the 3x3 cell pattern across destinations so that:
    - For every destination, row sums match destination_days_cross_allocation (11/12/11, 11/11/11, 11/11/11)
    - For every destination, col sums match destination_interest_count_cross_allocation (11/12/11, 11/11/11, 11/11/11)
    - Globally across all 3 destinations, days x interest_count cells are 11 everywhere except (3, 2) = 12,
      achieving theoretical minimum cross-cell imbalance (max - min = 1).
    """
    grid: Dict[str, Dict[Tuple[int, int], int]] = {
        "ha-noi": {
            (2, 1): 4, (2, 2): 4, (2, 3): 3,
            (3, 1): 4, (3, 2): 4, (3, 3): 4,
            (4, 1): 3, (4, 2): 4, (4, 3): 4,
        },
        "da-nang": {
            (2, 1): 4, (2, 2): 3, (2, 3): 4,
            (3, 1): 3, (3, 2): 4, (3, 3): 4,
            (4, 1): 4, (4, 2): 4, (4, 3): 3,
        },
        "ha-long": {
            (2, 1): 3, (2, 2): 4, (2, 3): 4,
            (3, 1): 4, (3, 2): 4, (3, 3): 3,
            (4, 1): 4, (4, 2): 3, (4, 3): 4,
        },
    }
    cross_d = method_lock["destination_days_cross_allocation"]
    cross_k = method_lock["destination_interest_count_cross_allocation"]
    for dest in ORDERED_DESTINATIONS:
        for d in ORDERED_DAYS:
            row_sum = sum(grid[dest][(d, k)] for k in ORDERED_INTEREST_COUNTS)
            if row_sum != cross_d[dest][str(d)]:
                raise ScenarioGenerationInfeasibleError(
                    f"3D grid row sum mismatch at {dest} d={d}: {row_sum} != {cross_d[dest][str(d)]}"
                )
        for k in ORDERED_INTEREST_COUNTS:
            col_sum = sum(grid[dest][(d, k)] for d in ORDERED_DAYS)
            if col_sum != cross_k[dest][str(k)]:
                raise ScenarioGenerationInfeasibleError(
                    f"3D grid col sum mismatch at {dest} k={k}: {col_sum} != {cross_k[dest][str(k)]}"
                )
    return grid


def _enumerate_valid_date_windows(
    window_start_str: str,
    window_end_str: str,
    seed: int,
) -> Dict[Tuple[int, bool], List[Tuple[str, str]]]:
    """Enumerate all valid contiguous [start_date, end_date] pairs inside the allowed window."""
    try:
        start_dt = datetime.date.fromisoformat(window_start_str)
        end_dt = datetime.date.fromisoformat(window_end_str)
    except ValueError as exc:
        raise ScenarioGenerationInfeasibleError(f"Invalid date window: {exc}") from exc

    if start_dt > end_dt:
        raise ScenarioGenerationInfeasibleError(
            f"Date window start {window_start_str} is after end {window_end_str}."
        )

    pools: Dict[Tuple[int, bool], List[Tuple[str, str]]] = {}
    for d in ORDERED_DAYS:
        for wk in (True, False):
            valid_ranges: List[Tuple[str, str]] = []
            cur = start_dt
            while cur + datetime.timedelta(days=d - 1) <= end_dt:
                trip_days = [cur + datetime.timedelta(days=offset) for offset in range(d)]
                has_weekend = any(dt.weekday() in (5, 6) for dt in trip_days)
                if has_weekend == wk:
                    valid_ranges.append((cur.isoformat(), trip_days[-1].isoformat()))
                cur += datetime.timedelta(days=1)
            if not valid_ranges:
                raise ScenarioGenerationInfeasibleError(
                    f"Zero valid contiguous date ranges for days={d}, weekend_exposed={wk} "
                    f"in window {window_start_str}..{window_end_str}."
                )
            valid_ranges.sort(
                key=lambda pair: (
                    deterministic_tiebreak_digest(seed, f"date|{d}|{wk}|{pair[0]}|{pair[1]}"),
                    pair[0],
                    pair[1],
                )
            )
            pools[(d, wk)] = valid_ranges
    return pools


def build_cross_balance_report(slots: Sequence[DryRunScenarioSlot]) -> CrossBalanceReport:
    """Build deterministic marginal and cross-dimension balance report from assigned slots."""
    dest_counts = {d: 0 for d in ORDERED_DESTINATIONS}
    days_counts = {str(d): 0 for d in ORDERED_DAYS}
    k_counts = {str(k): 0 for k in ORDERED_INTEREST_COUNTS}
    budget_keys = ("B1", "B2", "B3", "null")
    budget_counts = {b: 0 for b in budget_keys}
    style_counts = {s: 0 for s in ORDERED_TRAVEL_STYLES}
    weekend_counts = {"weekend_exposed": 0, "non_weekend_exposed": 0}
    support_counts = {"CLEAR": 0, "STRESS": 0, "EXCLUDED": 0}

    dest_by_days = {d: {str(day): 0 for day in ORDERED_DAYS} for d in ORDERED_DESTINATIONS}
    dest_by_k = {d: {str(k): 0 for k in ORDERED_INTEREST_COUNTS} for d in ORDERED_DESTINATIONS}
    dest_by_budget = {d: {b: 0 for b in budget_keys} for d in ORDERED_DESTINATIONS}
    dest_by_style = {d: {s: 0 for s in ORDERED_TRAVEL_STYLES} for d in ORDERED_DESTINATIONS}
    dest_by_wk = {
        d: {"weekend_exposed": 0, "non_weekend_exposed": 0} for d in ORDERED_DESTINATIONS
    }
    days_by_k = {str(day): {str(k): 0 for k in ORDERED_INTEREST_COUNTS} for day in ORDERED_DAYS}
    days_by_budget = {str(day): {b: 0 for b in budget_keys} for day in ORDERED_DAYS}
    days_by_style = {str(day): {s: 0 for s in ORDERED_TRAVEL_STYLES} for day in ORDERED_DAYS}
    k_by_budget = {str(k): {b: 0 for b in budget_keys} for k in ORDERED_INTEREST_COUNTS}
    k_by_style = {str(k): {s: 0 for s in ORDERED_TRAVEL_STYLES} for k in ORDERED_INTEREST_COUNTS}
    support_by_dest = {
        d: {"CLEAR": 0, "STRESS": 0, "EXCLUDED": 0} for d in ORDERED_DESTINATIONS
    }

    for s in slots:
        d_slug = s.destination_slug
        day_s = str(s.days)
        k_s = str(s.interest_count)
        b_key = s.budget_tier_or_null if s.budget_tier_or_null is not None else "null"
        st_key = s.travel_style
        wk_key = "weekend_exposed" if s.weekend_exposure else "non_weekend_exposed"
        sc_key = s.support_class

        dest_counts[d_slug] += 1
        days_counts[day_s] += 1
        k_counts[k_s] += 1
        budget_counts[b_key] += 1
        style_counts[st_key] += 1
        weekend_counts[wk_key] += 1
        support_counts[sc_key] += 1

        dest_by_days[d_slug][day_s] += 1
        dest_by_k[d_slug][k_s] += 1
        dest_by_budget[d_slug][b_key] += 1
        dest_by_style[d_slug][st_key] += 1
        dest_by_wk[d_slug][wk_key] += 1
        days_by_k[day_s][k_s] += 1
        days_by_budget[day_s][b_key] += 1
        days_by_style[day_s][st_key] += 1
        k_by_budget[k_s][b_key] += 1
        k_by_style[k_s][st_key] += 1
        support_by_dest[d_slug][sc_key] += 1

    def _imbalance_stats(table: Dict[str, Dict[str, int]]) -> Dict[str, int]:
        vals = [cnt for row in table.values() for cnt in row.values()]
        return {
            "max_cell": max(vals),
            "min_cell": min(vals),
            "max_minus_min": max(vals) - min(vals),
        }

    imbalance = {
        "destination_by_days": _imbalance_stats(dest_by_days),
        "destination_by_interest_count": _imbalance_stats(dest_by_k),
        "destination_by_budget": _imbalance_stats(dest_by_budget),
        "destination_by_style": _imbalance_stats(dest_by_style),
        "destination_by_weekend": _imbalance_stats(dest_by_wk),
        "days_by_interest_count": _imbalance_stats(days_by_k),
        "days_by_budget": _imbalance_stats(days_by_budget),
        "days_by_style": _imbalance_stats(days_by_style),
        "interest_count_by_budget": _imbalance_stats(k_by_budget),
        "interest_count_by_style": _imbalance_stats(k_by_style),
    }

    unavoidable_notes = [
        "100 scenarios across 3 destinations (34/33/33), 3 day lengths (33/34/33), and 3 interest counts (33/34/33) is non-divisible by 3 or 9, making a minimum cell difference of 1 mathematically unavoidable.",
        "Budget marginals (B1=27, B2=27, B3=26, null=20) have uneven tier totals (27 vs 20), so a 3x4 cross-table across 3 destinations/days/interest_counts has an unavoidable spread between B1/B2 (~9 per row) and null (~6-7 per row).",
        "Travel style marginals (25 each across 3 rows of 34/33/33) are not divisible by 3 (25 = 8*3 + 1), making an 8 vs 9 cell count (spread = 1) mathematically unavoidable.",
        "Da Nang has 0 STRESS combinations in the frozen support matrix (all 63 combinations are CLEAR across 2d/3d/4d), whereas Ha Long and Ha Noi contain both CLEAR and STRESS combinations.",
    ]

    return CrossBalanceReport(
        locked_marginal_counts={
            "total_scenarios": len(slots),
            "destination": dest_counts,
            "days": days_counts,
            "interest_count": k_counts,
            "budget": budget_counts,
            "travel_style": style_counts,
            "weekend_exposure": weekend_counts,
        },
        destination_by_days=dest_by_days,
        destination_by_interest_count=dest_by_k,
        destination_by_budget=dest_by_budget,
        destination_by_style=dest_by_style,
        destination_by_weekend=dest_by_wk,
        days_by_interest_count=days_by_k,
        days_by_budget=days_by_budget,
        days_by_style=days_by_style,
        interest_count_by_budget=k_by_budget,
        interest_count_by_style=k_by_style,
        support_class_counts=support_counts,
        support_class_by_destination=support_by_dest,
        max_min_cross_cell_imbalance=imbalance,
        unavoidable_imbalance_notes=unavoidable_notes,
    )


def verify_dry_run_bundle_invariants(
    bundle: DryRunGeneratorBundle,
    method_lock: Dict[str, Any],
    support_matrix: Dict[str, Any],
    catalog_interest_sets: Optional[Dict[str, Dict[str, Set[str]]]] = None,
) -> Dict[str, Any]:
    """Verify all frozen W06 scenario generation invariants on a dry-run bundle; fail closed on violation."""
    if bundle.slot_count != 100 or len(bundle.slots) != 100:
        raise ScenarioGenerationInfeasibleError(
            f"Expected exactly 100 slots, got {len(bundle.slots)}"
        )

    cat_sets = (
        catalog_interest_sets
        if catalog_interest_sets is not None
        else load_direct_catalog_interest_sets()
    )
    caps = method_lock["near_duplicate_policy"]["repeat_caps_by_destination_and_interest_count"]
    daily_nominal = {
        "B1": method_lock["budget_policy"]["nominal_tiers"]["B1"]["daily_nominal_vnd"],
        "B2": method_lock["budget_policy"]["nominal_tiers"]["B2"]["daily_nominal_vnd"],
        "B3": method_lock["budget_policy"]["nominal_tiers"]["B3"]["daily_nominal_vnd"],
    }
    win_start = datetime.date.fromisoformat(method_lock["date_policy"]["window_start_date"])
    win_end = datetime.date.fromisoformat(method_lock["date_policy"]["window_end_date"])

    repeat_counter: Counter[Tuple[str, Tuple[str, ...]]] = Counter()
    seen_signatures: Set[str] = set()
    seen_scenario_ids: Set[str] = set()
    excluded_used = 0

    for idx, slot in enumerate(bundle.slots, start=1):
        if slot.slot_index != idx:
            raise ScenarioGenerationInfeasibleError(f"Non-sequential slot_index at {idx}")
        if slot.scenario_id in seen_scenario_ids:
            raise ScenarioGenerationInfeasibleError(f"Duplicate scenario_id: {slot.scenario_id}")
        seen_scenario_ids.add(slot.scenario_id)

        # Validate through BenchmarkScenarioInput
        validated_input = BenchmarkScenarioInput.model_validate(
            slot.scenario_input.model_dump(mode="json")
        )
        if validated_input.allow_revisit_place_ids is not False:
            raise ScenarioGenerationInfeasibleError(
                f"allow_revisit_place_ids must be False on {slot.scenario_id}"
            )
        if validated_input.fixture_label != DRY_RUN_FIXTURE_LABEL:
            raise ScenarioGenerationInfeasibleError(
                f"fixture_label must be {DRY_RUN_FIXTURE_LABEL!r} on {slot.scenario_id}"
            )

        # Verify canonical interests
        if len(slot.interests) != slot.interest_count:
            raise ScenarioGenerationInfeasibleError(
                f"interest_count mismatch on {slot.scenario_id}"
            )
        if list(slot.interests) != sorted(slot.interests):
            raise ScenarioGenerationInfeasibleError(
                f"Interests not sorted on {slot.scenario_id}"
            )
        for intr in slot.interests:
            if intr not in CANONICAL_BENCHMARK_INTERESTS:
                raise ScenarioGenerationInfeasibleError(
                    f"Non-canonical interest {intr!r} on {slot.scenario_id}"
                )

        # Verify support matrix & direct catalog Rule A and Rule B
        d_entry = support_matrix["destinations"][slot.destination_slug]["by_days"][str(slot.days)]
        matrix_matches = [
            c
            for c in d_entry["combinations"]
            if c["interests_sorted"] == slot.interests
        ]
        if len(matrix_matches) != 1:
            raise ScenarioGenerationInfeasibleError(
                f"Combination {slot.interests} not found in support_matrix for "
                f"{slot.destination_slug} d={slot.days}"
            )
        m_comb = matrix_matches[0]
        direct_eval = verify_combination_direct_support(
            slot.destination_slug,
            slot.days,
            slot.interests,
            cat_sets,
            min_poi_visits_per_day=2,
        )
        if not m_comb["eligible"] or not direct_eval["eligible"]:
            excluded_used += 1
            raise ScenarioGenerationInfeasibleError(
                f"EXCLUDED combination selected on {slot.scenario_id}: {slot.interests}"
            )
        if (
            slot.support_class != m_comb["support_class"]
            or slot.support_class != direct_eval["support_class"]
            or slot.support_class not in ("CLEAR", "STRESS")
        ):
            raise ScenarioGenerationInfeasibleError(
                f"support_class mismatch on {slot.scenario_id}: {slot.support_class}"
            )
        if not slot.rule_a_passed or not slot.rule_b_passed:
            raise ScenarioGenerationInfeasibleError(
                f"Rule A/B flag false on {slot.scenario_id}"
            )

        # Verify budget formula
        if slot.budget_tier_or_null is None:
            if slot.budget is not None:
                raise ScenarioGenerationInfeasibleError(
                    f"Expected budget=None for null tier on {slot.scenario_id}"
                )
        else:
            expected_budget = daily_nominal[slot.budget_tier_or_null] * slot.days
            if slot.budget != expected_budget:
                raise ScenarioGenerationInfeasibleError(
                    f"Budget formula mismatch on {slot.scenario_id}: {slot.budget} != {expected_budget}"
                )

        # Verify contiguous dates inside window and weekend exposure
        s_dt = datetime.date.fromisoformat(slot.start_date)
        e_dt = datetime.date.fromisoformat(slot.end_date)
        if s_dt < win_start or e_dt > win_end:
            raise ScenarioGenerationInfeasibleError(
                f"Date range {slot.start_date}..{slot.end_date} outside window on {slot.scenario_id}"
            )
        if (e_dt - s_dt).days + 1 != slot.days:
            raise ScenarioGenerationInfeasibleError(
                f"Non-contiguous date range on {slot.scenario_id}: {slot.start_date}..{slot.end_date} for {slot.days}d"
            )
        trip_dates = [s_dt + datetime.timedelta(days=offset) for offset in range(slot.days)]
        observed_wk = any(dt.weekday() in (5, 6) for dt in trip_dates)
        if observed_wk != slot.weekend_exposure:
            raise ScenarioGenerationInfeasibleError(
                f"weekend_exposure mismatch on {slot.scenario_id}"
            )

        # Track repeat cap by (destination_slug, sorted(interests)) across all days/budgets/weekend/styles
        combo_key = (slot.destination_slug, tuple(slot.interests))
        repeat_counter[combo_key] += 1
        cap_val = caps[slot.destination_slug][str(slot.interest_count)]["repeat_cap"]
        if repeat_counter[combo_key] > cap_val:
            raise ScenarioGenerationInfeasibleError(
                f"Repeat cap exceeded for {combo_key}: {repeat_counter[combo_key]} > {cap_val}"
            )

        # Verify canonical duplicate signature
        expected_sig = [
            slot.destination_slug,
            slot.days,
            list(slot.interests),
            slot.budget_tier_or_null,
            slot.weekend_exposure,
            slot.travel_style,
        ]
        if slot.canonical_signature != expected_sig:
            raise ScenarioGenerationInfeasibleError(
                f"canonical_signature mismatch on {slot.scenario_id}"
            )
        sig_key = json.dumps(expected_sig, sort_keys=True)
        if sig_key in seen_signatures:
            raise ScenarioGenerationInfeasibleError(
                f"Duplicate canonical signature on {slot.scenario_id}: {expected_sig}"
            )
        seen_signatures.add(sig_key)

    cb = bundle.cross_balance_report
    lm = cb.locked_marginal_counts
    if lm["destination"] != {"ha-noi": 34, "da-nang": 33, "ha-long": 33}:
        raise ScenarioGenerationInfeasibleError(f"Destination marginal mismatch: {lm['destination']}")
    if lm["days"] != {"2": 33, "3": 34, "4": 33}:
        raise ScenarioGenerationInfeasibleError(f"Days marginal mismatch: {lm['days']}")
    if lm["interest_count"] != {"1": 33, "2": 34, "3": 33}:
        raise ScenarioGenerationInfeasibleError(f"Interest count marginal mismatch: {lm['interest_count']}")
    if lm["budget"] != {"B1": 27, "B2": 27, "B3": 26, "null": 20}:
        raise ScenarioGenerationInfeasibleError(f"Budget marginal mismatch: {lm['budget']}")
    if lm["travel_style"] != {"BACKPACKER": 25, "BUDGET": 25, "COMFORT": 25, "LUXURY": 25}:
        raise ScenarioGenerationInfeasibleError(f"Travel style marginal mismatch: {lm['travel_style']}")
    if lm["weekend_exposure"] != {"weekend_exposed": 50, "non_weekend_exposed": 50}:
        raise ScenarioGenerationInfeasibleError(f"Weekend marginal mismatch: {lm['weekend_exposure']}")
    if cb.destination_by_days != method_lock["destination_days_cross_allocation"]:
        raise ScenarioGenerationInfeasibleError("destination_by_days cross-allocation mismatch")
    if cb.destination_by_interest_count != method_lock["destination_interest_count_cross_allocation"]:
        raise ScenarioGenerationInfeasibleError("destination_by_interest_count cross-allocation mismatch")

    return {
        "all_invariants_passed": True,
        "slot_count": 100,
        "excluded_combinations_used": excluded_used,
        "repeat_cap_violations": 0,
        "duplicate_canonical_signatures": 0,
    }


def generate_dry_run_scenarios(
    *,
    seed: int = DEFAULT_SCENARIO_GENERATION_SEED,
    method_lock_path: Optional[Path] = None,
    support_matrix_path: Optional[Path] = None,
    catalog_path: Optional[Path] = None,
    method_lock_override: Optional[Dict[str, Any]] = None,
    support_matrix_override: Optional[Dict[str, Any]] = None,
    manual_reject_candidate_indices: Optional[Set[int]] = None,
) -> DryRunGeneratorBundle:
    """Run the deterministic W06 scenario generator in DRY_RUN / SYNTHETIC_GENERATOR_QA mode.

    Never writes final 100 scenario artifacts or P11.
    Fails closed with ScenarioGenerationInfeasibleError if any constraint is infeasible.
    """
    ml_path = method_lock_path or DEFAULT_METHOD_LOCK_PATH
    sm_path = support_matrix_path or DEFAULT_SUPPORT_MATRIX_PATH

    method_lock = (
        method_lock_override
        if method_lock_override is not None
        else load_method_lock_config(ml_path)
    )
    support_matrix = (
        support_matrix_override
        if support_matrix_override is not None
        else load_support_matrix(sm_path)
    )

    _validate_method_lock_and_support_matrix_invariants(method_lock, support_matrix, seed)
    catalog_interest_sets = load_direct_catalog_interest_sets(catalog_path=catalog_path)

    grid_3d = _build_3d_destination_days_interest_grid(method_lock)
    caps_cfg = method_lock["near_duplicate_policy"]["repeat_caps_by_destination_and_interest_count"]
    date_pools = _enumerate_valid_date_windows(
        method_lock["date_policy"]["window_start_date"],
        method_lock["date_policy"]["window_end_date"],
        seed=seed,
    )
    daily_nominal = {
        "B1": method_lock["budget_policy"]["nominal_tiers"]["B1"]["daily_nominal_vnd"],
        "B2": method_lock["budget_policy"]["nominal_tiers"]["B2"]["daily_nominal_vnd"],
        "B3": method_lock["budget_policy"]["nominal_tiers"]["B3"]["daily_nominal_vnd"],
    }

    manual_rejects = manual_reject_candidate_indices or set()
    rejection_log: List[CandidateRejectionEntry] = []
    candidate_counter = 0

    # Stage 1: Deterministic Selection of (destination_slug, days, interest_count, interests_sorted)
    # respecting Priority 1 (destination), Priority 2 (days), Priority 3 (interest_count),
    # Priority 7 (eligibility), Priority 8 (repeat cap), and Priority 9 (CLEAR/STRESS round-robin).
    partial_slots: List[Dict[str, Any]] = []

    for dest in ORDERED_DESTINATIONS:
        dest_matrix = support_matrix["destinations"][dest]
        used_combo_counts: Counter[Tuple[str, ...]] = Counter()
        support_class_toggle = 0  # Alternates 0 ("CLEAR") and 1 ("STRESS") for round-robin balance

        for k in ORDERED_INTEREST_COUNTS:
            cap_k = int(caps_cfg[dest][str(k)]["repeat_cap"])
            # Process from d=4 down to d=2 so the strictest day threshold selects from its pool first
            for d in (4, 3, 2):
                need = grid_3d[dest][(d, k)]
                raw_combs = [
                    c
                    for c in dest_matrix["by_days"][str(d)]["combinations"]
                    if c["interest_count"] == k
                ]
                # Order all combinations for (dest, d, k) deterministically using seed + combination_id
                ordered_combs = sorted(
                    raw_combs,
                    key=lambda c: (
                        deterministic_tiebreak_digest(seed, f"comb|{dest}|d={d}|k={k}|{c['combination_id']}"),
                        c["combination_id"],
                    ),
                )

                selected_in_cell: List[Dict[str, Any]] = []
                used_in_this_cell: Set[Tuple[str, ...]] = set()

                for _slot_num in range(need):
                    preferred_sc = "CLEAR" if (support_class_toggle % 2 == 0) else "STRESS"
                    support_class_toggle += 1

                    # Determine the minimum used_combo_count among currently valid eligible candidates
                    valid_eligible = [
                        c
                        for c in ordered_combs
                        if c["eligible"] is True
                        and used_combo_counts[tuple(c["interests_sorted"])] < cap_k
                        and tuple(c["interests_sorted"]) not in used_in_this_cell
                    ]
                    if not valid_eligible:
                        # Allow repeating within cell only if repeat_cap permits and distinct pool exhausted
                        valid_eligible = [
                            c
                            for c in ordered_combs
                            if c["eligible"] is True
                            and used_combo_counts[tuple(c["interests_sorted"])] < cap_k
                        ]
                    if not valid_eligible:
                        raise ScenarioGenerationInfeasibleError(
                            f"No eligible interest combination available under repeat_cap={cap_k} "
                            f"for destination={dest}, days={d}, interest_count={k}."
                        )

                    min_used = min(
                        used_combo_counts[tuple(c["interests_sorted"])] for c in valid_eligible
                    )
                    has_preferred_sc_at_min = any(
                        c["support_class"] == preferred_sc
                        and used_combo_counts[tuple(c["interests_sorted"])] == min_used
                        for c in valid_eligible
                    )
                    target_sc = preferred_sc if has_preferred_sc_at_min else (
                        "STRESS" if preferred_sc == "CLEAR" else "CLEAR"
                    )

                    # Scan candidate stream in deterministic order:
                    # 1. Log any EXCLUDED or repeat-capped candidates encountered before acceptance
                    # 2. Accept the first eligible candidate matching (min_used, target_sc)
                    pending_rejection_indices: List[int] = []
                    chosen_comb: Optional[Dict[str, Any]] = None
                    chosen_cand_idx: Optional[int] = None
                    chosen_cand_sha: Optional[str] = None

                    # Order scan stream so candidates matching target_sc at min_used are visited right after
                    # any natural stream candidates that precede them in deterministic order
                    scan_stream = sorted(
                        ordered_combs,
                        key=lambda c: (
                            0
                            if not c["eligible"]
                            or used_combo_counts[tuple(c["interests_sorted"])] >= cap_k
                            else (
                                1
                                if (
                                    used_combo_counts[tuple(c["interests_sorted"])] == min_used
                                    and c["support_class"] == target_sc
                                    and tuple(c["interests_sorted"]) not in used_in_this_cell
                                )
                                else (
                                    2
                                    if (
                                        used_combo_counts[tuple(c["interests_sorted"])] == min_used
                                        and c["support_class"] == target_sc
                                    )
                                    else 3
                                )
                            ),
                            deterministic_tiebreak_digest(
                                seed,
                                f"scan|{dest}|d={d}|k={k}|slot={len(selected_in_cell)}|{c['combination_id']}",
                            ),
                            c["combination_id"],
                        ),
                    )

                    for cand in scan_stream:
                        combo_tuple = tuple(cand["interests_sorted"])
                        # Skip combinations already selected in this exact cell unless no unused remain
                        if (
                            cand["eligible"]
                            and used_combo_counts[combo_tuple] < cap_k
                            and combo_tuple in used_in_this_cell
                            and any(
                                tuple(x["interests_sorted"]) not in used_in_this_cell
                                for x in valid_eligible
                            )
                        ):
                            continue

                        candidate_counter += 1
                        c_idx = candidate_counter
                        cand_repr = {
                            "candidate_index": c_idx,
                            "destination_slug": dest,
                            "days": d,
                            "interest_count": k,
                            "interests_sorted": list(combo_tuple),
                            "combination_id": cand["combination_id"],
                        }
                        c_sha = sha256_hex(canonical_json_bytes(cand_repr))

                        if not cand["eligible"]:
                            reason = (
                                "CATALOG_SUPPORT_BELOW_THRESHOLD"
                                if not cand["rule_a_passed"]
                                else "TOTAL_INTEREST_CAPACITY_INSUFFICIENT"
                            )
                            pending_rejection_indices.append(len(rejection_log))
                            rejection_log.append(
                                CandidateRejectionEntry(
                                    candidate_index=c_idx,
                                    candidate_sha256=c_sha,
                                    reason_code=reason,
                                    rule_version=METHOD_LOCK_RULE_VERSION,
                                    replacement_candidate_index=None,
                                    destination_slug=dest,
                                    days=d,
                                    interest_count=k,
                                    interests_sorted=list(combo_tuple),
                                )
                            )
                            continue

                        if used_combo_counts[combo_tuple] >= cap_k:
                            pending_rejection_indices.append(len(rejection_log))
                            rejection_log.append(
                                CandidateRejectionEntry(
                                    candidate_index=c_idx,
                                    candidate_sha256=c_sha,
                                    reason_code="INTEREST_COMBINATION_REPEAT_CAP",
                                    rule_version=METHOD_LOCK_RULE_VERSION,
                                    replacement_candidate_index=None,
                                    destination_slug=dest,
                                    days=d,
                                    interest_count=k,
                                    interests_sorted=list(combo_tuple),
                                )
                            )
                            continue

                        if c_idx in manual_rejects:
                            pending_rejection_indices.append(len(rejection_log))
                            rejection_log.append(
                                CandidateRejectionEntry(
                                    candidate_index=c_idx,
                                    candidate_sha256=c_sha,
                                    reason_code="MANUAL_QA_REJECT",
                                    rule_version=METHOD_LOCK_RULE_VERSION,
                                    replacement_candidate_index=None,
                                    destination_slug=dest,
                                    days=d,
                                    interest_count=k,
                                    interests_sorted=list(combo_tuple),
                                )
                            )
                            continue

                        # Eligible and within repeat cap
                        chosen_comb = cand
                        chosen_cand_idx = c_idx
                        chosen_cand_sha = c_sha
                        break

                    if chosen_comb is None or chosen_cand_idx is None or chosen_cand_sha is None:
                        raise ScenarioGenerationInfeasibleError(
                            f"Candidate stream exhausted for ({dest}, d={d}, k={k}) without valid candidate."
                        )

                    for r_pos in pending_rejection_indices:
                        rejection_log[r_pos].replacement_candidate_index = chosen_cand_idx

                    combo_tuple = tuple(chosen_comb["interests_sorted"])
                    used_combo_counts[combo_tuple] += 1
                    used_in_this_cell.add(combo_tuple)
                    selected_in_cell.append(
                        {
                            "candidate_index": chosen_cand_idx,
                            "candidate_sha256": chosen_cand_sha,
                            "destination_slug": dest,
                            "days": d,
                            "interest_count": k,
                            "interests_sorted": list(combo_tuple),
                            "support_class": chosen_comb["support_class"],
                            "rule_a_passed": chosen_comb["rule_a_passed"],
                            "rule_b_passed": chosen_comb["rule_b_passed"],
                            "union_support": chosen_comb["union_support"],
                            "sum_support": chosen_comb["sum_support"],
                            "min_interest_support": chosen_comb["min_interest_support"],
                        }
                    )

                partial_slots.extend(selected_in_cell)

    if len(partial_slots) != 100:
        raise ScenarioGenerationInfeasibleError(
            f"Expected 100 partial slots after Stage 1, got {len(partial_slots)}"
        )

    # Order the 100 slots deterministically by (destination_slug order, days asc, interest_count asc, interests)
    dest_rank = {d: i for i, d in enumerate(ORDERED_DESTINATIONS)}
    partial_slots.sort(
        key=lambda s: (
            dest_rank[s["destination_slug"]],
            s["days"],
            s["interest_count"],
            s["interests_sorted"],
            s["candidate_index"],
        )
    )

    # Stage 2: Deterministic Allocation of Budget Tier (Priority 4), Travel Style (Priority 5),
    # Weekend Exposure & Contiguous Dates (Priority 6), Duplicate Signature Prevention (Priority 8),
    # and Cross-Dimension Balance Optimization (Priority 10).
    remaining_budget: Dict[Optional[str], int] = {
        "B1": 27,
        "B2": 27,
        "B3": 26,
        None: 20,
    }
    remaining_style: Dict[str, int] = {
        "BACKPACKER": 25,
        "BUDGET": 25,
        "COMFORT": 25,
        "LUXURY": 25,
    }
    remaining_weekend: Dict[bool, int] = {
        True: 50,
        False: 50,
    }

    budget_by_dest: Counter[Tuple[str, Optional[str]]] = Counter()
    budget_by_days: Counter[Tuple[int, Optional[str]]] = Counter()
    budget_by_k: Counter[Tuple[int, Optional[str]]] = Counter()

    style_by_dest: Counter[Tuple[str, str]] = Counter()
    style_by_days: Counter[Tuple[int, str]] = Counter()
    style_by_k: Counter[Tuple[int, str]] = Counter()
    style_by_budget: Counter[Tuple[Optional[str], str]] = Counter()

    wk_by_dest: Counter[Tuple[str, bool]] = Counter()
    wk_by_days: Counter[Tuple[int, bool]] = Counter()
    wk_by_k: Counter[Tuple[int, bool]] = Counter()

    date_pool_cursors: Counter[Tuple[int, bool]] = Counter()
    seen_canonical_signatures: Set[Tuple[Any, ...]] = set()

    final_slots: List[DryRunScenarioSlot] = []

    for slot_idx, pslot in enumerate(partial_slots, start=1):
        dest = pslot["destination_slug"]
        d = pslot["days"]
        k = pslot["interest_count"]
        interests_tuple = tuple(pslot["interests_sorted"])

        avail_budgets = [b for b in ORDERED_BUDGET_TIERS if remaining_budget[b] > 0]
        if not avail_budgets:
            raise ScenarioGenerationInfeasibleError("No remaining budget quota.")

        # Target share weights for budget tiers (27, 27, 26, 20)
        b_weights = {"B1": 27, "B2": 27, "B3": 26, None: 20}
        avail_budgets.sort(
            key=lambda b: (
                round(
                    max(
                        budget_by_dest[(dest, b)] / b_weights[b],
                        budget_by_days[(d, b)] / b_weights[b],
                        budget_by_k[(k, b)] / b_weights[b],
                    ),
                    9,
                ),
                round(
                    (
                        budget_by_dest[(dest, b)]
                        + budget_by_days[(d, b)]
                        + budget_by_k[(k, b)]
                    )
                    / b_weights[b],
                    9,
                ),
                -remaining_budget[b],
                deterministic_tiebreak_digest(seed, f"budget|slot={slot_idx}|{b}"),
            )
        )

        avail_styles = [st for st in ORDERED_TRAVEL_STYLES if remaining_style[st] > 0]
        if not avail_styles:
            raise ScenarioGenerationInfeasibleError("No remaining travel_style quota.")

        avail_wks = [wk for wk in (True, False) if remaining_weekend[wk] > 0]
        if not avail_wks:
            raise ScenarioGenerationInfeasibleError("No remaining weekend_exposure quota.")

        # Search over ordered (budget, style, weekend) combinations to pick the best balance
        # that does NOT collide with any existing canonical signature
        chosen_tuple: Optional[Tuple[Optional[str], str, bool]] = None
        for b_cand in avail_budgets:
            ranked_styles = sorted(
                avail_styles,
                key=lambda st: (
                    max(
                        style_by_dest[(dest, st)],
                        style_by_days[(d, st)],
                        style_by_k[(k, st)],
                    ),
                    style_by_dest[(dest, st)]
                    + style_by_days[(d, st)]
                    + style_by_k[(k, st)],
                    style_by_budget[(b_cand, st)],
                    -remaining_style[st],
                    deterministic_tiebreak_digest(seed, f"style|slot={slot_idx}|{b_cand}|{st}"),
                ),
            )
            for st_cand in ranked_styles:
                ranked_wks = sorted(
                    avail_wks,
                    key=lambda wk: (
                        max(
                            wk_by_dest[(dest, wk)],
                            wk_by_days[(d, wk)],
                            wk_by_k[(k, wk)],
                        ),
                        wk_by_dest[(dest, wk)]
                        + wk_by_days[(d, wk)]
                        + wk_by_k[(k, wk)],
                        -remaining_weekend[wk],
                        deterministic_tiebreak_digest(
                            seed, f"wk|slot={slot_idx}|{b_cand}|{st_cand}|{wk}"
                        ),
                    ),
                )
                for wk_cand in ranked_wks:
                    sig_tuple = (dest, d, interests_tuple, b_cand, wk_cand, st_cand)
                    if sig_tuple in seen_canonical_signatures:
                        candidate_counter += 1
                        dup_idx = candidate_counter
                        dup_sha = sha256_hex(
                            canonical_json_bytes({"dup_sig": list(sig_tuple), "idx": dup_idx})
                        )
                        rejection_log.append(
                            CandidateRejectionEntry(
                                candidate_index=dup_idx,
                                candidate_sha256=dup_sha,
                                reason_code="NEAR_DUPLICATE_SIGNATURE",
                                rule_version=METHOD_LOCK_RULE_VERSION,
                                replacement_candidate_index=pslot["candidate_index"],
                                destination_slug=dest,
                                days=d,
                                interest_count=k,
                                interests_sorted=list(interests_tuple),
                            )
                        )
                        continue
                    chosen_tuple = (b_cand, st_cand, wk_cand)
                    break
                if chosen_tuple is not None:
                    break
            if chosen_tuple is not None:
                break

        if chosen_tuple is None:
            raise ScenarioGenerationInfeasibleError(
                f"Cannot assign unique canonical signature at slot {slot_idx} for {dest} d={d} {interests_tuple}"
            )

        b_chosen, st_chosen, wk_chosen = chosen_tuple
        remaining_budget[b_chosen] -= 1
        remaining_style[st_chosen] -= 1
        remaining_weekend[wk_chosen] -= 1

        budget_by_dest[(dest, b_chosen)] += 1
        budget_by_days[(d, b_chosen)] += 1
        budget_by_k[(k, b_chosen)] += 1

        style_by_dest[(dest, st_chosen)] += 1
        style_by_days[(d, st_chosen)] += 1
        style_by_k[(k, st_chosen)] += 1
        style_by_budget[(b_chosen, st_chosen)] += 1

        wk_by_dest[(dest, wk_chosen)] += 1
        wk_by_days[(d, wk_chosen)] += 1
        wk_by_k[(k, wk_chosen)] += 1

        sig_tuple = (dest, d, interests_tuple, b_chosen, wk_chosen, st_chosen)
        seen_canonical_signatures.add(sig_tuple)

        # Deterministic date assignment from valid pool for (d, wk_chosen)
        pool = date_pools[(d, wk_chosen)]
        cursor = date_pool_cursors[(d, wk_chosen)]
        start_date_str, end_date_str = pool[cursor % len(pool)]
        date_pool_cursors[(d, wk_chosen)] += 1

        numeric_budget = None if b_chosen is None else daily_nominal[b_chosen] * d
        scenario_id = f"{DRY_RUN_SCENARIO_ID_PREFIX}-{slot_idx:03d}"
        dest_display = PRIMARY_BENCHMARK_DESTINATIONS[dest]

        scenario_obj = BenchmarkScenarioInput(
            scenario_id=scenario_id,
            destination_slug=dest,
            destination=dest_display,
            days=d,
            start_date=start_date_str,
            end_date=end_date_str,
            budget=numeric_budget,
            currency="VND",
            travel_style=st_chosen,
            interests=list(interests_tuple),
            notes=None,
            allow_revisit_place_ids=False,
            fixture_label=DRY_RUN_FIXTURE_LABEL,
        )

        canonical_sig_list: List[Any] = [
            dest,
            d,
            list(interests_tuple),
            b_chosen,
            wk_chosen,
            st_chosen,
        ]
        canonical_sig_sha = sha256_hex(canonical_json_bytes(canonical_sig_list))

        final_slots.append(
            DryRunScenarioSlot(
                slot_index=slot_idx,
                scenario_id=scenario_id,
                candidate_index=pslot["candidate_index"],
                candidate_sha256=pslot["candidate_sha256"],
                destination_slug=dest,
                destination=dest_display,
                days=d,
                interest_count=k,
                interests=list(interests_tuple),
                support_class=pslot["support_class"],
                rule_a_passed=pslot["rule_a_passed"],
                rule_b_passed=pslot["rule_b_passed"],
                union_support=pslot["union_support"],
                sum_support=pslot["sum_support"],
                min_interest_support=pslot["min_interest_support"],
                budget_tier_or_null=b_chosen,
                budget=numeric_budget,
                currency="VND",
                travel_style=st_chosen,
                weekend_exposure=wk_chosen,
                start_date=start_date_str,
                end_date=end_date_str,
                canonical_signature=canonical_sig_list,
                canonical_signature_sha256=canonical_sig_sha,
                scenario_input=scenario_obj,
            )
        )

    cross_report = build_cross_balance_report(final_slots)
    reason_counts_counter: Counter[str] = Counter(r.reason_code for r in rejection_log)
    rejection_reason_counts = {
        code: reason_counts_counter[code]
        for code in sorted(reason_counts_counter.keys())
    }

    ml_sha = lf_normalized_file_sha256(ml_path) if ml_path.exists() else "0" * 64
    sm_sha = lf_normalized_file_sha256(sm_path) if sm_path.exists() else "0" * 64

    bundle = DryRunGeneratorBundle(
        generator_version=SCENARIO_GENERATOR_VERSION,
        run_mode=DRY_RUN_MODE,
        fixture_label=DRY_RUN_FIXTURE_LABEL,
        is_final_100_scenarios=False,
        real_scenarios_generated=False,
        p11_created=False,
        preregistration_created=False,
        gemini_called=False,
        seed=seed,
        method_lock_id=method_lock["method_lock_id"],
        method_lock_version=method_lock["method_lock_version"],
        method_lock_sha256=ml_sha,
        support_matrix_id=support_matrix["artifact_id"],
        support_matrix_version=support_matrix["artifact_version"],
        support_matrix_sha256=sm_sha,
        slot_count=len(final_slots),
        slots=final_slots,
        rejection_log_count=len(rejection_log),
        rejection_reason_counts=rejection_reason_counts,
        rejection_log=rejection_log,
        cross_balance_report=cross_report,
        invariants_verified={},
    )

    invariants = verify_dry_run_bundle_invariants(
        bundle,
        method_lock,
        support_matrix,
        catalog_interest_sets=catalog_interest_sets,
    )
    bundle.invariants_verified = invariants
    return bundle
