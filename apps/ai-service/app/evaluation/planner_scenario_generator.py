"""Deterministic W06 Benchmark Scenario Generator Engine (W06-SCENARIO-GENERATOR-01).

Grounded in:
- data/evaluation/w06/w06_scenario_method_lock_v1.json (W06-SCENARIO-METHOD-LOCK-01 v1.0.0)
- data/evaluation/w06/w06_scenario_support_matrix_v1.json (W06-SCENARIO-SUPPORT-MATRIX-V1 v1.0.0)
- data/curated/gomate_places_freeze_v2.json (REC-A-CORE-V2 frozen catalog)
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
DEFAULT_RECA_CONTRACT_PATH = (
    REPO_ROOT / "apps" / "ai-service" / "recommendation" / "reca" / "contract.py"
)

EXPECTED_METHOD_LOCK_LF_SHA256: str = (
    "5e5359f9f10a0248a9cf031f8e8b26c0314c46aecfe0d9df479388bbe4fd1af9"
)
EXPECTED_SUPPORT_MATRIX_LF_SHA256: str = (
    "68c2bfc2164e664b3856c31b99a92d75a588f64465526b47c9104918a51cedb4"
)
EXPECTED_CATALOG_LF_SHA256: str = (
    "f7517938598e3923906763f8f31334a500ee88bc06232f2992d38e2fcb28a444"
)
EXPECTED_RECA_CONTRACT_LF_SHA256: str = (
    "1a62c36a95092be35ab78dca43e20f646016e154746ee051a499bdebfc67538c"
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

FROZEN_EXECUTABLE_PRIORITY_TRACE: Tuple[str, ...] = (
    "DESTINATION_ALLOCATION",
    "DAYS_ALLOCATION",
    "INTEREST_COUNT_ALLOCATION",
    "BUDGET_ALLOCATION",
    "TRAVEL_STYLE_ALLOCATION",
    "WEEKEND_EXPOSURE_ALLOCATION",
    "SCENARIO_ELIGIBILITY",
    "DUPLICATE_REPEAT_CAP",
    "CLEAR_STRESS_COVERAGE",
    "CROSS_DIMENSION_IMBALANCE",
)

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


class PhaseBLockedSlot(BaseModel):
    """Immutable slot state locked at the end of Phase B (Priorities 1..6).

    Created before Phase C (Priorities 7..9) evaluates or selects any interest combination.
    Frozen so Phase C can never silently alter Priorities 1..6 to rescue an infeasible candidate.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    slot_index: int = Field(..., ge=1, le=100)
    destination_slug: str
    destination: str
    days: int
    interest_count: int
    budget_tier_or_null: Optional[str] = None
    budget: Optional[int] = None
    currency: str = "VND"
    travel_style: str
    weekend_exposure: bool
    start_date: str
    end_date: str


class ScenarioGenerationInfeasibleError(ValueError):
    """Raised when scenario generation constraints are mathematically or structurally infeasible.

    Enforces fail-closed behavior under STOP_DO_NOT_SILENTLY_RELAX_REQUIRE_FORMAL_METHOD_AMENDMENT.
    Carries any already-locked Phase B slots and executable priority trace for audit inspection.
    """

    def __init__(
        self,
        reason: str,
        protocol_status: str = INFEASIBILITY_PROTOCOL_STATUS,
        *,
        phase_b_slots: Optional[Sequence[PhaseBLockedSlot]] = None,
        executable_priority_trace: Optional[Sequence[str]] = None,
    ) -> None:
        self.reason = reason
        self.protocol_status = protocol_status
        self.phase_b_slots: Optional[Tuple[PhaseBLockedSlot, ...]] = (
            tuple(phase_b_slots) if phase_b_slots is not None else None
        )
        self.executable_priority_trace: Optional[Tuple[str, ...]] = (
            tuple(executable_priority_trace)
            if executable_priority_trace is not None
            else None
        )
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
    catalog_sha256: str
    reca_contract_sha256: str
    executable_priority_trace: List[str]
    phase_b_locked_slots_sha256: str
    slot_count: int
    slots: List[DryRunScenarioSlot]
    rejection_log_count: int
    rejection_reason_counts: Dict[str, int]
    rejection_log: List[CandidateRejectionEntry]
    cross_balance_report: CrossBalanceReport
    invariants_verified: Dict[str, Any]


def load_method_lock_config(
    path: Optional[Path] = None,
    *,
    enforce_frozen_hash: bool = True,
) -> Dict[str, Any]:
    """Load and validate the frozen W06 scenario method lock JSON."""
    target = path or DEFAULT_METHOD_LOCK_PATH
    if not target.exists():
        raise ScenarioGenerationInfeasibleError(f"Missing method lock file: {target}")
    if enforce_frozen_hash:
        actual_sha = lf_normalized_file_sha256(target)
        if actual_sha != EXPECTED_METHOD_LOCK_LF_SHA256:
            raise ScenarioGenerationInfeasibleError(
                f"Method lock file SHA256 mismatch at {target}: "
                f"{actual_sha} != {EXPECTED_METHOD_LOCK_LF_SHA256}"
            )
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


def load_support_matrix(
    path: Optional[Path] = None,
    *,
    expected_sha256: str = EXPECTED_SUPPORT_MATRIX_LF_SHA256,
) -> Dict[str, Any]:
    """Load and validate the frozen W06 scenario support matrix JSON."""
    target = path or DEFAULT_SUPPORT_MATRIX_PATH
    if not target.exists():
        raise ScenarioGenerationInfeasibleError(f"Missing support matrix file: {target}")
    actual_sha = lf_normalized_file_sha256(target)
    if actual_sha != expected_sha256 or actual_sha != EXPECTED_SUPPORT_MATRIX_LF_SHA256:
        raise ScenarioGenerationInfeasibleError(
            f"Support matrix SHA256 mismatch at {target}: "
            f"{actual_sha} != {expected_sha256}"
        )
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


def verify_runtime_scientific_authorities(
    method_lock: Dict[str, Any],
    *,
    catalog_path: Optional[Path] = None,
    reca_contract_path: Optional[Path] = None,
    support_matrix_path: Optional[Path] = None,
    verify_support_matrix_file: bool = True,
) -> Dict[str, str]:
    """Verify frozen runtime authorities (Catalog, REC-A contract, Support Matrix) against Method Lock.

    Fails closed with ScenarioGenerationInfeasibleError on any mismatch.
    """
    im = method_lock.get("interest_mapping")
    if not isinstance(im, dict):
        raise ScenarioGenerationInfeasibleError(
            "Method lock missing authoritative 'interest_mapping' block."
        )

    lock_cat_sha = im.get("catalog_lf_sha256")
    lock_reca_sha = im.get("source_file_lf_sha256")
    lock_sm_sha = im.get("pre_freeze_support_matrix_sha256")
    lock_fn_name = im.get("function_name")
    lock_cat_rel = im.get("catalog_file_path")
    lock_reca_rel = im.get("source_file_path")
    lock_sm_rel = im.get("pre_freeze_support_matrix_path")

    if lock_cat_rel != "data/curated/gomate_places_freeze_v2.json":
        raise ScenarioGenerationInfeasibleError(
            f"Method lock catalog_file_path mismatch: {lock_cat_rel!r}"
        )
    if lock_cat_sha != EXPECTED_CATALOG_LF_SHA256:
        raise ScenarioGenerationInfeasibleError(
            f"Method lock catalog_lf_sha256 mismatch: {lock_cat_sha!r} != {EXPECTED_CATALOG_LF_SHA256!r}"
        )
    if lock_reca_rel != "apps/ai-service/recommendation/reca/contract.py":
        raise ScenarioGenerationInfeasibleError(
            f"Method lock source_file_path mismatch: {lock_reca_rel!r}"
        )
    if lock_reca_sha != EXPECTED_RECA_CONTRACT_LF_SHA256:
        raise ScenarioGenerationInfeasibleError(
            f"Method lock source_file_lf_sha256 mismatch: {lock_reca_sha!r} != {EXPECTED_RECA_CONTRACT_LF_SHA256!r}"
        )
    if lock_fn_name != "poi_to_canonical_vector":
        raise ScenarioGenerationInfeasibleError(
            f"Method lock interest_mapping.function_name mismatch: {lock_fn_name!r}"
        )
    if lock_sm_rel != "data/evaluation/w06/w06_scenario_support_matrix_v1.json":
        raise ScenarioGenerationInfeasibleError(
            f"Method lock pre_freeze_support_matrix_path mismatch: {lock_sm_rel!r}"
        )
    if lock_sm_sha != EXPECTED_SUPPORT_MATRIX_LF_SHA256:
        raise ScenarioGenerationInfeasibleError(
            f"Method lock pre_freeze_support_matrix_sha256 mismatch: {lock_sm_sha!r} != {EXPECTED_SUPPORT_MATRIX_LF_SHA256!r}"
        )

    cat_target = catalog_path or (REPO_ROOT / lock_cat_rel)
    if not cat_target.exists():
        raise ScenarioGenerationInfeasibleError(f"Missing catalog file: {cat_target}")
    actual_cat_sha = lf_normalized_file_sha256(cat_target)
    if actual_cat_sha != lock_cat_sha or actual_cat_sha != EXPECTED_CATALOG_LF_SHA256:
        raise ScenarioGenerationInfeasibleError(
            f"Frozen catalog LF SHA256 mismatch at {cat_target}: "
            f"{actual_cat_sha} != {lock_cat_sha}"
        )

    reca_target = reca_contract_path or (REPO_ROOT / lock_reca_rel)
    if not reca_target.exists():
        raise ScenarioGenerationInfeasibleError(
            f"Missing REC-A mapping source file: {reca_target}"
        )
    actual_reca_sha = lf_normalized_file_sha256(reca_target)
    if actual_reca_sha != lock_reca_sha or actual_reca_sha != EXPECTED_RECA_CONTRACT_LF_SHA256:
        raise ScenarioGenerationInfeasibleError(
            f"Frozen REC-A contract LF SHA256 mismatch at {reca_target}: "
            f"{actual_reca_sha} != {lock_reca_sha}"
        )

    sm_target = support_matrix_path or (REPO_ROOT / lock_sm_rel)
    if not sm_target.exists():
        raise ScenarioGenerationInfeasibleError(
            f"Missing support matrix file: {sm_target}"
        )
    actual_sm_sha = lf_normalized_file_sha256(sm_target)
    if verify_support_matrix_file and (
        actual_sm_sha != lock_sm_sha or actual_sm_sha != EXPECTED_SUPPORT_MATRIX_LF_SHA256
    ):
        raise ScenarioGenerationInfeasibleError(
            f"Frozen support matrix SHA256 mismatch at {sm_target}: "
            f"{actual_sm_sha} != {lock_sm_sha}"
        )

    return {
        "catalog_sha256": actual_cat_sha,
        "reca_contract_sha256": actual_reca_sha,
        "support_matrix_sha256": actual_sm_sha,
    }


def load_direct_catalog_interest_sets(
    catalog_path: Optional[Path] = None,
    *,
    reca_contract_path: Optional[Path] = None,
    expected_catalog_sha256: str = EXPECTED_CATALOG_LF_SHA256,
    expected_reca_sha256: str = EXPECTED_RECA_CONTRACT_LF_SHA256,
) -> Dict[str, Dict[str, Set[str]]]:
    """Build destination -> canonical_interest -> set(place_id) directly from REC-A-CORE-V2 catalog."""
    target = catalog_path or DEFAULT_CATALOG_PATH
    if not target.exists():
        raise ScenarioGenerationInfeasibleError(f"Missing catalog file: {target}")
    actual_cat_sha = lf_normalized_file_sha256(target)
    if actual_cat_sha != expected_catalog_sha256 or actual_cat_sha != EXPECTED_CATALOG_LF_SHA256:
        raise ScenarioGenerationInfeasibleError(
            f"Frozen catalog LF SHA256 mismatch at {target}: "
            f"{actual_cat_sha} != {expected_catalog_sha256}"
        )

    rc_target = reca_contract_path or DEFAULT_RECA_CONTRACT_PATH
    if not rc_target.exists():
        raise ScenarioGenerationInfeasibleError(f"Missing REC-A contract file: {rc_target}")
    actual_reca_sha = lf_normalized_file_sha256(rc_target)
    if actual_reca_sha != expected_reca_sha256 or actual_reca_sha != EXPECTED_RECA_CONTRACT_LF_SHA256:
        raise ScenarioGenerationInfeasibleError(
            f"Frozen REC-A contract LF SHA256 mismatch at {rc_target}: "
            f"{actual_reca_sha} != {expected_reca_sha256}"
        )

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
    """Validate all frozen marginals, priority order, and repeat caps before allocation; fail closed on mismatch."""
    seed_policy = method_lock.get("generation_seed_policy", {})
    expected_seed = seed_policy.get("scenario_generation_seed")
    if (
        seed_policy.get("allowed_seed_count") != 1
        or seed_policy.get("seed_shopping_allowed") is not False
    ):
        raise ScenarioGenerationInfeasibleError(
            "Seed policy violated: allowed_seed_count must be 1 and seed_shopping_allowed must be False."
        )
    if seed != expected_seed:
        raise ScenarioGenerationInfeasibleError(
            f"Generator seed {seed} does not match frozen scenario_generation_seed {expected_seed}."
        )

    expected_priority_order = [
        {"priority": 1, "rule": "exact destination allocation"},
        {"priority": 2, "rule": "exact days marginal"},
        {"priority": 3, "rule": "exact interest-count marginal"},
        {"priority": 4, "rule": "exact budget applicability/tier marginal"},
        {"priority": 5, "rule": "exact travel-style marginal"},
        {"priority": 6, "rule": "exact weekend-exposure marginal"},
        {"priority": 7, "rule": "scenario eligibility"},
        {"priority": 8, "rule": "duplicate/near-duplicate rules"},
        {"priority": 9, "rule": "CLEAR/STRESS coverage"},
        {"priority": 10, "rule": "minimize remaining cross-dimension imbalance"},
    ]
    actual_priority_order = method_lock.get("generator_policy", {}).get("priority_order")
    if actual_priority_order != expected_priority_order:
        raise ScenarioGenerationInfeasibleError(
            f"Method lock priority_order mismatch: {actual_priority_order!r}"
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
    if tl.get("allowed_days") != [2, 3, 4] or tl.get("marginal_counts") != {
        "2": 33,
        "3": 34,
        "4": 33,
    }:
        raise ScenarioGenerationInfeasibleError(f"Trip length target mismatch: {tl!r}")

    ic = method_lock.get("interest_count_target", {})
    if ic.get("allowed_interest_counts") != [1, 2, 3] or ic.get("marginal_counts") != {
        "1": 33,
        "2": 34,
        "3": 33,
    }:
        raise ScenarioGenerationInfeasibleError(f"Interest count target mismatch: {ic!r}")
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
        raise ScenarioGenerationInfeasibleError(f"Budget policy mismatch: {bp!r}")

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
        raise ScenarioGenerationInfeasibleError(f"Date policy mismatch: {dp!r}")

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


def _run_phase_a_allocate_core_marginals(
    method_lock: Dict[str, Any],
    execution_trace: List[str],
) -> List[Dict[str, Any]]:
    """PHASE A: Execute Priorities 1, 2, and 3 in strict sequence.

    1. DESTINATION_ALLOCATION: exact 34/33/33 destination slots
    2. DAYS_ALLOCATION: exact 33/34/33 days marginal & destination x days matrix
    3. INTEREST_COUNT_ALLOCATION: exact 33/34/33 interest_count marginal & destination x interest_count matrix
    """
    # Priority 1: Exact destination allocation
    dest_alloc = method_lock["primary_benchmark"]["destination_allocation"]
    dest_slots: List[Dict[str, Any]] = []
    slot_idx = 0
    for dest in ORDERED_DESTINATIONS:
        count = int(dest_alloc[dest])
        for _ in range(count):
            slot_idx += 1
            dest_slots.append(
                {
                    "slot_index": slot_idx,
                    "destination_slug": dest,
                    "destination": PRIMARY_BENCHMARK_DESTINATIONS[dest],
                }
            )
    if len(dest_slots) != 100:
        raise ScenarioGenerationInfeasibleError(
            f"Priority 1 destination allocation produced {len(dest_slots)} slots, expected 100."
        )
    execution_trace.append("DESTINATION_ALLOCATION")

    # Priority 2: Exact days marginal & destination x days cross-allocation
    cross_d = method_lock["destination_days_cross_allocation"]
    cursor = 0
    for dest in ORDERED_DESTINATIONS:
        for d in ORDERED_DAYS:
            need_d = int(cross_d[dest][str(d)])
            for _ in range(need_d):
                if dest_slots[cursor]["destination_slug"] != dest:
                    raise ScenarioGenerationInfeasibleError(
                        "Destination slot alignment mismatch during Priority 2 days allocation."
                    )
                dest_slots[cursor]["days"] = d
                cursor += 1
    if cursor != 100:
        raise ScenarioGenerationInfeasibleError(
            f"Priority 2 days allocation assigned {cursor} slots, expected 100."
        )
    execution_trace.append("DAYS_ALLOCATION")

    # Priority 3: Exact interest_count marginal & destination x interest_count cross-allocation
    grid_3d = _build_3d_destination_days_interest_grid(method_lock)
    cursor = 0
    for dest in ORDERED_DESTINATIONS:
        for d in ORDERED_DAYS:
            for k in ORDERED_INTEREST_COUNTS:
                need_dk = int(grid_3d[dest][(d, k)])
                for _ in range(need_dk):
                    slot = dest_slots[cursor]
                    if slot["destination_slug"] != dest or slot["days"] != d:
                        raise ScenarioGenerationInfeasibleError(
                            "Slot alignment mismatch during Priority 3 interest_count allocation."
                        )
                    slot["interest_count"] = k
                    cursor += 1
    if cursor != 100:
        raise ScenarioGenerationInfeasibleError(
            f"Priority 3 interest_count allocation assigned {cursor} slots, expected 100."
        )
    execution_trace.append("INTEREST_COUNT_ALLOCATION")

    return dest_slots


def _run_phase_b_allocate_secondary_marginals(
    phase_a_slots: Sequence[Dict[str, Any]],
    method_lock: Dict[str, Any],
    seed: int,
    execution_trace: List[str],
) -> Tuple[PhaseBLockedSlot, ...]:
    """PHASE B: Execute Priorities 4, 5, and 6 in strict sequence BEFORE any interest selection.

    4. BUDGET_ALLOCATION: exact B1=27, B2=27, B3=26, null=20 across all 100 slots
    5. TRAVEL_STYLE_ALLOCATION: exact 25 each of BACKPACKER, BUDGET, COMFORT, LUXURY across all 100 slots
    6. WEEKEND_EXPOSURE_ALLOCATION: exact 50/50 weekend exposure and valid contiguous dates across all 100 slots
    """
    working_slots = [dict(s) for s in phase_a_slots]
    daily_nominal = {
        "B1": method_lock["budget_policy"]["nominal_tiers"]["B1"]["daily_nominal_vnd"],
        "B2": method_lock["budget_policy"]["nominal_tiers"]["B2"]["daily_nominal_vnd"],
        "B3": method_lock["budget_policy"]["nominal_tiers"]["B3"]["daily_nominal_vnd"],
    }

    # Priority 4: Exact budget applicability/tier marginal across all 100 slots
    remaining_budget: Dict[Optional[str], int] = {
        "B1": 27,
        "B2": 27,
        "B3": 26,
        None: 20,
    }
    b_weights = {"B1": 27, "B2": 27, "B3": 26, None: 20}
    budget_by_dest: Counter[Tuple[str, Optional[str]]] = Counter()
    budget_by_days: Counter[Tuple[int, Optional[str]]] = Counter()
    budget_by_k: Counter[Tuple[int, Optional[str]]] = Counter()

    for slot in working_slots:
        s_idx = slot["slot_index"]
        dest = slot["destination_slug"]
        d = slot["days"]
        k = slot["interest_count"]
        avail_budgets = [b for b in ORDERED_BUDGET_TIERS if remaining_budget[b] > 0]
        if not avail_budgets:
            raise ScenarioGenerationInfeasibleError("No remaining budget quota in Priority 4.")
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
                deterministic_tiebreak_digest(seed, f"budget|slot={s_idx}|{b}"),
            )
        )
        b_chosen = avail_budgets[0]
        remaining_budget[b_chosen] -= 1
        budget_by_dest[(dest, b_chosen)] += 1
        budget_by_days[(d, b_chosen)] += 1
        budget_by_k[(k, b_chosen)] += 1
        slot["budget_tier_or_null"] = b_chosen
        slot["budget"] = None if b_chosen is None else daily_nominal[b_chosen] * d
        slot["currency"] = "VND"

    execution_trace.append("BUDGET_ALLOCATION")

    # Priority 5: Exact travel-style marginal across all 100 slots
    remaining_style: Dict[str, int] = {
        "BACKPACKER": 25,
        "BUDGET": 25,
        "COMFORT": 25,
        "LUXURY": 25,
    }
    style_by_dest: Counter[Tuple[str, str]] = Counter()
    style_by_days: Counter[Tuple[int, str]] = Counter()
    style_by_k: Counter[Tuple[int, str]] = Counter()
    style_by_budget: Counter[Tuple[Optional[str], str]] = Counter()

    for slot in working_slots:
        s_idx = slot["slot_index"]
        dest = slot["destination_slug"]
        d = slot["days"]
        k = slot["interest_count"]
        b_chosen = slot["budget_tier_or_null"]
        avail_styles = [st for st in ORDERED_TRAVEL_STYLES if remaining_style[st] > 0]
        if not avail_styles:
            raise ScenarioGenerationInfeasibleError("No remaining travel_style quota in Priority 5.")
        avail_styles.sort(
            key=lambda st: (
                max(
                    style_by_dest[(dest, st)],
                    style_by_days[(d, st)],
                    style_by_k[(k, st)],
                ),
                style_by_dest[(dest, st)]
                + style_by_days[(d, st)]
                + style_by_k[(k, st)],
                style_by_budget[(b_chosen, st)],
                -remaining_style[st],
                deterministic_tiebreak_digest(seed, f"style|slot={s_idx}|{b_chosen}|{st}"),
            )
        )
        st_chosen = avail_styles[0]
        remaining_style[st_chosen] -= 1
        style_by_dest[(dest, st_chosen)] += 1
        style_by_days[(d, st_chosen)] += 1
        style_by_k[(k, st_chosen)] += 1
        style_by_budget[(b_chosen, st_chosen)] += 1
        slot["travel_style"] = st_chosen

    execution_trace.append("TRAVEL_STYLE_ALLOCATION")

    # Priority 6: Exact weekend-exposure marginal and deterministic contiguous dates across all 100 slots
    remaining_weekend: Dict[bool, int] = {
        True: 50,
        False: 50,
    }
    wk_by_dest: Counter[Tuple[str, bool]] = Counter()
    wk_by_days: Counter[Tuple[int, bool]] = Counter()
    wk_by_k: Counter[Tuple[int, bool]] = Counter()
    wk_by_budget: Counter[Tuple[Optional[str], bool]] = Counter()
    wk_by_style: Counter[Tuple[str, bool]] = Counter()

    date_pools = _enumerate_valid_date_windows(
        method_lock["date_policy"]["window_start_date"],
        method_lock["date_policy"]["window_end_date"],
        seed=seed,
    )
    date_pool_cursors: Counter[Tuple[int, bool]] = Counter()

    locked_slots: List[PhaseBLockedSlot] = []
    for slot in working_slots:
        s_idx = slot["slot_index"]
        dest = slot["destination_slug"]
        d = slot["days"]
        k = slot["interest_count"]
        b_chosen = slot["budget_tier_or_null"]
        st_chosen = slot["travel_style"]

        avail_wks = [wk for wk in (True, False) if remaining_weekend[wk] > 0]
        if not avail_wks:
            raise ScenarioGenerationInfeasibleError(
                "No remaining weekend_exposure quota in Priority 6."
            )
        avail_wks.sort(
            key=lambda wk: (
                max(
                    wk_by_dest[(dest, wk)],
                    wk_by_days[(d, wk)],
                    wk_by_k[(k, wk)],
                ),
                wk_by_dest[(dest, wk)]
                + wk_by_days[(d, wk)]
                + wk_by_k[(k, wk)],
                wk_by_budget[(b_chosen, wk)] + wk_by_style[(st_chosen, wk)],
                -remaining_weekend[wk],
                deterministic_tiebreak_digest(
                    seed, f"wk|slot={s_idx}|{b_chosen}|{st_chosen}|{wk}"
                ),
            )
        )
        wk_chosen = avail_wks[0]
        remaining_weekend[wk_chosen] -= 1
        wk_by_dest[(dest, wk_chosen)] += 1
        wk_by_days[(d, wk_chosen)] += 1
        wk_by_k[(k, wk_chosen)] += 1
        wk_by_budget[(b_chosen, wk_chosen)] += 1
        wk_by_style[(st_chosen, wk_chosen)] += 1

        pool = date_pools[(d, wk_chosen)]
        cursor = date_pool_cursors[(d, wk_chosen)]
        start_date_str, end_date_str = pool[cursor % len(pool)]
        date_pool_cursors[(d, wk_chosen)] += 1

        locked_slots.append(
            PhaseBLockedSlot(
                slot_index=s_idx,
                destination_slug=dest,
                destination=slot["destination"],
                days=d,
                interest_count=k,
                budget_tier_or_null=b_chosen,
                budget=slot["budget"],
                currency=slot["currency"],
                travel_style=st_chosen,
                weekend_exposure=wk_chosen,
                start_date=start_date_str,
                end_date=end_date_str,
            )
        )

    execution_trace.append("WEEKEND_EXPOSURE_ALLOCATION")
    return tuple(locked_slots)


def _run_phase_c_select_eligible_interests(
    phase_b_slots: Tuple[PhaseBLockedSlot, ...],
    method_lock: Dict[str, Any],
    support_matrix: Dict[str, Any],
    catalog_interest_sets: Dict[str, Dict[str, Set[str]]],
    seed: int,
    manual_rejects: Set[int],
    execution_trace: List[str],
) -> Tuple[List[DryRunScenarioSlot], List[CandidateRejectionEntry]]:
    """PHASE C: Execute Priorities 7, 8, and 9 under already-locked Priorities 1..6.

    7. SCENARIO_ELIGIBILITY: evaluate Rule A and Rule B on all candidate combinations
    8. DUPLICATE_REPEAT_CAP: enforce repeat caps and canonical signature uniqueness against locked Phase B slots
    9. CLEAR_STRESS_COVERAGE: apply deterministic round-robin CLEAR/STRESS selection among admissible candidates

    Never modifies Phase B slot assignments; fails closed with ScenarioGenerationInfeasibleError
    if any slot cannot be satisfied under its locked Priority 1..6 assignments.
    """
    # Priority 7: Evaluate and verify candidate combination eligibility across all (dest, d, k) cells
    cell_ordered_combs: Dict[Tuple[str, int, int], List[Dict[str, Any]]] = {}
    for dest in ORDERED_DESTINATIONS:
        dest_matrix = support_matrix["destinations"][dest]
        for k in ORDERED_INTEREST_COUNTS:
            for d in ORDERED_DAYS:
                raw_combs = [
                    c
                    for c in dest_matrix["by_days"][str(d)]["combinations"]
                    if c["interest_count"] == k
                ]
                for c in raw_combs:
                    direct_eval = verify_combination_direct_support(
                        dest,
                        d,
                        c["interests_sorted"],
                        catalog_interest_sets,
                        min_poi_visits_per_day=2,
                    )
                    # Cross-check support matrix against direct catalog evaluation unless matrix was overridden
                    # to mark a combination EXCLUDED for infeasibility testing
                    if c["eligible"] is True and not direct_eval["eligible"]:
                        raise ScenarioGenerationInfeasibleError(
                            f"Support matrix marks {c['interests_sorted']} eligible for {dest} d={d}, "
                            "but direct catalog evaluation failed Rule A/B.",
                            phase_b_slots=phase_b_slots,
                            executable_priority_trace=execution_trace,
                        )
                ordered_combs = sorted(
                    raw_combs,
                    key=lambda c: (
                        deterministic_tiebreak_digest(
                            seed, f"comb|{dest}|d={d}|k={k}|{c['combination_id']}"
                        ),
                        c["combination_id"],
                    ),
                )
                if not any(c["eligible"] is True for c in ordered_combs):
                    execution_trace.append("SCENARIO_ELIGIBILITY")
                    raise ScenarioGenerationInfeasibleError(
                        f"Zero eligible combinations in Priority 7 for destination={dest}, days={d}, interest_count={k}.",
                        phase_b_slots=phase_b_slots,
                        executable_priority_trace=execution_trace,
                    )
                cell_ordered_combs[(dest, d, k)] = ordered_combs

    execution_trace.append("SCENARIO_ELIGIBILITY")

    # Priorities 8 & 9: Enforce repeat-cap + canonical duplicate rules and CLEAR/STRESS coverage
    # on the fixed PhaseBLockedSlot objects without mutating Priorities 1..6
    caps_cfg = method_lock["near_duplicate_policy"]["repeat_caps_by_destination_and_interest_count"]
    rejection_log: List[CandidateRejectionEntry] = []
    candidate_counter = 0
    seen_canonical_signatures: Set[Tuple[Any, ...]] = set()
    assigned_by_slot_index: Dict[int, DryRunScenarioSlot] = {}

    execution_trace.append("DUPLICATE_REPEAT_CAP")
    execution_trace.append("CLEAR_STRESS_COVERAGE")

    for dest in ORDERED_DESTINATIONS:
        used_combo_counts: Counter[Tuple[str, ...]] = Counter()
        support_class_toggle = 0

        for k in ORDERED_INTEREST_COUNTS:
            cap_k = int(caps_cfg[dest][str(k)]["repeat_cap"])
            # Process locked slots for (dest, k) from strictest day threshold d=4 down to d=2
            # without altering any locked slot's Priority 1..6 attributes
            for d in (4, 3, 2):
                cell_slots = [
                    pslot
                    for pslot in phase_b_slots
                    if pslot.destination_slug == dest
                    and pslot.days == d
                    and pslot.interest_count == k
                ]
                ordered_combs = cell_ordered_combs[(dest, d, k)]
                used_in_this_cell: Set[Tuple[str, ...]] = set()

                for cell_pos, pslot in enumerate(cell_slots):
                    preferred_sc = "CLEAR" if (support_class_toggle % 2 == 0) else "STRESS"
                    support_class_toggle += 1

                    def _is_admissible_under_p7_p8(
                        cand_obj: Dict[str, Any],
                        *,
                        require_unused_in_cell: bool,
                        _pslot: PhaseBLockedSlot = pslot,
                        _cap_k: int = cap_k,
                        _used_counts: Counter[Tuple[str, ...]] = used_combo_counts,
                        _used_cell: Set[Tuple[str, ...]] = used_in_this_cell,
                    ) -> bool:
                        if cand_obj["eligible"] is not True:
                            return False
                        c_tuple = tuple(cand_obj["interests_sorted"])
                        if _used_counts[c_tuple] >= _cap_k:
                            return False
                        if require_unused_in_cell and c_tuple in _used_cell:
                            return False
                        sig = (
                            _pslot.destination_slug,
                            _pslot.days,
                            c_tuple,
                            _pslot.budget_tier_or_null,
                            _pslot.weekend_exposure,
                            _pslot.travel_style,
                        )
                        return sig not in seen_canonical_signatures

                    valid_admissible = [
                        c
                        for c in ordered_combs
                        if _is_admissible_under_p7_p8(c, require_unused_in_cell=True)
                    ]
                    if not valid_admissible:
                        valid_admissible = [
                            c
                            for c in ordered_combs
                            if _is_admissible_under_p7_p8(c, require_unused_in_cell=False)
                        ]
                    if not valid_admissible:
                        raise ScenarioGenerationInfeasibleError(
                            f"No admissible interest combination under Priority 7/8 (repeat_cap={cap_k}, "
                            f"duplicate signature check) for locked slot {pslot.slot_index} "
                            f"({dest}, days={d}, interest_count={k}, budget={pslot.budget_tier_or_null}, "
                            f"style={pslot.travel_style}, weekend={pslot.weekend_exposure}).",
                            phase_b_slots=phase_b_slots,
                            executable_priority_trace=execution_trace,
                        )

                    # Priority 9: Determine target support_class (CLEAR vs STRESS) at minimum repeat usage
                    min_used = min(
                        used_combo_counts[tuple(c["interests_sorted"])]
                        for c in valid_admissible
                    )
                    has_preferred_sc_at_min = any(
                        c["support_class"] == preferred_sc
                        and used_combo_counts[tuple(c["interests_sorted"])] == min_used
                        for c in valid_admissible
                    )
                    target_sc = (
                        preferred_sc
                        if has_preferred_sc_at_min
                        else ("STRESS" if preferred_sc == "CLEAR" else "CLEAR")
                    )

                    pending_rejection_indices: List[int] = []
                    chosen_comb: Optional[Dict[str, Any]] = None
                    chosen_cand_idx: Optional[int] = None
                    chosen_cand_sha: Optional[str] = None

                    scan_stream = sorted(
                        ordered_combs,
                        key=lambda c, _cell_pos=cell_pos, _min_u=min_used, _tsc=target_sc: (
                            0
                            if not _is_admissible_under_p7_p8(c, require_unused_in_cell=False)
                            else (
                                1
                                if (
                                    used_combo_counts[tuple(c["interests_sorted"])] == _min_u
                                    and c["support_class"] == _tsc
                                    and tuple(c["interests_sorted"]) not in used_in_this_cell
                                )
                                else (
                                    2
                                    if (
                                        used_combo_counts[tuple(c["interests_sorted"])] == _min_u
                                        and c["support_class"] == _tsc
                                    )
                                    else 3
                                )
                            ),
                            deterministic_tiebreak_digest(
                                seed,
                                f"scan|{dest}|d={d}|k={k}|slot={_cell_pos}|{c['combination_id']}",
                            ),
                            c["combination_id"],
                        ),
                    )

                    for cand in scan_stream:
                        combo_tuple = tuple(cand["interests_sorted"])
                        if (
                            _is_admissible_under_p7_p8(cand, require_unused_in_cell=False)
                            and combo_tuple in used_in_this_cell
                            and any(
                                tuple(x["interests_sorted"]) not in used_in_this_cell
                                for x in valid_admissible
                            )
                        ):
                            continue

                        candidate_counter += 1
                        c_idx = candidate_counter
                        cand_repr = {
                            "candidate_index": c_idx,
                            "slot_index": pslot.slot_index,
                            "destination_slug": dest,
                            "days": d,
                            "interest_count": k,
                            "budget_tier_or_null": pslot.budget_tier_or_null,
                            "travel_style": pslot.travel_style,
                            "weekend_exposure": pslot.weekend_exposure,
                            "interests_sorted": list(combo_tuple),
                            "combination_id": cand["combination_id"],
                        }
                        c_sha = sha256_hex(canonical_json_bytes(cand_repr))

                        # Priority 7 check: Eligibility
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

                        # Priority 8a check: Repeat cap
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

                        # Priority 8b check: Canonical duplicate signature against locked Phase B slot
                        cand_sig_tuple = (
                            dest,
                            d,
                            combo_tuple,
                            pslot.budget_tier_or_null,
                            pslot.weekend_exposure,
                            pslot.travel_style,
                        )
                        if cand_sig_tuple in seen_canonical_signatures:
                            pending_rejection_indices.append(len(rejection_log))
                            rejection_log.append(
                                CandidateRejectionEntry(
                                    candidate_index=c_idx,
                                    candidate_sha256=c_sha,
                                    reason_code="NEAR_DUPLICATE_SIGNATURE",
                                    rule_version=METHOD_LOCK_RULE_VERSION,
                                    replacement_candidate_index=None,
                                    destination_slug=dest,
                                    days=d,
                                    interest_count=k,
                                    interests_sorted=list(combo_tuple),
                                )
                            )
                            continue

                        # Manual QA reject check
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

                        chosen_comb = cand
                        chosen_cand_idx = c_idx
                        chosen_cand_sha = c_sha
                        break

                    if chosen_comb is None or chosen_cand_idx is None or chosen_cand_sha is None:
                        raise ScenarioGenerationInfeasibleError(
                            f"Candidate stream exhausted in Phase C for locked slot {pslot.slot_index} "
                            f"({dest}, d={d}, k={k}) without valid candidate.",
                            phase_b_slots=phase_b_slots,
                            executable_priority_trace=execution_trace,
                        )

                    for r_pos in pending_rejection_indices:
                        rejection_log[r_pos].replacement_candidate_index = chosen_cand_idx

                    combo_tuple = tuple(chosen_comb["interests_sorted"])
                    used_combo_counts[combo_tuple] += 1
                    used_in_this_cell.add(combo_tuple)

                    sig_tuple = (
                        pslot.destination_slug,
                        pslot.days,
                        combo_tuple,
                        pslot.budget_tier_or_null,
                        pslot.weekend_exposure,
                        pslot.travel_style,
                    )
                    seen_canonical_signatures.add(sig_tuple)

                    scenario_id = f"{DRY_RUN_SCENARIO_ID_PREFIX}-{pslot.slot_index:03d}"
                    scenario_obj = BenchmarkScenarioInput(
                        scenario_id=scenario_id,
                        destination_slug=pslot.destination_slug,
                        destination=pslot.destination,
                        days=pslot.days,
                        start_date=pslot.start_date,
                        end_date=pslot.end_date,
                        budget=pslot.budget,
                        currency=pslot.currency,
                        travel_style=pslot.travel_style,
                        interests=list(combo_tuple),
                        notes=None,
                        allow_revisit_place_ids=False,
                        fixture_label=DRY_RUN_FIXTURE_LABEL,
                    )
                    canonical_sig_list: List[Any] = [
                        pslot.destination_slug,
                        pslot.days,
                        list(combo_tuple),
                        pslot.budget_tier_or_null,
                        pslot.weekend_exposure,
                        pslot.travel_style,
                    ]
                    canonical_sig_sha = sha256_hex(canonical_json_bytes(canonical_sig_list))

                    assigned_by_slot_index[pslot.slot_index] = DryRunScenarioSlot(
                        slot_index=pslot.slot_index,
                        scenario_id=scenario_id,
                        candidate_index=chosen_cand_idx,
                        candidate_sha256=chosen_cand_sha,
                        destination_slug=pslot.destination_slug,
                        destination=pslot.destination,
                        days=pslot.days,
                        interest_count=pslot.interest_count,
                        interests=list(combo_tuple),
                        support_class=chosen_comb["support_class"],
                        rule_a_passed=chosen_comb["rule_a_passed"],
                        rule_b_passed=chosen_comb["rule_b_passed"],
                        union_support=chosen_comb["union_support"],
                        sum_support=chosen_comb["sum_support"],
                        min_interest_support=chosen_comb["min_interest_support"],
                        budget_tier_or_null=pslot.budget_tier_or_null,
                        budget=pslot.budget,
                        currency=pslot.currency,
                        travel_style=pslot.travel_style,
                        weekend_exposure=pslot.weekend_exposure,
                        start_date=pslot.start_date,
                        end_date=pslot.end_date,
                        canonical_signature=canonical_sig_list,
                        canonical_signature_sha256=canonical_sig_sha,
                        scenario_input=scenario_obj,
                    )

    if len(assigned_by_slot_index) != 100:
        raise ScenarioGenerationInfeasibleError(
            f"Expected 100 assigned slots after Phase C, got {len(assigned_by_slot_index)}",
            phase_b_slots=phase_b_slots,
            executable_priority_trace=execution_trace,
        )

    # Verify that every final slot preserves the exact Phase B locked Priority 1..6 fields
    final_slots: List[DryRunScenarioSlot] = []
    for pslot in phase_b_slots:
        fslot = assigned_by_slot_index[pslot.slot_index]
        if (
            fslot.destination_slug != pslot.destination_slug
            or fslot.days != pslot.days
            or fslot.interest_count != pslot.interest_count
            or fslot.budget_tier_or_null != pslot.budget_tier_or_null
            or fslot.budget != pslot.budget
            or fslot.travel_style != pslot.travel_style
            or fslot.weekend_exposure != pslot.weekend_exposure
            or fslot.start_date != pslot.start_date
            or fslot.end_date != pslot.end_date
        ):
            raise ScenarioGenerationInfeasibleError(
                f"Phase C mutated locked Priority 1..6 assignments on slot {pslot.slot_index}",
                phase_b_slots=phase_b_slots,
                executable_priority_trace=execution_trace,
            )
        final_slots.append(fslot)

    return final_slots, rejection_log


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
    if tuple(bundle.executable_priority_trace) != FROZEN_EXECUTABLE_PRIORITY_TRACE:
        raise ScenarioGenerationInfeasibleError(
            f"Executable priority trace mismatch: {bundle.executable_priority_trace} "
            f"!= {list(FROZEN_EXECUTABLE_PRIORITY_TRACE)}"
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
        "executable_priority_trace": list(bundle.executable_priority_trace),
    }


def generate_dry_run_scenarios(
    *,
    seed: int = DEFAULT_SCENARIO_GENERATION_SEED,
    method_lock_path: Optional[Path] = None,
    support_matrix_path: Optional[Path] = None,
    catalog_path: Optional[Path] = None,
    reca_contract_path: Optional[Path] = None,
    method_lock_override: Optional[Dict[str, Any]] = None,
    support_matrix_override: Optional[Dict[str, Any]] = None,
    manual_reject_candidate_indices: Optional[Set[int]] = None,
) -> DryRunGeneratorBundle:
    """Run the deterministic W06 scenario generator in DRY_RUN / SYNTHETIC_GENERATOR_QA mode.

    Executes the frozen 10-step priority hierarchy in strict sequence:
      PHASE A: 1. DESTINATION_ALLOCATION, 2. DAYS_ALLOCATION, 3. INTEREST_COUNT_ALLOCATION
      PHASE B: 4. BUDGET_ALLOCATION, 5. TRAVEL_STYLE_ALLOCATION, 6. WEEKEND_EXPOSURE_ALLOCATION
      PHASE C: 7. SCENARIO_ELIGIBILITY, 8. DUPLICATE_REPEAT_CAP, 9. CLEAR_STRESS_COVERAGE
      PHASE D: 10. CROSS_DIMENSION_IMBALANCE

    Never writes final 100 scenario artifacts or P11.
    Fails closed with ScenarioGenerationInfeasibleError if any runtime authority hash
    or allocation constraint is violated.
    """
    ml_path = method_lock_path or DEFAULT_METHOD_LOCK_PATH
    sm_path = support_matrix_path or DEFAULT_SUPPORT_MATRIX_PATH

    method_lock = (
        method_lock_override
        if method_lock_override is not None
        else load_method_lock_config(ml_path, enforce_frozen_hash=True)
    )
    authority_hashes = verify_runtime_scientific_authorities(
        method_lock,
        catalog_path=catalog_path,
        reca_contract_path=reca_contract_path,
        support_matrix_path=sm_path,
        verify_support_matrix_file=(support_matrix_override is None),
    )

    support_matrix = (
        support_matrix_override
        if support_matrix_override is not None
        else load_support_matrix(
            sm_path,
            expected_sha256=method_lock["interest_mapping"]["pre_freeze_support_matrix_sha256"],
        )
    )

    _validate_method_lock_and_support_matrix_invariants(method_lock, support_matrix, seed)
    catalog_interest_sets = load_direct_catalog_interest_sets(
        catalog_path=catalog_path,
        reca_contract_path=reca_contract_path,
        expected_catalog_sha256=method_lock["interest_mapping"]["catalog_lf_sha256"],
        expected_reca_sha256=method_lock["interest_mapping"]["source_file_lf_sha256"],
    )

    execution_trace: List[str] = []
    manual_rejects = manual_reject_candidate_indices or set()

    # PHASE A: Priorities 1..3 (destination, days, interest_count)
    phase_a_slots = _run_phase_a_allocate_core_marginals(method_lock, execution_trace)

    # PHASE B: Priorities 4..6 (budget, travel_style, weekend_exposure + dates)
    phase_b_locked_slots = _run_phase_b_allocate_secondary_marginals(
        phase_a_slots,
        method_lock,
        seed,
        execution_trace,
    )
    phase_b_locked_sha = sha256_hex(
        canonical_json_bytes([s.model_dump(mode="json") for s in phase_b_locked_slots])
    )

    # PHASE C: Priorities 7..9 (eligibility, repeat-cap + duplicate signature, CLEAR/STRESS coverage)
    final_slots, rejection_log = _run_phase_c_select_eligible_interests(
        phase_b_locked_slots,
        method_lock,
        support_matrix,
        catalog_interest_sets,
        seed,
        manual_rejects,
        execution_trace,
    )

    # PHASE D: Priority 10 (cross-dimension imbalance report)
    cross_report = build_cross_balance_report(final_slots)
    execution_trace.append("CROSS_DIMENSION_IMBALANCE")

    if tuple(execution_trace) != FROZEN_EXECUTABLE_PRIORITY_TRACE:
        raise ScenarioGenerationInfeasibleError(
            f"Executable priority order violated: {execution_trace} != {list(FROZEN_EXECUTABLE_PRIORITY_TRACE)}",
            phase_b_slots=phase_b_locked_slots,
            executable_priority_trace=execution_trace,
        )

    reason_counts_counter: Counter[str] = Counter(r.reason_code for r in rejection_log)
    rejection_reason_counts = {
        code: reason_counts_counter[code]
        for code in sorted(reason_counts_counter.keys())
    }

    ml_sha = lf_normalized_file_sha256(ml_path) if ml_path.exists() else "0" * 64
    sm_sha = authority_hashes["support_matrix_sha256"]

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
        catalog_sha256=authority_hashes["catalog_sha256"],
        reca_contract_sha256=authority_hashes["reca_contract_sha256"],
        executable_priority_trace=execution_trace,
        phase_b_locked_slots_sha256=phase_b_locked_sha,
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
