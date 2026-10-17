"""W06-MODEL-PREFLIGHT-01B-LIVE-SMOKE — Frozen Live Smoke Plan, Counting Transport,
1-Call Budget Enforcement, Technical Pass/Fail Classifier, and Sanitized Artifact Persistence.

STRICT INVARIANTS (Sections 0–24):
- Architecture: LLM_BASED_ITINERARY_PLANNER_WITH_DETERMINISTIC_GROUNDING_AND_VALIDATION_V1
- Candidates (frozen, no substitution, no alias switch, no fallback):
  - C1: Google / gemini-3.8-flash
  - C2: OpenAI / gpt-6.1-sol
  - C3: Anthropic / claude-sonnet-5-5
- Live budget:
  - MAX_LIVE_GENERATION_CALLS_TOTAL = 3
  - MAX_LIVE_GENERATION_CALLS_PER_CANDIDATE = 1
  - automatic_retry = 0, manual_retry = 0, fallback = False, llm_repair = 0
- Fixture:
  - ONLY W06-PREFLIGHT-SMOKE-001 (W06-PREFLIGHT-SMOKE-002, DEV 80, and Final 100 are strictly forbidden)
- Technical preflight only:
  - Never invokes the W06 scientific evaluator (PlannerBenchmarkEvaluator / evaluate_planner_benchmark_run).
"""
import argparse
from importlib.metadata import version as pkg_version
import json
from pathlib import Path
import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple

import anthropic
from google import genai
from google.genai import types as genai_types
import httpx
import httpx2
import openai
from pydantic import ValidationError

from app.evaluation.model_preflight.anthropic_adapter import AnthropicPreflightAdapter
from app.evaluation.model_preflight.base import (
    PREFLIGHT_SHARED_SYSTEM_PROMPT,
    REQUIRED_ENV_KEY_NAMES,
    build_shared_semantic_user_prompt,
    build_synthetic_smoke_fixtures,
    check_dotenv_key_presence,
    sanitize_secret_error_text,
    scan_tracked_files_for_secret_leaks,
    verify_model_metadata_integrity,
)
from app.evaluation.model_preflight.google_adapter import GooglePreflightAdapter
from app.evaluation.model_preflight.openai_adapter import OpenAIPreflightAdapter
from app.evaluation.model_preflight.schema_adapter import (
    COMMON_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA,
    COMMON_GENERATION_SCHEMA_SHA256,
    SEMANTIC_SCHEMA_SHA256,
)
from app.evaluation.model_preflight.types import (
    FROZEN_ARCHITECTURE_CLASS,
    FROZEN_ARCHITECTURE_ID,
    FROZEN_CLAUDE_EFFORT,
    FROZEN_CLAUDE_THINKING_MODE,
    FROZEN_GOOGLE_THINKING_LEVEL,
    FROZEN_LIVE_SMOKE_FIXTURE_ID,
    FROZEN_MAX_CUMULATIVE_COST_USD,
    FROZEN_MAX_LIVE_GENERATION_CALLS_PER_CANDIDATE,
    FROZEN_MAX_LIVE_GENERATION_CALLS_TOTAL,
    FROZEN_MAX_OUTPUT_TOKENS,
    FROZEN_OPENAI_REASONING_EFFORT,
    FROZEN_OPENAI_SERVICE_TIER,
    FROZEN_SAMPLING_SEED,
    FROZEN_TIMEOUT_MS,
    CandidateFinalPreflightStatus,
    CandidateStandardPricingRecord,
    LiveCandidateExecutionRecord,
    LiveFailureClassification,
    LiveProviderCallForbiddenError,
    LiveUsageMetadataRecord,
    OneCallInvariantViolationError,
)
from app.prompts.planner_benchmark_prompt import REPO_ROOT
from app.schemas.planner_benchmark import (
    BenchmarkCatalogPOI,
    BenchmarkPlanResponse,
    BenchmarkScenarioInput,
)
from app.services.planner_benchmark_runner import (
    canonical_json_bytes,
    normalize_lf_bytes,
    parse_strict_benchmark_plan_response,
    sha256_bytes,
    write_canonical_json,
    write_exact_utf8_text,
)

TASK_ID_01B: str = "W06-MODEL-PREFLIGHT-01B-LIVE-SMOKE"
VERSION_01B: str = "1.0.0"
EXPECTED_BASE_DEVELOP_SHA_01B: str = "f9bab45f08d97655cf8482b5386dfa75eee09ee7"

DEFAULT_LIVE_PLAN_PATH: Path = (
    REPO_ROOT / "data" / "evaluation" / "w06" / "w06_model_preflight_01b_live_plan_v1.json"
)
DEFAULT_LIVE_RECEIPT_PATH: Path = (
    REPO_ROOT / "data" / "evaluation" / "w06" / "w06_model_preflight_01b_live_receipt_v1.json"
)
DEFAULT_LIVE_ARTIFACTS_DIR: Path = (
    REPO_ROOT / "data" / "evaluation" / "w06" / "model_preflight_01b_live"
)

FROZEN_CANDIDATE_EXECUTION_ORDER: Tuple[str, str, str] = ("C1", "C2", "C3")

FROZEN_CANDIDATE_SPECS: Dict[str, Dict[str, str]] = {
    "C1": {
        "candidate_id": "C1",
        "provider": "Google",
        "requested_model_id": "gemini-3.8-flash",
        "env_key_name": "GEMINI_API_KEY",
        "sdk_package": "google-genai",
        "endpoint": "POST /v1beta/models/{model}:generateContent",
    },
    "C2": {
        "candidate_id": "C2",
        "provider": "OpenAI",
        "requested_model_id": "gpt-6.1-sol",
        "env_key_name": "OPENAI_API_KEY",
        "sdk_package": "openai",
        "endpoint": "POST /v1/chat/completions",
    },
    "C3": {
        "candidate_id": "C3",
        "provider": "Anthropic",
        "requested_model_id": "claude-sonnet-5-5",
        "env_key_name": "ANTHROPIC_API_KEY",
        "sdk_package": "anthropic",
        "endpoint": "POST /v1/messages",
    },
}

FROZEN_STANDARD_PRICING_SPECS: Dict[str, CandidateStandardPricingRecord] = {
    "C1": CandidateStandardPricingRecord(
        candidate_id="C1",
        provider="Google",
        model_id="gemini-3.8-flash",
        pricing_source_url="https://ai.google.dev/gemini-api/docs/pricing",
        pricing_access_date="2026-10-17",
        input_price_per_million=0.75,
        output_price_per_million=3.75,
        notes="Standard paid tier rate ($0.75/1M input, $3.75/1M output including thinking tokens).",
    ),
    "C2": CandidateStandardPricingRecord(
        candidate_id="C2",
        provider="OpenAI",
        model_id="gpt-6.1-sol",
        pricing_source_url="https://platform.openai.com/docs/pricing",
        pricing_access_date="2026-10-17",
        input_price_per_million=2.00,
        output_price_per_million=10.00,
        notes="Standard API tier rate ($2.00/1M input, $10.00/1M output including reasoning tokens).",
    ),
    "C3": CandidateStandardPricingRecord(
        candidate_id="C3",
        provider="Anthropic",
        model_id="claude-sonnet-5-5",
        pricing_source_url="https://docs.anthropic.com/en/docs/about-claude/pricing",
        pricing_access_date="2026-10-17",
        input_price_per_million=2.00,
        output_price_per_million=10.00,
        notes="Standard API tier rate ($2.00/1M input, $10.00/1M output).",
    ),
}

EXPECTED_FROZEN_AUTHORITY_SHAS_01B: Dict[str, str] = {
    "data/evaluation/w06/w06_scenarios_freeze_v1.json": (
        "c03bc6dc300604ac395505d59b6413c1a47339b21408cfd637671e81d4b555a1"
    ),
    "data/evaluation/w06/w06_p11_assignment_manifest_v1.json": (
        "0aa9ae923d0e7f29df49735fa41e87530b1caf62418fcbec09a1eff81d83af62"
    ),
    "data/evaluation/w06/w06_dev_fixtures_freeze_v1.json": (
        "bb0f051446ea3da8229298f22f4ce92b4db20751695273c6d01b7766da044050"
    ),
    "data/evaluation/w06/w06_dev_fixture_manifest_v1.json": (
        "15cf3af6c93d3de967703dbc52d7e082bfd4a1e657409c0678ff51bd081e3c98"
    ),
    "data/evaluation/w06/w06_dev_final_overlap_receipt_v1.json": (
        "285699ee1370b537a6579b88a7fb02781b51ac52e0ed14f469d77969261f04aa"
    ),
    "data/evaluation/w06/w06_dev_fixture_freeze_01_receipt_v1.json": (
        "437a296cf123d1469f303b97cb6665cd8217c2dfeabd12d1712ec2789d890026"
    ),
    "data/evaluation/w06/w06_model_arch_selection_method_lock_v1.json": (
        "6f30cdf90355dd720795de8e0b21beba45f527767892ca7eb88769141a64210c"
    ),
    "data/evaluation/w06/w06_scenario_method_lock_v1.json": (
        "5e5359f9f10a0248a9cf031f8e8b26c0314c46aecfe0d9df479388bbe4fd1af9"
    ),
    "data/evaluation/w06/w06_scenario_support_matrix_v1.json": (
        "68c2bfc2164e664b3856c31b99a92d75a588f64465526b47c9104918a51cedb4"
    ),
    "data/evaluation/w06/w06_measurement_contract_v1.json": (
        "0ddc1f8d879493517cee25f247d2365a0bacb816dc33b129b0c6110d4bfb8298"
    ),
    "data/curated/gomate_places_freeze_v2.json": (
        "f7517938598e3923906763f8f31334a500ee88bc06232f2992d38e2fcb28a444"
    ),
    "apps/ai-service/recommendation/reca/contract.py": (
        "1a62c36a95092be35ab78dca43e20f646016e154746ee051a499bdebfc67538c"
    ),
}


def validate_candidate_identity(
    candidate_id: str,
    provider: str,
    requested_model_id: str,
) -> None:
    """Enforce frozen candidate identity (Section 1 & LB-24: NO SUBSTITUTION, NO ALIAS SWITCH, NO FALLBACK)."""
    if candidate_id not in FROZEN_CANDIDATE_SPECS:
        raise OneCallInvariantViolationError(
            f"Forbidden candidate_id {candidate_id!r}; only C1, C2, C3 are permitted."
        )
    spec = FROZEN_CANDIDATE_SPECS[candidate_id]
    if provider != spec["provider"] or requested_model_id != spec["requested_model_id"]:
        raise OneCallInvariantViolationError(
            f"Candidate substitution or alias switch forbidden for {candidate_id}: "
            f"expected ({spec['provider']!r}, {spec['requested_model_id']!r}), "
            f"got ({provider!r}, {requested_model_id!r})."
        )


def validate_live_smoke_fixture_id(scenario_id: str) -> None:
    """Enforce Section 10 (LB-02, LB-03, LB-04): ONLY W06-PREFLIGHT-SMOKE-001 is allowed in Phase 01B."""
    if scenario_id != FROZEN_LIVE_SMOKE_FIXTURE_ID:
        raise OneCallInvariantViolationError(
            f"Forbidden fixture {scenario_id!r} in Phase 01B live smoke; "
            f"ONLY {FROZEN_LIVE_SMOKE_FIXTURE_ID!r} is allowed."
        )


def get_live_smoke_001_fixture() -> Tuple[BenchmarkScenarioInput, List[BenchmarkCatalogPOI]]:
    """Return the single authorized smoke fixture W06-PREFLIGHT-SMOKE-001 and its synthetic POI catalog."""
    scenario, pois = build_synthetic_smoke_fixtures()[0]
    validate_live_smoke_fixture_id(scenario.scenario_id)
    return scenario, pois


def compute_fixture_sha256(
    scenario: BenchmarkScenarioInput,
    catalog_pois: List[BenchmarkCatalogPOI],
) -> str:
    """Compute canonical SHA256 over scenario + sorted POI catalog for W06-PREFLIGHT-SMOKE-001."""
    payload = {
        "scenario": scenario.model_dump(),
        "catalog_pois": [p.model_dump() for p in sorted(catalog_pois, key=lambda x: x.place_id)],
    }
    return sha256_bytes(canonical_json_bytes(payload))


def verify_frozen_authorities_01b(repo_root: Optional[Path] = None) -> Dict[str, str]:
    """Verify all 12 frozen scientific authorities from Section 5 are unchanged."""
    root = repo_root or REPO_ROOT
    verified: Dict[str, str] = {}
    for rel_path, expected_sha in EXPECTED_FROZEN_AUTHORITY_SHAS_01B.items():
        fpath = root / rel_path
        if not fpath.is_file():
            raise RuntimeError(f"HARNESS_ERROR: Missing frozen authority file: {rel_path}")
        actual_sha = sha256_bytes(normalize_lf_bytes(fpath.read_bytes()))
        if actual_sha != expected_sha:
            raise RuntimeError(
                f"HARNESS_ERROR: Frozen authority SHA mismatch for {rel_path}: "
                f"expected {expected_sha}, got {actual_sha}"
            )
        verified[rel_path] = actual_sha
    return verified


def build_live_smoke_plan_payload() -> Dict[str, Any]:
    """Build the deterministic pre-call live smoke plan payload (Section 11)."""
    scenario, pois = get_live_smoke_001_fixture()
    fixture_sha = compute_fixture_sha256(scenario, pois)
    user_prompt = build_shared_semantic_user_prompt(scenario, pois)
    sys_prompt_sha = sha256_bytes(PREFLIGHT_SHARED_SYSTEM_PROMPT.encode("utf-8"))
    usr_prompt_sha = sha256_bytes(user_prompt.encode("utf-8"))

    g_adapter = GooglePreflightAdapter()
    o_adapter = OpenAIPreflightAdapter()
    a_adapter = AnthropicPreflightAdapter()

    g_req = g_adapter.serialize_smoke_request(scenario, pois)
    o_req = o_adapter.serialize_smoke_request(scenario, pois)
    a_req = a_adapter.serialize_smoke_request(scenario, pois)

    # Verify all 3 candidates share identical prompt and schema hashes before freezing plan
    if not (g_req["system_prompt_sha256"] == o_req["system_prompt_sha256"] == a_req["system_prompt_sha256"] == sys_prompt_sha):
        raise RuntimeError("HARNESS_ERROR: System prompt hash mismatch across candidates.")
    if not (g_req["user_prompt_sha256"] == o_req["user_prompt_sha256"] == a_req["user_prompt_sha256"] == usr_prompt_sha):
        raise RuntimeError("HARNESS_ERROR: User prompt hash mismatch across candidates.")

    return {
        "artifact_id": "W06-MODEL-PREFLIGHT-01B-LIVE-PLAN",
        "task_id": TASK_ID_01B,
        "version": VERSION_01B,
        "base_develop_sha": EXPECTED_BASE_DEVELOP_SHA_01B,
        "architecture_id": FROZEN_ARCHITECTURE_ID,
        "architecture_class": FROZEN_ARCHITECTURE_CLASS,
        "candidate_execution_order": list(FROZEN_CANDIDATE_EXECUTION_ORDER),
        "candidate_ids": list(FROZEN_CANDIDATE_EXECUTION_ORDER),
        "requested_model_ids": {
            cid: FROZEN_CANDIDATE_SPECS[cid]["requested_model_id"]
            for cid in FROZEN_CANDIDATE_EXECUTION_ORDER
        },
        "provider_sdk_versions": {
            "C1": f"google-genai=={pkg_version('google-genai')}",
            "C2": f"openai=={pkg_version('openai')}",
            "C3": f"anthropic=={pkg_version('anthropic')}",
        },
        "endpoints": {
            cid: FROZEN_CANDIDATE_SPECS[cid]["endpoint"]
            for cid in FROZEN_CANDIDATE_EXECUTION_ORDER
        },
        "fixture_id": FROZEN_LIVE_SMOKE_FIXTURE_ID,
        "smoke_002_used": False,
        "fixture_sha256": fixture_sha,
        "system_prompt_sha256": sys_prompt_sha,
        "user_prompt_sha256": usr_prompt_sha,
        "semantic_schema_sha256": SEMANTIC_SCHEMA_SHA256,
        "common_generation_schema_sha256": COMMON_GENERATION_SCHEMA_SHA256,
        "candidate_configurations": {
            "C1": {
                "candidate_id": "C1",
                "provider": "Google",
                "model": "gemini-3.8-flash",
                "endpoint": FROZEN_CANDIDATE_SPECS["C1"]["endpoint"],
                "thinking_config": {"thinking_level": FROZEN_GOOGLE_THINKING_LEVEL},
                "seed": FROZEN_SAMPLING_SEED,
                "max_output_tokens": FROZEN_MAX_OUTPUT_TOKENS,
                "omitted_parameters": ["temperature", "top_p", "top_k", "candidate_count"],
                "response_mime_type": "application/json",
                "response_json_schema_sha256": COMMON_GENERATION_SCHEMA_SHA256,
                "tools": None,
                "automatic_function_calling_disabled": True,
                "sdk_automatic_retry": 0,
                "transport_retry": 0,
                "timeout_ms": FROZEN_TIMEOUT_MS,
            },
            "C2": {
                "candidate_id": "C2",
                "provider": "OpenAI",
                "model": "gpt-6.1-sol",
                "endpoint": FROZEN_CANDIDATE_SPECS["C2"]["endpoint"],
                "reasoning_effort": FROZEN_OPENAI_REASONING_EFFORT,
                "service_tier": FROZEN_OPENAI_SERVICE_TIER,
                "seed": FROZEN_SAMPLING_SEED,
                "max_completion_tokens": FROZEN_MAX_OUTPUT_TOKENS,
                "omitted_parameters": ["temperature", "top_p", "top_k", "top_logprobs", "logprobs", "tools"],
                "response_format": {
                    "type": "json_schema",
                    "name": "BenchmarkPlanResponse",
                    "strict": True,
                    "schema_sha256": COMMON_GENERATION_SCHEMA_SHA256,
                },
                "tools": None,
                "sdk_automatic_retry": 0,
                "transport_retry": 0,
                "timeout_seconds": FROZEN_TIMEOUT_MS / 1000.0,
            },
            "C3": {
                "candidate_id": "C3",
                "provider": "Anthropic",
                "model": "claude-sonnet-5-5",
                "endpoint": FROZEN_CANDIDATE_SPECS["C3"]["endpoint"],
                "thinking": {"type": FROZEN_CLAUDE_THINKING_MODE},
                "output_config": {
                    "effort": FROZEN_CLAUDE_EFFORT,
                    "format_type": "json_schema",
                    "schema_sha256": COMMON_GENERATION_SCHEMA_SHA256,
                },
                "max_tokens": FROZEN_MAX_OUTPUT_TOKENS,
                "omitted_parameters": ["temperature", "top_p", "top_k", "seed", "tools"],
                "tools": None,
                "fast_mode": False,
                "sdk_automatic_retry": 0,
                "transport_retry": 0,
                "timeout_seconds": FROZEN_TIMEOUT_MS / 1000.0,
            },
        },
        "max_live_generation_calls_total": FROZEN_MAX_LIVE_GENERATION_CALLS_TOTAL,
        "max_live_generation_calls_per_candidate": FROZEN_MAX_LIVE_GENERATION_CALLS_PER_CANDIDATE,
        "max_cumulative_estimated_cost_usd": FROZEN_MAX_CUMULATIVE_COST_USD,
        "automatic_retry": 0,
        "manual_retry": 0,
        "fallback": False,
        "repair": False,
        "scientific_performance_scoring_allowed": False,
        "dev_tune_allowed": False,
        "dev_select_allowed": False,
        "final_100_allowed": False,
        "user_live_authorization": True,
        "pricing_evidence": {
            cid: FROZEN_STANDARD_PRICING_SPECS[cid].model_dump()
            for cid in FROZEN_CANDIDATE_EXECUTION_ORDER
        },
    }


def write_live_smoke_plan(output_path: Path = DEFAULT_LIVE_PLAN_PATH) -> Path:
    """Write the canonical pre-call live smoke plan JSON artifact."""
    payload = build_live_smoke_plan_payload()
    write_canonical_json(output_path, payload)
    return output_path


def verify_live_plan_immutability(plan_path: Path = DEFAULT_LIVE_PLAN_PATH) -> str:
    """Verify the frozen live plan file on disk matches the canonical expected plan payload (LB-26)."""
    if not plan_path.is_file():
        raise RuntimeError(f"HARNESS_ERROR: Frozen live plan file missing at {plan_path}")
    disk_bytes = plan_path.read_bytes()
    expected_bytes = canonical_json_bytes(build_live_smoke_plan_payload())
    if disk_bytes != expected_bytes:
        raise RuntimeError(
            "HARNESS_ERROR: Frozen live plan file on disk does not match canonical live plan configuration; "
            "mutating plan/config after freeze is forbidden."
        )
    return sha256_bytes(disk_bytes)


class LiveCallBudgetTracker:
    """Fail-closed outbound HTTP generation call budget tracker (Sections 2, 3, 12, LB-05, LB-06, LB-22)."""

    def __init__(
        self,
        *,
        max_total_calls: int = FROZEN_MAX_LIVE_GENERATION_CALLS_TOTAL,
        max_calls_per_candidate: int = FROZEN_MAX_LIVE_GENERATION_CALLS_PER_CANDIDATE,
        max_cumulative_cost_usd: float = FROZEN_MAX_CUMULATIVE_COST_USD,
    ) -> None:
        self.max_total_calls = max_total_calls
        self.max_calls_per_candidate = max_calls_per_candidate
        self.max_cumulative_cost_usd = max_cumulative_cost_usd
        self.total_http_requests: int = 0
        self.per_candidate_http_requests: Dict[str, int] = {
            cid: 0 for cid in FROZEN_CANDIDATE_EXECUTION_ORDER
        }
        self.attempted_candidates: Set[str] = set()
        self.cumulative_estimated_cost_usd: float = 0.0

    def assert_can_start_candidate(self, candidate_id: str) -> None:
        """Verify candidate has not been attempted and cumulative limits have not been reached."""
        if candidate_id not in FROZEN_CANDIDATE_SPECS:
            raise OneCallInvariantViolationError(f"Unknown candidate_id: {candidate_id!r}")
        if candidate_id in self.attempted_candidates:
            raise OneCallInvariantViolationError(
                f"Candidate {candidate_id} has already been attempted; manual/second attempt is forbidden."
            )
        if self.per_candidate_http_requests.get(candidate_id, 0) >= self.max_calls_per_candidate:
            raise OneCallInvariantViolationError(
                f"Candidate {candidate_id} HTTP request count already at {self.per_candidate_http_requests[candidate_id]}."
            )
        if self.total_http_requests >= self.max_total_calls:
            raise OneCallInvariantViolationError(
                f"Total live generation HTTP request budget ({self.max_total_calls}) already reached."
            )
        if self.cumulative_estimated_cost_usd >= self.max_cumulative_cost_usd:
            raise OneCallInvariantViolationError(
                f"Cumulative estimated cost USD ({self.cumulative_estimated_cost_usd:.6f}) reached safety cap "
                f"({self.max_cumulative_cost_usd:.2f})."
            )
        self.attempted_candidates.add(candidate_id)

    def record_outbound_http_request_before_send(self, candidate_id: str) -> None:
        """Called inside CountingTransport.handle_request BEFORE sending the outbound HTTP request.

        If a second HTTP request is attempted for the same candidate (e.g., hidden retry) or total > 3,
        raises OneCallInvariantViolationError BEFORE any network packet is transmitted.
        """
        current_cand = self.per_candidate_http_requests.get(candidate_id, 0)
        if current_cand >= self.max_calls_per_candidate:
            raise OneCallInvariantViolationError(
                f"ABORT BEFORE EXTRA REQUEST: Candidate {candidate_id} attempted outbound HTTP request "
                f"#{current_cand + 1} (max_live_generation_calls_per_candidate={self.max_calls_per_candidate})."
            )
        if self.total_http_requests >= self.max_total_calls:
            raise OneCallInvariantViolationError(
                f"ABORT BEFORE EXTRA REQUEST: Total outbound HTTP request #{self.total_http_requests + 1} "
                f"exceeds max_live_generation_calls_total={self.max_total_calls}."
            )
        if self.cumulative_estimated_cost_usd >= self.max_cumulative_cost_usd:
            raise OneCallInvariantViolationError(
                f"ABORT BEFORE EXTRA REQUEST: Cumulative estimated spend ${self.cumulative_estimated_cost_usd:.6f} "
                f"reached cap ${self.max_cumulative_cost_usd:.2f}."
            )
        self.per_candidate_http_requests[candidate_id] = current_cand + 1
        self.total_http_requests += 1

    def add_estimated_cost(self, cost_usd: Optional[float]) -> None:
        if cost_usd is not None and cost_usd > 0:
            self.cumulative_estimated_cost_usd = round(
                self.cumulative_estimated_cost_usd + cost_usd, 8
            )


class CountingHttpxTransport(httpx.BaseTransport):
    """Transparent httpx.BaseTransport wrapper that counts real outbound HTTP requests and fails closed > 1."""

    def __init__(
        self,
        *,
        candidate_id: str,
        budget_tracker: LiveCallBudgetTracker,
        inner_transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        self.candidate_id = candidate_id
        self.budget_tracker = budget_tracker
        self._inner = inner_transport or httpx.HTTPTransport(retries=0)
        self.request_count: int = 0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.budget_tracker.record_outbound_http_request_before_send(self.candidate_id)
        self.request_count += 1
        return self._inner.handle_request(request)

    def close(self) -> None:
        self._inner.close()


class CountingHttpx2Transport(httpx2.BaseTransport):
    """Transparent httpx2.BaseTransport wrapper that counts real outbound HTTP requests and fails closed > 1."""

    def __init__(
        self,
        *,
        candidate_id: str,
        budget_tracker: LiveCallBudgetTracker,
        inner_transport: Optional[httpx2.BaseTransport] = None,
    ) -> None:
        self.candidate_id = candidate_id
        self.budget_tracker = budget_tracker
        self._inner = inner_transport or httpx2.HTTPTransport(retries=0)
        self.request_count: int = 0

    def handle_request(self, request: httpx2.Request) -> httpx2.Response:
        self.budget_tracker.record_outbound_http_request_before_send(self.candidate_id)
        self.request_count += 1
        return self._inner.handle_request(request)

    def close(self) -> None:
        self._inner.close()


def _load_single_candidate_api_key(
    candidate_id: str,
    *,
    dotenv_path: Optional[Path] = None,
) -> str:
    """Load a single candidate's API key in-memory without printing, logging, or exposing it."""
    env_key_name = FROZEN_CANDIDATE_SPECS[candidate_id]["env_key_name"]
    target_path = dotenv_path or (REPO_ROOT / "apps" / "ai-service" / ".env")
    if target_path.exists():
        for raw_line in target_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k_part, v_part = line.split("=", 1)
            if k_part.strip() == env_key_name:
                val = v_part.strip().strip("'").strip('"').strip()
                if val:
                    return val
    raise RuntimeError(f"Missing required secret key for {candidate_id} in local .env")


def compute_estimated_standard_api_cost_usd(
    candidate_id: str,
    usage: LiveUsageMetadataRecord,
) -> Optional[float]:
    """Compute ESTIMATED_STANDARD_API_COST_USD from authoritative provider token usage (Section 18)."""
    if (
        not usage.authoritative_usage_available
        or usage.input_tokens is None
        or usage.output_tokens is None
    ):
        return None
    pricing = FROZEN_STANDARD_PRICING_SPECS[candidate_id]
    in_tokens = int(usage.input_tokens)
    out_tokens = int(usage.output_tokens)
    # In Google Gemini API, thoughts_token_count is reported separately from candidates_token_count
    # and billed at the output token rate. In OpenAI and Anthropic, output_tokens already includes reasoning/thinking tokens.
    if candidate_id == "C1" and usage.thought_tokens is not None:
        out_tokens += int(usage.thought_tokens)
    cost = (
        (in_tokens / 1_000_000.0) * pricing.input_price_per_million
        + (out_tokens / 1_000_000.0) * pricing.output_price_per_million
    )
    return round(cost, 8)


def classify_live_exception(exc: Exception) -> LiveFailureClassification:
    """Deterministically classify a live provider/transport exception into Section 15 failure codes."""
    if isinstance(exc, OneCallInvariantViolationError):
        return LiveFailureClassification.HARNESS_ERROR
    cls_name = type(exc).__name__.lower()
    msg = (sanitize_secret_error_text(str(exc)) or "").lower()
    status_code = getattr(exc, "status_code", None) or getattr(exc, "code", None)

    if "timeout" in cls_name or "timed out" in msg or "timeout" in msg or status_code == 408:
        return LiveFailureClassification.FAILED_TIMEOUT
    if status_code == 429 or "ratelimit" in cls_name or "429" in msg or "resource_exhausted" in msg:
        return LiveFailureClassification.FAILED_HTTP_429
    if (isinstance(status_code, int) and 500 <= status_code <= 599) or "internalserver" in cls_name or "overloaded" in msg:
        return LiveFailureClassification.FAILED_HTTP_5XX
    if status_code == 401 or "authentication" in cls_name or "unauthenticated" in msg or "invalid api key" in msg or "api_key_invalid" in msg:
        return LiveFailureClassification.FAILED_AUTHENTICATION
    if status_code == 404 or "notfound" in cls_name or ("model" in msg and ("not found" in msg or "does not exist" in msg or "not supported" in msg and "v1beta/models" in msg)):
        return LiveFailureClassification.FAILED_MODEL_ACCESS
    if status_code == 403 or "permissiondenied" in cls_name:
        if "model" in msg and ("access" in msg or "not have access" in msg):
            return LiveFailureClassification.FAILED_MODEL_ACCESS
        return LiveFailureClassification.FAILED_AUTHENTICATION
    if status_code == 400 or "badrequest" in cls_name or "invalid_argument" in msg:
        if any(tok in msg for tok in ("v1/responses", "chat/completions", "endpoint", "only supported in")):
            return LiveFailureClassification.FAILED_ENDPOINT_COMPATIBILITY
        if any(tok in msg for tok in ("response_format", "json_schema", "response_json_schema", "output_config", "structured")):
            return LiveFailureClassification.FAILED_STRUCTURED_OUTPUT_COMPATIBILITY
        if any(tok in msg for tok in ("temperature", "seed", "reasoning_effort", "thinking", "service_tier", "top_p", "top_k", "max_completion_tokens", "max_output_tokens", "max_tokens", "unrecognized request argument", "unsupported parameter", "unsupported value")):
            return LiveFailureClassification.FAILED_PARAMETER_COMPATIBILITY
        if "model" in msg and ("not found" in msg or "does not exist" in msg or "invalid model" in msg):
            return LiveFailureClassification.FAILED_MODEL_ACCESS
        return LiveFailureClassification.FAILED_PARAMETER_COMPATIBILITY
    return LiveFailureClassification.FAILED_PARAMETER_COMPATIBILITY


def scan_directory_for_secret_leaks(
    target_dir: Path,
    *,
    dotenv_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Scan all files in a directory for secret patterns or raw .env values (Sections 6, 16, 24, LB-25)."""
    from app.evaluation.model_preflight.base import _load_raw_dotenv_secret_values

    leak_patterns = (
        re.compile(r"AIza[0-9A-Za-z\-_]{16,}"),
        re.compile(r"sk-ant-[0-9A-Za-z\-_]{12,}"),
        re.compile(r"sk-proj-[0-9A-Za-z\-_]{12,}"),
        re.compile(r"sk-[0-9A-Za-z]{20,}"),
        re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]{12,}=*"),
    )
    raw_secrets = _load_raw_dotenv_secret_values(dotenv_path=dotenv_path)
    affected: List[str] = []
    leak_count = 0

    if target_dir.exists():
        for fpath in sorted(target_dir.rglob("*")):
            if not fpath.is_file():
                continue
            try:
                text = fpath.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            f_leaks = 0
            for pat in leak_patterns:
                matches = pat.findall(text)
                if matches:
                    f_leaks += len(matches)
            for sec in raw_secrets:
                if sec and sec in text:
                    f_leaks += 1
            if f_leaks > 0:
                leak_count += f_leaks
                try:
                    rel = str(fpath.relative_to(REPO_ROOT)).replace("\\", "/")
                except ValueError:
                    rel = str(fpath)
                affected.append(rel)

    return {
        "secret_leak_count": leak_count,
        "affected_file_paths": sorted(affected),
    }


def _invoke_c1_google_live(
    *,
    api_key: str,
    request_payload: Dict[str, Any],
    counting_transport: CountingHttpxTransport,
) -> Tuple[Optional[str], Dict[str, Any], LiveUsageMetadataRecord, bool]:
    http_client = httpx.Client(transport=counting_transport)
    try:
        client = genai.Client(
            api_key=api_key,
            http_options=genai_types.HttpOptions(
                timeout=FROZEN_TIMEOUT_MS,
                retry_options=genai_types.HttpRetryOptions(attempts=1),
                httpx_client=http_client,
            ),
        )
        cfg = request_payload["config"]
        call_config = genai_types.GenerateContentConfig(
            system_instruction=cfg["system_instruction"],
            seed=cfg["seed"],
            thinking_config=genai_types.ThinkingConfig(
                thinking_level=cfg["thinking_config"]["thinking_level"]
            ),
            max_output_tokens=cfg["max_output_tokens"],
            response_mime_type=cfg["response_mime_type"],
            response_json_schema=cfg["response_json_schema"],
            tools=None,
            automatic_function_calling=genai_types.AutomaticFunctionCallingConfig(disable=True),
        )
        resp = client.models.generate_content(
            model=request_payload["model"],
            contents=request_payload["user_prompt"],
            config=call_config,
        )
    finally:
        http_client.close()

    raw_text = getattr(resp, "text", None)
    returned_model = getattr(resp, "model_version", None)
    candidates = getattr(resp, "candidates", None) or []
    finish_reason: Optional[str] = None
    is_refusal = False
    if candidates:
        fr_val = getattr(candidates[0], "finish_reason", None)
        finish_reason = str(fr_val.value if hasattr(fr_val, "value") else fr_val) if fr_val is not None else None
        fr_upper = (finish_reason or "").upper()
        if any(tok in fr_upper for tok in ("SAFETY", "BLOCKLIST", "PROHIBITED", "RECITATION", "REFUSAL")):
            is_refusal = True

    usage_obj = getattr(resp, "usage_metadata", None)
    in_tok = getattr(usage_obj, "prompt_token_count", None) if usage_obj else None
    out_tok = getattr(usage_obj, "candidates_token_count", None) if usage_obj else None
    thought_tok = getattr(usage_obj, "thoughts_token_count", None) if usage_obj else None
    tot_tok = getattr(usage_obj, "total_token_count", None) if usage_obj else None
    cached_tok = getattr(usage_obj, "cached_content_token_count", None) if usage_obj else None
    traffic_type = getattr(usage_obj, "traffic_type", None) if usage_obj else None
    service_tier = str(traffic_type.value if hasattr(traffic_type, "value") else traffic_type) if traffic_type else None

    usage_rec = LiveUsageMetadataRecord(
        input_tokens=in_tok,
        output_tokens=out_tok,
        total_tokens=tot_tok,
        reasoning_tokens=None,
        thought_tokens=thought_tok,
        cached_content_token_count=cached_tok,
        authoritative_usage_available=(in_tok is not None and out_tok is not None and tot_tok is not None),
    )
    meta = {
        "returned_model_id": returned_model,
        "resolved_model_version": returned_model,
        "system_fingerprint": None,
        "service_tier": service_tier,
        "finish_or_stop_reason": finish_reason,
        "response_id": getattr(resp, "response_id", None),
        "thinking_level": FROZEN_GOOGLE_THINKING_LEVEL,
        "seed_sent": FROZEN_SAMPLING_SEED,
        "seed_acceptance_status": "ACCEPTED_BY_LIVE_ENDPOINT",
    }
    return raw_text, meta, usage_rec, is_refusal


def _invoke_c2_openai_live(
    *,
    api_key: str,
    request_payload: Dict[str, Any],
    counting_transport: CountingHttpx2Transport,
) -> Tuple[Optional[str], Dict[str, Any], LiveUsageMetadataRecord, bool]:
    http_client = httpx2.Client(transport=counting_transport)
    try:
        client = openai.OpenAI(
            api_key=api_key,
            max_retries=0,
            timeout=FROZEN_TIMEOUT_MS / 1000.0,
            http_client=http_client,
        )
        cfg = request_payload["config"]
        resp = client.chat.completions.create(
            model=request_payload["model"],
            messages=cfg["messages"],
            seed=cfg["seed"],
            reasoning_effort=cfg["reasoning_effort"],
            service_tier=cfg["service_tier"],
            max_completion_tokens=cfg["max_completion_tokens"],
            response_format=cfg["response_format"],
        )
    finally:
        http_client.close()

    returned_model = getattr(resp, "model", None)
    sys_fp = getattr(resp, "system_fingerprint", None)
    srv_tier = getattr(resp, "service_tier", None)
    choices = getattr(resp, "choices", None) or []
    raw_text: Optional[str] = None
    finish_reason: Optional[str] = None
    is_refusal = False
    if choices:
        finish_reason = getattr(choices[0], "finish_reason", None)
        msg = getattr(choices[0], "message", None)
        if msg is not None:
            refusal_val = getattr(msg, "refusal", None)
            if isinstance(refusal_val, str) and refusal_val.strip():
                is_refusal = True
                raw_text = refusal_val
            else:
                raw_text = getattr(msg, "content", None)

    usage_obj = getattr(resp, "usage", None)
    in_tok = getattr(usage_obj, "prompt_tokens", None) if usage_obj else None
    out_tok = getattr(usage_obj, "completion_tokens", None) if usage_obj else None
    tot_tok = getattr(usage_obj, "total_tokens", None) if usage_obj else None
    comp_details = getattr(usage_obj, "completion_tokens_details", None) if usage_obj else None
    reas_tok = getattr(comp_details, "reasoning_tokens", None) if comp_details else None
    prompt_details = getattr(usage_obj, "prompt_tokens_details", None) if usage_obj else None
    cached_tok = getattr(prompt_details, "cached_tokens", None) if prompt_details else None

    usage_rec = LiveUsageMetadataRecord(
        input_tokens=in_tok,
        output_tokens=out_tok,
        total_tokens=tot_tok,
        reasoning_tokens=reas_tok,
        thought_tokens=None,
        cached_content_token_count=cached_tok,
        authoritative_usage_available=(in_tok is not None and out_tok is not None and tot_tok is not None),
    )
    meta = {
        "returned_model_id": returned_model,
        "resolved_model_version": returned_model,
        "system_fingerprint": sys_fp,
        "service_tier": srv_tier,
        "finish_or_stop_reason": finish_reason,
        "response_id": getattr(resp, "id", None),
        "reasoning_effort": FROZEN_OPENAI_REASONING_EFFORT,
        "seed_sent": FROZEN_SAMPLING_SEED,
        "seed_acceptance_status": "ACCEPTED_BY_LIVE_ENDPOINT",
    }
    return raw_text, meta, usage_rec, is_refusal


def _invoke_c3_anthropic_live(
    *,
    api_key: str,
    request_payload: Dict[str, Any],
    counting_transport: CountingHttpx2Transport,
) -> Tuple[Optional[str], Dict[str, Any], LiveUsageMetadataRecord, bool]:
    http_client = httpx2.Client(transport=counting_transport)
    try:
        client = anthropic.Anthropic(
            api_key=api_key,
            max_retries=0,
            timeout=FROZEN_TIMEOUT_MS / 1000.0,
            http_client=http_client,
        )
        cfg = request_payload["config"]
        resp = client.messages.create(
            model=request_payload["model"],
            system=cfg["system"],
            messages=cfg["messages"],
            max_tokens=cfg["max_tokens"],
            thinking=cfg["thinking"],
            output_config=cfg["output_config"],
        )
    finally:
        http_client.close()

    returned_model = getattr(resp, "model", None)
    stop_reason = getattr(resp, "stop_reason", None)
    is_refusal = str(stop_reason or "").lower() == "refusal"

    content_blocks = getattr(resp, "content", None) or []
    text_parts: List[str] = []
    for block in content_blocks:
        b_type = getattr(block, "type", None) or (block.get("type") if isinstance(block, dict) else None)
        if b_type == "text":
            b_text = getattr(block, "text", None) or (block.get("text") if isinstance(block, dict) else None)
            if isinstance(b_text, str):
                text_parts.append(b_text)
    raw_text = "".join(text_parts) if text_parts else None

    usage_obj = getattr(resp, "usage", None)
    in_tok = getattr(usage_obj, "input_tokens", None) if usage_obj else None
    out_tok = getattr(usage_obj, "output_tokens", None) if usage_obj else None
    tot_tok = (in_tok + out_tok) if (in_tok is not None and out_tok is not None) else None
    cache_read = getattr(usage_obj, "cache_read_input_tokens", None) if usage_obj else None
    cache_create = getattr(usage_obj, "cache_creation_input_tokens", None) if usage_obj else None
    srv_tier = getattr(usage_obj, "service_tier", None) if usage_obj else None

    usage_rec = LiveUsageMetadataRecord(
        input_tokens=in_tok,
        output_tokens=out_tok,
        total_tokens=tot_tok,
        reasoning_tokens=None,
        thought_tokens=None,
        cache_read_input_tokens=cache_read,
        cache_creation_input_tokens=cache_create,
        authoritative_usage_available=(in_tok is not None and out_tok is not None and tot_tok is not None),
    )
    meta = {
        "returned_model_id": returned_model,
        "resolved_model_version": returned_model,
        "system_fingerprint": None,
        "service_tier": srv_tier,
        "finish_or_stop_reason": stop_reason,
        "response_id": getattr(resp, "id", None),
        "thinking_mode": FROZEN_CLAUDE_THINKING_MODE,
        "effort": FROZEN_CLAUDE_EFFORT,
        "seed_sent": None,
        "seed_acceptance_status": "UNSUPPORTED_OMITTED",
    }
    return raw_text, meta, usage_rec, is_refusal


def execute_single_candidate_live_smoke(
    *,
    candidate_id: str,
    budget_tracker: LiveCallBudgetTracker,
    confirm_live: bool,
    artifact_root_dir: Path = DEFAULT_LIVE_ARTIFACTS_DIR,
    plan_path: Path = DEFAULT_LIVE_PLAN_PATH,
    dotenv_path: Optional[Path] = None,
    inner_transport_override: Optional[Any] = None,
) -> LiveCandidateExecutionRecord:
    """Execute at most 1 generation request for a candidate and persist sanitized technical evidence."""
    if not confirm_live:
        raise LiveProviderCallForbiddenError(
            "Explicit confirmation (--confirm-live / confirm_live=True) is required for Phase 01B live execution."
        )

    spec = FROZEN_CANDIDATE_SPECS.get(candidate_id)
    if spec is None:
        raise OneCallInvariantViolationError(f"Forbidden candidate_id: {candidate_id!r}")
    validate_candidate_identity(candidate_id, spec["provider"], spec["requested_model_id"])

    # Pre-request invariant checks (Section 13)
    budget_tracker.assert_can_start_candidate(candidate_id)
    verify_live_plan_immutability(plan_path=plan_path)
    verify_frozen_authorities_01b()

    key_presence = check_dotenv_key_presence(dotenv_path=dotenv_path)
    if any(v != "PRESENT" for v in key_presence.values()):
        raise RuntimeError(f"HARNESS_ERROR: Missing required .env keys: {key_presence}")

    tracked_scan = scan_tracked_files_for_secret_leaks()
    if tracked_scan["secret_leak_count"] != 0:
        raise RuntimeError("HARNESS_ERROR: Tracked secret scan failed before candidate execution.")

    scenario, pois = get_live_smoke_001_fixture()
    validate_live_smoke_fixture_id(scenario.scenario_id)

    adapters = {
        "C1": GooglePreflightAdapter(live_allowed=True),
        "C2": OpenAIPreflightAdapter(live_allowed=True),
        "C3": AnthropicPreflightAdapter(live_allowed=True),
    }
    adapter = adapters[candidate_id]
    request_payload = adapter.serialize_smoke_request(scenario, pois)

    cand_dir = artifact_root_dir / candidate_id
    cand_dir.mkdir(parents=True, exist_ok=True)

    # Persist sanitized request_manifest.json (never includes credentials or HTTP headers)
    request_manifest = {
        "task_id": TASK_ID_01B,
        "candidate_id": candidate_id,
        "provider": spec["provider"],
        "requested_model_id": spec["requested_model_id"],
        "endpoint": spec["endpoint"],
        "fixture_id": scenario.scenario_id,
        "fixture_sha256": compute_fixture_sha256(scenario, pois),
        "system_prompt_sha256": request_payload["system_prompt_sha256"],
        "user_prompt_sha256": request_payload["user_prompt_sha256"],
        "semantic_schema_sha256": request_payload["semantic_schema_sha256"],
        "common_generation_schema_sha256": request_payload["common_generation_schema_sha256"],
        "config_summary": {
            k: v
            for k, v in request_payload["config"].items()
            if k not in ("messages", "system_instruction", "system", "response_json_schema", "response_format", "output_config")
        },
    }
    write_canonical_json(cand_dir / "request_manifest.json", request_manifest)

    api_key = _load_single_candidate_api_key(candidate_id, dotenv_path=dotenv_path)
    pricing = FROZEN_STANDARD_PRICING_SPECS[candidate_id]

    if candidate_id == "C1":
        c_transport: Any = CountingHttpxTransport(
            candidate_id="C1",
            budget_tracker=budget_tracker,
            inner_transport=inner_transport_override,
        )
    else:
        c_transport = CountingHttpx2Transport(
            candidate_id=candidate_id,
            budget_tracker=budget_tracker,
            inner_transport=inner_transport_override,
        )

    t_start = time.perf_counter()
    try:
        if candidate_id == "C1":
            raw_text, meta, usage_rec, is_refusal = _invoke_c1_google_live(
                api_key=api_key,
                request_payload=request_payload,
                counting_transport=c_transport,
            )
        elif candidate_id == "C2":
            raw_text, meta, usage_rec, is_refusal = _invoke_c2_openai_live(
                api_key=api_key,
                request_payload=request_payload,
                counting_transport=c_transport,
            )
        else:
            raw_text, meta, usage_rec, is_refusal = _invoke_c3_anthropic_live(
                api_key=api_key,
                request_payload=request_payload,
                counting_transport=c_transport,
            )
    except Exception as exc:
        t_end = time.perf_counter()
        latency_ms = round((t_end - t_start) * 1000.0, 3)
        if isinstance(exc, OneCallInvariantViolationError):
            raise
        failure_cls = classify_live_exception(exc)
        safe_err = sanitize_secret_error_text(f"{type(exc).__name__}: {exc}", dotenv_path=dotenv_path)
        empty_usage = LiveUsageMetadataRecord(authoritative_usage_available=False)

        seed_status = "UNSUPPORTED_OMITTED" if candidate_id == "C3" else (
            "REJECTED_BY_LIVE_ENDPOINT"
            if (failure_cls == LiveFailureClassification.FAILED_PARAMETER_COMPATIBILITY and "seed" in (safe_err or "").lower())
            else "NOT_CONFIRMED_DUE_TO_REQUEST_FAILURE"
        )
        write_exact_utf8_text(cand_dir / "raw_provider_response.txt", "")
        write_canonical_json(
            cand_dir / "provider_response_metadata.json",
            {
                "candidate_id": candidate_id,
                "provider": spec["provider"],
                "requested_model_id": spec["requested_model_id"],
                "returned_model_id": None,
                "failure_classification": failure_cls.value,
                "error_detail_sanitized": safe_err,
                "latency_ms": latency_ms,
                "actual_http_request_count": c_transport.request_count,
            },
        )
        rec = LiveCandidateExecutionRecord(
            candidate_id=candidate_id,
            attempted=True,
            actual_http_request_count=c_transport.request_count,
            provider=spec["provider"],
            requested_model_id=spec["requested_model_id"],
            returned_model_id=None,
            resolved_model_version=None,
            system_fingerprint=None,
            service_tier=None,
            reasoning_effort=FROZEN_OPENAI_REASONING_EFFORT if candidate_id == "C2" else None,
            thinking_mode=(
                FROZEN_GOOGLE_THINKING_LEVEL
                if candidate_id == "C1"
                else (FROZEN_CLAUDE_THINKING_MODE if candidate_id == "C3" else None)
            ),
            effort=FROZEN_CLAUDE_EFFORT if candidate_id == "C3" else None,
            seed_acceptance_status=seed_status,
            status=CandidateFinalPreflightStatus.FAILED_TECHNICAL_PREFLIGHT,
            live_preflight_status="FAILED_LIVE_PREFLIGHT",
            failure_classification=failure_cls,
            error_detail_sanitized=safe_err,
            schema_valid=False,
            raw_artifact_preserved=False,
            raw_response_sha256=None,
            parsed_response_sha256=None,
            sanitization_occurred_in_raw_response=False,
            usage_metadata=empty_usage,
            latency_ms=latency_ms,
            finish_or_stop_reason=None,
            pricing_source_url=pricing.pricing_source_url,
            pricing_access_date=pricing.pricing_access_date,
            input_price_per_million=pricing.input_price_per_million,
            output_price_per_million=pricing.output_price_per_million,
            authoritative_usage_available=False,
            estimated_standard_api_cost_usd=None,
            blockers=[f"{failure_cls.value}: {safe_err}"],
        )
        write_canonical_json(cand_dir / "execution_receipt.json", rec.model_dump())
        return rec

    t_end = time.perf_counter()
    latency_ms = round((t_end - t_start) * 1000.0, 3)

    raw_str_unsanitized = raw_text if isinstance(raw_text, str) else ""
    raw_str_sanitized = sanitize_secret_error_text(raw_str_unsanitized, dotenv_path=dotenv_path) or ""
    sanitization_occurred = raw_str_sanitized != raw_str_unsanitized
    raw_sha256 = sha256_bytes(raw_str_sanitized.encode("utf-8"))
    write_exact_utf8_text(cand_dir / "raw_provider_response.txt", raw_str_sanitized)

    est_cost = compute_estimated_standard_api_cost_usd(candidate_id, usage_rec)
    budget_tracker.add_estimated_cost(est_cost)

    returned_model_id = meta.get("returned_model_id")
    finish_reason = meta.get("finish_or_stop_reason")

    write_canonical_json(
        cand_dir / "provider_response_metadata.json",
        {
            "candidate_id": candidate_id,
            "provider": spec["provider"],
            "requested_model_id": spec["requested_model_id"],
            "returned_model_id": returned_model_id,
            "resolved_model_version": meta.get("resolved_model_version"),
            "system_fingerprint": meta.get("system_fingerprint"),
            "service_tier": meta.get("service_tier"),
            "finish_or_stop_reason": finish_reason,
            "latency_ms": latency_ms,
            "actual_http_request_count": c_transport.request_count,
            "usage_metadata": usage_rec.model_dump(),
            "estimated_standard_api_cost_usd": est_cost,
            "seed_acceptance_status": meta.get("seed_acceptance_status"),
        },
    )

    # Technical Pass/Fail evaluation (Section 14 — NO scientific evaluator!)
    failure_cls = LiveFailureClassification.NONE
    err_detail: Optional[str] = None
    schema_valid = False
    parsed_sha256: Optional[str] = None
    blockers: List[str] = []

    # 1. Check HTTP request count == 1
    if c_transport.request_count != 1:
        failure_cls = LiveFailureClassification.HARNESS_ERROR
        err_detail = f"Expected actual_http_request_count == 1, got {c_transport.request_count}"
        blockers.append(err_detail)

    # 2. Check returned model metadata integrity
    if failure_cls == LiveFailureClassification.NONE:
        model_ok, model_err = verify_model_metadata_integrity(
            candidate_id=candidate_id,
            requested_model_id=spec["requested_model_id"],
            returned_model_id=returned_model_id,
            raise_on_mismatch=False,
        )
        if not model_ok:
            failure_cls = LiveFailureClassification.FAILED_MODEL_ID_INTEGRITY
            err_detail = sanitize_secret_error_text(model_err, dotenv_path=dotenv_path)
            blockers.append(err_detail or "Model ID mismatch")

    # 3. Check refusal
    if failure_cls == LiveFailureClassification.NONE and is_refusal:
        failure_cls = LiveFailureClassification.FAILED_REFUSAL
        err_detail = f"Provider returned refusal response (finish_or_stop_reason={finish_reason!r})."
        blockers.append(err_detail)

    # 4. Check max_tokens / truncation
    if failure_cls == LiveFailureClassification.NONE:
        fr_norm = str(finish_reason or "").strip().lower()
        if fr_norm in ("max_tokens", "length", "FinishReason.MAX_TOKENS".lower()):
            failure_cls = LiveFailureClassification.FAILED_MAX_TOKENS
            err_detail = f"Output truncated due to max_tokens (finish_or_stop_reason={finish_reason!r})."
            blockers.append(err_detail)

    # 5. Check authoritative usage metadata
    if failure_cls == LiveFailureClassification.NONE and not usage_rec.authoritative_usage_available:
        failure_cls = LiveFailureClassification.FAILED_USAGE_METADATA
        err_detail = "Authoritative token usage metadata missing from provider response."
        blockers.append(err_detail)

    # 6. Check strict JSON & BenchmarkPlanResponse.model_validate (zero repair, zero code-fence cleanup)
    if failure_cls == LiveFailureClassification.NONE:
        try:
            decoded_json = json.loads(raw_str_sanitized)
            BenchmarkPlanResponse.model_validate(decoded_json)
            parsed_plan = parse_strict_benchmark_plan_response(
                raw_data=decoded_json,
                scenario=scenario,
                plan_id=decoded_json.get("plan_id") or f"live-smoke-{candidate_id.lower()}",
            )
            schema_valid = True
            parsed_dump = parsed_plan.model_dump()
            parsed_sha256 = sha256_bytes(canonical_json_bytes(parsed_dump))
            write_canonical_json(cand_dir / "parsed_plan_response.json", parsed_dump)
        except (json.JSONDecodeError, ValidationError, ValueError, TypeError, KeyError) as val_exc:
            failure_cls = LiveFailureClassification.FAILED_SCHEMA_OUTPUT
            err_detail = sanitize_secret_error_text(
                f"Strict JSON / BenchmarkPlanResponse validation failed: {type(val_exc).__name__}: {val_exc}",
                dotenv_path=dotenv_path,
            )
            blockers.append(err_detail or "Schema validation failed")

    # 7. Check artifact secret scan
    cand_secret_scan = scan_directory_for_secret_leaks(cand_dir, dotenv_path=dotenv_path)
    if cand_secret_scan["secret_leak_count"] != 0 or sanitization_occurred:
        if cand_secret_scan["secret_leak_count"] != 0:
            failure_cls = LiveFailureClassification.FAILED_SECRET_SAFETY
            err_detail = "Secret pattern detected in candidate artifact directory."
            blockers.append(err_detail)

    passed = failure_cls == LiveFailureClassification.NONE and schema_valid
    final_status = (
        CandidateFinalPreflightStatus.PASSED_TECHNICAL_PREFLIGHT
        if passed
        else CandidateFinalPreflightStatus.FAILED_TECHNICAL_PREFLIGHT
    )
    live_status_str = "PASS_LIVE_PREFLIGHT" if passed else failure_cls.value

    rec = LiveCandidateExecutionRecord(
        candidate_id=candidate_id,
        attempted=True,
        actual_http_request_count=c_transport.request_count,
        provider=spec["provider"],
        requested_model_id=spec["requested_model_id"],
        returned_model_id=returned_model_id,
        resolved_model_version=meta.get("resolved_model_version"),
        system_fingerprint=meta.get("system_fingerprint"),
        service_tier=meta.get("service_tier"),
        reasoning_effort=FROZEN_OPENAI_REASONING_EFFORT if candidate_id == "C2" else None,
        thinking_mode=(
            FROZEN_GOOGLE_THINKING_LEVEL
            if candidate_id == "C1"
            else (FROZEN_CLAUDE_THINKING_MODE if candidate_id == "C3" else None)
        ),
        effort=FROZEN_CLAUDE_EFFORT if candidate_id == "C3" else None,
        seed_acceptance_status=meta.get("seed_acceptance_status"),
        status=final_status,
        live_preflight_status=live_status_str,
        failure_classification=failure_cls,
        error_detail_sanitized=err_detail,
        schema_valid=schema_valid,
        raw_artifact_preserved=True,
        raw_response_sha256=raw_sha256,
        parsed_response_sha256=parsed_sha256,
        sanitization_occurred_in_raw_response=sanitization_occurred,
        usage_metadata=usage_rec,
        latency_ms=latency_ms,
        finish_or_stop_reason=finish_reason,
        pricing_source_url=pricing.pricing_source_url,
        pricing_access_date=pricing.pricing_access_date,
        input_price_per_million=pricing.input_price_per_million,
        output_price_per_million=pricing.output_price_per_million,
        authoritative_usage_available=usage_rec.authoritative_usage_available,
        estimated_standard_api_cost_usd=est_cost,
        blockers=blockers,
    )
    write_canonical_json(cand_dir / "execution_receipt.json", rec.model_dump())
    return rec


def run_live_smoke_suite(
    *,
    confirm_live: bool = False,
    live_plan_commit_sha: Optional[str] = None,
    transport_overrides: Optional[Dict[str, Any]] = None,
    artifact_root_dir: Path = DEFAULT_LIVE_ARTIFACTS_DIR,
    receipt_path: Path = DEFAULT_LIVE_RECEIPT_PATH,
    plan_path: Path = DEFAULT_LIVE_PLAN_PATH,
    dotenv_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Execute the complete W06-MODEL-PREFLIGHT-01B-LIVE-SMOKE suite in fixed order C1 -> C2 -> C3."""
    if not confirm_live:
        raise LiveProviderCallForbiddenError(
            "LIVE_PROVIDER_CALL_FORBIDDEN: run_live_smoke_suite requires confirm_live=True (--confirm-live)."
        )

    plan_sha256 = verify_live_plan_immutability(plan_path=plan_path)
    frozen_authorities = verify_frozen_authorities_01b()
    key_presence = check_dotenv_key_presence(dotenv_path=dotenv_path)
    if any(v != "PRESENT" for v in key_presence.values()):
        raise RuntimeError(f"HARNESS_ERROR: Missing required keys in .env: {key_presence}")

    budget_tracker = LiveCallBudgetTracker()
    candidate_records: Dict[str, Dict[str, Any]] = {}

    for cid in FROZEN_CANDIDATE_EXECUTION_ORDER:
        override = (transport_overrides or {}).get(cid)
        rec = execute_single_candidate_live_smoke(
            candidate_id=cid,
            budget_tracker=budget_tracker,
            confirm_live=confirm_live,
            artifact_root_dir=artifact_root_dir,
            plan_path=plan_path,
            dotenv_path=dotenv_path,
            inner_transport_override=override,
        )
        candidate_records[cid] = rec.model_dump()
        if rec.failure_classification == LiveFailureClassification.HARNESS_ERROR:
            raise RuntimeError(f"HARNESS_ERROR during {cid} execution: {rec.error_detail_sanitized}")

    tracked_scan = scan_tracked_files_for_secret_leaks()
    artifact_scan = scan_directory_for_secret_leaks(artifact_root_dir, dotenv_path=dotenv_path)

    total_cost = round(budget_tracker.cumulative_estimated_cost_usd, 8)
    all_blockers: List[str] = []
    for cid in FROZEN_CANDIDATE_EXECUTION_ORDER:
        for b in candidate_records[cid]["blockers"]:
            all_blockers.append(f"[{cid}] {b}")

    receipt_payload: Dict[str, Any] = {
        "artifact_id": "W06-MODEL-PREFLIGHT-01B-LIVE-RECEIPT",
        "task_id": TASK_ID_01B,
        "version": VERSION_01B,
        "base_develop_sha": EXPECTED_BASE_DEVELOP_SHA_01B,
        "live_plan_commit_sha": live_plan_commit_sha,
        "live_plan_sha256": plan_sha256,
        "live_result_commit_sha": None,
        "user_live_authorization": True,
        "live_provider_calls_allowed": True,
        "max_live_generation_calls_total": FROZEN_MAX_LIVE_GENERATION_CALLS_TOTAL,
        "max_live_generation_calls_per_candidate": FROZEN_MAX_LIVE_GENERATION_CALLS_PER_CANDIDATE,
        "actual_live_generation_calls_total": budget_tracker.total_http_requests,
        "automatic_retry": 0,
        "manual_retry": 0,
        "fallback": False,
        "llm_repair": 0,
        "scientific_evaluator_invoked": False,
        "dev_tune_started": False,
        "dev_select_started": False,
        "winning_model_selected": False,
        "final_100_used": False,
        "final_benchmark_started": False,
        "preregistered": False,
        "fixture_id": FROZEN_LIVE_SMOKE_FIXTURE_ID,
        "smoke_002_used": False,
        "semantic_schema_sha256": SEMANTIC_SCHEMA_SHA256,
        "common_generation_schema_sha256": COMMON_GENERATION_SCHEMA_SHA256,
        "env_key_presence": key_presence,
        "tracked_secret_scan": tracked_scan,
        "artifact_secret_scan": artifact_scan,
        "total_estimated_standard_api_cost_usd": total_cost,
        "candidates": candidate_records,
        "passed_technical_preflight_candidates": [
            cid
            for cid in FROZEN_CANDIDATE_EXECUTION_ORDER
            if candidate_records[cid]["status"] == CandidateFinalPreflightStatus.PASSED_TECHNICAL_PREFLIGHT.value
        ],
        "failed_technical_preflight_candidates": [
            cid
            for cid in FROZEN_CANDIDATE_EXECUTION_ORDER
            if candidate_records[cid]["status"] == CandidateFinalPreflightStatus.FAILED_TECHNICAL_PREFLIGHT.value
        ],
        "blockers": all_blockers,
        "frozen_authority_preservation": frozen_authorities,
    }
    write_canonical_json(receipt_path, receipt_payload)
    return receipt_payload


def main() -> None:
    parser = argparse.ArgumentParser(description="W06-MODEL-PREFLIGHT-01B-LIVE-SMOKE CLI")
    parser.add_argument("--write-plan", action="store_true", help="Write frozen live smoke plan JSON.")
    parser.add_argument("--execute-live", action="store_true", help="Execute the 3 live smoke requests.")
    parser.add_argument("--confirm-live", action="store_true", help="Explicit user live confirmation flag.")
    parser.add_argument("--live-plan-commit-sha", type=str, default=None, help="Git commit SHA of frozen live plan.")
    args = parser.parse_args()

    if args.write_plan:
        p = write_live_smoke_plan()
        print(f"WROTE_LIVE_PLAN={p} SHA256={sha256_bytes(p.read_bytes())}")
        return

    if args.execute_live:
        receipt = run_live_smoke_suite(
            confirm_live=bool(args.confirm_live),
            live_plan_commit_sha=args.live_plan_commit_sha,
        )
        print(
            json.dumps(
                {
                    "actual_live_generation_calls_total": receipt["actual_live_generation_calls_total"],
                    "total_estimated_standard_api_cost_usd": receipt["total_estimated_standard_api_cost_usd"],
                    "passed": receipt["passed_technical_preflight_candidates"],
                    "failed": receipt["failed_technical_preflight_candidates"],
                },
                indent=2,
            )
        )
        return

    parser.error("Specify either --write-plan or --execute-live --confirm-live")


if __name__ == "__main__":
    main()
