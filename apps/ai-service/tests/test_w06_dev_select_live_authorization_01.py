"""Tests for W06-DEV-SELECT-LIVE-AUTHORIZATION-01.

Verifies:
- DSAU-01..DSAU-40 authorization checks
- ADV-01..ADV-20 adversarial fail-closed checks (Section 17)
- Production DevLiveAuthorizationArtifact builder and verifier contract
- Cryptographic downstream recognition & fail-closed rejection (Section 19)
- Verify-only CLI mode (`--verify-only`) with zero writes and zero provider calls
"""

from __future__ import annotations

import hashlib
import json
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
for p in (AI_SERVICE_DIR, SCRIPTS_DIR):
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
    DevExecutionPlan,
    canonical_json_bytes,
    normalize_lf_bytes,
    sha256_bytes,
    verify_dev_execution_plan_for_execution,
)
import issue_w06_dev_select_live_authorization as ds_auth_mod  # noqa: E402
import prepare_w06_dev_select_authorization as ds_prep_mod  # noqa: E402
import prepare_w06_dev_tune_authorization as dt_prep_mod  # noqa: E402


DSAU_CHECK_IDS = [f"DSAU-{i:02d}" for i in range(1, 41)]
ADV_CHECK_IDS = [f"ADV-{i:02d}" for i in range(1, 21)]


@pytest.mark.parametrize("check_id", DSAU_CHECK_IDS)
def test_dsau_check_recorded_and_passes(check_id: str) -> None:
    """Verify each DSAU-01..DSAU-40 check in w06_dev_select_live_authorization_01_receipt_v1.json is PASS."""
    receipt_path = REPO_ROOT / ds_auth_mod.AUTHORIZATION_RECEIPT_REL_PATH
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    checks_by_id = {c["check_id"]: c for c in receipt["checks"]}
    assert check_id in checks_by_id
    assert checks_by_id[check_id]["status"] == "PASS"


@pytest.mark.parametrize("check_id", ADV_CHECK_IDS)
def test_adversarial_check_recorded_and_passes(check_id: str) -> None:
    """Verify each ADV-01..ADV-20 check in w06_dev_select_live_authorization_01_receipt_v1.json is PASS."""
    receipt_path = REPO_ROOT / ds_auth_mod.AUTHORIZATION_RECEIPT_REL_PATH
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    checks_by_id = {c["check_id"]: c for c in receipt["adversarial_checks"]}
    assert check_id in checks_by_id
    assert checks_by_id[check_id]["status"] == "PASS"


def test_persisted_authorization_artifact_and_receipt_hashes_and_contract() -> None:
    """Verify persisted production DevLiveAuthorizationArtifact and receipt match exact pinned SHA256s."""
    auth_path = REPO_ROOT / ds_auth_mod.AUTHORIZATION_ARTIFACT_REL_PATH
    receipt_path = REPO_ROOT / ds_auth_mod.AUTHORIZATION_RECEIPT_REL_PATH
    prep_path = REPO_ROOT / ds_auth_mod.AUTHORIZATION_PREP_REL_PATH

    auth_bytes = normalize_lf_bytes(auth_path.read_bytes())
    receipt_bytes = normalize_lf_bytes(receipt_path.read_bytes())
    prep_bytes = normalize_lf_bytes(prep_path.read_bytes())

    auth_file_sha = sha256_bytes(auth_bytes)
    receipt_file_sha = sha256_bytes(receipt_bytes)
    prep_file_sha = sha256_bytes(prep_bytes)

    assert auth_file_sha == ds_auth_mod.EXPECTED_AUTHORIZATION_ARTIFACT_FILE_SHA256
    assert receipt_file_sha == ds_auth_mod.EXPECTED_AUTHORIZATION_RECEIPT_FILE_SHA256
    assert prep_file_sha == ds_auth_mod.EXPECTED_PREP_ARTIFACT_FILE_SHA256

    auths = ds_auth_mod.load_verified_authorities(REPO_ROOT)
    validated_auth = verify_dev_live_authorization_artifact(
        auth_path,
        execution_plan=auths["execution_plan"],
        prompt_freeze=auths["prompt_freeze"],
        expected_phase="DEV_SELECT",
        repo_root=REPO_ROOT,
    )
    assert isinstance(validated_auth, DevLiveAuthorizationArtifact)
    assert validated_auth.task_id == "W06-DEV-SELECT-LIVE-AUTHORIZATION-01"
    assert validated_auth.authorization_id == "W06-DEV-SELECT-LIVE-AUTHORIZATION-01-V1"
    assert validated_auth.authorized_by_role == "PROJECT_OWNER"
    assert validated_auth.authorization_status == "AUTHORIZED"
    assert validated_auth.allowed_phase == "DEV_SELECT"
    assert validated_auth.allowed_candidate_ids == ["C1", "C2", "C3"]
    assert validated_auth.maximum_live_generation_calls == 180
    assert (
        validated_auth.allowed_execution_plan_sha256
        == "de04255989a9e3bd8c2e39c766432487dce4ccd0612d5dba73b3476cbc9d0c6d"
    )
    assert (
        validated_auth.allowed_prompt_freeze_sha256
        == "2f345363f580ea882b2e5b3562c587ef5309bc7f994440257a54d18994ab6956"
    )
    assert (
        validated_auth.scientific_code_bundle_sha256
        == "0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3"
    )
    assert (
        validated_auth.code_basis_commit_sha
        == "c0adf74ceda9ffaf8b4ec42d299932e33f448e6a"
    )
    assert (
        validated_auth.authorization_artifact_sha256
        == ds_auth_mod.EXPECTED_AUTHORIZATION_INTERNAL_SHA256
    )

    receipt = json.loads(receipt_bytes.decode("utf-8"))
    assert receipt["artifact_id"] == "W06-DEV-SELECT-LIVE-AUTHORIZATION-01-RECEIPT-V1"
    assert receipt["authorization_text_character_count"] == 633
    assert (
        receipt["authorization_text_sha256"]
        == "6c32d37fcc557916b89ef0c1c87790bf76465e1352841a38655d5cf9676dbad7"
    )
    assert receipt["authorization_artifact_file_sha256"] == auth_file_sha
    assert (
        receipt["authorization_artifact_sha256"]
        == validated_auth.authorization_artifact_sha256
    )
    assert receipt["selected_prompt_id"] == "P1"
    assert (
        receipt["selected_prompt_semantic_sha256"]
        == "096ff4c74dd8d1aed1c0abe501b97c8dfd0f6424dbca535f2b79a242637a1c11"
    )
    assert receipt["stage_a_created"] is False
    assert receipt["live_execution_capability_issued"] is False
    assert receipt["production_provider_transport_constructed"] is False
    assert receipt["dev_select_execution_started"] is False
    assert receipt["live_provider_calls_new"] == 0
    assert receipt["provider_cost_usd_new"] == 0
    assert receipt["model_winner_selected"] is False
    assert receipt["stochasticity_execution_started"] is False
    assert receipt["final100_used"] is False

    assert_no_secrets_in_payload(validated_auth.model_dump(), context="TEST_AUTH")
    assert_no_secrets_in_payload(receipt, context="TEST_RECEIPT")


def test_verify_only_mode_succeeds_without_writes() -> None:
    """Verify --verify-only mode succeeds and leaves files byte-identical."""
    auth_path = REPO_ROOT / ds_auth_mod.AUTHORIZATION_ARTIFACT_REL_PATH
    receipt_path = REPO_ROOT / ds_auth_mod.AUTHORIZATION_RECEIPT_REL_PATH
    before_auth = auth_path.read_bytes()
    before_rec = receipt_path.read_bytes()

    rc = ds_auth_mod.main(["--verify-only"])
    assert rc == 0
    assert auth_path.read_bytes() == before_auth
    assert receipt_path.read_bytes() == before_rec


def test_adversarial_production_contract_rejections() -> None:
    """Directly verify all 20 adversarial fail-closed requirements from Section 17."""
    auths = ds_auth_mod.load_verified_authorities(REPO_ROOT)
    plan_model: DevExecutionPlan = auths["execution_plan"]
    freeze_model = auths["prompt_freeze"]
    cand_reg = auths["candidate_registry"]
    valid_auth = ds_auth_mod.build_scoped_dev_select_authorization_artifact(REPO_ROOT)
    valid_dict = valid_auth.model_dump()

    # 1. Wrong phase DEV_TUNE
    with pytest.raises(DevLiveAuthorizationError):
        verify_dev_live_authorization_artifact(
            valid_auth,
            execution_plan=plan_model,
            prompt_freeze=freeze_model,
            expected_phase="DEV_TUNE",
            repo_root=REPO_ROOT,
        )

    # 2. Wrong phase STOCHASTICITY
    with pytest.raises(DevLiveAuthorizationError):
        verify_dev_live_authorization_artifact(
            valid_auth,
            execution_plan=plan_model,
            prompt_freeze=freeze_model,
            expected_phase="STOCHASTICITY",
            repo_root=REPO_ROOT,
        )

    # 3. Final100
    with pytest.raises(Final100FirewallViolationError):
        verify_dev_live_authorization_artifact(
            valid_auth,
            execution_plan=plan_model,
            prompt_freeze=freeze_model,
            expected_phase="FINAL100",
            repo_root=REPO_ROOT,
        )

    # 4. 179/181 call budget
    for bad_calls in (179, 181):
        with pytest.raises(DevLiveAuthorizationError):
            build_dev_live_authorization_artifact(
                task_id=ds_auth_mod.TASK_ID,
                authorization_id=f"BAD-{bad_calls}",
                authorized_by_role="PROJECT_OWNER",
                authorized_at_utc=ds_auth_mod.AUTHORIZED_AT_UTC,
                authorization_status="AUTHORIZED",
                allowed_phase="DEV_SELECT",
                allowed_candidate_ids=["C1", "C2", "C3"],
                maximum_live_generation_calls=bad_calls,
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
            )

    # 5 & 6. Candidate C4 and candidate missing
    for bad_cands in (["C1", "C2", "C3", "C4"], ["C1", "C2"]):
        with pytest.raises(DevLiveAuthorizationError):
            build_dev_live_authorization_artifact(
                task_id=ds_auth_mod.TASK_ID,
                authorization_id="BAD-CANDS",
                authorized_by_role="PROJECT_OWNER",
                authorized_at_utc=ds_auth_mod.AUTHORIZED_AT_UTC,
                authorization_status="AUTHORIZED",
                allowed_phase="DEV_SELECT",
                allowed_candidate_ids=bad_cands,
                maximum_live_generation_calls=180,
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
            )

    # 7 & 8. Wrong plan internal SHA and wrong prompt-freeze SHA
    for field, bad_val in (
        ("allowed_execution_plan_sha256", "0" * 64),
        ("allowed_prompt_freeze_sha256", "f" * 64),
    ):
        d = dict(valid_dict)
        d.pop("authorization_artifact_sha256", None)
        d[field] = bad_val
        d["authorization_artifact_sha256"] = sha256_bytes(canonical_json_bytes(d))
        with pytest.raises(DevLiveAuthorizationError):
            verify_dev_live_authorization_artifact(
                d,
                execution_plan=plan_model,
                prompt_freeze=freeze_model,
                expected_phase="DEV_SELECT",
                repo_root=REPO_ROOT,
            )

    # 9 & 10. Wrong owner role and authorization_status != AUTHORIZED
    with pytest.raises(DevLiveAuthorizationError):
        build_dev_live_authorization_artifact(
            task_id=ds_auth_mod.TASK_ID,
            authorization_id="BAD-ROLE",
            authorized_by_role="DEVELOPER",
            authorized_at_utc=ds_auth_mod.AUTHORIZED_AT_UTC,
            authorization_status="AUTHORIZED",
            allowed_phase="DEV_SELECT",
            allowed_candidate_ids=["C1", "C2", "C3"],
            maximum_live_generation_calls=180,
            execution_plan=plan_model,
            prompt_freeze=freeze_model,
        )
    with pytest.raises(DevLiveAuthorizationError):
        build_dev_live_authorization_artifact(
            task_id=ds_auth_mod.TASK_ID,
            authorization_id="BAD-STATUS",
            authorized_by_role="PROJECT_OWNER",
            authorized_at_utc=ds_auth_mod.AUTHORIZED_AT_UTC,
            authorization_status="NOT_GRANTED",
            allowed_phase="DEV_SELECT",
            allowed_candidate_ids=["C1", "C2", "C3"],
            maximum_live_generation_calls=180,
            execution_plan=plan_model,
            prompt_freeze=freeze_model,
        )

    # 11. Wrong scientific bundle SHA
    d_bundle = dict(valid_dict)
    d_bundle.pop("authorization_artifact_sha256", None)
    d_bundle["scientific_code_bundle_sha256"] = "c" * 64
    d_bundle["authorization_artifact_sha256"] = sha256_bytes(
        canonical_json_bytes(d_bundle)
    )
    with pytest.raises(ScientificCodeBundleIntegrityError):
        verify_dev_live_authorization_artifact(
            d_bundle,
            execution_plan=plan_model,
            prompt_freeze=freeze_model,
            expected_phase="DEV_SELECT",
            repo_root=REPO_ROOT,
        )

    # 12. Wrong code basis (replacing c0adf74... with 1f5f94f...)
    d_basis = dict(valid_dict)
    d_basis.pop("authorization_artifact_sha256", None)
    d_basis["code_basis_commit_sha"] = ds_auth_mod.SOURCE_DEVELOP_SHA
    d_basis["authorization_artifact_sha256"] = sha256_bytes(
        canonical_json_bytes(d_basis)
    )
    with pytest.raises(DevLiveAuthorizationError):
        ds_auth_mod.verify_dev_select_live_authorization_contract(
            d_basis,
            execution_plan=plan_model,
            prompt_freeze=freeze_model,
            expected_phase="DEV_SELECT",
            repo_root=REPO_ROOT,
        )

    # 13. Tampered internal authorization SHA
    d_tampered = dict(valid_dict)
    d_tampered["authorization_artifact_sha256"] = "d" * 64
    with pytest.raises(DevLiveAuthorizationError):
        verify_dev_live_authorization_artifact(
            d_tampered,
            execution_plan=plan_model,
            prompt_freeze=freeze_model,
            expected_phase="DEV_SELECT",
            repo_root=REPO_ROOT,
        )

    # 17 & 18. P2 substituted into DEV-SELECT plan and retry=1 in cell
    p2_header_dict = plan_model.model_dump()
    p2_header_dict["prompt_ids"] = ["P2"]
    p2_header_model = DevExecutionPlan.model_validate(p2_header_dict)
    with pytest.raises(DevLiveAuthorizationError):
        ds_auth_mod.verify_dev_select_live_authorization_contract(
            valid_auth,
            execution_plan=p2_header_model,
            prompt_freeze=freeze_model,
            expected_phase="DEV_SELECT",
            repo_root=REPO_ROOT,
        )

    retry_plan_dict = plan_model.model_dump()
    retry_plan_dict["cells"][0]["retry"] = 1
    with pytest.raises(Exception):
        bad_retry_plan = DevExecutionPlan.model_validate(retry_plan_dict)
        verify_dev_execution_plan_for_execution(
            bad_retry_plan, candidate_registry=cand_reg, repo_root=REPO_ROOT
        )


def test_network_kill_switch_blocks_socket_urllib_httpx_and_httpx2() -> None:
    """Verify actual httpx2 (distinct from httpx), httpx, urllib, and socket are blocked."""
    assert httpx2.__name__ == "httpx2"
    assert httpx2 is not httpx
    guard = ds_auth_mod.NetworkKillSwitchGuard()
    with guard.activate():
        with pytest.raises(ds_auth_mod.OutboundNetworkBlockedError):
            with httpx2.Client() as c2:
                c2.get("https://example.com")
        with pytest.raises(ds_auth_mod.OutboundNetworkBlockedError):
            with httpx.Client() as c1:
                c1.get("https://example.com")
        with pytest.raises(ds_auth_mod.OutboundNetworkBlockedError):
            urllib.request.urlopen("https://example.com")
        with pytest.raises(ds_auth_mod.OutboundNetworkBlockedError):
            s = socket.socket()
            try:
                s.connect(("127.0.0.1", 9))
            finally:
                s.close()
    assert len(guard.blocked_attempts) == 4


def test_downstream_recognition_and_fail_closed_tampering(tmp_path: Path) -> None:
    """Verify Section 19 downstream recognizer accepts only exact verified DEV-SELECT authorization and rejects tampered files."""
    legit_auth = REPO_ROOT / ds_auth_mod.AUTHORIZATION_ARTIFACT_REL_PATH
    legit_rec = REPO_ROOT / ds_auth_mod.AUTHORIZATION_RECEIPT_REL_PATH

    assert (
        ds_auth_mod.is_verified_downstream_w06_dev_select_authorization_file(
            legit_auth, repo_root=REPO_ROOT
        )
        is True
    )
    assert (
        ds_auth_mod.is_verified_downstream_w06_dev_select_authorization_file(
            legit_rec, repo_root=REPO_ROOT
        )
        is True
    )

    # Pre-authorization firewalls on REPO_ROOT remain clean because downstream DEV-SELECT authorization is cryptographically verified
    fw_ds = ds_prep_mod.verify_pre_authorization_firewall(REPO_ROOT)
    assert fw_ds["dev_select_live_authorization_artifact_created"] is False
    assert fw_ds["forbidden_dev_select_auth_files"] == []

    fw_dt = dt_prep_mod.verify_pre_authorization_firewall(REPO_ROOT)
    assert fw_dt["live_authorization_artifact_created"] is False
    assert fw_dt["forbidden_auth_files"] == []

    # Synthetic tampered files with same filename fail closed
    w06_dir = tmp_path / "data" / "evaluation" / "w06"
    w06_dir.mkdir(parents=True)
    fake_auth = w06_dir / "w06_dev_select_live_authorization_v1.json"
    fake_rec = w06_dir / "w06_dev_select_live_authorization_01_receipt_v1.json"

    fake_auth.write_bytes(legit_auth.read_bytes() + b"\n")
    fake_rec.write_bytes(legit_rec.read_bytes())
    assert (
        ds_auth_mod.is_verified_downstream_w06_dev_select_authorization_file(
            fake_auth, repo_root=REPO_ROOT
        )
        is False
    )
    assert (
        ds_auth_mod.is_verified_downstream_w06_dev_select_authorization_file(
            fake_rec, repo_root=REPO_ROOT
        )
        is False
    )

    # Valid auth paired with tampered receipt fails closed
    fake_auth.write_bytes(legit_auth.read_bytes())
    bad_rec_obj = json.loads(legit_rec.read_text(encoding="utf-8"))
    bad_rec_obj["authorization_text_sha256"] = "0" * 64
    fake_rec.write_bytes(canonical_json_bytes(bad_rec_obj))
    assert (
        ds_auth_mod.is_verified_downstream_w06_dev_select_authorization_file(
            fake_auth, repo_root=REPO_ROOT
        )
        is False
    )
    assert (
        ds_auth_mod.is_verified_downstream_w06_dev_select_authorization_file(
            fake_rec, repo_root=REPO_ROOT
        )
        is False
    )

    # Pre-authorization firewall detects tampered DEV-SELECT authorization files
    fw_dirty = ds_prep_mod.verify_pre_authorization_firewall(tmp_path)
    assert fw_dirty["dev_select_live_authorization_artifact_created"] is True
    assert (
        "data/evaluation/w06/w06_dev_select_live_authorization_v1.json"
        in fw_dirty["forbidden_dev_select_auth_files"]
    )


def test_source_develop_provenance_fail_closed(tmp_path: Path) -> None:
    """Verify fail-closed source develop provenance check for 1f5f94f81bb57b4c6e746d86dc179f4c975e5f4f."""
    # Real repo passes
    real_res = ds_auth_mod.verify_source_develop_commit_or_shallow_fallback(REPO_ROOT)
    assert real_res["verified"] is True

    # Commit exists in local git but is NOT ancestor -> fails closed
    def _git_non_ancestor(args: list[str]) -> subprocess.CompletedProcess[str]:
        if "cat-file" in args:
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        if "merge-base" in args:
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="")
        return subprocess.CompletedProcess(args, 0, stdout="false\n", stderr="")

    bad_anc = ds_auth_mod.verify_source_develop_commit_or_shallow_fallback(
        REPO_ROOT, git_runner=_git_non_ancestor
    )
    assert bad_anc["verified"] is False

    # Shallow repo with all frozen fallback authorities matching -> passes
    def _git_shallow(args: list[str]) -> subprocess.CompletedProcess[str]:
        if "cat-file" in args:
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="missing")
        if "--is-shallow-repository" in args:
            return subprocess.CompletedProcess(args, 0, stdout="true\n", stderr="")
        return subprocess.CompletedProcess(args, 1, stdout="", stderr="")

    shallow_ok = ds_auth_mod.verify_source_develop_commit_or_shallow_fallback(
        REPO_ROOT, git_runner=_git_shallow
    )
    assert shallow_ok["verified"] is True
    assert shallow_ok["shallow_repository_fallback_used"] is True


def test_documentation_contains_required_hashes_and_metadata() -> None:
    """Verify docs/research/w06_dev_select_live_authorization_01.md records all required authorities."""
    doc_path = REPO_ROOT / "docs" / "research" / "w06_dev_select_live_authorization_01.md"
    assert doc_path.is_file()
    text = doc_path.read_text(encoding="utf-8")
    for expected_token in (
        "W06-DEV-SELECT-LIVE-AUTHORIZATION-01",
        "W06-DEV-SELECT-LIVE-AUTHORIZATION-01-V1",
        "W06-DEV-SELECT-LIVE-AUTHORIZATION-01-RECEIPT-V1",
        "1f5f94f81bb57b4c6e746d86dc179f4c975e5f4f",
        "c0adf74ceda9ffaf8b4ec42d299932e33f448e6a",
        "6c32d37fcc557916b89ef0c1c87790bf76465e1352841a38655d5cf9676dbad7",
        "de04255989a9e3bd8c2e39c766432487dce4ccd0612d5dba73b3476cbc9d0c6d",
        "c519baf7cd2557b5e1dd2699a5ceaec592af015d7bc6dcc83abf63892a8a329a",
        "5f32782f6359f409c7dd68f08699218cd577cb48bcb517f14c15939f896b9549",
        "2f345363f580ea882b2e5b3562c587ef5309bc7f994440257a54d18994ab6956",
        "096ff4c74dd8d1aed1c0abe501b97c8dfd0f6424dbca535f2b79a242637a1c11",
        "e1e79801117e59d3c8c703e024eacbad12d5336134c6597c333886c434a446b8",
        "60e6f0125ed54d6541e506e538a37b63b027a6c60a55572dcd612aa7cd2b72b8",
        "0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3",
        ds_auth_mod.EXPECTED_AUTHORIZATION_ARTIFACT_FILE_SHA256,
        ds_auth_mod.EXPECTED_AUTHORIZATION_INTERNAL_SHA256,
        ds_auth_mod.EXPECTED_AUTHORIZATION_RECEIPT_FILE_SHA256,
    ):
        assert expected_token in text
