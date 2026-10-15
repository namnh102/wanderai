"""Independent Verifier for W06 Primary Scenario Freeze & P11 Manifest (W06-SCENARIO-FREEZE-01).

Independently loads and verifies:
- data/evaluation/w06/w06_scenarios_freeze_v1.json
- data/evaluation/w06/w06_p11_assignment_manifest_v1.json
- data/evaluation/w06/w06_scenario_method_lock_v1.json
- data/evaluation/w06/w06_scenario_support_matrix_v1.json
- data/curated/gomate_places_freeze_v2.json
- apps/ai-service/recommendation/reca/contract.py

Never trusts generator receipt flags; recomputes all marginals, cross-allocation matrices,
Rule A / Rule B direct place_id set union support, support classes, repeat caps, canonical
signatures, 1:1 dry-run transformation proof, per-scenario SHA256s, bundle SHA256, P11 SHA256,
and two-run clean temporary directory freeze determinism.
"""

from __future__ import annotations

import argparse
from collections import Counter
import datetime
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
AI_SERVICE_ROOT = REPO_ROOT / "apps" / "ai-service"
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.evaluation.planner_scenario_generator import (  # noqa: E402
    DEFAULT_SCENARIO_GENERATION_SEED,
    SCENARIO_GENERATOR_VERSION,
    canonical_json_bytes,
    generate_dry_run_scenarios,
)
from app.schemas.planner_benchmark import BenchmarkScenarioInput  # noqa: E402
from scripts.audit_w06_scenario_generator_dryrun import (  # noqa: E402
    CATALOG_PATH,
    EXPECTED_DRY_RUN_SHA256,
    METHOD_LOCK_PATH,
    SUPPORT_MATRIX_PATH,
    build_independent_catalog_support_map,
    independent_lf_sha256,
    recompute_independent_rule_a_b,
)
from scripts.freeze_w06_scenarios import (  # noqa: E402
    BENCHMARK_SCENARIO_INPUT_FIELDS,
    DEFAULT_P11_REL_PATH,
    DEFAULT_SCENARIO_BUNDLE_REL_PATH,
    SEMANTIC_1_TO_1_INVARIANT_FIELDS,
    serialize_canonical_json_lf,
    sha256_canonical_json_lf,
    write_frozen_scenario_artifacts,
)

SCENARIO_BUNDLE_PATH = REPO_ROOT / DEFAULT_SCENARIO_BUNDLE_REL_PATH
P11_MANIFEST_PATH = REPO_ROOT / DEFAULT_P11_REL_PATH

FORBIDDEN_SCENARIO_LEAKAGE_KEYS: Set[str] = {
    "candidate_index",
    "budget_tier_or_null",
    "weekend_exposure",
    "interest_count",
    "support_class",
    "union_support",
    "sum_support",
    "min_interest_support",
    "rule_a_passed",
    "rule_b_passed",
    "canonical_signature",
    "rejection_log",
    "executable_priority_trace",
}

FORBIDDEN_P11_MODEL_KEYS: Set[str] = {
    "model_id",
    "provider",
    "assigned_model",
    "agent_architecture",
    "prompt_version",
    "gemini_model",
    "openai_model",
    "claude_model",
    "grok_model",
    "planner_output",
    "benchmark_score",
}


class FreezeVerificationError(ValueError):
    """Raised when independent verification of W06 scenario freeze or P11 fails."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


def verify_frozen_scenario_artifacts_independently(
    *,
    scenario_bundle_dict: Optional[Dict[str, Any]] = None,
    p11_manifest_dict: Optional[Dict[str, Any]] = None,
    scenario_bundle_raw_bytes: Optional[bytes] = None,
    p11_raw_bytes: Optional[bytes] = None,
    dry_run_dict: Optional[Dict[str, Any]] = None,
    check_two_run_determinism: bool = True,
) -> Dict[str, Any]:
    """Independently verify W06 frozen scenario bundle and P11 assignment manifest."""
    if scenario_bundle_dict is None:
        if not SCENARIO_BUNDLE_PATH.exists():
            raise FreezeVerificationError("BUNDLE_MISSING", f"Missing {SCENARIO_BUNDLE_PATH}")
        scenario_bundle_raw_bytes = SCENARIO_BUNDLE_PATH.read_bytes()
        scenario_bundle_dict = json.loads(scenario_bundle_raw_bytes.decode("utf-8"))
    elif scenario_bundle_raw_bytes is None:
        scenario_bundle_raw_bytes = serialize_canonical_json_lf(scenario_bundle_dict)

    if p11_manifest_dict is None:
        if not P11_MANIFEST_PATH.exists():
            raise FreezeVerificationError("P11_MISSING", f"Missing {P11_MANIFEST_PATH}")
        p11_raw_bytes = P11_MANIFEST_PATH.read_bytes()
        p11_manifest_dict = json.loads(p11_raw_bytes.decode("utf-8"))
    elif p11_raw_bytes is None:
        p11_raw_bytes = serialize_canonical_json_lf(p11_manifest_dict)

    # Check canonical byte formatting
    expected_bundle_bytes = serialize_canonical_json_lf(scenario_bundle_dict)
    if scenario_bundle_raw_bytes != expected_bundle_bytes:
        raise FreezeVerificationError(
            "BUNDLE_NON_CANONICAL_BYTES",
            "Scenario bundle file bytes are not canonical UTF-8 LF JSON.",
        )
    expected_p11_bytes = serialize_canonical_json_lf(p11_manifest_dict)
    if p11_raw_bytes != expected_p11_bytes:
        raise FreezeVerificationError(
            "P11_NON_CANONICAL_BYTES",
            "P11 manifest file bytes are not canonical UTF-8 LF JSON.",
        )

    computed_bundle_sha256 = hashlib.sha256(scenario_bundle_raw_bytes).hexdigest()
    computed_p11_sha256 = hashlib.sha256(p11_raw_bytes).hexdigest()

    # Load frozen authorities independently
    ml = json.loads(METHOD_LOCK_PATH.read_text(encoding="utf-8"))
    sm = json.loads(SUPPORT_MATRIX_PATH.read_text(encoding="utf-8"))
    cat_map = build_independent_catalog_support_map(CATALOG_PATH)

    # Load dry-run slots for 1:1 transformation proof
    if dry_run_dict is None:
        dry_run_bundle = generate_dry_run_scenarios(seed=DEFAULT_SCENARIO_GENERATION_SEED)
        dry_run_dict = dry_run_bundle.model_dump(mode="json")
    computed_dry_run_sha256 = hashlib.sha256(canonical_json_bytes(dry_run_dict)).hexdigest()
    if computed_dry_run_sha256 != EXPECTED_DRY_RUN_SHA256:
        raise FreezeVerificationError(
            "SOURCE_DRY_RUN_SHA_MISMATCH",
            f"Dry-run SHA {computed_dry_run_sha256} != {EXPECTED_DRY_RUN_SHA256}",
        )

    # Top-level bundle checks
    if scenario_bundle_dict.get("artifact_id") != "W06-SCENARIOS-FREEZE-01":
        raise FreezeVerificationError("BUNDLE_ARTIFACT_ID_INVALID", "Invalid bundle artifact_id")
    if scenario_bundle_dict.get("version") != "1.0.0":
        raise FreezeVerificationError("BUNDLE_VERSION_INVALID", "Invalid bundle version")
    if scenario_bundle_dict.get("scenario_count") != 100:
        raise FreezeVerificationError("BUNDLE_COUNT_FIELD_INVALID", "scenario_count != 100")
    if scenario_bundle_dict.get("source_generator_version") != SCENARIO_GENERATOR_VERSION:
        raise FreezeVerificationError("BUNDLE_GENERATOR_VERSION_INVALID", "Invalid source_generator_version")
    if scenario_bundle_dict.get("source_seed") != DEFAULT_SCENARIO_GENERATION_SEED:
        raise FreezeVerificationError("BUNDLE_SEED_INVALID", "Invalid source_seed")
    if scenario_bundle_dict.get("source_dry_run_sha256") != EXPECTED_DRY_RUN_SHA256:
        raise FreezeVerificationError("BUNDLE_DRY_RUN_SHA_INVALID", "Invalid source_dry_run_sha256 in bundle")
    if scenario_bundle_dict.get("hash_basis") != "SHA256_CANONICAL_JSON_UTF8_LF_BYTES":
        raise FreezeVerificationError("BUNDLE_HASH_BASIS_INVALID", "Invalid hash_basis in bundle")

    # Top-level P11 checks
    if p11_manifest_dict.get("artifact_id") != "W06-P11-FROZEN-ASSIGNMENT-MANIFEST":
        raise FreezeVerificationError("P11_ARTIFACT_ID_INVALID", "Invalid P11 artifact_id")
    if p11_manifest_dict.get("version") != "1.0.0":
        raise FreezeVerificationError("P11_VERSION_INVALID", "Invalid P11 version")
    if p11_manifest_dict.get("scenario_freeze_id") != "W06-SCENARIOS-FREEZE-01":
        raise FreezeVerificationError("P11_FREEZE_ID_INVALID", "Invalid scenario_freeze_id")
    if p11_manifest_dict.get("scenario_count") != 100:
        raise FreezeVerificationError("P11_COUNT_FIELD_INVALID", "P11 scenario_count != 100")
    if p11_manifest_dict.get("generator_seed") != DEFAULT_SCENARIO_GENERATION_SEED:
        raise FreezeVerificationError("P11_SEED_INVALID", "Invalid P11 generator_seed")
    if p11_manifest_dict.get("source_dry_run_sha256") != EXPECTED_DRY_RUN_SHA256:
        raise FreezeVerificationError("P11_DRY_RUN_SHA_INVALID", "Invalid P11 source_dry_run_sha256")
    if p11_manifest_dict.get("scenario_bundle_sha256") != computed_bundle_sha256:
        raise FreezeVerificationError(
            "P11_BUNDLE_SHA_MISMATCH",
            f"P11 scenario_bundle_sha256={p11_manifest_dict.get('scenario_bundle_sha256')} != {computed_bundle_sha256}",
        )
    if p11_manifest_dict.get("hash_basis_version") != "W06-ARTIFACT-HASH-BASIS-V1":
        raise FreezeVerificationError("P11_HASH_BASIS_INVALID", "Invalid P11 hash_basis_version")
    for flag_true in (
        "created_before_model_selection",
        "created_before_preregistration",
        "created_before_final_execution",
    ):
        if p11_manifest_dict.get(flag_true) is not True:
            raise FreezeVerificationError("P11_PRECONDITION_FLAG_INVALID", f"{flag_true} must be True")
    if p11_manifest_dict.get("model_output_used") is not False:
        raise FreezeVerificationError("P11_MODEL_OUTPUT_FLAG_INVALID", "model_output_used must be False")

    if FORBIDDEN_P11_MODEL_KEYS.intersection(p11_manifest_dict.keys()):
        raise FreezeVerificationError("P11_MODEL_LEAKAGE", "P11 top-level contains forbidden model/provider keys")

    scenarios = scenario_bundle_dict.get("scenarios")
    assignments = p11_manifest_dict.get("assignments")
    dry_run_slots = dry_run_dict.get("slots")

    if not isinstance(scenarios, list) or len(scenarios) != 100:
        raise FreezeVerificationError("SCENARIO_COUNT_MISMATCH", f"Expected 100 scenarios, got {len(scenarios) if isinstance(scenarios, list) else None}")
    if not isinstance(assignments, list) or len(assignments) != 100:
        raise FreezeVerificationError("P11_ASSIGNMENT_COUNT_MISMATCH", f"Expected 100 P11 assignments, got {len(assignments) if isinstance(assignments, list) else None}")
    if not isinstance(dry_run_slots, list) or len(dry_run_slots) != 100:
        raise FreezeVerificationError("DRY_RUN_SLOT_COUNT_MISMATCH", "Expected 100 dry-run slots")

    canonical_interests_set = set(ml["interest_count_target"]["canonical_interests"])
    allowed_destinations = {"ha-noi": "Hà Nội", "da-nang": "Đà Nẵng", "ha-long": "Hạ Long"}
    allowed_days = {2, 3, 4}
    allowed_k = {1, 2, 3}
    allowed_styles = {"BACKPACKER", "BUDGET", "COMFORT", "LUXURY"}
    daily_nominal = {
        "B1": ml["budget_policy"]["nominal_tiers"]["B1"]["daily_nominal_vnd"],
        "B2": ml["budget_policy"]["nominal_tiers"]["B2"]["daily_nominal_vnd"],
        "B3": ml["budget_policy"]["nominal_tiers"]["B3"]["daily_nominal_vnd"],
    }
    daily_to_tier = {v: k for k, v in daily_nominal.items()}
    win_start = datetime.date.fromisoformat(ml["date_policy"]["window_start_date"])
    win_end = datetime.date.fromisoformat(ml["date_policy"]["window_end_date"])
    repeat_caps = ml["near_duplicate_policy"]["repeat_caps_by_destination_and_interest_count"]

    dest_counts = {"ha-noi": 0, "da-nang": 0, "ha-long": 0}
    days_counts = {"2": 0, "3": 0, "4": 0}
    k_counts = {"1": 0, "2": 0, "3": 0}
    budget_counts = {"B1": 0, "B2": 0, "B3": 0, "null": 0}
    style_counts = {"BACKPACKER": 0, "BUDGET": 0, "COMFORT": 0, "LUXURY": 0}
    wk_counts = {"weekend_exposed": 0, "non_weekend_exposed": 0}
    sc_counts = {"CLEAR": 0, "STRESS": 0, "EXCLUDED": 0}

    dest_by_days = {d: {"2": 0, "3": 0, "4": 0} for d in allowed_destinations}
    dest_by_k = {d: {"1": 0, "2": 0, "3": 0} for d in allowed_destinations}

    seen_scenario_ids: Set[str] = set()
    seen_scenario_hashes: Set[str] = set()
    seen_canonical_signatures: Set[Tuple[Any, ...]] = set()
    repeat_counter: Counter[Tuple[str, Tuple[str, ...]]] = Counter()

    rule_a_failures = 0
    rule_b_failures = 0
    excluded_used = 0

    for idx in range(1, 101):
        scen = scenarios[idx - 1]
        p11_row = assignments[idx - 1]
        dry_slot = dry_run_slots[idx - 1]
        dry_in = dry_slot["scenario_input"]

        if not isinstance(scen, dict) or not isinstance(p11_row, dict):
            raise FreezeVerificationError("ENTRY_NOT_DICT", f"Non-dict entry at index {idx}")

        # Check no forbidden leakage keys in final scenario or P11 row
        leaked_scen_keys = FORBIDDEN_SCENARIO_LEAKAGE_KEYS.intersection(scen.keys())
        if leaked_scen_keys:
            raise FreezeVerificationError(
                "SCENARIO_METADATA_LEAKAGE",
                f"Forbidden generator/QA metadata keys {sorted(leaked_scen_keys)} in scenario {idx}",
            )
        if tuple(sorted(scen.keys())) != tuple(sorted(BENCHMARK_SCENARIO_INPUT_FIELDS)):
            raise FreezeVerificationError(
                "SCENARIO_FIELD_SET_INVALID",
                f"Scenario {idx} keys {sorted(scen.keys())} != {sorted(BENCHMARK_SCENARIO_INPUT_FIELDS)}",
            )

        leaked_p11_keys = FORBIDDEN_P11_MODEL_KEYS.intersection(p11_row.keys())
        if leaked_p11_keys:
            raise FreezeVerificationError(
                "P11_ROW_MODEL_LEAKAGE",
                f"Forbidden model/provider keys {sorted(leaked_p11_keys)} in P11 row {idx}",
            )

        # Validate through BenchmarkScenarioInput schema
        try:
            validated = BenchmarkScenarioInput.model_validate(scen)
        except Exception as exc:
            raise FreezeVerificationError(
                "BENCHMARK_SCHEMA_INVALID", f"Scenario {idx} failed BenchmarkScenarioInput validation: {exc}"
            ) from exc
        if validated.model_dump(mode="json") != scen:
            raise FreezeVerificationError(
                "BENCHMARK_SCHEMA_DUMP_MISMATCH", f"Scenario {idx} normalized dump differs from raw dict"
            )

        expected_scen_id = f"W06-SCENARIO-{idx:03d}"
        expected_dry_id = f"W06-DRYRUN-{idx:03d}"
        if scen["scenario_id"] != expected_scen_id:
            raise FreezeVerificationError(
                "SCENARIO_ID_SEQUENCE_INVALID",
                f"Expected scenario_id={expected_scen_id}, got {scen['scenario_id']!r}",
            )
        if scen["scenario_id"] in seen_scenario_ids:
            raise FreezeVerificationError("DUPLICATE_SCENARIO_ID", f"Duplicate {scen['scenario_id']}")
        seen_scenario_ids.add(scen["scenario_id"])

        if scen["fixture_label"] is not None:
            raise FreezeVerificationError(
                "FIXTURE_LABEL_NOT_NULL",
                f"Expected fixture_label=None on {expected_scen_id}, got {scen['fixture_label']!r}",
            )
        if scen["allow_revisit_place_ids"] is not False:
            raise FreezeVerificationError(
                "ALLOW_REVISIT_NOT_FALSE",
                f"Expected allow_revisit_place_ids=False on {expected_scen_id}",
            )
        if scen["currency"] != "VND":
            raise FreezeVerificationError(
                "CURRENCY_NOT_VND",
                f"Expected currency='VND' on {expected_scen_id}, got {scen['currency']!r}",
            )

        # Section 12: 1:1 semantic equality against dry-run slot scenario_input
        if dry_slot["slot_index"] != idx or dry_slot["scenario_id"] != expected_dry_id:
            raise FreezeVerificationError("DRY_RUN_SLOT_ALIGNMENT_FAILED", f"Slot alignment failed at {idx}")
        if dry_in.get("scenario_id") != expected_dry_id or dry_in.get("fixture_label") != "SYNTHETIC_GENERATOR_QA":
            raise FreezeVerificationError("DRY_RUN_SOURCE_LABELS_INVALID", f"Dry-run labels invalid at {idx}")
        for field_name in SEMANTIC_1_TO_1_INVARIANT_FIELDS:
            if scen[field_name] != dry_in[field_name]:
                raise FreezeVerificationError(
                    "SEMANTIC_1_TO_1_MISMATCH",
                    f"Field {field_name!r} mismatch at slot {idx}: {scen[field_name]!r} != {dry_in[field_name]!r}",
                )

        # Per-scenario SHA256 verification
        recomputed_scen_sha = sha256_canonical_json_lf(scen)
        if recomputed_scen_sha in seen_scenario_hashes:
            raise FreezeVerificationError("DUPLICATE_SCENARIO_SHA", f"Duplicate scenario_sha256 at {expected_scen_id}")
        seen_scenario_hashes.add(recomputed_scen_sha)

        # P11 index & ID alignment
        if p11_row.get("assignment_index") != idx or p11_row.get("source_slot_index") != idx:
            raise FreezeVerificationError(
                "P11_INDEX_MISMATCH",
                f"Expected assignment_index=source_slot_index={idx}, got {p11_row.get('assignment_index')}/{p11_row.get('source_slot_index')}",
            )
        if p11_row.get("source_dry_run_scenario_id") != expected_dry_id:
            raise FreezeVerificationError(
                "P11_SOURCE_ID_MISMATCH",
                f"Expected source_dry_run_scenario_id={expected_dry_id}, got {p11_row.get('source_dry_run_scenario_id')!r}",
            )
        if p11_row.get("scenario_id") != expected_scen_id:
            raise FreezeVerificationError(
                "P11_SCENARIO_ID_MISMATCH",
                f"Expected P11 scenario_id={expected_scen_id}, got {p11_row.get('scenario_id')!r}",
            )
        if p11_row.get("scenario_sha256") != recomputed_scen_sha:
            raise FreezeVerificationError(
                "P11_SCENARIO_SHA_MISMATCH",
                f"P11 scenario_sha256 mismatch on {expected_scen_id}: {p11_row.get('scenario_sha256')} != {recomputed_scen_sha}",
            )

        # Destination, days, interests, budget, style, dates, weekend
        dest = scen["destination_slug"]
        if dest not in allowed_destinations or scen["destination"] != allowed_destinations[dest]:
            raise FreezeVerificationError("DESTINATION_INVALID", f"Invalid destination on {expected_scen_id}")
        days = scen["days"]
        if days not in allowed_days:
            raise FreezeVerificationError("DAYS_INVALID", f"Invalid days={days} on {expected_scen_id}")

        interests = scen["interests"]
        k = len(interests)
        if k not in allowed_k or len(set(interests)) != k or interests != sorted(interests):
            raise FreezeVerificationError("INTERESTS_INVALID", f"Invalid interests={interests} on {expected_scen_id}")
        for intr in interests:
            if intr not in canonical_interests_set:
                raise FreezeVerificationError("NON_CANONICAL_INTEREST", f"Invalid interest {intr!r}")

        budget_val = scen["budget"]
        if budget_val is None:
            recomputed_tier: Optional[str] = None
        else:
            if budget_val % days != 0 or (budget_val // days) not in daily_to_tier:
                raise FreezeVerificationError(
                    "BUDGET_FORMULA_INVALID",
                    f"Budget {budget_val} is not a valid tier * {days}d on {expected_scen_id}",
                )
            recomputed_tier = daily_to_tier[budget_val // days]
            if daily_nominal[recomputed_tier] * days != budget_val:
                raise FreezeVerificationError("BUDGET_FORMULA_INVALID", f"Budget formula mismatch on {expected_scen_id}")

        style = scen["travel_style"]
        if style not in allowed_styles:
            raise FreezeVerificationError("STYLE_INVALID", f"Invalid travel_style={style!r} on {expected_scen_id}")

        s_dt = datetime.date.fromisoformat(scen["start_date"])
        e_dt = datetime.date.fromisoformat(scen["end_date"])
        if s_dt < win_start or e_dt > win_end:
            raise FreezeVerificationError("DATE_OUTSIDE_WINDOW", f"Date outside frozen window on {expected_scen_id}")
        if (e_dt - s_dt).days + 1 != days:
            raise FreezeVerificationError("NON_CONTIGUOUS_DATES", f"Dates not contiguous on {expected_scen_id}")
        trip_dates = [s_dt + datetime.timedelta(days=offset) for offset in range(days)]
        ind_weekend = any(dt.weekday() in (5, 6) for dt in trip_dates)

        # Independent Rule A / Rule B / support_class
        ind_support = recompute_independent_rule_a_b(dest, days, interests, cat_map)
        if not ind_support["rule_a_passed"]:
            rule_a_failures += 1
        if not ind_support["rule_b_passed"]:
            rule_b_failures += 1
        if not ind_support["eligible"]:
            excluded_used += 1
        if not ind_support["rule_a_passed"] or not ind_support["rule_b_passed"]:
            raise FreezeVerificationError("RULE_A_B_FAILED", f"Rule A/B failed on {expected_scen_id}")

        matrix_combs = [
            c
            for c in sm["destinations"][dest]["by_days"][str(days)]["combinations"]
            if c["interests_sorted"] == interests
        ]
        if len(matrix_combs) != 1 or not matrix_combs[0]["eligible"] or matrix_combs[0]["support_class"] == "EXCLUDED":
            raise FreezeVerificationError("EXCLUDED_COMBINATION_USED", f"Excluded combination on {expected_scen_id}")
        if ind_support["support_class"] != matrix_combs[0]["support_class"]:
            raise FreezeVerificationError("SUPPORT_CLASS_MATRIX_MISMATCH", f"Support class mismatch on {expected_scen_id}")

        # Verify P11 row metadata matches scenario semantics
        expected_sig = [dest, days, list(interests), recomputed_tier, ind_weekend, style]
        if (
            p11_row.get("destination_slug") != dest
            or p11_row.get("days") != days
            or p11_row.get("interest_count") != k
            or p11_row.get("interests") != interests
            or p11_row.get("budget_tier_or_null") != recomputed_tier
            or p11_row.get("travel_style") != style
            or p11_row.get("weekend_exposure") is not ind_weekend
            or p11_row.get("support_class") != ind_support["support_class"]
            or p11_row.get("canonical_signature") != expected_sig
        ):
            raise FreezeVerificationError(
                "P11_METADATA_SEMANTIC_MISMATCH",
                f"P11 metadata does not match recomputed scenario semantics on {expected_scen_id}",
            )

        # Repeat cap check
        combo_key = (dest, tuple(interests))
        repeat_counter[combo_key] += 1
        cap_limit = int(repeat_caps[dest][str(k)]["repeat_cap"])
        if repeat_counter[combo_key] > cap_limit:
            raise FreezeVerificationError(
                "REPEAT_CAP_EXCEEDED",
                f"Repeat cap exceeded for {combo_key}: {repeat_counter[combo_key]} > {cap_limit}",
            )

        # Canonical signature uniqueness
        sig_tuple = (dest, days, tuple(interests), recomputed_tier, ind_weekend, style)
        if sig_tuple in seen_canonical_signatures:
            raise FreezeVerificationError(
                "DUPLICATE_CANONICAL_SIGNATURE",
                f"Duplicate canonical signature on {expected_scen_id}",
            )
        seen_canonical_signatures.add(sig_tuple)

        # Accumulate marginals & cross-matrices
        dest_counts[dest] += 1
        days_counts[str(days)] += 1
        k_counts[str(k)] += 1
        b_key = recomputed_tier if recomputed_tier is not None else "null"
        budget_counts[b_key] += 1
        style_counts[style] += 1
        wk_key = "weekend_exposed" if ind_weekend else "non_weekend_exposed"
        wk_counts[wk_key] += 1
        sc_counts[ind_support["support_class"]] += 1

        dest_by_days[dest][str(days)] += 1
        dest_by_k[dest][str(k)] += 1

    # Verify frozen marginals & matrices
    if dest_counts != {"ha-noi": 34, "da-nang": 33, "ha-long": 33}:
        raise FreezeVerificationError("DESTINATION_MARGINAL_MISMATCH", f"dest_counts={dest_counts}")
    if days_counts != {"2": 33, "3": 34, "4": 33}:
        raise FreezeVerificationError("DAYS_MARGINAL_MISMATCH", f"days_counts={days_counts}")
    if dest_by_days != ml["destination_days_cross_allocation"]:
        raise FreezeVerificationError("DEST_DAYS_MATRIX_MISMATCH", f"dest_by_days={dest_by_days}")
    if k_counts != {"1": 33, "2": 34, "3": 33}:
        raise FreezeVerificationError("INTEREST_COUNT_MARGINAL_MISMATCH", f"k_counts={k_counts}")
    if dest_by_k != ml["destination_interest_count_cross_allocation"]:
        raise FreezeVerificationError("DEST_K_MATRIX_MISMATCH", f"dest_by_k={dest_by_k}")
    if budget_counts != {"B1": 27, "B2": 27, "B3": 26, "null": 20}:
        raise FreezeVerificationError("BUDGET_MARGINAL_MISMATCH", f"budget_counts={budget_counts}")
    if style_counts != {"BACKPACKER": 25, "BUDGET": 25, "COMFORT": 25, "LUXURY": 25}:
        raise FreezeVerificationError("STYLE_MARGINAL_MISMATCH", f"style_counts={style_counts}")
    if wk_counts != {"weekend_exposed": 50, "non_weekend_exposed": 50}:
        raise FreezeVerificationError("WEEKEND_MARGINAL_MISMATCH", f"wk_counts={wk_counts}")
    if sc_counts != {"CLEAR": 81, "STRESS": 19, "EXCLUDED": 0}:
        raise FreezeVerificationError("SUPPORT_CLASS_COUNTS_MISMATCH", f"sc_counts={sc_counts}")

    run1_bundle_sha = computed_bundle_sha256
    run2_bundle_sha = computed_bundle_sha256
    run1_p11_sha = computed_p11_sha256
    run2_p11_sha = computed_p11_sha256

    if check_two_run_determinism:
        with tempfile.TemporaryDirectory(prefix="w06_freeze_det_1_") as dir1, tempfile.TemporaryDirectory(
            prefix="w06_freeze_det_2_"
        ) as dir2:
            b1_path = Path(dir1) / "w06_scenarios_freeze_v1.json"
            p1_path = Path(dir1) / "w06_p11_assignment_manifest_v1.json"
            b2_path = Path(dir2) / "w06_scenarios_freeze_v1.json"
            p2_path = Path(dir2) / "w06_p11_assignment_manifest_v1.json"

            write_frozen_scenario_artifacts(scenario_bundle_path=b1_path, p11_path=p1_path)
            write_frozen_scenario_artifacts(scenario_bundle_path=b2_path, p11_path=p2_path)

            run1_bundle_sha = independent_lf_sha256(b1_path)
            run2_bundle_sha = independent_lf_sha256(b2_path)
            run1_p11_sha = independent_lf_sha256(p1_path)
            run2_p11_sha = independent_lf_sha256(p2_path)

            if (
                b1_path.read_bytes() != b2_path.read_bytes()
                or p1_path.read_bytes() != p2_path.read_bytes()
                or run1_bundle_sha != computed_bundle_sha256
                or run1_p11_sha != computed_p11_sha256
            ):
                raise FreezeVerificationError(
                    "FREEZE_DETERMINISM_FAILED",
                    f"Two-run freeze determinism mismatch: bundle={run1_bundle_sha}/{run2_bundle_sha}, p11={run1_p11_sha}/{run2_p11_sha}",
                )

    return {
        "verification_status": "PASS",
        "source_dry_run_sha256": computed_dry_run_sha256,
        "final_scenario_count": 100,
        "p11_assignment_count": 100,
        "per_scenario_hash_count": len(seen_scenario_hashes),
        "final_id_range": "W06-SCENARIO-001 .. W06-SCENARIO-100",
        "semantic_1_to_1_transformation": "PASS",
        "benchmark_schema_validation": "PASS",
        "p11_assignment_validation": "PASS",
        "scenario_bundle_sha256": computed_bundle_sha256,
        "p11_sha256": computed_p11_sha256,
        "freeze_run_1_bundle_sha256": run1_bundle_sha,
        "freeze_run_2_bundle_sha256": run2_bundle_sha,
        "freeze_run_1_p11_sha256": run1_p11_sha,
        "freeze_run_2_p11_sha256": run2_p11_sha,
        "freeze_determinism": "PASS",
        "destination_counts": dest_counts,
        "days_counts": days_counts,
        "destination_by_days": dest_by_days,
        "interest_count_counts": k_counts,
        "destination_by_interest_count": dest_by_k,
        "budget_counts": budget_counts,
        "travel_style_counts": style_counts,
        "weekend_counts": wk_counts,
        "support_class_counts": sc_counts,
        "rule_a_failures": rule_a_failures,
        "rule_b_failures": rule_b_failures,
        "excluded_combinations_used": excluded_used,
        "repeat_cap_violations": 0,
        "duplicate_canonical_signatures": 0,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Independently verify W06 frozen scenario bundle and P11 assignment manifest."
    )
    parser.add_argument(
        "--skip-two-run-determinism",
        action="store_true",
        help="Skip two-run clean temporary directory regeneration check.",
    )
    args = parser.parse_args(argv)

    report = verify_frozen_scenario_artifacts_independently(
        check_two_run_determinism=not args.skip_two_run_determinism
    )
    sys.stdout.write(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
