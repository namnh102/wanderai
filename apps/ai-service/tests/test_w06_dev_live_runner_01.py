"""Offline Test Suite for W06 DEV Live Runner Infrastructure (W06-DEV-LIVE-RUNNER-01-OFFLINE).

Covers LR-01 through LR-50+ verifying:
- Scientific code bundle inclusion and content-hash sensitivity (LR-01, LR-02)
- Explicit live authorization gate and fail-closed verification (LR-03..LR-09)
- Final100 phase, path, scenario ID, and content firewall (LR-10, LR-11, LR-44)
- Two-stage Plan-Before-Live protocol and plan membership enforcement (LR-12, LR-13)
- Frozen provider wire request payloads for C1, C2, C3 + Portable Schema V2 + RECA context (LR-14..LR-18)
- Transport-start journal, raw-evidence-before-interpretation, and immutable atomic artifacts (LR-19..LR-21, LR-34, LR-37..LR-39)
- Strict primary parser only (zero markdown fence or prose rescue) (LR-22, LR-23)
- Failure taxonomy & denominator retention vs batch-fatal stops (LR-24..LR-29)
- Usage metadata normalization, raw usage preservation, and exact Decimal costing (LR-30..LR-33, LR-48)
- Deterministic call-budget ledger & retry=0 enforcement (LR-35, LR-36)
- Full mock batch execution for DEV-TUNE (60 & 120), DEV-SELECT (180), and STOCHASTICITY (15) (LR-40..LR-43)
- Secret sanitization and leak prevention (LR-45)
- Dry-run mode with 0 provider calls (LR-46)
- Network kill-switch blocking socket connections across all tests (LR-47)
- Historical receipts byte-for-byte preservation (LR-49)
- Default unauthorized live state & runner receipt verification (LR-50)
"""

from __future__ import annotations

import copy
import datetime as dt
from decimal import Decimal
import json
import os
from pathlib import Path
import socket
import subprocess
from typing import Any, Dict, List
import urllib.request

import pytest

from app.evaluation import dev_live_runner as runner
from app.evaluation.dev_live_runner import (
    ATTEMPT_STATUS_UNKNOWN_AFTER_TRANSPORT,
    AUTHORIZATION_STATUS_AUTHORIZED,
    AUTHORIZED_BY_ROLE_PROJECT_OWNER,
    DEFAULT_COST_COMPARABILITY_BY_CANDIDATE,
    DEFAULT_RUNNER_RECEIPT_PATH,
    EXPECTED_BASE_DEVELOP_SHA_RUNNER_01,
    NEXT_GATE_RUNNER_QA_01,
    PROMPT_FREEZE_STATUS_NOT_YET_FROZEN,
    REDACTED_SECRET_PLACEHOLDER,
    RUNNER_RECEIPT_ARTIFACT_ID,
    TASK_ID_DEV_LIVE_RUNNER_01,
    TRANSPORT_STATUS_COMPLETED,
    TRANSPORT_STATUS_NOT_INVOKED,
    TRANSPORT_STATUS_STARTING,
    CrashAmbiguityBatchStopError,
    DevCallBudgetExhaustedError,
    DevCallBudgetLedger,
    DevLiveAuthorizationArtifact,
    DevLiveAuthorizationError,
    DuplicateDevCellAttemptError,
    LiveExecutionNotAuthorizedError,
    MockDevProviderTransport,
    PlanBeforeLiveProtocolError,
    SecretLeakageViolationError,
    assert_no_secrets_in_payload,
    build_dev_live_authorization_artifact,
    build_dev_live_runner_01_receipt_payload,
    build_frozen_provider_wire_request,
    compute_prompt_freeze_sha256,
    create_live_provider_transport_factory,
    execute_live_dev_batch,
    execute_live_dev_cell,
    inspect_and_guard_cell_directory_before_transport,
    normalize_candidate_usage_metadata,
    run_cli,
    run_dev_live_runner_dry_run,
    sanitize_runner_structure,
    sanitize_runner_text,
    verify_dev_live_authorization_artifact,
    write_immutable_atomic_bytes,
    write_immutable_canonical_json,
    write_transport_journal_starting,
)
from app.evaluation.dev_selection_harness import (
    DEV_SELECT_MAX_CALLS,
    DEV_TUNE_MAX_CALLS_ONE_PROMPT,
    DEV_TUNE_MAX_CALLS_TWO_PROMPTS,
    EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
    EXPECTED_SEMANTIC_SCHEMA_SHA256,
    ORDERED_CANDIDATE_IDS,
    REPO_ROOT,
    SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS,
    STOCHASTICITY_MAX_CALLS,
    CandidateCostComparabilityRecord,
    CandidateRegistryIntegrityError,
    DevCellExecutionManifest,
    DevCellFailureClassification,
    DevSelectModelSelectionResult,
    Final100FirewallViolationError,
    ImmutableCellExecutionError,
    MockProviderTransportResponse,
    ModelIntegrityBatchStopError,
    PromptFreezeFirewallError,
    ScientificCodeBundleIntegrityError,
    StochasticityGateViolationError,
    aggregate_dev_cell_receipts,
    build_default_infrastructure_prompt_registry,
    build_dev_prompt_freeze_artifact,
    build_dev_select_execution_plan,
    build_dev_tune_execution_plan,
    build_prompt_registry,
    build_stochasticity_diagnostic_plan,
    canonical_json_bytes,
    compute_canonical_cell_cost_decimal,
    compute_scientific_code_bundle,
    compute_scientific_code_bundle_sha256,
    create_prompt_candidate_spec,
    load_and_verify_candidate_registry,
    load_and_verify_frozen_dev_bundle,
    select_winning_candidate_dev_select,
    sha256_bytes,
    write_canonical_json,
)
from app.evaluation.planner_benchmark_evaluator import load_core_catalog_by_place_id
from app.prompts.planner_benchmark_prompt import build_destination_catalog_context
from app.schemas.planner_benchmark import BenchmarkRunStatus, BenchmarkScenarioInput


HISTORICAL_IMMUTABLE_RECEIPTS: Dict[str, str] = {
    "data/evaluation/w06/w06_dev_selection_harness_01_receipt_v1.json": "c18dd65ec0618833dc1a345bc2805ad4b9e78b113bed79cadaff5aa5e4d34edc",
    "data/evaluation/w06/w06_dev_selection_harness_qa_01_receipt_v1.json": "51b7606ebca7b5a67b6e6514d2f0c4fa4c7933919be2a5c2ec8179b21b286c9f",
    "data/evaluation/w06/w06_dev_selection_harness_fix_01_receipt_v1.json": "3753fdcfe70931a918d399c3304df4c9e74d2114f8771021866f0ad66f65f03d",
    "data/evaluation/w06/w06_dev_selection_harness_qa_02_receipt_v1.json": "367e0bb91eeaa486e61050a33c4af3f02a669153ae57787a2414c4e7f626669e",
    "data/evaluation/w06/w06_model_preflight_01b_live_receipt_v1.json": "06e7e848612a333b4bc3f73a2a6722b94247ece6b337555d7ec458bdfa8cedbb",
    "data/evaluation/w06/w06_model_preflight_01c_portable_schema_receipt_v1.json": "524fcdefdf92de8783a39662c7514eb26612f4228545ad4cd687e700684eceb0",
    "data/evaluation/w06/w06_model_preflight_01d_v2_live_receipt_v1.json": "2c8c3384e1977816aeff559cddc8010ad9b57fdfa62b618090b7f3911e732e65",
}


@pytest.fixture(autouse=True)
def _network_kill_switch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Block all outbound socket/network connections across the entire offline runner test suite (Section 40 / LR-47)."""

    def _forbidden_connect(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError(
            "NETWORK_KILL_SWITCH_TRIGGERED: Offline DEV live runner test attempted a network socket connection!"
        )

    monkeypatch.setattr(socket.socket, "connect", _forbidden_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", _forbidden_connect)
    monkeypatch.setattr(socket, "create_connection", _forbidden_connect)


@pytest.fixture(scope="module")
def runner_env() -> Dict[str, Any]:
    """Load frozen DEV bundle, candidate registry, catalog, and pre-built plans once per module."""
    bundle = load_and_verify_frozen_dev_bundle()
    cand_reg = load_and_verify_candidate_registry()
    core_map = load_core_catalog_by_place_id()

    catalogs_by_slug: Dict[str, List[Any]] = {}
    all_fixtures = list(bundle.dev_tune_fixtures) + list(bundle.dev_select_fixtures)
    for scen in all_fixtures:
        if scen.destination_slug not in catalogs_by_slug:
            catalogs_by_slug[scen.destination_slug] = build_destination_catalog_context(
                scen.destination_slug
            )

    p1_reg = build_default_infrastructure_prompt_registry()
    p1_spec = p1_reg.prompts[0]
    p2_spec = create_prompt_candidate_spec(
        prompt_id="P2",
        prompt_version=f"{p1_spec.prompt_version}_P2",
        system_prompt=p1_spec.system_prompt,
        user_prompt_template=p1_spec.user_prompt_template
        + "\nEnsure strict adherence to daily budget and opening hours.",
    )
    p1_p2_reg = build_prompt_registry([p1_spec, p2_spec])

    tune_plan_1p = build_dev_tune_execution_plan(
        p1_reg, dev_bundle=bundle, candidate_registry=cand_reg
    )
    pf_1p = build_dev_prompt_freeze_artifact(
        prompt_registry=p1_reg,
        dev_tune_plan=tune_plan_1p,
        dev_bundle=bundle,
        candidate_registry=cand_reg,
    )
    auth_tune_1p = build_dev_live_authorization_artifact(
        task_id="TEST-AUTH-TUNE-1P",
        authorization_id="AUTH-DEV-TUNE-1P-001",
        allowed_phase="DEV_TUNE",
        execution_plan=tune_plan_1p,
        prompt_freeze=pf_1p,
    )

    tune_plan_2p = build_dev_tune_execution_plan(
        p1_p2_reg, dev_bundle=bundle, candidate_registry=cand_reg
    )
    pf_2p = build_dev_prompt_freeze_artifact(
        prompt_registry=p1_p2_reg,
        dev_tune_plan=tune_plan_2p,
        dev_bundle=bundle,
        candidate_registry=cand_reg,
    )
    auth_tune_2p = build_dev_live_authorization_artifact(
        task_id="TEST-AUTH-TUNE-2P",
        authorization_id="AUTH-DEV-TUNE-2P-001",
        allowed_phase="DEV_TUNE",
        execution_plan=tune_plan_2p,
        prompt_freeze=pf_2p,
    )

    select_plan = build_dev_select_execution_plan(
        p1_spec,
        dev_bundle=bundle,
        candidate_registry=cand_reg,
    )
    auth_select = build_dev_live_authorization_artifact(
        task_id="TEST-AUTH-SELECT",
        authorization_id="AUTH-DEV-SELECT-001",
        allowed_phase="DEV_SELECT",
        execution_plan=select_plan,
        prompt_freeze=pf_1p,
    )

    scenarios_by_id = {s.scenario_id: s for s in all_fixtures}
    valid_json_by_scenario_id: Dict[str, str] = {}
    for scen in all_fixtures:
        plan_dict = _build_valid_plan_dict_for_scenario(
            scen, catalogs_by_slug[scen.destination_slug]
        )
        valid_json_by_scenario_id[scen.scenario_id] = json.dumps(
            plan_dict, ensure_ascii=False
        )

    return {
        "bundle": bundle,
        "cand_reg": cand_reg,
        "core_map": core_map,
        "catalogs_by_slug": catalogs_by_slug,
        "scenarios_by_id": scenarios_by_id,
        "valid_json_by_scenario_id": valid_json_by_scenario_id,
        "p1_reg": p1_reg,
        "p1_p2_reg": p1_p2_reg,
        "tune_plan_1p": tune_plan_1p,
        "pf_1p": pf_1p,
        "auth_tune_1p": auth_tune_1p,
        "tune_plan_2p": tune_plan_2p,
        "pf_2p": pf_2p,
        "auth_tune_2p": auth_tune_2p,
        "select_plan": select_plan,
        "auth_select": auth_select,
    }


def _build_valid_plan_dict_for_scenario(
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
        "plan_id": f"plan-runner-{scenario.scenario_id.lower()}",
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


def _make_valid_mock_response(
    cell: DevCellExecutionManifest,
    raw_json_text: str,
    *,
    latency_ns: int = 125_000_000,
) -> MockProviderTransportResponse:
    if cell.candidate_id == "C1":
        return MockProviderTransportResponse(
            returned_model_id=cell.requested_model_id,
            raw_text=raw_json_text,
            finish_reason="STOP",
            latency_ns=latency_ns,
            latency_ms=125.0,
            simulated_failure=DevCellFailureClassification.NONE,
            authoritative_usage_available=True,
            input_tokens=1000,
            output_tokens=500,
            thought_tokens=100,
            cached_input_tokens=0,
            total_tokens=1600,
            raw_usage_metadata={
                "prompt_token_count": 1000,
                "candidates_token_count": 500,
                "thoughts_token_count": 100,
                "cached_content_token_count": 0,
                "total_token_count": 1600,
            },
        )
    if cell.candidate_id == "C2":
        return MockProviderTransportResponse(
            returned_model_id=cell.requested_model_id,
            raw_text=raw_json_text,
            finish_reason="stop",
            latency_ns=latency_ns,
            latency_ms=125.0,
            simulated_failure=DevCellFailureClassification.NONE,
            authoritative_usage_available=True,
            input_tokens=1000,
            output_tokens=600,
            reasoning_tokens=100,
            cached_input_tokens=0,
            total_tokens=1600,
            raw_usage_metadata={
                "input_tokens": 1000,
                "output_tokens": 600,
                "total_tokens": 1600,
                "output_tokens_details": {"reasoning_tokens": 100},
                "input_tokens_details": {"cached_tokens": 0},
            },
        )
    return MockProviderTransportResponse(
        returned_model_id=cell.requested_model_id,
        raw_text=raw_json_text,
        finish_reason="end_turn",
        latency_ns=latency_ns,
        latency_ms=125.0,
        simulated_failure=DevCellFailureClassification.NONE,
        authoritative_usage_available=True,
        input_tokens=1000,
        output_tokens=500,
        thinking_tokens=100,
        cache_read_input_tokens=0,
        cache_creation_input_tokens=0,
        total_tokens=1600,
        raw_usage_metadata={
            "input_tokens": 1000,
            "output_tokens": 500,
            "thinking_tokens": 100,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        },
    )


# ==============================================================================
# LR-01 & LR-02: SCIENTIFIC CODE BUNDLE INCLUSION & SENSITIVITY
# ==============================================================================


def test_lr_01_runner_included_in_scientific_code_bundle() -> None:
    """LR-01: apps/ai-service/app/evaluation/dev_live_runner.py is included in SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS."""
    rel_path = "apps/ai-service/app/evaluation/dev_live_runner.py"
    assert rel_path in SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS
    assert len(SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS) == 14
    bundle = compute_scientific_code_bundle()
    assert any(
        entry["path"] == rel_path for entry in bundle.scientific_code_bundle_file_hashes
    )


def test_lr_02_changing_runner_content_changes_scientific_code_bundle_sha256(
    tmp_path: Path,
) -> None:
    """LR-02: Modifying dev_live_runner.py bytes changes scientific_code_bundle_sha256."""
    fake_root = tmp_path / "repo"
    for rel_path in SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS:
        src = REPO_ROOT / rel_path
        dst = fake_root / rel_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())

    sha_before = compute_scientific_code_bundle_sha256(repo_root=fake_root)
    runner_copy = fake_root / "apps/ai-service/app/evaluation/dev_live_runner.py"
    runner_copy.write_bytes(runner_copy.read_bytes() + b"\n# synthetic edit\n")
    sha_after = compute_scientific_code_bundle_sha256(repo_root=fake_root)
    assert sha_before != sha_after


# ==============================================================================
# LR-03 THROUGH LR-11: AUTHORIZATION GATE & FINAL100 FIREWALL
# ==============================================================================


def test_lr_03_live_execution_without_execute_live_flag_fails_before_transport(
    runner_env: Dict[str, Any],
) -> None:
    """LR-03: Attempting live transport factory without --execute-live fails closed before any provider call."""
    with pytest.raises(LiveExecutionNotAuthorizedError, match="LIVE_EXECUTION_DISABLED"):
        create_live_provider_transport_factory(
            execute_live=False,
            authorization=runner_env["auth_tune_1p"],
        )

    res = run_cli(["--offline-validate"])
    assert res["live_provider_calls"] == 0
    assert res["transport_status"] == TRANSPORT_STATUS_NOT_INVOKED


def test_lr_04_live_execution_without_authorization_artifact_fails_before_transport(
    runner_env: Dict[str, Any], tmp_path: Path
) -> None:
    """LR-04: Live execution without authorization artifact fails before transport."""
    with pytest.raises(LiveExecutionNotAuthorizedError, match="LIVE_AUTHORIZATION_MISSING"):
        create_live_provider_transport_factory(execute_live=True, authorization=None)

    plan = runner_env["tune_plan_1p"]
    cell0 = plan.cells[0]
    scen0 = runner_env["scenarios_by_id"][cell0.fixture_id]
    ledger = DevCallBudgetLedger.from_execution_plan(plan)
    transport = MockDevProviderTransport(
        _make_valid_mock_response(cell0, runner_env["valid_json_by_scenario_id"][cell0.fixture_id])
    )
    with pytest.raises(DevLiveAuthorizationError, match="AUTHORIZATION_MISSING"):
        execute_live_dev_cell(
            cell_manifest=cell0,
            scenario=scen0,
            execution_plan=plan,
            prompt_freeze=runner_env["pf_1p"],
            prompt_registry=runner_env["p1_reg"],
            authorization=None,  # type: ignore[arg-type]
            call_budget_ledger=ledger,
            cell_dir=tmp_path / cell0.run_id,
            transport=transport,
        )
    assert transport.call_count == 0


def test_lr_05_live_execution_with_mismatched_plan_hash_fails(
    runner_env: Dict[str, Any],
) -> None:
    """LR-05: Authorization artifact with mismatched allowed_execution_plan_sha256 fails closed."""
    bad_auth = build_dev_live_authorization_artifact(
        task_id="TEST-BAD-PLAN",
        authorization_id="AUTH-BAD-PLAN",
        allowed_phase="DEV_TUNE",
        execution_plan=runner_env["tune_plan_2p"],
        prompt_freeze=runner_env["pf_1p"],
        maximum_live_generation_calls=60,
    )
    with pytest.raises(DevLiveAuthorizationError, match="AUTHORIZATION_PLAN_SHA256_MISMATCH"):
        verify_dev_live_authorization_artifact(
            bad_auth,
            execution_plan=runner_env["tune_plan_1p"],
            prompt_freeze=runner_env["pf_1p"],
        )


def test_lr_06_live_execution_with_mismatched_prompt_freeze_hash_fails(
    runner_env: Dict[str, Any],
) -> None:
    """LR-06: Authorization artifact with mismatched allowed_prompt_freeze_sha256 fails closed."""
    bad_auth = build_dev_live_authorization_artifact(
        task_id="TEST-BAD-PF",
        authorization_id="AUTH-BAD-PF",
        allowed_phase="DEV_TUNE",
        execution_plan=runner_env["tune_plan_1p"],
        prompt_freeze=runner_env["pf_2p"],
    )
    with pytest.raises(
        DevLiveAuthorizationError, match="AUTHORIZATION_PROMPT_FREEZE_SHA256_MISMATCH"
    ):
        verify_dev_live_authorization_artifact(
            bad_auth,
            execution_plan=runner_env["tune_plan_1p"],
            prompt_freeze=runner_env["pf_1p"],
        )


def test_lr_07_live_execution_with_mismatched_code_bundle_hash_fails(
    runner_env: Dict[str, Any],
) -> None:
    """LR-07: Authorization artifact with stale scientific_code_bundle_sha256 fails closed."""
    stale_auth = build_dev_live_authorization_artifact(
        task_id="TEST-STALE-BUNDLE",
        authorization_id="AUTH-STALE-BUNDLE",
        allowed_phase="DEV_TUNE",
        execution_plan=runner_env["tune_plan_1p"],
        prompt_freeze=runner_env["pf_1p"],
        scientific_code_bundle_sha256="0" * 64,
    )
    with pytest.raises(
        ScientificCodeBundleIntegrityError, match="SCIENTIFIC_CODE_BUNDLE_MISMATCH"
    ):
        verify_dev_live_authorization_artifact(
            stale_auth,
            execution_plan=runner_env["tune_plan_1p"],
            prompt_freeze=runner_env["pf_1p"],
        )


def test_lr_08_live_execution_with_mismatched_provider_config_hash_fails(
    runner_env: Dict[str, Any], tmp_path: Path
) -> None:
    """LR-08: Cell manifest with tampered provider_config_sha256 fails before transport."""
    plan = runner_env["tune_plan_1p"]
    cell0 = plan.cells[0]
    tampered_cell = cell0.model_copy(update={"provider_config_sha256": "f" * 64})
    tampered_plan = plan.model_copy(
        update={"cells": [tampered_cell] + list(plan.cells[1:])}
    )
    transport = MockDevProviderTransport(
        _make_valid_mock_response(cell0, runner_env["valid_json_by_scenario_id"][cell0.fixture_id])
    )
    with pytest.raises(CandidateRegistryIntegrityError):
        execute_live_dev_cell(
            cell_manifest=tampered_cell,
            scenario=runner_env["scenarios_by_id"][cell0.fixture_id],
            execution_plan=tampered_plan,
            prompt_freeze=runner_env["pf_1p"],
            prompt_registry=runner_env["p1_reg"],
            authorization=runner_env["auth_tune_1p"],
            call_budget_ledger=DevCallBudgetLedger.from_execution_plan(tampered_plan),
            cell_dir=tmp_path / cell0.run_id,
            transport=transport,
        )
    assert transport.call_count == 0


def test_lr_09_live_execution_with_wrong_phase_fails(
    runner_env: Dict[str, Any],
) -> None:
    """LR-09: Authorization for DEV_TUNE cannot authorize DEV_SELECT."""
    with pytest.raises(DevLiveAuthorizationError, match="AUTHORIZATION_PHASE_MISMATCH"):
        verify_dev_live_authorization_artifact(
            runner_env["auth_tune_1p"],
            execution_plan=runner_env["select_plan"],
            prompt_freeze=runner_env["pf_1p"],
        )


def test_lr_10_final100_phase_rejected(runner_env: Dict[str, Any]) -> None:
    """LR-10: FINAL100 phase is unconditionally rejected by authorization, CLI, and ledger."""
    with pytest.raises(Final100FirewallViolationError):
        build_dev_live_authorization_artifact(
            task_id="FORBIDDEN-FINAL100",
            authorization_id="AUTH-FINAL100",
            allowed_phase="FINAL100",
            execution_plan=runner_env["tune_plan_1p"],
            prompt_freeze=runner_env["pf_1p"],
        )
    with pytest.raises(Final100FirewallViolationError):
        run_cli(["--phase", "FINAL100"])
    with pytest.raises(Final100FirewallViolationError):
        run_cli(["--final100"])


def test_lr_11_final100_scenario_id_path_and_content_rejected(
    runner_env: Dict[str, Any], tmp_path: Path
) -> None:
    """LR-11: Final100 scenario ID, path, and content are rejected fail-closed."""
    plan = runner_env["tune_plan_1p"]
    cell0 = plan.cells[0]
    scen0 = runner_env["scenarios_by_id"][cell0.fixture_id]
    ledger = DevCallBudgetLedger.from_execution_plan(plan)
    transport = MockDevProviderTransport(
        _make_valid_mock_response(cell0, runner_env["valid_json_by_scenario_id"][cell0.fixture_id])
    )

    with pytest.raises(Final100FirewallViolationError):
        execute_live_dev_cell(
            cell_manifest=cell0,
            scenario=scen0,
            execution_plan=plan,
            prompt_freeze=runner_env["pf_1p"],
            prompt_registry=runner_env["p1_reg"],
            authorization=runner_env["auth_tune_1p"],
            call_budget_ledger=ledger,
            cell_dir=tmp_path / "w06_scenarios_freeze_v1" / cell0.run_id,
            transport=transport,
        )

    final100_scen = scen0.model_copy(update={"scenario_id": "W06-S001"})
    with pytest.raises(Final100FirewallViolationError):
        execute_live_dev_cell(
            cell_manifest=cell0,
            scenario=final100_scen,
            execution_plan=plan,
            prompt_freeze=runner_env["pf_1p"],
            prompt_registry=runner_env["p1_reg"],
            authorization=runner_env["auth_tune_1p"],
            call_budget_ledger=ledger,
            cell_dir=tmp_path / cell0.run_id,
            transport=transport,
        )
    assert transport.call_count == 0


# ==============================================================================
# LR-12 & LR-13: TWO-STAGE PLAN-BEFORE-LIVE & PLAN MEMBERSHIP
# ==============================================================================


def test_lr_12_two_stage_plan_before_live_required_combined_rejected(
    runner_env: Dict[str, Any], tmp_path: Path
) -> None:
    """LR-12: Combined --create-plan + --execute-live is rejected; missing Stage A disk files rejected."""
    with pytest.raises(PlanBeforeLiveProtocolError, match="PLAN_BEFORE_LIVE_VIOLATION"):
        run_cli(["--create-plan", "--execute-live"])

    with pytest.raises(
        PlanBeforeLiveProtocolError, match="STAGE_A_EXECUTION_PLAN_MISSING"
    ):
        execute_live_dev_batch(
            execution_plan_path=tmp_path / "nonexistent_plan.json",
            prompt_freeze_path=tmp_path / "nonexistent_pf.json",
            authorization_path=tmp_path / "nonexistent_auth.json",
            batch_root_dir=tmp_path / "batch",
            prompt_registry=runner_env["p1_reg"],
            transport={},
        )


def test_lr_13_cell_not_in_frozen_execution_plan_rejected(
    runner_env: Dict[str, Any], tmp_path: Path
) -> None:
    """LR-13: Cell not belonging to the frozen execution plan is rejected before transport."""
    tune_plan = runner_env["tune_plan_1p"]
    select_cell = runner_env["select_plan"].cells[0]
    scen = runner_env["scenarios_by_id"][select_cell.fixture_id]
    ledger = DevCallBudgetLedger.from_execution_plan(tune_plan)
    transport = MockDevProviderTransport(
        _make_valid_mock_response(
            select_cell, runner_env["valid_json_by_scenario_id"][select_cell.fixture_id]
        )
    )
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="CELL_NOT_IN_FROZEN_EXECUTION_PLAN"
    ):
        execute_live_dev_cell(
            cell_manifest=select_cell,
            scenario=scen,
            execution_plan=tune_plan,
            prompt_freeze=runner_env["pf_1p"],
            prompt_registry=runner_env["p1_reg"],
            authorization=runner_env["auth_tune_1p"],
            call_budget_ledger=ledger,
            cell_dir=tmp_path / select_cell.run_id,
            transport=transport,
        )
    assert transport.call_count == 0


# ==============================================================================
# LR-14 THROUGH LR-18: FROZEN PROVIDER WIRE REQUEST PAYLOADS & RETRY=0
# ==============================================================================


def test_lr_14_c1_request_payload_matches_frozen_config_and_portable_schema_v2(
    runner_env: Dict[str, Any],
) -> None:
    """LR-14: C1 (Google Gemini) request payload matches frozen config + Portable Schema V2."""
    c1_cell = [c for c in runner_env["tune_plan_1p"].cells if c.candidate_id == "C1"][0]
    scen = runner_env["scenarios_by_id"][c1_cell.fixture_id]
    prompt_spec = runner_env["p1_reg"].prompts[0]
    req = build_frozen_provider_wire_request(
        cell_manifest=c1_cell,
        scenario=scen,
        prompt_spec=prompt_spec,
        candidate_registry=runner_env["cand_reg"],
    )
    assert req["provider"] == "google"
    assert req["candidate_id"] == "C1"
    assert req["model"] == "gemini-3.8-flash"
    assert req["config"]["response_mime_type"] == "application/json"
    assert req["config"]["thinking_config"] == {
        "thinking_level": "medium",
        "include_thoughts": False,
    }
    assert req["config"]["seed"] == 2026101508
    assert req["config"]["max_output_tokens"] == 16384
    assert req["config"]["http_options"] == {"timeout": 55000}
    assert req["config"]["tools"] is None
    assert req["config"]["automatic_function_calling"] == {"disable": True}
    assert req["omitted_parameters"] == ["temperature", "top_p", "top_k"]
    assert "temperature" not in req["config"]
    assert req["portable_generation_schema_v2_sha256"] == EXPECTED_PORTABLE_SCHEMA_V2_SHA256
    assert req["semantic_schema_sha256"] == EXPECTED_SEMANTIC_SCHEMA_SHA256
    assert (
        sha256_bytes(canonical_json_bytes(req["config"]["response_json_schema"]))
        == EXPECTED_PORTABLE_SCHEMA_V2_SHA256
    )


def test_lr_15_c2_request_payload_matches_frozen_config_and_portable_schema_v2(
    runner_env: Dict[str, Any],
) -> None:
    """LR-15: C2 (OpenAI) request payload matches frozen config + Portable Schema V2."""
    c2_cell = [c for c in runner_env["tune_plan_1p"].cells if c.candidate_id == "C2"][0]
    scen = runner_env["scenarios_by_id"][c2_cell.fixture_id]
    prompt_spec = runner_env["p1_reg"].prompts[0]
    req = build_frozen_provider_wire_request(
        cell_manifest=c2_cell,
        scenario=scen,
        prompt_spec=prompt_spec,
        candidate_registry=runner_env["cand_reg"],
    )
    assert req["provider"] == "openai"
    assert req["candidate_id"] == "C2"
    assert req["model"] == "gpt-6.1-sol"
    assert req["reasoning_effort"] == "medium"
    assert req["seed"] == 2026101508
    assert req["service_tier"] == "default"
    assert req["max_completion_tokens"] == 16384
    assert req["timeout_seconds"] == 55.0
    assert req["max_retries"] == 0
    assert req["tools"] is False
    assert req["response_format"]["type"] == "json_schema"
    assert req["response_format"]["json_schema"]["name"] == "BenchmarkPlanResponse"
    assert req["response_format"]["json_schema"]["strict"] is True
    assert (
        sha256_bytes(
            canonical_json_bytes(req["response_format"]["json_schema"]["schema"])
        )
        == EXPECTED_PORTABLE_SCHEMA_V2_SHA256
    )
    assert "temperature" not in req


def test_lr_16_c3_request_payload_matches_frozen_config_and_portable_schema_v2(
    runner_env: Dict[str, Any],
) -> None:
    """LR-16: C3 (Anthropic Claude) request payload matches frozen config + Portable Schema V2."""
    c3_cell = [c for c in runner_env["tune_plan_1p"].cells if c.candidate_id == "C3"][0]
    scen = runner_env["scenarios_by_id"][c3_cell.fixture_id]
    prompt_spec = runner_env["p1_reg"].prompts[0]
    req = build_frozen_provider_wire_request(
        cell_manifest=c3_cell,
        scenario=scen,
        prompt_spec=prompt_spec,
        candidate_registry=runner_env["cand_reg"],
    )
    assert req["provider"] == "anthropic"
    assert req["candidate_id"] == "C3"
    assert req["model"] == "claude-sonnet-5-5"
    assert req["max_tokens"] == 16384
    assert req["thinking"] == {"type": "adaptive"}
    assert req["output_config"]["effort"] == "high"
    assert req["output_config"]["format"]["type"] == "json_schema"
    assert (
        sha256_bytes(
            canonical_json_bytes(req["output_config"]["format"]["schema"])
        )
        == EXPECTED_PORTABLE_SCHEMA_V2_SHA256
    )
    assert req["seed_support"] == "UNSUPPORTED"
    assert "seed" not in req
    assert "temperature" not in req


def test_lr_17_c1_c2_c3_receive_identical_reca_context_and_shared_prompt_text(
    runner_env: Dict[str, Any],
) -> None:
    """LR-17: C1, C2, and C3 receive byte-identical RECA context and shared prompt text for the same fixture."""
    fixture_id = runner_env["tune_plan_1p"].cells[0].fixture_id
    cells_for_fix = {
        c.candidate_id: c
        for c in runner_env["tune_plan_1p"].cells
        if c.fixture_id == fixture_id
    }
    scen = runner_env["scenarios_by_id"][fixture_id]
    prompt_spec = runner_env["p1_reg"].prompts[0]

    req_c1 = build_frozen_provider_wire_request(
        cell_manifest=cells_for_fix["C1"], scenario=scen, prompt_spec=prompt_spec
    )
    req_c2 = build_frozen_provider_wire_request(
        cell_manifest=cells_for_fix["C2"], scenario=scen, prompt_spec=prompt_spec
    )
    req_c3 = build_frozen_provider_wire_request(
        cell_manifest=cells_for_fix["C3"], scenario=scen, prompt_spec=prompt_spec
    )

    user_c1 = req_c1["contents"]
    user_c2 = req_c2["messages"][1]["content"]
    user_c3 = req_c3["messages"][0]["content"]
    assert user_c1 == user_c2 == user_c3

    sys_c1 = req_c1["config"]["system_instruction"]
    sys_c2 = req_c2["messages"][0]["content"]
    sys_c3 = req_c3["system"]
    assert sys_c1 == sys_c2 == sys_c3


def test_lr_18_sdk_retry_disabled_zero_retries(runner_env: Dict[str, Any]) -> None:
    """LR-18: All provider wire requests and MockDevProviderTransport enforce zero retries."""
    fixture_id = runner_env["tune_plan_1p"].cells[0].fixture_id
    scen = runner_env["scenarios_by_id"][fixture_id]
    prompt_spec = runner_env["p1_reg"].prompts[0]
    for cid in ORDERED_CANDIDATE_IDS:
        cell = [
            c
            for c in runner_env["tune_plan_1p"].cells
            if c.fixture_id == fixture_id and c.candidate_id == cid
        ][0]
        req = build_frozen_provider_wire_request(
            cell_manifest=cell, scenario=scen, prompt_spec=prompt_spec
        )
        assert req["sdk_retry"] == 0
        assert req["transport_retry"] == 0
        assert req["manual_retry"] == 0
        assert req["retry"] == 0

    cell0 = runner_env["tune_plan_1p"].cells[0]
    transport = MockDevProviderTransport(
        _make_valid_mock_response(cell0, runner_env["valid_json_by_scenario_id"][cell0.fixture_id])
    )
    transport(cell0, {})
    with pytest.raises(ImmutableCellExecutionError, match="RETRY_FORBIDDEN"):
        transport(cell0, {})


# ==============================================================================
# LR-19 THROUGH LR-21: JOURNALING, RAW-EVIDENCE-FIRST, & ARTIFACT CHAIN
# ==============================================================================


def test_lr_19_transport_start_journal_written_before_transport_call(
    runner_env: Dict[str, Any], tmp_path: Path
) -> None:
    """LR-19: transport_journal_starting.json and request_manifest.json exist on disk when transport is invoked."""
    plan = runner_env["tune_plan_1p"]
    cell0 = plan.cells[0]
    scen0 = runner_env["scenarios_by_id"][cell0.fixture_id]
    cell_dir = tmp_path / cell0.run_id
    observed_in_transport: Dict[str, Any] = {}

    def _inspecting_transport(
        manifest: DevCellExecutionManifest, wire_req: Dict[str, Any]
    ) -> MockProviderTransportResponse:
        starting_file = cell_dir / "transport_journal_starting.json"
        req_file = cell_dir / "request_manifest.json"
        completed_file = cell_dir / "transport_journal_completed.json"
        observed_in_transport["starting_exists"] = starting_file.exists()
        observed_in_transport["req_exists"] = req_file.exists()
        observed_in_transport["completed_exists"] = completed_file.exists()
        observed_in_transport["starting_status"] = json.loads(
            starting_file.read_text(encoding="utf-8")
        )["status"]
        return _make_valid_mock_response(
            manifest, runner_env["valid_json_by_scenario_id"][manifest.fixture_id]
        )

    execute_live_dev_cell(
        cell_manifest=cell0,
        scenario=scen0,
        execution_plan=plan,
        prompt_freeze=runner_env["pf_1p"],
        prompt_registry=runner_env["p1_reg"],
        authorization=runner_env["auth_tune_1p"],
        call_budget_ledger=DevCallBudgetLedger.from_execution_plan(plan),
        cell_dir=cell_dir,
        transport=_inspecting_transport,
    )
    assert observed_in_transport["starting_exists"] is True
    assert observed_in_transport["req_exists"] is True
    assert observed_in_transport["completed_exists"] is False
    assert observed_in_transport["starting_status"] == TRANSPORT_STATUS_STARTING


def test_lr_20_raw_response_written_before_parser_or_evaluator_failure(
    runner_env: Dict[str, Any], tmp_path: Path
) -> None:
    """LR-20: Raw response, completed journal, usage metadata, and provider metadata are persisted even when parsing or model ID fails."""
    plan = runner_env["tune_plan_1p"]
    cell0 = plan.cells[0]
    scen0 = runner_env["scenarios_by_id"][cell0.fixture_id]
    cell_dir = tmp_path / cell0.run_id

    bad_resp = _make_valid_mock_response(cell0, "{not valid json").model_copy(
        update={"returned_model_id": "wrong-model-999"}
    )
    with pytest.raises(ModelIntegrityBatchStopError):
        execute_live_dev_cell(
            cell_manifest=cell0,
            scenario=scen0,
            execution_plan=plan,
            prompt_freeze=runner_env["pf_1p"],
            prompt_registry=runner_env["p1_reg"],
            authorization=runner_env["auth_tune_1p"],
            call_budget_ledger=DevCallBudgetLedger.from_execution_plan(plan),
            cell_dir=cell_dir,
            transport=bad_resp,
        )

    assert (cell_dir / "transport_journal_completed.json").exists()
    assert (cell_dir / "raw_provider_response.txt").read_text(encoding="utf-8") == "{not valid json"
    assert (cell_dir / "raw_usage_metadata.json").exists()
    assert (cell_dir / "provider_response_metadata.json").exists()
    assert (cell_dir / "execution_receipt.json").exists()


def test_lr_21_valid_cell_writes_full_artifact_chain_and_receipt(
    runner_env: Dict[str, Any], tmp_path: Path
) -> None:
    """LR-21: Valid cell execution writes all 9 immutable cell artifacts and matching SHA-256 digests."""
    plan = runner_env["tune_plan_1p"]
    cell0 = plan.cells[0]
    scen0 = runner_env["scenarios_by_id"][cell0.fixture_id]
    cell_dir = tmp_path / cell0.run_id

    receipt, eval_res = execute_live_dev_cell(
        cell_manifest=cell0,
        scenario=scen0,
        execution_plan=plan,
        prompt_freeze=runner_env["pf_1p"],
        prompt_registry=runner_env["p1_reg"],
        authorization=runner_env["auth_tune_1p"],
        call_budget_ledger=DevCallBudgetLedger.from_execution_plan(plan),
        cell_dir=cell_dir,
        transport=_make_valid_mock_response(
            cell0, runner_env["valid_json_by_scenario_id"][cell0.fixture_id]
        ),
    )

    for fname in (
        "request_manifest.json",
        "transport_journal_starting.json",
        "transport_journal_completed.json",
        "raw_provider_response.txt",
        "raw_usage_metadata.json",
        "provider_response_metadata.json",
        "parsed_plan_response.json",
        "evaluation_result.json",
        "execution_receipt.json",
    ):
        assert (cell_dir / fname).exists(), f"Missing {fname}"

    assert receipt.valid_run_and_schema is True
    assert receipt.exact_grounding_pass is True
    assert receipt.final_core_pass is True
    assert eval_res.core_scenario_pass is True


# ==============================================================================
# LR-22 THROUGH LR-29: STRICT PARSER & FAILURE TAXONOMY
# ==============================================================================


def test_lr_22_primary_parser_only_markdown_fence_fails_primary_path(
    runner_env: Dict[str, Any], tmp_path: Path
) -> None:
    """LR-22: Markdown code fence around valid JSON is rejected by strict primary parser (zero rescue)."""
    plan = runner_env["tune_plan_1p"]
    cell0 = plan.cells[0]
    scen0 = runner_env["scenarios_by_id"][cell0.fixture_id]
    valid_json = runner_env["valid_json_by_scenario_id"][cell0.fixture_id]
    fenced = f"```json\n{valid_json}\n```"

    receipt, eval_res = execute_live_dev_cell(
        cell_manifest=cell0,
        scenario=scen0,
        execution_plan=plan,
        prompt_freeze=runner_env["pf_1p"],
        prompt_registry=runner_env["p1_reg"],
        authorization=runner_env["auth_tune_1p"],
        call_budget_ledger=DevCallBudgetLedger.from_execution_plan(plan),
        cell_dir=tmp_path / cell0.run_id,
        transport=_make_valid_mock_response(cell0, fenced),
    )
    assert receipt.failure_classification == DevCellFailureClassification.MALFORMED_JSON
    assert receipt.valid_run_and_schema is False
    assert receipt.final_core_pass is False
    assert receipt.counts_in_denominator is True
    assert eval_res.core_scenario_pass is False
    assert not (tmp_path / cell0.run_id / "parsed_plan_response.json").exists()


def test_lr_23_prose_wrapper_fails_primary_path(
    runner_env: Dict[str, Any], tmp_path: Path
) -> None:
    """LR-23: Leading/trailing prose around valid JSON fails strict primary parser."""
    plan = runner_env["tune_plan_1p"]
    cell0 = plan.cells[0]
    scen0 = runner_env["scenarios_by_id"][cell0.fixture_id]
    valid_json = runner_env["valid_json_by_scenario_id"][cell0.fixture_id]
    wrapped = f"Here is your itinerary:\n{valid_json}\nEnjoy your trip!"

    receipt, eval_res = execute_live_dev_cell(
        cell_manifest=cell0,
        scenario=scen0,
        execution_plan=plan,
        prompt_freeze=runner_env["pf_1p"],
        prompt_registry=runner_env["p1_reg"],
        authorization=runner_env["auth_tune_1p"],
        call_budget_ledger=DevCallBudgetLedger.from_execution_plan(plan),
        cell_dir=tmp_path / cell0.run_id,
        transport=_make_valid_mock_response(cell0, wrapped),
    )
    assert receipt.failure_classification == DevCellFailureClassification.MALFORMED_JSON
    assert receipt.valid_run_and_schema is False
    assert receipt.final_core_pass is False
    assert receipt.counts_in_denominator is True
    assert eval_res.core_scenario_pass is False


def test_lr_24_malformed_json_classified_invalid_json_output_score_0_retained(
    runner_env: Dict[str, Any], tmp_path: Path
) -> None:
    """LR-24: Malformed JSON -> MALFORMED_JSON, score 0, retained in denominator."""
    plan = runner_env["tune_plan_1p"]
    cell0 = plan.cells[0]
    scen0 = runner_env["scenarios_by_id"][cell0.fixture_id]

    receipt, eval_res = execute_live_dev_cell(
        cell_manifest=cell0,
        scenario=scen0,
        execution_plan=plan,
        prompt_freeze=runner_env["pf_1p"],
        prompt_registry=runner_env["p1_reg"],
        authorization=runner_env["auth_tune_1p"],
        call_budget_ledger=DevCallBudgetLedger.from_execution_plan(plan),
        cell_dir=tmp_path / cell0.run_id,
        transport=_make_valid_mock_response(cell0, '{"destination": "Ha Noi", broken}'),
    )
    assert receipt.failure_classification == DevCellFailureClassification.MALFORMED_JSON
    assert receipt.counts_in_denominator is True
    assert receipt.batch_stop_required is False
    assert receipt.final_core_pass is False
    assert eval_res.run_status == BenchmarkRunStatus.UNPARSABLE_MODEL_OUTPUT
    assert eval_res.core_scenario_pass is False


def test_lr_25_schema_failure_classified_schema_validation_error_score_0_retained(
    runner_env: Dict[str, Any], tmp_path: Path
) -> None:
    """LR-25: Valid JSON violating BenchmarkPlanResponse schema -> SEMANTIC_VALIDATION_FAILURE, score 0, retained."""
    plan = runner_env["tune_plan_1p"]
    cell0 = plan.cells[0]
    scen0 = runner_env["scenarios_by_id"][cell0.fixture_id]

    receipt, eval_res = execute_live_dev_cell(
        cell_manifest=cell0,
        scenario=scen0,
        execution_plan=plan,
        prompt_freeze=runner_env["pf_1p"],
        prompt_registry=runner_env["p1_reg"],
        authorization=runner_env["auth_tune_1p"],
        call_budget_ledger=DevCallBudgetLedger.from_execution_plan(plan),
        cell_dir=tmp_path / cell0.run_id,
        transport=_make_valid_mock_response(cell0, '{"unexpected_field": 123}'),
    )
    assert receipt.failure_classification == DevCellFailureClassification.SEMANTIC_VALIDATION_FAILURE
    assert receipt.counts_in_denominator is True
    assert receipt.batch_stop_required is False
    assert receipt.final_core_pass is False
    assert eval_res.run_status == BenchmarkRunStatus.SCHEMA_NONCOMPLIANT_OUTPUT
    assert eval_res.core_scenario_pass is False


def test_lr_26_empty_or_truncated_classified_empty_or_truncated_output_score_0_retained(
    runner_env: Dict[str, Any], tmp_path: Path
) -> None:
    """LR-26: Empty/whitespace output -> MALFORMED_JSON / UNPARSABLE_MODEL_OUTPUT, score 0, retained."""
    plan = runner_env["tune_plan_1p"]
    cell0 = plan.cells[0]
    scen0 = runner_env["scenarios_by_id"][cell0.fixture_id]

    receipt, eval_res = execute_live_dev_cell(
        cell_manifest=cell0,
        scenario=scen0,
        execution_plan=plan,
        prompt_freeze=runner_env["pf_1p"],
        prompt_registry=runner_env["p1_reg"],
        authorization=runner_env["auth_tune_1p"],
        call_budget_ledger=DevCallBudgetLedger.from_execution_plan(plan),
        cell_dir=tmp_path / cell0.run_id,
        transport=_make_valid_mock_response(cell0, "   \n  "),
    )
    assert receipt.failure_classification == DevCellFailureClassification.MALFORMED_JSON
    assert receipt.counts_in_denominator is True
    assert receipt.batch_stop_required is False
    assert receipt.final_core_pass is False
    assert eval_res.core_scenario_pass is False


def test_lr_27_timeout_classified_provider_timeout_score_0_retained(
    runner_env: Dict[str, Any], tmp_path: Path
) -> None:
    """LR-27: Provider timeout -> TIMEOUT, score 0, retained in denominator, consumes 1 call."""
    plan = runner_env["tune_plan_1p"]
    cell0 = plan.cells[0]
    scen0 = runner_env["scenarios_by_id"][cell0.fixture_id]
    ledger = DevCallBudgetLedger.from_execution_plan(plan)
    timeout_resp = _make_valid_mock_response(cell0, "").model_copy(
        update={
            "simulated_failure": DevCellFailureClassification.TIMEOUT,
            "finish_reason": "TIMEOUT",
        }
    )

    receipt, eval_res = execute_live_dev_cell(
        cell_manifest=cell0,
        scenario=scen0,
        execution_plan=plan,
        prompt_freeze=runner_env["pf_1p"],
        prompt_registry=runner_env["p1_reg"],
        authorization=runner_env["auth_tune_1p"],
        call_budget_ledger=ledger,
        cell_dir=tmp_path / cell0.run_id,
        transport=timeout_resp,
    )
    assert receipt.failure_classification == DevCellFailureClassification.TIMEOUT
    assert receipt.counts_in_denominator is True
    assert receipt.batch_stop_required is False
    assert receipt.final_core_pass is False
    assert eval_res.core_scenario_pass is False
    assert ledger.consumed_calls == 1


def test_lr_28_transport_error_classified_provider_transport_error_score_0_retained(
    runner_env: Dict[str, Any], tmp_path: Path
) -> None:
    """LR-28: Provider transport error -> HTTP_ERROR / HTTP_5XX, score 0, retained in denominator, consumes 1 call."""
    plan = runner_env["tune_plan_1p"]
    cell0 = plan.cells[0]
    scen0 = runner_env["scenarios_by_id"][cell0.fixture_id]
    ledger = DevCallBudgetLedger.from_execution_plan(plan)
    err_resp = _make_valid_mock_response(cell0, "").model_copy(
        update={
            "simulated_failure": DevCellFailureClassification.HTTP_5XX,
            "finish_reason": "HTTP_503_OVERLOADED",
        }
    )

    receipt, eval_res = execute_live_dev_cell(
        cell_manifest=cell0,
        scenario=scen0,
        execution_plan=plan,
        prompt_freeze=runner_env["pf_1p"],
        prompt_registry=runner_env["p1_reg"],
        authorization=runner_env["auth_tune_1p"],
        call_budget_ledger=ledger,
        cell_dir=tmp_path / cell0.run_id,
        transport=err_resp,
    )
    assert receipt.failure_classification == DevCellFailureClassification.HTTP_5XX
    assert receipt.counts_in_denominator is True
    assert receipt.batch_stop_required is False
    assert receipt.final_core_pass is False
    assert eval_res.core_scenario_pass is False
    assert ledger.consumed_calls == 1


def test_lr_29_returned_model_mismatch_saves_raw_evidence_and_stops_batch(
    runner_env: Dict[str, Any], tmp_path: Path
) -> None:
    """LR-29: Returned model mismatch or missing returned_model_id saves raw evidence and halts batch."""
    plan = runner_env["tune_plan_1p"]
    plan_path = tmp_path / "plan.json"
    pf_path = tmp_path / "pf.json"
    auth_path = tmp_path / "auth.json"
    write_canonical_json(plan_path, plan.model_dump())
    write_canonical_json(pf_path, runner_env["pf_1p"].model_dump())
    write_canonical_json(auth_path, runner_env["auth_tune_1p"].model_dump())

    def _mismatch_on_second(
        cell: DevCellExecutionManifest, wire_req: Dict[str, Any]
    ) -> MockProviderTransportResponse:
        resp = _make_valid_mock_response(
            cell, runner_env["valid_json_by_scenario_id"][cell.fixture_id]
        )
        if cell.run_id == plan.cells[1].run_id:
            return resp.model_copy(update={"returned_model_id": None})
        return resp

    transport = MockDevProviderTransport(_mismatch_on_second)
    batch_dir = tmp_path / "batch_lr29"
    with pytest.raises(ModelIntegrityBatchStopError):
        execute_live_dev_batch(
            execution_plan_path=plan_path,
            prompt_freeze_path=pf_path,
            authorization_path=auth_path,
            batch_root_dir=batch_dir,
            prompt_registry=runner_env["p1_reg"],
            transport=transport,
            dev_bundle=runner_env["bundle"],
            candidate_registry=runner_env["cand_reg"],
            core_catalog_by_id=runner_env["core_map"],
        )

    assert transport.call_count == 2
    failed_cell_dir = batch_dir / plan.cells[1].run_id
    assert (failed_cell_dir / "raw_provider_response.txt").exists()
    saved_rec = json.loads(
        (failed_cell_dir / "execution_receipt.json").read_text(encoding="utf-8")
    )
    assert saved_rec["returned_model_id"] is None
    assert saved_rec["batch_stop_required"] is True
    assert saved_rec["counts_in_denominator"] is False


# ==============================================================================
# LR-30 THROUGH LR-33 & LR-48: USAGE NORMALIZATION & COST ACCOUNTING
# ==============================================================================


def test_lr_30_c1_usage_normalization_and_thought_tokens_cost() -> None:
    """LR-30: C1 (Gemini) usage normalization maps prompt/candidates/thoughts/cached tokens and prices thought_tokens at output rate."""
    norm = normalize_candidate_usage_metadata(
        "C1",
        {
            "prompt_token_count": 2000,
            "candidates_token_count": 800,
            "thoughts_token_count": 200,
            "cached_content_token_count": 0,
            "total_token_count": 3000,
        },
    )
    assert norm["usage_present"] is True
    assert norm["input_tokens"] == 2000
    assert norm["output_tokens"] == 800
    assert norm["thought_tokens"] == 200
    assert norm["cached_input_tokens"] == 0
    assert norm["total_tokens"] == 3000

    cost_dec = compute_canonical_cell_cost_decimal(
        input_tokens=norm["input_tokens"],
        output_tokens=norm["output_tokens"],
        thought_tokens=norm["thought_tokens"],
        cached_input_tokens=norm["cached_input_tokens"],
        cost_record=DEFAULT_COST_COMPARABILITY_BY_CANDIDATE["C1"],
    )
    # 2000 * 0.30/1M + (800 + 200) * 2.50/1M = 0.0006 + 0.0025 = 0.0031 USD
    assert cost_dec == Decimal("0.0031")


def test_lr_31_c2_usage_normalization_and_reasoning_tokens_included_in_output() -> None:
    """LR-31: C2 (OpenAI) usage normalization extracts nested reasoning_tokens and does not double-bill them."""
    norm = normalize_candidate_usage_metadata(
        "C2",
        {
            "input_tokens": 1000,
            "output_tokens": 500,
            "total_tokens": 1500,
            "output_tokens_details": {"reasoning_tokens": 150},
            "input_tokens_details": {"cached_tokens": 0},
        },
    )
    assert norm["usage_present"] is True
    assert norm["input_tokens"] == 1000
    assert norm["output_tokens"] == 500
    assert norm["reasoning_tokens"] == 150
    assert norm["cached_input_tokens"] == 0

    cost_dec = compute_canonical_cell_cost_decimal(
        input_tokens=norm["input_tokens"],
        output_tokens=norm["output_tokens"],
        reasoning_tokens=norm["reasoning_tokens"],
        cached_input_tokens=norm["cached_input_tokens"],
        cost_record=DEFAULT_COST_COMPARABILITY_BY_CANDIDATE["C2"],
    )
    # 1000 * 2.50/1M + 500 * 10.00/1M = 0.0025 + 0.0050 = 0.0075 USD (reasoning_tokens NOT double-added)
    assert cost_dec == Decimal("0.0075")


def test_lr_32_c3_usage_normalization_and_cache_thinking_tokens_handling() -> None:
    """LR-32: C3 (Anthropic) usage normalization handles cache_read, cache_creation, and thinking_tokens."""
    norm = normalize_candidate_usage_metadata(
        "C3",
        {
            "input_tokens": 1000,
            "output_tokens": 400,
            "thinking_tokens": 100,
            "cache_read_input_tokens": 200,
            "cache_creation_input_tokens": 50,
        },
    )
    assert norm["usage_present"] is True
    assert norm["input_tokens"] == 1000
    assert norm["output_tokens"] == 400
    assert norm["thinking_tokens"] == 100
    assert norm["cache_read_input_tokens"] == 200
    assert norm["cache_creation_input_tokens"] == 50
    assert norm["cached_input_tokens"] == 250


def test_lr_33_missing_usage_marks_non_comparable_cost(
    runner_env: Dict[str, Any], tmp_path: Path
) -> None:
    """LR-33: Missing usage metadata marks authoritative_usage_available=False and canonical_cost_usd_decimal=None."""
    plan = runner_env["tune_plan_1p"]
    cell0 = plan.cells[0]
    scen0 = runner_env["scenarios_by_id"][cell0.fixture_id]
    no_usage_resp = _make_valid_mock_response(
        cell0, runner_env["valid_json_by_scenario_id"][cell0.fixture_id]
    ).model_copy(
        update={
            "authoritative_usage_available": False,
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "raw_usage_metadata": None,
        }
    )

    receipt, _ = execute_live_dev_cell(
        cell_manifest=cell0,
        scenario=scen0,
        execution_plan=plan,
        prompt_freeze=runner_env["pf_1p"],
        prompt_registry=runner_env["p1_reg"],
        authorization=runner_env["auth_tune_1p"],
        call_budget_ledger=DevCallBudgetLedger.from_execution_plan(plan),
        cell_dir=tmp_path / cell0.run_id,
        transport=no_usage_resp,
    )
    assert receipt.authoritative_usage_available is False
    assert receipt.canonical_cost_usd_decimal is None
    assert receipt.canonical_cost_usd is None


# ==============================================================================
# LR-34 THROUGH LR-39: IMMUTABILITY, LEDGER, CRASH AMBIGUITY, & ATOMIC WRITES
# ==============================================================================


def test_lr_34_existing_cell_receipt_prevents_rerun_before_transport(
    runner_env: Dict[str, Any], tmp_path: Path
) -> None:
    """LR-34: Existing cell receipt on disk blocks any rerun before transport is invoked."""
    plan = runner_env["tune_plan_1p"]
    cell0 = plan.cells[0]
    scen0 = runner_env["scenarios_by_id"][cell0.fixture_id]
    cell_dir = tmp_path / cell0.run_id
    resp = _make_valid_mock_response(
        cell0, runner_env["valid_json_by_scenario_id"][cell0.fixture_id]
    )

    execute_live_dev_cell(
        cell_manifest=cell0,
        scenario=scen0,
        execution_plan=plan,
        prompt_freeze=runner_env["pf_1p"],
        prompt_registry=runner_env["p1_reg"],
        authorization=runner_env["auth_tune_1p"],
        call_budget_ledger=DevCallBudgetLedger.from_execution_plan(plan),
        cell_dir=cell_dir,
        transport=resp,
    )

    second_transport = MockDevProviderTransport(resp)
    with pytest.raises(ImmutableCellExecutionError):
        execute_live_dev_cell(
            cell_manifest=cell0,
            scenario=scen0,
            execution_plan=plan,
            prompt_freeze=runner_env["pf_1p"],
            prompt_registry=runner_env["p1_reg"],
            authorization=runner_env["auth_tune_1p"],
            call_budget_ledger=DevCallBudgetLedger.from_execution_plan(plan),
            cell_dir=cell_dir,
            transport=second_transport,
        )
    assert second_transport.call_count == 0


def test_lr_35_duplicate_cell_in_ledger_rejected(runner_env: Dict[str, Any]) -> None:
    """LR-35: Duplicate cell reservation in DevCallBudgetLedger is rejected with DuplicateDevCellAttemptError."""
    plan = runner_env["tune_plan_1p"]
    cell0 = plan.cells[0]
    ledger = DevCallBudgetLedger.from_execution_plan(plan)
    ledger.reserve_call(cell0)
    with pytest.raises(DuplicateDevCellAttemptError):
        ledger.reserve_call(cell0)


def test_lr_36_call_budget_exceeded_rejected_before_transport(
    runner_env: Dict[str, Any],
) -> None:
    """LR-36: Exceeding maximum_live_generation_calls raises DevCallBudgetExhaustedError before transport."""
    plan = runner_env["tune_plan_1p"]
    cell0, cell1 = plan.cells[0], plan.cells[1]
    small_ledger = DevCallBudgetLedger(
        phase="DEV_TUNE",
        maximum_live_generation_calls=1,
        allowed_run_ids=[cell0.run_id, cell1.run_id],
        allowed_cell_keys=[
            (cell0.phase, cell0.prompt_id, cell0.candidate_id, cell0.fixture_id, cell0.attempt_number),
            (cell1.phase, cell1.prompt_id, cell1.candidate_id, cell1.fixture_id, cell1.attempt_number),
        ],
        allowed_candidate_ids=list(ORDERED_CANDIDATE_IDS),
        allowed_fixture_ids=[cell0.fixture_id, cell1.fixture_id],
    )
    small_ledger.reserve_call(cell0)
    with pytest.raises(DevCallBudgetExhaustedError, match="CALL_BUDGET_EXHAUSTED"):
        small_ledger.reserve_call(cell1)


def test_lr_37_crash_after_transport_starting_marks_unknown_and_stops_batch(
    runner_env: Dict[str, Any], tmp_path: Path
) -> None:
    """LR-37: Simulated crash after TRANSPORT_STARTING writes ATTEMPT_STATUS_UNKNOWN_AFTER_TRANSPORT and stops batch without rerun."""
    plan = runner_env["tune_plan_1p"]
    cell0 = plan.cells[0]
    scen0 = runner_env["scenarios_by_id"][cell0.fixture_id]
    cell_dir = tmp_path / cell0.run_id

    write_transport_journal_starting(
        cell_dir,
        cell_manifest=cell0,
        runtime_head_sha=cell0.code_basis_commit_sha,
        authorization_id=runner_env["auth_tune_1p"].authorization_id,
    )

    transport = MockDevProviderTransport(
        _make_valid_mock_response(
            cell0, runner_env["valid_json_by_scenario_id"][cell0.fixture_id]
        )
    )
    with pytest.raises(
        CrashAmbiguityBatchStopError, match=ATTEMPT_STATUS_UNKNOWN_AFTER_TRANSPORT
    ):
        execute_live_dev_cell(
            cell_manifest=cell0,
            scenario=scen0,
            execution_plan=plan,
            prompt_freeze=runner_env["pf_1p"],
            prompt_registry=runner_env["p1_reg"],
            authorization=runner_env["auth_tune_1p"],
            call_budget_ledger=DevCallBudgetLedger.from_execution_plan(plan),
            cell_dir=cell_dir,
            transport=transport,
        )

    assert transport.call_count == 0
    unknown_file = cell_dir / "transport_journal_unknown_after_transport.json"
    assert unknown_file.exists()
    unknown_payload = json.loads(unknown_file.read_text(encoding="utf-8"))
    assert unknown_payload["status"] == ATTEMPT_STATUS_UNKNOWN_AFTER_TRANSPORT
    assert unknown_payload["rerun_permitted"] is False


def test_lr_38_transport_completed_is_separate_append_only_artifact(
    runner_env: Dict[str, Any], tmp_path: Path
) -> None:
    """LR-38: transport_journal_completed.json is a separate append-only artifact and does not overwrite transport_journal_starting.json."""
    plan = runner_env["tune_plan_1p"]
    cell0 = plan.cells[0]
    scen0 = runner_env["scenarios_by_id"][cell0.fixture_id]
    cell_dir = tmp_path / cell0.run_id

    execute_live_dev_cell(
        cell_manifest=cell0,
        scenario=scen0,
        execution_plan=plan,
        prompt_freeze=runner_env["pf_1p"],
        prompt_registry=runner_env["p1_reg"],
        authorization=runner_env["auth_tune_1p"],
        call_budget_ledger=DevCallBudgetLedger.from_execution_plan(plan),
        cell_dir=cell_dir,
        transport=_make_valid_mock_response(
            cell0, runner_env["valid_json_by_scenario_id"][cell0.fixture_id]
        ),
    )

    starting = json.loads(
        (cell_dir / "transport_journal_starting.json").read_text(encoding="utf-8")
    )
    completed = json.loads(
        (cell_dir / "transport_journal_completed.json").read_text(encoding="utf-8")
    )
    assert starting["status"] == TRANSPORT_STATUS_STARTING
    assert completed["status"] == TRANSPORT_STATUS_COMPLETED
    assert starting["run_id"] == completed["run_id"] == cell0.run_id


def test_lr_39_atomic_write_leaves_no_partial_target_file_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """LR-39: Atomic write cleans up temporary .part file and leaves no target file if os.replace fails."""
    target = tmp_path / "atomic_test.json"

    def _failing_replace(src: str, dst: str) -> None:
        raise OSError("Simulated atomic rename failure")

    monkeypatch.setattr(os, "replace", _failing_replace)
    with pytest.raises(OSError, match="Simulated atomic rename failure"):
        write_immutable_atomic_bytes(target, b'{"test": true}\n')

    assert not target.exists()
    assert list(tmp_path.glob("*.part")) == []


# ==============================================================================
# LR-40 THROUGH LR-44: FULL MOCK BATCH EXECUTION (60, 120, 180, 15) & DISJOINTNESS
# ==============================================================================


def test_lr_40_dev_tune_1_prompt_batch_executes_60_mock_cells(
    runner_env: Dict[str, Any], tmp_path: Path
) -> None:
    """LR-40: DEV-TUNE 1-prompt batch executes exactly 60 mock cells (20 fixtures * 3 candidates)."""
    plan = runner_env["tune_plan_1p"]
    plan_path = tmp_path / "tune_1p_plan.json"
    pf_path = tmp_path / "pf_1p.json"
    auth_path = tmp_path / "auth_1p.json"
    write_canonical_json(plan_path, plan.model_dump())
    write_canonical_json(pf_path, runner_env["pf_1p"].model_dump())
    write_canonical_json(auth_path, runner_env["auth_tune_1p"].model_dump())

    transport = MockDevProviderTransport(
        lambda c, _: _make_valid_mock_response(
            c, runner_env["valid_json_by_scenario_id"][c.fixture_id]
        )
    )
    receipts, ledger = execute_live_dev_batch(
        execution_plan_path=plan_path,
        prompt_freeze_path=pf_path,
        authorization_path=auth_path,
        batch_root_dir=tmp_path / "cells_60",
        prompt_registry=runner_env["p1_reg"],
        transport=transport,
        dev_bundle=runner_env["bundle"],
        candidate_registry=runner_env["cand_reg"],
        core_catalog_by_id=runner_env["core_map"],
    )
    assert len(receipts) == DEV_TUNE_MAX_CALLS_ONE_PROMPT == 60
    assert transport.call_count == 60
    assert ledger.reserved_calls == 60
    assert ledger.consumed_calls == 60


def test_lr_41_dev_tune_2_prompt_batch_executes_120_mock_cells(
    runner_env: Dict[str, Any], tmp_path: Path
) -> None:
    """LR-41: DEV-TUNE 2-prompt batch executes exactly 120 mock cells (20 fixtures * 3 candidates * 2 prompts)."""
    plan = runner_env["tune_plan_2p"]
    plan_path = tmp_path / "tune_2p_plan.json"
    pf_path = tmp_path / "pf_2p.json"
    auth_path = tmp_path / "auth_2p.json"
    write_canonical_json(plan_path, plan.model_dump())
    write_canonical_json(pf_path, runner_env["pf_2p"].model_dump())
    write_canonical_json(auth_path, runner_env["auth_tune_2p"].model_dump())

    transport = MockDevProviderTransport(
        lambda c, _: _make_valid_mock_response(
            c, runner_env["valid_json_by_scenario_id"][c.fixture_id]
        )
    )
    receipts, ledger = execute_live_dev_batch(
        execution_plan_path=plan_path,
        prompt_freeze_path=pf_path,
        authorization_path=auth_path,
        batch_root_dir=tmp_path / "cells_120",
        prompt_registry=runner_env["p1_p2_reg"],
        transport=transport,
        dev_bundle=runner_env["bundle"],
        candidate_registry=runner_env["cand_reg"],
        core_catalog_by_id=runner_env["core_map"],
    )
    assert len(receipts) == DEV_TUNE_MAX_CALLS_TWO_PROMPTS == 120
    assert transport.call_count == 120
    assert ledger.reserved_calls == 120
    assert ledger.consumed_calls == 120


def test_lr_42_dev_select_batch_executes_180_mock_cells(
    runner_env: Dict[str, Any], tmp_path: Path
) -> None:
    """LR-42: DEV-SELECT batch executes exactly 180 mock cells (60 fixtures * 3 candidates * 1 prompt)."""
    plan = runner_env["select_plan"]
    plan_path = tmp_path / "select_plan.json"
    pf_path = tmp_path / "pf_1p.json"
    auth_path = tmp_path / "auth_select.json"
    write_canonical_json(plan_path, plan.model_dump())
    write_canonical_json(pf_path, runner_env["pf_1p"].model_dump())
    write_canonical_json(auth_path, runner_env["auth_select"].model_dump())

    transport = MockDevProviderTransport(
        lambda c, _: _make_valid_mock_response(
            c, runner_env["valid_json_by_scenario_id"][c.fixture_id]
        )
    )
    receipts, ledger = execute_live_dev_batch(
        execution_plan_path=plan_path,
        prompt_freeze_path=pf_path,
        authorization_path=auth_path,
        batch_root_dir=tmp_path / "cells_180",
        prompt_registry=runner_env["p1_reg"],
        transport=transport,
        dev_bundle=runner_env["bundle"],
        candidate_registry=runner_env["cand_reg"],
        core_catalog_by_id=runner_env["core_map"],
    )
    assert len(receipts) == DEV_SELECT_MAX_CALLS == 180
    assert transport.call_count == 180
    assert ledger.reserved_calls == 180
    assert ledger.consumed_calls == 180


def test_lr_43_stochasticity_blocked_without_winner_and_executes_15_cells_after_winner(
    runner_env: Dict[str, Any], tmp_path: Path
) -> None:
    """LR-43: STOCHASTICITY batch is blocked without a DEV-SELECT winner and executes 15 mock cells after winner selection."""
    fake_winner_result = DevSelectModelSelectionResult(
        winner_selected=True,
        selected_candidate_id="C1",
        locked_prompt_id="P1",
        selected_at_stage="STAGE_3_ADMINISTRATIVE_TIEBREAK",
        cost_criterion_status="COMPARABLE",
        is_administrative_tiebreak=True,
        administrative_tiebreak_claims_scientific_superiority=False,
        used_final100=False,
        candidate_aggregates={},
        cost_comparability_by_candidate=DEFAULT_COST_COMPARABILITY_BY_CANDIDATE,
        reduction_trace=[],
    )
    stoch_plan = build_stochasticity_diagnostic_plan(
        dev_select_result=fake_winner_result,
        locked_prompt_spec=runner_env["p1_reg"].prompts[0],
        dev_bundle=runner_env["bundle"],
        candidate_registry=runner_env["cand_reg"],
    )
    stoch_auth = build_dev_live_authorization_artifact(
        task_id="TEST-AUTH-STOCH",
        authorization_id="AUTH-STOCH-001",
        allowed_phase="STOCHASTICITY",
        execution_plan=stoch_plan,
        prompt_freeze=runner_env["pf_1p"],
    )

    plan_path = tmp_path / "stoch_plan.json"
    pf_path = tmp_path / "pf_1p.json"
    auth_path = tmp_path / "auth_stoch.json"
    write_canonical_json(plan_path, stoch_plan.model_dump())
    write_canonical_json(pf_path, runner_env["pf_1p"].model_dump())
    write_canonical_json(auth_path, stoch_auth.model_dump())

    with pytest.raises(StochasticityGateViolationError):
        execute_live_dev_batch(
            execution_plan_path=plan_path,
            prompt_freeze_path=pf_path,
            authorization_path=auth_path,
            batch_root_dir=tmp_path / "cells_stoch_blocked",
            prompt_registry=runner_env["p1_reg"],
            transport=lambda c, _: _make_valid_mock_response(
                c, runner_env["valid_json_by_scenario_id"][c.fixture_id]
            ),
            dev_select_result=None,
        )

    transport = MockDevProviderTransport(
        lambda c, _: _make_valid_mock_response(
            c, runner_env["valid_json_by_scenario_id"][c.fixture_id]
        )
    )
    receipts, ledger = execute_live_dev_batch(
        execution_plan_path=plan_path,
        prompt_freeze_path=pf_path,
        authorization_path=auth_path,
        batch_root_dir=tmp_path / "cells_stoch_15",
        prompt_registry=runner_env["p1_reg"],
        transport=transport,
        dev_bundle=runner_env["bundle"],
        candidate_registry=runner_env["cand_reg"],
        dev_select_result=fake_winner_result,
        core_catalog_by_id=runner_env["core_map"],
    )
    assert len(receipts) == STOCHASTICITY_MAX_CALLS == 15
    assert transport.call_count == 15
    assert ledger.consumed_calls == 15


def test_lr_44_dev_tune_cannot_use_dev_select_fixtures_and_vice_versa(
    runner_env: Dict[str, Any],
) -> None:
    """LR-44: DEV-TUNE ledger rejects DEV-SELECT fixtures and DEV-SELECT ledger rejects DEV-TUNE fixtures."""
    tune_ledger = DevCallBudgetLedger.from_execution_plan(runner_env["tune_plan_1p"])
    select_cell = runner_env["select_plan"].cells[0]
    with pytest.raises(PlanBeforeLiveProtocolError, match="UNEXPECTED_FIXTURE_IN_LEDGER"):
        tune_ledger.reserve_call(select_cell)

    select_ledger = DevCallBudgetLedger.from_execution_plan(runner_env["select_plan"])
    tune_cell = runner_env["tune_plan_1p"].cells[0]
    with pytest.raises(PlanBeforeLiveProtocolError, match="UNEXPECTED_FIXTURE_IN_LEDGER"):
        select_ledger.reserve_call(tune_cell)


# ==============================================================================
# LR-45 THROUGH LR-50: SECRETS, DRY-RUN, KILL-SWITCH, USAGE, RECEIPTS, & READY STATE
# ==============================================================================


def test_lr_45_secret_strings_in_transport_exception_and_metadata_redacted(
    runner_env: Dict[str, Any], tmp_path: Path
) -> None:
    """LR-45: Secret strings (AIza..., sk-ant-..., sk-proj-..., Bearer ...) are redacted and never written raw to disk."""
    syn_g = "AIza" + ("S" * 24)
    syn_a = "sk-ant-" + ("F" * 24)
    syn_o = "sk-proj-" + ("P" * 24)
    syn_b = "Bear" + "er " + ("J" * 24)
    raw_secret_text = (
        f"Fatal auth error with key {syn_g} and {syn_a} and {syn_o} and {syn_b}"
    )
    sanitized = sanitize_runner_text(raw_secret_text)
    assert syn_g not in sanitized
    assert syn_a not in sanitized
    assert syn_o not in sanitized
    assert ("J" * 24) not in sanitized
    assert REDACTED_SECRET_PLACEHOLDER in sanitized

    nested = {
        "api_key": "raw-secret-value",
        "nested": {"openai_api_key": syn_o, "safe": "ok"},
    }
    sanitized_struct = sanitize_runner_structure(nested)
    assert sanitized_struct["api_key"] == REDACTED_SECRET_PLACEHOLDER
    assert sanitized_struct["nested"]["openai_api_key"] == REDACTED_SECRET_PLACEHOLDER
    assert sanitized_struct["nested"]["safe"] == "ok"

    with pytest.raises(SecretLeakageViolationError):
        assert_no_secrets_in_payload(nested, context="UNIT_TEST")


def test_lr_46_dry_run_executes_zero_transport_calls_and_validates_full_batch(
    runner_env: Dict[str, Any], tmp_path: Path
) -> None:
    """LR-46: Dry-run mode validates execution plan, prompt freeze, authorization, and serializes all 60 requests with 0 transport calls."""
    plan_path = tmp_path / "dry_run_plan.json"
    pf_path = tmp_path / "dry_run_pf.json"
    auth_path = tmp_path / "dry_run_auth.json"
    write_canonical_json(plan_path, runner_env["tune_plan_1p"].model_dump())
    write_canonical_json(pf_path, runner_env["pf_1p"].model_dump())
    write_canonical_json(auth_path, runner_env["auth_tune_1p"].model_dump())

    report = run_dev_live_runner_dry_run(
        execution_plan=plan_path,
        prompt_freeze=pf_path,
        authorization=auth_path,
        batch_root_dir=tmp_path / "dry_run_cells",
        dev_bundle=runner_env["bundle"],
        candidate_registry=runner_env["cand_reg"],
    )
    assert report["mode"] == "dry_run"
    assert report["dry_run"] is True
    assert report["transport_status"] == TRANSPORT_STATUS_NOT_INVOKED
    assert report["live_provider_calls"] == 0
    assert report["provider_cost_usd"] == 0
    assert report["planned_call_count"] == 60
    assert report["authorization_verified"] is True
    assert len(report["serialized_request_sha256_by_run_id"]) == 60
    assert not (tmp_path / "dry_run_cells").exists()


def test_lr_47_network_kill_switch_blocks_outbound_connections() -> None:
    """LR-47: Network kill-switch actively blocks socket.connect, socket.create_connection, and urllib requests."""
    with pytest.raises(RuntimeError, match="NETWORK_KILL_SWITCH_TRIGGERED"):
        socket.create_connection(("example.com", 443), timeout=1)

    with pytest.raises(Exception):
        urllib.request.urlopen("https://generativelanguage.googleapis.com", timeout=1)


def test_lr_48_raw_provider_usage_payload_preserved_alongside_normalized_fields(
    runner_env: Dict[str, Any], tmp_path: Path
) -> None:
    """LR-48: raw_usage_metadata.json preserves the exact provider-native usage dictionary alongside normalized fields."""
    plan = runner_env["tune_plan_1p"]
    c2_cell = [c for c in plan.cells if c.candidate_id == "C2"][0]
    scen = runner_env["scenarios_by_id"][c2_cell.fixture_id]
    cell_dir = tmp_path / c2_cell.run_id

    execute_live_dev_cell(
        cell_manifest=c2_cell,
        scenario=scen,
        execution_plan=plan,
        prompt_freeze=runner_env["pf_1p"],
        prompt_registry=runner_env["p1_reg"],
        authorization=runner_env["auth_tune_1p"],
        call_budget_ledger=DevCallBudgetLedger.from_execution_plan(plan),
        cell_dir=cell_dir,
        transport=_make_valid_mock_response(
            c2_cell, runner_env["valid_json_by_scenario_id"][c2_cell.fixture_id]
        ),
    )

    raw_usage_file = json.loads(
        (cell_dir / "raw_usage_metadata.json").read_text(encoding="utf-8")
    )
    assert raw_usage_file["raw_usage_metadata"]["output_tokens_details"] == {
        "reasoning_tokens": 100
    }
    assert raw_usage_file["normalized_usage_metadata"]["reasoning_tokens"] == 100
    assert raw_usage_file["normalized_usage_metadata"]["input_tokens"] == 1000
    assert raw_usage_file["normalized_usage_metadata"]["output_tokens"] == 600


def test_lr_49_historical_receipts_remain_untouched() -> None:
    """LR-49: Historical receipts (harness_01, QA-01, FIX-01, QA-02, 01B, 01C, 01D) remain byte-identical to develop."""
    for rel_path, expected_sha256 in HISTORICAL_IMMUTABLE_RECEIPTS.items():
        target = REPO_ROOT / rel_path
        assert target.exists(), f"Missing historical receipt {rel_path}"
        actual_sha256 = sha256_bytes(target.read_bytes())
        assert actual_sha256 == expected_sha256, (
            f"Historical receipt {rel_path} was modified: {actual_sha256} != {expected_sha256}"
        )


def test_lr_50_dev_live_execution_remains_unauthorized_by_default_and_receipt_matches() -> None:
    """LR-50: DEV live execution remains unauthorized by default and w06_dev_live_runner_01_receipt_v1.json is verified."""
    assert DEFAULT_RUNNER_RECEIPT_PATH.exists()
    persisted = json.loads(DEFAULT_RUNNER_RECEIPT_PATH.read_text(encoding="utf-8"))
    computed = build_dev_live_runner_01_receipt_payload()
    assert persisted == computed

    assert persisted["artifact_id"] == RUNNER_RECEIPT_ARTIFACT_ID
    assert persisted["task_id"] == TASK_ID_DEV_LIVE_RUNNER_01
    assert persisted["base_develop_sha"] == EXPECTED_BASE_DEVELOP_SHA_RUNNER_01
    assert persisted["live_provider_calls"] == 0
    assert persisted["provider_cost_usd"] == 0
    assert persisted["runner_implemented"] is True
    assert persisted["runner_in_scientific_code_bundle"] is True
    assert persisted["prompt_freeze_status"] == PROMPT_FREEZE_STATUS_NOT_YET_FROZEN
    assert persisted["live_authorization_present"] is False
    assert persisted["dev_model_execution_allowed"] is False
    assert persisted["dev_tune_execution_started"] is False
    assert persisted["dev_select_execution_started"] is False
    assert persisted["stochasticity_execution_started"] is False
    assert persisted["winner_selected"] is False
    assert persisted["final100_used"] is False
    assert persisted["next_gate"] == NEXT_GATE_RUNNER_QA_01
    assert persisted["status"] == "READY_FOR_CHATGPT_AUDIT"
