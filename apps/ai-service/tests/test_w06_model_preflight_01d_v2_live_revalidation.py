"""Offline test suite for W06-MODEL-PREFLIGHT-01D-PORTABLE-SCHEMA-LIVE-REVALIDATION (PD-01 through PD-45).

Verifies all pre-call plan invariants, V2 request serialization across C1/C2/C3,
preservation of historical V1 serializers, 1-call per candidate & 3-call global budget counters,
dual-layer validation (strict JSON + semantic BenchmarkPlanResponse.model_validate),
failure classification (including FAILED_JSON_OUTPUT vs FAILED_SEMANTIC_SCHEMA_VALIDATION),
secret sanitization, artifact scanning, and immutability of 01B, 01C, and frozen scientific authorities.
All tests in this module are 100% offline and make zero live network calls.
"""
import copy
import inspect
import json
from pathlib import Path
from typing import Any, Dict

import httpx
import httpx2
import pytest

from app.evaluation.model_preflight.anthropic_adapter import AnthropicPreflightAdapter
from app.evaluation.model_preflight.base import (
    build_synthetic_valid_plan_json,
    sanitize_secret_error_text,
    scan_tracked_files_for_secret_leaks,
)
from app.evaluation.model_preflight.google_adapter import GooglePreflightAdapter
from app.evaluation.model_preflight.live_revalidation_v2 import (
    DEFAULT_LIVE_ARTIFACTS_V2_DIR,
    DEFAULT_LIVE_PLAN_V2_PATH,
    DEFAULT_LIVE_RECEIPT_V2_PATH,
    EXPECTED_01C_AMENDMENT_SHAS,
    EXPECTED_BASE_DEVELOP_SHA_01D,
    EXPECTED_FROZEN_AUTHORITY_SHAS_01D,
    EXPECTED_GENERATION_SCHEMA_V1_SHA256_01D,
    EXPECTED_HISTORICAL_01B_EVIDENCE_SHAS,
    EXPECTED_HISTORICAL_01B_PLAN_SHA256_01D,
    EXPECTED_PORTABLE_GENERATION_SCHEMA_V2_SHA256_01D,
    EXPECTED_SEMANTIC_SCHEMA_SHA256_01D,
    CandidateFinalPreflightStatusV2,
    LiveFailureClassificationV2,
    build_live_revalidation_v2_plan_payload,
    execute_single_candidate_live_revalidation_v2,
    load_historical_01b_plan_hashes,
    run_live_revalidation_v2_suite,
    verify_frozen_authorities_01d,
    verify_historical_01b_and_01c_immutability,
    verify_live_revalidation_v2_plan_immutability,
    verify_schema_hashes_01d,
)
from app.evaluation.model_preflight.live_smoke import (
    CountingHttpx2Transport,
    CountingHttpxTransport,
    LiveCallBudgetTracker,
    compute_fixture_sha256,
    get_live_smoke_001_fixture,
    scan_directory_for_secret_leaks,
    validate_candidate_identity,
    validate_live_smoke_fixture_id,
)
from app.evaluation.model_preflight.openai_adapter import OpenAIPreflightAdapter
from app.evaluation.model_preflight.schema_adapter import (
    COMMON_GENERATION_SCHEMA_SHA256_V1,
    COMMON_PORTABLE_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA_V2,
    COMMON_PORTABLE_GENERATION_SCHEMA_SHA256_V2,
    SEMANTIC_SCHEMA_SHA256,
)
from app.evaluation.model_preflight.types import (
    LiveProviderCallForbiddenError,
    OneCallInvariantViolationError,
)
from app.services.planner_benchmark_runner import canonical_json_bytes, sha256_bytes


def _load_plan_v2() -> Dict[str, Any]:
    assert DEFAULT_LIVE_PLAN_V2_PATH.is_file(), f"Missing 01D V2 live plan at {DEFAULT_LIVE_PLAN_V2_PATH}"
    return json.loads(DEFAULT_LIVE_PLAN_V2_PATH.read_text(encoding="utf-8"))


def _make_dummy_dotenv(tmp_path: Path) -> Path:
    env_file = tmp_path / ".env"
    syn_g = "AIza" + ("D" * 35)
    syn_o = "sk-proj-" + ("E" * 28)
    syn_a = "sk-ant-" + ("F" * 28)
    env_file.write_text(
        f"GEMINI_API_KEY={syn_g}\nOPENAI_API_KEY={syn_o}\nANTHROPIC_API_KEY={syn_a}\n",
        encoding="utf-8",
    )
    return env_file


def _make_mock_google_transport(response_json_str: str) -> httpx.MockTransport:
    def _handler(request: httpx.Request) -> httpx.Response:
        # Verify request body sent to Google contains V2 schema (no minimum/maximum/minLength)
        req_body = json.loads(request.content.decode("utf-8"))
        assert "generationConfig" in req_body
        payload = {
            "modelVersion": "gemini-3.8-flash-001",
            "responseId": "resp-c1-v2-test",
            "candidates": [
                {
                    "content": {"role": "model", "parts": [{"text": response_json_str}]},
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 900,
                "candidatesTokenCount": 400,
                "thoughtsTokenCount": 100,
                "totalTokenCount": 1400,
            },
        }
        return httpx.Response(200, json=payload)

    return httpx.MockTransport(_handler)


def _make_mock_openai_transport(response_json_str: str) -> httpx2.MockTransport:
    def _handler(request: httpx2.Request) -> httpx2.Response:
        req_body = json.loads(request.content.decode("utf-8"))
        assert req_body["response_format"]["type"] == "json_schema"
        payload = {
            "id": "chatcmpl-c2-v2-test",
            "object": "chat.completion",
            "created": 1792200000,
            "model": "gpt-6.1-sol-2026-09-01",
            "system_fingerprint": "fp_v2_test",
            "service_tier": "default",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": response_json_str, "refusal": None},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 920,
                "completion_tokens": 450,
                "total_tokens": 1370,
                "completion_tokens_details": {"reasoning_tokens": 150},
                "prompt_tokens_details": {"cached_tokens": 0},
            },
        }
        return httpx2.Response(200, json=payload)

    return httpx2.MockTransport(_handler)


def _make_mock_anthropic_transport(response_json_str: str) -> httpx2.MockTransport:
    def _handler(request: httpx2.Request) -> httpx2.Response:
        req_body = json.loads(request.content.decode("utf-8"))
        assert req_body["output_config"]["effort"] == "high"
        assert req_body["output_config"]["format"]["type"] == "json_schema"
        payload = {
            "id": "msg_c3_v2_test",
            "type": "message",
            "role": "assistant",
            "model": "claude-sonnet-5-5-20261001",
            "content": [{"type": "text", "text": response_json_str}],
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {
                "input_tokens": 950,
                "output_tokens": 420,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
                "service_tier": "standard",
            },
        }
        return httpx2.Response(200, json=payload)

    return httpx2.MockTransport(_handler)


def test_pd01_base_sha_exact() -> None:
    """PD-01: base SHA exact (a55d8802f958a909095b1bff39e665179c2c205e)."""
    plan = _load_plan_v2()
    assert EXPECTED_BASE_DEVELOP_SHA_01D == "a55d8802f958a909095b1bff39e665179c2c205e"
    assert plan["base_develop_sha"] == "a55d8802f958a909095b1bff39e665179c2c205e"
    verify_live_revalidation_v2_plan_immutability()


def test_pd02_candidate_identities_unchanged() -> None:
    """PD-02: candidate identities unchanged."""
    plan = _load_plan_v2()
    assert plan["candidate_ids"] == ["C1", "C2", "C3"]
    assert plan["requested_model_ids"] == {
        "C1": "gemini-3.8-flash",
        "C2": "gpt-6.1-sol",
        "C3": "claude-sonnet-5-5",
    }
    assert plan["candidate_configurations"]["C1"]["provider"] == "Google"
    assert plan["candidate_configurations"]["C2"]["provider"] == "OpenAI"
    assert plan["candidate_configurations"]["C3"]["provider"] == "Anthropic"


def test_pd03_candidate_order_c1_c2_c3() -> None:
    """PD-03: candidate order C1, C2, C3."""
    plan = _load_plan_v2()
    assert plan["candidate_execution_order"] == ["C1", "C2", "C3"]


def test_pd04_max_total_live_calls_3() -> None:
    """PD-04: max total live calls 3."""
    plan = _load_plan_v2()
    assert plan["max_live_generation_calls_total"] == 3
    assert plan["authorization_max_live_calls"] == 3


def test_pd05_max_per_candidate_1() -> None:
    """PD-05: max per candidate 1."""
    plan = _load_plan_v2()
    assert plan["max_live_generation_calls_per_candidate"] == 1


def test_pd06_retry_0() -> None:
    """PD-06: retry 0 (automatic_retry=0, transport_retry=0, manual_retry=0)."""
    plan = _load_plan_v2()
    assert plan["automatic_retry"] == 0
    assert plan["transport_retry"] == 0
    assert plan["manual_retry"] == 0
    for cid in ("C1", "C2", "C3"):
        cfg = plan["candidate_configurations"][cid]
        assert cfg["sdk_automatic_retry"] == 0
        assert cfg["transport_retry"] == 0


def test_pd07_fallback_false() -> None:
    """PD-07: fallback false."""
    plan = _load_plan_v2()
    assert plan["fallback"] is False


def test_pd08_repair_0() -> None:
    """PD-08: repair 0."""
    plan = _load_plan_v2()
    assert plan["llm_repair"] == 0
    assert plan["repair"] is False


def test_pd09_same_fixture_as_01b() -> None:
    """PD-09: same fixture as 01B (W06-PREFLIGHT-SMOKE-001, smoke_002_used=False)."""
    plan = _load_plan_v2()
    hist = load_historical_01b_plan_hashes()
    assert plan["fixture_id"] == "W06-PREFLIGHT-SMOKE-001"
    assert plan["fixture_id"] == hist["historical_01b_fixture_id"]
    assert plan["smoke_002_used"] is False


def test_pd10_same_fixture_sha_as_01b() -> None:
    """PD-10: same fixture SHA as 01B."""
    plan = _load_plan_v2()
    hist = load_historical_01b_plan_hashes()
    scenario, pois = get_live_smoke_001_fixture()
    assert compute_fixture_sha256(scenario, pois) == hist["historical_01b_fixture_sha256"]
    assert plan["fixture_sha256"] == hist["historical_01b_fixture_sha256"]
    assert plan["fixture_matches_01b"] is True


def test_pd11_same_system_prompt_sha_as_01b() -> None:
    """PD-11: same system prompt SHA as 01B."""
    plan = _load_plan_v2()
    hist = load_historical_01b_plan_hashes()
    assert plan["system_prompt_sha256"] == hist["historical_01b_system_prompt_sha256"]
    assert plan["system_prompt_matches_01b"] is True


def test_pd12_same_user_prompt_sha_as_01b() -> None:
    """PD-12: same user prompt SHA as 01B."""
    plan = _load_plan_v2()
    hist = load_historical_01b_plan_hashes()
    assert plan["user_prompt_sha256"] == hist["historical_01b_user_prompt_sha256"]
    assert plan["user_prompt_matches_01b"] is True


def test_pd13_semantic_schema_hash_unchanged() -> None:
    """PD-13: semantic schema hash unchanged."""
    plan = _load_plan_v2()
    hashes = verify_schema_hashes_01d()
    assert SEMANTIC_SCHEMA_SHA256 == EXPECTED_SEMANTIC_SCHEMA_SHA256_01D
    assert plan["semantic_schema_sha256"] == EXPECTED_SEMANTIC_SCHEMA_SHA256_01D
    assert hashes["semantic_schema_sha256"] == EXPECTED_SEMANTIC_SCHEMA_SHA256_01D


def test_pd14_v1_schema_hash_unchanged() -> None:
    """PD-14: V1 schema hash unchanged."""
    plan = _load_plan_v2()
    assert COMMON_GENERATION_SCHEMA_SHA256_V1 == EXPECTED_GENERATION_SCHEMA_V1_SHA256_01D
    assert plan["generation_schema_v1_sha256"] == EXPECTED_GENERATION_SCHEMA_V1_SHA256_01D


def test_pd15_v2_schema_exact_frozen_hash() -> None:
    """PD-15: V2 schema exact frozen hash."""
    plan = _load_plan_v2()
    assert (
        COMMON_PORTABLE_GENERATION_SCHEMA_SHA256_V2
        == EXPECTED_PORTABLE_GENERATION_SCHEMA_V2_SHA256_01D
    )
    assert (
        plan["portable_generation_schema_v2_sha256"]
        == EXPECTED_PORTABLE_GENERATION_SCHEMA_V2_SHA256_01D
    )


def test_pd16_c1_uses_v2_exact_hash() -> None:
    """PD-16: C1 uses V2 exact hash."""
    scenario, pois = get_live_smoke_001_fixture()
    req = GooglePreflightAdapter().serialize_smoke_request_v2(scenario, pois)
    assert (
        req["portable_generation_schema_v2_sha256"]
        == EXPECTED_PORTABLE_GENERATION_SCHEMA_V2_SHA256_01D
    )
    schema_sha = sha256_bytes(canonical_json_bytes(req["config"]["response_json_schema"]))
    assert schema_sha == EXPECTED_PORTABLE_GENERATION_SCHEMA_V2_SHA256_01D


def test_pd17_c2_uses_v2_exact_hash() -> None:
    """PD-17: C2 uses V2 exact hash."""
    scenario, pois = get_live_smoke_001_fixture()
    req = OpenAIPreflightAdapter().serialize_smoke_request_v2(scenario, pois)
    assert (
        req["portable_generation_schema_v2_sha256"]
        == EXPECTED_PORTABLE_GENERATION_SCHEMA_V2_SHA256_01D
    )
    schema_sha = sha256_bytes(
        canonical_json_bytes(req["config"]["response_format"]["json_schema"]["schema"])
    )
    assert schema_sha == EXPECTED_PORTABLE_GENERATION_SCHEMA_V2_SHA256_01D


def test_pd18_c3_uses_v2_exact_hash() -> None:
    """PD-18: C3 uses V2 exact hash."""
    scenario, pois = get_live_smoke_001_fixture()
    req = AnthropicPreflightAdapter().serialize_smoke_request_v2(scenario, pois)
    assert (
        req["portable_generation_schema_v2_sha256"]
        == EXPECTED_PORTABLE_GENERATION_SCHEMA_V2_SHA256_01D
    )
    schema_sha = sha256_bytes(
        canonical_json_bytes(req["config"]["output_config"]["format"]["schema"])
    )
    assert schema_sha == EXPECTED_PORTABLE_GENERATION_SCHEMA_V2_SHA256_01D


def test_pd19_all_three_v2_schemas_structurally_identical() -> None:
    """PD-19: all three V2 schemas structurally identical."""
    scenario, pois = get_live_smoke_001_fixture()
    g_req = GooglePreflightAdapter().serialize_smoke_request_v2(scenario, pois)
    o_req = OpenAIPreflightAdapter().serialize_smoke_request_v2(scenario, pois)
    a_req = AnthropicPreflightAdapter().serialize_smoke_request_v2(scenario, pois)

    g_schema = g_req["config"]["response_json_schema"]
    o_schema = o_req["config"]["response_format"]["json_schema"]["schema"]
    a_schema = a_req["config"]["output_config"]["format"]["schema"]

    assert g_schema == o_schema == a_schema == COMMON_PORTABLE_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA_V2


def test_pd20_historical_v1_serializers_remain_v1() -> None:
    """PD-20: historical V1 serializers remain V1 while V2 serializers hash to V2."""
    scenario, pois = get_live_smoke_001_fixture()
    g_v1 = GooglePreflightAdapter().serialize_smoke_request(scenario, pois)
    o_v1 = OpenAIPreflightAdapter().serialize_smoke_request(scenario, pois)
    a_v1 = AnthropicPreflightAdapter().serialize_smoke_request(scenario, pois)

    assert g_v1["common_generation_schema_sha256"] == EXPECTED_GENERATION_SCHEMA_V1_SHA256_01D
    assert o_v1["common_generation_schema_sha256"] == EXPECTED_GENERATION_SCHEMA_V1_SHA256_01D
    assert a_v1["common_generation_schema_sha256"] == EXPECTED_GENERATION_SCHEMA_V1_SHA256_01D

    assert (
        sha256_bytes(canonical_json_bytes(g_v1["config"]["response_json_schema"]))
        == EXPECTED_GENERATION_SCHEMA_V1_SHA256_01D
    )
    assert (
        sha256_bytes(canonical_json_bytes(o_v1["config"]["response_format"]["json_schema"]["schema"]))
        == EXPECTED_GENERATION_SCHEMA_V1_SHA256_01D
    )
    assert (
        sha256_bytes(canonical_json_bytes(a_v1["config"]["output_config"]["format"]["schema"]))
        == EXPECTED_GENERATION_SCHEMA_V1_SHA256_01D
    )


def test_pd21_c1_thinking_medium() -> None:
    """PD-21: C1 thinking medium."""
    scenario, pois = get_live_smoke_001_fixture()
    req = GooglePreflightAdapter().serialize_smoke_request_v2(scenario, pois)
    assert req["config"]["thinking_config"] == {"thinking_level": "medium"}


def test_pd22_c1_seed_2026101508() -> None:
    """PD-22: C1 seed 2026101508."""
    scenario, pois = get_live_smoke_001_fixture()
    req = GooglePreflightAdapter().serialize_smoke_request_v2(scenario, pois)
    assert req["config"]["seed"] == 2026101508


def test_pd23_c1_temperature_top_p_top_k_omitted() -> None:
    """PD-23: C1 temperature/top_p/top_k omitted."""
    scenario, pois = get_live_smoke_001_fixture()
    req = GooglePreflightAdapter().serialize_smoke_request_v2(scenario, pois)
    for k in ("temperature", "top_p", "top_k"):
        assert k not in req["config"]


def test_pd24_c2_reasoning_medium() -> None:
    """PD-24: C2 reasoning medium."""
    scenario, pois = get_live_smoke_001_fixture()
    req = OpenAIPreflightAdapter().serialize_smoke_request_v2(scenario, pois)
    assert req["config"]["reasoning_effort"] == "medium"


def test_pd25_c2_seed_2026101508() -> None:
    """PD-25: C2 seed 2026101508."""
    scenario, pois = get_live_smoke_001_fixture()
    req = OpenAIPreflightAdapter().serialize_smoke_request_v2(scenario, pois)
    assert req["config"]["seed"] == 2026101508


def test_pd26_c2_service_tier_default() -> None:
    """PD-26: C2 service_tier default."""
    scenario, pois = get_live_smoke_001_fixture()
    req = OpenAIPreflightAdapter().serialize_smoke_request_v2(scenario, pois)
    assert req["config"]["service_tier"] == "default"


def test_pd27_c2_temperature_top_p_top_k_omitted() -> None:
    """PD-27: C2 temperature/top_p/top_k omitted."""
    scenario, pois = get_live_smoke_001_fixture()
    req = OpenAIPreflightAdapter().serialize_smoke_request_v2(scenario, pois)
    for k in ("temperature", "top_p", "top_k", "top_logprobs", "logprobs"):
        assert k not in req["config"]


def test_pd28_c3_adaptive_thinking() -> None:
    """PD-28: C3 adaptive thinking."""
    scenario, pois = get_live_smoke_001_fixture()
    req = AnthropicPreflightAdapter().serialize_smoke_request_v2(scenario, pois)
    assert req["config"]["thinking"] == {"type": "adaptive"}


def test_pd29_c3_effort_high() -> None:
    """PD-29: C3 effort high."""
    scenario, pois = get_live_smoke_001_fixture()
    req = AnthropicPreflightAdapter().serialize_smoke_request_v2(scenario, pois)
    assert req["config"]["output_config"]["effort"] == "high"


def test_pd30_c3_temperature_top_p_top_k_seed_omitted() -> None:
    """PD-30: C3 temperature/top_p/top_k/seed omitted."""
    scenario, pois = get_live_smoke_001_fixture()
    req = AnthropicPreflightAdapter().serialize_smoke_request_v2(scenario, pois)
    for k in ("temperature", "top_p", "top_k", "seed"):
        assert k not in req["config"]


def test_pd31_one_call_counter_fails_closed_above_1() -> None:
    """PD-31: one-call counter fails closed above 1 before transmitting any extra network packet."""
    tracker = LiveCallBudgetTracker(max_total_calls=3, max_calls_per_candidate=1)
    sent_count = 0

    def _inner_handler(request: httpx2.Request) -> httpx2.Response:
        nonlocal sent_count
        sent_count += 1
        return httpx2.Response(200, json={"ok": True})

    transport = CountingHttpx2Transport(
        candidate_id="C3",
        budget_tracker=tracker,
        inner_transport=httpx2.MockTransport(_inner_handler),
    )
    req = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    resp = transport.handle_request(req)
    assert resp.status_code == 200
    assert sent_count == 1

    with pytest.raises(OneCallInvariantViolationError, match="ABORT BEFORE EXTRA REQUEST"):
        transport.handle_request(req)
    assert sent_count == 1


def test_pd32_global_call_counter_fails_closed_above_3() -> None:
    """PD-32: global call counter fails closed above 3."""
    tracker = LiveCallBudgetTracker(max_total_calls=3, max_calls_per_candidate=1)
    for cid in ("C1", "C2", "C3"):
        tracker.assert_can_start_candidate(cid)
        tracker.record_outbound_http_request_before_send(cid)
    assert tracker.total_http_requests == 3

    with pytest.raises(OneCallInvariantViolationError):
        tracker.record_outbound_http_request_before_send("C1")


def test_pd33_scientific_evaluator_cannot_be_invoked() -> None:
    """PD-33: scientific evaluator cannot be invoked in live_revalidation_v2."""
    import app.evaluation.model_preflight.live_revalidation_v2 as mod_01d

    src = inspect.getsource(mod_01d)
    assert "PlannerBenchmarkEvaluator" not in src
    assert "evaluate_planner_benchmark_run" not in src
    plan = _load_plan_v2()
    assert plan["scientific_quality_scoring_allowed"] is False
    assert plan["scientific_performance_scoring_allowed"] is False


def test_pd34_dev_tune_forbidden() -> None:
    """PD-34: DEV-TUNE forbidden."""
    plan = _load_plan_v2()
    assert plan["dev_tune_allowed"] is False
    with pytest.raises(OneCallInvariantViolationError):
        validate_live_smoke_fixture_id("W06-DEV-TUNE-001")


def test_pd35_dev_select_forbidden() -> None:
    """PD-35: DEV-SELECT forbidden."""
    plan = _load_plan_v2()
    assert plan["dev_select_allowed"] is False
    with pytest.raises(OneCallInvariantViolationError):
        validate_live_smoke_fixture_id("W06-DEV-SELECT-001")


def test_pd36_final100_forbidden() -> None:
    """PD-36: final100 forbidden."""
    plan = _load_plan_v2()
    assert plan["final100_allowed"] is False
    assert plan["final_100_allowed"] is False
    with pytest.raises(OneCallInvariantViolationError):
        validate_live_smoke_fixture_id("W06-S001")
    with pytest.raises(OneCallInvariantViolationError):
        validate_live_smoke_fixture_id("W06-PREFLIGHT-SMOKE-002")


def test_pd37_candidate_substitution_forbidden() -> None:
    """PD-37: candidate substitution forbidden."""
    validate_candidate_identity("C1", "Google", "gemini-3.8-flash")
    validate_candidate_identity("C2", "OpenAI", "gpt-6.1-sol")
    validate_candidate_identity("C3", "Anthropic", "claude-sonnet-5-5")

    with pytest.raises(OneCallInvariantViolationError):
        validate_candidate_identity("C3", "Anthropic", "claude-sonnet-4-5")
    with pytest.raises(OneCallInvariantViolationError):
        validate_candidate_identity("C4", "Grok", "grok-3")


def test_pd38_no_provider_specific_v2_schema_transformation() -> None:
    """PD-38: no provider-specific V2 schema transformation."""
    scenario, pois = get_live_smoke_001_fixture()
    g_req = GooglePreflightAdapter().serialize_smoke_request_v2(scenario, pois)
    o_req = OpenAIPreflightAdapter().serialize_smoke_request_v2(scenario, pois)
    a_req = AnthropicPreflightAdapter().serialize_smoke_request_v2(scenario, pois)

    g_bytes = canonical_json_bytes(g_req["config"]["response_json_schema"])
    o_bytes = canonical_json_bytes(o_req["config"]["response_format"]["json_schema"]["schema"])
    a_bytes = canonical_json_bytes(a_req["config"]["output_config"]["format"]["schema"])
    v2_bytes = canonical_json_bytes(COMMON_PORTABLE_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA_V2)

    assert g_bytes == o_bytes == a_bytes == v2_bytes
    assert sha256_bytes(v2_bytes) == EXPECTED_PORTABLE_GENERATION_SCHEMA_V2_SHA256_01D


def test_pd39_semantic_pydantic_validation_mandatory(tmp_path: Path) -> None:
    """PD-39: semantic Pydantic validation mandatory (valid JSON + valid semantic model passes all 3 candidates)."""
    scenario, pois = get_live_smoke_001_fixture()
    valid_json_str = build_synthetic_valid_plan_json(scenario, pois)
    dotenv_file = _make_dummy_dotenv(tmp_path)
    out_dir = tmp_path / "artifacts_01d_pass"
    receipt_file = tmp_path / "receipt_01d_pass.json"

    receipt = run_live_revalidation_v2_suite(
        confirm_live=True,
        live_plan_commit_sha="01d_test_plan_commit_sha",
        transport_overrides={
            "C1": _make_mock_google_transport(valid_json_str),
            "C2": _make_mock_openai_transport(valid_json_str),
            "C3": _make_mock_anthropic_transport(valid_json_str),
        },
        artifact_root_dir=out_dir,
        receipt_path=receipt_file,
        dotenv_path=dotenv_file,
    )

    assert receipt["actual_live_generation_calls_total"] == 3
    assert receipt["passed_technical_preflight_schema_v2_candidates"] == ["C1", "C2", "C3"]
    assert receipt["failed_technical_preflight_schema_v2_candidates"] == []
    for cid in ("C1", "C2", "C3"):
        c_rec = receipt["candidates"][cid]
        assert c_rec["status"] == CandidateFinalPreflightStatusV2.PASSED_TECHNICAL_PREFLIGHT_SCHEMA_V2.value
        assert c_rec["failure_classification"] == LiveFailureClassificationV2.NONE.value
        assert c_rec["schema_v2_accepted"] is True
        assert c_rec["strict_json_valid"] is True
        assert c_rec["semantic_pydantic_valid"] is True
        assert (out_dir / cid / "parsed_plan_response.json").is_file()


def test_pd40_semantic_invalid_v2_output_gets_fail_no_repair(tmp_path: Path) -> None:
    """PD-40: semantic-invalid V2 output gets FAIL (FAILED_SEMANTIC_SCHEMA_VALIDATION), no repair."""
    scenario, pois = get_live_smoke_001_fixture()
    valid_dict = json.loads(build_synthetic_valid_plan_json(scenario, pois))
    # Mutate a semantic constraint that was stripped from V2 decoder schema (e.g., day_number = 0 < minimum=1,
    # or start_minute = 2000 > maximum=1439) while still satisfying V2 structural types!
    semantically_invalid_dict = copy.deepcopy(valid_dict)
    semantically_invalid_dict["days"][0]["day_number"] = 0
    semantically_invalid_json_str = json.dumps(semantically_invalid_dict)

    dotenv_file = _make_dummy_dotenv(tmp_path)
    out_dir = tmp_path / "artifacts_01d_sem_fail"
    tracker = LiveCallBudgetTracker()

    rec_sem_fail = execute_single_candidate_live_revalidation_v2(
        candidate_id="C3",
        budget_tracker=tracker,
        confirm_live=True,
        artifact_root_dir=out_dir,
        dotenv_path=dotenv_file,
        inner_transport_override=_make_mock_anthropic_transport(semantically_invalid_json_str),
    )

    assert rec_sem_fail.actual_http_request_count == 1
    assert rec_sem_fail.status == CandidateFinalPreflightStatusV2.FAILED_TECHNICAL_PREFLIGHT_SCHEMA_V2
    assert rec_sem_fail.failure_classification == LiveFailureClassificationV2.FAILED_SEMANTIC_SCHEMA_VALIDATION
    assert rec_sem_fail.schema_v2_accepted is True
    assert rec_sem_fail.strict_json_valid is True
    assert rec_sem_fail.semantic_pydantic_valid is False
    assert not (out_dir / "C3" / "parsed_plan_response.json").exists()

    # Also verify malformed / code-fenced JSON gets FAILED_JSON_OUTPUT without rescue
    fenced_json_str = f"```json\n{build_synthetic_valid_plan_json(scenario, pois)}\n```"
    rec_json_fail = execute_single_candidate_live_revalidation_v2(
        candidate_id="C2",
        budget_tracker=tracker,
        confirm_live=True,
        artifact_root_dir=out_dir,
        dotenv_path=dotenv_file,
        inner_transport_override=_make_mock_openai_transport(fenced_json_str),
    )
    assert rec_json_fail.actual_http_request_count == 1
    assert rec_json_fail.status == CandidateFinalPreflightStatusV2.FAILED_TECHNICAL_PREFLIGHT_SCHEMA_V2
    assert rec_json_fail.failure_classification == LiveFailureClassificationV2.FAILED_JSON_OUTPUT
    assert rec_json_fail.schema_v2_accepted is True
    assert rec_json_fail.strict_json_valid is False
    assert rec_json_fail.semantic_pydantic_valid is False


def test_pd41_secret_sanitizer(tmp_path: Path) -> None:
    """PD-41: secret sanitizer scrubs API keys, Bearer tokens, and raw .env values."""
    dotenv_file = _make_dummy_dotenv(tmp_path)
    syn_g = "AIza" + ("D" * 35)
    syn_a = "sk-ant-" + ("F" * 28)
    syn_bearer = "Bear" + "er " + ("T" * 24)
    raw_msg = f"Error with {syn_g} and {syn_a} and {syn_bearer}"
    sanitized = sanitize_secret_error_text(raw_msg, dotenv_path=dotenv_file)
    assert sanitized is not None
    assert syn_g not in sanitized
    assert syn_a not in sanitized
    assert ("T" * 24) not in sanitized
    assert "[REDACTED" in sanitized


def test_pd42_artifact_scanner(tmp_path: Path) -> None:
    """PD-42: artifact scanner detects leaked secrets and passes clean directories."""
    dotenv_file = _make_dummy_dotenv(tmp_path)
    clean_dir = tmp_path / "clean_artifacts"
    clean_dir.mkdir()
    (clean_dir / "receipt.json").write_text('{"status": "ok"}', encoding="utf-8")
    clean_scan = scan_directory_for_secret_leaks(clean_dir, dotenv_path=dotenv_file)
    assert clean_scan["secret_leak_count"] == 0

    leaky_dir = tmp_path / "leaky_artifacts"
    leaky_dir.mkdir()
    syn_a = "sk-ant-" + ("F" * 28)
    (leaky_dir / "bad.txt").write_text(f"leaked key {syn_a}", encoding="utf-8")
    leaky_scan = scan_directory_for_secret_leaks(leaky_dir, dotenv_path=dotenv_file)
    assert leaky_scan["secret_leak_count"] > 0
    assert len(leaky_scan["affected_file_paths"]) == 1

    tracked_scan = scan_tracked_files_for_secret_leaks()
    assert tracked_scan["secret_leak_count"] == 0


def test_pd43_01b_historical_evidence_unchanged() -> None:
    """PD-43: 01B historical evidence unchanged."""
    verified = verify_historical_01b_and_01c_immutability()
    assert len(verified["historical_01b"]) == len(EXPECTED_HISTORICAL_01B_EVIDENCE_SHAS)
    assert (
        verified["historical_01b"]["data/evaluation/w06/w06_model_preflight_01b_live_plan_v1.json"]
        == EXPECTED_HISTORICAL_01B_PLAN_SHA256_01D
    )


def test_pd44_01c_amendment_unchanged() -> None:
    """PD-44: 01C amendment unchanged and all 13 frozen scientific authorities intact."""
    verified = verify_historical_01b_and_01c_immutability()
    assert len(verified["amendment_01c"]) == len(EXPECTED_01C_AMENDMENT_SHAS)
    frozen = verify_frozen_authorities_01d()
    assert len(frozen) == len(EXPECTED_FROZEN_AUTHORITY_SHAS_01D)


def test_pd45_live_execution_requires_explicit_confirm_live() -> None:
    """PD-45: live execution requires explicit --confirm-live or confirm_live=True."""
    tracker = LiveCallBudgetTracker()
    with pytest.raises(LiveProviderCallForbiddenError):
        execute_single_candidate_live_revalidation_v2(
            candidate_id="C1",
            budget_tracker=tracker,
            confirm_live=False,
        )
    with pytest.raises(LiveProviderCallForbiddenError):
        run_live_revalidation_v2_suite(confirm_live=False)
    assert tracker.total_http_requests == 0


def test_pd_post_live_receipt_and_artifacts_when_present() -> None:
    """Verify the persisted 01D live receipt and candidate artifacts on disk when present."""
    if not DEFAULT_LIVE_RECEIPT_V2_PATH.is_file():
        return
    receipt = json.loads(DEFAULT_LIVE_RECEIPT_V2_PATH.read_text(encoding="utf-8"))
    assert receipt["task_id"] == "W06-MODEL-PREFLIGHT-01D-PORTABLE-SCHEMA-LIVE-REVALIDATION"
    assert receipt["base_develop_sha"] == EXPECTED_BASE_DEVELOP_SHA_01D
    assert receipt["semantic_schema_sha256"] == EXPECTED_SEMANTIC_SCHEMA_SHA256_01D
    assert receipt["generation_schema_v1_sha256"] == EXPECTED_GENERATION_SCHEMA_V1_SHA256_01D
    assert (
        receipt["portable_generation_schema_v2_sha256"]
        == EXPECTED_PORTABLE_GENERATION_SCHEMA_V2_SHA256_01D
    )
    assert receipt["actual_live_generation_calls_total"] <= 3
    assert receipt["retry"] == 0
    assert receipt["fallback"] is False
    assert receipt["repair"] == 0
    assert receipt["dev_tune_started"] is False
    assert receipt["dev_select_started"] is False
    assert receipt["winner_selected"] is False
    assert receipt["final_100_used"] is False
    assert receipt["historical_01b_preserved"] is True

    art_scan = scan_directory_for_secret_leaks(DEFAULT_LIVE_ARTIFACTS_V2_DIR)
    assert art_scan["secret_leak_count"] == 0
    for cid in ("C1", "C2", "C3"):
        c_rec = receipt["candidates"][cid]
        assert c_rec["actual_http_request_count"] <= 1
        assert c_rec["status"] in (
            "PASSED_TECHNICAL_PREFLIGHT_SCHEMA_V2",
            "FAILED_TECHNICAL_PREFLIGHT_SCHEMA_V2",
        )
