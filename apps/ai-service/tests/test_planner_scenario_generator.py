"""Verification suite for W06-SCENARIO-GENERATOR-01 (GEN-01 through GEN-40).

Verifies the deterministic W06 scenario generator engine, constraint invariants,
rejection logger, fail-closed behavior, cross-dimension balance reporting,
and scientific boundaries in DRY_RUN / SYNTHETIC_GENERATOR_QA mode.
"""
from collections import Counter
import copy
import datetime
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import random
import sys
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
AI_SERVICE_ROOT = REPO_ROOT / "apps" / "ai-service"
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.evaluation.planner_scenario_generator import (  # noqa: E402
    ALLOWED_REJECTION_REASON_CODES,
    DEFAULT_CATALOG_PATH,
    DEFAULT_METHOD_LOCK_PATH,
    DEFAULT_RECA_CONTRACT_PATH,
    DEFAULT_SCENARIO_GENERATION_SEED,
    DEFAULT_SUPPORT_MATRIX_PATH,
    DRY_RUN_FIXTURE_LABEL,
    DRY_RUN_MODE,
    EXPECTED_CATALOG_LF_SHA256,
    FROZEN_EXECUTABLE_PRIORITY_TRACE,
    INFEASIBILITY_PROTOCOL_STATUS,
    ORDERED_DESTINATIONS,
    ORDERED_TRAVEL_STYLES,
    SCENARIO_GENERATOR_VERSION,
    ScenarioGenerationInfeasibleError,
    _run_phase_a_allocate_core_marginals,
    _run_phase_b_allocate_secondary_marginals,
    canonical_json_bytes,
    generate_dry_run_scenarios,
    lf_normalized_file_sha256,
    load_direct_catalog_interest_sets,
    load_method_lock_config,
    load_support_matrix,
    sha256_hex,
    verify_combination_direct_support,
)
from app.schemas.planner_benchmark import (  # noqa: E402
    CANONICAL_BENCHMARK_INTERESTS,
    BenchmarkScenarioInput,
)
from scripts.generate_w06_scenarios_dryrun import (  # noqa: E402
    main as dryrun_cli_main,
)

RECEIPT_PATH = REPO_ROOT / "data" / "evaluation" / "w06" / "w06_scenario_generator_01_receipt_v1.json"
DOC_PATH = REPO_ROOT / "docs" / "research" / "w06_scenario_generator_01_v1.md"

EXPECTED_METHOD_LOCK_SHA256 = "5e5359f9f10a0248a9cf031f8e8b26c0314c46aecfe0d9df479388bbe4fd1af9"
EXPECTED_SUPPORT_MATRIX_SHA256 = "68c2bfc2164e664b3856c31b99a92d75a588f64465526b47c9104918a51cedb4"
EXPECTED_MEASUREMENT_CONTRACT_SHA256 = "0ddc1f8d879493517cee25f247d2365a0bacb816dc33b129b0c6110d4bfb8298"
EXPECTED_RECA_CONTRACT_SHA256 = "1a62c36a95092be35ab78dca43e20f646016e154746ee051a499bdebfc67538c"
EXPECTED_PLANNER_PROMPT_SHA256 = "31387107994ed10aa0b5d42999dc4c46dcf5f408c6d9ca454db2b0ab8084ef65"
EXPECTED_PLANNER_SCHEMA_SHA256 = "1792dadcfa681ef75df3d66fb291b4d6702c6cced4fb4aab5d9e571884dc8685"
EXPECTED_DRY_RUN_SHA256 = "3c3b5314c2fca0fb3c2fb53cc1b4fc26cc06b83d058218adfa13f8b641c1f769"


@lru_cache(maxsize=1)
def _cached_bundle():
    return generate_dry_run_scenarios(seed=DEFAULT_SCENARIO_GENERATION_SEED)


@lru_cache(maxsize=1)
def _cached_catalog_sets():
    return load_direct_catalog_interest_sets(DEFAULT_CATALOG_PATH)


def test_w06_gen_01_same_input_same_seed_identical_canonical_output():
    """GEN-01: same input + same seed -> identical canonical output."""
    b1 = generate_dry_run_scenarios(seed=DEFAULT_SCENARIO_GENERATION_SEED)
    b2 = generate_dry_run_scenarios(seed=DEFAULT_SCENARIO_GENERATION_SEED)
    bytes_1 = canonical_json_bytes(b1.model_dump(mode="json"))
    bytes_2 = canonical_json_bytes(b2.model_dump(mode="json"))
    assert bytes_1 == bytes_2


def test_w06_gen_02_same_input_same_seed_identical_sha256():
    """GEN-02: same input + same seed -> identical SHA256."""
    b1 = _cached_bundle()
    b2 = generate_dry_run_scenarios(seed=DEFAULT_SCENARIO_GENERATION_SEED)
    sha_1 = sha256_hex(canonical_json_bytes(b1.model_dump(mode="json")))
    sha_2 = sha256_hex(canonical_json_bytes(b2.model_dump(mode="json")))
    assert sha_1 == sha_2
    assert sha_1 == EXPECTED_DRY_RUN_SHA256


def test_w06_gen_03_no_global_random_or_hash_ordering_dependence():
    """GEN-03: no global/random hash ordering dependence in observed output."""
    baseline_sha = sha256_hex(canonical_json_bytes(_cached_bundle().model_dump(mode="json")))
    random.seed(12345)
    _ = [random.random() for _ in range(50)]
    b_after_random = generate_dry_run_scenarios(seed=DEFAULT_SCENARIO_GENERATION_SEED)
    sha_after = sha256_hex(canonical_json_bytes(b_after_random.model_dump(mode="json")))
    assert sha_after == baseline_sha


def test_w06_gen_04_100_dry_run_assignment_slots():
    """GEN-04: 100 dry-run assignment slots with explicit DRY_RUN / SYNTHETIC_GENERATOR_QA markings."""
    bundle = _cached_bundle()
    assert bundle.slot_count == 100
    assert len(bundle.slots) == 100
    assert bundle.run_mode == DRY_RUN_MODE
    assert bundle.fixture_label == DRY_RUN_FIXTURE_LABEL
    assert bundle.is_final_100_scenarios is False
    assert [s.slot_index for s in bundle.slots] == list(range(1, 101))
    assert [s.scenario_id for s in bundle.slots] == [f"W06-DRYRUN-{i:03d}" for i in range(1, 101)]


def test_w06_gen_05_destination_exact_34_33_33():
    """GEN-05: destination exact 34/33/33."""
    bundle = _cached_bundle()
    counts = Counter(s.destination_slug for s in bundle.slots)
    assert dict(counts) == {"ha-noi": 34, "da-nang": 33, "ha-long": 33}
    assert set(counts.keys()) == set(ORDERED_DESTINATIONS)


def test_w06_gen_06_days_exact_33_34_33():
    """GEN-06: days exact 33/34/33."""
    bundle = _cached_bundle()
    counts = Counter(str(s.days) for s in bundle.slots)
    assert dict(counts) == {"2": 33, "3": 34, "4": 33}


def test_w06_gen_07_destination_by_days_exact_frozen_matrix():
    """GEN-07: destination x days exact frozen matrix."""
    bundle = _cached_bundle()
    lock = load_method_lock_config()
    observed = {d: {"2": 0, "3": 0, "4": 0} for d in ORDERED_DESTINATIONS}
    for s in bundle.slots:
        observed[s.destination_slug][str(s.days)] += 1
    assert observed == lock["destination_days_cross_allocation"]


def test_w06_gen_08_interest_count_exact_33_34_33():
    """GEN-08: interest_count exact 33/34/33."""
    bundle = _cached_bundle()
    counts = Counter(str(s.interest_count) for s in bundle.slots)
    assert dict(counts) == {"1": 33, "2": 34, "3": 33}


def test_w06_gen_09_destination_by_interest_count_exact_frozen_matrix():
    """GEN-09: destination x interest_count exact frozen matrix."""
    bundle = _cached_bundle()
    lock = load_method_lock_config()
    observed = {d: {"1": 0, "2": 0, "3": 0} for d in ORDERED_DESTINATIONS}
    for s in bundle.slots:
        observed[s.destination_slug][str(s.interest_count)] += 1
    assert observed == lock["destination_interest_count_cross_allocation"]


def test_w06_gen_10_budget_tier_counts_27_27_26_20():
    """GEN-10: budget B1/B2/B3/null = 27/27/26/20."""
    bundle = _cached_bundle()
    counts = Counter(
        s.budget_tier_or_null if s.budget_tier_or_null is not None else "null"
        for s in bundle.slots
    )
    assert dict(counts) == {"B1": 27, "B2": 27, "B3": 26, "null": 20}


def test_w06_gen_11_numeric_budget_formula_correct():
    """GEN-11: numeric budget formula daily_nominal_vnd * scenario.days (and None for null)."""
    bundle = _cached_bundle()
    daily_map = {"B1": 500000, "B2": 1000000, "B3": 2000000}
    for s in bundle.slots:
        assert s.currency == "VND"
        if s.budget_tier_or_null is None:
            assert s.budget is None
            assert s.scenario_input.budget is None
        else:
            expected = daily_map[s.budget_tier_or_null] * s.days
            assert s.budget == expected
            assert s.scenario_input.budget == expected


def test_w06_gen_12_travel_style_exact_25_each():
    """GEN-12: travel_style = 25 each (BACKPACKER, BUDGET, COMFORT, LUXURY)."""
    bundle = _cached_bundle()
    counts = Counter(s.travel_style for s in bundle.slots)
    assert dict(counts) == {
        "BACKPACKER": 25,
        "BUDGET": 25,
        "COMFORT": 25,
        "LUXURY": 25,
    }
    assert set(counts.keys()) == set(ORDERED_TRAVEL_STYLES)


def test_w06_gen_13_weekend_exposure_exact_50_50():
    """GEN-13: weekend_exposed = 50, non_weekend_exposed = 50."""
    bundle = _cached_bundle()
    wk_true = sum(1 for s in bundle.slots if s.weekend_exposure is True)
    wk_false = sum(1 for s in bundle.slots if s.weekend_exposure is False)
    assert wk_true == 50
    assert wk_false == 50


def test_w06_gen_14_all_dates_inside_allowed_window():
    """GEN-14: all dates inside 2026-11-02 through 2026-12-13."""
    bundle = _cached_bundle()
    w_start = datetime.date(2026, 11, 2)
    w_end = datetime.date(2026, 12, 13)
    for s in bundle.slots:
        s_dt = datetime.date.fromisoformat(s.start_date)
        e_dt = datetime.date.fromisoformat(s.end_date)
        assert w_start <= s_dt <= e_dt <= w_end


def test_w06_gen_15_all_trips_contiguous_and_weekend_flag_accurate():
    """GEN-15: all trips contiguous (end_date = start_date + d - 1) and weekend flag matches dates."""
    bundle = _cached_bundle()
    for s in bundle.slots:
        s_dt = datetime.date.fromisoformat(s.start_date)
        e_dt = datetime.date.fromisoformat(s.end_date)
        assert e_dt == s_dt + datetime.timedelta(days=s.days - 1)
        trip_days = [s_dt + datetime.timedelta(days=i) for i in range(s.days)]
        has_sat_or_sun = any(dt.weekday() in (5, 6) for dt in trip_days)
        assert has_sat_or_sun is s.weekend_exposure


def test_w06_gen_16_all_interest_keys_canonical():
    """GEN-16: all interest keys belong to the 7 canonical interests and are sorted."""
    bundle = _cached_bundle()
    canonical_set = set(CANONICAL_BENCHMARK_INTERESTS)
    for s in bundle.slots:
        assert len(s.interests) == s.interest_count
        assert s.interests == sorted(s.interests)
        assert len(set(s.interests)) == len(s.interests)
        assert set(s.interests).issubset(canonical_set)


def test_w06_gen_17_all_selected_combinations_are_eligible():
    """GEN-17: all selected combinations are eligible in the frozen support matrix."""
    bundle = _cached_bundle()
    matrix = load_support_matrix()
    for s in bundle.slots:
        combs = matrix["destinations"][s.destination_slug]["by_days"][str(s.days)]["combinations"]
        match = next(c for c in combs if c["interests_sorted"] == s.interests)
        assert match["eligible"] is True
        assert match["eligibility"] == "PRIMARY_ELIGIBLE"


def test_w06_gen_18_zero_excluded_combinations():
    """GEN-18: zero EXCLUDED combinations used."""
    bundle = _cached_bundle()
    assert bundle.invariants_verified["excluded_combinations_used"] == 0
    assert bundle.cross_balance_report.support_class_counts["EXCLUDED"] == 0
    for s in bundle.slots:
        assert s.support_class != "EXCLUDED"


def test_w06_gen_19_rule_a_verified_for_all_slots():
    """GEN-19: Rule A (for every requested interest i: n_i >= days) verified directly."""
    bundle = _cached_bundle()
    cat_sets = _cached_catalog_sets()
    for s in bundle.slots:
        assert s.rule_a_passed is True
        assert s.min_interest_support >= s.days
        for intr in s.interests:
            assert len(cat_sets[s.destination_slug][intr]) >= s.days


def test_w06_gen_20_rule_b_verified_using_direct_union_semantics():
    """GEN-20: Rule B (direct union_support >= days * 2 and sum_support >= days * 2) verified."""
    bundle = _cached_bundle()
    cat_sets = _cached_catalog_sets()
    for s in bundle.slots:
        direct = verify_combination_direct_support(
            s.destination_slug, s.days, s.interests, cat_sets, min_poi_visits_per_day=2
        )
        assert s.rule_b_passed is True
        assert s.union_support == direct["union_support"]
        assert s.sum_support == direct["sum_support"]
        assert direct["union_support"] >= s.days * 2
        assert direct["sum_support"] >= s.days * 2


def test_w06_gen_21_repeat_cap_never_exceeded():
    """GEN-21: repeat cap (3/1/1 for ha-noi, 2/1/1 for da-nang, 2/1/1 for ha-long) never exceeded."""
    bundle = _cached_bundle()
    expected_caps = {
        "ha-noi": {1: 3, 2: 1, 3: 1},
        "da-nang": {1: 2, 2: 1, 3: 1},
        "ha-long": {1: 2, 2: 1, 3: 1},
    }
    counts: Counter[tuple[str, tuple[str, ...]]] = Counter()
    for s in bundle.slots:
        key = (s.destination_slug, tuple(s.interests))
        counts[key] += 1
        assert counts[key] <= expected_caps[s.destination_slug][s.interest_count]


def test_w06_gen_22_repeat_counter_not_reset_by_days_budget_weekend_or_style():
    """GEN-22: repeat counter is pooled across days, budget, weekend_exposure, and travel_style."""
    bundle = _cached_bundle()
    # For k=2 and k=3, repeat_cap is 1 across the entire destination regardless of days/budget/weekend/style
    for dest in ORDERED_DESTINATIONS:
        for k in (2, 3):
            combos_at_dest_k = [
                tuple(s.interests)
                for s in bundle.slots
                if s.destination_slug == dest and s.interest_count == k
            ]
            # Every combination of size k in {2,3} at a destination is 100% distinct across all days!
            assert len(combos_at_dest_k) == len(set(combos_at_dest_k))


def test_w06_gen_23_zero_duplicate_canonical_signatures():
    """GEN-23: zero duplicate canonical signatures across all 100 scenarios."""
    bundle = _cached_bundle()
    sigs = [
        (
            s.destination_slug,
            s.days,
            tuple(s.interests),
            s.budget_tier_or_null,
            s.weekend_exposure,
            s.travel_style,
        )
        for s in bundle.slots
    ]
    assert len(sigs) == 100
    assert len(set(sigs)) == 100
    assert len({s.canonical_signature_sha256 for s in bundle.slots}) == 100


def test_w06_gen_24_clear_and_stress_classification_preserved():
    """GEN-24: CLEAR/STRESS classification matches frozen support matrix and direct catalog rules."""
    bundle = _cached_bundle()
    matrix = load_support_matrix()
    cat_sets = _cached_catalog_sets()
    for s in bundle.slots:
        combs = matrix["destinations"][s.destination_slug]["by_days"][str(s.days)]["combinations"]
        match = next(c for c in combs if c["interests_sorted"] == s.interests)
        direct = verify_combination_direct_support(
            s.destination_slug, s.days, s.interests, cat_sets, min_poi_visits_per_day=2
        )
        assert s.support_class == match["support_class"] == direct["support_class"]
        assert s.support_class in ("CLEAR", "STRESS")


def test_w06_gen_25_no_fixed_stress_quota_and_eligible_stress_not_excluded():
    """GEN-25: no fixed STRESS quota imposed; eligible STRESS combinations are included naturally."""
    bundle = _cached_bundle()
    lock = load_method_lock_config()
    assert lock["stress_policy"]["fixed_stress_percentage"] is None
    assert lock["stress_policy"]["manual_stress_quota_allowed"] is False

    by_dest = bundle.cross_balance_report.support_class_by_destination
    # Da Nang has 0 STRESS combinations in catalog; Ha Noi and Ha Long have both CLEAR and STRESS
    assert by_dest["da-nang"] == {"CLEAR": 33, "STRESS": 0, "EXCLUDED": 0}
    assert by_dest["ha-noi"]["CLEAR"] > 0 and by_dest["ha-noi"]["STRESS"] > 0
    assert by_dest["ha-long"]["CLEAR"] > 0 and by_dest["ha-long"]["STRESS"] > 0
    assert bundle.cross_balance_report.support_class_counts == {
        "CLEAR": 81,
        "STRESS": 19,
        "EXCLUDED": 0,
    }


def test_w06_gen_26_scenario_objects_validate_through_benchmark_scenario_input():
    """GEN-26: all 100 dry-run scenario objects validate through BenchmarkScenarioInput."""
    bundle = _cached_bundle()
    for s in bundle.slots:
        dumped = s.scenario_input.model_dump(mode="json")
        revalidated = BenchmarkScenarioInput.model_validate(dumped)
        assert revalidated == s.scenario_input


def test_w06_gen_27_all_allow_revisit_place_ids_false_and_dry_run_fixture_label():
    """GEN-27: all allow_revisit_place_ids are False and fixture_label is SYNTHETIC_GENERATOR_QA."""
    bundle = _cached_bundle()
    for s in bundle.slots:
        assert s.scenario_input.allow_revisit_place_ids is False
        assert s.scenario_input.fixture_label == DRY_RUN_FIXTURE_LABEL
        assert s.scenario_input.notes is None


def test_w06_gen_28_rejection_log_reason_codes_belong_to_frozen_vocabulary():
    """GEN-28: every rejection log entry uses only the frozen reason code vocabulary and has no model fields."""
    bundle = _cached_bundle()
    assert bundle.rejection_log_count == len(bundle.rejection_log)
    assert bundle.rejection_log_count > 0
    allowed_set = set(ALLOWED_REJECTION_REASON_CODES)
    forbidden_keys = {
        "gemini_output",
        "planner_output",
        "planner_pass_fail",
        "estimated_cost",
        "benchmark_result",
    }
    for entry in bundle.rejection_log:
        assert entry.reason_code in allowed_set
        assert entry.candidate_index >= 1
        assert len(entry.candidate_sha256) == 64
        assert entry.replacement_candidate_index is not None
        assert entry.replacement_candidate_index > entry.candidate_index
        entry_dict = entry.model_dump()
        assert forbidden_keys.isdisjoint(entry_dict.keys())


def test_w06_gen_29_rejection_log_deterministic_across_runs_and_manual_qa_replacement():
    """GEN-29: rejection log is byte-identical across runs and supports deterministic MANUAL_QA_REJECT replacement."""
    b1 = _cached_bundle()
    b2 = generate_dry_run_scenarios(seed=DEFAULT_SCENARIO_GENERATION_SEED)
    assert [r.model_dump() for r in b1.rejection_log] == [r.model_dump() for r in b2.rejection_log]

    # Verify manual QA reject of first chosen candidate replaces it deterministically with next eligible candidate
    first_chosen_cand_idx = b1.slots[0].candidate_index
    b_manual = generate_dry_run_scenarios(
        seed=DEFAULT_SCENARIO_GENERATION_SEED,
        manual_reject_candidate_indices={first_chosen_cand_idx},
    )
    manual_entries = [r for r in b_manual.rejection_log if r.reason_code == "MANUAL_QA_REJECT"]
    assert len(manual_entries) == 1
    assert manual_entries[0].candidate_index == first_chosen_cand_idx
    assert manual_entries[0].replacement_candidate_index is not None
    assert b_manual.slot_count == 100


def test_w06_gen_30_infeasibility_fails_closed_instead_of_relaxing_rules():
    """GEN-30: infeasibility fails closed with ScenarioGenerationInfeasibleError (never silently relaxes rules)."""
    base_lock = load_method_lock_config()
    base_matrix = load_support_matrix()

    # Case 1: Wrong seed -> fail closed
    with pytest.raises(ScenarioGenerationInfeasibleError) as exc_seed:
        generate_dry_run_scenarios(seed=99999999)
    assert exc_seed.value.protocol_status == INFEASIBILITY_PROTOCOL_STATUS

    # Case 2: Impossible destination marginal (e.g. ha-noi = 35) -> fail closed
    bad_lock_dest = copy.deepcopy(base_lock)
    bad_lock_dest["primary_benchmark"]["destination_allocation"]["ha-noi"] = 35
    with pytest.raises(ScenarioGenerationInfeasibleError) as exc_dest:
        generate_dry_run_scenarios(method_lock_override=bad_lock_dest)
    assert exc_dest.value.protocol_status == INFEASIBILITY_PROTOCOL_STATUS

    # Case 3: Impossible repeat cap (e.g. ha-noi k=1 repeat_cap = 1 for 11 slots with only 5 eligible combos) -> fail closed
    bad_lock_cap = copy.deepcopy(base_lock)
    bad_lock_cap["near_duplicate_policy"]["repeat_caps_by_destination_and_interest_count"]["ha-noi"]["1"]["repeat_cap"] = 1
    with pytest.raises(ScenarioGenerationInfeasibleError) as exc_cap:
        generate_dry_run_scenarios(method_lock_override=bad_lock_cap)
    assert exc_cap.value.protocol_status == INFEASIBILITY_PROTOCOL_STATUS

    # Case 4: All combinations in support matrix marked EXCLUDED for a cell -> fail closed
    bad_matrix = copy.deepcopy(base_matrix)
    for c in bad_matrix["destinations"]["ha-noi"]["by_days"]["4"]["combinations"]:
        if c["interest_count"] == 1:
            c["eligible"] = False
            c["support_class"] = "EXCLUDED"
    with pytest.raises(ScenarioGenerationInfeasibleError) as exc_elig:
        generate_dry_run_scenarios(support_matrix_override=bad_matrix)
    assert exc_elig.value.protocol_status == INFEASIBILITY_PROTOCOL_STATUS


def test_w06_gen_31_no_final_scenario_artifact_written_and_cli_protects_final_paths(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """GEN-31: no final scenario artifact written; CLI defaults to stdout and refuses protected paths."""
    exit_code = dryrun_cli_main([])
    assert exit_code == 0
    captured = json.loads(capsys.readouterr().out)
    assert captured["run_mode"] == "DRY_RUN"
    assert captured["fixture_label"] == "SYNTHETIC_GENERATOR_QA"
    assert captured["is_final_100_scenarios"] is False
    assert captured["real_scenarios_generated"] is False

    # Writing to tmp_path succeeds for DRY_RUN QA
    tmp_out = tmp_path / "dryrun_qa_bundle.json"
    assert dryrun_cli_main(["--output-json", str(tmp_out)]) == 0
    assert tmp_out.exists()
    _ = capsys.readouterr()

    # Writing to data/evaluation/w06/ or any p11/final_100 filename is strictly refused
    protected_target = REPO_ROOT / "data" / "evaluation" / "w06" / "dryrun_attempt.json"
    with pytest.raises(ValueError, match="Refusing to write DRY_RUN output"):
        dryrun_cli_main(["--output-json", str(protected_target)])

    p11_named_target = tmp_path / "w06_p11_scenarios.json"
    with pytest.raises(ValueError, match="Refusing to write DRY_RUN output"):
        dryrun_cli_main(["--output-json", str(p11_named_target)])


def test_w06_gen_32_no_p11_created():
    """GEN-32: generator dry-run bundle does not create P11; only canonical freeze P11 allowed if freeze receipt exists."""
    bundle = _cached_bundle()
    assert bundle.p11_created is False
    w06_dir = REPO_ROOT / "data" / "evaluation" / "w06"
    freeze_receipt = w06_dir / "w06_scenario_freeze_01_receipt_v1.json"
    allowed_p11 = {"w06_p11_assignment_manifest_v1.json"} if freeze_receipt.exists() else set()
    for p in w06_dir.rglob("*"):
        if p.name not in allowed_p11:
            assert "p11" not in p.name.lower(), f"Forbidden P11 artifact found: {p}"
        assert "final_100" not in p.name.lower(), f"Forbidden final_100 artifact found: {p}"


def test_w06_gen_33_no_preregistration_created():
    """GEN-33: no W06 preregistration artifact created."""
    for p in (REPO_ROOT / "data" / "evaluation" / "w06").rglob("*"):
        assert "prereg" not in p.name.lower(), f"Forbidden W06 preregistration file found: {p}"
    for p in (REPO_ROOT / "docs" / "research").rglob("*"):
        name_lower = p.name.lower()
        assert not (
            "w06" in name_lower and "prereg" in name_lower
        ), f"Forbidden W06 preregistration doc found: {p}"



def test_w06_gen_34_no_model_or_provider_called():
    """GEN-34: generator module does not import or call any LLM/provider client."""
    gen_src = (
        AI_SERVICE_ROOT / "app" / "evaluation" / "planner_scenario_generator.py"
    ).read_text(encoding="utf-8")
    forbidden_imports = (
        "google.genai",
        "google.generativeai",
        "openai",
        "anthropic",
        "planner_benchmark_runner",
        "planner_service",
    )
    for token in forbidden_imports:
        assert token not in gen_src, f"Forbidden provider reference '{token}' in generator source"
    bundle = _cached_bundle()
    assert bundle.gemini_called is False


def test_w06_gen_35_frozen_method_lock_unchanged():
    """GEN-35: frozen scenario method lock SHA256 unchanged."""
    assert lf_normalized_file_sha256(DEFAULT_METHOD_LOCK_PATH) == EXPECTED_METHOD_LOCK_SHA256
    assert hashlib.sha256(DEFAULT_METHOD_LOCK_PATH.read_bytes()).hexdigest() == EXPECTED_METHOD_LOCK_SHA256


def test_w06_gen_36_frozen_support_matrix_unchanged():
    """GEN-36: frozen scenario support matrix SHA256 unchanged."""
    assert lf_normalized_file_sha256(DEFAULT_SUPPORT_MATRIX_PATH) == EXPECTED_SUPPORT_MATRIX_SHA256
    assert hashlib.sha256(DEFAULT_SUPPORT_MATRIX_PATH.read_bytes()).hexdigest() == EXPECTED_SUPPORT_MATRIX_SHA256


def test_w06_gen_37_historical_measurement_contract_unchanged():
    """GEN-37: historical W06 Measurement Contract SHA256 unchanged."""
    contract_path = REPO_ROOT / "data" / "evaluation" / "w06" / "w06_measurement_contract_v1.json"
    assert lf_normalized_file_sha256(contract_path) == EXPECTED_MEASUREMENT_CONTRACT_SHA256


def test_w06_gen_38_production_planner_unchanged():
    """GEN-38: production planner prompt and schema files unchanged."""
    prompt_path = AI_SERVICE_ROOT / "app" / "prompts" / "planner_prompt.py"
    schema_path = AI_SERVICE_ROOT / "app" / "schemas" / "planner.py"
    assert lf_normalized_file_sha256(prompt_path) == EXPECTED_PLANNER_PROMPT_SHA256
    assert lf_normalized_file_sha256(schema_path) == EXPECTED_PLANNER_SCHEMA_SHA256


def test_w06_gen_39_w5_unchanged():
    """GEN-39: W5 REC-A contract file unchanged."""
    reca_path = AI_SERVICE_ROOT / "recommendation" / "reca" / "contract.py"
    assert lf_normalized_file_sha256(reca_path) == EXPECTED_RECA_CONTRACT_SHA256


def test_w06_gen_40_cross_balance_report_and_receipt_complete():
    """GEN-40: cross-balance report, receipt, and documentation are deterministic and complete."""
    bundle = _cached_bundle()
    cb = bundle.cross_balance_report

    assert sum(cb.destination_by_days[d][day] for d in ORDERED_DESTINATIONS for day in ("2", "3", "4")) == 100
    assert sum(cb.destination_by_interest_count[d][k] for d in ORDERED_DESTINATIONS for k in ("1", "2", "3")) == 100
    assert sum(cb.destination_by_budget[d][b] for d in ORDERED_DESTINATIONS for b in ("B1", "B2", "B3", "null")) == 100
    assert sum(cb.destination_by_style[d][st] for d in ORDERED_DESTINATIONS for st in ORDERED_TRAVEL_STYLES) == 100
    assert sum(cb.destination_by_weekend[d][wk] for d in ORDERED_DESTINATIONS for wk in ("weekend_exposed", "non_weekend_exposed")) == 100
    assert sum(cb.days_by_interest_count[day][k] for day in ("2", "3", "4") for k in ("1", "2", "3")) == 100
    assert sum(cb.days_by_budget[day][b] for day in ("2", "3", "4") for b in ("B1", "B2", "B3", "null")) == 100
    assert sum(cb.days_by_style[day][st] for day in ("2", "3", "4") for st in ORDERED_TRAVEL_STYLES) == 100
    assert sum(cb.interest_count_by_budget[k][b] for k in ("1", "2", "3") for b in ("B1", "B2", "B3", "null")) == 100
    assert sum(cb.interest_count_by_style[k][st] for k in ("1", "2", "3") for st in ORDERED_TRAVEL_STYLES) == 100
    assert len(cb.unavoidable_imbalance_notes) >= 3

    assert RECEIPT_PATH.exists()
    raw_receipt = RECEIPT_PATH.read_bytes()
    receipt = json.loads(raw_receipt.decode("utf-8"))
    assert raw_receipt == canonical_json_bytes(receipt)
    assert receipt["task_id"] == "W06-SCENARIO-GENERATOR-01"
    assert receipt["version"] == "1.0.0"
    assert receipt["base_develop_sha"] == "fab7f63bb70a12ae332af82ae0f0261c35207ae0"
    assert receipt["seed"] == DEFAULT_SCENARIO_GENERATION_SEED
    assert receipt["method_lock_id"] == "W06-SCENARIO-METHOD-LOCK-01"
    assert receipt["support_matrix_id"] == "W06-SCENARIO-SUPPORT-MATRIX-V1"
    assert receipt["generator_version"] == SCENARIO_GENERATOR_VERSION
    assert receipt["generator_deterministic"] is True
    assert receipt["seed_shopping"] is False
    assert receipt["may_inspect_model_output"] is False
    assert receipt["final_scenarios_generated"] is False
    assert receipt["real_scenarios_generated"] is False
    assert receipt["p11_created"] is False
    assert receipt["preregistration_created"] is False
    assert receipt["gemini_called"] is False
    assert receipt["scientific_results_generated"] is False
    assert receipt["w5_modified"] is False
    assert receipt["production_planner_modified"] is False
    assert receipt["historical_measurement_contract_modified"] is False

    gen_source_path = REPO_ROOT / receipt["generator_source_path"]
    schema_source_path = REPO_ROOT / receipt["schema_source_path"]
    assert receipt["generator_source_sha256"] == lf_normalized_file_sha256(gen_source_path)
    assert receipt["schema_source_sha256"] == lf_normalized_file_sha256(schema_source_path)
    assert receipt["method_lock_sha256"] == EXPECTED_METHOD_LOCK_SHA256
    assert receipt["support_matrix_sha256"] == EXPECTED_SUPPORT_MATRIX_SHA256
    assert receipt["catalog_sha256"] == EXPECTED_CATALOG_LF_SHA256
    assert receipt["reca_contract_sha256"] == EXPECTED_RECA_CONTRACT_SHA256
    assert receipt["artifact_hashes"]["catalog_sha256"] == EXPECTED_CATALOG_LF_SHA256
    assert receipt["dry_run_verification_summary"]["determinism_sha256"] == EXPECTED_DRY_RUN_SHA256
    assert receipt["dry_run_verification_summary"]["executable_priority_trace"] == list(
        FROZEN_EXECUTABLE_PRIORITY_TRACE
    )

    assert DOC_PATH.exists()
    doc_text = DOC_PATH.read_text(encoding="utf-8")
    assert "W06-SCENARIO-GENERATOR-01" in doc_text
    assert "STOP_DO_NOT_SILENTLY_RELAX_REQUIRE_FORMAL_METHOD_AMENDMENT" in doc_text
    assert (
        "Under the audited repository revision, frozen scientific inputs, "
        "recorded dependency environment, and seed `2026101506`, repeated "
        "executions produced identical canonical output and SHA256"
    ) in doc_text
    assert (
        "This does not claim universal bit-for-bit reproducibility across arbitrary environments."
        in doc_text
    )
    assert "Any independent researcher running the generator" not in doc_text


def test_w06_gen_fix_01_frozen_executable_priority_order():
    """GEN-FIX-01: frozen executable priority order = 1..10 exactly; Phase B (4..6) finishes before Phase C (7..9)."""
    bundle = _cached_bundle()
    expected_trace = [
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
    ]
    assert bundle.executable_priority_trace == expected_trace

    # Directly verify Phase A (1..3) and Phase B (4..6) execute and freeze all 100 slots
    # BEFORE any interest combination eligibility or selection takes place
    method_lock = load_method_lock_config(DEFAULT_METHOD_LOCK_PATH)
    trace_ab: list[str] = []
    phase_a_slots = _run_phase_a_allocate_core_marginals(method_lock, trace_ab)
    assert trace_ab == [
        "DESTINATION_ALLOCATION",
        "DAYS_ALLOCATION",
        "INTEREST_COUNT_ALLOCATION",
    ]
    assert len(phase_a_slots) == 100
    for s in phase_a_slots:
        assert set(s.keys()) == {
            "slot_index",
            "destination_slug",
            "destination",
            "days",
            "interest_count",
        }

    phase_b_slots = _run_phase_b_allocate_secondary_marginals(
        phase_a_slots,
        method_lock,
        DEFAULT_SCENARIO_GENERATION_SEED,
        trace_ab,
    )
    assert trace_ab == expected_trace[:6]
    assert len(phase_b_slots) == 100

    phase_b_sha = sha256_hex(
        canonical_json_bytes([s.model_dump(mode="json") for s in phase_b_slots])
    )
    assert phase_b_sha == bundle.phase_b_locked_slots_sha256

    # Verify every final slot in bundle preserves the exact Phase B Priority 1..6 assignments
    for pslot, fslot in zip(phase_b_slots, bundle.slots):
        assert not hasattr(pslot, "interests")
        assert fslot.slot_index == pslot.slot_index
        assert fslot.destination_slug == pslot.destination_slug
        assert fslot.days == pslot.days
        assert fslot.interest_count == pslot.interest_count
        assert fslot.budget_tier_or_null == pslot.budget_tier_or_null
        assert fslot.budget == pslot.budget
        assert fslot.travel_style == pslot.travel_style
        assert fslot.weekend_exposure == pslot.weekend_exposure
        assert fslot.start_date == pslot.start_date
        assert fslot.end_date == pslot.end_date


def test_w06_gen_fix_02_phase_7_plus_failure_does_not_alter_priorities_1_to_6():
    """GEN-FIX-02: failure in Phase C (priority 7+) fails closed and never alters assignments made by Priorities 1..6."""
    baseline_bundle = _cached_bundle()
    baseline_p1_to_p6 = [
        (
            s.slot_index,
            s.destination_slug,
            s.days,
            s.interest_count,
            s.budget_tier_or_null,
            s.budget,
            s.travel_style,
            s.weekend_exposure,
            s.start_date,
            s.end_date,
        )
        for s in baseline_bundle.slots
    ]

    # Case A: Phase C fails in Priority 7 (SCENARIO_ELIGIBILITY)
    base_matrix = load_support_matrix(DEFAULT_SUPPORT_MATRIX_PATH)
    bad_matrix = copy.deepcopy(base_matrix)
    for c in bad_matrix["destinations"]["ha-noi"]["by_days"]["4"]["combinations"]:
        if c["interest_count"] == 1:
            c["eligible"] = False
            c["support_class"] = "EXCLUDED"

    with pytest.raises(ScenarioGenerationInfeasibleError) as exc_p7:
        generate_dry_run_scenarios(support_matrix_override=bad_matrix)
    assert exc_p7.value.protocol_status == INFEASIBILITY_PROTOCOL_STATUS
    assert exc_p7.value.phase_b_slots is not None
    assert list(exc_p7.value.executable_priority_trace[:6]) == [
        "DESTINATION_ALLOCATION",
        "DAYS_ALLOCATION",
        "INTEREST_COUNT_ALLOCATION",
        "BUDGET_ALLOCATION",
        "TRAVEL_STYLE_ALLOCATION",
        "WEEKEND_EXPOSURE_ALLOCATION",
    ]
    assert [
        (
            s.slot_index,
            s.destination_slug,
            s.days,
            s.interest_count,
            s.budget_tier_or_null,
            s.budget,
            s.travel_style,
            s.weekend_exposure,
            s.start_date,
            s.end_date,
        )
        for s in exc_p7.value.phase_b_slots
    ] == baseline_p1_to_p6

    # Case B: Phase C fails in Priority 8/9 (candidate stream exhausted after eligibility)
    with pytest.raises(ScenarioGenerationInfeasibleError) as exc_p8:
        generate_dry_run_scenarios(manual_reject_candidate_indices=set(range(1, 5000)))
    assert exc_p8.value.protocol_status == INFEASIBILITY_PROTOCOL_STATUS
    assert exc_p8.value.phase_b_slots is not None
    assert list(exc_p8.value.executable_priority_trace) == [
        "DESTINATION_ALLOCATION",
        "DAYS_ALLOCATION",
        "INTEREST_COUNT_ALLOCATION",
        "BUDGET_ALLOCATION",
        "TRAVEL_STYLE_ALLOCATION",
        "WEEKEND_EXPOSURE_ALLOCATION",
        "SCENARIO_ELIGIBILITY",
        "DUPLICATE_REPEAT_CAP",
        "CLEAR_STRESS_COVERAGE",
    ]
    assert [
        (
            s.slot_index,
            s.destination_slug,
            s.days,
            s.interest_count,
            s.budget_tier_or_null,
            s.budget,
            s.travel_style,
            s.weekend_exposure,
            s.start_date,
            s.end_date,
        )
        for s in exc_p8.value.phase_b_slots
    ] == baseline_p1_to_p6


def test_w06_gen_fix_03_catalog_hash_mismatch_fails_closed(tmp_path: Path):
    """GEN-FIX-03: catalog hash mismatch -> FAIL CLOSED."""
    tmp_catalog = tmp_path / "corrupted_catalog.json"
    tmp_catalog.write_bytes(DEFAULT_CATALOG_PATH.read_bytes() + b"\n")

    with pytest.raises(ScenarioGenerationInfeasibleError) as exc_cat:
        generate_dry_run_scenarios(catalog_path=tmp_catalog)
    assert exc_cat.value.protocol_status == INFEASIBILITY_PROTOCOL_STATUS
    assert "catalog LF SHA256 mismatch" in str(exc_cat.value)

    # Also test mismatch in method_lock["interest_mapping"]["catalog_lf_sha256"]
    bad_lock = copy.deepcopy(load_method_lock_config(DEFAULT_METHOD_LOCK_PATH))
    bad_lock["interest_mapping"]["catalog_lf_sha256"] = "0" * 64
    with pytest.raises(ScenarioGenerationInfeasibleError) as exc_lock_cat:
        generate_dry_run_scenarios(method_lock_override=bad_lock)
    assert exc_lock_cat.value.protocol_status == INFEASIBILITY_PROTOCOL_STATUS

    # Real catalog file remains untouched
    assert lf_normalized_file_sha256(DEFAULT_CATALOG_PATH) == EXPECTED_CATALOG_LF_SHA256


def test_w06_gen_fix_04_reca_contract_mapping_authority_mismatch_fails_closed(tmp_path: Path):
    """GEN-FIX-04: REC-A contract/mapping authority mismatch -> FAIL CLOSED."""
    tmp_reca = tmp_path / "corrupted_reca_contract.py"
    tmp_reca.write_bytes(DEFAULT_RECA_CONTRACT_PATH.read_bytes() + b"\n# modified\n")

    with pytest.raises(ScenarioGenerationInfeasibleError) as exc_reca:
        generate_dry_run_scenarios(reca_contract_path=tmp_reca)
    assert exc_reca.value.protocol_status == INFEASIBILITY_PROTOCOL_STATUS
    assert "REC-A contract LF SHA256 mismatch" in str(exc_reca.value)

    # Also test mismatch in method_lock["interest_mapping"]["source_file_lf_sha256"] and function_name
    bad_lock_sha = copy.deepcopy(load_method_lock_config(DEFAULT_METHOD_LOCK_PATH))
    bad_lock_sha["interest_mapping"]["source_file_lf_sha256"] = "f" * 64
    with pytest.raises(ScenarioGenerationInfeasibleError) as exc_lock_sha:
        generate_dry_run_scenarios(method_lock_override=bad_lock_sha)
    assert exc_lock_sha.value.protocol_status == INFEASIBILITY_PROTOCOL_STATUS

    bad_lock_fn = copy.deepcopy(load_method_lock_config(DEFAULT_METHOD_LOCK_PATH))
    bad_lock_fn["interest_mapping"]["function_name"] = "wrong_mapping_fn"
    with pytest.raises(ScenarioGenerationInfeasibleError) as exc_lock_fn:
        generate_dry_run_scenarios(method_lock_override=bad_lock_fn)
    assert exc_lock_fn.value.protocol_status == INFEASIBILITY_PROTOCOL_STATUS

    # Real REC-A contract remains untouched
    assert lf_normalized_file_sha256(DEFAULT_RECA_CONTRACT_PATH) == EXPECTED_RECA_CONTRACT_SHA256


def test_w06_gen_fix_05_support_matrix_hash_mismatch_fails_closed(tmp_path: Path):
    """GEN-FIX-05: support matrix hash mismatch -> FAIL CLOSED."""
    tmp_matrix = tmp_path / "corrupted_support_matrix.json"
    tmp_matrix.write_bytes(DEFAULT_SUPPORT_MATRIX_PATH.read_bytes() + b"\n")

    with pytest.raises(ScenarioGenerationInfeasibleError) as exc_sm:
        generate_dry_run_scenarios(support_matrix_path=tmp_matrix)
    assert exc_sm.value.protocol_status == INFEASIBILITY_PROTOCOL_STATUS
    assert "support matrix SHA256 mismatch" in str(exc_sm.value)

    # Also test mismatch in method_lock["interest_mapping"]["pre_freeze_support_matrix_sha256"]
    bad_lock_sm = copy.deepcopy(load_method_lock_config(DEFAULT_METHOD_LOCK_PATH))
    bad_lock_sm["interest_mapping"]["pre_freeze_support_matrix_sha256"] = "a" * 64
    with pytest.raises(ScenarioGenerationInfeasibleError) as exc_lock_sm:
        generate_dry_run_scenarios(method_lock_override=bad_lock_sm)
    assert exc_lock_sm.value.protocol_status == INFEASIBILITY_PROTOCOL_STATUS

    # Real support matrix remains untouched
    assert lf_normalized_file_sha256(DEFAULT_SUPPORT_MATRIX_PATH) == EXPECTED_SUPPORT_MATRIX_SHA256
