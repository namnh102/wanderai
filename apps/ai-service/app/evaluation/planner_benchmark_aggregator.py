"""Deterministic Batch Statistical Aggregation Engine for W06 Itinerary Benchmark (W06-INSTRUMENT-01C).

Grounded in:
- W06-MEASUREMENT-CONTRACT-01 v1.1.0 (data/evaluation/w06/w06_measurement_contract_v1.json)
- W06-INSTRUMENT-01A v1.1.0 & W06-INSTRUMENT-01B v1.0.0

Implements:
- Authoritative assignment-manifest denominator enforcement (including strict FINAL_100 mode: 34 ha-noi, 33 da-nang, 33 ha-long).
- Invalid-run retention in the primary denominator (CORE_SCENARIO_PASS_RATE_ALL_100).
- Secondary diagnostic CORE_SCENARIO_PASS_RATE_CONDITIONAL_ON_VALID_RUNS.
- Count-based item-level Grounded POI Rate and 95% scenario-cluster bootstrap CI (10,000 iterations, seed=20261015).
- Deterministic 95% Wilson score confidence intervals for scenario-level binary proportions.
- Hardened batch-level schedule_violation_rate and estimated_budget_violation_rate denominators.
- Per-destination stratification (ha-noi, da-nang, ha-long) and equal-destination macro average.
- Zero weighted composite scores, zero LLM/network calls, zero unseeded randomness, zero timestamps in payload.
"""
from collections import Counter
import json
import math
from pathlib import Path
import random
from typing import Dict, List, Optional, Sequence, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.evaluation.opening_hours_evaluator import OPENING_HOURS_PARSER_VERSION
from app.evaluation.planner_benchmark_evaluator import (
    EVALUATOR_VERSION,
    ScenarioEvaluationResult,
)
from app.schemas.planner_benchmark import (
    HASH_BASIS_VERSION,
    PRIMARY_BENCHMARK_DESTINATIONS,
)
from app.services.planner_benchmark_runner import (
    MEASUREMENT_CONTRACT_ID,
    MEASUREMENT_CONTRACT_VERSION,
    canonical_json_bytes,
    normalize_lf_bytes,
    sha256_bytes,
    write_canonical_json,
)

AGGREGATOR_VERSION: str = "W06-BATCH-AGGREGATOR-01C-V1.0.0"
BOOTSTRAP_ITERATIONS: int = 10000
BOOTSTRAP_SEED: int = 20261015
WILSON_Z_95: float = 1.959963984540054

FINAL_100_EXPECTED_TOTAL: int = 100
FINAL_100_EXPECTED_ALLOCATION: Dict[str, int] = {
    "ha-noi": 34,
    "da-nang": 33,
    "ha-long": 33,
}
ORDERED_PRIMARY_DESTINATIONS: Tuple[str, ...] = ("ha-noi", "da-nang", "ha-long")


class ConfidenceInterval95(BaseModel):
    """Deterministic 95% Wilson score confidence interval for a binomial proportion k/n."""

    model_config = ConfigDict(extra="forbid")

    k: int
    n: int
    point_estimate: float
    lower: float
    upper: float
    confidence_level: float = 0.95
    method: str = "WILSON_SCORE_95"


class ClusterBootstrapCI95(BaseModel):
    """Deterministic 95% scenario-cluster bootstrap confidence interval for item-level Grounded POI Rate."""

    model_config = ConfigDict(extra="forbid")

    point_estimate: float
    lower: float
    upper: float
    confidence_level: float = 0.95
    method: str = "95_PERCENT_SCENARIO_CLUSTER_BOOTSTRAP_CI"
    resampling_unit: str = "scenario"
    iterations: int = BOOTSTRAP_ITERATIONS
    seed: int = BOOTSTRAP_SEED
    cluster_count: int
    grounded_item_count: int
    poi_visit_item_count: int


class AssignedScenarioSpec(BaseModel):
    """Single assigned scenario entry in an authoritative benchmark assignment manifest."""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str = Field(..., min_length=1)
    destination_slug: str = Field(..., min_length=1)
    scenario_sha256: Optional[str] = None

    @field_validator("destination_slug")
    @classmethod
    def validate_destination_slug(cls, v: str) -> str:
        slug = v.strip()
        if slug not in PRIMARY_BENCHMARK_DESTINATIONS:
            raise ValueError(
                f"Unsupported destination_slug {v!r} in assignment manifest. "
                f"Allowed primary destinations: {sorted(PRIMARY_BENCHMARK_DESTINATIONS.keys())}"
            )
        return slug


class BenchmarkAssignmentManifest(BaseModel):
    """Authoritative list of assigned benchmark scenarios defining the primary denominator."""

    model_config = ConfigDict(extra="forbid")

    manifest_id: str = Field(..., min_length=1)
    manifest_version: str = "1.0.0"
    is_final_100_frozen: bool = False
    assigned_scenarios: List[AssignedScenarioSpec] = Field(..., min_length=1)


class DestinationAggregationSummary(BaseModel):
    """Aggregated benchmark metrics for a single primary destination (ha-noi, da-nang, ha-long)."""

    model_config = ConfigDict(extra="forbid")

    destination_slug: str
    assigned_scenario_count: int
    valid_run_count: int
    invalid_run_count: int
    valid_run_rate: Optional[float] = None
    valid_run_rate_ci95: Optional[ConfidenceInterval95] = None

    core_scenario_pass_count: int
    core_scenario_pass_rate: Optional[float] = None
    core_scenario_pass_rate_ci95: Optional[ConfidenceInterval95] = None
    conditional_core_pass_rate_on_valid_runs: Optional[float] = None

    grounding_evaluable_scenario_count: int
    grounded_item_count: int
    ungrounded_item_count: int
    poi_visit_item_count: int
    grounded_poi_rate: Optional[float] = None
    grounded_poi_rate_cluster_bootstrap_ci95: Optional[ClusterBootstrapCI95] = None

    all_pois_grounded_scenario_count: int
    all_pois_grounded_rate: Optional[float] = None
    all_pois_grounded_rate_ci95: Optional[ConfidenceInterval95] = None

    schedule_evaluable_scenario_count: int
    schedule_violation_scenario_count: int
    schedule_violation_rate: Optional[float] = None
    schedule_violation_rate_ci95: Optional[ConfidenceInterval95] = None

    budget_applicable_scenario_count: int
    budget_not_applicable_scenario_count: int
    budget_violation_scenario_count: int
    estimated_budget_violation_rate: Optional[float] = None
    estimated_budget_violation_rate_ci95: Optional[ConfidenceInterval95] = None

    opening_hours_poi_visit_items: int
    opening_hours_evaluable_items: int
    opening_hours_compliant_items: int
    opening_hours_known_violation_count: int
    opening_hours_unknown_items: int
    opening_hours_evidence_coverage: Optional[float] = None
    opening_hours_compliance_rate_on_evaluable_items: Optional[float] = None
    opening_hours_known_violation_scenario_count: int
    opening_hours_known_violation_scenario_rate: Optional[float] = None
    opening_hours_known_violation_scenario_rate_ci95: Optional[ConfidenceInterval95] = None


class EqualDestinationMacroSummary(BaseModel):
    """Equal-weight (1/3 ha-noi, 1/3 da-nang, 1/3 ha-long) macro averages across primary destinations."""

    model_config = ConfigDict(extra="forbid")

    destinations_included: List[str] = Field(
        default_factory=lambda: list(ORDERED_PRIMARY_DESTINATIONS)
    )
    equal_weight_per_destination: float = round(1.0 / 3.0, 6)

    valid_run_rate_macro: Optional[float] = None
    core_scenario_pass_rate_macro: Optional[float] = None
    conditional_core_pass_rate_on_valid_runs_macro: Optional[float] = None
    grounded_poi_rate_macro: Optional[float] = None
    all_pois_grounded_rate_macro: Optional[float] = None
    schedule_violation_rate_macro: Optional[float] = None
    estimated_budget_violation_rate_macro: Optional[float] = None
    opening_hours_evidence_coverage_macro: Optional[float] = None
    opening_hours_compliance_rate_on_evaluable_items_macro: Optional[float] = None

    metric_macro_status: Dict[str, str] = Field(default_factory=dict)


class GroundingGateEvaluation(BaseModel):
    """Evaluation of the frozen W06 hard roadmap GROUNDING_GATE (grounded_poi_rate == 1.0)."""

    model_config = ConfigDict(extra="forbid")

    gate_name: str = "GROUNDING_GATE"
    required_grounded_poi_rate: float = 1.0
    observed_grounded_poi_rate: Optional[float] = None
    grounded_item_count: int
    poi_visit_item_count: int
    valid_run_count: int
    invalid_run_count: int
    valid_run_rate: float
    gate_pass: bool
    gate_status: str
    interpretation_note: str


class BenchmarkBatchAggregationResult(BaseModel):
    """Deterministic batch aggregation output for W06 planner benchmark evaluations."""

    model_config = ConfigDict(extra="forbid")

    aggregation_version: str = AGGREGATOR_VERSION
    aggregator_version: str = AGGREGATOR_VERSION
    aggregator_code_sha256: str
    evaluator_version: str = EVALUATOR_VERSION
    opening_hours_parser_version: str = OPENING_HOURS_PARSER_VERSION
    measurement_contract_id: str = MEASUREMENT_CONTRACT_ID
    measurement_contract_version: str = MEASUREMENT_CONTRACT_VERSION
    hash_basis_version: str = HASH_BASIS_VERSION
    assignment_manifest_id: str
    assignment_manifest_sha256: str
    final_100_mode: bool

    bootstrap_iterations: int = BOOTSTRAP_ITERATIONS
    bootstrap_seed: int = BOOTSTRAP_SEED

    assigned_scenario_count: int
    valid_run_count: int
    invalid_run_count: int

    valid_run_rate: float
    valid_run_rate_ci95: ConfidenceInterval95

    primary_pass_rate_denominator: int
    core_scenario_pass_count: int
    core_scenario_pass_rate_all_100: float
    core_scenario_pass_rate_all_100_ci95: ConfidenceInterval95

    conditional_core_pass_rate_on_valid_runs: Optional[float] = None
    conditional_core_pass_rate_on_valid_runs_ci95: Optional[ConfidenceInterval95] = None
    conditional_core_pass_rate_status: str = (
        "SECONDARY_DIAGNOSTIC_ONLY_NEVER_SUBSTITUTE_FOR_PRIMARY"
    )

    grounding_evaluable_scenario_count: int
    grounded_item_count: int
    ungrounded_item_count: int
    poi_visit_item_count: int
    grounded_poi_rate: Optional[float] = None
    grounded_poi_rate_cluster_bootstrap_ci95: Optional[ClusterBootstrapCI95] = None

    all_pois_grounded_scenario_count: int
    all_pois_grounded_rate: Optional[float] = None
    all_pois_grounded_rate_ci95: Optional[ConfidenceInterval95] = None
    all_pois_grounded_rate_all_assigned: float
    all_pois_grounded_rate_all_assigned_ci95: ConfidenceInterval95

    schedule_evaluable_scenario_count: int
    schedule_violation_scenario_count: int
    schedule_violation_rate: Optional[float] = None
    schedule_violation_rate_ci95: Optional[ConfidenceInterval95] = None

    budget_applicable_scenario_count: int
    budget_not_applicable_scenario_count: int
    budget_violation_scenario_count: int
    estimated_budget_violation_rate: Optional[float] = None
    estimated_budget_violation_rate_ci95: Optional[ConfidenceInterval95] = None

    opening_hours_poi_visit_items: int
    opening_hours_evaluable_items: int
    opening_hours_compliant_items: int
    opening_hours_known_violation_count: int
    opening_hours_unknown_items: int
    opening_hours_evidence_coverage: Optional[float] = None
    opening_hours_compliance_rate_on_evaluable_items: Optional[float] = None
    opening_hours_known_violation_scenario_count: int
    opening_hours_known_violation_scenario_rate: Optional[float] = None
    opening_hours_known_violation_scenario_rate_ci95: Optional[ConfidenceInterval95] = None
    opening_hours_evidence_status_counts: Dict[str, int] = Field(default_factory=dict)

    per_destination: Dict[str, DestinationAggregationSummary]
    equal_destination_macro: EqualDestinationMacroSummary
    GROUNDING_GATE: GroundingGateEvaluation


def compute_aggregator_code_sha256() -> str:
    """Compute SHA256 over LF-normalized UTF-8 bytes of this aggregator module."""
    aggregator_path = Path(__file__).resolve()
    return sha256_bytes(normalize_lf_bytes(aggregator_path.read_bytes()))


def compute_wilson_ci95(
    k: int,
    n: int,
    *,
    z: float = WILSON_Z_95,
) -> Optional[ConfidenceInterval95]:
    """Compute deterministic 95% Wilson score confidence interval for k successes in n trials."""
    if n <= 0:
        return None
    if k < 0 or k > n:
        raise ValueError(f"Invalid binomial counts for Wilson CI: k={k}, n={n}")

    p_hat = k / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p_hat + z2 / (2.0 * n)) / denom
    radicand = (p_hat * (1.0 - p_hat) / n) + (z2 / (4.0 * n * n))
    half_width = (z * math.sqrt(max(0.0, radicand))) / denom

    lower = max(0.0, min(1.0, round(center - half_width, 6)))
    upper = max(0.0, min(1.0, round(center + half_width, 6)))
    if k == 0:
        lower = 0.0
    if k == n:
        upper = 1.0

    return ConfidenceInterval95(
        k=k,
        n=n,
        point_estimate=round(p_hat, 6),
        lower=lower,
        upper=upper,
    )


def _percentile_sorted(sorted_vals: Sequence[float], q: float) -> float:
    """Deterministic linear-interpolation percentile on a non-empty sorted list for q in [0, 1]."""
    m = len(sorted_vals)
    if m == 1:
        return sorted_vals[0]
    pos = q * (m - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return sorted_vals[lo]
    frac = pos - lo
    return sorted_vals[lo] + frac * (sorted_vals[hi] - sorted_vals[lo])


def compute_scenario_cluster_bootstrap_grounding_ci95(
    scenario_clusters: Sequence[Tuple[str, int, int]],
    *,
    iterations: int = BOOTSTRAP_ITERATIONS,
    seed: int = BOOTSTRAP_SEED,
) -> Optional[ClusterBootstrapCI95]:
    """Compute 95% scenario-cluster bootstrap CI for item-level Grounded POI Rate.

    Each element of scenario_clusters is (scenario_id, grounded_item_count, poi_visit_item_count).
    Resampling unit is strictly the scenario (never individual POI items).
    Returns None only when no item-level grounding denominator exists (total_poi_visit_items == 0).
    """
    ordered_clusters = sorted(scenario_clusters, key=lambda x: x[0])
    total_grounded = sum(g for _, g, _ in ordered_clusters)
    total_poi_visits = sum(t for _, _, t in ordered_clusters)
    m = len(ordered_clusters)

    if m == 0 or total_poi_visits == 0:
        return None

    point_estimate = round(total_grounded / total_poi_visits, 6)
    rng = random.Random(seed)
    replicate_rates: List[float] = []

    for _ in range(iterations):
        sample = [ordered_clusters[rng.randrange(m)] for _ in range(m)]
        rep_grounded = sum(g for _, g, _ in sample)
        rep_total = sum(t for _, _, t in sample)
        if rep_total > 0:
            replicate_rates.append(rep_grounded / rep_total)
        else:
            replicate_rates.append(point_estimate)

    replicate_rates.sort()
    lower = max(0.0, min(1.0, round(_percentile_sorted(replicate_rates, 0.025), 6)))
    upper = max(0.0, min(1.0, round(_percentile_sorted(replicate_rates, 0.975), 6)))

    return ClusterBootstrapCI95(
        point_estimate=point_estimate,
        lower=lower,
        upper=upper,
        iterations=iterations,
        seed=seed,
        cluster_count=m,
        grounded_item_count=total_grounded,
        poi_visit_item_count=total_poi_visits,
    )


def _is_valid_evaluated(ev: ScenarioEvaluationResult) -> bool:
    return (
        ev.evaluation_status == "EVALUATED"
        and ev.evidence_integrity_valid is True
        and ev.run_valid is True
    )


def _compute_destination_summary(
    destination_slug: str,
    assigned_specs: Sequence[AssignedScenarioSpec],
    eval_by_id: Dict[str, ScenarioEvaluationResult],
    *,
    bootstrap_iterations: int,
    bootstrap_seed: int,
) -> DestinationAggregationSummary:
    assigned_count = len(assigned_specs)
    dest_evals = [eval_by_id[s.scenario_id] for s in assigned_specs]
    valid_evals = [ev for ev in dest_evals if _is_valid_evaluated(ev)]
    valid_count = len(valid_evals)
    invalid_count = assigned_count - valid_count

    valid_rate = round(valid_count / assigned_count, 6) if assigned_count > 0 else None
    valid_rate_ci = compute_wilson_ci95(valid_count, assigned_count) if assigned_count > 0 else None

    core_pass_count = sum(1 for ev in valid_evals if ev.core_scenario_pass is True)
    core_pass_rate = round(core_pass_count / assigned_count, 6) if assigned_count > 0 else None
    core_pass_ci = compute_wilson_ci95(core_pass_count, assigned_count) if assigned_count > 0 else None
    cond_core_pass_rate = (
        round(core_pass_count / valid_count, 6) if valid_count > 0 else None
    )

    grounded_items = sum(ev.grounded_item_count for ev in valid_evals)
    ungrounded_items = sum(ev.ungrounded_item_count for ev in valid_evals)
    poi_visit_items = sum(ev.poi_visit_item_count for ev in valid_evals)
    grounded_rate = (
        round(grounded_items / poi_visit_items, 6) if poi_visit_items > 0 else None
    )
    clusters = [
        (ev.scenario_id, ev.grounded_item_count, ev.poi_visit_item_count)
        for ev in valid_evals
    ]
    grounded_bootstrap_ci = compute_scenario_cluster_bootstrap_grounding_ci95(
        clusters, iterations=bootstrap_iterations, seed=bootstrap_seed
    )

    all_grounded_scen_count = sum(1 for ev in valid_evals if ev.all_pois_grounded is True)
    all_grounded_rate = (
        round(all_grounded_scen_count / valid_count, 6) if valid_count > 0 else None
    )
    all_grounded_ci = (
        compute_wilson_ci95(all_grounded_scen_count, valid_count) if valid_count > 0 else None
    )

    sched_eval_count = valid_count
    sched_viol_count = sum(1 for ev in valid_evals if not ev.schedule_pass)
    sched_viol_rate = (
        round(sched_viol_count / sched_eval_count, 6) if sched_eval_count > 0 else None
    )
    sched_viol_ci = (
        compute_wilson_ci95(sched_viol_count, sched_eval_count)
        if sched_eval_count > 0
        else None
    )

    budget_app_evals = [
        ev
        for ev in valid_evals
        if ev.budget_status != "NOT_APPLICABLE" and ev.budget_ceiling is not None
    ]
    budget_app_count = len(budget_app_evals)
    budget_na_count = valid_count - budget_app_count
    budget_viol_count = sum(
        1
        for ev in budget_app_evals
        if ev.budget_status == "VIOLATION" or ev.estimated_budget_compliant is False
    )
    budget_viol_rate = (
        round(budget_viol_count / budget_app_count, 6) if budget_app_count > 0 else None
    )
    budget_viol_ci = (
        compute_wilson_ci95(budget_viol_count, budget_app_count)
        if budget_app_count > 0
        else None
    )

    oh_poi_items = sum(ev.opening_hours_poi_visit_items for ev in valid_evals)
    oh_eval_items = sum(ev.opening_hours_evaluable_items for ev in valid_evals)
    oh_comp_items = sum(ev.opening_hours_compliant_items for ev in valid_evals)
    oh_viol_items = sum(ev.opening_hours_known_violation_count for ev in valid_evals)
    oh_unk_items = sum(ev.opening_hours_unknown_items for ev in valid_evals)
    oh_coverage = round(oh_eval_items / oh_poi_items, 6) if oh_poi_items > 0 else None
    oh_comp_rate = (
        round(oh_comp_items / oh_eval_items, 6) if oh_eval_items > 0 else None
    )
    oh_viol_scen_count = sum(
        1 for ev in valid_evals if ev.opening_hours_known_violation_count > 0
    )
    oh_viol_scen_rate = (
        round(oh_viol_scen_count / valid_count, 6) if valid_count > 0 else None
    )
    oh_viol_scen_ci = (
        compute_wilson_ci95(oh_viol_scen_count, valid_count) if valid_count > 0 else None
    )

    return DestinationAggregationSummary(
        destination_slug=destination_slug,
        assigned_scenario_count=assigned_count,
        valid_run_count=valid_count,
        invalid_run_count=invalid_count,
        valid_run_rate=valid_rate,
        valid_run_rate_ci95=valid_rate_ci,
        core_scenario_pass_count=core_pass_count,
        core_scenario_pass_rate=core_pass_rate,
        core_scenario_pass_rate_ci95=core_pass_ci,
        conditional_core_pass_rate_on_valid_runs=cond_core_pass_rate,
        grounding_evaluable_scenario_count=valid_count,
        grounded_item_count=grounded_items,
        ungrounded_item_count=ungrounded_items,
        poi_visit_item_count=poi_visit_items,
        grounded_poi_rate=grounded_rate,
        grounded_poi_rate_cluster_bootstrap_ci95=grounded_bootstrap_ci,
        all_pois_grounded_scenario_count=all_grounded_scen_count,
        all_pois_grounded_rate=all_grounded_rate,
        all_pois_grounded_rate_ci95=all_grounded_ci,
        schedule_evaluable_scenario_count=sched_eval_count,
        schedule_violation_scenario_count=sched_viol_count,
        schedule_violation_rate=sched_viol_rate,
        schedule_violation_rate_ci95=sched_viol_ci,
        budget_applicable_scenario_count=budget_app_count,
        budget_not_applicable_scenario_count=budget_na_count,
        budget_violation_scenario_count=budget_viol_count,
        estimated_budget_violation_rate=budget_viol_rate,
        estimated_budget_violation_rate_ci95=budget_viol_ci,
        opening_hours_poi_visit_items=oh_poi_items,
        opening_hours_evaluable_items=oh_eval_items,
        opening_hours_compliant_items=oh_comp_items,
        opening_hours_known_violation_count=oh_viol_items,
        opening_hours_unknown_items=oh_unk_items,
        opening_hours_evidence_coverage=oh_coverage,
        opening_hours_compliance_rate_on_evaluable_items=oh_comp_rate,
        opening_hours_known_violation_scenario_count=oh_viol_scen_count,
        opening_hours_known_violation_scenario_rate=oh_viol_scen_rate,
        opening_hours_known_violation_scenario_rate_ci95=oh_viol_scen_ci,
    )


def _compute_equal_destination_macro(
    per_destination: Dict[str, DestinationAggregationSummary],
) -> EqualDestinationMacroSummary:
    """Compute unweighted arithmetic mean across ha-noi, da-nang, ha-long without zero imputation."""
    metric_fields = (
        ("valid_run_rate_macro", "valid_run_rate"),
        ("core_scenario_pass_rate_macro", "core_scenario_pass_rate"),
        ("conditional_core_pass_rate_on_valid_runs_macro", "conditional_core_pass_rate_on_valid_runs"),
        ("grounded_poi_rate_macro", "grounded_poi_rate"),
        ("all_pois_grounded_rate_macro", "all_pois_grounded_rate"),
        ("schedule_violation_rate_macro", "schedule_violation_rate"),
        ("estimated_budget_violation_rate_macro", "estimated_budget_violation_rate"),
        ("opening_hours_evidence_coverage_macro", "opening_hours_evidence_coverage"),
        (
            "opening_hours_compliance_rate_on_evaluable_items_macro",
            "opening_hours_compliance_rate_on_evaluable_items",
        ),
    )

    macro_values: Dict[str, Optional[float]] = {}
    macro_status: Dict[str, str] = {}

    for macro_key, dest_attr in metric_fields:
        vals = [
            getattr(per_destination[dest], dest_attr)
            for dest in ORDERED_PRIMARY_DESTINATIONS
        ]
        if all(v is not None for v in vals):
            macro_values[macro_key] = round(sum(float(v) for v in vals if v is not None) / 3.0, 6)
            macro_status[macro_key] = "COMPUTED_ALL_3_DESTINATIONS"
        else:
            macro_values[macro_key] = None
            macro_status[macro_key] = "UNDEFINED_MISSING_DESTINATION_EVIDENCE"

    return EqualDestinationMacroSummary(
        **macro_values,
        metric_macro_status=macro_status,
    )


def validate_assignment_and_evaluations(
    assignment_manifest: BenchmarkAssignmentManifest,
    evaluations: Sequence[ScenarioEvaluationResult],
    *,
    final_100_mode: bool = False,
) -> Dict[str, ScenarioEvaluationResult]:
    """Fail-closed validation of assigned scenarios and evaluation results (Sections 18 & 19)."""
    assigned_ids = [s.scenario_id for s in assignment_manifest.assigned_scenarios]
    id_counts = Counter(assigned_ids)
    duplicates = sorted(sid for sid, cnt in id_counts.items() if cnt > 1)
    if duplicates:
        raise ValueError(f"Duplicate assigned scenario_id values rejected: {duplicates}")

    assigned_by_id = {s.scenario_id: s for s in assignment_manifest.assigned_scenarios}

    if final_100_mode or assignment_manifest.is_final_100_frozen:
        if len(assigned_by_id) != FINAL_100_EXPECTED_TOTAL:
            raise ValueError(
                f"FINAL_100 mode requires exactly {FINAL_100_EXPECTED_TOTAL} unique assigned scenarios "
                f"(got {len(assigned_by_id)})."
            )
        dest_counts = Counter(s.destination_slug for s in assignment_manifest.assigned_scenarios)
        actual_alloc = {d: dest_counts.get(d, 0) for d in ORDERED_PRIMARY_DESTINATIONS}
        if actual_alloc != FINAL_100_EXPECTED_ALLOCATION:
            raise ValueError(
                f"FINAL_100 mode requires exact destination allocation {FINAL_100_EXPECTED_ALLOCATION} "
                f"(got {actual_alloc})."
            )

    eval_by_id: Dict[str, ScenarioEvaluationResult] = {}
    for ev in evaluations:
        if ev.scenario_id in eval_by_id:
            raise ValueError(
                f"Multiple evaluation results provided for scenario_id {ev.scenario_id!r}."
            )
        if ev.scenario_id not in assigned_by_id:
            raise ValueError(
                f"Unexpected evaluation result for unassigned scenario_id {ev.scenario_id!r}."
            )
        spec = assigned_by_id[ev.scenario_id]
        if ev.destination_slug != spec.destination_slug:
            raise ValueError(
                f"Destination mismatch for scenario_id {ev.scenario_id!r}: "
                f"assigned {spec.destination_slug!r} vs evaluated {ev.destination_slug!r}."
            )
        if spec.scenario_sha256 is not None and ev.scenario_sha256 != spec.scenario_sha256:
            raise ValueError(
                f"Scenario SHA256 mismatch for scenario_id {ev.scenario_id!r}: "
                f"manifest expects {spec.scenario_sha256} vs evaluation {ev.scenario_sha256}."
            )
        if ev.evaluation_status not in {"EVALUATED", "INVALID_RUN", "EVIDENCE_INTEGRITY_FAILURE"}:
            raise ValueError(
                f"Unsupported terminal evaluation_status {ev.evaluation_status!r} for {ev.scenario_id!r}."
            )
        eval_by_id[ev.scenario_id] = ev

    missing_ids = sorted(set(assigned_by_id.keys()) - set(eval_by_id.keys()))
    if missing_ids:
        raise ValueError(
            f"Missing evaluation results for assigned scenarios: {missing_ids}. "
            "Assigned scenarios must never disappear from the benchmark denominator."
        )

    return eval_by_id


def aggregate_benchmark_evaluations(
    assignment_manifest: BenchmarkAssignmentManifest,
    evaluations: Sequence[ScenarioEvaluationResult],
    *,
    final_100_mode: bool = False,
    assignment_manifest_sha256: Optional[str] = None,
    bootstrap_iterations: int = BOOTSTRAP_ITERATIONS,
    bootstrap_seed: int = BOOTSTRAP_SEED,
) -> BenchmarkBatchAggregationResult:
    """Deterministically aggregate single-scenario evaluation results against an assignment manifest."""
    effective_final_100 = bool(final_100_mode or assignment_manifest.is_final_100_frozen)
    eval_by_id = validate_assignment_and_evaluations(
        assignment_manifest, evaluations, final_100_mode=effective_final_100
    )

    ordered_specs = sorted(
        assignment_manifest.assigned_scenarios, key=lambda s: s.scenario_id
    )
    ordered_evals = [eval_by_id[s.scenario_id] for s in ordered_specs]
    assigned_count = len(ordered_specs)

    valid_evals = [ev for ev in ordered_evals if _is_valid_evaluated(ev)]
    valid_count = len(valid_evals)
    invalid_count = assigned_count - valid_count

    valid_run_rate = round(valid_count / assigned_count, 6)
    valid_run_rate_ci95 = compute_wilson_ci95(valid_count, assigned_count)
    assert valid_run_rate_ci95 is not None

    # Primary CORE_SCENARIO_PASS_RATE_ALL_100 retains all assigned scenarios (100 in FINAL_100 mode)
    # Invalid runs contribute 0 to core_scenario_pass_count.
    core_pass_count = sum(1 for ev in valid_evals if ev.core_scenario_pass is True)
    primary_denom = FINAL_100_EXPECTED_TOTAL if effective_final_100 else assigned_count
    core_pass_rate_all_100 = round(core_pass_count / primary_denom, 6)
    core_pass_rate_all_100_ci95 = compute_wilson_ci95(core_pass_count, primary_denom)
    assert core_pass_rate_all_100_ci95 is not None

    # Secondary diagnostic: conditional on valid runs
    cond_core_pass_rate = (
        round(core_pass_count / valid_count, 6) if valid_count > 0 else None
    )
    cond_core_pass_ci = (
        compute_wilson_ci95(core_pass_count, valid_count) if valid_count > 0 else None
    )

    # Item-level grounding aggregation (counts across valid evaluated runs, never mean-of-means)
    grounded_items = sum(ev.grounded_item_count for ev in valid_evals)
    ungrounded_items = sum(ev.ungrounded_item_count for ev in valid_evals)
    poi_visit_items = sum(ev.poi_visit_item_count for ev in valid_evals)
    grounded_poi_rate = (
        round(grounded_items / poi_visit_items, 6) if poi_visit_items > 0 else None
    )

    clusters = [
        (ev.scenario_id, ev.grounded_item_count, ev.poi_visit_item_count)
        for ev in valid_evals
    ]
    grounded_bootstrap_ci = compute_scenario_cluster_bootstrap_grounding_ci95(
        clusters, iterations=bootstrap_iterations, seed=bootstrap_seed
    )

    all_grounded_scen_count = sum(1 for ev in valid_evals if ev.all_pois_grounded is True)
    all_grounded_rate = (
        round(all_grounded_scen_count / valid_count, 6) if valid_count > 0 else None
    )
    all_grounded_ci = (
        compute_wilson_ci95(all_grounded_scen_count, valid_count) if valid_count > 0 else None
    )
    all_grounded_rate_assigned = round(all_grounded_scen_count / assigned_count, 6)
    all_grounded_ci_assigned = compute_wilson_ci95(all_grounded_scen_count, assigned_count)
    assert all_grounded_ci_assigned is not None

    # Batch-level schedule_violation_rate (denominator: VALID evaluated scenarios)
    sched_eval_count = valid_count
    sched_viol_count = sum(1 for ev in valid_evals if not ev.schedule_pass)
    sched_viol_rate = (
        round(sched_viol_count / sched_eval_count, 6) if sched_eval_count > 0 else None
    )
    sched_viol_ci = (
        compute_wilson_ci95(sched_viol_count, sched_eval_count)
        if sched_eval_count > 0
        else None
    )

    # Batch-level estimated_budget_violation_rate (denominator: VALID budget-applicable scenarios)
    budget_app_evals = [
        ev
        for ev in valid_evals
        if ev.budget_status != "NOT_APPLICABLE" and ev.budget_ceiling is not None
    ]
    budget_app_count = len(budget_app_evals)
    budget_na_count = valid_count - budget_app_count
    budget_viol_count = sum(
        1
        for ev in budget_app_evals
        if ev.budget_status == "VIOLATION" or ev.estimated_budget_compliant is False
    )
    budget_viol_rate = (
        round(budget_viol_count / budget_app_count, 6) if budget_app_count > 0 else None
    )
    budget_viol_ci = (
        compute_wilson_ci95(budget_viol_count, budget_app_count)
        if budget_app_count > 0
        else None
    )

    # Opening-hours batch aggregation
    oh_poi_items = sum(ev.opening_hours_poi_visit_items for ev in valid_evals)
    oh_eval_items = sum(ev.opening_hours_evaluable_items for ev in valid_evals)
    oh_comp_items = sum(ev.opening_hours_compliant_items for ev in valid_evals)
    oh_viol_items = sum(ev.opening_hours_known_violation_count for ev in valid_evals)
    oh_unk_items = sum(ev.opening_hours_unknown_items for ev in valid_evals)
    oh_coverage = round(oh_eval_items / oh_poi_items, 6) if oh_poi_items > 0 else None
    oh_comp_rate = (
        round(oh_comp_items / oh_eval_items, 6) if oh_eval_items > 0 else None
    )
    oh_viol_scen_count = sum(
        1 for ev in valid_evals if ev.opening_hours_known_violation_count > 0
    )
    oh_viol_scen_rate = (
        round(oh_viol_scen_count / valid_count, 6) if valid_count > 0 else None
    )
    oh_viol_scen_ci = (
        compute_wilson_ci95(oh_viol_scen_count, valid_count) if valid_count > 0 else None
    )

    ev_status_counter = Counter(ev.opening_hours_evidence_status for ev in valid_evals)
    oh_status_counts = {
        "FULLY_EVALUABLE": ev_status_counter.get("FULLY_EVALUABLE", 0),
        "PARTIALLY_EVALUABLE": ev_status_counter.get("PARTIALLY_EVALUABLE", 0),
        "NO_EVALUABLE_EVIDENCE": ev_status_counter.get("NO_EVALUABLE_EVIDENCE", 0),
    }

    # Per-destination & Equal-Destination Macro
    per_destination: Dict[str, DestinationAggregationSummary] = {}
    for dest in ORDERED_PRIMARY_DESTINATIONS:
        dest_specs = [s for s in ordered_specs if s.destination_slug == dest]
        per_destination[dest] = _compute_destination_summary(
            dest,
            dest_specs,
            eval_by_id,
            bootstrap_iterations=bootstrap_iterations,
            bootstrap_seed=bootstrap_seed,
        )

    equal_macro = _compute_equal_destination_macro(per_destination)

    # GROUNDING_GATE per frozen Measurement Contract
    if grounded_poi_rate == 1.0 and invalid_count == 0 and poi_visit_items > 0:
        gate_pass = True
        gate_status = "PASS"
        gate_note = (
            "All assigned scenarios produced valid runs and 100% of POI_VISIT items grounded in REC-A-CORE-V2."
        )
    elif grounded_poi_rate == 1.0 and invalid_count > 0 and poi_visit_items > 0:
        gate_pass = False
        gate_status = "INCOMPLETE_DUE_TO_INVALID_RUNS"
        gate_note = (
            f"grounded_poi_rate is 1.0 across {valid_count} valid runs, but {invalid_count} assigned "
            f"scenario(s) failed run validity (valid_run_rate={valid_run_rate}); missing evidence from "
            "invalid runs prevents unconditional benchmark-wide grounding gate closure."
        )
    else:
        gate_pass = False
        gate_status = "FAIL"
        gate_note = (
            f"grounded_poi_rate={grounded_poi_rate} (requires 1.0 across all POI_VISIT items with valid_run_rate=1.0)."
        )

    grounding_gate = GroundingGateEvaluation(
        observed_grounded_poi_rate=grounded_poi_rate,
        grounded_item_count=grounded_items,
        poi_visit_item_count=poi_visit_items,
        valid_run_count=valid_count,
        invalid_run_count=invalid_count,
        valid_run_rate=valid_run_rate,
        gate_pass=gate_pass,
        gate_status=gate_status,
        interpretation_note=gate_note,
    )

    effective_manifest_sha = assignment_manifest_sha256 or sha256_bytes(
        canonical_json_bytes(assignment_manifest.model_dump())
    )

    return BenchmarkBatchAggregationResult(
        aggregator_code_sha256=compute_aggregator_code_sha256(),
        assignment_manifest_id=assignment_manifest.manifest_id,
        assignment_manifest_sha256=effective_manifest_sha,
        final_100_mode=effective_final_100,
        bootstrap_iterations=bootstrap_iterations,
        bootstrap_seed=bootstrap_seed,
        assigned_scenario_count=assigned_count,
        valid_run_count=valid_count,
        invalid_run_count=invalid_count,
        valid_run_rate=valid_run_rate,
        valid_run_rate_ci95=valid_run_rate_ci95,
        primary_pass_rate_denominator=primary_denom,
        core_scenario_pass_count=core_pass_count,
        core_scenario_pass_rate_all_100=core_pass_rate_all_100,
        core_scenario_pass_rate_all_100_ci95=core_pass_rate_all_100_ci95,
        conditional_core_pass_rate_on_valid_runs=cond_core_pass_rate,
        conditional_core_pass_rate_on_valid_runs_ci95=cond_core_pass_ci,
        grounding_evaluable_scenario_count=valid_count,
        grounded_item_count=grounded_items,
        ungrounded_item_count=ungrounded_items,
        poi_visit_item_count=poi_visit_items,
        grounded_poi_rate=grounded_poi_rate,
        grounded_poi_rate_cluster_bootstrap_ci95=grounded_bootstrap_ci,
        all_pois_grounded_scenario_count=all_grounded_scen_count,
        all_pois_grounded_rate=all_grounded_rate,
        all_pois_grounded_rate_ci95=all_grounded_ci,
        all_pois_grounded_rate_all_assigned=all_grounded_rate_assigned,
        all_pois_grounded_rate_all_assigned_ci95=all_grounded_ci_assigned,
        schedule_evaluable_scenario_count=sched_eval_count,
        schedule_violation_scenario_count=sched_viol_count,
        schedule_violation_rate=sched_viol_rate,
        schedule_violation_rate_ci95=sched_viol_ci,
        budget_applicable_scenario_count=budget_app_count,
        budget_not_applicable_scenario_count=budget_na_count,
        budget_violation_scenario_count=budget_viol_count,
        estimated_budget_violation_rate=budget_viol_rate,
        estimated_budget_violation_rate_ci95=budget_viol_ci,
        opening_hours_poi_visit_items=oh_poi_items,
        opening_hours_evaluable_items=oh_eval_items,
        opening_hours_compliant_items=oh_comp_items,
        opening_hours_known_violation_count=oh_viol_items,
        opening_hours_unknown_items=oh_unk_items,
        opening_hours_evidence_coverage=oh_coverage,
        opening_hours_compliance_rate_on_evaluable_items=oh_comp_rate,
        opening_hours_known_violation_scenario_count=oh_viol_scen_count,
        opening_hours_known_violation_scenario_rate=oh_viol_scen_rate,
        opening_hours_known_violation_scenario_rate_ci95=oh_viol_scen_ci,
        opening_hours_evidence_status_counts=oh_status_counts,
        per_destination=per_destination,
        equal_destination_macro=equal_macro,
        GROUNDING_GATE=grounding_gate,
    )


def aggregate_evaluations_from_disk(
    *,
    assignment_manifest_path: Path,
    evaluations_dir: Path,
    output_path: Path,
    final_100_mode: bool = False,
) -> BenchmarkBatchAggregationResult:
    """Load an assignment manifest and persisted scenario_evaluation.json files and write batch aggregation JSON."""
    if not assignment_manifest_path.exists():
        raise FileNotFoundError(f"Assignment manifest not found: {assignment_manifest_path}")
    if not evaluations_dir.exists() or not evaluations_dir.is_dir():
        raise FileNotFoundError(f"Evaluations directory not found: {evaluations_dir}")

    manifest_bytes = assignment_manifest_path.read_bytes()
    manifest = BenchmarkAssignmentManifest.model_validate(
        json.loads(manifest_bytes.decode("utf-8"))
    )

    evaluations: List[ScenarioEvaluationResult] = []
    # Support both <evaluations_dir>/<scenario_id>/scenario_evaluation.json and <evaluations_dir>/*.json
    direct_json_files = sorted(evaluations_dir.glob("*.json"))
    subdir_eval_files = sorted(evaluations_dir.glob("*/scenario_evaluation.json"))

    candidate_files = subdir_eval_files if subdir_eval_files else direct_json_files
    for fpath in candidate_files:
        raw_obj = json.loads(fpath.read_bytes().decode("utf-8"))
        evaluations.append(ScenarioEvaluationResult.model_validate(raw_obj))

    result = aggregate_benchmark_evaluations(
        manifest,
        evaluations,
        final_100_mode=final_100_mode,
        assignment_manifest_sha256=sha256_bytes(manifest_bytes),
    )
    write_canonical_json(output_path, result.model_dump())
    return result
