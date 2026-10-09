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

import hashlib
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


def compute_sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


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
            top_k=300,
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
    for manifest_name in ["dataset-freeze-v1.sha256", "dataset-freeze-v2.sha256"]:
        manifest_path = REPO_ROOT / "data" / "manifests" / manifest_name
        assert manifest_path.exists(), f"Missing manifest: {manifest_path}"
        with open(manifest_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                expected_sha, rel_path = line.split(None, 1)
                target_file = REPO_ROOT / rel_path.strip()
                assert target_file.exists(), f"Target file missing: {rel_path}"
                actual_sha = compute_sha256(target_file)
                assert actual_sha == expected_sha, f"SHA mismatch on {rel_path}! Expected {expected_sha}, got {actual_sha}"
