"""Offline pytest suite for W06-DEV-PROMPT-CANDIDATE-FREEZE-01 (PF-01 through PF-35).

Strictly offline:
- Installs independent outbound-network kill switch across all tests
- Scrubs provider API keys (GEMINI_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY)
- Verifies PF-01 through PF-35 plus persisted artifact round-trip integrity
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
    assert freeze_sha == pf.EXPECTED_PROMPT_FREEZE_SHA256

    freeze_model = DevPromptFreezeArtifact.model_validate_json(freeze_bytes)
    plan_model = DevExecutionPlan.model_validate_json(plan_bytes)

    assert freeze_model.artifact_id == "W06-DEV-PROMPT-CANDIDATE-FREEZE-01-V1"
    assert freeze_model.version == "1.0.0"
    assert freeze_model.freeze_status == "FROZEN_FOR_LIVE_DEV_TUNE"
    assert freeze_model.created_before_live_dev_execution is True
    assert freeze_model.prompt_candidate_ids == ["P1", "P2"]
    assert freeze_model.max_call_budget == DEV_TUNE_MAX_CALLS_TWO_PROMPTS == 120
    assert freeze_model.code_basis_commit_sha == pf.CODE_BASIS_COMMIT_SHA
    assert (
        freeze_model.scientific_code_bundle_sha256
        == pf.EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
        == compute_scientific_code_bundle_sha256(repo_root=REPO_ROOT)
    )
    assert len(freeze_model.scientific_code_bundle_file_hashes) == len(
        SCIENTIFIC_CODE_BUNDLE_RELATIVE_PATHS
    ) == 14
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
    assert receipt_data["status"] == "PASS"
    assert receipt_data["verification_summary"]["total_checks"] == 35
    assert receipt_data["verification_summary"]["passed_checks"] == 35
    assert receipt_data["verification_summary"]["failed_checks"] == 0
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
    checks = pf.run_all_pf_checks()
    assert len(checks) == 35
    assert all(c["status"] == "PASS" for c in checks)
