"""Tier 4 Opaque-Box E2E Tests — Realistic Multi-Feature Tourism Workloads (7 tests).

Covers `T4-01..T4-07` across synthetic Vietnamese/English tourism workloads
(`Hà Nội`, `Đà Nẵng`, `Hạ Long`) with zero real-corpus access.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List

import pytest

from .conftest import (
    ALL_SIX_CELLS,
    BLIND_PACKET_KEYS,
    WANDERAI_EXPECTED_HEAD,
    WANDERAI_ROOT,
    cached_minilm_tokenizer,
    extract_cells_map,
    extract_contrasts_map,
    extract_metric_value,
    extract_per_query_map,
    extract_unanswerable_map,
    file_sha256,
    is_blocked_or_invalid_status,
    read_json,
    read_jsonl,
    report_contains_token,
    require_retrieval_cli,
    require_scorer_cli,
    rows_for_cell_query,
    run_python_probe,
    run_retrieval_cli,
    run_scorer_cli,
    scorer_supports_flag,
)
from .synthetic_builders import (
    build_tourism_workload_pack,
    find_span,
    make_5x3_query_matrix,
    make_b1b_doc,
    make_judge_record,
    make_multi_level_doc,
    make_osm_doc,
    make_overture_doc,
    make_qrel_row,
    make_query_row,
    split_span_excluding_removed,
    write_jsonl,
    write_synthetic_sealed_rankings,
)


def _strip_timestamps(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {
            k: _strip_timestamps(v)
            for k, v in obj.items()
            if k not in {"generated_at", "timestamp", "created_at", "elapsed_ms"}
        }
    if isinstance(obj, list):
        return [_strip_timestamps(v) for v in obj]
    return obj


def test_t4_01_full_offline_2x3_benchmark_pipeline_tourism_corpus(tmp_path: Path) -> None:
    """T4-01: Full Offline 2x3 Benchmark Pipeline (Hà Nội / Đà Nẵng / Hạ Long)."""
    require_retrieval_cli()
    require_scorer_cli()
    pack = build_tourism_workload_pack("full_2x3")
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", pack["docs"])
    queries_p = write_jsonl(tmp_path / "queries.jsonl", pack["queries"])
    qrels_p = write_jsonl(tmp_path / "qrels.jsonl", pack["qrels"])
    rem_p = tmp_path / "removed_spans.json"
    rem_p.write_text(json.dumps(pack["removed_spans"]), encoding="utf-8")
    out_dir = tmp_path / "g3"

    run_retrieval_cli(corpus_p, queries_p, out_dir, packet_salt="T4_01_SALT", timeout=300)
    manifest = read_json(out_dir / "g3_sealed_rankings_v1_manifest.json")
    assert manifest["snapshot_id"] == "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"
    assert manifest["rankings_sha256"] == file_sha256(out_dir / "g3_sealed_rankings_v1.jsonl")

    tok = cached_minilm_tokenizer()
    for ch in read_jsonl(out_dir / "chunks_manifest.jsonl"):
        if ch.get("chunker") == "C1":
            assert len(tok.encode(ch["assembled_text"], add_special_tokens=True, truncation=False)) <= 128

    for row in read_jsonl(out_dir / "blind_annotation_packet.jsonl"):
        assert set(row.keys()) == BLIND_PACKET_KEYS

    report_p = tmp_path / "g4_report.json"
    run_scorer_cli(
        out_dir / "g3_sealed_rankings_v1.jsonl",
        out_dir / "g3_sealed_rankings_v1_manifest.json",
        qrels_p,
        queries_p,
        report_p,
        removed_audit_spans=rem_p,
        strict_full_pool=True,
    )
    report = read_json(report_p)
    assert set(extract_cells_map(report).keys()) == set(ALL_SIX_CELLS)
    assert {"K1", "K2", "K3", "K4", "K5"}.issubset(extract_contrasts_map(report).keys())
    assert not report_contains_token(report, "CorrectAbstentionRate")
    assert not report_contains_token(report, "G5 PASS")


def test_t4_02_long_bilingual_poi_guide_truncation_rescue(tmp_path: Path) -> None:
    """T4-02: Long Bilingual POI Guide Truncation Rescue (C0 vs C1 Diagnostic)."""
    require_retrieval_cli()
    require_scorer_cli()
    filler = "Lịch sử hình thành và kiến trúc trưng bày bảo tàng tại trung tâm Hà Nội. " * 25
    doc_long, rem_long = make_overture_doc(
        "doc-long-poi",
        "Giờ mở cửa bảo tàng ARCHIVE-HOURS-0800",
        [
            ("Vé tham quan ", "[CORROBORATED: osm:node/77, wikidata:Q77]"),
            (" giá 40.000 đồng.\n" + filler + "Giờ mở cửa chính thức: ARCHIVE-HOURS-0800.", None),
        ],
    )
    doc_short = make_multi_level_doc(
        "doc-short-sec",
        "Cầu Rồng Đà Nẵng",
        [
            (2, "Giới thiệu", "Cầu Rồng bắc qua sông Hàn tại thành phố Đà Nẵng rất nổi tiếng với du khách."),
            (2, "Giờ mở cửa", "Mở cửa từ 07:30 đến 17:30 hàng ngày."),
        ],
        city="Đà Nẵng",
        poi_id="syn-poi-dn-02",
    )
    s_long = doc_long["canonical_text_S"]
    tail_idx = s_long.rindex("ARCHIVE-HOURS-0800")
    tail_span = [[tail_idx, tail_idx + len("ARCHIVE-HOURS-0800")]]
    early_sub = split_span_excluding_removed(
        0, s_long.index("40.000 đồng.") + len("40.000 đồng."), rem_long
    )

    q_tail = make_query_row(
        "Q-TAIL",
        "ARCHIVE-HOURS-0800",
        requested_facet_keywords=["ARCHIVE-HOURS-0800"],
        required_evidence_facets=[[{"document_id": "doc-long-poi", "s_spans": tail_span}]],
    )
    q_early = make_query_row(
        "Q-EARLY",
        "Vé tham quan giá 40.000 đồng",
        requested_facet_keywords=["40.000"],
        required_evidence_facets=[[{"document_id": "doc-long-poi", "s_spans": early_sub}]],
    )
    q_short = make_query_row(
        "Q-SHORT",
        "07:30 đến 17:30 hàng ngày",
        target_city="Đà Nẵng",
        target_poi_ids=["syn-poi-dn-02"],
        requested_facet_keywords=["07:30", "17:30"],
    )

    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", [doc_long, doc_short])
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q_tail, q_early, q_short])
    out_dir = tmp_path / "g3"
    run_retrieval_cli(corpus_p, queries_p, out_dir, timeout=300)

    all_rows = read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl")
    assert rows_for_cell_query(all_rows, "C0-BM25", "Q-SHORT") == [] or all(
        r["document_id"] != "doc-short-sec"
        for r in rows_for_cell_query(all_rows, "C0-BM25", "Q-SHORT")
    )
    c1_bm25_short = rows_for_cell_query(all_rows, "C1-BM25", "Q-SHORT")
    assert any(r["document_id"] == "doc-short-sec" for r in c1_bm25_short)

    # Score tail + early span queries
    q_vis_p = write_jsonl(tmp_path / "q_vis.jsonl", [q_tail])
    qr_vis_p = write_jsonl(
        tmp_path / "qr_vis.jsonl",
        [
            make_qrel_row("Q-TAIL", "doc-long-poi", "REL_2", evidence_s_spans=tail_span),
            make_qrel_row("Q-TAIL", "doc-short-sec", "REL_0"),
        ],
    )
    rep_p = tmp_path / "g4_tail.json"
    run_scorer_cli(
        out_dir / "g3_sealed_rankings_v1.jsonl",
        out_dir / "g3_sealed_rankings_v1_manifest.json",
        qr_vis_p,
        q_vis_p,
        rep_p,
    )
    cells = extract_cells_map(read_json(rep_p))
    assert float(extract_metric_value(cells["C0-Dense"], ["VisibleEvidenceSpanHit@10", "visible_evidence_span_hit_10"])) == pytest.approx(0.0)
    assert float(extract_metric_value(cells["C1-Dense"], ["VisibleEvidenceSpanHit@10", "visible_evidence_span_hit_10"])) == pytest.approx(1.0)
    assert float(extract_metric_value(cells["C1-RRF"], ["VisibleEvidenceSpanHit@10", "visible_evidence_span_hit_10"])) == pytest.approx(1.0)


def _assert_nested_metrics_close(a: Any, b: Any, *, tol: float = 1e-6) -> None:
    if isinstance(a, dict):
        assert isinstance(b, dict)
        assert set(a.keys()) == set(b.keys())
        for k in a:
            _assert_nested_metrics_close(a[k], b[k], tol=tol)
    elif isinstance(a, list):
        assert isinstance(b, list) and len(a) == len(b)
        for va, vb in zip(a, b):
            _assert_nested_metrics_close(va, vb, tol=tol)
    elif isinstance(a, float) or isinstance(b, float):
        assert float(a) == pytest.approx(float(b), abs=tol)
    else:
        assert a == b


def test_t4_03_repeated_run_bit_exact_reproducibility_and_order_invariance(tmp_path: Path) -> None:
    """T4-03: Repeated-Run Bit-Exact Reproducibility & Corpus/Query-Order Invariance."""
    require_retrieval_cli()
    require_scorer_cli()
    pack = build_tourism_workload_pack("full_2x3")
    docs = pack["docs"]
    queries = pack["queries"]
    qrels = pack["qrels"]

    run_a = tmp_path / "run_a"
    run_b = tmp_path / "run_b"
    run_rev = tmp_path / "run_rev"
    run_a.mkdir()
    run_b.mkdir()
    run_rev.mkdir()

    c_a = write_jsonl(run_a / "corpus.jsonl", docs)
    q_a = write_jsonl(run_a / "queries.jsonl", queries)
    qr_a = write_jsonl(run_a / "qrels.jsonl", qrels)

    c_b = write_jsonl(run_b / "corpus.jsonl", docs)
    q_b = write_jsonl(run_b / "queries.jsonl", queries)
    qr_b = write_jsonl(run_b / "qrels.jsonl", qrels)

    c_rev = write_jsonl(run_rev / "corpus.jsonl", list(reversed(docs)))
    q_rev = write_jsonl(run_rev / "queries.jsonl", list(reversed(queries)))
    qr_rev = write_jsonl(run_rev / "qrels.jsonl", list(reversed(qrels)))

    # (a) Repeated runs on identical inputs -> byte-identical rankings, packet, and G4 report
    run_retrieval_cli(c_a, q_a, run_a / "g3", packet_salt="W07_AUDIT_SALT", timeout=300)
    run_retrieval_cli(c_b, q_b, run_b / "g3", packet_salt="W07_AUDIT_SALT", timeout=300)
    assert file_sha256(run_a / "g3" / "g3_sealed_rankings_v1.jsonl") == file_sha256(
        run_b / "g3" / "g3_sealed_rankings_v1.jsonl"
    )
    assert file_sha256(run_a / "g3" / "blind_annotation_packet.jsonl") == file_sha256(
        run_b / "g3" / "blind_annotation_packet.jsonl"
    )

    rep_a = run_a / "g4.json"
    rep_b = run_b / "g4.json"
    run_scorer_cli(
        run_a / "g3" / "g3_sealed_rankings_v1.jsonl",
        run_a / "g3" / "g3_sealed_rankings_v1_manifest.json",
        qr_a,
        q_a,
        rep_a,
    )
    run_scorer_cli(
        run_b / "g3" / "g3_sealed_rankings_v1.jsonl",
        run_b / "g3" / "g3_sealed_rankings_v1_manifest.json",
        qr_b,
        q_b,
        rep_b,
    )
    rep_a_json = read_json(rep_a)
    assert _strip_timestamps(rep_a_json) == _strip_timestamps(read_json(rep_b))

    # (b) Reversed corpus + queries + qrels -> byte-identical packet, identical rank order,
    # rankings scores within 1e-5, and cell_metrics within 1e-6
    run_retrieval_cli(c_rev, q_rev, run_rev / "g3", packet_salt="W07_AUDIT_SALT", timeout=300)
    assert file_sha256(run_a / "g3" / "blind_annotation_packet.jsonl") == file_sha256(
        run_rev / "g3" / "blind_annotation_packet.jsonl"
    )
    rows_a = read_jsonl(run_a / "g3" / "g3_sealed_rankings_v1.jsonl")
    rows_rev = read_jsonl(run_rev / "g3" / "g3_sealed_rankings_v1.jsonl")
    assert len(rows_a) == len(rows_rev)
    for ra, rr in zip(rows_a, rows_rev):
        assert (ra["cell_id"], ra["query_id"], ra["rank"], ra["document_id"]) == (
            rr["cell_id"],
            rr["query_id"],
            rr["rank"],
            rr["document_id"],
        )
        assert abs(float(ra["score"]) - float(rr["score"])) < 1e-5

    rep_rev = run_rev / "g4.json"
    run_scorer_cli(
        run_rev / "g3" / "g3_sealed_rankings_v1.jsonl",
        run_rev / "g3" / "g3_sealed_rankings_v1_manifest.json",
        qr_rev,
        q_rev,
        rep_rev,
    )
    rep_rev_json = read_json(rep_rev)
    _assert_nested_metrics_close(
        extract_cells_map(rep_a_json), extract_cells_map(rep_rev_json), tol=1e-6
    )


def test_t4_04_bilingual_tourism_bm25_vs_dense_vs_hybrid_rrf(tmp_path: Path) -> None:
    """T4-04: Bilingual Tourism Retrieval (BM25 Compounds vs Dense Cross-Lingual vs RRF Multi-Evidence)."""
    require_retrieval_cli()
    require_scorer_cli()
    docs = [
        make_b1b_doc("d-vi-pho", "Phở Hà Nội", "Quán phở bò gia truyền giá 45.000 đồng tại phố cổ Hà Nội."),
        make_b1b_doc("d-vi-bridge", "Cầu Rồng", "Cầu Rồng Đà Nẵng trình diễn phun lửa lúc 21:00 cuối tuần.", city="Đà Nẵng", poi_id="syn-poi-dn-02"),
        make_b1b_doc("d-en-cable", "Ba Na Cable Car", "Sun World cable car schedule runs daily from 07:30 AM.", language="en", city="Đà Nẵng", poi_id="syn-poi-dn-01"),
        make_b1b_doc("d-en-cruise", "Ha Long Cruise", "Ha Long night cruise boarding gate opens at Tuan Chau pier.", language="en", city="Hạ Long", poi_id="syn-poi-hl-01"),
        make_osm_doc("d-osm-m", "Bảo tàng Chăm", destination="Đà Nẵng", tags={"opening_hours": "07:00-17:00"}, source_id="node/88", poi_id="syn-poi-dn-03"),
        make_b1b_doc("d-b1b-m", "Lịch sử Chăm", "Bảo tàng Điêu khắc Chăm lưu giữ tượng cổ Champa thế kỷ X.", city="Đà Nẵng", poi_id="syn-poi-dn-03"),
    ]
    sp_osm = [find_span(docs[4]["canonical_text_S"], "Giờ mở cửa: 07:00-17:00.")]
    sp_b1b = [find_span(docs[5]["canonical_text_S"], "tượng cổ Champa thế kỷ X")]

    queries = [
        make_query_row("Q-BM1", "phở bò 45.000", requested_facet_keywords=["45.000"]),
        make_query_row("Q-BM2", "cầu Rồng phun lửa 21:00", target_city="Đà Nẵng", target_poi_ids=["syn-poi-dn-02"], requested_facet_keywords=["21:00"]),
        make_query_row("Q-EN1", "Lịch chạy cáp treo Sun World hoạt động lúc mấy giờ?", query_family="S4_CROSS_LINGUAL_VI_TO_EN", target_city="Đà Nẵng", target_poi_ids=["syn-poi-dn-01"], requested_facet_keywords=["07:30"]),
        make_query_row("Q-EN2", "Cổng lên tàu du thuyền đêm Hạ Long ở bến nào?", query_family="S4_CROSS_LINGUAL_VI_TO_EN", target_city="Hạ Long", target_poi_ids=["syn-poi-hl-01"], requested_facet_keywords=["Tuan Chau"]),
        make_query_row("Q-S3", "Bảo tàng Chăm mở cửa giờ nào và trưng bày cổ vật gì?", query_family="S3_MULTI_EVIDENCE", target_city="Đà Nẵng", target_poi_ids=["syn-poi-dn-03"], requested_facet_keywords=["07:00", "Champa"], required_evidence_facets=[[{"document_id": "d-osm-m", "s_spans": sp_osm}], [{"document_id": "d-b1b-m", "s_spans": sp_b1b}]]),
    ]
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", queries)
    out_dir = tmp_path / "g3"
    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-BM25", "C1-Dense", "C1-RRF"])

    all_rows = read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl")
    assert rows_for_cell_query(all_rows, "C1-BM25", "Q-BM1")[0]["document_id"] == "d-vi-pho"
    assert rows_for_cell_query(all_rows, "C1-BM25", "Q-BM2")[0]["document_id"] == "d-vi-bridge"
    # English docs excluded from Vietnamese-only BM25
    assert "d-en-cable" not in {r["document_id"] for r in rows_for_cell_query(all_rows, "C1-BM25", "Q-BM1")}
    assert rows_for_cell_query(all_rows, "C1-Dense", "Q-EN1")[0]["document_id"] == "d-en-cable"
    assert rows_for_cell_query(all_rows, "C1-Dense", "Q-EN2")[0]["document_id"] == "d-en-cruise"

    # Multi-evidence S3 scored via C1-RRF
    q_s3_p = write_jsonl(tmp_path / "q_s3.jsonl", [queries[4]])
    qr_s3 = [
        make_qrel_row("Q-S3", d["document_id"], "REL_1" if d["document_id"] in {"d-osm-m", "d-b1b-m"} else "REL_0", evidence_s_spans=sp_osm if d["document_id"] == "d-osm-m" else (sp_b1b if d["document_id"] == "d-b1b-m" else []))
        for d in docs
    ]
    rep_p = tmp_path / "g4_s3.json"
    run_scorer_cli(
        out_dir / "g3_sealed_rankings_v1.jsonl",
        out_dir / "g3_sealed_rankings_v1_manifest.json",
        write_jsonl(tmp_path / "qr_s3.jsonl", qr_s3),
        q_s3_p,
        rep_p,
    )
    c1_rrf = extract_cells_map(read_json(rep_p))["C1-RRF"]
    assert float(extract_metric_value(c1_rrf, ["VisibleEvidenceSpanHit@10", "visible_evidence_span_hit_10"])) == pytest.approx(1.0)


def test_t4_05_shared_lineage_sibling_pool_and_partial_id_lifecycle(tmp_path: Path) -> None:
    """T4-05: Shared-Lineage Sibling Pool & Partial-Identification Lifecycle (D05 + Cert-1..4)."""
    require_retrieval_cli()
    require_scorer_cli()
    docs = [
        make_b1b_doc("sib-wv-1", "Hanoi 1", "Phố cổ Hà Nội ẩm thực đặc sắc.", source_lineage_id="wikivoyage:en:Hanoi"),
        make_b1b_doc("sib-wv-2", "Hanoi 2", "Phố cổ Hà Nội nhiều di tích cổ.", source_lineage_id="wikivoyage:en:Hanoi"),
        make_b1b_doc("sib-wv-3", "Hanoi 3", "Phố cổ Hà Nội về đêm sôi động.", source_lineage_id="wikivoyage:en:Hanoi"),
        make_b1b_doc("sib-wp-1", "Wiki 1", "Hồ Hoàn Kiếm nằm giữa thủ đô.", source_lineage_id="wikipedia:vi:4483"),
        make_b1b_doc("sib-wp-2", "Wiki 2", "Hồ Hoàn Kiếm gắn với truyền thuyết.", source_lineage_id="wikipedia:vi:4483"),
    ]
    # Add 7 filler docs so an out-of-top-10 doc can remain UNJUDGED in Stage 2
    for i in range(1, 8):
        docs.append(make_b1b_doc(f"filler-{i}", f"F{i}", f"Chủ đề khác biệt số {i} về xe buýt."))

    q = make_query_row("Q-LIN", "phố cổ Hà Nội", requested_facet_keywords=["phố cổ"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "g3"
    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-BM25", "C1-Dense", "C1-RRF"])

    # Determine top-10 union across cells so Stage 2 leaves strictly an out-of-top-10 doc UNJUDGED
    all_rows = read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl")
    top10_ids = {r["document_id"] for r in all_rows if r["rank"] <= 10}
    out_of_top10 = [d["document_id"] for d in docs if d["document_id"] not in top10_ids]
    assert len(out_of_top10) >= 1
    unjudged_out = out_of_top10[0]

    # Stage 1: sib-wv-2 (in top-10) left UNJUDGED -> must fail Cert-2 / block
    qrels_s1 = [
        make_qrel_row(
            "Q-LIN",
            d["document_id"],
            "UNJUDGED" if d["document_id"] == "sib-wv-2" else ("REL_2" if d["document_id"] in {"sib-wv-1", "sib-wv-3"} else "REL_0"),
            source_lineage_id=d["source_lineage_id"],
        )
        for d in docs
    ]
    out_s1 = tmp_path / "g4_s1.json"
    p1 = run_scorer_cli(
        out_dir / "g3_sealed_rankings_v1.jsonl",
        out_dir / "g3_sealed_rankings_v1_manifest.json",
        write_jsonl(tmp_path / "qr_s1.jsonl", qrels_s1),
        queries_p,
        out_s1,
        check=False,
    )
    assert is_blocked_or_invalid_status(p1, out_s1)

    # Stage 2: all top-10 closed, out-of-top-10 unjudged_out stays UNJUDGED -> BOUNDED_NOT_EXACT
    qrels_s2 = [
        make_qrel_row(
            "Q-LIN",
            d["document_id"],
            "UNJUDGED" if d["document_id"] == unjudged_out else ("REL_2" if d["document_id"] in {"sib-wv-1", "sib-wv-2"} else "REL_0"),
            source_lineage_id=d["source_lineage_id"],
        )
        for d in docs
    ]
    out_s2 = tmp_path / "g4_s2.json"
    run_scorer_cli(
        out_dir / "g3_sealed_rankings_v1.jsonl",
        out_dir / "g3_sealed_rankings_v1_manifest.json",
        write_jsonl(tmp_path / "qr_s2.jsonl", qrels_s2),
        queries_p,
        out_s2,
    )
    rep_s2 = read_json(out_s2)
    assert rep_s2["headline_status"] == "NO_EXACT_FULL_SET_ESTIMATE"
    cell = extract_cells_map(rep_s2)["C1-RRF"]
    elc = extract_metric_value(cell, ["epistemic_lineage_mean_at_10", "epistemic_lineage_count", "distinct_lineages"])
    assert float(elc) == pytest.approx(1.0)


def test_t4_06_auto_eval_dual_llm_proxy_audit_workload(tmp_path: Path) -> None:
    """T4-06: AUTO-EVAL-01 v0.4.2 Dual-LLM Proxy Audit Workload."""
    require_scorer_cli()
    queries = make_5x3_query_matrix(split="FINAL", question_origin="INDEPENDENT_HUMAN")
    queries[0]["target_city"] = "Hà Nội"
    queries[0]["target_poi_ids"] = ["syn-poi-hn-01"]
    queries[0]["query_intent_polarity"] = "AFFIRMATIVE_FACT_NEED"
    queries[0]["requested_facet_keywords"] = ["mở cửa"]

    queries[1]["target_city"] = "Hà Nội"
    queries[1]["target_poi_ids"] = ["syn-poi-hn-01"]
    queries[1]["query_intent_polarity"] = "BOOLEAN_ELIGIBILITY_OR_POLICY_CHECK"
    queries[1]["requested_facet_keywords"] = ["mở cửa"]

    d_clean = make_b1b_doc("d-clean", "HN", "Bảo tàng mở cửa từ 08:00.", poi_id="syn-poi-hn-01", city="Hà Nội")
    d_wrong_city = make_b1b_doc("d-wc", "DN", "Bảo tàng mở cửa từ 08:00.", poi_id="syn-poi-hn-01", city="Đà Nẵng")
    d_neg = make_b1b_doc("d-neg", "HN", "Bảo tàng không mở cửa thứ Hai.", poi_id="syn-poi-hn-01", city="Hà Nội")
    d_tag, rem_tag = make_overture_doc("d-tag", "HN", [("Giờ ", "[CORROBORATED: osm:node/1]"), (" mở cửa.", None)], confidence=None, poi_id="syn-poi-hn-01", city="Hà Nội")
    rem_p = tmp_path / "rem.json"
    rem_p.write_text(json.dumps({"d-tag": [list(s) for s in rem_tag]}), encoding="utf-8")

    docs = {d["document_id"]: d for d in (d_clean, d_wrong_city, d_neg, d_tag)}
    rank_map = {
        (cell, q["query_id"]): [("d-clean", 4.0), ("d-wc", 3.0), ("d-neg", 2.0), ("d-tag", 1.0)]
        for cell in ("C1-BM25", "C1-RRF")
        for q in queries
    }
    rankings_p, manifest_p = write_synthetic_sealed_rankings(tmp_path / "g3", rank_map, docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", queries)
    docs_p = write_jsonl(tmp_path / "docs.jsonl", list(docs.values()))

    expected_pairs = [
        [queries[0]["query_id"], "d-clean"],
        [queries[0]["query_id"], "d-wc"],
        [queries[1]["query_id"], "d-neg"],
        [queries[0]["query_id"], "d-tag"],
    ]
    ep_p = tmp_path / "expected_pairs.json"
    ep_p.write_text(json.dumps(expected_pairs), encoding="utf-8")

    ja = [
        make_judge_record(queries[0]["query_id"], "d-clean", "REL_2", evidence_quote="Bảo tàng mở cửa từ 08:00.", char_start=0, char_end=len(d_clean["canonical_text_S"])),
        make_judge_record(queries[0]["query_id"], "d-wc", "REL_2", evidence_quote="Bảo tàng mở cửa từ 08:00.", char_start=0, char_end=len(d_wrong_city["canonical_text_S"])),
        make_judge_record(queries[1]["query_id"], "d-neg", "REL_2", evidence_quote="không mở cửa", char_start=9, char_end=21),
        make_judge_record(queries[0]["query_id"], "d-tag", "REL_2", evidence_quote="[CORROBORATED: osm:node/1]", char_start=4, char_end=30),
    ]
    jb = [
        make_judge_record(queries[0]["query_id"], "d-clean", "REL_1", evidence_quote="Bảo tàng mở cửa từ 08:00.", char_start=0, char_end=len(d_clean["canonical_text_S"])),
        make_judge_record(queries[0]["query_id"], "d-wc", "REL_0"),
        make_judge_record(queries[1]["query_id"], "d-neg", "REL_2", evidence_quote="không mở cửa", char_start=9, char_end=21),
        make_judge_record(queries[0]["query_id"], "d-tag", "REL_0"),
    ]

    out_full = tmp_path / "g4_full.json"
    run_scorer_cli(
        rankings_p,
        manifest_p,
        None,
        queries_p,
        out_full,
        removed_audit_spans=rem_p,
        judge_a_path=write_jsonl(tmp_path / "ja_full.jsonl", ja),
        judge_b_path=write_jsonl(tmp_path / "jb_full.jsonl", jb),
        judging_order="ORDER_B",
        expected_pairs_path=ep_p,
        docs_path=docs_p,
        enforce_final50_matrix=True,
    )
    rep_full = read_json(out_full)
    jg = rep_full["judge_gates"]
    assert jg["epistemic_tier"] == "AI_PROXY_DUAL_LLM"
    assert jg["HumanGraded-GoMate-nDCG@10"] == "NOT_PERFORMED"
    ja_c1 = jg["judge_A_by_cell"]["C1-BM25"]
    jb_c1 = jg["judge_B_by_cell"]["C1-BM25"]
    assert jb_c1["error_code_counts"] == {}
    assert jb_c1["state_counts"] == {"REL_0": 2, "REL_1": 1, "REL_2": 1}
    assert ja_c1["error_code_counts"] == {
        "SAFETY_BLOCK_WRONG_CITY_CE9": 1,
        "UNVERIFIED_POSITIVE_QUOTE:PROHIBITED_AUDIT_OR_UNVERIFIED_TAG_OVERLAP": 1,
    }
    assert ja_c1["validated_by_q"][queries[0]["query_id"]]["d-clean"]["confirmed_gain"] == 3
    assert ja_c1["validated_by_q"][queries[1]["query_id"]]["d-neg"]["confirmed_gain"] == 3
    assert ja_c1["validated_by_q"][queries[0]["query_id"]]["d-wc"]["confirmed_gain"] == 0
    assert ja_c1["validated_by_q"][queries[0]["query_id"]]["d-tag"]["confirmed_gain"] == 0
    assert not report_contains_token(rep_full, "G5 PASS")

    out_halt = tmp_path / "g4_halt.json"
    proc_halt = run_scorer_cli(
        rankings_p,
        manifest_p,
        None,
        queries_p,
        out_halt,
        judge_a_path=write_jsonl(tmp_path / "ja_halt.jsonl", ja[:-1]),
        judge_b_path=write_jsonl(tmp_path / "jb_halt.jsonl", jb),
        judging_order="ORDER_B",
        expected_pairs_path=ep_p,
        docs_path=docs_p,
        enforce_final50_matrix=True,
        check=False,
    )
    assert is_blocked_or_invalid_status(proc_halt, out_halt)
    rep_halt = read_json(out_halt)
    assert (
        rep_halt["judge_gates"]["judge_A_by_cell"]["C1-BM25"]["status"]
        == "INCOMPLETE_SEALED_JUDGE_COVERAGE_HALT"
    )
    assert rep_halt["judge_gates"]["judge_A_by_cell"]["C1-BM25"]["confirmable"] is False


def test_t4_07_pre_freeze_governance_offline_fail_closed_and_safety_audit(tmp_path: Path) -> None:
    """T4-07: Pre-Freeze Governance, Offline Fail-Closed & Unanswerable Safety Audit."""
    require_retrieval_cli()
    require_scorer_cli()
    docs = [
        make_b1b_doc("d-ans", "Đền Ngọc Sơn", "Đền Ngọc Sơn tại Hà Nội mở cửa từ 08:00 sáng hàng ngày.", poi_id="syn-poi-hn-01"),
        make_b1b_doc("d-lure", "Bãi Cháy", "Thông tin bãi biển Bãi Cháy [CONFLICT: FC-001 tạm ẩn giá vé].", poi_id="syn-poi-hl-02", city="Hạ Long"),
        make_b1b_doc("d-clean-neg", "Công viên", "Công viên cây xanh miễn phí vào cửa cho người dân.", poi_id="syn-poi-hn-02"),
    ]
    queries = [
        make_query_row("QA-1", "Đền Ngọc Sơn mở cửa mấy giờ?", target_poi_ids=["syn-poi-hn-01"]),
        make_query_row("QU-NONLURE", "giá vé tàu ngầm thám hiểm?", query_family="S5_UNANSWERABLE_OR_UNSTABLE", pre_rank_answerability="UNANSWERABLE", target_poi_ids=["syn-poi-hn-02"]),
        make_query_row("QU-LURE", "giá vé FC-001 Bãi Cháy?", query_family="S5_UNANSWERABLE_OR_UNSTABLE", pre_rank_answerability="UNANSWERABLE", target_city="Hạ Long", target_poi_ids=["syn-poi-hl-02"]),
    ]
    qrels = [
        make_qrel_row("QA-1", "d-ans", "REL_2"),
        make_qrel_row("QA-1", "d-lure", "REL_0"),
        make_qrel_row("QA-1", "d-clean-neg", "REL_0"),
        make_qrel_row("QU-NONLURE", "d-ans", "REL_0", plausible_unsupported_lure=0),
        make_qrel_row("QU-NONLURE", "d-lure", "REL_0", plausible_unsupported_lure=0),
        make_qrel_row("QU-NONLURE", "d-clean-neg", "REL_0", plausible_unsupported_lure=0),
        make_qrel_row("QU-LURE", "d-ans", "REL_0", plausible_unsupported_lure=0),
        make_qrel_row("QU-LURE", "d-lure", "REL_0", plausible_unsupported_lure=1),
        make_qrel_row("QU-LURE", "d-clean-neg", "REL_0", plausible_unsupported_lure=0),
    ]
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", queries)
    qrels_p = write_jsonl(tmp_path / "qrels.jsonl", qrels)
    out_dir = tmp_path / "g3"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-BM25", "C1-Dense", "C1-RRF"])
    rep_p = tmp_path / "g4.json"
    run_scorer_cli(
        out_dir / "g3_sealed_rankings_v1.jsonl",
        out_dir / "g3_sealed_rankings_v1_manifest.json",
        qrels_p,
        queries_p,
        rep_p,
    )
    rep = read_json(rep_p)
    assert not report_contains_token(rep, "CorrectAbstentionRate")
    dense_u = extract_unanswerable_map(rep).get("C1-Dense", extract_cells_map(rep)["C1-Dense"])
    assert float(extract_metric_value(dense_u, ["any_result_at_10", "AnyResult@10", "any_result_10"])) == pytest.approx(1.0)
    assert 0.0 < float(extract_metric_value(dense_u, ["false_support_exposure_at_10", "FalseSupportExposure@10", "false_support_exposure_10"])) <= 1.0

    # Invalid snapshot fails closed without MockEmbedder fallback
    bad_snap = run_retrieval_cli(
        corpus_p,
        queries_p,
        tmp_path / "g3_bad",
        cells=["C1-Dense"],
        snapshot_dir=tmp_path / "missing_snap",
        check=False,
    )
    assert bad_snap.returncode != 0

    # Verify wanderai untouched
    head = subprocess.check_output(
        ["git", "-C", str(WANDERAI_ROOT), "rev-parse", "HEAD"], text=True, encoding="utf-8"
    ).strip()
    assert head == WANDERAI_EXPECTED_HEAD
