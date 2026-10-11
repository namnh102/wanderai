"""OSM place knowledge documents (TASK 07.5).

Builds RAG chunks ONLY from metadata that exists in OpenStreetMap (the tags stored in
``place_sources.raw_data``) and from the place row itself (name, category, coordinates, destination).
Missing attributes are omitted; nothing is inferred, defaulted or invented (no ratings, no opening hours,
no descriptions that are not in OSM).
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.rag.chunker import RAGChunk, SectionAwareChunker

OSM_LICENSE = "ODbL 1.0"
OSM_ATTRIBUTION = "© OpenStreetMap contributors"

# Vietnamese label of OUR category taxonomy (not an OSM claim).
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

# OSM keys that describe what the object is.
CLASS_KEYS = ("tourism", "historic", "natural", "amenity", "leisure")

# (label, candidate OSM keys) - first present key wins; value is copied verbatim.
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


def _tags(raw: Any) -> Dict[str, str]:
    if isinstance(raw, str):
        import json

        raw = json.loads(raw)
    return {k: str(v) for k, v in (raw or {}).items() if not k.startswith("_") and str(v).strip()}


def format_osm_address(tags: Dict[str, str]) -> str:
    """Address only from addr:* tags (never from a placeholder)."""
    parts = []
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


def osm_source_url(source_id: str) -> str:
    return f"https://www.openstreetmap.org/{source_id}"


def _parse_ts(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def build_osm_place_chunk(place: Dict[str, Any]) -> Optional[RAGChunk]:
    """place: id, name, category, destination_id, destination_name, latitude, longitude,
    sources: [{source_name, source_id, raw_data, created_at}]. Returns None for places without an OSM source."""
    osm_sources = sorted(
        (s for s in place.get("sources", []) if s.get("source_name") == "osm"),
        key=lambda s: s["source_id"],
    )
    if not osm_sources:
        return None  # never ingest a place without verified provenance
    src = osm_sources[0]
    tags = _tags(src.get("raw_data"))
    raw_data = src.get("raw_data") or {}
    if isinstance(raw_data, str):
        import json

        raw_data = json.loads(raw_data)

    name = place["name"]
    category = place.get("category") or ""
    label = CATEGORY_LABEL_VI.get(category, category)

    head = name
    if tags.get("name:en") and tags["name:en"] != name:
        head += f" ({tags['name:en']})"
    head += f" thuộc nhóm {label}" if label else " là một địa điểm"
    if place.get("destination_name"):
        head += f" tại {place['destination_name']}"
    lines: List[str] = [head + "."]

    klass = [f"{k}={tags[k]}" for k in CLASS_KEYS if tags.get(k)]
    if klass:
        lines.append("Loại OSM: " + ", ".join(klass) + ".")
    address = format_osm_address(tags)
    if address:
        lines.append(f"Địa chỉ: {address}.")
    if place.get("latitude") is not None and place.get("longitude") is not None:
        lines.append(f"Tọa độ: {place['latitude']}, {place['longitude']}.")

    used = []
    for lbl, keys in FACT_FIELDS:
        for k in keys:
            if tags.get(k):
                lines.append(f"{lbl}: {tags[k]}.")
                used.append(k)
                break
    lines.append(f"Nguồn: OpenStreetMap {src['source_id']}.")
    content = "\n".join(lines)

    retrieved_at = _parse_ts(raw_data.get("_osm_base_timestamp")) or _parse_ts(src.get("created_at"))
    doc_id = f"osm-place-{place['id']}"
    return RAGChunk(
        chunk_id=doc_id,
        document_id=doc_id,
        title=name,
        section_heading=category or "place",
        topic="attractions",
        content=content,
        content_hash=SectionAwareChunker.compute_hash(content),
        source_name="osm",
        source_url=osm_source_url(src["source_id"]),
        license=OSM_LICENSE,
        attribution=OSM_ATTRIBUTION,
        language="vi",
        destination_id=place.get("destination_id"),
        place_id=place["id"],
        category=category or None,
        metadata={
            "source_type": "osm_place",
            "source_id": src["source_id"],
            "osm_base_timestamp": raw_data.get("_osm_base_timestamp"),
            "osm_tags_used": sorted(used),
        },
        retrieved_at=retrieved_at,
    )
