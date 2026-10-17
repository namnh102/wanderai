"""Independent adversarial QA test suite for W06 DEV Selection Harness (W06-DEV-SELECTION-HARNESS-QA-01-OFFLINE-ADVERSARIAL).

Tests all 40 adversarial checks (QA-01 through QA-40), independently verifying
passing harness invariants and asserting the exact root-cause reproducers for
the 10 scientific defects (5 CRITICAL, 5 MAJOR) uncovered in
`apps/ai-service/app/evaluation/dev_selection_harness.py`.

Zero live provider calls. Provider cost = $0.
"""

from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path
import tempfile

import pytest

from app.evaluation import dev_selection_harness as harness
from app.evaluation.planner_benchmark_evaluator import load_core_catalog_by_place_id
from app.prompts.planner_benchmark_prompt import build_destination_catalog_context
from scripts.audit_w06_dev_selection_harness import (
    EXPECTED_BASE_DEVELOP_SHA,
    FORBIDDEN_FINAL100_PATH,
    FORBIDDEN_P11_PATH,
    QA_RECEIPT_OUTPUT_PATH,
    build_failure_taxonomy_mapping_table,
    build_provider_billing_semantics_audit,
    build_valid_complete_plan_dict_for_scenario,
    derive_independent_dev_oracle,
    derive_independent_reca_oracle,
    run_all_qa_checks,
    sha256_lf_file,
)


@pytest.fixture(scope="module")
def qa_report():
    """Execute the full 40-check independent QA oracle once per test module."""
    return run_all_qa_checks()


@pytest.fixture(scope="module")
def qa_checks_by_id(qa_report):
    """Map check_id (QA-01..QA-40) to its check dictionary."""
    return {c["check_id"]: c for c in qa_report["checks"]}


def test_qa_receipt_file_exists_and_matches_oracle(qa_report):
    """Verify the generated JSON receipt exists and matches the live oracle."""
    assert QA_RECEIPT_OUTPUT_PATH.exists(), f"Missing {QA_RECEIPT_OUTPUT_PATH}"
    receipt_on_disk = json.loads(QA_RECEIPT_OUTPUT_PATH.read_text(encoding="utf-8"))
    assert receipt_on_disk["task_id"] == "W06-DEV-SELECTION-HARNESS-QA-01-OFFLINE-ADVERSARIAL"
    assert receipt_on_disk["base_develop_sha"] == EXPECTED_BASE_DEVELOP_SHA
    assert receipt_on_disk["live_provider_calls"] == 0
    assert receipt_on_disk["provider_cost_usd"] == 0
    assert receipt_on_disk["dev_tune_execution_started"] is False
    assert receipt_on_disk["dev_select_execution_started"] is False
    assert receipt_on_disk["winner_selected"] is False
    assert receipt_on_disk["final100_used"] is False
    assert receipt_on_disk["qa_checks_total"] == 40
    assert receipt_on_disk["qa_pass"] == 30
    assert receipt_on_disk["qa_fail"] == 10
    assert receipt_on_disk["critical_failures"] == [
        "QA-14",
        "QA-15",
        "QA-27",
        "QA-28",
        "QA-29",
    ]
    assert receipt_on_disk["major_failures"] == [
        "QA-05",
        "QA-30",
        "QA-32",
        "QA-33",
        "QA-39",
    ]
    assert receipt_on_disk["overall_qa"] == "FAIL"
    assert receipt_on_disk["next_status"] == "NEEDS_FIX"
    assert receipt_on_disk["next_gate"] == "W06-DEV-SELECTION-HARNESS-FIX-01"
    assert receipt_on_disk["domain_rollup"] == qa_report["domain_rollup"]


def test_qa_01_through_03_dev_bundle_and_marginals(qa_checks_by_id):
    """Verify QA-01, QA-02, QA-03: source state, DEV bundle SHA256, and exact marginals."""
    assert qa_checks_by_id["QA-01"]["status"] == "PASS"
    assert qa_checks_by_id["QA-02"]["status"] == "PASS"
    assert qa_checks_by_id["QA-03"]["status"] == "PASS"

    oracle = derive_independent_dev_oracle()
    assert (
        oracle["bundle_sha256"]
        == "bb0f051446ea3da8229298f22f4ce92b4db20751695273c6d01b7766da044050"
    )
    assert oracle["dev_total"] == 80
    assert oracle["dev_tune_count"] == 20
    assert oracle["dev_select_count"] == 60
    assert oracle["exact_final_overlap_count"] == 0
    assert oracle["dev_tune_near_overlap_final_count"] == 0


def test_qa_04_and_05_final100_firewall_direct_and_alias_defect(qa_checks_by_id):
    """Verify QA-04 passes on direct paths while QA-05 exposes copied-file and label mismatch gaps."""
    assert qa_checks_by_id["QA-04"]["status"] == "PASS"
    assert qa_checks_by_id["QA-05"]["status"] == "FAIL"
    assert qa_checks_by_id["QA-05"]["severity"] == "MAJOR"

    with pytest.raises(harness.Final100FirewallViolationError):
        harness.assert_not_final100_path(FORBIDDEN_FINAL100_PATH)
    with pytest.raises(harness.Final100FirewallViolationError):
        harness.assert_not_final100_path(FORBIDDEN_P11_PATH)

    # Reproducer for QA-05 defect: copied final100 under a different filename bypasses assert_not_final100_path
    with tempfile.TemporaryDirectory() as tmpdir:
        copied = Path(tmpdir) / "copied_bundle.json"
        copied.write_bytes(FORBIDDEN_FINAL100_PATH.read_bytes())
        assert sha256_lf_file(copied) == sha256_lf_file(FORBIDDEN_FINAL100_PATH)
        # Does not raise Final100FirewallViolationError in assert_not_final100_path:
        harness.assert_not_final100_path(copied)
        # Nor does cross-partition scenario_id vs fixture_label raise in assert_not_final100_scenario:
        harness.assert_not_final100_scenario(
            {"scenario_id": "W06-DEV-TUNE-001", "fixture_label": "W06_DEV_SELECT"}
        )


def test_qa_06_07_08_reca_catalog_integrity(qa_checks_by_id):
    """Verify QA-06, QA-07, QA-08: exact 622 REC-A catalog, DN 289 (not 293), and 0 secondary leakage."""
    assert qa_checks_by_id["QA-06"]["status"] == "PASS"
    assert qa_checks_by_id["QA-07"]["status"] == "PASS"
    assert qa_checks_by_id["QA-08"]["status"] == "PASS"

    reca_oracle = derive_independent_reca_oracle()
    assert reca_oracle["counts_by_destination"] == {
        "ha-noi": 145,
        "da-nang": 289,
        "ha-long": 188,
    }
    assert reca_oracle["total_reca_core"] == 622
    assert reca_oracle["map_discovery_counts"]["da-nang"] == 293
    assert len(reca_oracle["danang_lodging_only_ids"]) == 4


def test_qa_09_10_11_12_provider_serialization_and_configs(qa_checks_by_id):
    """Verify QA-09 through QA-12: semantic input equality across C1/C2/C3 and frozen provider configs."""
    for cid in ("QA-09", "QA-10", "QA-11", "QA-12"):
        assert qa_checks_by_id[cid]["status"] == "PASS"


def test_qa_13_and_14_strict_parser_and_semantic_rescue_defect(qa_checks_by_id):
    """Verify QA-13 passes on malformed JSON/fences while QA-14 exposes PRIMARY_SEMANTIC_RESCUE_DETECTED."""
    assert qa_checks_by_id["QA-13"]["status"] == "PASS"
    assert qa_checks_by_id["QA-14"]["status"] == "FAIL"
    assert qa_checks_by_id["QA-14"]["severity"] == "CRITICAL"
    assert (
        qa_checks_by_id["QA-14"]["evidence"]["failure_code"]
        == "PRIMARY_SEMANTIC_RESCUE_DETECTED"
    )

    bundle = harness.load_and_verify_frozen_dev_bundle()
    scen0 = bundle.dev_tune_fixtures[0]
    cat0 = build_destination_catalog_context(scen0.destination_slug)
    core_map = load_core_catalog_by_place_id()
    p1_reg = harness.build_default_infrastructure_prompt_registry()
    cell0 = harness.build_dev_tune_execution_plan(p1_reg).cells[0]

    # Omit required plan_id and budget_analysis -> harness rescues via parse_strict_benchmark_plan_response
    rescued_payload = build_valid_complete_plan_dict_for_scenario(scen0, cat0)
    del rescued_payload["plan_id"]
    del rescued_payload["budget_analysis"]
    with tempfile.TemporaryDirectory() as tmpdir:
        receipt, _ = harness.execute_dev_cell_with_mock_transport(
            cell_manifest=cell0,
            scenario=scen0,
            cell_dir=Path(tmpdir) / "rescue_repro",
            mock_response=harness.MockProviderTransportResponse(
                returned_model_id=cell0.requested_model_id,
                raw_text=json.dumps(rescued_payload, ensure_ascii=False),
                latency_ms=100.0,
                input_tokens=500,
                output_tokens=600,
                total_tokens=1100,
                authoritative_usage_available=True,
            ),
            core_catalog_by_id=core_map,
        )
        assert receipt.valid_run_and_schema is True


def test_qa_15_model_id_mismatch_fails_to_stop_batch(qa_checks_by_id):
    """Verify QA-15 exposes MODEL_ID_MISMATCH_FAILS_TO_STOP_BATCH."""
    assert qa_checks_by_id["QA-15"]["status"] == "FAIL"
    assert qa_checks_by_id["QA-15"]["severity"] == "CRITICAL"
    assert (
        qa_checks_by_id["QA-15"]["evidence"]["failure_code"]
        == "MODEL_ID_MISMATCH_FAILS_TO_STOP_BATCH"
    )


def test_qa_16_17_18_denominator_preservation_and_fail_closed(qa_checks_by_id):
    """Verify QA-16, QA-17, QA-18: denominator preservation and missing/duplicate receipt rejection."""
    assert qa_checks_by_id["QA-16"]["status"] == "PASS"
    assert qa_checks_by_id["QA-17"]["status"] == "PASS"
    assert qa_checks_by_id["QA-18"]["status"] == "PASS"


def test_qa_19_20_21_22_evaluator_metric_mapping(qa_checks_by_id):
    """Verify QA-19 through QA-22: grounding, core pass, opening-hours, and min 2 POI/day."""
    for cid in ("QA-19", "QA-20", "QA-21", "QA-22"):
        assert qa_checks_by_id[cid]["status"] == "PASS"


def test_qa_23_24_25_26_ten_pp_and_cost_comparability(qa_checks_by_id):
    """Verify QA-23 through QA-26: non-pairwise 10pp rule, exact boundary, early stop, and cost comparability."""
    for cid in ("QA-23", "QA-24", "QA-25", "QA-26"):
        assert qa_checks_by_id[cid]["status"] == "PASS"


def test_qa_27_and_28_provider_billing_semantics_and_double_counting(qa_checks_by_id):
    """Verify QA-27 and QA-28 expose C1 missing thought_tokens and C2/C3 reasoning/thinking double counting."""
    assert qa_checks_by_id["QA-27"]["status"] == "FAIL"
    assert qa_checks_by_id["QA-27"]["severity"] == "CRITICAL"
    assert qa_checks_by_id["QA-28"]["status"] == "FAIL"
    assert qa_checks_by_id["QA-28"]["severity"] == "CRITICAL"

    billing = build_provider_billing_semantics_audit()
    assert set(billing["candidates"].keys()) == {"C1", "C2", "C3"}
    assert billing["live_generation_api_calls"] == 0


def test_qa_29_and_30_unrounded_cost_and_latency_tiebreak_defects(qa_checks_by_id):
    """Verify QA-29 (CRITICAL) and QA-30 (MAJOR) expose 12-decimal rounding defects in _to_exact_decimal."""
    assert qa_checks_by_id["QA-29"]["status"] == "FAIL"
    assert qa_checks_by_id["QA-29"]["severity"] == "CRITICAL"
    assert (
        qa_checks_by_id["QA-29"]["evidence"]["failure_code"]
        == "COST_TIEBREAK_NOT_UNROUNDED"
    )

    assert qa_checks_by_id["QA-30"]["status"] == "FAIL"
    assert qa_checks_by_id["QA-30"]["severity"] == "MAJOR"
    assert (
        qa_checks_by_id["QA-30"]["evidence"]["failure_code"]
        == "LATENCY_TIEBREAK_ROUNDING"
    )

    # Direct unit proof of _to_exact_decimal truncation/rounding at 12 decimal places
    assert harness._to_exact_decimal(0.0100000000001) == Decimal("0.010000000000")
    assert harness._to_exact_decimal(0.0100000000002) == Decimal("0.010000000000")
    assert harness._to_exact_decimal(1.0000000000001) == Decimal("1.000000000000")
    assert harness._to_exact_decimal(1.0000000000002) == Decimal("1.000000000000")


def test_qa_31_and_32_prompt_registry_and_freeze_gate_defect(qa_checks_by_id):
    """Verify QA-31 passes on P1/P2 registry while QA-32 exposes missing prompt freeze gate and status mismatch."""
    assert qa_checks_by_id["QA-31"]["status"] == "PASS"
    assert qa_checks_by_id["QA-32"]["status"] == "FAIL"
    assert qa_checks_by_id["QA-32"]["severity"] == "MAJOR"


def test_qa_33_34_35_36_provenance_immutability_reproducibility_budgets(qa_checks_by_id):
    """Verify QA-33 fails on missing code_commit_sha while QA-34, QA-35, QA-36 pass."""
    assert qa_checks_by_id["QA-33"]["status"] == "FAIL"
    assert qa_checks_by_id["QA-33"]["severity"] == "MAJOR"
    assert qa_checks_by_id["QA-34"]["status"] == "PASS"
    assert qa_checks_by_id["QA-35"]["status"] == "PASS"
    assert qa_checks_by_id["QA-36"]["status"] == "PASS"


def test_qa_37_38_39_40_stochasticity_taxonomy_and_no_live_evidence(qa_checks_by_id):
    """Verify QA-37, QA-38, QA-40 pass and QA-39 exposes unmapped failure taxonomy outcomes."""
    assert qa_checks_by_id["QA-37"]["status"] == "PASS"
    assert qa_checks_by_id["QA-38"]["status"] == "PASS"
    assert qa_checks_by_id["QA-39"]["status"] == "FAIL"
    assert qa_checks_by_id["QA-39"]["severity"] == "MAJOR"
    assert qa_checks_by_id["QA-40"]["status"] == "PASS"

    taxonomy_table = build_failure_taxonomy_mapping_table()
    assert len(taxonomy_table) == 10
    invalid = [row["method_lock_outcome"] for row in taxonomy_table if not row["mapping_valid"]]
    assert invalid == [
        "PARTIAL_TIMEOUT_WHERE_DISTINGUISHABLE",
        "SCHEMA_NONCOMPLIANCE",
        "MODEL_ID_OR_RESOLVED_VERSION_MISMATCH",
        "HARNESS_OR_INFRASTRUCTURE_ERROR",
    ]
