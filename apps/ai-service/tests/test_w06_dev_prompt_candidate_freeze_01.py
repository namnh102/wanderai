"""Offline pytest suite for W06-DEV-PROMPT-CANDIDATE-FREEZE-01 & Audit Correction 01.

Strictly offline:
- Installs independent outbound-network kill switch across all tests
- Scrubs provider API keys (GEMINI_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY)
- Verifies PF-01 through PF-35 (35/35 PASS) and PFC-01 through PFC-16 (16/16 PASS)
- Verifies byte-identical rendered user prompts across all 20 DEV-TUNE fixtures
- Verifies persisted artifact round-trip integrity
"""

from __future__ import annotations

import hashlib
import json
import socket
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import freeze_w06_dev_prompt_candidates as pf  # noqa: E402
from app.evaluation.dev_live_runner import (  # noqa: E402
    verify_runner_prompt_freeze_artifact,
)
from app.evaluation.dev_selection_harness import (  # noqa: E402
    DEV_TUNE_MAX_CALLS_TWO_PROMPTS,
    EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
    EXPECTED_SEMANTIC_SCHEMA_SHA256,
    SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS,
    DevExecutionPlan,
    DevPromptFreezeArtifact,
    canonical_json_bytes,
    compute_scientific_code_bundle_sha256,
    load_and_verify_candidate_registry,
    load_and_verify_frozen_dev_bundle,
    verify_dev_execution_plan_for_execution,
    verify_prompt_candidate_freeze_artifact,
)


@pytest.fixture(scope="module")
def pf_checks_by_id() -> dict[str, dict[str, Any]]:
    """Run all PF-01..PF-35 checks once under network kill switch and return indexed map."""
    checks = pf.run_all_pf_checks()
    return {c["check_id"]: c for c in checks}


@pytest.fixture(scope="module")
def pfc_checks_by_id() -> dict[str, dict[str, Any]]:
    """Run all PFC-01..PFC-16 Audit Correction 01 checks once under network kill switch."""
    checks = pf.run_all_pfc_checks()
    return {c["check_id"]: c for c in checks}


@pytest.mark.parametrize(
    "check_id",
    [f"PF-{i:02d}" for i in range(1, 36)],
)
def test_pf_check_passes(
    check_id: str, pf_checks_by_id: dict[str, dict[str, Any]]
) -> None:
    assert check_id in pf_checks_by_id, f"Missing check {check_id}"
    entry = pf_checks_by_id[check_id]
    assert entry["status"] == "PASS", (
        f"{check_id} ({entry['domain']}) failed: expected={entry['expected']!r}, "
        f"observed={entry['observed']!r}"
    )


@pytest.mark.parametrize(
    "check_id",
    [f"PFC-{i:02d}" for i in range(1, 17)],
)
def test_pfc_check_passes(
    check_id: str, pfc_checks_by_id: dict[str, dict[str, Any]]
) -> None:
    assert check_id in pfc_checks_by_id, f"Missing check {check_id}"
    entry = pfc_checks_by_id[check_id]
    assert entry["status"] == "PASS", (
        f"{check_id} ({entry['domain']}) failed: expected={entry['expected']!r}, "
        f"observed={entry['observed']!r}"
    )


def test_network_kill_switch_blocks_outbound_socket() -> None:
    guard = pf.NetworkKillSwitchGuard()
    with guard.activate():
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            with pytest.raises(pf.OutboundNetworkBlockedError):
                sock.connect(("8.8.8.8", 443))
        finally:
            sock.close()
    assert len(guard.blocked_attempts) == 1


def test_persisted_prompt_freeze_and_plan_and_receipt_artifacts() -> None:
    freeze_path = REPO_ROOT / pf.FREEZE_ARTIFACT_RELATIVE_PATH
    plan_path = REPO_ROOT / pf.DEV_TUNE_PLAN_RELATIVE_PATH
    receipt_path = REPO_ROOT / pf.FREEZE_RECEIPT_RELATIVE_PATH
    report_path = REPO_ROOT / "docs/research/w06_dev_prompt_candidate_freeze_01.md"

    assert freeze_path.is_file(), f"Missing {freeze_path}"
    assert plan_path.is_file(), f"Missing {plan_path}"
    assert receipt_path.is_file(), f"Missing {receipt_path}"
    assert report_path.is_file(), f"Missing {report_path}"

    freeze_bytes = freeze_path.read_bytes()
    plan_bytes = plan_path.read_bytes()
    receipt_data = json.loads(receipt_path.read_text(encoding="utf-8"))

    freeze_sha = hashlib.sha256(freeze_bytes).hexdigest()
    plan_file_sha = hashlib.sha256(plan_bytes).hexdigest()
    assert freeze_sha == pf.EXPECTED_PROMPT_FREEZE_SHA256
    assert plan_file_sha == pf.EXPECTED_DEV_TUNE_PLAN_FILE_SHA256

    freeze_model = DevPromptFreezeArtifact.model_validate_json(freeze_bytes)
    plan_model = DevExecutionPlan.model_validate_json(plan_bytes)

    assert freeze_model.artifact_id == "W06-DEV-PROMPT-CANDIDATE-FREEZE-01-V1"
    assert freeze_model.version == "1.0.0"
    assert freeze_model.freeze_status == "FROZEN_FOR_LIVE_DEV_TUNE"
    assert freeze_model.created_before_live_dev_execution is True
    assert freeze_model.prompt_candidate_ids == ["P1", "P2"]
    assert freeze_model.prompt_versions == {
        "P1": "TRAVEL_PLANNER_BENCHMARK_V2",
        "P2": "TRAVEL_PLANNER_BENCHMARK_V2",
    }
    assert freeze_model.semantic_prompt_sha256_by_id == {
        "P1": pf.P1_AUTHORITATIVE_SEMANTIC_PROMPT_SHA256,
        "P2": pf.P2_EXPECTED_SEMANTIC_PROMPT_SHA256,
    }
    assert (
        freeze_model.dev_tune_execution_plan_sha256
        == pf.EXPECTED_DEV_TUNE_PLAN_SHA256
    )
    assert freeze_model.max_call_budget == DEV_TUNE_MAX_CALLS_TWO_PROMPTS == 120
    assert freeze_model.code_basis_commit_sha == pf.CODE_BASIS_COMMIT_SHA
    assert (
        freeze_model.scientific_code_bundle_sha256
        == pf.EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
        == compute_scientific_code_bundle_sha256(repo_root=REPO_ROOT)
    )
    assert (
        len(freeze_model.scientific_code_bundle_file_hashes)
        == len(SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS)
        == 14
    )
    assert (
        freeze_model.portable_generation_schema_v2_sha256
        == EXPECTED_PORTABLE_SCHEMA_V2_SHA256
    )

    assert plan_model.phase == "DEV_TUNE"
    assert plan_model.fixture_count == 20
    assert plan_model.expected_total_cells == 120
    assert len(plan_model.cells) == 120
    assert plan_model.plan_sha256 == pf.EXPECTED_DEV_TUNE_PLAN_SHA256
    assert all(
        c.semantic_schema_sha256 == EXPECTED_SEMANTIC_SCHEMA_SHA256
        for c in plan_model.cells
    )

    dev_bundle = load_and_verify_frozen_dev_bundle()
    cand_reg = load_and_verify_candidate_registry()
    registry = pf.build_frozen_p1_p2_registry()

    assert registry.registry_sha256 == pf.EXPECTED_PROMPT_REGISTRY_SHA256
    assert registry.prompts[0].prompt_version == "TRAVEL_PLANNER_BENCHMARK_V2"
    assert registry.prompts[1].prompt_version == "TRAVEL_PLANNER_BENCHMARK_V2"
    assert pf.P2_CANDIDATE_DEFINITION_ID == "W06_DEV_TUNE_CANDIDATE_P2_V1"

    pair_audit = pf.build_per_fixture_pair_audit(dev_bundle, registry, plan_model)
    assert pair_audit["fixture_count"] == 20
    assert pair_audit["all_20_rendered_user_prompts_byte_identical"] is True
    assert (
        pair_audit[
            "all_60_p1_p2_cell_pairs_identical_except_prompt_identity_and_system_prompt"
        ]
        is True
    )
    assert pair_audit["differing_manifest_fields_across_all_60_pairs"] == [
        "prompt_id",
        "run_id",
        "system_prompt_sha256",
    ]
    assert (
        pair_audit["fixtures"][0]["fixture_id"] == "W06-DEV-TUNE-001"
        and pair_audit["fixtures"][0]["p1_rendered_user_prompt_sha256"]
        == pf.EXPECTED_FIXTURE_001_RENDERED_USER_PROMPT_SHA256
        and pair_audit["fixtures"][0]["p2_rendered_user_prompt_sha256"]
        == pf.EXPECTED_FIXTURE_001_RENDERED_USER_PROMPT_SHA256
    )

    verify_dev_execution_plan_for_execution(
        plan_model, repo_root=REPO_ROOT, candidate_registry=cand_reg
    )
    verify_prompt_candidate_freeze_artifact(
        freeze_path,
        prompt_registry=registry,
        dev_tune_plan=plan_model,
        dev_bundle=dev_bundle,
        candidate_registry=cand_reg,
        repo_root=REPO_ROOT,
    )
    verify_runner_prompt_freeze_artifact(
        freeze_path,
        prompt_registry=registry,
        execution_plan=plan_model,
        dev_bundle=dev_bundle,
        candidate_registry=cand_reg,
        repo_root=REPO_ROOT,
    )

    assert receipt_data["task_id"] == "W06-DEV-PROMPT-CANDIDATE-FREEZE-01"
    assert (
        receipt_data["audit_correction_task_id"]
        == "W06-DEV-PROMPT-CANDIDATE-FREEZE-01-AUDIT-CORRECTION-01"
    )
    assert receipt_data["status"] == "PASS"
    assert receipt_data["verification_summary"]["pf_total_checks"] == 35
    assert receipt_data["verification_summary"]["pf_passed_checks"] == 35
    assert receipt_data["verification_summary"]["pf_failed_checks"] == 0
    assert receipt_data["verification_summary"]["pfc_total_checks"] == 16
    assert receipt_data["verification_summary"]["pfc_passed_checks"] == 16
    assert receipt_data["verification_summary"]["pfc_failed_checks"] == 0
    assert receipt_data["verification_summary"]["total_checks"] == 51
    assert receipt_data["verification_summary"]["passed_checks"] == 51
    assert receipt_data["verification_summary"]["failed_checks"] == 0
    assert receipt_data["prompts"]["P2"]["p2_candidate_definition_id"] == (
        "W06_DEV_TUNE_CANDIDATE_P2_V1"
    )
    assert receipt_data["prompts"]["P2"]["prompt_version"] == (
        "TRAVEL_PLANNER_BENCHMARK_V2"
    )
    assert receipt_data["prompts"]["p1_p2_rendered_user_prompts_identical_all_20"] is True
    assert receipt_data["prompts"]["only_system_prompt_suffix_differs"] is True
    assert receipt_data["scientific_decision"]["prompt_candidate_decision"] == (
        "P1_PLUS_P2_PRE_RESULTS"
    )
    assert receipt_data["scientific_decision"]["no_prompt_result_shopping"] is True
    assert receipt_data["zero_live_execution_boundary"]["live_provider_calls"] == 0
    assert receipt_data["zero_live_execution_boundary"]["provider_cost_usd"] == 0.0
    assert (
        receipt_data["zero_live_execution_boundary"]["dev_tune_execution_started"]
        is False
    )
    assert (
        receipt_data["zero_live_execution_boundary"]["dev_select_execution_started"]
        is False
    )
    assert (
        receipt_data["zero_live_execution_boundary"]["winning_prompt_selected"]
        is False
    )
    assert (
        receipt_data["zero_live_execution_boundary"]["winner_model_selected"] is False
    )
    assert receipt_data["zero_live_execution_boundary"]["final100_used"] is False
    assert (
        receipt_data["zero_live_execution_boundary"]["live_authorization_created"]
        is False
    )
    assert canonical_json_bytes(freeze_model.model_dump(mode="json")) == freeze_bytes
    assert canonical_json_bytes(plan_model.model_dump(mode="json")) == plan_bytes


def test_shallow_ci_checkout_compatibility(monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess as sp

    orig_run = sp.run

    def _mock_shallow_run(cmd: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(cmd, list) and len(cmd) >= 3 and cmd[:2] == ["git", "cat-file"]:
            return sp.CompletedProcess(cmd, 1, stdout="", stderr="missing")
        if (
            isinstance(cmd, list)
            and len(cmd) >= 3
            and cmd[:3] == ["git", "rev-parse", "--is-shallow-repository"]
        ):
            return sp.CompletedProcess(cmd, 0, stdout="true\n", stderr="")
        return orig_run(cmd, *args, **kwargs)

    monkeypatch.setattr(pf.subprocess, "run", _mock_shallow_run)
    pf_checks = pf.run_all_pf_checks()
    pfc_checks = pf.run_all_pfc_checks()
    assert len(pf_checks) == 35
    assert len(pfc_checks) == 16
    assert all(c["status"] == "PASS" for c in pf_checks)
    assert all(c["status"] == "PASS" for c in pfc_checks)
