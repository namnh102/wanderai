"""Deterministic evaluator for AI Trip Planner test cases."""
import json
from pathlib import Path


def evaluate_itinerary(response_data: dict, scenario_spec: dict) -> dict:
    """Evaluates whether an itinerary response satisfies scenario constraints."""
    constraints = scenario_spec.get("expected_constraints", {})
    days = response_data.get("days", [])
    total_days = len(days)

    passed_checks = []
    failed_checks = []

    # 1. Day count check
    min_days = constraints.get("min_days", 1)
    max_days = constraints.get("max_days", 14)
    if min_days <= total_days <= max_days:
        passed_checks.append(f"Day count {total_days} satisfies [{min_days}, {max_days}]")
    else:
        failed_checks.append(f"Day count {total_days} outside [{min_days}, {max_days}]")

    # 2. Arithmetic integrity check
    reported_total = response_data.get("budget_analysis", {}).get("estimated_cost", 0)
    calculated_total = 0
    all_activities_text = ""

    for d in days:
        day_cost = d.get("day_cost", 0)
        items = d.get("items", [])
        computed_day_cost = sum(i.get("estimated_cost", 0) for i in items)
        calculated_total += computed_day_cost

        if computed_day_cost != day_cost:
            failed_checks.append(
                f"Day {d.get('day_number')} day_cost {day_cost} != sum of items {computed_day_cost}"
            )
        
        min_items = constraints.get("min_items_per_day", 1)
        if len(items) < min_items:
            failed_checks.append(
                f"Day {d.get('day_number')} has {len(items)} items < min required {min_items}"
            )

        for itm in items:
            all_activities_text += f" {itm.get('activity', '')} {itm.get('place_name', '')}"

    if calculated_total == reported_total:
        passed_checks.append(f"Arithmetic integrity verified: {calculated_total} == {reported_total}")
    else:
        failed_checks.append(
            f"Arithmetic mismatch: reported {reported_total} != calculated {calculated_total}"
        )

    # 3. Required keywords check (soft check)
    req_keywords = constraints.get("required_keywords", [])
    matched_keywords = [kw for kw in req_keywords if kw.lower() in all_activities_text.lower()]
    passed_checks.append(f"Matched {len(matched_keywords)}/{len(req_keywords)} keywords: {matched_keywords}")

    return {
        "scenario_id": scenario_spec.get("scenario_id"),
        "success": len(failed_checks) == 0,
        "passed_checks": passed_checks,
        "failed_checks": failed_checks,
        "calculated_total": calculated_total,
    }


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    planner_dir = Path(__file__).parent
    scenarios = list(planner_dir.glob("*.json"))
    print(f"Found {len(scenarios)} evaluation scenarios in {planner_dir}")
    for sc in scenarios:
        with open(sc, "r", encoding="utf-8") as f:
            data = json.load(f)
            print(f"- {data.get('scenario_id')}: {data.get('name')}")
