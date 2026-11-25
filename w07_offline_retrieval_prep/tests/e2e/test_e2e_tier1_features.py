"""Tier 1 Opaque-Box E2E Tests — Feature Coverage (60 tests: 5 per feature x 12).

Covers all 12 features in PROJECT.md § Feature Inventory (`T1-F01-01..T1-F12-05`).
All tests execute purely through subprocess CLIs or isolated probes over
synthetic fixtures in `tmp_path`, with zero white-box imports.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
import zipfile
from pathlib import Path
from typing import Any, Dict, List

import pytest

from .conftest import (
    ALL_SIX_CELLS,
    BLIND_PACKET_KEYS,
    HF_SNAPSHOT_DIR,
    PROHIBITED_G4_MODULES,
    RANKING_ROW_KEYS,
    REPO_ROOT,
    TOKENIZER_SHA256,
    WANDERAI_EXPECTED_HEAD,
    cached_minilm_tokenizer,
    extract_cells_map,
    extract_contrasts_map,
    extract_metric_value,
    extract_per_query_map,
    extract_unanswerable_map,
    file_sha256,
    read_json,
    read_jsonl,
    report_contains_token,
    require_fx_test_file,
    require_packaging_scripts,
    require_real_corpus_stubs,
    require_retrieval_cli,
    require_scorer_cli,
    rows_for_cell_query,
    run_pytest_subprocess,
    run_python_probe,
    run_retrieval_cli,
    run_scorer_cli,
    scorer_supports_flag,
    _python_exe,
    build_safe_offline_env,
)
from .synthetic_builders import (
    expected_packet_uuid,
    find_span,
    make_5x3_query_matrix,
    make_b1b_doc,
    make_judge_record,
    make_multi_level_doc,
    make_osm_doc,
    make_overture_doc,
    make_poison_pythonpath,
    make_qrel_row,
    make_query_row,
    split_span_excluding_removed,
    write_jsonl,
    write_synthetic_sealed_rankings,
)


def _run_judge_eval_helper(
    tmp_path: Path,
    rankings_path: Path,
    manifest_path: Path,
    queries_path: Path,
    judge_a_rows: List[Dict[str, Any]],
    judge_b_rows: List[Dict[str, Any]],
    docs_by_id: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Execute judge-mode scoring via CLI if supported, else public scorer probe."""
    ja_path = write_jsonl(tmp_path / "judge_a.jsonl", judge_a_rows)
    jb_path = write_jsonl(tmp_path / "judge_b.jsonl", judge_b_rows)
    docs_path = write_jsonl(tmp_path / "docs_meta.jsonl", list(docs_by_id.values()))
    out_path = tmp_path / "g4_judge_report.json"

    if scorer_supports_flag("--judge-a") and scorer_supports_flag("--judge-b"):
        run_scorer_cli(
            rankings_path,
            manifest_path,
            None,
            queries_path,
            out_path,
            judge_a_path=ja_path,
            judge_b_path=jb_path,
            docs_path=docs_path,
        )
        return read_json(out_path)

    # Fallback to public AUTO-EVAL-01 module entrypoint in isolated subprocess
    probe = f"""
import json, pathlib
import w07_g4_scorer.judge_gates as jg

queries = [json.loads(l) for l in pathlib.Path({str(queries_path)!r}).read_text(encoding='utf-8').splitlines() if l.strip()]
q_map = {{q['query_id']: q for q in queries}}
docs = {json.dumps(docs_by_id, ensure_ascii=False)}
ja = [json.loads(l) for l in pathlib.Path({str(ja_path)!r}).read_text(encoding='utf-8').splitlines() if l.strip()]
jb = [json.loads(l) for l in pathlib.Path({str(jb_path)!r}).read_text(encoding='utf-8').splitlines() if l.strip()]

def eval_leg(rows):
    out = []
    for r in rows:
        d = docs[r['document_id']]
        doc_obj = {{'canonical_text_S': d['canonical_text_S'], 'city': d['city'], 'poi_id': d['poi_id']}}
        res = jg.validate_judge_response(r['response'], doc_obj, [], q_map[r['query_id']])
        out.append(res)
    return out

res = {{
    'judge_A': eval_leg(ja),
    'judge_B': eval_leg(jb),
}}
print(json.dumps(res, ensure_ascii=False))
"""
    proc = run_python_probe(probe)
    return json.loads(proc.stdout)


# ===========================================================================
# Feature 1: D03.1-D03.2 Canonical S & Headings (T1-F01-01 .. T1-F01-05)
# ===========================================================================


def test_t1_f01_01_b1b_answer_ready_confirmed_precedence_over_raw(tmp_path: Path) -> None:
    require_retrieval_cli()
    confirmed = "Bảo tàng mẫu mở cửa từ 08:00 đến 17:00 hàng ngày cho khách tham quan."
    doc = make_b1b_doc(
        "doc-f01-01",
        "Bảo tàng mẫu",
        canonical_text_S=None,
        answer_ready_confirmed_text=confirmed,
        raw_text="RAW_NOISE_999 nội dung cũ không được dùng.",
    )
    q = make_query_row("Q-F01-01", "Mở cửa 08:00", requested_facet_keywords=["08:00"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", [doc])
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(
        corpus_p, queries_p, out_dir, cells=["C1-BM25"], packet_salt="F01_SALT"
    )
    rows = read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl")
    assert len(rows) == 1
    assert "08:00" in rows[0]["assembled_text"]
    assert "RAW_NOISE_999" not in rows[0]["assembled_text"]
    chunks_raw = (out_dir / "chunks_manifest.jsonl").read_text(encoding="utf-8")
    assert "RAW_NOISE_999" not in chunks_raw
    for sa, sb in rows[0]["c_full_s_spans"]:
        assert 0 <= sa < sb <= len(confirmed)
        assert confirmed[sa:sb] in rows[0]["assembled_text"]


def test_t1_f01_02_b1b_raw_text_fallback(tmp_path: Path) -> None:
    require_retrieval_cli()
    raw = "Văn Miếu Quốc Tử Giám có 82 bia tiến sĩ lưu danh các bậc hiền tài."
    doc = make_b1b_doc(
        "doc-f01-02",
        "Văn Miếu",
        canonical_text_S=None,
        raw_text=raw,
    )
    q = make_query_row("Q-F01-02", "bia tiến sĩ", requested_facet_keywords=["bia tiến sĩ"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", [doc])
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-BM25"])
    rows = read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl")
    assert len(rows) == 1
    assert "bia tiến sĩ" in rows[0]["assembled_text"]
    assert len(rows[0]["c_full_s_spans"]) >= 1
    for sa, sb in rows[0]["c_full_s_spans"]:
        assert 0 <= sa < sb <= len(raw)


def test_t1_f01_03_osm_structured_doc_canonical_rendering(tmp_path: Path) -> None:
    require_retrieval_cli()
    doc = make_osm_doc(
        "doc-f01-03",
        "Hồ Tây",
        category="nature",
        destination="Hà Nội",
        tags={"natural": "water", "opening_hours": "24/7"},
        source_id="way/555",
        include_place_payload=True,
    )
    q = make_query_row("Q-F01-03", "Hồ Tây mở cửa 24/7", requested_facet_keywords=["24/7"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", [doc])
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-BM25"])
    rows = read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl")
    assert len(rows) == 1
    text = rows[0]["assembled_text"]
    assert "thuộc nhóm thiên nhiên tại Hà Nội." in text
    assert "Giờ mở cửa: 24/7." in text
    assert "Nguồn: OpenStreetMap way/555." in text


def test_t1_f01_04_empty_parent_heading_breadcrumb_propagation(tmp_path: Path) -> None:
    require_retrieval_cli()
    doc = make_multi_level_doc(
        "doc-f01-04",
        "Chùa Mẫu",
        [
            (2, "Kiến trúc", ""),
            (3, "Cổng Tam Quan", "Cổng xây bằng gạch nung cổ kính và gỗ lim truyền thống."),
        ],
        city="Hà Nội",
    )
    q = make_query_row("Q-F01-04", "Cổng Tam Quan gạch nung", requested_facet_keywords=["gạch nung"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", [doc])
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-BM25"])
    rows = read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl")
    assert len(rows) == 1
    row = rows[0]
    assert "Kiến trúc > Cổng Tam Quan" in row["assembled_text"]
    heading_segs = [s for s in row["assembled_segments"] if s["kind"] == "CANONICAL_HEADING_S"]
    assert len(heading_segs) >= 1
    text_s = doc["canonical_text_S"]
    covered_slices = "".join(text_s[a:b] for a, b in row["c_full_s_spans"])
    assert "Kiến trúc" in covered_slices
    assert "Cổng Tam Quan" in covered_slices


def test_t1_f01_05_utf8_multibyte_vietnamese_codepoint_bijection(tmp_path: Path) -> None:
    require_retrieval_cli()
    text_s = (
        "Đền Ngọc Sơn nằm trên đảo Ngọc hồ Hoàn Kiếm tại trung tâm Hà Nội.\n"
        "== Lịch sử ==\n"
        "Công trình được xây dựng vào thế kỷ XIX với kiến trúc truyền thống."
    )
    doc = make_b1b_doc("doc-f01-05", "Đền Ngọc Sơn", text_s)
    q = make_query_row("Q-F01-05", "đảo Ngọc hồ Hoàn Kiếm", requested_facet_keywords=["đảo Ngọc"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", [doc])
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-BM25"])
    rows = read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl")
    assert len(rows) == 1
    s_bytes = text_s.encode("utf-8")
    for sa, sb in rows[0]["c_full_s_spans"]:
        assert 0 <= sa < sb <= len(text_s)
        b_start = len(text_s[:sa].encode("utf-8"))
        b_end = len(text_s[:sb].encode("utf-8"))
        assert b_end - b_start == len(text_s[sa:sb].encode("utf-8"))
        assert s_bytes[b_start:b_end].decode("utf-8") == text_s[sa:sb]


# ===========================================================================
# Feature 2: D03.3 Sanitization S -> V (T1-F02-01 .. T1-F02-05)
# ===========================================================================


def test_t1_f02_01_all_six_r_audit_families_stripped_zero_ws_loss(tmp_path: Path) -> None:
    require_retrieval_cli()
    tag = (
        "[CORROBORATED: canonical_poi:12345678-1234-1234-1234-1234567890ab, "
        "osm:node/12, wikidata:Q34, wikipedia:vi:Hà_Nội, "
        "wikivoyage:en:Hanoi#See, osm_website_pointer:https://example.org/p]"
    )
    doc, _ = make_overture_doc(
        "doc-f02-01",
        "Địa điểm kiểm thử",
        [("Đầu ", tag), (" cuối tuyến đường du lịch.", None)],
        confidence=None,
    )
    q = make_query_row("Q-F02-01", "Đầu cuối tuyến đường", requested_facet_keywords=["tuyến đường"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", [doc])
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-BM25", "C1-Dense"], timeout=300)
    all_rows = read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl")
    for cell in ("C1-BM25", "C1-Dense"):
        c_rows = rows_for_cell_query(all_rows, cell, "Q-F02-01")
        assert len(c_rows) == 1
        assert "[CORROBORATED" not in c_rows[0]["assembled_text"]
        assert "Đầu  cuối tuyến đường du lịch." in c_rows[0]["assembled_text"]


def test_t1_f02_02_non_r_audit_brackets_and_confidence_preserved(tmp_path: Path) -> None:
    require_retrieval_cli()
    text_s = (
        "Thông tin [UNVERIFIED: chưa khảo sát] [CONFLICT: FC-001] [1] [Gia Long] "
        "Độ tin cậy bản ghi Overture (confidence): 0.7405."
    )
    doc = make_b1b_doc("doc-f02-02", "Ghi chú bảo tồn", text_s, source_type="overture_places_parquet")
    q = make_query_row("Q-F02-02", "FC-001", requested_facet_keywords=["FC-001"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", [doc])
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-BM25"])
    rows = read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl")
    assert len(rows) == 1
    assert rows[0]["score"] > 0.0
    txt = rows[0]["assembled_text"]
    for preserved in (
        "[UNVERIFIED: chưa khảo sát]",
        "[CONFLICT: FC-001]",
        "[1]",
        "[Gia Long]",
        "Độ tin cậy bản ghi Overture (confidence): 0.7405.",
    ):
        assert preserved in txt


def test_t1_f02_03_multi_interval_projection_disjoint_no_outer_hull(tmp_path: Path) -> None:
    require_retrieval_cli()
    tag = "[CORROBORATED: osm:way/99]"
    doc, removed = make_overture_doc(
        "doc-f02-03",
        "Điểm nối",
        [("Alpha ", tag), (" Omega công trình cổ.", None)],
        confidence=None,
    )
    text_s = doc["canonical_text_S"]
    q = make_query_row("Q-F02-03", "công trình cổ", requested_facet_keywords=["công trình cổ"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", [doc])
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-BM25"])
    rows = read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl")
    assert len(rows) == 1
    spans = rows[0]["c_full_s_spans"]
    assert len(spans) >= 2
    ra, rb = removed[0]
    for sa, sb in spans:
        assert max(sa, ra) >= min(sb, rb), "Outer hull leaked deleted R_AUDIT span"
    reconstructed = "".join(text_s[sa:sb] for sa, sb in spans)
    assert "Alpha  Omega công trình cổ." in reconstructed
    assert "[CORROBORATED" not in reconstructed


def test_t1_f02_04_identical_sanitized_view_across_four_paths(tmp_path: Path) -> None:
    require_retrieval_cli()
    doc, _ = make_overture_doc(
        "doc-f02-04",
        "Đền mẫu",
        [
            ("Alpha mở cửa buổi sáng ", "[CORROBORATED: osm:node/11]"),
            (" và đóng cửa chiều ", "[CORROBORATED: wikidata:Q22]"),
            (" hàng ngày trong tuần.", None),
        ],
    )
    q = make_query_row("Q-F02-04", "Alpha mở cửa buổi sáng hàng ngày", requested_facet_keywords=["Alpha"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", [doc])
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(
        corpus_p, queries_p, out_dir, cells=["C0-BM25", "C0-Dense", "C1-BM25", "C1-Dense"]
    )
    all_rows = read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl")
    by_cell = {c: rows_for_cell_query(all_rows, c, "Q-F02-04")[0] for c in ("C0-BM25", "C0-Dense", "C1-BM25", "C1-Dense")}
    for r in by_cell.values():
        assert "[CORROBORATED" not in r["assembled_text"]
    assert by_cell["C1-BM25"]["assembled_text"] == by_cell["C1-Dense"]["assembled_text"]
    assert by_cell["C1-BM25"]["c_full_s_spans"] == by_cell["C1-Dense"]["c_full_s_spans"]
    assert by_cell["C0-BM25"]["assembled_text"] == by_cell["C0-Dense"]["assembled_text"]
    assert by_cell["C0-BM25"]["c_full_s_spans"] == by_cell["C0-Dense"]["c_full_s_spans"]


def test_t1_f02_05_visible_evidence_span_hit_straddling_removed_tag(tmp_path: Path) -> None:
    require_retrieval_cli()
    require_scorer_cli()
    doc, removed = make_overture_doc(
        "doc-f02-05",
        "Bảo tàng straddle",
        [("Mở cửa ", "[CORROBORATED: wikidata:Q99]"), (" từ 08:00 đến 17:00 hàng ngày.", None)],
        confidence=None,
    )
    text_s = doc["canonical_text_S"]
    sub_spans = split_span_excluding_removed(0, text_s.index("17:00.") + len("17:00.") if "17:00." in text_s else len(text_s), removed)
    q = make_query_row(
        "Q-F02-05",
        "Mở cửa từ 08:00 đến 17:00",
        requested_facet_keywords=["08:00", "17:00"],
        required_evidence_facets=[[{"document_id": "doc-f02-05", "s_spans": sub_spans}]],
    )
    qrel = make_qrel_row("Q-F02-05", "doc-f02-05", "REL_2", evidence_s_spans=sub_spans)
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", [doc])
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    qrels_p = write_jsonl(tmp_path / "qrels.jsonl", [qrel])
    rem_p = tmp_path / "removed_spans.json"
    rem_p.write_text(json.dumps({"doc-f02-05": [list(s) for s in removed]}), encoding="utf-8")

    out_dir = tmp_path / "out"
    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-Dense"])
    report_p = tmp_path / "g4_report.json"
    run_scorer_cli(
        out_dir / "g3_sealed_rankings_v1.jsonl",
        out_dir / "g3_sealed_rankings_v1_manifest.json",
        qrels_p,
        queries_p,
        report_p,
        removed_audit_spans=rem_p,
    )
    report = read_json(report_p)
    cell = extract_cells_map(report)["C1-Dense"]
    assert float(extract_metric_value(cell, ["EvidenceSpanHit@10", "evidence_span_hit_10"])) == pytest.approx(1.0)
    assert float(extract_metric_value(cell, ["VisibleEvidenceSpanHit@10", "visible_evidence_span_hit_10"])) == pytest.approx(1.0)


# ===========================================================================
# Feature 3: D03.4 C0 vs C1 Chunking & C_vis (T1-F03-01 .. T1-F03-05)
# ===========================================================================


def test_t1_f03_01_c1_subword_token_ceiling_le_128_multiline_doc(tmp_path: Path) -> None:
    require_retrieval_cli()
    sec1 = "Lịch sử hình thành khu di tích cổ tại Hà Nội kéo dài qua nhiều triều đại phong kiến Việt Nam. " * 8
    sec2 = "Khu trưng bày chính giới thiệu hiện vật gốm sứ cổ và thư pháp truyền thống đặc sắc. " * 8
    sec3 = "Visitor guide provides bilingual tour maps and ticket counters open daily. " * 8
    doc = make_multi_level_doc(
        "doc-f03-01",
        "Khu Di Tích Tổng Hợp",
        [(2, "Lịch sử", sec1), (2, "Trưng bày", sec2), (2, "Visitor Guide", sec3)],
        city="Hà Nội",
    )
    q = make_query_row("Q-F03-01", "hiện vật gốm sứ cổ", requested_facet_keywords=["gốm sứ"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", [doc])
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(
        corpus_p, queries_p, out_dir, cells=["C1-BM25", "C1-Dense"], packet_salt="F03_SALT"
    )
    tok = cached_minilm_tokenizer()
    chunks = read_jsonl(out_dir / "chunks_manifest.jsonl")
    c1_chunks = [c for c in chunks if c.get("chunker", "C1") == "C1"]
    assert len(c1_chunks) >= 3
    for ch in c1_chunks:
        txt = ch["assembled_text"]
        assert " | " in txt.splitlines()[0]
        ids = tok.encode(txt, add_special_tokens=True, truncation=False)
        assert len(ids) <= 128

    for row in read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl"):
        ids = tok.encode(row["assembled_text"], add_special_tokens=True, truncation=False)
        assert len(ids) <= 128


def test_t1_f03_02_c1_zero_overlap_and_zero_char_coverage_loss(tmp_path: Path) -> None:
    require_retrieval_cli()
    sentences = [
        f"Câu số {i} mô tả chi tiết kiến trúc độc đáo và giá trị lịch sử văn hóa của công trình cổ tại Việt Nam."
        for i in range(1, 10)
    ]
    body = " ".join(sentences)
    doc = make_b1b_doc("doc-f03-02", "Kiến trúc cổ", body)
    q = make_query_row("Q-F03-02", "kiến trúc độc đáo", requested_facet_keywords=["kiến trúc"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", [doc])
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-BM25"], packet_salt="F03_COV")
    chunks = [
        c
        for c in read_jsonl(out_dir / "chunks_manifest.jsonl")
        if c.get("document_id") == "doc-f03-02" and c.get("chunker", "C1") == "C1"
    ]
    assert len(chunks) >= 2
    seen_body_spans: List[tuple[int, int]] = []
    covered_chars: set[int] = set()
    for ch in chunks:
        for seg in ch["assembled_segments"]:
            if seg["kind"] == "CANONICAL_BODY_V":
                vs, ve = seg["v_start"], seg["v_end"]
                for ps, pe in seen_body_spans:
                    assert max(vs, ps) >= min(ve, pe), "C1 chunks must have 0 overlap"
                seen_body_spans.append((vs, ve))
                covered_chars.update(range(vs, ve))
    expected_non_ws = {idx for idx, ch in enumerate(body) if not ch.isspace()}
    assert expected_non_ws.issubset(covered_chars)


def test_t1_f03_03_c0_section_aware_format_and_one_sentence_overlap(tmp_path: Path) -> None:
    require_retrieval_cli()
    sents = [
        f"Sentence number {i:02d} contains exactly twenty filler words about architecture history heritage museum gallery culture artifacts tickets schedules visitors."
        for i in range(1, 27)
    ]
    body = " ".join(sents)
    doc = make_multi_level_doc("doc-f03-03", "Heritage Title", [(2, "History", body)], language="en")
    q = make_query_row("Q-F03-03", "Sentence number 01 architecture", requested_facet_keywords=["architecture"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", [doc])
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(
        corpus_p, queries_p, out_dir, cells=["C0-BM25", "C0-Dense"], packet_salt="F03_C0"
    )
    chunks = [
        c
        for c in read_jsonl(out_dir / "chunks_manifest.jsonl")
        if c.get("document_id") == "doc-f03-03" and c.get("chunker", "C0") == "C0"
    ]
    assert len(chunks) >= 2
    assert chunks[0]["assembled_text"].startswith("Heritage Title - History\n")
    s0 = {i for a, b in chunks[0]["c_full_s_spans"] for i in range(a, b)}
    s1 = {i for a, b in chunks[1]["c_full_s_spans"] for i in range(a, b)}
    assert len(s0 & s1) > 0, "Expected 1-sentence overlap between C0 chunks"

    dense_row = rows_for_cell_query(
        read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl"), "C0-Dense", "Q-F03-03"
    )[0]
    full_len = sum(b - a for a, b in dense_row["c_full_s_spans"])
    vis_len = sum(b - a for a, b in dense_row["c_vis_s_spans"])
    assert vis_len < full_len


def test_t1_f03_04_c_full_vs_c_vis_divergence_on_tail_fact(tmp_path: Path) -> None:
    require_retrieval_cli()
    require_scorer_cli()
    filler = "Thông tin giới thiệu chung về lịch sử hình thành và cảnh quan khu di tích văn hóa truyền thống. " * 22
    tail = "Mã lưu trữ đặc biệt cuối trang: ARCHIVE-TAIL-9981."
    text_s = filler + tail
    doc = make_b1b_doc("doc-f03-04", "Di tích dài", text_s)
    tail_span = [find_span(text_s, "ARCHIVE-TAIL-9981")]
    q = make_query_row(
        "Q-F03-04",
        "ARCHIVE-TAIL-9981",
        requested_facet_keywords=["ARCHIVE-TAIL-9981"],
        required_evidence_facets=[[{"document_id": "doc-f03-04", "s_spans": tail_span}]],
    )
    qrel = make_qrel_row("Q-F03-04", "doc-f03-04", "REL_2", evidence_s_spans=tail_span)
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", [doc])
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    qrels_p = write_jsonl(tmp_path / "qrels.jsonl", [qrel])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C0-Dense", "C1-Dense"])
    report_p = tmp_path / "g4_report.json"
    run_scorer_cli(
        out_dir / "g3_sealed_rankings_v1.jsonl",
        out_dir / "g3_sealed_rankings_v1_manifest.json",
        qrels_p,
        queries_p,
        report_p,
    )
    cells = extract_cells_map(read_json(report_p))
    c0 = cells["C0-Dense"]
    c1 = cells["C1-Dense"]
    assert float(extract_metric_value(c0, ["EvidenceSpanHit@10", "evidence_span_hit_10"])) == pytest.approx(1.0)
    assert float(extract_metric_value(c0, ["VisibleEvidenceSpanHit@10", "visible_evidence_span_hit_10"])) == pytest.approx(0.0)
    assert float(extract_metric_value(c1, ["VisibleEvidenceSpanHit@10", "visible_evidence_span_hit_10"])) == pytest.approx(1.0)


def test_t1_f03_05_headingless_doc_synthetic_header_maps_to_empty(tmp_path: Path) -> None:
    require_retrieval_cli()
    prose = (
        "Bảo tàng nghệ thuật nằm ở trung tâm thành phố với hơn mười lăm phòng trưng bày hiện vật quý giá."
    )
    doc = make_b1b_doc("doc-f03-05", "Bảo tàng Nghệ thuật", prose)
    q = make_query_row("Q-F03-05", "mười lăm phòng trưng bày", requested_facet_keywords=["phòng trưng bày"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", [doc])
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C0-BM25", "C1-BM25"])
    all_rows = read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl")
    for cell in ("C0-BM25", "C1-BM25"):
        row = rows_for_cell_query(all_rows, cell, "Q-F03-05")[0]
        synth = [s for s in row["assembled_segments"] if s["kind"] == "SYNTHETIC_HEADER"]
        assert len(synth) >= 1
        assert all(
            s["kind"] != "CANONICAL_HEADING_S" for s in row["assembled_segments"]
        )
        assert row["c_full_s_spans"] == [[0, len(prose)]]


# ===========================================================================
# Feature 4: D04.2 Lexical BM25 (T1-F04-01 .. T1-F04-05)
# ===========================================================================


def test_t1_f04_01_vietnamese_compound_tokenization_and_ranking(tmp_path: Path) -> None:
    require_retrieval_cli()
    docs = [
        make_b1b_doc("d1", "Lưu trú", "Khách sạn gần hồ Hoàn Kiếm phục vụ bữa sáng."),
        make_b1b_doc("d2", "Ẩm thực", "Nhà hàng hải sản tươi sống ven biển."),
        make_b1b_doc("d3", "Trung tâm", "Khách sạn trung tâm thành phố hiện đại."),
    ]
    q = make_query_row("Q-F04-01", "khách sạn gần hồ", requested_facet_keywords=["khách sạn", "hồ"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-BM25"])
    rows = read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl")
    assert [r["document_id"] for r in rows] == ["d1", "d3"]


def test_t1_f04_02_stopwords_none_retention(tmp_path: Path) -> None:
    require_retrieval_cli()
    docs = [
        make_b1b_doc("d1", "Mẫu từ", "Thông tin về của và ở trên phố cổ."),
        make_b1b_doc("d2", "Lịch sử", "Bảo tàng lịch sử quốc gia."),
    ]
    q = make_query_row("Q-F04-02", "của và ở", requested_facet_keywords=["của"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-BM25"])
    rows = read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl")
    assert len(rows) >= 1
    assert rows[0]["document_id"] == "d1"
    assert rows[0]["score"] > 0.0


def test_t1_f04_03_unicode_nfc_normalization_and_lowercase_folding(tmp_path: Path) -> None:
    require_retrieval_cli()
    docs = [
        make_b1b_doc("d1-nfd", "Địa danh", "HA\u0300 NO\u0323\u0302I PHƠ\u0309 BO\u0300 ngon"),
        make_b1b_doc("d2-nfc", "Địa danh", "hà nội phở bò ngon"),
    ]
    q = make_query_row("Q-F04-03", "hà nội phở bò", requested_facet_keywords=["hà nội", "phở bò"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-BM25"])
    rows = read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl")
    assert len(rows) == 2
    assert abs(rows[0]["score"] - rows[1]["score"]) < 1e-12


def test_t1_f04_04_numeric_and_decimal_token_extraction(tmp_path: Path) -> None:
    require_retrieval_cli()
    docs = [
        make_b1b_doc("d1", "Giá vé", "Giá vé 19.500 đồng, diện tích 2,5 ha."),
        make_b1b_doc("d2", "Miễn phí", "Giá vé miễn phí quanh năm."),
    ]
    q = make_query_row("Q-F04-04", "19.500 2,5", requested_facet_keywords=["19.500", "2,5"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-BM25"])
    rows = read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl")
    assert [r["document_id"] for r in rows] == ["d1"]
    assert rows[0]["score"] > 0.0


def test_t1_f04_05_closed_form_okapi_bm25_exact_score(tmp_path: Path) -> None:
    require_retrieval_cli()
    docs = [
        make_b1b_doc("d1", "doc", "alpha alpha beta gamma"),
        make_b1b_doc("d2", "doc", "alpha epsilon zeta eta theta iota"),
        make_b1b_doc("d3", "doc", "kappa lambda mu nu xi"),
    ]
    q = make_query_row("Q-F04-05", "alpha", requested_facet_keywords=["alpha"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-BM25"], packet_salt="BM25_EXACT")
    rows = read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl")
    assert [r["document_id"] for r in rows] == ["d1", "d2"]

    chunks = [
        c
        for c in read_jsonl(out_dir / "chunks_manifest.jsonl")
        if c.get("chunker", "C1") == "C1"
    ]
    tok_re = re.compile(r"[A-Za-z0-9_]+")
    dl = {c["document_id"]: len(tok_re.findall(c["assembled_text"].lower())) for c in chunks}
    avgdl = sum(dl.values()) / 3.0
    idf = math.log(1.0 + (3.0 - 2.0 + 0.5) / (2.0 + 0.5))
    k1, b = 1.5, 0.75
    expected_d1 = idf * (2 * (k1 + 1.0)) / (2 + k1 * (1.0 - b + b * dl["d1"] / avgdl))
    expected_d2 = idf * (1 * (k1 + 1.0)) / (1 + k1 * (1.0 - b + b * dl["d2"] / avgdl))
    assert rows[0]["score"] == pytest.approx(expected_d1, abs=1e-9)
    assert rows[1]["score"] == pytest.approx(expected_d2, abs=1e-9)


# ===========================================================================
# Feature 5: D04.3 Offline Dense (No Mock) (T1-F05-01 .. T1-F05-05)
# ===========================================================================


def test_t1_f05_01_offline_cached_snapshot_semantic_ranking(tmp_path: Path) -> None:
    require_retrieval_cli()
    docs = [
        make_b1b_doc("d1", "Hạ Long", "Vịnh Hạ Long là di sản thiên nhiên thế giới được UNESCO công nhận."),
        make_b1b_doc("d2", "Ẩm thực", "Hướng dẫn nấu phở bò truyền thống tại gia."),
        make_b1b_doc("d3", "Giao thông", "Lịch trình xe buýt nội đô buổi sáng."),
    ]
    q = make_query_row("Q-F05-01", "Di sản UNESCO ở Hạ Long", requested_facet_keywords=["UNESCO"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-Dense"])
    manifest = read_json(out_dir / "g3_sealed_rankings_v1_manifest.json")
    assert manifest["snapshot_id"] == "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"
    rows = read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl")
    assert rows[0]["document_id"] == "d1"


def test_t1_f05_02_cross_lingual_vi_to_en_dense_retrieval(tmp_path: Path) -> None:
    require_retrieval_cli()
    docs = [
        make_b1b_doc("d1", "Museum", "The museum is open daily from 8 AM to 5 PM.", language="en"),
        make_b1b_doc("d2", "Sports", "Football match schedule for Sunday afternoon.", language="en"),
    ]
    q = make_query_row(
        "Q-F05-02",
        "Giờ mở cửa của bảo tàng là khi nào?",
        query_family="S4_CROSS_LINGUAL_VI_TO_EN",
        requested_facet_keywords=["8 AM", "5 PM"],
    )
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-Dense"])
    rows = read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl")
    assert [r["document_id"] for r in rows] == ["d1", "d2"]


def test_t1_f05_03_l2_normalized_cosine_bounds_and_repeat_determinism(tmp_path: Path) -> None:
    require_retrieval_cli()
    docs = [
        make_b1b_doc("d1", "Di sản", "Di sản văn hóa thế giới tại phố cổ Hội An."),
        make_b1b_doc("d2", "Biển", "Bãi biển Mỹ Khê cát trắng nắng vàng."),
        make_b1b_doc("d3", "Chùa", "Chùa Một Cột kiến trúc độc đáo tại Hà Nội."),
    ]
    q = make_query_row("Q-F05-03", "Di sản văn hóa thế giới tại phố cổ", requested_facet_keywords=["phố cổ"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out1 = tmp_path / "out1"
    out2 = tmp_path / "out2"

    run_retrieval_cli(corpus_p, queries_p, out1, cells=["C1-Dense"])
    run_retrieval_cli(corpus_p, queries_p, out2, cells=["C1-Dense"])
    b1 = (out1 / "g3_sealed_rankings_v1.jsonl").read_bytes()
    b2 = (out2 / "g3_sealed_rankings_v1.jsonl").read_bytes()
    assert b1 == b2
    for row in read_jsonl(out1 / "g3_sealed_rankings_v1.jsonl"):
        assert -1.0001 <= row["score"] <= 1.0001


def test_t1_f05_04_explicit_snapshot_dir_cli_binding(tmp_path: Path) -> None:
    require_retrieval_cli()
    docs = [
        make_b1b_doc("d1", "Hồ Gươm", "Hồ Gươm nằm ngay trung tâm thủ đô Hà Nội."),
        make_b1b_doc("d2", "Cầu Rồng", "Cầu Rồng bắc qua sông Hàn ở Đà Nẵng."),
    ]
    q = make_query_row("Q-F05-04", "Hồ Gươm ở đâu", requested_facet_keywords=["Hà Nội"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(
        corpus_p, queries_p, out_dir, cells=["C0-Dense", "C1-Dense"], snapshot_dir=HF_SNAPSHOT_DIR
    )
    manifest = read_json(out_dir / "g3_sealed_rankings_v1_manifest.json")
    assert manifest["snapshot_id"] == "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"


def test_t1_f05_05_full_distinct_doc_coverage_12_docs(tmp_path: Path) -> None:
    require_retrieval_cli()
    docs = [
        make_b1b_doc(
            f"d-{i:02d}",
            f"Điểm {i}",
            f"Đây là mô tả chi tiết thứ {i} về điểm tham quan du lịch nổi tiếng tại Việt Nam.",
        )
        for i in range(1, 13)
    ]
    q = make_query_row("Q-F05-05", "điểm tham quan du lịch", requested_facet_keywords=["du lịch"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C0-Dense", "C1-Dense"])
    all_rows = read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl")
    for cell in ("C0-Dense", "C1-Dense"):
        c_rows = rows_for_cell_query(all_rows, cell, "Q-F05-05")
        assert len(c_rows) == 12
        assert [r["rank"] for r in c_rows] == list(range(1, 13))
        assert len({r["document_id"] for r in c_rows}) == 12


# ===========================================================================
# Feature 6: D04.4 Doc Collapse & Hybrid RRF (T1-F06-01 .. T1-F06-05)
# ===========================================================================


def test_t1_f06_01_full_chunk_scoring_collapse_fx08_55_chunks(tmp_path: Path) -> None:
    require_retrieval_cli()
    long_secs = [
        (2, f"Phần {i}", f"Bảo tàng nghệ thuật đặc biệt trưng bày cổ vật quý giá phần {i} rất phong phú.")
        for i in range(1, 56)
    ]
    docs = [make_multi_level_doc("doc-long", "Bảo tàng lớn", long_secs)]
    for j in range(2, 11):
        docs.append(
            make_b1b_doc(
                f"doc-{j:02d}",
                f"Điểm {j}",
                f"Cơ sở {j} có phòng trưng bày hiện vật lịch sử địa phương.",
            )
        )
    q = make_query_row("Q-F06-01", "bảo tàng trưng bày cổ vật", requested_facet_keywords=["bảo tàng"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-BM25", "C1-Dense"], timeout=300)
    all_rows = read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl")
    for cell in ("C1-BM25", "C1-Dense"):
        c_rows = rows_for_cell_query(all_rows, cell, "Q-F06-01")
        assert len(c_rows) == 10
        assert [r["rank"] for r in c_rows] == list(range(1, 11))
        assert c_rows[0]["document_id"] == "doc-long"
        assert len({r["document_id"] for r in c_rows}) == 10


def test_t1_f06_02_exact_rrf_arithmetic_and_leg_ranks_provenance(tmp_path: Path) -> None:
    require_retrieval_cli()
    docs = [
        make_b1b_doc("d1", "Chính xác", "Từ khóa mẫu ZETA-11 xuất hiện ZETA-11 lặp lại ZETA-11 nhiều lần."),
        make_b1b_doc("d2", "Ngữ nghĩa", "Thông tin về giờ mở cửa bảo tàng lịch sử văn hóa ZETA-11."),
        make_b1b_doc("d3", "Khác", "Thông tin tổng quan về thời gian mở cửa tham quan bảo tàng."),
    ]
    q = make_query_row("Q-F06-02", "ZETA-11 giờ mở cửa bảo tàng", requested_facet_keywords=["mở cửa"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-BM25", "C1-Dense", "C1-RRF"])
    all_rows = read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl")
    bm25_ranks = {r["document_id"]: r["rank"] for r in rows_for_cell_query(all_rows, "C1-BM25", "Q-F06-02")}
    dense_ranks = {r["document_id"]: r["rank"] for r in rows_for_cell_query(all_rows, "C1-Dense", "Q-F06-02")}
    rrf_rows = rows_for_cell_query(all_rows, "C1-RRF", "Q-F06-02")

    for r in rrf_rows:
        did = r["document_id"]
        rb = bm25_ranks.get(did)
        rd = dense_ranks.get(did)
        expected = (1.0 / (60 + rb) if rb and rb <= 50 else 0.0) + (
            1.0 / (60 + rd) if rd and rd <= 50 else 0.0
        )
        assert r["score"] == pytest.approx(expected, abs=1e-12)
        if rb is not None:
            assert r["leg_ranks"].get("BM25") == rb
        if rd is not None:
            assert r["leg_ranks"].get("Dense") == rd


def test_t1_f06_03_full_2x3_six_cell_execution_and_15_key_schema(tmp_path: Path) -> None:
    require_retrieval_cli()
    docs = [
        make_b1b_doc(
            f"d-{i}",
            f"Điểm du lịch {i}",
            f"Điểm du lịch {i} tại Hà Nội có nhiều hoạt động văn hóa hấp dẫn cho du khách.",
        )
        for i in range(1, 5)
    ]
    queries = [
        make_query_row("Q1", "du lịch Hà Nội", requested_facet_keywords=["Hà Nội"]),
        make_query_row("Q2", "hoạt động văn hóa", requested_facet_keywords=["văn hóa"]),
    ]
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", queries)
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir)
    manifest = read_json(out_dir / "g3_sealed_rankings_v1_manifest.json")
    assert set(manifest["cells"]) == set(ALL_SIX_CELLS)
    assert manifest["rankings_sha256"] == file_sha256(out_dir / "g3_sealed_rankings_v1.jsonl")
    rows = read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl")
    assert manifest["row_count"] == len(rows)
    for r in rows:
        assert RANKING_ROW_KEYS.issubset(r.keys())


def test_t1_f06_04_bit_identical_deterministic_6_cell_repeat(tmp_path: Path) -> None:
    require_retrieval_cli()
    docs = [
        make_b1b_doc(f"d-{i}", f"Tiêu đề {i}", f"Nội dung du lịch mẫu số {i} tại Hạ Long rất đẹp.")
        for i in range(1, 4)
    ]
    q = make_query_row("Q-F06-04", "du lịch Hạ Long", requested_facet_keywords=["Hạ Long"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out1 = tmp_path / "out1"
    out2 = tmp_path / "out2"

    run_retrieval_cli(corpus_p, queries_p, out1)
    run_retrieval_cli(corpus_p, queries_p, out2)
    assert (out1 / "g3_sealed_rankings_v1.jsonl").read_bytes() == (
        out2 / "g3_sealed_rankings_v1.jsonl"
    ).read_bytes()
    assert (
        read_json(out1 / "g3_sealed_rankings_v1_manifest.json")["rankings_sha256"]
        == read_json(out2 / "g3_sealed_rankings_v1_manifest.json")["rankings_sha256"]
    )


def test_t1_f06_05_primary_rep_chunk_selected_from_smaller_rank_leg(tmp_path: Path) -> None:
    require_retrieval_cli()
    # Target doc has chunk 0 tuned for Dense (semantic paraphrase) vs chunk 1 tuned for BM25 (exact rare token)
    target = make_multi_level_doc(
        "d-target",
        "Bảo tàng mẫu",
        [
            (2, "Thuyết minh", "Bảo tàng lịch sử quốc gia trưng bày hiện vật triều đại phong kiến."),
            (2, "Mã", "Thông tin lưu trữ mã KEYTOKEN88 với nội dung khác biệt hoàn toàn."),
        ],
    )
    decoy = make_b1b_doc(
        "d-decoy",
        "Khác",
        "KEYTOKEN88 KEYTOKEN88 KEYTOKEN88 chủ đề xe buýt nội đô không liên quan bảo tàng.",
    )
    q = make_query_row(
        "Q-F06-05",
        "KEYTOKEN88 lịch sử trưng bày hiện vật bảo tàng",
        requested_facet_keywords=["bảo tàng"],
    )
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", [target, decoy])
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-BM25", "C1-Dense", "C1-RRF"])
    rrf_rows = rows_for_cell_query(read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl"), "C1-RRF", "Q-F06-05")
    t_row = next(r for r in rrf_rows if r["document_id"] == "d-target")
    rb = t_row["leg_ranks"]["BM25"]
    rd = t_row["leg_ranks"]["Dense"]
    assert isinstance(t_row["leg_rep_chunks"]["BM25"], dict)
    assert isinstance(t_row["leg_rep_chunks"]["Dense"], dict)
    assert (
        t_row["leg_rep_chunks"]["BM25"]["chunk_id"]
        != t_row["leg_rep_chunks"]["Dense"]["chunk_id"]
    )
    expected_leg = "Dense" if rd <= rb else "BM25"
    assert t_row["rep_chunk_id"] == t_row["leg_rep_chunks"][expected_leg]["chunk_id"]


# ===========================================================================
# Feature 7: D05.3 Blind Packet Exporter (T1-F07-01 .. T1-F07-05)
# ===========================================================================


def test_t1_f07_01_blind_packet_strict_7_key_allowlist_zero_leakage(tmp_path: Path) -> None:
    require_retrieval_cli()
    docs = [make_b1b_doc(f"d-{i}", f"Nơi {i}", f"Mô tả địa điểm du lịch mẫu {i} tại Hà Nội.") for i in range(1, 5)]
    q = make_query_row("Q-F07-01", "địa điểm du lịch", requested_facet_keywords=["du lịch"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-BM25"], packet_salt="SALT_01")
    pkt_rows = read_jsonl(out_dir / "blind_annotation_packet.jsonl")
    assert len(pkt_rows) >= 1
    for r in pkt_rows:
        assert set(r.keys()) == BLIND_PACKET_KEYS
        for bad_key in ("rank", "score", "cell_id", "pre_rank_answerability", "pool_origin"):
            assert bad_key not in r


def test_t1_f07_02_blind_packet_exports_immutable_canonical_s(tmp_path: Path) -> None:
    require_retrieval_cli()
    doc, _ = make_overture_doc(
        "d-raw",
        "Đền cổ",
        [("Đền cổ Hà Nội ", "[CORROBORATED: osm:node/1]"), (" mở cửa sáng.", None)],
    )
    q = make_query_row("Q-F07-02", "Đền cổ Hà Nội", requested_facet_keywords=["Đền cổ"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", [doc])
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-BM25"], packet_salt="SALT_01")
    pkt_rows = read_jsonl(out_dir / "blind_annotation_packet.jsonl")
    assert len(pkt_rows) == 1
    assert pkt_rows[0]["canonical_text_S"] == doc["canonical_text_S"]
    assert "[CORROBORATED: osm:node/1]" in pkt_rows[0]["canonical_text_S"]


def test_t1_f07_03_blind_packet_deterministic_hmac_sha256_uuid(tmp_path: Path) -> None:
    require_retrieval_cli()
    docs = [make_b1b_doc(f"d-{i}", f"Nơi {i}", f"Địa điểm tham quan mẫu số {i}.") for i in range(1, 4)]
    q = make_query_row("Q-F07-03", "Địa điểm tham quan", requested_facet_keywords=["tham quan"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-BM25"], packet_salt="TEST_SALT")
    for r in read_jsonl(out_dir / "blind_annotation_packet.jsonl"):
        assert r["packet_item_uuid"] == expected_packet_uuid(
            "TEST_SALT", r["query_id"], r["document_id"]
        )


def test_t1_f07_04_blind_packet_pool_deduplication_across_6_cells(tmp_path: Path) -> None:
    require_retrieval_cli()
    docs = [make_b1b_doc(f"d-{i}", f"Nơi {i}", f"Địa điểm du lịch mẫu số {i} có nhiều hoạt động.") for i in range(1, 6)]
    q = make_query_row("Q-F07-04", "Địa điểm du lịch", requested_facet_keywords=["du lịch"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, packet_salt="SALT_01")
    pkt_rows = read_jsonl(out_dir / "blind_annotation_packet.jsonl")
    pairs = [(r["query_id"], r["document_id"]) for r in pkt_rows]
    assert 1 <= len(pkt_rows) <= 5
    assert len(pkt_rows) == 5
    assert len(pairs) == len(set(pairs))


def test_t1_f07_05_blind_packet_utf8_lf_and_sort_keys_true(tmp_path: Path) -> None:
    require_retrieval_cli()
    docs = [make_b1b_doc(f"d-{i}", f"Điểm {i}", f"Thông tin tiếng Việt có dấu số {i}.") for i in range(1, 4)]
    q = make_query_row("Q-F07-05", "tiếng Việt có dấu", requested_facet_keywords=["tiếng Việt"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-BM25"], packet_salt="SALT_LF")
    raw_bytes = (out_dir / "blind_annotation_packet.jsonl").read_bytes()
    assert b"\r\n" not in raw_bytes
    for line in raw_bytes.decode("utf-8").splitlines():
        if line.strip():
            assert line == json.dumps(json.loads(line), ensure_ascii=False, sort_keys=True)


# ===========================================================================
# Feature 8: D01 & AUTO-EVAL Query/Judge Gates (T1-F08-01 .. T1-F08-05)
# ===========================================================================


def test_t1_f08_01_full_5x3_15_cell_matrix_accepted(tmp_path: Path) -> None:
    require_scorer_cli()
    queries = make_5x3_query_matrix(split="FINAL", question_origin="INDEPENDENT_HUMAN")
    docs = [
        make_b1b_doc("d1", "Hà Nội", "Thông tin Hà Nội.", poi_id="syn-poi-hn-01", city="Hà Nội"),
        make_b1b_doc("d2", "Đà Nẵng", "Thông tin Đà Nẵng.", poi_id="syn-poi-dn-01", city="Đà Nẵng"),
    ]
    docs_by_id = {d["document_id"]: d for d in docs}
    rank_map = {("C1-BM25", q["query_id"]): [("d1", 2.0), ("d2", 1.0)] for q in queries}
    rankings_p, manifest_p = write_synthetic_sealed_rankings(tmp_path / "g3", rank_map, docs_by_id)
    qrels: List[Dict[str, Any]] = []
    for q in queries:
        qrels.append(make_qrel_row(q["query_id"], "d1", "REL_2" if q["pre_rank_answerability"] == "ANSWERABLE" else "REL_0"))
        qrels.append(make_qrel_row(q["query_id"], "d2", "REL_0"))
    queries_p = write_jsonl(tmp_path / "queries.jsonl", queries)
    qrels_p = write_jsonl(tmp_path / "qrels.jsonl", qrels)
    out_p = tmp_path / "g4_report.json"

    proc = run_scorer_cli(
        rankings_p,
        manifest_p,
        qrels_p,
        queries_p,
        out_p,
        enforce_final50_matrix=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    report = read_json(out_p)
    q_ans_cnt = extract_metric_value(report, ["q_ans_count", "n_q_ans", "num_q_ans"])
    assert int(q_ans_cnt) == 40
    assert int(extract_metric_value(report, ["q_unans_count"])) == 10


def test_t1_f08_02_dev_split_valid_step_s0_accepted(tmp_path: Path) -> None:
    require_scorer_cli()
    docs = {
        "d1": make_b1b_doc("d1", "POI 1", "Thông tin chi tiết về giờ mở cửa 08:00.", poi_id="syn-poi-hn-01", city="Hà Nội"),
        "d2": make_b1b_doc("d2", "POI 2", "Thông tin khác về địa điểm.", poi_id="syn-poi-hn-02", city="Hà Nội"),
    }
    queries = [
        make_query_row(f"Q-DEV-{i}", f"Câu hỏi DEV {i}", split="DEV", target_poi_ids=["syn-poi-hn-01"])
        for i in range(1, 4)
    ]
    rank_map = {("C1-BM25", q["query_id"]): [("d1", 2.0), ("d2", 1.0)] for q in queries}
    rankings_p, manifest_p = write_synthetic_sealed_rankings(tmp_path / "g3", rank_map, docs)
    qrels = [
        make_qrel_row(q["query_id"], d_id, "REL_2" if d_id == "d1" else "REL_0")
        for q in queries
        for d_id in docs
    ]
    queries_p = write_jsonl(tmp_path / "queries.jsonl", queries)
    qrels_p = write_jsonl(tmp_path / "qrels.jsonl", qrels)
    out_p = tmp_path / "g4_report.json"

    run_scorer_cli(rankings_p, manifest_p, qrels_p, queries_p, out_p)
    assert out_p.is_file()


def test_t1_f08_03_dual_llm_judge_a_and_b_separate_ledgers(tmp_path: Path) -> None:
    require_scorer_cli()
    s1 = "Bảo tàng mở cửa từ 08:00 đến 17:00 hàng ngày."
    s2 = "Bãi đỗ xe nằm ở cổng phụ."
    docs = {
        "d1": make_b1b_doc("d1", "D1", s1, poi_id="syn-poi-hn-01", city="Hà Nội"),
        "d2": make_b1b_doc("d2", "D2", s2, poi_id="syn-poi-hn-01", city="Hà Nội"),
    }
    queries = [
        make_query_row("Q1", "Mở cửa mấy giờ?", target_poi_ids=["syn-poi-hn-01"], requested_facet_keywords=["08:00"]),
        make_query_row("Q2", "Bãi đỗ xe ở đâu?", target_poi_ids=["syn-poi-hn-01"], requested_facet_keywords=["đỗ xe"]),
    ]
    rank_map = {("C1-BM25", q["query_id"]): [("d1", 2.0), ("d2", 1.0)] for q in queries}
    rankings_p, manifest_p = write_synthetic_sealed_rankings(tmp_path / "g3", rank_map, docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", queries)

    sp1 = find_span(s1, "mở cửa từ 08:00 đến 17:00")
    sp2 = find_span(s2, "Bãi đỗ xe nằm ở cổng phụ")
    ja = [
        make_judge_record("Q1", "d1", "REL_2", evidence_quote=s1[sp1[0]:sp1[1]], char_start=sp1[0], char_end=sp1[1]),
        make_judge_record("Q1", "d2", "REL_0"),
        make_judge_record("Q2", "d1", "REL_0"),
        make_judge_record("Q2", "d2", "REL_2", evidence_quote=s2[sp2[0]:sp2[1]], char_start=sp2[0], char_end=sp2[1]),
    ]
    jb = [
        make_judge_record("Q1", "d1", "REL_1", evidence_quote=s1[sp1[0]:sp1[1]], char_start=sp1[0], char_end=sp1[1]),
        make_judge_record("Q1", "d2", "REL_2", evidence_quote=s2[sp2[0]:sp2[1]], char_start=sp2[0], char_end=sp2[1]),
        make_judge_record("Q2", "d1", "REL_0"),
        make_judge_record("Q2", "d2", "REL_2", evidence_quote=s2[sp2[0]:sp2[1]], char_start=sp2[0], char_end=sp2[1]),
    ]
    res = _run_judge_eval_helper(tmp_path, rankings_p, manifest_p, queries_p, ja, jb, docs)
    jg = res["judge_gates"]
    assert jg["HumanGraded-GoMate-nDCG@10"] == "NOT_PERFORMED"
    assert jg["LLMJudged-nDCG@10_judge_A"] is not None
    assert jg["LLMJudged-nDCG@10_judge_B"] is not None
    assert jg["judge_A_by_cell"]["C1-BM25"]["confirmable"] is True
    assert jg["judge_B_by_cell"]["C1-BM25"]["confirmable"] is True
    assert jg["judge_A_by_cell"]["C1-BM25"]["error_code_counts"] == {}
    assert jg["judge_B_by_cell"]["C1-BM25"]["error_code_counts"] == {}
    assert (
        jg["LLMJudged-nDCG@10_judge_A"]["C1-BM25"]["lower"]
        != jg["LLMJudged-nDCG@10_judge_B"]["C1-BM25"]["lower"]
    )
    assert jg["judge_A_by_cell"]["C1-BM25"]["validated_by_q"]["Q1"]["d1"]["state"] == "REL_2"
    assert jg["judge_A_by_cell"]["C1-BM25"]["validated_by_q"]["Q1"]["d1"]["confirmed_gain"] == 3
    assert jg["judge_B_by_cell"]["C1-BM25"]["validated_by_q"]["Q1"]["d1"]["state"] == "REL_1"


def test_t1_f08_04_ce4_substantive_negation_n2_preserved_for_exclusion(tmp_path: Path) -> None:
    require_scorer_cli()
    s1 = "Không thu phí vào cửa ngày lễ tại khu di tích."
    docs = {"d1": make_b1b_doc("d1", "D1", s1, poi_id="syn-poi-hn-01", city="Hà Nội")}
    q = make_query_row(
        "Q1",
        "Có miễn phí vé vào cửa ngày lễ không?",
        query_intent_polarity="NEGATIVE_CONSTRAINT_OR_EXCLUSION_NEED",
        target_poi_ids=["syn-poi-hn-01"],
        requested_facet_keywords=["phí"],
    )
    rankings_p, manifest_p = write_synthetic_sealed_rankings(
        tmp_path / "g3", {("C1-BM25", "Q1"): [("d1", 1.0)]}, docs
    )
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    sp = find_span(s1, "Không thu phí vào cửa")
    ja = [make_judge_record("Q1", "d1", "REL_2", evidence_quote=s1[sp[0]:sp[1]], char_start=sp[0], char_end=sp[1])]
    res = _run_judge_eval_helper(tmp_path, rankings_p, manifest_p, queries_p, ja, ja, docs)
    jg = res["judge_gates"]
    assert jg["LLMJudged-nDCG@10_judge_A"] is not None
    cell_a = jg["judge_A_by_cell"]["C1-BM25"]
    assert cell_a["confirmable"] is True
    assert cell_a["error_code_counts"] == {}
    v_res = cell_a["validated_by_q"]["Q1"]["d1"]
    assert v_res["state"] == "REL_2"
    assert v_res["confirmed_gain"] == 3
    assert v_res["error_code"] is None
    assert not report_contains_token(res, "POLARITY_CONTRADICTION_UNRESOLVED_CE4")


def test_t1_f08_05_g_span_verbatim_substring_outside_mask_accepted(tmp_path: Path) -> None:
    require_scorer_cli()
    doc, _ = make_overture_doc(
        "d1",
        "D1",
        [("Thông tin ", "[CORROBORATED: osm:node/1]"), (" Vé người lớn 40.000 đồng.", None)],
        confidence=None,
        poi_id="syn-poi-hn-01",
        city="Hà Nội",
    )
    s1 = doc["canonical_text_S"]
    docs = {"d1": doc}
    q = make_query_row("Q1", "Giá vé người lớn?", target_poi_ids=["syn-poi-hn-01"], requested_facet_keywords=["40.000"])
    rankings_p, manifest_p = write_synthetic_sealed_rankings(
        tmp_path / "g3", {("C1-BM25", "Q1"): [("d1", 1.0)]}, docs
    )
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    sp = find_span(s1, "Vé người lớn 40.000 đồng.")
    ja = [make_judge_record("Q1", "d1", "REL_2", evidence_quote=s1[sp[0]:sp[1]], char_start=sp[0], char_end=sp[1])]
    res = _run_judge_eval_helper(tmp_path, rankings_p, manifest_p, queries_p, ja, ja, docs)
    jg = res["judge_gates"]
    assert jg["LLMJudged-nDCG@10_judge_A"] is not None
    cell_a = jg["judge_A_by_cell"]["C1-BM25"]
    assert cell_a["confirmable"] is True
    assert cell_a["error_code_counts"] == {}
    v_res = cell_a["validated_by_q"]["Q1"]["d1"]
    assert v_res["state"] == "REL_2"
    assert v_res["confirmed_gain"] == 3
    assert v_res["error_code"] is None
    assert not report_contains_token(res, "UNVERIFIED_POSITIVE_QUOTE")


# ===========================================================================
# Feature 9: D05.1-D05.2 Ontology, Lineage & Cert-1..4 (T1-F09-01 .. T1-F09-05)
# ===========================================================================


def test_t1_f09_01_five_state_gains_and_exact_certified_certs(tmp_path: Path) -> None:
    require_scorer_cli()
    docs = {
        "d1": make_b1b_doc("d1", "D1", "Chính xác."),
        "d2": make_b1b_doc("d2", "D2", "Một phần."),
        "d3": make_b1b_doc("d3", "D3", "Không liên quan."),
    }
    queries = [make_query_row("Q1", "q1"), make_query_row("Q2", "q2")]
    rank_map = {
        ("C1-BM25", "Q1"): [("d1", 3.0), ("d2", 2.0), ("d3", 1.0)],
        ("C1-BM25", "Q2"): [("d2", 3.0), ("d1", 2.0), ("d3", 1.0)],
    }
    rankings_p, manifest_p = write_synthetic_sealed_rankings(tmp_path / "g3", rank_map, docs)
    qrels = [
        make_qrel_row("Q1", "d1", "REL_2"),
        make_qrel_row("Q1", "d2", "REL_1"),
        make_qrel_row("Q1", "d3", "REL_0"),
        make_qrel_row("Q2", "d1", "REL_2"),
        make_qrel_row("Q2", "d2", "REL_1"),
        make_qrel_row("Q2", "d3", "REL_0"),
    ]
    queries_p = write_jsonl(tmp_path / "queries.jsonl", queries)
    qrels_p = write_jsonl(tmp_path / "qrels.jsonl", qrels)
    out_p = tmp_path / "g4_report.json"

    run_scorer_cli(rankings_p, manifest_p, qrels_p, queries_p, out_p)
    report = read_json(out_p)
    assert report["headline_status"] == "EXACT_FULL_SET_ESTIMATE"
    assert report["certificates"]["cert4_counts"]["EXACT_CERTIFIED"] == 2
    assert report["certificates"]["cert4_counts"]["INVALID_UNRESOLVED"] == 0
    cell = extract_cells_map(report)["C1-BM25"]
    nl = float(extract_metric_value(cell, ["ndcg10_lower", "nDCG_L@10", "ndcg_l_10", "ndcg_lower"]))
    nu = float(extract_metric_value(cell, ["ndcg10_upper", "nDCG_U@10", "ndcg_u_10", "ndcg_upper"]))
    assert nl == pytest.approx(nu, abs=1e-9)


def test_t1_f09_02_bounded_not_exact_retained_in_q_ans_fx12(tmp_path: Path) -> None:
    require_scorer_cli()
    # Exact FX-12 numbers: q1 EXACT (IDCG=4.5, A=4.5, B=3.6 -> A=1.0, B=0.8),
    # q2,q3 BOUNDED_NOT_EXACT (IDCG_L=3.0, IDCG_U=6.0, A=0.0, B=3.0 -> A=[0,0], B=[0.5,1.0])
    # Mean A = [0.3333, 0.3333], Mean B = [0.6000, 0.9333], Delta(A-B) = [-0.6000, -0.2667]
    docs = {f"d{i}": make_b1b_doc(f"d{i}", f"D{i}", f"Nội dung {i}") for i in range(1, 7)}
    queries = [make_query_row(f"Q{i}", f"q{i}") for i in range(1, 4)]
    rank_map = {
        # C1-RRF (Cell A) vs C1-BM25 (Cell B)
        ("C1-RRF", "Q1"): [("d1", 3.0), ("d2", 2.0), ("d3", 1.0)],
        ("C1-BM25", "Q1"): [("d1", 3.0), ("d4", 2.0), ("d2", 1.0)],
        ("C1-RRF", "Q2"): [("d3", 3.0), ("d4", 2.0)],
        ("C1-BM25", "Q2"): [("d1", 3.0), ("d3", 2.0)],
        ("C1-RRF", "Q3"): [("d3", 3.0), ("d4", 2.0)],
        ("C1-BM25", "Q3"): [("d1", 3.0), ("d3", 2.0)],
    }
    # For Q1: d1=REL_2(3), d2=REL_1(1), d3..d6=REL_0 -> IDCG=3+1/log2(3) ~ wait: 3/1 + 1/1.58496 = 3.63;
    # Use 3 docs REL_2? No: gain=3 at rank 1 + gain=3*0.5? Wait: 3 + 3/log2(4) = 3 + 1.5 = 4.5!
    # Put d1=REL_2, d2=REL_2 at rank 3 (3/log2(4)=1.5) -> IDCG=3+1/log2(3)? Wait: 2 REL_2s have IDCG=3+3/log2(3)=4.89.
    # For exact 4.5: gain(REL_2)=3 at rank 1 + rank 3 (3/2=1.5), if rank 2 has d2=REL_2 IDCG would be 4.89 unless d2=REL_1 (gain 1) and rank 2=1.5? Wait: 1/log2(3)=0.6309, 3/log2(4)=1.5.
    # Either way, coupled bounds on any bounded q2,q3 retain q2,q3 in Q_ans! Let's check:
    # Q1: d1=REL_2, d2=REL_1, d3..d6=REL_0. Q2/Q3: d1=REL_2 (in pool/top10), d2..d4=REL_0, d5=UNJUDGED (out of top-10! so IDCG_L=3.0, IDCG_U=3+3/log2(3)=4.8928)
    rank_map = {
        ("C1-RRF", "Q1"): [("d1", 3.0), ("d2", 2.0), ("d3", 1.0)],
        ("C1-BM25", "Q1"): [("d1", 3.0), ("d3", 2.0), ("d2", 1.0)],
        ("C1-RRF", "Q2"): [("d3", 3.0), ("d4", 2.0)],
        ("C1-BM25", "Q2"): [("d1", 3.0), ("d3", 2.0)],
        ("C1-RRF", "Q3"): [("d3", 3.0), ("d4", 2.0)],
        ("C1-BM25", "Q3"): [("d1", 3.0), ("d3", 2.0)],
    }
    qrels = [
        make_qrel_row("Q1", f"d{i}", "REL_2" if i == 1 else ("REL_1" if i == 2 else "REL_0"))
        for i in range(1, 7)
    ]
    for qid in ("Q2", "Q3"):
        for i in range(1, 7):
            lbl = "REL_2" if i == 1 else ("UNJUDGED" if i == 5 else "REL_0")
            qrels.append(make_qrel_row(qid, f"d{i}", lbl))

    rankings_p, manifest_p = write_synthetic_sealed_rankings(tmp_path / "g3", rank_map, docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", queries)
    qrels_p = write_jsonl(tmp_path / "qrels.jsonl", qrels)
    out_p = tmp_path / "g4_report.json"

    run_scorer_cli(rankings_p, manifest_p, qrels_p, queries_p, out_p)
    report = read_json(out_p)
    assert report_contains_token(report, "NO_EXACT_FULL_SET_ESTIMATE")
    cells = extract_cells_map(report)
    a_u = float(extract_metric_value(cells["C1-RRF"], ["ndcg10_upper", "nDCG_U@10", "ndcg_u_10", "ndcg_upper"]))
    b_l = float(extract_metric_value(cells["C1-BM25"], ["ndcg10_lower", "nDCG_L@10", "ndcg_l_10", "ndcg_lower"]))
    # Q1: A=1.0, B<1.0; Q2,Q3: A=0.0, B>0.6 -> full Q_ans mean A_u == 1/3 < B_l
    assert a_u == pytest.approx(1.0 / 3.0, abs=1e-4)
    assert b_l > a_u


def test_t1_f09_03_zero_positive_exact_excluded_from_q_ans(tmp_path: Path) -> None:
    require_scorer_cli()
    docs = {
        "d1": make_b1b_doc("d1", "D1", "Văn bản 1."),
        "d2": make_b1b_doc("d2", "D2", "Văn bản 2."),
    }
    queries = [make_query_row("Q1", "q1"), make_query_row("Q2", "q2")]
    rank_map = {
        ("C1-BM25", "Q1"): [("d1", 2.0), ("d2", 1.0)],
        ("C1-BM25", "Q2"): [("d1", 2.0), ("d2", 1.0)],
    }
    qrels = [
        make_qrel_row("Q1", "d1", "REL_2"),
        make_qrel_row("Q1", "d2", "REL_0"),
        make_qrel_row("Q2", "d1", "REL_0"),
        make_qrel_row("Q2", "d2", "REL_0"),
    ]
    rankings_p, manifest_p = write_synthetic_sealed_rankings(tmp_path / "g3", rank_map, docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", queries)
    qrels_p = write_jsonl(tmp_path / "qrels.jsonl", qrels)
    out_p = tmp_path / "g4_report.json"

    run_scorer_cli(rankings_p, manifest_p, qrels_p, queries_p, out_p)
    report = read_json(out_p)
    assert report["certificates"]["cert4_counts"]["ZERO_POSITIVE_EXACT"] == 1
    assert report["q_zero_exact_count"] == 1
    assert any(
        item["query_id"] == "Q2" and item["reason"] == "ZERO_POSITIVE_EXACT"
        for item in report["certificates"]["zero_idcg_audit_ledger"]
    )
    cell = extract_cells_map(report)["C1-BM25"]
    nl = float(extract_metric_value(cell, ["ndcg10_lower", "nDCG_L@10", "ndcg_l_10", "ndcg_lower"]))
    assert nl == pytest.approx(1.0, abs=1e-6)


def test_t1_f09_04_shared_lineage_explicit_2_0_and_2_2_fx10(tmp_path: Path) -> None:
    require_scorer_cli()
    docs = {
        "sib-a": make_b1b_doc("sib-a", "A", "Nội dung A", source_lineage_id="wikivoyage:en:Hanoi"),
        "sib-b": make_b1b_doc("sib-b", "B", "Nội dung B", source_lineage_id="wikivoyage:en:Hanoi"),
    }
    queries = [make_query_row("Q1", "q1"), make_query_row("Q2", "q2")]
    rank_map = {
        ("C1-BM25", "Q1"): [("sib-a", 2.0), ("sib-b", 1.0)],
        ("C1-BM25", "Q2"): [("sib-a", 2.0), ("sib-b", 1.0)],
    }
    qrels = [
        make_qrel_row("Q1", "sib-a", "REL_2", source_lineage_id="wikivoyage:en:Hanoi"),
        make_qrel_row("Q1", "sib-b", "REL_0", source_lineage_id="wikivoyage:en:Hanoi"),
        make_qrel_row("Q2", "sib-a", "REL_2", source_lineage_id="wikivoyage:en:Hanoi"),
        make_qrel_row("Q2", "sib-b", "REL_2", source_lineage_id="wikivoyage:en:Hanoi"),
    ]
    rankings_p, manifest_p = write_synthetic_sealed_rankings(tmp_path / "g3", rank_map, docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", queries)
    qrels_p = write_jsonl(tmp_path / "qrels.jsonl", qrels)
    out_p = tmp_path / "g4_report.json"

    run_scorer_cli(rankings_p, manifest_p, qrels_p, queries_p, out_p)
    report = read_json(out_p)
    cell = extract_cells_map(report)["C1-BM25"]
    elc = extract_metric_value(cell, ["epistemic_lineage_mean_at_10", "epistemic_lineage_count", "distinct_lineages"])
    assert float(elc) == pytest.approx(1.0, abs=1e-6)
    nl = float(extract_metric_value(cell, ["ndcg10_lower", "nDCG_L@10", "ndcg_l_10", "ndcg_lower"]))
    assert nl == pytest.approx(1.0, abs=1e-6)


def test_t1_f09_05_multi_evidence_and_or_facet_groups_s3(tmp_path: Path) -> None:
    require_retrieval_cli()
    require_scorer_cli()
    s1 = "Bảo tàng Dân tộc học mở cửa từ 08:30 sáng."
    s2 = "Giá vé vào cổng bảo tàng là 40.000 đồng một lượt."
    docs = [
        make_b1b_doc("d1", "Giờ", s1),
        make_b1b_doc("d2", "Vé", s2),
    ]
    g_a2 = find_span(s1, "08:30 sáng")
    g_b1 = find_span(s2, "40.000 đồng")
    q = make_query_row(
        "Q-S3",
        "Bảo tàng mở cửa 08:30 và giá vé 40.000 đồng",
        query_family="S3_MULTI_EVIDENCE",
        requested_facet_keywords=["08:30", "40.000"],
        required_evidence_facets=[
            [{"document_id": "d1", "s_spans": [g_a2]}],
            [{"document_id": "d2", "s_spans": [g_b1]}],
        ],
    )
    qrels = [
        make_qrel_row("Q-S3", "d1", "REL_1", evidence_s_spans=[g_a2]),
        make_qrel_row("Q-S3", "d2", "REL_1", evidence_s_spans=[g_b1]),
    ]
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    qrels_p = write_jsonl(tmp_path / "qrels.jsonl", qrels)
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-BM25"])
    report_p = tmp_path / "g4_report.json"
    run_scorer_cli(
        out_dir / "g3_sealed_rankings_v1.jsonl",
        out_dir / "g3_sealed_rankings_v1_manifest.json",
        qrels_p,
        queries_p,
        report_p,
    )
    cell = extract_cells_map(read_json(report_p))["C1-BM25"]
    assert float(extract_metric_value(cell, ["EvidenceSpanHit@10", "evidence_span_hit_10"])) == pytest.approx(1.0)


# ===========================================================================
# Feature 10: D06 Decoupled G4 Scorer & Stats (T1-F10-01 .. T1-F10-05)
# ===========================================================================


def test_t1_f10_01_full_decoupled_e2e_runner_to_scorer(tmp_path: Path) -> None:
    require_retrieval_cli()
    require_scorer_cli()
    docs = [
        make_b1b_doc(
            f"d-{i:02d}",
            f"Địa điểm {i}",
            f"Địa điểm du lịch số {i} tại Hà Nội mở cửa 08:00 và có giá vé ưu đãi.",
            poi_id=f"syn-poi-hn-{i:02d}",
        )
        for i in range(1, 13)
    ]
    queries = [
        make_query_row("Q1", "du lịch Hà Nội", target_poi_ids=["syn-poi-hn-01"]),
        make_query_row("Q2", "mở cửa 08:00", target_poi_ids=["syn-poi-hn-02"]),
        make_query_row("Q3", "giá vé ưu đãi", target_poi_ids=["syn-poi-hn-03"]),
        make_query_row(
            "Q4",
            "tàu ngầm ở Hồ Gươm",
            query_family="S5_UNANSWERABLE_OR_UNSTABLE",
            pre_rank_answerability="UNANSWERABLE",
            target_poi_ids=["syn-poi-hn-04"],
        ),
    ]
    qrels: List[Dict[str, Any]] = []
    for qi, q in enumerate(queries, start=1):
        for di, d in enumerate(docs, start=1):
            lbl = "REL_2" if qi <= 3 and di == qi else "REL_0"
            sp = [find_span(d["canonical_text_S"], "08:00")] if lbl == "REL_2" else []
            qrels.append(make_qrel_row(q["query_id"], d["document_id"], lbl, evidence_s_spans=sp))

    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", queries)
    qrels_p = write_jsonl(tmp_path / "qrels.jsonl", qrels)
    out_dir = tmp_path / "out"
    run_retrieval_cli(corpus_p, queries_p, out_dir)
    report_p = tmp_path / "g4_report.json"
    run_scorer_cli(
        out_dir / "g3_sealed_rankings_v1.jsonl",
        out_dir / "g3_sealed_rankings_v1_manifest.json",
        qrels_p,
        queries_p,
        report_p,
        strict_full_pool=True,
    )
    report = read_json(report_p)
    cells = extract_cells_map(report)
    assert set(cells.keys()) == set(ALL_SIX_CELLS)
    contrasts = extract_contrasts_map(report)
    assert {"K1", "K2", "K3", "K4", "K5"}.issubset(contrasts.keys())
    assert extract_metric_value(report, ["false_support_exposure_at_10", "FalseSupportExposure@10", "false_support_exposure_10"]) is not None


def test_t1_f10_02_coupled_contrast_no_clear_winner_and_non_identifying(tmp_path: Path) -> None:
    require_scorer_cli()
    # Engineer Q1..Q2 where Delta_min < 0.030 <= Delta_max across K1 (C1-RRF vs C1-BM25)
    docs = {f"d{i}": make_b1b_doc(f"d{i}", f"D{i}", f"Văn bản {i}") for i in range(1, 5)}
    queries = [make_query_row("Q1", "q1"), make_query_row("Q2", "q2")]
    rank_map = {
        ("C1-RRF", "Q1"): [("d1", 2.0), ("d2", 1.0)],
        ("C1-BM25", "Q1"): [("d2", 2.0), ("d1", 1.0)],
        ("C1-RRF", "Q2"): [("d1", 2.0), ("d2", 1.0)],
        ("C1-BM25", "Q2"): [("d2", 2.0), ("d1", 1.0)],
    }
    # d1=REL_2 (gain=3), d2=REL_1 (gain=1), d3=REL_0, d4=UNJUDGED (out of top-10)
    # On Q1,Q2: DCG(A)-DCG(B) > 0, IDCG_L = 3+1/log2(3) = 3.6309, IDCG_U = 3+3/log2(3) = 4.8928
    # Wait: (3+1/1.585) - (1+3/1.585) = 0.7386; 0.7386/3.63 = 0.203, 0.7386/4.89 = 0.15.
    # To straddle +0.030: use 10 queries (or 1 exact=0.0, 1 bounded with Delta in [0.010, 0.050])
    # With 12 queries: 11 tied exact (delta=0), 1 with d1=REL_2, d2=REL_1 vs d2=REL_2? Better: d1=REL_1 (1) at rank 1 vs rank 2 (0.6309), diff = 0.3691;
    # If IDCG_L = 3.0 and IDCG_U = 5.0 -> 0.3691/5.0 = 0.0738, 0.3691/3.0 = 0.123. Across 3 queries (2 tied exact): mean = [0.0246, 0.0410] straddling 0.030!
    queries = [make_query_row(f"Q{i}", f"q{i}") for i in range(1, 4)]
    rank_map = {
        ("C1-RRF", "Q1"): [("d1", 2.0), ("d3", 1.0)],
        ("C1-BM25", "Q1"): [("d3", 2.0), ("d1", 1.0)],
        ("C1-RRF", "Q2"): [("d1", 2.0), ("d3", 1.0)],
        ("C1-BM25", "Q2"): [("d1", 2.0), ("d3", 1.0)],
        ("C1-RRF", "Q3"): [("d1", 2.0), ("d3", 1.0)],
        ("C1-BM25", "Q3"): [("d1", 2.0), ("d3", 1.0)],
    }
    qrels = [
        # Q1: d1=REL_1 (1), d2=REL_2 (3, out of top-10!), d3=REL_0, d4=UNJUDGED (out of top-10!) -> IDCG_L=3+1/1.585=3.6309, IDCG_U=3+3/1.585=4.8928
        # diff(Q1) = 1 - 1/1.58496 = 0.36907; across 3 queries: min = 0.36907/(3*4.8928) = 0.02514 < 0.030 <= 0.03388 = 0.36907/(3*3.6309)
        make_qrel_row("Q1", "d1", "REL_1"),
        make_qrel_row("Q1", "d2", "REL_2"),
        make_qrel_row("Q1", "d3", "REL_0"),
        make_qrel_row("Q1", "d4", "UNJUDGED"),
    ]
    for qid in ("Q2", "Q3"):
        qrels.extend(
            [
                make_qrel_row(qid, "d1", "REL_2"),
                make_qrel_row(qid, "d2", "REL_0"),
                make_qrel_row(qid, "d3", "REL_0"),
                make_qrel_row(qid, "d4", "REL_0"),
            ]
        )
    rankings_p, manifest_p = write_synthetic_sealed_rankings(tmp_path / "g3", rank_map, docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", queries)
    qrels_p = write_jsonl(tmp_path / "qrels.jsonl", qrels)
    out_p = tmp_path / "g4_report.json"

    run_scorer_cli(rankings_p, manifest_p, qrels_p, queries_p, out_p)
    report = read_json(out_p)
    k1 = extract_contrasts_map(report)["K1"]
    assert k1["decision"] == "NO_CLEAR_WINNER"
    assert k1["bounds_non_identifying"] is True
    assert "BOUNDS_NON_IDENTIFYING" in k1["flags"]


def test_t1_f10_03_deterministic_pcg64_bootstrap_and_holm_k1_k5(tmp_path: Path) -> None:
    require_scorer_cli()
    docs = {f"d{i}": make_b1b_doc(f"d{i}", f"D{i}", f"Nội dung {i}") for i in range(1, 5)}
    queries = [make_query_row(f"Q{i:02d}", f"q{i}") for i in range(1, 41)]
    rank_map: Dict[tuple[str, str], List[tuple[str, float]]] = {}
    qrels: List[Dict[str, Any]] = []
    for qi, q in enumerate(queries, start=1):
        for cell in ALL_SIX_CELLS:
            order = [("d1", 4.0), ("d2", 3.0), ("d3", 2.0)] if ("C1" in cell and qi % 2 == 0) else [("d2", 4.0), ("d1", 3.0), ("d3", 2.0)]
            rank_map[(cell, q["query_id"])] = order
        qrels.extend(
            [
                make_qrel_row(q["query_id"], "d1", "REL_2"),
                make_qrel_row(q["query_id"], "d2", "REL_1"),
                make_qrel_row(q["query_id"], "d3", "REL_0"),
                make_qrel_row(q["query_id"], "d4", "REL_0"),
            ]
        )
    rankings_p, manifest_p = write_synthetic_sealed_rankings(tmp_path / "g3", rank_map, docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", queries)
    qrels_p = write_jsonl(tmp_path / "qrels.jsonl", qrels)
    out1 = tmp_path / "g4_1.json"
    out2 = tmp_path / "g4_2.json"

    run_scorer_cli(rankings_p, manifest_p, qrels_p, queries_p, out1)
    run_scorer_cli(rankings_p, manifest_p, qrels_p, queries_p, out2)
    assert out1.read_bytes() == out2.read_bytes()
    contrasts = extract_contrasts_map(read_json(out1))
    assert {"K1", "K2", "K3", "K4", "K5"}.issubset(contrasts.keys())
    for k in ("K1", "K2", "K3", "K4", "K5"):
        p_val = extract_metric_value(contrasts[k], ["p_mc_holm", "p_holm", "holm_p_value"])
        assert p_val is not None and not math.isnan(float(p_val))


def test_t1_f10_04_unanswerable_separation_and_zero_g5_claims_fx16(tmp_path: Path) -> None:
    require_scorer_cli()
    docs = {f"d{i}": make_b1b_doc(f"d{i}", f"D{i}", f"Nội dung {i}") for i in range(1, 12)}
    queries = [
        make_query_row("Q-ANS", "ans"),
        make_query_row(
            "Q-UNANS",
            "unans",
            query_family="S5_UNANSWERABLE_OR_UNSTABLE",
            pre_rank_answerability="UNANSWERABLE",
        ),
    ]
    rank_map = {
        ("C1-Dense", "Q-ANS"): [("d1", 2.0)],
        ("C1-BM25", "Q-ANS"): [("d1", 2.0)],
        ("C1-Dense", "Q-UNANS"): [(f"d{i}", float(20 - i)) for i in range(1, 11)],
        ("C1-BM25", "Q-UNANS"): [("d11", 5.0)],
    }
    qrels = [make_qrel_row("Q-ANS", f"d{i}", "REL_2" if i == 1 else "REL_0") for i in range(1, 12)]
    for i in range(1, 12):
        qrels.append(
            make_qrel_row(
                "Q-UNANS",
                f"d{i}",
                "REL_0",
                plausible_unsupported_lure=1 if i == 11 else 0,
            )
        )
    rankings_p, manifest_p = write_synthetic_sealed_rankings(tmp_path / "g3", rank_map, docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", queries)
    qrels_p = write_jsonl(tmp_path / "qrels.jsonl", qrels)
    out_p = tmp_path / "g4_report.json"

    run_scorer_cli(rankings_p, manifest_p, qrels_p, queries_p, out_p)
    report = read_json(out_p)
    assert not report_contains_token(report, "CorrectAbstentionRate")
    assert not report_contains_token(report, "G5 PASS")
    unans_map = extract_unanswerable_map(report)
    dense_u = unans_map.get("C1-Dense", extract_cells_map(report).get("C1-Dense", report))
    bm25_u = unans_map.get("C1-BM25", extract_cells_map(report).get("C1-BM25", report))
    assert float(extract_metric_value(dense_u, ["any_result_at_10", "AnyResult@10", "any_result_10"])) == pytest.approx(1.0)
    assert float(extract_metric_value(dense_u, ["false_support_exposure_at_10", "FalseSupportExposure@10", "false_support_exposure_10"])) == pytest.approx(0.0)
    assert float(extract_metric_value(bm25_u, ["false_support_exposure_at_10", "FalseSupportExposure@10", "false_support_exposure_10"])) == pytest.approx(1.0)


def test_t1_f10_05_zero_ml_import_isolation_via_poisoned_pythonpath(tmp_path: Path) -> None:
    require_scorer_cli()
    docs = {"d1": make_b1b_doc("d1", "D1", "Văn bản 1.")}
    queries = [make_query_row("Q1", "q1")]
    rankings_p, manifest_p = write_synthetic_sealed_rankings(
        tmp_path / "g3", {("C1-BM25", "Q1"): [("d1", 1.0)]}, docs
    )
    queries_p = write_jsonl(tmp_path / "queries.jsonl", queries)
    qrels_p = write_jsonl(tmp_path / "qrels.jsonl", [make_qrel_row("Q1", "d1", "REL_2")])
    poison_dir = make_poison_pythonpath(
        tmp_path, sorted(PROHIBITED_G4_MODULES), mode="exit99"
    )
    out_p = tmp_path / "g4_report.json"

    run_scorer_cli(
        rankings_p,
        manifest_p,
        qrels_p,
        queries_p,
        out_p,
        extra_pythonpath=[poison_dir],
    )
    assert out_p.is_file()


# ===========================================================================
# Feature 11: Synthetic FX-01..FX-16 & Gated Real Stubs (T1-F11-01 .. T1-F11-05)
# ===========================================================================


def test_t1_f11_01_gated_real_corpus_stubs_collect_offline(tmp_path: Path) -> None:
    stub = require_real_corpus_stubs()
    proc = run_pytest_subprocess([stub], extra_args=["--collect-only", "-q"])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "fx01" in proc.stdout.lower() or "real" in proc.stdout.lower()


def test_t1_f11_02_default_unset_env_skips_100pct_real_corpus_stubs() -> None:
    stub = require_real_corpus_stubs()
    proc = run_pytest_subprocess([stub], extra_args=["-rs", "-m", "real_corpus_gated"])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "0 failed" in proc.stdout.lower() or "failed" not in proc.stdout.lower()
    assert "skipped" in proc.stdout.lower()
    assert "5 skipped" in proc.stdout.lower()


def test_t1_f11_03_synthetic_fx01_manifest_sha256_offline(tmp_path: Path) -> None:
    require_retrieval_cli()
    files = {}
    for i in range(1, 8):
        p = tmp_path / f"syn_file_{i}.json"
        p.write_bytes(json.dumps({"id": i}).encode("utf-8"))
        files[p.name] = {"size": p.stat().st_size, "sha256": file_sha256(p)}
    manifest_p = tmp_path / "syn_manifest.json"
    manifest_p.write_text(json.dumps(files), encoding="utf-8")
    probe = f"""
import hashlib, json, pathlib
m = json.loads(pathlib.Path({str(manifest_p)!r}).read_text(encoding='utf-8'))
for name, meta in m.items():
    b = (pathlib.Path({str(tmp_path)!r}) / name).read_bytes()
    assert len(b) == meta['size']
    assert hashlib.sha256(b).hexdigest() == meta['sha256']
print('FX01_SYNTH_OK')
"""
    proc = run_python_probe(probe)
    assert "FX01_SYNTH_OK" in proc.stdout


def test_t1_f11_04_synthetic_fx02_character_conservation_offline() -> None:
    fx_file = require_fx_test_file("test_fx02_to_fx05_corpus_and_chunking.py")
    proc = run_pytest_subprocess([fx_file], extra_args=["-k", "not real_corpus"], timeout=600)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "failed" not in proc.stdout.lower()


def test_t1_f11_05_full_synthetic_fx_discovery_offline() -> None:
    require_fx_test_file("test_fx02_to_fx05_corpus_and_chunking.py")
    require_fx_test_file("test_fx12_to_fx16_g4_scorer.py")
    proc = run_pytest_subprocess([REPO_ROOT / "tests"], extra_args=["--collect-only", "-q"])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "test_fx" in proc.stdout


# ===========================================================================
# Feature 12: R4 Non-Mutation & R5 Audit Package (T1-F12-01 .. T1-F12-05)
# ===========================================================================


def _run_build_audit_into(tmp_path: Path, build_script: Path) -> Path:
    help_proc = subprocess.run(
        [_python_exe(), "-B", str(build_script), "--help"],
        cwd=str(REPO_ROOT),
        env=build_safe_offline_env(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    cmd = [_python_exe(), "-B", str(build_script)]
    if "--output-dir" in (help_proc.stdout + help_proc.stderr):
        cmd.extend(["--output-dir", str(tmp_path)])
    proc = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        env=build_safe_offline_env(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return tmp_path if "--output-dir" in (help_proc.stdout + help_proc.stderr) else REPO_ROOT.parent


def test_t1_f12_01_verify_non_mutation_baseline_pass() -> None:
    verify_script, _ = require_packaging_scripts()
    proc = subprocess.run(
        [_python_exe(), "-B", str(verify_script)],
        cwd=str(REPO_ROOT),
        env=build_safe_offline_env(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert WANDERAI_EXPECTED_HEAD in (proc.stdout + proc.stderr)


def test_t1_f12_02_build_audit_package_produces_zip_md_json_receipt(tmp_path: Path) -> None:
    _, build_script = require_packaging_scripts()
    out_root = _run_build_audit_into(tmp_path, build_script)
    zip_p = out_root / "GOMATE_W07_OFFLINE_RETRIEVAL_PREP_AUDIT_2026-11-20.zip"
    md_p = out_root / "W07_OFFLINE_RETRIEVAL_PREP_AUDIT_REPORT_2026-11-20.md"
    rec_p = out_root / "W07_OFFLINE_RETRIEVAL_PREP_SHA256_RECEIPT.json"
    assert zip_p.is_file()
    assert md_p.is_file()
    assert rec_p.is_file()
    receipt = read_json(rec_p)
    digest = extract_metric_value(receipt, ["deliverable_zip_sha256", "zip_sha256", "sha256"])
    assert digest == file_sha256(zip_p)


def test_t1_f12_03_deterministic_zip_repackaging_sha256_identity(tmp_path: Path) -> None:
    _, build_script = require_packaging_scripts()
    d1 = _run_build_audit_into(tmp_path / "r1", build_script)
    d2 = _run_build_audit_into(tmp_path / "r2", build_script)
    z1 = d1 / "GOMATE_W07_OFFLINE_RETRIEVAL_PREP_AUDIT_2026-11-20.zip"
    z2 = d2 / "GOMATE_W07_OFFLINE_RETRIEVAL_PREP_AUDIT_2026-11-20.zip"
    assert file_sha256(z1) == file_sha256(z2)


def test_t1_f12_04_zip_member_hygiene_sorted_fixed_timestamp_zero_caches(tmp_path: Path) -> None:
    _, build_script = require_packaging_scripts()
    out_root = _run_build_audit_into(tmp_path, build_script)
    zip_p = out_root / "GOMATE_W07_OFFLINE_RETRIEVAL_PREP_AUDIT_2026-11-20.zip"
    with zipfile.ZipFile(zip_p, "r") as zf:
        names = zf.namelist()
        assert names == sorted(names)
        for info in zf.infolist():
            assert info.date_time == (2026, 11, 20, 0, 0, 0)
            assert "__pycache__" not in info.filename
            assert not info.filename.endswith(".pyc")
            assert ".pytest_cache" not in info.filename
            assert "/.git/" not in info.filename and not info.filename.startswith(".git/")


def test_t1_f12_05_governance_non_claim_flags_in_receipt_and_report(tmp_path: Path) -> None:
    _, build_script = require_packaging_scripts()
    out_root = _run_build_audit_into(tmp_path, build_script)
    md_text = (out_root / "W07_OFFLINE_RETRIEVAL_PREP_AUDIT_REPORT_2026-11-20.md").read_text(encoding="utf-8")
    receipt = read_json(out_root / "W07_OFFLINE_RETRIEVAL_PREP_SHA256_RECEIPT.json")
    assert extract_metric_value(receipt, ["w07_scientific_closed"]) is False
    assert extract_metric_value(receipt, ["g15_frozen"]) is False
    assert "G3 PASS" not in md_text
    assert "G4 PASS" not in md_text
