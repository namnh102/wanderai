"""Offline Preflight Adapter for Candidate C3: Anthropic / claude-sonnet-5-5 (W06-MODEL-PREFLIGHT-01A-OFFLINE).

SDK: anthropic==1.15.0
Endpoint semantics: messages.create (POST /v1/messages)
Structured output: output_config={'format': {'type': 'json_schema', 'schema': <schema>}}
Retry=0 mechanism: anthropic.Anthropic(max_retries=0, timeout=55.0, http_client=...)
Sampling note on anthropic==1.15.0:
- In anthropic==1.15.0, messages.create exposes system, messages, max_tokens, output_config (effort, format), thinking, tools, tool_choice, timeout.
- temperature, seed, top_p, and top_k are NOT exposed on the anthropic==1.15.0 messages.create SDK signature and are recorded as UNSUPPORTED with documented fixed provider behavior per Section 9.
"""
from importlib.metadata import version as pkg_version
from typing import Any, Dict, List, Optional, Tuple

import anthropic
import httpx2

from app.evaluation.model_preflight.base import (
    FROZEN_MAX_OUTPUT_TOKENS,
    FROZEN_TIMEOUT_MS,
    PREFLIGHT_SHARED_SYSTEM_PROMPT,
    BasePreflightProviderAdapter,
    build_shared_semantic_user_prompt,
)
from app.evaluation.model_preflight.schema_adapter import (
    COMMON_BENCHMARK_PLAN_JSON_SCHEMA,
    COMMON_SCHEMA_SHA256,
    build_anthropic_structured_output_wiring,
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


class AnthropicPreflightAdapter(BasePreflightProviderAdapter):
    """Evaluation-only preflight adapter for C3 (Anthropic / claude-sonnet-5-5)."""

    candidate_id = "C3"
    provider_name = "Anthropic"
    requested_model_id = "claude-sonnet-5-5"
    sdk_package = "anthropic"

    def __init__(self, *, live_allowed: Optional[bool] = None) -> None:
        super().__init__(live_allowed=live_allowed)
        self.sdk_version = pkg_version("anthropic")

    def get_preflight_record(self) -> CandidatePreflightRecord:
        wiring = build_anthropic_structured_output_wiring(COMMON_BENCHMARK_PLAN_JSON_SCHEMA)
        return CandidatePreflightRecord(
            candidate_id=self.candidate_id,
            provider=self.provider_name,
            requested_model_id=self.requested_model_id,
            role="CANDIDATE_NOT_SELECTED_FINAL_MODEL",
            sdk_package=self.sdk_package,
            sdk_version=self.sdk_version,
            provider_documentation_url="https://docs.anthropic.com/en/docs/build-with-claude/structured-outputs",
            access_date="2026-10-17",
            endpoint_semantics="anthropic.Anthropic.messages.create (POST /v1/messages)",
            endpoint_verification_status=CapabilityVerificationStatus.VERIFIED_BY_SDK_SURFACE,
            live_model_id_status=CapabilityVerificationStatus.PENDING_LIVE_CONFIRMATION,
            structured_output_mode="NATIVE_OUTPUT_CONFIG_JSON_SCHEMA",
            structured_output_wiring_summary={
                "output_config_format_type": wiring["output_config"]["format"]["type"],
                "schema_parameter": "messages.create(output_config={'format': {'type': 'json_schema', 'schema': ...}})",
                "common_schema_sha256": wiring["common_schema_sha256"],
            },
            structured_output_capability_status=CapabilityVerificationStatus.VERIFIED_BY_SDK_SURFACE,
            common_schema_sha256=COMMON_SCHEMA_SHA256,
            place_id_encoded_as_catalog_enum=False,
            sampling_capabilities={
                "temperature": SamplingCapabilitySpec(
                    parameter_name="temperature",
                    sdk_parameter_name=None,
                    configured_value="UNSUPPORTED",
                    verification_status=CapabilityVerificationStatus.UNSUPPORTED,
                    notes=(
                        "In anthropic==1.15.0, Messages.create does not expose a temperature parameter "
                        "(fixed provider default sampling behavior used; documented per Method Lock Section 9)."
                    ),
                ),
                "seed": SamplingCapabilitySpec(
                    parameter_name="seed",
                    sdk_parameter_name=None,
                    configured_value="UNSUPPORTED",
                    verification_status=CapabilityVerificationStatus.UNSUPPORTED,
                    notes="Anthropic Messages API / anthropic==1.15.0 does not support a deterministic seed parameter.",
                ),
                "top_p": SamplingCapabilitySpec(
                    parameter_name="top_p",
                    sdk_parameter_name=None,
                    configured_value="UNSUPPORTED",
                    verification_status=CapabilityVerificationStatus.UNSUPPORTED,
                    notes="In anthropic==1.15.0, Messages.create does not expose a top_p parameter.",
                ),
                "top_k": SamplingCapabilitySpec(
                    parameter_name="top_k",
                    sdk_parameter_name=None,
                    configured_value="UNSUPPORTED",
                    verification_status=CapabilityVerificationStatus.UNSUPPORTED,
                    notes="In anthropic==1.15.0, Messages.create does not expose a top_k parameter.",
                ),
                "thinking_or_reasoning_setting": SamplingCapabilitySpec(
                    parameter_name="thinking_or_reasoning_setting",
                    sdk_parameter_name="messages.create(thinking=...)",
                    configured_value={"type": "disabled"},
                    verification_status=CapabilityVerificationStatus.VERIFIED_BY_SDK_SURFACE,
                    notes="Messages.create exposes thinking: ThinkingConfigParam; fixed to {'type': 'disabled'} (never tuned on DEV).",
                ),
                "max_output_tokens": SamplingCapabilitySpec(
                    parameter_name="max_output_tokens",
                    sdk_parameter_name="messages.create(max_tokens=...)",
                    configured_value=FROZEN_MAX_OUTPUT_TOKENS,
                    verification_status=CapabilityVerificationStatus.VERIFIED_BY_SDK_SURFACE,
                    notes="Messages.create exposes max_tokens: int; fixed to 16384.",
                ),
                "timeout": SamplingCapabilitySpec(
                    parameter_name="timeout",
                    sdk_parameter_name="Anthropic(timeout=...)",
                    configured_value=FROZEN_TIMEOUT_MS,
                    verification_status=CapabilityVerificationStatus.VERIFIED_BY_SDK_SURFACE,
                    notes="Anthropic client timeout configured as 55.0 seconds (55000 ms).",
                ),
            },
            retry_configuration=CandidateRetryConfigRecord(
                sdk_automatic_retry=0,
                transport_retry=0,
                sdk_retry_mechanism="anthropic.Anthropic(max_retries=0, timeout=55.0, http_client=httpx2.Client(transport=...))",
                verification_status=CapabilityVerificationStatus.OFFLINE_TEST_VERIFIED,
            ),
            model_metadata_check=CandidateModelMetadataCheckRecord(
                response_metadata_field="Message.model",
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
        wiring = build_anthropic_structured_output_wiring(COMMON_BENCHMARK_PLAN_JSON_SCHEMA)
        return {
            "candidate_id": self.candidate_id,
            "provider": self.provider_name,
            "model": self.requested_model_id,
            "system_prompt": PREFLIGHT_SHARED_SYSTEM_PROMPT,
            "system_prompt_sha256": sha256_bytes(PREFLIGHT_SHARED_SYSTEM_PROMPT.encode("utf-8")),
            "user_prompt": user_prompt,
            "user_prompt_sha256": sha256_bytes(user_prompt.encode("utf-8")),
            "config": {
                "system": PREFLIGHT_SHARED_SYSTEM_PROMPT,
                "messages": [
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": "UNSUPPORTED",
                "seed": "UNSUPPORTED",
                "top_p": "UNSUPPORTED",
                "top_k": "UNSUPPORTED",
                "thinking": {"type": "disabled"},
                "max_tokens": FROZEN_MAX_OUTPUT_TOKENS,
                "output_config": wiring["output_config"],
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
            client = anthropic.Anthropic(
                api_key="OFFLINE_PREFLIGHT_DUMMY_KEY",
                max_retries=0,
                timeout=FROZEN_TIMEOUT_MS / 1000.0,
                http_client=http_client,
            )
            cfg = request_payload["config"]
            resp = client.messages.create(
                model=request_payload["model"],
                max_tokens=cfg["max_tokens"],
                system=cfg["system"],
                messages=cfg["messages"],
                thinking=cfg["thinking"],
                output_config=cfg["output_config"],
            )
        finally:
            http_client.close()

        returned_model = getattr(resp, "model", None)
        stop_reason = str(getattr(resp, "stop_reason", "") or "").lower()
        is_refusal = stop_reason == "refusal"

        content_blocks = getattr(resp, "content", None) or []
        raw_text_parts: List[str] = []
        for block in content_blocks:
            block_text = getattr(block, "text", None)
            if isinstance(block_text, str):
                raw_text_parts.append(block_text)
        raw_text = "".join(raw_text_parts) if raw_text_parts else None

        usage_obj = getattr(resp, "usage", None)
        in_tok = getattr(usage_obj, "input_tokens", None) if usage_obj else None
        out_tok = getattr(usage_obj, "output_tokens", None) if usage_obj else None
        tot_tok = (in_tok + out_tok) if (isinstance(in_tok, int) and isinstance(out_tok, int)) else None
        usage = BenchmarkUsageMetadata(
            input_tokens=in_tok,
            output_tokens=out_tok,
            total_tokens=tot_tok,
        )
        return raw_text, returned_model, usage, is_refusal
