"""Offline Preflight Adapter for Candidate C2: OpenAI / gpt-6.1-sol (W06-MODEL-PREFLIGHT-01A-OFFLINE).

SDK: openai==3.17.0
Endpoint semantics: chat.completions.create (POST /v1/chat/completions)
Structured output: response_format={'type': 'json_schema', 'json_schema': {'name': 'BenchmarkPlanResponse', 'strict': True, 'schema': <schema>}}
Retry=0 mechanism: openai.OpenAI(max_retries=0, timeout=55.0, http_client=...)
"""
from importlib.metadata import version as pkg_version
from typing import Any, Dict, List, Optional, Tuple

import httpx2
import openai

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
    build_openai_structured_output_wiring,
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


class OpenAIPreflightAdapter(BasePreflightProviderAdapter):
    """Evaluation-only preflight adapter for C2 (OpenAI / gpt-6.1-sol)."""

    candidate_id = "C2"
    provider_name = "OpenAI"
    requested_model_id = "gpt-6.1-sol"
    sdk_package = "openai"

    def __init__(self, *, live_allowed: Optional[bool] = None) -> None:
        super().__init__(live_allowed=live_allowed)
        self.sdk_version = pkg_version("openai")

    def get_preflight_record(self) -> CandidatePreflightRecord:
        wiring = build_openai_structured_output_wiring(COMMON_BENCHMARK_PLAN_JSON_SCHEMA)
        return CandidatePreflightRecord(
            candidate_id=self.candidate_id,
            provider=self.provider_name,
            requested_model_id=self.requested_model_id,
            role="CANDIDATE_NOT_SELECTED_FINAL_MODEL",
            sdk_package=self.sdk_package,
            sdk_version=self.sdk_version,
            provider_documentation_url="https://platform.openai.com/docs/guides/structured-outputs",
            access_date="2026-10-17",
            endpoint_semantics="openai.OpenAI.chat.completions.create (POST /v1/chat/completions)",
            endpoint_verification_status=CapabilityVerificationStatus.VERIFIED_BY_SDK_SURFACE,
            live_model_id_status=CapabilityVerificationStatus.PENDING_LIVE_CONFIRMATION,
            structured_output_mode="NATIVE_JSON_SCHEMA_STRICT",
            structured_output_wiring_summary={
                "response_format_type": wiring["response_format"]["type"],
                "schema_name": wiring["response_format"]["json_schema"]["name"],
                "strict": wiring["response_format"]["json_schema"]["strict"],
                "common_schema_sha256": wiring["common_schema_sha256"],
            },
            structured_output_capability_status=CapabilityVerificationStatus.VERIFIED_BY_SDK_SURFACE,
            common_schema_sha256=COMMON_SCHEMA_SHA256,
            place_id_encoded_as_catalog_enum=False,
            sampling_capabilities={
                "temperature": SamplingCapabilitySpec(
                    parameter_name="temperature",
                    sdk_parameter_name="chat.completions.create(temperature=...)",
                    configured_value=FROZEN_SAMPLING_TEMPERATURE,
                    verification_status=CapabilityVerificationStatus.VERIFIED_BY_SDK_SURFACE,
                    notes=(
                        "chat.completions.create exposes temperature: Optional[float] (fixed to 0.0 on SDK surface; "
                        "runtime acceptance by model gpt-6.1-sol is PENDING_LIVE_CONFIRMATION in Phase 01B)."
                    ),
                ),
                "seed": SamplingCapabilitySpec(
                    parameter_name="seed",
                    sdk_parameter_name="chat.completions.create(seed=...)",
                    configured_value=FROZEN_SAMPLING_SEED,
                    verification_status=CapabilityVerificationStatus.VERIFIED_BY_SDK_SURFACE,
                    notes="chat.completions.create exposes seed: Optional[int]; fixed to 2026101508 per Method Lock.",
                ),
                "top_p": SamplingCapabilitySpec(
                    parameter_name="top_p",
                    sdk_parameter_name="chat.completions.create(top_p=...)",
                    configured_value=None,
                    verification_status=CapabilityVerificationStatus.VERIFIED_BY_SDK_SURFACE,
                    notes="chat.completions.create exposes top_p: Optional[float]; left None (not tuned).",
                ),
                "top_k": SamplingCapabilitySpec(
                    parameter_name="top_k",
                    sdk_parameter_name=None,
                    configured_value="UNSUPPORTED",
                    verification_status=CapabilityVerificationStatus.UNSUPPORTED,
                    notes="OpenAI Chat Completions API/SDK does not support a top_k sampling parameter.",
                ),
                "thinking_or_reasoning_setting": SamplingCapabilitySpec(
                    parameter_name="thinking_or_reasoning_setting",
                    sdk_parameter_name="chat.completions.create(reasoning_effort=...)",
                    configured_value=None,
                    verification_status=CapabilityVerificationStatus.VERIFIED_BY_SDK_SURFACE,
                    notes="chat.completions.create exposes reasoning_effort; fixed to None (default provider mode, never tuned on DEV).",
                ),
                "max_output_tokens": SamplingCapabilitySpec(
                    parameter_name="max_output_tokens",
                    sdk_parameter_name="chat.completions.create(max_completion_tokens=...)",
                    configured_value=FROZEN_MAX_OUTPUT_TOKENS,
                    verification_status=CapabilityVerificationStatus.VERIFIED_BY_SDK_SURFACE,
                    notes="chat.completions.create exposes max_completion_tokens: Optional[int]; fixed to 16384.",
                ),
                "timeout": SamplingCapabilitySpec(
                    parameter_name="timeout",
                    sdk_parameter_name="OpenAI(timeout=...)",
                    configured_value=FROZEN_TIMEOUT_MS,
                    verification_status=CapabilityVerificationStatus.VERIFIED_BY_SDK_SURFACE,
                    notes="OpenAI client timeout configured as 55.0 seconds (55000 ms).",
                ),
            },
            retry_configuration=CandidateRetryConfigRecord(
                sdk_automatic_retry=0,
                transport_retry=0,
                sdk_retry_mechanism="openai.OpenAI(max_retries=0, timeout=55.0, http_client=httpx2.Client(transport=...))",
                verification_status=CapabilityVerificationStatus.OFFLINE_TEST_VERIFIED,
            ),
            model_metadata_check=CandidateModelMetadataCheckRecord(
                response_metadata_field="ChatCompletion.model",
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
        wiring = build_openai_structured_output_wiring(COMMON_BENCHMARK_PLAN_JSON_SCHEMA)
        return {
            "candidate_id": self.candidate_id,
            "provider": self.provider_name,
            "model": self.requested_model_id,
            "system_prompt": PREFLIGHT_SHARED_SYSTEM_PROMPT,
            "system_prompt_sha256": sha256_bytes(PREFLIGHT_SHARED_SYSTEM_PROMPT.encode("utf-8")),
            "user_prompt": user_prompt,
            "user_prompt_sha256": sha256_bytes(user_prompt.encode("utf-8")),
            "config": {
                "messages": [
                    {"role": "system", "content": PREFLIGHT_SHARED_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": FROZEN_SAMPLING_TEMPERATURE,
                "seed": FROZEN_SAMPLING_SEED,
                "top_p": None,
                "top_k": "UNSUPPORTED",
                "reasoning_effort": None,
                "max_completion_tokens": FROZEN_MAX_OUTPUT_TOKENS,
                "response_format": wiring["response_format"],
                "tools": None,
                "timeout_seconds": FROZEN_TIMEOUT_MS / 1000.0,
                "max_retries": 0,
            },
            "common_schema_sha256": COMMON_SCHEMA_SHA256,
        }

    def _invoke_single_sdk_call_with_transport(
        self,
        *,
        request_payload: Dict[str, Any],
        mock_transport: Any,
    ) -> Tuple[Optional[str], Optional[str], BenchmarkUsageMetadata, bool]:
        http_client = httpx2.Client(transport=mock_transport)
        try:
            client = openai.OpenAI(
                api_key="OFFLINE_PREFLIGHT_DUMMY_KEY",
                max_retries=0,
                timeout=FROZEN_TIMEOUT_MS / 1000.0,
                http_client=http_client,
            )
            cfg = request_payload["config"]
            resp = client.chat.completions.create(
                model=request_payload["model"],
                messages=cfg["messages"],
                temperature=cfg["temperature"],
                seed=cfg["seed"],
                max_completion_tokens=cfg["max_completion_tokens"],
                response_format=cfg["response_format"],
            )
        finally:
            http_client.close()

        returned_model = getattr(resp, "model", None)
        choices = getattr(resp, "choices", None) or []
        raw_text: Optional[str] = None
        is_refusal = False
        if choices:
            msg = getattr(choices[0], "message", None)
            if msg is not None:
                refusal_val = getattr(msg, "refusal", None)
                if isinstance(refusal_val, str) and refusal_val.strip():
                    is_refusal = True
                    raw_text = refusal_val
                else:
                    raw_text = getattr(msg, "content", None)

        usage_obj = getattr(resp, "usage", None)
        usage = BenchmarkUsageMetadata(
            input_tokens=getattr(usage_obj, "prompt_tokens", None) if usage_obj else None,
            output_tokens=getattr(usage_obj, "completion_tokens", None) if usage_obj else None,
            total_tokens=getattr(usage_obj, "total_tokens", None) if usage_obj else None,
        )
        return raw_text, returned_model, usage, is_refusal
