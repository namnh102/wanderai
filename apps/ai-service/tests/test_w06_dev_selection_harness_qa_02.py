"""Independent scientific re-audit / adversarial verification test suite (QA-02) for W06 DEV Selection Harness.

Task: W06-DEV-SELECTION-HARNESS-QA-02-OFFLINE-INDEPENDENT
Role: Independent scientific re-audit / adversarial verification agent.

Verifies all 67 independent QA-02 checks (Q2-01 through Q2-67) derived from frozen
scientific authorities, manual mathematical oracles, and persisted QA-02 receipt
invariants. Strictly 100% offline with zero live provider calls.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Dict

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.audit_w06_dev_selection_harness_qa_02 import (  # noqa: E402
    ARTIFACT_ID,
    EXPECTED_BASE_DEVELOP_SHA,
    EXPECTED_SCIENTIFIC_BUNDLE_PATHS,
    FROZEN_AUTHORITY_EXPECTED_SHAS,
    HISTORICAL_QA01_EXPECTED_SHAS,
    QA02_RECEIPT_OUTPUT_PATH,
    TASK_ID,
    derive_independent_dev_oracle,
    derive_independent_reca_oracle,
    run_all_qa_02_checks,
    sha256_lf_file,
)


@pytest.fixture(scope="module")
def qa02_audit_result() -> Dict[str, Any]:
    """Run the full independent QA-02 audit oracle once per test module."""
    return run_all_qa_02_checks()


@pytest.fixture(scope="module")
def qa02_checks_by_id(qa02_audit_result: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Index all 67 QA-02 checks by check_id (Q2-01 .. Q2-67)."""
    return {c["check_id"]: c for c in qa02_audit_result["checks"]}


ALL_67_CHECK_IDS = [f"Q2-{i:02d}" for i in range(1, 68)]


def test_qa02_check_inventory_complete(qa02_audit_result: Dict[str, Any]) -> None:
    """Verify exactly 67 checks Q2-01 .. Q2-67 are executed with zero failures."""
    observed_ids = [c["check_id"] for c in qa02_audit_result["checks"]]
    assert observed_ids == ALL_67_CHECK_IDS
    assert qa02_audit_result["qa_checks_total"] == 67
    assert qa02_audit_result["qa_pass"] == 67
    assert qa02_audit_result["qa_fail"] == 0
    assert qa02_audit_result["critical_failures"] == []
    assert qa02_audit_result["major_failures"] == []
    assert qa02_audit_result["overall_qa"] == "PASS"


@pytest.mark.parametrize("check_id", ALL_67_CHECK_IDS)
def test_qa02_individual_check_passes(
    check_id: str, qa02_checks_by_id: Dict[str, Dict[str, Any]]
) -> None:
    """Verify each individual check Q2-01 .. Q2-67 passes independently."""
    assert check_id in qa02_checks_by_id, f"Missing check {check_id}"
    check = qa02_checks_by_id[check_id]
    assert check["status"] == "PASS", (
        f"{check_id} ({check['category']}) FAILED: {check['description']}\n"
        f"Expected: {check['expected']}\nObserved: {check['observed']}"
    )


def test_qa02_independent_dev_oracle_invariants() -> None:
    """Directly verify independent DEV bundle oracle without consulting harness constants."""
    oracle = derive_independent_dev_oracle()
    assert (
        oracle["bundle_sha256"]
        == "bb0f051446ea3da8229298f22f4ce92b4db20751695273c6d01b7766da044050"
    )
    assert oracle["total_count"] == 80
    assert oracle["dev_tune_count"] == 20
    assert oracle["dev_select_count"] == 60
    assert oracle["all_dev_exact_overlap_with_final"] == 0
    assert oracle["dev_tune_near_overlap_with_final"] == 0


def test_qa02_independent_reca_oracle_invariants() -> None:
    """Directly verify independent REC-A-CORE-V2 oracle counts and zero non-core overlap."""
    oracle = derive_independent_reca_oracle()
    assert oracle["counts"] == {"ha-noi": 145, "da-nang": 289, "ha-long": 188}
    assert oracle["total_core"] == 622
    assert oracle["all_da_nang_total"] == 293
    for slug in ("ha-noi", "da-nang", "ha-long"):
        assert (set(oracle["core_by_dest"][slug]) & oracle["non_core_place_ids"]) == set()


def test_qa02_historical_qa01_immutability_and_production_harness_unmodified() -> None:
    """Verify historical QA-01 evidence and frozen authorities are untouched."""
    for rel, expected_sha in HISTORICAL_QA01_EXPECTED_SHAS.items():
        assert sha256_lf_file(REPO_ROOT / rel) == expected_sha, f"Modified QA-01 file: {rel}"

    for rel, expected_sha in FROZEN_AUTHORITY_EXPECTED_SHAS.items():
        assert sha256_lf_file(REPO_ROOT / rel) == expected_sha, f"Modified authority: {rel}"

    assert len(EXPECTED_SCIENTIFIC_BUNDLE_PATHS) == 14
    assert "apps/ai-service/app/evaluation/dev_live_runner.py" in EXPECTED_SCIENTIFIC_BUNDLE_PATHS


def test_qa02_persisted_receipt_integrity(qa02_audit_result: Dict[str, Any]) -> None:
    """Verify the persisted historical QA-02 receipt file exists and preserves all QA-02 invariants."""
    assert QA02_RECEIPT_OUTPUT_PATH.exists(), (
        f"Persisted QA-02 receipt missing at {QA02_RECEIPT_OUTPUT_PATH}"
    )
    persisted = json.loads(QA02_RECEIPT_OUTPUT_PATH.read_text(encoding="utf-8"))
    assert persisted["task_id"] == TASK_ID
    assert persisted["artifact_id"] == ARTIFACT_ID
    assert persisted["base_develop_sha"] == EXPECTED_BASE_DEVELOP_SHA
    assert persisted["qa_independent_from_qa01"] is True
    assert persisted["historical_qa01_preserved"] is True
    assert persisted["historical_qa01_unchanged"] is True
    assert persisted["qa02_skipped"] is False
    assert persisted["qa_checks_total"] == 67
    assert persisted["qa_pass"] == 67
    assert persisted["qa_fail"] == 0
    assert persisted["overall_qa"] == "PASS"
    assert persisted["harness_scientific_readiness"] == "PASS"
    assert persisted["live_dev_runner_implemented"] is False
    assert persisted["live_dev_runner_in_scientific_bundle"] is False
    assert persisted["live_dev_runner_offline_qa_complete"] is False
    assert persisted["dev_model_execution_allowed"] is False
    assert persisted["next_gate"] == "W06-DEV-LIVE-RUNNER-01-OFFLINE"
    assert persisted["live_provider_calls"] == 0
    assert persisted["provider_cost_usd"] == 0
    assert persisted["dev_tune_execution_started"] is False
    assert persisted["dev_select_execution_started"] is False
    assert persisted["winner_selected"] is False
    assert persisted["final100_used"] is False
    persisted_by_id = {c["check_id"]: c for c in persisted["checks"]}
    live_by_id = {c["check_id"]: c for c in qa02_audit_result["checks"]}
    assert set(persisted_by_id.keys()) == set(live_by_id.keys())
    for cid, p_chk in persisted_by_id.items():
        if cid not in ("Q2-01", "Q2-53", "Q2-54"):
            assert live_by_id[cid] == p_chk
        else:
            assert live_by_id[cid]["status"] == "PASS"
