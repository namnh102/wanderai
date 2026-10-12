"""TASK REC-01A Place Recommendation Baseline Test Suite.

Verifies:
1. REC-A-CORE-V2 item universe = 622, secondary = 137 excluded.
2. 4 Quảng Nam outside-core places are never recommended in Da Nang core.
3. Canonical 7D item vectors and user vectors are deterministic and valid.
4. REC-A0 taxonomy overlap and REC-A1 cosine similarity scoring formulas are exact.
5. Determinism: identical input yields bit-identical Top-K rankings and scores.
6. Destination filtering strictly bounds candidates to requested destination slug.
7. Top-K results contain unique place IDs ordered by score descending and deterministic tie-break.
8. Cold-start produces deterministic non-empty fallback labeled COLD_START_DIVERSE_CATALOG_BASELINE.
9. Unsupported budget, group, avoidance, and dietary signals do not fabricate filtering.
10. Explanation contract aligns reason_code, matched_interests, and Vietnamese explanation text.
11. All 300 synthetic preference profiles process successfully with 0 zero-results.
12. Freeze V1 and Freeze V2 SHA256 integrity remains 100% unchanged.
"""

import json
import math
from pathlib import Path
import sys
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
AI_SERVICE_DIR = REPO_ROOT / "apps" / "ai-service"
if str(AI_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_DIR))

from recommendation.reca.contract import (
    CANONICAL_INTERESTS,
    UNSUPPORTED_USER_FEATURES,
    poi_to_canonical_vector,
    user_to_canonical_vector,
    normalize_destination,
    normalize_string,
    l2_norm,
)
from recommendation.reca.models import (
    RecA0TaxonomyBaseline,
    RecA1CosineBaseline,
    ColdStartDiverseBaseline,
    build_explanation,
)
from recommendation.reca.engine import PlaceRecommender


@pytest.fixture(scope="module")
def v2_places():
    path = REPO_ROOT / "data" / "curated" / "gomate_places_freeze_v2.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def synthetic_profiles():
    path = REPO_ROOT / "data" / "evaluation" / "synthetic" / "preferences_n300_seed42.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def recommender(v2_places):
    return PlaceRecommender(places_source=v2_places)


# 1. Core Item Universe = 622, Secondary = 137 Excluded
def test_assertion_1_candidate_universe_partition(recommender, v2_places):
    assert len(recommender.core_places) == 622
    assert len(recommender.secondary_places) == 137
    assert len(v2_places) == 759

    core_ids = {p["place_id"] for p in recommender.core_places}
    sec_ids = {p["place_id"] for p in recommender.secondary_places}
    assert core_ids.isdisjoint(sec_ids)

    # Core destination distribution: Da Nang = 289, Ha Noi = 145, Ha Long = 188
    core_by_dest = {}
    for p in recommender.core_places:
        d = p["destination_slug"]
        core_by_dest[d] = core_by_dest.get(d, 0) + 1
    assert core_by_dest["da-nang"] == 289
    assert core_by_dest["ha-noi"] == 145
    assert core_by_dest["ha-long"] == 188
    assert sum(core_by_dest.values()) == 622


# 2. 4 Quang Nam Outside-Core Items Excluded from Da Nang Recommendations
def test_assertion_2_quang_nam_outside_core_exclusion(recommender):
    known_quang_nam_ids = {
        "5e1ca20e-b579-59b8-b243-9f13aa43c65f",  # TASY STUDIO
        "6489aeb0-fb3d-584d-9ca9-d6172e9cc63f",  # Khu tưởng niệm Hà My
        "db61c6ab-1fde-51fe-ac20-0deef2fc5981",  # Đài tưởng niệm thảm sát Hà My
        "4c4ca7e8-2586-57cb-af5d-5e2b72c7bd4d",  # Mini-Golf Hoi An
    }
    core_ids = {p["place_id"] for p in recommender.core_places}
    for qn_id in known_quang_nam_ids:
        assert qn_id not in core_ids, f"Quảng Nam outside place {qn_id} found in core catalog!"

    # Test recommendation outputs for Da Nang across different interest combinations
    for interests in [
        ["nature_outdoor", "beach_island"],
        ["culture_history"],
        ["food_cuisine", "coffee_culture"],
        [],
    ]:
        for model in ["rec-a0", "rec-a1"]:
            res = recommender.recommend(
                preferences={"interests": interests},
                destination="da-nang",
                top_k=50,
                model=model,
            )
            rec_ids = {r["place_id"] for r in res["recommendations"]}
            assert known_quang_nam_ids.isdisjoint(rec_ids)


# 3. Canonical 7D Item and User Vectors
def test_assertion_3_canonical_vectors(recommender):
    assert len(CANONICAL_INTERESTS) == 7
    expected_vocabulary = [
        "food_cuisine",
        "culture_history",
        "nature_outdoor",
        "coffee_culture",
        "beach_island",
        "shopping_local",
        "nightlife_entertainment",
    ]
    assert CANONICAL_INTERESTS == expected_vocabulary

    # Check user vector conversion
    u_vec = user_to_canonical_vector(["food_cuisine", "beach_island", "unknown_interest"])
    assert len(u_vec) == 7
    assert u_vec[0] == 1.0  # food_cuisine
    assert u_vec[4] == 1.0  # beach_island
    assert sum(u_vec) == 2.0

    # Check every core place produces valid 7D vector
    for p in recommender.core_places:
        pid = p["place_id"]
        vec = recommender.poi_vectors[pid]
        assert len(vec) == 7
        for val in vec:
            assert isinstance(val, (int, float))
            assert 0.0 <= val <= 1.0


# 4. REC-A0 Overlap and REC-A1 Cosine Similarity Formulas
def test_assertion_4_scoring_formulas():
    # REC-A0 Overlap: sum(min(u_i, p_i)) where both > 0
    u1 = [1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    p1 = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0]
    score_a0, matched = RecA0TaxonomyBaseline.score(u1, p1)
    assert score_a0 == 1.0
    assert matched == ["food_cuisine"]

    # REC-A1 Cosine: dot(u, p) / (|u| * |p|)
    # dot = 1.0, |u| = sqrt(2), |p| = sqrt(2) -> cos = 1.0 / 2.0 = 0.5
    score_a1, matched_a1 = RecA1CosineBaseline.score(u1, p1)
    expected_cos = 1.0 / (math.sqrt(2) * math.sqrt(2))
    assert math.isclose(score_a1, expected_cos, rel_tol=1e-5)
    assert matched_a1 == ["food_cuisine"]

    # Orthogonal vectors: score must be 0.0
    u_ortho = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    p_ortho = [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    assert RecA0TaxonomyBaseline.score(u_ortho, p_ortho)[0] == 0.0
    assert RecA1CosineBaseline.score(u_ortho, p_ortho)[0] == 0.0

    # Identical vectors: cosine score must be 1.0
    u_ident = [1.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0]
    p_ident = [1.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0]
    assert math.isclose(RecA1CosineBaseline.score(u_ident, p_ident)[0], 1.0, rel_tol=1e-5)


# 5. Determinism Check
def test_assertion_5_determinism(recommender):
    pref = {"interests": ["nature_outdoor", "beach_island", "coffee_culture"]}
    run1 = recommender.recommend(preferences=pref, destination="da-nang", top_k=10, model="rec-a1")
    run2 = recommender.recommend(preferences=pref, destination="da-nang", top_k=10, model="rec-a1")
    assert run1 == run2

    run1_a0 = recommender.recommend(preferences=pref, destination=None, top_k=15, model="rec-a0")
    run2_a0 = recommender.recommend(preferences=pref, destination=None, top_k=15, model="rec-a0")
    assert run1_a0 == run2_a0


# 6. Destination Filtering
def test_assertion_6_destination_filtering(recommender):
    for dest_slug, expected_count in [("ha-noi", 145), ("ha-long", 188), ("da-nang", 289)]:
        res = recommender.recommend(
            preferences={"interests": ["food_cuisine"]},
            destination=dest_slug,
            top_k=50,
            model="rec-a1",
        )
        for r in res["recommendations"]:
            assert r["destination_slug"] == dest_slug
        assert res["metadata"]["total_candidates"] == expected_count

    # None / All destinations
    all_res = recommender.recommend(
        preferences={"interests": ["food_cuisine"]},
        destination=None,
        top_k=10,
        model="rec-a1",
    )
    assert all_res["metadata"]["total_candidates"] == 622


# 7. Top-K Uniqueness, Ranking, and Deterministic Tie-Breaking
def test_assertion_7_topk_uniqueness_and_tie_breaking(recommender):
    res = recommender.recommend(
        preferences={"interests": ["food_cuisine", "coffee_culture"]},
        destination=None,
        top_k=20,
        model="rec-a1",
    )
    recs = res["recommendations"]
    assert len(recs) == 20

    # All returned IDs unique
    rec_ids = [r["place_id"] for r in recs]
    assert len(rec_ids) == len(set(rec_ids))

    # Scores monotonically non-increasing
    for i in range(len(recs) - 1):
        assert recs[i]["score"] >= recs[i + 1]["score"]
        if recs[i]["score"] == recs[i + 1]["score"]:
            name_curr = normalize_string(recs[i]["name"])
            name_next = normalize_string(recs[i + 1]["name"])
            assert (name_curr, recs[i]["place_id"]) <= (name_next, recs[i + 1]["place_id"])


# 8. Cold-Start Fallback Labeled COLD_START_DIVERSE_CATALOG_BASELINE
def test_assertion_8_cold_start_fallback(recommender):
    empty_prefs = [
        {"interests": []},
        {"interests": ["completely_unrecognized_tag"]},
        {},
    ]
    for pref in empty_prefs:
        res = recommender.recommend(preferences=pref, destination="da-nang", top_k=10)
        assert res["metadata"]["cold_start"] is True
        assert res["metadata"]["algorithm"] == "COLD_START_DIVERSE_CATALOG_BASELINE"
        recs = res["recommendations"]
        assert len(recs) == 10

        # Check diversity of categories across cold start recommendations
        categories = {r["category"] for r in recs}
        assert len(categories) >= 3, f"Expected diverse category coverage in cold start, got: {categories}"

        for r in recs:
            assert r["strategy"] == "COLD_START_DIVERSE_CATALOG_BASELINE"
            assert r["explanation"]["reason_code"] == "COLD_START_DIVERSE_FALLBACK"
            assert "Địa điểm tiêu biểu tại điểm đến" in r["explanation"]["text"]


# 9. Unsupported User Features Manifest
def test_assertion_9_unsupported_features_manifest(recommender):
    expected_unsupported = [
        "travelStyle",
        "budgetMin",
        "budgetMax",
        "preferredGroup",
        "avoidances",
        "dietaryNeeds",
    ]
    actual_features = [f["feature"] for f in UNSUPPORTED_USER_FEATURES]
    assert actual_features == expected_unsupported
    for f in UNSUPPORTED_USER_FEATURES:
        assert f["status"] == "AVAILABLE_USER_FEATURE_NOT_USED_IN_V1"

    pref_with_unsupported = {
        "interests": ["nature_outdoor"],
        "budgetMin": 500000,
        "budgetMax": 1000000,
        "preferredGroup": "SOLO",
        "avoidances": ["crowds"],
        "dietaryNeeds": ["vegan"],
    }
    res = recommender.recommend(preferences=pref_with_unsupported, destination="da-nang", top_k=10)
    assert res["unsupported_user_features"] == UNSUPPORTED_USER_FEATURES
    # Verify recommendations are based purely on valid canonical interests
    assert len(res["recommendations"]) == 10
    assert "nature_outdoor" in res["recommendations"][0]["matched_interests"]


# 10. Explanation Contract
def test_assertion_10_explanation_contract():
    expl = build_explanation(
        matched_interests=["food_cuisine", "coffee_culture"],
        matched_taxonomy=["FOOD_BEVERAGE"],
        is_cold_start=False,
    )
    assert expl["reason_code"] == "PREFERENCE_TAXONOMY_MATCH"
    assert "ẩm thực & đặc sản" in expl["text"]
    assert "văn hóa cà phê & trà" in expl["text"]
    assert expl["matched_taxonomy"] == ["FOOD_BEVERAGE"]

    cold_expl = build_explanation(
        matched_interests=[],
        matched_taxonomy=[],
        is_cold_start=True,
    )
    assert cold_expl["reason_code"] == "COLD_START_DIVERSE_FALLBACK"
    assert "Địa điểm tiêu biểu tại điểm đến" in cold_expl["text"]


# 11. All 300 Synthetic Profiles Benchmark Outputs
def test_assertion_11_synthetic_benchmark_outputs():
    summary_path = REPO_ROOT / "data" / "evaluation" / "reca" / "reca_benchmark_summary.json"
    a0_path = REPO_ROOT / "data" / "evaluation" / "reca" / "reca0_top10_n300.json"
    a1_path = REPO_ROOT / "data" / "evaluation" / "reca" / "reca1_top10_n300.json"

    assert summary_path.exists(), "Benchmark summary artifact missing!"
    assert a0_path.exists(), "REC-A0 artifact missing!"
    assert a1_path.exists(), "REC-A1 artifact missing!"

    with open(summary_path, "r", encoding="utf-8") as f:
        summary = json.load(f)

    assert summary["profiles_evaluated"] == 300
    assert summary["catalog_size"] == 622
    assert summary["determinism_verification"]["rec_a0_bit_identical"] is True
    assert summary["determinism_verification"]["rec_a1_bit_identical"] is True
    assert summary["rec_a0"]["zero_result_profiles"] == 0
    assert summary["rec_a1"]["zero_result_profiles"] == 0
    assert summary["rec_a0"]["unique_places_recommended"] > 0
    assert summary["rec_a1"]["unique_places_recommended"] > 0

    with open(a0_path, "r", encoding="utf-8") as f:
        a0_data = json.load(f)
    assert len(a0_data) == 300

    with open(a1_path, "r", encoding="utf-8") as f:
        a1_data = json.load(f)
    assert len(a1_data) == 300


# 12. Freeze V1 and Freeze V2 SHA Integrity
def test_assertion_12_freeze_v1_and_v2_sha_integrity():
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from scripts.freeze_checksum import (
        DEFAULT_COMPAT_RELPATHS, LEGACY_EOL_COMPAT_PASS, PASS, verify_manifest,
    )
    compat_paths = [REPO_ROOT / p for p in DEFAULT_COMPAT_RELPATHS]
    for manifest_name in ["dataset-freeze-v1.sha256", "dataset-freeze-v2.sha256"]:
        manifest_path = REPO_ROOT / "data" / "manifests" / manifest_name
        assert manifest_path.exists(), f"Missing manifest: {manifest_path}"
        results = verify_manifest(REPO_ROOT, manifest_path, compat_paths)
        assert results, f"Empty manifest: {manifest_name}"
        bad = [d for _, st, d in results if st not in (PASS, LEGACY_EOL_COMPAT_PASS)]
        assert not bad, f"{manifest_name} integrity failure: " + "; ".join(bad)


# ==============================================================================
# R1 SPECIFIC ASSERTIONS (TASK REC-01A-R1)
# ==============================================================================

# R1-1: cafe_tea does NOT automatically imply food_cuisine unless trusted dining subtype is present
def test_r1_cafe_tea_does_not_automatically_imply_food_cuisine():
    pure_cafe = {
        "place_id": "test-cafe-pure",
        "name": "Cà Phê Phố Cổ",
        "category": "cafe",
        "sources": [{
            "source_name": "osm",
            "raw_data": {
                "tier_1": "FOOD_BEVERAGE",
                "tier_2": "cafe_tea",
                "tags": {"amenity": "cafe"},
            },
        }],
    }
    vec, matched = poi_to_canonical_vector(pure_cafe)
    assert vec[CANONICAL_INTERESTS.index("coffee_culture")] == 1.0
    assert vec[CANONICAL_INTERESTS.index("food_cuisine")] == 0.0

    # Cafe with explicit dining amenity tag
    dining_cafe = {
        "place_id": "test-cafe-dining",
        "name": "Bistro & Cafe",
        "category": "cafe",
        "sources": [{
            "source_name": "osm",
            "raw_data": {
                "tier_1": "FOOD_BEVERAGE",
                "tier_2": "cafe_tea",
                "tags": {"amenity": "restaurant", "cuisine": "vietnamese;coffee"},
            },
        }],
    }
    d_vec, _ = poi_to_canonical_vector(dining_cafe)
    assert d_vec[CANONICAL_INTERESTS.index("coffee_culture")] == 1.0
    assert d_vec[CANONICAL_INTERESTS.index("food_cuisine")] == 1.0


# R1-2: restaurant_dining, street_food, seafood_dining map to food_cuisine
def test_r1_restaurant_dining_maps_to_food_cuisine():
    dining_types = ["restaurant_dining", "street_food", "street_food_market", "seafood_dining"]
    for dtype in dining_types:
        poi = {
            "place_id": f"test-{dtype}",
            "name": f"Test {dtype}",
            "category": "restaurant",
            "sources": [{
                "source_name": "osm",
                "raw_data": {
                    "tier_1": "FOOD_BEVERAGE",
                    "tier_2": dtype,
                    "tags": {"amenity": "restaurant"},
                },
            }],
        }
        vec, matched = poi_to_canonical_vector(poi)
        assert vec[CANONICAL_INTERESTS.index("food_cuisine")] == 1.0
        assert "FOOD_BEVERAGE" in matched


# R1-3: nightlife_entertainment maps to nightlife
def test_r1_nightlife_entertainment_maps_to_nightlife():
    nightlife_poi = {
        "place_id": "test-bar",
        "name": "Sky Bar & Lounge",
        "category": "nightlife",
        "sources": [{
            "source_name": "osm",
            "raw_data": {
                "tier_1": "ATTRACTIONS_LEISURE",
                "tier_2": "nightlife_entertainment",
                "tags": {"amenity": "bar"},
            },
        }],
    }
    vec, matched = poi_to_canonical_vector(nightlife_poi)
    assert vec[CANONICAL_INTERESTS.index("nightlife_entertainment")] == 1.0
    assert "ATTRACTIONS_LEISURE" in matched


# R1-4: generic attraction and theme park do NOT automatically map to nightlife
def test_r1_generic_attractions_and_theme_parks_do_not_map_to_nightlife():
    non_nightlife_attractions = [
        ("theme_park_leisure", "Công viên giải trí Sun World"),
        ("water_park", "Công viên nước Mikazuki"),
        ("landmark_iconic", "Cầu Rồng"),
        ("attraction", "Điểm tham quan chung"),
    ]
    for tier2, name in non_nightlife_attractions:
        poi = {
            "place_id": f"test-{tier2}",
            "name": name,
            "category": "attraction",
            "sources": [{
                "source_name": "osm",
                "raw_data": {
                    "tier_1": "ATTRACTIONS_LEISURE",
                    "tier_2": tier2,
                    "tags": {"tourism": "attraction"},
                },
            }],
        }
        vec, _ = poi_to_canonical_vector(poi)
        assert vec[CANONICAL_INTERESTS.index("nightlife_entertainment")] == 0.0, (
            f"POI {name} ({tier2}) improperly mapped to nightlife_entertainment!"
        )


# R1-5: No unsupported heuristic Hospitality weighting exists unless contract-backed
def test_r1_no_unsupported_hospitality_heuristic_weighting():
    hotels = [
        ("Furama Resort Danang Beach", {"tourism": "resort"}),
        ("Diamond Sea Hotel", {"tourism": "hotel"}),
        ("Ha Long Bay Luxury Hotel", {"tourism": "hotel"}),
    ]
    for name, tags in hotels:
        poi = {
            "place_id": f"test-hotel-{name[:5]}",
            "name": name,
            "category": "hotel",
            "sources": [{
                "source_name": "osm",
                "raw_data": {
                    "tier_1": "HOSPITALITY",
                    "tier_2": "hotel_resort",
                    "tags": tags,
                },
            }],
        }
        vec, _ = poi_to_canonical_vector(poi)
        assert vec == [0.0] * 7, f"Hotel {name} received non-zero activity feature vector: {vec}"


# R1-6: travelStyle is explicitly marked unsupported with validated reason
def test_r1_travel_style_explicitly_marked_unsupported():
    travel_style_feature = next((f for f in UNSUPPORTED_USER_FEATURES if f["feature"] == "travelStyle"), None)
    assert travel_style_feature is not None
    assert travel_style_feature["status"] == "AVAILABLE_USER_FEATURE_NOT_USED_IN_V1"
    assert "Dataset Freeze V2" in travel_style_feature["reason"]


# R1-7: explanation matched_interests exactly reflect score features
def test_r1_explanation_matched_interests_exactly_reflect_score_features(recommender):
    user_prefs = {"interests": ["food_cuisine", "coffee_culture"]}
    res = recommender.recommend(preferences=user_prefs, destination="da-nang", top_k=10, model="rec-a1")
    for r in res["recommendations"]:
        expl = r["explanation"]
        matched = expl["matched_interests"]
        assert set(matched).issubset({"food_cuisine", "coffee_culture"})
        # Every matched interest must be in the POI's canonical vector
        pid = r["place_id"]
        poi_vec = recommender.poi_vectors[pid]
        for m in matched:
            idx = CANONICAL_INTERESTS.index(m)
            assert poi_vec[idx] > 0.0


# ============================================================================
# W4-GATE-02: Focused Internal Validation Hardening Tests
# ============================================================================

# MODEL:
def test_val_model_01_valid_reca0_works(recommender):
    res = recommender.recommend(preferences={"interests": ["food_cuisine"]}, destination="da-nang", top_k=5, model="rec-a0")
    assert res["metadata"]["model"] == "rec-a0"
    assert len(res["recommendations"]) == 5


def test_val_model_02_valid_reca1_works(recommender):
    res = recommender.recommend(preferences={"interests": ["food_cuisine"]}, destination="da-nang", top_k=5, model="rec-a1")
    assert res["metadata"]["model"] == "rec-a1"
    assert len(res["recommendations"]) == 5


@pytest.mark.parametrize("bad_model", ["garbage", "rec-a9", "abc", "", "rec-b1"])
def test_val_model_03_explicit_garbage_model_fails(recommender, bad_model):
    with pytest.raises(ValueError, match="Unsupported recommendation model"):
        recommender.recommend(preferences={"interests": ["food_cuisine"]}, destination="da-nang", top_k=5, model=bad_model)


def test_val_model_04_omitted_model_preserves_default(recommender):
    # Omitted model defaults to rec-a1
    res = recommender.recommend(preferences={"interests": ["food_cuisine"]}, destination="da-nang", top_k=5)
    assert res["metadata"]["model"] == "rec-a1"
    # Explicit None also defaults to rec-a1
    res_none = recommender.recommend(preferences={"interests": ["food_cuisine"]}, destination="da-nang", top_k=5, model=None)
    assert res_none["metadata"]["model"] == "rec-a1"


# DESTINATION:
def test_val_dst_01_hanoi_works(recommender):
    res = recommender.recommend(preferences={"interests": ["food_cuisine"]}, destination="ha-noi", top_k=5)
    assert res["metadata"]["destination_filter"] == "ha-noi"
    assert res["metadata"]["total_candidates"] == 145


def test_val_dst_02_danang_works(recommender):
    res = recommender.recommend(preferences={"interests": ["food_cuisine"]}, destination="da-nang", top_k=5)
    assert res["metadata"]["destination_filter"] == "da-nang"
    assert res["metadata"]["total_candidates"] == 289


def test_val_dst_03_halong_works(recommender):
    res = recommender.recommend(preferences={"interests": ["food_cuisine"]}, destination="ha-long", top_k=5)
    assert res["metadata"]["destination_filter"] == "ha-long"
    assert res["metadata"]["total_candidates"] == 188


@pytest.mark.parametrize(
    "alias,expected_slug",
    [
        ("Hanoi", "ha-noi"),
        ("hanoi", "ha-noi"),
        ("hn", "ha-noi"),
        ("Hà Nội", "ha-noi"),
        ("Danang", "da-nang"),
        ("danang", "da-nang"),
        ("dn", "da-nang"),
        ("Đà Nẵng", "da-nang"),
        ("Halong", "ha-long"),
        ("halong", "ha-long"),
        ("hl", "ha-long"),
        ("Hạ Long", "ha-long"),
    ],
)
def test_val_dst_04_supported_aliases_normalize(recommender, alias, expected_slug):
    res = recommender.recommend(preferences={"interests": ["food_cuisine"]}, destination=alias, top_k=5)
    assert res["metadata"]["destination_filter"] == expected_slug


@pytest.mark.parametrize("bad_dst", ["paris", "hue", "abc", "unknown-city", "quang-nam", "da nang city"])
def test_val_dst_05_explicit_invalid_destination_fails(recommender, bad_dst):
    with pytest.raises(ValueError, match="Unsupported destination"):
        recommender.recommend(preferences={"interests": ["food_cuisine"]}, destination=bad_dst, top_k=5)


def test_val_dst_06_invalid_destination_must_not_return_global_catalog(recommender):
    with pytest.raises(ValueError):
        recommender.recommend(preferences={"interests": ["food_cuisine"]}, destination="paris", top_k=10)


def test_val_dst_07_omitted_destination_preserves_global_scope(recommender):
    res = recommender.recommend(preferences={"interests": ["food_cuisine"]}, destination=None, top_k=10)
    assert res["metadata"]["destination_filter"] is None
    assert res["metadata"]["total_candidates"] == 622


# TOP_K:
def test_val_k_01_min_top_k_works(recommender):
    res = recommender.recommend(preferences={"interests": ["food_cuisine"]}, destination="da-nang", top_k=1)
    assert len(res["recommendations"]) == 1


def test_val_k_02_max_top_k_works(recommender):
    res = recommender.recommend(preferences={"interests": ["food_cuisine"]}, destination="da-nang", top_k=50)
    assert len(res["recommendations"]) == 50


@pytest.mark.parametrize("below_min", [0, -1, -10])
def test_val_k_03_below_min_fails(recommender, below_min):
    with pytest.raises(ValueError, match="must be between 1 and 50"):
        recommender.recommend(preferences={"interests": ["food_cuisine"]}, destination="da-nang", top_k=below_min)


@pytest.mark.parametrize("above_max", [51, 100, 9999])
def test_val_k_04_above_max_fails(recommender, above_max):
    with pytest.raises(ValueError, match="must be between 1 and 50"):
        recommender.recommend(preferences={"interests": ["food_cuisine"]}, destination="da-nang", top_k=above_max)


def test_val_k_05_negative_fails(recommender):
    with pytest.raises(ValueError, match="must be between 1 and 50"):
        recommender.recommend(preferences={"interests": ["food_cuisine"]}, destination="da-nang", top_k=-5)


@pytest.mark.parametrize("bad_type", ["10", 10.5, True, False, [10]])
def test_val_k_06_non_integer_fails(recommender, bad_type):
    with pytest.raises(ValueError, match="Invalid top_k"):
        recommender.recommend(preferences={"interests": ["food_cuisine"]}, destination="da-nang", top_k=bad_type)


# COLD START:
def test_val_cs_01_empty_interests_use_cold_start(recommender):
    for empty in [[], None, {}]:
        prefs = {"interests": empty} if empty is not None else {}
        res = recommender.recommend(preferences=prefs, destination="da-nang", top_k=10)
        assert res["metadata"]["cold_start"] is True
        assert res["metadata"]["algorithm"] == "COLD_START_DIVERSE_CATALOG_BASELINE"


def test_val_cs_02_cold_start_deterministic(recommender):
    res1 = recommender.recommend(preferences={"interests": []}, destination="da-nang", top_k=10)
    res2 = recommender.recommend(preferences={"interests": []}, destination="da-nang", top_k=10)
    ids1 = [r["place_id"] for r in res1["recommendations"]]
    ids2 = [r["place_id"] for r in res2["recommendations"]]
    assert ids1 == ids2


# REGRESSION:
def test_val_reg_01_valid_a0_behavior_unchanged(recommender):
    res = recommender.recommend(preferences={"interests": ["food_cuisine"]}, destination="ha-noi", top_k=5, model="rec-a0")
    assert res["metadata"]["model"] == "rec-a0"
    assert res["recommendations"][0]["score"] == 1.0


def test_val_reg_02_valid_a1_behavior_unchanged(recommender):
    res = recommender.recommend(preferences={"interests": ["food_cuisine"]}, destination="ha-noi", top_k=5, model="rec-a1")
    assert res["metadata"]["model"] == "rec-a1"
    assert math.isclose(res["recommendations"][0]["score"], 1.0, rel_tol=1e-5)


def test_val_reg_03_reca_core_counts_unchanged(recommender):
    assert len(recommender.core_places) == 622
    hn = [p for p in recommender.core_places if p.get("destination_slug") == "ha-noi"]
    dn = [p for p in recommender.core_places if p.get("destination_slug") == "da-nang"]
    hl = [p for p in recommender.core_places if p.get("destination_slug") == "ha-long"]
    assert len(hn) == 145
    assert len(dn) == 289
    assert len(hl) == 188


def test_val_reg_04_secondary_leakage_remains_zero(recommender):
    res = recommender.recommend(preferences={"interests": ["food_cuisine"]}, destination=None, top_k=50)
    core_ids = {p["place_id"] for p in recommender.core_places}
    sec_ids = {p["place_id"] for p in recommender.secondary_places}
    for r in res["recommendations"]:
        assert r["place_id"] in core_ids
        assert r["place_id"] not in sec_ids


# ============================================================================
# W4-A2-01: Focused REC-A2 Diversity Reranker Tests
# ============================================================================

def test_a2_micro_01_synthetic_in_memory_fixture():
    """Section 18 required micro-fixture test.

    User interests: food_cuisine, coffee_culture, shopping_local
    Candidates:
    R1 restaurant -> food
    R2 restaurant -> food
    R3 cafe -> coffee
    R4 market -> shopping
    R5 restaurant -> food
    Z1 hotel -> zero-vector
    Z2 attraction -> zero-vector

    Invariant: Top-3 must cover food, coffee, shopping before any food repetition.
    Z1 and Z2 must not enter Top-5.
    """
    synthetic_places = [
        {
            "place_id": "r1",
            "name": "An Restaurant",
            "category": "restaurant",
            "is_rec_a_core_v2": True,
            "destination_slug": "da-nang",
            "sources": [{"source_name": "osm", "raw_data": {"tier_1": "FOOD_BEVERAGE", "tier_2": "restaurant_dining"}}],
        },
        {
            "place_id": "r2",
            "name": "Binh Restaurant",
            "category": "restaurant",
            "is_rec_a_core_v2": True,
            "destination_slug": "da-nang",
            "sources": [{"source_name": "osm", "raw_data": {"tier_1": "FOOD_BEVERAGE", "tier_2": "restaurant_dining"}}],
        },
        {
            "place_id": "r3",
            "name": "Ca Cafe",
            "category": "cafe",
            "is_rec_a_core_v2": True,
            "destination_slug": "da-nang",
            "sources": [{"source_name": "osm", "raw_data": {"tier_1": "FOOD_BEVERAGE", "tier_2": "cafe_tea"}}],
        },
        {
            "place_id": "r4",
            "name": "Dan Market",
            "category": "market",
            "is_rec_a_core_v2": True,
            "destination_slug": "da-nang",
            "sources": [{"source_name": "osm", "raw_data": {"tier_1": "SHOPPING_COMMERCE", "tier_2": "traditional_market"}}],
        },
        {
            "place_id": "r5",
            "name": "Em Restaurant",
            "category": "restaurant",
            "is_rec_a_core_v2": True,
            "destination_slug": "da-nang",
            "sources": [{"source_name": "osm", "raw_data": {"tier_1": "FOOD_BEVERAGE", "tier_2": "restaurant_dining"}}],
        },
        {
            "place_id": "z1",
            "name": "A Hotel",
            "category": "hotel",
            "is_rec_a_core_v2": True,
            "destination_slug": "da-nang",
            "sources": [{"source_name": "osm", "raw_data": {"tier_1": "HOSPITALITY", "tier_2": "hotel_resort"}}],
        },
        {
            "place_id": "z2",
            "name": "B Attraction",
            "category": "attraction",
            "is_rec_a_core_v2": True,
            "destination_slug": "da-nang",
            "sources": [{"source_name": "osm", "raw_data": {"tier_1": "ATTRACTIONS_LEISURE", "tier_2": "attraction"}}],
        },
    ]

    engine = PlaceRecommender(places_source=synthetic_places)
    res = engine.recommend(
        preferences={"interests": ["food_cuisine", "coffee_culture", "shopping_local"]},
        destination="da-nang",
        top_k=5,
        model="rec-a2",
    )
    recs = res["recommendations"]
    assert len(recs) == 5

    # Top-3 must cover all 3 declared interests before repeating food
    top_3_interests = {m for r in recs[:3] for m in r["matched_interests"]}
    assert top_3_interests == {"food_cuisine", "coffee_culture", "shopping_local"}

    # Slots 4 and 5 must be the remaining positive food items (r2, r5)
    remaining_ids = {r["place_id"] for r in recs[3:]}
    assert remaining_ids == {"r2", "r5"}

    # Zero-vector items (z1, z2) must not enter Top-5
    for r in recs:
        assert r["place_id"] not in ("z1", "z2")


def test_a2_u0_01_empty_interests_fallback(recommender):
    """A2-U0-01: empty interests -> existing cold-start fallback."""
    res = recommender.recommend(
        preferences={"interests": []},
        destination="da-nang",
        top_k=10,
        model="rec-a2",
    )
    assert res["metadata"]["cold_start"] is True
    assert res["metadata"]["algorithm"] == "COLD_START_DIVERSE_CATALOG_BASELINE"
    assert res["metadata"]["model"] == "cold-start-diverse"
    assert len(res["recommendations"]) == 10


def test_a2_u1_01_positive_relevance_ahead_of_zero(recommender):
    """A2-U1-01: positive-relevance items rank ahead of zero-relevance items."""
    res = recommender.recommend(
        preferences={"interests": ["food_cuisine"]},
        destination="da-nang",
        top_k=10,
        model="rec-a2",
    )
    assert res["metadata"]["model"] == "rec-a2"
    for r in res["recommendations"]:
        assert r["score"] > 0.0
        assert "food_cuisine" in r["matched_interests"]


def test_a2_u1_02_same_relevance_prefers_unseen_category():
    """A2-U1-02: same relevance/interest situation may prefer unseen category."""
    synthetic_places = [
        {
            "place_id": "f1",
            "name": "An Restaurant",
            "category": "restaurant",
            "is_rec_a_core_v2": True,
            "destination_slug": "da-nang",
            "sources": [{"source_name": "osm", "raw_data": {"tier_1": "FOOD_BEVERAGE", "tier_2": "restaurant_dining"}}],
        },
        {
            "place_id": "f2",
            "name": "Binh Restaurant",
            "category": "restaurant",
            "is_rec_a_core_v2": True,
            "destination_slug": "da-nang",
            "sources": [{"source_name": "osm", "raw_data": {"tier_1": "FOOD_BEVERAGE", "tier_2": "restaurant_dining"}}],
        },
        {
            "place_id": "f3",
            "name": "Z Street Food",
            "category": "street_food",
            "is_rec_a_core_v2": True,
            "destination_slug": "da-nang",
            "sources": [{"source_name": "osm", "raw_data": {"tier_1": "FOOD_BEVERAGE", "tier_2": "street_food"}}],
        },
    ]
    engine = PlaceRecommender(places_source=synthetic_places)
    res = engine.recommend(
        preferences={"interests": ["food_cuisine"]},
        destination="da-nang",
        top_k=3,
        model="rec-a2",
    )
    recs = res["recommendations"]
    assert recs[0]["place_id"] == "f1"  # Best name 'An'
    # Second place must be f3 because 'street_food' is an unseen category, beating f2 ('restaurant') despite 'Z' vs 'Binh'
    assert recs[1]["place_id"] == "f3"
    assert recs[2]["place_id"] == "f2"


def test_a2_u2_01_multi_interest_coverage_before_unnecessary_repetition(recommender):
    """A2-U2-01: multi-interest coverage occurs before unnecessary repetition."""
    res = recommender.recommend(
        preferences={"interests": ["food_cuisine", "coffee_culture", "shopping_local"]},
        destination="da-nang",
        top_k=10,
        model="rec-a2",
    )
    # The first 3 places must cover all 3 declared interests
    top_3_interests = {m for r in res["recommendations"][:3] for m in r["matched_interests"]}
    assert top_3_interests == {"food_cuisine", "coffee_culture", "shopping_local"}


def test_a2_u2_02_missing_interest_does_not_crash_or_fabricate():
    """A2-U2-02: missing one requested interest does not crash or fabricate matches."""
    # Synthetic pool where candidates only have food_cuisine, but user requests beach_island and food_cuisine
    synthetic_places = [
        {
            "place_id": f"p{i}",
            "name": f"Food Place {i}",
            "category": "restaurant",
            "is_rec_a_core_v2": True,
            "destination_slug": "da-nang",
            "sources": [{"source_name": "osm", "raw_data": {"tier_1": "FOOD_BEVERAGE", "tier_2": "restaurant_dining"}}],
        }
        for i in range(5)
    ]
    engine = PlaceRecommender(places_source=synthetic_places)
    res = engine.recommend(
        preferences={"interests": ["beach_island", "food_cuisine"]},
        destination="da-nang",
        top_k=5,
        model="rec-a2",
    )
    assert res["metadata"]["model"] == "rec-a2"
    assert len(res["recommendations"]) == 5
    for r in res["recommendations"]:
        assert "beach_island" not in r["matched_interests"]
        assert "food_cuisine" in r["matched_interests"]


def test_a2_rel_01_zero_relevance_cannot_outrank_positive():
    """A2-REL-01: zero-relevance new-category item cannot outrank positive relevant item."""
    synthetic_places = [
        {
            "place_id": "p1",
            "name": "Z Food",
            "category": "restaurant",
            "is_rec_a_core_v2": True,
            "destination_slug": "da-nang",
            "sources": [{"source_name": "osm", "raw_data": {"tier_1": "FOOD_BEVERAGE", "tier_2": "restaurant_dining"}}],
        },
        {
            "place_id": "z1",
            "name": "A Museum",
            "category": "museum",
            "is_rec_a_core_v2": True,
            "destination_slug": "da-nang",
            # User only likes food, so z1 has base_score = 0.0
            "sources": [{"source_name": "osm", "raw_data": {"tier_1": "CULTURE_HERITAGE", "tier_2": "museum_gallery"}}],
        },
    ]
    engine = PlaceRecommender(places_source=synthetic_places)
    res = engine.recommend(
        preferences={"interests": ["food_cuisine"]},
        destination="da-nang",
        top_k=2,
        model="rec-a2",
    )
    recs = res["recommendations"]
    assert recs[0]["place_id"] == "p1"
    assert recs[1]["place_id"] == "z1"


def test_a2_cat_01_unseen_category_preferred_in_equivalent_conditions():
    """A2-CAT-01: within equivalent relevance/coverage conditions, unseen category is preferred."""
    synthetic_places = [
        {
            "place_id": "c1",
            "name": "Cafe Alpha",
            "category": "cafe",
            "is_rec_a_core_v2": True,
            "destination_slug": "da-nang",
            "sources": [{"source_name": "osm", "raw_data": {"tier_1": "FOOD_BEVERAGE", "tier_2": "cafe_tea"}}],
        },
        {
            "place_id": "c2",
            "name": "Cafe Beta",
            "category": "cafe",
            "is_rec_a_core_v2": True,
            "destination_slug": "da-nang",
            "sources": [{"source_name": "osm", "raw_data": {"tier_1": "FOOD_BEVERAGE", "tier_2": "cafe_tea"}}],
        },
        {
            "place_id": "c3",
            "name": "Tea Gamma",
            "category": "tea_house",
            "is_rec_a_core_v2": True,
            "destination_slug": "da-nang",
            "sources": [{"source_name": "osm", "raw_data": {"tier_1": "FOOD_BEVERAGE", "tier_2": "cafe_tea"}}],
        },
    ]
    engine = PlaceRecommender(places_source=synthetic_places)
    res = engine.recommend(
        preferences={"interests": ["coffee_culture"]},
        destination="da-nang",
        top_k=3,
        model="rec-a2",
    )
    recs = res["recommendations"]
    assert recs[0]["place_id"] == "c1"  # First cafe
    assert recs[1]["place_id"] == "c3"  # Unseen category 'tea_house' preferred over c2 ('cafe')
    assert recs[2]["place_id"] == "c2"


def test_a2_zv_01_zero_vectors_do_not_appear_when_enough_positive(recommender):
    """A2-ZV-01: when >= top_k positive items exist, zero-vector items do not appear in Top-K."""
    res = recommender.recommend(
        preferences={"interests": ["food_cuisine"]},
        destination="da-nang",
        top_k=10,
        model="rec-a2",
    )
    for r in res["recommendations"]:
        assert r["score"] > 0.0
        assert len(r["matched_interests"]) > 0


def test_a2_zv_02_zero_items_fill_remaining_slots():
    """A2-ZV-02: when positive items < top_k, zero items only fill the remaining slots."""
    synthetic_places = [
        {
            "place_id": "p1",
            "name": "P1 Food",
            "category": "restaurant",
            "is_rec_a_core_v2": True,
            "destination_slug": "da-nang",
            "sources": [{"source_name": "osm", "raw_data": {"tier_1": "FOOD_BEVERAGE", "tier_2": "restaurant_dining"}}],
        },
        {
            "place_id": "p2",
            "name": "P2 Food",
            "category": "restaurant",
            "is_rec_a_core_v2": True,
            "destination_slug": "da-nang",
            "sources": [{"source_name": "osm", "raw_data": {"tier_1": "FOOD_BEVERAGE", "tier_2": "restaurant_dining"}}],
        },
        {
            "place_id": "z1",
            "name": "Z1 Hotel",
            "category": "hotel",
            "is_rec_a_core_v2": True,
            "destination_slug": "da-nang",
            "sources": [{"source_name": "osm", "raw_data": {"tier_1": "HOSPITALITY", "tier_2": "hotel_resort"}}],
        },
        {
            "place_id": "z2",
            "name": "Z2 Hotel",
            "category": "hotel",
            "is_rec_a_core_v2": True,
            "destination_slug": "da-nang",
            "sources": [{"source_name": "osm", "raw_data": {"tier_1": "HOSPITALITY", "tier_2": "hotel_resort"}}],
        },
    ]
    engine = PlaceRecommender(places_source=synthetic_places)
    res = engine.recommend(
        preferences={"interests": ["food_cuisine"]},
        destination="da-nang",
        top_k=3,
        model="rec-a2",
    )
    recs = res["recommendations"]
    assert len(recs) == 3
    # First 2 are positive
    assert recs[0]["score"] > 0.0
    assert recs[1]["score"] > 0.0
    # 3rd is zero-vector fill
    assert recs[2]["score"] == 0.0
    assert recs[2]["place_id"] in ("z1", "z2")


def test_a2_det_01_repeated_100_times_identical(recommender):
    """A2-DET-01: same request repeated 100 times produces identical place_id order."""
    first_res = recommender.recommend(
        preferences={"interests": ["food_cuisine", "coffee_culture", "shopping_local"]},
        destination="da-nang",
        top_k=10,
        model="rec-a2",
    )
    expected_ids = [r["place_id"] for r in first_res["recommendations"]]
    for _ in range(100):
        res = recommender.recommend(
            preferences={"interests": ["food_cuisine", "coffee_culture", "shopping_local"]},
            destination="da-nang",
            top_k=10,
            model="rec-a2",
        )
        assert [r["place_id"] for r in res["recommendations"]] == expected_ids


def test_a2_dst_01_destination_isolation_preserved(recommender):
    """A2-DST-01: destination isolation preserved."""
    for dst in ["ha-noi", "da-nang", "ha-long"]:
        res = recommender.recommend(
            preferences={"interests": ["food_cuisine"]},
            destination=dst,
            top_k=10,
            model="rec-a2",
        )
        assert res["metadata"]["destination_filter"] == dst
        for r in res["recommendations"]:
            assert r["destination_slug"] == dst


def test_a2_core_01_secondary_pois_never_returned(recommender):
    """A2-CORE-01: secondary POIs never returned."""
    res = recommender.recommend(
        preferences={"interests": ["food_cuisine", "nature_outdoor"]},
        destination=None,
        top_k=50,
        model="rec-a2",
    )
    core_ids = {p["place_id"] for p in recommender.core_places}
    sec_ids = {p["place_id"] for p in recommender.secondary_places}
    for r in res["recommendations"]:
        assert r["place_id"] in core_ids
        assert r["place_id"] not in sec_ids


def test_a2_k_01_top_k_boundaries(recommender):
    """A2-K-01: valid top_k boundaries remain correct."""
    r1 = recommender.recommend(preferences={"interests": ["food_cuisine"]}, destination="da-nang", top_k=1, model="rec-a2")
    assert len(r1["recommendations"]) == 1
    r50 = recommender.recommend(preferences={"interests": ["food_cuisine"]}, destination="da-nang", top_k=50, model="rec-a2")
    assert len(r50["recommendations"]) == 50
    with pytest.raises(ValueError):
        recommender.recommend(preferences={"interests": ["food_cuisine"]}, destination="da-nang", top_k=0, model="rec-a2")
    with pytest.raises(ValueError):
        recommender.recommend(preferences={"interests": ["food_cuisine"]}, destination="da-nang", top_k=51, model="rec-a2")


def test_a2_val_01_invalid_model_still_rejected(recommender):
    """A2-VAL-01: invalid model still rejected."""
    with pytest.raises(ValueError, match="Unsupported recommendation model"):
        recommender.recommend(preferences={"interests": ["food_cuisine"]}, destination="da-nang", top_k=5, model="rec-a9")
    with pytest.raises(ValueError, match="Unsupported recommendation model"):
        recommender.recommend(preferences={"interests": ["food_cuisine"]}, destination="da-nang", top_k=5, model="garbage")


def test_a2_reg_01_reca0_unchanged(recommender):
    """A2-REG-01: rec-a0 behavior unchanged."""
    res = recommender.recommend(preferences={"interests": ["food_cuisine"]}, destination="da-nang", top_k=5, model="rec-a0")
    assert res["metadata"]["model"] == "rec-a0"
    assert res["recommendations"][0]["strategy"] == "rec-a0_content_match"
    assert res["recommendations"][0]["score"] == 1.0


def test_a2_reg_02_reca1_unchanged(recommender):
    """A2-REG-02: rec-a1 behavior unchanged."""
    res = recommender.recommend(preferences={"interests": ["food_cuisine"]}, destination="da-nang", top_k=5, model="rec-a1")
    assert res["metadata"]["model"] == "rec-a1"
    assert res["recommendations"][0]["strategy"] == "rec-a1_content_match"
    assert math.isclose(res["recommendations"][0]["score"], 1.0, rel_tol=1e-5)


def test_a2_out_01_response_contract_complete(recommender):
    """A2-OUT-01: A2 response contract complete."""
    res = recommender.recommend(
        preferences={"interests": ["food_cuisine", "coffee_culture"]},
        destination="da-nang",
        top_k=5,
        model="rec-a2",
    )
    assert res["metadata"]["model"] == "rec-a2"
    assert res["metadata"]["algorithm"] == "Deterministic Relevance-Preserving Multi-Interest Diversity Reranker"
    for r in res["recommendations"]:
        for field in ["place_id", "name", "destination", "destination_slug", "category", "score", "rank", "matched_interests", "explanation", "strategy"]:
            assert field in r
        assert r["strategy"] == "rec-a2_relevance_preserving_diversity"


def test_a2_score_01_public_score_equals_base_a1_relevance(recommender):
    """A2-SCORE-01: public `score` equals base A1 relevance, not diversity/reranking score."""
    res_a1 = recommender.recommend(
        preferences={"interests": ["food_cuisine", "coffee_culture"]},
        destination="da-nang",
        top_k=50,
        model="rec-a1",
    )
    res_a2 = recommender.recommend(
        preferences={"interests": ["food_cuisine", "coffee_culture"]},
        destination="da-nang",
        top_k=50,
        model="rec-a2",
    )
    a1_scores = {r["place_id"]: r["score"] for r in res_a1["recommendations"]}
    for r2 in res_a2["recommendations"]:
        pid = r2["place_id"]
        if pid in a1_scores:
            assert math.isclose(r2["score"], a1_scores[pid], rel_tol=1e-5)
