"""Provider-neutral JSON schema generator and technical structured-output wiring for W06 Model Preflight.

Grounded in W06-MODEL-ARCH-SELECTION-METHOD-LOCK-01 Section 7 (Structured Output Policy):
- Generates one common semantic JSON schema directly from BenchmarkPlanResponse.
- Computes COMMON_SCHEMA_SHA256 using SHA256_CANONICAL_JSON_UTF8_LF_BYTES.
- Verifies place_id is NOT encoded as a provider-side enum of catalog IDs.
- Translates ONLY technical provider wiring for Google (C1), OpenAI (C2), and Anthropic (C3).
"""
import copy
from typing import Any, Dict

from app.schemas.planner_benchmark import BenchmarkPlanResponse
from app.services.planner_benchmark_runner import canonical_json_bytes, sha256_bytes


def _normalize_strict_json_schema_node(node: Any) -> Any:
    """Recursively normalize a JSON schema node for strict structured output compliance across providers.

    - Preserves exact semantic structure of BenchmarkPlanResponse.
    - Sets additionalProperties: False on every object node.
    - Ensures 'required' lists all object properties in deterministic sorted order for strict JSON schema mode.
    - Strips non-semantic Pydantic title metadata only if needed? No, keeping deterministic properties and
      enforcing strict object closure works cleanly across Google, OpenAI strict mode, and Anthropic json_schema.
    """
    if isinstance(node, dict):
        out: Dict[str, Any] = {}
        for k, v in node.items():
            if k == "default":
                # OpenAI/Anthropic strict json_schema modes require all fields in 'required' without relying on omitted defaults
                continue
            out[k] = _normalize_strict_json_schema_node(v)

        if out.get("type") == "object" and "properties" in out and isinstance(out["properties"], dict):
            out["additionalProperties"] = False
            out["required"] = sorted(out["properties"].keys())
        return out
    if isinstance(node, list):
        return [_normalize_strict_json_schema_node(item) for item in node]
    return node


def build_common_benchmark_plan_json_schema() -> Dict[str, Any]:
    """Build the canonical provider-neutral JSON schema for BenchmarkPlanResponse."""
    raw_schema = BenchmarkPlanResponse.model_json_schema()
    normalized = _normalize_strict_json_schema_node(copy.deepcopy(raw_schema))
    return normalized


def compute_common_schema_sha256() -> str:
    """Compute SHA256 of the common BenchmarkPlanResponse JSON schema using SHA256_CANONICAL_JSON_UTF8_LF_BYTES."""
    schema = build_common_benchmark_plan_json_schema()
    return sha256_bytes(canonical_json_bytes(schema))


def schema_encodes_place_id_as_catalog_enum(schema: Dict[str, Any]) -> bool:
    """Verify recursively that 'place_id' is NEVER constrained to an enum of catalog place IDs."""

    def _walk(node: Any, key_name: str = "") -> bool:
        if isinstance(node, dict):
            if key_name == "place_id":
                if "enum" in node:
                    return True
                for sub in node.get("anyOf", []):
                    if isinstance(sub, dict) and "enum" in sub:
                        return True
            for k, v in node.items():
                if _walk(v, k):
                    return True
        elif isinstance(node, list):
            for item in node:
                if _walk(item, key_name):
                    return True
        return False

    return _walk(schema)


COMMON_BENCHMARK_PLAN_JSON_SCHEMA: Dict[str, Any] = build_common_benchmark_plan_json_schema()
COMMON_SCHEMA_SHA256: str = compute_common_schema_sha256()


def build_google_structured_output_wiring(
    schema: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Build Google (C1) technical structured-output wiring for GenerateContentConfig."""
    target_schema = copy.deepcopy(schema or COMMON_BENCHMARK_PLAN_JSON_SCHEMA)
    return {
        "response_mime_type": "application/json",
        "response_json_schema": target_schema,
        "common_schema_sha256": sha256_bytes(canonical_json_bytes(target_schema)),
    }


def build_openai_structured_output_wiring(
    schema: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Build OpenAI (C2) technical structured-output wiring for chat.completions.create."""
    target_schema = copy.deepcopy(schema or COMMON_BENCHMARK_PLAN_JSON_SCHEMA)
    return {
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "BenchmarkPlanResponse",
                "strict": True,
                "schema": target_schema,
            },
        },
        "common_schema_sha256": sha256_bytes(canonical_json_bytes(target_schema)),
    }


def build_anthropic_structured_output_wiring(
    schema: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Build Anthropic (C3) technical structured-output wiring for messages.create."""
    target_schema = copy.deepcopy(schema or COMMON_BENCHMARK_PLAN_JSON_SCHEMA)
    return {
        "output_config": {
            "format": {
                "type": "json_schema",
                "schema": target_schema,
            },
        },
        "common_schema_sha256": sha256_bytes(canonical_json_bytes(target_schema)),
    }
