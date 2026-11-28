"""C4 product itinerary evaluator supporting nullable (unknown) and zero (free) item costs.

Keeps locked W06 legacy `data/evaluation/planner/evaluate_planner.py` untouched while verifying
C4 budget & schedule invariants across `estimated_cost = None` (unknown) and `estimated_cost = 0` (free).
"""
from typing import Optional


def _extract_item_cost(item: dict) -> Optional[int]:
    if "estimated_cost" not in item:
        return None
    raw = item.get("estimated_cost")
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw
    return None


def evaluate_c4_itinerary(response_data: dict, scenario_spec: dict) -> dict:
    """Evaluate a C4 PlanResponse payload with explicit unknown-price (`None`) vs free (`0`) rules."""
    constraints = scenario_spec.get("expected_constraints", {})
    days = response_data.get("days", [])
    total_days = len(days)

    passed_checks: list[str] = []
    failed_checks: list[str] = []

    min_days = constraints.get("min_days", 1)
    max_days = constraints.get("max_days", 14)
    if min_days <= total_days <= max_days:
        passed_checks.append(f"Day count {total_days} satisfies [{min_days}, {max_days}]")
    else:
        failed_checks.append(f"Day count {total_days} outside [{min_days}, {max_days}]")

    ba = response_data.get("budget_analysis", {})
    reported_estimated = ba.get("estimated_cost", 0)
    reported_known = ba.get("known_cost_total", reported_estimated)
    reported_unknown_count = ba.get("unknown_cost_item_count", 0)
    reported_cost_status = ba.get("cost_status", "COMPLETE")
    reported_has_basis = ba.get("has_sufficient_budget_basis", False)
    reported_is_over = ba.get("is_over_budget", False)
    reported_variance = ba.get("variance")
    total_budget = ba.get("total_budget")

    calculated_known_total = 0
    calculated_unknown_count = 0
    total_items_count = 0
    all_activities_text = ""

    for d in days:
        day_num = d.get("day_number")
        day_cost = d.get("day_cost", 0)
        day_unknown_reported = d.get("unknown_cost_item_count", 0)
        items = d.get("items", [])

        computed_day_known = 0
        computed_day_unknown = 0
        for itm in items:
            total_items_count += 1
            c = _extract_item_cost(itm)
            if c is None:
                computed_day_unknown += 1
                if itm.get("cost_status", "UNKNOWN") != "UNKNOWN":
                    failed_checks.append(
                        f"Day {day_num} item cost=None must have cost_status=UNKNOWN"
                    )
            else:
                if c < 0:
                    failed_checks.append(f"Day {day_num} item has negative cost {c}")
                computed_day_known += c
                if "cost_status" in itm and itm.get("cost_status") != "KNOWN":
                    failed_checks.append(
                        f"Day {day_num} item cost={c} must have cost_status=KNOWN"
                    )
            all_activities_text += f" {itm.get('activity', '')} {itm.get('place_name', '')}"

        calculated_known_total += computed_day_known
        calculated_unknown_count += computed_day_unknown

        if computed_day_known != day_cost:
            failed_checks.append(
                f"Day {day_num} day_cost {day_cost} != sum of known items {computed_day_known}"
            )
        if computed_day_unknown != day_unknown_reported:
            failed_checks.append(
                f"Day {day_num} unknown_cost_item_count {day_unknown_reported} != {computed_day_unknown}"
            )

        min_items = constraints.get("min_items_per_day", 1)
        if len(items) < min_items:
            failed_checks.append(
                f"Day {day_num} has {len(items)} items < min required {min_items}"
            )

    if calculated_known_total == reported_estimated == reported_known:
        passed_checks.append(f"Known cost total verified: {calculated_known_total}")
    else:
        failed_checks.append(
            f"Known cost mismatch: calc={calculated_known_total}, "
            f"estimated_cost={reported_estimated}, known_cost_total={reported_known}"
        )

    if calculated_unknown_count == reported_unknown_count:
        passed_checks.append(f"Unknown item count verified: {calculated_unknown_count}")
    else:
        failed_checks.append(
            f"Unknown count mismatch: calc={calculated_unknown_count} != reported={reported_unknown_count}"
        )

    if calculated_unknown_count == 0:
        expected_status = "COMPLETE"
    elif calculated_unknown_count == total_items_count:
        expected_status = "ALL_UNKNOWN"
    else:
        expected_status = "PARTIAL_UNKNOWN"

    if reported_cost_status != expected_status:
        failed_checks.append(
            f"cost_status {reported_cost_status} != expected {expected_status}"
        )

    has_positive_budget = isinstance(total_budget, int) and total_budget > 0
    expected_over = bool(has_positive_budget and calculated_known_total > total_budget)
    expected_basis = bool(has_positive_budget and calculated_unknown_count == 0)
    if has_positive_budget:
        expected_variance = (
            total_budget - calculated_known_total
            if (expected_over or expected_basis)
            else None
        )
    else:
        expected_variance = 0 if calculated_unknown_count == 0 else None

    if reported_is_over != expected_over:
        failed_checks.append(f"is_over_budget {reported_is_over} != expected {expected_over}")
    if reported_has_basis != expected_basis:
        failed_checks.append(
            f"has_sufficient_budget_basis {reported_has_basis} != expected {expected_basis}"
        )
    if reported_variance != expected_variance:
        failed_checks.append(f"variance {reported_variance} != expected {expected_variance}")

    req_keywords = constraints.get("required_keywords", [])
    matched_keywords = [kw for kw in req_keywords if kw.lower() in all_activities_text.lower()]
    passed_checks.append(
        f"Matched {len(matched_keywords)}/{len(req_keywords)} keywords: {matched_keywords}"
    )

    return {
        "scenario_id": scenario_spec.get("scenario_id"),
        "success": len(failed_checks) == 0,
        "passed_checks": passed_checks,
        "failed_checks": failed_checks,
        "calculated_known_total": calculated_known_total,
        "calculated_unknown_count": calculated_unknown_count,
        "cost_status": expected_status,
    }
