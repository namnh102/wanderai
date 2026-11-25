"""Canonical document, chunk, provenance, and ranking schemas for W07 offline retrieval."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

OSM_LICENSE = "ODbL 1.0"
OSM_ATTRIBUTION = "© OpenStreetMap contributors"

PINNED_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
PINNED_SNAPSHOT_ID = "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"
PINNED_TOKENIZER_SHA256 = (
    "2c3387be76557bd40970cec13153b3bbf80407865484b209e655e5e4729076b8"
)
DEFAULT_SNAPSHOT_DIR = (
    Path.home()
    / ".cache"
    / "huggingface"
    / "hub"
    / "models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2"
    / "snapshots"
    / PINNED_SNAPSHOT_ID
)

CATEGORY_LABEL_VI: Dict[str, str] = {
    "attraction": "tham quan",
    "culture": "văn hóa",
    "beach": "biển",
    "nature": "thiên nhiên",
    "entertainment": "giải trí",
    "cafe": "quán cà phê",
    "restaurant": "nhà hàng",
    "hotel": "khách sạn",
}

CLASS_KEYS: Tuple[str, ...] = ("tourism", "historic", "natural", "amenity", "leisure")

FACT_FIELDS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("Giờ mở cửa", ("opening_hours",)),
    ("Website", ("website", "contact:website")),
    ("Điện thoại", ("phone", "contact:phone")),
    ("Email", ("email", "contact:email")),
    ("Ẩm thực", ("cuisine",)),
    ("Tiếp cận xe lăn", ("wheelchair",)),
    ("Đơn vị vận hành", ("operator",)),
    ("Tôn giáo", ("religion",)),
    ("Số sao", ("stars",)),
    ("Wikipedia", ("wikipedia",)),
    ("Wikidata", ("wikidata",)),
    ("Mô tả (OSM)", ("description:vi", "description")),
)


def compute_content_hash(text: str) -> str:
    """Compute deterministic SHA-256 hash matching SectionAwareChunker.compute_hash."""
    normalized = " ".join(text.strip().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ProvenanceSegment:
    """Disjoint provenance slice [a_start, a_end) inside assembled chunk string A(c)."""

    kind: Literal["SYNTHETIC_HEADER", "CANONICAL_HEADING_S", "CANONICAL_BODY_V"]
    a_start: int
    a_end: int
    s_start: Optional[int] = None
    s_end: Optional[int] = None
    v_start: Optional[int] = None
    v_end: Optional[int] = None

    def __post_init__(self) -> None:
        if not (0 <= self.a_start <= self.a_end):
            raise ValueError(f"Invalid A(c) span [{self.a_start}, {self.a_end})")
        a_len = self.a_end - self.a_start
        if self.kind == "SYNTHETIC_HEADER":
            if any(x is not None for x in (self.s_start, self.s_end, self.v_start, self.v_end)):
                raise ValueError("SYNTHETIC_HEADER must have None canonical/view offsets")
        elif self.kind == "CANONICAL_HEADING_S":
            if self.s_start is None or self.s_end is None:
                raise ValueError("CANONICAL_HEADING_S requires s_start and s_end")
            if self.v_start is not None or self.v_end is not None:
                raise ValueError("CANONICAL_HEADING_S must not set v_start/v_end")
            if (self.s_end - self.s_start) != a_len:
                raise ValueError("CANONICAL_HEADING_S length mismatch with A(c) slice")
        elif self.kind == "CANONICAL_BODY_V":
            if self.v_start is None or self.v_end is None:
                raise ValueError("CANONICAL_BODY_V requires v_start and v_end")
            if self.s_start is not None or self.s_end is not None:
                raise ValueError("CANONICAL_BODY_V must not set s_start/s_end")
            if (self.v_end - self.v_start) != a_len:
                raise ValueError("CANONICAL_BODY_V length mismatch with A(c) slice")
        else:
            raise ValueError(f"Unknown provenance segment kind: {self.kind!r}")

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "kind": self.kind,
            "a_start": self.a_start,
            "a_end": self.a_end,
        }
        if self.s_start is not None:
            out["s_start"] = self.s_start
            out["s_end"] = self.s_end
        if self.v_start is not None:
            out["v_start"] = self.v_start
            out["v_end"] = self.v_end
        return out


@dataclass(frozen=True)
class CanonicalDocument:
    """Immutable canonical source document S."""

    document_id: str
    source_type: str
    title: str
    language: str
    source_lineage_id: str
    poi_id: Optional[str]
    city: Optional[str]
    canonical_text_S: str
    text_field_used: str
    license: str = ""
    attribution: str = ""
    source_url: str = ""
    source_revision: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChunkRecord:
    """Chunk produced by C0 or C1 over sanitized view V with full provenance."""

    chunk_id: str
    document_id: str
    chunker: Literal["C0", "C1"]
    chunk_index: int
    title: str
    poi_id: Optional[str]
    source_type: str
    language: str
    section_heading: str
    section_breadcrumb: str
    assembled_text: str
    assembled_segments: List[Dict[str, Any]]
    heading_spans: List[List[int]]
    body_v_span: Optional[List[int]]
    c_full_s_spans: List[List[int]]
    c_vis_s_spans_dense: List[List[int]]
    c_vis_s_spans_bm25: List[List[int]]
    token_count_with_special: int
    word_count: int
    content_hash: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_manifest_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "chunker": self.chunker,
            "chunk_index": self.chunk_index,
            "title": self.title,
            "poi_id": self.poi_id,
            "source_type": self.source_type,
            "language": self.language,
            "section_heading": self.section_heading,
            "section_breadcrumb": self.section_breadcrumb,
            "assembled_text": self.assembled_text,
            "assembled_segments": self.assembled_segments,
            "heading_spans": self.heading_spans,
            "body_v_span": self.body_v_span,
            "c_full_s_spans": self.c_full_s_spans,
            "c_vis_s_spans_dense": self.c_vis_s_spans_dense,
            "c_vis_s_spans_bm25": self.c_vis_s_spans_bm25,
            "token_count_with_special": self.token_count_with_special,
            "word_count": self.word_count,
            "content_hash": self.content_hash,
            "metadata": self.metadata,
        }


@dataclass
class RankingRow:
    """Exact 15-key sealed ranking row for g3_sealed_rankings_v1.jsonl."""

    cell_id: str
    chunker: Literal["C0", "C1"]
    retriever: Literal["BM25", "Dense", "RRF"]
    query_id: str
    rank: int
    document_id: str
    score: float
    rep_chunk_id: str
    rep_chunk_index: int
    assembled_text: str
    assembled_segments: List[Dict[str, Any]]
    c_full_s_spans: List[List[int]]
    c_vis_s_spans: List[List[int]]
    leg_ranks: Dict[str, Optional[int]]
    leg_rep_chunks: Dict[str, Optional[Dict[str, Any]]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cell_id": self.cell_id,
            "chunker": self.chunker,
            "retriever": self.retriever,
            "query_id": self.query_id,
            "rank": self.rank,
            "document_id": self.document_id,
            "score": float(self.score),
            "rep_chunk_id": self.rep_chunk_id,
            "rep_chunk_index": self.rep_chunk_index,
            "assembled_text": self.assembled_text,
            "assembled_segments": self.assembled_segments,
            "c_full_s_spans": self.c_full_s_spans,
            "c_vis_s_spans": self.c_vis_s_spans,
            "leg_ranks": self.leg_ranks,
            "leg_rep_chunks": self.leg_rep_chunks,
        }


@dataclass(frozen=True)
class QueryRecord:
    """Query record loaded from queries.jsonl."""

    query_id: str
    query_text: str
    metadata: Dict[str, Any] = field(default_factory=dict)


def _coerce_raw_dict(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return {}
    if not isinstance(raw, dict):
        return {}
    return raw


def extract_osm_tags(raw: Any) -> Dict[str, str]:
    """Extract clean string OSM tags mirroring apps/ai-service/app/rag/osm_documents.py."""
    data = _coerce_raw_dict(raw)
    if not data:
        return {}
    nested_tags = data.get("tags")
    tag_source = nested_tags if isinstance(nested_tags, dict) else data
    return {
        str(k): str(v)
        for k, v in tag_source.items()
        if isinstance(k, str)
        and not k.startswith("_")
        and (nested_tags is tag_source or k != "tags")
        and v is not None
        and not isinstance(v, (dict, list))
        and str(v).strip()
    }


def format_osm_address(tags: Dict[str, str]) -> str:
    """Address only from addr:* tags."""
    parts: List[str] = []
    street, number = tags.get("addr:street"), tags.get("addr:housenumber")
    if street and number:
        parts.append(f"{number} {street}")
    elif street:
        parts.append(street)
    district = tags.get("addr:district") or tags.get("addr:suburb")
    if district:
        parts.append(district)
    city = tags.get("addr:city") or tags.get("addr:province")
    if city:
        parts.append(city)
    return ", ".join(parts)


def build_osm_canonical_text(
    place: Dict[str, Any], city_fallback: Optional[str] = None
) -> Tuple[str, Dict[str, Any]]:
    """Build deterministic OSM canonical text S and metadata from a place dict."""
    osm_sources = sorted(
        (s for s in place.get("sources", []) if s.get("source_name") == "osm"),
        key=lambda s: s["source_id"],
    )
    if not osm_sources:
        raise ValueError("Place missing verified OSM source")
    src = osm_sources[0]
    tags = extract_osm_tags(src.get("raw_data"))
    raw_data = _coerce_raw_dict(src.get("raw_data"))
    nested_raw_tags = raw_data.get("tags")
    osm_base_ts = raw_data.get("_osm_base_timestamp")
    if osm_base_ts is None and isinstance(nested_raw_tags, dict):
        osm_base_ts = nested_raw_tags.get("_osm_base_timestamp")

    name = place["name"]
    category = place.get("category") or ""
    label = CATEGORY_LABEL_VI.get(category, category)

    head = name
    if tags.get("name:en") and tags["name:en"] != name:
        head += f" ({tags['name:en']})"
    head += f" thuộc nhóm {label}" if label else " là một địa điểm"
    dest = (
        place.get("destination")
        or place.get("destination_name")
        or place.get("city")
        or city_fallback
    )
    if dest:
        head += f" tại {dest}"
    lines: List[str] = [head + "."]

    klass = [f"{k}={tags[k]}" for k in CLASS_KEYS if tags.get(k)]
    if klass:
        lines.append("Loại OSM: " + ", ".join(klass) + ".")
    address = format_osm_address(tags)
    if address:
        lines.append(f"Địa chỉ: {address}.")
    if place.get("latitude") is not None and place.get("longitude") is not None:
        lines.append(f"Tọa độ: {place['latitude']}, {place['longitude']}.")

    used: List[str] = []
    for lbl, keys in FACT_FIELDS:
        for k in keys:
            if tags.get(k):
                lines.append(f"{lbl}: {tags[k]}.")
                used.append(k)
                break
    lines.append(f"Nguồn: OpenStreetMap {src['source_id']}.")
    content = "\n".join(lines)
    meta = {
        "source_id": src["source_id"],
        "source_url": f"https://www.openstreetmap.org/{src['source_id']}",
        "osm_tags_used": sorted(used),
        "osm_base_timestamp": osm_base_ts,
    }
    return content, meta


def load_canonical_document(
    record: Dict[str, Any], city_fallback: Optional[str] = None
) -> CanonicalDocument:
    """Load CanonicalDocument from synthetic corpus row, B1B doc, or OSM place payload."""
    extra_meta: Dict[str, Any] = dict(record.get("metadata") or {})

    # Case 1: Explicit canonical_text_S
    if record.get("canonical_text_S") is not None:
        doc_id = str(record["document_id"])
        source_type = str(record.get("source_type") or "synthetic")
        title = str(
            record.get("title")
            or record.get("poi_name")
            or record.get("source_title")
            or doc_id
        )
        language = str(record.get("language") or "vi")
        source_lineage_id = str(record.get("source_lineage_id") or doc_id)
        return CanonicalDocument(
            document_id=doc_id,
            source_type=source_type,
            title=title,
            language=language,
            source_lineage_id=source_lineage_id,
            poi_id=record.get("poi_id"),
            city=record.get("city") or city_fallback,
            canonical_text_S=str(record["canonical_text_S"]),
            text_field_used="canonical_text_S",
            license=str(
                record.get("license")
                or (OSM_LICENSE if source_type == "osm_useful_structured" else "")
            ),
            attribution=str(
                record.get("attribution")
                or (OSM_ATTRIBUTION if source_type == "osm_useful_structured" else "")
            ),
            source_url=str(record.get("source_url") or ""),
            source_revision=record.get("source_revision"),
            metadata=extra_meta,
        )

    # Case 2: OSM payload
    is_osm = record.get("source_type") == "osm_useful_structured" or (
        ("sources" in record or isinstance(record.get("place"), dict))
        and "raw_text" not in record
        and "answer_ready_confirmed_text" not in record
    )
    if is_osm:
        if "content" in record and "sources" not in record and "place" not in record:
            content = str(record["content"])
            doc_id = str(record["document_id"])
            title = str(record.get("title") or record.get("name") or doc_id)
            return CanonicalDocument(
                document_id=doc_id,
                source_type="osm_useful_structured",
                title=title,
                language=str(record.get("language") or "vi"),
                source_lineage_id=str(record.get("source_lineage_id") or doc_id),
                poi_id=record.get("poi_id"),
                city=record.get("city") or city_fallback,
                canonical_text_S=content,
                text_field_used="osm_useful_structured.content",
                license=str(record.get("license") or OSM_LICENSE),
                attribution=str(record.get("attribution") or OSM_ATTRIBUTION),
                source_url=str(record.get("source_url") or ""),
                source_revision=record.get("source_revision"),
                metadata=extra_meta,
            )

        place = record.get("place", record)
        eff_city = record.get("city") or city_fallback
        content, osm_meta = build_osm_canonical_text(place, city_fallback=eff_city)
        pid = place.get("place_id") or place.get("id")
        doc_id = str(record.get("document_id") or f"osm-place-{pid}")
        source_type = str(record.get("source_type") or "osm_useful_structured")
        title = str(record.get("title") or place["name"])
        osm_source_id = osm_meta["source_id"]
        extra_meta.update(osm_meta)
        return CanonicalDocument(
            document_id=doc_id,
            source_type=source_type,
            title=title,
            language=str(record.get("language") or "vi"),
            source_lineage_id=str(
                record.get("source_lineage_id") or f"osm:{osm_source_id}"
            ),
            poi_id=record.get("poi_id") or pid,
            city=eff_city
            or place.get("destination")
            or place.get("destination_name"),
            canonical_text_S=content,
            text_field_used="osm_built_from_place",
            license=OSM_LICENSE,
            attribution=OSM_ATTRIBUTION,
            source_url=osm_meta["source_url"],
            source_revision=record.get("source_revision"),
            metadata=extra_meta,
        )

    # Case 3: B1B / generic document
    if record.get("answer_ready_confirmed_text") is not None:
        text_s = str(record["answer_ready_confirmed_text"])
        text_field_used = "answer_ready_confirmed_text"
    elif record.get("raw_text") is not None:
        text_s = str(record["raw_text"])
        text_field_used = "raw_text"
    else:
        raise ValueError(
            f"Corpus record {record.get('document_id')!r} missing canonical text field"
        )

    doc_id = str(record["document_id"])
    title = str(
        record.get("title")
        or record.get("poi_name")
        or record.get("source_title")
        or doc_id
    )
    return CanonicalDocument(
        document_id=doc_id,
        source_type=str(record.get("source_type") or "b1b"),
        title=title,
        language=str(record.get("language") or "vi"),
        source_lineage_id=str(record.get("source_lineage_id") or doc_id),
        poi_id=record.get("poi_id"),
        city=record.get("city") or city_fallback,
        canonical_text_S=text_s,
        text_field_used=text_field_used,
        license=str(
            record.get("license") or record.get("license_or_usage_class") or ""
        ),
        attribution=str(record.get("attribution") or ""),
        source_url=str(record.get("source_url") or ""),
        source_revision=record.get("source_revision"),
        metadata=extra_meta,
    )


def load_corpus_jsonl(path: Path) -> List[CanonicalDocument]:
    """Load corpus.jsonl deterministically, failing closed on malformed or duplicate docs."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Corpus file not found: {p}")
    raw_text = p.read_text(encoding="utf-8")
    docs: List[CanonicalDocument] = []
    seen_ids: set[str] = set()
    for line_no, line in enumerate(raw_text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {p}:{line_no}: {exc}") from exc
        if not isinstance(obj, dict):
            raise ValueError(f"Expected JSON object in {p}:{line_no}")
        doc = load_canonical_document(obj)
        if doc.document_id in seen_ids:
            raise ValueError(f"Duplicate document_id {doc.document_id!r} in {p}:{line_no}")
        seen_ids.add(doc.document_id)
        docs.append(doc)
    if not docs:
        raise ValueError(f"Corpus file is empty: {p}")
    return docs


def load_queries_jsonl(path: Path) -> List[QueryRecord]:
    """Load queries.jsonl deterministically, failing closed on missing keys or duplicates."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Queries file not found: {p}")
    raw_text = p.read_text(encoding="utf-8")
    queries: List[QueryRecord] = []
    seen_ids: set[str] = set()
    for line_no, line in enumerate(raw_text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {p}:{line_no}: {exc}") from exc
        if not isinstance(obj, dict):
            raise ValueError(f"Expected JSON object in {p}:{line_no}")
        if "query_id" not in obj or "query_text" not in obj:
            raise ValueError(f"Missing query_id or query_text in {p}:{line_no}")
        qid = str(obj["query_id"])
        qtext = str(obj["query_text"])
        if not qid or not qtext:
            raise ValueError(f"Empty query_id or query_text in {p}:{line_no}")
        if qid in seen_ids:
            raise ValueError(f"Duplicate query_id {qid!r} in {p}:{line_no}")
        seen_ids.add(qid)
        meta = {k: v for k, v in obj.items() if k not in ("query_id", "query_text")}
        queries.append(QueryRecord(query_id=qid, query_text=qtext, metadata=meta))
    if not queries:
        raise ValueError(f"Queries file is empty: {p}")
    return queries
