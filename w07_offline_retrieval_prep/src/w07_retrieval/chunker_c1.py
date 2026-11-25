"""C1 tokenizer- and span-safe candidate chunker on sanitized view V."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from w07_retrieval.sanitizer import (
    SanitizationResult,
    merge_intervals,
    project_v_span_to_s,
    subtract_intervals,
)
from w07_retrieval.schema import (
    CanonicalDocument,
    ChunkRecord,
    ProvenanceSegment,
    compute_content_hash,
)
from w07_retrieval.visibility import (
    _clone_tokenizer,
    load_minilm_tokenizer,
    populate_chunk_provenance,
)

C1_MAX_TOKENS = 128
C1_OVERLAP = 0

BOILERPLATE_FOOTER_ALLOWLIST = frozenset(
    {
        "Xem thêm",
        "Tham khảo",
        "Liên kết ngoài",
        "Chú thích",
        "Thư viện ảnh",
        "See also",
        "References",
        "External links",
        "Gallery",
        "Notes",
    }
)


@dataclass
class _EmptyParentEntry:
    """Active empty ancestor heading tracked on empty_parent_stack."""

    level: int
    heading: str
    s_spans: List[Tuple[int, int]]
    body_v_span: Tuple[int, int]
    consumed: bool = False


@dataclass
class C1DocumentResult:
    """Detailed C1 chunking output including conservation accounting and omitted footers."""

    chunks: List[ChunkRecord]
    omitted_boilerplate_headings: List[Dict[str, Any]] = field(default_factory=list)
    empty_parent_headings_propagated: List[Dict[str, Any]] = field(default_factory=list)
    body_cp: int = 0
    heading_header_cp: int = 0
    omitted_ws_cp: int = 0
    total_v_cp: int = 0
    total_s_cp: int = 0
    coverage_lost_due_to_chunking: int = 0


class C1Chunker:
    """Deterministic <=128-token, overlap=0, zero-coverage-loss chunker on sanitized view V."""

    HEADING_PATTERN = re.compile(
        r"^(?:(={2,4})[ \t]*([^\r\n]*?)[ \t]*={2,4}|(#{1,4})[ \t]*([^\r\n]*?))[ \t]*(?:\r?\n|$)",
        re.MULTILINE,
    )
    LINE_PATTERN = re.compile(r"[^\n]+\n?")
    SENTENCE_PATTERN = re.compile(r".+?(?:[.!?](?=\s|$)|\n|$)", re.DOTALL)
    CLAUSE_PATTERN = re.compile(r"(?:[^;:,]+[;:,]*|[;:,]+)\s*")
    WORD_PATTERN = re.compile(r"\S+\s*")

    def __init__(self, max_tokens: int = C1_MAX_TOKENS) -> None:
        self.max_tokens = max_tokens

    @staticmethod
    def _tok_len(untrunc_tok: Any, text: str) -> int:
        return len(untrunc_tok.encode(text, add_special_tokens=True).ids)

    @staticmethod
    def _trim_span(text: str, s: int, e: int) -> Optional[Tuple[int, int]]:
        sub = text[s:e]
        stripped = sub.strip()
        if not stripped:
            return None
        lead = len(sub) - len(sub.lstrip())
        return (s + lead, s + lead + len(stripped))

    def _split_unbroken_word(
        self,
        untrunc_tok: Any,
        view_v: str,
        w_s: int,
        w_e: int,
        header_str: str,
    ) -> List[Tuple[int, int, str]]:
        """Binary-search code-point split for an adversarial unbroken >128-token string."""
        spans: List[Tuple[int, int, str]] = []
        pos = w_s
        while pos < w_e:
            if self._tok_len(untrunc_tok, header_str + view_v[pos:w_e]) <= self.max_tokens:
                spans.append((pos, w_e, "char_split"))
                break
            lo = pos + 1
            hi = w_e
            best = pos
            while lo <= hi:
                mid = (lo + hi) // 2
                if self._tok_len(untrunc_tok, header_str + view_v[pos:mid]) <= self.max_tokens:
                    best = mid
                    lo = mid + 1
                else:
                    hi = mid - 1
            if best == pos:
                raise ValueError(
                    "C1 header leaves insufficient token budget for even 1 code point"
                )
            spans.append((pos, best, "char_split"))
            pos = best
        return spans

    def _split_span_into_clauses(
        self,
        untrunc_tok: Any,
        view_v: str,
        span_start: int,
        span_end: int,
        header_str: str,
    ) -> List[Tuple[int, int, str]]:
        """Deterministically split an over-budget unit at ;:, or whitespace or char boundaries."""
        sub_text = view_v[span_start:span_end]
        pieces: List[Tuple[int, int]] = []
        for m in self.CLAUSE_PATTERN.finditer(sub_text):
            trimmed = self._trim_span(
                view_v, span_start + m.start(), span_start + m.end()
            )
            if trimmed is not None:
                pieces.append(trimmed)
        if not pieces:
            trimmed = self._trim_span(view_v, span_start, span_end)
            if trimmed is not None:
                pieces = [trimmed]

        result_spans: List[Tuple[int, int, str]] = []
        cur_s: Optional[int] = None
        cur_e: Optional[int] = None

        for ps, pe in pieces:
            if self._tok_len(untrunc_tok, header_str + view_v[ps:pe]) > self.max_tokens:
                if cur_s is not None and cur_e is not None:
                    result_spans.append((cur_s, cur_e, "clause_split"))
                    cur_s, cur_e = None, None

                word_spans: List[Tuple[int, int]] = []
                for wm in self.WORD_PATTERN.finditer(view_v[ps:pe]):
                    trimmed_w = self._trim_span(view_v, ps + wm.start(), ps + wm.end())
                    if trimmed_w is not None:
                        word_spans.append(trimmed_w)

                ws_cur_s: Optional[int] = None
                ws_cur_e: Optional[int] = None
                for w_s, w_e in word_spans:
                    if (
                        self._tok_len(untrunc_tok, header_str + view_v[w_s:w_e])
                        > self.max_tokens
                    ):
                        if ws_cur_s is not None and ws_cur_e is not None:
                            result_spans.append((ws_cur_s, ws_cur_e, "word_split"))
                            ws_cur_s, ws_cur_e = None, None
                        result_spans.extend(
                            self._split_unbroken_word(
                                untrunc_tok, view_v, w_s, w_e, header_str
                            )
                        )
                        continue
                    if ws_cur_s is None:
                        ws_cur_s, ws_cur_e = w_s, w_e
                    elif (
                        self._tok_len(untrunc_tok, header_str + view_v[ws_cur_s:w_e])
                        <= self.max_tokens
                    ):
                        ws_cur_e = w_e
                    else:
                        result_spans.append((ws_cur_s, ws_cur_e, "word_split"))
                        ws_cur_s, ws_cur_e = w_s, w_e
                if ws_cur_s is not None and ws_cur_e is not None:
                    result_spans.append((ws_cur_s, ws_cur_e, "word_split"))
                continue

            if cur_s is None:
                cur_s, cur_e = ps, pe
            elif (
                self._tok_len(untrunc_tok, header_str + view_v[cur_s:pe])
                <= self.max_tokens
            ):
                cur_e = pe
            else:
                result_spans.append((cur_s, cur_e, "clause_split"))
                cur_s, cur_e = ps, pe

        if cur_s is not None and cur_e is not None:
            result_spans.append((cur_s, cur_e, "clause_split"))
        return result_spans

    @staticmethod
    def _build_header_and_segments(
        doc: CanonicalDocument,
        *,
        is_osm: bool,
        osm_line1: Optional[str],
        osm_line1_s_spans: List[Tuple[int, int]],
        active_chain: Sequence[Tuple[int, str, List[Tuple[int, int]]]],
        is_synthetic_intro: bool,
    ) -> Tuple[str, str, str, List[Dict[str, Any]], List[List[int]]]:
        """Build header_str, header provenance segments, and heading_spans."""
        segments: List[Dict[str, Any]] = []
        heading_s_spans: List[List[int]] = []
        parts: List[str] = []
        a_cur = 0

        def _append_synth(txt: str) -> None:
            nonlocal a_cur
            if not txt:
                return
            parts.append(txt)
            if segments and segments[-1]["kind"] == "SYNTHETIC_HEADER":
                segments[-1]["a_end"] += len(txt)
            else:
                segments.append(
                    ProvenanceSegment(
                        kind="SYNTHETIC_HEADER",
                        a_start=a_cur,
                        a_end=a_cur + len(txt),
                    ).to_dict()
                )
            a_cur += len(txt)

        if is_osm:
            if osm_line1 is not None:
                parts.append(osm_line1)
                for s_a, s_b in osm_line1_s_spans:
                    seg_len = s_b - s_a
                    segments.append(
                        ProvenanceSegment(
                            kind="CANONICAL_HEADING_S",
                            a_start=a_cur,
                            a_end=a_cur + seg_len,
                            s_start=s_a,
                            s_end=s_b,
                        ).to_dict()
                    )
                    heading_s_spans.append([s_a, s_b])
                    a_cur += seg_len
                _append_synth("\n")
                return "".join(parts), "OSM_Facts", "OSM_Facts", segments, heading_s_spans
            else:
                header_str = f"{doc.title} | OSM_Facts\n"
                _append_synth(header_str)
                return header_str, "OSM_Facts", "OSM_Facts", segments, []

        if is_synthetic_intro or not active_chain:
            breadcrumb = "Introduction"
            _append_synth(f"{doc.title} | {breadcrumb}\n")
            return "".join(parts), breadcrumb, breadcrumb, segments, []

        breadcrumb = " > ".join(h_txt for _, h_txt, _ in active_chain)
        leaf_heading = active_chain[-1][1]

        _append_synth(f"{doc.title} | ")
        for idx, (_lvl, h_txt, h_s_spans) in enumerate(active_chain):
            if idx > 0:
                _append_synth(" > ")
            if h_s_spans:
                parts.append(h_txt)
                for s_a, s_b in h_s_spans:
                    seg_len = s_b - s_a
                    segments.append(
                        ProvenanceSegment(
                            kind="CANONICAL_HEADING_S",
                            a_start=a_cur,
                            a_end=a_cur + seg_len,
                            s_start=s_a,
                            s_end=s_b,
                        ).to_dict()
                    )
                    heading_s_spans.append([s_a, s_b])
                    a_cur += seg_len
            else:
                _append_synth(h_txt)
        _append_synth("\n")
        return "".join(parts), leaf_heading, breadcrumb, segments, heading_s_spans

    def chunk_document_detailed(
        self,
        doc: CanonicalDocument,
        sanitized: SanitizationResult,
        tokenizer: Any,
        *,
        max_vis_tokens: int = 128,
    ) -> C1DocumentResult:
        """Chunk a single document into <=128-token C1 chunks with exact conservation accounting."""
        untrunc_tok = _clone_tokenizer(tokenizer, max_tokens=None)
        view_v = sanitized.view_V

        is_osm = doc.source_type == "osm_useful_structured"
        sections: List[Dict[str, Any]] = []
        heading_markup_v_spans: List[Tuple[int, int]] = []
        omitted_boilerplate: List[Dict[str, Any]] = []
        propagated_parents: List[Dict[str, Any]] = []

        if is_osm:
            first_nl = view_v.find("\n")
            if first_nl != -1:
                osm_line1 = view_v[:first_nl]
                osm_line1_s_spans = project_v_span_to_s(0, first_nl, sanitized.segments)
                heading_markup_v_spans.append((0, first_nl + 1))
                sections.append(
                    {
                        "is_osm": True,
                        "osm_line1": osm_line1,
                        "osm_line1_s_spans": osm_line1_s_spans,
                        "active_chain": [],
                        "is_synthetic_intro": False,
                        "body_v_span": (first_nl + 1, len(view_v)),
                        "heading_only": False,
                    }
                )
            else:
                sections.append(
                    {
                        "is_osm": True,
                        "osm_line1": None,
                        "osm_line1_s_spans": [],
                        "active_chain": [],
                        "is_synthetic_intro": False,
                        "body_v_span": (0, len(view_v)),
                        "heading_only": False,
                    }
                )
        else:
            matches = list(self.HEADING_PATTERN.finditer(view_v))
            if not matches:
                if view_v.strip():
                    sections.append(
                        {
                            "is_osm": False,
                            "osm_line1": None,
                            "osm_line1_s_spans": [],
                            "active_chain": [],
                            "is_synthetic_intro": True,
                            "body_v_span": (0, len(view_v)),
                            "heading_only": False,
                        }
                    )
            else:
                if matches[0].start() > 0 and view_v[: matches[0].start()].strip():
                    sections.append(
                        {
                            "is_osm": False,
                            "osm_line1": None,
                            "osm_line1_s_spans": [],
                            "active_chain": [],
                            "is_synthetic_intro": True,
                            "body_v_span": (0, matches[0].start()),
                            "heading_only": False,
                        }
                    )

                empty_parent_stack: List[_EmptyParentEntry] = []
                parsed_headings: List[Tuple[int, str, List[Tuple[int, int]], int, int]] = []
                for idx, m in enumerate(matches):
                    heading_markup_v_spans.append((m.start(), m.end()))
                    if m.group(1) is not None:
                        level = len(m.group(1))
                        raw_txt = m.group(2)
                        grp = 2
                    else:
                        level = len(m.group(3))
                        raw_txt = m.group(4)
                        grp = 4
                    stripped_h = raw_txt.strip()
                    if stripped_h:
                        lead_h = len(raw_txt) - len(raw_txt.lstrip())
                        vh_s = m.start(grp) + lead_h
                        vh_e = vh_s + len(stripped_h)
                        h_s_spans = project_v_span_to_s(vh_s, vh_e, sanitized.segments)
                    else:
                        stripped_h = "Section"
                        h_s_spans = []
                    b_start = m.end()
                    b_end = (
                        matches[idx + 1].start() if idx + 1 < len(matches) else len(view_v)
                    )
                    parsed_headings.append((level, stripped_h, h_s_spans, b_start, b_end))

                def _flush_and_pop_parents(min_level: int) -> None:
                    # Demote unconsumed allowlisted empty parents whose descendants were
                    # all omitted allowlisted leaves so only parents with kept children survive.
                    while (
                        empty_parent_stack
                        and empty_parent_stack[-1].level >= min_level
                        and not empty_parent_stack[-1].consumed
                        and empty_parent_stack[-1].heading in BOILERPLATE_FOOTER_ALLOWLIST
                    ):
                        popped = empty_parent_stack.pop()
                        omitted_boilerplate.append(
                            {
                                "document_id": doc.document_id,
                                "heading": popped.heading,
                                "s_spans": [[a, b] for a, b in popped.s_spans],
                                "omitted_whitespace_chars": (
                                    popped.body_v_span[1] - popped.body_v_span[0]
                                ),
                            }
                        )
                    to_pop = [e for e in empty_parent_stack if e.level >= min_level]
                    if to_pop and any(not e.consumed for e in to_pop):
                        active_chain = [
                            (e.level, e.heading, e.s_spans)
                            for e in empty_parent_stack
                        ]
                        leaf_entry = empty_parent_stack[-1]
                        for e in empty_parent_stack:
                            e.consumed = True
                        sections.append(
                            {
                                "is_osm": False,
                                "osm_line1": None,
                                "osm_line1_s_spans": [],
                                "active_chain": active_chain,
                                "is_synthetic_intro": False,
                                "body_v_span": leaf_entry.body_v_span,
                                "heading_only": True,
                            }
                        )
                    while empty_parent_stack and empty_parent_stack[-1].level >= min_level:
                        empty_parent_stack.pop()

                for idx, (level, stripped_h, h_s_spans, b_start, b_end) in enumerate(
                    parsed_headings
                ):
                    _flush_and_pop_parents(level)

                    has_body = bool(view_v[b_start:b_end].strip())
                    if has_body:
                        active_chain = [
                            *((e.level, e.heading, e.s_spans) for e in empty_parent_stack),
                            (level, stripped_h, h_s_spans),
                        ]
                        if empty_parent_stack:
                            propagated_parents.append(
                                {
                                    "document_id": doc.document_id,
                                    "parents": [e.heading for e in empty_parent_stack],
                                    "child": stripped_h,
                                }
                            )
                        for e in empty_parent_stack:
                            e.consumed = True
                        sections.append(
                            {
                                "is_osm": False,
                                "osm_line1": None,
                                "osm_line1_s_spans": [],
                                "active_chain": active_chain,
                                "is_synthetic_intro": False,
                                "body_v_span": (b_start, b_end),
                                "heading_only": False,
                            }
                        )
                    else:
                        next_level = (
                            parsed_headings[idx + 1][0]
                            if idx + 1 < len(parsed_headings)
                            else None
                        )
                        # Structural hierarchy takes precedence over leaf boilerplate omission:
                        # keep any empty parent preceding a deeper subheading even if its title
                        # matches BOILERPLATE_FOOTER_ALLOWLIST (e.g., `== Tham khảo ==` before
                        # `=== Ghi chú ===` / `=== Đọc thêm ===`). Standalone empty leaves remain omitted.
                        if next_level is not None and next_level > level:
                            empty_parent_stack.append(
                                _EmptyParentEntry(
                                    level=level,
                                    heading=stripped_h,
                                    s_spans=h_s_spans,
                                    body_v_span=(b_start, b_end),
                                    consumed=False,
                                )
                            )
                        elif stripped_h in BOILERPLATE_FOOTER_ALLOWLIST:
                            omitted_boilerplate.append(
                                {
                                    "document_id": doc.document_id,
                                    "heading": stripped_h,
                                    "s_spans": [[a, b] for a, b in h_s_spans],
                                    "omitted_whitespace_chars": b_end - b_start,
                                }
                            )
                        else:
                            active_chain = [
                                *((e.level, e.heading, e.s_spans) for e in empty_parent_stack),
                                (level, stripped_h, h_s_spans),
                            ]
                            for e in empty_parent_stack:
                                e.consumed = True
                            sections.append(
                                {
                                    "is_osm": False,
                                    "osm_line1": None,
                                    "osm_line1_s_spans": [],
                                    "active_chain": active_chain,
                                    "is_synthetic_intro": False,
                                    "body_v_span": (b_start, b_end),
                                    "heading_only": True,
                                }
                            )

                _flush_and_pop_parents(0)

        chunks: List[ChunkRecord] = []
        body_v_spans_used: List[Tuple[int, int]] = []
        expected_body_non_ws_parts: List[str] = []
        reconstructed_body_non_ws_parts: List[str] = []
        chunk_index = 0

        for sec_idx, sec in enumerate(sections):
            header_str, leaf_heading, breadcrumb, header_segs, heading_s_spans = (
                self._build_header_and_segments(
                    doc,
                    is_osm=sec["is_osm"],
                    osm_line1=sec["osm_line1"],
                    osm_line1_s_spans=sec["osm_line1_s_spans"],
                    active_chain=sec["active_chain"],
                    is_synthetic_intro=sec["is_synthetic_intro"],
                )
            )

            header_tok_count = self._tok_len(untrunc_tok, header_str)
            if header_tok_count >= self.max_tokens:
                raise ValueError(
                    f"C1 header alone leaves zero body token budget ({header_tok_count} >= {self.max_tokens}) "
                    f"for {doc.document_id!r}"
                )

            b_start, b_end = sec["body_v_span"]

            if sec["heading_only"]:
                cid = f"{doc.document_id}-c1-s{sec_idx}-p0"
                rec = ChunkRecord(
                    chunk_id=cid,
                    document_id=doc.document_id,
                    chunker="C1",
                    chunk_index=chunk_index,
                    title=doc.title,
                    poi_id=doc.poi_id,
                    source_type=doc.source_type,
                    language=doc.language,
                    section_heading=leaf_heading,
                    section_breadcrumb=breadcrumb,
                    assembled_text=header_str,
                    assembled_segments=header_segs,
                    heading_spans=heading_s_spans,
                    body_v_span=None,
                    c_full_s_spans=[],
                    c_vis_s_spans_dense=[],
                    c_vis_s_spans_bm25=[],
                    token_count_with_special=0,
                    word_count=0,
                    content_hash=compute_content_hash(header_str),
                    metadata={
                        "section_index": sec_idx,
                        "part_index": 0,
                        "heading_only": True,
                    },
                )
                populate_chunk_provenance(
                    rec,
                    untrunc_tok,
                    sanitized.segments,
                    max_dense_tokens=max_vis_tokens,
                )
                if rec.token_count_with_special > self.max_tokens:
                    raise AssertionError(
                        f"C1 token ceiling exceeded: {rec.token_count_with_special} > {self.max_tokens}"
                    )
                chunks.append(rec)
                chunk_index += 1
                continue

            sec_text = view_v[b_start:b_end]
            expected_body_non_ws_parts.append("".join(sec_text.split()))

            unit_spans: List[Tuple[int, int, str]] = []
            if doc.source_type in (
                "overture_places_parquet",
                "wikidata_entity",
                "osm_useful_structured",
            ):
                for lm in self.LINE_PATTERN.finditer(sec_text):
                    trimmed = self._trim_span(
                        view_v, b_start + lm.start(), b_start + lm.end()
                    )
                    if trimmed is not None:
                        unit_spans.append((trimmed[0], trimmed[1], "line"))
            else:
                for lm in self.LINE_PATTERN.finditer(sec_text):
                    line_str = lm.group(0)
                    if not line_str.strip():
                        continue
                    l_abs = b_start + lm.start()
                    for sm in self.SENTENCE_PATTERN.finditer(line_str):
                        trimmed = self._trim_span(
                            view_v, l_abs + sm.start(), l_abs + sm.end()
                        )
                        if trimmed is not None:
                            unit_spans.append((trimmed[0], trimmed[1], "sentence"))

            safe_units: List[Tuple[int, int, str]] = []
            for u_s, u_e, u_kind in unit_spans:
                if (
                    self._tok_len(untrunc_tok, header_str + view_v[u_s:u_e])
                    <= self.max_tokens
                ):
                    safe_units.append((u_s, u_e, u_kind))
                else:
                    safe_units.extend(
                        self._split_span_into_clauses(
                            untrunc_tok, view_v, u_s, u_e, header_str
                        )
                    )

            part_idx = 0
            cur_s: Optional[int] = None
            cur_e: Optional[int] = None

            def _emit_chunk(slice_s: int, slice_e: int, p_idx: int) -> None:
                nonlocal chunk_index
                body_slice = view_v[slice_s:slice_e]
                assembled = header_str + body_slice
                segs = [dict(seg) for seg in header_segs]
                segs.append(
                    ProvenanceSegment(
                        kind="CANONICAL_BODY_V",
                        a_start=len(header_str),
                        a_end=len(assembled),
                        v_start=slice_s,
                        v_end=slice_e,
                    ).to_dict()
                )
                cid = (
                    f"{doc.document_id}-c1-p{p_idx}"
                    if is_osm
                    else f"{doc.document_id}-c1-s{sec_idx}-p{p_idx}"
                )
                rec = ChunkRecord(
                    chunk_id=cid,
                    document_id=doc.document_id,
                    chunker="C1",
                    chunk_index=chunk_index,
                    title=doc.title,
                    poi_id=doc.poi_id,
                    source_type=doc.source_type,
                    language=doc.language,
                    section_heading=leaf_heading,
                    section_breadcrumb=breadcrumb,
                    assembled_text=assembled,
                    assembled_segments=segs,
                    heading_spans=[list(sp) for sp in heading_s_spans],
                    body_v_span=[slice_s, slice_e],
                    c_full_s_spans=[],
                    c_vis_s_spans_dense=[],
                    c_vis_s_spans_bm25=[],
                    token_count_with_special=0,
                    word_count=len(body_slice.split()),
                    content_hash=compute_content_hash(assembled),
                    metadata={
                        "section_index": sec_idx,
                        "part_index": p_idx,
                        "heading_only": False,
                    },
                )
                populate_chunk_provenance(
                    rec,
                    untrunc_tok,
                    sanitized.segments,
                    max_dense_tokens=max_vis_tokens,
                )
                if rec.token_count_with_special > self.max_tokens:
                    raise AssertionError(
                        f"C1 token ceiling violated on {cid}: {rec.token_count_with_special} > {self.max_tokens}"
                    )
                chunks.append(rec)
                body_v_spans_used.append((slice_s, slice_e))
                reconstructed_body_non_ws_parts.append("".join(body_slice.split()))
                chunk_index += 1

            for u_s, u_e, _ in safe_units:
                if cur_s is None:
                    cur_s, cur_e = u_s, u_e
                elif (
                    self._tok_len(untrunc_tok, header_str + view_v[cur_s:u_e])
                    <= self.max_tokens
                ):
                    cur_e = u_e
                else:
                    assert cur_e is not None
                    _emit_chunk(cur_s, cur_e, part_idx)
                    part_idx += 1
                    cur_s, cur_e = u_s, u_e

            if cur_s is not None and cur_e is not None:
                _emit_chunk(cur_s, cur_e, part_idx)

        expected_non_ws = "".join(expected_body_non_ws_parts)
        reconstructed_non_ws = "".join(reconstructed_body_non_ws_parts)
        coverage_lost = len(expected_non_ws) - len(reconstructed_non_ws)
        if coverage_lost != 0 or expected_non_ws != reconstructed_non_ws:
            raise AssertionError(
                f"C1 coverage conservation failed on {doc.document_id}: lost={coverage_lost}"
            )

        # Exact code-point partition accounting on V: body_cp + heading_header_cp + omitted_ws_cp == len(V)
        merged_body = merge_intervals(body_v_spans_used)
        merged_headings = merge_intervals(heading_markup_v_spans)
        covered = merge_intervals([*merged_body, *merged_headings])
        omitted_spans = subtract_intervals([(0, len(view_v))], covered)
        for oa, ob in omitted_spans:
            if not view_v[oa:ob].isspace():
                raise AssertionError(
                    f"Non-whitespace character omitted in {doc.document_id} at V[{oa}:{ob}]={view_v[oa:ob]!r}"
                )

        body_cp = sum(b - a for a, b in merged_body)
        heading_header_cp = sum(b - a for a, b in merged_headings)
        omitted_ws_cp = sum(b - a for a, b in omitted_spans)
        if body_cp + heading_header_cp + omitted_ws_cp != len(view_v):
            raise AssertionError("Code-point partition sum mismatch on V")

        return C1DocumentResult(
            chunks=chunks,
            omitted_boilerplate_headings=omitted_boilerplate,
            empty_parent_headings_propagated=propagated_parents,
            body_cp=body_cp,
            heading_header_cp=heading_header_cp,
            omitted_ws_cp=omitted_ws_cp,
            total_v_cp=len(view_v),
            total_s_cp=len(sanitized.canonical_S),
            coverage_lost_due_to_chunking=coverage_lost,
        )

    def chunk_document(
        self,
        doc: CanonicalDocument,
        sanitized: SanitizationResult,
        tokenizer: Any,
        *,
        max_vis_tokens: int = 128,
    ) -> List[ChunkRecord]:
        """Chunk a single document into C1 ChunkRecords."""
        return self.chunk_document_detailed(
            doc, sanitized, tokenizer, max_vis_tokens=max_vis_tokens
        ).chunks


def chunk_corpus_c1(
    docs: Sequence[CanonicalDocument],
    sanitized_by_doc: Dict[str, SanitizationResult],
    tokenizer: Any = None,
    *,
    max_vis_tokens: int = 128,
) -> Tuple[List[ChunkRecord], Dict[str, Any]]:
    """Chunk an entire corpus with C1Chunker, returning (chunks, audit_summary)."""
    tok = tokenizer if tokenizer is not None else load_minilm_tokenizer()
    chunker = C1Chunker()
    all_chunks: List[ChunkRecord] = []
    omitted_boilerplate: List[Dict[str, Any]] = []
    propagated_parents: List[Dict[str, Any]] = []
    body_cp = 0
    heading_header_cp = 0
    omitted_ws_cp = 0
    total_v_cp = 0
    total_s_cp = 0
    coverage_lost = 0

    for doc in docs:
        res = chunker.chunk_document_detailed(
            doc, sanitized_by_doc[doc.document_id], tok, max_vis_tokens=max_vis_tokens
        )
        all_chunks.extend(res.chunks)
        omitted_boilerplate.extend(res.omitted_boilerplate_headings)
        propagated_parents.extend(res.empty_parent_headings_propagated)
        body_cp += res.body_cp
        heading_header_cp += res.heading_header_cp
        omitted_ws_cp += res.omitted_ws_cp
        total_v_cp += res.total_v_cp
        total_s_cp += res.total_s_cp
        coverage_lost += res.coverage_lost_due_to_chunking

    audit = {
        "omitted_boilerplate_headings": omitted_boilerplate,
        "empty_parent_headings_propagated": propagated_parents,
        "body_cp": body_cp,
        "heading_header_cp": heading_header_cp,
        "omitted_ws_cp": omitted_ws_cp,
        "total_v_cp": total_v_cp,
        "total_s_cp": total_s_cp,
        "coverage_lost_due_to_chunking": coverage_lost,
    }
    return all_chunks, audit
