"""Pytest suite for W06-DEV-SELECT-STAGE-A-FREEZE-01.

Verifies:
- DSA-01 through DSA-40 Stage-A freeze checks (Section 18)
- ADV-01 through ADV-27 adversarial fail-closed checks (Section 19)
- Production DevLiveStageAFreezeReceipt contract validation
- Process A single-generation refusal on existing receipt
- Same-process barrier (`STAGE_A_AND_STAGE_B_SAME_PROCESS_FORBIDDEN`)
- Separate-process Process B read-only committed verification (`require_git_committed=True`)
- Git ancestor & blob attestation for code_basis_commit_sha (`c0adf74...`) and stage_a_commit_sha (`e69b7d70...`)
- Cryptographic downstream Stage-A recognition and fail-closed rejection (Section 17)
- Outbound network kill switch covering socket, urllib, httpx, and httpx2
"""

from __future__ import annotations

import hashlib
import json
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
    _CURRENT_PROCESS_INVOCATION_TOKEN,
    _build_stage_a_freeze_receipt_with_token,
    CandidateRegistryIntegrityError,
    DevLiveStageAFreezeReceipt,
    PlanBeforeLiveProtocolError,
    STAGE_A_FREEZE_RECEIPT_ARTIFACT_ID,
    STAGE_A_STATUS_FROZEN_BEFORE_LIVE,
    assert_no_secrets_in_payload,
    compute_assigned_cells_sha256,
    verify_stage_a_freeze_receipt,
)
from app.evaluation.dev_selection_harness import (  # noqa: E402
    Final100FirewallViolationError,
    ScientificCodeBundleIntegrityError,
    DevExecutionPlan,
    canonical_json_bytes,
    normalize_lf_bytes,
    sha256_bytes,
    verify_dev_execution_plan_for_execution,
)
import freeze_w06_dev_select_stage_a as dsa_mod  # noqa: E402
import issue_w06_dev_select_live_authorization as ds_auth_mod  # noqa: E402
import prepare_w06_dev_select_authorization as ds_prep_mod  # noqa: E402


DSA_CHECK_IDS = [f"DSA-{i:02d}" for i in range(1, 41)]
ADV_CHECK_IDS = [f"ADV-{i:02d}" for i in range(1, 28)]


def test_all_40_dsa_checks_pass() -> None:
    """Verify DSA-01 through DSA-40 all pass against the repository and committed Stage-A receipt."""
    checks = dsa_mod.run_all_dsa_checks(REPO_ROOT, require_committed_in_head=True)
    assert len(checks) == 40
    assert [c["check_id"] for c in checks] == DSA_CHECK_IDS

    failed = [c for c in checks if c["status"] != "PASS"]
    assert not failed, f"Failed DSA checks: {failed}"


@pytest.mark.parametrize("check_id", DSA_CHECK_IDS)
def test_individual_dsa_check_in_persisted_receipt(check_id: str) -> None:
    """Verify each DSA-01..DSA-40 check recorded in w06_dev_select_stage_a_freeze_01_receipt_v1.json is PASS."""
    receipt_path = REPO_ROOT / dsa_mod.TASK_AUDIT_RECEIPT_REL_PATH
    data = json.loads(receipt_path.read_text(encoding="utf-8"))
    matching = [c for c in data["checks"] if c["check_id"] == check_id]
    assert len(matching) == 1
    assert matching[0]["status"] == "PASS"


def test_all_27_adversarial_checks_pass() -> None:
    """Verify ADV-01 through ADV-27 adversarial checks all pass."""
    adv_checks = dsa_mod.run_all_adversarial_checks(REPO_ROOT)
    assert len(adv_checks) == 27
    assert [c["check_id"] for c in adv_checks] == ADV_CHECK_IDS

    failed = [c for c in adv_checks if c["status"] != "PASS"]
    assert not failed, f"Failed adversarial checks: {failed}"


@pytest.mark.parametrize("check_id", ADV_CHECK_IDS)
def test_individual_adversarial_check_in_persisted_receipt(check_id: str) -> None:
    """Verify each ADV-01..ADV-27 adversarial check recorded in w06_dev_select_stage_a_freeze_01_receipt_v1.json is PASS."""
    receipt_path = REPO_ROOT / dsa_mod.TASK_AUDIT_RECEIPT_REL_PATH
    data = json.loads(receipt_path.read_text(encoding="utf-8"))
    matching = [c for c in data["adversarial_checks"] if c["check_id"] == check_id]
    assert len(matching) == 1
    assert matching[0]["status"] == "PASS"


def test_persisted_stage_a_receipt_and_task_audit_receipt_integrity() -> None:
    """Verify persisted Stage-A receipt and task audit receipt match production contract and hashes."""
    stage_a_path = REPO_ROOT / dsa_mod.STAGE_A_RECEIPT_REL_PATH
    audit_path = REPO_ROOT / dsa_mod.TASK_AUDIT_RECEIPT_REL_PATH

    stage_a_raw = stage_a_path.read_bytes()
    audit_raw = audit_path.read_bytes()
    assert b"\r\n" not in stage_a_raw
    assert b"\r\n" not in audit_raw

    stage_a_file_sha = sha256_bytes(normalize_lf_bytes(stage_a_raw))
    audit_file_sha = sha256_bytes(normalize_lf_bytes(audit_raw))
    assert stage_a_file_sha == dsa_mod.EXPECTED_STAGE_A_RECEIPT_FILE_SHA256
    assert audit_file_sha == dsa_mod.EXPECTED_TASK_AUDIT_RECEIPT_FILE_SHA256

    stage_a_dict = json.loads(stage_a_raw.decode("utf-8"))
    audit_dict = json.loads(audit_raw.decode("utf-8"))

    assert_no_secrets_in_payload(stage_a_dict, context="TEST_PERSISTED_DEV_SELECT_STAGE_A")
    assert_no_secrets_in_payload(
        audit_dict, context="TEST_PERSISTED_DEV_SELECT_STAGE_A_AUDIT"
    )

    auths = dsa_mod.load_verified_stage_a_authorities(REPO_ROOT)
    validated_stage_a = dsa_mod.verify_committed_stage_a_or_shallow_ci_fallback(
        stage_a_path,
        execution_plan=auths["execution_plan"],
        prompt_freeze=auths["prompt_freeze"],
        authorization=auths["authorization"],
        execution_plan_path=REPO_ROOT / dsa_mod.DEV_SELECT_PLAN_REL_PATH,
        prompt_freeze_path=REPO_ROOT / dsa_mod.PROMPT_FREEZE_REL_PATH,
        authorization_path=REPO_ROOT / dsa_mod.AUTHORIZATION_REL_PATH,
        candidate_registry=auths["candidate_registry"],
        repo_root=REPO_ROOT,
    )
    assert isinstance(validated_stage_a, DevLiveStageAFreezeReceipt)
    assert validated_stage_a.artifact_id == STAGE_A_FREEZE_RECEIPT_ARTIFACT_ID
    assert validated_stage_a.phase == "DEV_SELECT"
    assert (
        validated_stage_a.execution_plan_sha256
        == "de04255989a9e3bd8c2e39c766432487dce4ccd0612d5dba73b3476cbc9d0c6d"
    )
    assert (
        validated_stage_a.prompt_freeze_sha256
        == "2f345363f580ea882b2e5b3562c587ef5309bc7f994440257a54d18994ab6956"
    )
    assert (
        validated_stage_a.authorization_artifact_sha256
        == "31cebcf5aafa7a575d4bf1327fc9d454a2817c2acbbdb2c087d8c1210e8ec504"
    )
    assert (
        validated_stage_a.scientific_code_bundle_sha256
        == "0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3"
    )
    assert (
        validated_stage_a.provider_config_registry_sha256
        == "3dc05d29acc2f647cba58303865bd7406b8c1d9f7ccbe0f120e87ad471190938"
    )
    assert (
        validated_stage_a.code_basis_commit_sha
        == "c0adf74ceda9ffaf8b4ec42d299932e33f448e6a"
    )
    assert (
        validated_stage_a.stage_a_commit_sha
        == "e69b7d70c3908d2b888b7c5d7e6c4e1d49fac863"
    )
    assert validated_stage_a.stage_a_status == STAGE_A_STATUS_FROZEN_BEFORE_LIVE
    assert len(validated_stage_a.assigned_cell_run_ids) == 180
    expected_run_ids, expected_cells_sha = compute_assigned_cells_sha256(
        auths["execution_plan"]
    )
    assert validated_stage_a.assigned_cell_run_ids == expected_run_ids
    assert validated_stage_a.assigned_cells_sha256 == expected_cells_sha
    assert (
        validated_stage_a.stage_a_receipt_sha256
        == dsa_mod.EXPECTED_STAGE_A_RECEIPT_INTERNAL_SHA256
    )

    assert audit_dict["artifact_id"] == "W06-DEV-SELECT-STAGE-A-FREEZE-01-RECEIPT-V1"
    assert audit_dict["task_id"] == "W06-DEV-SELECT-STAGE-A-FREEZE-01"
    assert audit_dict["source_develop_sha"] == "e69b7d70c3908d2b888b7c5d7e6c4e1d49fac863"
    assert (
        audit_dict["code_basis_commit_sha"]
        == "c0adf74ceda9ffaf8b4ec42d299932e33f448e6a"
    )
    assert (
        audit_dict["stage_a_commit_sha"]
        == "e69b7d70c3908d2b888b7c5d7e6c4e1d49fac863"
    )
    assert audit_dict["selected_prompt_id"] == "P1"
    assert (
        audit_dict["selected_prompt_semantic_sha256"]
        == "096ff4c74dd8d1aed1c0abe501b97c8dfd0f6424dbca535f2b79a242637a1c11"
    )
    assert audit_dict["assigned_cell_count"] == 180
    assert audit_dict["stage_a_receipt_file_sha256"] == stage_a_file_sha
    assert (
        audit_dict["stage_a_receipt_sha256"]
        == validated_stage_a.stage_a_receipt_sha256
    )
    assert audit_dict["same_process_verification_rejected"] is True
    assert audit_dict["separate_process_committed_verification_passed"] is True
    assert audit_dict["live_execution_capability_issued"] is False
    assert audit_dict["production_provider_transport_constructed"] is False
    assert audit_dict["transport_journal_created"] is False
    assert audit_dict["dev_select_live_result_directory_created"] is False
    assert audit_dict["dev_select_execution_started"] is False
    assert audit_dict["live_provider_calls_new"] == 0
    assert audit_dict["provider_cost_usd_new"] == 0
    assert audit_dict["model_winner_selected"] is False
    assert audit_dict["stochasticity_execution_started"] is False
    assert audit_dict["final100_used"] is False


def test_process_a_refuses_to_overwrite_existing_stage_a_receipt() -> None:
    """Verify Process A (--create-stage-a) refuses to overwrite the existing Stage-A receipt."""
    stage_a_path = REPO_ROOT / dsa_mod.STAGE_A_RECEIPT_REL_PATH
    before_bytes = stage_a_path.read_bytes()
    with pytest.raises(RuntimeError, match="STAGE_A_RECEIPT_ALREADY_EXISTS"):
        dsa_mod.generate_stage_a_receipt_once_process_a(REPO_ROOT)
    assert stage_a_path.read_bytes() == before_bytes


def test_adversarial_stage_a_tampering_and_same_process_barrier(
    tmp_path: Path,
) -> None:
    """Directly test all adversarial Stage-A rejection conditions required in Section 19."""
    auths = dsa_mod.load_verified_stage_a_authorities(REPO_ROOT)
    plan_model: DevExecutionPlan = auths["execution_plan"]
    freeze_model = auths["prompt_freeze"]
    auth_model = auths["authorization"]
    cand_reg = auths["candidate_registry"]

    stage_a_path = REPO_ROOT / dsa_mod.STAGE_A_RECEIPT_REL_PATH
    persisted = DevLiveStageAFreezeReceipt.model_validate_json(
        normalize_lf_bytes(stage_a_path.read_bytes())
    )
    base = persisted.model_dump(exclude={"stage_a_receipt_sha256"})
    base["stage_a_process_token"] = "pid-77777-ns-123"

    def _tamper(**overrides: object) -> dict[str, object]:
        d = dict(base)
        d.update(overrides)
        d["stage_a_receipt_sha256"] = sha256_bytes(canonical_json_bytes(d))
        return d

    # 1 & 2. Wrong phase DEV_TUNE and STOCHASTICITY
    for bad_phase in ("DEV_TUNE", "STOCHASTICITY"):
        with pytest.raises(PlanBeforeLiveProtocolError, match="STAGE_A_PHASE_MISMATCH"):
            verify_stage_a_freeze_receipt(
                _tamper(phase=bad_phase),
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
                authorization=auth_model,
                candidate_registry=cand_reg,
                repo_root=REPO_ROOT,
                require_git_committed=False,
            )

    # 3. Final100 path
    with pytest.raises(Final100FirewallViolationError):
        verify_stage_a_freeze_receipt(
            REPO_ROOT / "data/evaluation/w06/w06_scenarios_freeze_v1.json",
            execution_plan=plan_model,
            prompt_freeze=freeze_model,
            authorization=auth_model,
            candidate_registry=cand_reg,
            repo_root=REPO_ROOT,
            require_git_committed=False,
        )

    # 4. Wrong plan SHA
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="STAGE_A_PLAN_SHA256_MISMATCH"
    ):
        verify_stage_a_freeze_receipt(
            _tamper(execution_plan_sha256="1" * 64),
            execution_plan=plan_model,
            prompt_freeze=freeze_model,
            authorization=auth_model,
            candidate_registry=cand_reg,
            repo_root=REPO_ROOT,
            require_git_committed=False,
        )

    # 5. Wrong prompt freeze SHA
    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="STAGE_A_PROMPT_FREEZE_SHA256_MISMATCH",
    ):
        verify_stage_a_freeze_receipt(
            _tamper(prompt_freeze_sha256="2" * 64),
            execution_plan=plan_model,
            prompt_freeze=freeze_model,
            authorization=auth_model,
            candidate_registry=cand_reg,
            repo_root=REPO_ROOT,
            require_git_committed=False,
        )

    # 6. Wrong authorization SHA
    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="STAGE_A_AUTHORIZATION_SHA256_MISMATCH",
    ):
        verify_stage_a_freeze_receipt(
            _tamper(authorization_artifact_sha256="3" * 64),
            execution_plan=plan_model,
            prompt_freeze=freeze_model,
            authorization=auth_model,
            candidate_registry=cand_reg,
            repo_root=REPO_ROOT,
            require_git_committed=False,
        )

    # 7. Wrong scientific bundle SHA
    with pytest.raises(
        ScientificCodeBundleIntegrityError, match="STAGE_A_CODE_BUNDLE_MISMATCH"
    ):
        verify_stage_a_freeze_receipt(
            _tamper(scientific_code_bundle_sha256="4" * 64),
            execution_plan=plan_model,
            prompt_freeze=freeze_model,
            authorization=auth_model,
            candidate_registry=cand_reg,
            repo_root=REPO_ROOT,
            require_git_committed=False,
        )

    # 8. Wrong provider-config registry SHA
    with pytest.raises(
        CandidateRegistryIntegrityError,
        match="STAGE_A_PROVIDER_CONFIG_MISMATCH",
    ):
        verify_stage_a_freeze_receipt(
            _tamper(provider_config_registry_sha256="5" * 64),
            execution_plan=plan_model,
            prompt_freeze=freeze_model,
            authorization=auth_model,
            candidate_registry=cand_reg,
            repo_root=REPO_ROOT,
            require_git_committed=False,
        )

    # 9. Wrong code_basis_commit_sha
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="STAGE_A_CODE_BASIS_MISMATCH"
    ):
        verify_stage_a_freeze_receipt(
            _tamper(code_basis_commit_sha="b" * 40),
            execution_plan=plan_model,
            prompt_freeze=freeze_model,
            authorization=auth_model,
            candidate_registry=cand_reg,
            repo_root=REPO_ROOT,
            require_git_committed=False,
        )

    # 10. Wrong stage_a_commit_sha
    p10 = tmp_path / "bad_commit_stage_a.json"
    p10.write_bytes(canonical_json_bytes(_tamper(stage_a_commit_sha="a" * 40)))
    with pytest.raises(PlanBeforeLiveProtocolError):
        verify_stage_a_freeze_receipt(
            p10,
            execution_plan=plan_model,
            prompt_freeze=freeze_model,
            authorization=auth_model,
            execution_plan_path=REPO_ROOT / dsa_mod.DEV_SELECT_PLAN_REL_PATH,
            prompt_freeze_path=REPO_ROOT / dsa_mod.PROMPT_FREEZE_REL_PATH,
            authorization_path=REPO_ROOT / dsa_mod.AUTHORIZATION_REL_PATH,
            candidate_registry=cand_reg,
            repo_root=REPO_ROOT,
            require_git_committed=True,
        )

    # 11. Missing or blank process token
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="STAGE_A_PROCESS_TOKEN_EMPTY"
    ):
        DevLiveStageAFreezeReceipt.model_validate(_tamper(stage_a_process_token="   "))

    # 12. Same-process execution attempt rejected
    same_proc = _build_stage_a_freeze_receipt_with_token(
        execution_plan=plan_model,
        prompt_freeze=freeze_model,
        authorization=auth_model,
        stage_a_commit_sha=dsa_mod.STAGE_A_COMMIT_SHA,
        freeze_created_at_utc=persisted.freeze_created_at_utc,
        stage_a_process_token=_CURRENT_PROCESS_INVOCATION_TOKEN,
        candidate_registry=cand_reg,
    )
    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="STAGE_A_AND_STAGE_B_SAME_PROCESS_FORBIDDEN",
    ):
        verify_stage_a_freeze_receipt(
            same_proc,
            execution_plan=plan_model,
            prompt_freeze=freeze_model,
            authorization=auth_model,
            candidate_registry=cand_reg,
            repo_root=REPO_ROOT,
            require_git_committed=False,
        )

    # 13, 14, 15. 179/181 run IDs, duplicate run IDs, reordered run IDs
    for bad_ids in (
        persisted.assigned_cell_run_ids[:179],
        [*persisted.assigned_cell_run_ids, "W06-DEV-SELECT-EXTRA-181"],
        list(reversed(persisted.assigned_cell_run_ids)),
    ):
        with pytest.raises(
            PlanBeforeLiveProtocolError, match="STAGE_A_ASSIGNED_CELLS_MISMATCH"
        ):
            verify_stage_a_freeze_receipt(
                _tamper(assigned_cell_run_ids=bad_ids),
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
                authorization=auth_model,
                candidate_registry=cand_reg,
                repo_root=REPO_ROOT,
                require_git_committed=False,
            )

    dup_ids = list(persisted.assigned_cell_run_ids)
    dup_ids[-1] = dup_ids[0]
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="STAGE_A_RECEIPT_CELLS_INVALID"
    ):
        DevLiveStageAFreezeReceipt.model_validate(
            _tamper(assigned_cell_run_ids=dup_ids)
        )

    # 16. Tampered assigned_cells_sha256
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="STAGE_A_ASSIGNED_CELLS_MISMATCH"
    ):
        verify_stage_a_freeze_receipt(
            _tamper(assigned_cells_sha256="c" * 64),
            execution_plan=plan_model,
            prompt_freeze=freeze_model,
            authorization=auth_model,
            candidate_registry=cand_reg,
            repo_root=REPO_ROOT,
            require_git_committed=False,
        )

    # 17. Tampered stage_a_receipt_sha256
    bad_sha_dict = dict(base)
    bad_sha_dict["stage_a_receipt_sha256"] = "d" * 64
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="STAGE_A_RECEIPT_SHA256_MISMATCH"
    ):
        DevLiveStageAFreezeReceipt.model_validate(bad_sha_dict)

    # 23. Missing path arguments when require_git_committed=True
    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="STAGE_A_PATHS_REQUIRED_FOR_GIT_ATTESTATION",
    ):
        verify_stage_a_freeze_receipt(
            stage_a_path,
            execution_plan=plan_model,
            prompt_freeze=freeze_model,
            authorization=auth_model,
            execution_plan_path=None,
            prompt_freeze_path=REPO_ROOT / dsa_mod.PROMPT_FREEZE_REL_PATH,
            authorization_path=REPO_ROOT / dsa_mod.AUTHORIZATION_REL_PATH,
            candidate_registry=cand_reg,
            repo_root=REPO_ROOT,
            require_git_committed=True,
        )

    # 24. Synthetic unknown/tampered Stage-A file rejected by downstream verifier and historical firewalls
    w06_tmp = tmp_path / "data" / "evaluation" / "w06"
    w06_tmp.mkdir(parents=True)
    fake_sa = w06_tmp / "w06_dev_select_stage_a_freeze_receipt_v1.json"
    fake_sa.write_text(
        json.dumps(
            {
                "artifact_id": STAGE_A_FREEZE_RECEIPT_ARTIFACT_ID,
                "task_id": dsa_mod.TASK_ID,
                "phase": "DEV_SELECT",
            }
        ),
        encoding="utf-8",
    )
    assert (
        dsa_mod.is_verified_downstream_w06_dev_select_stage_a_file(
            fake_sa, repo_root=REPO_ROOT
        )
        is False
    )
    fw_prep = ds_prep_mod.verify_pre_authorization_firewall(tmp_path)
    assert fw_prep["pre_authorization_firewall_intact"] is False
    assert (
        "data/evaluation/w06/w06_dev_select_stage_a_freeze_receipt_v1.json"
        in fw_prep["forbidden_dev_select_stage_a_files"]
    )
    fw_auth = ds_auth_mod.verify_pre_stage_a_firewall(tmp_path)
    assert fw_auth["stage_a_created"] is True
    assert (
        "data/evaluation/w06/w06_dev_select_stage_a_freeze_receipt_v1.json"
        in fw_auth["forbidden_dev_select_stage_a_files"]
    )

    # 27. P2 cell injection into DEV-SELECT plan
    p2_plan_dict = plan_model.model_dump()
    p2_plan_dict["cells"][0]["prompt_id"] = "P2"
    with pytest.raises(Exception):
        bad_p2_plan = DevExecutionPlan.model_validate(p2_plan_dict)
        verify_dev_execution_plan_for_execution(
            bad_p2_plan, candidate_registry=cand_reg, repo_root=REPO_ROOT
        )


def test_network_kill_switch_blocks_socket_urllib_httpx_and_httpx2() -> None:
    """Verify NetworkKillSwitchGuard blocks outbound socket, urllib, httpx, and httpx2 calls."""
    assert httpx2.__name__ == "httpx2"
    assert httpx2 is not httpx
    guard = dsa_mod.NetworkKillSwitchGuard()
    with guard.activate():
        with pytest.raises(dsa_mod.OutboundNetworkBlockedError):
            with httpx2.Client() as c2:
                c2.get("https://example.com")
        with pytest.raises(dsa_mod.OutboundNetworkBlockedError):
            with httpx.Client() as c1:
                c1.get("https://example.com")
        with pytest.raises(dsa_mod.OutboundNetworkBlockedError):
            urllib.request.urlopen("https://example.com")
        with pytest.raises(dsa_mod.OutboundNetworkBlockedError):
            s = socket.socket()
            try:
                s.connect(("127.0.0.1", 9))
            finally:
                s.close()
    assert len(guard.blocked_attempts) == 4


def test_separate_process_b_cli_verification_is_read_only() -> None:
    """Invoke freeze_w06_dev_select_stage_a.py --verify-committed in a separate subprocess and verify read-only PASS."""
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "freeze_w06_dev_select_stage_a.py"),
            "--verify-committed",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"Process B failed: {proc.stderr}\n{proc.stdout}"
    payload = json.loads(proc.stdout)
    assert payload["process_b_read_only"] is True
    assert payload["separate_process_committed_verification_passed"] is True
    assert (
        payload["stage_a_receipt_sha256"]
        == dsa_mod.EXPECTED_STAGE_A_RECEIPT_INTERNAL_SHA256
    )
    assert (
        payload["stage_a_receipt_file_sha256"]
        == dsa_mod.EXPECTED_STAGE_A_RECEIPT_FILE_SHA256
    )
    assert (
        payload["task_audit_receipt_file_sha256"]
        == dsa_mod.EXPECTED_TASK_AUDIT_RECEIPT_FILE_SHA256
    )
    assert payload["assigned_cell_count"] == 180
    assert payload["dsa_checks"] == "40/40 PASS"
    assert payload["adversarial_checks"] == "27/27 PASS"
    assert payload["live_provider_calls_new"] == 0
    assert payload["provider_cost_usd_new"] == 0


def test_report_markdown_contains_all_required_hashes() -> None:
    """Verify docs/research/w06_dev_select_stage_a_freeze_01.md contains all required hashes and metadata."""
    report_path = REPO_ROOT / dsa_mod.REPORT_MD_REL_PATH
    assert report_path.is_file()
    text = report_path.read_text(encoding="utf-8")

    stage_a_file_sha = hashlib.sha256(
        normalize_lf_bytes((REPO_ROOT / dsa_mod.STAGE_A_RECEIPT_REL_PATH).read_bytes())
    ).hexdigest()
    audit_file_sha = hashlib.sha256(
        normalize_lf_bytes(
            (REPO_ROOT / dsa_mod.TASK_AUDIT_RECEIPT_REL_PATH).read_bytes()
        )
    ).hexdigest()

    required_substrings = [
        "W06-DEV-SELECT-STAGE-A-FREEZE-01",
        "W06-DEV-LIVE-STAGE-A-FREEZE-RECEIPT-V1",
        "W06-DEV-SELECT-STAGE-A-FREEZE-01-RECEIPT-V1",
        "e69b7d70c3908d2b888b7c5d7e6c4e1d49fac863",
        "c0adf74ceda9ffaf8b4ec42d299932e33f448e6a",
        "de04255989a9e3bd8c2e39c766432487dce4ccd0612d5dba73b3476cbc9d0c6d",
        "c519baf7cd2557b5e1dd2699a5ceaec592af015d7bc6dcc83abf63892a8a329a",
        "5f32782f6359f409c7dd68f08699218cd577cb48bcb517f14c15939f896b9549",
        "2f345363f580ea882b2e5b3562c587ef5309bc7f994440257a54d18994ab6956",
        "096ff4c74dd8d1aed1c0abe501b97c8dfd0f6424dbca535f2b79a242637a1c11",
        "247c0f201d8b900a1e0356d874891ba6e2884138b1ddd8500dfedb663f04f5f7",
        "31cebcf5aafa7a575d4bf1327fc9d454a2817c2acbbdb2c087d8c1210e8ec504",
        "0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3",
        "4dd29164afdf7f364978420f41ab88ef07ec396062188169fcb859a9ef01e058",
        "3dc05d29acc2f647cba58303865bd7406b8c1d9f7ccbe0f120e87ad471190938",
        dsa_mod.EXPECTED_STAGE_A_FREEZE_CREATED_AT_UTC,
        dsa_mod.EXPECTED_STAGE_A_RECEIPT_INTERNAL_SHA256,
        stage_a_file_sha,
        audit_file_sha,
    ]
    for sub in required_substrings:
        assert sub in text, f"Missing required substring in report: {sub!r}"


def test_source_develop_provenance_fail_closed_and_shallow_ci_fallback() -> None:
    """Verify fail-closed source develop provenance check for e69b7d70c3908d2b888b7c5d7e6c4e1d49fac863."""
    real_res = dsa_mod.verify_source_develop_commit_or_shallow_fallback(REPO_ROOT)
    assert real_res["verified"] is True

    # Commit exists in local git but is NOT ancestor -> fails closed
    def _git_non_ancestor(args: list[str]) -> subprocess.CompletedProcess[str]:
        if "cat-file" in args:
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        if "merge-base" in args:
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="")
        return subprocess.CompletedProcess(args, 0, stdout="false\n", stderr="")

    bad_anc = dsa_mod.verify_source_develop_commit_or_shallow_fallback(
        REPO_ROOT, git_runner=_git_non_ancestor
    )
    assert bad_anc["verified"] is False

    # Non-shallow repo missing commit -> fails closed
    def _git_non_shallow_missing(args: list[str]) -> subprocess.CompletedProcess[str]:
        if "cat-file" in args:
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="missing")
        if "--is-shallow-repository" in args:
            return subprocess.CompletedProcess(args, 0, stdout="false\n", stderr="")
        return subprocess.CompletedProcess(args, 1, stdout="", stderr="")

    non_shallow_missing = dsa_mod.verify_source_develop_commit_or_shallow_fallback(
        REPO_ROOT, git_runner=_git_non_shallow_missing
    )
    assert non_shallow_missing["verified"] is False

    # Shallow repo with all frozen fallback authorities matching -> passes
    def _git_shallow(args: list[str]) -> subprocess.CompletedProcess[str]:
        if "cat-file" in args:
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="missing")
        if "--is-shallow-repository" in args:
            return subprocess.CompletedProcess(args, 0, stdout="true\n", stderr="")
        return subprocess.CompletedProcess(args, 1, stdout="", stderr="")

    shallow_ok = dsa_mod.verify_source_develop_commit_or_shallow_fallback(
        REPO_ROOT, git_runner=_git_shallow
    )
    assert shallow_ok["verified"] is True
    assert shallow_ok["shallow_repository_fallback_used"] is True


def test_downstream_verifier_has_no_positive_cache_and_reloads_authorities_each_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Section 2 & 5: Verify _CACHED_CANONICAL_STAGE_A_AUTHORITIES is removed and load_verified_stage_a_authorities is called on every invocation."""
    assert not hasattr(dsa_mod, "_CACHED_CANONICAL_STAGE_A_AUTHORITIES")

    orig_loader = dsa_mod.load_verified_stage_a_authorities
    call_count = 0

    def _wrapped_loader(repo_root: Path = REPO_ROOT) -> dict[str, object]:
        nonlocal call_count
        call_count += 1
        return orig_loader(repo_root)

    monkeypatch.setattr(
        dsa_mod, "load_verified_stage_a_authorities", _wrapped_loader
    )

    stage_a_path = REPO_ROOT / dsa_mod.STAGE_A_RECEIPT_REL_PATH
    assert (
        dsa_mod.is_verified_downstream_w06_dev_select_stage_a_freeze_receipt(
            stage_a_path, repo_root=REPO_ROOT
        )
        is True
    )
    assert (
        dsa_mod.is_verified_downstream_w06_dev_select_stage_a_freeze_receipt(
            stage_a_path, repo_root=REPO_ROOT
        )
        is True
    )
    assert call_count == 2


def test_saa_stat_01_to_04_same_process_upstream_tamper_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sections 3, 4, 6, 7: Prove stateless same-process fail-closed behavior across SAA-STAT-01..04, task-audit verifier, and historical firewalls."""
    stage_a_path = REPO_ROOT / dsa_mod.STAGE_A_RECEIPT_REL_PATH
    audit_path = REPO_ROOT / dsa_mod.TASK_AUDIT_RECEIPT_REL_PATH
    orig_read_bytes = Path.read_bytes
    tampered_rel_paths: set[str] = set()

    def _tampering_read_bytes(self: Path) -> bytes:
        raw = orig_read_bytes(self)
        try:
            rel = self.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
        except Exception:
            rel = ""
        if rel in tampered_rel_paths:
            return raw + b"\n"
        return raw

    monkeypatch.setattr(Path, "read_bytes", _tampering_read_bytes)

    def _assert_stateless_tamper_cycle(target_rel_path: str) -> None:
        try:
            # A. Verify legitimate downstream Stage-A receipt, task-audit receipt, and historical firewalls => True / clean
            assert (
                dsa_mod.is_verified_downstream_w06_dev_select_stage_a_freeze_receipt(
                    stage_a_path, repo_root=REPO_ROOT
                )
                is True
            )
            assert (
                dsa_mod.is_verified_downstream_w06_dev_select_stage_a_task_audit_receipt(
                    audit_path, repo_root=REPO_ROOT
                )
                is True
            )
            assert (
                dsa_mod.is_verified_downstream_w06_dev_select_stage_a_file(
                    stage_a_path, repo_root=REPO_ROOT
                )
                is True
            )
            assert (
                dsa_mod.is_verified_downstream_w06_dev_select_stage_a_file(
                    audit_path, repo_root=REPO_ROOT
                )
                is True
            )
            fw_auth_clean = ds_auth_mod.verify_pre_stage_a_firewall(REPO_ROOT)
            assert fw_auth_clean["stage_a_created"] is False
            fw_prep_clean = ds_prep_mod.verify_pre_authorization_firewall(REPO_ROOT)
            assert fw_prep_clean["dev_select_stage_a_receipt_created"] is False

            # B. WITHOUT restarting Python process, tamper the upstream authority read from disk
            tampered_rel_paths.add(target_rel_path)

            # C & D. Call the same downstream verifiers and historical firewalls again => require False / fail closed
            assert (
                dsa_mod.is_verified_downstream_w06_dev_select_stage_a_freeze_receipt(
                    stage_a_path, repo_root=REPO_ROOT
                )
                is False
            )
            assert (
                dsa_mod.is_verified_downstream_w06_dev_select_stage_a_task_audit_receipt(
                    audit_path, repo_root=REPO_ROOT
                )
                is False
            )
            assert (
                dsa_mod.is_verified_downstream_w06_dev_select_stage_a_file(
                    stage_a_path, repo_root=REPO_ROOT
                )
                is False
            )
            assert (
                dsa_mod.is_verified_downstream_w06_dev_select_stage_a_file(
                    audit_path, repo_root=REPO_ROOT
                )
                is False
            )
            fw_auth_tampered = ds_auth_mod.verify_pre_stage_a_firewall(REPO_ROOT)
            assert fw_auth_tampered["stage_a_created"] is True
            assert (
                dsa_mod.STAGE_A_RECEIPT_REL_PATH
                in fw_auth_tampered["forbidden_dev_select_stage_a_files"]
            )
            fw_prep_tampered = ds_prep_mod.verify_pre_authorization_firewall(REPO_ROOT)
            assert fw_prep_tampered["dev_select_stage_a_receipt_created"] is True
            assert (
                dsa_mod.STAGE_A_RECEIPT_REL_PATH
                in fw_prep_tampered["forbidden_dev_select_stage_a_files"]
            )
        finally:
            # E. Restore exact bytes
            tampered_rel_paths.discard(target_rel_path)

        # F. Verify again => True / clean
        assert (
            dsa_mod.is_verified_downstream_w06_dev_select_stage_a_freeze_receipt(
                stage_a_path, repo_root=REPO_ROOT
            )
            is True
        )
        assert (
            dsa_mod.is_verified_downstream_w06_dev_select_stage_a_task_audit_receipt(
                audit_path, repo_root=REPO_ROOT
            )
            is True
        )
        assert (
            dsa_mod.is_verified_downstream_w06_dev_select_stage_a_file(
                stage_a_path, repo_root=REPO_ROOT
            )
            is True
        )
        assert (
            dsa_mod.is_verified_downstream_w06_dev_select_stage_a_file(
                audit_path, repo_root=REPO_ROOT
            )
            is True
        )

    # SAA-STAT-01: execution plan bytes tampered after first successful verification
    _assert_stateless_tamper_cycle(dsa_mod.DEV_SELECT_PLAN_REL_PATH)

    # SAA-STAT-02: prompt-freeze bytes tampered after first successful verification
    _assert_stateless_tamper_cycle(dsa_mod.PROMPT_FREEZE_REL_PATH)

    # SAA-STAT-03: live authorization bytes tampered after first successful verification
    _assert_stateless_tamper_cycle(dsa_mod.AUTHORIZATION_REL_PATH)

    # SAA-STAT-04: scientific bundle authority tampered after first successful verification
    _assert_stateless_tamper_cycle(
        "apps/ai-service/app/evaluation/dev_live_runner.py"
    )
