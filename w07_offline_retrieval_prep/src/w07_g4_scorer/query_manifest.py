"""D01 5x3 matrix quotas, DEV isolation, and AUTO-EVAL-01 v0.4.2 Step S0 zero-default metadata validator."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ANNEX_G15_CELL_QUOTAS: dict[tuple[str, str], int] = {
    ("S1_STRUCTURED_FACT", "Hà Nội"): 4,
    ("S1_STRUCTURED_FACT", "Đà Nẵng"): 4,
    ("S1_STRUCTURED_FACT", "Hạ Long"): 4,
    ("S2_NARRATIVE_ADVISORY", "Hà Nội"): 4,
    ("S2_NARRATIVE_ADVISORY", "Đà Nẵng"): 4,
    ("S2_NARRATIVE_ADVISORY", "Hạ Long"): 4,
    ("S3_MULTI_EVIDENCE", "Hà Nội"): 3,
    ("S3_MULTI_EVIDENCE", "Đà Nẵng"): 3,
    ("S3_MULTI_EVIDENCE", "Hạ Long"): 2,
    ("S4_CROSS_LINGUAL_VI_TO_EN", "Hà Nội"): 4,
    ("S4_CROSS_LINGUAL_VI_TO_EN", "Đà Nẵng"): 3,
    ("S4_CROSS_LINGUAL_VI_TO_EN", "Hạ Long"): 1,
    ("S5_UNANSWERABLE_OR_UNSTABLE", "Hà Nội"): 2,
    ("S5_UNANSWERABLE_OR_UNSTABLE", "Đà Nẵng"): 3,
    ("S5_UNANSWERABLE_OR_UNSTABLE", "Hạ Long"): 5,
}

ANNEX_G15_STRATA_QUOTAS: dict[str, int] = {
    "S1_STRUCTURED_FACT": 12,
    "S2_NARRATIVE_ADVISORY": 12,
    "S3_MULTI_EVIDENCE": 8,
    "S4_CROSS_LINGUAL_VI_TO_EN": 8,
    "S5_UNANSWERABLE_OR_UNSTABLE": 10,
}

ANNEX_G15_CITY_QUOTAS: dict[str, int] = {
    "Hà Nội": 17,
    "Đà Nẵng": 17,
    "Hạ Long": 16,
}

ALLOWED_SCOPE_MODES: frozenset[str] = frozenset({"STRICT_TARGET_POI", "CITY_MULTI_POI"})

ALLOWED_QUERY_POLARITIES: frozenset[str] = frozenset(
    {
        "AFFIRMATIVE_FACT_NEED",
        "BOOLEAN_ELIGIBILITY_OR_POLICY_CHECK",
        "NEGATIVE_CONSTRAINT_OR_EXCLUSION_NEED",
    }
)

ALLOWED_PRE_RANK_ANSWERABILITY: frozenset[str] = frozenset({"ANSWERABLE", "UNANSWERABLE"})
ALLOWED_QUESTION_ORIGINS: frozenset[str] = frozenset(
    {
        "INDEPENDENT_HUMAN",
        "SYNTHETIC_DISCLOSED",
        "AI_GENERATED_NO_HUMAN_REVIEW",
    }
)


def _validate_query_origin_and_exposure(
    row: dict[str, Any],
    *,
    qid: str,
    split: str,
    exposure: str,
    owner_synthetic_final_approved: bool = False,
    route2_ai_proxy_approved: bool = False,
) -> None:
    if split == "FINAL" and exposure != "NO":
        raise ValueError(f"FINAL query {qid!r} violates corpus-blind creator_exposure_to_corpus='NO'")
    origin = row.get("question_origin")
    if type(origin) is not str or origin not in ALLOWED_QUESTION_ORIGINS:
        raise ValueError(f"Query {qid!r} missing valid question_origin: {origin!r}")
    if split == "FINAL":
        if origin == "SYNTHETIC_DISCLOSED" and not owner_synthetic_final_approved:
            raise ValueError(f"SYNTHETIC_DISCLOSED forbidden in FINAL without signed exception: {qid!r}")
        if origin == "AI_GENERATED_NO_HUMAN_REVIEW":
            if not route2_ai_proxy_approved:
                raise ValueError(
                    f"AI_GENERATED_NO_HUMAN_REVIEW forbidden in FINAL without approved Route 2 authorization: {qid!r}"
                )
            if row.get("human_ground_truth") is not False:
                raise ValueError(
                    f"AI_GENERATED_NO_HUMAN_REVIEW query {qid!r} requires explicit human_ground_truth=False"
                )
        if route2_ai_proxy_approved:
            if origin == "INDEPENDENT_HUMAN":
                raise ValueError(f"FALSE_HUMAN_ORIGIN_UNDER_ROUTE2_AI_PROXY on {qid!r}: got {origin!r}")
            if row.get("human_ground_truth") is True:
                raise ValueError(f"FALSE_HUMAN_GROUND_TRUTH_CLAIM_UNDER_ROUTE2 on {qid!r}")


@dataclass(frozen=True)
class QuerySpec:
    query_id: str
    query_text: str
    split: str
    creator_exposure_to_corpus: str
    question_origin: str
    query_family: str
    target_city: str
    pre_rank_answerability: str
    scope_mode: str
    target_poi_ids: tuple[str, ...]
    query_intent_polarity: str
    requested_facet_keywords: tuple[str, ...]
    fact_cluster_id: str
    required_evidence_facets: tuple[Any, ...] | None = None


def _invalid_input_result(
    error_code: str,
    raw_grade: Any = None,
    flags: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "state": "INVALID_INPUT",
        "error_code": error_code,
        "confirmed_gain": 0,
        "max_admissible_gain": 0,
        "unresolved": True,
        "flags": list(flags or []),
        "audit_trail": {
            "raw_judge_grade": raw_grade,
            "disposition": "PIPELINE_ABORT_INVALID_INPUT",
            "error_code": error_code,
        },
    }


def validate_sealed_query_metadata(
    query_meta: Any,
    approved_pois_by_id: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Fail-closed upfront Step S0 validator for sealed query metadata (AUTO-R07).

    Returns None when valid, or an INVALID_INPUT dict when invalid. Never raises exceptions,
    never defaults scope_mode or query_intent_polarity (legacy 'polarity' alias retired),
    and validates list elements before constructing sets so unhashable elements never cause TypeError.
    """
    if type(query_meta) is not dict:
        return _invalid_input_result("INVALID_QUERY_META_TYPE")

    tc = query_meta.get("target_city")
    if type(tc) is not str or tc not in ANNEX_G15_CITY_QUOTAS:
        return _invalid_input_result("INVALID_OR_UNKNOWN_TARGET_CITY")

    sm = query_meta.get("scope_mode")
    if type(sm) is not str or sm not in ALLOWED_SCOPE_MODES:
        return _invalid_input_result("INVALID_OR_UNKNOWN_SCOPE_MODE")

    if "target_poi_ids" not in query_meta:
        return _invalid_input_result("MISSING_TARGET_POI_IDS")
    t_pids = query_meta["target_poi_ids"]
    if type(t_pids) is not list:
        return _invalid_input_result("MALFORMED_TARGET_POI_IDS_NOT_LIST")

    seen_pids: set[str] = set()
    for pid in t_pids:
        if type(pid) is not str or not pid.strip() or pid != pid.strip():
            return _invalid_input_result("MALFORMED_TARGET_POI_ID_ELEMENT")
        if pid in seen_pids:
            return _invalid_input_result("DUPLICATE_TARGET_POI_ID_ELEMENT")
        seen_pids.add(pid)

    if sm == "STRICT_TARGET_POI" and len(t_pids) == 0:
        return _invalid_input_result("EMPTY_TARGET_POI_IDS_FOR_STRICT_SCOPE")
    if sm == "CITY_MULTI_POI" and len(t_pids) == 1:
        return _invalid_input_result("SINGLE_TARGET_POI_MUST_USE_STRICT_SCOPE")

    if approved_pois_by_id is not None:
        if type(approved_pois_by_id) is not dict or len(approved_pois_by_id) == 0:
            return _invalid_input_result("INVALID_APPROVED_POIS_REGISTRY")
        for pid in t_pids:
            poi_rec = approved_pois_by_id.get(pid)
            if type(poi_rec) is not dict:
                return _invalid_input_result("UNAPPROVED_TARGET_POI_ID")
            if poi_rec.get("city") != tc:
                return _invalid_input_result("TARGET_POI_CITY_MISMATCH")

    pol = query_meta.get("query_intent_polarity")
    if type(pol) is not str or pol not in ALLOWED_QUERY_POLARITIES:
        return _invalid_input_result("MISSING_OR_INVALID_QUERY_INTENT_POLARITY")

    if "requested_facet_keywords" not in query_meta:
        return _invalid_input_result("MISSING_REQUESTED_FACET_KEYWORDS")
    rfk = query_meta["requested_facet_keywords"]
    if type(rfk) is not list or len(rfk) == 0:
        return _invalid_input_result("INVALID_OR_EMPTY_REQUESTED_FACET_KEYWORDS")
    for kw in rfk:
        if type(kw) is not str or not kw.strip():
            return _invalid_input_result("MALFORMED_REQUESTED_FACET_KEYWORD_ELEMENT")

    if "pre_rank_answerability" in query_meta:
        ans = query_meta["pre_rank_answerability"]
        if type(ans) is not str or ans not in ALLOWED_PRE_RANK_ANSWERABILITY:
            return _invalid_input_result("INVALID_PRE_RANK_ANSWERABILITY")

    return None


def validate_final50_strata_and_city_quota(
    rows: list[dict[str, Any]],
    approved_pois_by_id: dict[str, dict[str, Any]] | None = None,
    *,
    owner_synthetic_final_approved: bool = False,
    route2_ai_proxy_approved: bool = False,
) -> dict[str, Any]:
    """Enforce full Annex G1.5 v0.2.1 5x3 (15-cell) matrix, unique query_ids, answerability, & Step S0 metadata."""
    if type(rows) is not list or len(rows) != 50:
        raise ValueError(
            f"Expected list of 50 FINAL queries, got {len(rows) if type(rows) is list else type(rows).__name__}"
        )

    if approved_pois_by_id is not None and (type(approved_pois_by_id) is not dict or len(approved_pois_by_id) == 0):
        raise ValueError("Approved W07 POIs registry is empty or invalid")

    seen_qids: set[str] = set()
    seen_clusters: set[tuple[str, str]] = set()
    cell_counts: Counter[tuple[str, str]] = Counter()
    strata_counts: Counter[str] = Counter()
    city_counts: Counter[str] = Counter()
    q_ans_ids: list[str] = []
    q_unans_ids: list[str] = []

    for idx, r in enumerate(rows):
        if type(r) is not dict:
            raise ValueError(f"Row {idx} in FINAL 50 manifest is not a dict")
        qid = r.get("query_id")
        if type(qid) is not str or not qid.strip() or qid != qid.strip():
            raise ValueError(f"Row {idx} has missing or malformed query_id: {qid!r}")
        if qid in seen_qids:
            raise ValueError(f"Duplicate query_id in FINAL 50 manifest: {qid!r}")
        seen_qids.add(qid)

        fam = r.get("query_family")
        if type(fam) is not str or fam not in ANNEX_G15_STRATA_QUOTAS:
            raise ValueError(f"Invalid query_family on {qid!r}: {fam!r}")

        ans = r.get("pre_rank_answerability")
        if type(ans) is not str or ans not in ALLOWED_PRE_RANK_ANSWERABILITY:
            raise ValueError(f"Invalid pre_rank_answerability on {qid!r}: {ans!r}")
        expected_ans = "UNANSWERABLE" if fam == "S5_UNANSWERABLE_OR_UNSTABLE" else "ANSWERABLE"
        if ans != expected_ans:
            raise ValueError(f"Stratum-answerability mismatch on {qid!r}: {fam} requires {expected_ans}, got {ans!r}")

        split = r.get("split")
        if split != "FINAL":
            raise ValueError(f"FINAL 50 row {qid!r} must have split='FINAL', got {split!r}")
        exposure = r.get("creator_exposure_to_corpus")
        if type(exposure) is not str or not exposure.strip():
            raise ValueError(f"FINAL query {qid!r} missing creator_exposure_to_corpus")
        _validate_query_origin_and_exposure(
            r,
            qid=qid,
            split=split,
            exposure=exposure,
            owner_synthetic_final_approved=owner_synthetic_final_approved,
            route2_ai_proxy_approved=route2_ai_proxy_approved,
        )

        meta_err = validate_sealed_query_metadata(r, approved_pois_by_id=approved_pois_by_id)
        if meta_err is not None:
            raise ValueError(f"Invalid FINAL query metadata on {qid!r}: {meta_err['error_code']}")

        fc_id = r.get("fact_cluster_id")
        if type(fc_id) is not str or not fc_id.strip():
            raise ValueError(f"Missing or invalid fact_cluster_id on {qid!r}")

        city = r["target_city"]
        cell_counts[(fam, city)] += 1
        strata_counts[fam] += 1
        city_counts[city] += 1

        if ans == "ANSWERABLE":
            scope_keys = r["target_poi_ids"] if len(r["target_poi_ids"]) > 0 else [f"CITY:{city}"]
            for sk in scope_keys:
                ckey = (sk, fc_id.strip())
                if ckey in seen_clusters:
                    raise ValueError(f"Duplicate atomic (scope, fact_cluster_id) in Q_ans on {qid!r}: {ckey}")
                seen_clusters.add(ckey)
            q_ans_ids.append(qid)
        else:
            q_unans_ids.append(qid)

    mismatched_cells = {
        f"{fam}::{city}": {"actual": cell_counts.get((fam, city), 0), "expected": exp_n}
        for (fam, city), exp_n in ANNEX_G15_CELL_QUOTAS.items()
        if cell_counts.get((fam, city), 0) != exp_n
    }
    if mismatched_cells or set(cell_counts.keys()) != set(ANNEX_G15_CELL_QUOTAS.keys()):
        raise ValueError(f"5x3 cell matrix mismatch vs Annex G1.5 v0.2.1: {mismatched_cells}")

    if dict(strata_counts) != ANNEX_G15_STRATA_QUOTAS:
        raise ValueError(f"Strata quota mismatch vs Annex G1.5 v0.2.1: {dict(strata_counts)}")
    if dict(city_counts) != ANNEX_G15_CITY_QUOTAS:
        raise ValueError(f"City quota mismatch vs Annex G1.5 v0.2.1: {dict(city_counts)}")

    return {
        "cell_counts": {f"{fam}::{city}": cell_counts[(fam, city)] for (fam, city) in ANNEX_G15_CELL_QUOTAS},
        "strata_counts": dict(strata_counts),
        "city_counts": dict(city_counts),
        "halong_s4_count": cell_counts[("S4_CROSS_LINGUAL_VI_TO_EN", "Hạ Long")],
        "q_ans_count": len(q_ans_ids),
        "q_unans_count": len(q_unans_ids),
    }


def validate_pre_g3_query_manifest(
    rows: list[dict[str, Any]],
    approved_pois_by_id: dict[str, dict[str, Any]] | None = None,
    *,
    owner_synthetic_final_approved: bool = False,
    route2_ai_proxy_approved: bool = False,
) -> dict[str, Any]:
    """Top-level Pre-G3 query lock validator enforcing full 5x3 matrix + metadata on FINAL 50."""
    res = validate_final50_strata_and_city_quota(
        rows,
        approved_pois_by_id=approved_pois_by_id,
        owner_synthetic_final_approved=owner_synthetic_final_approved,
        route2_ai_proxy_approved=route2_ai_proxy_approved,
    )
    q_ans = [r["query_id"] for r in rows if r["pre_rank_answerability"] == "ANSWERABLE"]
    q_unans = [r["query_id"] for r in rows if r["pre_rank_answerability"] == "UNANSWERABLE"]
    return {"q_ans": q_ans, "q_unans": q_unans, "matrix_summary": res}


def validate_dev_isolation(
    dev_rows: list[dict[str, Any]],
    final_rows: list[dict[str, Any]],
    *,
    max_dev_queries: int = 10,
) -> dict[str, Any]:
    """Verify DEV-SET-V1 <= 10 queries and strictly disjoint from FINAL-50."""
    if type(dev_rows) is not list or type(final_rows) is not list:
        raise ValueError("dev_rows and final_rows must be lists")
    if len(dev_rows) > max_dev_queries:
        raise ValueError(f"DEV set exceeds maximum {max_dev_queries} queries: got {len(dev_rows)}")

    final_qids = {r.get("query_id") for r in final_rows if isinstance(r, dict)}
    final_texts = {
        str(r.get("query_text", "")).strip().lower() for r in final_rows if isinstance(r, dict) and r.get("query_text")
    }
    for idx, dr in enumerate(dev_rows):
        if type(dr) is not dict:
            raise ValueError(f"DEV row {idx} is not a dict")
        if dr.get("split") == "FINAL":
            raise ValueError(f"DEV row {dr.get('query_id')!r} cannot have split='FINAL'")
        qid = dr.get("query_id")
        if qid in final_qids:
            raise ValueError(f"DEV_FINAL_ID_OVERLAP: {qid!r} appears in both DEV and FINAL")
        qtxt = str(dr.get("query_text", "")).strip().lower()
        if qtxt and qtxt in final_texts:
            raise ValueError(f"DEV_FINAL_TEXT_OVERLAP: query_text for {qid!r} overlaps FINAL")

    return {"dev_count": len(dev_rows), "final_count": len(final_rows), "disjoint": True}


def load_query_manifest(
    queries_path: Path | str,
    *,
    enforce_final50_matrix: bool = False,
    approved_pois_by_id: dict[str, dict[str, Any]] | None = None,
    owner_synthetic_final_approved: bool = False,
    route2_ai_proxy_approved: bool = False,
) -> tuple[list[QuerySpec], dict[str, Any]]:
    """Load and validate queries.jsonl, enforcing Step S0 metadata and optional 5x3 FINAL-50 lock."""
    q_path = Path(queries_path)
    if not q_path.is_file():
        raise FileNotFoundError(f"Queries file not found: {q_path}")

    raw_text = q_path.read_text(encoding="utf-8")
    stripped = raw_text.lstrip()
    if not stripped:
        raise ValueError("EMPTY_QUERIES_MANIFEST")

    rows: list[dict[str, Any]]
    if stripped.startswith("["):
        parsed = json.loads(raw_text)
        if type(parsed) is not list:
            raise ValueError("Queries JSON must be a list of objects")
        rows = parsed
    else:
        rows = [json.loads(ln) for ln in raw_text.splitlines() if ln.strip()]

    if not rows:
        raise ValueError("EMPTY_QUERIES_MANIFEST")

    if enforce_final50_matrix:
        pre_g3 = validate_pre_g3_query_manifest(
            rows,
            approved_pois_by_id=approved_pois_by_id,
            owner_synthetic_final_approved=owner_synthetic_final_approved,
            route2_ai_proxy_approved=route2_ai_proxy_approved,
        )
        summary = pre_g3["matrix_summary"]
    else:
        summary = {}

    seen_qids: set[str] = set()
    seen_clusters: set[tuple[str, str]] = set()
    specs: list[QuerySpec] = []
    q_ans_pre: list[str] = []
    q_unans_pre: list[str] = []

    for idx, r in enumerate(rows):
        if type(r) is not dict:
            raise ValueError(f"Query row {idx} is not a dict")
        qid = r.get("query_id")
        if type(qid) is not str or not qid.strip() or qid != qid.strip():
            raise ValueError(f"Row {idx} has missing or malformed query_id: {qid!r}")
        if qid in seen_qids:
            raise ValueError(f"Duplicate query_id: {qid!r}")
        seen_qids.add(qid)

        qtext = r.get("query_text")
        if type(qtext) is not str or not qtext.strip():
            raise ValueError(f"Invalid or missing query_text on {qid!r}")

        fam = r.get("query_family")
        if type(fam) is not str or fam not in ANNEX_G15_STRATA_QUOTAS:
            raise ValueError(f"Invalid query_family on {qid!r}: {fam!r}")

        ans = r.get("pre_rank_answerability")
        if type(ans) is not str or ans not in ALLOWED_PRE_RANK_ANSWERABILITY:
            raise ValueError(f"Invalid pre_rank_answerability on {qid!r}: {ans!r}")
        expected_ans = "UNANSWERABLE" if fam == "S5_UNANSWERABLE_OR_UNSTABLE" else "ANSWERABLE"
        if ans != expected_ans:
            raise ValueError(f"Stratum-answerability mismatch on {qid!r}: {fam} requires {expected_ans}, got {ans!r}")

        split = r.get("split")
        if type(split) is not str or not split.strip():
            raise ValueError(f"Missing split on {qid!r}")
        exposure = r.get("creator_exposure_to_corpus")
        if type(exposure) is not str or not exposure.strip():
            raise ValueError(f"Missing creator_exposure_to_corpus on {qid!r}")
        _validate_query_origin_and_exposure(
            r,
            qid=qid,
            split=split,
            exposure=exposure,
            owner_synthetic_final_approved=owner_synthetic_final_approved,
            route2_ai_proxy_approved=route2_ai_proxy_approved,
        )
        origin = r["question_origin"]

        meta_err = validate_sealed_query_metadata(r, approved_pois_by_id=approved_pois_by_id)
        if meta_err is not None:
            raise ValueError(f"Step S0 validation failed on {qid!r}: {meta_err['error_code']}")

        fc_id = r.get("fact_cluster_id")
        if type(fc_id) is not str or not fc_id.strip():
            raise ValueError(f"Missing or invalid fact_cluster_id on {qid!r}")

        if ans == "ANSWERABLE":
            scope_keys = r["target_poi_ids"] if len(r["target_poi_ids"]) > 0 else [f"CITY:{r['target_city']}"]
            for sk in scope_keys:
                ckey = (sk, fc_id.strip())
                if ckey in seen_clusters:
                    raise ValueError(f"Duplicate atomic (scope, fact_cluster_id) in Q_ans on {qid!r}: {ckey}")
                seen_clusters.add(ckey)
            q_ans_pre.append(qid)
        else:
            q_unans_pre.append(qid)

        facets_raw = r.get("required_evidence_facets")
        if facets_raw is not None and type(facets_raw) is not list:
            raise ValueError(f"required_evidence_facets must be list or None on {qid!r}")

        specs.append(
            QuerySpec(
                query_id=qid,
                query_text=qtext,
                split=split,
                creator_exposure_to_corpus=exposure,
                question_origin=origin,
                query_family=fam,
                target_city=r["target_city"],
                pre_rank_answerability=ans,
                scope_mode=r["scope_mode"],
                target_poi_ids=tuple(r["target_poi_ids"]),
                query_intent_polarity=r["query_intent_polarity"],
                requested_facet_keywords=tuple(r["requested_facet_keywords"]),
                fact_cluster_id=fc_id.strip(),
                required_evidence_facets=tuple(facets_raw) if facets_raw is not None else None,
            )
        )

    meta_summary = {
        "q_ans_pre": q_ans_pre,
        "q_unans_pre": q_unans_pre,
        "total_queries": len(specs),
        "matrix_summary": summary,
    }
    return specs, meta_summary
