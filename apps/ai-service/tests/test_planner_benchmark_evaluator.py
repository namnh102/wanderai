"""Focused tests for W06-INSTRUMENT-01B (Deterministic Core Constraint Evaluator).

Covers W06-I01B-01 through W06-I01B-30.
"""
import json
from pathlib import Path
import sys
from typing import List, Optional

AI_SERVICE_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = AI_SERVICE_ROOT.parent.parent
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.evaluation.planner_benchmark_evaluator import (  # noqa: E402
    EVALUATOR_VERSION,
    EVALUATOR_VERSION_01B,
    FINAL_CORE_PASS_STATUS_01B,
    FINAL_CORE_PASS_STATUS_01C,
    MINIMUM_ITEMS_PER_DAY_CONTRACT_STATUS,
    OPENING_HOURS_STATUS_01B,
    OPENING_HOURS_STATUS_01C,
    compute_haversine_geo_distance_proxy_km,
    evaluate_benchmark_scenario,
    evaluate_run_directory,
    load_core_catalog_by_place_id,
    parse_strict_hhmm,
)
from app.prompts.planner_benchmark_prompt import (  # noqa: E402
    BENCHMARK_PROMPT_VERSION,
    build_destination_catalog_context,
)
from app.schemas.planner_benchmark import (  # noqa: E402
    ActivityKind,
    BenchmarkBudgetAnalysis,
    BenchmarkItineraryDay,
    BenchmarkItineraryItem,
    BenchmarkPlanResponse,
    BenchmarkRunManifest,
    BenchmarkRunStatus,
    BenchmarkScenarioInput,
    BenchmarkUsageMetadata,
)
from app.services.planner_benchmark_runner import (  # noqa: E402
    canonical_json_bytes,
    compute_catalog_sha256,
    sha256_bytes,
    write_canonical_json,
)
from scripts.evaluate_w06_planner_run import main as evaluator_cli_main  # noqa: E402

RECEIPT_01B_JSON_PATH = REPO_ROOT / "data" / "evaluation" / "w06" / "w06_instrument_01b_receipt_v1.json"
RECEIPT_01B_MD_PATH = REPO_ROOT / "docs" / "research" / "w06_instrument_01b_implementation_v1.md"
CONTRACT_JSON_PATH = REPO_ROOT / "data" / "evaluation" / "w06" / "w06_measurement_contract_v1.json"
PLANNER_EVAL_DIR = REPO_ROOT / "data" / "evaluation" / "planner"


def _make_scenario(
    *,
    destination_slug: str = "da-nang",
    days: int = 2,
    budget: Optional[int] = 2000000,
    allow_revisit_place_ids: bool = False,
) -> BenchmarkScenarioInput:
    import datetime

    dest_names = {"ha-noi": "Hà Nội", "da-nang": "Đà Nẵng", "ha-long": "Hạ Long"}
    start_dt = datetime.date(2026, 7, 1)
    end_dt = start_dt + datetime.timedelta(days=days - 1)
    return BenchmarkScenarioInput(
        scenario_id="SYNTHETIC_01B_TEST_SCENARIO",
        destination_slug=destination_slug,
        destination=dest_names[destination_slug],
        days=days,
        start_date=start_dt.isoformat(),
        end_date=end_dt.isoformat(),
        budget=budget,
        currency="VND",
        travel_style="comfort",
        interests=["beach_island", "food_cuisine", "culture_history"],
        notes="SYNTHETIC_TEST_ONLY fixture for W06-INSTRUMENT-01B",
        allow_revisit_place_ids=allow_revisit_place_ids,
        fixture_label="SYNTHETIC_TEST_ONLY",
    )


def _make_poi_item(
    order_index: int,
    start_time: str,
    end_time: str,
    place_id: str,
    place_name: str,
    estimated_cost: int = 100000,
) -> BenchmarkItineraryItem:
    return BenchmarkItineraryItem(
        order_index=order_index,
        start_time=start_time,
        end_time=end_time,
        activity_kind=ActivityKind.POI_VISIT,
        activity=f"Tham quan {place_name}",
        place_name=place_name,
        place_id=place_id,
        notes="Hoạt động kiểm thử",
        estimated_cost=estimated_cost,
        transport_mode="taxi",
    )


def _make_transit_item(
    order_index: int,
    start_time: str,
    end_time: str,
    place_name: Optional[str] = None,
    estimated_cost: int = 30000,
) -> BenchmarkItineraryItem:
    return BenchmarkItineraryItem(
        order_index=order_index,
        start_time=start_time,
        end_time=end_time,
        activity_kind=ActivityKind.TRANSIT_ONLY,
        activity="Di chuyển nội đô",
        place_name=place_name,
        place_id=None,
        notes="Di chuyển",
        estimated_cost=estimated_cost,
        transport_mode="taxi",
    )


def _make_plan_and_manifest(
    scenario: BenchmarkScenarioInput,
    days_list: List[BenchmarkItineraryDay],
    *,
    reported_total_cost: Optional[int] = None,
    run_status: BenchmarkRunStatus = BenchmarkRunStatus.VALID,
) -> tuple[BenchmarkPlanResponse, BenchmarkRunManifest]:
    actual_sum = sum(sum(i.estimated_cost for i in d.items) for d in days_list)
    effective_reported = reported_total_cost if reported_total_cost is not None else actual_sum
    is_over = False
    variance = 0
    if scenario.budget is not None and scenario.budget > 0:
        is_over = effective_reported > scenario.budget
        variance = scenario.budget - effective_reported

    plan = BenchmarkPlanResponse(
        plan_id="plan-01b-test-001",
        scenario_id=scenario.scenario_id,
        destination_slug=scenario.destination_slug,
        destination=scenario.destination,
        total_days=len(days_list),
        overview="Lịch trình kiểm thử 01B.",
        best_time_to_visit="Tháng 3 - Tháng 8",
        general_tips=["Chuẩn bị mũ nón"],
        budget_analysis=BenchmarkBudgetAnalysis(
            total_budget=scenario.budget,
            estimated_cost=effective_reported,
            currency=scenario.currency,
            is_over_budget=is_over,
            variance=variance,
        ),
        days=days_list,
    )
    scenario_sha = sha256_bytes(canonical_json_bytes(scenario.model_dump()))
    parsed_sha = sha256_bytes(canonical_json_bytes(plan.model_dump()))
    catalog_sha = compute_catalog_sha256()

    manifest = BenchmarkRunManifest(
        run_id="run-01b-test-001",
        scenario_id=scenario.scenario_id,
        execution_timestamp_utc="2026-10-15T00:00:00Z",
        provider="google-genai",
        model_id="gemini-3.5-flash",
        expected_model_id="gemini-3.5-flash",
        generation_parameters={"temperature": 0.7},
        execution_mode="LIVE_PROVIDER" if run_status == BenchmarkRunStatus.VALID else "NOT_EXECUTED_FAIL_CLOSED",
        latency_ms=450.0 if run_status == BenchmarkRunStatus.VALID else None,
        usage_metadata=BenchmarkUsageMetadata(input_tokens=1200, output_tokens=400, total_tokens=1600),
        code_commit_sha="770ead820e16716ce29a1a39d54a12b8a2246a3b",
        scenario_sha256=scenario_sha,
        catalog_sha256=catalog_sha,
        benchmark_prompt_version=BENCHMARK_PROMPT_VERSION,
        raw_response_sha256="a" * 64 if run_status == BenchmarkRunStatus.VALID else None,
        parsed_response_sha256=parsed_sha if run_status == BenchmarkRunStatus.VALID else None,
        run_status=run_status,
    )
    return plan, manifest


def _make_default_valid_days(dn_pois):
    d1_items = [
        _make_poi_item(1, "08:00", "09:30", dn_pois[0].place_id, dn_pois[0].name, 100000),
        _make_transit_item(2, "09:30", "10:00", None, 30000),
        _make_poi_item(3, "10:00", "11:30", dn_pois[1].place_id, dn_pois[1].name, 150000),
    ]
    d2_items = [
        _make_poi_item(1, "08:30", "10:30", dn_pois[2].place_id, dn_pois[2].name, 120000),
    ]
    return [
        BenchmarkItineraryDay(
            day_number=1,
            date="2026-07-01",
            title="Ngày 1",
            items=d1_items,
            day_cost=sum(i.estimated_cost for i in d1_items),
        ),
        BenchmarkItineraryDay(
            day_number=2,
            date="2026-07-02",
            title="Ngày 2",
            items=d2_items,
            day_cost=sum(i.estimated_cost for i in d2_items),
        ),
    ]


def test_w06_i01b_01_valid_canonical_place_id_grounds_successfully():
    """W06-I01B-01: valid canonical place_id grounds successfully."""
    dn_pois = build_destination_catalog_context("da-nang")
    scenario = _make_scenario(destination_slug="da-nang")
    plan, manifest = _make_plan_and_manifest(scenario, _make_default_valid_days(dn_pois))

    res = evaluate_benchmark_scenario(scenario, plan, manifest)
    assert res.poi_visit_item_count == 3
    assert res.grounded_item_count == 3
    assert res.ungrounded_item_count == 0
    assert res.grounded_poi_rate == 1.0
    assert res.all_pois_grounded is True
    assert res.core_scenario_pass_pre_opening_hours is True


def test_w06_i01b_02_unknown_place_id_fails_grounding():
    """W06-I01B-02: unknown place_id fails grounding."""
    dn_pois = build_destination_catalog_context("da-nang")
    scenario = _make_scenario(destination_slug="da-nang")
    days = _make_default_valid_days(dn_pois)
    days[1].items[0] = _make_poi_item(
        1, "08:30", "10:30", "non_existent_place_id_999", "Unknown Place", 120000
    )
    plan, manifest = _make_plan_and_manifest(scenario, days)

    res = evaluate_benchmark_scenario(scenario, plan, manifest)
    assert res.poi_visit_item_count == 3
    assert res.grounded_item_count == 2
    assert res.ungrounded_item_count == 1
    assert res.grounded_poi_rate == round(2 / 3, 6)
    assert res.all_pois_grounded is False
    assert res.core_scenario_pass_pre_opening_hours is False
    assert "UNGROUNDED_POI_VISIT_ITEMS" in res.failure_reasons


def test_w06_i01b_03_free_text_name_cannot_rescue_invalid_place_id():
    """W06-I01B-03: free-text name cannot rescue invalid place_id."""
    dn_pois = build_destination_catalog_context("da-nang")
    scenario = _make_scenario(destination_slug="da-nang")
    days = _make_default_valid_days(dn_pois)
    # Exact valid catalog name, but bogus place_id
    days[1].items[0] = _make_poi_item(
        1, "08:30", "10:30", "bogus_id_with_exact_real_name", dn_pois[2].name, 120000
    )
    plan, manifest = _make_plan_and_manifest(scenario, days)

    res = evaluate_benchmark_scenario(scenario, plan, manifest)
    assert res.ungrounded_item_count == 1
    assert res.all_pois_grounded is False
    assert res.core_scenario_pass_pre_opening_hours is False


def test_w06_i01b_04_zero_poi_visit_causes_grounding_and_scenario_fail():
    """W06-I01B-04: zero POI_VISIT => grounding/scenario fail."""
    scenario = _make_scenario(destination_slug="da-nang")
    days = [
        BenchmarkItineraryDay(
            day_number=1,
            date="2026-07-01",
            title="Ngày 1",
            items=[_make_transit_item(1, "08:00", "09:00", None, 30000)],
            day_cost=30000,
        ),
        BenchmarkItineraryDay(
            day_number=2,
            date="2026-07-02",
            title="Ngày 2",
            items=[_make_transit_item(1, "09:00", "10:00", None, 30000)],
            day_cost=30000,
        ),
    ]
    plan, manifest = _make_plan_and_manifest(scenario, days)

    res = evaluate_benchmark_scenario(scenario, plan, manifest)
    assert res.poi_visit_item_count == 0
    assert res.all_pois_grounded is False
    assert res.core_scenario_pass_pre_opening_hours is False
    assert "ZERO_POI_VISIT_ITEMS" in res.failure_reasons


def test_w06_i01b_05_destination_mismatch_detected():
    """W06-I01B-05: destination mismatch detected when a grounded POI belongs to another city."""
    dn_pois = build_destination_catalog_context("da-nang")
    hn_pois = build_destination_catalog_context("ha-noi")
    scenario = _make_scenario(destination_slug="da-nang")
    days = _make_default_valid_days(dn_pois)
    # Replace day 2 item with a valid grounded Hanoi POI in a Da Nang scenario
    days[1].items[0] = _make_poi_item(
        1, "08:30", "10:30", hn_pois[0].place_id, hn_pois[0].name, 120000
    )
    plan, manifest = _make_plan_and_manifest(scenario, days)

    res = evaluate_benchmark_scenario(scenario, plan, manifest)
    assert res.all_pois_grounded is True
    assert res.destination_correct_item_count == 2
    assert res.destination_incorrect_item_count == 1
    assert res.destination_correct_poi_rate == round(2 / 3, 6)
    assert res.scenario_destination_valid is False
    assert res.core_scenario_pass_pre_opening_hours is False
    assert "DESTINATION_MISMATCH" in res.failure_reasons


def test_w06_i01b_06_duplicate_place_id_detected_when_revisits_forbidden():
    """W06-I01B-06: duplicate place_id detected when revisits forbidden."""
    dn_pois = build_destination_catalog_context("da-nang")
    scenario = _make_scenario(destination_slug="da-nang", allow_revisit_place_ids=False)
    days = _make_default_valid_days(dn_pois)
    # Repeat dn_pois[0].place_id on Day 2
    days[1].items[0] = _make_poi_item(
        1, "08:30", "10:30", dn_pois[0].place_id, dn_pois[0].name, 120000
    )
    plan, manifest = _make_plan_and_manifest(scenario, days)

    res = evaluate_benchmark_scenario(scenario, plan, manifest)
    assert res.duplicate_poi_violation_count == 1
    assert res.duplicate_poi_pass is False
    assert res.core_scenario_pass_pre_opening_hours is False
    assert "DUPLICATE_POI_VIOLATION" in res.failure_reasons


def test_w06_i01b_07_duplicate_allowed_when_scenario_allows_revisits():
    """W06-I01B-07: duplicate allowed when scenario allows revisits."""
    dn_pois = build_destination_catalog_context("da-nang")
    scenario = _make_scenario(destination_slug="da-nang", allow_revisit_place_ids=True)
    days = _make_default_valid_days(dn_pois)
    days[1].items[0] = _make_poi_item(
        1, "08:30", "10:30", dn_pois[0].place_id, dn_pois[0].name, 120000
    )
    plan, manifest = _make_plan_and_manifest(scenario, days)

    res = evaluate_benchmark_scenario(scenario, plan, manifest)
    assert res.duplicate_poi_violation_count == 0
    assert res.duplicate_poi_pass is True
    assert res.core_scenario_pass_pre_opening_hours is True


def test_w06_i01b_08_transit_only_named_place_violation_detected():
    """W06-I01B-08: TRANSIT_ONLY named place violation detected."""
    dn_pois = build_destination_catalog_context("da-nang")
    scenario = _make_scenario(destination_slug="da-nang")
    days = _make_default_valid_days(dn_pois)
    # Give TRANSIT_ONLY item a non-null place_name to attempt grounding evasion
    days[0].items[1] = _make_transit_item(2, "09:30", "10:00", "Cầu Rồng Đà Nẵng", 30000)
    plan, manifest = _make_plan_and_manifest(scenario, days)

    res = evaluate_benchmark_scenario(scenario, plan, manifest)
    assert res.transit_only_named_poi_violation_count == 1
    assert res.transit_only_pass is False
    assert res.core_scenario_pass_pre_opening_hours is False
    assert "TRANSIT_ONLY_NAMED_POI_VIOLATION" in res.failure_reasons


def test_w06_i01b_09_valid_hhmm_parsed():
    """W06-I01B-09: valid HH:MM parsed."""
    assert parse_strict_hhmm("00:00") == 0
    assert parse_strict_hhmm("08:30") == 510
    assert parse_strict_hhmm("23:59") == 1439


def test_w06_i01b_10_invalid_hhmm_rejected():
    """W06-I01B-10: invalid HH:MM rejected."""
    for bad in ("8:00", "24:00", "12:60", "-01:00", "08:00:00", "08:00 AM", " 08:00", "invalid", ""):
        assert parse_strict_hhmm(bad) is None

    dn_pois = build_destination_catalog_context("da-nang")
    scenario = _make_scenario(destination_slug="da-nang")
    days = _make_default_valid_days(dn_pois)
    days[1].items[0] = _make_poi_item(
        1, "24:00", "25:00", dn_pois[2].place_id, dn_pois[2].name, 120000
    )
    plan, manifest = _make_plan_and_manifest(scenario, days)

    res = evaluate_benchmark_scenario(scenario, plan, manifest)
    assert res.time_parse_invalid_count == 1
    assert res.schedule_pass is False
    assert res.core_scenario_pass_pre_opening_hours is False
    assert "TIME_PARSE_INVALID" in res.failure_reasons


def test_w06_i01b_11_start_greater_or_equal_end_detected():
    """W06-I01B-11: start >= end detected as TIME_INTERVAL_INVALID."""
    dn_pois = build_destination_catalog_context("da-nang")
    scenario = _make_scenario(destination_slug="da-nang")
    days = _make_default_valid_days(dn_pois)
    days[1].items[0] = _make_poi_item(
        1, "11:00", "10:00", dn_pois[2].place_id, dn_pois[2].name, 120000
    )
    plan, manifest = _make_plan_and_manifest(scenario, days)

    res = evaluate_benchmark_scenario(scenario, plan, manifest)
    assert res.time_interval_invalid_count == 1
    assert res.schedule_pass is False
    assert res.core_scenario_pass_pre_opening_hours is False
    assert "TIME_INTERVAL_INVALID" in res.failure_reasons


def test_w06_i01b_12_back_to_back_intervals_are_non_overlapping():
    """W06-I01B-12: back-to-back intervals [09:00, 10:00) and [10:00, 11:00) are non-overlapping."""
    dn_pois = build_destination_catalog_context("da-nang")
    scenario = _make_scenario(destination_slug="da-nang", days=1)
    d1_items = [
        _make_poi_item(1, "09:00", "10:00", dn_pois[0].place_id, dn_pois[0].name, 100000),
        _make_poi_item(2, "10:00", "11:00", dn_pois[1].place_id, dn_pois[1].name, 100000),
    ]
    days = [
        BenchmarkItineraryDay(
            day_number=1, date="2026-07-01", title="Ngày 1", items=d1_items, day_cost=200000
        )
    ]
    plan, manifest = _make_plan_and_manifest(scenario, days)

    res = evaluate_benchmark_scenario(scenario, plan, manifest)
    assert res.schedule_overlap_count == 0
    assert res.schedule_pass is True
    assert res.core_scenario_pass_pre_opening_hours is True


def test_w06_i01b_13_true_overlapping_intervals_detected():
    """W06-I01B-13: true overlapping intervals within the same day detected."""
    dn_pois = build_destination_catalog_context("da-nang")
    scenario = _make_scenario(destination_slug="da-nang", days=1)
    d1_items = [
        _make_poi_item(1, "09:00", "10:30", dn_pois[0].place_id, dn_pois[0].name, 100000),
        _make_poi_item(2, "10:00", "11:30", dn_pois[1].place_id, dn_pois[1].name, 100000),
    ]
    days = [
        BenchmarkItineraryDay(
            day_number=1, date="2026-07-01", title="Ngày 1", items=d1_items, day_cost=200000
        )
    ]
    plan, manifest = _make_plan_and_manifest(scenario, days)

    res = evaluate_benchmark_scenario(scenario, plan, manifest)
    assert res.schedule_overlap_count == 1
    assert res.schedule_pass is False
    assert res.core_scenario_pass_pre_opening_hours is False
    assert "SCHEDULE_OVERLAP" in res.failure_reasons


def test_w06_i01b_14_schedule_checked_separately_per_day():
    """W06-I01B-14: identical time windows on different days do not overlap."""
    dn_pois = build_destination_catalog_context("da-nang")
    scenario = _make_scenario(destination_slug="da-nang", days=2)
    days = [
        BenchmarkItineraryDay(
            day_number=1,
            date="2026-07-01",
            title="Ngày 1",
            items=[_make_poi_item(1, "09:00", "11:00", dn_pois[0].place_id, dn_pois[0].name, 100000)],
            day_cost=100000,
        ),
        BenchmarkItineraryDay(
            day_number=2,
            date="2026-07-02",
            title="Ngày 2",
            items=[_make_poi_item(1, "09:00", "11:00", dn_pois[1].place_id, dn_pois[1].name, 100000)],
            day_cost=100000,
        ),
    ]
    plan, manifest = _make_plan_and_manifest(scenario, days)

    res = evaluate_benchmark_scenario(scenario, plan, manifest)
    assert res.schedule_overlap_count == 0
    assert res.schedule_pass is True
    assert res.core_scenario_pass_pre_opening_hours is True


def test_w06_i01b_15_estimated_budget_compliant_case():
    """W06-I01B-15: estimated budget compliant case."""
    dn_pois = build_destination_catalog_context("da-nang")
    scenario = _make_scenario(destination_slug="da-nang", budget=500000)
    plan, manifest = _make_plan_and_manifest(scenario, _make_default_valid_days(dn_pois))

    res = evaluate_benchmark_scenario(scenario, plan, manifest)
    assert res.estimated_total_cost == 400000
    assert res.budget_ceiling == 500000
    assert res.budget_status == "COMPLIANT"
    assert res.estimated_budget_compliant is True
    assert res.estimated_budget_violation_amount == 0
    assert res.core_scenario_pass_pre_opening_hours is True


def test_w06_i01b_16_estimated_budget_violation_case():
    """W06-I01B-16: estimated budget violation case."""
    dn_pois = build_destination_catalog_context("da-nang")
    scenario = _make_scenario(destination_slug="da-nang", budget=300000)
    plan, manifest = _make_plan_and_manifest(scenario, _make_default_valid_days(dn_pois))

    res = evaluate_benchmark_scenario(scenario, plan, manifest)
    assert res.estimated_total_cost == 400000
    assert res.budget_ceiling == 300000
    assert res.budget_status == "VIOLATION"
    assert res.estimated_budget_compliant is False
    assert res.estimated_budget_violation_amount == 100000
    assert res.core_scenario_pass_pre_opening_hours is False
    assert "ESTIMATED_BUDGET_VIOLATION" in res.failure_reasons


def test_w06_i01b_17_budget_null_is_not_applicable():
    """W06-I01B-17: budget null => NOT_APPLICABLE."""
    dn_pois = build_destination_catalog_context("da-nang")
    scenario = _make_scenario(destination_slug="da-nang", budget=None)
    plan, manifest = _make_plan_and_manifest(scenario, _make_default_valid_days(dn_pois))

    res = evaluate_benchmark_scenario(scenario, plan, manifest)
    assert res.budget_status == "NOT_APPLICABLE"
    assert res.budget_ceiling is None
    assert res.estimated_budget_compliant is None
    assert res.estimated_budget_violation_amount is None
    assert res.core_scenario_pass_pre_opening_hours is True


def test_w06_i01b_18_arithmetic_inconsistency_fails_core_pre_opening_hours_pass():
    """W06-I01B-18: arithmetic inconsistency fails core pre-opening-hours pass."""
    dn_pois = build_destination_catalog_context("da-nang")
    scenario = _make_scenario(destination_slug="da-nang", budget=500000)
    # Actual sum is 400000, but budget_analysis.estimated_cost reports 350000
    plan, manifest = _make_plan_and_manifest(
        scenario, _make_default_valid_days(dn_pois), reported_total_cost=350000
    )

    res = evaluate_benchmark_scenario(scenario, plan, manifest)
    assert res.arithmetic_self_consistency is False
    assert res.core_scenario_pass_pre_opening_hours is False
    assert "ARITHMETIC_SELF_CONSISTENCY_FAILURE" in res.failure_reasons


def test_w06_i01b_19_geo_distance_proxy_deterministic():
    """W06-I01B-19: GEO_DISTANCE_PROXY deterministic and skips TRANSIT_ONLY items."""
    dn_pois = build_destination_catalog_context("da-nang")
    scenario = _make_scenario(destination_slug="da-nang")
    plan, manifest = _make_plan_and_manifest(scenario, _make_default_valid_days(dn_pois))

    res1 = evaluate_benchmark_scenario(scenario, plan, manifest)
    res2 = evaluate_benchmark_scenario(scenario, plan, manifest)

    # 3 grounded POI_VISIT items => 2 consecutive legs (TRANSIT_ONLY item skipped)
    assert res1.geo_leg_count == 2
    leg1 = compute_haversine_geo_distance_proxy_km(
        dn_pois[0].lat, dn_pois[0].lng, dn_pois[1].lat, dn_pois[1].lng
    )
    leg2 = compute_haversine_geo_distance_proxy_km(
        dn_pois[1].lat, dn_pois[1].lng, dn_pois[2].lat, dn_pois[2].lng
    )
    assert res1.total_geo_distance_proxy_km == round(leg1 + leg2, 6) == res2.total_geo_distance_proxy_km
    assert res1.mean_leg_geo_distance_proxy_km == round((leg1 + leg2) / 2.0, 6)
    assert res1.max_leg_geo_distance_proxy_km == round(max(leg1, leg2), 6)


def test_w06_i01b_20_geo_proxy_excluded_from_core_pass():
    """W06-I01B-20: GEO_DISTANCE_PROXY is diagnostic only and never causes core pass failure."""
    dn_pois = build_destination_catalog_context("da-nang")
    # Pick farthest apart POIs in Da Nang and alternate back and forth
    scenario = _make_scenario(destination_slug="da-nang")
    d1_items = [
        _make_poi_item(1, "08:00", "09:30", dn_pois[0].place_id, dn_pois[0].name, 50000),
        _make_poi_item(2, "10:00", "11:30", dn_pois[-1].place_id, dn_pois[-1].name, 50000),
    ]
    d2_items = [
        _make_poi_item(1, "08:00", "09:30", dn_pois[len(dn_pois) // 2].place_id, dn_pois[len(dn_pois) // 2].name, 50000),
    ]
    days = [
        BenchmarkItineraryDay(day_number=1, date="2026-07-01", title="Ngày 1", items=d1_items, day_cost=100000),
        BenchmarkItineraryDay(day_number=2, date="2026-07-02", title="Ngày 2", items=d2_items, day_cost=50000),
    ]
    plan, manifest = _make_plan_and_manifest(scenario, days)

    res = evaluate_benchmark_scenario(scenario, plan, manifest)
    assert res.geo_leg_count == 2
    assert res.core_scenario_pass_pre_opening_hours is True


def test_w06_i01b_21_opening_hours_remains_not_evaluated_in_01b():
    """W06-I01B-21: 01B receipt records NOT_EVALUATED_IN_01B; 01C evaluator upgrades status to EVALUATED."""
    receipt = json.loads(RECEIPT_01B_JSON_PATH.read_text(encoding="utf-8"))
    assert receipt["opening_hours_status"] == OPENING_HOURS_STATUS_01B == "NOT_EVALUATED_IN_01B"

    dn_pois = build_destination_catalog_context("da-nang")
    scenario = _make_scenario(destination_slug="da-nang")
    plan, manifest = _make_plan_and_manifest(scenario, _make_default_valid_days(dn_pois))

    res = evaluate_benchmark_scenario(scenario, plan, manifest)
    assert res.opening_hours_status == OPENING_HOURS_STATUS_01C == "EVALUATED"


def test_w06_i01b_22_invalid_run_status_fails_closed():
    """W06-I01B-22: invalid run status fails closed as INVALID_RUN."""
    dn_pois = build_destination_catalog_context("da-nang")
    scenario = _make_scenario(destination_slug="da-nang")
    for non_valid_status in (
        BenchmarkRunStatus.LIVE_PROVIDER_REQUIRED,
        BenchmarkRunStatus.MOCK_OR_FALLBACK_RUN,
        BenchmarkRunStatus.API_ERROR,
        BenchmarkRunStatus.UNPARSABLE_MODEL_OUTPUT,
        BenchmarkRunStatus.MODEL_ID_MISMATCH,
        BenchmarkRunStatus.SCHEMA_NONCOMPLIANT_OUTPUT,
        BenchmarkRunStatus.MISSING_REQUIRED_RUN_METADATA,
    ):
        plan, manifest = _make_plan_and_manifest(
            scenario, _make_default_valid_days(dn_pois), run_status=non_valid_status
        )
        res = evaluate_benchmark_scenario(scenario, None, manifest, verify_hashes=False)
        assert res.evaluation_status == "INVALID_RUN"
        assert res.run_valid is False
        assert res.run_status == non_valid_status.value
        assert res.core_scenario_pass_pre_opening_hours is False
        assert res.core_scenario_pass is False
        assert "INVALID_RUN" in res.failure_reasons


def test_w06_i01b_23_scenario_hash_mismatch_causes_evidence_integrity_failure():
    """W06-I01B-23: scenario hash mismatch => EVIDENCE_INTEGRITY_FAILURE."""
    dn_pois = build_destination_catalog_context("da-nang")
    scenario = _make_scenario(destination_slug="da-nang")
    plan, manifest = _make_plan_and_manifest(scenario, _make_default_valid_days(dn_pois))
    manifest.scenario_sha256 = "0" * 64

    res = evaluate_benchmark_scenario(scenario, plan, manifest, verify_hashes=True)
    assert res.evaluation_status == "EVIDENCE_INTEGRITY_FAILURE"
    assert res.evidence_integrity_valid is False
    assert res.core_scenario_pass_pre_opening_hours is False
    assert res.core_scenario_pass is False
    assert "SCENARIO_SHA256_MISMATCH" in res.failure_reasons


def test_w06_i01b_24_parsed_response_hash_mismatch_causes_evidence_integrity_failure():
    """W06-I01B-24: parsed response hash mismatch => EVIDENCE_INTEGRITY_FAILURE."""
    dn_pois = build_destination_catalog_context("da-nang")
    scenario = _make_scenario(destination_slug="da-nang")
    plan, manifest = _make_plan_and_manifest(scenario, _make_default_valid_days(dn_pois))
    manifest.parsed_response_sha256 = "f" * 64

    res = evaluate_benchmark_scenario(scenario, plan, manifest, verify_hashes=True)
    assert res.evaluation_status == "EVIDENCE_INTEGRITY_FAILURE"
    assert res.evidence_integrity_valid is False
    assert res.core_scenario_pass_pre_opening_hours is False
    assert res.core_scenario_pass is False
    assert "PARSED_RESPONSE_SHA256_MISMATCH" in res.failure_reasons


def test_w06_i01b_25_catalog_hash_mismatch_causes_evidence_integrity_failure():
    """W06-I01B-25: catalog hash mismatch => EVIDENCE_INTEGRITY_FAILURE."""
    dn_pois = build_destination_catalog_context("da-nang")
    scenario = _make_scenario(destination_slug="da-nang")
    plan, manifest = _make_plan_and_manifest(scenario, _make_default_valid_days(dn_pois))
    manifest.catalog_sha256 = "c" * 64

    res = evaluate_benchmark_scenario(scenario, plan, manifest, verify_hashes=True)
    assert res.evaluation_status == "EVIDENCE_INTEGRITY_FAILURE"
    assert res.evidence_integrity_valid is False
    assert res.core_scenario_pass_pre_opening_hours is False
    assert res.core_scenario_pass is False
    assert "CATALOG_SHA256_MISMATCH" in res.failure_reasons


def test_w06_i01b_26_evaluation_output_deterministic_byte_identically(tmp_path: Path):
    """W06-I01B-26: evaluation output deterministic byte-identically."""
    dn_pois = build_destination_catalog_context("da-nang")
    scenario = _make_scenario(destination_slug="da-nang")
    plan, manifest = _make_plan_and_manifest(scenario, _make_default_valid_days(dn_pois))

    run_dir_1 = tmp_path / "run_1"
    run_dir_2 = tmp_path / "run_2"
    for rdir in (run_dir_1, run_dir_2):
        write_canonical_json(rdir / "scenario_input.json", scenario.model_dump())
        write_canonical_json(rdir / "parsed_plan_response.json", plan.model_dump())
        write_canonical_json(rdir / "run_manifest.json", manifest.model_dump())

    evaluate_run_directory(run_dir_1)
    evaluate_run_directory(run_dir_2)

    bytes_1 = (run_dir_1 / "scenario_evaluation.json").read_bytes()
    bytes_2 = (run_dir_2 / "scenario_evaluation.json").read_bytes()
    assert bytes_1 == bytes_2
    assert bytes_1.endswith(b"\n")
    assert not bytes_1.endswith(b"\n\n")


def test_w06_i01b_27_no_weighted_composite_score_exists():
    """W06-I01B-27: no weighted composite score exists."""
    dn_pois = build_destination_catalog_context("da-nang")
    scenario = _make_scenario(destination_slug="da-nang")
    plan, manifest = _make_plan_and_manifest(scenario, _make_default_valid_days(dn_pois))

    res_dict = evaluate_benchmark_scenario(scenario, plan, manifest).model_dump()
    forbidden_keys = {"composite_score", "weighted_score", "overall_score", "total_score"}
    assert forbidden_keys.isdisjoint(res_dict.keys())
    for k in res_dict:
        assert "composite" not in k.lower()
        assert "weighted" not in k.lower()


def test_w06_i01b_28_no_final_core_scenario_pass_field_or_result_produced():
    """W06-I01B-28: 01B receipt preserves pre-opening-hours gate; 01C computes both pre and final core_scenario_pass."""
    receipt = json.loads(RECEIPT_01B_JSON_PATH.read_text(encoding="utf-8"))
    assert receipt["core_pass_field"] == "core_scenario_pass_pre_opening_hours"
    assert receipt["final_core_scenario_pass_status"] == FINAL_CORE_PASS_STATUS_01B

    dn_pois = build_destination_catalog_context("da-nang")
    scenario = _make_scenario(destination_slug="da-nang")
    plan, manifest = _make_plan_and_manifest(scenario, _make_default_valid_days(dn_pois))

    res = evaluate_benchmark_scenario(scenario, plan, manifest)
    res_dict = res.model_dump()
    assert "core_scenario_pass_pre_opening_hours" in res_dict
    assert "core_scenario_pass" in res_dict
    assert res.final_core_scenario_pass_status == FINAL_CORE_PASS_STATUS_01C


def test_w06_i01b_29_no_opening_hours_final_result_produced():
    """W06-I01B-29: 01B receipt preserves NOT_EVALUATED_IN_01B; 01C evaluates item states."""
    receipt = json.loads(RECEIPT_01B_JSON_PATH.read_text(encoding="utf-8"))
    assert receipt["opening_hours_status"] == "NOT_EVALUATED_IN_01B"

    dn_pois = build_destination_catalog_context("da-nang")
    scenario = _make_scenario(destination_slug="da-nang")
    plan, manifest = _make_plan_and_manifest(scenario, _make_default_valid_days(dn_pois))

    res = evaluate_benchmark_scenario(scenario, plan, manifest)
    assert res.opening_hours_status == "EVALUATED"
    assert res.opening_hours_evidence_status in {
        "FULLY_EVALUABLE",
        "PARTIALLY_EVALUABLE",
        "NO_EVALUABLE_EVIDENCE",
    }


def test_w06_i01b_30_no_final_100_scenario_benchmark_produced_and_cli_verified(tmp_path: Path):
    """W06-I01B-30: no final 100-scenario benchmark produced; receipt, P1..P12, and CLI verified."""
    assert RECEIPT_01B_JSON_PATH.exists()
    assert RECEIPT_01B_MD_PATH.exists()

    receipt = json.loads(RECEIPT_01B_JSON_PATH.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT_JSON_PATH.read_text(encoding="utf-8"))

    bounds = receipt["scientific_boundaries"]
    assert bounds["final_100_scenarios_generated"] is False
    assert bounds["final_benchmark_executed"] is False
    assert bounds["final_core_scenario_pass_computed"] is False
    assert bounds["opening_hours_final_evaluation_computed"] is False
    assert bounds["scientific_results_generated"] is False
    assert bounds["preregistration_created"] is False
    assert bounds["W5_modified"] is False
    assert bounds["measurement_contract_semantics_modified"] is False

    assert receipt["evaluator_version"] == EVALUATOR_VERSION_01B
    assert EVALUATOR_VERSION == "W06-CORE-EVALUATOR-01C-V1.0.0"
    assert receipt["minimum_items_per_day_contract_status"] == MINIMUM_ITEMS_PER_DAY_CONTRACT_STATUS

    contract_prereqs = {
        item["id"]: item["requirement"]
        for item in contract["required_instrumentation_prerequisites"]
    }
    matrix = receipt["prerequisite_implementation_matrix"]
    assert list(matrix.keys()) == [f"P{i}" for i in range(1, 13)]
    for pid, req in contract_prereqs.items():
        assert matrix[pid]["contract_requirement"] == req

    assert matrix["P7"]["status"] == "NOT_IMPLEMENTED"
    assert matrix["P11"]["status"] == "NOT_IMPLEMENTED"
    for pid in ("P1", "P2", "P3", "P4", "P5", "P6", "P9", "P12"):
        assert matrix[pid]["status"] == "IMPLEMENTED"

    scenario_files = sorted(p.name for p in PLANNER_EVAL_DIR.glob("*.json"))
    assert scenario_files == ["da_nang_4d.json", "ha_giang_3d.json", "moc_chau_3d.json"]

    # Verify CLI end-to-end on a valid run directory and a tampered run directory
    dn_pois = build_destination_catalog_context("da-nang")
    scenario = _make_scenario(destination_slug="da-nang")
    plan, manifest = _make_plan_and_manifest(scenario, _make_default_valid_days(dn_pois))

    valid_run_dir = tmp_path / "cli_valid_run"
    write_canonical_json(valid_run_dir / "scenario_input.json", scenario.model_dump())
    write_canonical_json(valid_run_dir / "parsed_plan_response.json", plan.model_dump())
    write_canonical_json(valid_run_dir / "run_manifest.json", manifest.model_dump())

    rc_ok = evaluator_cli_main(["--run-dir", str(valid_run_dir)])
    assert rc_ok == 0
    eval_json = json.loads((valid_run_dir / "scenario_evaluation.json").read_text(encoding="utf-8"))
    assert eval_json["core_scenario_pass_pre_opening_hours"] is True

    # Tamper with scenario_input.json and verify CLI returns exit code 1 with EVIDENCE_INTEGRITY_FAILURE
    (valid_run_dir / "scenario_input.json").write_bytes(
        (valid_run_dir / "scenario_input.json").read_bytes() + b"\n"
    )
    rc_bad = evaluator_cli_main(["--run-dir", str(valid_run_dir)])
    assert rc_bad == 1
    eval_json_bad = json.loads((valid_run_dir / "scenario_evaluation.json").read_text(encoding="utf-8"))
    assert eval_json_bad["evaluation_status"] == "EVIDENCE_INTEGRITY_FAILURE"
    assert eval_json_bad["core_scenario_pass_pre_opening_hours"] is False

    # Confirm catalog count loaded by evaluator is 622
    core_map = load_core_catalog_by_place_id()
    assert len(core_map) == 622
