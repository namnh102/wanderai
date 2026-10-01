"""Unit tests for the GoMate real travel data pipeline and entity resolution."""
import pytest
from pathlib import Path
import sys

# Add wanderai root to sys.path so data.pipelines modules can be imported
workspace_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(workspace_root))

from data.pipelines.entity_resolution.matcher import (
    normalize_vietnamese_text,
    remove_vietnamese_accents,
    calculate_name_similarity,
    haversine_distance_meters,
    calculate_geo_similarity,
    calculate_category_similarity,
    compute_composite_match_score,
)
from data.pipelines.osm.parse_osm import is_valid_coordinate, parse_single_osm_element as parse_osm_element
from data.pipelines.reviews.clean_reviews import clean_review_record
from data.pipelines.quality_checker import validate_places, validate_reviews


class TestOsmValidation:
    """Test OSM geographic boundaries and parsing."""

    def test_within_vietnam_valid_coordinates(self):
        # Da Nang coordinates
        assert is_valid_coordinate(16.0544, 108.2022) is True
        # Hanoi coordinates
        assert is_valid_coordinate(21.0285, 105.8542) is True
        # Ho Chi Minh City coordinates
        assert is_valid_coordinate(10.8231, 106.6297) is True

    def test_within_vietnam_invalid_coordinates(self):
        # London
        assert is_valid_coordinate(51.5074, -0.1278) is False
        # Null coordinates
        assert is_valid_coordinate(None, 108.2022) is False
        assert is_valid_coordinate(16.0544, None) is False

    def test_parse_osm_element_valid(self):
        el = {
            "type": "node",
            "id": 123456,
            "lat": 16.0612,
            "lon": 108.2272,
            "tags": {
                "name": "Cầu Rồng",
                "name:en": "Dragon Bridge",
                "tourism": "attraction",
                "addr:city": "Đà Nẵng",
            },
            "_region": "da_nang",
        }
        parsed = parse_osm_element(el)
        assert parsed is not None
        assert parsed["name"] == "Cầu Rồng"
        assert parsed["category"] == "attraction"
        assert parsed["source_name"] == "osm"
        assert parsed["source_id"] == "node/123456"

    def test_parse_osm_element_nameless_skipped(self):
        el = {
            "type": "node",
            "id": 78910,
            "lat": 16.0612,
            "lon": 108.2272,
            "tags": {"natural": "tree"},
        }
        assert parse_osm_element(el) is None


class TestEntityResolutionMatcher:
    """Test multi-signal entity matching."""

    def test_text_normalization(self):
        assert normalize_vietnamese_text("  Đà   Nẵng! ") == "đà nẵng"
        assert remove_vietnamese_accents("Hồ Hoàn Kiếm") == "Ho Hoan Kiem"

    def test_name_similarity_exact_and_accents(self):
        # Exact match
        assert calculate_name_similarity("Chùa Linh Ứng", "Chùa Linh Ứng") == 1.0
        # Accent-insensitive match
        sim_accent = calculate_name_similarity("Bãi biển Mỹ Khê", "Bai bien My Khe")
        assert sim_accent >= 0.90
        # Unrelated strings
        sim_diff = calculate_name_similarity("Chùa Linh Ứng", "Nhà hàng Pizza 4P")
        assert sim_diff < 0.20

    def test_haversine_distance(self):
        # Same point
        dist = haversine_distance_meters(16.0612, 108.2272, 16.0612, 108.2272)
        assert dist == pytest.approx(0.0, abs=0.1)

        # ~100 meters apart
        dist_near = haversine_distance_meters(16.0612, 108.2272, 16.0618, 108.2272)
        assert 50 < dist_near < 100

    def test_geo_similarity_scores(self):
        # Very close (<50m)
        assert calculate_geo_similarity(16.0612, 108.2272, 16.06125, 108.2272) == 1.0
        # Far (>2500m)
        assert calculate_geo_similarity(16.0612, 108.2272, 16.1500, 108.3500) == 0.0

    def test_composite_match_score_high_confidence(self):
        p1 = {
            "name": "Bãi biển Mỹ Khê",
            "latitude": 16.0601,
            "longitude": 108.2435,
            "category": "beach",
        }
        p2 = {
            "name": "My Khe Beach",
            "latitude": 16.0602,
            "longitude": 108.2436,
            "category": "beach",
        }
        score = compute_composite_match_score(p1, p2)
        assert score >= 0.80


class TestReviewCleaner:
    """Test review cleaning and validation."""

    def test_clean_review_valid(self):
        raw = {
            "source_review_id": "test_001",
            "place_name_target": "Bãi biển Mỹ Khê",
            "city": "Đà Nẵng",
            "rating": 4.5,
            "text": "Bãi biển Mỹ Khê rất sạch và đẹp, dịch vụ tốt.",
            "aspects": [{"aspect": "cleanliness", "score": 5.0}],
        }
        cleaned = clean_review_record(raw)
        assert cleaned is not None
        assert cleaned["rating"] == 4.5
        assert len(cleaned["aspects"]) == 1

    def test_clean_review_short_rejected(self):
        raw = {
            "source_review_id": "test_short",
            "rating": 5.0,
            "text": "Ngắn",
        }
        assert clean_review_record(raw) is None

    def test_clean_review_rating_clamping(self):
        raw_high = {
            "source_review_id": "test_high",
            "rating": 10.0,
            "text": "Nội dung hợp lệ trên mười ký tự.",
        }
        cleaned = clean_review_record(raw_high)
        assert cleaned["rating"] == 5.0


class TestDataQualityRules:
    """Test quality checker rules."""

    def test_validate_places_integrity(self):
        sample_places = [
            {
                "id": "11111111-1111-1111-1111-111111111111",
                "name": "Điểm tham quan A",
                "latitude": 16.0,
                "longitude": 108.0,
                "category": "attraction",
                "rating": 4.5,
                "sources": [{"source_name": "osm", "source_id": "node/1"}],
            }
        ]
        metrics = validate_places(sample_places)
        assert metrics["total_places"] == 1
        assert metrics["missing_names"] == 0
        assert metrics["out_of_bounds_coordinates"] == 0
        assert metrics["source_provenance_rate"] == 1.0
