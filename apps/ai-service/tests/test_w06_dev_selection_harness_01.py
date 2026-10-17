"""Offline Scientific Test Suite for W06 DEV Selection Harness (W06-DEV-SELECTION-HARNESS-01-OFFLINE).

Covers required test IDs DH-01 through DH-35 as distinct test functions plus mock transport
execution, cell immutability, and CLI safety mode checks.
Zero live provider calls are made.
"""

from __future__ import annotations

import json
from typing import Dict, List

import pytest

from app.evaluation.dev_selection_harness import (
    ALLOWED_PROMPT_IDS,
    COST_CRITERION_APPLIED,
    COST_CRITERION_SKIPPED_NOT_COMPARABLE,
    DEFAULT_HARNESS_ARTIFACT_PATH,
    DEFAULT_HARNESS_RECEIPT_PATH,
    DEV_SELECT_COUNT,
    DEV_SELECT_MAX_CALLS,
    DEV_TOTAL_COUNT,
    DEV_TUNE_COUNT,
    DEV_TUNE_MAX_CALLS_ONE_PROMPT,
    DEV_TUNE_MAX_CALLS_TWO_PROMPTS,
    EXPECTED_BASE_DEVELOP_SHA_DEV_HARNESS,
    EXPECTED_DEV_SELECT_MARGINALS,
    EXPECTED_DEV_TUNE_MARGINALS,
    EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
    EXPECTED_STOCHASTICITY_FIXTURE_IDS,
    FORBIDDEN_FINAL100_BUNDLE_PATH,
    FORBIDDEN_P11_MANIFEST_PATH,
    MAX_PROMPT_CANDIDATES,
    NEXT_GATE_ID,
    ORDERED_CANDIDATE_IDS,
    STOCHASTICITY_EXECUTIONS_PER_FIXTURE,
    STOCHASTICITY_FIXTURE_COUNT,
    STOCHASTICITY_MAX_CALLS,
    TASK_ID_DEV_HARNESS,
    CandidateCostComparabilityRecord,
    CandidateRegistryIntegrityError,
    DenominatorIntegrityError,
    DevCandidateSpec,
    DevCellExecutionManifest,
    DevCellExecutionReceipt,
    DevCellFailureClassification,
    DevGroupAggregateMetrics,
    DevHarnessOfflineViolationError,
    Final100FirewallViolationError,
    ImmutableCellExecutionError,
    MockProviderTransportResponse,
    PromptRegistryIntegrityError,
    StochasticityGateViolationError,
    aggregate_dev_cell_receipts,
    assert_not_final100_path,
    assert_not_final100_scenario,
    assert_not_final100_scenario_id,
    build_default_infrastructure_prompt_registry,
    build_deterministic_dev_scenario_context,
    build_dev_select_execution_plan,
    build_dev_tune_execution_plan,
    build_prompt_registry,
    build_stochasticity_diagnostic_plan,
    calculate_expected_dev_select_cell_count,
    calculate_expected_dev_tune_cell_count,
    compute_harness_determinism_hashes,
    create_prompt_candidate_spec,
    evaluate_dev_cell_scenario,
    execute_dev_cell_with_mock_transport,
    load_and_verify_candidate_registry,
    load_and_verify_frozen_dev_bundle,
    reduce_survivors_by_10pp_rule,
    run_cli,
    select_winning_candidate_dev_select,
    select_winning_prompt_dev_tune,
    verify_frozen_authorities_dev_harness,
)
from app.evaluation.model_preflight.base import PREFLIGHT_SHARED_SYSTEM_PROMPT
from app.evaluation.planner_benchmark_evaluator import load_core_catalog_by_place_id
from app.prompts.planner_benchmark_prompt import (
    BENCHMARK_PROMPT_VERSION,
    TRAVEL_PLANNER_BENCHMARK_V2,
    build_destination_catalog_context,
)
from app.schemas.planner_benchmark import (
    BenchmarkRunManifest,
    BenchmarkRunStatus,
    BenchmarkScenarioInput,
    BenchmarkUsageMetadata,
)


@pytest.fixture(scope="module")
def verified_dev_bundle():
    return load_and_verify_frozen_dev_bundle()


@pytest.fixture(scope="module")
def candidate_registry():
    return load_and_verify_candidate_registry()


@pytest.fixture(scope="module")
def default_prompt_registry():
    return build_default_infrastructure_prompt_registry()


@pytest.fixture(scope="module")
def two_prompt_registry():
    p1 = create_prompt_candidate_spec(
        prompt_id="P1",
        prompt_version=BENCHMARK_PROMPT_VERSION,
        system_prompt=PREFLIGHT_SHARED_SYSTEM_PROMPT,
        user_prompt_template=TRAVEL_PLANNER_BENCHMARK_V2,
        created_before_live_dev_execution=True,
    )
    p2 = create_prompt_candidate_spec(
        prompt_id="P2",
        prompt_version="TRAVEL_PLANNER_BENCHMARK_V2_ALT",
        system_prompt=PREFLIGHT_SHARED_SYSTEM_PROMPT + " Prioritize concise notes.",
        user_prompt_template=TRAVEL_PLANNER_BENCHMARK_V2,
        created_before_live_dev_execution=True,
    )
    return build_prompt_registry([p1, p2])


def _make_synthetic_receipt(
    *,
    phase: str,
    prompt_id: str,
    candidate_id: str,
    fixture_id: str,
    valid_run_and_schema: bool = True,
    exact_grounding_pass: bool = True,
    final_core_pass: bool = True,
    failure_classification: DevCellFailureClassification = DevCellFailureClassification.NONE,
    latency_ms: float = 1000.0,
    authoritative_usage_available: bool = True,
    canonical_cost_usd: float | None = 0.01,
) -> DevCellExecutionReceipt:
    model_map = {
        "C1": "gemini-3.8-flash",
        "C2": "gpt-6.1-sol",
        "C3": "claude-sonnet-5-5",
    }
    return DevCellExecutionReceipt(
        run_id=f"SYNTH-{phase}-{prompt_id}-{candidate_id}-{fixture_id}",
        phase=phase,  # type: ignore[arg-type]
        fixture_id=fixture_id,
        candidate_id=candidate_id,
        prompt_id=prompt_id,
        requested_model_id=model_map[candidate_id],
        returned_model_id=model_map[candidate_id],
        attempt_number=1,
        attempted=True,
        failure_classification=failure_classification,
        valid_run_and_schema=valid_run_and_schema,
        exact_grounding_pass=exact_grounding_pass if valid_run_and_schema else False,
        final_core_pass=(
            final_core_pass if (valid_run_and_schema and exact_grounding_pass) else False
        ),
        latency_ms=latency_ms,
        authoritative_usage_available=authoritative_usage_available,
        input_tokens=1000 if authoritative_usage_available else None,
        output_tokens=500 if authoritative_usage_available else None,
        total_tokens=1500 if authoritative_usage_available else None,
        canonical_cost_usd=canonical_cost_usd if authoritative_usage_available else None,
        request_manifest_sha256="a" * 64,
        raw_response_sha256="b" * 64,
        provider_metadata_sha256="c" * 64,
        parsed_response_sha256="d" * 64 if valid_run_and_schema else None,
        evaluation_result_sha256="e" * 64,
    )


def _make_all_comparable_cost_records() -> Dict[str, CandidateCostComparabilityRecord]:
    return {
        "C1": CandidateCostComparabilityRecord(
            candidate_id="C1",
            authoritative_usage_available=True,
            pricing_source="https://ai.google.dev/gemini-api/docs/pricing",
            pricing_access_date="2026-10-17",
            input_price_per_million_usd=0.75,
            output_price_per_million_usd=3.75,
            canonical_cost_computable=True,
        ),
        "C2": CandidateCostComparabilityRecord(
            candidate_id="C2",
            authoritative_usage_available=True,
            pricing_source="https://platform.openai.com/docs/pricing",
            pricing_access_date="2026-10-17",
            input_price_per_million_usd=2.0,
            output_price_per_million_usd=10.0,
            canonical_cost_computable=True,
        ),
        "C3": CandidateCostComparabilityRecord(
            candidate_id="C3",
            authoritative_usage_available=True,
            pricing_source="https://docs.anthropic.com/en/docs/about-claude/pricing",
            pricing_access_date="2026-10-17",
            input_price_per_million_usd=2.0,
            output_price_per_million_usd=10.0,
            canonical_cost_computable=True,
        ),
    }


def _build_valid_plan_dict_for_scenario(scenario: BenchmarkScenarioInput) -> dict:
    pois = build_destination_catalog_context(scenario.destination_slug)
    safe_pois = [p for p in pois if p.opening_hours is None]
    selected_pool = safe_pois if len(safe_pois) >= scenario.days * 2 else pois

    import datetime as dt

    start_dt = dt.date.fromisoformat(scenario.start_date)
    days_list = []
    poi_cursor = 0
    for d_idx in range(scenario.days):
        day_date = (start_dt + dt.timedelta(days=d_idx)).isoformat()
        p1 = selected_pool[poi_cursor % len(selected_pool)]
        p2 = selected_pool[(poi_cursor + 1) % len(selected_pool)]
        poi_cursor += 2
        days_list.append(
            {
                "day_number": d_idx + 1,
                "date": day_date,
                "title": f"Day {d_idx + 1}",
                "items": [
                    {
                        "order_index": 1,
                        "start_time": "08:30",
                        "end_time": "10:00",
                        "activity_kind": "POI_VISIT",
                        "activity": f"Visit {p1.name}",
                        "place_name": p1.name,
                        "place_id": p1.place_id,
                        "notes": "Morning visit",
                        "estimated_cost": 50000,
                        "transport_mode": "taxi",
                    },
                    {
                        "order_index": 2,
                        "start_time": "10:30",
                        "end_time": "12:00",
                        "activity_kind": "POI_VISIT",
                        "activity": f"Visit {p2.name}",
                        "place_name": p2.name,
                        "place_id": p2.place_id,
                        "notes": "Late morning visit",
                        "estimated_cost": 50000,
                        "transport_mode": "taxi",
                    },
                ],
            }
        )
    return {
        "destination": scenario.destination,
        "total_days": scenario.days,
        "overview": "Deterministic valid itinerary.",
        "best_time_to_visit": "All year",
        "general_tips": ["Tip 1"],
        "days": days_list,
    }


def test_dh_01_exact_base_sha():
    """DH-01: Verify exact base develop SHA and frozen authorities."""
    assert EXPECTED_BASE_DEVELOP_SHA_DEV_HARNESS == "50884c610cebf455255b9d05f737d9558cabf2e7"
    harness_payload = json.loads(DEFAULT_HARNESS_ARTIFACT_PATH.read_text(encoding="utf-8"))
    receipt_payload = json.loads(DEFAULT_HARNESS_RECEIPT_PATH.read_text(encoding="utf-8"))
    assert harness_payload["base_develop_sha"] == EXPECTED_BASE_DEVELOP_SHA_DEV_HARNESS
    assert receipt_payload["base_develop_sha"] == EXPECTED_BASE_DEVELOP_SHA_DEV_HARNESS
    assert receipt_payload["task_id"] == TASK_ID_DEV_HARNESS
    assert receipt_payload["next_gate"] == NEXT_GATE_ID
    assert receipt_payload["live_provider_calls"] == 0
    assert receipt_payload["provider_cost_usd"] == 0
    verified = verify_frozen_authorities_dev_harness()
    assert len(verified) == 18


def test_dh_02_dev_total_80(verified_dev_bundle):
    """DH-02: Verify DEV total = 80."""
    assert verified_dev_bundle.total_count == DEV_TOTAL_COUNT == 80


def test_dh_03_dev_tune_total_20(verified_dev_bundle):
    """DH-03: Verify DEV-TUNE total = 20."""
    assert verified_dev_bundle.dev_tune_count == DEV_TUNE_COUNT == 20
    assert len(verified_dev_bundle.dev_tune_fixtures) == 20


def test_dh_04_dev_select_total_60(verified_dev_bundle):
    """DH-04: Verify DEV-SELECT total = 60."""
    assert verified_dev_bundle.dev_select_count == DEV_SELECT_COUNT == 60
    assert len(verified_dev_bundle.dev_select_fixtures) == 60


def test_dh_05_all_frozen_marginals(verified_dev_bundle):
    """DH-05: Verify all frozen DEV-TUNE and DEV-SELECT marginals match exact specifications."""
    assert verified_dev_bundle.dev_tune_marginals == EXPECTED_DEV_TUNE_MARGINALS
    assert verified_dev_bundle.dev_select_marginals == EXPECTED_DEV_SELECT_MARGINALS


def test_dh_06_exact_candidate_registry(candidate_registry):
    """DH-06: Verify exact candidate registry C1, C2, C3."""
    assert candidate_registry.ordered_candidate_ids == ["C1", "C2", "C3"]
    assert set(candidate_registry.candidates.keys()) == {"C1", "C2", "C3"}
    assert candidate_registry.candidates["C1"].requested_model_id == "gemini-3.8-flash"
    assert candidate_registry.candidates["C2"].requested_model_id == "gpt-6.1-sol"
    assert candidate_registry.candidates["C3"].requested_model_id == "claude-sonnet-5-5"


def test_dh_07_all_3_technical_eligibility(candidate_registry):
    """DH-07: Verify all 3 candidates have PASSED_TECHNICAL_PREFLIGHT_SCHEMA_V2."""
    for cid in ORDERED_CANDIDATE_IDS:
        assert (
            candidate_registry.candidates[cid].technical_preflight_v2_status
            == "PASSED_TECHNICAL_PREFLIGHT_SCHEMA_V2"
        )


def test_dh_08_portable_schema_v2_exact_hash(candidate_registry):
    """DH-08: Verify Portable Schema V2 exact SHA256 on all candidates."""
    for cid in ORDERED_CANDIDATE_IDS:
        assert (
            candidate_registry.candidates[cid].portable_generation_schema_v2_sha256
            == EXPECTED_PORTABLE_SCHEMA_V2_SHA256
            == "825a4ff912d851a95f7392cb564b7d7ca3588135508dc6eb3ac6304cdde3c490"
        )


def test_dh_09_final100_runtime_firewall(default_prompt_registry):
    """DH-09: Verify final-100 runtime firewall blocks path access, scenario loading, and context building."""
    with pytest.raises(Final100FirewallViolationError):
        assert_not_final100_path(FORBIDDEN_FINAL100_BUNDLE_PATH)

    with pytest.raises(Final100FirewallViolationError):
        assert_not_final100_path(FORBIDDEN_P11_MANIFEST_PATH)

    with pytest.raises(Final100FirewallViolationError):
        load_and_verify_frozen_dev_bundle(dev_bundle_path=FORBIDDEN_FINAL100_BUNDLE_PATH)

    with pytest.raises(Final100FirewallViolationError):
        assert_not_final100_scenario_id("W06-S001")

    fake_final_scenario = BenchmarkScenarioInput(
        scenario_id="W06-S001",
        destination_slug="ha-noi",
        destination="Hà Nội",
        days=2,
        start_date="2026-11-02",
        end_date="2026-11-03",
        budget=2000000,
        currency="VND",
        travel_style="BUDGET",
        interests=["culture_history"],
        notes=None,
        allow_revisit_place_ids=False,
        fixture_label="W06_FINAL_BENCHMARK",
    )

    with pytest.raises(Final100FirewallViolationError):
        assert_not_final100_scenario(fake_final_scenario)

    with pytest.raises(Final100FirewallViolationError):
        build_deterministic_dev_scenario_context(
            fake_final_scenario, default_prompt_registry.prompts[0]
        )


def test_dh_10_max_prompt_candidates_2(two_prompt_registry):
    """DH-10: Verify max prompt candidates = 2 and >2 prompts rejected."""
    assert MAX_PROMPT_CANDIDATES == 2
    assert len(two_prompt_registry.prompts) == 2

    with pytest.raises(PromptRegistryIntegrityError):
        build_prompt_registry(
            [
                two_prompt_registry.prompts[0],
                two_prompt_registry.prompts[1],
                two_prompt_registry.prompts[0],
            ]
        )


def test_dh_11_p3_rejected():
    """DH-11: Verify P3 or provider-specific prompts are rejected."""
    assert ALLOWED_PROMPT_IDS == ("P1", "P2")
    with pytest.raises(PromptRegistryIntegrityError):
        create_prompt_candidate_spec(
            prompt_id="P3",
            prompt_version="V3",
            system_prompt="sys",
            user_prompt_template=TRAVEL_PLANNER_BENCHMARK_V2,
        )
    with pytest.raises(PromptRegistryIntegrityError):
        create_prompt_candidate_spec(
            prompt_id="P1",
            prompt_version="V1",
            system_prompt="sys",
            user_prompt_template=TRAVEL_PLANNER_BENCHMARK_V2,
            provider_specific_semantic_prompt=True,
        )


def test_dh_12_c4_rejected():
    """DH-12: Verify C4 or candidate model substitution is rejected."""
    with pytest.raises(CandidateRegistryIntegrityError):
        DevCandidateSpec(
            candidate_id="C4",
            provider="Google",
            requested_model_id="gemini-3.8-flash",
            technical_preflight_v2_status="PASSED_TECHNICAL_PREFLIGHT_SCHEMA_V2",
            portable_generation_schema_v2_sha256=EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
            structured_output_wiring={},
            sampling_reasoning_config={},
            omitted_parameters=[],
        )
    with pytest.raises(CandidateRegistryIntegrityError):
        DevCandidateSpec(
            candidate_id="C1",
            provider="Google",
            requested_model_id="gemini-other-model",
            technical_preflight_v2_status="PASSED_TECHNICAL_PREFLIGHT_SCHEMA_V2",
            portable_generation_schema_v2_sha256=EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
            structured_output_wiring={},
            sampling_reasoning_config={},
            omitted_parameters=[],
        )


def test_dh_13_retry_0(candidate_registry):
    """DH-13: Verify retry = 0 across all candidates and manifests."""
    for cid, spec in candidate_registry.candidates.items():
        assert spec.automatic_retry == 0
        assert spec.transport_retry == 0
        assert spec.manual_retry == 0

    with pytest.raises(ValueError):
        DevCellExecutionManifest(
            run_id="r1",
            phase="DEV_SELECT",
            fixture_id="W06-DEV-SELECT-001",
            candidate_id="C1",
            prompt_id="P1",
            requested_model_id="gemini-3.8-flash",
            scenario_sha256="0" * 64,
            catalog_context_sha256="0" * 64,
            system_prompt_sha256="0" * 64,
            user_prompt_sha256="0" * 64,
            semantic_schema_sha256="0" * 64,
            portable_generation_schema_v2_sha256=EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
            sampling_reasoning_configuration={},
            retry=1,
        )


def test_dh_14_fallback_false(candidate_registry):
    """DH-14: Verify fallback = False across all candidates and manifests."""
    for spec in candidate_registry.candidates.values():
        assert spec.fallback is False

    with pytest.raises(ValueError):
        DevCellExecutionManifest(
            run_id="r1",
            phase="DEV_SELECT",
            fixture_id="W06-DEV-SELECT-001",
            candidate_id="C1",
            prompt_id="P1",
            requested_model_id="gemini-3.8-flash",
            scenario_sha256="0" * 64,
            catalog_context_sha256="0" * 64,
            system_prompt_sha256="0" * 64,
            user_prompt_sha256="0" * 64,
            semantic_schema_sha256="0" * 64,
            portable_generation_schema_v2_sha256=EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
            sampling_reasoning_configuration={},
            fallback=True,
        )


def test_dh_15_repair_0(candidate_registry):
    """DH-15: Verify repair = 0 across all candidates and manifests."""
    for spec in candidate_registry.candidates.values():
        assert spec.llm_repair == 0
        assert spec.deterministic_semantic_repair is False

    with pytest.raises(ValueError):
        DevCellExecutionManifest(
            run_id="r1",
            phase="DEV_SELECT",
            fixture_id="W06-DEV-SELECT-001",
            candidate_id="C1",
            prompt_id="P1",
            requested_model_id="gemini-3.8-flash",
            scenario_sha256="0" * 64,
            catalog_context_sha256="0" * 64,
            system_prompt_sha256="0" * 64,
            user_prompt_sha256="0" * 64,
            semantic_schema_sha256="0" * 64,
            portable_generation_schema_v2_sha256=EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
            sampling_reasoning_configuration={},
            repair=1,
        )


def test_dh_16_one_execution_per_cell(candidate_registry):
    """DH-16: Verify 1 execution per cell in DEV_TUNE and DEV_SELECT."""
    for spec in candidate_registry.candidates.values():
        assert spec.llm_calls_per_execution == 1

    with pytest.raises(ValueError):
        DevCellExecutionManifest(
            run_id="r2",
            phase="DEV_SELECT",
            fixture_id="W06-DEV-SELECT-001",
            candidate_id="C1",
            prompt_id="P1",
            requested_model_id="gemini-3.8-flash",
            scenario_sha256="0" * 64,
            catalog_context_sha256="0" * 64,
            system_prompt_sha256="0" * 64,
            user_prompt_sha256="0" * 64,
            semantic_schema_sha256="0" * 64,
            portable_generation_schema_v2_sha256=EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
            sampling_reasoning_configuration={},
            attempt_number=2,
        )


def test_dh_17_failed_cell_remains_denominator(verified_dev_bundle):
    """DH-17: Verify failed cells remain in denominator and dropping any assigned cell raises DenominatorIntegrityError."""
    fids = verified_dev_bundle.dev_tune_ids
    assigned_keys = [("P1", "C1", fid) for fid in fids]
    receipts: List[DevCellExecutionReceipt] = []
    for idx, fid in enumerate(fids):
        if idx < 15:
            receipts.append(
                _make_synthetic_receipt(
                    phase="DEV_TUNE",
                    prompt_id="P1",
                    candidate_id="C1",
                    fixture_id=fid,
                )
            )
        else:
            receipts.append(
                _make_synthetic_receipt(
                    phase="DEV_TUNE",
                    prompt_id="P1",
                    candidate_id="C1",
                    fixture_id=fid,
                    valid_run_and_schema=False,
                    exact_grounding_pass=False,
                    final_core_pass=False,
                    failure_classification=DevCellFailureClassification.HTTP_429,
                )
            )

    agg = aggregate_dev_cell_receipts(
        group_id="C1",
        assigned_cell_keys=assigned_keys,
        cell_receipts=receipts,
    )
    assert agg.n_assigned == 20
    assert agg.n_attempted == 20
    assert agg.n_valid_schema == 15
    assert agg.valid_run_and_schema_rate == 0.75

    with pytest.raises(DenominatorIntegrityError):
        aggregate_dev_cell_receipts(
            group_id="C1",
            assigned_cell_keys=assigned_keys,
            cell_receipts=receipts[:15],
        )


def test_dh_18_dev_tune_60_calls_for_1_prompt(
    verified_dev_bundle, candidate_registry, default_prompt_registry
):
    """DH-18: Verify DEV-TUNE = 60 calls for 1 prompt."""
    assert calculate_expected_dev_tune_cell_count(1) == DEV_TUNE_MAX_CALLS_ONE_PROMPT == 60
    plan_1p = build_dev_tune_execution_plan(
        default_prompt_registry,
        dev_bundle=verified_dev_bundle,
        candidate_registry=candidate_registry,
    )
    assert plan_1p.expected_total_cells == 60
    assert len(plan_1p.cells) == 60


def test_dh_19_dev_tune_120_calls_for_2_prompts(
    verified_dev_bundle, candidate_registry, two_prompt_registry
):
    """DH-19: Verify DEV-TUNE = 120 calls for 2 prompts."""
    assert calculate_expected_dev_tune_cell_count(2) == DEV_TUNE_MAX_CALLS_TWO_PROMPTS == 120
    plan_2p = build_dev_tune_execution_plan(
        two_prompt_registry,
        dev_bundle=verified_dev_bundle,
        candidate_registry=candidate_registry,
    )
    assert plan_2p.expected_total_cells == 120
    assert len(plan_2p.cells) == 120


def test_dh_20_dev_select_180_calls(
    verified_dev_bundle, candidate_registry, default_prompt_registry
):
    """DH-20: Verify DEV-SELECT = 180 calls."""
    assert calculate_expected_dev_select_cell_count(locked_prompt_count=1) == DEV_SELECT_MAX_CALLS == 180
    plan_sel = build_dev_select_execution_plan(
        default_prompt_registry.prompts[0],
        dev_bundle=verified_dev_bundle,
        candidate_registry=candidate_registry,
    )
    assert plan_sel.expected_total_cells == 180
    assert len(plan_sel.cells) == 180


def test_dh_21_prompt_selection_10pp_algorithm(verified_dev_bundle, two_prompt_registry):
    """DH-21: Verify DEV-TUNE prompt selection 10pp rule and P1 administrative tiebreak."""
    fids = verified_dev_bundle.dev_tune_ids
    receipts_p2_wins: List[DevCellExecutionReceipt] = []
    for pid in ("P1", "P2"):
        cell_idx = 0
        for cid in ORDERED_CANDIDATE_IDS:
            for fid in fids:
                cell_idx += 1
                grounding_ok = (cell_idx <= 45) if pid == "P1" else (cell_idx <= 54)
                receipts_p2_wins.append(
                    _make_synthetic_receipt(
                        phase="DEV_TUNE",
                        prompt_id=pid,
                        candidate_id=cid,
                        fixture_id=fid,
                        valid_run_and_schema=True,
                        exact_grounding_pass=grounding_ok,
                        final_core_pass=grounding_ok,
                    )
                )

    res_p2 = select_winning_prompt_dev_tune(
        prompt_registry=two_prompt_registry,
        cell_receipts=receipts_p2_wins,
        dev_tune_fixture_ids=fids,
    )
    assert res_p2.selected_prompt_id == "P2"
    assert res_p2.selected_at_stage == "EXACT_GROUNDING_PASS_RATE"
    assert res_p2.is_administrative_tiebreak is False

    receipts_tie: List[DevCellExecutionReceipt] = []
    for pid in ("P1", "P2"):
        cell_idx = 0
        for cid in ORDERED_CANDIDATE_IDS:
            for fid in fids:
                cell_idx += 1
                ok = (cell_idx <= 48) if pid == "P1" else (cell_idx <= 54)
                receipts_tie.append(
                    _make_synthetic_receipt(
                        phase="DEV_TUNE",
                        prompt_id=pid,
                        candidate_id=cid,
                        fixture_id=fid,
                        valid_run_and_schema=True,
                        exact_grounding_pass=ok,
                        final_core_pass=ok,
                    )
                )

    res_tie = select_winning_prompt_dev_tune(
        prompt_registry=two_prompt_registry,
        cell_receipts=receipts_tie,
        dev_tune_fixture_ids=fids,
    )
    assert res_tie.selected_prompt_id == "P1"
    assert res_tie.selected_at_stage == "ADMINISTRATIVE_TIEBREAK_P1"
    assert res_tie.is_administrative_tiebreak is True


def test_dh_22_prompt_non_pairwise_chaining_proof():
    """DH-22: Prove prompt survivor reduction is set-based relative-to-best (0.90, 0.82, 0.73 -> C eliminated)."""
    survivors, best = reduce_survivors_by_10pp_rule(
        ["P_A", "P_B", "P_C"],
        {"P_A": 0.90, "P_B": 0.82, "P_C": 0.73},
    )
    assert best == 0.90
    assert survivors == ["P_A", "P_B"]
    assert "P_C" not in survivors


def test_dh_23_model_selection_10pp_algorithm(verified_dev_bundle):
    """DH-23: Verify DEV-SELECT model selection 10pp algorithm across Criteria 1-3."""
    fids = verified_dev_bundle.dev_select_ids
    receipts: List[DevCellExecutionReceipt] = []
    valid_counts = {"C1": 54, "C2": 49, "C3": 44}
    core_counts = {"C1": 40, "C2": 50, "C3": 44}

    for cid in ORDERED_CANDIDATE_IDS:
        for idx, fid in enumerate(fids, start=1):
            v_ok = idx <= valid_counts[cid]
            c_ok = v_ok and (idx <= core_counts[cid])
            receipts.append(
                _make_synthetic_receipt(
                    phase="DEV_SELECT",
                    prompt_id="P1",
                    candidate_id=cid,
                    fixture_id=fid,
                    valid_run_and_schema=v_ok,
                    exact_grounding_pass=v_ok,
                    final_core_pass=c_ok,
                )
            )

    res = select_winning_candidate_dev_select(
        cell_receipts=receipts,
        cost_comparability_by_candidate=_make_all_comparable_cost_records(),
        dev_select_fixture_ids=fids,
    )
    assert res.selected_candidate_id == "C2"
    assert res.selected_at_stage == "FINAL_CORE_PASS_RATE"


def test_dh_24_model_non_pairwise_chaining_proof(verified_dev_bundle):
    """DH-24: Prove model survivor reduction is set-based relative-to-best (A=0.90, B=0.82, C=0.73 -> C eliminated)."""
    surv, best = reduce_survivors_by_10pp_rule(
        ["C1", "C2", "C3"],
        {"C1": 0.90, "C2": 0.82, "C3": 0.73},
    )
    assert best == 0.90
    assert surv == ["C1", "C2"]
    assert "C3" not in surv


def test_dh_25_26_cost_criterion_all_survivor_comparability_and_skip_status(verified_dev_bundle):
    """DH-25 & DH-26: Verify cost criterion requires all-survivor comparability and emits COST_CRITERION_SKIPPED_NOT_COMPARABLE."""
    fids = verified_dev_bundle.dev_select_ids
    incomp_records = _make_all_comparable_cost_records()
    incomp_records["C3"] = CandidateCostComparabilityRecord(
        candidate_id="C3",
        authoritative_usage_available=False,
        canonical_cost_computable=False,
    )
    receipts: List[DevCellExecutionReceipt] = []
    lat_map = {"C1": 18000.0, "C2": 15000.0, "C3": 12000.0}
    for cid in ORDERED_CANDIDATE_IDS:
        for fid in fids:
            receipts.append(
                _make_synthetic_receipt(
                    phase="DEV_SELECT",
                    prompt_id="P1",
                    candidate_id=cid,
                    fixture_id=fid,
                    latency_ms=lat_map[cid],
                    authoritative_usage_available=(cid != "C3"),
                    canonical_cost_usd=0.01 if cid != "C3" else None,
                )
            )
    res = select_winning_candidate_dev_select(
        cell_receipts=receipts,
        cost_comparability_by_candidate=incomp_records,
        dev_select_fixture_ids=fids,
    )
    assert res.cost_criterion_status == COST_CRITERION_SKIPPED_NOT_COMPARABLE


def test_dh_27_median_cost_tiebreak(verified_dev_bundle):
    """DH-27: Verify minimum unrounded canonical median cost tiebreak."""
    fids = verified_dev_bundle.dev_select_ids
    costs_map = {"C1": 0.015, "C2": 0.011, "C3": 0.025}
    receipts = [
        _make_synthetic_receipt(
            phase="DEV_SELECT",
            prompt_id="P1",
            candidate_id=cid,
            fixture_id=fid,
            latency_ms=2000.0,
            canonical_cost_usd=costs_map[cid],
        )
        for cid in ORDERED_CANDIDATE_IDS
        for fid in fids
    ]
    res = select_winning_candidate_dev_select(
        cell_receipts=receipts,
        cost_comparability_by_candidate=_make_all_comparable_cost_records(),
        dev_select_fixture_ids=fids,
    )
    assert res.selected_candidate_id == "C2"
    assert res.selected_at_stage == "MEDIAN_COST_PER_SCENARIO"
    assert res.cost_criterion_status == COST_CRITERION_APPLIED


def test_dh_28_median_latency_tiebreak(verified_dev_bundle):
    """DH-28: Verify minimum canonical median latency tiebreak."""
    fids = verified_dev_bundle.dev_select_ids
    lat_map = {"C1": 18000.0, "C2": 15000.0, "C3": 12000.0}
    receipts = [
        _make_synthetic_receipt(
            phase="DEV_SELECT",
            prompt_id="P1",
            candidate_id=cid,
            fixture_id=fid,
            latency_ms=lat_map[cid],
            canonical_cost_usd=0.015,
        )
        for cid in ORDERED_CANDIDATE_IDS
        for fid in fids
    ]
    res = select_winning_candidate_dev_select(
        cell_receipts=receipts,
        cost_comparability_by_candidate=_make_all_comparable_cost_records(),
        dev_select_fixture_ids=fids,
    )
    assert res.selected_candidate_id == "C3"
    assert res.selected_at_stage == "MEDIAN_LATENCY"


def test_dh_29_c1_gt_c2_gt_c3_final_administrative_tie(verified_dev_bundle):
    """DH-29: Verify C1 > C2 > C3 final administrative tiebreak."""
    fids = verified_dev_bundle.dev_select_ids
    receipts = [
        _make_synthetic_receipt(
            phase="DEV_SELECT",
            prompt_id="P1",
            candidate_id=cid,
            fixture_id=fid,
            latency_ms=15000.0,
            canonical_cost_usd=0.015,
        )
        for cid in ORDERED_CANDIDATE_IDS
        for fid in fids
    ]
    res = select_winning_candidate_dev_select(
        cell_receipts=receipts,
        cost_comparability_by_candidate=_make_all_comparable_cost_records(),
        dev_select_fixture_ids=fids,
    )
    assert res.selected_candidate_id == "C1"
    assert res.selected_at_stage == "FINAL_ADMINISTRATIVE_TIEBREAK_C1_GT_C2_GT_C3"
    assert res.is_administrative_tiebreak is True
    assert res.administrative_tiebreak_claims_scientific_superiority is False


def test_dh_30_no_weighted_composite():
    """DH-30: Verify DevGroupAggregateMetrics has no weighted composite field."""
    fields = set(DevGroupAggregateMetrics.model_fields.keys())
    forbidden_composite_names = {
        "composite_score",
        "weighted_score",
        "overall_score",
        "total_score",
        "combined_score",
    }
    assert fields.isdisjoint(forbidden_composite_names)


def test_dh_31_no_scientific_evaluator_on_final100():
    """DH-31: Verify evaluate_dev_cell_scenario rejects any final-100 scenario."""
    fake_final_scenario = BenchmarkScenarioInput(
        scenario_id="W06-S001",
        destination_slug="ha-noi",
        destination="Hà Nội",
        days=2,
        start_date="2026-11-02",
        end_date="2026-11-03",
        budget=2000000,
        currency="VND",
        travel_style="BUDGET",
        interests=["culture_history"],
        notes=None,
        allow_revisit_place_ids=False,
        fixture_label="W06_FINAL_BENCHMARK",
    )
    fake_manifest = BenchmarkRunManifest(
        run_id="run-s001",
        scenario_id="W06-S001",
        execution_timestamp_utc="2026-10-17T00:00:00Z",
        provider="C1",
        model_id="gemini-3.8-flash",
        expected_model_id="gemini-3.8-flash",
        generation_parameters={},
        execution_mode="OFFLINE",
        latency_ms=100.0,
        usage_metadata=BenchmarkUsageMetadata(),
        code_commit_sha="0" * 64,
        scenario_sha256="0" * 64,
        catalog_sha256="0" * 64,
        benchmark_prompt_version="P1",
        raw_response_sha256="0" * 64,
        run_status=BenchmarkRunStatus.API_ERROR,
        error_detail="API_ERROR",
    )
    with pytest.raises(Final100FirewallViolationError):
        evaluate_dev_cell_scenario(fake_final_scenario, None, fake_manifest)


def test_dh_32_stochasticity_gated_after_winner(default_prompt_registry):
    """DH-32: Verify stochasticity diagnostic cannot be planned before DEV-SELECT winner selection."""
    with pytest.raises(StochasticityGateViolationError):
        build_stochasticity_diagnostic_plan(
            dev_select_result=None,
            locked_prompt_spec=default_prompt_registry.prompts[0],
        )


def test_dh_33_stochasticity_exact_5_ids_x3_design(
    verified_dev_bundle, candidate_registry, default_prompt_registry
):
    """DH-33: Verify stochasticity diagnostic uses 5 lexicographically smallest DEV-TUNE IDs × 3 runs = 15 calls."""
    fids = verified_dev_bundle.dev_select_ids
    receipts = [
        _make_synthetic_receipt(
            phase="DEV_SELECT",
            prompt_id="P1",
            candidate_id=cid,
            fixture_id=fid,
            canonical_cost_usd=0.01 if cid == "C1" else 0.02,
        )
        for cid in ORDERED_CANDIDATE_IDS
        for fid in fids
    ]
    dev_select_res = select_winning_candidate_dev_select(
        cell_receipts=receipts,
        cost_comparability_by_candidate=_make_all_comparable_cost_records(),
        dev_select_fixture_ids=fids,
    )

    stoch_plan = build_stochasticity_diagnostic_plan(
        dev_select_result=dev_select_res,
        locked_prompt_spec=default_prompt_registry.prompts[0],
        dev_bundle=verified_dev_bundle,
        candidate_registry=candidate_registry,
    )
    assert stoch_plan.selected_candidate_id == "C1"
    assert stoch_plan.fixture_ids == list(EXPECTED_STOCHASTICITY_FIXTURE_IDS)
    assert len(stoch_plan.fixture_ids) == STOCHASTICITY_FIXTURE_COUNT == 5
    assert stoch_plan.executions_per_fixture == STOCHASTICITY_EXECUTIONS_PER_FIXTURE == 3
    assert stoch_plan.max_calls == STOCHASTICITY_MAX_CALLS == 15
    assert len(stoch_plan.cells) == 15
    assert stoch_plan.retry == 0
    assert stoch_plan.best_of_n is False
    assert stoch_plan.diagnostic_only is True


def test_dh_34_deterministic_plan_hashes(
    verified_dev_bundle, candidate_registry, default_prompt_registry
):
    """DH-34: Verify deterministic hashes across repeated invocations."""
    h1 = compute_harness_determinism_hashes(
        dev_bundle=verified_dev_bundle,
        candidate_registry=candidate_registry,
        prompt_registry=default_prompt_registry,
    )
    h2 = compute_harness_determinism_hashes(
        dev_bundle=verified_dev_bundle,
        candidate_registry=candidate_registry,
        prompt_registry=default_prompt_registry,
    )
    assert h1 == h2


def test_dh_35_secret_independent_offline_operation(monkeypatch):
    """DH-35: Verify harness operates completely offline without API keys and rejects live CLI flags."""
    for key_name in ("GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(key_name, raising=False)

    res_val = run_cli(["--offline-validate"])
    assert res_val["status"] == "PASS"
    assert res_val["receipt"]["live_provider_calls"] == 0

    res_tune = run_cli(["--plan-dev-tune"])
    assert res_tune["expected_total_cells"] == 60

    res_sel = run_cli(["--plan-dev-select"])
    assert res_sel["expected_total_cells"] == 180

    with pytest.raises(DevHarnessOfflineViolationError):
        run_cli(["--execute-live"])

    with pytest.raises(DevHarnessOfflineViolationError):
        run_cli(["--confirm-live"])


def test_mock_transport_execution_and_immutability(
    tmp_path, verified_dev_bundle, candidate_registry, default_prompt_registry
):
    """Section 23: Exercise mock provider responses (all-pass, schema failure, grounding failure, core failure, HTTP/timeout/refusal) and cell immutability."""
    scenario = verified_dev_bundle.dev_tune_fixtures[0]
    prompt_spec = default_prompt_registry.prompts[0]
    ctx = build_deterministic_dev_scenario_context(scenario, prompt_spec)
    cspec = candidate_registry.candidates["C1"]
    core_cat = load_core_catalog_by_place_id()
    cost_rec = _make_all_comparable_cost_records()["C1"]

    cell_manifest = DevCellExecutionManifest(
        run_id="MOCK-CELL-001",
        phase="DEV_TUNE",
        fixture_id=scenario.scenario_id,
        candidate_id="C1",
        prompt_id="P1",
        requested_model_id=cspec.requested_model_id,
        scenario_sha256=ctx.scenario_sha256,
        catalog_context_sha256=ctx.catalog_context_sha256,
        system_prompt_sha256=ctx.system_prompt_sha256,
        user_prompt_sha256=ctx.user_prompt_sha256,
        semantic_schema_sha256=ctx.semantic_schema_sha256,
        portable_generation_schema_v2_sha256=ctx.portable_generation_schema_v2_sha256,
        sampling_reasoning_configuration=cspec.sampling_reasoning_config,
    )

    valid_plan_dict = _build_valid_plan_dict_for_scenario(scenario)
    cell_dir_pass = tmp_path / "cell_pass"
    rec_pass, _ = execute_dev_cell_with_mock_transport(
        cell_manifest=cell_manifest,
        scenario=scenario,
        cell_dir=cell_dir_pass,
        mock_response=MockProviderTransportResponse(
            raw_text=json.dumps(valid_plan_dict, ensure_ascii=False),
        ),
        cost_comparability=cost_rec,
        core_catalog_by_id=core_cat,
    )
    assert rec_pass.valid_run_and_schema is True
    assert rec_pass.exact_grounding_pass is True
    assert rec_pass.final_core_pass is True
    assert (cell_dir_pass / "parsed_plan_response.json").exists()

    with pytest.raises(ImmutableCellExecutionError):
        execute_dev_cell_with_mock_transport(
            cell_manifest=cell_manifest,
            scenario=scenario,
            cell_dir=cell_dir_pass,
            mock_response=MockProviderTransportResponse(
                raw_text=json.dumps(valid_plan_dict, ensure_ascii=False),
            ),
            cost_comparability=cost_rec,
            core_catalog_by_id=core_cat,
        )

    cell_dir_bad_json = tmp_path / "cell_bad_json"
    rec_bad_json, _ = execute_dev_cell_with_mock_transport(
        cell_manifest=cell_manifest,
        scenario=scenario,
        cell_dir=cell_dir_bad_json,
        mock_response=MockProviderTransportResponse(raw_text="{not valid json"),
        cost_comparability=cost_rec,
        core_catalog_by_id=core_cat,
    )
    assert rec_bad_json.valid_run_and_schema is False
    assert rec_bad_json.exact_grounding_pass is False
    assert rec_bad_json.final_core_pass is False
    assert rec_bad_json.failure_classification == DevCellFailureClassification.MALFORMED_JSON
    assert not (cell_dir_bad_json / "parsed_plan_response.json").exists()

    ungrounded_plan = _build_valid_plan_dict_for_scenario(scenario)
    ungrounded_plan["days"][0]["items"][0]["place_id"] = "non-existent-place-id-999"
    cell_dir_ungrounded = tmp_path / "cell_ungrounded"
    rec_ungrounded, _ = execute_dev_cell_with_mock_transport(
        cell_manifest=cell_manifest,
        scenario=scenario,
        cell_dir=cell_dir_ungrounded,
        mock_response=MockProviderTransportResponse(
            raw_text=json.dumps(ungrounded_plan, ensure_ascii=False),
        ),
        cost_comparability=cost_rec,
        core_catalog_by_id=core_cat,
    )
    assert rec_ungrounded.valid_run_and_schema is True
    assert rec_ungrounded.exact_grounding_pass is False
    assert rec_ungrounded.final_core_pass is False

    core_fail_plan = _build_valid_plan_dict_for_scenario(scenario)
    core_fail_plan["days"][0]["items"][0]["start_time"] = "09:00"
    core_fail_plan["days"][0]["items"][0]["end_time"] = "11:00"
    core_fail_plan["days"][0]["items"][1]["start_time"] = "10:00"
    core_fail_plan["days"][0]["items"][1]["end_time"] = "12:00"
    cell_dir_core_fail = tmp_path / "cell_core_fail"
    rec_core_fail, _ = execute_dev_cell_with_mock_transport(
        cell_manifest=cell_manifest,
        scenario=scenario,
        cell_dir=cell_dir_core_fail,
        mock_response=MockProviderTransportResponse(
            raw_text=json.dumps(core_fail_plan, ensure_ascii=False),
        ),
        cost_comparability=cost_rec,
        core_catalog_by_id=core_cat,
    )
    assert rec_core_fail.valid_run_and_schema is True
    assert rec_core_fail.exact_grounding_pass is True
    assert rec_core_fail.final_core_pass is False
