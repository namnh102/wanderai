"""Pytest suite for W06-DEV-TUNE-LIVE-AUTHORIZATION-01.

Verifies AU-01 through AU-30, production DevLiveAuthorizationArtifact contract
validation, adversarial rejection of scope widening/tampering, secret safety,
and Pre-Stage-A firewall invariants.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import socket
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "scripts"
AI_SERVICE_DIR = REPO_ROOT / "apps" / "ai-service"
for p in (SCRIPTS_DIR, AI_SERVICE_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from app.evaluation.dev_live_runner import (  # noqa: E402
    DevLiveAuthorizationArtifact,
    DevLiveAuthorizationError,
    assert_no_secrets_in_payload,
    build_dev_live_authorization_artifact,
    verify_dev_live_authorization_artifact,
)
from app.evaluation.dev_selection_harness import (  # noqa: E402
    Final100FirewallViolationError,
    ScientificCodeBundleIntegrityError,
    canonical_json_bytes,
    normalize_lf_bytes,
    sha256_bytes,
)
import issue_w06_dev_tune_live_authorization as auth_mod  # noqa: E402


def test_all_30_au_checks_pass() -> None:
    """Verify AU-01 through AU-30 all pass against the repository and persisted artifact."""
    auth_path = REPO_ROOT / auth_mod.AUTHORIZATION_ARTIFACT_REL_PATH
    assert auth_path.is_file(), f"Missing authorization artifact: {auth_path}"

    checks = auth_mod.run_all_au_checks(REPO_ROOT, auth_artifact_path=auth_path)
    assert len(checks) == 30
    expected_ids = [f"AU-{i:02d}" for i in range(1, 31)]
    assert [c["check_id"] for c in checks] == expected_ids

    failed = [c for c in checks if c["status"] != "PASS"]
    assert not failed, f"Failed AU checks: {failed}"


@pytest.mark.parametrize("check_idx", range(1, 31))
def test_individual_au_check_in_persisted_receipt(check_idx: int) -> None:
    """Verify each AU-01..AU-30 check recorded in w06_dev_tune_live_authorization_01_receipt_v1.json is PASS."""
    receipt_path = REPO_ROOT / auth_mod.AUTHORIZATION_RECEIPT_REL_PATH
    data = json.loads(receipt_path.read_text(encoding="utf-8"))
    check_id = f"AU-{check_idx:02d}"
    matching = [c for c in data["checks"] if c["check_id"] == check_id]
    assert len(matching) == 1
    assert matching[0]["status"] == "PASS"


def test_persisted_authorization_artifact_and_receipt_integrity() -> None:
    """Verify persisted authorization artifact and receipt match production contract and hashes."""
    auth_path = REPO_ROOT / auth_mod.AUTHORIZATION_ARTIFACT_REL_PATH
    receipt_path = REPO_ROOT / auth_mod.AUTHORIZATION_RECEIPT_REL_PATH

    auth_raw = auth_path.read_bytes()
    receipt_raw = receipt_path.read_bytes()
    assert b"\r\n" not in auth_raw
    assert b"\r\n" not in receipt_raw

    auth_file_sha = sha256_bytes(normalize_lf_bytes(auth_raw))
    auth_dict = json.loads(auth_raw.decode("utf-8"))
    receipt_dict = json.loads(receipt_raw.decode("utf-8"))

    assert_no_secrets_in_payload(auth_dict, context="TEST_PERSISTED_AUTH")
    assert_no_secrets_in_payload(receipt_dict, context="TEST_PERSISTED_RECEIPT")

    auths = auth_mod.load_verified_authorities(REPO_ROOT)
    validated_auth = verify_dev_live_authorization_artifact(
        auth_path,
        execution_plan=auths["execution_plan"],
        prompt_freeze=auths["prompt_freeze"],
        expected_phase="DEV_TUNE",
        repo_root=REPO_ROOT,
    )
    assert isinstance(validated_auth, DevLiveAuthorizationArtifact)
    assert validated_auth.task_id == "W06-DEV-TUNE-LIVE-AUTHORIZATION-01"
    assert validated_auth.authorization_id == "W06-DEV-TUNE-LIVE-AUTHORIZATION-01-V1"
    assert validated_auth.authorized_by_role == "PROJECT_OWNER"
    assert validated_auth.authorization_status == "AUTHORIZED"
    assert validated_auth.allowed_phase == "DEV_TUNE"
    assert (
        validated_auth.allowed_execution_plan_sha256
        == "582d9964b4fffbac91f83373d080f1fef120f0ddca4edab2d63e02796d0b20ae"
    )
    assert (
        validated_auth.allowed_prompt_freeze_sha256
        == "2f345363f580ea882b2e5b3562c587ef5309bc7f994440257a54d18994ab6956"
    )
    assert validated_auth.allowed_candidate_ids == ["C1", "C2", "C3"]
    assert validated_auth.maximum_live_generation_calls == 120
    assert (
        validated_auth.scientific_code_bundle_sha256
        == "0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3"
    )

    assert receipt_dict["authorization_artifact_file_sha256"] == auth_file_sha
    assert (
        receipt_dict["authorization_artifact_sha256"]
        == validated_auth.authorization_artifact_sha256
    )
    assert (
        receipt_dict["exact_authorization_text"]
        == auth_mod.EXACT_AUTHORIZATION_TEXT
    )
    assert (
        receipt_dict["authorization_text_sha256"]
        == hashlib.sha256(auth_mod.EXACT_AUTHORIZATION_TEXT.encode("utf-8")).hexdigest()
    )
    assert receipt_dict["stage_a_created"] is False
    assert receipt_dict["live_execution_capability_minted"] is False
    assert receipt_dict["live_provider_calls"] == 0
    assert receipt_dict["provider_cost_usd"] == 0.0
    assert receipt_dict["dev_tune_execution_started"] is False
    assert receipt_dict["dev_select_execution_started"] is False
    assert receipt_dict["stochasticity_execution_started"] is False
    assert receipt_dict["final100_used"] is False


def test_adversarial_authorization_scope_and_tampering_rejections() -> None:
    """Adversarially verify rejection of tampered hashes, extra fields, secrets, and wrong scopes."""
    auths = auth_mod.load_verified_authorities(REPO_ROOT)
    plan_model = auths["execution_plan"]
    freeze_model = auths["prompt_freeze"]
    valid_auth = auth_mod.build_scoped_dev_tune_authorization_artifact(REPO_ROOT)

    # 1. Tampered authorization_artifact_sha256
    tampered = valid_auth.model_dump()
    tampered["authorization_artifact_sha256"] = "a" * 64
    with pytest.raises(
        DevLiveAuthorizationError, match="AUTHORIZATION_ARTIFACT_SHA256_MISMATCH"
    ):
        DevLiveAuthorizationArtifact.model_validate(tampered)

    # 2. Extra unapproved field rejected by ConfigDict(extra="forbid")
    extra_field = valid_auth.model_dump()
    extra_field["self_referential_file_sha256"] = "b" * 64
    with pytest.raises(Exception):
        DevLiveAuthorizationArtifact.model_validate(extra_field)

    # 3. Secret leakage in authorization artifact rejected
    secret_payload = valid_auth.model_dump()
    secret_payload["task_id"] = "sk-ant-api03-1234567890abcdefghijklmnop"
    with pytest.raises(
        DevLiveAuthorizationError, match="AUTHORIZATION_CONTAINS_FORBIDDEN_SECRET"
    ):
        DevLiveAuthorizationArtifact.model_validate(secret_payload)

    # 4. Stale scientific code bundle SHA256 rejected
    stale_bundle = valid_auth.model_dump(exclude={"authorization_artifact_sha256"})
    stale_bundle["scientific_code_bundle_sha256"] = "1" * 64
    stale_bundle["authorization_artifact_sha256"] = sha256_bytes(
        canonical_json_bytes(stale_bundle)
    )
    with pytest.raises(
        ScientificCodeBundleIntegrityError, match="SCIENTIFIC_CODE_BUNDLE_MISMATCH"
    ):
        verify_dev_live_authorization_artifact(
            stale_bundle,
            execution_plan=plan_model,
            prompt_freeze=freeze_model,
            expected_phase="DEV_TUNE",
            repo_root=REPO_ROOT,
        )

    # 5. Final100 phase rejected with Final100FirewallViolationError
    with pytest.raises(
        Final100FirewallViolationError, match="FINAL100_FIREWALL_VIOLATION"
    ):
        build_dev_live_authorization_artifact(
            task_id=auth_mod.TASK_ID,
            authorization_id="BAD-FINAL100",
            authorized_by_role="PROJECT_OWNER",
            authorized_at_utc=auth_mod.AUTHORIZED_AT_UTC,
            authorization_status="AUTHORIZED",
            allowed_phase="FINAL100",
            allowed_candidate_ids=["C1", "C2", "C3"],
            maximum_live_generation_calls=100,
            execution_plan=plan_model,
            prompt_freeze=freeze_model,
        )


def test_network_kill_switch_and_pre_stage_a_firewall(tmp_path: Path) -> None:
    """Verify NetworkKillSwitchGuard blocks outbound sockets and verify_pre_stage_a_firewall detects Stage-A."""
    guard = auth_mod.NetworkKillSwitchGuard()
    with guard.activate():
        with pytest.raises(
            auth_mod.OutboundNetworkBlockedError,
            match="OFFLINE_NETWORK_KILL_SWITCH_TRIGGERED",
        ):
            socket.create_connection(("example.com", 443), timeout=0.1)
    assert len(guard.blocked_attempts) == 1

    w06_dir = tmp_path / "data" / "evaluation" / "w06"
    w06_dir.mkdir(parents=True)
    clean_fw = auth_mod.verify_pre_stage_a_firewall(tmp_path)
    assert clean_fw["stage_a_created"] is False

    (w06_dir / "stage_a_freeze_receipt.json").write_text("{}", encoding="utf-8")
    dirty_fw = auth_mod.verify_pre_stage_a_firewall(tmp_path)
    assert dirty_fw["stage_a_created"] is True


def test_report_markdown_contains_all_required_hashes() -> None:
    """Verify docs/research/w06_dev_tune_live_authorization_01.md contains all required hashes and metadata."""
    report_path = (
        REPO_ROOT / "docs" / "research" / "w06_dev_tune_live_authorization_01.md"
    )
    assert report_path.is_file()
    text = report_path.read_text(encoding="utf-8")

    auth_file_sha = hashlib.sha256(
        (REPO_ROOT / auth_mod.AUTHORIZATION_ARTIFACT_REL_PATH).read_bytes()
    ).hexdigest()
    receipt_file_sha = hashlib.sha256(
        (REPO_ROOT / auth_mod.AUTHORIZATION_RECEIPT_REL_PATH).read_bytes()
    ).hexdigest()

    required_substrings = [
        "W06-DEV-TUNE-LIVE-AUTHORIZATION-01",
        "W06-DEV-TUNE-LIVE-AUTHORIZATION-01-V1",
        "cd9d4e6ae072e737083c9069123f00a5a04107a5",
        "2026-10-21T06:25:00Z",
        auth_mod.EXACT_AUTHORIZATION_TEXT,
        auth_mod.AUTHORIZATION_TEXT_SHA256,
        auth_file_sha,
        receipt_file_sha,
        "582d9964b4fffbac91f83373d080f1fef120f0ddca4edab2d63e02796d0b20ae",
        "2f345363f580ea882b2e5b3562c587ef5309bc7f994440257a54d18994ab6956",
        "0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3",
    ]
    for sub in required_substrings:
        assert sub in text, f"Missing required substring in report: {sub!r}"
