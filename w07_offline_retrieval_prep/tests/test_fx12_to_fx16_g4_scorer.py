"""FX-12 to FX-16 & D06.3 tests for decoupled w07_g4_scorer (plus gated real-corpus stub)."""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

import w07_g4_scorer
from fixtures.g4_fixtures import (
    build_fx15_smoke_bundle,
    make_query_dict,
    make_query_spec,
    make_ranking_row,
    write_jsonl,
    write_sealed_rankings_bundle,
)
from w07_g4_scorer.contracts import (
    Cert4Status,
    QrelRecord,
    RelevanceState,
    assert_g4_package_zero_ml_imports,
    assert_zero_ml_imports,
    compute_query_certificates,
    load_external_qrels,
    load_sealed_rankings,
)
from w07_g4_scorer.judge_gates import seal_expected_pairs_manifest
from w07_g4_scorer.metrics import (
    compute_span_hits_at_10,
    compute_unanswerable_metrics,
    conservative_ndcg10_enclosure,
    coupled_ndcg10_bounds,
    coupled_pairwise_contrast_bounds,
    exact_ndcg10_bounds,
    span_hit_matches,
)
from w07_g4_scorer.scorer import score_g4, score_g4_from_files
from w07_g4_scorer.stats import STAT_SEED, evaluate_winner_gate, holm_bonferroni, paired_bootstrap_and_sign_flip


def _collect_all_keys(obj: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.add(str(k))
            keys.update(_collect_all_keys(v))
    elif isinstance(obj, list):
        for item in obj:
            keys.update(_collect_all_keys(item))
    return keys


# ============================================================================
# FX-12: Fixed Q_ans, G15-F01 Coupled Contrasts, CE-01, Cert-1..4, & Strict Ontology
# ============================================================================
def test_fx12_g15_f01_coupled_bounds_and_ce01_reversal() -> None:
    # Exact G15-F01 analytical counterexample
    dcg_a = {"q1": 4.5, "q2": 0.0, "q3": 0.0}
    dcg_b = {"q1": 3.6, "q2": 3.0, "q3": 3.0}
    idcg_l = {"q1": 4.5, "q2": 3.0, "q3": 3.0}
    idcg_u = {"q1": 4.5, "q2": 6.0, "q3": 6.0}

    a_lower = sum(dcg_a[q] / idcg_u[q] for q in dcg_a) / 3.0
    a_upper = sum(dcg_a[q] / idcg_l[q] for q in dcg_a) / 3.0
    b_lower = sum(dcg_b[q] / idcg_u[q] for q in dcg_b) / 3.0
    b_upper = sum(dcg_b[q] / idcg_l[q] for q in dcg_b) / 3.0
    assert round(a_lower, 4) == 0.3333 and round(a_upper, 4) == 0.3333
    assert round(b_lower, 4) == 0.6000 and round(b_upper, 4) == 0.9333

    contrast = coupled_pairwise_contrast_bounds(dcg_a, dcg_b, idcg_l, idcg_u)
    assert round(contrast["delta_min"], 4) == -0.6000
    assert round(contrast["delta_max"], 4) == -0.2667
    # Biased exact-only slice on q1 would falsely show +0.2000; coupled full-Q_ans proves A < B
    assert contrast["delta_max"] < 0.0

    # Grok C CE-01 pooled-denominator reversal check:
    # q1 has judged doc 'a'(rel=1, gain=1), 'd0'(rel=0, gain=0), and corpus doc 'b'(rel=2, gain=3) unjudged in pool.
    # q2 has single doc 'c'(rel=1, gain=1).
    qrels_q1 = {
        "a": QrelRecord("q1", "a", RelevanceState.REL_1, 0, (), None),
        "d0": QrelRecord("q1", "d0", RelevanceState.REL_0, 0, (), None),
    }
    qrels_q2 = {"c": QrelRecord("q2", "c", RelevanceState.REL_1, 0, (), None)}
    # Under true corpus-aware bounds, q1 has IDCG_L=1.0, IDCG_U=3.0+1.0/log2(3)
    res_x_q1 = coupled_ndcg10_bounds(["a", "d0"], ["a", "d0", "b"], qrels_q1, strict_cert2=True)
    res_y_q1 = coupled_ndcg10_bounds(["d0", "a"], ["a", "d0", "b"], qrels_q1, strict_cert2=True)
    assert res_x_q1["ndcg_l"] < 0.30
    assert res_x_q1["ndcg_u"] == 1.0
    assert res_y_q1["ndcg_l"] < res_x_q1["ndcg_l"]
    assert res_y_q1["ndcg_u"] < 0.65
    res_q2 = coupled_ndcg10_bounds(["c"], ["c"], qrels_q2, strict_cert2=True)
    assert res_q2["ndcg_l"] == 1.0 and res_q2["ndcg_u"] == 1.0

    # exact_ndcg10_bounds deduplicates duplicate doc IDs in all_doc_ids
    ex_dup = exact_ndcg10_bounds(["d1"], ["d1", "d1", "d2"], {"d1": 3, "d2": 0})
    assert abs(ex_dup["lower"] - 1.0) < 1e-12 and abs(ex_dup["upper"] - 1.0) < 1e-12

    # coupled_ndcg10_bounds unites top10 into doc_universe so ndcg_u <= 1.0
    qrels_extra = {
        "d1": QrelRecord("q_ex", "d1", RelevanceState.REL_2, 0, (), None),
        "d2": QrelRecord("q_ex", "d2", RelevanceState.REL_1, 0, (), None),
    }
    res_extra = coupled_ndcg10_bounds(["d1"], ["d2"], qrels_extra, strict_cert2=True)
    expected_extra = 3.0 / (3.0 + 1.0 / math.log2(3.0))
    assert res_extra["ndcg_u"] <= 1.0 + 1e-12
    assert abs(res_extra["ndcg_l"] - expected_extra) < 1e-12
    assert abs(res_extra["ndcg_u"] - expected_extra) < 1e-12


def test_fx12_end_to_end_retains_bounded_not_exact_and_rejects_na_coercion(tmp_path: Path) -> None:
    # 4 queries: q1 EXACT_CERTIFIED, q2/q3 BOUNDED_NOT_EXACT (retained!), q4 ZERO_POSITIVE_EXACT (excluded!)
    queries = [
        make_query_dict(query_id="q1", target_city="Hà Nội", target_poi_ids=["poi-hn-01"]),
        make_query_dict(query_id="q2", target_city="Hà Nội", target_poi_ids=["poi-hn-02"]),
        make_query_dict(query_id="q3", target_city="Đà Nẵng", target_poi_ids=["poi-dn-01"]),
        make_query_dict(query_id="q4", target_city="Hạ Long", target_poi_ids=["poi-hl-01"]),
    ]
    queries_path = write_jsonl(tmp_path / "queries.jsonl", queries)

    # Corpus of 12 docs: d1..d10 positive for q1; d11, d12 extra
    rows = []
    # C1-RRF shines on q1 only, fails on q2/q3; C1-BM25 consistent on q2/q3
    for qid in ("q1", "q2", "q3", "q4"):
        if qid == "q1":
            rows.append(make_ranking_row(cell_id="C1-RRF", query_id=qid, rank=1, document_id="d1", score=1.0))
            rows.append(make_ranking_row(cell_id="C1-BM25", query_id=qid, rank=1, document_id="d11", score=1.0))
        elif qid in ("q2", "q3"):
            rows.append(make_ranking_row(cell_id="C1-RRF", query_id=qid, rank=1, document_id="d11", score=1.0))
            rows.append(make_ranking_row(cell_id="C1-BM25", query_id=qid, rank=1, document_id="d1", score=1.0))
        else:
            rows.append(make_ranking_row(cell_id="C1-RRF", query_id=qid, rank=1, document_id="d11", score=1.0))
            rows.append(make_ranking_row(cell_id="C1-BM25", query_id=qid, rank=1, document_id="d11", score=1.0))

    rankings_path, manifest_path = write_sealed_rankings_bundle(tmp_path, rows, cells=["C1-RRF", "C1-BM25"])

    qrels_rows = []
    # q1: d1..d10 all REL_2 -> saturated IDCG_L = IDCG_U -> EXACT_CERTIFIED; d11 REL_1
    for i in range(1, 11):
        qrels_rows.append({"query_id": "q1", "document_id": f"d{i}", "label": "REL_2", "plausible_unsupported_lure": 0, "evidence_s_spans": [[0, 10]]})
    qrels_rows.append({"query_id": "q1", "document_id": "d11", "label": "REL_1", "plausible_unsupported_lure": 0, "evidence_s_spans": [[0, 10]]})
    qrels_rows.append({"query_id": "q1", "document_id": "d12", "label": "REL_0", "plausible_unsupported_lure": 0, "evidence_s_spans": []})

    # q2, q3: d1=REL_2, d11=REL_0, d12 omitted (UNJUDGED outside top-10) -> BOUNDED_NOT_EXACT
    for qid in ("q2", "q3"):
        qrels_rows.append({"query_id": qid, "document_id": "d1", "label": "REL_2", "plausible_unsupported_lure": 0, "evidence_s_spans": [[0, 10]]})
        qrels_rows.append({"query_id": qid, "document_id": "d11", "label": "REL_0", "plausible_unsupported_lure": 0, "evidence_s_spans": []})

    # q4: all 12 docs judged REL_0 -> ZERO_POSITIVE_EXACT -> excluded to audit ledger
    for i in range(1, 13):
        qrels_rows.append({"query_id": "q4", "document_id": f"d{i}", "label": "REL_0", "plausible_unsupported_lure": 0, "evidence_s_spans": []})

    qrels_path = write_jsonl(tmp_path / "qrels.jsonl", qrels_rows)
    report = score_g4_from_files(
        rankings_path=rankings_path,
        manifest_path=manifest_path,
        queries_path=queries_path,
        qrels_path=qrels_path,
    )
    assert report["q_ans_count"] == 3
    assert report["q_zero_exact_count"] == 1
    assert report["headline_status"] == "NO_EXACT_FULL_SET_ESTIMATE"
    assert report["certificates"]["zero_idcg_audit_ledger"][0]["query_id"] == "q4"

    # P2-03 check: C1-RRF got DCG=0 on q2/q3 so nDCG_L == nDCG_U contribution from q2/q3 is 0.0,
    # yet q2/q3 remain BOUNDED_NOT_EXACT in Q_ans!
    assert report["cell_metrics"]["C1-RRF"]["ndcg10_lower"] == report["cell_metrics"]["C1-RRF"]["ndcg10_upper"]
    assert report["contrasts_k1_to_k5"]["K1"]["delta_max"] < 0.0

    # Reject invalid qrel coercions (None, int 0, missing lure on REL_0, lure=1 on REL_2, fillna)
    bad_qrel_cases = [
        {"query_id": "q1", "document_id": "d1", "label": None},
        {"query_id": "q1", "document_id": "d1", "label": 0, "plausible_unsupported_lure": 0},
        {"query_id": "q1", "document_id": "d1", "label": "REL_0"},  # missing lure
        {"query_id": "q1", "document_id": "d1", "label": "REL_2", "plausible_unsupported_lure": 1},
        {"query_id": "q1", "document_id": "d1", "label": "REL_0", "plausible_unsupported_lure": 0, "row_index_fallback": True},
    ]
    for idx, bad in enumerate(bad_qrel_cases):
        bad_path = write_jsonl(tmp_path / f"bad_qrels_{idx}.jsonl", [bad])
        with pytest.raises(ValueError):
            load_external_qrels(bad_path)

    # Reject NA -> 0 and UNJUDGED -> 0 in Cert-2 / INVALID_UNRESOLVED blocker
    na_qrels = write_jsonl(
        tmp_path / "na_qrels.jsonl",
        [{"query_id": "q1", "document_id": "d1", "label": "NA", "evidence_s_spans": []}],
    )
    loaded_na = load_external_qrels(na_qrels)
    assert loaded_na[("q1", "d1")].label == RelevanceState.NA
    cert_na = compute_query_certificates("q1", {"C1-RRF": ["d1"]}, ["d1", "d2"], loaded_na)
    assert cert_na.cert4_status == Cert4Status.INVALID_UNRESOLVED


# ============================================================================
# FX-13: Rank-10 UNJUDGED Conservative Enclosure vs Exact Sharp Bounds
# ============================================================================
def test_fx13_rank10_unjudged_conservative_enclosure_and_exact_bounds() -> None:
    all_docs = [f"d{i}" for i in range(1, 138)]  # 137 docs
    top10 = [f"d{i}" for i in range(1, 11)]
    known_gains: dict[str, int] = {"d1": 3}
    for i in range(2, 10):
        known_gains[f"d{i}"] = 0
    # d10 is UNJUDGED; remaining 127 docs d11..d137 are rel=0
    for i in range(11, 138):
        known_gains[f"d{i}"] = 0

    cons = conservative_ndcg10_enclosure(top10, all_docs, known_gains)
    exact = exact_ndcg10_bounds(top10, all_docs, known_gains)

    expected_d_u = 3.0 + 3.0 / math.log2(11.0)
    expected_i_u = 3.0 + 3.0 / math.log2(3.0)
    expected_exact_low = expected_d_u / expected_i_u  # ~0.790386

    assert abs(cons["lower"] - (3.0 / expected_i_u)) < 1e-12
    assert cons["upper"] == 1.0
    assert abs(exact["lower"] - expected_exact_low) < 1e-9
    assert abs(exact["upper"] - 1.0) < 1e-12
    # Conservative enclosure must enclose exact bounds (rejecting decoupled 1.0 > 0.790386)
    assert cons["lower"] <= exact["lower"] <= exact["upper"] <= cons["upper"]


# ============================================================================
# D06.3: EvidenceSpanHit@10 vs VisibleEvidenceSpanHit@10, AND/OR, G_sub, >=80%
# ============================================================================
def test_d063_span_hits_facets_r_audit_straddle_and_gt128_split() -> None:
    # 1. Standard AND/OR facets where C_full hits both groups, but C_vis truncates group 2
    q_facet = make_query_spec(
        query_id="q_s3",
        query_family="S3_MULTI_EVIDENCE",
        required_evidence_facets=[
            {"or": [{"document_id": "d1", "s_spans": [[0, 15]]}]},
            {"or": [{"document_id": "d2", "s_spans": [[50, 70]]}, {"document_id": "d3", "s_spans": [[0, 10]]}]},
        ],
    )
    rows = [
        make_ranking_row(cell_id="C1-RRF", query_id="q_s3", rank=1, document_id="d1", c_full_s_spans=[[0, 20]], c_vis_s_spans=[[0, 20]]),
        make_ranking_row(cell_id="C1-RRF", query_id="q_s3", rank=2, document_id="d2", c_full_s_spans=[[0, 80]], c_vis_s_spans=[[0, 40]]),
    ]
    hits = compute_span_hits_at_10(rows, q_facet, {})
    assert hits["evidence_span_hit_at_10"] == 1.0
    assert hits["visible_evidence_span_hit_at_10"] == 0.0

    # 2. Straddling deleted R_AUDIT tag [20, 35) inside target [10, 45) -> passes via G_sub when non-tag intervals covered
    q_straddle = make_query_spec(
        query_id="q_str",
        required_evidence_facets=[[{"document_id": "d_str", "s_spans": [[10, 45]]}]],
    )
    row_str = [
        make_ranking_row(
            cell_id="C1-RRF",
            query_id="q_str",
            rank=1,
            document_id="d_str",
            c_full_s_spans=[[10, 20], [35, 45]],
            c_vis_s_spans=[[10, 20], [35, 45]],
        )
    ]
    hits_str = compute_span_hits_at_10(row_str, q_straddle, {}, removed_audit_spans_by_doc={"d_str": [(20, 35)]})
    assert hits_str["evidence_span_hit_at_10"] == 1.0
    assert hits_str["visible_evidence_span_hit_at_10"] == 1.0

    # 2b. CE-08 outer-hull rejection: row span overlapping deleted R_AUDIT MUST return False / 0.0
    assert span_hit_matches([(10, 45)], [(10, 45)], [(20, 35)]) is False
    row_outer_hull = [
        make_ranking_row(
            cell_id="C1-RRF",
            query_id="q_str",
            rank=1,
            document_id="d_str",
            c_full_s_spans=[[10, 20], [35, 45]],
            c_vis_s_spans=[[10, 45]],
        )
    ]
    hits_hull = compute_span_hits_at_10(row_outer_hull, q_straddle, {}, removed_audit_spans_by_doc={"d_str": [(20, 35)]})
    assert hits_hull["evidence_span_hit_at_10"] == 1.0
    assert hits_hull["visible_evidence_span_hit_at_10"] == 0.0

    # 3. Split >128-token atomic sentence >=80% non-ws coverage rule (strict canonical_text_S required)
    canon_s = "abcdefghij" * 2  # 20 non-ws chars [0, 20)
    q_split = make_query_spec(
        query_id="q_gt128",
        required_evidence_facets=[[{"document_id": "d_gt", "s_spans": [[0, 20]], "is_split_atomic_gt128": True}]],
    )
    # 16/20 = 80% -> PASS; 15/20 = 75% -> FAIL
    row_80 = [make_ranking_row(cell_id="C1-RRF", query_id="q_gt128", rank=1, document_id="d_gt", c_full_s_spans=[[0, 20]], c_vis_s_spans=[[0, 16]])]
    row_75 = [make_ranking_row(cell_id="C1-RRF", query_id="q_gt128", rank=1, document_id="d_gt", c_full_s_spans=[[0, 20]], c_vis_s_spans=[[0, 15]])]
    assert compute_span_hits_at_10(row_80, q_split, {}, docs_by_id={"d_gt": {"canonical_text_S": canon_s}})["visible_evidence_span_hit_at_10"] == 1.0
    assert compute_span_hits_at_10(row_75, q_split, {}, docs_by_id={"d_gt": {"canonical_text_S": canon_s}})["visible_evidence_span_hit_at_10"] == 0.0

    # Missing canonical_text_S with is_split_atomic_gt128=True raises ValueError (no raw-char fallback)
    with pytest.raises(ValueError, match="canonical_text_S is required"):
        compute_span_hits_at_10(row_80, q_split, {}, docs_by_id=None)

    # Whitespace-heavy string: 4 non-ws chars ("a" + 16 spaces + "bcd"), [0, 18) covers 2/4 = 50% < 80% -> False
    ws_s = "a" + (" " * 16) + "bcd"
    assert span_hit_matches([(0, 18)], [(0, len(ws_s))], [], is_split_atomic_gt128=True, canonical_text_S=ws_s) is False

    # Reject boolean span endpoints in facet OR alternatives and ranking spans
    q_bool_span = make_query_spec(
        query_id="q_bool_sp",
        required_evidence_facets=[[{"document_id": "d1", "s_spans": [[True, 10]]}]],
    )
    with pytest.raises(ValueError, match="Boolean or non-int"):
        compute_span_hits_at_10(row_80, q_bool_span, {})
    row_bool_span = [
        make_ranking_row(cell_id="C1-RRF", query_id="q_gt128", rank=1, document_id="d_gt", c_full_s_spans=[[True, 10]], c_vis_s_spans=[[0, 16]])
    ]
    with pytest.raises(ValueError, match="Boolean or non-int"):
        compute_span_hits_at_10(row_bool_span, q_split, {}, docs_by_id={"d_gt": {"canonical_text_S": canon_s}})


# ============================================================================
# FX-14: PCG64(20261105), BCa Degeneracy Fallbacks, MC Sign-Flip, Holm, Winner Gate
# ============================================================================
def test_fx14_stats_bca_degeneracy_exhaustive_small_n_and_winner_gate() -> None:
    # (a) Non-degenerate 40-query delta vector: bit-exact reproducibility & true BCa
    rng = np.random.Generator(np.random.PCG64(12345))
    deltas_40 = (0.06 + 0.05 * rng.standard_normal(40)).tolist()
    res_a = paired_bootstrap_and_sign_flip(deltas_40, seed=STAT_SEED, b_resamples=10_000)
    res_b = paired_bootstrap_and_sign_flip(deltas_40, seed=STAT_SEED, b_resamples=10_000)
    assert res_a == res_b
    assert res_a.test_method == "MONTE_CARLO_SIGN_FLIP"
    assert res_a.ci_method == "BCA_AND_PERCENTILE"
    assert res_a.bca_ci_low is not None and res_a.bca_ci_high is not None

    # (b) All-zero delta vector -> DEGENERATE_CONSTANT & p_mc == 1.0
    zero_res = paired_bootstrap_and_sign_flip([0.0] * 40)
    assert zero_res.ci_method == "DEGENERATE_CONSTANT"
    assert zero_res.ci_low == 0.0 and zero_res.ci_high == 0.0
    assert zero_res.p_mc == 1.0

    # (c) Constant non-zero delta = 0.05 -> DEGENERATE_CONSTANT [0.05, 0.05]
    const_res = paired_bootstrap_and_sign_flip([0.05] * 40)
    assert const_res.ci_method == "DEGENERATE_CONSTANT"
    assert const_res.ci_low == 0.05 and const_res.ci_high == 0.05
    assert abs(const_res.p_mc - (1.0 / 10001.0)) < 1e-12

    # (d) BCa scale invariance & undefined fallback cases:
    # 1. Scale invariance: [0.0, 1e-6] and [0.0]*39 + [1e-5] match unit-scale acceleration & BCA_AND_PERCENTILE
    unit_skew = paired_bootstrap_and_sign_flip([0.0] * 39 + [1.0], seed=STAT_SEED, b_resamples=10_000)
    tiny_skew = paired_bootstrap_and_sign_flip([0.0] * 39 + [1e-5], seed=STAT_SEED, b_resamples=10_000)
    assert unit_skew.ci_method == "BCA_AND_PERCENTILE"
    assert tiny_skew.ci_method == "BCA_AND_PERCENTILE"
    assert unit_skew.acceleration is not None and tiny_skew.acceleration is not None
    assert abs(unit_skew.acceleration - tiny_skew.acceleration) < 1e-9

    tiny_pair = paired_bootstrap_and_sign_flip([0.0, 1e-6], seed=STAT_SEED, b_resamples=10_000)
    unit_pair = paired_bootstrap_and_sign_flip([0.0, 1.0], seed=STAT_SEED, b_resamples=10_000)
    assert tiny_pair.ci_method == unit_pair.ci_method == "BCA_AND_PERCENTILE"

    # 2. Extreme one-sided skew / small B where p0 == 1.0 -> strictly PERCENTILE_FALLBACK_BCA_UNDEFINED
    p0_undef_res = paired_bootstrap_and_sign_flip([0.0] * 39 + [1.0], seed=STAT_SEED, b_resamples=3)
    assert p0_undef_res.ci_method == "PERCENTILE_FALLBACK_BCA_UNDEFINED"
    assert p0_undef_res.bca_ci_low is None and p0_undef_res.bca_ci_high is None
    assert math.isfinite(p0_undef_res.ci_low) and math.isfinite(p0_undef_res.ci_high)

    # Symmetric non-constant vector where sum_d3 == 0 AND scale > 0 -> MUST be valid BCa (a == 0.0), NOT undefined!
    sym_vec = [0.01 * i for i in range(-10, 11)]  # 21 values symmetric around 0 -> sum_d3 == 0
    sym_res = paired_bootstrap_and_sign_flip(sym_vec, seed=STAT_SEED, b_resamples=10_000)
    assert sym_res.ci_method == "BCA_AND_PERCENTILE"
    assert sym_res.acceleration is not None and abs(sym_res.acceleration) < 1e-12

    # (e) Small-n (n <= 16) uses exhaustive 2^n sign-flip; n > 16 uses MC
    small_res = paired_bootstrap_and_sign_flip([0.05, 0.05, 0.05, 0.05])
    assert small_res.test_method == "EXHAUSTIVE_SIGN_FLIP"
    assert abs(small_res.p_mc - (2.0 / 16.0)) < 1e-12

    # (f) Holm-Bonferroni validation & 4-part Winner Gate (pass + all negative branches)
    holm = holm_bonferroni({"K1": 0.001, "K2": 0.02, "K3": 0.03, "K4": 0.5, "K5": 0.8})
    assert abs(holm["K1"] - 0.005) < 1e-12
    assert abs(holm["K2"] - 0.08) < 1e-12
    for bad_p in (-0.1, 1.5, float("nan"), True):
        with pytest.raises(ValueError):
            holm_bonferroni({"K1": bad_p})  # type: ignore[dict-item]

    ev_pass = evaluate_winner_gate(
        "K1",
        "C1-RRF",
        "C1-BM25",
        delta_min=0.035,
        delta_max=0.050,
        d_low_vec=deltas_40,
        stats_res=res_a,
        p_mc_holm=0.001,
        vis_span_delta=0.02,
        fse_a=0.10,
        fse_b=0.10,
    )
    assert ev_pass.decision == "A_OVER_B"

    ev_non_id = evaluate_winner_gate(
        "K2",
        "C1-RRF",
        "C1-Dense",
        delta_min=0.010,
        delta_max=0.045,
        d_low_vec=deltas_40,
        stats_res=res_a,
        p_mc_holm=0.001,
        vis_span_delta=0.0,
        fse_a=0.10,
        fse_b=0.10,
    )
    assert ev_non_id.decision == "NO_CLEAR_WINNER"
    assert ev_non_id.bounds_non_identifying is True
    assert "BOUNDS_NON_IDENTIFYING" in ev_non_id.flags

    ev_small_max = evaluate_winner_gate(
        "K3", "C1-Dense", "C0-Dense", delta_min=0.010, delta_max=0.025,
        d_low_vec=deltas_40, stats_res=res_a, p_mc_holm=0.001, vis_span_delta=0.0, fse_a=0.0, fse_b=0.0,
    )
    assert ev_small_max.decision == "NO_CLEAR_WINNER" and ev_small_max.bounds_non_identifying is False

    ev_vis_neg = evaluate_winner_gate(
        "K4", "C1-RRF", "C0-RRF", delta_min=0.040, delta_max=0.050,
        d_low_vec=deltas_40, stats_res=res_a, p_mc_holm=0.001, vis_span_delta=-0.01, fse_a=0.0, fse_b=0.0,
    )
    assert ev_vis_neg.decision == "NO_CLEAR_WINNER"

    ev_fse_fail = evaluate_winner_gate(
        "K5", "C1-BM25", "C0-BM25", delta_min=0.040, delta_max=0.050,
        d_low_vec=deltas_40, stats_res=res_a, p_mc_holm=0.001, vis_span_delta=0.01, fse_a=0.25, fse_b=0.10,
    )
    assert ev_fse_fail.decision == "NO_CLEAR_WINNER"

    ev_p_fail = evaluate_winner_gate(
        "K1", "C1-RRF", "C1-BM25", delta_min=0.040, delta_max=0.050,
        d_low_vec=deltas_40, stats_res=res_a, p_mc_holm=0.06, vis_span_delta=0.01, fse_a=0.10, fse_b=0.10,
    )
    assert ev_p_fail.decision == "NO_CLEAR_WINNER"


# ============================================================================
# FX-15: Zero-ML-Import Isolation, SHA-256 Tamper Rejection, No Label Self-Gen
# ============================================================================
def test_fx15_zero_ml_imports_tamper_abort_and_no_label_self_gen(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = build_fx15_smoke_bundle(tmp_path)
    src_dir = str(Path(__file__).resolve().parents[1] / "src")
    env = dict(os.environ)
    env["PYTHONPATH"] = src_dir
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONHASHSEED"] = "0"

    # Static AST audit + PEP 562 lazy package export check
    assert_g4_package_zero_ml_imports()
    assert callable(w07_g4_scorer.score_g4)
    assert callable(w07_g4_scorer.score_g4_from_files)

    # 1. Clean subprocess import (including w07_g4_scorer.scorer) + sys.modules verification
    proc_import = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys, w07_g4_scorer, w07_g4_scorer.scorer; "
                "w07_g4_scorer.assert_zero_ml_imports(); "
                "forbidden={'torch','transformers','sentence_transformers','tokenizers','underthesea','w07_retrieval','apps.ai_service'}; "
                "assert not [m for m in sys.modules if any(m==f or m.startswith(f+'.') for f in forbidden)]"
            ),
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc_import.returncode == 0, proc_import.stderr

    # 2. Clean subprocess CLI end-to-end execution (zero RuntimeWarning!)
    out_json = tmp_path / "g4_report.json"
    proc_cli = subprocess.run(
        [
            sys.executable,
            "-m",
            "w07_g4_scorer.scorer",
            "--rankings",
            str(bundle["rankings_path"]),
            "--manifest",
            str(bundle["manifest_path"]),
            "--qrels",
            str(bundle["qrels_path"]),
            "--queries",
            str(bundle["queries_path"]),
            "--docs",
            str(bundle["docs_path"]),
            "--output",
            str(out_json),
            "--strict-full-pool",
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc_cli.returncode == 0, proc_cli.stderr
    assert "RuntimeWarning" not in proc_cli.stderr, proc_cli.stderr
    report = json.loads(out_json.read_text(encoding="utf-8"))
    assert report["manifest_verification"]["verified"] is True
    assert report["g5_status"] == "HOLD"

    # 3. Runtime sys.modules guard triggers immediately if forbidden module injected
    with monkeypatch.context() as mp:
        mp.setitem(sys.modules, "torch", object())
        with pytest.raises(RuntimeError, match="FORBIDDEN_ML_OR_RETRIEVER_IMPORT"):
            assert_zero_ml_imports()

    # 4. 1-byte tamper on g3_sealed_rankings_v1.jsonl MUST abort before scoring (subprocess CLI)
    raw = bytearray(bundle["rankings_path"].read_bytes())
    raw[10] ^= 0x01
    tampered_path = tmp_path / "tampered_rankings.jsonl"
    tampered_path.write_bytes(bytes(raw))
    manifest_obj = json.loads(bundle["manifest_path"].read_text(encoding="utf-8"))
    manifest_obj["rankings_file"] = tampered_path.name
    tampered_manifest = tmp_path / "tampered_manifest.json"
    tampered_manifest.write_text(json.dumps(manifest_obj), encoding="utf-8")

    with pytest.raises(ValueError, match="RANKINGS_SHA256_MISMATCH"):
        load_sealed_rankings(tampered_path, tampered_manifest)

    tamper_out = tmp_path / "should_not_exist.json"
    proc_tamper = subprocess.run(
        [
            sys.executable,
            "-m",
            "w07_g4_scorer.scorer",
            "--rankings",
            str(tampered_path),
            "--manifest",
            str(tampered_manifest),
            "--qrels",
            str(bundle["qrels_path"]),
            "--queries",
            str(bundle["queries_path"]),
            "--output",
            str(tamper_out),
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc_tamper.returncode == 2
    assert "RANKINGS_SHA256_MISMATCH" in proc_tamper.stderr
    assert not tamper_out.exists()

    # 5. Missing external qrels / judges MUST fail rather than self-generating labels (subprocess CLI)
    nolabel_out = tmp_path / "no_label_report.json"
    proc_nolabel = subprocess.run(
        [
            sys.executable,
            "-m",
            "w07_g4_scorer.scorer",
            "--rankings",
            str(bundle["rankings_path"]),
            "--manifest",
            str(bundle["manifest_path"]),
            "--queries",
            str(bundle["queries_path"]),
            "--output",
            str(nolabel_out),
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc_nolabel.returncode == 2
    assert "EXTERNAL_LABELS_REQUIRED" in proc_nolabel.stderr
    assert not nolabel_out.exists()

    # 6. Poisoned sys.modules inside CLI subprocess MUST fail closed with FORBIDDEN_ML_OR_RETRIEVER_IMPORT
    proc_poisoned = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys, types; "
                "sys.modules['w07_retrieval'] = types.ModuleType('w07_retrieval'); "
                "from w07_g4_scorer.scorer import main; "
                "raise SystemExit(main([]))"
            ),
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc_poisoned.returncode != 0
    assert "FORBIDDEN_ML_OR_RETRIEVER_IMPORT" in proc_poisoned.stderr


# ============================================================================
# FX-16: Unanswerable Q_unans Exposure vs AnyResult & Hard G5 Boundary
# ============================================================================
def test_fx16_unanswerable_exposure_and_zero_g5_fields(tmp_path: Path) -> None:
    q_unans = make_query_spec(
        query_id="q_u1",
        query_family="S5_UNANSWERABLE_OR_UNSTABLE",
        target_city="Hạ Long",
        target_poi_ids=["poi-hl-target"],
    )
    docs_meta = {
        **{f"d_unrel_{i}": {"poi_id": f"poi-other-{i}", "has_conflict": False} for i in range(1, 11)},
        "d_decoy": {"poi_id": "poi-hl-target", "has_conflict": True},
    }
    qrels_q = {
        **{f"d_unrel_{i}": QrelRecord("q_u1", f"d_unrel_{i}", RelevanceState.REL_0, 0, (), None) for i in range(1, 11)},
        "d_decoy": QrelRecord("q_u1", "d_decoy", RelevanceState.REL_0, 1, (), None),
    }
    dense_rows = [make_ranking_row(cell_id="C1-Dense", query_id="q_u1", rank=i, document_id=f"d_unrel_{i}") for i in range(1, 11)]
    decoy_rows = [make_ranking_row(cell_id="C0-BM25", query_id="q_u1", rank=1, document_id="d_decoy", assembled_text="FC-001 conflict")]

    m_dense = compute_unanswerable_metrics(dense_rows, q_unans, qrels_q, docs_by_id=docs_meta)
    assert m_dense["any_result_at_10"] == 1.0
    assert m_dense["false_support_exposure_at_10"] == 0.0
    assert m_dense["false_support_count_at_10"] == 0.0

    m_decoy = compute_unanswerable_metrics(decoy_rows, q_unans, qrels_q, docs_by_id=docs_meta)
    assert m_decoy["false_support_exposure_at_10"] == 1.0
    assert m_decoy["same_poi_or_conflict_decoy_at_10"] == 1.0
    assert m_decoy["false_support_count_at_10"] >= 0.1

    # Parameterized [SUPPRESSED_FACT_CONFLICT: ...] tag MUST also set decoy_hit=1.0
    suppressed_rows = [
        make_ranking_row(
            cell_id="C0-BM25",
            query_id="q_u1",
            rank=1,
            document_id="d_unrel_1",
            assembled_text="Notice [SUPPRESSED_FACT_CONFLICT: price mismatch]",
        )
    ]
    m_suppressed = compute_unanswerable_metrics(suppressed_rows, q_unans, qrels_q, docs_by_id=docs_meta)
    assert m_suppressed["same_poi_or_conflict_decoy_at_10"] == 1.0

    # Full report check: ZERO CorrectAbstentionRate / G5 pass fields anywhere in JSON tree
    bundle = build_fx15_smoke_bundle(tmp_path)
    report = score_g4_from_files(
        rankings_path=bundle["rankings_path"],
        manifest_path=bundle["manifest_path"],
        queries_path=bundle["queries_path"],
        qrels_path=bundle["qrels_path"],
        docs_path=bundle["docs_path"],
    )
    all_keys = _collect_all_keys(report)
    forbidden_g5_keys = {"CorrectAbstentionRate", "correct_abstention_rate", "G5_PASS", "g5_pass", "HallucinationRate"}
    assert not (all_keys & forbidden_g5_keys)


# ============================================================================
# Iteration 2 Regression Tests: JSONL docs, strict Q_unans, Recall label, Expected Pairs seal
# ============================================================================
def test_scorer_regressions_jsonl_docs_strict_qunans_recall_label_and_sealed_expected_pairs(
    tmp_path: Path,
) -> None:
    bundle = build_fx15_smoke_bundle(tmp_path)
    docs_dict = json.loads(bundle["docs_path"].read_text(encoding="utf-8"))
    docs_jsonl = write_jsonl(tmp_path / "docs.jsonl", list(docs_dict.values()))

    # 1. Multi-line JSONL --docs loads cleanly
    rep_jsonl = score_g4_from_files(
        rankings_path=bundle["rankings_path"],
        manifest_path=bundle["manifest_path"],
        queries_path=bundle["queries_path"],
        qrels_path=bundle["qrels_path"],
        docs_path=docs_jsonl,
        strict_full_pool=True,
    )
    assert rep_jsonl["q_ans_count"] == 2 and rep_jsonl["q_unans_count"] == 1

    # 2. strict_full_pool=True rejects out-of-pool / unjudged doc on Q_unans
    q_u = [make_query_dict(query_id="q_u", query_family="S5_UNANSWERABLE_OR_UNSTABLE", target_city="Hạ Long")]
    q_u_path = write_jsonl(tmp_path / "q_u.jsonl", q_u)
    r_u = [make_ranking_row(cell_id="C1-RRF", query_id="q_u", rank=1, document_id="d_out_of_pool", score=1.0)]
    rk_u_path, mf_u_path = write_sealed_rankings_bundle(tmp_path / "u_only", r_u, cells=["C1-RRF"])
    qr_u_path = write_jsonl(
        tmp_path / "qr_u.jsonl",
        [{"query_id": "q_u", "document_id": "d_in_pool", "label": "REL_0", "plausible_unsupported_lure": 0, "evidence_s_spans": []}],
    )
    with pytest.raises(ValueError, match="G4_BLOCKER_STRICT_FULL_POOL_CERT_FAILED"):
        score_g4_from_files(
            rankings_path=rk_u_path,
            manifest_path=mf_u_path,
            queries_path=q_u_path,
            qrels_path=qr_u_path,
            strict_full_pool=True,
        )

    # 3. Exhaustive-Recall@K disclosure requires len(doc_universe) == 137 AND unjudged_count == 0
    all_137 = [f"d{i:03d}" for i in range(1, 138)]
    q_137 = [make_query_spec(query_id="q_137", target_city="Hà Nội", target_poi_ids=["poi-hn-01"])]
    rows_137 = [
        make_ranking_row(cell_id="C1-RRF", query_id="q_137", rank=i, document_id=f"d{i:03d}", score=1.0 / i)
        for i in range(1, 11)
    ]
    rk_137_p, mf_137_p = write_sealed_rankings_bundle(tmp_path / "r137", rows_137, cells=["C1-RRF"])
    mf_137, rrows_137 = load_sealed_rankings(rk_137_p, mf_137_p)

    # 10 REL_2 -> EXACT_CERTIFIED (all_exact=True), but remaining 127 UNJUDGED -> PooledJudged-Recall@K
    qrels_partial = {
        ("q_137", f"d{i:03d}"): QrelRecord("q_137", f"d{i:03d}", RelevanceState.REL_2, 0, ((0, 10),), None)
        for i in range(1, 11)
    }
    rep_partial = score_g4(
        manifest=mf_137,
        ranking_rows=rrows_137,
        query_specs=q_137,
        qrels=qrels_partial,
        all_doc_ids=all_137,
    )
    assert rep_partial["cell_metrics"]["C1-RRF"]["recall_completeness_disclosure"].startswith("PooledJudged-Recall@K")

    # All 137 judged (10 REL_2 + 127 REL_0) -> unjudged_count == 0 -> Exhaustive-Recall@K
    qrels_full = dict(qrels_partial)
    for i in range(11, 138):
        qrels_full[("q_137", f"d{i:03d}")] = QrelRecord("q_137", f"d{i:03d}", RelevanceState.REL_0, 0, (), None)
    rep_exhaustive = score_g4(
        manifest=mf_137,
        ranking_rows=rrows_137,
        query_specs=q_137,
        qrels=qrels_full,
        all_doc_ids=all_137,
    )
    assert rep_exhaustive["cell_metrics"]["C1-RRF"]["recall_completeness_disclosure"].startswith("Exhaustive-Recall@K")

    # 4. Tampered sealed --expected-pairs manifest fails with EXPECTED_PAIRS_MANIFEST_SHA256_MISMATCH
    ep_manifest = seal_expected_pairs_manifest(
        judging_order="ORDER_B",
        expected_pairs=[("q_ans_1", "d_pos_1"), ("q_ans_1", "d_neg_1")],
        query_manifest_sha256="b" * 64,
        sanitized_v_corpus_sha256="c" * 64,
        sealed_at_utc="2026-11-20T10:00:00Z",
        g3_rankings_bundle_sha256="d" * 64,
        expected_v_corpus_sha256=None,
    )
    ep_manifest["expected_pairs"][0][1] = "d_tampered"
    ep_path = tmp_path / "tampered_ep.json"
    ep_path.write_text(json.dumps(ep_manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="EXPECTED_PAIRS_MANIFEST_SHA256_MISMATCH"):
        score_g4_from_files(
            rankings_path=bundle["rankings_path"],
            manifest_path=bundle["manifest_path"],
            queries_path=bundle["queries_path"],
            qrels_path=bundle["qrels_path"],
            expected_pairs_path=ep_path,
        )


# ============================================================================
# Gated Real-Corpus Scorer Stub (HOLD: Requires G1.5 Freeze + Signed Owner Receipt)
# ============================================================================
from conftest import REAL_CORPUS_GATE_REASON, is_real_corpus_authorized


@pytest.mark.skipif(
    not is_real_corpus_authorized(),
    reason=REAL_CORPUS_GATE_REASON,
)
def test_gated_real_137_corpus_g4_scorer_stub() -> None:
    pytest.fail("HOLD: Gated real-corpus G4 scoring requires frozen FINAL-50 qrels and signed Owner authorization receipt.")
