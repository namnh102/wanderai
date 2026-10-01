"""Deterministic entity resolution matching signals for places."""
import math
import unicodedata
import re


def normalize_vietnamese_text(text: str | None) -> str:
    """Normalizes text for comparison: lowercases, trims, and cleans punctuation."""
    if not text:
        return ""
    text = text.lower().strip()
    # Normalize unicode to NFC
    text = unicodedata.normalize("NFC", text)
    # Remove excessive punctuation
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def remove_vietnamese_accents(text: str) -> str:
    """Removes diacritics for phonetic/accent-insensitive comparison."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join([c for c in nfkd if not unicodedata.combining(c)])


def calculate_name_similarity(name1: str, name2: str) -> float:
    """Calculates string similarity using exact, token set, and accent-insensitive overlap."""
    n1 = normalize_vietnamese_text(name1)
    n2 = normalize_vietnamese_text(name2)

    if not n1 or not n2:
        return 0.0

    if n1 == n2:
        return 1.0

    # Token Jaccard similarity (both accented and unaccented)
    tokens1 = set(n1.split())
    tokens2 = set(n2.split())
    intersection = tokens1.intersection(tokens2)
    union = tokens1.union(tokens2)
    jaccard = len(intersection) / len(union) if union else 0.0

    # Accent-insensitive comparison
    unaccented1 = remove_vietnamese_accents(n1)
    unaccented2 = remove_vietnamese_accents(n2)
    if unaccented1 == unaccented2:
        return 0.95

    unacc_tokens1 = set(unaccented1.split())
    unacc_tokens2 = set(unaccented2.split())
    unacc_inter = unacc_tokens1.intersection(unacc_tokens2)
    unacc_union = unacc_tokens1.union(unacc_tokens2)
    unacc_jaccard = len(unacc_inter) / len(unacc_union) if unacc_union else 0.0
    sim = max(jaccard, unacc_jaccard)

    # Core place name overlap without common category words (e.g. "bãi biển", "beach", "chùa")
    place_stopwords = {
        "bai", "bien", "beach", "chua", "pagoda", "temple", "cau", "bridge",
        "khach", "san", "hotel", "resort", "quan", "nha", "hang", "restaurant",
        "cafe", "ca", "phe", "coffee", "ho", "lake", "nui", "mountain", "di",
        "tich", "bao", "tang", "museum", "cong", "vien", "park",
    }
    core1 = unacc_tokens1 - place_stopwords
    core2 = unacc_tokens2 - place_stopwords
    if core1 and core2:
        if core1 == core2:
            sim = max(sim, 0.90)
        elif core1.issubset(core2) or core2.issubset(core1):
            sim = max(sim, 0.85)

    return sim


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates great-circle distance between two points in meters."""
    R = 6371000  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def calculate_geo_similarity(lat1: float | None, lon1: float | None, lat2: float | None, lon2: float | None) -> float:
    """Computes geometric proximity score (0.0 to 1.0) based on distance."""
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return 0.5  # Neutral score when coordinates missing on one record

    dist_m = haversine_distance_meters(lat1, lon1, lat2, lon2)
    if dist_m <= 50:
        return 1.0
    elif dist_m <= 200:
        return 0.85
    elif dist_m <= 500:
        return 0.65
    elif dist_m <= 1000:
        return 0.35
    elif dist_m <= 2500:
        return 0.15
    return 0.0


def calculate_category_similarity(cat1: str | None, cat2: str | None) -> float:
    """Computes category taxonomy alignment."""
    if not cat1 or not cat2:
        return 0.5
    c1 = cat1.lower().strip()
    c2 = cat2.lower().strip()
    if c1 == c2:
        return 1.0

    # Compatible categories
    compatible_groups = [
        {"attraction", "culture", "nature"},
        {"restaurant", "cafe", "food"},
        {"hotel", "resort", "homestay"},
        {"beach", "nature", "attraction"},
    ]
    for group in compatible_groups:
        if c1 in group and c2 in group:
            return 0.6

    return 0.0


def compute_composite_match_score(
    p1: dict,
    p2: dict,
    weight_name: float = 0.50,
    weight_geo: float = 0.35,
    weight_cat: float = 0.15,
) -> float:
    """Computes multi-signal composite match score between two place candidates."""
    name_score = calculate_name_similarity(p1.get("name", ""), p2.get("name", ""))
    geo_score = calculate_geo_similarity(
        p1.get("latitude"), p1.get("longitude"),
        p2.get("latitude"), p2.get("longitude"),
    )
    cat_score = calculate_category_similarity(p1.get("category"), p2.get("category"))

    composite = (
        weight_name * name_score
        + weight_geo * geo_score
        + weight_cat * cat_score
    )
    return round(composite, 4)
