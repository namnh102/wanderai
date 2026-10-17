"""Offline verification suite for W06-MODEL-PREFLIGHT-01B-LIVE-SMOKE (Tests LB-01 through LB-26).

Proves all Phase 01B invariants, live plan freeze, C1/C2/C3 wire configurations,
counting transport fail-closed budget enforcement, candidate substitution guard,
secret-safe persistence, and live plan immutability without making any live API calls.
"""
import ast
import json
from pathlib import Path
import sys
from typing import Any, Dict, List

import httpx
import httpx2
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
AI_SERVICE_ROOT = REPO_ROOT / "apps" / "ai-service"
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))

from app.evaluation.model_preflight import (  # noqa: E402
    COMMON_GENERATION_SCHEMA_SHA256,
    FROZEN_SAMPLING_SEED,
    SEMANTIC_SCHEMA_SHA256,
    AnthropicPreflightAdapter,
    GooglePreflightAdapter,
    LiveProviderCallForbiddenError,
    OneCallInvariantViolationError,
    OpenAIPreflightAdapter,
    build_all_candidate_preflight_adapters,
    build_synthetic_valid_plan_json,
     sanitize_secret_error_text,
)
from app.evaluation.model_preflight.live_smoke import (  # noqa: E402
    DEFAULT_LIVE_ARTIFACTS_DIR,
    DEFAULT_LIVE_PLAN_PATH,
    DEFAULT_LIVE_RECEIPT_PATH,
    EXPECTED_BASE_DEVELOP_SHA_01B,
    FROZEN_CANDIDATE_EXECUTION_ORDER,
    FROZEN_CANDIDATE_SPECS,
    TASK_ID_01B,
    CountingHttpx2Transport,
    CountingHttpxTransport,
    LiveCallBudgetTracker,
    build_live_smoke_plan_payload,
    compute_estimated_standard_api_cost_usd,
    execute_single_candidate_live_smoke,
    get_live_smoke_001_fixture,
    run_live_smoke_suite,
    scan_directory_for_secret_leaks,
    validate_candidate_identity,
    validate_live_smoke_fixture_id,
    verify_frozen_authorities_01b,
    verify_live_plan_immutability,
)
from app.evaluation.model_preflight.types import (  # noqa: E402
    FROZEN_LIVE_SMOKE_FIXTURE_ID,
    FROZEN_MAX_LIVE_GENERATION_CALLS_PER_CANDIDATE,
    FROZEN_MAX_LIVE_GENERATION_CALLS_TOTAL,
    CandidateFinalPreflightStatus,
    LiveFailureClassification,
    LiveUsageMetadataRecord,
)
from app.services.planner_benchmark_runner import canonical_json_bytes, sha256_bytes  # noqa: E402


def _make_mock_httpx_transport(body_json: Dict[str, Any], captured_bodies: List[Dict[str, Any]]) -> httpx.MockTransport:
    def _handler(request: httpx.Request) -> httpx.Response:
        if request.content:
            captured_bodies.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(
            status_code=200,
            headers={"content-type": "application/json"},
            content=json.dumps(body_json).encode("utf-8"),
            request=request,
        )

    return httpx.MockTransport(_handler)


def _make_mock_httpx2_transport(body_json: Dict[str, Any], captured_bodies: List[Dict[str, Any]]) -> httpx2.MockTransport:
    def _handler(request: httpx2.Request) -> httpx2.Response:
        if request.content:
            captured_bodies.append(json.loads(request.content.decode("utf-8")))
        return httpx2.Response(
            status_code=200,
            headers={"content-type": "application/json"},
            content=json.dumps(body_json).encode("utf-8"),
            request=request,
        )

    return httpx2.MockTransport(_handler)


def test_lb_01_live_plan_exact_candidate_list() -> None:
    """LB-01: Live plan freezes exact candidate list C1, C2, C3 and requested model IDs."""
    assert DEFAULT_LIVE_PLAN_PATH.is_file()
    plan = json.loads(DEFAULT_LIVE_PLAN_PATH.read_text(encoding="utf-8"))
    assert plan["task_id"] == TASK_ID_01B
    assert plan["base_develop_sha"] == EXPECTED_BASE_DEVELOP_SHA_01B
    assert plan["candidate_ids"] == ["C1", "C2", "C3"]
    assert plan["candidate_execution_order"] == ["C1", "C2", "C3"]
    assert plan["requested_model_ids"] == {
        "C1": "gemini-3.8-flash",
        "C2": "gpt-6.1-sol",
        "C3": "claude-sonnet-5-5",
    }


def test_lb_02_same_smoke_fixture_for_all_candidates() -> None:
    """LB-02: All three candidates use ONLY W06-PREFLIGHT-SMOKE-001; W06-PREFLIGHT-SMOKE-002 is rejected."""
    plan = json.loads(DEFAULT_LIVE_PLAN_PATH.read_text(encoding="utf-8"))
    assert plan["fixture_id"] == "W06-PREFLIGHT-SMOKE-001"
    assert plan["smoke_002_used"] is False
    scenario, pois = get_live_smoke_001_fixture()
    assert scenario.scenario_id == "W06-PREFLIGHT-SMOKE-001"
    assert len(pois) == 2

    with pytest.raises(OneCallInvariantViolationError, match="ONLY 'W06-PREFLIGHT-SMOKE-001' is allowed"):
        validate_live_smoke_fixture_id("W06-PREFLIGHT-SMOKE-002")


def test_lb_03_final_100_scenarios_forbidden() -> None:
    """LB-03: Final 100 scenarios are strictly forbidden in Phase 01B live smoke."""
    plan = json.loads(DEFAULT_LIVE_PLAN_PATH.read_text(encoding="utf-8"))
    assert plan["final_100_allowed"] is False
    for bad_id in ("W06-S001", "W06-S050", "W06-S100"):
        with pytest.raises(OneCallInvariantViolationError):
            validate_live_smoke_fixture_id(bad_id)


def test_lb_04_dev_fixtures_not_used() -> None:
    """LB-04: DEV-TUNE (20) and DEV-SELECT (60) fixtures are strictly forbidden in Phase 01B."""
    plan = json.loads(DEFAULT_LIVE_PLAN_PATH.read_text(encoding="utf-8"))
    assert plan["dev_tune_allowed"] is False
    assert plan["dev_select_allowed"] is False
    for bad_id in ("W06-DEV-TUNE-001", "W06-DEV-SELECT-001", "W06-DEV-001"):
        with pytest.raises(OneCallInvariantViolationError):
            validate_live_smoke_fixture_id(bad_id)


def test_lb_05_max_total_live_calls_equals_3() -> None:
    """LB-05: Frozen live plan and budget tracker enforce max_live_generation_calls_total == 3."""
    plan = json.loads(DEFAULT_LIVE_PLAN_PATH.read_text(encoding="utf-8"))
    assert plan["max_live_generation_calls_total"] == 3
    assert FROZEN_MAX_LIVE_GENERATION_CALLS_TOTAL == 3
    tracker = LiveCallBudgetTracker()
    assert tracker.max_total_calls == 3


def test_lb_06_max_calls_per_candidate_equals_1() -> None:
    """LB-06: Frozen live plan and budget tracker enforce max_live_generation_calls_per_candidate == 1."""
    plan = json.loads(DEFAULT_LIVE_PLAN_PATH.read_text(encoding="utf-8"))
    assert plan["max_live_generation_calls_per_candidate"] == 1
    assert FROZEN_MAX_LIVE_GENERATION_CALLS_PER_CANDIDATE == 1
    tracker = LiveCallBudgetTracker()
    assert tracker.max_calls_per_candidate == 1


def test_lb_07_retry_equals_zero_across_plan_and_adapters() -> None:
    """LB-07: Automatic and manual retries are fixed to 0 across C1, C2, and C3."""
    plan = json.loads(DEFAULT_LIVE_PLAN_PATH.read_text(encoding="utf-8"))
    assert plan["automatic_retry"] == 0
    assert plan["manual_retry"] == 0
    for cid in ("C1", "C2", "C3"):
        c_cfg = plan["candidate_configurations"][cid]
        assert c_cfg["sdk_automatic_retry"] == 0
        assert c_cfg["transport_retry"] == 0


def test_lb_08_fallback_equals_false() -> None:
    """LB-08: Fallback model/provider is strictly false."""
    plan = json.loads(DEFAULT_LIVE_PLAN_PATH.read_text(encoding="utf-8"))
    assert plan["fallback"] is False
    for adapter in build_all_candidate_preflight_adapters().values():
        assert adapter.common_architecture_invariants()["fallback"] is False


def test_lb_09_repair_equals_zero() -> None:
    """LB-09: LLM repair calls and primary JSON repair are strictly 0 / false."""
    plan = json.loads(DEFAULT_LIVE_PLAN_PATH.read_text(encoding="utf-8"))
    assert plan["repair"] is False
    for adapter in build_all_candidate_preflight_adapters().values():
        inv = adapter.common_architecture_invariants()
        assert inv["llm_repair_calls"] == 0
        assert inv["primary_json_repair"] is False


def test_lb_10_c1_omits_temperature_top_p_top_k() -> None:
    """LB-10: C1 (Google / gemini-3.8-flash) omits temperature, top_p, top_k, and candidate_count."""
    scenario, pois = get_live_smoke_001_fixture()
    valid_json_str = build_synthetic_valid_plan_json(scenario, pois)
    bodies: List[Dict[str, Any]] = []
    mock_tx = _make_mock_httpx_transport(
        {
            "modelVersion": "gemini-3.8-flash",
            "candidates": [{"content": {"role": "model", "parts": [{"text": valid_json_str}]}, "finishReason": "STOP"}],
            "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 200, "totalTokenCount": 300},
        },
        bodies,
    )
    GooglePreflightAdapter().execute_offline_simulated_request(
        scenario=scenario,
        catalog_pois=pois,
        mock_transport=mock_tx,
        request_counter=lambda: len(bodies),
    )
    assert len(bodies) == 1
    gen_cfg = bodies[0].get("generationConfig", {})
    assert "temperature" not in gen_cfg
    assert "topP" not in gen_cfg
    assert "topK" not in gen_cfg
    assert "candidateCount" not in gen_cfg


def test_lb_11_c1_thinking_medium() -> None:
    """LB-11: C1 (Google / gemini-3.8-flash) explicitly configures thinking_level='medium'."""
    scenario, pois = get_live_smoke_001_fixture()
    req = GooglePreflightAdapter().serialize_smoke_request(scenario, pois)
    assert req["config"]["thinking_config"] == {"thinking_level": "medium"}
    plan = json.loads(DEFAULT_LIVE_PLAN_PATH.read_text(encoding="utf-8"))
    assert plan["candidate_configurations"]["C1"]["thinking_config"] == {"thinking_level": "medium"}


def test_lb_12_c2_reasoning_effort_medium() -> None:
    """LB-12: C2 (OpenAI / gpt-6.1-sol) explicitly sets reasoning_effort='medium' on the wire."""
    scenario, pois = get_live_smoke_001_fixture()
    valid_json_str = build_synthetic_valid_plan_json(scenario, pois)
    bodies: List[Dict[str, Any]] = []
    mock_tx = _make_mock_httpx2_transport(
        {
            "id": "chatcmpl-lb12",
            "object": "chat.completion",
            "created": 1760000000,
            "model": "gpt-6.1-sol",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": valid_json_str}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 200, "total_tokens": 300},
        },
        bodies,
    )
    OpenAIPreflightAdapter().execute_offline_simulated_request(
        scenario=scenario,
        catalog_pois=pois,
        mock_transport=mock_tx,
        request_counter=lambda: len(bodies),
    )
    assert len(bodies) == 1
    assert bodies[0].get("reasoning_effort") == "medium"


def test_lb_13_c2_omits_temperature_top_p_top_k_top_logprobs_logprobs() -> None:
    """LB-13: C2 (OpenAI / gpt-6.1-sol) omits temperature, top_p, top_k, top_logprobs, and logprobs from wire body."""
    scenario, pois = get_live_smoke_001_fixture()
    valid_json_str = build_synthetic_valid_plan_json(scenario, pois)
    bodies: List[Dict[str, Any]] = []
    mock_tx = _make_mock_httpx2_transport(
        {
            "id": "chatcmpl-lb13",
            "object": "chat.completion",
            "created": 1760000000,
            "model": "gpt-6.1-sol",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": valid_json_str}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 200, "total_tokens": 300},
        },
        bodies,
    )
    OpenAIPreflightAdapter().execute_offline_simulated_request(
        scenario=scenario,
        catalog_pois=pois,
        mock_transport=mock_tx,
        request_counter=lambda: len(bodies),
    )
    assert len(bodies) == 1
    for forbidden_key in ("temperature", "top_p", "top_k", "top_logprobs", "logprobs", "tools"):
        assert forbidden_key not in bodies[0]


def test_lb_14_c2_service_tier_default() -> None:
    """LB-14: C2 (OpenAI / gpt-6.1-sol) sets service_tier='default' on the wire."""
    scenario, pois = get_live_smoke_001_fixture()
    valid_json_str = build_synthetic_valid_plan_json(scenario, pois)
    bodies: List[Dict[str, Any]] = []
    mock_tx = _make_mock_httpx2_transport(
        {
            "id": "chatcmpl-lb14",
            "object": "chat.completion",
            "created": 1760000000,
            "model": "gpt-6.1-sol",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": valid_json_str}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 200, "total_tokens": 300},
        },
        bodies,
    )
    OpenAIPreflightAdapter().execute_offline_simulated_request(
        scenario=scenario,
        catalog_pois=pois,
        mock_transport=mock_tx,
        request_counter=lambda: len(bodies),
    )
    assert len(bodies) == 1
    assert bodies[0].get("service_tier") == "default"


def test_lb_15_c2_seed_exactly_2026101508() -> None:
    """LB-15: C2 (OpenAI / gpt-6.1-sol) sends seed=2026101508 on the wire."""
    scenario, pois = get_live_smoke_001_fixture()
    valid_json_str = build_synthetic_valid_plan_json(scenario, pois)
    bodies: List[Dict[str, Any]] = []
    mock_tx = _make_mock_httpx2_transport(
        {
            "id": "chatcmpl-lb15",
            "object": "chat.completion",
            "created": 1760000000,
            "model": "gpt-6.1-sol",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": valid_json_str}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 200, "total_tokens": 300},
        },
        bodies,
    )
    OpenAIPreflightAdapter().execute_offline_simulated_request(
        scenario=scenario,
        catalog_pois=pois,
        mock_transport=mock_tx,
        request_counter=lambda: len(bodies),
    )
    assert len(bodies) == 1
    assert bodies[0].get("seed") == 2026101508
    assert FROZEN_SAMPLING_SEED == 2026101508


def test_lb_16_c3_adaptive_thinking() -> None:
    """LB-16: C3 (Anthropic / claude-sonnet-5-5) sets thinking={'type': 'adaptive'} on the wire."""
    scenario, pois = get_live_smoke_001_fixture()
    valid_json_str = build_synthetic_valid_plan_json(scenario, pois)
    bodies: List[Dict[str, Any]] = []
    mock_tx = _make_mock_httpx2_transport(
        {
            "id": "msg-lb16",
            "type": "message",
            "role": "assistant",
            "model": "claude-sonnet-5-5",
            "content": [{"type": "text", "text": valid_json_str}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 100, "output_tokens": 200},
        },
        bodies,
    )
    AnthropicPreflightAdapter().execute_offline_simulated_request(
        scenario=scenario,
        catalog_pois=pois,
        mock_transport=mock_tx,
        request_counter=lambda: len(bodies),
    )
    assert len(bodies) == 1
    assert bodies[0].get("thinking") == {"type": "adaptive"}


def test_lb_17_c3_effort_high() -> None:
    """LB-17: C3 (Anthropic / claude-sonnet-5-5) sets output_config.effort='high' on the wire."""
    scenario, pois = get_live_smoke_001_fixture()
    valid_json_str = build_synthetic_valid_plan_json(scenario, pois)
    bodies: List[Dict[str, Any]] = []
    mock_tx = _make_mock_httpx2_transport(
        {
            "id": "msg-lb17",
            "type": "message",
            "role": "assistant",
            "model": "claude-sonnet-5-5",
            "content": [{"type": "text", "text": valid_json_str}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 100, "output_tokens": 200},
        },
        bodies,
    )
    AnthropicPreflightAdapter().execute_offline_simulated_request(
        scenario=scenario,
        catalog_pois=pois,
        mock_transport=mock_tx,
        request_counter=lambda: len(bodies),
    )
    assert len(bodies) == 1
    assert bodies[0].get("output_config", {}).get("effort") == "high"


def test_lb_18_c3_omits_temperature_top_p_top_k_seed() -> None:
    """LB-18: C3 (Anthropic / claude-sonnet-5-5) omits temperature, top_p, top_k, and seed from wire body."""
    scenario, pois = get_live_smoke_001_fixture()
    valid_json_str = build_synthetic_valid_plan_json(scenario, pois)
    bodies: List[Dict[str, Any]] = []
    mock_tx = _make_mock_httpx2_transport(
        {
            "id": "msg-lb18",
            "type": "message",
            "role": "assistant",
            "model": "claude-sonnet-5-5",
            "content": [{"type": "text", "text": valid_json_str}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 100, "output_tokens": 200},
        },
        bodies,
    )
    AnthropicPreflightAdapter().execute_offline_simulated_request(
        scenario=scenario,
        catalog_pois=pois,
        mock_transport=mock_tx,
        request_counter=lambda: len(bodies),
    )
    assert len(bodies) == 1
    for forbidden_key in ("temperature", "top_p", "top_k", "seed", "tools"):
        assert forbidden_key not in bodies[0]


def test_lb_19_shared_semantic_prompt_hashes_equal() -> None:
    """LB-19: C1, C2, and C3 share identical system_prompt_sha256 and user_prompt_sha256 on W06-PREFLIGHT-SMOKE-001."""
    scenario, pois = get_live_smoke_001_fixture()
    adapters = build_all_candidate_preflight_adapters()
    r1 = adapters["C1"].serialize_smoke_request(scenario, pois)
    r2 = adapters["C2"].serialize_smoke_request(scenario, pois)
    r3 = adapters["C3"].serialize_smoke_request(scenario, pois)
    plan = json.loads(DEFAULT_LIVE_PLAN_PATH.read_text(encoding="utf-8"))

    assert r1["system_prompt_sha256"] == r2["system_prompt_sha256"] == r3["system_prompt_sha256"] == plan["system_prompt_sha256"]
    assert r1["user_prompt_sha256"] == r2["user_prompt_sha256"] == r3["user_prompt_sha256"] == plan["user_prompt_sha256"]


def test_lb_20_shared_schema_hashes_equal() -> None:
    """LB-20: C1, C2, and C3 share identical SEMANTIC_SCHEMA_SHA256 and COMMON_GENERATION_SCHEMA_SHA256."""
    scenario, pois = get_live_smoke_001_fixture()
    adapters = build_all_candidate_preflight_adapters()
    r1 = adapters["C1"].serialize_smoke_request(scenario, pois)
    r2 = adapters["C2"].serialize_smoke_request(scenario, pois)
    r3 = adapters["C3"].serialize_smoke_request(scenario, pois)
    plan = json.loads(DEFAULT_LIVE_PLAN_PATH.read_text(encoding="utf-8"))

    assert r1["semantic_schema_sha256"] == r2["semantic_schema_sha256"] == r3["semantic_schema_sha256"] == SEMANTIC_SCHEMA_SHA256
    assert r1["common_generation_schema_sha256"] == r2["common_generation_schema_sha256"] == r3["common_generation_schema_sha256"] == COMMON_GENERATION_SCHEMA_SHA256
    assert plan["semantic_schema_sha256"] == SEMANTIC_SCHEMA_SHA256
    assert plan["common_generation_schema_sha256"] == COMMON_GENERATION_SCHEMA_SHA256


def test_lb_21_secret_values_cannot_serialize(tmp_path: Path) -> None:
    """LB-21: Secret values from .env or provider exceptions are deterministically sanitized and never serialize."""
    fake_dotenv = tmp_path / ".env"
    syn_g = "AIza" + ("A" * 35)
    syn_o = "sk-proj-" + ("B" * 28)
    syn_a = "sk-ant-" + ("C" * 28)
    fake_dotenv.write_text(
        f"GEMINI_API_KEY={syn_g}\nOPENAI_API_KEY={syn_o}\nANTHROPIC_API_KEY={syn_a}\n",
        encoding="utf-8",
    )
    raw_msg = f"Failed auth: key={syn_g}, bearer={syn_o}, ant={syn_a}, GEMINI_API_KEY={syn_g}"
    sanitized = sanitize_secret_error_text(raw_msg, dotenv_path=fake_dotenv)
    assert sanitized is not None
    assert "[REDACTED_SECRET]" in sanitized
    for secret in (syn_g, syn_o, syn_a, "GEMINI_API_KEY"):
        assert secret not in sanitized


def test_lb_22_actual_http_request_counter_fails_closed_above_one() -> None:
    """LB-22: CountingHttpxTransport / CountingHttpx2Transport and LiveCallBudgetTracker fail closed before a 2nd candidate request or >3 total requests."""
    tracker = LiveCallBudgetTracker()
    bodies: List[Dict[str, Any]] = []
    inner_tx = _make_mock_httpx_transport({"ok": True}, bodies)
    counting_tx = CountingHttpxTransport(
        candidate_id="C1",
        budget_tracker=tracker,
        inner_transport=inner_tx,
    )
    req = httpx.Request("POST", "https://example.com/v1beta/models/gemini-3.8-flash:generateContent")

    # 1st request succeeds
    resp = counting_tx.handle_request(req)
    assert resp.status_code == 200
    assert counting_tx.request_count == 1
    assert tracker.per_candidate_http_requests["C1"] == 1
    assert tracker.total_http_requests == 1

    # 2nd request for C1 aborts BEFORE inner_tx is called
    with pytest.raises(OneCallInvariantViolationError, match="ABORT BEFORE EXTRA REQUEST"):
        counting_tx.handle_request(req)
    assert counting_tx.request_count == 1
    assert tracker.per_candidate_http_requests["C1"] == 1
    assert tracker.total_http_requests == 1

    # Also test cumulative cost cap ($1.00) fail-closed
    tracker.add_estimated_cost(1.05)
    counting_c2 = CountingHttpx2Transport(
        candidate_id="C2",
        budget_tracker=tracker,
        inner_transport=_make_mock_httpx2_transport({"ok": True}, []),
    )
    with pytest.raises(OneCallInvariantViolationError, match="Cumulative estimated spend"):
        counting_c2.handle_request(httpx2.Request("POST", "https://api.openai.com/v1/chat/completions"))


def test_lb_23_no_scientific_evaluator_invocation_in_live_smoke() -> None:
    """LB-23: live_smoke.py never imports or invokes the W06 scientific evaluator or core scoring metrics."""
    live_smoke_path = AI_SERVICE_ROOT / "app" / "evaluation" / "model_preflight" / "live_smoke.py"
    source = live_smoke_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    forbidden_symbols = {
        "PlannerBenchmarkEvaluator",
        "evaluate_planner_benchmark_run",
        "planner_benchmark_evaluator",
        "FINAL_CORE_PASS_RATE",
        "EXACT_GROUNDING_PASS_RATE",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert "planner_benchmark_evaluator" not in node.module
        if isinstance(node, ast.Name):
            assert node.id not in forbidden_symbols


def test_lb_24_candidate_substitution_forbidden() -> None:
    """LB-24: Attempting to substitute a candidate model or add a 4th candidate raises OneCallInvariantViolationError."""
    validate_candidate_identity("C1", "Google", "gemini-3.8-flash")
    validate_candidate_identity("C2", "OpenAI", "gpt-6.1-sol")
    validate_candidate_identity("C3", "Anthropic", "claude-sonnet-5-5")

    with pytest.raises(OneCallInvariantViolationError, match="Candidate substitution or alias switch forbidden"):
        validate_candidate_identity("C1", "Google", "gemini-2.5-flash")
    with pytest.raises(OneCallInvariantViolationError, match="Candidate substitution or alias switch forbidden"):
        validate_candidate_identity("C2", "OpenAI", "gpt-4o")
    with pytest.raises(OneCallInvariantViolationError, match="Candidate substitution or alias switch forbidden"):
        validate_candidate_identity("C3", "Anthropic", "claude-3-7-sonnet-20250219")
    with pytest.raises(OneCallInvariantViolationError, match="Forbidden candidate_id"):
        validate_candidate_identity("C4", "xAI", "grok-3")


def test_lb_25_live_artifact_paths_contain_no_secret(tmp_path: Path) -> None:
    """LB-25: Offline simulated execution of run_live_smoke_suite writes sanitized artifacts with 0 secret leaks."""
    scenario, pois = get_live_smoke_001_fixture()
    valid_json_str = build_synthetic_valid_plan_json(scenario, pois)

    fake_dotenv = tmp_path / ".env"
    syn_g = "AIza" + ("D" * 35)
    syn_o = "sk-proj-" + ("E" * 28)
    syn_a = "sk-ant-" + ("F" * 28)
    fake_dotenv.write_text(
        f"GEMINI_API_KEY={syn_g}\nOPENAI_API_KEY={syn_o}\nANTHROPIC_API_KEY={syn_a}\n",
        encoding="utf-8",
    )

    # Without confirm_live=True, raises LiveProviderCallForbiddenError
    with pytest.raises(LiveProviderCallForbiddenError):
        run_live_smoke_suite(confirm_live=False)

    g_tx = _make_mock_httpx_transport(
        {
            "modelVersion": "gemini-3.8-flash-001",
            "candidates": [{"content": {"role": "model", "parts": [{"text": valid_json_str}]}, "finishReason": "STOP"}],
            "usageMetadata": {"promptTokenCount": 120, "candidatesTokenCount": 240, "thoughtsTokenCount": 40, "totalTokenCount": 400},
        },
        [],
    )
    o_tx = _make_mock_httpx2_transport(
        {
            "id": "chatcmpl-sim",
            "object": "chat.completion",
            "created": 1760000000,
            "model": "gpt-6.1-sol-2026-10-01",
            "service_tier": "default",
            "system_fingerprint": "fp_sim_01",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": valid_json_str}, "finish_reason": "stop"}],
            "usage": {
                "prompt_tokens": 110,
                "completion_tokens": 230,
                "total_tokens": 340,
                "completion_tokens_details": {"reasoning_tokens": 50},
            },
        },
        [],
    )
    a_tx = _make_mock_httpx2_transport(
        {
            "id": "msg_sim",
            "type": "message",
            "role": "assistant",
            "model": "claude-sonnet-5-5-20261001",
            "content": [{"type": "text", "text": valid_json_str}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 115, "output_tokens": 235, "service_tier": "standard"},
        },
        [],
    )

    sim_artifacts = tmp_path / "live_artifacts"
    sim_receipt = tmp_path / "live_receipt.json"
    receipt = run_live_smoke_suite(
        confirm_live=True,
        live_plan_commit_sha="0" * 40,
        transport_overrides={"C1": g_tx, "C2": o_tx, "C3": a_tx},
        artifact_root_dir=sim_artifacts,
        receipt_path=sim_receipt,
        dotenv_path=fake_dotenv,
    )

    assert receipt["actual_live_generation_calls_total"] == 3
    assert receipt["passed_technical_preflight_candidates"] == ["C1", "C2", "C3"]
    assert receipt["artifact_secret_scan"]["secret_leak_count"] == 0
    assert receipt["artifact_secret_scan"]["affected_file_paths"] == []

    # If real live artifacts exist on disk after live run, verify they also pass secret scan
    if DEFAULT_LIVE_ARTIFACTS_DIR.exists():
        real_scan = scan_directory_for_secret_leaks(DEFAULT_LIVE_ARTIFACTS_DIR)
        assert real_scan["secret_leak_count"] == 0
        assert real_scan["affected_file_paths"] == []
    if DEFAULT_LIVE_RECEIPT_PATH.is_file():
        r_data = json.loads(DEFAULT_LIVE_RECEIPT_PATH.read_text(encoding="utf-8"))
        assert r_data["artifact_secret_scan"]["secret_leak_count"] == 0
        assert r_data["tracked_secret_scan"]["secret_leak_count"] == 0
        assert r_data["actual_live_generation_calls_total"] <= 3


def test_lb_26_live_plan_hash_and_config_cannot_mutate_after_freeze(tmp_path: Path) -> None:
    """LB-26: verify_live_plan_immutability succeeds on the canonical plan and fails closed if any byte is mutated."""
    sha = verify_live_plan_immutability(DEFAULT_LIVE_PLAN_PATH)
    assert len(sha) == 64

    mutated_plan_path = tmp_path / "mutated_plan.json"
    payload = build_live_smoke_plan_payload()
    payload["max_live_generation_calls_total"] = 5
    mutated_plan_path.write_bytes(canonical_json_bytes(payload))

    with pytest.raises(RuntimeError, match="HARNESS_ERROR: Frozen live plan file on disk does not match"):
        verify_live_plan_immutability(mutated_plan_path)
