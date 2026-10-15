"""Pytest suite for W06-MODEL-ARCH-SELECTION-METHOD-LOCK-01.

Verifies the frozen W06 Model & Architecture Selection Method Lock
(`data/evaluation/w06/w06_model_arch_selection_method_lock_v1.json`),
its companion documentation (`docs/research/w06_model_arch_selection_method_lock_v1.md`),
cryptographic non-interference with all prior frozen W06 artifacts,
and strict scientific/execution boundaries before DEV model execution.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Tuple

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
METHOD_LOCK_PATH = (
    REPO_ROOT / "data" / "evaluation" / "w06" / "w06_model_arch_selection_method_lock_v1.json"
)
DOC_PATH = REPO_ROOT / "docs" / "research" / "w06_model_arch_selection_method_lock_v1.md"

EXPECTED_BASE_DEVELOP_SHA = "6043402ab102a6bc116aabc0319932208184e102"
EXPECTED_FROZEN_BUNDLE_SHA256 = "c03bc6dc300604ac395505d59b6413c1a47339b21408cfd637671e81d4b555a1"
EXPECTED_P11_SHA256 = "0aa9ae923d0e7f29df49735fa41e87530b1caf62418fcbec09a1eff81d83af62"

EXPECTED_PRIOR_ARTIFACTS: Dict[str, Tuple[Path, str]] = {
    "frozen_scenario_bundle": (
        REPO_ROOT / "data" / "evaluation" / "w06" / "w06_scenarios_freeze_v1.json",
        EXPECTED_FROZEN_BUNDLE_SHA256,
    ),
    "p11_manifest": (
        REPO_ROOT / "data" / "evaluation" / "w06" / "w06_p11_assignment_manifest_v1.json",
        EXPECTED_P11_SHA256,
    ),
    "scenario_method_lock": (
        REPO_ROOT / "data" / "evaluation" / "w06" / "w06_scenario_method_lock_v1.json",
        "5e5359f9f10a0248a9cf031f8e8b26c0314c46aecfe0d9df479388bbe4fd1af9",
    ),
    "scenario_support_matrix": (
        REPO_ROOT / "data" / "evaluation" / "w06" / "w06_scenario_support_matrix_v1.json",
        "68c2bfc2164e664b3856c31b99a92d75a588f64465526b47c9104918a51cedb4",
    ),
    "measurement_contract": (
        REPO_ROOT / "data" / "evaluation" / "w06" / "w06_measurement_contract_v1.json",
        "0ddc1f8d879493517cee25f247d2365a0bacb816dc33b129b0c6110d4bfb8298",
    ),
    "catalog": (
        REPO_ROOT / "data" / "curated" / "gomate_places_freeze_v2.json",
        "f7517938598e3923906763f8f31334a500ee88bc06232f2992d38e2fcb28a444",
    ),
    "reca_contract": (
        REPO_ROOT / "apps" / "ai-service" / "recommendation" / "reca" / "contract.py",
        "1a62c36a95092be35ab78dca43e20f646016e154746ee051a499bdebfc67538c",
    ),
    "generator_source": (
        REPO_ROOT / "apps" / "ai-service" / "app" / "evaluation" / "planner_scenario_generator.py",
        "623c52cbdd98d181cd9cbbc1e68697a7299cb6c864628e97e743afd9e09ceae1",
    ),
    "qa_verifier": (
        REPO_ROOT / "scripts" / "audit_w06_scenario_generator_dryrun.py",
        "2e5a218fc49d4af0052dffa49c14a8a7d5d9818847fd6d37f647422a9cadc6fc",
    ),
}


def _lf_sha256(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(raw).hexdigest()


def _canonical_json_lf_bytes(obj: Any) -> bytes:
    return (json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


@pytest.fixture(scope="module")
def lock_data() -> Dict[str, Any]:
    return json.loads(METHOD_LOCK_PATH.read_text(encoding="utf-8"))


def test_mas_01_method_lock_exists_and_is_canonical_json(lock_data: Dict[str, Any]):
    """MAS-01: method lock file exists, is canonical UTF-8 LF JSON, and has frozen status."""
    assert METHOD_LOCK_PATH.exists()
    raw_bytes = METHOD_LOCK_PATH.read_bytes()
    assert raw_bytes == _canonical_json_lf_bytes(lock_data)
    assert lock_data["artifact_id"] == "W06-MODEL-ARCH-SELECTION-METHOD-LOCK-01"
    assert lock_data["task_id"] == "W06-MODEL-ARCH-SELECTION-METHOD-LOCK-01"
    assert lock_data["version"] == "1.0.0"
    assert lock_data["status"] == "FROZEN_BEFORE_DEV_MODEL_EXECUTION"
    assert lock_data["base_develop_sha"] == EXPECTED_BASE_DEVELOP_SHA
    assert lock_data["hash_basis"] == "SHA256_CANONICAL_JSON_UTF8_LF_BYTES"


def test_mas_02_preconditions_and_prior_frozen_artifacts_unchanged(lock_data: Dict[str, Any]):
    """MAS-02: preconditions match closed W06-SCENARIO-FREEZE-01 and all prior artifacts are byte-identical."""
    pre = lock_data["preconditions"]
    assert pre["w06_scenario_freeze_01_status"] == "CLOSED"
    assert pre["grok_council_phase_2_status"] == "COMPLETE"
    assert pre["chatgpt_methodology_decision"] == "FINAL_FOR_DEV_SELECTION"
    assert pre["frozen_scenario_bundle_sha256"] == EXPECTED_FROZEN_BUNDLE_SHA256
    assert pre["p11_sha256"] == EXPECTED_P11_SHA256

    for name, (path, expected_sha) in EXPECTED_PRIOR_ARTIFACTS.items():
        assert path.exists(), f"Missing prior artifact {name}: {path}"
        assert _lf_sha256(path) == expected_sha, f"Prior artifact modified: {name}"


def test_mas_03_primary_architecture_locked(lock_data: Dict[str, Any]):
    """MAS-03: primary architecture is locked to direct 1-call LLM planner with deterministic grounding/validation."""
    arch = lock_data["primary_architecture"]
    assert (
        arch["architecture_id"]
        == "LLM_BASED_ITINERARY_PLANNER_WITH_DETERMINISTIC_GROUNDING_AND_VALIDATION_V1"
    )
    assert arch["architecture_class"] == "DIRECT_ONE_CALL_PLUS_READ_ONLY_DETERMINISTIC_VALIDATION"
    assert (
        arch["preferred_thesis_label"]
        == "LLM-based itinerary planner with deterministic grounding and validation"
    )
    assert arch["autonomous_or_multi_agent_claim_allowed"] is False
    assert arch["llm_calls_per_execution"] == 1
    assert arch["model_initiated_tool_calls"] == 0
    assert arch["validator_feedback_to_model"] is False
    assert arch["llm_repair_calls"] == 0
    assert arch["deterministic_semantic_repair_enabled"] is False
    assert arch["automatic_retry_count"] == 0
    assert arch["fallback_model_allowed"] is False
    assert arch["deterministic_catalog_before_model"] is True
    assert arch["offline_evaluator_is_scientific_score_authority"] is True


def test_mas_04_structured_output_policy_locked(lock_data: Dict[str, Any]):
    """MAS-04: structured output policy requires native semantic schema support without place_id enum encoding."""
    sop = lock_data["structured_output_policy"]
    assert sop["native_structured_output_required_for_dev_select"] is True
    assert sop["required_semantic_schema"] == "BenchmarkPlanResponse"
    assert sop["encode_catalog_place_ids_as_provider_side_enum"] is False
    assert sop["provider_decoding_is_part_of_evaluated_system"] is True
    assert sop["offline_pydantic_validation_identical_across_providers"] is True
    assert (
        sop["structured_output_mode_determined_by"]
        == "TECHNICAL_CAPABILITY_PREFLIGHT_NOT_DEV_PERFORMANCE"
    )
    assert sop["candidate_without_semantic_schema_support_enters_dev_select"] is False


def test_mas_05_primary_json_normalization_policy_locked(lock_data: Dict[str, Any]):
    """MAS-05: primary JSON normalization disables all malformed-JSON rescue and isolates legacy cleaner as diagnostic."""
    jnp = lock_data["primary_json_normalization_policy"]
    assert jnp["raw_provider_artifact_preserved"] is True
    assert jnp["primary_substring_json_extraction"] is False
    assert jnp["primary_trailing_comma_repair"] is False
    assert jnp["primary_code_fence_removal"] is False
    assert jnp["primary_llm_json_repair"] is False
    assert jnp["primary_json_repair_enabled"] is False
    assert jnp["malformed_json_rescue_affects_primary_metrics"] is False
    assert jnp["legacy_cleaner_function"] == "clean_benchmark_json_response"
    assert jnp["legacy_cleaner_role"] == "DIAGNOSTIC_ONLY_RECOVERY_REPORTING"
    assert jnp["diagnostic_metric_name"] == "LEGACY_RECOVERABLE_PARSE_RATE"
    assert jnp["legacy_cleaner_replaces_primary_artifact"] is False


def test_mas_06_sampling_policy_locked(lock_data: Dict[str, Any]):
    """MAS-06: sampling policy locks temperature=0/UNSUPPORTED and seed=2026101508/UNSUPPORTED with no tuning."""
    sp = lock_data["sampling_policy"]
    assert sp["temperature_if_supported"] == 0
    assert sp["temperature_if_unsupported"] == "UNSUPPORTED"
    assert sp["unsupported_temperature_requires_documented_provider_fixed_behavior"] is True
    assert sp["seed_if_supported"] == 2026101508
    assert sp["seed_if_unsupported"] == "UNSUPPORTED"
    assert sp["temperature_or_seed_selected_by_dev_performance"] is False
    assert sp["temperature_grid_search_allowed"] is False
    assert sp["seed_shopping_allowed"] is False
    assert sp["bitwise_determinism_claimed"] is False
    assert (
        sp["thinking_or_reasoning_level_policy"]
        == "FIXED_DURING_TECHNICAL_PREFLIGHT_DOCUMENTED_AND_NOT_TUNED_ON_DEV_SELECT"
    )


def test_mas_07_retry_and_failure_policy_locked(lock_data: Dict[str, Any]):
    """MAS-07: retry/failure policy enforces 0 SDK/transport retries and keeps all failures in denominator."""
    rfp = lock_data["retry_and_failure_policy"]
    assert rfp["sdk_automatic_retry"] == 0
    assert rfp["transport_retry"] == 0
    assert rfp["scenario_retry_allowed_after"] == []
    assert rfp["forbidden_retry_outcomes"] == [
        "HTTP_429",
        "HTTP_5XX",
        "TIMEOUT",
        "PARTIAL_TIMEOUT",
        "MALFORMED_MODEL_OUTPUT",
        "SCHEMA_NONCOMPLIANCE",
        "REFUSAL",
        "CONSTRAINT_FAILURE",
    ]
    assert rfp["all_final_outcomes_remain_in_assigned_denominator"] is True
    assert rfp["fallback_model_or_provider_allowed"] is False
    assert (
        rfp["model_id_or_resolved_version_mismatch_action"]
        == "CONFIGURATION_INTEGRITY_FAILURE_STOP_BATCH_BEFORE_SCIENTIFIC_REPORTING"
    )
    assert rfp["simulated_transport_or_server_failure_single_request_validation_required"] is True


def test_mas_08_harness_error_policy_locked(lock_data: Dict[str, Any]):
    """MAS-08: harness error policy forbids single-scenario reruns and mandates batch stop + formal amendment."""
    hep = lock_data["harness_error_policy"]
    assert hep["single_scenario_harness_rerun_allowed"] is False
    assert hep["on_objectively_demonstrated_harness_error"] == [
        "STOP_ENTIRE_BATCH",
        "PRESERVE_ALL_OLD_ARTIFACTS",
        "DO_NOT_SILENTLY_CONTINUE",
        "REQUIRE_FORMAL_AMENDMENT",
        "RE_FREEZE_CHANGED_CONFIG_OR_CODE",
        "AMEND_PREREGISTRATION",
        "RERUN_COMPLETE_100_AS_NEW_RUN_ID_IF_ALLOWED",
    ]
    assert (
        hep["harness_error_determination_basis"]
        == "INFRASTRUCTURE_AND_CODE_EVIDENCE_AND_LOGS_ONLY_NOT_OBSERVED_PERFORMANCE"
    )
    assert "COMPROMISED" in hep["if_scientific_metrics_inspected_before_defect_declaration"]


def test_mas_09_dev_model_candidates_locked(lock_data: Dict[str, Any]):
    """MAS-09: exactly 3 DEV model candidates C1/C2/C3 are locked without auto-substitution."""
    dmc = lock_data["dev_model_candidates_policy"]
    assert dmc["max_dev_select_candidates"] == 3
    assert dmc["candidates_are_final_selected_models"] is False
    assert dmc["automatic_substitution_or_alias_allowed"] is False
    assert dmc["failed_preflight_status"] == "FAILED_PREFLIGHT"
    assert dmc["replace_failed_candidate_after_dev_results_allowed"] is False
    assert (
        dmc[
            "gemini_flash_lite_or_open_weight_addition_without_formal_amendment_before_dev_select_allowed"
        ]
        is False
    )
    assert dmc["candidates"] == [
        {
            "candidate_id": "C1",
            "provider": "Google",
            "model": "gemini-3.8-flash",
            "role": "CANDIDATE_NOT_SELECTED_FINAL_MODEL",
        },
        {
            "candidate_id": "C2",
            "provider": "OpenAI",
            "model": "gpt-6.1-sol",
            "role": "CANDIDATE_NOT_SELECTED_FINAL_MODEL",
        },
        {
            "candidate_id": "C3",
            "provider": "Anthropic",
            "model": "claude-sonnet-5-5",
            "role": "CANDIDATE_NOT_SELECTED_FINAL_MODEL",
        },
    ]


def test_mas_10_dev_fixture_methodology_locked(lock_data: Dict[str, Any]):
    """MAS-10: DEV fixture seed 2026101507, 80 total (20 DEV-TUNE + 60 DEV-SELECT), and exact DEV-SELECT balance."""
    dfm = lock_data["dev_fixture_methodology"]
    assert dfm["dev_fixture_seed"] == 2026101507
    assert dfm["seed_shopping"] is False
    assert dfm["total_dev_fixtures"] == 80
    assert dfm["dev_tune_count"] == 20
    assert dfm["dev_select_count"] == 60
    assert dfm["dev_tune_count"] + dfm["dev_select_count"] == dfm["total_dev_fixtures"]
    assert dfm["final_100_forbidden_for_model_selection"] is True
    assert dfm["dev_fixture_ids_and_paths_distinct_from_final_w06"] is True

    bal = dfm["dev_select_target_balance"]
    assert bal["destination"] == {"ha-noi": 20, "da-nang": 20, "ha-long": 20}
    assert bal["days"] == {"2": 20, "3": 20, "4": 20}
    assert bal["interest_count"] == {"1": 20, "2": 20, "3": 20}
    assert bal["budget"] == {"B1": 15, "B2": 15, "B3": 15, "null": 15}
    assert bal["travel_style"] == {"BACKPACKER": 15, "BUDGET": 15, "COMFORT": 15, "LUXURY": 15}
    assert bal["weekend"] == {"true": 30, "false": 30}


def test_mas_11_final_dev_overlap_policy_locked(lock_data: Dict[str, Any]):
    """MAS-11: overlap policy enforces 0 exact overlap on all 80 DEV fixtures and 0 near overlap on DEV-TUNE."""
    ovp = lock_data["final_dev_overlap_policy"]
    assert ovp["exact_signature_fields"] == [
        "destination_slug",
        "days",
        "sorted_interests",
        "budget_tier_or_null",
        "weekend_exposure",
        "travel_style",
    ]
    assert ovp["all_80_dev_exact_signature_overlap_with_final_100"] == 0
    assert ovp["dev_tune_near_overlap_with_final_100"] == 0
    assert ovp["dev_select_exact_overlap_with_final_100"] == 0
    assert ovp["dev_select_near_overlap_may_exist"] is True
    assert ovp["dev_select_near_overlap_count_must_be_reported"] is True
    assert ovp["automated_overlap_checker_prints_final_scenario_semantics"] is False
    assert (
        ovp["infeasible_20_dev_tune_zero_near_overlap_action"]
        == "STOP_DO_NOT_SILENTLY_RELAX_DEFINITION"
    )


def test_mas_12_prompt_tuning_and_dev_select_execution_policies_locked(lock_data: Dict[str, Any]):
    """MAS-12: shared prompt tuning max 2 versions on DEV-TUNE with prompt lock, and max 180 executions on DEV-SELECT."""
    ptp = lock_data["prompt_tuning_policy"]
    assert ptp["max_shared_semantic_prompt_versions_on_dev_tune"] == 2
    assert ptp["provider_specific_semantic_prompts_allowed"] is False
    assert ptp["allowed_provider_adapter_differences"] == ["API_SYNTAX", "STRUCTURED_OUTPUT_WIRING"]
    assert ptp["record_every_attempted_prompt_version"] is True
    assert ptp["prompt_lock_before_dev_select"] is True
    assert ptp["semantic_prompt_edit_after_dev_select_begins_allowed"] is False
    assert ptp["dev_select_rerun_on_disappointing_result_allowed"] is False

    dse = lock_data["dev_select_execution_policy"]
    assert dse["executions_per_candidate_per_fixture"] == 1
    assert dse["automatic_retry"] == 0
    assert dse["repair"] == 0
    assert dse["max_dev_select_configs"] == 3
    assert dse["dev_select_fixture_count"] == 60
    assert dse["max_model_executions_in_one_dev_select"] == 180
    assert dse["best_of_n_selection_allowed"] is False


def test_mas_13_lexicographic_selection_rule_and_final_config_count_locked(
    lock_data: Dict[str, Any],
):
    """MAS-13: lexicographic selection rule with 10pp tie band on criteria 1-3 and final_primary_config_count=1."""
    rule = lock_data["model_config_selection_rule"]
    assert rule["weighted_composite_allowed"] is False
    assert rule["rule_type"] == "LEXICOGRAPHIC_WITH_PRACTICAL_TIE_BAND"
    assert rule["ordered_criteria"] == [
        "VALID_RUN_AND_SCHEMA_RATE",
        "EXACT_GROUNDING_PASS_RATE",
        "FINAL_CORE_PASS_RATE",
        "MEDIAN_COST_PER_SCENARIO",
        "MEDIAN_LATENCY",
    ]
    assert rule["criteria_1_to_3_practical_tie_abs_diff_percentage_points"] == 10.0
    assert rule["on_tie_action"] == "ADVANCE_TO_NEXT_CRITERION"
    assert rule["criterion_4_tie_breaker"] == "LOWER_MEDIAN_COST_WINS"
    assert rule["criterion_5_tie_breaker"] == "LOWER_MEDIAN_LATENCY_WINS"
    assert (
        rule["final_tie_breaker"]
        == "SIMPLER_AND_MORE_DIRECTLY_PINNABLE_PROVIDER_CONFIGURATION"
    )
    assert rule["stop_permanently_after_one_dev_select_comparison"] is True
    assert rule["add_candidate_or_config_after_inspecting_dev_select_allowed"] is False
    assert rule["report_every_candidate_result_required"] is True

    fbd = lock_data["final_benchmark_design"]
    assert fbd["final_primary_config_count"] == 1
    assert fbd["final_scenario_count"] == 100
    assert fbd["executions_per_scenario"] == 1
    assert fbd["automatic_retry"] == 0
    assert fbd["claim_model_superiority_from_final_100_allowed"] is False


def test_mas_14_opening_hours_audit_and_pre_prereg_freeze_fields_locked(
    lock_data: Dict[str, Any],
):
    """MAS-14: opening-hours catalog audit authorized read-only and all pre-preregistration fields specified."""
    oha = lock_data["opening_hours_coverage_audit_authorization"]
    assert oha["authorized"] is True
    assert oha["mode"] == "READ_ONLY_CATALOG_EVIDENCE_AUDIT"
    assert oha["target_catalog_path"] == "data/curated/gomate_places_freeze_v2.json"
    assert oha["inspect_final_scenario_model_outputs_allowed"] is False
    assert oha["modify_frozen_scenarios_allowed"] is False
    assert oha["reporting_role"] == "BENCHMARK_EVIDENCE_COVERAGE_ONLY"

    req_fields = set(lock_data["required_pre_preregistration_config_freeze_fields"])
    expected_fields = {
        "provider",
        "provider_endpoint",
        "region",
        "requested_model_id",
        "resolved_or_returned_model_metadata_if_exposed",
        "sdk_exact_version",
        "dependency_lock_or_environment_hash",
        "architecture_id",
        "llm_calls_per_execution",
        "tool_call_policy",
        "system_prompt",
        "user_template",
        "prompt_hashes",
        "response_schema",
        "schema_hash",
        "structured_output_mode",
        "temperature",
        "top_p",
        "top_k",
        "seed",
        "thinking_or_reasoning_setting",
        "max_output_tokens",
        "timeout",
        "automatic_retry",
        "transport_retry",
        "fallback_policy",
        "repair_policy",
        "json_normalization_policy",
        "catalog_sha",
        "scenario_bundle_sha",
        "p11_sha",
        "evaluator_sha",
        "opening_hours_evidence_state_or_hash",
        "failure_taxonomy",
        "execution_ordering",
        "logging_schema_or_version",
        "code_commit_sha",
    }
    assert req_fields == expected_fields


def test_mas_15_claim_boundaries_provenance_and_execution_boundaries(lock_data: Dict[str, Any]):
    """MAS-15: claim boundaries, ChatGPT methodology ownership, and zero provider/DEV/prereg execution."""
    scb = lock_data["scientific_claim_boundaries"]
    assert (
        scb["preferred_system_description"]
        == "LLM-based itinerary planner with deterministic grounding and validation"
    )
    assert len(scb["w06_does_not_establish"]) == 8

    prov = lock_data["decision_provenance"]
    assert prov["methodology_owner"] == "ChatGPT"
    assert prov["grok_made_final_decision"] is False
    assert "W06 Grok Council Phase 2 cross-critique" in prov["inputs"]
    assert "final ChatGPT methodology decision" in prov["inputs"]

    teb = lock_data["task_execution_boundaries"]
    for key, val in teb.items():
        assert val is False, f"Expected task_execution_boundaries[{key!r}] is False, got {val!r}"

    assert DOC_PATH.exists()
    doc_text = DOC_PATH.read_text(encoding="utf-8")
    assert "W06-MODEL-ARCH-SELECTION-METHOD-LOCK-01" in doc_text
    assert "LLM-based itinerary planner with deterministic grounding and validation" in doc_text
    assert "gemini-3.8-flash" in doc_text
    assert "gpt-6.1-sol" in doc_text
    assert "claude-sonnet-5-5" in doc_text
