"""Entity resolution pipeline to unify multiple data sources into canonical places."""
import json
import uuid
import logging
from pathlib import Path

try:
    from matcher import compute_composite_match_score
except ImportError:
    from data.pipelines.entity_resolution.matcher import compute_composite_match_score

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("entity_resolver")

HIGH_CONFIDENCE_THRESHOLD = 0.80
REVIEW_NEEDED_THRESHOLD = 0.60


def resolve_places(input_places: list[dict], existing_canonical: list[dict] | None = None) -> tuple[list[dict], dict]:
    """Resolves incoming place records against existing canonical pool."""
    canonical_pool = list(existing_canonical) if existing_canonical else []

    stats = {
        "total_incoming": len(input_places),
        "matched_existing": 0,
        "new_canonical_created": 0,
        "review_needed_count": 0,
        "review_needed_cases": [],
    }

    for incoming in input_places:
        best_match = None
        highest_score = 0.0

        for canon in canonical_pool:
            score = compute_composite_match_score(incoming, canon)
            if score > highest_score:
                highest_score = score
                best_match = canon

        if best_match and highest_score >= HIGH_CONFIDENCE_THRESHOLD:
            # High confidence merge: attach as new provenance source
            stats["matched_existing"] += 1
            source_entry = {
                "source_name": incoming.get("source_name", "osm"),
                "source_id": incoming.get("source_id", ""),
                "raw_name": incoming.get("raw_name", incoming.get("name", "")),
                "latitude": incoming.get("latitude"),
                "longitude": incoming.get("longitude"),
                "raw_data": incoming.get("raw_data", {}),
                "confidence_score": highest_score,
            }
            # Prevent duplicate sources on same canonical record
            existing_source_ids = {s.get("source_id") for s in best_match.get("sources", [])}
            if source_entry["source_id"] not in existing_source_ids:
                best_match.setdefault("sources", []).append(source_entry)

            # Enhance canonical metadata if incoming has better info
            if not best_match.get("name_en") and incoming.get("name_en"):
                best_match["name_en"] = incoming["name_en"]
            if not best_match.get("address") and incoming.get("address"):
                best_match["address"] = incoming["address"]

        elif best_match and highest_score >= REVIEW_NEEDED_THRESHOLD:
            # Medium confidence: mark for review, create separate canonical record with review flag
            stats["review_needed_count"] += 1
            stats["review_needed_cases"].append({
                "incoming_name": incoming.get("name"),
                "candidate_name": best_match.get("name"),
                "score": highest_score,
            })
            new_id = str(uuid.uuid4())
            canonical_record = _create_canonical_record(incoming, new_id, confidence_score=highest_score, review_flag=True)
            canonical_pool.append(canonical_record)
            stats["new_canonical_created"] += 1

        else:
            # Unmatched: create new canonical place
            new_id = str(uuid.uuid4())
            canonical_record = _create_canonical_record(incoming, new_id, confidence_score=1.0)
            canonical_pool.append(canonical_record)
            stats["new_canonical_created"] += 1

    return canonical_pool, stats


def _create_canonical_record(source_record: dict, canonical_id: str, confidence_score: float = 1.0, review_flag: bool = False) -> dict:
    """Constructs a clean canonical place entity with initial source."""
    return {
        "id": canonical_id,
        "name": source_record.get("name", "").strip(),
        "name_en": source_record.get("name_en"),
        "category": source_record.get("category", "attraction"),
        "address": source_record.get("address"),
        "city": source_record.get("city", ""),
        "latitude": source_record.get("latitude"),
        "longitude": source_record.get("longitude"),
        "description": source_record.get("description"),
        "rating": source_record.get("rating", 4.5),
        "review_count": source_record.get("review_count", 0),
        "review_flag": review_flag,
        "sources": [
            {
                "source_name": source_record.get("source_name", "osm"),
                "source_id": source_record.get("source_id", ""),
                "raw_name": source_record.get("raw_name", source_record.get("name", "")),
                "latitude": source_record.get("latitude"),
                "longitude": source_record.get("longitude"),
                "raw_data": source_record.get("raw_data", {}),
                "confidence_score": confidence_score,
            }
        ],
    }


def run_resolution_pipeline(input_path: Path, output_path: Path, report_path: Path) -> list[dict]:
    """Executes the resolution pipeline from processed input to curated output."""
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    with open(input_path, "r", encoding="utf-8") as f:
        places = json.load(f)

    logger.info(f"Running entity resolution on {len(places)} places from {input_path}...")
    canonical_places, stats = resolve_places(places)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(canonical_places, f, ensure_ascii=False, indent=2)

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    logger.info(
        f"Resolution complete: {stats['new_canonical_created']} canonical places created, "
        f"{stats['matched_existing']} merged, {stats['review_needed_count']} review-needed. "
        f"Saved to {output_path}"
    )
    return canonical_places


if __name__ == "__main__":
    proc_file = Path(__file__).parent.parent.parent / "processed" / "osm_places.json"
    curated_file = Path(__file__).parent.parent.parent / "curated" / "places_canonical.json"
    report_file = Path(__file__).parent.parent.parent / "curated" / "entity_resolution_report.json"
    run_resolution_pipeline(proc_file, curated_file, report_file)
