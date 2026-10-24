"""Offline verification test suite for W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-APPROVAL-RECEIPT-PREP.

Verifies all 23 requirements from the task specification:
1. decision artifact remains byte-identical (`2e4211893c1988230e2eeb2718195d48c093da87725cd2fa074e1743ee599ddf` / `38dc02de2e846d4cf72108e8beacffdcfcf6308879e0ea72cca3bb83bf71387a`)
2. canary manifest remains byte-identical (`3ce0ebaac35f22dfe8c981478a6c63d7a2fde0580b372fd8f25762ab3b18fb96` / `707d99fee54d65822f194cc690cbfadea14ad2176594d4ef882e7d8031990518`)
3. receipt binds exact decision SHA hashes
4. receipt binds exact merge commit (`1de6ad5288f2fc5f3036145f4089d3e1bb46f1ab`) and two parents (`bc913ed61097f26db8eae87b9fe47d1869dc3ec5`, `b745067e7e1949a3dfc2ee4974522913ca0c6a39`)
5. receipt binds exact post-merge CI run (`40094419087`), head (`1de6ad5288f2fc5f3036145f4089d3e1bb46f1ab`), event (`push`), and jobs (`ai-service`, `backend`, `data-contract`, `mobile` all `success`)
6. methodology policy bundle & canary authorities exactly match frozen decision
7. `AMENDMENT_APPROVED = true` and `AMENDMENT_METHODOLOGY_SELECTED = true`
8. `approval_scope = "METHODOLOGY_ONLY"` and `approval_authority = "CHATGPT"`
9. every live authorization/execution flag = `false`
10. `LIVE_PROVIDER_CALLS_NEW = 0`
11. provider readiness statuses = `"NOT_YET_ATTESTED"` and `OWNER_PROVIDER_ACTION_REQUIRED_BEFORE_CANARY_AUTHORIZATION = true`
12. pricing refresh still required (`EXTERNAL_PRICING_REFRESH_REQUIRED_BEFORE_AUTHORIZATION = true`)
13. Final100 untouched (`FINAL100_USED = false`, `FINAL100_STATUS = "NO-GO"`)
14. model winner null (`MODEL_WINNER_SELECTED = false`, `SELECTED_MODEL_ID = null`)
15. stochasticity false (`STOCHASTICITY_EXECUTION_STARTED = false`)
16. primary immutable (`PRIMARY_EXPERIMENT_MUTATED = false`, `PRIMARY_RESULTS_REPLACED = false`, `PRIMARY_DENOMINATORS_CHANGED = false`)
17. no secrets
18. network kill switch
19. no `.env`/API-key read
20. receipt tamper detection & immutability write guards
21. historical decision artifact with `AMENDMENT_APPROVED = false` remains unchanged and is NOT treated as contradiction
22. effective amendment state is derived as `decision.AMENDMENT_METHODOLOGY_SELECTED = true` + `approval_receipt.AMENDMENT_APPROVED = true` => methodology approved
23. methodology approval MUST NOT derive `live authorization = true`
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
    canonical_json_bytes,
    compute_scientific_code_bundle_sha256,
    normalize_lf_bytes,
    sha256_bytes,
)
import freeze_w06_dev_select_execution_environment_amendment_01_approval_receipt as rec_mod  # noqa: E402
import freeze_w06_dev_select_execution_environment_amendment_01_decision as dec_mod  # noqa: E402
import freeze_w06_dev_select_live_results as _freeze_mod  # noqa: E402
from run_w06_dev_select_live_v1 import OutboundNetworkBlockedError  # noqa: E402


@pytest.fixture(scope="module")
def disk_approval_receipt() -> dict:
    path = REPO_ROOT / rec_mod.APPROVAL_RECEIPT_REL_PATH
    assert path.is_file(), f"Missing approval receipt artifact: {path}"
    return json.loads(normalize_lf_bytes(path.read_bytes()).decode("utf-8"))


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


def test_ear_01_decision_and_canary_artifacts_remain_byte_identical(
    disk_decision_payload: dict, disk_canary_manifest: dict
) -> None:
    """EAR-01 (Reqs 1, 2, 21): Merged formal decision artifact and canary manifest remain byte-identical."""
    dec_path = REPO_ROOT / dec_mod.DECISION_ARTIFACT_REL_PATH
    dec_file_sha = sha256_bytes(normalize_lf_bytes(dec_path.read_bytes()))
    assert (
        dec_file_sha
        == "2e4211893c1988230e2eeb2718195d48c093da87725cd2fa074e1743ee599ddf"
    )
    assert (
        disk_decision_payload["decision_artifact_internal_sha256"]
        == "38dc02de2e846d4cf72108e8beacffdcfcf6308879e0ea72cca3bb83bf71387a"
    )
    assert disk_decision_payload["AMENDMENT_METHODOLOGY_SELECTED"] is True
    assert disk_decision_payload["AMENDMENT_APPROVED"] is False

    can_path = REPO_ROOT / dec_mod.CANARY_MANIFEST_REL_PATH
    can_file_sha = sha256_bytes(normalize_lf_bytes(can_path.read_bytes()))
    assert (
        can_file_sha
        == "3ce0ebaac35f22dfe8c981478a6c63d7a2fde0580b372fd8f25762ab3b18fb96"
    )
    assert (
        disk_canary_manifest["canary_manifest_internal_sha256"]
        == "707d99fee54d65822f194cc690cbfadea14ad2176594d4ef882e7d8031990518"
    )


def test_ear_02_receipt_binds_decision_canary_merge_and_postmerge_ci(
    disk_approval_receipt: dict, disk_decision_payload: dict
) -> None:
    """EAR-02 (Reqs 3, 4, 5 & Corrective A..D): Receipt binds exact decision/canary SHA256s, PR #68 merge commit/parents, post-merge CI run 40094419087, and cross-bound primary results-freeze receipt internal SHA."""
    expected_base = "1de6ad5288f2fc5f3036145f4089d3e1bb46f1ab"
    assert (
        disk_approval_receipt["authoritative_base_develop_sha"] == expected_base
    )

    ba = disk_approval_receipt["bound_authorities"]

    fd = ba["formal_decision"]
    assert (
        fd["decision_artifact_path"]
        == "data/evaluation/w06/w06_dev_select_execution_environment_amendment_01_decision_v1.json"
    )
    assert (
        fd["decision_artifact_file_sha256"]
        == "2e4211893c1988230e2eeb2718195d48c093da87725cd2fa074e1743ee599ddf"
    )
    assert (
        fd["decision_artifact_internal_sha256"]
        == "38dc02de2e846d4cf72108e8beacffdcfcf6308879e0ea72cca3bb83bf71387a"
    )
    assert fd["historical_decision_amendment_methodology_selected"] is True
    assert fd["historical_decision_amendment_approved"] is False
    assert fd["historical_decision_state_immutable"] is True

    cm = ba["canary_manifest"]
    assert (
        cm["path"]
        == "data/evaluation/w06/w06_dev_select_amendment_01_canary_manifest_v1.json"
    )
    assert (
        cm["file_sha256"]
        == "3ce0ebaac35f22dfe8c981478a6c63d7a2fde0580b372fd8f25762ab3b18fb96"
    )
    assert (
        cm["internal_sha256"]
        == "707d99fee54d65822f194cc690cbfadea14ad2176594d4ef882e7d8031990518"
    )

    fdm = ba["formal_decision_merge"]
    assert fdm["pr_number"] == 68
    assert fdm["pr_state"] == "MERGED"
    assert (
        fdm["merge_commit_sha"]
        == "1de6ad5288f2fc5f3036145f4089d3e1bb46f1ab"
    )
    assert fdm["parent1"] == "bc913ed61097f26db8eae87b9fe47d1869dc3ec5"
    assert fdm["parent2"] == "b745067e7e1949a3dfc2ee4974522913ca0c6a39"

    pm_ci = ba["post_merge_ci"]
    assert pm_ci["run_id"] == 40094419087
    assert (
        pm_ci["exact_head_sha"]
        == "1de6ad5288f2fc5f3036145f4089d3e1bb46f1ab"
    )
    assert pm_ci["event"] == "push"
    assert pm_ci["conclusion"] == "success"
    assert pm_ci["required_jobs"] == {
        "ai-service": "success",
        "backend": "success",
        "data-contract": "success",
        "mobile": "success",
    }

    prep_ba = ba["prep_authorities"]
    assert (
        prep_ba["prep_artifact_file_sha256"]
        == "e8786c4f538b86c8aa1d6b2c0cfb4afd6b8b6a1efa5b51799e44bd6bdd5a9a91"
    )
    assert (
        prep_ba["prep_artifact_internal_sha256"]
        == "49c24e65690cb4fb947d2733ddf8b019d863046cf955d9415eec1d16e9eaaf7a"
    )

    prim_ba = ba["primary_authorities"]
    assert (
        prim_ba["scientific_code_bundle_sha256"]
        == "0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3"
    )
    assert (
        prim_ba["raw_evidence_tree_sha256"]
        == "d5c4e53952500655b656a624657a3cf1ec7aae685809c9e53a318459cc319817"
    )
    assert (
        prim_ba["results_manifest_file_sha256"]
        == "1d303e1c07b627c3f3eb87287b744f55ba3f6d3d85bd5cec36959b01919d26c0"
    )
    assert (
        prim_ba["results_freeze_receipt_file_sha256"]
        == "c021094e26277d41664c4ae2f0560b7684435b6002c5b7ba742a17808c5b07a4"
    )
    # Mandatory Assertions A, B, C, D:
    assert (
        prim_ba["results_freeze_receipt_internal_sha256"]
        == "7b270de482f0b077e79bbba40a0c662851da46355a18b5e05f8fdf572880943a"
    )
    assert (
        rec_mod.EXPECTED_RESULTS_FREEZE_RECEIPT_INTERNAL_SHA256
        == _freeze_mod.EXPECTED_RESULTS_FREEZE_RECEIPT_INTERNAL_SHA256
    )
    assert (
        disk_decision_payload["bound_authorities"][
            "primary_results_freeze_receipt_internal_sha256"
        ]
        == _freeze_mod.EXPECTED_RESULTS_FREEZE_RECEIPT_INTERNAL_SHA256
    )
    freeze_receipt_doc = json.loads(
        normalize_lf_bytes(
            (REPO_ROOT / _freeze_mod.RESULTS_FREEZE_RECEIPT_REL_PATH).read_bytes()
        ).decode("utf-8")
    )
    assert (
        freeze_receipt_doc["results_freeze_receipt_sha256"]
        == _freeze_mod.EXPECTED_RESULTS_FREEZE_RECEIPT_INTERNAL_SHA256
    )
    assert (
        prim_ba["diagnostic_file_sha256"]
        == "b729883505ecfc98f15917347239ea6d09cede106691b155026891996391e692"
    )
    assert (
        prim_ba["diagnostic_internal_sha256"]
        == "509528413e1d9eb8408943867be21f83dc2dda72acd53fe9028e3c37c7db05c8"
    )


def test_ear_03_receipt_semantics_authority_model_and_approved_policy(
    disk_approval_receipt: dict,
) -> None:
    """EAR-03 (Reqs 6, 7, 8): Receipt semantics, candidate authority model, and approved frozen policy bundle."""
    assert (
        disk_approval_receipt["artifact_id"]
        == "W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-APPROVAL-RECEIPT-V1"
    )
    assert disk_approval_receipt["approval_authority"] == "CHATGPT"
    assert disk_approval_receipt["approval_scope"] == "METHODOLOGY_ONLY"
    assert (
        disk_approval_receipt["track_classification"]
        == "SECONDARY_POST_HOC_EXECUTION_ENVIRONMENT_STABILIZATION_TRACK"
    )
    assert disk_approval_receipt["AMENDMENT_METHODOLOGY_SELECTED"] is True
    assert disk_approval_receipt["AMENDMENT_APPROVED"] is True
    assert (
        disk_approval_receipt["approval_statement"]
        == "ChatGPT, acting as final methodology decision authority, approved the frozen secondary post-hoc execution-environment stabilization methodology after independent audit of the formal decision artifact, normal merge of PR #68, and successful post-merge CI on the exact merge SHA."
    )

    assert (
        disk_approval_receipt["receipt_candidate_status"]
        == "PENDING_CHATGPT_AUDIT_AND_REPOSITORY_FREEZE"
    )
    assert (
        disk_approval_receipt["repository_authoritative_before_merge"] is False
    )
    assert (
        disk_approval_receipt[
            "becomes_repository_authoritative_after_chatgpt_pass_merge_and_postmerge_ci"
        ]
        is True
    )
    auth_model = disk_approval_receipt["receipt_authority_model"]
    assert (
        auth_model["receipt_candidate_status"]
        == "PENDING_CHATGPT_AUDIT_AND_REPOSITORY_FREEZE"
    )
    assert auth_model["repository_authoritative_before_merge"] is False
    assert (
        auth_model[
            "becomes_repository_authoritative_after_chatgpt_pass_merge_and_postmerge_ci"
        ]
        is True
    )

    pol = disk_approval_receipt["approved_frozen_policy"]
    assert (
        pol["FAIRNESS_POLICY"]
        == "OPTION_B_CONSERVATIVE_RELIABILITY_ENVIRONMENT"
    )
    assert pol["TIMEOUT_POLICY"]["timeout_policy_id"] == "T3_CANDIDATE_180S"
    assert pol["TIMEOUT_POLICY"]["timeout_ms"] == 180000
    assert pol["TIMEOUT_POLICY"]["timeout_applies_symmetrically_to"] == [
        "C1",
        "C2",
        "C3",
    ]
    assert pol["TIMEOUT_POLICY"]["guarantees_completion"] is False

    assert (
        pol["PACING_POLICY"]["pacing_policy_id"]
        == "P1_FIXED_2000MS_INTER_CALL_DELAY"
    )
    assert pol["PACING_POLICY"]["inter_call_delay_ms"] == 2000
    assert pol["PACING_POLICY"]["fixed"] is True
    assert pol["PACING_POLICY"]["deterministic"] is True
    assert pol["PACING_POLICY"]["adaptive"] is False
    assert pol["PACING_POLICY"]["response_dependent"] is False

    assert (
        pol["RETRY_POLICY"]["retry_policy_id"] == "R0_STRICT_ZERO_RETRY"
    )
    assert pol["RETRY_POLICY"]["automatic_retry"] == 0
    assert pol["RETRY_POLICY"]["transport_retry"] == 0
    assert pol["RETRY_POLICY"]["manual_retry"] == 0
    assert pol["RETRY_POLICY"]["llm_repair"] == 0
    assert pol["RETRY_POLICY"]["semantic_repair"] == 0
    assert pol["RETRY_POLICY"]["fallback"] is False

    assert (
        pol["FIXTURE_POLICY"]
        == "POLICY_F3_ENGINEERING_READINESS_SUBSET_PLUS_AMENDED_COMPARATIVE_SET"
    )
    assert (
        pol["CALL_BUDGET_POLICY"]["call_budget_policy_id"]
        == "S2_READINESS_CANARY_PLUS_COMPARATIVE_180"
    )
    assert pol["CALL_BUDGET_POLICY"]["readiness_canary_assigned_calls"] == 9
    assert pol["CALL_BUDGET_POLICY"]["comparative_assigned_calls"] == 180
    assert pol["CALL_BUDGET_POLICY"]["maximum_generation_calls"] == 189
    assert pol["CALL_BUDGET_POLICY"]["calls_per_candidate_max"] == 63

    can_auth = disk_approval_receipt["canary_authorities"]
    assert can_auth["exact_fixture_ids"] == [
        "W06-DEV-TUNE-007",
        "W06-DEV-TUNE-011",
        "W06-DEV-TUNE-015",
    ]
    assert can_auth["exact_assigned_canary_cells"] == 9
    assert can_auth["selection_weight"] == 0
    assert can_auth["canary_gate_pass_requirement"] == "9/9 operational PASS"
    assert (
        can_auth["planner_quality_results_determine_operational_readiness"]
        is False
    )
    assert (
        can_auth[
            "canary_pass_automatically_authorizes_or_launches_comparative_benchmark"
        ]
        is False
    )
    assert (
        can_auth[
            "separate_chatgpt_authorization_required_for_180_cell_comparative_benchmark"
        ]
        is True
    )


def test_ear_04_effective_amendment_state_derivation_and_historical_non_contradiction(
    disk_decision_payload: dict, disk_approval_receipt: dict
) -> None:
    """EAR-04 (Reqs 21, 22, 23): Historical decision (`AMENDMENT_APPROVED=false`) + receipt (`AMENDMENT_APPROVED=true`) derives `METHODOLOGY_APPROVED_LIVE_UNAUTHORIZED` and rejects live authorization."""
    derived = rec_mod.derive_effective_amendment_state(
        decision_payload=disk_decision_payload,
        approval_receipt_payload=disk_approval_receipt,
    )
    assert derived == disk_approval_receipt["effective_amendment_state"]
    assert derived["decision_historical_amendment_methodology_selected"] is True
    assert derived["decision_historical_amendment_approved"] is False
    assert (
        derived["historical_decision_amendment_approved_false_preserved"]
        is True
    )
    assert derived["historical_decision_contradiction"] is False
    assert derived["approval_receipt_amendment_methodology_selected"] is True
    assert derived["approval_receipt_amendment_approved"] is True
    assert derived["approval_scope"] == "METHODOLOGY_ONLY"
    assert derived["effective_methodology_selected"] is True
    assert derived["effective_methodology_approved"] is True
    assert (
        derived["effective_amendment_status"]
        == "METHODOLOGY_APPROVED_LIVE_UNAUTHORIZED"
    )
    assert derived["methodology_approval_derives_live_authorization"] is False
    assert derived["effective_amended_canary_live_authorized"] is False
    assert derived["effective_amended_comparative_live_authorized"] is False
    assert derived["effective_amended_live_authorized"] is False
    assert derived["effective_amended_live_executed"] is False
    assert derived["effective_live_provider_calls_new"] == 0

    # If someone mutates historical decision to AMENDMENT_APPROVED=True, derivation must fail
    tampered_dec = copy.deepcopy(disk_decision_payload)
    tampered_dec["AMENDMENT_APPROVED"] = True
    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="HISTORICAL_DECISION_ARTIFACT_MUST_PRESERVE_AMENDMENT_APPROVED_FALSE",
    ):
        rec_mod.derive_effective_amendment_state(
            decision_payload=tampered_dec,
            approval_receipt_payload=disk_approval_receipt,
        )

    # If someone tries to derive live authorization=True from methodology approval, derivation must fail
    for flag in (
        "AMENDED_CANARY_LIVE_AUTHORIZED",
        "AMENDED_COMPARATIVE_LIVE_AUTHORIZED",
        "AMENDED_LIVE_AUTHORIZED",
        "AMENDED_LIVE_EXECUTED",
        "CANARY_EXECUTED",
        "COMPARATIVE_EXECUTED",
    ):
        tampered_rec = copy.deepcopy(disk_approval_receipt)
        tampered_rec[flag] = True
        with pytest.raises(
            PlanBeforeLiveProtocolError,
            match="METHODOLOGY_APPROVAL_MUST_NOT_DERIVE_LIVE_EXECUTION_OR_AUTHORIZATION",
        ):
            rec_mod.derive_effective_amendment_state(
                decision_payload=disk_decision_payload,
                approval_receipt_payload=tampered_rec,
            )


def test_ear_05_live_firewall_provider_readiness_and_pricing_status(
    disk_approval_receipt: dict,
) -> None:
    """EAR-05 (Reqs 9..16): All live authorization flags are false, provider readiness is NOT_YET_ATTESTED, pricing refresh required, primary/Final100/model-winner untouched."""
    assert disk_approval_receipt["AMENDED_CANARY_LIVE_AUTHORIZED"] is False
    assert disk_approval_receipt["AMENDED_COMPARATIVE_LIVE_AUTHORIZED"] is False
    assert disk_approval_receipt["AMENDED_LIVE_AUTHORIZED"] is False
    assert disk_approval_receipt["AMENDED_LIVE_EXECUTED"] is False
    assert disk_approval_receipt["LIVE_PROVIDER_CALLS_NEW"] == 0
    assert disk_approval_receipt["CANARY_EXECUTED"] is False
    assert disk_approval_receipt["COMPARATIVE_EXECUTED"] is False
    assert disk_approval_receipt["MODEL_WINNER_SELECTED"] is False
    assert disk_approval_receipt["SELECTED_MODEL_ID"] is None
    assert disk_approval_receipt["STOCHASTICITY_EXECUTION_STARTED"] is False
    assert disk_approval_receipt["FINAL100_USED"] is False
    assert disk_approval_receipt["FINAL100_STATUS"] == "NO-GO"
    assert disk_approval_receipt["PRIMARY_EXPERIMENT_MUTATED"] is False
    assert disk_approval_receipt["PRIMARY_RESULTS_REPLACED"] is False
    assert disk_approval_receipt["PRIMARY_DENOMINATORS_CHANGED"] is False

    assert disk_approval_receipt["C1_PROVIDER_READINESS"] == "NOT_YET_ATTESTED"
    assert disk_approval_receipt["C2_PROVIDER_READINESS"] == "NOT_YET_ATTESTED"
    assert disk_approval_receipt["C3_PROVIDER_READINESS"] == "NOT_YET_ATTESTED"
    assert (
        disk_approval_receipt[
            "EXTERNAL_PRICING_REFRESH_REQUIRED_BEFORE_AUTHORIZATION"
        ]
        is True
    )
    assert (
        disk_approval_receipt[
            "OWNER_PROVIDER_ACTION_REQUIRED_BEFORE_CANARY_AUTHORIZATION"
        ]
        is True
    )
    assert (
        disk_approval_receipt["NEXT_GATE"]
        == "W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-APPROVAL-RECEIPT-CHATGPT-AUDIT"
    )

    assert (
        compute_scientific_code_bundle_sha256(REPO_ROOT)
        == "0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3"
    )
    assert (
        sha256_bytes(
            normalize_lf_bytes(
                (
                    REPO_ROOT
                    / "data/evaluation/w06/w06_scenarios_freeze_v1.json"
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
    for rel_path in SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS:
        assert (REPO_ROOT / rel_path).is_file()


def test_ear_06_no_dotenv_or_apikey_read_and_network_kill_switch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """EAR-06 (Reqs 18, 19): No .env or API key read during verification, and outbound network is blocked."""
    for env_key in ("GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.setenv(env_key, "FORBIDDEN_SECRET_VALUE_MUST_NOT_BE_READ")

    orig_getenv = os.getenv

    def guarded_getenv(key: str, default=None):
        if key in ("GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
            raise AssertionError(f"Forbidden API key read: {key}")
        return orig_getenv(key, default)

    monkeypatch.setattr(os, "getenv", guarded_getenv)

    with rec_mod.NetworkKillSwitchGuard():
        with pytest.raises(OutboundNetworkBlockedError):
            socket.create_connection(("example.com", 443))
        with pytest.raises(OutboundNetworkBlockedError):
            urllib.request.urlopen("https://example.com")
        with pytest.raises(OutboundNetworkBlockedError):
            httpx.Client().get("https://example.com")
        with pytest.raises(OutboundNetworkBlockedError):
            httpx2.Client().get("https://example.com")

    summary = rec_mod.verify_w06_execution_environment_amendment_approval_receipt(
        repo_root=REPO_ROOT
    )
    assert summary["verified"] is True
    assert summary["live_provider_calls_new"] == 0


def test_ear_07_tamper_detection_immutability_guards_and_secret_scan(
    tmp_path: Path, disk_approval_receipt: dict
) -> None:
    """EAR-07 (Reqs 17, 20): Tampered receipt fails verification, writing over decision/canary/raw evidence is blocked, and secret scan is clean."""
    assert_no_secrets_in_payload(
        disk_approval_receipt, context="TEST_EAR_07_RECEIPT"
    )

    tampered_path = tmp_path / "tampered_approval_receipt.json"
    tampered_payload = copy.deepcopy(disk_approval_receipt)
    tampered_payload["AMENDED_LIVE_AUTHORIZED"] = True
    tampered_path.write_bytes(
        (
            json.dumps(
                tampered_payload, indent=2, sort_keys=True, ensure_ascii=False
            )
            + "\n"
        ).encode("utf-8")
    )
    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="APPROVAL_RECEIPT_INTERNAL_SHA256_TAMPERED",
    ):
        rec_mod.verify_w06_execution_environment_amendment_approval_receipt(
            receipt_path=tampered_path, repo_root=REPO_ROOT
        )

    # Mandatory Assertion E: Receipt using the old incorrect primary results-freeze receipt internal SHA
    # (`053d15328d76efbc0da057a1fe6095ec548de59bc9d0d542d4ba72fa6874a665`) is rejected even with recomputed self-hash
    stale_sha_path = tmp_path / "stale_results_freeze_receipt_sha.json"
    stale_payload = copy.deepcopy(disk_approval_receipt)
    stale_payload["bound_authorities"]["primary_authorities"][
        "results_freeze_receipt_internal_sha256"
    ] = "053d15328d76efbc0da057a1fe6095ec548de59bc9d0d542d4ba72fa6874a665"
    stale_without_self_hash = {
        k: v
        for k, v in stale_payload.items()
        if k != "approval_receipt_internal_sha256"
    }
    stale_payload["approval_receipt_internal_sha256"] = sha256_bytes(
        canonical_json_bytes(stale_without_self_hash)
    )
    stale_sha_path.write_bytes(
        (
            json.dumps(
                stale_payload, indent=2, sort_keys=True, ensure_ascii=False
            )
            + "\n"
        ).encode("utf-8")
    )
    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="APPROVAL_RECEIPT_RESULTS_FREEZE_RECEIPT_INTERNAL_SHA256_MISMATCH",
    ):
        rec_mod.verify_w06_execution_environment_amendment_approval_receipt(
            receipt_path=stale_sha_path, repo_root=REPO_ROOT
        )

    # Guard against overwriting decision artifact, canary manifest, or raw evidence
    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="DECISION_ARTIFACT_MUTATION_FORBIDDEN",
    ):
        rec_mod.write_w06_execution_environment_amendment_approval_receipt(
            receipt_path=REPO_ROOT / dec_mod.DECISION_ARTIFACT_REL_PATH,
            repo_root=REPO_ROOT,
        )
    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="CANARY_MANIFEST_MUTATION_FORBIDDEN",
    ):
        rec_mod.write_w06_execution_environment_amendment_approval_receipt(
            receipt_path=REPO_ROOT / dec_mod.CANARY_MANIFEST_REL_PATH,
            repo_root=REPO_ROOT,
        )
    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="RAW_EVIDENCE_WRITE_FORBIDDEN",
    ):
        rec_mod.write_w06_execution_environment_amendment_approval_receipt(
            receipt_path=REPO_ROOT
            / "data/evaluation/w06/live_dev_select_primary_v1/forbidden.json",
            repo_root=REPO_ROOT,
        )


def test_ear_08_cli_verify_only_and_markdown_documentation() -> None:
    """EAR-08: CLI `--verify-only` exits 0 and markdown documentation contains all required sections."""
    proc = subprocess.run(
        [
            sys.executable,
            str(
                REPO_ROOT
                / "scripts/freeze_w06_dev_select_execution_environment_amendment_01_approval_receipt.py"
            ),
            "--verify-only",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    cli_summary = json.loads(proc.stdout)
    assert cli_summary["verified"] is True
    assert (
        cli_summary["approval_receipt_file_sha256"]
        == rec_mod.EXPECTED_APPROVAL_RECEIPT_FILE_SHA256
    )
    assert (
        cli_summary["approval_receipt_internal_sha256"]
        == rec_mod.EXPECTED_APPROVAL_RECEIPT_INTERNAL_SHA256
    )

    doc_path = REPO_ROOT / rec_mod.APPROVAL_RECEIPT_DOC_REL_PATH
    assert doc_path.is_file()
    doc_text = doc_path.read_text(encoding="utf-8")
    assert_no_secrets_in_payload(
        {"doc": doc_text}, context="APPROVAL_RECEIPT_MARKDOWN_DOC"
    )
    for token in (
        "W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-APPROVAL-RECEIPT-V1",
        rec_mod.EXPECTED_APPROVAL_RECEIPT_FILE_SHA256,
        rec_mod.EXPECTED_APPROVAL_RECEIPT_INTERNAL_SHA256,
        "2e4211893c1988230e2eeb2718195d48c093da87725cd2fa074e1743ee599ddf",
        "38dc02de2e846d4cf72108e8beacffdcfcf6308879e0ea72cca3bb83bf71387a",
        "3ce0ebaac35f22dfe8c981478a6c63d7a2fde0580b372fd8f25762ab3b18fb96",
        "707d99fee54d65822f194cc690cbfadea14ad2176594d4ef882e7d8031990518",
        "1de6ad5288f2fc5f3036145f4089d3e1bb46f1ab",
        "7b270de482f0b077e79bbba40a0c662851da46355a18b5e05f8fdf572880943a",
        "40094419087",
        "METHODOLOGY_ONLY",
        "PENDING_CHATGPT_AUDIT_AND_REPOSITORY_FREEZE",
        "NOT_YET_ATTESTED",
        "W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-APPROVAL-RECEIPT-CHATGPT-AUDIT",
    ):
        assert token in doc_text
    assert (
        "053d15328d76efbc0da057a1fe6095ec548de59bc9d0d542d4ba72fa6874a665"
        not in doc_text
    )
