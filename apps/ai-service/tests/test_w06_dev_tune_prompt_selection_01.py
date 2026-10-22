"""Tests for W06-DEV-TUNE-PROMPT-SELECTION-01: Deterministic preregistered prompt selection.

Covers:
- PS-01 through PS-35 (Section 15)
- Adversarial tests proving fail-closed behavior on any count, denominator, band,
  criterion order, tie-break, cost/latency, candidate-specific, raw SHA, receipt,
  prompt SHA, model winner, or Final100 tampering.
- Offline network kill-switch enforcement (`LIVE_PROVIDER_CALLS_NEW = 0`).
"""

from __future__ import annotations

import copy
from decimal import Decimal
import json
from pathlib import Path
import shutil
import socket
import sys
from typing import Any
import urllib.request

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
AI_SERVICE_ROOT = REPO_ROOT / "apps" / "ai-service"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for _p in (AI_SERVICE_ROOT, SCRIPTS_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from app.evaluation.dev_live_runner import PlanBeforeLiveProtocolError  # noqa: E402
from app.evaluation.dev_selection_harness import (  # noqa: E402
    FORBIDDEN_FINAL100_BUNDLE_SHA256,
    FORBIDDEN_P11_MANIFEST_SHA256,
)
from freeze_w06_dev_tune_live_results import (  # noqa: E402
    DEV_TUNE_PLAN_REL_PATH,
    EXPECTED_LAUNCHER_LF_SHA256,
    EXPECTED_PROMPT_FREEZE_SHA256,
    EXPECTED_PROMPT_REGISTRY_SHA256,
    EXPECTED_RAW_EVIDENCE_FILE_COUNT,
    EXPECTED_RAW_EVIDENCE_TOTAL_BYTES,
    EXPECTED_RAW_EVIDENCE_TREE_SHA256,
    EXPECTED_RESULTS_FREEZE_RECEIPT_FILE_SHA256,
    EXPECTED_RESULTS_MANIFEST_FILE_SHA256,
    EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256,
    FORBIDDEN_FINAL100_SCENARIOS_REL_PATH,
    FORBIDDEN_P11_MANIFEST_REL_PATH,
    PROMPT_FREEZE_REL_PATH,
    RAW_OUTPUT_ROOT_REL_PATH,
    RESULTS_FREEZE_RECEIPT_REL_PATH,
    RESULTS_MANIFEST_REL_PATH,
    build_raw_evidence_tree_manifest,
    compute_scientific_code_bundle_sha256,
    is_verified_downstream_w06_dev_tune_live_results_tree,
    normalize_lf_bytes,
    sha256_bytes,
)
from select_w06_dev_tune_prompt import (  # noqa: E402
    CANDIDATE_PROMPT_IDS,
    EXPECTED_P1_SEMANTIC_PROMPT_SHA256,
    EXPECTED_P1_SYSTEM_PROMPT_SHA256,
    EXPECTED_P1_USER_PROMPT_TEMPLATE_SHA256,
    EXPECTED_P2_SEMANTIC_PROMPT_SHA256,
    EXPECTED_PRIMARY_COUNTS,
    EXPECTED_PROMPT_SELECTION_ARTIFACT_FILE_SHA256,
    EXPECTED_PROMPT_SELECTION_ARTIFACT_INTERNAL_SHA256,
    EXPECTED_PROMPT_SELECTION_RECEIPT_FILE_SHA256,
    EXPECTED_SELECTED_PROMPT_ID,
    EXPECTED_SELECTION_REASON,
    FORBIDDEN_CAUSAL_429_CLAIMS,
    FORBIDDEN_SUPERIORITY_CLAIMS,
    PROMPT_SELECTION_ARTIFACT_REL_PATH,
    PROMPT_SELECTION_DOC_REL_PATH,
    PROMPT_SELECTION_RECEIPT_REL_PATH,
    SCIENTIFIC_INTERPRETATION_STATEMENT,
    SELECTION_CRITERIA_ORDER,
    SOURCE_DEVELOP_SHA,
    SURVIVOR_BAND_PERCENTAGE_POINTS_DECIMAL,
    TIE_BREAK_POLICY,
    NetworkKillSwitchGuard,
    OutboundNetworkBlockedError,
    build_prompt_selection_artifact_payload,
    evaluate_preregistered_prompt_selection,
    verify_frozen_inputs_and_results_freeze,
    verify_persisted_prompt_selection_artifacts,
    verify_source_develop_provenance,
)


@pytest.fixture(scope="module")
def verified_selection_state() -> dict[str, Any]:
    """Load and verify the persisted prompt-selection artifact, receipt, and frozen inputs once per module."""
    with NetworkKillSwitchGuard():
        src_prov = verify_source_develop_provenance(REPO_ROOT)
        frozen_ctx = verify_frozen_inputs_and_results_freeze(REPO_ROOT)
        persisted_ver = verify_persisted_prompt_selection_artifacts(REPO_ROOT)

        art_path = REPO_ROOT / PROMPT_SELECTION_ARTIFACT_REL_PATH
        rec_path = REPO_ROOT / PROMPT_SELECTION_RECEIPT_REL_PATH
        doc_path = REPO_ROOT / PROMPT_SELECTION_DOC_REL_PATH

        art_obj = json.loads(art_path.read_text(encoding="utf-8"))
        rec_obj = json.loads(rec_path.read_text(encoding="utf-8"))
        doc_text = doc_path.read_text(encoding="utf-8")

        return {
            "source_provenance": src_prov,
            "frozen_ctx": frozen_ctx,
            "persisted_verification": persisted_ver,
            "artifact": art_obj,
            "receipt": rec_obj,
            "doc_text": doc_text,
        }


# ==============================================================================
# 1. PS-01 .. PS-35 REQUIRED CHECKS (SECTION 15)
# ==============================================================================


def test_ps01_source_develop_sha_exact(verified_selection_state: dict[str, Any]) -> None:
    """PS-01: source develop SHA exact."""
    prov = verified_selection_state["source_provenance"]
    art = verified_selection_state["artifact"]
    rec = verified_selection_state["receipt"]
    assert prov["source_develop_sha"] == SOURCE_DEVELOP_SHA
    assert prov["ancestry_verified"] is True
    assert art["source_develop_sha"] == SOURCE_DEVELOP_SHA
    assert rec["source_develop_sha"] == SOURCE_DEVELOP_SHA
    assert rec["ps_checks"]["PS-01_source_develop_sha_exact"] == "PASS"


def test_ps02_results_freeze_verifies(verified_selection_state: dict[str, Any]) -> None:
    """PS-02: results-freeze verifies via stateless production/offline verifier."""
    assert is_verified_downstream_w06_dev_tune_live_results_tree(REPO_ROOT) is True
    rec = verified_selection_state["receipt"]
    assert rec["ps_checks"]["PS-02_results_freeze_verifies"] == "PASS"


def test_ps03_raw_tree_sha_exact(verified_selection_state: dict[str, Any]) -> None:
    """PS-03: raw tree SHA exact."""
    tm = verified_selection_state["frozen_ctx"]["raw_summary"]["tree_manifest"]
    art = verified_selection_state["artifact"]
    rec = verified_selection_state["receipt"]
    assert tm["raw_evidence_file_count"] == EXPECTED_RAW_EVIDENCE_FILE_COUNT
    assert tm["raw_evidence_total_bytes"] == EXPECTED_RAW_EVIDENCE_TOTAL_BYTES
    assert tm["raw_evidence_tree_sha256"] == EXPECTED_RAW_EVIDENCE_TREE_SHA256
    assert art["raw_evidence_tree_sha256"] == EXPECTED_RAW_EVIDENCE_TREE_SHA256
    assert rec["raw_evidence_tree_sha256"] == EXPECTED_RAW_EVIDENCE_TREE_SHA256
    assert rec["ps_checks"]["PS-03_raw_tree_sha_exact"] == "PASS"


def test_ps04_results_manifest_sha_exact(
    verified_selection_state: dict[str, Any],
) -> None:
    """PS-04: results manifest SHA exact."""
    art = verified_selection_state["artifact"]
    rec = verified_selection_state["receipt"]
    man_sha = sha256_bytes(
        normalize_lf_bytes((REPO_ROOT / RESULTS_MANIFEST_REL_PATH).read_bytes())
    )
    assert man_sha == EXPECTED_RESULTS_MANIFEST_FILE_SHA256
    assert art["results_manifest_file_sha256"] == EXPECTED_RESULTS_MANIFEST_FILE_SHA256
    assert rec["results_manifest_file_sha256"] == EXPECTED_RESULTS_MANIFEST_FILE_SHA256
    assert rec["ps_checks"]["PS-04_results_manifest_sha_exact"] == "PASS"


def test_ps05_results_freeze_receipt_sha_exact(
    verified_selection_state: dict[str, Any],
) -> None:
    """PS-05: results-freeze receipt SHA exact."""
    art = verified_selection_state["artifact"]
    rec = verified_selection_state["receipt"]
    rf_rec_sha = sha256_bytes(
        normalize_lf_bytes((REPO_ROOT / RESULTS_FREEZE_RECEIPT_REL_PATH).read_bytes())
    )
    assert rf_rec_sha == EXPECTED_RESULTS_FREEZE_RECEIPT_FILE_SHA256
    assert (
        art["results_freeze_receipt_file_sha256"]
        == EXPECTED_RESULTS_FREEZE_RECEIPT_FILE_SHA256
    )
    assert (
        rec["results_freeze_receipt_file_sha256"]
        == EXPECTED_RESULTS_FREEZE_RECEIPT_FILE_SHA256
    )
    assert rec["ps_checks"]["PS-05_results_freeze_receipt_sha_exact"] == "PASS"


def test_ps06_prompt_freeze_sha_exact(verified_selection_state: dict[str, Any]) -> None:
    """PS-06: prompt freeze SHA exact."""
    art = verified_selection_state["artifact"]
    rec = verified_selection_state["receipt"]
    pf_sha = sha256_bytes(
        normalize_lf_bytes((REPO_ROOT / PROMPT_FREEZE_REL_PATH).read_bytes())
    )
    assert pf_sha == EXPECTED_PROMPT_FREEZE_SHA256
    assert art["prompt_freeze_sha256"] == EXPECTED_PROMPT_FREEZE_SHA256
    assert art["prompt_registry_sha256"] == EXPECTED_PROMPT_REGISTRY_SHA256
    assert rec["prompt_freeze_sha256"] == EXPECTED_PROMPT_FREEZE_SHA256
    assert rec["prompt_registry_sha256"] == EXPECTED_PROMPT_REGISTRY_SHA256
    assert rec["ps_checks"]["PS-06_prompt_freeze_sha_exact"] == "PASS"


def test_ps07_prompt_candidates_exact_p1_p2(
    verified_selection_state: dict[str, Any],
) -> None:
    """PS-07: prompt candidates exactly P1/P2."""
    art = verified_selection_state["artifact"]
    rec = verified_selection_state["receipt"]
    assert art["candidate_prompt_ids"] == ["P1", "P2"]
    assert rec["candidate_prompt_ids"] == ["P1", "P2"]
    assert (
        art["candidate_prompt_metadata"]["P1"]["semantic_prompt_sha256"]
        == EXPECTED_P1_SEMANTIC_PROMPT_SHA256
    )
    assert (
        art["candidate_prompt_metadata"]["P2"]["semantic_prompt_sha256"]
        == EXPECTED_P2_SEMANTIC_PROMPT_SHA256
    )
    assert rec["ps_checks"]["PS-07_prompt_candidates_exact_p1_p2"] == "PASS"


def test_ps08_p1_valid_schema_23_of_60(
    verified_selection_state: dict[str, Any],
) -> None:
    """PS-08: P1 valid/schema 23/60."""
    art = verified_selection_state["artifact"]
    c1_p1 = art["criterion_1_rates"]["P1"]
    assert c1_p1["true_count"] == 23
    assert c1_p1["false_count"] == 37
    assert c1_p1["denominator"] == 60
    assert c1_p1["rational_rate"] == "23/60"
    assert c1_p1["percentage_decimal_str"] == "38.333333333333"
    assert verified_selection_state["receipt"]["ps_checks"]["PS-08_p1_valid_schema_23_of_60"] == "PASS"


def test_ps09_p2_valid_schema_21_of_60(
    verified_selection_state: dict[str, Any],
) -> None:
    """PS-09: P2 valid/schema 21/60."""
    art = verified_selection_state["artifact"]
    c1_p2 = art["criterion_1_rates"]["P2"]
    assert c1_p2["true_count"] == 21
    assert c1_p2["false_count"] == 39
    assert c1_p2["denominator"] == 60
    assert c1_p2["rational_rate"] == "21/60"
    assert c1_p2["percentage_decimal_str"] == "35.000000000000"
    assert verified_selection_state["receipt"]["ps_checks"]["PS-09_p2_valid_schema_21_of_60"] == "PASS"


def test_ps10_criterion1_survivors_p1_p2(
    verified_selection_state: dict[str, Any],
) -> None:
    """PS-10: criterion1 survivors P1/P2."""
    art = verified_selection_state["artifact"]
    rec = verified_selection_state["receipt"]
    c1_meta = art["criterion_metrics"]["VALID_RUN_AND_SCHEMA_RATE"]
    assert c1_meta["best_surviving_prompt_id"] == "P1"
    assert c1_meta["survivor_threshold_percentage_decimal_str"] == "28.333333333333"
    assert art["criterion_1_survivors"] == ["P1", "P2"]
    assert rec["criterion_1_survivors"] == ["P1", "P2"]
    assert rec["ps_checks"]["PS-10_criterion1_survivors_p1_p2"] == "PASS"


def test_ps11_p1_grounding_23_of_60(verified_selection_state: dict[str, Any]) -> None:
    """PS-11: P1 grounding 23/60."""
    art = verified_selection_state["artifact"]
    c2_p1 = art["criterion_2_rates"]["P1"]
    assert c2_p1["true_count"] == 23
    assert c2_p1["false_count"] == 37
    assert c2_p1["denominator"] == 60
    assert c2_p1["rational_rate"] == "23/60"
    assert c2_p1["percentage_decimal_str"] == "38.333333333333"
    assert verified_selection_state["receipt"]["ps_checks"]["PS-11_p1_grounding_23_of_60"] == "PASS"


def test_ps12_p2_grounding_21_of_60(verified_selection_state: dict[str, Any]) -> None:
    """PS-12: P2 grounding 21/60."""
    art = verified_selection_state["artifact"]
    c2_p2 = art["criterion_2_rates"]["P2"]
    assert c2_p2["true_count"] == 21
    assert c2_p2["false_count"] == 39
    assert c2_p2["denominator"] == 60
    assert c2_p2["rational_rate"] == "21/60"
    assert c2_p2["percentage_decimal_str"] == "35.000000000000"
    assert verified_selection_state["receipt"]["ps_checks"]["PS-12_p2_grounding_21_of_60"] == "PASS"


def test_ps13_criterion2_survivors_p1_p2(
    verified_selection_state: dict[str, Any],
) -> None:
    """PS-13: criterion2 survivors P1/P2."""
    art = verified_selection_state["artifact"]
    rec = verified_selection_state["receipt"]
    c2_meta = art["criterion_metrics"]["EXACT_GROUNDING_PASS_RATE"]
    assert c2_meta["best_surviving_prompt_id"] == "P1"
    assert c2_meta["survivor_threshold_percentage_decimal_str"] == "28.333333333333"
    assert art["criterion_2_survivors"] == ["P1", "P2"]
    assert rec["criterion_2_survivors"] == ["P1", "P2"]
    assert rec["ps_checks"]["PS-13_criterion2_survivors_p1_p2"] == "PASS"


def test_ps14_p1_core_20_of_60(verified_selection_state: dict[str, Any]) -> None:
    """PS-14: P1 core 20/60."""
    art = verified_selection_state["artifact"]
    c3_p1 = art["criterion_3_rates"]["P1"]
    assert c3_p1["true_count"] == 20
    assert c3_p1["false_count"] == 40
    assert c3_p1["denominator"] == 60
    assert c3_p1["rational_rate"] == "20/60"
    assert c3_p1["percentage_decimal_str"] == "33.333333333333"
    assert verified_selection_state["receipt"]["ps_checks"]["PS-14_p1_core_20_of_60"] == "PASS"


def test_ps15_p2_core_21_of_60(verified_selection_state: dict[str, Any]) -> None:
    """PS-15: P2 core 21/60."""
    art = verified_selection_state["artifact"]
    c3_p2 = art["criterion_3_rates"]["P2"]
    assert c3_p2["true_count"] == 21
    assert c3_p2["false_count"] == 39
    assert c3_p2["denominator"] == 60
    assert c3_p2["rational_rate"] == "21/60"
    assert c3_p2["percentage_decimal_str"] == "35.000000000000"
    assert verified_selection_state["receipt"]["ps_checks"]["PS-15_p2_core_21_of_60"] == "PASS"


def test_ps16_criterion3_survivors_p1_p2(
    verified_selection_state: dict[str, Any],
) -> None:
    """PS-16: criterion3 survivors P1/P2."""
    art = verified_selection_state["artifact"]
    rec = verified_selection_state["receipt"]
    c3_meta = art["criterion_metrics"]["FINAL_CORE_PASS_RATE"]
    assert c3_meta["best_surviving_prompt_id"] == "P2"
    assert c3_meta["survivor_threshold_percentage_decimal_str"] == "25.000000000000"
    assert art["criterion_3_survivors"] == ["P1", "P2"]
    assert rec["criterion_3_survivors"] == ["P1", "P2"]
    assert rec["ps_checks"]["PS-16_criterion3_survivors_p1_p2"] == "PASS"


def test_ps17_final_survivors_p1_p2(verified_selection_state: dict[str, Any]) -> None:
    """PS-17: final survivors P1/P2."""
    art = verified_selection_state["artifact"]
    rec = verified_selection_state["receipt"]
    assert art["final_survivors"] == ["P1", "P2"]
    assert rec["final_survivors"] == ["P1", "P2"]
    assert rec["ps_checks"]["PS-17_final_survivors_p1_p2"] == "PASS"


def test_ps18_admin_tie_break_selects_p1(
    verified_selection_state: dict[str, Any],
) -> None:
    """PS-18: admin tie-break selects P1."""
    art = verified_selection_state["artifact"]
    rec = verified_selection_state["receipt"]
    assert art["tie_break_policy"] == TIE_BREAK_POLICY
    assert art["tie_break_applied"] is True
    assert art["selected_prompt_id"] == EXPECTED_SELECTED_PROMPT_ID == "P1"
    assert art["selection_reason"] == EXPECTED_SELECTION_REASON
    assert rec["tie_break_policy"] == TIE_BREAK_POLICY
    assert rec["selected_prompt_id"] == "P1"
    assert rec["selection_reason"] == EXPECTED_SELECTION_REASON
    assert rec["ps_checks"]["PS-18_admin_tie_break_selects_p1"] == "PASS"


def test_ps19_selected_p1_semantic_sha_exact(
    verified_selection_state: dict[str, Any],
) -> None:
    """PS-19: selected P1 semantic SHA, system SHA, and user template SHA exact + formal prompt lock."""
    art = verified_selection_state["artifact"]
    rec = verified_selection_state["receipt"]
    lock = art["future_dev_select_prompt_lock"]
    assert art["selected_prompt_semantic_sha256"] == EXPECTED_P1_SEMANTIC_PROMPT_SHA256
    assert art["selected_prompt_system_sha256"] == EXPECTED_P1_SYSTEM_PROMPT_SHA256
    assert (
        art["selected_prompt_user_template_sha256"]
        == EXPECTED_P1_USER_PROMPT_TEMPLATE_SHA256
    )
    assert rec["selected_prompt_semantic_sha256"] == EXPECTED_P1_SEMANTIC_PROMPT_SHA256
    assert lock["allowed_dev_select_prompt_ids"] == ["P1"]
    assert lock["forbidden_dev_select_prompt_ids"] == ["P2", "P3"]
    assert lock["prompt_editing_allowed"] is False
    assert lock["prompt_suffix_modification_allowed"] is False
    assert lock["user_template_modification_allowed"] is False
    assert lock["provider_specific_prompt_allowed"] is False
    assert lock["locked_prompt_semantic_sha256"] == EXPECTED_P1_SEMANTIC_PROMPT_SHA256
    assert rec["ps_checks"]["PS-19_selected_p1_semantic_sha_exact"] == "PASS"


def test_ps20_no_cost_criterion(verified_selection_state: dict[str, Any]) -> None:
    """PS-20: no cost criterion."""
    art = verified_selection_state["artifact"]
    rec = verified_selection_state["receipt"]
    assert art["cost_used_for_prompt_selection"] is False
    assert rec["cost_used_for_prompt_selection"] is False
    assert "COST" not in " ".join(art["selection_criteria_order"])
    assert rec["ps_checks"]["PS-20_no_cost_criterion"] == "PASS"


def test_ps21_no_latency_criterion(verified_selection_state: dict[str, Any]) -> None:
    """PS-21: no latency criterion."""
    art = verified_selection_state["artifact"]
    rec = verified_selection_state["receipt"]
    assert art["latency_used_for_prompt_selection"] is False
    assert rec["latency_used_for_prompt_selection"] is False
    assert "LATENCY" not in " ".join(art["selection_criteria_order"])
    assert rec["ps_checks"]["PS-21_no_latency_criterion"] == "PASS"


def test_ps22_no_provider_specific_selection(
    verified_selection_state: dict[str, Any],
) -> None:
    """PS-22: no provider-specific selection."""
    art = verified_selection_state["artifact"]
    rec = verified_selection_state["receipt"]
    assert art["provider_specific_prompt_selection"] is False
    assert rec["provider_specific_prompt_selection"] is False
    assert art["selection_unit"]["per_provider_prompt_selection_allowed"] is False
    assert rec["ps_checks"]["PS-22_no_provider_specific_selection"] == "PASS"


def test_ps23_superiority_claim_false(
    verified_selection_state: dict[str, Any],
) -> None:
    """PS-23: superiority_claim false and exact scientific statement present."""
    art = verified_selection_state["artifact"]
    rec = verified_selection_state["receipt"]
    doc = verified_selection_state["doc_text"]
    assert art["superiority_claim"] is False
    assert rec["superiority_claim"] is False
    assert (
        art["scientific_interpretation_statement"]
        == SCIENTIFIC_INTERPRETATION_STATEMENT
    )
    assert (
        rec["scientific_interpretation_statement"]
        == SCIENTIFIC_INTERPRETATION_STATEMENT
    )
    assert SCIENTIFIC_INTERPRETATION_STATEMENT in doc
    assert art["forbidden_superiority_claims"] == list(FORBIDDEN_SUPERIORITY_CLAIMS)
    assert rec["ps_checks"]["PS-23_superiority_claim_false"] == "PASS"


def test_ps24_temporal_ordering_limitation_recorded(
    verified_selection_state: dict[str, Any],
) -> None:
    """PS-24: temporal ordering limitation recorded."""
    art = verified_selection_state["artifact"]
    rec = verified_selection_state["receipt"]
    t_lim = art["temporal_ordering_limitation"]
    assert t_lim["p1_executed_before_p2"] is True
    assert t_lim["p1_assigned_cell_count"] == 60
    assert t_lim["p2_assigned_cell_count"] == 60
    assert t_lim["prompt_treatment_temporally_interleaved_or_randomized"] is False
    assert t_lim["observed_http_429_total"] == 15
    assert t_lim["observed_http_429_in_p2_c1"] == 15
    assert rec["temporal_ordering_limitation"] == t_lim
    assert rec["ps_checks"]["PS-24_temporal_ordering_limitation_recorded"] == "PASS"


def test_ps25_429_causal_claim_forbidden(
    verified_selection_state: dict[str, Any],
) -> None:
    """PS-25: 429 causal claim forbidden."""
    art = verified_selection_state["artifact"]
    rec = verified_selection_state["receipt"]
    t_lim = art["temporal_ordering_limitation"]
    assert t_lim["causal_inference_p2_causes_http_429_forbidden"] is True
    assert t_lim["retroactive_interleaved_rerun_forbidden"] is True
    assert t_lim["primary_results_modification_forbidden"] is True
    assert t_lim["forbidden_causal_claims"] == list(FORBIDDEN_CAUSAL_429_CLAIMS)
    assert rec["ps_checks"]["PS-25_429_causal_claim_forbidden"] == "PASS"


def test_ps26_model_winner_false(verified_selection_state: dict[str, Any]) -> None:
    """PS-26: model winner false."""
    art = verified_selection_state["artifact"]
    rec = verified_selection_state["receipt"]
    msf = art["model_selection_firewall"]
    assert art["model_winner_selected"] is False
    assert rec["model_winner_selected"] is False
    assert msf["model_winner_selected"] is False
    assert msf["selected_model_id"] is None
    assert msf["dev_select_candidate_ids"] == ["C1", "C2", "C3"]
    assert msf["candidates_removed_in_dev_tune"] == []
    assert rec["ps_checks"]["PS-26_model_winner_false"] == "PASS"


def test_ps27_dev_select_not_started(verified_selection_state: dict[str, Any]) -> None:
    """PS-27: DEV-SELECT not started."""
    art = verified_selection_state["artifact"]
    rec = verified_selection_state["receipt"]
    assert art["dev_select_execution_started"] is False
    assert rec["dev_select_execution_started"] is False
    assert rec["ps_checks"]["PS-27_dev_select_not_started"] == "PASS"


def test_ps28_stochasticity_not_started(
    verified_selection_state: dict[str, Any],
) -> None:
    """PS-28: stochasticity not started."""
    art = verified_selection_state["artifact"]
    rec = verified_selection_state["receipt"]
    assert art["stochasticity_execution_started"] is False
    assert rec["stochasticity_execution_started"] is False
    assert rec["ps_checks"]["PS-28_stochasticity_not_started"] == "PASS"


def test_ps29_final100_untouched(verified_selection_state: dict[str, Any]) -> None:
    """PS-29: Final100 untouched."""
    art = verified_selection_state["artifact"]
    rec = verified_selection_state["receipt"]
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
    assert art["final100_used"] is False
    assert rec["final100_used"] is False
    assert rec["ps_checks"]["PS-29_final100_untouched"] == "PASS"


def test_ps30_zero_new_provider_calls(
    verified_selection_state: dict[str, Any],
) -> None:
    """PS-30: zero new provider calls."""
    art = verified_selection_state["artifact"]
    rec = verified_selection_state["receipt"]
    ver = verified_selection_state["persisted_verification"]
    assert art["live_provider_calls_new"] == 0
    assert rec["live_provider_calls_new"] == 0
    assert ver["live_provider_calls_new"] == 0
    assert rec["ps_checks"]["PS-30_zero_new_provider_calls"] == "PASS"


def test_ps31_raw_evidence_unchanged(verified_selection_state: dict[str, Any]) -> None:
    """PS-31: raw evidence unchanged."""
    tm = build_raw_evidence_tree_manifest(REPO_ROOT)
    assert tm["raw_evidence_file_count"] == EXPECTED_RAW_EVIDENCE_FILE_COUNT
    assert tm["raw_evidence_total_bytes"] == EXPECTED_RAW_EVIDENCE_TOTAL_BYTES
    assert tm["raw_evidence_tree_sha256"] == EXPECTED_RAW_EVIDENCE_TREE_SHA256
    assert (
        verified_selection_state["receipt"]["ps_checks"][
            "PS-31_raw_evidence_unchanged"
        ]
        == "PASS"
    )


def test_ps32_results_manifest_unchanged(
    verified_selection_state: dict[str, Any],
) -> None:
    """PS-32: results manifest unchanged."""
    man_sha = sha256_bytes(
        normalize_lf_bytes((REPO_ROOT / RESULTS_MANIFEST_REL_PATH).read_bytes())
    )
    assert man_sha == EXPECTED_RESULTS_MANIFEST_FILE_SHA256
    assert (
        verified_selection_state["receipt"]["ps_checks"][
            "PS-32_results_manifest_unchanged"
        ]
        == "PASS"
    )


def test_ps33_results_freeze_receipt_unchanged(
    verified_selection_state: dict[str, Any],
) -> None:
    """PS-33: results-freeze receipt unchanged."""
    rf_rec_sha = sha256_bytes(
        normalize_lf_bytes((REPO_ROOT / RESULTS_FREEZE_RECEIPT_REL_PATH).read_bytes())
    )
    assert rf_rec_sha == EXPECTED_RESULTS_FREEZE_RECEIPT_FILE_SHA256
    assert (
        verified_selection_state["receipt"]["ps_checks"][
            "PS-33_results_freeze_receipt_unchanged"
        ]
        == "PASS"
    )


def test_ps34_prompt_freeze_unchanged(
    verified_selection_state: dict[str, Any],
) -> None:
    """PS-34: prompt freeze unchanged."""
    pf_sha = sha256_bytes(
        normalize_lf_bytes((REPO_ROOT / PROMPT_FREEZE_REL_PATH).read_bytes())
    )
    assert pf_sha == EXPECTED_PROMPT_FREEZE_SHA256
    assert (
        verified_selection_state["receipt"]["ps_checks"][
            "PS-34_prompt_freeze_unchanged"
        ]
        == "PASS"
    )


def test_ps35_scientific_bundle_unchanged(
    verified_selection_state: dict[str, Any],
) -> None:
    """PS-35: scientific bundle unchanged and selection artifact/receipt hashes exact."""
    bundle_sha = compute_scientific_code_bundle_sha256(REPO_ROOT)
    launcher_sha = sha256_bytes(
        normalize_lf_bytes(
            (REPO_ROOT / "scripts" / "run_w06_dev_tune_live_v1.py").read_bytes()
        )
    )
    ver = verified_selection_state["persisted_verification"]
    assert bundle_sha == EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
    assert launcher_sha == EXPECTED_LAUNCHER_LF_SHA256
    assert (
        ver["prompt_selection_artifact_file_sha256"]
        == EXPECTED_PROMPT_SELECTION_ARTIFACT_FILE_SHA256
    )
    assert (
        ver["prompt_selection_artifact_internal_sha256"]
        == EXPECTED_PROMPT_SELECTION_ARTIFACT_INTERNAL_SHA256
    )
    assert (
        ver["prompt_selection_receipt_file_sha256"]
        == EXPECTED_PROMPT_SELECTION_RECEIPT_FILE_SHA256
    )
    assert (
        verified_selection_state["receipt"]["ps_checks"][
            "PS-35_scientific_bundle_unchanged"
        ]
        == "PASS"
    )


# ==============================================================================
# 2. ADVERSARIAL TESTS (SECTION 15)
# ==============================================================================


def test_adv01_altered_numerator_fails_closed() -> None:
    """Adversarial 1: any numerator altered fails closed."""
    for crit_name in SELECTION_CRITERIA_ORDER:
        for pid in CANDIDATE_PROMPT_IDS:
            tampered = copy.deepcopy(EXPECTED_PRIMARY_COUNTS)
            tampered[crit_name][pid]["true"] += 1
            tampered[crit_name][pid]["false"] -= 1
            with pytest.raises(
                PlanBeforeLiveProtocolError, match="FROZEN_PRIMARY_COUNT_TAMPERED"
            ):
                evaluate_preregistered_prompt_selection(tampered)


def test_adv02_denominator_not_60_fails_closed() -> None:
    """Adversarial 2: denominator != 60 fails closed."""
    tampered = copy.deepcopy(EXPECTED_PRIMARY_COUNTS)
    tampered["VALID_RUN_AND_SCHEMA_RATE"]["P1"] = {
        "true": 23,
        "false": 21,
        "denominator": 44,
    }
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="INVALID_PROMPT_CELL_DENOMINATOR"
    ):
        evaluate_preregistered_prompt_selection(tampered)


def test_adv03_survivor_band_not_10pp_fails_closed() -> None:
    """Adversarial 3: survivor band != 10.0 percentage points fails closed."""
    for bad_band in (Decimal("1.0"), Decimal("5.0"), Decimal("9.99"), Decimal("15.0")):
        with pytest.raises(
            PlanBeforeLiveProtocolError, match="INVALID_SURVIVOR_BAND_PP"
        ):
            evaluate_preregistered_prompt_selection(
                copy.deepcopy(EXPECTED_PRIMARY_COUNTS),
                survivor_band_pp=bad_band,
            )


def test_adv04_criterion_ordering_change_fails_closed() -> None:
    """Adversarial 4: criterion ordering changes fail closed."""
    reversed_order = (
        "FINAL_CORE_PASS_RATE",
        "EXACT_GROUNDING_PASS_RATE",
        "VALID_RUN_AND_SCHEMA_RATE",
    )
    with pytest.raises(PlanBeforeLiveProtocolError, match="INVALID_CRITERIA_ORDER"):
        evaluate_preregistered_prompt_selection(
            copy.deepcopy(EXPECTED_PRIMARY_COUNTS),
            criteria_order=reversed_order,
        )


def test_adv05_selecting_p2_without_tie_break_fails_closed() -> None:
    """Adversarial 5: selecting P2 when both [P1, P2] survive all 3 criteria fails closed."""
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="SELECTED_PROMPT_OVERRIDE_FORBIDDEN"
    ):
        evaluate_preregistered_prompt_selection(
            copy.deepcopy(EXPECTED_PRIMARY_COUNTS),
            override_selected_prompt_id="P2",
        )
    with pytest.raises(PlanBeforeLiveProtocolError, match="INVALID_TIE_BREAK_POLICY"):
        evaluate_preregistered_prompt_selection(
            copy.deepcopy(EXPECTED_PRIMARY_COUNTS),
            tie_break_policy="SELECT_P2_ON_CORE_PASS",
        )


def test_adv06_cost_or_latency_influence_fails_closed() -> None:
    """Adversarial 6: cost or latency influencing selection fails closed."""
    with pytest.raises(PlanBeforeLiveProtocolError, match="COST_CRITERION_FORBIDDEN"):
        evaluate_preregistered_prompt_selection(
            copy.deepcopy(EXPECTED_PRIMARY_COUNTS),
            use_cost_criterion=True,
        )
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="LATENCY_CRITERION_FORBIDDEN"
    ):
        evaluate_preregistered_prompt_selection(
            copy.deepcopy(EXPECTED_PRIMARY_COUNTS),
            use_latency_criterion=True,
        )


def test_adv07_candidate_specific_prompt_winner_fails_closed() -> None:
    """Adversarial 7: candidate-specific prompt winner attempt fails closed."""
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="PER_CANDIDATE_PROMPT_SELECTION_FORBIDDEN"
    ):
        evaluate_preregistered_prompt_selection(
            copy.deepcopy(EXPECTED_PRIMARY_COUNTS),
            per_candidate_selection=True,
        )


def _setup_minimal_selection_repo_copy(tmp_path: Path) -> Path:
    """Create a temporary repo copy with the exact frozen files required by prompt selection."""
    repo_copy = tmp_path / "repo"
    shutil.copytree(
        REPO_ROOT / RAW_OUTPUT_ROOT_REL_PATH,
        repo_copy / RAW_OUTPUT_ROOT_REL_PATH,
    )
    w06_dst = repo_copy / "data" / "evaluation" / "w06"
    w06_dst.mkdir(parents=True, exist_ok=True)
    for src_json in (REPO_ROOT / "data" / "evaluation" / "w06").glob("*.json"):
        shutil.copy2(src_json, w06_dst / src_json.name)

    for rel in ("scripts/run_w06_dev_tune_live_v1.py",):
        dst = repo_copy / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / rel, dst)

    # Also copy the 14 scientific code bundle files
    pf_obj = json.loads(
        (REPO_ROOT / PROMPT_FREEZE_REL_PATH).read_text(encoding="utf-8")
    )
    for entry in pf_obj["scientific_code_bundle_file_hashes"]:
        rel = entry["path"]
        dst = repo_copy / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / rel, dst)

    return repo_copy


def test_adv08_raw_results_sha_change_fails_closed(tmp_path: Path) -> None:
    """Adversarial 8: raw results SHA change fails closed."""
    repo_copy = _setup_minimal_selection_repo_copy(tmp_path)
    assert is_verified_downstream_w06_dev_tune_live_results_tree(repo_copy) is True
    assert (
        build_raw_evidence_tree_manifest(repo_copy)["raw_evidence_tree_sha256"]
        == EXPECTED_RAW_EVIDENCE_TREE_SHA256
    )

    target = (
        repo_copy
        / RAW_OUTPUT_ROOT_REL_PATH
        / "W06-DEV-TUNE-P1-C1-W06-DEV-TUNE-001"
        / "raw_provider_response.txt"
    )
    target.write_bytes(target.read_bytes() + b" ")
    assert is_verified_downstream_w06_dev_tune_live_results_tree(repo_copy) is False
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="RESULTS_FREEZE_VERIFICATION_FAILED"
    ):
        verify_frozen_inputs_and_results_freeze(repo_copy)


def test_adv09_results_freeze_receipt_change_fails_closed(tmp_path: Path) -> None:
    """Adversarial 9: results-freeze receipt change fails closed."""
    repo_copy = _setup_minimal_selection_repo_copy(tmp_path)
    rec_path = repo_copy / RESULTS_FREEZE_RECEIPT_REL_PATH
    rec_path.write_bytes(rec_path.read_bytes() + b"\n")
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="RESULTS_FREEZE_VERIFICATION_FAILED"
    ):
        verify_frozen_inputs_and_results_freeze(repo_copy)


def test_adv10_prompt_sha_change_fails_closed(tmp_path: Path) -> None:
    """Adversarial 10: prompt SHA change fails closed."""
    repo_copy = _setup_minimal_selection_repo_copy(tmp_path)
    pf_path = repo_copy / PROMPT_FREEZE_REL_PATH
    pf_obj = json.loads(pf_path.read_text(encoding="utf-8"))
    pf_obj["semantic_prompt_sha256_by_id"]["P1"] = "0" * 64
    pf_path.write_text(json.dumps(pf_obj, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="PROMPT_FREEZE_SHA_MISMATCH"
    ):
        verify_frozen_inputs_and_results_freeze(repo_copy)


def test_adv11_model_winner_set_fails_closed(tmp_path: Path) -> None:
    """Adversarial 11: setting model_winner_selected=True in selection artifact or receipt fails closed."""
    art_path = tmp_path / "w06_dev_tune_prompt_selection_v1.json"
    rec_path = tmp_path / "w06_dev_tune_prompt_selection_01_receipt_v1.json"
    shutil.copy2(REPO_ROOT / PROMPT_SELECTION_ARTIFACT_REL_PATH, art_path)
    shutil.copy2(REPO_ROOT / PROMPT_SELECTION_RECEIPT_REL_PATH, rec_path)

    art_obj = json.loads(art_path.read_text(encoding="utf-8"))
    art_obj["model_winner_selected"] = True
    art_path.write_text(json.dumps(art_obj, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="PROMPT_SELECTION_ARTIFACT_FILE_SHA_MISMATCH|PROMPT_SELECTION_ARTIFACT_CONTENT_MISMATCH",
    ):
        verify_persisted_prompt_selection_artifacts(
            REPO_ROOT,
            selection_artifact_path=art_path,
            selection_receipt_path=rec_path,
        )


def test_adv12_final100_marked_used_or_tampered_fails_closed(tmp_path: Path) -> None:
    """Adversarial 12: marking final100_used=True or tampering Final100 file fails closed."""
    art_path = tmp_path / "w06_dev_tune_prompt_selection_v1.json"
    rec_path = tmp_path / "w06_dev_tune_prompt_selection_01_receipt_v1.json"
    shutil.copy2(REPO_ROOT / PROMPT_SELECTION_ARTIFACT_REL_PATH, art_path)
    shutil.copy2(REPO_ROOT / PROMPT_SELECTION_RECEIPT_REL_PATH, rec_path)

    rec_obj = json.loads(rec_path.read_text(encoding="utf-8"))
    rec_obj["final100_used"] = True
    rec_path.write_text(json.dumps(rec_obj, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="PROMPT_SELECTION_RECEIPT_FILE_SHA_MISMATCH|PROMPT_SELECTION_RECEIPT_CONTENT_MISMATCH",
    ):
        verify_persisted_prompt_selection_artifacts(
            REPO_ROOT,
            selection_artifact_path=art_path,
            selection_receipt_path=rec_path,
        )

    repo_copy = _setup_minimal_selection_repo_copy(tmp_path)
    f100_copy = repo_copy / FORBIDDEN_FINAL100_SCENARIOS_REL_PATH
    f100_copy.write_bytes(f100_copy.read_bytes() + b"\n")
    with pytest.raises(PlanBeforeLiveProtocolError, match="FINAL100_TAMPERED"):
        verify_frozen_inputs_and_results_freeze(repo_copy)


def test_network_kill_switch_blocks_all_outbound_calls() -> None:
    """Section 16: NetworkKillSwitchGuard blocks socket, urllib, and httpx calls."""
    with NetworkKillSwitchGuard() as guard:
        with pytest.raises(OutboundNetworkBlockedError):
            s = socket.socket()
            try:
                s.connect(("127.0.0.1", 80))
            finally:
                s.close()
        with pytest.raises(OutboundNetworkBlockedError):
            urllib.request.urlopen("http://127.0.0.1:80")
        with pytest.raises(OutboundNetworkBlockedError):
            with httpx.Client() as client:
                client.get("http://127.0.0.1:80")
        assert len(guard.blocked_attempts) == 3
