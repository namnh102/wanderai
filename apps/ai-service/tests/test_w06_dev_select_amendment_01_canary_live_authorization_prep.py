"""Offline verification test suite for W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-AMENDED-CANARY-LIVE-AUTHORIZATION-PREP."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import socket
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
    SecretLeakageViolationError,
)
from app.evaluation.dev_selection_harness import (  # noqa: E402
    FORBIDDEN_FINAL100_BUNDLE_SHA256,
    FORBIDDEN_P11_MANIFEST_SHA256,
    compute_scientific_code_bundle_sha256,
    normalize_lf_bytes,
    sha256_bytes,
)
import freeze_w06_dev_select_amendment_01_canary_live_authorization_prep as auth_mod  # noqa: E402
from prepare_w06_dev_select_execution_environment_amendment_01 import (  # noqa: E402
    NetworkKillSwitchGuard,
)
from run_w06_dev_select_live_v1 import OutboundNetworkBlockedError  # noqa: E402


def _load_json(rel_path: str) -> tuple[dict, str]:
    path = REPO_ROOT / rel_path
    assert path.is_file(), f"Missing required file: {rel_path}"
    raw = normalize_lf_bytes(path.read_bytes())
    return json.loads(raw.decode("utf-8")), sha256_bytes(raw)


def _valid_operational_cell_observation() -> dict:
    return {
        "correct_candidate_provider_model_config_used": True,
        "generation_calls_attempted": 1,
        "retry_count": 0,
        "no_authentication_failure": True,
        "no_billing_or_credit_failure": True,
        "no_quota_or_rate_limit_rejection": True,
        "no_model_access_failure": True,
        "no_client_timeout": True,
        "no_provider_transport_failure": True,
        "no_http_4xx_failure": True,
        "no_http_5xx_failure": True,
        "provider_returns_response": True,
        "required_provider_model_identity_evidence_captured": True,
        "diagnostic_schema_valid": False,
        "diagnostic_final_core_pass": False,
    }


def test_clap_01_authoritative_base_and_upstream_authorities_unchanged() -> None:
    """Verify authoritative base commit binding, owner-readiness receipt binding, canary manifest binding, and all upstream hashes."""
    with NetworkKillSwitchGuard():
        auth_json, auth_sha = _load_json(auth_mod.CANARY_AUTH_PREP_REL_PATH)
        assert (
            auth_sha
            == "21f9432c4c8bfa0ba5f63bdd99e8ab8c15d2802918b7e0a9c21cb5c0ccc63b61"
        )
        assert (
            auth_json["canary_live_authorization_prep_internal_sha256"]
            == "0f1480969d506d5b6dc16951a45cf2f8aaf913a13c011f2add6ec3e31721af61"
        )
        doc_sha = sha256_bytes(
            normalize_lf_bytes(
                (REPO_ROOT / auth_mod.CANARY_AUTH_PREP_DOC_REL_PATH).read_bytes()
            )
        )
        assert (
            doc_sha
            == "d9db3cf7876c408f9a30f703200bd575934e1c81679740e7cdd6ba30256904da"
        )

        # 1. Authoritative base commit binding + PR #71 merge
        assert (
            auth_json["authoritative_base_develop_sha"]
            == "df5a76d9d3734f77bf64abbe66d9d93492fabb3c"
        )
        ba = auth_json["bound_authorities"]
        assert ba["develop_base_sha"] == "df5a76d9d3734f77bf64abbe66d9d93492fabb3c"
        pr71 = ba["owner_readiness_attestation_merge"]
        assert pr71["pr_number"] == 71
        assert pr71["pr_state"] == "MERGED"
        assert (
            pr71["merge_commit_sha"]
            == "df5a76d9d3734f77bf64abbe66d9d93492fabb3c"
        )
        assert pr71["parent1"] == "ef78127ef06215849861e7d3358e24cb5222281e"
        assert pr71["parent2"] == "aa70f7bdea7cefee40894ba3c20f00bf9f01491d"
        assert pr71["post_merge_ci_run_id"] == 41112477246
        assert pr71["post_merge_ci_event"] == "push"
        assert (
            pr71["post_merge_ci_head_sha"]
            == "df5a76d9d3734f77bf64abbe66d9d93492fabb3c"
        )
        assert pr71["post_merge_ci_conclusion"] == "success"
        assert pr71["post_merge_ci_required_jobs"] == {
            "ai-service": "success",
            "backend": "success",
            "data-contract": "success",
            "mobile": "success",
        }

        # 2. Owner-readiness receipt hash binding
        att_json, att_sha = _load_json(auth_mod.OWNER_READINESS_ATTESTATION_REL_PATH)
        assert (
            att_sha
            == "91702599a9c81d57bfa1360d33cf19129537608a5141d35bbba58958a62b1d06"
        )
        assert (
            att_json["owner_readiness_attestation_internal_sha256"]
            == "137aae6ba52912c10098262ecd29238cb591c92005d99eb226ffbe65c9dfbd75"
        )
        assert (
            ba["owner_provider_readiness_attestation"]["file_sha256"] == att_sha
        )
        assert (
            ba["owner_provider_readiness_attestation"]["internal_sha256"]
            == att_json["owner_readiness_attestation_internal_sha256"]
        )

        # 3. Canary manifest hash binding
        can_json, can_sha = _load_json(auth_mod.CANARY_MANIFEST_REL_PATH)
        assert (
            can_sha
            == "3ce0ebaac35f22dfe8c981478a6c63d7a2fde0580b372fd8f25762ab3b18fb96"
        )
        assert (
            can_json["canary_manifest_internal_sha256"]
            == "707d99fee54d65822f194cc690cbfadea14ad2176594d4ef882e7d8031990518"
        )
        assert ba["canary_assignment_manifest"]["file_sha256"] == can_sha
        assert (
            ba["canary_assignment_manifest"]["internal_sha256"]
            == can_json["canary_manifest_internal_sha256"]
        )

        # 23. All upstream frozen hashes unchanged
        dec_json, dec_sha = _load_json(auth_mod.DECISION_ARTIFACT_REL_PATH)
        assert (
            dec_sha
            == "2e4211893c1988230e2eeb2718195d48c093da87725cd2fa074e1743ee599ddf"
        )
        assert (
            dec_json["decision_artifact_internal_sha256"]
            == "38dc02de2e846d4cf72108e8beacffdcfcf6308879e0ea72cca3bb83bf71387a"
        )

        app_json, app_sha = _load_json(auth_mod.APPROVAL_RECEIPT_REL_PATH)
        assert (
            app_sha
            == "171564d09b0011ddfc0e2b70ca2f9029bf6981b944527c09331fa7f6a0f914a5"
        )
        assert (
            app_json["approval_receipt_internal_sha256"]
            == "d32e1c61b130a93c5ccbf18294fc1e972c36ba4e561b7fff51a9ea13b43aa991"
        )

        prp_json, prp_sha = _load_json(
            auth_mod.PROVIDER_READINESS_PRICING_PREP_REL_PATH
        )
        assert (
            prp_sha
            == "ef94513ceb5d64a84da2ee3a4890e563dde19fb597e27d3e545bdbe4add58006"
        )
        assert (
            prp_json["provider_readiness_pricing_prep_sha256"]
            == "07f61e211c6e77ee3ed08936b04ee07ac090398e50047c7534ab30d32d24506e"
        )

        snap_json, snap_sha = _load_json(auth_mod.PUBLIC_PRICING_SNAPSHOT_REL_PATH)
        assert (
            snap_sha
            == "2302724e26c24c7eec09ecafaa3a707bc51a45e505d4954f3661601473946cf6"
        )
        assert (
            snap_json["public_pricing_snapshot_sha256"]
            == "bcc8daeb0d5feae6426446ffc206726f8d91c07bdad3b82df2b8bcddcacb5ffe"
        )

        prep_json, prep_sha = _load_json(auth_mod.PREP_ARTIFACT_REL_PATH)
        assert (
            prep_sha
            == "e8786c4f538b86c8aa1d6b2c0cfb4afd6b8b6a1efa5b51799e44bd6bdd5a9a91"
        )
        assert (
            prep_json["prep_artifact_internal_sha256"]
            == "49c24e65690cb4fb947d2733ddf8b019d863046cf955d9415eec1d16e9eaaf7a"
        )

        rec_json, rec_sha = _load_json(
            auth_mod.PRIMARY_RESULTS_FREEZE_RECEIPT_REL_PATH
        )
        assert (
            rec_sha
            == "c021094e26277d41664c4ae2f0560b7684435b6002c5b7ba742a17808c5b07a4"
        )
        assert (
            rec_json["results_freeze_receipt_sha256"]
            == "7b270de482f0b077e79bbba40a0c662851da46355a18b5e05f8fdf572880943a"
        )

        man_json, man_sha = _load_json(auth_mod.PRIMARY_RESULTS_MANIFEST_REL_PATH)
        assert (
            man_sha
            == "1d303e1c07b627c3f3eb87287b744f55ba3f6d3d85bd5cec36959b01919d26c0"
        )
        assert (
            man_json["results_manifest_sha256"]
            == "4e2f8f0df0a6e069d65b563b8221c3ba3086bb50ad73854e9cc592a9beb05011"
        )

        diag_json, diag_sha = _load_json(auth_mod.FAILURE_DIAGNOSTIC_REL_PATH)
        assert (
            diag_sha
            == "b729883505ecfc98f15917347239ea6d09cede106691b155026891996391e692"
        )
        assert (
            diag_json["diagnostic_artifact_sha256"]
            == "509528413e1d9eb8408943867be21f83dc2dda72acd53fe9028e3c37c7db05c8"
        )

        assert (
            compute_scientific_code_bundle_sha256()
            == "0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3"
        )


def test_clap_02_candidates_fixtures_9_cell_order_and_runtime_policy() -> None:
    """Verify exact 3 candidates, exact 3 fixtures, exact 9-cell order, timeout=180000, pacing=2000, zero retries, fallback=false, 1 call/cell, and no substitutions."""
    auth_json, _ = _load_json(auth_mod.CANARY_AUTH_PREP_REL_PATH)
    contract = auth_json["frozen_canary_execution_contract"]

    # 4 & 14. Exact three candidates & no model substitution
    cands = contract["candidates"]
    assert set(cands.keys()) == {"C1", "C2", "C3"}
    assert cands["C1"] == {
        "candidate_id": "C1",
        "provider": "GOOGLE",
        "provider_slug": "google",
        "exact_model_id": "gemini-3.8-flash",
        "assigned_canary_calls": 3,
    }
    assert cands["C2"] == {
        "candidate_id": "C2",
        "provider": "OPENAI",
        "provider_slug": "openai",
        "exact_model_id": "gpt-6.1-sol",
        "assigned_canary_calls": 3,
    }
    assert cands["C3"] == {
        "candidate_id": "C3",
        "provider": "ANTHROPIC",
        "provider_slug": "anthropic",
        "exact_model_id": "claude-sonnet-5-5",
        "assigned_canary_calls": 3,
    }
    assert contract["candidate_substitution_permitted"] is False
    assert contract["fourth_model_permitted"] is False

    # 5 & 15. Exact three fixtures & no fixture substitution
    assert contract["exact_canary_fixtures"] == [
        "W06-DEV-TUNE-007",
        "W06-DEV-TUNE-011",
        "W06-DEV-TUNE-015",
    ]
    assert contract["fixture_count"] == 3
    assert contract["additional_fixture_permitted"] is False
    assert contract["replacement_fixture_permitted"] is False
    assert contract["final100_scenario_permitted"] is False

    # 6. Exact 9-cell execution order
    assert contract["exact_9_cell_execution_order_labels"] == [
        "007 / C1",
        "007 / C2",
        "007 / C3",
        "011 / C1",
        "011 / C2",
        "011 / C3",
        "015 / C1",
        "015 / C2",
        "015 / C3",
    ]
    ordered_cells = contract["ordered_canary_cells"]
    assert len(ordered_cells) == 9
    assert [
        (c["order_index"], c["short_label"], c["fixture_id"], c["candidate_id"], c["cell_id"])
        for c in ordered_cells
    ] == list(auth_mod.EXPECTED_CANARY_9_CELL_ORDER)
    assert contract["total_maximum_canary_generation_calls"] == 9
    assert contract["calls_per_candidate"] == {"C1": 3, "C2": 3, "C3": 3}

    # 7, 8, 9, 10, 11. Frozen runtime policy
    rt = contract["frozen_runtime_policy"]
    assert rt["timeout_ms"] == 180000
    assert rt["inter_call_delay_ms"] == 2000
    assert rt["total_inter_cell_pacing_intervals"] == 8
    assert rt["total_inter_cell_pacing_ms"] == 16000
    assert rt["automatic_retry"] == 0
    assert rt["transport_retry"] == 0
    assert rt["manual_retry"] == 0
    assert rt["llm_repair"] == 0
    assert rt["semantic_repair"] == 0
    assert rt["fallback"] is False
    assert rt["generation_calls_per_assigned_cell"] == 1
    assert rt["adaptive_pacing_permitted"] is False
    assert rt["dynamic_timeout_permitted"] is False
    assert rt["provider_specific_special_treatment_permitted"] is False
    assert rt["retry_after_timeout_429_or_5xx_permitted"] is False


def test_clap_03_operational_pass_criterion_9_of_9_aggregate_and_fail_stop() -> None:
    """Verify operational PASS criterion per cell, 9/9 aggregate rule, and fail-stop behavior."""
    auth_json, _ = _load_json(auth_mod.CANARY_AUTH_PREP_REL_PATH)
    contract = auth_json["frozen_canary_execution_contract"]

    # Canary purpose
    purpose = contract["canary_purpose"]
    assert (
        purpose["classification"]
        == "OPERATIONAL_EXECUTION_ENVIRONMENT_READINESS_CHECK"
    )
    assert purpose["is_operational_execution_environment_readiness_check"] is True
    assert purpose["is_planner_quality_model_selection"] is False
    assert purpose["is_scientific_superiority_evaluation"] is False
    assert purpose["is_comparative_benchmark"] is False
    assert purpose["is_final100_evaluation"] is False
    assert purpose["interpretable_as_candidate_superiority_evidence"] is False
    assert purpose["selection_weight"] == 0

    # Operational PASS criterion per cell (schema validity / core quality do NOT redefine operational PASS)
    obs_pass = _valid_operational_cell_observation()
    res_pass = auth_mod.evaluate_canary_cell_operational_pass(obs_pass)
    assert res_pass["operational_pass"] is True
    assert res_pass["fail_stop_triggered"] is False
    assert res_pass["diagnostic_only_schema_valid"] is False
    assert res_pass["diagnostic_only_final_core_pass"] is False

    # Any operational failure triggers fail-stop
    for failure_field, bad_val in (
        ("correct_candidate_provider_model_config_used", False),
        ("generation_calls_attempted", 2),
        ("retry_count", 1),
        ("no_authentication_failure", False),
        ("no_billing_or_credit_failure", False),
        ("no_quota_or_rate_limit_rejection", False),
        ("no_model_access_failure", False),
        ("no_client_timeout", False),
        ("no_provider_transport_failure", False),
        ("no_http_4xx_failure", False),
        ("no_http_5xx_failure", False),
        ("provider_returns_response", False),
        ("required_provider_model_identity_evidence_captured", False),
    ):
        obs_fail = copy.deepcopy(obs_pass)
        obs_fail[failure_field] = bad_val
        res_fail = auth_mod.evaluate_canary_cell_operational_pass(obs_fail)
        assert res_fail["operational_pass"] is False
        assert res_fail["fail_stop_triggered"] is True

    # 12 & 13. 9/9 aggregate operational PASS requirement & fail-stop behavior
    nine_passes = [
        auth_mod.evaluate_canary_cell_operational_pass(obs_pass) for _ in range(9)
    ]
    agg_pass = auth_mod.evaluate_aggregate_canary_operational_decision(nine_passes)
    assert agg_pass["ALL_9_CANARY_OPERATIONAL_PASS"] is True
    assert agg_pass["operational_pass_count"] == 9
    assert agg_pass["operational_pass_fraction"] == "9/9"
    assert agg_pass["comparative_authorized"] is False

    # 8/9 must FAIL aggregate decision (no partial/majority/2-of-3/provider-average threshold allowed)
    eight_of_nine = copy.deepcopy(nine_passes)
    eight_of_nine[4]["operational_pass"] = False
    agg_8 = auth_mod.evaluate_aggregate_canary_operational_decision(eight_of_nine)
    assert agg_8["ALL_9_CANARY_OPERATIONAL_PASS"] is False
    assert agg_8["operational_pass_count"] == 8
    assert agg_8["aggregate_status"] == "FAIL_STOP_OPERATIONAL_FAILURE"
    assert agg_8["comparative_authorized"] is False
    assert agg_8["must_return_to_chatgpt_audit"] is True

    # Incomplete run (e.g. fail-stopped at cell 3) must FAIL aggregate decision
    aborted_run = nine_passes[:3]
    aborted_run[2]["operational_pass"] = False
    agg_aborted = auth_mod.evaluate_aggregate_canary_operational_decision(aborted_run)
    assert agg_aborted["ALL_9_CANARY_OPERATIONAL_PASS"] is False
    assert agg_aborted["aggregate_status"] == "FAIL_STOP_INCOMPLETE_OR_ABORTED"
    assert agg_aborted["comparative_authorized"] is False


def test_clap_04_proposed_vs_effective_authorization_and_scientific_firewalls() -> None:
    """Verify proposed vs effective authorization, comparative firewall, winner/stochasticity/Final100 firewalls, and primary strict rates."""
    auth_json, _ = _load_json(auth_mod.CANARY_AUTH_PREP_REL_PATH)

    # 12. Proposed vs effective authorization
    assert auth_json["CANARY_LIVE_AUTHORIZATION_PROPOSED"] is True
    assert auth_json["AMENDED_CANARY_LIVE_AUTHORIZED"] is False
    assert auth_json["AMENDED_LIVE_AUTHORIZED"] is False
    assert auth_json["AMENDED_LIVE_EXECUTED"] is False
    assert auth_json["CANARY_EXECUTED"] is False

    # 17. Comparative remains unauthorized
    assert auth_json["AMENDED_COMPARATIVE_LIVE_AUTHORIZED"] is False
    assert auth_json["COMPARATIVE_EXECUTED"] is False
    comp_fw = auth_json["comparative_execution_firewall"]
    assert comp_fw["AMENDED_COMPARATIVE_LIVE_AUTHORIZED"] is False
    assert comp_fw["COMPARATIVE_EXECUTED"] is False
    assert comp_fw["comparative_180_authorized"] is False
    assert comp_fw["canary_pass_auto_authorizes_comparative"] is False
    assert (
        comp_fw[
            "c3_comparative_readiness_must_be_rechecked_before_comparative_authorization"
        ]
        is True
    )

    # 16, 18, 19, 20, 21. Winner, stochasticity, Final100, live calls, env/secrets
    assert auth_json["MODEL_WINNER_SELECTED"] is False
    assert auth_json["SELECTED_MODEL_ID"] is None
    assert auth_json["STOCHASTICITY_EXECUTION_STARTED"] is False
    assert auth_json["FINAL100_USED"] is False
    assert auth_json["FINAL100_STATUS"] == "NO-GO"
    assert auth_json["LIVE_PROVIDER_CALLS_NEW"] == 0
    assert auth_json["ENV_FILE_READ"] is False
    assert auth_json["API_KEYS_INSPECTED"] is False
    assert (
        auth_json["NEXT_GATE"]
        == "W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-AMENDED-CANARY-LIVE-AUTHORIZATION-PREP-CHATGPT-AUDIT"
    )

    # 22. Primary strict rates remain 1/60, 8/60, 0/60
    p_fw = auth_json["primary_authority_firewall"]
    assert p_fw["authoritative_primary_strict_rates"] == {
        "C1": "1/60",
        "C2": "8/60",
        "C3": "0/60",
    }
    assert p_fw["rejected_erroneous_human_report_rates"] == {
        "C1": "0/60",
        "C2": "43/60",
        "C3": "0/60",
    }
    assert p_fw["erroneous_report_propagated"] is False
    assert p_fw["secondary_amendment_replaces_primary_experiment"] is False
    assert auth_json["PRIMARY_EXPERIMENT_MUTATED"] is False
    assert auth_json["PRIMARY_RESULTS_REPLACED"] is False
    assert auth_json["PRIMARY_DENOMINATORS_CHANGED"] is False

    # Final100 / P11 files untouched
    assert (
        sha256_bytes(
            normalize_lf_bytes(
                (
                    REPO_ROOT / "data/evaluation/w06/w06_scenarios_freeze_v1.json"
                ).read_bytes()
            )
        )
        == FORBIDDEN_FINAL100_BUNDLE_SHA256
    )
    assert (
        sha256_bytes(
            normalize_lf_bytes(
                (
                    REPO_ROOT
                    / "data/evaluation/w06/w06_p11_assignment_manifest_v1.json"
                ).read_bytes()
            )
        )
        == FORBIDDEN_P11_MANIFEST_SHA256
    )


def test_clap_05_tamper_detection_immutability_and_network_kill_switch(
    tmp_path: Path,
) -> None:
    """Verify tamper detection, model/fixture substitution rejection, write guards, and network kill switch."""
    with NetworkKillSwitchGuard():
        with pytest.raises(OutboundNetworkBlockedError):
            socket.create_connection(("api.openai.com", 443))
        with pytest.raises(OutboundNetworkBlockedError):
            urllib.request.urlopen("https://generativelanguage.googleapis.com")
        with pytest.raises(OutboundNetworkBlockedError):
            httpx.get("https://api.anthropic.com")
        with pytest.raises(OutboundNetworkBlockedError):
            httpx2.get("https://api.openai.com")

        summary = auth_mod.verify_w06_canary_live_authorization_prep(
            repo_root=REPO_ROOT
        )
        assert summary["verified"] is True
        assert summary["status"] == "PASS"
        assert summary["live_provider_calls_new"] == 0

    auth_json, _ = _load_json(auth_mod.CANARY_AUTH_PREP_REL_PATH)
    doc_bytes = (REPO_ROOT / auth_mod.CANARY_AUTH_PREP_DOC_REL_PATH).read_bytes()

    tampered_json = tmp_path / "tampered_auth.json"
    tampered_doc = tmp_path / "tampered_auth.md"
    tampered_doc.write_bytes(doc_bytes)

    # 1. Tamper timeout without updating internal SHA -> tamper error
    bad_timeout = copy.deepcopy(auth_json)
    bad_timeout["frozen_canary_execution_contract"]["frozen_runtime_policy"][
        "timeout_ms"
    ] = 55000
    tampered_json.write_text(
        json.dumps(bad_timeout, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="CANARY_AUTH_PREP_INTERNAL_SHA256_TAMPERED",
    ):
        auth_mod.verify_w06_canary_live_authorization_prep(
            artifact_path=tampered_json, doc_path=tampered_doc
        )

    # 2. Tamper Markdown doc -> drift error
    valid_json_copy = tmp_path / "valid_auth.json"
    valid_json_copy.write_bytes(
        (REPO_ROOT / auth_mod.CANARY_AUTH_PREP_REL_PATH).read_bytes()
    )
    tampered_doc.write_text(
        doc_bytes.decode("utf-8") + "\n<!-- drift -->\n", encoding="utf-8"
    )
    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="CANARY_AUTH_PREP_MARKDOWN_DRIFT_FROM_CANONICAL_JSON",
    ):
        auth_mod.verify_w06_canary_live_authorization_prep(
            artifact_path=valid_json_copy, doc_path=tampered_doc
        )

    # 3. Model substitution / 4th model -> rejected
    bad_cand = copy.deepcopy(auth_json["frozen_canary_execution_contract"])
    bad_cand["candidates"]["C2"]["exact_model_id"] = "gpt-4o"
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="CANARY_CANDIDATE_SPEC_MISMATCH"
    ):
        auth_mod.validate_canary_execution_contract(bad_cand)

    # 4. Fixture substitution -> rejected
    bad_fix = copy.deepcopy(auth_json["frozen_canary_execution_contract"])
    bad_fix["exact_canary_fixtures"] = [
        "W06-DEV-TUNE-001",
        "W06-DEV-TUNE-011",
        "W06-DEV-TUNE-015",
    ]
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="CANARY_FIXTURE_CONTRACT_MISMATCH"
    ):
        auth_mod.validate_canary_execution_contract(bad_fix)

    # 5. Effective live authorization = True during PREP -> rejected
    bad_live = copy.deepcopy(auth_json)
    bad_live["AMENDED_CANARY_LIVE_AUTHORIZED"] = True
    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="CANARY_AUTHORIZATION_PREP_MUST_NOT_AUTHORIZE_OR_EXECUTE_LIVE_CALLS",
    ):
        auth_mod.validate_authorization_and_scientific_firewalls(bad_live)

    # 6. Secret injection -> rejected
    with pytest.raises(SecretLeakageViolationError):
        auth_mod.assert_no_secrets_in_payload(
            {"openai_api_key": "sk-proj-secret123456"},
            context="test_secret_rejection",
        )

    # 7. Overwriting immutable upstream artifacts or raw evidence -> rejected
    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="IMMUTABLE_UPSTREAM_ARTIFACT_MUTATION_FORBIDDEN",
    ):
        auth_mod.write_w06_canary_live_authorization_prep(
            artifact_path=REPO_ROOT / auth_mod.OWNER_READINESS_ATTESTATION_REL_PATH
        )
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="RAW_EVIDENCE_WRITE_FORBIDDEN"
    ):
        auth_mod.write_w06_canary_live_authorization_prep(
            artifact_path=REPO_ROOT
            / "data/evaluation/w06/live_dev_select_primary_v1/forbidden.json"
        )
