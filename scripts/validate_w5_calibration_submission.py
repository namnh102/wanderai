"""Operational builder and submission validator for W5 human calibration.

Prepares and validates blinded, reproducible three-judge (J1, J2, J3) calibration
packages and submissions for the W5 calibration phase (CAL-HN-01, CAL-DN-01, CAL-HL-01;
45 items total).

Scientific boundaries enforced:
- Calibration is CALIBRATION_ONLY and strictly disjoint from the 30 primary scenarios
  and 474 primary candidate pool records.
- Enforces strict immutability of all read-only context fields in both JSON and CSV
  submissions (only 'label' and 'judge_note' are mutable).
- Does NOT populate or simulate human relevance labels.
- Does NOT aggregate judges, calculate final reliability, create HUMAN-GT,
  adjudicate, or compute recommender metrics.
- Does NOT mutate the canonical calibration source (w5_calibration_v1.json).
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
CANONICAL_CALIBRATION_PATH = (
    REPO_ROOT / "data" / "evaluation" / "reca_w5" / "annotation" / "w5_calibration_v1.json"
)
CALIBRATION_OPS_DIR = REPO_ROOT / "data" / "evaluation" / "reca_w5" / "calibration_ops"

CALIBRATION_VERSION = "W5-CALIBRATION-V1"
RUBRIC_VERSION = "W5-RUBRIC-V1"
POOL_VERSION = "W5-POOL-V1"
PRESENTATION_VERSION = "W5-CAL-OPS-V1"
SUBMISSION_CONTRACT_VERSION = "W5-CAL-SUBMISSION-CONTRACT-V1"
SESSION_LOG_TEMPLATE_VERSION = "W5-CAL-SESSION-LOG-TEMPLATE-V1"
ORDER_SEED_BASE = 20261013
ORDER_PURPOSE_TAG = "calibration-presentation"

ALLOWED_JUDGES = ("J1", "J2", "J3")
EXPECTED_SCENARIO_IDS = ("CAL-HN-01", "CAL-DN-01", "CAL-HL-01")
EXPECTED_ITEMS_PER_SCENARIO = 15
EXPECTED_TOTAL_ITEMS = 45
ALLOWED_ORDINAL_LABELS = (0, 1, 2)
ALLOWED_MISSING_CODE = "NA"
EDITABLE_ITEM_FIELDS = ("label", "judge_note")

# Forbidden fields that must never appear in judge-visible calibration packages or submissions
FORBIDDEN_LEAKAGE_KEYS = frozenset(
    {
        "model",
        "model_id",
        "model_identity",
        "strategy",
        "rank",
        "score",
        "confidence_score",
        "similarity_score",
        "baseline_membership",
        "a2_membership",
        "source_systems",
        "is_control",
        "control_flag",
        "canonical_interest_vector",
        "canonical_active_interests",
        "matched_interests",
        "metadata_sufficiency",
        "sufficiency_status",
        "sufficiency_reason",
        "duplicate_group",
        "duplicate_equivalence_group",
        "duplicate_group_status",
        "recommendation_explanation",
        "tier_1",
        "tier_2",
        "legacy_category",
    }
)

CSV_READ_ONLY_COLUMNS = (
    "judge_id",
    "calibration_version",
    "rubric_version",
    "presentation_version",
    "scenario_id",
    "presentation_index",
    "global_presentation_index",
    "calibration_item_id",
    "judge_item_id",
    "place_id",
    "destination",
    "declared_interests",
    "name",
    "category",
    "address",
    "latitude",
    "longitude",
    "opening_hours",
    "osm_source_id",
    "osm_factual_tags_json",
)
CSV_EDITABLE_COLUMNS = ("label", "judge_note")
CSV_ALL_COLUMNS = CSV_READ_ONLY_COLUMNS + CSV_EDITABLE_COLUMNS

REQUIRED_ATTESTATION_STATEMENTS = [
    "I completed calibration independently.",
    "I did not view another judge's labels.",
    "I did not see model identity, ranking, score, strategy, or control status.",
    "I did not use an LLM to generate relevance labels.",
    "I used only the factual evidence provided in the calibration package.",
    "I used NA when the provided evidence was insufficient.",
]


def _strict_equal(a: Any, b: Any) -> bool:
    """Recursively compare two JSON values with strict type equality."""
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        if set(a.keys()) != set(b.keys()):
            return False
        return all(_strict_equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        if len(a) != len(b):
            return False
        return all(_strict_equal(x, y) for x, y in zip(a, b, strict=True))
    return bool(a == b)


def compute_scenario_seed_basis(scenario_id: str, judge_id: str) -> str:
    """Return the canonical seed basis string for a scenario and judge."""
    return f"{ORDER_SEED_BASE}:{scenario_id}:{judge_id}:{ORDER_PURPOSE_TAG}"


def compute_item_order_key(
    scenario_id: str, judge_id: str, judge_item_id: str
) -> tuple[str, str]:
    """Compute SHA256-derived deterministic ordering key for a calibration item.

    Uses SHA256 of '20261013:<scenario_id>:<judge_id>:calibration-presentation:<judge_item_id>'.
    Never uses Python hash() or model information.
    """
    basis = f"{compute_scenario_seed_basis(scenario_id, judge_id)}:{judge_item_id}"
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()
    return (digest, judge_item_id)


def load_canonical_calibration(
    path: Path = CANONICAL_CALIBRATION_PATH,
) -> dict[str, Any]:
    """Load the frozen canonical calibration artifact."""
    with path.open("r", encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
    return data


def build_judge_calibration_package(
    canonical_doc: dict[str, Any], judge_id: str
) -> dict[str, Any]:
    """Build a deterministic, blinded judge-specific calibration presentation package."""
    if judge_id not in ALLOWED_JUDGES:
        raise ValueError(f"Unsupported judge_id {judge_id!r}; expected one of {ALLOWED_JUDGES}")

    scenarios_out: list[dict[str, Any]] = []
    global_idx = 0

    for sc in canonical_doc.get("scenarios", []):
        sc_id = sc["scenario_id"]
        destination = sc["destination"]
        declared_interests = list(sc["declared_interests"])

        raw_items = list(sc.get("items", []))
        ordered_items = sorted(
            raw_items,
            key=lambda it: compute_item_order_key(sc_id, judge_id, it["judge_item_id"]),
        )

        presented_items: list[dict[str, Any]] = []
        for p_idx, item in enumerate(ordered_items, start=1):
            global_idx += 1
            factual_ctx = copy.deepcopy(item.get("factual_context", {}))
            for k in list(factual_ctx.keys()):
                if k in FORBIDDEN_LEAKAGE_KEYS:
                    factual_ctx.pop(k, None)

            presented_items.append(
                {
                    "judge_id": judge_id,
                    "calibration_version": CALIBRATION_VERSION,
                    "rubric_version": RUBRIC_VERSION,
                    "presentation_version": PRESENTATION_VERSION,
                    "scenario_id": sc_id,
                    "presentation_index": p_idx,
                    "global_presentation_index": global_idx,
                    "calibration_item_id": item["judge_item_id"],
                    "judge_item_id": item["judge_item_id"],
                    "place_id": item["place_id"],
                    "destination": destination,
                    "declared_interests": declared_interests,
                    "name": item["name"],
                    "category": item["category"],
                    "factual_context": factual_ctx,
                    "label": None,
                    "judge_note": None,
                }
            )

        scenarios_out.append(
            {
                "scenario_id": sc_id,
                "destination": destination,
                "declared_interests": declared_interests,
                "track": "CALIBRATION_ONLY",
                "excluded_from_final_metrics": True,
                "order_seed_basis": compute_scenario_seed_basis(sc_id, judge_id),
                "item_count": len(presented_items),
                "items": presented_items,
            }
        )

    return {
        "judge_id": judge_id,
        "calibration_version": CALIBRATION_VERSION,
        "rubric_version": RUBRIC_VERSION,
        "pool_version": POOL_VERSION,
        "presentation_version": PRESENTATION_VERSION,
        "base_seed": ORDER_SEED_BASE,
        "track": "CALIBRATION_ONLY",
        "excluded_from_final_metrics": True,
        "scenario_count": len(scenarios_out),
        "total_items": global_idx,
        "scenarios": scenarios_out,
    }


def package_to_csv_rows(package_doc: dict[str, Any]) -> list[dict[str, str]]:
    """Convert a judge calibration package into ordered CSV row dictionaries."""
    rows: list[dict[str, str]] = []
    for sc in package_doc.get("scenarios", []):
        for item in sc.get("items", []):
            fctx = item.get("factual_context", {}) or {}
            osm_source = fctx.get("osm_source") or {}
            osm_source_id = ""
            if isinstance(osm_source, dict) and osm_source.get("source_id"):
                osm_source_id = f"{osm_source.get('source_name', 'osm')}:{osm_source['source_id']}"
            osm_tags = fctx.get("osm_factual_tags") or {}

            label_val = item.get("label")
            note_val = item.get("judge_note")

            row = {
                "judge_id": str(item["judge_id"]),
                "calibration_version": str(item["calibration_version"]),
                "rubric_version": str(item["rubric_version"]),
                "presentation_version": str(item["presentation_version"]),
                "scenario_id": str(item["scenario_id"]),
                "presentation_index": str(item["presentation_index"]),
                "global_presentation_index": str(item["global_presentation_index"]),
                "calibration_item_id": str(item["calibration_item_id"]),
                "judge_item_id": str(item["judge_item_id"]),
                "place_id": str(item["place_id"]),
                "destination": str(item["destination"]),
                "declared_interests": json.dumps(item["declared_interests"], ensure_ascii=False),
                "name": str(item["name"] or ""),
                "category": str(item["category"] or ""),
                "address": "" if fctx.get("address") is None else str(fctx.get("address")),
                "latitude": "" if fctx.get("latitude") is None else str(fctx.get("latitude")),
                "longitude": "" if fctx.get("longitude") is None else str(fctx.get("longitude")),
                "opening_hours": (
                    "" if fctx.get("opening_hours") is None else str(fctx.get("opening_hours"))
                ),
                "osm_source_id": osm_source_id,
                "osm_factual_tags_json": json.dumps(osm_tags, ensure_ascii=False, sort_keys=True),
                "label": "" if label_val is None else str(label_val),
                "judge_note": "" if note_val is None else str(note_val),
            }
            rows.append(row)
    return rows


def build_submission_contract_doc() -> dict[str, Any]:
    """Return the machine-readable calibration submission contract."""
    return {
        "contract_version": SUBMISSION_CONTRACT_VERSION,
        "calibration_version": CALIBRATION_VERSION,
        "rubric_version": RUBRIC_VERSION,
        "presentation_version": PRESENTATION_VERSION,
        "track": "CALIBRATION_ONLY",
        "excluded_from_final_metrics": True,
        "read_only_context_policy": "EXACT_MATCH_TO_FROZEN_PRESENTATION_PACKAGE",
        "editable_fields": list(EDITABLE_ITEM_FIELDS),
        "read_only_context_mutation": "REJECT",
        "enforcement_mechanism": "VALIDATOR_ENFORCED_IMMUTABILITY",
        "allowed_judges": list(ALLOWED_JUDGES),
        "expected_scenarios": list(EXPECTED_SCENARIO_IDS),
        "expected_items_per_scenario": EXPECTED_ITEMS_PER_SCENARIO,
        "expected_total_items": EXPECTED_TOTAL_ITEMS,
        "allowed_completed_labels": [0, 1, 2, "NA"],
        "label_semantics": {
            "0": "NOT_RELEVANT (ordinal numeric)",
            "1": "RELEVANT (ordinal numeric)",
            "2": "HIGHLY_RELEVANT (ordinal numeric)",
            "NA": "INSUFFICIENT_EVIDENCE (non-ordinal missing evidence code; NA != 0)",
        },
        "rejected_label_types_and_values": [
            "null / blank in completed submission",
            "boolean True or False",
            "float values (e.g. 0.0, 1.0, 2.0, 1.5)",
            "numeric strings (e.g. '0', '1', '2')",
            "lowercase or alternative NA strings (e.g. 'na', 'N/A', 'null', 'none')",
            "out-of-range integers (e.g. -1, 3)",
        ],
        "csv_column_layout": {
            "read_only_context_columns": list(CSV_READ_ONLY_COLUMNS),
            "editable_columns": list(CSV_EDITABLE_COLUMNS),
            "spreadsheet_formulas_allowed": False,
        },
        "required_top_level_fields": [
            "judge_id",
            "calibration_version",
            "rubric_version",
            "presentation_version",
            "scenarios",
        ],
        "required_item_fields": [
            "judge_id",
            "calibration_version",
            "rubric_version",
            "presentation_version",
            "scenario_id",
            "presentation_index",
            "global_presentation_index",
            "calibration_item_id",
            "judge_item_id",
            "place_id",
            "destination",
            "declared_interests",
            "name",
            "category",
            "factual_context",
            "label",
            "judge_note",
        ],
        "forbidden_leakage_fields": sorted(FORBIDDEN_LEAKAGE_KEYS),
    }


def build_session_log_template_doc() -> dict[str, Any]:
    """Return the calibration session log template with human-execution fields set to null."""
    return {
        "template_version": SESSION_LOG_TEMPLATE_VERSION,
        "judge_id": None,
        "rubric_version": RUBRIC_VERSION,
        "calibration_version": CALIBRATION_VERSION,
        "presentation_version": PRESENTATION_VERSION,
        "started_at": None,
        "completed_at": None,
        "submission_sha256": None,
        "independence_attestation": None,
        "required_attestation_statements": list(REQUIRED_ATTESTATION_STATEMENTS),
        "external_help_used": None,
        "issues_reported": None,
        "discussion_started": False,
    }


def write_calibration_ops_artifacts(output_dir: Path = CALIBRATION_OPS_DIR) -> None:
    """Generate and write all W5-CAL-OPS-PREP-01 artifacts to disk."""
    output_dir.mkdir(parents=True, exist_ok=True)
    canonical_doc = load_canonical_calibration()

    for jid in ALLOWED_JUDGES:
        pkg = build_judge_calibration_package(canonical_doc, jid)
        json_path = output_dir / f"w5_calibration_{jid}_v1.json"
        with json_path.open("w", encoding="utf-8", newline="\n") as f:
            json.dump(pkg, f, ensure_ascii=False, indent=2)
            f.write("\n")

        csv_path = output_dir / f"w5_calibration_{jid}_v1.csv"
        rows = package_to_csv_rows(pkg)
        with csv_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(CSV_ALL_COLUMNS))
            writer.writeheader()
            writer.writerows(rows)

    session_log_path = output_dir / "w5_calibration_session_log_template_v1.json"
    with session_log_path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(build_session_log_template_doc(), f, ensure_ascii=False, indent=2)
        f.write("\n")

    contract_path = output_dir / "w5_calibration_submission_contract_v1.json"
    with contract_path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(build_submission_contract_doc(), f, ensure_ascii=False, indent=2)
        f.write("\n")


def _find_leakage_keys(obj: Any, path_prefix: str = "") -> list[str]:
    """Recursively scan a JSON structure for any forbidden leakage keys."""
    found: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            curr = f"{path_prefix}.{k}" if path_prefix else str(k)
            if k in FORBIDDEN_LEAKAGE_KEYS:
                found.append(curr)
            found.extend(_find_leakage_keys(v, curr))
    elif isinstance(obj, list):
        for idx, elem in enumerate(obj):
            curr = f"{path_prefix}[{idx}]"
            found.extend(_find_leakage_keys(elem, curr))
    return found


def validate_completed_calibration_label(val: Any) -> int | str:
    """Strictly validate a completed calibration label.

    Allowed values:
      - int 0, 1, 2 (strictly int, NOT bool)
      - str "NA" (exact uppercase "NA")
    """
    if isinstance(val, bool):
        raise ValueError(f"Boolean label {val!r} is forbidden; must be int in {{0, 1, 2}} or 'NA'.")
    if val is None:
        raise ValueError("Completed calibration label cannot be null/None.")
    if isinstance(val, float):
        raise ValueError(f"Float label {val!r} is forbidden; must be int in {{0, 1, 2}} or 'NA'.")
    if type(val) is int:
        if val in ALLOWED_ORDINAL_LABELS:
            return val
        raise ValueError(f"Integer label {val!r} out of range; allowed integers are 0, 1, 2.")
    if type(val) is str:
        if val == ALLOWED_MISSING_CODE:
            return val
        if val.strip() in {"0", "1", "2"} or val.strip().lstrip("-").isdigit():
            raise ValueError(
                f"Numeric string label {val!r} is forbidden; use JSON integer 0, 1, or 2."
            )
        raise ValueError(
            f"Invalid string label {val!r}; only exact uppercase 'NA' is permitted."
        )
    raise ValueError(f"Unsupported label type {type(val).__name__}: {val!r}")


def _validate_item_factual_context(
    item_id: str,
    actual_fctx: Any,
    expected_fctx: dict[str, Any],
) -> None:
    """Verify that item.factual_context is present and strictly matches reference."""
    if not isinstance(actual_fctx, dict):
        raise ValueError(
            f"Item {item_id!r} is missing required 'factual_context' object."
        )
    if set(actual_fctx.keys()) != set(expected_fctx.keys()):
        raise ValueError(
            f"Item {item_id!r} factual_context keys mismatch: "
            f"got {sorted(actual_fctx.keys())}, expected {sorted(expected_fctx.keys())}."
        )
    for k, exp_val in expected_fctx.items():
        act_val = actual_fctx.get(k)
        if not _strict_equal(act_val, exp_val):
            raise ValueError(
                f"Read-only factual_context.{k} modified on item {item_id!r}: "
                f"got {act_val!r}, expected {exp_val!r}."
            )


def validate_calibration_submission(
    submission_data: dict[str, Any],
    canonical_doc: dict[str, Any] | None = None,
    reference_package: dict[str, Any] | None = None,
    *,
    validate_empty_package: bool = False,
) -> dict[str, Any]:
    """Validate a judge calibration package or submission against canonical & judge contracts.

    Enforces exact immutability of all read-only fields at top-level, scenario-level,
    and item-level (including factual_context). Only 'label' and 'judge_note' may differ
    in a completed submission.
    """
    if not isinstance(submission_data, dict):
        raise ValueError("Submission root must be a JSON object.")

    if canonical_doc is None:
        canonical_doc = load_canonical_calibration()

    # 1. Check for forbidden leakage fields anywhere in the structure
    leakage = _find_leakage_keys(submission_data)
    if leakage:
        raise ValueError(f"Forbidden leakage fields detected: {leakage}")

    # 2. Validate judge_id
    judge_id = submission_data.get("judge_id")
    if judge_id not in ALLOWED_JUDGES:
        raise ValueError(
            f"Invalid judge_id {judge_id!r}; expected one of {ALLOWED_JUDGES}."
        )

    if reference_package is None:
        reference_package = build_judge_calibration_package(canonical_doc, judge_id)

    if judge_id != reference_package.get("judge_id"):
        raise ValueError(
            f"judge_id mismatch: submission has {judge_id!r}, "
            f"reference package has {reference_package.get('judge_id')!r}."
        )

    # 3. Validate top-level read-only fields
    cal_ver = submission_data.get("calibration_version")
    if cal_ver != CALIBRATION_VERSION:
        raise ValueError(
            f"Invalid calibration_version {cal_ver!r}; expected {CALIBRATION_VERSION!r}."
        )

    rubric_ver = submission_data.get("rubric_version")
    if rubric_ver != RUBRIC_VERSION:
        raise ValueError(
            f"Invalid rubric_version {rubric_ver!r}; expected {RUBRIC_VERSION!r}."
        )

    pres_ver = submission_data.get("presentation_version")
    if pres_ver != PRESENTATION_VERSION:
        raise ValueError(
            f"Invalid presentation_version {pres_ver!r}; expected {PRESENTATION_VERSION!r}."
        )

    if "pool_version" in submission_data and submission_data["pool_version"] != POOL_VERSION:
        raise ValueError(
            f"Invalid pool_version {submission_data['pool_version']!r}; expected {POOL_VERSION!r}."
        )
    if "base_seed" in submission_data and not _strict_equal(
        submission_data["base_seed"], ORDER_SEED_BASE
    ):
        raise ValueError(
            f"Invalid base_seed {submission_data['base_seed']!r}; expected {ORDER_SEED_BASE!r}."
        )
    if submission_data.get("track", "CALIBRATION_ONLY") != "CALIBRATION_ONLY":
        raise ValueError(
            f"Invalid track {submission_data.get('track')!r}; expected 'CALIBRATION_ONLY'."
        )
    if submission_data.get("excluded_from_final_metrics", True) is not True:
        raise ValueError("excluded_from_final_metrics must be true.")
    if "scenario_count" in submission_data and not _strict_equal(
        submission_data["scenario_count"], len(EXPECTED_SCENARIO_IDS)
    ):
        raise ValueError(
            f"Invalid scenario_count {submission_data['scenario_count']!r}; "
            f"expected {len(EXPECTED_SCENARIO_IDS)}."
        )
    if "total_items" in submission_data and not _strict_equal(
        submission_data["total_items"], EXPECTED_TOTAL_ITEMS
    ):
        raise ValueError(
            f"Invalid total_items {submission_data['total_items']!r}; "
            f"expected {EXPECTED_TOTAL_ITEMS}."
        )

    # 4. Build canonical item lookup and reference lookups
    canonical_items_by_id: dict[str, dict[str, Any]] = {}
    canonical_scenarios = canonical_doc.get("scenarios", [])
    if len(canonical_scenarios) != len(EXPECTED_SCENARIO_IDS):
        raise ValueError("Canonical calibration source has unexpected scenario count.")

    for sc in canonical_scenarios:
        sc_id = sc["scenario_id"]
        for it in sc.get("items", []):
            item_id = it["judge_item_id"]
            canonical_items_by_id[item_id] = {
                "scenario_id": sc_id,
                "judge_item_id": item_id,
                "place_id": it["place_id"],
            }

    ref_scenarios_by_id: dict[str, dict[str, Any]] = {}
    expected_order_by_scenario: dict[str, list[str]] = {}
    ref_items_by_id: dict[str, dict[str, Any]] = {}
    for sc in reference_package.get("scenarios", []):
        sc_id = sc["scenario_id"]
        ref_scenarios_by_id[sc_id] = sc
        expected_order_by_scenario[sc_id] = [
            it["judge_item_id"] for it in sc.get("items", [])
        ]
        for it in sc.get("items", []):
            ref_items_by_id[it["judge_item_id"]] = it

    # 5. Extract scenarios and items from submission
    sub_scenarios = submission_data.get("scenarios")
    if not isinstance(sub_scenarios, list):
        raise ValueError("Submission must contain a 'scenarios' list.")

    sub_scenario_ids = [sc.get("scenario_id") for sc in sub_scenarios if isinstance(sc, dict)]
    if tuple(sub_scenario_ids) != EXPECTED_SCENARIO_IDS:
        raise ValueError(
            f"Calibration scenarios mismatch: got {sub_scenario_ids}, "
            f"expected {list(EXPECTED_SCENARIO_IDS)}."
        )

    seen_item_ids: set[str] = set()
    seen_place_ids: set[str] = set()
    flat_items: list[dict[str, Any]] = []

    for sc in sub_scenarios:
        sc_id = sc.get("scenario_id")
        items = sc.get("items")
        if not isinstance(items, list):
            raise ValueError(f"Scenario {sc_id!r} must contain an 'items' list.")

        for item in items:
            if not isinstance(item, dict):
                raise ValueError(f"Each item in scenario {sc_id!r} must be a JSON object.")
            flat_items.append(item)

    # 6. Check duplicate, extra, and missing items
    for item in flat_items:
        item_id = item.get("judge_item_id") or item.get("calibration_item_id")
        if not isinstance(item_id, str) or not item_id:
            raise ValueError("Item is missing valid 'judge_item_id' / 'calibration_item_id'.")

        if (
            "calibration_item_id" in item
            and "judge_item_id" in item
            and item["calibration_item_id"] != item["judge_item_id"]
        ):
            raise ValueError(
                f"Mismatched calibration_item_id ({item['calibration_item_id']!r}) "
                f"and judge_item_id ({item['judge_item_id']!r})."
            )

        if item_id in seen_item_ids:
            raise ValueError(f"Duplicate calibration item detected: {item_id!r}.")
        seen_item_ids.add(item_id)

        if item_id not in canonical_items_by_id:
            raise ValueError(f"Extra or unknown calibration item detected: {item_id!r}.")

        place_id = item.get("place_id")
        if place_id in seen_place_ids:
            raise ValueError(f"Duplicate place_id detected across calibration items: {place_id!r}.")
        if isinstance(place_id, str):
            seen_place_ids.add(place_id)

    missing_ids = sorted(set(canonical_items_by_id.keys()) - seen_item_ids)
    if missing_ids:
        raise ValueError(f"Missing canonical calibration item(s): {missing_ids}")

    if len(flat_items) != EXPECTED_TOTAL_ITEMS:
        raise ValueError(
            f"Expected exactly {EXPECTED_TOTAL_ITEMS} items, got {len(flat_items)}."
        )

    # 7. Per-scenario and per-item read-only context immutability + label/note checks
    read_only_item_keys = (
        "judge_id",
        "calibration_version",
        "rubric_version",
        "presentation_version",
        "scenario_id",
        "presentation_index",
        "global_presentation_index",
        "calibration_item_id",
        "judge_item_id",
        "place_id",
        "destination",
        "declared_interests",
        "name",
        "category",
    )

    for sc in sub_scenarios:
        sc_id = sc["scenario_id"]
        ref_sc = ref_scenarios_by_id[sc_id]
        items = sc["items"]

        if len(items) != EXPECTED_ITEMS_PER_SCENARIO:
            raise ValueError(
                f"Scenario {sc_id!r} must have {EXPECTED_ITEMS_PER_SCENARIO} items, got {len(items)}."
            )

        # Scenario-level read-only fields check
        if not _strict_equal(sc.get("destination"), ref_sc["destination"]):
            raise ValueError(
                f"Scenario {sc_id!r} destination modified: "
                f"got {sc.get('destination')!r}, expected {ref_sc['destination']!r}."
            )
        if not _strict_equal(sc.get("declared_interests"), ref_sc["declared_interests"]):
            raise ValueError(
                f"Scenario {sc_id!r} declared_interests modified: "
                f"got {sc.get('declared_interests')!r}, expected {ref_sc['declared_interests']!r}."
            )
        if sc.get("track", "CALIBRATION_ONLY") != "CALIBRATION_ONLY":
            raise ValueError(f"Scenario {sc_id!r} track must be 'CALIBRATION_ONLY'.")
        if sc.get("excluded_from_final_metrics", True) is not True:
            raise ValueError(f"Scenario {sc_id!r} excluded_from_final_metrics must be true.")
        if "order_seed_basis" in sc and not _strict_equal(
            sc["order_seed_basis"], ref_sc["order_seed_basis"]
        ):
            raise ValueError(
                f"Scenario {sc_id!r} order_seed_basis modified: "
                f"got {sc['order_seed_basis']!r}, expected {ref_sc['order_seed_basis']!r}."
            )
        if "item_count" in sc and not _strict_equal(sc["item_count"], ref_sc["item_count"]):
            raise ValueError(
                f"Scenario {sc_id!r} item_count modified: "
                f"got {sc['item_count']!r}, expected {ref_sc['item_count']!r}."
            )

        actual_ids = [it.get("judge_item_id") or it.get("calibration_item_id") for it in items]
        expected_ids = expected_order_by_scenario[sc_id]
        if actual_ids != expected_ids:
            raise ValueError(
                f"Presentation order mismatch in scenario {sc_id!r} for judge {judge_id!r}."
            )

        for item in items:
            item_id = item.get("judge_item_id") or item.get("calibration_item_id")
            ref_item = ref_items_by_id[item_id]

            # Reject any unexpected extra keys on item
            extra_keys = set(item.keys()) - set(ref_item.keys())
            if extra_keys:
                raise ValueError(
                    f"Item {item_id!r} contains unsupported extra keys: {sorted(extra_keys)}."
                )

            # Verify every read-only item field strictly matches reference package
            for key in read_only_item_keys:
                if key not in item:
                    raise ValueError(f"Item {item_id!r} is missing required read-only field {key!r}.")
                if not _strict_equal(item[key], ref_item[key]):
                    raise ValueError(
                        f"Read-only field {key!r} modified on item {item_id!r}: "
                        f"got {item[key]!r}, expected {ref_item[key]!r}."
                    )

            # Verify factual_context is present and strictly matches reference package
            _validate_item_factual_context(
                item_id,
                item.get("factual_context"),
                ref_item["factual_context"],
            )

            label = item.get("label")
            note = item.get("judge_note")

            if validate_empty_package:
                if label is not None:
                    raise ValueError(
                        f"Empty-package validation failed: item {item_id!r} has non-null label {label!r}."
                    )
                if note is not None:
                    raise ValueError(
                        f"Empty-package validation failed: item {item_id!r} has non-null judge_note {note!r}."
                    )
            else:
                validate_completed_calibration_label(label)
                if note is not None:
                    if not isinstance(note, str):
                        raise ValueError(
                            f"Item {item_id!r} judge_note must be string or null, got {type(note).__name__}."
                        )
                    if note.lstrip().startswith("="):
                        raise ValueError(
                            f"Item {item_id!r} judge_note must not contain spreadsheet formulas."
                        )

    return {
        "status": "PASS",
        "mode": "EMPTY_PACKAGE" if validate_empty_package else "COMPLETED_SUBMISSION",
        "judge_id": judge_id,
        "calibration_version": cal_ver,
        "rubric_version": rubric_ver,
        "presentation_version": pres_ver,
        "scenario_count": len(sub_scenarios),
        "total_items": len(flat_items),
    }


def load_csv_package_as_submission_dict(
    csv_path: Path,
    canonical_doc: dict[str, Any] | None = None,
    *,
    validate_empty_package: bool = False,
) -> dict[str, Any]:
    """Load and validate a judge calibration CSV file against the deterministic reference CSV/package.

    Enforces that all CSV_READ_ONLY_COLUMNS match the judge's deterministic reference rows
    before parsing the mutable 'label' and 'judge_note' columns.
    """
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"CSV file {csv_path} is empty or missing header.")
        if tuple(reader.fieldnames) != CSV_ALL_COLUMNS:
            raise ValueError(
                f"CSV columns mismatch in {csv_path}: got {reader.fieldnames}, "
                f"expected {list(CSV_ALL_COLUMNS)}."
            )
        rows = list(reader)

    if not rows:
        raise ValueError(f"CSV file {csv_path} has 0 data rows.")

    # Check for spreadsheet formulas in any cell
    for r_idx, row in enumerate(rows, start=1):
        for col, cell in row.items():
            if isinstance(cell, str) and cell.lstrip().startswith("="):
                raise ValueError(
                    f"Spreadsheet formula detected in row {r_idx}, column {col!r}: {cell!r}"
                )

    if canonical_doc is None:
        canonical_doc = load_canonical_calibration()

    judge_id = rows[0]["judge_id"]
    if judge_id not in ALLOWED_JUDGES:
        raise ValueError(
            f"Invalid judge_id {judge_id!r} in CSV row 1; expected one of {ALLOWED_JUDGES}."
        )

    reference_package = build_judge_calibration_package(canonical_doc, judge_id)
    expected_rows = package_to_csv_rows(reference_package)

    # Check duplicate, extra, and missing items in CSV rows first
    canonical_item_ids = {r["judge_item_id"] for r in expected_rows}
    seen_csv_ids: set[str] = set()
    for r_idx, row in enumerate(rows, start=1):
        item_id = row.get("judge_item_id") or row.get("calibration_item_id") or ""
        if not item_id:
            raise ValueError(f"CSV row {r_idx} is missing judge_item_id / calibration_item_id.")
        if row.get("calibration_item_id") != row.get("judge_item_id"):
            raise ValueError(
                f"CSV row {r_idx} has mismatched calibration_item_id and judge_item_id."
            )
        if item_id in seen_csv_ids:
            raise ValueError(f"Duplicate calibration item detected in CSV: {item_id!r}.")
        seen_csv_ids.add(item_id)
        if item_id not in canonical_item_ids:
            raise ValueError(f"Extra or unknown calibration item detected in CSV: {item_id!r}.")

    missing_csv_ids = sorted(canonical_item_ids - seen_csv_ids)
    if missing_csv_ids:
        raise ValueError(f"Missing canonical calibration item(s) in CSV: {missing_csv_ids}")

    if len(rows) != len(expected_rows):
        raise ValueError(
            f"Expected {len(expected_rows)} CSV rows, got {len(rows)}."
        )

    # Compare every read-only column row-by-row against deterministic reference CSV rows
    for r_idx, (row, exp_row) in enumerate(zip(rows, expected_rows, strict=True), start=1):
        item_id = exp_row["judge_item_id"]
        for col in CSV_READ_ONLY_COLUMNS:
            actual_cell = row[col]
            expected_cell = exp_row[col]
            if col == "declared_interests":
                try:
                    actual_parsed = json.loads(actual_cell)
                except Exception as exc:
                    raise ValueError(
                        f"CSV row {r_idx} ({item_id}) has invalid JSON in read-only column "
                        f"'declared_interests': {actual_cell!r}"
                    ) from exc
                expected_parsed = json.loads(expected_cell)
                if not _strict_equal(actual_parsed, expected_parsed):
                    raise ValueError(
                        f"CSV read-only column 'declared_interests' modified on row {r_idx} ({item_id}): "
                        f"got {actual_cell!r}, expected {expected_cell!r}."
                    )
            elif col == "osm_factual_tags_json":
                try:
                    actual_tags = json.loads(actual_cell)
                except Exception as exc:
                    raise ValueError(
                        f"CSV row {r_idx} ({item_id}) has invalid JSON in read-only column "
                        f"'osm_factual_tags_json': {actual_cell!r}"
                    ) from exc
                expected_tags = json.loads(expected_cell)
                if not _strict_equal(actual_tags, expected_tags):
                    raise ValueError(
                        f"CSV read-only column 'osm_factual_tags_json' modified on row {r_idx} ({item_id}): "
                        f"got {actual_cell!r}, expected {expected_cell!r}."
                    )
            else:
                if actual_cell != expected_cell:
                    raise ValueError(
                        f"CSV read-only column {col!r} modified on row {r_idx} ({item_id}): "
                        f"got {actual_cell!r}, expected {expected_cell!r}."
                    )

    # All read-only columns match the frozen reference package; populate label and judge_note
    submission_doc = copy.deepcopy(reference_package)
    row_by_item_id = {r["judge_item_id"]: r for r in rows}

    for sc in submission_doc["scenarios"]:
        for item in sc["items"]:
            row = row_by_item_id[item["judge_item_id"]]
            raw_label = row["label"]
            raw_note = row["judge_note"]

            if validate_empty_package:
                parsed_label: Any = None if raw_label == "" else raw_label
            else:
                if raw_label == "":
                    parsed_label = None
                elif raw_label in {"0", "1", "2"}:
                    parsed_label = int(raw_label)
                else:
                    parsed_label = raw_label

            item["label"] = parsed_label
            item["judge_note"] = None if raw_note == "" else raw_note

    return submission_doc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate W5 calibration packages or judge submissions."
    )
    parser.add_argument(
        "--package",
        type=Path,
        help="Path to the judge calibration package or submission (.json or .csv).",
    )
    parser.add_argument(
        "--validate-empty-package",
        action="store_true",
        help="Validate that the package is an unannotated operational package with all labels and notes null.",
    )
    parser.add_argument(
        "--build-ops-packages",
        action="store_true",
        help="Generate deterministic J1/J2/J3 calibration packages, CSVs, and templates.",
    )
    args = parser.parse_args(argv)

    if args.build_ops_packages:
        write_calibration_ops_artifacts()
        print("BUILT_W5_CALIBRATION_OPS_ARTIFACTS")
        return 0

    if not args.package:
        parser.error("--package is required unless --build-ops-packages is specified.")

    pkg_path: Path = args.package
    if not pkg_path.exists():
        print(f"FAIL: Package not found: {pkg_path}", file=sys.stderr)
        return 1

    try:
        if pkg_path.suffix.lower() == ".csv":
            sub_data = load_csv_package_as_submission_dict(
                pkg_path, validate_empty_package=args.validate_empty_package
            )
        else:
            with pkg_path.open("r", encoding="utf-8") as f:
                sub_data = json.load(f)

        result = validate_calibration_submission(
            sub_data, validate_empty_package=args.validate_empty_package
        )
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    print(
        f"PASS: {result['mode']} judge={result['judge_id']} "
        f"scenarios={result['scenario_count']} items={result['total_items']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
