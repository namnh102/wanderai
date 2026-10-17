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

# Explicit V1 identifiers (preserving historical 01A/01B generation schema authority)
COMMON_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA_V1: Dict[str, Any] = (
    COMMON_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA
)
COMMON_GENERATION_SCHEMA_SHA256_V1: str = COMMON_GENERATION_SCHEMA_SHA256
build_common_generation_benchmark_plan_json_schema_v1 = (
    build_common_generation_benchmark_plan_json_schema
)
compute_common_generation_schema_sha256_v1 = compute_common_generation_schema_sha256

# Backwards-compatible aliases pointing to the strict V1 generation schema
COMMON_BENCHMARK_PLAN_JSON_SCHEMA: Dict[str, Any] = COMMON_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA
COMMON_SCHEMA_SHA256: str = COMMON_GENERATION_SCHEMA_SHA256
build_common_benchmark_plan_json_schema = build_common_generation_benchmark_plan_json_schema
compute_common_schema_sha256 = compute_common_generation_schema_sha256

# ==============================================================================
# PHASE 01C: COMMON PORTABLE GENERATION SCHEMA V2 (CROSS-PROVIDER INTERSECTION)
# ==============================================================================

TRANSFORMATION_ALGORITHM_ID_V2 = (
    "W06_PORTABLE_GENERATION_SCHEMA_V1_TO_V2_DETERMINISTIC_PROJECTION"
)

UNSUPPORTED_PORTABLE_NUMERIC_KEYWORDS = (
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "multipleOf",
)
UNSUPPORTED_PORTABLE_STRING_KEYWORDS = (
    "minLength",
    "maxLength",
)
UNSUPPORTED_PORTABLE_ARRAY_KEYWORDS = (
    "maxItems",
    "uniqueItems",
    "contains",
    "minContains",
    "maxContains",
)
ALL_UNCONDITIONAL_STRIPPED_V2_KEYWORDS = frozenset(
    UNSUPPORTED_PORTABLE_NUMERIC_KEYWORDS
    + UNSUPPORTED_PORTABLE_STRING_KEYWORDS
    + UNSUPPORTED_PORTABLE_ARRAY_KEYWORDS
)
SUPPORTED_ANTHROPIC_MIN_ITEMS_VALUES = (0, 1)

OFFICIAL_DOCUMENTATION_EVIDENCE_V2: Dict[str, Any] = {
    "access_date": "2026-10-17",
    "anthropic": {
        "source_url": "https://platform.claude.com/docs/en/build-with-claude/structured-outputs",
        "section": "JSON Schema limitations",
        "supported_constructs": [
            "object",
            "properties",
            "required",
            "additionalProperties=false",
            "string",
            "integer",
            "number",
            "boolean",
            "null",
            "enum (primitive values)",
            "const",
            "anyOf",
            "$ref / $defs (internal non-recursive)",
            "minItems (only values 0 or 1)",
        ],
        "unsupported_raw_schema_constructs": [
            "minimum",
            "maximum",
            "exclusiveMinimum",
            "exclusiveMaximum",
            "multipleOf",
            "minLength",
            "maxLength",
            "minItems (> 1)",
            "maxItems",
            "uniqueItems",
            "contains",
            "minContains",
            "maxContains",
            "external $ref",
            "recursive schemas",
            "additionalProperties != false",
        ],
        "sdk_note": (
            "Anthropic SDK transform_schema() automatically strips unsupported constraints and appends "
            "them to description text when given a Pydantic model, whereas passing a raw dict to "
            "output_config.format.schema sends the schema directly and returns HTTP 400 on unsupported keywords."
        ),
    },
    "openai": {
        "source_url": "https://platform.openai.com/docs/guides/structured-outputs",
        "section": "Supported schemas (Strict mode)",
        "compatibility_notes": (
            "Requires additionalProperties=false and all properties listed in required on every object node; "
            "accepts standard JSON Schema types, enums, anyOf, internal $defs/$ref, and description strings."
        ),
    },
    "google": {
        "source_url": "https://ai.google.dev/gemini-api/docs/structured-output",
        "section": "Structured Outputs / JSON Schema",
        "compatibility_notes": (
            "Accepts standard JSON Schema via response_json_schema with response_mime_type='application/json', "
            "including object properties, required, additionalProperties=false, enums, anyOf, $defs/$ref, and descriptions."
        ),
    },
}


def _official_limitation_for_keyword(keyword: str) -> str:
    if keyword in UNSUPPORTED_PORTABLE_NUMERIC_KEYWORDS:
        return (
            "Anthropic Structured Outputs JSON Schema limitations: "
            "Numerical constraints (minimum, maximum, exclusiveMinimum, exclusiveMaximum, multipleOf) "
            "are not supported in raw output_config.format.schema."
        )
    if keyword in UNSUPPORTED_PORTABLE_STRING_KEYWORDS:
        return (
            "Anthropic Structured Outputs JSON Schema limitations: "
            "String length constraints (minLength, maxLength) "
            "are not supported in raw output_config.format.schema."
        )
    return (
        "Anthropic Structured Outputs JSON Schema limitations: "
        "Array constraints beyond minItems in {0, 1} "
        "are not supported in raw output_config.format.schema."
    )


def format_semantic_constraint_annotation(removed_kv: Dict[str, Any]) -> str:
    """Format removed constraint key-values into a deterministic, sorted semantic hint string."""
    if not removed_kv:
        return ""
    parts = [f"{k}={removed_kv[k]}" for k in sorted(removed_kv.keys())]
    return f"[SEMANTIC_CONSTRAINTS: {'; '.join(parts)}]"


def apply_deterministic_constraint_description(
    existing_description: str | None,
    removed_kv: Dict[str, Any],
) -> str | None:
    """Deterministically append or create a description containing the semantic constraint hint."""
    if not removed_kv:
        return existing_description
    hint = format_semantic_constraint_annotation(removed_kv)
    if isinstance(existing_description, str) and existing_description.strip():
        return f"{existing_description} {hint}"
    return hint


def _is_unsupported_portable_keyword(key: str, val: Any) -> bool:
    if key in ALL_UNCONDITIONAL_STRIPPED_V2_KEYWORDS:
        return True
    if key == "minItems":
        if (
            not isinstance(val, int)
            or isinstance(val, bool)
            or val not in SUPPORTED_ANTHROPIC_MIN_ITEMS_VALUES
        ):
            return True
    return False


def _project_portable_generation_schema_v2_node(
    node: Any,
    path: str,
    removed_records: List[Dict[str, Any]],
) -> Any:
    """Recursively project strict V1 generation schema into portable V2 generation schema."""
    if isinstance(node, dict):
        removed_on_node: Dict[str, Any] = {}
        for k in sorted(node.keys()):
            v = node[k]
            if _is_unsupported_portable_keyword(k, v):
                removed_on_node[k] = v
                removed_records.append(
                    {
                        "schema_path": path,
                        "keyword": k,
                        "original_value": copy.deepcopy(v),
                        "reason": (
                            "Raw JSON Schema constraint keyword is not supported across all three candidate "
                            "providers' native structured-output decoders (rejected by Anthropic HTTP 400)."
                        ),
                        "official_provider_limitation": _official_limitation_for_keyword(k),
                        "semantic_enforcement_retained_by": "BenchmarkPlanResponse.model_validate",
                    }
                )

        out: Dict[str, Any] = {}
        for k, v in node.items():
            if k in removed_on_node:
                continue
            if k == "properties" and isinstance(v, dict):
                out[k] = {
                    prop_name: _project_portable_generation_schema_v2_node(
                        prop_val,
                        f"{path}.properties.{prop_name}",
                        removed_records,
                    )
                    for prop_name, prop_val in v.items()
                }
            elif k == "$defs" and isinstance(v, dict):
                out[k] = {
                    def_name: _project_portable_generation_schema_v2_node(
                        def_val,
                        f"{path}.$defs.{def_name}",
                        removed_records,
                    )
                    for def_name, def_val in v.items()
                }
            elif k == "items":
                out[k] = _project_portable_generation_schema_v2_node(
                    v,
                    f"{path}.items",
                    removed_records,
                )
            elif k == "anyOf" and isinstance(v, list):
                out[k] = [
                    _project_portable_generation_schema_v2_node(
                        item,
                        f"{path}.anyOf[{idx}]",
                        removed_records,
                    )
                    for idx, item in enumerate(v)
                ]
            else:
                out[k] = copy.deepcopy(v)

        if removed_on_node:
            new_desc = apply_deterministic_constraint_description(
                out.get("description"),
                removed_on_node,
            )
            if new_desc is not None:
                out["description"] = new_desc

        return out

    if isinstance(node, list):
        return [
            _project_portable_generation_schema_v2_node(item, f"{path}[{idx}]", removed_records)
            for idx, item in enumerate(node)
        ]
    return copy.deepcopy(node)


def build_common_portable_generation_benchmark_plan_json_schema_v2() -> Dict[str, Any]:
    """Build the common portable structured-output generation schema V2 from strict V1."""
    v1_schema = build_common_generation_benchmark_plan_json_schema_v1()
    removed_records: List[Dict[str, Any]] = []
    return _project_portable_generation_schema_v2_node(v1_schema, "$", removed_records)


def compute_common_portable_generation_schema_sha256_v2() -> str:
    """Compute canonical SHA256 of the common portable structured-output generation schema V2."""
    return sha256_bytes(
        canonical_json_bytes(build_common_portable_generation_benchmark_plan_json_schema_v2())
    )


def verify_portable_generation_schema_v2_projection(
    v1_schema: Dict[str, Any] | None = None,
    v2_schema: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Automated structural-diff and safety guard proving V1 -> V2 changes ONLY:
    1. verified unsupported structured-output keywords
    2. deterministic description annotations recording removed semantics.

    Raises ValueError on any unapproved mutation.
    """
    s_v1 = (
        v1_schema
        if v1_schema is not None
        else build_common_generation_benchmark_plan_json_schema_v1()
    )
    s_v2 = (
        v2_schema
        if v2_schema is not None
        else build_common_portable_generation_benchmark_plan_json_schema_v2()
    )

    removed_constraint_paths: List[Dict[str, Any]] = []
    keyword_counts: Dict[str, int] = {}

    def _compare_v1_v2(n1: Any, n2: Any, path: str) -> None:
        if type(n1) is not type(n2):
            raise ValueError(f"V1->V2 node type mismatch at {path}: {type(n1)} vs {type(n2)}")

        if isinstance(n1, dict):
            expected_removed_on_node: Dict[str, Any] = {}
            for k in sorted(n1.keys()):
                if _is_unsupported_portable_keyword(k, n1[k]):
                    if k in n2:
                        raise ValueError(
                            f"V2 schema retained unsupported portable keyword '{k}' at {path}"
                        )
                    expected_removed_on_node[k] = n1[k]
                    keyword_counts[k] = keyword_counts.get(k, 0) + 1
                    removed_constraint_paths.append(
                        {
                            "schema_path": path,
                            "keyword": k,
                            "original_value": copy.deepcopy(n1[k]),
                            "reason": (
                                "Raw JSON Schema constraint keyword is not supported across all three candidate "
                                "providers' native structured-output decoders (rejected by Anthropic HTTP 400)."
                            ),
                            "official_provider_limitation": _official_limitation_for_keyword(k),
                            "semantic_enforcement_retained_by": "BenchmarkPlanResponse.model_validate",
                        }
                    )

            # Check for any unsupported keyword introduced in n2
            for k, v in n2.items():
                if _is_unsupported_portable_keyword(k, v):
                    raise ValueError(
                        f"V2 schema introduced unsupported portable keyword '{k}' at {path}"
                    )

            # Verify key sets (excluding removed unsupported keys and deterministic description)
            n1_remaining_keys = set(n1.keys()) - set(expected_removed_on_node.keys())
            n2_keys = set(n2.keys())
            if expected_removed_on_node:
                expected_n2_keys = n1_remaining_keys | {"description"}
                if n2_keys != expected_n2_keys:
                    raise ValueError(
                        f"Unapproved key set change at {path}: expected {sorted(expected_n2_keys)}, "
                        f"got {sorted(n2_keys)}"
                    )
                expected_desc = apply_deterministic_constraint_description(
                    n1.get("description"),
                    expected_removed_on_node,
                )
                if n2.get("description") != expected_desc:
                    raise ValueError(
                        f"Non-deterministic or invalid description annotation at {path}: "
                        f"expected {expected_desc!r}, got {n2.get('description')!r}"
                    )
            else:
                if n2_keys != n1_remaining_keys:
                    raise ValueError(
                        f"Unapproved key set change on unstripped node at {path}: "
                        f"V1={sorted(n1_remaining_keys)} vs V2={sorted(n2_keys)}"
                    )
                if "description" in n1 and n1["description"] != n2.get("description"):
                    raise ValueError(
                        f"Unrelated description modified at {path}: "
                        f"{n1['description']!r} -> {n2.get('description')!r}"
                    )

            # Verify protected structural & semantic keys on this node
            for pk in ("type", "$ref", "enum", "const", "title", "minItems", "additionalProperties", "required"):
                if pk in n1 or pk in n2:
                    if n1.get(pk) != n2.get(pk):
                        raise ValueError(
                            f"Protected V1->V2 key '{pk}' altered at {path}: "
                            f"{n1.get(pk)!r} -> {n2.get(pk)!r}"
                        )

            if "anyOf" in n1:
                a1 = n1["anyOf"]
                a2 = n2.get("anyOf", [])
                if not isinstance(a1, list) or not isinstance(a2, list) or len(a1) != len(a2):
                    raise ValueError(f"anyOf structure altered at {path}")
                for idx, (sub1, sub2) in enumerate(zip(a1, a2)):
                    _compare_v1_v2(sub1, sub2, f"{path}.anyOf[{idx}]")

            if "properties" in n1:
                p1 = n1["properties"]
                p2 = n2.get("properties")
                if not isinstance(p1, dict) or not isinstance(p2, dict):
                    raise ValueError(f"Invalid properties container at {path}")
                if set(p1.keys()) != set(p2.keys()):
                    raise ValueError(
                        f"Property names changed at {path}: {sorted(p1.keys())} vs {sorted(p2.keys())}"
                    )
                if n2.get("additionalProperties") is not False:
                    raise ValueError(f"additionalProperties=False lost at {path}")
                if n2.get("required") != sorted(p1.keys()):
                    raise ValueError(f"required materialization altered at {path}")
                for prop_name in sorted(p1.keys()):
                    _compare_v1_v2(p1[prop_name], p2[prop_name], f"{path}.properties.{prop_name}")

            if "$defs" in n1:
                d1 = n1["$defs"]
                d2 = n2.get("$defs")
                if not isinstance(d1, dict) or not isinstance(d2, dict):
                    raise ValueError(f"Invalid $defs container at {path}")
                if set(d1.keys()) != set(d2.keys()):
                    raise ValueError(
                        f"$defs keys changed at {path}: {sorted(d1.keys())} vs {sorted(d2.keys())}"
                    )
                for def_name in sorted(d1.keys()):
                    _compare_v1_v2(d1[def_name], d2[def_name], f"{path}.$defs.{def_name}")

            if "items" in n1:
                _compare_v1_v2(n1["items"], n2["items"], f"{path}.items")

        elif isinstance(n1, list):
            if len(n1) != len(n2):
                raise ValueError(f"List length mismatch at {path}: {len(n1)} vs {len(n2)}")
            for idx, (i1, i2) in enumerate(zip(n1, n2)):
                _compare_v1_v2(i1, i2, f"{path}[{idx}]")
        else:
            if n1 != n2:
                raise ValueError(f"Scalar value changed at {path}: {n1!r} -> {n2!r}")

    _compare_v1_v2(s_v1, s_v2, "$")

    if schema_encodes_place_id_as_catalog_enum(s_v2):
        raise ValueError("V2 schema must never encode place_id as a catalog enum.")

    activity_kind_def = s_v2.get("$defs", {}).get("ActivityKind", {})
    if activity_kind_def.get("enum") != ["POI_VISIT", "TRANSIT_ONLY"]:
        raise ValueError(f"ActivityKind enum altered in V2: {activity_kind_def.get('enum')!r}")

    item_place_id = (
        s_v2.get("$defs", {})
        .get("BenchmarkItineraryItem", {})
        .get("properties", {})
        .get("place_id", {})
    )
    if item_place_id != {"anyOf": [{"type": "string"}, {"type": "null"}], "title": "Place Id"}:
        raise ValueError(f"place_id nullable schema altered in V2: {item_place_id!r}")

    sorted_keyword_counts = {k: keyword_counts[k] for k in sorted(keyword_counts.keys())}

    return {
        "whitelist_guard_passed": True,
        "transformation_algorithm_id": TRANSFORMATION_ALGORITHM_ID_V2,
        "semantic_schema_sha256": SEMANTIC_SCHEMA_SHA256,
        "generation_schema_v1_sha256": sha256_bytes(canonical_json_bytes(s_v1)),
        "portable_generation_schema_v2_sha256": sha256_bytes(canonical_json_bytes(s_v2)),
        "removed_constraint_keyword_counts": sorted_keyword_counts,
        "removed_constraint_keywords": sorted(sorted_keyword_counts.keys()),
        "removed_constraint_total_count": len(removed_constraint_paths),
        "removed_constraint_paths": removed_constraint_paths,
        "preserved_constraint_keywords": [
            "$defs",
            "$ref",
            "additionalProperties",
            "anyOf",
            "enum",
            "minItems",
            "properties",
            "required",
            "type",
        ],
        "place_id_catalog_enum_present": False,
        "activity_kind_enum_preserved": True,
        "required_materialization_preserved": True,
        "additional_properties_false_preserved": True,
    }


def scan_anthropic_portable_schema_compatibility(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Offline static scanner that recursively detects unsupported Anthropic raw-schema constructs (Section 14)."""
    violations: List[Dict[str, Any]] = []
    supported_min_items_paths: List[str] = []
    external_ref_count = 0
    recursive_ref_count = 0
    open_additional_props_count = 0

    defs = schema.get("$defs", {}) if isinstance(schema, dict) else {}

    def _contains_ref_cycle(node: Any, visited_defs: set[str]) -> bool:
        if isinstance(node, dict):
            if "$ref" in node and isinstance(node["$ref"], str) and node["$ref"].startswith("#/$defs/"):
                target = node["$ref"].split("#/$defs/", 1)[1]
                if target in visited_defs:
                    return True
                if isinstance(defs, dict) and target in defs:
                    if _contains_ref_cycle(defs[target], visited_defs | {target}):
                        return True
            for k, v in node.items():
                if k != "$defs" and _contains_ref_cycle(v, visited_defs):
                    return True
        elif isinstance(node, list):
            for item in node:
                if _contains_ref_cycle(item, visited_defs):
                    return True
        return False

    def _walk(node: Any, path: str) -> None:
        nonlocal external_ref_count, recursive_ref_count, open_additional_props_count
        if isinstance(node, dict):
            # 1. Check unsupported constraint keywords
            for k, v in node.items():
                if k in ALL_UNCONDITIONAL_STRIPPED_V2_KEYWORDS:
                    violations.append(
                        {
                            "schema_path": path,
                            "keyword": k,
                            "value": v,
                            "reason": f"Unsupported Anthropic raw-schema keyword: {k}",
                        }
                    )
                elif k == "minItems":
                    if (
                        isinstance(v, int)
                        and not isinstance(v, bool)
                        and v in SUPPORTED_ANTHROPIC_MIN_ITEMS_VALUES
                    ):
                        supported_min_items_paths.append(path)
                    else:
                        violations.append(
                            {
                                "schema_path": path,
                                "keyword": "minItems",
                                "value": v,
                                "reason": (
                                    f"Unsupported minItems value {v!r}; Anthropic supports only 0 or 1."
                                ),
                            }
                        )

            # 2. Check object additionalProperties == False
            if node.get("type") == "object" or "properties" in node:
                if node.get("additionalProperties") is not False:
                    open_additional_props_count += 1
                    violations.append(
                        {
                            "schema_path": path,
                            "keyword": "additionalProperties",
                            "value": node.get("additionalProperties"),
                            "reason": "Object schema must set additionalProperties=False.",
                        }
                    )

            # 3. Check $ref (external or recursive)
            if "$ref" in node:
                ref_val = node["$ref"]
                if not isinstance(ref_val, str) or not ref_val.startswith("#/$defs/"):
                    external_ref_count += 1
                    violations.append(
                        {
                            "schema_path": path,
                            "keyword": "$ref",
                            "value": ref_val,
                            "reason": "External or non-local $ref is not supported.",
                        }
                    )
                else:
                    def_name = ref_val.split("#/$defs/", 1)[1]
                    if not isinstance(defs, dict) or def_name not in defs:
                        external_ref_count += 1
                        violations.append(
                            {
                                "schema_path": path,
                                "keyword": "$ref",
                                "value": ref_val,
                                "reason": f"Unresolved internal $ref target: {def_name}",
                            }
                        )
                    elif _contains_ref_cycle(defs[def_name], {def_name}):
                        recursive_ref_count += 1
                        violations.append(
                            {
                                "schema_path": path,
                                "keyword": "$ref",
                                "value": ref_val,
                                "reason": f"Recursive $ref cycle detected for definition: {def_name}",
                            }
                        )

            for k, v in node.items():
                if k == "$defs" and isinstance(v, dict):
                    for def_name, def_node in v.items():
                        _walk(def_node, f"{path}.$defs.{def_name}")
                elif k == "properties" and isinstance(v, dict):
                    for prop_name, prop_node in v.items():
                        _walk(prop_node, f"{path}.properties.{prop_name}")
                elif k not in ("$defs", "properties"):
                    _walk(v, f"{path}.{k}")

        elif isinstance(node, list):
            for idx, item in enumerate(node):
                _walk(item, f"{path}[{idx}]")

    _walk(schema, "$")

    return {
        "unsupported_anthropic_keyword_count": len(violations),
        "violations": violations,
        "supported_min_items_paths": sorted(supported_min_items_paths),
        "external_ref_count": external_ref_count,
        "recursive_ref_count": recursive_ref_count,
        "open_additional_properties_count": open_additional_props_count,
        "status": (
            "OFFLINE_PORTABILITY_CHECK_PASS"
            if len(violations) == 0
            else "OFFLINE_PORTABILITY_CHECK_FAIL"
        ),
    }


def check_cross_provider_v2_static_compatibility(
    schema: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Static documentation-based compatibility check across Google (C1), OpenAI (C2), and Anthropic (C3)."""
    target_schema = (
        schema
        if schema is not None
        else COMMON_PORTABLE_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA_V2
    )
    anthropic_scan = scan_anthropic_portable_schema_compatibility(target_schema)

    # OpenAI strict mode static checks: every object node has additionalProperties=False and all properties required
    openai_violations: List[str] = []
    google_violations: List[str] = []

    def _walk_common(node: Any, path: str) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" or "properties" in node:
                props = node.get("properties", {})
                if not isinstance(props, dict):
                    openai_violations.append(f"Invalid properties at {path}")
                    google_violations.append(f"Invalid properties at {path}")
                else:
                    if node.get("additionalProperties") is not False:
                        openai_violations.append(f"Missing additionalProperties=False at {path}")
                        google_violations.append(f"Missing additionalProperties=False at {path}")
                    if node.get("required") != sorted(props.keys()):
                        openai_violations.append(
                            f"OpenAI strict mode requires all properties in required at {path}"
                        )
            for k, v in node.items():
                _walk_common(v, f"{path}.{k}")
        elif isinstance(node, list):
            for idx, item in enumerate(node):
                _walk_common(item, f"{path}[{idx}]")

    _walk_common(target_schema, "$")

    if anthropic_scan["external_ref_count"] > 0 or anthropic_scan["recursive_ref_count"] > 0:
        openai_violations.append("External or recursive $ref detected")
        google_violations.append("External or recursive $ref detected")

    google_ok = len(google_violations) == 0
    openai_ok = len(openai_violations) == 0
    anthropic_ok = anthropic_scan["unsupported_anthropic_keyword_count"] == 0

    return {
        "portable_generation_schema_v2_sha256": sha256_bytes(canonical_json_bytes(target_schema)),
        "GOOGLE_V2_STATIC_COMPATIBILITY": "PASS" if google_ok else "NOT_READY",
        "OPENAI_V2_STATIC_COMPATIBILITY": "PASS" if openai_ok else "NOT_READY",
        "ANTHROPIC_V2_STATIC_COMPATIBILITY": "PASS" if anthropic_ok else "NOT_READY",
        "google_violations": google_violations,
        "openai_violations": openai_violations,
        "anthropic_portability_scan": anthropic_scan,
        "status": (
            "OFFLINE_PORTABILITY_CHECK_PASS"
            if (google_ok and openai_ok and anthropic_ok)
            else "NOT_READY"
        ),
    }


COMMON_PORTABLE_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA_V2: Dict[str, Any] = (
    build_common_portable_generation_benchmark_plan_json_schema_v2()
)
COMMON_PORTABLE_GENERATION_SCHEMA_SHA256_V2: str = (
    compute_common_portable_generation_schema_sha256_v2()
)


def build_google_structured_output_wiring(
    schema: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Build Google (C1) technical structured-output wiring for GenerateContentConfig (V1 default)."""
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
    """Build OpenAI (C2) technical structured-output wiring for chat.completions.create (V1 default)."""
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
    """Build Anthropic (C3) technical structured-output wiring for messages.create (Part E, V1 default).

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


def build_google_structured_output_wiring_v2(
    schema: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Build Google (C1) technical structured-output wiring using Portable Generation Schema V2."""
    target_schema = copy.deepcopy(
        schema or COMMON_PORTABLE_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA_V2
    )
    v2_sha = sha256_bytes(canonical_json_bytes(target_schema))
    return {
        "response_mime_type": "application/json",
        "response_json_schema": target_schema,
        "semantic_schema_sha256": SEMANTIC_SCHEMA_SHA256,
        "generation_schema_v1_sha256": COMMON_GENERATION_SCHEMA_SHA256_V1,
        "portable_generation_schema_v2_sha256": v2_sha,
        "common_generation_schema_sha256": v2_sha,
        "common_schema_sha256": v2_sha,
    }


def build_openai_structured_output_wiring_v2(
    schema: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Build OpenAI (C2) technical structured-output wiring using Portable Generation Schema V2."""
    target_schema = copy.deepcopy(
        schema or COMMON_PORTABLE_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA_V2
    )
    v2_sha = sha256_bytes(canonical_json_bytes(target_schema))
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
        "generation_schema_v1_sha256": COMMON_GENERATION_SCHEMA_SHA256_V1,
        "portable_generation_schema_v2_sha256": v2_sha,
        "common_generation_schema_sha256": v2_sha,
        "common_schema_sha256": v2_sha,
    }


def build_anthropic_structured_output_wiring_v2(
    schema: Dict[str, Any] | None = None,
    *,
    effort: str = FROZEN_CLAUDE_EFFORT,
) -> Dict[str, Any]:
    """Build Anthropic (C3) technical structured-output wiring using Portable Generation Schema V2."""
    target_schema = copy.deepcopy(
        schema or COMMON_PORTABLE_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA_V2
    )
    v2_sha = sha256_bytes(canonical_json_bytes(target_schema))
    return {
        "output_config": {
            "effort": effort,
            "format": {
                "type": "json_schema",
                "schema": target_schema,
            },
        },
        "semantic_schema_sha256": SEMANTIC_SCHEMA_SHA256,
        "generation_schema_v1_sha256": COMMON_GENERATION_SCHEMA_SHA256_V1,
        "portable_generation_schema_v2_sha256": v2_sha,
        "common_generation_schema_sha256": v2_sha,
        "common_schema_sha256": v2_sha,
    }


FROZEN_01C_BASE_DEVELOP_SHA = "8b88ec05cec2697fc26049bad140d4117028f69e"
FROZEN_01B_LIVE_PLAN_SHA256 = "3c59a1fba4faa7463c2a068a230ee492437713a78337b2e904980cf13c58f712"


def build_portable_schema_v2_manifest(
    *,
    base_develop_sha: str = FROZEN_01C_BASE_DEVELOP_SHA,
) -> Dict[str, Any]:
    """Build the V2 Transformation Manifest artifact (Section 9)."""
    diff = verify_portable_generation_schema_v2_projection()
    compat = check_cross_provider_v2_static_compatibility()
    return {
        "artifact_id": "W06-MODEL-PREFLIGHT-PORTABLE-SCHEMA-V2-MANIFEST",
        "version": "1.0.0",
        "base_develop_sha": base_develop_sha,
        "semantic_schema_sha256": SEMANTIC_SCHEMA_SHA256,
        "generation_schema_v1_sha256": COMMON_GENERATION_SCHEMA_SHA256_V1,
        "portable_generation_schema_v2_sha256": COMMON_PORTABLE_GENERATION_SCHEMA_SHA256_V2,
        "transformation_algorithm_id": TRANSFORMATION_ALGORITHM_ID_V2,
        "official_documentation_evidence": copy.deepcopy(OFFICIAL_DOCUMENTATION_EVIDENCE_V2),
        "removed_constraint_keyword_counts": diff["removed_constraint_keyword_counts"],
        "removed_constraint_keywords": diff["removed_constraint_keywords"],
        "removed_constraint_total_count": diff["removed_constraint_total_count"],
        "removed_constraint_paths": diff["removed_constraint_paths"],
        "preserved_constraint_keywords": diff["preserved_constraint_keywords"],
        "place_id_catalog_enum_present": False,
        "activity_kind_enum_preserved": True,
        "required_materialization_preserved": True,
        "additional_properties_false_preserved": True,
        "semantic_validator": "BenchmarkPlanResponse.model_validate",
        "semantic_schema_modified": False,
        "generation_schema_v1_modified": False,
        "provider_specific_schema": False,
        "cross_provider_static_compatibility": {
            "GOOGLE_V2_STATIC_COMPATIBILITY": compat["GOOGLE_V2_STATIC_COMPATIBILITY"],
            "OPENAI_V2_STATIC_COMPATIBILITY": compat["OPENAI_V2_STATIC_COMPATIBILITY"],
            "ANTHROPIC_V2_STATIC_COMPATIBILITY": compat["ANTHROPIC_V2_STATIC_COMPATIBILITY"],
            "unsupported_anthropic_keyword_count": compat["anthropic_portability_scan"][
                "unsupported_anthropic_keyword_count"
            ],
            "status": compat["status"],
        },
        "portable_generation_schema_v2": copy.deepcopy(
            COMMON_PORTABLE_GENERATION_BENCHMARK_PLAN_JSON_SCHEMA_V2
        ),
    }


def build_schema_portability_amendment_v1(
    *,
    base_develop_sha: str = FROZEN_01C_BASE_DEVELOP_SHA,
) -> Dict[str, Any]:
    """Build the Formal Schema Portability Amendment artifact (Section 10)."""
    return {
        "amendment_id": "W06-MODEL-PREFLIGHT-SCHEMA-PORTABILITY-AMENDMENT-01",
        "version": "1.0.0",
        "base_develop_sha": base_develop_sha,
        "trigger": "01B_C3_RAW_STRUCTURED_OUTPUT_SCHEMA_REJECTION",
        "trigger_candidate": "C3",
        "trigger_failure": "FAILED_STRUCTURED_OUTPUT_COMPATIBILITY",
        "trigger_http_status": 400,
        "trigger_provider_error": (
            "output_config.format.schema: For 'integer' type, property 'minimum' is not supported"
        ),
        "historical_01b_preserved": True,
        "historical_01b_plan_sha256": FROZEN_01B_LIVE_PLAN_SHA256,
        "historical_01b_candidate_outcomes": {
            "C1": "PASSED_TECHNICAL_PREFLIGHT_SCHEMA_V1",
            "C2": "PASSED_TECHNICAL_PREFLIGHT_SCHEMA_V1",
            "C3": "FAILED_TECHNICAL_PREFLIGHT_SCHEMA_V1",
        },
        "dev_tune_started": False,
        "dev_select_started": False,
        "winner_selected": False,
        "final_100_used": False,
        "performance_evidence_used_to_design_amendment": False,
        "candidate_list_changed": False,
        "candidate_substitution": False,
        "semantic_schema_changed": False,
        "semantic_schema_sha256": SEMANTIC_SCHEMA_SHA256,
        "common_generation_schema_v1_changed": False,
        "generation_schema_v1_sha256": COMMON_GENERATION_SCHEMA_SHA256_V1,
        "portable_generation_schema_v2_created": True,
        "portable_generation_schema_v2_sha256": COMMON_PORTABLE_GENERATION_SCHEMA_SHA256_V2,
        "v2_applies_identically_to": ["C1", "C2", "C3"],
        "future_live_revalidation_required_for_all_candidates": True,
        "reuse_v1_pass_without_v2_revalidation": False,
        "max_future_01d_calls": 3,
        "future_calls_per_candidate": 1,
        "retry_future_01d": 0,
        "current_candidate_technical_eligibility_for_dev": {
            "C1": "PENDING_SCHEMA_V2_LIVE_REVALIDATION",
            "C2": "PENDING_SCHEMA_V2_LIVE_REVALIDATION",
            "C3": "PENDING_SCHEMA_V2_LIVE_REVALIDATION",
        },
        "DEV_MODEL_SELECTION_ALLOWED": False,
        "NEXT_GATE": "W06-MODEL-PREFLIGHT-01D-PORTABLE-SCHEMA-LIVE-REVALIDATION",
    }


def build_model_preflight_01c_receipt_v1(
    *,
    base_develop_sha: str = FROZEN_01C_BASE_DEVELOP_SHA,
) -> Dict[str, Any]:
    """Build the Phase 01C Offline Portable Schema Amendment Receipt (Section 23)."""
    diff = verify_portable_generation_schema_v2_projection()
    compat = check_cross_provider_v2_static_compatibility()
    return {
        "task_id": "W06-MODEL-PREFLIGHT-01C-PORTABLE-SCHEMA-AMENDMENT-OFFLINE",
        "version": "1.0.0",
        "base_develop_sha": base_develop_sha,
        "phase": "OFFLINE_FORMAL_AMENDMENT",
        "live_provider_calls": 0,
        "provider_cost_usd": 0,
        "semantic_schema_sha256": SEMANTIC_SCHEMA_SHA256,
        "generation_schema_v1_sha256": COMMON_GENERATION_SCHEMA_SHA256_V1,
        "portable_generation_schema_v2_sha256": COMMON_PORTABLE_GENERATION_SCHEMA_SHA256_V2,
        "v1_unchanged": True,
        "historical_01b_preserved": True,
        "historical_01b_plan_sha256": FROZEN_01B_LIVE_PLAN_SHA256,
        "removed_constraint_total_count": diff["removed_constraint_total_count"],
        "removed_constraint_keywords": diff["removed_constraint_keywords"],
        "removed_constraint_keyword_counts": diff["removed_constraint_keyword_counts"],
        "anthropic_unsupported_keyword_count_v2": compat["anthropic_portability_scan"][
            "unsupported_anthropic_keyword_count"
        ],
        "GOOGLE_V2_STATIC_COMPATIBILITY": compat["GOOGLE_V2_STATIC_COMPATIBILITY"],
        "OPENAI_V2_STATIC_COMPATIBILITY": compat["OPENAI_V2_STATIC_COMPATIBILITY"],
        "ANTHROPIC_V2_STATIC_COMPATIBILITY": compat["ANTHROPIC_V2_STATIC_COMPATIBILITY"],
        "portability_check_status": compat["status"],
        "place_id_catalog_enum_present": False,
        "activity_kind_enum_preserved": True,
        "C1_historical_v1_status": "PASS",
        "C2_historical_v1_status": "PASS",
        "C3_historical_v1_status": "FAIL",
        "C1_current_status": "PENDING_SCHEMA_V2_LIVE_REVALIDATION",
        "C2_current_status": "PENDING_SCHEMA_V2_LIVE_REVALIDATION",
        "C3_current_status": "PENDING_SCHEMA_V2_LIVE_REVALIDATION",
        "dev_tune_started": False,
        "dev_select_started": False,
        "winner_selected": False,
        "final_100_used": False,
        "DEV_MODEL_SELECTION_ALLOWED": False,
        "next_task": "W06-MODEL-PREFLIGHT-01D-PORTABLE-SCHEMA-LIVE-REVALIDATION",
    }
