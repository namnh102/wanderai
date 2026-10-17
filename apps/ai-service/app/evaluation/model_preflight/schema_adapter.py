"""Semantic vs. Strict Generation JSON Schema Authority and Equivalence Guard for W06 Model Preflight.

Grounded in W06-MODEL-ARCH-SELECTION-METHOD-LOCK-01 Section 7 & W06-MODEL-PREFLIGHT-01A-FIX-01 Part G:
1. SEMANTIC_BENCHMARK_PLAN_JSON_SCHEMA:
   Raw Pydantic JSON schema produced directly by BenchmarkPlanResponse.model_json_schema().
   Hashed as SEMANTIC_SCHEMA_SHA256 via SHA256_CANONICAL_JSON_UTF8_LF_BYTES.
2. COMMON_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA:
   Strict structured-output projection shared identically across C1 (Google), C2 (OpenAI), and C3 (Anthropic).
   Hashed as COMMON_GENERATION_SCHEMA_SHA256 via SHA256_CANONICAL_JSON_UTF8_LF_BYTES.
3. Automated structural-diff / equivalence guard (verify_strict_generation_schema_projection):
   Proves that the strict generation schema projection changes ONLY approved serialization mechanics:
   - removal of 'default' metadata
   - materialization of 'required' with all object property names in sorted order
   - enforcement of 'additionalProperties': False on object nodes
   And NEVER changes:
   - property names
   - primitive types / $ref / anyOf
   - enum domains
   - numeric bounds (minimum, maximum, exclusiveMinimum, exclusiveMaximum)
   - array/string min/max semantics (minItems, maxItems, minLength, maxLength)
   - place_id semantics (nullable string, never a catalog enum)
   - ActivityKind semantics (enum == ['POI_VISIT', 'TRANSIT_ONLY'])
"""
import copy
from typing import Any, Dict, List

from app.evaluation.model_preflight.types import FROZEN_CLAUDE_EFFORT
from app.schemas.planner_benchmark import BenchmarkPlanResponse
from app.services.planner_benchmark_runner import canonical_json_bytes, sha256_bytes

APPROVED_PROJECTION_KEYS = frozenset({"default", "required", "additionalProperties"})
PROTECTED_SEMANTIC_KEYS = (
    "type",
    "$ref",
    "anyOf",
    "enum",
    "const",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "minItems",
    "maxItems",
    "minLength",
    "maxLength",
    "pattern",
)


def build_semantic_benchmark_plan_json_schema() -> Dict[str, Any]:
    """Return the raw semantic JSON schema directly from BenchmarkPlanResponse.model_json_schema()."""
    return copy.deepcopy(BenchmarkPlanResponse.model_json_schema())


def compute_semantic_schema_sha256() -> str:
    """Compute canonical SHA256 of the raw semantic BenchmarkPlanResponse.model_json_schema()."""
    return sha256_bytes(canonical_json_bytes(build_semantic_benchmark_plan_json_schema()))


def _project_strict_generation_schema_node(node: Any) -> Any:
    """Recursively project a semantic JSON schema node into the strict structured-output generation schema.

    Approved transformations ONLY:
    - remove 'default' metadata
    - set 'additionalProperties': False on object nodes with 'properties'
    - materialize 'required' as sorted(properties.keys()) on object nodes with 'properties'
    """
    if isinstance(node, dict):
        out: Dict[str, Any] = {}
        for k, v in node.items():
            if k == "default":
                continue
            out[k] = _project_strict_generation_schema_node(v)

        if out.get("type") == "object" and "properties" in out and isinstance(out["properties"], dict):
            out["additionalProperties"] = False
            out["required"] = sorted(out["properties"].keys())
        return out
    if isinstance(node, list):
        return [_project_strict_generation_schema_node(item) for item in node]
    return node


def build_common_generation_benchmark_plan_json_schema() -> Dict[str, Any]:
    """Build the strict structured-output generation schema projection shared across all providers."""
    semantic = build_semantic_benchmark_plan_json_schema()
    return _project_strict_generation_schema_node(semantic)


def compute_common_generation_schema_sha256() -> str:
    """Compute canonical SHA256 of the strict structured-output generation schema projection."""
    return sha256_bytes(canonical_json_bytes(build_common_generation_benchmark_plan_json_schema()))


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


def verify_strict_generation_schema_projection(
    semantic_schema: Dict[str, Any] | None = None,
    generation_schema: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Automated structural-diff and semantic-equivalence guard between semantic and generation schemas (Part G).

    Raises ValueError if any unapproved semantic mutation is detected.
    """
    sem = semantic_schema if semantic_schema is not None else build_semantic_benchmark_plan_json_schema()
    gen = (
        generation_schema
        if generation_schema is not None
        else build_common_generation_benchmark_plan_json_schema()
    )

    removed_defaults_paths: List[str] = []
    materialized_required_paths: List[str] = []
    additional_props_closed_paths: List[str] = []

    def _compare(s_node: Any, g_node: Any, path: str) -> None:
        if type(s_node) is not type(g_node):
            raise ValueError(f"Schema node type mismatch at {path}: {type(s_node)} vs {type(g_node)}")

        if isinstance(s_node, dict):
            if "default" in g_node:
                raise ValueError(f"Generation schema retained unremoved 'default' at {path}")
            if "default" in s_node:
                removed_defaults_paths.append(path)

            # Verify no unapproved keys were added or removed
            s_keys_non_approved = set(s_node.keys()) - APPROVED_PROJECTION_KEYS
            g_keys_non_approved = set(g_node.keys()) - APPROVED_PROJECTION_KEYS
            if s_keys_non_approved != g_keys_non_approved:
                raise ValueError(
                    f"Unapproved key set change at {path}: "
                    f"semantic={sorted(s_keys_non_approved)} vs generation={sorted(g_keys_non_approved)}"
                )

            # Verify all protected semantic keys match identically (except recursive containers)
            for pk in PROTECTED_SEMANTIC_KEYS:
                if pk in s_node or pk in g_node:
                    if pk == "anyOf":
                        s_any = s_node.get("anyOf", [])
                        g_any = g_node.get("anyOf", [])
                        if len(s_any) != len(g_any):
                            raise ValueError(f"anyOf length mismatch at {path}")
                        for idx, (sa, ga) in enumerate(zip(s_any, g_any)):
                            _compare(sa, ga, f"{path}.anyOf[{idx}]")
                    else:
                        if s_node.get(pk) != g_node.get(pk):
                            raise ValueError(
                                f"Protected semantic constraint '{pk}' changed at {path}: "
                                f"{s_node.get(pk)!r} -> {g_node.get(pk)!r}"
                            )

            # Verify object properties and strict closure rules
            if "properties" in s_node:
                s_props = s_node["properties"]
                g_props = g_node.get("properties")
                if not isinstance(s_props, dict) or not isinstance(g_props, dict):
                    raise ValueError(f"Invalid properties container at {path}")
                if set(s_props.keys()) != set(g_props.keys()):
                    raise ValueError(
                        f"Property names changed at {path}: "
                        f"{sorted(s_props.keys())} vs {sorted(g_props.keys())}"
                    )
                if g_node.get("additionalProperties") is not False:
                    raise ValueError(f"additionalProperties must be False at {path}")
                additional_props_closed_paths.append(path)

                expected_req = sorted(s_props.keys())
                if g_node.get("required") != expected_req:
                    raise ValueError(
                        f"required list at {path} must equal sorted property keys {expected_req}"
                    )
                materialized_required_paths.append(path)

                for prop_name in sorted(s_props.keys()):
                    _compare(s_props[prop_name], g_props[prop_name], f"{path}.properties.{prop_name}")

            # Verify $defs recursively
            if "$defs" in s_node:
                s_defs = s_node["$defs"]
                g_defs = g_node.get("$defs")
                if not isinstance(s_defs, dict) or not isinstance(g_defs, dict):
                    raise ValueError(f"Invalid $defs container at {path}")
                if set(s_defs.keys()) != set(g_defs.keys()):
                    raise ValueError(
                        f"$defs keys changed at {path}: {sorted(s_defs.keys())} vs {sorted(g_defs.keys())}"
                    )
                for def_name in sorted(s_defs.keys()):
                    _compare(s_defs[def_name], g_defs[def_name], f"{path}.$defs.{def_name}")

            # Verify array items recursively
            if "items" in s_node:
                _compare(s_node["items"], g_node["items"], f"{path}.items")

        elif isinstance(s_node, list):
            if len(s_node) != len(g_node):
                raise ValueError(f"List length mismatch at {path}: {len(s_node)} vs {len(g_node)}")
            for idx, (s_item, g_item) in enumerate(zip(s_node, g_node)):
                _compare(s_item, g_item, f"{path}[{idx}]")
        else:
            if s_node != g_node:
                raise ValueError(f"Scalar value changed at {path}: {s_node!r} -> {g_node!r}")

    _compare(sem, gen, "$")

    # Explicit domain checks on place_id and ActivityKind
    if schema_encodes_place_id_as_catalog_enum(sem) or schema_encodes_place_id_as_catalog_enum(gen):
        raise ValueError("place_id must never be encoded as a catalog enum.")

    activity_kind_def = gen.get("$defs", {}).get("ActivityKind", {})
    if activity_kind_def.get("enum") != ["POI_VISIT", "TRANSIT_ONLY"]:
        raise ValueError(f"ActivityKind enum altered: {activity_kind_def.get('enum')!r}")

    item_place_id = (
        gen.get("$defs", {})
        .get("BenchmarkItineraryItem", {})
        .get("properties", {})
        .get("place_id", {})
    )
    if item_place_id != {"anyOf": [{"type": "string"}, {"type": "null"}], "title": "Place Id"}:
        raise ValueError(f"place_id schema altered unexpectedly: {item_place_id!r}")

    return {
        "whitelist_guard_passed": True,
        "semantic_schema_sha256": sha256_bytes(canonical_json_bytes(sem)),
        "common_generation_schema_sha256": sha256_bytes(canonical_json_bytes(gen)),
        "approved_mechanics_applied": [
            "default_metadata_removal",
            "required_field_materialization_sorted",
            "additionalProperties_false_closure",
        ],
        "removed_defaults_count": len(removed_defaults_paths),
        "materialized_required_objects_count": len(materialized_required_paths),
        "additional_properties_closed_objects_count": len(additional_props_closed_paths),
        "place_id_catalog_enum_present": False,
        "activity_kind_enum_preserved": True,
    }


SEMANTIC_BENCHMARK_PLAN_JSON_SCHEMA: Dict[str, Any] = build_semantic_benchmark_plan_json_schema()
SEMANTIC_SCHEMA_SHA256: str = compute_semantic_schema_sha256()

COMMON_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA: Dict[str, Any] = (
    build_common_generation_benchmark_plan_json_schema()
)
COMMON_GENERATION_SCHEMA_SHA256: str = compute_common_generation_schema_sha256()

# Backwards-compatible aliases pointing to the strict generation schema
COMMON_BENCHMARK_PLAN_JSON_SCHEMA: Dict[str, Any] = COMMON_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA
COMMON_SCHEMA_SHA256: str = COMMON_GENERATION_SCHEMA_SHA256
build_common_benchmark_plan_json_schema = build_common_generation_benchmark_plan_json_schema
compute_common_schema_sha256 = compute_common_generation_schema_sha256


def build_google_structured_output_wiring(
    schema: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Build Google (C1) technical structured-output wiring for GenerateContentConfig."""
    target_schema = copy.deepcopy(schema or COMMON_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA)
    gen_sha = sha256_bytes(canonical_json_bytes(target_schema))
    return {
        "response_mime_type": "application/json",
        "response_json_schema": target_schema,
        "semantic_schema_sha256": SEMANTIC_SCHEMA_SHA256,
        "common_generation_schema_sha256": gen_sha,
        "common_schema_sha256": gen_sha,
    }


def build_openai_structured_output_wiring(
    schema: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Build OpenAI (C2) technical structured-output wiring for chat.completions.create."""
    target_schema = copy.deepcopy(schema or COMMON_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA)
    gen_sha = sha256_bytes(canonical_json_bytes(target_schema))
    return {
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "BenchmarkPlanResponse",
                "strict": True,
                "schema": target_schema,
            },
        },
        "semantic_schema_sha256": SEMANTIC_SCHEMA_SHA256,
        "common_generation_schema_sha256": gen_sha,
        "common_schema_sha256": gen_sha,
    }


def build_anthropic_structured_output_wiring(
    schema: Dict[str, Any] | None = None,
    *,
    effort: str = FROZEN_CLAUDE_EFFORT,
) -> Dict[str, Any]:
    """Build Anthropic (C3) technical structured-output wiring for messages.create (Part E).

    Includes both fixed effort='high' and native JSON schema format in output_config.
    """
    target_schema = copy.deepcopy(schema or COMMON_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA)
    gen_sha = sha256_bytes(canonical_json_bytes(target_schema))
    return {
        "output_config": {
            "effort": effort,
            "format": {
                "type": "json_schema",
                "schema": target_schema,
            },
        },
        "semantic_schema_sha256": SEMANTIC_SCHEMA_SHA256,
        "common_generation_schema_sha256": gen_sha,
        "common_schema_sha256": gen_sha,
    }
