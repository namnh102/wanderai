"""Independent adversarial scientific execution audit test suite (Runner QA-01) for W06 DEV Live Runner.

Task: W06-DEV-LIVE-RUNNER-QA-01-OFFLINE-ADVERSARIAL
Role: Independent adversarial scientific execution auditor.

Verifies all 60 independent Runner QA-01 checks (RQA-01 through RQA-60) derived from
frozen W06 scientific authorities, Portable Schema V2, Model Preflight 01B/01C/01D,
Harness QA-02, and the Runner Architecture Contract.
Strictly 100% offline with zero live provider calls and zero provider cost.
"""

from __future__ import annotations

import json
from pathlib import Path
import socket
import sys
from typing import Any, Dict
import urllib.request

import httpx
import httpx2
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.audit_w06_dev_live_runner_qa_01 import (  # noqa: E402
    ARTIFACT_ID,
    EXPECTED_14_SCIENTIFIC_BUNDLE_PATHS,
    EXPECTED_BASE_DEVELOP_SHA,
    EXPECTED_PRODUCTION_MODULE_SHAS,
    EXPECTED_RUNNER_SCIENTIFIC_BUNDLE_SHA256,
    FROZEN_AUTHORITY_EXPECTED_SHAS,
    HISTORICAL_QA_AND_RUNNER_EXPECTED_SHAS,
    QA01_RECEIPT_OUTPUT_PATH,
    TASK_ID,
    ExternalNetworkBlockedByQAKillSwitchError,
    IndependentNetworkKillSwitch,
    derive_independent_portable_schema_v2_oracle,
    derive_independent_scientific_bundle_oracle,
    run_all_runner_qa_01_checks,
    sha256_lf_file,
)


@pytest.fixture(scope="module")
def runner_qa01_audit_result() -> Dict[str, Any]:
    """Run the full independent Runner QA-01 adversarial audit once per test module."""
    return run_all_runner_qa_01_checks()


@pytest.fixture(scope="module")
def runner_qa01_checks_by_id(
    runner_qa01_audit_result: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    """Index all 60 Runner QA-01 checks by check_id (RQA-01 .. RQA-60)."""
    return {c["check_id"]: c for c in runner_qa01_audit_result["checks"]}


ALL_60_CHECK_IDS = [f"RQA-{i:02d}" for i in range(1, 61)]


def test_runner_qa01_check_inventory_complete(
    runner_qa01_audit_result: Dict[str, Any],
) -> None:
    """Verify all 60 checks RQA-01 .. RQA-60 are executed with zero failures."""
    observed_ids = [c["check_id"] for c in runner_qa01_audit_result["checks"]]
    assert observed_ids == ALL_60_CHECK_IDS
    assert runner_qa01_audit_result["qa_checks_total"] == 60
    assert runner_qa01_audit_result["qa_pass"] == 60
    assert runner_qa01_audit_result["qa_fail"] == 0
    assert runner_qa01_audit_result["critical_failures"] == []
    assert runner_qa01_audit_result["major_failures"] == []
    assert runner_qa01_audit_result["minor_failures"] == []
    assert runner_qa01_audit_result["overall_qa"] == "PASS"


@pytest.mark.parametrize("check_id", ALL_60_CHECK_IDS)
def test_runner_qa01_individual_check_passes(
    check_id: str, runner_qa01_checks_by_id: Dict[str, Dict[str, Any]]
) -> None:
    """Verify each individual check RQA-01 .. RQA-60 passes independently."""
    assert check_id in runner_qa01_checks_by_id, f"Missing check {check_id}"
    check = runner_qa01_checks_by_id[check_id]
    assert check["status"] == "PASS", (
        f"{check_id} ({check['domain']}) FAILED: {check['description']}\n"
        f"Expected: {check['expected']}\nObserved: {check['observed']}"
    )


def test_runner_qa01_independent_scientific_bundle_oracle() -> None:
    """Directly verify the independent 14-file scientific code bundle SHA256 oracle."""
    oracle = derive_independent_scientific_bundle_oracle()
    assert oracle["file_count"] == 14
    assert len(EXPECTED_14_SCIENTIFIC_BUNDLE_PATHS) == 14
    assert (
        "apps/ai-service/app/evaluation/dev_live_runner.py"
        in EXPECTED_14_SCIENTIFIC_BUNDLE_PATHS
    )
    assert oracle["bundle_sha256"] == EXPECTED_RUNNER_SCIENTIFIC_BUNDLE_SHA256
    assert (
        oracle["bundle_sha256"]
        == "0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3"
    )


def test_runner_qa01_independent_portable_schema_oracle() -> None:
    """Directly verify independent Portable Schema V2 manifest oracle."""
    schema_oracle = derive_independent_portable_schema_v2_oracle()
    assert (
        schema_oracle["computed_schema_sha256"]
        == schema_oracle["manifest_recorded_sha256"]
    )
    assert (
        schema_oracle["computed_schema_sha256"]
        == "825a4ff912d851a95f7392cb564b7d7ca3588135508dc6eb3ac6304cdde3c490"
    )
    assert (
        schema_oracle["semantic_schema_sha256"]
        == "e4169f7b890f77d13af65e9f2070b6071c535b206d88440f5e8f28c179977555"
    )
    assert schema_oracle["schema"]["additionalProperties"] is False


def test_runner_qa01_network_kill_switch_blocks_all_transports() -> None:
    """Directly verify the independent QA-01 network kill switch blocks socket, urllib, httpx, and httpx2."""
    ks = IndependentNetworkKillSwitch()
    with ks:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            with pytest.raises(
                ExternalNetworkBlockedByQAKillSwitchError,
                match="QA_KILL_SWITCH_BLOCKED_OUTBOUND_NETWORK",
            ):
                s.connect(("8.8.8.8", 443))
            with pytest.raises(
                ExternalNetworkBlockedByQAKillSwitchError,
                match="QA_KILL_SWITCH_BLOCKED_OUTBOUND_NETWORK",
            ):
                s.connect_ex(("8.8.8.8", 443))
        finally:
            s.close()

        with pytest.raises(
            ExternalNetworkBlockedByQAKillSwitchError,
            match="QA_KILL_SWITCH_BLOCKED_OUTBOUND_NETWORK",
        ):
            socket.create_connection(("example.com", 443))
        with pytest.raises(
            ExternalNetworkBlockedByQAKillSwitchError,
            match="QA_KILL_SWITCH_BLOCKED_OUTBOUND_NETWORK",
        ):
            urllib.request.urlopen("https://example.com")
        with pytest.raises(
            ExternalNetworkBlockedByQAKillSwitchError,
            match="QA_KILL_SWITCH_BLOCKED_OUTBOUND_NETWORK",
        ):
            httpx.HTTPTransport().handle_request(httpx.Request("GET", "https://example.com"))
        with pytest.raises(
            ExternalNetworkBlockedByQAKillSwitchError,
            match="QA_KILL_SWITCH_BLOCKED_OUTBOUND_NETWORK",
        ):
            httpx2.HTTPTransport().handle_request(
                httpx2.Request("GET", "https://example.com")
            )
    assert len(ks.blocked_attempts) == 6
    assert ks.external_connections_established == 0


def test_runner_qa01_production_files_and_historical_qa_unmodified() -> None:
    """Verify dev_live_runner.py, dev_selection_harness.py, frozen authorities, and historical QA artifacts are untouched."""
    for rel, expected_sha in EXPECTED_PRODUCTION_MODULE_SHAS.items():
        assert (
            sha256_lf_file(REPO_ROOT / rel) == expected_sha
        ), f"Modified production module: {rel}"

    for rel, expected_sha in FROZEN_AUTHORITY_EXPECTED_SHAS.items():
        assert (
            sha256_lf_file(REPO_ROOT / rel) == expected_sha
        ), f"Modified frozen authority or production file: {rel}"

    for rel, expected_sha in HISTORICAL_QA_AND_RUNNER_EXPECTED_SHAS.items():
        assert (
            sha256_lf_file(REPO_ROOT / rel) == expected_sha
        ), f"Modified historical QA or runner artifact: {rel}"


def test_runner_qa01_persisted_receipt_integrity(
    runner_qa01_audit_result: Dict[str, Any],
) -> None:
    """Verify the persisted Runner QA-01 receipt file exists and matches the live audit result."""
    assert QA01_RECEIPT_OUTPUT_PATH.exists(), (
        f"Persisted Runner QA-01 receipt missing at {QA01_RECEIPT_OUTPUT_PATH}"
    )
    persisted = json.loads(QA01_RECEIPT_OUTPUT_PATH.read_text(encoding="utf-8"))
    assert persisted["task_id"] == TASK_ID
    assert persisted["artifact_id"] == ARTIFACT_ID
    assert persisted["base_develop_sha"] == EXPECTED_BASE_DEVELOP_SHA
    assert (
        persisted["runner_scientific_bundle_sha256"]
        == EXPECTED_RUNNER_SCIENTIFIC_BUNDLE_SHA256
    )
    assert persisted["qa_checks_total"] == 60
    assert persisted["qa_pass"] == 60
    assert persisted["qa_fail"] == 0
    assert persisted["critical_failures"] == []
    assert persisted["major_failures"] == []
    assert persisted["minor_failures"] == []
    assert persisted["overall_qa"] == "PASS"
    assert persisted["network_isolation"] == "PASS"
    assert persisted["provider_requests"] == "PASS"
    assert persisted["one_http_request_per_cell"] == "PASS"
    assert persisted["retry_zero"] == "PASS"
    assert persisted["live_gate"] == "PASS"
    assert persisted["stage_a_process_boundary"] == "PASS"
    assert persisted["stage_a_commit_attestation"] == "PASS"
    assert persisted["action_boundary_reattestation"] == "PASS"
    assert persisted["toctou"] == "PASS"
    assert persisted["mid_batch_drift"] == "PASS"
    assert persisted["final100_firewall"] == "PASS"
    assert persisted["crash_ambiguity"] == "PASS"
    assert persisted["raw_evidence_order"] == "PASS"
    assert persisted["artifact_immutability"] == "PASS"
    assert persisted["strict_primary_parser"] == "PASS"
    assert persisted["model_id_integrity"] == "PASS"
    assert persisted["failure_taxonomy"] == "PASS"
    assert persisted["secret_sanitization"] == "PASS"
    assert persisted["usage_normalization"] == "PASS"
    assert persisted["exact_cost"] == "PASS"
    assert persisted["latency_ns"] == "PASS"
    assert persisted["call_budget"] == "PASS"
    assert persisted["duplicate_cell"] == "PASS"
    assert persisted["timestamp_provenance"] == "PASS"
    assert persisted["execution_mode_truthful"] == "PASS"
    assert persisted["stochasticity_firewall"] == "PASS"
    assert persisted["dev_select_firewall"] == "PASS"
    assert persisted["scientific_code_bundle"] == "PASS"
    assert persisted["historical_qa_unchanged"] is True
    assert persisted["live_provider_calls"] == 0
    assert persisted["provider_cost_usd"] == 0
    assert persisted["dev_tune_execution_started"] is False
    assert persisted["dev_select_execution_started"] is False
    assert persisted["winner_selected"] is False
    assert persisted["final100_used"] is False
    assert persisted["prompt_freeze_status"] == "NOT_YET_FROZEN"
    assert persisted["dev_model_execution_allowed"] is False
    assert persisted["next_gate"] == "W06-DEV-PROMPT-CANDIDATE-FREEZE-01"
    assert persisted == runner_qa01_audit_result
