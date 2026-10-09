#!/usr/bin/env python3
"""DATA-02 / MVP-SCOPE-01 Da Nang OSM Parser, Normalizer & Quality Filter.

Parses raw Overpass JSON snapshot for Da Nang (v2).
Applies Ratified Taxonomy V1.1 and strict quality gates.
Produces normalized candidate POIs with zero inferred/fabricated values.
"""

import json
import logging
import math
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("danang_osm_normalizer")

# Canonical Da Nang locked bounding box
BOUNDS = {
    "min_lat": 15.95,
    "max_lat": 16.20,
    "min_lon": 107.95,
    "max_lon": 108.35
}

def map_taxonomy(tags: dict) -> tuple[str, str, str]:
    """Maps OSM tags to (Tier-1, Tier-2, Legacy Category) using Ratified Taxonomy V1.1.
    
    Returns (tier_1, tier_2, legacy_category) or (None, None, None) if unsupported.
    """
    # 1. Transport Hubs (ferry/boat terminal)
    if tags.get("amenity") == "ferry_terminal" or tags.get("boat_terminal") == "yes":
        return "TRANSPORT_HUBS", "boat_terminal", "attraction"

    # 2. Tourism
    tourism = tags.get("tourism")
    if tourism:
        if tourism == "zoo":
            return "NATURE_SCENERY", "zoo_wildlife", "park"
        elif tourism == "aquarium":
            return "ATTRACTIONS_LEISURE", "aquarium", "attraction"
        elif tourism == "theme_park":
            return "ATTRACTIONS_LEISURE", "theme_park_leisure", "entertainment"
        elif tourism == "museum":
            return "CULTURE_HERITAGE", "museum_gallery", "museum"
        elif tourism == "gallery":
            return "CULTURE_HERITAGE", "museum_gallery", "museum"
        elif tourism == "viewpoint":
            return "NATURE_SCENERY", "viewpoint_scenic", "attraction"
        elif tourism in ("hotel", "resort"):
            return "HOSPITALITY", "hotel_resort", "hotel"
        elif tourism in ("guest_house", "hostel"):
            return "HOSPITALITY", "homestay_hostel", "hotel"
        elif tourism == "attraction":
            return "ATTRACTIONS_LEISURE", "landmark_iconic", "attraction"

    # 3. Historic
    historic = tags.get("historic")
    if historic:
        if historic in ("monument", "memorial", "castle", "ruins", "archaeological_site", "city_gate"):
            return "CULTURE_HERITAGE", "historic_monument", "culture"

    # 4. Natural
    natural = tags.get("natural")
    if natural:
        if natural == "cave_entrance":
            return "NATURE_SCENERY", "cave_grotto", "attraction"
        elif natural == "beach":
            return "NATURE_SCENERY", "beach_coastal", "beach"

    # 5. Leisure
    leisure = tags.get("leisure")
    if leisure:
        if leisure == "park":
            return "NATURE_SCENERY", "park_garden", "park"
        elif leisure == "beach_resort":
            return "NATURE_SCENERY", "beach_coastal", "beach"

    # 6. Shop
    shop = tags.get("shop")
    if shop == "mall":
        return "SHOPPING_COMMERCE", "shopping_mall", "market"

    # 7. Place island
    place = tags.get("place")
    if place == "island":
        return "NATURE_SCENERY", "island_landmark", "attraction"

    # 8. Amenity
    amenity = tags.get("amenity")
    if amenity:
        if amenity == "marketplace":
            return "SHOPPING_COMMERCE", "traditional_market", "market"
        elif amenity == "place_of_worship":
            return "CULTURE_HERITAGE", "religious_temple", "temple"
        elif amenity == "cafe":
            return "FOOD_BEVERAGE", "cafe_tea", "cafe"
        elif amenity in ("bar", "pub", "nightclub"):
            return "ATTRACTIONS_LEISURE", "nightlife_entertainment", "nightlife"
        elif amenity == "fast_food":
            return "FOOD_BEVERAGE", "street_food_market", "restaurant"
        elif amenity in ("restaurant", "food_court"):
            cuisine = tags.get("cuisine", "").lower()
            name_lower = tags.get("name", "").lower()
            if "seafood" in cuisine or "hải sản" in name_lower or "seafood" in name_lower:
                return "FOOD_BEVERAGE", "seafood_dining", "restaurant"
            return "FOOD_BEVERAGE", "restaurant_dining", "restaurant"

    return None, None, None

def format_address(tags: dict) -> str | None:
    parts = []
    num = tags.get("addr:housenumber")
    street = tags.get("addr:street")
    ward = tags.get("addr:subdistrict") or tags.get("addr:ward")
    district = tags.get("addr:district")
    city = tags.get("addr:city")

    if num and street:
        parts.append(f"{num} {street}")
    elif street:
        parts.append(street)

    if ward:
        parts.append(ward)
    if district:
        parts.append(district)
    if city:
        parts.append(city)

    return ", ".join(parts) if parts else None

def parse_and_filter_danang(raw_json_path: Path) -> tuple[list[dict], dict]:
    with open(raw_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    osm_base = data.get("osm3s", {}).get("timestamp_osm_base", "UNKNOWN")
    elements = data.get("elements", [])
    raw_count = len(elements)

    accepted = []
    rejected_reasons = {}

    def reject(reason: str):
        rejected_reasons[reason] = rejected_reasons.get(reason, 0) + 1

    seen_source_ids = set()

    for el in elements:
        osm_type = el.get("type")
        osm_id = el.get("id")
        if not osm_type or not osm_id:
            reject("MISSING_OSM_IDENTITY")
            continue

        source_id = f"{osm_type}/{osm_id}"
        if source_id in seen_source_ids:
            reject("DUPLICATE_SOURCE_ID")
            continue

        # Coordinate extraction
        lat = el.get("lat")
        lon = el.get("lon")
        if lat is None or lon is None:
            center = el.get("center", {})
            lat = center.get("lat")
            lon = center.get("lon")

        if lat is None or lon is None:
            reject("MISSING_COORDINATES")
            continue

        # Bounding box check
        if not (BOUNDS["min_lat"] <= lat <= BOUNDS["max_lat"] and BOUNDS["min_lon"] <= lon <= BOUNDS["max_lon"]):
            reject("OUT_OF_BBOX")
            continue

        tags = el.get("tags", {})
        name = tags.get("name", "").strip()
        if not name or len(name) < 2:
            reject("MISSING_OR_SHORT_NAME")
            continue

        # Check for generic unnamed placeholders
        if name.lower() in ("unnamed", "chưa đặt tên", "nhà hàng", "khách sạn", "quán cà phê"):
            reject("GENERIC_PLACEHOLDER_NAME")
            continue

        # Place=island special filtering: must be a recognized named tourist island/landmark
        if tags.get("place") == "island":
            if "hòn" not in name.lower() and "đảo" not in name.lower() and "island" not in name.lower():
                reject("ISLAND_WITHOUT_LANDMARK_NAME")
                continue

        # Taxonomy mapping
        tier_1, tier_2, legacy_cat = map_taxonomy(tags)
        if not tier_1:
            reject("UNSUPPORTED_TAXONOMY_TAGS")
            continue

        # Address & contact fields
        address = format_address(tags)
        phone = tags.get("phone") or tags.get("contact:phone")
        website = tags.get("website") or tags.get("contact:website")
        opening_hours = tags.get("opening_hours")
        name_en = tags.get("name:en")

        seen_source_ids.add(source_id)

        record = {
            "source_name": "osm",
            "source_id": source_id,
            "osm_type": osm_type,
            "osm_id": osm_id,
            "osm_version": el.get("version"),
            "osm_changeset": el.get("changeset"),
            "osm_timestamp": el.get("timestamp"),
            "osm_base": osm_base,
            "name": name,
            "name_en": name_en,
            "latitude": round(lat, 7),
            "longitude": round(lon, 7),
            "tier_1": tier_1,
            "tier_2": tier_2,
            "legacy_category": legacy_cat,
            "address": address,
            "opening_hours": opening_hours,
            "phone": phone,
            "website": website,
            "rating": None,           # Strict invariant: zero fabricated rating
            "review_count": 0,        # Strict invariant: zero fake review count
            "raw_tags": tags,
            "region": "danang"
        }
        accepted.append(record)

    stats = {
        "region": "danang",
        "bbox": BOUNDS,
        "raw_elements": raw_count,
        "accepted_count": len(accepted),
        "rejected_total": raw_count - len(accepted),
        "rejected_reasons": rejected_reasons,
        "tier1_distribution": {},
        "tier2_distribution": {},
        "missing_fields": {
            "missing_address": sum(1 for r in accepted if not r["address"]),
            "missing_opening_hours": sum(1 for r in accepted if not r["opening_hours"]),
            "missing_phone": sum(1 for r in accepted if not r["phone"]),
            "missing_website": sum(1 for r in accepted if not r["website"]),
            "missing_name_en": sum(1 for r in accepted if not r["name_en"])
        }
    }

    for r in accepted:
        t1 = r["tier_1"]
        t2 = r["tier_2"]
        stats["tier1_distribution"][t1] = stats["tier1_distribution"].get(t1, 0) + 1
        stats["tier2_distribution"][t2] = stats["tier2_distribution"].get(t2, 0) + 1

    return accepted, stats

def main():
    repo_root = Path(__file__).resolve().parent.parent
    raw_file = repo_root / "data" / "raw" / "osm" / "danang_2026-10-07_v2.json"
    processed_dir = repo_root / "data" / "processed" / "osm"
    processed_dir.mkdir(parents=True, exist_ok=True)

    norm_file = processed_dir / "danang_normalized_v2.json"
    stats_file = processed_dir / "danang_normalization_quality_stats_v2.json"

    print("=" * 70)
    print("PARSING AND NORMALIZING DA NANG OSM DATA (V2)")
    print(f"Raw source:    {raw_file}")
    print(f"Target norm:   {norm_file}")
    print(f"Target stats:  {stats_file}")
    print("=" * 70)

    if not raw_file.exists():
        raise FileNotFoundError(f"Missing raw file: {raw_file}")

    accepted_pois, stats = parse_and_filter_danang(raw_file)

    with open(norm_file, "w", encoding="utf-8") as f:
        json.dump(accepted_pois, f, indent=2, ensure_ascii=False)

    with open(stats_file, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

    print(f"[PASS] Da Nang normalization complete:")
    print(f"       Raw elements:     {stats['raw_elements']}")
    print(f"       Accepted POIs:    {stats['accepted_count']}")
    print(f"       Rejected total:   {stats['rejected_total']}")
    print(f"       Rejected reasons: {stats['rejected_reasons']}")
    print(f"\nTier-1 Distribution:")
    for t1, count in sorted(stats["tier1_distribution"].items(), key=lambda x: -x[1]):
        pct = (count / stats["accepted_count"]) * 100
        print(f"  {t1:25s}: {count:5d} ({pct:5.1f}%)")

    print(f"\nMissing Field Distribution (Accepted POIs: {stats['accepted_count']}):")
    for f_name, f_cnt in stats["missing_fields"].items():
        pct = (f_cnt / stats["accepted_count"]) * 100
        print(f"  {f_name:25s}: {f_cnt:5d} ({pct:5.1f}%)")

if __name__ == "__main__":
    main()
