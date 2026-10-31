"""Offline tests for W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-CANARY-LIVE-LAUNCHER-PREP.

Covers all 28 required verification scenarios from Section 16:
1. Exact authoritative base ancestry (`develop@1ebe30c251958542088a3056dcfc6b780dac3a88`)
2. Exact auth-prep hash (`21f9432c...` / `0f148096...` / `d9db3cf7...`)
3. Exact canary-manifest hash (`3ce0ebaa...` / `707d99fe...`)
4. Exact 3 models (`gemini-3.8-flash`, `gpt-6.1-sol`, `claude-sonnet-5-5`)
5. Exact 3 fixtures (`W06-DEV-TUNE-007`, `W06-DEV-TUNE-011`, `W06-DEV-TUNE-015`)
6. Exact 9-cell order (`007 / C1` .. `015 / C3`)
7. Exact P1 prompt authority
8. Timeout 180s (`timeout_ms = 180000`, `T3_CANDIDATE_180S`)
9. Delay 2s (`inter_call_delay_ms = 2000`, `P1_FIXED_2000MS_INTER_CALL_DELAY`, 8 intervals)
10. Zero retries across all dimensions (`R0_STRICT_ZERO_RETRY`)
11. No fallback (`fallback = false`)
12. Concurrency 1 (`STRICT_SEQUENTIAL_SINGLE_WORKER`)
13. Max generation calls 9 (`1` per cell, `9` total)
14. Primary launcher remains untouched (`scripts/run_w06_dev_select_live_v1.py`)
15. Primary results unchanged (`C1 = 1/60`, `C2 = 8/60`, `C3 = 0/60`)
16. Final100/P11 unchanged
17. Output-root-exists -> fail
18. Wrong model -> fail
19. Wrong fixture -> fail
20. Wrong order -> fail
21. Retry > 0 -> fail
22. Timeout mutation -> fail
23. Provider substitution -> fail
24. Network attempt during preflight -> fail
25. `.env`/secret access during preflight -> fail
26. Simulated first operational failure (`007 / C2`) -> remaining cells 3..9 not scheduled
27. Simulated 8/9 -> aggregate FAIL (`ALL_9_CANARY_OPERATIONAL_PASS = false`)
28. Simulated 9/9 -> aggregate PASS (`ALL_9_CANARY_OPERATIONAL_PASS = true`) while comparative authorization remains false (`AMENDED_COMPARATIVE_LIVE_AUTHORIZED = false`)
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from typing import Any
import urllib.request

import httpx
import httpx2
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
AI_SERVICE_DIR = REPO_ROOT / "apps" / "ai-service"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for _p in (AI_SERVICE_DIR, SCRIPTS_DIR, REPO_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from app.evaluation.dev_live_runner import (  # noqa: E402
    CandidateRegistryIntegrityError,
    ImmutableCellExecutionError,
    LiveExecutionNotAuthorizedError,
    PlanBeforeLiveProtocolError,
    StochasticityGateViolationError,
)
from app.evaluation.dev_selection_harness import (  # noqa: E402
    FORBIDDEN_FINAL100_BUNDLE_SHA256,
    FORBIDDEN_P11_MANIFEST_SHA256,
    SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS,
    DevCellFailureClassification,
    Final100FirewallViolationError,
    compute_scientific_code_bundle_sha256,
    normalize_lf_bytes,
    sha256_bytes,
)
import run_w06_dev_select_amendment_01_canary_live_v1 as canary_launcher  # noqa: E402


@pytest.fixture(autouse=True)
def _enforce_offline_guards():
    """Run every test in this module under the offline network kill-switch."""
    with canary_launcher.NetworkKillSwitchGuard():
        yield


@pytest.fixture(scope="module")
def preflight_out() -> dict[str, Any]:
    """Execute `--preflight` once at module scope."""
    return canary_launcher.run_canary_launcher_cli(["--preflight"], repo_root=REPO_ROOT)


@pytest.fixture(scope="module")
def verified_authorities() -> dict[str, Any]:
    """Verify frozen canary launcher authorities once at module scope."""
    return canary_launcher.verify_frozen_canary_launcher_authorities(REPO_ROOT)


# ==============================================================================
# ITEMS 1..16: POSITIVE AUTHORITY, CONTRACT & FIREWALL VERIFICATION
# ==============================================================================


def test_01_exact_authoritative_base_ancestry(
    preflight_out: dict[str, Any],
) -> None:
    """Item 1: Verify exact authoritative base develop@1ebe30c251958542088a3056dcfc6b780dac3a88 ancestry."""
    assert (
        preflight_out["authoritative_base_develop_sha"]
        == "1ebe30c251958542088a3056dcfc6b780dac3a88"
    )
    prov = preflight_out["source_develop_provenance"]
    assert (
        prov["authoritative_base_develop_sha"]
        == "1ebe30c251958542088a3056dcfc6b780dac3a88"
    )
    assert (
        prov["pr_72_merge_commit_sha"]
        == "1ebe30c251958542088a3056dcfc6b780dac3a88"
    )
    assert prov["pr_72_parent_1"] == "df5a76d9d3734f77bf64abbe66d9d93492fabb3c"
    assert prov["pr_72_parent_2"] == "9e638f6dbb9a955ab574e9d09f6503d79d3ed762"
    assert prov["is_ancestor_of_head"] is True
    assert prov["verified"] is True

    def _fake_non_ancestor(args: list[str]) -> subprocess.CompletedProcess[str]:
        if "cat-file" in args:
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        if "--is-ancestor" in args:
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="")
        return subprocess.CompletedProcess(args, 0, stdout="false\n", stderr="")

    with pytest.raises(
        PlanBeforeLiveProtocolError, match="SOURCE_DEVELOP_NOT_ANCESTOR_OF_HEAD"
    ):
        canary_launcher.verify_source_develop_provenance(
            REPO_ROOT, git_runner=_fake_non_ancestor
        )


def test_02_exact_auth_prep_and_owner_readiness_hashes(
    preflight_out: dict[str, Any],
) -> None:
    """Item 2: Verify exact canary authorization PREP and owner-readiness attestation hashes."""
    assert (
        preflight_out["canary_authorization_prep_path"]
        == "data/evaluation/w06/w06_dev_select_amendment_01_canary_authorization_prep_v1.json"
    )
    assert (
        preflight_out["canary_authorization_prep_file_sha256"]
        == "21f9432c4c8bfa0ba5f63bdd99e8ab8c15d2802918b7e0a9c21cb5c0ccc63b61"
    )
    assert (
        preflight_out["canary_authorization_prep_internal_sha256"]
        == "0f1480969d506d5b6dc16951a45cf2f8aaf913a13c011f2add6ec3e31721af61"
    )
    assert (
        preflight_out["canary_authorization_prep_doc_sha256"]
        == "d9db3cf7876c408f9a30f703200bd575934e1c81679740e7cdd6ba30256904da"
    )
    assert (
        preflight_out["owner_readiness_attestation_file_sha256"]
        == "91702599a9c81d57bfa1360d33cf19129537608a5141d35bbba58958a62b1d06"
    )
    assert (
        preflight_out["owner_readiness_attestation_internal_sha256"]
        == "137aae6ba52912c10098262ecd29238cb591c92005d99eb226ffbe65c9dfbd75"
    )


def test_03_exact_canary_manifest_hash(preflight_out: dict[str, Any]) -> None:
    """Item 3: Verify exact canary manifest file and internal SHA256."""
    assert (
        preflight_out["canary_manifest_path"]
        == "data/evaluation/w06/w06_dev_select_amendment_01_canary_manifest_v1.json"
    )
    assert (
        preflight_out["canary_manifest_file_sha256"]
        == "3ce0ebaac35f22dfe8c981478a6c63d7a2fde0580b372fd8f25762ab3b18fb96"
    )
    assert (
        preflight_out["canary_manifest_internal_sha256"]
        == "707d99fee54d65822f194cc690cbfadea14ad2176594d4ef882e7d8031990518"
    )


def test_04_exact_3_models(preflight_out: dict[str, Any]) -> None:
    """Item 4: Verify exact 3 candidate models (gemini-3.8-flash, gpt-6.1-sol, claude-sonnet-5-5)."""
    cands = preflight_out["frozen_candidates"]
    assert list(cands.keys()) == ["C1", "C2", "C3"]
    assert cands["C1"] == {
        "candidate_id": "C1",
        "provider": "GOOGLE",
        "provider_slug": "google",
        "exact_model_id": "gemini-3.8-flash",
    }
    assert cands["C2"] == {
        "candidate_id": "C2",
        "provider": "OPENAI",
        "provider_slug": "openai",
        "exact_model_id": "gpt-6.1-sol",
    }
    assert cands["C3"] == {
        "candidate_id": "C3",
        "provider": "ANTHROPIC",
        "provider_slug": "anthropic",
        "exact_model_id": "claude-sonnet-5-5",
    }


def test_05_06_07_exact_fixtures_9_cell_order_and_p1(
    preflight_out: dict[str, Any],
) -> None:
    """Items 5, 6, 7: Verify exact 3 fixtures, exact 9-cell order, and locked P1 prompt."""
    assert preflight_out["frozen_canary_fixtures"] == [
        "W06-DEV-TUNE-007",
        "W06-DEV-TUNE-011",
        "W06-DEV-TUNE-015",
    ]
    order = preflight_out["exact_9_cell_execution_order"]
    assert len(order) == 9
    assert [c["short_label"] for c in order] == [
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
    assert [c["cell_id"] for c in order] == [
        "W06-AMENDMENT-01-CANARY-01-P1-C1-W06-DEV-TUNE-007",
        "W06-AMENDMENT-01-CANARY-02-P1-C2-W06-DEV-TUNE-007",
        "W06-AMENDMENT-01-CANARY-03-P1-C3-W06-DEV-TUNE-007",
        "W06-AMENDMENT-01-CANARY-04-P1-C1-W06-DEV-TUNE-011",
        "W06-AMENDMENT-01-CANARY-05-P1-C2-W06-DEV-TUNE-011",
        "W06-AMENDMENT-01-CANARY-06-P1-C3-W06-DEV-TUNE-011",
        "W06-AMENDMENT-01-CANARY-07-P1-C1-W06-DEV-TUNE-015",
        "W06-AMENDMENT-01-CANARY-08-P1-C2-W06-DEV-TUNE-015",
        "W06-AMENDMENT-01-CANARY-09-P1-C3-W06-DEV-TUNE-015",
    ]
    assert preflight_out["selected_prompt_id"] == "P1"
    assert (
        preflight_out["selected_prompt_semantic_sha256"]
        == "096ff4c74dd8d1aed1c0abe501b97c8dfd0f6424dbca535f2b79a242637a1c11"
    )
    assert (
        preflight_out["selected_prompt_system_sha256"]
        == "4bcb84a8aca1fc89f65709ac9d91c88e42359c284850061bae85c3607c345b0e"
    )
    assert (
        preflight_out["selected_prompt_user_template_sha256"]
        == "19762f7c72b4dd19b57c29e160d9195b8f2c72e836188823e9949f271a22f5de"
    )


def test_08_09_10_11_12_13_frozen_runtime_policy(
    preflight_out: dict[str, Any],
) -> None:
    """Items 8..13: Verify timeout 180s, delay 2s, zero retries, no fallback, concurrency 1, max calls 9."""
    rt = preflight_out["frozen_runtime_policy"]
    assert rt["timeout_policy_id"] == "T3_CANDIDATE_180S"
    assert rt["timeout_ms"] == 180000
    assert rt["pacing_policy_id"] == "P1_FIXED_2000MS_INTER_CALL_DELAY"
    assert rt["inter_call_delay_ms"] == 2000
    assert rt["delay_before_first_call_ms"] == 0
    assert rt["delay_after_last_call_ms"] == 0
    assert rt["maximum_scheduled_delays"] == 8
    assert rt["total_inter_cell_pacing_ms"] == 16000
    assert rt["retry_policy_id"] == "R0_STRICT_ZERO_RETRY"
    assert rt["automatic_retry"] == 0
    assert rt["transport_retry"] == 0
    assert rt["manual_retry"] == 0
    assert rt["llm_repair"] == 0
    assert rt["semantic_repair"] == 0
    assert rt["fallback"] is False
    assert rt["concurrency"] == 1
    assert rt["execution_mode"] == "STRICT_SEQUENTIAL_SINGLE_WORKER"
    assert rt["generation_calls_per_assigned_cell"] == 1
    assert rt["total_maximum_provider_generation_calls"] == 9


def test_14_15_16_primary_launcher_results_and_final100_untouched(
    preflight_out: dict[str, Any],
) -> None:
    """Items 14, 15, 16: Verify primary launcher, scientific code bundle, primary results, and Final100/P11 untouched."""
    assert (
        canary_launcher.LAUNCHER_REL_PATH not in SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS
    )
    assert (
        compute_scientific_code_bundle_sha256(repo_root=REPO_ROOT)
        == "0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3"
    )
    assert preflight_out["scientific_code_bundle_unchanged"] is True
    assert preflight_out["primary_launcher_untouched"] is True
    assert (
        preflight_out["primary_launcher_lf_sha256"]
        == "cd36b8ecad24059edb597c0039bd6e760a37ee8b4f36f49077801c65e7ddc7bf"
    )
    assert preflight_out["PRIMARY_EXPERIMENT_MUTATED"] is False
    assert preflight_out["PRIMARY_RESULTS_REPLACED"] is False
    assert preflight_out["PRIMARY_DENOMINATORS_CHANGED"] is False
    assert preflight_out["authoritative_primary_strict_rates"] == {
        "C1": "1/60",
        "C2": "8/60",
        "C3": "0/60",
    }
    assert preflight_out["FINAL100_USED"] is False
    assert preflight_out["FINAL100_STATUS"] == "NO-GO"
    assert preflight_out["LIVE_PROVIDER_CALLS_NEW"] == 0
    assert preflight_out["ENV_FILE_READ"] is False
    assert preflight_out["API_KEYS_INSPECTED"] is False
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


# ==============================================================================
# ITEMS 17..25: ADVERSARIAL NEGATIVE TESTS (MUTATIONS, GUARDS, FIREWALLS)
# ==============================================================================


def test_17_output_root_exists_fails(tmp_path: Path) -> None:
    """Item 17: Preflight and execution fail closed if the canary output root already exists."""
    existing_root = tmp_path / "live_amendment_01_canary_v1"
    existing_root.mkdir(parents=True)
    with pytest.raises(
        ImmutableCellExecutionError, match="CANARY_OUTPUT_ROOT_ALREADY_EXISTS"
    ):
        canary_launcher.run_preflight(
            repo_root=REPO_ROOT, output_root_override=existing_root
        )

    primary_root = REPO_ROOT / "data/evaluation/w06/live_dev_select_primary_v1"
    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="PRIMARY_DEV_SELECT_OUTPUT_ROOT_FORBIDDEN_IN_CANARY_LAUNCHER",
    ):
        canary_launcher.verify_canary_output_root_not_existing(
            repo_root=REPO_ROOT, output_root_override=primary_root
        )


def test_18_wrong_model_fails(verified_authorities: dict[str, Any]) -> None:
    """Item 18: Wrong model ID in contract or cell is rejected fail-closed."""
    bad_auth = copy.deepcopy(verified_authorities["auth_prep"])
    bad_auth["frozen_canary_execution_contract"]["candidates"]["C1"][
        "exact_model_id"
    ] = "gemini-2.5-pro"
    with pytest.raises(
        CandidateRegistryIntegrityError,
        match="CANARY_CANDIDATE_MODEL_OR_PROVIDER_MISMATCH",
    ):
        canary_launcher.verify_frozen_canary_contract_and_cells(
            auth_prep=bad_auth,
            canary_manifest=verified_authorities["canary_manifest"],
            dev_bundle=verified_authorities["dev_bundle"],
            cand_reg=verified_authorities["candidate_registry"],
            p1_spec=verified_authorities["p1_spec"],
        )

    bad_cell_auth = copy.deepcopy(verified_authorities["auth_prep"])
    bad_cell_auth["frozen_canary_execution_contract"]["ordered_canary_cells"][1][
        "requested_model_id"
    ] = "gpt-5.4"
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="CANARY_CELL_CONTRACT_MISMATCH"
    ):
        canary_launcher.verify_frozen_canary_contract_and_cells(
            auth_prep=bad_cell_auth,
            canary_manifest=verified_authorities["canary_manifest"],
            dev_bundle=verified_authorities["dev_bundle"],
            cand_reg=verified_authorities["candidate_registry"],
            p1_spec=verified_authorities["p1_spec"],
        )


def test_19_wrong_fixture_fails(verified_authorities: dict[str, Any]) -> None:
    """Item 19: Wrong fixture ID in contract or cell is rejected fail-closed."""
    bad_auth = copy.deepcopy(verified_authorities["auth_prep"])
    bad_auth["frozen_canary_execution_contract"]["exact_canary_fixtures"] = [
        "W06-DEV-TUNE-001",
        "W06-DEV-TUNE-011",
        "W06-DEV-TUNE-015",
    ]
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="CANARY_FIXTURE_OR_CELL_COUNT_MISMATCH"
    ):
        canary_launcher.verify_frozen_canary_contract_and_cells(
            auth_prep=bad_auth,
            canary_manifest=verified_authorities["canary_manifest"],
            dev_bundle=verified_authorities["dev_bundle"],
            cand_reg=verified_authorities["candidate_registry"],
            p1_spec=verified_authorities["p1_spec"],
        )

    bad_cell_auth = copy.deepcopy(verified_authorities["auth_prep"])
    bad_cell_auth["frozen_canary_execution_contract"]["ordered_canary_cells"][0][
        "fixture_id"
    ] = "W06-DEV-SELECT-001"
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="CANARY_CELL_CONTRACT_MISMATCH"
    ):
        canary_launcher.verify_frozen_canary_contract_and_cells(
            auth_prep=bad_cell_auth,
            canary_manifest=verified_authorities["canary_manifest"],
            dev_bundle=verified_authorities["dev_bundle"],
            cand_reg=verified_authorities["candidate_registry"],
            p1_spec=verified_authorities["p1_spec"],
        )


def test_20_wrong_order_fails(verified_authorities: dict[str, Any]) -> None:
    """Item 20: Swapping cell execution order or labels is rejected fail-closed."""
    bad_auth = copy.deepcopy(verified_authorities["auth_prep"])
    cells = bad_auth["frozen_canary_execution_contract"]["ordered_canary_cells"]
    cells[0], cells[1] = cells[1], cells[0]
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="CANARY_CELL_CONTRACT_MISMATCH"
    ):
        canary_launcher.verify_frozen_canary_contract_and_cells(
            auth_prep=bad_auth,
            canary_manifest=verified_authorities["canary_manifest"],
            dev_bundle=verified_authorities["dev_bundle"],
            cand_reg=verified_authorities["candidate_registry"],
            p1_spec=verified_authorities["p1_spec"],
        )


def test_21_retry_greater_than_zero_fails(
    verified_authorities: dict[str, Any],
) -> None:
    """Item 21: Any retry > 0 in runtime policy or cell contract is rejected fail-closed."""
    for retry_field in (
        "automatic_retry",
        "transport_retry",
        "manual_retry",
        "llm_repair",
        "semantic_repair",
    ):
        bad_auth = copy.deepcopy(verified_authorities["auth_prep"])
        bad_auth["frozen_canary_execution_contract"]["frozen_runtime_policy"][
            retry_field
        ] = 1
        with pytest.raises(
            PlanBeforeLiveProtocolError, match="CANARY_RUNTIME_POLICY_MISMATCH"
        ):
            canary_launcher.verify_frozen_canary_contract_and_cells(
                auth_prep=bad_auth,
                canary_manifest=verified_authorities["canary_manifest"],
                dev_bundle=verified_authorities["dev_bundle"],
                cand_reg=verified_authorities["candidate_registry"],
                p1_spec=verified_authorities["p1_spec"],
            )

    bad_cell_auth = copy.deepcopy(verified_authorities["auth_prep"])
    bad_cell_auth["frozen_canary_execution_contract"]["ordered_canary_cells"][2][
        "retry"
    ] = 1
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="CANARY_CELL_CONTRACT_MISMATCH"
    ):
        canary_launcher.verify_frozen_canary_contract_and_cells(
            auth_prep=bad_cell_auth,
            canary_manifest=verified_authorities["canary_manifest"],
            dev_bundle=verified_authorities["dev_bundle"],
            cand_reg=verified_authorities["candidate_registry"],
            p1_spec=verified_authorities["p1_spec"],
        )


def test_22_timeout_or_delay_mutation_fails(
    verified_authorities: dict[str, Any],
) -> None:
    """Item 22: Mutating timeout_ms away from 180000 or inter_call_delay_ms away from 2000 fails."""
    bad_timeout = copy.deepcopy(verified_authorities["auth_prep"])
    bad_timeout["frozen_canary_execution_contract"]["frozen_runtime_policy"][
        "timeout_ms"
    ] = 55000
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="CANARY_RUNTIME_POLICY_MISMATCH"
    ):
        canary_launcher.verify_frozen_canary_contract_and_cells(
            auth_prep=bad_timeout,
            canary_manifest=verified_authorities["canary_manifest"],
            dev_bundle=verified_authorities["dev_bundle"],
            cand_reg=verified_authorities["candidate_registry"],
            p1_spec=verified_authorities["p1_spec"],
        )

    bad_delay = copy.deepcopy(verified_authorities["auth_prep"])
    bad_delay["frozen_canary_execution_contract"]["frozen_runtime_policy"][
        "inter_call_delay_ms"
    ] = 5000
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="CANARY_RUNTIME_POLICY_MISMATCH"
    ):
        canary_launcher.verify_frozen_canary_contract_and_cells(
            auth_prep=bad_delay,
            canary_manifest=verified_authorities["canary_manifest"],
            dev_bundle=verified_authorities["dev_bundle"],
            cand_reg=verified_authorities["candidate_registry"],
            p1_spec=verified_authorities["p1_spec"],
        )


def test_23_provider_substitution_or_fourth_model_fails(
    verified_authorities: dict[str, Any],
) -> None:
    """Item 23: Provider substitution or adding a fourth candidate fails closed."""
    bad_prov = copy.deepcopy(verified_authorities["auth_prep"])
    bad_prov["frozen_canary_execution_contract"]["candidates"]["C3"][
        "provider"
    ] = "OPENAI"
    with pytest.raises(
        CandidateRegistryIntegrityError,
        match="CANARY_CANDIDATE_MODEL_OR_PROVIDER_MISMATCH",
    ):
        canary_launcher.verify_frozen_canary_contract_and_cells(
            auth_prep=bad_prov,
            canary_manifest=verified_authorities["canary_manifest"],
            dev_bundle=verified_authorities["dev_bundle"],
            cand_reg=verified_authorities["candidate_registry"],
            p1_spec=verified_authorities["p1_spec"],
        )

    bad_fourth = copy.deepcopy(verified_authorities["auth_prep"])
    bad_fourth["frozen_canary_execution_contract"]["candidates"]["C4"] = {
        "candidate_id": "C4",
        "provider": "GOOGLE",
        "provider_slug": "google",
        "exact_model_id": "gemini-3.8-flash",
        "assigned_canary_calls": 3,
    }
    with pytest.raises(
        CandidateRegistryIntegrityError, match="CANARY_CANDIDATE_SET_MISMATCH"
    ):
        canary_launcher.verify_frozen_canary_contract_and_cells(
            auth_prep=bad_fourth,
            canary_manifest=verified_authorities["canary_manifest"],
            dev_bundle=verified_authorities["dev_bundle"],
            cand_reg=verified_authorities["candidate_registry"],
            p1_spec=verified_authorities["p1_spec"],
        )


def test_24_network_attempt_during_preflight_fails() -> None:
    """Item 24: Any outbound network attempt during preflight is blocked by NetworkKillSwitchGuard."""
    with canary_launcher.NetworkKillSwitchGuard():
        with pytest.raises(
            canary_launcher.OutboundNetworkBlockedError,
            match="OFFLINE_NETWORK_KILL_SWITCH_TRIGGERED",
        ):
            socket.create_connection(("example.com", 443), timeout=0.1)

        with pytest.raises(
            canary_launcher.OutboundNetworkBlockedError,
            match="OFFLINE_NETWORK_KILL_SWITCH_TRIGGERED",
        ):
            urllib.request.urlopen("https://example.com", timeout=0.1)

        with pytest.raises(
            canary_launcher.OutboundNetworkBlockedError,
            match="OFFLINE_NETWORK_KILL_SWITCH_TRIGGERED",
        ):
            with httpx.Client() as c:
                c.get("https://example.com")

        with pytest.raises(
            canary_launcher.OutboundNetworkBlockedError,
            match="OFFLINE_NETWORK_KILL_SWITCH_TRIGGERED",
        ):
            with httpx2.Client() as c2:
                c2.get("https://example.com")


def test_25_dotenv_or_secret_access_during_preflight_fails(tmp_path: Path) -> None:
    """Item 25: Reading `.env` or inspecting provider API keys during preflight fails closed."""
    fake_dotenv = tmp_path / ".env"
    fake_dotenv.write_text("OPENAI_API_KEY=dummy\n", encoding="utf-8")

    with canary_launcher.PreflightSecretAndEnvFileAccessGuard():
        with pytest.raises(
            canary_launcher.PreflightSecretAccessForbiddenError,
            match="PREFLIGHT_DOTENV_READ_FORBIDDEN",
        ):
            fake_dotenv.read_text(encoding="utf-8")

        with pytest.raises(
            canary_launcher.PreflightSecretAccessForbiddenError,
            match="PREFLIGHT_DOTENV_READ_FORBIDDEN",
        ):
            open(fake_dotenv, "r", encoding="utf-8")

        for key_name in ("GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
            with pytest.raises(
                canary_launcher.PreflightSecretAccessForbiddenError,
                match="PREFLIGHT_API_KEY_INSPECTION_FORBIDDEN",
            ):
                os.getenv(key_name)

            with pytest.raises(
                canary_launcher.PreflightSecretAccessForbiddenError,
                match="PREFLIGHT_API_KEY_INSPECTION_FORBIDDEN",
            ):
                os.environ.get(key_name)


# ==============================================================================
# ITEMS 26..28: SIMULATED EXECUTION (FAIL-STOP, 8/9 FAIL, 9/9 PASS + FIREWALL)
# ==============================================================================


def test_26_simulated_first_operational_failure_stops_immediately(
    tmp_path: Path,
) -> None:
    """Item 26: If `007 / C2` (order index 2) fails operationally, cell 1 passes, cell 2 failure is frozen, and cells 3..9 are NOT scheduled."""
    out_root = tmp_path / "sim_fail_stop_007_c2"
    invoked_orders: list[int] = []

    def _responder(
        order_index: int,
        cell_record: dict[str, Any],
        _wire_request: dict[str, Any],
    ) -> dict[str, Any]:
        invoked_orders.append(order_index)
        if order_index == 2:
            # Simulate operational timeout failure on 007 / C2
            return {
                "raw_text": "",
                "returned_model_id": None,
                "simulated_failure": DevCellFailureClassification.TIMEOUT,
            }
        return {
            "raw_text": '{"days": []}',
            "returned_model_id": cell_record["requested_model_id"],
            "simulated_failure": DevCellFailureClassification.NONE,
        }

    with canary_launcher.PreflightSecretAndEnvFileAccessGuard():
        summary = canary_launcher.execute_canary_9_cell_sequence(
            repo_root=REPO_ROOT,
            output_root=out_root,
            execution_mode="OFFLINE_SIMULATION",
            simulated_cell_responder=_responder,
            persist_artifacts=True,
        )

    assert invoked_orders == [1, 2]
    assert summary["attempted_cells_count"] == 2
    assert summary["operational_pass_cells_count"] == 1
    assert summary["operational_pass_fraction"] == "1/9"
    assert summary["unscheduled_cells_count"] == 7
    assert summary["attempted_short_labels"] == ["007 / C1", "007 / C2"]
    assert summary["unscheduled_short_labels"] == [
        "007 / C3",
        "011 / C1",
        "011 / C2",
        "011 / C3",
        "015 / C1",
        "015 / C2",
        "015 / C3",
    ]
    assert summary["fail_stop_triggered"] is True
    assert summary["stopped_at_order_index"] == 2
    assert (
        summary["stopped_at_cell_id"]
        == "W06-AMENDMENT-01-CANARY-02-P1-C2-W06-DEV-TUNE-007"
    )
    assert summary["stopped_at_short_label"] == "007 / C2"
    assert summary["scheduled_inter_call_delays_executed"] == 1
    assert summary["scheduled_inter_call_delays_ms"] == [2000]
    assert summary["ALL_9_CANARY_OPERATIONAL_PASS"] is False
    assert summary["aggregate_canary_status"] == "FAIL"
    assert summary["AMENDED_COMPARATIVE_LIVE_AUTHORIZED"] is False
    assert (
        summary["next_action"]
        == "RETURN_TO_CHATGPT_AUDIT_ON_CANARY_OPERATIONAL_FAILURE"
    )

    # Verify only cells 1 and 2 directories were created on disk; cells 3..9 do not exist
    assert (
        out_root / "W06-AMENDMENT-01-CANARY-01-P1-C1-W06-DEV-TUNE-007"
    ).is_dir()
    assert (
        out_root / "W06-AMENDMENT-01-CANARY-02-P1-C2-W06-DEV-TUNE-007"
    ).is_dir()
    for unscheduled_id in summary["unscheduled_cell_ids"]:
        assert not (out_root / unscheduled_id).exists()


def test_27_simulated_8_of_9_produces_aggregate_fail(tmp_path: Path) -> None:
    """Item 27: Simulated 8/9 operational pass (cell 9 `015 / C3` fails) produces aggregate FAIL."""
    out_root = tmp_path / "sim_8_of_9"

    def _responder(
        order_index: int,
        cell_record: dict[str, Any],
        _wire_request: dict[str, Any],
    ) -> dict[str, Any]:
        if order_index == 9:
            return {
                "raw_text": "",
                "returned_model_id": None,
                "simulated_failure": DevCellFailureClassification.HTTP_429,
            }
        return {
            "raw_text": '{"days": []}',
            "returned_model_id": cell_record["requested_model_id"],
            "simulated_failure": DevCellFailureClassification.NONE,
        }

    with canary_launcher.PreflightSecretAndEnvFileAccessGuard():
        summary = canary_launcher.execute_canary_9_cell_sequence(
            repo_root=REPO_ROOT,
            output_root=out_root,
            execution_mode="OFFLINE_SIMULATION",
            simulated_cell_responder=_responder,
            persist_artifacts=True,
        )

    assert summary["attempted_cells_count"] == 9
    assert summary["operational_pass_cells_count"] == 8
    assert summary["operational_pass_fraction"] == "8/9"
    assert summary["unscheduled_cells_count"] == 0
    assert summary["fail_stop_triggered"] is True
    assert summary["stopped_at_order_index"] == 9
    assert summary["stopped_at_short_label"] == "015 / C3"
    assert summary["scheduled_inter_call_delays_executed"] == 8
    assert summary["total_inter_call_delay_ms_executed"] == 16000
    assert summary["ALL_9_CANARY_OPERATIONAL_PASS"] is False
    assert summary["aggregate_canary_status"] == "FAIL"
    assert summary["AMENDED_COMPARATIVE_LIVE_AUTHORIZED"] is False


def test_28_simulated_9_of_9_passes_while_comparative_remains_unauthorized(
    tmp_path: Path,
) -> None:
    """Item 28: Simulated 9/9 operational pass sets ALL_9_CANARY_OPERATIONAL_PASS = true while AMENDED_COMPARATIVE_LIVE_AUTHORIZED remains false."""
    out_root = tmp_path / "sim_9_of_9"

    def _responder(
        _order_index: int,
        cell_record: dict[str, Any],
        _wire_request: dict[str, Any],
    ) -> dict[str, Any]:
        # Intentionally return non-schema-valid text on cell 1 to prove schema validity is diagnostic only
        return {
            "raw_text": '{"non_schema_valid_diagnostic_payload": true}',
            "returned_model_id": cell_record["requested_model_id"],
            "simulated_failure": DevCellFailureClassification.NONE,
        }

    with canary_launcher.PreflightSecretAndEnvFileAccessGuard():
        summary = canary_launcher.execute_canary_9_cell_sequence(
            repo_root=REPO_ROOT,
            output_root=out_root,
            execution_mode="OFFLINE_SIMULATION",
            simulated_cell_responder=_responder,
            persist_artifacts=True,
        )

    assert summary["attempted_cells_count"] == 9
    assert summary["operational_pass_cells_count"] == 9
    assert summary["operational_pass_fraction"] == "9/9"
    assert summary["unscheduled_cells_count"] == 0
    assert summary["fail_stop_triggered"] is False
    assert summary["stopped_at_order_index"] is None
    assert summary["scheduled_inter_call_delays_executed"] == 8
    assert summary["scheduled_inter_call_delays_ms"] == [2000] * 8
    assert summary["total_inter_call_delay_ms_executed"] == 16000
    assert summary["ALL_9_CANARY_OPERATIONAL_PASS"] is True
    assert summary["aggregate_canary_status"] == "PASS"

    # Comparative, winner, stochasticity, and Final100 firewalls remain strictly closed
    assert summary["AMENDED_COMPARATIVE_LIVE_AUTHORIZED"] is False
    assert summary["COMPARATIVE_EXECUTED"] is False
    assert summary["canary_pass_auto_authorizes_comparative"] is False
    assert summary["MODEL_WINNER_SELECTED"] is False
    assert summary["SELECTED_MODEL_ID"] is None
    assert summary["STOCHASTICITY_EXECUTION_STARTED"] is False
    assert summary["FINAL100_USED"] is False
    assert summary["FINAL100_STATUS"] == "NO-GO"

    # Verify diagnostic schema validity was recorded as False without blocking operational PASS
    for cell_ev in summary["attempted_cells"]:
        assert cell_ev["cell_operational_pass"] is True
        assert cell_ev["diagnostic_schema_valid"] is False
        assert all(cell_ev["required_operational_conditions"].values())


def test_29_cli_safety_flags_and_live_execution_gate_firewall() -> None:
    """Verify CLI flag discipline and that Mode B rejects execution while AMENDED_CANARY_LIVE_AUTHORIZED is false."""
    with pytest.raises(LiveExecutionNotAuthorizedError, match="NO_MODE_SPECIFIED"):
        canary_launcher.run_canary_launcher_cli([])

    with pytest.raises(
        LiveExecutionNotAuthorizedError, match="LIVE_CONFIRMATION_FLAG_MISSING"
    ):
        canary_launcher.run_canary_launcher_cli(["--execute-live"])

    with pytest.raises(
        LiveExecutionNotAuthorizedError, match="LIVE_EXECUTION_FLAG_MISSING"
    ):
        canary_launcher.run_canary_launcher_cli(["--confirm-frozen-9-canary-cells"])

    with pytest.raises(
        PlanBeforeLiveProtocolError, match="MODE_CONFLICT_FORBIDDEN"
    ):
        canary_launcher.run_canary_launcher_cli(
            ["--preflight", "--execute-live", "--confirm-frozen-9-canary-cells"]
        )

    with pytest.raises(
        Final100FirewallViolationError, match="FINAL100_FIREWALL_VIOLATION"
    ):
        canary_launcher.run_canary_launcher_cli(["--final100"])

    with pytest.raises(
        StochasticityGateViolationError,
        match="STOCHASTICITY_FORBIDDEN_IN_CANARY_LAUNCHER",
    ):
        canary_launcher.run_canary_launcher_cli(["--stochasticity"])

    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="FROZEN_CANARY_SCOPE_OVERRIDE_FORBIDDEN",
    ):
        canary_launcher.run_canary_launcher_cli(["--timeout=60000"])

    with pytest.raises(
        LiveExecutionNotAuthorizedError,
        match="CANARY_LIVE_EXECUTION_NOT_YET_AUTHORIZED",
    ):
        canary_launcher.run_canary_launcher_cli(
            ["--execute-live", "--confirm-frozen-9-canary-cells"]
        )
