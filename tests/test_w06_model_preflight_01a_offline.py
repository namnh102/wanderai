"""Offline verification test suite for W06-MODEL-PREFLIGHT-01A-OFFLINE (PF-A-01 .. PF-A-30).

ABSOLUTELY NO LIVE MODEL/API REQUESTS ARE MADE IN THIS TEST SUITE.
All SDK calls use offline fake transports (httpx.MockTransport / httpx2.MockTransport).
"""
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable, Tuple

import httpx
import httpx2
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
AI_SERVICE_ROOT = REPO_ROOT / "apps" / "ai-service"
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))

from app.config import Settings, settings  # noqa: E402
from app.evaluation.model_preflight import (  # noqa: E402
    COMMON_BENCHMARK_PLAN_JSON_SCHEMA,
    COMMON_SCHEMA_SHA256,
    FROZEN_ARCHITECTURE_ID,
    FROZEN_MAX_OUTPUT_TOKENS,
    FROZEN_SAMPLING_SEED,
    FROZEN_SAMPLING_TEMPERATURE,
    FROZEN_TIMEOUT_MS,
    LIVE_PROVIDER_CALL_FORBIDDEN_CODE,
    SYNTHETIC_SMOKE_SCENARIO_IDS,
    AnthropicPreflightAdapter,
    CapabilityVerificationStatus,
    ConfigurationIntegrityError,
    GooglePreflightAdapter,
    LiveProviderCallForbiddenError,
    OneCallInvariantViolationError,
    OpenAIPreflightAdapter,
    PreflightFailureClassification,
    build_all_candidate_preflight_adapters,
    build_anthropic_structured_output_wiring,
    build_google_structured_output_wiring,
    build_openai_structured_output_wiring,
    build_synthetic_smoke_fixtures,
    build_synthetic_valid_plan_json,
    check_dotenv_key_presence,
    compute_common_schema_sha256,
    run_readonly_opening_hours_catalog_audit,
    scan_tracked_files_for_secret_leaks,
    schema_encodes_place_id_as_catalog_enum,
)
from app.schemas.planner_benchmark import BenchmarkRunStatus  # noqa: E402
from app.services.planner_benchmark_runner import (  # noqa: E402
    canonical_json_bytes,
    normalize_lf_bytes,
    sha256_bytes,
)

RECEIPT_PATH = REPO_ROOT / "data" / "evaluation" / "w06" / "w06_model_preflight_01a_offline_receipt_v1.json"
DOC_PATH = REPO_ROOT / "docs" / "research" / "w06_model_preflight_01a_offline_v1.md"
LOCK_PATH = AI_SERVICE_ROOT / "requirements-w06-provider-lock.txt"

EXPECTED_FROZEN_AUTHORITY_SHAS = {
    "data/evaluation/w06/w06_scenarios_freeze_v1.json": "c03bc6dc300604ac395505d59b6413c1a47339b21408cfd637671e81d4b555a1",
    "data/evaluation/w06/w06_p11_assignment_manifest_v1.json": "0aa9ae923d0e7f29df49735fa41e87530b1caf62418fcbec09a1eff81d83af62",
    "data/evaluation/w06/w06_model_arch_selection_method_lock_v1.json": "6f30cdf90355dd720795de8e0b21beba45f527767892ca7eb88769141a64210c",
    "data/evaluation/w06/w06_scenario_method_lock_v1.json": "5e5359f9f10a0248a9cf031f8e8b26c0314c46aecfe0d9df479388bbe4fd1af9",
    "data/evaluation/w06/w06_scenario_support_matrix_v1.json": "68c2bfc2164e664b3856c31b99a92d75a588f64465526b47c9104918a51cedb4",
    "data/evaluation/w06/w06_measurement_contract_v1.json": "0ddc1f8d879493517cee25f247d2365a0bacb816dc33b129b0c6110d4bfb8298",
    "apps/ai-service/app/evaluation/planner_scenario_generator.py": "623c52cbdd98d181cd9cbbc1e68697a7299cb6c864628e97e743afd9e09ceae1",
    "scripts/audit_w06_scenario_generator_dryrun.py": "2e5a218fc49d4af0052dffa49c14a8a7d5d9818847fd6d37f647422a9cadc6fc",
    "data/curated/gomate_places_freeze_v2.json": "f7517938598e3923906763f8f31334a500ee88bc06232f2992d38e2fcb28a444",
    "apps/ai-service/recommendation/reca/contract.py": "1a62c36a95092be35ab78dca43e20f646016e154746ee051a499bdebfc67538c",
    "data/evaluation/w06/w06_dev_fixtures_freeze_v1.json": "bb0f051446ea3da8229298f22f4ce92b4db20751695273c6d01b7766da044050",
    "data/evaluation/w06/w06_dev_fixture_manifest_v1.json": "15cf3af6c93d3de967703dbc52d7e082bfd4a1e657409c0678ff51bd081e3c98",
    "data/evaluation/w06/w06_dev_final_overlap_receipt_v1.json": "285699ee1370b537a6579b88a7fb02781b51ac52e0ed14f469d77969261f04aa",
    "data/evaluation/w06/w06_dev_fixture_freeze_01_receipt_v1.json": "437a296cf123d1469f303b97cb6665cd8217c2dfeabd12d1712ec2789d890026",
}


def _make_google_transport(
    status_code: int = 200,
    body_json: dict[str, Any] | None = None,
    raise_timeout: bool = False,
) -> Tuple[httpx.MockTransport, Callable[[], int]]:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if raise_timeout:
            raise httpx.ReadTimeout("Simulated Google transport timeout", request=request)
        return httpx.Response(status_code=status_code, json=body_json or {})

    return httpx.MockTransport(handler), lambda: calls


def _make_httpx2_transport(
    status_code: int = 200,
    body_json: dict[str, Any] | None = None,
    raise_timeout: bool = False,
) -> Tuple[httpx2.MockTransport, Callable[[], int]]:
    calls = 0

    def handler(request: httpx2.Request) -> httpx2.Response:
        nonlocal calls
        calls += 1
        if raise_timeout:
            raise httpx2.ReadTimeout("Simulated httpx2 transport timeout", request=request)
        return httpx2.Response(status_code=status_code, json=body_json or {})

    return httpx2.MockTransport(handler), lambda: calls


def test_pf_a_01_config_has_anthropic_api_key_and_preserves_planner_model() -> None:
    """PF-A-01: Settings defines ANTHROPIC_API_KEY: str = '' and preserves PLANNER_MODEL default."""
    assert "ANTHROPIC_API_KEY" in Settings.model_fields
    assert Settings.model_fields["ANTHROPIC_API_KEY"].default == ""
    assert settings.PLANNER_MODEL == "gemini-3.5-flash"


def test_pf_a_02_dependency_lock_file_exists_and_pins_required_packages() -> None:
    """PF-A-02: requirements-w06-provider-lock.txt exists and pins exact provider and transport packages."""
    assert LOCK_PATH.is_file()
    content = LOCK_PATH.read_text(encoding="utf-8")
    for required_pin in (
        "google-genai==2.25.0",
        "openai==3.17.0",
        "anthropic==1.15.0",
        "httpx==0.28.1",
        "httpcore==1.0.9",
        "pydantic==2.13.4",
        "pydantic-core==2.46.4",
        "anyio==4.13.0",
    ):
        assert required_pin in content


def test_pf_a_03_provider_sdks_are_importable() -> None:
    """PF-A-03: google-genai, openai, and anthropic SDKs are importable."""
    from importlib.metadata import version

    import anthropic
    from google import genai
    import openai

    assert genai is not None
    assert openai is not None
    assert anthropic is not None
    assert version("google-genai") == "2.25.0"
    assert version("openai") == "3.17.0"
    assert version("anthropic") == "1.15.0"


def test_pf_a_04_model_preflight_package_structure() -> None:
    """PF-A-04: apps/ai-service/app/evaluation/model_preflight contains all 7 required modules."""
    pkg_dir = AI_SERVICE_ROOT / "app" / "evaluation" / "model_preflight"
    for fname in (
        "__init__.py",
        "types.py",
        "schema_adapter.py",
        "base.py",
        "google_adapter.py",
        "openai_adapter.py",
        "anthropic_adapter.py",
    ):
        assert (pkg_dir / fname).is_file(), f"Missing {fname}"


def test_pf_a_05_runtime_live_call_guard_blocks_live_execution_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """PF-A-05: Attempting execution without an offline mock_transport while W06_PREFLIGHT_LIVE_ALLOWED=false raises LIVE_PROVIDER_CALL_FORBIDDEN."""
    monkeypatch.delenv("W06_PREFLIGHT_LIVE_ALLOWED", raising=False)
    smoke_scenario, smoke_pois = build_synthetic_smoke_fixtures()[0]
    for adapter in build_all_candidate_preflight_adapters().values():
        with pytest.raises(LiveProviderCallForbiddenError) as exc_info:
            adapter.execute_offline_simulated_request(
                scenario=smoke_scenario,
                catalog_pois=smoke_pois,
                mock_transport=None,
                request_counter=lambda: 0,
            )
        assert exc_info.value.code == LIVE_PROVIDER_CALL_FORBIDDEN_CODE
        assert LIVE_PROVIDER_CALL_FORBIDDEN_CODE in str(exc_info.value)


def test_pf_a_06_common_schema_deterministic_hash() -> None:
    """PF-A-06: Common BenchmarkPlanResponse JSON schema hash is deterministic under SHA256_CANONICAL_JSON_UTF8_LF_BYTES."""
    assert len(COMMON_SCHEMA_SHA256) == 64
    assert compute_common_schema_sha256() == COMMON_SCHEMA_SHA256
    assert COMMON_BENCHMARK_PLAN_JSON_SCHEMA.get("type") == "object"
    assert COMMON_BENCHMARK_PLAN_JSON_SCHEMA.get("additionalProperties") is False


def test_pf_a_07_place_id_not_encoded_as_catalog_enum() -> None:
    """PF-A-07: place_id is never constrained to an enum of catalog IDs in the schema."""
    assert schema_encodes_place_id_as_catalog_enum(COMMON_BENCHMARK_PLAN_JSON_SCHEMA) is False
    # Verify detector catches an artificial enum on place_id
    mutated = {"properties": {"place_id": {"type": "string", "enum": ["p1", "p2"]}}}
    assert schema_encodes_place_id_as_catalog_enum(mutated) is True


def test_pf_a_08_identical_semantic_prompts_and_schema_across_c1_c2_c3() -> None:
    """PF-A-08: C1, C2, and C3 serialize identical semantic system/user prompts and share COMMON_SCHEMA_SHA256."""
    adapters = build_all_candidate_preflight_adapters()
    for scenario, pois in build_synthetic_smoke_fixtures():
        r1 = adapters["C1"].serialize_smoke_request(scenario, pois)
        r2 = adapters["C2"].serialize_smoke_request(scenario, pois)
        r3 = adapters["C3"].serialize_smoke_request(scenario, pois)
        assert r1["system_prompt"] == r2["system_prompt"] == r3["system_prompt"]
        assert r1["user_prompt"] == r2["user_prompt"] == r3["user_prompt"]
        assert r1["system_prompt_sha256"] == r2["system_prompt_sha256"] == r3["system_prompt_sha256"]
        assert r1["user_prompt_sha256"] == r2["user_prompt_sha256"] == r3["user_prompt_sha256"]
        assert r1["common_schema_sha256"] == r2["common_schema_sha256"] == r3["common_schema_sha256"] == COMMON_SCHEMA_SHA256


def test_pf_a_09_provider_structured_output_wiring() -> None:
    """PF-A-09: Provider structured-output wiring builders translate only technical parameters."""
    g_wire = build_google_structured_output_wiring()
    assert g_wire["response_mime_type"] == "application/json"
    assert g_wire["common_schema_sha256"] == COMMON_SCHEMA_SHA256

    o_wire = build_openai_structured_output_wiring()
    assert o_wire["response_format"]["type"] == "json_schema"
    assert o_wire["response_format"]["json_schema"]["strict"] is True
    assert o_wire["common_schema_sha256"] == COMMON_SCHEMA_SHA256

    a_wire = build_anthropic_structured_output_wiring()
    assert a_wire["output_config"]["format"]["type"] == "json_schema"
    assert a_wire["common_schema_sha256"] == COMMON_SCHEMA_SHA256


def test_pf_a_10_one_call_invariant_rejects_multi_call_tool_repair_or_fallback() -> None:
    """PF-A-10: Base adapter rejects >1 LLM call, tool calls, repair calls, or fallback."""
    adapter = GooglePreflightAdapter()
    scenario, pois = build_synthetic_smoke_fixtures()[0]
    transport, counter = _make_google_transport()

    with pytest.raises(OneCallInvariantViolationError):
        adapter.execute_offline_simulated_request(
            scenario=scenario,
            catalog_pois=pois,
            mock_transport=transport,
            request_counter=counter,
            simulated_call_count=2,
        )
    with pytest.raises(OneCallInvariantViolationError):
        adapter.execute_offline_simulated_request(
            scenario=scenario,
            catalog_pois=pois,
            mock_transport=transport,
            request_counter=counter,
            simulated_tool_calls=1,
        )
    with pytest.raises(OneCallInvariantViolationError):
        adapter.execute_offline_simulated_request(
            scenario=scenario,
            catalog_pois=pois,
            mock_transport=transport,
            request_counter=counter,
            simulated_repair_calls=1,
        )
    with pytest.raises(OneCallInvariantViolationError):
        adapter.execute_offline_simulated_request(
            scenario=scenario,
            catalog_pois=pois,
            mock_transport=transport,
            request_counter=counter,
            simulated_fallback=True,
        )


def test_pf_a_11_primary_parse_path_succeeds_on_strict_json_across_all_candidates(tmp_path: Path) -> None:
    """PF-A-11: Valid strict JSON response parses into BenchmarkPlanResponse in 1 call with raw artifact preserved."""
    scenario, pois = build_synthetic_smoke_fixtures()[0]
    valid_json_str = build_synthetic_valid_plan_json(scenario, pois)

    # C1 Google
    g_adapter = GooglePreflightAdapter()
    g_transport, g_counter = _make_google_transport(
        status_code=200,
        body_json={
            "modelVersion": "gemini-3.8-flash",
            "candidates": [{"content": {"role": "model", "parts": [{"text": valid_json_str}]}, "finishReason": "STOP"}],
            "usageMetadata": {"promptTokenCount": 120, "candidatesTokenCount": 240, "totalTokenCount": 360},
        },
    )
    g_res = g_adapter.execute_offline_simulated_request(
        scenario=scenario,
        catalog_pois=pois,
        mock_transport=g_transport,
        request_counter=g_counter,
        output_dir=tmp_path / "c1",
    )
    assert g_res.run_status == BenchmarkRunStatus.VALID
    assert g_res.request_attempt_count == 1
    assert g_res.primary_json_repair_called is False
    assert g_res.raw_artifact_preserved is True
    assert g_res.parsed_response is not None

    # C2 OpenAI
    o_adapter = OpenAIPreflightAdapter()
    o_transport, o_counter = _make_httpx2_transport(
        status_code=200,
        body_json={
            "id": "chatcmpl-001",
            "object": "chat.completion",
            "created": 1760000000,
            "model": "gpt-6.1-sol",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": valid_json_str}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 110, "completion_tokens": 230, "total_tokens": 340},
        },
    )
    o_res = o_adapter.execute_offline_simulated_request(
        scenario=scenario,
        catalog_pois=pois,
        mock_transport=o_transport,
        request_counter=o_counter,
        output_dir=tmp_path / "c2",
    )
    assert o_res.run_status == BenchmarkRunStatus.VALID
    assert o_res.request_attempt_count == 1
    assert o_res.primary_json_repair_called is False
    assert o_res.parsed_response is not None

    # C3 Anthropic
    a_adapter = AnthropicPreflightAdapter()
    a_transport, a_counter = _make_httpx2_transport(
        status_code=200,
        body_json={
            "id": "msg_001",
            "type": "message",
            "role": "assistant",
            "model": "claude-sonnet-5-5",
            "content": [{"type": "text", "text": valid_json_str}],
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": 115, "output_tokens": 235},
        },
    )
    a_res = a_adapter.execute_offline_simulated_request(
        scenario=scenario,
        catalog_pois=pois,
        mock_transport=a_transport,
        request_counter=a_counter,
        output_dir=tmp_path / "c3",
    )
    assert a_res.run_status == BenchmarkRunStatus.VALID
    assert a_res.request_attempt_count == 1
    assert a_res.primary_json_repair_called is False
    assert a_res.parsed_response is not None


def test_pf_a_12_primary_parse_path_does_not_call_legacy_cleaner_on_fenced_json() -> None:
    """PF-A-12: Markdown code-fenced JSON fails primary parse (UNPARSABLE_MODEL_OUTPUT) because clean_benchmark_json_response is NOT called in primary path."""
    scenario, pois = build_synthetic_smoke_fixtures()[0]
    fenced_json = "```json\n" + build_synthetic_valid_plan_json(scenario, pois) + "\n```"

    g_adapter = GooglePreflightAdapter()
    g_transport, g_counter = _make_google_transport(
        status_code=200,
        body_json={
            "modelVersion": "gemini-3.8-flash",
            "candidates": [{"content": {"role": "model", "parts": [{"text": fenced_json}]}, "finishReason": "STOP"}],
        },
    )
    res = g_adapter.execute_offline_simulated_request(
        scenario=scenario,
        catalog_pois=pois,
        mock_transport=g_transport,
        request_counter=g_counter,
    )
    assert res.run_status == BenchmarkRunStatus.UNPARSABLE_MODEL_OUTPUT
    assert res.failure_classification == PreflightFailureClassification.UNPARSABLE_MODEL_OUTPUT
    assert res.primary_json_repair_called is False
    assert res.raw_artifact_preserved is True
    assert res.raw_response_text == fenced_json
    assert res.legacy_recoverable_parse_diagnostic is True


def test_pf_a_13_c1_google_preflight_record() -> None:
    """PF-A-13: C1 (Google / gemini-3.8-flash) preflight record satisfies Section 8 & 9 invariants."""
    rec = GooglePreflightAdapter().get_preflight_record()
    assert rec.candidate_id == "C1"
    assert rec.provider == "Google"
    assert rec.requested_model_id == "gemini-3.8-flash"
    assert rec.live_model_id_status == CapabilityVerificationStatus.PENDING_LIVE_CONFIRMATION
    assert rec.sampling_capabilities["temperature"].configured_value == FROZEN_SAMPLING_TEMPERATURE
    assert rec.sampling_capabilities["seed"].configured_value == FROZEN_SAMPLING_SEED
    assert rec.sampling_capabilities["max_output_tokens"].configured_value == FROZEN_MAX_OUTPUT_TOKENS
    assert rec.sampling_capabilities["timeout"].configured_value == FROZEN_TIMEOUT_MS
    assert rec.retry_configuration.sdk_automatic_retry == 0
    assert rec.retry_configuration.transport_retry == 0


def test_pf_a_14_c2_openai_preflight_record() -> None:
    """PF-A-14: C2 (OpenAI / gpt-6.1-sol) preflight record satisfies Section 8 & 9 invariants."""
    rec = OpenAIPreflightAdapter().get_preflight_record()
    assert rec.candidate_id == "C2"
    assert rec.provider == "OpenAI"
    assert rec.requested_model_id == "gpt-6.1-sol"
    assert rec.live_model_id_status == CapabilityVerificationStatus.PENDING_LIVE_CONFIRMATION
    assert rec.sampling_capabilities["temperature"].configured_value == FROZEN_SAMPLING_TEMPERATURE
    assert rec.sampling_capabilities["seed"].configured_value == FROZEN_SAMPLING_SEED
    assert rec.sampling_capabilities["top_k"].verification_status == CapabilityVerificationStatus.UNSUPPORTED
    assert rec.retry_configuration.sdk_automatic_retry == 0
    assert rec.retry_configuration.transport_retry == 0


def test_pf_a_15_c3_anthropic_preflight_record() -> None:
    """PF-A-15: C3 (Anthropic / claude-sonnet-5-5) preflight record satisfies Section 8 & 9 invariants."""
    rec = AnthropicPreflightAdapter().get_preflight_record()
    assert rec.candidate_id == "C3"
    assert rec.provider == "Anthropic"
    assert rec.requested_model_id == "claude-sonnet-5-5"
    assert rec.live_model_id_status == CapabilityVerificationStatus.PENDING_LIVE_CONFIRMATION
    assert rec.sampling_capabilities["temperature"].verification_status == CapabilityVerificationStatus.UNSUPPORTED
    assert rec.sampling_capabilities["seed"].verification_status == CapabilityVerificationStatus.UNSUPPORTED
    assert rec.sampling_capabilities["thinking_or_reasoning_setting"].configured_value == {"type": "disabled"}
    assert rec.retry_configuration.sdk_automatic_retry == 0
    assert rec.retry_configuration.transport_retry == 0


def test_pf_a_16_retry_zero_on_http_429_across_all_candidates() -> None:
    """PF-A-16: Simulated HTTP 429 makes exactly 1 request attempt across C1, C2, and C3."""
    scenario, pois = build_synthetic_smoke_fixtures()[0]

    # C1 Google
    g_transport, g_counter = _make_google_transport(
        status_code=429,
        body_json={"error": {"code": 429, "message": "Rate limit exceeded", "status": "RESOURCE_EXHAUSTED"}},
    )
    g_res = GooglePreflightAdapter().execute_offline_simulated_request(
        scenario=scenario, catalog_pois=pois, mock_transport=g_transport, request_counter=g_counter
    )
    assert g_res.request_attempt_count == 1
    assert g_res.failure_classification == PreflightFailureClassification.HTTP_429
    assert g_res.fallback_called is False
    assert g_res.llm_repair_calls == 0

    # C2 OpenAI
    o_transport, o_counter = _make_httpx2_transport(
        status_code=429,
        body_json={"error": {"message": "Rate limit exceeded", "type": "rate_limit_error"}},
    )
    o_res = OpenAIPreflightAdapter().execute_offline_simulated_request(
        scenario=scenario, catalog_pois=pois, mock_transport=o_transport, request_counter=o_counter
    )
    assert o_res.request_attempt_count == 1
    assert o_res.failure_classification == PreflightFailureClassification.HTTP_429
    assert o_res.fallback_called is False

    # C3 Anthropic
    a_transport, a_counter = _make_httpx2_transport(
        status_code=429,
        body_json={"type": "error", "error": {"type": "rate_limit_error", "message": "Rate limit exceeded"}},
    )
    a_res = AnthropicPreflightAdapter().execute_offline_simulated_request(
        scenario=scenario, catalog_pois=pois, mock_transport=a_transport, request_counter=a_counter
    )
    assert a_res.request_attempt_count == 1
    assert a_res.failure_classification == PreflightFailureClassification.HTTP_429
    assert a_res.fallback_called is False


def test_pf_a_17_retry_zero_on_http_500_across_all_candidates() -> None:
    """PF-A-17: Simulated HTTP 500 makes exactly 1 request attempt across C1, C2, and C3."""
    scenario, pois = build_synthetic_smoke_fixtures()[0]

    g_transport, g_counter = _make_google_transport(
        status_code=500,
        body_json={"error": {"code": 500, "message": "Internal server error", "status": "INTERNAL"}},
    )
    g_res = GooglePreflightAdapter().execute_offline_simulated_request(
        scenario=scenario, catalog_pois=pois, mock_transport=g_transport, request_counter=g_counter
    )
    assert g_res.request_attempt_count == 1
    assert g_res.failure_classification == PreflightFailureClassification.HTTP_5XX

    o_transport, o_counter = _make_httpx2_transport(
        status_code=500,
        body_json={"error": {"message": "Internal server error", "type": "server_error"}},
    )
    o_res = OpenAIPreflightAdapter().execute_offline_simulated_request(
        scenario=scenario, catalog_pois=pois, mock_transport=o_transport, request_counter=o_counter
    )
    assert o_res.request_attempt_count == 1
    assert o_res.failure_classification == PreflightFailureClassification.HTTP_5XX

    a_transport, a_counter = _make_httpx2_transport(
        status_code=500,
        body_json={"type": "error", "error": {"type": "api_error", "message": "Internal server error"}},
    )
    a_res = AnthropicPreflightAdapter().execute_offline_simulated_request(
        scenario=scenario, catalog_pois=pois, mock_transport=a_transport, request_counter=a_counter
    )
    assert a_res.request_attempt_count == 1
    assert a_res.failure_classification == PreflightFailureClassification.HTTP_5XX


def test_pf_a_18_retry_zero_on_timeout_across_all_candidates() -> None:
    """PF-A-18: Simulated transport timeout makes exactly 1 request attempt across C1, C2, and C3."""
    scenario, pois = build_synthetic_smoke_fixtures()[0]

    g_transport, g_counter = _make_google_transport(raise_timeout=True)
    g_res = GooglePreflightAdapter().execute_offline_simulated_request(
        scenario=scenario, catalog_pois=pois, mock_transport=g_transport, request_counter=g_counter
    )
    assert g_res.request_attempt_count == 1
    assert g_res.failure_classification == PreflightFailureClassification.TIMEOUT

    o_transport, o_counter = _make_httpx2_transport(raise_timeout=True)
    o_res = OpenAIPreflightAdapter().execute_offline_simulated_request(
        scenario=scenario, catalog_pois=pois, mock_transport=o_transport, request_counter=o_counter
    )
    assert o_res.request_attempt_count == 1
    assert o_res.failure_classification == PreflightFailureClassification.TIMEOUT

    a_transport, a_counter = _make_httpx2_transport(raise_timeout=True)
    a_res = AnthropicPreflightAdapter().execute_offline_simulated_request(
        scenario=scenario, catalog_pois=pois, mock_transport=a_transport, request_counter=a_counter
    )
    assert a_res.request_attempt_count == 1
    assert a_res.failure_classification == PreflightFailureClassification.TIMEOUT


def test_pf_a_19_malformed_response_single_attempt_and_raw_preserved() -> None:
    """PF-A-19: Malformed response makes 1 attempt, preserves raw artifact, and performs 0 repairs."""
    scenario, pois = build_synthetic_smoke_fixtures()[0]
    malformed = '{"plan_id": "broken-json", "days": ['

    g_transport, g_counter = _make_google_transport(
        status_code=200,
        body_json={
            "modelVersion": "gemini-3.8-flash",
            "candidates": [{"content": {"role": "model", "parts": [{"text": malformed}]}, "finishReason": "MAX_TOKENS"}],
        },
    )
    g_res = GooglePreflightAdapter().execute_offline_simulated_request(
        scenario=scenario, catalog_pois=pois, mock_transport=g_transport, request_counter=g_counter
    )
    assert g_res.request_attempt_count == 1
    assert g_res.failure_classification == PreflightFailureClassification.UNPARSABLE_MODEL_OUTPUT
    assert g_res.raw_artifact_preserved is True
    assert g_res.raw_response_text == malformed
    assert g_res.llm_repair_calls == 0

    o_transport, o_counter = _make_httpx2_transport(
        status_code=200,
        body_json={
            "id": "chatcmpl-mal",
            "object": "chat.completion",
            "created": 1760000000,
            "model": "gpt-6.1-sol",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": malformed}, "finish_reason": "length"}],
        },
    )
    o_res = OpenAIPreflightAdapter().execute_offline_simulated_request(
        scenario=scenario, catalog_pois=pois, mock_transport=o_transport, request_counter=o_counter
    )
    assert o_res.request_attempt_count == 1
    assert o_res.failure_classification == PreflightFailureClassification.UNPARSABLE_MODEL_OUTPUT
    assert o_res.raw_artifact_preserved is True

    a_transport, a_counter = _make_httpx2_transport(
        status_code=200,
        body_json={
            "id": "msg_mal",
            "type": "message",
            "role": "assistant",
            "model": "claude-sonnet-5-5",
            "content": [{"type": "text", "text": malformed}],
            "stop_reason": "max_tokens",
            "usage": {"input_tokens": 50, "output_tokens": 50},
        },
    )
    a_res = AnthropicPreflightAdapter().execute_offline_simulated_request(
        scenario=scenario, catalog_pois=pois, mock_transport=a_transport, request_counter=a_counter
    )
    assert a_res.request_attempt_count == 1
    assert a_res.failure_classification == PreflightFailureClassification.UNPARSABLE_MODEL_OUTPUT
    assert a_res.raw_artifact_preserved is True


def test_pf_a_20_refusal_response_single_attempt_and_raw_preserved() -> None:
    """PF-A-20: Refusal response makes 1 attempt, preserves raw artifact, and classifies as REFUSAL."""
    scenario, pois = build_synthetic_smoke_fixtures()[0]

    g_transport, g_counter = _make_google_transport(
        status_code=200,
        body_json={
            "modelVersion": "gemini-3.8-flash",
            "candidates": [{"content": {"role": "model", "parts": [{"text": "Cannot fulfill request."}]}, "finishReason": "SAFETY"}],
        },
    )
    g_res = GooglePreflightAdapter().execute_offline_simulated_request(
        scenario=scenario, catalog_pois=pois, mock_transport=g_transport, request_counter=g_counter
    )
    assert g_res.request_attempt_count == 1
    assert g_res.failure_classification == PreflightFailureClassification.REFUSAL
    assert g_res.raw_artifact_preserved is True

    o_transport, o_counter = _make_httpx2_transport(
        status_code=200,
        body_json={
            "id": "chatcmpl-ref",
            "object": "chat.completion",
            "created": 1760000000,
            "model": "gpt-6.1-sol",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": None, "refusal": "I cannot assist with that."}, "finish_reason": "stop"}],
        },
    )
    o_res = OpenAIPreflightAdapter().execute_offline_simulated_request(
        scenario=scenario, catalog_pois=pois, mock_transport=o_transport, request_counter=o_counter
    )
    assert o_res.request_attempt_count == 1
    assert o_res.failure_classification == PreflightFailureClassification.REFUSAL
    assert o_res.raw_artifact_preserved is True

    a_transport, a_counter = _make_httpx2_transport(
        status_code=200,
        body_json={
            "id": "msg_ref",
            "type": "message",
            "role": "assistant",
            "model": "claude-sonnet-5-5",
            "content": [{"type": "text", "text": "Refused due to policy."}],
            "stop_reason": "refusal",
            "usage": {"input_tokens": 50, "output_tokens": 10},
        },
    )
    a_res = AnthropicPreflightAdapter().execute_offline_simulated_request(
        scenario=scenario, catalog_pois=pois, mock_transport=a_transport, request_counter=a_counter
    )
    assert a_res.request_attempt_count == 1
    assert a_res.failure_classification == PreflightFailureClassification.REFUSAL
    assert a_res.raw_artifact_preserved is True


def test_pf_a_21_wrong_returned_model_id_triggers_configuration_integrity_failure() -> None:
    """PF-A-21: Wrong returned model metadata triggers CONFIGURATION_INTEGRITY_FAILURE with 1 attempt and zero fallback."""
    scenario, pois = build_synthetic_smoke_fixtures()[0]
    valid_json_str = build_synthetic_valid_plan_json(scenario, pois)

    g_transport, g_counter = _make_google_transport(
        status_code=200,
        body_json={
            "modelVersion": "gemini-2.5-flash-fallback",
            "candidates": [{"content": {"role": "model", "parts": [{"text": valid_json_str}]}, "finishReason": "STOP"}],
        },
    )
    g_res = GooglePreflightAdapter().execute_offline_simulated_request(
        scenario=scenario, catalog_pois=pois, mock_transport=g_transport, request_counter=g_counter
    )
    assert g_res.request_attempt_count == 1
    assert g_res.run_status == BenchmarkRunStatus.MODEL_ID_MISMATCH
    assert g_res.failure_classification == PreflightFailureClassification.CONFIGURATION_INTEGRITY_FAILURE

    # Also verify raise_on_integrity_failure=True raises ConfigurationIntegrityError
    o_transport, o_counter = _make_httpx2_transport(
        status_code=200,
        body_json={
            "id": "chatcmpl-wrong",
            "object": "chat.completion",
            "created": 1760000000,
            "model": "gpt-4o-mini",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": valid_json_str}, "finish_reason": "stop"}],
        },
    )
    with pytest.raises(ConfigurationIntegrityError):
        OpenAIPreflightAdapter().execute_offline_simulated_request(
            scenario=scenario,
            catalog_pois=pois,
            mock_transport=o_transport,
            request_counter=o_counter,
            raise_on_integrity_failure=True,
        )

    a_transport, a_counter = _make_httpx2_transport(
        status_code=200,
        body_json={
            "id": "msg_wrong",
            "type": "message",
            "role": "assistant",
            "model": "claude-3-5-haiku-20241022",
            "content": [{"type": "text", "text": valid_json_str}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 50, "output_tokens": 50},
        },
    )
    a_res = AnthropicPreflightAdapter().execute_offline_simulated_request(
        scenario=scenario, catalog_pois=pois, mock_transport=a_transport, request_counter=a_counter
    )
    assert a_res.request_attempt_count == 1
    assert a_res.run_status == BenchmarkRunStatus.MODEL_ID_MISMATCH
    assert a_res.failure_classification == PreflightFailureClassification.CONFIGURATION_INTEGRITY_FAILURE


def test_pf_a_22_synthetic_smoke_fixtures_isolated_from_final_100_and_dev_80() -> None:
    """PF-A-22: Synthetic smoke fixtures have distinct IDs and never touch final 100 or DEV 80 files."""
    fixtures = build_synthetic_smoke_fixtures()
    assert [sc.scenario_id for sc, _ in fixtures] == list(SYNTHETIC_SMOKE_SCENARIO_IDS)
    for sc, pois in fixtures:
        assert sc.scenario_id.startswith("W06-PREFLIGHT-SMOKE-")
        assert not sc.scenario_id.startswith("W06-S")
        assert not sc.scenario_id.startswith("W06-DEV-")
        assert all(p.place_id.startswith("smoke-") for p in pois)


def test_pf_a_23_dotenv_key_presence_redaction(tmp_path: Path) -> None:
    """PF-A-23: check_dotenv_key_presence reports ONLY PRESENT or MISSING, never key values."""
    fake_env = tmp_path / ".env"
    fake_env.write_text(
        "GEMINI_API_KEY=secret_val_1\nOPENAI_API_KEY=\nANTHROPIC_API_KEY=secret_val_3\n",
        encoding="utf-8",
    )
    presence = check_dotenv_key_presence(dotenv_path=fake_env)
    assert presence == {
        "GEMINI_API_KEY": "PRESENT",
        "OPENAI_API_KEY": "MISSING",
        "ANTHROPIC_API_KEY": "PRESENT",
    }
    serialized = json.dumps(presence)
    assert "secret_val" not in serialized


def test_pf_a_24_tracked_files_secret_leak_scan_is_clean() -> None:
    """PF-A-24: Tracked-file secret scan reports 0 leaks and 0 affected files."""
    scan_res = scan_tracked_files_for_secret_leaks(repo_root=REPO_ROOT)
    assert set(scan_res.keys()) == {"secret_leak_count", "affected_file_paths"}
    assert scan_res["secret_leak_count"] == 0
    assert scan_res["affected_file_paths"] == []


def test_pf_a_25_readonly_opening_hours_catalog_audit() -> None:
    """PF-A-25: Read-only opening-hours catalog audit matches exact frozen REC-A-CORE-V2 counts."""
    audit = run_readonly_opening_hours_catalog_audit()
    assert audit["mode"] == "READ_ONLY_CATALOG_EVIDENCE_AUDIT"
    assert audit["total_reca_core_pois"] == 622
    assert audit["raw_opening_hours_present_count"] == 101
    assert audit["raw_opening_hours_missing_count"] == 521
    assert audit["known_opening_hours_count"] == 91
    assert audit["parser_unsupported_opening_hours_count"] == 10
    assert audit["unknown_opening_hours_count"] == 531
    assert audit["coverage_rate"] == 0.146302
    assert audit["raw_presence_rate"] == 0.162379
    assert audit["catalog_sha256"] == "f7517938598e3923906763f8f31334a500ee88bc06232f2992d38e2fcb28a444"
    assert set(audit["per_destination_coverage"].keys()) == {"ha-noi", "da-nang", "ha-long"}


def test_pf_a_26_offline_receipt_exists_and_verifies_zero_live_calls() -> None:
    """PF-A-26: w06_model_preflight_01a_offline_receipt_v1.json exists, is canonical JSON, and records 0 live calls."""
    assert RECEIPT_PATH.is_file()
    raw_bytes = RECEIPT_PATH.read_bytes()
    data = json.loads(raw_bytes.decode("utf-8"))
    assert canonical_json_bytes(data) == raw_bytes
    assert data["artifact_id"] == "W06-MODEL-PREFLIGHT-01A-OFFLINE"
    assert data["live_calls_made"] is False
    assert data["live_call_count"] == 0
    assert data["gemini_called"] is False
    assert data["openai_called"] is False
    assert data["claude_called"] is False
    assert data["grok_called"] is False
    assert data["final_100_used"] is False
    assert data["dev_tune_executed"] is False
    assert data["dev_select_executed"] is False
    assert data["winning_model_selected"] is False
    assert data["preregistered"] is False
    assert data["final_benchmark_executed"] is False
    assert data["common_schema_sha256"] == COMMON_SCHEMA_SHA256
    assert data["architecture_invariants"]["architecture_id"] == FROZEN_ARCHITECTURE_ID
    assert data["frozen_authority_preservation"] == EXPECTED_FROZEN_AUTHORITY_SHAS


def test_pf_a_27_receipt_contains_no_secret_values() -> None:
    """PF-A-27: Receipt contains only PRESENT/MISSING for env_key_presence and zero secret patterns."""
    data = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
    for k, v in data["env_key_presence"].items():
        assert k in ("GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY")
        assert v in ("PRESENT", "MISSING")
    assert data["secret_leak_scan"]["secret_leak_count"] == 0
    assert data["secret_leak_scan"]["affected_file_paths"] == []


def test_pf_a_28_documentation_exists_and_covers_required_sections() -> None:
    """PF-A-28: docs/research/w06_model_preflight_01a_offline_v1.md exists and documents required preflight sections."""
    assert DOC_PATH.is_file()
    text = DOC_PATH.read_text(encoding="utf-8")
    for token in (
        "W06-MODEL-PREFLIGHT-01A-OFFLINE",
        "LLM_BASED_ITINERARY_PLANNER_WITH_DETERMINISTIC_GROUNDING_AND_VALIDATION_V1",
        "gemini-3.8-flash",
        "gpt-6.1-sol",
        "claude-sonnet-5-5",
        COMMON_SCHEMA_SHA256,
        "PENDING_LIVE_CONFIRMATION",
        "W06-PREFLIGHT-SMOKE-001",
        "W06-PREFLIGHT-SMOKE-002",
    ):
        assert token in text


def test_pf_a_29_production_planner_and_llm_providers_unmodified() -> None:
    """PF-A-29: Production /planner router and apps/ai-service/app/llm/* remain unmodified vs develop."""
    res = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            "develop",
            "--",
            "apps/ai-service/app/routers/planner.py",
            "apps/ai-service/app/llm/",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert res.stdout.strip() == ""


def test_pf_a_30_all_14_frozen_authorities_preserved_byte_identical() -> None:
    """PF-A-30: All 14 frozen scientific and DEV artifacts remain byte-identical."""
    assert len(EXPECTED_FROZEN_AUTHORITY_SHAS) == 14
    for rel_path, expected_sha in EXPECTED_FROZEN_AUTHORITY_SHAS.items():
        file_path = REPO_ROOT / rel_path
        assert file_path.is_file(), f"Missing frozen file: {rel_path}"
        actual_sha = sha256_bytes(normalize_lf_bytes(file_path.read_bytes()))
        assert actual_sha == expected_sha, f"SHA mismatch for {rel_path}: {actual_sha} != {expected_sha}"
