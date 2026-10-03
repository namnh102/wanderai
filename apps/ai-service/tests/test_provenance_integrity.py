"""TASK 07.3 regression tests: no fabricated ratings, provenance guards (no DB / network needed)."""
import json
import sys
from pathlib import Path

workspace_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(workspace_root))

from data.pipelines.entity_resolution.resolve import _create_canonical_record
from data.pipelines.reviews.clean_reviews import clean_review_record
from data.pipelines.quality_checker import validate_places

MANIFEST = workspace_root / "data" / "manifests" / "osm-invalid-sources.json"
CURATED = workspace_root / "data" / "curated" / "places_canonical.json"


def test_canonical_record_without_rating_stays_unavailable():
    rec = _create_canonical_record(
        {"name": "Quán A", "latitude": 16.0, "longitude": 108.2, "source_id": "node/1"}, "id-1"
    )
    assert rec["rating"] is None  # never 4.5, never 0


def test_canonical_record_keeps_real_rating():
    rec = _create_canonical_record({"name": "B", "rating": 3.8}, "id-2")
    assert rec["rating"] == 3.8


def test_review_without_rating_is_dropped_not_defaulted():
    assert clean_review_record({"text": "Một bài đánh giá đủ dài để hợp lệ"}) is None
    assert clean_review_record({"text": "Một bài đánh giá đủ dài", "rating": "abc"}) is None


def test_quality_checker_accepts_null_rating_and_flags_out_of_range():
    base = {"name": "X", "latitude": 16.0, "longitude": 108.2, "category": "cafe", "sources": [{"source_id": "node/1"}]}
    ok = validate_places([dict(base, rating=None)])
    assert ok["invalid_ratings"] == 0
    bad = validate_places([dict(base, rating=9.0)])
    assert bad["invalid_ratings"] == 1


def test_invalid_osm_sources_manifest_and_curated_data_are_consistent():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    ids = {s["source_id"] for s in manifest["invalid_sources"]}
    assert len(ids) == 13
    curated = json.loads(CURATED.read_text(encoding="utf-8"))
    for place in curated:
        for src in place.get("sources", []):
            assert src["source_id"] not in ids, f"{place['name']} still carries invalid source {src['source_id']}"
        assert place.get("rating") is None or place.get("review_count", 0) > 0, (
            f"{place['name']} has a rating without reviews (fabricated default)"
        )


def test_rag_place_ingestion_is_restricted_to_places_with_osm_source():
    src = (workspace_root / "apps" / "ai-service" / "app" / "rag" / "ingestion.py").read_text(encoding="utf-8")
    assert "FROM place_sources ps WHERE ps.place_id = p.id" in src
