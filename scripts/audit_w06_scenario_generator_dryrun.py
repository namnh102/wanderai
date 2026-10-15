"""Independent Adversarial QA Verifier for W06-SCENARIO-GENERATOR-01 (W06-SCENARIO-GENERATOR-QA-01).

INDEPENDENCE CONTRACT:
- This script audits the dry-run output of W06-SCENARIO-GENERATOR-01 without calling
  `verify_dry_run_bundle_invariants()`, `verify_combination_direct_support()`,
  `load_direct_catalog_interest_sets()`, or `build_cross_balance_report()` from the
  generator module, and never trusts `bundle["invariants_verified"]`,
  `slot["rule_a_passed"]`, `slot["rule_b_passed"]`, or `slot["support_class"]`.
- All marginals, cross-allocations, Rule A / Rule B direct set-union support,
  support classes, repeat-cap counters, canonical duplicate signatures, date windows,
  budget formulas, rejection log invariants, and cross-balance tables are
  recomputed independently from the frozen scientific authorities:
  1. data/evaluation/w06/w06_scenario_method_lock_v1.json
  2. data/evaluation/w06/w06_scenario_support_matrix_v1.json
  3. data/curated/gomate_places_freeze_v2.json
  4. apps/ai-service/recommendation/reca/contract.py (poi_to_canonical_vector)
"""

from __future__ import annotations

import argparse
from collections import Counter
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
AI_SERVICE_ROOT = REPO_ROOT / "apps" / "ai-service"
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from recommendation.reca.contract import (  # noqa: E402
    CANONICAL_INTERESTS,
    poi_to_canonical_vector,
)

METHOD_LOCK_PATH = REPO_ROOT / "data" / "evaluation" / "w06" / "w06_scenario_method_lock_v1.json"
SUPPORT_MATRIX_PATH = REPO_ROOT / "data" / "evaluation" / "w06" / "w06_scenario_support_matrix_v1.json"
CATALOG_PATH = REPO_ROOT / "data" / "curated" / "gomate_places_freeze_v2.json"
RECA_CONTRACT_PATH = AI_SERVICE_ROOT / "recommendation" / "reca" / "contract.py"
GENERATOR_SOURCE_PATH = AI_SERVICE_ROOT / "app" / "evaluation" / "planner_scenario_generator.py"
DRYRUN_CLI_PATH = REPO_ROOT / "scripts" / "generate_w06_scenarios_dryrun.py"

EXPECTED_DRY_RUN_SHA256 = "3c3b5314c2fca0fb3c2fb53cc1b4fc26cc06b83d058218adfa13f8b641c1f769"
EXPECTED_SEED = 2026101506

EXPECTED_PRIORITY_TRACE: List[str] = [
    "DESTINATION_ALLOCATION",
    "DAYS_ALLOCATION",
    "INTEREST_COUNT_ALLOCATION",
    "BUDGET_ALLOCATION",
    "TRAVEL_STYLE_ALLOCATION",
    "WEEKEND_EXPOSURE_ALLOCATION",
    "SCENARIO_ELIGIBILITY",
    "DUPLICATE_REPEAT_CAP",
    "CLEAR_STRESS_COVERAGE",
    "CROSS_DIMENSION_IMBALANCE",
]

FORBIDDEN_REJECTION_KEYS: Set[str] = {
    "planner_output",
    "model_output",
    "gemini_response",
    "provider_cost",
    "benchmark_performance",
    "scientific_result",
}


class IndependentDryRunAuditError(ValueError):
    """Raised when the independent QA verifier detects any invariant violation in a dry-run bundle."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


def independent_lf_sha256(path: Path) -> str:
    """Compute SHA256 over LF-normalized file bytes."""
    normalized = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(normalized).hexdigest()


def independent_canonical_json_bytes(obj: Any) -> bytes:
    """Serialize JSON object to canonical UTF-8 LF bytes."""
    return (json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def build_independent_catalog_support_map(
    catalog_path: Path = CATALOG_PATH,
) -> Dict[str, Dict[str, Set[str]]]:
    """Independently build destination -> canonical_interest -> set(place_id) from Freeze V2 catalog."""
    raw = json.loads(catalog_path.read_text(encoding="utf-8"))
    places = raw["places"] if isinstance(raw, dict) and "places" in raw else raw
    destinations = ("ha-noi", "da-nang", "ha-long")
    support_map: Dict[str, Dict[str, Set[str]]] = {
        d: {intr: set() for intr in CANONICAL_INTERESTS} for d in destinations
    }
    for place in places:
        if not place.get("is_rec_a_core_v2", False):
            continue
        dest = place.get("destination_slug")
        if dest not in support_map:
            continue
        place_id = place["place_id"]
        vec, _ = poi_to_canonical_vector(place)
        for i, intr in enumerate(CANONICAL_INTERESTS):
            if vec[i] > 0.0:
                support_map[dest][intr].add(place_id)
    return support_map


def recompute_independent_rule_a_b(
    destination_slug: str,
    days: int,
    interests: Sequence[str],
    support_map: Dict[str, Dict[str, Set[str]]],
) -> Dict[str, Any]:
    """Independently recompute Rule A, Rule B (direct place_id set union), and support_class."""
    dest_sets = support_map[destination_slug]
    per_interest_counts = {intr: len(dest_sets[intr]) for intr in interests}
    min_support = min(per_interest_counts.values())
    sum_support = sum(per_interest_counts.values())
    union_ids: Set[str] = set()
    for intr in interests:
        union_ids |= dest_sets[intr]
    union_support = len(union_ids)

    rule_a_ok = all(c >= days for c in per_interest_counts.values())
    rule_b_ok = (union_support >= 2 * days) and (sum_support >= 2 * days)
    eligible = rule_a_ok and rule_b_ok
    if not eligible:
        support_class = "EXCLUDED"
    elif any(days <= c < 2 * days for c in per_interest_counts.values()):
        support_class = "STRESS"
    else:
        support_class = "CLEAR"

    return {
        "per_interest_counts": per_interest_counts,
        "min_interest_support": min_support,
        "sum_support": sum_support,
        "union_support": union_support,
        "rule_a_passed": rule_a_ok,
        "rule_b_passed": rule_b_ok,
        "eligible": eligible,
        "support_class": support_class,
    }


def recompute_independent_cross_tables(slots: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Independently recompute all marginal and cross-balance tables from raw slot dicts."""
    destinations = ("ha-noi", "da-nang", "ha-long")
    days_keys = ("2", "3", "4")
    k_keys = ("1", "2", "3")
    budget_keys = ("B1", "B2", "B3", "null")
    style_keys = ("BACKPACKER", "BUDGET", "COMFORT", "LUXURY")
    wk_keys = ("weekend_exposed", "non_weekend_exposed")
    sc_keys = ("CLEAR", "STRESS", "EXCLUDED")

    dest_counts = {d: 0 for d in destinations}
    days_counts = {d: 0 for d in days_keys}
    k_counts = {k: 0 for k in k_keys}
    budget_counts = {b: 0 for b in budget_keys}
    style_counts = {st: 0 for st in style_keys}
    wk_counts = {w: 0 for w in wk_keys}
    sc_counts = {sc: 0 for sc in sc_keys}

    dest_by_days = {d: {day: 0 for day in days_keys} for d in destinations}
    dest_by_k = {d: {k: 0 for k in k_keys} for d in destinations}
    dest_by_budget = {d: {b: 0 for b in budget_keys} for d in destinations}
    dest_by_style = {d: {st: 0 for st in style_keys} for d in destinations}
    dest_by_wk = {d: {w: 0 for w in wk_keys} for d in destinations}
    days_by_k = {day: {k: 0 for k in k_keys} for day in days_keys}
    days_by_budget = {day: {b: 0 for b in budget_keys} for day in days_keys}
    days_by_style = {day: {st: 0 for st in style_keys} for day in days_keys}
    k_by_budget = {k: {b: 0 for b in budget_keys} for k in k_keys}
    k_by_style = {k: {st: 0 for st in style_keys} for k in k_keys}
    sc_by_dest = {d: {sc: 0 for sc in sc_keys} for d in destinations}

    for slot in slots:
        d = slot["destination_slug"]
        day = str(slot["days"])
        k = str(slot["interest_count"])
        b = slot["budget_tier_or_null"] if slot["budget_tier_or_null"] is not None else "null"
        st = slot["travel_style"]
        wk = "weekend_exposed" if slot["weekend_exposure"] else "non_weekend_exposed"
        sc = slot["support_class"]

        dest_counts[d] += 1
        days_counts[day] += 1
        k_counts[k] += 1
        budget_counts[b] += 1
        style_counts[st] += 1
        wk_counts[wk] += 1
        sc_counts[sc] += 1

        dest_by_days[d][day] += 1
        dest_by_k[d][k] += 1
        dest_by_budget[d][b] += 1
        dest_by_style[d][st] += 1
        dest_by_wk[d][wk] += 1
        days_by_k[day][k] += 1
        days_by_budget[day][b] += 1
        days_by_style[day][st] += 1
        k_by_budget[k][b] += 1
        k_by_style[k][st] += 1
        sc_by_dest[d][sc] += 1

    def _spread(tbl: Dict[str, Dict[str, int]]) -> Dict[str, int]:
        cells = [v for row in tbl.values() for v in row.values()]
        return {
            "max_cell": max(cells),
            "min_cell": min(cells),
            "max_minus_min": max(cells) - min(cells),
        }

    imbalance = {
        "destination_by_days": _spread(dest_by_days),
        "destination_by_interest_count": _spread(dest_by_k),
        "destination_by_budget": _spread(dest_by_budget),
        "destination_by_style": _spread(dest_by_style),
        "destination_by_weekend": _spread(dest_by_wk),
        "days_by_interest_count": _spread(days_by_k),
        "days_by_budget": _spread(days_by_budget),
        "days_by_style": _spread(days_by_style),
        "interest_count_by_budget": _spread(k_by_budget),
        "interest_count_by_style": _spread(k_by_style),
    }

    return {
        "locked_marginal_counts": {
            "total_scenarios": len(slots),
            "destination": dest_counts,
            "days": days_counts,
            "interest_count": k_counts,
            "budget": budget_counts,
            "travel_style": style_counts,
            "weekend_exposure": wk_counts,
        },
        "destination_by_days": dest_by_days,
        "destination_by_interest_count": dest_by_k,
        "destination_by_budget": dest_by_budget,
        "destination_by_style": dest_by_style,
        "destination_by_weekend": dest_by_wk,
        "days_by_interest_count": days_by_k,
        "days_by_budget": days_by_budget,
        "days_by_style": days_by_style,
        "interest_count_by_budget": k_by_budget,
        "interest_count_by_style": k_by_style,
        "support_class_counts": sc_counts,
        "support_class_by_destination": sc_by_dest,
        "max_min_cross_cell_imbalance": imbalance,
    }


def audit_dry_run_bundle_independently(
    bundle_dict: Dict[str, Any],
    *,
    method_lock: Optional[Dict[str, Any]] = None,
    support_matrix: Optional[Dict[str, Any]] = None,
    catalog_support_map: Optional[Dict[str, Dict[str, Set[str]]]] = None,
) -> Dict[str, Any]:
    """Independently verify all W06 dry-run invariants from raw bundle dict and frozen authorities.

    Never calls generator verification helpers or trusts `bundle_dict["invariants_verified"]`.
    Raises IndependentDryRunAuditError on any invariant violation.
    """
    ml = method_lock or json.loads(METHOD_LOCK_PATH.read_text(encoding="utf-8"))
    sm = support_matrix or json.loads(SUPPORT_MATRIX_PATH.read_text(encoding="utf-8"))
    cat_map = catalog_support_map or build_independent_catalog_support_map(CATALOG_PATH)

    # 1. Top-level non-final / dry-run / boundary flags (QA-MUT-17, QA-MUT-18)
    if bundle_dict.get("run_mode") != "DRY_RUN":
        raise IndependentDryRunAuditError("RUN_MODE_INVALID", f"run_mode={bundle_dict.get('run_mode')!r}")
    if bundle_dict.get("fixture_label") != "SYNTHETIC_GENERATOR_QA":
        raise IndependentDryRunAuditError(
            "BUNDLE_FIXTURE_LABEL_INVALID", f"fixture_label={bundle_dict.get('fixture_label')!r}"
        )
    for flag_name in (
        "is_final_100_scenarios",
        "real_scenarios_generated",
        "p11_created",
        "preregistration_created",
        "gemini_called",
    ):
        if bundle_dict.get(flag_name) is not False:
            raise IndependentDryRunAuditError(
                "FINAL_OR_BOUNDARY_FLAG_VIOLATION",
                f"{flag_name} must be False, got {bundle_dict.get(flag_name)!r}",
            )

    if bundle_dict.get("seed") != EXPECTED_SEED:
        raise IndependentDryRunAuditError(
            "SEED_MISMATCH", f"seed={bundle_dict.get('seed')!r} != {EXPECTED_SEED}"
        )
    if bundle_dict.get("executable_priority_trace") != EXPECTED_PRIORITY_TRACE:
        raise IndependentDryRunAuditError(
            "PRIORITY_TRACE_MISMATCH",
            f"executable_priority_trace={bundle_dict.get('executable_priority_trace')!r}",
        )

    # 2. Slot count (QA-MUT-01)
    slots = bundle_dict.get("slots")
    if not isinstance(slots, list) or len(slots) != 100 or bundle_dict.get("slot_count") != 100:
        raise IndependentDryRunAuditError(
            "SLOT_COUNT_MISMATCH",
            f"Expected 100 slots and slot_count=100, got len={len(slots) if isinstance(slots, list) else None}, "
            f"slot_count={bundle_dict.get('slot_count')!r}",
        )

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
    win_start = datetime.date.fromisoformat(ml["date_policy"]["window_start_date"])
    win_end = datetime.date.fromisoformat(ml["date_policy"]["window_end_date"])
    repeat_caps = ml["near_duplicate_policy"]["repeat_caps_by_destination_and_interest_count"]

    seen_scenario_ids: Set[str] = set()
    seen_canonical_signatures: Set[Tuple[Any, ...]] = set()
    repeat_counter: Counter[Tuple[str, Tuple[str, ...]]] = Counter()

    rule_a_failures = 0
    rule_b_failures = 0
    excluded_used = 0

    for idx, slot in enumerate(slots, start=1):
        if slot.get("slot_index") != idx:
            raise IndependentDryRunAuditError(
                "SLOT_INDEX_INVALID", f"Expected slot_index={idx}, got {slot.get('slot_index')!r}"
            )
        scen_id = slot.get("scenario_id")
        if not isinstance(scen_id, str) or not scen_id:
            raise IndependentDryRunAuditError("SCENARIO_ID_MISSING", f"Invalid scenario_id at slot {idx}")
        if scen_id in seen_scenario_ids:
            raise IndependentDryRunAuditError(
                "DUPLICATE_SCENARIO_ID", f"Duplicate scenario_id {scen_id!r}"
            )
        seen_scenario_ids.add(scen_id)

        sc_in = slot.get("scenario_input")
        if not isinstance(sc_in, dict):
            raise IndependentDryRunAuditError("SCENARIO_INPUT_MISSING", f"Missing scenario_input at {scen_id}")

        if sc_in.get("scenario_id") != scen_id:
            raise IndependentDryRunAuditError(
                "SCENARIO_ID_MISMATCH", f"scenario_input.scenario_id mismatch on {scen_id}"
            )
        if sc_in.get("fixture_label") != "SYNTHETIC_GENERATOR_QA":
            raise IndependentDryRunAuditError(
                "FIXTURE_LABEL_INVALID",
                f"fixture_label={sc_in.get('fixture_label')!r} on {scen_id}",
            )
        if sc_in.get("allow_revisit_place_ids") is not False:
            raise IndependentDryRunAuditError(
                "ALLOW_REVISIT_INVALID",
                f"allow_revisit_place_ids={sc_in.get('allow_revisit_place_ids')!r} on {scen_id}",
            )

        dest = slot.get("destination_slug")
        if dest not in allowed_destinations or sc_in.get("destination_slug") != dest:
            raise IndependentDryRunAuditError("DESTINATION_INVALID", f"Invalid destination on {scen_id}")
        if slot.get("destination") != allowed_destinations[dest] or sc_in.get("destination") != allowed_destinations[dest]:
            raise IndependentDryRunAuditError("DESTINATION_DISPLAY_INVALID", f"Display mismatch on {scen_id}")

        days = slot.get("days")
        if days not in allowed_days or sc_in.get("days") != days:
            raise IndependentDryRunAuditError("DAYS_INVALID", f"Invalid days={days!r} on {scen_id}")

        k = slot.get("interest_count")
        interests = slot.get("interests")
        if k not in allowed_k or not isinstance(interests, list):
            raise IndependentDryRunAuditError(
                "INTEREST_COUNT_INVALID", f"Invalid interest_count={k!r} on {scen_id}"
            )
        if len(interests) != k or len(set(interests)) != k or sc_in.get("interests") != interests:
            raise IndependentDryRunAuditError(
                "INTEREST_COUNT_MISMATCH",
                f"interest_count={k} does not match interests={interests!r} on {scen_id}",
            )
        if interests != sorted(interests):
            raise IndependentDryRunAuditError(
                "INTERESTS_UNSORTED", f"Interests not sorted on {scen_id}: {interests!r}"
            )
        for intr in interests:
            if intr not in canonical_interests_set:
                raise IndependentDryRunAuditError(
                    "NON_CANONICAL_INTEREST", f"Non-canonical interest {intr!r} on {scen_id}"
                )

        # Budget check (QA-MUT-05)
        b_tier = slot.get("budget_tier_or_null")
        budget_val = slot.get("budget")
        if b_tier not in ("B1", "B2", "B3", None):
            raise IndependentDryRunAuditError(
                "BUDGET_TIER_INVALID", f"Invalid budget_tier_or_null={b_tier!r} on {scen_id}"
            )
        if b_tier is None:
            if budget_val is not None or sc_in.get("budget") is not None:
                raise IndependentDryRunAuditError(
                    "BUDGET_FORMULA_MISMATCH",
                    f"Expected budget=None for null tier on {scen_id}, got {budget_val!r}",
                )
        else:
            expected_budget = daily_nominal[b_tier] * days
            if budget_val != expected_budget or sc_in.get("budget") != expected_budget:
                raise IndependentDryRunAuditError(
                    "BUDGET_FORMULA_MISMATCH",
                    f"Expected budget={expected_budget} for {b_tier}*{days}d on {scen_id}, got {budget_val!r}",
                )
        if slot.get("currency") != "VND" or sc_in.get("currency") != "VND":
            raise IndependentDryRunAuditError("CURRENCY_INVALID", f"Invalid currency on {scen_id}")

        # Travel style check (QA-MUT-06)
        style = slot.get("travel_style")
        if style not in allowed_styles or sc_in.get("travel_style") != style:
            raise IndependentDryRunAuditError(
                "TRAVEL_STYLE_INVALID", f"Invalid travel_style={style!r} on {scen_id}"
            )

        # Dates and weekend exposure check (QA-MUT-07, QA-MUT-08, QA-MUT-09)
        s_str = slot.get("start_date")
        e_str = slot.get("end_date")
        if sc_in.get("start_date") != s_str or sc_in.get("end_date") != e_str:
            raise IndependentDryRunAuditError("DATE_INPUT_MISMATCH", f"Date mismatch on {scen_id}")
        try:
            s_dt = datetime.date.fromisoformat(s_str)
            e_dt = datetime.date.fromisoformat(e_str)
        except Exception as exc:
            raise IndependentDryRunAuditError("DATE_FORMAT_INVALID", f"Invalid date on {scen_id}") from exc

        if s_dt < win_start or e_dt > win_end:
            raise IndependentDryRunAuditError(
                "DATE_OUTSIDE_WINDOW",
                f"Dates {s_str}..{e_str} outside frozen window {win_start}..{win_end} on {scen_id}",
            )
        if (e_dt - s_dt).days + 1 != days:
            raise IndependentDryRunAuditError(
                "NON_CONTIGUOUS_DATES",
                f"Span {s_str}..{e_str} is {(e_dt - s_dt).days + 1}d, expected {days}d on {scen_id}",
            )
        trip_dates = [s_dt + datetime.timedelta(days=offset) for offset in range(days)]
        ind_weekend = any(dt.weekday() in (5, 6) for dt in trip_dates)
        if slot.get("weekend_exposure") is not ind_weekend or not isinstance(slot.get("weekend_exposure"), bool):
            raise IndependentDryRunAuditError(
                "WEEKEND_FLAG_INCONSISTENT",
                f"weekend_exposure={slot.get('weekend_exposure')!r} != {ind_weekend} for {s_str}..{e_str} on {scen_id}",
            )

        # Independent Rule A / Rule B / support_class recomputation (QA-MUT-11, QA-MUT-19, QA-MUT-20)
        ind_support = recompute_independent_rule_a_b(dest, days, interests, cat_map)
        if not ind_support["rule_a_passed"]:
            rule_a_failures += 1
        if not ind_support["rule_b_passed"]:
            rule_b_failures += 1
        if not ind_support["eligible"]:
            excluded_used += 1

        if slot.get("rule_a_passed") is not True or slot.get("rule_b_passed") is not True:
            raise IndependentDryRunAuditError(
                "RULE_A_B_FLAG_FALSE", f"rule_a_passed/rule_b_passed not True on {scen_id}"
            )
        if not ind_support["rule_a_passed"] or not ind_support["rule_b_passed"]:
            raise IndependentDryRunAuditError(
                "INDEPENDENT_RULE_A_B_FAILED",
                f"Independent recomputation failed Rule A/B on {scen_id}: {ind_support}",
            )

        matrix_combs = [
            c
            for c in sm["destinations"][dest]["by_days"][str(days)]["combinations"]
            if c["interests_sorted"] == interests
        ]
        if len(matrix_combs) != 1:
            raise IndependentDryRunAuditError(
                "MATRIX_COMBINATION_MISSING", f"Combination {interests} missing in support matrix on {scen_id}"
            )
        m_comb = matrix_combs[0]
        if not m_comb["eligible"] or m_comb["support_class"] == "EXCLUDED":
            raise IndependentDryRunAuditError(
                "EXCLUDED_COMBINATION_SELECTED", f"Selected EXCLUDED combination {interests} on {scen_id}"
            )
        if (
            slot.get("support_class") != ind_support["support_class"]
            or slot.get("support_class") != m_comb["support_class"]
            or slot.get("support_class") not in ("CLEAR", "STRESS")
        ):
            raise IndependentDryRunAuditError(
                "SUPPORT_CLASS_MISMATCH",
                f"support_class={slot.get('support_class')!r} != recomputed={ind_support['support_class']!r} "
                f"(matrix={m_comb['support_class']!r}) on {scen_id}",
            )
        if (
            slot.get("union_support") != ind_support["union_support"]
            or slot.get("sum_support") != ind_support["sum_support"]
            or slot.get("min_interest_support") != ind_support["min_interest_support"]
        ):
            raise IndependentDryRunAuditError(
                "SUPPORT_NUMERIC_MISMATCH",
                f"Support numbers on {scen_id} do not match independent recomputation",
            )

        # Independent Repeat-Cap check (QA-MUT-12)
        combo_key = (dest, tuple(interests))
        repeat_counter[combo_key] += 1
        cap_limit = int(repeat_caps[dest][str(k)]["repeat_cap"])
        if repeat_counter[combo_key] > cap_limit:
            raise IndependentDryRunAuditError(
                "REPEAT_CAP_EXCEEDED",
                f"Repeat cap exceeded for {combo_key}: {repeat_counter[combo_key]} > {cap_limit}",
            )

        # Independent Canonical Signature Duplicate check (QA-MUT-13)
        ind_sig_list = [dest, days, list(interests), b_tier, ind_weekend, style]
        if slot.get("canonical_signature") != ind_sig_list:
            raise IndependentDryRunAuditError(
                "CANONICAL_SIGNATURE_MISMATCH",
                f"canonical_signature={slot.get('canonical_signature')!r} != {ind_sig_list!r} on {scen_id}",
            )
        ind_sig_tuple = (dest, days, tuple(interests), b_tier, ind_weekend, style)
        if ind_sig_tuple in seen_canonical_signatures:
            raise IndependentDryRunAuditError(
                "DUPLICATE_CANONICAL_SIGNATURE",
                f"Duplicate canonical signature {ind_sig_list!r} on {scen_id}",
            )
        seen_canonical_signatures.add(ind_sig_tuple)

    # 3. Independent marginal and cross-table verification (QA-MUT-02, QA-MUT-03, QA-MUT-04, Section 15)
    ind_tables = recompute_independent_cross_tables(slots)
    ind_marginals = ind_tables["locked_marginal_counts"]

    if ind_marginals["destination"] != {"ha-noi": 34, "da-nang": 33, "ha-long": 33}:
        raise IndependentDryRunAuditError(
            "DESTINATION_MARGINAL_MISMATCH", f"destination counts={ind_marginals['destination']}"
        )
    if ind_marginals["days"] != {"2": 33, "3": 34, "4": 33}:
        raise IndependentDryRunAuditError(
            "DAYS_MARGINAL_MISMATCH", f"days counts={ind_marginals['days']}"
        )
    if ind_tables["destination_by_days"] != ml["destination_days_cross_allocation"]:
        raise IndependentDryRunAuditError(
            "DESTINATION_DAYS_MATRIX_MISMATCH",
            f"destination_by_days={ind_tables['destination_by_days']}",
        )
    if ind_marginals["interest_count"] != {"1": 33, "2": 34, "3": 33}:
        raise IndependentDryRunAuditError(
            "INTEREST_COUNT_MARGINAL_MISMATCH",
            f"interest_count counts={ind_marginals['interest_count']}",
        )
    if ind_tables["destination_by_interest_count"] != ml["destination_interest_count_cross_allocation"]:
        raise IndependentDryRunAuditError(
            "DESTINATION_INTEREST_COUNT_MATRIX_MISMATCH",
            f"destination_by_interest_count={ind_tables['destination_by_interest_count']}",
        )
    if ind_marginals["budget"] != {"B1": 27, "B2": 27, "B3": 26, "null": 20}:
        raise IndependentDryRunAuditError(
            "BUDGET_MARGINAL_MISMATCH", f"budget counts={ind_marginals['budget']}"
        )
    if ind_marginals["travel_style"] != {
        "BACKPACKER": 25,
        "BUDGET": 25,
        "COMFORT": 25,
        "LUXURY": 25,
    }:
        raise IndependentDryRunAuditError(
            "TRAVEL_STYLE_MARGINAL_MISMATCH", f"travel_style counts={ind_marginals['travel_style']}"
        )
    if ind_marginals["weekend_exposure"] != {
        "weekend_exposed": 50,
        "non_weekend_exposed": 50,
    }:
        raise IndependentDryRunAuditError(
            "WEEKEND_MARGINAL_MISMATCH", f"weekend counts={ind_marginals['weekend_exposure']}"
        )

    # Compare independent cross-balance tables against generator CrossBalanceReport
    gen_cb = bundle_dict.get("cross_balance_report", {})
    for table_key in (
        "locked_marginal_counts",
        "destination_by_days",
        "destination_by_interest_count",
        "destination_by_budget",
        "destination_by_style",
        "destination_by_weekend",
        "days_by_interest_count",
        "days_by_budget",
        "days_by_style",
        "interest_count_by_budget",
        "interest_count_by_style",
        "support_class_counts",
        "support_class_by_destination",
        "max_min_cross_cell_imbalance",
    ):
        if gen_cb.get(table_key) != ind_tables[table_key]:
            raise IndependentDryRunAuditError(
                "CROSS_BALANCE_REPORT_MISMATCH",
                f"CrossBalanceReport.{table_key} mismatch: {gen_cb.get(table_key)} != {ind_tables[table_key]}",
            )

    # 4. Independent Rejection Log Audit (Section 13)
    rej_log = bundle_dict.get("rejection_log")
    rej_count = bundle_dict.get("rejection_log_count")
    rej_reason_counts = bundle_dict.get("rejection_reason_counts")
    allowed_reasons = set(ml["rejection_log_policy"]["allowed_reason_codes"])

    if not isinstance(rej_log, list) or rej_count != len(rej_log):
        raise IndependentDryRunAuditError(
            "REJECTION_LOG_COUNT_MISMATCH",
            f"rejection_log_count={rej_count} != len(rejection_log)={len(rej_log) if isinstance(rej_log, list) else None}",
        )
    if not isinstance(rej_reason_counts, dict) or sum(rej_reason_counts.values()) != rej_count:
        raise IndependentDryRunAuditError(
            "REJECTION_REASON_SUM_MISMATCH",
            f"sum(rejection_reason_counts) != {rej_count}",
        )

    accepted_candidate_indices = {s["candidate_index"] for s in slots}
    recomputed_reason_counter: Counter[str] = Counter()
    for entry in rej_log:
        if not isinstance(entry, dict):
            raise IndependentDryRunAuditError("REJECTION_ENTRY_INVALID", "Non-dict rejection entry")
        forbidden_present = FORBIDDEN_REJECTION_KEYS.intersection(entry.keys())
        if forbidden_present:
            raise IndependentDryRunAuditError(
                "FORBIDDEN_REJECTION_FIELD",
                f"Forbidden keys {sorted(forbidden_present)} in rejection log entry",
            )
        r_code = entry.get("reason_code")
        if r_code not in allowed_reasons:
            raise IndependentDryRunAuditError(
                "INVALID_REJECTION_REASON_CODE", f"Disallowed reason_code={r_code!r}"
            )
        recomputed_reason_counter[r_code] += 1
        rep_idx = entry.get("replacement_candidate_index")
        if rep_idx is None or not isinstance(rep_idx, int) or rep_idx <= entry.get("candidate_index", 0):
            raise IndependentDryRunAuditError(
                "INVALID_REPLACEMENT_CANDIDATE_INDEX",
                f"Invalid replacement_candidate_index={rep_idx!r} for candidate {entry.get('candidate_index')!r}",
            )
        if rep_idx not in accepted_candidate_indices:
            raise IndependentDryRunAuditError(
                "UNLINKED_REPLACEMENT_CANDIDATE_INDEX",
                f"replacement_candidate_index={rep_idx} is not an accepted slot candidate_index",
            )

    if dict(sorted(recomputed_reason_counter.items())) != dict(sorted(rej_reason_counts.items())):
        raise IndependentDryRunAuditError(
            "REJECTION_REASON_COUNTS_MISMATCH",
            f"Recomputed {dict(recomputed_reason_counter)} != {rej_reason_counts}",
        )

    return {
        "audit_status": "PASS",
        "slot_count": 100,
        "unique_canonical_signatures": len(seen_canonical_signatures),
        "duplicate_canonical_signatures": 0,
        "repeat_cap_violations": 0,
        "rule_a_failures": rule_a_failures,
        "rule_b_failures": rule_b_failures,
        "excluded_combinations_used": excluded_used,
        "rejection_log_count": rej_count,
        "rejection_reason_counts": dict(sorted(recomputed_reason_counter.items())),
        "independent_cross_tables": ind_tables,
    }


def run_fresh_process_dryrun(python_hash_seed: Optional[str] = None) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
    """Execute the public dry-run CLI in a fresh Python subprocess using a temporary file.

    Validates both CLI stdout summary and the full bundle written to the temporary file,
    which is automatically deleted when the TemporaryDirectory context exits.
    """
    import tempfile

    env = dict(os.environ)
    if python_hash_seed is not None:
        env["PYTHONHASHSEED"] = str(python_hash_seed)

    with tempfile.TemporaryDirectory(prefix="w06_qa_dryrun_") as tmp_dir:
        tmp_bundle_path = Path(tmp_dir) / "dryrun_qa_output.json"
        proc = subprocess.run(
            [
                sys.executable,
                str(DRYRUN_CLI_PATH),
                "--output-json",
                str(tmp_bundle_path),
            ],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
        stdout_summary = json.loads(proc.stdout)
        raw_bundle_bytes = tmp_bundle_path.read_bytes()
        bundle_dict = json.loads(raw_bundle_bytes.decode("utf-8"))

    canonical_bytes = independent_canonical_json_bytes(bundle_dict)
    if raw_bundle_bytes != canonical_bytes:
        raise IndependentDryRunAuditError(
            "NON_CANONICAL_BUNDLE_BYTES",
            "CLI --output-json bytes are not canonical UTF-8 LF JSON.",
        )
    bundle_sha = hashlib.sha256(raw_bundle_bytes).hexdigest()
    if stdout_summary.get("bundle_sha256") != bundle_sha:
        raise IndependentDryRunAuditError(
            "CLI_STDOUT_SHA_MISMATCH",
            f"CLI stdout bundle_sha256={stdout_summary.get('bundle_sha256')!r} != {bundle_sha!r}",
        )
    if stdout_summary.get("run_mode") != "DRY_RUN" or stdout_summary.get("slot_count") != 100:
        raise IndependentDryRunAuditError(
            "CLI_STDOUT_SUMMARY_INVALID",
            f"Invalid CLI stdout summary: {stdout_summary}",
        )
    return bundle_sha, stdout_summary, bundle_dict


def run_fresh_process_dryrun_sha(python_hash_seed: Optional[str] = None) -> str:
    """Return canonical bundle SHA256 from a fresh subprocess execution of the public dry-run CLI."""
    sha, _, _ = run_fresh_process_dryrun(python_hash_seed)
    return sha


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Independent adversarial QA verifier for W06-SCENARIO-GENERATOR-01."
    )
    parser.add_argument(
        "--check-fresh-processes",
        action="store_true",
        help="Also run fresh-process PYTHONHASHSEED={normal,0,1,42} determinism checks.",
    )
    args = parser.parse_args(argv)

    observed_sha, stdout_summary, bundle_dict = run_fresh_process_dryrun(None)
    if observed_sha != EXPECTED_DRY_RUN_SHA256:
        raise IndependentDryRunAuditError(
            "DRY_RUN_SHA_MISMATCH",
            f"Observed dry-run SHA {observed_sha} != {EXPECTED_DRY_RUN_SHA256}",
        )

    audit_result = audit_dry_run_bundle_independently(bundle_dict)
    summary: Dict[str, Any] = {
        "audit_status": audit_result["audit_status"],
        "cli_stdout_bundle_sha256": stdout_summary["bundle_sha256"],
        "dry_run_sha256": observed_sha,
        "slot_count": audit_result["slot_count"],
        "unique_canonical_signatures": audit_result["unique_canonical_signatures"],
        "duplicate_canonical_signatures": audit_result["duplicate_canonical_signatures"],
        "repeat_cap_violations": audit_result["repeat_cap_violations"],
        "rule_a_failures": audit_result["rule_a_failures"],
        "rule_b_failures": audit_result["rule_b_failures"],
        "excluded_combinations_used": audit_result["excluded_combinations_used"],
        "rejection_log_count": audit_result["rejection_log_count"],
        "rejection_reason_counts": audit_result["rejection_reason_counts"],
    }

    if args.check_fresh_processes:
        summary["fresh_process_shas"] = {
            "normal": observed_sha,
            "PYTHONHASHSEED_0": run_fresh_process_dryrun_sha("0"),
            "PYTHONHASHSEED_1": run_fresh_process_dryrun_sha("1"),
            "PYTHONHASHSEED_42": run_fresh_process_dryrun_sha("42"),
        }

    sys.stdout.write(json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
