"""Comprehensive tests for Frozen W5 Metric and Scientific Evaluation Runner.

Tests all requirements and specifications:
- MET-NDCG-01 .. MET-NDCG-05 (graded relevance, ideal ordering, IDCG=0, NA handling)
- MET-BIN-01 (binary threshold rel >= 1)
- MET-P-01 (Precision@10)
- MET-R-01, MET-R-02 (Pooled Recall@10, denominator=0 handling)
- MET-HR-01, MET-HR-02 (HitRate@10)
- MET-ILD-01 .. MET-ILD-03 (Category-ILD@10)
- MET-COV-01, MET-COV-02 (CatalogCoverage@10, destination macro vs pooled)
- MET-I1-01 .. MET-I1-03 (I1Exposure@10 diagnostic)
- MET-MACRO-01 (Destination macro vs unweighted scenario mean)
- MET-BOOT-01 .. MET-BOOT-06 (Paired destination-stratified bootstrap)
- MET-VERDICT-01 .. MET-VERDICT-04 (Pre-registered verdict rules)
- MET-NA-01 .. MET-NA-03 (NA evidence insufficiency, not_scorable, pool reporting)
- MET-SRC-01 .. MET-SRC-03 (W5-PREP-01, W5-PREP-02, Freeze V2 source immutability)
- MET-SYS-01 .. MET-SYS-03 (System identity, single shared baseline representation)
- MET-DUP-01, MET-DUP-02 (Duplicate policy status PENDING, duplicate map interface)
- MET-VAL-01 (Dry-run validation passes with zero human labels)
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple, Union

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.evaluate_w5_recommenders import (
    BOOTSTRAP_REPLICATES,
    EXPECTED_CATALOG_SIZES,
    EXPECTED_TOTAL_CORE,
    FREEZE_V2_ACCEPTED_SHA256,
    FROZEN_DESTINATIONS,
    INTERNAL_POOL_RELPATH,
    PRIMARY_SCENARIOS_RELPATH,
    SYSTEM_A2,
    SYSTEM_BASELINE,
    W5_METRIC_BOOTSTRAP_SEED,
    aggregate_destination_macro,
    aggregate_unweighted_mean,
    apply_duplicate_equivalence,
    calculate_gain,
    calculate_percentile,
    catalog_coverage_at_k,
    category_ild_at_k,
    classify_final_verdict,
    dcg_at_k,
    evaluate_scenario,
    hit_rate_at_k,
    i1_exposure_at_k,
    idcg_at_k,
    macro_destination_coverage,
    ndcg_at_k,
    paired_coverage_stratified_bootstrap,
    paired_destination_stratified_bootstrap,
    pooled_recall_at_k,
    precision_at_k,
    run_dry_run_validation,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

# Pinned Baseline Hashes
EXPECTED_W5_PREP_01_HASHES: Dict[str, Union[str, Set[str]]] = {
    "data/evaluation/reca_w5/w5_primary_scenarios_v1.json": "4f0c77dccc2c0bae32f5d87f1364a8e1487a83e9b7344a9d8d3c9d0528bc29fb",
    "data/evaluation/reca_w5/w5_thin_diagnostic_scenarios_v1.json": "538233a937acdd38ea208980a9ba629391b61e721363189f10f6087186fcfa77",
    "data/evaluation/reca_w5/w5_candidate_pool_internal_v1.json": "32b25ef8ffc19d671513f771d3d3a0d23ceb9d0cf614ace1eded94d8c84126c6",
    "data/evaluation/reca_w5/w5_candidate_pool_blinded_v1.json": "8f178e06b1b93e59b3a53f1b2bf1b6ecc697ccfa610d56783b613b6aa2f06ec7",
    "data/evaluation/reca_w5/w5_reproducibility_manifest_v1.json": {
        "ae2cbb97689148274723617e00a833093971c5f7cc11c7cdec39ec19619f6388",
        "d99f3187c3fa0535710ae7f3fc82c60d9f298ba399257e61b47562bdff48b51c",
    },
}

EXPECTED_W5_PREP_02_HASHES: Dict[str, Union[str, Set[str]]] = {
    "data/evaluation/reca_w5/annotation/w5_adjudication_template_v1.json": "9d811ef8f9c1ff6e248fedd4ae5f4b0d409937abab8ba80c68a9ab227604c775",
    "data/evaluation/reca_w5/annotation/w5_annotation_manifest_v1.json": {
        "9fa7e9e66f331e881cdb6cae0d29eecdfd77fe6cfa2108dad07a68c3fadde106",
        "e6f9839cc51b0cb282fa2ad7f644258dd1c03bd9914261ef6d60f0cfcf95f40d",
    },
    "data/evaluation/reca_w5/annotation/w5_annotation_template_v1.json": "9badb4f3c41c3b86ebe5246a7abd22d68ac57234a62aeb1525d8116566d482c5",
    "data/evaluation/reca_w5/annotation/w5_calibration_v1.json": "598bde75d464f3e58299522090833a8521a59d4c0755e13399ad46050a2ca823",
    "data/evaluation/reca_w5/annotation/w5_judge_J1_v1.json": "11a28f8f026ef5c70ed03d896c94270d9c8c3252bdc70e1bc838705425c61b5b",
    "data/evaluation/reca_w5/annotation/w5_judge_J2_v1.json": "63dafdf77e50d7c437996b738a750daf895a8d8192b7eeec6ca73ecc09728f3e",
    "data/evaluation/reca_w5/annotation/w5_judge_J3_v1.json": "9959326d1e306b9c52e3632cb67c4320df9e633881c14f02961bd6e9b2a19b8e",
    "data/evaluation/reca_w5/annotation/w5_judge_instructions_v1.md": "5d579d4c0b76a9c37eadac869db6e4f6abaa6c8c36f146d3176452d1fc56b4bb",
    "data/evaluation/reca_w5/annotation/w5_merged_ground_truth_template_v1.json": "3f33c6f866dec90f33212c5851a389ecc0b0f10d6e9da8ab8077aa8e305ab830",
    "data/evaluation/reca_w5/annotation/w5_metadata_sufficiency_v1.json": "c58f9a709cb338596536fae78ae444e9c8de9e070cf3b8449cbba64fe05fa989",
    "data/evaluation/reca_w5/annotation/w5_rubric_v1.md": "98601330b366ea99b2254509adf84762375460ab66a93ef3af2ef32df63ef8a4",
}


# ============================================================
# 1. NDCG TESTS (MET-NDCG-01 .. MET-NDCG-05)
# ============================================================


def test_met_ndcg_01_perfect_ideal_ranking() -> None:
    """MET-NDCG-01: Perfect ideal ranking produces NDCG = 1.0."""
    pool_rel = [2, 2, 1, 1, 0, 0, 0]
    ideal_ranked = [2, 2, 1, 1, 0]
    val, status = ndcg_at_k(ideal_ranked, pool_rel, k=5)
    assert status == "OK"
    assert val == 1.0


def test_met_ndcg_02_worse_ordering() -> None:
    """MET-NDCG-02: Worse ordering produces 0 < NDCG < 1.0."""
    pool_rel = [2, 2, 1, 1, 0, 0, 0]
    worse_ranked = [0, 0, 1, 1, 2]
    val, status = ndcg_at_k(worse_ranked, pool_rel, k=5)
    assert status == "OK"
    assert val is not None
    assert 0.0 < val < 1.0


def test_met_ndcg_03_all_relevance_zero() -> None:
    """MET-NDCG-03: All relevance zero -> NDCG = null, status = NO_RELEVANT_ITEM_IN_JUDGED_POOL."""
    pool_rel = [0, 0, 0, 0, 0]
    ranked = [0, 0, 0]
    val, status = ndcg_at_k(ranked, pool_rel, k=3)
    assert val is None
    assert status == "NO_RELEVANT_ITEM_IN_JUDGED_POOL"


def test_met_ndcg_04_graded_gains() -> None:
    """MET-NDCG-04: Label 2 has gain 3, label 1 has gain 1, label 0 has gain 0."""
    assert calculate_gain(0) == 0.0
    assert calculate_gain(1) == 1.0
    assert calculate_gain(2) == 3.0

    # Discount verification: log2(rank + 1)
    dcg = dcg_at_k([2, 1, 0], k=3)
    expected_dcg = (3.0 / math.log2(2)) + (1.0 / math.log2(3)) + (0.0 / math.log2(4))
    assert math.isclose(dcg, expected_dcg, rel_tol=1e-6)


def test_met_ndcg_05_na_never_converted_to_zero() -> None:
    """MET-NDCG-05: NA is never converted to 0."""
    pool_rel = [2, 1, 0, 0]
    ranked_with_na = [2, "NA", 1]
    val, status = ndcg_at_k(ranked_with_na, pool_rel, k=3)
    assert val is None
    assert status == "NOT_SCORABLE_UNRESOLVED_TOPK"

    ranked_with_none = [2, None, 1]
    val2, status2 = ndcg_at_k(ranked_with_none, pool_rel, k=3)
    assert val2 is None
    assert status2 == "NOT_SCORABLE_UNRESOLVED_TOPK"


# ============================================================
# 2. BINARY RELEVANCE TESTS (MET-BIN-01, MET-P-*, MET-R-*, MET-HR-*)
# ============================================================


def test_met_bin_01_binary_mapping() -> None:
    """MET-BIN-01: Labels [2, 1, 0] map to binary relevance [1, 1, 0] via rel >= 1."""
    labels = [2, 1, 0]
    binary = [1 if r >= 1 else 0 for r in labels]
    assert binary == [1, 1, 0]


def test_met_p_01_known_precision_fixture() -> None:
    """MET-P-01: Known Precision@10 fixture produces expected value."""
    # 6 relevant out of 10 returned items
    ranked = [1, 2, 0, 1, 0, 2, 0, 1, 0, 2]
    p_val, p_status = precision_at_k(ranked, k=10)
    assert p_status == "OK"
    assert p_val == 0.6


def test_met_r_01_known_pooled_recall_fixture() -> None:
    """MET-R-01: Known Pooled Recall@10 fixture produces expected value."""
    # 4 relevant in Top-10, 8 relevant in common judged pool
    ranked = [1, 2, 0, 0, 0, 1, 0, 0, 0, 2]  # 4 relevant
    pool = [2, 2, 2, 1, 1, 1, 1, 1, 0, 0, 0, 0]  # 8 relevant
    r_val, r_status = pooled_recall_at_k(ranked, pool, k=10)
    assert r_status == "OK"
    assert r_val == 0.5


def test_met_r_02_pooled_recall_denominator_zero() -> None:
    """MET-R-02: Denominator zero in pooled recall returns null (NO_RELEVANT_ITEM_IN_JUDGED_POOL)."""
    ranked = [0, 0, 0]
    pool = [0, 0, 0, 0]
    r_val, r_status = pooled_recall_at_k(ranked, pool, k=3)
    assert r_val is None
    assert r_status == "NO_RELEVANT_ITEM_IN_JUDGED_POOL"


def test_met_hr_01_hit_rate_one() -> None:
    """MET-HR-01: At least one relevant item in Top-k -> HitRate = 1.0."""
    ranked = [0, 0, 1, 0, 0]
    hr_val, hr_status = hit_rate_at_k(ranked, k=5)
    assert hr_status == "OK"
    assert hr_val == 1.0


def test_met_hr_02_hit_rate_zero() -> None:
    """MET-HR-02: Zero relevant items in Top-k -> HitRate = 0.0."""
    ranked = [0, 0, 0, 0, 0]
    hr_val, hr_status = hit_rate_at_k(ranked, k=5)
    assert hr_status == "OK"
    assert hr_val == 0.0


# ============================================================
# 3. DIVERSITY & COVERAGE TESTS (MET-ILD-*, MET-COV-*)
# ============================================================


def test_met_ild_01_all_categories_same() -> None:
    """MET-ILD-01: All categories same -> ILD = 0.0."""
    categories = ["restaurant"] * 10
    ild = category_ild_at_k(categories, k=10)
    assert ild == 0.0


def test_met_ild_02_all_categories_pairwise_different() -> None:
    """MET-ILD-02: All categories pairwise different -> ILD = 1.0."""
    categories = [f"cat_{i}" for i in range(10)]
    ild = category_ild_at_k(categories, k=10)
    assert ild == 1.0


def test_met_ild_03_mixed_category_fixture() -> None:
    """MET-ILD-03: Known mixed category fixture returns exact expected value."""
    # 4 items: A, A, B, B
    # Pairs: (A,A)=0, (A,B)=1, (A,B)=1, (A,B)=1, (A,B)=1, (B,B)=0 -> 4 diffs out of 6 pairs
    categories = ["A", "A", "B", "B"]
    ild = category_ild_at_k(categories, k=4)
    expected = 4.0 / 6.0
    assert math.isclose(ild, round(expected, 6), rel_tol=1e-6)


def test_met_cov_01_destination_coverage_ratio() -> None:
    """MET-COV-01: Known destination coverage fixture returns correct ratio."""
    # 29 unique places out of 145 Hanoi catalog
    cov = catalog_coverage_at_k(29, 145)
    assert cov == 0.2


def test_met_cov_02_equal_city_weighting() -> None:
    """MET-COV-02: Destination macro uses equal city weighting, not catalog-size weighting."""
    cov_hn = 0.20  # e.g. 29 / 145
    cov_dn = 0.10  # e.g. 28.9 / 289
    cov_hl = 0.30  # e.g. 56.4 / 188

    macro_cov = macro_destination_coverage(cov_hn, cov_dn, cov_hl)
    expected_macro = (0.20 + 0.10 + 0.30) / 3.0  # 0.20

    # Catalog-size weighted average:
    # (29 + 28.9 + 56.4) / (145 + 289 + 188) = 114.3 / 622 = 0.18376
    catalog_weighted = (29.0 + 28.9 + 56.4) / (145 + 289 + 188)

    assert math.isclose(macro_cov, expected_macro, rel_tol=1e-6)
    assert not math.isclose(macro_cov, catalog_weighted, rel_tol=1e-3)


# ============================================================
# 4. DIAGNOSTIC I1 TESTS (MET-I1-01 .. MET-I1-03)
# ============================================================


def test_met_i1_01_zero_i1_exposure() -> None:
    """MET-I1-01: 0 I1 in Top-10 -> 0.0."""
    strata = ["I0"] * 10
    assert i1_exposure_at_k(strata, k=10) == 0.0


def test_met_i1_02_half_i1_exposure() -> None:
    """MET-I1-02: 5 I1 in Top-10 -> 0.5."""
    strata = ["I1"] * 5 + ["I0"] * 5
    assert i1_exposure_at_k(strata, k=10) == 0.5


def test_met_i1_03_diagnostic_only_not_in_verdict() -> None:
    """MET-I1-03: I1Exposure is labeled diagnostic and does not enter verdict."""
    # classify_final_verdict signature does not include I1 exposure
    # High or low I1 exposure cannot flip verdict
    verdict = classify_final_verdict(
        ndcg_ci=(0.02, 0.08),
        ild_ci=(0.01, 0.05),
        cov_ci=(0.01, 0.05),
        ild_point_delta=0.03,
        cov_point_delta=0.03,
    )
    assert verdict == "A2_RELEVANCE_SUPERIOR"


# ============================================================
# 5. MACRO AGGREGATION TESTS (MET-MACRO-01)
# ============================================================


def test_met_macro_01_distinct_from_unweighted_mean() -> None:
    """MET-MACRO-01: Destination macro is mathematically distinct from simple pooled average."""
    # 9 HN scenarios (mean=1.0), 11 DN scenarios (mean=0.0), 10 HL scenarios (mean=0.5)
    hn_means = [1.0] * 9
    dn_means = [0.0] * 11
    hl_means = [0.5] * 10

    dest_means = {
        "ha-noi": sum(hn_means) / len(hn_means),  # 1.0
        "da-nang": sum(dn_means) / len(dn_means),  # 0.0
        "ha-long": sum(hl_means) / len(hl_means),  # 0.5
    }

    macro_avg = aggregate_destination_macro(dest_means)
    assert macro_avg == 0.5  # (1.0 + 0.0 + 0.5) / 3 = 0.5

    all_scenarios = hn_means + dn_means + hl_means  # 30 items
    pooled_avg = aggregate_unweighted_mean(all_scenarios)
    # (9*1.0 + 11*0.0 + 10*0.5) / 30 = 14.0 / 30 = 0.466667
    assert pooled_avg == 0.466667
    assert macro_avg != pooled_avg


# ============================================================
# 6. BOOTSTRAP TESTS (MET-BOOT-01 .. MET-BOOT-06)
# ============================================================


def test_met_boot_01_deterministic_reproducibility() -> None:
    """MET-BOOT-01: Same seed + same data -> identical CI."""
    data = {
        "ha-noi": [(0.5, 0.6), (0.7, 0.8), (0.4, 0.4)],
        "da-nang": [(0.3, 0.5), (0.6, 0.7), (0.8, 0.9)],
        "ha-long": [(0.5, 0.5), (0.6, 0.8), (0.7, 0.7)],
    }
    res1 = paired_destination_stratified_bootstrap(data, seed=W5_METRIC_BOOTSTRAP_SEED, replicates=1000)
    res2 = paired_destination_stratified_bootstrap(data, seed=W5_METRIC_BOOTSTRAP_SEED, replicates=1000)
    assert res1["mean_delta"] == res2["mean_delta"]
    assert res1["ci_95"] == res2["ci_95"]


def test_met_boot_02_paired_preservation() -> None:
    """MET-BOOT-02: Paired system observations remain paired."""
    # If delta for every pair is strictly 0.10, resampled delta must always be 0.10
    data = {
        "ha-noi": [(0.1, 0.2), (0.5, 0.6)],
        "da-nang": [(0.2, 0.3), (0.7, 0.8)],
        "ha-long": [(0.4, 0.5), (0.8, 0.9)],
    }
    res = paired_destination_stratified_bootstrap(data, seed=W5_METRIC_BOOTSTRAP_SEED, replicates=500)
    assert math.isclose(res["mean_delta"], 0.10, rel_tol=1e-5)
    assert math.isclose(res["ci_95"][0], 0.10, rel_tol=1e-5)
    assert math.isclose(res["ci_95"][1], 0.10, rel_tol=1e-5)


def test_met_boot_03_and_04_destination_stratified_resampling() -> None:
    """MET-BOOT-03 & 04: Scenario-level resampling is stratified within destinations."""
    # Destination A has strictly delta +0.3, Dest B has strictly delta 0.0, Dest C has strictly delta 0.0
    data = {
        "ha-noi": [(0.1, 0.4), (0.2, 0.5)],  # all +0.3
        "da-nang": [(0.5, 0.5), (0.6, 0.6)],  # all 0.0
        "ha-long": [(0.7, 0.7), (0.8, 0.8)],  # all 0.0
    }
    res = paired_destination_stratified_bootstrap(data, seed=W5_METRIC_BOOTSTRAP_SEED, replicates=500)
    # Stratified macro mean must always be (0.3 + 0.0 + 0.0) / 3 = 0.10
    assert math.isclose(res["mean_delta"], 0.10, rel_tol=1e-5)
    assert math.isclose(res["ci_95"][0], 0.10, rel_tol=1e-5)
    assert math.isclose(res["ci_95"][1], 0.10, rel_tol=1e-5)


def test_met_boot_05_clear_positive_delta() -> None:
    """MET-BOOT-05: Clear positive synthetic delta -> CI > 0."""
    data = {
        "ha-noi": [(0.4, 0.7), (0.5, 0.8), (0.3, 0.6)],
        "da-nang": [(0.5, 0.7), (0.6, 0.8), (0.4, 0.7)],
        "ha-long": [(0.4, 0.6), (0.5, 0.8), (0.3, 0.6)],
    }
    res = paired_destination_stratified_bootstrap(data, seed=W5_METRIC_BOOTSTRAP_SEED, replicates=1000)
    assert res["ci_95"][0] > 0.0
    assert res["ci_95"][1] > 0.0


def test_met_boot_06_clear_negative_delta() -> None:
    """MET-BOOT-06: Clear negative synthetic delta -> CI < 0."""
    data = {
        "ha-noi": [(0.7, 0.4), (0.8, 0.5), (0.6, 0.3)],
        "da-nang": [(0.7, 0.5), (0.8, 0.6), (0.7, 0.4)],
        "ha-long": [(0.6, 0.4), (0.8, 0.5), (0.6, 0.3)],
    }
    res = paired_destination_stratified_bootstrap(data, seed=W5_METRIC_BOOTSTRAP_SEED, replicates=1000)
    assert res["ci_95"][0] < 0.0
    assert res["ci_95"][1] < 0.0


# ============================================================
# 7. PRE-REGISTERED VERDICT TESTS (MET-VERDICT-01 .. MET-VERDICT-04)
# ============================================================


def test_met_verdict_01_a2_relevance_superior() -> None:
    """MET-VERDICT-01: NDCG CI entirely positive -> A2_RELEVANCE_SUPERIOR."""
    verdict = classify_final_verdict(
        ndcg_ci=(0.012, 0.065),
        ild_ci=(-0.01, 0.03),
        cov_ci=(-0.02, 0.02),
        ild_point_delta=0.01,
        cov_point_delta=0.0,
    )
    assert verdict == "A2_RELEVANCE_SUPERIOR"


def test_met_verdict_02_baseline_preferred() -> None:
    """MET-VERDICT-02: NDCG CI entirely negative -> BASELINE_PREFERRED."""
    verdict = classify_final_verdict(
        ndcg_ci=(-0.075, -0.015),
        ild_ci=(0.02, 0.08),
        cov_ci=(0.01, 0.05),
        ild_point_delta=0.05,
        cov_point_delta=0.03,
    )
    assert verdict == "BASELINE_PREFERRED"


def test_met_verdict_03_a2_diversity_tradeoff() -> None:
    """MET-VERDICT-03: NDCG CI includes zero, diversity positive -> A2_DIVERSITY_TRADEOFF."""
    # Case 1: ILD CI lower > 0 and cov_point_delta >= 0
    verdict1 = classify_final_verdict(
        ndcg_ci=(-0.02, 0.03),
        ild_ci=(0.015, 0.075),
        cov_ci=(-0.01, 0.04),
        ild_point_delta=0.045,
        cov_point_delta=0.015,
    )
    assert verdict1 == "A2_DIVERSITY_TRADEOFF"

    # Case 2: Cov CI lower > 0 and ild_point_delta >= 0
    verdict2 = classify_final_verdict(
        ndcg_ci=(-0.01, 0.02),
        ild_ci=(-0.01, 0.04),
        cov_ci=(0.010, 0.050),
        ild_point_delta=0.015,
        cov_point_delta=0.030,
    )
    assert verdict2 == "A2_DIVERSITY_TRADEOFF"


def test_met_verdict_04_inconclusive() -> None:
    """MET-VERDICT-04: Insufficient evidence -> INCONCLUSIVE."""
    # NDCG CI includes 0, neither diversity metric lower bound > 0
    verdict = classify_final_verdict(
        ndcg_ci=(-0.03, 0.04),
        ild_ci=(-0.02, 0.05),
        cov_ci=(-0.03, 0.02),
        ild_point_delta=0.015,
        cov_point_delta=-0.005,
    )
    assert verdict == "INCONCLUSIVE"


# ============================================================
# 8. NA / UNRESOLVED POLICY TESTS (MET-NA-01 .. MET-NA-03)
# ============================================================


def test_met_na_01_na_is_not_zero() -> None:
    """MET-NA-01: NA is never converted to 0."""
    with pytest.raises(ValueError):
        calculate_gain("NA")  # type: ignore


def test_met_na_02_unresolved_top10_marks_not_scorable() -> None:
    """MET-NA-02: Any unresolved Top10 candidate -> scenario relevance NOT_SCORABLE_UNRESOLVED_TOPK."""
    scenario_info = {
        "scenario_id": "HN-U1-01",
        "destination": "ha-noi",
        "user_stratum": "U1",
    }
    ranked_places = [
        {"place_id": f"p_{i}", "category": "restaurant", "i0_i1_stratum": "I0"}
        for i in range(10)
    ]
    pool_items = [
        {"place_id": f"p_{i}"} for i in range(15)
    ]
    # place p_3 is unresolved NA
    gt_map: Dict[str, Any] = {f"p_{i}": 1 for i in range(15)}
    gt_map["p_3"] = "NA"

    res = evaluate_scenario(scenario_info, ranked_places, pool_items, gt_map)
    assert res["metric_status"] == "NOT_SCORABLE_UNRESOLVED_TOPK"
    assert res["ndcg_at_10"] is None
    assert res["precision_at_10"] is None
    assert res["pooled_recall_at_10"] is None
    assert res["hit_rate_at_10"] is None
    # Category ILD and I1 exposure are catalog-based and remain scorable
    assert res["category_ild_at_10"] is not None
    assert res["i1_exposure_at_10"] is not None


def test_met_na_03_unresolved_pool_count_always_reported() -> None:
    """MET-NA-03: Unresolved pool count always reported in scenario output."""
    scenario_info = {
        "scenario_id": "HN-U1-01",
        "destination": "ha-noi",
        "user_stratum": "U1",
    }
    ranked_places = [
        {"place_id": f"p_{i}", "category": "restaurant", "i0_i1_stratum": "I0"}
        for i in range(10)
    ]
    pool_items = [
        {"place_id": f"p_{i}"} for i in range(15)
    ]
    gt_map: Dict[str, Any] = {f"p_{i}": 1 for i in range(12)}
    gt_map["p_12"] = "NA"
    gt_map["p_13"] = None
    gt_map["p_14"] = "NA"

    res = evaluate_scenario(scenario_info, ranked_places, pool_items, gt_map)
    assert res["judged_pool_count"] == 12
    assert res["unresolved_pool_count"] == 3


# ============================================================
# 9. SOURCE IMMUTABILITY TESTS (MET-SRC-01 .. MET-SRC-03)
# ============================================================


def test_met_src_01_w5_prep_01_hashes_unchanged() -> None:
    """MET-SRC-01: W5-PREP-01 source hashes remain strictly byte-identical."""
    for rel_path, expected_hash in EXPECTED_W5_PREP_01_HASHES.items():
        abs_path = REPO_ROOT / rel_path
        assert abs_path.exists(), f"Missing W5-PREP-01 artifact: {rel_path}"
        current_hash = hashlib.sha256(abs_path.read_bytes()).hexdigest()
        if isinstance(expected_hash, set):
            assert current_hash in expected_hash, (
                f"W5-PREP-01 source artifact drift for {rel_path}: got {current_hash}, expected one of {expected_hash}"
            )
        else:
            assert current_hash == expected_hash, (
                f"W5-PREP-01 source artifact drift for {rel_path}: got {current_hash}, expected {expected_hash}"
            )


def test_met_src_02_w5_prep_02_annotation_hashes_unchanged() -> None:
    """MET-SRC-02: W5-PREP-02 annotation source hashes remain strictly byte-identical."""
    for rel_path, expected_hash in EXPECTED_W5_PREP_02_HASHES.items():
        abs_path = REPO_ROOT / rel_path
        assert abs_path.exists(), f"Missing W5-PREP-02 artifact: {rel_path}"
        current_hash = hashlib.sha256(abs_path.read_bytes()).hexdigest()
        if isinstance(expected_hash, set):
            assert current_hash in expected_hash, (
                f"W5-PREP-02 annotation artifact drift for {rel_path}: got {current_hash}, expected one of {expected_hash}"
            )
        else:
            assert current_hash == expected_hash, (
                f"W5-PREP-02 annotation artifact drift for {rel_path}: got {current_hash}, expected {expected_hash}"
            )


def test_met_src_03_freeze_v2_unchanged() -> None:
    """MET-SRC-03: Freeze V2 catalog matches accepted checksums."""
    freeze_path = REPO_ROOT / "data" / "curated" / "gomate_places_freeze_v2.json"
    assert freeze_path.exists()
    current_hash = hashlib.sha256(freeze_path.read_bytes()).hexdigest()
    assert current_hash in FREEZE_V2_ACCEPTED_SHA256, (
        f"Freeze V2 checksum mismatch: got {current_hash}, expected one of {FREEZE_V2_ACCEPTED_SHA256}"
    )


# ============================================================
# 10. SYSTEM IDENTITY TESTS (MET-SYS-01 .. MET-SYS-03)
# ============================================================


def test_met_sys_01_shared_baseline_represented_once() -> None:
    """MET-SYS-01: Shared A0/A1 baseline represented once."""
    assert SYSTEM_BASELINE == "shared_a0_a1_baseline"


def test_met_sys_02_a2_represented_once() -> None:
    """MET-SYS-02: A2 represented once."""
    assert SYSTEM_A2 == "rec-a2"


def test_met_sys_03_no_direct_a0_vs_a1_comparison() -> None:
    """MET-SYS-03: No direct scientific A0-vs-A1 comparison generated."""
    res = run_dry_run_validation()
    assert res["evaluated_systems"] == [SYSTEM_BASELINE, SYSTEM_A2]
    assert "rec-a0" not in res["evaluated_systems"]
    assert "rec-a1" not in res["evaluated_systems"]


# ============================================================
# 11. DUPLICATE POLICY TESTS (MET-DUP-01, MET-DUP-02)
# ============================================================


def test_met_dup_01_duplicate_policy_pending() -> None:
    """MET-DUP-01: duplicate_policy_status is PENDING, final_scientific_ready is False."""
    res = run_dry_run_validation()
    assert res["duplicate_policy_status"] == "PENDING"
    assert res["final_scientific_evaluation_ready"] is False


def test_met_dup_02_duplicate_map_interface_hook() -> None:
    """MET-DUP-02: Runner accepts optional duplicate map interface without hardcoded data."""
    place_ids = ["pid_1", "pid_2", "pid_3"]
    # Without map -> unchanged
    assert apply_duplicate_equivalence(place_ids, None) == place_ids

    # With synthetic map -> equivalence groups applied
    dup_map = {"pid_1": "group_A", "pid_2": "group_A"}
    mapped = apply_duplicate_equivalence(place_ids, dup_map)
    assert mapped == ["group_A", "group_A", "pid_3"]


# ============================================================
# 12. DRY-RUN VALIDATION TEST (MET-VAL-01)
# ============================================================


def test_met_val_01_dry_run_validation_passes() -> None:
    """MET-VAL-01: Dry-run validation executes cleanly with zero human labels and no winner."""
    res = run_dry_run_validation()
    assert res["status"] == "VALIDATION_PASSED"
    assert res["total_core_places"] == EXPECTED_TOTAL_CORE
    assert res["destination_counts"] == EXPECTED_CATALOG_SIZES
    assert res["secondary_leakage"] == 0
    assert res["primary_scenarios"] == 30
    assert res["u1_scenarios"] == 15
    assert res["u2_scenarios"] == 15
    assert res["thin_scenarios"] == 6
    assert res["candidate_pool_records"] == 474
    assert res["human_judgments_collected"] == 0
    assert res["human_gt_available"] is False
    assert res["scientific_winner"] == "UNKNOWN"
