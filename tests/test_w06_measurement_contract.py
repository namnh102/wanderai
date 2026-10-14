"""Verification tests for W06-MEASUREMENT-CONTRACT-01 (Freeze Scientific Measurement Semantics Before W06 Implementation)."""
import json
import subprocess
from collections import Counter
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRACT_JSON_PATH = REPO_ROOT / "data" / "evaluation" / "w06" / "w06_measurement_contract_v1.json"
CONTRACT_MD_PATH = REPO_ROOT / "docs" / "research" / "w06_measurement_contract_v1.md"
CLARIFICATION_MD_PATH = REPO_ROOT / "docs" / "research" / "w06_roadmap_methodology_clarification_v1.md"
AUDIT_JSON_PATH = REPO_ROOT / "data" / "evaluation" / "w06" / "w06_measurement_capability_audit_v1.json"
FREEZE_V2_PATH = REPO_ROOT / "data" / "curated" / "gomate_places_freeze_v2.json"
PLANNER_EVAL_DIR = REPO_ROOT / "data" / "evaluation" / "planner"
ROADMAP_PATH = REPO_ROOT / "docs" / "roadmap" / "gomate-thesis-research-roadmap-v1.md"

EXPECTED_BASE_DEVELOP_SHA = "495ed4f731db723366a585617472795540e8a914"


def _ensure_commit_present(commit_sha: str) -> None:
    res = subprocess.run(
        ["git", "cat-file", "-e", f"{commit_sha}^{{commit}}"],
        cwd=REPO_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if res.returncode != 0:
        subprocess.run(
            ["git", "fetch", "origin", commit_sha, "--depth=1"],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )


@pytest.fixture(scope="module")
def contract_doc() -> dict:
    assert CONTRACT_JSON_PATH.exists(), f"Missing contract JSON: {CONTRACT_JSON_PATH}"
    assert CONTRACT_MD_PATH.exists(), f"Missing contract MD: {CONTRACT_MD_PATH}"
    assert CLARIFICATION_MD_PATH.exists(), f"Missing roadmap clarification MD: {CLARIFICATION_MD_PATH}"
    return json.loads(CONTRACT_JSON_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def freeze_v2_places() -> list[dict]:
    return json.loads(FREEZE_V2_PATH.read_text(encoding="utf-8"))


def test_w06_contract_01_base_sha_exact(contract_doc: dict):
    """W06-CONTRACT-01: contract base SHA exact."""
    assert contract_doc["contract_id"] == "W06-MEASUREMENT-CONTRACT-01"
    assert contract_doc["contract_version"] == "1.0.0"
    assert contract_doc["base_develop_sha"] == EXPECTED_BASE_DEVELOP_SHA
    assert contract_doc["status"] == "DRAFT_FOR_SCIENTIFIC_GATE"
    assert EXPECTED_BASE_DEVELOP_SHA in CONTRACT_MD_PATH.read_text(encoding="utf-8")
    assert EXPECTED_BASE_DEVELOP_SHA in CLARIFICATION_MD_PATH.read_text(encoding="utf-8")


def test_w06_contract_02_benchmark_target_exactly_100(contract_doc: dict):
    """W06-CONTRACT-02: benchmark target exactly 100."""
    assert contract_doc["benchmark_target_scenarios"] == 100
    assert contract_doc["benchmark_population"]["roadmap_requirement_scenarios"] == 100


def test_w06_contract_03_allocation_exactly_34_33_33_equals_100(contract_doc: dict):
    """W06-CONTRACT-03: allocation exactly 34 + 33 + 33 = 100."""
    alloc = contract_doc["primary_destination_allocation"]
    assert alloc == {"ha-noi": 34, "da-nang": 33, "ha-long": 33}
    assert sum(alloc.values()) == 100
    pop_alloc = contract_doc["benchmark_population"]["primary_destination_allocation"]
    assert pop_alloc["ha-noi"] == 34
    assert pop_alloc["da-nang"] == 33
    assert pop_alloc["ha-long"] == 33
    assert pop_alloc["total"] == 100


def test_w06_contract_04_only_primary_rec_a_core_v2_destinations_allowed(
    contract_doc: dict, freeze_v2_places: list[dict]
):
    """W06-CONTRACT-04: only ha-noi / da-nang / ha-long are primary grounded destinations."""
    assert contract_doc["primary_destinations"] == ["ha-noi", "da-nang", "ha-long"]
    pop = contract_doc["benchmark_population"]
    assert pop["primary_catalog_scope"] == "REC-A-CORE-V2"
    assert pop["only_rec_a_core_v2_destinations_allowed_in_primary_benchmark"] is True

    core_places = [p for p in freeze_v2_places if p.get("is_rec_a_core_v2") is True]
    core_by_slug = Counter(p["destination_slug"] for p in core_places)
    counts = pop["primary_catalog_poi_counts"]
    assert counts["ha-noi"] == core_by_slug["ha-noi"] == 145
    assert counts["da-nang"] == core_by_slug["da-nang"] == 289
    assert counts["ha-long"] == core_by_slug["ha-long"] == 188
    assert counts["total"] == len(core_places) == 622


def test_w06_contract_05_ha_giang_and_moc_chau_not_primary(contract_doc: dict):
    """W06-CONTRACT-05: Ha Giang / Moc Chau not primary."""
    disp = contract_doc["benchmark_population"]["existing_repository_scenarios_disposition"]
    for sc_id in ("eval_ha_giang_3d", "eval_moc_chau_3d"):
        assert disp[sc_id]["classification"] == "LEGACY_OUT_OF_CATALOG_DIAGNOSTIC"
        assert disp[sc_id]["allowed_in_primary_100_benchmark"] is False

    dn_disp = disp["eval_da_nang_4d"]
    assert dn_disp["automatically_counted_in_final_100"] is False


def test_w06_contract_06_grounding_target_exactly_100_percent(contract_doc: dict):
    """W06-CONTRACT-06: grounding target exactly 100%."""
    cg = contract_doc["primary_hard_measurement_dimensions"]["CATALOG_GROUNDING"]
    assert cg["roadmap_scientific_target"] == 1.0
    assert cg["roadmap_scientific_target_percentage"] == 100.0
    gate = contract_doc["hard_roadmap_grounding_gate"]
    assert gate["gate_name"] == "GROUNDING_GATE"
    assert gate["required_grounded_poi_rate"] == 1.0
    assert gate["fail_if_below_1_0"] is True


def test_w06_contract_07_place_id_required_for_grounding(contract_doc: dict):
    """W06-CONTRACT-07: place_id required for grounding."""
    cg = contract_doc["primary_hard_measurement_dimensions"]["CATALOG_GROUNDING"]
    assert cg["requires_canonical_place_id"] is True
    assert cg["free_text_place_name_matching_sufficient"] is False
    assert cg["scenario_level_metric"]["name"] == "ALL_POIS_GROUNDED"

    dest = contract_doc["primary_hard_measurement_dimensions"]["DESTINATION_CORRECTNESS"]
    assert dest["name_string_inference_allowed"] is False

    dup = contract_doc["primary_hard_measurement_dimensions"]["DUPLICATE_POI"]
    assert dup["operates_on"] == "canonical_place_id"
    assert dup["free_text_alias_equality_sufficient"] is False


def test_w06_contract_08_budget_named_estimated_budget_compliance_and_no_price_accuracy_claim(
    contract_doc: dict,
):
    """W06-CONTRACT-08: budget named ESTIMATED_BUDGET_COMPLIANCE and does not claim real-world price accuracy."""
    budget = contract_doc["budget_semantics"]
    assert budget["dimension_id"] == "ESTIMATED_BUDGET_COMPLIANCE"
    assert budget["metric"] == "estimated_budget_violation_rate"
    assert budget["claims_real_world_price_accuracy"] is False
    assert budget["claims_catalog_price_grounding"] is False
    assert "REAL_WORLD_BUDGET_ACCURACY" in budget["forbidden_claims"]
    assert "PRICE_GROUNDING" in budget["forbidden_claims"]
    assert budget["audit_price_evidence"]["structured_numeric_poi_price_coverage"] == "0 / 759"
    assert budget["separate_engineering_check"]["check_id"] == "ARITHMETIC_SELF_CONSISTENCY"
    assert budget["separate_engineering_check"]["must_remain_separate_from_factual_budget_accuracy"] is True


def test_w06_contract_09_opening_hours_unknown_is_neither_pass_nor_violation(contract_doc: dict):
    """W06-CONTRACT-09: opening-hours UNKNOWN is neither PASS nor VIOLATION."""
    oh = contract_doc["opening_hours_semantics"]
    assert oh["tier"] == "SECONDARY_EVIDENCE_CONDITIONAL"
    assert oh["evaluation_states"] == ["COMPLIANT", "VIOLATION", "UNKNOWN"]
    unk = oh["unknown_state_contract"]
    assert unk["is_pass"] is False
    assert unk["is_violation"] is False
    assert unk["never_silently_convert_to_pass_or_violation"] is True


def test_w06_contract_10_opening_hours_compliance_denominator_excludes_unknown(contract_doc: dict):
    """W06-CONTRACT-10: opening-hours compliance denominator excludes UNKNOWN."""
    oh = contract_doc["opening_hours_semantics"]
    assert oh["unknown_state_contract"]["excluded_from_compliance_denominator"] is True
    assert oh["compliance_rate_denominator"] == "opening_hours_evaluable_items_only"
    required_metrics = set(oh["required_reported_metrics"])
    assert {
        "opening_hours_evaluable_items",
        "opening_hours_unknown_items",
        "opening_hours_evidence_coverage",
        "opening_hours_compliance_rate_on_evaluable_items",
    }.issubset(required_metrics)


def test_w06_contract_11_travel_time_is_not_evaluable(contract_doc: dict):
    """W06-CONTRACT-11: travel time = NOT_EVALUABLE."""
    geo = contract_doc["geo_and_routing_semantics"]
    assert geo["road_network_routing_or_travel_time_evidence_exists"] is False
    assert geo["dimensions"]["TRAVEL_TIME"] == "NOT_EVALUABLE"
    assert geo["dimensions"]["ROUTE_DISTANCE"] == "NOT_EVALUABLE"


def test_w06_contract_12_haversine_only_geo_distance_proxy(contract_doc: dict):
    """W06-CONTRACT-12: Haversine only GEO_DISTANCE_PROXY."""
    geo = contract_doc["geo_and_routing_semantics"]
    hav = geo["haversine_naming_contract"]
    assert hav["required_metric_name"] == "GEO_DISTANCE_PROXY"
    assert hav["diagnostic_only_in_v1"] is True
    assert set(hav["forbidden_labels"]) == {"travel time", "route distance", "routing quality"}


def test_w06_contract_13_preference_satisfaction_not_primary_evaluable_with_synthetic_gt(
    contract_doc: dict,
):
    """W06-CONTRACT-13: preference satisfaction not primary evaluable with synthetic-only GT."""
    pref = contract_doc["preference_satisfaction_semantics"]
    assert pref["status"] == "NOT_PRIMARY_EVALUABLE"
    assert pref["audit_evidence"]["synthetic_preference_records"] == 300
    assert pref["audit_evidence"]["verified_real_user_preference_gt_records"] == 0
    assert pref["llm_as_judge_allowed_as_final_human_preference_gt"] is False
    assert "real_user_preference_satisfaction" in pref["forbidden_claims_from_synthetic_profiles"]


def test_w06_contract_14_no_weighted_composite_score(contract_doc: dict):
    """W06-CONTRACT-14: no weighted composite score."""
    core_pass = contract_doc["primary_scenario_pass_semantics"]
    assert core_pass["weighted_composite_score_allowed"] is False
    assert core_pass["report_each_dimension_independently"] is True


def test_w06_contract_15_core_scenario_pass_semantics_frozen(contract_doc: dict):
    """W06-CONTRACT-15: CORE_SCENARIO_PASS semantics frozen."""
    core_pass = contract_doc["primary_scenario_pass_semantics"]
    assert core_pass["indicator_name"] == "CORE_SCENARIO_PASS"
    assert core_pass["rate_metric_name"] == "CORE_SCENARIO_PASS_RATE"
    assert core_pass["required_pass_conditions"] == [
        "benchmark_run_is_valid",
        "required_day_structure_passes",
        "all_itinerary_poi_items_are_canonically_grounded",
        "all_grounded_pois_match_requested_destination",
        "duplicate_poi_policy_passes",
        "schedule_parsing_interval_and_overlap_checks_pass",
        "estimated_budget_compliance_passes_when_budget_is_present",
    ]
    assert core_pass["opening_hours_policy_in_core_pass"]["unknown_causes_core_scenario_pass_failure"] is False
    assert core_pass["opening_hours_policy_in_core_pass"]["known_violation_reported_separately"] is True


def test_w06_contract_16_mock_fallback_run_invalid(contract_doc: dict):
    """W06-CONTRACT-16: mock/fallback run invalid."""
    run_contract = contract_doc["valid_and_invalid_run_contract"]
    assert "MOCK_OR_FALLBACK_RUN" in run_contract["fail_closed_invalid_run_reasons"]
    assert "API_ERROR" in run_contract["fail_closed_invalid_run_reasons"]
    assert "UNPARSABLE_MODEL_OUTPUT" in run_contract["fail_closed_invalid_run_reasons"]
    assert "MODEL_ID_MISMATCH" in run_contract["fail_closed_invalid_run_reasons"]
    assert "MISSING_REQUIRED_RUN_METADATA" in run_contract["fail_closed_invalid_run_reasons"]
    assert run_contract["invalid_runs_counted_as_successful_scenarios"] is False
    assert run_contract["invalid_runs_must_be_reported_separately"] is True
    assert run_contract["silent_retry_until_success_forbidden"] is True


def test_w06_contract_17_raw_and_parsed_outputs_required_for_future_benchmark_evidence(
    contract_doc: dict,
):
    """W06-CONTRACT-17: raw and parsed outputs required for future benchmark evidence."""
    repro = contract_doc["reproducibility_contract"]
    assert repro["reproducibility_standard"] == "AUDITABLE_PROCESS_REPRODUCIBILITY"
    assert repro["bitwise_llm_output_determinism_claimed"] is False
    required_fields = set(repro["required_persisted_artifacts_and_fields"])
    for expected_field in (
        "scenario_input",
        "raw_provider_response",
        "parsed_plan_response",
        "execution_timestamp_utc",
        "provider",
        "model_id",
        "generation_parameters",
        "api_execution_mode",
        "latency",
        "usage_metadata_if_available",
        "scenario_sha256",
        "catalog_sha256",
        "evaluator_sha256",
        "code_commit_sha",
        "raw_response_sha256",
        "parsed_response_sha256",
    ):
        assert expected_field in required_fields


def test_w06_contract_18_100_scenarios_not_generated_in_this_task(contract_doc: dict):
    """W06-CONTRACT-18: 100 scenarios not generated in this task."""
    assert contract_doc["scenarios_generated"] is False
    assert contract_doc["scenario_design_contract"]["scenarios_generated_in_this_task"] is False
    scenario_files = sorted(p.name for p in PLANNER_EVAL_DIR.glob("*.json"))
    assert scenario_files == ["da_nang_4d.json", "ha_giang_3d.json", "moc_chau_3d.json"]


def test_w06_contract_19_production_behavior_unchanged(contract_doc: dict):
    """W06-CONTRACT-19: production behavior unchanged."""
    assert contract_doc["production_behavior_modified"] is False
    prereqs = contract_doc["required_instrumentation_prerequisites"]
    assert [p["id"] for p in prereqs] == [f"P{i}" for i in range(1, 13)]
    assert all(p["implemented_in_this_task"] is False for p in prereqs)

    _ensure_commit_present(EXPECTED_BASE_DEVELOP_SHA)
    res = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            EXPECTED_BASE_DEVELOP_SHA,
            "--",
            "apps/",
            "data/curated/",
            "data/evaluation/planner/",
            "data/evaluation/w5/",
            "scripts/",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert res.stdout.strip() == ""


def test_w06_contract_20_legacy_evaluator_classified_insufficient(contract_doc: dict):
    """W06-CONTRACT-20: legacy evaluator classified insufficient for final evaluation."""
    leg = contract_doc["legacy_evaluator_contract"]
    assert leg["evaluator_file"] == "data/evaluation/planner/evaluate_planner.py"
    assert leg["classification"] == "LEGACY_INSUFFICIENT_FOR_FINAL_AGENT_EVAL"
    assert leg["deleted_in_this_task"] is False
    assert leg["modified_in_this_task"] is False
    assert leg["relabeling_existing_outputs_as_final_w06_scientific_results_forbidden"] is True
    assert (REPO_ROOT / "data" / "evaluation" / "planner" / "evaluate_planner.py").exists()


def test_w06_contract_21_roadmap_file_itself_unchanged(contract_doc: dict):
    """W06-CONTRACT-21: roadmap file itself unchanged."""
    clar = contract_doc["roadmap_methodology_clarification"]
    assert clar["locked_roadmap_file"] == "docs/roadmap/gomate-thesis-research-roadmap-v1.md"
    assert clar["locked_roadmap_modified"] is False
    assert CLARIFICATION_MD_PATH.exists()

    _ensure_commit_present(EXPECTED_BASE_DEVELOP_SHA)
    res = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            EXPECTED_BASE_DEVELOP_SHA,
            "--",
            "docs/roadmap/gomate-thesis-research-roadmap-v1.md",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert res.stdout.strip() == ""


def test_w06_contract_22_no_preregistration_created(contract_doc: dict):
    """W06-CONTRACT-22: no preregistration created."""
    assert contract_doc["preregistration_created"] is False
    w06_files = sorted(p.name for p in (REPO_ROOT / "data" / "evaluation" / "w06").glob("*"))
    assert w06_files == [
        "w06_measurement_capability_audit_v1.json",
        "w06_measurement_contract_v1.json",
    ]


def test_w06_contract_23_no_scientific_w06_results_generated(contract_doc: dict):
    """W06-CONTRACT-23: no scientific W06 results generated."""
    assert contract_doc["scientific_results_generated"] is False
    assert contract_doc["final_benchmark_executed"] is False
    assert contract_doc["repository_mutation_scope"] == "CONTRACT_ARTIFACTS_AND_TESTS_ONLY"
