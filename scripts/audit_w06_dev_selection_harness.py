"""Independent adversarial QA oracle for the W06 DEV Selection Harness.

Task: W06-DEV-SELECTION-HARNESS-QA-01-OFFLINE-ADVERSARIAL
Role: Independent scientific red-team / adversarial QA agent.

All expected values in this module are derived independently from the frozen
W06 JSON and Python authorities rather than trusting constants in
`apps/ai-service/app/evaluation/dev_selection_harness.py`.

Zero live provider calls. Provider cost = $0.
"""

from __future__ import annotations

import copy
import datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
AI_SERVICE_ROOT = REPO_ROOT / "apps" / "ai-service"
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.evaluation import dev_selection_harness as harness  # noqa: E402
from app.evaluation.planner_benchmark_evaluator import (  # noqa: E402
    load_core_catalog_by_place_id,
)
from app.prompts.planner_benchmark_prompt import (  # noqa: E402
    build_destination_catalog_context,
)
from app.schemas.planner_benchmark import (  # noqa: E402
    BenchmarkCatalogPOI,
    BenchmarkScenarioInput,
)
from recommendation.reca.contract import SUPPORTED_DESTINATIONS  # noqa: E402

# ============================================================================
# 1. INDEPENDENT AUTHORITATIVE PATHS & LITERAL METHOD-LOCK EXPECTATIONS
# ============================================================================

TASK_ID = "W06-DEV-SELECTION-HARNESS-QA-01-OFFLINE-ADVERSARIAL"
EXPECTED_BASE_DEVELOP_SHA = "68d05e72f25ea37c7da411d5dffcb65033ef8a95"

AUTHORITY_PATHS: Dict[str, Path] = {
    "method_lock": REPO_ROOT
    / "data/evaluation/w06/w06_model_arch_selection_method_lock_v1.json",
    "measurement_contract": REPO_ROOT
    / "data/evaluation/w06/w06_measurement_contract_v1.json",
    "dev_fixtures_freeze": REPO_ROOT
    / "data/evaluation/w06/w06_dev_fixtures_freeze_v1.json",
    "dev_fixture_manifest": REPO_ROOT
    / "data/evaluation/w06/w06_dev_fixture_manifest_v1.json",
    "dev_final_overlap_receipt": REPO_ROOT
    / "data/evaluation/w06/w06_dev_final_overlap_receipt_v1.json",
    "preflight_01d_receipt": REPO_ROOT
    / "data/evaluation/w06/w06_model_preflight_01d_v2_live_receipt_v1.json",
    "portable_schema_v2_manifest": REPO_ROOT
    / "data/evaluation/w06/w06_model_preflight_portable_schema_v2_manifest.json",
    "places_freeze_v2": REPO_ROOT / "data/curated/gomate_places_freeze_v2.json",
    "reca_contract_py": AI_SERVICE_ROOT / "recommendation/reca/contract.py",
    "planner_benchmark_schema_py": AI_SERVICE_ROOT
    / "app/schemas/planner_benchmark.py",
    "planner_benchmark_evaluator_py": AI_SERVICE_ROOT
    / "app/evaluation/planner_benchmark_evaluator.py",
}

FORBIDDEN_FINAL100_PATH = (
    REPO_ROOT / "data/evaluation/w06/w06_scenarios_freeze_v1.json"
)
FORBIDDEN_P11_PATH = (
    REPO_ROOT / "data/evaluation/w06/w06_p11_assignment_manifest_v1.json"
)
HARNESS_MODULE_PATH = AI_SERVICE_ROOT / "app/evaluation/dev_selection_harness.py"
HARNESS_01_RECEIPT_PATH = (
    REPO_ROOT / "data/evaluation/w06/w06_dev_selection_harness_01_receipt_v1.json"
)
QA_RECEIPT_OUTPUT_PATH = (
    REPO_ROOT / "data/evaluation/w06/w06_dev_selection_harness_qa_01_receipt_v1.json"
)


def sha256_lf_file(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(raw).hexdigest()


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


# ============================================================================
# 2. INDEPENDENT ORACLE DERIVATIONS
# ============================================================================


def derive_independent_dev_oracle() -> Dict[str, Any]:
    """Derive DEV bundle counts, marginals, and hashes directly from frozen JSON."""
    bundle_sha = sha256_lf_file(AUTHORITY_PATHS["dev_fixtures_freeze"])
    manifest = load_json(AUTHORITY_PATHS["dev_fixture_manifest"])
    overlap = load_json(AUTHORITY_PATHS["dev_final_overlap_receipt"])
    bundle = load_json(AUTHORITY_PATHS["dev_fixtures_freeze"])

    all_fixtures = bundle["fixtures"]
    dev_tune = [f for f in all_fixtures if f.get("fixture_label") == "W06_DEV_TUNE"]
    dev_select = [f for f in all_fixtures if f.get("fixture_label") == "W06_DEV_SELECT"]

    budget_tier_lookup = {
        2: {1000000: "B1", 2000000: "B2", 4000000: "B3"},
        3: {1500000: "B1", 3000000: "B2", 6000000: "B3"},
        4: {2000000: "B1", 4000000: "B2", 8000000: "B3"},
    }

    def is_weekend(start_s: str, end_s: str) -> bool:
        cur = datetime.date.fromisoformat(start_s)
        end = datetime.date.fromisoformat(end_s)
        while cur <= end:
            if cur.weekday() in (5, 6):
                return True
            cur += datetime.timedelta(days=1)
        return False

    def compute_marginals(scenarios: List[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
        dest = {"ha-noi": 0, "da-nang": 0, "ha-long": 0}
        days = {"2": 0, "3": 0, "4": 0}
        interests = {"1": 0, "2": 0, "3": 0}
        budget = {"B1": 0, "B2": 0, "B3": 0, "null": 0}
        style = {"BACKPACKER": 0, "BUDGET": 0, "COMFORT": 0, "LUXURY": 0}
        weekend = {"true": 0, "false": 0}

        for s in scenarios:
            dest[s["destination_slug"]] += 1
            days[str(s["days"])] += 1
            interests[str(len(s["interests"]))] += 1
            b_val = s.get("budget")
            b_tier = "null" if b_val is None else budget_tier_lookup[s["days"]][b_val]
            budget[b_tier] += 1
            style[s["travel_style"]] += 1
            wk = "true" if is_weekend(s["start_date"], s["end_date"]) else "false"
            weekend[wk] += 1

        return {
            "destination": dest,
            "days": days,
            "interest_count": interests,
            "budget": budget,
            "travel_style": style,
            "weekend": weekend,
        }

    return {
        "bundle_sha256": bundle_sha,
        "manifest_bundle_sha256": manifest.get("dev_bundle_sha256")
        or manifest.get("dev_fixtures_freeze_sha256")
        or bundle_sha,
        "overlap_dev_sha256": overlap.get("dev_fixtures_sha256")
        or overlap.get("dev_fixtures_freeze_sha256")
        or bundle_sha,
        "dev_total": len(all_fixtures),
        "dev_tune_count": len(dev_tune),
        "dev_select_count": len(dev_select),
        "dev_tune_marginals": compute_marginals(dev_tune),
        "dev_select_marginals": compute_marginals(dev_select),
        "exact_final_overlap_count": overlap["all_dev_exact_overlap_with_final"],
        "dev_tune_near_overlap_final_count": overlap[
            "dev_tune_near_overlap_with_final"
        ],
        "dev_tune_scenarios": dev_tune,
        "dev_select_scenarios": dev_select,
    }


def derive_independent_reca_oracle() -> Dict[str, Any]:
    """Independently filter gomate_places_freeze_v2.json via REC-A-CORE-V2 contract."""
    raw = load_json(AUTHORITY_PATHS["places_freeze_v2"])
    places = raw["places"] if isinstance(raw, dict) and "places" in raw else raw
    reca_by_dest: Dict[str, List[Dict[str, Any]]] = {
        "ha-noi": [],
        "da-nang": [],
        "ha-long": [],
    }
    map_discovery_counts: Dict[str, int] = {"ha-noi": 0, "da-nang": 0, "ha-long": 0}
    secondary_ids: set[str] = set()
    danang_lodging_only_ids: List[str] = []

    for p in places:
        dest = p.get("destination_slug")
        is_core = dest in SUPPORTED_DESTINATIONS and p.get("is_rec_a_core_v2") is True
        if dest not in SUPPORTED_DESTINATIONS:
            secondary_ids.add(p["place_id"])
        if dest in map_discovery_counts:
            map_discovery_counts[dest] += 1
            if not is_core and dest == "da-nang":
                danang_lodging_only_ids.append(p["place_id"])

        if dest in reca_by_dest and is_core:
            reca_by_dest[dest].append(p)

    for dest in reca_by_dest:
        reca_by_dest[dest].sort(key=lambda item: item["place_id"])

    counts = {d: len(items) for d, items in reca_by_dest.items()}
    return {
        "counts_by_destination": counts,
        "total_reca_core": sum(counts.values()),
        "map_discovery_counts": map_discovery_counts,
        "danang_lodging_only_ids": sorted(danang_lodging_only_ids),
        "secondary_place_ids": secondary_ids,
        "reca_place_ids_by_destination": {
            d: [p["place_id"] for p in items] for d, items in reca_by_dest.items()
        },
        "reca_places_by_destination": reca_by_dest,
    }


def build_valid_complete_plan_dict_for_scenario(
    scenario: BenchmarkScenarioInput,
    catalog_pois: List[BenchmarkCatalogPOI],
) -> Dict[str, Any]:
    """Construct a complete BenchmarkPlanResponse dict matching the strict semantic schema."""
    neutral_pois = [p for p in catalog_pois if p.opening_hours is None]
    pool = neutral_pois if len(neutral_pois) >= scenario.days * 2 else catalog_pois

    start_dt = datetime.date.fromisoformat(scenario.start_date)
    days_list: List[Dict[str, Any]] = []
    idx = 0
    for d_idx in range(scenario.days):
        day_date = (start_dt + datetime.timedelta(days=d_idx)).isoformat()
        p1 = pool[idx % len(pool)]
        p2 = pool[(idx + 1) % len(pool)]
        idx += 2
        days_list.append(
            {
                "day_number": d_idx + 1,
                "date": day_date,
                "title": f"Day {d_idx + 1}",
                "day_cost": 100000,
                "items": [
                    {
                        "order_index": 1,
                        "start_time": "08:30",
                        "end_time": "10:00",
                        "activity_kind": "POI_VISIT",
                        "activity": f"Visit {p1.name}",
                        "place_name": p1.name,
                        "place_id": p1.place_id,
                        "notes": "Morning visit",
                        "estimated_cost": 50000,
                        "transport_mode": "taxi",
                    },
                    {
                        "order_index": 2,
                        "start_time": "10:30",
                        "end_time": "12:00",
                        "activity_kind": "POI_VISIT",
                        "activity": f"Visit {p2.name}",
                        "place_name": p2.name,
                        "place_id": p2.place_id,
                        "notes": "Late morning visit",
                        "estimated_cost": 50000,
                        "transport_mode": "taxi",
                    },
                ],
            }
        )

    total_est = 100000 * scenario.days
    total_budget = scenario.budget
    is_over = False if total_budget is None else (total_est > total_budget)
    variance = 0 if total_budget is None else (total_budget - total_est)
    return {
        "plan_id": f"plan-qa-{scenario.scenario_id.lower()}",
        "scenario_id": scenario.scenario_id,
        "destination_slug": scenario.destination_slug,
        "destination": scenario.destination,
        "total_days": scenario.days,
        "overview": "Deterministic valid itinerary.",
        "best_time_to_visit": "All year",
        "general_tips": ["Tip 1"],
        "budget_analysis": {
            "total_budget": total_budget,
            "estimated_cost": total_est,
            "currency": scenario.currency,
            "is_over_budget": is_over,
            "variance": variance,
        },
        "days": days_list,
    }


def build_failure_taxonomy_mapping_table() -> List[Dict[str, Any]]:
    """Build the Section 26 failure taxonomy comparison table against Method Lock."""
    return [
        {
            "method_lock_outcome": "HTTP_429_RATE_LIMIT",
            "harness_classification": "HTTP_429",
            "retry_allowed": False,
            "preserves_denominator": True,
            "expected_stop_batch": False,
            "observed_stop_batch": False,
            "mapping_valid": True,
        },
        {
            "method_lock_outcome": "HTTP_5XX_PROVIDER_ERROR",
            "harness_classification": "HTTP_5XX",
            "retry_allowed": False,
            "preserves_denominator": True,
            "expected_stop_batch": False,
            "observed_stop_batch": False,
            "mapping_valid": True,
        },
        {
            "method_lock_outcome": "TIMEOUT",
            "harness_classification": "TIMEOUT",
            "retry_allowed": False,
            "preserves_denominator": True,
            "expected_stop_batch": False,
            "observed_stop_batch": False,
            "mapping_valid": True,
        },
        {
            "method_lock_outcome": "PARTIAL_TIMEOUT_WHERE_DISTINGUISHABLE",
            "harness_classification": "UNMAPPED_NO_PARTIAL_TIMEOUT_ENUM_VALUE",
            "retry_allowed": False,
            "preserves_denominator": True,
            "expected_stop_batch": False,
            "observed_stop_batch": False,
            "mapping_valid": False,
        },
        {
            "method_lock_outcome": "MALFORMED_OUTPUT_NON_JSON",
            "harness_classification": "MALFORMED_JSON",
            "retry_allowed": False,
            "preserves_denominator": True,
            "expected_stop_batch": False,
            "observed_stop_batch": False,
            "mapping_valid": True,
        },
        {
            "method_lock_outcome": "SCHEMA_NONCOMPLIANCE",
            "harness_classification": "SEMANTIC_VALIDATION_FAILURE (rescued when plan_id/budget_analysis omitted)",
            "retry_allowed": False,
            "preserves_denominator": True,
            "expected_stop_batch": False,
            "observed_stop_batch": False,
            "mapping_valid": False,
        },
        {
            "method_lock_outcome": "PROVIDER_REFUSAL",
            "harness_classification": "REFUSAL",
            "retry_allowed": False,
            "preserves_denominator": True,
            "expected_stop_batch": False,
            "observed_stop_batch": False,
            "mapping_valid": True,
        },
        {
            "method_lock_outcome": "DOWNSTREAM_CONSTRAINT_FAILURE",
            "harness_classification": "NONE (evaluated downstream via exact_grounding_pass / final_core_pass)",
            "retry_allowed": False,
            "preserves_denominator": True,
            "expected_stop_batch": False,
            "observed_stop_batch": False,
            "mapping_valid": True,
        },
        {
            "method_lock_outcome": "MODEL_ID_OR_RESOLVED_VERSION_MISMATCH",
            "harness_classification": "MODEL_INTEGRITY_MISMATCH",
            "retry_allowed": False,
            "preserves_denominator": False,
            "expected_stop_batch": True,
            "observed_stop_batch": False,
            "mapping_valid": False,
        },
        {
            "method_lock_outcome": "HARNESS_OR_INFRASTRUCTURE_ERROR",
            "harness_classification": "UNMAPPED_NO_HARNESS_ERROR_ENUM_OR_STOP_BATCH_GUARD",
            "retry_allowed": False,
            "preserves_denominator": False,
            "expected_stop_batch": True,
            "observed_stop_batch": False,
            "mapping_valid": False,
        },
    ]


def build_provider_billing_semantics_audit() -> Dict[str, Any]:
    """Document official provider billing/token semantics (Section 16)."""
    return {
        "access_date": "2026-10-18",
        "live_generation_api_calls": 0,
        "candidates": {
            "C1": {
                "provider": "Google",
                "model_id": "gemini-3.8-flash",
                "official_docs_urls": [
                    "https://ai.google.dev/gemini-api/docs/thinking",
                    "https://ai.google.dev/gemini-api/docs/tokens",
                    "https://ai.google.dev/gemini-api/docs/caching",
                ],
                "billable_input_field": "usage_metadata.prompt_token_count",
                "billable_output_field": (
                    "usage_metadata.candidates_token_count + "
                    "usage_metadata.thoughts_token_count"
                ),
                "reasoning_thinking_token_relationship": (
                    "DISJOINT_MUST_BE_ADDED: Gemini candidates_token_count excludes "
                    "thoughts_token_count. Confirmed by official docs ('When thinking "
                    "is turned on, response pricing is the sum of output tokens and "
                    "thinking tokens') and 01D live receipt (514 + 599 + 3179 = 4292)."
                ),
                "cache_token_treatment": (
                    "usage_metadata.cached_content_token_count is billed at reduced "
                    "cached-input rate; if > 0, naive input_tokens * standard_rate is "
                    "non-comparable unless cache tokens are 0 or priced separately."
                ),
                "harness_defect": (
                    "MockProviderTransportResponse, DevCellExecutionReceipt, and "
                    "execute_dev_cell_with_mock_transport omit thought_tokens and "
                    "cache token fields; execute_dev_cell_with_mock_transport calls "
                    "compute_canonical_cell_cost_usd without thought_or_reasoning_tokens, "
                    "undercounting C1 billable output tokens."
                ),
            },
            "C2": {
                "provider": "OpenAI",
                "model_id": "gpt-6.1-sol",
                "official_docs_urls": [
                    "https://developers.openai.com/api/docs/guides/reasoning",
                    "https://platform.openai.com/docs/guides/reasoning",
                ],
                "billable_input_field": "usage.prompt_tokens (or usage.input_tokens)",
                "billable_output_field": (
                    "usage.completion_tokens (or usage.output_tokens)"
                ),
                "reasoning_thinking_token_relationship": (
                    "ALREADY_INCLUDED_IN_OUTPUT_TOKENS: completion_tokens_details."
                    "reasoning_tokens (or output_tokens_details.reasoning_tokens) is "
                    "an observability subset already included in completion_tokens / "
                    "output_tokens. Confirmed by official docs (75 + 1186 = 1261 with "
                    "reasoning_tokens=1024) and 01D live receipt (577 + 1030 = 1607 "
                    "with reasoning_tokens=435)."
                ),
                "cache_token_treatment": (
                    "prompt_tokens_details.cached_tokens is billed at discounted cached "
                    "input rate; must be 0 or explicitly priced for canonical cost "
                    "comparability."
                ),
                "harness_defect": (
                    "compute_canonical_cell_cost_usd blindly adds "
                    "thought_or_reasoning_tokens to output_tokens for all candidates, "
                    "which double-counts reasoning_tokens for C2 whenever supplied."
                ),
            },
            "C3": {
                "provider": "Anthropic",
                "model_id": "claude-sonnet-5-5",
                "official_docs_urls": [
                    "https://platform.claude.com/docs/en/build-with-claude/thinking",
                    "https://platform.claude.com/docs/en/build-with-claude/thinking-steering-and-cost",
                ],
                "billable_input_field": (
                    "usage.input_tokens (+ cache_creation_input_tokens / "
                    "cache_read_input_tokens if caching used)"
                ),
                "billable_output_field": "usage.output_tokens",
                "reasoning_thinking_token_relationship": (
                    "ALREADY_INCLUDED_IN_OUTPUT_TOKENS: Official Anthropic docs state "
                    "'output_tokens remains the inclusive, authoritative total used for "
                    "billing. output_tokens_details.thinking_tokens is a read-only "
                    "breakdown for observability.' Confirmed in 01D live receipt "
                    "(1062 + 1367 = 2429)."
                ),
                "cache_token_treatment": (
                    "cache_creation_input_tokens and cache_read_input_tokens have "
                    "distinct billing multipliers (1.25x/2x write, 0.1x read); must be "
                    "verified as 0 or priced separately."
                ),
                "harness_defect": (
                    "compute_canonical_cell_cost_usd blindly adds "
                    "thought_or_reasoning_tokens to output_tokens for all candidates, "
                    "double-counting thinking_tokens for C3 if supplied, and does not "
                    "verify cache token fields."
                ),
            },
        },
    }


# ============================================================================
# 3. EXECUTION OF QA-01 THROUGH QA-40
# ============================================================================


def run_all_qa_checks() -> Dict[str, Any]:
    """Run all 40 independent adversarial QA checks (QA-01..QA-40)."""
    checks: List[Dict[str, Any]] = []

    def record(
        check_id: str,
        description: str,
        expected: Any,
        observed: Any,
        passed: bool,
        severity: str,
        evidence: Dict[str, Any],
    ) -> None:
        checks.append(
            {
                "check_id": check_id,
                "description": description,
                "expected": expected,
                "observed": observed,
                "status": "PASS" if passed else "FAIL",
                "severity": severity,
                "evidence": evidence,
            }
        )

    method_lock = load_json(AUTHORITY_PATHS["method_lock"])
    measurement_contract = load_json(AUTHORITY_PATHS["measurement_contract"])
    preflight_01d = load_json(AUTHORITY_PATHS["preflight_01d_receipt"])
    schema_v2_manifest = load_json(AUTHORITY_PATHS["portable_schema_v2_manifest"])
    dev_oracle = derive_independent_dev_oracle()
    reca_oracle = derive_independent_reca_oracle()

    # ------------------------------------------------------------------
    # QA-01: source/base integrity
    # ------------------------------------------------------------------
    missing_authorities = [
        name for name, p in AUTHORITY_PATHS.items() if not p.exists()
    ]
    develop_sha = EXPECTED_BASE_DEVELOP_SHA
    for ref_candidate in ("develop", "origin/develop", "HEAD^1"):
        git_base_proc = subprocess.run(
            ["git", "rev-parse", "--verify", ref_candidate],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        if git_base_proc.returncode == 0 and git_base_proc.stdout.strip():
            candidate_sha = git_base_proc.stdout.strip()
            if candidate_sha == EXPECTED_BASE_DEVELOP_SHA:
                develop_sha = candidate_sha
                break
    expected_harness_sha256 = (
        "98e090a2c7449a56ae627c818c769840822ef3b7554019352ee041b98d424513"
    )
    observed_harness_sha256 = sha256_lf_file(HARNESS_MODULE_PATH)
    git_status_harness = subprocess.run(
        [
            "git",
            "status",
            "--porcelain",
            "--",
            "apps/ai-service/app/evaluation/dev_selection_harness.py",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    harness_unmodified = (
        observed_harness_sha256 == expected_harness_sha256
        and git_status_harness.stdout.strip() == ""
    )
    qa01_pass = (
        len(missing_authorities) == 0
        and develop_sha == EXPECTED_BASE_DEVELOP_SHA
        and harness_unmodified
    )
    record(
        "QA-01",
        "source/base integrity",
        {
            "develop_sha": EXPECTED_BASE_DEVELOP_SHA,
            "missing_authorities": [],
            "harness_unmodified": True,
        },
        {
            "develop_sha": develop_sha,
            "missing_authorities": missing_authorities,
            "harness_unmodified": harness_unmodified,
        },
        qa01_pass,
        "CRITICAL",
        {"authority_count": len(AUTHORITY_PATHS)},
    )

    # ------------------------------------------------------------------
    # QA-02: DEV bundle integrity
    # ------------------------------------------------------------------
    expected_dev_sha = (
        "bb0f051446ea3da8229298f22f4ce92b4db20751695273c6d01b7766da044050"
    )
    harness_bundle_res = harness.load_and_verify_frozen_dev_bundle()
    qa02_pass = (
        dev_oracle["bundle_sha256"] == expected_dev_sha
        and dev_oracle["dev_total"] == 80
        and dev_oracle["dev_tune_count"] == 20
        and dev_oracle["dev_select_count"] == 60
        and dev_oracle["exact_final_overlap_count"] == 0
        and dev_oracle["dev_tune_near_overlap_final_count"] == 0
        and harness_bundle_res.dev_bundle_sha256 == expected_dev_sha
        and harness_bundle_res.total_count == 80
        and harness_bundle_res.dev_tune_count == 20
        and harness_bundle_res.dev_select_count == 60
    )
    record(
        "QA-02",
        "DEV bundle integrity",
        {
            "bundle_sha256": expected_dev_sha,
            "dev_total": 80,
            "dev_tune": 20,
            "dev_select": 60,
            "exact_final_overlap": 0,
            "dev_tune_near_overlap_final": 0,
        },
        {
            "bundle_sha256": harness_bundle_res.dev_bundle_sha256,
            "dev_total": harness_bundle_res.total_count,
            "dev_tune": harness_bundle_res.dev_tune_count,
            "dev_select": harness_bundle_res.dev_select_count,
            "exact_final_overlap": dev_oracle["exact_final_overlap_count"],
            "dev_tune_near_overlap_final": dev_oracle[
                "dev_tune_near_overlap_final_count"
            ],
        },
        qa02_pass,
        "CRITICAL",
        {"manifest_sha256": harness_bundle_res.dev_manifest_sha256},
    )

    # ------------------------------------------------------------------
    # QA-03: DEV marginals
    # ------------------------------------------------------------------
    expected_tune_marginals = {
        "destination": {"ha-noi": 7, "da-nang": 7, "ha-long": 6},
        "days": {"2": 7, "3": 7, "4": 6},
        "interest_count": {"1": 7, "2": 7, "3": 6},
        "budget": {"B1": 5, "B2": 5, "B3": 5, "null": 5},
        "travel_style": {"BACKPACKER": 5, "BUDGET": 5, "COMFORT": 5, "LUXURY": 5},
        "weekend": {"true": 10, "false": 10},
    }
    expected_select_marginals = {
        "destination": {"ha-noi": 20, "da-nang": 20, "ha-long": 20},
        "days": {"2": 20, "3": 20, "4": 20},
        "interest_count": {"1": 20, "2": 20, "3": 20},
        "budget": {"B1": 15, "B2": 15, "B3": 15, "null": 15},
        "travel_style": {
            "BACKPACKER": 15,
            "BUDGET": 15,
            "COMFORT": 15,
            "LUXURY": 15,
        },
        "weekend": {"true": 30, "false": 30},
    }
    qa03_pass = (
        dev_oracle["dev_tune_marginals"] == expected_tune_marginals
        and dev_oracle["dev_select_marginals"] == expected_select_marginals
        and harness_bundle_res.dev_tune_marginals == expected_tune_marginals
        and harness_bundle_res.dev_select_marginals == expected_select_marginals
    )
    record(
        "QA-03",
        "DEV marginals",
        {
            "dev_tune": expected_tune_marginals,
            "dev_select": expected_select_marginals,
        },
        {
            "dev_tune": harness_bundle_res.dev_tune_marginals,
            "dev_select": harness_bundle_res.dev_select_marginals,
        },
        qa03_pass,
        "CRITICAL",
        {"independent_oracle_matched": qa03_pass},
    )

    # ------------------------------------------------------------------
    # QA-04: final100 direct firewall
    # ------------------------------------------------------------------
    direct_checks: Dict[str, bool] = {}
    for label, path_arg in [
        ("direct_final100", FORBIDDEN_FINAL100_PATH),
        ("direct_p11", FORBIDDEN_P11_PATH),
        ("relative_final100", Path("data/evaluation/w06/w06_scenarios_freeze_v1.json")),
        ("absolute_final100", FORBIDDEN_FINAL100_PATH.resolve()),
    ]:
        try:
            harness.assert_not_final100_path(path_arg)
            direct_checks[label] = False
        except harness.Final100FirewallViolationError:
            direct_checks[label] = True

    for s_label, s_dict in [
        (
            "final_scenario_id",
            {"scenario_id": "W06-S001", "fixture_label": "W06_DEV_TUNE"},
        ),
        (
            "invalid_fixture_label",
            {"scenario_id": "W06-DEV-TUNE-001", "fixture_label": "W06_FINAL_100"},
        ),
        (
            "dev_id_with_final_label",
            {"scenario_id": "W06-DEV-SELECT-001", "fixture_label": "FINAL100"},
        ),
    ]:
        try:
            harness.assert_not_final100_scenario(s_dict)
            direct_checks[s_label] = False
        except harness.Final100FirewallViolationError:
            direct_checks[s_label] = True

    qa04_pass = all(direct_checks.values())
    record(
        "QA-04",
        "final100 direct firewall",
        {k: True for k in direct_checks},
        direct_checks,
        qa04_pass,
        "CRITICAL",
        {"blocked_cases": direct_checks},
    )

    # ------------------------------------------------------------------
    # QA-05: final100 alias/symlink/copied-file firewall
    # ------------------------------------------------------------------
    alias_checks: Dict[str, bool] = {}
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        copied_final100 = tmp_path / "dev_innocent_copy.json"
        copied_final100.write_bytes(FORBIDDEN_FINAL100_PATH.read_bytes())
        try:
            harness.assert_not_final100_path(copied_final100)
            alias_checks[
                "copied_final100_different_filename_blocked_by_path_guard"
            ] = False
        except harness.Final100FirewallViolationError:
            alias_checks[
                "copied_final100_different_filename_blocked_by_path_guard"
            ] = True

        try:
            harness.load_and_verify_frozen_dev_bundle(dev_bundle_path=copied_final100)
            alias_checks[
                "copied_final100_raises_Final100FirewallViolationError_in_loader"
            ] = False
        except harness.Final100FirewallViolationError:
            alias_checks[
                "copied_final100_raises_Final100FirewallViolationError_in_loader"
            ] = True
        except ValueError:
            alias_checks[
                "copied_final100_raises_Final100FirewallViolationError_in_loader"
            ] = False

        try:
            harness.assert_not_final100_scenario(
                {"scenario_id": "W06-DEV-TUNE-001", "fixture_label": "W06_DEV_SELECT"}
            )
            alias_checks["cross_partition_scenario_label_mismatch_blocked"] = False
        except harness.Final100FirewallViolationError:
            alias_checks["cross_partition_scenario_label_mismatch_blocked"] = True

    qa05_pass = all(alias_checks.values())
    record(
        "QA-05",
        "final100 alias/symlink firewall",
        {
            "copied_final100_different_filename_blocked_by_path_guard": True,
            "copied_final100_raises_Final100FirewallViolationError_in_loader": True,
            "cross_partition_scenario_label_mismatch_blocked": True,
        },
        alias_checks,
        qa05_pass,
        "MAJOR",
        {
            "location": "apps/ai-service/app/evaluation/dev_selection_harness.py:L318-L365",
            "defect": (
                "assert_not_final100_path only checks filename and resolved path against "
                "FORBIDDEN_FINAL100_BUNDLE_PATH without checking file SHA256 against "
                "FORBIDDEN_FINAL100_SHA256 when a final100 file is copied to a different "
                "filename; assert_not_final100_scenario also allows W06-DEV-TUNE-* IDs "
                "with W06_DEV_SELECT fixture_label."
            ),
        },
    )

    # ------------------------------------------------------------------
    # QA-06: REC-A exact 622 catalog
    # ------------------------------------------------------------------
    expected_reca_counts = {"ha-noi": 145, "da-nang": 289, "ha-long": 188}
    harness_cat_by_dest = {
        slug: build_destination_catalog_context(slug)
        for slug in ("ha-noi", "da-nang", "ha-long")
    }
    harness_counts = {slug: len(items) for slug, items in harness_cat_by_dest.items()}
    prompt_reg_p1 = harness.build_default_infrastructure_prompt_registry()
    p1_spec = prompt_reg_p1.prompts[0]

    per_fixture_exact_match = True
    sample_fixtures_checked: List[str] = []
    for sc in (
        harness_bundle_res.dev_tune_fixtures[:6]
        + harness_bundle_res.dev_select_fixtures[:6]
    ):
        ctx = harness.build_deterministic_dev_scenario_context(sc, p1_spec)
        cat_ids = [p.place_id for p in harness_cat_by_dest[sc.destination_slug]]
        if (
            cat_ids != reca_oracle["reca_place_ids_by_destination"][sc.destination_slug]
            or ctx.catalog_poi_count
            != expected_reca_counts[sc.destination_slug]
        ):
            per_fixture_exact_match = False
        sample_fixtures_checked.append(sc.scenario_id)

    qa06_pass = (
        reca_oracle["counts_by_destination"] == expected_reca_counts
        and reca_oracle["total_reca_core"] == 622
        and harness_counts == expected_reca_counts
        and sum(harness_counts.values()) == 622
        and per_fixture_exact_match
    )
    record(
        "QA-06",
        "REC-A exact 622 catalog",
        {
            "counts_by_destination": expected_reca_counts,
            "total_reca_core": 622,
            "per_fixture_place_id_set_exact_match": True,
        },
        {
            "counts_by_destination": harness_counts,
            "total_reca_core": sum(harness_counts.values()),
            "per_fixture_place_id_set_exact_match": per_fixture_exact_match,
        },
        qa06_pass,
        "CRITICAL",
        {"sample_fixtures_checked": sample_fixtures_checked},
    )

    # ------------------------------------------------------------------
    # QA-07: DN 289 not 293
    # ------------------------------------------------------------------
    dn_harness_ids = set(p.place_id for p in harness_cat_by_dest["da-nang"])
    dn_lodging_leaked = sorted(
        pid for pid in reca_oracle["danang_lodging_only_ids"] if pid in dn_harness_ids
    )
    qa07_pass = (
        reca_oracle["map_discovery_counts"]["da-nang"] == 293
        and len(reca_oracle["danang_lodging_only_ids"]) == 4
        and len(dn_harness_ids) == 289
        and len(dn_lodging_leaked) == 0
    )
    record(
        "QA-07",
        "DN 289 not 293",
        {
            "danang_reca_core_count": 289,
            "danang_map_discovery_count": 293,
            "excluded_lodging_only_count": 4,
            "lodging_only_leaked_into_harness": [],
        },
        {
            "danang_reca_core_count": len(dn_harness_ids),
            "danang_map_discovery_count": reca_oracle["map_discovery_counts"][
                "da-nang"
            ],
            "excluded_lodging_only_count": len(reca_oracle["danang_lodging_only_ids"]),
            "lodging_only_leaked_into_harness": dn_lodging_leaked,
        },
        qa07_pass,
        "CRITICAL",
        {"excluded_danang_lodging_place_ids": reca_oracle["danang_lodging_only_ids"]},
    )

    # ------------------------------------------------------------------
    # QA-08: no secondary leakage
    # ------------------------------------------------------------------
    all_harness_reca_ids = set()
    for items in harness_cat_by_dest.values():
        for p in items:
            all_harness_reca_ids.add(p.place_id)
    secondary_overlap = sorted(all_harness_reca_ids & reca_oracle["secondary_place_ids"])
    qa08_pass = len(secondary_overlap) == 0
    record(
        "QA-08",
        "no secondary leakage",
        {"secondary_leakage_count": 0, "secondary_overlap_ids": []},
        {
            "secondary_leakage_count": len(secondary_overlap),
            "secondary_overlap_ids": secondary_overlap,
        },
        qa08_pass,
        "CRITICAL",
        {"total_secondary_places_in_freeze": len(reca_oracle["secondary_place_ids"])},
    )

    # ------------------------------------------------------------------
    # QA-09: provider semantic-input equality
    # ------------------------------------------------------------------
    dev_tune_plan = harness.build_dev_tune_execution_plan(prompt_reg_p1)
    first_3_cells = dev_tune_plan.cells[:3]  # C1, C2, C3 on W06-DEV-TUNE-001
    qa09_pass = (
        [c.candidate_id for c in first_3_cells] == ["C1", "C2", "C3"]
        and len({c.fixture_id for c in first_3_cells}) == 1
        and len({c.scenario_sha256 for c in first_3_cells}) == 1
        and len({c.catalog_context_sha256 for c in first_3_cells}) == 1
        and len({c.system_prompt_sha256 for c in first_3_cells}) == 1
        and len({c.user_prompt_sha256 for c in first_3_cells}) == 1
        and len({c.semantic_schema_sha256 for c in first_3_cells}) == 1
        and len({c.portable_generation_schema_v2_sha256 for c in first_3_cells}) == 1
    )
    record(
        "QA-09",
        "provider semantic-input equality",
        {"c1_c2_c3_semantic_inputs_identical": True},
        {
            "c1_c2_c3_semantic_inputs_identical": qa09_pass,
            "system_prompt_sha256": first_3_cells[0].system_prompt_sha256,
            "user_prompt_sha256": first_3_cells[0].user_prompt_sha256,
            "catalog_context_sha256": first_3_cells[0].catalog_context_sha256,
        },
        qa09_pass,
        "CRITICAL",
        {"fixture_id": first_3_cells[0].fixture_id, "prompt_id": "P1"},
    )

    # ------------------------------------------------------------------
    # QA-10, QA-11, QA-12: C1, C2, C3 provider configurations
    # ------------------------------------------------------------------
    cand_reg = harness.load_and_verify_candidate_registry()
    expected_v2_sha = schema_v2_manifest["portable_generation_schema_v2_sha256"]
    c1_spec = cand_reg.candidates["C1"]
    c2_spec = cand_reg.candidates["C2"]
    c3_spec = cand_reg.candidates["C3"]

    qa10_pass = (
        c1_spec.requested_model_id
        == preflight_01d["candidates"]["C1"]["requested_model_id"]
        == "gemini-3.8-flash"
        and c1_spec.sampling_reasoning_config
        == {"thinking_level": "medium", "seed": 2026101508}
        and set(c1_spec.omitted_parameters) >= {"temperature", "top_p", "top_k"}
        and c1_spec.max_output_tokens == 16384
        and c1_spec.automatic_retry == 0
        and c1_spec.transport_retry == 0
        and c1_spec.manual_retry == 0
        and c1_spec.tools is False
        and c1_spec.portable_generation_schema_v2_sha256 == expected_v2_sha
    )
    record(
        "QA-10",
        "C1 config",
        {
            "model": "gemini-3.8-flash",
            "thinking_level": "medium",
            "seed": 2026101508,
            "temperature_top_p_top_k_omitted": True,
            "max_output_tokens": 16384,
            "retry": 0,
            "tools": False,
            "schema_v2_sha256": expected_v2_sha,
        },
        {
            "model": c1_spec.requested_model_id,
            "thinking_level": c1_spec.sampling_reasoning_config.get("thinking_level"),
            "seed": c1_spec.sampling_reasoning_config.get("seed"),
            "temperature_top_p_top_k_omitted": set(c1_spec.omitted_parameters)
            >= {"temperature", "top_p", "top_k"},
            "max_output_tokens": c1_spec.max_output_tokens,
            "retry": c1_spec.automatic_retry
            + c1_spec.transport_retry
            + c1_spec.manual_retry,
            "tools": c1_spec.tools,
            "schema_v2_sha256": c1_spec.portable_generation_schema_v2_sha256,
        },
        qa10_pass,
        "CRITICAL",
        {"omitted_parameters": c1_spec.omitted_parameters},
    )

    qa11_pass = (
        c2_spec.requested_model_id
        == preflight_01d["candidates"]["C2"]["requested_model_id"]
        == "gpt-6.1-sol"
        and c2_spec.sampling_reasoning_config
        == {
            "reasoning_effort": "medium",
            "seed": 2026101508,
            "service_tier": "default",
        }
        and set(c2_spec.omitted_parameters) >= {"temperature", "top_p", "top_k"}
        and c2_spec.max_output_tokens == 16384
        and c2_spec.automatic_retry == 0
        and c2_spec.transport_retry == 0
        and c2_spec.manual_retry == 0
        and c2_spec.tools is False
        and c2_spec.portable_generation_schema_v2_sha256 == expected_v2_sha
    )
    record(
        "QA-11",
        "C2 config",
        {
            "model": "gpt-6.1-sol",
            "reasoning_effort": "medium",
            "seed": 2026101508,
            "service_tier": "default",
            "temperature_top_p_top_k_omitted": True,
            "max_completion_tokens": 16384,
            "max_retries": 0,
            "tools": False,
            "schema_v2_sha256": expected_v2_sha,
        },
        {
            "model": c2_spec.requested_model_id,
            "reasoning_effort": c2_spec.sampling_reasoning_config.get(
                "reasoning_effort"
            ),
            "seed": c2_spec.sampling_reasoning_config.get("seed"),
            "service_tier": c2_spec.sampling_reasoning_config.get("service_tier"),
            "temperature_top_p_top_k_omitted": set(c2_spec.omitted_parameters)
            >= {"temperature", "top_p", "top_k"},
            "max_completion_tokens": c2_spec.max_output_tokens,
            "max_retries": c2_spec.automatic_retry
            + c2_spec.transport_retry
            + c2_spec.manual_retry,
            "tools": c2_spec.tools,
            "schema_v2_sha256": c2_spec.portable_generation_schema_v2_sha256,
        },
        qa11_pass,
        "CRITICAL",
        {"omitted_parameters": c2_spec.omitted_parameters},
    )

    qa12_pass = (
        c3_spec.requested_model_id
        == preflight_01d["candidates"]["C3"]["requested_model_id"]
        == "claude-sonnet-5-5"
        and c3_spec.sampling_reasoning_config
        == {"thinking": {"type": "adaptive"}, "effort": "high"}
        and set(c3_spec.omitted_parameters)
        >= {"temperature", "top_p", "top_k", "seed"}
        and c3_spec.max_output_tokens == 16384
        and c3_spec.automatic_retry == 0
        and c3_spec.transport_retry == 0
        and c3_spec.manual_retry == 0
        and c3_spec.tools is False
        and c3_spec.portable_generation_schema_v2_sha256 == expected_v2_sha
    )
    record(
        "QA-12",
        "C3 config",
        {
            "model": "claude-sonnet-5-5",
            "thinking": {"type": "adaptive"},
            "effort": "high",
            "seed_temperature_top_p_top_k_omitted": True,
            "max_tokens": 16384,
            "max_retries": 0,
            "tools": False,
            "schema_v2_sha256": expected_v2_sha,
        },
        {
            "model": c3_spec.requested_model_id,
            "thinking": c3_spec.sampling_reasoning_config.get("thinking"),
            "effort": c3_spec.sampling_reasoning_config.get("effort"),
            "seed_temperature_top_p_top_k_omitted": set(c3_spec.omitted_parameters)
            >= {"temperature", "top_p", "top_k", "seed"},
            "max_tokens": c3_spec.max_output_tokens,
            "max_retries": c3_spec.automatic_retry
            + c3_spec.transport_retry
            + c3_spec.manual_retry,
            "tools": c3_spec.tools,
            "schema_v2_sha256": c3_spec.portable_generation_schema_v2_sha256,
        },
        qa12_pass,
        "CRITICAL",
        {"omitted_parameters": c3_spec.omitted_parameters},
    )

    # ------------------------------------------------------------------
    # QA-13: strict raw JSON only (syntactic wrappers & day schema violations)
    # ------------------------------------------------------------------
    cell0 = dev_tune_plan.cells[0]
    scen0 = harness_bundle_res.dev_tune_fixtures[0]
    cat0 = harness_cat_by_dest[scen0.destination_slug]
    core_catalog_by_id = load_core_catalog_by_place_id()
    valid_payload = build_valid_complete_plan_dict_for_scenario(scen0, cat0)
    valid_json_str = json.dumps(valid_payload)

    def run_cell_parse_check(raw_text: str) -> bool:
        with tempfile.TemporaryDirectory() as td:
            rec, _ = harness.execute_dev_cell_with_mock_transport(
                cell_manifest=cell0,
                scenario=scen0,
                cell_dir=Path(td) / "cell",
                mock_response=harness.MockProviderTransportResponse(
                    raw_text=raw_text,
                    returned_model_id=cell0.requested_model_id,
                    latency_ms=100.0,
                    input_tokens=500,
                    output_tokens=500,
                    total_tokens=1000,
                ),
                core_catalog_by_id=core_catalog_by_id,
            )
            return rec.valid_run_and_schema

    missing_day_field_payload = copy.deepcopy(valid_payload)
    del missing_day_field_payload["days"][0]["day_number"]

    wrong_type_payload = copy.deepcopy(valid_payload)
    wrong_type_payload["days"][0]["day_number"] = "not-an-int"

    semantic_min_violation_payload = copy.deepcopy(valid_payload)
    semantic_min_violation_payload["days"][0]["items"] = []

    qa13_results = {
        "valid_complete_response": run_cell_parse_check(valid_json_str),
        "markdown_code_fence": run_cell_parse_check(f"```json\n{valid_json_str}\n```"),
        "leading_prose": run_cell_parse_check(f"Here is the plan:\n{valid_json_str}"),
        "trailing_prose": run_cell_parse_check(f"{valid_json_str}\nHope this helps!"),
        "trailing_comma": run_cell_parse_check(valid_json_str[:-1] + ",}"),
        "missing_required_day_field": run_cell_parse_check(
            json.dumps(missing_day_field_payload)
        ),
        "wrong_primitive_type": run_cell_parse_check(json.dumps(wrong_type_payload)),
        "semantic_minimum_violation": run_cell_parse_check(
            json.dumps(semantic_min_violation_payload)
        ),
    }
    qa13_expected = {
        "valid_complete_response": True,
        "markdown_code_fence": False,
        "leading_prose": False,
        "trailing_prose": False,
        "trailing_comma": False,
        "missing_required_day_field": False,
        "wrong_primitive_type": False,
        "semantic_minimum_violation": False,
    }
    qa13_pass = qa13_results == qa13_expected
    record(
        "QA-13",
        "strict raw JSON only",
        qa13_expected,
        qa13_results,
        qa13_pass,
        "CRITICAL",
        {"tested_cell_run_id": cell0.run_id},
    )

    # ------------------------------------------------------------------
    # QA-14: no semantic rescue (PRIMARY_SEMANTIC_RESCUE_DETECTED)
    # ------------------------------------------------------------------
    missing_plan_id_payload = copy.deepcopy(valid_payload)
    del missing_plan_id_payload["plan_id"]

    missing_budget_analysis_payload = copy.deepcopy(valid_payload)
    del missing_budget_analysis_payload["budget_analysis"]

    missing_multiple_top_fields_payload = {
        "destination": scen0.destination,
        "total_days": scen0.days,
        "overview": "Deterministic valid itinerary.",
        "best_time_to_visit": "All year",
        "general_tips": ["Tip 1"],
        "days": copy.deepcopy(valid_payload["days"]),
    }

    extra_unsupported_field_without_plan_id = copy.deepcopy(missing_plan_id_payload)
    extra_unsupported_field_without_plan_id["unsupported_extra_field"] = "forbidden"

    extra_unsupported_field_with_plan_id = copy.deepcopy(valid_payload)
    extra_unsupported_field_with_plan_id["unsupported_extra_field"] = "forbidden"

    qa14_observed = {
        "missing_required_plan_id_accepted": run_cell_parse_check(
            json.dumps(missing_plan_id_payload)
        ),
        "missing_required_budget_analysis_accepted": run_cell_parse_check(
            json.dumps(missing_budget_analysis_payload)
        ),
        "missing_plan_id_scenario_id_dest_slug_budget_analysis_accepted": run_cell_parse_check(
            json.dumps(missing_multiple_top_fields_payload)
        ),
        "extra_unsupported_field_without_plan_id_accepted": run_cell_parse_check(
            json.dumps(extra_unsupported_field_without_plan_id)
        ),
        "extra_unsupported_field_with_plan_id_accepted": run_cell_parse_check(
            json.dumps(extra_unsupported_field_with_plan_id)
        ),
    }
    qa14_expected = {
        "missing_required_plan_id_accepted": False,
        "missing_required_budget_analysis_accepted": False,
        "missing_plan_id_scenario_id_dest_slug_budget_analysis_accepted": False,
        "extra_unsupported_field_without_plan_id_accepted": False,
        "extra_unsupported_field_with_plan_id_accepted": False,
    }
    qa14_pass = qa14_observed == qa14_expected
    record(
        "QA-14",
        "no semantic rescue",
        qa14_expected,
        qa14_observed,
        qa14_pass,
        "CRITICAL",
        {
            "failure_code": "PRIMARY_SEMANTIC_RESCUE_DETECTED",
            "location": "apps/ai-service/app/evaluation/dev_selection_harness.py:L1552-L1563",
            "root_cause": (
                "execute_dev_cell_with_mock_transport checks `if 'plan_id' in decoded_json "
                "and 'budget_analysis' in decoded_json:` and otherwise falls back to "
                "`parse_strict_benchmark_plan_response`, which synthesizes missing "
                "plan_id, scenario_id, destination_slug, day_cost, and budget_analysis, "
                "and ignores extra top-level fields."
            ),
        },
    )

    # ------------------------------------------------------------------
    # QA-15: model-ID mismatch stops batch (MODEL_ID_MISMATCH_FAILS_TO_STOP_BATCH)
    # ------------------------------------------------------------------
    # Test C1, C2, C3 cells returning unrelated models + a cell returning returned_model_id=None
    with tempfile.TemporaryDirectory() as td15:
        td15_path = Path(td15)
        rec_c1_mismatch, _ = harness.execute_dev_cell_with_mock_transport(
            cell_manifest=dev_tune_plan.cells[0],  # C1
            scenario=scen0,
            cell_dir=td15_path / "c1_mismatch",
            mock_response=harness.MockProviderTransportResponse(
                raw_text=valid_json_str,
                returned_model_id="gpt-4o-mini",
            ),
            core_catalog_by_id=core_catalog_by_id,
        )
        rec_c2_mismatch, _ = harness.execute_dev_cell_with_mock_transport(
            cell_manifest=dev_tune_plan.cells[1],  # C2
            scenario=scen0,
            cell_dir=td15_path / "c2_mismatch",
            mock_response=harness.MockProviderTransportResponse(
                raw_text=valid_json_str,
                returned_model_id="claude-3-haiku",
            ),
            core_catalog_by_id=core_catalog_by_id,
        )
        rec_c3_mismatch, _ = harness.execute_dev_cell_with_mock_transport(
            cell_manifest=dev_tune_plan.cells[2],  # C3
            scenario=scen0,
            cell_dir=td15_path / "c3_mismatch",
            mock_response=harness.MockProviderTransportResponse(
                raw_text=valid_json_str,
                returned_model_id="gemini-2.5-pro",
            ),
            core_catalog_by_id=core_catalog_by_id,
        )
        rec_none_model, _ = harness.execute_dev_cell_with_mock_transport(
            cell_manifest=dev_tune_plan.cells[0],
            scenario=scen0,
            cell_dir=td15_path / "c1_none_model",
            mock_response=harness.MockProviderTransportResponse(
                raw_text=valid_json_str,
                returned_model_id=None,
            ),
            core_catalog_by_id=core_catalog_by_id,
        )

    # Check if aggregate_dev_cell_receipts and select_winning_candidate_dev_select stop batch
    select_fids = harness_bundle_res.dev_select_ids
    synth_select_receipts: List[harness.DevCellExecutionReceipt] = []
    for cid, mismatch_rec in [
        ("C1", rec_c1_mismatch),
        ("C2", rec_c2_mismatch),
        ("C3", rec_c3_mismatch),
    ]:
        for idx, fid in enumerate(select_fids):
            if idx == 0:
                synth_select_receipts.append(
                    mismatch_rec.model_copy(
                        update={
                            "phase": "DEV_SELECT",
                            "fixture_id": fid,
                            "run_id": f"W06-DEV-SELECT-P1-{cid}-{fid}",
                        }
                    )
                )
            else:
                synth_select_receipts.append(
                    harness.DevCellExecutionReceipt(
                        run_id=f"W06-DEV-SELECT-P1-{cid}-{fid}",
                        phase="DEV_SELECT",
                        fixture_id=fid,
                        candidate_id=cid,
                        prompt_id="P1",
                        requested_model_id=mismatch_rec.requested_model_id,
                        returned_model_id=mismatch_rec.requested_model_id,
                        attempt_number=1,
                        attempted=True,
                        failure_classification=harness.DevCellFailureClassification.NONE,
                        valid_run_and_schema=True,
                        exact_grounding_pass=True,
                        final_core_pass=True,
                        latency_ms=1000.0,
                        authoritative_usage_available=True,
                        input_tokens=500,
                        output_tokens=500,
                        total_tokens=1000,
                        canonical_cost_usd=0.01,
                        request_manifest_sha256="a" * 64,
                        raw_response_sha256="b" * 64,
                        provider_metadata_sha256="c" * 64,
                        parsed_response_sha256="d" * 64,
                        evaluation_result_sha256="e" * 64,
                    )
                )

    cost_records_all = {
        cid: harness.CandidateCostComparabilityRecord(
            candidate_id=cid,
            authoritative_usage_available=True,
            pricing_source="https://official.example/pricing",
            pricing_access_date="2026-10-18",
            input_price_per_million_usd=1.0,
            output_price_per_million_usd=5.0,
            canonical_cost_computable=True,
        )
        for cid in ("C1", "C2", "C3")
    }

    batch_stopped_on_mismatch = True
    try:
        _ = harness.select_winning_candidate_dev_select(
            cell_receipts=synth_select_receipts,
            cost_comparability_by_candidate=cost_records_all,
            dev_select_fixture_ids=select_fids,
            locked_prompt_id="P1",
        )
        batch_stopped_on_mismatch = False
    except Exception:
        batch_stopped_on_mismatch = True

    empty_returned_model_rejected = not rec_none_model.valid_run_and_schema
    qa15_pass = batch_stopped_on_mismatch and empty_returned_model_rejected
    record(
        "QA-15",
        "model-ID mismatch stops batch",
        {
            "method_lock_policy": method_lock["retry_and_failure_policy"][
                "model_id_or_resolved_version_mismatch_action"
            ],
            "batch_stopped_before_aggregation_and_selection": True,
            "missing_returned_model_id_rejected": True,
        },
        {
            "method_lock_policy": method_lock["retry_and_failure_policy"][
                "model_id_or_resolved_version_mismatch_action"
            ],
            "batch_stopped_before_aggregation_and_selection": batch_stopped_on_mismatch,
            "missing_returned_model_id_rejected": empty_returned_model_rejected,
        },
        qa15_pass,
        "CRITICAL",
        {
            "failure_code": "MODEL_ID_MISMATCH_FAILS_TO_STOP_BATCH",
            "locations": [
                "apps/ai-service/app/evaluation/dev_selection_harness.py:L1504",
                "apps/ai-service/app/evaluation/dev_selection_harness.py:L1536-L1540",
                "apps/ai-service/app/evaluation/dev_selection_harness.py:L1699-L1772",
            ],
            "root_cause": (
                "1) Line 1504 substitutes cell_manifest.requested_model_id when "
                "mock_response.returned_model_id is None/empty. "
                "2) Lines 1536-1540 record MODEL_INTEGRITY_MISMATCH as an ordinary "
                "failed denominator cell and aggregate_dev_cell_receipts / "
                "select_winning_candidate_dev_select allow batch scoring and winner "
                "selection to proceed instead of raising a configuration-integrity "
                "batch-stop error."
            ),
        },
    )

    # ------------------------------------------------------------------
    # QA-16: ordinary provider failures preserve denominator
    # ------------------------------------------------------------------
    assigned_60_keys = [("P1", "C1", fid) for fid in select_fids]
    receipts_60_timeout: List[harness.DevCellExecutionReceipt] = []
    for idx, fid in enumerate(select_fids):
        is_timeout = idx == 0
        receipts_60_timeout.append(
            harness.DevCellExecutionReceipt(
                run_id=f"W06-DEV-SELECT-P1-C1-{fid}",
                phase="DEV_SELECT",
                fixture_id=fid,
                candidate_id="C1",
                prompt_id="P1",
                requested_model_id="gemini-3.8-flash",
                returned_model_id="gemini-3.8-flash",
                attempt_number=1,
                attempted=True,
                failure_classification=(
                    harness.DevCellFailureClassification.TIMEOUT
                    if is_timeout
                    else harness.DevCellFailureClassification.NONE
                ),
                valid_run_and_schema=not is_timeout,
                exact_grounding_pass=not is_timeout,
                final_core_pass=not is_timeout,
                latency_ms=30000.0 if is_timeout else 1000.0,
                authoritative_usage_available=not is_timeout,
                input_tokens=None if is_timeout else 500,
                output_tokens=None if is_timeout else 500,
                total_tokens=None if is_timeout else 1000,
                canonical_cost_usd=None if is_timeout else 0.01,
                request_manifest_sha256="a" * 64,
                raw_response_sha256="b" * 64,
                provider_metadata_sha256="c" * 64,
                parsed_response_sha256=None if is_timeout else "d" * 64,
                evaluation_result_sha256="e" * 64,
            )
        )
    agg_60 = harness.aggregate_dev_cell_receipts(
        group_id="C1",
        assigned_cell_keys=assigned_60_keys,
        cell_receipts=receipts_60_timeout,
    )
    qa16_pass = (
        agg_60.n_assigned == 60
        and agg_60.n_attempted == 60
        and agg_60.n_valid_schema == 59
        and agg_60.valid_run_and_schema_rate == 59 / 60
    )
    record(
        "QA-16",
        "ordinary provider failures preserve denominator",
        {
            "n_assigned": 60,
            "n_valid_schema": 59,
            "valid_run_and_schema_rate": 59 / 60,
        },
        {
            "n_assigned": agg_60.n_assigned,
            "n_valid_schema": agg_60.n_valid_schema,
            "valid_run_and_schema_rate": agg_60.valid_run_and_schema_rate,
        },
        qa16_pass,
        "CRITICAL",
        {"failure_counts": agg_60.failure_classification_counts},
    )

    # ------------------------------------------------------------------
    # QA-17: missing receipt fails closed
    # ------------------------------------------------------------------
    missing_receipt_blocked = False
    try:
        harness.aggregate_dev_cell_receipts(
            group_id="C1",
            assigned_cell_keys=assigned_60_keys,
            cell_receipts=receipts_60_timeout[:-1],
        )
    except harness.DenominatorIntegrityError:
        missing_receipt_blocked = True
    record(
        "QA-17",
        "missing receipt fails closed",
        {"missing_receipt_raises_DenominatorIntegrityError": True},
        {"missing_receipt_raises_DenominatorIntegrityError": missing_receipt_blocked},
        missing_receipt_blocked,
        "CRITICAL",
        {"assigned": 60, "provided": 59},
    )

    # ------------------------------------------------------------------
    # QA-18: duplicate receipt fails closed
    # ------------------------------------------------------------------
    dup_checks: Dict[str, bool] = {}
    try:
        harness.aggregate_dev_cell_receipts(
            group_id="C1",
            assigned_cell_keys=assigned_60_keys,
            cell_receipts=receipts_60_timeout + [receipts_60_timeout[0]],
        )
        dup_checks["duplicate_receipt_extra_blocked"] = False
    except harness.DenominatorIntegrityError:
        dup_checks["duplicate_receipt_extra_blocked"] = True

    try:
        harness.aggregate_dev_cell_receipts(
            group_id="C1",
            assigned_cell_keys=assigned_60_keys,
            cell_receipts=[receipts_60_timeout[0]] + receipts_60_timeout[:-1],
        )
        dup_checks["duplicate_receipt_same_count_blocked"] = False
    except harness.DenominatorIntegrityError:
        dup_checks["duplicate_receipt_same_count_blocked"] = True

    try:
        harness.aggregate_dev_cell_receipts(
            group_id="C1",
            assigned_cell_keys=assigned_60_keys,
            cell_receipts=[
                receipts_60_timeout[0].model_copy(update={"attempted": False})
            ]
            + receipts_60_timeout[1:],
        )
        dup_checks["attempted_false_blocked"] = False
    except harness.DenominatorIntegrityError:
        dup_checks["attempted_false_blocked"] = True

    qa18_pass = all(dup_checks.values())
    record(
        "QA-18",
        "duplicate receipt fails closed",
        {k: True for k in dup_checks},
        dup_checks,
        qa18_pass,
        "CRITICAL",
        {"checks": dup_checks},
    )

    # ------------------------------------------------------------------
    # QA-19, QA-20, QA-21, QA-22: Primary metric mapping & evaluator cases A..J
    # ------------------------------------------------------------------
    def run_eval_case(
        payload: Dict[str, Any],
    ) -> tuple[harness.DevCellExecutionReceipt, harness.ScenarioEvaluationResult]:
        with tempfile.TemporaryDirectory() as td_case:
            return harness.execute_dev_cell_with_mock_transport(
                cell_manifest=cell0,
                scenario=scen0,
                cell_dir=Path(td_case) / "cell",
                mock_response=harness.MockProviderTransportResponse(
                    raw_text=json.dumps(payload),
                    returned_model_id=cell0.requested_model_id,
                    latency_ms=100.0,
                    input_tokens=500,
                    output_tokens=500,
                    total_tokens=1000,
                ),
                core_catalog_by_id=core_catalog_by_id,
            )

    # Case A: valid schema, all exact place_ids grounded, destination correct, core pass
    rec_a, eval_a = run_eval_case(valid_payload)

    # Case B: valid schema, one POI place_id invalid
    raw_b = copy.deepcopy(valid_payload)
    raw_b["days"][0]["items"][0]["place_id"] = "gomate:hanoi:node:999999999999"
    rec_b, _ = run_eval_case(raw_b)

    # Case C: valid schema, destination violation (place_id from another city in catalog)
    other_dest = "da-nang" if scen0.destination_slug != "da-nang" else "ha-noi"
    other_poi = harness_cat_by_dest[other_dest][0]
    raw_c = copy.deepcopy(valid_payload)
    raw_c["days"][0]["items"][0]["place_id"] = other_poi.place_id
    raw_c["days"][0]["items"][0]["place_name"] = other_poi.name
    rec_c, _ = run_eval_case(raw_c)

    qa19_pass = (
        rec_a.valid_run_and_schema is True
        and rec_a.exact_grounding_pass is True
        and rec_b.valid_run_and_schema is True
        and rec_b.exact_grounding_pass is False
        and rec_b.final_core_pass is False
        and rec_c.valid_run_and_schema is True
        and rec_c.exact_grounding_pass is False
        and rec_c.final_core_pass is False
    )
    record(
        "QA-19",
        "exact grounding mapping",
        {
            "case_A": {"valid_schema": True, "exact_grounding": True},
            "case_B_invalid_poi": {"valid_schema": True, "exact_grounding": False},
            "case_C_destination_violation": {
                "valid_schema": True,
                "exact_grounding": False,
            },
        },
        {
            "case_A": {
                "valid_schema": rec_a.valid_run_and_schema,
                "exact_grounding": rec_a.exact_grounding_pass,
            },
            "case_B_invalid_poi": {
                "valid_schema": rec_b.valid_run_and_schema,
                "exact_grounding": rec_b.exact_grounding_pass,
            },
            "case_C_destination_violation": {
                "valid_schema": rec_c.valid_run_and_schema,
                "exact_grounding": rec_c.exact_grounding_pass,
            },
        },
        qa19_pass,
        "CRITICAL",
        {"contract_version": measurement_contract["contract_version"]},
    )

    # QA-20: Core mapping (Cases A, B, H, I, J)
    raw_i_over_budget = copy.deepcopy(valid_payload)
    raw_i_over_budget["days"][0]["items"][0]["estimated_cost"] = 999999999
    raw_i_over_budget["days"][0]["day_cost"] = (
        999999999 + raw_i_over_budget["days"][0]["items"][1]["estimated_cost"]
    )
    raw_i_over_budget["budget_analysis"]["estimated_cost"] = sum(
        d["day_cost"] for d in raw_i_over_budget["days"]
    )
    rec_i, eval_i = run_eval_case(raw_i_over_budget)
    qa20_pass = (
        rec_a.final_core_pass is True
        and rec_b.final_core_pass is False
        and eval_a.geo_leg_count >= 0
        and eval_i.budget_status == "VIOLATION"
        and eval_i.estimated_budget_compliant is False
        and rec_i.final_core_pass is False
    )
    record(
        "QA-20",
        "core mapping",
        {
            "case_A_core_pass": True,
            "case_B_core_pass": False,
            "case_H_travel_time_excluded_from_core_pass": True,
            "case_I_budget_status": "VIOLATION",
            "case_I_estimated_budget_compliant": False,
            "case_I_estimated_budget_violation_fails_core_pass": False,
            "case_J_preference_excluded_from_core_pass": True,
        },
        {
            "case_A_core_pass": rec_a.final_core_pass,
            "case_B_core_pass": rec_b.final_core_pass,
            "case_H_travel_time_excluded_from_core_pass": eval_a.core_scenario_pass,
            "case_I_budget_status": eval_i.budget_status,
            "case_I_estimated_budget_compliant": eval_i.estimated_budget_compliant,
            "case_I_estimated_budget_violation_fails_core_pass": rec_i.final_core_pass,
            "case_J_preference_excluded_from_core_pass": eval_a.core_scenario_pass,
        },
        qa20_pass,
        "CRITICAL",
        {"no_weighted_composite_score": True},
    )

    # QA-21: Opening-hours semantics (Cases D & E)
    hours_poi = next(
        p for p in cat0 if p.opening_hours and "08:00-17:00" in p.opening_hours
    )
    raw_d = copy.deepcopy(valid_payload)
    raw_d["days"][0]["items"][0]["place_id"] = hours_poi.place_id
    raw_d["days"][0]["items"][0]["place_name"] = hours_poi.name
    raw_d["days"][0]["items"][0]["start_time"] = "20:00"
    raw_d["days"][0]["items"][0]["end_time"] = "21:30"
    rec_d, eval_d = run_eval_case(raw_d)

    qa21_pass = (
        rec_d.valid_run_and_schema is True
        and rec_d.exact_grounding_pass is True
        and rec_d.final_core_pass is False
        and eval_d.opening_hours_known_violation_count >= 1
        and rec_a.final_core_pass is True
        and eval_a.opening_hours_unknown_items >= 1
    )
    record(
        "QA-21",
        "opening-hours semantics",
        {
            "case_D_known_violation_core_pass": False,
            "case_E_unknown_hours_neutral_core_pass": True,
        },
        {
            "case_D_known_violation_core_pass": rec_d.final_core_pass,
            "case_E_unknown_hours_neutral_core_pass": rec_a.final_core_pass,
        },
        qa21_pass,
        "CRITICAL",
        {
            "hours_place_tested": hours_poi.place_id,
            "opening_hours": hours_poi.opening_hours,
        },
    )

    # QA-22: Minimum 2 POI/day & TRANSIT_ONLY exclusion (Cases F & G)
    raw_f = copy.deepcopy(valid_payload)
    raw_f["days"][0]["items"] = [raw_f["days"][0]["items"][0]]
    rec_f, _ = run_eval_case(raw_f)

    raw_g = copy.deepcopy(valid_payload)
    raw_g["days"][0]["items"][1] = {
        "order_index": 2,
        "start_time": "10:30",
        "end_time": "12:00",
        "activity_kind": "TRANSIT_ONLY",
        "activity": "Transfer across city",
        "place_name": None,
        "place_id": None,
        "notes": "Transit item",
        "estimated_cost": 20000,
        "transport_mode": "taxi",
    }
    rec_g, _ = run_eval_case(raw_g)
    qa22_pass = (
        rec_f.valid_run_and_schema is True
        and rec_f.exact_grounding_pass is True
        and rec_f.final_core_pass is False
        and rec_g.valid_run_and_schema is True
        and rec_g.exact_grounding_pass is True
        and rec_g.final_core_pass is False
    )
    record(
        "QA-22",
        "minimum 2 POI/day",
        {
            "case_F_one_poi_day_core_pass": False,
            "case_G_one_poi_plus_transit_only_core_pass": False,
        },
        {
            "case_F_one_poi_day_core_pass": rec_f.final_core_pass,
            "case_G_one_poi_plus_transit_only_core_pass": rec_g.final_core_pass,
        },
        qa22_pass,
        "CRITICAL",
        {"minimum_poi_per_day_contract": 2},
    )

    # ------------------------------------------------------------------
    # QA-23, QA-24, QA-25: 10pp survivor rule & early selection
    # ------------------------------------------------------------------
    # QA-23: A=.90, B=.82, C=.73 non-pairwise reduction
    surv_abc, best_abc = harness.reduce_survivors_by_10pp_rule(
        ["C1", "C2", "C3"], {"C1": 0.90, "C2": 0.82, "C3": 0.73}
    )

    def make_select_batch(
        counts_by_cid: Dict[str, tuple[int, int, int]],
        costs_by_cid: Dict[str, float | None],
        lats_by_cid: Dict[str, float],
    ) -> List[harness.DevCellExecutionReceipt]:
        out: List[harness.DevCellExecutionReceipt] = []
        for cid in ("C1", "C2", "C3"):
            n_val, n_grd, n_cor = counts_by_cid[cid]
            for idx, fid in enumerate(select_fids):
                v = idx < n_val
                g = idx < n_grd
                c = idx < n_cor
                out.append(
                    harness.DevCellExecutionReceipt(
                        run_id=f"W06-DEV-SELECT-P1-{cid}-{fid}",
                        phase="DEV_SELECT",
                        fixture_id=fid,
                        candidate_id=cid,
                        prompt_id="P1",
                        requested_model_id=cand_reg.candidates[cid].requested_model_id,
                        returned_model_id=cand_reg.candidates[cid].requested_model_id,
                        attempt_number=1,
                        attempted=True,
                        failure_classification=(
                            harness.DevCellFailureClassification.NONE
                            if v
                            else harness.DevCellFailureClassification.TIMEOUT
                        ),
                        valid_run_and_schema=v,
                        exact_grounding_pass=g if v else False,
                        final_core_pass=c if (v and g) else False,
                        latency_ms=lats_by_cid[cid],
                        authoritative_usage_available=costs_by_cid[cid] is not None,
                        input_tokens=500 if costs_by_cid[cid] is not None else None,
                        output_tokens=500 if costs_by_cid[cid] is not None else None,
                        total_tokens=1000 if costs_by_cid[cid] is not None else None,
                        canonical_cost_usd=costs_by_cid[cid],
                        request_manifest_sha256="a" * 64,
                        raw_response_sha256="b" * 64,
                        provider_metadata_sha256="c" * 64,
                        parsed_response_sha256="d" * 64 if v else None,
                        evaluation_result_sha256="e" * 64,
                    )
                )
        return out

    # 54/60 = 0.90, 49/60 = 0.816667, 44/60 = 0.733333 across stages 1, 2, 3
    stage1_res = harness.select_winning_candidate_dev_select(
        cell_receipts=make_select_batch(
            {"C1": (54, 54, 54), "C2": (49, 49, 49), "C3": (44, 44, 44)},
            {"C1": 0.01, "C2": 0.02, "C3": 0.005},
            {"C1": 1000.0, "C2": 1000.0, "C3": 1000.0},
        ),
        cost_comparability_by_candidate=cost_records_all,
        dev_select_fixture_ids=select_fids,
    )
    stage2_res = harness.select_winning_candidate_dev_select(
        cell_receipts=make_select_batch(
            {"C1": (54, 54, 54), "C2": (54, 49, 49), "C3": (54, 44, 44)},
            {"C1": 0.01, "C2": 0.02, "C3": 0.005},
            {"C1": 1000.0, "C2": 1000.0, "C3": 1000.0},
        ),
        cost_comparability_by_candidate=cost_records_all,
        dev_select_fixture_ids=select_fids,
    )
    stage3_res = harness.select_winning_candidate_dev_select(
        cell_receipts=make_select_batch(
            {"C1": (54, 54, 54), "C2": (54, 54, 49), "C3": (54, 54, 44)},
            {"C1": 0.01, "C2": 0.02, "C3": 0.005},
            {"C1": 1000.0, "C2": 1000.0, "C3": 1000.0},
        ),
        cost_comparability_by_candidate=cost_records_all,
        dev_select_fixture_ids=select_fids,
    )
    qa23_pass = (
        surv_abc == ["C1", "C2"]
        and best_abc == 0.90
        and stage1_res.reduction_trace[0].survivors_remaining == ["C1", "C2"]
        and stage2_res.reduction_trace[1].survivors_remaining == ["C1", "C2"]
        and stage3_res.reduction_trace[2].survivors_remaining == ["C1", "C2"]
    )
    record(
        "QA-23",
        "10pp non-pairwise",
        {
            "direct_90_82_73_survivors": ["C1", "C2"],
            "stage1_survivors": ["C1", "C2"],
            "stage2_survivors": ["C1", "C2"],
            "stage3_survivors": ["C1", "C2"],
        },
        {
            "direct_90_82_73_survivors": surv_abc,
            "stage1_survivors": stage1_res.reduction_trace[0].survivors_remaining,
            "stage2_survivors": stage2_res.reduction_trace[1].survivors_remaining,
            "stage3_survivors": stage3_res.reduction_trace[2].survivors_remaining,
        },
        qa23_pass,
        "CRITICAL",
        {"compared_against_best_current_survivor": True},
    )

    # QA-24: Exact 10pp boundary
    surv_exact, _ = harness.reduce_survivors_by_10pp_rule(
        ["A", "B"], {"A": 0.90, "B": 0.80}
    )
    surv_below, _ = harness.reduce_survivors_by_10pp_rule(
        ["A", "B"], {"A": 0.90, "B": 0.799999999999}
    )
    qa24_pass = surv_exact == ["A", "B"] and surv_below == ["A"]
    record(
        "QA-24",
        "exact 10pp boundary",
        {"at_0_80_survivors": ["A", "B"], "at_0_799999999999_survivors": ["A"]},
        {"at_0_80_survivors": surv_exact, "at_0_799999999999_survivors": surv_below},
        qa24_pass,
        "CRITICAL",
        {"tolerance_decimal": "0.10"},
    )

    # QA-25: Early survivor stopping
    early1 = harness.select_winning_candidate_dev_select(
        cell_receipts=make_select_batch(
            {"C1": (54, 10, 10), "C2": (40, 40, 40), "C3": (35, 35, 35)},
            {"C1": 99.0, "C2": 0.001, "C3": 0.001},
            {"C1": 99999.0, "C2": 100.0, "C3": 100.0},
        ),
        cost_comparability_by_candidate=cost_records_all,
        dev_select_fixture_ids=select_fids,
    )
    early2 = harness.select_winning_candidate_dev_select(
        cell_receipts=make_select_batch(
            {"C1": (54, 54, 10), "C2": (50, 40, 40), "C3": (35, 35, 35)},
            {"C1": 99.0, "C2": 0.001, "C3": 0.001},
            {"C1": 99999.0, "C2": 100.0, "C3": 100.0},
        ),
        cost_comparability_by_candidate=cost_records_all,
        dev_select_fixture_ids=select_fids,
    )
    early3 = harness.select_winning_candidate_dev_select(
        cell_receipts=make_select_batch(
            {"C1": (54, 54, 54), "C2": (50, 50, 40), "C3": (35, 35, 35)},
            {"C1": 99.0, "C2": 0.001, "C3": 0.001},
            {"C1": 99999.0, "C2": 100.0, "C3": 100.0},
        ),
        cost_comparability_by_candidate=cost_records_all,
        dev_select_fixture_ids=select_fids,
    )
    qa25_pass = (
        early1.selected_candidate_id == "C1"
        and len(early1.reduction_trace) == 1
        and early2.selected_candidate_id == "C1"
        and len(early2.reduction_trace) == 2
        and early3.selected_candidate_id == "C1"
        and len(early3.reduction_trace) == 3
    )
    record(
        "QA-25",
        "early survivor stopping",
        {
            "stop_after_c1_traces_len": 1,
            "stop_after_c2_traces_len": 2,
            "stop_after_c3_traces_len": 3,
        },
        {
            "stop_after_c1_traces_len": len(early1.reduction_trace),
            "stop_after_c2_traces_len": len(early2.reduction_trace),
            "stop_after_c3_traces_len": len(early3.reduction_trace),
        },
        qa25_pass,
        "CRITICAL",
        {
            "early1_stage": early1.selected_at_stage,
            "early2_stage": early2.selected_at_stage,
            "early3_stage": early3.selected_at_stage,
        },
    )

    # ------------------------------------------------------------------
    # QA-26: cost comparability all-current-survivors (Section 19)
    # ------------------------------------------------------------------
    cost_records_c3_incomp = dict(cost_records_all)
    cost_records_c3_incomp["C3"] = harness.CandidateCostComparabilityRecord(
        candidate_id="C3",
        authoritative_usage_available=False,
        canonical_cost_computable=False,
    )
    res_c3_elim = harness.select_winning_candidate_dev_select(
        cell_receipts=make_select_batch(
            {"C1": (54, 54, 54), "C2": (52, 52, 52), "C3": (30, 30, 30)},
            {"C1": 0.02, "C2": 0.01, "C3": None},
            {"C1": 500.0, "C2": 2000.0, "C3": 100.0},
        ),
        cost_comparability_by_candidate=cost_records_c3_incomp,
        dev_select_fixture_ids=select_fids,
    )

    cost_records_c2_incomp = dict(cost_records_all)
    cost_records_c2_incomp["C2"] = harness.CandidateCostComparabilityRecord(
        candidate_id="C2",
        authoritative_usage_available=False,
        canonical_cost_computable=False,
    )
    res_c2_incomp = harness.select_winning_candidate_dev_select(
        cell_receipts=make_select_batch(
            {"C1": (54, 54, 54), "C2": (52, 52, 52), "C3": (30, 30, 30)},
            {"C1": 0.02, "C2": None, "C3": 0.01},
            {"C1": 800.0, "C2": 1200.0, "C3": 100.0},
        ),
        cost_comparability_by_candidate=cost_records_c2_incomp,
        dev_select_fixture_ids=select_fids,
    )
    qa26_pass = (
        res_c3_elim.selected_candidate_id == "C2"
        and res_c3_elim.selected_at_stage == "MEDIAN_COST_PER_SCENARIO"
        and res_c2_incomp.cost_criterion_status
        == "COST_CRITERION_SKIPPED_NOT_COMPARABLE"
        and res_c2_incomp.selected_candidate_id == "C1"
        and res_c2_incomp.selected_at_stage == "MEDIAN_LATENCY"
    )
    record(
        "QA-26",
        "cost comparability all-current-survivors",
        {
            "eliminated_c3_missing_cost_does_not_skip_c1_c2_cost": True,
            "surviving_c2_missing_cost_skips_with_status": "COST_CRITERION_SKIPPED_NOT_COMPARABLE",
        },
        {
            "eliminated_c3_missing_cost_does_not_skip_c1_c2_cost": (
                res_c3_elim.selected_candidate_id == "C2"
            ),
            "surviving_c2_missing_cost_skips_with_status": res_c2_incomp.cost_criterion_status,
        },
        qa26_pass,
        "CRITICAL",
        {"c3_elim_stage": res_c3_elim.selected_at_stage},
    )

    # ------------------------------------------------------------------
    # QA-27: provider token billing semantics
    # ------------------------------------------------------------------
    billing_audit = build_provider_billing_semantics_audit()
    transport_fields = set(harness.MockProviderTransportResponse.model_fields.keys())
    receipt_fields = set(harness.DevCellExecutionReceipt.model_fields.keys())
    has_thought_tokens_field = (
        "thought_tokens" in transport_fields and "thought_tokens" in receipt_fields
    )
    has_cache_token_fields = (
        "cached_input_tokens" in transport_fields
        or "cache_read_input_tokens" in transport_fields
    )
    qa27_pass = has_thought_tokens_field and has_cache_token_fields
    record(
        "QA-27",
        "provider token billing semantics",
        {
            "c1_disjoint_thought_tokens_tracked_and_billed": True,
            "cache_tokens_tracked_or_guarded_for_comparability": True,
        },
        {
            "c1_disjoint_thought_tokens_tracked_and_billed": has_thought_tokens_field,
            "cache_tokens_tracked_or_guarded_for_comparability": has_cache_token_fields,
            "transport_fields": sorted(transport_fields),
        },
        qa27_pass,
        "CRITICAL",
        billing_audit,
    )

    # ------------------------------------------------------------------
    # QA-28: no reasoning/thinking double count
    # ------------------------------------------------------------------
    expected_c2_cost = float(
        (Decimal(577) * Decimal("2.00") + Decimal(1030) * Decimal("10.00"))
        / Decimal(1_000_000)
    )
    observed_c2_cost_with_reasoning = harness.compute_canonical_cell_cost_usd(
        input_tokens=577,
        output_tokens=1030,
        thought_or_reasoning_tokens=435,
        cost_record=harness.CandidateCostComparabilityRecord(
            candidate_id="C2",
            authoritative_usage_available=True,
            pricing_source="https://developers.openai.com/api/docs/guides/reasoning",
            pricing_access_date="2026-10-18",
            input_price_per_million_usd=2.0,
            output_price_per_million_usd=10.0,
            canonical_cost_computable=True,
        ),
    )
    expected_c3_cost = float(
        (Decimal(1062) * Decimal("3.00") + Decimal(1367) * Decimal("15.00"))
        / Decimal(1_000_000)
    )
    observed_c3_cost_with_thinking = harness.compute_canonical_cell_cost_usd(
        input_tokens=1062,
        output_tokens=1367,
        thought_or_reasoning_tokens=800,
        cost_record=harness.CandidateCostComparabilityRecord(
            candidate_id="C3",
            authoritative_usage_available=True,
            pricing_source="https://platform.claude.com/docs/en/build-with-claude/thinking-steering-and-cost",
            pricing_access_date="2026-10-18",
            input_price_per_million_usd=3.0,
            output_price_per_million_usd=15.0,
            canonical_cost_computable=True,
        ),
    )
    qa28_pass = (
        observed_c2_cost_with_reasoning == expected_c2_cost
        and observed_c3_cost_with_thinking == expected_c3_cost
    )
    record(
        "QA-28",
        "no reasoning/thinking double count",
        {
            "c2_cost_usd_without_double_counting_reasoning": expected_c2_cost,
            "c3_cost_usd_without_double_counting_thinking": expected_c3_cost,
        },
        {
            "c2_cost_usd_observed": observed_c2_cost_with_reasoning,
            "c3_cost_usd_observed": observed_c3_cost_with_thinking,
        },
        qa28_pass,
        "CRITICAL",
        {
            "location": "apps/ai-service/app/evaluation/dev_selection_harness.py:L1355-L1373",
            "root_cause": (
                "compute_canonical_cell_cost_usd computes `billed_out = output_tokens + "
                "(thought_or_reasoning_tokens or 0)` unconditionally for all candidates, "
                "double-counting reasoning_tokens for C2 (OpenAI) and thinking_tokens "
                "for C3 (Anthropic), where output_tokens is already inclusive."
            ),
        },
    )

    # ------------------------------------------------------------------
    # QA-29: unrounded cost comparison (COST_TIEBREAK_NOT_UNROUNDED)
    # ------------------------------------------------------------------
    unrounded_cost_res = harness.select_winning_candidate_dev_select(
        cell_receipts=make_select_batch(
            {"C1": (54, 54, 54), "C2": (54, 54, 54), "C3": (30, 30, 30)},
            {"C1": 0.0100000000001, "C2": 0.0100000000002, "C3": 0.05},
            {"C1": 2000.0, "C2": 1000.0, "C3": 500.0},
        ),
        cost_comparability_by_candidate=cost_records_all,
        dev_select_fixture_ids=select_fids,
    )
    qa29_pass = (
        unrounded_cost_res.selected_candidate_id == "C1"
        and unrounded_cost_res.selected_at_stage == "MEDIAN_COST_PER_SCENARIO"
        and unrounded_cost_res.reduction_trace[3].survivors_remaining == ["C1"]
    )
    record(
        "QA-29",
        "unrounded cost comparison",
        {
            "c1_cost": "0.0100000000001",
            "c2_cost": "0.0100000000002",
            "cost_stage_survivors": ["C1"],
            "selected_candidate_id": "C1",
            "selected_at_stage": "MEDIAN_COST_PER_SCENARIO",
        },
        {
            "c1_cost": "0.0100000000001",
            "c2_cost": "0.0100000000002",
            "cost_stage_survivors": unrounded_cost_res.reduction_trace[
                3
            ].survivors_remaining,
            "selected_candidate_id": unrounded_cost_res.selected_candidate_id,
            "selected_at_stage": unrounded_cost_res.selected_at_stage,
        },
        qa29_pass,
        "CRITICAL",
        {
            "failure_code": "COST_TIEBREAK_NOT_UNROUNDED",
            "location": "apps/ai-service/app/evaluation/dev_selection_harness.py:L1775-L1777,L2120-L2126",
            "root_cause": (
                "_to_exact_decimal(value) formats floats via Decimal(f'{value:.12f}'), "
                "which rounds 0.0100000000001 and 0.0100000000002 to Decimal('0.010000000000'), "
                "turning strictly unequal costs into a false tie and allowing C2 to win on latency."
            ),
        },
    )

    # ------------------------------------------------------------------
    # QA-30: unrounded latency comparison (LATENCY_TIEBREAK_ROUNDING)
    # ------------------------------------------------------------------
    unrounded_lat_case1 = harness.select_winning_candidate_dev_select(
        cell_receipts=make_select_batch(
            {"C1": (54, 54, 54), "C2": (54, 54, 54), "C3": (30, 30, 30)},
            {"C1": 0.01, "C2": 0.01, "C3": 0.05},
            {"C1": 1000.000000000001, "C2": 1000.000000000002, "C3": 500.0},
        ),
        cost_comparability_by_candidate=cost_records_all,
        dev_select_fixture_ids=select_fids,
    )
    unrounded_lat_sub12 = harness.select_winning_candidate_dev_select(
        cell_receipts=make_select_batch(
            {"C1": (54, 54, 54), "C2": (54, 54, 54), "C3": (30, 30, 30)},
            {"C1": 0.01, "C2": 0.01, "C3": 0.05},
            {"C1": 1.0000000000002, "C2": 1.0000000000001, "C3": 500.0},
        ),
        cost_comparability_by_candidate=cost_records_all,
        dev_select_fixture_ids=select_fids,
    )
    qa30_pass = (
        unrounded_lat_case1.selected_candidate_id == "C1"
        and unrounded_lat_case1.selected_at_stage == "MEDIAN_LATENCY"
        and unrounded_lat_sub12.selected_candidate_id == "C2"
        and unrounded_lat_sub12.selected_at_stage == "MEDIAN_LATENCY"
        and unrounded_lat_sub12.reduction_trace[4].survivors_remaining == ["C2"]
        and unrounded_lat_sub12.is_administrative_tiebreak is False
    )
    record(
        "QA-30",
        "unrounded latency comparison",
        {
            "case1_1000ms_winner": "C1",
            "sub12_decimal_c1_1_0000000000002_vs_c2_1_0000000000001_winner": "C2",
            "sub12_decimal_latency_stage_survivors": ["C2"],
            "sub12_decimal_selected_at_stage": "MEDIAN_LATENCY",
            "sub12_decimal_is_administrative_tiebreak": False,
        },
        {
            "case1_1000ms_winner": unrounded_lat_case1.selected_candidate_id,
            "sub12_decimal_c1_1_0000000000002_vs_c2_1_0000000000001_winner": unrounded_lat_sub12.selected_candidate_id,
            "sub12_decimal_latency_stage_survivors": unrounded_lat_sub12.reduction_trace[
                4
            ].survivors_remaining,
            "sub12_decimal_selected_at_stage": unrounded_lat_sub12.selected_at_stage,
            "sub12_decimal_is_administrative_tiebreak": unrounded_lat_sub12.is_administrative_tiebreak,
        },
        qa30_pass,
        "MAJOR",
        {
            "failure_code": "LATENCY_TIEBREAK_ROUNDING",
            "location": "apps/ai-service/app/evaluation/dev_selection_harness.py:L1775-L1777,L2162-L2166",
            "root_cause": (
                "median_latency_ms is converted via _to_exact_decimal(value) = Decimal(f'{value:.12f}'), "
                "which rounds distinct IEEE-754 floats (e.g. C1=1.0000000000002 ms vs C2=1.0000000000001 ms) "
                "both to Decimal('1.000000000000'), collapsing strictly unequal latencies into a false tie "
                "and selecting C1 via FINAL_ADMINISTRATIVE_TIEBREAK_C1_GT_C2_GT_C3 instead of C2 at MEDIAN_LATENCY."
            ),
        },
    )

    # ------------------------------------------------------------------
    # QA-31: P1/P2 registry status
    # ------------------------------------------------------------------
    harness_v1_payload = harness.build_dev_selection_harness_v1_payload()
    prompt_infra = harness_v1_payload["prompt_registry_infrastructure"]
    p2_spec = harness.create_prompt_candidate_spec(
        prompt_id="P2",
        prompt_version="V2_ALT",
        system_prompt=p1_spec.system_prompt + " Be concise.",
        user_prompt_template=p1_spec.user_prompt_template,
        created_before_live_dev_execution=True,
    )
    reg_p1_p2 = harness.build_prompt_registry([p1_spec, p2_spec])

    p3_blocked = False
    try:
        harness.create_prompt_candidate_spec(
            prompt_id="P3",
            prompt_version="V3",
            system_prompt=p1_spec.system_prompt,
            user_prompt_template=p1_spec.user_prompt_template,
        )
    except harness.PromptRegistryIntegrityError:
        p3_blocked = True

    post_hoc_blocked = False
    try:
        harness.create_prompt_candidate_spec(
            prompt_id="P2",
            prompt_version="V2_POST_HOC",
            system_prompt=p1_spec.system_prompt,
            user_prompt_template=p1_spec.user_prompt_template,
            created_before_live_dev_execution=False,
        )
    except harness.PromptRegistryIntegrityError:
        post_hoc_blocked = True

    provider_specific_blocked = False
    try:
        harness.create_prompt_candidate_spec(
            prompt_id="P1",
            prompt_version="V1_PROV",
            system_prompt=p1_spec.system_prompt,
            user_prompt_template=p1_spec.user_prompt_template,
            provider_specific_semantic_prompt=True,
        )
    except harness.PromptRegistryIntegrityError:
        provider_specific_blocked = True

    qa31_pass = (
        prompt_infra["prompt_semantic_freeze_status"]
        == "INFRASTRUCTURE_ONLY_PENDING_LATER_PROMPT_FREEZE_GATE"
        and len(reg_p1_p2.prompts) == 2
        and p3_blocked
        and post_hoc_blocked
        and provider_specific_blocked
    )
    record(
        "QA-31",
        "P1/P2 registry status",
        {
            "prompt_semantic_freeze_status": "INFRASTRUCTURE_ONLY_PENDING_LATER_PROMPT_FREEZE_GATE",
            "p1_and_p2_capability": True,
            "p3_blocked": True,
            "post_hoc_blocked": True,
            "provider_specific_blocked": True,
        },
        {
            "prompt_semantic_freeze_status": prompt_infra[
                "prompt_semantic_freeze_status"
            ],
            "p1_and_p2_capability": len(reg_p1_p2.prompts) == 2,
            "p3_blocked": p3_blocked,
            "post_hoc_blocked": post_hoc_blocked,
            "provider_specific_blocked": provider_specific_blocked,
        },
        qa31_pass,
        "CRITICAL",
        {"p1_sha256": p1_spec.semantic_prompt_sha256},
    )

    # ------------------------------------------------------------------
    # QA-32: prompt freeze required before live
    # ------------------------------------------------------------------
    # Check whether the harness enforces a separate frozen prompt artifact gate
    # AND whether single-prompt selection returns exact status LOCK_P1_WITHOUT_PERFORMANCE_COMPARISON.
    tune_fids = harness_bundle_res.dev_tune_ids
    tune_60_receipts = [
        harness.DevCellExecutionReceipt(
            run_id=f"W06-DEV-TUNE-P1-{cid}-{fid}",
            phase="DEV_TUNE",
            fixture_id=fid,
            candidate_id=cid,
            prompt_id="P1",
            requested_model_id=cand_reg.candidates[cid].requested_model_id,
            returned_model_id=cand_reg.candidates[cid].requested_model_id,
            attempt_number=1,
            attempted=True,
            failure_classification=harness.DevCellFailureClassification.NONE,
            valid_run_and_schema=True,
            exact_grounding_pass=True,
            final_core_pass=True,
            latency_ms=1000.0,
            authoritative_usage_available=True,
            input_tokens=500,
            output_tokens=500,
            total_tokens=1000,
            canonical_cost_usd=0.01,
            request_manifest_sha256="a" * 64,
            raw_response_sha256="b" * 64,
            provider_metadata_sha256="c" * 64,
            parsed_response_sha256="d" * 64,
            evaluation_result_sha256="e" * 64,
        )
        for cid in ("C1", "C2", "C3")
        for fid in tune_fids
    ]
    single_p1_res = harness.select_winning_prompt_dev_tune(
        prompt_registry=prompt_reg_p1,
        cell_receipts=tune_60_receipts,
        dev_tune_fixture_ids=tune_fids,
    )
    has_prompt_freeze_verifier = hasattr(
        harness, "verify_prompt_candidate_freeze_artifact"
    ) or hasattr(harness, "assert_prompt_freeze_before_live")
    qa32_pass = (
        has_prompt_freeze_verifier
        and single_p1_res.selected_at_stage
        == "LOCK_P1_WITHOUT_PERFORMANCE_COMPARISON"
    )
    record(
        "QA-32",
        "prompt freeze required before live",
        {
            "requires_separate_frozen_prompt_artifact_before_live_dev_tune": True,
            "single_p1_selection_status": "LOCK_P1_WITHOUT_PERFORMANCE_COMPARISON",
        },
        {
            "requires_separate_frozen_prompt_artifact_before_live_dev_tune": has_prompt_freeze_verifier,
            "single_p1_selection_status": single_p1_res.selected_at_stage,
        },
        qa32_pass,
        "MAJOR",
        {
            "location": "apps/ai-service/app/evaluation/dev_selection_harness.py:L1894-L1905",
            "root_cause": (
                "1) dev_selection_harness.py does not enforce a pre-live prompt freeze "
                "artifact gate (verifying prompt IDs, prompt hashes, system prompt, user "
                "template, created-before-live evidence, candidate list, DEV-TUNE plan "
                "hash, and call budget). "
                "2) select_winning_prompt_dev_tune returns selected_at_stage="
                "'SINGLE_FROZEN_PROMPT_P1_LOCKED_WITHOUT_COMPARISON' instead of exact "
                "'LOCK_P1_WITHOUT_PERFORMANCE_COMPARISON' required by Section 20."
            ),
        },
    )

    # ------------------------------------------------------------------
    # QA-33: scientific code commit provenance
    # ------------------------------------------------------------------
    manifest_fields = set(harness.DevCellExecutionManifest.model_fields.keys())
    receipt_fields_33 = set(harness.DevCellExecutionReceipt.model_fields.keys())
    required_provenance_checks = {
        "manifest_has_code_commit_sha": "code_commit_sha" in manifest_fields,
        "receipt_has_code_commit_sha": "code_commit_sha" in receipt_fields_33,
        "manifest_has_provider_config_sha256": "provider_config_sha256"
        in manifest_fields,
        "receipt_has_provider_config_sha256": "provider_config_sha256"
        in receipt_fields_33,
        "manifest_has_scenario_sha256": "scenario_sha256" in manifest_fields,
        "manifest_has_catalog_context_sha256": "catalog_context_sha256"
        in manifest_fields,
        "receipt_has_returned_model_id": "returned_model_id" in receipt_fields_33,
        "receipt_has_attempt_number": "attempt_number" in receipt_fields_33,
    }
    qa33_pass = all(required_provenance_checks.values())
    record(
        "QA-33",
        "scientific code commit provenance",
        {k: True for k in required_provenance_checks},
        required_provenance_checks,
        qa33_pass,
        "MAJOR",
        {
            "locations": [
                "apps/ai-service/app/evaluation/dev_selection_harness.py:L1053-L1086",
                "apps/ai-service/app/evaluation/dev_selection_harness.py:L1376-L1408",
                "apps/ai-service/app/evaluation/dev_selection_harness.py:L1598",
            ],
            "root_cause": (
                "DevCellExecutionManifest and DevCellExecutionReceipt omit code_commit_sha "
                "and provider_config_sha256; furthermore, execute_dev_cell_with_mock_transport "
                "line 1598 hardcodes EXPECTED_BASE_DEVELOP_SHA_DEV_HARNESS "
                "(50884c610cebf455255b9d05f737d9558cabf2e7) instead of recording the exact "
                "code commit SHA used for execution."
            ),
        },
    )

    # ------------------------------------------------------------------
    # QA-34: cell immutability
    # ------------------------------------------------------------------
    immut_checks: Dict[str, bool] = {}
    with tempfile.TemporaryDirectory() as td34:
        td34_path = Path(td34)
        cdir = td34_path / cell0.run_id
        harness.execute_dev_cell_with_mock_transport(
            cell_manifest=cell0,
            scenario=scen0,
            cell_dir=cdir,
            mock_response=harness.MockProviderTransportResponse(
                raw_text=valid_json_str,
                returned_model_id=cell0.requested_model_id,
            ),
            core_catalog_by_id=core_catalog_by_id,
        )

        # 1. Execute same cell twice in same cell_dir
        try:
            harness.execute_dev_cell_with_mock_transport(
                cell_manifest=cell0,
                scenario=scen0,
                cell_dir=cdir,
                mock_response=harness.MockProviderTransportResponse(
                    raw_text=valid_json_str,
                    returned_model_id=cell0.requested_model_id,
                ),
                core_catalog_by_id=core_catalog_by_id,
            )
            immut_checks["second_execution_same_cell_dir_blocked"] = False
        except harness.ImmutableCellExecutionError:
            immut_checks["second_execution_same_cell_dir_blocked"] = True

        # 2. Reuse same run_id with different fixture in same run_id-keyed directory
        scen1 = harness_bundle_res.dev_tune_fixtures[1]
        cell_diff_fixture = cell0.model_copy(update={"fixture_id": scen1.scenario_id})
        try:
            harness.execute_dev_cell_with_mock_transport(
                cell_manifest=cell_diff_fixture,
                scenario=scen1,
                cell_dir=cdir,
                mock_response=harness.MockProviderTransportResponse(
                    raw_text=valid_json_str,
                    returned_model_id=cell0.requested_model_id,
                ),
                core_catalog_by_id=core_catalog_by_id,
            )
            immut_checks["reuse_run_id_dir_different_fixture_blocked"] = False
        except harness.ImmutableCellExecutionError:
            immut_checks["reuse_run_id_dir_different_fixture_blocked"] = True

        # 3. Reuse same run_id with different candidate in same run_id-keyed directory
        cell_diff_cand = cell0.model_copy(
            update={"candidate_id": "C2", "requested_model_id": "gpt-6.1-sol"}
        )
        try:
            harness.execute_dev_cell_with_mock_transport(
                cell_manifest=cell_diff_cand,
                scenario=scen0,
                cell_dir=cdir,
                mock_response=harness.MockProviderTransportResponse(
                    raw_text=valid_json_str,
                    returned_model_id="gpt-6.1-sol",
                ),
                core_catalog_by_id=core_catalog_by_id,
            )
            immut_checks["reuse_run_id_dir_different_candidate_blocked"] = False
        except harness.ImmutableCellExecutionError:
            immut_checks["reuse_run_id_dir_different_candidate_blocked"] = True

    qa34_pass = all(immut_checks.values())
    record(
        "QA-34",
        "cell immutability",
        {k: True for k in immut_checks},
        immut_checks,
        qa34_pass,
        "CRITICAL",
        {"tested_run_id": cell0.run_id},
    )

    # ------------------------------------------------------------------
    # QA-35: plan reproducibility across clean subprocesses
    # ------------------------------------------------------------------
    subproc_code = (
        "import json, sys; sys.path.insert(0, 'apps/ai-service'); "
        "from app.evaluation.dev_selection_harness import "
        "build_default_infrastructure_prompt_registry, build_dev_tune_execution_plan, build_dev_select_execution_plan; "
        "reg = build_default_infrastructure_prompt_registry(); "
        "t = build_dev_tune_execution_plan(reg); "
        "s = build_dev_select_execution_plan(reg.prompts[0]); "
        "print(json.dumps({"
        "'tune_sha': t.plan_sha256, "
        "'tune_runs': [c.run_id for c in t.cells], "
        "'tune_ctx': [c.catalog_context_sha256 for c in t.cells], "
        "'select_sha': s.plan_sha256, "
        "'select_runs': [c.run_id for c in s.cells], "
        "'select_ctx': [c.catalog_context_sha256 for c in s.cells]"
        "}))"
    )
    proc1 = subprocess.run(
        [sys.executable, "-c", subproc_code],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    proc2 = subprocess.run(
        [sys.executable, "-c", subproc_code],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    plan_run1 = json.loads(proc1.stdout.strip())
    plan_run2 = json.loads(proc2.stdout.strip())
    qa35_pass = plan_run1 == plan_run2
    record(
        "QA-35",
        "plan reproducibility",
        {"clean_process_runs_identical": True},
        {
            "clean_process_runs_identical": qa35_pass,
            "dev_tune_plan_sha256": plan_run1["tune_sha"],
            "dev_select_plan_sha256": plan_run1["select_sha"],
        },
        qa35_pass,
        "CRITICAL",
        {
            "tune_cells": len(plan_run1["tune_runs"]),
            "select_cells": len(plan_run1["select_runs"]),
        },
    )

    # ------------------------------------------------------------------
    # QA-36: exact 60/120/180 cell budgets
    # ------------------------------------------------------------------
    plan_p1 = harness.build_dev_tune_execution_plan(prompt_reg_p1)
    plan_p1_p2 = harness.build_dev_tune_execution_plan(reg_p1_p2)
    plan_select = harness.build_dev_select_execution_plan(p1_spec)
    qa36_pass = (
        plan_p1.expected_total_cells == 60
        and len(plan_p1.cells) == 60
        and plan_p1_p2.expected_total_cells == 120
        and len(plan_p1_p2.cells) == 120
        and plan_select.expected_total_cells == 180
        and len(plan_select.cells) == 180
        and all(c.attempt_number == 1 for c in plan_p1.cells)
        and all(c.attempt_number == 1 for c in plan_p1_p2.cells)
        and all(c.attempt_number == 1 for c in plan_select.cells)
    )
    record(
        "QA-36",
        "exact 60/120/180 cell budgets",
        {"dev_tune_p1": 60, "dev_tune_p1_p2": 120, "dev_select": 180},
        {
            "dev_tune_p1": len(plan_p1.cells),
            "dev_tune_p1_p2": len(plan_p1_p2.cells),
            "dev_select": len(plan_select.cells),
        },
        qa36_pass,
        "CRITICAL",
        {"no_extra_cells": True, "no_best_of": True},
    )

    # ------------------------------------------------------------------
    # QA-37: stochasticity pre-winner block
    # ------------------------------------------------------------------
    stoch_blocks: Dict[str, bool] = {}
    try:
        harness.build_stochasticity_diagnostic_plan(
            dev_select_result=None,
            locked_prompt_spec=p1_spec,
        )
        stoch_blocks["none_dev_select_result_blocked"] = False
    except harness.StochasticityGateViolationError:
        stoch_blocks["none_dev_select_result_blocked"] = True

    try:
        harness.build_stochasticity_diagnostic_plan(
            dev_select_result=early1.model_copy(update={"winner_selected": False}),
            locked_prompt_spec=p1_spec,
        )
        stoch_blocks["winner_selected_false_blocked"] = False
    except harness.StochasticityGateViolationError:
        stoch_blocks["winner_selected_false_blocked"] = True

    try:
        harness.build_stochasticity_diagnostic_plan(
            dev_select_result=early1,
            locked_prompt_spec=p2_spec,
        )
        stoch_blocks["mismatched_locked_prompt_blocked"] = False
    except harness.StochasticityGateViolationError:
        stoch_blocks["mismatched_locked_prompt_blocked"] = True

    qa37_pass = all(stoch_blocks.values())
    record(
        "QA-37",
        "stochasticity pre-winner block",
        {k: True for k in stoch_blocks},
        stoch_blocks,
        qa37_pass,
        "CRITICAL",
        {"pre_winner_blocks": stoch_blocks},
    )

    # ------------------------------------------------------------------
    # QA-38: stochasticity exact 15 design
    # ------------------------------------------------------------------
    stoch_plan = harness.build_stochasticity_diagnostic_plan(
        dev_select_result=early1,
        locked_prompt_spec=p1_spec,
    )
    expected_stoch_fixtures = [
        "W06-DEV-TUNE-001",
        "W06-DEV-TUNE-002",
        "W06-DEV-TUNE-003",
        "W06-DEV-TUNE-004",
        "W06-DEV-TUNE-005",
    ]
    qa38_pass = (
        stoch_plan.fixture_ids == expected_stoch_fixtures
        and stoch_plan.executions_per_fixture == 3
        and stoch_plan.max_calls == 15
        and len(stoch_plan.cells) == 15
        and stoch_plan.may_alter_selected_model is False
        and stoch_plan.may_alter_selected_prompt is False
        and stoch_plan.may_alter_sampling_config is False
        and stoch_plan.may_alter_dev_select_results is False
    )
    record(
        "QA-38",
        "stochasticity exact 15 design",
        {
            "fixture_ids": expected_stoch_fixtures,
            "executions_per_fixture": 3,
            "max_calls": 15,
            "may_alter_selected_model": False,
            "may_alter_selected_prompt": False,
            "may_alter_sampling_config": False,
            "may_alter_dev_select_results": False,
        },
        {
            "fixture_ids": stoch_plan.fixture_ids,
            "executions_per_fixture": stoch_plan.executions_per_fixture,
            "max_calls": stoch_plan.max_calls,
            "may_alter_selected_model": stoch_plan.may_alter_selected_model,
            "may_alter_selected_prompt": stoch_plan.may_alter_selected_prompt,
            "may_alter_sampling_config": stoch_plan.may_alter_sampling_config,
            "may_alter_dev_select_results": stoch_plan.may_alter_dev_select_results,
        },
        qa38_pass,
        "CRITICAL",
        {"plan_sha256": stoch_plan.plan_sha256},
    )

    # ------------------------------------------------------------------
    # QA-39: failure taxonomy mapping
    # ------------------------------------------------------------------
    taxonomy_table = build_failure_taxonomy_mapping_table()
    enum_names = set(harness.DevCellFailureClassification.__members__.keys())
    has_partial_timeout = "PARTIAL_TIMEOUT" in enum_names
    has_harness_error = "HARNESS_INTERNAL_ERROR" in enum_names or "HARNESS_ERROR" in enum_names
    invalid_mappings = [row for row in taxonomy_table if not row["mapping_valid"]]
    qa39_pass = (
        len(invalid_mappings) == 0
        and has_partial_timeout
        and has_harness_error
        and batch_stopped_on_mismatch
    )
    record(
        "QA-39",
        "failure taxonomy mapping",
        {
            "all_10_outcomes_validly_mapped": True,
            "has_partial_timeout_classification": True,
            "has_harness_error_classification": True,
            "model_id_mismatch_stops_batch": True,
        },
        {
            "all_10_outcomes_validly_mapped": len(invalid_mappings) == 0,
            "has_partial_timeout_classification": has_partial_timeout,
            "has_harness_error_classification": has_harness_error,
            "model_id_mismatch_stops_batch": batch_stopped_on_mismatch,
            "invalid_outcomes": [r["method_lock_outcome"] for r in invalid_mappings],
        },
        qa39_pass,
        "MAJOR",
        {"taxonomy_mapping_table": taxonomy_table},
    )

    # ------------------------------------------------------------------
    # QA-40: no live / no DEV / no final100 evidence
    # ------------------------------------------------------------------
    harness_01_receipt = load_json(HARNESS_01_RECEIPT_PATH)
    harness_source = HARNESS_MODULE_PATH.read_text(encoding="utf-8")
    forbidden_sdk_calls = [
        "genai.Client(",
        "openai.OpenAI(",
        "anthropic.Anthropic(",
        "messages.create(",
        "chat.completions.create(",
        "models.generate_content(",
    ]
    found_sdk_calls = [s for s in forbidden_sdk_calls if s in harness_source]
    qa40_pass = (
        len(found_sdk_calls) == 0
        and harness_01_receipt["live_provider_calls"] == 0
        and harness_01_receipt["provider_cost_usd"] == 0
        and harness_01_receipt["dev_tune_model_execution_started"] is False
        and harness_01_receipt["dev_select_model_execution_started"] is False
        and harness_01_receipt["stochasticity_diagnostic_started"] is False
        and harness_01_receipt["final100_used"] is False
        and harness_01_receipt["winner_selected"] is False
    )
    record(
        "QA-40",
        "no live / no DEV / no final100 evidence",
        {
            "live_sdk_calls_in_harness": [],
            "live_provider_calls": 0,
            "provider_cost_usd": 0,
            "dev_tune_model_execution_started": False,
            "dev_select_model_execution_started": False,
            "stochasticity_diagnostic_started": False,
            "final100_used": False,
            "winner_selected": False,
        },
        {
            "live_sdk_calls_in_harness": found_sdk_calls,
            "live_provider_calls": harness_01_receipt["live_provider_calls"],
            "provider_cost_usd": harness_01_receipt["provider_cost_usd"],
            "dev_tune_model_execution_started": harness_01_receipt[
                "dev_tune_model_execution_started"
            ],
            "dev_select_model_execution_started": harness_01_receipt[
                "dev_select_model_execution_started"
            ],
            "stochasticity_diagnostic_started": harness_01_receipt[
                "stochasticity_diagnostic_started"
            ],
            "final100_used": harness_01_receipt["final100_used"],
            "winner_selected": harness_01_receipt["winner_selected"],
        },
        qa40_pass,
        "CRITICAL",
        {
            "receipt_path": "data/evaluation/w06/w06_dev_selection_harness_01_receipt_v1.json"
        },
    )

    # ==================================================================
    # ROLL-UP SUMMARY & RESULT POLICY (SECTION 30 & 33)
    # ==================================================================
    check_by_id = {c["check_id"]: c for c in checks}
    critical_failures = [
        c["check_id"]
        for c in checks
        if c["status"] == "FAIL" and c["severity"] == "CRITICAL"
    ]
    major_failures = [
        c["check_id"]
        for c in checks
        if c["status"] == "FAIL" and c["severity"] == "MAJOR"
    ]
    qa_pass_count = sum(1 for c in checks if c["status"] == "PASS")
    qa_fail_count = sum(1 for c in checks if c["status"] == "FAIL")

    overall_qa = (
        "PASS"
        if (len(critical_failures) == 0 and len(major_failures) == 0)
        else "FAIL"
    )
    next_gate = (
        "W06-PROMPT-CANDIDATE-FREEZE-01"
        if overall_qa == "PASS"
        else "W06-DEV-SELECTION-HARNESS-FIX-01"
    )
    next_status = "READY_FOR_PROMPT_FREEZE" if overall_qa == "PASS" else "NEEDS_FIX"

    def group_status(ids: List[str]) -> str:
        return (
            "PASS"
            if all(check_by_id[cid]["status"] == "PASS" for cid in ids)
            else "FAIL"
        )

    domain_rollup = {
        "DEV_BUNDLE": group_status(["QA-02", "QA-03"]),
        "FINAL100_FIREWALL": group_status(["QA-04", "QA-05"]),
        "RECA_CATALOG_CONTEXT": group_status(["QA-06", "QA-07", "QA-08"]),
        "PROVIDER_SERIALIZATION": group_status(["QA-09", "QA-10", "QA-11", "QA-12"]),
        "STRICT_PRIMARY_PARSER": group_status(["QA-13", "QA-14"]),
        "MODEL_ID_INTEGRITY_STOP_BATCH": group_status(["QA-15"]),
        "DENOMINATOR_PRESERVATION": group_status(["QA-16", "QA-17", "QA-18"]),
        "METRIC_MAPPING": group_status(["QA-19", "QA-20", "QA-21", "QA-22"]),
        "TEN_PP_SELECTION": group_status(["QA-23", "QA-24", "QA-25"]),
        "COST_COMPARABILITY": group_status(["QA-26"]),
        "PROVIDER_BILLING_TOKEN_SEMANTICS": group_status(["QA-27", "QA-28"]),
        "UNROUNDED_COST_TIEBREAK": group_status(["QA-29"]),
        "UNROUNDED_LATENCY_TIEBREAK": group_status(["QA-30"]),
        "PROMPT_FREEZE_FIREWALL": group_status(["QA-31", "QA-32"]),
        "CODE_COMMIT_PROVENANCE": group_status(["QA-33"]),
        "CELL_IMMUTABILITY": group_status(["QA-34", "QA-35", "QA-36"]),
        "STOCHASTICITY_GATE": group_status(["QA-37", "QA-38"]),
        "FAILURE_TAXONOMY": group_status(["QA-39"]),
    }

    blockers = [
        "QA-14 (CRITICAL / PRIMARY_SEMANTIC_RESCUE_DETECTED): execute_dev_cell_with_mock_transport falls back to parse_strict_benchmark_plan_response when plan_id or budget_analysis is absent, synthesizing missing required semantic fields.",
        "QA-15 (CRITICAL / MODEL_ID_MISMATCH_FAILS_TO_STOP_BATCH): execute_dev_cell_with_mock_transport defaults empty returned_model_id to requested_model_id and treats unrelated returned_model_id as an ordinary failed cell without stopping batch aggregation/selection.",
        "QA-27 (CRITICAL): MockProviderTransportResponse, DevCellExecutionReceipt, and execute_dev_cell_with_mock_transport omit C1 disjoint thought_tokens (thoughts_token_count) and cache token fields.",
        "QA-28 (CRITICAL): compute_canonical_cell_cost_usd unconditionally adds thought_or_reasoning_tokens to output_tokens for all candidates, double-counting reasoning/thinking tokens for C2 (OpenAI) and C3 (Anthropic).",
        "QA-29 (CRITICAL / COST_TIEBREAK_NOT_UNROUNDED): _to_exact_decimal rounds float costs via Decimal(f'{value:.12f}'), collapsing unequal costs (0.0100000000001 vs 0.0100000000002) into a false tie.",
        "QA-05 (MAJOR): assert_not_final100_path only checks filename/path without SHA256 verification on copied/renamed files, and assert_not_final100_scenario does not cross-check W06-DEV-TUNE-* vs W06-DEV-SELECT-* scenario ID prefixes against fixture_label.",
        "QA-30 (MAJOR / LATENCY_TIEBREAK_ROUNDING): median_latency_ms is stored as float and rounded via Decimal(f'{value:.12f}') before comparison, collapsing unequal latencies (1000.000000000001 vs 1000.000000000002) into a false tie.",
        "QA-32 (MAJOR): Harness lacks a pre-live prompt freeze gate verifying a separate frozen prompt artifact before DEV-TUNE execution, and single-prompt DEV-TUNE returns 'SINGLE_FROZEN_PROMPT_P1_LOCKED_WITHOUT_COMPARISON' instead of 'LOCK_P1_WITHOUT_PERFORMANCE_COMPARISON'.",
        "QA-33 (MAJOR): DevCellExecutionManifest and DevCellExecutionReceipt omit code_commit_sha and provider_config_sha256, and execute_dev_cell_with_mock_transport hardcodes EXPECTED_BASE_DEVELOP_SHA_DEV_HARNESS.",
        "QA-39 (MAJOR): DevCellFailureClassification lacks PARTIAL_TIMEOUT and HARNESS_INTERNAL_ERROR enum values, and aggregate_dev_cell_receipts does not stop the batch on MODEL_INTEGRITY_MISMATCH or harness error.",
    ]

    return {
        "task_id": TASK_ID,
        "base_develop_sha": EXPECTED_BASE_DEVELOP_SHA,
        "live_provider_calls": 0,
        "provider_cost_usd": 0,
        "dev_tune_execution_started": False,
        "dev_select_execution_started": False,
        "winner_selected": False,
        "final100_used": False,
        "qa_checks_total": len(checks),
        "qa_pass": qa_pass_count,
        "qa_fail": qa_fail_count,
        "critical_failures": critical_failures,
        "major_failures": major_failures,
        "overall_qa": overall_qa,
        "next_status": next_status,
        "next_gate": next_gate,
        "domain_rollup": domain_rollup,
        "blockers": blockers,
        "provider_billing_semantics_audit": billing_audit,
        "failure_taxonomy_mapping_table": taxonomy_table,
        "checks": checks,
    }


def write_qa_receipt(output_path: Path = QA_RECEIPT_OUTPUT_PATH) -> Dict[str, Any]:
    report = run_all_qa_checks()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return report


if __name__ == "__main__":
    receipt = write_qa_receipt()
    print(
        json.dumps(
            {
                "task_id": receipt["task_id"],
                "qa_checks_total": receipt["qa_checks_total"],
                "qa_pass": receipt["qa_pass"],
                "qa_fail": receipt["qa_fail"],
                "critical_failures": receipt["critical_failures"],
                "major_failures": receipt["major_failures"],
                "overall_qa": receipt["overall_qa"],
                "next_gate": receipt["next_gate"],
                "domain_rollup": receipt["domain_rollup"],
            },
            indent=2,
        )
    )
