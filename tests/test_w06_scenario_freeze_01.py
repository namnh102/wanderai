"""Comprehensive pytest suite for W06-SCENARIO-FREEZE-01 (FRZ-01..FRZ-45).

Verifies the frozen W06 100-scenario bundle (`data/evaluation/w06/w06_scenarios_freeze_v1.json`),
the P11 frozen assignment manifest (`data/evaluation/w06/w06_p11_assignment_manifest_v1.json`),
the freeze receipt (`data/evaluation/w06/w06_scenario_freeze_01_receipt_v1.json`),
and strict non-interference across all pre-existing scientific authorities.
"""

from __future__ import annotations

from collections import Counter
import copy
import datetime
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from typing import Any, Dict, Tuple

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
AI_SERVICE_ROOT = REPO_ROOT / "apps" / "ai-service"
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.evaluation.planner_scenario_generator import (  # noqa: E402
    DEFAULT_SCENARIO_GENERATION_SEED,
    canonical_json_bytes,
    generate_dry_run_scenarios,
)
from app.schemas.planner_benchmark import (  # noqa: E402
    CANONICAL_BENCHMARK_INTERESTS,
    BenchmarkScenarioInput,
)
from scripts.audit_w06_scenario_generator_dryrun import (  # noqa: E402
    CATALOG_PATH,
    DRYRUN_CLI_PATH,
    EXPECTED_DRY_RUN_SHA256,
    GENERATOR_SOURCE_PATH,
    METHOD_LOCK_PATH,
    RECA_CONTRACT_PATH,
    SUPPORT_MATRIX_PATH,
    build_independent_catalog_support_map,
    independent_lf_sha256,
    recompute_independent_rule_a_b,
)
from scripts.freeze_w06_scenarios import (  # noqa: E402
    BENCHMARK_SCENARIO_INPUT_FIELDS,
    SEMANTIC_1_TO_1_INVARIANT_FIELDS,
    serialize_canonical_json_lf,
    sha256_canonical_json_lf,
    write_frozen_scenario_artifacts,
)
from scripts.verify_w06_scenario_freeze import (  # noqa: E402
    FORBIDDEN_P11_MODEL_KEYS,
    FORBIDDEN_SCENARIO_LEAKAGE_KEYS,
    FreezeVerificationError,
    P11_MANIFEST_PATH,
    SCENARIO_BUNDLE_PATH,
    verify_frozen_scenario_artifacts_independently,
)

FREEZE_RECEIPT_PATH = REPO_ROOT / "data" / "evaluation" / "w06" / "w06_scenario_freeze_01_receipt_v1.json"
FREEZE_DOC_PATH = REPO_ROOT / "docs" / "research" / "w06_scenario_freeze_01_v1.md"
QA_VERIFIER_PATH = REPO_ROOT / "scripts" / "audit_w06_scenario_generator_dryrun.py"
QA_RECEIPT_PATH = REPO_ROOT / "data" / "evaluation" / "w06" / "w06_scenario_generator_qa_01_receipt_v1.json"
GENERATOR_RECEIPT_PATH = REPO_ROOT / "data" / "evaluation" / "w06" / "w06_scenario_generator_01_receipt_v1.json"
MEASUREMENT_CONTRACT_PATH = REPO_ROOT / "data" / "evaluation" / "w06" / "w06_measurement_contract_v1.json"

EXPECTED_BUNDLE_SHA256 = "c03bc6dc300604ac395505d59b6413c1a47339b21408cfd637671e81d4b555a1"
EXPECTED_P11_SHA256 = "0aa9ae923d0e7f29df49735fa41e87530b1caf62418fcbec09a1eff81d83af62"

EXPECTED_AUTHORITY_HASHES: Dict[str, Tuple[Path, str]] = {
    "generator_source": (
        GENERATOR_SOURCE_PATH,
        "623c52cbdd98d181cd9cbbc1e68697a7299cb6c864628e97e743afd9e09ceae1",
    ),
    "dryrun_cli": (
        DRYRUN_CLI_PATH,
        "475b722011e5851ad3ddb445955c6d3a537e95de76e0179cc92df7e9f7153f08",
    ),
    "qa_verifier": (
        QA_VERIFIER_PATH,
        "2e5a218fc49d4af0052dffa49c14a8a7d5d9818847fd6d37f647422a9cadc6fc",
    ),
    "generator_receipt": (
        GENERATOR_RECEIPT_PATH,
        "7903055b80676c2140a08e570e4149b59721defeb37b5719292673c92f5e86f9",
    ),
    "qa_receipt": (
        QA_RECEIPT_PATH,
        "eb94c359276782e1e91dd669f34caa3f8ba430da7dcf8c4fbffb648a27313bf3",
    ),
    "method_lock": (
        METHOD_LOCK_PATH,
        "5e5359f9f10a0248a9cf031f8e8b26c0314c46aecfe0d9df479388bbe4fd1af9",
    ),
    "support_matrix": (
        SUPPORT_MATRIX_PATH,
        "68c2bfc2164e664b3856c31b99a92d75a588f64465526b47c9104918a51cedb4",
    ),
    "catalog": (
        CATALOG_PATH,
        "f7517938598e3923906763f8f31334a500ee88bc06232f2992d38e2fcb28a444",
    ),
    "reca_contract": (
        RECA_CONTRACT_PATH,
        "1a62c36a95092be35ab78dca43e20f646016e154746ee051a499bdebfc67538c",
    ),
    "measurement_contract": (
        MEASUREMENT_CONTRACT_PATH,
        "0ddc1f8d879493517cee25f247d2365a0bacb816dc33b129b0c6110d4bfb8298",
    ),
}


@pytest.fixture(scope="module")
def frozen_bundle() -> Dict[str, Any]:
    return json.loads(SCENARIO_BUNDLE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def p11_manifest() -> Dict[str, Any]:
    return json.loads(P11_MANIFEST_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def dry_run_dict() -> Dict[str, Any]:
    return generate_dry_run_scenarios(seed=DEFAULT_SCENARIO_GENERATION_SEED).model_dump(mode="json")


@pytest.fixture(scope="module")
def method_lock() -> Dict[str, Any]:
    return json.loads(METHOD_LOCK_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def support_matrix() -> Dict[str, Any]:
    return json.loads(SUPPORT_MATRIX_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def catalog_support_map() -> Dict[str, Dict[str, set[str]]]:
    return build_independent_catalog_support_map(CATALOG_PATH)


@pytest.fixture(scope="module")
def freeze_receipt() -> Dict[str, Any]:
    return json.loads(FREEZE_RECEIPT_PATH.read_text(encoding="utf-8"))


def test_frz_01_100_final_scenarios_exactly(frozen_bundle: Dict[str, Any]):
    """FRZ-01: 100 final scenarios exactly."""
    assert frozen_bundle["scenario_count"] == 100
    assert isinstance(frozen_bundle["scenarios"], list)
    assert len(frozen_bundle["scenarios"]) == 100


def test_frz_02_scenario_ids_exact_range(frozen_bundle: Dict[str, Any]):
    """FRZ-02: scenario IDs exactly W06-SCENARIO-001..100."""
    ids = [s["scenario_id"] for s in frozen_bundle["scenarios"]]
    expected = [f"W06-SCENARIO-{i:03d}" for i in range(1, 101)]
    assert ids == expected
    assert len(set(ids)) == 100


def test_frz_03_100_p11_assignments(p11_manifest: Dict[str, Any]):
    """FRZ-03: 100 P11 assignments."""
    assert p11_manifest["scenario_count"] == 100
    assert isinstance(p11_manifest["assignments"], list)
    assert len(p11_manifest["assignments"]) == 100


def test_frz_04_p11_assignment_and_slot_index_1_to_100(p11_manifest: Dict[str, Any]):
    """FRZ-04: P11 assignment_index/source_slot_index exactly 1..100."""
    for idx, row in enumerate(p11_manifest["assignments"], start=1):
        assert row["assignment_index"] == idx
        assert row["source_slot_index"] == idx
        assert row["source_dry_run_scenario_id"] == f"W06-DRYRUN-{idx:03d}"
        assert row["scenario_id"] == f"W06-SCENARIO-{idx:03d}"


def test_frz_05_all_final_objects_validate_benchmark_scenario_input(frozen_bundle: Dict[str, Any]):
    """FRZ-05: all final objects validate BenchmarkScenarioInput."""
    for scen in frozen_bundle["scenarios"]:
        model = BenchmarkScenarioInput.model_validate(scen)
        assert model.model_dump(mode="json") == scen


def test_frz_06_fixture_label_null_on_all_final_scenarios(frozen_bundle: Dict[str, Any]):
    """FRZ-06: fixture_label null on all final scenarios."""
    for scen in frozen_bundle["scenarios"]:
        assert "fixture_label" in scen
        assert scen["fixture_label"] is None


def test_frz_07_allow_revisit_false_on_all_final_scenarios(frozen_bundle: Dict[str, Any]):
    """FRZ-07: allow_revisit_place_ids is false on all final scenarios."""
    for scen in frozen_bundle["scenarios"]:
        assert scen["allow_revisit_place_ids"] is False


def test_frz_08_currency_vnd_on_all_final_scenarios(frozen_bundle: Dict[str, Any]):
    """FRZ-08: currency VND on all final scenarios."""
    for scen in frozen_bundle["scenarios"]:
        assert scen["currency"] == "VND"


def test_frz_09_dry_run_to_final_semantic_equality_except_id_and_fixture_label(
    frozen_bundle: Dict[str, Any], dry_run_dict: Dict[str, Any]
):
    """FRZ-09: dry-run -> final semantic equality except ID + fixture label."""
    slots = dry_run_dict["slots"]
    scenarios = frozen_bundle["scenarios"]
    assert len(slots) == len(scenarios) == 100
    for idx, (slot, scen) in enumerate(zip(slots, scenarios), start=1):
        src_in = slot["scenario_input"]
        assert src_in["scenario_id"] == f"W06-DRYRUN-{idx:03d}"
        assert scen["scenario_id"] == f"W06-SCENARIO-{idx:03d}"
        assert src_in["fixture_label"] == "SYNTHETIC_GENERATOR_QA"
        assert scen["fixture_label"] is None
        for field in SEMANTIC_1_TO_1_INVARIANT_FIELDS:
            assert scen[field] == src_in[field], f"Mismatch on slot {idx} field {field}"


def test_frz_10_destination_34_33_33(frozen_bundle: Dict[str, Any]):
    """FRZ-10: destination 34/33/33."""
    counts = Counter(s["destination_slug"] for s in frozen_bundle["scenarios"])
    assert dict(counts) == {"ha-noi": 34, "da-nang": 33, "ha-long": 33}


def test_frz_11_days_33_34_33(frozen_bundle: Dict[str, Any]):
    """FRZ-11: days 33/34/33."""
    counts = Counter(str(s["days"]) for s in frozen_bundle["scenarios"])
    assert dict(counts) == {"2": 33, "3": 34, "4": 33}


def test_frz_12_destination_by_days_exact(frozen_bundle: Dict[str, Any], method_lock: Dict[str, Any]):
    """FRZ-12: destination × days exact."""
    matrix = {d: {"2": 0, "3": 0, "4": 0} for d in ("ha-noi", "da-nang", "ha-long")}
    for s in frozen_bundle["scenarios"]:
        matrix[s["destination_slug"]][str(s["days"])] += 1
    assert matrix == method_lock["destination_days_cross_allocation"]


def test_frz_13_interest_count_33_34_33(frozen_bundle: Dict[str, Any]):
    """FRZ-13: interest count 33/34/33."""
    counts = Counter(str(len(s["interests"])) for s in frozen_bundle["scenarios"])
    assert dict(counts) == {"1": 33, "2": 34, "3": 33}


def test_frz_14_destination_by_interest_count_exact(frozen_bundle: Dict[str, Any], method_lock: Dict[str, Any]):
    """FRZ-14: destination × interest count exact."""
    matrix = {d: {"1": 0, "2": 0, "3": 0} for d in ("ha-noi", "da-nang", "ha-long")}
    for s in frozen_bundle["scenarios"]:
        matrix[s["destination_slug"]][str(len(s["interests"]))] += 1
    assert matrix == method_lock["destination_interest_count_cross_allocation"]


def test_frz_15_budget_27_27_26_null_20(p11_manifest: Dict[str, Any]):
    """FRZ-15: budget 27/27/26/null20."""
    counts = Counter(
        r["budget_tier_or_null"] if r["budget_tier_or_null"] is not None else "null"
        for r in p11_manifest["assignments"]
    )
    assert dict(counts) == {"B1": 27, "B2": 27, "B3": 26, "null": 20}


def test_frz_16_numeric_budget_formula_correct(
    frozen_bundle: Dict[str, Any], p11_manifest: Dict[str, Any], method_lock: Dict[str, Any]
):
    """FRZ-16: numeric budget formula correct."""
    daily_map = {
        "B1": method_lock["budget_policy"]["nominal_tiers"]["B1"]["daily_nominal_vnd"],
        "B2": method_lock["budget_policy"]["nominal_tiers"]["B2"]["daily_nominal_vnd"],
        "B3": method_lock["budget_policy"]["nominal_tiers"]["B3"]["daily_nominal_vnd"],
    }
    for scen, p11_row in zip(frozen_bundle["scenarios"], p11_manifest["assignments"]):
        tier = p11_row["budget_tier_or_null"]
        if tier is None:
            assert scen["budget"] is None
        else:
            assert scen["budget"] == daily_map[tier] * scen["days"]


def test_frz_17_travel_style_25_each(frozen_bundle: Dict[str, Any]):
    """FRZ-17: style 25 each."""
    counts = Counter(s["travel_style"] for s in frozen_bundle["scenarios"])
    assert dict(counts) == {"BACKPACKER": 25, "BUDGET": 25, "COMFORT": 25, "LUXURY": 25}


def test_frz_18_weekend_50_50(frozen_bundle: Dict[str, Any], p11_manifest: Dict[str, Any]):
    """FRZ-18: weekend 50/50."""
    wk_true = 0
    wk_false = 0
    for scen, p11_row in zip(frozen_bundle["scenarios"], p11_manifest["assignments"]):
        s_dt = datetime.date.fromisoformat(scen["start_date"])
        trip_dates = [s_dt + datetime.timedelta(days=offset) for offset in range(scen["days"])]
        has_wk = any(d.weekday() in (5, 6) for d in trip_dates)
        assert p11_row["weekend_exposure"] is has_wk
        if has_wk:
            wk_true += 1
        else:
            wk_false += 1
    assert wk_true == 50
    assert wk_false == 50


def test_frz_19_date_window_correct(frozen_bundle: Dict[str, Any], method_lock: Dict[str, Any]):
    """FRZ-19: date window correct (2026-11-02 .. 2026-12-13)."""
    win_start = datetime.date.fromisoformat(method_lock["date_policy"]["window_start_date"])
    win_end = datetime.date.fromisoformat(method_lock["date_policy"]["window_end_date"])
    assert str(win_start) == "2026-11-02"
    assert str(win_end) == "2026-12-13"
    for scen in frozen_bundle["scenarios"]:
        s_dt = datetime.date.fromisoformat(scen["start_date"])
        e_dt = datetime.date.fromisoformat(scen["end_date"])
        assert win_start <= s_dt <= e_dt <= win_end


def test_frz_20_trip_dates_contiguous(frozen_bundle: Dict[str, Any]):
    """FRZ-20: trip dates contiguous."""
    for scen in frozen_bundle["scenarios"]:
        s_dt = datetime.date.fromisoformat(scen["start_date"])
        e_dt = datetime.date.fromisoformat(scen["end_date"])
        assert (e_dt - s_dt).days + 1 == scen["days"]


def test_frz_21_canonical_interests_only(frozen_bundle: Dict[str, Any]):
    """FRZ-21: canonical interests only, sorted and distinct."""
    allowed = set(CANONICAL_BENCHMARK_INTERESTS)
    for scen in frozen_bundle["scenarios"]:
        interests = scen["interests"]
        assert 1 <= len(interests) <= 3
        assert len(set(interests)) == len(interests)
        assert interests == sorted(interests)
        assert set(interests).issubset(allowed)


def test_frz_22_rule_a_failures_zero(
    frozen_bundle: Dict[str, Any], catalog_support_map: Dict[str, Dict[str, set[str]]]
):
    """FRZ-22: Rule A failures 0."""
    failures = 0
    for scen in frozen_bundle["scenarios"]:
        res = recompute_independent_rule_a_b(
            scen["destination_slug"], scen["days"], scen["interests"], catalog_support_map
        )
        if not res["rule_a_passed"]:
            failures += 1
    assert failures == 0


def test_frz_23_rule_b_failures_zero_direct_union(
    frozen_bundle: Dict[str, Any], catalog_support_map: Dict[str, Dict[str, set[str]]]
):
    """FRZ-23: Rule B failures 0 direct union."""
    failures = 0
    for scen in frozen_bundle["scenarios"]:
        res = recompute_independent_rule_a_b(
            scen["destination_slug"], scen["days"], scen["interests"], catalog_support_map
        )
        if not res["rule_b_passed"]:
            failures += 1
    assert failures == 0


def test_frz_24_excluded_zero_and_support_classes_81_19_0(
    frozen_bundle: Dict[str, Any],
    p11_manifest: Dict[str, Any],
    catalog_support_map: Dict[str, Dict[str, set[str]]],
    support_matrix: Dict[str, Any],
):
    """FRZ-24: EXCLUDED 0 and support_class CLEAR=81, STRESS=19."""
    sc_counter: Counter[str] = Counter()
    for scen, p11_row in zip(frozen_bundle["scenarios"], p11_manifest["assignments"]):
        res = recompute_independent_rule_a_b(
            scen["destination_slug"], scen["days"], scen["interests"], catalog_support_map
        )
        assert res["eligible"] is True
        assert res["support_class"] in ("CLEAR", "STRESS")
        assert p11_row["support_class"] == res["support_class"]
        m_combs = [
            c
            for c in support_matrix["destinations"][scen["destination_slug"]]["by_days"][str(scen["days"])]["combinations"]
            if c["interests_sorted"] == scen["interests"]
        ]
        assert len(m_combs) == 1
        assert m_combs[0]["eligible"] is True
        assert m_combs[0]["support_class"] == res["support_class"]
        sc_counter[res["support_class"]] += 1
    assert sc_counter["EXCLUDED"] == 0
    assert sc_counter["CLEAR"] == 81
    assert sc_counter["STRESS"] == 19


def test_frz_25_repeat_cap_violations_zero(
    frozen_bundle: Dict[str, Any], method_lock: Dict[str, Any]
):
    """FRZ-25: repeat-cap violations 0."""
    repeat_caps = method_lock["near_duplicate_policy"]["repeat_caps_by_destination_and_interest_count"]
    counts: Counter[Tuple[str, Tuple[str, ...]]] = Counter()
    for scen in frozen_bundle["scenarios"]:
        dest = scen["destination_slug"]
        interests = tuple(scen["interests"])
        counts[(dest, interests)] += 1
        cap = int(repeat_caps[dest][str(len(interests))]["repeat_cap"])
        assert counts[(dest, interests)] <= cap


def test_frz_26_duplicate_signatures_zero(p11_manifest: Dict[str, Any]):
    """FRZ-26: duplicate signatures 0."""
    sigs = [
        (
            r["destination_slug"],
            r["days"],
            tuple(r["interests"]),
            r["budget_tier_or_null"],
            r["weekend_exposure"],
            r["travel_style"],
        )
        for r in p11_manifest["assignments"]
    ]
    assert len(sigs) == 100
    assert len(set(sigs)) == 100


def test_frz_27_per_scenario_hashes_all_verify(
    frozen_bundle: Dict[str, Any], p11_manifest: Dict[str, Any]
):
    """FRZ-27: per-scenario hashes all verify."""
    hashes = []
    for scen, p11_row in zip(frozen_bundle["scenarios"], p11_manifest["assignments"]):
        computed = sha256_canonical_json_lf(scen)
        assert p11_row["scenario_sha256"] == computed
        hashes.append(computed)
    assert len(hashes) == 100
    assert len(set(hashes)) == 100


def test_frz_28_scenario_bundle_sha_verifies(
    frozen_bundle: Dict[str, Any], p11_manifest: Dict[str, Any], freeze_receipt: Dict[str, Any]
):
    """FRZ-28: scenario bundle SHA verifies."""
    raw_bytes = SCENARIO_BUNDLE_PATH.read_bytes()
    assert raw_bytes == serialize_canonical_json_lf(frozen_bundle)
    sha = hashlib.sha256(raw_bytes).hexdigest()
    assert sha == EXPECTED_BUNDLE_SHA256
    assert p11_manifest["scenario_bundle_sha256"] == sha
    assert freeze_receipt["final_scenario_bundle_sha256"] == sha


def test_frz_29_p11_sha_deterministic(p11_manifest: Dict[str, Any], freeze_receipt: Dict[str, Any]):
    """FRZ-29: P11 SHA deterministic."""
    raw_bytes = P11_MANIFEST_PATH.read_bytes()
    assert raw_bytes == serialize_canonical_json_lf(p11_manifest)
    sha = hashlib.sha256(raw_bytes).hexdigest()
    assert sha == EXPECTED_P11_SHA256
    assert freeze_receipt["p11_sha256"] == sha


def test_frz_30_p11_metadata_agrees_with_final_scenarios():
    """FRZ-30: P11 metadata agrees with final scenarios (and verifier rejects tampered P11)."""
    report = verify_frozen_scenario_artifacts_independently(check_two_run_determinism=False)
    assert report["p11_assignment_validation"] == "PASS"

    bad_p11 = copy.deepcopy(json.loads(P11_MANIFEST_PATH.read_text(encoding="utf-8")))
    bad_p11["assignments"][0]["support_class"] = "STRESS" if bad_p11["assignments"][0]["support_class"] == "CLEAR" else "CLEAR"
    with pytest.raises(FreezeVerificationError) as exc_info:
        verify_frozen_scenario_artifacts_independently(
            p11_manifest_dict=bad_p11, check_two_run_determinism=False
        )
    assert exc_info.value.code == "P11_METADATA_SEMANTIC_MISMATCH"


def test_frz_31_source_dry_run_sha_exact(
    frozen_bundle: Dict[str, Any], p11_manifest: Dict[str, Any], freeze_receipt: Dict[str, Any]
):
    """FRZ-31: source dry-run SHA exact."""
    assert frozen_bundle["source_dry_run_sha256"] == EXPECTED_DRY_RUN_SHA256
    assert p11_manifest["source_dry_run_sha256"] == EXPECTED_DRY_RUN_SHA256
    assert freeze_receipt["source_dry_run_sha256"] == EXPECTED_DRY_RUN_SHA256
    dry_bundle = generate_dry_run_scenarios(seed=DEFAULT_SCENARIO_GENERATION_SEED)
    dry_sha = hashlib.sha256(canonical_json_bytes(dry_bundle.model_dump(mode="json"))).hexdigest()
    assert dry_sha == EXPECTED_DRY_RUN_SHA256


def test_frz_32_fresh_freeze_run_1_equals_run_2():
    """FRZ-32: fresh freeze run #1 == run #2."""
    with tempfile.TemporaryDirectory(prefix="frz32_1_") as d1, tempfile.TemporaryDirectory(
        prefix="frz32_2_"
    ) as d2:
        b1 = Path(d1) / "w06_scenarios_freeze_v1.json"
        p1 = Path(d1) / "w06_p11_assignment_manifest_v1.json"
        b2 = Path(d2) / "w06_scenarios_freeze_v1.json"
        p2 = Path(d2) / "w06_p11_assignment_manifest_v1.json"

        write_frozen_scenario_artifacts(scenario_bundle_path=b1, p11_path=p1)
        write_frozen_scenario_artifacts(scenario_bundle_path=b2, p11_path=p2)

        assert b1.read_bytes() == b2.read_bytes() == SCENARIO_BUNDLE_PATH.read_bytes()
        assert p1.read_bytes() == p2.read_bytes() == P11_MANIFEST_PATH.read_bytes()
        assert independent_lf_sha256(b1) == independent_lf_sha256(b2) == EXPECTED_BUNDLE_SHA256
        assert independent_lf_sha256(p1) == independent_lf_sha256(p2) == EXPECTED_P11_SHA256


def test_frz_33_method_lock_unchanged(freeze_receipt: Dict[str, Any]):
    """FRZ-33: Method Lock unchanged."""
    path, expected_sha = EXPECTED_AUTHORITY_HASHES["method_lock"]
    assert independent_lf_sha256(path) == expected_sha
    assert freeze_receipt["method_lock_modified"] is False
    assert freeze_receipt["authority_hashes"]["method_lock_sha256"] == expected_sha


def test_frz_34_support_matrix_unchanged(freeze_receipt: Dict[str, Any]):
    """FRZ-34: Support Matrix unchanged."""
    path, expected_sha = EXPECTED_AUTHORITY_HASHES["support_matrix"]
    assert independent_lf_sha256(path) == expected_sha
    assert freeze_receipt["support_matrix_modified"] is False
    assert freeze_receipt["authority_hashes"]["support_matrix_sha256"] == expected_sha


def test_frz_35_generator_unchanged(freeze_receipt: Dict[str, Any]):
    """FRZ-35: generator unchanged."""
    src_path, src_sha = EXPECTED_AUTHORITY_HASHES["generator_source"]
    cli_path, cli_sha = EXPECTED_AUTHORITY_HASHES["dryrun_cli"]
    rec_path, rec_sha = EXPECTED_AUTHORITY_HASHES["generator_receipt"]
    assert independent_lf_sha256(src_path) == src_sha
    assert independent_lf_sha256(cli_path) == cli_sha
    assert independent_lf_sha256(rec_path) == rec_sha
    assert freeze_receipt["generator_modified"] is False


def test_frz_36_qa_verifier_unchanged(freeze_receipt: Dict[str, Any]):
    """FRZ-36: QA verifier unchanged."""
    ver_path, ver_sha = EXPECTED_AUTHORITY_HASHES["qa_verifier"]
    qa_rec_path, qa_rec_sha = EXPECTED_AUTHORITY_HASHES["qa_receipt"]
    assert independent_lf_sha256(ver_path) == ver_sha
    assert independent_lf_sha256(qa_rec_path) == qa_rec_sha
    assert freeze_receipt["qa_verifier_modified"] is False


def test_frz_37_catalog_unchanged(freeze_receipt: Dict[str, Any]):
    """FRZ-37: catalog unchanged."""
    path, expected_sha = EXPECTED_AUTHORITY_HASHES["catalog"]
    assert independent_lf_sha256(path) == expected_sha
    assert freeze_receipt["catalog_modified"] is False


def test_frz_38_reca_contract_unchanged(freeze_receipt: Dict[str, Any]):
    """FRZ-38: REC-A contract unchanged."""
    path, expected_sha = EXPECTED_AUTHORITY_HASHES["reca_contract"]
    assert independent_lf_sha256(path) == expected_sha
    assert freeze_receipt["reca_contract_modified"] is False


def test_frz_39_measurement_contract_unchanged(freeze_receipt: Dict[str, Any]):
    """FRZ-39: Measurement Contract unchanged."""
    path, expected_sha = EXPECTED_AUTHORITY_HASHES["measurement_contract"]
    assert independent_lf_sha256(path) == expected_sha
    assert freeze_receipt["measurement_contract_modified"] is False


def test_frz_40_no_model_or_provider_called(
    p11_manifest: Dict[str, Any], freeze_receipt: Dict[str, Any]
):
    """FRZ-40: no model/provider called."""
    assert p11_manifest["model_output_used"] is False
    assert p11_manifest["created_before_model_selection"] is True
    assert freeze_receipt["model_selection_started"] is False
    assert freeze_receipt["gemini_called"] is False
    assert freeze_receipt["openai_called"] is False
    assert freeze_receipt["claude_called"] is False
    assert freeze_receipt["grok_called"] is False


def test_frz_41_no_preregistration(p11_manifest: Dict[str, Any], freeze_receipt: Dict[str, Any]):
    """FRZ-41: no W06 preregistration."""
    assert p11_manifest["created_before_preregistration"] is True
    assert freeze_receipt["preregistration_created"] is False
    w06_prereg_matches = list((REPO_ROOT / "docs" / "research").glob("*w06*prereg*")) + list(
        (REPO_ROOT / "data" / "evaluation" / "w06").glob("*prereg*")
    )
    assert w06_prereg_matches == []


def test_frz_42_no_scientific_benchmark_execution(
    p11_manifest: Dict[str, Any], freeze_receipt: Dict[str, Any]
):
    """FRZ-42: no scientific benchmark execution."""
    assert p11_manifest["created_before_final_execution"] is True
    assert freeze_receipt["benchmark_execution_started"] is False


def test_frz_43_no_scientific_performance_result(
    frozen_bundle: Dict[str, Any], freeze_receipt: Dict[str, Any]
):
    """FRZ-43: no scientific performance result."""
    assert freeze_receipt["scientific_performance_results_generated"] is False
    for forbidden_key in ("results", "scores", "itineraries", "metrics", "model_outputs"):
        assert forbidden_key not in frozen_bundle


def test_frz_44_p11_contains_no_provider_or_model_assignment(p11_manifest: Dict[str, Any]):
    """FRZ-44: P11 contains no provider/model assignment."""
    assert FORBIDDEN_P11_MODEL_KEYS.isdisjoint(p11_manifest.keys())
    for row in p11_manifest["assignments"]:
        assert FORBIDDEN_P11_MODEL_KEYS.isdisjoint(row.keys())

    bad_p11 = copy.deepcopy(p11_manifest)
    bad_p11["assignments"][0]["assigned_model"] = "gemini-2.5-flash"
    with pytest.raises(FreezeVerificationError) as exc_info:
        verify_frozen_scenario_artifacts_independently(
            p11_manifest_dict=bad_p11, check_two_run_determinism=False
        )
    assert exc_info.value.code == "P11_ROW_MODEL_LEAKAGE"


def test_frz_45_final_scenario_file_contains_no_qa_or_generator_metadata_leakage(
    frozen_bundle: Dict[str, Any], p11_manifest: Dict[str, Any]
):
    """FRZ-45: final scenario file contains no QA/generator metadata leakage."""
    for scen in frozen_bundle["scenarios"]:
        assert tuple(sorted(scen.keys())) == tuple(sorted(BENCHMARK_SCENARIO_INPUT_FIELDS))
        assert FORBIDDEN_SCENARIO_LEAKAGE_KEYS.isdisjoint(scen.keys())
        assert scen["fixture_label"] is None

    bad_bundle = copy.deepcopy(frozen_bundle)
    bad_bundle["scenarios"][0]["support_class"] = "CLEAR"
    bad_p11 = copy.deepcopy(p11_manifest)
    bad_p11["scenario_bundle_sha256"] = sha256_canonical_json_lf(bad_bundle)
    with pytest.raises(FreezeVerificationError) as exc_info:
        verify_frozen_scenario_artifacts_independently(
            scenario_bundle_dict=bad_bundle,
            p11_manifest_dict=bad_p11,
            check_two_run_determinism=False,
        )
    assert exc_info.value.code == "SCENARIO_METADATA_LEAKAGE"
    assert FREEZE_DOC_PATH.exists()
