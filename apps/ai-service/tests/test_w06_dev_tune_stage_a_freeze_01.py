"""Pytest suite for W06-DEV-TUNE-STAGE-A-FREEZE-01.

Verifies SA-01 through SA-40, SAA-01 through SAA-15, production
DevLiveStageAFreezeReceipt contract validation, same-process barrier,
separate-process committed verification, git/blob attestation, historical
gate cryptographic Stage-A verification, and offline/no-capability firewalls.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys

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
    canonical_json_bytes,
    normalize_lf_bytes,
    sha256_bytes,
)
import freeze_w06_dev_tune_stage_a as sa_mod  # noqa: E402
import issue_w06_dev_tune_live_authorization as auth_mod  # noqa: E402
import prepare_w06_dev_tune_authorization as prep_mod  # noqa: E402


def test_all_40_sa_checks_pass() -> None:
    """Verify SA-01 through SA-40 all pass against the repository and committed Stage-A receipt."""
    checks = sa_mod.run_all_sa_checks(REPO_ROOT, require_committed_in_head=True)
    assert len(checks) == 40
    expected_ids = [f"SA-{i:02d}" for i in range(1, 41)]
    assert [c["check_id"] for c in checks] == expected_ids

    failed = [c for c in checks if c["status"] != "PASS"]
    assert not failed, f"Failed SA checks: {failed}"


@pytest.mark.parametrize("check_idx", range(1, 41))
def test_individual_sa_check_in_persisted_receipt(check_idx: int) -> None:
    """Verify each SA-01..SA-40 check recorded in w06_dev_tune_stage_a_freeze_01_receipt_v1.json is PASS."""
    receipt_path = REPO_ROOT / sa_mod.TASK_AUDIT_RECEIPT_REL_PATH
    data = json.loads(receipt_path.read_text(encoding="utf-8"))
    check_id = f"SA-{check_idx:02d}"
    matching = [c for c in data["checks"] if c["check_id"] == check_id]
    assert len(matching) == 1
    assert matching[0]["status"] == "PASS"


def test_all_15_saa_adversarial_checks_pass() -> None:
    """Verify SAA-01 through SAA-15 adversarial checks all pass."""
    saa_checks = sa_mod.run_all_saa_adversarial_checks(REPO_ROOT)
    assert len(saa_checks) == 15
    expected_ids = [f"SAA-{i:02d}" for i in range(1, 16)]
    assert [c["check_id"] for c in saa_checks] == expected_ids

    failed = [c for c in saa_checks if c["status"] != "PASS"]
    assert not failed, f"Failed SAA checks: {failed}"


@pytest.mark.parametrize("saa_idx", range(1, 16))
def test_individual_saa_check_in_persisted_receipt(saa_idx: int) -> None:
    """Verify each SAA-01..SAA-15 adversarial check recorded in w06_dev_tune_stage_a_freeze_01_receipt_v1.json is PASS."""
    receipt_path = REPO_ROOT / sa_mod.TASK_AUDIT_RECEIPT_REL_PATH
    data = json.loads(receipt_path.read_text(encoding="utf-8"))
    check_id = f"SAA-{saa_idx:02d}"
    matching = [
        c for c in data["adversarial_checks"] if c["check_id"] == check_id
    ]
    assert len(matching) == 1
    assert matching[0]["status"] == "PASS"


def test_persisted_stage_a_receipt_and_task_audit_receipt_integrity() -> None:
    """Verify persisted Stage-A receipt and task audit receipt match production contract and hashes."""
    stage_a_path = REPO_ROOT / sa_mod.STAGE_A_RECEIPT_REL_PATH
    audit_path = REPO_ROOT / sa_mod.TASK_AUDIT_RECEIPT_REL_PATH

    stage_a_raw = stage_a_path.read_bytes()
    audit_raw = audit_path.read_bytes()
    assert b"\r\n" not in stage_a_raw
    assert b"\r\n" not in audit_raw

    stage_a_file_sha = sha256_bytes(normalize_lf_bytes(stage_a_raw))
    assert stage_a_file_sha == sa_mod.EXPECTED_STAGE_A_RECEIPT_FILE_SHA256

    stage_a_dict = json.loads(stage_a_raw.decode("utf-8"))
    audit_dict = json.loads(audit_raw.decode("utf-8"))

    assert_no_secrets_in_payload(stage_a_dict, context="TEST_PERSISTED_STAGE_A")
    assert_no_secrets_in_payload(audit_dict, context="TEST_PERSISTED_STAGE_A_AUDIT")

    auths = sa_mod.load_verified_stage_a_authorities(REPO_ROOT)
    validated_stage_a = verify_stage_a_freeze_receipt(
        stage_a_path,
        execution_plan=auths["execution_plan"],
        prompt_freeze=auths["prompt_freeze"],
        authorization=auths["authorization"],
        execution_plan_path=REPO_ROOT / sa_mod.DEV_TUNE_PLAN_REL_PATH,
        prompt_freeze_path=REPO_ROOT / sa_mod.PROMPT_FREEZE_REL_PATH,
        authorization_path=REPO_ROOT / sa_mod.AUTHORIZATION_REL_PATH,
        candidate_registry=auths["candidate_registry"],
        repo_root=REPO_ROOT,
        require_git_committed=True,
    )
    assert isinstance(validated_stage_a, DevLiveStageAFreezeReceipt)
    assert validated_stage_a.artifact_id == STAGE_A_FREEZE_RECEIPT_ARTIFACT_ID
    assert validated_stage_a.phase == "DEV_TUNE"
    assert (
        validated_stage_a.execution_plan_sha256
        == "582d9964b4fffbac91f83373d080f1fef120f0ddca4edab2d63e02796d0b20ae"
    )
    assert (
        validated_stage_a.prompt_freeze_sha256
        == "2f345363f580ea882b2e5b3562c587ef5309bc7f994440257a54d18994ab6956"
    )
    assert (
        validated_stage_a.authorization_artifact_sha256
        == "fb2c181e14b0b122100f7b3b386bdaeaffe467c913d384db16717149374a1c83"
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
        == "60d52d720e66f5af8e82fabf9cebe2ea0e8a9e26"
    )
    assert (
        validated_stage_a.stage_a_commit_sha
        == "25c81ad0e03b2d7e0b0cd29550a2d72b18d6e32e"
    )
    assert validated_stage_a.stage_a_status == STAGE_A_STATUS_FROZEN_BEFORE_LIVE
    assert len(validated_stage_a.assigned_cell_run_ids) == 120
    expected_run_ids, expected_cells_sha = compute_assigned_cells_sha256(
        auths["execution_plan"]
    )
    assert validated_stage_a.assigned_cell_run_ids == expected_run_ids
    assert validated_stage_a.assigned_cells_sha256 == expected_cells_sha
    assert (
        validated_stage_a.stage_a_receipt_sha256
        == sa_mod.EXPECTED_STAGE_A_RECEIPT_INTERNAL_SHA256
    )

    assert audit_dict["task"] == "W06-DEV-TUNE-STAGE-A-FREEZE-01"
    assert audit_dict["stage_a_receipt_file_sha256"] == stage_a_file_sha
    assert (
        audit_dict["stage_a_receipt_sha256"]
        == validated_stage_a.stage_a_receipt_sha256
    )
    assert audit_dict["same_process_execution_blocked"] is True
    assert audit_dict["separate_process_committed_verification_passed"] is True
    assert audit_dict["live_execution_capability_minted"] is False
    assert audit_dict["production_provider_transport_constructed"] is False
    assert audit_dict["live_provider_calls"] == 0
    assert audit_dict["provider_cost_usd"] == 0.0
    assert audit_dict["dev_tune_execution_started"] is False
    assert audit_dict["dev_select_execution_started"] is False
    assert audit_dict["stochasticity_execution_started"] is False
    assert audit_dict["final100_used"] is False


def test_process_a_refuses_to_overwrite_existing_stage_a_receipt() -> None:
    """Verify Process A (--generate-stage-a-once) refuses to overwrite the existing Stage-A receipt."""
    stage_a_path = REPO_ROOT / sa_mod.STAGE_A_RECEIPT_REL_PATH
    before_bytes = stage_a_path.read_bytes()
    with pytest.raises(RuntimeError, match="STAGE_A_RECEIPT_ALREADY_EXISTS"):
        sa_mod.generate_stage_a_receipt_once_process_a(REPO_ROOT)
    assert stage_a_path.read_bytes() == before_bytes


def test_adversarial_stage_a_tampering_and_same_process_barrier(
    tmp_path: Path,
) -> None:
    """Directly test all adversarial Stage-A rejection conditions required in Section 21."""
    auths = sa_mod.load_verified_stage_a_authorities(REPO_ROOT)
    plan_model = auths["execution_plan"]
    freeze_model = auths["prompt_freeze"]
    auth_model = auths["authorization"]
    cand_reg = auths["candidate_registry"]

    stage_a_path = REPO_ROOT / sa_mod.STAGE_A_RECEIPT_REL_PATH
    persisted = DevLiveStageAFreezeReceipt.model_validate_json(
        stage_a_path.read_bytes()
    )
    base = persisted.model_dump(exclude={"stage_a_receipt_sha256"})
    base["stage_a_process_token"] = "pid-77777-ns-123"

    def _tamper(**overrides: object) -> dict[str, object]:
        d = dict(base)
        d.update(overrides)
        d["stage_a_receipt_sha256"] = sha256_bytes(canonical_json_bytes(d))
        return d

    # 1. Wrong plan SHA
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

    # 2. Wrong prompt freeze SHA
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

    # 3. Wrong authorization SHA
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

    # 4. Wrong scientific bundle SHA
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

    # 5. Wrong provider-config registry SHA
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

    # 6. Wrong code_basis_commit_sha
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

    # 7. Missing/empty process token
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="STAGE_A_PROCESS_TOKEN_EMPTY"
    ):
        DevLiveStageAFreezeReceipt.model_validate(
            _tamper(stage_a_process_token="")
        )

    # 8. 121-cell / tampered assigned run list
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="STAGE_A_ASSIGNED_CELLS_MISMATCH"
    ):
        verify_stage_a_freeze_receipt(
            _tamper(
                assigned_cell_run_ids=[
                    *persisted.assigned_cell_run_ids,
                    "W06-DEV-TUNE-EXTRA-121",
                ]
            ),
            execution_plan=plan_model,
            prompt_freeze=freeze_model,
            authorization=auth_model,
            candidate_registry=cand_reg,
            repo_root=REPO_ROOT,
            require_git_committed=False,
        )

    # 9. Tampered assigned_cells_sha256
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

    # 10. Same-process execution attempt rejected
    same_proc = _build_stage_a_freeze_receipt_with_token(
        execution_plan=plan_model,
        prompt_freeze=freeze_model,
        authorization=auth_model,
        stage_a_commit_sha=sa_mod.STAGE_A_COMMIT_SHA,
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

    # 11. Fake Stage-A filename-only artifact rejected by downstream verifier and historical gates
    w06_tmp = tmp_path / "data" / "evaluation" / "w06"
    w06_tmp.mkdir(parents=True)
    fake_sa = w06_tmp / "w06_dev_tune_stage_a_freeze_receipt_v1.json"
    fake_sa.write_text(
        json.dumps(
            {
                "artifact_id": STAGE_A_FREEZE_RECEIPT_ARTIFACT_ID,
                "task_id": sa_mod.TASK_ID,
                "phase": "DEV_TUNE",
            }
        ),
        encoding="utf-8",
    )
    assert (
        sa_mod.is_verified_downstream_w06_dev_tune_stage_a_file(
            fake_sa, repo_root=REPO_ROOT
        )
        is False
    )
    fw_prep = prep_mod.verify_pre_authorization_firewall(tmp_path)
    assert fw_prep["pre_authorization_firewall_intact"] is False
    assert (
        "data/evaluation/w06/w06_dev_tune_stage_a_freeze_receipt_v1.json"
        in fw_prep["forbidden_stage_a_files"]
    )
    fw_auth = auth_mod.verify_pre_stage_a_firewall(tmp_path)
    assert fw_auth["stage_a_created"] is True
    assert (
        "data/evaluation/w06/w06_dev_tune_stage_a_freeze_receipt_v1.json"
        in fw_auth["forbidden_stage_a_files"]
    )


def test_network_kill_switch_and_final100_firewall() -> None:
    """Verify NetworkKillSwitchGuard blocks outbound sockets and Final100 paths are rejected."""
    guard = sa_mod.NetworkKillSwitchGuard()
    with guard.activate():
        with pytest.raises(
            sa_mod.OutboundNetworkBlockedError,
            match="OFFLINE_NETWORK_KILL_SWITCH_TRIGGERED",
        ):
            socket.create_connection(("example.com", 443), timeout=0.1)
    assert len(guard.blocked_attempts) == 1

    auths = sa_mod.load_verified_stage_a_authorities(REPO_ROOT)
    with pytest.raises(
        Final100FirewallViolationError, match="FINAL100_FIREWALL_VIOLATION"
    ):
        verify_stage_a_freeze_receipt(
            REPO_ROOT / "data/evaluation/w06/w06_scenarios_freeze_v1.json",
            execution_plan=auths["execution_plan"],
            prompt_freeze=auths["prompt_freeze"],
            authorization=auths["authorization"],
            candidate_registry=auths["candidate_registry"],
            repo_root=REPO_ROOT,
            require_git_committed=False,
        )


def test_separate_process_b_cli_verification_is_read_only() -> None:
    """Invoke freeze_w06_dev_tune_stage_a.py --verify-committed in a separate subprocess and verify read-only PASS."""
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "freeze_w06_dev_tune_stage_a.py"),
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
        == sa_mod.EXPECTED_STAGE_A_RECEIPT_INTERNAL_SHA256
    )
    assert (
        payload["stage_a_receipt_file_sha256"]
        == sa_mod.EXPECTED_STAGE_A_RECEIPT_FILE_SHA256
    )
    assert payload["sa_checks"] == "40/40 PASS"
    assert payload["saa_checks"] == "15/15 PASS"
    assert payload["live_provider_calls"] == 0
    assert payload["provider_cost_usd"] == 0.0


def test_report_markdown_contains_all_required_hashes() -> None:
    """Verify docs/research/w06_dev_tune_stage_a_freeze_01.md contains all required hashes and metadata."""
    report_path = REPO_ROOT / sa_mod.REPORT_MD_REL_PATH
    assert report_path.is_file()
    text = report_path.read_text(encoding="utf-8")

    stage_a_file_sha = hashlib.sha256(
        (REPO_ROOT / sa_mod.STAGE_A_RECEIPT_REL_PATH).read_bytes()
    ).hexdigest()
    audit_file_sha = hashlib.sha256(
        (REPO_ROOT / sa_mod.TASK_AUDIT_RECEIPT_REL_PATH).read_bytes()
    ).hexdigest()

    required_substrings = [
        "W06-DEV-TUNE-STAGE-A-FREEZE-01",
        "W06-DEV-LIVE-STAGE-A-FREEZE-RECEIPT-V1",
        "25c81ad0e03b2d7e0b0cd29550a2d72b18d6e32e",
        "60d52d720e66f5af8e82fabf9cebe2ea0e8a9e26",
        "582d9964b4fffbac91f83373d080f1fef120f0ddca4edab2d63e02796d0b20ae",
        "2f345363f580ea882b2e5b3562c587ef5309bc7f994440257a54d18994ab6956",
        "b2c068d216e6a71ad5c193137207cc8f7a74526f9a549eccfaefa9a7bd5eeba4",
        "fb2c181e14b0b122100f7b3b386bdaeaffe467c913d384db16717149374a1c83",
        "0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3",
        "4dd29164afdf7f364978420f41ab88ef07ec396062188169fcb859a9ef01e058",
        "3dc05d29acc2f647cba58303865bd7406b8c1d9f7ccbe0f120e87ad471190938",
        sa_mod.EXPECTED_STAGE_A_FREEZE_CREATED_AT_UTC,
        sa_mod.EXPECTED_STAGE_A_RECEIPT_INTERNAL_SHA256,
        stage_a_file_sha,
        audit_file_sha,
    ]
    for sub in required_substrings:
        assert sub in text, f"Missing required substring in report: {sub!r}"
