"""Parses raw OSM Overpass JSON and produces normalized travel POI records."""
import json
import logging
from pathlib import Path
try:
    from config import VIETNAM_BBOX, OSM_TAG_CATEGORY_MAP
except ImportError:
    from data.pipelines.osm.config import VIETNAM_BBOX, OSM_TAG_CATEGORY_MAP

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("osm_parser")


def is_valid_coordinate(lat: float | None, lon: float | None) -> bool:
    """Verifies that coordinates are within Vietnam bounding box."""
    if lat is None or lon is None:
        return False
    return (
        VIETNAM_BBOX["min_lat"] <= lat <= VIETNAM_BBOX["max_lat"]
        and VIETNAM_BBOX["min_lon"] <= lon <= VIETNAM_BBOX["max_lon"]
    )


def map_category(tags: dict) -> str:
    """Maps OSM tags to standard GoMate category."""
    for (k, v), category in OSM_TAG_CATEGORY_MAP.items():
        if tags.get(k) == v:
            return category
    if "tourism" in tags:
        return "attraction"
    if "amenity" in tags and "restaurant" in tags["amenity"]:
        return "restaurant"
    return "attraction"


def format_address(tags: dict) -> str:
    """Combines street, housenumber, district, city into a formatted address."""
    parts = []
    street = tags.get("addr:street")
    housenumber = tags.get("addr:housenumber")
    if housenumber and street:
        parts.append(f"{housenumber} {street}")
    elif street:
        parts.append(street)

    district = tags.get("addr:district") or tags.get("addr:suburb")
    if district:
        parts.append(district)

    city = tags.get("addr:city") or tags.get("addr:province")
    if city:
        parts.append(city)

    return ", ".join(parts) if parts else ""


def parse_single_osm_element(el: dict) -> dict | None:
    """Parses a single raw OSM element into a normalized record, or None if invalid."""
    tags = el.get("tags", {})
    name = tags.get("name", "").strip()

    if not name:
        return None

    lat = el.get("lat")
    lon = el.get("lon")
    if lat is None and "center" in el:
        lat = el["center"].get("lat")
        lon = el["center"].get("lon")

    if not is_valid_coordinate(lat, lon):
        return None

    source_type = el.get("type", "node")
    source_id = f"{source_type}/{el.get('id')}"
    category = map_category(tags)
    address = format_address(tags)
    city = tags.get("addr:city") or tags.get("addr:province") or el.get("_region", "")

    return {
        "source_name": "osm",
        "source_id": source_id,
        "raw_name": name,
        "name": name,
        "name_en": tags.get("name:en"),
        "category": category,
        "address": address or f"{name}, {city}".strip(", "),
        "city": city,
        "latitude": round(lat, 6),
        "longitude": round(lon, 6),
        "raw_data": tags,
    }


def parse_osm_elements(raw_json_path: Path, output_path: Path) -> list[dict]:
    """Parses raw OSM JSON and extracts standardized place records."""
    if not raw_json_path.exists():
        raise FileNotFoundError(f"Raw OSM file not found: {raw_json_path}")

    with open(raw_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    elements = data.get("elements", [])
    logger.info(f"Parsing {len(elements)} raw elements from {raw_json_path}...")

    normalized_places = []
    skipped_count = 0

    for el in elements:
        record = parse_single_osm_element(el)
        if record:
            normalized_places.append(record)
        else:
            skipped_count += 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(normalized_places, f, ensure_ascii=False, indent=2)

    logger.info(
        f"Parsed {len(normalized_places)} normalized places. (Skipped {skipped_count} invalid records). "
        f"Saved to {output_path}"
    )
    return normalized_places


if __name__ == "__main__":
    raw_file = Path(__file__).parent.parent.parent / "raw" / "osm_vietnam_sample.json"
    proc_file = Path(__file__).parent.parent.parent / "processed" / "osm_places.json"
    parse_osm_elements(raw_file, proc_file)
