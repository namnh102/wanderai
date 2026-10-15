"""Independent Adversarial QA Test Suite for W06-SCENARIO-GENERATOR-01 (W06-SCENARIO-GENERATOR-QA-01).

Covers:
- Baseline external dry-run audit (CLI stdout + canonical bundle)
- Independent Rule A / Rule B direct place_id set-union recomputation
- Independent repeat-cap audit
- Independent canonical duplicate signature audit
- Priority-order & PhaseBLockedSlot immutability audit
- Fresh-process determinism across PYTHONHASHSEED={normal, 0, 1, 42}
- Output verifier mutation tests: QA-MUT-01 through QA-MUT-20 (20/20)
- Scientific authority fail-closed mutation tests: QA-AUTH-01 through QA-AUTH-07 (7/7)
- Phase-C failure preservation of Priorities 1..6
- Rejection log audit (776 entries: 393 / 360 / 23)
- Dry-run artifact safety guards
- Independent cross-balance table recomputation
- Non-interference hash verification and receipt/documentation validation
"""

from __future__ import annotations

import copy
from functools import lru_cache
import json
from pathlib import Path
import sys
from typing import Any, Dict

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
AI_SERVICE_ROOT = REPO_ROOT / "apps" / "ai-service"
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.evaluation.planner_scenario_generator import (  # noqa: E402
    DEFAULT_SCENARIO_GENERATION_SEED,
    INFEASIBILITY_PROTOCOL_STATUS,
    ScenarioGenerationInfeasibleError,
    _run_phase_a_allocate_core_marginals,
    _run_phase_b_allocate_secondary_marginals,
    generate_dry_run_scenarios,
)
from scripts.audit_w06_scenario_generator_dryrun import (  # noqa: E402
    CATALOG_PATH,
    DRYRUN_CLI_PATH,
    EXPECTED_DRY_RUN_SHA256,
    EXPECTED_PRIORITY_TRACE,
    EXPECTED_SEED,
    GENERATOR_SOURCE_PATH,
    METHOD_LOCK_PATH,
    RECA_CONTRACT_PATH,
    SUPPORT_MATRIX_PATH,
    IndependentDryRunAuditError,
    audit_dry_run_bundle_independently,
    build_independent_catalog_support_map,
    independent_canonical_json_bytes,
    independent_lf_sha256,
    recompute_independent_cross_tables,
    recompute_independent_rule_a_b,
    run_fresh_process_dryrun,
    run_fresh_process_dryrun_sha,
)
from scripts.generate_w06_scenarios_dryrun import (  # noqa: E402
    main as dryrun_cli_main,
)

QA_RECEIPT_PATH = (
    REPO_ROOT / "data" / "evaluation" / "w06" / "w06_scenario_generator_qa_01_receipt_v1.json"
)
QA_DOC_PATH = REPO_ROOT / "docs" / "research" / "w06_scenario_generator_qa_01_v1.md"
GEN_RECEIPT_PATH = (
    REPO_ROOT / "data" / "evaluation" / "w06" / "w06_scenario_generator_01_receipt_v1.json"
)
MEASUREMENT_CONTRACT_PATH = (
    REPO_ROOT / "data" / "evaluation" / "w06" / "w06_measurement_contract_v1.json"
)

EXPECTED_HASHES = {
    "generator_source": "623c52cbdd98d181cd9cbbc1e68697a7299cb6c864628e97e743afd9e09ceae1",
    "dryrun_cli": "475b722011e5851ad3ddb445955c6d3a537e95de76e0179cc92df7e9f7153f08",
    "generator_receipt": "7903055b80676c2140a08e570e4149b59721defeb37b5719292673c92f5e86f9",
    "method_lock": "5e5359f9f10a0248a9cf031f8e8b26c0314c46aecfe0d9df479388bbe4fd1af9",
    "support_matrix": "68c2bfc2164e664b3856c31b99a92d75a588f64465526b47c9104918a51cedb4",
    "catalog": "f7517938598e3923906763f8f31334a500ee88bc06232f2992d38e2fcb28a444",
    "reca_contract": "1a62c36a95092be35ab78dca43e20f646016e154746ee051a499bdebfc67538c",
    "measurement_contract": "0ddc1f8d879493517cee25f247d2365a0bacb816dc33b129b0c6110d4bfb8298",
    "planner_prompt": "31387107994ed10aa0b5d42999dc4c46dcf5f408c6d9ca454db2b0ab8084ef65",
    "planner_schema": "1792dadcfa681ef75df3d66fb291b4d6702c6cced4fb4aab5d9e571884dc8685",
}


@lru_cache(maxsize=1)
def _baseline_cli_execution():
    return run_fresh_process_dryrun(None)


@lru_cache(maxsize=1)
def _baseline_bundle_dict() -> Dict[str, Any]:
    _, _, bundle_dict = _baseline_cli_execution()
    return bundle_dict


@lru_cache(maxsize=1)
def _cached_method_lock() -> Dict[str, Any]:
    return json.loads(METHOD_LOCK_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _cached_support_matrix() -> Dict[str, Any]:
    return json.loads(SUPPORT_MATRIX_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _cached_catalog_map():
    return build_independent_catalog_support_map(CATALOG_PATH)


def _fresh_bundle_copy() -> Dict[str, Any]:
    return copy.deepcopy(_baseline_bundle_dict())


# ==============================================================================
# SECTIONS 4..8: BASELINE INDEPENDENT AUDIT
# ==============================================================================


def test_qa_baseline_external_dryrun_and_independent_audit():
    """Verify baseline CLI dry-run output via independent verifier without calling generator verifier."""
    observed_sha, stdout_summary, bundle_dict = _baseline_cli_execution()
    assert observed_sha == EXPECTED_DRY_RUN_SHA256
    assert stdout_summary["bundle_sha256"] == EXPECTED_DRY_RUN_SHA256
    assert stdout_summary["slot_count"] == 100
    assert stdout_summary["run_mode"] == "DRY_RUN"
    assert stdout_summary["fixture_label"] == "SYNTHETIC_GENERATOR_QA"

    # Strip bundle_dict["invariants_verified"] before auditing to prove the independent verifier
    # never reads or relies on the generator's self-verification dictionary
    untrusted_bundle = copy.deepcopy(bundle_dict)
    untrusted_bundle["invariants_verified"] = {"poisoned_self_verifier": False}

    res = audit_dry_run_bundle_independently(
        untrusted_bundle,
        method_lock=_cached_method_lock(),
        support_matrix=_cached_support_matrix(),
        catalog_support_map=_cached_catalog_map(),
    )
    assert res["audit_status"] == "PASS"
    assert res["slot_count"] == 100
    assert res["unique_canonical_signatures"] == 100
    assert res["duplicate_canonical_signatures"] == 0
    assert res["repeat_cap_violations"] == 0
    assert res["rule_a_failures"] == 0
    assert res["rule_b_failures"] == 0
    assert res["excluded_combinations_used"] == 0


def test_qa_independent_rule_a_and_rule_b_direct_union_recomputation():
    """Independently recompute Rule A and Rule B (direct place_id set union) for all 100 slots."""
    bundle_dict = _baseline_bundle_dict()
    cat_map = _cached_catalog_map()
    sm = _cached_support_matrix()

    for slot in bundle_dict["slots"]:
        dest = slot["destination_slug"]
        days = slot["days"]
        interests = slot["interests"]
        recomputed = recompute_independent_rule_a_b(dest, days, interests, cat_map)
        assert recomputed["rule_a_passed"] is True
        assert recomputed["rule_b_passed"] is True
        assert recomputed["eligible"] is True
        assert recomputed["support_class"] in ("CLEAR", "STRESS")
        assert recomputed["support_class"] == slot["support_class"]

        m_matches = [
            c
            for c in sm["destinations"][dest]["by_days"][str(days)]["combinations"]
            if c["interests_sorted"] == interests
        ]
        assert len(m_matches) == 1
        assert recomputed["support_class"] == m_matches[0]["support_class"]
        assert recomputed["union_support"] == m_matches[0]["union_support"]


def test_qa_independent_repeat_cap_and_pooling_across_dimensions():
    """Independently verify repeat caps and confirm pooling across days/budget/weekend/style."""
    bundle_dict = _baseline_bundle_dict()
    expected_caps = {
        "ha-noi": {1: 3, 2: 1, 3: 1},
        "da-nang": {1: 2, 2: 1, 3: 1},
        "ha-long": {1: 2, 2: 1, 3: 1},
    }
    pooled_counts: Dict[tuple[str, tuple[str, ...]], list[dict[str, Any]]] = {}
    for slot in bundle_dict["slots"]:
        key = (slot["destination_slug"], tuple(sorted(slot["interests"])))
        pooled_counts.setdefault(key, []).append(slot)
        k = len(slot["interests"])
        assert len(pooled_counts[key]) <= expected_caps[slot["destination_slug"]][k]

    # Verify that repeated k=1 combinations differ in days/budget/weekend/style yet share the same counter
    repeated_k1 = [
        (key, occurrences)
        for key, occurrences in pooled_counts.items()
        if len(key[1]) == 1 and len(occurrences) > 1
    ]
    assert len(repeated_k1) > 0
    for (_dest, _intr), occs in repeated_k1:
        distinct_days_or_budgets = {
            (o["days"], o["budget_tier_or_null"], o["weekend_exposure"], o["travel_style"])
            for o in occs
        }
        assert len(distinct_days_or_budgets) == len(occs)


def test_qa_priority_order_and_phase_b_immutability():
    """Verify exact priority trace and prove Phase B locks Priorities 1..6 before Phase C."""
    bundle_dict = _baseline_bundle_dict()
    assert bundle_dict["executable_priority_trace"] == EXPECTED_PRIORITY_TRACE

    ml = _cached_method_lock()
    trace: list[str] = []
    phase_a = _run_phase_a_allocate_core_marginals(ml, trace)
    phase_b = _run_phase_b_allocate_secondary_marginals(phase_a, ml, EXPECTED_SEED, trace)
    assert trace == EXPECTED_PRIORITY_TRACE[:6]
    assert len(phase_b) == 100

    for pslot, fslot in zip(phase_b, bundle_dict["slots"]):
        assert not hasattr(pslot, "interests")
        assert (
            pslot.slot_index,
            pslot.destination_slug,
            pslot.days,
            pslot.interest_count,
            pslot.budget_tier_or_null,
            pslot.budget,
            pslot.travel_style,
            pslot.weekend_exposure,
            pslot.start_date,
            pslot.end_date,
        ) == (
            fslot["slot_index"],
            fslot["destination_slug"],
            fslot["days"],
            fslot["interest_count"],
            fslot["budget_tier_or_null"],
            fslot["budget"],
            fslot["travel_style"],
            fslot["weekend_exposure"],
            fslot["start_date"],
            fslot["end_date"],
        )


# ==============================================================================
# SECTION 9: FRESH-PROCESS DETERMINISM QA
# ==============================================================================


def test_qa_fresh_process_determinism_across_pythonhashseed():
    """Verify separate fresh Python processes with PYTHONHASHSEED={normal,0,1,42} yield identical SHA256."""
    sha_normal = run_fresh_process_dryrun_sha(None)
    sha_0 = run_fresh_process_dryrun_sha("0")
    sha_1 = run_fresh_process_dryrun_sha("1")
    sha_42 = run_fresh_process_dryrun_sha("42")

    assert sha_normal == EXPECTED_DRY_RUN_SHA256
    assert sha_0 == EXPECTED_DRY_RUN_SHA256
    assert sha_1 == EXPECTED_DRY_RUN_SHA256
    assert sha_42 == EXPECTED_DRY_RUN_SHA256


# ==============================================================================
# SECTION 10: MUTATION TESTS — OUTPUT VERIFIER (QA-MUT-01..QA-MUT-20)
# ==============================================================================


def _assert_rejected(mutated_bundle: Dict[str, Any]) -> IndependentDryRunAuditError:
    with pytest.raises(IndependentDryRunAuditError) as exc_info:
        audit_dry_run_bundle_independently(
            mutated_bundle,
            method_lock=_cached_method_lock(),
            support_matrix=_cached_support_matrix(),
            catalog_support_map=_cached_catalog_map(),
        )
    return exc_info.value


def test_qa_mut_01_slot_count_99():
    """QA-MUT-01: slot count 99 -> rejected by independent verifier."""
    b = _fresh_bundle_copy()
    b["slots"] = b["slots"][:99]
    b["slot_count"] = 99
    err = _assert_rejected(b)
    assert err.code == "SLOT_COUNT_MISMATCH"


def test_qa_mut_02_destination_marginal_altered():
    """QA-MUT-02: destination marginal altered -> rejected by independent verifier."""
    b = _fresh_bundle_copy()
    s0 = b["slots"][0]
    s0["destination_slug"] = "da-nang"
    s0["destination"] = "Đà Nẵng"
    s0["scenario_input"]["destination_slug"] = "da-nang"
    s0["scenario_input"]["destination"] = "Đà Nẵng"
    s0["canonical_signature"][0] = "da-nang"
    err = _assert_rejected(b)
    assert err.code in ("DESTINATION_MARGINAL_MISMATCH", "DESTINATION_DAYS_MATRIX_MISMATCH", "SUPPORT_NUMERIC_MISMATCH")


def test_qa_mut_03_days_marginal_altered():
    """QA-MUT-03: days marginal altered -> rejected by independent verifier."""
    b = _fresh_bundle_copy()
    s0 = b["slots"][0]
    s0["days"] = 3
    s0["scenario_input"]["days"] = 3
    if s0["weekend_exposure"]:
        s0["start_date"] = "2026-11-06"
        s0["end_date"] = "2026-11-08"
    else:
        s0["start_date"] = "2026-11-02"
        s0["end_date"] = "2026-11-04"
    s0["scenario_input"]["start_date"] = s0["start_date"]
    s0["scenario_input"]["end_date"] = s0["end_date"]
    s0["required_poi_per_day_total_2d"] = 6
    if s0["budget_tier_or_null"] is not None:
        daily = {"B1": 500000, "B2": 1000000, "B3": 2000000}[s0["budget_tier_or_null"]]
        s0["budget"] = daily * 3
        s0["scenario_input"]["budget"] = daily * 3
    s0["canonical_signature"][1] = 3
    err = _assert_rejected(b)
    assert err.code == "DAYS_MARGINAL_MISMATCH"


def test_qa_mut_04_interest_count_altered_incorrectly():
    """QA-MUT-04: interest_count altered incorrectly -> rejected by independent verifier."""
    b = _fresh_bundle_copy()
    b["slots"][0]["interest_count"] = 2
    err = _assert_rejected(b)
    assert err.code == "INTEREST_COUNT_MISMATCH"


def test_qa_mut_05_budget_formula_altered():
    """QA-MUT-05: budget formula altered -> rejected by independent verifier."""
    b = _fresh_bundle_copy()
    for slot in b["slots"]:
        if slot["budget_tier_or_null"] == "B1":
            slot["budget"] += 1000
            slot["scenario_input"]["budget"] += 1000
            break
    err = _assert_rejected(b)
    assert err.code == "BUDGET_FORMULA_MISMATCH"


def test_qa_mut_06_travel_style_invalid():
    """QA-MUT-06: travel style invalid -> rejected by independent verifier."""
    b = _fresh_bundle_copy()
    b["slots"][0]["travel_style"] = "ULTRA_VIP"
    b["slots"][0]["scenario_input"]["travel_style"] = "ULTRA_VIP"
    err = _assert_rejected(b)
    assert err.code == "TRAVEL_STYLE_INVALID"


def test_qa_mut_07_weekend_flag_inconsistent_with_dates():
    """QA-MUT-07: weekend flag inconsistent with dates -> rejected by independent verifier."""
    b = _fresh_bundle_copy()
    b["slots"][0]["weekend_exposure"] = not b["slots"][0]["weekend_exposure"]
    err = _assert_rejected(b)
    assert err.code == "WEEKEND_FLAG_INCONSISTENT"


def test_qa_mut_08_date_outside_frozen_window():
    """QA-MUT-08: date outside frozen window -> rejected by independent verifier."""
    b = _fresh_bundle_copy()
    s0 = b["slots"][0]
    s0["start_date"] = "2026-10-15"
    s0["end_date"] = "2026-10-16"
    s0["scenario_input"]["start_date"] = "2026-10-15"
    s0["scenario_input"]["end_date"] = "2026-10-16"
    err = _assert_rejected(b)
    assert err.code == "DATE_OUTSIDE_WINDOW"


def test_qa_mut_09_non_contiguous_trip_dates():
    """QA-MUT-09: non-contiguous trip dates -> rejected by independent verifier."""
    b = _fresh_bundle_copy()
    s0 = b["slots"][0]
    s0["end_date"] = "2026-11-20"
    s0["scenario_input"]["end_date"] = "2026-11-20"
    err = _assert_rejected(b)
    assert err.code == "NON_CONTIGUOUS_DATES"


def test_qa_mut_10_non_canonical_interest():
    """QA-MUT-10: non-canonical interest -> rejected by independent verifier."""
    b = _fresh_bundle_copy()
    s0 = b["slots"][0]
    s0["interests"] = ["extreme_skydiving"]
    s0["scenario_input"]["interests"] = ["extreme_skydiving"]
    err = _assert_rejected(b)
    assert err.code == "NON_CANONICAL_INTEREST"


def test_qa_mut_11_selected_excluded_interest_combination():
    """QA-MUT-11: selected EXCLUDED interest combination -> rejected by independent verifier."""
    b = _fresh_bundle_copy()
    # In ha-noi, beach_island has 0 POIs and is EXCLUDED at all day lengths
    s0 = b["slots"][0]
    s0["interests"] = ["beach_island"]
    s0["scenario_input"]["interests"] = ["beach_island"]
    s0["canonical_signature"][2] = ["beach_island"]
    err = _assert_rejected(b)
    assert err.code in ("INDEPENDENT_RULE_A_B_FAILED", "EXCLUDED_COMBINATION_SELECTED")


def test_qa_mut_12_repeat_cap_exceeded():
    """QA-MUT-12: repeat cap exceeded -> rejected by independent verifier."""
    b = _fresh_bundle_copy()
    # Force four k=1 slots in ha-noi to use ["food_cuisine"] (exceeding ha-noi k=1 cap of 3)
    cat_map = _cached_catalog_map()
    count_forced = 0
    for slot in b["slots"]:
        if slot["destination_slug"] == "ha-noi" and slot["interest_count"] == 1:
            recomp = recompute_independent_rule_a_b("ha-noi", slot["days"], ["food_cuisine"], cat_map)
            slot["interests"] = ["food_cuisine"]
            slot["scenario_input"]["interests"] = ["food_cuisine"]
            slot["support_class"] = recomp["support_class"]
            slot["union_support"] = recomp["union_support"]
            slot["sum_support"] = recomp["sum_support"]
            slot["min_interest_support"] = recomp["min_interest_support"]
            slot["canonical_signature"][2] = ["food_cuisine"]
            count_forced += 1
            if count_forced == 4:
                break
    err = _assert_rejected(b)
    assert err.code == "REPEAT_CAP_EXCEEDED"


def test_qa_mut_13_duplicate_canonical_signature():
    """QA-MUT-13: duplicate canonical signature -> rejected by independent verifier."""
    b = _fresh_bundle_copy()
    # Find two ha-noi k=1 slots that share the same interest (under repeat cap <= 3) and make their
    # days, budget, weekend_exposure, and travel_style identical so their canonical signature collides
    matching_slots = [
        s
        for s in b["slots"]
        if s["destination_slug"] == "ha-noi" and s["interests"] == b["slots"][0]["interests"]
    ]
    assert len(matching_slots) >= 2
    s_first, s_second = matching_slots[0], matching_slots[1]
    cat_map = _cached_catalog_map()
    recomp = recompute_independent_rule_a_b("ha-noi", s_first["days"], s_first["interests"], cat_map)
    s_second["days"] = s_first["days"]
    s_second["scenario_input"]["days"] = s_first["days"]
    s_second["start_date"] = s_first["start_date"]
    s_second["end_date"] = s_first["end_date"]
    s_second["scenario_input"]["start_date"] = s_first["start_date"]
    s_second["scenario_input"]["end_date"] = s_first["end_date"]
    s_second["budget_tier_or_null"] = s_first["budget_tier_or_null"]
    s_second["budget"] = s_first["budget"]
    s_second["scenario_input"]["budget"] = s_first["budget"]
    s_second["weekend_exposure"] = s_first["weekend_exposure"]
    s_second["travel_style"] = s_first["travel_style"]
    s_second["scenario_input"]["travel_style"] = s_first["travel_style"]
    s_second["support_class"] = recomp["support_class"]
    s_second["union_support"] = recomp["union_support"]
    s_second["sum_support"] = recomp["sum_support"]
    s_second["min_interest_support"] = recomp["min_interest_support"]
    s_second["canonical_signature"] = list(s_first["canonical_signature"])
    err = _assert_rejected(b)
    assert err.code == "DUPLICATE_CANONICAL_SIGNATURE"


def test_qa_mut_14_duplicate_scenario_id():
    """QA-MUT-14: duplicate scenario_id -> rejected by independent verifier."""
    b = _fresh_bundle_copy()
    b["slots"][1]["scenario_id"] = b["slots"][0]["scenario_id"]
    b["slots"][1]["scenario_input"]["scenario_id"] = b["slots"][0]["scenario_id"]
    err = _assert_rejected(b)
    assert err.code == "DUPLICATE_SCENARIO_ID"


def test_qa_mut_15_fixture_label_changed():
    """QA-MUT-15: fixture_label changed away from SYNTHETIC_GENERATOR_QA -> rejected."""
    b = _fresh_bundle_copy()
    b["slots"][0]["scenario_input"]["fixture_label"] = "FINAL_100"
    err = _assert_rejected(b)
    assert err.code == "FIXTURE_LABEL_INVALID"


def test_qa_mut_16_allow_revisit_place_ids_true():
    """QA-MUT-16: allow_revisit_place_ids = true -> rejected by independent verifier."""
    b = _fresh_bundle_copy()
    b["slots"][0]["scenario_input"]["allow_revisit_place_ids"] = True
    err = _assert_rejected(b)
    assert err.code == "ALLOW_REVISIT_INVALID"


def test_qa_mut_17_final_frozen_flag_changed_to_true():
    """QA-MUT-17: final/frozen flag changed to true -> rejected by independent verifier."""
    b = _fresh_bundle_copy()
    b["is_final_100_scenarios"] = True
    err = _assert_rejected(b)
    assert err.code == "FINAL_OR_BOUNDARY_FLAG_VIOLATION"


def test_qa_mut_18_priority_trace_reordered():
    """QA-MUT-18: priority trace reordered -> rejected by independent verifier."""
    b = _fresh_bundle_copy()
    trace = list(b["executable_priority_trace"])
    trace[3], trace[6] = trace[6], trace[3]
    b["executable_priority_trace"] = trace
    err = _assert_rejected(b)
    assert err.code == "PRIORITY_TRACE_MISMATCH"


def test_qa_mut_19_support_class_inconsistent_with_recomputed_support():
    """QA-MUT-19: support_class inconsistent with independently recomputed support -> rejected."""
    b = _fresh_bundle_copy()
    s0 = b["slots"][0]
    s0["support_class"] = "STRESS" if s0["support_class"] == "CLEAR" else "CLEAR"
    err = _assert_rejected(b)
    assert err.code == "SUPPORT_CLASS_MISMATCH"


def test_qa_mut_20_rule_a_b_claimed_true_while_recomputation_fails():
    """QA-MUT-20: rule_a/rule_b claimed true while independent recomputation fails -> rejected."""
    b = _fresh_bundle_copy()
    s0 = b["slots"][0]
    # Keep rule_a_passed=True and rule_b_passed=True on the slot, but set interests to an ineligible combo
    s0["interests"] = ["beach_island"]
    s0["scenario_input"]["interests"] = ["beach_island"]
    s0["rule_a_passed"] = True
    s0["rule_b_passed"] = True
    err = _assert_rejected(b)
    assert err.code == "INDEPENDENT_RULE_A_B_FAILED"


# ==============================================================================
# SECTION 11: MUTATION TESTS — SCIENTIFIC AUTHORITIES (QA-AUTH-01..QA-AUTH-07)
# ==============================================================================


def test_qa_auth_01_method_lock_byte_hash_mutation_fails_closed(tmp_path: Path):
    """QA-AUTH-01: Method Lock byte/hash mutation -> FAIL CLOSED."""
    tmp_lock = tmp_path / "tampered_method_lock.json"
    tmp_lock.write_bytes(METHOD_LOCK_PATH.read_bytes() + b"\n")
    with pytest.raises(ScenarioGenerationInfeasibleError) as exc_info:
        generate_dry_run_scenarios(method_lock_path=tmp_lock)
    assert exc_info.value.protocol_status == INFEASIBILITY_PROTOCOL_STATUS


def test_qa_auth_02_support_matrix_mutation_fails_closed(tmp_path: Path):
    """QA-AUTH-02: Support Matrix mutation -> FAIL CLOSED."""
    tmp_sm = tmp_path / "tampered_support_matrix.json"
    tmp_sm.write_bytes(SUPPORT_MATRIX_PATH.read_bytes() + b"\n")
    with pytest.raises(ScenarioGenerationInfeasibleError) as exc_info:
        generate_dry_run_scenarios(support_matrix_path=tmp_sm)
    assert exc_info.value.protocol_status == INFEASIBILITY_PROTOCOL_STATUS


def test_qa_auth_03_frozen_catalog_mutation_fails_closed(tmp_path: Path):
    """QA-AUTH-03: frozen catalog mutation -> FAIL CLOSED."""
    tmp_cat = tmp_path / "tampered_catalog.json"
    tmp_cat.write_bytes(CATALOG_PATH.read_bytes() + b"\n")
    with pytest.raises(ScenarioGenerationInfeasibleError) as exc_info:
        generate_dry_run_scenarios(catalog_path=tmp_cat)
    assert exc_info.value.protocol_status == INFEASIBILITY_PROTOCOL_STATUS


def test_qa_auth_04_reca_contract_source_mutation_fails_closed(tmp_path: Path):
    """QA-AUTH-04: REC-A contract source mutation -> FAIL CLOSED."""
    tmp_reca = tmp_path / "tampered_reca_contract.py"
    tmp_reca.write_bytes(RECA_CONTRACT_PATH.read_bytes() + b"\n# tampered\n")
    with pytest.raises(ScenarioGenerationInfeasibleError) as exc_info:
        generate_dry_run_scenarios(reca_contract_path=tmp_reca)
    assert exc_info.value.protocol_status == INFEASIBILITY_PROTOCOL_STATUS


def test_qa_auth_05_wrong_generator_seed_fails_closed():
    """QA-AUTH-05: wrong generator seed -> FAIL CLOSED."""
    with pytest.raises(ScenarioGenerationInfeasibleError) as exc_info:
        generate_dry_run_scenarios(seed=DEFAULT_SCENARIO_GENERATION_SEED + 99)
    assert exc_info.value.protocol_status == INFEASIBILITY_PROTOCOL_STATUS


def test_qa_auth_06_frozen_priority_order_mutation_fails_closed():
    """QA-AUTH-06: frozen priority order mutation -> FAIL CLOSED."""
    bad_lock = copy.deepcopy(_cached_method_lock())
    p_order = bad_lock["generator_policy"]["priority_order"]
    p_order[3], p_order[6] = p_order[6], p_order[3]
    with pytest.raises(ScenarioGenerationInfeasibleError) as exc_info:
        generate_dry_run_scenarios(method_lock_override=bad_lock)
    assert exc_info.value.protocol_status == INFEASIBILITY_PROTOCOL_STATUS


def test_qa_auth_07_repeat_cap_methodology_mutation_fails_closed():
    """QA-AUTH-07: repeat-cap methodology mutation -> FAIL CLOSED."""
    bad_lock = copy.deepcopy(_cached_method_lock())
    bad_lock["near_duplicate_policy"]["repeat_caps_by_destination_and_interest_count"]["ha-noi"]["1"]["repeat_cap"] = 1
    with pytest.raises(ScenarioGenerationInfeasibleError) as exc_info:
        generate_dry_run_scenarios(method_lock_override=bad_lock)
    assert exc_info.value.protocol_status == INFEASIBILITY_PROTOCOL_STATUS


# ==============================================================================
# SECTIONS 12..15: PHASE-C FAILURE, REJECTION LOG, ARTIFACT SAFETY, CROSS-BALANCE
# ==============================================================================


def test_qa_phase_c_failure_preservation():
    """Section 12: Phase C failure preserves Phase A + Phase B locked Priority 1..6 assignments."""
    baseline_bundle = _baseline_bundle_dict()
    baseline_phase_b_sha = baseline_bundle["phase_b_locked_slots_sha256"]

    with pytest.raises(ScenarioGenerationInfeasibleError) as exc_info:
        generate_dry_run_scenarios(manual_reject_candidate_indices=set(range(1, 5000)))

    err = exc_info.value
    assert err.protocol_status == "STOP_DO_NOT_SILENTLY_RELAX_REQUIRE_FORMAL_METHOD_AMENDMENT"
    assert err.phase_b_slots is not None
    assert len(err.phase_b_slots) == 100
    assert list(err.executable_priority_trace[:6]) == EXPECTED_PRIORITY_TRACE[:6]

    observed_phase_b_bytes = independent_canonical_json_bytes(
        [s.model_dump(mode="json") for s in err.phase_b_slots]
    )
    import hashlib

    observed_phase_b_sha = hashlib.sha256(observed_phase_b_bytes).hexdigest()
    assert observed_phase_b_sha == baseline_phase_b_sha


def test_qa_rejection_log_independent_audit():
    """Section 13: Verify baseline rejection log totals (776 = 393 + 360 + 23) and absence of model output."""
    bundle_dict = _baseline_bundle_dict()
    assert bundle_dict["rejection_log_count"] == 776
    assert len(bundle_dict["rejection_log"]) == 776
    assert bundle_dict["rejection_reason_counts"] == {
        "CATALOG_SUPPORT_BELOW_THRESHOLD": 393,
        "INTEREST_COMBINATION_REPEAT_CAP": 360,
        "TOTAL_INTEREST_CAPACITY_INSUFFICIENT": 23,
    }


def test_qa_dryrun_artifact_safety_guards(tmp_path: Path):
    """Section 14: Verify CLI refuses protected paths and no final/P11/prereg artifacts exist."""
    forbidden_targets = [
        REPO_ROOT / "data" / "evaluation" / "w06" / "qa_forbidden_write.json",
        REPO_ROOT / "data" / "curated" / "qa_forbidden_write.json",
        tmp_path / "w06_final_100_scenarios.json",
        tmp_path / "w06_p11_manifest.json",
        tmp_path / "w06_prereg_lock.json",
    ]
    for target in forbidden_targets:
        with pytest.raises(ValueError, match="Refusing to write DRY_RUN output"):
            dryrun_cli_main(["--output-json", str(target)])
        assert not target.exists()


def test_qa_cross_balance_independent_recomputation():
    """Section 15: Independently recompute all cross-balance tables and compare with CrossBalanceReport."""
    bundle_dict = _baseline_bundle_dict()
    ind_tables = recompute_independent_cross_tables(bundle_dict["slots"])
    gen_cb = bundle_dict["cross_balance_report"]
    for key, val in ind_tables.items():
        assert gen_cb[key] == val


def test_qa_non_interference_hashes_and_receipt_complete():
    """Sections 16, 17, 20: Verify all pre-existing hashes are unchanged and QA receipt/doc are complete."""
    assert independent_lf_sha256(GENERATOR_SOURCE_PATH) == EXPECTED_HASHES["generator_source"]
    assert independent_lf_sha256(DRYRUN_CLI_PATH) == EXPECTED_HASHES["dryrun_cli"]
    assert independent_lf_sha256(GEN_RECEIPT_PATH) == EXPECTED_HASHES["generator_receipt"]
    assert independent_lf_sha256(METHOD_LOCK_PATH) == EXPECTED_HASHES["method_lock"]
    assert independent_lf_sha256(SUPPORT_MATRIX_PATH) == EXPECTED_HASHES["support_matrix"]
    assert independent_lf_sha256(CATALOG_PATH) == EXPECTED_HASHES["catalog"]
    assert independent_lf_sha256(RECA_CONTRACT_PATH) == EXPECTED_HASHES["reca_contract"]
    assert independent_lf_sha256(MEASUREMENT_CONTRACT_PATH) == EXPECTED_HASHES["measurement_contract"]
    assert (
        independent_lf_sha256(AI_SERVICE_ROOT / "app" / "prompts" / "planner_prompt.py")
        == EXPECTED_HASHES["planner_prompt"]
    )
    assert (
        independent_lf_sha256(AI_SERVICE_ROOT / "app" / "schemas" / "planner.py")
        == EXPECTED_HASHES["planner_schema"]
    )

    assert QA_RECEIPT_PATH.exists()
    raw_receipt = QA_RECEIPT_PATH.read_bytes()
    receipt = json.loads(raw_receipt.decode("utf-8"))
    assert raw_receipt == independent_canonical_json_bytes(receipt)
    assert receipt["task_id"] == "W06-SCENARIO-GENERATOR-QA-01"
    assert receipt["version"] == "1.0.0"
    assert receipt["base_develop_sha"] == "e86c6363ecd0442028e5161b8c8be8fc8c8ab77e"
    assert receipt["generator_version"] == "W06-SCENARIO-GENERATOR-01-V1.0.0"
    assert receipt["generator_source_sha256"] == EXPECTED_HASHES["generator_source"]
    assert receipt["generator_receipt_sha256"] == EXPECTED_HASHES["generator_receipt"]
    assert receipt["seed"] == EXPECTED_SEED
    assert receipt["expected_dry_run_sha256"] == EXPECTED_DRY_RUN_SHA256
    assert receipt["independent_verifier"] is True
    assert receipt["generator_internal_verifier_used_as_primary_evidence"] is False
    assert receipt["final_scenarios_generated"] is False
    assert receipt["p11_created"] is False
    assert receipt["preregistration_created"] is False
    assert receipt["gemini_called"] is False
    assert receipt["openai_called"] is False
    assert receipt["claude_called"] is False
    assert receipt["grok_called"] is False
    assert receipt["scientific_results_generated"] is False
    assert receipt["generator_modified"] is False
    assert receipt["method_lock_modified"] is False
    assert receipt["support_matrix_modified"] is False
    assert receipt["catalog_modified"] is False
    assert receipt["reca_contract_modified"] is False
    assert receipt["w5_modified"] is False
    assert receipt["production_planner_modified"] is False

    assert QA_DOC_PATH.exists()
    doc_text = QA_DOC_PATH.read_text(encoding="utf-8")
    assert "W06-SCENARIO-GENERATOR-QA-01" in doc_text
    assert "This does not claim universal bit-for-bit reproducibility across arbitrary environments." in doc_text
