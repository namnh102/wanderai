"""Verification suite for W06-SCENARIO-METHOD-LOCK-01 + FIX-01 (METHOD-01 .. METHOD-42).

Verifies that the W06 scenario-generation methodology lock and pre-freeze
catalog support matrix are deterministically frozen, cryptographically pinned,
jointly feasible under the destination x interest_count repeat-cap rule, and
fully reproducible before any final 100-scenario creation (P11).
"""
from collections import Counter
import datetime
import hashlib
import itertools
import json
import math
from pathlib import Path
import sys
from typing import Dict, List, Set, Tuple

ROOT_DIR = Path(__file__).resolve().parents[1]
AI_SERVICE_DIR = ROOT_DIR / "apps" / "ai-service"
if str(AI_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_DIR))

from recommendation.reca.contract import (  # noqa: E402
    CANONICAL_INTERESTS,
    SUPPORTED_DESTINATIONS,
    poi_to_canonical_vector,
)

METHOD_LOCK_JSON_PATH = ROOT_DIR / "data" / "evaluation" / "w06" / "w06_scenario_method_lock_v1.json"
SUPPORT_MATRIX_JSON_PATH = ROOT_DIR / "data" / "evaluation" / "w06" / "w06_scenario_support_matrix_v1.json"
METHOD_LOCK_MD_PATH = ROOT_DIR / "docs" / "research" / "w06_scenario_method_lock_v1.md"
GENERATION_POLICY_MD_PATH = ROOT_DIR / "docs" / "research" / "w06_scenario_generation_policy_v1.md"
MEASUREMENT_CONTRACT_JSON_PATH = ROOT_DIR / "data" / "evaluation" / "w06" / "w06_measurement_contract_v1.json"
CATALOG_PATH = ROOT_DIR / "data" / "curated" / "gomate_places_freeze_v2.json"
RECA_CONTRACT_PATH = ROOT_DIR / "apps" / "ai-service" / "recommendation" / "reca" / "contract.py"

EXPECTED_BASE_DEVELOP_SHA = "de0c664f9831caaeda34a996d90f6d6d98643848"
EXPECTED_RECA_CONTRACT_LF_SHA256 = "1a62c36a95092be35ab78dca43e20f646016e154746ee051a499bdebfc67538c"
EXPECTED_CATALOG_LF_SHA256 = "f7517938598e3923906763f8f31334a500ee88bc06232f2992d38e2fcb28a444"
EXPECTED_REPEAT_CAP_FORMULA = (
    "repeat_cap(destination, interest_count) = "
    "ceil(assigned_scenario_count(destination, interest_count) / "
    "number_of_distinct_eligible_interest_combinations(destination, interest_count))"
)


def _lf_normalized_sha256(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(raw).hexdigest()


def _canonical_json_bytes(obj: object) -> bytes:
    return (json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _load_method_lock() -> dict:
    assert METHOD_LOCK_JSON_PATH.exists(), f"Missing {METHOD_LOCK_JSON_PATH}"
    raw = METHOD_LOCK_JSON_PATH.read_bytes()
    parsed = json.loads(raw.decode("utf-8"))
    assert raw == _canonical_json_bytes(parsed), "w06_scenario_method_lock_v1.json must be in canonical UTF-8 LF JSON format"
    return parsed


def _load_support_matrix() -> dict:
    assert SUPPORT_MATRIX_JSON_PATH.exists(), f"Missing {SUPPORT_MATRIX_JSON_PATH}"
    raw = SUPPORT_MATRIX_JSON_PATH.read_bytes()
    parsed = json.loads(raw.decode("utf-8"))
    assert raw == _canonical_json_bytes(parsed), "w06_scenario_support_matrix_v1.json must be in canonical UTF-8 LF JSON format"
    return parsed


def _evaluate_combination_support(
    combo: Tuple[str, ...],
    interest_to_pois: Dict[str, Set[str]],
    days: int,
    min_poi_visits_per_day: int = 2,
) -> dict:
    """Reference implementation of the two-stage W06 support eligibility rule using direct set union."""
    counts = {interest: len(interest_to_pois[interest]) for interest in combo}
    sum_support = sum(counts.values())
    union_set: Set[str] = set().union(*(interest_to_pois[interest] for interest in combo))
    union_support = len(union_set)
    overlap_poi_count = sum_support - union_support

    rule_a_threshold = days
    rule_b_threshold = days * min_poi_visits_per_day

    rule_a_passed = all(n_i >= rule_a_threshold for n_i in counts.values())
    rule_b_passed = (union_support >= rule_b_threshold) and (sum_support >= rule_b_threshold)
    eligible = rule_a_passed and rule_b_passed

    stress_interests = [i for i in combo if rule_a_threshold <= counts[i] < rule_b_threshold]
    if not eligible:
        support_class = "EXCLUDED"
        exclusion_reason_code = (
            "CATALOG_SUPPORT_BELOW_THRESHOLD"
            if not rule_a_passed
            else "TOTAL_INTEREST_CAPACITY_INSUFFICIENT"
        )
    elif stress_interests:
        support_class = "STRESS"
        exclusion_reason_code = None
    else:
        support_class = "CLEAR"
        exclusion_reason_code = None

    return {
        "counts": counts,
        "sum_support": sum_support,
        "union_support": union_support,
        "overlap_poi_count": overlap_poi_count,
        "rule_a_passed": rule_a_passed,
        "rule_b_passed": rule_b_passed,
        "eligible": eligible,
        "support_class": support_class,
        "stress_interests": stress_interests if eligible else [],
        "exclusion_reason_code": exclusion_reason_code,
    }


def _recompute_repeat_caps(lock: dict, matrix: dict) -> Dict[str, Dict[str, dict]]:
    """Recompute repeat caps dynamically from frozen support matrix and cross-allocation."""
    cross_k = lock["destination_interest_count_cross_allocation"]
    result: Dict[str, Dict[str, dict]] = {}
    for dest in ("ha-noi", "da-nang", "ha-long"):
        d_entry = matrix["destinations"][dest]
        result[dest] = {}
        for k_str in ("1", "2", "3"):
            k_int = int(k_str)
            distinct_eligible_across_days = set()
            for d_str in ("2", "3", "4"):
                for c in d_entry["by_days"][d_str]["combinations"]:
                    if c["interest_count"] == k_int and c["eligible"] is True:
                        distinct_eligible_across_days.add(tuple(c["interests_sorted"]))
            elig_count = len(distinct_eligible_across_days)
            assigned_count = cross_k[dest][k_str]
            cap = math.ceil(assigned_count / elig_count)
            result[dest][k_str] = {
                "assigned_scenario_count": assigned_count,
                "distinct_eligible_interest_combinations": elig_count,
                "repeat_cap": cap,
                "max_combination_slot_capacity": elig_count * cap,
            }
    return result


def _construct_feasible_abstract_assignment(lock: dict, matrix: dict) -> List[dict]:
    """Dependency-free deterministic offline constructive solver proving joint method feasibility."""
    cross_k = lock["destination_interest_count_cross_allocation"]
    cross_d = lock["destination_days_cross_allocation"]
    recomputed_caps = _recompute_repeat_caps(lock, matrix)

    # Exact 3D cell counts (destination, days, interest_count) compatible with both
    # destination_interest_count_cross_allocation and destination_days_cross_allocation:
    cell_3d: Dict[str, Dict[Tuple[int, int], int]] = {
        "ha-noi": {
            (2, 1): 4, (2, 2): 4, (2, 3): 3,
            (3, 1): 4, (3, 2): 4, (3, 3): 4,
            (4, 1): 3, (4, 2): 4, (4, 3): 4,
        },
        "da-nang": {
            (2, 1): 4, (2, 2): 4, (2, 3): 3,
            (3, 1): 4, (3, 2): 3, (3, 3): 4,
            (4, 1): 3, (4, 2): 4, (4, 3): 4,
        },
        "ha-long": {
            (2, 1): 4, (2, 2): 4, (2, 3): 3,
            (3, 1): 4, (3, 2): 3, (3, 3): 4,
            (4, 1): 3, (4, 2): 4, (4, 3): 4,
        },
    }

    for dest in ("ha-noi", "da-nang", "ha-long"):
        for d in (2, 3, 4):
            assert sum(cell_3d[dest][(d, k)] for k in (1, 2, 3)) == cross_d[dest][str(d)]
        for k in (1, 2, 3):
            assert sum(cell_3d[dest][(d, k)] for d in (2, 3, 4)) == cross_k[dest][str(k)]

    abstract_assignments: List[dict] = []
    for dest in ("ha-noi", "da-nang", "ha-long"):
        d_info = matrix["destinations"][dest]
        used_combo_counts: Counter = Counter()
        for k in (1, 2, 3):
            cap_k = recomputed_caps[dest][str(k)]["repeat_cap"]
            # Assign from d=4 down to d=2 so the strictest day length selects from its eligible pool first
            for d in (4, 3, 2):
                need = cell_3d[dest][(d, k)]
                eligible_for_d_k = [
                    c for c in d_info["by_days"][str(d)]["combinations"]
                    if c["interest_count"] == k and c["eligible"] is True
                ]
                for _ in range(need):
                    candidates = [
                        c for c in eligible_for_d_k
                        if used_combo_counts[tuple(c["interests_sorted"])] < cap_k
                    ]
                    assert candidates, f"No eligible candidate under repeat cap at {dest} d={d} k={k}"
                    candidates.sort(
                        key=lambda c: (
                            used_combo_counts[tuple(c["interests_sorted"])],
                            0 if c["support_class"] == "STRESS" else 1,
                            c["combination_id"],
                        )
                    )
                    chosen = candidates[0]
                    combo_key = tuple(chosen["interests_sorted"])
                    used_combo_counts[combo_key] += 1
                    abstract_assignments.append(
                        {
                            "destination_slug": dest,
                            "days": d,
                            "interest_count": k,
                            "interests_sorted": list(combo_key),
                            "support_class": chosen["support_class"],
                            "eligible": chosen["eligible"],
                        }
                    )

    budgets = ["B1"] * 27 + ["B2"] * 27 + ["B3"] * 26 + [None] * 20
    travel_styles = ["BACKPACKER", "BUDGET", "COMFORT", "LUXURY"] * 25
    weekend_flags = [True, False] * 50

    for idx, slot in enumerate(abstract_assignments):
        slot["budget_tier_or_null"] = budgets[idx]
        slot["travel_style"] = travel_styles[idx]
        slot["weekend_exposure"] = weekend_flags[idx]

    return abstract_assignments


def test_method_01_primary_benchmark_100_and_destination_allocation():
    """METHOD-01: 100 total scenarios and 34/33/33 destination allocation (REC-A-CORE-V2 only)."""
    lock = _load_method_lock()
    assert lock["method_lock_id"] == "W06-SCENARIO-METHOD-LOCK-01"
    assert lock["method_lock_version"] == "1.0.0"
    assert lock["base_develop_sha"] == EXPECTED_BASE_DEVELOP_SHA
    assert lock["status"] == "LOCKED_PENDING_INSTRUMENT_AMENDMENT"

    pb = lock["primary_benchmark"]
    assert pb["benchmark_target"] == 100
    assert pb["destination_allocation"] == {
        "ha-noi": 34,
        "da-nang": 33,
        "ha-long": 33,
    }
    assert sum(pb["destination_allocation"].values()) == 100
    assert pb["primary_destinations"] == ["ha-noi", "da-nang", "ha-long"]
    assert pb["catalog_scope"] == "REC-A-CORE-V2"
    assert pb["catalog_filter_predicate"] == "is_rec_a_core_v2 == true"
    assert pb["allow_other_primary_destinations"] is False


def test_method_02_min_poi_visits_per_day_exactly_2():
    """METHOD-02: min_poi_visits_per_day is frozen at exactly 2 POI_VISIT items per day."""
    lock = _load_method_lock()
    mp = lock["minimum_poi_visits_per_day_policy"]
    assert mp["min_poi_visits_per_day"] == 2
    assert mp["required_activity_kind"] == "POI_VISIT"
    assert mp["transit_only_counts_toward_minimum"] is False
    assert mp["instrumentation_amendment_required"] is True
    assert mp["evaluator_modified_in_this_task"] is False


def test_method_03_days_marginal_33_34_33():
    """METHOD-03: trip length marginal totals frozen at 2d=33, 3d=34, 4d=33."""
    lock = _load_method_lock()
    tl = lock["trip_length_target"]
    assert tl["allowed_days"] == [2, 3, 4]
    assert tl["marginal_counts"] == {"2": 33, "3": 34, "4": 33}
    assert sum(tl["marginal_counts"].values()) == 100
    assert tl["allow_other_trip_lengths_in_primary_100"] is False


def test_method_04_interest_count_marginal_33_34_33():
    """METHOD-04: interest-count marginal totals frozen at 1=33, 2=34, 3=33 with canonical taxonomy only."""
    lock = _load_method_lock()
    ic = lock["interest_count_target"]
    assert ic["allowed_interest_counts"] == [1, 2, 3]
    assert ic["marginal_counts"] == {"1": 33, "2": 34, "3": 33}
    assert sum(ic["marginal_counts"].values()) == 100
    assert ic["canonical_interest_taxonomy_only"] is True
    assert ic["canonical_interests"] == list(CANONICAL_INTERESTS)
    assert len(ic["canonical_interests"]) == 7


def test_method_05_interest_mapping_path_and_hashes_frozen():
    """METHOD-05: authoritative interest mapping path, commit SHA, and LF-normalized hashes frozen."""
    lock = _load_method_lock()
    im = lock["interest_mapping"]
    assert im["source_commit_sha"] == EXPECTED_BASE_DEVELOP_SHA
    assert im["source_file_path"] == "apps/ai-service/recommendation/reca/contract.py"
    assert im["function_name"] == "poi_to_canonical_vector"
    assert im["new_mapping_created"] is False
    assert im["source_file_hash_basis"] == "SHA256_LF_NORMALIZED_SOURCE_BYTES"
    assert im["source_file_lf_sha256"] == EXPECTED_RECA_CONTRACT_LF_SHA256
    assert _lf_normalized_sha256(RECA_CONTRACT_PATH) == im["source_file_lf_sha256"]

    assert im["catalog_file_path"] == "data/curated/gomate_places_freeze_v2.json"
    assert im["catalog_hash_basis"] == "SHA256_LF_NORMALIZED_SOURCE_BYTES"
    assert im["catalog_lf_sha256"] == EXPECTED_CATALOG_LF_SHA256
    assert _lf_normalized_sha256(CATALOG_PATH) == im["catalog_lf_sha256"]

    assert im["pre_freeze_support_matrix_path"] == "data/evaluation/w06/w06_scenario_support_matrix_v1.json"
    assert im["pre_freeze_support_matrix_hash_basis"] == "SHA256_CANONICAL_JSON_UTF8_LF_BYTES"
    assert hashlib.sha256(SUPPORT_MATRIX_JSON_PATH.read_bytes()).hexdigest() == im["pre_freeze_support_matrix_sha256"]
    assert im["pre_freeze_support_matrix_is_final_100_scenarios"] is False


def test_method_06_two_stage_eligibility_rule_exact():
    """METHOD-06: two-stage eligibility rule (Rule A and Rule B) is frozen with exact formulas."""
    lock = _load_method_lock()
    rule = lock["support_eligibility_rule"]
    assert rule["days_symbol"] == "d"
    assert rule["min_poi_visits_per_day_symbol"] == "m"
    assert rule["min_poi_visits_per_day"] == 2
    assert rule["interest_support_symbol"] == "n_i"
    assert rule["rule_a"]["rule_id"] == "RULE_A"
    assert rule["rule_a"]["condition"] == "for every requested interest i: n_i >= d"
    assert rule["rule_a"]["rejection_reason_code"] == "CATALOG_SUPPORT_BELOW_THRESHOLD"
    assert rule["rule_b"]["rule_id"] == "RULE_B"
    assert (
        rule["rule_b"]["condition"]
        == "union_support(requested_interests) >= d * m and sum(n_i across requested_interests) >= d * m"
    )
    assert rule["rule_b"]["rejection_reason_code"] == "TOTAL_INTEREST_CAPACITY_INSUFFICIENT"


def test_method_07_union_support_computed_directly_not_assuming_zero_overlap():
    """METHOD-07: union support is computed directly via set union rather than assuming zero overlap."""
    lock = _load_method_lock()
    rule = lock["support_eligibility_rule"]
    assert rule["rule_b"]["union_support_computation"] == "DIRECT_SET_UNION_OF_CANONICAL_PLACE_IDS"
    assert rule["rule_b"]["assume_zero_multi_interest_overlap_forever"] is False
    assert rule["rule_b"]["current_core_catalog_multi_interest_overlap_poi_count"] == 0

    synthetic_map = {
        "food_cuisine": {"p1", "p2", "p3"},
        "coffee_culture": {"p1", "p2", "p4"},
    }
    res = _evaluate_combination_support(
        ("food_cuisine", "coffee_culture"),
        synthetic_map,
        days=3,
        min_poi_visits_per_day=2,
    )
    assert res["sum_support"] == 6
    assert res["union_support"] == 4
    assert res["overlap_poi_count"] == 2
    assert res["rule_a_passed"] is True
    assert res["rule_b_passed"] is False
    assert res["eligible"] is False
    assert res["support_class"] == "EXCLUDED"
    assert res["exclusion_reason_code"] == "TOTAL_INTEREST_CAPACITY_INSUFFICIENT"


def test_method_08_excluded_stress_clear_semantics_and_claim_boundary():
    """METHOD-08: EXCLUDED/STRESS/CLEAR semantics and interest claim boundary frozen."""
    lock = _load_method_lock()
    rule = lock["support_eligibility_rule"]
    assert rule["excluded_allowed_in_primary_100"] is False
    assert rule["stress_allowed_in_primary_100"] is True
    assert rule["fixed_stress_percentage"] is None
    assert rule["classes"]["EXCLUDED"]["allowed_in_primary_100"] is False
    assert rule["classes"]["STRESS"]["allowed_in_primary_100"] is True
    assert rule["classes"]["STRESS"]["fixed_stress_percentage"] is None
    assert rule["classes"]["CLEAR"]["allowed_in_primary_100"] is True

    cb = lock["interest_claim_boundary"]
    assert cb["interest_support_role"] == "SCENARIO_FEASIBILITY_METADATA_ONLY"
    assert cb["preference_satisfaction_is_primary_w06_metric"] is False
    assert cb["claim_planner_satisfies_real_user_interests_allowed"] is False


def test_method_09_budget_80_applicable_20_null():
    """METHOD-09: 80 budget-applicable scenarios and 20 budget-null scenarios."""
    lock = _load_method_lock()
    bp = lock["budget_policy"]
    assert bp["budget_applicable_scenarios"] == 80
    assert bp["budget_null_scenarios"] == 20
    assert bp["budget_applicable_scenarios"] + bp["budget_null_scenarios"] == 100


def test_method_10_budget_tiers_b1_b2_b3():
    """METHOD-10: budget tiers are exactly B1 (500k/day), B2 (1M/day), B3 (2M/day)."""
    lock = _load_method_lock()
    bp = lock["budget_policy"]
    tiers = bp["nominal_tiers"]
    assert list(tiers.keys()) == ["B1", "B2", "B3"]
    assert tiers["B1"]["daily_nominal_vnd"] == 500000
    assert tiers["B2"]["daily_nominal_vnd"] == 1000000
    assert tiers["B3"]["daily_nominal_vnd"] == 2000000
    assert bp["scenario_budget_formula"] == "daily_nominal_tier_vnd * scenario.days"
    for tier_key, daily_vnd in (("B1", 500000), ("B2", 1000000), ("B3", 2000000)):
        by_days = tiers[tier_key]["scenario_budget_by_days_vnd"]
        assert by_days == {
            "2": daily_vnd * 2,
            "3": daily_vnd * 3,
            "4": daily_vnd * 4,
        }


def test_method_11_budget_tier_counts_27_27_26():
    """METHOD-11: among 80 budget-applicable scenarios, B1=27, B2=27, B3=26."""
    lock = _load_method_lock()
    tiers = lock["budget_policy"]["nominal_tiers"]
    assert tiers["B1"]["scenario_count"] == 27
    assert tiers["B2"]["scenario_count"] == 27
    assert tiers["B3"]["scenario_count"] == 26
    assert sum(t["scenario_count"] for t in tiers.values()) == 80


def test_method_12_budget_tiers_nominal_not_real_world():
    """METHOD-12: budget tiers marked NOMINAL_BENCHMARK_BUDGET_TIERS, not real-world prices."""
    lock = _load_method_lock()
    bp = lock["budget_policy"]
    assert bp["same_model_gemini_budget_calibration"] == "FORBIDDEN"
    assert bp["model_output_may_determine_benchmark_budget_ceilings"] is False
    assert bp["tier_classification"] == "NOMINAL_BENCHMARK_BUDGET_TIERS"
    assert bp["represents_real_world_travel_prices"] is False
    assert bp["represents_validated_cost_estimates"] is False
    assert bp["represents_price_ground_truth"] is False
    assert bp["metric"] == "ESTIMATED_BUDGET_COMPLIANCE"
    assert bp["zero_estimated_cost_frequency_role"] == "DESCRIPTIVE_ONLY"
    assert bp["zero_estimated_cost_may_independently_fail_scenario"] is False


def test_method_13_travel_style_vocabulary_four_values():
    """METHOD-13: travel style vocabulary has exactly four values and is descriptive input variation only."""
    lock = _load_method_lock()
    ts = lock["travel_style_policy"]
    assert ts["vocabulary"] == ["BACKPACKER", "BUDGET", "COMFORT", "LUXURY"]
    assert ts["role"] == "DESCRIPTIVE_INPUT_VARIATION_ONLY"
    assert ts["has_primary_metric"] is False
    assert ts["inferential_subgroup_claim_allowed"] is False


def test_method_14_travel_style_counts_25_each():
    """METHOD-14: travel style marginal counts are 25 each."""
    lock = _load_method_lock()
    ts = lock["travel_style_policy"]
    assert ts["marginal_counts"] == {
        "BACKPACKER": 25,
        "BUDGET": 25,
        "COMFORT": 25,
        "LUXURY": 25,
    }
    assert sum(ts["marginal_counts"].values()) == 100


def test_method_15_weekend_exposure_50_50_and_date_window():
    """METHOD-15: 50 weekend_exposed / 50 non_weekend_exposed within 2026-11-02..2026-12-13."""
    lock = _load_method_lock()
    dp = lock["date_policy"]
    assert dp["window_start_date"] == "2026-11-02"
    assert dp["window_end_date"] == "2026-12-13"
    start_dt = datetime.date.fromisoformat(dp["window_start_date"])
    end_dt = datetime.date.fromisoformat(dp["window_end_date"])
    assert start_dt.weekday() == 0  # Monday
    assert end_dt.weekday() == 6  # Sunday
    assert (end_dt - start_dt).days + 1 == 42
    assert dp["trip_dates_must_be_contiguous"] is True
    assert dp["weekend_exposed_count"] == 50
    assert dp["non_weekend_exposed_count"] == 50
    assert dp["marginal_counts"] == {"weekend_exposed": 50, "non_weekend_exposed": 50}
    assert dp["role"] == "INPUT_VARIATION_ONLY"
    assert dp["scientific_weekday_weekend_subgroup_defined"] is False
    assert dp["weekend_opening_hours_performance_claims_allowed"] is False


def test_method_16_no_formal_difficulty_tier():
    """METHOD-16: NO_FORMAL_DIFFICULTY_TIER frozen; EASY/MEDIUM/HARD forbidden."""
    lock = _load_method_lock()
    diff = lock["difficulty_policy"]
    assert diff["policy"] == "NO_FORMAL_DIFFICULTY_TIER"
    assert diff["forbidden_difficulty_strata"] == ["EASY", "MEDIUM", "HARD"]
    assert diff["allowed_pre_run_descriptive_metadata"] == [
        "days",
        "interest_count",
        "support_class",
        "budget_tier",
        "weekend_exposure",
        "travel_style",
    ]


def test_method_17_no_oh_quota_in_primary():
    """METHOD-17: primary 100 uses NATURAL_EXPOSURE_ONLY with no OH quota; separate probe deferred."""
    lock = _load_method_lock()
    oh = lock["opening_hours_policy"]
    assert oh["primary_100_policy"] == "NATURAL_EXPOSURE_ONLY"
    assert oh["oh_enriched_quota_allowed"] is False
    assert oh["select_primary_scenario_for_more_opening_hours_evidence_allowed"] is False
    assert oh["mandatory_future_reporting"] == [
        "opening_hours_evidence_coverage",
        "known_opening_hours_violations",
        "UNKNOWN_count_and_rate",
        "per_destination_evidence_coverage",
    ]
    assert oh["separate_oh_probe_set_status"] == "DEFERRED_FOR_W06_V1"
    assert oh["separate_oh_probe_set_created"] is False


def test_method_18_infeasible_diagnostics_deferred():
    """METHOD-18: infeasible diagnostics deferred outside primary W06 v1."""
    lock = _load_method_lock()
    inf = lock["infeasible_scenarios_policy"]
    assert inf["INFEASIBLE_DIAGNOSTIC_POLICY"] == "DEFERRED_OUTSIDE_PRIMARY_W06_V1"
    assert inf["intentionally_infeasible_scenarios_in_primary_100"] == 0
    assert inf["infeasible_diagnostic_set_created_in_this_task"] is False
    assert inf["claim_planner_detects_infeasibility_or_refusal_allowed"] is False


def test_method_19_seed_exact_2026101506():
    """METHOD-19: scenario_generation_seed is frozen at exactly 2026101506."""
    lock = _load_method_lock()
    sp = lock["generation_seed_policy"]
    assert sp["scenario_generation_seed"] == 2026101506


def test_method_20_one_seed_no_seed_shopping():
    """METHOD-20: one seed only, no seed shopping, committed before generation, deterministic priority order."""
    lock = _load_method_lock()
    sp = lock["generation_seed_policy"]
    assert sp["allowed_seed_count"] == 1
    assert sp["seed_shopping_allowed"] is False
    assert sp["seed_committed_before_generation"] is True

    gp = lock["generator_policy"]
    assert gp["deterministic_required"] is True
    assert gp["may_inspect_gemini_or_model_output"] is False
    expected_priorities = [
        (1, "exact destination allocation"),
        (2, "exact days marginal"),
        (3, "exact interest-count marginal"),
        (4, "exact budget applicability/tier marginal"),
        (5, "exact travel-style marginal"),
        (6, "exact weekend-exposure marginal"),
        (7, "scenario eligibility"),
        (8, "duplicate/near-duplicate rules"),
        (9, "CLEAR/STRESS coverage"),
        (10, "minimize remaining cross-dimension imbalance"),
    ]
    actual = [(item["priority"], item["rule"]) for item in gp["priority_order"]]
    assert actual == expected_priorities

    stress = lock["stress_policy"]
    assert stress["manual_stress_quota_allowed"] is False
    assert stress["fixed_stress_percentage"] is None
    assert stress["stress_status_source"] == "FROZEN_SUPPORT_RULES_ONLY"
    assert stress["systematic_exclusion_of_eligible_stress_candidates_forbidden"] is True
    assert stress["final_stress_count_nature"] == "OUTPUT_OF_FROZEN_GENERATION_PROCEDURE"


def test_method_21_canonical_near_duplicate_signature_frozen():
    """METHOD-21: canonical scenario near-duplicate signature is frozen; exact duplicates forbidden."""
    lock = _load_method_lock()
    nd = lock["near_duplicate_policy"]
    assert nd["canonical_scenario_signature"] == [
        "destination_slug",
        "days",
        "sorted(interests)",
        "budget_tier_or_null",
        "weekend_exposure",
        "travel_style",
    ]
    assert nd["exact_duplicate_signature_policy"] == "FORBIDDEN"
    assert nd["free_text_notes_can_create_uniqueness"] is False


def test_method_22_dynamic_interest_combination_repeat_cap_formula_frozen():
    """METHOD-22: dynamic interest-combination repeat-cap formula and stop-on-infeasibility rule frozen."""
    lock = _load_method_lock()
    nd = lock["near_duplicate_policy"]
    assert nd["interest_combination_repeat_cap_formula"] == EXPECTED_REPEAT_CAP_FORMULA
    assert nd["compute_repeat_cap_before_candidate_sampling"] is True
    assert nd["exceed_repeat_cap_without_mathematical_infeasibility_proof_allowed"] is False
    assert nd["infeasibility_protocol"] == "STOP_DO_NOT_SILENTLY_RELAX_REQUIRE_FORMAL_METHOD_AMENDMENT"


def test_method_23_rejection_reason_vocabulary_exact():
    """METHOD-23: rejection log deterministic fields and 10 allowed reason codes frozen."""
    lock = _load_method_lock()
    rl = lock["rejection_log_policy"]
    assert rl["log_every_rejected_candidate"] is True
    assert rl["required_deterministic_fields"] == [
        "candidate_index",
        "candidate_sha256",
        "reason_code",
        "rule_version",
        "replacement_candidate_index",
    ]
    assert rl["allowed_reason_codes"] == [
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
    ]
    assert rl["include_model_output_allowed"] is False
    assert rl["reason_may_depend_on_gemini_behavior"] is False


def test_method_24_manual_qa_cannot_inspect_model_output():
    """METHOD-24: manual QA is blinded from model output and uses deterministic stream replacement only."""
    lock = _load_method_lock()
    qa = lock["manual_qa_policy"]
    assert qa["reviewer_allowed_to_inspect"] == [
        "scenario_input",
        "catalog_evidence",
        "support_matrix",
        "schema_validity",
        "date_validity",
        "deterministic_generation_metadata",
    ]
    assert qa["reviewer_forbidden_to_inspect"] == [
        "Gemini_output",
        "planner_pass_fail",
        "planner_estimated_cost",
        "future_scientific_result",
    ]
    assert qa["manual_rejection_requires_allowed_reason_code"] is True
    assert qa["replacement_policy"] == "NEXT_DETERMINISTIC_ELIGIBLE_CANDIDATE_IN_GENERATOR_STREAM"
    assert qa["hand_written_replacement_scenario_allowed"] is False


def test_method_25_gemini_pilot_cannot_influence_scenario_design():
    """METHOD-25: Gemini/model-behavior pilot influencing scenario design is FORBIDDEN."""
    lock = _load_method_lock()
    pp = lock["pilot_policy"]
    assert pp["gemini_or_model_behavior_pilot_influencing_scenario_design"] == "FORBIDDEN"
    assert pp["same_model_budget_calibration"] == "FORBIDDEN"
    assert pp["allowed_pre_freeze_activities"] == [
        "synthetic_fixture_tests",
        "offline_generator_qa",
        "schema_validation",
        "support_matrix_validation",
    ]
    assert pp["send_final_scenario_to_gemini_before_p11_and_preregistration_allowed"] is False


def test_method_26_executions_per_scenario_equals_1():
    """METHOD-26: executions_per_scenario == 1 and one-shot interpretation recorded."""
    lock = _load_method_lock()
    ep = lock["execution_policy"]
    assert ep["executions_per_scenario"] == 1
    assert ep["PRIMARY_RESULT_INTERPRETATION"] == "ONE_SHOT_BENCHMARK_OUTCOME_UNDER_RECORDED_CONFIGURATION"
    assert ep["claim_stable_expected_performance_across_repeated_stochastic_executions_allowed"] is False


def test_method_27_automatic_retry_equals_0():
    """METHOD-27: automatic_retry_count == 0 and invalid execution remains non-pass in assigned denominator."""
    lock = _load_method_lock()
    ep = lock["execution_policy"]
    assert ep["automatic_retry_count"] == 0
    assert ep["invalid_execution_remains_non_pass_in_assigned_denominator"] is True


def test_method_28_subgroups_outside_destination_are_descriptive_only():
    """METHOD-28: subgroups outside destination are SECONDARY_DESCRIPTIVE_ONLY; no p-values or inferential claims."""
    lock = _load_method_lock()
    sg = lock["subgroup_policy"]
    assert sg["primary_required_reporting"] == [
        "overall",
        "per_destination",
        "equal_destination_macro",
    ]
    assert sg["secondary_descriptive_axes"] == [
        "budget_applicability",
        "trip_length",
        "interest_count",
        "support_class",
        "travel_style",
        "weekday_weekend",
        "individual_interest",
    ]
    assert sg["secondary_axes_classification"] == "SECONDARY_DESCRIPTIVE_ONLY"
    assert sg["p_values_allowed"] is False
    assert sg["inferential_subgroup_claims_allowed"] is False
    assert sg["scenario_level_bootstrap_unit_modified"] is False
    assert sg["frozen_bootstrap_resampling_unit"] == "scenario"

    cb = lock["scenario_counts_and_cross_balance_policy"]
    assert cb["require_perfect_factorial_balance"] is False
    assert cb["required_generator_reporting"] == [
        "all_locked_marginal_counts",
        "cross_tab_counts",
        "max_min_cross_cell_imbalance",
        "unavoidable_imbalance",
    ]
    assert cb["optimize_based_on_model_performance_allowed"] is False


def test_method_29_no_final_scenarios_generated():
    """METHOD-29: real_scenarios_generated is false and no final 100 scenarios exist in data/evaluation/w06."""
    lock = _load_method_lock()
    matrix = _load_support_matrix()
    assert lock["real_scenarios_generated"] is False
    assert lock["scenario_generator_implemented"] is False
    assert matrix["real_scenarios_generated"] is False
    assert matrix["is_final_100_scenario_manifest"] is False


def test_method_30_p11_not_created():
    """METHOD-30: p11_created is false and preregistration_created is false."""
    lock = _load_method_lock()
    matrix = _load_support_matrix()
    assert lock["p11_created"] is False
    assert lock["preregistration_created"] is False
    assert matrix["p11_created"] is False


def test_method_31_gemini_not_called():
    """METHOD-31: gemini_called is false and scientific_results_generated is false."""
    lock = _load_method_lock()
    matrix = _load_support_matrix()
    assert lock["gemini_called"] is False
    assert lock["scientific_results_generated"] is False
    assert matrix["gemini_called"] is False
    assert matrix["model_output_included"] is False


def test_method_32_instrumentation_amendment_required_and_historical_contract_untouched():
    """METHOD-32: instrument_amendment_required is true; historical Measurement Contract and Discrepancies recorded."""
    lock = _load_method_lock()
    assert lock["instrument_amendment_required"] is True
    assert lock["instrumentation_amendment_required"] is True
    assert lock["historical_measurement_contract_modified"] is False
    assert lock["production_planner_behavior_modified"] is False
    assert lock["w5_artifacts_modified"] is False

    hd = lock["historical_discrepancies"]
    assert hd["historical_charge_tag_count_discrepancy"] == "NON_BLOCKING_HISTORICAL_COUNT_DISCREPANCY"
    assert hd["historical_parser_currently_exists_false"] == "EXPECTED_HISTORICAL_STATE_SUPERSEDED_BY_IMPLEMENTATION"
    assert hd["historical_measurement_contract_rewritten"] is False

    mc = json.loads(MEASUREMENT_CONTRACT_JSON_PATH.read_text(encoding="utf-8"))
    assert mc["contract_id"] == "W06-MEASUREMENT-CONTRACT-01"
    assert mc["contract_version"] == "1.1.0"
    assert mc["opening_hours_semantics"]["audit_evidence"]["parser_currently_exists"] is False

    assert METHOD_LOCK_MD_PATH.exists()
    assert GENERATION_POLICY_MD_PATH.exists()
    md_lock_text = METHOD_LOCK_MD_PATH.read_text(encoding="utf-8")
    md_policy_text = GENERATION_POLICY_MD_PATH.read_text(encoding="utf-8")
    assert "W06-SCENARIO-METHOD-LOCK-01" in md_lock_text
    assert "LOCKED_PENDING_INSTRUMENT_AMENDMENT" in md_lock_text
    assert "2026101506" in md_policy_text
    assert "ONE_SHOT_BENCHMARK_OUTCOME_UNDER_RECORDED_CONFIGURATION" in md_policy_text


def test_method_33_support_matrix_fully_reproducible_from_catalog_and_mapping():
    """METHOD-33: support matrix is 100% reproducible from gomate_places_freeze_v2.json and poi_to_canonical_vector."""
    matrix = _load_support_matrix()
    lock = _load_method_lock()

    assert matrix["artifact_id"] == "W06-SCENARIO-SUPPORT-MATRIX-V1"
    assert matrix["method_lock_id"] == "W06-SCENARIO-METHOD-LOCK-01"
    assert matrix["base_develop_sha"] == EXPECTED_BASE_DEVELOP_SHA
    assert matrix["source_catalog"]["lf_sha256"] == _lf_normalized_sha256(CATALOG_PATH)
    assert matrix["authoritative_interest_mapping"]["lf_sha256"] == _lf_normalized_sha256(RECA_CONTRACT_PATH)

    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    core_pois = [p for p in catalog if p.get("is_rec_a_core_v2") is True]
    assert len(core_pois) == 622

    expected_single_counts = {
        "ha-noi": {
            "food_cuisine": 21,
            "culture_history": 37,
            "nature_outdoor": 12,
            "coffee_culture": 8,
            "beach_island": 1,
            "shopping_local": 3,
            "nightlife_entertainment": 12,
        },
        "da-nang": {
            "food_cuisine": 52,
            "culture_history": 53,
            "nature_outdoor": 8,
            "coffee_culture": 49,
            "beach_island": 10,
            "shopping_local": 21,
            "nightlife_entertainment": 11,
        },
        "ha-long": {
            "food_cuisine": 37,
            "culture_history": 16,
            "nature_outdoor": 10,
            "coffee_culture": 21,
            "beach_island": 3,
            "shopping_local": 15,
            "nightlife_entertainment": 5,
        },
    }
    expected_eligible_by_days = {
        "ha-noi": {"2": 40, "3": 40, "4": 25},
        "da-nang": {"2": 63, "3": 63, "4": 63},
        "ha-long": {"2": 62, "3": 61, "4": 40},
    }
    expected_stress_by_days = {
        "ha-noi": {"2": 15, "3": 15, "4": 0},
        "da-nang": {"2": 0, "3": 0, "4": 0},
        "ha-long": {"2": 21, "3": 36, "4": 15},
    }

    for dest in SUPPORTED_DESTINATIONS:
        d_pois = [p for p in core_pois if p.get("destination_slug") == dest]
        interest_to_pois: Dict[str, Set[str]] = {k: set() for k in CANONICAL_INTERESTS}
        for p in d_pois:
            vec, _ = poi_to_canonical_vector(p)
            for idx, val in enumerate(vec):
                if val > 0:
                    interest_to_pois[CANONICAL_INTERESTS[idx]].add(p["place_id"])

        dest_entry = matrix["destinations"][dest]
        assert dest_entry["canonical_interest_support_counts"] == expected_single_counts[dest]
        assert dest_entry["distinct_eligible_combinations_by_days"] == expected_eligible_by_days[dest]
        assert dest_entry["distinct_stress_combinations_by_days"] == expected_stress_by_days[dest]

        for d in (2, 3, 4):
            d_entry = dest_entry["by_days"][str(d)]
            combos = d_entry["combinations"]
            assert len(combos) == 63

            recomputed_by_id = {}
            for k_size in (1, 2, 3):
                for combo in itertools.combinations(CANONICAL_INTERESTS, k_size):
                    sorted_interests = sorted(combo)
                    cid = f"{dest}__d{d}__k{k_size}__{'+'.join(sorted_interests)}"
                    recomputed_by_id[cid] = _evaluate_combination_support(
                        combo,
                        interest_to_pois,
                        days=d,
                        min_poi_visits_per_day=2,
                    )

            for item in combos:
                ref = recomputed_by_id[item["combination_id"]]
                assert item["support_counts"] == ref["counts"]
                assert item["sum_support"] == ref["sum_support"]
                assert item["union_support"] == ref["union_support"]
                assert item["overlap_poi_count"] == ref["overlap_poi_count"]
                assert item["rule_a_passed"] == ref["rule_a_passed"]
                assert item["rule_b_passed"] == ref["rule_b_passed"]
                assert item["eligible"] == ref["eligible"]
                assert item["support_class"] == ref["support_class"]
                assert item["stress_interests"] == ref["stress_interests"]
                assert item["exclusion_reason_code"] == ref["exclusion_reason_code"]

    assert lock["support_matrix_summary"] == matrix["global_summary"]


def test_method_34_destination_interest_count_and_days_cross_allocation_exact():
    """METHOD-34: destination x interest-count (and destination x days) cross-allocation exact."""
    lock = _load_method_lock()
    cross_k = lock["destination_interest_count_cross_allocation"]
    assert cross_k == {
        "ha-noi": {"1": 11, "2": 12, "3": 11},
        "da-nang": {"1": 11, "2": 11, "3": 11},
        "ha-long": {"1": 11, "2": 11, "3": 11},
    }
    row_totals_k = {dest: sum(row.values()) for dest, row in cross_k.items()}
    assert row_totals_k == {"ha-noi": 34, "da-nang": 33, "ha-long": 33}
    col_totals_k = {
        k: sum(cross_k[dest][k] for dest in ("ha-noi", "da-nang", "ha-long"))
        for k in ("1", "2", "3")
    }
    assert col_totals_k == {"1": 33, "2": 34, "3": 33}
    assert sum(row_totals_k.values()) == 100

    cross_d = lock["destination_days_cross_allocation"]
    assert cross_d == {
        "ha-noi": {"2": 11, "3": 12, "4": 11},
        "da-nang": {"2": 11, "3": 11, "4": 11},
        "ha-long": {"2": 11, "3": 11, "4": 11},
    }
    row_totals_d = {dest: sum(row.values()) for dest, row in cross_d.items()}
    assert row_totals_d == {"ha-noi": 34, "da-nang": 33, "ha-long": 33}
    col_totals_d = {
        d: sum(cross_d[dest][d] for dest in ("ha-noi", "da-nang", "ha-long"))
        for d in ("2", "3", "4")
    }
    assert col_totals_d == {"2": 33, "3": 34, "4": 33}


def test_method_35_repeat_cap_formula_scoped_by_destination_and_interest_count():
    """METHOD-35: repeat-cap formula is scoped by (destination, interest_count) across allowed days."""
    lock = _load_method_lock()
    matrix = _load_support_matrix()
    nd = lock["near_duplicate_policy"]
    assert nd["interest_combination_repeat_cap_formula"] == EXPECTED_REPEAT_CAP_FORMULA
    assert nd["repeat_cap_scope"] == "DESTINATION_AND_INTEREST_COUNT"
    assert nd["repeat_counting_key"] == "(destination_slug, sorted(interests))"
    assert nd["variation_in_days_budget_weekend_or_travel_style_resets_repeat_counter"] is False

    for dest in ("ha-noi", "da-nang", "ha-long"):
        assert matrix["destinations"][dest]["repeat_cap_formula"] == EXPECTED_REPEAT_CAP_FORMULA


def test_method_36_expected_repeat_caps_reproduce_from_support_matrix():
    """METHOD-36: expected repeat caps reproduce dynamically: HN 3/1/1, DN 2/1/1, HL 2/1/1."""
    lock = _load_method_lock()
    matrix = _load_support_matrix()
    recomputed = _recompute_repeat_caps(lock, matrix)

    expected = {
        "ha-noi": {
            "1": {
                "assigned_scenario_count": 11,
                "distinct_eligible_interest_combinations": 5,
                "repeat_cap": 3,
                "max_combination_slot_capacity": 15,
            },
            "2": {
                "assigned_scenario_count": 12,
                "distinct_eligible_interest_combinations": 15,
                "repeat_cap": 1,
                "max_combination_slot_capacity": 15,
            },
            "3": {
                "assigned_scenario_count": 11,
                "distinct_eligible_interest_combinations": 20,
                "repeat_cap": 1,
                "max_combination_slot_capacity": 20,
            },
        },
        "da-nang": {
            "1": {
                "assigned_scenario_count": 11,
                "distinct_eligible_interest_combinations": 7,
                "repeat_cap": 2,
                "max_combination_slot_capacity": 14,
            },
            "2": {
                "assigned_scenario_count": 11,
                "distinct_eligible_interest_combinations": 21,
                "repeat_cap": 1,
                "max_combination_slot_capacity": 21,
            },
            "3": {
                "assigned_scenario_count": 11,
                "distinct_eligible_interest_combinations": 35,
                "repeat_cap": 1,
                "max_combination_slot_capacity": 35,
            },
        },
        "ha-long": {
            "1": {
                "assigned_scenario_count": 11,
                "distinct_eligible_interest_combinations": 6,
                "repeat_cap": 2,
                "max_combination_slot_capacity": 12,
            },
            "2": {
                "assigned_scenario_count": 11,
                "distinct_eligible_interest_combinations": 21,
                "repeat_cap": 1,
                "max_combination_slot_capacity": 21,
            },
            "3": {
                "assigned_scenario_count": 11,
                "distinct_eligible_interest_combinations": 35,
                "repeat_cap": 1,
                "max_combination_slot_capacity": 35,
            },
        },
    }

    assert recomputed == expected
    assert lock["near_duplicate_policy"]["repeat_caps_by_destination_and_interest_count"] == expected
    for dest, caps_dict in expected.items():
        short_caps = {k: v["repeat_cap"] for k, v in caps_dict.items()}
        assert matrix["destinations"][dest]["repeat_cap_by_interest_count"] == short_caps


def test_method_37_single_interest_capacity_is_sufficient_for_33_scenarios():
    """METHOD-37: single-interest capacity under scoped repeat_cap is 15+14+12=41 >= 33."""
    lock = _load_method_lock()
    matrix = _load_support_matrix()
    recomputed = _recompute_repeat_caps(lock, matrix)

    k1_capacities = {
        dest: recomputed[dest]["1"]["max_combination_slot_capacity"]
        for dest in ("ha-noi", "da-nang", "ha-long")
    }
    assert k1_capacities == {"ha-noi": 15, "da-nang": 14, "ha-long": 12}
    for dest in ("ha-noi", "da-nang", "ha-long"):
        assert k1_capacities[dest] >= lock["destination_interest_count_cross_allocation"][dest]["1"]
    assert sum(k1_capacities.values()) == 41 >= 33

    summary = lock["near_duplicate_policy"]["single_interest_capacity_summary"]
    assert summary["required_single_interest_scenarios"] == 33
    assert summary["max_capacity_by_destination"] == {"ha-noi": 15, "da-nang": 14, "ha-long": 12}
    assert summary["total_max_single_interest_capacity"] == 41
    assert summary["capacity_sufficient_for_33_scenarios"] is True


def test_method_38_old_pooled_repeat_cap_interpretation_is_not_authoritative():
    """METHOD-38: old pooled repeat_cap interpretation is removed as authoritative and marked resolved."""
    lock = _load_method_lock()
    matrix = _load_support_matrix()
    nd = lock["near_duplicate_policy"]
    assert nd["old_pooled_repeat_cap_authoritative"] is False
    assert (
        nd["old_pooled_pigeonhole_conflict_status"]
        == "RESOLVED_BY_DESTINATION_INTEREST_COUNT_SCOPED_REPEAT_CAP"
    )
    assert "precomputed_repeat_cap_diagnostics" not in nd
    for dest in ("ha-noi", "da-nang", "ha-long"):
        assert "repeat_cap_over_distinct_eligible_any_days" not in matrix["destinations"][dest]
        assert "repeat_cap_over_distinct_eligible_all_days" not in matrix["destinations"][dest]


def test_method_39_joint_methodology_feasibility_pass():
    """METHOD-39: offline deterministic constructive check proves JOINT_METHOD_FEASIBILITY = PASS."""
    lock = _load_method_lock()
    matrix = _load_support_matrix()
    gate = lock["joint_method_feasibility_gate"]
    assert gate["JOINT_METHOD_FEASIBILITY"] == "PASS"
    assert gate["status"] == "PASS"

    assignments = _construct_feasible_abstract_assignment(lock, matrix)
    assert len(assignments) == 100

    # 1. Verify destination totals: 34 / 33 / 33
    dest_counts = Counter(a["destination_slug"] for a in assignments)
    assert dict(dest_counts) == {"ha-noi": 34, "da-nang": 33, "ha-long": 33}

    # 2. Verify interest-count totals: 33 / 34 / 33
    k_counts = Counter(str(a["interest_count"]) for a in assignments)
    assert dict(k_counts) == {"1": 33, "2": 34, "3": 33}

    # 3. Verify destination x interest-count cross-allocation: 11/12/11, 11/11/11, 11/11/11
    for dest in ("ha-noi", "da-nang", "ha-long"):
        for k_str in ("1", "2", "3"):
            cnt = sum(
                1 for a in assignments
                if a["destination_slug"] == dest and str(a["interest_count"]) == k_str
            )
            assert cnt == lock["destination_interest_count_cross_allocation"][dest][k_str]

    # 4. Verify trip-length totals (33/34/33) and destination x days cross-allocation
    d_counts = Counter(str(a["days"]) for a in assignments)
    assert dict(d_counts) == {"2": 33, "3": 34, "4": 33}
    for dest in ("ha-noi", "da-nang", "ha-long"):
        for d_str in ("2", "3", "4"):
            cnt = sum(
                1 for a in assignments
                if a["destination_slug"] == dest and str(a["days"]) == d_str
            )
            assert cnt == lock["destination_days_cross_allocation"][dest][d_str]

    # 5. Verify support eligibility: zero EXCLUDED combinations used
    for a in assignments:
        assert a["eligible"] is True
        assert a["support_class"] in ("CLEAR", "STRESS")
        dest_d_combos = {
            tuple(c["interests_sorted"]): c
            for c in matrix["destinations"][a["destination_slug"]]["by_days"][str(a["days"])]["combinations"]
        }
        matrix_entry = dest_d_combos[tuple(a["interests_sorted"])]
        assert matrix_entry["eligible"] is True
        assert matrix_entry["support_class"] != "EXCLUDED"

    # 6. Verify repeat_cap(destination, interest_count) across all days
    recomputed_caps = _recompute_repeat_caps(lock, matrix)
    combo_usage = Counter((a["destination_slug"], tuple(a["interests_sorted"])) for a in assignments)
    for (dest, interests_tuple), count in combo_usage.items():
        k_str = str(len(interests_tuple))
        cap = recomputed_caps[dest][k_str]["repeat_cap"]
        assert count <= cap, f"Repeat cap exceeded for {(dest, interests_tuple)}: {count} > {cap}"

    # 7. Verify budget, travel_style, weekend_exposure marginals and 100 unique canonical signatures
    budget_counts = Counter(a["budget_tier_or_null"] for a in assignments)
    assert budget_counts == {"B1": 27, "B2": 27, "B3": 26, None: 20}
    style_counts = Counter(a["travel_style"] for a in assignments)
    assert style_counts == {"BACKPACKER": 25, "BUDGET": 25, "COMFORT": 25, "LUXURY": 25}
    weekend_counts = Counter(a["weekend_exposure"] for a in assignments)
    assert weekend_counts == {True: 50, False: 50}

    signatures = {
        (
            a["destination_slug"],
            a["days"],
            tuple(a["interests_sorted"]),
            a["budget_tier_or_null"],
            a["weekend_exposure"],
            a["travel_style"],
        )
        for a in assignments
    }
    assert len(signatures) == 100


def test_method_40_joint_feasibility_check_uses_no_gemini_or_model_output():
    """METHOD-40: joint feasibility check is 100% offline and uses no Gemini or model output."""
    lock = _load_method_lock()
    gate = lock["joint_method_feasibility_gate"]
    assert gate["uses_gemini_or_model_output"] is False
    assert lock["gemini_called"] is False
    assert lock["generator_policy"]["may_inspect_gemini_or_model_output"] is False


def test_method_41_no_real_scenarios_generated_during_feasibility_proof():
    """METHOD-41: no real scenario files are generated on disk during feasibility proof."""
    lock = _load_method_lock()
    matrix = _load_support_matrix()
    before_files = sorted(p.name for p in (ROOT_DIR / "data" / "evaluation" / "w06").iterdir())
    _ = _construct_feasible_abstract_assignment(lock, matrix)
    after_files = sorted(p.name for p in (ROOT_DIR / "data" / "evaluation" / "w06").iterdir())
    assert before_files == after_files
    assert lock["joint_method_feasibility_gate"]["writes_final_scenario_files"] is False
    assert lock["joint_method_feasibility_gate"]["real_scenarios_generated"] is False
    assert lock["real_scenarios_generated"] is False


def test_method_42_p11_still_not_created():
    """METHOD-42: P11 assignment manifest is still not created."""
    lock = _load_method_lock()
    matrix = _load_support_matrix()
    assert lock["p11_created"] is False
    assert lock["joint_method_feasibility_gate"]["p11_created"] is False
    assert matrix["p11_created"] is False
    w06_files = {p.name for p in (ROOT_DIR / "data" / "evaluation" / "w06").iterdir()}
    assert not any("p11" in name.lower() or "assignment_manifest" in name.lower() for name in w06_files)
