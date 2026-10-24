"""Offline verification and adversarial test suite for W06-DEV-SELECT-LIVE-RESULTS-FREEZE-01.

Covers:
- DSRF-01 through DSRF-40 (Section 22)
- Section 18: Same-process tamper & restore tests (no stale positive cache)
- Section 19: Raw tree adversarial tests (179/181 dirs, missing receipt/evaluation,
  duplicate/unknown run ID, 1 raw byte changed, receipt failure classification changed,
  evaluation metric changed, attempt=2, retry evidence, call count 181, model mismatch,
  cost value altered, manifest raw-tree SHA altered, freeze receipt manifest SHA altered,
  same filename with fake contents)
- Section 20: Downstream firewall (MODEL_WINNER_SELECTED=false, selected_model_id=null,
  STOCHASTICITY_EXECUTION_STARTED=false, FINAL100_USED=false, LIVE_PROVIDER_CALLS_NEW=0)
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
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
    compute_scientific_code_bundle_sha256,
    normalize_lf_bytes,
    sha256_bytes,
)
import freeze_w06_dev_select_live_results as dsrf  # noqa: E402
import run_w06_dev_select_live_v1 as launcher  # noqa: E402


@pytest.fixture(autouse=True)
def _enforce_offline_network_kill_switch():
    """Run every test in this module under NetworkKillSwitchGuard (0 outbound network calls)."""
    with dsrf.NetworkKillSwitchGuard():
        yield


@pytest.fixture(scope="module")
def verified_freeze_out() -> dict[str, Any]:
    """Run full `--verify-only` verification once at module scope for read-only DSRF assertions."""
    return dsrf.generate_or_verify_results_freeze_artifacts(
        repo_root=REPO_ROOT, write_artifacts=False
    )


@pytest.fixture(scope="module")
def manifest_obj() -> dict[str, Any]:
    return json.loads(
        (REPO_ROOT / dsrf.RESULTS_MANIFEST_REL_PATH).read_text(encoding="utf-8")
    )


@pytest.fixture(scope="module")
def receipt_obj() -> dict[str, Any]:
    return json.loads(
        (REPO_ROOT / dsrf.RESULTS_FREEZE_RECEIPT_REL_PATH).read_text(encoding="utf-8")
    )


@pytest.fixture(scope="module")
def temp_evidence_workspace(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create a temporary copy of the raw evidence tree, manifest, and freeze receipt for same-process tamper & adversarial tests."""
    ws = tmp_path_factory.mktemp("w06_dev_select_rf_adv")
    src_raw = REPO_ROOT / dsrf.RAW_OUTPUT_ROOT_REL_PATH
    dst_raw = ws / dsrf.RAW_OUTPUT_ROOT_REL_PATH
    shutil.copytree(src_raw, dst_raw)

    for rel in (
        dsrf.RESULTS_MANIFEST_REL_PATH,
        dsrf.RESULTS_FREEZE_RECEIPT_REL_PATH,
        dsrf.DEV_SELECT_PLAN_REL_PATH,
        dsrf.PLAN_FREEZE_RECEIPT_REL_PATH,
        dsrf.PROMPT_FREEZE_REL_PATH,
        dsrf.PROMPT_SELECTION_ARTIFACT_REL_PATH,
        dsrf.AUTHORIZATION_REL_PATH,
        dsrf.STAGE_A_RECEIPT_REL_PATH,
    ):
        s_file = REPO_ROOT / rel
        d_file = ws / rel
        d_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(s_file, d_file)
    return ws


# ==============================================================================
# 1. DSRF-01 .. DSRF-40 VERIFICATION MATRIX (SECTION 22)
# ==============================================================================


def test_dsrf_01_source_head_exact(
    verified_freeze_out: dict[str, Any],
    manifest_obj: dict[str, Any],
    receipt_obj: dict[str, Any],
) -> None:
    """DSRF-01: Verify source develop SHA eac86a38f6b457c9b6ff078f26c4f953a9fc98a7 is bound in manifest, receipt, and all 180 cells."""
    expected_sha = "eac86a38f6b457c9b6ff078f26c4f953a9fc98a7"
    assert verified_freeze_out["source_develop_sha"] == expected_sha
    assert manifest_obj["source_develop_sha"] == expected_sha
    assert manifest_obj["execution_head_sha"] == expected_sha
    assert receipt_obj["source_develop_sha"] == expected_sha
    assert receipt_obj["base_execution_head_sha"] == expected_sha
    assert receipt_obj["dsrf_checks"]["DSRF-01_source_head_exact"] == "PASS"


def test_dsrf_02_plan_internal_and_file_sha_exact(
    manifest_obj: dict[str, Any],
    receipt_obj: dict[str, Any],
) -> None:
    """DSRF-02: Verify DEV_SELECT execution plan internal and file SHA256s match frozen upstream authorities."""
    plan_bytes = normalize_lf_bytes(
        (REPO_ROOT / dsrf.DEV_SELECT_PLAN_REL_PATH).read_bytes()
    )
    assert (
        sha256_bytes(plan_bytes)
        == dsrf.EXPECTED_DEV_SELECT_PLAN_FILE_SHA256
        == "c519baf7cd2557b5e1dd2699a5ceaec592af015d7bc6dcc83abf63892a8a329a"
    )
    assert (
        manifest_obj["execution_plan_internal_sha256"]
        == dsrf.EXPECTED_DEV_SELECT_PLAN_INTERNAL_SHA256
        == "de04255989a9e3bd8c2e39c766432487dce4ccd0612d5dba73b3476cbc9d0c6d"
    )
    assert (
        receipt_obj["execution_plan_internal_sha256"]
        == dsrf.EXPECTED_DEV_SELECT_PLAN_INTERNAL_SHA256
    )


def test_dsrf_03_launcher_lf_and_git_blob_sha_exact(
    manifest_obj: dict[str, Any],
    receipt_obj: dict[str, Any],
) -> None:
    """DSRF-03: Verify launcher LF SHA256 and git blob SHA match frozen launcher."""
    launcher_bytes = normalize_lf_bytes(
        (REPO_ROOT / dsrf.EXPECTED_LAUNCHER_REL_PATH).read_bytes()
    )
    assert (
        sha256_bytes(launcher_bytes)
        == dsrf.EXPECTED_LAUNCHER_LF_SHA256
        == "cd36b8ecad24059edb597c0039bd6e760a37ee8b4f36f49077801c65e7ddc7bf"
    )
    assert manifest_obj["launcher_lf_sha256"] == dsrf.EXPECTED_LAUNCHER_LF_SHA256
    assert (
        manifest_obj["launcher_git_blob_sha"]
        == dsrf.EXPECTED_LAUNCHER_GIT_BLOB_SHA
        == "ad597560ca149f8b78786c63feb64d63ac399971"
    )
    assert receipt_obj["launcher_lf_sha256"] == dsrf.EXPECTED_LAUNCHER_LF_SHA256


def test_dsrf_04_authorization_file_and_internal_sha_exact(
    manifest_obj: dict[str, Any],
    receipt_obj: dict[str, Any],
) -> None:
    """DSRF-04: Verify live authorization file and internal SHA256s match frozen upstream authorities."""
    auth_bytes = normalize_lf_bytes(
        (REPO_ROOT / dsrf.AUTHORIZATION_REL_PATH).read_bytes()
    )
    assert (
        sha256_bytes(auth_bytes)
        == dsrf.EXPECTED_AUTHORIZATION_FILE_SHA256
        == "247c0f201d8b900a1e0356d874891ba6e2884138b1ddd8500dfedb663f04f5f7"
    )
    assert (
        manifest_obj["authorization_internal_sha256"]
        == dsrf.EXPECTED_AUTHORIZATION_INTERNAL_SHA256
        == "31cebcf5aafa7a575d4bf1327fc9d454a2817c2acbbdb2c087d8c1210e8ec504"
    )
    assert (
        receipt_obj["authorization_internal_sha256"]
        == dsrf.EXPECTED_AUTHORIZATION_INTERNAL_SHA256
    )


def test_dsrf_05_stage_a_file_and_internal_sha_exact(
    manifest_obj: dict[str, Any],
    receipt_obj: dict[str, Any],
) -> None:
    """DSRF-05: Verify Stage-A freeze receipt file and internal SHA256s match frozen upstream authorities."""
    sa_bytes = normalize_lf_bytes(
        (REPO_ROOT / dsrf.STAGE_A_RECEIPT_REL_PATH).read_bytes()
    )
    assert (
        sha256_bytes(sa_bytes)
        == dsrf.EXPECTED_STAGE_A_FILE_SHA256
        == "dd31582860e899b865d3dacd52bd1f92786ee6cf31d851e68e9050d93c451a26"
    )
    assert (
        manifest_obj["stage_a_internal_sha256"]
        == dsrf.EXPECTED_STAGE_A_INTERNAL_SHA256
        == "1b933067516b7142b4250870a18e6deef216c6854b1c9790d01830d196dde014"
    )
    assert (
        receipt_obj["stage_a_internal_sha256"]
        == dsrf.EXPECTED_STAGE_A_INTERNAL_SHA256
    )


def test_dsrf_06_scientific_code_bundle_sha_exact(
    verified_freeze_out: dict[str, Any],
    manifest_obj: dict[str, Any],
    receipt_obj: dict[str, Any],
) -> None:
    """DSRF-06: Verify SCIENTIFIC_CODE_BUNDLE_SHA256 == 0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3."""
    bundle_sha = compute_scientific_code_bundle_sha256(repo_root=REPO_ROOT)
    assert (
        bundle_sha
        == dsrf.EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
        == "0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3"
    )
    assert verified_freeze_out["scientific_code_bundle_sha256"] == bundle_sha
    assert manifest_obj["scientific_code_bundle_sha256"] == bundle_sha
    assert receipt_obj["scientific_code_bundle_sha256"] == bundle_sha


def test_dsrf_07_cell_directory_count_180_exact(
    manifest_obj: dict[str, Any],
    receipt_obj: dict[str, Any],
) -> None:
    """DSRF-07: Verify exactly 180 cell directories exist matching the 180 assigned run IDs."""
    raw_root = REPO_ROOT / dsrf.RAW_OUTPUT_ROOT_REL_PATH
    cell_dirs = [p for p in raw_root.iterdir() if p.is_dir()]
    assert len(cell_dirs) == 180
    assert manifest_obj["assigned_cells"] == 180
    assert manifest_obj["cell_directory_count"] == 180
    assert len(manifest_obj["assigned_run_ids"]) == 180
    assert receipt_obj["execution_summary"]["cell_directories"] == 180


def test_dsrf_08_execution_receipt_count_180_exact(
    manifest_obj: dict[str, Any],
    receipt_obj: dict[str, Any],
) -> None:
    """DSRF-08: Verify exactly 180 execution_receipt.json files exist and are hashed in receipt."""
    assert manifest_obj["execution_receipt_count"] == 180
    assert receipt_obj["execution_summary"]["execution_receipts"] == 180
    assert len(receipt_obj["execution_receipt_file_hashes_by_run_id"]) == 180


def test_dsrf_09_evaluation_result_count_180_exact(
    manifest_obj: dict[str, Any],
    receipt_obj: dict[str, Any],
) -> None:
    """DSRF-09: Verify exactly 180 evaluation_result.json files exist."""
    assert manifest_obj["evaluation_result_count"] == 180
    assert receipt_obj["execution_summary"]["evaluation_results"] == 180


def test_dsrf_10_raw_provider_response_count_180_exact(
    manifest_obj: dict[str, Any],
    receipt_obj: dict[str, Any],
) -> None:
    """DSRF-10: Verify exactly 180 raw_provider_response.txt files exist."""
    assert manifest_obj["raw_provider_response_count"] == 180
    assert receipt_obj["execution_summary"]["raw_provider_responses"] == 180


def test_dsrf_11_parsed_plan_response_count_9_exact(
    verified_freeze_out: dict[str, Any],
    manifest_obj: dict[str, Any],
    receipt_obj: dict[str, Any],
) -> None:
    """DSRF-11: Verify exactly 9 parsed_plan_response.json files exist (C1=1, C2=8, C3=0)."""
    assert verified_freeze_out["parsed_plan_response_count"] == 9
    assert manifest_obj["parsed_plan_response_count"] == 9
    assert receipt_obj["execution_summary"]["parsed_plan_responses"] == 9


def test_dsrf_12_live_provider_calls_attempted_180_exact(
    verified_freeze_out: dict[str, Any],
    manifest_obj: dict[str, Any],
    receipt_obj: dict[str, Any],
) -> None:
    """DSRF-12: Verify LIVE_PROVIDER_CALLS_ATTEMPTED == 180 and MAXIMUM_ALLOWED_LIVE_PROVIDER_CALLS == 180."""
    assert verified_freeze_out["live_provider_calls_attempted"] == 180
    assert manifest_obj["live_provider_calls_attempted"] == 180
    assert manifest_obj["maximum_allowed_live_provider_calls"] == 180
    assert manifest_obj["transport_starting_count"] == 180
    assert manifest_obj["transport_completed_count"] == 180
    assert manifest_obj["transport_ambiguous_count"] == 0
    assert receipt_obj["execution_summary"]["live_provider_calls_attempted"] == 180


def test_dsrf_13_retry_calls_zero(
    verified_freeze_out: dict[str, Any],
    manifest_obj: dict[str, Any],
    receipt_obj: dict[str, Any],
) -> None:
    """DSRF-13: Verify RETRY_CALLS == 0 across all 180 cells."""
    assert verified_freeze_out["retry_calls"] == 0
    assert manifest_obj["retry_calls"] == 0
    assert receipt_obj["execution_summary"]["retry_calls"] == 0


def test_dsrf_14_rerun_cells_zero(
    verified_freeze_out: dict[str, Any],
    manifest_obj: dict[str, Any],
    receipt_obj: dict[str, Any],
) -> None:
    """DSRF-14: Verify RERUN_CELLS == 0 across all 180 cells."""
    assert verified_freeze_out["rerun_cells"] == 0
    assert manifest_obj["rerun_cells"] == 0
    assert receipt_obj["execution_summary"]["rerun_cells"] == 0


def test_dsrf_15_attempt_number_1_for_all_180_cells() -> None:
    """DSRF-15: Verify attempt_number == 1 and actual_http_request_count == 1 for every assigned cell."""
    raw_root = REPO_ROOT / dsrf.RAW_OUTPUT_ROOT_REL_PATH
    count = 0
    for cdir in sorted(raw_root.iterdir()):
        rec = json.loads((cdir / "execution_receipt.json").read_text(encoding="utf-8"))
        req = json.loads((cdir / "request_manifest.json").read_text(encoding="utf-8"))
        meta = json.loads(
            (cdir / "provider_response_metadata.json").read_text(encoding="utf-8")
        )
        assert rec["attempt_number"] == 1
        assert req["attempt_number"] == 1
        assert req["retry"] == 0
        assert meta["actual_http_request_count"] == 1
        count += 1
    assert count == 180


def test_dsrf_16_primary_failure_classification_authority_execution_receipt(
    verified_freeze_out: dict[str, Any],
    manifest_obj: dict[str, Any],
    receipt_obj: dict[str, Any],
) -> None:
    """DSRF-16: Verify primary failure classification authority is execution_receipt.failure_classification."""
    assert (
        verified_freeze_out["primary_failure_classification_authority"]
        == "execution_receipt.failure_classification"
    )
    assert (
        manifest_obj["primary_failure_classification_authority"]
        == "execution_receipt.failure_classification"
    )
    assert (
        receipt_obj["execution_summary"]["primary_failure_classification_authority"]
        == "execution_receipt.failure_classification"
    )


def test_dsrf_17_primary_failure_taxonomy_counts_exact(
    verified_freeze_out: dict[str, Any],
) -> None:
    """DSRF-17: Verify primary failure classification counts (total and by candidate) match Section 7."""
    fc = verified_freeze_out["failure_classification_counts"]
    assert fc["total"] == {
        "HTTP_429": 35,
        "HTTP_5XX": 10,
        "HTTP_ERROR": 60,
        "NONE": 9,
        "TIMEOUT": 66,
    }
    assert sum(fc["total"].values()) == 180
    assert fc["by_candidate"] == {
        "C1": {
            "HTTP_429": 35,
            "HTTP_5XX": 10,
            "HTTP_ERROR": 0,
            "NONE": 1,
            "TIMEOUT": 14,
        },
        "C2": {
            "HTTP_429": 0,
            "HTTP_5XX": 0,
            "HTTP_ERROR": 0,
            "NONE": 8,
            "TIMEOUT": 52,
        },
        "C3": {
            "HTTP_429": 0,
            "HTTP_5XX": 0,
            "HTTP_ERROR": 60,
            "NONE": 0,
            "TIMEOUT": 0,
        },
    }


def test_dsrf_18_candidate_result_completeness_counts_exact(
    manifest_obj: dict[str, Any],
) -> None:
    """DSRF-18: Verify result completeness counts by candidate match Section 8."""
    assert manifest_obj["result_counts_by_candidate"] == {
        "C1": {
            "assigned": 60,
            "attempted": 60,
            "execution_receipts": 60,
            "evaluation_results": 60,
            "parsed_plan_responses": 1,
        },
        "C2": {
            "assigned": 60,
            "attempted": 60,
            "execution_receipts": 60,
            "evaluation_results": 60,
            "parsed_plan_responses": 8,
        },
        "C3": {
            "assigned": 60,
            "attempted": 60,
            "execution_receipts": 60,
            "evaluation_results": 60,
            "parsed_plan_responses": 0,
        },
    }


def test_dsrf_19_valid_run_and_schema_counts_exact(
    verified_freeze_out: dict[str, Any],
) -> None:
    """DSRF-19: Verify VALID_RUN_AND_SCHEMA counts (C1=1/60, C2=8/60, C3=0/60, total=9/180)."""
    v = verified_freeze_out["valid_run_and_schema_counts"]
    assert v["total"] == {"false": 171, "true": 9}
    assert v["by_candidate"]["C1"]["rate_fraction"] == "1/60"
    assert v["by_candidate"]["C2"]["rate_fraction"] == "8/60"
    assert v["by_candidate"]["C3"]["rate_fraction"] == "0/60"


def test_dsrf_20_exact_grounding_pass_counts_exact(
    verified_freeze_out: dict[str, Any],
) -> None:
    """DSRF-20: Verify EXACT_GROUNDING_PASS counts (C1=1/60, C2=8/60, C3=0/60, total=9/180)."""
    g = verified_freeze_out["exact_grounding_pass_counts"]
    assert g["total"] == {"false": 171, "true": 9}
    assert g["by_candidate"]["C1"]["rate_fraction"] == "1/60"
    assert g["by_candidate"]["C2"]["rate_fraction"] == "8/60"
    assert g["by_candidate"]["C3"]["rate_fraction"] == "0/60"


def test_dsrf_21_final_core_pass_counts_exact(
    verified_freeze_out: dict[str, Any],
) -> None:
    """DSRF-21: Verify FINAL_CORE_PASS counts (C1=1/60, C2=8/60, C3=0/60, total=9/180)."""
    c = verified_freeze_out["final_core_pass_counts"]
    assert c["total"] == {"false": 171, "true": 9}
    assert c["by_candidate"]["C1"]["rate_fraction"] == "1/60"
    assert c["by_candidate"]["C2"]["rate_fraction"] == "8/60"
    assert c["by_candidate"]["C3"]["rate_fraction"] == "0/60"


def test_dsrf_22_all_candidate_denominators_60(
    verified_freeze_out: dict[str, Any],
) -> None:
    """DSRF-22: Verify all candidate denominators remain 60 across all three primary metrics (no failure exclusion)."""
    for metric_key in (
        "valid_run_and_schema_counts",
        "exact_grounding_pass_counts",
        "final_core_pass_counts",
    ):
        by_cand = verified_freeze_out[metric_key]["by_candidate"]
        for cid in ("C1", "C2", "C3"):
            assert by_cand[cid]["denominator"] == 60
            assert by_cand[cid]["pass_count"] + by_cand[cid]["fail_count"] == 60


def test_dsrf_23_model_id_mismatch_count_zero(
    verified_freeze_out: dict[str, Any],
    manifest_obj: dict[str, Any],
    receipt_obj: dict[str, Any],
) -> None:
    """DSRF-23: Verify MODEL_ID_MISMATCH_COUNT == 0."""
    assert verified_freeze_out["model_id_mismatch_count"] == 0
    assert manifest_obj["model_id_mismatch_count"] == 0
    assert receipt_obj["execution_summary"]["model_id_mismatch_count"] == 0


def test_dsrf_24_candidate_model_integrity_breakdown_exact(
    manifest_obj: dict[str, Any],
) -> None:
    """DSRF-24: Verify candidate model integrity breakdown matches Section 11."""
    mi = manifest_obj["model_integrity_by_candidate"]
    assert mi["C1"]["assigned"] == 60
    assert mi["C1"]["verified_returned_model_matches"] == 1
    assert mi["C1"]["transport_failure_unverified"] == 59
    assert mi["C1"]["mismatch"] == 0

    assert mi["C2"]["assigned"] == 60
    assert mi["C2"]["verified_returned_model_matches"] == 8
    assert mi["C2"]["transport_failure_unverified"] == 52
    assert mi["C2"]["mismatch"] == 0

    assert mi["C3"]["assigned"] == 60
    assert mi["C3"]["verified_returned_model_matches"] == 0
    assert mi["C3"]["transport_failure_unverified"] == 60
    assert mi["C3"]["mismatch"] == 0


def test_dsrf_25_authoritative_cost_cell_count_9_exact(
    verified_freeze_out: dict[str, Any],
    manifest_obj: dict[str, Any],
    receipt_obj: dict[str, Any],
) -> None:
    """DSRF-25: Verify AUTHORITATIVE_COST_CELL_COUNT == 9 (C1=1, C2=8, C3=0)."""
    assert verified_freeze_out["authoritative_cost_cell_count"] == 9
    assert manifest_obj["authoritative_cost_cell_count"] == 9
    assert receipt_obj["execution_summary"]["authoritative_cost_cell_count"] == 9
    assert (
        manifest_obj["cost_accounting_label"]
        == "AUTHORITATIVE_RECEIPT_COST_AVAILABLE_ONLY"
    )


def test_dsrf_26_total_canonical_cost_usd_0_6468966_exact(
    verified_freeze_out: dict[str, Any],
    manifest_obj: dict[str, Any],
    receipt_obj: dict[str, Any],
) -> None:
    """DSRF-26: Verify TOTAL_CANONICAL_COST_USD == 0.6468966."""
    assert verified_freeze_out["total_canonical_cost_usd"] == "0.6468966"
    assert manifest_obj["total_canonical_cost_usd"] == "0.6468966"
    assert receipt_obj["execution_summary"]["total_canonical_cost_usd"] == "0.6468966"
    assert manifest_obj["cost_by_candidate_usd"] == {
        "C1": {
            "authoritative_cost_cells": 1,
            "canonical_cost_usd_decimal": "0.0266516",
        },
        "C2": {
            "authoritative_cost_cells": 8,
            "canonical_cost_usd_decimal": "0.620245",
        },
        "C3": {
            "authoritative_cost_cells": 0,
            "canonical_cost_usd_decimal": "0",
        },
    }


def test_dsrf_27_raw_evidence_tree_hash_deterministic_two_passes() -> None:
    """DSRF-27: Verify two independent passes of raw evidence tree hashing produce identical metadata."""
    pass1 = dsrf._compute_raw_evidence_tree_pass(REPO_ROOT)
    pass2 = dsrf._compute_raw_evidence_tree_pass(REPO_ROOT)
    assert pass1 == pass2
    assert pass1["raw_evidence_file_count"] == 1629
    assert pass1["raw_evidence_total_bytes"] == 16264062
    assert pass1["raw_evidence_max_file_bytes"] == 96143
    assert (
        pass1["raw_evidence_tree_sha256"]
        == dsrf.EXPECTED_RAW_EVIDENCE_TREE_SHA256
        == "d5c4e53952500655b656a624657a3cf1ec7aae685809c9e53a318459cc319817"
    )


def test_dsrf_28_manifest_binds_raw_evidence_tree(
    manifest_obj: dict[str, Any],
) -> None:
    """DSRF-28: Verify results manifest binds exact raw evidence tree metadata and file manifest."""
    assert manifest_obj["raw_evidence_file_count"] == 1629
    assert manifest_obj["raw_evidence_total_bytes"] == 16264062
    assert manifest_obj["raw_evidence_max_file_bytes"] == 96143
    assert (
        manifest_obj["raw_evidence_tree_sha256"]
        == dsrf.EXPECTED_RAW_EVIDENCE_TREE_SHA256
    )
    assert len(manifest_obj["ordered_raw_file_manifest"]) == 1629
    assert (
        manifest_obj["results_manifest_sha256"]
        == dsrf.EXPECTED_RESULTS_MANIFEST_INTERNAL_SHA256
    )


def test_dsrf_29_receipt_binds_manifest_and_raw_tree(
    receipt_obj: dict[str, Any],
) -> None:
    """DSRF-29: Verify freeze receipt binds results manifest file/internal SHA256 and raw evidence tree SHA256."""
    assert (
        receipt_obj["results_manifest_file_sha256"]
        == dsrf.EXPECTED_RESULTS_MANIFEST_FILE_SHA256
    )
    assert (
        receipt_obj["results_manifest_internal_sha256"]
        == dsrf.EXPECTED_RESULTS_MANIFEST_INTERNAL_SHA256
    )
    assert (
        receipt_obj["raw_evidence_tree_sha256"]
        == dsrf.EXPECTED_RAW_EVIDENCE_TREE_SHA256
    )
    assert (
        receipt_obj["results_freeze_receipt_sha256"]
        == dsrf.EXPECTED_RESULTS_FREEZE_RECEIPT_INTERNAL_SHA256
    )


def test_dsrf_30_preflight_request_identity_180_of_180(
    verified_freeze_out: dict[str, Any],
) -> None:
    """DSRF-30: Verify all 180 cell wire requests match the canonical preflight request set SHA256."""
    assert verified_freeze_out["request_identity_match"] == "180/180"


def test_dsrf_31_per_cell_hash_chains_180_of_180(
    verified_freeze_out: dict[str, Any],
) -> None:
    """DSRF-31: Verify per-cell hash chains (receipt -> request, raw response, metadata, evaluation, parsed) for all 180 cells."""
    assert verified_freeze_out["cell_hash_chain_valid"] == "180/180"


def test_dsrf_32_same_process_raw_tamper_rejected(
    temp_evidence_workspace: Path,
) -> None:
    """DSRF-32 & Section 18: Same-process tamper of raw_provider_response.txt -> False -> restore -> True."""
    raw_root = temp_evidence_workspace / dsrf.RAW_OUTPUT_ROOT_REL_PATH
    man_path = temp_evidence_workspace / dsrf.RESULTS_MANIFEST_REL_PATH
    rec_path = temp_evidence_workspace / dsrf.RESULTS_FREEZE_RECEIPT_REL_PATH

    assert dsrf.is_verified_downstream_w06_dev_select_live_results_tree(
        REPO_ROOT,
        raw_output_root=raw_root,
        results_manifest_path=man_path,
        results_freeze_receipt_path=rec_path,
    )

    target_file = (
        raw_root / "W06-DEV-SELECT-P1-C1-W06-DEV-SELECT-001" / "raw_provider_response.txt"
    )
    orig_bytes = target_file.read_bytes()
    try:
        target_file.write_bytes(orig_bytes + b" ")
        assert not dsrf.is_verified_downstream_w06_dev_select_live_results_tree(
            REPO_ROOT,
            raw_output_root=raw_root,
            results_manifest_path=man_path,
            results_freeze_receipt_path=rec_path,
        )
        with pytest.raises(PlanBeforeLiveProtocolError):
            dsrf.verify_committed_results_freeze_artifacts_from_disk(
                REPO_ROOT,
                raw_output_root=raw_root,
                results_manifest_path=man_path,
                results_freeze_receipt_path=rec_path,
                verify_preflight_dry_run=False,
            )
    finally:
        target_file.write_bytes(orig_bytes)

    assert dsrf.is_verified_downstream_w06_dev_select_live_results_tree(
        REPO_ROOT,
        raw_output_root=raw_root,
        results_manifest_path=man_path,
        results_freeze_receipt_path=rec_path,
    )


def test_dsrf_33_same_process_receipt_tamper_rejected(
    temp_evidence_workspace: Path,
) -> None:
    """DSRF-33 & Section 18: Same-process tamper of execution_receipt.json -> False -> restore -> True."""
    raw_root = temp_evidence_workspace / dsrf.RAW_OUTPUT_ROOT_REL_PATH
    man_path = temp_evidence_workspace / dsrf.RESULTS_MANIFEST_REL_PATH
    rec_path = temp_evidence_workspace / dsrf.RESULTS_FREEZE_RECEIPT_REL_PATH

    assert dsrf.is_verified_downstream_w06_dev_select_live_results_tree(
        REPO_ROOT,
        raw_output_root=raw_root,
        results_manifest_path=man_path,
        results_freeze_receipt_path=rec_path,
    )

    target_file = (
        raw_root / "W06-DEV-SELECT-P1-C1-W06-DEV-SELECT-001" / "execution_receipt.json"
    )
    orig_bytes = target_file.read_bytes()
    try:
        obj = json.loads(orig_bytes.decode("utf-8"))
        obj["failure_classification"] = "DevCellFailureClassification.TIMEOUT"
        target_file.write_text(json.dumps(obj, indent=2), encoding="utf-8")
        assert not dsrf.is_verified_downstream_w06_dev_select_live_results_tree(
            REPO_ROOT,
            raw_output_root=raw_root,
            results_manifest_path=man_path,
            results_freeze_receipt_path=rec_path,
        )
    finally:
        target_file.write_bytes(orig_bytes)

    assert dsrf.is_verified_downstream_w06_dev_select_live_results_tree(
        REPO_ROOT,
        raw_output_root=raw_root,
        results_manifest_path=man_path,
        results_freeze_receipt_path=rec_path,
    )


def test_dsrf_34_same_process_evaluation_tamper_rejected(
    temp_evidence_workspace: Path,
) -> None:
    """DSRF-34 & Section 18: Same-process tamper of evaluation_result.json -> False -> restore -> True."""
    raw_root = temp_evidence_workspace / dsrf.RAW_OUTPUT_ROOT_REL_PATH
    man_path = temp_evidence_workspace / dsrf.RESULTS_MANIFEST_REL_PATH
    rec_path = temp_evidence_workspace / dsrf.RESULTS_FREEZE_RECEIPT_REL_PATH

    assert dsrf.is_verified_downstream_w06_dev_select_live_results_tree(
        REPO_ROOT,
        raw_output_root=raw_root,
        results_manifest_path=man_path,
        results_freeze_receipt_path=rec_path,
    )

    target_file = (
        raw_root / "W06-DEV-SELECT-P1-C1-W06-DEV-SELECT-026" / "evaluation_result.json"
    )
    orig_bytes = target_file.read_bytes()
    try:
        obj = json.loads(orig_bytes.decode("utf-8"))
        obj["core_scenario_pass"] = False
        target_file.write_text(json.dumps(obj, indent=2), encoding="utf-8")
        assert not dsrf.is_verified_downstream_w06_dev_select_live_results_tree(
            REPO_ROOT,
            raw_output_root=raw_root,
            results_manifest_path=man_path,
            results_freeze_receipt_path=rec_path,
        )
    finally:
        target_file.write_bytes(orig_bytes)

    assert dsrf.is_verified_downstream_w06_dev_select_live_results_tree(
        REPO_ROOT,
        raw_output_root=raw_root,
        results_manifest_path=man_path,
        results_freeze_receipt_path=rec_path,
    )


def test_dsrf_35_same_process_manifest_and_receipt_tamper_rejected(
    temp_evidence_workspace: Path,
) -> None:
    """DSRF-35 & Section 18: Same-process tamper of manifest and freeze receipt -> False -> restore -> True."""
    raw_root = temp_evidence_workspace / dsrf.RAW_OUTPUT_ROOT_REL_PATH
    man_path = temp_evidence_workspace / dsrf.RESULTS_MANIFEST_REL_PATH
    rec_path = temp_evidence_workspace / dsrf.RESULTS_FREEZE_RECEIPT_REL_PATH

    orig_man = man_path.read_bytes()
    orig_rec = rec_path.read_bytes()

    # 1. Tamper manifest
    try:
        m_obj = json.loads(orig_man.decode("utf-8"))
        m_obj["raw_evidence_tree_sha256"] = "0" * 64
        man_path.write_text(json.dumps(m_obj, indent=2), encoding="utf-8")
        assert not dsrf.is_verified_downstream_w06_dev_select_live_results_tree(
            REPO_ROOT,
            raw_output_root=raw_root,
            results_manifest_path=man_path,
            results_freeze_receipt_path=rec_path,
        )
    finally:
        man_path.write_bytes(orig_man)

    assert dsrf.is_verified_downstream_w06_dev_select_live_results_tree(
        REPO_ROOT,
        raw_output_root=raw_root,
        results_manifest_path=man_path,
        results_freeze_receipt_path=rec_path,
    )

    # 2. Tamper freeze receipt
    try:
        r_obj = json.loads(orig_rec.decode("utf-8"))
        r_obj["results_manifest_file_sha256"] = "f" * 64
        rec_path.write_text(json.dumps(r_obj, indent=2), encoding="utf-8")
        assert not dsrf.is_verified_downstream_w06_dev_select_live_results_tree(
            REPO_ROOT,
            raw_output_root=raw_root,
            results_manifest_path=man_path,
            results_freeze_receipt_path=rec_path,
        )
    finally:
        rec_path.write_bytes(orig_rec)

    assert dsrf.is_verified_downstream_w06_dev_select_live_results_tree(
        REPO_ROOT,
        raw_output_root=raw_root,
        results_manifest_path=man_path,
        results_freeze_receipt_path=rec_path,
    )


def test_dsrf_36_stateless_verifier_no_positive_cache() -> None:
    """DSRF-36: Verify `freeze_w06_dev_select_live_results` contains no positive verification cache or lru_cache."""
    src_text = (REPO_ROOT / "scripts/freeze_w06_dev_select_live_results.py").read_text(
        encoding="utf-8"
    )
    assert "lru_cache" not in src_text
    assert "functools.cache" not in src_text
    assert "_VERIFIED_CACHE" not in src_text


def test_dsrf_37_model_winner_selected_false_and_selected_model_null(
    verified_freeze_out: dict[str, Any],
    manifest_obj: dict[str, Any],
    receipt_obj: dict[str, Any],
) -> None:
    """DSRF-37 & Section 10: Verify MODEL_WINNER_SELECTED == false and selected_model_id == null."""
    assert verified_freeze_out["model_winner_selected"] is False
    assert verified_freeze_out["selected_model_id"] is None
    assert manifest_obj["model_winner_selected"] is False
    assert manifest_obj["selected_model_id"] is None
    assert receipt_obj["model_winner_selected"] is False
    assert receipt_obj["selected_model_id"] is None

    for forbidden_rel in dsrf.FORBIDDEN_DOWNSTREAM_MODEL_SELECTION_REL_PATHS:
        assert not (REPO_ROOT / forbidden_rel).exists()


def test_dsrf_38_stochasticity_execution_started_false(
    verified_freeze_out: dict[str, Any],
    manifest_obj: dict[str, Any],
    receipt_obj: dict[str, Any],
) -> None:
    """DSRF-38 & Section 20: Verify STOCHASTICITY_EXECUTION_STARTED == false."""
    assert verified_freeze_out["stochasticity_execution_started"] is False
    assert manifest_obj["stochasticity_execution_started"] is False
    assert receipt_obj["stochasticity_execution_started"] is False


def test_dsrf_39_final100_used_false_and_untouched(
    verified_freeze_out: dict[str, Any],
    manifest_obj: dict[str, Any],
    receipt_obj: dict[str, Any],
) -> None:
    """DSRF-39 & Section 20: Verify FINAL100_USED == false and Final100/P11 artifacts are byte-identical."""
    assert verified_freeze_out["final100_used"] is False
    assert manifest_obj["final100_used"] is False
    assert receipt_obj["final100_used"] is False

    f100_sha = sha256_bytes(
        normalize_lf_bytes(
            (REPO_ROOT / dsrf.FORBIDDEN_FINAL100_SCENARIOS_REL_PATH).read_bytes()
        )
    )
    p11_sha = sha256_bytes(
        normalize_lf_bytes(
            (REPO_ROOT / dsrf.FORBIDDEN_P11_MANIFEST_REL_PATH).read_bytes()
        )
    )
    assert f100_sha == FORBIDDEN_FINAL100_BUNDLE_SHA256
    assert p11_sha == FORBIDDEN_P11_MANIFEST_SHA256


def test_dsrf_40_live_provider_calls_new_zero_and_secret_scan_pass(
    verified_freeze_out: dict[str, Any],
    manifest_obj: dict[str, Any],
    receipt_obj: dict[str, Any],
) -> None:
    """DSRF-40: Verify LIVE_PROVIDER_CALLS_NEW == 0 and secret leak scan passes across all 1,629 raw files."""
    assert verified_freeze_out["live_provider_calls_new"] == 0
    assert verified_freeze_out["secret_leak_scan"] == "PASS"
    assert manifest_obj["live_provider_calls_new"] == 0
    assert receipt_obj["live_provider_calls_new"] == 0
    assert receipt_obj["secret_scan_result"] == {
        "secret_leak_scan": "PASS",
        "scanned_file_count": 1629,
        "secret_leak_detected": False,
    }


# ==============================================================================
# 2. SECTION 19 RAW TREE ADVERSARIAL TESTS
# ==============================================================================


def test_section_19_adversarial_179_and_181_cell_dirs(
    temp_evidence_workspace: Path,
    tmp_path: Path,
) -> None:
    """Section 19: Fail closed on 179 cell dirs (missing cell) and 181 cell dirs (extra unknown cell)."""
    raw_root = temp_evidence_workspace / dsrf.RAW_OUTPUT_ROOT_REL_PATH
    c1_001 = raw_root / "W06-DEV-SELECT-P1-C1-W06-DEV-SELECT-001"
    backup_dir = tmp_path / "backup_c1_001"

    # 1. 179 cell dirs
    shutil.move(str(c1_001), str(backup_dir))
    try:
        with pytest.raises(
            PlanBeforeLiveProtocolError, match="MISSING_CELL_DIRECTORIES"
        ):
            dsrf.verify_and_summarize_live_results_evidence(
                REPO_ROOT,
                raw_output_root=raw_root,
                verify_preflight_dry_run=False,
                run_secret_leak_scan=False,
                double_pass_tree_hash=False,
            )
    finally:
        shutil.move(str(backup_dir), str(c1_001))

    # 2. 181 cell dirs (unknown run ID)
    extra_dir = raw_root / "W06-DEV-SELECT-P1-C1-W06-DEV-SELECT-999"
    shutil.copytree(c1_001, extra_dir)
    try:
        with pytest.raises(
            PlanBeforeLiveProtocolError, match="UNKNOWN_EXTRA_CELL_DIRECTORIES"
        ):
            dsrf.verify_and_summarize_live_results_evidence(
                REPO_ROOT,
                raw_output_root=raw_root,
                verify_preflight_dry_run=False,
                run_secret_leak_scan=False,
                double_pass_tree_hash=False,
            )
    finally:
        shutil.rmtree(extra_dir)


def test_section_19_adversarial_missing_receipt_and_missing_evaluation_result(
    temp_evidence_workspace: Path,
) -> None:
    """Section 19: Fail closed on missing execution_receipt.json or missing evaluation_result.json."""
    raw_root = temp_evidence_workspace / dsrf.RAW_OUTPUT_ROOT_REL_PATH
    cdir = raw_root / "W06-DEV-SELECT-P1-C1-W06-DEV-SELECT-001"

    rec_p = cdir / "execution_receipt.json"
    rec_bytes = rec_p.read_bytes()
    try:
        rec_p.unlink()
        with pytest.raises(
            PlanBeforeLiveProtocolError, match="MISSING_REQUIRED_CELL_FILE"
        ):
            dsrf.verify_and_summarize_live_results_evidence(
                REPO_ROOT,
                raw_output_root=raw_root,
                verify_preflight_dry_run=False,
                run_secret_leak_scan=False,
                double_pass_tree_hash=False,
            )
    finally:
        rec_p.write_bytes(rec_bytes)

    eval_p = cdir / "evaluation_result.json"
    eval_bytes = eval_p.read_bytes()
    try:
        eval_p.unlink()
        with pytest.raises(
            PlanBeforeLiveProtocolError, match="MISSING_REQUIRED_CELL_FILE"
        ):
            dsrf.verify_and_summarize_live_results_evidence(
                REPO_ROOT,
                raw_output_root=raw_root,
                verify_preflight_dry_run=False,
                run_secret_leak_scan=False,
                double_pass_tree_hash=False,
            )
    finally:
        eval_p.write_bytes(eval_bytes)


def test_section_19_adversarial_duplicate_run_id_and_fake_contents(
    temp_evidence_workspace: Path,
) -> None:
    """Section 19: Fail closed on duplicate/mismatched run_id inside receipt or same filename with fake contents."""
    raw_root = temp_evidence_workspace / dsrf.RAW_OUTPUT_ROOT_REL_PATH
    cdir = raw_root / "W06-DEV-SELECT-P1-C1-W06-DEV-SELECT-001"

    rec_p = cdir / "execution_receipt.json"
    orig_rec = rec_p.read_bytes()
    try:
        obj = json.loads(orig_rec.decode("utf-8"))
        obj["run_id"] = "W06-DEV-SELECT-P1-C1-W06-DEV-SELECT-002"
        rec_p.write_text(json.dumps(obj, indent=2), encoding="utf-8")
        with pytest.raises(PlanBeforeLiveProtocolError, match="CELL_RUN_ID_MISMATCH"):
            dsrf.verify_and_summarize_live_results_evidence(
                REPO_ROOT,
                raw_output_root=raw_root,
                verify_preflight_dry_run=False,
                run_secret_leak_scan=False,
                double_pass_tree_hash=False,
            )
    finally:
        rec_p.write_bytes(orig_rec)

    # Same filename (`raw_usage_metadata.json`) but fake contents
    usage_p = cdir / "raw_usage_metadata.json"
    orig_usage = usage_p.read_bytes()
    try:
        usage_p.write_text('{"run_id": "FAKE_RUN_ID"}\n', encoding="utf-8")
        with pytest.raises(PlanBeforeLiveProtocolError, match="CELL_RUN_ID_MISMATCH"):
            dsrf.verify_and_summarize_live_results_evidence(
                REPO_ROOT,
                raw_output_root=raw_root,
                verify_preflight_dry_run=False,
                run_secret_leak_scan=False,
                double_pass_tree_hash=False,
            )
    finally:
        usage_p.write_bytes(orig_usage)


def test_section_19_adversarial_attempt_2_retry_evidence_and_181_calls(
    temp_evidence_workspace: Path,
) -> None:
    """Section 19: Fail closed on attempt_number=2, retry evidence added, or provider call count 181."""
    raw_root = temp_evidence_workspace / dsrf.RAW_OUTPUT_ROOT_REL_PATH
    cdir = raw_root / "W06-DEV-SELECT-P1-C1-W06-DEV-SELECT-001"

    # 1. attempt_number changed to 2
    rec_p = cdir / "execution_receipt.json"
    orig_rec = rec_p.read_bytes()
    try:
        obj = json.loads(orig_rec.decode("utf-8"))
        obj["attempt_number"] = 2
        rec_p.write_text(json.dumps(obj, indent=2), encoding="utf-8")
        with pytest.raises(
            PlanBeforeLiveProtocolError, match="RETRY_OR_SECOND_ATTEMPT_DETECTED"
        ):
            dsrf.verify_and_summarize_live_results_evidence(
                REPO_ROOT,
                raw_output_root=raw_root,
                verify_preflight_dry_run=False,
                run_secret_leak_scan=False,
                double_pass_tree_hash=False,
            )
    finally:
        rec_p.write_bytes(orig_rec)

    # 2. retry evidence file added inside cell directory
    retry_file = cdir / "transport_journal_attempt_2.json"
    try:
        retry_file.write_text("{}", encoding="utf-8")
        with pytest.raises(PlanBeforeLiveProtocolError, match="UNKNOWN_FILES_IN_CELL"):
            dsrf.verify_and_summarize_live_results_evidence(
                REPO_ROOT,
                raw_output_root=raw_root,
                verify_preflight_dry_run=False,
                run_secret_leak_scan=False,
                double_pass_tree_hash=False,
            )
    finally:
        if retry_file.exists():
            retry_file.unlink()

    # 3. provider call count 181 (actual_http_request_count = 2 in one cell -> 181 total calls)
    meta_p = cdir / "provider_response_metadata.json"
    orig_meta = meta_p.read_bytes()
    try:
        m_obj = json.loads(orig_meta.decode("utf-8"))
        m_obj["actual_http_request_count"] = 2
        meta_bytes_new = json.dumps(m_obj, indent=2).encode("utf-8")
        meta_p.write_bytes(meta_bytes_new)

        r_obj = json.loads(orig_rec.decode("utf-8"))
        r_obj["provider_metadata_sha256"] = sha256_bytes(meta_bytes_new)
        rec_p.write_text(json.dumps(r_obj, indent=2), encoding="utf-8")

        with pytest.raises(
            PlanBeforeLiveProtocolError, match="RETRY_OR_SECOND_ATTEMPT_DETECTED"
        ):
            dsrf.verify_and_summarize_live_results_evidence(
                REPO_ROOT,
                raw_output_root=raw_root,
                verify_preflight_dry_run=False,
                run_secret_leak_scan=False,
                double_pass_tree_hash=False,
            )
    finally:
        meta_p.write_bytes(orig_meta)
        rec_p.write_bytes(orig_rec)


def test_section_19_adversarial_model_mismatch_and_cost_altered(
    temp_evidence_workspace: Path,
) -> None:
    """Section 19: Fail closed on injected model mismatch or altered cost value."""
    raw_root = temp_evidence_workspace / dsrf.RAW_OUTPUT_ROOT_REL_PATH
    cdir = raw_root / "W06-DEV-SELECT-P1-C1-W06-DEV-SELECT-026"
    rec_p = cdir / "execution_receipt.json"
    orig_rec = rec_p.read_bytes()

    # 1. Model mismatch injected
    try:
        obj = json.loads(orig_rec.decode("utf-8"))
        obj["returned_model_id"] = "gemini-2.5-flash-wrong"
        rec_p.write_text(json.dumps(obj, indent=2), encoding="utf-8")
        with pytest.raises(
            PlanBeforeLiveProtocolError, match="RETURNED_MODEL_ID_MISMATCH"
        ):
            dsrf.verify_and_summarize_live_results_evidence(
                REPO_ROOT,
                raw_output_root=raw_root,
                verify_preflight_dry_run=False,
                run_secret_leak_scan=False,
                double_pass_tree_hash=False,
            )
    finally:
        rec_p.write_bytes(orig_rec)

    # 2. Cost value altered
    try:
        obj = json.loads(orig_rec.decode("utf-8"))
        obj["canonical_cost_usd"] = 0.0999999
        obj["canonical_cost_usd_decimal"] = "0.0999999"
        obj["canonical_cost_usd_display"] = 0.0999999
        rec_p.write_text(json.dumps(obj, indent=2), encoding="utf-8")
        with pytest.raises(
            PlanBeforeLiveProtocolError, match="AUTHORITATIVE_COST_MISMATCH"
        ):
            dsrf.verify_and_summarize_live_results_evidence(
                REPO_ROOT,
                raw_output_root=raw_root,
                verify_preflight_dry_run=False,
                run_secret_leak_scan=False,
                double_pass_tree_hash=False,
            )
    finally:
        rec_p.write_bytes(orig_rec)


def test_section_19_adversarial_evaluation_metric_and_failure_classification_changed_with_rehashed_chain(
    temp_evidence_workspace: Path,
) -> None:
    """Section 19: Even if an attacker updates execution_receipt.evaluation_result_sha256, changing an evaluation metric or failure classification fails closed."""
    raw_root = temp_evidence_workspace / dsrf.RAW_OUTPUT_ROOT_REL_PATH
    cdir = raw_root / "W06-DEV-SELECT-P1-C1-W06-DEV-SELECT-026"
    eval_p = cdir / "evaluation_result.json"
    rec_p = cdir / "execution_receipt.json"
    orig_eval = eval_p.read_bytes()
    orig_rec = rec_p.read_bytes()

    # 1. Evaluation metric changed + receipt hash pointer updated
    try:
        ev_obj = json.loads(orig_eval.decode("utf-8"))
        ev_obj["core_scenario_pass"] = False
        new_eval_bytes = json.dumps(ev_obj, indent=2).encode("utf-8")
        eval_p.write_bytes(new_eval_bytes)

        r_obj = json.loads(orig_rec.decode("utf-8"))
        r_obj["evaluation_result_sha256"] = sha256_bytes(new_eval_bytes)
        rec_p.write_text(json.dumps(r_obj, indent=2), encoding="utf-8")

        with pytest.raises(
            PlanBeforeLiveProtocolError, match="EVALUATION_METRIC_DISCREPANCY"
        ):
            dsrf.verify_and_summarize_live_results_evidence(
                REPO_ROOT,
                raw_output_root=raw_root,
                verify_preflight_dry_run=False,
                run_secret_leak_scan=False,
                double_pass_tree_hash=False,
            )
    finally:
        eval_p.write_bytes(orig_eval)
        rec_p.write_bytes(orig_rec)

    # 2. Failure classification changed on a failed cell
    fail_dir = raw_root / "W06-DEV-SELECT-P1-C1-W06-DEV-SELECT-001"
    fail_rec_p = fail_dir / "execution_receipt.json"
    orig_fail_rec = fail_rec_p.read_bytes()
    try:
        fr_obj = json.loads(orig_fail_rec.decode("utf-8"))
        fr_obj["failure_classification"] = "DevCellFailureClassification.TIMEOUT"
        fail_rec_p.write_text(json.dumps(fr_obj, indent=2), encoding="utf-8")
        with pytest.raises(
            PlanBeforeLiveProtocolError, match="FAILURE_CLASSIFICATION_COUNTS_MISMATCH"
        ):
            dsrf.verify_and_summarize_live_results_evidence(
                REPO_ROOT,
                raw_output_root=raw_root,
                verify_preflight_dry_run=False,
                run_secret_leak_scan=False,
                double_pass_tree_hash=False,
            )
    finally:
        fail_rec_p.write_bytes(orig_fail_rec)


def test_section_23_post_live_output_root_guard_on_unpatched_launcher() -> None:
    """Section 23: Verify unpatched `run_w06_dev_select_live_v1.py --preflight` raises `LIVE_OUTPUT_ROOT_ALREADY_EXISTS` (EXPECTED_POST_LIVE_OUTPUT_ROOT_GUARD)."""
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="LIVE_OUTPUT_ROOT_ALREADY_EXISTS"
    ):
        launcher.verify_output_root_not_existing(REPO_ROOT)
