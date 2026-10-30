"""Offline verification test suite for W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-OWNER-PROVIDER-READINESS-ATTESTATION-RECEIPT-PREP."""

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
import freeze_w06_dev_select_amendment_01_owner_provider_readiness_attestation as att_mod  # noqa: E402
from prepare_w06_dev_select_execution_environment_amendment_01 import (  # noqa: E402
    NetworkKillSwitchGuard,
)
from run_w06_dev_select_live_v1 import OutboundNetworkBlockedError  # noqa: E402


def _load_json(rel_path: str) -> tuple[dict, str]:
    path = REPO_ROOT / rel_path
    assert path.is_file(), f"Missing required file: {rel_path}"
    raw = normalize_lf_bytes(path.read_bytes())
    return json.loads(raw.decode("utf-8")), sha256_bytes(raw)


def test_opr_01_all_upstream_authorities_byte_and_hash_unchanged() -> None:
    """Verify all upstream authorities and the scientific code bundle remain byte/hash unchanged."""
    with NetworkKillSwitchGuard():
        prp_json, prp_sha = _load_json(att_mod.PROVIDER_READINESS_PRICING_PREP_REL_PATH)
        assert prp_sha == "ef94513ceb5d64a84da2ee3a4890e563dde19fb597e27d3e545bdbe4add58006"
        assert (
            prp_json["provider_readiness_pricing_prep_sha256"]
            == "07f61e211c6e77ee3ed08936b04ee07ac090398e50047c7534ab30d32d24506e"
        )
        prp_flags = prp_json["scientific_and_execution_firewall_flags"]
        assert prp_flags["C1_PROVIDER_READINESS"] == "NOT_YET_ATTESTED"
        assert prp_flags["C2_PROVIDER_READINESS"] == "NOT_YET_ATTESTED"
        assert prp_flags["C3_PROVIDER_READINESS"] == "NOT_YET_ATTESTED"

        snap_json, snap_sha = _load_json(att_mod.PUBLIC_PRICING_SNAPSHOT_REL_PATH)
        assert snap_sha == "2302724e26c24c7eec09ecafaa3a707bc51a45e505d4954f3661601473946cf6"
        assert (
            snap_json["public_pricing_snapshot_sha256"]
            == "bcc8daeb0d5feae6426446ffc206726f8d91c07bdad3b82df2b8bcddcacb5ffe"
        )

        app_json, app_sha = _load_json(att_mod.APPROVAL_RECEIPT_REL_PATH)
        assert app_sha == "171564d09b0011ddfc0e2b70ca2f9029bf6981b944527c09331fa7f6a0f914a5"
        assert (
            app_json["approval_receipt_internal_sha256"]
            == "d32e1c61b130a93c5ccbf18294fc1e972c36ba4e561b7fff51a9ea13b43aa991"
        )

        dec_json, dec_sha = _load_json(att_mod.DECISION_ARTIFACT_REL_PATH)
        assert dec_sha == "2e4211893c1988230e2eeb2718195d48c093da87725cd2fa074e1743ee599ddf"
        assert (
            dec_json["decision_artifact_internal_sha256"]
            == "38dc02de2e846d4cf72108e8beacffdcfcf6308879e0ea72cca3bb83bf71387a"
        )

        can_json, can_sha = _load_json(att_mod.CANARY_MANIFEST_REL_PATH)
        assert can_sha == "3ce0ebaac35f22dfe8c981478a6c63d7a2fde0580b372fd8f25762ab3b18fb96"
        assert (
            can_json["canary_manifest_internal_sha256"]
            == "707d99fee54d65822f194cc690cbfadea14ad2176594d4ef882e7d8031990518"
        )

        prep_json, prep_sha = _load_json(att_mod.PREP_ARTIFACT_REL_PATH)
        assert prep_sha == "e8786c4f538b86c8aa1d6b2c0cfb4afd6b8b6a1efa5b51799e44bd6bdd5a9a91"
        assert (
            prep_json["prep_artifact_internal_sha256"]
            == "49c24e65690cb4fb947d2733ddf8b019d863046cf955d9415eec1d16e9eaaf7a"
        )

        rec_json, rec_sha = _load_json(att_mod.PRIMARY_RESULTS_FREEZE_RECEIPT_REL_PATH)
        assert rec_sha == "c021094e26277d41664c4ae2f0560b7684435b6002c5b7ba742a17808c5b07a4"
        assert (
            rec_json["results_freeze_receipt_sha256"]
            == "7b270de482f0b077e79bbba40a0c662851da46355a18b5e05f8fdf572880943a"
        )

        man_json, man_sha = _load_json(att_mod.PRIMARY_RESULTS_MANIFEST_REL_PATH)
        assert man_sha == "1d303e1c07b627c3f3eb87287b744f55ba3f6d3d85bd5cec36959b01919d26c0"
        assert (
            man_json["results_manifest_sha256"]
            == "4e2f8f0df0a6e069d65b563b8221c3ba3086bb50ad73854e9cc592a9beb05011"
        )

        diag_json, diag_sha = _load_json(att_mod.FAILURE_DIAGNOSTIC_REL_PATH)
        assert diag_sha == "b729883505ecfc98f15917347239ea6d09cede106691b155026891996391e692"
        assert (
            diag_json["diagnostic_artifact_sha256"]
            == "509528413e1d9eb8408943867be21f83dc2dda72acd53fe9028e3c37c7db05c8"
        )

        assert (
            compute_scientific_code_bundle_sha256()
            == "0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3"
        )


def test_opr_02_receipt_binds_base_merge_and_frozen_scientific_policy() -> None:
    """Verify receipt binds develop@ef78127..., PR #70 merge/CI, frozen policy, and candidateauthority model."""
    att_json, att_sha = _load_json(att_mod.OWNER_READINESS_ATTESTATION_REL_PATH)
    assert (
        att_sha
        == "622878407081f5bb4566d8a29d827258031b52edecb067e0cf1ebe253a162a9d"
    )
    assert (
        att_json["owner_readiness_attestation_internal_sha256"]
        == "45af6219a72bcef6c79bd6b83d7a95f6c549342e13d73e266abe4ac1260edf86"
    )
    assert (
        att_json["authoritative_base_develop_sha"]
        == "ef78127ef06215849861e7d3358e24cb5222281e"
    )
    assert att_json["owner_observed_readiness_evidence_date"] == "2026-10-30"
    assert (
        att_json["receipt_candidate_status"]
        == "PENDING_CHATGPT_AUDIT_AND_REPOSITORY_FREEZE"
    )
    assert att_json["repository_authoritative_before_merge"] is False
    assert (
        att_json[
            "becomes_repository_authoritative_after_chatgpt_pass_merge_and_postmerge_ci"
        ]
        is True
    )

    ba = att_json["bound_authorities"]
    assert ba["develop_base_sha"] == "ef78127ef06215849861e7d3358e24cb5222281e"
    pr_merge = ba["provider_readiness_pricing_prep_merge"]
    assert pr_merge["pr_number"] == 70
    assert pr_merge["pr_state"] == "MERGED"
    assert (
        pr_merge["merge_commit_sha"]
        == "ef78127ef06215849861e7d3358e24cb5222281e"
    )
    assert pr_merge["parent1"] == "c2e5126b7e1d3aa25ef6e46352e030c346fc733a"
    assert pr_merge["parent2"] == "ceb41980545982ac1a664a59d8caf8eb4526f90c"
    assert pr_merge["post_merge_ci_run_id"] == 40162573640
    assert pr_merge["post_merge_ci_event"] == "push"
    assert (
        pr_merge["post_merge_ci_head_sha"]
        == "ef78127ef06215849861e7d3358e24cb5222281e"
    )
    assert pr_merge["post_merge_ci_conclusion"] == "success"
    assert pr_merge["post_merge_ci_required_jobs"] == {
        "ai-service": "success",
        "backend": "success",
        "data-contract": "success",
        "mobile": "success",
    }

    pol = att_json["frozen_scientific_policy"]
    assert (
        pol["fairness_policy"]
        == "OPTION_B_CONSERVATIVE_RELIABILITY_ENVIRONMENT"
    )
    assert pol["timeout_ms"] == 180000
    assert pol["inter_call_delay_ms"] == 2000
    assert pol["automatic_retry"] == 0
    assert pol["transport_retry"] == 0
    assert pol["manual_retry"] == 0
    assert pol["llm_repair"] == 0
    assert pol["semantic_repair"] == 0
    assert pol["fallback"] is False
    assert pol["canary_assigned_calls"] == 9
    assert pol["comparative_assigned_calls"] == 180
    assert pol["maximum_generation_calls"] == 189
    assert pol["maximum_candidate_calls"] == 63
    assert pol["exact_canary_fixtures"] == [
        "W06-DEV-TUNE-007",
        "W06-DEV-TUNE-011",
        "W06-DEV-TUNE-015",
    ]
    assert pol["exact_candidates"] == {
        "C1": {"provider": "GOOGLE", "model": "gemini-3.8-flash"},
        "C2": {"provider": "OPENAI", "model": "gpt-6.1-sol"},
        "C3": {"provider": "ANTHROPIC", "model": "claude-sonnet-5-5"},
    }


def test_opr_03_c1_c2_c3_sanitized_readiness_evidence_and_statuses() -> None:
    """Verify exact C1 (Tier 1, 1000 RPM, 2M TPM, 10K RPD), C2 (Build, 5000 RPM, 1M TPM), and C3 (Evaluation Tier, 500K in, 80K out, 1K req, 49152 < 80000) readiness evidence."""
    att_json, _ = _load_json(att_mod.OWNER_READINESS_ATTESTATION_REL_PATH)
    cands = att_json["candidate_readiness_attestations"]

    # C1 / GOOGLE
    c1 = cands["C1"]
    assert c1["candidate_id"] == "C1"
    assert c1["provider"] == "GOOGLE"
    assert c1["exact_model_id"] == "gemini-3.8-flash"
    assert (
        c1["billing_surface"]
        == "GEMINI_DEVELOPER_API_GOOGLE_AI_STUDIO_STANDARD_PAID_TIER"
    )
    c1_obs = c1["owner_observed"]
    assert c1_obs["billing_active"] is True
    assert c1_obs["paid_tier_active"] is True
    assert c1_obs["usage_tier"] == "TIER_1"
    assert c1_obs["positive_prepaid_credit_available"] is True
    assert c1_obs["exact_model_visible_in_rate_limit_dashboard"] is True
    assert c1_obs["standard_rpm_limit"] == 1000
    assert c1_obs["standard_input_tpm_limit"] == 2000000
    assert c1_obs["standard_rpd_limit"] == 10000
    assert c1_obs["required_max_candidate_calls_under_frozen_amendment"] == 63
    assert c1_obs["canary_assigned_calls"] == 3
    assert c1_obs["rpm_sufficient_for_frozen_canary"] is True
    assert c1_obs["tpm_sufficient_for_frozen_canary"] is True
    assert c1_obs["rpd_sufficient_for_frozen_canary"] is True
    assert c1["provider_readiness"] == "READY_FOR_CANARY"
    assert c1["exact_prepaid_vnd_balance_stored"] is False

    # C2 / OPENAI
    c2 = cands["C2"]
    assert c2["candidate_id"] == "C2"
    assert c2["provider"] == "OPENAI"
    assert c2["exact_model_id"] == "gpt-6.1-sol"
    assert (
        c2["billing_surface"]
        == "OPENAI_STANDARD_API_CHAT_COMPLETIONS_DEFAULT_SERVICE_TIER"
    )
    c2_obs = c2["owner_observed"]
    assert c2_obs["billing_active"] is True
    assert c2_obs["positive_api_credit_available"] is True
    assert c2_obs["api_credit_sufficient_for_canary_planning_envelope"] is True
    assert c2_obs["usage_tier"] == "BUILD"
    assert c2_obs["organization_spend_limit_blocking"] is False
    assert c2_obs["standard_rpm_limit"] == 5000
    assert c2_obs["standard_tpm_limit"] == 1000000
    assert c2_obs["required_max_candidate_calls_under_frozen_amendment"] == 63
    assert c2_obs["canary_assigned_calls"] == 3
    assert c2_obs["rpm_sufficient_for_frozen_canary"] is True
    assert c2_obs["tpm_sufficient_for_frozen_canary"] is True
    assert c2["provider_readiness"] == "READY_FOR_CANARY"
    assert c2["exact_current_dollar_balance_stored"] is False

    # C3 / ANTHROPIC
    c3 = cands["C3"]
    assert c3["candidate_id"] == "C3"
    assert c3["provider"] == "ANTHROPIC"
    assert c3["exact_model_id"] == "claude-sonnet-5-5"
    assert (
        c3["billing_surface"]
        == "ANTHROPIC_CLAUDE_API_FIRST_PARTY_DIRECT_MESSAGES_STANDARD_GLOBAL"
    )
    c3_obs = c3["owner_observed"]
    assert c3_obs["billing_active"] is True
    assert c3_obs["positive_credit_available"] is True
    assert c3_obs["exact_model_visible_in_rate_limit_dashboard"] is True
    assert c3_obs["account_tier"] == "EVALUATION_TIER"
    assert c3_obs["input_token_limit"] == 500000
    assert c3_obs["output_token_limit"] == 80000
    assert c3_obs["request_limit"] == 1000
    assert c3_obs["canary_assigned_calls"] == 3
    assert c3_obs["configured_max_output_tokens_per_call"] == 16384
    assert c3_obs["configured_three_call_max_output_reference"] == 49152
    assert (
        c3_obs["configured_three_call_max_output_reference"]
        < c3_obs["output_token_limit"]
    )
    assert c3_obs["three_call_max_output_reference_comparison"] == "49152 < 80000"
    assert (
        c3_obs[
            "three_call_max_output_reference_strictly_less_than_output_token_limit"
        ]
        is True
    )
    assert (
        c3_obs["input_capacity_sufficient_for_frozen_canary_planning_envelope"]
        is True
    )
    assert c3_obs["output_capacity_sufficient_for_frozen_canary_reference"] is True
    assert c3_obs["request_capacity_sufficient_for_frozen_canary"] is True
    assert c3["provider_readiness"] == "READY_FOR_CANARY"
    assert c3["attestation_scope"] == "CANARY_READINESS_ATTESTATION_ONLY"
    assert (
        c3["generalized_as_readiness_proof_for_future_60_call_comparative_run"]
        is False
    )
    assert (
        c3[
            "comparative_readiness_must_be_rechecked_before_comparative_authorization"
        ]
        is True
    )

    assert att_json["OWNER_PROVIDER_READINESS_ATTESTED"] is True
    assert att_json["C1_PROVIDER_READINESS"] == "READY_FOR_CANARY"
    assert att_json["C2_PROVIDER_READINESS"] == "READY_FOR_CANARY"
    assert att_json["C3_PROVIDER_READINESS"] == "READY_FOR_CANARY"
    assert att_json["ALL_CANARY_PROVIDER_READINESS"] == "READY"


def test_opr_04_readiness_semantics_and_live_execution_firewalls() -> None:
    """Verify readiness does not imply authorization, comparative readiness remains separate, and all live/Final100/winner/stochasticity/primary firewalls hold."""
    att_json, _ = _load_json(att_mod.OWNER_READINESS_ATTESTATION_REL_PATH)

    assert att_json["READY_FOR_CANARY_IS_NOT_CANARY_AUTHORIZATION"] is True
    assert att_json["CANARY_OPERATIONAL_PASS_STILL_REQUIRES_9_OF_9"] is True
    assert att_json["CANARY_PASS_DOES_NOT_AUTO_AUTHORIZE_COMPARATIVE"] is True

    sem = att_json["readiness_semantics_and_non_implication_firewall"]
    assert sem["READY_FOR_CANARY_IS_NOT_CANARY_AUTHORIZATION"] is True
    assert sem["CANARY_OPERATIONAL_PASS_STILL_REQUIRES_9_OF_9"] is True
    assert sem["CANARY_PASS_DOES_NOT_AUTO_AUTHORIZE_COMPARATIVE"] is True
    assert (
        sem[
            "comparative_60_call_readiness_requires_separate_recheck_before_comparative_authorization"
        ]
        is True
    )
    does_not_mean = sem["does_not_mean"]
    assert does_not_mean["provider_availability_is_guaranteed"] is False
    assert does_not_mean["all_9_canary_calls_will_complete"] is False
    assert does_not_mean["schema_or_core_quality_will_pass"] is False
    assert does_not_mean["provider_5xx_cannot_occur"] is False
    assert does_not_mean["provider_high_demand_failures_cannot_occur"] is False
    assert does_not_mean["comparative_execution_is_authorized"] is False
    assert does_not_mean["final100_is_authorized"] is False

    # Live / execution / scientific firewalls
    assert att_json["AMENDED_CANARY_LIVE_AUTHORIZED"] is False
    assert att_json["AMENDED_COMPARATIVE_LIVE_AUTHORIZED"] is False
    assert att_json["AMENDED_LIVE_AUTHORIZED"] is False
    assert att_json["AMENDED_LIVE_EXECUTED"] is False
    assert att_json["CANARY_EXECUTED"] is False
    assert att_json["COMPARATIVE_EXECUTED"] is False
    assert att_json["LIVE_PROVIDER_CALLS_NEW"] == 0
    assert att_json["MODEL_WINNER_SELECTED"] is False
    assert att_json["SELECTED_MODEL_ID"] is None
    assert att_json["STOCHASTICITY_EXECUTION_STARTED"] is False
    assert att_json["FINAL100_USED"] is False
    assert att_json["FINAL100_STATUS"] == "NO-GO"
    assert att_json["PRIMARY_EXPERIMENT_MUTATED"] is False
    assert att_json["PRIMARY_RESULTS_REPLACED"] is False
    assert att_json["PRIMARY_DENOMINATORS_CHANGED"] is False
    assert att_json["ENV_FILE_READ"] is False
    assert att_json["API_KEYS_INSPECTED"] is False
    assert (
        att_json["NEXT_GATE"]
        == "W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-OWNER-PROVIDER-READINESS-ATTESTATION-CHATGPT-AUDIT"
    )

    # Primary metric firewall (1/60, 8/60, 0/60 vs rejected 0/60, 43/60, 0/60)
    p_fw = att_json["primary_authority_firewall"]
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


def test_opr_05_no_secrets_account_ids_cards_balances_or_screenshots_committed() -> None:
    """Verify no API keys, key prefixes/suffixes, card details, account/project/org IDs, emails, balances, or screenshots are committed."""
    att_json, _ = _load_json(att_mod.OWNER_READINESS_ATTESTATION_REL_PATH)
    att_mod.assert_no_sensitive_account_or_secret_data_in_attestation(att_json)
    att_mod.assert_no_screenshots_in_evaluation_or_research_dirs(REPO_ROOT)

    doc_text = normalize_lf_bytes(
        (REPO_ROOT / att_mod.OWNER_READINESS_ATTESTATION_DOC_REL_PATH).read_bytes()
    ).decode("utf-8")
    att_mod.assert_no_sensitive_account_or_secret_data_in_attestation(
        {"markdown": doc_text}
    )

    # Verify sensitive detector catches injected leaks
    for bad_payload in (
        {"leak": "sk-proj-abc123456789"},
        {"leak": "AIzaSyA1234567890abcdef"},
        {"leak": "AIza...7f9a"},
        {"leak": "01A2B3-4C5D6E-7F8A9B"},
        {"leak": "org-AbCdEfGh123456"},
        {"leak": "418293049581"},
        {"leak": "owner@example.com"},
        {"leak": "4111 1111 1111 1234"},
        {"leak": "pi_3QxYzAbCdEfGhIjK"},
        {"leak": "500,000 VND"},
        {"billing_account_id": "redacted"},
        {"exact_prepaid_vnd_balance": 100},
    ):
        with pytest.raises(
            (PlanBeforeLiveProtocolError, SecretLeakageViolationError)
        ):
            att_mod.assert_no_sensitive_account_or_secret_data_in_attestation(
                bad_payload
            )


def test_opr_06_offline_network_kill_switch_and_no_env_or_provider_calls() -> None:
    """Verify NetworkKillSwitchGuard blocks all network sockets/HTTP clients and verifier runs strictly offline."""
    with NetworkKillSwitchGuard():
        with pytest.raises(OutboundNetworkBlockedError):
            socket.create_connection(("api.openai.com", 443))
        with pytest.raises(OutboundNetworkBlockedError):
            urllib.request.urlopen("https://generativelanguage.googleapis.com")
        with pytest.raises(OutboundNetworkBlockedError):
            httpx.get("https://api.anthropic.com")
        with pytest.raises(OutboundNetworkBlockedError):
            httpx2.get("https://api.openai.com")

        summary = att_mod.verify_w06_owner_provider_readiness_attestation(
            repo_root=REPO_ROOT
        )
        assert summary["verified"] is True
        assert summary["status"] == "PASS"
        assert summary["live_provider_calls_new"] == 0


def test_opr_07_tamper_detection_and_immutability_write_guards(
    tmp_path: Path,
) -> None:
    """Verify tamper detection on JSON/Markdown and write protection on upstream/raw evidence paths."""
    att_json, _ = _load_json(att_mod.OWNER_READINESS_ATTESTATION_REL_PATH)
    doc_bytes = (
        REPO_ROOT / att_mod.OWNER_READINESS_ATTESTATION_DOC_REL_PATH
    ).read_bytes()

    tampered_receipt = tmp_path / "tampered_receipt.json"
    tampered_doc = tmp_path / "tampered_doc.md"
    tampered_doc.write_bytes(doc_bytes)

    # 1. Tamper C1 RPM limit without updating hash -> internal SHA tamper error
    bad_1 = copy.deepcopy(att_json)
    bad_1["candidate_readiness_attestations"]["C1"]["owner_observed"][
        "standard_rpm_limit"
    ] = 999
    tampered_receipt.write_text(
        json.dumps(bad_1, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="OWNER_READINESS_ATTESTATION_INTERNAL_SHA256_TAMPERED",
    ):
        att_mod.verify_w06_owner_provider_readiness_attestation(
            receipt_path=tampered_receipt, doc_path=tampered_doc
        )

    # 2. Tamper Markdown doc -> drift error
    valid_receipt_copy = tmp_path / "valid_receipt.json"
    valid_receipt_copy.write_bytes(
        (REPO_ROOT / att_mod.OWNER_READINESS_ATTESTATION_REL_PATH).read_bytes()
    )
    tampered_doc.write_text(
        doc_bytes.decode("utf-8") + "\n<!-- drift -->\n", encoding="utf-8"
    )
    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="OWNER_READINESS_ATTESTATION_MARKDOWN_DRIFT_FROM_CANONICAL_JSON",
    ):
        att_mod.verify_w06_owner_provider_readiness_attestation(
            receipt_path=valid_receipt_copy, doc_path=tampered_doc
        )

    # 3. Attempting to derive state with live authorization = True -> rejected
    prp_json, _ = _load_json(att_mod.PROVIDER_READINESS_PRICING_PREP_REL_PATH)
    app_json, _ = _load_json(att_mod.APPROVAL_RECEIPT_REL_PATH)
    bad_live = copy.deepcopy(att_json)
    bad_live["AMENDED_CANARY_LIVE_AUTHORIZED"] = True
    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="OWNER_READINESS_ATTESTATION_MUST_NOT_AUTHORIZE_OR_EXECUTE_LIVE_CALLS",
    ):
        att_mod.derive_effective_owner_readiness_state(
            pricing_prep_payload=prp_json,
            approval_receipt_payload=app_json,
            owner_attestation_payload=bad_live,
        )

    # 4. Attempting to generalize C3 Evaluation Tier to 60-call comparative run -> rejected
    bad_c3 = copy.deepcopy(att_json["candidate_readiness_attestations"])
    bad_c3["C3"][
        "generalized_as_readiness_proof_for_future_60_call_comparative_run"
    ] = True
    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="C3_EVALUATION_TIER_LIMITS_MUST_NOT_BE_GENERALIZED_TO_60_CALL_COMPARATIVE_RUN",
    ):
        att_mod.validate_sanitized_candidate_attestations(bad_c3)

    # 5. Attempting to overwrite immutable upstream artifacts or raw evidence -> rejected
    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="IMMUTABLE_UPSTREAM_ARTIFACT_MUTATION_FORBIDDEN",
    ):
        att_mod.write_w06_owner_provider_readiness_attestation(
            receipt_path=REPO_ROOT / att_mod.PROVIDER_READINESS_PRICING_PREP_REL_PATH
        )

    with pytest.raises(
        PlanBeforeLiveProtocolError, match="RAW_EVIDENCE_WRITE_FORBIDDEN"
    ):
        att_mod.write_w06_owner_provider_readiness_attestation(
            receipt_path=REPO_ROOT
            / "data/evaluation/w06/live_dev_select_primary_v1/forbidden.json"
        )
