"""Tier 2 Opaque-Box E2E Tests — Boundary Values & Negative/Error Paths (69 tests).

Covers all 12 features in PROJECT.md § Feature Inventory (`T2-F01-01..T2-F12-05`:
68 feature boundary/negative tests) plus standalone offline Python 3.11.9 &
cached HuggingFace snapshot `tokenizer.json` SHA-256 verification.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any, Dict, List

import pytest

from .conftest import (
    EXPECTED_PYTHON,
    HF_SNAPSHOT_DIR,
    REPO_ROOT,
    TOKENIZER_SHA256,
    WANDERAI_EXPECTED_HEAD,
    WANDERAI_ROOT,
    _python_exe,
    build_safe_offline_env,
    cached_minilm_tokenizer,
    extract_cells_map,
    extract_contrasts_map,
    extract_metric_value,
    extract_per_query_map,
    file_sha256,
    is_blocked_or_invalid_status,
    read_json,
    read_jsonl,
    report_contains_token,
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
)
from .synthetic_builders import (
    make_5x3_query_matrix,
    make_b1b_doc,
    make_judge_record,
    make_judge_response_json,
    make_multi_level_doc,
    make_overture_doc,
    make_poison_pythonpath,
    make_qrel_row,
    make_query_row,
    tamper_one_byte,
    write_jsonl,
    write_synthetic_sealed_rankings,
)


def _eval_judge_item(
    tmp_path: Path,
    doc: Dict[str, Any],
    query: Dict[str, Any],
    raw_response: str,
    removed_spans_by_doc: Dict[str, List[List[int]]] | None = None,
) -> Dict[str, Any]:
    """Evaluate one judge payload via CLI if supported, else public judge_gates probe."""
    docs = {doc["document_id"]: doc}
    rankings_p, manifest_p = write_synthetic_sealed_rankings(
        tmp_path / "g3", {("C1-BM25", query["query_id"]): [(doc["document_id"], 1.0)]}, docs
    )
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [query])
    if scorer_supports_flag("--judge-a") and scorer_supports_flag("--judge-b"):
        row = {"query_id": query["query_id"], "document_id": doc["document_id"], "raw_json_str": raw_response}
        ja_p = write_jsonl(tmp_path / "ja.jsonl", [row])
        jb_p = write_jsonl(tmp_path / "jb.jsonl", [row])
        out_p = tmp_path / "g4.json"
        rem_p = None
        if removed_spans_by_doc:
            rem_p = tmp_path / "rem.json"
            rem_p.write_text(json.dumps(removed_spans_by_doc), encoding="utf-8")
        proc = run_scorer_cli(
            rankings_p,
            manifest_p,
            None,
            queries_p,
            out_p,
            removed_audit_spans=rem_p,
            judge_a_path=ja_p,
            judge_b_path=jb_p,
            docs_path=write_jsonl(tmp_path / "docs.jsonl", [doc]),
            check=False,
        )
        return {"returncode": proc.returncode, "report": read_json(out_p) if out_p.is_file() else {}}

    probe = f"""
import json
import w07_g4_scorer.judge_gates as jg
doc = {json.dumps({"canonical_text_S": doc["canonical_text_S"], "city": doc["city"], "poi_id": doc["poi_id"]}, ensure_ascii=False)}
q = {json.dumps(query, ensure_ascii=False)}
raw = {raw_response!r}
res = jg.validate_judge_response(raw, doc, [], q)
print(json.dumps(res, ensure_ascii=False))
"""
    proc = run_python_probe(probe, check=False)
    if proc.returncode != 0:
        return {"returncode": proc.returncode, "report": {"error": proc.stderr}}
    return {"returncode": 0, "report": json.loads(proc.stdout)}


def _run_build_script(tmp_path: Path, build_script: Path, env_overrides: Dict[str, str] | None = None) -> Path:
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
    uses_out_dir = "--output-dir" in (help_proc.stdout + help_proc.stderr)
    if uses_out_dir:
        cmd.extend(["--output-dir", str(tmp_path)])
    proc = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        env=build_safe_offline_env(env_overrides=env_overrides),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return tmp_path if uses_out_dir else REPO_ROOT.parent


# ===========================================================================
# Standalone Environment & Snapshot Integrity Test (Executes Immediately)
# ===========================================================================


def test_t2_env_offline_python311_and_snapshot_tokenizer_sha256() -> None:
    assert sys.version_info[:2] == (3, 11)
    assert EXPECTED_PYTHON.is_file()
    tok_path = HF_SNAPSHOT_DIR / "tokenizer.json"
    assert tok_path.is_file(), f"Missing cached snapshot tokenizer.json at {tok_path}"
    actual_sha = hashlib.sha256(tok_path.read_bytes()).hexdigest()
    assert actual_sha == TOKENIZER_SHA256


# ===========================================================================
# Feature 1 Tier 2: D03.1-D03.2 Canonical S & Headings (T2-F01-01 .. T2-F01-05)
# ===========================================================================


def test_t2_f01_01_footer_allowlist_vs_non_allowlist_and_non_empty(tmp_path: Path) -> None:
    require_retrieval_cli()
    text_s = (
        "== Giới thiệu ==\nNội dung giới thiệu chính về bảo tàng cổ tại Hà Nội.\n"
        "== Xem thêm ==\n\n"
        "== References ==\n\n"
        "== Ghi chú riêng ==\n\n"
        "== Notes ==\nGhi chú quan trọng cho du khách."
    )
    doc = make_b1b_doc("doc-f01-b1", "Bảo tàng", text_s)
    q = make_query_row("Q1", "Ghi chú quan trọng", requested_facet_keywords=["Ghi chú quan trọng"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", [doc])
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-BM25"], packet_salt="FOOTER")
    chunks = read_jsonl(out_dir / "chunks_manifest.jsonl")
    joined = "\n".join(c["assembled_text"] for c in chunks)
    assert "Xem thêm" not in joined
    assert "References" not in joined
    assert "Ghi chú quan trọng" in joined
    assert "Ghi chú riêng" in joined


def test_t2_f01_02_non_empty_parent_heading_does_not_propagate_breadcrumb(tmp_path: Path) -> None:
    require_retrieval_cli()
    doc = make_multi_level_doc(
        "doc-f01-b2",
        "Đền cổ",
        [
            (2, "Kiến trúc", "."),
            (3, "Cổng chính", "Cổng gỗ lim chạm khắc tinh xảo tại Hà Nội."),
        ],
    )
    q = make_query_row("Q1", "Cổng gỗ lim", requested_facet_keywords=["Cổng gỗ lim"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", [doc])
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-BM25"], timeout=600)
    rows = read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl")
    assert len(rows) == 1
    assert "Kiến trúc > Cổng chính" not in rows[0]["assembled_text"]


def test_t2_f01_03_heading_only_evidence_vs_omitted_boilerplate(tmp_path: Path) -> None:
    require_retrieval_cli()
    text_s = (
        "== Lịch sử cổ đại ==\nNội dung chi tiết giai đoạn đầu.\n"
        "== External links ==\n"
    )
    doc = make_b1b_doc("doc-f01-b3", "Di tích", text_s)
    q = make_query_row("Q1", "Lịch sử cổ đại", requested_facet_keywords=["Lịch sử cổ đại"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", [doc])
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-BM25"], timeout=600)
    rows = read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl")
    assert len(rows) == 1
    covered = "".join(text_s[a:b] for a, b in rows[0]["c_full_s_spans"])
    assert "Lịch sử cổ đại" in covered
    assert "External links" not in covered
    assert "External links" not in rows[0]["assembled_text"]


@pytest.mark.parametrize(
    "bad_row",
    [
        {"document_id": "d-missing-text", "source_type": "wikipedia_article", "title": "X"},
        {"source_type": "wikipedia_article", "title": "Y", "canonical_text_S": "Có chữ."},
    ],
)
def test_t2_f01_04_missing_text_or_document_id_fails_closed(
    tmp_path: Path, bad_row: Dict[str, Any]
) -> None:
    require_retrieval_cli()
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", [bad_row])
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [make_query_row("Q1", "test")])
    proc = run_retrieval_cli(
        corpus_p, queries_p, tmp_path / "out", cells=["C1-BM25"], check=False
    )
    assert proc.returncode != 0


def test_t2_f01_05_supplementary_emoji_and_nfd_codepoint_alignment(tmp_path: Path) -> None:
    require_retrieval_cli()
    text_s = "🏛️ Đền Ngọc Sơn\u0301 đẹp và cổ kính tại trung tâm thủ đô Hà Nội."
    doc = make_b1b_doc("doc-f01-b5", "Ngọc Sơn", text_s)
    q = make_query_row("Q1", "Đền Ngọc Sơn", requested_facet_keywords=["Đền Ngọc Sơn"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", [doc])
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-BM25"], timeout=600)
    rows = read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl")
    assert len(rows) == 1
    for sa, sb in rows[0]["c_full_s_spans"]:
        piece = text_s[sa:sb]
        assert piece.encode("utf-8").decode("utf-8") == piece


# ===========================================================================
# Feature 2 Tier 2: D03.3 Sanitization S -> V (T2-F02-01 .. T2-F02-06)
# ===========================================================================


def test_t2_f02_01_adjacent_zero_gap_r_audit_tags(tmp_path: Path) -> None:
    require_retrieval_cli()
    t1 = "[CORROBORATED: osm:node/1]"
    t2 = "[CORROBORATED: wikidata:Q2]"
    doc, rem = make_overture_doc(
        "doc-f02-b1",
        "Điểm nối",
        [("Đầu ", t1), ("", t2), (" cuối tuyến.", None)],
        confidence=None,
    )
    assert rem[0][1] == rem[1][0]
    q = make_query_row("Q1", "Đầu cuối tuyến", requested_facet_keywords=["Đầu"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", [doc])
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-BM25"], timeout=600)
    row = read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl")[0]
    assert "Đầu  cuối tuyến." in row["assembled_text"]
    assert "[CORROBORATED" not in row["assembled_text"]
    assert len(row["c_full_s_spans"]) >= 2
    for sa, sb in row["c_full_s_spans"]:
        for ra, rb in rem:
            assert max(sa, ra) >= min(sb, rb)


def test_t2_f02_02_r_audit_tags_at_exact_start_and_end_of_s(tmp_path: Path) -> None:
    require_retrieval_cli()
    t1 = "[CORROBORATED: osm:node/1]"
    t2 = "[CORROBORATED: wikidata:Q2]"
    doc, _ = make_overture_doc(
        "doc-f02-b2",
        "Biên",
        [("", t1), ("Nội dung giữa đầy đủ thông tin.", t2)],
        confidence=None,
    )
    text_s = doc["canonical_text_S"]
    q = make_query_row("Q1", "Nội dung giữa", requested_facet_keywords=["giữa"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", [doc])
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-BM25"], timeout=600)
    row = read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl")[0]
    assert row["c_full_s_spans"] == [[len(t1), len(text_s) - len(t2)]]
    assert "Nội dung giữa đầy đủ thông tin." in row["assembled_text"]


def test_t2_f02_03_unclosed_r_audit_fails_closed(tmp_path: Path) -> None:
    require_retrieval_cli()
    doc = make_b1b_doc("d-bad", "Bad", "Text [CORROBORATED: osm:node/123 end.")
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", [doc])
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [make_query_row("Q1", "Text")])
    proc = run_retrieval_cli(corpus_p, queries_p, tmp_path / "out", cells=["C1-BM25"], check=False)
    assert proc.returncode != 0


def test_t2_f02_04_multiline_r_audit_fails_closed(tmp_path: Path) -> None:
    require_retrieval_cli()
    doc = make_b1b_doc("d-bad", "Bad", "Text [CORROBORATED: osm:node/123\n] end.")
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", [doc])
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [make_query_row("Q1", "Text")])
    proc = run_retrieval_cli(corpus_p, queries_p, tmp_path / "out", cells=["C1-BM25"], check=False)
    assert proc.returncode != 0


@pytest.mark.parametrize(
    "bad_tag",
    ["Text [CORROBORATED without colon] end.", "Text [CORROBORATED: ] end."],
)
def test_t2_f02_05_missing_colon_or_empty_r_audit_fails_closed(
    tmp_path: Path, bad_tag: str
) -> None:
    require_retrieval_cli()
    doc = make_b1b_doc("d-bad", "Bad", bad_tag)
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", [doc])
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [make_query_row("Q1", "Text")])
    proc = run_retrieval_cli(corpus_p, queries_p, tmp_path / "out", cells=["C1-BM25"], check=False)
    assert proc.returncode != 0


@pytest.mark.parametrize(
    "bad_tag",
    [
        "Text [CORROBORATED: unknown_family:abc] end.",
        "Text [CORROBORATED: canonical_poi:not-a-uuid] end.",
        "Text [CORROBORATED: osm:invalid_type/123] end.",
    ],
)
def test_t2_f02_06_layer2_invalid_family_uuid_osm_type_fails_closed(
    tmp_path: Path, bad_tag: str
) -> None:
    require_retrieval_cli()
    doc = make_b1b_doc("d-bad", "Bad", bad_tag)
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", [doc])
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [make_query_row("Q1", "Text")])
    proc = run_retrieval_cli(corpus_p, queries_p, tmp_path / "out", cells=["C1-BM25"], check=False)
    assert proc.returncode != 0


# ===========================================================================
# Feature 3 Tier 2: D03.4 C0 vs C1 Chunking & C_vis (T2-F03-01 .. T2-F03-06)
# ===========================================================================


def test_t2_f03_01_c1_exact_128_vs_129_subword_tokens(tmp_path: Path) -> None:
    require_retrieval_cli()
    tok = cached_minilm_tokenizer()
    prefix = "Title | Muc\n"
    words = ["alpha"]
    while len(tok.encode(prefix + " ".join(words), add_special_tokens=True, truncation=False)) < 128:
        words.append("beta")
    # Adjust if a token pushed count > 128 (shouldn't happen for single-subword 'beta')
    while len(tok.encode(prefix + " ".join(words), add_special_tokens=True, truncation=False)) > 128:
        words.pop()
    assert len(tok.encode(prefix + " ".join(words), add_special_tokens=True, truncation=False)) == 128
    body_128 = " ".join(words)
    body_129 = body_128 + " gamma"
    assert len(tok.encode(prefix + body_129, add_special_tokens=True, truncation=False)) == 129

    docs = [
        make_b1b_doc("d-128", "Title", f"== Muc ==\n{body_128}"),
        make_b1b_doc("d-129", "Title", f"== Muc ==\n{body_129}"),
    ]
    q = make_query_row("Q1", "alpha beta", requested_facet_keywords=["alpha"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-BM25", "C1-Dense"], packet_salt="TOK128")
    chunks = read_jsonl(out_dir / "chunks_manifest.jsonl")
    c_128 = [c for c in chunks if c["document_id"] == "d-128" and c.get("chunker", "C1") == "C1"]
    c_129 = [c for c in chunks if c["document_id"] == "d-129" and c.get("chunker", "C1") == "C1"]
    assert len(c_128) == 1
    assert len(tok.encode(c_128[0]["assembled_text"], add_special_tokens=True, truncation=False)) == 128
    assert len(c_129) == 2
    for ch in c_129:
        assert len(tok.encode(ch["assembled_text"], add_special_tokens=True, truncation=False)) <= 128


def test_t2_f03_02_c0_nine_words_dropped_vs_ten_words_kept(tmp_path: Path) -> None:
    require_retrieval_cli()
    text_s = (
        "== Ngắn ==\nMột hai ba bốn năm sáu bảy tám chín.\n"
        "== Đủ ==\nMột hai ba bốn năm sáu bảy tám chín mười."
    )
    doc = make_b1b_doc("doc-9v10", "Độ dài", text_s)
    q = make_query_row("Q1", "một hai ba bốn", requested_facet_keywords=["một"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", [doc])
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C0-BM25", "C1-BM25"], packet_salt="W9V10")
    chunks = read_jsonl(out_dir / "chunks_manifest.jsonl")
    c0_texts = [c["assembled_text"] for c in chunks if c.get("chunker") == "C0"]
    c1_texts = [c["assembled_text"] for c in chunks if c.get("chunker") == "C1"]
    assert len(c0_texts) == 1 and "Đủ" in c0_texts[0] and "Ngắn" not in c0_texts[0]
    assert len(c1_texts) == 2


def test_t2_f03_03_adversarial_synthetic_header_tail_echo_fx05(tmp_path: Path) -> None:
    require_retrieval_cli()
    require_scorer_cli()
    filler = "Thông tin giới thiệu tổng quan về bảo tàng lịch sử văn hóa dân tộc tại Hà Nội. " * 15
    tail = "Mã đặc biệt cuối: ARCHIVE-TAIL-9981."
    text_s = filler + tail
    doc = make_b1b_doc("doc-adv", "ARCHIVE-TAIL-9981", text_s)
    tail_idx = text_s.rindex("ARCHIVE-TAIL-9981")
    tail_span = [[tail_idx, tail_idx + len("ARCHIVE-TAIL-9981")]]
    q = make_query_row(
        "Q1",
        "ARCHIVE-TAIL-9981",
        requested_facet_keywords=["ARCHIVE-TAIL-9981"],
        required_evidence_facets=[[{"document_id": "doc-adv", "s_spans": tail_span}]],
    )
    qrel = make_qrel_row("Q1", "doc-adv", "REL_2", evidence_s_spans=tail_span)
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", [doc])
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    qrels_p = write_jsonl(tmp_path / "qrels.jsonl", [qrel])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C0-Dense"])
    rep_p = tmp_path / "g4.json"
    run_scorer_cli(
        out_dir / "g3_sealed_rankings_v1.jsonl",
        out_dir / "g3_sealed_rankings_v1_manifest.json",
        qrels_p,
        queries_p,
        rep_p,
    )
    c0 = extract_cells_map(read_json(rep_p))["C0-Dense"]
    assert float(extract_metric_value(c0, ["EvidenceSpanHit@10", "evidence_span_hit_10"])) == pytest.approx(1.0)
    assert float(extract_metric_value(c0, ["VisibleEvidenceSpanHit@10", "visible_evidence_span_hit_10"])) == pytest.approx(0.0)


def test_t2_f03_04_evidence_span_straddling_token_128_129_cutoff(tmp_path: Path) -> None:
    require_retrieval_cli()
    require_scorer_cli()
    tok = cached_minilm_tokenizer()
    header = "Title - Introduction\n"
    words = ["alpha"]
    while len(tok.encode(header + " ".join(words), add_special_tokens=True, truncation=False)) < 126:
        words.append("alpha")
    marker = "MASODACBIETCUOICUNGXYZ"
    body = " ".join(words) + f" {marker} tail extra prose."
    doc = make_b1b_doc("doc-straddle", "Title", body)
    m_start = body.index(marker)
    m_span = [[m_start, m_start + len(marker)]]
    q = make_query_row(
        "Q1",
        marker,
        requested_facet_keywords=[marker],
        required_evidence_facets=[[{"document_id": "doc-straddle", "s_spans": m_span}]],
    )
    qrel = make_qrel_row("Q1", "doc-straddle", "REL_2", evidence_s_spans=m_span)
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", [doc])
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    qrels_p = write_jsonl(tmp_path / "qrels.jsonl", [qrel])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C0-Dense"])
    rep_p = tmp_path / "g4.json"
    run_scorer_cli(
        out_dir / "g3_sealed_rankings_v1.jsonl",
        out_dir / "g3_sealed_rankings_v1_manifest.json",
        qrels_p,
        queries_p,
        rep_p,
    )
    c0 = extract_cells_map(read_json(rep_p))["C0-Dense"]
    assert float(extract_metric_value(c0, ["EvidenceSpanHit@10", "evidence_span_hit_10"])) == pytest.approx(1.0)
    assert float(extract_metric_value(c0, ["VisibleEvidenceSpanHit@10", "visible_evidence_span_hit_10"])) == pytest.approx(0.0)


def test_t2_f03_05_unpunctuated_180_word_clause_word_fallback_in_c1(tmp_path: Path) -> None:
    require_retrieval_cli()
    body = " ".join(f"word{i}" for i in range(1, 185))
    doc = make_b1b_doc("doc-nopunct", "Clause", body)
    q = make_query_row("Q1", "word1 word180", requested_facet_keywords=["word1"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", [doc])
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-BM25", "C1-Dense"], packet_salt="NOPUNCT")
    tok = cached_minilm_tokenizer()
    chunks = [
        c
        for c in read_jsonl(out_dir / "chunks_manifest.jsonl")
        if c["document_id"] == "doc-nopunct" and c.get("chunker", "C1") == "C1"
    ]
    assert len(chunks) >= 2
    covered = set()
    for ch in chunks:
        assert len(tok.encode(ch["assembled_text"], add_special_tokens=True, truncation=False)) <= 128
        for sa, sb in ch["c_full_s_spans"]:
            covered.update(range(sa, sb))
    expected = {i for i, c in enumerate(body) if not c.isspace()}
    assert expected.issubset(covered)


def test_t2_f03_06_c0_max_chunk_words_450_vs_451(tmp_path: Path) -> None:
    require_retrieval_cli()
    # 45 sentences * 10 words = 450 words; +12-word sentence = 462 words (>=10-word 2nd chunk after 1-sentence overlap)
    sents_450 = " ".join(
        f"Token{i:02d} w2 w3 w4 w5 w6 w7 w8 w9 w10." for i in range(1, 46)
    )
    sents_462 = sents_450 + " Token46 x2 x3 x4 x5 x6 x7 x8 x9 x10 x11 finalword."
    docs = [
        make_b1b_doc("d-450", "D450", sents_450),
        make_b1b_doc("d-451", "D451", sents_462),
    ]
    q = make_query_row("Q1", "Token1", requested_facet_keywords=["Token1"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C0-BM25"], packet_salt="W450")
    chunks = [c for c in read_jsonl(out_dir / "chunks_manifest.jsonl") if c.get("chunker", "C0") == "C0"]
    c450 = [c for c in chunks if c["document_id"] == "d-450"]
    c451 = [c for c in chunks if c["document_id"] == "d-451"]
    assert len(c450) == 1
    assert len(c451) == 2
    s0 = {i for a, b in c451[0]["c_full_s_spans"] for i in range(a, b)}
    s1 = {i for a, b in c451[1]["c_full_s_spans"] for i in range(a, b)}
    assert len(s0 & s1) > 0


# ===========================================================================
# Feature 4 Tier 2: D04.2 Lexical BM25 (T2-F04-01 .. T2-F04-05)
# ===========================================================================


def test_t2_f04_01_missing_underthesea_blocked_no_split_fallback(tmp_path: Path) -> None:
    require_retrieval_cli()
    poison_dir = make_poison_pythonpath(tmp_path, ["underthesea"], mode="importerror")
    docs = [make_b1b_doc("d1", "Test", "Khách sạn hồ Hoàn Kiếm.")]
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [make_query_row("Q1", "khách sạn")])
    proc = run_retrieval_cli(
        corpus_p,
        queries_p,
        tmp_path / "out",
        cells=["C1-BM25"],
        extra_pythonpath=[poison_dir],
        check=False,
    )
    assert proc.returncode != 0


def test_t2_f04_02_bm25_zero_score_excluded_on_137_doc_scale_fx09(tmp_path: Path) -> None:
    require_retrieval_cli()
    docs = [
        make_b1b_doc("d-pos-1", "P1", "Chiến thắng Bạch Đằng lịch sử hào hùng."),
        make_b1b_doc("d-pos-2", "P2", "Sông Bạch Đằng nổi tiếng vùng duyên hải."),
    ]
    # 138 synthetic docs (2 positive + 136 zero-BM25 negative): preserves >135-doc FX-09 scale
    # while respecting synthetic-prep's exact-137 real-corpus guard (SYNTHETIC_PREP_REAL_137_CORPUS_FORBIDDEN).
    for i in range(3, 139):
        docs.append(
            make_b1b_doc(
                f"d-neg-{i:03d}",
                f"N{i}",
                f"Địa điểm tham quan du lịch số {i} tại miền Trung Việt Nam.",
            )
        )
    q = make_query_row("Q1", "bạch đằng", requested_facet_keywords=["bạch đằng"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-BM25"], timeout=600)
    rows = read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl")
    assert len(rows) == 2
    assert {r["document_id"] for r in rows} == {"d-pos-1", "d-pos-2"}


def test_t2_f04_03_query_with_zero_matching_terms_clean_empty(tmp_path: Path) -> None:
    require_retrieval_cli()
    docs = [make_b1b_doc("d1", "Hà Nội", "Hồ Hoàn Kiếm và phố cổ Hà Nội.")]
    q = make_query_row("Q1", "xyzzy_nonexistent_999", requested_facet_keywords=["xyzzy"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-BM25"], timeout=600)
    rows = read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl")
    assert rows == []


def test_t2_f04_04_punctuation_only_query_and_chunk_zero_division_safety(tmp_path: Path) -> None:
    require_retrieval_cli()
    docs = [
        make_b1b_doc("d1", "Punct", "! @ # $ % ^ & * ( )"),
        make_b1b_doc("d2", "Normal", "Bảo tàng mỹ thuật mở cửa hàng ngày."),
    ]
    q = make_query_row("Q1", "!!!", requested_facet_keywords=["!!!"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    proc = run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-BM25"], check=False)
    assert "ZeroDivisionError" not in (proc.stdout + proc.stderr)
    if proc.returncode == 0:
        assert read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl") == []


def test_t2_f04_05_equal_bm25_scores_tie_broken_by_document_id_asc(tmp_path: Path) -> None:
    require_retrieval_cli()
    text = "Địa điểm du lịch cổ kính nổi tiếng tại trung tâm thành phố."
    docs = [make_b1b_doc("doc-z", "Cùng", text), make_b1b_doc("doc-a", "Cùng", text)]
    q = make_query_row("Q1", "du lịch cổ kính", requested_facet_keywords=["du lịch"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-BM25"], timeout=600)
    rows = read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl")
    assert [r["document_id"] for r in rows] == ["doc-a", "doc-z"]


# ===========================================================================
# Feature 5 Tier 2: D04.3 Offline Dense (T2-F05-01 .. T2-F05-05)
# ===========================================================================


def test_t2_f05_01_min_similarity_03_disabled_low_cosine_returned(tmp_path: Path) -> None:
    require_retrieval_cli()
    docs = [
        make_b1b_doc("d1", "Match", "Bảo tàng lịch sử tại Hà Nội mở cửa sáng."),
        make_b1b_doc("d2", "Orth1", "Quantum chromodynamics lattice gauge simulation parameter matrix."),
        make_b1b_doc("d3", "Orth2", "Phương trình vi phân đạo hàm riêng trong cơ học chất lỏng."),
        make_b1b_doc("d4", "Orth3", "Cấu hình bộ định tuyến BGP AS4567 trên hạ tầng cáp quang."),
    ]
    q = make_query_row("Q1", "Giờ mở cửa bảo tàng Hà Nội", requested_facet_keywords=["mở cửa"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-Dense"])
    rows = read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl")
    assert len(rows) == 4
    assert any(r["score"] < 0.3 for r in rows)


def test_t2_f05_02_nonexistent_snapshot_dir_fails_closed_no_mock(tmp_path: Path) -> None:
    require_retrieval_cli()
    docs = [make_b1b_doc("d1", "T", "Nội dung mẫu.")]
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [make_query_row("Q1", "mẫu")])
    out_dir = tmp_path / "out"
    proc = run_retrieval_cli(
        corpus_p,
        queries_p,
        out_dir,
        cells=["C1-Dense"],
        snapshot_dir=tmp_path / "missing_snapshot",
        check=False,
    )
    assert proc.returncode != 0
    assert not (out_dir / "g3_sealed_rankings_v1.jsonl").is_file()


def test_t2_f05_03_corrupted_snapshot_dir_fails_closed(tmp_path: Path) -> None:
    require_retrieval_cli()
    corrupt_snap = tmp_path / "corrupt_snap"
    corrupt_snap.mkdir()
    (corrupt_snap / "config.json").write_text("{}", encoding="utf-8")
    docs = [make_b1b_doc("d1", "T", "Nội dung mẫu.")]
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [make_query_row("Q1", "mẫu")])
    proc = run_retrieval_cli(
        corpus_p, queries_p, tmp_path / "out", cells=["C1-Dense"], snapshot_dir=corrupt_snap, check=False
    )
    assert proc.returncode != 0


def test_t2_f05_04_sentence_transformers_failure_fails_closed_no_mock(tmp_path: Path) -> None:
    require_retrieval_cli()
    poison_dir = make_poison_pythonpath(tmp_path, ["sentence_transformers"], mode="runtimeerror")
    docs = [make_b1b_doc("d1", "T", "Nội dung mẫu.")]
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [make_query_row("Q1", "mẫu")])
    proc = run_retrieval_cli(
        corpus_p,
        queries_p,
        tmp_path / "out",
        cells=["C1-Dense"],
        extra_pythonpath=[poison_dir],
        check=False,
    )
    assert proc.returncode != 0


def test_t2_f05_05_remote_hf_model_id_blocked_even_if_env_unset(tmp_path: Path) -> None:
    require_retrieval_cli()
    docs = [make_b1b_doc("d1", "T", "Nội dung mẫu.")]
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [make_query_row("Q1", "mẫu")])
    proc = run_retrieval_cli(
        corpus_p,
        queries_p,
        tmp_path / "out",
        cells=["C1-Dense"],
        snapshot_dir="org/nonexistent-remote-model",
        env_overrides={"HF_HUB_OFFLINE": None, "TRANSFORMERS_OFFLINE": None},
        check=False,
    )
    assert proc.returncode != 0


# ===========================================================================
# Feature 6 Tier 2: D04.4 Doc Collapse & Hybrid RRF (T2-F06-01 .. T2-F06-06)
# ===========================================================================


def test_t2_f06_01_rrf_candidate_depth_d50_cutoff(tmp_path: Path) -> None:
    require_retrieval_cli()
    docs = [
        make_b1b_doc(
            f"d-{i:02d}",
            f"D{i}",
            f"Chủ đề hoàn toàn khác biệt số {i} không chứa từ khóa truy vấn.",
        )
        for i in range(1, 56)
    ]
    q = make_query_row("Q1", "xyzzynomatchterm", requested_facet_keywords=["xyzzynomatchterm"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-BM25", "C1-Dense", "C1-RRF"], timeout=600)
    all_rows = read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl")
    dense_rows = rows_for_cell_query(all_rows, "C1-Dense", "Q1")
    rrf_rows = rows_for_cell_query(all_rows, "C1-RRF", "Q1")
    doc_50 = dense_rows[49]["document_id"]
    doc_51 = dense_rows[50]["document_id"]
    rrf_by_id = {r["document_id"]: r for r in rrf_rows}
    assert doc_50 in rrf_by_id
    assert rrf_by_id[doc_50]["score"] == pytest.approx(1.0 / (60 + 50), abs=1e-12)
    assert doc_51 not in rrf_by_id


def test_t2_f06_02_bm25_zero_docs_contribute_zero_to_rrf_fx09(tmp_path: Path) -> None:
    require_retrieval_cli()
    docs = [
        make_b1b_doc("d-pos-1", "P1", "Di tích Bạch Đằng lịch sử."),
        make_b1b_doc("d-pos-2", "P2", "Sông Bạch Đằng cổ xưa."),
    ]
    # 138 synthetic docs (2 positive + 136 zero-BM25 negative > RRF candidate_depth=50)
    # while respecting synthetic-prep's exact-137 real-corpus guard.
    for i in range(3, 139):
        docs.append(make_b1b_doc(f"d-z-{i:03d}", f"Z{i}", f"Chủ đề khác biệt số {i} về ẩm thực."))
    q = make_query_row("Q1", "bạch đằng", requested_facet_keywords=["bạch đằng"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-BM25", "C1-Dense", "C1-RRF"], timeout=600)
    all_rows = read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl")
    bm25_ids = {r["document_id"] for r in rows_for_cell_query(all_rows, "C1-BM25", "Q1")}
    assert bm25_ids == {"d-pos-1", "d-pos-2"}
    dense_ranks = {r["document_id"]: r["rank"] for r in rows_for_cell_query(all_rows, "C1-Dense", "Q1")}
    for r in rows_for_cell_query(all_rows, "C1-RRF", "Q1"):
        if r["document_id"] not in bm25_ids:
            rd = dense_ranks[r["document_id"]]
            assert r["score"] == pytest.approx(1.0 / (60 + rd), abs=1e-12)


def test_t2_f06_03_rrf_exact_tie_break_hierarchy(tmp_path: Path) -> None:
    require_retrieval_cli()
    # Engineer two docs where d-dense-win gets Dense#1/BM25#2 and d-bm25-win gets BM25#1/Dense#2
    docs = [
        make_b1b_doc(
            "d-z-bm25-win",
            "B",
            "ZXYW ZXYW ZXYW ZXYW ZXYW ZXYW xe tải cảng biển container.",
        ),
        make_b1b_doc(
            "d-a-dense-win",
            "D",
            "ZXYW bảo tàng lịch sử trưng bày cổ vật Hà Nội.",
        ),
    ]
    q = make_query_row(
        "Q1",
        "ZXYW bảo tàng lịch sử trưng bày cổ vật Hà Nội",
        requested_facet_keywords=["bảo tàng"],
    )
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", docs)
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-BM25", "C1-Dense", "C1-RRF"])
    rrf_rows = rows_for_cell_query(read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl"), "C1-RRF", "Q1")
    sort_keys = [
        (
            -round(r["score"], 12),
            min(v for v in r["leg_ranks"].values() if v is not None),
            r["leg_ranks"].get("Dense", 999999),
            r["document_id"],
        )
        for r in rrf_rows
    ]
    assert sort_keys == sorted(sort_keys)


def test_t2_f06_04_intra_doc_chunk_tie_broken_by_chunk_index_asc(tmp_path: Path) -> None:
    require_retrieval_cli()
    doc = make_multi_level_doc(
        "d-tie",
        "Đền",
        [
            (2, "Phần", "Kiến trúc gỗ lim cổ kính đặc sắc tại Hà Nội."),
            (2, "Phần", "Kiến trúc gỗ lim cổ kính đặc sắc tại Hà Nội."),
        ],
    )
    q = make_query_row("Q1", "Kiến trúc gỗ lim", requested_facet_keywords=["gỗ lim"])
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", [doc])
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-BM25", "C1-Dense"])
    for cell in ("C1-BM25", "C1-Dense"):
        row = rows_for_cell_query(read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl"), cell, "Q1")[0]
        assert row["rep_chunk_index"] == 0


def test_t2_f06_05_rrf_equal_leg_rank_breaks_rep_chunk_tie_to_dense(tmp_path: Path) -> None:
    require_retrieval_cli()
    doc = make_multi_level_doc(
        "d-single",
        "Mẫu",
        [
            (2, "Mục 1", "ZXYW ZXYW ZXYW ZXYW xe buýt sân bay cảng hàng không."),
            (2, "Mục 2", "Nơi lưu giữ di sản văn hóa triều đại phong kiến tại thủ đô Việt Nam."),
        ],
    )
    q = make_query_row(
        "Q1",
        "ZXYW bảo tàng lịch sử cổ vật Hà Nội",
        requested_facet_keywords=["bảo tàng"],
    )
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", [doc])
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out_dir = tmp_path / "out"

    run_retrieval_cli(corpus_p, queries_p, out_dir, cells=["C1-BM25", "C1-Dense", "C1-RRF"])
    r = rows_for_cell_query(read_jsonl(out_dir / "g3_sealed_rankings_v1.jsonl"), "C1-RRF", "Q1")[0]
    assert r["leg_ranks"]["BM25"] == 1 and r["leg_ranks"]["Dense"] == 1
    assert isinstance(r["leg_rep_chunks"]["BM25"], dict)
    assert isinstance(r["leg_rep_chunks"]["Dense"], dict)
    assert (
        r["leg_rep_chunks"]["BM25"]["chunk_id"]
        != r["leg_rep_chunks"]["Dense"]["chunk_id"]
    )
    assert r["rep_chunk_id"] == r["leg_rep_chunks"]["Dense"]["chunk_id"]


def test_t2_f06_06_unknown_cells_value_rejected(tmp_path: Path) -> None:
    require_retrieval_cli()
    corpus_p = write_jsonl(tmp_path / "corpus.jsonl", [make_b1b_doc("d1", "T", "Nội dung mẫu.")])
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [make_query_row("Q1", "mẫu")])
    proc = run_retrieval_cli(
        corpus_p, queries_p, tmp_path / "out", cells=["C2-BM25"], check=False
    )
    assert proc.returncode != 0


# ===========================================================================
# Feature 7 Tier 2: D05.3 Blind Packet Exporter (T2-F07-01 .. T2-F07-05)
# ===========================================================================


def test_t2_f07_01_blind_packet_rank_and_input_order_invariance_fx11(tmp_path: Path) -> None:
    require_retrieval_cli()
    docs = [
        make_b1b_doc(
            f"doc-{i:02d}",
            f"Điểm {i}",
            f"Điểm du lịch {i} với nội dung văn hóa lịch sử đặc sắc thứ {i}.",
        )
        for i in range(1, 21)
    ]
    q = make_query_row("Q01", "du lịch văn hóa lịch sử", requested_facet_keywords=["du lịch"])
    c_fwd = write_jsonl(tmp_path / "c_fwd.jsonl", docs)
    c_rev = write_jsonl(tmp_path / "c_rev.jsonl", list(reversed(docs)))
    q_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out1 = tmp_path / "out1"
    out2 = tmp_path / "out2"

    run_retrieval_cli(
        c_fwd,
        q_p,
        out1,
        cells=["C1-BM25"],
        packet_salt="SALT_2026",
        extra_args=["--pool-depth", "0"],
    )
    run_retrieval_cli(
        c_rev,
        q_p,
        out2,
        cells=["C1-Dense"],
        packet_salt="SALT_2026",
        extra_args=["--pool-depth", "0"],
    )
    assert file_sha256(out1 / "blind_annotation_packet.jsonl") == file_sha256(
        out2 / "blind_annotation_packet.jsonl"
    )


def test_t2_f07_02_different_salts_produce_distinct_uuids_and_order(tmp_path: Path) -> None:
    require_retrieval_cli()
    docs = [make_b1b_doc(f"d-{i:02d}", f"D{i}", f"Nội dung du lịch mẫu {i}.") for i in range(1, 9)]
    q = make_query_row("Q1", "du lịch mẫu", requested_facet_keywords=["du lịch"])
    c_p = write_jsonl(tmp_path / "corpus.jsonl", docs)
    q_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    out1 = tmp_path / "out1"
    out2 = tmp_path / "out2"

    run_retrieval_cli(c_p, q_p, out1, cells=["C1-BM25"], packet_salt="SALT_A")
    run_retrieval_cli(c_p, q_p, out2, cells=["C1-BM25"], packet_salt="SALT_B")
    p1 = read_jsonl(out1 / "blind_annotation_packet.jsonl")
    p2 = read_jsonl(out2 / "blind_annotation_packet.jsonl")
    assert [r["packet_item_uuid"] for r in p1] != [r["packet_item_uuid"] for r in p2]
    assert [r["document_id"] for r in p1] != [r["document_id"] for r in p2]


def test_t2_f07_03_minimum_pool_size_one_doc(tmp_path: Path) -> None:
    require_retrieval_cli()
    c_p = write_jsonl(tmp_path / "corpus.jsonl", [make_b1b_doc("d1", "D1", "Văn bản du lịch duy nhất.")])
    q_p = write_jsonl(tmp_path / "queries.jsonl", [make_query_row("Q1", "du lịch duy nhất")])
    out_dir = tmp_path / "out"

    run_retrieval_cli(c_p, q_p, out_dir, cells=["C1-BM25"], packet_salt="SALT_01")
    pkt = read_jsonl(out_dir / "blind_annotation_packet.jsonl")
    assert len(pkt) == 1
    assert set(pkt[0].keys()) == {
        "packet_item_uuid",
        "query_id",
        "query_text",
        "document_id",
        "source_type",
        "language",
        "canonical_text_S",
    }


def test_t2_f07_04_omitting_packet_salt_skips_packet_generation(tmp_path: Path) -> None:
    require_retrieval_cli()
    c_p = write_jsonl(tmp_path / "corpus.jsonl", [make_b1b_doc("d1", "D1", "Văn bản du lịch.")])
    q_p = write_jsonl(tmp_path / "queries.jsonl", [make_query_row("Q1", "du lịch")])
    out_dir = tmp_path / "out"

    run_retrieval_cli(c_p, q_p, out_dir, cells=["C1-BM25"])
    assert (out_dir / "g3_sealed_rankings_v1.jsonl").is_file()
    assert not (out_dir / "blind_annotation_packet.jsonl").exists()


def test_t2_f07_05_empty_packet_salt_rejected(tmp_path: Path) -> None:
    require_retrieval_cli()
    c_p = write_jsonl(tmp_path / "corpus.jsonl", [make_b1b_doc("d1", "D1", "Văn bản du lịch.")])
    q_p = write_jsonl(tmp_path / "queries.jsonl", [make_query_row("Q1", "du lịch")])
    out_dir = tmp_path / "out"
    proc = run_retrieval_cli(
        c_p, q_p, out_dir, cells=["C1-BM25"], packet_salt="", check=False
    )
    assert proc.returncode != 0 or not (out_dir / "blind_annotation_packet.jsonl").exists()

    probe = """
from w07_retrieval.blind_packet import export_multi_query_blind_packet_jsonl

try:
    export_multi_query_blind_packet_jsonl(
        queries={"Q1": "du lịch"},
        rankings_by_query={"Q1": [{"document_id": "d1"}]},
        corpus_lookup={"d1": {"source_type": "wikipedia_article", "language": "vi", "canonical_text_S": "Văn bản du lịch."}},
        packet_salt="",
    )
except ValueError as exc:
    assert "packet_salt" in str(exc)
    print("EMPTY_SALT_REJECTED")
else:
    raise SystemExit(2)
"""
    p_probe = run_python_probe(probe)
    assert "EMPTY_SALT_REJECTED" in p_probe.stdout


# ===========================================================================
# Feature 8 Tier 2: D01 & AUTO-EVAL Query/Judge Gates (T2-F08-01 .. T2-F08-08)
# ===========================================================================


def test_t2_f08_01_cross_stratum_city_swap_marginal_preserving_rejected(tmp_path: Path) -> None:
    require_scorer_cli()
    queries = make_5x3_query_matrix(split="FINAL", question_origin="INDEPENDENT_HUMAN")
    # Swap one Hà Nội query in S1 with one Đà Nẵng query in S2 -> row & col totals unchanged!
    s1_hn = next(q for q in queries if q["query_family"] == "S1_STRUCTURED_FACT" and q["target_city"] == "Hà Nội")
    s2_dn = next(q for q in queries if q["query_family"] == "S2_NARRATIVE_ADVISORY" and q["target_city"] == "Đà Nẵng")
    s1_hn["target_city"] = "Đà Nẵng"
    s1_hn["target_poi_ids"] = ["syn-poi-dn-01"]
    s2_dn["target_city"] = "Hà Nội"
    s2_dn["target_poi_ids"] = ["syn-poi-hn-01"]

    docs = {"d1": make_b1b_doc("d1", "D1", "Nội dung.")}
    rankings_p, manifest_p = write_synthetic_sealed_rankings(
        tmp_path / "g3", {("C1-BM25", q["query_id"]): [("d1", 1.0)] for q in queries}, docs
    )
    qrels_p = write_jsonl(
        tmp_path / "qrels.jsonl",
        [make_qrel_row(q["query_id"], "d1", "REL_2" if q["pre_rank_answerability"] == "ANSWERABLE" else "REL_0") for q in queries],
    )
    queries_p = write_jsonl(tmp_path / "queries.jsonl", queries)
    proc = run_scorer_cli(
        rankings_p,
        manifest_p,
        qrels_p,
        queries_p,
        tmp_path / "g4.json",
        enforce_final50_matrix=True,
        check=False,
    )
    assert proc.returncode != 0


@pytest.mark.parametrize(
    "field,bad_val",
    [
        ("pre_rank_answerability", "AMBIGUOUS"),
        ("question_origin", "SYNTHETIC_DISCLOSED"),
    ],
)
def test_t2_f08_02_ambiguous_or_synthetic_disclosed_in_final_rejected(
    tmp_path: Path, field: str, bad_val: str
) -> None:
    require_scorer_cli()
    queries = make_5x3_query_matrix(split="FINAL", question_origin="INDEPENDENT_HUMAN")
    queries[0][field] = bad_val
    docs = {"d1": make_b1b_doc("d1", "D1", "Nội dung.")}
    rankings_p, manifest_p = write_synthetic_sealed_rankings(
        tmp_path / "g3", {("C1-BM25", q["query_id"]): [("d1", 1.0)] for q in queries}, docs
    )
    qrels_p = write_jsonl(
        tmp_path / "qrels.jsonl",
        [make_qrel_row(q["query_id"], "d1", "REL_2") for q in queries],
    )
    queries_p = write_jsonl(tmp_path / "queries.jsonl", queries)
    proc = run_scorer_cli(
        rankings_p,
        manifest_p,
        qrels_p,
        queries_p,
        tmp_path / "g4.json",
        enforce_final50_matrix=True,
        check=False,
    )
    assert proc.returncode != 0


@pytest.mark.parametrize(
    "mutator",
    [
        lambda q: q.__setitem__("scope_mode", "UNKNOWN"),
        lambda q: q.pop("query_intent_polarity"),
        lambda q: q.__setitem__("target_poi_ids", [{"id": "poi-1"}]),
    ],
)
def test_t2_f08_03_step_s0_zero_default_and_unhashable_poi_rejected(
    tmp_path: Path, mutator: Any
) -> None:
    require_scorer_cli()
    q = make_query_row("Q1", "mở cửa")
    mutator(q)
    docs = {"d1": make_b1b_doc("d1", "D1", "Nội dung.")}
    rankings_p, manifest_p = write_synthetic_sealed_rankings(
        tmp_path / "g3", {("C1-BM25", "Q1"): [("d1", 1.0)]}, docs
    )
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    qrels_p = write_jsonl(tmp_path / "qrels.jsonl", [make_qrel_row("Q1", "d1", "REL_2")])
    proc = run_scorer_cli(rankings_p, manifest_p, qrels_p, queries_p, tmp_path / "g4.json", check=False)
    assert proc.returncode != 0
    assert "TypeError" not in (proc.stdout + proc.stderr)


def test_t2_f08_04_duplicate_poi_cluster_or_empty_strict_poi_rejected(tmp_path: Path) -> None:
    require_scorer_cli()
    docs = {"d1": make_b1b_doc("d1", "D1", "Nội dung.")}
    # Case A: duplicate (poi_id, fact_cluster_id)
    q1 = make_query_row("Q1", "q1", target_poi_ids=["syn-poi-hn-01"], fact_cluster_id="fc-dup")
    q2 = make_query_row("Q2", "q2", target_poi_ids=["syn-poi-hn-01"], fact_cluster_id="fc-dup")
    r_p, m_p = write_synthetic_sealed_rankings(
        tmp_path / "g3a", {("C1-BM25", "Q1"): [("d1", 1.0)], ("C1-BM25", "Q2"): [("d1", 1.0)]}, docs
    )
    p1 = run_scorer_cli(
        r_p,
        m_p,
        write_jsonl(tmp_path / "qa.jsonl", [make_qrel_row("Q1", "d1", "REL_2"), make_qrel_row("Q2", "d1", "REL_2")]),
        write_jsonl(tmp_path / "qsa.jsonl", [q1, q2]),
        tmp_path / "g4a.json",
        check=False,
    )
    assert p1.returncode != 0

    # Case B: STRICT_TARGET_POI with empty target_poi_ids=[]
    q_empty = make_query_row("Q3", "q3", scope_mode="STRICT_TARGET_POI", target_poi_ids=[])
    r_p2, m_p2 = write_synthetic_sealed_rankings(
        tmp_path / "g3b", {("C1-BM25", "Q3"): [("d1", 1.0)]}, docs
    )
    p2 = run_scorer_cli(
        r_p2,
        m_p2,
        write_jsonl(tmp_path / "qb.jsonl", [make_qrel_row("Q3", "d1", "REL_2")]),
        write_jsonl(tmp_path / "qsb.jsonl", [q_empty]),
        tmp_path / "g4b.json",
        check=False,
    )
    assert p2.returncode != 0


def _assert_judge_error_result(
    res: Dict[str, Any],
    *,
    query_id: str,
    doc_id: str,
    expected_code_prefix: str,
) -> None:
    rep = res["report"]
    if "judge_gates" in rep:
        jg = rep["judge_gates"]
        assert jg["LLMJudged-nDCG@10_judge_A"] is None
        cell_a = jg["judge_A_by_cell"]["C1-BM25"]
        assert cell_a["confirmable"] is False
        assert cell_a["error_rate"] > 0.0
        v_res = cell_a["validated_by_q"][query_id][doc_id]
    else:
        v_res = rep
    assert v_res["state"] == "ERROR"
    assert v_res["confirmed_gain"] == 0
    assert isinstance(v_res["error_code"], str)
    assert v_res["error_code"].startswith(expected_code_prefix), (
        f"Expected error_code starting with {expected_code_prefix!r}, got {v_res['error_code']!r}"
    )


@pytest.mark.parametrize(
    "bad_raw,expected_code_prefix",
    [
        ("[]", "INVALID_TOP_LEVEL_JSON_TYPE:list"),
        (
            make_judge_response_json("REL_2", evidence_quote="x", char_start=True, char_end=1),
            "BOOLEAN_OFFSET_FORBIDDEN",
        ),
        (
            make_judge_response_json(
                "REL_2", evidence_quote="x", char_start=0, char_end=1, extra_fields={"unexpected": 1}
            ),
            "UNEXPECTED_EXTRA_SCHEMA_KEYS",
        ),
    ],
)
def test_t2_f08_05_steps_s1_s4_malformed_or_boolean_offset_error(
    tmp_path: Path, bad_raw: str, expected_code_prefix: str
) -> None:
    require_scorer_cli()
    doc = make_b1b_doc("d1", "D1", "x nội dung.", poi_id="syn-poi-hn-01", city="Hà Nội")
    q = make_query_row("Q1", "q1", target_poi_ids=["syn-poi-hn-01"], target_city="Hà Nội")
    res = _eval_judge_item(tmp_path, doc, q, bad_raw)
    _assert_judge_error_result(
        res, query_id="Q1", doc_id="d1", expected_code_prefix=expected_code_prefix
    )


def test_t2_f08_06_g_span_quote_overlapping_r_audit_or_mismatch_error(tmp_path: Path) -> None:
    require_scorer_cli()
    doc, rem = make_overture_doc(
        "d1",
        "D1",
        [("Thông tin ", "[CORROBORATED: osm:node/1]"), (" mở cửa.", None)],
        confidence=None,
        poi_id="syn-poi-hn-01",
        city="Hà Nội",
    )
    q = make_query_row("Q1", "q1", target_poi_ids=["syn-poi-hn-01"], target_city="Hà Nội")
    raw = make_judge_response_json(
        "REL_2",
        evidence_quote="[CORROBORATED: osm:node/1]",
        char_start=10,
        char_end=36,
    )
    res = _eval_judge_item(tmp_path, doc, q, raw, removed_spans_by_doc={"d1": [list(s) for s in rem]})
    _assert_judge_error_result(
        res, query_id="Q1", doc_id="d1", expected_code_prefix="UNVERIFIED_POSITIVE_QUOTE"
    )


@pytest.mark.parametrize(
    "doc_city,doc_poi,quote,polarity,expected_code_prefix",
    [
        ("Đà Nẵng", "syn-poi-hn-01", "Mở cửa 08:00.", "AFFIRMATIVE_FACT_NEED", "SAFETY_BLOCK_WRONG_CITY_CE9"),
        ("Hà Nội", "syn-poi-other", "Mở cửa 08:00.", "AFFIRMATIVE_FACT_NEED", "SAFETY_BLOCK_NON_TARGET_POI_CE9"),
        ("Hà Nội", "syn-poi-hn-01", "Hiện không có thông tin về giờ.", "AFFIRMATIVE_FACT_NEED", "EPISTEMIC_ABSENCE_NOT_EVIDENCE_CE4"),
        ("Hà Nội", "syn-poi-hn-01", "Hiện đang đóng cửa sửa chữa.", "AFFIRMATIVE_FACT_NEED", "POLARITY_CONTRADICTION_UNRESOLVED_CE4"),
    ],
)
def test_t2_f08_07_ce9_wrong_city_poi_and_ce4_n1_n2_blocked(
    tmp_path: Path, doc_city: str, doc_poi: str, quote: str, polarity: str, expected_code_prefix: str
) -> None:
    require_scorer_cli()
    doc = make_b1b_doc("d1", "D1", quote, poi_id=doc_poi, city=doc_city)
    q = make_query_row(
        "Q1",
        "q1",
        target_poi_ids=["syn-poi-hn-01"],
        target_city="Hà Nội",
        query_intent_polarity=polarity,
    )
    raw = make_judge_response_json("REL_2", evidence_quote=quote, char_start=0, char_end=len(quote))
    res = _eval_judge_item(tmp_path, doc, q, raw)
    _assert_judge_error_result(
        res, query_id="Q1", doc_id="d1", expected_code_prefix=expected_code_prefix
    )


def test_t2_f08_08_order_b_missing_one_expected_judge_pair_halts(tmp_path: Path) -> None:
    require_scorer_cli()
    docs = {
        f"d{i}": make_b1b_doc(f"d{i}", f"D{i}", "Mở cửa 08:00.", poi_id="syn-poi-hn-01", city="Hà Nội")
        for i in range(1, 21)
    }
    q = make_query_row("Q1", "Mở cửa 08:00?", target_poi_ids=["syn-poi-hn-01"], requested_facet_keywords=["08:00"])
    rankings_p, manifest_p = write_synthetic_sealed_rankings(
        tmp_path / "g3", {("C1-BM25", "Q1"): [(f"d{i}", float(30 - i)) for i in range(1, 21)]}, docs
    )
    queries_p = write_jsonl(tmp_path / "queries.jsonl", [q])
    expected_pairs = [("Q1", f"d{i}") for i in range(1, 21)]
    full_rows = [
        make_judge_record("Q1", f"d{i}", "REL_2", evidence_quote="Mở cửa 08:00.", char_start=0, char_end=13)
        for i in range(1, 21)
    ]
    partial_rows = full_rows[:-1]  # omit 1 pair -> 5% missing <= 0.10

    if scorer_supports_flag("--judge-a") and scorer_supports_flag("--expected-pairs"):
        ep_p = tmp_path / "expected_pairs.json"
        ep_p.write_text(json.dumps(expected_pairs), encoding="utf-8")
        docs_p = write_jsonl(tmp_path / "docs.jsonl", list(docs.values()))
        out_p = tmp_path / "g4.json"
        proc = run_scorer_cli(
            rankings_p,
            manifest_p,
            None,
            queries_p,
            out_p,
            judge_a_path=write_jsonl(tmp_path / "ja.jsonl", partial_rows),
            judge_b_path=write_jsonl(tmp_path / "jb.jsonl", full_rows),
            judging_order="ORDER_B",
            expected_pairs_path=ep_p,
            docs_path=docs_p,
            check=False,
        )
        assert is_blocked_or_invalid_status(proc, out_p)
    else:
        probe = f"""
import json
import w07_g4_scorer.judge_gates as jg
docs = {json.dumps({k: {"canonical_text_S": v["canonical_text_S"], "city": v["city"], "poi_id": v["poi_id"]} for k, v in docs.items()}, ensure_ascii=False)}
q = {json.dumps(q, ensure_ascii=False)}
partial = {json.dumps(partial_rows, ensure_ascii=False)}
full = {json.dumps(full_rows, ensure_ascii=False)}
expected = [tuple(x) for x in {json.dumps(expected_pairs)}]
res = jg.score_validated_judge_rankings(
    judging_order="ORDER_B",
    sealed_expected_pairs=expected,
    judge_a_rows=partial,
    judge_b_rows=full,
    docs=docs,
    queries={{"Q1": q}},
)
print(json.dumps(res, ensure_ascii=False))
"""
        proc = run_python_probe(probe, check=False)
        assert proc.returncode == 0, proc.stderr
        rep = json.loads(proc.stdout)
        assert rep["status"] == "INCOMPLETE_SEALED_JUDGE_COVERAGE_HALT"
        assert rep["confirmable"] is False


# ===========================================================================
# Feature 9 Tier 2: D05.1-D05.2 Ontology, Lineage & Cert-1..4 (T2-F09-01..06)
# ===========================================================================


def test_t2_f09_01_shared_lineage_a_rel2_b_unjudged_no_propagation_fx10(tmp_path: Path) -> None:
    require_scorer_cli()
    docs = {
        "sib-a": make_b1b_doc("sib-a", "A", "A", source_lineage_id="wikivoyage:en:Hanoi"),
        "sib-b": make_b1b_doc("sib-b", "B", "B", source_lineage_id="wikivoyage:en:Hanoi"),
    }
    queries = [make_query_row("Q1", "q1")]
    rankings_p, manifest_p = write_synthetic_sealed_rankings(
        tmp_path / "g3", {("C1-BM25", "Q1"): [("sib-a", 2.0), ("sib-b", 1.0)]}, docs
    )
    qrels = [
        make_qrel_row("Q1", "sib-a", "REL_2", source_lineage_id="wikivoyage:en:Hanoi"),
        make_qrel_row("Q1", "sib-b", "UNJUDGED", source_lineage_id="wikivoyage:en:Hanoi"),
    ]
    out_p = tmp_path / "g4.json"
    proc = run_scorer_cli(
        rankings_p,
        manifest_p,
        write_jsonl(tmp_path / "qrels.jsonl", qrels),
        write_jsonl(tmp_path / "queries.jsonl", queries),
        out_p,
        check=False,
    )
    assert is_blocked_or_invalid_status(proc, out_p)


def test_t2_f09_02_shared_lineage_b_na_preserved_never_coerced_to_zero(tmp_path: Path) -> None:
    require_scorer_cli()
    docs = {
        "sib-a": make_b1b_doc("sib-a", "A", "A", source_lineage_id="wikivoyage:en:Hanoi"),
        "sib-b": make_b1b_doc("sib-b", "B", "B", source_lineage_id="wikivoyage:en:Hanoi"),
    }
    queries = [make_query_row("Q1", "q1")]
    rankings_p, manifest_p = write_synthetic_sealed_rankings(
        tmp_path / "g3", {("C1-BM25", "Q1"): [("sib-a", 2.0), ("sib-b", 1.0)]}, docs
    )
    qrels = [
        make_qrel_row("Q1", "sib-a", "REL_2", source_lineage_id="wikivoyage:en:Hanoi"),
        make_qrel_row("Q1", "sib-b", "NA", source_lineage_id="wikivoyage:en:Hanoi"),
    ]
    out_p = tmp_path / "g4.json"
    proc = run_scorer_cli(
        rankings_p,
        manifest_p,
        write_jsonl(tmp_path / "qrels.jsonl", qrels),
        write_jsonl(tmp_path / "queries.jsonl", queries),
        out_p,
        check=False,
    )
    assert is_blocked_or_invalid_status(proc, out_p)


@pytest.mark.parametrize("bad_state", ["NA", "UNJUDGED"])
def test_t2_f09_03_na_or_unjudged_in_top10_fails_cert2(tmp_path: Path, bad_state: str) -> None:
    require_scorer_cli()
    docs = {f"d{i}": make_b1b_doc(f"d{i}", f"D{i}", f"T{i}") for i in range(1, 11)}
    queries = [make_query_row("Q1", "q1")]
    rankings_p, manifest_p = write_synthetic_sealed_rankings(
        tmp_path / "g3", {("C1-BM25", "Q1"): [(f"d{i}", float(20 - i)) for i in range(1, 11)]}, docs
    )
    qrels = [
        make_qrel_row("Q1", f"d{i}", bad_state if i == 10 else ("REL_2" if i == 1 else "REL_0"))
        for i in range(1, 11)
    ]
    out_p = tmp_path / "g4.json"
    proc = run_scorer_cli(
        rankings_p,
        manifest_p,
        write_jsonl(tmp_path / "qrels.jsonl", qrels),
        write_jsonl(tmp_path / "queries.jsonl", queries),
        out_p,
        check=False,
    )
    assert is_blocked_or_invalid_status(proc, out_p)


def test_t2_f09_04_idcg_l_zero_lt_idcg_u_blocked_invalid_unresolved(tmp_path: Path) -> None:
    require_scorer_cli()
    docs = {f"d{i}": make_b1b_doc(f"d{i}", f"D{i}", f"T{i}") for i in range(1, 5)}
    queries = [make_query_row("Q1", "q1")]
    rankings_p, manifest_p = write_synthetic_sealed_rankings(
        tmp_path / "g3", {("C1-BM25", "Q1"): [("d1", 3.0), ("d2", 2.0)]}, docs
    )
    qrels = [
        make_qrel_row("Q1", "d1", "REL_0"),
        make_qrel_row("Q1", "d2", "REL_0"),
        make_qrel_row("Q1", "d3", "REL_0"),
        make_qrel_row("Q1", "d4", "UNJUDGED"),
    ]
    out_p = tmp_path / "g4.json"
    proc = run_scorer_cli(
        rankings_p,
        manifest_p,
        write_jsonl(tmp_path / "qrels.jsonl", qrels),
        write_jsonl(tmp_path / "queries.jsonl", queries),
        out_p,
        check=False,
    )
    assert is_blocked_or_invalid_status(proc, out_p)


def test_t2_f09_05_cert1_lt_1_under_strict_full_pool_fails(tmp_path: Path) -> None:
    require_scorer_cli()
    docs = {"d1": make_b1b_doc("d1", "D1", "T1"), "d2": make_b1b_doc("d2", "D2", "T2")}
    queries = [make_query_row("Q1", "q1")]
    rankings_p, manifest_p = write_synthetic_sealed_rankings(
        tmp_path / "g3", {("C1-BM25", "Q1"): [("d1", 2.0), ("d2", 1.0)]}, docs
    )
    # Omit d2 from qrels completely -> Cert-1 < 1.00
    qrels = [make_qrel_row("Q1", "d1", "REL_2")]
    proc = run_scorer_cli(
        rankings_p,
        manifest_p,
        write_jsonl(tmp_path / "qrels.jsonl", qrels),
        write_jsonl(tmp_path / "queries.jsonl", queries),
        tmp_path / "g4.json",
        strict_full_pool=True,
        check=False,
    )
    assert proc.returncode != 0


def test_t2_f09_06_rank10_unjudged_conservative_enclosure_fx13(tmp_path: Path) -> None:
    require_scorer_cli()
    docs = {f"d{i}": make_b1b_doc(f"d{i}", f"D{i}", f"T{i}") for i in range(1, 11)}
    queries = [make_query_row("Q1", "q1")]
    rankings_p, manifest_p = write_synthetic_sealed_rankings(
        tmp_path / "g3", {("C1-BM25", "Q1"): [(f"d{i}", float(20 - i)) for i in range(1, 11)]}, docs
    )
    qrels = [
        make_qrel_row("Q1", f"d{i}", "REL_2" if i == 1 else ("UNJUDGED" if i == 10 else "REL_0"))
        for i in range(1, 11)
    ]
    out_p = tmp_path / "g4.json"
    proc = run_scorer_cli(
        rankings_p,
        manifest_p,
        write_jsonl(tmp_path / "qrels.jsonl", qrels),
        write_jsonl(tmp_path / "queries.jsonl", queries),
        out_p,
        check=False,
    )
    assert is_blocked_or_invalid_status(proc, out_p)

    probe = """
import json
from w07_g4_scorer.metrics import conservative_ndcg10_enclosure

top10 = [f"d{i}" for i in range(1, 11)]
all_docs = list(top10)
known = {"d1": 3, **{f"d{i}": 0 for i in range(2, 10)}}
res = conservative_ndcg10_enclosure(top10, all_docs, known)
print(json.dumps(res))
"""
    p_enc = run_python_probe(probe)
    enc = json.loads(p_enc.stdout)
    assert float(enc["lower"]) <= 0.790386 + 1e-6
    assert float(enc["upper"]) >= 1.0 - 1e-6


# ===========================================================================
# Feature 10 Tier 2: D06 Decoupled G4 Scorer & Stats (T2-F10-01 .. T2-F10-06)
# ===========================================================================


def test_t2_f10_01_one_byte_sha256_tamper_aborts_immediately_fx15(tmp_path: Path) -> None:
    require_scorer_cli()
    docs = {"d1": make_b1b_doc("d1", "D1", "Văn bản 1.")}
    queries = [make_query_row("Q1", "q1")]
    rankings_p, manifest_p = write_synthetic_sealed_rankings(
        tmp_path / "g3", {("C1-BM25", "Q1"): [("d1", 1.0)]}, docs
    )
    tamper_one_byte(rankings_p)
    out_p = tmp_path / "g4_tampered.json"
    proc = run_scorer_cli(
        rankings_p,
        manifest_p,
        write_jsonl(tmp_path / "qrels.jsonl", [make_qrel_row("Q1", "d1", "REL_2")]),
        write_jsonl(tmp_path / "queries.jsonl", queries),
        out_p,
        check=False,
    )
    assert proc.returncode != 0
    assert not out_p.exists()


def test_t2_f10_02_missing_qrels_refuses_label_self_generation(tmp_path: Path) -> None:
    require_scorer_cli()
    docs = {"d1": make_b1b_doc("d1", "D1", "Văn bản 1.")}
    queries = [make_query_row("Q1", "q1")]
    rankings_p, manifest_p = write_synthetic_sealed_rankings(
        tmp_path / "g3", {("C1-BM25", "Q1"): [("d1", 1.0)]}, docs
    )
    proc = run_scorer_cli(
        rankings_p,
        manifest_p,
        None,
        write_jsonl(tmp_path / "queries.jsonl", queries),
        tmp_path / "g4.json",
        check=False,
    )
    assert proc.returncode != 0


@pytest.mark.parametrize("constant_delta", [0.0, 0.05])
def test_t2_f10_03_constant_bootstrap_difference_vector_fx14bc(
    tmp_path: Path, constant_delta: float
) -> None:
    require_scorer_cli()
    if constant_delta == 0.0:
        docs = {"d1": make_b1b_doc("d1", "D1", "A"), "d2": make_b1b_doc("d2", "D2", "B")}
        queries = [make_query_row(f"Q{i}", f"q{i}") for i in range(1, 11)]
        rank_map: Dict[tuple[str, str], List[tuple[str, float]]] = {}
        qrels: List[Dict[str, Any]] = []
        for q in queries:
            for c in ("C1-RRF", "C1-BM25"):
                rank_map[(c, q["query_id"])] = [("d1", 2.0), ("d2", 1.0)]
            qrels.extend([make_qrel_row(q["query_id"], "d1", "REL_2"), make_qrel_row(q["query_id"], "d2", "REL_0")])
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
        k1 = extract_contrasts_map(rep)["K1"]
        assert k1["ci_method"] == "DEGENERATE_CONSTANT"
        assert float(extract_metric_value(k1, ["p_mc", "p_mc_raw", "p_value"])) == pytest.approx(1.0)
    else:
        probe = """
import json
from dataclasses import asdict
import w07_g4_scorer.stats as st
res = asdict(st.paired_bootstrap_and_sign_flip([0.05] * 10))
print(json.dumps(res, ensure_ascii=False))
"""
        proc = run_python_probe(probe)
        res = json.loads(proc.stdout)
        assert res["ci_method"] == "DEGENERATE_CONSTANT"


def test_t2_f10_04_zero_jackknife_skewness_bca_fallback_fx14d(tmp_path: Path) -> None:
    require_scorer_cli()
    docs = {
        "d1": make_b1b_doc("d1", "D1", "A"),
        "d2": make_b1b_doc("d2", "D2", "B"),
    }
    queries = [make_query_row(f"Q{i}", f"q{i}") for i in range(1, 7)]
    rank_map: Dict[tuple[str, str], List[tuple[str, float]]] = {}
    qrels: List[Dict[str, Any]] = []
    for idx, q in enumerate(queries):
        if idx % 2 == 0:
            rank_map[("C1-RRF", q["query_id"])] = [("d1", 2.0), ("d2", 1.0)]
            rank_map[("C1-BM25", q["query_id"])] = [("d2", 2.0), ("d1", 1.0)]
        else:
            rank_map[("C1-RRF", q["query_id"])] = [("d2", 2.0), ("d1", 1.0)]
            rank_map[("C1-BM25", q["query_id"])] = [("d1", 2.0), ("d2", 1.0)]
        qrels.extend([make_qrel_row(q["query_id"], "d1", "REL_2"), make_qrel_row(q["query_id"], "d2", "REL_0")])

    r_p, m_p = write_synthetic_sealed_rankings(tmp_path / "g3", rank_map, docs)
    out_p = tmp_path / "g4.json"
    run_scorer_cli(
        r_p,
        m_p,
        write_jsonl(tmp_path / "qrels.jsonl", qrels),
        write_jsonl(tmp_path / "queries.jsonl", queries),
        out_p,
    )
    k1 = extract_contrasts_map(read_json(out_p))["K1"]
    ci_95 = extract_metric_value(k1, ["ci_95", "bootstrap_ci_95_percentile"])
    assert ci_95 is not None and all(isinstance(x, (int, float)) for x in ci_95)
    # Also verify boundary p0 in {0, 1} triggers PERCENTILE_FALLBACK_BCA_UNDEFINED cleanly
    probe = """
import json
from dataclasses import asdict
import w07_g4_scorer.stats as st
res = asdict(st.paired_bootstrap_and_sign_flip([1.0, 0.0, 0.0], b_resamples=1))
print(json.dumps(res, ensure_ascii=False))
"""
    proc = run_python_probe(probe)
    assert json.loads(proc.stdout)["ci_method"] == "PERCENTILE_FALLBACK_BCA_UNDEFINED"


def test_t2_f10_05_unanswerable_decoy_regression_blocks_winner_gate(tmp_path: Path) -> None:
    require_scorer_cli()
    docs = {f"d{i}": make_b1b_doc(f"d{i}", f"D{i}", f"T{i}") for i in range(1, 5)}
    ans_qs = [make_query_row(f"QA-{i:02d}", f"ans {i}") for i in range(1, 21)]
    unans_qs = [
        make_query_row(
            f"QU-{i:02d}",
            f"unans {i}",
            query_family="S5_UNANSWERABLE_OR_UNSTABLE",
            pre_rank_answerability="UNANSWERABLE",
        )
        for i in range(1, 5)
    ]
    rank_map: Dict[tuple[str, str], List[tuple[str, float]]] = {}
    qrels: List[Dict[str, Any]] = []
    for q in ans_qs:
        rank_map[("C1-Dense", q["query_id"])] = [("d1", 2.0), ("d2", 1.0)]
        rank_map[("C0-Dense", q["query_id"])] = [("d2", 2.0), ("d1", 1.0)]
        qrels.extend(
            [
                make_qrel_row(q["query_id"], "d1", "REL_2"),
                make_qrel_row(q["query_id"], "d2", "REL_0"),
                make_qrel_row(q["query_id"], "d3", "REL_0"),
                make_qrel_row(q["query_id"], "d4", "REL_0"),
            ]
        )
    for q in unans_qs:
        # C1-Dense puts lure d3 at rank 1; C0-Dense puts non-lure d4 at rank 1
        rank_map[("C1-Dense", q["query_id"])] = [("d3", 2.0)]
        rank_map[("C0-Dense", q["query_id"])] = [("d4", 2.0)]
        qrels.extend(
            [
                make_qrel_row(q["query_id"], "d1", "REL_0", plausible_unsupported_lure=0),
                make_qrel_row(q["query_id"], "d2", "REL_0", plausible_unsupported_lure=0),
                make_qrel_row(q["query_id"], "d3", "REL_0", plausible_unsupported_lure=1),
                make_qrel_row(q["query_id"], "d4", "REL_0", plausible_unsupported_lure=0),
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
    k3 = extract_contrasts_map(read_json(out_p))["K3"]
    assert k3["decision"] == "NO_CLEAR_WINNER"


def test_t2_f10_06_n20_monte_carlo_randomization_regime(tmp_path: Path) -> None:
    require_scorer_cli()
    docs = {"d1": make_b1b_doc("d1", "D1", "A"), "d2": make_b1b_doc("d2", "D2", "B")}
    queries = [make_query_row(f"Q{i:02d}", f"q{i}") for i in range(1, 21)]
    rank_map: Dict[tuple[str, str], List[tuple[str, float]]] = {}
    qrels: List[Dict[str, Any]] = []
    for q in queries:
        rank_map[("C1-RRF", q["query_id"])] = [("d1", 2.0), ("d2", 1.0)]
        rank_map[("C1-BM25", q["query_id"])] = [("d2", 2.0), ("d1", 1.0)]
        qrels.extend([make_qrel_row(q["query_id"], "d1", "REL_2"), make_qrel_row(q["query_id"], "d2", "REL_0")])
    r_p, m_p = write_synthetic_sealed_rankings(tmp_path / "g3", rank_map, docs)
    out_p = tmp_path / "g4.json"
    run_scorer_cli(
        r_p,
        m_p,
        write_jsonl(tmp_path / "qrels.jsonl", qrels),
        write_jsonl(tmp_path / "queries.jsonl", queries),
        out_p,
    )
    k1 = extract_contrasts_map(read_json(out_p))["K1"]
    p_mc = float(extract_metric_value(k1, ["p_mc", "p_mc_raw", "p_value"]))
    assert p_mc >= 1.0 / 10001.0
    assert k1["test_method"] == "MONTE_CARLO_SIGN_FLIP"
    assert not report_contains_token(k1, "exact permutation")


# ===========================================================================
# Feature 11 Tier 2: Gated Real Stubs & Static Hygiene (T2-F11-01 .. T2-F11-05)
# ===========================================================================


def test_t2_f11_01_partial_gate_frozen_only_still_skips() -> None:
    stub = require_real_corpus_stubs()
    proc = run_pytest_subprocess(
        [stub], extra_args=["-rs", "-m", "real_corpus_gated"], env_overrides={"W07_G15_FROZEN": "1"}
    )
    assert proc.returncode == 0
    assert "failed" not in proc.stdout.lower()
    assert "5 skipped" in proc.stdout.lower()


def test_t2_f11_02_reverse_partial_gate_authorized_only_still_skips() -> None:
    stub = require_real_corpus_stubs()
    proc = run_pytest_subprocess(
        [stub], extra_args=["-rs", "-m", "real_corpus_gated"], env_overrides={"W07_OWNER_AUTHORIZED": "1"}
    )
    assert proc.returncode == 0
    assert "failed" not in proc.stdout.lower()
    assert "5 skipped" in proc.stdout.lower()


def test_t2_f11_03_truthy_non_one_strings_do_not_unlock_real_stubs() -> None:
    stub = require_real_corpus_stubs()
    proc = run_pytest_subprocess(
        [stub],
        extra_args=["-rs", "-m", "real_corpus_gated"],
        env_overrides={"W07_G15_FROZEN": "true", "W07_OWNER_AUTHORIZED": "yes"},
    )
    assert proc.returncode == 0
    assert "failed" not in proc.stdout.lower()
    assert "5 skipped" in proc.stdout.lower()


def test_t2_f11_04_static_hygiene_zero_real_corpus_and_whitebox_imports() -> None:
    """Scan tests/e2e/ (and src/ if present) for forbidden corpus paths & imports."""
    import ast

    forbidden_patterns = [
        "FINAL" + "-50",
        "T0_" + "PRIVATE",
        "DEV" + "-5",
        "poi_knowledge_" + "acquired_v1.jsonl",
        "gomate_places_" + "freeze_v2.json",
    ]
    e2e_dir = REPO_ROOT / "tests" / "e2e"
    for py_file in sorted(e2e_dir.glob("*.py")):
        content = py_file.read_text(encoding="utf-8")
        for pat in forbidden_patterns:
            assert pat not in content, f"Forbidden token {pat!r} found in {py_file}"
        tree = ast.parse(content, filename=str(py_file))
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith(("w07_", "tests.fixtures")), (
                        f"Top-level white-box/fixture import in {py_file}: {alias.name}"
                    )
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                assert not node.module.startswith(("w07_", "tests.fixtures")), (
                    f"Top-level white-box/fixture import in {py_file}: {node.module}"
                )

    src_dir = REPO_ROOT / "src"
    if src_dir.is_dir():
        real_corpus_files = forbidden_patterns[1:]  # T0, DEV, real corpus filenames
        for py_file in sorted(src_dir.rglob("*.py")):
            content = py_file.read_text(encoding="utf-8")
            for pat in real_corpus_files:
                assert pat not in content, f"Forbidden token {pat!r} found in {py_file}"


def test_t2_f11_05_wanderai_non_mutation_and_cache_isolation() -> None:
    """Confirm <WANDERAI_REPO_ROOT> git HEAD and working tree remain completely clean."""
    head = subprocess.check_output(
        ["git", "-C", str(WANDERAI_ROOT), "rev-parse", "HEAD"],
        text=True,
        encoding="utf-8",
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
    allowed_untracked = {
        "?? docs/research/W07_B2_G1_5_ANTY_READONLY_SOURCE_HANDOFF_TASK_2026-11-05.md",
        "?? docs/research/W07_B2_G1_5_PREFREEZE_REVIEW_REGISTER_2026-11-05.md",
        "?? docs/research/W07_B2_G1_READONLY_PREFLIGHT_ANTY_TASK_2026-11-04.md",
        "?? docs/research/W07_B2_SCIENTIFIC_PROTOCOL_V1_0_OWNER_APPROVED_2026-11-04.md",
    }
    assert set(status_lines) == allowed_untracked, f"Unexpected wanderai changes: {status_lines}"


# ===========================================================================
# Feature 12 Tier 2: R4 Non-Mutation & R5 Audit Package (T2-F12-01 .. T2-F12-05)
# ===========================================================================


def test_t2_f12_01_verify_non_mutation_detects_tamper_in_temp_copy(tmp_path: Path) -> None:
    verify_script, _ = require_packaging_scripts()
    help_proc = subprocess.run(
        [_python_exe(), "-B", str(verify_script), "--help"],
        cwd=str(REPO_ROOT),
        env=build_safe_offline_env(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    bad_file = tmp_path / "tampered_authority.md"
    bad_file.write_text("tampered content\n", encoding="utf-8")
    help_txt = help_proc.stdout + help_proc.stderr
    if "--critical-path-report" in help_txt or "--authority-dir" in help_txt:
        flag = "--critical-path-report" if "--critical-path-report" in help_txt else "--authority-dir"
        target = bad_file if flag == "--critical-path-report" else tmp_path
        proc = subprocess.run(
            [_python_exe(), "-B", str(verify_script), flag, str(target)],
            cwd=str(REPO_ROOT),
            env=build_safe_offline_env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        assert proc.returncode != 0
    else:
        pytest.fail(
            "scripts/verify_non_mutation.py must expose --critical-path-report or --authority-dir "
            "so authority-tamper detection can be verified on a temp copy"
        )


def test_t2_f12_02_verify_non_mutation_detects_stray_file_in_temp_git_repo(tmp_path: Path) -> None:
    verify_script, _ = require_packaging_scripts()
    fake_repo = tmp_path / "fake_wanderai"
    fake_repo.mkdir()
    subprocess.check_call(["git", "-C", str(fake_repo), "init", "-q"])
    subprocess.check_call(["git", "-C", str(fake_repo), "config", "user.email", "test@example.com"])
    subprocess.check_call(["git", "-C", str(fake_repo), "config", "user.name", "Test"])
    (fake_repo / "README.md").write_text("init\n", encoding="utf-8")
    subprocess.check_call(["git", "-C", str(fake_repo), "add", "README.md"])
    subprocess.check_call(["git", "-C", str(fake_repo), "commit", "-q", "-m", "init"])
    (fake_repo / "stray_untracked.txt").write_text("stray\n", encoding="utf-8")

    help_proc = subprocess.run(
        [_python_exe(), "-B", str(verify_script), "--help"],
        cwd=str(REPO_ROOT),
        env=build_safe_offline_env(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    if "--wanderai-dir" in (help_proc.stdout + help_proc.stderr):
        proc = subprocess.run(
            [_python_exe(), "-B", str(verify_script), "--wanderai-dir", str(fake_repo)],
            cwd=str(REPO_ROOT),
            env=build_safe_offline_env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        assert proc.returncode != 0
    else:
        pytest.fail(
            "scripts/verify_non_mutation.py must expose --wanderai-dir "
            "so stray-file detection can be verified on a temp git repo"
        )


def test_t2_f12_03_build_audit_package_excludes_cache_entries(tmp_path: Path) -> None:
    _, build_script = require_packaging_scripts()
    out_root = _run_build_script(tmp_path, build_script)
    zip_p = out_root / "GOMATE_W07_OFFLINE_RETRIEVAL_PREP_AUDIT_2026-11-20.zip"
    with zipfile.ZipFile(zip_p, "r") as zf:
        for name in zf.namelist():
            assert "__pycache__" not in name
            assert ".pytest_cache" not in name
            assert not name.endswith(".pyc")


def test_t2_f12_04_one_byte_zip_tamper_breaks_receipt_sha256(tmp_path: Path) -> None:
    _, build_script = require_packaging_scripts()
    out_root = _run_build_script(tmp_path, build_script)
    zip_p = out_root / "GOMATE_W07_OFFLINE_RETRIEVAL_PREP_AUDIT_2026-11-20.zip"
    rec_p = out_root / "W07_OFFLINE_RETRIEVAL_PREP_SHA256_RECEIPT.json"
    receipt = read_json(rec_p)
    digest = extract_metric_value(receipt, ["deliverable_zip_sha256", "zip_sha256", "sha256"])
    copy_zip = tamper_one_byte(zip_p, dest_path=tmp_path / "tampered.zip")
    assert file_sha256(copy_zip) != digest


def test_t2_f12_05_pythonhashseed_invariance_during_zip_packaging(tmp_path: Path) -> None:
    _, build_script = require_packaging_scripts()
    d1 = _run_build_script(tmp_path / "h1", build_script, env_overrides={"PYTHONHASHSEED": "1"})
    d2 = _run_build_script(tmp_path / "h42", build_script, env_overrides={"PYTHONHASHSEED": "42"})
    z1 = d1 / "GOMATE_W07_OFFLINE_RETRIEVAL_PREP_AUDIT_2026-11-20.zip"
    z2 = d2 / "GOMATE_W07_OFFLINE_RETRIEVAL_PREP_AUDIT_2026-11-20.zip"
    assert file_sha256(z1) == file_sha256(z2)
