"""Links normalized reviews to canonical places using multi-signal matching."""
import json
import logging
from pathlib import Path
import uuid
import sys

# Ensure pipelines can import sibling modules
current_dir = Path(__file__).resolve().parent
root_dir = current_dir.parent.parent
sys.path.insert(0, str(root_dir))

try:
    from data.pipelines.entity_resolution.matcher import (
        calculate_name_similarity,
        normalize_vietnamese_text,
        remove_vietnamese_accents,
    )
except ImportError:
    from pipelines.entity_resolution.matcher import (  # type: ignore
        calculate_name_similarity,
        normalize_vietnamese_text,
        remove_vietnamese_accents,
    )

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("review_linker")

AUTO_LINK_THRESHOLD = 0.85
REVIEW_QUEUE_THRESHOLD = 0.60


def city_matches(city_query: str, place_city: str, place_address: str) -> bool:
    """Checks if city names or regions match loosely."""
    q = remove_vietnamese_accents(normalize_vietnamese_text(city_query))
    pc = remove_vietnamese_accents(normalize_vietnamese_text(place_city))
    pa = remove_vietnamese_accents(normalize_vietnamese_text(place_address))

    if not q:
        return True
    return q in pc or pc in q or q in pa


def find_best_place_match(review_target_name: str, city_hint: str, canonical_places: list[dict]) -> tuple[dict | None, float]:
    """Finds best matching canonical place for a given target place name."""
    best_place = None
    best_score = 0.0

    target_norm = normalize_vietnamese_text(review_target_name)

    for place in canonical_places:
        place_name = place.get("name", "")
        name_sim = calculate_name_similarity(review_target_name, place_name)

        # Check alternative raw names from sources
        for src in place.get("sources", []):
            raw_name = src.get("raw_name", "")
            raw_sim = calculate_name_similarity(review_target_name, raw_name)
            if raw_sim > name_sim:
                name_sim = raw_sim

        # City alignment bonus/penalty
        c_match = city_matches(city_hint, place.get("city", ""), place.get("address", ""))
        composite_score = name_sim * (1.0 if c_match else 0.75)

        if composite_score > best_score:
            best_score = composite_score
            best_place = place

    return best_place, round(best_score, 4)


def link_reviews_dataset(
    reviews_path: Path,
    places_path: Path,
    output_path: Path,
) -> dict:
    """Links normalized reviews to canonical places and writes curated dataset."""
    with open(reviews_path, "r", encoding="utf-8") as f:
        reviews = json.load(f)

    with open(places_path, "r", encoding="utf-8") as f:
        places = json.load(f)

    logger.info(f"Loaded {len(reviews)} normalized reviews and {len(places)} canonical places.")

    curated_reviews = []
    stats = {
        "total_reviews": len(reviews),
        "linked": 0,
        "review_queue": 0,
        "unmatched": 0,
    }

    for rev in reviews:
        target_name = rev.get("place_name_target", "")
        city_hint = rev.get("city", "")

        matched_place, confidence = find_best_place_match(target_name, city_hint, places)

        if confidence >= AUTO_LINK_THRESHOLD and matched_place:
            status = "linked"
            place_id = matched_place["id"]
            stats["linked"] += 1
        elif confidence >= REVIEW_QUEUE_THRESHOLD and matched_place:
            status = "review_queue"
            place_id = matched_place["id"]
            stats["review_queue"] += 1
        else:
            status = "unmatched"
            place_id = None
            stats["unmatched"] += 1

        curated_rec = {
            "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"gomate.review.{rev.get('source_review_id')}")),
            "place_id": place_id,
            "place_name_matched": matched_place["name"] if matched_place else None,
            "target_name_raw": target_name,
            "city": city_hint,
            "rating": rev.get("rating", 5.0),
            "content": rev.get("content", ""),
            "aspects": rev.get("aspects", []),
            "source_review_id": rev.get("source_review_id", ""),
            "source_name": "academic_benchmark",
            "match_confidence": confidence,
            "match_status": status,
        }
        curated_reviews.append(curated_rec)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(curated_reviews, f, ensure_ascii=False, indent=2)

    logger.info(
        f"Review linking complete: {stats['linked']} auto-linked, "
        f"{stats['review_queue']} in review queue, {stats['unmatched']} unmatched."
    )
    return {"stats": stats, "records": curated_reviews}


if __name__ == "__main__":
    proc_reviews = Path(__file__).parent.parent.parent / "processed" / "reviews_normalized.json"
    canonical_places = Path(__file__).parent.parent.parent / "curated" / "places_canonical.json"
    curated_out = Path(__file__).parent.parent.parent / "curated" / "reviews_curated.json"

    link_reviews_dataset(proc_reviews, canonical_places, curated_out)
