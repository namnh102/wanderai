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
    ProviderNormalizedTransportResponse,
    StochasticityGateViolationError,
)
from app.evaluation.dev_selection_harness import (  # noqa: E402
    FORBIDDEN_FINAL100_BUNDLE_SHA256,
    FORBIDDEN_P11_MANIFEST_SHA256,
    SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS,
    DevCellFailureClassification,
    Final100FirewallViolationError,
    canonical_json_bytes,
    compute_scientific_code_bundle_sha256,
    normalize_lf_bytes,
    sha256_bytes,
)
import freeze_w06_dev_select_amendment_01_canary_live_execution_authorization as exec_auth_mod  # noqa: E402
import run_w06_dev_select_amendment_01_canary_live_v1 as canary_launcher  # noqa: E402

_ORIG_INSPECT_EXEC_AUTH_STATE = (
    canary_launcher.inspect_canary_live_execution_authorization_state
)
_ORIG_VERIFY_EXEC_AUTH_RECEIPT = (
    canary_launcher.verify_canary_live_execution_authorization_receipt
)
_PRE_RECEIPT_ABSENT_SENTINEL_REL_PATH = (
    "data/evaluation/w06/_pre_receipt_absent_simulation_v1.json"
)


def _inspect_exec_auth_with_downstream_receipt_exemption(
    repo_root: Path = REPO_ROOT,
    *,
    receipt_path_override: Path | None = None,
    git_runner: Any = None,
    launcher_file_path_override: Path | None = None,
) -> dict[str, Any]:
    if (
        receipt_path_override is None
        and repo_root == REPO_ROOT
        and exec_auth_mod.is_verified_downstream_w06_canary_live_execution_authorization_receipt(
            REPO_ROOT
        )
    ):
        receipt_path_override = repo_root / _PRE_RECEIPT_ABSENT_SENTINEL_REL_PATH
    return _ORIG_INSPECT_EXEC_AUTH_STATE(
        repo_root=repo_root,
        receipt_path_override=receipt_path_override,
        git_runner=git_runner,
        launcher_file_path_override=launcher_file_path_override,
    )


def _verify_exec_auth_with_downstream_receipt_exemption(
    repo_root: Path = REPO_ROOT,
    *,
    receipt_path_override: Path | None = None,
    receipt_payload_override: Any = None,
    git_runner: Any = None,
    launcher_file_path_override: Path | None = None,
) -> dict[str, Any]:
    if (
        receipt_path_override is None
        and receipt_payload_override is None
        and repo_root == REPO_ROOT
        and exec_auth_mod.is_verified_downstream_w06_canary_live_execution_authorization_receipt(
            REPO_ROOT
        )
    ):
        receipt_path_override = repo_root / _PRE_RECEIPT_ABSENT_SENTINEL_REL_PATH
    return _ORIG_VERIFY_EXEC_AUTH_RECEIPT(
        repo_root=repo_root,
        receipt_path_override=receipt_path_override,
        receipt_payload_override=receipt_payload_override,
        git_runner=git_runner,
        launcher_file_path_override=launcher_file_path_override,
    )


@pytest.fixture(autouse=True)
def _enforce_offline_guards(monkeypatch: pytest.MonkeyPatch):
    """Run every test in this module under the offline network kill-switch."""
    monkeypatch.setattr(
        canary_launcher,
        "inspect_canary_live_execution_authorization_state",
        _inspect_exec_auth_with_downstream_receipt_exemption,
    )
    monkeypatch.setattr(
        canary_launcher,
        "verify_canary_live_execution_authorization_receipt",
        _verify_exec_auth_with_downstream_receipt_exemption,
    )
    with canary_launcher.NetworkKillSwitchGuard():
        yield


@pytest.fixture(scope="module")
def preflight_out(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """Execute `--preflight` once at module scope in an isolated pre-execution output root."""
    isolated_pre_live_root = (
        tmp_path_factory.mktemp("canary_preflight_pre_live_root")
        / "live_amendment_01_canary_v1"
    )
    orig_inspect = canary_launcher.inspect_canary_live_execution_authorization_state
    orig_verify = canary_launcher.verify_canary_live_execution_authorization_receipt
    canary_launcher.inspect_canary_live_execution_authorization_state = (  # type: ignore[assignment]
        _inspect_exec_auth_with_downstream_receipt_exemption
    )
    canary_launcher.verify_canary_live_execution_authorization_receipt = (  # type: ignore[assignment]
        _verify_exec_auth_with_downstream_receipt_exemption
    )
    try:
        return canary_launcher.run_canary_launcher_cli(
            ["--preflight"],
            repo_root=REPO_ROOT,
            output_root_override=isolated_pre_live_root,
        )
    finally:
        canary_launcher.inspect_canary_live_execution_authorization_state = (  # type: ignore[assignment]
            orig_inspect
        )
        canary_launcher.verify_canary_live_execution_authorization_receipt = (  # type: ignore[assignment]
            orig_verify
        )


@pytest.fixture(scope="module")
def verified_authorities(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """Verify frozen canary launcher authorities once at module scope in an isolated pre-execution output root."""
    isolated_pre_live_root = (
        tmp_path_factory.mktemp("canary_authorities_pre_live_root")
        / "live_amendment_01_canary_v1"
    )
    return canary_launcher.verify_frozen_canary_launcher_authorities(
        REPO_ROOT,
        output_root_override=isolated_pre_live_root,
    )


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


def test_29_cli_safety_flags_and_live_execution_gate_firewall(
    tmp_path: Path,
) -> None:
    """Verify CLI flag discipline and that Mode B rejects execution while AMENDED_CANARY_LIVE_AUTHORIZED is false."""
    isolated_pre_live_root = tmp_path / "isolated_cli_pre_live_root"
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
        match="CANARY_LIVE_EXECUTION_AUTHORIZATION_RECEIPT_MISSING",
    ):
        canary_launcher.run_canary_launcher_cli(
            ["--execute-live", "--confirm-frozen-9-canary-cells"],
            output_root_override=isolated_pre_live_root,
        )


# ==============================================================================
# CORRECTIVE 01 — BLOCKER 1 & SECTION 5: TWO-LAYER LIVE-EXECUTION AUTHORIZATION
# (12 REQUIRED SCENARIOS)
# ==============================================================================


SYNTHETIC_PR_73_HEAD_SHA = "b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1"
SYNTHETIC_PR_73_MERGE_SHA = "c2c2c2c2c2c2c2c2c2c2c2c2c2c2c2c2c2c2c2c2"
SYNTHETIC_RUNTIME_HEAD_SHA = "d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3"


def _current_launcher_lf_sha256() -> str:
    return sha256_bytes(
        normalize_lf_bytes(
            (REPO_ROOT / canary_launcher.LAUNCHER_REL_PATH).read_bytes()
        )
    )


def _make_synthetic_git_runner(
    *,
    parents_by_commit: dict[str, list[str]] | None = None,
    runtime_head_sha: str = SYNTHETIC_RUNTIME_HEAD_SHA,
):
    """Build an offline synthetic Git graph runner (`BASE -> PR_HEAD -> MERGE(BASE, PR_HEAD) -> RUNTIME_HEAD`)."""
    base_sha = canary_launcher.AUTHORITATIVE_BASE_DEVELOP_SHA
    default_graph: dict[str, list[str]] = {
        canary_launcher.PR_72_MERGE_PARENT_1: [],
        canary_launcher.PR_72_MERGE_PARENT_2: [],
        base_sha: [
            canary_launcher.PR_72_MERGE_PARENT_1,
            canary_launcher.PR_72_MERGE_PARENT_2,
        ],
        SYNTHETIC_PR_73_HEAD_SHA: [base_sha],
        SYNTHETIC_PR_73_MERGE_SHA: [base_sha, SYNTHETIC_PR_73_HEAD_SHA],
        SYNTHETIC_RUNTIME_HEAD_SHA: [SYNTHETIC_PR_73_MERGE_SHA],
    }
    graph = parents_by_commit if parents_by_commit is not None else default_graph

    def _is_ancestor(anc: str, desc: str) -> bool:
        if anc not in graph or desc not in graph:
            return False
        visited: set[str] = set()
        stack = [desc]
        while stack:
            cur = stack.pop()
            if cur == anc:
                return True
            if cur in visited:
                continue
            visited.add(cur)
            stack.extend(graph.get(cur, []))
        return False

    def _runner(args: list[str]) -> subprocess.CompletedProcess[str]:
        if len(args) >= 3 and args[0] == "cat-file" and args[1] == "-e":
            target = args[2].split("^")[0]
            rc = 0 if target in graph else 1
            return subprocess.CompletedProcess(args, rc, stdout="", stderr="")
        if (
            len(args) >= 4
            and args[0] == "rev-list"
            and "--parents" in args
            and "-n" in args
        ):
            target = args[-1]
            if target not in graph:
                return subprocess.CompletedProcess(args, 1, stdout="", stderr="missing")
            parents = graph[target]
            line = " ".join([target, *parents]) + "\n"
            return subprocess.CompletedProcess(args, 0, stdout=line, stderr="")
        if (
            len(args) >= 4
            and args[0] == "merge-base"
            and args[1] == "--is-ancestor"
        ):
            anc, desc = args[2], args[3]
            rc = 0 if _is_ancestor(anc, desc) else 1
            return subprocess.CompletedProcess(args, rc, stdout="", stderr="")
        if args == ["rev-parse", "HEAD"]:
            return subprocess.CompletedProcess(
                args, 0, stdout=f"{runtime_head_sha}\n", stderr=""
            )
        return subprocess.CompletedProcess(args, 1, stdout="", stderr="unsupported")

    return _runner


def _build_synthetic_valid_receipt(
    *,
    launcher_pr_head_sha: str = SYNTHETIC_PR_73_HEAD_SHA,
    launcher_merge_commit_sha: str = SYNTHETIC_PR_73_MERGE_SHA,
    authorized_code_basis_commit_sha: str = SYNTHETIC_PR_73_MERGE_SHA,
    launcher_file_lf_sha256: str | None = None,
    launcher_pr_number: int = 73,
    overrides: dict[str, Any] | None = None,
    recompute_internal_sha: bool = True,
) -> dict[str, Any]:
    return canary_launcher.build_canary_live_execution_authorization_receipt_payload(
        launcher_pr_head_sha=launcher_pr_head_sha,
        launcher_merge_commit_sha=launcher_merge_commit_sha,
        authorized_code_basis_commit_sha=authorized_code_basis_commit_sha,
        launcher_file_lf_sha256=(
            launcher_file_lf_sha256
            if launcher_file_lf_sha256 is not None
            else _current_launcher_lf_sha256()
        ),
        launcher_pr_number=launcher_pr_number,
        overrides=overrides,
        recompute_internal_sha=recompute_internal_sha,
    )


def _resign_receipt(payload: dict[str, Any]) -> dict[str, Any]:
    """Recompute canonical internal SHA256 after mutating a field (to isolate field-level checks)."""
    cloned = copy.deepcopy(payload)
    key = canary_launcher.CANARY_LIVE_EXECUTION_AUTH_INTERNAL_SHA_KEY
    without_sig = {k: v for k, v in cloned.items() if k != key}
    cloned[key] = sha256_bytes(canonical_json_bytes(without_sig))
    return cloned


def _write_receipt(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def test_30_auth_01_no_execution_receipt_and_prep_immutability_state(
    preflight_out: dict[str, Any],
    verified_authorities: dict[str, Any],
    tmp_path: Path,
) -> None:
    """Auth Test 1: No execution receipt exists in repo; preflight reports receipt absent/unauthorized; live mode fails before key access or network; mutating PREP AMENDED_CANARY_LIVE_AUTHORIZED to true fails closed."""
    prod_receipt_path = (
        REPO_ROOT / canary_launcher.CANARY_LIVE_EXECUTION_AUTH_RECEIPT_REL_PATH
    )
    assert (
        not prod_receipt_path.exists()
        or exec_auth_mod.is_verified_downstream_w06_canary_live_execution_authorization_receipt(
            REPO_ROOT
        )
    )
    assert (
        preflight_out["canary_authorization_prep_doc_path"]
        == "docs/research/w06_dev_select_amendment_01_canary_live_authorization_prep.md"
    )
    assert (
        preflight_out["execution_authorization_receipt_path"]
        == "data/evaluation/w06/w06_dev_select_amendment_01_canary_live_execution_authorization_v1.json"
    )
    assert preflight_out["execution_authorization_receipt_present"] is False
    assert preflight_out["effective_live_execution_authorized"] is False
    assert preflight_out["live_execution_available"] is False
    assert preflight_out["AMENDED_CANARY_LIVE_AUTHORIZED"] is False

    # Also verify that if anyone mutated AMENDED_CANARY_LIVE_AUTHORIZED to True in PREP, contract verification rejects it
    mutated_prep = copy.deepcopy(verified_authorities["auth_prep"])
    mutated_prep["AMENDED_CANARY_LIVE_AUTHORIZED"] = True
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="CANARY_AUTH_PREP_STATE_FLAG_MISMATCH"
    ):
        canary_launcher.verify_frozen_canary_contract_and_cells(
            auth_prep=mutated_prep,
            canary_manifest=verified_authorities["canary_manifest"],
            dev_bundle=verified_authorities["dev_bundle"],
            cand_reg=verified_authorities["candidate_registry"],
            p1_spec=verified_authorities["p1_spec"],
        )

    key_loader_called = False

    def _forbidden_key_loader(_cid: str) -> str:
        nonlocal key_loader_called
        key_loader_called = True
        raise AssertionError("Key loader must not be reached when receipt is absent")

    missing_receipt = tmp_path / "nonexistent_receipt.json"
    out_root = tmp_path / "unauth_live_out"
    with pytest.raises(
        LiveExecutionNotAuthorizedError,
        match="CANARY_LIVE_EXECUTION_AUTHORIZATION_RECEIPT_MISSING",
    ):
        canary_launcher.run_live_canary_execution(
            repo_root=REPO_ROOT,
            output_root_override=out_root,
            execution_authorization_receipt_path_override=missing_receipt,
            api_key_loader=_forbidden_key_loader,
        )
    assert key_loader_called is False
    assert not out_root.exists()


def test_31_auth_02_malformed_execution_receipt_fails(tmp_path: Path) -> None:
    """Auth Test 2: Malformed JSON or non-mapping receipt fails closed."""
    bad_json_path = tmp_path / "malformed.json"
    bad_json_path.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(
        LiveExecutionNotAuthorizedError,
        match="CANARY_LIVE_EXECUTION_AUTHORIZATION_RECEIPT_MALFORMED",
    ):
        canary_launcher.verify_canary_live_execution_authorization_receipt(
            repo_root=REPO_ROOT, receipt_path_override=bad_json_path
        )

    list_json_path = tmp_path / "list_receipt.json"
    list_json_path.write_text("[1, 2, 3]\n", encoding="utf-8")
    with pytest.raises(
        LiveExecutionNotAuthorizedError,
        match="CANARY_LIVE_EXECUTION_AUTHORIZATION_RECEIPT_MALFORMED",
    ):
        canary_launcher.verify_canary_live_execution_authorization_receipt(
            repo_root=REPO_ROOT, receipt_path_override=list_json_path
        )


def test_32_auth_03_wrong_prep_hash_in_receipt_fails(tmp_path: Path) -> None:
    """Auth Test 3: Wrong canary authorization PREP file/internal/doc SHA256 in receipt fails closed."""
    base = _build_synthetic_valid_receipt()
    for field in (
        "canary_authorization_prep_file_sha256",
        "canary_authorization_prep_internal_sha256",
        "canary_authorization_prep_doc_sha256",
    ):
        bad = copy.deepcopy(base)
        bad[field] = "0" * 64
        bad = _resign_receipt(bad)
        p = _write_receipt(tmp_path / f"bad_{field}.json", bad)
        with pytest.raises(
            LiveExecutionNotAuthorizedError,
            match="CANARY_EXECUTION_AUTH_PREP_SHA256_MISMATCH",
        ):
            canary_launcher.verify_canary_live_execution_authorization_receipt(
                repo_root=REPO_ROOT,
                receipt_path_override=p,
                git_runner=_make_synthetic_git_runner(),
            )


def test_33_auth_04_wrong_manifest_hash_in_receipt_fails(tmp_path: Path) -> None:
    """Auth Test 4: Wrong canary manifest file/internal SHA256 in receipt fails closed."""
    base = _build_synthetic_valid_receipt()
    for field in ("canary_manifest_file_sha256", "canary_manifest_internal_sha256"):
        bad = copy.deepcopy(base)
        bad[field] = "f" * 64
        bad = _resign_receipt(bad)
        p = _write_receipt(tmp_path / f"bad_{field}.json", bad)
        with pytest.raises(
            LiveExecutionNotAuthorizedError,
            match="CANARY_EXECUTION_AUTH_MANIFEST_SHA256_MISMATCH",
        ):
            canary_launcher.verify_canary_live_execution_authorization_receipt(
                repo_root=REPO_ROOT,
                receipt_path_override=p,
                git_runner=_make_synthetic_git_runner(),
            )


def test_34_auth_05_wrong_model_set_in_receipt_fails(tmp_path: Path) -> None:
    """Auth Test 5: Wrong model set in receipt fails closed."""
    base = _build_synthetic_valid_receipt()
    bad = copy.deepcopy(base)
    bad["candidates"]["C2"]["exact_model_id"] = "gpt-5.4"
    bad = _resign_receipt(bad)
    p = _write_receipt(tmp_path / "bad_models.json", bad)
    with pytest.raises(
        CandidateRegistryIntegrityError,
        match="CANARY_EXECUTION_AUTH_CANDIDATE_SET_MISMATCH",
    ):
        canary_launcher.verify_canary_live_execution_authorization_receipt(
            repo_root=REPO_ROOT,
            receipt_path_override=p,
            git_runner=_make_synthetic_git_runner(),
        )


def test_35_auth_06_wrong_9_cell_order_in_receipt_fails(tmp_path: Path) -> None:
    """Auth Test 6: Wrong 9-cell execution order in receipt fails closed."""
    base = _build_synthetic_valid_receipt()
    bad = copy.deepcopy(base)
    cells = bad["exact_9_cell_execution_order"]
    cells[0], cells[1] = cells[1], cells[0]
    bad = _resign_receipt(bad)
    p = _write_receipt(tmp_path / "bad_order.json", bad)
    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="CANARY_EXECUTION_AUTH_9_CELL_ORDER_MISMATCH",
    ):
        canary_launcher.verify_canary_live_execution_authorization_receipt(
            repo_root=REPO_ROOT,
            receipt_path_override=p,
            git_runner=_make_synthetic_git_runner(),
        )


def test_36_auth_07_max_calls_not_equal_9_in_receipt_fails(tmp_path: Path) -> None:
    """Auth Test 7: max_provider_generation_calls != 9 in receipt fails closed."""
    base = _build_synthetic_valid_receipt()
    bad = copy.deepcopy(base)
    bad["max_provider_generation_calls"] = 18
    bad = _resign_receipt(bad)
    p = _write_receipt(tmp_path / "bad_max_calls.json", bad)
    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="CANARY_EXECUTION_AUTH_RUNTIME_POLICY_MISMATCH",
    ):
        canary_launcher.verify_canary_live_execution_authorization_receipt(
            repo_root=REPO_ROOT,
            receipt_path_override=p,
            git_runner=_make_synthetic_git_runner(),
        )


def test_37_auth_08_retry_not_zero_in_receipt_fails(tmp_path: Path) -> None:
    """Auth Test 8: Any retry dimension != 0 in receipt fails closed."""
    base = _build_synthetic_valid_receipt()
    bad = copy.deepcopy(base)
    bad["automatic_retry"] = 1
    bad = _resign_receipt(bad)
    p = _write_receipt(tmp_path / "bad_retry.json", bad)
    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="CANARY_EXECUTION_AUTH_RUNTIME_POLICY_MISMATCH",
    ):
        canary_launcher.verify_canary_live_execution_authorization_receipt(
            repo_root=REPO_ROOT,
            receipt_path_override=p,
            git_runner=_make_synthetic_git_runner(),
        )


def test_38_auth_09_comparative_authorized_true_in_receipt_fails(
    tmp_path: Path,
) -> None:
    """Auth Test 9: AMENDED_COMPARATIVE_LIVE_AUTHORIZED = true in receipt fails closed."""
    base = _build_synthetic_valid_receipt()
    bad = copy.deepcopy(base)
    bad["AMENDED_COMPARATIVE_LIVE_AUTHORIZED"] = True
    bad = _resign_receipt(bad)
    p = _write_receipt(tmp_path / "bad_comp_auth.json", bad)
    with pytest.raises(
        LiveExecutionNotAuthorizedError,
        match="CANARY_EXECUTION_AUTH_COMPARATIVE_OR_DOWNSTREAM_FORBIDDEN",
    ):
        canary_launcher.verify_canary_live_execution_authorization_receipt(
            repo_root=REPO_ROOT,
            receipt_path_override=p,
            git_runner=_make_synthetic_git_runner(),
        )


def test_39_auth_10_holdout_firewall_authorized_or_used_in_receipt_fails(
    tmp_path: Path,
) -> None:
    """Auth Test 10: FINAL100_USED = true or FINAL100_STATUS != 'NO-GO' in receipt fails closed."""
    base = _build_synthetic_valid_receipt()
    bad = copy.deepcopy(base)
    bad["FINAL100_USED"] = True
    bad = _resign_receipt(bad)
    p = _write_receipt(tmp_path / "bad_holdout_flag.json", bad)
    with pytest.raises(
        Final100FirewallViolationError,
        match="CANARY_EXECUTION_AUTH_FINAL100_FORBIDDEN",
    ):
        canary_launcher.verify_canary_live_execution_authorization_receipt(
            repo_root=REPO_ROOT,
            receipt_path_override=p,
            git_runner=_make_synthetic_git_runner(),
        )


def test_40_auth_11_tampered_internal_sha_in_receipt_fails(tmp_path: Path) -> None:
    """Auth Test 11: Tampered canary_live_execution_authorization_internal_sha256 fails closed."""
    base = _build_synthetic_valid_receipt()
    tampered = copy.deepcopy(base)
    tampered[canary_launcher.CANARY_LIVE_EXECUTION_AUTH_INTERNAL_SHA_KEY] = "a" * 64
    p = _write_receipt(tmp_path / "tampered_sha.json", tampered)
    with pytest.raises(
        LiveExecutionNotAuthorizedError,
        match="CANARY_LIVE_EXECUTION_AUTHORIZATION_INTERNAL_SHA256_MISMATCH",
    ):
        canary_launcher.verify_canary_live_execution_authorization_receipt(
            repo_root=REPO_ROOT,
            receipt_path_override=p,
            git_runner=_make_synthetic_git_runner(),
        )


def test_41_auth_12_valid_synthetic_temporary_receipt_passes_verifier_offline(
    tmp_path: Path,
) -> None:
    """Auth Test 12: Valid synthetic temporary receipt passes two-layer authorization verifier without any live network call."""
    valid_payload = _build_synthetic_valid_receipt()
    receipt_path = _write_receipt(tmp_path / "valid_synthetic_receipt.json", valid_payload)
    out_root = tmp_path / "valid_auth_out_root"

    with canary_launcher.PreflightSecretAndEnvFileAccessGuard():
        res = canary_launcher.verify_two_layer_canary_live_execution_authorization(
            repo_root=REPO_ROOT,
            execution_auth_receipt_path_override=receipt_path,
            output_root_override=out_root,
            git_runner=_make_synthetic_git_runner(),
        )

    assert res["verified"] is True
    assert res["layer_1_frozen_auth_prep_verified"] is True
    assert res["layer_1_auth_prep_amended_canary_live_authorized"] is False
    assert res["layer_2_execution_authorization_receipt_verified"] is True
    assert res["effective_live_execution_authorized"] is True
    assert res["execution_authorization_receipt"]["CANARY_LIVE_EXECUTION_AUTHORIZED"] is True
    assert (
        res["authorities"]["auth_prep"]["AMENDED_CANARY_LIVE_AUTHORIZED"]
        is False
    )


# ==============================================================================
# CORRECTIVE 01 — BLOCKER 2: PRE-PROVIDER CREDENTIAL FAILURE & PROVIDER EXCEPTION
# ==============================================================================


def test_42_blocker_2a_missing_credential_before_generation_invocation_fails_closed(
    tmp_path: Path,
) -> None:
    """Blocker 2(A): Missing credential before generation invocation writes cell failure evidence with 0 logical/actual calls, triggers fail-stop, leaves remaining cells unscheduled, and leaks no secrets."""
    valid_payload = _build_synthetic_valid_receipt()
    receipt_path = _write_receipt(
        tmp_path / "synthetic_exec_receipt.json", valid_payload
    )
    out_root = tmp_path / "sim_missing_credential_cell_1"
    invoker_called = False

    def _missing_key_loader(cid: str) -> str:
        raise LiveExecutionNotAuthorizedError(
            f"MISSING_PROVIDER_API_KEY_FOR_{cid}: GEMINI_API_KEY is not configured."
        )

    def _never_called_invoker(**_kwargs: Any) -> ProviderNormalizedTransportResponse:
        nonlocal invoker_called
        invoker_called = True
        raise AssertionError("Transport invoker must not be called when key is missing")

    summary = canary_launcher.run_live_canary_execution(
        repo_root=REPO_ROOT,
        output_root_override=out_root,
        execution_authorization_receipt_path_override=receipt_path,
        git_runner=_make_synthetic_git_runner(),
        api_key_loader=_missing_key_loader,
        live_transport_invoker=_never_called_invoker,
        sleep_fn=lambda _sec: None,
    )

    assert invoker_called is False
    assert summary["attempted_cells_count"] == 1
    assert summary["total_logical_generation_invocations"] == 0
    assert summary["total_actual_provider_http_requests"] == 0
    assert summary["operational_pass_cells_count"] == 0
    assert summary["operational_pass_fraction"] == "0/9"
    assert summary["unscheduled_cells_count"] == 8
    assert summary["fail_stop_triggered"] is True
    assert summary["stopped_at_order_index"] == 1
    assert summary["stopped_at_short_label"] == "007 / C1"
    assert summary["ALL_9_CANARY_OPERATIONAL_PASS"] is False
    assert summary["aggregate_canary_status"] == "FAIL"

    cell_1 = summary["attempted_cells"][0]
    assert cell_1["logical_generation_invocation_count"] == 0
    assert cell_1["generation_call_count"] == 0
    assert cell_1["actual_provider_http_request_count"] == 0
    assert cell_1["provider_response_received"] is False
    assert cell_1["provider_returned_response"] is False
    assert cell_1["authentication_failure"] is True
    assert cell_1["cell_operational_pass"] is False
    assert (
        cell_1["required_operational_conditions"][
            "exactly_one_generation_call_attempted"
        ]
        is False
    )
    assert (
        cell_1["required_operational_conditions"]["no_authentication_failure"]
        is False
    )
    assert (
        cell_1["required_operational_conditions"]["provider_returns_response"]
        is False
    )

    # Verify all per-cell evidence files were written for cell 1 and none for cells 2..9
    cell_1_dir = out_root / "W06-AMENDMENT-01-CANARY-01-P1-C1-W06-DEV-TUNE-007"
    assert cell_1_dir.is_dir()
    for fname in canary_launcher.CANARY_CELL_ARTIFACT_FILENAMES:
        assert (cell_1_dir / fname).is_file()
    for unscheduled_id in summary["unscheduled_cell_ids"]:
        assert not (out_root / unscheduled_id).exists()


def test_43_blocker_2b_provider_exception_after_1_generation_invocation_records_truthful_counts(
    tmp_path: Path,
) -> None:
    """Blocker 2(B): Provider exception after 1 generation invocation records logical_generation_invocation_count = 1, actual_provider_http_request_count from counter, retry_count = 0, and triggers fail-stop."""
    valid_payload = _build_synthetic_valid_receipt()
    receipt_path = _write_receipt(
        tmp_path / "synthetic_exec_receipt.json", valid_payload
    )
    out_root = tmp_path / "sim_provider_exception_cell_1"

    def _dummy_key_loader(_cid: str) -> str:
        return "DUMMY_NON_SECRET_TEST_TOKEN"

    def _failing_transport_invoker(
        *,
        cell_manifest: Any,
        wire_request: dict[str, Any],
        http_counter: Any,
        api_key: str,
    ) -> ProviderNormalizedTransportResponse:
        assert api_key == "DUMMY_NON_SECRET_TEST_TOKEN"
        assert wire_request["candidate_id"] == "C1"
        # Simulate exactly 1 outbound HTTP attempt recorded by the transport wrapper before raising TimeoutError
        http_counter.record_outbound_http_request_before_send(
            run_id=cell_manifest.run_id,
            candidate_id=cell_manifest.candidate_id,
            method="POST",
            url="https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent",
            body_bytes=b"{}",
        )
        raise TimeoutError("ReadTimeout after 180000ms")

    summary = canary_launcher.run_live_canary_execution(
        repo_root=REPO_ROOT,
        output_root_override=out_root,
        execution_authorization_receipt_path_override=receipt_path,
        git_runner=_make_synthetic_git_runner(),
        api_key_loader=_dummy_key_loader,
        live_transport_invoker=_failing_transport_invoker,
        sleep_fn=lambda _sec: None,
    )

    assert summary["attempted_cells_count"] == 1
    assert summary["total_logical_generation_invocations"] == 1
    assert summary["total_actual_provider_http_requests"] == 1
    assert summary["operational_pass_cells_count"] == 0
    assert summary["unscheduled_cells_count"] == 8
    assert summary["fail_stop_triggered"] is True
    assert summary["stopped_at_order_index"] == 1
    assert summary["ALL_9_CANARY_OPERATIONAL_PASS"] is False

    cell_1 = summary["attempted_cells"][0]
    assert cell_1["logical_generation_invocation_count"] == 1
    assert cell_1["generation_call_count"] == 1
    assert cell_1["actual_provider_http_request_count"] == 1
    assert cell_1["retry_count"] == 0
    assert cell_1["provider_response_received"] is False
    assert cell_1["provider_returned_response"] is False
    assert cell_1["timeout_failure"] is True
    assert cell_1["cell_operational_pass"] is False
    assert (
        cell_1["required_operational_conditions"][
            "exactly_one_generation_call_attempted"
        ]
        is True
    )
    assert cell_1["required_operational_conditions"]["no_client_timeout"] is False
    assert (
        cell_1["required_operational_conditions"]["provider_returns_response"]
        is False
    )
    assert cell_1["required_operational_conditions"]["retry_count_equals_zero"] is True


# ==============================================================================
# CORRECTIVE 01 — BLOCKER 3: ADVERSARIAL `provider_returns_response` SEMANTICS
# ==============================================================================


def test_44_blocker_3a_empty_text_with_valid_provider_response_passes_operationally(
    tmp_path: Path,
) -> None:
    """Blocker 3(A): Provider response received with empty raw_text ('') and valid model identity passes operationally."""
    out_root = tmp_path / "sim_empty_text_operational_pass"

    def _responder(
        _order_index: int,
        cell_record: dict[str, Any],
        _wire_request: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "raw_text": "",
            "returned_model_id": cell_record["requested_model_id"],
            "provider_response_received": True,
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

    assert summary["ALL_9_CANARY_OPERATIONAL_PASS"] is True
    assert summary["operational_pass_cells_count"] == 9
    for cell_ev in summary["attempted_cells"]:
        assert cell_ev["provider_response_received"] is True
        assert cell_ev["provider_returned_response"] is True
        assert (
            cell_ev["required_operational_conditions"]["provider_returns_response"]
            is True
        )
        assert cell_ev["raw_text_present"] is True
        assert cell_ev["raw_text_non_empty"] is False
        assert cell_ev["raw_text_length"] == 0
        assert cell_ev["provider_model_identity_evidence_captured"] is True
        assert cell_ev["diagnostic_schema_valid"] is False
        assert cell_ev["cell_operational_pass"] is True


def test_45_blocker_3b_refusal_or_safety_response_with_valid_identity_passes_operationally(
    tmp_path: Path,
) -> None:
    """Blocker 3(B): Provider response received in refusal/safety state with valid model identity passes operationally."""
    out_root = tmp_path / "sim_refusal_operational_pass"

    def _responder(
        _order_index: int,
        cell_record: dict[str, Any],
        _wire_request: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "raw_text": "",
            "returned_model_id": cell_record["requested_model_id"],
            "provider_response_received": True,
            "refusal_state": True,
            "finish_reason": "refusal",
            "simulated_failure": DevCellFailureClassification.REFUSAL,
        }

    with canary_launcher.PreflightSecretAndEnvFileAccessGuard():
        summary = canary_launcher.execute_canary_9_cell_sequence(
            repo_root=REPO_ROOT,
            output_root=out_root,
            execution_mode="OFFLINE_SIMULATION",
            simulated_cell_responder=_responder,
            persist_artifacts=True,
        )

    assert summary["ALL_9_CANARY_OPERATIONAL_PASS"] is True
    assert summary["operational_pass_cells_count"] == 9
    for cell_ev in summary["attempted_cells"]:
        assert cell_ev["provider_response_received"] is True
        assert cell_ev["provider_returned_response"] is True
        assert (
            cell_ev["required_operational_conditions"]["provider_returns_response"]
            is True
        )
        assert cell_ev["refusal_or_safety_state"] is True
        assert cell_ev["provider_model_identity_evidence_captured"] is True
        assert cell_ev["diagnostic_schema_valid"] is False
        assert cell_ev["cell_operational_pass"] is True


def test_46_blocker_3c_http_timeout_or_transport_failure_sets_provider_returns_response_false(
    verified_authorities: dict[str, Any],
) -> None:
    """Blocker 3(C): HTTP 4xx/5xx, timeout, and transport failures set provider_returns_response = False and cell_operational_pass = False."""
    cell_record = verified_authorities["ordered_canary_cells"][0]
    norm_usage = canary_launcher.normalize_candidate_usage_metadata("C1", None)

    for failure_cls, extra_kwargs in (
        (DevCellFailureClassification.TIMEOUT, {"provider_response_received": False}),
        (
            DevCellFailureClassification.HARNESS_INTERNAL_ERROR,
            {"provider_response_received": False, "transport_failure": True},
        ),
        (
            DevCellFailureClassification.HTTP_5XX,
            {"provider_response_received": False, "http_5xx_failure": True},
        ),
        (
            DevCellFailureClassification.HTTP_429,
            {"provider_response_received": False, "http_4xx_failure": True},
        ),
    ):
        resp = ProviderNormalizedTransportResponse(
            candidate_id="C1",
            provider="google",
            requested_model_id="gemini-3.8-flash",
            returned_model_id=None,
            raw_text="",
            finish_or_stop_reason=failure_cls.value,
            finish_reason=failure_cls.value,
            raw_usage_metadata=None,
            normalized_usage_metadata=norm_usage,
            raw_provider_metadata={},
            normalized_provider_metadata={},
            actual_http_request_count=1,
            simulated_failure=failure_cls,
            authoritative_usage_available=False,
        )
        op_eval = canary_launcher.evaluate_canary_cell_operational_pass(
            cell_record=cell_record,
            transport_response=resp,
            generation_calls_attempted=1,
            actual_http_request_count=1,
            retry_count=0,
            **extra_kwargs,
        )
        assert op_eval["provider_response_received"] is False
        assert op_eval["provider_returned_response"] is False
        assert (
            op_eval["required_operational_conditions"]["provider_returns_response"]
            is False
        )
        assert op_eval["cell_operational_pass"] is False


# ==============================================================================
# CORRECTIVE 02 — EXECUTION AUTHORIZATION RECEIPT CRYPTOGRAPHIC CODE & GIT
# PROVENANCE BINDING (SECTIONS 2–8)
# ==============================================================================


def test_47_corrective_02_unsafe_receipt_builder_defaults_removed_and_base_develop_rejected(
    tmp_path: Path,
) -> None:
    """Section 3 & 6: Builder requires explicit provenance args (no default to 1ebe30c...) and rejects 1ebe30c... for PR head, merge commit, or code basis."""
    with pytest.raises(TypeError):
        canary_launcher.build_canary_live_execution_authorization_receipt_payload()  # type: ignore[call-arg]

    base_dev = canary_launcher.AUTHORITATIVE_BASE_DEVELOP_SHA
    for bad_kwargs in (
        {"launcher_pr_head_sha": base_dev},
        {"launcher_merge_commit_sha": base_dev},
        {"authorized_code_basis_commit_sha": base_dev},
    ):
        payload = _build_synthetic_valid_receipt(**bad_kwargs)
        p = _write_receipt(tmp_path / "bad_pre_launcher_base.json", payload)
        with pytest.raises(
            LiveExecutionNotAuthorizedError,
            match="CANARY_EXECUTION_PRE_LAUNCHER_BASE_DEVELOP_SHA_FORBIDDEN",
        ):
            canary_launcher.verify_canary_live_execution_authorization_receipt(
                repo_root=REPO_ROOT,
                receipt_path_override=p,
                git_runner=_make_synthetic_git_runner(),
            )


def test_48_corrective_02_neg_01_nonexistent_launcher_pr_head_sha_fails(
    tmp_path: Path,
) -> None:
    """Section 7(1): Nonexistent launcher_pr_head_sha fails closed."""
    missing_pr_head = "1111111111111111111111111111111111111111"
    payload = _build_synthetic_valid_receipt(launcher_pr_head_sha=missing_pr_head)
    p = _write_receipt(tmp_path / "neg_01_missing_pr_head.json", payload)
    with pytest.raises(
        LiveExecutionNotAuthorizedError,
        match="CANARY_EXECUTION_LAUNCHER_PR_HEAD_COMMIT_NOT_FOUND",
    ):
        canary_launcher.verify_canary_live_execution_authorization_receipt(
            repo_root=REPO_ROOT,
            receipt_path_override=p,
            git_runner=_make_synthetic_git_runner(),
        )


def test_49_corrective_02_neg_02_nonexistent_launcher_merge_commit_sha_fails(
    tmp_path: Path,
) -> None:
    """Section 7(2): Nonexistent launcher_merge_commit_sha fails closed."""
    missing_merge = "2222222222222222222222222222222222222222"
    payload = _build_synthetic_valid_receipt(
        launcher_merge_commit_sha=missing_merge,
        authorized_code_basis_commit_sha=missing_merge,
    )
    p = _write_receipt(tmp_path / "neg_02_missing_merge.json", payload)
    with pytest.raises(
        LiveExecutionNotAuthorizedError,
        match="CANARY_EXECUTION_LAUNCHER_MERGE_COMMIT_NOT_FOUND",
    ):
        canary_launcher.verify_canary_live_execution_authorization_receipt(
            repo_root=REPO_ROOT,
            receipt_path_override=p,
            git_runner=_make_synthetic_git_runner(),
        )


def test_50_corrective_02_neg_03_nonexistent_authorized_code_basis_commit_sha_fails(
    tmp_path: Path,
) -> None:
    """Section 7(3): Nonexistent authorized_code_basis_commit_sha fails closed."""
    missing_basis = "3333333333333333333333333333333333333333"
    payload = _build_synthetic_valid_receipt(
        authorized_code_basis_commit_sha=missing_basis,
    )
    p = _write_receipt(tmp_path / "neg_03_missing_basis.json", payload)
    with pytest.raises(
        LiveExecutionNotAuthorizedError,
        match="CANARY_EXECUTION_AUTHORIZED_CODE_BASIS_COMMIT_NOT_FOUND",
    ):
        canary_launcher.verify_canary_live_execution_authorization_receipt(
            repo_root=REPO_ROOT,
            receipt_path_override=p,
            git_runner=_make_synthetic_git_runner(),
        )


def test_51_corrective_02_neg_04_code_basis_not_equal_to_launcher_merge_commit_fails(
    tmp_path: Path,
) -> None:
    """Section 7(4): authorized_code_basis_commit_sha != launcher_merge_commit_sha fails closed even when both exist in git."""
    payload = _build_synthetic_valid_receipt(
        launcher_pr_head_sha=SYNTHETIC_PR_73_HEAD_SHA,
        launcher_merge_commit_sha=SYNTHETIC_PR_73_MERGE_SHA,
        authorized_code_basis_commit_sha=SYNTHETIC_PR_73_HEAD_SHA,
    )
    p = _write_receipt(tmp_path / "neg_04_basis_ne_merge.json", payload)
    with pytest.raises(
        LiveExecutionNotAuthorizedError,
        match="CANARY_EXECUTION_CODE_BASIS_NOT_EQUAL_TO_LAUNCHER_MERGE_COMMIT",
    ):
        canary_launcher.verify_canary_live_execution_authorization_receipt(
            repo_root=REPO_ROOT,
            receipt_path_override=p,
            git_runner=_make_synthetic_git_runner(),
        )


def test_52_corrective_02_neg_05_merge_commit_not_descended_from_expected_pr_head_fails(
    tmp_path: Path,
) -> None:
    """Section 7(5): Merge commit not descended from expected PR head fails closed."""
    base_sha = canary_launcher.AUTHORITATIVE_BASE_DEVELOP_SHA
    other_branch_head = "4444444444444444444444444444444444444444"
    bad_graph = {
        canary_launcher.PR_72_MERGE_PARENT_1: [],
        canary_launcher.PR_72_MERGE_PARENT_2: [],
        base_sha: [
            canary_launcher.PR_72_MERGE_PARENT_1,
            canary_launcher.PR_72_MERGE_PARENT_2,
        ],
        SYNTHETIC_PR_73_HEAD_SHA: [base_sha],
        other_branch_head: [base_sha],
        SYNTHETIC_PR_73_MERGE_SHA: [base_sha, other_branch_head],
        SYNTHETIC_RUNTIME_HEAD_SHA: [SYNTHETIC_PR_73_MERGE_SHA],
    }
    payload = _build_synthetic_valid_receipt()
    p = _write_receipt(tmp_path / "neg_05_wrong_pr_head_parent.json", payload)
    with pytest.raises(
        LiveExecutionNotAuthorizedError,
        match="CANARY_EXECUTION_LAUNCHER_MERGE_PR_HEAD_ANCESTRY_MISMATCH",
    ):
        canary_launcher.verify_canary_live_execution_authorization_receipt(
            repo_root=REPO_ROOT,
            receipt_path_override=p,
            git_runner=_make_synthetic_git_runner(parents_by_commit=bad_graph),
        )


def test_53_corrective_02_neg_06_wrong_base_parent_fails(
    tmp_path: Path,
) -> None:
    """Section 7(6): Wrong base parent on merge commit fails closed."""
    base_sha = canary_launcher.AUTHORITATIVE_BASE_DEVELOP_SHA
    wrong_base = "5555555555555555555555555555555555555555"
    bad_graph = {
        canary_launcher.PR_72_MERGE_PARENT_1: [],
        canary_launcher.PR_72_MERGE_PARENT_2: [],
        base_sha: [
            canary_launcher.PR_72_MERGE_PARENT_1,
            canary_launcher.PR_72_MERGE_PARENT_2,
        ],
        wrong_base: [],
        SYNTHETIC_PR_73_HEAD_SHA: [base_sha],
        SYNTHETIC_PR_73_MERGE_SHA: [wrong_base, SYNTHETIC_PR_73_HEAD_SHA],
        SYNTHETIC_RUNTIME_HEAD_SHA: [SYNTHETIC_PR_73_MERGE_SHA],
    }
    payload = _build_synthetic_valid_receipt()
    p = _write_receipt(tmp_path / "neg_06_wrong_base_parent.json", payload)
    with pytest.raises(
        LiveExecutionNotAuthorizedError,
        match="CANARY_EXECUTION_LAUNCHER_MERGE_BASE_PARENT_MISMATCH",
    ):
        canary_launcher.verify_canary_live_execution_authorization_receipt(
            repo_root=REPO_ROOT,
            receipt_path_override=p,
            git_runner=_make_synthetic_git_runner(parents_by_commit=bad_graph),
        )


def test_54_corrective_02_neg_07_merge_commit_not_ancestor_of_runtime_head_fails(
    tmp_path: Path,
) -> None:
    """Section 7(7): Merge commit not ancestor of runtime HEAD fails closed."""
    base_sha = canary_launcher.AUTHORITATIVE_BASE_DEVELOP_SHA
    unrelated_runtime = "6666666666666666666666666666666666666666"
    bad_graph = {
        canary_launcher.PR_72_MERGE_PARENT_1: [],
        canary_launcher.PR_72_MERGE_PARENT_2: [],
        base_sha: [
            canary_launcher.PR_72_MERGE_PARENT_1,
            canary_launcher.PR_72_MERGE_PARENT_2,
        ],
        SYNTHETIC_PR_73_HEAD_SHA: [base_sha],
        SYNTHETIC_PR_73_MERGE_SHA: [base_sha, SYNTHETIC_PR_73_HEAD_SHA],
        unrelated_runtime: [base_sha],
    }
    payload = _build_synthetic_valid_receipt()
    p = _write_receipt(tmp_path / "neg_07_not_runtime_ancestor.json", payload)
    with pytest.raises(
        LiveExecutionNotAuthorizedError,
        match="CANARY_EXECUTION_LAUNCHER_MERGE_NOT_ANCESTOR_OF_RUNTIME_HEAD",
    ):
        canary_launcher.verify_canary_live_execution_authorization_receipt(
            repo_root=REPO_ROOT,
            receipt_path_override=p,
            git_runner=_make_synthetic_git_runner(
                parents_by_commit=bad_graph,
                runtime_head_sha=unrelated_runtime,
            ),
        )


def test_55_corrective_02_neg_08_receipt_launcher_hash_differs_from_current_launcher_file_hash_fails(
    tmp_path: Path,
) -> None:
    """Section 7(8): Receipt launcher_file_lf_sha256 differs from current launcher file LF SHA256 fails closed."""
    wrong_file_sha = "7" * 64
    payload = _build_synthetic_valid_receipt(launcher_file_lf_sha256=wrong_file_sha)
    p = _write_receipt(tmp_path / "neg_08_wrong_launcher_sha.json", payload)
    with pytest.raises(
        LiveExecutionNotAuthorizedError,
        match="CANARY_EXECUTION_LAUNCHER_FILE_LF_SHA256_MISMATCH",
    ):
        canary_launcher.verify_canary_live_execution_authorization_receipt(
            repo_root=REPO_ROOT,
            receipt_path_override=p,
            git_runner=_make_synthetic_git_runner(),
        )


def test_56_corrective_02_neg_09_launcher_file_modified_after_authorization_fails(
    tmp_path: Path,
) -> None:
    """Section 7(9): Launcher file modified after authorization receipt was issued fails closed."""
    payload = _build_synthetic_valid_receipt()
    p = _write_receipt(tmp_path / "neg_09_valid_receipt.json", payload)

    modified_launcher = tmp_path / "modified_launcher.py"
    original_bytes = (REPO_ROOT / canary_launcher.LAUNCHER_REL_PATH).read_bytes()
    modified_launcher.write_bytes(original_bytes + b"\n# unauthorized post-auth edit\n")

    with pytest.raises(
        LiveExecutionNotAuthorizedError,
        match="CANARY_EXECUTION_LAUNCHER_FILE_LF_SHA256_MISMATCH",
    ):
        canary_launcher.verify_canary_live_execution_authorization_receipt(
            repo_root=REPO_ROOT,
            receipt_path_override=p,
            git_runner=_make_synthetic_git_runner(),
            launcher_file_path_override=modified_launcher,
        )


def test_57_corrective_02_neg_10_arbitrary_valid_looking_40_char_shas_rejected_by_real_git(
    tmp_path: Path,
) -> None:
    """Section 7(10): Arbitrary valid-looking 40-char SHA values AND real older git commits that lack PR #73 merge ancestry are rejected by real git."""
    # Case A: Arbitrary 40-char hex SHAs against real repository git (no mock git_runner)
    arbitrary_pr_head = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
    arbitrary_merge = "cafebabecafebabecafebabecafebabecafebabe"
    payload_arbitrary = _build_synthetic_valid_receipt(
        launcher_pr_head_sha=arbitrary_pr_head,
        launcher_merge_commit_sha=arbitrary_merge,
        authorized_code_basis_commit_sha=arbitrary_merge,
    )
    p_arbitrary = _write_receipt(
        tmp_path / "neg_10a_arbitrary_40char.json", payload_arbitrary
    )
    with pytest.raises(
        LiveExecutionNotAuthorizedError,
        match="CANARY_EXECUTION_LAUNCHER_PR_HEAD_COMMIT_NOT_FOUND",
    ):
        canary_launcher.verify_canary_live_execution_authorization_receipt(
            repo_root=REPO_ROOT,
            receipt_path_override=p_arbitrary,
        )

    # Case B: Real existing commit in repository git (current HEAD, present in both full and shallow CI checkouts) that lacks PR #73 merge ancestry
    real_head_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=str(REPO_ROOT),
        text=True,
    ).strip()
    payload_real_commit = _build_synthetic_valid_receipt(
        launcher_pr_head_sha=real_head_sha,
        launcher_merge_commit_sha=real_head_sha,
        authorized_code_basis_commit_sha=real_head_sha,
    )
    p_real_commit = _write_receipt(
        tmp_path / "neg_10b_real_existing_commit.json", payload_real_commit
    )
    with pytest.raises(
        LiveExecutionNotAuthorizedError,
        match=(
            "CANARY_EXECUTION_LAUNCHER_MERGE_COMMIT_NOT_TWO_PARENT_MERGE|"
            "CANARY_EXECUTION_LAUNCHER_MERGE_BASE_PARENT_MISMATCH|"
            "CANARY_EXECUTION_LAUNCHER_MERGE_PR_HEAD_ANCESTRY_MISMATCH|"
            "CANARY_EXECUTION_PRE_LAUNCHER_BASE_DEVELOP_SHA_FORBIDDEN"
        ),
    ):
        canary_launcher.verify_canary_live_execution_authorization_receipt(
            repo_root=REPO_ROOT,
            receipt_path_override=p_real_commit,
        )


def test_58_corrective_02_pos_synthetic_git_merge_graph_and_content_binding_passes_offline(
    tmp_path: Path,
) -> None:
    """Section 8: Controlled offline synthetic Git graph BASE -> PR_HEAD -> MERGE(BASE, PR_HEAD) -> RUNTIME_HEAD passes all provenance and content checks with zero network calls and zero key access."""
    expected_launcher_sha = _current_launcher_lf_sha256()
    valid_payload = _build_synthetic_valid_receipt(
        launcher_pr_head_sha=SYNTHETIC_PR_73_HEAD_SHA,
        launcher_merge_commit_sha=SYNTHETIC_PR_73_MERGE_SHA,
        authorized_code_basis_commit_sha=SYNTHETIC_PR_73_MERGE_SHA,
        launcher_file_lf_sha256=expected_launcher_sha,
        launcher_pr_number=73,
    )
    receipt_path = _write_receipt(
        tmp_path / "pos_synthetic_merge_graph_receipt.json", valid_payload
    )
    out_root = tmp_path / "pos_synthetic_out_root"
    git_runner = _make_synthetic_git_runner()

    with (
        canary_launcher.NetworkKillSwitchGuard(),
        canary_launcher.PreflightSecretAndEnvFileAccessGuard(),
    ):
        prov = canary_launcher.verify_canary_launcher_execution_code_provenance(
            repo_root=REPO_ROOT,
            launcher_pr_number=valid_payload["launcher_pr_number"],
            launcher_pr_head_sha=valid_payload["launcher_pr_head_sha"],
            launcher_merge_commit_sha=valid_payload["launcher_merge_commit_sha"],
            authorized_code_basis_commit_sha=valid_payload[
                "authorized_code_basis_commit_sha"
            ],
            launcher_file_lf_sha256=valid_payload["launcher_file_lf_sha256"],
            launcher_path=valid_payload["launcher_path"],
            git_runner=git_runner,
        )
        two_layer = canary_launcher.verify_two_layer_canary_live_execution_authorization(
            repo_root=REPO_ROOT,
            execution_auth_receipt_path_override=receipt_path,
            output_root_override=out_root,
            git_runner=git_runner,
        )

    assert prov["verified"] is True
    assert prov["launcher_pr_number"] == 73
    assert (
        prov["authoritative_base_develop_sha"]
        == "1ebe30c251958542088a3056dcfc6b780dac3a88"
    )
    assert prov["launcher_pr_head_sha"] == SYNTHETIC_PR_73_HEAD_SHA
    assert prov["launcher_merge_commit_sha"] == SYNTHETIC_PR_73_MERGE_SHA
    assert prov["authorized_code_basis_commit_sha"] == SYNTHETIC_PR_73_MERGE_SHA
    assert prov["merge_parent_1"] == "1ebe30c251958542088a3056dcfc6b780dac3a88"
    assert prov["merge_parent_2"] == SYNTHETIC_PR_73_HEAD_SHA
    assert prov["runtime_head_sha"] == SYNTHETIC_RUNTIME_HEAD_SHA
    assert prov["launcher_path"] == "scripts/run_w06_dev_select_amendment_01_canary_live_v1.py"
    assert prov["launcher_file_lf_sha256"] == expected_launcher_sha

    assert two_layer["verified"] is True
    assert two_layer["effective_live_execution_authorized"] is True
    assert (
        two_layer["execution_authorization_receipt"]["code_provenance"]["verified"]
        is True
    )
