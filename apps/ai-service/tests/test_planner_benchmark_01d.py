"""Targeted unit test suite for W06-INSTRUMENT-01D (01D-01 through 01D-27).

Verifies alignment of the W06 benchmark prompt (TRAVEL_PLANNER_BENCHMARK_V2) and
deterministic core evaluator (W06-CORE-EVALUATOR-01D-V1.0.0) with the frozen
W06-SCENARIO-METHOD-LOCK-01 rule min_poi_visits_per_day = 2.
"""
import datetime
import json
from pathlib import Path
import sys
from typing import List, Optional

REPO_ROOT = Path(__file__).resolve().parents[3]
AI_SERVICE_ROOT = REPO_ROOT / "apps" / "ai-service"
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.evaluation.planner_benchmark_evaluator import (  # noqa: E402
    EVALUATOR_VERSION,
    EVALUATOR_VERSION_01B,
    EVALUATOR_VERSION_01C,
    EVALUATOR_VERSION_01D,
    MIN_POI_VISITS_PER_DAY,
    MINIMUM_POI_VISITS_PER_DAY_METHOD_STATUS,
    MINIMUM_POI_VISITS_PER_DAY_RULE_SOURCE,
    evaluate_benchmark_scenario,
    evaluate_run_directory,
)
from app.prompts.planner_benchmark_prompt import (  # noqa: E402
    BENCHMARK_PROMPT_VERSION,
    BENCHMARK_PROMPT_VERSION_01A,
    TRAVEL_PLANNER_BENCHMARK_V1,
    TRAVEL_PLANNER_BENCHMARK_V2,
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

_HN_POIS = build_destination_catalog_context("ha-noi")
_DN_POIS = build_destination_catalog_context("da-nang")

HN_POI_1 = _HN_POIS[0].place_id
HN_POI_2 = _HN_POIS[1].place_id
HN_POI_3 = _HN_POIS[2].place_id
HN_POI_4 = _HN_POIS[3].place_id

DN_POI_1 = _DN_POIS[0].place_id
DN_POI_2 = _DN_POIS[1].place_id

# Pick one Ha Noi POI with null opening_hours (UNKNOWN) and one with "24/7" (COMPLIANT)
HN_POI_UNKNOWN_OH = next(p for p in _HN_POIS if p.opening_hours is None).place_id
HN_POI_24_7_OH = next(p for p in _HN_POIS if p.opening_hours == "24/7").place_id


def _make_scenario(
    *,
    destination_slug: str = "ha-noi",
    days: int = 1,
    budget: Optional[int] = 500000,
    allow_revisit_place_ids: bool = False,
) -> BenchmarkScenarioInput:
    dest_names = {"ha-noi": "Hà Nội", "da-nang": "Đà Nẵng", "ha-long": "Hạ Long"}
    start_dt = datetime.date(2026, 11, 2)
    end_dt = start_dt + datetime.timedelta(days=days - 1)
    return BenchmarkScenarioInput(
        scenario_id="SYNTHETIC_01D_TEST_SCENARIO",
        destination_slug=destination_slug,
        destination=dest_names[destination_slug],
        days=days,
        start_date=start_dt.isoformat(),
        end_date=end_dt.isoformat(),
        budget=budget,
        currency="VND",
        travel_style="comfort",
        interests=["culture_history", "food_cuisine"],
        notes="SYNTHETIC_TEST_ONLY fixture for W06-INSTRUMENT-01D",
        allow_revisit_place_ids=allow_revisit_place_ids,
        fixture_label="SYNTHETIC_TEST_ONLY",
    )


def _make_poi_item(
    order_index: int,
    start_time: str,
    end_time: str,
    place_id: str,
    place_name: str = "Địa điểm",
    estimated_cost: int = 50000,
) -> BenchmarkItineraryItem:
    return BenchmarkItineraryItem(
        order_index=order_index,
        start_time=start_time,
        end_time=end_time,
        activity_kind=ActivityKind.POI_VISIT,
        activity=f"Tham quan {place_name}",
        place_name=place_name,
        place_id=place_id,
        notes="Hoạt động kiểm thử 01D",
        estimated_cost=estimated_cost,
        transport_mode="taxi",
    )


def _make_transit_item(
    order_index: int,
    start_time: str,
    end_time: str,
    place_name: Optional[str] = None,
    estimated_cost: int = 20000,
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


def _make_day(
    day_number: int,
    date_str: str,
    items: List[BenchmarkItineraryItem],
) -> BenchmarkItineraryDay:
    return BenchmarkItineraryDay(
        day_number=day_number,
        date=date_str,
        title=f"Ngày {day_number}",
        items=items,
        day_cost=sum(i.estimated_cost for i in items),
    )


def _make_plan_and_manifest(
    scenario: BenchmarkScenarioInput,
    days_list: List[BenchmarkItineraryDay],
    *,
    run_status: BenchmarkRunStatus = BenchmarkRunStatus.VALID,
) -> tuple[BenchmarkPlanResponse, BenchmarkRunManifest]:
    actual_sum = sum(sum(i.estimated_cost for i in d.items) for d in days_list)
    is_over = False
    variance = 0
    if scenario.budget is not None and scenario.budget > 0:
        is_over = actual_sum > scenario.budget
        variance = scenario.budget - actual_sum

    plan = BenchmarkPlanResponse(
        plan_id="plan-01d-test-001",
        scenario_id=scenario.scenario_id,
        destination_slug=scenario.destination_slug,
        destination=scenario.destination,
        total_days=len(days_list),
        overview="Lịch trình kiểm thử 01D.",
        best_time_to_visit="Tháng 9 - Tháng 11",
        general_tips=["Chuẩn bị giày đi bộ"],
        budget_analysis=BenchmarkBudgetAnalysis(
            total_budget=scenario.budget,
            estimated_cost=actual_sum,
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
        run_id="run-01d-test-001",
        scenario_id=scenario.scenario_id,
        execution_timestamp_utc="2026-10-15T06:00:00Z",
        provider="google-genai",
        model_id="gemini-3.5-flash",
        expected_model_id="gemini-3.5-flash",
        generation_parameters={"temperature": 0.7},
        execution_mode="LIVE_PROVIDER" if run_status == BenchmarkRunStatus.VALID else "NOT_EXECUTED_FAIL_CLOSED",
        latency_ms=450.0 if run_status == BenchmarkRunStatus.VALID else None,
        usage_metadata=BenchmarkUsageMetadata(input_tokens=1200, output_tokens=400, total_tokens=1600),
        code_commit_sha="e5e1f450f68772b2fdc09e37eef58fd6bd5509ba",
        scenario_sha256=scenario_sha,
        catalog_sha256=catalog_sha,
        benchmark_prompt_version=BENCHMARK_PROMPT_VERSION,
        raw_response_sha256="a" * 64 if run_status == BenchmarkRunStatus.VALID else None,
        parsed_response_sha256=parsed_sha if run_status == BenchmarkRunStatus.VALID else None,
        run_status=run_status,
    )
    return plan, manifest


# ---------------------------------------------------------------------------
# 01D-01 .. 01D-04: Prompt Version & Minimum POI Rules
# ---------------------------------------------------------------------------


def test_w06_i01d_01_prompt_active_version_is_v2():
    """01D-01: prompt active version is TRAVEL_PLANNER_BENCHMARK_V2 (with V1 preserved)."""
    assert BENCHMARK_PROMPT_VERSION == "TRAVEL_PLANNER_BENCHMARK_V2"
    assert BENCHMARK_PROMPT_VERSION_01A == "TRAVEL_PLANNER_BENCHMARK_V1"
    assert isinstance(TRAVEL_PLANNER_BENCHMARK_V1, str) and TRAVEL_PLANNER_BENCHMARK_V1.strip()
    assert isinstance(TRAVEL_PLANNER_BENCHMARK_V2, str) and TRAVEL_PLANNER_BENCHMARK_V2.strip()
    assert TRAVEL_PLANNER_BENCHMARK_V2 != TRAVEL_PLANNER_BENCHMARK_V1


def test_w06_i01d_02_prompt_explicitly_requires_at_least_two_poi_visits_per_day():
    """01D-02: prompt explicitly requires >=2 POI_VISIT/day."""
    assert "min_poi_visits_per_day = 2" in TRAVEL_PLANNER_BENCHMARK_V2
    assert 'Mỗi ngày trong lịch trình BẮT BUỘC có ít nhất 2 hoạt động có "activity_kind": "POI_VISIT"' in TRAVEL_PLANNER_BENCHMARK_V2
    assert 'Quy tắc tối thiểu 2 "POI_VISIT"/ngày này áp dụng ĐỘC LẬP cho TỪNG ngày trong lịch trình' in TRAVEL_PLANNER_BENCHMARK_V2


def test_w06_i01d_03_prompt_explicitly_states_transit_only_does_not_count():
    """01D-03: prompt explicitly says TRANSIT_ONLY does not count toward minimum POI visits."""
    assert (
        'CHỈ các hoạt động có "activity_kind" == "POI_VISIT" mới được tính vào số lượng tối thiểu 2 địa điểm/ngày này; "TRANSIT_ONLY" KHÔNG được tính vào số lượng tối thiểu này.'
        in TRAVEL_PLANNER_BENCHMARK_V2
    )
    assert (
        'Một ngày chỉ có 1 "POI_VISIT" kèm theo bất kỳ số lượng "TRANSIT_ONLY" nào đều bị tính là VI PHẠM cấu trúc ngày'
        in TRAVEL_PLANNER_BENCHMARK_V2
    )


def test_w06_i01d_04_prompt_example_contains_at_least_two_poi_visits_for_demonstrated_day():
    """01D-04: prompt example itself contains >=2 POI_VISIT for the demonstrated day."""
    section_e = TRAVEL_PLANNER_BENCHMARK_V2.split("E. ĐỊNH DẠNG ĐẦU RA (JSON ONLY)")[1]
    section_e_json_part = section_e.split("DANH MỤC ĐỊA ĐIỂM ĐƯỢC PHÉP")[0]
    start_idx = section_e_json_part.index("{{")
    end_idx = section_e_json_part.rindex("}}") + 2
    example_json_str = (
        section_e_json_part[start_idx:end_idx]
        .replace("{destination}", "Hà Nội")
        .replace("{days}", "1")
        .replace("{start_date}", "2026-11-02")
        .replace("{{", "{")
        .replace("}}", "}")
    )
    parsed_example = json.loads(example_json_str)
    assert len(parsed_example["days"]) >= 1
    day1_items = parsed_example["days"][0]["items"]
    poi_visits = [item for item in day1_items if item["activity_kind"] == "POI_VISIT"]
    transit_items = [item for item in day1_items if item["activity_kind"] == "TRANSIT_ONLY"]
    assert len(poi_visits) >= 2
    assert len(transit_items) >= 1
    assert [item["order_index"] for item in day1_items] == list(range(1, len(day1_items) + 1))


# ---------------------------------------------------------------------------
# 01D-05 .. 01D-12: Day POI Count & Multi-Day Evaluation
# ---------------------------------------------------------------------------


def test_w06_i01d_05_zero_poi_visit_plus_transit_only_day_fails_minimum():
    """01D-05: 0 POI_VISIT + transit-only day -> minimum pass false."""
    scenario = _make_scenario(days=1)
    days = [
        _make_day(
            1,
            "2026-11-02",
            [
                _make_transit_item(1, "08:00", "09:00"),
                _make_transit_item(2, "09:30", "10:30"),
            ],
        )
    ]
    plan, manifest = _make_plan_and_manifest(scenario, days)
    result = evaluate_benchmark_scenario(scenario, plan, manifest)

    assert result.minimum_poi_visits_per_day_required == 2
    assert result.poi_visit_count_by_day == [0]
    assert result.min_poi_visits_observed_per_day == 0
    assert result.minimum_poi_visits_per_day_pass is False
    assert result.day_structure_pass is False
    assert "MINIMUM_POI_VISITS_PER_DAY_VIOLATION" in result.failure_reasons


def test_w06_i01d_06_one_poi_visit_only_fails_minimum():
    """01D-06: 1 POI_VISIT only -> minimum pass false."""
    scenario = _make_scenario(days=1)
    days = [
        _make_day(
            1,
            "2026-11-02",
            [
                _make_poi_item(1, "09:00", "11:00", HN_POI_1, "Địa điểm 1"),
            ],
        )
    ]
    plan, manifest = _make_plan_and_manifest(scenario, days)
    result = evaluate_benchmark_scenario(scenario, plan, manifest)

    assert result.poi_visit_count_by_day == [1]
    assert result.min_poi_visits_observed_per_day == 1
    assert result.minimum_poi_visits_per_day_pass is False
    assert result.day_structure_pass is False
    assert "MINIMUM_POI_VISITS_PER_DAY_VIOLATION" in result.failure_reasons


def test_w06_i01d_07_one_poi_visit_plus_many_transit_only_fails_minimum():
    """01D-07: 1 POI_VISIT + many TRANSIT_ONLY -> minimum pass false."""
    scenario = _make_scenario(days=1)
    days = [
        _make_day(
            1,
            "2026-11-02",
            [
                _make_transit_item(1, "08:00", "08:30"),
                _make_poi_item(2, "09:00", "10:30", HN_POI_1, "Địa điểm 1"),
                _make_transit_item(3, "10:30", "11:00"),
                _make_transit_item(4, "14:00", "14:30"),
            ],
        )
    ]
    plan, manifest = _make_plan_and_manifest(scenario, days)
    result = evaluate_benchmark_scenario(scenario, plan, manifest)

    assert result.min_items_observed_per_day == 4
    assert result.poi_visit_count_by_day == [1]
    assert result.min_poi_visits_observed_per_day == 1
    assert result.minimum_poi_visits_per_day_pass is False
    assert result.day_structure_pass is False
    assert "MINIMUM_POI_VISITS_PER_DAY_VIOLATION" in result.failure_reasons


def test_w06_i01d_08_two_poi_visits_passes_minimum():
    """01D-08: 2 POI_VISIT -> minimum pass true."""
    scenario = _make_scenario(days=1)
    days = [
        _make_day(
            1,
            "2026-11-02",
            [
                _make_poi_item(1, "09:00", "10:30", HN_POI_1, "Địa điểm 1"),
                _make_poi_item(2, "11:00", "12:30", HN_POI_2, "Địa điểm 2"),
            ],
        )
    ]
    plan, manifest = _make_plan_and_manifest(scenario, days)
    result = evaluate_benchmark_scenario(scenario, plan, manifest)

    assert result.poi_visit_count_by_day == [2]
    assert result.min_poi_visits_observed_per_day == 2
    assert result.minimum_poi_visits_per_day_pass is True
    assert result.day_structure_pass is True
    assert result.core_scenario_pass is True


def test_w06_i01d_09_two_poi_visits_plus_transit_only_passes_minimum():
    """01D-09: 2 POI_VISIT + TRANSIT_ONLY -> minimum pass true."""
    scenario = _make_scenario(days=1)
    days = [
        _make_day(
            1,
            "2026-11-02",
            [
                _make_poi_item(1, "09:00", "10:30", HN_POI_1, "Địa điểm 1"),
                _make_transit_item(2, "10:30", "11:00"),
                _make_poi_item(3, "11:00", "12:30", HN_POI_2, "Địa điểm 2"),
            ],
        )
    ]
    plan, manifest = _make_plan_and_manifest(scenario, days)
    result = evaluate_benchmark_scenario(scenario, plan, manifest)

    assert result.poi_visit_count_by_day == [2]
    assert result.min_poi_visits_observed_per_day == 2
    assert result.minimum_poi_visits_per_day_pass is True
    assert result.day_structure_pass is True
    assert result.core_scenario_pass is True


def test_w06_i01d_10_three_or_more_poi_visits_passes_minimum():
    """01D-10: 3+ POI_VISIT -> minimum pass true."""
    scenario = _make_scenario(days=1)
    days = [
        _make_day(
            1,
            "2026-11-02",
            [
                _make_poi_item(1, "08:30", "10:00", HN_POI_1, "Địa điểm 1"),
                _make_poi_item(2, "10:30", "12:00", HN_POI_2, "Địa điểm 2"),
                _make_poi_item(3, "14:00", "15:30", HN_POI_4, "Địa điểm 4"),
            ],
        )
    ]
    plan, manifest = _make_plan_and_manifest(scenario, days)
    result = evaluate_benchmark_scenario(scenario, plan, manifest)

    assert result.poi_visit_count_by_day == [3]
    assert result.min_poi_visits_observed_per_day == 3
    assert result.minimum_poi_visits_per_day_pass is True
    assert result.day_structure_pass is True


def test_w06_i01d_11_multiday_plan_with_one_day_below_two_poi_visits_fails():
    """01D-11: multi-day plan where one day has only 1 POI_VISIT -> whole minimum pass false and day_structure_pass false."""
    scenario = _make_scenario(days=2)
    days = [
        _make_day(
            1,
            "2026-11-02",
            [
                _make_poi_item(1, "08:30", "10:00", HN_POI_1, "Địa điểm 1"),
                _make_poi_item(2, "10:30", "12:00", HN_POI_2, "Địa điểm 2"),
                _make_poi_item(3, "14:00", "15:30", HN_POI_4, "Địa điểm 4"),
            ],
        ),
        _make_day(
            2,
            "2026-11-03",
            [
                _make_poi_item(1, "09:00", "11:00", HN_POI_3, "Địa điểm 3"),
                _make_transit_item(2, "11:00", "12:00"),
            ],
        ),
    ]
    plan, manifest = _make_plan_and_manifest(scenario, days)
    result = evaluate_benchmark_scenario(scenario, plan, manifest)

    assert result.day_count_pass is True
    assert result.poi_visit_count_by_day == [3, 1]
    assert result.min_poi_visits_observed_per_day == 1
    assert result.minimum_poi_visits_per_day_pass is False
    assert result.day_structure_pass is False
    assert "MINIMUM_POI_VISITS_PER_DAY_VIOLATION" in result.failure_reasons
    assert "DAY_STRUCTURE_VIOLATION" not in result.failure_reasons


def test_w06_i01d_12_multiday_plan_all_days_at_least_two_poi_visits_passes():
    """01D-12: all days >=2 POI_VISIT -> minimum pass true."""
    scenario = _make_scenario(days=2)
    days = [
        _make_day(
            1,
            "2026-11-02",
            [
                _make_poi_item(1, "09:00", "10:30", HN_POI_1, "Địa điểm 1"),
                _make_poi_item(2, "11:00", "12:30", HN_POI_2, "Địa điểm 2"),
            ],
        ),
        _make_day(
            2,
            "2026-11-03",
            [
                _make_poi_item(1, "09:00", "10:30", HN_POI_3, "Địa điểm 3"),
                _make_poi_item(2, "14:00", "15:30", HN_POI_4, "Địa điểm 4"),
            ],
        ),
    ]
    plan, manifest = _make_plan_and_manifest(scenario, days)
    result = evaluate_benchmark_scenario(scenario, plan, manifest)

    assert result.poi_visit_count_by_day == [2, 2]
    assert result.min_poi_visits_observed_per_day == 2
    assert result.minimum_poi_visits_per_day_pass is True
    assert result.day_structure_pass is True
    assert result.core_scenario_pass is True


# ---------------------------------------------------------------------------
# 01D-13 .. 01D-16: Orthogonality With Duplicate, Grounding, Destination, Transit
# ---------------------------------------------------------------------------


def test_w06_i01d_13_two_duplicated_poi_visits_satisfy_minimum_but_fail_duplicate_constraint():
    """01D-13: two duplicated POI visits satisfy minimum count but duplicate constraint fails separately."""
    scenario = _make_scenario(days=1, allow_revisit_place_ids=False)
    days = [
        _make_day(
            1,
            "2026-11-02",
            [
                _make_poi_item(1, "09:00", "10:30", HN_POI_1, "Địa điểm 1"),
                _make_poi_item(2, "14:00", "15:30", HN_POI_1, "Địa điểm 1"),
            ],
        )
    ]
    plan, manifest = _make_plan_and_manifest(scenario, days)
    result = evaluate_benchmark_scenario(scenario, plan, manifest)

    assert result.poi_visit_count_by_day == [2]
    assert result.minimum_poi_visits_per_day_pass is True
    assert result.day_structure_pass is True
    assert result.duplicate_poi_pass is False
    assert "DUPLICATE_POI_VIOLATION" in result.failure_reasons
    assert "MINIMUM_POI_VISITS_PER_DAY_VIOLATION" not in result.failure_reasons
    assert result.core_scenario_pass is False


def test_w06_i01d_14_two_ungrounded_poi_visits_satisfy_minimum_but_fail_grounding():
    """01D-14: two ungrounded/fake POI visits satisfy minimum count but grounding fails separately."""
    scenario = _make_scenario(days=1)
    days = [
        _make_day(
            1,
            "2026-11-02",
            [
                _make_poi_item(1, "09:00", "10:30", "fake_place_id_9991", "Fake POI 1"),
                _make_poi_item(2, "14:00", "15:30", "fake_place_id_9992", "Fake POI 2"),
            ],
        )
    ]
    plan, manifest = _make_plan_and_manifest(scenario, days)
    result = evaluate_benchmark_scenario(scenario, plan, manifest)

    assert result.poi_visit_count_by_day == [2]
    assert result.minimum_poi_visits_per_day_pass is True
    assert result.day_structure_pass is True
    assert result.all_pois_grounded is False
    assert "UNGROUNDED_POI_VISIT_ITEMS" in result.failure_reasons
    assert "MINIMUM_POI_VISITS_PER_DAY_VIOLATION" not in result.failure_reasons
    assert result.core_scenario_pass is False


def test_w06_i01d_15_two_wrong_destination_poi_visits_satisfy_minimum_but_fail_destination():
    """01D-15: two wrong-destination POI visits satisfy minimum count but destination constraint fails separately."""
    scenario = _make_scenario(destination_slug="ha-noi", days=1)
    days = [
        _make_day(
            1,
            "2026-11-02",
            [
                _make_poi_item(1, "09:00", "10:30", DN_POI_1, "Đà Nẵng POI 1"),
                _make_poi_item(2, "14:00", "15:30", DN_POI_2, "Đà Nẵng POI 2"),
            ],
        )
    ]
    plan, manifest = _make_plan_and_manifest(scenario, days)
    result = evaluate_benchmark_scenario(scenario, plan, manifest)

    assert result.poi_visit_count_by_day == [2]
    assert result.minimum_poi_visits_per_day_pass is True
    assert result.day_structure_pass is True
    assert result.all_pois_grounded is True
    assert result.scenario_destination_valid is False
    assert "DESTINATION_MISMATCH" in result.failure_reasons
    assert "MINIMUM_POI_VISITS_PER_DAY_VIOLATION" not in result.failure_reasons
    assert result.core_scenario_pass is False


def test_w06_i01d_16_transit_only_named_poi_violation_does_not_count_toward_minimum():
    """01D-16: TRANSIT_ONLY named-POI violation does not affect POI minimum count."""
    scenario = _make_scenario(days=1)
    days = [
        _make_day(
            1,
            "2026-11-02",
            [
                _make_poi_item(1, "09:00", "10:30", HN_POI_1, "Địa điểm 1"),
                _make_transit_item(2, "11:00", "12:00", place_name="Chùa Một Cột"),
            ],
        )
    ]
    plan, manifest = _make_plan_and_manifest(scenario, days)
    result = evaluate_benchmark_scenario(scenario, plan, manifest)

    assert result.poi_visit_count_by_day == [1]
    assert result.min_poi_visits_observed_per_day == 1
    assert result.minimum_poi_visits_per_day_pass is False
    assert result.transit_only_pass is False
    assert "TRANSIT_ONLY_NAMED_POI_VIOLATION" in result.failure_reasons
    assert "MINIMUM_POI_VISITS_PER_DAY_VIOLATION" in result.failure_reasons


# ---------------------------------------------------------------------------
# 01D-17 .. 01D-25: Non-Evaluated Defaults, Failure Reasons, & Pass Gates
# ---------------------------------------------------------------------------


def test_w06_i01d_17_invalid_run_defaults_to_zero_observed_and_pass_false():
    """01D-17: invalid run -> min observed 0, pass false."""
    scenario = _make_scenario(days=1)
    days = [
        _make_day(
            1,
            "2026-11-02",
            [
                _make_poi_item(1, "09:00", "10:30", HN_POI_1),
                _make_poi_item(2, "11:00", "12:30", HN_POI_2),
            ],
        )
    ]
    _, manifest = _make_plan_and_manifest(
        scenario, days, run_status=BenchmarkRunStatus.SCHEMA_NONCOMPLIANT_OUTPUT
    )
    result = evaluate_benchmark_scenario(scenario, None, manifest)

    assert result.evaluation_status == "INVALID_RUN"
    assert result.minimum_poi_visits_per_day_required == 2
    assert result.minimum_poi_visits_per_day_method_status == MINIMUM_POI_VISITS_PER_DAY_METHOD_STATUS
    assert result.minimum_poi_visits_per_day_rule_source == MINIMUM_POI_VISITS_PER_DAY_RULE_SOURCE
    assert result.poi_visit_count_by_day == []
    assert result.min_poi_visits_observed_per_day == 0
    assert result.minimum_poi_visits_per_day_pass is False
    assert result.day_structure_pass is False
    assert result.core_scenario_pass is False


def test_w06_i01d_18_evidence_integrity_failure_defaults_to_zero_observed_and_pass_false():
    """01D-18: evidence-integrity failure -> min observed 0, pass false."""
    scenario = _make_scenario(days=1)
    days = [
        _make_day(
            1,
            "2026-11-02",
            [
                _make_poi_item(1, "09:00", "10:30", HN_POI_1),
                _make_poi_item(2, "11:00", "12:30", HN_POI_2),
            ],
        )
    ]
    plan, manifest = _make_plan_and_manifest(scenario, days)
    manifest.parsed_response_sha256 = "f" * 64
    result = evaluate_benchmark_scenario(scenario, plan, manifest, verify_hashes=True)

    assert result.evaluation_status == "EVIDENCE_INTEGRITY_FAILURE"
    assert result.minimum_poi_visits_per_day_required == 2
    assert result.poi_visit_count_by_day == []
    assert result.min_poi_visits_observed_per_day == 0
    assert result.minimum_poi_visits_per_day_pass is False
    assert result.day_structure_pass is False
    assert result.core_scenario_pass is False


def test_w06_i01d_19_failure_reasons_distinguish_day_count_vs_minimum_poi_visits():
    """01D-19: failure reason MINIMUM_POI_VISITS_PER_DAY_VIOLATION emitted exactly when required."""
    scenario = _make_scenario(days=2)

    # Case A: day_count_pass is False, minimum_poi_visits_per_day_pass is True -> DAY_STRUCTURE_VIOLATION only
    days_case_a = [
        _make_day(
            1,
            "2026-11-02",
            [
                _make_poi_item(1, "09:00", "10:30", HN_POI_1),
                _make_poi_item(2, "11:00", "12:30", HN_POI_2),
            ],
        )
    ]
    plan_a, manifest_a = _make_plan_and_manifest(scenario, days_case_a)
    res_a = evaluate_benchmark_scenario(scenario, plan_a, manifest_a)
    assert res_a.day_count_pass is False
    assert res_a.minimum_poi_visits_per_day_pass is True
    assert "DAY_STRUCTURE_VIOLATION" in res_a.failure_reasons
    assert "MINIMUM_POI_VISITS_PER_DAY_VIOLATION" not in res_a.failure_reasons

    # Case B: day_count_pass is False AND minimum_poi_visits_per_day_pass is False -> both emitted
    days_case_b = [
        _make_day(
            1,
            "2026-11-02",
            [
                _make_poi_item(1, "09:00", "10:30", HN_POI_1),
            ],
        )
    ]
    plan_b, manifest_b = _make_plan_and_manifest(scenario, days_case_b)
    res_b = evaluate_benchmark_scenario(scenario, plan_b, manifest_b)
    assert res_b.day_count_pass is False
    assert res_b.minimum_poi_visits_per_day_pass is False
    assert "DAY_STRUCTURE_VIOLATION" in res_b.failure_reasons
    assert "MINIMUM_POI_VISITS_PER_DAY_VIOLATION" in res_b.failure_reasons


def test_w06_i01d_20_valid_two_poi_per_day_plan_has_no_minimum_poi_failure_reason(tmp_path: Path):
    """01D-20: valid >=2 POI/day plan has no minimum-POI failure reason (and persists via evaluate_run_directory)."""
    scenario = _make_scenario(days=1)
    days = [
        _make_day(
            1,
            "2026-11-02",
            [
                _make_poi_item(1, "09:00", "10:30", HN_POI_1),
                _make_poi_item(2, "11:00", "12:30", HN_POI_2),
            ],
        )
    ]
    plan, manifest = _make_plan_and_manifest(scenario, days)
    run_dir = tmp_path / "run_01d_20"
    write_canonical_json(run_dir / "scenario_input.json", scenario.model_dump())
    write_canonical_json(run_dir / "parsed_plan_response.json", plan.model_dump())
    write_canonical_json(run_dir / "run_manifest.json", manifest.model_dump())

    result = evaluate_run_directory(run_dir)
    assert "MINIMUM_POI_VISITS_PER_DAY_VIOLATION" not in result.failure_reasons
    assert "DAY_STRUCTURE_VIOLATION" not in result.failure_reasons
    assert result.failure_reasons == []


def test_w06_i01d_21_new_minimum_rule_affects_core_scenario_pass_pre_opening_hours():
    """01D-21: new minimum rule affects core_scenario_pass_pre_opening_hours."""
    scenario = _make_scenario(days=1)
    days = [
        _make_day(
            1,
            "2026-11-02",
            [
                _make_poi_item(1, "09:00", "10:30", HN_POI_1),
            ],
        )
    ]
    plan, manifest = _make_plan_and_manifest(scenario, days)
    result = evaluate_benchmark_scenario(scenario, plan, manifest)

    # Every other pre-opening-hours gate passes, only minimum_poi_visits_per_day_pass is False
    assert result.all_pois_grounded is True
    assert result.scenario_destination_valid is True
    assert result.duplicate_poi_pass is True
    assert result.transit_only_pass is True
    assert result.schedule_pass is True
    assert result.arithmetic_self_consistency is True
    assert result.estimated_budget_compliant is True
    assert result.day_count_pass is True
    assert result.minimum_poi_visits_per_day_pass is False
    assert result.day_structure_pass is False
    assert result.core_scenario_pass_pre_opening_hours is False


def test_w06_i01d_22_new_minimum_rule_affects_final_core_scenario_pass():
    """01D-22: new minimum rule affects final core_scenario_pass."""
    scenario = _make_scenario(days=1)
    days = [
        _make_day(
            1,
            "2026-11-02",
            [
                _make_poi_item(1, "09:00", "10:30", HN_POI_24_7_OH),
            ],
        )
    ]
    plan, manifest = _make_plan_and_manifest(scenario, days)
    result = evaluate_benchmark_scenario(scenario, plan, manifest)

    assert result.scenario_date_alignment_pass is True
    assert result.opening_hours_known_violation_count == 0
    assert result.minimum_poi_visits_per_day_pass is False
    assert result.core_scenario_pass_pre_opening_hours is False
    assert result.core_scenario_pass is False


def test_w06_i01d_23_opening_hours_unknown_behavior_unchanged():
    """01D-23: opening-hours UNKNOWN behavior unchanged when >=2 POI_VISIT items exist."""
    scenario = _make_scenario(days=1)
    days = [
        _make_day(
            1,
            "2026-11-02",
            [
                _make_poi_item(1, "09:00", "10:30", HN_POI_UNKNOWN_OH, "POI Unknown OH"),
                _make_poi_item(2, "11:00", "12:30", HN_POI_24_7_OH, "POI 24/7 OH"),
            ],
        )
    ]
    plan, manifest = _make_plan_and_manifest(scenario, days)
    result = evaluate_benchmark_scenario(scenario, plan, manifest)

    assert result.opening_hours_unknown_items == 1
    assert result.opening_hours_compliant_items == 1
    assert result.opening_hours_known_violation_count == 0
    assert result.core_scenario_pass is True


def test_w06_i01d_24_budget_behavior_unchanged():
    """01D-24: budget behavior unchanged under 01D."""
    scenario = _make_scenario(days=1, budget=500000)
    days = [
        _make_day(
            1,
            "2026-11-02",
            [
                _make_poi_item(1, "09:00", "10:30", HN_POI_1, estimated_cost=300000),
                _make_poi_item(2, "11:00", "12:30", HN_POI_2, estimated_cost=300000),
            ],
        )
    ]
    plan, manifest = _make_plan_and_manifest(scenario, days)
    result = evaluate_benchmark_scenario(scenario, plan, manifest)

    assert result.minimum_poi_visits_per_day_pass is True
    assert result.budget_status == "VIOLATION"
    assert result.estimated_budget_compliant is False
    assert "ESTIMATED_BUDGET_VIOLATION" in result.failure_reasons
    assert result.core_scenario_pass is False


def test_w06_i01d_25_schedule_behavior_unchanged():
    """01D-25: schedule behavior unchanged under 01D."""
    scenario = _make_scenario(days=1)
    days = [
        _make_day(
            1,
            "2026-11-02",
            [
                _make_poi_item(1, "09:00", "11:00", HN_POI_1),
                _make_poi_item(2, "10:30", "12:00", HN_POI_2),  # overlaps 10:30-11:00
            ],
        )
    ]
    plan, manifest = _make_plan_and_manifest(scenario, days)
    result = evaluate_benchmark_scenario(scenario, plan, manifest)

    assert result.minimum_poi_visits_per_day_pass is True
    assert result.schedule_pass is False
    assert result.schedule_overlap_count == 1
    assert "SCHEDULE_OVERLAP" in result.failure_reasons
    assert result.core_scenario_pass is False


# ---------------------------------------------------------------------------
# 01D-26 .. 01D-27: Schema Preservation Checks
# ---------------------------------------------------------------------------


def test_w06_i01d_26_schema_still_permits_one_poi_day_to_parse_for_scientific_evaluation():
    """01D-26: schema still permits a one-POI day to parse for scientific evaluation."""
    day = BenchmarkItineraryDay.model_validate(
        {
            "day_number": 1,
            "date": "2026-11-02",
            "title": "Ngày 1",
            "items": [
                _make_poi_item(1, "09:00", "10:30", HN_POI_1, "Địa điểm 1").model_dump(),
            ],
            "day_cost": 50000,
        }
    )
    assert len(day.items) == 1
    assert day.items[0].activity_kind == ActivityKind.POI_VISIT


def test_w06_i01d_27_benchmark_itinerary_day_items_min_length_not_changed_to_two():
    """01D-27: BenchmarkItineraryDay.items generic min_length was NOT changed to pretend to enforce two POI visits."""
    items_field = BenchmarkItineraryDay.model_fields["items"]
    min_len_metadata = [
        getattr(m, "min_length", None)
        for m in items_field.metadata
        if hasattr(m, "min_length")
    ]
    assert min_len_metadata == [1]
    assert MIN_POI_VISITS_PER_DAY == 2
    assert EVALUATOR_VERSION == "W06-CORE-EVALUATOR-01D-V1.0.0"
    assert EVALUATOR_VERSION_01D == "W06-CORE-EVALUATOR-01D-V1.0.0"
    assert EVALUATOR_VERSION_01C == "W06-CORE-EVALUATOR-01C-V1.0.0"
    assert EVALUATOR_VERSION_01B == "W06-CORE-EVALUATOR-01B-V1.0.0"
