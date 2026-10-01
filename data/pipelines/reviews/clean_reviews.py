"""Cleans and normalizes raw review datasets, ensuring data privacy and validity."""
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("review_cleaner")

MIN_TEXT_LENGTH = 10


def clean_review_record(raw_rev: dict) -> dict | None:
    """Validates and cleans an individual review record."""
    text = raw_rev.get("text", "").strip()
    if len(text) < MIN_TEXT_LENGTH:
        return None

    raw_rating = raw_rev.get("rating", 5.0)
    try:
        rating = float(raw_rating)
        # Clamp rating between 1.0 and 5.0
        rating = max(1.0, min(5.0, round(rating, 1)))
    except (ValueError, TypeError):
        rating = 5.0

    aspects = []
    for asp in raw_rev.get("aspects", []):
        aspect_name = asp.get("aspect", "").lower().strip()
        aspect_score = asp.get("score", rating)
        try:
            aspect_score = max(1.0, min(5.0, float(aspect_score)))
        except (ValueError, TypeError):
            aspect_score = rating
        if aspect_name:
            aspects.append({
                "aspect": aspect_name,
                "score": aspect_score,
                "comment": asp.get("comment", "").strip(),
            })

    return {
        "source_review_id": raw_rev.get("source_review_id", ""),
        "place_name_target": raw_rev.get("place_name_target", "").strip(),
        "city": raw_rev.get("city", "").strip(),
        "rating": rating,
        "content": text,
        "aspects": aspects,
    }


def clean_reviews_file(raw_path: Path, output_path: Path) -> list[dict]:
    """Processes raw reviews file and writes normalized reviews."""
    if not raw_path.exists():
        raise FileNotFoundError(f"Raw reviews file not found: {raw_path}")

    with open(raw_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    raw_reviews = data.get("reviews", [])
    logger.info(f"Cleaning {len(raw_reviews)} reviews from {raw_path}...")

    cleaned = []
    skipped = 0

    for r in raw_reviews:
        cleaned_rec = clean_review_record(r)
        if cleaned_rec:
            cleaned.append(cleaned_rec)
        else:
            skipped += 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)

    logger.info(f"Cleaned {len(cleaned)} reviews (skipped {skipped}). Saved to {output_path}")
    return cleaned


if __name__ == "__main__":
    raw_file = Path(__file__).parent.parent.parent / "raw" / "vietnam_travel_reviews.json"
    proc_file = Path(__file__).parent.parent.parent / "processed" / "reviews_normalized.json"
    clean_reviews_file(raw_file, proc_file)
