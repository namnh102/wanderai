"""Document collapse (first-occurrence max chunk) and Hybrid RRF(k=60, D=50)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal, Sequence

from w07_retrieval.schema import ChunkRecord

RRF_K: int = 60
RRF_CANDIDATE_DEPTH: int = 50


@dataclass(frozen=True)
class RankedDocument:
    """Document-level ranked entry with label-blind representative chunk and provenance."""

    rank: int
    document_id: str
    score: float
    rep_chunk: ChunkRecord
    primary_leg: Literal["BM25", "Dense"]
    leg_ranks: dict[str, int | None]
    leg_rep_chunks: dict[str, dict[str, Any] | None]
    c_full_s_spans: list[list[int]]
    c_vis_s_spans: list[list[int]]


def collapse_chunk_scores(
    chunks: Sequence[ChunkRecord],
    scores: Sequence[float],
    *,
    retriever_name: Literal["BM25", "Dense"],
    min_score_exclusive: float | None = None,
) -> list[RankedDocument]:
    """Score 100% of chunks -> deterministic sort -> first-occurrence document_id collapse."""
    if len(chunks) != len(scores):
        raise ValueError(
            f"Length mismatch: {len(chunks)} chunks vs {len(scores)} scores"
        )
    if retriever_name not in ("BM25", "Dense"):
        raise ValueError(f"Unsupported retriever_name: {retriever_name!r}")

    ordered = sorted(
        zip(chunks, scores),
        key=lambda item: (
            -float(item[1]),
            item[0].document_id,
            item[0].chunk_index,
            item[0].chunk_id,
        ),
    )

    seen_docs: set[str] = set()
    collapsed: list[tuple[ChunkRecord, float]] = []
    for chunk, raw_score in ordered:
        if chunk.document_id in seen_docs:
            continue
        seen_docs.add(chunk.document_id)
        score_val = float(raw_score)
        if min_score_exclusive is not None and not (score_val > min_score_exclusive):
            continue
        collapsed.append((chunk, score_val))

    ranked: list[RankedDocument] = []
    for rank, (chunk, score_val) in enumerate(collapsed, start=1):
        c_full = [[int(a), int(b)] for a, b in chunk.c_full_s_spans]
        if retriever_name == "Dense":
            c_vis = [[int(a), int(b)] for a, b in chunk.c_vis_s_spans_dense]
        else:
            c_vis = [[int(a), int(b)] for a, b in chunk.c_vis_s_spans_bm25]

        ranked.append(
            RankedDocument(
                rank=rank,
                document_id=chunk.document_id,
                score=score_val,
                rep_chunk=chunk,
                primary_leg=retriever_name,
                leg_ranks={retriever_name: rank},
                leg_rep_chunks={
                    retriever_name: {
                        "chunk_id": chunk.chunk_id,
                        "chunk_index": chunk.chunk_index,
                        "score": score_val,
                    }
                },
                c_full_s_spans=c_full,
                c_vis_s_spans=c_vis,
            )
        )
    return ranked


def fuse_rrf(
    bm25_ranked: Sequence[RankedDocument],
    dense_ranked: Sequence[RankedDocument],
    *,
    rrf_k: int = RRF_K,
    candidate_depth: int = RRF_CANDIDATE_DEPTH,
) -> list[RankedDocument]:
    """Reciprocal Rank Fusion RRF(k=60, D=50) over distinct collapsed documents."""
    bm25_pool = list(bm25_ranked[:candidate_depth])
    dense_pool = list(dense_ranked[:candidate_depth])

    bm25_by_doc = {r.document_id: r for r in bm25_pool}
    dense_by_doc = {r.document_id: r for r in dense_pool}
    candidate_doc_ids = set(bm25_by_doc) | set(dense_by_doc)

    candidates: list[tuple[float, int, float, str, RankedDocument]] = []
    for doc_id in candidate_doc_ids:
        b_entry = bm25_by_doc.get(doc_id)
        d_entry = dense_by_doc.get(doc_id)

        r_bm25 = b_entry.rank if b_entry is not None else None
        r_dense = d_entry.rank if d_entry is not None else None

        rrf_score = (1.0 / (rrf_k + r_bm25) if r_bm25 is not None else 0.0) + (
            1.0 / (rrf_k + r_dense) if r_dense is not None else 0.0
        )
        min_leg_rank = min(r for r in (r_bm25, r_dense) if r is not None)
        rank_dense_key = float(r_dense) if r_dense is not None else math.inf

        if d_entry is not None and (b_entry is None or r_dense <= r_bm25):  # type: ignore[operator]
            primary_leg: Literal["BM25", "Dense"] = "Dense"
            rep_entry = d_entry
        else:
            assert b_entry is not None
            primary_leg = "BM25"
            rep_entry = b_entry

        leg_ranks: dict[str, int | None] = {"BM25": r_bm25, "Dense": r_dense}
        leg_rep_chunks: dict[str, dict[str, Any] | None] = {
            "BM25": b_entry.leg_rep_chunks["BM25"] if b_entry is not None else None,
            "Dense": d_entry.leg_rep_chunks["Dense"] if d_entry is not None else None,
        }

        fused_proto = RankedDocument(
            rank=0,
            document_id=doc_id,
            score=rrf_score,
            rep_chunk=rep_entry.rep_chunk,
            primary_leg=primary_leg,
            leg_ranks=leg_ranks,
            leg_rep_chunks=leg_rep_chunks,
            c_full_s_spans=rep_entry.c_full_s_spans,
            c_vis_s_spans=rep_entry.c_vis_s_spans,
        )
        candidates.append((-rrf_score, min_leg_rank, rank_dense_key, doc_id, fused_proto))

    candidates.sort(key=lambda item: (item[0], item[1], item[2], item[3]))

    fused: list[RankedDocument] = []
    for rank, (_, _, _, _, proto) in enumerate(candidates, start=1):
        fused.append(
            RankedDocument(
                rank=rank,
                document_id=proto.document_id,
                score=proto.score,
                rep_chunk=proto.rep_chunk,
                primary_leg=proto.primary_leg,
                leg_ranks=proto.leg_ranks,
                leg_rep_chunks=proto.leg_rep_chunks,
                c_full_s_spans=proto.c_full_s_spans,
                c_vis_s_spans=proto.c_vis_s_spans,
            )
        )
    return fused
