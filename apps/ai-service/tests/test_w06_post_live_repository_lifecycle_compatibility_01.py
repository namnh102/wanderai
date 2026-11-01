"""Post-live repository lifecycle compatibility tests for W06 Amendment-01 Canary Live Execution 01.

Task: `W06-POST-LIVE-REPOSITORY-LIFECYCLE-COMPATIBILITY-CORRECTIVE-01`
Previous gate: `W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-CANARY-LIVE-EXECUTION-01-RESULTS-CHATGPT-AUDIT`

Covers:
1. Section 6: Explicit two-state lifecycle model (`PRE_EXECUTION` vs `POST_EXECUTION_EVIDENCE_PRESENT`);
2. Section 7: Immutable post-live evidence verification for `data/evaluation/w06/live_amendment_01_canary_v1`
   (exact 9 files, exact SHA256s, exact summary & cell 1 fail-stop `504 DEADLINE_EXCEEDED` fields,
   cells 2..9 absent);
3. Section 8: Historical pre-live phase firewall isolation (`AP-22`, `AU-29`, `SA-40`, `DSAP`,
   `DSAU-37`, `DSA-37`, `LL-33`, `LL-35`);
4. Section 9 & 10: Canary launcher and authorization receipt pre-live vs post-live separation;
5. Section 11: Rerun & overwrite protection (`CANARY_OUTPUT_ROOT_ALREADY_EXISTS`);
6. Section 12: Mandatory regression test matrix (Scenarios A through F).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
import sys
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
AI_SERVICE_DIR = REPO_ROOT / "apps" / "ai-service"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for _p in (AI_SERVICE_DIR, SCRIPTS_DIR, REPO_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from app.evaluation.dev_live_runner import (  # noqa: E402
    ImmutableCellExecutionError,
    LiveExecutionNotAuthorizedError,
    PlanBeforeLiveProtocolError,
)
from app.evaluation.dev_selection_harness import (  # noqa: E402
    FORBIDDEN_FINAL100_BUNDLE_SHA256,
    FORBIDDEN_P11_MANIFEST_SHA256,
    Final100FirewallViolationError,
    compute_scientific_code_bundle_sha256,
    normalize_lf_bytes,
    sha256_bytes,
)
import freeze_w06_dev_select_amendment_01_canary_live_execution_authorization as exec_auth_freeze  # noqa: E402
import freeze_w06_dev_select_stage_a as dsa_mod  # noqa: E402
import freeze_w06_dev_tune_stage_a as sa_mod  # noqa: E402
import issue_w06_dev_select_live_authorization as dsau_mod  # noqa: E402
import issue_w06_dev_tune_live_authorization as au_mod  # noqa: E402
import prepare_w06_dev_select_authorization as dsap_mod  # noqa: E402
import prepare_w06_dev_tune_authorization as ap_mod  # noqa: E402
import run_w06_dev_select_amendment_01_canary_live_v1 as canary_launcher  # noqa: E402
import verify_w06_dev_select_amendment_01_canary_live_execution_01_evidence as canary_evidence_ver  # noqa: E402


@pytest.fixture(autouse=True)
def _enforce_offline_and_secret_guards():
    """Run every test in this module under offline network and secret/env kill-switches."""
    with (
        canary_launcher.NetworkKillSwitchGuard(),
        canary_launcher.PreflightSecretAndEnvFileAccessGuard(),
    ):
        yield


# ==============================================================================
# SECTION 6 & 7: EXPLICIT LIFECYCLE MODEL & IMMUTABLE 9-FILE EVIDENCE VERIFIER
# ==============================================================================


def test_01_lifecycle_state_inspection_pre_and_post_execution(
    tmp_path: Path,
) -> None:
    """Section 6: Verify explicit lifecycle model (`PRE_EXECUTION` vs `POST_EXECUTION_EVIDENCE_PRESENT`)."""
    # 1. Isolated PRE_EXECUTION state (output root absent)
    pre_root = tmp_path / "pre_exec_out_root" / "live_amendment_01_canary_v1"
    pre_state = canary_evidence_ver.verify_w06_amendment_01_canary_repository_lifecycle(
        repo_root=REPO_ROOT,
        output_root_override=pre_root,
    )
    assert pre_state["lifecycle_state"] == canary_evidence_ver.LIFECYCLE_PRE_EXECUTION
    assert pre_state["output_root_exists"] is False
    assert pre_state["evidence_verified"] is False
    assert pre_state["LIVE_PROVIDER_CALLS_NEW"] == 0
    assert pre_state["AMENDED_COMPARATIVE_LIVE_AUTHORIZED"] is False
    assert pre_state["COMPARATIVE_EXECUTED"] is False
    assert pre_state["MODEL_WINNER_SELECTED"] is False
    assert pre_state["SELECTED_MODEL_ID"] is None
    assert pre_state["STOCHASTICITY_EXECUTION_STARTED"] is False
    assert pre_state["FINAL100_USED"] is False
    assert pre_state["FINAL100_STATUS"] == "NO-GO"

    # 2. Isolated POST_EXECUTION_EVIDENCE_PRESENT state (exact 9 frozen files materialized)
    post_root = tmp_path / "post_exec_out_root" / "live_amendment_01_canary_v1"
    canary_evidence_ver.materialize_frozen_canary_live_execution_01_evidence_tree(
        post_root, repo_root=REPO_ROOT
    )
    post_state = canary_evidence_ver.verify_w06_amendment_01_canary_repository_lifecycle(
        repo_root=REPO_ROOT,
        output_root_override=post_root,
        require_evidence_present=True,
    )
    assert (
        post_state["lifecycle_state"]
        == canary_evidence_ver.LIFECYCLE_POST_EXECUTION_EVIDENCE_PRESENT
    )
    assert post_state["output_root_exists"] is True
    assert post_state["evidence_verified"] is True
    assert post_state["second_live_execution_blocked"] is True
    assert post_state["evidence_summary"]["file_count"] == 9


def test_02_post_live_immutable_evidence_verifier_all_9_files_and_semantics(
    tmp_path: Path,
) -> None:
    """Section 7: Verify all 9 frozen files, SHA256 hashes, batch summary fields, cell 1 fail-stop receipt, and absence of cells 2..9."""
    evidence_root = tmp_path / "live_amendment_01_canary_v1"
    canary_evidence_ver.materialize_frozen_canary_live_execution_01_evidence_tree(
        evidence_root, repo_root=REPO_ROOT
    )

    res = canary_evidence_ver.verify_w06_amendment_01_canary_live_execution_01_evidence_tree(
        repo_root=REPO_ROOT,
        output_root_override=evidence_root,
    )
    assert res["verified"] is True
    assert res["lifecycle_state"] == "POST_EXECUTION_EVIDENCE_PRESENT"
    assert res["file_count"] == 9
    assert (
        res["batch_summary_sha256"]
        == "d16a3f5f49101914a584045bee2e7470e4dee7eb7aa106c7e9409b1d3d77a8ec"
    )
    assert (
        res["cell_01_receipt_sha256"]
        == "1456833419e4ba76bd52be9f3e4444724febc52e24e08ff30c808379596442c6"
    )
    assert (
        res["file_hashes"]
        == canary_evidence_ver.EXPECTED_CANARY_LIVE_EXECUTION_01_EVIDENCE_FILE_SHA256S
    )

    # Downstream firewalls
    assert res["ALL_9_CANARY_OPERATIONAL_PASS"] is False
    assert res["AMENDED_COMPARATIVE_LIVE_AUTHORIZED"] is False
    assert res["COMPARATIVE_EXECUTED"] is False
    assert res["MODEL_WINNER_SELECTED"] is False
    assert res["SELECTED_MODEL_ID"] is None
    assert res["STOCHASTICITY_EXECUTION_STARTED"] is False
    assert res["FINAL100_USED"] is False
    assert res["FINAL100_STATUS"] == "NO-GO"

    # Verify cells 2..9 directories do not exist
    for cell_id in canary_evidence_ver.EXPECTED_UNSCHEDULED_CELL_IDS:
        assert not (evidence_root / cell_id).exists()


# ==============================================================================
# SECTION 12: MANDATORY REGRESSION TEST MATRIX (SCENARIOS A .. F)
# ==============================================================================


def test_03_scenario_a_historical_pre_live_environment_guards_pass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scenario A: Historical pre-live environment (synthetic/isolated canonical root absent -> old PREP/pre-live guards PASS)."""
    isolated_absent_root = tmp_path / "absent_canary_root" / "live_amendment_01_canary_v1"
    assert not isolated_absent_root.exists()

    # 1. Canary output-root absence guard passes when canonical root is absent
    canary_launcher.verify_canary_output_root_not_existing(
        repo_root=REPO_ROOT,
        output_root_override=isolated_absent_root,
    )

    # 2. Frozen canary launcher authorities & preflight pass against isolated absent output root
    auths = canary_launcher.verify_frozen_canary_launcher_authorities(
        repo_root=REPO_ROOT,
        output_root_override=isolated_absent_root,
    )
    assert auths["output_root"] == isolated_absent_root

    orig_inspect = canary_launcher.inspect_canary_live_execution_authorization_state
    shallow_git_runner = exec_auth_freeze.build_shallow_aware_git_runner(REPO_ROOT)
    monkeypatch.setattr(
        canary_launcher,
        "inspect_canary_live_execution_authorization_state",
        lambda repo_root=REPO_ROOT, **kwargs: orig_inspect(
            repo_root=repo_root,
            git_runner=kwargs.get("git_runner") or shallow_git_runner,
            receipt_path_override=kwargs.get("receipt_path_override"),
            launcher_file_path_override=kwargs.get("launcher_file_path_override"),
        ),
    )

    preflight = canary_launcher.run_preflight(
        repo_root=REPO_ROOT,
        output_root_override=isolated_absent_root,
    )
    assert preflight["status"] == "PASS"
    assert preflight["verified"] is True
    assert preflight["output_root_exists"] is False

    # 3. Receipt verifier in strict pre-execution mode passes when output root is absent
    rec_ver = exec_auth_freeze.verify_canary_live_execution_authorization_artifacts(
        repo_root=REPO_ROOT,
        output_root_override=isolated_absent_root,
        require_pre_execution_output_root_absent=True,
    )
    assert rec_ver["status"] == "PASS"
    assert rec_ver["verified"] is True
    assert rec_ver["lifecycle_state"] == "PRE_EXECUTION"


def test_04_scenario_b_unauthorized_live_evidence_in_forbidden_path_rejected(
    tmp_path: Path,
) -> None:
    """Scenario B: Unauthorized live evidence in a phase-specific forbidden path -> corresponding historical guard FAILS."""
    fake_repo = tmp_path / "fake_repo_unauth"
    fake_w06 = fake_repo / "data" / "evaluation" / "w06"
    fake_w06.mkdir(parents=True, exist_ok=True)

    # Copy verified baseline files needed for directory scan and then plant an unauthorized transport journal & rogue live dir
    rogue_dir = fake_w06 / "live_dev_select_rogue_unverified_run"
    rogue_dir.mkdir(parents=True, exist_ok=True)
    rogue_journal = rogue_dir / "transport_journal.jsonl"
    rogue_journal.write_text('{"rogue": true}\n', encoding="utf-8")

    # Also plant an unverified/tampered file inside live_amendment_01_canary_v1
    tampered_canary_dir = fake_w06 / "live_amendment_01_canary_v1"
    tampered_canary_dir.mkdir(parents=True, exist_ok=True)
    (tampered_canary_dir / "transport_journal.jsonl").write_text(
        '{"tampered_canary_journal": true}\n', encoding="utf-8"
    )

    for firewall_fn in (
        ap_mod.verify_pre_authorization_firewall,
        au_mod.verify_pre_stage_a_firewall,
        sa_mod.verify_no_live_execution_or_stage_b_artifacts,
        dsap_mod.verify_pre_authorization_firewall,
        dsau_mod.verify_pre_stage_a_firewall,
        dsa_mod.verify_no_live_execution_or_stage_b_artifacts,
    ):
        fw = firewall_fn(fake_repo)
        assert fw["transport_journal_created"] is True
        assert (
            "data/evaluation/w06/live_dev_select_rogue_unverified_run/transport_journal.jsonl"
            in fw["forbidden_transport_journals"]
        )
        assert (
            "data/evaluation/w06/live_amendment_01_canary_v1/transport_journal.jsonl"
            in fw["forbidden_transport_journals"]
        )


def test_05_scenario_c_authorized_downstream_amendment_01_evidence_allows_historical_phase_firewalls(
    tmp_path: Path,
) -> None:
    """Scenario C: Authorized downstream Amendment-01 evidence exists -> unrelated historical phase firewall checks PASS."""
    # Build a synthetic repo view with the exact verified 9-file Amendment-01 canary evidence tree
    fake_repo = tmp_path / "fake_repo_with_verified_canary"
    fake_w06 = fake_repo / "data" / "evaluation" / "w06"
    fake_w06.mkdir(parents=True, exist_ok=True)

    # Copy top-level W06 JSON authority files so JSON root inspection in historical firewalls runs against real artifacts
    real_w06 = REPO_ROOT / "data" / "evaluation" / "w06"
    for item in real_w06.iterdir():
        if item.is_file():
            shutil.copy2(item, fake_w06 / item.name)

    canary_out = fake_w06 / "live_amendment_01_canary_v1"
    canary_evidence_ver.materialize_frozen_canary_live_execution_01_evidence_tree(
        canary_out, repo_root=REPO_ROOT
    )
    assert (
        canary_evidence_ver.is_verified_downstream_w06_amendment_01_canary_live_evidence_tree(
            fake_repo
        )
        is True
    )

    # Verify all 6 historical firewall functions report zero forbidden transport journals and zero forbidden live cell dirs
    ap_fw = ap_mod.verify_pre_authorization_firewall(fake_repo)
    assert ap_fw["transport_journal_created"] is False
    assert ap_fw["provider_result_directories_created"] is False
    assert ap_fw["forbidden_transport_journals"] == []
    assert ap_fw["forbidden_live_cell_dirs"] == []

    au_fw = au_mod.verify_pre_stage_a_firewall(fake_repo)
    assert au_fw["transport_journal_created"] is False
    assert au_fw["provider_result_directory_created"] is False
    assert au_fw["forbidden_transport_journals"] == []
    assert au_fw["forbidden_live_cell_dirs"] == []

    sa_fw = sa_mod.verify_no_live_execution_or_stage_b_artifacts(fake_repo)
    assert sa_fw["transport_journal_created"] is False
    assert sa_fw["provider_result_directory_created"] is False
    assert sa_fw["forbidden_transport_journals"] == []
    assert sa_fw["forbidden_live_cell_dirs"] == []

    dsap_fw = dsap_mod.verify_pre_authorization_firewall(fake_repo)
    assert dsap_fw["transport_journal_created"] is False
    assert dsap_fw["dev_select_live_result_directory_created"] is False
    assert dsap_fw["forbidden_transport_journals"] == []
    assert dsap_fw["forbidden_dev_select_live_dirs"] == []

    dsau_fw = dsau_mod.verify_pre_stage_a_firewall(fake_repo)
    assert dsau_fw["transport_journal_created"] is False
    assert dsau_fw["dev_select_live_result_directory_created"] is False
    assert dsau_fw["forbidden_transport_journals"] == []
    assert dsau_fw["forbidden_dev_select_live_dirs"] == []

    dsa_fw = dsa_mod.verify_no_live_execution_or_stage_b_artifacts(fake_repo)
    assert dsa_fw["transport_journal_created"] is False
    assert dsa_fw["dev_select_live_result_directory_created"] is False
    assert dsa_fw["forbidden_transport_journals"] == []
    assert dsa_fw["forbidden_dev_select_live_dirs"] == []


def test_06_scenario_d_second_canary_live_execution_blocked_when_canonical_root_exists(
    tmp_path: Path,
) -> None:
    """Scenario D: Canonical Amendment-01 live root exists -> second canary live execution is blocked fail-closed before key access or network."""
    existing_canary_root = tmp_path / "live_amendment_01_canary_v1"
    canary_evidence_ver.materialize_frozen_canary_live_execution_01_evidence_tree(
        existing_canary_root, repo_root=REPO_ROOT
    )

    prefix = f"{canary_evidence_ver.CANARY_LIVE_EVIDENCE_OUTPUT_ROOT_REL_PATH}/"
    before_sha_map = {
        rel: sha256_bytes(
            normalize_lf_bytes(
                (existing_canary_root / rel.removeprefix(prefix)).read_bytes()
            )
        )
        for rel in canary_evidence_ver.EXPECTED_CANARY_LIVE_EXECUTION_01_EVIDENCE_FILE_SHA256S
    }

    key_loader_called = False
    transport_called = False

    def _forbidden_key_loader(_cid: str) -> str:
        nonlocal key_loader_called
        key_loader_called = True
        raise AssertionError("API key loader must not be reached when output root exists")

    def _forbidden_transport(**_kwargs: Any) -> Any:
        nonlocal transport_called
        transport_called = True
        raise AssertionError("Transport invoker must not be reached when output root exists")

    # 1. Direct `verify_canary_output_root_not_existing` fails closed
    with pytest.raises(
        ImmutableCellExecutionError, match="CANARY_OUTPUT_ROOT_ALREADY_EXISTS"
    ):
        canary_launcher.verify_canary_output_root_not_existing(
            repo_root=REPO_ROOT,
            output_root_override=existing_canary_root,
        )

    # 2. `run_live_canary_execution` fails closed before key loader or transport
    with pytest.raises(
        ImmutableCellExecutionError, match="CANARY_OUTPUT_ROOT_ALREADY_EXISTS"
    ):
        canary_launcher.run_live_canary_execution(
            repo_root=REPO_ROOT,
            output_root_override=existing_canary_root,
            git_runner=exec_auth_freeze.build_shallow_aware_git_runner(REPO_ROOT),
            api_key_loader=_forbidden_key_loader,
            live_transport_invoker=_forbidden_transport,
        )

    # 3. CLI `--execute-live --confirm-frozen-9-canary-cells` fails closed
    with pytest.raises(
        ImmutableCellExecutionError, match="CANARY_OUTPUT_ROOT_ALREADY_EXISTS"
    ):
        canary_launcher.run_canary_launcher_cli(
            ["--execute-live", "--confirm-frozen-9-canary-cells"],
            repo_root=REPO_ROOT,
            output_root_override=existing_canary_root,
        )

    assert key_loader_called is False
    assert transport_called is False

    # Verify all 9 evidence files remain byte-identical (no overwrite occurred)
    after_sha_map = {
        rel: sha256_bytes(
            normalize_lf_bytes(
                (existing_canary_root / rel.removeprefix(prefix)).read_bytes()
            )
        )
        for rel in canary_evidence_ver.EXPECTED_CANARY_LIVE_EXECUTION_01_EVIDENCE_FILE_SHA256S
    }
    assert after_sha_map == before_sha_map


def test_07_scenario_e_frozen_evidence_hash_alteration_or_extra_file_fails(
    tmp_path: Path,
) -> None:
    """Scenario E: Frozen evidence hash altered or unexpected file/cell added -> post-live immutable evidence verifier FAILS."""
    # Case 1: Tamper with `canary_batch_execution_summary_v1.json`
    root_1 = tmp_path / "case_1_tampered_summary" / "live_amendment_01_canary_v1"
    canary_evidence_ver.materialize_frozen_canary_live_execution_01_evidence_tree(
        root_1, repo_root=REPO_ROOT
    )
    summary_path = root_1 / "canary_batch_execution_summary_v1.json"
    summary_data = json.loads(summary_path.read_text(encoding="utf-8"))
    summary_data["operational_pass_cells_count"] = 9
    summary_path.write_text(
        json.dumps(summary_data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="CANARY_LIVE_EVIDENCE_FILE_SHA256_MISMATCH",
    ):
        canary_evidence_ver.verify_w06_amendment_01_canary_live_execution_01_evidence_tree(
            repo_root=REPO_ROOT,
            output_root_override=root_1,
        )

    # Case 2: Tamper with cell 1 `canary_cell_evidence_receipt.json`
    root_2 = tmp_path / "case_2_tampered_cell_receipt" / "live_amendment_01_canary_v1"
    canary_evidence_ver.materialize_frozen_canary_live_execution_01_evidence_tree(
        root_2, repo_root=REPO_ROOT
    )
    cell_rec_path = (
        root_2
        / canary_evidence_ver.CANARY_CELL_01_ID
        / "canary_cell_evidence_receipt.json"
    )
    cell_rec = json.loads(cell_rec_path.read_text(encoding="utf-8"))
    cell_rec["cell_operational_pass"] = True
    cell_rec_path.write_text(
        json.dumps(cell_rec, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="CANARY_LIVE_EVIDENCE_FILE_SHA256_MISMATCH",
    ):
        canary_evidence_ver.verify_w06_amendment_01_canary_live_execution_01_evidence_tree(
            repo_root=REPO_ROOT,
            output_root_override=root_2,
        )

    # Case 3: Add an unexpected cell 2 directory
    root_3 = tmp_path / "case_3_extra_cell_dir" / "live_amendment_01_canary_v1"
    canary_evidence_ver.materialize_frozen_canary_live_execution_01_evidence_tree(
        root_3, repo_root=REPO_ROOT
    )
    extra_cell = root_3 / "W06-AMENDMENT-01-CANARY-02-P1-C2-W06-DEV-TUNE-007"
    extra_cell.mkdir(parents=True, exist_ok=True)
    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match=(
            "UNSCHEDULED_CANARY_CELL_DIR_FORBIDDEN|"
            "CANARY_LIVE_EVIDENCE_ROOT_CHILDREN_MISMATCH"
        ),
    ):
        canary_evidence_ver.verify_w06_amendment_01_canary_live_execution_01_evidence_tree(
            repo_root=REPO_ROOT,
            output_root_override=root_3,
        )

    # Case 4: Delete one of the 9 required evidence files
    root_4 = tmp_path / "case_4_missing_file" / "live_amendment_01_canary_v1"
    canary_evidence_ver.materialize_frozen_canary_live_execution_01_evidence_tree(
        root_4, repo_root=REPO_ROOT
    )
    (
        root_4
        / canary_evidence_ver.CANARY_CELL_01_ID
        / "transport_journal_completed.json"
    ).unlink()
    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="CANARY_LIVE_EVIDENCE_FILE_SET_MISMATCH",
    ):
        canary_evidence_ver.verify_w06_amendment_01_canary_live_execution_01_evidence_tree(
            repo_root=REPO_ROOT,
            output_root_override=root_4,
        )


def test_08_scenario_f_comparative_winner_final100_or_primary_mutation_fails(
    tmp_path: Path,
) -> None:
    """Scenario F: Comparative / winner / Final100 / primary-result mutation -> FAILS."""
    receipt_path = REPO_ROOT / exec_auth_freeze.RECEIPT_REL_PATH
    base_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    def _write_resigned(name: str, mutated: dict[str, Any]) -> Path:
        cloned = copy.deepcopy(mutated)
        key = exec_auth_freeze.RECEIPT_INTERNAL_SHA_KEY
        without_sig = {k: v for k, v in cloned.items() if k != key}
        from app.evaluation.dev_selection_harness import canonical_json_bytes

        cloned[key] = sha256_bytes(canonical_json_bytes(without_sig))
        out = tmp_path / name
        out.write_text(
            json.dumps(cloned, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return out

    # 1. Comparative authorization mutation fails
    bad_comp = copy.deepcopy(base_receipt)
    bad_comp["AMENDED_COMPARATIVE_LIVE_AUTHORIZED"] = True
    p_comp = _write_resigned("bad_comp.json", bad_comp)
    with pytest.raises(
        LiveExecutionNotAuthorizedError,
        match="CANARY_EXECUTION_AUTH_COMPARATIVE_OR_DOWNSTREAM_FORBIDDEN",
    ):
        exec_auth_freeze.verify_canary_live_execution_authorization_artifacts(
            repo_root=REPO_ROOT,
            receipt_path_override=p_comp,
        )

    # 2. Winner selection mutation fails
    bad_winner = copy.deepcopy(base_receipt)
    bad_winner["MODEL_WINNER_SELECTED"] = True
    bad_winner["SELECTED_MODEL_ID"] = "gemini-3.8-flash"
    p_winner = _write_resigned("bad_winner.json", bad_winner)
    with pytest.raises(
        LiveExecutionNotAuthorizedError,
        match="CANARY_EXECUTION_AUTH_COMPARATIVE_OR_DOWNSTREAM_FORBIDDEN",
    ):
        exec_auth_freeze.verify_canary_live_execution_authorization_artifacts(
            repo_root=REPO_ROOT,
            receipt_path_override=p_winner,
        )

    # 3. Final100 firewall mutation fails
    bad_f100 = copy.deepcopy(base_receipt)
    bad_f100["FINAL100_USED"] = True
    bad_f100["FINAL100_STATUS"] = "GO"
    p_f100 = _write_resigned("bad_f100.json", bad_f100)
    with pytest.raises(
        Final100FirewallViolationError,
        match="CANARY_EXECUTION_AUTH_FINAL100_FORBIDDEN",
    ):
        exec_auth_freeze.verify_canary_live_execution_authorization_artifacts(
            repo_root=REPO_ROOT,
            receipt_path_override=p_f100,
        )

    # 4. Primary results replacement mutation fails
    bad_prim = copy.deepcopy(base_receipt)
    bad_prim["PRIMARY_RESULTS_REPLACED"] = True
    p_prim = _write_resigned("bad_prim.json", bad_prim)
    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="CANARY_EXECUTION_RECEIPT_GOVERNANCE_OR_DOWNSTREAM_FIREWALL_MISMATCH",
    ):
        exec_auth_freeze.verify_canary_live_execution_authorization_artifacts(
            repo_root=REPO_ROOT,
            receipt_path_override=p_prim,
        )

    # 5. Verify Final100, P11, scientific code bundle, primary launcher, and canary launcher hashes on disk
    assert (
        compute_scientific_code_bundle_sha256(repo_root=REPO_ROOT)
        == "0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3"
    )
    assert (
        sha256_bytes(
            normalize_lf_bytes(
                (REPO_ROOT / "scripts/run_w06_dev_select_amendment_01_canary_live_v1.py").read_bytes()
            )
        )
        == "7db06f178d5e07980642dc846fa160f51305db7ce59981e706790a3475a8bda2"
    )
    assert (
        sha256_bytes(
            normalize_lf_bytes(
                (REPO_ROOT / "scripts/run_w06_dev_select_live_v1.py").read_bytes()
            )
        )
        == "cd36b8ecad24059edb597c0039bd6e760a37ee8b4f36f49077801c65e7ddc7bf"
    )
    assert (
        sha256_bytes(
            normalize_lf_bytes(
                (REPO_ROOT / "data/evaluation/w06/w06_scenarios_freeze_v1.json").read_bytes()
            )
        )
        == FORBIDDEN_FINAL100_BUNDLE_SHA256
    )
    assert (
        sha256_bytes(
            normalize_lf_bytes(
                (REPO_ROOT / "data/evaluation/w06/w06_p11_assignment_manifest_v1.json").read_bytes()
            )
        )
        == FORBIDDEN_P11_MANIFEST_SHA256
    )
