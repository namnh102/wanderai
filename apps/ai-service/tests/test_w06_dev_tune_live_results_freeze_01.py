"""Tests for W06-DEV-TUNE-LIVE-RESULTS-FREEZE-01.

Verifies RF-01 through RF-36 and 11 adversarial fail-closed tests.
Strictly offline (LIVE_PROVIDER_CALLS_NEW = 0).
Never mutates the committed raw output root `data/evaluation/w06/live_dev_tune_primary_v1`.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "scripts"
AI_SERVICE_DIR = REPO_ROOT / "apps" / "ai-service"
for _p in (SCRIPTS_DIR, AI_SERVICE_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from app.evaluation.dev_live_runner import PlanBeforeLiveProtocolError  # noqa: E402
from app.evaluation.dev_selection_harness import (  # noqa: E402
    FORBIDDEN_FINAL100_BUNDLE_SHA256,
    FORBIDDEN_P11_MANIFEST_SHA256,
    DevExecutionPlan,
    compute_scientific_code_bundle_sha256,
    normalize_lf_bytes,
    sha256_bytes,
)
import freeze_w06_dev_tune_live_results as rf_mod  # noqa: E402
from freeze_w06_dev_tune_live_results import (  # noqa: E402
    AUTHORIZATION_REL_PATH,
    BASE_EXECUTION_HEAD_SHA,
    COST_ACCOUNTING_LABEL,
    DEV_TUNE_PLAN_REL_PATH,
    EXPECTED_AUTHORITATIVE_COST_CELL_COUNT,
    EXPECTED_AUTHORIZATION_FILE_SHA256,
    EXPECTED_AUTHORIZATION_INTERNAL_SHA256,
    EXPECTED_DEV_TUNE_PLAN_FILE_SHA256,
    EXPECTED_DEV_TUNE_PLAN_SHA256,
    EXPECTED_LAUNCHER_GIT_BLOB_SHA,
    EXPECTED_LAUNCHER_LF_SHA256,
    EXPECTED_LAUNCHER_REL_PATH,
    EXPECTED_PARSED_PLAN_RESPONSE_COUNT,
    EXPECTED_PREFLIGHT_ARTIFACT_PATH_SET_SHA256,
    EXPECTED_PREFLIGHT_REQUEST_SET_SHA256,
    EXPECTED_PROMPT_FREEZE_SHA256,
    EXPECTED_RAW_EVIDENCE_FILE_COUNT,
    EXPECTED_RAW_EVIDENCE_MAX_FILE_BYTES,
    EXPECTED_RAW_EVIDENCE_TOTAL_BYTES,
    EXPECTED_RAW_EVIDENCE_TREE_SHA256,
    EXPECTED_RESULTS_FREEZE_RECEIPT_FILE_SHA256,
    EXPECTED_RESULTS_MANIFEST_FILE_SHA256,
    EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256,
    EXPECTED_STAGE_A_FILE_SHA256,
    EXPECTED_STAGE_A_INTERNAL_SHA256,
    EXPECTED_TOTAL_CANONICAL_COST_USD_DECIMAL,
    FORBIDDEN_FINAL100_SCENARIOS_REL_PATH,
    FORBIDDEN_P11_MANIFEST_REL_PATH,
    PROMPT_FREEZE_REL_PATH,
    RAW_OUTPUT_ROOT_REL_PATH,
    RESULTS_FREEZE_RECEIPT_REL_PATH,
    RESULTS_MANIFEST_REL_PATH,
    STAGE_A_RECEIPT_REL_PATH,
    NetworkKillSwitchGuard,
    OutboundNetworkBlockedError,
    build_raw_evidence_tree_manifest,
    generate_or_verify_results_freeze_artifacts,
    is_verified_downstream_w06_dev_tune_live_results_file,
    is_verified_downstream_w06_dev_tune_live_results_tree,
    verify_and_summarize_live_results_evidence,
)


@pytest.fixture(autouse=True)
def _enforce_offline_network_kill_switch() -> Any:
    with NetworkKillSwitchGuard():
        yield


@pytest.fixture(scope="module")
def verified_summary() -> dict[str, Any]:
    with NetworkKillSwitchGuard():
        return verify_and_summarize_live_results_evidence(REPO_ROOT)


@pytest.fixture(scope="module")
def persisted_manifest() -> dict[str, Any]:
    path = REPO_ROOT / RESULTS_MANIFEST_REL_PATH
    raw = normalize_lf_bytes(path.read_bytes())
    assert sha256_bytes(raw) == EXPECTED_RESULTS_MANIFEST_FILE_SHA256
    return json.loads(raw.decode("utf-8"))


@pytest.fixture(scope="module")
def persisted_receipt() -> dict[str, Any]:
    path = REPO_ROOT / RESULTS_FREEZE_RECEIPT_REL_PATH
    raw = normalize_lf_bytes(path.read_bytes())
    assert sha256_bytes(raw) == EXPECTED_RESULTS_FREEZE_RECEIPT_FILE_SHA256
    return json.loads(raw.decode("utf-8"))


def _clone_isolated_raw_output_root(tmp_path: Path) -> Path:
    """Create a fast isolated copy of the 120-cell raw output root in `tmp_path`
    so adversarial mutations never touch REPO_ROOT.
    """
    dst = tmp_path / "live_dev_tune_primary_v1"
    shutil.copytree(REPO_ROOT / RAW_OUTPUT_ROOT_REL_PATH, dst)
    return dst


# ==============================================================================
# RF-01 .. RF-36 DETERMINISTIC VERIFICATION CHECKS
# ==============================================================================


def test_rf01_execution_head_exact(
    persisted_manifest: dict[str, Any], persisted_receipt: dict[str, Any]
) -> None:
    assert persisted_manifest["execution_head_sha"] == BASE_EXECUTION_HEAD_SHA
    assert persisted_manifest["pre_live_head_sha"] == BASE_EXECUTION_HEAD_SHA
    assert persisted_manifest["post_live_head_sha"] == BASE_EXECUTION_HEAD_SHA
    assert persisted_receipt["base_execution_head_sha"] == BASE_EXECUTION_HEAD_SHA
    assert persisted_receipt["rf_checks"]["RF-01_execution_head_exact"] == "PASS"


def test_rf02_raw_output_root_exact(
    verified_summary: dict[str, Any],
    persisted_manifest: dict[str, Any],
    persisted_receipt: dict[str, Any],
) -> None:
    tm = verified_summary["tree_manifest"]
    assert tm["raw_output_root"] == RAW_OUTPUT_ROOT_REL_PATH
    assert tm["raw_evidence_file_count"] == EXPECTED_RAW_EVIDENCE_FILE_COUNT == 1124
    assert tm["raw_evidence_total_bytes"] == EXPECTED_RAW_EVIDENCE_TOTAL_BYTES == 11749420
    assert tm["raw_evidence_max_file_bytes"] == EXPECTED_RAW_EVIDENCE_MAX_FILE_BYTES == 96816
    assert tm["raw_evidence_tree_sha256"] == EXPECTED_RAW_EVIDENCE_TREE_SHA256
    assert persisted_manifest["raw_evidence_tree_sha256"] == EXPECTED_RAW_EVIDENCE_TREE_SHA256
    assert persisted_receipt["raw_evidence_tree_sha256"] == EXPECTED_RAW_EVIDENCE_TREE_SHA256
    assert persisted_receipt["rf_checks"]["RF-02_raw_output_root_exact"] == "PASS"


def test_rf03_raw_root_no_unknown_cell_dirs(
    persisted_manifest: dict[str, Any], persisted_receipt: dict[str, Any]
) -> None:
    raw_root = REPO_ROOT / RAW_OUTPUT_ROOT_REL_PATH
    dirs = sorted(p.name for p in raw_root.iterdir() if p.is_dir())
    files = [p.name for p in raw_root.iterdir() if not p.is_dir()]
    assert files == []
    assert len(dirs) == 120
    assert sorted(persisted_manifest["assigned_run_ids"]) == dirs
    assert persisted_receipt["rf_checks"]["RF-03_raw_root_no_unknown_cell_dirs"] == "PASS"


def test_rf04_120_assigned_run_ids_exact(
    verified_summary: dict[str, Any],
    persisted_manifest: dict[str, Any],
    persisted_receipt: dict[str, Any],
) -> None:
    plan = DevExecutionPlan.model_validate_json(
        normalize_lf_bytes((REPO_ROOT / DEV_TUNE_PLAN_REL_PATH).read_bytes())
    )
    expected_ids = [c.run_id for c in plan.cells]
    assert len(expected_ids) == 120
    assert len(set(expected_ids)) == 120
    assert verified_summary["assigned_run_ids"] == expected_ids
    assert persisted_manifest["assigned_run_ids"] == expected_ids
    assert persisted_receipt["rf_checks"]["RF-04_120_assigned_run_ids_exact"] == "PASS"


def test_rf05_request_manifest_count_120(
    verified_summary: dict[str, Any],
    persisted_manifest: dict[str, Any],
    persisted_receipt: dict[str, Any],
) -> None:
    assert verified_summary["file_type_counts"]["request_manifest.json"] == 120
    assert persisted_manifest["request_manifest_count"] == 120
    assert persisted_receipt["rf_checks"]["RF-05_request_manifest_count_120"] == "PASS"


def test_rf06_transport_starting_count_120(
    verified_summary: dict[str, Any],
    persisted_manifest: dict[str, Any],
    persisted_receipt: dict[str, Any],
) -> None:
    assert verified_summary["transport_starting_count"] == 120
    assert persisted_manifest["transport_starting_count"] == 120
    assert persisted_receipt["rf_checks"]["RF-06_transport_starting_count_120"] == "PASS"


def test_rf07_transport_completed_count_120(
    verified_summary: dict[str, Any],
    persisted_manifest: dict[str, Any],
    persisted_receipt: dict[str, Any],
) -> None:
    assert verified_summary["transport_completed_count"] == 120
    assert verified_summary["transport_ambiguous_count"] == 0
    assert persisted_manifest["transport_completed_count"] == 120
    assert persisted_manifest["transport_ambiguous_count"] == 0
    assert persisted_receipt["rf_checks"]["RF-07_transport_completed_count_120"] == "PASS"


def test_rf08_raw_response_count_120(
    verified_summary: dict[str, Any],
    persisted_manifest: dict[str, Any],
    persisted_receipt: dict[str, Any],
) -> None:
    assert verified_summary["file_type_counts"]["raw_provider_response.txt"] == 120
    assert persisted_manifest["raw_provider_response_count"] == 120
    assert persisted_receipt["rf_checks"]["RF-08_raw_response_count_120"] == "PASS"


def test_rf09_execution_receipt_count_120(
    verified_summary: dict[str, Any],
    persisted_manifest: dict[str, Any],
    persisted_receipt: dict[str, Any],
) -> None:
    assert verified_summary["file_type_counts"]["execution_receipt.json"] == 120
    assert len(verified_summary["execution_receipt_file_hashes"]) == 120
    assert persisted_manifest["execution_receipt_count"] == 120
    assert persisted_receipt["rf_checks"]["RF-09_execution_receipt_count_120"] == "PASS"


def test_rf10_evaluation_result_count_120(
    verified_summary: dict[str, Any],
    persisted_manifest: dict[str, Any],
    persisted_receipt: dict[str, Any],
) -> None:
    assert verified_summary["file_type_counts"]["evaluation_result.json"] == 120
    assert persisted_manifest["evaluation_result_count"] == 120
    assert persisted_receipt["rf_checks"]["RF-10_evaluation_result_count_120"] == "PASS"


def test_rf11_parsed_response_count_44(
    verified_summary: dict[str, Any],
    persisted_manifest: dict[str, Any],
    persisted_receipt: dict[str, Any],
) -> None:
    assert (
        verified_summary["file_type_counts"]["parsed_plan_response.json"]
        == EXPECTED_PARSED_PLAN_RESPONSE_COUNT
        == 44
    )
    assert persisted_manifest["parsed_plan_response_count"] == 44
    assert persisted_receipt["rf_checks"]["RF-11_parsed_response_count_44"] == "PASS"


def test_rf12_preflight_request_set_sha_exact(
    persisted_manifest: dict[str, Any], persisted_receipt: dict[str, Any]
) -> None:
    pf = rf_mod.compute_canonical_preflight_for_results_verification(REPO_ROOT)
    assert pf["preflight_request_set_sha256"] == EXPECTED_PREFLIGHT_REQUEST_SET_SHA256
    assert (
        pf["preflight_artifact_path_set_sha256"]
        == EXPECTED_PREFLIGHT_ARTIFACT_PATH_SET_SHA256
    )
    assert (
        persisted_manifest["preflight_request_set_sha256"]
        == EXPECTED_PREFLIGHT_REQUEST_SET_SHA256
    )
    assert (
        persisted_receipt["rf_checks"]["RF-12_preflight_request_set_sha_exact"]
        == "PASS"
    )


def test_rf13_request_identity_120_of_120(
    verified_summary: dict[str, Any],
    persisted_manifest: dict[str, Any],
    persisted_receipt: dict[str, Any],
) -> None:
    assert verified_summary["request_identity_match"] == "120/120"
    assert verified_summary["request_identity_match_count"] == 120
    assert persisted_manifest["request_identity_match"] == "120/120"
    assert persisted_receipt["rf_checks"]["RF-13_request_identity_120_of_120"] == "PASS"


def test_rf14_per_cell_receipt_hash_chains_120_of_120(
    verified_summary: dict[str, Any],
    persisted_manifest: dict[str, Any],
    persisted_receipt: dict[str, Any],
) -> None:
    assert verified_summary["cell_hash_chain_valid"] == "120/120"
    assert verified_summary["cell_hash_chain_valid_count"] == 120
    assert persisted_manifest["cell_hash_chain_valid"] == "120/120"
    assert (
        persisted_receipt["rf_checks"]["RF-14_per_cell_receipt_hash_chains_120_of_120"]
        == "PASS"
    )


def test_rf15_retry_count_zero(
    verified_summary: dict[str, Any],
    persisted_manifest: dict[str, Any],
    persisted_receipt: dict[str, Any],
) -> None:
    assert verified_summary["retry_calls"] == 0
    assert persisted_manifest["retry_calls"] == 0
    assert persisted_receipt["rf_checks"]["RF-15_retry_count_zero"] == "PASS"


def test_rf16_rerun_count_zero(
    verified_summary: dict[str, Any],
    persisted_manifest: dict[str, Any],
    persisted_receipt: dict[str, Any],
) -> None:
    assert verified_summary["rerun_cells"] == 0
    assert persisted_manifest["rerun_cells"] == 0
    assert persisted_receipt["rf_checks"]["RF-16_rerun_count_zero"] == "PASS"


def test_rf17_model_mismatch_zero(
    verified_summary: dict[str, Any],
    persisted_manifest: dict[str, Any],
    persisted_receipt: dict[str, Any],
) -> None:
    assert verified_summary["model_id_mismatch_count"] == 0
    assert persisted_manifest["model_id_mismatch_count"] == 0
    assert persisted_receipt["rf_checks"]["RF-17_model_mismatch_zero"] == "PASS"


def test_rf18_failure_counts_exact(
    verified_summary: dict[str, Any],
    persisted_manifest: dict[str, Any],
    persisted_receipt: dict[str, Any],
) -> None:
    fc = verified_summary["failure_classification_counts"]
    assert fc["total"] == {
        "HTTP_429": 15,
        "HTTP_5XX": 3,
        "HTTP_ERROR": 1,
        "NONE": 44,
        "TIMEOUT": 57,
    }
    assert fc["by_candidate"] == {
        "C1": {"HTTP_429": 15, "HTTP_5XX": 3, "NONE": 4, "TIMEOUT": 18},
        "C2": {"NONE": 7, "TIMEOUT": 33},
        "C3": {"HTTP_ERROR": 1, "NONE": 33, "TIMEOUT": 6},
    }
    assert fc["by_prompt"] == {
        "P1": {"HTTP_5XX": 2, "NONE": 23, "TIMEOUT": 35},
        "P2": {"HTTP_429": 15, "HTTP_5XX": 1, "HTTP_ERROR": 1, "NONE": 21, "TIMEOUT": 22},
    }
    assert persisted_manifest["failure_classification_counts"] == fc
    assert persisted_receipt["rf_checks"]["RF-18_failure_counts_exact"] == "PASS"


def test_rf19_valid_schema_counts_exact(
    verified_summary: dict[str, Any],
    persisted_manifest: dict[str, Any],
    persisted_receipt: dict[str, Any],
) -> None:
    vc = verified_summary["valid_run_and_schema_counts"]
    assert vc["total"] == {"false": 76, "true": 44}
    assert vc["by_candidate"] == {
        "C1": {"false": 36, "true": 4},
        "C2": {"false": 33, "true": 7},
        "C3": {"false": 7, "true": 33},
    }
    assert vc["by_prompt"] == {
        "P1": {"false": 37, "true": 23},
        "P2": {"false": 39, "true": 21},
    }
    assert vc["by_prompt_candidate"] == {
        "P1_C1": {"false": 17, "true": 3},
        "P1_C2": {"false": 16, "true": 4},
        "P1_C3": {"false": 4, "true": 16},
        "P2_C1": {"false": 19, "true": 1},
        "P2_C2": {"false": 17, "true": 3},
        "P2_C3": {"false": 3, "true": 17},
    }
    assert persisted_manifest["valid_run_and_schema_counts"] == vc
    assert persisted_receipt["rf_checks"]["RF-19_valid_schema_counts_exact"] == "PASS"


def test_rf20_grounding_counts_exact(
    verified_summary: dict[str, Any],
    persisted_manifest: dict[str, Any],
    persisted_receipt: dict[str, Any],
) -> None:
    gc = verified_summary["exact_grounding_pass_counts"]
    assert gc["total"] == {"false": 76, "true": 44}
    assert gc["by_prompt_candidate"] == {
        "P1_C1": {"false": 17, "true": 3},
        "P1_C2": {"false": 16, "true": 4},
        "P1_C3": {"false": 4, "true": 16},
        "P2_C1": {"false": 19, "true": 1},
        "P2_C2": {"false": 17, "true": 3},
        "P2_C3": {"false": 3, "true": 17},
    }
    assert persisted_manifest["exact_grounding_pass_counts"] == gc
    assert persisted_receipt["rf_checks"]["RF-20_grounding_counts_exact"] == "PASS"


def test_rf21_core_pass_counts_exact(
    verified_summary: dict[str, Any],
    persisted_manifest: dict[str, Any],
    persisted_receipt: dict[str, Any],
) -> None:
    cc = verified_summary["final_core_pass_counts"]
    assert cc["total"] == {"false": 79, "true": 41}
    assert cc["by_candidate"] == {
        "C1": {"false": 39, "true": 1},
        "C2": {"false": 33, "true": 7},
        "C3": {"false": 7, "true": 33},
    }
    assert cc["by_prompt"] == {
        "P1": {"false": 40, "true": 20},
        "P2": {"false": 39, "true": 21},
    }
    assert cc["by_prompt_candidate"] == {
        "P1_C1": {"false": 20, "true": 0},
        "P1_C2": {"false": 16, "true": 4},
        "P1_C3": {"false": 4, "true": 16},
        "P2_C1": {"false": 19, "true": 1},
        "P2_C2": {"false": 17, "true": 3},
        "P2_C3": {"false": 3, "true": 17},
    }
    assert persisted_manifest["final_core_pass_counts"] == cc
    assert persisted_receipt["rf_checks"]["RF-21_core_pass_counts_exact"] == "PASS"


def test_rf22_authoritative_cost_cells_42(
    verified_summary: dict[str, Any],
    persisted_manifest: dict[str, Any],
    persisted_receipt: dict[str, Any],
) -> None:
    assert (
        verified_summary["authoritative_cost_cell_count"]
        == EXPECTED_AUTHORITATIVE_COST_CELL_COUNT
        == 42
    )
    assert len(verified_summary["non_comparable_cached_valid_run_ids"]) == 2
    assert persisted_manifest["authoritative_cost_cell_count"] == 42
    assert persisted_receipt["rf_checks"]["RF-22_authoritative_cost_cells_42"] == "PASS"


def test_rf23_canonical_available_cost_6_5555805(
    verified_summary: dict[str, Any],
    persisted_manifest: dict[str, Any],
    persisted_receipt: dict[str, Any],
) -> None:
    assert (
        verified_summary["authoritative_receipt_cost_total_usd"]
        == EXPECTED_TOTAL_CANONICAL_COST_USD_DECIMAL
        == "6.5555805"
    )
    assert verified_summary["cost_accounting_label"] == COST_ACCOUNTING_LABEL
    assert persisted_manifest["authoritative_receipt_cost_total_usd"] == "6.5555805"
    assert (
        persisted_receipt["rf_checks"]["RF-23_canonical_available_cost_6_5555805"]
        == "PASS"
    )


def test_rf24_p1_count_60(
    verified_summary: dict[str, Any],
    persisted_manifest: dict[str, Any],
    persisted_receipt: dict[str, Any],
) -> None:
    assert verified_summary["result_counts_by_prompt"]["P1"] == 60
    assert persisted_manifest["result_counts_by_prompt"]["P1"] == 60
    assert persisted_receipt["rf_checks"]["RF-24_p1_count_60"] == "PASS"


def test_rf25_p2_count_60(
    verified_summary: dict[str, Any],
    persisted_manifest: dict[str, Any],
    persisted_receipt: dict[str, Any],
) -> None:
    assert verified_summary["result_counts_by_prompt"]["P2"] == 60
    assert persisted_manifest["result_counts_by_prompt"]["P2"] == 60
    assert persisted_receipt["rf_checks"]["RF-25_p2_count_60"] == "PASS"


def test_rf26_c1_c2_c3_each_40(
    verified_summary: dict[str, Any],
    persisted_manifest: dict[str, Any],
    persisted_receipt: dict[str, Any],
) -> None:
    assert verified_summary["result_counts_by_candidate"] == {
        "C1": 40,
        "C2": 40,
        "C3": 40,
    }
    assert persisted_manifest["result_counts_by_candidate"] == {
        "C1": 40,
        "C2": 40,
        "C3": 40,
    }
    assert persisted_receipt["rf_checks"]["RF-26_c1_c2_c3_each_40"] == "PASS"


def test_rf27_execution_ordering_records_p1_before_p2(
    verified_summary: dict[str, Any], persisted_receipt: dict[str, Any]
) -> None:
    tol = verified_summary["temporal_ordering_limitation"]
    assert tol["p1_executed_before_p2"] is True
    assert tol["p1_cell_indices"] == [0, 59]
    assert tol["p2_cell_indices"] == [60, 119]
    assert tol["prompt_treatment_temporally_interleaved_or_randomized"] is False
    assert (
        persisted_receipt["rf_checks"]["RF-27_execution_ordering_records_p1_before_p2"]
        == "PASS"
    )


def test_rf28_429_temporal_confound_limitation_recorded(
    verified_summary: dict[str, Any], persisted_receipt: dict[str, Any]
) -> None:
    tol = verified_summary["temporal_ordering_limitation"]
    assert tol["observed_http_429_total"] == 15
    assert tol["observed_http_429_in_p2_c1"] == 15
    assert "MUST NOT be interpreted as evidence that P2 causes HTTP 429" in tol[
        "scientific_interpretation"
    ]
    doc_text = (
        REPO_ROOT / "docs/research/w06_dev_tune_live_results_freeze_01.md"
    ).read_text(encoding="utf-8")
    assert "MUST NOT" in doc_text and "HTTP 429" in doc_text
    assert (
        persisted_receipt["rf_checks"][
            "RF-28_429_temporal_confound_limitation_recorded"
        ]
        == "PASS"
    )


def test_rf29_prompt_winner_not_yet_selected(
    verified_summary: dict[str, Any],
    persisted_manifest: dict[str, Any],
    persisted_receipt: dict[str, Any],
) -> None:
    preview = verified_summary["prompt_selection_preview"]
    assert preview["winning_prompt_selected"] is False
    assert preview["criterion_1_valid_run_and_schema_rate"]["survivors"] == ["P1", "P2"]
    assert preview["criterion_2_exact_grounding_pass_rate"]["survivors"] == ["P1", "P2"]
    assert preview["criterion_3_final_core_pass_rate"]["survivors"] == ["P1", "P2"]
    assert preview["administrative_tie_break_would_select"] == "P1"
    assert persisted_manifest["winning_prompt_selected"] is False
    assert persisted_receipt["winning_prompt_selected"] is False
    assert (
        persisted_receipt["rf_checks"]["RF-29_prompt_winner_not_yet_selected"]
        == "PASS"
    )


def test_rf30_model_winner_not_selected(
    persisted_manifest: dict[str, Any], persisted_receipt: dict[str, Any]
) -> None:
    assert persisted_manifest["model_winner_selected"] is False
    assert persisted_manifest["dev_select_execution_started"] is False
    assert persisted_manifest["stochasticity_execution_started"] is False
    assert persisted_receipt["model_winner_selected"] is False
    assert persisted_receipt["dev_select_execution_started"] is False
    assert persisted_receipt["rf_checks"]["RF-30_model_winner_not_selected"] == "PASS"


def test_rf31_final100_untouched(
    persisted_manifest: dict[str, Any], persisted_receipt: dict[str, Any]
) -> None:
    f100_sha = sha256_bytes(
        normalize_lf_bytes(
            (REPO_ROOT / FORBIDDEN_FINAL100_SCENARIOS_REL_PATH).read_bytes()
        )
    )
    p11_sha = sha256_bytes(
        normalize_lf_bytes((REPO_ROOT / FORBIDDEN_P11_MANIFEST_REL_PATH).read_bytes())
    )
    assert f100_sha == FORBIDDEN_FINAL100_BUNDLE_SHA256
    assert p11_sha == FORBIDDEN_P11_MANIFEST_SHA256
    assert persisted_manifest["final100_used"] is False
    assert persisted_receipt["final100_used"] is False
    assert persisted_receipt["rf_checks"]["RF-31_final100_untouched"] == "PASS"


def test_rf32_secret_scan_pass(
    verified_summary: dict[str, Any], persisted_receipt: dict[str, Any]
) -> None:
    assert verified_summary["secret_scan_result"] == {
        "secret_leak_scan": "PASS",
        "scanned_file_count": 1124,
        "secret_leak_detected": False,
    }
    assert persisted_receipt["rf_checks"]["RF-32_secret_scan_pass"] == "PASS"


def test_rf33_raw_tree_hash_stable_before_after_freeze_generation(
    persisted_receipt: dict[str, Any],
) -> None:
    before_tm = build_raw_evidence_tree_manifest(REPO_ROOT)
    out = generate_or_verify_results_freeze_artifacts(
        repo_root=REPO_ROOT, write_artifacts=False
    )
    after_tm = build_raw_evidence_tree_manifest(REPO_ROOT)
    assert (
        before_tm["raw_evidence_tree_sha256"]
        == after_tm["raw_evidence_tree_sha256"]
        == out["raw_evidence_tree_sha256"]
        == EXPECTED_RAW_EVIDENCE_TREE_SHA256
    )
    assert (
        persisted_receipt["rf_checks"][
            "RF-33_raw_tree_hash_stable_before_after_freeze_generation"
        ]
        == "PASS"
    )


def test_rf34_raw_tree_hash_stable_after_commit(
    persisted_receipt: dict[str, Any],
) -> None:
    tm = build_raw_evidence_tree_manifest(REPO_ROOT)
    assert tm["raw_evidence_tree_sha256"] == EXPECTED_RAW_EVIDENCE_TREE_SHA256
    assert is_verified_downstream_w06_dev_tune_live_results_tree(REPO_ROOT) is True
    assert (
        persisted_receipt["rf_checks"]["RF-34_raw_tree_hash_stable_after_commit"]
        == "PASS"
    )


def test_rf35_scientific_bundle_unchanged(
    persisted_manifest: dict[str, Any], persisted_receipt: dict[str, Any]
) -> None:
    bundle_sha = compute_scientific_code_bundle_sha256(repo_root=REPO_ROOT)
    assert bundle_sha == EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
    assert (
        persisted_manifest["scientific_code_bundle_sha256"]
        == EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
    )
    assert (
        persisted_receipt["rf_checks"]["RF-35_scientific_bundle_unchanged"] == "PASS"
    )


def test_rf36_launcher_unchanged(
    persisted_manifest: dict[str, Any], persisted_receipt: dict[str, Any]
) -> None:
    launcher_path = REPO_ROOT / EXPECTED_LAUNCHER_REL_PATH
    lf_sha = sha256_bytes(normalize_lf_bytes(launcher_path.read_bytes()))
    assert lf_sha == EXPECTED_LAUNCHER_LF_SHA256
    blob_proc = subprocess.run(
        ["git", "hash-object", EXPECTED_LAUNCHER_REL_PATH],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert blob_proc.stdout.strip() == EXPECTED_LAUNCHER_GIT_BLOB_SHA
    assert persisted_manifest["launcher_lf_sha256"] == EXPECTED_LAUNCHER_LF_SHA256
    assert (
        persisted_manifest["launcher_git_blob_sha"] == EXPECTED_LAUNCHER_GIT_BLOB_SHA
    )
    assert persisted_receipt["rf_checks"]["RF-36_launcher_unchanged"] == "PASS"


# ==============================================================================
# 11 ADVERSARIAL FAIL-CLOSED TESTS (SECTION 24)
# ==============================================================================


def test_adversarial_01_missing_cell_fails_closed(tmp_path: Path) -> None:
    raw_copy = _clone_isolated_raw_output_root(tmp_path)
    shutil.rmtree(raw_copy / "W06-DEV-TUNE-P1-C1-W06-DEV-TUNE-001")

    with pytest.raises(PlanBeforeLiveProtocolError, match="MISSING_CELL_DIRECTORIES"):
        verify_and_summarize_live_results_evidence(
            repo_root=REPO_ROOT, raw_output_root=raw_copy
        )
    assert (
        is_verified_downstream_w06_dev_tune_live_results_tree(
            REPO_ROOT, raw_output_root=raw_copy
        )
        is False
    )


def test_adversarial_02_extra_cell_fails_closed(tmp_path: Path) -> None:
    raw_copy = _clone_isolated_raw_output_root(tmp_path)
    (raw_copy / "W06-DEV-TUNE-P1-C1-W06-DEV-TUNE-999").mkdir(parents=True)

    with pytest.raises(
        PlanBeforeLiveProtocolError, match="UNKNOWN_EXTRA_CELL_DIRECTORIES"
    ):
        verify_and_summarize_live_results_evidence(
            repo_root=REPO_ROOT, raw_output_root=raw_copy
        )
    assert (
        is_verified_downstream_w06_dev_tune_live_results_tree(
            REPO_ROOT, raw_output_root=raw_copy
        )
        is False
    )


def test_adversarial_03_edited_raw_response_fails_closed(tmp_path: Path) -> None:
    raw_copy = _clone_isolated_raw_output_root(tmp_path)
    raw_resp_path = (
        raw_copy
        / "W06-DEV-TUNE-P1-C3-W06-DEV-TUNE-001"
        / "raw_provider_response.txt"
    )
    raw_resp_path.write_bytes(raw_resp_path.read_bytes() + b"\n")

    with pytest.raises(PlanBeforeLiveProtocolError, match="CELL_HASH_CHAIN_BROKEN"):
        verify_and_summarize_live_results_evidence(
            repo_root=REPO_ROOT, raw_output_root=raw_copy
        )
    assert (
        is_verified_downstream_w06_dev_tune_live_results_tree(
            REPO_ROOT, raw_output_root=raw_copy
        )
        is False
    )


def test_adversarial_04_edited_receipt_fails_closed(tmp_path: Path) -> None:
    raw_copy = _clone_isolated_raw_output_root(tmp_path)
    rec_path = (
        raw_copy
        / "W06-DEV-TUNE-P1-C1-W06-DEV-TUNE-001"
        / "execution_receipt.json"
    )
    rec_obj = json.loads(rec_path.read_text(encoding="utf-8"))
    rec_obj["requested_model_id"] = "tampered-model-v0"
    rec_path.write_text(json.dumps(rec_obj, indent=2), encoding="utf-8")

    with pytest.raises(
        PlanBeforeLiveProtocolError, match="REQUESTED_MODEL_ID_MISMATCH"
    ):
        verify_and_summarize_live_results_evidence(
            repo_root=REPO_ROOT, raw_output_root=raw_copy
        )
    assert (
        is_verified_downstream_w06_dev_tune_live_results_tree(
            REPO_ROOT, raw_output_root=raw_copy
        )
        is False
    )


def test_adversarial_05_tampered_receipt_hash_pointer_fails_closed(
    tmp_path: Path,
) -> None:
    raw_copy = _clone_isolated_raw_output_root(tmp_path)
    rec_path = (
        raw_copy
        / "W06-DEV-TUNE-P1-C3-W06-DEV-TUNE-001"
        / "execution_receipt.json"
    )
    rec_obj = json.loads(rec_path.read_text(encoding="utf-8"))
    rec_obj["evaluation_result_sha256"] = "0" * 64
    rec_path.write_text(json.dumps(rec_obj, indent=2), encoding="utf-8")

    with pytest.raises(PlanBeforeLiveProtocolError, match="CELL_HASH_CHAIN_BROKEN"):
        verify_and_summarize_live_results_evidence(
            repo_root=REPO_ROOT, raw_output_root=raw_copy
        )


def test_adversarial_06_duplicate_run_id_fails_closed(tmp_path: Path) -> None:
    raw_copy = _clone_isolated_raw_output_root(tmp_path)
    rec_path = (
        raw_copy
        / "W06-DEV-TUNE-P1-C2-W06-DEV-TUNE-001"
        / "execution_receipt.json"
    )
    rec_obj = json.loads(rec_path.read_text(encoding="utf-8"))
    rec_obj["run_id"] = "W06-DEV-TUNE-P1-C1-W06-DEV-TUNE-001"
    rec_path.write_text(json.dumps(rec_obj, indent=2), encoding="utf-8")

    with pytest.raises(PlanBeforeLiveProtocolError, match="CELL_RUN_ID_MISMATCH"):
        verify_and_summarize_live_results_evidence(
            repo_root=REPO_ROOT, raw_output_root=raw_copy
        )


def test_adversarial_07_wrong_plan_binding_fails_closed(tmp_path: Path) -> None:
    raw_copy = _clone_isolated_raw_output_root(tmp_path)
    valid_plan = DevExecutionPlan.model_validate_json(
        normalize_lf_bytes((REPO_ROOT / DEV_TUNE_PLAN_REL_PATH).read_bytes())
    )
    tampered_plan = valid_plan.model_copy(update={"plan_sha256": "f" * 64})

    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="PLAN_BINDING_MISMATCH",
    ):
        verify_and_summarize_live_results_evidence(
            repo_root=REPO_ROOT,
            raw_output_root=raw_copy,
            execution_plan_override=tampered_plan,
        )


def test_adversarial_08_retry_evidence_fails_closed(tmp_path: Path) -> None:
    raw_copy = _clone_isolated_raw_output_root(tmp_path)
    cell_dir = raw_copy / "W06-DEV-TUNE-P1-C1-W06-DEV-TUNE-001"
    meta_path = cell_dir / "provider_response_metadata.json"
    rec_path = cell_dir / "execution_receipt.json"
    meta_obj = json.loads(meta_path.read_text(encoding="utf-8"))
    meta_obj["actual_http_request_count"] = 2
    meta_bytes = json.dumps(meta_obj, indent=2).encode("utf-8")
    meta_path.write_bytes(meta_bytes)

    # Update receipt pointer so it passes hash chain and hits the retry gate
    rec_obj = json.loads(rec_path.read_text(encoding="utf-8"))
    rec_obj["provider_metadata_sha256"] = hashlib.sha256(meta_bytes).hexdigest()
    rec_path.write_text(json.dumps(rec_obj, indent=2), encoding="utf-8")

    with pytest.raises(
        PlanBeforeLiveProtocolError, match="RETRY_OR_SECOND_ATTEMPT_DETECTED"
    ):
        verify_and_summarize_live_results_evidence(
            repo_root=REPO_ROOT, raw_output_root=raw_copy
        )


def test_adversarial_09_second_attempt_fails_closed(tmp_path: Path) -> None:
    raw_copy = _clone_isolated_raw_output_root(tmp_path)
    cell_dir = raw_copy / "W06-DEV-TUNE-P1-C1-W06-DEV-TUNE-001"
    rec_path = cell_dir / "execution_receipt.json"
    rec_obj = json.loads(rec_path.read_text(encoding="utf-8"))
    rec_obj["attempt_number"] = 2
    rec_path.write_text(json.dumps(rec_obj, indent=2), encoding="utf-8")

    with pytest.raises(
        PlanBeforeLiveProtocolError, match="RETRY_OR_SECOND_ATTEMPT_DETECTED"
    ):
        verify_and_summarize_live_results_evidence(
            repo_root=REPO_ROOT, raw_output_root=raw_copy
        )


def test_adversarial_10_modified_raw_tree_fails_closed(tmp_path: Path) -> None:
    raw_copy = _clone_isolated_raw_output_root(tmp_path)
    stray = (
        raw_copy
        / "W06-DEV-TUNE-P1-C1-W06-DEV-TUNE-001"
        / "stray_extra.json"
    )
    stray.write_text("{}", encoding="utf-8")

    with pytest.raises(PlanBeforeLiveProtocolError, match="UNKNOWN_FILES_IN_CELL"):
        verify_and_summarize_live_results_evidence(
            repo_root=REPO_ROOT, raw_output_root=raw_copy
        )
    assert (
        is_verified_downstream_w06_dev_tune_live_results_tree(
            REPO_ROOT, raw_output_root=raw_copy
        )
        is False
    )
    assert (
        is_verified_downstream_w06_dev_tune_live_results_file(stray, repo_root=REPO_ROOT)
        is False
    )


def test_adversarial_11_fake_summary_counts_fails_closed(tmp_path: Path) -> None:
    raw_copy = _clone_isolated_raw_output_root(tmp_path)
    cell_dir = raw_copy / "W06-DEV-TUNE-P1-C1-W06-DEV-TUNE-001"
    rec_path = cell_dir / "execution_receipt.json"
    rec_obj = json.loads(rec_path.read_text(encoding="utf-8"))
    rec_obj["final_core_pass"] = True
    rec_path.write_text(json.dumps(rec_obj, indent=2), encoding="utf-8")

    with pytest.raises(PlanBeforeLiveProtocolError, match="FINAL_CORE_PASS_MISMATCH"):
        verify_and_summarize_live_results_evidence(
            repo_root=REPO_ROOT, raw_output_root=raw_copy
        )


def test_network_kill_switch_blocks_outbound_connections() -> None:
    with pytest.raises(OutboundNetworkBlockedError):
        s = socket.socket()
        try:
            s.connect(("8.8.8.8", 53))
        finally:
            s.close()


# ==============================================================================
# AUC-RF-01 .. AUC-RF-12 AUDIT CORRECTION ADVERSARIAL TESTS (SECTIONS 6 & 7)
# ==============================================================================


def _clone_isolated_repo_for_downstream_verifier(tmp_path: Path) -> Path:
    """Create an isolated temporary repository tree containing the raw evidence tree,
    manifest, receipt, and execution plan so same-process tamper tests never touch REPO_ROOT.
    """
    tmp_repo = tmp_path / "isolated_repo"
    w06_dst = tmp_repo / "data" / "evaluation" / "w06"
    w06_dst.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        REPO_ROOT / RAW_OUTPUT_ROOT_REL_PATH,
        tmp_repo / RAW_OUTPUT_ROOT_REL_PATH,
    )
    for rel_path in (
        RESULTS_MANIFEST_REL_PATH,
        RESULTS_FREEZE_RECEIPT_REL_PATH,
        DEV_TUNE_PLAN_REL_PATH,
    ):
        shutil.copy2(REPO_ROOT / rel_path, tmp_repo / rel_path)
    return tmp_repo


def _write_canonical_json_bytes_and_sha(path: Path, payload: dict[str, Any]) -> str:
    raw = normalize_lf_bytes(
        (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode(
            "utf-8"
        )
    )
    path.write_bytes(raw)
    return sha256_bytes(raw)


def test_auc_rf_01_legitimate_frozen_tree_recognized(tmp_path: Path) -> None:
    """AUC-RF-01: legitimate frozen tree => true, and positive cache is removed."""
    assert not hasattr(rf_mod, "_VERIFIED_DOWNSTREAM_RESULTS_TREE_CACHE")
    assert is_verified_downstream_w06_dev_tune_live_results_tree(REPO_ROOT) is True
    tmp_repo = _clone_isolated_repo_for_downstream_verifier(tmp_path)
    assert is_verified_downstream_w06_dev_tune_live_results_tree(tmp_repo) is True


def test_auc_rf_02_same_process_raw_byte_tamper_fails_closed(tmp_path: Path) -> None:
    """AUC-RF-02: verify legitimate tree true, then mutate one raw byte in an ISOLATED
    temporary repo/tree, call verifier again IN THE SAME PYTHON PROCESS => false.
    """
    tmp_repo = _clone_isolated_repo_for_downstream_verifier(tmp_path)
    assert is_verified_downstream_w06_dev_tune_live_results_tree(tmp_repo) is True

    target_raw_file = (
        tmp_repo
        / RAW_OUTPUT_ROOT_REL_PATH
        / "W06-DEV-TUNE-P1-C3-W06-DEV-TUNE-001"
        / "raw_provider_response.txt"
    )
    assert (
        is_verified_downstream_w06_dev_tune_live_results_file(
            target_raw_file, repo_root=tmp_repo
        )
        is True
    )

    orig_bytes = target_raw_file.read_bytes()
    target_raw_file.write_bytes(orig_bytes[:-1] + (b"X" if orig_bytes[-1:] != b"X" else b"Y"))

    assert is_verified_downstream_w06_dev_tune_live_results_tree(tmp_repo) is False
    assert (
        is_verified_downstream_w06_dev_tune_live_results_file(
            target_raw_file, repo_root=tmp_repo
        )
        is False
    )


def test_auc_rf_03_same_process_manifest_tamper_fails_closed(tmp_path: Path) -> None:
    """AUC-RF-03: verify legitimate tree true, then mutate manifest in same process => false."""
    tmp_repo = _clone_isolated_repo_for_downstream_verifier(tmp_path)
    assert is_verified_downstream_w06_dev_tune_live_results_tree(tmp_repo) is True

    manifest_path = tmp_repo / RESULTS_MANIFEST_REL_PATH
    manifest_obj = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_obj["live_command_invocation_count"] = 2
    _write_canonical_json_bytes_and_sha(manifest_path, manifest_obj)

    assert is_verified_downstream_w06_dev_tune_live_results_tree(tmp_repo) is False
    assert (
        is_verified_downstream_w06_dev_tune_live_results_file(
            manifest_path, repo_root=tmp_repo
        )
        is False
    )


def test_auc_rf_04_same_process_receipt_tamper_fails_closed(tmp_path: Path) -> None:
    """AUC-RF-04: verify legitimate tree true, then mutate results-freeze receipt in same process => false."""
    tmp_repo = _clone_isolated_repo_for_downstream_verifier(tmp_path)
    assert is_verified_downstream_w06_dev_tune_live_results_tree(tmp_repo) is True

    receipt_path = tmp_repo / RESULTS_FREEZE_RECEIPT_REL_PATH
    receipt_obj = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt_obj["rf_checks"]["RF-01_execution_head_exact"] = "FAIL"
    _write_canonical_json_bytes_and_sha(receipt_path, receipt_obj)

    assert is_verified_downstream_w06_dev_tune_live_results_tree(tmp_repo) is False
    assert (
        is_verified_downstream_w06_dev_tune_live_results_file(
            receipt_path, repo_root=tmp_repo
        )
        is False
    )


def test_auc_rf_05_exact_legitimate_receipt_sha_recognized(tmp_path: Path) -> None:
    """AUC-RF-05: exact legitimate receipt SHA => recognized."""
    receipt_path = REPO_ROOT / RESULTS_FREEZE_RECEIPT_REL_PATH
    receipt_sha = sha256_bytes(normalize_lf_bytes(receipt_path.read_bytes()))
    assert (
        receipt_sha
        == EXPECTED_RESULTS_FREEZE_RECEIPT_FILE_SHA256
        == "5f45c31a96b3827d64b927bccde154ad9345202fbfad6f8070c9f7927c40cbfe"
    )
    assert is_verified_downstream_w06_dev_tune_live_results_tree(REPO_ROOT) is True


def test_auc_rf_06_uninspected_receipt_field_tamper_rejected_by_exact_receipt_sha(
    tmp_path: Path,
) -> None:
    """AUC-RF-06: modify a receipt field NOT previously inspected by the old verifier
    while preserving previously inspected fields => rejected because receipt file SHA differs.
    """
    tmp_repo = _clone_isolated_repo_for_downstream_verifier(tmp_path)
    assert is_verified_downstream_w06_dev_tune_live_results_tree(tmp_repo) is True

    receipt_path = tmp_repo / RESULTS_FREEZE_RECEIPT_REL_PATH
    receipt_obj = json.loads(receipt_path.read_text(encoding="utf-8"))
    # Mutate nested field not individually enumerated in top-level semantic checks
    receipt_obj["secret_scan_result"]["scanned_file_count"] = 9999
    tampered_sha = _write_canonical_json_bytes_and_sha(receipt_path, receipt_obj)
    assert tampered_sha != EXPECTED_RESULTS_FREEZE_RECEIPT_FILE_SHA256

    assert is_verified_downstream_w06_dev_tune_live_results_tree(tmp_repo) is False


def test_auc_rf_07_same_artifact_id_and_task_id_wrong_receipt_sha_rejected(
    tmp_path: Path,
) -> None:
    """AUC-RF-07: same artifact_id/task_id but wrong receipt SHA => rejected."""
    tmp_repo = _clone_isolated_repo_for_downstream_verifier(tmp_path)
    receipt_path = tmp_repo / RESULTS_FREEZE_RECEIPT_REL_PATH
    receipt_obj = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert (
        receipt_obj["artifact_id"] == "W06-DEV-TUNE-LIVE-RESULTS-FREEZE-01-RECEIPT-V1"
    )
    assert receipt_obj["task_id"] == "W06-DEV-TUNE-LIVE-RESULTS-FREEZE-01"
    receipt_obj["extra_untrusted_annotation"] = "rogue-metadata"
    tampered_sha = _write_canonical_json_bytes_and_sha(receipt_path, receipt_obj)
    assert tampered_sha != EXPECTED_RESULTS_FREEZE_RECEIPT_FILE_SHA256

    assert is_verified_downstream_w06_dev_tune_live_results_tree(tmp_repo) is False


def test_auc_rf_08_wrong_results_manifest_file_sha256_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AUC-RF-08: wrong results_manifest_file_sha256 => rejected."""
    tmp_repo = _clone_isolated_repo_for_downstream_verifier(tmp_path)
    receipt_path = tmp_repo / RESULTS_FREEZE_RECEIPT_REL_PATH
    receipt_obj = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt_obj["results_manifest_file_sha256"] = "0" * 64
    tampered_sha = _write_canonical_json_bytes_and_sha(receipt_path, receipt_obj)

    assert is_verified_downstream_w06_dev_tune_live_results_tree(tmp_repo) is False
    monkeypatch.setattr(
        rf_mod, "EXPECTED_RESULTS_FREEZE_RECEIPT_FILE_SHA256", tampered_sha
    )
    assert is_verified_downstream_w06_dev_tune_live_results_tree(tmp_repo) is False


def test_auc_rf_09_wrong_raw_evidence_tree_sha256_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AUC-RF-09: wrong raw_evidence_tree_sha256 => rejected."""
    tmp_repo = _clone_isolated_repo_for_downstream_verifier(tmp_path)
    receipt_path = tmp_repo / RESULTS_FREEZE_RECEIPT_REL_PATH
    receipt_obj = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt_obj["raw_evidence_tree_sha256"] = "0" * 64
    tampered_sha = _write_canonical_json_bytes_and_sha(receipt_path, receipt_obj)

    assert is_verified_downstream_w06_dev_tune_live_results_tree(tmp_repo) is False
    monkeypatch.setattr(
        rf_mod, "EXPECTED_RESULTS_FREEZE_RECEIPT_FILE_SHA256", tampered_sha
    )
    assert is_verified_downstream_w06_dev_tune_live_results_tree(tmp_repo) is False


def test_auc_rf_10_wrong_execution_plan_sha256_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AUC-RF-10: wrong execution_plan_sha256 => rejected."""
    tmp_repo = _clone_isolated_repo_for_downstream_verifier(tmp_path)
    receipt_path = tmp_repo / RESULTS_FREEZE_RECEIPT_REL_PATH
    receipt_obj = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt_obj["execution_plan_sha256"] = "0" * 64
    tampered_sha = _write_canonical_json_bytes_and_sha(receipt_path, receipt_obj)

    assert is_verified_downstream_w06_dev_tune_live_results_tree(tmp_repo) is False
    monkeypatch.setattr(
        rf_mod, "EXPECTED_RESULTS_FREEZE_RECEIPT_FILE_SHA256", tampered_sha
    )
    assert is_verified_downstream_w06_dev_tune_live_results_tree(tmp_repo) is False


def test_auc_rf_11_winning_prompt_selected_true_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AUC-RF-11: winning_prompt_selected=true => rejected."""
    tmp_repo = _clone_isolated_repo_for_downstream_verifier(tmp_path)
    receipt_path = tmp_repo / RESULTS_FREEZE_RECEIPT_REL_PATH
    receipt_obj = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt_obj["winning_prompt_selected"] = True
    tampered_sha = _write_canonical_json_bytes_and_sha(receipt_path, receipt_obj)

    assert is_verified_downstream_w06_dev_tune_live_results_tree(tmp_repo) is False
    monkeypatch.setattr(
        rf_mod, "EXPECTED_RESULTS_FREEZE_RECEIPT_FILE_SHA256", tampered_sha
    )
    assert is_verified_downstream_w06_dev_tune_live_results_tree(tmp_repo) is False


def test_auc_rf_12_live_provider_calls_new_positive_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AUC-RF-12: live_provider_calls_new > 0 => rejected."""
    tmp_repo = _clone_isolated_repo_for_downstream_verifier(tmp_path)
    receipt_path = tmp_repo / RESULTS_FREEZE_RECEIPT_REL_PATH
    receipt_obj = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt_obj["live_provider_calls_new"] = 1
    tampered_sha = _write_canonical_json_bytes_and_sha(receipt_path, receipt_obj)

    assert is_verified_downstream_w06_dev_tune_live_results_tree(tmp_repo) is False
    monkeypatch.setattr(
        rf_mod, "EXPECTED_RESULTS_FREEZE_RECEIPT_FILE_SHA256", tampered_sha
    )
    assert is_verified_downstream_w06_dev_tune_live_results_tree(tmp_repo) is False
