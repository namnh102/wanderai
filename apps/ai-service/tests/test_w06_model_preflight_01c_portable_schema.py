"""Offline verification tests for W06-MODEL-PREFLIGHT-01C-PORTABLE-SCHEMA-AMENDMENT-OFFLINE.

Covers PC-01 through PC-35:
- PC-01: semantic schema SHA unchanged
- PC-02: V1 generation schema SHA unchanged
- PC-03: 01B live plan SHA unchanged
- PC-04: 01B receipt/artifacts unchanged
- PC-05: V2 deterministic hash
- PC-06: V2 shared identically across C1/C2/C3
- PC-07: no provider-specific V2 schema
- PC-08: minimum removed from provider V2
- PC-09: maximum removed
- PC-10: multipleOf absent
- PC-11: minLength removed
- PC-12: maxLength removed
- PC-13: unsupported array constraints absent
- PC-14: supported minItems values obey Anthropic docs
- PC-15: additionalProperties=false preserved
- PC-16: required materialization preserved
- PC-17: ActivityKind enum unchanged
- PC-18: place_id not catalog enum
- PC-19: nullable place_id semantics preserved
- PC-20: stripped constraint manifest exact
- PC-21: constraint description annotation deterministic
- PC-22: V2 projection guard rejects unrelated mutation
- PC-23: semantic Pydantic validation still rejects total_days=0
- PC-24: semantic validation rejects total_days=15
- PC-25: semantic validation rejects order_index=0
- PC-26: semantic validation rejects negative estimated_cost
- PC-27: semantic validation rejects empty required item list
- PC-28: valid smoke response validates
- PC-29: Anthropic unsupported-keyword scanner returns 0 for V2
- PC-30: historical 01B V1 code path still verifies
- PC-31: DEV-TUNE forbidden
- PC-32: DEV-SELECT forbidden
- PC-33: final100 forbidden
- PC-34: live provider call forbidden
- PC-35: amendment requires all 3 candidates in 01D
"""
import copy
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.evaluation.model_preflight import (
    COMMON_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA,
    COMMON_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA_V1,
    COMMON_GENERATION_SCHEMA_SHA256,
    COMMON_GENERATION_SCHEMA_SHA256_V1,
    COMMON_PORTABLE_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA_V2,
    COMMON_PORTABLE_GENERATION_SCHEMA_SHA256_V2,
    FROZEN_01B_LIVE_PLAN_SHA256,
    FROZEN_01C_BASE_DEVELOP_SHA,
    SEMANTIC_SCHEMA_SHA256,
    LiveProviderCallForbiddenError,
    apply_deterministic_constraint_description,
    build_all_candidate_preflight_adapters,
    build_anthropic_structured_output_wiring_v2,
    build_common_portable_generation_benchmark_plan_json_schema_v2,
    build_google_structured_output_wiring_v2,
    build_model_preflight_01c_receipt_v1,
    build_openai_structured_output_wiring_v2,
    build_portable_schema_v2_manifest,
    build_schema_portability_amendment_v1,
    build_synthetic_smoke_fixtures,
    build_synthetic_valid_plan_json,
    check_cross_provider_v2_static_compatibility,
    compute_common_generation_schema_sha256,
    compute_common_portable_generation_schema_sha256_v2,
    compute_semantic_schema_sha256,
    format_semantic_constraint_annotation,
    scan_anthropic_portable_schema_compatibility,
    schema_encodes_place_id_as_catalog_enum,
    verify_portable_generation_schema_v2_projection,
)
from app.evaluation.model_preflight.live_smoke import (
    verify_frozen_authorities_01b,
    verify_live_plan_immutability,
)
from app.schemas.planner_benchmark import BenchmarkPlanResponse
from app.services.planner_benchmark_runner import sha256_bytes

REPO_ROOT = Path(__file__).resolve().parents[3]
W06_EVAL_DIR = REPO_ROOT / "data" / "evaluation" / "w06"

EXPECTED_SEMANTIC_SCHEMA_SHA256 = (
    "e4169f7b890f77d13af65e9f2070b6071c535b206d88440f5e8f28c179977555"
)
EXPECTED_V1_GENERATION_SCHEMA_SHA256 = (
    "5f7331eb1ac137a42b75a0c307107e3305703d4782ddffdcfe98c1b5ae11c27c"
)


def _valid_smoke_plan_payload() -> dict[str, Any]:
    scenario, pois = build_synthetic_smoke_fixtures()[0]
    return json.loads(build_synthetic_valid_plan_json(scenario, pois))


def _collect_all_keywords(node: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(node, dict):
        for k, v in node.items():
            found.add(k)
            found |= _collect_all_keywords(v)
    elif isinstance(node, list):
        for item in node:
            found |= _collect_all_keywords(item)
    return found


def test_pc_01_semantic_schema_sha_unchanged():
    """PC-01: semantic schema SHA unchanged."""
    assert SEMANTIC_SCHEMA_SHA256 == EXPECTED_SEMANTIC_SCHEMA_SHA256
    assert compute_semantic_schema_sha256() == EXPECTED_SEMANTIC_SCHEMA_SHA256


def test_pc_02_v1_generation_schema_sha_unchanged():
    """PC-02: V1 generation schema SHA unchanged."""
    assert COMMON_GENERATION_SCHEMA_SHA256 == EXPECTED_V1_GENERATION_SCHEMA_SHA256
    assert COMMON_GENERATION_SCHEMA_SHA256_V1 == EXPECTED_V1_GENERATION_SCHEMA_SHA256
    assert compute_common_generation_schema_sha256() == EXPECTED_V1_GENERATION_SCHEMA_SHA256
    assert (
        COMMON_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA_V1
        == COMMON_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA
    )


def test_pc_03_01b_live_plan_sha_unchanged():
    """PC-03: 01B live plan SHA unchanged."""
    plan_path = W06_EVAL_DIR / "w06_model_preflight_01b_live_plan_v1.json"
    assert plan_path.exists()
    actual_sha = sha256_bytes(plan_path.read_bytes())
    assert actual_sha == FROZEN_01B_LIVE_PLAN_SHA256
    assert actual_sha == "3c59a1fba4faa7463c2a068a230ee492437713a78337b2e904980cf13c58f712"


def test_pc_04_01b_receipt_and_artifacts_unchanged():
    """PC-04: 01B receipt/artifacts unchanged and C3 failure preserved."""
    receipt_path = W06_EVAL_DIR / "w06_model_preflight_01b_live_receipt_v1.json"
    assert receipt_path.exists()
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["candidates"]["C1"]["status"] == "PASSED_TECHNICAL_PREFLIGHT"
    assert receipt["candidates"]["C2"]["status"] == "PASSED_TECHNICAL_PREFLIGHT"
    assert receipt["candidates"]["C3"]["status"] == "FAILED_TECHNICAL_PREFLIGHT"
    assert (
        receipt["candidates"]["C3"]["failure_classification"]
        == "FAILED_STRUCTURED_OUTPUT_COMPATIBILITY"
    )

    for cid in ("C1", "C2", "C3"):
        c_dir = W06_EVAL_DIR / "model_preflight_01b_live" / cid
        assert c_dir.is_dir()
        assert any(c_dir.iterdir())


def test_pc_05_v2_deterministic_hash():
    """PC-05: V2 deterministic hash across repeated builds."""
    sha_a = compute_common_portable_generation_schema_sha256_v2()
    sha_b = compute_common_portable_generation_schema_sha256_v2()
    assert sha_a == sha_b
    assert sha_a == COMMON_PORTABLE_GENERATION_SCHEMA_SHA256_V2
    assert sha_a != EXPECTED_V1_GENERATION_SCHEMA_SHA256
    assert sha_a != EXPECTED_SEMANTIC_SCHEMA_SHA256


def test_pc_06_v2_shared_identically_across_c1_c2_c3():
    """PC-06: V2 shared identically across C1/C2/C3."""
    w_c1 = build_google_structured_output_wiring_v2()
    w_c2 = build_openai_structured_output_wiring_v2()
    w_c3 = build_anthropic_structured_output_wiring_v2()

    assert (
        w_c1["portable_generation_schema_v2_sha256"]
        == COMMON_PORTABLE_GENERATION_SCHEMA_SHA256_V2
    )
    assert (
        w_c2["portable_generation_schema_v2_sha256"]
        == COMMON_PORTABLE_GENERATION_SCHEMA_SHA256_V2
    )
    assert (
        w_c3["portable_generation_schema_v2_sha256"]
        == COMMON_PORTABLE_GENERATION_SCHEMA_SHA256_V2
    )
    assert (
        w_c1["response_json_schema"]
        == w_c2["response_format"]["json_schema"]["schema"]
        == w_c3["output_config"]["format"]["schema"]
    )


def test_pc_07_no_provider_specific_v2_schema():
    """PC-07: no provider-specific V2 schema."""
    manifest = build_portable_schema_v2_manifest()
    amendment = build_schema_portability_amendment_v1()
    assert manifest["provider_specific_schema"] is False
    assert amendment["v2_applies_identically_to"] == ["C1", "C2", "C3"]


def test_pc_08_minimum_removed_from_provider_v2():
    """PC-08: minimum removed from provider V2."""
    v1_keywords = _collect_all_keywords(COMMON_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA_V1)
    v2_keywords = _collect_all_keywords(COMMON_PORTABLE_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA_V2)
    assert "minimum" in v1_keywords
    assert "minimum" not in v2_keywords


def test_pc_09_maximum_removed():
    """PC-09: maximum removed from provider V2."""
    v1_keywords = _collect_all_keywords(COMMON_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA_V1)
    v2_keywords = _collect_all_keywords(COMMON_PORTABLE_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA_V2)
    assert "maximum" in v1_keywords
    assert "maximum" not in v2_keywords


def test_pc_10_multiple_of_absent():
    """PC-10: multipleOf absent in provider V2."""
    v2_keywords = _collect_all_keywords(COMMON_PORTABLE_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA_V2)
    assert "multipleOf" not in v2_keywords
    assert "exclusiveMinimum" not in v2_keywords
    assert "exclusiveMaximum" not in v2_keywords


def test_pc_11_min_length_removed():
    """PC-11: minLength removed from provider V2."""
    v1_keywords = _collect_all_keywords(COMMON_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA_V1)
    v2_keywords = _collect_all_keywords(COMMON_PORTABLE_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA_V2)
    assert "minLength" in v1_keywords
    assert "minLength" not in v2_keywords


def test_pc_12_max_length_removed():
    """PC-12: maxLength removed / absent in provider V2."""
    v2_keywords = _collect_all_keywords(COMMON_PORTABLE_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA_V2)
    assert "maxLength" not in v2_keywords


def test_pc_13_unsupported_array_constraints_absent():
    """PC-13: unsupported array constraints absent in V2."""
    v2_keywords = _collect_all_keywords(COMMON_PORTABLE_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA_V2)
    for bad_kw in ("maxItems", "uniqueItems", "contains", "minContains", "maxContains"):
        assert bad_kw not in v2_keywords


def test_pc_14_supported_min_items_values_obey_anthropic_docs():
    """PC-14: supported minItems values obey Anthropic docs (only 0 or 1)."""
    scan = scan_anthropic_portable_schema_compatibility(
        COMMON_PORTABLE_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA_V2
    )
    assert scan["supported_min_items_paths"] == [
        "$.$defs.BenchmarkItineraryDay.properties.items",
        "$.properties.days",
    ]
    assert (
        COMMON_PORTABLE_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA_V2["properties"]["days"][
            "minItems"
        ]
        == 1
    )
    assert (
        COMMON_PORTABLE_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA_V2["$defs"][
            "BenchmarkItineraryDay"
        ]["properties"]["items"]["minItems"]
        == 1
    )


def test_pc_15_additional_properties_false_preserved():
    """PC-15: additionalProperties=false preserved on all object nodes."""
    v2 = COMMON_PORTABLE_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA_V2
    assert v2["additionalProperties"] is False
    assert v2["$defs"]["BenchmarkItineraryDay"]["additionalProperties"] is False
    assert v2["$defs"]["BenchmarkItineraryItem"]["additionalProperties"] is False


def test_pc_16_required_materialization_preserved():
    """PC-16: required materialization preserved on all object nodes."""
    v2 = COMMON_PORTABLE_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA_V2
    assert v2["required"] == sorted(v2["properties"].keys())
    day_def = v2["$defs"]["BenchmarkItineraryDay"]
    assert day_def["required"] == sorted(day_def["properties"].keys())
    item_def = v2["$defs"]["BenchmarkItineraryItem"]
    assert item_def["required"] == sorted(item_def["properties"].keys())


def test_pc_17_activity_kind_enum_unchanged():
    """PC-17: ActivityKind enum unchanged."""
    v2 = COMMON_PORTABLE_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA_V2
    assert v2["$defs"]["ActivityKind"]["enum"] == ["POI_VISIT", "TRANSIT_ONLY"]


def test_pc_18_place_id_not_catalog_enum():
    """PC-18: place_id not catalog enum."""
    assert not schema_encodes_place_id_as_catalog_enum(
        COMMON_PORTABLE_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA_V2
    )


def test_pc_19_nullable_place_id_semantics_preserved():
    """PC-19: nullable place_id semantics preserved."""
    place_id_node = COMMON_PORTABLE_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA_V2["$defs"][
        "BenchmarkItineraryItem"
    ]["properties"]["place_id"]
    assert place_id_node == {
        "anyOf": [{"type": "string"}, {"type": "null"}],
        "title": "Place Id",
    }


def test_pc_20_stripped_constraint_manifest_exact():
    """PC-20: stripped constraint manifest exact (16 occurrences: 5 minimum, 1 maximum, 10 minLength)."""
    diff = verify_portable_generation_schema_v2_projection()
    assert diff["whitelist_guard_passed"] is True
    assert diff["removed_constraint_total_count"] == 16
    assert diff["removed_constraint_keyword_counts"] == {
        "maximum": 1,
        "minLength": 10,
        "minimum": 5,
    }
    assert diff["removed_constraint_keywords"] == ["maximum", "minLength", "minimum"]
    assert len(diff["removed_constraint_paths"]) == 16


def test_pc_21_constraint_description_annotation_deterministic():
    """PC-21: constraint description annotation deterministic."""
    v2 = COMMON_PORTABLE_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA_V2
    assert (
        v2["properties"]["total_days"]["description"]
        == "[SEMANTIC_CONSTRAINTS: maximum=14; minimum=1]"
    )
    assert (
        v2["$defs"]["BenchmarkItineraryDay"]["properties"]["day_number"]["description"]
        == "[SEMANTIC_CONSTRAINTS: minimum=1]"
    )
    assert (
        format_semantic_constraint_annotation({"minimum": 1, "maximum": 14})
        == "[SEMANTIC_CONSTRAINTS: maximum=14; minimum=1]"
    )
    assert (
        apply_deterministic_constraint_description("Existing desc.", {"minLength": 1})
        == "Existing desc. [SEMANTIC_CONSTRAINTS: minLength=1]"
    )


def test_pc_22_v2_projection_guard_rejects_unrelated_mutation():
    """PC-22: V2 projection guard rejects unrelated mutation."""
    # 1. Retain an unsupported keyword
    bad_retained = build_common_portable_generation_benchmark_plan_json_schema_v2()
    bad_retained["properties"]["total_days"]["minimum"] = 1
    with pytest.raises(ValueError, match="retained unsupported portable keyword"):
        verify_portable_generation_schema_v2_projection(v2_schema=bad_retained)

    # 2. Mutate an unrelated description on an unstripped node
    bad_desc = build_common_portable_generation_benchmark_plan_json_schema_v2()
    bad_desc["properties"]["days"]["description"] = "Unapproved description"
    with pytest.raises(ValueError, match="Unapproved key set change on unstripped node"):
        verify_portable_generation_schema_v2_projection(v2_schema=bad_desc)

    # 3. Mutate deterministic constraint annotation text
    bad_annot = build_common_portable_generation_benchmark_plan_json_schema_v2()
    bad_annot["properties"]["total_days"]["description"] = "[SEMANTIC_CONSTRAINTS: minimum=1]"
    with pytest.raises(ValueError, match="Non-deterministic or invalid description annotation"):
        verify_portable_generation_schema_v2_projection(v2_schema=bad_annot)

    # 4. Mutate ActivityKind enum
    bad_enum = build_common_portable_generation_benchmark_plan_json_schema_v2()
    bad_enum["$defs"]["ActivityKind"]["enum"] = ["POI_VISIT"]
    with pytest.raises(ValueError, match="Protected V1->V2 key 'enum' altered"):
        verify_portable_generation_schema_v2_projection(v2_schema=bad_enum)


def test_pc_23_semantic_pydantic_validation_still_rejects_total_days_0():
    """PC-23: semantic Pydantic validation still rejects total_days=0."""
    payload = _valid_smoke_plan_payload()
    payload["total_days"] = 0
    with pytest.raises(ValidationError):
        BenchmarkPlanResponse.model_validate(payload)


def test_pc_24_semantic_validation_rejects_total_days_15():
    """PC-24: semantic validation rejects total_days=15."""
    payload = _valid_smoke_plan_payload()
    payload["total_days"] = 15
    with pytest.raises(ValidationError):
        BenchmarkPlanResponse.model_validate(payload)


def test_pc_25_semantic_validation_rejects_order_index_0_and_day_number_0():
    """PC-25: semantic validation rejects order_index=0 and day_number=0."""
    payload_order = _valid_smoke_plan_payload()
    payload_order["days"][0]["items"][0]["order_index"] = 0
    with pytest.raises(ValidationError):
        BenchmarkPlanResponse.model_validate(payload_order)

    payload_day = _valid_smoke_plan_payload()
    payload_day["days"][0]["day_number"] = 0
    with pytest.raises(ValidationError):
        BenchmarkPlanResponse.model_validate(payload_day)


def test_pc_26_semantic_validation_rejects_negative_estimated_cost_and_empty_string():
    """PC-26: semantic validation rejects negative estimated_cost and empty required string."""
    payload_cost = _valid_smoke_plan_payload()
    payload_cost["days"][0]["items"][0]["estimated_cost"] = -10.0
    with pytest.raises(ValidationError):
        BenchmarkPlanResponse.model_validate(payload_cost)

    payload_str = _valid_smoke_plan_payload()
    payload_str["destination"] = ""
    with pytest.raises(ValidationError):
        BenchmarkPlanResponse.model_validate(payload_str)


def test_pc_27_semantic_validation_rejects_empty_required_item_list():
    """PC-27: semantic validation rejects empty required item list."""
    payload = _valid_smoke_plan_payload()
    payload["days"][0]["items"] = []
    with pytest.raises(ValidationError):
        BenchmarkPlanResponse.model_validate(payload)


def test_pc_28_valid_smoke_response_validates():
    """PC-28: valid smoke response still validates cleanly under BenchmarkPlanResponse."""
    payload = _valid_smoke_plan_payload()
    validated = BenchmarkPlanResponse.model_validate(payload)
    assert validated.total_days == 2
    assert len(validated.days) == 2


def test_pc_29_anthropic_unsupported_keyword_scanner_returns_0_for_v2_and_detects_v1():
    """PC-29: Anthropic unsupported-keyword scanner returns 0 for V2 and 16 for V1."""
    v1_scan = scan_anthropic_portable_schema_compatibility(
        COMMON_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA_V1
    )
    assert v1_scan["unsupported_anthropic_keyword_count"] == 16
    assert v1_scan["status"] == "OFFLINE_PORTABILITY_CHECK_FAIL"

    v2_scan = scan_anthropic_portable_schema_compatibility(
        COMMON_PORTABLE_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA_V2
    )
    assert v2_scan["unsupported_anthropic_keyword_count"] == 0
    assert v2_scan["external_ref_count"] == 0
    assert v2_scan["recursive_ref_count"] == 0
    assert v2_scan["open_additional_properties_count"] == 0
    assert v2_scan["status"] == "OFFLINE_PORTABILITY_CHECK_PASS"

    compat = check_cross_provider_v2_static_compatibility()
    assert compat["GOOGLE_V2_STATIC_COMPATIBILITY"] == "PASS"
    assert compat["OPENAI_V2_STATIC_COMPATIBILITY"] == "PASS"
    assert compat["ANTHROPIC_V2_STATIC_COMPATIBILITY"] == "PASS"
    assert compat["status"] == "OFFLINE_PORTABILITY_CHECK_PASS"


def test_pc_30_historical_01b_v1_code_path_still_verifies():
    """PC-30: historical 01B V1 code path still verifies identically."""
    plan_path = W06_EVAL_DIR / "w06_model_preflight_01b_live_plan_v1.json"
    plan_sha = verify_live_plan_immutability(plan_path)
    assert plan_sha == FROZEN_01B_LIVE_PLAN_SHA256
    verified_authorities = verify_frozen_authorities_01b(REPO_ROOT)
    assert len(verified_authorities) == 12


def test_pc_31_dev_tune_forbidden():
    """PC-31: DEV-TUNE forbidden in 01C."""
    amendment = build_schema_portability_amendment_v1()
    receipt = build_model_preflight_01c_receipt_v1()
    assert amendment["dev_tune_started"] is False
    assert receipt["dev_tune_started"] is False


def test_pc_32_dev_select_forbidden():
    """PC-32: DEV-SELECT and winner selection forbidden in 01C."""
    amendment = build_schema_portability_amendment_v1()
    receipt = build_model_preflight_01c_receipt_v1()
    assert amendment["dev_select_started"] is False
    assert amendment["winner_selected"] is False
    assert amendment["DEV_MODEL_SELECTION_ALLOWED"] is False
    assert receipt["dev_select_started"] is False
    assert receipt["winner_selected"] is False
    assert receipt["DEV_MODEL_SELECTION_ALLOWED"] is False


def test_pc_33_final100_forbidden():
    """PC-33: final100 forbidden in 01C."""
    amendment = build_schema_portability_amendment_v1()
    receipt = build_model_preflight_01c_receipt_v1()
    assert amendment["final_100_used"] is False
    assert receipt["final_100_used"] is False


def test_pc_34_live_provider_call_forbidden():
    """PC-34: live provider call forbidden by default in 01C."""
    scenario, pois = build_synthetic_smoke_fixtures()[0]
    adapters = build_all_candidate_preflight_adapters()
    for _cid, adapter in adapters.items():
        with pytest.raises(LiveProviderCallForbiddenError):
            adapter.execute_offline_simulated_request(
                scenario=scenario,
                catalog_pois=pois,
                mock_transport=None,
                request_counter=lambda: 0,
            )


def test_pc_35_amendment_requires_all_3_candidates_in_01d():
    """PC-35: amendment requires all 3 candidates to undergo V2 live revalidation in 01D."""
    amendment = build_schema_portability_amendment_v1()
    receipt = build_model_preflight_01c_receipt_v1()

    assert amendment["future_live_revalidation_required_for_all_candidates"] is True
    assert amendment["reuse_v1_pass_without_v2_revalidation"] is False
    assert amendment["max_future_01d_calls"] == 3
    assert amendment["future_calls_per_candidate"] == 1
    assert amendment["retry_future_01d"] == 0
    assert amendment["current_candidate_technical_eligibility_for_dev"] == {
        "C1": "PENDING_SCHEMA_V2_LIVE_REVALIDATION",
        "C2": "PENDING_SCHEMA_V2_LIVE_REVALIDATION",
        "C3": "PENDING_SCHEMA_V2_LIVE_REVALIDATION",
    }
    assert receipt["C1_current_status"] == "PENDING_SCHEMA_V2_LIVE_REVALIDATION"
    assert receipt["C2_current_status"] == "PENDING_SCHEMA_V2_LIVE_REVALIDATION"
    assert receipt["C3_current_status"] == "PENDING_SCHEMA_V2_LIVE_REVALIDATION"
    assert (
        receipt["next_task"]
        == "W06-MODEL-PREFLIGHT-01D-PORTABLE-SCHEMA-LIVE-REVALIDATION"
    )

    # Also verify materialized JSON artifacts on disk match builders
    manifest_disk = json.loads(
        (W06_EVAL_DIR / "w06_model_preflight_portable_schema_v2_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    amendment_disk = json.loads(
        (W06_EVAL_DIR / "w06_model_preflight_schema_portability_amendment_v1.json").read_text(
            encoding="utf-8"
        )
    )
    receipt_disk = json.loads(
        (W06_EVAL_DIR / "w06_model_preflight_01c_portable_schema_receipt_v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest_disk == build_portable_schema_v2_manifest(
        base_develop_sha=FROZEN_01C_BASE_DEVELOP_SHA
    )
    assert amendment_disk == amendment
    assert receipt_disk == receipt
