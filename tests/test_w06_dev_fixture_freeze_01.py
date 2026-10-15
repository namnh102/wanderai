"""Test Suite for W06 DEV-Only Scenario Fixture Freeze (W06-DEV-FIXTURE-FREEZE-01).

Covers DEV-FRZ-01 through DEV-FRZ-40.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Dict

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
AI_SERVICE_ROOT = REPO_ROOT / "apps" / "ai-service"
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.evaluation.planner_dev_fixture_generator import (  # noqa: E402
    DEV_FIXTURE_GENERATION_SEED,
    DEV_SELECT_BALANCE_INFEASIBLE_STATUS,
    DEV_TUNE_ZERO_NEAR_OVERLAP_INFEASIBLE_STATUS,
    LOCKED_DEV_SELECT_MARGINALS,
    LOCKED_DEV_TUNE_MARGINALS,
    DevFixtureFreezeInfeasibleError,
    _allocate_partition_slots,
    _build_dev_tune_3d_grid,
    generate_dev_fixture_artifacts,
    write_frozen_dev_fixture_files,
)
from app.schemas.planner_benchmark import BenchmarkScenarioInput  # noqa: E402
from scripts.verify_w06_dev_fixture_freeze import (  # noqa: E402
    EXPECTED_AUTHORITY_HASHES,
    _canonical_json_lf_bytes,
    _lf_sha256,
    _sha256_bytes,
    verify_w06_dev_fixture_freeze_independently,
)

DEV_BUNDLE_PATH = REPO_ROOT / "data" / "evaluation" / "w06" / "w06_dev_fixtures_freeze_v1.json"
DEV_MANIFEST_PATH = REPO_ROOT / "data" / "evaluation" / "w06" / "w06_dev_fixture_manifest_v1.json"
OVERLAP_RECEIPT_PATH = (
    REPO_ROOT / "data" / "evaluation" / "w06" / "w06_dev_final_overlap_receipt_v1.json"
)
FREEZE_RECEIPT_PATH = (
    REPO_ROOT / "data" / "evaluation" / "w06" / "w06_dev_fixture_freeze_01_receipt_v1.json"
)


@pytest.fixture(scope="module")
def independent_report() -> Dict[str, Any]:
    return verify_w06_dev_fixture_freeze_independently(run_determinism_check=False)


@pytest.fixture(scope="module")
def bundle_data() -> Dict[str, Any]:
    return json.loads(DEV_BUNDLE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def manifest_data() -> Dict[str, Any]:
    return json.loads(DEV_MANIFEST_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def overlap_data() -> Dict[str, Any]:
    return json.loads(OVERLAP_RECEIPT_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def receipt_data() -> Dict[str, Any]:
    return json.loads(FREEZE_RECEIPT_PATH.read_text(encoding="utf-8"))


def test_dev_frz_01_total_80(bundle_data: Dict[str, Any], manifest_data: Dict[str, Any]) -> None:
    """DEV-FRZ-01: Total DEV fixture count is 80."""
    assert bundle_data["fixture_count"] == 80
    assert len(bundle_data["fixtures"]) == 80
    assert manifest_data["fixture_count"] == 80
    assert len(manifest_data["fixtures"]) == 80


def test_dev_frz_02_tune_20(bundle_data: Dict[str, Any], manifest_data: Dict[str, Any]) -> None:
    """DEV-FRZ-02: DEV-TUNE partition count is 20."""
    assert bundle_data["dev_tune_count"] == 20
    assert manifest_data["dev_tune_count"] == 20
    tune_bundle = [f for f in bundle_data["fixtures"] if f["fixture_label"] == "W06_DEV_TUNE"]
    tune_manifest = [m for m in manifest_data["fixtures"] if m["partition"] == "DEV_TUNE"]
    assert len(tune_bundle) == 20
    assert len(tune_manifest) == 20


def test_dev_frz_03_select_60(bundle_data: Dict[str, Any], manifest_data: Dict[str, Any]) -> None:
    """DEV-FRZ-03: DEV-SELECT partition count is 60."""
    assert bundle_data["dev_select_count"] == 60
    assert manifest_data["dev_select_count"] == 60
    select_bundle = [f for f in bundle_data["fixtures"] if f["fixture_label"] == "W06_DEV_SELECT"]
    select_manifest = [m for m in manifest_data["fixtures"] if m["partition"] == "DEV_SELECT"]
    assert len(select_bundle) == 60
    assert len(select_manifest) == 60


def test_dev_frz_04_tune_ids_exact(
    bundle_data: Dict[str, Any], manifest_data: Dict[str, Any]
) -> None:
    """DEV-FRZ-04: DEV-TUNE IDs match W06-DEV-TUNE-001..020 with no UUID or W06-SCENARIO-* IDs."""
    expected_ids = [f"W06-DEV-TUNE-{i:03d}" for i in range(1, 21)]
    bundle_ids = [f["scenario_id"] for f in bundle_data["fixtures"][:20]]
    manifest_ids = [m["scenario_id"] for m in manifest_data["fixtures"][:20]]
    assert bundle_ids == expected_ids
    assert manifest_ids == expected_ids
    for sid in bundle_ids:
        assert not sid.startswith("W06-SCENARIO-")


def test_dev_frz_05_select_ids_exact(
    bundle_data: Dict[str, Any], manifest_data: Dict[str, Any]
) -> None:
    """DEV-FRZ-05: DEV-SELECT IDs match W06-DEV-SELECT-001..060 with no UUID or W06-SCENARIO-* IDs."""
    expected_ids = [f"W06-DEV-SELECT-{i:03d}" for i in range(1, 61)]
    bundle_ids = [f["scenario_id"] for f in bundle_data["fixtures"][20:]]
    manifest_ids = [m["scenario_id"] for m in manifest_data["fixtures"][20:]]
    assert bundle_ids == expected_ids
    assert manifest_ids == expected_ids
    for sid in bundle_ids:
        assert not sid.startswith("W06-SCENARIO-")


def test_dev_frz_06_schema_valid(
    bundle_data: Dict[str, Any], independent_report: Dict[str, Any]
) -> None:
    """DEV-FRZ-06: All 80 fixtures validate against BenchmarkScenarioInput and pass independent audit."""
    assert independent_report["status"] == "PASS"
    assert independent_report["errors"] == []
    for idx, f_obj in enumerate(bundle_data["fixtures"], start=1):
        validated = BenchmarkScenarioInput.model_validate(f_obj)
        assert validated.model_dump(mode="json") == f_obj
        expected_label = "W06_DEV_TUNE" if idx <= 20 else "W06_DEV_SELECT"
        assert validated.fixture_label == expected_label
        assert validated.allow_revisit_place_ids is False
        assert validated.currency == "VND"


def test_dev_frz_07_tune_destination_7_7_6(independent_report: Dict[str, Any]) -> None:
    """DEV-FRZ-07: DEV-TUNE destination marginals are ha-noi=7, da-nang=7, ha-long=6."""
    assert independent_report["dev_tune_marginals"]["destination"] == {
        "ha-noi": 7,
        "da-nang": 7,
        "ha-long": 6,
    }


def test_dev_frz_08_tune_days_7_7_6(independent_report: Dict[str, Any]) -> None:
    """DEV-FRZ-08: DEV-TUNE days marginals are 2=7, 3=7, 4=6."""
    assert independent_report["dev_tune_marginals"]["days"] == {"2": 7, "3": 7, "4": 6}


def test_dev_frz_09_tune_interest_count_7_7_6(independent_report: Dict[str, Any]) -> None:
    """DEV-FRZ-09: DEV-TUNE interest_count marginals are 1=7, 2=7, 3=6."""
    assert independent_report["dev_tune_marginals"]["interest_count"] == {
        "1": 7,
        "2": 7,
        "3": 6,
    }


def test_dev_frz_10_tune_budget_5_each(independent_report: Dict[str, Any]) -> None:
    """DEV-FRZ-10: DEV-TUNE budget marginals are B1=5, B2=5, B3=5, null=5."""
    assert independent_report["dev_tune_marginals"]["budget"] == {
        "B1": 5,
        "B2": 5,
        "B3": 5,
        "null": 5,
    }


def test_dev_frz_11_tune_style_5_each(independent_report: Dict[str, Any]) -> None:
    """DEV-FRZ-11: DEV-TUNE travel_style marginals are 5 each."""
    assert independent_report["dev_tune_marginals"]["travel_style"] == {
        "BACKPACKER": 5,
        "BUDGET": 5,
        "COMFORT": 5,
        "LUXURY": 5,
    }


def test_dev_frz_12_tune_weekend_10_10(independent_report: Dict[str, Any]) -> None:
    """DEV-FRZ-12: DEV-TUNE weekend marginals are 10/10."""
    assert independent_report["dev_tune_marginals"]["weekend"] == {
        "weekend_exposed": 10,
        "non_weekend_exposed": 10,
    }


def test_dev_frz_13_select_destination_20_each(independent_report: Dict[str, Any]) -> None:
    """DEV-FRZ-13: DEV-SELECT destination marginals are 20 each."""
    assert independent_report["dev_select_marginals"]["destination"] == {
        "ha-noi": 20,
        "da-nang": 20,
        "ha-long": 20,
    }


def test_dev_frz_14_select_days_20_each(independent_report: Dict[str, Any]) -> None:
    """DEV-FRZ-14: DEV-SELECT days marginals are 20 each."""
    assert independent_report["dev_select_marginals"]["days"] == {
        "2": 20,
        "3": 20,
        "4": 20,
    }


def test_dev_frz_15_select_interest_count_20_each(independent_report: Dict[str, Any]) -> None:
    """DEV-FRZ-15: DEV-SELECT interest_count marginals are 20 each."""
    assert independent_report["dev_select_marginals"]["interest_count"] == {
        "1": 20,
        "2": 20,
        "3": 20,
    }


def test_dev_frz_16_select_budget_15_each(independent_report: Dict[str, Any]) -> None:
    """DEV-FRZ-16: DEV-SELECT budget marginals are 15 each."""
    assert independent_report["dev_select_marginals"]["budget"] == {
        "B1": 15,
        "B2": 15,
        "B3": 15,
        "null": 15,
    }


def test_dev_frz_17_select_style_15_each(independent_report: Dict[str, Any]) -> None:
    """DEV-FRZ-17: DEV-SELECT travel_style marginals are 15 each."""
    assert independent_report["dev_select_marginals"]["travel_style"] == {
        "BACKPACKER": 15,
        "BUDGET": 15,
        "COMFORT": 15,
        "LUXURY": 15,
    }


def test_dev_frz_18_select_weekend_30_30(independent_report: Dict[str, Any]) -> None:
    """DEV-FRZ-18: DEV-SELECT weekend marginals are 30/30."""
    assert independent_report["dev_select_marginals"]["weekend"] == {
        "weekend_exposed": 30,
        "non_weekend_exposed": 30,
    }


def test_dev_frz_19_rule_a_failures_0(independent_report: Dict[str, Any]) -> None:
    """DEV-FRZ-19: Independent Rule A failure count is 0."""
    assert independent_report["rule_a_failures"] == 0


def test_dev_frz_20_rule_b_failures_0(independent_report: Dict[str, Any]) -> None:
    """DEV-FRZ-20: Independent Rule B (direct place_id set union) failure count is 0."""
    assert independent_report["rule_b_failures"] == 0


def test_dev_frz_21_excluded_0(
    independent_report: Dict[str, Any], manifest_data: Dict[str, Any]
) -> None:
    """DEV-FRZ-21: EXCLUDED combination count is 0 and CLEAR/STRESS are both represented."""
    assert independent_report["excluded_count"] == 0
    sc_set = {m["support_class"] for m in manifest_data["fixtures"]}
    assert "EXCLUDED" not in sc_set
    assert sc_set == {"CLEAR", "STRESS"}


def test_dev_frz_22_all_dev_exact_signatures_unique(
    independent_report: Dict[str, Any], manifest_data: Dict[str, Any]
) -> None:
    """DEV-FRZ-22: All 80 DEV exact signatures are unique across DEV-TUNE and DEV-SELECT."""
    assert independent_report["dev_duplicate_exact_signatures"] == 0
    sigs = [
        (
            m["destination_slug"],
            m["days"],
            tuple(m["sorted_interests"]),
            m["budget_tier_or_null"],
            m["weekend_exposure"],
            m["travel_style"],
        )
        for m in manifest_data["fixtures"]
    ]
    assert len(sigs) == 80
    assert len(set(sigs)) == 80


def test_dev_frz_23_final_exact_overlap_0(
    independent_report: Dict[str, Any], overlap_data: Dict[str, Any]
) -> None:
    """DEV-FRZ-23: Exact overlap with final 100 is 0."""
    assert independent_report["final_exact_overlap_count"] == 0
    assert overlap_data["all_dev_exact_overlap_with_final"] == 0


def test_dev_frz_24_tune_near_overlap_0_and_fail_closed(
    independent_report: Dict[str, Any], overlap_data: Dict[str, Any]
) -> None:
    """DEV-FRZ-24: DEV-TUNE near-overlap with final 100 is 0, and generator fails closed if infeasible."""
    assert independent_report["dev_tune_near_overlap_count"] == 0
    assert overlap_data["dev_tune_near_overlap_with_final"] == 0

    # Verify fail-closed status DEV_TUNE_ZERO_NEAR_OVERLAP_INFEASIBLE when all combinations are near-overlapped
    dummy_combs = {
        (dest, d, k): [
            {
                "combination_id": "dummy",
                "interests_sorted": ["food_cuisine"][:k],
                "interest_count": k,
                "eligible": True,
                "support_class": "CLEAR",
                "rule_a_passed": True,
                "rule_b_passed": True,
                "union_support": 20,
                "sum_support": 20,
                "min_interest_support": 10,
            }
        ]
        for dest in ("ha-noi", "da-nang", "ha-long")
        for d in (2, 3, 4)
        for k in (1, 2, 3)
    }
    saturated_near_keys = {
        (dest, d, ("food_cuisine",) * k if False else tuple(["food_cuisine"][:k]), b)
        for dest in ("ha-noi", "da-nang", "ha-long")
        for d in (2, 3, 4)
        for k in (1, 2, 3)
        for b in ("B1", "B2", "B3", None)
    }
    with pytest.raises(DevFixtureFreezeInfeasibleError) as exc_info:
        _allocate_partition_slots(
            partition_name="DEV_TUNE",
            id_prefix="W06-DEV-TUNE",
            fixture_label="W06_DEV_TUNE",
            target_count=20,
            locked_marginals=LOCKED_DEV_TUNE_MARGINALS,
            grid_3d=_build_dev_tune_3d_grid(),
            global_index_offset=0,
            seed=DEV_FIXTURE_GENERATION_SEED,
            window_start_str="2026-11-02",
            window_end_str="2026-12-13",
            cell_ordered_combs=dummy_combs,
            final_exact_signatures=set(),
            final_near_overlap_keys=saturated_near_keys,
            require_zero_near_overlap=True,
            seen_dev_exact_signatures=set(),
            global_combo_reuse_counts=Counter(),
        )
    assert exc_info.value.status == DEV_TUNE_ZERO_NEAR_OVERLAP_INFEASIBLE_STATUS

    # Also verify wrong seed fails closed with STOP_REQUIRE_FORMAL_METHOD_AMENDMENT
    with pytest.raises(DevFixtureFreezeInfeasibleError) as seed_exc:
        generate_dev_fixture_artifacts(seed=99999999)
    assert seed_exc.value.status == DEV_SELECT_BALANCE_INFEASIBLE_STATUS


def test_dev_frz_25_select_near_overlap_accurately_reported(
    independent_report: Dict[str, Any],
    overlap_data: Dict[str, Any],
    receipt_data: Dict[str, Any],
) -> None:
    """DEV-FRZ-25: DEV-SELECT near-overlap count and rate are accurately reported."""
    cnt = independent_report["dev_select_near_overlap_count"]
    rate = independent_report["dev_select_near_overlap_rate"]
    assert cnt == 10
    assert rate == round(cnt / 60, 6)
    assert overlap_data["dev_select_near_overlap_with_final"] == cnt
    assert overlap_data["dev_select_near_overlap_rate"] == rate
    assert receipt_data["verification_summary"]["dev_select_final_near_overlap_count"] == cnt
    assert receipt_data["verification_summary"]["dev_select_final_near_overlap_rate"] == rate


def test_dev_frz_26_no_final_semantic_dump(
    overlap_data: Dict[str, Any], receipt_data: Dict[str, Any]
) -> None:
    """DEV-FRZ-26: No final-100 scenario semantics or scenario IDs are dumped to receipts or CLI stdout."""
    assert overlap_data["final_semantics_printed_to_operator_logs"] is False
    assert receipt_data["final_semantics_printed_to_operator_logs"] is False

    overlap_raw_str = OVERLAP_RECEIPT_PATH.read_text(encoding="utf-8")
    receipt_raw_str = FREEZE_RECEIPT_PATH.read_text(encoding="utf-8")
    for i in range(1, 101):
        scen_id = f"W06-SCENARIO-{i:03d}"
        assert scen_id not in overlap_raw_str
        assert scen_id not in receipt_raw_str

    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "verify_w06_dev_fixture_freeze.py")],
        capture_output=True,
        text=True,
        check=True,
    )
    for i in range(1, 101):
        assert f"W06-SCENARIO-{i:03d}" not in proc.stdout


def test_dev_frz_27_bundle_hashes_verify(
    bundle_data: Dict[str, Any],
    manifest_data: Dict[str, Any],
    overlap_data: Dict[str, Any],
    receipt_data: Dict[str, Any],
) -> None:
    """DEV-FRZ-27: DEV bundle canonical UTF-8 LF bytes and SHA256 verify across all artifacts."""
    raw = DEV_BUNDLE_PATH.read_bytes()
    assert b"\r" not in raw
    assert raw == _canonical_json_lf_bytes(bundle_data)
    bundle_sha = _sha256_bytes(raw)
    assert manifest_data["dev_bundle_sha256"] == bundle_sha
    assert overlap_data["dev_bundle_sha256"] == bundle_sha
    assert receipt_data["generated_artifacts"]["dev_bundle_sha256"] == bundle_sha


def test_dev_frz_28_manifest_hashes_verify(
    bundle_data: Dict[str, Any],
    manifest_data: Dict[str, Any],
    overlap_data: Dict[str, Any],
    receipt_data: Dict[str, Any],
) -> None:
    """DEV-FRZ-28: DEV manifest canonical UTF-8 LF bytes, SHA256, and per-fixture hashes verify."""
    raw = DEV_MANIFEST_PATH.read_bytes()
    assert b"\r" not in raw
    assert raw == _canonical_json_lf_bytes(manifest_data)
    manifest_sha = _sha256_bytes(raw)
    assert overlap_data["dev_manifest_sha256"] == manifest_sha
    assert receipt_data["generated_artifacts"]["dev_manifest_sha256"] == manifest_sha

    for f_obj, m_obj in zip(bundle_data["fixtures"], manifest_data["fixtures"]):
        assert m_obj["scenario_sha256"] == _sha256_bytes(_canonical_json_lf_bytes(f_obj))


def test_dev_frz_29_two_independent_freeze_runs_identical() -> None:
    """DEV-FRZ-29: Two independent freeze runs in separate temporary directories are byte-identical."""
    with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
        r1 = write_frozen_dev_fixture_files(output_dir=Path(tmp1))
        r2 = write_frozen_dev_fixture_files(output_dir=Path(tmp2))
        for key, disk_path in (
            ("bundle_path", DEV_BUNDLE_PATH),
            ("manifest_path", DEV_MANIFEST_PATH),
            ("overlap_path", OVERLAP_RECEIPT_PATH),
            ("receipt_path", FREEZE_RECEIPT_PATH),
        ):
            b1 = Path(r1[key]).read_bytes()
            b2 = Path(r2[key]).read_bytes()
            b_disk = disk_path.read_bytes()
            assert b1 == b2 == b_disk


def test_dev_frz_30_method_locks_unchanged() -> None:
    """DEV-FRZ-30: Both W06 Method Lock files are byte-identical to frozen baselines."""
    for rel in (
        "data/evaluation/w06/w06_model_arch_selection_method_lock_v1.json",
        "data/evaluation/w06/w06_scenario_method_lock_v1.json",
    ):
        assert _lf_sha256(REPO_ROOT / rel) == EXPECTED_AUTHORITY_HASHES[rel]


def test_dev_frz_31_final_bundle_unchanged() -> None:
    """DEV-FRZ-31: Final 100 scenario bundle is byte-identical."""
    rel = "data/evaluation/w06/w06_scenarios_freeze_v1.json"
    assert _lf_sha256(REPO_ROOT / rel) == EXPECTED_AUTHORITY_HASHES[rel]


def test_dev_frz_32_p11_unchanged() -> None:
    """DEV-FRZ-32: P11 assignment manifest is byte-identical."""
    rel = "data/evaluation/w06/w06_p11_assignment_manifest_v1.json"
    assert _lf_sha256(REPO_ROOT / rel) == EXPECTED_AUTHORITY_HASHES[rel]


def test_dev_frz_33_generator_unchanged() -> None:
    """DEV-FRZ-33: Authoritative final scenario generator and QA dry-run auditor are byte-identical."""
    for rel in (
        "apps/ai-service/app/evaluation/planner_scenario_generator.py",
        "scripts/audit_w06_scenario_generator_dryrun.py",
    ):
        assert _lf_sha256(REPO_ROOT / rel) == EXPECTED_AUTHORITY_HASHES[rel]


def test_dev_frz_34_support_matrix_unchanged() -> None:
    """DEV-FRZ-34: Support Matrix is byte-identical."""
    rel = "data/evaluation/w06/w06_scenario_support_matrix_v1.json"
    assert _lf_sha256(REPO_ROOT / rel) == EXPECTED_AUTHORITY_HASHES[rel]


def test_dev_frz_35_measurement_contract_unchanged() -> None:
    """DEV-FRZ-35: Measurement Contract is byte-identical."""
    rel = "data/evaluation/w06/w06_measurement_contract_v1.json"
    assert _lf_sha256(REPO_ROOT / rel) == EXPECTED_AUTHORITY_HASHES[rel]


def test_dev_frz_36_catalog_unchanged() -> None:
    """DEV-FRZ-36: Frozen catalog is byte-identical."""
    rel = "data/curated/gomate_places_freeze_v2.json"
    assert _lf_sha256(REPO_ROOT / rel) == EXPECTED_AUTHORITY_HASHES[rel]


def test_dev_frz_37_reca_mapping_unchanged() -> None:
    """DEV-FRZ-37: REC-A mapping contract is byte-identical."""
    rel = "apps/ai-service/recommendation/reca/contract.py"
    assert _lf_sha256(REPO_ROOT / rel) == EXPECTED_AUTHORITY_HASHES[rel]


def test_dev_frz_38_no_provider_calls(receipt_data: Dict[str, Any]) -> None:
    """DEV-FRZ-38: Zero provider calls were made."""
    assert receipt_data["provider_calls"] == 0
    assert receipt_data["gemini_called"] is False
    assert receipt_data["openai_called"] is False
    assert receipt_data["claude_called"] is False
    assert receipt_data["grok_called"] is False


def test_dev_frz_39_winning_model_not_selected(
    bundle_data: Dict[str, Any],
    manifest_data: Dict[str, Any],
    receipt_data: Dict[str, Any],
) -> None:
    """DEV-FRZ-39: Winning model is not selected and no model/provider assignment exists in DEV bundle/manifest."""
    assert receipt_data["winning_model_selected"] is False
    assert receipt_data["dev_model_outputs_generated"] is False
    for obj in (bundle_data, manifest_data):
        assert "winning_model" not in obj
        assert "selected_model" not in obj
        for row in obj["fixtures"]:
            assert "model" not in row
            assert "provider" not in row


def test_dev_frz_40_no_preregistration_or_final_execution(
    receipt_data: Dict[str, Any],
) -> None:
    """DEV-FRZ-40: No preregistration or final benchmark execution occurred."""
    assert receipt_data["preregistration_created"] is False
    assert receipt_data["final_benchmark_executed"] is False
    w06_dir = REPO_ROOT / "data" / "evaluation" / "w06"
    for p in w06_dir.iterdir():
        name_lower = p.name.lower()
        assert "prereg" not in name_lower
        assert "final_100" not in name_lower
