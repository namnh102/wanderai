"""Offline Preflight Adapter for Candidate C1: Google / gemini-3.8-flash (W06-MODEL-PREFLIGHT-01A-OFFLINE).

SDK: google-genai==2.25.0
Endpoint semantics: models.generate_content (v1beta/models/{model}:generateContent)
Structured output: response_mime_type='application/json', response_json_schema=<BenchmarkPlanResponse JSON Schema>
Retry=0 mechanism: types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=1))
Tool calling: automatic_function_calling=AutomaticFunctionCallingConfig(disable=True), tools=None
"""
from importlib.metadata import version as pkg_version
from typing import Any, Dict, List, Optional, Tuple

from google import genai
from google.genai import types
import httpx

from app.evaluation.model_preflight.base import (
    FROZEN_MAX_OUTPUT_TOKENS,
    FROZEN_SAMPLING_SEED,
    FROZEN_SAMPLING_TEMPERATURE,
    FROZEN_TIMEOUT_MS,
    PREFLIGHT_SHARED_SYSTEM_PROMPT,
    BasePreflightProviderAdapter,
    build_shared_semantic_user_prompt,
)
from app.evaluation.model_preflight.schema_adapter import (
    COMMON_BENCHMARK_PLAN_JSON_SCHEMA,
    COMMON_SCHEMA_SHA256,
    build_google_structured_output_wiring,
)
from app.evaluation.model_preflight.types import (
    CandidateModelMetadataCheckRecord,
    CandidatePreflightRecord,
    CandidateRetryConfigRecord,
    CapabilityVerificationStatus,
    SamplingCapabilitySpec,
)
from app.schemas.planner_benchmark import (
    BenchmarkCatalogPOI,
    BenchmarkScenarioInput,
    BenchmarkUsageMetadata,
)
from app.services.planner_benchmark_runner import sha256_bytes


class GooglePreflightAdapter(BasePreflightProviderAdapter):
    """Evaluation-only preflight adapter for C1 (Google / gemini-3.8-flash)."""

    candidate_id = "C1"
    provider_name = "Google"
    requested_model_id = "gemini-3.8-flash"
    sdk_package = "google-genai"

    def __init__(self, *, live_allowed: Optional[bool] = None) -> None:
        super().__init__(live_allowed=live_allowed)
        self.sdk_version = pkg_version("google-genai")

    def get_preflight_record(self) -> CandidatePreflightRecord:
        wiring = build_google_structured_output_wiring(COMMON_BENCHMARK_PLAN_JSON_SCHEMA)
        return CandidatePreflightRecord(
            candidate_id=self.candidate_id,
            provider=self.provider_name,
            requested_model_id=self.requested_model_id,
            role="CANDIDATE_NOT_SELECTED_FINAL_MODEL",
            sdk_package=self.sdk_package,
            sdk_version=self.sdk_version,
            provider_documentation_url="https://ai.google.dev/gemini-api/docs/structured-output",
            access_date="2026-10-17",
            endpoint_semantics="google.genai.Client.models.generate_content (POST /v1beta/models/{model}:generateContent)",
            endpoint_verification_status=CapabilityVerificationStatus.VERIFIED_BY_SDK_SURFACE,
            live_model_id_status=CapabilityVerificationStatus.PENDING_LIVE_CONFIRMATION,
            structured_output_mode="NATIVE_RESPONSE_JSON_SCHEMA",
            structured_output_wiring_summary={
                "response_mime_type": wiring["response_mime_type"],
                "schema_parameter": "GenerateContentConfig.response_json_schema",
                "common_schema_sha256": wiring["common_schema_sha256"],
            },
            structured_output_capability_status=CapabilityVerificationStatus.VERIFIED_BY_SDK_SURFACE,
            common_schema_sha256=COMMON_SCHEMA_SHA256,
            place_id_encoded_as_catalog_enum=False,
            sampling_capabilities={
                "temperature": SamplingCapabilitySpec(
                    parameter_name="temperature",
                    sdk_parameter_name="GenerateContentConfig.temperature",
                    configured_value=FROZEN_SAMPLING_TEMPERATURE,
                    verification_status=CapabilityVerificationStatus.VERIFIED_BY_SDK_SURFACE,
                    notes="GenerateContentConfig exposes temperature: Optional[float]; fixed to 0.0 per Method Lock.",
                ),
                "seed": SamplingCapabilitySpec(
                    parameter_name="seed",
                    sdk_parameter_name="GenerateContentConfig.seed",
                    configured_value=FROZEN_SAMPLING_SEED,
                    verification_status=CapabilityVerificationStatus.VERIFIED_BY_SDK_SURFACE,
                    notes="GenerateContentConfig exposes seed: Optional[int]; fixed to 2026101508 per Method Lock.",
                ),
                "top_p": SamplingCapabilitySpec(
                    parameter_name="top_p",
                    sdk_parameter_name="GenerateContentConfig.top_p",
                    configured_value=None,
                    verification_status=CapabilityVerificationStatus.VERIFIED_BY_SDK_SURFACE,
                    notes="GenerateContentConfig exposes top_p: Optional[float]; left None (not grid-searched or tuned).",
                ),
                "top_k": SamplingCapabilitySpec(
                    parameter_name="top_k",
                    sdk_parameter_name="GenerateContentConfig.top_k",
                    configured_value=None,
                    verification_status=CapabilityVerificationStatus.VERIFIED_BY_SDK_SURFACE,
                    notes="GenerateContentConfig exposes top_k: Optional[float]; left None (not grid-searched or tuned).",
                ),
                "thinking_or_reasoning_setting": SamplingCapabilitySpec(
                    parameter_name="thinking_or_reasoning_setting",
                    sdk_parameter_name="GenerateContentConfig.thinking_config",
                    configured_value=None,
                    verification_status=CapabilityVerificationStatus.VERIFIED_BY_SDK_SURFACE,
                    notes="GenerateContentConfig exposes thinking_config: Optional[ThinkingConfig]; fixed to None (default provider mode, never tuned on DEV).",
                ),
                "max_output_tokens": SamplingCapabilitySpec(
                    parameter_name="max_output_tokens",
                    sdk_parameter_name="GenerateContentConfig.max_output_tokens",
                    configured_value=FROZEN_MAX_OUTPUT_TOKENS,
                    verification_status=CapabilityVerificationStatus.VERIFIED_BY_SDK_SURFACE,
                    notes="GenerateContentConfig exposes max_output_tokens: Optional[int]; fixed to 16384.",
                ),
                "timeout": SamplingCapabilitySpec(
                    parameter_name="timeout",
                    sdk_parameter_name="HttpOptions.timeout",
                    configured_value=FROZEN_TIMEOUT_MS,
                    verification_status=CapabilityVerificationStatus.VERIFIED_BY_SDK_SURFACE,
                    notes="HttpOptions.timeout configured in milliseconds (55000 ms).",
                ),
            },
            retry_configuration=CandidateRetryConfigRecord(
                sdk_automatic_retry=0,
                transport_retry=0,
                sdk_retry_mechanism="HttpOptions(retry_options=HttpRetryOptions(attempts=1)) with httpx.Client(transport=...)",
                verification_status=CapabilityVerificationStatus.OFFLINE_TEST_VERIFIED,
            ),
            model_metadata_check=CandidateModelMetadataCheckRecord(
                response_metadata_field="GenerateContentResponse.model_version",
                verification_status=CapabilityVerificationStatus.VERIFIED_BY_SDK_SURFACE,
            ),
            architecture_invariants=self.common_architecture_invariants(),
        )

    def serialize_smoke_request(
        self,
        scenario: BenchmarkScenarioInput,
        catalog_pois: List[BenchmarkCatalogPOI],
    ) -> Dict[str, Any]:
        user_prompt = build_shared_semantic_user_prompt(scenario, catalog_pois)
        wiring = build_google_structured_output_wiring(COMMON_BENCHMARK_PLAN_JSON_SCHEMA)
        return {
            "candidate_id": self.candidate_id,
            "provider": self.provider_name,
            "model": self.requested_model_id,
            "system_prompt": PREFLIGHT_SHARED_SYSTEM_PROMPT,
            "system_prompt_sha256": sha256_bytes(PREFLIGHT_SHARED_SYSTEM_PROMPT.encode("utf-8")),
            "user_prompt": user_prompt,
            "user_prompt_sha256": sha256_bytes(user_prompt.encode("utf-8")),
            "config": {
                "system_instruction": PREFLIGHT_SHARED_SYSTEM_PROMPT,
                "temperature": FROZEN_SAMPLING_TEMPERATURE,
                "seed": FROZEN_SAMPLING_SEED,
                "top_p": None,
                "top_k": None,
                "thinking_config": None,
                "max_output_tokens": FROZEN_MAX_OUTPUT_TOKENS,
                "response_mime_type": wiring["response_mime_type"],
                "response_json_schema": wiring["response_json_schema"],
                "tools": None,
                "automatic_function_calling_disabled": True,
                "timeout_ms": FROZEN_TIMEOUT_MS,
                "retry_attempts": 1,
            },
            "common_schema_sha256": COMMON_SCHEMA_SHA256,
        }

    def _invoke_single_sdk_call_with_transport(
        self,
        *,
        request_payload: Dict[str, Any],
        mock_transport: Any,
    ) -> Tuple[Optional[str], Optional[str], BenchmarkUsageMetadata, bool]:
        http_client = httpx.Client(transport=mock_transport)
        try:
            client = genai.Client(
                api_key="OFFLINE_PREFLIGHT_DUMMY_KEY",
                http_options=types.HttpOptions(
                    timeout=FROZEN_TIMEOUT_MS,
                    retry_options=types.HttpRetryOptions(attempts=1),
                    httpx_client=http_client,
                ),
            )
            cfg_dict = request_payload["config"]
            call_config = types.GenerateContentConfig(
                system_instruction=cfg_dict["system_instruction"],
                temperature=cfg_dict["temperature"],
                seed=cfg_dict["seed"],
                top_p=cfg_dict["top_p"],
                top_k=cfg_dict["top_k"],
                thinking_config=cfg_dict["thinking_config"],
                max_output_tokens=cfg_dict["max_output_tokens"],
                response_mime_type=cfg_dict["response_mime_type"],
                response_json_schema=cfg_dict["response_json_schema"],
                tools=None,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
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
        usage_obj = getattr(resp, "usage_metadata", None)
        usage = BenchmarkUsageMetadata(
            input_tokens=getattr(usage_obj, "prompt_token_count", None) if usage_obj else None,
            output_tokens=getattr(usage_obj, "candidates_token_count", None) if usage_obj else None,
            total_tokens=getattr(usage_obj, "total_token_count", None) if usage_obj else None,
        )

        # Check finish_reason for SAFETY / RECITATION / BLOCKLIST refusal
        is_refusal = False
        candidates = getattr(resp, "candidates", None) or []
        if candidates:
            finish_reason = str(getattr(candidates[0], "finish_reason", "") or "").upper()
            if any(tok in finish_reason for tok in ("SAFETY", "BLOCKLIST", "PROHIBITED", "RECITATION", "REFUSAL")):
                is_refusal = True

        return raw_text, returned_model, usage, is_refusal
