"""Tests for W06-DEV-SELECT-PLAN-FREEZE-01: DEV-SELECT execution-plan freeze and independent offline verification.

Covers:
- DSP-01 through DSP-40 (Section 18)
- All 26 adversarial fail-closed tests (Section 19)
- Offline network kill-switch enforcement (`LIVE_PROVIDER_CALLS_NEW = 0`).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
import socket
import sys
from typing import Any
import urllib.request

import httpx
import httpx2
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
AI_SERVICE_ROOT = REPO_ROOT / "apps" / "ai-service"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for _p in (AI_SERVICE_ROOT, SCRIPTS_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from app.evaluation.dev_live_runner import PlanBeforeLiveProtocolError  # noqa: E402
from app.evaluation.dev_selection_harness import (  # noqa: E402
    EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
    EXPECTED_SEMANTIC_SCHEMA_SHA256,
    FORBIDDEN_FINAL100_BUNDLE_SHA256,
    FORBIDDEN_P11_MANIFEST_SHA256,
    Final100FirewallViolationError,
    canonical_json_bytes,
    compute_common_portable_generation_schema_sha256_v2,
    compute_provider_config_registry_sha256,
    compute_scientific_code_bundle_sha256,
    compute_semantic_schema_sha256,
    normalize_lf_bytes,
    sha256_bytes,
)
from freeze_w06_dev_prompt_candidates import (  # noqa: E402
    EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256,
    P1_AUTHORITATIVE_SEMANTIC_PROMPT_SHA256,
    P1_EXPECTED_PROMPT_VERSION,
    P1_EXPECTED_SYSTEM_PROMPT_SHA256,
    P1_EXPECTED_USER_PROMPT_TEMPLATE_SHA256,
    build_p1_spec,
    build_p2_spec,
)
from freeze_w06_dev_select_plan import (  # noqa: E402
    ALLOWED_DEV_SELECT_PROMPT_IDS,
    CODE_BASIS_COMMIT_SHA,
    CODE_COMMIT_SHA,
    DEV_FINAL_OVERLAP_RECEIPT_REL_PATH,
    DEV_FIXTURE_BUNDLE_REL_PATH,
    DEV_FIXTURE_MANIFEST_REL_PATH,
    DEV_SELECT_PLAN_REL_PATH,
    EXPECTED_ASSIGNED_CELLS,
    EXPECTED_ATTEMPTS_PER_CELL,
    EXPECTED_CANDIDATE_IDS,
    EXPECTED_CANDIDATE_REGISTRY_SHA256,
    EXPECTED_DEV_FINAL_OVERLAP_RECEIPT_SHA256,
    EXPECTED_DEV_FIXTURE_BUNDLE_SHA256,
    EXPECTED_DEV_FIXTURE_FREEZE_RECEIPT_SHA256,
    EXPECTED_DEV_FIXTURE_MANIFEST_SHA256,
    EXPECTED_DEV_SELECT_FIXTURE_IDS,
    EXPECTED_DEV_SELECT_MARGINALS,
    EXPECTED_DEV_SELECT_PLAN_FILE_SHA256,
    EXPECTED_DEV_SELECT_PLAN_INTERNAL_SHA256,
    EXPECTED_DEV_SELECT_SUPPORT_CLASS_MARGINALS,
    EXPECTED_FIXTURE_COUNT,
    EXPECTED_PLAN_FREEZE_RECEIPT_FILE_SHA256,
    EXPECTED_PROVIDER_CONFIG_REGISTRY_SHA256,
    EXPECTED_RETRY_CALLS,
    EXPECTED_UNIQUE_CELL_KEYS,
    EXPECTED_UNIQUE_RUN_IDS,
    FORBIDDEN_DEV_SELECT_PROMPT_IDS,
    FORBIDDEN_FINAL100_SCENARIOS_REL_PATH,
    FORBIDDEN_P11_MANIFEST_REL_PATH,
    PHASE_DEV_SELECT,
    PLAN_FREEZE_DOC_REL_PATH,
    PLAN_FREEZE_RECEIPT_REL_PATH,
    SOURCE_DEVELOP_SHA,
    NetworkKillSwitchGuard,
    OutboundNetworkBlockedError,
    _bind_frozen_code_basis_commit,
    build_frozen_dev_select_execution_plan,
    load_and_verify_locked_p1_prompt_spec,
    validate_dev_select_execution_plan_dict,
    validate_plan_freeze_receipt_dict,
    verify_candidate_and_provider_config_registries,
    verify_frozen_dev_select_fixtures_and_marginals,
    verify_persisted_dev_select_plan_and_receipt,
    verify_source_develop_provenance,
    verify_upstream_prompt_selection_gate,
)
from select_w06_dev_tune_prompt import (  # noqa: E402
    EXPECTED_PROMPT_SELECTION_ARTIFACT_FILE_SHA256,
    EXPECTED_PROMPT_SELECTION_ARTIFACT_INTERNAL_SHA256,
    EXPECTED_PROMPT_SELECTION_RECEIPT_FILE_SHA256,
    PROMPT_SELECTION_ARTIFACT_REL_PATH,
    PROMPT_SELECTION_RECEIPT_REL_PATH,
)


@pytest.fixture(scope="module")
def verified_plan_freeze_state() -> dict[str, Any]:
    """Load and verify the persisted DEV-SELECT execution plan, freeze receipt, and upstream authorities once per module."""
    with NetworkKillSwitchGuard():
        src_prov = verify_source_develop_provenance(REPO_ROOT)
        upstream_gate = verify_upstream_prompt_selection_gate(REPO_ROOT)
        fix_info = verify_frozen_dev_select_fixtures_and_marginals(REPO_ROOT)
        cand_info = verify_candidate_and_provider_config_registries()
        locked_p1 = load_and_verify_locked_p1_prompt_spec()
        persisted_ver = verify_persisted_dev_select_plan_and_receipt(REPO_ROOT)

        plan_path = REPO_ROOT / DEV_SELECT_PLAN_REL_PATH
        rec_path = REPO_ROOT / PLAN_FREEZE_RECEIPT_REL_PATH
        doc_path = REPO_ROOT / PLAN_FREEZE_DOC_REL_PATH

        plan_obj = json.loads(plan_path.read_text(encoding="utf-8"))
        rec_obj = json.loads(rec_path.read_text(encoding="utf-8"))
        doc_text = doc_path.read_text(encoding="utf-8")

        return {
            "source_provenance": src_prov,
            "upstream_gate": upstream_gate,
            "fixtures_info": fix_info,
            "candidates_info": cand_info,
            "locked_p1": locked_p1,
            "persisted_verification": persisted_ver,
            "plan": plan_obj,
            "receipt": rec_obj,
            "doc_text": doc_text,
        }


# ==============================================================================
# 1. DSP-01 .. DSP-40 REQUIRED FAIL-CLOSED CHECKS (SECTION 18)
# ==============================================================================


def test_dsp01_source_develop_exact_or_ancestry_valid(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """DSP-01: source develop exact / ancestry valid."""
    prov = verified_plan_freeze_state["source_provenance"]
    rec = verified_plan_freeze_state["receipt"]
    assert prov["source_develop_sha"] == SOURCE_DEVELOP_SHA
    assert prov["ancestry_verified"] is True
    assert rec["source_develop_sha"] == SOURCE_DEVELOP_SHA
    assert rec["dsp_checks"]["DSP-01_source_develop_exact_or_ancestry_valid"] == "PASS"


def test_dsp02_prompt_selection_artifact_exact(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """DSP-02: prompt-selection artifact exact."""
    up = verified_plan_freeze_state["upstream_gate"]
    rec = verified_plan_freeze_state["receipt"]
    assert (
        up["prompt_selection_artifact_file_sha256"]
        == EXPECTED_PROMPT_SELECTION_ARTIFACT_FILE_SHA256
    )
    assert (
        up["prompt_selection_artifact_internal_sha256"]
        == EXPECTED_PROMPT_SELECTION_ARTIFACT_INTERNAL_SHA256
    )
    assert (
        rec["prompt_selection_artifact_file_sha256"]
        == EXPECTED_PROMPT_SELECTION_ARTIFACT_FILE_SHA256
    )
    assert (
        rec["prompt_selection_artifact_internal_sha256"]
        == EXPECTED_PROMPT_SELECTION_ARTIFACT_INTERNAL_SHA256
    )
    assert rec["dsp_checks"]["DSP-02_prompt_selection_artifact_exact"] == "PASS"


def test_dsp03_prompt_selection_receipt_exact(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """DSP-03: prompt-selection receipt exact."""
    up = verified_plan_freeze_state["upstream_gate"]
    rec = verified_plan_freeze_state["receipt"]
    assert (
        up["prompt_selection_receipt_file_sha256"]
        == EXPECTED_PROMPT_SELECTION_RECEIPT_FILE_SHA256
    )
    assert (
        rec["prompt_selection_receipt_file_sha256"]
        == EXPECTED_PROMPT_SELECTION_RECEIPT_FILE_SHA256
    )
    assert rec["dsp_checks"]["DSP-03_prompt_selection_receipt_exact"] == "PASS"


def test_dsp04_selected_prompt_p1_exact(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """DSP-04: selected prompt P1 exact."""
    up = verified_plan_freeze_state["upstream_gate"]
    p1 = verified_plan_freeze_state["locked_p1"]
    rec = verified_plan_freeze_state["receipt"]
    assert up["selected_prompt_id"] == "P1"
    assert up["final_survivors"] == ["P1", "P2"]
    assert up["superiority_claim"] is False
    assert p1.prompt_id == "P1"
    assert p1.prompt_version == P1_EXPECTED_PROMPT_VERSION
    assert rec["selected_prompt_id"] == "P1"
    assert rec["selected_prompt_version"] == P1_EXPECTED_PROMPT_VERSION
    assert rec["dsp_checks"]["DSP-04_selected_prompt_p1_exact"] == "PASS"


def test_dsp05_selected_p1_semantic_sha_exact(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """DSP-05: selected P1 semantic SHA exact."""
    p1 = verified_plan_freeze_state["locked_p1"]
    rec = verified_plan_freeze_state["receipt"]
    assert p1.semantic_prompt_sha256 == P1_AUTHORITATIVE_SEMANTIC_PROMPT_SHA256
    assert (
        rec["selected_prompt_semantic_sha256"]
        == P1_AUTHORITATIVE_SEMANTIC_PROMPT_SHA256
    )
    assert (
        rec["selected_prompt_system_sha256"] == P1_EXPECTED_SYSTEM_PROMPT_SHA256
    )
    assert (
        rec["selected_prompt_user_template_sha256"]
        == P1_EXPECTED_USER_PROMPT_TEMPLATE_SHA256
    )
    assert rec["dsp_checks"]["DSP-05_selected_p1_semantic_sha_exact"] == "PASS"


def test_dsp06_p2_forbidden_in_dev_select(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """DSP-06: P2 forbidden in DEV-SELECT."""
    rec = verified_plan_freeze_state["receipt"]
    assert list(ALLOWED_DEV_SELECT_PROMPT_IDS) == ["P1"]
    assert "P2" in FORBIDDEN_DEV_SELECT_PROMPT_IDS
    assert "P3" in FORBIDDEN_DEV_SELECT_PROMPT_IDS
    assert rec["allowed_dev_select_prompt_ids"] == ["P1"]
    assert rec["forbidden_dev_select_prompt_ids"] == ["P2", "P3"]
    assert rec["dsp_checks"]["DSP-06_p2_forbidden_in_dev_select"] == "PASS"


def test_dsp07_candidate_ids_exact_c1_c2_c3(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """DSP-07: candidate IDs exactly C1/C2/C3."""
    cand_reg = verified_plan_freeze_state["candidates_info"]["candidate_registry"]
    rec = verified_plan_freeze_state["receipt"]
    assert cand_reg.ordered_candidate_ids == ["C1", "C2", "C3"]
    assert rec["candidate_ids"] == ["C1", "C2", "C3"]
    assert rec["dsp_checks"]["DSP-07_candidate_ids_exact_c1_c2_c3"] == "PASS"


def test_dsp08_candidate_registry_sha_exact(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """DSP-08: candidate registry SHA exact."""
    c_info = verified_plan_freeze_state["candidates_info"]
    rec = verified_plan_freeze_state["receipt"]
    assert c_info["candidate_registry_sha256"] == EXPECTED_CANDIDATE_REGISTRY_SHA256
    assert rec["candidate_registry_sha256"] == EXPECTED_CANDIDATE_REGISTRY_SHA256
    assert rec["dsp_checks"]["DSP-08_candidate_registry_sha_exact"] == "PASS"


def test_dsp09_provider_config_registry_sha_exact(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """DSP-09: provider config registry SHA exact."""
    c_info = verified_plan_freeze_state["candidates_info"]
    rec = verified_plan_freeze_state["receipt"]
    assert (
        c_info["provider_config_registry_sha256"]
        == EXPECTED_PROVIDER_CONFIG_REGISTRY_SHA256
    )
    assert (
        compute_provider_config_registry_sha256()
        == EXPECTED_PROVIDER_CONFIG_REGISTRY_SHA256
    )
    assert (
        rec["provider_config_registry_sha256"]
        == EXPECTED_PROVIDER_CONFIG_REGISTRY_SHA256
    )
    assert rec["dsp_checks"]["DSP-09_provider_config_registry_sha_exact"] == "PASS"


def test_dsp10_dev_fixture_bundle_sha_exact(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """DSP-10: DEV fixture bundle SHA exact."""
    f_info = verified_plan_freeze_state["fixtures_info"]
    rec = verified_plan_freeze_state["receipt"]
    assert f_info["dev_fixture_bundle_sha256"] == EXPECTED_DEV_FIXTURE_BUNDLE_SHA256
    assert rec["dev_fixture_bundle_sha256"] == EXPECTED_DEV_FIXTURE_BUNDLE_SHA256
    assert rec["dsp_checks"]["DSP-10_dev_fixture_bundle_sha_exact"] == "PASS"


def test_dsp11_dev_manifest_sha_exact(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """DSP-11: DEV manifest SHA exact."""
    f_info = verified_plan_freeze_state["fixtures_info"]
    rec = verified_plan_freeze_state["receipt"]
    assert (
        f_info["dev_fixture_manifest_sha256"] == EXPECTED_DEV_FIXTURE_MANIFEST_SHA256
    )
    assert rec["dev_fixture_manifest_sha256"] == EXPECTED_DEV_FIXTURE_MANIFEST_SHA256
    assert rec["dsp_checks"]["DSP-11_dev_manifest_sha_exact"] == "PASS"


def test_dsp12_overlap_receipt_sha_exact(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """DSP-12: overlap receipt SHA exact."""
    f_info = verified_plan_freeze_state["fixtures_info"]
    rec = verified_plan_freeze_state["receipt"]
    assert (
        f_info["dev_final_overlap_receipt_sha256"]
        == EXPECTED_DEV_FINAL_OVERLAP_RECEIPT_SHA256
    )
    assert (
        f_info["dev_fixture_freeze_receipt_sha256"]
        == EXPECTED_DEV_FIXTURE_FREEZE_RECEIPT_SHA256
    )
    assert (
        rec["dev_final_overlap_receipt_sha256"]
        == EXPECTED_DEV_FINAL_OVERLAP_RECEIPT_SHA256
    )
    assert (
        rec["dev_fixture_freeze_receipt_sha256"]
        == EXPECTED_DEV_FIXTURE_FREEZE_RECEIPT_SHA256
    )
    assert rec["dsp_checks"]["DSP-12_overlap_receipt_sha_exact"] == "PASS"


def test_dsp13_fixture_count_exact_60(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """DSP-13: fixture count exactly 60."""
    bundle = verified_plan_freeze_state["fixtures_info"]["bundle"]
    plan = verified_plan_freeze_state["plan"]
    rec = verified_plan_freeze_state["receipt"]
    assert bundle.dev_select_count == 60
    assert len(bundle.dev_select_fixtures) == 60
    assert plan["fixture_count"] == 60
    assert rec["fixture_count"] == 60
    assert rec["dsp_checks"]["DSP-13_fixture_count_exact_60"] == "PASS"


def test_dsp14_fixture_ids_exact_001_to_060(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """DSP-14: fixture IDs exactly W06-DEV-SELECT-001..060."""
    bundle = verified_plan_freeze_state["fixtures_info"]["bundle"]
    rec = verified_plan_freeze_state["receipt"]
    fids = [sc.scenario_id for sc in bundle.dev_select_fixtures]
    assert tuple(fids) == EXPECTED_DEV_SELECT_FIXTURE_IDS
    assert len(set(fids)) == 60
    assert all(not fid.startswith("W06-DEV-TUNE-") for fid in fids)
    assert rec["dsp_checks"]["DSP-14_fixture_ids_exact_001_to_060"] == "PASS"


def test_dsp15_destination_marginals_exact(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """DSP-15: destination marginals exact (ha-noi=20, da-nang=20, ha-long=20)."""
    m = verified_plan_freeze_state["fixtures_info"]["dev_select_marginals"]
    assert m["destination"] == {"ha-noi": 20, "da-nang": 20, "ha-long": 20}
    assert (
        verified_plan_freeze_state["receipt"]["dsp_checks"][
            "DSP-15_destination_marginals_exact"
        ]
        == "PASS"
    )


def test_dsp16_days_marginals_exact(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """DSP-16: days marginals exact (2=20, 3=20, 4=20)."""
    m = verified_plan_freeze_state["fixtures_info"]["dev_select_marginals"]
    assert m["days"] == {"2": 20, "3": 20, "4": 20}
    assert (
        verified_plan_freeze_state["receipt"]["dsp_checks"][
            "DSP-16_days_marginals_exact"
        ]
        == "PASS"
    )


def test_dsp17_interest_count_marginals_exact(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """DSP-17: interest-count marginals exact (1=20, 2=20, 3=20)."""
    m = verified_plan_freeze_state["fixtures_info"]["dev_select_marginals"]
    assert m["interest_count"] == {"1": 20, "2": 20, "3": 20}
    assert (
        verified_plan_freeze_state["receipt"]["dsp_checks"][
            "DSP-17_interest_count_marginals_exact"
        ]
        == "PASS"
    )


def test_dsp18_budget_marginals_exact(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """DSP-18: budget marginals exact (B1=15, B2=15, B3=15, null=15)."""
    m = verified_plan_freeze_state["fixtures_info"]["dev_select_marginals"]
    assert m["budget"] == {"B1": 15, "B2": 15, "B3": 15, "null": 15}
    assert (
        verified_plan_freeze_state["receipt"]["dsp_checks"][
            "DSP-18_budget_marginals_exact"
        ]
        == "PASS"
    )


def test_dsp19_travel_style_marginals_exact(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """DSP-19: travel-style marginals exact (BACKPACKER=15, BUDGET=15, COMFORT=15, LUXURY=15)."""
    m = verified_plan_freeze_state["fixtures_info"]["dev_select_marginals"]
    assert m["travel_style"] == {
        "BACKPACKER": 15,
        "BUDGET": 15,
        "COMFORT": 15,
        "LUXURY": 15,
    }
    assert (
        verified_plan_freeze_state["receipt"]["dsp_checks"][
            "DSP-19_travel_style_marginals_exact"
        ]
        == "PASS"
    )


def test_dsp20_weekend_marginals_exact(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """DSP-20: weekend marginals exact (true=30, false=30) + support class observed values."""
    f_info = verified_plan_freeze_state["fixtures_info"]
    assert f_info["dev_select_marginals"]["weekend"] == {"true": 30, "false": 30}
    assert (
        f_info["support_class_marginals"] == EXPECTED_DEV_SELECT_SUPPORT_CLASS_MARGINALS
    )
    assert (
        verified_plan_freeze_state["receipt"]["dsp_checks"][
            "DSP-20_weekend_marginals_exact"
        ]
        == "PASS"
    )


def test_dsp21_execution_plan_phase_dev_select(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """DSP-21: execution-plan phase DEV_SELECT."""
    plan = verified_plan_freeze_state["plan"]
    rec = verified_plan_freeze_state["receipt"]
    assert plan["phase"] == "DEV_SELECT"
    assert rec["phase"] == "DEV_SELECT"
    assert all(c["phase"] == "DEV_SELECT" for c in plan["cells"])
    assert rec["dsp_checks"]["DSP-21_execution_plan_phase_dev_select"] == "PASS"


def test_dsp22_prompt_ids_exact_p1(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """DSP-22: prompt_ids exactly [P1]."""
    plan = verified_plan_freeze_state["plan"]
    rec = verified_plan_freeze_state["receipt"]
    assert plan["prompt_ids"] == ["P1"]
    assert all(c["prompt_id"] == "P1" for c in plan["cells"])
    assert rec["prompt_count"] == 1
    assert rec["dsp_checks"]["DSP-22_prompt_ids_exact_p1"] == "PASS"


def test_dsp23_candidate_ids_exact_c1_c2_c3(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """DSP-23: candidate_ids exactly [C1, C2, C3]."""
    plan = verified_plan_freeze_state["plan"]
    rec = verified_plan_freeze_state["receipt"]
    assert plan["candidate_ids"] == ["C1", "C2", "C3"]
    assert rec["candidate_count"] == 3
    assert rec["dsp_checks"]["DSP-23_candidate_ids_exact_c1_c2_c3"] == "PASS"


def test_dsp24_expected_total_cells_exact_180(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """DSP-24: expected_total_cells exactly 180."""
    plan = verified_plan_freeze_state["plan"]
    rec = verified_plan_freeze_state["receipt"]
    assert plan["expected_total_cells"] == 180
    assert rec["assigned_cells"] == 180
    assert rec["maximum_future_live_generation_calls"] == 180
    assert rec["dsp_checks"]["DSP-24_expected_total_cells_exact_180"] == "PASS"


def test_dsp25_actual_cells_exact_180(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """DSP-25: actual cells exactly 180."""
    plan = verified_plan_freeze_state["plan"]
    rec = verified_plan_freeze_state["receipt"]
    assert len(plan["cells"]) == EXPECTED_ASSIGNED_CELLS == 180
    assert rec["dsp_checks"]["DSP-25_actual_cells_exact_180"] == "PASS"


def test_dsp26_unique_run_ids_exact_180(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """DSP-26: unique run IDs exactly 180."""
    plan = verified_plan_freeze_state["plan"]
    rec = verified_plan_freeze_state["receipt"]
    run_ids = [c["run_id"] for c in plan["cells"]]
    assert len(set(run_ids)) == EXPECTED_UNIQUE_RUN_IDS == 180
    assert run_ids[0] == "W06-DEV-SELECT-P1-C1-W06-DEV-SELECT-001"
    assert run_ids[1] == "W06-DEV-SELECT-P1-C2-W06-DEV-SELECT-001"
    assert run_ids[2] == "W06-DEV-SELECT-P1-C3-W06-DEV-SELECT-001"
    assert run_ids[-1] == "W06-DEV-SELECT-P1-C3-W06-DEV-SELECT-060"
    assert rec["unique_run_ids"] == 180
    assert rec["dsp_checks"]["DSP-26_unique_run_ids_exact_180"] == "PASS"


def test_dsp27_unique_cell_keys_exact_180(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """DSP-27: unique cell keys (phase, prompt_id, candidate_id, fixture_id) exactly 180."""
    plan = verified_plan_freeze_state["plan"]
    rec = verified_plan_freeze_state["receipt"]
    keys = [
        (c["phase"], c["prompt_id"], c["candidate_id"], c["fixture_id"])
        for c in plan["cells"]
    ]
    assert len(set(keys)) == EXPECTED_UNIQUE_CELL_KEYS == 180
    assert rec["unique_cell_keys"] == 180
    assert rec["dsp_checks"]["DSP-27_unique_cell_keys_exact_180"] == "PASS"


def test_dsp28_each_fixture_once_per_candidate(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """DSP-28: each fixture appears exactly once per candidate."""
    plan = verified_plan_freeze_state["plan"]
    rec = verified_plan_freeze_state["receipt"]
    by_fixture: dict[str, list[str]] = {
        fid: [] for fid in EXPECTED_DEV_SELECT_FIXTURE_IDS
    }
    for c in plan["cells"]:
        by_fixture[c["fixture_id"]].append(c["candidate_id"])
    for fid, cids in by_fixture.items():
        assert cids == ["C1", "C2", "C3"], f"Mismatch for {fid}: {cids}"
    assert rec["dsp_checks"]["DSP-28_each_fixture_once_per_candidate"] == "PASS"


def test_dsp29_attempts_per_cell_exact_1(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """DSP-29: attempts per cell exactly 1."""
    plan = verified_plan_freeze_state["plan"]
    rec = verified_plan_freeze_state["receipt"]
    assert all(c["attempt_number"] == EXPECTED_ATTEMPTS_PER_CELL == 1 for c in plan["cells"])
    assert rec["attempts_per_cell"] == 1
    assert rec["dsp_checks"]["DSP-29_attempts_per_cell_exact_1"] == "PASS"


def test_dsp30_all_retries_zero(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """DSP-30: all retries zero."""
    plan = verified_plan_freeze_state["plan"]
    rec = verified_plan_freeze_state["receipt"]
    for c in plan["cells"]:
        assert c["retry"] == 0
        assert c["automatic_retry"] == 0
        assert c["transport_retry"] == 0
        assert c["manual_retry"] == 0
    assert rec["retry_calls"] == EXPECTED_RETRY_CALLS == 0
    assert rec["dsp_checks"]["DSP-30_all_retries_zero"] == "PASS"


def test_dsp31_fallback_repair_tools_disabled(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """DSP-31: fallback/repair/tools disabled."""
    plan = verified_plan_freeze_state["plan"]
    rec = verified_plan_freeze_state["receipt"]
    for c in plan["cells"]:
        assert c["fallback"] is False
        assert c["repair"] == 0
        assert c["llm_repair"] == 0
        assert c["deterministic_semantic_repair"] is False
        assert c["tools"] is False
    assert rec["dsp_checks"]["DSP-31_fallback_repair_tools_disabled"] == "PASS"


def test_dsp32_code_basis_exact(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """DSP-32: code basis exact (`c0adf74ceda9ffaf8b4ec42d299932e33f448e6a`)."""
    plan = verified_plan_freeze_state["plan"]
    rec = verified_plan_freeze_state["receipt"]
    assert rec["code_basis_commit_sha"] == CODE_BASIS_COMMIT_SHA
    assert rec["code_commit_sha"] == CODE_COMMIT_SHA
    for c in plan["cells"]:
        assert c["code_basis_commit_sha"] == CODE_BASIS_COMMIT_SHA
        assert c["code_commit_sha"] == CODE_COMMIT_SHA
    assert rec["dsp_checks"]["DSP-32_code_basis_exact"] == "PASS"


def test_dsp33_scientific_bundle_exact(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """DSP-33: scientific bundle exact."""
    plan = verified_plan_freeze_state["plan"]
    rec = verified_plan_freeze_state["receipt"]
    bundle_sha = compute_scientific_code_bundle_sha256(REPO_ROOT)
    assert bundle_sha == EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
    assert rec["scientific_code_bundle_sha256"] == EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
    for c in plan["cells"]:
        assert c["scientific_code_bundle_sha256"] == EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
    assert rec["dsp_checks"]["DSP-33_scientific_bundle_exact"] == "PASS"


def test_dsp34_portable_schema_exact(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """DSP-34: portable schema exact."""
    plan = verified_plan_freeze_state["plan"]
    rec = verified_plan_freeze_state["receipt"]
    assert (
        compute_common_portable_generation_schema_sha256_v2()
        == EXPECTED_PORTABLE_SCHEMA_V2_SHA256
    )
    assert rec["portable_schema_v2_sha256"] == EXPECTED_PORTABLE_SCHEMA_V2_SHA256
    for c in plan["cells"]:
        assert (
            c["portable_generation_schema_v2_sha256"]
            == EXPECTED_PORTABLE_SCHEMA_V2_SHA256
        )
    assert rec["dsp_checks"]["DSP-34_portable_schema_exact"] == "PASS"


def test_dsp35_semantic_schema_exact(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """DSP-35: semantic schema exact."""
    plan = verified_plan_freeze_state["plan"]
    rec = verified_plan_freeze_state["receipt"]
    assert compute_semantic_schema_sha256() == EXPECTED_SEMANTIC_SCHEMA_SHA256
    assert rec["semantic_schema_sha256"] == EXPECTED_SEMANTIC_SCHEMA_SHA256
    for c in plan["cells"]:
        assert c["semantic_schema_sha256"] == EXPECTED_SEMANTIC_SCHEMA_SHA256
    assert rec["dsp_checks"]["DSP-35_semantic_schema_exact"] == "PASS"


def test_dsp36_plan_internal_sha_recomputes_exact(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """DSP-36: plan internal SHA recomputes exactly."""
    plan = verified_plan_freeze_state["plan"]
    rec = verified_plan_freeze_state["receipt"]
    recomputed = sha256_bytes(canonical_json_bytes(plan["cells"]))
    assert recomputed == EXPECTED_DEV_SELECT_PLAN_INTERNAL_SHA256
    assert plan["plan_sha256"] == EXPECTED_DEV_SELECT_PLAN_INTERNAL_SHA256
    assert rec["dev_select_plan_internal_sha256"] == EXPECTED_DEV_SELECT_PLAN_INTERNAL_SHA256
    assert rec["DEV_SELECT_PLAN_INTERNAL_SHA256"] == EXPECTED_DEV_SELECT_PLAN_INTERNAL_SHA256
    assert rec["dsp_checks"]["DSP-36_plan_internal_sha_recomputes_exact"] == "PASS"


def test_dsp37_persisted_plan_file_sha_exact(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """DSP-37: persisted plan file SHA exact."""
    rec = verified_plan_freeze_state["receipt"]
    plan_file_sha = sha256_bytes(
        normalize_lf_bytes((REPO_ROOT / DEV_SELECT_PLAN_REL_PATH).read_bytes())
    )
    rec_file_sha = sha256_bytes(
        normalize_lf_bytes((REPO_ROOT / PLAN_FREEZE_RECEIPT_REL_PATH).read_bytes())
    )
    assert plan_file_sha == EXPECTED_DEV_SELECT_PLAN_FILE_SHA256
    assert rec["dev_select_plan_file_sha256"] == EXPECTED_DEV_SELECT_PLAN_FILE_SHA256
    assert rec["DEV_SELECT_PLAN_FILE_SHA256"] == EXPECTED_DEV_SELECT_PLAN_FILE_SHA256
    assert rec_file_sha == EXPECTED_PLAN_FREEZE_RECEIPT_FILE_SHA256
    assert rec["dsp_checks"]["DSP-37_persisted_plan_file_sha_exact"] == "PASS"


def test_dsp38_final100_untouched_and_unused(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """DSP-38: Final100 untouched / unused."""
    rec = verified_plan_freeze_state["receipt"]
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
    assert rec["final100_used"] is False
    assert rec["dsp_checks"]["DSP-38_final100_untouched_and_unused"] == "PASS"


def test_dsp39_model_winner_remains_false(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """DSP-39: model winner remains false."""
    rec = verified_plan_freeze_state["receipt"]
    ver = verified_plan_freeze_state["persisted_verification"]
    assert rec["model_winner_selected"] is False
    assert rec["dev_select_execution_started"] is False
    assert rec["stochasticity_execution_started"] is False
    assert ver["model_winner_selected"] is False
    assert rec["dsp_checks"]["DSP-39_model_winner_remains_false"] == "PASS"


def test_dsp40_live_provider_calls_new_zero(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """DSP-40: live provider calls new = 0."""
    rec = verified_plan_freeze_state["receipt"]
    ver = verified_plan_freeze_state["persisted_verification"]
    assert rec["live_provider_calls_new"] == 0
    assert rec["provider_cost_usd_new"] == 0
    assert rec["live_execution_capability_issued"] is False
    assert rec["production_transport_started"] is False
    assert ver["live_provider_calls_new"] == 0
    assert ver["provider_cost_usd_new"] == 0
    assert rec["dsp_checks"]["DSP-40_live_provider_calls_new_zero"] == "PASS"


# ==============================================================================
# 2. SECTION 19 ADVERSARIAL TESTS (ALL 26 REQUIRED FAIL-CLOSED CHECKS)
# ==============================================================================


def test_adv01_changing_p1_to_p2_fails_closed() -> None:
    """Adversarial 1: changing P1 to P2 fails closed."""
    p2 = build_p2_spec()
    with pytest.raises(PlanBeforeLiveProtocolError, match="FORBIDDEN_DEV_SELECT_PROMPT_ID"):
        load_and_verify_locked_p1_prompt_spec(prompt_spec=p2)


def test_adv02_changing_p1_semantic_sha_fails_closed() -> None:
    """Adversarial 2: changing P1 semantic SHA fails closed."""
    p1 = build_p1_spec()
    tampered_p1 = p1.model_copy(update={"semantic_prompt_sha256": "a" * 64})
    with pytest.raises(PlanBeforeLiveProtocolError, match="LOCKED_P1_SEMANTIC_SHA_MISMATCH"):
        load_and_verify_locked_p1_prompt_spec(prompt_spec=tampered_p1)


def test_adv03_deleting_one_cell_179_fails_closed(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """Adversarial 3: deleting one cell => 179 fails closed."""
    tampered = copy.deepcopy(verified_plan_freeze_state["plan"])
    tampered["cells"].pop()
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="DEV_SELECT_PLAN_CELLS_COUNT_MISMATCH"
    ):
        validate_dev_select_execution_plan_dict(tampered)


def test_adv04_adding_one_cell_181_fails_closed(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """Adversarial 4: adding one cell => 181 fails closed."""
    tampered = copy.deepcopy(verified_plan_freeze_state["plan"])
    tampered["cells"].append(copy.deepcopy(tampered["cells"][0]))
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="DEV_SELECT_PLAN_CELLS_COUNT_MISMATCH"
    ):
        validate_dev_select_execution_plan_dict(tampered)


def test_adv05_duplicate_run_id_fails_closed(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """Adversarial 5: duplicate run_id fails closed."""
    tampered = copy.deepcopy(verified_plan_freeze_state["plan"])
    tampered["cells"][1]["run_id"] = tampered["cells"][0]["run_id"]
    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="CELL_RUN_ID_MISMATCH|DUPLICATE_RUN_IDS_DETECTED",
    ):
        validate_dev_select_execution_plan_dict(tampered)


def test_adv06_duplicate_cell_key_fails_closed(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """Adversarial 6: duplicate cell key fails closed."""
    tampered = copy.deepcopy(verified_plan_freeze_state["plan"])
    tampered["cells"][1] = copy.deepcopy(tampered["cells"][0])
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="DUPLICATE_RUN_IDS_DETECTED|DUPLICATE_CELL_KEYS_DETECTED"
    ):
        validate_dev_select_execution_plan_dict(tampered)


def test_adv07_candidate_c4_fails_closed(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """Adversarial 7: candidate C4 fails closed."""
    tampered = copy.deepcopy(verified_plan_freeze_state["plan"])
    tampered["cells"][0]["candidate_id"] = "C4"
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="CELL_CANDIDATE_ID_FORBIDDEN"
    ):
        validate_dev_select_execution_plan_dict(tampered)


def test_adv08_candidate_removed_fails_closed(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """Adversarial 8: candidate removed fails closed."""
    tampered = copy.deepcopy(verified_plan_freeze_state["plan"])
    tampered["candidate_ids"] = ["C1", "C3"]
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="DEV_SELECT_PLAN_CANDIDATE_IDS_MISMATCH"
    ):
        validate_dev_select_execution_plan_dict(tampered)


def test_adv09_fixture_removed_fails_closed(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """Adversarial 9: fixture removed fails closed."""
    tampered = copy.deepcopy(verified_plan_freeze_state["plan"])
    tampered["fixture_count"] = 59
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="DEV_SELECT_PLAN_FIXTURE_COUNT_MISMATCH"
    ):
        validate_dev_select_execution_plan_dict(tampered)


def test_adv10_dev_tune_fixture_injected_fails_closed(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """Adversarial 10: DEV-TUNE fixture injected fails closed."""
    tampered = copy.deepcopy(verified_plan_freeze_state["plan"])
    tampered["cells"][0]["fixture_id"] = "W06-DEV-TUNE-001"
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="CELL_FIXTURE_ID_FORBIDDEN"
    ):
        validate_dev_select_execution_plan_dict(tampered)


def test_adv11_wrong_phase_dev_tune_fails_closed(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """Adversarial 11: wrong phase DEV_TUNE fails closed."""
    tampered = copy.deepcopy(verified_plan_freeze_state["plan"])
    tampered["phase"] = "DEV_TUNE"
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="DEV_SELECT_PLAN_WRONG_PHASE"
    ):
        validate_dev_select_execution_plan_dict(tampered)


def test_adv12_wrong_code_basis_fails_closed(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """Adversarial 12: wrong code basis (e.g. old DEV-TUNE code basis) fails closed."""
    tampered = copy.deepcopy(verified_plan_freeze_state["plan"])
    tampered["cells"][0]["code_basis_commit_sha"] = (
        "60d52d720e66f5af8e82fabf9cebe2ea0e8a9e26"
    )
    with pytest.raises(PlanBeforeLiveProtocolError, match="CELL_CODE_BASIS_MISMATCH"):
        validate_dev_select_execution_plan_dict(tampered)


def test_adv13_modified_scientific_bundle_fails_closed(
    verified_plan_freeze_state: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Adversarial 13: modified scientific bundle fails closed both in cell check and code basis binder."""
    tampered = copy.deepcopy(verified_plan_freeze_state["plan"])
    tampered["cells"][0]["scientific_code_bundle_sha256"] = "b" * 64
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="CELL_SCIENTIFIC_BUNDLE_SHA_MISMATCH"
    ):
        validate_dev_select_execution_plan_dict(tampered)

    import freeze_w06_dev_select_plan as mod

    monkeypatch.setattr(
        mod, "compute_scientific_code_bundle_sha256", lambda repo_root=REPO_ROOT: "f" * 64
    )
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="BLOCKED_BY_SCIENTIFIC_BUNDLE_MUTATION"
    ):
        with _bind_frozen_code_basis_commit():
            pass


def test_adv14_modified_provider_config_sha_fails_closed(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """Adversarial 14: modified provider config SHA fails closed."""
    tampered = copy.deepcopy(verified_plan_freeze_state["plan"])
    tampered["cells"][0]["provider_config_sha256"] = "c" * 64
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="CELL_PROVIDER_CONFIG_SHA_MISMATCH"
    ):
        validate_dev_select_execution_plan_dict(tampered)


def test_adv15_retry_1_fails_closed(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """Adversarial 15: retry=1 fails closed."""
    tampered = copy.deepcopy(verified_plan_freeze_state["plan"])
    tampered["cells"][0]["retry"] = 1
    with pytest.raises(PlanBeforeLiveProtocolError, match="CELL_RETRY_NONZERO"):
        validate_dev_select_execution_plan_dict(tampered)


def test_adv16_fallback_true_fails_closed(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """Adversarial 16: fallback=true fails closed."""
    tampered = copy.deepcopy(verified_plan_freeze_state["plan"])
    tampered["cells"][0]["fallback"] = True
    with pytest.raises(PlanBeforeLiveProtocolError, match="CELL_FALLBACK_ENABLED"):
        validate_dev_select_execution_plan_dict(tampered)


def test_adv17_repair_1_fails_closed(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """Adversarial 17: repair=1 fails closed."""
    tampered = copy.deepcopy(verified_plan_freeze_state["plan"])
    tampered["cells"][0]["repair"] = 1
    with pytest.raises(PlanBeforeLiveProtocolError, match="CELL_REPAIR_NONZERO"):
        validate_dev_select_execution_plan_dict(tampered)


def test_adv18_tools_true_fails_closed(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """Adversarial 18: tools=true fails closed."""
    tampered = copy.deepcopy(verified_plan_freeze_state["plan"])
    tampered["cells"][0]["tools"] = True
    with pytest.raises(PlanBeforeLiveProtocolError, match="CELL_TOOLS_ENABLED"):
        validate_dev_select_execution_plan_dict(tampered)


def test_adv19_attempt_number_2_fails_closed(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """Adversarial 19: attempt_number=2 fails closed."""
    tampered = copy.deepcopy(verified_plan_freeze_state["plan"])
    tampered["cells"][0]["attempt_number"] = 2
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="CELL_ATTEMPT_NUMBER_MISMATCH"
    ):
        validate_dev_select_execution_plan_dict(tampered)


def test_adv20_final100_scenario_id_fails_closed(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """Adversarial 20: Final100 scenario ID fails closed."""
    tampered = copy.deepcopy(verified_plan_freeze_state["plan"])
    tampered["cells"][0]["fixture_id"] = "W06-S001"
    with pytest.raises(
        Final100FirewallViolationError, match="FINAL100_FIREWALL_VIOLATION"
    ):
        validate_dev_select_execution_plan_dict(tampered)


def test_adv21_final100_used_flag_true_fails_closed(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """Adversarial 21: Final100-used flag true fails closed."""
    tampered_rec = copy.deepcopy(verified_plan_freeze_state["receipt"])
    tampered_rec["final100_used"] = True
    with pytest.raises(PlanBeforeLiveProtocolError, match="RECEIPT_FINAL100_USED_TRUE"):
        validate_plan_freeze_receipt_dict(
            tampered_rec,
            expected_plan_internal_sha256=EXPECTED_DEV_SELECT_PLAN_INTERNAL_SHA256,
            expected_plan_file_sha256=EXPECTED_DEV_SELECT_PLAN_FILE_SHA256,
        )


def test_adv22_fake_selection_receipt_filename_with_wrong_hash_fails_closed(
    tmp_path: Path,
) -> None:
    """Adversarial 22: fake selection receipt filename with wrong hash fails closed."""
    fake_rec = tmp_path / "w06_dev_tune_prompt_selection_01_receipt_v1.json"
    fake_rec.write_text('{"selected_prompt_id": "P1"}\n', encoding="utf-8")
    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="PROMPT_SELECTION_RECEIPT_FILE_SHA_MISMATCH",
    ):
        verify_upstream_prompt_selection_gate(
            REPO_ROOT, selection_receipt_path=fake_rec
        )


def test_adv23_plan_file_tampered_after_creation_fails_closed(
    verified_plan_freeze_state: dict[str, Any],
    tmp_path: Path,
) -> None:
    """Adversarial 23: plan file tampered after creation fails closed."""
    tampered_plan = copy.deepcopy(verified_plan_freeze_state["plan"])
    tampered_plan["plan_sha256"] = "0" * 64
    tampered_path = tmp_path / "w06_dev_select_execution_plan_v1.json"
    tampered_path.write_bytes(canonical_json_bytes(tampered_plan))
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="PERSISTED_PLAN_FILE_SHA_MISMATCH"
    ):
        verify_persisted_dev_select_plan_and_receipt(
            REPO_ROOT, plan_path=tampered_path
        )


def test_adv24_receipt_plan_sha_tampered_fails_closed(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """Adversarial 24: receipt plan SHA tampered fails closed."""
    tampered_rec = copy.deepcopy(verified_plan_freeze_state["receipt"])
    tampered_rec["dev_select_plan_internal_sha256"] = "d" * 64
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="RECEIPT_PLAN_INTERNAL_SHA_MISMATCH"
    ):
        validate_plan_freeze_receipt_dict(
            tampered_rec,
            expected_plan_internal_sha256=EXPECTED_DEV_SELECT_PLAN_INTERNAL_SHA256,
            expected_plan_file_sha256=EXPECTED_DEV_SELECT_PLAN_FILE_SHA256,
        )


def test_adv25_model_winner_selected_true_fails_closed(
    verified_plan_freeze_state: dict[str, Any],
) -> None:
    """Adversarial 25: model_winner_selected=true fails closed."""
    tampered_rec = copy.deepcopy(verified_plan_freeze_state["receipt"])
    tampered_rec["model_winner_selected"] = True
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="RECEIPT_MODEL_WINNER_SELECTED_TRUE"
    ):
        validate_plan_freeze_receipt_dict(
            tampered_rec,
            expected_plan_internal_sha256=EXPECTED_DEV_SELECT_PLAN_INTERNAL_SHA256,
            expected_plan_file_sha256=EXPECTED_DEV_SELECT_PLAN_FILE_SHA256,
        )


def test_adv26_outbound_network_kill_switch_blocks_all_transports() -> None:
    """Adversarial 26: network kill-switch test proving provider/network access is blocked across socket, urllib, httpx, and actual httpx2."""
    assert httpx2.__name__ == "httpx2"
    assert httpx2 is not httpx
    with NetworkKillSwitchGuard() as guard:
        with pytest.raises(OutboundNetworkBlockedError):
            socket.create_connection(("example.com", 443), timeout=0.1)
        with pytest.raises(OutboundNetworkBlockedError):
            urllib.request.urlopen("https://example.com", timeout=0.1)
        with pytest.raises(OutboundNetworkBlockedError):
            with httpx.Client() as client:
                client.get("https://example.com")
        with pytest.raises(OutboundNetworkBlockedError):
            httpx2.get("https://example.com")
        assert len(guard.blocked_attempts) == 4
        assert "httpx.Client.send" in guard.blocked_attempts
        assert "httpx2.Client.send" in guard.blocked_attempts
