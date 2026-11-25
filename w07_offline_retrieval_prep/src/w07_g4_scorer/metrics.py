"""G4 evaluation metrics: coupled [nDCG_L, nDCG_U], enclosure, span hits, secondary, and unanswerable safety."""

from __future__ import annotations

import itertools
import math
import re
from collections.abc import Mapping, Sequence
from typing import Any

from w07_g4_scorer.contracts import (
    GAIN_MAP,
    Cert4Status,
    QrelRecord,
    RankingRow,
    RelevanceState,
    intervals_contain,
    merge_intervals,
    subtract_intervals,
)
from w07_g4_scorer.query_manifest import QuerySpec

_CONFLICT_TAG_RE = re.compile(r"\[SUPPRESSED_FACT_CONFLICT[^\]]*\]|\bFC-00[12]\b")


def dcg_at_10(gains: Sequence[int]) -> float:
    return sum(g / math.log2(idx + 2) for idx, g in enumerate(gains[:10]) if g > 0)


def idcg_at_10(all_gains: Sequence[int]) -> float:
    top_ideal = sorted(all_gains, reverse=True)[:10]
    return dcg_at_10(top_ideal)


def conservative_ndcg10_enclosure(
    top10_doc_ids: Sequence[str],
    all_doc_ids: Sequence[str],
    known_gains: Mapping[str, int],
    zero_capped_doc_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Conservative enclosure [D_L / I_U, min(1.0, D_U / I_L)] respecting zero-capped ineligible lures."""
    zcap = zero_capped_doc_ids or set()
    eff_known = dict(known_gains)
    for d in zcap:
        eff_known[d] = 0
    top10 = list(top10_doc_ids[:10])
    all_docs_unique = list(dict.fromkeys(all_doc_ids))
    d_l = dcg_at_10([eff_known.get(d, 0) for d in top10])
    d_u = dcg_at_10([eff_known.get(d, 3) for d in top10])
    i_l = idcg_at_10([eff_known.get(d, 0) for d in all_docs_unique])
    i_u = idcg_at_10([eff_known.get(d, 3) for d in all_docs_unique])
    unresolved = [d for d in all_docs_unique if d not in eff_known]
    if i_u == 0.0 and len(unresolved) == 0:
        return {"status": "ZERO_IDCG_COMPLETE", "lower": 0.0, "upper": 0.0, "i_l": 0.0, "i_u": 0.0}
    if i_l == 0.0:
        return {"status": "ZERO_IDCG_INCOMPLETE", "lower": 0.0, "upper": 1.0, "i_l": 0.0, "i_u": i_u}
    return {
        "status": "BOUNDED_OR_EXACT",
        "lower": d_l / i_u,
        "upper": min(1.0, d_u / i_l),
        "i_l": i_l,
        "i_u": i_u,
        "d_l": d_l,
        "d_u": d_u,
    }


def exact_ndcg10_bounds(
    top10_doc_ids: Sequence[str],
    all_doc_ids: Sequence[str],
    known_gains: Mapping[str, int],
    zero_idcg_value: float = 0.0,
    zero_capped_doc_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Exact finite-domain sharp optimizer over g in {0, 1, 3}^|U_q| (respecting zero-capped ineligible docs)."""
    eff_known = dict(known_gains)
    if zero_capped_doc_ids:
        for d in zero_capped_doc_ids:
            eff_known[d] = 0

    all_docs_unique = list(dict.fromkeys(all_doc_ids))
    top10 = list(top10_doc_ids[:10])
    top10_set = set(top10)
    u_top = [d for d in dict.fromkeys(top10) if d not in eff_known]
    u_out = [d for d in all_docs_unique if d not in eff_known and d not in top10_set]
    known_all_gains = [eff_known[d] for d in all_docs_unique if d in eff_known]

    if not u_top and not u_out:
        dcg = dcg_at_10([eff_known[d] for d in top10])
        idcg = idcg_at_10(known_all_gains)
        if idcg == 0.0:
            return {"status": "ZERO_IDCG_COMPLETE", "lower": zero_idcg_value, "upper": zero_idcg_value}
        val = dcg / idcg
        return {"status": "EXACT", "lower": val, "upper": val}

    min_val = float("inf")
    max_val = float("-inf")
    zero_idcg_possible = False

    for g_top_tuple in itertools.product((0, 1, 3), repeat=len(u_top)):
        g_top_map = dict(zip(u_top, g_top_tuple))
        dcg = dcg_at_10([eff_known[d] if d in eff_known else g_top_map[d] for d in top10])
        base_gains = known_all_gains + list(g_top_tuple)

        idcg_max = idcg_at_10(base_gains + [3] * len(u_out))
        if idcg_max == 0.0:
            zero_idcg_possible = True
            cand_low = zero_idcg_value
        else:
            cand_low = dcg / idcg_max
        min_val = min(min_val, cand_low)
        max_val = max(max_val, cand_low)

        idcg_min = idcg_at_10(base_gains + [0] * len(u_out))
        if idcg_min == 0.0:
            zero_idcg_possible = True
            cand_high = zero_idcg_value
        else:
            cand_high = dcg / idcg_min
        min_val = min(min_val, cand_high)
        max_val = max(max_val, cand_high)

    status = (
        "ZERO_IDCG_INCOMPLETE"
        if zero_idcg_possible
        else ("EXACT" if abs(max_val - min_val) <= 1e-15 else "BOUNDED")
    )
    if zero_idcg_possible:
        return {
            "status": status,
            "lower": 0.0,
            "upper": 1.0,
            "value_conditioned_lower": min_val,
            "value_conditioned_upper": max_val,
        }
    return {"status": status, "lower": min_val, "upper": max_val}


def coupled_ndcg10_bounds(
    top10_doc_ids: Sequence[str],
    all_doc_ids: Sequence[str],
    qrels_for_q: Mapping[str, QrelRecord],
    *,
    strict_cert2: bool = True,
) -> dict[str, Any]:
    """Compute coupled [nDCG_L@10, nDCG_U@10] for a query under Cert-2 and IDCG_L/U."""
    top10 = list(top10_doc_ids[:10])
    doc_universe = list(dict.fromkeys(list(all_doc_ids) + top10))
    known_gains: dict[str, int] = {}
    for did in doc_universe:
        rec = qrels_for_q.get(did)
        if rec is not None and rec.label in GAIN_MAP:
            known_gains[did] = GAIN_MAP[rec.label]

    unresolved_top10 = [did for did in top10 if did not in known_gains]
    if strict_cert2 and unresolved_top10:
        raise ValueError(f"CERT2_INCOMPLETE_UNRESOLVED_TOP10: {unresolved_top10}")

    if unresolved_top10:
        cons = conservative_ndcg10_enclosure(top10, doc_universe, known_gains)
        ex = exact_ndcg10_bounds(top10, doc_universe, known_gains)
        return {
            "dcg": None,
            "idcg_l": cons["i_l"],
            "idcg_u": cons["i_u"],
            "ndcg_l": ex["lower"],
            "ndcg_u": ex["upper"],
            "conservative_lower": cons["lower"],
            "conservative_upper": cons["upper"],
            "status": ex["status"],
        }

    dcg = dcg_at_10([known_gains[did] for did in top10])
    z_count = sum(1 for did in doc_universe if did not in known_gains)
    known_list = [known_gains[did] for did in doc_universe if did in known_gains]
    idcg_l = idcg_at_10(known_list + [0] * z_count)
    idcg_u = idcg_at_10(known_list + [3] * z_count)

    if z_count == 0 and idcg_u == 0.0:
        return {
            "dcg": dcg,
            "idcg_l": 0.0,
            "idcg_u": 0.0,
            "ndcg_l": 0.0,
            "ndcg_u": 0.0,
            "status": Cert4Status.ZERO_POSITIVE_EXACT.value,
        }
    if idcg_l == 0.0 and idcg_u > 0.0:
        raise ValueError("INVALID_UNRESOLVED: IDCG_L == 0.0 < IDCG_U")

    # P2-03 edge case: if DCG == 0 < IDCG_L, nDCG_L == nDCG_U == 0.0 while Cert-4 remains BOUNDED_NOT_EXACT.
    if dcg == 0.0:
        ndcg_l = 0.0
        ndcg_u = 0.0
    else:
        ndcg_l = dcg / idcg_u
        ndcg_u = dcg / idcg_l

    status = (
        Cert4Status.EXACT_CERTIFIED.value
        if abs(idcg_u - idcg_l) <= 1e-12
        else Cert4Status.BOUNDED_NOT_EXACT.value
    )
    return {
        "dcg": dcg,
        "idcg_l": idcg_l,
        "idcg_u": idcg_u,
        "ndcg_l": ndcg_l,
        "ndcg_u": ndcg_u,
        "status": status,
    }


def coupled_pairwise_contrast_bounds(
    dcg_a_by_q: Mapping[str, float],
    dcg_b_by_q: Mapping[str, float],
    idcg_l_by_q: Mapping[str, float],
    idcg_u_by_q: Mapping[str, float],
) -> dict[str, Any]:
    """Compute coupled Delta_min(A, B) and Delta_max(A, B) sharing I_q across systems A and B."""
    qids = list(dcg_a_by_q.keys())
    if not qids or set(qids) != set(dcg_b_by_q.keys()):
        raise ValueError("Mismatched query sets for coupled pairwise contrast")

    d_low_vec: list[float] = []
    d_high_vec: list[float] = []
    for qid in qids:
        il = idcg_l_by_q[qid]
        iu = idcg_u_by_q[qid]
        if il <= 0.0 or iu <= 0.0:
            raise ValueError(f"Non-positive IDCG bounds on query {qid!r}: I_L={il}, I_U={iu}")
        diff_dcg = dcg_a_by_q[qid] - dcg_b_by_q[qid]
        c1 = diff_dcg / il
        c2 = diff_dcg / iu
        d_low_vec.append(min(c1, c2))
        d_high_vec.append(max(c1, c2))

    return {
        "qids": qids,
        "delta_min": sum(d_low_vec) / float(len(d_low_vec)),
        "delta_max": sum(d_high_vec) / float(len(d_high_vec)),
        "d_low_vec": d_low_vec,
        "d_high_vec": d_high_vec,
    }


def _non_ws_len_in_intervals(text: str, intervals: Sequence[tuple[int, int]]) -> int:
    total = 0
    n = len(text)
    for a, b in intervals:
        hi = min(b, n)
        for idx in range(max(0, a), hi):
            if not text[idx].isspace():
                total += 1
    return total


def span_hit_matches(
    row_s_spans: Sequence[tuple[int, int]],
    target_s_spans: Sequence[tuple[int, int]],
    removed_r_audit: Sequence[tuple[int, int]],
    *,
    is_split_atomic_gt128: bool = False,
    canonical_text_S: str | None = None,
    has_contradiction: bool = False,
) -> bool:
    """Evaluate single target evidence span(s) against row C_full or C_vis S-intervals."""
    row_clean = merge_intervals(row_s_spans)
    rem_clean = merge_intervals(removed_r_audit)

    # CE-08 outer-hull rejection: any overlap with deleted R_AUDIT intervals fails immediately
    for a, b in row_clean:
        for ra, rb in rem_clean:
            if max(a, ra) < min(b, rb):
                return False

    g_sub = subtract_intervals(target_s_spans, rem_clean)
    if not g_sub:
        return False

    if not is_split_atomic_gt128:
        return intervals_contain(row_clean, g_sub)

    if canonical_text_S is None:
        raise ValueError("canonical_text_S is required when is_split_atomic_gt128=True")
    if has_contradiction:
        return False

    missing = subtract_intervals(g_sub, row_clean)
    covered = subtract_intervals(g_sub, missing)
    denom = _non_ws_len_in_intervals(canonical_text_S, g_sub)
    if denom == 0:
        return False
    numer = _non_ws_len_in_intervals(canonical_text_S, covered)
    return (numer / float(denom)) >= 0.80 - 1e-12


def _normalize_or_alternatives(group: Any) -> list[dict[str, Any]]:
    if isinstance(group, dict):
        if "or" in group and isinstance(group["or"], list):
            alts = group["or"]
        elif "alternatives" in group and isinstance(group["alternatives"], list):
            alts = group["alternatives"]
        else:
            alts = [group]
    elif isinstance(group, list):
        alts = group
    else:
        raise ValueError(f"Malformed evidence facet group: {group!r}")

    normalized: list[dict[str, Any]] = []
    for alt in alts:
        if not isinstance(alt, dict):
            raise ValueError(f"Malformed OR alternative: {alt!r}")
        doc_id = alt.get("document_id", alt.get("doc_id"))
        raw_spans = alt.get("s_spans", alt.get("spans", alt.get("evidence_s_spans")))
        if type(doc_id) is not str or not doc_id.strip():
            raise ValueError(f"Facet OR alternative missing document_id: {alt!r}")
        if not isinstance(raw_spans, list) or not raw_spans:
            raise ValueError(f"Facet OR alternative missing s_spans: {alt!r}")
        spans = merge_intervals(raw_spans)
        normalized.append(
            {
                "document_id": doc_id,
                "s_spans": spans,
                "is_split_atomic_gt128": bool(alt.get("is_split_atomic_gt128", False)),
                "has_contradiction": bool(alt.get("has_contradiction", False)),
            }
        )
    return normalized


def _row_field(row: RankingRow | Mapping[str, Any], name: str, default: Any = None) -> Any:
    if isinstance(row, Mapping):
        return row.get(name, default)
    return getattr(row, name, default)


def _as_span_tuples(raw_spans: Any) -> list[tuple[int, int]]:
    if not raw_spans:
        return []
    if not isinstance(raw_spans, (list, tuple)):
        raise ValueError(f"Malformed spans sequence: {raw_spans!r}")
    return merge_intervals(raw_spans)


def compute_span_hits_at_10(
    top10_rows: Sequence[RankingRow | Mapping[str, Any]],
    query_spec: QuerySpec,
    qrels_for_q: Mapping[str, QrelRecord],
    removed_audit_spans_by_doc: Mapping[str, Sequence[tuple[int, int]]] | None = None,
    docs_by_id: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, float | None]:
    """Compute EvidenceSpanHit@10 (C_full) and VisibleEvidenceSpanHit@10 (C_vis) across AND/OR facet groups."""
    rem_map = removed_audit_spans_by_doc or {}
    row_by_doc: dict[str, RankingRow | Mapping[str, Any]] = {}
    for row in top10_rows[:10]:
        did = _row_field(row, "document_id")
        if did not in row_by_doc:
            row_by_doc[did] = row

    groups: list[list[dict[str, Any]]] = []
    if query_spec.required_evidence_facets:
        for grp in query_spec.required_evidence_facets:
            groups.append(_normalize_or_alternatives(grp))
    else:
        pos_alts: list[dict[str, Any]] = []
        for did, rec in sorted(qrels_for_q.items()):
            if rec.label in (RelevanceState.REL_1, RelevanceState.REL_2) and rec.evidence_s_spans:
                pos_alts.append(
                    {
                        "document_id": did,
                        "s_spans": list(rec.evidence_s_spans),
                        "is_split_atomic_gt128": False,
                        "has_contradiction": False,
                    }
                )
        if pos_alts:
            groups.append(pos_alts)

    if not groups:
        return {"evidence_span_hit_at_10": None, "visible_evidence_span_hit_at_10": None}

    def _all_groups_satisfied(use_vis: bool) -> bool:
        for alts in groups:
            grp_hit = False
            for alt in alts:
                did = alt["document_id"]
                row = row_by_doc.get(did)
                if row is None:
                    continue
                rem = rem_map.get(did, [])
                raw_row_spans = _row_field(row, "c_vis_s_spans" if use_vis else "c_full_s_spans", ())
                row_spans = _as_span_tuples(raw_row_spans)
                canon_s = docs_by_id[did].get("canonical_text_S") if (docs_by_id and did in docs_by_id) else None
                if span_hit_matches(
                    row_spans,
                    alt["s_spans"],
                    rem,
                    is_split_atomic_gt128=alt["is_split_atomic_gt128"],
                    canonical_text_S=canon_s,
                    has_contradiction=alt["has_contradiction"],
                ):
                    grp_hit = True
                    break
            if not grp_hit:
                return False
        return True

    return {
        "evidence_span_hit_at_10": 1.0 if _all_groups_satisfied(use_vis=False) else 0.0,
        "visible_evidence_span_hit_at_10": 1.0 if _all_groups_satisfied(use_vis=True) else 0.0,
    }


def mrr_at_10(top10_doc_ids: Sequence[str], qrels_for_q: Mapping[str, QrelRecord]) -> float:
    for rank, did in enumerate(top10_doc_ids[:10], start=1):
        rec = qrels_for_q.get(did)
        if rec is not None and rec.label in (RelevanceState.REL_1, RelevanceState.REL_2):
            return 1.0 / float(rank)
    return 0.0


def hit_rate_at_10(top10_doc_ids: Sequence[str], qrels_for_q: Mapping[str, QrelRecord]) -> float:
    for did in top10_doc_ids[:10]:
        rec = qrels_for_q.get(did)
        if rec is not None and rec.label in (RelevanceState.REL_1, RelevanceState.REL_2):
            return 1.0
    return 0.0


def recall_at_k(
    top_doc_ids: Sequence[str],
    qrels_for_q: Mapping[str, QrelRecord],
    k: int = 10,
) -> float | None:
    positives = {
        did for did, rec in qrels_for_q.items() if rec.label in (RelevanceState.REL_1, RelevanceState.REL_2)
    }
    if not positives:
        return None
    top_k = set(top_doc_ids[:k])
    return len(top_k & positives) / float(len(positives))


def compute_unanswerable_metrics(
    top10_rows: Sequence[RankingRow | Mapping[str, Any]],
    query_spec: QuerySpec,
    qrels_for_q: Mapping[str, QrelRecord],
    docs_by_id: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, float]:
    """Compute D06.4 Q_unans exposure metrics (zero CorrectAbstentionRate or G5 fields)."""
    top10 = list(top10_rows[:10])
    any_result = 1.0 if len(top10) >= 1 else 0.0

    target_pois = set(query_spec.target_poi_ids)
    decoy_hit = False
    lure_count = 0

    for row in top10:
        did = _row_field(row, "document_id")
        assembled_text = _row_field(row, "assembled_text", "")
        doc_meta = docs_by_id.get(did, {}) if docs_by_id else {}
        doc_poi = doc_meta.get("poi_id")
        if doc_poi is not None and doc_poi in target_pois:
            decoy_hit = True
        if bool(doc_meta.get("has_conflict")) or (_CONFLICT_TAG_RE.search(assembled_text) is not None):
            decoy_hit = True

        rec = qrels_for_q.get(did)
        if rec is not None and rec.label == RelevanceState.REL_0 and rec.plausible_unsupported_lure == 1:
            lure_count += 1

    return {
        "any_result_at_10": any_result,
        "same_poi_or_conflict_decoy_at_10": 1.0 if decoy_hit else 0.0,
        "false_support_exposure_at_10": 1.0 if lure_count >= 1 else 0.0,
        "false_support_count_at_10": lure_count / 10.0,
    }
