#!/usr/bin/env python3
"""DATA-02 OSM Parser, Normalizer & Quality Filter.

Parses raw Overpass JSON snapshots for Hanoi and Ha Long.
Applies Ratified Taxonomy V1.1 and strict quality filters.
Produces normalized candidate POIs with zero inferred/fabricated values.
"""

import json
import logging
import math
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("osm_normalizer")

# Canonical MVP bounding boxes
BOUNDS = {
    "hanoi": {"min_lat": 20.95, "max_lat": 21.15, "min_lon": 105.75, "max_lon": 105.95},
    "halong": {"min_lat": 20.85, "max_lat": 21.05, "min_lon": 106.95, "max_lon": 107.25}
}

def map_taxonomy(tags: dict) -> tuple[str, str, str]:
    """Maps OSM tags to (Tier-1, Tier-2, Legacy Category) using Ratified Taxonomy V1.1.
    
    Returns (tier_1, tier_2, legacy_category) or (None, None, None) if unsupported.
    """
    # 1. Transport Hubs (boat terminals)
    if tags.get("amenity") == "ferry_terminal" or tags.get("boat_terminal") == "yes":
        return "TRANSPORT_HUBS", "boat_terminal", "attraction"  # legacy fallback attraction

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

def parse_and_filter_region(region: str, raw_json_path: Path) -> tuple[list[dict], dict]:
    bounds = BOUNDS[region]
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
        if not (bounds["min_lat"] <= lat <= bounds["max_lat"] and bounds["min_lon"] <= lon <= bounds["max_lon"]):
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
            # Must not be an entire massive bay or unnamed islet
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
            "region": region
        }
        accepted.append(record)

    stats = {
        "region": region,
        "raw_elements": raw_count,
        "accepted_count": len(accepted),
        "rejected_total": raw_count - len(accepted),
        "rejected_reasons": rejected_reasons,
        "category_distribution": {},
        "tier1_distribution": {}
    }

    for r in accepted:
        t1 = r["tier_1"]
        t2 = r["tier_2"]
        stats["tier1_distribution"][t1] = stats["tier1_distribution"].get(t1, 0) + 1
        stats["category_distribution"][t2] = stats["category_distribution"].get(t2, 0) + 1

    return accepted, stats

def run_normalization():
    repo_root = Path(__file__).resolve().parent.parent
    raw_dir = repo_root / "data" / "raw" / "osm"
    processed_dir = repo_root / "data" / "processed" / "osm"
    processed_dir.mkdir(parents=True, exist_ok=True)

    today = "2026-10-07"
    all_stats = {}

    for region in ("hanoi", "halong"):
        raw_path = raw_dir / f"{region}_{today}.json"
        print("=" * 70)
        print(f"NORMALIZING & QUALITY FILTERING: {region.upper()}")
        print(f"Raw Input: {raw_path}")
        print("=" * 70)

        accepted, stats = parse_and_filter_region(region, raw_path)
        out_path = processed_dir / f"{region}_normalized_v1.json"

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(accepted, f, indent=2, ensure_ascii=False)

        all_stats[region] = stats
        print(f"[PASS] {region.upper()} Normalized Output Saved:")
        print(f"       File:     {out_path.relative_to(repo_root)}")
        print(f"       Raw:      {stats['raw_elements']}")
        print(f"       Accepted: {stats['accepted_count']}")
        print(f"       Rejected: {stats['rejected_total']}")
        print("       Tier-1 Breakdown:")
        for k, v in sorted(stats['tier1_distribution'].items()):
            print(f"         - {k:<22}: {v}")
        print("       Rejected Reasons:")
        for k, v in sorted(stats['rejected_reasons'].items()):
            print(f"         - {k:<25}: {v}")

    stats_path = processed_dir / f"normalization_quality_stats_{today}.json"
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(all_stats, f, indent=2, ensure_ascii=False)
    print(f"\nOverall quality stats written to: {stats_path.relative_to(repo_root)}")

if __name__ == "__main__":
    run_normalization()
