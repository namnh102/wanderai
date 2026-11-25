"""Tier 3 Opaque-Box E2E Tests — Cross-Feature Pairwise Combinatorial (14 tests).

Covers `T3-01..T3-14` across all 12 features in PROJECT.md § Feature Inventory.
"""

from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path
from typing import Any, Dict, List

import pytest

from .conftest import (
    BLIND_PACKET_KEYS,
    PROHIBITED_G4_MODULES,
    REPO_ROOT,
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
    require_real_corpus_stubs,
    require_retrieval_cli,
    require_scorer_cli,
    rows_for_cell_query,
    run_pytest_subprocess,
    run_python_probe,
    run_retrieval_cli,
    run_scorer_cli,
    scorer_supports_flag,
)
from .synthetic_builders import (
    find_span,
    make_5x3_query_matrix,
    make_b1b_doc,
    make_judge_record,
    make_multi_level_doc,
    make_overture_doc,
    make_qrel_row,
    make_query_row,
    split_span_excluding_removed,
    tamper_one_byte,
    write_jsonl,
    write_synthetic_sealed_rankings,
)


def test_t3_01_canonical_headings_x_sanitizer_r_audit(tmp_path: Path) -> None:
    """T3-01: Feature #1 Canonical S & Headings x Feature #2 Sanitizer R_AUDIT."""
    require_retrieval_cli()
    six_tag = (
        "[CORROBORATED: canonical_poi:12345678-1234-1234-1234-1234567890ab, "
        "osm:node/12, wikidata:Q34, wikipedia:vi:Hà_Nội, "
        "wikivoyage:en:Hanoi#See, osm_website_pointer:https://example.org/p]"
    )
    body_child = f"Cổng Tam Quan {six_tag} xây dựng cổ kính [1] [UNVERIFIED: note]."
    text_s = (
        "== Kiến trúc ==\n"
        f"=== Cổng Tam Quan ===\n{body_child}\n"
        "== Xem thêm ==\n\n"
        "== Ghi chú riêng ==\n"
    )
    r_start = text_s.index(six_tag)
    r_end = r_start + len(six_tag)
    doc = make_b1b_doc("doc-t3-01", "Chùa Mẫu", text_s)
    q = make_query_row("Q-T3-01", "Cổng Tam Quan cổ kính", requested_facet_keywords=["Cổng Tam Quan"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", [doc])
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-BM25"], packet_salt="T301")
    chunks = read_jsonl(out_dir / "chunks_manifest.jsonl")
    joined = "\n".join(c["assembled_text"] for c in chunks)
    assert "Kiến trúc > Cổng Tam Quan" in joined
    assert "Xem thêm" not in joined
    assert "Ghi chú riêng" in joined

    row = rows_for_cell_query(read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl"), "C1-BM25", "Q-T3-01")[0]
    assert "[CORROBORATED" not in row["assembled_text"]
    assert "[1]" in row["assembled_text"]
    assert "[UNVERIFIED: note]" in row["assembled_text"]
    assert "Cổng Tam Quan  xây dựng" in row["assembled_text"]
    for sa, sb in row["c_full_s_spans"]:
        assert max(sa, r_start) >= min(sb, r_end)


def test_t3_02_r_audit_x_c0_c1_chunker_visible_evidence_span_hit(tmp_path: Path) -> None:
    """T3-02: Feature #2 R_AUDIT x Feature #3 C0/C1 -> Feature #10 VisibleEvidenceSpanHit."""
    require_retrieval_cli()
    require_scorer_cli()
    four_tag = (
        "[CORROBORATED: canonical_poi:12345678-1234-1234-1234-1234567890ab, "
        "osm:way/99, wikidata:Q88, osm_website_pointer:https://example.org/m]"
    )
    filler = "Thông tin lịch sử hình thành và hiện vật trưng bày tại bảo tàng dân tộc học. " * 25
    tail_fact = "Mã lưu trữ đặc biệt cuối trang: ARCHIVE-TAIL-9981."
    doc, rem = make_overture_doc(
        "doc-t3-02",
        "ARCHIVE-TAIL-9981",
        [
            ("Giờ mở cửa ", four_tag),
            (" từ 08:30 đến 17:30 hàng ngày.\n" + filler + tail_fact, None),
        ],
        confidence=0.88,
    )
    text_s = doc["canonical_text_S"]
    early_sub = split_span_excluding_removed(
        0, text_s.index("17:30 hàng ngày.") + len("17:30 hàng ngày."), rem
    )
    tail_idx = text_s.rindex("ARCHIVE-TAIL-9981")
    tail_span = [[tail_idx, tail_idx + len("ARCHIVE-TAIL-9981")]]

    q_early = make_query_row(
        "Q-EARLY",
        "Giờ mở cửa từ 08:30 đến 17:30",
        requested_facet_keywords=["08:30", "17:30"],
        required_evidence_facets=[[{"document_id": "doc-t3-02", "s_spans": early_sub}]],
    )
    q_tail = make_query_row(
        "Q-TAIL",
        "ARCHIVE-TAIL-9981",
        requested_facet_keywords=["ARCHIVE-TAIL-9981"],
        required_evidence_facets=[[{"document_id": "doc-t3-02", "s_spans": tail_span}]],
    )
    qrels = [
        make_qrel_row("Q-EARLY", "doc-t3-02", "REL_2", evidence_s_spans=early_sub),
        make_qrel_row("Q-TAIL", "doc-t3-02", "REL_2", evidence_s_spans=tail_span),
    ]
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", [doc])
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q_early, q_tail])
    qrels_p = write_jsonl(tmp_path / "qrels.jsonl", qrels)
    out_dir = tmp_path / "out"

    run_retrieval_cli(
        corpus_p, queries_p, out_dir, cells=["C0-Dense", "C1-Dense"], packet_salt="T302"
    )
    tok = cached_minilm_tokenizer()
    for ch in read_jsonl(out_dir / "chunks_manifest.jsonl"):
        if ch.get("chunker") == "C1":
            assert len(tok.encode(ch["assembled_text"], add_special_tokens=True, truncation=False)) <= 128

    c1_early = rows_for_cell_query(
        read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl"), "C1-Dense", "Q-EARLY"
    )[0]
    for sa, sb in c1_early["c_vis_s_spans"]:
        for ra, rb in rem:
            assert max(sa, ra) >= min(sb, rb)

    # Evaluate Q-TAIL separately to check C0-Dense vs C1-Dense visibility
    q_tail_p = write_jsonl(tmp_path / "q_tail.jsonl", [q_tail])
    qrels_tail_p = write_jsonl(tmp_path / "qrels_tail.jsonl", [qrels[1]])
    rep_tail = tmp_path / "g4_tail.json"
    run_scorer_cli(
        out_dir / "g3_sealed_rankings_v1.jsonl",
        out_dir / "g3_sealed_rankings_v1_manifest.json",
        qrels_tail_p,
        q_tail_p,
        rep_tail,
    )
    cells_tail = extract_cells_map(read_json(rep_tail))
    assert float(extract_metric_value(cells_tail["C0-Dense"], ["EvidenceSpanHit@10", "evidence_span_hit_10"])) == pytest.approx(1.0)
    assert float(extract_metric_value(cells_tail["C0-Dense"], ["VisibleEvidenceSpanHit@10", "visible_evidence_span_hit_10"])) == pytest.approx(0.0)
    assert float(extract_metric_value(cells_tail["C1-Dense"], ["VisibleEvidenceSpanHit@10", "visible_evidence_span_hit_10"])) == pytest.approx(1.0)


def test_t3_03_utf8_nfc_nfd_x_bm25_underthesea_analyzer(tmp_path: Path) -> None:
    """T3-03: Feature #1 UTF-8 Bijection / NFC x Feature #4 BM25 Analyzer."""
    require_retrieval_cli()
    s_nfc = "Hồ Hoàn Kiếm có đặc sản phở bò 45.000 đồng."
    s_nfd = "Hô\u0300 Hoa\u0300n Kiê\u0301m co\u0301 đă\u0323c sa\u0309n phơ\u0309 bo\u0300 45.000 đô\u0300ng."
    docs = [
        make_b1b_doc("doc_nfc", "Hà Nội", s_nfc),
        make_b1b_doc("doc_nfd", "Hà Nội", s_nfd),
    ]
    q = make_query_row(
        "Q-T3-03",
        "hô\u0300 hoa\u0300n kiê\u0301m phơ\u0309 bo\u0300",
        requested_facet_keywords=["phở bò"],
    )
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-BM25"])
    rows = rows_for_cell_query(read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl"), "C1-BM25", "Q-T3-03")
    assert [r["document_id"] for r in rows] == ["doc_nfc", "doc_nfd"]
    assert abs(rows[0]["score"] - rows[1]["score"]) < 1e-9
    for r, raw_s in zip(rows, (s_nfc, s_nfd)):
        b_all = raw_s.encode("utf-8")
        for sa, sb in r["c_full_s_spans"]:
            b_a = len(raw_s[:sa].encode("utf-8"))
            b_b = len(raw_s[:sb].encode("utf-8"))
            assert b_all[b_a:b_b].decode("utf-8") == raw_s[sa:sb]


def test_t3_04_c0_short_fragment_drop_x_bm25_positive_filter(tmp_path: Path) -> None:
    """T3-04: Feature #3 C0 <10-word Drop x Feature #4 BM25 >0 Filter."""
    require_retrieval_cli()
    long_intro = " ".join(f"chủđề{i}" for i in range(1, 41)) + "."
    doc = make_multi_level_doc(
        "doc-t3-04",
        "Địa điểm",
        [
            (2, "Tổng quan", long_intro),
            (2, "Giá vé", "Giá vé vào cổng 30.000 đồng mỗi lượt."),
        ],
    )
    q = make_query_row("Q-T3-04", "giá vé vào cổng 30.000", requested_facet_keywords=["30.000"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", [doc])
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C0-BM25", "C1-BM25"])
    all_rows = read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl")
    assert rows_for_cell_query(all_rows, "C0-BM25", "Q-T3-04") == []
    c1_rows = rows_for_cell_query(all_rows, "C1-BM25", "Q-T3-04")
    assert len(c1_rows) == 1 and c1_rows[0]["score"] > 0.0


def test_t3_05_c1_chunking_x_offline_dense_and_no_mock_embedder(tmp_path: Path) -> None:
    """T3-05: Feature #3 C1 Chunking x Feature #5 Offline Dense & MockEmbedder Block."""
    require_retrieval_cli()
    docs = [
        make_b1b_doc("d1", "Hanoi", "Hồ Hoàn Kiếm là trái tim của thủ đô Hà Nội."),
        make_b1b_doc("d2", "Math", "Differential topology manifold curvature tensor calculations."),
    ]
    q = make_query_row("Q-T3-05", "bãi biển nào đẹp ở Đà Nẵng", requested_facet_keywords=["Đà Nẵng"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-Dense"])
    manifest = read_json(out_dir / "g3_sealed_rankings_v1_manifest.json")
    assert manifest["snapshot_id"] == "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"
    rows = rows_for_cell_query(read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl"), "C1-Dense", "Q-T3-05")
    assert len(rows) == 2

    # Missing snapshot must fail closed without MockEmbedder fallback
    bad_proc = run_retrieval_cli(
        corpus_p,
        queries_p,
        tmp_path / "bad_out",
        cells=["C1-Dense"],
        snapshot_dir=tmp_path / "missing_snap",
        check=False,
    )
    assert bad_proc.returncode != 0

    # MockEmbedder probe must raise RuntimeError
    probe = """
import w07_retrieval.dense as wd
if hasattr(wd, 'MockEmbedder'):
    try:
        wd.MockEmbedder()
    except RuntimeError:
        print('MOCK_BLOCKED')
        raise SystemExit(0)
    raise SystemExit(2)
print('NO_MOCK_CLASS')
"""
    p_mock = run_python_probe(probe)
    assert "MOCK_BLOCKED" in p_mock.stdout or "NO_MOCK_CLASS" in p_mock.stdout


def test_t3_06_bm25_positive_filter_x_doc_collapse_and_hybrid_rrf(tmp_path: Path) -> None:
    """T3-06: Feature #4 BM25 >0 Filter x Feature #6 Doc Collapse & Hybrid RRF."""
    require_retrieval_cli()
    long_secs = [
        (2, f"Mục {i}", f"Bảo tàng nghệ thuật cổ đại phần {i} trưng bày hiện vật quý.")
        for i in range(1, 16)
    ]
    docs: List[Dict[str, Any]] = [make_multi_level_doc("doc_long", "Bảo tàng", long_secs)]
    for i in range(1, 9):
        docs.append(make_b1b_doc(f"doc_bm_{i}", f"D{i}", f"Bảo tàng lịch sử số {i}."))
    for i in range(1, 4):
        docs.append(make_b1b_doc(f"doc_dense_only_{i}", f"O{i}", f"Cơ sở văn hóa trưng bày {i}."))

    q = make_query_row("Q-T3-06", "bảo tàng", requested_facet_keywords=["bảo tàng"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-BM25", "C1-Dense", "C1-RRF"])
    all_rows = read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl")
    dense_rows = rows_for_cell_query(all_rows, "C1-Dense", "Q-T3-06")
    bm25_rows = rows_for_cell_query(all_rows, "C1-BM25", "Q-T3-06")
    rrf_rows = rows_for_cell_query(all_rows, "C1-RRF", "Q-T3-06")

    assert len(dense_rows) == 12
    assert len({r["document_id"] for r in dense_rows}) == 12
    bm25_ids = {r["document_id"] for r in bm25_rows}
    for i in range(1, 4):
        assert f"doc_dense_only_{i}" not in bm25_ids

    dense_ranks = {r["document_id"]: r["rank"] for r in dense_rows}
    for r in rrf_rows:
        if r["document_id"].startswith("doc_dense_only_"):
            assert r["score"] == pytest.approx(1.0 / (60 + dense_ranks[r["document_id"]]), abs=1e-12)


def test_t3_07_hybrid_rrf_rankings_x_blind_packet_rank_invariance(tmp_path: Path) -> None:
    """T3-07: Feature #6 Hybrid RRF x Feature #7 Blind Packet Exporter."""
    require_retrieval_cli()
    docs = [
        make_b1b_doc(
            f"doc-{i:02d}",
            f"Điểm {i}",
            ("ZALPHA " * (11 - i)) + f"tham quan du lịch văn hóa số {i} tại Việt Nam.",
        )
        for i in range(1, 11)
    ]
    q = make_query_row("Q-T3-07", "ZALPHA du lịch văn hóa", requested_facet_keywords=["du lịch"])
    c_p = write_jsonl(tmp_path / "corpus.jsonl", docs)
    q_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out1 = tmp_path / "run1"
    out2 = tmp_path / "run2"

    run_retrieval_cli(c_p, q_p, out1, cells=["C1-BM25"], packet_salt="TEST_SALT")
    run_retrieval_cli(c_p, q_p, out2, cells=["C1-Dense"], packet_salt="TEST_SALT")
    assert file_sha256(out1 / "blind_annotation_packet.jsonl") == file_sha256(
        out2 / "blind_annotation_packet.jsonl"
    )
    for r in read_jsonl(out1 / "blind_annotation_packet.jsonl"):
        assert set(r.keys()) == BLIND_PACKET_KEYS


def test_t3_08_sealed_g3_manifest_x_g4_scorer_tamper_and_sys_modules(tmp_path: Path) -> None:
    """T3-08: Feature #6 Sealed G3 Manifest x Feature #10 Decoupled G4 Scorer."""
    require_retrieval_cli()
    require_scorer_cli()
    docs = [make_b1b_doc("d1", "D1", "Bảo tàng mở cửa 08:00."), make_b1b_doc("d2", "D2", "Công viên.")]
    q = make_query_row("Q1", "Bảo tàng mở cửa", requested_facet_keywords=["08:00"])
    qrels = [make_qrel_row("Q1", "d1", "REL_2"), make_qrel_row("Q1", "d2", "REL_0")]
    c_p = write_jsonl(tmp_path / "corpus.jsonl", docs)
    q_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    qr_p = write_jsonl(tmp_path / "qrels.jsonl", qrels)
    out_dir = tmp_path / "g3"

    run_retrieval_cli(c_p, q_p, out_dir, cells=["C1-BM25"])
    rep_p = tmp_path / "g4_clean.json"
    run_scorer_cli(
        out_dir / "g3_sealed_rankings_v1.jsonl",
        out_dir / "g3_sealed_rankings_v1_manifest.json",
        qr_p,
        q_p,
        rep_p,
    )
    assert rep_p.is_file()

    # Check sys.modules clean in subprocess running scorer
    probe = f"""
import sys
import w07_g4_scorer.scorer as sc
sc.main([
    "--rankings", {str(out_dir / "g3_sealed_rankings_v1.jsonl")!r},
    "--manifest", {str(out_dir / "g3_sealed_rankings_v1_manifest.json")!r},
    "--qrels", {str(qr_p)!r},
    "--queries", {str(q_p)!r},
    "--output", {str(tmp_path / "g4_probe.json")!r},
])
banned = {sorted(PROHIBITED_G4_MODULES)!r}
leaked = [m for m in banned if m in sys.modules]
assert not leaked, f"Prohibited modules imported: {{leaked}}"
print("SYS_MODULES_CLEAN")
"""
    p_clean = run_python_probe(probe)
    assert "SYS_MODULES_CLEAN" in p_clean.stdout

    # 1-byte tamper must fail immediately
    tamper_one_byte(out_dir / "g3_sealed_rankings_v1.jsonl")
    tamper_out = tmp_path / "g4_tampered.json"
    bad = run_scorer_cli(
        out_dir / "g3_sealed_rankings_v1.jsonl",
        out_dir / "g3_sealed_rankings_v1_manifest.json",
        qr_p,
        q_p,
        tamper_out,
        check=False,
    )
    assert bad.returncode != 0
    assert not tamper_out.exists()


def test_t3_09_d01_5x3_matrix_and_step_s0_x_g4_scorer(tmp_path: Path) -> None:
    """T3-09: Feature #8 D01 5x3 Matrix & Step S0 x Feature #10 G4 Scorer."""
    require_scorer_cli()
    valid_50 = make_5x3_query_matrix(split="FINAL", question_origin="INDEPENDENT_HUMAN")
    q_p = write_jsonl(tmp_path / "valid50.jsonl", valid_50)

    # Check exact 5x3 validator passes valid matrix and rejects marginal-preserving swap
    swapped = make_5x3_query_matrix(split="FINAL", question_origin="INDEPENDENT_HUMAN")
    s1_hn = next(q for q in swapped if q["query_family"] == "S1_STRUCTURED_FACT" and q["target_city"] == "Hà Nội")
    s2_dn = next(q for q in swapped if q["query_family"] == "S2_NARRATIVE_ADVISORY" and q["target_city"] == "Đà Nẵng")
    s1_hn["target_city"] = "Đà Nẵng"
    s1_hn["target_poi_ids"] = ["syn-poi-dn-01"]
    s2_dn["target_city"] = "Hà Nội"
    s2_dn["target_poi_ids"] = ["syn-poi-hn-01"]
    swap_p = write_jsonl(tmp_path / "swapped50.jsonl", swapped)

    docs = {"d1": make_b1b_doc("d1", "D1", "Văn bản.")}
    r_p, m_p = write_synthetic_sealed_rankings(
        tmp_path / "g3", {("C1-BM25", q["query_id"]): [("d1", 1.0)] for q in swapped}, docs
    )
    qr_p = write_jsonl(
        tmp_path / "qr.jsonl", [make_qrel_row(q["query_id"], "d1", "REL_2") for q in swapped]
    )
    bad_swap = run_scorer_cli(
        r_p, m_p, qr_p, swap_p, tmp_path / "g4_swap.json", enforce_final50_matrix=True, check=False
    )
    assert bad_swap.returncode != 0

    # Missing scope_mode or SYNTHETIC_DISCLOSED in FINAL fails closed
    bad_s0 = make_5x3_query_matrix(split="FINAL", question_origin="INDEPENDENT_HUMAN")
    bad_s0[0].pop("scope_mode")
    bad_s0_p = write_jsonl(tmp_path / "bad_s0.jsonl", bad_s0)
    bad_proc = run_scorer_cli(
        r_p, m_p, qr_p, bad_s0_p, tmp_path / "g4_s0.json", enforce_final50_matrix=True, check=False
    )
    assert bad_proc.returncode != 0

    probe = f"""
import json, pathlib
import w07_g4_scorer.query_manifest as qm
rows = [json.loads(l) for l in pathlib.Path({str(q_p)!r}).read_text(encoding='utf-8').splitlines() if l.strip()]
qm.validate_final50_strata_and_city_quota(rows)
print('VALID_5X3')
"""
    assert "VALID_5X3" in run_python_probe(probe).stdout


def test_t3_10_auto_eval_judge_gates_x_g4_scorer(tmp_path: Path) -> None:
    """T3-10: Feature #8 AUTO-EVAL Judge Gates x Feature #9/#10 G4 Scorer."""
    require_scorer_cli()
    s_ok = "Bảo tàng mở cửa bình thường."
    s_neg = "Bảo tàng không mở cửa thứ Hai."
    s_tag, _ = make_overture_doc(
        "d_tag", "D", [("Giờ ", "[CORROBORATED: osm:node/1]"), (" mở cửa.", None)], confidence=None
    )
    docs = {
        "d_wrong_city": make_b1b_doc("d_wrong_city", "W", s_ok, poi_id="syn-poi-hn-01", city="Đà Nẵng"),
        "d_neg": make_b1b_doc("d_neg", "N", s_neg, poi_id="syn-poi-hn-01", city="Hà Nội"),
        "d_tag": s_tag,
    }
    q_aff = make_query_row("Q-AFF", "Mở cửa?", target_poi_ids=["syn-poi-hn-01"], target_city="Hà Nội", query_intent_polarity="AFFIRMATIVE_FACT_NEED", requested_facet_keywords=["mở cửa"])
    q_bool = make_query_row("Q-BOOL", "Có mở cửa thứ Hai?", target_poi_ids=["syn-poi-hn-01"], target_city="Hà Nội", query_intent_polarity="BOOLEAN_ELIGIBILITY_OR_POLICY_CHECK", requested_facet_keywords=["mở cửa"])

    probe = f"""
import json
import w07_g4_scorer.judge_gates as jg

docs = {json.dumps({k: {"canonical_text_S": v["canonical_text_S"], "city": v["city"], "poi_id": v["poi_id"]} for k, v in docs.items()}, ensure_ascii=False)}
q_aff = {json.dumps(q_aff, ensure_ascii=False)}
q_bool = {json.dumps(q_bool, ensure_ascii=False)}

# (i) CE9 wrong city
r1 = jg.validate_judge_response(json.dumps({{"grade": "REL_2", "evidence_quote": {s_ok!r}, "char_start": 0, "char_end": {len(s_ok)}, "rationale": "ok"}}), docs["d_wrong_city"], [], q_aff)
assert r1["state"] == "ERROR" and r1["confirmed_gain"] == 0 and "CE9" in r1["error_code"]

# (ii) CE4 affirmative + N2
r2 = jg.validate_judge_response(json.dumps({{"grade": "REL_2", "evidence_quote": "không mở cửa", "char_start": 9, "char_end": 21, "rationale": "ok"}}), docs["d_neg"], [], q_aff)
assert r2["state"] == "ERROR" and r2["confirmed_gain"] == 0 and "CE4" in r2["error_code"]

# (iii) CE4 boolean + N2 preserved
r3 = jg.validate_judge_response(json.dumps({{"grade": "REL_2", "evidence_quote": "không mở cửa", "char_start": 9, "char_end": 21, "rationale": "ok"}}), docs["d_neg"], [], q_bool)
assert r3["confirmed_gain"] == 3

# (iv) G-SPAN overlapping R_AUDIT
tag_txt = "[CORROBORATED: osm:node/1]"
s_t = docs["d_tag"]["canonical_text_S"]
r4 = jg.validate_judge_response(json.dumps({{"grade": "REL_2", "evidence_quote": tag_txt, "char_start": s_t.index(tag_txt), "char_end": s_t.index(tag_txt)+len(tag_txt), "rationale": "ok"}}), docs["d_tag"], [(s_t.index(tag_txt), s_t.index(tag_txt)+len(tag_txt))], q_aff)
assert r4["state"] == "ERROR" and r4["confirmed_gain"] == 0

# (v) ORDER_B missing 1 expected pair halts
expected = [("Q-BOOL", "d_neg"), ("Q-AFF", "d_neg")]
ja = {{("Q-BOOL", "d_neg"): json.dumps({{"grade": "REL_2", "evidence_quote": "không mở cửa", "char_start": 9, "char_end": 21, "rationale": "ok"}})}}
jb = {{
    ("Q-BOOL", "d_neg"): ja[("Q-BOOL", "d_neg")],
    ("Q-AFF", "d_neg"): json.dumps({{"grade": "REL_0", "evidence_quote": "", "char_start": None, "char_end": None, "rationale": "ok"}}),
}}
rep = jg.evaluate_dual_judge_concordance(
    queries_meta=[q_aff, q_bool],
    docs_by_id=docs,
    removed_by_doc_id={{}},
    rankings_by_cell={{"C1-BM25": {{"Q-BOOL": ["d_neg"], "Q-AFF": ["d_neg"]}}}},
    judge_a_responses=ja,
    judge_b_responses=jb,
    judging_order="ORDER_B",
    sealed_expected_pairs=expected,
)
assert rep["judge_A_by_cell"]["C1-BM25"]["status"] == "INCOMPLETE_SEALED_JUDGE_COVERAGE_HALT"
assert rep["judge_A_by_cell"]["C1-BM25"]["confirmable"] is False
print("T3_10_OK")
"""
    assert "T3_10_OK" in run_python_probe(probe).stdout


def test_t3_11_shared_lineage_non_propagation_x_cert2_and_cert4(tmp_path: Path) -> None:
    """T3-11: Feature #9 Shared-Lineage Non-Propagation x Cert-2 & Cert-4 (FX-10)."""
    require_scorer_cli()
    docs = {
        "sib_a": make_b1b_doc("sib_a", "A", "Nội dung A", source_lineage_id="wikivoyage:en:Hanoi"),
        "sib_b": make_b1b_doc("sib_b", "B", "Nội dung B", source_lineage_id="wikivoyage:en:Hanoi"),
    }
    queries = [make_query_row("Q1", "q1")]
    r_p, m_p = write_synthetic_sealed_rankings(
        tmp_path / "g3", {("C1-RRF", "Q1"): [("sib_a", 2.0), ("sib_b", 1.0)]}, docs
    )
    q_p = write_jsonl(tmp_path / "queries.jsonl", queries)

    # Case A: sib_b UNJUDGED -> blocks G4 confirmation
    qr_a = write_jsonl(
        tmp_path / "qrels_a.jsonl",
        [
            make_qrel_row("Q1", "sib_a", "REL_2", source_lineage_id="wikivoyage:en:Hanoi"),
            make_qrel_row("Q1", "sib_b", "UNJUDGED", source_lineage_id="wikivoyage:en:Hanoi"),
        ],
    )
    out_a = tmp_path / "g4_a.json"
    proc_a = run_scorer_cli(r_p, m_p, qr_a, q_p, out_a, check=False)
    assert is_blocked_or_invalid_status(proc_a, out_a)

    # Case B: both independently REL_2 -> passes Cert-2, epistemic_lineage_count == 1
    qr_b = write_jsonl(
        tmp_path / "qrels_b.jsonl",
        [
            make_qrel_row("Q1", "sib_a", "REL_2", source_lineage_id="wikivoyage:en:Hanoi"),
            make_qrel_row("Q1", "sib_b", "REL_2", source_lineage_id="wikivoyage:en:Hanoi"),
        ],
    )
    out_b = tmp_path / "g4_b.json"
    run_scorer_cli(r_p, m_p, qr_b, q_p, out_b)
    rep_b = read_json(out_b)
    c1_rrf = extract_cells_map(rep_b)["C1-RRF"]
    assert float(c1_rrf["epistemic_lineage_mean_at_10"]) == pytest.approx(1.0)
    assert float(rep_b["certificates"]["cert2_pass_rate"]) == pytest.approx(1.0)


def test_t3_12_cert4_bounded_not_exact_x_coupled_bounds_and_holm_k1_k5(tmp_path: Path) -> None:
    """T3-12: Feature #9 BOUNDED_NOT_EXACT x Feature #10 Coupled Bounds & Holm K1..K5."""
    require_scorer_cli()
    docs = {f"d{i}": make_b1b_doc(f"d{i}", f"D{i}", f"T{i}") for i in range(1, 6)}
    queries = [make_query_row(f"Q{i}", f"q{i}") for i in range(1, 4)]
    rank_map = {
        ("C1-RRF", "Q1"): [("d1", 3.0), ("d2", 2.0)],
        ("C1-BM25", "Q1"): [("d2", 3.0), ("d1", 2.0)],
        ("C1-RRF", "Q2"): [("d3", 3.0), ("d4", 2.0)],
        ("C1-BM25", "Q2"): [("d1", 3.0), ("d3", 2.0)],
        ("C1-RRF", "Q3"): [("d3", 3.0), ("d4", 2.0)],
        ("C1-BM25", "Q3"): [("d1", 3.0), ("d3", 2.0)],
    }
    qrels = [
        make_qrel_row("Q1", "d1", "REL_2"),
        make_qrel_row("Q1", "d2", "REL_0"),
        make_qrel_row("Q1", "d3", "REL_0"),
        make_qrel_row("Q1", "d4", "REL_0"),
        make_qrel_row("Q1", "d5", "REL_0"),
    ]
    for qid in ("Q2", "Q3"):
        qrels.extend(
            [
                make_qrel_row(qid, "d1", "REL_2"),
                make_qrel_row(qid, "d2", "REL_0"),
                make_qrel_row(qid, "d3", "REL_0"),
                make_qrel_row(qid, "d4", "REL_0"),
                make_qrel_row(qid, "d5", "UNJUDGED"),
            ]
        )
    r_p, m_p = write_synthetic_sealed_rankings(tmp_path / "g3", rank_map, docs)
    out_p = tmp_path / "g4.json"
    run_scorer_cli(
        r_p,
        m_p,
        write_jsonl(tmp_path / "qrels.jsonl", qrels),
        write_jsonl(tmp_path / "queries.jsonl", queries),
        out_p,
    )
    rep = read_json(out_p)
    assert rep["headline_status"] == "NO_EXACT_FULL_SET_ESTIMATE"
    k1 = extract_contrasts_map(rep)["K1"]
    assert k1["decision"] == "NO_CLEAR_WINNER"
    p_holm = extract_metric_value(k1, ["p_mc_holm", "p_holm", "holm_p_value"])
    assert p_holm is not None and not math.isnan(float(p_holm))


def test_t3_13_unanswerable_lures_x_winner_gate_and_g5_lock(tmp_path: Path) -> None:
    """T3-13: Feature #10 Unanswerable Lures x Winner Gate & G5 Lock (FX-16)."""
    require_scorer_cli()
    docs = {f"d{i}": make_b1b_doc(f"d{i}", f"D{i}", f"T{i}") for i in range(1, 5)}
    ans_qs = [make_query_row(f"QA-{i:02d}", f"ans {i}") for i in range(1, 21)]
    unans_qs = [
        make_query_row("QU-01", "u1", query_family="S5_UNANSWERABLE_OR_UNSTABLE", pre_rank_answerability="UNANSWERABLE"),
        make_query_row("QU-02", "u2", query_family="S5_UNANSWERABLE_OR_UNSTABLE", pre_rank_answerability="UNANSWERABLE"),
    ]
    rank_map: Dict[tuple[str, str], List[tuple[str, float]]] = {}
    qrels: List[Dict[str, Any]] = []
    for q in ans_qs:
        rank_map[("C1-Dense", q["query_id"])] = [("d1", 2.0), ("d2", 1.0)]
        rank_map[("C0-Dense", q["query_id"])] = [("d2", 2.0), ("d1", 1.0)]
        qrels.extend([make_qrel_row(q["query_id"], f"d{i}", "REL_2" if i == 1 else "REL_0") for i in range(1, 5)])

    # QU-01: C1-Dense surfaces lure d3 (lure=1); QU-02: C1-Dense surfaces non-lure d4 (lure=0)
    rank_map[("C1-Dense", "QU-01")] = [("d3", 2.0)]
    rank_map[("C0-Dense", "QU-01")] = [("d4", 2.0)]
    rank_map[("C1-Dense", "QU-02")] = [("d4", 2.0)]
    rank_map[("C0-Dense", "QU-02")] = [("d4", 2.0)]
    for uq in unans_qs:
        qrels.extend(
            [
                make_qrel_row(uq["query_id"], "d1", "REL_0", plausible_unsupported_lure=0),
                make_qrel_row(uq["query_id"], "d2", "REL_0", plausible_unsupported_lure=0),
                make_qrel_row(uq["query_id"], "d3", "REL_0", plausible_unsupported_lure=1),
                make_qrel_row(uq["query_id"], "d4", "REL_0", plausible_unsupported_lure=0),
            ]
        )

    r_p, m_p = write_synthetic_sealed_rankings(tmp_path / "g3", rank_map, docs)
    out_p = tmp_path / "g4.json"
    run_scorer_cli(
        r_p,
        m_p,
        write_jsonl(tmp_path / "qrels.jsonl", qrels),
        write_jsonl(tmp_path / "queries.jsonl", ans_qs + unans_qs),
        out_p,
    )
    rep = read_json(out_p)
    assert not report_contains_token(rep, "CorrectAbstentionRate")
    assert not report_contains_token(rep, "G5 PASS")
    assert extract_contrasts_map(rep)["K3"]["decision"] == "NO_CLEAR_WINNER"
    c1_u = extract_unanswerable_map(rep).get("C1-Dense", extract_cells_map(rep)["C1-Dense"])
    assert float(extract_metric_value(c1_u, ["any_result_at_10", "AnyResult@10", "any_result_10"])) == pytest.approx(1.0)
    assert float(extract_metric_value(c1_u, ["false_support_exposure_at_10", "FalseSupportExposure@10", "false_support_exposure_10"])) == pytest.approx(0.5)


def test_t3_14_real_corpus_gating_x_non_mutation_and_offline_isolation() -> None:
    """T3-14: Feature #11 Real-Corpus Gating x Feature #12 Non-Mutation & Offline Isolation."""
    stub = require_real_corpus_stubs()
    proc = run_pytest_subprocess([stub], extra_args=["-rs", "-m", "real_corpus_gated"])
    assert proc.returncode == 0
    assert "failed" not in proc.stdout.lower()
    assert "5 skipped" in proc.stdout.lower()

    head = subprocess.check_output(
        ["git", "-C", str(WANDERAI_ROOT), "rev-parse", "HEAD"], text=True, encoding="utf-8"
    ).strip()
    assert head == WANDERAI_EXPECTED_HEAD
    status_lines = [
        line
        for line in subprocess.check_output(
            ["git", "-C", str(WANDERAI_ROOT), "status", "--porcelain=v1", "-uall"],
            text=True,
            encoding="utf-8",
        ).splitlines()
        if line.strip()
    ]
    assert len(status_lines) == 4
    assert all(line.startswith("?? docs/research/W07_B2_") for line in status_lines)
