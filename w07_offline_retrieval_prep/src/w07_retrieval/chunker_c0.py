"""C0 legacy comparator chunker: SectionAwareChunker(250, 450, 1) on sanitized view V."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from w07_retrieval.sanitizer import SanitizationResult, project_v_span_to_s
from w07_retrieval.schema import (
    CanonicalDocument,
    ChunkRecord,
    ProvenanceSegment,
    compute_content_hash,
)
from w07_retrieval.visibility import (
    load_minilm_tokenizer,
    populate_chunk_provenance,
)


@dataclass
class C0DocumentResult:
    """Detailed C0 chunking output including logged <10-word skipped fragments."""

    chunks: List[ChunkRecord]
    skipped_short_fragments: List[Dict[str, Any]] = field(default_factory=list)


class C0Chunker:
    """Exact SectionAwareChunker(250, 450, 1) comparator applied to sanitized view V."""

    HEADING_PATTERN = re.compile(
        r"^(?:={2,4}\s*(.*?)\s*={2,4}|#{1,4}\s*(.*?))$", re.MULTILINE
    )
    SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+")

    def __init__(
        self,
        target_chunk_words: int = 250,
        max_chunk_words: int = 450,
        overlap_sentences: int = 1,
    ) -> None:
        self.target_chunk_words = target_chunk_words
        self.max_chunk_words = max_chunk_words
        self.overlap_sentences = overlap_sentences

    def _split_into_sections_with_spans(
        self, view_v: str
    ) -> List[Dict[str, Any]]:
        """Mirror SectionAwareChunker.split_into_sections while retaining exact V spans."""
        matches = list(self.HEADING_PATTERN.finditer(view_v))
        sections: List[Dict[str, Any]] = []

        if not matches:
            stripped = view_v.strip()
            if stripped:
                lead = len(view_v) - len(view_v.lstrip())
                b_s = lead
                b_e = b_s + len(stripped)
                sections.append(
                    {
                        "heading": "Introduction",
                        "heading_is_synthetic": True,
                        "heading_v_span": None,
                        "body_v_span": (b_s, b_e),
                    }
                )
            else:
                sections.append(
                    {
                        "heading": "Introduction",
                        "heading_is_synthetic": True,
                        "heading_v_span": None,
                        "body_v_span": (0, 0),
                    }
                )
            return sections

        first_start = matches[0].start()
        if first_start > 0:
            intro_raw = view_v[:first_start]
            intro_stripped = intro_raw.strip()
            if intro_stripped:
                lead = len(intro_raw) - len(intro_raw.lstrip())
                b_s = lead
                b_e = b_s + len(intro_stripped)
                sections.append(
                    {
                        "heading": "Introduction",
                        "heading_is_synthetic": True,
                        "heading_v_span": None,
                        "body_v_span": (b_s, b_e),
                    }
                )

        for i, m in enumerate(matches):
            if m.group(1) is not None and m.group(1).strip():
                grp = 1
            elif m.group(2) is not None and m.group(2).strip():
                grp = 2
            else:
                grp = None

            if grp is None:
                heading = "Section"
                heading_is_synthetic = True
                heading_v_span = None
            else:
                raw_inner = m.group(grp)
                heading = raw_inner.strip()
                lead_h = len(raw_inner) - len(raw_inner.lstrip())
                v_h_s = m.start(grp) + lead_h
                v_h_e = v_h_s + len(heading)
                heading_is_synthetic = False
                heading_v_span = (v_h_s, v_h_e)

            start_body = m.end()
            end_body = matches[i + 1].start() if i + 1 < len(matches) else len(view_v)
            raw_body = view_v[start_body:end_body]
            stripped_body = raw_body.strip()
            if stripped_body:
                lead_b = len(raw_body) - len(raw_body.lstrip())
                b_s = start_body + lead_b
                b_e = b_s + len(stripped_body)
                sections.append(
                    {
                        "heading": heading,
                        "heading_is_synthetic": heading_is_synthetic,
                        "heading_v_span": heading_v_span,
                        "body_v_span": (b_s, b_e),
                    }
                )

        return sections

    def _split_body_into_sentence_chunks(
        self, view_v: str, b_s: int, b_e: int
    ) -> List[List[Tuple[int, int]]]:
        """Mirror SectionAwareChunker._split_body_into_chunks keeping exact sentence V spans."""
        if b_s >= b_e:
            return []

        raw_spans: List[Tuple[int, int]] = []
        cursor = b_s
        for sm in self.SENTENCE_SPLIT_PATTERN.finditer(view_v, b_s, b_e):
            raw_spans.append((cursor, sm.start()))
            cursor = sm.end()
        raw_spans.append((cursor, b_e))

        sent_spans: List[Tuple[int, int]] = []
        for rs, re_ in raw_spans:
            sub = view_v[rs:re_]
            stripped = sub.strip()
            if not stripped:
                continue
            lead = len(sub) - len(sub.lstrip())
            s_start = rs + lead
            s_end = s_start + len(stripped)
            sent_spans.append((s_start, s_end))

        if not sent_spans:
            return []

        chunks: List[List[Tuple[int, int]]] = []
        current_sentences: List[Tuple[int, int]] = []
        current_word_count = 0

        for vs, ve in sent_spans:
            words = len(view_v[vs:ve].split())
            if current_word_count + words > self.max_chunk_words and current_sentences:
                chunks.append(list(current_sentences))
                current_sentences = (
                    current_sentences[-self.overlap_sentences :]
                    if self.overlap_sentences > 0
                    else []
                )
                current_word_count = sum(
                    len(view_v[s_a:s_b].split()) for s_a, s_b in current_sentences
                )
            current_sentences.append((vs, ve))
            current_word_count += words

        if current_sentences:
            chunks.append(list(current_sentences))

        return chunks

    @staticmethod
    def _build_assembled_and_segments(
        doc: CanonicalDocument,
        sanitized: SanitizationResult,
        heading: str,
        heading_is_synthetic: bool,
        heading_v_span: Optional[Tuple[int, int]],
        sent_spans: Sequence[Tuple[int, int]],
    ) -> Tuple[str, List[Dict[str, Any]], List[List[int]]]:
        """Construct A(c) = f'{title} - {heading}\\n{body_chunk}' and disjoint segments."""
        view_v = sanitized.view_V
        segments: List[Dict[str, Any]] = []
        heading_s_spans: List[List[int]] = []

        def _append_synth(text_len: int, a_cur: int) -> int:
            if text_len <= 0:
                return a_cur
            if segments and segments[-1]["kind"] == "SYNTHETIC_HEADER":
                segments[-1]["a_end"] += text_len
            else:
                segments.append(
                    ProvenanceSegment(
                        kind="SYNTHETIC_HEADER",
                        a_start=a_cur,
                        a_end=a_cur + text_len,
                    ).to_dict()
                )
            return a_cur + text_len

        parts: List[str] = []
        a_cur = 0

        prefix = f"{doc.title} - "
        parts.append(prefix)
        a_cur = _append_synth(len(prefix), a_cur)

        parts.append(heading)
        if heading_is_synthetic or heading_v_span is None:
            a_cur = _append_synth(len(heading), a_cur)
        else:
            vh_s, vh_e = heading_v_span
            proj = project_v_span_to_s(vh_s, vh_e, sanitized.segments)
            for s_a, s_b in proj:
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

        parts.append("\n")
        a_cur = _append_synth(1, a_cur)

        for idx, (vs, ve) in enumerate(sent_spans):
            if idx > 0:
                prev_e = sent_spans[idx - 1][1]
                parts.append(" ")
                if (
                    view_v[prev_e:vs] == " "
                    and segments
                    and segments[-1]["kind"] == "CANONICAL_BODY_V"
                ):
                    segments[-1]["a_end"] += 1 + (ve - vs)
                    segments[-1]["v_end"] = ve
                    parts.append(view_v[vs:ve])
                    a_cur += 1 + (ve - vs)
                    continue
                else:
                    a_cur = _append_synth(1, a_cur)

            sent_text = view_v[vs:ve]
            parts.append(sent_text)
            segments.append(
                ProvenanceSegment(
                    kind="CANONICAL_BODY_V",
                    a_start=a_cur,
                    a_end=a_cur + len(sent_text),
                    v_start=vs,
                    v_end=ve,
                ).to_dict()
            )
            a_cur += len(sent_text)

        assembled = "".join(parts)
        return assembled, segments, heading_s_spans

    def chunk_document_detailed(
        self,
        doc: CanonicalDocument,
        sanitized: SanitizationResult,
        tokenizer: Any,
        *,
        max_vis_tokens: int = 128,
    ) -> C0DocumentResult:
        """Chunk a single document into C0 ChunkRecords plus skipped short-fragment logs."""
        view_v = sanitized.view_V
        sections = self._split_into_sections_with_spans(view_v)
        chunks: List[ChunkRecord] = []
        skipped: List[Dict[str, Any]] = []
        chunk_index = 0

        for sec_idx, sec in enumerate(sections):
            heading = sec["heading"]
            b_s, b_e = sec["body_v_span"]
            body_chunks = self._split_body_into_sentence_chunks(view_v, b_s, b_e)
            for part_idx, sent_spans in enumerate(body_chunks):
                body_chunk = " ".join(view_v[vs:ve] for vs, ve in sent_spans)
                word_count = len(body_chunk.split())
                chunk_id = f"{doc.document_id}-s{sec_idx}-p{part_idx}"
                if word_count < 10:
                    skipped.append(
                        {
                            "document_id": doc.document_id,
                            "chunk_id_candidate": chunk_id,
                            "section_index": sec_idx,
                            "part_index": part_idx,
                            "section_heading": heading,
                            "word_count": word_count,
                            "body_preview": body_chunk[:120],
                            "v_span": [sent_spans[0][0], sent_spans[-1][1]],
                        }
                    )
                    continue

                assembled, segments, heading_s_spans = self._build_assembled_and_segments(
                    doc=doc,
                    sanitized=sanitized,
                    heading=heading,
                    heading_is_synthetic=sec["heading_is_synthetic"],
                    heading_v_span=sec["heading_v_span"],
                    sent_spans=sent_spans,
                )

                rec = ChunkRecord(
                    chunk_id=chunk_id,
                    document_id=doc.document_id,
                    chunker="C0",
                    chunk_index=chunk_index,
                    title=doc.title,
                    poi_id=doc.poi_id,
                    source_type=doc.source_type,
                    language=doc.language,
                    section_heading=heading,
                    section_breadcrumb=heading,
                    assembled_text=assembled,
                    assembled_segments=segments,
                    heading_spans=heading_s_spans,
                    body_v_span=[sent_spans[0][0], sent_spans[-1][1]],
                    c_full_s_spans=[],
                    c_vis_s_spans_dense=[],
                    c_vis_s_spans_bm25=[],
                    token_count_with_special=0,
                    word_count=word_count,
                    content_hash=compute_content_hash(assembled),
                    metadata={
                        "section_index": sec_idx,
                        "part_index": part_idx,
                        "word_count": word_count,
                    },
                )
                populate_chunk_provenance(
                    rec,
                    tokenizer,
                    sanitized.segments,
                    max_dense_tokens=max_vis_tokens,
                )
                chunks.append(rec)
                chunk_index += 1

        return C0DocumentResult(chunks=chunks, skipped_short_fragments=skipped)

    def chunk_document(
        self,
        doc: CanonicalDocument,
        sanitized: SanitizationResult,
        tokenizer: Any,
        *,
        max_vis_tokens: int = 128,
    ) -> List[ChunkRecord]:
        """Chunk a single document into C0 ChunkRecords."""
        return self.chunk_document_detailed(
            doc, sanitized, tokenizer, max_vis_tokens=max_vis_tokens
        ).chunks


def chunk_corpus_c0(
    docs: Sequence[CanonicalDocument],
    sanitized_by_doc: Dict[str, SanitizationResult],
    tokenizer: Any = None,
    *,
    max_vis_tokens: int = 128,
) -> Tuple[List[ChunkRecord], List[Dict[str, Any]]]:
    """Chunk an entire corpus with C0Chunker, returning (chunks, c0_skipped_short_fragments)."""
    tok = tokenizer if tokenizer is not None else load_minilm_tokenizer()
    chunker = C0Chunker()
    all_chunks: List[ChunkRecord] = []
    all_skipped: List[Dict[str, Any]] = []
    for doc in docs:
        res = chunker.chunk_document_detailed(
            doc, sanitized_by_doc[doc.document_id], tok, max_vis_tokens=max_vis_tokens
        )
        all_chunks.extend(res.chunks)
        all_skipped.extend(res.skipped_short_fragments)
    return all_chunks, all_skipped
