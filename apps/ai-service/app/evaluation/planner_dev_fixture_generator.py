"""Deterministic W06 DEV-Only Scenario Fixture Generator & Freeze Engine (W06-DEV-FIXTURE-FREEZE-01).

Grounded in:
- data/evaluation/w06/w06_model_arch_selection_method_lock_v1.json (W06-MODEL-ARCH-SELECTION-METHOD-LOCK-01 v1.1.0)
- data/evaluation/w06/w06_scenario_method_lock_v1.json (W06-SCENARIO-METHOD-LOCK-01 v1.0.0)
- data/evaluation/w06/w06_scenario_support_matrix_v1.json (W06-SCENARIO-SUPPORT-MATRIX-V1 v1.0.0)
- data/evaluation/w06/w06_scenarios_freeze_v1.json (W06-SCENARIOS-FREEZE-01 v1.0.0)
- data/evaluation/w06/w06_p11_assignment_manifest_v1.json (W06-P11-ASSIGNMENT-MANIFEST-01 v1.0.0)
- data/curated/gomate_places_freeze_v2.json (REC-A-CORE-V2 frozen catalog)
- apps/ai-service/recommendation/reca/contract.py (CANONICAL_INTERESTS, poi_to_canonical_vector)
- apps/ai-service/app/schemas/planner_benchmark.py (BenchmarkScenarioInput)

SCIENTIFIC BOUNDARIES:
- Generates and freezes 80 DEV-only scenario fixtures (DEV-TUNE = 20, DEV-SELECT = 60)
  under frozen seed 2026101507.
- Does NOT modify planner_scenario_generator.py or any frozen W06 scientific authority.
- Does NOT print final 100 scenario semantic contents (interests, dates, budgets, or full JSON)
  to operator logs, receipts, or stdout.
- Never calls Gemini, OpenAI, Claude, Grok, or any external model provider.
"""

from __future__ import annotations

from collections import Counter
import datetime
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from app.evaluation.planner_scenario_generator import (
    DEFAULT_CATALOG_PATH,
    DEFAULT_METHOD_LOCK_PATH,
    DEFAULT_RECA_CONTRACT_PATH,
    DEFAULT_SUPPORT_MATRIX_PATH,
    EXPECTED_CATALOG_LF_SHA256,
    EXPECTED_METHOD_LOCK_LF_SHA256,
    EXPECTED_RECA_CONTRACT_LF_SHA256,
    EXPECTED_SUPPORT_MATRIX_LF_SHA256,
    ORDERED_BUDGET_TIERS,
    ORDERED_DAYS,
    ORDERED_DESTINATIONS,
    ORDERED_INTEREST_COUNTS,
    ORDERED_TRAVEL_STYLES,
    canonical_json_bytes,
    deterministic_tiebreak_digest,
    lf_normalized_file_sha256,
    load_direct_catalog_interest_sets,
    load_method_lock_config,
    load_support_matrix,
    sha256_hex,
    verify_combination_direct_support,
    verify_runtime_scientific_authorities,
)
from app.schemas.planner_benchmark import (
    CANONICAL_BENCHMARK_INTERESTS,
    PRIMARY_BENCHMARK_DESTINATIONS,
    BenchmarkScenarioInput,
)

REPO_ROOT = Path(__file__).resolve().parents[4]

DEFAULT_MODEL_SELECTION_METHOD_LOCK_PATH = (
    REPO_ROOT / "data" / "evaluation" / "w06" / "w06_model_arch_selection_method_lock_v1.json"
)
DEFAULT_FINAL_SCENARIOS_FREEZE_PATH = (
    REPO_ROOT / "data" / "evaluation" / "w06" / "w06_scenarios_freeze_v1.json"
)
DEFAULT_P11_MANIFEST_PATH = (
    REPO_ROOT / "data" / "evaluation" / "w06" / "w06_p11_assignment_manifest_v1.json"
)
DEFAULT_MEASUREMENT_CONTRACT_PATH = (
    REPO_ROOT / "data" / "evaluation" / "w06" / "w06_measurement_contract_v1.json"
)
DEFAULT_GENERATOR_SOURCE_PATH = (
    REPO_ROOT / "apps" / "ai-service" / "app" / "evaluation" / "planner_scenario_generator.py"
)

DEFAULT_DEV_BUNDLE_PATH = (
    REPO_ROOT / "data" / "evaluation" / "w06" / "w06_dev_fixtures_freeze_v1.json"
)
DEFAULT_DEV_MANIFEST_PATH = (
    REPO_ROOT / "data" / "evaluation" / "w06" / "w06_dev_fixture_manifest_v1.json"
)
DEFAULT_OVERLAP_RECEIPT_PATH = (
    REPO_ROOT / "data" / "evaluation" / "w06" / "w06_dev_final_overlap_receipt_v1.json"
)
DEFAULT_FREEZE_RECEIPT_PATH = (
    REPO_ROOT / "data" / "evaluation" / "w06" / "w06_dev_fixture_freeze_01_receipt_v1.json"
)

EXPECTED_FINAL_SCENARIOS_FREEZE_SHA256: str = (
    "c03bc6dc300604ac395505d59b6413c1a47339b21408cfd637671e81d4b555a1"
)
EXPECTED_P11_MANIFEST_SHA256: str = (
    "0aa9ae923d0e7f29df49735fa41e87530b1caf62418fcbec09a1eff81d83af62"
)
EXPECTED_MODEL_SELECTION_METHOD_LOCK_SHA256: str = (
    "6f30cdf90355dd720795de8e0b21beba45f527767892ca7eb88769141a64210c"
)
EXPECTED_MEASUREMENT_CONTRACT_SHA256: str = (
    "0ddc1f8d879493517cee25f247d2365a0bacb816dc33b129b0c6110d4bfb8298"
)
EXPECTED_GENERATOR_SOURCE_SHA256: str = (
    "623c52cbdd98d181cd9cbbc1e68697a7299cb6c864628e97e743afd9e09ceae1"
)
EXPECTED_BASE_DEVELOP_SHA: str = "2873b161b241573cf9d5db2df64b3e1594a1a595"

DEV_FIXTURE_GENERATION_SEED: int = 2026101507
DEV_FIXTURE_GENERATOR_VERSION: str = "W06-DEV-FIXTURE-GENERATOR-01-V1.0.0"
MODEL_SELECTION_METHOD_LOCK_ID: str = "W06-MODEL-ARCH-SELECTION-METHOD-LOCK-01"

DEV_TUNE_PARTITION: str = "DEV_TUNE"
DEV_SELECT_PARTITION: str = "DEV_SELECT"
DEV_TUNE_FIXTURE_LABEL: str = "W06_DEV_TUNE"
DEV_SELECT_FIXTURE_LABEL: str = "W06_DEV_SELECT"
DEV_TUNE_ID_PREFIX: str = "W06-DEV-TUNE"
DEV_SELECT_ID_PREFIX: str = "W06-DEV-SELECT"

TOTAL_DEV_FIXTURE_COUNT: int = 80
DEV_TUNE_COUNT: int = 20
DEV_SELECT_COUNT: int = 60

DEV_TUNE_ZERO_NEAR_OVERLAP_INFEASIBLE_STATUS: str = (
    "DEV_TUNE_ZERO_NEAR_OVERLAP_INFEASIBLE"
)
DEV_SELECT_BALANCE_INFEASIBLE_STATUS: str = (
    "STOP_REQUIRE_FORMAL_METHOD_AMENDMENT"
)

DEV_SELECTION_PRIORITY_ORDER: Tuple[str, ...] = (
    "EXACT_PARTITION_SIZE",
    "EXACT_LOCKED_MARGINALS",
    "ELIGIBILITY",
    "FINAL_EXACT_OVERLAP_EXCLUSION",
    "DEV_TUNE_NEAR_OVERLAP_EXCLUSION",
    "NO_DUPLICATE_DEV_EXACT_SIGNATURES",
    "MAINTAIN_INTEREST_COMBINATION_DIVERSITY",
    "CLEAR_STRESS_COVERAGE_WITHOUT_FIXED_QUOTA",
    "MINIMIZE_REMAINING_CROSS_DIMENSION_IMBALANCE",
    "DETERMINISTIC_TIE_BREAK",
)

LOCKED_DEV_TUNE_MARGINALS: Dict[str, Any] = {
    "destination": {"ha-noi": 7, "da-nang": 7, "ha-long": 6},
    "days": {"2": 7, "3": 7, "4": 6},
    "interest_count": {"1": 7, "2": 7, "3": 6},
    "budget": {"B1": 5, "B2": 5, "B3": 5, "null": 5},
    "travel_style": {
        "BACKPACKER": 5,
        "BUDGET": 5,
        "COMFORT": 5,
        "LUXURY": 5,
    },
    "weekend": {"weekend_exposed": 10, "non_weekend_exposed": 10},
}

LOCKED_DEV_SELECT_MARGINALS: Dict[str, Any] = {
    "destination": {"ha-noi": 20, "da-nang": 20, "ha-long": 20},
    "days": {"2": 20, "3": 20, "4": 20},
    "interest_count": {"1": 20, "2": 20, "3": 20},
    "budget": {"B1": 15, "B2": 15, "B3": 15, "null": 15},
    "travel_style": {
        "BACKPACKER": 15,
        "BUDGET": 15,
        "COMFORT": 15,
        "LUXURY": 15,
    },
    "weekend": {"weekend_exposed": 30, "non_weekend_exposed": 30},
}

BUDGET_DAILY_NOMINAL_VND: Dict[str, int] = {
    "B1": 500000,
    "B2": 1000000,
    "B3": 2000000,
}


class DevFixtureFreezeInfeasibleError(ValueError):
    """Fail-closed exception raised when DEV fixture generation constraints cannot be satisfied."""

    def __init__(self, reason: str, status: str = DEV_SELECT_BALANCE_INFEASIBLE_STATUS) -> None:
        self.reason = reason
        self.status = status
        super().__init__(f"[{status}] {reason}")


def _budget_tier_from_amount_and_days(budget: Optional[int], days: int) -> Optional[str]:
    if budget is None:
        return None
    if days <= 0 or budget % days != 0:
        raise DevFixtureFreezeInfeasibleError(
            f"Non-canonical budget amount {budget} for days={days}."
        )
    daily = budget // days
    for tier, nominal in BUDGET_DAILY_NOMINAL_VND.items():
        if daily == nominal:
            return tier
    raise DevFixtureFreezeInfeasibleError(
        f"Unrecognized daily nominal budget {daily} VND/day."
    )


def _compute_weekend_exposure(start_date_str: str, end_date_str: str, days: int) -> bool:
    start_dt = datetime.date.fromisoformat(start_date_str)
    end_dt = datetime.date.fromisoformat(end_date_str)
    if end_dt != start_dt + datetime.timedelta(days=days - 1):
        raise DevFixtureFreezeInfeasibleError(
            f"Non-contiguous date span {start_date_str}..{end_date_str} for days={days}."
        )
    return any(
        (start_dt + datetime.timedelta(days=offset)).weekday() in (5, 6)
        for offset in range(days)
    )


def load_blinded_final_100_index(
    *,
    final_bundle_path: Optional[Path] = None,
    p11_path: Optional[Path] = None,
    enforce_frozen_hashes: bool = True,
) -> Dict[str, Any]:
    """Load final-100 exact signatures and near-overlap lookup sets in memory without logging semantics."""
    fb_target = final_bundle_path or DEFAULT_FINAL_SCENARIOS_FREEZE_PATH
    p11_target = p11_path or DEFAULT_P11_MANIFEST_PATH
    if not fb_target.exists():
        raise DevFixtureFreezeInfeasibleError(f"Missing final scenario bundle: {fb_target}")
    if not p11_target.exists():
        raise DevFixtureFreezeInfeasibleError(f"Missing P11 manifest: {p11_target}")

    fb_sha = lf_normalized_file_sha256(fb_target)
    p11_sha = lf_normalized_file_sha256(p11_target)
    if enforce_frozen_hashes:
        if fb_sha != EXPECTED_FINAL_SCENARIOS_FREEZE_SHA256:
            raise DevFixtureFreezeInfeasibleError(
                f"Final scenario bundle SHA256 mismatch: {fb_sha} != {EXPECTED_FINAL_SCENARIOS_FREEZE_SHA256}"
            )
        if p11_sha != EXPECTED_P11_MANIFEST_SHA256:
            raise DevFixtureFreezeInfeasibleError(
                f"P11 manifest SHA256 mismatch: {p11_sha} != {EXPECTED_P11_MANIFEST_SHA256}"
            )

    fb_data = json.loads(fb_target.read_text(encoding="utf-8"))
    p11_data = json.loads(p11_target.read_text(encoding="utf-8"))
    scenarios = fb_data.get("scenarios", [])
    assignments = p11_data.get("assignments", [])
    if len(scenarios) != 100 or len(assignments) != 100:
        raise DevFixtureFreezeInfeasibleError(
            f"Expected 100 final scenarios and 100 P11 assignments, got {len(scenarios)} and {len(assignments)}."
        )

    exact_signatures: Set[Tuple[str, int, Tuple[str, ...], Optional[str], bool, str]] = set()
    near_overlap_keys: Set[Tuple[str, int, Tuple[str, ...], Optional[str]]] = set()

    for scen, p11_row in zip(scenarios, assignments):
        if scen.get("scenario_id") != p11_row.get("scenario_id"):
            raise DevFixtureFreezeInfeasibleError(
                "Final bundle and P11 scenario_id order mismatch."
            )
        dest = str(scen["destination_slug"])
        days = int(scen["days"])
        interests_sorted = tuple(sorted(scen["interests"]))
        b_tier = _budget_tier_from_amount_and_days(scen.get("budget"), days)
        wk = _compute_weekend_exposure(scen["start_date"], scen["end_date"], days)
        style = str(scen["travel_style"])

        p11_sig = p11_row.get("canonical_signature", [])
        expected_sig_list = [dest, days, list(interests_sorted), b_tier, wk, style]
        if p11_sig != expected_sig_list:
            raise DevFixtureFreezeInfeasibleError(
                f"Final scenario signature mismatch against P11 on {scen.get('scenario_id')}."
            )

        exact_signatures.add((dest, days, interests_sorted, b_tier, wk, style))
        for d_dev in ORDERED_DAYS:
            if abs(d_dev - days) <= 1:
                near_overlap_keys.add((dest, d_dev, interests_sorted, b_tier))

    if len(exact_signatures) != 100:
        raise DevFixtureFreezeInfeasibleError(
            f"Expected 100 unique final exact signatures, got {len(exact_signatures)}."
        )

    return {
        "final_bundle_sha256": fb_sha,
        "p11_sha256": p11_sha,
        "final_scenario_count": 100,
        "exact_signatures": exact_signatures,
        "near_overlap_keys": near_overlap_keys,
    }


def load_and_verify_model_selection_method_lock(
    path: Optional[Path] = None,
    *,
    enforce_frozen_hash: bool = True,
) -> Tuple[Dict[str, Any], str]:
    """Load and verify the frozen W06 Model/Architecture Selection Method Lock."""
    target = path or DEFAULT_MODEL_SELECTION_METHOD_LOCK_PATH
    if not target.exists():
        raise DevFixtureFreezeInfeasibleError(
            f"Missing model-selection method lock: {target}"
        )
    actual_sha = lf_normalized_file_sha256(target)
    if enforce_frozen_hash and actual_sha != EXPECTED_MODEL_SELECTION_METHOD_LOCK_SHA256:
        raise DevFixtureFreezeInfeasibleError(
            f"Model-selection method lock SHA256 mismatch: {actual_sha} != {EXPECTED_MODEL_SELECTION_METHOD_LOCK_SHA256}"
        )
    data = json.loads(target.read_text(encoding="utf-8"))
    if data.get("artifact_id") != MODEL_SELECTION_METHOD_LOCK_ID:
        raise DevFixtureFreezeInfeasibleError(
            f"Unexpected model-selection method lock artifact_id: {data.get('artifact_id')!r}"
        )
    if data.get("status") != "FROZEN_BEFORE_DEV_MODEL_EXECUTION":
        raise DevFixtureFreezeInfeasibleError(
            f"Unexpected model-selection method lock status: {data.get('status')!r}"
        )
    dev_meth = data.get("dev_fixture_methodology", {})
    if (
        dev_meth.get("dev_fixture_seed") != DEV_FIXTURE_GENERATION_SEED
        or dev_meth.get("total_dev_fixtures") != TOTAL_DEV_FIXTURE_COUNT
        or dev_meth.get("dev_tune_count") != DEV_TUNE_COUNT
        or dev_meth.get("dev_select_count") != DEV_SELECT_COUNT
        or dev_meth.get("seed_shopping") is not False
        or dev_meth.get("final_100_forbidden_for_model_selection") is not True
    ):
        raise DevFixtureFreezeInfeasibleError(
            "Model-selection method lock dev_fixture_methodology invariant mismatch."
        )
    return data, actual_sha


def _build_dev_tune_3d_grid() -> Dict[str, Dict[Tuple[int, int], int]]:
    """Construct exact 3D (destination, days, interest_count) cell counts for DEV-TUNE (20 fixtures).

    Satisfies:
    - destination: ha-noi=7, da-nang=7, ha-long=6
    - days: 2=7, 3=7, 4=6
    - interest_count: 1=7, 2=7, 3=6
    - every 2D projection (dest x days, dest x k, days x k) has cell counts in {2, 3} (spread <= 1).
    """
    grid: Dict[str, Dict[Tuple[int, int], int]] = {
        "ha-noi": {
            (2, 1): 1, (2, 2): 1, (2, 3): 1,
            (3, 1): 1, (3, 2): 1, (3, 3): 0,
            (4, 1): 1, (4, 2): 0, (4, 3): 1,
        },
        "da-nang": {
            (2, 1): 1, (2, 2): 1, (2, 3): 0,
            (3, 1): 1, (3, 2): 1, (3, 3): 1,
            (4, 1): 0, (4, 2): 1, (4, 3): 1,
        },
        "ha-long": {
            (2, 1): 1, (2, 2): 0, (2, 3): 1,
            (3, 1): 0, (3, 2): 1, (3, 3): 1,
            (4, 1): 1, (4, 2): 1, (4, 3): 0,
        },
    }
    return grid


def _build_dev_select_3d_grid() -> Dict[str, Dict[Tuple[int, int], int]]:
    """Construct exact 3D (destination, days, interest_count) cell counts for DEV-SELECT (60 fixtures).

    Satisfies:
    - destination: ha-noi=20, da-nang=20, ha-long=20
    - days: 2=20, 3=20, 4=20
    - interest_count: 1=20, 2=20, 3=20
    - every 2D projection (dest x days, dest x k, days x k) has cell counts in {6, 7} (spread <= 1).
    """
    grid: Dict[str, Dict[Tuple[int, int], int]] = {
        "ha-noi": {
            (2, 1): 3, (2, 2): 2, (2, 3): 2,
            (3, 1): 2, (3, 2): 3, (3, 3): 2,
            (4, 1): 2, (4, 2): 2, (4, 3): 2,
        },
        "da-nang": {
            (2, 1): 2, (2, 2): 2, (2, 3): 3,
            (3, 1): 2, (3, 2): 2, (3, 3): 2,
            (4, 1): 3, (4, 2): 2, (4, 3): 2,
        },
        "ha-long": {
            (2, 1): 2, (2, 2): 2, (2, 3): 2,
            (3, 1): 2, (3, 2): 2, (3, 3): 3,
            (4, 1): 2, (4, 2): 3, (4, 3): 2,
        },
    }
    return grid


def _enumerate_dev_date_windows(
    window_start_str: str,
    window_end_str: str,
    seed: int,
    partition_tag: str,
) -> Dict[Tuple[int, bool], List[Tuple[str, str]]]:
    """Enumerate all valid contiguous [start_date, end_date] pairs inside the allowed window."""
    start_dt = datetime.date.fromisoformat(window_start_str)
    end_dt = datetime.date.fromisoformat(window_end_str)
    if start_dt > end_dt:
        raise DevFixtureFreezeInfeasibleError(
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
                raise DevFixtureFreezeInfeasibleError(
                    f"Zero valid contiguous date ranges for days={d}, weekend={wk}."
                )
            valid_ranges.sort(
                key=lambda pair: (
                    deterministic_tiebreak_digest(
                        seed, f"dev_date|{partition_tag}|{d}|{wk}|{pair[0]}|{pair[1]}"
                    ),
                    pair[0],
                    pair[1],
                )
            )
            pools[(d, wk)] = valid_ranges
    return pools


def _allocate_partition_slots(
    *,
    partition_name: str,
    id_prefix: str,
    fixture_label: str,
    target_count: int,
    locked_marginals: Dict[str, Any],
    grid_3d: Dict[str, Dict[Tuple[int, int], int]],
    global_index_offset: int,
    seed: int,
    window_start_str: str,
    window_end_str: str,
    cell_ordered_combs: Dict[Tuple[str, int, int], List[Dict[str, Any]]],
    final_exact_signatures: Set[Tuple[str, int, Tuple[str, ...], Optional[str], bool, str]],
    final_near_overlap_keys: Set[Tuple[str, int, Tuple[str, ...], Optional[str]]],
    require_zero_near_overlap: bool,
    seen_dev_exact_signatures: Set[Tuple[str, int, Tuple[str, ...], Optional[str], bool, str]],
    global_combo_reuse_counts: Counter[Tuple[str, Tuple[str, ...]]],
) -> List[Dict[str, Any]]:
    """Deterministically allocate and verify all slots for a DEV partition (DEV-TUNE or DEV-SELECT)."""
    infeasible_status = (
        DEV_TUNE_ZERO_NEAR_OVERLAP_INFEASIBLE_STATUS
        if require_zero_near_overlap
        else DEV_SELECT_BALANCE_INFEASIBLE_STATUS
    )

    # Step 1: Build core (destination_slug, days, interest_count) slots from exact 3D grid
    slots: List[Dict[str, Any]] = []
    part_idx = 0
    for dest in ORDERED_DESTINATIONS:
        for d in ORDERED_DAYS:
            for k in ORDERED_INTEREST_COUNTS:
                cell_cnt = int(grid_3d[dest][(d, k)])
                for _ in range(cell_cnt):
                    part_idx += 1
                    slots.append(
                        {
                            "partition": partition_name,
                            "partition_index": part_idx,
                            "global_index": global_index_offset + part_idx,
                            "scenario_id": f"{id_prefix}-{part_idx:03d}",
                            "fixture_label": fixture_label,
                            "destination_slug": dest,
                            "destination": PRIMARY_BENCHMARK_DESTINATIONS[dest],
                            "days": d,
                            "interest_count": k,
                        }
                    )

    if len(slots) != target_count:
        raise DevFixtureFreezeInfeasibleError(
            f"{partition_name} 3D grid produced {len(slots)} slots, expected {target_count}.",
            status=infeasible_status,
        )

    # Verify core marginals against locked_marginals
    dest_totals = Counter(s["destination_slug"] for s in slots)
    days_totals = Counter(str(s["days"]) for s in slots)
    k_totals = Counter(str(s["interest_count"]) for s in slots)
    if (
        dict(dest_totals) != locked_marginals["destination"]
        or dict(days_totals) != locked_marginals["days"]
        or dict(k_totals) != locked_marginals["interest_count"]
    ):
        raise DevFixtureFreezeInfeasibleError(
            f"{partition_name} core marginal mismatch against locked target.",
            status=infeasible_status,
        )

    # Step 2: Allocate exact budget marginals while minimizing cross-dimension imbalance
    # and ensuring feasibility under zero-near-overlap / exact-overlap constraints
    remaining_budget: Dict[Optional[str], int] = {
        "B1": int(locked_marginals["budget"]["B1"]),
        "B2": int(locked_marginals["budget"]["B2"]),
        "B3": int(locked_marginals["budget"]["B3"]),
        None: int(locked_marginals["budget"]["null"]),
    }
    budget_by_dest: Counter[Tuple[str, Optional[str]]] = Counter()
    budget_by_days: Counter[Tuple[int, Optional[str]]] = Counter()
    budget_by_k: Counter[Tuple[int, Optional[str]]] = Counter()

    for slot in slots:
        p_idx = slot["partition_index"]
        dest = slot["destination_slug"]
        d = slot["days"]
        k = slot["interest_count"]
        combs = cell_ordered_combs[(dest, d, k)]

        avail_budgets: List[Optional[str]] = []
        for b in ORDERED_BUDGET_TIERS:
            if remaining_budget[b] <= 0:
                continue
            # Check that at least one eligible combination is compatible with this budget tier
            if require_zero_near_overlap:
                has_compatible = any(
                    c["eligible"]
                    and (dest, d, tuple(c["interests_sorted"]), b) not in final_near_overlap_keys
                    for c in combs
                )
            else:
                has_compatible = any(c["eligible"] for c in combs)
            if has_compatible:
                avail_budgets.append(b)

        if not avail_budgets:
            raise DevFixtureFreezeInfeasibleError(
                f"No feasible budget tier for {partition_name} slot {p_idx} ({dest}, d={d}, k={k}).",
                status=infeasible_status,
            )

        avail_budgets.sort(
            key=lambda b: (
                max(
                    budget_by_dest[(dest, b)],
                    budget_by_days[(d, b)],
                    budget_by_k[(k, b)],
                ),
                budget_by_dest[(dest, b)]
                + budget_by_days[(d, b)]
                + budget_by_k[(k, b)],
                -remaining_budget[b],
                deterministic_tiebreak_digest(
                    seed, f"{partition_name}|budget|slot={p_idx}|{dest}|d={d}|k={k}|{b}"
                ),
            )
        )
        b_chosen = avail_budgets[0]
        remaining_budget[b_chosen] -= 1
        budget_by_dest[(dest, b_chosen)] += 1
        budget_by_days[(d, b_chosen)] += 1
        budget_by_k[(k, b_chosen)] += 1
        slot["budget_tier_or_null"] = b_chosen
        slot["budget"] = None if b_chosen is None else BUDGET_DAILY_NOMINAL_VND[b_chosen] * d
        slot["currency"] = "VND"

    # Step 3: Allocate exact travel_style marginals while minimizing cross-dimension imbalance
    remaining_style: Dict[str, int] = {
        st: int(locked_marginals["travel_style"][st]) for st in ORDERED_TRAVEL_STYLES
    }
    style_by_dest: Counter[Tuple[str, str]] = Counter()
    style_by_days: Counter[Tuple[int, str]] = Counter()
    style_by_k: Counter[Tuple[int, str]] = Counter()
    style_by_budget: Counter[Tuple[Optional[str], str]] = Counter()

    for slot in slots:
        p_idx = slot["partition_index"]
        dest = slot["destination_slug"]
        d = slot["days"]
        k = slot["interest_count"]
        b_chosen = slot["budget_tier_or_null"]
        avail_styles = [st for st in ORDERED_TRAVEL_STYLES if remaining_style[st] > 0]
        if not avail_styles:
            raise DevFixtureFreezeInfeasibleError(
                f"No remaining travel_style quota for {partition_name} slot {p_idx}.",
                status=infeasible_status,
            )
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
                deterministic_tiebreak_digest(
                    seed, f"{partition_name}|style|slot={p_idx}|{b_chosen}|{st}"
                ),
            )
        )
        st_chosen = avail_styles[0]
        remaining_style[st_chosen] -= 1
        style_by_dest[(dest, st_chosen)] += 1
        style_by_days[(d, st_chosen)] += 1
        style_by_k[(k, st_chosen)] += 1
        style_by_budget[(b_chosen, st_chosen)] += 1
        slot["travel_style"] = st_chosen

    # Step 4: Allocate exact weekend_exposure marginals and contiguous dates inside 2026-11-02..2026-12-13
    remaining_wk: Dict[bool, int] = {
        True: int(locked_marginals["weekend"]["weekend_exposed"]),
        False: int(locked_marginals["weekend"]["non_weekend_exposed"]),
    }
    wk_by_dest: Counter[Tuple[str, bool]] = Counter()
    wk_by_days: Counter[Tuple[int, bool]] = Counter()
    wk_by_k: Counter[Tuple[int, bool]] = Counter()
    wk_by_budget: Counter[Tuple[Optional[str], bool]] = Counter()
    wk_by_style: Counter[Tuple[str, bool]] = Counter()

    date_pools = _enumerate_dev_date_windows(
        window_start_str, window_end_str, seed=seed, partition_tag=partition_name
    )
    date_cursors: Counter[Tuple[int, bool]] = Counter()

    for slot in slots:
        p_idx = slot["partition_index"]
        dest = slot["destination_slug"]
        d = slot["days"]
        k = slot["interest_count"]
        b_chosen = slot["budget_tier_or_null"]
        st_chosen = slot["travel_style"]

        avail_wks = [wk for wk in (True, False) if remaining_wk[wk] > 0]
        if not avail_wks:
            raise DevFixtureFreezeInfeasibleError(
                f"No remaining weekend_exposure quota for {partition_name} slot {p_idx}.",
                status=infeasible_status,
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
                -remaining_wk[wk],
                deterministic_tiebreak_digest(
                    seed,
                    f"{partition_name}|wk|slot={p_idx}|{b_chosen}|{st_chosen}|{wk}",
                ),
            )
        )
        wk_chosen = avail_wks[0]
        remaining_wk[wk_chosen] -= 1
        wk_by_dest[(dest, wk_chosen)] += 1
        wk_by_days[(d, wk_chosen)] += 1
        wk_by_k[(k, wk_chosen)] += 1
        wk_by_budget[(b_chosen, wk_chosen)] += 1
        wk_by_style[(st_chosen, wk_chosen)] += 1

        pool = date_pools[(d, wk_chosen)]
        cur_idx = date_cursors[(d, wk_chosen)]
        start_date_str, end_date_str = pool[cur_idx % len(pool)]
        date_cursors[(d, wk_chosen)] += 1

        slot["weekend_exposure"] = wk_chosen
        slot["start_date"] = start_date_str
        slot["end_date"] = end_date_str

    # Step 5: Select eligible interest combinations in priority order:
    # - Priority 3: Eligibility (Rule A and Rule B pass, EXCLUDED forbidden)
    # - Priority 4: Final exact-overlap exclusion (exact signature not in final 100)
    # - Priority 5: DEV-TUNE near-overlap exclusion (if require_zero_near_overlap is True)
    # - Priority 6: No duplicate DEV exact signatures (across DEV-TUNE and DEV-SELECT)
    # - Priority 7: Interest-combination diversity: lowest current reuse count of (destination_slug, sorted(interests))
    # - Priority 8: CLEAR/STRESS coverage without fixed quota (alternating preference when tied on reuse count)
    # - Priority 10: Deterministic tie-break using seed 2026101507
    support_class_toggle = 0
    for slot in slots:
        p_idx = slot["partition_index"]
        dest = slot["destination_slug"]
        d = slot["days"]
        k = slot["interest_count"]
        b_chosen = slot["budget_tier_or_null"]
        st_chosen = slot["travel_style"]
        wk_chosen = slot["weekend_exposure"]

        combs = cell_ordered_combs[(dest, d, k)]
        preferred_sc = "CLEAR" if (support_class_toggle % 2 == 0) else "STRESS"
        support_class_toggle += 1

        admissible: List[Dict[str, Any]] = []
        for cand in combs:
            if cand["eligible"] is not True or cand["support_class"] == "EXCLUDED":
                continue
            c_tuple = tuple(cand["interests_sorted"])
            sig_tuple = (dest, d, c_tuple, b_chosen, wk_chosen, st_chosen)
            if sig_tuple in final_exact_signatures:
                continue
            if sig_tuple in seen_dev_exact_signatures:
                continue
            if require_zero_near_overlap and (dest, d, c_tuple, b_chosen) in final_near_overlap_keys:
                continue
            admissible.append(cand)

        if not admissible:
            raise DevFixtureFreezeInfeasibleError(
                f"Zero admissible interest combinations for {partition_name} slot {p_idx} "
                f"({dest}, d={d}, k={k}, budget={b_chosen}, style={st_chosen}, wk={wk_chosen}).",
                status=infeasible_status,
            )

        admissible.sort(
            key=lambda c: (
                global_combo_reuse_counts[(dest, tuple(c["interests_sorted"]))],
                0 if c["support_class"] == preferred_sc else 1,
                deterministic_tiebreak_digest(
                    seed,
                    f"{partition_name}|comb|slot={p_idx}|{dest}|d={d}|k={k}|{c['combination_id']}",
                ),
                c["combination_id"],
            )
        )

        chosen = admissible[0]
        c_tuple = tuple(chosen["interests_sorted"])
        sig_tuple = (dest, d, c_tuple, b_chosen, wk_chosen, st_chosen)
        seen_dev_exact_signatures.add(sig_tuple)
        global_combo_reuse_counts[(dest, c_tuple)] += 1

        is_near_overlap = (dest, d, c_tuple, b_chosen) in final_near_overlap_keys
        if require_zero_near_overlap and is_near_overlap:
            raise DevFixtureFreezeInfeasibleError(
                f"DEV-TUNE near-overlap violation at slot {p_idx}.",
                status=DEV_TUNE_ZERO_NEAR_OVERLAP_INFEASIBLE_STATUS,
            )

        scenario_obj = BenchmarkScenarioInput(
            scenario_id=slot["scenario_id"],
            destination_slug=dest,
            destination=slot["destination"],
            days=d,
            start_date=slot["start_date"],
            end_date=slot["end_date"],
            budget=slot["budget"],
            currency=slot["currency"],
            travel_style=st_chosen,
            interests=list(c_tuple),
            notes=None,
            allow_revisit_place_ids=False,
            fixture_label=fixture_label,
        )
        scen_dict = scenario_obj.model_dump(mode="json")
        scen_sha256 = sha256_hex(canonical_json_bytes(scen_dict))
        canonical_sig_list: List[Any] = [
            dest,
            d,
            list(c_tuple),
            b_chosen,
            wk_chosen,
            st_chosen,
        ]

        slot["sorted_interests"] = list(c_tuple)
        slot["support_class"] = chosen["support_class"]
        slot["rule_a_passed"] = chosen["rule_a_passed"]
        slot["rule_b_passed"] = chosen["rule_b_passed"]
        slot["union_support"] = chosen["union_support"]
        slot["sum_support"] = chosen["sum_support"]
        slot["min_interest_support"] = chosen["min_interest_support"]
        slot["near_overlap_with_final"] = is_near_overlap
        slot["canonical_signature"] = canonical_sig_list
        slot["scenario_sha256"] = scen_sha256
        slot["scenario_input"] = scen_dict

    return slots


def _compute_partition_marginal_summary(slots: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    dest_counts = {d: 0 for d in ORDERED_DESTINATIONS}
    days_counts = {str(d): 0 for d in ORDERED_DAYS}
    k_counts = {str(k): 0 for k in ORDERED_INTEREST_COUNTS}
    budget_counts = {"B1": 0, "B2": 0, "B3": 0, "null": 0}
    style_counts = {s: 0 for s in ORDERED_TRAVEL_STYLES}
    wk_counts = {"weekend_exposed": 0, "non_weekend_exposed": 0}
    sc_counts = {"CLEAR": 0, "STRESS": 0, "EXCLUDED": 0}

    for s in slots:
        dest_counts[s["destination_slug"]] += 1
        days_counts[str(s["days"])] += 1
        k_counts[str(s["interest_count"])] += 1
        b_key = s["budget_tier_or_null"] if s["budget_tier_or_null"] is not None else "null"
        budget_counts[b_key] += 1
        style_counts[s["travel_style"]] += 1
        wk_key = "weekend_exposed" if s["weekend_exposure"] else "non_weekend_exposed"
        wk_counts[wk_key] += 1
        sc_counts[s["support_class"]] += 1

    return {
        "destination": dest_counts,
        "days": days_counts,
        "interest_count": k_counts,
        "budget": budget_counts,
        "travel_style": style_counts,
        "weekend": wk_counts,
        "support_class": sc_counts,
    }


def _compute_reuse_diagnostics(
    all_slots: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    combo_counts: Counter[Tuple[str, Tuple[str, ...]]] = Counter()
    for s in all_slots:
        combo_counts[(s["destination_slug"], tuple(s["sorted_interests"]))] += 1

    counts_list = list(combo_counts.values())
    max_reuse = max(counts_list) if counts_list else 0
    mean_reuse = round(sum(counts_list) / len(counts_list), 6) if counts_list else 0.0

    by_dest_k: Dict[str, Dict[str, Dict[str, Any]]] = {
        dest: {} for dest in ORDERED_DESTINATIONS
    }
    for dest in ORDERED_DESTINATIONS:
        for k in ORDERED_INTEREST_COUNTS:
            cell_counts = [
                cnt
                for (d_slug, ints), cnt in combo_counts.items()
                if d_slug == dest and len(ints) == k
            ]
            hist = Counter(cell_counts)
            by_dest_k[dest][str(k)] = {
                "distinct_combinations_used": len(cell_counts),
                "max_reuse": max(cell_counts) if cell_counts else 0,
                "mean_reuse": round(sum(cell_counts) / len(cell_counts), 6)
                if cell_counts
                else 0.0,
                "reuse_count_histogram": {
                    str(r): int(hist[r]) for r in sorted(hist.keys())
                },
            }

    return {
        "distinct_destination_interest_combinations_used": len(combo_counts),
        "max_interest_combination_reuse": max_reuse,
        "mean_interest_combination_reuse": mean_reuse,
        "reuse_distribution_by_destination_and_interest_count": by_dest_k,
    }


def generate_dev_fixture_artifacts(
    *,
    seed: int = DEV_FIXTURE_GENERATION_SEED,
    scenario_method_lock_path: Optional[Path] = None,
    model_selection_method_lock_path: Optional[Path] = None,
    support_matrix_path: Optional[Path] = None,
    catalog_path: Optional[Path] = None,
    reca_contract_path: Optional[Path] = None,
    final_bundle_path: Optional[Path] = None,
    p11_path: Optional[Path] = None,
    enforce_frozen_hashes: bool = True,
) -> Dict[str, Any]:
    """Deterministically generate and verify all 4 frozen DEV fixture artifacts in memory."""
    if seed != DEV_FIXTURE_GENERATION_SEED:
        raise DevFixtureFreezeInfeasibleError(
            f"Seed {seed} != frozen DEV_FIXTURE_GENERATION_SEED {DEV_FIXTURE_GENERATION_SEED}.",
            status=DEV_SELECT_BALANCE_INFEASIBLE_STATUS,
        )

    scenario_ml = load_method_lock_config(
        scenario_method_lock_path, enforce_frozen_hash=enforce_frozen_hashes
    )
    _, model_sel_ml_sha = load_and_verify_model_selection_method_lock(
        model_selection_method_lock_path, enforce_frozen_hash=enforce_frozen_hashes
    )
    support_matrix = load_support_matrix(support_matrix_path)
    runtime_hashes = verify_runtime_scientific_authorities(
        scenario_ml,
        catalog_path=catalog_path,
        reca_contract_path=reca_contract_path,
        support_matrix_path=support_matrix_path,
    )
    catalog_interest_sets = load_direct_catalog_interest_sets(
        catalog_path=catalog_path,
        reca_contract_path=reca_contract_path,
    )
    blinded_final = load_blinded_final_100_index(
        final_bundle_path=final_bundle_path,
        p11_path=p11_path,
        enforce_frozen_hashes=enforce_frozen_hashes,
    )

    # Pre-verify and deterministically order all candidate combinations per (destination, days, interest_count)
    cell_ordered_combs: Dict[Tuple[str, int, int], List[Dict[str, Any]]] = {}
    for dest in ORDERED_DESTINATIONS:
        dest_matrix = support_matrix["destinations"][dest]
        for k in ORDERED_INTEREST_COUNTS:
            for d in ORDERED_DAYS:
                raw_combs = [
                    dict(c)
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
                    if c["eligible"] is True and not direct_eval["eligible"]:
                        raise DevFixtureFreezeInfeasibleError(
                            f"Support matrix eligibility mismatch against direct catalog evaluation for {dest} d={d}."
                        )
                    c["rule_a_passed"] = direct_eval["rule_a_passed"]
                    c["rule_b_passed"] = direct_eval["rule_b_passed"]
                    c["union_support"] = direct_eval["union_support"]
                    c["sum_support"] = direct_eval["sum_support"]
                    c["min_interest_support"] = direct_eval["min_interest_support"]
                    c["support_class"] = direct_eval["support_class"]
                    c["eligible"] = direct_eval["eligible"]

                ordered_combs = sorted(
                    raw_combs,
                    key=lambda c, _dest=dest, _d=d, _k=k: (
                        deterministic_tiebreak_digest(
                            seed, f"dev_cell_comb|{_dest}|d={_d}|k={_k}|{c['combination_id']}"
                        ),
                        c["combination_id"],
                    ),
                )
                if not any(c["eligible"] is True for c in ordered_combs):
                    raise DevFixtureFreezeInfeasibleError(
                        f"Zero eligible combinations for destination={dest}, days={d}, interest_count={k}."
                    )
                cell_ordered_combs[(dest, d, k)] = ordered_combs

    window_start_str = scenario_ml["date_policy"]["window_start_date"]
    window_end_str = scenario_ml["date_policy"]["window_end_date"]

    seen_dev_exact_signatures: Set[Tuple[str, int, Tuple[str, ...], Optional[str], bool, str]] = set()
    global_combo_reuse_counts: Counter[Tuple[str, Tuple[str, ...]]] = Counter()

    # Generate DEV-TUNE first (20 fixtures, strict zero near-overlap with final 100)
    dev_tune_slots = _allocate_partition_slots(
        partition_name=DEV_TUNE_PARTITION,
        id_prefix=DEV_TUNE_ID_PREFIX,
        fixture_label=DEV_TUNE_FIXTURE_LABEL,
        target_count=DEV_TUNE_COUNT,
        locked_marginals=LOCKED_DEV_TUNE_MARGINALS,
        grid_3d=_build_dev_tune_3d_grid(),
        global_index_offset=0,
        seed=seed,
        window_start_str=window_start_str,
        window_end_str=window_end_str,
        cell_ordered_combs=cell_ordered_combs,
        final_exact_signatures=blinded_final["exact_signatures"],
        final_near_overlap_keys=blinded_final["near_overlap_keys"],
        require_zero_near_overlap=True,
        seen_dev_exact_signatures=seen_dev_exact_signatures,
        global_combo_reuse_counts=global_combo_reuse_counts,
    )

    # Generate DEV-SELECT second (60 fixtures, zero exact overlap with final 100 and DEV-TUNE)
    dev_select_slots = _allocate_partition_slots(
        partition_name=DEV_SELECT_PARTITION,
        id_prefix=DEV_SELECT_ID_PREFIX,
        fixture_label=DEV_SELECT_FIXTURE_LABEL,
        target_count=DEV_SELECT_COUNT,
        locked_marginals=LOCKED_DEV_SELECT_MARGINALS,
        grid_3d=_build_dev_select_3d_grid(),
        global_index_offset=DEV_TUNE_COUNT,
        seed=seed,
        window_start_str=window_start_str,
        window_end_str=window_end_str,
        cell_ordered_combs=cell_ordered_combs,
        final_exact_signatures=blinded_final["exact_signatures"],
        final_near_overlap_keys=blinded_final["near_overlap_keys"],
        require_zero_near_overlap=False,
        seen_dev_exact_signatures=seen_dev_exact_signatures,
        global_combo_reuse_counts=global_combo_reuse_counts,
    )

    all_slots = dev_tune_slots + dev_select_slots
    if len(all_slots) != TOTAL_DEV_FIXTURE_COUNT or len(seen_dev_exact_signatures) != TOTAL_DEV_FIXTURE_COUNT:
        raise DevFixtureFreezeInfeasibleError(
            "Total DEV fixture count or unique exact signature invariant failed."
        )

    dev_tune_near_overlap_count = sum(1 for s in dev_tune_slots if s["near_overlap_with_final"])
    if dev_tune_near_overlap_count != 0:
        raise DevFixtureFreezeInfeasibleError(
            f"DEV-TUNE near-overlap count must be 0, got {dev_tune_near_overlap_count}.",
            status=DEV_TUNE_ZERO_NEAR_OVERLAP_INFEASIBLE_STATUS,
        )

    dev_select_near_overlap_count = sum(1 for s in dev_select_slots if s["near_overlap_with_final"])
    dev_select_near_overlap_rate = round(dev_select_near_overlap_count / DEV_SELECT_COUNT, 6)

    all_dev_exact_overlap_with_final = sum(
        1
        for s in all_slots
        if (
            s["destination_slug"],
            s["days"],
            tuple(s["sorted_interests"]),
            s["budget_tier_or_null"],
            s["weekend_exposure"],
            s["travel_style"],
        )
        in blinded_final["exact_signatures"]
    )
    if all_dev_exact_overlap_with_final != 0:
        raise DevFixtureFreezeInfeasibleError(
            f"DEV exact overlap with final 100 must be 0, got {all_dev_exact_overlap_with_final}."
        )

    rule_a_failures = sum(1 for s in all_slots if not s["rule_a_passed"])
    rule_b_failures = sum(1 for s in all_slots if not s["rule_b_passed"])
    excluded_count = sum(1 for s in all_slots if s["support_class"] == "EXCLUDED")
    dev_duplicate_count = len(all_slots) - len(seen_dev_exact_signatures)

    dev_tune_marginals = _compute_partition_marginal_summary(dev_tune_slots)
    dev_select_marginals = _compute_partition_marginal_summary(dev_select_slots)
    reuse_diagnostics = _compute_reuse_diagnostics(all_slots)

    # 1. Materialize DEV bundle (w06_dev_fixtures_freeze_v1.json)
    dev_bundle: Dict[str, Any] = {
        "artifact_id": "W06-DEV-FIXTURES-FREEZE-01",
        "version": "1.0.0",
        "seed": seed,
        "fixture_count": TOTAL_DEV_FIXTURE_COUNT,
        "dev_tune_count": DEV_TUNE_COUNT,
        "dev_select_count": DEV_SELECT_COUNT,
        "method_lock": MODEL_SELECTION_METHOD_LOCK_ID,
        "final_bundle_sha256": blinded_final["final_bundle_sha256"],
        "p11_sha256": blinded_final["p11_sha256"],
        "hash_basis": "SHA256_CANONICAL_JSON_UTF8_LF_BYTES",
        "fixtures": [s["scenario_input"] for s in all_slots],
    }
    dev_bundle_sha256 = sha256_hex(canonical_json_bytes(dev_bundle))

    # 2. Materialize DEV manifest (w06_dev_fixture_manifest_v1.json)
    manifest_entries: List[Dict[str, Any]] = []
    for s in all_slots:
        manifest_entries.append(
            {
                "partition": s["partition"],
                "partition_index": s["partition_index"],
                "global_index": s["global_index"],
                "scenario_id": s["scenario_id"],
                "scenario_sha256": s["scenario_sha256"],
                "destination_slug": s["destination_slug"],
                "days": s["days"],
                "interest_count": s["interest_count"],
                "sorted_interests": list(s["sorted_interests"]),
                "budget_tier_or_null": s["budget_tier_or_null"],
                "travel_style": s["travel_style"],
                "weekend_exposure": s["weekend_exposure"],
                "support_class": s["support_class"],
                "canonical_signature": list(s["canonical_signature"]),
            }
        )

    dev_manifest: Dict[str, Any] = {
        "artifact_id": "W06-DEV-FIXTURE-MANIFEST-01",
        "version": "1.0.0",
        "seed": seed,
        "method_lock": MODEL_SELECTION_METHOD_LOCK_ID,
        "dev_bundle_path": "data/evaluation/w06/w06_dev_fixtures_freeze_v1.json",
        "dev_bundle_sha256": dev_bundle_sha256,
        "final_bundle_sha256": blinded_final["final_bundle_sha256"],
        "p11_sha256": blinded_final["p11_sha256"],
        "fixture_count": TOTAL_DEV_FIXTURE_COUNT,
        "dev_tune_count": DEV_TUNE_COUNT,
        "dev_select_count": DEV_SELECT_COUNT,
        "priority_order": list(DEV_SELECTION_PRIORITY_ORDER),
        "dev_tune_marginals": dev_tune_marginals,
        "dev_select_marginals": dev_select_marginals,
        "interest_combination_diversity": reuse_diagnostics,
        "hash_basis": "SHA256_CANONICAL_JSON_UTF8_LF_BYTES",
        "fixtures": manifest_entries,
    }
    dev_manifest_sha256 = sha256_hex(canonical_json_bytes(dev_manifest))

    # 3. Materialize Overlap Receipt (w06_dev_final_overlap_receipt_v1.json)
    overlap_receipt: Dict[str, Any] = {
        "artifact_id": "W06-DEV-FINAL-OVERLAP-RECEIPT-01",
        "task_id": "W06-DEV-FIXTURE-FREEZE-01",
        "version": "1.0.0",
        "final_bundle_sha256": blinded_final["final_bundle_sha256"],
        "p11_sha256": blinded_final["p11_sha256"],
        "dev_bundle_sha256": dev_bundle_sha256,
        "dev_manifest_sha256": dev_manifest_sha256,
        "dev_fixture_seed": seed,
        "total_dev_count": TOTAL_DEV_FIXTURE_COUNT,
        "dev_tune_count": DEV_TUNE_COUNT,
        "dev_select_count": DEV_SELECT_COUNT,
        "all_dev_exact_overlap_with_final": all_dev_exact_overlap_with_final,
        "dev_tune_near_overlap_with_final": dev_tune_near_overlap_count,
        "dev_select_near_overlap_with_final": dev_select_near_overlap_count,
        "dev_select_near_overlap_rate": dev_select_near_overlap_rate,
        "all_dev_unique_exact_signatures": (dev_duplicate_count == 0),
        "dev_duplicate_exact_signature_count": dev_duplicate_count,
        "final_semantics_printed_to_operator_logs": False,
        "overlap_audit_status": "PASS",
        "hash_basis": "SHA256_CANONICAL_JSON_UTF8_LF_BYTES",
    }
    overlap_receipt_sha256 = sha256_hex(canonical_json_bytes(overlap_receipt))

    # 4. Materialize DEV Freeze Receipt (w06_dev_fixture_freeze_01_receipt_v1.json)
    freeze_receipt: Dict[str, Any] = {
        "artifact_id": "W06-DEV-FIXTURE-FREEZE-01-RECEIPT-V1",
        "task_id": "W06-DEV-FIXTURE-FREEZE-01",
        "version": "1.0.0",
        "status": "FROZEN_FOR_DEV_EXECUTION_ONLY",
        "base_develop_sha": EXPECTED_BASE_DEVELOP_SHA,
        "seed": seed,
        "generator_version": DEV_FIXTURE_GENERATOR_VERSION,
        "authorities": {
            "model_selection_method_lock_path": "data/evaluation/w06/w06_model_arch_selection_method_lock_v1.json",
            "model_selection_method_lock_sha256": model_sel_ml_sha,
            "scenario_method_lock_path": "data/evaluation/w06/w06_scenario_method_lock_v1.json",
            "scenario_method_lock_sha256": EXPECTED_METHOD_LOCK_LF_SHA256,
            "catalog_path": "data/curated/gomate_places_freeze_v2.json",
            "catalog_sha256": runtime_hashes["catalog_sha256"],
            "reca_mapping_path": "apps/ai-service/recommendation/reca/contract.py",
            "reca_mapping_sha256": runtime_hashes["reca_contract_sha256"],
            "support_matrix_path": "data/evaluation/w06/w06_scenario_support_matrix_v1.json",
            "support_matrix_sha256": runtime_hashes["support_matrix_sha256"],
            "measurement_contract_path": "data/evaluation/w06/w06_measurement_contract_v1.json",
            "measurement_contract_sha256": EXPECTED_MEASUREMENT_CONTRACT_SHA256,
            "final_bundle_path": "data/evaluation/w06/w06_scenarios_freeze_v1.json",
            "final_bundle_sha256": blinded_final["final_bundle_sha256"],
            "p11_path": "data/evaluation/w06/w06_p11_assignment_manifest_v1.json",
            "p11_sha256": blinded_final["p11_sha256"],
        },
        "generated_artifacts": {
            "dev_bundle_path": "data/evaluation/w06/w06_dev_fixtures_freeze_v1.json",
            "dev_bundle_sha256": dev_bundle_sha256,
            "dev_manifest_path": "data/evaluation/w06/w06_dev_fixture_manifest_v1.json",
            "dev_manifest_sha256": dev_manifest_sha256,
            "overlap_receipt_path": "data/evaluation/w06/w06_dev_final_overlap_receipt_v1.json",
            "overlap_receipt_sha256": overlap_receipt_sha256,
        },
        "counts": {
            "fixture_count": TOTAL_DEV_FIXTURE_COUNT,
            "dev_tune_count": DEV_TUNE_COUNT,
            "dev_select_count": DEV_SELECT_COUNT,
        },
        "marginals": {
            "dev_tune": dev_tune_marginals,
            "dev_select": dev_select_marginals,
        },
        "verification_summary": {
            "rule_a_failures": rule_a_failures,
            "rule_b_failures": rule_b_failures,
            "excluded_count": excluded_count,
            "dev_duplicate_count": dev_duplicate_count,
            "final_exact_overlap_count": all_dev_exact_overlap_with_final,
            "dev_tune_final_near_overlap_count": dev_tune_near_overlap_count,
            "dev_select_final_near_overlap_count": dev_select_near_overlap_count,
            "dev_select_final_near_overlap_rate": dev_select_near_overlap_rate,
            "max_interest_combination_reuse": reuse_diagnostics["max_interest_combination_reuse"],
            "mean_interest_combination_reuse": reuse_diagnostics["mean_interest_combination_reuse"],
        },
        "interest_combination_diversity": reuse_diagnostics,
        "provider_calls": 0,
        "gemini_called": False,
        "openai_called": False,
        "claude_called": False,
        "grok_called": False,
        "winning_model_selected": False,
        "dev_model_outputs_generated": False,
        "preregistration_created": False,
        "final_benchmark_executed": False,
        "final_semantics_printed_to_operator_logs": False,
        "hash_basis": "SHA256_CANONICAL_JSON_UTF8_LF_BYTES",
    }
    freeze_receipt_sha256 = sha256_hex(canonical_json_bytes(freeze_receipt))

    return {
        "dev_bundle": dev_bundle,
        "dev_bundle_sha256": dev_bundle_sha256,
        "dev_manifest": dev_manifest,
        "dev_manifest_sha256": dev_manifest_sha256,
        "overlap_receipt": overlap_receipt,
        "overlap_receipt_sha256": overlap_receipt_sha256,
        "freeze_receipt": freeze_receipt,
        "freeze_receipt_sha256": freeze_receipt_sha256,
    }


def write_frozen_dev_fixture_files(
    *,
    output_dir: Optional[Path] = None,
    seed: int = DEV_FIXTURE_GENERATION_SEED,
) -> Dict[str, Any]:
    """Generate and write the 4 canonical UTF-8 LF JSON files for W06-DEV-FIXTURE-FREEZE-01."""
    artifacts = generate_dev_fixture_artifacts(seed=seed)
    target_dir = output_dir or (REPO_ROOT / "data" / "evaluation" / "w06")
    target_dir.mkdir(parents=True, exist_ok=True)

    bundle_path = target_dir / "w06_dev_fixtures_freeze_v1.json"
    manifest_path = target_dir / "w06_dev_fixture_manifest_v1.json"
    overlap_path = target_dir / "w06_dev_final_overlap_receipt_v1.json"
    receipt_path = target_dir / "w06_dev_fixture_freeze_01_receipt_v1.json"

    bundle_path.write_bytes(canonical_json_bytes(artifacts["dev_bundle"]))
    manifest_path.write_bytes(canonical_json_bytes(artifacts["dev_manifest"]))
    overlap_path.write_bytes(canonical_json_bytes(artifacts["overlap_receipt"]))
    receipt_path.write_bytes(canonical_json_bytes(artifacts["freeze_receipt"]))

    return {
        "bundle_path": bundle_path,
        "manifest_path": manifest_path,
        "overlap_path": overlap_path,
        "receipt_path": receipt_path,
        **artifacts,
    }


if __name__ == "__main__":
    result = write_frozen_dev_fixture_files()
    print(
        json.dumps(
            {
                "status": "PASS",
                "seed": DEV_FIXTURE_GENERATION_SEED,
                "dev_bundle_sha256": result["dev_bundle_sha256"],
                "dev_manifest_sha256": result["dev_manifest_sha256"],
                "overlap_receipt_sha256": result["overlap_receipt_sha256"],
                "freeze_receipt_sha256": result["freeze_receipt_sha256"],
                "verification_summary": result["freeze_receipt"]["verification_summary"],
            },
            indent=2,
            sort_keys=True,
        )
    )
