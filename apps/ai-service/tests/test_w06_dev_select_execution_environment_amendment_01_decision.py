"""Offline verification test suite for W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-FORMAL-DECISION-FREEZE.

Tests Section 23 requirements:
- exact authoritative base develop SHA (`bc913ed61097f26db8eae87b9fe47d1869dc3ec5`) and PREP bindings
- selected policy IDs exactly match ChatGPT decision (`SECONDARY_POST_HOC_EXECUTION_ENVIRONMENT_STABILIZATION_TRACK`, `OPTION_B_CONSERVATIVE_RELIABILITY_ENVIRONMENT`, `T3_CANDIDATE_180S`, `P1_FIXED_2000MS_INTER_CALL_DELAY`, `R0_STRICT_ZERO_RETRY`, `POLICY_F3_ENGINEERING_READINESS_SUBSET_PLUS_AMENDED_COMPARATIVE_SET`, `S2_READINESS_CANARY_PLUS_COMPARATIVE_180`)
- timeout_ms == 180000 symmetrically across C1, C2, C3; scientific wording does not claim guaranteed completion
- inter_call_delay_ms == 2000, fixed=true, deterministic=true, adaptive=false, response_dependent=false; does not claim to prevent HTTP 503
- retry == 0 (`automatic_retry=0`, `transport_retry=0`, `manual_retry=0`, `llm_repair=0`, `semantic_repair=0`, `fallback=false`)
- selected call budget == 189 max (`readiness_canary_assigned_calls=9`, `comparative_assigned_calls=180`, `calls_per_candidate_max=63`), no variable `3..9` semantics in selected policy
- exact canary count == 9
- exact canary fixture IDs == `["W06-DEV-TUNE-007", "W06-DEV-TUNE-011", "W06-DEV-TUNE-015"]`
- structural balance: destinations == `{"Hà Nội", "Đà Nẵng", "Hạ Long"}`, days == `{2, 3, 4}`, interest_counts == `{1, 2, 3}`
- exact 9-cell matrix/order (`01..09`)
- `selection_weight == 0`
- no result-based fixture selection rationale (`prior_model_quality_output_used = false`, `prior_canary_success_or_failure_used = false`)
- schema/core failure cannot fail operational readiness (`successful_provider_response_failing_schema_or_core_is_operational_pass = true`)
- one operational failure means future comparative authorization false (`CANARY_GATE_PASS = false`, `AMENDED_COMPARATIVE_AUTHORIZED = false`, `RETURN_TO_CHATGPT_HOLD`)
- canary PASS cannot automatically authorize comparative execution (`canary_pass_automatically_launches_comparative_execution = false`, `separate_chatgpt_authorization_gate_required_before_180_comparative_calls = true`)
- P1/C1/C2/C3/schema/evaluator unchanged
- primary immutable (`PRIMARY_EXPERIMENT_MUTATED = false`, `PRIMARY_RESULTS_REPLACED = false`, `PRIMARY_DENOMINATORS_CHANGED = false`)
- Final100 untouched (`FINAL100_USED = false`, `NO-GO`)
- model winner null (`MODEL_WINNER_SELECTED = false`, `SELECTED_MODEL_ID = null`)
- stochasticity false (`STOCHASTICITY_EXECUTION_STARTED = false`)
- no secrets, network kill switch, `LIVE_PROVIDER_CALLS_NEW = 0`
- `EXTERNAL_PRICING_REFRESH_REQUIRED_BEFORE_AUTHORIZATION` retained (`hard_maximum_claimed = false`)
- artifact tamper rejection & raw-evidence write guard
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import urllib.request

import httpx
import httpx2
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "scripts"
AI_SERVICE_DIR = REPO_ROOT / "apps" / "ai-service"
for _p in (SCRIPTS_DIR, AI_SERVICE_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from app.evaluation.dev_live_runner import (  # noqa: E402
    PlanBeforeLiveProtocolError,
    assert_no_secrets_in_payload,
)
from app.evaluation.dev_selection_harness import (  # noqa: E402
    FORBIDDEN_FINAL100_BUNDLE_SHA256,
    FORBIDDEN_P11_MANIFEST_SHA256,
    SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS,
    compute_scientific_code_bundle_sha256,
    normalize_lf_bytes,
    sha256_bytes,
)
import freeze_w06_dev_select_execution_environment_amendment_01_decision as dec_mod  # noqa: E402
from run_w06_dev_select_live_v1 import OutboundNetworkBlockedError  # noqa: E402


@pytest.fixture(scope="module")
def disk_decision_payload() -> dict:
    path = REPO_ROOT / dec_mod.DECISION_ARTIFACT_REL_PATH
    assert path.is_file(), f"Missing decision artifact: {path}"
    return json.loads(normalize_lf_bytes(path.read_bytes()).decode("utf-8"))


@pytest.fixture(scope="module")
def disk_canary_manifest() -> dict:
    path = REPO_ROOT / dec_mod.CANARY_MANIFEST_REL_PATH
    assert path.is_file(), f"Missing canary manifest: {path}"
    return json.loads(normalize_lf_bytes(path.read_bytes()).decode("utf-8"))


def test_ead_01_authoritative_base_and_prep_bindings(
    disk_decision_payload: dict, disk_canary_manifest: dict
) -> None:
    """EAD-01: Exact authoritative base SHA (`bc913ed61097f26db8eae87b9fe47d1869dc3ec5`) and PREP authority bindings."""
    expected_base = "bc913ed61097f26db8eae87b9fe47d1869dc3ec5"
    assert dec_mod.AUTHORITATIVE_BASE_DEVELOP_SHA == expected_base
    assert disk_decision_payload["authoritative_base_develop_sha"] == expected_base
    assert disk_canary_manifest["authoritative_base_develop_sha"] == expected_base
    assert disk_decision_payload["PREP_GATE"] == "CLOSED"
    assert (
        disk_decision_payload["CHATGPT_FINAL_METHODOLOGY_DECISION_FOR_FREEZE"]
        == "APPROVED_FOR_FORMAL_FREEZE"
    )

    ba = disk_decision_payload["bound_authorities"]
    assert (
        ba["prep_artifact_file_sha256"]
        == "e8786c4f538b86c8aa1d6b2c0cfb4afd6b8b6a1efa5b51799e44bd6bdd5a9a91"
    )
    assert (
        ba["prep_artifact_internal_sha256"]
        == "49c24e65690cb4fb947d2733ddf8b019d863046cf955d9415eec1d16e9eaaf7a"
    )
    assert (
        ba["scientific_code_bundle_sha256"]
        == "0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3"
    )
    assert (
        ba["primary_raw_evidence_tree_sha256"]
        == "d5c4e53952500655b656a624657a3cf1ec7aae685809c9e53a318459cc319817"
    )
    assert (
        ba["primary_results_manifest_file_sha256"]
        == "1d303e1c07b627c3f3eb87287b744f55ba3f6d3d85bd5cec36959b01919d26c0"
    )
    assert (
        ba["primary_results_freeze_receipt_file_sha256"]
        == "c021094e26277d41664c4ae2f0560b7684435b6002c5b7ba742a17808c5b07a4"
    )
    assert (
        ba["diagnostic_artifact_file_sha256"]
        == "b729883505ecfc98f15917347239ea6d09cede106691b155026891996391e692"
    )
    assert (
        ba["diagnostic_artifact_internal_sha256"]
        == "509528413e1d9eb8408943867be21f83dc2dda72acd53fe9028e3c37c7db05c8"
    )
    assert (
        ba["dev_fixtures_freeze_sha256"]
        == "bb0f051446ea3da8229298f22f4ce92b4db20751695273c6d01b7766da044050"
    )
    assert (
        ba["canary_manifest_file_sha256"]
        == dec_mod.EXPECTED_CANARY_MANIFEST_FILE_SHA256
    )
    assert (
        ba["canary_manifest_internal_sha256"]
        == dec_mod.EXPECTED_CANARY_MANIFEST_INTERNAL_SHA256
    )

    cat_proc = subprocess.run(
        ["git", "cat-file", "-e", f"{expected_base}^{{commit}}"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if cat_proc.returncode == 0:
        proc = subprocess.run(
            ["git", "merge-base", "--is-ancestor", expected_base, "HEAD"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0


def test_ead_02_selected_policy_ids_and_parameters_exact_match(
    disk_decision_payload: dict,
) -> None:
    """EAD-02: Selected policy IDs, timeout (180000ms), pacing (2000ms), retry (0), and call budget (189 max, 9 canary, 180 comparative)."""
    bundle = disk_decision_payload["frozen_selected_policy_bundle"]
    assert (
        bundle["track_classification"]
        == "SECONDARY_POST_HOC_EXECUTION_ENVIRONMENT_STABILIZATION_TRACK"
    )
    assert (
        bundle["fairness_policy_id"]
        == "OPTION_B_CONSERVATIVE_RELIABILITY_ENVIRONMENT"
    )
    assert (
        bundle["fixture_policy_id"]
        == "POLICY_F3_ENGINEERING_READINESS_SUBSET_PLUS_AMENDED_COMPARATIVE_SET"
    )

    t_pol = bundle["timeout_policy"]
    assert t_pol["timeout_policy_id"] == "T3_CANDIDATE_180S"
    assert t_pol["timeout_ms"] == 180000
    assert t_pol["timeout_seconds"] == 180
    assert t_pol["applied_symmetrically_to_candidates"] == ["C1", "C2", "C3"]
    assert t_pol["timeout_ms_by_candidate"] == {
        "C1": 180000,
        "C2": 180000,
        "C3": 180000,
    }
    assert t_pol["guarantees_completion"] is False
    assert (
        t_pol["scientific_wording"]
        == "This removes the frozen 55s client-side cutoff from the secondary configuration and materially reduces client-side right-censoring risk. It does NOT guarantee completion. Provider-side deadlines, capacity failures, quota errors, or other transport failures may still prevent observation."
    )

    p_pol = bundle["pacing_policy"]
    assert p_pol["pacing_policy_id"] == "P1_FIXED_2000MS_INTER_CALL_DELAY"
    assert p_pol["inter_call_delay_ms"] == 2000
    assert p_pol["fixed"] is True
    assert p_pol["deterministic"] is True
    assert p_pol["adaptive"] is False
    assert p_pol["response_dependent"] is False
    assert p_pol["prevents_provider_http_503_or_high_demand_failures_claimed"] is False
    assert (
        p_pol["scientific_wording"]
        == "Pacing bounds client-issued request cadence only. It MUST NOT be claimed to prevent provider HTTP 503/high-demand failures."
    )

    r_pol = bundle["retry_policy"]
    assert r_pol == {
        "automatic_retry": 0,
        "fallback": False,
        "llm_repair": 0,
        "manual_retry": 0,
        "retry": 0,
        "retry_policy_id": "R0_STRICT_ZERO_RETRY",
        "semantic_repair": 0,
        "transport_retry": 0,
    }

    b_pol = bundle["call_budget_policy"]
    assert b_pol["call_budget_policy_id"] == "S2_READINESS_CANARY_PLUS_COMPARATIVE_180"
    assert b_pol["readiness_canary_assigned_calls"] == 9
    assert b_pol["comparative_assigned_calls"] == 180
    assert b_pol["maximum_generation_calls"] == 189
    assert b_pol["calls_per_candidate_max"] == 63
    assert b_pol["exact_canary_assigned_matrix_cells"] == 9
    assert b_pol["variable_canary_range_removed"] is True

    # Ensure "3..9" does not appear anywhere in the decision JSON or canary manifest JSON
    decision_text = (REPO_ROOT / dec_mod.DECISION_ARTIFACT_REL_PATH).read_text(
        encoding="utf-8"
    )
    canary_text = (REPO_ROOT / dec_mod.CANARY_MANIFEST_REL_PATH).read_text(
        encoding="utf-8"
    )
    assert "3..9" not in decision_text
    assert "3..9" not in canary_text


def test_ead_03_exact_canary_fixtures_and_structural_balance(
    disk_decision_payload: dict, disk_canary_manifest: dict
) -> None:
    """EAD-03: Exact canary fixture IDs (007, 011, 015), structural balance, and non-result-based selection rationale."""
    cf = disk_decision_payload["canary_fixtures"]
    assert cf["fixture_count"] == 3
    assert cf["fixture_ids"] == [
        "W06-DEV-TUNE-007",
        "W06-DEV-TUNE-011",
        "W06-DEV-TUNE-015",
    ]
    assert disk_canary_manifest["fixture_ids"] == cf["fixture_ids"]
    assert (
        cf["bound_fixture_source_file"]
        == "data/evaluation/w06/w06_dev_fixtures_freeze_v1.json"
    )
    assert (
        cf["bound_fixture_source_sha256"]
        == "bb0f051446ea3da8229298f22f4ce92b4db20751695273c6d01b7766da044050"
    )

    fixtures = cf["fixtures"]
    assert len(fixtures) == 3

    assert fixtures[0]["canary_fixture_slot"] == "A"
    assert fixtures[0]["fixture_id"] == "W06-DEV-TUNE-007"
    assert fixtures[0]["destination"] == "Hà Nội"
    assert fixtures[0]["days"] == 4
    assert fixtures[0]["interest_count"] == 3

    assert fixtures[1]["canary_fixture_slot"] == "B"
    assert fixtures[1]["fixture_id"] == "W06-DEV-TUNE-011"
    assert fixtures[1]["destination"] == "Đà Nẵng"
    assert fixtures[1]["days"] == 3
    assert fixtures[1]["interest_count"] == 2

    assert fixtures[2]["canary_fixture_slot"] == "C"
    assert fixtures[2]["fixture_id"] == "W06-DEV-TUNE-015"
    assert fixtures[2]["destination"] == "Hạ Long"
    assert fixtures[2]["days"] == 2
    assert fixtures[2]["interest_count"] == 1

    assert {f["destination"] for f in fixtures} == {"Hà Nội", "Đà Nẵng", "Hạ Long"}
    assert {f["days"] for f in fixtures} == {2, 3, 4}
    assert {f["interest_count"] for f in fixtures} == {1, 2, 3}

    rationale = cf["fixture_selection_rationale"]
    assert rationale["method"] == "DETERMINISTIC_STRUCTURAL_COVERAGE_ONLY"
    assert rationale["prior_model_quality_output_used"] is False
    assert rationale["prior_canary_success_or_failure_used"] is False


def test_ead_04_exact_9_cell_canary_call_matrix_and_order(
    disk_decision_payload: dict, disk_canary_manifest: dict
) -> None:
    """EAD-04: Exact 9-cell canary call matrix and order (01..09), pacing=2000ms, retry=0, selection_weight=0."""
    matrix = disk_decision_payload["canary_call_matrix_and_order"]
    assert matrix["assigned_cell_count"] == 9
    assert matrix["all_9_cells_assigned_once"] is True
    assert matrix["alternate_fixtures_permitted"] is False
    assert matrix["reruns_permitted"] is False
    assert matrix["retries_permitted"] is False
    assert matrix["inter_call_delay_ms"] == 2000

    expected_labels = [
        "01 W06-DEV-TUNE-007 × C1",
        "02 W06-DEV-TUNE-007 × C2",
        "03 W06-DEV-TUNE-007 × C3",
        "04 W06-DEV-TUNE-011 × C1",
        "05 W06-DEV-TUNE-011 × C2",
        "06 W06-DEV-TUNE-011 × C3",
        "07 W06-DEV-TUNE-015 × C1",
        "08 W06-DEV-TUNE-015 × C2",
        "09 W06-DEV-TUNE-015 × C3",
    ]
    assert matrix["matrix_summary"] == expected_labels

    cells = matrix["cells"]
    assert cells == disk_canary_manifest["cells"]
    assert len(cells) == 9
    for idx, cell in enumerate(cells, start=1):
        assert cell["order_index"] == idx
        assert cell["matrix_label"] == expected_labels[idx - 1]
        assert cell["prompt_id"] == "P1"
        assert cell["attempt_number"] == 1
        assert cell["selection_weight"] == 0
        assert cell["timeout_ms"] == 180000
        assert cell["retry"] == 0
        assert cell["automatic_retry"] == 0
        assert cell["transport_retry"] == 0
        assert cell["manual_retry"] == 0
        assert cell["llm_repair"] == 0
        assert cell["semantic_repair"] == 0
        assert cell["fallback"] is False
        expected_delay = 2000 if idx < 9 else 0
        assert cell["inter_call_delay_ms_before_next_cell"] == expected_delay


def test_ead_05_canary_selection_weight_operational_pass_and_gate_rules(
    disk_decision_payload: dict,
) -> None:
    """EAD-05: Selection weight = 0, planner quality firewall, and 9/9 canary gate rule."""
    rules = disk_decision_payload["canary_gate_and_operational_pass_rules"]
    weight_pol = rules["canary_selection_weight_policy"]
    assert weight_pol == {
        "can_alter_prompt_model_schema_or_evaluator_parameters": False,
        "can_contribute_to_dev_select_comparative_denominator": False,
        "can_contribute_to_final100": False,
        "can_contribute_to_stochasticity": False,
        "can_select_model_winner": False,
        "selection_weight": 0,
    }

    cell_pass = rules["operational_canary_cell_pass_rule"]
    assert len(cell_pass["all_conditions_required_for_operational_pass"]) == 13
    pq_fw = cell_pass["planner_quality_firewall"]
    assert pq_fw["planner_quality_determines_operational_pass_or_fail"] is False
    assert (
        pq_fw["successful_provider_response_failing_schema_or_core_is_operational_pass"]
        is True
    )
    assert set(pq_fw["excluded_planner_quality_metrics"]) == {
        "VALID_RUN_AND_SCHEMA_RATE",
        "EXACT_GROUNDING_PASS_RATE",
        "OPENING_HOUR_COMPLIANCE",
        "BUDGET_METRIC",
        "FINAL_CORE_PASS",
    }

    gate_rule = rules["canary_gate_rule"]
    assert gate_rule["required_operational_pass_cell_count"] == 9
    assert gate_rule["total_assigned_canary_cells"] == 9
    assert gate_rule["if_any_single_cell_operationally_fails"] == {
        "AMENDED_COMPARATIVE_AUTHORIZED": False,
        "CANARY_GATE_PASS": False,
        "next_status": "CHATGPT_HOLD",
    }
    assert gate_rule["action_on_any_failure"] == "RETURN_TO_CHATGPT_HOLD"
    for val in gate_rule["automatic_adjustments_on_failure_permitted"].values():
        assert val is False


def test_ead_06_comparative_batch_policy_and_separate_authorization_gate(
    disk_decision_payload: dict,
) -> None:
    """EAD-06: Section 13 comparative batch policy and mandatory separate ChatGPT authorization gate."""
    comp = disk_decision_payload["comparative_batch_policy"]
    assert (
        comp["comparative_fixture_id_range"]
        == "W06-DEV-SELECT-001..W06-DEV-SELECT-060"
    )
    assert comp["comparative_fixture_count"] == 60
    assert comp["candidate_ids"] == ["C1", "C2", "C3"]
    assert comp["assigned_comparative_cells"] == 180
    assert comp["prompt_id"] == "P1"
    assert comp["prompt_unchanged"] is True
    assert comp["portable_generation_schema_v2_unchanged"] is True
    assert comp["evaluator_semantics_unchanged"] is True
    assert comp["primary_model_selection_metrics"] == [
        "VALID_RUN_AND_SCHEMA_RATE",
        "EXACT_GROUNDING_PASS_RATE",
        "FINAL_CORE_PASS_RATE",
    ]
    assert comp["practical_tie_survivor_threshold_percentage_points"] == 10
    assert comp["practical_tie_survivor_threshold_cells"] == 6
    assert comp["practical_tie_survivor_threshold_denominator"] == 60
    assert comp["practical_tie_survivor_threshold_ratio"] == "0.1"
    assert comp["canary_pass_automatically_launches_comparative_execution"] is False
    assert (
        comp[
            "separate_chatgpt_authorization_gate_required_before_180_comparative_calls"
        ]
        is True
    )


def test_ead_07_frozen_scientific_invariants_and_primary_immutability(
    disk_decision_payload: dict,
) -> None:
    """EAD-07: Sections 14..18 frozen scientific invariants, primary immutability, Final100, and firewall flags."""
    inv = disk_decision_payload["frozen_scientific_invariants"]
    assert inv["prompt_id"] == "P1"
    assert inv["prompt_p1_unchanged"] is True
    assert inv["candidate_models"] == {
        "C1": "gemini-3.8-flash",
        "C2": "gpt-6.1-sol",
        "C3": "claude-sonnet-5-5",
    }
    assert inv["candidate_reasoning_settings_unchanged"] is True
    assert inv["portable_schema_v2_unchanged"] is True
    assert inv["semantic_schema_unchanged"] is True
    assert inv["evaluator_semantics_unchanged"] is True
    assert inv["primary_selection_metrics_unchanged"] is True
    assert inv["practical_tie_rule_unchanged"] is True
    assert inv["final100_unchanged"] is True
    assert inv["retry0_unchanged"] is True
    assert inv["primary_180_evidence_and_results_unchanged"] is True
    assert inv["fourth_model_added"] is False

    immut = disk_decision_payload["primary_experiment_immutability"]
    assert (
        immut["classification"]
        == "PRIMARY_PREREGISTERED_ONE_SHOT_OPERATIONAL_BENCHMARK"
    )
    assert immut["primary_experiment_mutated"] is False
    assert immut["primary_results_replaced"] is False
    assert immut["primary_denominators_changed"] is False
    assert immut["reclassification_or_rerun_or_replacement_permitted"] is False
    assert immut["primary_denominators_by_candidate"] == {
        "C1": 60,
        "C2": 60,
        "C3": 60,
    }
    assert immut["primary_counts_total"] == {
        "HTTP_429": 35,
        "HTTP_5XX": 10,
        "HTTP_ERROR": 60,
        "NONE": 9,
        "TIMEOUT": 66,
    }

    assert disk_decision_payload["AMENDMENT_METHODOLOGY_SELECTED"] is True
    assert disk_decision_payload["AMENDMENT_APPROVED"] is False
    assert disk_decision_payload["AMENDED_LIVE_AUTHORIZED"] is False
    assert disk_decision_payload["AMENDED_CANARY_LIVE_AUTHORIZED"] is False
    assert disk_decision_payload["AMENDED_COMPARATIVE_LIVE_AUTHORIZED"] is False
    assert disk_decision_payload["AMENDED_LIVE_EXECUTED"] is False
    assert disk_decision_payload["LIVE_PROVIDER_CALLS_NEW"] == 0
    assert disk_decision_payload["PRIMARY_EXPERIMENT_MUTATED"] is False
    assert disk_decision_payload["PRIMARY_RESULTS_REPLACED"] is False
    assert disk_decision_payload["PRIMARY_DENOMINATORS_CHANGED"] is False
    assert disk_decision_payload["FINAL100_USED"] is False
    assert disk_decision_payload["MODEL_WINNER_SELECTED"] is False
    assert disk_decision_payload["SELECTED_MODEL_ID"] is None
    assert disk_decision_payload["STOCHASTICITY_EXECUTION_STARTED"] is False


def test_ead_08_provider_readiness_and_pricing_boundaries(
    disk_decision_payload: dict,
) -> None:
    """EAD-08: Sections 19..20 provider readiness boundary and pricing status."""
    pr = disk_decision_payload["provider_readiness_boundary"]
    assert (
        pr["owner_and_provider_attestation_separate_from_live_readiness_canary"]
        is True
    )
    assert pr["candidates"]["C1"]["max_authorized_calls_under_s2"] == 63
    assert pr["candidates"]["C1"]["no_free_tier_20_rpd_ceiling_required"] is True
    assert pr["candidates"]["C2"]["max_authorized_calls_under_s2"] == 63
    assert pr["candidates"]["C3"]["max_authorized_calls_under_s2"] == 63
    assert pr["secret_safety_invariants"] == {
        "print_billing_or_project_or_org_ids": False,
        "print_secret_hashes": False,
        "print_secret_prefixes_or_suffixes": False,
        "print_secret_values": False,
    }

    pricing = disk_decision_payload["pricing_and_cost_boundary"]
    assert (
        pricing["current_price_input_status"]
        == "EXTERNAL_PRICING_REFRESH_REQUIRED_BEFORE_AUTHORIZATION"
    )
    assert pricing["hard_maximum_claimed"] is False
    assert pricing["live_pricing_calls_performed_in_decision_freeze"] == 0


def test_ead_09_scientific_bundle_and_final100_unchanged() -> None:
    """EAD-09: Scientific code bundle and Final100 authorities are byte-identical to develop."""
    assert (
        compute_scientific_code_bundle_sha256(REPO_ROOT)
        == "0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3"
    )
    final100_path = REPO_ROOT / "data/evaluation/w06/w06_scenarios_freeze_v1.json"
    p11_path = REPO_ROOT / "data/evaluation/w06/w06_p11_assignment_manifest_v1.json"
    assert (
        sha256_bytes(normalize_lf_bytes(final100_path.read_bytes()))
        == FORBIDDEN_FINAL100_BUNDLE_SHA256
    )
    assert (
        sha256_bytes(normalize_lf_bytes(p11_path.read_bytes()))
        == FORBIDDEN_P11_MANIFEST_SHA256
    )

    plan_doc = json.loads(
        (
            REPO_ROOT / "data/evaluation/w06/w06_dev_select_execution_plan_v1.json"
        ).read_text(encoding="utf-8")
    )
    expected_file_hashes = {
        entry["path"]: entry["sha256"]
        for entry in plan_doc["scientific_code_bundle_file_hashes"]
    }
    assert set(expected_file_hashes.keys()) == set(
        SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS
    )
    for sci_rel, exp_sha in expected_file_hashes.items():
        actual_sha = sha256_bytes(
            normalize_lf_bytes((REPO_ROOT / sci_rel).read_bytes())
        )
        assert actual_sha == exp_sha, (
            f"Scientific code bundle file modified: {sci_rel}"
        )


def test_ead_10_no_api_key_or_dotenv_read_and_network_kill_switch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """EAD-10: Verification never reads API keys or `.env`, and NetworkKillSwitchGuard blocks all network egress."""
    for env_key in ("GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(env_key, raising=False)

    orig_open = Path.open

    def _guarded_open(self: Path, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        if self.name == ".env" or self.name.startswith(".env."):
            raise AssertionError(f"Forbidden .env read attempted: {self}")
        if self.name == "w06_scenarios_freeze_v1.json" and (
            "rb" not in args and kwargs.get("mode") != "rb"
        ):
            raise AssertionError(f"Forbidden Final100 scenario text read: {self}")
        return orig_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", _guarded_open)
    summary = dec_mod.verify_w06_execution_environment_amendment_decision_freeze(
        repo_root=REPO_ROOT
    )
    assert summary["verified"] is True
    assert summary["live_provider_calls_new"] == 0

    with dec_mod.NetworkKillSwitchGuard() as guard:
        with pytest.raises(OutboundNetworkBlockedError):
            socket.create_connection(("example.com", 443))
        with pytest.raises(OutboundNetworkBlockedError):
            socket.getaddrinfo("example.com", 443)
        with pytest.raises(OutboundNetworkBlockedError):
            urllib.request.urlopen("https://example.com")
        with pytest.raises(OutboundNetworkBlockedError):
            httpx.get("https://example.com")
        with pytest.raises(OutboundNetworkBlockedError):
            httpx2.get("https://example.com")
        assert len(guard.blocked_attempts) == 5


def test_ead_11_artifact_tamper_rejection_and_secret_scan(
    tmp_path: Path, disk_decision_payload: dict, disk_canary_manifest: dict
) -> None:
    """EAD-11: Verifier rejects tampered decision/canary artifacts or raw-evidence write paths, and rejects injected secrets."""
    assert_no_secrets_in_payload(
        disk_decision_payload, context="TEST_DECISION_DISK"
    )
    assert_no_secrets_in_payload(
        disk_canary_manifest, context="TEST_CANARY_MANIFEST_DISK"
    )

    poisoned = copy.deepcopy(disk_decision_payload)
    poisoned["injected_secret"] = "sk-ant-" + "api03-" + ("A" * 36)
    with pytest.raises(Exception):
        assert_no_secrets_in_payload(poisoned, context="TEST_POISONED")

    with pytest.raises(
        PlanBeforeLiveProtocolError, match="RAW_EVIDENCE_WRITE_FORBIDDEN"
    ):
        dec_mod._assert_not_inside_raw_evidence(
            REPO_ROOT
            / "data/evaluation/w06/live_dev_select_primary_v1/tamper.json",
            REPO_ROOT,
        )

    tampered_file = tmp_path / "tampered_decision.json"
    tampered_payload = copy.deepcopy(disk_decision_payload)
    tampered_payload["AMENDED_LIVE_AUTHORIZED"] = True
    tampered_file.write_text(
        json.dumps(tampered_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    orig_rel = dec_mod.DECISION_ARTIFACT_REL_PATH
    try:
        rel_tmp = os.path.relpath(tampered_file, REPO_ROOT)
    except ValueError:
        rel_tmp = None

    if rel_tmp is not None:
        dec_mod.DECISION_ARTIFACT_REL_PATH = rel_tmp
        try:
            with pytest.raises(
                PlanBeforeLiveProtocolError,
                match="DECISION_ARTIFACT_INTERNAL_SHA256_TAMPERED",
            ):
                dec_mod.verify_w06_execution_environment_amendment_decision_freeze(
                    repo_root=REPO_ROOT
                )
        finally:
            dec_mod.DECISION_ARTIFACT_REL_PATH = orig_rel


def test_ead_12_cli_verify_only_and_markdown_documentation() -> None:
    """EAD-12: CLI `--verify-only` exits 0 and research markdown covers all required sections."""
    proc = subprocess.run(
        [
            sys.executable,
            str(
                REPO_ROOT
                / "scripts/freeze_w06_dev_select_execution_environment_amendment_01_decision.py"
            ),
            "--verify-only",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["verified"] is True
    assert (
        out["decision_artifact_file_sha256"]
        == dec_mod.EXPECTED_DECISION_ARTIFACT_FILE_SHA256
    )
    assert (
        out["decision_artifact_internal_sha256"]
        == dec_mod.EXPECTED_DECISION_ARTIFACT_INTERNAL_SHA256
    )
    assert (
        out["canary_manifest_file_sha256"]
        == dec_mod.EXPECTED_CANARY_MANIFEST_FILE_SHA256
    )
    assert (
        out["canary_manifest_internal_sha256"]
        == dec_mod.EXPECTED_CANARY_MANIFEST_INTERNAL_SHA256
    )

    doc_path = REPO_ROOT / dec_mod.DECISION_DOC_REL_PATH
    assert doc_path.is_file()
    doc_text = doc_path.read_text(encoding="utf-8")
    for required_token in (
        "APPROVED_FOR_FORMAL_FREEZE",
        "SECONDARY_POST_HOC_EXECUTION_ENVIRONMENT_STABILIZATION_TRACK",
        "OPTION_B_CONSERVATIVE_RELIABILITY_ENVIRONMENT",
        "T3_CANDIDATE_180S",
        "P1_FIXED_2000MS_INTER_CALL_DELAY",
        "R0_STRICT_ZERO_RETRY",
        "POLICY_F3_ENGINEERING_READINESS_SUBSET_PLUS_AMENDED_COMPARATIVE_SET",
        "S2_READINESS_CANARY_PLUS_COMPARATIVE_180",
        "01 W06-DEV-TUNE-007 × C1",
        "09 W06-DEV-TUNE-015 × C3",
        "EXTERNAL_PRICING_REFRESH_REQUIRED_BEFORE_AUTHORIZATION",
    ):
        assert required_token in doc_text
