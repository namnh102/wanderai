"""GoMate REC-A Recommender Feature Contract and Representation Module.

Authoritative specification based on:
- docs/recommendation/gomate-reca-feature-contract-v1.md
- WP-PROF-01 Canonical Preferences
- Taxonomy V1.1
"""

import math
import unicodedata
from typing import Dict, List, Tuple, Any, Optional

CANONICAL_INTERESTS = [
    "food_cuisine",
    "culture_history",
    "nature_outdoor",
    "coffee_culture",
    "beach_island",
    "shopping_local",
    "nightlife_entertainment",
]

INTEREST_INDEX = {k: i for i, k in enumerate(CANONICAL_INTERESTS)}

INTEREST_LABELS_VI = {
    "food_cuisine": "ẩm thực & đặc sản",
    "culture_history": "văn hóa & lịch sử",
    "nature_outdoor": "thiên nhiên & dã ngoại",
    "coffee_culture": "văn hóa cà phê & trà",
    "beach_island": "biển đảo & nghỉ dưỡng",
    "shopping_local": "mua sắm & chợ địa phương",
    "nightlife_entertainment": "giải trí & đời sống về đêm",
}

UNSUPPORTED_USER_FEATURES = [
    {
        "feature": "travelStyle",
        "status": "AVAILABLE_USER_FEATURE_NOT_USED_IN_V1",
        "reason": "No validated POI-side travel-style compatibility signal exists in Dataset Freeze V2.",
    },
    {
        "feature": "budgetMin",
        "status": "AVAILABLE_USER_FEATURE_NOT_USED_IN_V1",
        "reason": "POI price data is not reliably standardized in OSM/Overture factual dataset.",
    },
    {
        "feature": "budgetMax",
        "status": "AVAILABLE_USER_FEATURE_NOT_USED_IN_V1",
        "reason": "POI price data is not reliably standardized in OSM/Overture factual dataset.",
    },
    {
        "feature": "preferredGroup",
        "status": "AVAILABLE_USER_FEATURE_NOT_USED_IN_V1",
        "reason": "Group dynamics and party size constraints are not modeled in REC-A baseline.",
    },
    {
        "feature": "avoidances",
        "status": "AVAILABLE_USER_FEATURE_NOT_USED_IN_V1",
        "reason": "Negative preference filtering is deferred to post-filtering in later milestones.",
    },
    {
        "feature": "dietaryNeeds",
        "status": "AVAILABLE_USER_FEATURE_NOT_USED_IN_V1",
        "reason": "Detailed dietary certification is not universally populated in OSM nodes.",
    },
]

DESTINATION_SLUG_MAP = {
    "ha-noi": "ha-noi",
    "hanoi": "ha-noi",
    "hà nội": "ha-noi",
    "ha_noi": "ha-noi",
    "hn": "ha-noi",
    "da-nang": "da-nang",
    "danang": "da-nang",
    "đà nẵng": "da-nang",
    "da_nang": "da-nang",
    "dn": "da-nang",
    "ha-long": "ha-long",
    "halong": "ha-long",
    "hạ long": "ha-long",
    "ha_long": "ha-long",
    "hl": "ha-long",
}


def normalize_string(s: str) -> str:
    """Normalize string for deterministic comparison (lowercase, unaccented, stripped)."""
    if not s:
        return ""
    nfkd = unicodedata.normalize("NFKD", s)
    unaccented = "".join([c for c in nfkd if not unicodedata.combining(c)])
    return " ".join(unaccented.lower().split())


def normalize_destination(destination: Optional[str]) -> Optional[str]:
    """Map destination input to canonical destination slug or None if not recognized/empty."""
    if not destination:
        return None
    raw = destination.strip().lower()
    return DESTINATION_SLUG_MAP.get(raw, DESTINATION_SLUG_MAP.get(normalize_string(raw)))


def extract_poi_taxonomy(poi: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any]]:
    """Extract (tier_1, tier_2, tags) from a canonical POI dict."""
    osm_source = next((s for s in poi.get("sources", []) if s.get("source_name") == "osm"), None)
    rd = osm_source.get("raw_data", {}) if osm_source else {}
    t1 = rd.get("tier_1")
    t2 = rd.get("tier_2")
    tags = rd.get("tags") or {}

    if t1 and t2:
        return str(t1), str(t2), tags

    # Deterministic fallback from tags or category if not populated in raw_data
    cat = (poi.get("category") or "").lower()
    if tags.get("amenity") == "cafe" or cat == "cafe":
        return "FOOD_BEVERAGE", "cafe_tea", tags
    if tags.get("amenity") in ("restaurant", "fast_food", "food_court") or cat in ("restaurant", "food"):
        cuisine = tags.get("cuisine", "")
        if "seafood" in cuisine:
            return "FOOD_BEVERAGE", "seafood_dining", tags
        return "FOOD_BEVERAGE", "restaurant_dining", tags
    if tags.get("tourism") == "museum" or cat == "museum":
        return "CULTURE_HERITAGE", "museum_gallery", tags
    if tags.get("amenity") == "place_of_worship" or cat == "temple":
        return "CULTURE_HERITAGE", "religious_temple", tags
    if tags.get("historic") or cat == "culture":
        return "CULTURE_HERITAGE", "historic_monument", tags
    if tags.get("natural") == "beach" or cat == "beach":
        return "NATURE_SCENERY", "beach_coastal", tags
    if tags.get("place") == "island":
        return "NATURE_SCENERY", "island_landmark", tags
    if tags.get("leisure") == "park" or cat in ("nature", "park"):
        return "NATURE_SCENERY", "park_garden", tags
    if tags.get("shop") == "mall":
        return "SHOPPING_COMMERCE", "shopping_mall", tags
    if tags.get("amenity") == "marketplace" or cat == "market":
        return "SHOPPING_COMMERCE", "traditional_market", tags
    if tags.get("tourism") == "theme_park" or tags.get("leisure") == "water_park":
        return "ATTRACTIONS_LEISURE", "theme_park_leisure", tags
    if tags.get("amenity") in ("bar", "pub", "nightclub") or cat == "nightlife":
        return "ATTRACTIONS_LEISURE", "nightlife_entertainment", tags
    if tags.get("tourism") == "hotel" or cat == "hotel":
        return "HOSPITALITY", "hotel_resort", tags
    if tags.get("amenity") == "ferry_terminal":
        return "TRANSPORT_HUBS", "boat_terminal", tags

    return "ATTRACTIONS_LEISURE", "attraction", tags


def poi_to_canonical_vector(poi: Dict[str, Any]) -> Tuple[List[float], List[str]]:
    """Convert a canonical POI into a 7-dimensional interest feature vector.

    Strictly reconciled with gomate-reca-feature-contract-v1.md.
    No heuristic feature invention.
    Hospitality has no activity feature mapping in REC-A V1.

    Returns:
        (vector, matched_taxonomy_domains)
    """
    t1, t2, tags = extract_poi_taxonomy(poi)
    vec = [0.0] * len(CANONICAL_INTERESTS)
    matched_tax = []

    # 1. food_cuisine: restaurant_dining, street_food, street_food_market, seafood_dining
    if t2 in ("restaurant_dining", "street_food", "street_food_market", "seafood_dining"):
        vec[INTEREST_INDEX["food_cuisine"]] = 1.0
        matched_tax.append("FOOD_BEVERAGE")

    # 2. coffee_culture: cafe_tea
    # Do NOT automatically classify cafe_tea as food_cuisine unless trusted taxonomy explicitly represents a dining subtype.
    if t2 == "cafe_tea":
        vec[INTEREST_INDEX["coffee_culture"]] = 1.0
        matched_tax.append("FOOD_BEVERAGE")
        cuisine_tag = str(tags.get("cuisine", "")).lower()
        amenity_tag = str(tags.get("amenity", "")).lower()
        if amenity_tag == "restaurant" or "restaurant" in cuisine_tag or "dining" in cuisine_tag:
            vec[INTEREST_INDEX["food_cuisine"]] = 1.0

    # 3. culture_history: valid CULTURE_HERITAGE mappings from contract
    if t1 == "CULTURE_HERITAGE" or t2 in ("temple_pagoda", "religious_temple", "museum_gallery", "historic_monument", "heritage_craft"):
        vec[INTEREST_INDEX["culture_history"]] = 1.0
        matched_tax.append("CULTURE_HERITAGE")

    # 4. nature_outdoor: park_garden, cave_grotto, lake_river, zoo_wildlife, scenic_viewpoint, viewpoint_scenic
    if t2 in ("park_garden", "cave_grotto", "lake_river", "zoo_wildlife", "scenic_viewpoint", "viewpoint_scenic"):
        vec[INTEREST_INDEX["nature_outdoor"]] = 1.0
        matched_tax.append("NATURE_SCENERY")

    # 5. beach_island: beach_coastal, island_landmark
    if t2 in ("beach_coastal", "island_landmark"):
        vec[INTEREST_INDEX["beach_island"]] = 1.0
        matched_tax.append("NATURE_SCENERY")

    # 6. shopping_local: traditional_market, shopping_mall, souvenir_craft
    if t2 in ("traditional_market", "shopping_mall", "souvenir_craft"):
        vec[INTEREST_INDEX["shopping_local"]] = 1.0
        matched_tax.append("SHOPPING_COMMERCE")

    # 7. nightlife_entertainment: nightlife_entertainment
    # Do NOT automatically classify every ATTRACTIONS_LEISURE POI (e.g. landmark_iconic, theme_park_leisure, attraction) as nightlife.
    if t2 == "nightlife_entertainment":
        vec[INTEREST_INDEX["nightlife_entertainment"]] = 1.0
        matched_tax.append("ATTRACTIONS_LEISURE")

    # HOSPITALITY: audited and removed - no contract-backed activity feature in REC-A V1.
    # Result for pure hotels is [0.0]*7.

    matched_tax = list(dict.fromkeys(matched_tax))
    return vec, matched_tax


def user_to_canonical_vector(interests: Optional[List[str]]) -> List[float]:
    """Convert user canonical interests list into a 7-dimensional multi-hot vector."""
    vec = [0.0] * len(CANONICAL_INTERESTS)
    if not interests:
        return vec
    for item in interests:
        if isinstance(item, str):
            clean = item.strip().lower()
            if clean in INTEREST_INDEX:
                vec[INTEREST_INDEX[clean]] = 1.0
    return vec


def l2_norm(vec: List[float]) -> float:
    """Compute Euclidean (L2) norm of a vector."""
    return math.sqrt(sum(x * x for x in vec))


def cosine_similarity(u: List[float], v: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(a * b for a, b in zip(u, v))
    norm_u = l2_norm(u)
    norm_v = l2_norm(v)
    if norm_u == 0.0 or norm_v == 0.0:
        return 0.0
    return dot / (norm_u * norm_v)
