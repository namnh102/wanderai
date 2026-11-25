"""Decoupled G4 Scorer orchestration and CLI entrypoint (zero ML/retriever imports)."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from w07_g4_scorer.contracts import (
    ANNEX_G15_CONTRASTS_K1_K5,
    GAIN_MAP,
    Cert4Status,
    QrelRecord,
    RankingManifest,
    RankingRow,
    RelevanceState,
    assert_g4_package_zero_ml_imports,
    assert_zero_ml_imports,
    compute_query_certificates,
    count_epistemic_lineages,
    load_external_qrels,
    load_sealed_rankings,
    merge_intervals,
)
from w07_g4_scorer.judge_gates import (
    evaluate_dual_judge_concordance,
    score_validated_judge_rankings,
    verify_sealed_expected_pairs_manifest,
)
from w07_g4_scorer.metrics import (
    compute_span_hits_at_10,
    compute_unanswerable_metrics,
    coupled_ndcg10_bounds,
    coupled_pairwise_contrast_bounds,
    dcg_at_10,
    hit_rate_at_10,
    mrr_at_10,
    recall_at_k,
)
from w07_g4_scorer.query_manifest import QuerySpec, load_query_manifest
from w07_g4_scorer.stats import DEFAULT_B, STAT_SEED, evaluate_winner_gate, holm_bonferroni, paired_bootstrap_and_sign_flip


def _load_removed_audit_spans(path: Path | str | None) -> dict[str, list[tuple[int, int]]]:
    if path is None:
        return {}
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Removed audit spans file not found: {p}")
    raw = json.loads(p.read_text(encoding="utf-8"))
    if type(raw) is not dict:
        raise ValueError("removed_audit_spans JSON must be a dict mapping doc_id -> [[start, end], ...]")
    out: dict[str, list[tuple[int, int]]] = {}
    for did, spans in raw.items():
        if type(did) is not str or type(spans) is not list:
            raise ValueError(f"Invalid removed_audit_spans entry for {did!r}")
        pairs: list[tuple[int, int]] = []
        for sp in spans:
            if not isinstance(sp, (list, tuple)) or len(sp) != 2:
                raise ValueError(f"Invalid span {sp!r} for {did!r}")
            a, b = sp[0], sp[1]
            if type(a) is bool or type(b) is bool or type(a) is not int or type(b) is not int:
                raise ValueError(f"Boolean/non-int span {sp!r} for {did!r}")
            pairs.append((a, b))
        out[did] = merge_intervals(pairs)
    return out


def _load_docs_metadata(path: Path | str | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Docs metadata file not found: {p}")
    raw_text = p.read_text(encoding="utf-8").strip()
    if not raw_text:
        raise ValueError(f"Empty docs metadata file: {p}")

    rows: list[Any]
    if raw_text.startswith("["):
        parsed = json.loads(raw_text)
        if type(parsed) is not list:
            raise ValueError(f"Expected JSON list in docs metadata file: {p}")
        rows = parsed
    elif raw_text.startswith("{"):
        try:
            obj = json.loads(raw_text)
        except json.JSONDecodeError:
            rows = [json.loads(ln) for ln in raw_text.splitlines() if ln.strip()]
        else:
            if isinstance(obj, dict) and all(isinstance(v, dict) for v in obj.values()):
                return obj
            if isinstance(obj, dict):
                rows = [obj]
            else:
                raise ValueError(f"Unexpected JSON type in docs metadata file: {p}")
    else:
        rows = [json.loads(ln) for ln in raw_text.splitlines() if ln.strip()]

    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if type(row) is not dict:
            raise ValueError(f"Doc row must be a dict, got {row!r}")
        did = row.get("document_id", row.get("doc_id"))
        if type(did) is not str or not did.strip():
            raise ValueError(f"Doc row missing document_id: {row!r}")
        out[did] = row
    return out


def _load_judge_responses_jsonl(path: Path | str) -> dict[tuple[str, str], Any]:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Judge responses file not found: {p}")
    lines = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not lines:
        raise ValueError(f"Empty judge responses file: {p}")
    out: dict[tuple[str, str], Any] = {}
    for line_no, ln in enumerate(lines, start=1):
        obj = json.loads(ln)
        if type(obj) is not dict:
            raise ValueError(f"Invalid judge response row line {line_no}")
        qid = obj.get("query_id")
        did = obj.get("document_id", obj.get("doc_id"))
        if type(qid) is not str or type(did) is not str:
            raise ValueError(f"Missing query_id/document_id in judge response line {line_no}")
        if "raw_json_str" in obj:
            raw_str = obj["raw_json_str"]
        elif "response_json" in obj:
            raw_str = obj["response_json"] if type(obj["response_json"]) is str else json.dumps(obj["response_json"])
        else:
            payload = {k: v for k, v in obj.items() if k not in ("query_id", "document_id", "doc_id")}
            raw_str = json.dumps(payload, ensure_ascii=False)
        out[(qid, did)] = raw_str
    return out


def _mean_or_none(vals: Sequence[float | None]) -> float | None:
    clean = [float(v) for v in vals if v is not None]
    if not clean:
        return None
    return sum(clean) / float(len(clean))


def score_g4(
    *,
    manifest: RankingManifest,
    ranking_rows: Sequence[RankingRow],
    query_specs: Sequence[QuerySpec],
    qrels: Mapping[tuple[str, str], QrelRecord] | None = None,
    removed_audit_spans_by_doc: Mapping[str, Sequence[tuple[int, int]]] | None = None,
    docs_by_id: Mapping[str, Mapping[str, Any]] | None = None,
    all_doc_ids: Sequence[str] | None = None,
    pool_doc_ids_by_q: Mapping[str, Sequence[str]] | None = None,
    strict_full_pool: bool = False,
    judge_a_responses: dict[tuple[str, str], Any] | None = None,
    judge_b_responses: dict[tuple[str, str], Any] | None = None,
    judging_order: str = "ORDER_A",
    sealed_expected_pairs: set[tuple[str, str]] | list[tuple[str, str]] | None = None,
    tau_unresolved: float = 0.10,
    enforce_clean_sys_modules: bool = False,
) -> dict[str, Any]:
    """Run decoupled G4 scoring over sealed rankings + external qrels and/or validated judge responses."""
    assert_g4_package_zero_ml_imports()
    if enforce_clean_sys_modules:
        assert_zero_ml_imports()

    if qrels is None and judge_a_responses is None and judge_b_responses is None:
        raise ValueError(
            "EXTERNAL_LABELS_REQUIRED: G4 scorer requires external qrels or judge responses; "
            "self-generating relevance labels is strictly forbidden"
        )

    rem_map: dict[str, list[tuple[int, int]]] = {
        did: merge_intervals(list(sp)) for did, sp in (removed_audit_spans_by_doc or {}).items()
    }
    docs_meta = dict(docs_by_id or {})
    q_by_id: dict[str, QuerySpec] = {q.query_id: q for q in query_specs}

    # Group rankings: rankings[cell_id][query_id] -> sorted list[RankingRow]
    rankings_by_cell: dict[str, dict[str, list[RankingRow]]] = {c: defaultdict(list) for c in manifest.cells}
    for row in ranking_rows:
        rankings_by_cell.setdefault(row.cell_id, defaultdict(list))[row.query_id].append(row)
    for cell_id, by_q in rankings_by_cell.items():
        for qid in by_q:
            by_q[qid].sort(key=lambda r: r.rank)

    cells = list(manifest.cells)

    # Determine universe of known documents
    doc_universe_set: set[str] = set(all_doc_ids or ())
    doc_universe_set.update(docs_meta.keys())
    for r in ranking_rows:
        doc_universe_set.add(r.document_id)
    if qrels is not None:
        for _, did in qrels:
            doc_universe_set.add(did)
    doc_universe = sorted(doc_universe_set)

    report: dict[str, Any] = {
        "schema_version": "w07_g4_report_v1",
        "epistemic_tier": "HUMAN_ADJUDICATED_QRELS" if qrels is not None else "AI_PROXY_DUAL_LLM",
        "g5_status": "HOLD",
        "manifest_verification": {
            "rankings_file": manifest.rankings_file,
            "rankings_sha256": manifest.rankings_sha256,
            "verified": True,
            "row_count": manifest.row_count,
            "cells": cells,
            "snapshot_id": manifest.snapshot_id,
        },
    }

    if qrels is not None:
        lineage_by_doc: dict[str, str | None] = {}
        for did, meta in docs_meta.items():
            lin = meta.get("source_lineage_id")
            if isinstance(lin, str) and lin.strip():
                lineage_by_doc[did] = lin.strip()
        for (_, did), rec in qrels.items():
            if isinstance(rec.source_lineage_id, str) and rec.source_lineage_id.strip() and did not in lineage_by_doc:
                lineage_by_doc[did] = rec.source_lineage_id.strip()

        qrels_by_q: dict[str, dict[str, QrelRecord]] = defaultdict(dict)
        for (qid, did), rec in qrels.items():
            qrels_by_q[qid][did] = rec

        certs_by_q: dict[str, Any] = {}
        disposition_table: list[dict[str, Any]] = []
        zero_idcg_ledger: list[dict[str, Any]] = []
        q_ans: list[str] = []
        q_unans: list[str] = []
        q_zero_exact: list[str] = []

        for q in query_specs:
            qid = q.query_id
            top10_docs_by_cell = {
                cell_id: [r.document_id for r in rankings_by_cell[cell_id].get(qid, [])[:10]]
                for cell_id in cells
            }
            pool_docs = pool_doc_ids_by_q[qid] if (pool_doc_ids_by_q and qid in pool_doc_ids_by_q) else None
            cert = compute_query_certificates(
                qid,
                top10_docs_by_cell,
                doc_universe,
                qrels,
                pool_doc_ids=pool_docs,
                strict_full_pool=strict_full_pool,
            )
            certs_by_q[qid] = cert

            if q.pre_rank_answerability == "UNANSWERABLE":
                if strict_full_pool:
                    min_c2 = min(cert.cert2_judged_at_10.values()) if cert.cert2_judged_at_10 else 1.0
                    if (
                        cert.cert1_top10_in_pool < 1.0 - 1e-12
                        or min_c2 < 1.0 - 1e-12
                        or cert.cert3_full_pool_closed < 1.0 - 1e-12
                    ):
                        raise ValueError(
                            f"G4_BLOCKER_STRICT_FULL_POOL_CERT_FAILED on query {qid!r}: "
                            f"Cert-1={cert.cert1_top10_in_pool}, Cert-2={min_c2}, Cert-3={cert.cert3_full_pool_closed}"
                        )
                q_unans.append(qid)
                disposition_table.append(
                    {
                        "query_id": qid,
                        "query_family": q.query_family,
                        "target_city": q.target_city,
                        "pre_rank_answerability": q.pre_rank_answerability,
                        "in_q_ans": False,
                        "in_q_unans": True,
                        "exclusion_reason": None,
                        "cert1_top10_in_pool": cert.cert1_top10_in_pool,
                        "cert3_full_pool_closed": cert.cert3_full_pool_closed,
                        "cert4_status": None,
                        "idcg_l": None,
                        "idcg_u": None,
                    }
                )
                continue

            # Pre-rank ANSWERABLE: only ZERO_POSITIVE_EXACT leaves Q_ans!
            if cert.cert4_status == Cert4Status.ZERO_POSITIVE_EXACT:
                q_zero_exact.append(qid)
                zero_idcg_ledger.append(
                    {
                        "query_id": qid,
                        "query_family": q.query_family,
                        "target_city": q.target_city,
                        "reason": "ZERO_POSITIVE_EXACT",
                        "known_count": cert.known_count,
                        "unjudged_count": cert.unjudged_count,
                    }
                )
                disposition_table.append(
                    {
                        "query_id": qid,
                        "query_family": q.query_family,
                        "target_city": q.target_city,
                        "pre_rank_answerability": q.pre_rank_answerability,
                        "in_q_ans": False,
                        "in_q_unans": False,
                        "exclusion_reason": "ZERO_POSITIVE_EXACT",
                        "cert1_top10_in_pool": cert.cert1_top10_in_pool,
                        "cert2_min_judged_at_10": min(cert.cert2_judged_at_10.values()) if cert.cert2_judged_at_10 else 1.0,
                        "cert3_full_pool_closed": cert.cert3_full_pool_closed,
                        "cert4_status": cert.cert4_status.value,
                        "idcg_l": cert.idcg_l,
                        "idcg_u": cert.idcg_u,
                    }
                )
                continue

            if cert.cert4_status == Cert4Status.INVALID_UNRESOLVED:
                raise ValueError(
                    f"G4_BLOCKER_INVALID_UNRESOLVED on query {qid!r}: "
                    f"Cert-2={cert.cert2_judged_at_10}, IDCG_L={cert.idcg_l}, IDCG_U={cert.idcg_u}"
                )

            if strict_full_pool:
                min_c2 = min(cert.cert2_judged_at_10.values()) if cert.cert2_judged_at_10 else 1.0
                if cert.cert1_top10_in_pool < 1.0 - 1e-12 or min_c2 < 1.0 - 1e-12 or cert.cert3_full_pool_closed < 1.0 - 1e-12:
                    raise ValueError(
                        f"G4_BLOCKER_STRICT_FULL_POOL_CERT_FAILED on query {qid!r}: "
                        f"Cert-1={cert.cert1_top10_in_pool}, Cert-2={min_c2}, Cert-3={cert.cert3_full_pool_closed}"
                    )

            q_ans.append(qid)
            disposition_table.append(
                {
                    "query_id": qid,
                    "query_family": q.query_family,
                    "target_city": q.target_city,
                    "pre_rank_answerability": q.pre_rank_answerability,
                    "in_q_ans": True,
                    "in_q_unans": False,
                    "exclusion_reason": None,
                    "cert1_top10_in_pool": cert.cert1_top10_in_pool,
                    "cert2_min_judged_at_10": min(cert.cert2_judged_at_10.values()) if cert.cert2_judged_at_10 else 1.0,
                    "cert3_full_pool_closed": cert.cert3_full_pool_closed,
                    "cert4_status": cert.cert4_status.value,
                    "idcg_l": cert.idcg_l,
                    "idcg_u": cert.idcg_u,
                }
            )

        q_ans_exact = [qid for qid in q_ans if certs_by_q[qid].cert4_status == Cert4Status.EXACT_CERTIFIED]
        all_exact = len(q_ans) > 0 and len(q_ans_exact) == len(q_ans)
        headline_status = "EXACT_FULL_SET_ESTIMATE" if all_exact else "NO_EXACT_FULL_SET_ESTIMATE"

        # Per-cell evaluation on Q_ans
        dcg_by_cell_q: dict[str, dict[str, float]] = {c: {} for c in cells}
        ndcg_l_by_cell_q: dict[str, dict[str, float]] = {c: {} for c in cells}
        ndcg_u_by_cell_q: dict[str, dict[str, float]] = {c: {} for c in cells}
        vis_span_by_cell_q: dict[str, dict[str, float | None]] = {c: {} for c in cells}
        full_span_by_cell_q: dict[str, dict[str, float | None]] = {c: {} for c in cells}

        cell_metrics: dict[str, Any] = {}
        for cell_id in cells:
            mrrs: list[float] = []
            hrs: list[float] = []
            rec5s: list[float | None] = []
            rec10s: list[float | None] = []
            lin_counts: list[int] = []
            for qid in q_ans:
                top_rows = rankings_by_cell[cell_id].get(qid, [])[:10]
                top_docs = [r.document_id for r in top_rows]
                qrel_q = qrels_by_q[qid]

                gains = [GAIN_MAP[qrel_q[did].label] for did in top_docs]
                dcg_q = dcg_at_10(gains)
                coupled_q = coupled_ndcg10_bounds(top_docs, doc_universe, qrel_q, strict_cert2=True)

                dcg_by_cell_q[cell_id][qid] = dcg_q
                ndcg_l_by_cell_q[cell_id][qid] = coupled_q["ndcg_l"]
                ndcg_u_by_cell_q[cell_id][qid] = coupled_q["ndcg_u"]

                spans_q = compute_span_hits_at_10(
                    top_rows,
                    q_by_id[qid],
                    qrel_q,
                    removed_audit_spans_by_doc=rem_map,
                    docs_by_id=docs_meta,
                )
                full_span_by_cell_q[cell_id][qid] = spans_q["evidence_span_hit_at_10"]
                vis_span_by_cell_q[cell_id][qid] = spans_q["visible_evidence_span_hit_at_10"]

                mrrs.append(mrr_at_10(top_docs, qrel_q))
                hrs.append(hit_rate_at_10(top_docs, qrel_q))
                rec5s.append(recall_at_k(top_docs, qrel_q, k=5))
                rec10s.append(recall_at_k(top_docs, qrel_q, k=10))

                pos_top10 = [
                    did
                    for did in top_docs
                    if did in qrel_q and qrel_q[did].label in (RelevanceState.REL_1, RelevanceState.REL_2)
                ]
                lin_counts.append(count_epistemic_lineages(pos_top10, lineage_by_doc))

            exact_vals = [ndcg_l_by_cell_q[cell_id][qid] for qid in q_ans_exact]
            exact_mean = (sum(exact_vals) / float(len(exact_vals))) if exact_vals else None
            all_unjudged_zero = bool(q_ans) and all(certs_by_q[qid].unjudged_count == 0 for qid in q_ans)
            recall_label = (
                "Exhaustive-Recall@K"
                if (all_exact and len(doc_universe) == 137 and all_unjudged_zero)
                else "PooledJudged-Recall@K"
            )
            cell_metrics[cell_id] = {
                "q_ans_count": len(q_ans),
                "ndcg10_lower": (sum(ndcg_l_by_cell_q[cell_id].values()) / float(len(q_ans))) if q_ans else 0.0,
                "ndcg10_upper": (sum(ndcg_u_by_cell_q[cell_id].values()) / float(len(q_ans))) if q_ans else 0.0,
                "exact_certified_slice_descriptive": {
                    "mean_ndcg10": exact_mean,
                    "exact_count": len(q_ans_exact),
                    "total_q_ans": len(q_ans),
                    "disclosure": f"Descriptive exact-certified slice ({len(q_ans_exact)}/{len(q_ans)}); NOT headline.",
                },
                "evidence_span_hit_at_10": _mean_or_none(list(full_span_by_cell_q[cell_id].values())),
                "visible_evidence_span_hit_at_10": _mean_or_none(list(vis_span_by_cell_q[cell_id].values())),
                "mrr_at_10": (sum(mrrs) / float(len(mrrs))) if mrrs else 0.0,
                "hit_rate_at_10": (sum(hrs) / float(len(hrs))) if hrs else 0.0,
                "pooled_judged_recall_at_5": _mean_or_none(rec5s),
                "pooled_judged_recall_at_10": _mean_or_none(rec10s),
                "recall_completeness_disclosure": (
                    f"{recall_label}: computed over pooled judged positives only; corpus-wide unjudged docs may exist."
                ),
                "epistemic_lineage_mean_at_10": (sum(lin_counts) / float(len(lin_counts))) if lin_counts else 0.0,
            }

        # Unanswerable Q_unans exposure metrics (zero CorrectAbstentionRate / G5 fields)
        unanswerable_safety: dict[str, Any] = {}
        for cell_id in cells:
            if not q_unans:
                unanswerable_safety[cell_id] = {
                    "q_unans_count": 0,
                    "any_result_at_10": None,
                    "same_poi_or_conflict_decoy_at_10": None,
                    "false_support_exposure_at_10": None,
                    "false_support_count_at_10": None,
                }
                continue
            per_q_u = [
                compute_unanswerable_metrics(
                    rankings_by_cell[cell_id].get(qid, [])[:10],
                    q_by_id[qid],
                    qrels_by_q[qid],
                    docs_by_id=docs_meta,
                )
                for qid in q_unans
            ]
            unanswerable_safety[cell_id] = {
                "q_unans_count": len(q_unans),
                "any_result_at_10": sum(x["any_result_at_10"] for x in per_q_u) / float(len(q_unans)),
                "same_poi_or_conflict_decoy_at_10": sum(x["same_poi_or_conflict_decoy_at_10"] for x in per_q_u) / float(len(q_unans)),
                "false_support_exposure_at_10": sum(x["false_support_exposure_at_10"] for x in per_q_u) / float(len(q_unans)),
                "false_support_count_at_10": sum(x["false_support_count_at_10"] for x in per_q_u) / float(len(q_unans)),
            }

        # Contrasts K1..K5 with Holm-Bonferroni & Winner Gate
        idcg_l_map = {qid: certs_by_q[qid].idcg_l for qid in q_ans}
        idcg_u_map = {qid: certs_by_q[qid].idcg_u for qid in q_ans}
        raw_p_by_contrast: dict[str, float] = {}
        contrast_cache: dict[str, dict[str, Any]] = {}

        if q_ans:
            for k_id, (cell_a, cell_b) in ANNEX_G15_CONTRASTS_K1_K5.items():
                if cell_a not in cell_metrics or cell_b not in cell_metrics:
                    continue
                coupled_c = coupled_pairwise_contrast_bounds(
                    {qid: dcg_by_cell_q[cell_a][qid] for qid in q_ans},
                    {qid: dcg_by_cell_q[cell_b][qid] for qid in q_ans},
                    idcg_l_map,
                    idcg_u_map,
                )
                stats_res = paired_bootstrap_and_sign_flip(
                    coupled_c["d_low_vec"],
                    seed=STAT_SEED,
                    b_resamples=DEFAULT_B,
                    allow_exhaustive_small_n=True,
                )
                raw_p_by_contrast[k_id] = stats_res.p_mc
                contrast_cache[k_id] = {
                    "cell_a": cell_a,
                    "cell_b": cell_b,
                    "coupled": coupled_c,
                    "stats": stats_res,
                }

        holm_p = holm_bonferroni(raw_p_by_contrast)
        contrasts_out: dict[str, Any] = {}
        for k_id, c_info in contrast_cache.items():
            cell_a = c_info["cell_a"]
            cell_b = c_info["cell_b"]
            vis_a = cell_metrics[cell_a]["visible_evidence_span_hit_at_10"]
            vis_b = cell_metrics[cell_b]["visible_evidence_span_hit_at_10"]
            vis_delta = (vis_a - vis_b) if (vis_a is not None and vis_b is not None) else None
            fse_a = unanswerable_safety[cell_a]["false_support_exposure_at_10"]
            fse_b = unanswerable_safety[cell_b]["false_support_exposure_at_10"]

            ev = evaluate_winner_gate(
                k_id,
                cell_a,
                cell_b,
                delta_min=c_info["coupled"]["delta_min"],
                delta_max=c_info["coupled"]["delta_max"],
                d_low_vec=c_info["coupled"]["d_low_vec"],
                stats_res=c_info["stats"],
                p_mc_holm=holm_p[k_id],
                vis_span_delta=vis_delta,
                fse_a=fse_a,
                fse_b=fse_b,
            )
            contrasts_out[k_id] = {
                "cell_a": ev.cell_a,
                "cell_b": ev.cell_b,
                "delta_min": ev.delta_min,
                "delta_max": ev.delta_max,
                "d_low_mean": ev.d_low_mean,
                "bootstrap_ci_95_percentile": [ev.stats.percentile_ci_low, ev.stats.percentile_ci_high],
                "bootstrap_ci_95_bca": (
                    [ev.stats.bca_ci_low, ev.stats.bca_ci_high]
                    if (ev.stats.bca_ci_low is not None and ev.stats.bca_ci_high is not None)
                    else None
                ),
                "ci_95": [ev.stats.ci_low, ev.stats.ci_high],
                "ci_method": ev.stats.ci_method,
                "p_mc": ev.stats.p_mc,
                "p_mc_holm": ev.p_mc_holm,
                "test_method": ev.stats.test_method,
                "vis_span_delta": ev.vis_span_delta,
                "fse_a": ev.fse_a,
                "fse_b": ev.fse_b,
                "decision": ev.decision,
                "flags": list(ev.flags),
                "bounds_non_identifying": ev.bounds_non_identifying,
            }

        # Stratified descriptive breakdown (exploratory only)
        by_city: dict[str, Any] = {}
        by_family: dict[str, Any] = {}
        for city in sorted({q_by_id[qid].target_city for qid in q_ans}):
            sub_q = [qid for qid in q_ans if q_by_id[qid].target_city == city]
            by_city[city] = {
                "exploratory_descriptive": True,
                "query_count": len(sub_q),
                "cells": {
                    c: {
                        "ndcg10_lower": sum(ndcg_l_by_cell_q[c][qid] for qid in sub_q) / float(len(sub_q)),
                        "ndcg10_upper": sum(ndcg_u_by_cell_q[c][qid] for qid in sub_q) / float(len(sub_q)),
                    }
                    for c in cells
                },
            }
        for fam in sorted({q_by_id[qid].query_family for qid in q_ans}):
            sub_q = [qid for qid in q_ans if q_by_id[qid].query_family == fam]
            by_family[fam] = {
                "exploratory_descriptive": True,
                "query_count": len(sub_q),
                "cells": {
                    c: {
                        "ndcg10_lower": sum(ndcg_l_by_cell_q[c][qid] for qid in sub_q) / float(len(sub_q)),
                        "ndcg10_upper": sum(ndcg_u_by_cell_q[c][qid] for qid in sub_q) / float(len(sub_q)),
                    }
                    for c in cells
                },
            }

        cert4_counts: dict[str, int] = {st.value: 0 for st in Cert4Status}
        for qid in q_ans + q_zero_exact:
            cert4_counts[certs_by_q[qid].cert4_status.value] += 1

        report.update(
            {
                "q_ans_count": len(q_ans),
                "q_unans_count": len(q_unans),
                "q_zero_exact_count": len(q_zero_exact),
                "headline_status": headline_status,
                "query_disposition_table": disposition_table,
                "certificates": {
                    "cert1_pass_rate": (
                        sum(1 for qid in q_ans + q_unans if certs_by_q[qid].cert1_top10_in_pool >= 1.0 - 1e-12)
                        / float(max(1, len(q_ans) + len(q_unans)))
                    ),
                    "cert2_pass_rate": (
                        sum(
                            1
                            for qid in q_ans
                            if (
                                min(certs_by_q[qid].cert2_judged_at_10.values())
                                if certs_by_q[qid].cert2_judged_at_10
                                else 1.0
                            )
                            >= 1.0 - 1e-12
                        )
                        / float(max(1, len(q_ans)))
                    ),
                    "cert3_pass_rate": (
                        sum(1 for qid in q_ans + q_unans if certs_by_q[qid].cert3_full_pool_closed >= 1.0 - 1e-12)
                        / float(max(1, len(q_ans) + len(q_unans)))
                    ),
                    "cert4_counts": cert4_counts,
                    "zero_idcg_audit_ledger": zero_idcg_ledger,
                },
                "cell_metrics": cell_metrics,
                "unanswerable_safety": unanswerable_safety,
                "contrasts_k1_to_k5": contrasts_out,
                "stratified_descriptive": {
                    "exploratory_descriptive": True,
                    "by_target_city": by_city,
                    "by_query_family": by_family,
                },
            }
        )

    if judge_a_responses is not None or judge_b_responses is not None:
        if not docs_meta:
            raise ValueError("Judge gate evaluation requires docs_by_id (--docs) with canonical_text_S, city, poi_id")
        queries_meta_dicts = [
            {
                "query_id": q.query_id,
                "query_text": q.query_text,
                "split": q.split,
                "creator_exposure_to_corpus": q.creator_exposure_to_corpus,
                "question_origin": q.question_origin,
                "query_family": q.query_family,
                "target_city": q.target_city,
                "pre_rank_answerability": q.pre_rank_answerability,
                "scope_mode": q.scope_mode,
                "target_poi_ids": list(q.target_poi_ids),
                "query_intent_polarity": q.query_intent_polarity,
                "requested_facet_keywords": list(q.requested_facet_keywords),
                "fact_cluster_id": q.fact_cluster_id,
            }
            for q in query_specs
        ]
        rankings_doc_ids_by_cell = {
            c: {qid: [r.document_id for r in rows] for qid, rows in by_q.items()}
            for c, by_q in rankings_by_cell.items()
        }
        if judge_a_responses is not None and judge_b_responses is not None:
            report["judge_gates"] = evaluate_dual_judge_concordance(
                queries_meta=queries_meta_dicts,
                docs_by_id=docs_meta,
                removed_by_doc_id=rem_map,
                rankings_by_cell=rankings_doc_ids_by_cell,
                judge_a_responses=judge_a_responses,
                judge_b_responses=judge_b_responses,
                tau_unresolved=tau_unresolved,
                judging_order=judging_order,
                sealed_expected_pairs=sealed_expected_pairs,
            )
        else:
            single_key = "judge_A" if judge_a_responses is not None else "judge_B"
            single_resp = judge_a_responses if judge_a_responses is not None else judge_b_responses
            assert single_resp is not None
            per_cell = {
                c: score_validated_judge_rankings(
                    queries_meta_dicts,
                    docs_meta,
                    rem_map,
                    single_resp,
                    dict(cell_r),
                    tau_unresolved=tau_unresolved,
                    judging_order=judging_order,
                    sealed_expected_pairs=sealed_expected_pairs,
                )
                for c, cell_r in rankings_doc_ids_by_cell.items()
            }
            report["judge_gates"] = {
                "epistemic_tier": "AI_PROXY_SINGLE_LLM",
                "HumanGraded-GoMate-nDCG@10": "NOT_PERFORMED",
                single_key: per_cell,
            }

    if enforce_clean_sys_modules:
        assert_zero_ml_imports()
    return report


def score_g4_from_files(
    *,
    rankings_path: Path | str,
    manifest_path: Path | str,
    queries_path: Path | str,
    output_path: Path | str | None = None,
    qrels_path: Path | str | None = None,
    removed_audit_spans_path: Path | str | None = None,
    strict_full_pool: bool = False,
    enforce_final50_matrix: bool = False,
    judge_a_path: Path | str | None = None,
    judge_b_path: Path | str | None = None,
    judging_order: str = "ORDER_A",
    expected_pairs_path: Path | str | None = None,
    docs_path: Path | str | None = None,
    tau_unresolved: float = 0.10,
    enforce_clean_sys_modules: bool = False,
) -> dict[str, Any]:
    """Load sealed files, verify SHA-256 and zero-ML imports, score G4, and optionally write report JSON."""
    assert_g4_package_zero_ml_imports()
    if enforce_clean_sys_modules:
        assert_zero_ml_imports()

    if qrels_path is None and judge_a_path is None and judge_b_path is None:
        raise ValueError(
            "EXTERNAL_LABELS_REQUIRED: must provide --qrels or --judge-a / --judge-b (no label self-generation)"
        )

    manifest, ranking_rows = load_sealed_rankings(rankings_path, manifest_path)
    query_specs, _ = load_query_manifest(queries_path, enforce_final50_matrix=enforce_final50_matrix)
    qrels = load_external_qrels(qrels_path) if qrels_path is not None else None
    removed_map = _load_removed_audit_spans(removed_audit_spans_path)
    docs_meta = _load_docs_metadata(docs_path)
    judge_a = _load_judge_responses_jsonl(judge_a_path) if judge_a_path is not None else None
    judge_b = _load_judge_responses_jsonl(judge_b_path) if judge_b_path is not None else None

    expected_pairs = None
    if expected_pairs_path is not None:
        raw_ep = json.loads(Path(expected_pairs_path).read_text(encoding="utf-8"))
        manifest_keys = {
            "expected_pairs_manifest_sha256",
            "judging_order",
            "query_manifest_sha256",
            "sanitized_v_corpus_sha256",
            "sealed_at_utc",
            "pair_count",
        }
        if isinstance(raw_ep, dict) and (manifest_keys & set(raw_ep.keys())):
            expected_pairs = verify_sealed_expected_pairs_manifest(raw_ep, expected_v_corpus_sha256=None)
        elif isinstance(raw_ep, dict) and "expected_pairs" in raw_ep:
            expected_pairs = [(p[0], p[1]) for p in raw_ep["expected_pairs"]]
        else:
            expected_pairs = [(p[0], p[1]) for p in raw_ep]

    report = score_g4(
        manifest=manifest,
        ranking_rows=ranking_rows,
        query_specs=query_specs,
        qrels=qrels,
        removed_audit_spans_by_doc=removed_map,
        docs_by_id=docs_meta,
        strict_full_pool=strict_full_pool,
        judge_a_responses=judge_a,
        judge_b_responses=judge_b,
        judging_order=judging_order,
        sealed_expected_pairs=expected_pairs,
        tau_unresolved=tau_unresolved,
        enforce_clean_sys_modules=enforce_clean_sys_modules,
    )

    if output_path is not None:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")

    return report


def main(argv: list[str] | None = None, *, enforce_clean_sys_modules: bool = True) -> int:
    if enforce_clean_sys_modules:
        try:
            assert_zero_ml_imports()
        except Exception as exc:
            print(f"G4_SCORER_ERROR: {exc}", file=sys.stderr)
            return 2
    parser = argparse.ArgumentParser(
        prog="w07_g4_scorer.scorer",
        description="Decoupled, zero-ML-import GOMATE W07 G4 Scorer",
    )
    parser.add_argument("--rankings", required=True, help="Path to g3_sealed_rankings_v1.jsonl")
    parser.add_argument("--manifest", required=True, help="Path to g3_sealed_rankings_v1_manifest.json")
    parser.add_argument("--qrels", default=None, help="Path to external qrels.jsonl")
    parser.add_argument("--queries", required=True, help="Path to queries.jsonl")
    parser.add_argument("--output", required=True, help="Path to output g4_report.json")
    parser.add_argument("--removed-audit-spans", default=None, help="Optional JSON mapping doc_id -> [[start, end], ...]")
    parser.add_argument("--strict-full-pool", action="store_true", help="Enforce Cert-1, Cert-2, Cert-3 == 1.00")
    parser.add_argument("--enforce-final50-matrix", action="store_true", help="Enforce 5x3 15-cell FINAL-50 lock")
    parser.add_argument("--judge-a", default=None, help="Optional Judge A responses JSONL")
    parser.add_argument("--judge-b", default=None, help="Optional Judge B responses JSONL")
    parser.add_argument("--judging-order", default="ORDER_A", choices=("ORDER_A", "ORDER_B"))
    parser.add_argument("--expected-pairs", default=None, help="Optional sealed expected pairs JSON")
    parser.add_argument("--docs", default=None, help="Optional corpus metadata JSON/JSONL for judge/decoy gates")

    args = parser.parse_args(argv)
    try:
        score_g4_from_files(
            rankings_path=args.rankings,
            manifest_path=args.manifest,
            queries_path=args.queries,
            output_path=args.output,
            qrels_path=args.qrels,
            removed_audit_spans_path=args.removed_audit_spans,
            strict_full_pool=args.strict_full_pool,
            enforce_final50_matrix=args.enforce_final50_matrix,
            judge_a_path=args.judge_a,
            judge_b_path=args.judge_b,
            judging_order=args.judging_order,
            expected_pairs_path=args.expected_pairs,
            docs_path=args.docs,
            enforce_clean_sys_modules=enforce_clean_sys_modules,
        )
    except Exception as exc:
        print(f"G4_SCORER_ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
