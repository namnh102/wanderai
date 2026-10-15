"""Focused tests for W06-INSTRUMENT-01C (Opening-Hours Evaluation, Final Scenario Gate & Statistical Aggregation Engine).

Covers W06-I01C-01 through W06-I01C-40.
"""
import datetime
import json
from pathlib import Path
import sys
from typing import Dict, List, Optional, Tuple
import pytest

AI_SERVICE_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = AI_SERVICE_ROOT.parent.parent
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.evaluation.opening_hours_evaluator import (  # noqa: E402
    OPENING_HOURS_PARSER_VERSION,
    build_opening_hours_parser_coverage_report,
    evaluate_poi_visit_opening_hours,
    parse_osm_opening_hours,
)
from app.evaluation.planner_benchmark_aggregator import (  # noqa: E402
    AGGREGATOR_VERSION,
    BOOTSTRAP_ITERATIONS,
    BOOTSTRAP_SEED,
    AssignedScenarioSpec,
    BenchmarkAssignmentManifest,
    aggregate_benchmark_evaluations,
    aggregate_evaluations_from_disk,
    compute_scenario_cluster_bootstrap_grounding_ci95,
    compute_wilson_ci95,
)
from app.evaluation.planner_benchmark_evaluator import (  # noqa: E402
    EVALUATOR_VERSION,
    EVALUATOR_VERSION_01C,
    EVALUATOR_VERSION_01D,
    ScenarioEvaluationResult,
    evaluate_benchmark_scenario,
)
from app.prompts.planner_benchmark_prompt import (  # noqa: E402
    BENCHMARK_PROMPT_VERSION,
)
from app.schemas.planner_benchmark import (  # noqa: E402
    ActivityKind,
    BenchmarkBudgetAnalysis,
    BenchmarkCatalogPOI,
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
from scripts.aggregate_w06_planner_evaluations import main as aggregator_cli_main  # noqa: E402

COVERAGE_JSON_PATH = REPO_ROOT / "data" / "evaluation" / "w06" / "w06_opening_hours_parser_coverage_v1.json"
RECEIPT_01C_JSON_PATH = REPO_ROOT / "data" / "evaluation" / "w06" / "w06_instrument_01c_receipt_v1.json"
RECEIPT_01C_MD_PATH = REPO_ROOT / "docs" / "research" / "w06_instrument_01c_implementation_v1.md"
SEMANTICS_01C_MD_PATH = REPO_ROOT / "docs" / "research" / "w06_instrument_01c_metric_semantics_v1.md"
CONTRACT_JSON_PATH = REPO_ROOT / "data" / "evaluation" / "w06" / "w06_measurement_contract_v1.json"
PLANNER_EVAL_DIR = REPO_ROOT / "data" / "evaluation" / "planner"


def _make_custom_catalog() -> Dict[str, BenchmarkCatalogPOI]:
    """Build a deterministic in-memory core catalog map with diverse opening_hours test cases."""
    cat: Dict[str, BenchmarkCatalogPOI] = {
        "poi_dn_247": BenchmarkCatalogPOI(
            place_id="poi_dn_247",
            name="Cầu Rồng 24/7",
            category="attraction",
            destination_slug="da-nang",
            lat=16.0611,
            lng=108.2275,
            opening_hours="24/7",
        ),
        "poi_dn_weekday": BenchmarkCatalogPOI(
            place_id="poi_dn_weekday",
            name="Bảo tàng Điêu khắc Chăm",
            category="culture",
            destination_slug="da-nang",
            lat=16.0605,
            lng=108.2234,
            opening_hours="Mo off; Tu-Su 08:00-12:00,13:30-17:00",
        ),
        "poi_dn_missing_oh": BenchmarkCatalogPOI(
            place_id="poi_dn_missing_oh",
            name="Bãi biển Mỹ Khê",
            category="beach",
            destination_slug="da-nang",
            lat=16.0598,
            lng=108.2465,
            opening_hours=None,
        ),
        "poi_dn_unsupported_oh": BenchmarkCatalogPOI(
            place_id="poi_dn_unsupported_oh",
            name="Chợ Đêm Đà Nẵng",
            category="nightlife",
            destination_slug="da-nang",
            lat=16.0615,
            lng=108.2290,
            opening_hours="Mo-Su 18:00-02:00",
        ),
        "poi_hn_247": BenchmarkCatalogPOI(
            place_id="poi_hn_247",
            name="Hồ Hoàn Kiếm",
            category="attraction",
            destination_slug="ha-noi",
            lat=21.0285,
            lng=105.8525,
            opening_hours="24/7",
        ),
        "poi_hl_247": BenchmarkCatalogPOI(
            place_id="poi_hl_247",
            name="Vịnh Hạ Long",
            category="nature",
            destination_slug="ha-long",
            lat=20.9101,
            lng=107.1839,
            opening_hours="24/7",
        ),
    }
    for dest in ("da-nang", "ha-noi", "ha-long"):
        for k in range(1, 12):
            pid = f"poi_{dest}_{k}"
            cat[pid] = BenchmarkCatalogPOI(
                place_id=pid,
                name=f"POI {dest} {k}",
                category="attraction",
                destination_slug=dest,
                lat=16.0 + 0.01 * k,
                lng=108.0 + 0.01 * k,
                opening_hours="24/7",
            )
    return cat


def _make_scenario(
    *,
    scenario_id: str = "SYNTHETIC_01C_SCENARIO",
    destination_slug: str = "da-nang",
    days: int = 1,
    start_date: str = "2026-07-07",  # 2026-07-07 is a Tuesday
    end_date: Optional[str] = None,
    budget: Optional[int] = 1000000,
) -> BenchmarkScenarioInput:
    dest_names = {"ha-noi": "Hà Nội", "da-nang": "Đà Nẵng", "ha-long": "Hạ Long"}
    if end_date is None:
        s_dt = datetime.date.fromisoformat(start_date)
        end_date = (s_dt + datetime.timedelta(days=days - 1)).isoformat()
    return BenchmarkScenarioInput(
        scenario_id=scenario_id,
        destination_slug=destination_slug,
        destination=dest_names[destination_slug],
        days=days,
        start_date=start_date,
        end_date=end_date,
        budget=budget,
        currency="VND",
        travel_style="comfort",
        interests=["culture_history", "food_cuisine"],
        notes="SYNTHETIC_TEST_ONLY fixture for W06-INSTRUMENT-01C",
        allow_revisit_place_ids=False,
        fixture_label="SYNTHETIC_TEST_ONLY",
    )


def _make_poi_item(
    order_index: int,
    start_time: str,
    end_time: str,
    place_id: str,
    place_name: str = "Test Place",
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
        notes="Hoạt động kiểm thử 01C",
        estimated_cost=estimated_cost,
        transport_mode="taxi",
    )


def _make_plan_and_manifest(
    scenario: BenchmarkScenarioInput,
    days_list: List[BenchmarkItineraryDay],
    *,
    run_status: BenchmarkRunStatus = BenchmarkRunStatus.VALID,
    reported_total_cost: Optional[int] = None,
) -> Tuple[BenchmarkPlanResponse, BenchmarkRunManifest]:
    actual_sum = sum(sum(i.estimated_cost for i in d.items) for d in days_list)
    eff_cost = reported_total_cost if reported_total_cost is not None else actual_sum
    plan = BenchmarkPlanResponse(
        plan_id=f"plan-{scenario.scenario_id}",
        scenario_id=scenario.scenario_id,
        destination_slug=scenario.destination_slug,
        destination=scenario.destination,
        total_days=len(days_list),
        overview="Lịch trình kiểm thử 01C.",
        best_time_to_visit="Quanh năm",
        general_tips=["Kiểm thử"],
        budget_analysis=BenchmarkBudgetAnalysis(
            total_budget=scenario.budget,
            estimated_cost=eff_cost,
            currency="VND",
            is_over_budget=bool(scenario.budget is not None and eff_cost > scenario.budget),
            variance=(scenario.budget - eff_cost) if scenario.budget is not None else 0,
        ),
        days=days_list,
    )
    scen_sha = sha256_bytes(canonical_json_bytes(scenario.model_dump()))
    parsed_sha = sha256_bytes(canonical_json_bytes(plan.model_dump()))
    cat_sha = compute_catalog_sha256()
    manifest = BenchmarkRunManifest(
        run_id=f"run-{scenario.scenario_id}",
        scenario_id=scenario.scenario_id,
        execution_timestamp_utc="2026-10-15T00:00:00Z",
        provider="google-genai",
        model_id="gemini-3.5-flash",
        expected_model_id="gemini-3.5-flash",
        generation_parameters={"temperature": 0.7},
        execution_mode="LIVE_PROVIDER" if run_status == BenchmarkRunStatus.VALID else "NOT_EXECUTED_FAIL_CLOSED",
        latency_ms=420.0 if run_status == BenchmarkRunStatus.VALID else None,
        usage_metadata=BenchmarkUsageMetadata(input_tokens=1000, output_tokens=300, total_tokens=1300),
        code_commit_sha="98d01c1e2a83b6fe96699b802d1e0ff80cdd3758",
        scenario_sha256=scen_sha,
        catalog_sha256=cat_sha,
        benchmark_prompt_version=BENCHMARK_PROMPT_VERSION,
        raw_response_sha256="a" * 64 if run_status == BenchmarkRunStatus.VALID else None,
        parsed_response_sha256=parsed_sha if run_status == BenchmarkRunStatus.VALID else None,
        run_status=run_status,
    )
    return plan, manifest


def test_w06_i01c_01_24_7_evaluates_visit_compliant():
    """W06-I01C-01: 24/7 evaluates visit COMPLIANT."""
    ev = evaluate_poi_visit_opening_hours(
        day_number=1,
        date_str="2026-07-06",  # Monday
        date_context_trusted=True,
        order_index=1,
        place_id="poi_dn_247",
        is_grounded=True,
        opening_hours_raw="24/7",
        start_time="21:00",
        end_time="23:30",
    )
    assert ev.opening_hours_state == "COMPLIANT"
    assert ev.reason_code == "WITHIN_OPENING_HOURS"


def test_w06_i01c_02_simple_weekday_time_visit_compliant():
    """W06-I01C-02: simple weekday/time visit COMPLIANT."""
    ev = evaluate_poi_visit_opening_hours(
        day_number=1,
        date_str="2026-07-07",  # Tuesday
        date_context_trusted=True,
        order_index=1,
        place_id="poi_dn_weekday",
        is_grounded=True,
        opening_hours_raw="Mo off; Tu-Su 08:00-12:00,13:30-17:00",
        start_time="08:30",
        end_time="11:30",
    )
    assert ev.opening_hours_state == "COMPLIANT"
    assert ev.reason_code == "WITHIN_OPENING_HOURS"


def test_w06_i01c_03_known_closed_time_visit_violation():
    """W06-I01C-03: known closed-time visit => VIOLATION."""
    # Monday is explicitly 'Mo off'
    ev_monday = evaluate_poi_visit_opening_hours(
        day_number=1,
        date_str="2026-07-06",  # Monday
        date_context_trusted=True,
        order_index=1,
        place_id="poi_dn_weekday",
        is_grounded=True,
        opening_hours_raw="Mo off; Tu-Su 08:00-12:00,13:30-17:00",
        start_time="09:00",
        end_time="10:30",
    )
    assert ev_monday.opening_hours_state == "VIOLATION"
    assert ev_monday.reason_code == "CLOSED_ON_WEEKDAY"

    # Tuesday lunch break 12:00-13:30 is closed
    ev_lunch = evaluate_poi_visit_opening_hours(
        day_number=1,
        date_str="2026-07-07",  # Tuesday
        date_context_trusted=True,
        order_index=1,
        place_id="poi_dn_weekday",
        is_grounded=True,
        opening_hours_raw="Mo off; Tu-Su 08:00-12:00,13:30-17:00",
        start_time="11:30",
        end_time="13:00",
    )
    assert ev_lunch.opening_hours_state == "VIOLATION"
    assert ev_lunch.reason_code == "OUTSIDE_OPENING_HOURS_WINDOW"


def test_w06_i01c_04_missing_opening_hours_unknown():
    """W06-I01C-04: missing opening_hours => UNKNOWN."""
    ev = evaluate_poi_visit_opening_hours(
        day_number=1,
        date_str="2026-07-07",
        date_context_trusted=True,
        order_index=1,
        place_id="poi_dn_missing_oh",
        is_grounded=True,
        opening_hours_raw=None,
        start_time="09:00",
        end_time="10:30",
    )
    assert ev.opening_hours_state == "UNKNOWN"
    assert ev.reason_code == "MISSING_OPENING_HOURS"


def test_w06_i01c_05_unsupported_syntax_unknown_never_violation():
    """W06-I01C-05: unsupported syntax => UNKNOWN, never VIOLATION or COMPLIANT."""
    for raw_unsupported, expected_reason in (
        ("Mo-Su 18:00-02:00", "UNSUPPORTED_CROSS_MIDNIGHT_SYNTAX"),
        ("Fr-Su 18:00-00:00", "UNSUPPORTED_CROSS_MIDNIGHT_SYNTAX"),
        ("Mo-Su 05:30+", "UNSUPPORTED_OPEN_ENDED_PLUS"),
        ("Tu-Th,Sa-Su,PH 08:00-11:30,13:00-16:30", "UNSUPPORTED_HOLIDAY_SELECTOR"),
        ("sunrise-sunset", "UNSUPPORTED_SOLAR_EVENT_SYNTAX"),
        ("Jan-Mar 08:00-17:00", "UNSUPPORTED_DATE_OR_MONTH_SELECTOR"),
    ):
        ev = evaluate_poi_visit_opening_hours(
            day_number=1,
            date_str="2026-07-07",
            date_context_trusted=True,
            order_index=1,
            place_id="poi_dn_unsupported_oh",
            is_grounded=True,
            opening_hours_raw=raw_unsupported,
            start_time="03:00",
            end_time="04:00",
        )
        assert ev.opening_hours_state == "UNKNOWN"
        assert ev.opening_hours_state not in {"COMPLIANT", "VIOLATION"}
        assert ev.reason_code == expected_reason


def test_w06_i01c_06_unknown_excluded_from_compliance_denominator():
    """W06-I01C-06: UNKNOWN excluded from compliance denominator."""
    cat = _make_custom_catalog()
    scenario = _make_scenario(start_date="2026-07-07", days=1)  # Tuesday
    days = [
        BenchmarkItineraryDay(
            day_number=1,
            date="2026-07-07",
            title="Ngày 1",
            items=[
                _make_poi_item(1, "09:00", "10:30", "poi_dn_weekday"),      # COMPLIANT
                _make_poi_item(2, "11:00", "12:00", "poi_dn_missing_oh"),   # UNKNOWN
                _make_poi_item(3, "19:00", "20:30", "poi_dn_unsupported_oh"),  # UNKNOWN
            ],
            day_cost=300000,
        )
    ]
    plan, manifest = _make_plan_and_manifest(scenario, days)
    res = evaluate_benchmark_scenario(scenario, plan, manifest, core_catalog_by_id=cat)

    assert res.opening_hours_poi_visit_items == 3
    assert res.opening_hours_evaluable_items == 1
    assert res.opening_hours_compliant_items == 1
    assert res.opening_hours_unknown_items == 2
    assert res.opening_hours_known_violation_count == 0
    assert res.opening_hours_evidence_coverage == round(1 / 3, 6)
    assert res.opening_hours_compliance_rate_on_evaluable_items == 1.0


def test_w06_i01c_07_known_violation_fails_final_core_scenario_pass():
    """W06-I01C-07: known VIOLATION fails final core_scenario_pass."""
    cat = _make_custom_catalog()
    # 2026-07-06 is Monday, when poi_dn_weekday is explicitly 'Mo off'
    scenario = _make_scenario(start_date="2026-07-06", days=1)
    days = [
        BenchmarkItineraryDay(
            day_number=1,
            date="2026-07-06",
            title="Ngày 1",
            items=[
                _make_poi_item(1, "09:00", "10:30", "poi_dn_weekday"),
                _make_poi_item(2, "11:00", "12:00", "poi_dn_247"),
            ],
            day_cost=200000,
        )
    ]
    plan, manifest = _make_plan_and_manifest(scenario, days)
    res = evaluate_benchmark_scenario(scenario, plan, manifest, core_catalog_by_id=cat)

    assert res.core_scenario_pass_pre_opening_hours is True
    assert res.opening_hours_known_violation_count == 1
    assert res.core_scenario_pass is False
    assert "OPENING_HOURS_KNOWN_VIOLATION" in res.failure_reasons


def test_w06_i01c_08_unknown_alone_does_not_fail_final_core_scenario_pass():
    """W06-I01C-08: UNKNOWN alone does not fail final core_scenario_pass."""
    cat = _make_custom_catalog()
    scenario = _make_scenario(start_date="2026-07-07", days=1)
    days = [
        BenchmarkItineraryDay(
            day_number=1,
            date="2026-07-07",
            title="Ngày 1",
            items=[
                _make_poi_item(1, "09:00", "10:30", "poi_dn_missing_oh"),
                _make_poi_item(2, "18:30", "20:00", "poi_dn_unsupported_oh"),
            ],
            day_cost=200000,
        )
    ]
    plan, manifest = _make_plan_and_manifest(scenario, days)
    res = evaluate_benchmark_scenario(scenario, plan, manifest, core_catalog_by_id=cat)

    assert res.opening_hours_unknown_items == 2
    assert res.opening_hours_evaluable_items == 0
    assert res.opening_hours_known_violation_count == 0
    assert res.core_scenario_pass_pre_opening_hours is True
    assert res.core_scenario_pass is True


def test_w06_i01c_09_no_evaluable_evidence_not_labeled_opening_hours_success():
    """W06-I01C-09: NO_EVALUABLE_EVIDENCE has null compliance rate and is not labeled opening-hours success."""
    cat = _make_custom_catalog()
    scenario = _make_scenario(start_date="2026-07-07", days=1)
    days = [
        BenchmarkItineraryDay(
            day_number=1,
            date="2026-07-07",
            title="Ngày 1",
            items=[_make_poi_item(1, "09:00", "10:30", "poi_dn_missing_oh")],
            day_cost=100000,
        )
    ]
    plan, manifest = _make_plan_and_manifest(scenario, days)
    res = evaluate_benchmark_scenario(scenario, plan, manifest, core_catalog_by_id=cat)

    assert res.opening_hours_evidence_status == "NO_EVALUABLE_EVIDENCE"
    assert res.opening_hours_evaluable_items == 0
    assert res.opening_hours_compliance_rate_on_evaluable_items is None


def test_w06_i01c_10_partially_evaluable_classification_correct():
    """W06-I01C-10: PARTIALLY_EVALUABLE classification correct when >=1 evaluable and >=1 UNKNOWN."""
    cat = _make_custom_catalog()
    scenario = _make_scenario(start_date="2026-07-07", days=1)
    days = [
        BenchmarkItineraryDay(
            day_number=1,
            date="2026-07-07",
            title="Ngày 1",
            items=[
                _make_poi_item(1, "09:00", "10:30", "poi_dn_247"),
                _make_poi_item(2, "11:00", "12:00", "poi_dn_missing_oh"),
            ],
            day_cost=200000,
        )
    ]
    plan, manifest = _make_plan_and_manifest(scenario, days)
    res = evaluate_benchmark_scenario(scenario, plan, manifest, core_catalog_by_id=cat)

    assert res.opening_hours_evidence_status == "PARTIALLY_EVALUABLE"
    assert res.opening_hours_evaluable_items == 1
    assert res.opening_hours_unknown_items == 1


def test_w06_i01c_11_fully_evaluable_classification_correct():
    """W06-I01C-11: FULLY_EVALUABLE classification correct when all POI_VISIT items are evaluable."""
    cat = _make_custom_catalog()
    scenario = _make_scenario(start_date="2026-07-07", days=1)
    days = [
        BenchmarkItineraryDay(
            day_number=1,
            date="2026-07-07",
            title="Ngày 1",
            items=[
                _make_poi_item(1, "09:00", "10:30", "poi_dn_weekday"),
                _make_poi_item(2, "14:00", "15:30", "poi_dn_247"),
            ],
            day_cost=200000,
        )
    ]
    plan, manifest = _make_plan_and_manifest(scenario, days)
    res = evaluate_benchmark_scenario(scenario, plan, manifest, core_catalog_by_id=cat)

    assert res.opening_hours_evidence_status == "FULLY_EVALUABLE"
    assert res.opening_hours_evaluable_items == 2
    assert res.opening_hours_unknown_items == 0
    assert res.opening_hours_evidence_coverage == 1.0


def test_w06_i01c_12_invalid_scenario_date_alignment_detected():
    """W06-I01C-12: invalid scenario date alignment detected."""
    cat = _make_custom_catalog()
    scenario = _make_scenario(start_date="2026-07-07", days=2)  # expects 2026-07-07 and 2026-07-08
    days = [
        BenchmarkItineraryDay(
            day_number=1,
            date="2026-07-07",
            title="Ngày 1",
            items=[_make_poi_item(1, "09:00", "10:30", "poi_dn_247")],
            day_cost=100000,
        ),
        BenchmarkItineraryDay(
            day_number=2,
            date="2026-07-09",  # Skips 2026-07-08
            title="Ngày 2",
            items=[_make_poi_item(1, "09:00", "10:30", "poi_dn_weekday")],
            day_cost=100000,
        ),
    ]
    plan, manifest = _make_plan_and_manifest(scenario, days)
    res = evaluate_benchmark_scenario(scenario, plan, manifest, core_catalog_by_id=cat)

    assert res.scenario_date_alignment_pass is False
    assert res.scenario_date_alignment_status == "SCENARIO_DATE_ALIGNMENT_FAILURE"
    assert "SCENARIO_DATE_ALIGNMENT_FAILURE" in res.failure_reasons
    assert res.core_scenario_pass is False


def test_w06_i01c_13_date_alignment_failure_cannot_evade_opening_hours_constraint():
    """W06-I01C-13: missing or falsified day date cannot turn a Monday opening-hours closure into a pass."""
    cat = _make_custom_catalog()
    # Scenario starts on Monday 2026-07-06 when poi_dn_weekday is closed ('Mo off')
    scenario = _make_scenario(start_date="2026-07-06", days=1)

    for fake_date in (None, "invalid-date", "2026-07-07"):  # Trying None, garbage, or Tuesday to evade Monday closure
        days = [
            BenchmarkItineraryDay(
                day_number=1,
                date=fake_date,
                title="Ngày 1",
                items=[_make_poi_item(1, "09:00", "10:30", "poi_dn_weekday")],
                day_cost=100000,
            )
        ]
        plan, manifest = _make_plan_and_manifest(scenario, days)
        res = evaluate_benchmark_scenario(scenario, plan, manifest, core_catalog_by_id=cat)

        assert res.scenario_date_alignment_pass is False
        assert res.opening_hours_item_evaluations[0].opening_hours_state == "UNKNOWN"
        assert res.opening_hours_item_evaluations[0].reason_code == "UNKNOWN_DATE_CONTEXT"
        assert res.core_scenario_pass is False
        assert "SCENARIO_DATE_ALIGNMENT_FAILURE" in res.failure_reasons


def _build_eval_for_batch(
    scenario_id: str,
    destination_slug: str,
    *,
    run_status: BenchmarkRunStatus = BenchmarkRunStatus.VALID,
    budget: Optional[int] = 500000,
    item_cost: int = 100000,
    schedule_overlap: bool = False,
    grounded_count: int = 2,
    ungrounded_count: int = 0,
    oh_violation: bool = False,
) -> Tuple[AssignedScenarioSpec, ScenarioEvaluationResult]:
    cat = _make_custom_catalog()
    default_pid = {
        "da-nang": "poi_dn_247",
        "ha-noi": "poi_hn_247",
        "ha-long": "poi_hl_247",
    }[destination_slug]

    # Monday 2026-07-06 triggers violation on poi_dn_weekday if oh_violation=True
    start_date = "2026-07-06" if oh_violation else "2026-07-07"
    scenario = _make_scenario(
        scenario_id=scenario_id,
        destination_slug=destination_slug,
        days=1,
        start_date=start_date,
        budget=budget,
    )

    items: List[BenchmarkItineraryItem] = []
    idx = 1
    for g in range(grounded_count):
        pid = (
            "poi_dn_weekday"
            if (oh_violation and g == 0 and destination_slug == "da-nang")
            else f"poi_{destination_slug}_{g + 1}"
        )
        s_t = "09:00" if (schedule_overlap and idx <= 2) else f"{7 + idx:02d}:00"
        e_t = "10:30" if (schedule_overlap and idx <= 2) else f"{7 + idx:02d}:45"
        items.append(_make_poi_item(idx, s_t, e_t, pid, f"Place {idx}", item_cost))
        idx += 1

    for u in range(ungrounded_count):
        items.append(
            _make_poi_item(
                idx,
                f"{18 + u:02d}:00",
                f"{18 + u:02d}:45",
                f"ungrounded_{u}",
                "Ungrounded",
                item_cost,
            )
        )
        idx += 1

    if not items:
        items.append(_make_poi_item(1, "09:00", "10:00", default_pid, "Default", item_cost))

    days = [
        BenchmarkItineraryDay(
            day_number=1,
            date=start_date,
            title="Ngày 1",
            items=items,
            day_cost=sum(i.estimated_cost for i in items),
        )
    ]
    plan, manifest = _make_plan_and_manifest(scenario, days, run_status=run_status)
    ev = evaluate_benchmark_scenario(
        scenario,
        plan if run_status == BenchmarkRunStatus.VALID else None,
        manifest,
        core_catalog_by_id=cat,
        verify_hashes=(run_status == BenchmarkRunStatus.VALID),
    )
    spec = AssignedScenarioSpec(
        scenario_id=scenario_id,
        destination_slug=destination_slug,
        scenario_sha256=ev.scenario_sha256,
    )
    return spec, ev


def test_w06_i01c_14_schedule_violation_rate_batch_denominator_uses_valid_evaluated_scenarios():
    """W06-I01C-14: schedule_violation_rate batch denominator uses VALID evaluated scenarios."""
    s1, e1 = _build_eval_for_batch("s1", "da-nang", schedule_overlap=True, grounded_count=2)
    s2, e2 = _build_eval_for_batch("s2", "ha-noi", schedule_overlap=False, grounded_count=4)
    s3, e3 = _build_eval_for_batch("s3", "ha-long", run_status=BenchmarkRunStatus.API_ERROR)

    manifest = BenchmarkAssignmentManifest(
        manifest_id="test-sched-denom",
        assigned_scenarios=[s1, s2, s3],
    )
    agg = aggregate_benchmark_evaluations(manifest, [e1, e2, e3])

    assert agg.schedule_evaluable_scenario_count == 2
    assert agg.schedule_violation_scenario_count == 1
    assert agg.schedule_violation_rate == 0.5


def test_w06_i01c_15_invalid_provider_run_not_classified_as_factual_schedule_violation():
    """W06-I01C-15: invalid provider run is not counted in schedule_violation_scenario_count."""
    s1, e1 = _build_eval_for_batch("s1", "da-nang", schedule_overlap=False)
    s2, e2 = _build_eval_for_batch("s2", "ha-noi", run_status=BenchmarkRunStatus.API_ERROR)

    manifest = BenchmarkAssignmentManifest(
        manifest_id="test-sched-invalid",
        assigned_scenarios=[s1, s2],
    )
    agg = aggregate_benchmark_evaluations(manifest, [e1, e2])

    assert agg.schedule_evaluable_scenario_count == 1
    assert agg.schedule_violation_scenario_count == 0
    assert agg.schedule_violation_rate == 0.0
    assert agg.core_scenario_pass_rate_all_assigned == 0.5
    assert agg.core_scenario_pass_rate_all_100 is None


def test_w06_i01c_16_estimated_budget_violation_rate_denominator_uses_only_budget_applicable_valid_scenarios():
    """W06-I01C-16: estimated_budget_violation_rate denominator uses only budget-applicable VALID scenarios."""
    # s1: budget 150k, actual 200k => VIOLATION
    s1, e1 = _build_eval_for_batch("s1", "da-nang", budget=150000, item_cost=100000, grounded_count=2)
    # s2: budget 500k, actual 200k => COMPLIANT
    s2, e2 = _build_eval_for_batch("s2", "ha-noi", budget=500000, item_cost=100000, grounded_count=2)
    # s3: budget None => NOT_APPLICABLE
    s3, e3 = _build_eval_for_batch("s3", "ha-long", budget=None, item_cost=100000, grounded_count=2)

    assert e1.budget_overrun_fraction == round((200000 - 150000) / 150000, 6)
    assert e2.budget_overrun_fraction == 0.0
    assert e3.budget_overrun_fraction is None

    manifest = BenchmarkAssignmentManifest(
        manifest_id="test-budget-denom",
        assigned_scenarios=[s1, s2, s3],
    )
    agg = aggregate_benchmark_evaluations(manifest, [e1, e2, e3])

    assert agg.budget_applicable_scenario_count == 2
    assert agg.budget_not_applicable_scenario_count == 1
    assert agg.budget_violation_scenario_count == 1
    assert agg.estimated_budget_violation_rate == 0.5


def test_w06_i01c_17_budget_null_excluded_from_budget_denominator():
    """W06-I01C-17: when all scenarios have budget=None, budget_applicable_scenario_count == 0 and rate is None."""
    s1, e1 = _build_eval_for_batch("s1", "da-nang", budget=None)
    manifest = BenchmarkAssignmentManifest(manifest_id="test-budget-null", assigned_scenarios=[s1])
    agg = aggregate_benchmark_evaluations(manifest, [e1])

    assert agg.budget_applicable_scenario_count == 0
    assert agg.budget_violation_scenario_count == 0
    assert agg.estimated_budget_violation_rate is None


def test_w06_i01c_18_invalid_provider_run_not_classified_as_factual_budget_violation():
    """W06-I01C-18: invalid provider run not classified as factual budget violation."""
    s1, e1 = _build_eval_for_batch("s1", "da-nang", budget=500000, item_cost=100000)
    s2, e2 = _build_eval_for_batch(
        "s2", "ha-noi", budget=500000, run_status=BenchmarkRunStatus.UNPARSABLE_MODEL_OUTPUT
    )
    manifest = BenchmarkAssignmentManifest(manifest_id="test-budget-inv", assigned_scenarios=[s1, s2])
    agg = aggregate_benchmark_evaluations(manifest, [e1, e2])

    assert agg.budget_applicable_scenario_count == 1
    assert agg.budget_violation_scenario_count == 0
    assert agg.estimated_budget_violation_rate == 0.0


def test_w06_i01c_19_valid_run_rate_denominator_exactly_assigned_scenarios():
    """W06-I01C-19: VALID_RUN_RATE denominator is exactly assigned scenarios."""
    s1, e1 = _build_eval_for_batch("s1", "da-nang")
    s2, e2 = _build_eval_for_batch("s2", "ha-noi")
    s3, e3 = _build_eval_for_batch("s3", "ha-long", run_status=BenchmarkRunStatus.API_ERROR)
    s4, e4 = _build_eval_for_batch("s4", "da-nang", run_status=BenchmarkRunStatus.MOCK_OR_FALLBACK_RUN)

    manifest = BenchmarkAssignmentManifest(
        manifest_id="test-valid-rate",
        assigned_scenarios=[s1, s2, s3, s4],
    )
    agg = aggregate_benchmark_evaluations(manifest, [e1, e2, e3, e4])

    assert agg.assigned_scenario_count == 4
    assert agg.valid_run_count == 2
    assert agg.invalid_run_count == 2
    assert agg.valid_run_rate == 0.5


def _build_synthetic_100_fixture(
    *,
    invalid_count: int = 0,
    violation_count: int = 0,
) -> Tuple[BenchmarkAssignmentManifest, List[ScenarioEvaluationResult]]:
    specs: List[AssignedScenarioSpec] = []
    evals: List[ScenarioEvaluationResult] = []
    allocations = [("ha-noi", 34), ("da-nang", 33), ("ha-long", 33)]
    idx = 0
    for dest, count in allocations:
        for j in range(count):
            sid = f"SYNTH_100_{dest}_{j + 1:02d}"
            is_invalid = idx < invalid_count
            is_viol = (not is_invalid) and (idx < invalid_count + violation_count)
            spec, ev = _build_eval_for_batch(
                sid,
                dest,
                run_status=BenchmarkRunStatus.API_ERROR if is_invalid else BenchmarkRunStatus.VALID,
                schedule_overlap=is_viol,
            )
            specs.append(spec)
            evals.append(ev)
            idx += 1

    manifest = BenchmarkAssignmentManifest(
        manifest_id="SYNTHETIC_TEST_100_MANIFEST",
        is_final_100_frozen=True,
        assigned_scenarios=specs,
    )
    return manifest, evals


def test_w06_i01c_20_core_scenario_pass_rate_all_100_denominator_exactly_100_in_final_100():
    """W06-I01C-20: CORE_SCENARIO_PASS_RATE_ALL_100 denominator is exactly 100 in FINAL_100 mode."""
    manifest, evals = _build_synthetic_100_fixture(invalid_count=5, violation_count=10)
    agg = aggregate_benchmark_evaluations(manifest, evals, final_100_mode=True)

    assert agg.final_100_mode is True
    assert agg.assigned_scenario_count == 100
    assert agg.primary_pass_rate_denominator == 100
    assert agg.valid_run_count == 95
    assert agg.invalid_run_count == 5
    assert agg.core_scenario_pass_count == 85
    assert agg.core_scenario_pass_rate_all_100 == 0.85
    assert agg.core_scenario_pass_rate_all_100_ci95.n == 100
    assert agg.core_scenario_pass_rate_all_100_ci95.k == 85


def test_w06_i01c_21_invalid_runs_remain_denominator_non_passes():
    """W06-I01C-21: invalid runs contribute 0 to core_scenario_pass_count and remain in primary denominator."""
    manifest, evals = _build_synthetic_100_fixture(invalid_count=20, violation_count=0)
    agg = aggregate_benchmark_evaluations(manifest, evals, final_100_mode=True)

    # All 80 valid runs pass, 20 invalid runs fail => primary pass rate is 80/100 = 0.80, NOT 1.0
    assert agg.core_scenario_pass_count == 80
    assert agg.core_scenario_pass_rate_all_100 == 0.80
    assert agg.GROUNDING_GATE.gate_pass is False
    assert agg.GROUNDING_GATE.gate_status == "INCOMPLETE_DUE_TO_INVALID_RUNS"


def test_w06_i01c_22_conditional_on_valid_pass_rate_remains_secondary_diagnostic():
    """W06-I01C-22: conditional_core_pass_rate_on_valid_runs is reported separately as secondary diagnostic."""
    manifest, evals = _build_synthetic_100_fixture(invalid_count=20, violation_count=0)
    agg = aggregate_benchmark_evaluations(manifest, evals, final_100_mode=True)

    assert agg.core_scenario_pass_rate_all_100 == 0.80
    assert agg.conditional_core_pass_rate_on_valid_runs == 1.0
    assert "SECONDARY_DIAGNOSTIC_ONLY" in agg.conditional_core_pass_rate_status


def test_w06_i01c_23_wilson_interval_deterministic_and_numerically_correct():
    """W06-I01C-23: Wilson 95% confidence interval deterministic and numerically accurate."""
    ci_50_100 = compute_wilson_ci95(50, 100)
    assert ci_50_100 is not None
    assert ci_50_100.point_estimate == 0.5
    # Exact Wilson 95% CI for 50/100 with z=1.959963984540054 is [0.403832, 0.596168]
    assert ci_50_100.lower == 0.403832
    assert ci_50_100.upper == 0.596168

    ci_100_100 = compute_wilson_ci95(100, 100)
    assert ci_100_100 is not None
    assert ci_100_100.lower == 0.963007
    assert ci_100_100.upper == 1.0

    ci_0_100 = compute_wilson_ci95(0, 100)
    assert ci_0_100 is not None
    assert ci_0_100.lower == 0.0
    assert ci_0_100.upper == 0.036993

    assert compute_wilson_ci95(0, 0) is None


def test_w06_i01c_24_item_grounded_poi_rate_aggregates_counts_not_mean_of_means():
    """W06-I01C-24: item Grounded POI Rate aggregates sum(grounded)/sum(poi_visits), not mean-of-means."""
    # Scenario 1: 1 grounded / 1 ungrounded => 1/2 = 0.5
    s1, e1 = _build_eval_for_batch("s1", "da-nang", grounded_count=1, ungrounded_count=1)
    # Scenario 2: 8 grounded / 0 ungrounded => 8/8 = 1.0
    s2, e2 = _build_eval_for_batch("s2", "ha-noi", grounded_count=8, ungrounded_count=0)

    manifest = BenchmarkAssignmentManifest(manifest_id="test-counts-vs-means", assigned_scenarios=[s1, s2])
    agg = aggregate_benchmark_evaluations(manifest, [e1, e2])

    # Count-based ratio: (1 + 8) / (2 + 8) = 9 / 10 = 0.9 (whereas mean-of-means would be (0.5 + 1.0)/2 = 0.75)
    assert agg.grounded_item_count == 9
    assert agg.poi_visit_item_count == 10
    assert agg.grounded_poi_rate == 0.9
    assert agg.grounded_poi_rate != 0.75


def test_w06_i01c_25_cluster_bootstrap_resamples_scenarios_not_items():
    """W06-I01C-25: cluster bootstrap resamples scenarios as clusters, not independent items."""
    # Construct 2 scenarios where every scenario has identical ratio 3/4 = 0.75.
    # Under scenario-cluster resampling, every resample of scenarios has ratio (3*k)/(4*k) == 0.75,
    # so the cluster bootstrap CI is [0.75, 0.75], whereas item-level Bernoulli resampling would have non-zero width!
    clusters = [("s1", 3, 4), ("s2", 6, 8)]
    ci = compute_scenario_cluster_bootstrap_grounding_ci95(clusters)
    assert ci is not None
    assert ci.resampling_unit == "scenario"
    assert ci.cluster_count == 2
    assert ci.point_estimate == 0.75
    assert ci.lower == 0.75
    assert ci.upper == 0.75


def test_w06_i01c_26_bootstrap_iterations_10000():
    """W06-I01C-26: bootstrap iterations = 10000."""
    assert BOOTSTRAP_ITERATIONS == 10000
    ci = compute_scenario_cluster_bootstrap_grounding_ci95([("s1", 2, 2), ("s2", 1, 2)])
    assert ci is not None
    assert ci.iterations == 10000


def test_w06_i01c_27_bootstrap_seed_20261015():
    """W06-I01C-27: bootstrap seed = 20261015."""
    assert BOOTSTRAP_SEED == 20261015
    ci = compute_scenario_cluster_bootstrap_grounding_ci95([("s1", 2, 2), ("s2", 1, 2)])
    assert ci is not None
    assert ci.seed == 20261015


def test_w06_i01c_28_bootstrap_output_deterministic():
    """W06-I01C-28: bootstrap output is deterministic and invariant to input ordering."""
    clusters_a = [("s1", 4, 4), ("s2", 2, 4), ("s3", 3, 5), ("s4", 5, 5)]
    clusters_b = list(reversed(clusters_a))
    ci_a = compute_scenario_cluster_bootstrap_grounding_ci95(clusters_a)
    ci_b = compute_scenario_cluster_bootstrap_grounding_ci95(clusters_b)
    assert ci_a == ci_b


def test_w06_i01c_29_per_destination_grouping_correct():
    """W06-I01C-29: per-destination grouping accurately stratifies ha-noi, da-nang, ha-long."""
    s1, e1 = _build_eval_for_batch("hn1", "ha-noi", grounded_count=2)
    s2, e2 = _build_eval_for_batch("dn1", "da-nang", grounded_count=2, schedule_overlap=True)
    s3, e3 = _build_eval_for_batch("hl1", "ha-long", grounded_count=2)

    manifest = BenchmarkAssignmentManifest(manifest_id="test-per-dest", assigned_scenarios=[s1, s2, s3])
    agg = aggregate_benchmark_evaluations(manifest, [e1, e2, e3])

    assert agg.per_destination["ha-noi"].core_scenario_pass_rate == 1.0
    assert agg.per_destination["da-nang"].core_scenario_pass_rate == 0.0
    assert agg.per_destination["ha-long"].core_scenario_pass_rate == 1.0


def test_w06_i01c_30_equal_destination_macro_gives_each_destination_equal_weight():
    """W06-I01C-30: equal-destination macro weights each destination 1/3 regardless of scenario count."""
    # ha-noi has 4 passing scenarios (rate 1.0); da-nang has 1 failing (rate 0.0); ha-long has 1 failing (rate 0.0)
    # Micro pass rate = 4/6 = 0.666667, but equal-destination macro = (1.0 + 0.0 + 0.0)/3 = 0.333333
    specs = []
    evals = []
    for i in range(4):
        s, e = _build_eval_for_batch(f"hn_{i}", "ha-noi")
        specs.append(s)
        evals.append(e)
    s_dn, e_dn = _build_eval_for_batch("dn_0", "da-nang", schedule_overlap=True)
    s_hl, e_hl = _build_eval_for_batch("hl_0", "ha-long", schedule_overlap=True)
    specs.extend([s_dn, s_hl])
    evals.extend([e_dn, e_hl])

    manifest = BenchmarkAssignmentManifest(manifest_id="test-macro", assigned_scenarios=specs)
    agg = aggregate_benchmark_evaluations(manifest, evals)

    assert agg.core_scenario_pass_rate_all_assigned == round(4 / 6, 6)
    assert agg.core_scenario_pass_rate_all_100 is None
    assert agg.equal_destination_macro.core_scenario_pass_rate_macro == round(1 / 3, 6)


def test_w06_i01c_31_duplicate_assigned_scenario_id_rejected():
    """W06-I01C-31: duplicate assigned scenario ID rejected."""
    s1, e1 = _build_eval_for_batch("dup_id", "da-nang")
    manifest = BenchmarkAssignmentManifest(manifest_id="test-dup", assigned_scenarios=[s1, s1])
    with pytest.raises(ValueError, match="Duplicate assigned scenario_id"):
        aggregate_benchmark_evaluations(manifest, [e1])


def test_w06_i01c_32_missing_assigned_scenario_rejected_in_final_100():
    """W06-I01C-32: missing assigned scenario rejected in FINAL_100."""
    manifest, evals = _build_synthetic_100_fixture()
    with pytest.raises(ValueError, match="Missing evaluation results for assigned scenarios"):
        aggregate_benchmark_evaluations(manifest, evals[:-1], final_100_mode=True)


def test_w06_i01c_33_unexpected_scenario_result_rejected():
    """W06-I01C-33: unexpected scenario result rejected."""
    s1, e1 = _build_eval_for_batch("s1", "da-nang")
    _, e_extra = _build_eval_for_batch("unassigned_s2", "ha-noi")
    manifest = BenchmarkAssignmentManifest(manifest_id="test-unexp", assigned_scenarios=[s1])
    with pytest.raises(ValueError, match="Unexpected evaluation result for unassigned scenario_id"):
        aggregate_benchmark_evaluations(manifest, [e1, e_extra])


def test_w06_i01c_34_final_100_requires_exact_34_33_33_allocation():
    """W06-I01C-34: FINAL_100 mode rejects 100 scenarios if destination allocation is not 34/33/33."""
    manifest, evals = _build_synthetic_100_fixture()
    # Change one ha-noi scenario to da-nang so allocation becomes 33/34/33
    manifest.assigned_scenarios[0].destination_slug = "da-nang"
    evals[0].destination_slug = "da-nang"
    with pytest.raises(ValueError, match="FINAL_100 mode requires exact destination allocation"):
        aggregate_benchmark_evaluations(manifest, evals, final_100_mode=True)


def test_w06_i01c_35_no_real_final_100_scenarios_generated():
    """W06-I01C-35: no real final 100 scenarios generated on disk."""
    scenario_files = sorted(p.name for p in PLANNER_EVAL_DIR.glob("*.json"))
    assert scenario_files == ["da_nang_4d.json", "ha_giang_3d.json", "moc_chau_3d.json"]


def test_w06_i01c_36_opening_hours_parser_coverage_inventory_reproduces_101_core_records():
    """W06-I01C-36: opening-hours parser coverage inventory reproduces 101 core records."""
    assert COVERAGE_JSON_PATH.exists()
    persisted = json.loads(COVERAGE_JSON_PATH.read_text(encoding="utf-8"))
    recomputed = build_opening_hours_parser_coverage_report()

    assert persisted == recomputed
    assert persisted["total_core_pois"] == 622
    assert persisted["core_opening_hours_records"] == 101
    assert persisted["unique_opening_hours_string_count"] == 73
    assert persisted["parser_supported_record_count"] == 91
    assert persisted["parser_unsupported_record_count"] == 10
    assert persisted["parser_supported_ratio"] == round(91 / 101, 6)
    assert persisted["claims_planner_performance"] is False


def test_w06_i01c_37_parser_unsupported_records_remain_unknown_capable_not_guessed():
    """W06-I01C-37: every unsupported record in the 101-record corpus evaluates to UNKNOWN, never guessed."""
    coverage = build_opening_hours_parser_coverage_report()
    assert len(coverage["unsupported_records"]) == 10
    for rec in coverage["unsupported_records"]:
        parsed = parse_osm_opening_hours(rec["opening_hours"])
        assert parsed.supported is False
        ev = evaluate_poi_visit_opening_hours(
            day_number=1,
            date_str="2026-07-07",
            date_context_trusted=True,
            order_index=1,
            place_id=rec["place_id"],
            is_grounded=True,
            opening_hours_raw=rec["opening_hours"],
            start_time="10:00",
            end_time="11:00",
        )
        assert ev.opening_hours_state == "UNKNOWN"
        assert ev.reason_code == rec["reason_code"]


def test_w06_i01c_38_aggregation_output_canonical_json_byte_deterministic(tmp_path: Path):
    """W06-I01C-38: aggregation output canonical JSON is byte-identical across repeated runs."""
    s1, e1 = _build_eval_for_batch("s1", "ha-noi")
    s2, e2 = _build_eval_for_batch("s2", "da-nang")
    s3, e3 = _build_eval_for_batch("s3", "ha-long")
    manifest = BenchmarkAssignmentManifest(manifest_id="det-test", assigned_scenarios=[s1, s2, s3])

    manifest_path = tmp_path / "assignment_manifest.json"
    evals_dir = tmp_path / "evals"
    write_canonical_json(manifest_path, manifest.model_dump())
    for ev in (e1, e2, e3):
        write_canonical_json(evals_dir / ev.scenario_id / "scenario_evaluation.json", ev.model_dump())

    out_1 = tmp_path / "agg_1.json"
    out_2 = tmp_path / "agg_2.json"
    aggregate_evaluations_from_disk(
        assignment_manifest_path=manifest_path,
        evaluations_dir=evals_dir,
        output_path=out_1,
    )
    rc = aggregator_cli_main(
        [
            "--assignment-manifest",
            str(manifest_path),
            "--evaluations-dir",
            str(evals_dir),
            "--output",
            str(out_2),
        ]
    )
    assert rc == 0
    bytes_1 = out_1.read_bytes()
    bytes_2 = out_2.read_bytes()
    assert bytes_1 == bytes_2
    assert bytes_1.endswith(b"\n")
    assert not bytes_1.endswith(b"\n\n")


def test_w06_i01c_39_no_weighted_composite_score_exists():
    """W06-I01C-39: no weighted composite score exists in scenario evaluation or batch aggregation."""
    s1, e1 = _build_eval_for_batch("s1", "ha-noi")
    s2, e2 = _build_eval_for_batch("s2", "da-nang")
    s3, e3 = _build_eval_for_batch("s3", "ha-long")
    manifest = BenchmarkAssignmentManifest(manifest_id="no-comp-test", assigned_scenarios=[s1, s2, s3])
    agg = aggregate_benchmark_evaluations(manifest, [e1, e2, e3])

    for payload in (e1.model_dump(), agg.model_dump()):
        for key in payload:
            assert "composite" not in key.lower()
            assert "weighted" not in key.lower()


def test_w06_i01c_40_no_scientific_final_benchmark_result_generated():
    """W06-I01C-40: receipt, docs, P1..P12 status, and scientific boundaries verified."""
    assert RECEIPT_01C_JSON_PATH.exists()
    assert RECEIPT_01C_MD_PATH.exists()
    assert SEMANTICS_01C_MD_PATH.exists()

    receipt = json.loads(RECEIPT_01C_JSON_PATH.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT_JSON_PATH.read_text(encoding="utf-8"))

    assert receipt["task_id"] == "W06-INSTRUMENT-01C"
    assert receipt["base_develop_sha"] == "98d01c1e2a83b6fe96699b802d1e0ff80cdd3758"
    assert receipt["evaluator_version"] == EVALUATOR_VERSION_01C == "W06-CORE-EVALUATOR-01C-V1.0.0"
    assert EVALUATOR_VERSION == EVALUATOR_VERSION_01D == "W06-CORE-EVALUATOR-01D-V1.0.0"
    assert receipt["aggregator_version"] == AGGREGATOR_VERSION
    assert receipt["opening_hours_parser_version"] == OPENING_HOURS_PARSER_VERSION

    bounds = receipt["scientific_boundaries"]
    assert bounds["final_100_scenarios_generated"] is False
    assert bounds["final_100_scenario_manifest_created"] is False
    assert bounds["final_benchmark_executed"] is False
    assert bounds["scientific_results_generated"] is False
    assert bounds["preregistration_created"] is False
    assert bounds["W5_modified"] is False
    assert bounds["production_planner_behavior_modified"] is False
    assert bounds["measurement_contract_historical_text_modified"] is False
    assert bounds["weighted_composite_score_exists"] is False

    matrix = receipt["prerequisite_implementation_matrix"]
    contract_prereqs = {
        item["id"]: item["requirement"]
        for item in contract["required_instrumentation_prerequisites"]
    }
    assert list(matrix.keys()) == [f"P{i}" for i in range(1, 13)]
    for pid, req in contract_prereqs.items():
        assert matrix[pid]["contract_requirement"] == req

    assert matrix["P11"]["status"] == "NOT_IMPLEMENTED"
    for pid in ("P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9", "P10", "P12"):
        assert matrix[pid]["status"] == "IMPLEMENTED"
