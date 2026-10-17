"""W06-MODEL-PREFLIGHT-01D-PORTABLE-SCHEMA-LIVE-REVALIDATION — Frozen V2 Live Revalidation Plan,
Counting Transport, 1-Call Budget Enforcement, Dual-Layer (Strict JSON + Semantic Pydantic)
Technical Pass/Fail Classifier, and Sanitized Artifact Persistence.

STRICT INVARIANTS (Sections 0–28):
- Architecture: LLM_BASED_ITINERARY_PLANNER_WITH_DETERMINISTIC_GROUNDING_AND_VALIDATION_V1
- Candidates (frozen, no substitution, no alias switch, no fallback):
  - C1: Google / gemini-3.8-flash
  - C2: OpenAI / gpt-6.1-sol
  - C3: Anthropic / claude-sonnet-5-5
- Live budget:
  - MAX_LIVE_GENERATION_CALLS_TOTAL = 3
  - MAX_LIVE_GENERATION_CALLS_PER_CANDIDATE = 1
  - automatic_retry = 0, transport_retry = 0, manual_retry = 0, fallback = False, llm_repair = 0, tools = False
- Experimental difference from 01B:
  - ONLY model-input contract change: COMMON_GENERATION_SCHEMA_V1 -> COMMON_PORTABLE_GENERATION_SCHEMA_V2
  - Fixture (W06-PREFLIGHT-SMOKE-001), system prompt, user prompt, sampling/reasoning parameters,
    max_output_tokens, and timeouts remain identical to 01B.
- Dual-layer validation (Section 18):
  - Layer 1: Constrained generation under COMMON_PORTABLE_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA_V2 + strict json.loads
  - Layer 2: Mandatory semantic validation via BenchmarkPlanResponse.model_validate & parse_strict_benchmark_plan_response
  - If JSON satisfies V2 but violates semantic Pydantic constraints -> FAILED_SEMANTIC_SCHEMA_VALIDATION (no repair).
- Historical 01B and 01C artifacts remain completely immutable.
"""
import argparse
from enum import Enum
from importlib.metadata import version as pkg_version
import json
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.evaluation.model_preflight.anthropic_adapter import AnthropicPreflightAdapter
from app.evaluation.model_preflight.base import (
    PREFLIGHT_SHARED_SYSTEM_PROMPT,
    build_shared_semantic_user_prompt,
    check_dotenv_key_presence,
    sanitize_secret_error_text,
    scan_tracked_files_for_secret_leaks,
    verify_model_metadata_integrity,
)
from app.evaluation.model_preflight.google_adapter import GooglePreflightAdapter
from app.evaluation.model_preflight.live_smoke import (
    EXPECTED_FROZEN_AUTHORITY_SHAS_01B,
    FROZEN_CANDIDATE_EXECUTION_ORDER,
    FROZEN_CANDIDATE_SPECS,
    FROZEN_STANDARD_PRICING_SPECS,
    CountingHttpx2Transport,
    CountingHttpxTransport,
    LiveCallBudgetTracker,
    _invoke_c1_google_live,
    _invoke_c2_openai_live,
    _invoke_c3_anthropic_live,
    _load_single_candidate_api_key,
    classify_live_exception,
    compute_estimated_standard_api_cost_usd,
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
    LiveProviderCallForbiddenError,
    LiveUsageMetadataRecord,
    OneCallInvariantViolationError,
)
from app.prompts.planner_benchmark_prompt import REPO_ROOT
from app.schemas.planner_benchmark import BenchmarkPlanResponse
from app.services.planner_benchmark_runner import (
    canonical_json_bytes,
    normalize_lf_bytes,
    parse_strict_benchmark_plan_response,
    sha256_bytes,
    write_canonical_json,
    write_exact_utf8_text,
)

TASK_ID_01D: str = "W06-MODEL-PREFLIGHT-01D-PORTABLE-SCHEMA-LIVE-REVALIDATION"
VERSION_01D: str = "1.0.0"
EXPECTED_BASE_DEVELOP_SHA_01D: str = "a55d8802f958a909095b1bff39e665179c2c205e"

EXPECTED_SEMANTIC_SCHEMA_SHA256_01D: str = (
    "e4169f7b890f77d13af65e9f2070b6071c535b206d88440f5e8f28c179977555"
)
EXPECTED_GENERATION_SCHEMA_V1_SHA256_01D: str = (
    "5f7331eb1ac137a42b75a0c307107e3305703d4782ddffdcfe98c1b5ae11c27c"
)
EXPECTED_PORTABLE_GENERATION_SCHEMA_V2_SHA256_01D: str = (
    "825a4ff912d851a95f7392cb564b7d7ca3588135508dc6eb3ac6304cdde3c490"
)
EXPECTED_HISTORICAL_01B_PLAN_SHA256_01D: str = (
    "3c59a1fba4faa7463c2a068a230ee492437713a78337b2e904980cf13c58f712"
)

DEFAULT_LIVE_PLAN_V2_PATH: Path = (
    REPO_ROOT / "data" / "evaluation" / "w06" / "w06_model_preflight_01d_v2_live_plan_v1.json"
)
DEFAULT_LIVE_RECEIPT_V2_PATH: Path = (
    REPO_ROOT / "data" / "evaluation" / "w06" / "w06_model_preflight_01d_v2_live_receipt_v1.json"
)
DEFAULT_LIVE_ARTIFACTS_V2_DIR: Path = (
    REPO_ROOT / "data" / "evaluation" / "w06" / "model_preflight_01d_v2_live"
)
HISTORICAL_01B_PLAN_PATH: Path = (
    REPO_ROOT / "data" / "evaluation" / "w06" / "w06_model_preflight_01b_live_plan_v1.json"
)

EXPECTED_FROZEN_AUTHORITY_SHAS_01D: Dict[str, str] = {
    **EXPECTED_FROZEN_AUTHORITY_SHAS_01B,
    "apps/ai-service/app/schemas/planner_benchmark.py": (
        "3f27ed7e12b2492d722937d4f36476e8dbf97635c281a6e270fd0621cc18e712"
    ),
}

EXPECTED_HISTORICAL_01B_EVIDENCE_SHAS: Dict[str, str] = {
    "data/evaluation/w06/w06_model_preflight_01b_live_plan_v1.json": (
        "3c59a1fba4faa7463c2a068a230ee492437713a78337b2e904980cf13c58f712"
    ),
    "data/evaluation/w06/w06_model_preflight_01b_live_receipt_v1.json": (
        "06e7e848612a333b4bc3f73a2a6722b94247ece6b337555d7ec458bdfa8cedbb"
    ),
    "data/evaluation/w06/model_preflight_01b_live/C1/execution_receipt.json": (
        "0689033a8b44a4e979189fc124f35b705497cbdfbaf970a8dbd4521acadf491d"
    ),
    "data/evaluation/w06/model_preflight_01b_live/C1/parsed_plan_response.json": (
        "87e4e4135105f435aa815579ad31fe11c12d2a330c74cddfad67ccdb9bb9f199"
    ),
    "data/evaluation/w06/model_preflight_01b_live/C1/provider_response_metadata.json": (
        "ee9044e483c7aa3dc5ad77602d374891fbcb0dac495a33393ab8f0a164b535ba"
    ),
    "data/evaluation/w06/model_preflight_01b_live/C1/raw_provider_response.txt": (
        "79f38f8bc3814795f7403715201ab2331f122596d0a7b916f46b66bb7a9bb941"
    ),
    "data/evaluation/w06/model_preflight_01b_live/C1/request_manifest.json": (
        "967bbb04d295253dd32afbaca034c6176d1489e363312b92e7445eb8f5df252c"
    ),
    "data/evaluation/w06/model_preflight_01b_live/C2/execution_receipt.json": (
        "8cb25012b81ac4f9d594b2a0ed9a22ae1da581c97910c88c751435fbe092283c"
    ),
    "data/evaluation/w06/model_preflight_01b_live/C2/parsed_plan_response.json": (
        "9f504ff9be8fe791196c04d8c25e1b91a99911448d13e2068775ffe016b49807"
    ),
    "data/evaluation/w06/model_preflight_01b_live/C2/provider_response_metadata.json": (
        "5c3833c774090c29d7aca6ca0c8dbdbbed2d4e7acac9e8be36c0f8564a72ff4e"
    ),
    "data/evaluation/w06/model_preflight_01b_live/C2/raw_provider_response.txt": (
        "52de0bbc1bc243bdf9069bb818acd5047b43730805855ec67bf96a3d352b670a"
    ),
    "data/evaluation/w06/model_preflight_01b_live/C2/request_manifest.json": (
        "9c8b949198cc9be97af4e8b7df0b8299f87cea319e515f879c7ca25a442430c9"
    ),
    "data/evaluation/w06/model_preflight_01b_live/C3/execution_receipt.json": (
        "7f926941ae3213ca1004ac5a8f07c78ec12339194375b400e4877777f2f2c2e5"
    ),
    "data/evaluation/w06/model_preflight_01b_live/C3/provider_response_metadata.json": (
        "ee01859a51903677efff1008c488ac95d9ffe62e7c9c1dda526e5391b78df698"
    ),
    "data/evaluation/w06/model_preflight_01b_live/C3/raw_provider_response.txt": (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    ),
    "data/evaluation/w06/model_preflight_01b_live/C3/request_manifest.json": (
        "94384251c7b034c1b40910d1bc69d24229fff1b963b7b54f7b99f6b55467f3a8"
    ),
}

EXPECTED_01C_AMENDMENT_SHAS: Dict[str, str] = {
    "data/evaluation/w06/w06_model_preflight_portable_schema_v2_manifest.json": (
        "b11974a5119dc49de80d96e2a9ed11ad5c7aca93aff25fec2cb54049a27c6b28"
    ),
    "data/evaluation/w06/w06_model_preflight_schema_portability_amendment_v1.json": (
        "7b33fc2568e942db751649a7b2908dba50d2155e311582717e4f753bd608d350"
    ),
    "data/evaluation/w06/w06_model_preflight_01c_portable_schema_receipt_v1.json": (
        "524fcdefdf92de8783a39662c7514eb26612f4228545ad4cd687e700684eceb0"
    ),
}


class CandidateFinalPreflightStatusV2(str, Enum):
    """Final technical preflight status per candidate at the end of Phase 01D (Sections 18 & 24)."""

    PASSED_TECHNICAL_PREFLIGHT_SCHEMA_V2 = "PASSED_TECHNICAL_PREFLIGHT_SCHEMA_V2"
    FAILED_TECHNICAL_PREFLIGHT_SCHEMA_V2 = "FAILED_TECHNICAL_PREFLIGHT_SCHEMA_V2"


class LiveFailureClassificationV2(str, Enum):
    """Deterministic failure classification for Phase 01D Schema-V2 live revalidation (Section 19)."""

    NONE = "NONE"
    PASSED_TECHNICAL_PREFLIGHT_SCHEMA_V2 = "PASSED_TECHNICAL_PREFLIGHT_SCHEMA_V2"
    FAILED_AUTHENTICATION = "FAILED_AUTHENTICATION"
    FAILED_MODEL_ACCESS = "FAILED_MODEL_ACCESS"
    FAILED_MODEL_ID_INTEGRITY = "FAILED_MODEL_ID_INTEGRITY"
    FAILED_ENDPOINT_COMPATIBILITY = "FAILED_ENDPOINT_COMPATIBILITY"
    FAILED_PARAMETER_COMPATIBILITY = "FAILED_PARAMETER_COMPATIBILITY"
    FAILED_STRUCTURED_OUTPUT_COMPATIBILITY = "FAILED_STRUCTURED_OUTPUT_COMPATIBILITY"
    FAILED_JSON_OUTPUT = "FAILED_JSON_OUTPUT"
    FAILED_SEMANTIC_SCHEMA_VALIDATION = "FAILED_SEMANTIC_SCHEMA_VALIDATION"
    FAILED_REFUSAL = "FAILED_REFUSAL"
    FAILED_MAX_TOKENS = "FAILED_MAX_TOKENS"
    FAILED_TIMEOUT = "FAILED_TIMEOUT"
    FAILED_HTTP_429 = "FAILED_HTTP_429"
    FAILED_HTTP_5XX = "FAILED_HTTP_5XX"
    FAILED_USAGE_METADATA = "FAILED_USAGE_METADATA"
    FAILED_SECRET_SAFETY = "FAILED_SECRET_SAFETY"
    HARNESS_ERROR = "HARNESS_ERROR"


class LiveCandidateExecutionRecordV2(BaseModel):
    """Machine-readable execution record for a single candidate in W06-MODEL-PREFLIGHT-01D (Section 23)."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    attempted: bool
    actual_http_request_count: int
    provider: str
    requested_model_id: str
    returned_model_id: Optional[str] = None
    resolved_model_version: Optional[str] = None
    system_fingerprint: Optional[str] = None
    service_tier: Optional[str] = None
    reasoning_effort: Optional[str] = None
    thinking_mode: Optional[str] = None
    effort: Optional[str] = None
    seed_acceptance_status: Optional[str] = None
    status: CandidateFinalPreflightStatusV2
    live_preflight_status: str
    failure_classification: LiveFailureClassificationV2
    sanitized_error_detail: Optional[str] = None
    error_detail_sanitized: Optional[str] = None
    schema_v2_accepted: bool
    strict_json_valid: bool
    semantic_pydantic_valid: bool
    schema_valid: bool
    raw_artifact_preserved: bool
    raw_response_sha256: Optional[str] = None
    parsed_response_sha256: Optional[str] = None
    sanitization_occurred_in_raw_response: bool = False
    usage_metadata: LiveUsageMetadataRecord
    latency_ms: Optional[float] = None
    finish_or_stop_reason: Optional[str] = None
    pricing_source: str
    pricing_source_url: str
    pricing_access_date: str
    input_price_per_million: float
    output_price_per_million: float
    authoritative_usage_available: bool
    estimated_standard_api_cost_usd: Optional[float] = None
    current_technical_eligibility: str
    blockers: List[str] = Field(default_factory=list)


def verify_schema_hashes_01d() -> Dict[str, str]:
    """Verify Section 1 frozen schema hashes before any live execution."""
    if SEMANTIC_SCHEMA_SHA256 != EXPECTED_SEMANTIC_SCHEMA_SHA256_01D:
        raise RuntimeError(
            f"HARNESS_ERROR: SEMANTIC_SCHEMA_SHA256 mismatch: expected "
            f"{EXPECTED_SEMANTIC_SCHEMA_SHA256_01D}, got {SEMANTIC_SCHEMA_SHA256}"
        )
    if COMMON_GENERATION_SCHEMA_SHA256_V1 != EXPECTED_GENERATION_SCHEMA_V1_SHA256_01D:
        raise RuntimeError(
            f"HARNESS_ERROR: GENERATION_SCHEMA_V1_SHA256 mismatch: expected "
            f"{EXPECTED_GENERATION_SCHEMA_V1_SHA256_01D}, got {COMMON_GENERATION_SCHEMA_SHA256_V1}"
        )
    if (
        COMMON_PORTABLE_GENERATION_SCHEMA_SHA256_V2
        != EXPECTED_PORTABLE_GENERATION_SCHEMA_V2_SHA256_01D
    ):
        raise RuntimeError(
            f"HARNESS_ERROR: PORTABLE_GENERATION_SCHEMA_V2_SHA256 mismatch: expected "
            f"{EXPECTED_PORTABLE_GENERATION_SCHEMA_V2_SHA256_01D}, got {COMMON_PORTABLE_GENERATION_SCHEMA_SHA256_V2}"
        )
    return {
        "semantic_schema_sha256": SEMANTIC_SCHEMA_SHA256,
        "generation_schema_v1_sha256": COMMON_GENERATION_SCHEMA_SHA256_V1,
        "portable_generation_schema_v2_sha256": COMMON_PORTABLE_GENERATION_SCHEMA_SHA256_V2,
    }


def verify_frozen_authorities_01d(repo_root: Optional[Path] = None) -> Dict[str, str]:
    """Verify all 13 frozen scientific authorities from Section 12 are unchanged."""
    root = repo_root or REPO_ROOT
    verified: Dict[str, str] = {}
    for rel_path, expected_sha in EXPECTED_FROZEN_AUTHORITY_SHAS_01D.items():
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


def verify_historical_01b_and_01c_immutability(
    repo_root: Optional[Path] = None,
) -> Dict[str, Dict[str, str]]:
    """Verify all historical 01B live artifacts and 01C amendment artifacts are untouched (Sections 5, 12, PD-43, PD-44)."""
    root = repo_root or REPO_ROOT
    verified_01b: Dict[str, str] = {}
    for rel_path, expected_sha in EXPECTED_HISTORICAL_01B_EVIDENCE_SHAS.items():
        fpath = root / rel_path
        if not fpath.is_file():
            raise RuntimeError(f"HARNESS_ERROR: Missing historical 01B evidence file: {rel_path}")
        actual_sha = sha256_bytes(normalize_lf_bytes(fpath.read_bytes()))
        if actual_sha != expected_sha:
            raise RuntimeError(
                f"HARNESS_ERROR: Historical 01B evidence mutated at {rel_path}: "
                f"expected {expected_sha}, got {actual_sha}"
            )
        verified_01b[rel_path] = actual_sha

    verified_01c: Dict[str, str] = {}
    for rel_path, expected_sha in EXPECTED_01C_AMENDMENT_SHAS.items():
        fpath = root / rel_path
        if not fpath.is_file():
            raise RuntimeError(f"HARNESS_ERROR: Missing 01C amendment file: {rel_path}")
        actual_sha = sha256_bytes(normalize_lf_bytes(fpath.read_bytes()))
        if actual_sha != expected_sha:
            raise RuntimeError(
                f"HARNESS_ERROR: 01C amendment artifact mutated at {rel_path}: "
                f"expected {expected_sha}, got {actual_sha}"
            )
        verified_01c[rel_path] = actual_sha

    return {
        "historical_01b": verified_01b,
        "amendment_01c": verified_01c,
    }


def load_historical_01b_plan_hashes(
    plan_01b_path: Path = HISTORICAL_01B_PLAN_PATH,
) -> Dict[str, str]:
    """Load the frozen 01B plan and verify its exact SHA256 and fixture/prompt hashes (Section 6)."""
    if not plan_01b_path.is_file():
        raise RuntimeError(f"HARNESS_ERROR: Historical 01B plan missing at {plan_01b_path}")
    raw_bytes = normalize_lf_bytes(plan_01b_path.read_bytes())
    plan_sha = sha256_bytes(raw_bytes)
    if plan_sha != EXPECTED_HISTORICAL_01B_PLAN_SHA256_01D:
        raise RuntimeError(
            f"HARNESS_ERROR: Historical 01B plan SHA256 mismatch: "
            f"expected {EXPECTED_HISTORICAL_01B_PLAN_SHA256_01D}, got {plan_sha}"
        )
    data = json.loads(raw_bytes.decode("utf-8"))
    return {
        "historical_01b_plan_sha256": plan_sha,
        "historical_01b_fixture_id": data["fixture_id"],
        "historical_01b_fixture_sha256": data["fixture_sha256"],
        "historical_01b_system_prompt_sha256": data["system_prompt_sha256"],
        "historical_01b_user_prompt_sha256": data["user_prompt_sha256"],
    }


def build_live_revalidation_v2_plan_payload() -> Dict[str, Any]:
    """Build the deterministic pre-call Phase 01D Schema-V2 live revalidation plan payload (Section 14)."""
    verify_schema_hashes_01d()
    hist_01b = load_historical_01b_plan_hashes()

    scenario, pois = get_live_smoke_001_fixture()
    fixture_sha = compute_fixture_sha256(scenario, pois)
    user_prompt = build_shared_semantic_user_prompt(scenario, pois)
    sys_prompt_sha = sha256_bytes(PREFLIGHT_SHARED_SYSTEM_PROMPT.encode("utf-8"))
    usr_prompt_sha = sha256_bytes(user_prompt.encode("utf-8"))

    if scenario.scenario_id != hist_01b["historical_01b_fixture_id"]:
        raise RuntimeError("HARNESS_ERROR: 01D fixture_id does not match historical 01B fixture_id.")
    if fixture_sha != hist_01b["historical_01b_fixture_sha256"]:
        raise RuntimeError("HARNESS_ERROR: 01D fixture_sha256 does not match historical 01B fixture_sha256.")
    if sys_prompt_sha != hist_01b["historical_01b_system_prompt_sha256"]:
        raise RuntimeError("HARNESS_ERROR: 01D system_prompt_sha256 does not match historical 01B.")
    if usr_prompt_sha != hist_01b["historical_01b_user_prompt_sha256"]:
        raise RuntimeError("HARNESS_ERROR: 01D user_prompt_sha256 does not match historical 01B.")

    g_adapter = GooglePreflightAdapter()
    o_adapter = OpenAIPreflightAdapter()
    a_adapter = AnthropicPreflightAdapter()

    g_req = g_adapter.serialize_smoke_request_v2(scenario, pois)
    o_req = o_adapter.serialize_smoke_request_v2(scenario, pois)
    a_req = a_adapter.serialize_smoke_request_v2(scenario, pois)

    if not (
        g_req["system_prompt_sha256"]
        == o_req["system_prompt_sha256"]
        == a_req["system_prompt_sha256"]
        == sys_prompt_sha
    ):
        raise RuntimeError("HARNESS_ERROR: System prompt hash mismatch across V2 candidates.")
    if not (
        g_req["user_prompt_sha256"]
        == o_req["user_prompt_sha256"]
        == a_req["user_prompt_sha256"]
        == usr_prompt_sha
    ):
        raise RuntimeError("HARNESS_ERROR: User prompt hash mismatch across V2 candidates.")
    if not (
        g_req["portable_generation_schema_v2_sha256"]
        == o_req["portable_generation_schema_v2_sha256"]
        == a_req["portable_generation_schema_v2_sha256"]
        == EXPECTED_PORTABLE_GENERATION_SCHEMA_V2_SHA256_01D
    ):
        raise RuntimeError("HARNESS_ERROR: Portable V2 schema hash mismatch across candidates.")

    # Verify structural identity of the V2 schema wired into all 3 provider requests (Section 7 / PD-19 / PD-38)
    g_schema = g_req["config"]["response_json_schema"]
    o_schema = o_req["config"]["response_format"]["json_schema"]["schema"]
    a_schema = a_req["config"]["output_config"]["format"]["schema"]
    if not (
        g_schema
        == o_schema
        == a_schema
        == COMMON_PORTABLE_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA_V2
    ):
        raise RuntimeError(
            "HARNESS_ERROR: Provider-specific schema mutation detected across C1/C2/C3 V2 requests."
        )

    return {
        "artifact_id": "W06-MODEL-PREFLIGHT-01D-V2-LIVE-PLAN",
        "task_id": TASK_ID_01D,
        "version": VERSION_01D,
        "base_develop_sha": EXPECTED_BASE_DEVELOP_SHA_01D,
        "architecture_id": FROZEN_ARCHITECTURE_ID,
        "architecture_class": FROZEN_ARCHITECTURE_CLASS,
        "user_live_authorization": True,
        "authorization_max_live_calls": FROZEN_MAX_LIVE_GENERATION_CALLS_TOTAL,
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
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
        "endpoints": {
            cid: FROZEN_CANDIDATE_SPECS[cid]["endpoint"]
            for cid in FROZEN_CANDIDATE_EXECUTION_ORDER
        },
        "fixture_id": FROZEN_LIVE_SMOKE_FIXTURE_ID,
        "smoke_002_used": False,
        "fixture_sha256": fixture_sha,
        "system_prompt_sha256": sys_prompt_sha,
        "user_prompt_sha256": usr_prompt_sha,
        "historical_01b_plan_sha256": hist_01b["historical_01b_plan_sha256"],
        "historical_01b_fixture_sha256": hist_01b["historical_01b_fixture_sha256"],
        "historical_01b_system_prompt_sha256": hist_01b["historical_01b_system_prompt_sha256"],
        "historical_01b_user_prompt_sha256": hist_01b["historical_01b_user_prompt_sha256"],
        "fixture_matches_01b": True,
        "system_prompt_matches_01b": True,
        "user_prompt_matches_01b": True,
        "semantic_schema_sha256": SEMANTIC_SCHEMA_SHA256,
        "generation_schema_v1_sha256": COMMON_GENERATION_SCHEMA_SHA256_V1,
        "portable_generation_schema_v2_sha256": COMMON_PORTABLE_GENERATION_SCHEMA_SHA256_V2,
        "common_generation_schema_sha256": COMMON_PORTABLE_GENERATION_SCHEMA_SHA256_V2,
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
                "response_json_schema_sha256": COMMON_PORTABLE_GENERATION_SCHEMA_SHA256_V2,
                "portable_generation_schema_v2_sha256": COMMON_PORTABLE_GENERATION_SCHEMA_SHA256_V2,
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
                "omitted_parameters": [
                    "temperature",
                    "top_p",
                    "top_k",
                    "top_logprobs",
                    "logprobs",
                    "tools",
                ],
                "response_format": {
                    "type": "json_schema",
                    "name": "BenchmarkPlanResponse",
                    "strict": True,
                    "schema_sha256": COMMON_PORTABLE_GENERATION_SCHEMA_SHA256_V2,
                    "portable_generation_schema_v2_sha256": COMMON_PORTABLE_GENERATION_SCHEMA_SHA256_V2,
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
                    "schema_sha256": COMMON_PORTABLE_GENERATION_SCHEMA_SHA256_V2,
                    "portable_generation_schema_v2_sha256": COMMON_PORTABLE_GENERATION_SCHEMA_SHA256_V2,
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
        "transport_retry": 0,
        "manual_retry": 0,
        "fallback": False,
        "llm_repair": 0,
        "repair": False,
        "tools": False,
        "dev_tune_allowed": False,
        "dev_select_allowed": False,
        "final100_allowed": False,
        "final_100_allowed": False,
        "scientific_quality_scoring_allowed": False,
        "scientific_performance_scoring_allowed": False,
        "01B_historical_evidence_preserved": True,
        "01C_amendment_preserved": True,
        "pricing_evidence": {
            cid: FROZEN_STANDARD_PRICING_SPECS[cid].model_dump()
            for cid in FROZEN_CANDIDATE_EXECUTION_ORDER
        },
    }


def write_live_revalidation_v2_plan(
    output_path: Path = DEFAULT_LIVE_PLAN_V2_PATH,
) -> Path:
    """Write the canonical pre-call Phase 01D Schema-V2 live revalidation plan JSON artifact."""
    payload = build_live_revalidation_v2_plan_payload()
    write_canonical_json(output_path, payload)
    return output_path


def verify_live_revalidation_v2_plan_immutability(
    plan_path: Path = DEFAULT_LIVE_PLAN_V2_PATH,
) -> str:
    """Verify the frozen 01D V2 live plan file on disk matches the canonical expected plan payload."""
    if not plan_path.is_file():
        raise RuntimeError(f"HARNESS_ERROR: Frozen 01D V2 live plan file missing at {plan_path}")
    disk_bytes = normalize_lf_bytes(plan_path.read_bytes())
    expected_bytes = canonical_json_bytes(build_live_revalidation_v2_plan_payload())
    if disk_bytes != expected_bytes:
        raise RuntimeError(
            "HARNESS_ERROR: Frozen 01D V2 live plan file on disk does not match canonical live plan configuration; "
            "mutating plan/config after freeze is forbidden."
        )
    return sha256_bytes(disk_bytes)


def _map_01b_exception_classification_to_v2(
    exc: Exception,
) -> LiveFailureClassificationV2:
    """Map transport/provider exception classification into LiveFailureClassificationV2."""
    cls_01b = classify_live_exception(exc)
    return LiveFailureClassificationV2(cls_01b.value)


def execute_single_candidate_live_revalidation_v2(
    *,
    candidate_id: str,
    budget_tracker: LiveCallBudgetTracker,
    confirm_live: bool,
    artifact_root_dir: Path = DEFAULT_LIVE_ARTIFACTS_V2_DIR,
    plan_path: Path = DEFAULT_LIVE_PLAN_V2_PATH,
    dotenv_path: Optional[Path] = None,
    inner_transport_override: Optional[Any] = None,
) -> LiveCandidateExecutionRecordV2:
    """Execute at most 1 generation request for a candidate under Portable Schema V2 and persist sanitized evidence."""
    if not confirm_live:
        raise LiveProviderCallForbiddenError(
            "Explicit confirmation (--confirm-live / confirm_live=True) is required for Phase 01D live revalidation."
        )

    spec = FROZEN_CANDIDATE_SPECS.get(candidate_id)
    if spec is None:
        raise OneCallInvariantViolationError(f"Forbidden candidate_id: {candidate_id!r}")
    validate_candidate_identity(candidate_id, spec["provider"], spec["requested_model_id"])

    # Pre-request invariant checks (Section 17)
    verify_schema_hashes_01d()
    verify_live_revalidation_v2_plan_immutability(plan_path=plan_path)
    verify_frozen_authorities_01d()
    verify_historical_01b_and_01c_immutability()
    budget_tracker.assert_can_start_candidate(candidate_id)

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
    request_payload = adapter.serialize_smoke_request_v2(scenario, pois)

    if (
        request_payload["portable_generation_schema_v2_sha256"]
        != EXPECTED_PORTABLE_GENERATION_SCHEMA_V2_SHA256_01D
    ):
        raise RuntimeError("HARNESS_ERROR: Candidate V2 request schema hash mismatch.")

    cand_dir = artifact_root_dir / candidate_id
    cand_dir.mkdir(parents=True, exist_ok=True)

    # Persist sanitized request_manifest.json (never includes credentials or HTTP headers)
    request_manifest = {
        "task_id": TASK_ID_01D,
        "candidate_id": candidate_id,
        "provider": spec["provider"],
        "requested_model_id": spec["requested_model_id"],
        "endpoint": spec["endpoint"],
        "fixture_id": scenario.scenario_id,
        "fixture_sha256": compute_fixture_sha256(scenario, pois),
        "system_prompt_sha256": request_payload["system_prompt_sha256"],
        "user_prompt_sha256": request_payload["user_prompt_sha256"],
        "semantic_schema_sha256": request_payload["semantic_schema_sha256"],
        "generation_schema_v1_sha256": request_payload["generation_schema_v1_sha256"],
        "portable_generation_schema_v2_sha256": request_payload["portable_generation_schema_v2_sha256"],
        "common_generation_schema_sha256": request_payload["common_generation_schema_sha256"],
        "config_summary": {
            k: v
            for k, v in request_payload["config"].items()
            if k
            not in (
                "messages",
                "system_instruction",
                "system",
                "response_json_schema",
                "response_format",
                "output_config",
            )
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
        failure_cls = _map_01b_exception_classification_to_v2(exc)
        safe_err = sanitize_secret_error_text(
            f"{type(exc).__name__}: {exc}", dotenv_path=dotenv_path
        )
        empty_usage = LiveUsageMetadataRecord(authoritative_usage_available=False)

        seed_status = (
            "UNSUPPORTED_OMITTED"
            if candidate_id == "C3"
            else (
                "REJECTED_BY_LIVE_ENDPOINT"
                if (
                    failure_cls == LiveFailureClassificationV2.FAILED_PARAMETER_COMPATIBILITY
                    and "seed" in (safe_err or "").lower()
                )
                else "NOT_CONFIRMED_DUE_TO_REQUEST_FAILURE"
            )
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
                "sanitized_error_detail": safe_err,
                "error_detail_sanitized": safe_err,
                "latency_ms": latency_ms,
                "actual_http_request_count": c_transport.request_count,
                "semantic_schema_sha256": SEMANTIC_SCHEMA_SHA256,
                "portable_generation_schema_v2_sha256": COMMON_PORTABLE_GENERATION_SCHEMA_SHA256_V2,
            },
        )
        rec = LiveCandidateExecutionRecordV2(
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
            status=CandidateFinalPreflightStatusV2.FAILED_TECHNICAL_PREFLIGHT_SCHEMA_V2,
            live_preflight_status=failure_cls.value,
            failure_classification=failure_cls,
            sanitized_error_detail=safe_err,
            error_detail_sanitized=safe_err,
            schema_v2_accepted=False,
            strict_json_valid=False,
            semantic_pydantic_valid=False,
            schema_valid=False,
            raw_artifact_preserved=False,
            raw_response_sha256=None,
            parsed_response_sha256=None,
            sanitization_occurred_in_raw_response=False,
            usage_metadata=empty_usage,
            latency_ms=latency_ms,
            finish_or_stop_reason=None,
            pricing_source=pricing.pricing_source_url,
            pricing_source_url=pricing.pricing_source_url,
            pricing_access_date=pricing.pricing_access_date,
            input_price_per_million=pricing.input_price_per_million,
            output_price_per_million=pricing.output_price_per_million,
            authoritative_usage_available=False,
            estimated_standard_api_cost_usd=None,
            current_technical_eligibility=CandidateFinalPreflightStatusV2.FAILED_TECHNICAL_PREFLIGHT_SCHEMA_V2.value,
            blockers=[f"{failure_cls.value}: {safe_err}"],
        )
        write_canonical_json(cand_dir / "execution_receipt.json", rec.model_dump())
        return rec

    t_end = time.perf_counter()
    latency_ms = round((t_end - t_start) * 1000.0, 3)

    raw_str_unsanitized = raw_text if isinstance(raw_text, str) else ""
    raw_str_sanitized = (
        sanitize_secret_error_text(raw_str_unsanitized, dotenv_path=dotenv_path) or ""
    )
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
            "semantic_schema_sha256": SEMANTIC_SCHEMA_SHA256,
            "portable_generation_schema_v2_sha256": COMMON_PORTABLE_GENERATION_SCHEMA_SHA256_V2,
        },
    )

    # Technical Pass/Fail evaluation (Section 18 — NO scientific evaluator!)
    failure_cls = LiveFailureClassificationV2.NONE
    err_detail: Optional[str] = None
    schema_v2_accepted = True
    strict_json_valid = False
    semantic_pydantic_valid = False
    parsed_sha256: Optional[str] = None
    blockers: List[str] = []

    # 1. Check HTTP request count == 1
    if c_transport.request_count != 1:
        failure_cls = LiveFailureClassificationV2.HARNESS_ERROR
        err_detail = f"Expected actual_http_request_count == 1, got {c_transport.request_count}"
        blockers.append(err_detail)

    # 2. Check returned model metadata integrity
    if failure_cls == LiveFailureClassificationV2.NONE:
        model_ok, model_err = verify_model_metadata_integrity(
            candidate_id=candidate_id,
            requested_model_id=spec["requested_model_id"],
            returned_model_id=returned_model_id,
            raise_on_mismatch=False,
        )
        if not model_ok:
            failure_cls = LiveFailureClassificationV2.FAILED_MODEL_ID_INTEGRITY
            err_detail = sanitize_secret_error_text(model_err, dotenv_path=dotenv_path)
            blockers.append(err_detail or "Model ID mismatch")

    # 3. Check refusal
    if failure_cls == LiveFailureClassificationV2.NONE and is_refusal:
        failure_cls = LiveFailureClassificationV2.FAILED_REFUSAL
        err_detail = f"Provider returned refusal response (finish_or_stop_reason={finish_reason!r})."
        blockers.append(err_detail)

    # 4. Check max_tokens / truncation
    if failure_cls == LiveFailureClassificationV2.NONE:
        fr_norm = str(finish_reason or "").strip().lower()
        if fr_norm in ("max_tokens", "length", "finishreason.max_tokens"):
            failure_cls = LiveFailureClassificationV2.FAILED_MAX_TOKENS
            err_detail = f"Output truncated due to max_tokens (finish_or_stop_reason={finish_reason!r})."
            blockers.append(err_detail)

    # 5. Check authoritative usage metadata
    if failure_cls == LiveFailureClassificationV2.NONE and not usage_rec.authoritative_usage_available:
        failure_cls = LiveFailureClassificationV2.FAILED_USAGE_METADATA
        err_detail = "Authoritative token usage metadata missing from provider response."
        blockers.append(err_detail)

    # 6. Dual-Layer Validation (Section 18):
    #    6a. Strict JSON parse without rescue/code-fence cleanup -> FAILED_JSON_OUTPUT on failure
    #    6b. Semantic Pydantic validation via BenchmarkPlanResponse.model_validate & parse_strict_benchmark_plan_response
    #        -> FAILED_SEMANTIC_SCHEMA_VALIDATION on failure (no repair!)
    decoded_json: Any = None
    if failure_cls == LiveFailureClassificationV2.NONE:
        try:
            decoded_json = json.loads(raw_str_sanitized)
            if not isinstance(decoded_json, dict):
                raise json.JSONDecodeError("Top-level JSON value must be an object", raw_str_sanitized, 0)
            strict_json_valid = True
        except (json.JSONDecodeError, TypeError) as json_exc:
            failure_cls = LiveFailureClassificationV2.FAILED_JSON_OUTPUT
            err_detail = sanitize_secret_error_text(
                f"Strict JSON parse failed without rescue: {type(json_exc).__name__}: {json_exc}",
                dotenv_path=dotenv_path,
            )
            blockers.append(err_detail or "Strict JSON parse failed")

    if failure_cls == LiveFailureClassificationV2.NONE and strict_json_valid:
        try:
            BenchmarkPlanResponse.model_validate(decoded_json)
            parsed_plan = parse_strict_benchmark_plan_response(
                raw_data=decoded_json,
                scenario=scenario,
                plan_id=decoded_json.get("plan_id") or f"live-v2-{candidate_id.lower()}",
            )
            semantic_pydantic_valid = True
            parsed_dump = parsed_plan.model_dump()
            parsed_sha256 = sha256_bytes(canonical_json_bytes(parsed_dump))
            write_canonical_json(cand_dir / "parsed_plan_response.json", parsed_dump)
        except (ValidationError, ValueError, TypeError, KeyError) as sem_exc:
            failure_cls = LiveFailureClassificationV2.FAILED_SEMANTIC_SCHEMA_VALIDATION
            err_detail = sanitize_secret_error_text(
                f"Semantic BenchmarkPlanResponse validation failed under Schema V2: {type(sem_exc).__name__}: {sem_exc}",
                dotenv_path=dotenv_path,
            )
            blockers.append(err_detail or "Semantic Pydantic validation failed")

    # 7. Check artifact secret scan
    cand_secret_scan = scan_directory_for_secret_leaks(cand_dir, dotenv_path=dotenv_path)
    if cand_secret_scan["secret_leak_count"] != 0 or sanitization_occurred:
        if cand_secret_scan["secret_leak_count"] != 0:
            failure_cls = LiveFailureClassificationV2.FAILED_SECRET_SAFETY
            err_detail = "Secret pattern detected in candidate artifact directory."
            blockers.append(err_detail)

    passed = (
        failure_cls == LiveFailureClassificationV2.NONE
        and schema_v2_accepted
        and strict_json_valid
        and semantic_pydantic_valid
    )
    final_status = (
        CandidateFinalPreflightStatusV2.PASSED_TECHNICAL_PREFLIGHT_SCHEMA_V2
        if passed
        else CandidateFinalPreflightStatusV2.FAILED_TECHNICAL_PREFLIGHT_SCHEMA_V2
    )
    live_status_str = (
        CandidateFinalPreflightStatusV2.PASSED_TECHNICAL_PREFLIGHT_SCHEMA_V2.value
        if passed
        else failure_cls.value
    )

    rec = LiveCandidateExecutionRecordV2(
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
        sanitized_error_detail=err_detail,
        error_detail_sanitized=err_detail,
        schema_v2_accepted=schema_v2_accepted,
        strict_json_valid=strict_json_valid,
        semantic_pydantic_valid=semantic_pydantic_valid,
        schema_valid=semantic_pydantic_valid,
        raw_artifact_preserved=True,
        raw_response_sha256=raw_sha256,
        parsed_response_sha256=parsed_sha256,
        sanitization_occurred_in_raw_response=sanitization_occurred,
        usage_metadata=usage_rec,
        latency_ms=latency_ms,
        finish_or_stop_reason=finish_reason,
        pricing_source=pricing.pricing_source_url,
        pricing_source_url=pricing.pricing_source_url,
        pricing_access_date=pricing.pricing_access_date,
        input_price_per_million=pricing.input_price_per_million,
        output_price_per_million=pricing.output_price_per_million,
        authoritative_usage_available=usage_rec.authoritative_usage_available,
        estimated_standard_api_cost_usd=est_cost,
        current_technical_eligibility=final_status.value,
        blockers=blockers,
    )
    write_canonical_json(cand_dir / "execution_receipt.json", rec.model_dump())
    return rec


def run_live_revalidation_v2_suite(
    *,
    confirm_live: bool = False,
    live_plan_commit_sha: Optional[str] = None,
    transport_overrides: Optional[Dict[str, Any]] = None,
    artifact_root_dir: Path = DEFAULT_LIVE_ARTIFACTS_V2_DIR,
    receipt_path: Path = DEFAULT_LIVE_RECEIPT_V2_PATH,
    plan_path: Path = DEFAULT_LIVE_PLAN_V2_PATH,
    dotenv_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Execute the complete W06-MODEL-PREFLIGHT-01D-PORTABLE-SCHEMA-LIVE-REVALIDATION suite in fixed order C1 -> C2 -> C3."""
    if not confirm_live:
        raise LiveProviderCallForbiddenError(
            "LIVE_PROVIDER_CALL_FORBIDDEN: run_live_revalidation_v2_suite requires confirm_live=True (--confirm-live)."
        )

    verify_schema_hashes_01d()
    plan_sha256 = verify_live_revalidation_v2_plan_immutability(plan_path=plan_path)
    frozen_authorities = verify_frozen_authorities_01d()
    verify_historical_01b_and_01c_immutability()

    key_presence = check_dotenv_key_presence(dotenv_path=dotenv_path)
    if any(v != "PRESENT" for v in key_presence.values()):
        raise RuntimeError(f"HARNESS_ERROR: Missing required keys in .env: {key_presence}")

    budget_tracker = LiveCallBudgetTracker()
    candidate_records: Dict[str, Dict[str, Any]] = {}

    for cid in FROZEN_CANDIDATE_EXECUTION_ORDER:
        override = (transport_overrides or {}).get(cid)
        rec = execute_single_candidate_live_revalidation_v2(
            candidate_id=cid,
            budget_tracker=budget_tracker,
            confirm_live=confirm_live,
            artifact_root_dir=artifact_root_dir,
            plan_path=plan_path,
            dotenv_path=dotenv_path,
            inner_transport_override=override,
        )
        candidate_records[cid] = rec.model_dump()
        if rec.failure_classification == LiveFailureClassificationV2.HARNESS_ERROR:
            raise RuntimeError(
                f"HARNESS_ERROR during {cid} V2 execution: {rec.sanitized_error_detail}"
            )

    tracked_scan = scan_tracked_files_for_secret_leaks()
    artifact_scan = scan_directory_for_secret_leaks(artifact_root_dir, dotenv_path=dotenv_path)

    total_cost = round(budget_tracker.cumulative_estimated_cost_usd, 8)
    all_blockers: List[str] = []
    for cid in FROZEN_CANDIDATE_EXECUTION_ORDER:
        for b in candidate_records[cid]["blockers"]:
            all_blockers.append(f"[{cid}] {b}")

    passed_cands = [
        cid
        for cid in FROZEN_CANDIDATE_EXECUTION_ORDER
        if candidate_records[cid]["status"]
        == CandidateFinalPreflightStatusV2.PASSED_TECHNICAL_PREFLIGHT_SCHEMA_V2.value
    ]
    failed_cands = [
        cid
        for cid in FROZEN_CANDIDATE_EXECUTION_ORDER
        if candidate_records[cid]["status"]
        == CandidateFinalPreflightStatusV2.FAILED_TECHNICAL_PREFLIGHT_SCHEMA_V2.value
    ]

    receipt_payload: Dict[str, Any] = {
        "artifact_id": "W06-MODEL-PREFLIGHT-01D-V2-LIVE-RECEIPT",
        "task_id": TASK_ID_01D,
        "version": VERSION_01D,
        "base_develop_sha": EXPECTED_BASE_DEVELOP_SHA_01D,
        "live_plan_commit_sha": live_plan_commit_sha,
        "live_plan_sha256": plan_sha256,
        "live_result_commit_sha": None,
        "user_live_authorization": True,
        "live_provider_calls_allowed": True,
        "max_live_generation_calls_total": FROZEN_MAX_LIVE_GENERATION_CALLS_TOTAL,
        "max_live_generation_calls_per_candidate": FROZEN_MAX_LIVE_GENERATION_CALLS_PER_CANDIDATE,
        "actual_live_generation_calls_total": budget_tracker.total_http_requests,
        "retry": 0,
        "automatic_retry": 0,
        "transport_retry": 0,
        "manual_retry": 0,
        "fallback": False,
        "repair": 0,
        "llm_repair": 0,
        "tools": False,
        "scientific_evaluator_invoked": False,
        "dev_tune_started": False,
        "dev_select_started": False,
        "winner_selected": False,
        "winning_model_selected": False,
        "final_100_used": False,
        "final_benchmark_started": False,
        "preregistered": False,
        "fixture_id": FROZEN_LIVE_SMOKE_FIXTURE_ID,
        "smoke_002_used": False,
        "fixture_matches_01b": True,
        "system_prompt_matches_01b": True,
        "user_prompt_matches_01b": True,
        "semantic_schema_sha256": SEMANTIC_SCHEMA_SHA256,
        "generation_schema_v1_sha256": COMMON_GENERATION_SCHEMA_SHA256_V1,
        "portable_generation_schema_v2_sha256": COMMON_PORTABLE_GENERATION_SCHEMA_SHA256_V2,
        "common_generation_schema_sha256": COMMON_PORTABLE_GENERATION_SCHEMA_SHA256_V2,
        "historical_01b_preserved": True,
        "amendment_01c_preserved": True,
        "env_key_presence": key_presence,
        "tracked_secret_scan": tracked_scan,
        "artifact_secret_scan": artifact_scan,
        "total_estimated_standard_api_cost_usd": total_cost,
        "candidates": candidate_records,
        "passed_technical_preflight_schema_v2_candidates": passed_cands,
        "failed_technical_preflight_schema_v2_candidates": failed_cands,
        "current_technical_eligibility": {
            cid: candidate_records[cid]["status"]
            for cid in FROZEN_CANDIDATE_EXECUTION_ORDER
        },
        "blockers": all_blockers,
        "frozen_authority_preservation": frozen_authorities,
    }
    write_canonical_json(receipt_path, receipt_payload)
    return receipt_payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description="W06-MODEL-PREFLIGHT-01D-PORTABLE-SCHEMA-LIVE-REVALIDATION CLI"
    )
    parser.add_argument(
        "--write-plan",
        action="store_true",
        help="Write frozen Phase 01D V2 live revalidation plan JSON.",
    )
    parser.add_argument(
        "--execute-live",
        action="store_true",
        help="Execute the 3 live V2 revalidation requests (1 per candidate).",
    )
    parser.add_argument(
        "--confirm-live",
        action="store_true",
        help="Explicit user live confirmation flag.",
    )
    parser.add_argument(
        "--live-plan-commit-sha",
        type=str,
        default=None,
        help="Git commit SHA of frozen 01D V2 live plan.",
    )
    args = parser.parse_args()

    if args.write_plan:
        p = write_live_revalidation_v2_plan()
        print(f"WROTE_LIVE_PLAN_V2={p} SHA256={sha256_bytes(p.read_bytes())}")
        return

    if args.execute_live:
        receipt = run_live_revalidation_v2_suite(
            confirm_live=bool(args.confirm_live),
            live_plan_commit_sha=args.live_plan_commit_sha,
        )
        print(
            json.dumps(
                {
                    "actual_live_generation_calls_total": receipt[
                        "actual_live_generation_calls_total"
                    ],
                    "total_estimated_standard_api_cost_usd": receipt[
                        "total_estimated_standard_api_cost_usd"
                    ],
                    "passed": receipt["passed_technical_preflight_schema_v2_candidates"],
                    "failed": receipt["failed_technical_preflight_schema_v2_candidates"],
                },
                indent=2,
            )
        )
        return

    parser.error("Specify either --write-plan or --execute-live --confirm-live")


if __name__ == "__main__":
    main()
