"""Offline verification test suite for W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-PREP.

Tests Section 17 requirements:
- exact base SHA binding (`811255a7dd00234d63184ab483e9f88b1f2d8554`)
- raw tree binding (`d5c4e53952500655b656a624657a3cf1ec7aae685809c9e53a318459cc319817`)
- results manifest & freeze receipt bindings
- diagnostic artifact binding (`b729883505ecfc98f15917347239ea6d09cede106691b155026891996391e692`)
- primary counts unchanged (`HTTP_429=35, HTTP_5XX=10, HTTP_ERROR=60, NONE=9, TIMEOUT=66`)
- no primary mutation (`PRIMARY_EXPERIMENT_MUTATED=false`, `PRIMARY_RESULTS_REPLACED=false`, `PRIMARY_DENOMINATORS_CHANGED=false`)
- no model winner (`MODEL_WINNER_SELECTED=false`, `SELECTED_MODEL_ID=null`)
- no Final100 usage (`FINAL100_USED=false`)
- no stochasticity execution (`STOCHASTICITY_EXECUTION_STARTED=false`)
- no API-key or `.env` reads during prep/verification
- hard network kill switch enforcement
- zero live provider calls (`LIVE_PROVIDER_CALLS_NEW=0`)
- deterministic timeout option table & counterfactual firewall
- deterministic pacing and retry policy options
- fairness policy options (`OPTION_A`, `OPTION_B`, `OPTION_C`)
- fixture-policy alternatives (`POLICY_F1`, `POLICY_F2`, `POLICY_F3`)
- call-budget alternatives (`S1`, `S2`, `S3`) & cost planning envelopes
- project owner action matrix (`POA-01..POA-04`)
- advisory recommendation (`FINAL_METHODOLOGY_DECISION_AUTHORITY = CHATGPT`)
- amendment approval/authorization/execution flags all `false`
- scientific code bundle unchanged (`0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3`)
- no scientific runner/harness diff
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
import prepare_w06_dev_select_execution_environment_amendment_01 as prep_mod  # noqa: E402
from run_w06_dev_select_live_v1 import OutboundNetworkBlockedError  # noqa: E402


@pytest.fixture(scope="module")
def computed_prep_payload() -> dict:
    return prep_mod.compute_w06_execution_environment_amendment_prep_payload(
        repo_root=REPO_ROOT
    )


@pytest.fixture(scope="module")
def disk_prep_payload() -> dict:
    path = REPO_ROOT / prep_mod.PREP_ARTIFACT_REL_PATH
    assert path.is_file(), f"Missing prep artifact: {path}"
    return json.loads(normalize_lf_bytes(path.read_bytes()).decode("utf-8"))


def test_eap_01_exact_base_sha_binding(
    computed_prep_payload: dict, disk_prep_payload: dict
) -> None:
    """EAP-01: Exact authoritative base develop SHA binding (`811255a7dd00234d63184ab483e9f88b1f2d8554`)."""
    expected_base = "811255a7dd00234d63184ab483e9f88b1f2d8554"
    assert prep_mod.AUTHORITATIVE_BASE_DEVELOP_SHA == expected_base
    assert computed_prep_payload["authoritative_base_develop_sha"] == expected_base
    assert disk_prep_payload["authoritative_base_develop_sha"] == expected_base

    proc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", expected_base, "HEAD"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0


def test_eap_02_raw_tree_and_results_freeze_bindings(
    computed_prep_payload: dict, disk_prep_payload: dict
) -> None:
    """EAP-02: Exact bindings to frozen raw evidence tree, manifest, and freeze receipt."""
    immut = disk_prep_payload["primary_experiment_immutability"]
    assert (
        immut["raw_evidence_tree_sha256"]
        == "d5c4e53952500655b656a624657a3cf1ec7aae685809c9e53a318459cc319817"
    )
    assert (
        immut["results_manifest_file_sha256"]
        == "1d303e1c07b627c3f3eb87287b744f55ba3f6d3d85bd5cec36959b01919d26c0"
    )
    assert (
        immut["results_freeze_receipt_file_sha256"]
        == "c021094e26277d41664c4ae2f0560b7684435b6002c5b7ba742a17808c5b07a4"
    )
    assert computed_prep_payload["primary_experiment_immutability"] == immut


def test_eap_03_diagnostic_artifact_binding(
    computed_prep_payload: dict, disk_prep_payload: dict
) -> None:
    """EAP-03: Exact binding to frozen failure diagnostic artifact file and internal SHA256."""
    immut = disk_prep_payload["primary_experiment_immutability"]
    assert (
        immut["diagnostic_artifact_file_sha256"]
        == "b729883505ecfc98f15917347239ea6d09cede106691b155026891996391e692"
    )
    assert (
        immut["diagnostic_artifact_internal_sha256"]
        == "509528413e1d9eb8408943867be21f83dc2dda72acd53fe9028e3c37c7db05c8"
    )
    diag_path = REPO_ROOT / prep_mod.EXPECTED_DIAGNOSTIC_ARTIFACT_REL_PATH
    assert (
        sha256_bytes(normalize_lf_bytes(diag_path.read_bytes()))
        == immut["diagnostic_artifact_file_sha256"]
    )


def test_eap_04_primary_counts_and_denominators_unchanged(
    disk_prep_payload: dict,
) -> None:
    """EAP-04: Primary failure classification counts and 60-cell denominators are unchanged."""
    immut = disk_prep_payload["primary_experiment_immutability"]
    assert (
        immut["classification"]
        == "PRIMARY_PREREGISTERED_ONE_SHOT_OPERATIONAL_BENCHMARK"
    )
    assert (
        immut["primary_failure_classification_authority"]
        == "execution_receipt.failure_classification"
    )
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
    assert immut["primary_counts_by_candidate"] == {
        "C1": {
            "HTTP_429": 35,
            "HTTP_5XX": 10,
            "HTTP_ERROR": 0,
            "NONE": 1,
            "TIMEOUT": 14,
        },
        "C2": {
            "HTTP_429": 0,
            "HTTP_5XX": 0,
            "HTTP_ERROR": 0,
            "NONE": 8,
            "TIMEOUT": 52,
        },
        "C3": {
            "HTTP_429": 0,
            "HTTP_5XX": 0,
            "HTTP_ERROR": 60,
            "NONE": 0,
            "TIMEOUT": 0,
        },
    }


def test_eap_05_evidence_supported_reasons_and_harness_integrity(
    disk_prep_payload: dict,
) -> None:
    """EAP-05: Section 3 evidence-supported reasons for C1, C2, C3 and harness integrity."""
    reasons = disk_prep_payload["evidence_supported_reasons_for_amendment_consideration"]
    assert reasons["C1"]["http_429_free_tier_quota_exhaustion_ratio"] == "35/60"
    assert reasons["C1"]["http_503_high_demand_capacity_failure_ratio"] == "10/60"
    assert reasons["C1"]["primary_timeout_breakdown"] == {
        "client_read_timeout_count": 4,
        "server_http_504_deadline_exceeded_count": 10,
        "total_timeout_ratio": "14/60",
    }

    assert reasons["C2"]["client_api_timeout_error_ratio"] == "52/60"
    assert reasons["C2"]["timeout_latency_range_ms"] == [55078.0, 55797.0]
    assert reasons["C2"]["frozen_timeout_ms"] == 55000
    assert reasons["C2"]["none_completed_ratio"] == "8/60"
    assert reasons["C2"]["all_completed_cells_scenario_days"] == 2
    assert reasons["C2"]["completed_3_day_or_4_day_cells"] == 0

    assert reasons["C3"]["http_400_invalid_request_error_ratio"] == "60/60"
    assert (
        reasons["C3"]["provider_declared_billing_credit_rejection_ratio"] == "60/60"
    )
    assert reasons["C3"]["model_generations_observed"] == 0

    hb = reasons["harness_and_binding_integrity"]
    assert hb == {
        "cell_hash_chain_valid": "180/180",
        "harness_or_binding_inconsistency_observed": False,
        "model_id_mismatch_count": 0,
        "request_identity_match": "180/180",
        "rerun_cells": 0,
        "retry_calls": 0,
    }


def test_eap_06_amendment_classification_and_scope_boundary(
    disk_prep_payload: dict,
) -> None:
    """EAP-06: Section 4 classification and Section 5 frozen scientific scope boundary."""
    cls_info = disk_prep_payload["amendment_classification"]
    assert (
        cls_info["classification"]
        == "SECONDARY_POST_HOC_EXECUTION_ENVIRONMENT_STABILIZATION_TRACK"
    )
    assert cls_info["primary_experiment_remains_reportable"] is True
    assert set(cls_info["forbidden_descriptions"]) == {
        "replacement of primary benchmark",
        "retroactive preregistration",
        "correction of primary results",
        "rerun of failed cells",
        "continuation of the same primary batch",
    }

    scope = disk_prep_payload["amendment_scope_boundary"]
    assert scope["prompt_id"] == "P1"
    assert scope["prompt_retuning_proposed"] is False
    assert scope["candidates"] == {
        "C1": "gemini-3.8-flash",
        "C2": "gpt-6.1-sol",
        "C3": "claude-sonnet-5-5",
    }
    assert scope["candidate_model_change_proposed"] is False
    assert scope["fourth_model_addition_proposed"] is False
    assert scope["portable_schema_v2_unchanged"] is True
    assert scope["semantic_schema_unchanged"] is True
    assert scope["evaluator_semantics_unchanged"] is True
    assert scope["primary_model_selection_metrics"] == [
        "VALID_RUN_AND_SCHEMA_RATE",
        "EXACT_GROUNDING_PASS_RATE",
        "FINAL_CORE_PASS_RATE",
    ]
    assert scope["ten_percentage_point_survivor_rule_unchanged"] is True
    assert scope["ten_percentage_point_survivor_rule_threshold"] == "0.1"
    assert scope["final100_used_for_amendment_calibration"] is False


def test_eap_07_timeout_option_table_deterministic_and_counterfactual_firewall(
    disk_prep_payload: dict,
) -> None:
    """EAP-07: Section 6B & Section 8 timeout decision-support table and counterfactual firewall."""
    t_pol = disk_prep_payload["timeout_policy_options"]
    assert t_pol["current_frozen_timeout_ms"] == 55000
    assert t_pol["current_frozen_timeout_seconds"] == 55
    assert t_pol["selected_timeout_option_id"] is None
    assert t_pol["selection_authority"] == "CHATGPT"
    assert (
        t_pol["counterfactual_firewall"]["counterfactual_success_rate_estimated"]
        is False
    )

    options = t_pol["candidate_timeout_options"]
    seconds_list = [o["timeout_seconds"] for o in options]
    assert seconds_list == [55, 90, 120, 180, 240]
    for opt in options:
        assert opt["timeout_ms"] == opt["timeout_seconds"] * 1000
        assert opt["scientific_rationale"]
        assert opt["engineering_rationale"]
        wc = opt["estimated_worst_case_sequential_wall_clock_impact"]
        assert wc["s1_180_cells_unpaced_worst_case_seconds"] == 180 * opt["timeout_seconds"]
        assert opt["risk_of_still_censoring_long_responses"]
        assert opt["risk_of_excessively_long_stuck_requests"]
        assert opt["comparability_implications"]


def test_eap_08_pacing_and_retry_policy_options(disk_prep_payload: dict) -> None:
    """EAP-08: Section 6C pacing options and Section 6D retry policy (`retry = 0` default)."""
    p_pol = disk_prep_payload["pacing_policy_options"]
    assert p_pol["selected_pacing_option_id"] is None
    assert p_pol["pacing_implemented_in_prep"] is False
    inv = p_pol["invariants_for_all_pacing_options"]
    assert inv == {
        "fixed_before_execution": True,
        "applies_by_explicit_fair_rule": True,
        "reacts_to_success_or_failure": False,
        "performs_retry": False,
        "adapts_to_provider_responses_or_headers": False,
    }
    assert [o["inter_call_delay_ms"] for o in p_pol["options"]] == [0, 2000, 5000]

    r_pol = disk_prep_payload["retry_policy_options"]
    assert r_pol["default_proposal_option_id"] == "R0_STRICT_ZERO_RETRY"
    r0 = r_pol["options"][0]
    r1 = r_pol["options"][1]
    assert r0["retry"] == 0
    assert (
        r1["recommendation_status"]
        == "NOT_RECOMMENDED_WITHOUT_MAJOR_METHODOLOGY_CHANGE"
    )


def test_eap_09_provider_readiness_attestation_and_owner_action_matrix(
    disk_prep_payload: dict,
) -> None:
    """EAP-09: Section 7 provider-readiness design and Section 14 Project Owner Action Matrix."""
    pr = disk_prep_payload["provider_readiness_attestation_design"]
    assert pr["generation_calls_performed_during_prep"] == 0
    assert pr["secret_safety_invariants"] == {
        "print_secret_values": False,
        "print_secret_hashes": False,
        "print_secret_prefixes_or_suffixes": False,
        "print_sensitive_account_or_org_ids": False,
    }
    for cid in ("C1", "C2", "C3"):
        c_spec = pr["candidates"][cid]
        assert c_spec["owner_action_marker"] == "OWNER_ACTION_REQUIRED"
        assert len(c_spec["required_attestations_before_amended_live_authorization"]) >= 3

    matrix = disk_prep_payload["project_owner_action_matrix"]
    assert len(matrix) == 4
    for row in matrix:
        assert set(row.keys()) >= {
            "action_id",
            "action",
            "provider",
            "required_before_which_gate",
            "mandatory_or_optional",
            "reason",
            "how_to_verify_without_secret_disclosure",
            "owner_action_marker",
            "status",
        }
        assert row["owner_action_marker"] == "OWNER_ACTION_REQUIRED"
        assert row["status"] == "PENDING_CHATGPT_AMENDMENT_DECISION"


def test_eap_10_fairness_fixture_call_budget_and_cost_options(
    disk_prep_payload: dict,
) -> None:
    """EAP-10: Sections 9, 10, 11, 12, and 13 options and advisory recommendation."""
    fairness = disk_prep_payload["fairness_policy_options"]
    assert fairness["selected_fairness_policy_option_id"] is None
    assert [o["option_id"] for o in fairness["options"]] == [
        "OPTION_A_MINIMAL_ENVIRONMENT_REPAIR",
        "OPTION_B_CONSERVATIVE_RELIABILITY_ENVIRONMENT",
        "OPTION_C_NO_AMENDED_COMPARATIVE_BENCHMARK",
    ]

    fixtures = disk_prep_payload["fixture_policy_options"]
    assert fixtures["selected_fixture_policy_id"] is None
    assert fixtures["final100_scenarios_inspected_or_used"] is False
    assert fixtures["final100_calibration_forbidden"] is True
    assert [o["policy_id"] for o in fixtures["options"]] == [
        "POLICY_F1_REUSE_EXISTING_DEV_SELECT_60",
        "POLICY_F2_SECONDARY_STABILIZATION_FROM_NON_FINAL_FROZEN_DEV",
        "POLICY_F3_ENGINEERING_READINESS_SUBSET_PLUS_AMENDED_COMPARATIVE_SET",
    ]

    budgets = disk_prep_payload["call_budget_options"]
    assert budgets["selected_call_budget_option_id"] is None
    assert budgets["authorized_generation_calls_in_prep"] == 0
    assert [o["budget_option_id"] for o in budgets["options"]] == [
        "S1_FULL_COMPARATIVE_180",
        "S2_READINESS_CANARY_PLUS_COMPARATIVE_180",
        "S3_REDUCED_STRATIFIED_COMPARATIVE_90",
    ]

    cost = disk_prep_payload["cost_planning"]
    assert (
        cost["current_price_input_status"]
        == "EXTERNAL_PRICING_REFRESH_REQUIRED_BEFORE_AUTHORIZATION"
    )
    assert cost["hard_maximum_claimed"] is False
    assert set(cost["cost_category_separation"].keys()) == {
        "planning_estimate",
        "authoritative_provider_receipt_cost",
        "provider_invoice",
    }

    rec = disk_prep_payload["anty_analytical_recommendation"]
    assert rec["advisory_only"] is True
    assert rec["recommendation_implemented"] is False
    assert rec["final_methodology_decision_authority"] == "CHATGPT"


def test_eap_11_required_firewall_fields_and_zero_calls(
    disk_prep_payload: dict,
) -> None:
    """EAP-11: Section 16 required firewall fields all hold exact required values."""
    assert disk_prep_payload["PRIMARY_EXPERIMENT_MUTATED"] is False
    assert disk_prep_payload["PRIMARY_RESULTS_REPLACED"] is False
    assert disk_prep_payload["PRIMARY_DENOMINATORS_CHANGED"] is False
    assert disk_prep_payload["MODEL_WINNER_SELECTED"] is False
    assert disk_prep_payload["SELECTED_MODEL_ID"] is None
    assert disk_prep_payload["AMENDMENT_APPROVED"] is False
    assert disk_prep_payload["AMENDED_LIVE_AUTHORIZED"] is False
    assert disk_prep_payload["AMENDED_LIVE_EXECUTED"] is False
    assert disk_prep_payload["STOCHASTICITY_EXECUTION_STARTED"] is False
    assert disk_prep_payload["FINAL100_USED"] is False
    assert disk_prep_payload["LIVE_PROVIDER_CALLS_NEW"] == 0
    assert disk_prep_payload["FINAL_METHODOLOGY_DECISION_AUTHORITY"] == "CHATGPT"

    assert disk_prep_payload["primary_experiment_mutated"] is False
    assert disk_prep_payload["primary_results_replaced"] is False
    assert disk_prep_payload["primary_denominators_changed"] is False
    assert disk_prep_payload["model_winner_selected"] is False
    assert disk_prep_payload["selected_model_id"] is None
    assert disk_prep_payload["amendment_approved"] is False
    assert disk_prep_payload["amended_live_authorized"] is False
    assert disk_prep_payload["amended_live_executed"] is False
    assert disk_prep_payload["stochasticity_execution_started"] is False
    assert disk_prep_payload["final100_used"] is False
    assert disk_prep_payload["live_provider_calls_new"] == 0


def test_eap_12_scientific_bundle_and_final100_unchanged() -> None:
    """EAP-12: Scientific code bundle and Final100 authorities are byte-identical to develop."""
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

    proc = subprocess.run(
        ["git", "diff", "--name-only", prep_mod.AUTHORITATIVE_BASE_DEVELOP_SHA],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    changed_paths = {
        line.strip() for line in proc.stdout.splitlines() if line.strip()
    }
    for sci_rel in SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS:
        assert sci_rel not in changed_paths, (
            f"Scientific code bundle file modified: {sci_rel}"
        )


def test_eap_13_no_api_key_or_dotenv_read_and_network_kill_switch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """EAP-13: Verification never reads API keys or `.env`, and NetworkKillSwitchGuard blocks all network egress."""
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
    summary = prep_mod.verify_w06_execution_environment_amendment_prep(
        repo_root=REPO_ROOT
    )
    assert summary["verified"] is True
    assert summary["live_provider_calls_new"] == 0

    with prep_mod.NetworkKillSwitchGuard() as guard:
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


def test_eap_14_artifact_tamper_rejection_and_secret_scan(
    tmp_path: Path, computed_prep_payload: dict, disk_prep_payload: dict
) -> None:
    """EAP-14: Verifier rejects tampered prep artifact or raw-evidence write paths, and rejects injected secrets."""
    assert_no_secrets_in_payload(computed_prep_payload, context="TEST_COMPUTED")
    assert_no_secrets_in_payload(disk_prep_payload, context="TEST_DISK")

    poisoned = copy.deepcopy(computed_prep_payload)
    poisoned["injected_secret"] = "sk-ant-" + "api03-" + ("A" * 36)
    with pytest.raises(Exception):
        assert_no_secrets_in_payload(poisoned, context="TEST_POISONED")

    with pytest.raises(
        PlanBeforeLiveProtocolError, match="RAW_EVIDENCE_WRITE_FORBIDDEN"
    ):
        prep_mod._assert_not_inside_raw_evidence(
            REPO_ROOT
            / "data/evaluation/w06/live_dev_select_primary_v1/tamper.json",
            REPO_ROOT,
        )

    # Verify tamper detection on prep artifact via monkeypatched path
    tampered_file = tmp_path / "tampered_prep.json"
    tampered_payload = copy.deepcopy(disk_prep_payload)
    tampered_payload["AMENDMENT_APPROVED"] = True
    tampered_file.write_text(
        json.dumps(tampered_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    orig_rel = prep_mod.PREP_ARTIFACT_REL_PATH
    try:
        rel_tmp = os.path.relpath(tampered_file, REPO_ROOT)
    except ValueError:
        rel_tmp = None

    if rel_tmp is not None:
        prep_mod.PREP_ARTIFACT_REL_PATH = rel_tmp
        try:
            with pytest.raises(
                PlanBeforeLiveProtocolError,
                match="PREP_ARTIFACT_INTERNAL_SHA256_TAMPERED",
            ):
                prep_mod.verify_w06_execution_environment_amendment_prep(
                    repo_root=REPO_ROOT
                )
        finally:
            prep_mod.PREP_ARTIFACT_REL_PATH = orig_rel


def test_eap_15_cli_verify_only_and_markdown_documentation() -> None:
    """EAP-15: CLI `--verify-only` exits 0 and research markdown covers all required sections."""
    proc = subprocess.run(
        [
            sys.executable,
            str(
                REPO_ROOT
                / "scripts/prepare_w06_dev_select_execution_environment_amendment_01.py"
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
        out["prep_artifact_file_sha256"]
        == prep_mod.EXPECTED_PREP_ARTIFACT_FILE_SHA256
    )
    assert (
        out["prep_artifact_internal_sha256"]
        == prep_mod.EXPECTED_PREP_ARTIFACT_INTERNAL_SHA256
    )

    doc_path = REPO_ROOT / prep_mod.PREP_DOC_REL_PATH
    assert doc_path.is_file()
    doc_text = doc_path.read_text(encoding="utf-8")
    for required_token in (
        "PRIMARY_PREREGISTERED_ONE_SHOT_OPERATIONAL_BENCHMARK",
        "SECONDARY_POST_HOC_EXECUTION_ENVIRONMENT_STABILIZATION_TRACK",
        "OWNER_ACTION_REQUIRED",
        "NOT_RECOMMENDED_WITHOUT_MAJOR_METHODOLOGY_CHANGE",
        "EXTERNAL_PRICING_REFRESH_REQUIRED_BEFORE_AUTHORIZATION",
        "ANTY_ANALYTICAL_RECOMMENDATION",
        "FINAL_METHODOLOGY_DECISION_AUTHORITY = CHATGPT",
        "PENDING_CHATGPT_AMENDMENT_DECISION",
    ):
        assert required_token in doc_text
