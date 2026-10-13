"""Frozen W5 Metric and Scientific Evaluation Runner.

Pre-registered evaluation runner for GoMate / WanderAI recommendation systems:
- Shared REC-A0/A1 baseline vs. REC-A2
- Evaluates 30 primary scenarios (15 U1, 15 U2 across Hanoi, Da Nang, Ha Long)
- Destination-conditioned macro aggregation (equal city weighting: Hanoi, Da Nang, Ha Long)
- Paired destination-stratified bootstrap (seed 20261013, 10,000 replicates)
- Pure metric functions: NDCG@10, Precision@10, Pooled Recall@10, HitRate@10,
  Category-ILD@10, CatalogCoverage@10, I1Exposure@10 (diagnostic)
- Strict NA handling: NA is evidence insufficiency, never cast to 0
- Pre-registered verdict classification (Rule A, B, C, INCONCLUSIVE)
- Duplicate-equivalence map interface (status PENDING until W5-GATE-DUP)

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


# ============================================================
# PURE METRIC FUNCTIONS
# ============================================================


def calculate_gain(rel: int) -> float:
    """Graded relevance gain: 2^rel - 1.

    rel=0 -> 0.0
    rel=1 -> 1.0
    rel=2 -> 3.0
    """
    if rel not in (0, 1, 2):
        raise ValueError(f"Invalid relevance label {rel}. Expected 0, 1, or 2.")
    return float((1 << rel) - 1)


def dcg_at_k(relevances: Sequence[int], k: int = 10) -> float:
    """Calculate Discounted Cumulative Gain at k using standard log2(i + 1) discount.

    DCG@k = sum_{i=1..k} (2^{rel_i} - 1) / log2(i + 1)
    """
    k_eff = min(k, len(relevances))
    dcg = 0.0
    for i in range(k_eff):
        rank = i + 1
        gain = calculate_gain(relevances[i])
        discount = math.log2(rank + 1)
        dcg += gain / discount
    return dcg


def idcg_at_k(pool_relevances: Sequence[int], k: int = 10) -> float:
    """Calculate Ideal DCG at k from numerically judged scenario candidate pool.

    Sorts all numerically judged candidate items descending by relevance, takes top k.
    """
    valid_labels = [r for r in pool_relevances if r in (0, 1, 2)]
    sorted_relevances = sorted(valid_labels, reverse=True)
    return dcg_at_k(sorted_relevances[:k], k=k)


def ndcg_at_k(
    ranked_relevances: Sequence[Optional[Union[int, str]]],
    pool_relevances: Sequence[Optional[Union[int, str]]],
    k: int = 10,
) -> Tuple[Optional[float], str]:
    """Calculate standard graded NDCG@10 against common judged pool.

    IDCG is constructed from all numerically judged items in the scenario candidate pool.

    NA / Unresolved Policy:
      If any item in evaluated Top-k is unresolved (NA or None), returns
      (None, "NOT_SCORABLE_UNRESOLVED_TOPK"). NA is NEVER cast to 0.

    IDCG = 0 Policy:
      If IDCG@k == 0 (no relevant item in judged pool), returns
      (None, "NO_RELEVANT_ITEM_IN_JUDGED_POOL").

    Returns:
      (ndcg_value, status_code)
    """
    k_eff = min(k, len(ranked_relevances))
    for i in range(k_eff):
        r = ranked_relevances[i]
        if r is None or r == "NA" or not isinstance(r, int) or r not in (0, 1, 2):
            return None, "NOT_SCORABLE_UNRESOLVED_TOPK"

    clean_ranked: List[int] = [int(r) for r in ranked_relevances[:k_eff]]  # type: ignore
    clean_pool: List[int] = [int(r) for r in pool_relevances if isinstance(r, int) and r in (0, 1, 2)]

    idcg = idcg_at_k(clean_pool, k=k)
    if idcg == 0.0:
        return None, "NO_RELEVANT_ITEM_IN_JUDGED_POOL"

    dcg = dcg_at_k(clean_ranked, k=k)
    return round(dcg / idcg, 6), "OK"


def precision_at_k(
    ranked_relevances: Sequence[Optional[Union[int, str]]],
    k: int = 10,
) -> Tuple[Optional[float], str]:
    """Precision at k with rel >= 1 threshold.

    If any item in evaluated Top-k is unresolved, returns (None, 'NOT_SCORABLE_UNRESOLVED_TOPK').
    """
    k_eff = min(k, len(ranked_relevances))
    if k_eff == 0:
        return None, "EMPTY_RANKING"

    for i in range(k_eff):
        r = ranked_relevances[i]
        if r is None or r == "NA" or not isinstance(r, int) or r not in (0, 1, 2):
            return None, "NOT_SCORABLE_UNRESOLVED_TOPK"

    relevant_count = sum(1 for i in range(k_eff) if int(ranked_relevances[i]) >= 1)  # type: ignore
    return round(relevant_count / k_eff, 6), "OK"


def pooled_recall_at_k(
    ranked_relevances: Sequence[Optional[Union[int, str]]],
    pool_relevances: Sequence[Optional[Union[int, str]]],
    k: int = 10,
) -> Tuple[Optional[float], str]:
    """Pooled Recall at k: # relevant in Top-k / # relevant in common judged pool.

    Threshold: rel >= 1.
    If pool contains zero relevant items, returns (None, 'NO_RELEVANT_ITEM_IN_JUDGED_POOL').
    If any item in evaluated Top-k is unresolved, returns (None, 'NOT_SCORABLE_UNRESOLVED_TOPK').
    """
    k_eff = min(k, len(ranked_relevances))
    if k_eff == 0:
        return None, "EMPTY_RANKING"

    for i in range(k_eff):
        r = ranked_relevances[i]
        if r is None or r == "NA" or not isinstance(r, int) or r not in (0, 1, 2):
            return None, "NOT_SCORABLE_UNRESOLVED_TOPK"

    pool_numeric = [int(r) for r in pool_relevances if isinstance(r, int) and r in (0, 1, 2)]
    pool_relevant = sum(1 for r in pool_numeric if r >= 1)
    if pool_relevant == 0:
        return None, "NO_RELEVANT_ITEM_IN_JUDGED_POOL"

    topk_relevant = sum(1 for i in range(k_eff) if int(ranked_relevances[i]) >= 1)  # type: ignore
    return round(topk_relevant / pool_relevant, 6), "OK"


def hit_rate_at_k(
    ranked_relevances: Sequence[Optional[Union[int, str]]],
    k: int = 10,
) -> Tuple[Optional[float], str]:
    """HitRate at k: 1.0 if at least one item in evaluated Top-k has rel >= 1, else 0.0.

    If any item in evaluated Top-k is unresolved, returns (None, 'NOT_SCORABLE_UNRESOLVED_TOPK').
    """
    k_eff = min(k, len(ranked_relevances))
    if k_eff == 0:
        return None, "EMPTY_RANKING"

    for i in range(k_eff):
        r = ranked_relevances[i]
        if r is None or r == "NA" or not isinstance(r, int) or r not in (0, 1, 2):
            return None, "NOT_SCORABLE_UNRESOLVED_TOPK"

    hits = any(int(ranked_relevances[i]) >= 1 for i in range(k_eff))  # type: ignore
    return (1.0 if hits else 0.0), "OK"


def category_ild_at_k(
    categories: Sequence[str],
    k: int = 10,
) -> Optional[float]:
    """Calculate Intra-List Distance (ILD) based on factual POI category.

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
    """
    k_eff = min(k, len(strata))
    if k_eff == 0:
        return 0.0
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
    """
    required = ["ha-noi", "da-nang", "ha-long"]
    vals = [destination_means[d] for d in required if d in destination_means and destination_means[d] is not None]
    if len(vals) < len(required):
        return None
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

    For each replicate:
      For each destination independently:
        Sample with replacement N_d pairs from that destination's scorable scenarios.
        Compute destination mean delta: mean(a2 - baseline).
      Primary replicate delta: mean(delta_HN, delta_DN, delta_HL).

    Returns:
      {
        "mean_delta": float,
        "ci_95": (float, float),
        "replicates": int,
        "seed": int,
      }
    """
    destinations = FROZEN_DESTINATIONS
    clean_data: Dict[str, List[Tuple[float, float]]] = {}
    for d in destinations:
        pairs = paired_scenarios_by_dest.get(d, [])
        valid_pairs = [(b, a) for b, a in pairs if b is not None and a is not None]
        clean_data[d] = valid_pairs

    rng = random.Random(seed)
    replicate_deltas: List[float] = []

    for _ in range(replicates):
        dest_deltas: List[float] = []
        for d in destinations:
            pairs = clean_data[d]
            n = len(pairs)
            if n == 0:
                dest_deltas.append(0.0)
                continue
            sampled = rng.choices(pairs, k=n)
            diffs = [a - b for b, a in sampled]
            dest_deltas.append(sum(diffs) / n)
        macro_delta = sum(dest_deltas) / len(destinations)
        replicate_deltas.append(macro_delta)

    sorted_deltas = sorted(replicate_deltas)
    ci_lower = calculate_percentile(sorted_deltas, 2.5)
    ci_upper = calculate_percentile(sorted_deltas, 97.5)
    mean_delta = sum(replicate_deltas) / len(replicate_deltas)

    return {
        "mean_delta": round(mean_delta, 6),
        "ci_95": (round(ci_lower, 6), round(ci_upper, 6)),
        "replicates": replicates,
        "seed": seed,
    }


def paired_coverage_stratified_bootstrap(
    scenarios_by_dest: Dict[str, List[Dict[str, Any]]],
    catalog_sizes: Dict[str, int],
    seed: int = W5_METRIC_BOOTSTRAP_SEED,
    replicates: int = BOOTSTRAP_REPLICATES,
) -> Dict[str, Any]:
    """Paired destination-stratified bootstrap for CatalogCoverage@10.

    For each replicate:
      For each destination independently:
        Sample with replacement N_d scenarios.
        Recompute unique coverage for baseline and a2 in resampled scenario set.
        delta_d = (unique_a2 - unique_base) / catalog_size_d.
      Primary replicate delta: mean(delta_HN, delta_DN, delta_HL).
    """
    destinations = FROZEN_DESTINATIONS
    rng = random.Random(seed)
    replicate_deltas: List[float] = []

    for _ in range(replicates):
        dest_deltas: List[float] = []
        for d in destinations:
            sc_list = scenarios_by_dest.get(d, [])
            n = len(sc_list)
            cat_size = catalog_sizes.get(d, 1)
            if n == 0 or cat_size <= 0:
                dest_deltas.append(0.0)
                continue
            sampled_sc = rng.choices(sc_list, k=n)
            base_places: Set[str] = set()
            a2_places: Set[str] = set()
            for sc in sampled_sc:
                base_places.update(sc.get("baseline_top10", []))
                a2_places.update(sc.get("a2_top10", []))
            cov_base = len(base_places) / cat_size
            cov_a2 = len(a2_places) / cat_size
            dest_deltas.append(cov_a2 - cov_base)

        macro_delta = sum(dest_deltas) / len(destinations)
        replicate_deltas.append(macro_delta)

    sorted_deltas = sorted(replicate_deltas)
    ci_lower = calculate_percentile(sorted_deltas, 2.5)
    ci_upper = calculate_percentile(sorted_deltas, 97.5)
    mean_delta = sum(replicate_deltas) / len(replicate_deltas)

    return {
        "mean_delta": round(mean_delta, 6),
        "ci_95": (round(ci_lower, 6), round(ci_upper, 6)),
        "replicates": replicates,
        "seed": seed,
    }


# ============================================================
# PRE-REGISTERED FINAL VERDICT CLASSIFICATION
# ============================================================


def classify_final_verdict(
    ndcg_ci: Tuple[float, float],
    ild_ci: Tuple[float, float],
    cov_ci: Tuple[float, float],
    ild_point_delta: float,
    cov_point_delta: float,
) -> str:
    """Classify final scientific verdict according to pre-registered rules.

    Rule A: 95% CI lower bound for Delta NDCG@10 > 0
            -> A2_RELEVANCE_SUPERIOR
    Rule B: 95% CI upper bound for Delta NDCG@10 < 0
            -> BASELINE_PREFERRED
    Rule C: NDCG CI includes 0, AND at least one diversity metric CI lower bound > 0
            with the point estimate of the other >= 0
            -> A2_DIVERSITY_TRADEOFF
    Otherwise:
            -> INCONCLUSIVE
    """
    ndcg_lower, ndcg_upper = ndcg_ci
    if ndcg_lower > 0.0:
        return "A2_RELEVANCE_SUPERIOR"
    if ndcg_upper < 0.0:
        return "BASELINE_PREFERRED"

    # NDCG CI includes zero
    if ndcg_lower <= 0.0 <= ndcg_upper:
        ild_lower, _ = ild_ci
        cov_lower, _ = cov_ci
        rule_c1 = ild_lower > 0.0 and cov_point_delta >= 0.0
        rule_c2 = cov_lower > 0.0 and ild_point_delta >= 0.0
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
    gt_map: Dict[str, Optional[Union[int, str]]],
    duplicate_map: Optional[Dict[str, str]] = None,
    k: int = 10,
) -> Dict[str, Any]:
    """Evaluate one system on one scenario against ground truth."""
    scenario_id = scenario_info["scenario_id"]
    destination = scenario_info["destination"]
    user_stratum = scenario_info.get("user_stratum", "U1")

    # Extract ranked relevances and metadata
    k_eff = min(k, len(ranked_places))
    ranked_relevances: List[Optional[Union[int, str]]] = []
    ranked_categories: List[str] = []
    ranked_strata: List[str] = []

    for item in ranked_places[:k_eff]:
        pid = item["place_id"]
        ranked_relevances.append(gt_map.get(pid))
        ranked_categories.append(item.get("category", ""))
        ranked_strata.append(item.get("i0_i1_stratum", "I0"))

    # Extract pool relevances
    pool_relevances: List[Optional[Union[int, str]]] = []
    for item in pool_items:
        pid = item["place_id"]
        pool_relevances.append(gt_map.get(pid))

    # Pool counts
    judged_pool_count = sum(1 for r in pool_relevances if isinstance(r, int) and r in (0, 1, 2))
    unresolved_pool_count = sum(1 for r in pool_relevances if r is None or r == "NA")

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
        "ndcg_at_10": ndcg_val,
        "precision_at_10": p_val,
        "pooled_recall_at_10": r_val,
        "hit_rate_at_10": hr_val,
        "category_ild_at_10": ild_val,
        "i1_exposure_at_10": i1_val,
        "judged_pool_count": judged_pool_count,
        "unresolved_pool_count": unresolved_pool_count,
        "metric_status": overall_status,
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
# DRY-RUN VALIDATION
# ============================================================


def run_dry_run_validation(repo_root: Optional[Path] = None) -> Dict[str, Any]:
    """Execute pre-registered dry-run validation.

    Validates:
    - Freeze V2 catalog integrity (622 core, 145 HN, 289 DN, 188 HL, 0 leakage)
    - Scenario manifest integrity (30 primary: 15 U1, 15 U2; 6 thin)
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
    hn_count = sum(1 for p in core_places if p.get("destination_slug") == "ha-noi")
    dn_count = sum(1 for p in core_places if p.get("destination_slug") == "da-nang")
    hl_count = sum(1 for p in core_places if p.get("destination_slug") == "ha-long")
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
    if len(primary_scenarios) != 30:
        raise ValueError(f"Expected 30 primary scenarios, got {len(primary_scenarios)}")
    u1_scenarios = [s for s in primary_scenarios if s.get("user_stratum") == "U1"]
    u2_scenarios = [s for s in primary_scenarios if s.get("user_stratum") == "U2"]
    if len(u1_scenarios) != 15 or len(u2_scenarios) != 15:
        raise ValueError(f"Expected 15 U1 and 15 U2 scenarios, got {len(u1_scenarios)} U1, {len(u2_scenarios)} U2")

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

    # Validate Top-10 structural properties for each system
    system_rankings = extract_system_rankings(internal_pool)
    for sid_idx, sc in enumerate(internal_pool):
        sid = sc["scenario_id"]
        base_top10 = system_rankings[SYSTEM_BASELINE][sid]
        a2_top10 = system_rankings[SYSTEM_A2][sid]
        if len(base_top10) != 10:
            raise ValueError(f"Scenario {sid} baseline ranking length != 10: {len(base_top10)}")
        if len(a2_top10) != 10:
            raise ValueError(f"Scenario {sid} A2 ranking length != 10: {len(a2_top10)}")

        base_ids = [it["place_id"] for it in base_top10]
        a2_ids = [it["place_id"] for it in a2_top10]
        if len(set(base_ids)) != 10:
            raise ValueError(f"Scenario {sid} baseline contains duplicate place_ids")
        if len(set(a2_ids)) != 10:
            raise ValueError(f"Scenario {sid} A2 contains duplicate place_ids")

        # Check secondary leakage
        for it in sc["items"]:
            if it["place_id"] in secondary_ids:
                raise ValueError(f"Secondary place {it['place_id']} leaked into pool for {sid}")
            if not it.get("category"):
                raise ValueError(f"Missing category for place {it['place_id']} in {sid}")
            if it.get("i0_i1_stratum") not in ("I0", "I1"):
                raise ValueError(f"Invalid stratum {it.get('i0_i1_stratum')} in {sid}")

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
        print("\nNote: Scientific comparison and winner declaration are strictly gated until HUMAN-GT is collected.")
        sys.exit(0)

    # Future ground truth evaluation path
    print(f"Ground truth file specified: {args.gt_file}")
    print("Scientific evaluation with real HUMAN-GT is not permitted in W5-PREP-03.")
    sys.exit(1)


if __name__ == "__main__":
    main()
