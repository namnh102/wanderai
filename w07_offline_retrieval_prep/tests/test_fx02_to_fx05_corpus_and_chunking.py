"""Synthetic unit tests for FX-02..FX-05 (conservation, R_AUDIT, C1 ceiling, C_vis)."""

from __future__ import annotations

from pathlib import Path

import pytest

from fixtures.retrieval_fixtures import (
    BOILERPLATE_FOOTER_ALLOWLIST,
    FX03_MALFORMED_INPUTS,
    FX03_VALID_SIX_FAMILY_DOC,
    build_fx02_conservation_doc,
    build_fx02_osm_payload,
    build_fx04_corpus,
    build_fx05_synthetic_overture_doc,
)
from w07_retrieval.chunker_c0 import C0Chunker
from w07_retrieval.chunker_c1 import C1Chunker, chunk_corpus_c1
from w07_retrieval.sanitizer import (
    KNOWN_FAMILIES,
    cp_to_utf8_byte_offsets,
    intervals_contain,
    project_v_span_to_s,
    sanitize_canonical_to_view,
    subtract_intervals,
)
from w07_retrieval.schema import load_canonical_document
from w07_retrieval.visibility import (
    compute_provenance_visible_s_spans,
    get_token_offset_spans,
    load_minilm_tokenizer,
)


def test_fx02_canonical_conservation_and_parent_breadcrumbs(snapshot_dir: Path) -> None:
    tok = load_minilm_tokenizer(snapshot_dir)
    doc = build_fx02_conservation_doc()
    san = sanitize_canonical_to_view(doc.canonical_text_S)
    res = C1Chunker().chunk_document_detailed(doc, san, tok)

    # Exact code-point partition: len(S) == body_cp + heading_header_cp + omitted_ws_cp
    assert res.total_s_cp == len(doc.canonical_text_S)
    assert res.body_cp + res.heading_header_cp + res.omitted_ws_cp == res.total_s_cp
    assert res.coverage_lost_due_to_chunking == 0

    # Parent breadcrumb propagation ("Kiến trúc > Mặt tiền") and parent_heading_span recorded
    child_chunks = [c for c in res.chunks if c.section_heading == "Mặt tiền"]
    assert len(child_chunks) == 1
    child = child_chunks[0]
    assert child.section_breadcrumb == "Kiến trúc > Mặt tiền"
    assert f"{doc.title} | Kiến trúc > Mặt tiền\n" in child.assembled_text
    assert len(child.heading_spans) == 2
    s_text = doc.canonical_text_S
    assert s_text[child.heading_spans[0][0] : child.heading_spans[0][1]] == "Kiến trúc"
    assert s_text[child.heading_spans[1][0] : child.heading_spans[1][1]] == "Mặt tiền"

    # Allowlisted empty footers omitted and logged; non-allowlisted empty section NOT omitted as boilerplate
    omitted_names = {entry["heading"] for entry in res.omitted_boilerplate_headings}
    assert omitted_names == {"Xem thêm", "Tham khảo", "See also", "References"}
    assert omitted_names.issubset(set(BOILERPLATE_FOOTER_ALLOWLIST))

    non_allowlisted = [c for c in res.chunks if c.section_heading == "Kiến trúc đặc biệt"]
    assert len(non_allowlisted) == 1
    assert non_allowlisted[0].body_v_span is None
    assert non_allowlisted[0].metadata["heading_only"] is True

    # UTF-8 byte bijection round-trip on all canonical spans
    bmap = cp_to_utf8_byte_offsets(s_text)
    s_utf8 = s_text.encode("utf-8")
    for ch in res.chunks:
        for a, b in ch.c_full_s_spans:
            assert s_utf8[bmap[a] : bmap[b]].decode("utf-8") == s_text[a:b]

    # OSM line-1 header assembly & schema loader check
    osm_doc = load_canonical_document(build_fx02_osm_payload())
    osm_san = sanitize_canonical_to_view(osm_doc.canonical_text_S)
    osm_res = C1Chunker().chunk_document_detailed(osm_doc, osm_san, tok)
    assert osm_res.body_cp + osm_res.heading_header_cp + osm_res.omitted_ws_cp == osm_res.total_s_cp
    first_line = osm_doc.canonical_text_S.splitlines()[0]
    assert osm_res.chunks[0].assembled_text.startswith(first_line + "\n")
    assert osm_res.chunks[0].heading_spans == [[0, len(first_line)]]


def test_fx03_six_family_raudit_adjacent_and_qualifiers() -> None:
    s_orig = str(FX03_VALID_SIX_FAMILY_DOC)
    res = sanitize_canonical_to_view(s_orig)

    # S immutable, 0 [CORROBORATED remaining, exact conservation
    assert res.canonical_S == s_orig
    assert "[CORROBORATED" not in res.view_V
    assert len(res.view_V) + sum(b - a for a, b in res.removed_intervals) == len(s_orig)
    assert set(res.families) == KNOWN_FAMILIES

    # Zero surrounding whitespace consumed around adjacent tags
    assert len(res.removed_intervals) == 3
    assert res.removed_intervals[1][1] == res.removed_intervals[2][0]
    assert "Địa điểm  lưu giữ" in res.view_V

    # Non-audit prose/confidence/brackets/qualifiers preserved verbatim
    assert "Độ tin cậy bản ghi Overture (confidence): 0.8542." in res.view_V
    for marker in (
        "[1]",
        "[4]",
        "[Gia Long]",
        "[UNVERIFIED: chưa xác minh thực địa]",
        "[CONFLICT: FC-001 ẩn khỏi câu trả lời]",
        "FC-002",
    ):
        assert res.view_V.count(marker) == s_orig.count(marker)


def test_fx03_pi_v_to_s_utf8_and_cp_roundtrip_rejects_outer_hull() -> None:
    s_orig = FX03_VALID_SIX_FAMILY_DOC
    res = sanitize_canonical_to_view(s_orig)
    bmap = cp_to_utf8_byte_offsets(s_orig)
    s_utf8 = s_orig.encode("utf-8")

    # Compute cut points in V corresponding to each removed tag
    v_cuts: list[int] = []
    acc = 0
    for ra, rb in res.removed_intervals:
        v_cuts.append(ra - acc)
        acc += rb - ra

    for v_cut in v_cuts:
        va = max(0, v_cut - 10)
        vb = min(len(res.view_V), v_cut + 10)
        iv = project_v_span_to_s(va, vb, res.segments)
        assert len(iv) >= 2
        # Outer hull must expose the deleted tag (rejected as single span)
        hull_text = s_orig[iv[0][0] : iv[-1][1]]
        assert "[CORROBORATED:" in hull_text
        # Exact code-point and UTF-8 byte round-trip
        assert "".join(s_orig[a:b] for a, b in iv) == res.view_V[va:vb]
        assert (
            b"".join(s_utf8[bmap[a] : bmap[b]] for a, b in iv).decode("utf-8")
            == res.view_V[va:vb]
        )
        # Disjoint from removed_intervals
        for a, b in iv:
            for ra, rb in res.removed_intervals:
                assert max(a, ra) >= min(b, rb)

    # Full-view straddle across all 3 removed tags (including adjacent tags)
    iv_all = project_v_span_to_s(0, len(res.view_V), res.segments)
    assert len(iv_all) == 3  # 1st tag + adjacent pair (coalesced cut) -> 3 preserved spans
    assert "".join(s_orig[a:b] for a, b in iv_all) == res.view_V
    assert (
        b"".join(s_utf8[bmap[a] : bmap[b]] for a, b in iv_all).decode("utf-8")
        == res.view_V
    )


@pytest.mark.parametrize("bad_input", FX03_MALFORMED_INPUTS)
def test_fx03_malformed_tags_fail_closed(bad_input: str) -> None:
    with pytest.raises(ValueError):
        sanitize_canonical_to_view(bad_input)


def test_fx04_c1_token_ceiling_and_zero_coverage_loss(snapshot_dir: Path) -> None:
    tok = load_minilm_tokenizer(snapshot_dir)
    corpus = build_fx04_corpus()
    san_by_doc = {
        d.document_id: sanitize_canonical_to_view(d.canonical_text_S) for d in corpus
    }
    chunks, audit = chunk_corpus_c1(corpus, san_by_doc, tok)

    assert len(chunks) > 5
    assert audit["coverage_lost_due_to_chunking"] == 0

    for ch in chunks:
        untrunc_offsets = get_token_offset_spans(ch.assembled_text, tok, max_tokens=None)
        assert len(untrunc_offsets) == ch.token_count_with_special
        assert len(untrunc_offsets) <= 128

    # <10-word body in syn-fx04-short must NOT be dropped
    short_chunks = [c for c in chunks if c.document_id == "syn-fx04-short"]
    assert len(short_chunks) == 1
    assert "Mở cửa miễn phí hàng ngày." in short_chunks[0].assembled_text
    assert short_chunks[0].word_count < 10

    # Unpunctuated long run + 260-char unbroken string must be cleanly split <= 128 tokens
    unpunct_chunks = [c for c in chunks if c.document_id == "syn-fx04-unpunct"]
    assert len(unpunct_chunks) >= 3
    assert all(c.token_count_with_special <= 128 for c in unpunct_chunks)
    assert unpunct_chunks[0].section_heading == "Long Clause"
    assert unpunct_chunks[0].heading_spans == [[3, 14]]

    # Markdown ## heading in syn-fx04-en must extract canonical heading & span
    en_chunks = [c for c in chunks if c.document_id == "syn-fx04-en"]
    assert len(en_chunks) >= 2
    assert en_chunks[0].section_heading == "Travel Guide"
    assert en_chunks[0].section_breadcrumb == "Travel Guide"
    assert en_chunks[0].heading_spans == [[3, 15]]
    assert "Travel Guide" not in en_chunks[0].assembled_text.split("\n", 1)[1]


def test_fx05_c0_truncation_synthetic_header_and_multi_span_vis(
    snapshot_dir: Path,
) -> None:
    tok = load_minilm_tokenizer(snapshot_dir)
    doc = build_fx05_synthetic_overture_doc()
    s_text = doc.canonical_text_S
    san = sanitize_canonical_to_view(s_text)
    assert len(san.removed_intervals) == 1

    c0_chunks = C0Chunker().chunk_document(doc, san, tok, max_vis_tokens=128)
    assert len(c0_chunks) == 1
    ch = c0_chunks[0]
    assert ch.token_count_with_special > 160

    c_full = [tuple(x) for x in ch.c_full_s_spans]
    c_vis_dense = [tuple(x) for x in ch.c_vis_s_spans_dense]
    c_vis_bm25 = [tuple(x) for x in ch.c_vis_s_spans_bm25]

    # (a) Tail fact echoed in SYNTHETIC_HEADER -> visible in C_full & BM25, blocked in Dense C_vis
    tail_phrase = "ARCHIVE-TAIL-9981"
    assert tail_phrase in ch.assembled_text.splitlines()[0]  # echoed in SYNTHETIC_HEADER
    g_tail_s = s_text.rindex(tail_phrase)
    g_tail = [(g_tail_s, g_tail_s + len(tail_phrase))]
    assert intervals_contain(c_full, g_tail) is True
    assert intervals_contain(c_vis_bm25, g_tail) is True
    assert intervals_contain(c_vis_dense, g_tail) is False

    # (a2) Canonical heading in CANONICAL_HEADING_S within tokens 1..128 -> visible in Dense C_vis
    heading_phrase = "Bảo tàng Dân tộc học Việt Nam"
    h_s = s_text.index(heading_phrase)
    g_heading = [(h_s, h_s + len(heading_phrase))]
    assert intervals_contain(c_vis_dense, g_heading) is True

    # (a3) Span straddling MiniLM token 128/129 cutoff -> in C_full, NOT fully visible in Dense C_vis
    trunc_offsets = get_token_offset_spans(ch.assembled_text, tok, max_tokens=128)
    untrunc_offsets = get_token_offset_spans(ch.assembled_text, tok, max_tokens=None)
    assert len(trunc_offsets) == 128
    assert trunc_offsets[-1] == (0, 0)  # </s> at index 127
    # Token index 126 is last visible token; token index 127 in untruncated is first truncated token
    last_vis_a, _ = trunc_offsets[126]
    first_cut_a, first_cut_b = untrunc_offsets[127]
    body_seg = next(s for s in ch.assembled_segments if s["kind"] == "CANONICAL_BODY_V")
    v_cross_s = body_seg["v_start"] + (last_vis_a - body_seg["a_start"])
    v_cross_e = body_seg["v_start"] + (first_cut_b - body_seg["a_start"])
    assert first_cut_a < first_cut_b
    g_cross = project_v_span_to_s(v_cross_s, v_cross_e, san.segments)
    assert intervals_contain(c_full, g_cross) is True
    assert intervals_contain(c_vis_dense, g_cross) is False

    # (b) Early canonical span straddling deleted 4-family R_AUDIT tag -> G_sub <= C_vis(c)
    straddle_s = s_text.index("(arts_and_entertainment > museum)")
    straddle_e = s_text.index("0.7405.") + len("0.7405.")
    g_sub = subtract_intervals([(straddle_s, straddle_e)], san.removed_intervals)
    assert len(g_sub) == 2
    assert intervals_contain(c_vis_dense, g_sub) is True
    for a, b in c_vis_dense:
        for ra, rb in san.removed_intervals:
            assert max(a, ra) >= min(b, rb)


def test_c1_markdown_crlf_empty_headings_and_sibling_breadcrumbs(
    snapshot_dir: Path,
) -> None:
    tok = load_minilm_tokenizer(snapshot_dir)
    c1 = C1Chunker()

    def _make_doc(doc_id: str, text_s: str):
        return load_canonical_document(
            {
                "document_id": doc_id,
                "source_type": "wikipedia_vi",
                "title": "Test POI",
                "language": "vi",
                "canonical_text_S": text_s,
            }
        )

    # 1. Markdown empty parent -> child breadcrumb
    md_text = "## See\n\n### Caves\nThien Cung Cave is famous.\n"
    md_doc = _make_doc("reg-md-parent", md_text)
    md_res = c1.chunk_document_detailed(md_doc, sanitize_canonical_to_view(md_text), tok)
    assert len(md_res.chunks) == 1
    assert md_res.chunks[0].section_heading == "Caves"
    assert md_res.chunks[0].section_breadcrumb == "See > Caves"
    assert md_res.chunks[0].heading_spans == [[3, 6], [12, 17]]
    assert md_res.coverage_lost_due_to_chunking == 0

    # 2. CRLF headings must parse cleanly without leaking \r into body
    crlf_text = "== H1 ==\r\nBody line one.\r\n=== H2 ===\r\nBody line two.\r\n"
    crlf_doc = _make_doc("reg-crlf", crlf_text)
    crlf_res = c1.chunk_document_detailed(
        crlf_doc, sanitize_canonical_to_view(crlf_text), tok
    )
    assert [(c.section_heading, c.section_breadcrumb) for c in crlf_res.chunks] == [
        ("H1", "H1"),
        ("H2", "H2"),
    ]
    assert crlf_res.coverage_lost_due_to_chunking == 0
    assert crlf_res.body_cp + crlf_res.heading_header_cp + crlf_res.omitted_ws_cp == crlf_res.total_v_cp
    assert not crlf_res.chunks[0].assembled_text.split("\n", 1)[1].startswith("\r")

    # 3. Empty ==\nText == and ##\nBody must NOT span newlines or swallow next line
    nl_eq_text = "==\nText ==\nBody paragraph."
    nl_eq_doc = _make_doc("reg-nl-eq", nl_eq_text)
    nl_eq_res = c1.chunk_document_detailed(
        nl_eq_doc, sanitize_canonical_to_view(nl_eq_text), tok
    )
    assert len(nl_eq_res.chunks) == 1
    assert nl_eq_res.chunks[0].section_heading == "Introduction"
    assert nl_eq_res.chunks[0].heading_spans == []
    assert nl_eq_res.coverage_lost_due_to_chunking == 0

    nl_md_text = "##\nBody paragraph."
    nl_md_doc = _make_doc("reg-nl-md", nl_md_text)
    nl_md_res = c1.chunk_document_detailed(
        nl_md_doc, sanitize_canonical_to_view(nl_md_text), tok
    )
    assert len(nl_md_res.chunks) == 1
    assert nl_md_res.chunks[0].section_heading == "Section"
    assert nl_md_res.chunks[0].heading_spans == []
    assert "Body paragraph." in nl_md_res.chunks[0].assembled_text
    assert nl_md_res.coverage_lost_due_to_chunking == 0

    # 4. Multi-sibling children under empty parent inherit parent breadcrumb until equal/higher heading
    sib_text = (
        "== Kiến trúc ==\n"
        "=== Mặt tiền ===\nMặt tiền rộng lớn.\n"
        "=== Hậu cung ===\nHậu cung trang nghiêm.\n"
        "== Lịch sử ==\nNăm 1070.\n"
    )
    sib_doc = _make_doc("reg-siblings", sib_text)
    sib_res = c1.chunk_document_detailed(sib_doc, sanitize_canonical_to_view(sib_text), tok)
    assert [(c.section_heading, c.section_breadcrumb) for c in sib_res.chunks] == [
        ("Mặt tiền", "Kiến trúc > Mặt tiền"),
        ("Hậu cung", "Kiến trúc > Hậu cung"),
        ("Lịch sử", "Lịch sử"),
    ]
    assert sib_text[sib_res.chunks[1].heading_spans[0][0] : sib_res.chunks[1].heading_spans[0][1]] == "Kiến trúc"
    assert sib_text[sib_res.chunks[1].heading_spans[1][0] : sib_res.chunks[1].heading_spans[1][1]] == "Hậu cung"

    # 5. Non-allowlisted empty parent before allowlisted footer is NEVER silently dropped
    footer_only_text = "== Kiến trúc ==\n=== Xem thêm ===\n"
    footer_only_doc = _make_doc("reg-parent-footer-eof", footer_only_text)
    footer_only_res = c1.chunk_document_detailed(
        footer_only_doc, sanitize_canonical_to_view(footer_only_text), tok
    )
    assert len(footer_only_res.chunks) == 1
    assert footer_only_res.chunks[0].section_heading == "Kiến trúc"
    assert footer_only_res.chunks[0].metadata["heading_only"] is True
    assert [e["heading"] for e in footer_only_res.omitted_boilerplate_headings] == ["Xem thêm"]

    footer_mid_text = "== Kiến trúc ==\n=== Xem thêm ===\n== Lịch sử ==\nNăm 1070.\n"
    footer_mid_doc = _make_doc("reg-parent-footer-mid", footer_mid_text)
    footer_mid_res = c1.chunk_document_detailed(
        footer_mid_doc, sanitize_canonical_to_view(footer_mid_text), tok
    )
    assert [(c.section_heading, c.metadata["heading_only"]) for c in footer_mid_res.chunks] == [
        ("Kiến trúc", True),
        ("Lịch sử", False),
    ]
    assert [e["heading"] for e in footer_mid_res.omitted_boilerplate_headings] == ["Xem thêm"]


@pytest.mark.parametrize(
    ("case_id", "body_text"),
    [
        ("colon_prefix", ": " + " ".join(f"word{i}" for i in range(150)) + "."),
        ("leading_semicolon", "Mr. ; " + " ".join(f"word{i}" for i in range(150)) + "."),
        ("double_comma", "Thông tin địa điểm, , " + " ".join(f"word{i}" for i in range(150)) + "."),
        ("all_punct_long", ";:, " * 100),
    ],
)
def test_c1_over_budget_leading_and_isolated_punctuation(
    snapshot_dir: Path, case_id: str, body_text: str
) -> None:
    tok = load_minilm_tokenizer(snapshot_dir)
    text_s = f"== Sec ==\n{body_text}"
    doc = load_canonical_document(
        {
            "document_id": f"reg-punct-{case_id}",
            "source_type": "wikipedia_vi",
            "title": "Test POI",
            "language": "vi",
            "canonical_text_S": text_s,
        }
    )
    res = C1Chunker().chunk_document_detailed(
        doc, sanitize_canonical_to_view(text_s), tok
    )
    assert res.coverage_lost_due_to_chunking == 0
    assert res.body_cp + res.heading_header_cp + res.omitted_ws_cp == res.total_v_cp
    assert len(res.chunks) >= 2
    assert all(c.token_count_with_special <= 128 for c in res.chunks)


def test_schema_load_canonical_document_place_without_source_type() -> None:
    record = {
        "document_id": "osm-place-no-st",
        "place": {
            "id": "p-1",
            "name": "Chùa Một Cột",
            "sources": [
                {
                    "source_name": "osm",
                    "source_id": "node/123",
                    "raw_data": {"tags": {"tourism": "attraction"}},
                }
            ],
        },
    }
    doc = load_canonical_document(record)
    assert doc.document_id == "osm-place-no-st"
    assert doc.source_type == "osm_useful_structured"
    assert doc.text_field_used == "osm_built_from_place"
    assert "Chùa Một Cột" in doc.canonical_text_S
    assert "OpenStreetMap node/123" in doc.canonical_text_S


def test_visibility_untruncated_vs_truncated_parity(snapshot_dir: Path) -> None:
    tok = load_minilm_tokenizer(snapshot_dir)
    doc = build_fx05_synthetic_overture_doc()
    san = sanitize_canonical_to_view(doc.canonical_text_S)
    ch = C0Chunker().chunk_document(doc, san, tok, max_vis_tokens=128)[0]

    trunc_offsets = get_token_offset_spans(ch.assembled_text, tok, max_tokens=128)
    untrunc_offsets = get_token_offset_spans(ch.assembled_text, tok, max_tokens=None)
    assert len(untrunc_offsets) > 128

    vis_from_trunc = compute_provenance_visible_s_spans(
        ch.assembled_text, ch.assembled_segments, trunc_offsets, 128, san.segments
    )
    vis_from_untrunc = compute_provenance_visible_s_spans(
        ch.assembled_text, ch.assembled_segments, untrunc_offsets, 128, san.segments
    )
    assert vis_from_untrunc == vis_from_trunc


def test_c1_allowlisted_empty_parent_hierarchy_wins_over_footer_leaf_omission(
    snapshot_dir: Path,
) -> None:
    """STUB-02 narrow C1 corrective: hierarchy precedes leaf footer allowlist; 21+24+14=59 partition."""
    tok = load_minilm_tokenizer(snapshot_dir)
    c1 = C1Chunker()

    def _make_doc(doc_id: str, text_s: str, title: str = "Hoàng thành mẫu"):
        return load_canonical_document(
            {
                "document_id": doc_id,
                "source_type": "wikipedia_article",
                "title": title,
                "language": "vi",
                "canonical_text_S": text_s,
            }
        )

    # 1. Allowlisted empty parent before deeper children (`== Tham khảo ==` -> `=== Ghi chú ===` -> `=== Đọc thêm ===`)
    # plus a standalone allowlisted footer leaf (`== Liên kết ngoài ==`) and populated sibling section.
    hier_text = (
        "== Kiến trúc ==\n"
        "Cổng thành được xây dựng bằng đá xanh truyền thống.\n"
        "== Tham khảo ==\n"
        "=== Ghi chú ===\n"
        "=== Đọc thêm ===\n"
        "Tài liệu khảo cổ ghi nhận nền móng có niên đại thế kỷ XI tại khu vực trung tâm.\n"
        "== Liên kết ngoài ==\n"
    )
    hier_doc = _make_doc("syn-tham-khao-parent", hier_text)
    hier_res = c1.chunk_document_detailed(
        hier_doc, sanitize_canonical_to_view(hier_text), tok
    )

    assert hier_res.coverage_lost_due_to_chunking == 0
    assert (
        hier_res.body_cp + hier_res.heading_header_cp + hier_res.omitted_ws_cp
        == hier_res.total_v_cp
        == hier_res.total_s_cp
    )
    for ch in hier_res.chunks:
        untrunc = get_token_offset_spans(ch.assembled_text, tok, max_tokens=None)
        assert len(untrunc) == ch.token_count_with_special <= 128

    # Standalone allowlisted leaf omitted; parent allowlisted `Tham khảo` NOT omitted
    omitted_names = [e["heading"] for e in hier_res.omitted_boilerplate_headings]
    assert omitted_names == ["Liên kết ngoài"]

    # Propagated parent recorded for `Tham khảo -> Đọc thêm`
    assert hier_res.empty_parent_headings_propagated == [
        {
            "document_id": "syn-tham-khao-parent",
            "parents": ["Tham khảo"],
            "child": "Đọc thêm",
        }
    ]

    # Empty child leaf `=== Ghi chú ===` inherits `Tham khảo > Ghi chú` with exact source spans
    ghi_chu_chunks = [c for c in hier_res.chunks if c.section_heading == "Ghi chú"]
    assert len(ghi_chu_chunks) == 1
    gc = ghi_chu_chunks[0]
    assert gc.metadata["heading_only"] is True
    assert gc.section_breadcrumb == "Tham khảo > Ghi chú"
    assert [hier_text[a:b] for a, b in gc.heading_spans] == ["Tham khảo", "Ghi chú"]

    # Populated child `=== Đọc thêm ===` retains `Tham khảo > Đọc thêm`, exact source spans,
    # zero factual leakage from sibling sections, and empty mapping on SYNTHETIC_HEADER
    doc_them_chunks = [c for c in hier_res.chunks if c.section_heading == "Đọc thêm"]
    assert len(doc_them_chunks) == 1
    dt = doc_them_chunks[0]
    assert dt.metadata["heading_only"] is False
    assert dt.section_breadcrumb == "Tham khảo > Đọc thêm"
    assert [hier_text[a:b] for a, b in dt.heading_spans] == ["Tham khảo", "Đọc thêm"]
    assert dt.assembled_text.startswith("Hoàng thành mẫu | Tham khảo > Đọc thêm\n")
    synth_segs = [s for s in dt.assembled_segments if s["kind"] == "SYNTHETIC_HEADER"]
    assert synth_segs and compute_provenance_visible_s_spans(
        dt.assembled_text, synth_segs, [(s["a_start"], s["a_end"]) for s in synth_segs], 128, sanitize_canonical_to_view(hier_text).segments
    ) == []
    sibling_fact = "Cổng thành được xây dựng bằng đá xanh truyền thống."
    sib_s = hier_text.index(sibling_fact)
    assert intervals_contain(dt.c_full_s_spans, [(sib_s, sib_s + len(sibling_fact))]) is False
    assert dt.c_vis_s_spans_dense == dt.c_full_s_spans  # <= 128 tokens -> 100% visible

    # 2. Standalone empty allowlisted leaf & all-allowlisted empty subtree edge cases + non-allowlisted leaf
    leaf_tk_doc = _make_doc("syn-leaf-tk", "== Tham khảo ==\n")
    leaf_tk_res = c1.chunk_document_detailed(
        leaf_tk_doc, sanitize_canonical_to_view(leaf_tk_doc.canonical_text_S), tok
    )
    assert leaf_tk_res.chunks == []
    assert [e["heading"] for e in leaf_tk_res.omitted_boilerplate_headings] == ["Tham khảo"]
    assert leaf_tk_res.omitted_ws_cp + leaf_tk_res.heading_header_cp == leaf_tk_res.total_s_cp

    all_allow_sub = _make_doc("syn-allow-sub", "== Tham khảo ==\n=== Xem thêm ===\n")
    all_allow_res = c1.chunk_document_detailed(
        all_allow_sub, sanitize_canonical_to_view(all_allow_sub.canonical_text_S), tok
    )
    assert all_allow_res.chunks == []
    assert [e["heading"] for e in all_allow_res.omitted_boilerplate_headings] == [
        "Xem thêm",
        "Tham khảo",
    ]
    assert all_allow_res.coverage_lost_due_to_chunking == 0

    mixed_anc = _make_doc(
        "syn-mixed-anc", "== Kiến trúc ==\n=== Tham khảo ===\n==== Xem thêm ====\n"
    )
    mixed_res = c1.chunk_document_detailed(
        mixed_anc, sanitize_canonical_to_view(mixed_anc.canonical_text_S), tok
    )
    assert len(mixed_res.chunks) == 1
    assert mixed_res.chunks[0].section_heading == "Kiến trúc"
    assert mixed_res.chunks[0].metadata["heading_only"] is True
    assert {e["heading"] for e in mixed_res.omitted_boilerplate_headings} == {
        "Xem thêm",
        "Tham khảo",
    }

    non_allow_leaf = _make_doc("syn-non-allow-leaf", "== Bảo tồn ==\n")
    non_allow_res = c1.chunk_document_detailed(
        non_allow_leaf, sanitize_canonical_to_view(non_allow_leaf.canonical_text_S), tok
    )
    assert len(non_allow_res.chunks) == 1
    assert non_allow_res.chunks[0].section_heading == "Bảo tồn"
    assert non_allow_res.chunks[0].metadata["heading_only"] is True
    assert non_allow_res.omitted_boilerplate_headings == []

    # 3. Synthetic 59-empty-heading partition verification (21 parents + 24 omitted + 14 heading-only = 59)
    allowlisted_sorted = sorted(BOILERPLATE_FOOTER_ALLOWLIST)
    part_sections: list[str] = []
    for i in range(20):
        part_sections.append(
            f"== Nhóm cha {i:02d} ==\n=== Nhánh con {i:02d} ===\nNội dung lịch sử đoạn {i:02d}.\n"
        )
    part_sections.append(
        "== Tham khảo ==\n=== Ghi chú ===\n=== Đọc thêm ===\nTư liệu bổ sung đã xác minh.\n"
    )
    for j in range(24):
        part_sections.append(f"== {allowlisted_sorted[j % len(allowlisted_sorted)]} ==\n")
    for k in range(13):
        part_sections.append(f"== Mục trống {k:02d} ==\n")

    mirror_doc = _make_doc("syn-59-partition", "".join(part_sections))
    mirror_san = {"syn-59-partition": sanitize_canonical_to_view(mirror_doc.canonical_text_S)}
    mirror_chunks, mirror_audit = chunk_corpus_c1([mirror_doc], mirror_san, tok)
    uniq_parents = {
        (item["document_id"], p_h)
        for item in mirror_audit["empty_parent_headings_propagated"]
        for p_h in item["parents"]
    }
    omitted_count = len(mirror_audit["omitted_boilerplate_headings"])
    heading_only_count = sum(1 for c in mirror_chunks if c.metadata["heading_only"] is True)

    assert len(uniq_parents) == 21
    assert omitted_count == 24
    assert heading_only_count == 14
    assert len(uniq_parents) + omitted_count + heading_only_count == 59
    assert omitted_count + heading_only_count == 38
    assert mirror_audit["coverage_lost_due_to_chunking"] == 0
    assert (
        mirror_audit["body_cp"]
        + mirror_audit["heading_header_cp"]
        + mirror_audit["omitted_ws_cp"]
        == mirror_audit["total_v_cp"]
        == mirror_audit["total_s_cp"]
    )
    assert all(
        len(get_token_offset_spans(ch.assembled_text, tok, max_tokens=None))
        == ch.token_count_with_special
        <= 128
        for ch in mirror_chunks
    )
