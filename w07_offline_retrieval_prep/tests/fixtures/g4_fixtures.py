"""Deterministic synthetic fixtures for M2 G4 Scorer tests (FX-10, FX-12..FX-16, AUTO-EVAL-01)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from w07_g4_scorer.contracts import LOCKED_CELLS
from w07_g4_scorer.query_manifest import (
    ANNEX_G15_CELL_QUOTAS,
    QuerySpec,
)


def make_ranking_row(
    *,
    cell_id: str,
    query_id: str,
    rank: int,
    document_id: str,
    score: float = 1.0,
    rep_chunk_id: str | None = None,
    rep_chunk_index: int = 0,
    assembled_text: str = "Điểm tham quan nổi bật mở cửa hàng ngày.",
    c_full_s_spans: list[list[int]] | None = None,
    c_vis_s_spans: list[list[int]] | None = None,
) -> dict[str, Any]:
    chunker, retriever = cell_id.split("-", 1)
    return {
        "cell_id": cell_id,
        "chunker": chunker,
        "retriever": retriever,
        "query_id": query_id,
        "rank": rank,
        "document_id": document_id,
        "score": float(score),
        "rep_chunk_id": rep_chunk_id or f"{document_id}::chunk_{rep_chunk_index}",
        "rep_chunk_index": rep_chunk_index,
        "assembled_text": assembled_text,
        "assembled_segments": [{"kind": "CANONICAL_BODY_V", "a_start": 0, "a_end": len(assembled_text)}],
        "c_full_s_spans": c_full_s_spans if c_full_s_spans is not None else [[0, len(assembled_text)]],
        "c_vis_s_spans": c_vis_s_spans if c_vis_s_spans is not None else [[0, len(assembled_text)]],
        "leg_ranks": {},
        "leg_rep_chunks": {},
    }


def write_sealed_rankings_bundle(
    out_dir: Path,
    rows: list[dict[str, Any]],
    *,
    cells: list[str] | None = None,
    snapshot_id: str = "e8f8c211226b894fcb81acc59f3b34ba3efd5f42",
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    rankings_path = out_dir / "g3_sealed_rankings_v1.jsonl"
    manifest_path = out_dir / "g3_sealed_rankings_v1_manifest.json"

    lines = [json.dumps(r, ensure_ascii=False, sort_keys=True) for r in rows]
    raw_bytes = ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")
    rankings_path.write_bytes(raw_bytes)
    digest = hashlib.sha256(raw_bytes).hexdigest()

    cell_list = cells if cells is not None else sorted({r["cell_id"] for r in rows})
    manifest = {
        "rankings_file": rankings_path.name,
        "rankings_sha256": digest,
        "row_count": len(rows),
        "cells": cell_list,
        "snapshot_id": snapshot_id,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return rankings_path, manifest_path


def make_query_dict(
    *,
    query_id: str,
    query_text: str = "Giờ mở cửa của địa điểm này là khi nào?",
    split: str = "FINAL",
    creator_exposure_to_corpus: str = "NO",
    question_origin: str = "INDEPENDENT_HUMAN",
    query_family: str = "S1_STRUCTURED_FACT",
    target_city: str = "Hà Nội",
    pre_rank_answerability: str | None = None,
    scope_mode: str = "STRICT_TARGET_POI",
    target_poi_ids: list[str] | None = None,
    query_intent_polarity: str = "AFFIRMATIVE_FACT_NEED",
    requested_facet_keywords: list[str] | None = None,
    fact_cluster_id: str | None = None,
    required_evidence_facets: list[Any] | None = None,
) -> dict[str, Any]:
    ans = pre_rank_answerability or ("UNANSWERABLE" if query_family == "S5_UNANSWERABLE_OR_UNSTABLE" else "ANSWERABLE")
    city_tag = {"Hà Nội": "hn", "Đà Nẵng": "dn", "Hạ Long": "hl"}[target_city]
    pids = target_poi_ids if target_poi_ids is not None else [f"poi-{city_tag}-01"]
    row: dict[str, Any] = {
        "query_id": query_id,
        "query_text": query_text,
        "split": split,
        "creator_exposure_to_corpus": creator_exposure_to_corpus,
        "question_origin": question_origin,
        "query_family": query_family,
        "target_city": target_city,
        "pre_rank_answerability": ans,
        "scope_mode": scope_mode,
        "target_poi_ids": pids,
        "query_intent_polarity": query_intent_polarity,
        "requested_facet_keywords": requested_facet_keywords if requested_facet_keywords is not None else ["mở cửa"],
        "fact_cluster_id": fact_cluster_id or f"fc-{query_id}",
    }
    if required_evidence_facets is not None:
        row["required_evidence_facets"] = required_evidence_facets
    return row


def make_query_spec(**kwargs: Any) -> QuerySpec:
    d = make_query_dict(**kwargs)
    return QuerySpec(
        query_id=d["query_id"],
        query_text=d["query_text"],
        split=d["split"],
        creator_exposure_to_corpus=d["creator_exposure_to_corpus"],
        question_origin=d["question_origin"],
        query_family=d["query_family"],
        target_city=d["target_city"],
        pre_rank_answerability=d["pre_rank_answerability"],
        scope_mode=d["scope_mode"],
        target_poi_ids=tuple(d["target_poi_ids"]),
        query_intent_polarity=d["query_intent_polarity"],
        requested_facet_keywords=tuple(d["requested_facet_keywords"]),
        fact_cluster_id=d["fact_cluster_id"],
        required_evidence_facets=tuple(d["required_evidence_facets"]) if "required_evidence_facets" in d else None,
    )


def build_synthetic_final50_manifest() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Generate a valid 50-query manifest satisfying every 5x3 cell quota + approved 60-POI map."""
    approved_pois: dict[str, dict[str, Any]] = {}
    city_prefixes = {"Hà Nội": "hn", "Đà Nẵng": "dn", "Hạ Long": "hl"}
    for city, pfx in city_prefixes.items():
        for i in range(1, 21):
            pid = f"poi-{pfx}-{i:02d}"
            approved_pois[pid] = {"poi_id": pid, "city": city, "name": f"POI {pfx.upper()} {i}"}

    rows: list[dict[str, Any]] = []
    idx = 0
    for (fam, city), count in ANNEX_G15_CELL_QUOTAS.items():
        pfx = city_prefixes[city]
        for k in range(count):
            idx += 1
            qid = f"fq_{idx:02d}"
            poi_id = f"poi-{pfx}-{(k % 10) + 1:02d}"
            rows.append(
                make_query_dict(
                    query_id=qid,
                    query_text=f"Synthetic final question {idx} in {city}",
                    query_family=fam,
                    target_city=city,
                    target_poi_ids=[poi_id],
                    fact_cluster_id=f"fc-{idx:03d}",
                )
            )
    return rows, approved_pois


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in rows) + ("\n" if rows else "")
    path.write_text(text, encoding="utf-8")
    return path


def build_fx10_shared_lineage_bundle(tmp_path: Path) -> dict[str, Any]:
    """Build synthetic shared-lineage sibling fixture across wikivoyage:en:Hanoi & wikipedia:vi:4483."""
    docs = {
        "doc_wv_a": {
            "document_id": "doc_wv_a",
            "city": "Hà Nội",
            "poi_id": "poi-hn-01",
            "source_lineage_id": "wikivoyage:en:Hanoi",
            "canonical_text_S": "Hồ Hoàn Kiếm nằm ở trung tâm Hà Nội và mở cửa cả ngày.",
        },
        "doc_wv_b": {
            "document_id": "doc_wv_b",
            "city": "Hà Nội",
            "poi_id": "poi-hn-01",
            "source_lineage_id": "wikivoyage:en:Hanoi",
            "canonical_text_S": "Khu vực quanh Hồ Hoàn Kiếm có phố đi bộ vào cuối tuần.",
        },
        "doc_wp_a": {
            "document_id": "doc_wp_a",
            "city": "Hà Nội",
            "poi_id": "poi-hn-02",
            "source_lineage_id": "wikipedia:vi:4483",
            "canonical_text_S": "Văn Miếu Quốc Tử Giám mở cửa từ 08:00 đến 17:00 hàng ngày.",
        },
        "doc_wp_b": {
            "document_id": "doc_wp_b",
            "city": "Hà Nội",
            "poi_id": "poi-hn-02",
            "source_lineage_id": "wikipedia:vi:4483",
            "canonical_text_S": "Văn Miếu Quốc Tử Giám được xây dựng năm 1070.",
        },
    }
    queries = [
        make_query_dict(query_id="q_wv", target_city="Hà Nội", target_poi_ids=["poi-hn-01"]),
        make_query_dict(query_id="q_wp", target_city="Hà Nội", target_poi_ids=["poi-hn-02"]),
    ]
    queries_path = write_jsonl(tmp_path / "queries.jsonl", queries)
    return {"docs": docs, "queries_path": queries_path, "queries": queries}


def build_fx15_smoke_bundle(tmp_path: Path) -> dict[str, Any]:
    """Build complete minimal 6-cell sealed rankings + queries + external qrels bundle for FX-15 & CLI smoke."""
    queries = [
        make_query_dict(
            query_id="q_ans_1",
            query_text="Giờ mở cửa của địa điểm A?",
            query_family="S1_STRUCTURED_FACT",
            target_city="Hà Nội",
            target_poi_ids=["poi-hn-01"],
            required_evidence_facets=[[{"document_id": "d_pos_1", "s_spans": [[0, 20]]}]],
        ),
        make_query_dict(
            query_id="q_ans_2",
            query_text="Địa điểm B có giá vé không?",
            query_family="S2_NARRATIVE_ADVISORY",
            target_city="Đà Nẵng",
            target_poi_ids=["poi-dn-01"],
            required_evidence_facets=[[{"document_id": "d_pos_2", "s_spans": [[0, 20]]}]],
        ),
        make_query_dict(
            query_id="q_unans_1",
            query_text="Hiện tại thời tiết ở địa điểm C thế nào?",
            query_family="S5_UNANSWERABLE_OR_UNSTABLE",
            target_city="Hạ Long",
            target_poi_ids=["poi-hl-01"],
        ),
    ]
    docs_meta = {
        "d_pos_1": {"document_id": "d_pos_1", "city": "Hà Nội", "poi_id": "poi-hn-01", "source_lineage_id": "lin_1"},
        "d_pos_2": {"document_id": "d_pos_2", "city": "Đà Nẵng", "poi_id": "poi-dn-01", "source_lineage_id": "lin_2"},
        "d_neg_1": {"document_id": "d_neg_1", "city": "Hà Nội", "poi_id": "poi-hn-99", "source_lineage_id": "lin_3"},
        "d_lure_1": {"document_id": "d_lure_1", "city": "Hạ Long", "poi_id": "poi-hl-01", "source_lineage_id": "lin_4"},
    }

    rows: list[dict[str, Any]] = []
    for cell_id in LOCKED_CELLS:
        # C1 cells rank positive docs higher than C0 cells
        is_c1 = cell_id.startswith("C1-")
        order_q1 = ["d_pos_1", "d_neg_1"] if is_c1 else ["d_neg_1", "d_pos_1"]
        order_q2 = ["d_pos_2", "d_neg_1"] if is_c1 else ["d_neg_1", "d_pos_2"]
        order_qu = ["d_neg_1"] if is_c1 else ["d_lure_1", "d_neg_1"]

        for rank, did in enumerate(order_q1, start=1):
            rows.append(make_ranking_row(cell_id=cell_id, query_id="q_ans_1", rank=rank, document_id=did, score=1.0 / rank))
        for rank, did in enumerate(order_q2, start=1):
            rows.append(make_ranking_row(cell_id=cell_id, query_id="q_ans_2", rank=rank, document_id=did, score=1.0 / rank))
        for rank, did in enumerate(order_qu, start=1):
            rows.append(make_ranking_row(cell_id=cell_id, query_id="q_unans_1", rank=rank, document_id=did, score=1.0 / rank))

    qrels_rows = [
        {
            "query_id": "q_ans_1",
            "document_id": "d_pos_1",
            "label": "REL_2",
            "plausible_unsupported_lure": 0,
            "evidence_s_spans": [[0, 20]],
            "source_lineage_id": "lin_1",
        },
        {
            "query_id": "q_ans_1",
            "document_id": "d_neg_1",
            "label": "REL_0",
            "plausible_unsupported_lure": 0,
            "evidence_s_spans": [],
            "source_lineage_id": "lin_3",
        },
        {
            "query_id": "q_ans_1",
            "document_id": "d_pos_2",
            "label": "REL_0",
            "plausible_unsupported_lure": 0,
            "evidence_s_spans": [],
            "source_lineage_id": "lin_2",
        },
        {
            "query_id": "q_ans_1",
            "document_id": "d_lure_1",
            "label": "REL_0",
            "plausible_unsupported_lure": 0,
            "evidence_s_spans": [],
            "source_lineage_id": "lin_4",
        },
        {
            "query_id": "q_ans_2",
            "document_id": "d_pos_2",
            "label": "REL_2",
            "plausible_unsupported_lure": 0,
            "evidence_s_spans": [[0, 20]],
            "source_lineage_id": "lin_2",
        },
        {
            "query_id": "q_ans_2",
            "document_id": "d_neg_1",
            "label": "REL_0",
            "plausible_unsupported_lure": 0,
            "evidence_s_spans": [],
            "source_lineage_id": "lin_3",
        },
        {
            "query_id": "q_ans_2",
            "document_id": "d_pos_1",
            "label": "REL_0",
            "plausible_unsupported_lure": 0,
            "evidence_s_spans": [],
            "source_lineage_id": "lin_1",
        },
        {
            "query_id": "q_ans_2",
            "document_id": "d_lure_1",
            "label": "REL_0",
            "plausible_unsupported_lure": 0,
            "evidence_s_spans": [],
            "source_lineage_id": "lin_4",
        },
        {
            "query_id": "q_unans_1",
            "document_id": "d_neg_1",
            "label": "REL_0",
            "plausible_unsupported_lure": 0,
            "evidence_s_spans": [],
            "source_lineage_id": "lin_3",
        },
        {
            "query_id": "q_unans_1",
            "document_id": "d_lure_1",
            "label": "REL_0",
            "plausible_unsupported_lure": 1,
            "evidence_s_spans": [],
            "source_lineage_id": "lin_4",
        },
    ]

    rankings_path, manifest_path = write_sealed_rankings_bundle(tmp_path, rows, cells=list(LOCKED_CELLS))
    queries_path = write_jsonl(tmp_path / "queries.jsonl", queries)
    qrels_path = write_jsonl(tmp_path / "qrels.jsonl", qrels_rows)
    docs_path = tmp_path / "docs.json"
    docs_path.write_text(json.dumps(docs_meta, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "rankings_path": rankings_path,
        "manifest_path": manifest_path,
        "queries_path": queries_path,
        "qrels_path": qrels_path,
        "docs_path": docs_path,
    }
