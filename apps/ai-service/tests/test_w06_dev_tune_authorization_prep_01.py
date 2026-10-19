"""Pytest suite for W06-DEV-TUNE-LIVE-AUTHORIZATION-PREP-01.

Verifies AP-01 through AP-30, strict offline execution, secret-free key presence,
candidate-aware pricing evidence, conservative cost envelope honesty, and
pre-authorization firewall invariants.
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

import prepare_w06_dev_tune_authorization as prep_mod  # noqa: E402


def test_all_30_ap_checks_pass() -> None:
    """Verify AP-01 through AP-30 all pass against the repository and persisted artifact."""
    prep_path = REPO_ROOT / prep_mod.PREP_ARTIFACT_REL_PATH
    assert prep_path.is_file(), f"Missing prep artifact: {prep_path}"

    checks = prep_mod.run_all_ap_checks(REPO_ROOT, prep_artifact_path=prep_path)
    assert len(checks) == 30
    expected_ids = [f"AP-{i:02d}" for i in range(1, 31)]
    assert [c["check_id"] for c in checks] == expected_ids

    failed = [c for c in checks if c["status"] != "PASS"]
    assert not failed, f"Failed AP checks: {failed}"


@pytest.mark.parametrize("check_idx", range(1, 31))
def test_individual_ap_check_in_persisted_artifact(check_idx: int) -> None:
    """Verify each AP-01..AP-30 check recorded in w06_dev_tune_authorization_prep_v1.json is PASS."""
    prep_path = REPO_ROOT / prep_mod.PREP_ARTIFACT_REL_PATH
    data = json.loads(prep_path.read_text(encoding="utf-8"))
    check_id = f"AP-{check_idx:02d}"
    matching = [c for c in data["checks"] if c["check_id"] == check_id]
    assert len(matching) == 1
    assert matching[0]["status"] == "PASS"


def test_persisted_prep_artifact_deterministic_and_secret_free() -> None:
    """Verify persisted preparation artifact matches canonical builder output and is 100% secret-free."""
    prep_path = REPO_ROOT / prep_mod.PREP_ARTIFACT_REL_PATH
    raw_bytes = prep_path.read_bytes()
    assert b"\r\n" not in raw_bytes

    persisted = json.loads(raw_bytes.decode("utf-8"))
    prep_mod.assert_prep_payload_secret_free(persisted, context="TEST_PERSISTED_PREP")

    rebuilt = prep_mod.build_authorization_prep_payload(
        REPO_ROOT,
        key_presence_override=persisted["key_presence_status"],
    )
    for k, v in rebuilt.items():
        assert persisted[k] == v, f"Mismatch on field {k!r}"

    assert persisted["verification_summary"] == {
        "total_checks": 30,
        "passed_checks": 30,
        "failed_checks": 0,
        "overall_status": "PASS",
    }
    assert persisted["phase"] == "DEV_TUNE"
    assert persisted["project_owner_authorization_status"] == "NOT_GRANTED"
    assert persisted["live_authorization_artifact_created"] is False
    assert persisted["stage_a_created"] is False
    assert persisted["live_provider_calls"] == 0
    assert persisted["provider_cost_usd"] == 0.0
    assert persisted["dev_tune_execution_started"] is False
    assert persisted["dev_select_execution_started"] is False
    assert persisted["stochasticity_execution_started"] is False
    assert persisted["final100_used"] is False


def test_frozen_authorities_and_controlled_experiment_parity() -> None:
    """Verify frozen authorities and P1/P2 controlled experiment parity in the prep artifact."""
    prep_path = REPO_ROOT / prep_mod.PREP_ARTIFACT_REL_PATH
    persisted = json.loads(prep_path.read_text(encoding="utf-8"))

    assert (
        persisted["prompt_freeze_sha256"]
        == "2f345363f580ea882b2e5b3562c587ef5309bc7f994440257a54d18994ab6956"
    )
    assert (
        persisted["execution_plan_sha256"]
        == "582d9964b4fffbac91f83373d080f1fef120f0ddca4edab2d63e02796d0b20ae"
    )
    assert (
        persisted["execution_plan_file_sha256"]
        == "652e3beb08771c3125e613172b1aaa396fc1b60aaaf3b98cc238e91a14e0dc74"
    )
    assert (
        persisted["prompt_registry_sha256"]
        == "846dc4c14ec2a87537b7b3e07bf492de51dc534d24b21e469094b7e3d34d32b6"
    )
    assert (
        persisted["scientific_code_bundle_sha256"]
        == "0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3"
    )
    assert (
        persisted["portable_schema_v2_sha256"]
        == "825a4ff912d851a95f7392cb564b7d7ca3588135508dc6eb3ac6304cdde3c490"
    )
    assert (
        persisted["semantic_schema_sha256"]
        == "e4169f7b890f77d13af65e9f2070b6071c535b206d88440f5e8f28c179977555"
    )

    parity = persisted["controlled_experiment_parity"]
    assert parity["p1_p2_rendered_user_prompts_identical_all_20"] is True
    assert parity["only_system_prompt_suffix_differs"] is True
    assert parity["differing_cell_manifest_fields"] == [
        "prompt_id",
        "run_id",
        "system_prompt_sha256",
    ]
    assert (
        parity["fixture_001_rendered_user_prompt_sha256"]
        == "c632a1f607203a81c9422164a7910c5f82211437d74af9c91bb6b370c1da3c17"
    )


def test_secret_free_key_presence_check_with_and_without_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify check_key_presence_status_only returns only PRESENT/MISSING and never leaks secrets."""
    for k in prep_mod.REQUIRED_ENV_KEYS:
        monkeypatch.delenv(k, raising=False)

    # Without .env or process env -> all MISSING
    status_missing = prep_mod.check_key_presence_status_only(tmp_path)
    assert status_missing == {
        "GEMINI_API_KEY": "MISSING",
        "OPENAI_API_KEY": "MISSING",
        "ANTHROPIC_API_KEY": "MISSING",
    }

    # With .env containing only 2 keys and 1 empty key
    dotenv_file = tmp_path / ".env"
    dotenv_file.write_text(
        "GEMINI_API_KEY=dummy_gemini_val\nOPENAI_API_KEY=\nANTHROPIC_API_KEY='dummy_ant_val'\n",
        encoding="utf-8",
    )
    status_partial = prep_mod.check_key_presence_status_only(tmp_path)
    assert status_partial == {
        "GEMINI_API_KEY": "PRESENT",
        "OPENAI_API_KEY": "MISSING",
        "ANTHROPIC_API_KEY": "PRESENT",
    }

    # Reject any non-PRESENT/MISSING value in assert_prep_payload_secret_free
    bad_payload = {
        "key_presence_status": {
            "GEMINI_API_KEY": "dummy_gemini_val",
            "OPENAI_API_KEY": "MISSING",
            "ANTHROPIC_API_KEY": "PRESENT",
        }
    }
    with pytest.raises(ValueError, match="only PRESENT or MISSING allowed"):
        prep_mod.assert_prep_payload_secret_free(bad_payload, context="TEST_BAD")


def test_network_kill_switch_blocks_outbound_sockets() -> None:
    """Verify NetworkKillSwitchGuard blocks outbound socket/HTTP operations and records attempts."""
    guard = prep_mod.NetworkKillSwitchGuard()
    with guard.activate():
        with pytest.raises(
            prep_mod.OutboundNetworkBlockedError,
            match="OFFLINE_NETWORK_KILL_SWITCH_TRIGGERED",
        ):
            socket.create_connection(("example.com", 443), timeout=0.1)
    assert len(guard.blocked_attempts) == 1


def test_pre_authorization_firewall_detects_forbidden_artifacts(tmp_path: Path) -> None:
    """Verify verify_pre_authorization_firewall detects any early authorization or Stage-A files."""
    w06_dir = tmp_path / "data" / "evaluation" / "w06"
    w06_dir.mkdir(parents=True)

    clean_fw = prep_mod.verify_pre_authorization_firewall(tmp_path)
    assert clean_fw["live_authorization_artifact_created"] is False
    assert clean_fw["stage_a_receipt_created"] is False
    assert clean_fw["transport_journal_created"] is False
    assert clean_fw["provider_result_directories_created"] is False

    # Create a forbidden live authorization file
    (w06_dir / "w06_dev_tune_live_authorization_v1.json").write_text(
        "{}", encoding="utf-8"
    )
    dirty_fw = prep_mod.verify_pre_authorization_firewall(tmp_path)
    assert dirty_fw["live_authorization_artifact_created"] is True


def test_report_markdown_contains_required_hashes_and_sections() -> None:
    """Verify docs/research/w06_dev_tune_authorization_prep_01.md contains all required hashes and status strings."""
    report_path = (
        REPO_ROOT / "docs" / "research" / "w06_dev_tune_authorization_prep_01.md"
    )
    assert report_path.is_file()
    text = report_path.read_text(encoding="utf-8")

    prep_sha = hashlib.sha256(
        (REPO_ROOT / prep_mod.PREP_ARTIFACT_REL_PATH).read_bytes()
    ).hexdigest()
    required_substrings = [
        "W06-DEV-TUNE-LIVE-AUTHORIZATION-PREP-01",
        "443634e1f7583f334dec0315bb3816d249feb124",
        "2f345363f580ea882b2e5b3562c587ef5309bc7f994440257a54d18994ab6956",
        "582d9964b4fffbac91f83373d080f1fef120f0ddca4edab2d63e02796d0b20ae",
        "652e3beb08771c3125e613172b1aaa396fc1b60aaaf3b98cc238e91a14e0dc74",
        "846dc4c14ec2a87537b7b3e07bf492de51dc534d24b21e469094b7e3d34d32b6",
        "0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3",
        "825a4ff912d851a95f7392cb564b7d7ca3588135508dc6eb3ac6304cdde3c490",
        "e4169f7b890f77d13af65e9f2070b6071c535b206d88440f5e8f28c179977555",
        prep_sha,
        "NOT_GRANTED",
        "NOT_DEFENSIBLY_COMPUTABLE",
        prep_mod.PROPOSED_OWNER_AUTHORIZATION_TEXT,
    ]
    for sub in required_substrings:
        assert sub in text, f"Missing required substring in report: {sub!r}"
