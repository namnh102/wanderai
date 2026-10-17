"""Offline Preflight Adapter for Candidate C1: Google / gemini-3.8-flash (W06-MODEL-PREFLIGHT-01A-FIX-01).

SDK: google-genai==2.25.0
Endpoint semantics: models.generate_content (v1beta/models/{model}:generateContent)
Structured output: response_mime_type='application/json', response_json_schema=<Strict Generation Schema>
Model-specific Gemini 3.8 Flash configuration (Part D):
- temperature, top_p, top_k custom settings are deprecated/ignored for Gemini 3.8 and are OMITTED from the request.
- thinking_level is explicitly frozen to 'medium' via types.ThinkingConfig(thinking_level='medium').
- seed (2026101508) exists on the SDK surface; model-level acceptance is retained as PENDING_LIVE_CONFIRMATION.
- Retry=0 mechanism: types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=1))
- Tool calling: automatic_function_calling=AutomaticFunctionCallingConfig(disable=True), tools=None
"""
from importlib.metadata import version as pkg_version
from typing import Any, Dict, List, Optional, Tuple

from google import genai
from google.genai import types
import httpx

from app.evaluation.model_preflight.base import (
    FROZEN_MAX_OUTPUT_TOKENS,
    FROZEN_SAMPLING_SEED,
    FROZEN_TIMEOUT_MS,
    PREFLIGHT_SHARED_SYSTEM_PROMPT,
    BasePreflightProviderAdapter,
    build_shared_semantic_user_prompt,
)
from app.evaluation.model_preflight.schema_adapter import (
    COMMON_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA,
    COMMON_GENERATION_SCHEMA_SHA256,
    COMMON_GENERATION_SCHEMA_SHA256_V1,
    COMMON_PORTABLE_GENERATION_SCHEMA_SHA256_V2,
    COMMON_SCHEMA_SHA256,
    SEMANTIC_SCHEMA_SHA256,
    build_google_structured_output_wiring,
    build_google_structured_output_wiring_v2,
)
from app.evaluation.model_preflight.types import (
    FROZEN_GOOGLE_THINKING_LEVEL,
    CandidateModelMetadataCheckRecord,
    CandidateOfflineReadinessStatus,
    CandidatePreflightRecord,
    CandidateRetryConfigRecord,
    CapabilityVerificationStatus,
    DocumentationProvenanceRecord,
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
        wiring = build_google_structured_output_wiring(COMMON_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA)
        return CandidatePreflightRecord(
            candidate_id=self.candidate_id,
            provider=self.provider_name,
            requested_model_id=self.requested_model_id,
            role="CANDIDATE_NOT_SELECTED_FINAL_MODEL",
            offline_status=CandidateOfflineReadinessStatus.READY_FOR_LIVE_PREFLIGHT,
            blockers=[],
            sdk_package=self.sdk_package,
            sdk_version=self.sdk_version,
            provider_documentation_url="https://ai.google.dev/gemini-api/docs/models",
            access_date="2026-10-17",
            documentation_provenance=[
                DocumentationProvenanceRecord(
                    claim="Gemini 3.8 Flash model family identifier and model overview",
                    official_url="https://ai.google.dev/gemini-api/docs/models",
                    access_date="2026-10-17",
                    verification_scope="MODEL_ID",
                ),
                DocumentationProvenanceRecord(
                    claim="Gemini 3.8 thinking_level configuration (low / medium / high; default medium) via ThinkingConfig(thinking_level='medium')",
                    official_url="https://ai.google.dev/gemini-api/docs/thinking",
                    access_date="2026-10-17",
                    verification_scope="THINKING_REASONING",
                ),
                DocumentationProvenanceRecord(
                    claim="Gemini 3.8 model-specific sampling behavior: custom temperature, top_p, and top_k settings are deprecated/ignored and omitted from request",
                    official_url="https://ai.google.dev/gemini-api/docs/thinking",
                    access_date="2026-10-17",
                    verification_scope="SAMPLING",
                ),
                DocumentationProvenanceRecord(
                    claim="Native JSON Schema structured output via response_mime_type='application/json' and response_json_schema",
                    official_url="https://ai.google.dev/gemini-api/docs/structured-output",
                    access_date="2026-10-17",
                    verification_scope="STRUCTURED_OUTPUT",
                ),
                DocumentationProvenanceRecord(
                    claim="GenerateContent max_output_tokens configuration in GenerateContentConfig",
                    official_url="https://ai.google.dev/api/generate-content#v1beta.GenerationConfig",
                    access_date="2026-10-17",
                    verification_scope="MAX_OUTPUT",
                ),
                DocumentationProvenanceRecord(
                    claim="GenerateContent endpoint semantics (POST /v1beta/models/{model}:generateContent)",
                    official_url="https://ai.google.dev/api/generate-content#method:-models.generatecontent",
                    access_date="2026-10-17",
                    verification_scope="ENDPOINT",
                ),
            ],
            endpoint_semantics="google.genai.Client.models.generate_content (POST /v1beta/models/{model}:generateContent)",
            endpoint_verification_status=CapabilityVerificationStatus.VERIFIED_BY_OFFICIAL_DOC_REFERENCE,
            live_model_id_status=CapabilityVerificationStatus.PENDING_LIVE_CONFIRMATION,
            structured_output_mode="NATIVE_RESPONSE_JSON_SCHEMA",
            structured_output_wiring_summary={
                "response_mime_type": wiring["response_mime_type"],
                "schema_parameter": "GenerateContentConfig.response_json_schema",
                "semantic_schema_sha256": SEMANTIC_SCHEMA_SHA256,
                "common_generation_schema_sha256": wiring["common_generation_schema_sha256"],
            },
            structured_output_capability_status=CapabilityVerificationStatus.VERIFIED_BY_OFFICIAL_DOC_REFERENCE,
            semantic_schema_sha256=SEMANTIC_SCHEMA_SHA256,
            common_generation_schema_sha256=COMMON_GENERATION_SCHEMA_SHA256,
            common_schema_sha256=COMMON_SCHEMA_SHA256,
            place_id_encoded_as_catalog_enum=False,
            sampling_capabilities={
                "temperature": SamplingCapabilitySpec(
                    parameter_name="temperature",
                    sdk_parameter_name="GenerateContentConfig.temperature",
                    sdk_parameter_status="SDK_PARAMETER_EXISTS",
                    model_specific_status="DEPRECATED_IGNORED_OMITTED",
                    sent_in_request=False,
                    configured_value="OMITTED",
                    verification_status=CapabilityVerificationStatus.UNSUPPORTED,
                    notes=(
                        "Official Gemini 3.8 documentation states custom temperature is deprecated/ignored "
                        "for Gemini 3.8 thinking models; omitted from C1 request."
                    ),
                ),
                "seed": SamplingCapabilitySpec(
                    parameter_name="seed",
                    sdk_parameter_name="GenerateContentConfig.seed",
                    sdk_parameter_status="SDK_PARAMETER_EXISTS",
                    model_specific_status="PENDING_LIVE_CONFIRMATION",
                    sent_in_request=True,
                    configured_value=FROZEN_SAMPLING_SEED,
                    verification_status=CapabilityVerificationStatus.PENDING_LIVE_CONFIRMATION,
                    notes=(
                        "GenerateContentConfig exposes seed: Optional[int] (fixed to 2026101508); "
                        "model-specific acceptance by gemini-3.8-flash is retained as PENDING_LIVE_CONFIRMATION for Phase 01B."
                    ),
                ),
                "top_p": SamplingCapabilitySpec(
                    parameter_name="top_p",
                    sdk_parameter_name="GenerateContentConfig.top_p",
                    sdk_parameter_status="SDK_PARAMETER_EXISTS",
                    model_specific_status="DEPRECATED_IGNORED_OMITTED",
                    sent_in_request=False,
                    configured_value="OMITTED",
                    verification_status=CapabilityVerificationStatus.UNSUPPORTED,
                    notes=(
                        "Official Gemini 3.8 documentation states custom top_p is deprecated/ignored "
                        "for Gemini 3.8 thinking models; omitted from C1 request."
                    ),
                ),
                "top_k": SamplingCapabilitySpec(
                    parameter_name="top_k",
                    sdk_parameter_name="GenerateContentConfig.top_k",
                    sdk_parameter_status="SDK_PARAMETER_EXISTS",
                    model_specific_status="DEPRECATED_IGNORED_OMITTED",
                    sent_in_request=False,
                    configured_value="OMITTED",
                    verification_status=CapabilityVerificationStatus.UNSUPPORTED,
                    notes=(
                        "Official Gemini 3.8 documentation states custom top_k is deprecated/ignored "
                        "for Gemini 3.8 thinking models; omitted from C1 request."
                    ),
                ),
                "thinking_or_reasoning_setting": SamplingCapabilitySpec(
                    parameter_name="thinking_or_reasoning_setting",
                    sdk_parameter_name="GenerateContentConfig.thinking_config",
                    sdk_parameter_status="SDK_PARAMETER_EXISTS",
                    model_specific_status="MODEL_SPECIFIC_PARAMETER_CONFIRMED",
                    sent_in_request=True,
                    configured_value={"thinking_level": FROZEN_GOOGLE_THINKING_LEVEL},
                    verification_status=CapabilityVerificationStatus.VERIFIED_BY_OFFICIAL_DOC_REFERENCE,
                    notes=(
                        "Gemini 3.8 Flash supports thinking_level ('low' / 'medium' / 'high'; documented default 'medium'); "
                        "explicitly frozen to types.ThinkingConfig(thinking_level='medium') and never tuned on DEV."
                    ),
                ),
                "max_output_tokens": SamplingCapabilitySpec(
                    parameter_name="max_output_tokens",
                    sdk_parameter_name="GenerateContentConfig.max_output_tokens",
                    sdk_parameter_status="SDK_PARAMETER_EXISTS",
                    model_specific_status="MODEL_SPECIFIC_PARAMETER_CONFIRMED",
                    sent_in_request=True,
                    configured_value=FROZEN_MAX_OUTPUT_TOKENS,
                    verification_status=CapabilityVerificationStatus.VERIFIED_BY_OFFICIAL_DOC_REFERENCE,
                    notes="GenerateContentConfig.max_output_tokens fixed to 16384.",
                ),
                "timeout": SamplingCapabilitySpec(
                    parameter_name="timeout",
                    sdk_parameter_name="HttpOptions.timeout",
                    sdk_parameter_status="SDK_PARAMETER_EXISTS",
                    model_specific_status="MODEL_SPECIFIC_PARAMETER_CONFIRMED",
                    sent_in_request=True,
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
        wiring = build_google_structured_output_wiring(COMMON_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA)
        # Note (Part D): temperature, top_p, and top_k are OMITTED from the Gemini 3.8 Flash request config.
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
                "seed": FROZEN_SAMPLING_SEED,
                "thinking_config": {
                    "thinking_level": FROZEN_GOOGLE_THINKING_LEVEL,
                },
                "max_output_tokens": FROZEN_MAX_OUTPUT_TOKENS,
                "response_mime_type": wiring["response_mime_type"],
                "response_json_schema": wiring["response_json_schema"],
                "tools": None,
                "automatic_function_calling_disabled": True,
                "timeout_ms": FROZEN_TIMEOUT_MS,
                "retry_attempts": 1,
            },
            "semantic_schema_sha256": SEMANTIC_SCHEMA_SHA256,
            "common_generation_schema_sha256": COMMON_GENERATION_SCHEMA_SHA256,
            "common_schema_sha256": COMMON_SCHEMA_SHA256,
        }

    def serialize_smoke_request_v2(
        self,
        scenario: BenchmarkScenarioInput,
        catalog_pois: List[BenchmarkCatalogPOI],
    ) -> Dict[str, Any]:
        """Serialize Phase 01D smoke request using Portable Generation Schema V2."""
        user_prompt = build_shared_semantic_user_prompt(scenario, catalog_pois)
        wiring = build_google_structured_output_wiring_v2()
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
                "seed": FROZEN_SAMPLING_SEED,
                "thinking_config": {
                    "thinking_level": FROZEN_GOOGLE_THINKING_LEVEL,
                },
                "max_output_tokens": FROZEN_MAX_OUTPUT_TOKENS,
                "response_mime_type": wiring["response_mime_type"],
                "response_json_schema": wiring["response_json_schema"],
                "tools": None,
                "automatic_function_calling_disabled": True,
                "timeout_ms": FROZEN_TIMEOUT_MS,
                "retry_attempts": 1,
            },
            "semantic_schema_sha256": SEMANTIC_SCHEMA_SHA256,
            "generation_schema_v1_sha256": COMMON_GENERATION_SCHEMA_SHA256_V1,
            "portable_generation_schema_v2_sha256": COMMON_PORTABLE_GENERATION_SCHEMA_SHA256_V2,
            "common_generation_schema_sha256": COMMON_PORTABLE_GENERATION_SCHEMA_SHA256_V2,
            "common_schema_sha256": COMMON_PORTABLE_GENERATION_SCHEMA_SHA256_V2,
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
            thinking_lvl = cfg_dict["thinking_config"]["thinking_level"]
            call_config = types.GenerateContentConfig(
                system_instruction=cfg_dict["system_instruction"],
                seed=cfg_dict["seed"],
                thinking_config=types.ThinkingConfig(thinking_level=thinking_lvl),
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

        is_refusal = False
        candidates = getattr(resp, "candidates", None) or []
        if candidates:
            finish_reason = str(getattr(candidates[0], "finish_reason", "") or "").upper()
            if any(tok in finish_reason for tok in ("SAFETY", "BLOCKLIST", "PROHIBITED", "RECITATION", "REFUSAL")):
                is_refusal = True

        return raw_text, returned_model, usage, is_refusal
