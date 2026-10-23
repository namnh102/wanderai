"""Tests for W06-DEV-SELECT-LIVE-LAUNCHER-01-OFFLINE (DSL-01 through DSL-40 & Section 24/27/28/29).

Strictly offline:
- LIVE_PROVIDER_CALLS = 0
- PROVIDER_COST_USD = 0
- Never invokes `--execute-live --confirm-frozen-180-cells` against live provider APIs.
"""

from __future__ import annotations

import asyncio
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

from app.evaluation import dev_live_runner as dlr_mod  # noqa: E402
from app.evaluation.dev_live_runner import (  # noqa: E402
    RUNNER_EXECUTION_MODE_LIVE_EXECUTION,
    TRANSPORT_STATUS_NOT_INVOKED,
    CandidateRegistryIntegrityError,
    DevCallBudgetLedger,
    DevLiveAuthorizationArtifact,
    DevLiveAuthorizationError,
    DevLiveStageAFreezeReceipt,
    DuplicateDevCellAttemptError,
    ImmutableCellExecutionError,
    LiveExecutionCapability,
    LiveExecutionNotAuthorizedError,
    PlanBeforeLiveProtocolError,
    PromptFreezeFirewallError,
    SecretLeakageViolationError,
    StochasticityGateViolationError,
    assert_no_secrets_in_payload,
    run_cli as run_generic_runner_cli,
)
from app.evaluation.dev_selection_harness import (  # noqa: E402
    EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
    EXPECTED_SEMANTIC_SCHEMA_SHA256,
    FORBIDDEN_FINAL100_BUNDLE_SHA256,
    FORBIDDEN_P11_MANIFEST_SHA256,
    SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS,
    CodeCommitProvenanceError,
    DevExecutionPlan,
    Final100FirewallViolationError,
    ScientificCodeBundleIntegrityError,
    assert_not_final100_path,
    assert_not_final100_scenario_id,
    build_default_infrastructure_prompt_registry,
    canonical_json_bytes,
    compute_scientific_code_bundle_sha256,
    load_and_verify_candidate_registry,
    load_and_verify_frozen_dev_bundle,
    normalize_lf_bytes,
    sha256_bytes,
)
import run_w06_dev_select_live_v1 as launcher  # noqa: E402

EXPECTED_LAUNCHER_LF_SHA256 = (
    "cd36b8ecad24059edb597c0039bd6e760a37ee8b4f36f49077801c65e7ddc7bf"
)
EXPECTED_PREFLIGHT_REQUEST_SET_SHA256 = (
    "3ef997b8833399095b9bf5953ae200d45dd85acb7b253c5b6975adf1b01667e2"
)
EXPECTED_PREFLIGHT_ARTIFACT_PATH_SET_SHA256 = (
    "2a058ebd180cf3fe557549f5d2d3eff66d72f5320155b0e73bbb6b31f412d544"
)

SYNTHETIC_NON_SECRET_ENV: dict[str, str] = {
    "GEMINI_API_KEY": "SYNTHETIC_TEST_PRESENT_TOKEN_1",
    "OPENAI_API_KEY": "SYNTHETIC_TEST_PRESENT_TOKEN_2",
    "ANTHROPIC_API_KEY": "SYNTHETIC_TEST_PRESENT_TOKEN_3",
}


def _effective_env_override() -> dict[str, str] | None:
    """Use real local env/.env when all 3 keys are present locally; use synthetic non-secret tokens in keyless CI."""
    local_status = launcher.check_key_presence_status_only(REPO_ROOT)
    if all(v == "PRESENT" for v in local_status.values()):
        return None
    return dict(SYNTHETIC_NON_SECRET_ENV)


def _effective_versions_override() -> dict[str, str] | None:
    """Use real local SDK versions when exact; use pinned version map in CI if runner patch version differs."""
    local_sdk = launcher.check_runtime_sdk_versions()
    if not local_sdk["environment_version_drift"]:
        return None
    return dict(launcher.EXPECTED_RUNTIME_SDK_VERSIONS)


@pytest.fixture(autouse=True)
def _enforce_offline_network_kill_switch():
    """Ensure every test in this module runs under the strict offline network kill switch (Section 28)."""
    with launcher.NetworkKillSwitchGuard():
        yield


@pytest.fixture(scope="module")
def verified_authorities() -> dict[str, Any]:
    """Verify frozen launcher authorities once at module scope."""
    return launcher.verify_frozen_launcher_authorities(REPO_ROOT)


@pytest.fixture(scope="module")
def preflight_out() -> dict[str, Any]:
    """Execute `--preflight` once at module scope and return the full output dictionary."""
    return launcher.run_launcher_cli(
        ["--preflight"],
        repo_root=REPO_ROOT,
        env_override=_effective_env_override(),
        versions_override=_effective_versions_override(),
    )


# ==============================================================================
# DSL-01 .. DSL-40 (SECTION 26)
# ==============================================================================


def test_dsl_01_source_develop_provenance(verified_authorities: dict[str, Any]) -> None:
    """DSL-01: Verify base develop SHA 681510af0e9232bae318562cf115e2ff4ce05968 provenance and shallow fallback rejection."""
    prov = verified_authorities["source_develop_provenance"]
    assert prov["base_develop_sha"] == "681510af0e9232bae318562cf115e2ff4ce05968"
    assert prov["verified"] is True
    assert prov["is_ancestor_of_head"] is True

    with pytest.raises(PlanBeforeLiveProtocolError, match="INVALID_BASE_DEVELOP_SHA"):
        launcher.verify_source_develop_provenance(
            REPO_ROOT, expected_source_sha="0" * 40
        )

    def _fake_non_ancestor(args: list[str]) -> subprocess.CompletedProcess[str]:
        if "cat-file" in args:
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        if "--is-ancestor" in args:
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="")
        return subprocess.CompletedProcess(args, 0, stdout="false\n", stderr="")

    with pytest.raises(
        PlanBeforeLiveProtocolError, match="SOURCE_DEVELOP_NOT_ANCESTOR_OF_HEAD"
    ):
        launcher.verify_source_develop_provenance(
            REPO_ROOT, git_runner=_fake_non_ancestor
        )


def test_dsl_02_launcher_file_exists_and_outside_scientific_bundle() -> None:
    """DSL-02: Verify launcher script exists, has exact LF SHA256, and is outside SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS."""
    launcher_path = REPO_ROOT / launcher.LAUNCHER_REL_PATH
    assert launcher_path.is_file()
    assert launcher.LAUNCHER_REL_PATH not in SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS
    assert len(SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS) == 14
    lf_sha = sha256_bytes(normalize_lf_bytes(launcher_path.read_bytes()))
    assert lf_sha == EXPECTED_LAUNCHER_LF_SHA256


def test_dsl_03_scientific_code_bundle_unchanged(
    verified_authorities: dict[str, Any],
) -> None:
    """DSL-03: Verify SCIENTIFIC_CODE_BUNDLE_SHA256 == 0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3."""
    bundle_sha = compute_scientific_code_bundle_sha256(repo_root=REPO_ROOT)
    assert (
        bundle_sha
        == "0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3"
    )
    assert verified_authorities["scientific_code_bundle_sha256"] == bundle_sha


def test_dsl_04_frozen_execution_plan_sha256_and_180_cells(
    verified_authorities: dict[str, Any],
) -> None:
    """DSL-04: Verify frozen DEV_SELECT plan file and internal SHA256 and 180-cell structure."""
    plan: DevExecutionPlan = verified_authorities["execution_plan"]
    assert (
        verified_authorities["execution_plan_file_sha256"]
        == "c519baf7cd2557b5e1dd2699a5ceaec592af015d7bc6dcc83abf63892a8a329a"
    )
    assert (
        plan.plan_sha256
        == "de04255989a9e3bd8c2e39c766432487dce4ccd0612d5dba73b3476cbc9d0c6d"
    )
    assert (
        verified_authorities["plan_freeze_receipt_file_sha256"]
        == "5f32782f6359f409c7dd68f08699218cd577cb48bcb517f14c15939f896b9549"
    )
    assert plan.phase == "DEV_SELECT"
    assert plan.fixture_count == 60
    assert plan.expected_total_cells == 180
    assert len(plan.cells) == 180
    assert len({c.run_id for c in plan.cells}) == 180


def test_dsl_05_locked_p1_prompt_authority(
    verified_authorities: dict[str, Any],
    preflight_out: dict[str, Any],
) -> None:
    """DSL-05: Verify P1 prompt lock, semantic/system/user template SHA256s, and prompt-selection artifact binding."""
    assert preflight_out["selected_prompt_id"] == "P1"
    assert preflight_out["frozen_plan_prompt_ids"] == ["P1"]
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
    assert (
        preflight_out["prompt_selection_artifact_file_sha256"]
        == "e1e79801117e59d3c8c703e024eacbad12d5336134c6597c333886c434a446b8"
    )
    assert (
        verified_authorities["prompt_freeze_file_sha256"]
        == "2f345363f580ea882b2e5b3562c587ef5309bc7f994440257a54d18994ab6956"
    )


def test_dsl_06_p2_and_p0_rejected_in_dev_select(
    verified_authorities: dict[str, Any],
) -> None:
    """DSL-06: Verify P2 and P0 are absent from all 180 DEV-SELECT cells and rejected fail-closed if injected."""
    plan: DevExecutionPlan = verified_authorities["execution_plan"]
    assert all(c.prompt_id == "P1" for c in plan.cells)
    assert all(c.prompt_id not in ("P0", "P2") for c in plan.cells)


def test_dsl_07_candidates_c1_c2_c3_and_models_locked(
    verified_authorities: dict[str, Any],
    preflight_out: dict[str, Any],
) -> None:
    """DSL-07: Verify candidates C1/C2/C3, requested model IDs, and registry hashes."""
    assert preflight_out["frozen_candidate_ids"] == ["C1", "C2", "C3"]
    assert preflight_out["requested_model_by_candidate"] == {
        "C1": "gemini-3.8-flash",
        "C2": "gpt-6.1-sol",
        "C3": "claude-sonnet-5-5",
    }
    assert (
        verified_authorities["candidate_registry_sha256"]
        == "4dd29164afdf7f364978420f41ab88ef07ec396062188169fcb859a9ef01e058"
    )
    assert (
        verified_authorities["provider_config_registry_sha256"]
        == "3dc05d29acc2f647cba58303865bd7406b8c1d9f7ccbe0f120e87ad471190938"
    )


def test_dsl_08_authorization_artifact_verified(
    verified_authorities: dict[str, Any],
    preflight_out: dict[str, Any],
) -> None:
    """DSL-08: Verify Project Owner live authorization artifact file and internal SHA256 and 180-call cap."""
    auth: DevLiveAuthorizationArtifact = verified_authorities["authorization"]
    assert auth.authorization_id == "W06-DEV-SELECT-LIVE-AUTHORIZATION-01-V1"
    assert auth.authorization_status == "AUTHORIZED"
    assert auth.allowed_phase == "DEV_SELECT"
    assert auth.allowed_candidate_ids == ["C1", "C2", "C3"]
    assert auth.maximum_live_generation_calls == 180
    assert (
        verified_authorities["authorization_file_sha256"]
        == "247c0f201d8b900a1e0356d874891ba6e2884138b1ddd8500dfedb663f04f5f7"
    )
    assert (
        auth.authorization_artifact_sha256
        == "31cebcf5aafa7a575d4bf1327fc9d454a2817c2acbbdb2c087d8c1210e8ec504"
    )
    assert (
        verified_authorities["authorization_receipt_file_sha256"]
        == "cb2dc986d9e03502f8e351d569e14d55147346fee64102a5f4cbedc9be895f39"
    )
    assert (
        preflight_out["project_owner_authorization_text_sha256"]
        == "6c32d37fcc557916b89ef0c1c87790bf76465e1352841a38655d5cf9676dbad7"
    )
    assert preflight_out["authorization_verified"] is True


def test_dsl_09_committed_stage_a_receipt_verified(
    verified_authorities: dict[str, Any],
    preflight_out: dict[str, Any],
) -> None:
    """DSL-09: Verify committed Stage-A receipt file/internal SHA256, commit SHA, and 180 assigned cells."""
    stage_a: DevLiveStageAFreezeReceipt = verified_authorities["stage_a_receipt"]
    assert (
        verified_authorities["stage_a_file_sha256"]
        == "dd31582860e899b865d3dacd52bd1f92786ee6cf31d851e68e9050d93c451a26"
    )
    assert (
        stage_a.stage_a_receipt_sha256
        == "1b933067516b7142b4250870a18e6deef216c6854b1c9790d01830d196dde014"
    )
    assert (
        verified_authorities["task_audit_receipt_file_sha256"]
        == "73eb38335f6fa0d21f9f38f0e15f9dc2c6497c46519a784b0d4e3df7da6a64c5"
    )
    assert stage_a.phase == "DEV_SELECT"
    assert stage_a.stage_a_status == "FROZEN_BEFORE_LIVE"
    assert (
        stage_a.stage_a_commit_sha
        == "e69b7d70c3908d2b888b7c5d7e6c4e1d49fac863"
    )
    assert (
        stage_a.code_basis_commit_sha
        == "c0adf74ceda9ffaf8b4ec42d299932e33f448e6a"
    )
    assert len(stage_a.assigned_cell_run_ids) == 180
    assert (
        stage_a.assigned_cells_sha256
        == "de04255989a9e3bd8c2e39c766432487dce4ccd0612d5dba73b3476cbc9d0c6d"
    )
    assert preflight_out["stage_a_verified"] is True
    assert preflight_out["stage_a_committed_verified"] is True


def test_dsl_10_stage_a_commit_attestation_fails_on_uncommitted_or_dirty(
    tmp_path: Path,
    verified_authorities: dict[str, Any],
) -> None:
    """DSL-10: Verify `verify_committed_stage_a_for_launcher` fails closed when Stage-A receipt is uncommitted or dirty."""
    untracked_stage_a = tmp_path / "w06_dev_select_stage_a_freeze_receipt_v1.json"
    untracked_stage_a.write_bytes(
        verified_authorities["stage_a_receipt_path"].read_bytes()
    )
    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="STAGE_A_ARTIFACT_OUTSIDE_REPO|STAGE_A_ARTIFACT_UNCOMMITTED",
    ):
        launcher.verify_committed_stage_a_for_launcher(
            untracked_stage_a,
            execution_plan=verified_authorities["execution_plan"],
            prompt_freeze=verified_authorities["prompt_freeze"],
            authorization=verified_authorities["authorization"],
            execution_plan_path=verified_authorities["execution_plan_path"],
            prompt_freeze_path=verified_authorities["prompt_freeze_path"],
            authorization_path=verified_authorities["authorization_path"],
            candidate_registry=verified_authorities["candidate_registry"],
            repo_root=REPO_ROOT,
        )


def test_dsl_11_preflight_succeeds_offline_with_zero_calls(
    preflight_out: dict[str, Any],
) -> None:
    """DSL-11: Verify `--preflight` succeeds offline with 0 provider calls and TRANSPORT_NOT_INVOKED."""
    assert preflight_out["mode"] == "dry_run"
    assert preflight_out["launcher_mode"] == "preflight"
    assert preflight_out["dry_run"] is True
    assert preflight_out["phase"] == "DEV_SELECT"
    assert preflight_out["planned_call_count"] == 180
    assert preflight_out["expected_total_cells"] == 180
    assert preflight_out["transport_status"] == TRANSPORT_STATUS_NOT_INVOKED
    assert preflight_out["live_provider_calls"] == 0
    assert preflight_out["provider_cost_usd"] == 0
    assert preflight_out["live_command_executed"] is False
    assert preflight_out["live_execution_capability_minted"] is False
    assert preflight_out["production_provider_transport_constructed"] is False
    assert preflight_out["transport_starting_count"] == 0


def test_dsl_12_preflight_180_serialized_request_hashes(
    preflight_out: dict[str, Any],
) -> None:
    """DSL-12: Verify `--preflight` computes 180 serialized request hashes with exact set SHA256."""
    assert preflight_out["preflight_request_hash_count"] == 180
    assert (
        preflight_out["preflight_request_set_sha256"]
        == EXPECTED_PREFLIGHT_REQUEST_SET_SHA256
    )
    req_map = preflight_out["serialized_request_sha256_by_run_id"]
    assert len(req_map) == 180
    assert all(isinstance(v, str) and len(v) == 64 for v in req_map.values())


def test_dsl_13_preflight_180_artifact_path_maps(
    preflight_out: dict[str, Any],
) -> None:
    """DSL-13: Verify `--preflight` computes 180 cell artifact path maps (10 files each = 1800 paths) with exact set SHA256."""
    assert preflight_out["preflight_artifact_path_count"] == 180
    assert (
        preflight_out["preflight_artifact_path_set_sha256"]
        == EXPECTED_PREFLIGHT_ARTIFACT_PATH_SET_SHA256
    )
    path_map = preflight_out["planned_artifact_paths_by_run_id"]
    assert len(path_map) == 180
    all_files: set[str] = set()
    for run_id, cell_files in path_map.items():
        assert len(cell_files) == 10
        expected_prefix = f"data/evaluation/w06/live_dev_select_primary_v1/{run_id}/"
        for fname, rel_path in cell_files.items():
            assert rel_path == f"{expected_prefix}{fname}"
            assert "final100" not in rel_path.lower()
            all_files.add(rel_path)
    assert len(all_files) == 1800


def test_dsl_14_live_output_root_non_existent_and_not_created_by_preflight(
    preflight_out: dict[str, Any],
) -> None:
    """DSL-14: Verify `data/evaluation/w06/live_dev_select_primary_v1` does not exist before or after `--preflight`."""
    output_root = REPO_ROOT / "data/evaluation/w06/live_dev_select_primary_v1"
    assert not output_root.exists()
    assert preflight_out["live_output_root"] == "data/evaluation/w06/live_dev_select_primary_v1"
    assert preflight_out["live_output_root_exists"] is False


def test_dsl_15_call_budget_180_and_zero_retry(
    verified_authorities: dict[str, Any],
    preflight_out: dict[str, Any],
) -> None:
    """DSL-15: Verify call budget ledger enforces max 180 calls, 0 reserved/consumed in preflight, and 0 retry."""
    assert preflight_out["call_budget_max"] == 180
    assert preflight_out["call_budget_reserved"] == 0
    assert preflight_out["call_budget_consumed"] == 0
    assert preflight_out["retry_calls"] == 0
    assert preflight_out["attempts_per_cell"] == 1

    plan: DevExecutionPlan = verified_authorities["execution_plan"]
    ledger = DevCallBudgetLedger.from_execution_plan(
        plan, maximum_live_generation_calls=180
    )
    for idx, cell in enumerate(plan.cells, start=1):
        res_num = ledger.reserve_call(cell)
        assert res_num == idx
        ledger.consume_reserved_call(cell.run_id, transport_outcome="SUCCESS")
    assert ledger.reserved_calls == 180
    assert ledger.consumed_calls == 180

    with pytest.raises(DuplicateDevCellAttemptError):
        ledger.reserve_call(plan.cells[0])


def test_dsl_16_secret_free_api_key_presence_check(
    preflight_out: dict[str, Any],
) -> None:
    """DSL-16: Verify API key presence check reports ONLY PRESENT/MISSING and never leaks secret material."""
    assert preflight_out["gemini_key_presence"] == "PRESENT"
    assert preflight_out["openai_key_presence"] == "PRESENT"
    assert preflight_out["anthropic_key_presence"] == "PRESENT"
    assert_no_secrets_in_payload(preflight_out, context="DSL_16_PREFLIGHT")

    status_missing = launcher.check_key_presence_status_only(
        REPO_ROOT,
        env_override={"GEMINI_API_KEY": "ok", "OPENAI_API_KEY": "", "ANTHROPIC_API_KEY": "   "},
        include_dotenv_files=False,
    )
    assert status_missing == {
        "GEMINI_API_KEY": "PRESENT",
        "OPENAI_API_KEY": "MISSING",
        "ANTHROPIC_API_KEY": "MISSING",
    }

    with pytest.raises(SecretLeakageViolationError):
        assert_no_secrets_in_payload(
            {"gemini_api_key": "PRESENT"}, context="DSL_16_FORBIDDEN_KEY_NAME"
        )


def test_dsl_17_runtime_sdk_version_check(
    preflight_out: dict[str, Any],
) -> None:
    """DSL-17: Verify runtime Python & SDK version check against frozen expectations."""
    assert preflight_out["runtime_environment"] == launcher.EXPECTED_RUNTIME_SDK_VERSIONS
    assert preflight_out["runtime_sdk_version_evidence"]["environment_version_drift"] is False
    assert preflight_out["runtime_sdk_version_evidence"]["pre_flight_ready"] is True
    assert preflight_out["live_readiness"] == "READY"
    assert preflight_out["pre_flight_ready"] is True

    drifted = launcher.check_runtime_sdk_versions(
        versions_override={
            **launcher.EXPECTED_RUNTIME_SDK_VERSIONS,
            "OPENAI_VERSION": "9.99.9",
        }
    )
    assert drifted["environment_version_drift"] is True
    assert drifted["drifted_components"] == ["OPENAI_VERSION"]
    assert drifted["runtime_sdk_status"] == "ENVIRONMENT_VERSION_DRIFT"
    assert drifted["pre_flight_ready"] is False


def test_dsl_18_two_flag_live_confirmation_gate() -> None:
    """DSL-18: Verify two-flag live execution gate rejects missing flags and mode conflicts."""
    with pytest.raises(LiveExecutionNotAuthorizedError, match="NO_MODE_SPECIFIED"):
        launcher.run_launcher_cli([])

    with pytest.raises(
        LiveExecutionNotAuthorizedError, match="LIVE_CONFIRMATION_FLAG_MISSING"
    ):
        launcher.run_launcher_cli(["--execute-live"])

    with pytest.raises(
        LiveExecutionNotAuthorizedError, match="LIVE_EXECUTION_FLAG_MISSING"
    ):
        launcher.run_launcher_cli(["--confirm-frozen-180-cells"])

    with pytest.raises(PlanBeforeLiveProtocolError, match="MODE_CONFLICT_FORBIDDEN"):
        launcher.run_launcher_cli(["--preflight", "--execute-live"])

    with pytest.raises(PlanBeforeLiveProtocolError, match="MODE_CONFLICT_FORBIDDEN"):
        launcher.run_launcher_cli(
            ["--preflight", "--execute-live", "--confirm-frozen-180-cells"]
        )


def test_dsl_19_preflight_determinism_across_repeated_runs(
    preflight_out: dict[str, Any],
) -> None:
    """DSL-19: Verify running `--preflight` a second time produces identical request and artifact path set hashes."""
    second_out = launcher.run_launcher_cli(
        ["--preflight"],
        repo_root=REPO_ROOT,
        env_override=_effective_env_override(),
        versions_override=_effective_versions_override(),
    )
    assert (
        second_out["preflight_request_set_sha256"]
        == preflight_out["preflight_request_set_sha256"]
        == EXPECTED_PREFLIGHT_REQUEST_SET_SHA256
    )
    assert (
        second_out["preflight_artifact_path_set_sha256"]
        == preflight_out["preflight_artifact_path_set_sha256"]
        == EXPECTED_PREFLIGHT_ARTIFACT_PATH_SET_SHA256
    )


def test_dsl_20_live_execution_code_path_delegation_order(
    monkeypatch: pytest.MonkeyPatch,
    verified_authorities: dict[str, Any],
) -> None:
    """DSL-20: Verify `run_live_execution` follows exact Section 19 step order using offline spy stubs (0 network calls)."""
    call_order: list[str] = []

    orig_verify = launcher.verify_frozen_launcher_authorities

    def _spy_verify(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
        call_order.append("1_verify_frozen_launcher_authorities")
        return verified_authorities

    def _spy_issue_capability(**kwargs: Any) -> Any:
        call_order.append("2_issue_live_execution_capability")
        assert kwargs["execute_live"] is True
        assert kwargs["execution_plan_path"] == verified_authorities["execution_plan_path"]
        assert kwargs["prompt_freeze_path"] == verified_authorities["prompt_freeze_path"]
        assert kwargs["authorization_path"] == verified_authorities["authorization_path"]
        assert (
            kwargs["stage_a_freeze_receipt_path"]
            == verified_authorities["stage_a_receipt_path"]
        )
        cap = LiveExecutionCapability(
            _mint_guard=dlr_mod._CAPABILITY_MINT_GUARD,
            phase="DEV_SELECT",
            manifest_execution_mode="LIVE_DEV_SELECT",
            execution_plan_sha256=verified_authorities["execution_plan"].plan_sha256,
            prompt_freeze_sha256=verified_authorities["prompt_freeze_file_sha256"],
            authorization_id=verified_authorities["authorization"].authorization_id,
            authorization_artifact_sha256=verified_authorities[
                "authorization"
            ].authorization_artifact_sha256,
            stage_a_receipt_sha256=verified_authorities[
                "stage_a_receipt"
            ].stage_a_receipt_sha256,
            stage_a_commit_sha=verified_authorities[
                "stage_a_receipt"
            ].stage_a_commit_sha,
            code_basis_commit_sha=verified_authorities[
                "execution_plan"
            ].code_basis_commit_sha,
            runtime_head_sha="681510af0e9232bae318562cf115e2ff4ce05968",
            scientific_code_bundle_sha256=verified_authorities[
                "scientific_code_bundle_sha256"
            ],
            provider_config_registry_sha256=verified_authorities[
                "provider_config_registry_sha256"
            ],
            allowed_candidate_ids=("C1", "C2", "C3"),
            maximum_live_generation_calls=180,
            execution_plan_path=verified_authorities["execution_plan_path"],
            prompt_freeze_path=verified_authorities["prompt_freeze_path"],
            authorization_path=verified_authorities["authorization_path"],
            stage_a_freeze_receipt_path=verified_authorities["stage_a_receipt_path"],
            repo_root=REPO_ROOT,
        )
        return (
            cap,
            verified_authorities["execution_plan"],
            verified_authorities["prompt_freeze"],
            verified_authorities["authorization"],
            verified_authorities["stage_a_receipt"],
        )

    def _spy_reattest(**kwargs: Any) -> Any:
        call_order.append("3_reattest_stage_a_at_live_action_boundary")
        assert isinstance(kwargs["live_capability"], LiveExecutionCapability)
        return None

    sentinel_transport = object()

    def _spy_create_transport(**kwargs: Any) -> Any:
        call_order.append("4_create_live_provider_transport_factory")
        assert kwargs["execute_live"] is True
        assert isinstance(kwargs["live_capability"], LiveExecutionCapability)
        return sentinel_transport

    def _spy_execute_batch(**kwargs: Any) -> Any:
        call_order.append("5_execute_live_dev_batch")
        assert kwargs["transport"] is sentinel_transport
        assert kwargs["execution_mode"] == RUNNER_EXECUTION_MODE_LIVE_EXECUTION
        assert kwargs["batch_root_dir"] == verified_authorities["output_root"]
        ledger = DevCallBudgetLedger.from_execution_plan(
            verified_authorities["execution_plan"],
            maximum_live_generation_calls=180,
        )
        return ([object() for _ in range(180)], ledger)

    monkeypatch.setattr(launcher, "verify_frozen_launcher_authorities", _spy_verify)
    monkeypatch.setattr(
        launcher, "issue_live_execution_capability", _spy_issue_capability
    )
    monkeypatch.setattr(
        launcher, "reattest_stage_a_at_live_action_boundary", _spy_reattest
    )
    monkeypatch.setattr(
        launcher, "create_live_provider_transport_factory", _spy_create_transport
    )
    monkeypatch.setattr(launcher, "execute_live_dev_batch", _spy_execute_batch)

    out = launcher.run_launcher_cli(
        ["--execute-live", "--confirm-frozen-180-cells"],
        repo_root=REPO_ROOT,
        env_override=_effective_env_override(),
        versions_override=_effective_versions_override(),
    )
    assert call_order == [
        "1_verify_frozen_launcher_authorities",
        "2_issue_live_execution_capability",
        "3_reattest_stage_a_at_live_action_boundary",
        "4_create_live_provider_transport_factory",
        "5_execute_live_dev_batch",
    ]
    assert out["mode"] == "execute_live"
    assert out["phase"] == "DEV_SELECT"
    assert out["selected_prompt_id"] == "P1"
    assert out["executed_cells"] == 180
    assert not verified_authorities["output_root"].exists()
    assert orig_verify is not None


def test_dsl_21_adversarial_wrong_plan_sha_and_wrong_plan_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DSL-21: Reject wrong execution plan SHA256, tampered plan file hash, or missing plan file."""
    monkeypatch.setattr(launcher, "EXPECTED_EXECUTION_PLAN_SHA256", "0" * 64)
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="EXECUTION_PLAN_SHA256_MISMATCH"
    ):
        launcher.verify_frozen_launcher_authorities(REPO_ROOT)

    monkeypatch.undo()
    monkeypatch.setattr(launcher, "EXPECTED_EXECUTION_PLAN_FILE_SHA256", "1" * 64)
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="EXECUTION_PLAN_FILE_SHA256_MISMATCH"
    ):
        launcher.verify_frozen_launcher_authorities(REPO_ROOT)

    monkeypatch.undo()
    monkeypatch.setattr(
        launcher,
        "EXECUTION_PLAN_REL_PATH",
        "data/evaluation/w06/non_existent_plan.json",
    )
    with pytest.raises(PlanBeforeLiveProtocolError, match="EXECUTION_PLAN_MISSING"):
        launcher.verify_frozen_launcher_authorities(REPO_ROOT)


def test_dsl_22_adversarial_wrong_p1_semantic_sha_and_p2_substitution(
    monkeypatch: pytest.MonkeyPatch,
    verified_authorities: dict[str, Any],
    preflight_out: dict[str, Any],
) -> None:
    """DSL-22: Reject wrong P1 semantic SHA256 or P2 prompt substitution in any cell."""
    monkeypatch.setattr(launcher, "EXPECTED_P1_SEMANTIC_SHA256", "f" * 64)
    with pytest.raises(
        PromptFreezeFirewallError, match="LOCKED_P1_PROMPT_AUTHORITY_MISMATCH"
    ):
        launcher.load_and_verify_frozen_prompt_authorities(REPO_ROOT)

    monkeypatch.undo()
    plan_copy = copy.deepcopy(verified_authorities["execution_plan"])
    object.__setattr__(plan_copy.cells[0], "prompt_id", "P2")
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="PREFLIGHT_CELL_METADATA_MISMATCH"
    ):
        launcher._validate_and_hash_preflight_requests_and_paths(
            plan_model=plan_copy,
            dry_run_out=preflight_out,
            dev_bundle=verified_authorities["dev_bundle"],
            cand_reg=verified_authorities["candidate_registry"],
            p1_spec=verified_authorities["p1_spec"],
            repo_root=REPO_ROOT,
        )


def test_dsl_23_adversarial_candidate_missing_or_c4_injected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DSL-23: Reject missing candidate (C1/C2 only) or unauthorized candidate C4."""
    monkeypatch.setattr(launcher, "FROZEN_CANDIDATE_IDS", ("C1", "C2"))
    with pytest.raises(
        (PlanBeforeLiveProtocolError, CandidateRegistryIntegrityError)
    ):
        launcher.verify_frozen_launcher_authorities(REPO_ROOT)

    monkeypatch.setattr(launcher, "FROZEN_CANDIDATE_IDS", ("C1", "C2", "C3", "C4"))
    with pytest.raises(
        (PlanBeforeLiveProtocolError, CandidateRegistryIntegrityError)
    ):
        launcher.verify_frozen_launcher_authorities(REPO_ROOT)


def test_dsl_24_adversarial_wrong_authorization_and_wrong_stage_a(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DSL-24: Reject wrong authorization SHA256 or wrong Stage-A receipt SHA256."""
    monkeypatch.setattr(launcher, "EXPECTED_AUTHORIZATION_FILE_SHA256", "a" * 64)
    with pytest.raises(
        DevLiveAuthorizationError, match="AUTHORIZATION_FILE_SHA256_MISMATCH"
    ):
        launcher.verify_frozen_launcher_authorities(REPO_ROOT)

    monkeypatch.undo()
    monkeypatch.setattr(launcher, "EXPECTED_STAGE_A_FILE_SHA256", "b" * 64)
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="STAGE_A_FILE_SHA256_MISMATCH"
    ):
        launcher.verify_frozen_launcher_authorities(REPO_ROOT)


def test_dsl_25_adversarial_dirty_stage_a_and_uncommitted_stage_a_in_git(
    verified_authorities: dict[str, Any],
) -> None:
    """DSL-25: Reject dirty or uncommitted Stage-A files in git commit verification."""
    untracked_in_repo = (
        REPO_ROOT
        / "data"
        / "evaluation"
        / "w06"
        / "_tmp_untracked_stage_a_dsl25.json"
    )
    try:
        untracked_in_repo.write_bytes(
            verified_authorities["stage_a_receipt_path"].read_bytes()
        )
        with pytest.raises(
            PlanBeforeLiveProtocolError, match="STAGE_A_ARTIFACT_UNCOMMITTED"
        ):
            launcher.verify_committed_stage_a_for_launcher(
                untracked_in_repo,
                execution_plan=verified_authorities["execution_plan"],
                prompt_freeze=verified_authorities["prompt_freeze"],
                authorization=verified_authorities["authorization"],
                execution_plan_path=verified_authorities["execution_plan_path"],
                prompt_freeze_path=verified_authorities["prompt_freeze_path"],
                authorization_path=verified_authorities["authorization_path"],
                candidate_registry=verified_authorities["candidate_registry"],
                repo_root=REPO_ROOT,
            )
    finally:
        if untracked_in_repo.exists():
            untracked_in_repo.unlink()


def test_dsl_26_adversarial_scientific_bundle_and_provider_registry_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DSL-26: Reject scientific code bundle drift or provider config registry SHA256 drift."""
    monkeypatch.setattr(
        launcher, "EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256", "c" * 64
    )
    with pytest.raises(
        ScientificCodeBundleIntegrityError,
        match="SCIENTIFIC_CODE_BUNDLE_SHA256_MISMATCH",
    ):
        launcher.verify_frozen_launcher_authorities(REPO_ROOT)

    monkeypatch.undo()
    monkeypatch.setattr(
        launcher, "EXPECTED_PROVIDER_CONFIG_REGISTRY_SHA256", "d" * 64
    )
    with pytest.raises(
        CandidateRegistryIntegrityError,
        match="PROVIDER_CONFIG_REGISTRY_SHA256_MISMATCH",
    ):
        launcher.verify_frozen_launcher_authorities(REPO_ROOT)


def test_dsl_27_adversarial_181_calls_and_179_cells(
    monkeypatch: pytest.MonkeyPatch,
    verified_authorities: dict[str, Any],
) -> None:
    """DSL-27: Reject 181 calls budget mismatch and 179 cells count mismatch."""
    plan: DevExecutionPlan = verified_authorities["execution_plan"]
    with pytest.raises(DevLiveAuthorizationError, match="LEDGER_BUDGET_MISMATCH"):
        DevCallBudgetLedger.from_execution_plan(
            plan, maximum_live_generation_calls=181
        )

    monkeypatch.setattr(launcher, "FROZEN_CELL_COUNT", 179)
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="EXECUTION_PLAN_SCOPE_LOCK_MISMATCH"
    ):
        launcher.verify_frozen_launcher_authorities(REPO_ROOT)


def test_dsl_28_adversarial_retry_1_and_attempt_2(
    verified_authorities: dict[str, Any],
    preflight_out: dict[str, Any],
) -> None:
    """DSL-28: Reject retry=1 or attempt_number=2 in cell execution manifest or ledger."""
    plan: DevExecutionPlan = verified_authorities["execution_plan"]
    ledger = DevCallBudgetLedger.from_execution_plan(
        plan, maximum_live_generation_calls=180
    )
    bad_attempt_cell = plan.cells[0].model_copy(update={"attempt_number": 2})
    with pytest.raises(ImmutableCellExecutionError, match="RETRY_FORBIDDEN"):
        ledger.reserve_call(bad_attempt_cell)

    plan_bad_retry = copy.deepcopy(plan)
    object.__setattr__(plan_bad_retry.cells[0], "retry", 1)
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="PREFLIGHT_CELL_METADATA_MISMATCH"
    ):
        launcher._validate_and_hash_preflight_requests_and_paths(
            plan_model=plan_bad_retry,
            dry_run_out=preflight_out,
            dev_bundle=verified_authorities["dev_bundle"],
            cand_reg=verified_authorities["candidate_registry"],
            p1_spec=verified_authorities["p1_spec"],
            repo_root=REPO_ROOT,
        )


def test_dsl_29_adversarial_duplicate_run_id_and_duplicate_output_path(
    verified_authorities: dict[str, Any],
    preflight_out: dict[str, Any],
) -> None:
    """DSL-29: Reject duplicate run_id or duplicate artifact output path in preflight validation."""
    plan_dup = copy.deepcopy(verified_authorities["execution_plan"])
    plan_dup.cells[1] = plan_dup.cells[0]

    dup_paths = copy.deepcopy(preflight_out["planned_artifact_paths_by_run_id"])
    first_run_id = verified_authorities["execution_plan"].cells[0].run_id
    second_run_id = verified_authorities["execution_plan"].cells[1].run_id
    dup_paths[second_run_id] = dict(dup_paths[first_run_id])

    fake_dry_run = {
        "serialized_request_sha256_by_run_id": preflight_out[
            "serialized_request_sha256_by_run_id"
        ],
        "planned_artifact_paths_by_run_id": dup_paths,
    }
    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="PREFLIGHT_ARTIFACT_PATH_MISMATCH|DUPLICATE_PREFLIGHT",
    ):
        launcher._validate_and_hash_preflight_requests_and_paths(
            plan_model=verified_authorities["execution_plan"],
            dry_run_out=fake_dry_run,
            dev_bundle=verified_authorities["dev_bundle"],
            cand_reg=verified_authorities["candidate_registry"],
            p1_spec=verified_authorities["p1_spec"],
            repo_root=REPO_ROOT,
        )


def test_dsl_30_adversarial_existing_live_output_root_rejected(
    tmp_path: Path,
) -> None:
    """DSL-30: Reject existing live output root (`LIVE_OUTPUT_ROOT_ALREADY_EXISTS`)."""
    existing_root = tmp_path / launcher.FROZEN_LIVE_OUTPUT_ROOT_REL_PATH
    existing_root.mkdir(parents=True, exist_ok=True)
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="LIVE_OUTPUT_ROOT_ALREADY_EXISTS"
    ):
        launcher.verify_output_root_not_existing(tmp_path)


def test_dsl_31_adversarial_api_key_absent_and_sdk_drift_fail_closed() -> None:
    """DSL-31: Reject missing API key (`PREFLIGHT_API_KEY_MISSING`) and runtime SDK drift (`PREFLIGHT_RUNTIME_SDK_DRIFT`)."""
    with pytest.raises(DevLiveAuthorizationError, match="PREFLIGHT_API_KEY_MISSING"):
        launcher.run_preflight(
            REPO_ROOT,
            env_override={
                "GEMINI_API_KEY": "PRESENT_VAL",
                "OPENAI_API_KEY": "",
                "ANTHROPIC_API_KEY": "PRESENT_VAL",
            },
            include_dotenv_files=False,
            versions_override=_effective_versions_override(),
        )

    with pytest.raises(
        PlanBeforeLiveProtocolError, match="PREFLIGHT_RUNTIME_SDK_DRIFT"
    ):
        launcher.run_preflight(
            REPO_ROOT,
            env_override=_effective_env_override(),
            versions_override={
                **launcher.EXPECTED_RUNTIME_SDK_VERSIONS,
                "GOOGLE_GENAI_VERSION": "0.0.1",
            },
        )


def test_dsl_32_adversarial_cli_override_and_scope_mutation_flags_rejected() -> None:
    """DSL-32: Reject all CLI scope overrides (--phase, --prompt, --candidates, --retry, --resume, --dev-tune, --stochasticity)."""
    forbidden_flags = [
        ["--preflight", "--phase=DEV_TUNE"],
        ["--preflight", "--prompt=P2"],
        ["--preflight", "--candidates=C1,C2"],
        ["--preflight", "--retry=1"],
        ["--preflight", "--max-retries=2"],
        ["--preflight", "--resume"],
        ["--preflight", "--rerun"],
        ["--preflight", "--best-of=3"],
        ["--preflight", "--skip-stage-a"],
        ["--preflight", "--skip-authorization"],
        ["--preflight", "--ignore-hash"],
        ["--preflight", "--execution-plan=other.json"],
        ["--preflight", "--output-root=other_dir"],
        ["--preflight", "--max-calls=181"],
        ["--preflight", "--confirm-frozen-120-cells"],
        ["--preflight", "--unknown-flag"],
    ]
    for argv in forbidden_flags:
        with pytest.raises(PlanBeforeLiveProtocolError):
            launcher.run_launcher_cli(argv)

    with pytest.raises(
        StochasticityGateViolationError,
        match="STOCHASTICITY_FORBIDDEN_IN_DEV_SELECT_LAUNCHER",
    ):
        launcher.run_launcher_cli(["--preflight", "--stochasticity"])

    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="DEV_TUNE_FORBIDDEN_IN_DEV_SELECT_LAUNCHER",
    ):
        launcher.run_launcher_cli(["--preflight", "--dev-tune"])


def test_dsl_33_adversarial_final100_firewall() -> None:
    """DSL-33: Reject any Final100 CLI flag, path, or scenario ID (`Final100FirewallViolationError`)."""
    for bad_arg in (
        "--final100",
        "--execution-plan=data/evaluation/w06/w06_scenarios_freeze_v1.json",
        "--fixture=W06-SCENARIO-001",
        "w06_p11_assignment_manifest_v1.json",
    ):
        with pytest.raises(Final100FirewallViolationError):
            launcher.run_launcher_cli([bad_arg])

    with pytest.raises(Final100FirewallViolationError):
        assert_not_final100_path(
            REPO_ROOT / "data/evaluation/w06/w06_scenarios_freeze_v1.json"
        )
    with pytest.raises(Final100FirewallViolationError):
        assert_not_final100_scenario_id("W06-SCENARIO-001")

    f100_sha = sha256_bytes(
        normalize_lf_bytes(
            (REPO_ROOT / "data/evaluation/w06/w06_scenarios_freeze_v1.json").read_bytes()
        )
    )
    p11_sha = sha256_bytes(
        normalize_lf_bytes(
            (
                REPO_ROOT / "data/evaluation/w06/w06_p11_assignment_manifest_v1.json"
            ).read_bytes()
        )
    )
    assert f100_sha == FORBIDDEN_FINAL100_BUNDLE_SHA256
    assert p11_sha == FORBIDDEN_P11_MANIFEST_SHA256


def test_dsl_34_adversarial_network_kill_switch_blocks_socket_urllib_httpx_httpx2() -> None:
    """DSL-34: Verify `NetworkKillSwitchGuard` blocks socket, urllib, httpx, and httpx2 sync/async calls (Section 28)."""
    with pytest.raises(launcher.OutboundNetworkBlockedError, match="socket.socket.connect"):
        s = socket.socket()
        try:
            s.connect(("127.0.0.1", 80))
        finally:
            s.close()

    with pytest.raises(
        launcher.OutboundNetworkBlockedError, match="socket.create_connection"
    ):
        socket.create_connection(("127.0.0.1", 80))

    with pytest.raises(
        launcher.OutboundNetworkBlockedError, match="urllib.request.urlopen"
    ):
        urllib.request.urlopen("https://example.com")

    with pytest.raises(launcher.OutboundNetworkBlockedError, match="httpx.Client.send"):
        with httpx.Client() as client:
            client.get("https://example.com")

    with pytest.raises(
        launcher.OutboundNetworkBlockedError, match="httpx.AsyncClient.send"
    ):
        httpx.AsyncClient.send(None, None)  # type: ignore[arg-type]

    with pytest.raises(launcher.OutboundNetworkBlockedError, match="httpx2.Client.send"):
        with httpx2.Client() as client2:
            client2.get("https://example.com")

    with pytest.raises(
        launcher.OutboundNetworkBlockedError, match="httpx2.AsyncClient.send"
    ):
        httpx2.AsyncClient.send(None, None)  # type: ignore[arg-type]


def test_dsl_35_adversarial_no_capability_or_transport_or_filesystem_output_during_preflight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DSL-35: Verify `--preflight` never calls `issue_live_execution_capability`, `create_live_provider_transport_factory`, or creates output dirs."""
    def _forbid_capability(**_kw: Any) -> Any:
        raise AssertionError("issue_live_execution_capability must NEVER be called during --preflight!")

    def _forbid_transport(**_kw: Any) -> Any:
        raise AssertionError("create_live_provider_transport_factory must NEVER be called during --preflight!")

    monkeypatch.setattr(launcher, "issue_live_execution_capability", _forbid_capability)
    monkeypatch.setattr(
        launcher, "create_live_provider_transport_factory", _forbid_transport
    )

    out = launcher.run_launcher_cli(
        ["--preflight"],
        repo_root=REPO_ROOT,
        env_override=_effective_env_override(),
        versions_override=_effective_versions_override(),
    )
    assert out["live_execution_capability_minted"] is False
    assert out["production_provider_transport_constructed"] is False
    assert not (REPO_ROOT / launcher.FROZEN_LIVE_OUTPUT_ROOT_REL_PATH).exists()


def test_dsl_36_generic_runner_cli_firewall_section_24(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DSL-36: Verify `dev_live_runner.py` generic CLI fails closed on missing args, Final100, combined Stage-A + live, and the exact frozen DEV-SELECT `--execute-live` bypass attempt (Section 24)."""
    with pytest.raises(LiveExecutionNotAuthorizedError, match="NO_MODE_SPECIFIED"):
        run_generic_runner_cli([])

    with pytest.raises(Final100FirewallViolationError):
        run_generic_runner_cli(["--dry-run", "--phase=FINAL100"])

    with pytest.raises(PlanBeforeLiveProtocolError, match="PLAN_BEFORE_LIVE_VIOLATION"):
        run_generic_runner_cli(["--create-stage-a", "--execute-live"])

    with pytest.raises(PlanBeforeLiveProtocolError, match="EXECUTION_PLAN_MISSING"):
        run_generic_runner_cli(["--execute-live"])

    temp_batch_root = tmp_path / "generic_cli_bypass_batch_root"
    temp_batch_root.mkdir(parents=True, exist_ok=True)
    assert list(temp_batch_root.iterdir()) == []

    orig_issue_capability = dlr_mod.issue_live_execution_capability
    capability_attempts: list[dict[str, Any]] = []
    minted_capabilities: list[LiveExecutionCapability] = []
    transport_constructed = False
    batch_executed = False

    def _spy_real_issue_capability(*args: Any, **kwargs: Any) -> Any:
        capability_attempts.append({"args": args, "kwargs": dict(kwargs)})
        res = orig_issue_capability(*args, **kwargs)
        minted_capabilities.append(res[0])
        return res

    def _fail_if_transport_constructed(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal transport_constructed
        transport_constructed = True
        pytest.fail(
            "BLOCKER: Generic run_cli unexpectedly reached create_live_provider_transport_factory!"
        )

    def _fail_if_batch_executed(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal batch_executed
        batch_executed = True
        pytest.fail(
            "BLOCKER: Generic run_cli unexpectedly reached execute_live_dev_batch!"
        )

    monkeypatch.setattr(
        dlr_mod, "issue_live_execution_capability", _spy_real_issue_capability
    )
    monkeypatch.setattr(
        dlr_mod,
        "create_live_provider_transport_factory",
        _fail_if_transport_constructed,
    )
    monkeypatch.setattr(
        dlr_mod, "execute_live_dev_batch", _fail_if_batch_executed
    )
    monkeypatch.chdir(REPO_ROOT)

    exact_generic_dev_select_live_argv = [
        "--execute-live",
        "--execution-plan",
        "data/evaluation/w06/w06_dev_select_execution_plan_v1.json",
        "--prompt-freeze",
        "data/evaluation/w06/w06_dev_prompt_candidate_freeze_v1.json",
        "--authorization-artifact",
        "data/evaluation/w06/w06_dev_select_live_authorization_v1.json",
        "--stage-a-freeze-receipt",
        "data/evaluation/w06/w06_dev_select_stage_a_freeze_receipt_v1.json",
        "--phase",
        "DEV_SELECT",
        "--batch-root-dir",
        str(temp_batch_root),
    ]

    with launcher.NetworkKillSwitchGuard():
        # 1. Pure unpatched generic `run_cli` fails closed inside `issue_live_execution_capability`
        #    -> `verify_runner_prompt_freeze_artifact` (at `build_dev_tune_execution_plan`
        #    with `CodeCommitProvenanceError`, or `PromptFreezeFirewallError` if HEAD == code_basis_commit_sha).
        with pytest.raises(
            (PromptFreezeFirewallError, CodeCommitProvenanceError)
        ) as exc_unpatched:
            run_generic_runner_cli(exact_generic_dev_select_live_argv)

        assert isinstance(
            exc_unpatched.value,
            (PromptFreezeFirewallError, CodeCommitProvenanceError),
        )
        assert len(capability_attempts) == 1
        default_infra_reg = build_default_infrastructure_prompt_registry()
        supplied_prompt_reg = capability_attempts[0]["kwargs"]["prompt_registry"]
        assert (
            supplied_prompt_reg.registry_sha256
            == default_infra_reg.registry_sha256
        )
        assert (
            supplied_prompt_reg.registry_sha256
            != "846dc4c14ec2a87537b7b3e07bf492de51dc534d24b21e469094b7e3d34d32b6"
        )
        assert len(minted_capabilities) == 0
        assert transport_constructed is False
        assert batch_executed is False
        assert list(temp_batch_root.iterdir()) == []
        assert not (
            REPO_ROOT / "data/evaluation/w06/live_dev_select_primary_v1"
        ).exists()

        # 2. Even with the committed DEV_TUNE plan bridge active, generic `run_cli`
        #    fails closed with `PromptFreezeFirewallError` because `run_cli` uses
        #    `build_default_infrastructure_prompt_registry()` whereas the committed
        #    prompt-freeze binds `build_frozen_p1_p2_registry()`
        #    (`846dc4c14ec2a87537b7b3e07bf492de51dc534d24b21e469094b7e3d34d32b6`).
        with launcher._launcher_runner_bridge():
            with pytest.raises(PromptFreezeFirewallError) as exc_bridged:
                run_generic_runner_cli(exact_generic_dev_select_live_argv)

        err_msg = str(exc_bridged.value)
        assert (
            "PROMPT_CANDIDATE_ID_MISMATCH" in err_msg
            or "846dc4c14ec2a87537b7b3e07bf492de51dc534d24b21e469094b7e3d34d32b6"
            in err_msg
            or "PROMPT_FREEZE" in err_msg
        )
        assert len(capability_attempts) == 2
        assert len(minted_capabilities) == 0
        assert transport_constructed is False
        assert batch_executed is False
        assert list(temp_batch_root.iterdir()) == []
        assert not (
            REPO_ROOT / "data/evaluation/w06/live_dev_select_primary_v1"
        ).exists()


def test_dsl_37_schema_authorities_locked(
    verified_authorities: dict[str, Any],
    preflight_out: dict[str, Any],
) -> None:
    """DSL-37: Verify Portable Schema V2 SHA256 and Semantic Schema SHA256 match frozen authorities across all 180 cells."""
    assert (
        verified_authorities["portable_schema_v2_sha256"]
        == EXPECTED_PORTABLE_SCHEMA_V2_SHA256
        == "825a4ff912d851a95f7392cb564b7d7ca3588135508dc6eb3ac6304cdde3c490"
    )
    assert (
        verified_authorities["semantic_schema_sha256"]
        == EXPECTED_SEMANTIC_SCHEMA_SHA256
        == "e4169f7b890f77d13af65e9f2070b6071c535b206d88440f5e8f28c179977555"
    )
    assert (
        preflight_out["portable_schema_v2_sha256"]
        == EXPECTED_PORTABLE_SCHEMA_V2_SHA256
    )
    assert preflight_out["semantic_schema_sha256"] == EXPECTED_SEMANTIC_SCHEMA_SHA256


def test_dsl_38_dev_select_fixture_partition_disjoint_from_dev_tune_and_final100() -> None:
    """DSL-38: Verify 60 DEV-SELECT fixtures W06-DEV-SELECT-001..060 are disjoint from DEV-TUNE and Final100."""
    dev_bundle = load_and_verify_frozen_dev_bundle()
    select_ids = [s.scenario_id for s in dev_bundle.dev_select_fixtures]
    tune_ids = {s.scenario_id for s in dev_bundle.dev_tune_fixtures}
    assert select_ids == [f"W06-DEV-SELECT-{i:03d}" for i in range(1, 61)]
    assert set(select_ids).isdisjoint(tune_ids)
    for sid in select_ids:
        assert_not_final100_scenario_id(sid)


def test_dsl_39_preflight_immutability_section_29() -> None:
    """DSL-39: Verify `--preflight` does not modify any tracked or frozen W06 artifact on disk (Section 29)."""
    frozen_files = {
        "data/evaluation/w06/w06_dev_select_execution_plan_v1.json": (
            "c519baf7cd2557b5e1dd2699a5ceaec592af015d7bc6dcc83abf63892a8a329a"
        ),
        "data/evaluation/w06/w06_dev_select_plan_freeze_01_receipt_v1.json": (
            "5f32782f6359f409c7dd68f08699218cd577cb48bcb517f14c15939f896b9549"
        ),
        "data/evaluation/w06/w06_dev_prompt_candidate_freeze_v1.json": (
            "2f345363f580ea882b2e5b3562c587ef5309bc7f994440257a54d18994ab6956"
        ),
        "data/evaluation/w06/w06_dev_tune_prompt_selection_v1.json": (
            "e1e79801117e59d3c8c703e024eacbad12d5336134c6597c333886c434a446b8"
        ),
        "data/evaluation/w06/w06_dev_select_authorization_prep_v1.json": (
            "60e6f0125ed54d6541e506e538a37b63b027a6c60a55572dcd612aa7cd2b72b8"
        ),
        "data/evaluation/w06/w06_dev_select_live_authorization_v1.json": (
            "247c0f201d8b900a1e0356d874891ba6e2884138b1ddd8500dfedb663f04f5f7"
        ),
        "data/evaluation/w06/w06_dev_select_live_authorization_01_receipt_v1.json": (
            "cb2dc986d9e03502f8e351d569e14d55147346fee64102a5f4cbedc9be895f39"
        ),
        "data/evaluation/w06/w06_dev_select_stage_a_freeze_receipt_v1.json": (
            "dd31582860e899b865d3dacd52bd1f92786ee6cf31d851e68e9050d93c451a26"
        ),
        "data/evaluation/w06/w06_dev_select_stage_a_freeze_01_receipt_v1.json": (
            "73eb38335f6fa0d21f9f38f0e15f9dc2c6497c46519a784b0d4e3df7da6a64c5"
        ),
    }
    for rel, exp_sha in frozen_files.items():
        actual_sha = sha256_bytes(normalize_lf_bytes((REPO_ROOT / rel).read_bytes()))
        assert actual_sha == exp_sha, f"Frozen artifact modified: {rel}"
    assert not (REPO_ROOT / "data/evaluation/w06/live_dev_select_primary_v1").exists()


def test_dsl_40_research_documentation_and_future_live_command_contract(
    preflight_out: dict[str, Any],
) -> None:
    """DSL-40: Verify research documentation exists and documents exact future live command and preflight hashes."""
    doc_path = REPO_ROOT / "docs/research/w06_dev_select_live_launcher_01.md"
    assert doc_path.is_file()
    doc_text = doc_path.read_text(encoding="utf-8")
    assert (
        "python scripts/run_w06_dev_select_live_v1.py --execute-live --confirm-frozen-180-cells"
        in doc_text
    )
    assert EXPECTED_PREFLIGHT_REQUEST_SET_SHA256 in doc_text
    assert EXPECTED_PREFLIGHT_ARTIFACT_PATH_SET_SHA256 in doc_text
    assert EXPECTED_LAUNCHER_LF_SHA256 in doc_text
    assert preflight_out["live_command"] == (
        "python scripts/run_w06_dev_select_live_v1.py --execute-live --confirm-frozen-180-cells"
    )
    assert preflight_out["dev_select_execution_started"] is False
    assert preflight_out["model_winner_selected"] is False
    assert preflight_out["stochasticity_execution_started"] is False
    assert preflight_out["final100_used"] is False
