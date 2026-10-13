"""Frozen W5 Metric and Scientific Evaluation Runner.

Pre-registered evaluation runner for GoMate / WanderAI recommendation systems:
- Shared REC-A0/A1 baseline vs. REC-A2
- Evaluates 30 primary scenarios (15 U1, 15 U2 across Hanoi, Da Nang, Ha Long)
- Destination-conditioned macro aggregation (equal city weighting: Hanoi, Da Nang, Ha Long)
- Paired destination-stratified bootstrap (seed 20261013, 10,000 replicates)
- Pure metric functions: NDCG@10, Precision@10, Pooled Recall@10, HitRate@10,
  Category-ILD@10, CatalogCoverage@10, I1Exposure@10 (diagnostic)
- Strict relevance label validation: 0, 1, 2, 'NA', None (booleans/malformed strictly rejected)
- Strict missingness handling: missing destination evidence is NEVER imputed as 0
- Separated observed effect size (observed_point_delta) from bootstrap distribution
- Pre-registered verdict classification (Rule A, B, C, INCONCLUSIVE)
- Duplicate-equivalence map interface (status PENDING until W5-GATE-DUP)
- Complete future evaluation pipeline (load_and_validate_ground_truth, evaluate_system,
  build_paired_comparison, build_final_evaluation_result) ready before human labels exist.

CRITICAL INVARIANTS:
- No human labels collected or prefilled in repository
- No real scientific model comparison executed on real data
- No model winner declared
- Recommender algorithms remain unchanged
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

REPO_ROOT = Path(__file__).resolve().parent.parent

# Configuration Constants
W5_METRIC_BOOTSTRAP_SEED: int = 20261013
BOOTSTRAP_REPLICATES: int = 10000

DATASET_FREEZE_V2_RELPATH = "data/curated/gomate_places_freeze_v2.json"
FREEZE_V2_CANONICAL_LF_SHA256 = "f7517938598e3923906763f8f31334a500ee88bc06232f2992d38e2fcb28a444"
FREEZE_V2_CRLF_COMPAT_SHA256 = "93681135d94b379f28802aa75204a0a4c7bec4039f85d28e76ae6737e792e245"
FREEZE_V2_ACCEPTED_SHA256 = {
    FREEZE_V2_CANONICAL_LF_SHA256,
    FREEZE_V2_CRLF_COMPAT_SHA256,
}

PRIMARY_SCENARIOS_RELPATH = "data/evaluation/reca_w5/w5_primary_scenarios_v1.json"
THIN_SCENARIOS_RELPATH = "data/evaluation/reca_w5/w5_thin_diagnostic_scenarios_v1.json"
INTERNAL_POOL_RELPATH = "data/evaluation/reca_w5/w5_candidate_pool_internal_v1.json"
BLINDED_POOL_RELPATH = "data/evaluation/reca_w5/w5_candidate_pool_blinded_v1.json"
REPRODUCIBILITY_MANIFEST_RELPATH = "data/evaluation/reca_w5/w5_reproducibility_manifest_v1.json"

FROZEN_DESTINATIONS = ["ha-noi", "da-nang", "ha-long"]
EXPECTED_CATALOG_SIZES: Dict[str, int] = {
    "ha-noi": 145,
    "da-nang": 289,
    "ha-long": 188,
}
EXPECTED_TOTAL_CORE: int = 622

SYSTEM_BASELINE = "shared_a0_a1_baseline"
SYSTEM_A2 = "rec-a2"
VALID_SYSTEMS: Set[str] = {SYSTEM_BASELINE, SYSTEM_A2}

# Scientific Semantics Metadata
CATEGORY_ILD_SEMANTICS: str = "structural_category_diversity_proxy"
EVALUATION_VERSION: str = "W5-EVAL-V1"
EXPECTED_RUBRIC_VERSION: str = "W5-RUBRIC-V1"
EXPECTED_POOL_VERSION: str = "W5-POOL-V1"
EXPECTED_SCENARIO_VERSION: str = "W5-SCENARIO-V1"
EXPECTED_METADATA_VERSION: str = "W5-METADATA-V1"
EXPECTED_TEMPLATE_VERSION: str = "W5-MERGED-GROUND-TRUTH-TEMPLATE-V1"



# ============================================================
# STRICT RELEVANCE LABEL VALIDATION
# ============================================================


def validate_relevance_label(val: Any) -> Optional[int]:
    """Strictly validate a relevance label.

    Allowed:
      0, 1, 2 -> valid integer relevance
      "NA", None -> unresolved judgment (returns None)

    Explicitly rejected (raises ValueError):
      bool (True, False) - bool is a subclass of int in Python!
      int not in {0, 1, 2} (e.g. 3, -1)
      float (e.g. 1.5)
      str not in {"NA"} (e.g. "0", "1", "2", "bad")
      any other type/value (list, dict, etc.)
    """
    if isinstance(val, bool):
        raise ValueError(f"Invalid relevance label: boolean {val} is not permitted")
    if val is None or val == "NA":
        return None
    if isinstance(val, int):
        if val in (0, 1, 2):
            return val
        raise ValueError(f"Invalid integer relevance label: {val}. Allowed: 0, 1, 2")
    raise ValueError(
        f"Invalid relevance label: {val!r} of type {type(val).__name__}. Allowed: 0, 1, 2, 'NA', None"
    )


def validate_relevance_sequence(labels: Sequence[Any], context_name: str = "relevance") -> List[Optional[int]]:
    """Validate a sequence of labels. Raises ValueError on any malformed label."""
    validated: List[Optional[int]] = []
    for idx, item in enumerate(labels):
        try:
            validated.append(validate_relevance_label(item))
        except ValueError as err:
            raise ValueError(f"Malformed label in {context_name} at index {idx}: {err}") from err
    return validated


# ============================================================
# PURE METRIC FUNCTIONS
# ============================================================


def calculate_gain(rel: Any) -> float:
    """Graded relevance gain: 2^rel - 1.

    rel=0 -> 0.0
    rel=1 -> 1.0
    rel=2 -> 3.0
    Unresolved ('NA', None) or invalid values raise ValueError.
    """
    validated = validate_relevance_label(rel)
    if validated is None:
        raise ValueError(f"Cannot calculate gain for unresolved label {rel!r}")
    return float((1 << validated) - 1)


def dcg_at_k(relevances: Sequence[Any], k: int = 10) -> float:
    """Calculate Discounted Cumulative Gain at k using standard log2(i + 1) discount.

    DCG@k = sum_{i=1..k} (2^{rel_i} - 1) / log2(i + 1)
    """
    validated = validate_relevance_sequence(relevances, context_name="dcg_at_k relevances")
    k_eff = min(k, len(validated))
    dcg = 0.0
    for i in range(k_eff):
        r = validated[i]
        if r is None:
            raise ValueError(f"Cannot compute DCG on unresolved relevance at rank {i + 1}")
        rank = i + 1
        gain = calculate_gain(r)
        discount = math.log2(rank + 1)
        dcg += gain / discount
    return dcg


def idcg_at_k(pool_relevances: Sequence[Any], k: int = 10) -> float:
    """Calculate Ideal DCG at k from numerically judged scenario candidate pool.

    Sorts all numerically judged candidate items descending by relevance, takes top k.
    Unresolved (NA, None) pool items are safely excluded from IDCG.
    Malformed items raise ValueError.
    """
    validated_pool = validate_relevance_sequence(pool_relevances, context_name="idcg_at_k pool")
    valid_numeric = [r for r in validated_pool if r is not None]
    sorted_relevances = sorted(valid_numeric, reverse=True)
    return dcg_at_k(sorted_relevances[:k], k=k)


def ndcg_at_k(
    ranked_relevances: Sequence[Any],
    pool_relevances: Sequence[Any],
    k: int = 10,
) -> Tuple[Optional[float], str]:
    """Calculate standard graded NDCG@10 against common judged pool.

    IDCG is constructed from all numerically judged items in the scenario candidate pool.

    Validation:
      Malformed labels in ranked_relevances or pool_relevances raise ValueError.

    NA / Unresolved Policy:
      If any item in evaluated Top-k is unresolved (NA or None), returns
      (None, "NOT_SCORABLE_UNRESOLVED_TOPK"). NA is NEVER cast to 0.

    IDCG = 0 Policy:
      If IDCG@k == 0 (no relevant item in judged pool), returns
      (None, "NO_RELEVANT_ITEM_IN_JUDGED_POOL").

    Returns:
      (ndcg_value, status_code)
    """
    valid_pool = validate_relevance_sequence(pool_relevances, context_name="pool_relevances")
    valid_ranked = validate_relevance_sequence(ranked_relevances, context_name="ranked_relevances")

    k_eff = min(k, len(valid_ranked))
    for i in range(k_eff):
        if valid_ranked[i] is None:
            return None, "NOT_SCORABLE_UNRESOLVED_TOPK"

    clean_ranked: List[int] = [int(r) for r in valid_ranked[:k_eff]]  # type: ignore
    clean_pool: List[int] = [int(r) for r in valid_pool if r is not None]

    idcg = idcg_at_k(clean_pool, k=k)
    if idcg == 0.0:
        return None, "NO_RELEVANT_ITEM_IN_JUDGED_POOL"

    dcg = dcg_at_k(clean_ranked, k=k)
    return round(dcg / idcg, 6), "OK"


def precision_at_k(
    ranked_relevances: Sequence[Any],
    k: int = 10,
) -> Tuple[Optional[float], str]:
    """Precision at k with rel >= 1 threshold.

    If any item in evaluated Top-k is unresolved, returns (None, 'NOT_SCORABLE_UNRESOLVED_TOPK').
    """
    valid_ranked = validate_relevance_sequence(ranked_relevances, context_name="ranked_relevances")
    k_eff = min(k, len(valid_ranked))
    if k_eff == 0:
        return None, "EMPTY_RANKING"

    for i in range(k_eff):
        if valid_ranked[i] is None:
            return None, "NOT_SCORABLE_UNRESOLVED_TOPK"

    relevant_count = sum(1 for i in range(k_eff) if int(valid_ranked[i]) >= 1)  # type: ignore
    return round(relevant_count / k_eff, 6), "OK"


def pooled_recall_at_k(
    ranked_relevances: Sequence[Any],
    pool_relevances: Sequence[Any],
    k: int = 10,
) -> Tuple[Optional[float], str]:
    """Pooled Recall at k: # relevant in Top-k / # relevant in common judged pool.

    Threshold: rel >= 1.
    If pool contains zero relevant items, returns (None, 'NO_RELEVANT_ITEM_IN_JUDGED_POOL').
    If any item in evaluated Top-k is unresolved, returns (None, 'NOT_SCORABLE_UNRESOLVED_TOPK').
    """
    valid_pool = validate_relevance_sequence(pool_relevances, context_name="pool_relevances")
    valid_ranked = validate_relevance_sequence(ranked_relevances, context_name="ranked_relevances")

    k_eff = min(k, len(valid_ranked))
    if k_eff == 0:
        return None, "EMPTY_RANKING"

    for i in range(k_eff):
        if valid_ranked[i] is None:
            return None, "NOT_SCORABLE_UNRESOLVED_TOPK"

    pool_numeric = [r for r in valid_pool if r is not None]
    pool_relevant = sum(1 for r in pool_numeric if r >= 1)
    if pool_relevant == 0:
        return None, "NO_RELEVANT_ITEM_IN_JUDGED_POOL"

    topk_relevant = sum(1 for i in range(k_eff) if int(valid_ranked[i]) >= 1)  # type: ignore
    return round(topk_relevant / pool_relevant, 6), "OK"


def hit_rate_at_k(
    ranked_relevances: Sequence[Any],
    k: int = 10,
) -> Tuple[Optional[float], str]:
    """HitRate at k: 1.0 if at least one item in evaluated Top-k has rel >= 1, else 0.0.

    If any item in evaluated Top-k is unresolved, returns (None, 'NOT_SCORABLE_UNRESOLVED_TOPK').
    """
    valid_ranked = validate_relevance_sequence(ranked_relevances, context_name="ranked_relevances")
    k_eff = min(k, len(valid_ranked))
    if k_eff == 0:
        return None, "EMPTY_RANKING"

    for i in range(k_eff):
        if valid_ranked[i] is None:
            return None, "NOT_SCORABLE_UNRESOLVED_TOPK"

    hits = any(int(valid_ranked[i]) >= 1 for i in range(k_eff))  # type: ignore
    return (1.0 if hits else 0.0), "OK"


def category_ild_at_k(
    categories: Sequence[str],
    k: int = 10,
) -> Optional[float]:
    """Calculate Intra-List Distance (ILD) based on factual POI category.

    Category-ILD@10 is explicitly a STRUCTURAL CATEGORY-DIVERSITY PROXY.
    It does not measure semantic diversity, human-perceived diversity, or user satisfaction.

    d(i, j) = 0 if category(i) == category(j) else 1
    ILD(L) = 2 / (n * (n - 1)) * sum_{i < j} d(i, j)

    If n < 2, returns None.
    Missing categories raise ValueError.
    """
    k_eff = min(k, len(categories))
    if k_eff < 2:
        return None

    diff_count = 0
    for i in range(k_eff):
        cat_i = categories[i]
        if not cat_i:
            raise ValueError(f"Missing category at rank {i + 1}")
        for j in range(i + 1, k_eff):
            cat_j = categories[j]
            if not cat_j:
                raise ValueError(f"Missing category at rank {j + 1}")
            if cat_i != cat_j:
                diff_count += 1

    total_pairs = (k_eff * (k_eff - 1)) // 2
    return round(diff_count / total_pairs, 6)


def catalog_coverage_at_k(unique_recommended_count: int, catalog_size: int) -> float:
    """Calculate system-level catalog coverage ratio for destination d."""
    if catalog_size <= 0:
        raise ValueError(f"Catalog size must be positive, got {catalog_size}")
    return round(unique_recommended_count / catalog_size, 6)


def macro_destination_coverage(cov_hn: float, cov_dn: float, cov_hl: float) -> float:
    """Equal city weighting macro average for CatalogCoverage@10."""
    return round((cov_hn + cov_dn + cov_hl) / 3.0, 6)


def i1_exposure_at_k(strata: Sequence[str], k: int = 10) -> float:
    """Diagnostic ratio of zero-vector I1 items in evaluated Top-k.

    Diagnostic only: does NOT enter relevance verdict.
    Strictly validates that every stratum is 'I0' or 'I1'. Unknown values raise ValueError.
    """
    k_eff = min(k, len(strata))
    if k_eff == 0:
        return 0.0
    for idx, s in enumerate(strata[:k_eff]):
        if s not in ("I0", "I1"):
            raise ValueError(f"Invalid stratum {s!r} at rank {idx + 1}. Expected 'I0' or 'I1'.")
    i1_count = sum(1 for s in strata[:k_eff] if s == "I1")
    return round(i1_count / k_eff, 6)


# ============================================================
# STATISTICAL / AGGREGATION FUNCTIONS
# ============================================================


def calculate_percentile(sorted_values: Sequence[float], p: float) -> float:
    """Calculate percentile p in [0, 100] using standard linear interpolation."""
    if not sorted_values:
        raise ValueError("Cannot calculate percentile of empty sequence")
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    idx = (len(sorted_values) - 1) * (p / 100.0)
    lower = int(idx)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = idx - lower
    return float(sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight)


def aggregate_destination_macro(destination_means: Dict[str, Optional[float]]) -> Optional[float]:
    """Compute primary overall macro mean across Hanoi, Da Nang, and Ha Long.

    Equal city weighting: mean(HN_mean, DN_mean, HL_mean).
    If any required destination mean is None (not estimable), returns None.
    """
    required = FROZEN_DESTINATIONS
    for d in required:
        if d not in destination_means or destination_means[d] is None:
            return None
    vals = [destination_means[d] for d in required if destination_means[d] is not None]  # type: ignore
    return round(sum(vals) / len(vals), 6)


def aggregate_unweighted_mean(all_metrics: Sequence[Optional[float]]) -> Optional[float]:
    """Compute secondary unweighted mean across all scorable scenarios."""
    valid_vals = [m for m in all_metrics if m is not None]
    if not valid_vals:
        return None
    return round(sum(valid_vals) / len(valid_vals), 6)


def paired_destination_stratified_bootstrap(
    paired_scenarios_by_dest: Dict[str, List[Tuple[Optional[float], Optional[float]]]],
    seed: int = W5_METRIC_BOOTSTRAP_SEED,
    replicates: int = BOOTSTRAP_REPLICATES,
) -> Dict[str, Any]:
    """Paired destination-stratified bootstrap for query-level metrics.

    CRITICAL SCIENTIFIC RULES:
    1. Observed Point Delta:
       Direct analytical mean of (A2 - Baseline) across original paired scorable scenarios.
       Separated from bootstrap replicate mean.
    2. Missingness / Non-Estimability:
       If ANY destination has 0 paired scorable scenarios, delta 0 is NEVER imputed!
       Returns status: "PRIMARY_INFERENCE_NOT_ESTIMABLE", observed_point_delta: None, ci_95: None.
    3. Attrition Reporting:
       Exposes total, paired scorable, and excluded counts globally and per destination.

    Returns:
      {
        "status": "ESTIMATED" | "PRIMARY_INFERENCE_NOT_ESTIMABLE",
        "observed_point_delta": Optional[float],
        "ci_95": Optional[Tuple[float, float]],
        "bootstrap_mean": Optional[float],
        "replicates": int,
        "seed": int,
        "sample_attrition": Dict[str, Any],
      }
    """
    destinations = FROZEN_DESTINATIONS
    clean_data: Dict[str, List[Tuple[float, float]]] = {}
    attrition_per_dest: Dict[str, Dict[str, int]] = {}

    total_primary = 0
    total_paired_scorable = 0
    total_excluded = 0

    has_empty_destination = False

    for d in destinations:
        pairs = paired_scenarios_by_dest.get(d, [])
        n_total = len(pairs)
        valid_pairs = [(b, a) for b, a in pairs if b is not None and a is not None]
        n_scorable = len(valid_pairs)
        n_excluded = n_total - n_scorable

        total_primary += n_total
        total_paired_scorable += n_scorable
        total_excluded += n_excluded

        attrition_per_dest[d] = {
            "total": n_total,
            "paired_scorable": n_scorable,
            "excluded": n_excluded,
        }
        clean_data[d] = valid_pairs

        if n_scorable == 0:
            has_empty_destination = True

    sample_attrition = {
        "total_primary_scenarios": total_primary,
        "paired_scorable_scenarios": total_paired_scorable,
        "excluded_scenarios": total_excluded,
        "per_destination": attrition_per_dest,
    }

    # Blocker A: Zero imputation is strictly forbidden!
    if has_empty_destination:
        return {
            "status": "PRIMARY_INFERENCE_NOT_ESTIMABLE",
            "observed_point_delta": None,
            "ci_95": None,
            "bootstrap_mean": None,
            "replicates": replicates,
            "seed": seed,
            "sample_attrition": sample_attrition,
        }

    # Blocker B: Calculate OBSERVED point delta directly from original scenarios
    observed_dest_deltas: List[float] = []
    for d in destinations:
        pairs = clean_data[d]
        diffs = [a - b for b, a in pairs]
        observed_dest_deltas.append(sum(diffs) / len(diffs))
    observed_point_delta = round(sum(observed_dest_deltas) / len(destinations), 6)

    # Bootstrap Resampling
    rng = random.Random(seed)
    replicate_deltas: List[float] = []

    for _ in range(replicates):
        dest_deltas: List[float] = []
        for d in destinations:
            pairs = clean_data[d]
            n = len(pairs)
            sampled = rng.choices(pairs, k=n)
            diffs = [a - b for b, a in sampled]
            dest_deltas.append(sum(diffs) / n)
        macro_delta = sum(dest_deltas) / len(destinations)
        replicate_deltas.append(macro_delta)

    sorted_deltas = sorted(replicate_deltas)
    ci_lower = calculate_percentile(sorted_deltas, 2.5)
    ci_upper = calculate_percentile(sorted_deltas, 97.5)
    bootstrap_mean = round(sum(replicate_deltas) / len(replicate_deltas), 6)

    return {
        "status": "ESTIMATED",
        "observed_point_delta": observed_point_delta,
        "ci_95": (round(ci_lower, 6), round(ci_upper, 6)),
        "bootstrap_mean": bootstrap_mean,
        "replicates": replicates,
        "seed": seed,
        "sample_attrition": sample_attrition,
    }


def paired_coverage_stratified_bootstrap(
    scenarios_by_dest: Dict[str, List[Dict[str, Any]]],
    catalog_sizes: Dict[str, int],
    seed: int = W5_METRIC_BOOTSTRAP_SEED,
    replicates: int = BOOTSTRAP_REPLICATES,
) -> Dict[str, Any]:
    """Paired destination-stratified bootstrap for CatalogCoverage@10.

    CRITICAL SCIENTIFIC RULES:
    1. Observed Point Delta:
       Direct analytical coverage delta on original scenarios:
       delta_d = (unique_a2_d - unique_base_d) / catalog_size_d
       observed_point_delta = mean(delta_HN, delta_DN, delta_HL)
    2. Missingness / Non-Estimability:
       If any required destination has 0 scenarios, returns PRIMARY_INFERENCE_NOT_ESTIMABLE.
    """
    destinations = FROZEN_DESTINATIONS
    attrition_per_dest: Dict[str, Dict[str, int]] = {}
    has_empty_destination = False

    for d in destinations:
        sc_list = scenarios_by_dest.get(d, [])
        cat_size = catalog_sizes.get(d, 0)
        n = len(sc_list)
        attrition_per_dest[d] = {
            "total": n,
            "paired_scorable": n,
            "excluded": 0,
        }
        if n == 0 or cat_size <= 0:
            has_empty_destination = True

    sample_attrition = {
        "total_primary_scenarios": sum(len(scenarios_by_dest.get(d, [])) for d in destinations),
        "paired_scorable_scenarios": sum(len(scenarios_by_dest.get(d, [])) for d in destinations),
        "excluded_scenarios": 0,
        "per_destination": attrition_per_dest,
    }

    if has_empty_destination:
        return {
            "status": "PRIMARY_INFERENCE_NOT_ESTIMABLE",
            "observed_point_delta": None,
            "ci_95": None,
            "bootstrap_mean": None,
            "replicates": replicates,
            "seed": seed,
            "sample_attrition": sample_attrition,
        }

    # Observed Point Delta from original scenario set
    observed_dest_deltas: List[float] = []
    for d in destinations:
        sc_list = scenarios_by_dest[d]
        cat_size = catalog_sizes[d]
        base_places: Set[str] = set()
        a2_places: Set[str] = set()
        for sc in sc_list:
            base_places.update(sc.get("baseline_top10", []))
            a2_places.update(sc.get("a2_top10", []))
        cov_base = len(base_places) / cat_size
        cov_a2 = len(a2_places) / cat_size
        observed_dest_deltas.append(cov_a2 - cov_base)

    observed_point_delta = round(sum(observed_dest_deltas) / len(destinations), 6)

    # Bootstrap Resampling
    rng = random.Random(seed)
    replicate_deltas: List[float] = []

    for _ in range(replicates):
        dest_deltas: List[float] = []
        for d in destinations:
            sc_list = scenarios_by_dest[d]
            n = len(sc_list)
            cat_size = catalog_sizes[d]
            sampled_sc = rng.choices(sc_list, k=n)
            b_places: Set[str] = set()
            a_places: Set[str] = set()
            for sc in sampled_sc:
                b_places.update(sc.get("baseline_top10", []))
                a_places.update(sc.get("a2_top10", []))
            cov_b = len(b_places) / cat_size
            cov_a = len(a_places) / cat_size
            dest_deltas.append(cov_a - cov_b)

        macro_delta = sum(dest_deltas) / len(destinations)
        replicate_deltas.append(macro_delta)

    sorted_deltas = sorted(replicate_deltas)
    ci_lower = calculate_percentile(sorted_deltas, 2.5)
    ci_upper = calculate_percentile(sorted_deltas, 97.5)
    bootstrap_mean = round(sum(replicate_deltas) / len(replicate_deltas), 6)

    return {
        "status": "ESTIMATED",
        "observed_point_delta": observed_point_delta,
        "ci_95": (round(ci_lower, 6), round(ci_upper, 6)),
        "bootstrap_mean": bootstrap_mean,
        "replicates": replicates,
        "seed": seed,
        "sample_attrition": sample_attrition,
    }


# ============================================================
# PRE-REGISTERED FINAL VERDICT CLASSIFICATION
# ============================================================


def classify_final_verdict(
    ndcg_ci: Optional[Tuple[float, float]],
    ild_ci: Optional[Tuple[float, float]],
    cov_ci: Optional[Tuple[float, float]],
    ild_point_delta: Optional[float],
    cov_point_delta: Optional[float],
) -> str:
    """Classify final scientific verdict according to pre-registered rules.

    Permitted Verdict Labels:
      A2_RELEVANCE_SUPERIOR
      BASELINE_PREFERRED
      A2_DIVERSITY_TRADEOFF
      INCONCLUSIVE

    If primary inference cannot be estimated (ndcg_ci is None), returns INCONCLUSIVE.
    """
    if ndcg_ci is None:
        return "INCONCLUSIVE"

    ndcg_lower, ndcg_upper = ndcg_ci
    if ndcg_lower > 0.0:
        return "A2_RELEVANCE_SUPERIOR"
    if ndcg_upper < 0.0:
        return "BASELINE_PREFERRED"

    # NDCG CI includes zero
    if ndcg_lower <= 0.0 <= ndcg_upper:
        ild_lower = ild_ci[0] if ild_ci is not None else -1.0
        cov_lower = cov_ci[0] if cov_ci is not None else -1.0
        c_p_ild = ild_point_delta if ild_point_delta is not None else -1.0
        c_p_cov = cov_point_delta if cov_point_delta is not None else -1.0

        rule_c1 = ild_lower > 0.0 and c_p_cov >= 0.0
        rule_c2 = cov_lower > 0.0 and c_p_ild >= 0.0
        if rule_c1 or rule_c2:
            return "A2_DIVERSITY_TRADEOFF"

    return "INCONCLUSIVE"


# ============================================================
# DUPLICATE INTERFACE HOOK
# ============================================================


def apply_duplicate_equivalence(
    place_ids: Sequence[str],
    duplicate_map: Optional[Dict[str, str]] = None,
) -> List[str]:
    """Map place IDs to equivalence groups if a duplicate map is provided.

    If duplicate_map is None, returns original place_ids unchanged.
    """
    if not duplicate_map:
        return list(place_ids)
    return [duplicate_map.get(pid, pid) for pid in place_ids]


# ============================================================
# SCENARIO & SYSTEM EVALUATION
# ============================================================


def evaluate_scenario(
    scenario_info: Dict[str, Any],
    ranked_places: List[Dict[str, Any]],
    pool_items: List[Dict[str, Any]],
    gt_map: Dict[str, Any],
    system_name: str,
    duplicate_map: Optional[Dict[str, str]] = None,
    k: int = 10,
) -> Dict[str, Any]:
    """Evaluate one system on one scenario against ground truth."""
    scenario_id = scenario_info["scenario_id"]
    destination = scenario_info["destination"]
    user_stratum = scenario_info.get("user_stratum", "U1")

    # Extract ranked relevances and metadata
    k_eff = min(k, len(ranked_places))
    ranked_relevances: List[Any] = []
    ranked_categories: List[str] = []
    ranked_strata: List[str] = []

    for item in ranked_places[:k_eff]:
        pid = item["place_id"]
        ranked_relevances.append(gt_map.get(pid))
        ranked_categories.append(item.get("category", ""))
        ranked_strata.append(item.get("i0_i1_stratum", "I0"))

    # Extract pool relevances
    pool_relevances: List[Any] = []
    for item in pool_items:
        pid = item["place_id"]
        pool_relevances.append(gt_map.get(pid))

    # Pool counts
    validated_pool = validate_relevance_sequence(pool_relevances, context_name=f"{scenario_id} pool")
    judged_pool_count = sum(1 for r in validated_pool if r is not None)
    unresolved_pool_count = sum(1 for r in validated_pool if r is None)

    # Compute metrics
    ndcg_val, ndcg_status = ndcg_at_k(ranked_relevances, pool_relevances, k=k)
    p_val, p_status = precision_at_k(ranked_relevances, k=k)
    r_val, r_status = pooled_recall_at_k(ranked_relevances, pool_relevances, k=k)
    hr_val, hr_status = hit_rate_at_k(ranked_relevances, k=k)
    ild_val = category_ild_at_k(ranked_categories, k=k)
    i1_val = i1_exposure_at_k(ranked_strata, k=k)

    overall_status = "OK"
    if "NOT_SCORABLE_UNRESOLVED_TOPK" in (ndcg_status, p_status, r_status, hr_status):
        overall_status = "NOT_SCORABLE_UNRESOLVED_TOPK"
    elif "NO_RELEVANT_ITEM_IN_JUDGED_POOL" in (ndcg_status, r_status):
        overall_status = "NO_RELEVANT_ITEM_IN_JUDGED_POOL"

    return {
        "scenario_id": scenario_id,
        "destination": destination,
        "user_stratum": user_stratum,
        "system": system_name,
        "ndcg_at_10": ndcg_val,
        "precision_at_10": p_val,
        "pooled_recall_at_10": r_val,
        "hit_rate_at_10": hr_val,
        "category_ild_at_10": ild_val,
        "i1_exposure_at_10": i1_val,
        "judged_pool_count": judged_pool_count,
        "unresolved_pool_count": unresolved_pool_count,
        "metric_status": overall_status,
        "category_ild_semantics": CATEGORY_ILD_SEMANTICS,
        "topk_place_ids": [item["place_id"] for item in ranked_places[:k_eff]],
    }


def extract_system_rankings(
    internal_pool: List[Dict[str, Any]],
) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    """Extract ordered Top-10 lists for baseline and A2 from internal pool."""
    rankings: Dict[str, Dict[str, List[Dict[str, Any]]]] = {
        SYSTEM_BASELINE: {},
        SYSTEM_A2: {},
    }
    for sc in internal_pool:
        sid = sc["scenario_id"]
        base_items = [it for it in sc["items"] if it.get("baseline_rank") is not None]
        base_items.sort(key=lambda x: x["baseline_rank"])
        rankings[SYSTEM_BASELINE][sid] = base_items

        a2_items = [it for it in sc["items"] if it.get("a2_rank") is not None]
        a2_items.sort(key=lambda x: x["a2_rank"])
        rankings[SYSTEM_A2][sid] = a2_items

    return rankings


# ============================================================
# STRICT IDENTITY & GROUND TRUTH VALIDATION
# ============================================================


def validate_primary_scenario_manifest(
    scenarios: List[Dict[str, Any]],
    canonical_manifest: Optional[List[Dict[str, Any]]] = None,
) -> None:
    """Validate that the primary scenarios match the canonical frozen manifest exactly.

    Compares against canonical w5_primary_scenarios_v1.json.
    Verifies exact match for every scenario:
    - scenario_id
    - scenario_version
    - track
    - user_stratum
    - destination
    - declared_interests
    - top_k
    - candidate_catalog
    """
    if canonical_manifest is None:
        canonical_path = REPO_ROOT / PRIMARY_SCENARIOS_RELPATH
        if not canonical_path.exists():
            raise FileNotFoundError(f"Canonical primary scenario manifest not found at {canonical_path}")
        canonical_manifest = json.loads(canonical_path.read_text(encoding="utf-8"))

    if len(scenarios) != len(canonical_manifest):
        raise ValueError(
            f"Expected exactly {len(canonical_manifest)} primary scenarios, got {len(scenarios)}"
        )

    canonical_map = {sc["scenario_id"]: sc for sc in canonical_manifest}
    input_ids = [sc.get("scenario_id") for sc in scenarios]

    seen_ids: Set[str] = set()
    for sid in input_ids:
        if not sid or not isinstance(sid, str):
            raise ValueError(f"Invalid or missing scenario_id: {sid!r}")
        if sid in seen_ids:
            raise ValueError(f"Duplicate scenario_id in primary scenarios: {sid}")
        seen_ids.add(sid)

    if seen_ids != set(canonical_map.keys()):
        missing = set(canonical_map.keys()) - seen_ids
        extra = seen_ids - set(canonical_map.keys())
        if missing and extra:
            raise ValueError(f"Primary scenario ID mismatch: missing {missing}, extra {extra}")
        if missing:
            raise ValueError(f"Primary scenarios missing canonical IDs: {missing}")
        if extra:
            raise ValueError(f"Primary scenarios contain unknown IDs: {extra}")

    identity_fields = (
        "scenario_id",
        "scenario_version",
        "track",
        "user_stratum",
        "destination",
        "declared_interests",
        "top_k",
        "candidate_catalog",
    )

    for sc in scenarios:
        sid = sc["scenario_id"]
        canonical_sc = canonical_map[sid]
        for field in identity_fields:
            if field not in sc:
                raise ValueError(f"Scenario {sid} is missing required field {field!r}")
            val = sc[field]
            canon_val = canonical_sc[field]
            if val != canon_val:
                raise ValueError(
                    f"Scenario {sid} field {field!r} mismatch: got {val!r}, expected {canon_val!r}"
                )

    # Invariants verification
    u1_count = sum(1 for s in scenarios if s.get("user_stratum") == "U1")
    u2_count = sum(1 for s in scenarios if s.get("user_stratum") == "U2")
    if u1_count != 15 or u2_count != 15:
        raise ValueError(f"Expected 15 U1 and 15 U2 scenarios, got {u1_count} U1, {u2_count} U2")

    dest_counts = {
        d: sum(1 for s in scenarios if s.get("destination") == d) for d in FROZEN_DESTINATIONS
    }
    expected_dest_counts = {"ha-noi": 9, "da-nang": 11, "ha-long": 10}
    if dest_counts != expected_dest_counts:
        raise ValueError(f"Destination scenario counts mismatch: {dest_counts} != {expected_dest_counts}")


def validate_pool_manifest_consistency(
    scenarios: List[Dict[str, Any]],
    internal_pool: List[Dict[str, Any]],
) -> None:
    """Verify internal pool has exactly one record per canonical primary scenario, matching destination."""
    scenario_map = {sc["scenario_id"]: sc for sc in scenarios}
    pool_seen_ids: Set[str] = set()

    if len(internal_pool) != len(scenarios):
        raise ValueError(f"Pool scenario count mismatch: expected {len(scenarios)}, got {len(internal_pool)}")

    for pool_sc in internal_pool:
        sid = pool_sc.get("scenario_id")
        if not sid or not isinstance(sid, str):
            raise ValueError(f"Pool record missing or invalid scenario_id: {sid!r}")
        if sid in pool_seen_ids:
            raise ValueError(f"Duplicate scenario_id in candidate pool: {sid}")
        pool_seen_ids.add(sid)

        if sid not in scenario_map:
            raise ValueError(f"Candidate pool contains unknown scenario_id: {sid}")

        expected_dest = scenario_map[sid]["destination"]
        actual_dest = pool_sc.get("destination")
        if actual_dest != expected_dest:
            raise ValueError(
                f"Candidate pool scenario {sid} destination mismatch: got {actual_dest!r}, expected {expected_dest!r}"
            )

    if pool_seen_ids != set(scenario_map.keys()):
        missing = set(scenario_map.keys()) - pool_seen_ids
        raise ValueError(f"Candidate pool missing scenarios: {missing}")


def validate_system_ranking_integrity(
    system_name: str,
    scenario: Dict[str, Any],
    ranking: List[Dict[str, Any]],
    pool_place_ids: Set[str],
    destination_catalog_ids: Set[str],
) -> None:
    """Validate Top-10 ranking properties strictly."""
    sid = scenario["scenario_id"]
    dest = scenario["destination"]

    if len(ranking) != 10:
        raise ValueError(
            f"Canonical primary ranking for {system_name} on {sid} must have length 10, got {len(ranking)}"
        )

    pids: List[str] = []
    for idx, item in enumerate(ranking):
        pid = item.get("place_id")
        if not pid or not isinstance(pid, str):
            raise ValueError(f"Missing place_id in {system_name} on {sid} at rank {idx + 1}")
        if pid not in pool_place_ids:
            raise ValueError(f"Place {pid} in {system_name} on {sid} does not belong to candidate pool")
        if pid not in destination_catalog_ids:
            raise ValueError(f"Place {pid} in {system_name} on {sid} does not belong to {dest} catalog")
        pids.append(pid)

    if len(set(pids)) != 10:
        raise ValueError(f"Duplicate place_ids in Top-10 ranking for {system_name} on {sid}: {pids}")


def load_and_validate_ground_truth(
    gt_source: Union[str, Path, Dict[str, Any]],
    expected_pool_version: str = EXPECTED_POOL_VERSION,
    expected_rubric_version: str = EXPECTED_RUBRIC_VERSION,
    expected_metadata_version: str = EXPECTED_METADATA_VERSION,
    expected_keys: Optional[Set[Tuple[str, str]]] = None,
) -> Dict[str, Any]:
    """Load and validate ground truth data.

    Validates:
    - pool_version == expected_pool_version
    - rubric_version == expected_rubric_version
    - metadata_version == expected_metadata_version
    - records list exists and total_records matches
    - exact (scenario_id, place_id) membership matching 474 frozen keys (or expected_keys)
    - no duplicate (scenario_id, place_id) keys
    - no duplicate judge_item_id
    - record-level pool_version, rubric_version, metadata_version match top-level contract
    - all labels are strictly valid via validate_relevance_label
    - distinguishes template_version from gt_version (does NOT fabricate gt_version when absent)
    """
    if isinstance(gt_source, (str, Path)):
        path = Path(gt_source)
        if not path.exists():
            raise FileNotFoundError(f"Ground truth file not found: {path}")
        raw_text = path.read_text(encoding="utf-8")
        data = json.loads(raw_text)
    elif isinstance(gt_source, dict):
        data = gt_source
    else:
        raise TypeError(f"Expected path or dict for gt_source, got {type(gt_source).__name__}")

    pool_ver = data.get("pool_version")
    if pool_ver != expected_pool_version:
        raise ValueError(f"GT pool_version mismatch: got {pool_ver!r}, expected {expected_pool_version!r}")

    rubric_ver = data.get("rubric_version")
    if rubric_ver != expected_rubric_version:
        raise ValueError(f"GT rubric_version mismatch: got {rubric_ver!r}, expected {expected_rubric_version!r}")

    meta_ver = data.get("metadata_version")
    if meta_ver is not None and meta_ver != expected_metadata_version:
        raise ValueError(f"GT metadata_version mismatch: got {meta_ver!r}, expected {expected_metadata_version!r}")

    records = data.get("records")
    if not isinstance(records, list):
        raise ValueError("GT data must contain a 'records' list")

    total_records = data.get("total_records", len(records))
    if len(records) != total_records:
        raise ValueError(f"GT record count mismatch: header specifies {total_records}, got {len(records)}")

    seen_keys: Set[Tuple[str, str]] = set()
    seen_judge_item_ids: Set[str] = set()
    gt_map: Dict[Tuple[str, str], Optional[int]] = {}

    for idx, rec in enumerate(records):
        sid = rec.get("scenario_id")
        pid = rec.get("place_id")
        if not sid or not pid or not isinstance(sid, str) or not isinstance(pid, str):
            raise ValueError(f"Missing or invalid scenario_id or place_id at record {idx}: ({sid!r}, {pid!r})")

        key = (sid, pid)
        if key in seen_keys:
            raise ValueError(f"Duplicate (scenario_id, place_id) in GT at record {idx}: {key}")
        seen_keys.add(key)

        jid = rec.get("judge_item_id")
        if jid is not None:
            if not isinstance(jid, str):
                raise ValueError(f"Invalid judge_item_id at record {idx}: {jid!r}")
            if jid in seen_judge_item_ids:
                raise ValueError(f"Duplicate judge_item_id in GT at record {idx}: {jid}")
            seen_judge_item_ids.add(jid)

        rec_pool_ver = rec.get("pool_version")
        if rec_pool_ver is not None and rec_pool_ver != expected_pool_version:
            raise ValueError(
                f"Record {idx} ({sid}, {pid}) pool_version mismatch: got {rec_pool_ver!r}, expected {expected_pool_version!r}"
            )
        rec_rubric_ver = rec.get("rubric_version")
        if rec_rubric_ver is not None and rec_rubric_ver != expected_rubric_version:
            raise ValueError(
                f"Record {idx} ({sid}, {pid}) rubric_version mismatch: got {rec_rubric_ver!r}, expected {expected_rubric_version!r}"
            )
        rec_meta_ver = rec.get("metadata_version")
        if rec_meta_ver is not None and rec_meta_ver != expected_metadata_version:
            raise ValueError(
                f"Record {idx} ({sid}, {pid}) metadata_version mismatch: got {rec_meta_ver!r}, expected {expected_metadata_version!r}"
            )

        raw_rel = rec.get("final_relevance")
        try:
            validated_rel = validate_relevance_label(raw_rel)
        except ValueError as err:
            raise ValueError(f"Invalid relevance in GT record {idx} ({sid}, {pid}): {err}") from err

        gt_map[key] = validated_rel

    # Validate exact GT key membership against expected 474 frozen keys or expected_keys
    target_expected_keys = expected_keys
    if target_expected_keys is None:
        canonical_pool_path = REPO_ROOT / INTERNAL_POOL_RELPATH
        if canonical_pool_path.exists():
            pool_data = json.loads(canonical_pool_path.read_text(encoding="utf-8"))
            target_expected_keys = {
                (sc["scenario_id"], item["place_id"])
                for sc in pool_data
                for item in sc.get("items", [])
            }

    if target_expected_keys is not None:
        if seen_keys != target_expected_keys:
            missing = target_expected_keys - seen_keys
            extra = seen_keys - target_expected_keys
            if missing and extra:
                raise ValueError(
                    f"GT key mismatch: {len(missing)} missing keys and {len(extra)} extra keys"
                )
            if missing:
                raise ValueError(f"GT missing {len(missing)} expected (scenario_id, place_id) keys: sample {list(missing)[:3]}")
            if extra:
                raise ValueError(f"GT contains {len(extra)} unexpected (scenario_id, place_id) keys: sample {list(extra)[:3]}")

    # Distinguish template_version from gt_version; do not fabricate gt_version when absent
    template_version = data.get("template_version")
    gt_version = data.get("gt_version")

    return {
        "template_version": template_version,
        "gt_version": gt_version,
        "pool_version": pool_ver,
        "rubric_version": rubric_ver,
        "metadata_version": data.get("metadata_version", expected_metadata_version),
        "total_records": len(records),
        "gt_map": gt_map,
    }


def evaluate_system(
    system_name: str,
    scenarios: List[Dict[str, Any]],
    internal_pool: List[Dict[str, Any]],
    system_rankings: Dict[str, List[Dict[str, Any]]],
    gt_map: Dict[Tuple[str, str], Optional[int]],
    catalog_sizes: Dict[str, int] = EXPECTED_CATALOG_SIZES,
    destination_catalogs: Optional[Dict[str, Set[str]]] = None,
    duplicate_map: Optional[Dict[str, str]] = None,
    k: int = 10,
) -> Dict[str, Any]:
    """Execute full evaluation of one system across all scenarios."""
    if system_name not in VALID_SYSTEMS:
        raise ValueError(
            f"Invalid system_name {system_name!r}. Allowed systems: {sorted(list(VALID_SYSTEMS))}"
        )

    # Validate pool ↔ scenario manifest consistency
    validate_pool_manifest_consistency(scenarios, internal_pool)

    # Resolve destination catalogs if not provided
    if destination_catalogs is None:
        freeze_path = REPO_ROOT / DATASET_FREEZE_V2_RELPATH
        if freeze_path.exists():
            freeze_places = json.loads(freeze_path.read_text(encoding="utf-8"))
            destination_catalogs = {d: set() for d in FROZEN_DESTINATIONS}
            for p in freeze_places:
                if p.get("is_rec_a_core_v2") is True:
                    slug = p.get("destination_slug")
                    if slug in destination_catalogs:
                        destination_catalogs[slug].add(p["place_id"])
        else:
            destination_catalogs = {d: set() for d in FROZEN_DESTINATIONS}

    pool_map = {sc["scenario_id"]: sc for sc in internal_pool}
    scenario_results: List[Dict[str, Any]] = []

    for sc in scenarios:
        sid = sc["scenario_id"]
        dest = sc["destination"]
        if sid not in pool_map:
            raise ValueError(f"Scenario {sid} not found in internal pool")
        pool_sc = pool_map[sid]

        if sid not in system_rankings:
            raise ValueError(f"Missing ranking for system {system_name} on scenario {sid}")
        ranked_places = system_rankings[sid]

        # Enforce ranking integrity directly inside evaluate_system
        pool_pids = {it["place_id"] for it in pool_sc["items"]}
        dest_pids = destination_catalogs.get(dest, set())
        validate_system_ranking_integrity(
            system_name=system_name,
            scenario=sc,
            ranking=ranked_places,
            pool_place_ids=pool_pids,
            destination_catalog_ids=dest_pids,
        )

        scenario_gt = {item["place_id"]: gt_map.get((sid, item["place_id"])) for item in pool_sc["items"]}

        res = evaluate_scenario(
            scenario_info=sc,
            ranked_places=ranked_places,
            pool_items=pool_sc["items"],
            gt_map=scenario_gt,
            system_name=system_name,
            duplicate_map=duplicate_map,
            k=k,
        )
        scenario_results.append(res)

    # Aggregations
    dest_means: Dict[str, Dict[str, Optional[float]]] = {}
    dest_counts: Dict[str, Dict[str, int]] = {}

    metrics_keys = [
        "ndcg_at_10",
        "precision_at_10",
        "pooled_recall_at_10",
        "hit_rate_at_10",
        "category_ild_at_10",
        "i1_exposure_at_10",
    ]

    for d in FROZEN_DESTINATIONS:
        d_res = [r for r in scenario_results if r["destination"] == d]
        dest_means[d] = {}
        dest_counts[d] = {}
        for m in metrics_keys:
            scorable = [r[m] for r in d_res if r[m] is not None]
            dest_counts[d][m] = len(scorable)
            dest_means[d][m] = round(sum(scorable) / len(scorable), 6) if scorable else None

    # Overall macro means
    overall_macro: Dict[str, Optional[float]] = {}
    for m in metrics_keys:
        per_d = {d: dest_means[d][m] for d in FROZEN_DESTINATIONS}
        overall_macro[m] = aggregate_destination_macro(per_d)

    # Unweighted all-scenario means
    unweighted_means: Dict[str, Optional[float]] = {}
    for m in metrics_keys:
        unweighted_means[m] = aggregate_unweighted_mean([r[m] for r in scenario_results])

    # Stratum breakdowns (U1, U2)
    stratum_means: Dict[str, Dict[str, Optional[float]]] = {}
    stratum_counts: Dict[str, Dict[str, int]] = {}
    for strat in ("U1", "U2"):
        s_res = [r for r in scenario_results if r["user_stratum"] == strat]
        stratum_means[strat] = {}
        stratum_counts[strat] = {}
        for m in metrics_keys:
            scorable = [r[m] for r in s_res if r[m] is not None]
            stratum_counts[strat][m] = len(scorable)
            stratum_means[strat][m] = round(sum(scorable) / len(scorable), 6) if scorable else None

    # Catalog Coverage
    coverage_by_dest: Dict[str, float] = {}
    for d in FROZEN_DESTINATIONS:
        d_scs = [sc["scenario_id"] for sc in scenarios if sc["destination"] == d]
        unique_pids: Set[str] = set()
        for sid in d_scs:
            if sid not in system_rankings:
                raise ValueError(f"Missing ranking for system {system_name} on scenario {sid}")
            for item in system_rankings[sid][:k]:
                unique_pids.add(item["place_id"])
        coverage_by_dest[d] = catalog_coverage_at_k(len(unique_pids), catalog_sizes[d])

    macro_cov = macro_destination_coverage(
        coverage_by_dest["ha-noi"],
        coverage_by_dest["da-nang"],
        coverage_by_dest["ha-long"],
    )
    overall_macro["catalog_coverage_at_10"] = macro_cov

    return {
        "system": system_name,
        "overall_destination_macro": overall_macro,
        "unweighted_all_scenario_mean": unweighted_means,
        "destination_breakdown": {
            d: {
                "means": dest_means[d],
                "scorable_counts": dest_counts[d],
                "coverage_at_10": coverage_by_dest[d],
            }
            for d in FROZEN_DESTINATIONS
        },
        "stratum_breakdown": {
            strat: {
                "means": stratum_means[strat],
                "scorable_counts": stratum_counts[strat],
            }
            for strat in ("U1", "U2")
        },
        "scenario_results": scenario_results,
    }


def build_paired_comparison(
    baseline_eval: Dict[str, Any],
    a2_eval: Dict[str, Any],
    scenarios: List[Dict[str, Any]],
    catalog_sizes: Dict[str, int] = EXPECTED_CATALOG_SIZES,
    seed: int = W5_METRIC_BOOTSTRAP_SEED,
    replicates: int = BOOTSTRAP_REPLICATES,
) -> Dict[str, Any]:
    """Execute paired destination-stratified comparisons across all metrics."""
    base_res = {r["scenario_id"]: r for r in baseline_eval["scenario_results"]}
    a2_res = {r["scenario_id"]: r for r in a2_eval["scenario_results"]}

    query_metrics = [
        "ndcg_at_10",
        "precision_at_10",
        "pooled_recall_at_10",
        "hit_rate_at_10",
        "category_ild_at_10",
        "i1_exposure_at_10",
    ]

    metrics_comparison: Dict[str, Any] = {}

    for m in query_metrics:
        paired_by_dest: Dict[str, List[Tuple[Optional[float], Optional[float]]]] = {
            d: [] for d in FROZEN_DESTINATIONS
        }
        for sc in scenarios:
            sid = sc["scenario_id"]
            d = sc["destination"]
            if sid not in base_res or sid not in a2_res:
                raise ValueError(f"Scenario {sid} missing from evaluation results")
            b_val = base_res[sid].get(m)
            a_val = a2_res[sid].get(m)
            paired_by_dest[d].append((b_val, a_val))

        boot_res = paired_destination_stratified_bootstrap(
            paired_by_dest, seed=seed, replicates=replicates
        )
        metrics_comparison[m] = boot_res

    # Coverage paired bootstrap using validated topk_place_ids
    scenarios_by_dest: Dict[str, List[Dict[str, Any]]] = {d: [] for d in FROZEN_DESTINATIONS}
    for sc in scenarios:
        sid = sc["scenario_id"]
        d = sc["destination"]
        if "topk_place_ids" not in base_res[sid]:
            raise ValueError(f"Missing validated baseline topk_place_ids for scenario {sid}")
        if "topk_place_ids" not in a2_res[sid]:
            raise ValueError(f"Missing validated A2 topk_place_ids for scenario {sid}")
        b_pids = list(base_res[sid]["topk_place_ids"])
        a_pids = list(a2_res[sid]["topk_place_ids"])
        if len(b_pids) != 10:
            raise ValueError(f"Baseline topk_place_ids for {sid} must have length 10, got {len(b_pids)}")
        if len(a_pids) != 10:
            raise ValueError(f"A2 topk_place_ids for {sid} must have length 10, got {len(a_pids)}")
        scenarios_by_dest[d].append({
            "scenario_id": sid,
            "baseline_top10": b_pids,
            "a2_top10": a_pids,
        })

    # Coverage from system results
    cov_boot = paired_coverage_stratified_bootstrap(
        scenarios_by_dest, catalog_sizes=catalog_sizes, seed=seed, replicates=replicates
    )
    metrics_comparison["catalog_coverage_at_10"] = cov_boot

    # Verdict determination
    ndcg_info = metrics_comparison["ndcg_at_10"]
    ild_info = metrics_comparison["category_ild_at_10"]
    cov_info = metrics_comparison["catalog_coverage_at_10"]

    verdict = classify_final_verdict(
        ndcg_ci=ndcg_info.get("ci_95"),
        ild_ci=ild_info.get("ci_95"),
        cov_ci=cov_info.get("ci_95"),
        ild_point_delta=ild_info.get("observed_point_delta"),
        cov_point_delta=cov_info.get("observed_point_delta"),
    )

    verdict_reason = None
    if ndcg_info.get("status") == "PRIMARY_INFERENCE_NOT_ESTIMABLE":
        verdict_reason = "PRIMARY_INFERENCE_NOT_ESTIMABLE"

    return {
        "primary_metric": "ndcg_at_10",
        "observed_delta_ndcg_at_10": ndcg_info.get("observed_point_delta"),
        "ndcg_ci_95": ndcg_info.get("ci_95"),
        "scientific_verdict": verdict,
        "verdict_reason": verdict_reason,
        "metrics": metrics_comparison,
    }


def build_final_evaluation_result(
    baseline_eval: Dict[str, Any],
    a2_eval: Dict[str, Any],
    comparison: Dict[str, Any],
    gt_meta: Dict[str, Any],
) -> Dict[str, Any]:
    """Construct final comprehensive evaluation document."""
    ndcg_info = comparison.get("metrics", {}).get("ndcg_at_10", {})
    effective_sample_counts = ndcg_info.get("sample_attrition", {})

    return {
        "evaluation_version": EVALUATION_VERSION,
        "template_version": gt_meta.get("template_version"),
        "gt_version": gt_meta.get("gt_version"),
        "pool_version": gt_meta.get("pool_version"),
        "rubric_version": gt_meta.get("rubric_version"),
        "metadata_version": gt_meta.get("metadata_version"),
        "primary_metric": "NDCG@10",
        "duplicate_policy_status": "PENDING",
        "final_scientific_evaluation_ready": False,
        "category_ild_semantics": CATEGORY_ILD_SEMANTICS,
        "effective_sample_counts": effective_sample_counts,
        "systems": {
            SYSTEM_BASELINE: {
                "overall_destination_macro": baseline_eval["overall_destination_macro"],
                "unweighted_all_scenario_mean": baseline_eval["unweighted_all_scenario_mean"],
                "destination_breakdown": baseline_eval["destination_breakdown"],
                "stratum_breakdown": baseline_eval["stratum_breakdown"],
            },
            SYSTEM_A2: {
                "overall_destination_macro": a2_eval["overall_destination_macro"],
                "unweighted_all_scenario_mean": a2_eval["unweighted_all_scenario_mean"],
                "destination_breakdown": a2_eval["destination_breakdown"],
                "stratum_breakdown": a2_eval["stratum_breakdown"],
            },
        },
        "paired_comparison": comparison,
        "scientific_verdict": comparison["scientific_verdict"],
    }


def run_full_evaluation(
    gt_source: Union[str, Path, Dict[str, Any]],
    repo_root: Optional[Path] = None,
    primary_scenarios_source: Optional[Union[str, Path, List[Dict[str, Any]]]] = None,
    canonical_manifest_source: Optional[Union[str, Path, List[Dict[str, Any]]]] = None,
    internal_pool_source: Optional[Union[str, Path, List[Dict[str, Any]]]] = None,
    freeze_places_source: Optional[Union[str, Path, List[Dict[str, Any]]]] = None,
    system_rankings_source: Optional[Dict[str, Dict[str, List[Dict[str, Any]]]]] = None,
    catalog_sizes: Optional[Dict[str, int]] = None,
    destination_catalogs: Optional[Dict[str, Set[str]]] = None,
    seed: int = W5_METRIC_BOOTSTRAP_SEED,
    replicates: int = BOOTSTRAP_REPLICATES,
    duplicate_map: Optional[Dict[str, str]] = None,
    is_synthetic_test: bool = False,
) -> Dict[str, Any]:
    """Single central orchestration pipeline for W5 recommender evaluation.

    Executes in strict order:
    1. Load primary scenarios manifest
    2. Validate exact frozen scenario identity against canonical manifest
    3. Load internal candidate pool
    4. Validate pool ↔ scenario manifest consistency
    5. Build destination catalog IDs from Freeze V2 (or provided sources)
    6. Construct expected 474 frozen candidate pool keys
    7. Load + validate GT, enforcing exact key-set membership and label validity
    8. Extract/validate baseline ranking and A2 ranking
    9. Evaluate baseline system (enforcing ranking integrity inside evaluate_system)
    10. Evaluate A2 system (enforcing ranking integrity inside evaluate_system)
    11. Paired query-level metrics aggregation and stratified bootstrap
    12. Paired catalog coverage stratified bootstrap
    13. Final verdict determination
    14. Assemble final comprehensive evaluation result
    """
    root = repo_root or REPO_ROOT

    # 1. Load primary scenarios
    if primary_scenarios_source is None:
        p_path = root / PRIMARY_SCENARIOS_RELPATH
        primary_scenarios = json.loads(p_path.read_text(encoding="utf-8"))
    elif isinstance(primary_scenarios_source, (str, Path)):
        primary_scenarios = json.loads(Path(primary_scenarios_source).read_text(encoding="utf-8"))
    elif isinstance(primary_scenarios_source, list):
        primary_scenarios = primary_scenarios_source
    else:
        raise TypeError(f"Invalid primary_scenarios_source: {type(primary_scenarios_source).__name__}")

    # 2. Validate exact frozen scenario identity
    validate_primary_scenario_manifest(primary_scenarios, canonical_manifest=canonical_manifest_source)

    # 3. Load internal pool
    if internal_pool_source is None:
        pool_path = root / INTERNAL_POOL_RELPATH
        internal_pool = json.loads(pool_path.read_text(encoding="utf-8"))
    elif isinstance(internal_pool_source, (str, Path)):
        internal_pool = json.loads(Path(internal_pool_source).read_text(encoding="utf-8"))
    elif isinstance(internal_pool_source, list):
        internal_pool = internal_pool_source
    else:
        raise TypeError(f"Invalid internal_pool_source: {type(internal_pool_source).__name__}")

    # 4. Validate pool ↔ manifest consistency
    validate_pool_manifest_consistency(primary_scenarios, internal_pool)

    # 5. Build destination catalog IDs from Freeze V2
    if destination_catalogs is None:
        if freeze_places_source is None:
            freeze_path = root / DATASET_FREEZE_V2_RELPATH
            freeze_places = json.loads(freeze_path.read_text(encoding="utf-8"))
        elif isinstance(freeze_places_source, (str, Path)):
            freeze_places = json.loads(Path(freeze_places_source).read_text(encoding="utf-8"))
        elif isinstance(freeze_places_source, list):
            freeze_places = freeze_places_source
        else:
            raise TypeError(f"Invalid freeze_places_source: {type(freeze_places_source).__name__}")

        destination_catalogs = {d: set() for d in FROZEN_DESTINATIONS}
        for p in freeze_places:
            if p.get("is_rec_a_core_v2") is True:
                slug = p.get("destination_slug")
                if slug in destination_catalogs:
                    destination_catalogs[slug].add(p["place_id"])

    cat_sizes = catalog_sizes or {d: len(destination_catalogs[d]) for d in FROZEN_DESTINATIONS}

    # 6. Expected GT keys
    expected_gt_keys = {
        (sc["scenario_id"], item["place_id"])
        for sc in internal_pool
        for item in sc.get("items", [])
    }

    # 7. Load + validate GT
    gt_data = load_and_validate_ground_truth(gt_source, expected_keys=expected_gt_keys)

    # 8. Extract system rankings
    if system_rankings_source is None:
        system_rankings = extract_system_rankings(internal_pool)
    else:
        system_rankings = system_rankings_source

    if SYSTEM_BASELINE not in system_rankings:
        raise ValueError(f"system_rankings missing baseline system: {SYSTEM_BASELINE}")
    if SYSTEM_A2 not in system_rankings:
        raise ValueError(f"system_rankings missing A2 system: {SYSTEM_A2}")

    baseline_rankings = system_rankings[SYSTEM_BASELINE]
    a2_rankings = system_rankings[SYSTEM_A2]

    # 9. Evaluate baseline
    baseline_eval = evaluate_system(
        system_name=SYSTEM_BASELINE,
        scenarios=primary_scenarios,
        internal_pool=internal_pool,
        system_rankings=baseline_rankings,
        gt_map=gt_data["gt_map"],
        catalog_sizes=cat_sizes,
        destination_catalogs=destination_catalogs,
        duplicate_map=duplicate_map,
    )

    # 10. Evaluate A2
    a2_eval = evaluate_system(
        system_name=SYSTEM_A2,
        scenarios=primary_scenarios,
        internal_pool=internal_pool,
        system_rankings=a2_rankings,
        gt_map=gt_data["gt_map"],
        catalog_sizes=cat_sizes,
        destination_catalogs=destination_catalogs,
        duplicate_map=duplicate_map,
    )

    # 11-13. Paired comparison & bootstrap & verdict
    comparison = build_paired_comparison(
        baseline_eval=baseline_eval,
        a2_eval=a2_eval,
        scenarios=primary_scenarios,
        catalog_sizes=cat_sizes,
        seed=seed,
        replicates=replicates,
    )

    # 14. Final evaluation result
    final_res = build_final_evaluation_result(
        baseline_eval=baseline_eval,
        a2_eval=a2_eval,
        comparison=comparison,
        gt_meta=gt_data,
    )

    if is_synthetic_test:
        final_res["synthetic_test_flag"] = "SYNTHETIC_TEST_ONLY"

    return final_res


# ============================================================
# DRY-RUN VALIDATION
# ============================================================


def run_dry_run_validation(repo_root: Optional[Path] = None) -> Dict[str, Any]:
    """Execute pre-registered dry-run validation.

    Validates:
    - Freeze V2 catalog integrity (622 core, 145 HN, 289 DN, 188 HL, 0 leakage)
    - Scenario manifest exact identity (30 primary: 15 U1, 15 U2; 6 thin)
    - Internal candidate pool integrity (30 scenarios, 474 unique candidate pool records)
    - Recommender top-10 structural integrity (no duplicates, exactly 10 items)
    - Preserves scientific boundary: NO human labels, NO winner, NO comparison.
    """
    root = repo_root or REPO_ROOT

    # 1. Freeze V2 validation
    freeze_path = root / DATASET_FREEZE_V2_RELPATH
    if not freeze_path.exists():
        raise FileNotFoundError(f"Freeze V2 dataset missing: {freeze_path}")
    raw_bytes = freeze_path.read_bytes()
    freeze_sha = hashlib.sha256(raw_bytes).hexdigest()
    if freeze_sha not in FREEZE_V2_ACCEPTED_SHA256:
        raise ValueError(f"Freeze V2 checksum mismatch: got {freeze_sha}, expected one of {FREEZE_V2_ACCEPTED_SHA256}")
    freeze_places = json.loads(raw_bytes.decode("utf-8"))
    core_places = [p for p in freeze_places if p.get("is_rec_a_core_v2") is True]
    if len(core_places) != EXPECTED_TOTAL_CORE:
        raise ValueError(f"Expected {EXPECTED_TOTAL_CORE} core places, got {len(core_places)}")

    core_by_dest: Dict[str, Set[str]] = {d: set() for d in FROZEN_DESTINATIONS}
    for p in core_places:
        slug = p.get("destination_slug")
        if slug in core_by_dest:
            core_by_dest[slug].add(p["place_id"])

    hn_count = len(core_by_dest["ha-noi"])
    dn_count = len(core_by_dest["da-nang"])
    hl_count = len(core_by_dest["ha-long"])
    if hn_count != EXPECTED_CATALOG_SIZES["ha-noi"]:
        raise ValueError(f"HN core count mismatch: {hn_count} != {EXPECTED_CATALOG_SIZES['ha-noi']}")
    if dn_count != EXPECTED_CATALOG_SIZES["da-nang"]:
        raise ValueError(f"DN core count mismatch: {dn_count} != {EXPECTED_CATALOG_SIZES['da-nang']}")
    if hl_count != EXPECTED_CATALOG_SIZES["ha-long"]:
        raise ValueError(f"HL core count mismatch: {hl_count} != {EXPECTED_CATALOG_SIZES['ha-long']}")

    secondary_places = [p for p in freeze_places if p.get("is_rec_a_core_v2") is False]
    secondary_ids = {p["place_id"] for p in secondary_places}
    if len(secondary_ids) != 137:
        raise ValueError(f"Expected 137 secondary places, got {len(secondary_ids)}")

    # 2. Primary scenarios validation
    primary_path = root / PRIMARY_SCENARIOS_RELPATH
    if not primary_path.exists():
        raise FileNotFoundError(f"Primary scenarios manifest missing: {primary_path}")
    primary_scenarios = json.loads(primary_path.read_text(encoding="utf-8"))
    validate_primary_scenario_manifest(primary_scenarios)

    # 3. Thin scenarios validation
    thin_path = root / THIN_SCENARIOS_RELPATH
    if not thin_path.exists():
        raise FileNotFoundError(f"Thin scenarios manifest missing: {thin_path}")
    thin_scenarios = json.loads(thin_path.read_text(encoding="utf-8"))
    if len(thin_scenarios) != 6:
        raise ValueError(f"Expected 6 thin scenarios, got {len(thin_scenarios)}")

    # 4. Internal pool validation
    pool_path = root / INTERNAL_POOL_RELPATH
    if not pool_path.exists():
        raise FileNotFoundError(f"Internal candidate pool missing: {pool_path}")
    internal_pool = json.loads(pool_path.read_text(encoding="utf-8"))
    if len(internal_pool) != 30:
        raise ValueError(f"Expected 30 scenarios in internal pool, got {len(internal_pool)}")

    total_pool_records = sum(len(sc["items"]) for sc in internal_pool)
    if total_pool_records != 474:
        raise ValueError(f"Expected 474 candidate pool records, got {total_pool_records}")

    validate_pool_manifest_consistency(primary_scenarios, internal_pool)

    # Validate Top-10 structural properties for each system
    system_rankings = extract_system_rankings(internal_pool)
    scenario_map = {sc["scenario_id"]: sc for sc in primary_scenarios}

    for sc in internal_pool:
        sid = sc["scenario_id"]
        primary_spec = scenario_map[sid]
        dest = primary_spec["destination"]
        dest_catalog = core_by_dest[dest]
        pool_pids = {it["place_id"] for it in sc["items"]}

        base_top10 = system_rankings[SYSTEM_BASELINE][sid]
        a2_top10 = system_rankings[SYSTEM_A2][sid]

        validate_system_ranking_integrity(
            SYSTEM_BASELINE, primary_spec, base_top10, pool_pids, dest_catalog
        )
        validate_system_ranking_integrity(
            SYSTEM_A2, primary_spec, a2_top10, pool_pids, dest_catalog
        )

        # Check secondary leakage and item valid attributes
        for it in sc["items"]:
            if it["place_id"] in secondary_ids:
                raise ValueError(f"Secondary place {it['place_id']} leaked into pool for {sid}")
            if not it.get("category"):
                raise ValueError(f"Missing category for place {it['place_id']} in {sid}")
            if it.get("i0_i1_stratum") not in ("I0", "I1"):
                raise ValueError(f"Invalid stratum {it.get('i0_i1_stratum')} in {sid}")

    u1_scenarios = [s for s in primary_scenarios if s.get("user_stratum") == "U1"]
    u2_scenarios = [s for s in primary_scenarios if s.get("user_stratum") == "U2"]

    return {
        "status": "VALIDATION_PASSED",
        "freeze_sha256": freeze_sha,
        "total_core_places": len(core_places),
        "destination_counts": {"ha-noi": hn_count, "da-nang": dn_count, "ha-long": hl_count},
        "secondary_places": len(secondary_ids),
        "secondary_leakage": 0,
        "primary_scenarios": len(primary_scenarios),
        "u1_scenarios": len(u1_scenarios),
        "u2_scenarios": len(u2_scenarios),
        "thin_scenarios": len(thin_scenarios),
        "candidate_pool_records": total_pool_records,
        "evaluated_systems": [SYSTEM_BASELINE, SYSTEM_A2],
        "top_k_evaluated": 10,
        "duplicate_policy_status": "PENDING",
        "final_scientific_evaluation_ready": False,
        "human_judgments_collected": 0,
        "human_gt_available": False,
        "scientific_winner": "UNKNOWN",
        "category_ild_semantics": CATEGORY_ILD_SEMANTICS,
    }


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="W5 Frozen Metric and Scientific Evaluation Runner")
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate scenario structure, system rankings, pool membership, and Freeze V2 invariants without computing relevance.",
    )
    parser.add_argument(
        "--gt-file",
        type=str,
        default=None,
        help="Path to merged human ground truth JSON file (future evaluation).",
    )
    args = parser.parse_args()

    if args.validate_only or args.gt_file is None:
        print("Executing W5 evaluation dry-run validation...")
        res = run_dry_run_validation()
        print("\n=== W5 PREP-03 VALIDATION REPORT ===")
        print(f"Status:                      {res['status']}")
        print(f"Freeze V2 Checksum:          {res['freeze_sha256']}")
        print(f"Total Core Places:           {res['total_core_places']} (HN: {res['destination_counts']['ha-noi']}, DN: {res['destination_counts']['da-nang']}, HL: {res['destination_counts']['ha-long']})")
        print(f"Secondary POI Leakage:       {res['secondary_leakage']}")
        print(f"Primary Scenarios:           {res['primary_scenarios']} (U1: {res['u1_scenarios']}, U2: {res['u2_scenarios']})")
        print(f"THIN Diagnostic Scenarios:   {res['thin_scenarios']}")
        print(f"Candidate Pool Records:      {res['candidate_pool_records']}")
        print(f"Evaluated Systems:           {res['evaluated_systems']}")
        print(f"Top-K Evaluated:             {res['top_k_evaluated']}")
        print(f"Duplicate Policy Status:     {res['duplicate_policy_status']}")
        print(f"Final Scientific Ready:      {res['final_scientific_evaluation_ready']}")
        print(f"Human Judgments Collected:   {res['human_judgments_collected']}")
        print(f"Human GT Available:          {res['human_gt_available']}")
        print(f"Scientific Winner:           {res['scientific_winner']}")
        print(f"Category ILD Semantics:      {res['category_ild_semantics']}")
        print("\nNote: Scientific comparison and winner declaration are strictly gated until HUMAN-GT is collected.")
        sys.exit(0)

    # Future ground truth evaluation path
    print(f"Ground truth file specified: {args.gt_file}")
    gt_data = load_and_validate_ground_truth(args.gt_file)
    print(f"Loaded ground truth template {gt_data['template_version']} (gt_version={gt_data['gt_version']}) with {gt_data['total_records']} records.")

    all_unresolved = all(v is None for v in gt_data["gt_map"].values())
    if all_unresolved:
        print("\nGround truth file is an empty/unadjudicated template (0 labels completed).")
        print("Scientific evaluation cannot be executed until human judgments are collected and adjudicated at W5-GT-01.")
        print("Scientific winner: UNKNOWN.")
        print("Validation status: SCHEMA_VALID_BUT_EVALUATION_GATED.")
        sys.exit(0)

    print("Scientific evaluation with real HUMAN-GT is gated until W5-METH-LOCK and human judgments are collected.")
    sys.exit(0)


if __name__ == "__main__":
    main()
