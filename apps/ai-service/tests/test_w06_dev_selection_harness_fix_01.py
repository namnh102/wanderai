"""Regression test suite for W06 DEV Selection Harness Fix 01 (W06-DEV-SELECTION-HARNESS-FIX-01).

Covers all 35 required regression tests (FIX-01 through FIX-35) verifying the
repair of all 10 QA-01 defects (QA-05, QA-14, QA-15, QA-27, QA-28, QA-29,
QA-30, QA-32, QA-33, QA-39) and verifying strict immutability of historical
QA-01 evidence and frozen scientific authorities.

Zero live provider calls. Provider cost = $0.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
import inspect
import json
from pathlib import Path
import subprocess
from typing import Any, Dict, List

import pytest
from pydantic import ValidationError

from app.evaluation import dev_selection_harness as harness
from app.evaluation.dev_selection_harness import (
    BATCH_STOP_FAILURE_CLASSIFICATIONS,
    DECIMAL_SCIENTIFIC_PRECISION,
    CandidateCostComparabilityRecord,
    CodeCommitProvenanceError,
    DevCellExecutionManifest,
    DevCellExecutionReceipt,
    DevCellFailureClassification,
    Final100FirewallViolationError,
    FORBIDDEN_FINAL100_BUNDLE_SHA256,
    FORBIDDEN_P11_MANIFEST_SHA256,
    HarnessInternalBatchStopError,
    LatencyAuthorityUnavailableError,
    MockProviderTransportResponse,
    ModelIntegrityBatchStopError,
    ORDINARY_DENOMINATOR_FAILURE_CLASSIFICATIONS,
    ORDERED_CANDIDATE_IDS,
    PromptFreezeFirewallError,
    REPO_ROOT,
    SINGLE_PROMPT_P1_LOCK_STATUS,
    StochasticityGateViolationError,
    aggregate_dev_cell_receipts,
    assert_batch_receipts_integrity,
    assert_not_final100_path,
    assert_not_final100_scenario,
    assert_prompt_freeze_before_live,
    build_default_infrastructure_prompt_registry,
    build_dev_prompt_freeze_artifact,
    build_dev_select_execution_plan,
    build_dev_tune_execution_plan,
    build_prompt_registry,
    build_stochasticity_diagnostic_plan,
    compute_candidate_provider_config_sha256,
    compute_canonical_cell_cost_decimal,
    compute_canonical_cell_cost_decimal_str,
    compute_canonical_cell_cost_usd,
    compute_exact_decimal_median,
    create_prompt_candidate_spec,
    create_synthetic_test_only_cell_manifest,
    create_synthetic_test_only_cell_receipt,
    execute_dev_batch_with_mock_transport,
    execute_dev_cell_with_mock_transport,
    format_canonical_decimal_str,
    load_and_verify_candidate_registry,
    load_and_verify_frozen_dev_bundle,
    normalize_lf_bytes,
    parse_canonical_decimal_str,
    parse_primary_dev_plan_response,
    reduce_survivors_by_10pp_rule,
    resolve_active_git_commit_sha,
    resolve_and_verify_code_commit_sha,
    select_winning_candidate_dev_select,
    select_winning_prompt_dev_tune,
    sha256_bytes,
    verify_frozen_authorities_dev_harness,
    verify_prompt_candidate_freeze_artifact,
)
from app.evaluation.planner_benchmark_evaluator import load_core_catalog_by_place_id
from app.prompts.planner_benchmark_prompt import build_destination_catalog_context
from app.schemas.planner_benchmark import BenchmarkScenarioInput


HISTORICAL_QA01_IMMUTABLE_FILES = (
    "data/evaluation/w06/w06_dev_selection_harness_qa_01_receipt_v1.json",
    "docs/research/w06_dev_selection_harness_qa_01.md",
    "scripts/audit_w06_dev_selection_harness.py",
    "apps/ai-service/tests/test_w06_dev_selection_harness_qa_01.py",
)


@pytest.fixture(scope="module")
def shared_env() -> Dict[str, Any]:
    """Load frozen bundle, catalog, prompt registry, and sample cell once per module."""
    bundle = load_and_verify_frozen_dev_bundle()
    cand_reg = load_and_verify_candidate_registry()
    scen0 = bundle.dev_tune_fixtures[0]
    cat0 = build_destination_catalog_context(scen0.destination_slug)
    core_map = load_core_catalog_by_place_id()
    p1_reg = build_default_infrastructure_prompt_registry()
    tune_plan = build_dev_tune_execution_plan(
        p1_reg,
        dev_bundle=bundle,
        candidate_registry=cand_reg,
    )
    cell0 = tune_plan.cells[0]
    return {
        "bundle": bundle,
        "cand_reg": cand_reg,
        "scen0": scen0,
        "cat0": cat0,
        "core_map": core_map,
        "p1_reg": p1_reg,
        "tune_plan": tune_plan,
        "cell0": cell0,
    }


def _build_complete_valid_plan_dict(
    scenario: BenchmarkScenarioInput,
    catalog_pois: List[Any],
) -> Dict[str, Any]:
    neutral_pois = [p for p in catalog_pois if p.opening_hours is None]
    pool = neutral_pois if len(neutral_pois) >= scenario.days * 2 else catalog_pois
    start_dt = dt.date.fromisoformat(scenario.start_date)
    days_list: List[Dict[str, Any]] = []
    idx = 0
    for d_idx in range(scenario.days):
        day_date = (start_dt + dt.timedelta(days=d_idx)).isoformat()
        p1 = pool[idx % len(pool)]
        p2 = pool[(idx + 1) % len(pool)]
        idx += 2
        days_list.append(
            {
                "day_number": d_idx + 1,
                "date": day_date,
                "title": f"Day {d_idx + 1}",
                "day_cost": 100000,
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
    total_est = 100000 * scenario.days
    is_over = False if scenario.budget is None else (total_est > scenario.budget)
    variance = 0 if scenario.budget is None else (scenario.budget - total_est)
    return {
        "plan_id": f"plan-fix-{scenario.scenario_id.lower()}",
        "scenario_id": scenario.scenario_id,
        "destination": scenario.destination,
        "destination_slug": scenario.destination_slug,
        "total_days": scenario.days,
        "overview": "Deterministic valid itinerary.",
        "best_time_to_visit": "All year",
        "general_tips": ["Tip 1"],
        "days": days_list,
        "budget_analysis": {
            "total_budget": scenario.budget,
            "estimated_cost": total_est,
            "currency": scenario.currency,
            "is_over_budget": is_over,
            "variance": variance,
        },
    }


_UNSET = object()


def _make_receipt(
    *,
    phase: str = "DEV_TUNE",
    prompt_id: str = "P1",
    candidate_id: str = "C1",
    fixture_id: str = "W06-DEV-TUNE-001",
    valid_run_and_schema: bool = True,
    exact_grounding_pass: bool = True,
    final_core_pass: bool = True,
    failure_classification: DevCellFailureClassification = DevCellFailureClassification.NONE,
    counts_in_denominator: bool = True,
    batch_stop_required: bool = False,
    latency_ms: float = 100.0,
    latency_ns: Any = _UNSET,
    canonical_cost_usd: float | None = 0.001,
    canonical_cost_usd_decimal: Any = _UNSET,
    authoritative_usage_available: bool = True,
    requested_model_id: str = "gemini-3.8-flash",
    returned_model_id: str | None = "gemini-3.8-flash",
    code_commit_sha: str | None = None,
) -> DevCellExecutionReceipt:
    resolved_latency_ns: int | None = (
        int(Decimal(str(latency_ms)) * Decimal(1_000_000))
        if latency_ns is _UNSET
        else latency_ns
    )
    if canonical_cost_usd_decimal is not _UNSET:
        resolved_cost_dec_str: str | None = canonical_cost_usd_decimal
    elif authoritative_usage_available and canonical_cost_usd is not None:
        resolved_cost_dec_str = format_canonical_decimal_str(Decimal(str(canonical_cost_usd)))
    else:
        resolved_cost_dec_str = None

    return DevCellExecutionReceipt(
        run_id=f"{phase}__{prompt_id}__{candidate_id}__{fixture_id}",
        phase=phase,  # type: ignore[arg-type]
        prompt_id=prompt_id,
        candidate_id=candidate_id,
        fixture_id=fixture_id,
        code_commit_sha=code_commit_sha or resolve_active_git_commit_sha(),
        requested_model_id=requested_model_id,
        returned_model_id=returned_model_id,
        latency_ns=resolved_latency_ns,
        latency_ms_display=latency_ms,
        latency_ms=latency_ms,
        input_tokens=500,
        output_tokens=600,
        thought_tokens=100 if candidate_id == "C1" else 0,
        reasoning_tokens=100 if candidate_id == "C2" else 0,
        thinking_tokens=100 if candidate_id == "C3" else 0,
        cached_input_tokens=0,
        cache_read_input_tokens=0,
        cache_creation_input_tokens=0,
        total_tokens=1200 if candidate_id == "C1" else 1100,
        authoritative_usage_available=authoritative_usage_available,
        raw_usage_metadata={"prompt_token_count": 500},
        canonical_cost_usd_decimal=resolved_cost_dec_str,
        canonical_cost_usd_display=canonical_cost_usd,
        canonical_cost_usd=canonical_cost_usd,
        valid_run_and_schema=valid_run_and_schema,
        exact_grounding_pass=exact_grounding_pass if valid_run_and_schema else False,
        final_core_pass=final_core_pass if (valid_run_and_schema and exact_grounding_pass) else False,
        failure_classification=failure_classification,
        counts_in_denominator=counts_in_denominator,
        batch_stop_required=batch_stop_required,
        request_manifest_sha256="a" * 64,
        raw_response_sha256="b" * 64,
        provider_metadata_sha256="c" * 64,
        parsed_response_sha256="d" * 64 if valid_run_and_schema else None,
        evaluation_result_sha256="e" * 64,
    )


def _cost_records_all_computable() -> Dict[str, CandidateCostComparabilityRecord]:
    return {
        cid: CandidateCostComparabilityRecord(
            candidate_id=cid,
            authoritative_usage_available=True,
            pricing_source="https://official.example/pricing",
            pricing_access_date="2026-10-18",
            input_price_per_million_usd=0.5 if cid == "C1" else (1.0 if cid == "C2" else 2.0),
            output_price_per_million_usd=2.0 if cid == "C1" else (4.0 if cid == "C2" else 8.0),
            canonical_cost_computable=True,
        )
        for cid in ORDERED_CANDIDATE_IDS
    }


# ==============================================================================
# FIX-01 through FIX-07: Fix Group A (QA-14 Strict Unrescued Primary Parsing)
# ==============================================================================


def test_fix_01_missing_plan_id_fails_valid_run_and_schema(shared_env, tmp_path: Path):
    """FIX-01: Missing plan_id fails VALID_RUN_AND_SCHEMA_RATE without rescue."""
    payload = _build_complete_valid_plan_dict(shared_env["scen0"], shared_env["cat0"])
    del payload["plan_id"]
    rec, eval_res = execute_dev_cell_with_mock_transport(
        cell_manifest=shared_env["cell0"],
        scenario=shared_env["scen0"],
        cell_dir=tmp_path / "fix_01",
        mock_response=MockProviderTransportResponse(
            returned_model_id=shared_env["cell0"].requested_model_id,
            raw_text=json.dumps(payload, ensure_ascii=False),
        ),
        core_catalog_by_id=shared_env["core_map"],
    )
    assert rec.valid_run_and_schema is False
    assert rec.exact_grounding_pass is False
    assert rec.final_core_pass is False
    assert rec.failure_classification == DevCellFailureClassification.SEMANTIC_VALIDATION_FAILURE
    assert rec.counts_in_denominator is True
    assert eval_res.run_valid is False


def test_fix_02_missing_budget_analysis_fails_valid_run_and_schema(shared_env, tmp_path: Path):
    """FIX-02: Missing budget_analysis fails VALID_RUN_AND_SCHEMA_RATE without rescue."""
    payload = _build_complete_valid_plan_dict(shared_env["scen0"], shared_env["cat0"])
    del payload["budget_analysis"]
    rec, eval_res = execute_dev_cell_with_mock_transport(
        cell_manifest=shared_env["cell0"],
        scenario=shared_env["scen0"],
        cell_dir=tmp_path / "fix_02",
        mock_response=MockProviderTransportResponse(
            returned_model_id=shared_env["cell0"].requested_model_id,
            raw_text=json.dumps(payload, ensure_ascii=False),
        ),
        core_catalog_by_id=shared_env["core_map"],
    )
    assert rec.valid_run_and_schema is False
    assert rec.failure_classification == DevCellFailureClassification.SEMANTIC_VALIDATION_FAILURE
    assert eval_res.run_valid is False


def test_fix_03_missing_scenario_id_fails_valid_run_and_schema(shared_env, tmp_path: Path):
    """FIX-03: Missing scenario_id fails VALID_RUN_AND_SCHEMA_RATE without rescue."""
    payload = _build_complete_valid_plan_dict(shared_env["scen0"], shared_env["cat0"])
    del payload["scenario_id"]
    rec, _ = execute_dev_cell_with_mock_transport(
        cell_manifest=shared_env["cell0"],
        scenario=shared_env["scen0"],
        cell_dir=tmp_path / "fix_03",
        mock_response=MockProviderTransportResponse(
            returned_model_id=shared_env["cell0"].requested_model_id,
            raw_text=json.dumps(payload, ensure_ascii=False),
        ),
        core_catalog_by_id=shared_env["core_map"],
    )
    assert rec.valid_run_and_schema is False
    assert rec.failure_classification == DevCellFailureClassification.SEMANTIC_VALIDATION_FAILURE


def test_fix_04_missing_destination_slug_fails_valid_run_and_schema(shared_env, tmp_path: Path):
    """FIX-04: Missing destination_slug fails VALID_RUN_AND_SCHEMA_RATE without rescue."""
    payload = _build_complete_valid_plan_dict(shared_env["scen0"], shared_env["cat0"])
    del payload["destination_slug"]
    rec, _ = execute_dev_cell_with_mock_transport(
        cell_manifest=shared_env["cell0"],
        scenario=shared_env["scen0"],
        cell_dir=tmp_path / "fix_04",
        mock_response=MockProviderTransportResponse(
            returned_model_id=shared_env["cell0"].requested_model_id,
            raw_text=json.dumps(payload, ensure_ascii=False),
        ),
        core_catalog_by_id=shared_env["core_map"],
    )
    assert rec.valid_run_and_schema is False
    assert rec.failure_classification == DevCellFailureClassification.SEMANTIC_VALIDATION_FAILURE


def test_fix_05_missing_day_cost_fails_valid_run_and_schema(shared_env, tmp_path: Path):
    """FIX-05: Missing day_cost fails VALID_RUN_AND_SCHEMA_RATE without rescue."""
    payload = _build_complete_valid_plan_dict(shared_env["scen0"], shared_env["cat0"])
    del payload["days"][0]["day_cost"]
    rec, _ = execute_dev_cell_with_mock_transport(
        cell_manifest=shared_env["cell0"],
        scenario=shared_env["scen0"],
        cell_dir=tmp_path / "fix_05",
        mock_response=MockProviderTransportResponse(
            returned_model_id=shared_env["cell0"].requested_model_id,
            raw_text=json.dumps(payload, ensure_ascii=False),
        ),
        core_catalog_by_id=shared_env["core_map"],
    )
    assert rec.valid_run_and_schema is False
    assert rec.failure_classification == DevCellFailureClassification.SEMANTIC_VALIDATION_FAILURE


def test_fix_06_parser_does_not_call_rescue_or_synthesis(shared_env):
    """FIX-06: Primary DEV parser does not import or call parse_strict_benchmark_plan_response."""
    assert "parse_strict_benchmark_plan_response" not in getattr(harness, "__dict__", {})
    exec_src = inspect.getsource(execute_dev_cell_with_mock_transport)
    assert "parse_strict_benchmark_plan_response" not in exec_src
    assert "parse_primary_dev_plan_response" in exec_src

    incomplete = _build_complete_valid_plan_dict(shared_env["scen0"], shared_env["cat0"])
    del incomplete["plan_id"]
    parsed_plan, fclass, _ = parse_primary_dev_plan_response(
        json.dumps(incomplete, ensure_ascii=False)
    )
    assert parsed_plan is None
    assert fclass == DevCellFailureClassification.SEMANTIC_VALIDATION_FAILURE


def test_fix_07_complete_valid_plan_passes_valid_run_and_schema(shared_env, tmp_path: Path):
    """FIX-07: Complete valid BenchmarkPlanResponse passes VALID_RUN_AND_SCHEMA_RATE."""
    payload = _build_complete_valid_plan_dict(shared_env["scen0"], shared_env["cat0"])
    rec, eval_res = execute_dev_cell_with_mock_transport(
        cell_manifest=shared_env["cell0"],
        scenario=shared_env["scen0"],
        cell_dir=tmp_path / "fix_07",
        mock_response=MockProviderTransportResponse(
            returned_model_id=shared_env["cell0"].requested_model_id,
            raw_text=json.dumps(payload, ensure_ascii=False),
        ),
        core_catalog_by_id=shared_env["core_map"],
    )
    assert rec.valid_run_and_schema is True
    assert rec.exact_grounding_pass is True
    assert rec.final_core_pass is True
    assert rec.failure_classification == DevCellFailureClassification.NONE
    assert eval_res.run_valid is True


# ==============================================================================
# FIX-08 through FIX-15: Fix Group B & C (QA-15 & QA-39 Model Integrity & Taxonomy)
# ==============================================================================


def test_fix_08_returned_model_id_mismatch_records_and_stops_batch(shared_env, tmp_path: Path):
    """FIX-08: returned_model_id mismatch records MODEL_INTEGRITY_MISMATCH and halts batch."""
    payload = _build_complete_valid_plan_dict(shared_env["scen0"], shared_env["cat0"])
    rec, _ = execute_dev_cell_with_mock_transport(
        cell_manifest=shared_env["cell0"],
        scenario=shared_env["scen0"],
        cell_dir=tmp_path / "fix_08_cell",
        mock_response=MockProviderTransportResponse(
            returned_model_id="gpt-4o-mini-unexpected",
            raw_text=json.dumps(payload, ensure_ascii=False),
        ),
        core_catalog_by_id=shared_env["core_map"],
    )
    assert rec.failure_classification == DevCellFailureClassification.MODEL_INTEGRITY_MISMATCH
    assert rec.valid_run_and_schema is False
    assert rec.counts_in_denominator is False
    assert rec.batch_stop_required is True

    # Also verify execute_dev_batch_with_mock_transport halts immediately on first mismatch
    cells = shared_env["tune_plan"].cells
    scenarios_by_id = {s.scenario_id: s for s in shared_env["bundle"].dev_tune_fixtures}
    responses = {
        cells[0].run_id: MockProviderTransportResponse(
            returned_model_id="wrong-model-v1",
            raw_text=json.dumps(payload, ensure_ascii=False),
        ),
        cells[1].run_id: MockProviderTransportResponse(
            returned_model_id=cells[1].requested_model_id,
            raw_text=json.dumps(payload, ensure_ascii=False),
        ),
    }
    with pytest.raises(ModelIntegrityBatchStopError):
        execute_dev_batch_with_mock_transport(
            execution_plan=shared_env["tune_plan"],
            scenarios_by_id=scenarios_by_id,
            batch_root_dir=tmp_path / "fix_08_batch",
            mock_response_by_run_id=responses,
            core_catalog_by_id=shared_env["core_map"],
        )
    # Cell 1 must not have been executed after Cell 0 triggered batch stop
    assert (tmp_path / "fix_08_batch" / cells[0].run_id / "execution_receipt.json").exists()
    assert not (tmp_path / "fix_08_batch" / cells[1].run_id).exists()


def test_fix_09_missing_returned_model_id_not_substituted_with_requested(shared_env, tmp_path: Path):
    """FIX-09: Missing or empty returned_model_id is NOT substituted with requested_model_id."""
    payload = _build_complete_valid_plan_dict(shared_env["scen0"], shared_env["cat0"])
    rec_none, _ = execute_dev_cell_with_mock_transport(
        cell_manifest=shared_env["cell0"],
        scenario=shared_env["scen0"],
        cell_dir=tmp_path / "fix_09_none",
        mock_response=MockProviderTransportResponse(
            returned_model_id=None,
            raw_text=json.dumps(payload, ensure_ascii=False),
        ),
        core_catalog_by_id=shared_env["core_map"],
    )
    assert rec_none.returned_model_id is None
    assert rec_none.returned_model_id != shared_env["cell0"].requested_model_id
    assert rec_none.failure_classification == DevCellFailureClassification.MODEL_INTEGRITY_MISMATCH
    assert rec_none.counts_in_denominator is False
    assert rec_none.batch_stop_required is True

    rec_empty, _ = execute_dev_cell_with_mock_transport(
        cell_manifest=shared_env["cell0"],
        scenario=shared_env["scen0"],
        cell_dir=tmp_path / "fix_09_empty",
        mock_response=MockProviderTransportResponse(
            returned_model_id="   ",
            raw_text=json.dumps(payload, ensure_ascii=False),
        ),
        core_catalog_by_id=shared_env["core_map"],
    )
    assert rec_empty.returned_model_id != shared_env["cell0"].requested_model_id
    assert rec_empty.failure_classification == DevCellFailureClassification.MODEL_INTEGRITY_MISMATCH
    assert rec_empty.counts_in_denominator is False
    assert rec_empty.batch_stop_required is True


def test_fix_10_model_integrity_mismatch_sets_denominator_false_and_batch_stop_true():
    """FIX-10: MODEL_INTEGRITY_MISMATCH sets counts_in_denominator=False and batch_stop_required=True."""
    rec = _make_receipt(
        valid_run_and_schema=False,
        exact_grounding_pass=False,
        final_core_pass=False,
        failure_classification=DevCellFailureClassification.MODEL_INTEGRITY_MISMATCH,
        counts_in_denominator=False,
        batch_stop_required=True,
        returned_model_id="unexpected-model",
    )
    assert rec.counts_in_denominator is False
    assert rec.batch_stop_required is True

    # Attempting to construct MODEL_INTEGRITY_MISMATCH with counts_in_denominator=True must fail validation
    with pytest.raises(ValidationError):
        _make_receipt(
            valid_run_and_schema=False,
            failure_classification=DevCellFailureClassification.MODEL_INTEGRITY_MISMATCH,
            counts_in_denominator=True,
            batch_stop_required=True,
            returned_model_id="unexpected-model",
        )


def test_fix_11_aggregate_rejects_model_integrity_mismatch():
    """FIX-11: aggregate_dev_cell_receipts rejects any receipt with MODEL_INTEGRITY_MISMATCH."""
    bad_rec = _make_receipt(
        valid_run_and_schema=False,
        failure_classification=DevCellFailureClassification.MODEL_INTEGRITY_MISMATCH,
        counts_in_denominator=False,
        batch_stop_required=True,
        returned_model_id="wrong-model",
    )
    with pytest.raises(ModelIntegrityBatchStopError):
        aggregate_dev_cell_receipts(
            group_id="C1",
            assigned_cell_keys=[("P1", "C1", "W06-DEV-TUNE-001")],
            cell_receipts=[bad_rec],
            cost_comparability_all_computable=False,
        )


def test_fix_12_select_winning_prompt_dev_tune_rejects_model_integrity_mismatch(shared_env):
    """FIX-12: select_winning_prompt_dev_tune rejects MODEL_INTEGRITY_MISMATCH before any ranking."""
    fids = [s.scenario_id for s in shared_env["bundle"].dev_tune_fixtures]
    receipts: List[DevCellExecutionReceipt] = []
    for cid in ORDERED_CANDIDATE_IDS:
        for fid in fids:
            if cid == "C2" and fid == fids[0]:
                receipts.append(
                    _make_receipt(
                        prompt_id="P1",
                        candidate_id=cid,
                        fixture_id=fid,
                        valid_run_and_schema=False,
                        failure_classification=DevCellFailureClassification.MODEL_INTEGRITY_MISMATCH,
                        counts_in_denominator=False,
                        batch_stop_required=True,
                        requested_model_id="gpt-6.1-sol",
                        returned_model_id="gpt-4o-wrong",
                    )
                )
            else:
                receipts.append(_make_receipt(prompt_id="P1", candidate_id=cid, fixture_id=fid))

    with pytest.raises(ModelIntegrityBatchStopError):
        select_winning_prompt_dev_tune(
            prompt_registry=shared_env["p1_reg"],
            dev_tune_fixture_ids=fids,
            cell_receipts=receipts,
        )


def test_fix_13_select_winning_candidate_dev_select_rejects_model_integrity_mismatch(shared_env):
    """FIX-13: select_winning_candidate_dev_select rejects MODEL_INTEGRITY_MISMATCH before any ranking."""
    fids = [s.scenario_id for s in shared_env["bundle"].dev_select_fixtures]
    receipts: List[DevCellExecutionReceipt] = []
    for cid in ORDERED_CANDIDATE_IDS:
        for fid in fids:
            if cid == "C3" and fid == fids[0]:
                receipts.append(
                    _make_receipt(
                        phase="DEV_SELECT",
                        prompt_id="P1",
                        candidate_id=cid,
                        fixture_id=fid,
                        valid_run_and_schema=False,
                        failure_classification=DevCellFailureClassification.MODEL_INTEGRITY_MISMATCH,
                        counts_in_denominator=False,
                        batch_stop_required=True,
                        requested_model_id="claude-sonnet-5-5",
                        returned_model_id="claude-3-haiku-wrong",
                    )
                )
            else:
                receipts.append(
                    _make_receipt(
                        phase="DEV_SELECT",
                        prompt_id="P1",
                        candidate_id=cid,
                        fixture_id=fid,
                    )
                )

    with pytest.raises(ModelIntegrityBatchStopError):
        select_winning_candidate_dev_select(
            locked_prompt_id="P1",
            dev_select_fixture_ids=fids,
            cell_receipts=receipts,
            cost_comparability_by_candidate=_cost_records_all_computable(),
        )


def test_fix_14_harness_internal_error_stops_batch_and_blocks_aggregation(shared_env, tmp_path: Path):
    """FIX-14: HARNESS_INTERNAL_ERROR exists in taxonomy and stops batch / raises HarnessInternalBatchStopError."""
    assert DevCellFailureClassification.HARNESS_INTERNAL_ERROR in BATCH_STOP_FAILURE_CLASSIFICATIONS
    rec, _ = execute_dev_cell_with_mock_transport(
        cell_manifest=shared_env["cell0"],
        scenario=shared_env["scen0"],
        cell_dir=tmp_path / "fix_14_cell",
        mock_response=MockProviderTransportResponse(
            returned_model_id=shared_env["cell0"].requested_model_id,
            simulated_failure=DevCellFailureClassification.HARNESS_INTERNAL_ERROR,
        ),
        core_catalog_by_id=shared_env["core_map"],
    )
    assert rec.failure_classification == DevCellFailureClassification.HARNESS_INTERNAL_ERROR
    assert rec.counts_in_denominator is False
    assert rec.batch_stop_required is True

    with pytest.raises(HarnessInternalBatchStopError):
        assert_batch_receipts_integrity([rec])
    with pytest.raises(HarnessInternalBatchStopError):
        aggregate_dev_cell_receipts(
            group_id="C1",
            assigned_cell_keys=[("P1", "C1", shared_env["scen0"].scenario_id)],
            cell_receipts=[rec],
            cost_comparability_all_computable=False,
        )


def test_fix_15_partial_timeout_preserves_denominator(shared_env, tmp_path: Path):
    """FIX-15: PARTIAL_TIMEOUT exists in taxonomy, counts in denominator, and does not stop batch."""
    assert DevCellFailureClassification.PARTIAL_TIMEOUT in ORDINARY_DENOMINATOR_FAILURE_CLASSIFICATIONS
    rec, _ = execute_dev_cell_with_mock_transport(
        cell_manifest=shared_env["cell0"],
        scenario=shared_env["scen0"],
        cell_dir=tmp_path / "fix_15_cell",
        mock_response=MockProviderTransportResponse(
            returned_model_id=shared_env["cell0"].requested_model_id,
            simulated_failure=DevCellFailureClassification.PARTIAL_TIMEOUT,
            raw_text='{"plan_id": "truncated',
        ),
        core_catalog_by_id=shared_env["core_map"],
    )
    assert rec.failure_classification == DevCellFailureClassification.PARTIAL_TIMEOUT
    assert rec.counts_in_denominator is True
    assert rec.batch_stop_required is False
    assert rec.valid_run_and_schema is False

    agg = aggregate_dev_cell_receipts(
        group_id="C1",
        assigned_cell_keys=[
            (
                shared_env["cell0"].prompt_id,
                shared_env["cell0"].candidate_id,
                shared_env["scen0"].scenario_id,
            )
        ],
        cell_receipts=[rec],
        cost_comparability_all_computable=False,
    )
    assert agg.n_assigned == 1
    assert agg.n_attempted == 1
    assert agg.n_valid_schema == 0
    assert agg.failure_classification_counts["PARTIAL_TIMEOUT"] == 1


# ==============================================================================
# FIX-16 through FIX-19: Fix Group D (QA-05 Content-Addressed Final100 Firewall)
# ==============================================================================


def test_fix_16_copied_final100_file_with_different_name_fails_firewall(tmp_path: Path):
    """FIX-16: Copied final100 file under an alias filename fails assert_not_final100_path by SHA256."""
    src = REPO_ROOT / "data" / "evaluation" / "w06" / "w06_scenarios_freeze_v1.json"
    copied = tmp_path / "innocent_looking_bundle.json"
    copied.write_bytes(src.read_bytes())
    assert sha256_bytes(normalize_lf_bytes(copied.read_bytes())) == FORBIDDEN_FINAL100_BUNDLE_SHA256
    with pytest.raises(Final100FirewallViolationError, match="SHA256"):
        assert_not_final100_path(copied)


def test_fix_17_copied_p11_manifest_with_different_name_fails_firewall(tmp_path: Path):
    """FIX-17: Copied P11 assignment manifest under an alias filename fails assert_not_final100_path by SHA256."""
    src = REPO_ROOT / "data" / "evaluation" / "w06" / "w06_p11_assignment_manifest_v1.json"
    copied = tmp_path / "copied_p11_alias.json"
    copied.write_bytes(src.read_bytes())
    assert sha256_bytes(normalize_lf_bytes(copied.read_bytes())) == FORBIDDEN_P11_MANIFEST_SHA256
    with pytest.raises(Final100FirewallViolationError, match="SHA256"):
        assert_not_final100_path(copied)


def test_fix_18_dev_tune_id_with_dev_select_label_fails_firewall():
    """FIX-18: W06-DEV-TUNE-001 paired with W06_DEV_SELECT label fails assert_not_final100_scenario."""
    with pytest.raises(Final100FirewallViolationError, match="Cross-partition"):
        assert_not_final100_scenario(
            {"scenario_id": "W06-DEV-TUNE-001", "fixture_label": "W06_DEV_SELECT"}
        )


def test_fix_19_dev_select_id_with_dev_tune_label_fails_firewall():
    """FIX-19: W06-DEV-SELECT-001 paired with W06_DEV_TUNE label fails assert_not_final100_scenario."""
    with pytest.raises(Final100FirewallViolationError, match="Cross-partition"):
        assert_not_final100_scenario(
            {"scenario_id": "W06-DEV-SELECT-001", "fixture_label": "W06_DEV_TUNE"}
        )


# ==============================================================================
# FIX-20 through FIX-23: Fix Group E (QA-27 & QA-28 Provider-Aware Token Billing)
# ==============================================================================


def test_fix_20_c1_gemini_cost_includes_thought_tokens_once():
    """FIX-20: C1 (gemini-3.8-flash) cost adds disjoint thought_tokens to output_tokens once."""
    c1_rec = _cost_records_all_computable()["C1"]  # input=$0.50/1M, output=$2.00/1M
    # input=514, output=599, thought=3179 -> billable_output = 599 + 3179 = 3778
    cost_dec = compute_canonical_cell_cost_decimal(
        cost_record=c1_rec,
        input_tokens=514,
        output_tokens=599,
        thought_tokens=3179,
    )
    expected = (Decimal(514) * Decimal("0.5") + Decimal(599 + 3179) * Decimal("2.0")) / Decimal(1_000_000)
    assert cost_dec == expected


def test_fix_21_c2_openai_cost_does_not_double_count_reasoning_tokens():
    """FIX-21: C2 (gpt-6.1-sol) cost does NOT add reasoning_tokens on top of output_tokens."""
    c2_rec = _cost_records_all_computable()["C2"]  # input=$1.00/1M, output=$4.00/1M
    # input=577, output=1030, reasoning=435 (already inside 1030) -> billable_output = 1030
    cost_with_reasoning = compute_canonical_cell_cost_decimal(
        cost_record=c2_rec,
        input_tokens=577,
        output_tokens=1030,
        reasoning_tokens=435,
    )
    cost_without_reasoning = compute_canonical_cell_cost_decimal(
        cost_record=c2_rec,
        input_tokens=577,
        output_tokens=1030,
        reasoning_tokens=0,
    )
    expected = (Decimal(577) * Decimal("1.0") + Decimal(1030) * Decimal("4.0")) / Decimal(1_000_000)
    assert cost_with_reasoning == expected
    assert cost_with_reasoning == cost_without_reasoning


def test_fix_22_c3_anthropic_cost_does_not_double_count_thinking_tokens():
    """FIX-22: C3 (claude-sonnet-5-5) cost does NOT add thinking_tokens on top of output_tokens."""
    c3_rec = _cost_records_all_computable()["C3"]  # input=$2.00/1M, output=$8.00/1M
    cost_with_thinking = compute_canonical_cell_cost_decimal(
        cost_record=c3_rec,
        input_tokens=877,
        output_tokens=809,
        thinking_tokens=250,
    )
    expected = (Decimal(877) * Decimal("2.0") + Decimal(809) * Decimal("8.0")) / Decimal(1_000_000)
    assert cost_with_thinking == expected


def test_fix_23_nonzero_unsupported_cache_tokens_disable_cost_comparability(shared_env, tmp_path: Path):
    """FIX-23: Nonzero unsupported cache tokens disable canonical cost comparability."""
    c1_rec = _cost_records_all_computable()["C1"]
    assert (
        compute_canonical_cell_cost_usd(
            cost_record=c1_rec,
            input_tokens=500,
            output_tokens=600,
            cached_input_tokens=128,
        )
        is None
    )
    assert (
        compute_canonical_cell_cost_usd(
            cost_record=c1_rec,
            input_tokens=500,
            output_tokens=600,
            cache_read_input_tokens=64,
        )
        is None
    )
    assert (
        compute_canonical_cell_cost_usd(
            cost_record=c1_rec,
            input_tokens=500,
            output_tokens=600,
            cache_creation_input_tokens=32,
        )
        is None
    )

    payload = _build_complete_valid_plan_dict(shared_env["scen0"], shared_env["cat0"])
    rec, _ = execute_dev_cell_with_mock_transport(
        cell_manifest=shared_env["cell0"],
        scenario=shared_env["scen0"],
        cell_dir=tmp_path / "fix_23_cache",
        mock_response=MockProviderTransportResponse(
            returned_model_id=shared_env["cell0"].requested_model_id,
            raw_text=json.dumps(payload, ensure_ascii=False),
            input_tokens=500,
            output_tokens=600,
            thought_tokens=100,
            cached_input_tokens=200,
            total_tokens=1200,
            authoritative_usage_available=True,
        ),
        cost_comparability=c1_rec,
        core_catalog_by_id=shared_env["core_map"],
    )
    assert rec.canonical_cost_usd is None
    assert rec.cached_input_tokens == 200


# ==============================================================================
# FIX-24 & FIX-25: Fix Group F & G (QA-29 & QA-30 Unrounded Cost & Latency Tiebreak)
# ==============================================================================


def test_fix_24_cost_tiebreak_distinguishes_sub_12_decimal_differences(shared_env):
    """FIX-24: Cost tiebreak distinguishes 0.0100000000001 vs 0.0100000000002 without 12-decimal truncation."""
    assert harness._to_exact_decimal(0.0100000000001) != harness._to_exact_decimal(0.0100000000002)
    assert harness._to_exact_decimal("0.0100000000001") == Decimal("0.0100000000001")
    assert harness._to_exact_decimal("0.0100000000002") == Decimal("0.0100000000002")

    fids = [s.scenario_id for s in shared_env["bundle"].dev_select_fixtures]
    costs = {"C1": "0.0100000000002", "C2": "0.0100000000001", "C3": "0.0100000000003"}
    req_models = {"C1": "gemini-3.8-flash", "C2": "gpt-6.1-sol", "C3": "claude-sonnet-5-5"}
    receipts = [
        _make_receipt(
            phase="DEV_SELECT",
            prompt_id="P1",
            candidate_id=cid,
            fixture_id=fid,
            canonical_cost_usd=float(costs[cid]),
            canonical_cost_usd_decimal=costs[cid],
            latency_ms=100.0,
            requested_model_id=req_models[cid],
            returned_model_id=req_models[cid],
        )
        for cid in ORDERED_CANDIDATE_IDS
        for fid in fids
    ]
    res = select_winning_candidate_dev_select(
        locked_prompt_id="P1",
        dev_select_fixture_ids=fids,
        cell_receipts=receipts,
        cost_comparability_by_candidate=_cost_records_all_computable(),
    )
    assert res.selected_candidate_id == "C2"
    assert res.selected_at_stage == "MEDIAN_COST_PER_SCENARIO"
    assert res.is_administrative_tiebreak is False


def test_fix_25_latency_tiebreak_distinguishes_sub_12_decimal_differences(shared_env):
    """FIX-25: Latency tiebreak distinguishes sub-12-decimal differences via authoritative integer latency_ns."""
    assert harness._to_exact_decimal(100.0000000000001) != harness._to_exact_decimal(100.0000000000002)
    assert harness._to_exact_decimal(1.0000000000001) != harness._to_exact_decimal(1.0000000000002)

    fids = [s.scenario_id for s in shared_env["bundle"].dev_select_fixtures]
    lats_ms = {"C1": 1.0000000000002, "C2": 1.0000000000003, "C3": 1.0000000000001}
    lats_ns = {
        "C1": 1_000_000_000_002,
        "C2": 1_000_000_000_003,
        "C3": 1_000_000_000_001,
    }
    req_models = {"C1": "gemini-3.8-flash", "C2": "gpt-6.1-sol", "C3": "claude-sonnet-5-5"}
    cost_recs = _cost_records_all_computable()
    cost_recs["C1"] = CandidateCostComparabilityRecord(
        candidate_id="C1",
        authoritative_usage_available=False,
        canonical_cost_computable=False,
    )
    receipts = [
        _make_receipt(
            phase="DEV_SELECT",
            prompt_id="P1",
            candidate_id=cid,
            fixture_id=fid,
            canonical_cost_usd=None,
            canonical_cost_usd_decimal=None,
            authoritative_usage_available=False,
            latency_ms=lats_ms[cid],
            latency_ns=lats_ns[cid],
            requested_model_id=req_models[cid],
            returned_model_id=req_models[cid],
        )
        for cid in ORDERED_CANDIDATE_IDS
        for fid in fids
    ]
    res = select_winning_candidate_dev_select(
        locked_prompt_id="P1",
        dev_select_fixture_ids=fids,
        cell_receipts=receipts,
        cost_comparability_by_candidate=cost_recs,
    )
    assert res.selected_candidate_id == "C3"
    assert res.selected_at_stage == "MEDIAN_LATENCY"
    assert res.is_administrative_tiebreak is False


# ==============================================================================
# FIX-26 & FIX-27: Fix Group H (QA-32 Prompt Freeze Gate & Single-Prompt Status)
# ==============================================================================


def test_fix_26_single_prompt_dev_tune_returns_exact_lock_p1_status(shared_env):
    """FIX-26: Single-prompt DEV-TUNE returns selected_at_stage == LOCK_P1_WITHOUT_PERFORMANCE_COMPARISON."""
    fids = [s.scenario_id for s in shared_env["bundle"].dev_tune_fixtures]
    receipts = [
        _make_receipt(prompt_id="P1", candidate_id=cid, fixture_id=fid)
        for cid in ORDERED_CANDIDATE_IDS
        for fid in fids
    ]
    res = select_winning_prompt_dev_tune(
        prompt_registry=shared_env["p1_reg"],
        dev_tune_fixture_ids=fids,
        cell_receipts=receipts,
    )
    assert res.selected_prompt_id == "P1"
    assert res.selected_at_stage == "LOCK_P1_WITHOUT_PERFORMANCE_COMPARISON"
    assert SINGLE_PROMPT_P1_LOCK_STATUS == "LOCK_P1_WITHOUT_PERFORMANCE_COMPARISON"


def test_fix_27_unverified_prompt_freeze_fails_closed_before_live(shared_env, tmp_path: Path):
    """FIX-27: Missing, unverified, or hash-mismatched prompt freeze artifact fails closed."""
    p1_reg = shared_env["p1_reg"]
    tune_plan = shared_env["tune_plan"]
    missing_path = tmp_path / "nonexistent_freeze.json"
    with pytest.raises(PromptFreezeFirewallError):
        assert_prompt_freeze_before_live(
            missing_path,
            prompt_registry=p1_reg,
            dev_tune_plan=tune_plan,
            dev_bundle=shared_env["bundle"],
            candidate_registry=shared_env["cand_reg"],
        )

    valid_freeze = build_dev_prompt_freeze_artifact(
        prompt_registry=p1_reg,
        dev_tune_plan=tune_plan,
        dev_bundle=shared_env["bundle"],
        candidate_registry=shared_env["cand_reg"],
    )
    verified = verify_prompt_candidate_freeze_artifact(
        valid_freeze,
        prompt_registry=p1_reg,
        dev_tune_plan=tune_plan,
        dev_bundle=shared_env["bundle"],
        candidate_registry=shared_env["cand_reg"],
    )
    assert verified.freeze_status == "FROZEN_FOR_LIVE_DEV_TUNE"

    # Unverified flag fails
    unverified_payload = valid_freeze.model_dump()
    unverified_payload["created_before_live_dev_execution"] = False
    with pytest.raises(PromptFreezeFirewallError):
        verify_prompt_candidate_freeze_artifact(
            unverified_payload,
            prompt_registry=p1_reg,
            dev_tune_plan=tune_plan,
            dev_bundle=shared_env["bundle"],
            candidate_registry=shared_env["cand_reg"],
        )

    # Tampered prompt hash fails
    tampered_payload = valid_freeze.model_dump()
    tampered_payload["system_prompt_sha256_by_id"]["P1"] = "0" * 64
    with pytest.raises(PromptFreezeFirewallError, match="mismatch"):
        verify_prompt_candidate_freeze_artifact(
            tampered_payload,
            prompt_registry=p1_reg,
            dev_tune_plan=tune_plan,
            dev_bundle=shared_env["bundle"],
            candidate_registry=shared_env["cand_reg"],
        )


# ==============================================================================
# FIX-28: Fix Group I (QA-33 Complete Provenance Fields)
# ==============================================================================


def test_fix_28_code_commit_sha_and_provider_config_sha256_on_manifest_and_receipt(
    shared_env, tmp_path: Path
):
    """FIX-28: code_commit_sha and provider_config_sha256 are present, validated against HEAD, and propagated."""
    cell0: DevCellExecutionManifest = shared_env["cell0"]
    head_sha = resolve_active_git_commit_sha()
    assert len(cell0.code_commit_sha) == 40
    assert cell0.code_commit_sha == head_sha
    assert len(cell0.provider_config_sha256) == 64

    c1_spec = shared_env["cand_reg"].candidates[cell0.candidate_id]
    assert cell0.provider_config_sha256 == compute_candidate_provider_config_sha256(c1_spec)

    payload = _build_complete_valid_plan_dict(shared_env["scen0"], shared_env["cat0"])
    rec, eval_res = execute_dev_cell_with_mock_transport(
        cell_manifest=cell0,
        scenario=shared_env["scen0"],
        cell_dir=tmp_path / "fix_28_cell",
        mock_response=MockProviderTransportResponse(
            returned_model_id=cell0.requested_model_id,
            raw_text=json.dumps(payload, ensure_ascii=False),
        ),
        core_catalog_by_id=shared_env["core_map"],
    )
    assert rec.code_commit_sha == head_sha
    assert rec.provider_config_sha256 == cell0.provider_config_sha256
    assert eval_res.run_valid is True
    manifest_on_disk = json.loads((tmp_path / "fix_28_cell" / "request_manifest.json").read_text(encoding="utf-8"))
    receipt_on_disk = json.loads((tmp_path / "fix_28_cell" / "execution_receipt.json").read_text(encoding="utf-8"))
    assert manifest_on_disk["code_commit_sha"] == head_sha
    assert manifest_on_disk["provider_config_sha256"] == cell0.provider_config_sha256
    assert receipt_on_disk["code_commit_sha"] == head_sha
    assert receipt_on_disk["provider_config_sha256"] == cell0.provider_config_sha256

    with pytest.raises(ValidationError):
        DevCellExecutionManifest(**{**cell0.model_dump(), "code_commit_sha": "short"})


# ==============================================================================
# FIX-29 through FIX-35: Preserved Scientific Contracts & Zero Live Calls
# ==============================================================================


def test_fix_29_dev_tune_10pp_set_based_reduction_still_passes(shared_env):
    """FIX-29: DEV-TUNE 10pp set-based reduction selects P2 when P2 beats P1 by >10pp."""
    p1 = shared_env["p1_reg"].prompts[0]
    p2 = create_prompt_candidate_spec(
        prompt_id="P2",
        prompt_version="TRAVEL_PLANNER_BENCHMARK_V2_P2",
        system_prompt=p1.system_prompt + "\nEnsure strict compliance.",
        user_prompt_template=p1.user_prompt_template,
        created_before_live_dev_execution=True,
    )
    reg2 = build_prompt_registry([p1, p2])
    fids = [s.scenario_id for s in shared_env["bundle"].dev_tune_fixtures]
    receipts: List[DevCellExecutionReceipt] = []
    for pid in ("P1", "P2"):
        for cid in ORDERED_CANDIDATE_IDS:
            for idx, fid in enumerate(fids):
                # P2 has 100% valid, P1 has 80% valid (20pp gap > 10pp)
                valid = True if pid == "P2" else (idx >= 4)
                receipts.append(
                    _make_receipt(
                        prompt_id=pid,
                        candidate_id=cid,
                        fixture_id=fid,
                        valid_run_and_schema=valid,
                        exact_grounding_pass=valid,
                        final_core_pass=valid,
                        failure_classification=(
                            DevCellFailureClassification.NONE
                            if valid
                            else DevCellFailureClassification.SEMANTIC_VALIDATION_FAILURE
                        ),
                    )
                )
    res = select_winning_prompt_dev_tune(
        prompt_registry=reg2,
        dev_tune_fixture_ids=fids,
        cell_receipts=receipts,
    )
    assert res.selected_prompt_id == "P2"
    assert res.selected_at_stage == "VALID_RUN_AND_SCHEMA_RATE"


def test_fix_30_dev_select_10pp_set_based_reduction_still_passes(shared_env):
    """FIX-30: DEV-SELECT 10pp set-based reduction selects clear winner on Criterion 2."""
    fids = [s.scenario_id for s in shared_env["bundle"].dev_select_fixtures]
    req_models = {"C1": "gemini-3.8-flash", "C2": "gpt-6.1-sol", "C3": "claude-sonnet-5-5"}
    receipts: List[DevCellExecutionReceipt] = []
    for cid in ORDERED_CANDIDATE_IDS:
        for idx, fid in enumerate(fids):
            # All 100% valid_run_and_schema; C2 has 100% grounding, C1 & C3 have 80% grounding
            grounded = True if cid == "C2" else (idx >= 12)
            receipts.append(
                _make_receipt(
                    phase="DEV_SELECT",
                    prompt_id="P1",
                    candidate_id=cid,
                    fixture_id=fid,
                    valid_run_and_schema=True,
                    exact_grounding_pass=grounded,
                    final_core_pass=grounded,
                    requested_model_id=req_models[cid],
                    returned_model_id=req_models[cid],
                )
            )
    res = select_winning_candidate_dev_select(
        locked_prompt_id="P1",
        dev_select_fixture_ids=fids,
        cell_receipts=receipts,
        cost_comparability_by_candidate=_cost_records_all_computable(),
    )
    assert res.selected_candidate_id == "C2"
    assert res.selected_at_stage == "EXACT_GROUNDING_PASS_RATE"


def test_fix_31_no_pairwise_chaining_still_passes():
    """FIX-31: Set-based 10pp rule keeps all three for {A:0.90, B:0.82, C:0.80} and does not chain via B."""
    survivors, best_val = reduce_survivors_by_10pp_rule(
        ["C1", "C2", "C3"],
        {"C1": 0.90, "C2": 0.82, "C3": 0.80},
    )
    assert survivors == ["C1", "C2", "C3"]
    assert best_val == 0.90

    # And when C3 is 0.78, C3 is eliminated against best=0.90 (not preserved by chaining from C2=0.82)
    survivors2, _ = reduce_survivors_by_10pp_rule(
        ["C1", "C2", "C3"],
        {"C1": 0.90, "C2": 0.82, "C3": 0.78},
    )
    assert survivors2 == ["C1", "C2"]


def test_fix_32_exact_0_10_boundary_still_passes():
    """FIX-32: Exact 0.10 difference survives (best - r <= 0.10); 0.100001 difference is eliminated."""
    survivors_exact, _ = reduce_survivors_by_10pp_rule(
        ["C1", "C2"],
        {"C1": 0.90, "C2": 0.80},
    )
    assert survivors_exact == ["C1", "C2"]

    survivors_below, _ = reduce_survivors_by_10pp_rule(
        ["C1", "C2"],
        {"C1": 0.90, "C2": 0.799999},
    )
    assert survivors_below == ["C1"]


def test_fix_33_reca_622_catalog_still_passes():
    """FIX-33: REC-A 622 catalog integrity (145 + 289 + 188 = 622) still passes."""
    counts = {
        slug: len(build_destination_catalog_context(slug))
        for slug in ("ha-noi", "da-nang", "ha-long")
    }
    assert counts == {"ha-noi": 145, "da-nang": 289, "ha-long": 188}
    assert sum(counts.values()) == 622


def test_fix_34_stochasticity_5_fixture_gate_still_passes(shared_env):
    """FIX-34: Stochasticity 5-fixture gate (W06-DEV-TUNE-001..005, max 15 calls) still passes."""
    with pytest.raises(StochasticityGateViolationError):
        build_stochasticity_diagnostic_plan(
            dev_select_result=None,
            locked_prompt_spec=shared_env["p1_reg"].prompts[0],
            dev_bundle=shared_env["bundle"],
            candidate_registry=shared_env["cand_reg"],
        )

    fids = [s.scenario_id for s in shared_env["bundle"].dev_select_fixtures]
    req_models = {"C1": "gemini-3.8-flash", "C2": "gpt-6.1-sol", "C3": "claude-sonnet-5-5"}
    receipts = [
        _make_receipt(
            phase="DEV_SELECT",
            prompt_id="P1",
            candidate_id=cid,
            fixture_id=fid,
            requested_model_id=req_models[cid],
            returned_model_id=req_models[cid],
        )
        for cid in ORDERED_CANDIDATE_IDS
        for fid in fids
    ]
    sel_res = select_winning_candidate_dev_select(
        locked_prompt_id="P1",
        dev_select_fixture_ids=fids,
        cell_receipts=receipts,
        cost_comparability_by_candidate=_cost_records_all_computable(),
    )
    stoch_plan = build_stochasticity_diagnostic_plan(
        dev_select_result=sel_res,
        locked_prompt_spec=shared_env["p1_reg"].prompts[0],
        dev_bundle=shared_env["bundle"],
        candidate_registry=shared_env["cand_reg"],
    )
    assert stoch_plan.max_calls == 15
    assert len(stoch_plan.cells) == 15
    assert stoch_plan.fixture_ids == [
        "W06-DEV-TUNE-001",
        "W06-DEV-TUNE-002",
        "W06-DEV-TUNE-003",
        "W06-DEV-TUNE-004",
        "W06-DEV-TUNE-005",
    ]


def test_fix_35_zero_live_calls_and_historical_qa01_immutability():
    """FIX-35 & Section 17: Verify 0 live calls, frozen authorities intact, and QA-01 evidence untouched."""
    verified = verify_frozen_authorities_dev_harness()
    assert len(verified) >= 10

    fix_receipt_path = (
        REPO_ROOT / "data" / "evaluation" / "w06" / "w06_dev_selection_harness_fix_01_receipt_v1.json"
    )
    if fix_receipt_path.exists():
        fix_receipt = json.loads(fix_receipt_path.read_text(encoding="utf-8"))
        assert fix_receipt["live_provider_calls"] == 0
        assert fix_receipt["provider_cost_usd"] == 0
        assert fix_receipt["historical_qa_01_preserved"] is True
        assert fix_receipt["fix_status"] == "READY_FOR_RE_QA"
        assert fix_receipt["next_gate"] == "W06-DEV-SELECTION-HARNESS-QA-02-OFFLINE-RERUN"

    # Verify exact LF-normalized SHA256 hashes for all 4 historical QA-01 files
    expected_qa01_shas = {
        "data/evaluation/w06/w06_dev_selection_harness_qa_01_receipt_v1.json": (
            "51b7606ebca7b5a67b6e6514d2f0c4fa4c7933919be2a5c2ec8179b21b286c9f"
        ),
        "docs/research/w06_dev_selection_harness_qa_01.md": (
            "2620638d08d76dd619743f606e004c14fe5822635caafd130a258d5e052ff7d9"
        ),
        "scripts/audit_w06_dev_selection_harness.py": (
            "878f89ecd80e62a80c1ad23e9a48fa03ace4bb1b228c5ba1814c3cf632a3bd80"
        ),
        "apps/ai-service/tests/test_w06_dev_selection_harness_qa_01.py": (
            "b97615b4279a669e0064213681442a3c7506a5fc048f77ca9b5814d6c882bc18"
        ),
    }
    for rel_path, exp_sha in expected_qa01_shas.items():
        fpath = REPO_ROOT / rel_path
        assert fpath.exists(), f"Missing historical QA-01 file: {rel_path}"
        actual_sha = sha256_bytes(normalize_lf_bytes(fpath.read_bytes()))
        assert actual_sha == exp_sha, f"Historical QA-01 file {rel_path} modified: {actual_sha} != {exp_sha}"

    # Also verify git diff against develop when base commit is present (non-shallow checkout)
    has_base = subprocess.run(
        ["git", "cat-file", "-e", "f81faa7de3988a20af1adc5b04601c49cf953d4a^{commit}"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if has_base.returncode == 0:
        proc = subprocess.run(
            ["git", "diff", "f81faa7de3988a20af1adc5b04601c49cf953d4a", "--", *HISTORICAL_QA01_IMMUTABLE_FILES],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=True,
        )
        assert proc.stdout.strip() == "", f"Historical QA-01 files modified: {proc.stdout}"


# ==============================================================================
# AC-01 through AC-18: ChatGPT Audit Correction 01 Regression Tests
# (W06-DEV-SELECTION-HARNESS-FIX-01-AUDIT-CORRECTION-01)
# ==============================================================================


def test_ac_01_cell_receipt_stores_exact_canonical_cost_usd_decimal(shared_env, tmp_path: Path):
    """AC-01: Cell receipt stores exact canonical_cost_usd_decimal as non-exponent decimal text."""
    c1_rec = CandidateCostComparabilityRecord(
        candidate_id="C1",
        authoritative_usage_available=True,
        pricing_source="https://ai.google.dev/gemini-api/docs/pricing",
        pricing_access_date="2026-10-18",
        input_price_per_million_usd=0.1000000000001,
        output_price_per_million_usd=0.4000000000003,
        canonical_cost_computable=True,
    )
    payload = _build_complete_valid_plan_dict(shared_env["scen0"], shared_env["cat0"])
    rec, _ = execute_dev_cell_with_mock_transport(
        cell_manifest=shared_env["cell0"],
        scenario=shared_env["scen0"],
        cell_dir=tmp_path / "ac_01_cell",
        mock_response=MockProviderTransportResponse(
            returned_model_id=shared_env["cell0"].requested_model_id,
            raw_text=json.dumps(payload, ensure_ascii=False),
            input_tokens=514,
            output_tokens=599,
            thought_tokens=3179,
            total_tokens=4292,
            authoritative_usage_available=True,
        ),
        cost_comparability=c1_rec,
        core_catalog_by_id=shared_env["core_map"],
    )
    expected_dec = compute_canonical_cell_cost_decimal(
        input_tokens=514,
        output_tokens=599,
        thought_tokens=3179,
        cost_record=c1_rec,
    )
    expected_str = compute_canonical_cell_cost_decimal_str(
        input_tokens=514,
        output_tokens=599,
        thought_tokens=3179,
        cost_record=c1_rec,
    )
    assert expected_dec is not None
    assert expected_str is not None
    assert "e" not in expected_str.lower()
    assert rec.canonical_cost_usd_decimal == expected_str
    assert parse_canonical_decimal_str(rec.canonical_cost_usd_decimal) == expected_dec
    on_disk = json.loads((tmp_path / "ac_01_cell" / "execution_receipt.json").read_text(encoding="utf-8"))
    assert on_disk["canonical_cost_usd_decimal"] == expected_str


def test_ac_02_even_count_cost_median_uses_exact_decimal_division_by_2():
    """AC-02: Even-count cost median (60 DEV-SELECT cells or 2-cell group) uses exact Decimal division by 2."""
    assert DECIMAL_SCIENTIFIC_PRECISION == 100
    d_low = Decimal("0.010000000000000000000000000001")
    d_high = Decimal("0.010000000000000000000000000002")
    med = compute_exact_decimal_median([d_low, d_high])
    assert med == Decimal("0.0100000000000000000000000000015")
    assert format_canonical_decimal_str(med) == "0.0100000000000000000000000000015"

    # Also test via aggregate_dev_cell_receipts with 2 assigned cells
    r1 = _make_receipt(
        phase="DEV_SELECT",
        prompt_id="P1",
        candidate_id="C1",
        fixture_id="W06-DEV-SELECT-001",
        canonical_cost_usd_decimal="0.010000000000000000000000000001",
        canonical_cost_usd=0.01,
    )
    r2 = _make_receipt(
        phase="DEV_SELECT",
        prompt_id="P1",
        candidate_id="C1",
        fixture_id="W06-DEV-SELECT-002",
        canonical_cost_usd_decimal="0.010000000000000000000000000002",
        canonical_cost_usd=0.01,
    )
    agg = aggregate_dev_cell_receipts(
        group_id="C1",
        assigned_cell_keys=[
            ("P1", "C1", "W06-DEV-SELECT-001"),
            ("P1", "C1", "W06-DEV-SELECT-002"),
        ],
        cell_receipts=[r1, r2],
        cost_comparability_all_computable=True,
    )
    assert agg.canonical_cost_comparable is True
    assert agg.median_canonical_cost_usd_decimal == "0.0100000000000000000000000000015"

    # Confirm float input to compute_exact_decimal_median is rejected
    with pytest.raises(TypeError, match="forbids float"):
        compute_exact_decimal_median([0.01, 0.02])  # type: ignore[list-item]


def test_ac_03_cost_tiebreak_distinguishes_sub_float_precision_decimal_differences(shared_env):
    """AC-03: Cost tiebreak distinguishes sub-float64-precision Decimal differences where float(a) == float(b)."""
    c1_dec_str = "0.010000000000000000000000000002"
    c2_dec_str = "0.010000000000000000000000000001"
    c3_dec_str = "0.010000000000000000000000000003"
    # In IEEE-754 float64, all three collapse to the exact same float!
    assert float(c1_dec_str) == float(c2_dec_str) == float(c3_dec_str)
    # In exact Decimal, C2 < C1 < C3
    assert Decimal(c2_dec_str) < Decimal(c1_dec_str) < Decimal(c3_dec_str)

    fids = [s.scenario_id for s in shared_env["bundle"].dev_select_fixtures]
    costs_dec_map = {"C1": c1_dec_str, "C2": c2_dec_str, "C3": c3_dec_str}
    req_models = {"C1": "gemini-3.8-flash", "C2": "gpt-6.1-sol", "C3": "claude-sonnet-5-5"}
    receipts = [
        _make_receipt(
            phase="DEV_SELECT",
            prompt_id="P1",
            candidate_id=cid,
            fixture_id=fid,
            canonical_cost_usd=float(costs_dec_map[cid]),
            canonical_cost_usd_decimal=costs_dec_map[cid],
            latency_ns=1_000_000_000,
            requested_model_id=req_models[cid],
            returned_model_id=req_models[cid],
        )
        for cid in ORDERED_CANDIDATE_IDS
        for fid in fids
    ]
    res = select_winning_candidate_dev_select(
        locked_prompt_id="P1",
        dev_select_fixture_ids=fids,
        cell_receipts=receipts,
        cost_comparability_by_candidate=_cost_records_all_computable(),
    )
    assert res.selected_candidate_id == "C2"
    assert res.selected_at_stage == "MEDIAN_COST_PER_SCENARIO"
    assert res.is_administrative_tiebreak is False
    cost_step = next(s for s in res.reduction_trace if s.criterion_name == "MEDIAN_COST_PER_SCENARIO")
    assert cost_step.best_or_reference_value_decimal == c2_dec_str
    assert cost_step.scores_of_entering_survivors_decimal == costs_dec_map


def test_ac_04_float_display_cost_field_never_consulted_by_dev_select(shared_env):
    """AC-04: Float display cost fields are never consulted by aggregator or DEV-SELECT Criterion 4."""
    fids = [s.scenario_id for s in shared_env["bundle"].dev_select_fixtures]
    req_models = {"C1": "gemini-3.8-flash", "C2": "gpt-6.1-sol", "C3": "claude-sonnet-5-5"}
    # Give C3 the lowest exact Decimal cost ("0.005"), while poisoning float display cost to make C1 look cheapest (0.0001)
    exact_costs = {"C1": "0.020", "C2": "0.015", "C3": "0.005"}
    poisoned_float_costs = {"C1": 0.0001, "C2": 0.0002, "C3": 999.0}
    receipts = [
        _make_receipt(
            phase="DEV_SELECT",
            prompt_id="P1",
            candidate_id=cid,
            fixture_id=fid,
            canonical_cost_usd=poisoned_float_costs[cid],
            canonical_cost_usd_decimal=exact_costs[cid],
            latency_ns=1_000_000_000,
            requested_model_id=req_models[cid],
            returned_model_id=req_models[cid],
        )
        for cid in ORDERED_CANDIDATE_IDS
        for fid in fids
    ]
    res = select_winning_candidate_dev_select(
        locked_prompt_id="P1",
        dev_select_fixture_ids=fids,
        cell_receipts=receipts,
        cost_comparability_by_candidate=_cost_records_all_computable(),
    )
    assert res.selected_candidate_id == "C3"
    assert res.selected_at_stage == "MEDIAN_COST_PER_SCENARIO"
    assert res.candidate_aggregates["C3"].median_canonical_cost_usd_decimal == "0.005"


def test_ac_05_cell_receipt_stores_integer_latency_ns(shared_env, tmp_path: Path):
    """AC-05: Cell receipt stores authoritative integer latency_ns and rejects negative/bool latency_ns."""
    payload = _build_complete_valid_plan_dict(shared_env["scen0"], shared_env["cat0"])
    rec, _ = execute_dev_cell_with_mock_transport(
        cell_manifest=shared_env["cell0"],
        scenario=shared_env["scen0"],
        cell_dir=tmp_path / "ac_05_cell",
        mock_response=MockProviderTransportResponse(
            returned_model_id=shared_env["cell0"].requested_model_id,
            raw_text=json.dumps(payload, ensure_ascii=False),
            latency_ns=1_234_567_891,
            latency_ms=1234.567891,
        ),
        core_catalog_by_id=shared_env["core_map"],
    )
    assert isinstance(rec.latency_ns, int)
    assert rec.latency_ns == 1_234_567_891
    assert rec.latency_ms_display == 1234.567891

    with pytest.raises(ValidationError):
        _make_receipt(latency_ns=-1)


def test_ac_06_aggregator_computes_exact_decimal_median_from_latency_ns():
    """AC-06: Aggregator computes median_latency_ns_decimal as exact Decimal median of integer latency_ns."""
    # Even count (2 cells) with odd sum: 1_000_000_000 + 1_000_000_001 -> exact median "1000000000.5"
    r1 = _make_receipt(
        phase="DEV_SELECT",
        prompt_id="P1",
        candidate_id="C1",
        fixture_id="W06-DEV-SELECT-001",
        latency_ns=1_000_000_000,
        latency_ms=99999.0,  # poisoned float latency_ms
    )
    r2 = _make_receipt(
        phase="DEV_SELECT",
        prompt_id="P1",
        candidate_id="C1",
        fixture_id="W06-DEV-SELECT-002",
        latency_ns=1_000_000_001,
        latency_ms=99999.0,  # poisoned float latency_ms
    )
    agg = aggregate_dev_cell_receipts(
        group_id="C1",
        assigned_cell_keys=[
            ("P1", "C1", "W06-DEV-SELECT-001"),
            ("P1", "C1", "W06-DEV-SELECT-002"),
        ],
        cell_receipts=[r1, r2],
        cost_comparability_all_computable=True,
    )
    assert agg.median_latency_ns_decimal == "1000000000.5"


def test_ac_07_dev_select_criterion_5_compares_exact_decimal_median_latency_ns(shared_env):
    """AC-07: DEV-SELECT Criterion 5 compares exact Decimal median_latency_ns_decimal and ignores float latency_ms."""
    fids = [s.scenario_id for s in shared_env["bundle"].dev_select_fixtures]
    req_models = {"C1": "gemini-3.8-flash", "C2": "gpt-6.1-sol", "C3": "claude-sonnet-5-5"}
    # Integer nanoseconds that collide in IEEE-754 float64 (beyond 53 bits of significand: 10^18 + 1 vs 10^18 + 2)
    lats_ns = {
        "C1": 1_000_000_000_000_000_002,
        "C2": 1_000_000_000_000_000_003,
        "C3": 1_000_000_000_000_000_001,
    }
    assert float(lats_ns["C1"]) == float(lats_ns["C2"]) == float(lats_ns["C3"])
    # Poison float latency_ms in the opposite order (C1 lowest ms, C3 highest ms)
    poisoned_lats_ms = {"C1": 10.0, "C2": 20.0, "C3": 99999.0}

    receipts = [
        _make_receipt(
            phase="DEV_SELECT",
            prompt_id="P1",
            candidate_id=cid,
            fixture_id=fid,
            canonical_cost_usd_decimal="0.015",
            canonical_cost_usd=0.015,
            latency_ns=lats_ns[cid],
            latency_ms=poisoned_lats_ms[cid],
            requested_model_id=req_models[cid],
            returned_model_id=req_models[cid],
        )
        for cid in ORDERED_CANDIDATE_IDS
        for fid in fids
    ]
    res = select_winning_candidate_dev_select(
        locked_prompt_id="P1",
        dev_select_fixture_ids=fids,
        cell_receipts=receipts,
        cost_comparability_by_candidate=_cost_records_all_computable(),
    )
    assert res.selected_candidate_id == "C3"
    assert res.selected_at_stage == "MEDIAN_LATENCY"
    assert res.is_administrative_tiebreak is False
    lat_step = next(s for s in res.reduction_trace if s.criterion_name == "MEDIAN_LATENCY")
    assert lat_step.best_or_reference_value_decimal == str(lats_ns["C3"])


def test_ac_08_missing_latency_ns_fails_closed_when_criterion_5_is_reached(shared_env):
    """AC-08: Missing latency_ns fails closed with LatencyAuthorityUnavailableError when Criterion 5 is reached."""
    fids = [s.scenario_id for s in shared_env["bundle"].dev_select_fixtures]
    req_models = {"C1": "gemini-3.8-flash", "C2": "gpt-6.1-sol", "C3": "claude-sonnet-5-5"}
    receipts = [
        _make_receipt(
            phase="DEV_SELECT",
            prompt_id="P1",
            candidate_id=cid,
            fixture_id=fid,
            canonical_cost_usd_decimal="0.015",
            canonical_cost_usd=0.015,
            latency_ns=None if (cid == "C2" and fid == fids[0]) else 1_000_000_000,
            latency_ms=1000.0,
            requested_model_id=req_models[cid],
            returned_model_id=req_models[cid],
        )
        for cid in ORDERED_CANDIDATE_IDS
        for fid in fids
    ]
    with pytest.raises(LatencyAuthorityUnavailableError, match="LATENCY_AUTHORITY_UNAVAILABLE"):
        select_winning_candidate_dev_select(
            locked_prompt_id="P1",
            dev_select_fixture_ids=fids,
            cell_receipts=receipts,
            cost_comparability_by_candidate=_cost_records_all_computable(),
        )


def test_ac_09_resolve_active_git_commit_sha_returns_exact_git_rev_parse_head():
    """AC-09: resolve_active_git_commit_sha() returns exact 40-char lowercase hex git rev-parse HEAD."""
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    expected_head = proc.stdout.strip().lower()
    assert len(expected_head) == 40
    assert resolve_active_git_commit_sha() == expected_head
    assert resolve_and_verify_code_commit_sha(None) == expected_head
    assert resolve_and_verify_code_commit_sha(expected_head) == expected_head


def test_ac_10_resolve_active_git_commit_sha_fails_closed_when_git_fails(monkeypatch):
    """AC-10: resolve_active_git_commit_sha() fails closed with CodeCommitProvenanceError when git fails."""
    def _mock_run_nonzero(*args, **kwargs):
        return subprocess.CompletedProcess(args=args[0], returncode=128, stdout="", stderr="fatal: not a git repo")

    monkeypatch.setattr(subprocess, "run", _mock_run_nonzero)
    with pytest.raises(CodeCommitProvenanceError, match="CODE_COMMIT_PROVENANCE_ERROR"):
        resolve_active_git_commit_sha()

    def _mock_run_bad_sha(*args, **kwargs):
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="not-a-40-hex-sha\n", stderr="")

    monkeypatch.setattr(subprocess, "run", _mock_run_bad_sha)
    with pytest.raises(CodeCommitProvenanceError, match="CODE_COMMIT_PROVENANCE_ERROR"):
        resolve_active_git_commit_sha()

    def _mock_run_oserror(*args, **kwargs):
        raise OSError("git binary missing")

    monkeypatch.setattr(subprocess, "run", _mock_run_oserror)
    with pytest.raises(CodeCommitProvenanceError, match="CODE_COMMIT_PROVENANCE_ERROR"):
        resolve_active_git_commit_sha()


def test_ac_11_static_fallback_sha_constant_is_removed_or_forbidden():
    """AC-11: Static fallback SHA constant EXPECTED_BASE_DEVELOP_SHA_FIX_01 is removed and forbidden."""
    assert not hasattr(harness, "EXPECTED_BASE_DEVELOP_SHA_FIX_01")
    src_resolve = inspect.getsource(resolve_active_git_commit_sha)
    src_verify = inspect.getsource(resolve_and_verify_code_commit_sha)
    assert "f81faa7de3988a20af1adc5b04601c49cf953d4a" not in src_resolve
    assert "f81faa7de3988a20af1adc5b04601c49cf953d4a" not in src_verify
    assert "EXPECTED_BASE_DEVELOP_SHA" not in src_resolve


def test_ac_12_mismatched_supplied_code_commit_sha_is_rejected(shared_env):
    """AC-12: Supplying a 40-hex SHA that does not match git rev-parse HEAD is rejected fail-closed."""
    head_sha = resolve_active_git_commit_sha()
    wrong_sha = ("0" * 39 + "1") if head_sha != ("0" * 39 + "1") else ("0" * 39 + "2")

    with pytest.raises(CodeCommitProvenanceError, match="CODE_COMMIT_SHA_MISMATCH"):
        resolve_and_verify_code_commit_sha(wrong_sha)

    cell0: DevCellExecutionManifest = shared_env["cell0"]
    with pytest.raises((CodeCommitProvenanceError, ValidationError), match="CODE_COMMIT_SHA_MISMATCH"):
        DevCellExecutionManifest(**{**cell0.model_dump(), "code_commit_sha": wrong_sha})

    with pytest.raises((CodeCommitProvenanceError, ValidationError), match="CODE_COMMIT_SHA_MISMATCH"):
        _make_receipt(code_commit_sha=wrong_sha)

    with pytest.raises(CodeCommitProvenanceError, match="CODE_COMMIT_SHA_MISMATCH"):
        build_dev_tune_execution_plan(
            shared_env["p1_reg"],
            dev_bundle=shared_env["bundle"],
            candidate_registry=shared_env["cand_reg"],
            code_commit_sha=wrong_sha,
        )

    with pytest.raises(CodeCommitProvenanceError, match="CODE_COMMIT_SHA_MISMATCH"):
        build_dev_select_execution_plan(
            shared_env["p1_reg"].prompts[0],
            dev_bundle=shared_env["bundle"],
            candidate_registry=shared_env["cand_reg"],
            code_commit_sha=wrong_sha,
        )

    with pytest.raises(CodeCommitProvenanceError, match="CODE_COMMIT_SHA_MISMATCH"):
        build_dev_prompt_freeze_artifact(
            prompt_registry=shared_env["p1_reg"],
            dev_tune_plan=shared_env["tune_plan"],
            dev_bundle=shared_env["bundle"],
            candidate_registry=shared_env["cand_reg"],
            code_commit_sha=wrong_sha,
        )

    # Confirm explicit test-only helper allows synthetic SHA only when explicitly invoked
    synth_manifest = create_synthetic_test_only_cell_manifest(
        **{**cell0.model_dump(), "code_commit_sha": wrong_sha}
    )
    assert synth_manifest.code_commit_sha == wrong_sha
    synth_receipt = create_synthetic_test_only_cell_receipt(
        run_id="SYNTH-TEST-ONLY-001",
        phase="DEV_TUNE",
        fixture_id=cell0.fixture_id,
        candidate_id="C1",
        prompt_id="P1",
        requested_model_id=cell0.requested_model_id,
        returned_model_id=cell0.requested_model_id,
        code_commit_sha=wrong_sha,
        provider_config_sha256=cell0.provider_config_sha256,
        attempt_number=1,
        attempted=True,
        failure_classification=DevCellFailureClassification.NONE,
        valid_run_and_schema=True,
        exact_grounding_pass=True,
        final_core_pass=True,
        latency_ns=1_000_000,
        latency_ms=1.0,
        request_manifest_sha256="a" * 64,
        raw_response_sha256="b" * 64,
        provider_metadata_sha256="c" * 64,
        parsed_response_sha256="d" * 64,
        evaluation_result_sha256="e" * 64,
    )
    assert synth_receipt.code_commit_sha == wrong_sha


def test_ac_13_conftest_contains_no_monkeypatching_of_dev_selection_harness():
    """AC-13: conftest.py contains no runtime monkeypatching of dev_selection_harness."""
    conftest_path = REPO_ROOT / "apps" / "ai-service" / "tests" / "conftest.py"
    conftest_src = conftest_path.read_text(encoding="utf-8")
    assert "pytest_runtest_setup" not in conftest_src
    assert "pytest_runtest_teardown" not in conftest_src
    assert "_SAVED_PATCHES" not in conftest_src
    assert "setattr(" not in conftest_src
    assert "import dev_selection_harness" not in conftest_src


def test_ac_14_conftest_does_not_replace_run_all_qa_checks():
    """AC-14: conftest.py does not replace run_all_qa_checks and uses pytest_collection_modifyitems skip marker."""
    conftest_path = REPO_ROOT / "apps" / "ai-service" / "tests" / "conftest.py"
    conftest_src = conftest_path.read_text(encoding="utf-8")
    assert "pytest_pycollect_makeitem" not in conftest_src
    assert "run_all_qa_checks" not in conftest_src
    assert "_load_frozen_qa01_receipt" not in conftest_src
    assert "pytest_collection_modifyitems" in conftest_src
    assert "HISTORICAL_QA01_EVIDENCE_ONLY_CURRENT_HARNESS_REAUDITED_BY_QA02" in conftest_src


def test_ac_15_historical_qa01_files_remain_byte_identical_to_develop():
    """AC-15: All 4 historical QA-01 evidence files remain byte-identical to develop."""
    expected_qa01_shas = {
        "data/evaluation/w06/w06_dev_selection_harness_qa_01_receipt_v1.json": (
            "51b7606ebca7b5a67b6e6514d2f0c4fa4c7933919be2a5c2ec8179b21b286c9f"
        ),
        "docs/research/w06_dev_selection_harness_qa_01.md": (
            "2620638d08d76dd619743f606e004c14fe5822635caafd130a258d5e052ff7d9"
        ),
        "scripts/audit_w06_dev_selection_harness.py": (
            "878f89ecd80e62a80c1ad23e9a48fa03ace4bb1b228c5ba1814c3cf632a3bd80"
        ),
        "apps/ai-service/tests/test_w06_dev_selection_harness_qa_01.py": (
            "b97615b4279a669e0064213681442a3c7506a5fc048f77ca9b5814d6c882bc18"
        ),
    }
    for rel_path, exp_sha in expected_qa01_shas.items():
        fpath = REPO_ROOT / rel_path
        assert fpath.exists()
        assert sha256_bytes(normalize_lf_bytes(fpath.read_bytes())) == exp_sha


def test_ac_16_all_existing_dh_01_to_dh_35_tests_present():
    """AC-16: Verify all existing DH-01..DH-35 test functions exist in test_w06_dev_selection_harness_01."""
    import importlib.util

    dh_path = REPO_ROOT / "apps" / "ai-service" / "tests" / "test_w06_dev_selection_harness_01.py"
    spec = importlib.util.spec_from_file_location("test_w06_dev_selection_harness_01", dh_path)
    assert spec is not None and spec.loader is not None
    dh_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dh_mod)

    dh_funcs = [name for name in dir(dh_mod) if name.startswith("test_dh_")]
    # DH-25 and DH-26 are combined in test_dh_25_26_cost_criterion_all_survivor_comparability_and_skip_status (34 functions covering 35 IDs)
    assert len(dh_funcs) == 34
    for idx in range(1, 36):
        if idx in (25, 26):
            assert any(name.startswith("test_dh_25_26_") for name in dh_funcs)
        else:
            prefix = f"test_dh_{idx:02d}_"
            assert any(name.startswith(prefix) for name in dh_funcs), f"Missing {prefix}"


def test_ac_17_all_existing_fix_01_to_fix_35_tests_present():
    """AC-17: Verify all existing FIX-01..FIX-35 test functions exist in this module."""
    import sys

    this_mod = sys.modules[__name__]
    fix_funcs = [name for name in dir(this_mod) if name.startswith("test_fix_")]
    assert len(fix_funcs) == 35
    for idx in range(1, 36):
        prefix = f"test_fix_{idx:02d}_"
        assert any(name.startswith(prefix) for name in fix_funcs), f"Missing {prefix}"


def test_ac_18_live_provider_calls_remain_0():
    """AC-18: Verify live_provider_calls == 0, provider_cost_usd == 0, and audit correction fields in receipt."""
    fix_receipt_path = (
        REPO_ROOT / "data" / "evaluation" / "w06" / "w06_dev_selection_harness_fix_01_receipt_v1.json"
    )
    assert fix_receipt_path.exists()
    fix_receipt = json.loads(fix_receipt_path.read_text(encoding="utf-8"))
    assert fix_receipt["live_provider_calls"] == 0
    assert fix_receipt["provider_cost_usd"] == 0
    assert fix_receipt["chatgpt_audit_correction_required"] is True
    assert fix_receipt["audit_correction_id"] == "W06-DEV-SELECTION-HARNESS-FIX-01-AUDIT-CORRECTION-01"
    assert fix_receipt["exact_cost_end_to_end"] == "PASS"
    assert fix_receipt["latency_ns_selection_authority"] == "PASS"
    assert fix_receipt["code_sha_fail_closed"] == "PASS"
    assert fix_receipt["historical_qa_runtime_monkeypatch_removed"] == "PASS"
