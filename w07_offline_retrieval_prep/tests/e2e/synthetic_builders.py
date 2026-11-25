"""100% self-contained pure-stdlib synthetic builders for opaque-box E2E tests.

Zero imports from `tests.fixtures.*`, `w07_retrieval.*`, or `w07_g4_scorer.*`.
Zero access to real 137-doc corpus, frozen eval manifests, or `<WANDERAI_REPO_ROOT>`.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

CITIES = ("Hà Nội", "Đà Nẵng", "Hạ Long")

# Exact Annex G1.5 v0.2.1 §D01 5x3 cell matrix (12/12/8/8/10; 17/17/16 = 50)
FINAL50_MATRIX_QUOTAS: Dict[Tuple[str, str], Tuple[int, str]] = {
    ("S1_STRUCTURED_FACT", "Hà Nội"): (4, "ANSWERABLE"),
    ("S1_STRUCTURED_FACT", "Đà Nẵng"): (4, "ANSWERABLE"),
    ("S1_STRUCTURED_FACT", "Hạ Long"): (4, "ANSWERABLE"),
    ("S2_NARRATIVE_ADVISORY", "Hà Nội"): (4, "ANSWERABLE"),
    ("S2_NARRATIVE_ADVISORY", "Đà Nẵng"): (4, "ANSWERABLE"),
    ("S2_NARRATIVE_ADVISORY", "Hạ Long"): (4, "ANSWERABLE"),
    ("S3_MULTI_EVIDENCE", "Hà Nội"): (3, "ANSWERABLE"),
    ("S3_MULTI_EVIDENCE", "Đà Nẵng"): (3, "ANSWERABLE"),
    ("S3_MULTI_EVIDENCE", "Hạ Long"): (2, "ANSWERABLE"),
    ("S4_CROSS_LINGUAL_VI_TO_EN", "Hà Nội"): (4, "ANSWERABLE"),
    ("S4_CROSS_LINGUAL_VI_TO_EN", "Đà Nẵng"): (3, "ANSWERABLE"),
    ("S4_CROSS_LINGUAL_VI_TO_EN", "Hạ Long"): (1, "ANSWERABLE"),
    ("S5_UNANSWERABLE_OR_UNSTABLE", "Hà Nội"): (2, "UNANSWERABLE"),
    ("S5_UNANSWERABLE_OR_UNSTABLE", "Đà Nẵng"): (3, "UNANSWERABLE"),
    ("S5_UNANSWERABLE_OR_UNSTABLE", "Hạ Long"): (5, "UNANSWERABLE"),
}

CATEGORY_LABEL_VI = {
    "attraction": "tham quan",
    "culture": "văn hóa",
    "beach": "biển",
    "nature": "thiên nhiên",
    "entertainment": "giải trí",
    "cafe": "quán cà phê",
    "restaurant": "nhà hàng",
    "hotel": "khách sạn",
}
CLASS_KEYS = ("tourism", "historic", "natural", "amenity", "leisure")
FACT_FIELDS = (
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


def make_b1b_doc(
    doc_id: str,
    title: str,
    canonical_text_S: Optional[str] = None,
    *,
    source_type: str = "wikipedia_article",
    language: str = "vi",
    source_lineage_id: Optional[str] = None,
    poi_id: Optional[str] = "syn-poi-hn-01",
    city: Optional[str] = "Hà Nội",
    answer_ready_confirmed_text: Optional[str] = None,
    raw_text: Optional[str] = None,
) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "document_id": doc_id,
        "source_type": source_type,
        "title": title,
        "language": language,
        "source_lineage_id": source_lineage_id or f"syn-lineage-{doc_id}",
        "poi_id": poi_id,
        "city": city,
    }
    if canonical_text_S is not None:
        row["canonical_text_S"] = canonical_text_S
    if answer_ready_confirmed_text is not None:
        row["answer_ready_confirmed_text"] = answer_ready_confirmed_text
    if raw_text is not None:
        row["raw_text"] = raw_text
    return row


def render_osm_canonical_text(
    name: str,
    *,
    category: str = "attraction",
    destination: str = "Hà Nội",
    tags: Optional[Dict[str, str]] = None,
    source_id: str = "node/900001",
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
) -> str:
    tags = tags or {}
    label = CATEGORY_LABEL_VI.get(category, category)
    head = name
    if tags.get("name:en") and tags["name:en"] != name:
        head += f" ({tags['name:en']})"
    head += f" thuộc nhóm {label}" if label else " là một địa điểm"
    if destination:
        head += f" tại {destination}"
    lines = [head + "."]

    klass = [f"{k}={tags[k]}" for k in CLASS_KEYS if tags.get(k)]
    if klass:
        lines.append("Loại OSM: " + ", ".join(klass) + ".")

    addr_parts: List[str] = []
    street, number = tags.get("addr:street"), tags.get("addr:housenumber")
    if street and number:
        addr_parts.append(f"{number} {street}")
    elif street:
        addr_parts.append(street)
    district = tags.get("addr:district") or tags.get("addr:suburb")
    if district:
        addr_parts.append(district)
    city = tags.get("addr:city") or tags.get("addr:province")
    if city:
        addr_parts.append(city)
    if addr_parts:
        lines.append(f"Địa chỉ: {', '.join(addr_parts)}.")

    if latitude is not None and longitude is not None:
        lines.append(f"Tọa độ: {latitude}, {longitude}.")

    for lbl, keys in FACT_FIELDS:
        for k in keys:
            if tags.get(k):
                lines.append(f"{lbl}: {tags[k]}.")
                break
    lines.append(f"Nguồn: OpenStreetMap {source_id}.")
    return "\n".join(lines)


def make_osm_doc(
    doc_id: str,
    name: str,
    *,
    category: str = "attraction",
    destination: str = "Hà Nội",
    tags: Optional[Dict[str, str]] = None,
    source_id: str = "node/900001",
    latitude: Optional[float] = 21.0285,
    longitude: Optional[float] = 105.8542,
    poi_id: Optional[str] = "syn-poi-osm-01",
    include_place_payload: bool = False,
) -> Dict[str, Any]:
    canonical = render_osm_canonical_text(
        name,
        category=category,
        destination=destination,
        tags=tags,
        source_id=source_id,
        latitude=latitude,
        longitude=longitude,
    )
    row: Dict[str, Any] = {
        "document_id": doc_id,
        "source_type": "osm_useful_structured",
        "title": name,
        "language": "vi",
        "source_lineage_id": f"osm:{source_id}",
        "poi_id": poi_id,
        "city": destination,
        "canonical_text_S": canonical,
    }
    if include_place_payload:
        row["place"] = {
            "id": poi_id or doc_id,
            "place_id": poi_id or doc_id,
            "name": name,
            "category": category,
            "destination": destination,
            "destination_name": destination,
            "latitude": latitude,
            "longitude": longitude,
            "sources": [
                {
                    "source_name": "osm",
                    "source_id": source_id,
                    "raw_data": {"tags": dict(tags or {})},
                }
            ],
        }
    return row


def make_overture_doc(
    doc_id: str,
    title: str,
    segments_and_tags: Sequence[Tuple[str, Optional[str]]],
    *,
    confidence: Optional[float] = 0.92,
    poi_id: Optional[str] = "syn-poi-ov-01",
    city: str = "Hà Nội",
    language: str = "vi",
    source_lineage_id: Optional[str] = None,
) -> Tuple[Dict[str, Any], List[Tuple[int, int]]]:
    """Build canonical S with exact [r_start, r_end) R_AUDIT spans from construction."""
    parts: List[str] = []
    removed_spans: List[Tuple[int, int]] = []
    cursor = 0
    for text_part, tag_part in segments_and_tags:
        if text_part:
            parts.append(text_part)
            cursor += len(text_part)
        if tag_part:
            r_start = cursor
            parts.append(tag_part)
            cursor += len(tag_part)
            removed_spans.append((r_start, cursor))
    if confidence is not None:
        conf_line = f"\nĐộ tin cậy bản ghi Overture (confidence): {confidence}."
        parts.append(conf_line)
    canonical_s = "".join(parts)
    doc = make_b1b_doc(
        doc_id,
        title,
        canonical_s,
        source_type="overture_places_parquet",
        language=language,
        source_lineage_id=source_lineage_id,
        poi_id=poi_id,
        city=city,
    )
    return doc, removed_spans


def make_multi_level_doc(
    doc_id: str,
    title: str,
    sections: Sequence[Tuple[int, str, str]],
    *,
    include_allowlisted_footer: bool = False,
    footer_title: str = "Xem thêm",
    include_non_allowlisted_empty: bool = False,
    city: str = "Đà Nẵng",
    poi_id: str = "syn-poi-dn-01",
    language: str = "vi",
) -> Dict[str, Any]:
    """Assemble wikitext sections `(level, heading, body)` into canonical S."""
    lines: List[str] = []
    for level, heading, body in sections:
        eq = "=" * level
        lines.append(f"{eq} {heading} {eq}")
        if body:
            lines.append(body)
    if include_allowlisted_footer:
        lines.append(f"== {footer_title} ==")
    if include_non_allowlisted_empty:
        lines.append("== Ghi chú riêng ==")
    canonical_s = "\n".join(lines)
    return make_b1b_doc(
        doc_id,
        title,
        canonical_s,
        source_type="wikipedia_article",
        language=language,
        poi_id=poi_id,
        city=city,
    )


def make_query_row(
    query_id: str,
    query_text: str,
    *,
    split: str = "DEV",
    creator_exposure_to_corpus: str = "NO",
    question_origin: str = "INDEPENDENT_HUMAN",
    query_family: str = "S1_STRUCTURED_FACT",
    target_city: str = "Hà Nội",
    pre_rank_answerability: str = "ANSWERABLE",
    scope_mode: str = "STRICT_TARGET_POI",
    target_poi_ids: Optional[List[str]] = None,
    query_intent_polarity: str = "AFFIRMATIVE_FACT_NEED",
    requested_facet_keywords: Optional[List[str]] = None,
    fact_cluster_id: Optional[str] = None,
    required_evidence_facets: Optional[Any] = None,
) -> Dict[str, Any]:
    pois = (
        ["syn-poi-hn-01"]
        if target_poi_ids is None and scope_mode == "STRICT_TARGET_POI"
        else (target_poi_ids if target_poi_ids is not None else [])
    )
    row: Dict[str, Any] = {
        "query_id": query_id,
        "query_text": query_text,
        "split": split,
        "creator_exposure_to_corpus": creator_exposure_to_corpus,
        "question_origin": question_origin,
        "query_family": query_family,
        "target_city": target_city,
        "pre_rank_answerability": pre_rank_answerability,
        "scope_mode": scope_mode,
        "target_poi_ids": pois,
        "query_intent_polarity": query_intent_polarity,
        "requested_facet_keywords": requested_facet_keywords or ["thông tin"],
        "fact_cluster_id": fact_cluster_id or f"fc-{query_id}",
    }
    if required_evidence_facets is not None:
        row["required_evidence_facets"] = required_evidence_facets
    return row


def make_5x3_query_matrix(
    *,
    split: str = "FINAL",
    question_origin: str = "INDEPENDENT_HUMAN",
) -> List[Dict[str, Any]]:
    """Build exact 50-query 5x3 Annex G1.5 D01 matrix (12/12/8/8/10; 17/17/16)."""
    rows: List[Dict[str, Any]] = []
    idx = 1
    city_code = {"Hà Nội": "hn", "Đà Nẵng": "dn", "Hạ Long": "hl"}
    for (family, city), (quota, ans) in FINAL50_MATRIX_QUOTAS.items():
        for k in range(quota):
            qid = f"Q-SYN-{idx:03d}"
            poi_id = f"syn-poi-{city_code[city]}-{(k % 6) + 1:02d}"
            rows.append(
                make_query_row(
                    qid,
                    f"Câu hỏi tổng hợp {idx} tại {city} thuộc nhóm {family}?",
                    split=split,
                    creator_exposure_to_corpus="NO",
                    question_origin=question_origin,
                    query_family=family,
                    target_city=city,
                    pre_rank_answerability=ans,
                    scope_mode="STRICT_TARGET_POI",
                    target_poi_ids=[poi_id],
                    query_intent_polarity="AFFIRMATIVE_FACT_NEED",
                    requested_facet_keywords=["giờ mở cửa", city],
                    fact_cluster_id=f"fc-syn-{idx:03d}",
                )
            )
            idx += 1
    assert len(rows) == 50
    return rows


def make_qrel_row(
    query_id: str,
    document_id: str,
    label: str = "REL_2",
    *,
    plausible_unsupported_lure: int = 0,
    evidence_s_spans: Optional[List[List[int]]] = None,
    source_lineage_id: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "query_id": query_id,
        "document_id": document_id,
        "label": label,
        "plausible_unsupported_lure": plausible_unsupported_lure,
        "evidence_s_spans": evidence_s_spans if evidence_s_spans is not None else [],
        "source_lineage_id": source_lineage_id,
    }


def make_judge_record(
    query_id: str,
    document_id: str,
    grade: str = "REL_2",
    *,
    evidence_quote: str = "",
    char_start: Optional[int] = None,
    char_end: Optional[int] = None,
    rationale: str = "synthetic verification",
) -> Dict[str, Any]:
    if grade in {"REL_0", "NA"}:
        cs_val = char_start
        ce_val = char_end
    else:
        cs_val = 0 if char_start is None else char_start
        ce_val = 0 if char_end is None else char_end
    return {
        "query_id": query_id,
        "document_id": document_id,
        "raw_json_str": json.dumps(
            {
                "grade": grade,
                "evidence_quote": evidence_quote,
                "char_start": cs_val,
                "char_end": ce_val,
                "rationale": rationale,
            },
            ensure_ascii=False,
        ),
    }


def make_judge_response_json(
    grade: str,
    *,
    evidence_quote: str = "",
    char_start: Any = None,
    char_end: Any = None,
    rationale: str = "synthetic",
    extra_fields: Optional[Dict[str, Any]] = None,
) -> str:
    payload: Dict[str, Any] = {
        "grade": grade,
        "evidence_quote": evidence_quote,
        "char_start": char_start,
        "char_end": char_end,
        "rationale": rationale,
    }
    if extra_fields:
        payload.update(extra_fields)
    return json.dumps(payload, ensure_ascii=False)


def find_span(canonical_text_S: str, substring: str) -> List[int]:
    start = canonical_text_S.index(substring)
    return [start, start + len(substring)]


def split_span_excluding_removed(
    start: int,
    end: int,
    removed_spans: Sequence[Tuple[int, int]],
) -> List[List[int]]:
    """Subtract deleted R_AUDIT intervals from [start, end) without outer hull."""
    cur: List[Tuple[int, int]] = [(start, end)]
    for ra, rb in sorted(removed_spans):
        nxt: List[Tuple[int, int]] = []
        for a, b in cur:
            if rb <= a or ra >= b:
                nxt.append((a, b))
            else:
                if a < ra:
                    nxt.append((a, ra))
                if rb < b:
                    nxt.append((rb, b))
        cur = nxt
    return [[a, b] for a, b in cur if a < b]


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(r, ensure_ascii=False) for r in rows]
    path.write_bytes(("\n".join(lines) + ("\n" if lines else "")).encode("utf-8"))
    return path


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected_packet_uuid(salt: str, query_id: str, document_id: str) -> str:
    return hmac.new(
        salt.encode("utf-8"),
        f"{query_id}::{document_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:32]


def tamper_one_byte(path: Path, *, dest_path: Optional[Path] = None) -> Path:
    """Flip 1 safe ASCII character byte in a JSON/JSONL/ZIP file."""
    target = dest_path or path
    data = bytearray(path.read_bytes())
    assert len(data) > 0, f"Cannot tamper empty file {path}"
    idx = len(data) // 2
    for offset in range(len(data)):
        pos = (idx + offset) % len(data)
        b = data[pos]
        if ord("a") <= b < ord("z"):
            data[pos] = b + 1
            break
        if ord("A") <= b < ord("Z"):
            data[pos] = b + 1
            break
        if ord("0") <= b < ord("9"):
            data[pos] = b + 1
            break
    else:
        data[0] ^= 0x01
    target.write_bytes(bytes(data))
    return target


def make_poison_pythonpath(
    tmp_path: Path,
    modules_to_poison: Sequence[str],
    *,
    mode: str = "exit99",
) -> Path:
    """Create a temporary directory with poison `.py` shims for opaque-box tests."""
    poison_dir = tmp_path / "poison_pythonpath"
    poison_dir.mkdir(parents=True, exist_ok=True)
    if mode == "exit99":
        body = "raise SystemExit(99)\n"
    elif mode == "importerror":
        body = "raise ImportError('poisoned missing module')\n"
    elif mode == "runtimeerror":
        body = "raise RuntimeError('poisoned module load failure')\n"
    else:
        raise ValueError(f"Unknown poison mode: {mode}")

    for mod in modules_to_poison:
        parts = mod.split(".")
        if len(parts) == 1:
            (poison_dir / f"{parts[0]}.py").write_text(body, encoding="utf-8")
        else:
            pkg_dir = poison_dir / Path(*parts[:-1])
            pkg_dir.mkdir(parents=True, exist_ok=True)
            (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
            (pkg_dir / f"{parts[-1]}.py").write_text(body, encoding="utf-8")
    return poison_dir


def make_synthetic_sealed_rankings(
    doc_ids_by_cell_query: Dict[Tuple[str, str], List[Tuple[str, float]]],
    docs_by_id: Dict[str, Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Create a valid G3 sealed ranking JSONL payload + matching manifest."""
    rows: List[Dict[str, Any]] = []
    cells_seen: List[str] = []
    for (cell_id, query_id), ranked_docs in sorted(doc_ids_by_cell_query.items()):
        if cell_id not in cells_seen:
            cells_seen.append(cell_id)
        chunker, retriever = cell_id.split("-", 1)
        for rank_idx, (doc_id, score) in enumerate(ranked_docs, start=1):
            text_s = docs_by_id[doc_id].get("canonical_text_S", "")
            span = [[0, len(text_s)]] if text_s else []
            chunk_id = f"{doc_id}-c0"
            rows.append(
                {
                    "cell_id": cell_id,
                    "chunker": chunker,
                    "retriever": retriever,
                    "query_id": query_id,
                    "rank": rank_idx,
                    "document_id": doc_id,
                    "score": float(score),
                    "rep_chunk_id": chunk_id,
                    "rep_chunk_index": 0,
                    "assembled_text": text_s,
                    "assembled_segments": (
                        [
                            {
                                "kind": "CANONICAL_BODY_V",
                                "a_start": 0,
                                "a_end": len(text_s),
                                "v_start": 0,
                                "v_end": len(text_s),
                            }
                        ]
                        if text_s
                        else []
                    ),
                    "c_full_s_spans": span,
                    "c_vis_s_spans": span,
                    "leg_ranks": (
                        {"BM25": rank_idx, "Dense": rank_idx}
                        if retriever == "RRF"
                        else {retriever: rank_idx}
                    ),
                    "leg_rep_chunks": (
                        {
                            "BM25": {
                                "chunk_id": chunk_id,
                                "chunk_index": 0,
                                "score": float(score),
                            },
                            "Dense": {
                                "chunk_id": chunk_id,
                                "chunk_index": 0,
                                "score": float(score),
                            },
                        }
                        if retriever == "RRF"
                        else {
                            retriever: {
                                "chunk_id": chunk_id,
                                "chunk_index": 0,
                                "score": float(score),
                            }
                        }
                    ),
                }
            )
    manifest = {
        "rankings_file": "g3_sealed_rankings_v1.jsonl",
        "rankings_sha256": "",
        "row_count": len(rows),
        "cells": sorted(cells_seen),
        "snapshot_id": "e8f8c211226b894fcb81acc59f3b34ba3efd5f42",
    }
    return rows, manifest


def write_synthetic_sealed_rankings(
    out_dir: Path,
    doc_ids_by_cell_query: Dict[Tuple[str, str], List[Tuple[str, float]]],
    docs_by_id: Dict[str, Dict[str, Any]],
) -> Tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows, manifest = make_synthetic_sealed_rankings(doc_ids_by_cell_query, docs_by_id)
    rankings_path = out_dir / "g3_sealed_rankings_v1.jsonl"
    raw = "\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in rows) + "\n"
    rankings_path.write_bytes(raw.encode("utf-8"))
    manifest["rankings_sha256"] = sha256_file(rankings_path)
    manifest_path = out_dir / "g3_sealed_rankings_v1_manifest.json"
    manifest_path.write_bytes(
        (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    )
    return rankings_path, manifest_path


def build_tourism_workload_pack(variant: str) -> Dict[str, Any]:
    """Generate self-contained synthetic Vietnamese/English tourism packs for Tier 4."""
    if variant == "full_2x3":
        docs: List[Dict[str, Any]] = []
        ov1, rem1 = make_overture_doc(
            "syn-doc-hn-ov1",
            "Bảo tàng Lịch sử Quốc gia",
            [
                (
                    "Bảo tàng Lịch sử Quốc gia tại Hà Nội lưu giữ nhiều cổ vật quý giá ",
                    "[CORROBORATED: canonical_poi:12345678-1234-1234-1234-1234567890ab, osm:way/101, wikidata:Q1001, wikipedia:vi:Bảo_tàng, wikivoyage:en:Hanoi#See, osm_website_pointer:https://example.org/bt]",
                ),
                (" mở cửa từ 08:00 đến 17:00 hàng ngày.", None),
            ],
            confidence=0.94,
            poi_id="syn-poi-hn-01",
            city="Hà Nội",
        )
        docs.append(ov1)
        docs.append(
            make_multi_level_doc(
                "syn-doc-hn-wiki1",
                "Văn Miếu Quốc Tử Giám",
                [
                    (2, "Kiến trúc", ""),
                    (3, "Khuê Văn Các", "Khuê Văn Các xây dựng năm 1805 tại Hà Nội [1]."),
                    (2, "Tham khảo", "Giá vé tham quan 70.000 đồng [Gia Long]."),
                ],
                include_allowlisted_footer=True,
                footer_title="Xem thêm",
                city="Hà Nội",
                poi_id="syn-poi-hn-02",
            )
        )
        docs.append(
            make_osm_doc(
                "syn-doc-hn-osm1",
                "Hồ Hoàn Kiếm",
                category="nature",
                destination="Hà Nội",
                tags={"natural": "water", "opening_hours": "24/7", "wheelchair": "yes"},
                source_id="way/202",
                poi_id="syn-poi-hn-03",
            )
        )
        docs.append(
            make_b1b_doc(
                "syn-doc-hn-wv1",
                "Phố cổ Hà Nội",
                "Khu phố cổ Hà Nội nổi tiếng với ẩm thực phở bò 45.000 đồng và cà phê trứng.",
                source_type="wikivoyage_poi_listing",
                source_lineage_id="wikivoyage:en:Hanoi",
                poi_id="syn-poi-hn-04",
                city="Hà Nội",
            )
        )
        docs.append(
            make_b1b_doc(
                "syn-doc-hn-wv2",
                "Chợ Đồng Xuân",
                "Chợ Đồng Xuân nằm ở phía bắc khu phố cổ Hà Nội, mở cửa từ 06:00.",
                source_type="wikivoyage_poi_listing",
                source_lineage_id="wikivoyage:en:Hanoi",
                poi_id="syn-poi-hn-04",
                city="Hà Nội",
            )
        )
        docs.append(
            make_b1b_doc(
                "syn-doc-dn-en1",
                "Ba Na Hills Golden Bridge",
                "Sun World Ba Na Hills cable car operates from 07:30 to 21:00 daily in Da Nang.",
                source_type="wikipedia_article",
                language="en",
                poi_id="syn-poi-dn-01",
                city="Đà Nẵng",
            )
        )
        docs.append(
            make_osm_doc(
                "syn-doc-dn-osm1",
                "Cầu Rồng",
                category="attraction",
                destination="Đà Nẵng",
                tags={"tourism": "attraction", "opening_hours": "24/7"},
                source_id="node/303",
                poi_id="syn-poi-dn-02",
            )
        )
        docs.append(
            make_b1b_doc(
                "syn-doc-hl-en1",
                "Ha Long Bay Cruise",
                "Ha Long overnight cruise boarding gate opens at Tuan Chau port at 11:30 AM.",
                source_type="wikivoyage_poi_listing",
                language="en",
                poi_id="syn-poi-hl-01",
                city="Hạ Long",
            )
        )
        docs.append(
            make_b1b_doc(
                "syn-doc-hl-fc1",
                "Bãi Cháy Hạ Long",
                "Thông tin bãi biển Bãi Cháy. [CONFLICT: FC-001 tạm ẩn dữ liệu giá vé chưa đối soát].",
                source_type="overture_places_parquet",
                poi_id="syn-poi-hl-02",
                city="Hạ Long",
            )
        )
        for i in range(10, 19):
            city = CITIES[i % 3]
            docs.append(
                make_b1b_doc(
                    f"syn-doc-extra-{i}",
                    f"Điểm tham quan mẫu {i}",
                    f"Điểm tham quan mẫu {i} nằm tại trung tâm {city} phục vụ khách du lịch quanh năm.",
                    poi_id=f"syn-poi-ex-{i}",
                    city=city,
                )
            )

        queries = [
            make_query_row(
                "Q-T4-01",
                "Bảo tàng Lịch sử Quốc gia mở cửa mấy giờ?",
                query_family="S1_STRUCTURED_FACT",
                target_city="Hà Nội",
                target_poi_ids=["syn-poi-hn-01"],
                requested_facet_keywords=["08:00", "17:00"],
                required_evidence_facets=[
                    [{"document_id": "syn-doc-hn-ov1", "s_spans": [find_span(ov1["canonical_text_S"], "mở cửa từ 08:00 đến 17:00")]}]
                ],
            ),
            make_query_row(
                "Q-T4-02",
                "Khuê Văn Các xây dựng năm nào?",
                query_family="S2_NARRATIVE_ADVISORY",
                target_city="Hà Nội",
                target_poi_ids=["syn-poi-hn-02"],
                requested_facet_keywords=["1805"],
                required_evidence_facets=[
                    [{"document_id": "syn-doc-hn-wiki1", "s_spans": [find_span(docs[1]["canonical_text_S"], "Khuê Văn Các xây dựng năm 1805")]}]
                ],
            ),
            make_query_row(
                "Q-T4-03",
                "Hồ Hoàn Kiếm có lối đi xe lăn không?",
                query_family="S1_STRUCTURED_FACT",
                target_city="Hà Nội",
                target_poi_ids=["syn-poi-hn-03"],
                query_intent_polarity="BOOLEAN_ELIGIBILITY_OR_POLICY_CHECK",
                requested_facet_keywords=["xe lăn"],
                required_evidence_facets=[
                    [{"document_id": "syn-doc-hn-osm1", "s_spans": [find_span(docs[2]["canonical_text_S"], "Tiếp cận xe lăn: yes.")]}]
                ],
            ),
            make_query_row(
                "Q-T4-04",
                "Cáp treo Bà Nà Hills hoạt động giờ nào?",
                query_family="S4_CROSS_LINGUAL_VI_TO_EN",
                target_city="Đà Nẵng",
                target_poi_ids=["syn-poi-dn-01"],
                requested_facet_keywords=["07:30", "21:00"],
                required_evidence_facets=[
                    [{"document_id": "syn-doc-dn-en1", "s_spans": [find_span(docs[5]["canonical_text_S"], "07:30 to 21:00")]}]
                ],
            ),
            make_query_row(
                "Q-T4-05",
                "Giá vé tàu ngầm thám hiểm ở Hạ Long là bao nhiêu?",
                query_family="S5_UNANSWERABLE_OR_UNSTABLE",
                target_city="Hạ Long",
                pre_rank_answerability="UNANSWERABLE",
                target_poi_ids=["syn-poi-hl-02"],
                requested_facet_keywords=["giá vé", "tàu ngầm"],
            ),
        ]

        qrels: List[Dict[str, Any]] = []
        rel_map = {
            ("Q-T4-01", "syn-doc-hn-ov1"): (
                "REL_2",
                0,
                [find_span(ov1["canonical_text_S"], "mở cửa từ 08:00 đến 17:00")],
            ),
            ("Q-T4-02", "syn-doc-hn-wiki1"): (
                "REL_2",
                0,
                [find_span(docs[1]["canonical_text_S"], "Khuê Văn Các xây dựng năm 1805")],
            ),
            ("Q-T4-03", "syn-doc-hn-osm1"): (
                "REL_2",
                0,
                [find_span(docs[2]["canonical_text_S"], "Tiếp cận xe lăn: yes.")],
            ),
            ("Q-T4-04", "syn-doc-dn-en1"): (
                "REL_2",
                0,
                [find_span(docs[5]["canonical_text_S"], "07:30 to 21:00")],
            ),
            ("Q-T4-05", "syn-doc-hl-fc1"): ("REL_0", 1, []),
        }
        for q in queries:
            for d in docs:
                key = (q["query_id"], d["document_id"])
                lbl, lure, spans = rel_map.get(key, ("REL_0", 0, []))
                qrels.append(
                    make_qrel_row(
                        q["query_id"],
                        d["document_id"],
                        lbl,
                        plausible_unsupported_lure=lure,
                        evidence_s_spans=spans,
                        source_lineage_id=d["source_lineage_id"],
                    )
                )
        return {
            "docs": docs,
            "queries": queries,
            "qrels": qrels,
            "removed_spans": {"syn-doc-hn-ov1": [list(s) for s in rem1]},
        }

    raise ValueError(f"Unknown workload variant: {variant}")
